# graph_rag/schemas.py
"""
Pydantic models for structured LLM output validation.
These models define the expected structure for LLM responses used with call_llm_structured.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class CypherGenerationOutput(BaseModel):
    """
    Schema for LLM-generated Cypher query output.
    
    Used for validating structured responses when generating Cypher queries.
    The LLM should return a JSON object with these exact field names.
    """
    cypher: str = Field(
        description="The generated Cypher query string",
        examples=["MATCH (n:Person) RETURN n LIMIT 10"]
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the Cypher query",
        examples=[{"name": "John", "limit": 10}]
    )


class SummaryOutput(BaseModel):
    """
    Schema for LLM-generated summary output.
    
    Used for validating structured responses when generating summaries from query results.
    The LLM should return a JSON object with these exact field names.
    """
    summary: str = Field(
        description="The generated summary text",
        examples=["The query returned 5 people named John who work at tech companies."]
    )
    citations: List[str] = Field(
        default_factory=list,
        description="List of citation references or source identifiers",
        examples=[["node_123", "node_456"]]
    )
    table: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured table data extracted from results",
        examples=[[{"name": "John", "company": "TechCorp"}, {"name": "Jane", "company": "DataInc"}]]
    )


class PlannerOutput(BaseModel):
    """
    Schema for LLM-generated query planning output.
    
    Used for validating structured responses when planning query execution.
    This is a simplified version focused on core planning fields.
    The LLM should return a JSON object with these exact field names.
    """
    intent: str = Field(
        description="The query intent or template name",
        examples=["general_rag_query", "company_founder_query", "person_search"]
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the query execution",
        examples=[{"anchor": "John_Doe", "limit": 10}]
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score for the planning decision (0.0 to 1.0)",
        examples=[0.85, 0.92, 0.67]
    )
