# graph_rag/embeddings.py
import os
from typing import Optional
from dotenv import load_dotenv
from graph_rag.observability import get_logger, llm_calls_total
from graph_rag.config_manager import get_config_value

logger = get_logger(__name__)

# Load .env file once at import time (safe operation)
load_dotenv()

# Gemini client - lazy loaded
_gemini_client = None

def _should_use_mock() -> bool:
    """Check if we should use mock embeddings"""
    dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
    skip_integration = os.getenv("SKIP_INTEGRATION", "").lower() in ("true", "1", "yes")
    return dev_mode or skip_integration

def _get_gemini_api_key() -> Optional[str]:
    """Get Gemini API key from environment (GEMINI_API_KEY or GOOGLE_API_KEY as fallback)"""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not key and not _should_use_mock():
        logger.error("GEMINI_API_KEY (or GOOGLE_API_KEY) not present in env")
    elif not key and _should_use_mock():
        logger.info("GEMINI_API_KEY not present in env, running in DEV_MODE with mock embeddings")
    
    return key

def _get_gemini_client():
    """Get or create Gemini client instance"""
    global _gemini_client
    
    if _gemini_client is not None:
        return _gemini_client
    
    # In DEV_MODE, don't create a real client
    if _should_use_mock():
        logger.info("Running with mock embeddings (DEV_MODE or SKIP_INTEGRATION)")
        return None
    
    api_key = _get_gemini_api_key()
    if not api_key:
        logger.warning("No Gemini API key available, embeddings will use mocks")
        return None
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _gemini_client = genai
        logger.info("Gemini embeddings client initialized")
        return _gemini_client
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        return None

_embedding_provider_instance = None

