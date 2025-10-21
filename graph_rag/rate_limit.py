# graph_rag/rate_limit.py
"""
Centralized LLM rate limiting with token-bucket algorithm.

Enforces per-minute LLM call budget using Redis for distributed rate limiting.
Rate limiting is tracked per endpoint + model combination.
"""
import time
import functools
from typing import Optional, Callable
from graph_rag.observability import get_logger, Counter
from graph_rag.audit_store import audit_store
from graph_rag.config_manager import get_config_value
from graph_rag.dev_stubs import get_redis_client as get_redis_client_stub
from graph_rag.flags import LLM_RATE_LIMIT_PER_MIN
from opentelemetry.trace import get_current_span

logger = get_logger(__name__)

# Prometheus metric for rate limit hits
llm_rate_limit_hits = Counter(
    "llm_rate_limit_hits_total",
    "Total number of LLM rate limit hits",
    ["endpoint", "model"]
)

# Internal variable to store the Redis client instance
_redis_client_instance = None


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded (429-style error)"""
    def __init__(self, message: str = "LLM rate limit exceeded", endpoint: str = None, model: str = None):
        self.message = message
        self.endpoint = endpoint
        self.model = model
        super().__init__(self.message)


def _get_redis_url() -> str:
    """Get Redis URL from config or environment variable"""
    import os
    return get_config_value("llm.redis_url", os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def _get_redis_client():
    """Get Redis client instance, creating it lazily if needed"""
    global _redis_client_instance
    if _redis_client_instance is None:
        # Use dev stub if in DEV_MODE or SKIP_INTEGRATION
        _redis_client_instance = get_redis_client_stub(_get_redis_url(), decode_responses=True)
    return _redis_client_instance


# Lua script for atomic token consumption with per-endpoint+model tracking
# KEYS[1] - rate limit key (includes endpoint+model)
# ARGV[1] - tokens to consume (always 1 for LLM calls)
# ARGV[2] - rate limit per minute
# ARGV[3] - current timestamp (integer seconds)
RATE_LIMIT_LUA_SCRIPT = """
    local key = KEYS[1]
    local tokens_to_consume = tonumber(ARGV[1])
    local rate_limit_per_minute = tonumber(ARGV[2])
    local current_time = tonumber(ARGV[3])

    -- Calculate current minute window
    local window = math.floor(current_time / 60)
    local window_key = key .. ":" .. window

    -- Get current token count (initialize to rate_limit_per_minute if not set)
    local current_tokens = tonumber(redis.call('get', window_key) or rate_limit_per_minute)

    if current_tokens - tokens_to_consume >= 0 then
        -- Consume tokens
        redis.call('decrby', window_key, tokens_to_consume)
        -- Set expiry to the end of the current window + buffer (120 seconds)
        redis.call('expire', window_key, 120)
        return 1
    else
        -- Rate limit exceeded
        return 0
    end
