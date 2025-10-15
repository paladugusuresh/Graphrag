# graph_rag/rag.py
import os
import re
import json
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from graph_rag.planner import generate_plan
from graph_rag.retriever import Retriever # Import the class, not the instance
from graph_rag.observability import get_logger, tracer
from opentelemetry.trace import get_current_span
from graph_rag.audit_store import audit_store

logger = get_logger(__name__)

class RAGChain:
    def __init__(self):
        """Initialize RAG chain with lazy LLM instantiation"""
        self._llm: Optional[ChatOpenAI] = None
        self.retriever = Retriever() # Instantiate Retriever locally
    
    @property
    def llm(self) -> ChatOpenAI:
        """Lazy initialization of LLM"""
        if self._llm is None:
            # Check if we're in DEV_MODE or missing API key
            dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
            api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key and not dev_mode:
                raise RuntimeError("OPENAI_API_KEY not set and not in DEV_MODE")
            elif not api_key and dev_mode:
                logger.warning("DEV_MODE: Creating ChatOpenAI with placeholder - LLM calls will fail but imports succeed")
                # Create a placeholder that won't be used in tests
                try:
                    self._llm = ChatOpenAI(temperature=0, model_name="gpt-4o", api_key="dev-mode-placeholder")
                except Exception as e:
                    logger.warning(f"Could not create ChatOpenAI in DEV_MODE: {e}")
                    # Return None and let tests mock it
                    return None
            else:
                self._llm = ChatOpenAI(temperature=0, model_name="gpt-4o")
        
        return self._llm

    def _verify_citations(self, answer, provided_chunk_ids, question, trace_id):
        cited = set(re.findall(r'\[([^\]]+)\]', answer))
        provided = set(provided_chunk_ids)
        unknown = cited - provided
        
        verification_result = {
            "cited_ids": list(cited),
            "provided_ids": list(provided_chunk_ids),
            "unknown_citations": list(unknown),
            "verified": not bool(unknown),
            "verification_action": ""
        }
        
        if unknown:
            verification_result["verification_action"] = "human_review_required"
            audit_store.record({
                "event_type": "citation_verification_failed",
                "trace_id": trace_id,
                "question": question,
                "unknown_citations": list(unknown)
            })
            
        return verification_result

    def invoke(self, question: str):
        with tracer.start_as_current_span("rag.invoke") as span:
            plan = generate_plan(question)
            span.set_attribute("plan.intent", plan.intent)
            current_span = get_current_span()
            trace_id_hex = f"{current_span.context.trace_id:x}" if current_span and current_span.context.is_valid else None

            rc = self.retriever.retrieve_context(plan)
            prompt_template = """
            You are an expert Q&A system. Use ONLY the context provided below.
            Structured:
            {structured}
            Unstructured:
            {unstructured}
            Question:
            {question}
            """
            prompt = prompt_template.format(structured=rc['structured'], unstructured=rc['unstructured'], question=question)
            answer = self.llm.generate([{"role":"user","content":prompt}]).generations[0][0].text
            
            verification = self._verify_citations(answer, rc.get("chunk_ids", []), question, trace_id_hex)
            
            response = {
                "question": question,
                "answer": answer,
                "plan": plan.model_dump(),
                "sources": rc.get("chunk_ids", []),
                "citation_verification": verification,
                "trace_id": trace_id_hex # Include trace_id in response
            }
            return response

rag_chain = RAGChain()
