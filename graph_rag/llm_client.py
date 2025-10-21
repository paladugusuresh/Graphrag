# graph_rag/llm_client.py
import os
import time
import json
from typing import Optional
from pydantic import BaseModel, ValidationError
from graph_rag.observability import get_logger, tracer, llm_calls_total
from graph_rag.audit_store import audit_store
from graph_rag.config_manager import get_config_value
from graph_rag.dev_stubs import get_redis_client as get_redis_client_stub
from graph_rag.flags import LLM_JSON_MODE_ENABLED, LLM_RATE_LIMIT_PER_MIN, LLM_TOLERANT_JSON_PARSER
from graph_rag.json_utils import tolerant_json_parse, log_json_parse_error, redact_sensitive_content
from graph_rag.rate_limit import rate_limited_llm, RateLimitExceeded
from opentelemetry.trace import get_current_span

logger = get_logger(__name__)

# Gemini client imports - lazy loaded
_gemini_client = None

def _should_use_mock() -> bool:
    """Check if we should use mock LLM responses"""
    dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
    skip_integration = os.getenv("SKIP_INTEGRATION", "").lower() in ("true", "1", "yes")
    return dev_mode or skip_integration

def _get_gemini_api_key() -> Optional[str]:
    """Get Gemini API key from environment (GEMINI_API_KEY or GOOGLE_API_KEY as fallback)"""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not key and not _should_use_mock():
        logger.error("GEMINI_API_KEY (or GOOGLE_API_KEY) not present in env")
    elif not key and _should_use_mock():
        logger.info("GEMINI_API_KEY not present in env, running in DEV_MODE with mock LLM")
    
    return key

def _get_gemini_client():
    """Get or create Gemini client instance"""
    global _gemini_client
    
    if _gemini_client is not None:
        return _gemini_client
    
    # In DEV_MODE, don't create a real client
    if _should_use_mock():
        logger.info("Running with mock LLM (DEV_MODE or SKIP_INTEGRATION)")
        return None
    
    api_key = _get_gemini_api_key()
    if not api_key:
        logger.warning("No Gemini API key available, LLM calls will fail")
        return None
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _gemini_client = genai
        logger.info("Gemini client initialized")
        return _gemini_client
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        return None

# Internal variable to store the Redis client instance
_redis_client_instance = None

def _get_redis_url() -> str:
    """Get Redis URL from config or environment variable"""
    return get_config_value("llm.redis_url", os.getenv("REDIS_URL", "redis://localhost:6379/0"))

def _get_redis_client():
    """Get Redis client instance, creating it lazily if needed"""
    global _redis_client_instance
    if _redis_client_instance is None:
        # Use dev stub if in DEV_MODE or SKIP_INTEGRATION
        _redis_client_instance = get_redis_client_stub(_get_redis_url(), decode_responses=True)
    return _redis_client_instance

RATE_LIMIT_KEY = "graphrag:llm:tokens"

def _get_rate_limit() -> int:
    """Get rate limit per minute from config"""
    return get_config_value("llm.rate_limit_per_minute", 60)

# Lua script for atomic token consumption
# KEYS[1] - rate limit key
# ARGV[1] - tokens to consume
# ARGV[2] - rate limit per minute
# ARGV[3] - current timestamp (integer seconds)
RATE_LIMIT_LUA_SCRIPT = """
    local key = KEYS[1]
    local tokens_to_consume = tonumber(ARGV[1])
    local rate_limit_per_minute = tonumber(ARGV[2])
    local current_time = tonumber(ARGV[3])

    local window = math.floor(current_time / 60)
    local window_key = key .. ":" .. window

    local current_tokens = tonumber(redis.call('get', window_key) or rate_limit_per_minute)

    if current_tokens - tokens_to_consume >= 0 then
        redis.call('decrby', window_key, tokens_to_consume)
        -- Set expiry to the end of the current window + a buffer (e.g., 60 seconds)
        redis.call('expire', window_key, (window + 1) * 60 - current_time + 60)
        return 1
    else
        return 0
    end
"""

def consume_token(key=RATE_LIMIT_KEY, tokens=1) -> bool:
    """
    Consumes tokens from a Redis-backed token bucket using a Lua script for atomicity.
    Returns True if tokens were consumed, False otherwise.
    """
    now = int(time.time())
    redis_client = _get_redis_client()
    rate_limit = _get_rate_limit()
    result = redis_client.eval(RATE_LIMIT_LUA_SCRIPT, 1, key, tokens, rate_limit, now)
    return result == 1

