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

def call_llm_raw(prompt: str, model: str, max_tokens: int = 512) -> str:
    """
    Call Gemini LLM with the given prompt.
    Must be wrapped by call_llm_structured() which validates outputs.
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
        
        # Configure generation with max_tokens
        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": 0.0,  # Deterministic for structured output
        }
        
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

def call_llm_structured(prompt: str, schema_model: BaseModel, model: str = None, max_tokens: int = None):
    """
    Calls LLM and validates JSON output against schema_model (a Pydantic model class).
    Returns validated object instance or raises LLMStructuredError.
    """
    if not consume_token():
        raise LLMStructuredError("LLM rate limit exceeded")

    model = model or get_config_value('llm.model', 'gemini-2.0-flash-exp')
    max_tokens = max_tokens or get_config_value('llm.max_tokens', 512)
    response = call_llm_raw(prompt, model=model, max_tokens=max_tokens)

    # Try to parse JSON safely
    try:
        parsed = json.loads(response)
    except Exception:
        # attempt to extract JSON substring
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            parsed = json.loads(response[start:end])
        except Exception as e:
            logger.error(f"LLM returned non-JSON and extraction failed: {response}")
            span = get_current_span()
            audit_store.record(entry={"type":"llm_parse_failure", "prompt": prompt, "response":response, "error":str(e), "trace_id": str(span.context.trace_id) if span and span.is_recording() else None})
            raise LLMStructuredError("Invalid JSON from LLM") from e

    try:
        validated = schema_model.model_validate(parsed) # Use model_validate for Pydantic v2+
        return validated
    except ValidationError as e:
        logger.warning(f"LLM output failed validation: {e}")
        span = get_current_span()
        audit_store.record(entry={"type":"llm_validation_failed", "prompt": prompt, "response":response, "error":str(e), "trace_id": str(span.context.trace_id) if span and span.is_recording() else None})
        raise LLMStructuredError("Structured output failed validation") from e
