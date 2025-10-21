#!/usr/bin/env python3
"""
Test planner LLM functionality - Updated for LLM-driven approach (Task 21)
Tests the simplified planner models and LLM integration.
"""
import sys
import os
import unittest
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DEV_MODE for testing
os.environ["DEV_MODE"] = "true"

from graph_rag.planner import PlannerOutput, QueryPlan, generate_plan

class TestPlannerLLMSimple(unittest.TestCase):
    """Test cases for planner LLM integration and models."""

    def test_planner_output_model_creation(self):
        """Test that PlannerOutput model can be created with all fields."""
        
        output = PlannerOutput(
            intent="student_goal_query",
            params={"student_name": "Isabella Thomas", "goal_type": "academic"},
            confidence=0.95
        )
        
        self.assertEqual(output.intent, "student_goal_query")
        self.assertEqual(output.params["student_name"], "Isabella Thomas")
        self.assertEqual(output.params["goal_type"], "academic")
        self.assertEqual(output.confidence, 0.95)

    def test_planner_output_model_minimal(self):
        """Test that PlannerOutput model works with minimal fields."""
        
        output = PlannerOutput(intent="general_query")
        
        self.assertEqual(output.intent, "general_query")
        self.assertEqual(output.params, {})
        self.assertIsNone(output.confidence)

    def test_planner_output_model_serialization(self):
        """Test that PlannerOutput can be serialized to dict."""
        
        output = PlannerOutput(
            intent="intervention_query",
            params={"student_id": "123", "intervention_type": "behavioral"},
            confidence=0.8
        )
        
        output_dict = output.model_dump()
        
        self.assertEqual(output_dict["intent"], "intervention_query")
        self.assertEqual(output_dict["params"]["student_id"], "123")
        self.assertEqual(output_dict["confidence"], 0.8)
    
    def test_planner_output_model_validation(self):
        """Test that PlannerOutput validates input correctly."""
        
        # Test valid input
        output = PlannerOutput(
            intent="case_worker_query",
            params={"referral_id": "456"},
            confidence=0.7
        )
        
        self.assertEqual(output.intent, "case_worker_query")
        self.assertEqual(output.params["referral_id"], "456")
        self.assertEqual(output.confidence, 0.7)
        
        # Test with None confidence
        output_none = PlannerOutput(
            intent="service_query",
            params={"service_type": "therapy"}
        )
        
        self.assertEqual(output_none.intent, "service_query")
        self.assertIsNone(output_none.confidence)
    
    def test_query_plan_model(self):
        """Test QueryPlan model functionality."""
        
        # Test complete QueryPlan
        plan = QueryPlan(
            intent="student_goal_query",
            anchor_entity="Student",
            question="What are the goals for Isabella Thomas?"
        )
        
        self.assertEqual(plan.intent, "student_goal_query")
        self.assertEqual(plan.anchor_entity, "Student")
        self.assertEqual(plan.question, "What are the goals for Isabella Thomas?")
        
        # Test with minimal fields
        plan_minimal = QueryPlan(
            intent="general_query",
            question="Tell me about students"
        )
        
        self.assertEqual(plan_minimal.intent, "general_query")
        self.assertIsNone(plan_minimal.anchor_entity)
        self.assertEqual(plan_minimal.question, "Tell me about students")
    
    @patch('graph_rag.planner.call_llm_structured')
    def test_generate_plan_with_mock_llm(self, mock_llm):
        """Test generate_plan with mocked LLM response."""
        
        from graph_rag.schemas import PlannerOutput as SchemaPlannerOutput
        
        # Mock LLM response
        mock_llm.return_value = SchemaPlannerOutput(
            intent="student_goal_query",
            params={"student_name": "Isabella Thomas"},
            confidence=0.9
        )
        
        plan = generate_plan("What are the goals for Isabella Thomas?")
        
        # Verify LLM was called
        mock_llm.assert_called_once()
        
        # Verify plan structure
        self.assertIsInstance(plan, QueryPlan)
        self.assertEqual(plan.intent, "student_goal_query")
        self.assertEqual(plan.question, "What are the goals for Isabella Thomas?")
    
    def test_generate_plan_fallback(self):
        """Test generate_plan fallback when LLM fails."""
        
        from graph_rag.llm_client import LLMStructuredError
        
        with patch('graph_rag.planner.call_llm_structured') as mock_llm:
            # Mock LLM failure with correct exception type
            mock_llm.side_effect = LLMStructuredError("LLM failed")
            
            plan = generate_plan("What are the goals for Isabella Thomas?")
            
            # Should still return a plan with fallback intent
            self.assertIsInstance(plan, QueryPlan)
            self.assertIsNotNone(plan.intent)
            self.assertEqual(plan.question, "What are the goals for Isabella Thomas?")
            
            # Intent should be from fallback detection
            self.assertIn(plan.intent, ["general_query", "student_support_query"])

if __name__ == "__main__":
    unittest.main()
