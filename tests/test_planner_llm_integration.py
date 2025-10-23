import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json
from pydantic import BaseModel
from prometheus_client import REGISTRY

# Global patches for module-level imports
@patch("graph_rag.llm_client._get_redis_client") # Patch the lazy getter function
@patch("graph_rag.neo4j_client.GraphDatabase")
@patch("graph_rag.cypher_generator.CypherGenerator")
class TestPlannerLLMIntegration(unittest.TestCase):

    def setUp(self):
        # Clear module caches to ensure fresh imports
        if 'graph_rag.planner' in sys.modules:
            del sys.modules['graph_rag.planner']
        if 'graph_rag.llm_client' in sys.modules:
            del sys.modules['graph_rag.llm_client']
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("graph_rag.planner.call_llm_structured") # Patch where it's used in planner
    @patch("graph_rag.planner.logger")
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gemini-2.0-flash-exp",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        },
        "schema": {"allow_list_path": "allow_list.json"}
    }))
    def test_generate_plan_with_llm_entities(self, mock_open, mock_logger, mock_call_llm_structured_planner, mock_cypher_generator_class, mock_graph_database_class, mock_get_redis_client):
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

        mock_call_llm_structured_planner.return_value = MagicMock(names=["Alice", "Bob"])
        import graph_rag.planner
        plan = graph_rag.planner.generate_plan("Who founded Microsoft?")
        self.assertEqual(plan.intent, "company_founder_query")
        self.assertEqual(plan.anchor_entity, "Alice")
        self.assertEqual(plan.question, "Who founded Microsoft?")
        mock_logger.warning.assert_not_called()

    @patch("graph_rag.planner.call_llm_structured") # Patch where it's used in planner
    @patch("graph_rag.planner.logger")
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gemini-2.0-flash-exp",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        },
        "schema": {"allow_list_path": "allow_list.json"}
    }))
    def test_generate_plan_llm_error_fallback(self, mock_open, mock_logger, mock_call_llm_structured_planner, mock_cypher_generator_class, mock_graph_database_class, mock_get_redis_client):
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

        from graph_rag.llm_client import LLMStructuredError
        mock_call_llm_structured_planner.side_effect = LLMStructuredError("LLM failed")
        import graph_rag.planner
        plan = graph_rag.planner.generate_plan("Who founded Microsoft?")
        self.assertEqual(plan.intent, "company_founder_query")
        self.assertIsNone(plan.anchor_entity)
        self.assertEqual(plan.question, "Who founded Microsoft?")
        mock_logger.warning.assert_called_once_with("LLM entity extraction failed: LLM failed. Falling back to empty entities.")
