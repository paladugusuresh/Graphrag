# graph_rag/json_utils.py
"""
Tolerant JSON parsing utilities for development mode.

This module provides a tolerant JSON parser that can extract and normalize
JSON objects from LLM text output, useful for development when LLMs may
return malformed or non-standard JSON responses.
"""

import json
import re
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def extract_first_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract the first JSON object from text.
    
    Args:
        text: Input text that may contain JSON
        
    Returns:
        First JSON object found, or None if none found
    """
    if not text or not isinstance(text, str):
        return None
    
    # Look for JSON object patterns
    json_patterns = [
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Simple nested objects
        r'\{[^{}]*\}',  # Simple objects without nesting
        r'\{.*?\}',  # Greedy match for objects
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                # Try to parse as JSON
                parsed = json.loads(match)
                if isinstance(parsed, dict):
                    logger.debug(f"Extracted JSON object: {match[:100]}...")
                    return parsed
            except json.JSONDecodeError:
                continue
    
    # If no complete JSON found, try to fix common issues
    # Look for opening brace and try to add closing brace
    start_idx = text.find('{')
    if start_idx != -1:
        # Find the last quote or comma before end of string
        remaining = text[start_idx:]
        # Try to add closing brace
        try:
            fixed_json = remaining + '}'
            parsed = json.loads(fixed_json)
            if isinstance(parsed, dict):
                logger.debug(f"Fixed JSON by adding closing brace: {fixed_json[:100]}...")
                return parsed
        except json.JSONDecodeError:
            pass
    
    logger.debug("No valid JSON object found in text")
    return None


def normalize_guardrail_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize guardrail response data to expected schema.
    
    Args:
        data: Raw JSON data from LLM
        
    Returns:
        Normalized data matching expected schema
    """
    normalized = {}
    
    # Normalize 'allowed' field
    if 'allowed' in data:
        normalized['allowed'] = bool(data['allowed'])
    elif 'classification' in data:
        # Handle variations like "allow", "block", "deny"
        classification = str(data['classification']).lower()
        if classification in ['allow', 'allowed', 'permit', 'ok', 'pass']:
            normalized['allowed'] = True
        elif classification in ['block', 'deny', 'reject', 'fail', 'no']:
            normalized['allowed'] = False
        else:
            # Default to False for unknown classifications
            normalized['allowed'] = False
            logger.warning(f"Unknown classification value: {data['classification']}")
    else:
        # Default to False if no allowed/classification field
        normalized['allowed'] = False
        logger.warning("No 'allowed' or 'classification' field found")
    
    # Normalize 'reason' field
    if 'reason' in data:
        normalized['reason'] = str(data['reason'])
    elif 'explanation' in data:
        normalized['reason'] = str(data['explanation'])
    elif 'justification' in data:
        normalized['reason'] = str(data['justification'])
    else:
        # Provide default reason
        normalized['reason'] = "No reason provided"
    
    # Copy any other fields that might be useful
    for key, value in data.items():
        if key not in ['allowed', 'classification', 'reason', 'explanation', 'justification']:
            normalized[key] = value
    
    logger.debug(f"Normalized guardrail response: {normalized}")
    return normalized


def tolerant_json_parse(text: str, schema_type: str = "guardrail") -> Optional[Dict[str, Any]]:
    """
    Parse JSON text with tolerance for common variations.
    
    Args:
        text: JSON text to parse
        schema_type: Type of schema to normalize for
        
    Returns:
        Parsed and normalized JSON data, or None if parsing fails
    """
    if not text or not isinstance(text, str):
        return None
    
    # First try standard JSON parsing
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            logger.debug("Standard JSON parsing succeeded")
            return parsed
    except json.JSONDecodeError:
        logger.debug("Standard JSON parsing failed, trying tolerant parsing")
    
    # Try to extract first JSON object
    extracted = extract_first_json(text)
    if not extracted:
        logger.debug("No JSON object could be extracted from text")
        return None
    
    # Normalize based on schema type
    if schema_type == "guardrail":
        return normalize_guardrail_response(extracted)
    else:
        # For other schema types, return as-is for now
        return extracted


