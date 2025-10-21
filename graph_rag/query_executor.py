# graph_rag/query_executor.py
"""
Guarded query execution module for safe Cypher query execution.
Provides read-only query execution with timeout and limit enforcement.
"""
import os
from typing import List, Dict, Any, Optional
from graph_rag.observability import get_logger
from graph_rag.config_manager import get_config_value
from graph_rag.neo4j_client import Neo4jClient
from graph_rag.audit_store import audit_store

logger = get_logger(__name__)

def safe_execute(cypher: str, params: Dict[str, Any] = None, timeout: int = None) -> List[Dict[str, Any]]:
    """
    Safely execute a read-only Cypher query with timeout and limit enforcement.
    
    This function provides guarded execution of Cypher queries with the following safety measures:
    - Enforces read-only mode (no write operations)
    - Applies configurable timeout limits
    - Enforces result set limits to prevent resource exhaustion
    - Comprehensive error handling and audit logging
    
    Args:
        cypher: The Cypher query string to execute
        params: Optional parameters for the query
        timeout: Optional timeout in seconds (overrides config default)
        
    Returns:
        List of dictionaries representing query results
        
    Raises:
        RuntimeError: If query execution fails or violates safety constraints
    """
    if not cypher or not cypher.strip():
        logger.warning("Empty Cypher query provided for execution")
        audit_store.record({
            "event": "query_execution_failed",
            "reason": "empty_query",
            "cypher_preview": "",
            "error": "Empty query provided"
        })
        raise RuntimeError("Empty Cypher query provided")
    
    # Ensure read-only mode
    app_mode = os.getenv("APP_MODE", "read_only").lower()
    if app_mode not in ["read_only", "admin"]:
        logger.warning(f"Query execution attempted in non-read-only mode: {app_mode}")
        audit_store.record({
            "event": "query_execution_blocked",
            "reason": "non_read_only_mode",
            "app_mode": app_mode,
            "cypher_preview": cypher[:200]
        })
        raise RuntimeError(f"Query execution not allowed in mode: {app_mode}")
    
    try:
        # Get configuration values
        max_results = get_config_value('guardrails.max_results', 1000)
        default_timeout = get_config_value('guardrails.query_timeout', 30)
        execution_timeout = timeout or default_timeout
        
        # Apply LIMIT enforcement if not present
        # Heuristic: Check if query already contains LIMIT clause (case-insensitive)
        cypher_upper = cypher.upper()
        if 'LIMIT' not in cypher_upper:
            # Append LIMIT clause to prevent resource exhaustion
            limited_cypher = f"{cypher.rstrip(';')} LIMIT {max_results}"
            logger.debug(f"Applied LIMIT {max_results} to query without explicit limit")
        else:
            limited_cypher = cypher
            logger.debug("Query already contains LIMIT clause")
        
        # Initialize Neo4j client
        neo4j_client = Neo4jClient()
        
        # Execute the query
        logger.info(f"Executing guarded query with timeout {execution_timeout}s")
        logger.debug(f"Query preview: {cypher[:100]}{'...' if len(cypher) > 100 else ''}")
        
        results = neo4j_client.execute_read_query(
            query=limited_cypher,
            params=params or {},
            timeout=execution_timeout,
            query_name="user_query"
        )
        
        # Log successful execution
        result_count = len(results) if results else 0
        logger.info(f"Query executed successfully, returned {result_count} results")
        
        # Record successful execution in audit log
        audit_store.record({
            "event": "query_execution_success",
            "cypher_preview": cypher[:200],
            "result_count": result_count,
            "timeout_used": execution_timeout,
            "limit_applied": max_results if 'LIMIT' not in cypher_upper else None
        })
        
        return results
        
    except Exception as e:
        # Log error and record in audit store
        error_msg = f"Query execution failed: {str(e)}"
        logger.error(error_msg)
        
        audit_store.record({
            "event": "query_execution_failed",
            "reason": "execution_error",
            "cypher_preview": cypher[:200],
            "error": str(e),
            "timeout_used": execution_timeout if 'execution_timeout' in locals() else None
        })
        
        # Re-raise as RuntimeError for consistent error handling
        raise RuntimeError(error_msg) from e

def validate_query_safety(cypher: str) -> bool:
    """
    Validate that a query is safe for execution (read-only, no dangerous operations).
    
    This is a lightweight check that can be used before calling safe_execute.
    For comprehensive validation, use cypher_validator.validate_cypher().
    
    Args:
        cypher: The Cypher query string to validate
        
    Returns:
        True if query appears safe for execution
    """
    if not cypher or not cypher.strip():
        return False
    
    # Basic read-only check - look for dangerous keywords
    dangerous_keywords = ['CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE', 'DROP', 'CALL']
    cypher_upper = cypher.upper()
    
    for keyword in dangerous_keywords:
        if keyword in cypher_upper:
            logger.warning(f"Query contains potentially dangerous keyword: {keyword}")
            return False
    
    return True

def get_execution_stats() -> Dict[str, Any]:
    """
    Get current execution statistics and configuration.
    
    Returns:
        Dictionary containing execution configuration and limits
    """
    return {
        "max_results": get_config_value('guardrails.max_results', 1000),
        "default_timeout": get_config_value('guardrails.query_timeout', 30),
        "app_mode": os.getenv("APP_MODE", "read_only"),
        "read_only_enforced": True
    }
