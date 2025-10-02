# graph_rag/rag.py
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from graph_rag.planner import generate_plan
from graph_rag.retriever import Retriever # Import the class, not the instance
from graph_rag.observability import get_logger, tracer
from opentelemetry.trace import get_current_span

logger = get_logger(__name__)

class RAGChain:
    def __init__(self):
        self.llm = ChatOpenAI(temperature=0, model_name="gpt-4o")
        self.retriever = Retriever() # Instantiate Retriever locally

    def _verify_citations(self, answer, provided_context):
        cited = set(re.findall(r'\[([^\]]+)\]', answer))
        provided = set(re.findall(r'\[([^\]]+)\]', provided_context))
        unknown = cited - provided
        return {"cited_ids": list(cited), "provided_ids": list(provided), "unknown_citations": list(unknown), "verified": not unknown}

    def invoke(self, question: str):
        with tracer.start_as_current_span("rag.invoke") as span:
            plan = generate_plan(question)
            span.set_attribute("plan.intent", plan.intent)
            current_span = get_current_span()
            trace_id = current_span.context.trace_id if current_span and current_span.context.is_valid else None

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
            verification = self._verify_citations(answer, rc['unstructured'])
            response = {
                "question": question,
                "answer": answer,
                "plan": plan.model_dump(),
                "sources": rc.get("chunk_ids", []),
                "citation_verification": verification,
                "trace_id": f"{trace_id:x}" if trace_id else None # Include trace_id in response
            }
            return response

rag_chain = RAGChain()
