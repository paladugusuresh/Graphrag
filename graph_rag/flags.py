# graph_rag/flags.py
"""
Feature flags for controlling Graph RAG behavior.

All flags default to "current behavior" to ensure no breaking changes.
Flags are read from environment variables and can be overridden via config.
"""

import os
from typing import Union
from .config_manager import get_config_value


def _get_bool_flag(env_var: str, config_path: str, default: bool) -> bool:
    """Get boolean flag from environment or config with fallback to default."""
    # Check environment variable first
    env_value = os.getenv(env_var)
    if env_value is not None:
        return env_value.lower() in ("true", "1", "yes", "on")
    
    # Check config file
    config_value = get_config_value(config_path)
    if config_value is not None:
        if isinstance(config_value, bool):
            return config_value
        if isinstance(config_value, str):
            return config_value.lower() in ("true", "1", "yes", "on")
    
    return default


def _get_int_flag(env_var: str, config_path: str, default: int) -> int:
    """Get integer flag from environment or config with fallback to default."""
    # Check environment variable first
    env_value = os.getenv(env_var)
    if env_value is not None:
        try:
            return int(env_value)
        except ValueError:
            pass
    
    # Check config file
    config_value = get_config_value(config_path)
    if config_value is not None:
        if isinstance(config_value, int):
            return config_value
        if isinstance(config_value, str):
            try:
                return int(config_value)
            except ValueError:
                pass
    
    return default


def GUARDRAILS_FAIL_CLOSED_DEV() -> bool:
    """
    Whether guardrails should fail closed in development mode.
    
    Default: False (current behavior - permissive in dev)
    Environment: GUARDRAILS_FAIL_CLOSED_DEV
    Config: flags.guardrails_fail_closed_dev
    """
    return _get_bool_flag("GUARDRAILS_FAIL_CLOSED_DEV", "flags.guardrails_fail_closed_dev", False)


def LLM_JSON_MODE_ENABLED() -> bool:
    """
    Whether to enable JSON mode for LLM responses.
    
    Default: True (current behavior - JSON mode enabled)
    Environment: LLM_JSON_MODE_ENABLED
    Config: flags.llm_json_mode_enabled
    """
    return _get_bool_flag("LLM_JSON_MODE_ENABLED", "flags.llm_json_mode_enabled", True)


def LLM_RATE_LIMIT_PER_MIN() -> int:
    """
    Rate limit for LLM requests per minute (0 = disabled).
    
    Default: 0 (current behavior - no rate limiting)
    Environment: LLM_RATE_LIMIT_PER_MIN
    Config: flags.llm_rate_limit_per_min
    """
    return _get_int_flag("LLM_RATE_LIMIT_PER_MIN", "flags.llm_rate_limit_per_min", 0)


def GUARDRAILS_MAX_HOPS() -> int:
    """
    Maximum number of hops allowed in guardrail traversal checks.
    
    Default: 2 (current behavior - matches config guardrails.max_traversal_depth)
    Environment: GUARDRAILS_MAX_HOPS
    Config: flags.guardrails_max_hops
    """
    return _get_int_flag("GUARDRAILS_MAX_HOPS", "flags.guardrails_max_hops", 2)


def SCHEMA_BOOTSTRAP_ENABLED() -> bool:
    """
    Whether to enable schema bootstrap/ingestion at startup.
    
    Default: True (current behavior - schema loaded at startup)
    Environment: SCHEMA_BOOTSTRAP_ENABLED
    Config: flags.schema_bootstrap_enabled
    """
    return _get_bool_flag("SCHEMA_BOOTSTRAP_ENABLED", "flags.schema_bootstrap_enabled", True)


def RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED() -> bool:
    """
    Whether to enable chunk-level embeddings for retrieval.
    
    Default: False (current behavior - no chunk embeddings)
    Environment: RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED
    Config: flags.retrieval_chunk_embeddings_enabled
    """
    return _get_bool_flag("RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED", "flags.retrieval_chunk_embeddings_enabled", False)


def RETRIEVAL_TOPK() -> int:
    """
    Number of top chunks to retrieve via vector similarity.
    
    Default: 5 (current behavior)
    Environment: RETRIEVAL_TOPK
    Config: flags.retrieval_topk
    """
    return _get_int_flag("RETRIEVAL_TOPK", "flags.retrieval_topk", 5)


def MAPPER_ENABLED() -> bool:
    """
    Whether to enable SynonymMapper for semantic term mapping.
    
    Default: True (current behavior - mapper enabled)
    Environment: MAPPER_ENABLED
    Config: flags.mapper_enabled
    """
    return _get_bool_flag("MAPPER_ENABLED", "flags.mapper_enabled", True)


def FORMATTERS_ENABLED() -> bool:
    """
    Whether to enable table and graph formatters with citation verification.
    
    Default: False (current behavior - no formatters)
    Environment: FORMATTERS_ENABLED
    Config: flags.formatters_enabled
    """
    return _get_bool_flag("FORMATTERS_ENABLED", "flags.formatters_enabled", False)


def LLM_TOLERANT_JSON_PARSER() -> bool:
    """
    Whether to enable tolerant JSON parsing for LLM responses in development.
    
    This parser extracts JSON from text and normalizes common variations.
    Only active when enabled - strict parsing in production.
    
    Default: False (current behavior - strict JSON parsing only)
    Environment: LLM_TOLERANT_JSON_PARSER
    Config: flags.llm_tolerant_json_parser
    """
    return _get_bool_flag("LLM_TOLERANT_JSON_PARSER", "flags.llm_tolerant_json_parser", False)


def get_all_flags() -> dict[str, Union[bool, int]]:
    """
    Get all feature flags as a dictionary for logging/debugging.
    
    Returns:
        Dictionary mapping flag names to their current values
    """
    return {
        "GUARDRAILS_FAIL_CLOSED_DEV": GUARDRAILS_FAIL_CLOSED_DEV(),
        "LLM_JSON_MODE_ENABLED": LLM_JSON_MODE_ENABLED(),
        "LLM_RATE_LIMIT_PER_MIN": LLM_RATE_LIMIT_PER_MIN(),
        "GUARDRAILS_MAX_HOPS": GUARDRAILS_MAX_HOPS(),
        "SCHEMA_BOOTSTRAP_ENABLED": SCHEMA_BOOTSTRAP_ENABLED(),
        "RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED": RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED(),
        "RETRIEVAL_TOPK": RETRIEVAL_TOPK(),
        "MAPPER_ENABLED": MAPPER_ENABLED(),
        "FORMATTERS_ENABLED": FORMATTERS_ENABLED(),
        "LLM_TOLERANT_JSON_PARSER": LLM_TOLERANT_JSON_PARSER(),
    }
