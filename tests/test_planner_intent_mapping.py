# tests/test_planner_intent_mapping.py
import unittest
from unittest.mock import patch, MagicMock

from graph_rag.planner import _map_question_to_template_intent, generate_plan, QueryPlan


class TestIntentMapping(unittest.TestCase):
    """Test rule-based intent mapping functionality."""
    
    def test_map_goals_for_student(self):
        """Test mapping questions about goals for students."""
        test_cases = [
            "What are the goals for Isabella Thomas?",
            "Show me the goals for John Smith",
            "List all goals for Maria Garcia",
            "What goals does Sarah Johnson have?",
            "Goals for Michael Brown please"
        ]
        
        for question in test_cases:
            with self.subTest(question=question):
                result = _map_question_to_template_intent(question)
                self.assertEqual(result, "goals_for_student")
    
    def test_map_accommodations_for_student(self):
        """Test mapping questions about accommodations for students."""
        test_cases = [
            "What accommodations are available for Isabella Thomas?",
            "Show me the accommodations for John Smith",
            "List all accommodations for Maria Garcia",
            "What accommodation does Sarah Johnson have?",
            "Accommodations for Michael Brown please"
        ]
        
        for question in test_cases:
            with self.subTest(question=question):
                result = _map_question_to_template_intent(question)
                self.assertEqual(result, "accommodations_for_student")
    
    def test_map_case_manager_for_student(self):
        """Test mapping questions about case managers for students."""
        test_cases = [
            "Who is the case manager for Isabella Thomas?",
            "Show me the case manager for John Smith",
            "What case manager does Maria Garcia have?",
            "Case manager for Sarah Johnson",
            "Who manages Michael Brown's case?"
        ]
        
        for question in test_cases:
            with self.subTest(question=question):
                result = _map_question_to_template_intent(question)
                self.assertEqual(result, "case_manager_for_student")
    
    def test_map_eval_reports_for_student_with_date_range(self):
        """Test mapping questions about evaluation reports with date ranges."""
        test_cases = [
            "What evaluation reports exist for Isabella Thomas between 2024-01-01 and 2024-12-31?",
            "Show me evaluation reports for John Smith since January 2024",
            "List evaluation reports for Maria Garcia from 2024-01-01 to 2024-06-30",
            "What evaluation reports does Sarah Johnson have between March and June?",
            "Evaluation reports for Michael Brown since last year"
        ]
        
        for question in test_cases:
            with self.subTest(question=question):
                result = _map_question_to_template_intent(question)
                self.assertEqual(result, "eval_reports_for_student_in_range")
    
    def test_map_concern_areas_for_student(self):
        """Test mapping questions about concern areas for students."""
        test_cases = [
            "What are the concern areas for Isabella Thomas?",
            "Show me the concern areas for John Smith",
            "List all concern areas for Maria Garcia",
            "What concern areas does Sarah Johnson have?",
            "Concern areas for Michael Brown please"
        ]
        
        for question in test_cases:
            with self.subTest(question=question):
                result = _map_question_to_template_intent(question)
                self.assertEqual(result, "concern_areas_for_student")
    
    def test_no_template_intent_matched(self):
        """Test that unrelated questions don't match any template intent."""
        test_cases = [
            "What is the weather today?",
            "How many students are in the school?",
            "Show me all intervention plans",
            "What are the general statistics?",
            "List all staff members",
            "How do I create a new goal?",
            "What is the school's policy on accommodations?",
            "Tell me about the evaluation process"
        ]
        
        for question in test_cases:
            with self.subTest(question=question):
                result = _map_question_to_template_intent(question)
                self.assertIsNone(result)
    
    def test_edge_cases(self):
        """Test edge cases for intent mapping."""
        # Empty or invalid input
        self.assertIsNone(_map_question_to_template_intent(""))
        self.assertIsNone(_map_question_to_template_intent(None))
        self.assertIsNone(_map_question_to_template_intent(123))
        
        # Case insensitive matching
        self.assertEqual(_map_question_to_template_intent("GOALS FOR JOHN DOE"), "goals_for_student")
        self.assertEqual(_map_question_to_template_intent("Case Manager For Jane Smith"), "case_manager_for_student")
        
        # Partial matches (should not match)
        self.assertIsNone(_map_question_to_template_intent("goal"))
        self.assertIsNone(_map_question_to_template_intent("accommodation"))
        self.assertIsNone(_map_question_to_template_intent("case"))
    
    def test_eval_reports_without_date_range(self):
        """Test that evaluation reports without date range don't match."""
        test_cases = [
            "What evaluation reports exist for Isabella Thomas?",
            "Show me evaluation reports for John Smith",
            "List evaluation reports for Maria Garcia",
            "What evaluation reports does Sarah Johnson have?"
        ]
        
        for question in test_cases:
            with self.subTest(question=question):
                result = _map_question_to_template_intent(question)
                self.assertIsNone(result)


