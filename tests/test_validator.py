# tests/test_validator.py
import unittest
from unittest.mock import patch, MagicMock

from graph_rag.cypher_validator import validate_cypher, _enforce_depth_caps
from graph_rag.flags import GUARDRAILS_MAX_HOPS


class TestDepthCapsValidation(unittest.TestCase):
    """Test depth caps validation for Cypher queries."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.allow_list = {
            "node_labels": ["Student", "Plan", "Goal"],
            "relationship_types": ["HAS_PLAN", "HAS_GOAL", "MENTIONS"],
            "properties": {
                "Student": ["fullName", "id"],
                "Plan": ["title", "status"],
                "Goal": ["title", "status"]
            }
        }
    
    @patch('graph_rag.cypher_validator.GUARDRAILS_MAX_HOPS')
    def test_depth_cap_enforcement(self, mock_max_hops):
        """Test that depth caps are enforced."""
        # Set max hops to 2
        mock_max_hops.return_value = 2
        
        # Test query with unbounded traversal
        cypher = "MATCH (s:Student)-[*]->(n) RETURN n"
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
            result = validate_cypher(cypher)
            
            # Should fail due to unbounded traversal
            self.assertFalse(result["valid"])
            self.assertIn("depth cap", result["reason"].lower())
    
    @patch('graph_rag.cypher_validator.GUARDRAILS_MAX_HOPS')
    def test_depth_cap_within_limit(self, mock_max_hops):
        """Test that queries within depth limit pass."""
        # Set max hops to 3
        mock_max_hops.return_value = 3
        
        # Test query with bounded traversal
        cypher = "MATCH (s:Student)-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal) RETURN g"
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
            result = validate_cypher(cypher)
            
            # Should pass
            self.assertTrue(result["valid"])
    
    @patch('graph_rag.cypher_validator.GUARDRAILS_MAX_HOPS')
    def test_depth_cap_explicit_range(self, mock_max_hops):
        """Test explicit depth range validation."""
        # Set max hops to 2
        mock_max_hops.return_value = 2
        
        # Test query with explicit range exceeding limit
        cypher = "MATCH (s:Student)-[*..5]->(n) RETURN n"
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
            result = validate_cypher(cypher)
            
            # Should fail due to range exceeding limit
            self.assertFalse(result["valid"])
            self.assertIn("depth cap", result["reason"].lower())
    
    @patch('graph_rag.cypher_validator.GUARDRAILS_MAX_HOPS')
    def test_depth_cap_explicit_range_within_limit(self, mock_max_hops):
        """Test explicit depth range within limit."""
        # Set max hops to 5
        mock_max_hops.return_value = 5
        
        # Test query with explicit range within limit
        cypher = "MATCH (s:Student)-[*..3]->(n) RETURN n"
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
            result = validate_cypher(cypher)
            
            # Should pass
            self.assertTrue(result["valid"])
    
    def test_depth_cap_regex_patterns(self):
        """Test regex patterns for depth cap detection."""
        # Test various patterns
        test_cases = [
            ("MATCH (a)-[*]->(b)", True),  # Unbounded
            ("MATCH (a)-[*..5]->(b)", True),  # Explicit range
            ("MATCH (a)-[*1..5]->(b)", True),  # Range with start
            ("MATCH (a)-[*5]->(b)", True),  # Fixed length
            ("MATCH (a)-[:REL]->(b)", False),  # No variable length
            ("MATCH (a)-[r*]->(b)", True),  # With relationship variable
        ]
        
        for cypher, should_match in test_cases:
            with self.subTest(cypher=cypher):
                # Test the regex pattern directly
                import re
                pattern = r'\[[^]]*\*[^]]*\]'
                matches = bool(re.search(pattern, cypher))
                self.assertEqual(matches, should_match)


class TestCypherValidation(unittest.TestCase):
    """Test general Cypher validation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.allow_list = {
            "node_labels": ["Student", "Plan", "Goal"],
            "relationship_types": ["HAS_PLAN", "HAS_GOAL", "MENTIONS"],
            "properties": {
                "Student": ["fullName", "id"],
                "Plan": ["title", "status"],
                "Goal": ["title", "status"]
            }
        }
    
    def test_valid_cypher_query(self):
        """Test validation of valid Cypher query."""
        cypher = "MATCH (s:Student {fullName: 'Isabella Thomas'})-[:HAS_PLAN]->(p:Plan) RETURN p.title"
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
            result = validate_cypher(cypher)
            
            self.assertTrue(result["valid"])
            self.assertIsNone(result["reason"])
    
    def test_invalid_label(self):
        """Test validation with invalid label."""
        cypher = "MATCH (s:InvalidLabel) RETURN s"
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
            result = validate_cypher(cypher)
            
            self.assertFalse(result["valid"])
            self.assertIn("InvalidLabel", result["reason"])
    
    def test_invalid_relationship(self):
        """Test validation with invalid relationship."""
        cypher = "MATCH (s:Student)-[:INVALID_REL]->(p:Plan) RETURN p"
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
            result = validate_cypher(cypher)
            
            self.assertFalse(result["valid"])
            self.assertIn("INVALID_REL", result["reason"])
    
    def test_invalid_property(self):
        """Test validation with invalid property."""
        cypher = "MATCH (s:Student {invalidProp: 'value'}) RETURN s"
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
            result = validate_cypher(cypher)
            
            self.assertFalse(result["valid"])
            self.assertIn("invalidProp", result["reason"])
    
    def test_write_operation_detection(self):
        """Test detection of write operations."""
        write_operations = [
            "CREATE (s:Student {name: 'Test'})",
            "DELETE s",
            "SET s.name = 'New Name'",
            "REMOVE s.name",
            "MERGE (s:Student {name: 'Test'})",
            "DROP INDEX index_name"
        ]
        
        for cypher in write_operations:
            with self.subTest(cypher=cypher):
                with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
                    result = validate_cypher(cypher)
                    
                    self.assertFalse(result["valid"])
                    self.assertIn("write operation", result["reason"].lower())
    
    def test_limit_clause_requirement(self):
        """Test that LIMIT clause is required."""
        cypher = "MATCH (s:Student) RETURN s"
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
            result = validate_cypher(cypher)
            
            self.assertFalse(result["valid"])
            self.assertIn("limit", result["reason"].lower())
    
    def test_limit_clause_present(self):
        """Test that queries with LIMIT clause pass."""
        cypher = "MATCH (s:Student) RETURN s LIMIT 10"
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=self.allow_list):
            result = validate_cypher(cypher)
            
            self.assertTrue(result["valid"])


