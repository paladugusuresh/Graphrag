import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.formatters import TableFormatter, GraphFormatter, CitationVerifier, FormattersManager


class TestTableFormatter(unittest.TestCase):
    """Tests for TableFormatter class"""

    def setUp(self):
        """Set up test environment"""
        self.formatter = TableFormatter()

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_table_enabled(self, mock_flag):
        """Test table formatting when formatters are enabled"""
        mock_flag.return_value = True
        
        rows = [
            {"id": "1", "name": "Alice", "age": 25},
            {"id": "2", "name": "Bob", "age": 30},
            {"id": "3", "name": "Charlie", "age": 35}
        ]
        
        result = self.formatter.format_table(rows)
        
        self.assertIsNotNone(result)
        self.assertIn("columns", result)
        self.assertIn("data", result)
        
        # Check column ordering (should be stable)
        expected_columns = ["id", "name", "age"]  # All keys appear equally
        self.assertEqual(sorted(result["columns"]), sorted(expected_columns))
        
        # Check data formatting
        self.assertEqual(len(result["data"]), 3)
        self.assertEqual(len(result["data"][0]), 3)

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_table_disabled(self, mock_flag):
        """Test table formatting when formatters are disabled"""
        mock_flag.return_value = False
        
        rows = [{"id": "1", "name": "Alice"}]
        result = self.formatter.format_table(rows)
        
        self.assertIsNone(result)

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_table_empty_rows(self, mock_flag):
        """Test table formatting with empty rows"""
        mock_flag.return_value = True
        
        result = self.formatter.format_table([])
        
        self.assertIsNotNone(result)
        self.assertEqual(result["columns"], [])
        self.assertEqual(result["data"], [])

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_table_with_nulls(self, mock_flag):
        """Test table formatting with null values"""
        mock_flag.return_value = True
        
        rows = [
            {"id": "1", "name": "Alice", "age": None},
            {"id": "2", "name": None, "age": 30}
        ]
        
        result = self.formatter.format_table(rows)
        
        self.assertIsNotNone(result)
        # Check that None values are converted to empty strings
        for row in result["data"]:
            for cell in row:
                self.assertNotEqual(cell, None)

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_table_column_ordering(self, mock_flag):
        """Test that column ordering is deterministic"""
        mock_flag.return_value = True
        
        rows = [
            {"common_field": "value1", "rare_field": "value2"},
            {"common_field": "value3", "rare_field": "value4"},
            {"common_field": "value5", "rare_field": "value6"},
            {"common_field": "value7", "rare_field": "value8"}
        ]
        
        result = self.formatter.format_table(rows)
        
        # common_field should come first (higher frequency)
        self.assertEqual(result["columns"][0], "common_field")
        self.assertEqual(result["columns"][1], "rare_field")


class TestGraphFormatter(unittest.TestCase):
    """Tests for GraphFormatter class"""

    def setUp(self):
        """Set up test environment"""
        self.formatter = GraphFormatter()

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_graph_enabled(self, mock_flag):
        """Test graph formatting when formatters are enabled"""
        mock_flag.return_value = True
        
        rows = [
            {"primary_id": "node1", "name": "Alice", "age": 25},
            {"primary_id": "node2", "name": "Bob", "age": 30},
            {"primary_id": "node3", "name": "Charlie", "age": 35}
        ]
        
        result = self.formatter.format_graph(rows)
        
        self.assertIsNotNone(result)
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        
        # Check nodes
        self.assertEqual(len(result["nodes"]), 3)
        self.assertEqual(result["nodes"][0]["id"], "node1")
        self.assertEqual(result["nodes"][0]["label"], "node1")
        self.assertEqual(result["nodes"][0]["type"], "entity")
        
        # Check edges (should be sequential)
        self.assertEqual(len(result["edges"]), 2)
        self.assertEqual(result["edges"][0]["source"], "node1")
        self.assertEqual(result["edges"][0]["target"], "node2")

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_graph_disabled(self, mock_flag):
        """Test graph formatting when formatters are disabled"""
        mock_flag.return_value = False
        
        rows = [{"primary_id": "node1", "name": "Alice"}]
        result = self.formatter.format_graph(rows)
        
        self.assertIsNone(result)

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_graph_empty_rows(self, mock_flag):
        """Test graph formatting with empty rows"""
        mock_flag.return_value = True
        
        result = self.formatter.format_graph([])
        
        self.assertIsNotNone(result)
        self.assertEqual(result["nodes"], [])
        self.assertEqual(result["edges"], [])

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_graph_no_primary_id(self, mock_flag):
        """Test graph formatting with rows missing primary_id"""
        mock_flag.return_value = True
        
        rows = [
            {"name": "Alice", "age": 25},
            {"name": "Bob", "age": 30}
        ]
        
        result = self.formatter.format_graph(rows)
        
        # Should have no nodes since no primary_id
        self.assertEqual(len(result["nodes"]), 0)
        self.assertEqual(len(result["edges"]), 0)

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_graph_duplicate_primary_ids(self, mock_flag):
        """Test graph formatting with duplicate primary_ids"""
        mock_flag.return_value = True
        
        rows = [
            {"primary_id": "node1", "name": "Alice"},
            {"primary_id": "node1", "name": "Alice Duplicate"},
            {"primary_id": "node2", "name": "Bob"}
        ]
        
        result = self.formatter.format_graph(rows)
        
        # Should deduplicate nodes
        self.assertEqual(len(result["nodes"]), 2)
        self.assertEqual(len(result["edges"]), 1)