class LLMStructuredError(Exception):
    pass

@rate_limited_llm(endpoint_name="call_llm_raw")
def call_llm_raw(prompt: str, model: str, max_tokens: int = 512, temperature: float = 0.0, json_mode: bool = False) -> str:
    """
    Call Gemini LLM with the given prompt.
    Must be wrapped by call_llm_structured() which validates outputs.
    
    Args:
        prompt: The prompt to send to the LLM
        model: The model to use
        max_tokens: Maximum tokens for response
        temperature: Temperature for generation (0.0 = deterministic)
        json_mode: Whether to force JSON-only output (when supported by provider)
    """
    llm_calls_total.inc()
    
    # In DEV_MODE, return mock response
    if _should_use_mock():
        logger.debug("DEV_MODE: Returning mock LLM response")
        return '{"intent":"general_rag_query","anchor":null}'
    
    client = _get_gemini_client()
    if not client:
        logger.warning("No Gemini client available, returning mock response")
        return '{"intent":"general_rag_query","anchor":null}'
    
    try:
        # Create a GenerativeModel instance
        gemini_model = client.GenerativeModel(model)
        
        # Configure generation with max_tokens and temperature
        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # Add JSON mode if requested (Gemini uses response_mime_type)
        if json_mode:
            generation_config["response_mime_type"] = "application/json"
        
        # Generate content
        response = gemini_model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        # Extract text from response
        if response and response.text:
            return response.text
        else:
            logger.warning("Gemini returned empty response")
            return '{"intent":"general_rag_query","anchor":null}'
            
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        # Return a safe default for graceful degradation
        return '{"intent":"general_rag_query","anchor":null}'

