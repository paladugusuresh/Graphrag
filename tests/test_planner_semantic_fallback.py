import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
import sys

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.planner import generate_plan, _find_best_anchor_entity_semantic

class TestPlannerSemanticFallback(unittest.TestCase):

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

    @patch.dict(os.environ, {"GEMINI_API_KEY": "mock_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"})
    @patch("graph_rag.planner.Neo4jClient")
    @patch("graph_rag.planner.get_embedding_provider")
    @patch("graph_rag.planner.CypherGenerator")
    @patch("graph_rag.planner.tracer")
    @patch("builtins.open", new_callable=mock_open)
    def test_find_best_anchor_entity_semantic_success(self, mock_file_open, mock_tracer, mock_cypher_generator_class, mock_get_embedding_provider, mock_neo4j_client_class):
        """Test successful semantic mapping of entity using schema embeddings."""
        
        # Mock config.yaml
        config_data = """
        guardrails:
          neo4j_timeout: 10
        schema_embeddings:
          index_name: test_schema_embeddings
          top_k: 5
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock tracer span
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        # Mock embedding provider
        mock_embedding_provider = MagicMock()
        mock_embedding_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]
        mock_get_embedding_provider.return_value = mock_embedding_provider
        
        # Mock Neo4j client
        mock_neo4j_client = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client
        
        # Mock vector search results
        mock_neo4j_client.execute_read_query.return_value = [
            {
                'id': 'label:Organization',
                'term': 'Organization',
                'type': 'label',
                'canonical_id': 'Organization',
                'score': 0.95
            },
            {
                'id': 'label:Company',
                'term': 'Company', 
                'type': 'label',
                'canonical_id': 'Organization',  # Synonym mapping
                'score': 0.87
            }
        ]
        
        # Mock CypherGenerator
        mock_cypher_generator = MagicMock()
        mock_cypher_generator.validate_label.return_value = True
        mock_cypher_generator_class.return_value = mock_cypher_generator
        
        # Test semantic mapping
        result = _find_best_anchor_entity_semantic("Microsoft Corporation")
        
        # Verify result
        self.assertEqual(result, "Organization")
        
        # Verify embedding provider was called
        mock_embedding_provider.get_embeddings.assert_called_once_with(["Microsoft Corporation"])
        
        # Verify Neo4j query was called with correct parameters
        mock_neo4j_client.execute_read_query.assert_called_once()
        call_args = mock_neo4j_client.execute_read_query.call_args
        
        # Check query structure
        query = call_args[0][0]
        self.assertIn("CALL db.index.vector.queryNodes('test_schema_embeddings'", query)
        self.assertIn("YIELD node, score", query)
        self.assertIn("RETURN node.id as id, node.term as term, node.type as type", query)
        
        # Check parameters
        params = call_args[0][1]
        self.assertEqual(params['top_k'], 5)
        self.assertEqual(params['embedding'], [0.1, 0.2, 0.3, 0.4, 0.5])
        
        # Verify label validation was called
        mock_cypher_generator.validate_label.assert_called_once_with("Organization")
        
        # Verify tracing
        mock_tracer.start_as_current_span.assert_called_once_with("planner.semantic_mapping")
        mock_span.set_attribute.assert_any_call("candidate_entity", "Microsoft Corporation")
        mock_span.set_attribute.assert_any_call("embedding_dimensions", 5)
        mock_span.set_attribute.assert_any_call("mapped_entity", "Organization")
        mock_span.set_attribute.assert_any_call("similarity_score", 0.95)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "mock_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"})
    @patch("graph_rag.planner.Neo4jClient")
    @patch("graph_rag.planner.get_embedding_provider")
    @patch("graph_rag.planner.CypherGenerator")
    @patch("graph_rag.planner.tracer")
    @patch("builtins.open", new_callable=mock_open)
    def test_find_best_anchor_entity_semantic_no_results(self, mock_file_open, mock_tracer, mock_cypher_generator_class, mock_get_embedding_provider, mock_neo4j_client_class):
        """Test semantic mapping when no schema embeddings are found."""
        
        # Mock config.yaml
        config_data = """
        guardrails:
          neo4j_timeout: 10
        schema_embeddings:
          index_name: schema_embeddings
          top_k: 5
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock tracer span
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        # Mock embedding provider
        mock_embedding_provider = MagicMock()
        mock_embedding_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
        mock_get_embedding_provider.return_value = mock_embedding_provider
        
        # Mock Neo4j client with no results
        mock_neo4j_client = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client
        mock_neo4j_client.execute_read_query.return_value = []
        
        # Test semantic mapping
        result = _find_best_anchor_entity_semantic("UnknownEntity")
        
        # Verify result
        self.assertIsNone(result)
        
        # Verify components were called
        mock_embedding_provider.get_embeddings.assert_called_once_with(["UnknownEntity"])
        mock_neo4j_client.execute_read_query.assert_called_once()

    @patch.dict(os.environ, {"GEMINI_API_KEY": "mock_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"})
    @patch("graph_rag.planner.Neo4jClient")
    @patch("graph_rag.planner.get_embedding_provider")
    @patch("graph_rag.planner.CypherGenerator")
    @patch("graph_rag.planner.tracer")
    @patch("builtins.open", new_callable=mock_open)
    def test_find_best_anchor_entity_semantic_invalid_label(self, mock_file_open, mock_tracer, mock_cypher_generator_class, mock_get_embedding_provider, mock_neo4j_client_class):
        """Test semantic mapping when found label is not in allow_list."""
        
        # Mock config.yaml
        config_data = """
        guardrails:
          neo4j_timeout: 10
        schema_embeddings:
          index_name: schema_embeddings
          top_k: 5
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock tracer span
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        # Mock embedding provider
        mock_embedding_provider = MagicMock()
        mock_embedding_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
        mock_get_embedding_provider.return_value = mock_embedding_provider
        
        # Mock Neo4j client
        mock_neo4j_client = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client
        
        # Mock vector search results with invalid label
        mock_neo4j_client.execute_read_query.return_value = [
            {
                'id': 'label:InvalidLabel',
                'term': 'InvalidLabel',
                'type': 'label',
                'canonical_id': 'InvalidLabel',
                'score': 0.85
            }
        ]
        
        # Mock CypherGenerator to reject the label
        mock_cypher_generator = MagicMock()
        mock_cypher_generator.validate_label.return_value = False
        mock_cypher_generator_class.return_value = mock_cypher_generator
        
        # Test semantic mapping
        result = _find_best_anchor_entity_semantic("SomeEntity")
        
        # Verify result is None since label is invalid
        self.assertIsNone(result)
        
        # Verify label validation was attempted
        mock_cypher_generator.validate_label.assert_called_once_with("InvalidLabel")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "mock_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"})
    @patch("graph_rag.planner.call_llm_structured")
    @patch("graph_rag.planner._find_best_anchor_entity_semantic")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_plan_with_semantic_fallback(self, mock_file_open, mock_semantic_mapping, mock_call_llm_structured):
        """Test that generate_plan uses semantic fallback when LLM entity extraction succeeds."""
        
        # Mock config.yaml
        config_data = """
        llm:
          model: gemini-2.0-flash-exp
          planner_model: gemini-2.0-flash-exp
          planner_max_tokens: 256
        guardrails:
          neo4j_timeout: 10
        schema_embeddings:
          index_name: schema_embeddings
          top_k: 5
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock LLM planner to fail, triggering fallback
        from graph_rag.llm_client import LLMStructuredError
        
        # First call (planner) fails, second call (entity extraction) succeeds
        mock_call_llm_structured.side_effect = [
            LLMStructuredError("Planner failed"),  # Planner call fails
            MagicMock(names=["Apple Inc."])        # Entity extraction succeeds
        ]
        
        # Mock semantic mapping to return a valid label
        mock_semantic_mapping.return_value = "Organization"
        
        # Test plan generation
        plan = generate_plan("Tell me about Apple Inc.")
        
        # Verify plan was generated with semantic mapping
        self.assertEqual(plan.anchor_entity, "Organization")
        self.assertEqual(plan.intent, "general_rag_query")  # Default fallback intent
        self.assertEqual(plan.question, "Tell me about Apple Inc.")
        
        # Verify semantic mapping was called with extracted entity
        mock_semantic_mapping.assert_called_once_with("Apple Inc.")
        
        # Verify LLM was called twice (planner + entity extraction)
        self.assertEqual(mock_call_llm_structured.call_count, 2)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "mock_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"})
    @patch("graph_rag.planner.call_llm_structured")
    @patch("graph_rag.planner._find_best_anchor_entity_semantic")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_plan_semantic_fallback_no_mapping(self, mock_file_open, mock_semantic_mapping, mock_call_llm_structured):
        """Test that generate_plan falls back to original entity when semantic mapping fails."""
        
        # Mock config.yaml
        config_data = """
        llm:
          model: gemini-2.0-flash-exp
          planner_model: gemini-2.0-flash-exp
          planner_max_tokens: 256
        guardrails:
          neo4j_timeout: 10
        schema_embeddings:
          index_name: schema_embeddings
          top_k: 5
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock LLM planner to fail, triggering fallback
        from graph_rag.llm_client import LLMStructuredError
        
        # First call (planner) fails, second call (entity extraction) succeeds
        mock_call_llm_structured.side_effect = [
            LLMStructuredError("Planner failed"),  # Planner call fails
            MagicMock(names=["Unknown Entity"])    # Entity extraction succeeds
        ]
        
        # Mock semantic mapping to return None (no mapping found)
        mock_semantic_mapping.return_value = None
        
        # Test plan generation
        plan = generate_plan("Tell me about Unknown Entity")
        
        # Verify plan uses original entity when semantic mapping fails
        self.assertEqual(plan.anchor_entity, "Unknown Entity")
        self.assertEqual(plan.intent, "general_rag_query")
        
        # Verify semantic mapping was attempted
        mock_semantic_mapping.assert_called_once_with("Unknown Entity")

    def test_find_best_anchor_entity_semantic_empty_candidate(self):
        """Test semantic mapping with empty or None candidate."""
        
        # Test with None
        result = _find_best_anchor_entity_semantic(None)
        self.assertIsNone(result)
        
        # Test with empty string
        result = _find_best_anchor_entity_semantic("")
        self.assertIsNone(result)
        
        # Test with whitespace only
        result = _find_best_anchor_entity_semantic("   ")
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
