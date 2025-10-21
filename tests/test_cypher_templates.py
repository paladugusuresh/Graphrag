# tests/test_cypher_templates.py
import unittest
import tempfile
import os
import json
from unittest.mock import patch, mock_open, MagicMock

from graph_rag.cypher_generator import try_load_template, _validate_template, load_allow_list
from graph_rag.rag import RAGChain


class TestCypherTemplates(unittest.TestCase):
    """Test Cypher template loading and validation functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.templates_dir = os.path.join(self.test_dir, "templates")
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Create test allow-list
        self.test_allow_list = {
            "node_labels": ["Student", "Staff", "Goal", "Plan", "Accommodation", "EvaluationReport", "ConcernArea"],
            "relationship_types": ["HAS_PLAN", "HAS_GOAL", "USES_ACCOMMODATION", "HAS_CASE_MANAGER", "FOR_STUDENT", "HAS_CONCERN"],
            "properties": {
                "Student": ["fullName", "name"],
                "Staff": ["fullName", "role"],
                "Goal": ["title", "status"],
                "Accommodation": ["name"],
                "EvaluationReport": ["title", "dateTime"],
                "ConcernArea": ["name"]
            }
        }
    
    def tearDown(self):
        """Clean up test environment."""
        try:
            import shutil
            shutil.rmtree(self.test_dir)
        except (PermissionError, OSError):
            # Handle Windows permission issues
            pass
    
    def test_try_load_template_success(self):
        """Test successful template loading."""
        template_content = """MATCH (s:Student {fullName: $student})-[:HAS_GOAL]->(g:Goal)
RETURN g.title AS goal, g.status AS status
LIMIT $limit"""
        
        template_path = os.path.join(self.templates_dir, "goals_for_student.cypher")
        with open(template_path, 'w') as f:
            f.write(template_content)
        
        with patch('graph_rag.cypher_generator.load_allow_list', return_value=self.test_allow_list), \
             patch('graph_rag.cypher_generator.get_config_value', return_value=self.templates_dir):
            
            result = try_load_template("goals_for_student")
            
            self.assertIsNotNone(result)
            self.assertEqual(result.strip(), template_content.strip())
    
    def test_try_load_template_file_not_found(self):
        """Test template loading when file doesn't exist."""
        with patch('graph_rag.cypher_generator.get_config_value', return_value=self.templates_dir):
            result = try_load_template("goals_for_student")
            
            self.assertIsNone(result)
    
    def test_try_load_template_unknown_intent(self):
        """Test template loading for unknown intent."""
        result = try_load_template("unknown_intent")
        
        self.assertIsNone(result)
    
    def test_try_load_template_invalid_intent_name(self):
        """Test template loading with invalid intent name."""
        result = try_load_template(None)
        self.assertIsNone(result)
        
        result = try_load_template("")
        self.assertIsNone(result)
        
        result = try_load_template(123)
        self.assertIsNone(result)
    
    def test_try_load_template_empty_file(self):
        """Test template loading with empty file."""
        template_path = os.path.join(self.templates_dir, "goals_for_student.cypher")
        with open(template_path, 'w') as f:
            f.write("")
        
        with patch('graph_rag.cypher_generator.get_config_value', return_value=self.templates_dir):
            result = try_load_template("goals_for_student")
            
            self.assertIsNone(result)
    
    def test_try_load_template_validation_failure(self):
        """Test template loading with validation failure."""
        # Template with write operation (should fail validation)
        template_content = """MATCH (s:Student {fullName: $student})
CREATE (g:Goal {title: "Test"})
RETURN g.title AS goal
LIMIT $limit"""
        
        template_path = os.path.join(self.templates_dir, "goals_for_student.cypher")
        with open(template_path, 'w') as f:
            f.write(template_content)
        
        with patch('graph_rag.cypher_generator.load_allow_list', return_value=self.test_allow_list), \
             patch('graph_rag.cypher_generator.get_config_value', return_value=self.templates_dir):
            
            result = try_load_template("goals_for_student")
            
            self.assertIsNone(result)
    
    def test_validate_template_success(self):
        """Test successful template validation."""
        template_content = """MATCH (s:Student {fullName: $student})-[:HAS_GOAL]->(g:Goal)
RETURN g.title AS goal, g.status AS status
LIMIT $limit"""
        
        with patch('graph_rag.cypher_generator.load_allow_list', return_value=self.test_allow_list):
            result = _validate_template(template_content, "goals_for_student")
            
            self.assertTrue(result)
    
    def test_validate_template_write_operation(self):
        """Test template validation with write operation."""
        template_content = """MATCH (s:Student {fullName: $student})
CREATE (g:Goal {title: "Test"})
RETURN g.title AS goal
LIMIT $limit"""
        
        with patch('graph_rag.cypher_generator.load_allow_list', return_value=self.test_allow_list):
            result = _validate_template(template_content, "goals_for_student")
            
            self.assertFalse(result)
    
    def test_validate_template_unbounded_traversal(self):
        """Test template validation with unbounded traversal."""
        template_content = """MATCH (s:Student {fullName: $student})-[:HAS_GOAL*..]->(g:Goal)
RETURN g.title AS goal
LIMIT $limit"""
        
        with patch('graph_rag.cypher_generator.load_allow_list', return_value=self.test_allow_list):
            result = _validate_template(template_content, "goals_for_student")
            
            self.assertFalse(result)
    
    def test_validate_template_unknown_label(self):
        """Test template validation with unknown label."""
        template_content = """MATCH (s:UnknownLabel {fullName: $student})-[:HAS_GOAL]->(g:Goal)
RETURN g.title AS goal
LIMIT $limit"""
        
        with patch('graph_rag.cypher_generator.load_allow_list', return_value=self.test_allow_list):
            result = _validate_template(template_content, "goals_for_student")
            
            self.assertFalse(result)
    
    def test_validate_template_unknown_relationship(self):
        """Test template validation with unknown relationship."""
        template_content = """MATCH (s:Student {fullName: $student})-[:UNKNOWN_REL]->(g:Goal)
RETURN g.title AS goal
LIMIT $limit"""
        
        with patch('graph_rag.cypher_generator.load_allow_list', return_value=self.test_allow_list):
            result = _validate_template(template_content, "goals_for_student")
            
            self.assertFalse(result)
    
    def test_validate_template_missing_limit(self):
        """Test template validation without LIMIT clause."""
        template_content = """MATCH (s:Student {fullName: $student})-[:HAS_GOAL]->(g:Goal)
RETURN g.title AS goal, g.status AS status"""
        
        with patch('graph_rag.cypher_generator.load_allow_list', return_value=self.test_allow_list):
            result = _validate_template(template_content, "goals_for_student")
            
            self.assertFalse(result)
    
    def test_validate_template_multiple_write_operations(self):
        """Test template validation with multiple write operations."""
        write_operations = ['CREATE', 'DELETE', 'SET', 'REMOVE', 'MERGE', 'DROP']
        
        for op in write_operations:
            template_content = f"""MATCH (s:Student {{fullName: $student}})
{op} (g:Goal {{title: "Test"}})
RETURN g.title AS goal
LIMIT $limit"""
            
            with patch('graph_rag.cypher_generator.load_allow_list', return_value=self.test_allow_list):
                result = _validate_template(template_content, "goals_for_student")
                
                self.assertFalse(result, f"Should reject template with {op} operation")