def call_llm_structured(prompt: str, schema_model: BaseModel, model: str = None, max_tokens: int = None, example_structure: str = None):
    """
    Calls LLM and validates JSON output against schema_model (a Pydantic model class).
    Returns validated object instance or raises LLMStructuredError.
    
    With LLM_JSON_MODE_ENABLED=true:
    - Forces JSON-only output via provider's JSON mode
    - Sets temperature=0 for deterministic results
    - Retries up to 2 times on validation failures
    
    Rate limiting is enforced at the call_llm_raw level via @rate_limited_llm decorator.
    
    Args:
        prompt: The base prompt to send to the LLM
        schema_model: Pydantic model class for validation
        model: LLM model to use (defaults to config)
        max_tokens: Maximum tokens for response (defaults to config)
        example_structure: Optional example structure to include in prompt
    """
    model = model or get_config_value('llm.model', 'gemini-2.0-flash-exp')
    max_tokens = max_tokens or get_config_value('llm.max_tokens', 512)
    
    # Check feature flags
    json_mode_enabled = LLM_JSON_MODE_ENABLED()
    tolerant_parser_enabled = LLM_TOLERANT_JSON_PARSER()
    temperature = 0.0  # Always 0 for deterministic structured output
    max_retries = 2  # Always retry up to 2 times for structured calls
    
    # Build structured prompt with explicit JSON requirements
    structured_prompt = _build_structured_prompt(prompt, schema_model, example_structure)
    
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            # Call LLM with JSON mode if enabled
            # Note: Rate limiting is enforced by @rate_limited_llm decorator on call_llm_raw
            response = call_llm_raw(
                structured_prompt, 
                model=model, 
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=json_mode_enabled
            )

            # Try to parse JSON with tolerance if enabled
            parsed = None
            json_parse_error = None
            
            try:
                # First try standard JSON parsing
                parsed = json.loads(response)
            except json.JSONDecodeError as e:
                json_parse_error = e
                
                # If tolerant parser is enabled, try tolerant parsing
                if tolerant_parser_enabled:
                    logger.debug("Standard JSON parsing failed, trying tolerant parser")
                    parsed = tolerant_json_parse(response, schema_type="general")
                    
                    if parsed is not None:
                        logger.info("Tolerant JSON parser succeeded")
                    else:
                        logger.warning("Tolerant JSON parser also failed")
                else:
                    logger.debug("Tolerant parser disabled, skipping tolerant parsing")
            
            # If parsing failed completely, handle retry or error
            if parsed is None:
                if attempt < max_retries:
                    logger.warning(f"LLM returned non-JSON (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                    if json_parse_error:
                        log_json_parse_error(response, json_parse_error, f"attempt {attempt + 1}")
                    last_error = json_parse_error or Exception("JSON parsing failed")
                    continue
                
                # Final attempt failed - log and raise error
                redacted_response = redact_sensitive_content(response)
                logger.error(f"LLM returned non-JSON after all retries: {redacted_response}")
                
                span = get_current_span()
                audit_store.record(entry={
                    "type": "llm_parse_failure", 
                    "prompt": structured_prompt[:200],  # Truncate prompt for audit
                    "response": redacted_response, 
                    "error": str(json_parse_error) if json_parse_error else "JSON parsing failed",
                    "schema_model": schema_model.__name__,
                    "attempts": attempt + 1,
                    "tolerant_parser_enabled": tolerant_parser_enabled,
                    "trace_id": str(span.context.trace_id) if span and span.is_recording() else None
                })
                raise LLMStructuredError("Invalid JSON from LLM") from (json_parse_error or Exception("JSON parsing failed"))

            # Validate against schema
            try:
                validated = schema_model.model_validate(parsed)  # Use model_validate for Pydantic v2+
                if attempt > 0:
                    logger.info(f"LLM structured call succeeded on attempt {attempt + 1}/{max_retries + 1}")
                return validated
            except ValidationError as e:
                if attempt < max_retries:
                    logger.warning(f"LLM output failed validation (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                    last_error = e
                    continue
                
                logger.warning(f"LLM output failed validation for schema {schema_model.__name__}: {e}")
                span = get_current_span()
                redacted_response = redact_sensitive_content(response)
                audit_store.record(entry={
                    "type": "llm_validation_failed", 
                    "prompt": structured_prompt[:200],  # Truncate prompt for audit
                    "response": redacted_response, 
                    "error": str(e), 
                    "schema_model": schema_model.__name__,
                    "attempts": attempt + 1,
                    "tolerant_parser_enabled": tolerant_parser_enabled,
                    "trace_id": str(span.context.trace_id) if span and span.is_recording() else None
                })
                raise LLMStructuredError("Structured output failed validation") from e
        
        except RateLimitExceeded as e:
            # Convert rate limit error to LLMStructuredError (don't retry rate limits)
            logger.error(f"Rate limit exceeded: {e}")
            raise LLMStructuredError(str(e)) from e
        except LLMStructuredError:
            # Re-raise LLMStructuredError immediately (don't retry)
            raise
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}), retrying... Error: {e}")
                last_error = e
                continue
            raise LLMStructuredError(f"LLM call failed after {attempt + 1} attempts") from e
    
    # Should not reach here, but if we do, raise the last error
    if last_error:
        raise LLMStructuredError("All retry attempts exhausted") from last_error
    raise LLMStructuredError("Unexpected error in call_llm_structured")

def _build_structured_prompt(base_prompt: str, schema_model: BaseModel, example_structure: str = None) -> str:
    """
    Build a structured prompt with explicit JSON requirements and schema guidance.
    
    Args:
        base_prompt: The original prompt
        schema_model: Pydantic model class for validation
        example_structure: Optional example structure to include
        
    Returns:
        Enhanced prompt with JSON requirements
    """
    prompt_parts = [
        base_prompt,
        "",
        "IMPORTANT: Return only valid JSON matching the required schema.",
        f"Schema model: {schema_model.__name__}",
        "",
        "Requirements:",
        "- Return ONLY valid JSON, no additional text or explanations",
        "- Ensure all required fields are present",
        "- Use correct data types (strings, numbers, booleans, arrays, objects)",
        "- Follow the exact field names and structure expected"
    ]
    
    # Add example structure if provided
    if example_structure:
        prompt_parts.extend([
            "",
            "Example structure:",
            example_structure
        ])
    
    # Add schema JSON example if available (future enhancement)
    # TODO: If schema_model has schema_json_example() method, include it in prompt
    # This would provide a concrete example of the expected JSON structure
    
    prompt_parts.extend([
        "",
        "Return your response as valid JSON only:"
    ])
    
    return "\n".join(prompt_parts)
