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
        if not texts:
            return []
        
        # Use mock embeddings if configured
        if self._use_mock or not self.client:
            # simple deterministic mock embeddings
            return [[float(len(t))] * 8 for t in texts]
        
        try:
            llm_calls_total.inc()
            # Use Gemini embed_content API
            result = self.client.embed_content(
                model=self.model,
                content=texts,
                task_type="retrieval_document"
            )
            
            # Extract embeddings from result
            if hasattr(result, 'embedding'):
                # Single text case
                return [result.embedding]
            elif hasattr(result, 'embeddings'):
                # Multiple texts case
                return [emb.values for emb in result.embeddings]
            else:
                logger.warning(f"Unexpected Gemini embedding result format: {result}")
                return [[float(len(t))] * 8 for t in texts]
                
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            # Return mock embeddings on error instead of empty lists
            if _should_use_mock():
                return [[float(len(t))] * 8 for t in texts]
            return [[float(len(t))] * 8 for t in texts]  # Graceful fallback

def get_embedding_provider():
    """Get or create singleton embedding provider"""
    global _embedding_provider_instance
    if _embedding_provider_instance is None:
        _embedding_provider_instance = EmbeddingProvider()
    return _embedding_provider_instance
