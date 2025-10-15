# graph_rag/dev_stubs.py
"""
Development stubs and mock implementations for testing and development.
Used when real services (Neo4j, LLM, Redis) are unavailable or when DEV_MODE=true.
"""

import os
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock


class MockNeo4jClient:
    """
    Mock Neo4j client for testing and development.
    Returns empty results and doesn't connect to any database.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize mock client (ignores all connection parameters)"""
        self._connected = True
    
    def verify_connectivity(self):
        """Mock connectivity check - always succeeds"""
        pass
    
    def close(self):
        """Mock close operation"""
        self._connected = False
    
    def execute_read_query(self, query: str, params: Optional[Dict] = None, 
                          timeout: Optional[float] = None, 
                          query_name: Optional[str] = None) -> List[Dict]:
        """
        Mock read query - returns empty list.
        In tests, you should mock this method to return appropriate test data.
        """
        return []
    
    def execute_write_query(self, query: str, params: Optional[Dict] = None,
                           timeout: Optional[float] = None,
                           query_name: Optional[str] = None) -> List[Dict]:
        """
        Mock write query - returns empty list.
        Raises error if not in DEV_MODE to prevent accidental writes.
        """
        dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
        if not dev_mode:
            raise RuntimeError("MockNeo4jClient.execute_write_query called outside DEV_MODE")
        return []


class MockEmbeddingProvider:
    """
    Mock embedding provider for testing and development.
    Returns deterministic fake embeddings based on input text length.
    """
    
    def __init__(self, model_name: str = "mock-embedding-model", *args, **kwargs):
        """Initialize mock embedding provider"""
        self.model = model_name
        self.embedding_dim = 8  # Small dimension for testing
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate mock embeddings deterministically.
        Embedding values are based on text length to be reproducible.
        """
        embeddings = []
        for text in texts:
            # Generate deterministic embedding based on text characteristics
            base = float(len(text) % 100) / 100.0
            embedding = [base + (i * 0.01) for i in range(self.embedding_dim)]
            embeddings.append(embedding)
        return embeddings


class MockLLMClient:
    """
    Mock LLM client for testing and development.
    Returns simple predefined responses.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize mock LLM client"""
        self.call_count = 0
    
    def call_llm_raw(self, prompt: str, model: str, max_tokens: int = 512) -> str:
        """
        Mock raw LLM call - returns a simple JSON response.
        Override in tests for specific scenarios.
        """
        self.call_count += 1
        return '{"intent":"general_rag_query","anchor":null}'
    
    def call_llm_structured(self, prompt: str, schema_model: Any, 
                          model: Optional[str] = None, 
                          max_tokens: Optional[int] = None) -> Any:
        """
        Mock structured LLM call.
        Returns a mock instance of the schema_model.
        In tests, you should mock this to return appropriate test data.
        """
        self.call_count += 1
        # Return a mock instance - in real tests, mock this method
        return MagicMock(spec=schema_model)


class MockRedisClient:
    """
    Mock Redis client for testing and development.
    Simulates rate limiting without actual Redis connection.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize mock Redis client"""
        self._data = {}
        self._tokens = {}
    
    def get(self, key: str) -> Optional[str]:
        """Mock get operation"""
        return self._data.get(key)
    
    def set(self, key: str, value: str, *args, **kwargs):
        """Mock set operation"""
        self._data[key] = value
    
    def eval(self, script: str, num_keys: int, *args) -> int:
        """
        Mock Lua script execution for rate limiting.
        Always returns 1 (success) to allow all operations in dev mode.
        """
        return 1
    
    def ping(self) -> bool:
        """Mock ping - always succeeds"""
        return True
    
    def close(self):
        """Mock close operation"""
        pass


def should_use_mocks() -> bool:
    """
    Determine if mock implementations should be used.
    Returns True if:
    - DEV_MODE environment variable is set
    - SKIP_INTEGRATION environment variable is set  
    - Required secrets are missing
    """
    dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
    skip_integration = os.getenv("SKIP_INTEGRATION", "").lower() in ("true", "1", "yes")
    
    # Check if critical secrets are missing
    missing_neo4j = not all([
        os.getenv("NEO4J_URI"),
        os.getenv("NEO4J_USERNAME"),
        os.getenv("NEO4J_PASSWORD")
    ])
    missing_openai = not os.getenv("OPENAI_API_KEY")
    
    return dev_mode or skip_integration or missing_neo4j or missing_openai


def get_neo4j_client(*args, **kwargs):
    """
    Factory function that returns either a real or mock Neo4j client.
    Uses mocks if DEV_MODE is set or secrets are missing.
    """
    if should_use_mocks():
        return MockNeo4jClient(*args, **kwargs)
    else:
        # Import real client only when needed
        from graph_rag.neo4j_client import Neo4jClient
        return Neo4jClient(*args, **kwargs)


def get_embedding_provider(*args, **kwargs):
    """
    Factory function that returns either a real or mock embedding provider.
    Uses mocks if DEV_MODE is set or OPENAI_API_KEY is missing.
    """
    if should_use_mocks():
        return MockEmbeddingProvider(*args, **kwargs)
    else:
        # Import real provider only when needed
        from graph_rag.embeddings import EmbeddingProvider
        return EmbeddingProvider(*args, **kwargs)


def get_redis_client(*args, **kwargs):
    """
    Factory function that returns either a real or mock Redis client.
    Uses mocks if DEV_MODE is set.
    """
    if should_use_mocks():
        return MockRedisClient(*args, **kwargs)
    else:
        # Import real client only when needed
        import redis
        return redis.from_url(*args, **kwargs)

