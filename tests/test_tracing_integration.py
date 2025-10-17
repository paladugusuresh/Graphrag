import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from pydantic import BaseModel, Field
from prometheus_client import REGISTRY
from opentelemetry.trace import TraceFlags, SpanContext, Status, StatusCode

class ExtractedEntities(BaseModel):
    names: list[str] = Field(...)

class ExtractedNode(BaseModel):
    id: str
    type: str

class ExtractedGraph(BaseModel):
    nodes: list[ExtractedNode] = []
    relationships: list[dict] = []

# Global patches for module-level imports
@patch("builtins.open", new_callable=mock_open)
@patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password", "GEMINI_API_KEY": "mock_gemini_key"}, clear=True)
@patch("graph_rag.llm_client._get_redis_client") # Patch the lazy getter function
@patch("graph_rag.cypher_generator.CypherGenerator") # Patch CypherGenerator in its original module
@patch("graph_rag.embeddings.get_embedding_provider") # Patch the embedding getter function
@patch("graph_rag.planner.call_llm_structured") # Patch where it's used in planner
@patch("graph_rag.rag.call_llm_raw") # Patch call_llm_raw in rag
@patch("graph_rag.rag.tracer") # Patch tracer in rag
@patch("graph_rag.rag.get_current_span") # Patch get_current_span in rag
@patch("graph_rag.planner.logger")
@patch("graph_rag.retriever.logger")
@patch("graph_rag.rag.logger")
@patch("graph_rag.ingest.logger")
@patch("graph_rag.ingest.glob.glob")
@patch("langchain.docstore.document.Document") # Patch Document from langchain
@patch("langchain.text_splitter.TokenTextSplitter") # Patch TokenTextSplitter from langchain
@patch("graph_rag.rag.Retriever") # Patch Retriever in rag
@patch("graph_rag.retriever.Neo4jClient") # Patch Neo4jClient in retriever module
@patch("graph_rag.neo4j_client.Neo4jClient") # Patch Neo4jClient in its original module
class TestTracingIntegration(unittest.TestCase):

    def setUp(self):
        # Add the project root to sys.path for module discovery
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

        # Clear module caches to ensure fresh imports
        for module_name in ['graph_rag.rag', 'graph_rag.retriever', 'graph_rag.planner', 'graph_rag.llm_client', 'graph_rag.cypher_generator', 'graph_rag.neo4j_client', 'graph_rag.embeddings', 'graph_rag.ingest']:
            if module_name in sys.modules:
                del sys.modules[module_name]
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    def test_rag_chain_returns_trace_id_and_sources(self, mock_neo4j_client_class, mock_retriever_neo4j_client_class, mock_rag_retriever_class, mock_token_text_splitter_class, mock_document_class, mock_glob, mock_ingest_logger, mock_rag_logger, mock_retriever_logger, mock_planner_logger, mock_get_current_span, mock_rag_tracer, mock_call_llm_raw, mock_call_llm_structured_planner, mock_get_embedding_provider_class, mock_cypher_generator_class, mock_get_redis_client, mock_open):
        # Configure mock_open side_effect
        mock_open.side_effect = [
            mock_open(read_data=json.dumps({
                "schema": {
                    "allow_list_path": "allow_list.json"
                },
                "guardrails": {
                    "neo4j_timeout": 10,
                    "max_traversal_depth": 2
                },
                "llm": {
                    "model": "gemini-2.0-flash-exp",
                    "max_tokens": 512,
                    "rate_limit_per_minute": 60,
                    "redis_url": "redis://localhost:6379/0"
                },
                "retriever": {"max_chunks": 5}
            })).return_value, # For config.yaml
            mock_open(read_data=json.dumps({
                "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
                "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_CHUNK"],
                "properties": {}
            })).return_value, # For allow_list.json read by schema_catalog
        ]

        # Mock OpenTelemetry current span for trace_id
        test_trace_id = 0x1234567890abcdef1234567890abcdef # Changed to valid hexadecimal literal
        mock_span_context = SpanContext(trace_id=test_trace_id, span_id=0x1234567890abcdef, is_remote=False, trace_flags=TraceFlags.SAMPLED) # Set non-zero span_id
        mock_current_span = MagicMock(context=mock_span_context) # Mock a Span object with a context attribute
        
        # Configure mock_rag_tracer.start_as_current_span to return a context manager that yields mock_current_span
        mock_tracer_context_manager = MagicMock()
        mock_tracer_context_manager.__enter__.return_value = mock_current_span
        mock_rag_tracer.start_as_current_span.return_value = mock_tracer_context_manager

        mock_get_current_span.return_value = mock_current_span # Directly mock get_current_span

        # Configure mocks for module-level initializations
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance # Use the patched getter
        mock_redis_instance.eval.return_value = 1 # Allow token consumption

        # Configure the mock Neo4jClient instance that graph_rag.neo4j_client.Neo4jClient will return
        mock_neo4j_client_instance = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client_instance
        mock_neo4j_client_instance.verify_connectivity.return_value = None # Explicitly mock verify_connectivity to do nothing
        mock_neo4j_client_instance.execute_read_query.side_effect = [
            [{"output": "structured context"}], # For structured query
            [{"chunk_id": "chunk1"}], # For unstructured query (vector search)
            [{"id": "chunk1", "text": "chunk1 content"}] # For hierarchy expand
        ]

        # Mock Neo4jClient within the retriever module
        mock_retriever_neo4j_client_instance = MagicMock()
        mock_retriever_neo4j_client_class.return_value = mock_retriever_neo4j_client_instance
        mock_retriever_neo4j_client_instance.execute_read_query.side_effect = [
            [{"output": "structured context"}], # For structured query
            [{"chunk_id": "chunk1"}], # For unstructured query (vector search)
            [{"id": "chunk1", "text": "chunk1 content"}] # For hierarchy expand
        ]
        mock_retriever_neo4j_client_instance.verify_connectivity.return_value = None # Ensure connectivity check passes

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
        mock_embedding_provider_instance.get_embeddings.return_value = [[0.1]*8] # Mock embedding

        # Mock call_llm_raw to return answer text
        mock_call_llm_raw.return_value = "Answer with [chunk1]"

        mock_call_llm_structured_planner.return_value = MagicMock(names=["Microsoft"])

        # Mock the Retriever instance that RAGChain will use
        mock_retriever_instance = MagicMock()
        mock_rag_retriever_class.return_value = mock_retriever_instance
        mock_retriever_instance.retrieve_context.return_value = {
            "structured": "mock structured context",
            "unstructured": "mock unstructured context [chunk1]",
            "chunk_ids": ["chunk1"]
        }

        # Import rag and instantiate rag_chain AFTER all mocks are set up
        from graph_rag.rag import RAGChain
        rag_chain = RAGChain()

        question = "Who founded Microsoft?"
        response = rag_chain.invoke(question)

        self.assertIn("trace_id", response)
        self.assertEqual(response["trace_id"], f"{test_trace_id:x}")
        self.assertIn("sources", response)
        self.assertEqual(response["sources"], ["chunk1"])

        # Verify spans were created (simplified check, more robust checks would involve OTLP mock receiver)
        mock_rag_tracer.start_as_current_span.assert_any_call("rag.invoke")
        # Verify retriever spans are called
        # These will now be called within the mocked retriever, so we check on the mock_retriever_instance
        mock_retriever_instance.retrieve_context.assert_called_once()
