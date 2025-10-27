# graph_rag/guardrail.py
"""
Heuristic-based guardrail system for detecting malicious input.

This module provides lightweight, fast input validation using pattern-based
heuristics without requiring LLM calls. It blocks suspicious patterns while
allowing legitimate business queries through.
"""

from graph_rag.sanitizer import sanitize_text, is_probably_malicious
from graph_rag.observability import get_logger, guardrail_blocks_total, create_pipeline_span, add_span_attributes
from graph_rag.audit_store import audit_store
from opentelemetry.trace import get_current_span

logger = get_logger(__name__)


def guardrail_check(question: str) -> bool:
    """
    Performs a heuristic-based guardrail check to detect suspicious input patterns.
    
    Returns True by default, only blocking when heuristics flag the input as suspicious.
    This approach provides fast, deterministic validation without LLM dependencies.
    
    Args:
        question: The user question to analyze
        
    Returns:
        True if the question is allowed (default), False if it should be blocked
    """
    
    with create_pipeline_span("guardrail.check", question=question[:100]) as span:
        try:
            # Sanitize the input for logging/audit purposes
            sanitized_question = sanitize_text(question)
            
            # Compute suspiciousness using heuristics on ORIGINAL input
            # (before sanitization removes patterns we need to detect)
            suspicious = is_probably_malicious(question)
            
            # Determine allowed status and reason
            allowed = not suspicious
            reason = "heuristic_block" if suspicious else "heuristic_allow"
            
            # Add span attributes
            add_span_attributes(span,
                allowed=allowed,
                reason=reason,
                sanitized_question=sanitized_question[:100]
            )
            
            # Get trace ID for audit correlation
            try:
                current_span = get_current_span()
                trace_id = f"{current_span.context.trace_id:032x}" if current_span and hasattr(current_span, 'context') and current_span.context.is_valid else "no-trace"
            except:
                trace_id = "no-trace"
            
            if suspicious:
                # Block suspicious input
                logger.warning(f"Guardrail blocked suspicious input: {sanitized_question[:100]}...")
                
                # Increment metrics
                guardrail_blocks_total.labels(reason="heuristic_detected").inc()
                
                # Audit log the block
                audit_store.record({
                    "event": "guardrail_blocked",
                    "reason": "heuristic_detected",
                    "question_preview": sanitized_question[:100],
                    "trace_id": trace_id
                })
                
                return False
            else:
                # Allow legitimate input (default behavior)
                logger.debug(f"Guardrail check passed for: {sanitized_question[:100]}...")
                
                # Audit log the pass (optional, for debugging)
                audit_store.record({
                    "event": "guardrail_passed",
                    "reason": "heuristic_allow",
                    "question_preview": sanitized_question[:100],
                    "trace_id": trace_id
                })
                
                return True
                
        except Exception as e:
            # Fail-open by default: don't block legitimate traffic on unexpected errors
            logger.error(f"Unexpected error in guardrail check: {e}")
            
            # Try to get trace ID for audit
            try:
                current_span = get_current_span()
                trace_id = f"{current_span.context.trace_id:032x}" if current_span and hasattr(current_span, 'context') and current_span.context.is_valid else "no-trace"
            except:
                trace_id = "no-trace"
            
            # Audit log the error
            audit_store.record({
                "event": "guardrail_error",
                "reason": "unexpected_error",
                "error": str(e),
                "question_preview": question[:100] if isinstance(question, str) else "",
                "trace_id": trace_id
            })
            
            # Fail-open: return True to allow the query through
            return True
