# graph_rag/admin_api.py
"""
Admin API router for administrative actions.

This module provides dedicated endpoints for administrative operations like
schema refresh and embedding regeneration. These endpoints are unprotected
and designed for local and containerized environments.

No authentication is implemented at this time.
"""
import time
from fastapi import APIRouter, HTTPException
from graph_rag.observability import get_logger
from graph_rag.schema_manager import ensure_schema_loaded, ensure_chunk_vector_index
from graph_rag.schema_embeddings import upsert_schema_embeddings

logger = get_logger(__name__)

# Create admin router with /admin prefix
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.post("/schema/refresh")
async def admin_schema_refresh():
    """
    Force-refresh schema metadata, embeddings, and vector index.
    
    This endpoint sequentially executes:
    1. ensure_schema_loaded(force=True) - Refresh schema from Neo4j
    2. upsert_schema_embeddings() - Generate embeddings, DROP existing vector index,
       CREATE new index with current embedding dimension, and overwrite all embeddings
    3. ensure_chunk_vector_index() - Ensure chunk vector index exists
    
    The vector index is ALWAYS dropped and recreated to ensure dimension matches
    current embedding provider (e.g., when switching from 8-dim mock to 768-dim Gemini).
    
    No authentication required at this time.
    
    Returns:
        dict: {"status": "success", "duration_s": <elapsed_time>}
        
    Raises:
        HTTPException: 500 if any step fails
        
    Example:
        POST /admin/schema/refresh
        Response: {"status": "success", "duration_s": 2.47}
    """
    start_time = time.time()
    
    try:
        logger.info("Starting schema refresh...")
        
        # Step 1: Force-refresh schema from Neo4j
        logger.info("Step 1/3: Refreshing schema from Neo4j...")
        ensure_schema_loaded(force=True)
        logger.info("Schema loaded successfully")
        
        # Step 2: Upsert schema embeddings (includes drop+recreate of vector index)
        logger.info("Step 2/3: Upserting schema embeddings and recreating vector index...")
        embedding_result = upsert_schema_embeddings()
        logger.info(f"Schema embeddings upserted: {embedding_result.get('nodes_created', 0)} created, "
                   f"{embedding_result.get('nodes_updated', 0)} updated, "
                   f"index {embedding_result.get('index_status', 'unknown')} with "
                   f"{embedding_result.get('embedding_dimensions', 0)} dimensions")
        
        # Step 3: Ensure chunk vector index exists
        logger.info("Step 3/3: Ensuring chunk vector index...")
        ensure_chunk_vector_index()
        logger.info("Chunk vector index verified")
        
        # Calculate elapsed time
        elapsed = round(time.time() - start_time, 2)
        logger.info(f"Schema refresh completed successfully in {elapsed}s")
        
        return {
            "status": "success",
            "duration_s": elapsed,
            "steps_completed": [
                "ensure_schema_loaded",
                "upsert_schema_embeddings",
                "ensure_chunk_vector_index"
            ]
        }
        
    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        error_msg = f"Schema refresh failed after {elapsed}s: {str(e)}"
        logger.exception(error_msg)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@admin_router.get("/schema/status")
async def admin_schema_status():
    """
    Get current schema status information.
    
    This endpoint provides information about the current schema state without
    triggering a refresh.
    
    Returns:
        dict: Schema status information including fingerprint, labels count, etc.
        
    Example:
        GET /admin/schema/status
        Response: {"status": "loaded", "fingerprint": "abc123...", ...}
    """
    try:
        from graph_rag.schema_manager import get_schema_fingerprint, get_allow_list
        
        fingerprint = get_schema_fingerprint()
        allow_list = get_allow_list()
        
        return {
            "status": "loaded" if allow_list else "not_loaded",
            "fingerprint": fingerprint[:16] + "..." if fingerprint else None,
            "labels_count": len(allow_list.get('node_labels', [])) if allow_list else 0,
            "relationships_count": len(allow_list.get('relationship_types', [])) if allow_list else 0,
            "properties_count": len(allow_list.get('properties', {})) if allow_list else 0
        }
        
    except Exception as e:
        logger.exception("Failed to get schema status")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

