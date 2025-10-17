import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from pydantic import BaseModel, Field
from prometheus_client import REGISTRY
from opentelemetry.trace import TraceFlags, SpanContext

class ExtractedEntities(BaseModel):
    names: list[str] = Field(...)

class ExtractedNode(BaseModel):
    id: str
    type: str

class ExtractedGraph(BaseModel):
    nodes: list[ExtractedNode] = []
    relationships: list[dict] = []

@patch("builtins.open", new_callable=mock_open)
@patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password", "GEMINI_API_KEY": "mock_gemini_key"}, clear=True)
@patch("graph_rag.llm_client._get_redis_client")
@patch("graph_rag.cypher_generator.CypherGenerator")
@patch("graph_rag.embeddings.get_embedding_provider")
@patch("graph_rag.planner.call_llm_structured")
@patch("graph_rag.rag.call_llm_raw")
@patch("graph_rag.rag.tracer")
@patch("graph_rag.rag.get_current_span")
@patch("graph_rag.rag.audit_store.record") # Patch audit_store.record
@patch("graph_rag.planner.logger")
@patch("graph_rag.retriever.logger")
@patch("graph_rag.rag.logger")
@patch("graph_rag.ingest.logger")
@patch("graph_rag.ingest.glob.glob")
@patch("langchain.docstore.document.Document")
@patch("langchain.text_splitter.TokenTextSplitter")
@patch("graph_rag.rag.Retriever")
@patch("graph_rag.retriever.Neo4jClient")
@patch("graph_rag.neo4j_client.Neo4jClient")
class TestCitationVerification(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

        for module_name in ['graph_rag.rag', 'graph_rag.retriever', 'graph_rag.planner', 'graph_rag.llm_client', 'graph_rag.cypher_generator', 'graph_rag.neo4j_client', 'graph_rag.embeddings', 'graph_rag.ingest', 'graph_rag.audit_store']:
            if module_name in sys.modules:
                del sys.modules[module_name]
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    def test_unknown_citation_flags_verification_failure_and_audits(self, mock_neo4j_client_class, mock_retriever_neo4j_client_class, mock_rag_retriever_class, mock_token_text_splitter_class, mock_document_class, mock_glob, mock_ingest_logger, mock_rag_logger, mock_retriever_logger, mock_planner_logger, mock_audit_store_record, mock_get_current_span, mock_rag_tracer, mock_call_llm_raw, mock_call_llm_structured_planner, mock_get_embedding_provider_class, mock_cypher_generator_class, mock_get_redis_client, mock_open):
        # Configure mock_open side_effect
        mock_open.side_effect = [
            mock_open(read_data=json.dumps({
                "schema": { "allow_list_path": "allow_list.json" },
                "guardrails": { "neo4j_timeout": 10, "max_traversal_depth": 2 },
                "llm": { "model": "gemini-2.0-flash-exp", "max_tokens": 512, "rate_limit_per_minute": 60, "redis_url": "redis://localhost:6379/0" },
                "retriever": {"max_chunks": 5}
            })).return_value, # For config.yaml
            mock_open(read_data=json.dumps({
                "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
                "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_CHUNK"],
                "properties": {}
            })).return_value, # For allow_list.json
        ]

        # Mock OpenTelemetry current span for trace_id
        test_trace_id = 0x1234567890abcdef1234567890abcdef
        mock_span_context = SpanContext(trace_id=test_trace_id, span_id=0x1234567890abcdef, is_remote=False, trace_flags=TraceFlags.SAMPLED)
        mock_current_span = MagicMock(context=mock_span_context)
        
        mock_tracer_context_manager = MagicMock()
        mock_tracer_context_manager.__enter__.return_value = mock_current_span
        mock_rag_tracer.start_as_current_span.return_value = mock_tracer_context_manager

        mock_get_current_span.return_value = mock_current_span

        # Configure mocks for module-level initializations
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance
        mock_redis_instance.eval.return_value = 1

        mock_cypher_generator_instance = MagicMock()
        mock_cypher_generator_class.return_value = mock_cypher_generator_instance
        mock_cypher_generator_instance.allow_list = {
            "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
            "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_CHUNK"],
            "properties": {}
        }
        mock_cypher_generator_instance.CYPHER_TEMPLATES = {
            "general_rag_query": {"cypher": "MATCH (n) RETURN n LIMIT 1"},
            "company_founder_query": {"cypher": "MATCH (n:Person) RETURN n LIMIT 1"},
        }

        mock_embedding_provider_instance = MagicMock()
        mock_get_embedding_provider_class.return_value = mock_embedding_provider_instance
        mock_embedding_provider_instance.get_embeddings.return_value = [[0.1]*8]

        # Mock Neo4jClient instances
        mock_neo4j_client_instance = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client_instance
        mock_neo4j_client_instance.verify_connectivity.return_value = None
        mock_neo4j_client_instance.execute_read_query.side_effect = [
            [{"output": "structured context"}],
            [{"chunk_id": "chunk1"}],
            [{"id": "chunk1", "text": "chunk1 content"}]
        ]
        
        mock_retriever_neo4j_client_instance = MagicMock()
        mock_retriever_neo4j_client_class.return_value = mock_retriever_neo4j_client_instance
        mock_retriever_neo4j_client_instance.execute_read_query.side_effect = [
            [{"output": "structured context"}],
            [{"chunk_id": "chunk1"}],
            [{"id": "chunk1", "text": "chunk1 content"}]
        ]
        mock_retriever_neo4j_client_instance.verify_connectivity.return_value = None

        # Mock call_llm_raw to return an answer with an unknown citation "chunk_unknown"
        mock_call_llm_raw.return_value = "Answer with [chunk1] and [chunk_unknown]"

        mock_call_llm_structured_planner.return_value = MagicMock(names=["Microsoft"])

        # Mock the Retriever instance that RAGChain will use, providing only "chunk1"
        mock_retriever_instance = MagicMock()
        mock_rag_retriever_class.return_value = mock_retriever_instance
        mock_retriever_instance.retrieve_context.return_value = {
            "structured": "mock structured context",
            "unstructured": "mock unstructured context [chunk1]",
            "chunk_ids": ["chunk1"] # Only "chunk1" is provided
        }

        # Import rag and instantiate rag_chain AFTER all mocks are set up
        from graph_rag.rag import RAGChain
        rag_chain = RAGChain()

        question = "Who founded Microsoft?"
        response = rag_chain.invoke(question)

        # Assertions for citation verification
        self.assertIn("citation_verification", response)
        self.assertFalse(response["citation_verification"]["verified"])
        self.assertIn("chunk_unknown", response["citation_verification"]["unknown_citations"])
        self.assertEqual(response["citation_verification"]["verification_action"], "human_review_required")

        # Assert audit entry was created
        mock_audit_store_record.assert_called_once_with({
            "event_type": "citation_verification_failed",
            "trace_id": f"{test_trace_id:x}",
            "question": question,
            "unknown_citations": ["chunk_unknown"]
        })
