# main.py
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from graph_rag.rag import rag_chain
from graph_rag.observability import start_metrics_server, get_logger
from graph_rag.conversation_store import conversation_store
from graph_rag.sanitizer import sanitize_text, is_probably_malicious
from graph_rag.audit_store import audit_store
from graph_rag.guardrail import guardrail_check
from graph_rag.config_manager import get_config_value, ensure_production_flags
from graph_rag.schema_manager import ensure_schema_loaded, ensure_chunk_vector_index
from graph_rag.schema_embeddings import upsert_schema_embeddings
from graph_rag.flags import get_all_flags, SCHEMA_BOOTSTRAP_ENABLED
from graph_rag.admin_api import admin_router
import uuid

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on application startup"""
    # Ensure production flags are set correctly
    ensure_production_flags()
    
    # Log feature flags at startup (DEBUG level)
    flags = get_all_flags()
    logger.debug(f"Feature flags: {flags}")
    
    # Check if schema bootstrap is enabled
    schema_bootstrap_enabled = SCHEMA_BOOTSTRAP_ENABLED()
    app_mode = os.getenv("APP_MODE", "read_only").lower()
    allow_writes = os.getenv("ALLOW_WRITES", "false").lower() in ("true", "1", "yes", "on")
    write_allowed = app_mode == "admin" or allow_writes
    
    logger.info(f"Schema bootstrap: enabled={schema_bootstrap_enabled}, write_allowed={write_allowed}")
    
    if schema_bootstrap_enabled and write_allowed:
        # Admin/write mode: Generate schema and upsert embeddings (idempotent)
        try:
            logger.info("Running schema bootstrap in write mode")
            ensure_schema_loaded()  # Will skip if fingerprint unchanged
            
            # Upsert schema embeddings (idempotent)
            result = upsert_schema_embeddings()
            logger.info(f"Schema ingestion complete: {result.get('status')}")
            
            # Ensure chunk vector index exists (if enabled)
            try:
                vector_index_success = ensure_chunk_vector_index()
                if vector_index_success:
                    logger.info("Chunk vector index verification/creation completed")
                else:
                    logger.warning("Chunk vector index verification/creation failed")
            except Exception as e:
                logger.error(f"Chunk vector index operation failed: {e}")
                # Don't fail startup, continue without vector index
            
            # Record successful bootstrap
            audit_store.record({
                "event": "schema_bootstrap_complete",
                "status": result.get("status"),
                "nodes_created": result.get("nodes_created", 0),
                "nodes_updated": result.get("nodes_updated", 0),
                "timestamp": str(uuid.uuid4())
            })
        except Exception as e:
            logger.error(f"Schema bootstrap failed: {e}")
            audit_store.record({
                "event": "schema_bootstrap_failed",
                "error": str(e),
                "timestamp": str(uuid.uuid4())
            })
            # Don't fail startup, continue in degraded mode
    elif schema_bootstrap_enabled:
        # Bootstrap enabled but read-only mode: Only load existing schema
        try:
            logger.info("Loading existing schema in read-only mode")
            ensure_schema_loaded()  # Will load existing allow-list
        except FileNotFoundError as e:
            logger.error(f"Schema load failed in read-only mode: {e}")
            logger.warning("Application starting without schema - queries may fail")
    else:
        logger.info("Schema bootstrap disabled, skipping schema loading")
    
    conversation_store.init()
    # Start metrics server if enabled in config
    if get_config_value("observability.metrics_enabled", True):
        start_metrics_server()
    yield
    # Cleanup code can go here if needed

app = FastAPI(title="GraphRAG", lifespan=lifespan)

# Register admin router for administrative endpoints
app.include_router(admin_router)

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    question: str
    format_type: str | None = None  # Optional: "text", "table", "graph"

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Asynchronous chat endpoint that offloads heavy RAG processing to a thread pool.
    
    This endpoint handles user questions by:
    1. Sanitizing and validating input (synchronous)
    2. Running guardrail checks (synchronous)
    3. Offloading RAG chain invocation to thread pool (asynchronous)
    4. Recording conversation history
    5. Applying format_type if requested (text/table/graph)
    
    The heavy `rag_chain.invoke` call runs in a thread pool to preserve server
    concurrency and prevent blocking other requests.
    
    Parameters:
    - format_type: Optional format for response ("text", "table", "graph")
    - Returns trace_id and audit_id for tracking
    """
    if not req.question:
        raise HTTPException(400, "Question is required")

    # Sanitize the input immediately
    original_question = req.question
    req.question = sanitize_text(req.question)
    
    # Check if the original question is probably malicious
    if is_probably_malicious(original_question):
        # Record audit entry
        audit_store.record({
            "type": "malicious_input_blocked",
            "original_question": original_question,
            "sanitized_question": req.question,
            "timestamp": str(uuid.uuid4()),  # Using uuid as simple timestamp placeholder
            "action": "blocked_403",
            "check_type": "heuristic"
        })
        logger.warning(f"Malicious input blocked by heuristic: {original_question[:100]}...")
        raise HTTPException(403, "Input flagged for manual review")

    # # Run LLM guardrail check on sanitized input
    if not guardrail_check(req.question):
        # Record audit entry for guardrail block
        audit_store.record({
            "type": "guardrail_blocked",
            "original_question": original_question,
            "sanitized_question": req.question,
            "timestamp": str(uuid.uuid4()),
            "action": "blocked_403",
            "check_type": "llm_guardrail"
        })
        logger.warning(f"Input blocked by LLM guardrail: {original_question[:100]}...")
        raise HTTPException(403, "Input flagged for manual review")

    conv_id = req.conversation_id if req.conversation_id else str(uuid.uuid4())
    
    conversation_store.add_message(conv_id, {"role": "user", "text": req.question})

    try:
        # Offload heavy RAG processing to thread pool to preserve server concurrency
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, rag_chain.invoke, req.question, req.format_type)
        
        conversation_store.add_message(conv_id, {"role": "assistant", "text": resp.get("answer"), "trace_id": resp.get("trace_id")})
        resp["conversation_id"] = conv_id
        
        # Always include trace_id and audit_id for tracking
        resp["trace_id"] = resp.get("trace_id", "no-trace")
        resp["audit_id"] = resp.get("audit_id", "no-audit")
        
        return resp
    except Exception as e:
        logger.error(f"Error in /api/chat: {e}")
        raise HTTPException(500, "internal error")

@app.get("/api/chat/{conversation_id}/history")
def get_history(conversation_id: str):
    history = conversation_store.get_history(conversation_id)
    if not history:
        raise HTTPException(404, "Conversation not found")
    return history

# Note: Admin routes have been moved to graph_rag/admin_api.py
# The /admin/schema/refresh endpoint is now handled by admin_router
#
# @app.post("/admin/schema/refresh")
# def admin_schema_refresh(x_admin_token: str | None = Header(None)):
#     """
#     DEPRECATED: This route has been moved to admin_api.py
#     Use admin_router for all administrative endpoints.
#     """
#     pass

@app.get("/health")
def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns a simple status indicating the application is running.
    This endpoint does not check external dependencies and should
    respond quickly for health checks.
    """
    return {"status": "ok"}