class EmbeddingProvider:
    def __init__(self, model_name: str = None):
        """Initialize embedding provider with lazy client creation"""
        self.model = model_name or get_config_value('llm.embedding_model', 'models/text-embedding-004')
        self.client = None
        self._use_mock = _should_use_mock()
        
        # Only initialize real client if not in dev/test mode
        if not self._use_mock:
            self.client = _get_gemini_client()
            if self.client:
                logger.info("Gemini embeddings client initialized")
            else:
                logger.info("Running with mock embeddings (no API key or client failed)")
                self._use_mock = True
        else:
            logger.info("Running with mock embeddings (DEV_MODE or SKIP_INTEGRATION)")

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings for a list of texts with standardized output normalization.
        
        Args:
            texts: List of input strings to embed
            
        Returns:
            List[List[float]]: One embedding vector per input string, normalized to consistent shape and type
        """
        if not texts:
            return []
        
        # Use mock embeddings if configured
        if self._use_mock or not self.client:
            # Simple deterministic mock embeddings - 8 dimensions
            mock_embeddings = [[float(len(t))] * 8 for t in texts]
            logger.debug(f"Mock embeddings: {len(texts)} inputs → {len(mock_embeddings)} vectors, dimension=8")
            return mock_embeddings
        
        try:
            llm_calls_total.inc()
            # Use Gemini embed_content API
            result = self.client.embed_content(
                model=self.model,
                content=texts,
                task_type="retrieval_document"
            )
            
            # Extract embeddings from result using defensive normalization
            raw_embeddings = self._extract_embeddings_from_response(result, texts)
            
            # Normalize and validate the embeddings
            normalized_embeddings = self._normalize_embeddings(raw_embeddings, texts)
            
            return normalized_embeddings
                
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            # Return mock embeddings on error as graceful fallback
            fallback_embeddings = [[float(len(t))] * 8 for t in texts]
            logger.warning(f"Using fallback embeddings: {len(texts)} inputs → {len(fallback_embeddings)} vectors")
            return fallback_embeddings
    
    def _extract_embeddings_from_response(self, result, texts: list[str]) -> list:
        """
        Extract embeddings from various provider response formats.
        
        Handles known return shapes:
        - {"embedding": [[...]]} - batch format
        - {"embedding": [...]} - single vector format
        - {"data": [{"embedding": [...]}, ...]} - OpenAI-style format
        - {"embeddings": [obj, ...]} - Gemini format with .values attribute
        - {"embedding": [[[...]]]} - over-nested format
        """
        # Handle Gemini API response objects
        if hasattr(result, 'embedding'):
            # Single text case - wrap in list
            embedding = result.embedding
            if isinstance(embedding, (list, tuple)):
                return [embedding]
            else:
                logger.warning(f"Unexpected embedding type: {type(embedding)}")
                return []
        
        elif hasattr(result, 'embeddings'):
            # Multiple texts case - extract values from each embedding object
            embeddings = []
            for emb in result.embeddings:
                if hasattr(emb, 'values'):
                    embeddings.append(emb.values)
                elif isinstance(emb, (list, tuple)):
                    embeddings.append(emb)
                else:
                    logger.warning(f"Unexpected embedding object type: {type(emb)}")
            return embeddings
        
        # Handle dict-style responses
        elif isinstance(result, dict):
            # OpenAI-style format: {"data": [{"embedding": [...]}, ...]}
            if "data" in result:
                embeddings = []
                for item in result["data"]:
                    if isinstance(item, dict) and "embedding" in item:
                        embeddings.append(item["embedding"])
                return embeddings
            
            # Direct embedding key: {"embedding": ...}
            elif "embedding" in result:
                embedding = result["embedding"]
                
                # Check if it's a single vector (list of numbers)
                if isinstance(embedding, (list, tuple)) and len(embedding) > 0:
                    # Check if first element is a number or a list
                    if isinstance(embedding[0], (int, float)):
                        # Single vector - wrap it
                        return [embedding]
                    elif isinstance(embedding[0], (list, tuple)):
                        # Check for over-nesting: [[[...]]]
                        if len(embedding) == 1 and isinstance(embedding[0], (list, tuple)) and len(embedding[0]) > 0:
                            if isinstance(embedding[0][0], (list, tuple)):
                                # Over-nested: [[[...]]] - unwrap one level
                                logger.debug("Detected over-nested embedding format, unwrapping one level")
                                return embedding[0]
                        # Check if it's a batch of vectors (first element is a list of numbers)
                        if isinstance(embedding[0][0], (int, float)):
                            # Batch of vectors - return as-is
                            return embedding
                return []
            
            # Check for "embeddings" key in dict
            elif "embeddings" in result:
                return result["embeddings"]
        
        # Unknown format
        logger.warning(f"Unexpected embedding result format: {type(result)}")
        return []
    
    def _normalize_embeddings(self, raw_embeddings: list, texts: list[str]) -> list[list[float]]:
        """
        Normalize embeddings to ensure consistent shape, type, and batch size.
        
        Args:
            raw_embeddings: Raw embedding vectors from provider
            texts: Original input texts
            
        Returns:
            Normalized List[List[float]] with guaranteed 1:1 mapping to inputs
        """
        if not raw_embeddings:
            logger.warning(f"Empty or malformed embeddings response for {len(texts)} inputs")
            return []
        
        # Normalize each vector to List[float]
        normalized = []
        for i, vector in enumerate(raw_embeddings):
            if vector is None or not isinstance(vector, (list, tuple)):
                logger.warning(f"Skipping invalid embedding at index {i}: {type(vector)}")
                continue
            
            # Convert all elements to float, skipping non-numeric values
            normalized_vector = []
            for x in vector:
                if isinstance(x, (int, float)):
                    normalized_vector.append(float(x))
                else:
                    logger.debug(f"Skipping non-numeric value in embedding: {type(x)}")
            
            if normalized_vector:
                normalized.append(normalized_vector)
        
        # Validate shape consistency
        if len(normalized) != len(texts):
            logger.warning(
                f"Embedding count mismatch: {len(texts)} inputs → {len(normalized)} vectors. "
                f"Expected 1:1 mapping."
            )
            
            # Truncate to shortest length to maintain alignment
            min_length = min(len(normalized), len(texts))
            if min_length < len(normalized):
                logger.warning(f"Truncating embeddings from {len(normalized)} to {min_length}")
                normalized = normalized[:min_length]
        
        # Validate dimension consistency (all vectors should have same length)
        if normalized:
            dimensions = [len(v) for v in normalized]
            unique_dims = set(dimensions)
            
            if len(unique_dims) > 1:
                logger.warning(f"Inconsistent embedding dimensions detected: {unique_dims}")
            
            # Log successful normalization
            dimension = dimensions[0] if dimensions else 0
            logger.debug(
                f"Embedding batch: {len(texts)} inputs → {len(normalized)} vectors, dimension={dimension}"
            )
        
        return normalized

def get_embedding_provider():
    """Get or create singleton embedding provider"""
    global _embedding_provider_instance
    if _embedding_provider_instance is None:
        _embedding_provider_instance = EmbeddingProvider()
    return _embedding_provider_instance
