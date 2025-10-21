# tests/test_templates.py
import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock

from graph_rag.cypher_generator import try_load_template, _validate_template
from graph_rag.planner import generate_plan, QueryPlan


class TestTemplateLoading(unittest.TestCase):
    """Test template loading functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.templates_dir = os.path.join(self.test_dir, 'templates')
        os.makedirs(self.templates_dir, exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        try:
            import shutil
            shutil.rmtree(self.test_dir)
        except (OSError, PermissionError):
            pass  # Ignore cleanup errors on Windows
    
    def test_load_goals_template_success(self):
        """Test that goals_for_student template loads successfully."""
        template_content = """MATCH (s:Student {fullName: $student})
      -[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal)
RETURN g.title AS goal, coalesce(g.status,'') AS status
ORDER BY g.title
LIMIT $limit"""
        
        template_file = os.path.join(self.templates_dir, 'goals_for_student.cypher')
        with open(template_file, 'w') as f:
            f.write(template_content)
        
        # Mock config to return our test templates directory
        with patch('graph_rag.cypher_generator.get_config_value') as mock_config, \
             patch('graph_rag.cypher_generator.load_allow_list') as mock_allow_list:
            
            mock_config.return_value = self.templates_dir
            mock_allow_list.return_value = {
                "node_labels": ["Student", "Plan", "Goal"],
                "relationship_types": ["HAS_PLAN", "HAS_GOAL"],
                "properties": {
                    "Student": ["fullName"],
                    "Goal": ["title", "status"]
                }
            }
            
            result = try_load_template("goals_for_student")
            
            # Should return the template content
            self.assertIsNotNone(result)
            self.assertEqual(result.strip(), template_content.strip())
    
    def test_load_template_missing_file(self):
        """Test that template loading returns None for missing file."""
        with patch('graph_rag.cypher_generator.get_config_value') as mock_config:
            mock_config.return_value = self.templates_dir
            
            result = try_load_template("nonexistent_template")
            
            # Should return None for missing template
            self.assertIsNone(result)
    
    def test_load_template_invalid_intent(self):
        """Test that template loading returns None for invalid intent."""
        with patch('graph_rag.cypher_generator.get_config_value') as mock_config:
            mock_config.return_value = self.templates_dir
            
            result = try_load_template("invalid_intent")
            
            # Should return None for invalid intent
            self.assertIsNone(result)
    
    def test_template_validation_success(self):
        """Test that valid template passes validation."""
        template_content = """MATCH (s:Student {fullName: $student})
      -[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal)
RETURN g.title AS goal, coalesce(g.status,'') AS status
ORDER BY g.title
LIMIT $limit"""
        
        with patch('graph_rag.cypher_generator.load_allow_list') as mock_allow_list:
            mock_allow_list.return_value = {
                "node_labels": ["Student", "Plan", "Goal"],
                "relationship_types": ["HAS_PLAN", "HAS_GOAL"],
                "properties": {
                    "Student": ["fullName"],
                    "Goal": ["title", "status"]
                }
            }
            
            result = _validate_template(template_content, "goals_for_student")
            
            # Should pass validation
            self.assertTrue(result)
    
    def test_template_validation_write_operation(self):
        """Test that template with write operations fails validation."""
        template_content = """CREATE (s:Student {fullName: $student})
RETURN s
LIMIT $limit"""
        
        with patch('graph_rag.cypher_generator.load_allow_list') as mock_allow_list:
            mock_allow_list.return_value = {
                "node_labels": ["Student"],
                "relationship_types": [],
                "properties": {"Student": ["fullName"]}
            }
            
            result = _validate_template(template_content, "test_intent")
            
            # Should fail validation due to CREATE
            self.assertFalse(result)
    
    def test_template_validation_unknown_label(self):
        """Test that template with unknown labels fails validation."""
        template_content = """MATCH (s:UnknownLabel {fullName: $student})
RETURN s
LIMIT $limit"""
        
        with patch('graph_rag.cypher_generator.load_allow_list') as mock_allow_list:
            mock_allow_list.return_value = {
                "node_labels": ["Student"],
                "relationship_types": [],
                "properties": {"Student": ["fullName"]}
            }
            
            result = _validate_template(template_content, "test_intent")
            
            # Should fail validation due to unknown label
            self.assertFalse(result)
    
    def test_template_validation_missing_limit(self):
        """Test that template without LIMIT fails validation."""
        template_content = """MATCH (s:Student {fullName: $student})
RETURN s"""
        
        with patch('graph_rag.cypher_generator.load_allow_list') as mock_allow_list:
            mock_allow_list.return_value = {
                "node_labels": ["Student"],
                "relationship_types": [],
                "properties": {"Student": ["fullName"]}
            }
            
            result = _validate_template(template_content, "test_intent")
            
            # Should fail validation due to missing LIMIT
            self.assertFalse(result)


class TestTemplateIntegration(unittest.TestCase):
    """Test template integration with planner."""
    
    def test_planner_template_integration(self):
        """Test that planner uses template for goals_for_student intent."""
        # Create a mock template file
        template_content = """MATCH (s:Student {fullName: $student})
      -[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal)
