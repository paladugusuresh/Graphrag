import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
import sys
import pytest

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.planner import generate_plan

# Pytest markers for integration tests that require Neo4j
pytestmark = [pytest.mark.integration, pytest.mark.needs_neo4j]

class TestPlannerEndToEnd(unittest.TestCase):
    """End-to-end integration tests for planner with schema embeddings fallback."""

    def setUp(self):
        # Clear module cache and Prometheus registry
        for module_name in [
            'graph_rag.planner',
            'graph_rag.llm_client', 
            'graph_rag.neo4j_client',
            'graph_rag.embeddings',
            'graph_rag.cypher_generator',
            'graph_rag.observability'
        ]:
            if module_name in sys.modules:
                del sys.modules[module_name]
        
        # Clear Prometheus registry to prevent metric conflicts
        try:
            from prometheus_client import REGISTRY
            REGISTRY._names_to_collectors.clear()
        except ImportError:
            pass

    def _create_test_allow_list(self):
        """Create a test allow_list.json with known schema terms including Organization."""
        return {
            "node_labels": [
                "Document", "Chunk", "Entity", "__Entity__",
                "Person", "Organization", "Product", "Company"
            ],
            "relationship_types": [
                "PART_OF", "HAS_CHUNK", "MENTIONS", 
                "FOUNDED", "HAS_PRODUCT", "CREATED", "WORKS_AT"
            ],
            "properties": {
                "Person": ["name", "title", "email"],
                "Organization": ["name", "industry", "founded"],
                "Product": ["name", "version", "release_date"]
            }
        }

    def _create_test_config(self):
        """Create a test config.yaml with all required sections."""
        return """
        logging:
          level: INFO
        
        schema:
          allow_list_path: allow_list.json
        
        retriever:
          max_chunks: 5
        
        guardrails:
          neo4j_timeout: 10
          max_cypher_results: 25
        
        observability:
          metrics_enabled: true
          metrics_port: 8000
        
        llm:
          provider: openai
          model: gpt-4o
          max_tokens: 512
          rate_limit_per_minute: 60
          redis_url: redis://localhost:6379/0
          planner_model: gpt-4o
          planner_max_tokens: 256
        
        schema_embeddings:
          index_name: schema_embeddings
          node_label: SchemaTerm
          embedding_model: text-embedding-3-small
          top_k: 5
        """

    def _create_mock_schema_terms(self):
        """Create mock schema term embeddings for testing."""
        return [
            {
                'id': 'label:Organization',
                'term': 'Organization',
                'type': 'label',
                'canonical_id': 'Organization',
                'score': 0.92
            },
            {
                'id': 'label:Company',
                'term': 'Company',
                'type': 'label',
                'canonical_id': 'Organization',  # Synonym
                'score': 0.87
            }
        ]

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "mock_key", 
        "NEO4J_URI": "bolt://localhost:7687", 
        "NEO4J_USERNAME": "neo4j", 
        "NEO4J_PASSWORD": "password"
    })
    @patch("graph_rag.llm_client.CFG")
    @patch("graph_rag.planner.Neo4jClient")
    @patch("graph_rag.planner.get_embedding_provider")
    @patch("graph_rag.planner.CypherGenerator")
    @patch("graph_rag.planner.tracer")
    @patch("graph_rag.planner.call_llm_structured")
    @patch("graph_rag.llm_client._get_redis_client")
    @patch("builtins.open", new_callable=mock_open)
    def test_planner_with_semantic_fallback_integration(
        self, mock_file_open, mock_get_redis_client, mock_call_llm_structured, mock_tracer,
        mock_cypher_generator_class, mock_get_embedding_provider, mock_neo4j_client_class, mock_llm_cfg
    ):
        """Test complete planner integration: Who created Synapse product at Innovatech?
        
        This test verifies:
        - Seeded allow_list.json with "Organization" label
        - Mock schema embeddings for semantic fallback
        - Mock embedding provider with stable vectors
        - Mock database queries for vector search
        - Planner returns valid intent from CYPHER_TEMPLATES
        - Anchor entity is set via semantic mapping
        """
        
        # Set up file mocks
        test_config = self._create_test_config()
        test_allow_list = json.dumps(self._create_test_allow_list())
        
        def mock_open_side_effect(filename, mode='r'):
            if filename == "config.yaml":
                return mock_open(read_data=test_config).return_value
            elif filename == "allow_list.json":
                return mock_open(read_data=test_allow_list).return_value
            else:
                raise FileNotFoundError(f"File not found: {filename}")
        
        mock_file_open.side_effect = mock_open_side_effect
        
        # Mock LLM client config
        mock_llm_cfg.__getitem__.side_effect = lambda key: {
            "llm": {"redis_url": "redis://localhost:6379/0", "rate_limit_per_minute": 60}
        }[key]
        
        # Mock Redis client
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = 1
        mock_get_redis_client.return_value = mock_redis_instance
        
        # Mock tracer span
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        # Mock LLM calls - planner succeeds but doesn't provide anchor
        from graph_rag.planner import PlannerOutput, ExtractedEntities
        
        mock_planner_output = PlannerOutput(
            intent="general_rag_query",  # Valid intent from CYPHER_TEMPLATES
            params={"topic": "Synapse product", "company": "Innovatech"},
            confidence=0.85,
            chain=None
        )
        
        mock_extracted_entities = ExtractedEntities(names=["Innovatech", "Synapse"])
        
        mock_call_llm_structured.side_effect = [
            mock_planner_output,      # First call: planner
            mock_extracted_entities   # Second call: entity extraction fallback
        ]
        
        # Mock embedding provider with stable vectors
        mock_embedding_provider = MagicMock()
        mock_embedding_provider.get_embeddings.return_value = [
            [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]  # Stable 8-dim embedding for "Innovatech"
        ]
        mock_get_embedding_provider.return_value = mock_embedding_provider
        
        # Mock Neo4j client for vector search
        mock_neo4j_client = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client
        
        # Mock vector search results - "Innovatech" maps to "Organization"
        mock_schema_terms = self._create_mock_schema_terms()
        mock_neo4j_client.execute_read_query.return_value = mock_schema_terms
        
        # Mock CypherGenerator for label validation
        mock_cypher_generator = MagicMock()
        mock_cypher_generator.validate_label.return_value = True
        mock_cypher_generator_class.return_value = mock_cypher_generator
        
        # Execute the test - this is the main assertion
        plan = generate_plan("Who created Synapse product at Innovatech?")
        
        # Assertions as specified in task requirements
        self.assertIsNotNone(plan)
        
        # Assert returned intent is in CYPHER_TEMPLATES (we'll verify this exists)
        from graph_rag.cypher_generator import CYPHER_TEMPLATES
        self.assertIn(plan.intent, CYPHER_TEMPLATES, 
                     f"Intent '{plan.intent}' should be in CYPHER_TEMPLATES")
        
        # Assert anchor_entity is set by semantic fallback
        self.assertEqual(plan.anchor_entity, "Organization", 
                        "Anchor entity should be set to 'Organization' via semantic mapping")
        
        self.assertEqual(plan.question, "Who created Synapse product at Innovatech?")
        
        # Verify semantic mapping was used
        mock_embedding_provider.get_embeddings.assert_called_once_with(["Innovatech"])
        mock_neo4j_client.execute_read_query.assert_called_once()
        
        # Verify vector query structure
        vector_call_args = mock_neo4j_client.execute_read_query.call_args
        query = vector_call_args[0][0]
        self.assertIn("CALL db.index.vector.queryNodes('schema_embeddings'", query)
        
        # Verify label validation was called
        mock_cypher_generator.validate_label.assert_called_once_with("Organization")

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "mock_key", 
        "NEO4J_URI": "bolt://localhost:7687", 
        "NEO4J_USERNAME": "neo4j", 
        "NEO4J_PASSWORD": "password"
    })
    @patch("builtins.open", new_callable=mock_open)
    def test_planner_fallback_when_semantic_mapping_fails(
        self, mock_file_open
    ):
        """Test planner fallback when semantic mapping finds no results."""
        
        # Set up file mocks
        test_config = self._create_test_config()
        test_allow_list = json.dumps(self._create_test_allow_list())
        
        def mock_open_side_effect(filename, mode='r'):
            if filename == "config.yaml":
                return mock_open(read_data=test_config).return_value
            elif filename == "allow_list.json":
                return mock_open(read_data=test_allow_list).return_value
            else:
                raise FileNotFoundError(f"File not found: {filename}")
        
        mock_file_open.side_effect = mock_open_side_effect
        
        # Mock all the necessary components to avoid import errors
        with patch("graph_rag.llm_client.CFG", {"llm": {"redis_url": "redis://localhost:6379/0", "rate_limit_per_minute": 60}}), \
             patch("graph_rag.llm_client._get_redis_client") as mock_get_redis_client, \
             patch("graph_rag.planner.call_llm_structured") as mock_call_llm_structured:
            
            # Mock Redis client
            mock_redis_instance = MagicMock()
            mock_redis_instance.eval.return_value = 1
            mock_get_redis_client.return_value = mock_redis_instance
            
            # Mock LLM calls - all fail
            from graph_rag.llm_client import LLMStructuredError
            mock_call_llm_structured.side_effect = LLMStructuredError("All LLM calls failed")
            
            # Execute the test
            plan = generate_plan("Who founded Google?")
            
            # Assertions - should fall back to rule-based detection
            self.assertIsNotNone(plan)
            
            # Verify intent is valid (rule-based detection should return company_founder_query)
            from graph_rag.cypher_generator import CYPHER_TEMPLATES
            self.assertIn(plan.intent, CYPHER_TEMPLATES, 
                         f"Intent '{plan.intent}' should be in CYPHER_TEMPLATES even with fallback")
            
            self.assertEqual(plan.question, "Who founded Google?")

if __name__ == '__main__':
    unittest.main()