# graph_rag/health.py
"""
Health check utilities for Graph RAG system components.

This module provides health check functions to verify that critical
components are working correctly before deployment.
"""

import logging
from typing import Dict, Any, Tuple
from graph_rag.json_utils import validate_guardrail_schema
from graph_rag.observability import get_logger
from graph_rag.flags import get_all_flags

logger = get_logger(__name__)


def guardrail_classifier_ok() -> Tuple[bool, str]:
    """
    Verify that the guardrail classifier schema is correct.
    
    This function validates:
    - Guardrail schema structure
    - JSON normalization functions
    - Required fields validation
    
    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        logger.info("Starting guardrail classifier health check")
        
        # Test schema validation
        is_valid, error_msg = validate_guardrail_schema()
        if not is_valid:
            logger.error(f"Guardrail schema validation failed: {error_msg}")
            return False, f"Schema validation failed: {error_msg}"
        
        # Test with various input formats
        test_cases = [
            {"allowed": True, "reason": "Test reason"},
            {"classification": "allow", "explanation": "Test explanation"},
            {"classification": "block", "justification": "Test justification"},
        ]
        
        for i, test_case in enumerate(test_cases):
            try:
                from graph_rag.json_utils import normalize_guardrail_response
                normalized = normalize_guardrail_response(test_case)
                
                # Verify required fields exist
                if "allowed" not in normalized:
                    return False, f"Test case {i+1}: Missing 'allowed' field after normalization"
                
                if "reason" not in normalized:
                    return False, f"Test case {i+1}: Missing 'reason' field after normalization"
                
                # Verify field types
                if not isinstance(normalized["allowed"], bool):
                    return False, f"Test case {i+1}: 'allowed' field is not boolean"
                
                if not isinstance(normalized["reason"], str):
                    return False, f"Test case {i+1}: 'reason' field is not string"
                
                logger.debug(f"Test case {i+1} passed: {normalized}")
                
            except Exception as e:
                return False, f"Test case {i+1} failed: {e}"
        
        logger.info("Guardrail classifier health check passed")
        return True, "Guardrail classifier is healthy"
        
    except Exception as e:
        error_msg = f"Guardrail classifier health check failed: {e}"
        logger.error(error_msg)
        return False, error_msg


def llm_client_ok() -> Tuple[bool, str]:
    """
    Verify that the LLM client is properly configured.
    
    This function validates:
    - LLM client initialization
    - JSON mode configuration
    - Retry logic configuration
    
    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        logger.info("Starting LLM client health check")
        
        # Check feature flags
        flags = get_all_flags()
        logger.debug(f"Current feature flags: {flags}")
        
        # Verify JSON mode is enabled (should be True by default)
        if not flags.get("LLM_JSON_MODE_ENABLED", False):
            logger.warning("LLM_JSON_MODE_ENABLED is disabled - this may cause parsing issues")
        
        # Test LLM client import and basic functionality
        try:
            from graph_rag.llm_client import call_llm_structured, LLMStructuredError
            from graph_rag.llm_client import _should_use_mock, _get_gemini_client
            
            # Check if we're in mock mode (expected in test environments)
            is_mock = _should_use_mock()
            logger.debug(f"LLM client mock mode: {is_mock}")
            
            # Try to get client (should not fail even if no API key)
            client = _get_gemini_client()
            if client is None and not is_mock:
                logger.warning("Gemini client is None - check API key configuration")
            
        except ImportError as e:
            return False, f"Failed to import LLM client modules: {e}"
        except Exception as e:
            return False, f"LLM client initialization error: {e}"
        
        logger.info("LLM client health check passed")
        return True, "LLM client is healthy"
        
    except Exception as e:
        error_msg = f"LLM client health check failed: {e}"
        logger.error(error_msg)
        return False, error_msg


