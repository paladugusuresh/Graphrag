# main.py
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from graph_rag.rag import rag_chain
from graph_rag.observability import start_metrics_server, get_logger
from graph_rag.conversation_store import conversation_store
from graph_rag.sanitizer import sanitize_text, is_probably_malicious
from graph_rag.audit_store import audit_store
from graph_rag.guardrail import guardrail_check
from graph_rag.config_manager import get_config_value
import uuid

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on application startup"""
    conversation_store.init()
    # Start metrics server if enabled in config
    if get_config_value("observability.metrics_enabled", True):
        start_metrics_server()
    yield
    # Cleanup code can go here if needed

app = FastAPI(title="GraphRAG", lifespan=lifespan)

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    question: str

@app.post("/api/chat")
def chat(req: ChatRequest):
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

    # Run LLM guardrail check on sanitized input
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
        resp = rag_chain.invoke(req.question)
        conversation_store.add_message(conv_id, {"role": "assistant", "text": resp.get("answer"), "trace_id": resp.get("trace_id")})
        resp["conversation_id"] = conv_id
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
