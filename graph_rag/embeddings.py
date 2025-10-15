# graph_rag/embeddings.py
import os
from typing import Optional
from dotenv import load_dotenv
from graph_rag.observability import get_logger, llm_calls_total

logger = get_logger(__name__)

# Load .env file once at import time (safe operation)
load_dotenv()

def _get_openai_key() -> Optional[str]:
    """Get OpenAI API key from environment, logging warning if missing"""
    key = os.getenv("OPENAI_API_KEY")
    dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
    
    if not key and not dev_mode:
        logger.error("OPENAI_API_KEY not present in env")
    elif not key and dev_mode:
        logger.info("OPENAI_API_KEY not present in env, running in DEV_MODE with mock embeddings")
    
    return key

try:
    from langchain_openai import OpenAIEmbeddings
except Exception:
    # placeholder: real environment should have langchain-openai package
    OpenAIEmbeddings = None
    logger.info("langchain_openai not installed; will use mock embeddings")

_embedding_provider_instance = None

class EmbeddingProvider:
    def __init__(self, model_name: str = "text-embedding-3-small"):
        """Initialize embedding provider with lazy client creation"""
        self.model = model_name
        self.client = None
        
        # Only initialize if we have the API key and the package
        api_key = _get_openai_key()
        if api_key and OpenAIEmbeddings:
            try:
                self.client = OpenAIEmbeddings(model=model_name)
                logger.info("OpenAI embeddings client initialized")
            except Exception as e:
                dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
                if dev_mode:
                    logger.warning(f"Failed to initialize OpenAI embeddings in DEV_MODE: {e}")
                else:
                    logger.error(f"Failed to initialize OpenAI embeddings: {e}")
                    raise
        else:
            logger.info("Running with mock embeddings (no API key or langchain_openai not installed)")

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.client:
            # simple deterministic mock embeddings
            return [[float(len(t))] * 8 for t in texts]
        try:
            llm_calls_total.inc()
            return self.client.embed_documents(texts)
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return [[] for _ in texts]

def get_embedding_provider():
    global _embedding_provider_instance
    if _embedding_provider_instance is None:
        _embedding_provider_instance = EmbeddingProvider()
    return _embedding_provider_instance

# embedding_provider = EmbeddingProvider() # Removed module-level instantiation
