import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from prometheus_client import REGISTRY

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.planner import PlannerOutput, QueryPlan, generate_plan, _validate_and_build_chain

class TestPlannerChain(unittest.TestCase):

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

    def test_query_plan_with_chain(self):
        """Test that QueryPlan model can include chain field."""
        
        chain = [
            {"intent": "company_founder_query", "params": {"company": "Microsoft", "anchor": "Microsoft"}},
            {"intent": "general_rag_query", "params": {"entity": "Microsoft", "anchor": "Microsoft"}}
        ]
        
        plan = QueryPlan(
            intent="company_founder_query",
            anchor_entity="Microsoft",
            question="Who founded Microsoft and what are their other ventures?",
            chain=chain
        )
        
        self.assertEqual(plan.intent, "company_founder_query")
        self.assertEqual(plan.anchor_entity, "Microsoft")
        self.assertEqual(plan.chain, chain)
        self.assertEqual(len(plan.chain), 2)
        self.assertEqual(plan.chain[0]["intent"], "company_founder_query")
        self.assertEqual(plan.chain[1]["intent"], "general_rag_query")

    def test_query_plan_without_chain(self):
        """Test that QueryPlan works without chain (backward compatibility)."""
        
        plan = QueryPlan(
            intent="general_rag_query",
            anchor_entity="Apple",
            question="Tell me about Apple"
        )
        
        self.assertEqual(plan.intent, "general_rag_query")
        self.assertEqual(plan.anchor_entity, "Apple")
        self.assertIsNone(plan.chain)

    @patch("graph_rag.cypher_generator.CYPHER_TEMPLATES", {
        "general_rag_query": {"schema_requirements": {"labels": ["__Entity__"], "relationships": []}},
        "company_founder_query": {"schema_requirements": {"labels": ["Person", "Organization"], "relationships": ["FOUNDED"]}},
        "company_product_query": {"schema_requirements": {"labels": ["Organization", "Product"], "relationships": ["HAS_PRODUCT"]}}
    })
    def test_validate_and_build_chain_valid_templates(self):
        """Test chain validation with valid template names."""
        
        chain_template_names = ["company_founder_query", "general_rag_query"]
        base_params = {"company": "Microsoft"}
        anchor_entity = "Microsoft"
        
        result = _validate_and_build_chain(chain_template_names, base_params, anchor_entity)
        
        self.assertEqual(len(result), 2)
        
        # Check first step
        self.assertEqual(result[0]["intent"], "company_founder_query")
        self.assertEqual(result[0]["params"]["company"], "Microsoft")
        self.assertEqual(result[0]["params"]["anchor"], "Microsoft")
        
        # Check second step
        self.assertEqual(result[1]["intent"], "general_rag_query")
        self.assertEqual(result[1]["params"]["company"], "Microsoft")
        self.assertEqual(result[1]["params"]["anchor"], "Microsoft")

    @patch("graph_rag.cypher_generator.CYPHER_TEMPLATES", {
        "general_rag_query": {"schema_requirements": {"labels": ["__Entity__"], "relationships": []}},
        "company_founder_query": {"schema_requirements": {"labels": ["Person", "Organization"], "relationships": ["FOUNDED"]}}
    })
    def test_validate_and_build_chain_invalid_template(self):
        """Test chain validation with some invalid template names."""
        
        chain_template_names = ["company_founder_query", "invalid_template", "general_rag_query"]
        base_params = {"company": "Apple"}
        anchor_entity = "Apple"
        
        result = _validate_and_build_chain(chain_template_names, base_params, anchor_entity)
        
        # Should skip the invalid template
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["intent"], "company_founder_query")
        self.assertEqual(result[1]["intent"], "general_rag_query")

    @patch("graph_rag.cypher_generator.CYPHER_TEMPLATES", {
        "general_rag_query": {"schema_requirements": {"labels": ["__Entity__"], "relationships": []}},
        "company_founder_query": {"schema_requirements": {"labels": ["Person", "Organization"], "relationships": ["FOUNDED"]}}
    })
    def test_validate_and_build_chain_empty_chain(self):
        """Test chain validation with empty chain."""
        
        result = _validate_and_build_chain([], {}, None)
        self.assertEqual(len(result), 0)

    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(os.environ, {"OPENAI_API_KEY": "mock_openai_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}, clear=True)
    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_structured")
    @patch("graph_rag.llm_client.consume_token")
    def test_generate_plan_with_chain(self, mock_consume_token, mock_call_llm_structured, mock_get_redis_client, mock_file_open):
        """Test generate_plan with LLM returning a chain."""
        
        # Configure mock files
        mock_file_open.side_effect = [
            # config.yaml
            mock_open(read_data=json.dumps({
                "schema": {"allow_list_path": "allow_list.json"},
                "llm": {
                    "model": "gpt-4o",
                    "max_tokens": 512,
                    "rate_limit_per_minute": 60,
                    "redis_url": "redis://localhost:6379/0",
                    "planner_model": "gpt-4o",
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

        # Configure mocks
        mock_consume_token.return_value = True
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance

        # Mock LLM structured call to return PlannerOutput with chain
        mock_planner_output = PlannerOutput(
            intent="company_founder_query",
            params={"company": "Microsoft", "anchor": "Microsoft"},
            confidence=0.90,
            chain=["company_founder_query", "general_rag_query"]  # Chain of templates
        )
        mock_call_llm_structured.return_value = mock_planner_output

        # Test the planner
        question = "Who founded Microsoft and what are their other business relationships?"
        result = generate_plan(question)

        # Verify result
        self.assertIsInstance(result, QueryPlan)
        self.assertEqual(result.intent, "company_founder_query")
        self.assertEqual(result.anchor_entity, "Microsoft")
        self.assertEqual(result.question, question)
        
        # Verify chain
        self.assertIsNotNone(result.chain)
        self.assertEqual(len(result.chain), 2)
        
        # Check first chain step
        self.assertEqual(result.chain[0]["intent"], "company_founder_query")
        self.assertEqual(result.chain[0]["params"]["company"], "Microsoft")
        self.assertEqual(result.chain[0]["params"]["anchor"], "Microsoft")
        
        # Check second chain step
        self.assertEqual(result.chain[1]["intent"], "general_rag_query")
        self.assertEqual(result.chain[1]["params"]["company"], "Microsoft")
        self.assertEqual(result.chain[1]["params"]["anchor"], "Microsoft")

    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(os.environ, {"OPENAI_API_KEY": "mock_openai_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}, clear=True)
    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_structured")
    @patch("graph_rag.llm_client.consume_token")
    def test_generate_plan_without_chain(self, mock_consume_token, mock_call_llm_structured, mock_get_redis_client, mock_file_open):
        """Test generate_plan with LLM returning no chain (single template)."""
        
        # Configure mock files
        mock_file_open.side_effect = [
            # config.yaml
            mock_open(read_data=json.dumps({
                "schema": {"allow_list_path": "allow_list.json"},
                "llm": {
                    "model": "gpt-4o",
                    "max_tokens": 512,
                    "rate_limit_per_minute": 60,
                    "redis_url": "redis://localhost:6379/0",
                    "planner_model": "gpt-4o",
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

        # Configure mocks
        mock_consume_token.return_value = True
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance

        # Mock LLM structured call to return PlannerOutput without chain
        mock_planner_output = PlannerOutput(
            intent="general_rag_query",
            params={"entity": "Apple", "anchor": "Apple"},
            confidence=0.85,
            chain=None  # No chain
        )
        mock_call_llm_structured.return_value = mock_planner_output

        # Test the planner
        question = "Tell me about Apple"
        result = generate_plan(question)

        # Verify result
        self.assertIsInstance(result, QueryPlan)
        self.assertEqual(result.intent, "general_rag_query")
        self.assertEqual(result.anchor_entity, "Apple")
        self.assertEqual(result.question, question)
        self.assertIsNone(result.chain)  # No chain should be present

if __name__ == '__main__':
    unittest.main()
