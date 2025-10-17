import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.planner import PlannerOutput

class TestPlannerLLMSimple(unittest.TestCase):

    def test_planner_output_model_creation(self):
        """Test that PlannerOutput model can be created and works correctly."""
        
        # Test creating a PlannerOutput with all fields
        output = PlannerOutput(
            intent="company_founder_query",
            params={"company": "Microsoft", "anchor": "Microsoft"},
            confidence=0.95,
            chain=["company_founder_query", "general_rag_query"]
        )
        
        self.assertEqual(output.intent, "company_founder_query")
        self.assertEqual(output.params["company"], "Microsoft")
        self.assertEqual(output.params["anchor"], "Microsoft")
        self.assertEqual(output.confidence, 0.95)
        self.assertEqual(output.chain, ["company_founder_query", "general_rag_query"])

    def test_planner_output_model_minimal(self):
        """Test creating a PlannerOutput with minimal fields."""
        minimal_output = PlannerOutput(intent="general_rag_query")
        
        self.assertEqual(minimal_output.intent, "general_rag_query")
        self.assertEqual(minimal_output.params, {})
        self.assertIsNone(minimal_output.confidence)
        self.assertIsNone(minimal_output.chain)

    def test_planner_output_model_serialization(self):
        """Test that PlannerOutput can be serialized to dict."""
        output = PlannerOutput(
            intent="company_founder_query",
            params={"entity": "Apple"},
            confidence=0.85
        )
        
        output_dict = output.model_dump()
        self.assertEqual(output_dict["intent"], "company_founder_query")
        self.assertEqual(output_dict["params"]["entity"], "Apple")
        self.assertEqual(output_dict["confidence"], 0.85)
        self.assertIsNone(output_dict["chain"])

    @patch.dict(os.environ, {"GEMINI_API_KEY": "mock_key"})
    def test_template_summary_building(self):
        """Test that template summary can be built."""
        from graph_rag.planner import _build_template_summary
        
        # Mock the CypherGenerator and CYPHER_TEMPLATES from the correct module
        with patch("graph_rag.planner.CypherGenerator") as mock_cypher_gen:
            with patch("graph_rag.cypher_generator.CYPHER_TEMPLATES", {
                "general_rag_query": {
                    "schema_requirements": {"labels": ["__Entity__"], "relationships": []}
                },
                "company_founder_query": {
                    "schema_requirements": {"labels": ["Person", "Organization"], "relationships": ["FOUNDED"]}
                }
            }):
                summary = _build_template_summary()
                
                # Verify summary contains expected templates
                self.assertIn("general_rag_query", summary)
                self.assertIn("company_founder_query", summary)
                self.assertIn("General purpose query", summary)
                self.assertIn("Find who founded", summary)
                self.assertIn("labels: ['Person', 'Organization']", summary)
                self.assertIn("relationships: ['FOUNDED']", summary)

if __name__ == '__main__':
    unittest.main()