class TestRAGTemplateIntegration(unittest.TestCase):
    """Test RAG integration with template functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.rag = RAGChain()
    
    def test_build_template_params_goals_for_student(self):
        """Test building parameters for goals_for_student template."""
        from graph_rag.planner import QueryPlan
        
        plan = QueryPlan(
            intent="goals_for_student",
            anchor_entity="John Doe",
            question="What are the goals for John Doe?",
            params={"student_name": "John Doe"}
        )
        
        template_cypher = "MATCH (s:Student {fullName: $student})-[:HAS_GOAL]->(g:Goal) RETURN g.title AS goal LIMIT $limit"
        
        params = self.rag._build_template_params(plan, template_cypher)
        
        expected_params = {
            "student": "John Doe",
            "limit": 20
        }
        
        self.assertEqual(params, expected_params)
    
    def test_build_template_params_eval_reports_with_dates(self):
        """Test building parameters for eval_reports_for_student_in_range with date range."""
        from graph_rag.planner import QueryPlan
        
        plan = QueryPlan(
            intent="eval_reports_for_student_in_range",
            anchor_entity="Jane Smith",
            question="What evaluation reports exist for Jane Smith from 2024-01-01 to 2024-12-31?",
            params={
                "student_name": "Jane Smith",
                "from": "2024-01-01",
                "to": "2024-12-31"
            }
        )
        
        template_cypher = """MATCH (s:Student {fullName: $student})<-[:FOR_STUDENT]-(r:EvaluationReport)
