# graph_rag/planner.py
import yaml
from pydantic import BaseModel, Field
from graph_rag.observability import get_logger
from graph_rag.llm_client import call_llm_structured, LLMStructuredError

logger = get_logger(__name__)
with open("config.yaml", 'r') as f:
    CFG = yaml.safe_load(f)

class ExtractedEntities(BaseModel):
    names: list[str] = Field(...)

class QueryPlan(BaseModel):
    intent: str
    anchor_entity: str | None = None
    question: str

def _detect_intent(question: str):
    q = question.lower()
    if "who founded" in q:
        return "company_founder_query"
    if "product" in q:
        return "company_product_query"
    return "general_rag_query"

def generate_plan(question: str) -> QueryPlan:
    # Get candidate entities via LLM structured output (or local NER in production)
    try:
        prompt = f"Extract person and organization entity names from: {question}"
        extracted = call_llm_structured(prompt, ExtractedEntities)
        names = extracted.names
    except LLMStructuredError as e:
        logger.warning(f"LLM entity extraction failed: {e}. Falling back to empty entities.")
        names = []

    intent = _detect_intent(question)
    # Anchor validation against DB happens in the Planner caller; here we return a simple plan
    return QueryPlan(intent=intent, anchor_entity=(names[0] if names else None), question=question)