class TestValidatorMetrics(unittest.TestCase):
    """Test validator metrics and observability."""
    
    def test_validation_failure_metrics(self):
        """Test that validation failures are recorded as metrics."""
        from graph_rag.observability import guardrail_blocks_total
        
        cypher = "MATCH (s:InvalidLabel) RETURN s"
        allow_list = {"node_labels": ["Student"], "relationship_types": [], "properties": {}}
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=allow_list), \
             patch('graph_rag.cypher_validator.guardrail_blocks_total') as mock_metric:
            
            result = validate_cypher(cypher)
            
            # Should fail validation
            self.assertFalse(result["valid"])
            
            # Verify metric was incremented
            mock_metric.labels.assert_called_with(reason="validation_failed")
            mock_metric.labels.return_value.inc.assert_called()


class TestValidatorAuditLogging(unittest.TestCase):
    """Test validator audit logging."""
    
    def test_validation_audit_logging(self):
        """Test that validation results are logged to audit store."""
        cypher = "MATCH (s:Student) RETURN s LIMIT 10"
        allow_list = {
            "node_labels": ["Student"],
            "relationship_types": [],
            "properties": {"Student": ["fullName"]}
        }
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=allow_list), \
             patch('graph_rag.cypher_validator.audit_store') as mock_audit:
            
            result = validate_cypher(cypher)
            
            # Should pass validation
            self.assertTrue(result["valid"])
            
            # Verify audit logging
            mock_audit.record.assert_called()
            audit_call = mock_audit.record.call_args[0][0]
            self.assertEqual(audit_call["event"], "cypher_validation")
            self.assertEqual(audit_call["cypher_preview"], cypher[:100])
            self.assertEqual(audit_call["validation_result"], "passed")


class TestValidatorIntegration(unittest.TestCase):
    """Test validator integration with query executor."""
    
    def test_executor_integration(self):
        """Test validator integration with query executor."""
        from graph_rag.query_executor import safe_execute
        
        # Test that validator is called in safe_execute
        cypher = "MATCH (s:Student) RETURN s LIMIT 10"
        
        with patch('graph_rag.query_executor.validate_cypher') as mock_validate, \
             patch('graph_rag.query_executor.Neo4jClient') as mock_client:
            
            # Mock validation to pass
            mock_validate.return_value = {"valid": True, "reason": None}
            
            # Mock Neo4j client
            mock_client.return_value.execute_read_query.return_value = []
            
            result = safe_execute(cypher)
            
            # Verify validator was called
            mock_validate.assert_called_with(cypher)
            
            # Should return empty result
            self.assertEqual(result, [])
    
    def test_executor_validation_failure(self):
        """Test executor behavior when validation fails."""
        from graph_rag.query_executor import safe_execute
        
        cypher = "MATCH (s:InvalidLabel) RETURN s"
        
        with patch('graph_rag.query_executor.validate_cypher') as mock_validate:
            # Mock validation to fail
            mock_validate.return_value = {"valid": False, "reason": "Invalid label"}
            
            # Should raise exception
            with self.assertRaises(RuntimeError):
                safe_execute(cypher)


class TestValidatorEdgeCases(unittest.TestCase):
    """Test validator edge cases."""
    
    def test_empty_cypher(self):
        """Test validation of empty Cypher."""
        with patch('graph_rag.cypher_validator.load_allow_list', return_value={}):
            result = validate_cypher("")
            
            self.assertFalse(result["valid"])
            self.assertIn("empty", result["reason"].lower())
    
    def test_malformed_cypher(self):
        """Test validation of malformed Cypher."""
        cypher = "MATCH (s:Student RETURN s"  # Missing closing parenthesis
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value={}):
            result = validate_cypher(cypher)
            
            # Should handle gracefully
            self.assertIsInstance(result, dict)
            self.assertIn("valid", result)
    
    def test_complex_query_validation(self):
        """Test validation of complex queries."""
        cypher = """
        MATCH (s:Student {fullName: $student})
        -[:HAS_PLAN]->(p:Plan)
        -[:HAS_GOAL]->(g:Goal)
        WHERE g.status = 'active'
        RETURN g.title, g.status
        ORDER BY g.title
        LIMIT 10
        """
        
        allow_list = {
            "node_labels": ["Student", "Plan", "Goal"],
            "relationship_types": ["HAS_PLAN", "HAS_GOAL"],
            "properties": {
                "Student": ["fullName"],
                "Plan": ["title"],
                "Goal": ["title", "status"]
            }
        }
        
        with patch('graph_rag.cypher_validator.load_allow_list', return_value=allow_list):
            result = validate_cypher(cypher)
            
            # Should pass validation
            self.assertTrue(result["valid"])


if __name__ == '__main__':
    unittest.main()
