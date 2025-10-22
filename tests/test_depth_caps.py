import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.cypher_validator import (
    _enforce_depth_caps,
    validate_cypher,
    _mask_string_literals
)


class TestDepthCapsEnforcement(unittest.TestCase):
    """Tests for _enforce_depth_caps function"""

    def test_unbounded_traversal_rejected(self):
        """Test that unbounded traversals are rejected"""
        # Pass max_hops explicitly
        max_hops = 2
        
        # Unbounded patterns
        test_queries = [
            "MATCH (n)-[*]->(m) RETURN n, m",
            "MATCH (n)-[*..]-(m) RETURN n, m",
            "MATCH (n)-[:KNOWS*]-(m) RETURN n, m",
        ]
        
        for query in test_queries:
            with self.subTest(query=query):
                is_valid, details = _enforce_depth_caps(query, max_hops=max_hops)
                self.assertFalse(is_valid)
                self.assertIn("depth cap", details["blocked_reason"])
                self.assertGreater(len(details["variable_length_patterns"]), 0)

    def test_over_depth_pattern_rejected(self):
        """Test that patterns exceeding max_hops are rejected"""
        max_hops = 2
        
        # Patterns with depth > 2
        test_queries = [
            "MATCH (n)-[*..5]-(m) RETURN n, m",
            "MATCH (n)-[:KNOWS*1..3]-(m) RETURN n, m",
            "MATCH (n)-[*..10]-(m) RETURN n, m",
        ]
        
        for query in test_queries:
            with self.subTest(query=query):
                is_valid, details = _enforce_depth_caps(query, max_hops=max_hops)
                self.assertFalse(is_valid)
                self.assertIn("depth cap", details["blocked_reason"])
                self.assertIn("depth_limit", details)
                self.assertEqual(details["depth_limit"], 2)

    def test_variable_upper_bound_rejected(self):
        """Test that patterns with no upper bound are rejected"""
        max_hops = 2
        
        # Variable upper bound patterns [*N..]
        test_queries = [
            "MATCH (n)-[*2..]-(m) RETURN n, m",
            "MATCH (n)-[:KNOWS*1..]-(m) RETURN n, m",
        ]
        
        for query in test_queries:
            with self.subTest(query=query):
                is_valid, details = _enforce_depth_caps(query, max_hops=max_hops)
                self.assertFalse(is_valid)
                self.assertIn("no upper bound", details["blocked_reason"])

    def test_within_depth_allowed(self):
        """Test that patterns within max_hops are allowed"""
        max_hops = 2
        
        # Patterns within depth limit
        test_queries = [
            "MATCH (n)-[*..2]-(m) RETURN n, m",
            "MATCH (n)-[:KNOWS*1..2]-(m) RETURN n, m",
            "MATCH (n)-[*1]-(m) RETURN n, m",
        ]
        
        for query in test_queries:
            with self.subTest(query=query):
                is_valid, details = _enforce_depth_caps(query, max_hops=max_hops)
                self.assertTrue(is_valid)
                self.assertIsNone(details.get("blocked_reason"))

    def test_exact_depth_at_limit_allowed(self):
        """Test that patterns exactly at the limit are allowed"""
        max_hops = 3
        
        query = "MATCH (n)-[*..3]-(m) RETURN n, m"
        is_valid, details = _enforce_depth_caps(query, max_hops=max_hops)
        
        self.assertTrue(is_valid)
        self.assertIsNone(details.get("blocked_reason"))

    def test_depth_just_over_limit_rejected(self):
        """Test that patterns just over the limit are rejected"""
        max_hops = 3
        
        query = "MATCH (n)-[*..4]-(m) RETURN n, m"
        is_valid, details = _enforce_depth_caps(query, max_hops=max_hops)
        
        self.assertFalse(is_valid)
        self.assertIn("exceeds depth cap", details["blocked_reason"])
        self.assertEqual(details["requested_depth"], 4)
        self.assertEqual(details["depth_limit"], 3)

    def test_no_variable_length_patterns_allowed(self):
        """Test that queries without variable-length patterns pass"""
        max_hops = 2
        
        # No variable-length patterns
        test_queries = [
            "MATCH (n:Student)-[:ENROLLED_IN]->(c:Course) RETURN n, c",
            "MATCH (n)-[:KNOWS]-(m) RETURN n, m",
            "MATCH (n) RETURN n",
        ]
        
        for query in test_queries:
            with self.subTest(query=query):
                is_valid, details = _enforce_depth_caps(query, max_hops=max_hops)
                self.assertTrue(is_valid)
                self.assertEqual(len(details["variable_length_patterns"]), 0)

    def test_explicit_max_hops_parameter(self):
        """Test that explicit max_hops parameter overrides flag"""
        query = "MATCH (n)-[*..5]-(m) RETURN n, m"
        
        # With max_hops=5, should pass
        is_valid, details = _enforce_depth_caps(query, max_hops=5)
        self.assertTrue(is_valid)
        
        # With max_hops=3, should fail
        is_valid, details = _enforce_depth_caps(query, max_hops=3)
        self.assertFalse(is_valid)

    @patch("graph_rag.cypher_validator.audit_store")
    def test_audit_logging_on_violation(self, mock_audit):
        """Test that violations are logged to audit store"""
        max_hops = 2
        
        query = "MATCH (n)-[*..5]-(m) RETURN n, m"
        is_valid, details = _enforce_depth_caps(query, max_hops=max_hops)
        
        self.assertFalse(is_valid)
        self.assertTrue(mock_audit.record.called)
        
        audit_call = mock_audit.record.call_args[0][0]
        self.assertEqual(audit_call["event"], "cypher_validation_failed")
        self.assertEqual(audit_call["depth_cap"], 2)
        self.assertIn("reason", audit_call)


