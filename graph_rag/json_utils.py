# graph_rag/json_utils.py
"""
Tolerant JSON parsing utilities for LLM responses.

This module provides robust JSON extraction and normalization for LLM responses
that may contain malformed JSON or additional text around the JSON object.

Only active when LLM_TOLERANT_JSON_PARSER flag is enabled.
"""

import json
import re
from typing import Any, Optional
from .observability import get_logger

logger = get_logger(__name__)


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract the first JSON object or array from text.
    
    This function attempts to find and extract a complete JSON object {} or array []
    from text that may contain additional content before or after the JSON.
    
    Args:
        text: Text that may contain JSON
        
    Returns:
        Extracted JSON string, or None if no valid JSON found
        
    Examples:
        >>> extract_json_from_text('Here is the data: {"key": "value"}')
        '{"key": "value"}'
        
        >>> extract_json_from_text('```json\\n{"key": "value"}\\n```')
        '{"key": "value"}'
    """
    if not text or not isinstance(text, str):
        return None
    
    # Remove markdown code fences if present
    text = re.sub(r'```(?:json)?\s*\n', '', text)
    text = re.sub(r'\n```\s*$', '', text)
    
    # Try to find JSON object
    # Look for balanced braces
    brace_start = text.find('{')
    bracket_start = text.find('[')
    
    # Determine which comes first
    if brace_start == -1 and bracket_start == -1:
        return None
    
    if brace_start == -1:
        start_char = '['
        end_char = ']'
        start_pos = bracket_start
    elif bracket_start == -1:
        start_char = '{'
        end_char = '}'
        start_pos = brace_start
    else:
        if brace_start < bracket_start:
            start_char = '{'
            end_char = '}'
            start_pos = brace_start
        else:
            start_char = '['
            end_char = ']'
            start_pos = bracket_start
    
    # Find matching closing brace/bracket
    depth = 0
    in_string = False
    escape_next = False
    
    for i in range(start_pos, len(text)):
        char = text[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"':
            in_string = not in_string
            continue
        
        if in_string:
            continue
        
        if char == start_char:
            depth += 1
        elif char == end_char:
            depth -= 1
            if depth == 0:
                # Found complete JSON
                return text[start_pos:i+1]
    
    return None


def normalize_guardrail_response(data: dict) -> dict:
    """
    Normalize common variations in guardrail classification responses.
    
    This function handles various ways LLMs might express the same concept:
    - "classification": "allow" → "allowed": true
    - "action": "block" → "allowed": false
    - Missing "reason" field → adds default
    
    Args:
        data: Raw dictionary from LLM
        
    Returns:
        Normalized dictionary with standard keys (allowed, reason)
        
    Examples:
        >>> normalize_guardrail_response({"classification": "allow"})
        {"allowed": true, "reason": "OK"}
        
        >>> normalize_guardrail_response({"action": "block", "reason": "malicious"})
        {"allowed": false, "reason": "malicious"}
    """
    normalized = {}
    
    # Determine if request is allowed
    allowed = None
    
    # Check various keys that might indicate permission
    if "allowed" in data:
        allowed = bool(data["allowed"])
    elif "classification" in data:
        classification = str(data["classification"]).lower()
        allowed = classification in ("allow", "allowed", "ok", "safe", "pass")
    elif "action" in data:
        action = str(data["action"]).lower()
        allowed = action in ("allow", "pass", "ok")
    elif "is_allowed" in data:
        allowed = bool(data["is_allowed"])
    elif "status" in data:
        status = str(data["status"]).lower()
        allowed = status in ("allowed", "ok", "safe", "pass")
    
    # Default to not allowed if we can't determine
    if allowed is None:
        logger.warning(f"Could not determine allowed status from guardrail response: {data}")
        allowed = False
    
    normalized["allowed"] = allowed
    
    # Extract reason
    reason = data.get("reason") or data.get("message") or data.get("explanation")
    
    if not reason:
        reason = "OK" if allowed else "Classification failed"
    
    normalized["reason"] = str(reason)
    
    return normalized


def parse_json_tolerant(text: str, normalize_guardrail: bool = False) -> Optional[dict]:
    """
    Parse JSON with tolerance for malformed input.
    
    This function:
    1. Tries standard JSON parsing first
    2. Falls back to extracting JSON from text
    3. Optionally normalizes guardrail responses
    
    Args:
        text: Text that should contain JSON
        normalize_guardrail: Whether to normalize guardrail classification responses
        
    Returns:
        Parsed dictionary, or None if parsing fails
        
    Raises:
        ValueError: If JSON cannot be parsed even with tolerant methods
    """
    if not text or not isinstance(text, str):
        raise ValueError("Input must be non-empty string")
    
    # Try standard JSON parsing first
    try:
        data = json.loads(text)
        if normalize_guardrail and isinstance(data, dict):
            data = normalize_guardrail_response(data)
        return data
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from text
    extracted = extract_json_from_text(text)
    if not extracted:
        logger.warning(f"Could not extract JSON from text: {text[:200]}")
        raise ValueError("No valid JSON found in text")
    
    # Parse extracted JSON
    try:
        data = json.loads(extracted)
        if normalize_guardrail and isinstance(data, dict):
            data = normalize_guardrail_response(data)
        return data
    except json.JSONDecodeError as e:
        logger.warning(f"Extracted JSON is still invalid: {extracted[:200]}")
        raise ValueError(f"Invalid JSON after extraction: {str(e)}")


def redact_for_logging(text: str, max_length: int = 512) -> str:
    """
    Redact sensitive information from text for logging.
    
    Args:
        text: Text to redact
        max_length: Maximum length to return
        
    Returns:
        Redacted text truncated to max_length
    """
    if not text:
        return ""
    
    # Truncate
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    # Remove potential sensitive patterns
    # Email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    
    # Phone numbers (simple patterns)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
    
    # Credit card-like patterns (4 groups of 4 digits)
    text = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD]', text)
    
    return text


if __name__ == "__main__":
    # Simple tests
    import doctest
    doctest.testmod()