def json_utils_ok() -> Tuple[bool, str]:
    """
    Verify that JSON utilities are working correctly.
    
    This function validates:
    - JSON parsing functions
    - Tolerant parser functionality
    - Content redaction
    
    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        logger.info("Starting JSON utilities health check")
        
        # Test JSON parsing functions
        from graph_rag.json_utils import (
            extract_first_json, 
            normalize_guardrail_response,
            tolerant_json_parse,
            redact_sensitive_content,
            validate_json_schema
        )
        
        # Test extract_first_json
        test_text = 'Some text {"test": "value"} more text'
        extracted = extract_first_json(test_text)
        if extracted is None:
            return False, "extract_first_json failed to extract JSON"
        
        if extracted.get("test") != "value":
            return False, "extract_first_json returned incorrect data"
        
        # Test normalize_guardrail_response
        test_data = {"classification": "allow", "explanation": "Test"}
        normalized = normalize_guardrail_response(test_data)
        if not isinstance(normalized.get("allowed"), bool):
            return False, "normalize_guardrail_response failed to normalize 'allowed' field"
        
        if not isinstance(normalized.get("reason"), str):
            return False, "normalize_guardrail_response failed to normalize 'reason' field"
        
        # Test tolerant_json_parse
        malformed_json = '{"classification": "allow", "explanation": "Test"}'
        parsed = tolerant_json_parse(malformed_json, schema_type="guardrail")
        if parsed is None:
            return False, "tolerant_json_parse failed to parse malformed JSON"
        
        # Test redact_sensitive_content
        sensitive_text = '{"password": "secret123", "token": "abc123"}'
        redacted = redact_sensitive_content(sensitive_text)
        if "secret123" in redacted or "abc123" in redacted:
            return False, "redact_sensitive_content failed to redact sensitive data"
        
        # Test validate_json_schema
        valid_data = {"allowed": True, "reason": "Test"}
        is_valid, error_msg = validate_json_schema(valid_data, ["allowed", "reason"])
        if not is_valid:
            return False, f"validate_json_schema failed on valid data: {error_msg}"
        
        invalid_data = {"allowed": True}  # Missing required field
        is_valid, error_msg = validate_json_schema(invalid_data, ["allowed", "reason"])
        if is_valid:
            return False, "validate_json_schema should have failed on invalid data"
        
        logger.info("JSON utilities health check passed")
        return True, "JSON utilities are healthy"
        
    except Exception as e:
        error_msg = f"JSON utilities health check failed: {e}"
        logger.error(error_msg)
        return False, error_msg


def system_health_check() -> Dict[str, Any]:
    """
    Perform a comprehensive health check of the Graph RAG system.
    
    Returns:
        Dictionary with health status of all components
    """
    logger.info("Starting comprehensive system health check")
    
    health_status = {
        "overall_healthy": True,
        "components": {},
        "timestamp": None,
        "feature_flags": get_all_flags()
    }
    
    # Import datetime for timestamp
    from datetime import datetime, timezone
    health_status["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    # Check each component
    components = [
        ("guardrail_classifier", guardrail_classifier_ok),
        ("llm_client", llm_client_ok),
        ("json_utils", json_utils_ok),
    ]
    
    for component_name, check_function in components:
        try:
            is_healthy, message = check_function()
            health_status["components"][component_name] = {
                "healthy": is_healthy,
                "message": message
            }
            
            if not is_healthy:
                health_status["overall_healthy"] = False
                logger.error(f"Component {component_name} failed health check: {message}")
            else:
                logger.info(f"Component {component_name} passed health check")
                
        except Exception as e:
            health_status["components"][component_name] = {
                "healthy": False,
                "message": f"Health check exception: {e}"
            }
            health_status["overall_healthy"] = False
            logger.error(f"Component {component_name} health check exception: {e}")
    
    # Log overall status
    if health_status["overall_healthy"]:
        logger.info("System health check PASSED - all components healthy")
    else:
        logger.error("System health check FAILED - some components unhealthy")
    
    return health_status


def print_health_report(health_status: Dict[str, Any]) -> None:
    """
    Print a formatted health report to the console.
    
    Args:
        health_status: Health status dictionary from system_health_check()
    """
    print("\n" + "="*60)
    print("GRAPH RAG SYSTEM HEALTH REPORT")
    print("="*60)
    print(f"Timestamp: {health_status['timestamp']}")
    print(f"Overall Status: {'✅ HEALTHY' if health_status['overall_healthy'] else '❌ UNHEALTHY'}")
    print()
    
    print("Component Status:")
    for component, status in health_status["components"].items():
        status_icon = "✅" if status["healthy"] else "❌"
        print(f"  {status_icon} {component}: {status['message']}")
    
    print()
    print("Feature Flags:")
    for flag, value in health_status["feature_flags"].items():
        print(f"  {flag}: {value}")
    
    print("="*60)


if __name__ == "__main__":
    # Run health check when script is executed directly
    health_status = system_health_check()
    print_health_report(health_status)
    
    # Exit with appropriate code
    exit(0 if health_status["overall_healthy"] else 1)