WHERE r.dateTime >= $from AND r.dateTime < $to
RETURN r.title AS report, r.dateTime AS date
LIMIT $limit"""
        
        params = self.rag._build_template_params(plan, template_cypher)
        
        expected_params = {
            "student": "Jane Smith",
            "from": "2024-01-01",
            "to": "2024-12-31",
            "limit": 20
        }
        
        self.assertEqual(params, expected_params)
    
    def test_build_template_params_eval_reports_default_dates(self):
        """Test building parameters for eval_reports_for_student_in_range with default dates."""
        from graph_rag.planner import QueryPlan
        
        plan = QueryPlan(
            intent="eval_reports_for_student_in_range",
            anchor_entity="Jane Smith",
            question="What evaluation reports exist for Jane Smith?",
            params={"student_name": "Jane Smith"}
        )
        
        template_cypher = """MATCH (s:Student {fullName: $student})<-[:FOR_STUDENT]-(r:EvaluationReport)
WHERE r.dateTime >= $from AND r.dateTime < $to
RETURN r.title AS report, r.dateTime AS date
LIMIT $limit"""
        
        params = self.rag._build_template_params(plan, template_cypher)
        
        # Should have default dates (last 6 months to today)
        self.assertEqual(params["student"], "Jane Smith")
        self.assertEqual(params["limit"], 20)
        self.assertIn("from", params)
        self.assertIn("to", params)
        # Dates should be in YYYY-MM-DD format
        self.assertRegex(params["from"], r"\d{4}-\d{2}-\d{2}")
        self.assertRegex(params["to"], r"\d{4}-\d{2}-\d{2}")
    
    def test_build_template_params_no_student_name(self):
        """Test building parameters when no student name is provided."""
        from graph_rag.planner import QueryPlan
        
        plan = QueryPlan(
            intent="goals_for_student",
            anchor_entity=None,
            question="What are the goals?",
            params={}
        )
        
        template_cypher = "MATCH (s:Student {fullName: $student})-[:HAS_GOAL]->(g:Goal) RETURN g.title AS goal LIMIT $limit"
        
        params = self.rag._build_template_params(plan, template_cypher)
        
        expected_params = {
            "limit": 20
        }
        
        self.assertEqual(params, expected_params)
    
    def test_build_template_params_anchor_entity_fallback(self):
        """Test building parameters using anchor entity as fallback."""
        from graph_rag.planner import QueryPlan
        
        plan = QueryPlan(
            intent="goals_for_student",
            anchor_entity="Bob Wilson",
            question="What are the goals for Bob Wilson?",
            params={}  # No student_name in params
        )
        
        template_cypher = "MATCH (s:Student {fullName: $student})-[:HAS_GOAL]->(g:Goal) RETURN g.title AS goal LIMIT $limit"
        
        params = self.rag._build_template_params(plan, template_cypher)
        
        expected_params = {
            "student": "Bob Wilson",
            "limit": 20
        }
        
        self.assertEqual(params, expected_params)


class TestTemplateEndToEnd(unittest.TestCase):
    """End-to-end tests for template functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.templates_dir = os.path.join(self.test_dir, "templates")
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Create valid template
        self.valid_template = """MATCH (s:Student {fullName: $student})-[:HAS_GOAL]->(g:Goal)
RETURN g.title AS goal, coalesce(g.status,'') AS status
ORDER BY g.title
LIMIT $limit"""
        
        template_path = os.path.join(self.templates_dir, "goals_for_student.cypher")
        with open(template_path, 'w') as f:
            f.write(self.valid_template)
    
    def tearDown(self):
        """Clean up test environment."""
        try:
            import shutil
            shutil.rmtree(self.test_dir)
        except (PermissionError, OSError):
            pass
    
    def test_template_load_and_validation_integration(self):
        """Test complete template loading and validation workflow."""
        test_allow_list = {
            "node_labels": ["Student", "Goal"],
            "relationship_types": ["HAS_GOAL"],
            "properties": {
                "Student": ["fullName"],
                "Goal": ["title", "status"]
            }
        }
        
        with patch('graph_rag.cypher_generator.load_allow_list', return_value=test_allow_list), \
             patch('graph_rag.cypher_generator.get_config_value', return_value=self.templates_dir):
            
            result = try_load_template("goals_for_student")
            
            self.assertIsNotNone(result)
            self.assertEqual(result.strip(), self.valid_template.strip())
    
    def test_template_missing_file_fallback(self):
        """Test that missing template files fall back gracefully."""
        # Remove the template file
        template_path = os.path.join(self.templates_dir, "goals_for_student.cypher")
        os.remove(template_path)
        
        with patch('graph_rag.cypher_generator.get_config_value', return_value=self.templates_dir):
            result = try_load_template("goals_for_student")
            
            self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
