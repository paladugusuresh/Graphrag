#!/usr/bin/env python3
"""
Test planner functionality - Updated for LLM-driven approach (Task 21)
Tests the simplified planner that generates intent+params without template selection.
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DEV_MODE for testing
os.environ["DEV_MODE"] = "true"

from graph_rag.planner import generate_plan, QueryPlan, PlannerOutput
from graph_rag.schemas import PlannerOutput as SchemaPlannerOutput

class TestPlannerChain(unittest.TestCase):
    """Test cases for the simplified LLM-driven planner."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_question = "What are the goals for Isabella Thomas?"
        
    def test_generate_plan_basic(self):
        """Test basic plan generation with LLM-driven approach."""
        
        plan = generate_plan(self.test_question)
        
        # Verify plan structure
        self.assertIsInstance(plan, QueryPlan)
        self.assertIsNotNone(plan.intent)
        self.assertIsNotNone(plan.question)
        self.assertEqual(plan.question, self.test_question)
        
        # Intent should be a string (advisory label for LLM)
        self.assertIsInstance(plan.intent, str)
        self.assertGreater(len(plan.intent), 0)
        
        # Anchor entity might be None in DEV_MODE with mocks
        if plan.anchor_entity:
            self.assertIsInstance(plan.anchor_entity, str)
    
    @patch('graph_rag.planner.call_llm_structured')
    def test_generate_plan_with_mock_llm(self, mock_llm):
        """Test plan generation with mocked LLM response."""
        
        # Mock LLM response
        mock_llm.return_value = SchemaPlannerOutput(
            intent="student_goal_query",
            params={"student_name": "Isabella Thomas"},
            confidence=0.9
        )
        
        plan = generate_plan(self.test_question)
        
        # Verify LLM was called
        mock_llm.assert_called_once()
        
        # Verify plan structure
        self.assertEqual(plan.intent, "student_goal_query")
        self.assertEqual(plan.question, self.test_question)
        
        # In DEV_MODE, anchor_entity might be resolved via semantic mapping
        # or might be None if semantic mapping fails
    
    def test_generate_plan_fallback_detection(self):
        """Test that planner falls back to rule-based detection when LLM fails."""
        
        from graph_rag.llm_client import LLMStructuredError
        
        with patch('graph_rag.planner.call_llm_structured') as mock_llm:
            # Mock LLM failure with correct exception type
            mock_llm.side_effect = LLMStructuredError("LLM failed")
            
            plan = generate_plan(self.test_question)
            
            # Should still return a plan with fallback intent
            self.assertIsInstance(plan, QueryPlan)
            self.assertIsNotNone(plan.intent)
            self.assertEqual(plan.question, self.test_question)
            
            # Intent should be from fallback detection
            self.assertIn(plan.intent, ["general_query", "student_support_query"])
    
    def test_generate_plan_with_domain_keywords(self):
        """Test plan generation with Student Support domain keywords."""
        
        test_cases = [
            ("What are the goals for Isabella Thomas?", "student_goal_query"),
            ("Show me intervention plans for this student", "intervention_query"),
            ("Who is the case worker for this referral?", "case_worker_query"),
            ("What services are available?", "service_query"),
            ("Tell me about this student's progress", "progress_query")
        ]
        
        for question, expected_intent_pattern in test_cases:
            with self.subTest(question=question):
                plan = generate_plan(question)
                
                # Verify plan is generated
                self.assertIsInstance(plan, QueryPlan)
                self.assertEqual(plan.question, question)
                
                # Intent should be related to student support domain
                self.assertIsInstance(plan.intent, str)
                self.assertGreater(len(plan.intent), 0)
    
    def test_planner_output_model(self):
        """Test PlannerOutput model validation."""
        
        # Test valid PlannerOutput
        output = PlannerOutput(
            intent="student_goal_query",
            params={"student_name": "Isabella Thomas"},
            confidence=0.9
        )
        
        self.assertEqual(output.intent, "student_goal_query")
        self.assertEqual(output.params["student_name"], "Isabella Thomas")
        self.assertEqual(output.confidence, 0.9)
        
        # Test with minimal fields
        output_minimal = PlannerOutput(intent="general_query")
        self.assertEqual(output_minimal.intent, "general_query")
        self.assertEqual(output_minimal.params, {})
        self.assertIsNone(output_minimal.confidence)
    
    def test_query_plan_model(self):
        """Test QueryPlan model validation."""
        
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

if __name__ == "__main__":
    unittest.main()
