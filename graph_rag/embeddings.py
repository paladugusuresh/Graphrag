# graph_rag/embeddings.py
import os
from dotenv import load_dotenv
from graph_rag.observability import get_logger, llm_calls_total

logger = get_logger(__name__)
# load_dotenv() # Moved to be called explicitly if needed, or mocked

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_KEY:
    logger.error("OPENAI_API_KEY not present in env")

try:
    from langchain_openai import OpenAIEmbeddings
except Exception:
    # placeholder: real environment should have langchain-openai package
    OpenAIEmbeddings = None

_embedding_provider_instance = None

class EmbeddingProvider:
    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model = model_name
        if OpenAIEmbeddings:
            self.client = OpenAIEmbeddings(model=model_name)
            logger.info("OpenAI embeddings client initialized")
        else:
            self.client = None
            logger.info("OpenAIEmbeddings not installed; running in mock mode")

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
