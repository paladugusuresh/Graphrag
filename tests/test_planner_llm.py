import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from prometheus_client import REGISTRY

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.planner import PlannerOutput, QueryPlan, generate_plan

class TestPlannerLLM(unittest.TestCase):

    def setUp(self):
        # Clear module cache and Prometheus registry
        for module_name in [
            'graph_rag.planner', 'graph_rag.llm_client', 'graph_rag.cypher_generator',
            'graph_rag.neo4j_client', 'graph_rag.embeddings', 'graph_rag.audit_store'
        ]:
            if module_name in sys.modules:
                del sys.modules[module_name]
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(os.environ, {"GEMINI_API_KEY": "mock_gemini_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}, clear=True)
    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_structured")
    def test_llm_planner_company_founder_query(self, mock_call_llm_structured, mock_get_redis_client, mock_file_open):
        """Test LLM-driven planner for company founder question."""
        
        # Configure mock files
        mock_file_open.side_effect = [
            # config.yaml
            mock_open(read_data=json.dumps({
                "schema": {"allow_list_path": "allow_list.json"},
                "llm": {
                    "model": "gemini-2.0-flash-exp",
                    "max_tokens": 512,
                    "rate_limit_per_minute": 60,
                    "redis_url": "redis://localhost:6379/0",
                    "planner_model": "gemini-2.0-flash-exp",
                    "planner_max_tokens": 256
                }
            })).return_value,
            # allow_list.json
            mock_open(read_data=json.dumps({
                "node_labels": ["Person", "Organization", "__Entity__"],
                "relationship_types": ["FOUNDED", "HAS_CHUNK", "MENTIONS"],
                "properties": {}
            })).return_value,
        ]

        # Configure Redis mock
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance
        mock_redis_instance.eval.return_value = 1

        # Mock LLM structured call to return PlannerOutput
        mock_planner_output = PlannerOutput(
            intent="company_founder_query",
            params={"company": "Microsoft", "anchor": "Microsoft"},
            confidence=0.95,
            chain=None
        )
        mock_call_llm_structured.return_value = mock_planner_output

        # Test the planner
        question = "Who founded Microsoft?"
        result = generate_plan(question)

        # Verify result
        self.assertIsInstance(result, QueryPlan)
        self.assertEqual(result.intent, "company_founder_query")
        self.assertEqual(result.anchor_entity, "Microsoft")
        self.assertEqual(result.question, question)

        # Verify LLM was called with correct parameters
        mock_call_llm_structured.assert_called_once()
        call_args = mock_call_llm_structured.call_args
        self.assertEqual(call_args[1]["schema_model"], PlannerOutput)
        self.assertEqual(call_args[1]["model"], "gemini-2.0-flash-exp")
        self.assertEqual(call_args[1]["max_tokens"], 256)
        
        # Verify prompt contains template information
        prompt = call_args[1]["prompt"]
        self.assertIn("Available Templates:", prompt)
        self.assertIn("company_founder_query", prompt)
        self.assertIn("general_rag_query", prompt)
        self.assertIn(question, prompt)

    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(os.environ, {"GEMINI_API_KEY": "mock_gemini_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}, clear=True)
    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_structured")
    def test_llm_planner_general_query(self, mock_call_llm_structured, mock_get_redis_client, mock_file_open):
        """Test LLM-driven planner for general question."""
        
        # Configure mock files
        mock_file_open.side_effect = [
            # config.yaml
            mock_open(read_data=json.dumps({
                "schema": {"allow_list_path": "allow_list.json"},
                "llm": {
                    "model": "gemini-2.0-flash-exp",
                    "max_tokens": 512,
                    "rate_limit_per_minute": 60,
                    "redis_url": "redis://localhost:6379/0",
                    "planner_model": "gemini-2.0-flash-exp",
                    "planner_max_tokens": 256
                }
            })).return_value,
            # allow_list.json
            mock_open(read_data=json.dumps({
                "node_labels": ["Person", "Organization", "__Entity__"],
                "relationship_types": ["FOUNDED", "HAS_CHUNK", "MENTIONS"],
                "properties": {}
            })).return_value,
        ]

        # Configure Redis mock
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance
        mock_redis_instance.eval.return_value = 1

        # Mock LLM structured call to return PlannerOutput for general query
        mock_planner_output = PlannerOutput(
            intent="general_rag_query",
            params={"entity": "Apple", "anchor": "Apple"},
            confidence=0.85,
            chain=None
        )
        mock_call_llm_structured.return_value = mock_planner_output

        # Test the planner
        question = "Tell me about Apple's business relationships"
        result = generate_plan(question)

        # Verify result
        self.assertIsInstance(result, QueryPlan)
        self.assertEqual(result.intent, "general_rag_query")
        self.assertEqual(result.anchor_entity, "Apple")
        self.assertEqual(result.question, question)

    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(os.environ, {"GEMINI_API_KEY": "mock_gemini_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}, clear=True)
    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_structured")
    def test_llm_planner_invalid_intent_fallback(self, mock_call_llm_structured, mock_get_redis_client, mock_file_open):
        """Test that invalid intent from LLM falls back to general_rag_query."""
        
        # Configure mock files
        mock_file_open.side_effect = [
            # config.yaml
            mock_open(read_data=json.dumps({
                "schema": {"allow_list_path": "allow_list.json"},
                "llm": {
                    "model": "gemini-2.0-flash-exp",
                    "max_tokens": 512,
                    "rate_limit_per_minute": 60,
                    "redis_url": "redis://localhost:6379/0",
                    "planner_model": "gemini-2.0-flash-exp",
                    "planner_max_tokens": 256
                }
            })).return_value,
            # allow_list.json
            mock_open(read_data=json.dumps({
                "node_labels": ["Person", "Organization", "__Entity__"],
                "relationship_types": ["FOUNDED", "HAS_CHUNK", "MENTIONS"],
                "properties": {}
            })).return_value,
        ]

        # Configure Redis mock
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance
        mock_redis_instance.eval.return_value = 1

        # Mock LLM structured call to return invalid intent
        mock_planner_output = PlannerOutput(
            intent="invalid_template_name",
            params={"company": "Tesla"},
            confidence=0.90,
            chain=None
        )
        mock_call_llm_structured.return_value = mock_planner_output

        # Test the planner
        question = "What about Tesla?"
        result = generate_plan(question)

        # Verify result - should fallback to general_rag_query
        self.assertIsInstance(result, QueryPlan)
        self.assertEqual(result.intent, "general_rag_query")  # Should be corrected
        self.assertEqual(result.question, question)

    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(os.environ, {"GEMINI_API_KEY": "mock_gemini_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}, clear=True)
    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_structured")
    def test_llm_planner_fallback_on_error(self, mock_call_llm_structured, mock_get_redis_client, mock_file_open):
        """Test that LLM errors fall back to rule-based detection."""
        
        # Configure mock files
        mock_file_open.side_effect = [
            # config.yaml
            mock_open(read_data=json.dumps({
                "schema": {"allow_list_path": "allow_list.json"},
                "llm": {
                    "model": "gemini-2.0-flash-exp",
                    "max_tokens": 512,
                    "rate_limit_per_minute": 60,
                    "redis_url": "redis://localhost:6379/0",
                    "planner_model": "gemini-2.0-flash-exp",
                    "planner_max_tokens": 256
                }
            })).return_value,
            # allow_list.json
            mock_open(read_data=json.dumps({
                "node_labels": ["Person", "Organization", "__Entity__"],
                "relationship_types": ["FOUNDED", "HAS_CHUNK", "MENTIONS"],
                "properties": {}
            })).return_value,
        ]

        # Configure Redis mock
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance
        mock_redis_instance.eval.return_value = 1

        # Mock LLM structured call to raise an error
        from graph_rag.llm_client import LLMStructuredError
        mock_call_llm_structured.side_effect = LLMStructuredError("LLM failed")

        # Test the planner with a founder question (should use rule-based fallback)
        question = "Who founded Google?"
        result = generate_plan(question)

        # Verify result - should use rule-based fallback
        self.assertIsInstance(result, QueryPlan)
        self.assertEqual(result.intent, "company_founder_query")  # Rule-based detection
        self.assertEqual(result.question, question)

    def test_planner_output_model(self):
        """Test that PlannerOutput model works correctly."""
        
        # Test creating a PlannerOutput with all fields
        output = PlannerOutput(
            intent="company_founder_query",
            params={"company": "Microsoft", "anchor": "Microsoft"},
            confidence=0.95,
            chain=["company_founder_query", "general_rag_query"]
        )
        
        self.assertEqual(output.intent, "company_founder_query")
        self.assertEqual(output.params["company"], "Microsoft")
        self.assertEqual(output.confidence, 0.95)
        self.assertEqual(output.chain, ["company_founder_query", "general_rag_query"])

        # Test creating a PlannerOutput with minimal fields
        minimal_output = PlannerOutput(intent="general_rag_query")
        self.assertEqual(minimal_output.intent, "general_rag_query")
        self.assertEqual(minimal_output.params, {})
        self.assertIsNone(minimal_output.confidence)
        self.assertIsNone(minimal_output.chain)

if __name__ == '__main__':
    unittest.main()