RETURN g.title AS goal, coalesce(g.status,'') AS status
ORDER BY g.title
LIMIT $limit"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            templates_dir = os.path.join(temp_dir, 'templates')
            os.makedirs(templates_dir, exist_ok=True)
            
            template_file = os.path.join(templates_dir, 'goals_for_student.cypher')
            with open(template_file, 'w') as f:
                f.write(template_content)
            
            # Mock config and allow list
            with patch('graph_rag.planner.get_config_value') as mock_config, \
                 patch('graph_rag.cypher_generator.get_config_value') as mock_cypher_config, \
                 patch('graph_rag.cypher_generator.load_allow_list') as mock_allow_list:
                
                mock_config.return_value = "test_model"
                mock_cypher_config.return_value = templates_dir
                mock_allow_list.return_value = {
                    "node_labels": ["Student", "Plan", "Goal"],
                    "relationship_types": ["HAS_PLAN", "HAS_GOAL"],
                    "properties": {
                        "Student": ["fullName"],
                        "Goal": ["title", "status"]
                    }
                }
                
                # Test planner with template intent
                question = "What are the goals for Isabella Thomas?"
                plan = generate_plan(question)
                
                # Should use template intent
                self.assertEqual(plan.intent, "goals_for_student")
                self.assertEqual(plan.anchor_entity, "Isabella Thomas")
                self.assertEqual(plan.params["student_name"], "Isabella Thomas")
    
    def test_template_parameter_extraction(self):
        """Test that template parameters are extracted correctly."""
        # Test the parameter building logic
        from graph_rag.rag import RAGChain
        
        # Mock plan with student name
        mock_plan = QueryPlan(
            intent="goals_for_student",
            anchor_entity="Isabella Thomas",
            question="What are the goals for Isabella Thomas?",
            params={"student_name": "Isabella Thomas"}
        )
        
        template_cypher = """MATCH (s:Student {fullName: $student})
      -[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal)
RETURN g.title AS goal, coalesce(g.status,'') AS status
ORDER BY g.title
LIMIT $limit"""
        
        # Create RAG instance and test parameter building
        rag = RAGChain()
        params = rag._build_template_params(mock_plan, template_cypher)
        
        # Should extract student name
        self.assertIn("student", params)
        self.assertEqual(params["student"], "Isabella Thomas")
        
        # Should include limit parameter
        self.assertIn("limit", params)
        self.assertIsInstance(params["limit"], int)
    
    def test_template_parameter_extraction_with_dates(self):
        """Test that template parameters include date ranges for eval reports."""
        from graph_rag.rag import RAGChain
        
        # Mock plan for eval reports
        mock_plan = QueryPlan(
            intent="eval_reports_for_student_in_range",
            anchor_entity="Isabella Thomas",
            question="What evaluation reports exist for Isabella Thomas between 2024-01-01 and 2024-12-31?",
            params={"student_name": "Isabella Thomas"}
        )
        
        template_cypher = """MATCH (s:Student {fullName: $student})<-[:FOR_STUDENT]-(r:EvaluationReport)
WHERE r.dateTime >= $from AND r.dateTime < $to
RETURN r.title AS report, r.dateTime AS date
ORDER BY date DESC
LIMIT $limit"""
        
        # Create RAG instance and test parameter building
        rag = RAGChain()
        params = rag._build_template_params(mock_plan, template_cypher)
        
        # Should extract student name
        self.assertIn("student", params)
        self.assertEqual(params["student"], "Isabella Thomas")
        
        # Should include date parameters
        self.assertIn("from", params)
        self.assertIn("to", params)
        self.assertIsInstance(params["from"], str)
        self.assertIsInstance(params["to"], str)
        
        # Should include limit parameter
        self.assertIn("limit", params)
        self.assertIsInstance(params["limit"], int)


class TestTemplateSafety(unittest.TestCase):
    """Test template safety features."""
    
    def test_template_read_only_validation(self):
        """Test that templates are validated for read-only operations."""
        read_only_template = """MATCH (s:Student {fullName: $student})
RETURN s.fullName AS name
LIMIT $limit"""
        
        write_template = """CREATE (s:Student {fullName: $student})
RETURN s
LIMIT $limit"""
        
        with patch('graph_rag.cypher_generator.load_allow_list') as mock_allow_list:
            mock_allow_list.return_value = {
                "node_labels": ["Student"],
                "relationship_types": [],
                "properties": {"Student": ["fullName"]}
            }
            
            # Read-only template should pass
            self.assertTrue(_validate_template(read_only_template, "test"))
            
            # Write template should fail
            self.assertFalse(_validate_template(write_template, "test"))
    
    def test_template_depth_validation(self):
        """Test that templates are validated for depth limits."""
        safe_template = """MATCH (s:Student {fullName: $student})-[:HAS_PLAN]->(p:Plan)
RETURN p.title AS plan
LIMIT $limit"""
        
        unsafe_template = """MATCH (s:Student {fullName: $student})-[*..5]->(n)
RETURN n
LIMIT $limit"""
        
        with patch('graph_rag.cypher_generator.load_allow_list') as mock_allow_list:
            mock_allow_list.return_value = {
                "node_labels": ["Student", "Plan"],
                "relationship_types": ["HAS_PLAN"],
                "properties": {"Student": ["fullName"], "Plan": ["title"]}
            }
            
            # Safe template should pass
            self.assertTrue(_validate_template(safe_template, "test"))
            
            # Unsafe template should fail
            self.assertFalse(_validate_template(unsafe_template, "test"))


if __name__ == '__main__':
    unittest.main()
