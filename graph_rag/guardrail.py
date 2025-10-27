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
        # Get trace ID for audit correlation
        try:
            current_span = get_current_span()
            trace_id = f"{current_span.context.trace_id:032x}" if current_span and hasattr(current_span, 'context') and current_span.context.is_valid else "no-trace"
        except:
            trace_id = "no-trace"
        
        # Run heuristic checks on ORIGINAL input (before sanitization removes suspicious patterns)
        is_malicious = is_probably_malicious(question)
        
        # Sanitize for logging/audit purposes
        sanitized_question = sanitize_text(question)
        
        if is_malicious:
            # Block suspicious input
            reason = "heuristic_pattern_match"
            logger.warning(f"Guardrail blocked suspicious input: {sanitized_question[:100]}...")
            
            # Increment metrics
            guardrail_blocks_total.labels(reason=reason).inc()
            
            # Add span attributes
            add_span_attributes(span,
                allowed=False,
                reason=reason,
                sanitized_question=sanitized_question[:100],
                check_type="heuristic"
            )
            
            # Audit log the block
            audit_store.record({
                "event": "guardrail_blocked",
                "reason": reason,
                "question_preview": sanitized_question[:100],
                "trace_id": trace_id,
                "check_type": "heuristic"
            })
            
            return False
        else:
            # Allow legitimate input (default behavior)
            logger.debug(f"Guardrail check passed for: {sanitized_question[:100]}...")
            
            # Add span attributes
            add_span_attributes(span,
                allowed=True,
                reason="heuristic_pass",
                sanitized_question=sanitized_question[:100],
                check_type="heuristic"
            )
            
            # Audit log the pass (debug level)
            audit_store.record({
                "event": "guardrail_passed",
                "reason": "heuristic_pass",
                "question_preview": sanitized_question[:100],
                "trace_id": trace_id,
                "check_type": "heuristic"
            })
            
            return True