def validate_json_schema(data: Dict[str, Any], required_fields: list) -> Tuple[bool, str]:
    """
    Validate that JSON data contains required fields.
    
    Args:
        data: JSON data to validate
        required_fields: List of required field names
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Data is not a dictionary"
    
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    return True, ""


def redact_sensitive_content(text: str, max_length: int = 512) -> str:
    """
    Redact sensitive content from text for logging.
    
    Args:
        text: Text to redact
        max_length: Maximum length of returned text
        
    Returns:
        Redacted text safe for logging
    """
    if not text:
        return ""
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    # Simple redaction patterns (can be extended)
    redaction_patterns = [
        (r'password["\']?\s*:\s*["\'][^"\']+["\']', 'password": "[REDACTED]"'),
        (r'token["\']?\s*:\s*["\'][^"\']+["\']', 'token": "[REDACTED]"'),
        (r'key["\']?\s*:\s*["\'][^"\']+["\']', 'key": "[REDACTED]"'),
    ]
    
    redacted = text
    for pattern, replacement in redaction_patterns:
        redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
    
    return redacted


def safe_parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Safely parse JSON with automatic repairs for common malformations.
    
    This function implements a multi-stage parsing strategy:
    1. Try standard JSON parsing
    2. Apply common repairs (trailing commas, quotes, markdown fences)
    3. Extract first JSON object from text
    
    Args:
        raw_text: Raw text from LLM that should contain JSON
        
    Returns:
        Parsed JSON dict, or None if all parsing attempts fail
    """
    if not raw_text or not isinstance(raw_text, str):
        return None
    
    # Stage 1: Try standard JSON parsing
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    
    # Stage 2: Apply common repairs
    repaired_text = raw_text.strip()
    
    # Remove markdown code fences
    if repaired_text.startswith('```'):
        # Remove opening fence
        lines = repaired_text.split('\n')
        if lines:
            lines = lines[1:]  # Remove first line (```json or ```)
        # Remove closing fence
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        repaired_text = '\n'.join(lines).strip()
    
    # Strip trailing commas before closing braces/brackets
    repaired_text = re.sub(r',(\s*[}\]])', r'\1', repaired_text)
    
    # Convert single quotes to double quotes (when safe)
    # Only convert quotes that are clearly field names or values
    repaired_text = re.sub(r"'([^']*)'(\s*:\s*)", r'"\1"\2', repaired_text)  # Field names
    repaired_text = re.sub(r":\s*'([^']*)'", r': "\1"', repaired_text)  # String values
    
    # Try parsing after repairs
    try:
        parsed = json.loads(repaired_text)
        if isinstance(parsed, dict):
            logger.info("JSON parsing succeeded after repairs")
            return parsed
    except json.JSONDecodeError:
        pass
    
    # Stage 3: Try extracting first JSON object
    extracted = extract_first_json(repaired_text)
    if extracted:
        logger.info("JSON parsing succeeded via extraction")
        return extracted
    
    logger.warning("All JSON parsing attempts failed")
    return None


def log_json_parse_error(text: str, error: Exception, context: str = "", attempt: int = 1):
    """
    Log JSON parsing errors with redacted content.
    
    Args:
        text: Original text that failed to parse
        error: Exception that occurred
        context: Additional context for logging
        attempt: Attempt number (for logging first failure with full detail)
    """
    # On first failure, log more detail with redacted raw body
    if attempt == 1:
        # Log 200 characters of redacted content on first failure
        redacted_preview = redact_sensitive_content(text, max_length=200)
        logger.warning(f"JSON parsing failed {context} (attempt {attempt}): {error}")
        logger.warning(f"Redacted raw response preview: {redacted_preview}")
    else:
        # Subsequent failures get less detail
        redacted_text = redact_sensitive_content(text, max_length=100)
        logger.debug(f"JSON parsing failed {context} (attempt {attempt}): {error}")
        logger.debug(f"Redacted content: {redacted_text}")


# Health check utilities
def validate_guardrail_schema() -> Tuple[bool, str]:
    """
    Validate that guardrail schema is correct.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Test with sample data
        test_data = {
            "allowed": True,
            "reason": "Test reason"
        }
        
        # Validate required fields
        is_valid, error_msg = validate_json_schema(test_data, ["allowed", "reason"])
        if not is_valid:
            return False, f"Schema validation failed: {error_msg}"
        
        # Test normalization
        normalized = normalize_guardrail_response(test_data)
        if not isinstance(normalized.get("allowed"), bool):
            return False, "Normalized 'allowed' field is not boolean"
        
        if not isinstance(normalized.get("reason"), str):
            return False, "Normalized 'reason' field is not string"
        
        logger.info("Guardrail schema validation passed")
        return True, "Schema validation passed"
        
    except Exception as e:
        error_msg = f"Schema validation error: {e}"
        logger.error(error_msg)
        return False, error_msg


if __name__ == "__main__":
    # Test the utilities
    test_text = '{"classification": "allow", "explanation": "This is a test"}'
    result = tolerant_json_parse(test_text, "guardrail")
    print(f"Test result: {result}")
    
    # Test schema validation
    is_valid, msg = validate_guardrail_schema()
    print(f"Schema validation: {is_valid}, {msg}")