class TestPlannerIntegration(unittest.TestCase):
    """Test planner integration with intent mapping."""
    
    @patch('graph_rag.planner.call_llm_structured')
    def test_generate_plan_with_template_intent(self, mock_llm):
        """Test that generate_plan uses template intent when matched."""
        # Mock LLM to avoid actual calls
        mock_llm.return_value = MagicMock(
            intent="student_goal_query",
            params={"student_name": "Isabella Thomas"},
            confidence=0.9
        )
        
        question = "What are the goals for Isabella Thomas?"
        plan = generate_plan(question)
        
        # Should use template intent, not LLM intent
        self.assertEqual(plan.intent, "goals_for_student")
        self.assertEqual(plan.anchor_entity, "Isabella Thomas")
        self.assertEqual(plan.params["student_name"], "Isabella Thomas")
        self.assertEqual(plan.question, question)
        
        # LLM should not have been called
        mock_llm.assert_not_called()
    
    @patch('graph_rag.planner.call_llm_structured')
    def test_generate_plan_without_template_intent(self, mock_llm):
        """Test that generate_plan falls back to LLM when no template intent matches."""
        # Mock LLM response
        mock_output = MagicMock()
        mock_output.intent = "student_intervention_query"
        mock_output.params = {"student_name": "John Doe"}
        mock_output.confidence = 0.8
        mock_llm.return_value = mock_output
        
        question = "What intervention plans exist for John Doe?"
        plan = generate_plan(question)
        
        # Should use LLM intent
        self.assertEqual(plan.intent, "student_intervention_query")
        self.assertEqual(plan.params["student_name"], "John Doe")
        self.assertEqual(plan.question, question)
        
        # LLM should have been called
        mock_llm.assert_called_once()
    
    def test_generate_plan_student_name_extraction(self):
        """Test that student names are extracted correctly for template intents."""
        test_cases = [
            ("What are the goals for Isabella Thomas?", "Isabella Thomas"),
            ("Show me accommodations for John Michael Smith", "John Michael Smith"),
            ("Case manager for Maria Garcia-Rodriguez", "Maria Garcia-Rodriguez"),
            ("Goals for Sarah", "Sarah"),
            ("Accommodations for Dr. Johnson", "Dr. Johnson")
        ]
        
        for question, expected_name in test_cases:
            with self.subTest(question=question):
                plan = generate_plan(question)
                
                self.assertIsNotNone(plan.anchor_entity)
                self.assertEqual(plan.anchor_entity, expected_name)
                self.assertEqual(plan.params["student_name"], expected_name)
    
    def test_generate_plan_no_student_name(self):
        """Test that questions without student names still work."""
        question = "What are the goals for students?"
        plan = generate_plan(question)
        
        # Should still match template intent
        self.assertEqual(plan.intent, "goals_for_student")
        self.assertIsNone(plan.anchor_entity)
        self.assertEqual(plan.params, {})
    
    @patch('graph_rag.planner.call_llm_structured')
    @patch('graph_rag.planner._find_best_anchor_entity_semantic')
    def test_generate_plan_llm_fallback(self, mock_semantic_mapping, mock_llm):
        """Test that LLM fallback works when template mapping fails."""
        # Mock LLM response
        mock_output = MagicMock()
        mock_output.intent = "general_query"
        mock_output.params = {}
        mock_output.confidence = 0.5
        mock_llm.return_value = mock_output
        
        # Mock semantic mapping to return None
        mock_semantic_mapping.return_value = None
        
        question = "What is the weather today?"
        plan = generate_plan(question)
        
        # Should use LLM intent
        self.assertEqual(plan.intent, "general_query")
        self.assertEqual(plan.params, {})
        
        # LLM should have been called
        mock_llm.assert_called_once()


class TestIntentMappingEdgeCases(unittest.TestCase):
    """Test edge cases and complex scenarios for intent mapping."""
    
    def test_multiple_patterns_in_question(self):
        """Test questions that might match multiple patterns."""
        # Should match the first pattern found (goals)
        question = "What are the goals and accommodations for Isabella Thomas?"
        result = _map_question_to_template_intent(question)
        self.assertEqual(result, "goals_for_student")
    
    def test_question_with_punctuation(self):
        """Test questions with various punctuation."""
        test_cases = [
            "What are the goals for Isabella Thomas?",
            "Show me goals for John Smith!",
            "Goals for Maria Garcia...",
            "What goals does Sarah Johnson have???"
        ]
        
        for question in test_cases:
            with self.subTest(question=question):
                result = _map_question_to_template_intent(question)
                self.assertEqual(result, "goals_for_student")
    
    def test_question_with_extra_whitespace(self):
        """Test questions with extra whitespace."""
        test_cases = [
            "  What are the goals for Isabella Thomas?  ",
            "\tShow me goals for John Smith\n",
            "   Goals   for   Maria   Garcia   ",
            "What goals does Sarah Johnson have?   "
        ]
        
        for question in test_cases:
            with self.subTest(question=question):
                result = _map_question_to_template_intent(question)
                self.assertEqual(result, "goals_for_student")
    
    def test_eval_reports_date_keywords(self):
        """Test various date range keywords for evaluation reports."""
        base_question = "What evaluation reports exist for Isabella Thomas"
        date_keywords = ["between", "since", "from", "to"]
        
        for keyword in date_keywords:
            question = f"{base_question} {keyword} 2024-01-01"
            with self.subTest(keyword=keyword):
                result = _map_question_to_template_intent(question)
                self.assertEqual(result, "eval_reports_for_student_in_range")
    
    def test_case_sensitivity(self):
        """Test that matching is case insensitive."""
        test_cases = [
            ("GOALS FOR JOHN DOE", "goals_for_student"),
            ("Case Manager For Jane Smith", "case_manager_for_student"),
            ("ACCOMMODATIONS FOR MARIA GARCIA", "accommodations_for_student"),
            ("Evaluation Reports For Sarah Johnson Between Dates", "eval_reports_for_student_in_range"),
            ("Concern Areas For Michael Brown", "concern_areas_for_student")
        ]
        
        for question, expected_intent in test_cases:
            with self.subTest(question=question):
                result = _map_question_to_template_intent(question)
                self.assertEqual(result, expected_intent)


if __name__ == '__main__':
    unittest.main()