class TestValidateCypherIntegration(unittest.TestCase):
    """Integration tests for validate_cypher with depth caps"""

    @patch("graph_rag.cypher_validator._enforce_depth_caps")
    @patch("graph_rag.cypher_validator.load_allow_list")
    def test_validate_cypher_rejects_over_depth(self, mock_load_allow_list, mock_enforce_depth):
        """Test that validate_cypher rejects queries exceeding depth cap"""
        # Mock depth check to simulate rejection
        mock_enforce_depth.return_value = (False, {
            "variable_length_patterns": ["[*..5]"],
            "blocked_reason": "Traversal depth (5) exceeds depth cap (2).",
            "violating_pattern": "[*..5]",
            "requested_depth": 5,
            "depth_limit": 2
        })
        mock_load_allow_list.return_value = {
            "node_labels": ["Student", "Course"],
            "relationship_types": ["ENROLLED_IN"],
            "properties": {}
        }
        
        query = "MATCH (n:Student)-[:ENROLLED_IN*..5]->(c:Course) RETURN n, c"
        is_valid, details = validate_cypher(query)
        
        self.assertFalse(is_valid)
        self.assertIn("depth cap", details["blocked_reason"])

    @patch("graph_rag.cypher_validator._enforce_depth_caps")
    @patch("graph_rag.cypher_validator.load_allow_list")
    def test_validate_cypher_allows_within_depth(self, mock_load_allow_list, mock_enforce_depth):
        """Test that validate_cypher allows queries within depth cap"""
        # Mock depth check to simulate pass
        mock_enforce_depth.return_value = (True, {
            "variable_length_patterns": ["[*..2]"],
            "blocked_reason": None,
            "depth_limit": 2
        })
        mock_load_allow_list.return_value = {
            "node_labels": ["Student", "Course"],
            "relationship_types": ["ENROLLED_IN"],
            "properties": {}
        }
        
        query = "MATCH (n:Student)-[:ENROLLED_IN*..2]->(c:Course) RETURN n, c"
        is_valid, details = validate_cypher(query)
        
        self.assertTrue(is_valid)
        self.assertIsNone(details.get("blocked_reason"))

    @patch("graph_rag.cypher_validator._enforce_depth_caps")
    @patch("graph_rag.cypher_validator.load_allow_list")
    def test_validate_cypher_rejects_unbounded(self, mock_load_allow_list, mock_enforce_depth):
        """Test that validate_cypher rejects unbounded traversals"""
        # Mock depth check to simulate unbounded rejection
        mock_enforce_depth.return_value = (False, {
            "variable_length_patterns": ["[*..]"],
            "blocked_reason": "Unbounded traversal (e.g., [*] or [*..]) exceeds depth cap (2).",
            "depth_limit": 2
        })
        mock_load_allow_list.return_value = {
            "node_labels": ["Student", "Course"],
            "relationship_types": ["ENROLLED_IN"],
            "properties": {}
        }
        
        query = "MATCH (n:Student)-[:ENROLLED_IN*]->(c:Course) RETURN n, c"
        is_valid, details = validate_cypher(query)
        
        self.assertFalse(is_valid)
        self.assertIn("Unbounded traversal", details["blocked_reason"])

    @patch("graph_rag.cypher_validator._enforce_depth_caps")
    @patch("graph_rag.cypher_validator.load_allow_list")
    def test_depth_check_happens_before_schema_validation(self, mock_load_allow_list, mock_enforce_depth):
        """Test that depth checking happens before schema validation"""
        # Mock depth check to simulate rejection
        mock_enforce_depth.return_value = (False, {
            "variable_length_patterns": ["[*..5]"],
            "blocked_reason": "Traversal depth (5) exceeds depth cap (2).",
            "violating_pattern": "[*..5]",
            "requested_depth": 5,
            "depth_limit": 2
        })
        mock_load_allow_list.return_value = {
            "node_labels": ["Student"],
            "relationship_types": [],
            "properties": {}
        }
        
        # Query with both depth violation and schema violation
        query = "MATCH (n:Student)-[:INVALID_REL*..5]->(m:InvalidLabel) RETURN n, m"
        is_valid, details = validate_cypher(query)
        
        self.assertFalse(is_valid)
        # Depth violation should be caught first
        self.assertIn("depth cap", details["blocked_reason"])

    def test_high_max_hops_allows_deeper_traversals(self):
        """Test rollback: setting GUARDRAILS_MAX_HOPS high allows deeper traversals"""
        max_hops = 99
        
        query = "MATCH (n)-[*..50]-(m) RETURN n, m"
        is_valid, details = _enforce_depth_caps(query, max_hops=max_hops)
        
        self.assertTrue(is_valid)
        self.assertIsNone(details.get("blocked_reason"))


if __name__ == '__main__':
    unittest.main()