class TestCitationVerifier(unittest.TestCase):
    """Tests for CitationVerifier class"""

    def setUp(self):
        """Set up test environment"""
        self.verifier = CitationVerifier()

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_verify_citations_enabled_passed(self, mock_flag):
        """Test citation verification when all citations are valid"""
        mock_flag.return_value = True
        
        summary = "This is about [node1] and [node2]."
        available_ids = ["node1", "node2", "node3"]
        citations = ["node1", "node2"]
        
        result = self.verifier.verify_citations(summary, available_ids, citations)
        
        self.assertEqual(result["verification_status"], "passed")
        self.assertEqual(len(result["cited_ids"]), 2)
        self.assertEqual(len(result["unknown_citations"]), 0)

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_verify_citations_enabled_failed(self, mock_flag):
        """Test citation verification when no citations are valid"""
        mock_flag.return_value = True
        
        summary = "This is about [bad_node1] and [bad_node2]."
        available_ids = ["node1", "node2", "node3"]
        citations = ["bad_node1", "bad_node2"]
        
        result = self.verifier.verify_citations(summary, available_ids, citations)
        
        self.assertEqual(result["verification_status"], "failed")
        self.assertEqual(len(result["cited_ids"]), 0)
        self.assertEqual(len(result["unknown_citations"]), 2)

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_verify_citations_enabled_partial(self, mock_flag):
        """Test citation verification when some citations are valid"""
        mock_flag.return_value = True
        
        summary = "This is about [node1] and [bad_node]."
        available_ids = ["node1", "node2", "node3"]
        citations = ["node1", "bad_node"]
        
        result = self.verifier.verify_citations(summary, available_ids, citations)
        
        self.assertEqual(result["verification_status"], "partial")
        self.assertEqual(len(result["cited_ids"]), 1)
        self.assertEqual(len(result["unknown_citations"]), 1)

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_verify_citations_disabled(self, mock_flag):
        """Test citation verification when formatters are disabled"""
        mock_flag.return_value = False
        
        summary = "This is about [node1]."
        available_ids = ["node1"]
        citations = ["node1"]
        
        result = self.verifier.verify_citations(summary, available_ids, citations)
        
        self.assertEqual(result["verification_status"], "disabled")
        self.assertEqual(result["verification_action"], "disabled")

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_verify_citations_no_citations(self, mock_flag):
        """Test citation verification with no citations"""
        mock_flag.return_value = True
        
        summary = "This is a summary with no citations."
        available_ids = ["node1", "node2"]
        citations = []
        
        result = self.verifier.verify_citations(summary, available_ids, citations)
        
        self.assertEqual(result["verification_status"], "passed")
        self.assertEqual(len(result["cited_ids"]), 0)
        self.assertEqual(len(result["unknown_citations"]), 0)

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_verify_citations_extract_from_text(self, mock_flag):
        """Test that citations are extracted from summary text"""
        mock_flag.return_value = True
        
        summary = "This mentions [chunk_123] and [doc_456] in the text."
        available_ids = ["chunk_123", "doc_456", "other_id"]
        citations = []  # No explicit citations
        
        result = self.verifier.verify_citations(summary, available_ids, citations)
        
        self.assertEqual(result["verification_status"], "passed")
        self.assertEqual(len(result["cited_ids"]), 2)
        self.assertIn("chunk_123", result["cited_ids"])
        self.assertIn("doc_456", result["cited_ids"])


class TestFormattersManager(unittest.TestCase):
    """Tests for FormattersManager class"""

    def setUp(self):
        """Set up test environment"""
        self.manager = FormattersManager()

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_response_enabled(self, mock_flag):
        """Test complete response formatting when enabled"""
        mock_flag.return_value = True
        
        rows = [
            {"primary_id": "node1", "name": "Alice", "age": 25},
            {"primary_id": "node2", "name": "Bob", "age": 30}
        ]
        summary = "This is about [node1] and [node2]."
        citations = ["node1", "node2"]
        available_ids = ["node1", "node2", "node3"]
        
        result = self.manager.format_response(rows, summary, citations, available_ids)
        
        self.assertIsNotNone(result)
        self.assertIn("formatted", result)
        self.assertIn("verification_status", result)
        self.assertIn("citation_details", result)
        
        # Check formatted sections
        self.assertIn("table", result["formatted"])
        self.assertIn("graph", result["formatted"])
        
        # Check verification
        self.assertEqual(result["verification_status"], "passed")

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_response_disabled(self, mock_flag):
        """Test response formatting when disabled"""
        mock_flag.return_value = False
        
        rows = [{"primary_id": "node1", "name": "Alice"}]
        summary = "Test summary"
        citations = []
        available_ids = ["node1"]
        
        result = self.manager.format_response(rows, summary, citations, available_ids)
        
        self.assertIsNone(result)

    @patch("graph_rag.formatters.FORMATTERS_ENABLED")
    def test_format_response_bad_citations(self, mock_flag):
        """Test response formatting with bad citations"""
        mock_flag.return_value = True
        
        rows = [{"primary_id": "node1", "name": "Alice"}]
        summary = "This mentions [bad_node] which doesn't exist."
        citations = ["bad_node"]
        available_ids = ["node1"]
        
        result = self.manager.format_response(rows, summary, citations, available_ids)
        
        self.assertEqual(result["verification_status"], "failed")
        self.assertEqual(len(result["citation_details"]["unknown_citations"]), 1)
        self.assertIn("bad_node", result["citation_details"]["unknown_citations"])


if __name__ == '__main__':
    unittest.main()
