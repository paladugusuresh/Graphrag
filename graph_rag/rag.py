# graph_rag/rag.py
import os
import re
import json
from typing import Optional
from graph_rag.planner import generate_plan
from graph_rag.retriever import Retriever # Import the class, not the instance
from graph_rag.observability import get_logger, tracer
from opentelemetry.trace import get_current_span
from graph_rag.audit_store import audit_store
from graph_rag.llm_client import call_llm_raw
from graph_rag.config_manager import get_config_value

logger = get_logger(__name__)

class RAGChain:
    def __init__(self):
        """Initialize RAG chain"""
        self.retriever = Retriever() # Instantiate Retriever locally

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
            
            # Use llm_client instead of ChatOpenAI
            model = get_config_value('llm.model', 'gemini-2.0-flash-exp')
            max_tokens = get_config_value('llm.max_tokens', 512)
            answer = call_llm_raw(prompt, model=model, max_tokens=max_tokens)
            
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
