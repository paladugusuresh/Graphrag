# graph_rag/dev_stubs.py
"""
Development stubs for testing and dev mode without external dependencies.
These mock implementations allow the system to run without real Neo4j, LLM, or embeddings.
"""

import os
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock


class MockNeo4jClient:
    """Mock Neo4j client for testing without database"""
    
    def __init__(self, driver=None):
        self._driver = driver or MagicMock()
        self._connected = True
    
    def verify_connectivity(self):
        """Mock connectivity check"""
        return True
    
    def close(self):
        """Mock close"""
        self._connected = False
    
    def execute_read_query(self, query: str, params: dict = None, timeout: float = None, query_name: str = None):
        """Mock read query - returns empty results"""
        return []
    
    def execute_write_query(self, query: str, params: dict = None, timeout: float = None, query_name: str = None):
        """Mock write query - returns empty results"""
        return []


class MockEmbeddingProvider:
    """Mock embedding provider for testing without LLM API"""
    
    def __init__(self, model_name: str = "mock-model"):
        self.model = model_name
        self.call_count = 0
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Mock embeddings - returns deterministic vectors based on text length.
        Each embedding is 8-dimensional for simplicity in tests.
        """
        self.call_count += 1
        if not texts:
            return []
        
        # Return deterministic mock embeddings based on text characteristics
        embeddings = []
        for text in texts:
            # Simple deterministic embedding based on text properties
            length = len(text)
            embedding = [
                float(length % 10) / 10.0,
                float(length % 20) / 20.0,
                float(length % 30) / 30.0,
                float(length % 40) / 40.0,
                float(length % 50) / 50.0,
                float(length % 60) / 60.0,
                float(length % 70) / 70.0,
                float(length % 80) / 80.0,
            ]
            embeddings.append(embedding)
        
        return embeddings


class MockLLMClient:
    """Mock LLM client for testing without API calls"""
    
    def __init__(self):
        self.call_count = 0
        self.last_prompt = None
    
    def call_raw(self, prompt: str, model: str = None, max_tokens: int = 512) -> str:
        """Mock raw LLM call - returns simple JSON response"""
        self.call_count += 1
        self.last_prompt = prompt
        
        # Return a simple valid JSON response
        return '{"intent": "general_rag_query", "anchor": null, "params": {}}'
    
    def call_structured(self, prompt: str, schema_model: Any, model: str = None, max_tokens: int = None):
        """Mock structured LLM call - returns instance of schema_model with defaults"""
        self.call_count += 1
        self.last_prompt = prompt
        
        # Try to create a valid instance of the schema model with minimal data
        try:
            # Common response patterns for different schema types
            if hasattr(schema_model, '__name__'):
                model_name = schema_model.__name__
                
                if 'Entities' in model_name or 'Entity' in model_name:
                    # For entity extraction
                    return schema_model(names=["TestEntity"])
                elif 'Planner' in model_name:
                    # For planner output
                    return schema_model(intent="general_rag_query", params={})
                elif 'Guardrail' in model_name:
                    # For guardrail responses
                    return schema_model(allowed=True, reason="Mock response")
                elif 'Graph' in model_name:
                    # For graph extraction
                    return schema_model(nodes=[], relationships=[])
            
            # Generic fallback - try to instantiate with empty/minimal data
            try:
                return schema_model()
            except:
                # If that fails, try with common field names
                try:
                    return schema_model(intent="general_rag_query")
                except:
                    # Last resort - return MagicMock that looks like the schema
                    mock = MagicMock(spec=schema_model)
                    mock.intent = "general_rag_query"
                    mock.params = {}
                    return mock
        
        except Exception as e:
            # If all else fails, raise an error that tests can catch
            raise ValueError(f"Could not create mock instance of {schema_model}: {e}")


class MockRedisClient:
    """Mock Redis client for testing without Redis"""
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._ttls: Dict[str, int] = {}
    
    def get(self, key: str) -> Optional[str]:
        """Mock get"""
        return self._data.get(key)
    
    def set(self, key: str, value: str, ex: int = None):
        """Mock set"""
        self._data[key] = value
        if ex:
            self._ttls[key] = ex
    
    def delete(self, key: str):
        """Mock delete"""
        if key in self._data:
            del self._data[key]
        if key in self._ttls:
            del self._ttls[key]
    
    def eval(self, script: str, numkeys: int, *args):
        """Mock eval - for rate limiting script"""
        # Always return 1 (allow) for mocks
        return 1
    
    def ping(self):
        """Mock ping"""
        return True


def is_dev_mode() -> bool:
    """Check if system is running in development/test mode"""
    dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
    skip_integration = os.getenv("SKIP_INTEGRATION", "").lower() in ("true", "1", "yes")
    return dev_mode or skip_integration


def should_use_mocks() -> bool:
    """
    Determine if mock implementations should be used.
    Returns True if:
    - DEV_MODE is set
    - SKIP_INTEGRATION is set  
    - Required secrets are missing (GEMINI_API_KEY, NEO4J_PASSWORD, etc.)
    """
    if is_dev_mode():
        return True
    
    # Check for missing secrets
    has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    has_neo4j = bool(os.getenv("NEO4J_PASSWORD") or os.getenv("NEO4J_URI"))
    
    # Use mocks if any critical secret is missing
    return not (has_gemini and has_neo4j)


def get_neo4j_client_or_mock():
    """
    Return a real Neo4jClient if in production mode with secrets,
    otherwise return MockNeo4jClient.
    """
    if should_use_mocks():
        return MockNeo4jClient()
    
    # Import real client only when needed
    from graph_rag.neo4j_client import Neo4jClient
    return Neo4jClient()


def get_embedding_provider_or_mock():
    """
    Return a real EmbeddingProvider if in production mode with secrets,
    otherwise return MockEmbeddingProvider.
    """
    if should_use_mocks():
        return MockEmbeddingProvider()
    
    # Import real provider only when needed
    from graph_rag.embeddings import EmbeddingProvider
    return EmbeddingProvider()


def get_redis_client_or_mock():
    """
    Return a real Redis client if in production mode,
    otherwise return MockRedisClient.
    """
    if should_use_mocks():
        return MockRedisClient()
    
    # Import redis only when needed
    import redis
    from graph_rag.config_manager import get_config_value
    redis_url = get_config_value("llm.redis_url", "redis://localhost:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


# Alias for backward compatibility
def get_redis_client(redis_url: str = None, decode_responses: bool = True):
    """
    Get Redis client with optional URL override.
    Returns mock client in dev mode, real client otherwise.
    """
    if should_use_mocks():
        return MockRedisClient()
    
    # Import redis only when needed
    import redis
    from graph_rag.config_manager import get_config_value
    
    if redis_url is None:
        redis_url = get_config_value("llm.redis_url", "redis://localhost:6379/0")
    
    return redis.from_url(redis_url, decode_responses=decode_responses)
