import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from pydantic import BaseModel
from prometheus_client import REGISTRY

class ExtractedNode(BaseModel):
    id: str
    type: str

class ExtractedGraph(BaseModel):
    nodes: list[ExtractedNode] = []
    relationships: list[dict] = []

# Global patches for module-level imports
@patch("builtins.open", new_callable=mock_open)
@patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password", "OPENAI_API_KEY": "mock_openai_key"}, clear=True)
@patch("graph_rag.llm_client._get_redis_client") # Patch the lazy getter function
@patch("graph_rag.neo4j_client.GraphDatabase")
@patch("graph_rag.neo4j_client.Neo4jClient") # Patch Neo4jClient in its original module
@patch("graph_rag.cypher_generator.CypherGenerator") # Patch CypherGenerator in its original module
@patch("graph_rag.ingest.call_llm_structured") # Patch where it's used
@patch("graph_rag.ingest.logger")
@patch("graph_rag.ingest.glob.glob")
@patch("langchain.docstore.document.Document") # Patch Document from langchain
@patch("langchain.text_splitter.TokenTextSplitter") # Patch TokenTextSplitter from langchain
class TestIngestLLMValidation(unittest.TestCase):

    def setUp(self):
        # Add the project root to sys.path for module discovery
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

        if 'graph_rag.ingest' in sys.modules:
            del sys.modules['graph_rag.ingest']
        if 'graph_rag.cypher_generator' in sys.modules:
            del sys.modules['graph_rag.cypher_generator']
        if 'graph_rag.neo4j_client' in sys.modules:
            del sys.modules['graph_rag.neo4j_client']
        if 'graph_rag.llm_client' in sys.modules:
            del sys.modules['graph_rag.llm_client']
        if 'graph_rag.embeddings' in sys.modules:
            del sys.modules['graph_rag.embeddings']
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    def test_ingest_with_invalid_label_fallback(self, mock_token_text_splitter_class, mock_document_class, mock_glob, mock_logger, mock_call_llm_structured_ingest, mock_cypher_generator_class, mock_neo4j_client_class, mock_graph_database_class, mock_get_redis_client, mock_open):
        # Configure mock_open side_effect
        mock_open.side_effect = [
            mock_open(read_data=json.dumps({
                "schema": {
                    "allow_list_path": "allow_list.json"
                },
                "guardrails": {
                    "neo4j_timeout": 10
                },
                "llm": {
                    "model": "gpt-4o",
                    "max_tokens": 512,
                    "rate_limit_per_minute": 60,
                    "redis_url": "redis://localhost:6379/0"
                }
            })).return_value, # For config.yaml
            mock_open(read_data=json.dumps({
                "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
                "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_PRODUCT"],
                "properties": {}
            })).return_value, # For allow_list.json read by schema_catalog
            mock_open(read_data="---\nid: doc1\n---\ncontent").return_value # For the .md file
        ]
        mock_glob.return_value = ["data/doc1.md"]

        # Configure mocks for module-level initializations
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance # Use the patched getter
        mock_redis_instance.eval.return_value = 1 # Allow token consumption

        mock_driver_instance = MagicMock()
        mock_graph_database_class.driver.return_value = mock_driver_instance
        mock_driver_instance.verify_connectivity.return_value = None

        mock_cypher_generator_instance = MagicMock()
        mock_cypher_generator_class.return_value = mock_cypher_generator_instance
        mock_cypher_generator_instance.allow_list = {
            "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
            "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_PRODUCT"],
            "properties": {}
        }

        # Mock Neo4jClient instance
        mock_client_instance = MagicMock()
        mock_neo4j_client_class.return_value = mock_client_instance
        mock_client_instance.verify_connectivity.return_value = None

        # Mock call_llm_structured to return an invalid node type
        invalid_node_type = "Invalid-Label"
        mock_call_llm_structured_ingest.return_value = ExtractedGraph(nodes=[
            ExtractedNode(id="node1", type=invalid_node_type)
        ])

        # Mock cypher_generator.validate_label
        mock_cypher_generator_instance.validate_label.return_value = "`Entity`"
        
        from graph_rag import ingest
        ingest.process_and_ingest_files()

        # Assert that validate_label was called with the invalid type
        mock_cypher_generator_instance.validate_label.assert_called_once_with(invalid_node_type)
        
        # Assert that the MERGE query used the fallback 'Entity' label
        mock_client_instance.execute_write_query.assert_any_call(
            f"MERGE (n:`Entity` {{id: $id}})", 
            {"id": "node1"}, 
            timeout=10
        )

        # Assert that a warning was logged (though validate_label handles this now)
        # mock_logger.warning.assert_called_once() # This is now handled inside cypher_generator