"""


def _build_rate_limit_key(endpoint: str, model: str) -> str:
    """
    Build rate limit key for endpoint + model combination.
    
    Args:
        endpoint: The endpoint name (e.g., 'call_llm_raw', 'call_llm_structured')
        model: The model name (e.g., 'gemini-2.0-flash-exp')
        
    Returns:
        Redis key for rate limiting
    """
    # Sanitize endpoint and model names for Redis key
    safe_endpoint = endpoint.replace(":", "_").replace(" ", "_")
    safe_model = model.replace(":", "_").replace(" ", "_")
    return f"graphrag:llm:rate_limit:{safe_endpoint}:{safe_model}"


def consume_token_with_limit(endpoint: str, model: str, rate_limit_per_min: int) -> bool:
    """
    Attempt to consume a token from the rate limit bucket.
    
    Uses Redis-backed token bucket with Lua script for atomicity.
    Tracks rate limits per endpoint + model combination.
    
    Args:
        endpoint: The endpoint name (e.g., 'call_llm_raw')
        model: The model name (e.g., 'gemini-2.0-flash-exp')
        rate_limit_per_min: Rate limit per minute (0 = disabled)
        
    Returns:
        True if token was consumed (request allowed), False otherwise
    """
    if rate_limit_per_min <= 0:
        # Rate limiting disabled
        return True
    
    now = int(time.time())
    redis_client = _get_redis_client()
    key = _build_rate_limit_key(endpoint, model)
    
    try:
        result = redis_client.eval(RATE_LIMIT_LUA_SCRIPT, 1, key, 1, rate_limit_per_min, now)
        return result == 1
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        # Fail open on Redis errors (allow the request)
        return True


def rate_limited_llm(endpoint_name: Optional[str] = None):
    """
    Decorator that enforces LLM rate limiting based on LLM_RATE_LIMIT_PER_MIN flag.
    
    Tracks rate limits per endpoint + model combination. When limit is exceeded,
    raises RateLimitExceeded (429-style error) and logs to audit store.
    
    Usage:
        @rate_limited_llm(endpoint_name="call_llm_raw")
        def call_llm_raw(prompt: str, model: str, ...):
            ...
    
    Args:
        endpoint_name: Name of the endpoint (defaults to function name)
        
    Returns:
        Decorated function that enforces rate limiting
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get rate limit from flag
            rate_limit = LLM_RATE_LIMIT_PER_MIN()
            
            # If rate limiting is disabled (0), skip check
            if rate_limit <= 0:
                return func(*args, **kwargs)
            
            # Extract endpoint name and model from function call
            endpoint = endpoint_name or func.__name__
            
            # Try to extract model from args/kwargs
            # Assume 'model' is either a kwarg or the second positional arg after 'prompt'
            model = kwargs.get('model')
            if model is None and len(args) >= 2:
                model = args[1]
            if model is None:
                # Default to config value if not provided
                model = get_config_value('llm.model', 'gemini-2.0-flash-exp')
            
            # Attempt to consume token
            allowed = consume_token_with_limit(endpoint, model, rate_limit)
            
            if not allowed:
                # Rate limit exceeded
                logger.warning(f"Rate limit exceeded for {endpoint} with model {model}")
                
                # Increment metric
                llm_rate_limit_hits.labels(endpoint=endpoint, model=model).inc()
                
                # Audit log
                span = get_current_span()
                audit_store.record({
                    "event": "llm_rate_limit_exceeded",
                    "endpoint": endpoint,
                    "model": model,
                    "rate_limit": rate_limit,
                    "trace_id": str(span.context.trace_id) if span and span.is_recording() else None
                })
                
                # Raise 429-style error
                raise RateLimitExceeded(
                    message=f"LLM rate limit exceeded: {rate_limit} calls/minute for {endpoint}:{model}",
                    endpoint=endpoint,
                    model=model
                )
            
            # Token consumed, proceed with function call
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def get_current_rate_limit_usage(endpoint: str, model: str) -> dict:
    """
    Get current rate limit usage for endpoint + model.
    
    Args:
        endpoint: The endpoint name
        model: The model name
        
    Returns:
        Dictionary with usage information:
        - remaining: Tokens remaining in current window
        - limit: Total limit per minute
        - reset_at: Timestamp when the window resets
    """
    rate_limit = LLM_RATE_LIMIT_PER_MIN()
    
    if rate_limit <= 0:
        return {
            "remaining": float('inf'),
            "limit": 0,
            "reset_at": None,
            "disabled": True
        }
    
    now = int(time.time())
    window = now // 60
    window_key = _build_rate_limit_key(endpoint, model) + f":{window}"
    
    try:
        redis_client = _get_redis_client()
        current_tokens = redis_client.get(window_key)
        
        if current_tokens is None:
            remaining = rate_limit
        else:
            remaining = int(current_tokens)
        
        reset_at = (window + 1) * 60  # Next minute boundary
        
        return {
            "remaining": remaining,
            "limit": rate_limit,
            "reset_at": reset_at,
            "disabled": False
        }
    except Exception as e:
        logger.error(f"Failed to get rate limit usage: {e}")
        return {
            "remaining": rate_limit,
            "limit": rate_limit,
            "reset_at": None,
            "error": str(e)
        }

