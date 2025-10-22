# tests/test_allow_list_merge.py
import unittest
import json
import tempfile
import os
from unittest.mock import patch, mock_open

from graph_rag.schema_manager import (
    merge_allow_list_overrides,
    load_allow_list_overrides
)


class TestAllowListMerge(unittest.TestCase):
    """Test allow-list merge functionality with live schema validation."""
    
    def setUp(self):
        """Set up test data."""
        self.base_allow_list = {
            "node_labels": ["Student", "Staff", "Document"],
            "relationship_types": ["MENTIONS", "HAS_CHUNK", "PART_OF"],
            "properties": {
                "Student": ["name", "age"],
                "Staff": ["title", "department"],
                "Document": ["content", "type"]
            }
        }
        
        self.live_schema = {
            "node_labels": ["Student", "Staff", "Document", "Goal"],
            "relationship_types": ["MENTIONS", "HAS_CHUNK", "PART_OF", "HAS_GOAL", "FOR_STUDENT"],
            "properties": {
                "Student": ["name", "age", "fullName"],
                "Staff": ["title", "department", "email"],
                "Document": ["content", "type"],
                "Goal": ["title", "status"]
            }
        }
    
    def test_merge_relationships_valid(self):
        """Test merging valid relationships from overrides."""
        overrides = {
            "relationships": ["HAS_GOAL", "FOR_STUDENT"]
        }
        
        result = merge_allow_list_overrides(self.base_allow_list, overrides, self.live_schema)
        
        # Check that valid relationships were added
        expected_relationships = ["FOR_STUDENT", "HAS_CHUNK", "HAS_GOAL", "MENTIONS", "PART_OF"]
        self.assertEqual(sorted(result["relationship_types"]), expected_relationships)
    
    def test_merge_relationships_invalid(self):
        """Test that invalid relationships are skipped with warning."""
        overrides = {
            "relationships": ["UNKNOWN_REL", "HAS_GOAL", "INVALID_REL"]
        }
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = merge_allow_list_overrides(self.base_allow_list, overrides, self.live_schema)
        
        # Check that only valid relationships were added
        expected_relationships = ["HAS_CHUNK", "HAS_GOAL", "MENTIONS", "PART_OF"]
        self.assertEqual(sorted(result["relationship_types"]), expected_relationships)
        
        # Check that warning was logged for invalid relationships
        mock_logger.warning.assert_called_with(
            "Skipping unknown relationship types from overrides: ['INVALID_REL', 'UNKNOWN_REL']"
        )
    
    def test_merge_labels_valid(self):
        """Test merging valid labels from overrides."""
        overrides = {
            "node_labels": ["Goal"]
        }
        
        result = merge_allow_list_overrides(self.base_allow_list, overrides, self.live_schema)
        
        # Check that valid labels were added
        expected_labels = ["Document", "Goal", "Staff", "Student"]
        self.assertEqual(sorted(result["node_labels"]), expected_labels)
    
    def test_merge_labels_invalid(self):
        """Test that invalid labels are skipped with warning."""
        overrides = {
            "node_labels": ["UnknownLabel", "Goal", "InvalidLabel"]
        }
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = merge_allow_list_overrides(self.base_allow_list, overrides, self.live_schema)
        
        # Check that only valid labels were added
        expected_labels = ["Document", "Goal", "Staff", "Student"]
        self.assertEqual(sorted(result["node_labels"]), expected_labels)
        
        # Check that warning was logged for invalid labels
        mock_logger.warning.assert_called_with(
            "Skipping unknown node labels from overrides: ['InvalidLabel', 'UnknownLabel']"
        )
    
    def test_merge_properties_valid(self):
        """Test merging valid properties from overrides."""
        overrides = {
            "properties": {
                "Student": ["fullName"],
                "Staff": ["email"]
            }
        }
        
        result = merge_allow_list_overrides(self.base_allow_list, overrides, self.live_schema)
        
        # Check that valid properties were added
        expected_student_props = ["age", "fullName", "name"]
        expected_staff_props = ["department", "email", "title"]
        
        self.assertEqual(sorted(result["properties"]["Student"]), expected_student_props)
        self.assertEqual(sorted(result["properties"]["Staff"]), expected_staff_props)
    
    def test_merge_properties_invalid_label(self):
        """Test that properties for invalid labels are skipped."""
        overrides = {
            "properties": {
                "UnknownLabel": ["someProp"],
                "Student": ["fullName"]
            }
        }
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = merge_allow_list_overrides(self.base_allow_list, overrides, self.live_schema)
        
        # Check that properties for unknown label were not added
        self.assertNotIn("UnknownLabel", result["properties"])
        
        # Check that valid properties were still added
        expected_student_props = ["age", "fullName", "name"]
        self.assertEqual(sorted(result["properties"]["Student"]), expected_student_props)
        
        # Check that warning was logged
        mock_logger.warning.assert_called_with(
            "Skipping properties for unknown label 'UnknownLabel' from overrides"
        )
    
    def test_merge_properties_invalid_props(self):
        """Test that invalid properties are skipped with warning."""
        overrides = {
            "properties": {
                "Student": ["fullName", "invalidProp", "anotherInvalid"]
            }
        }
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = merge_allow_list_overrides(self.base_allow_list, overrides, self.live_schema)
        
        # Check that only valid properties were added
        expected_student_props = ["age", "fullName", "name"]
        self.assertEqual(sorted(result["properties"]["Student"]), expected_student_props)
        
        # Check that warning was logged for invalid properties
        mock_logger.warning.assert_called_with(
            "Skipping unknown properties for label 'Student' from overrides: ['anotherInvalid', 'invalidProp']"
        )
    
    def test_merge_empty_overrides(self):
        """Test that empty overrides don't change the base allow-list."""
        overrides = {}
        
        result = merge_allow_list_overrides(self.base_allow_list, overrides, self.live_schema)
        
        # Should be identical to base
        self.assertEqual(result, self.base_allow_list)
    
    def test_merge_no_valid_overrides(self):
        """Test that when no overrides are valid, base allow-list is unchanged."""
        overrides = {
            "node_labels": ["UnknownLabel"],
            "relationships": ["UnknownRel"],
            "properties": {
                "UnknownLabel": ["someProp"]
            }
        }
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = merge_allow_list_overrides(self.base_allow_list, overrides, self.live_schema)
        
        # Should be identical to base
        self.assertEqual(result, self.base_allow_list)
        
        # Should have logged warnings
        self.assertEqual(mock_logger.warning.call_count, 3)


class TestLoadAllowListOverrides(unittest.TestCase):
    """Test loading allow-list overrides from file."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test_overrides.json")
    
    def tearDown(self):
        """Clean up test environment."""
        try:
            if os.path.exists(self.test_file):
                os.remove(self.test_file)
            os.rmdir(self.test_dir)
        except (PermissionError, OSError):
            # Handle Windows permission issues
            pass
    
    def test_load_overrides_file_exists(self):
        """Test loading overrides when file exists."""
        overrides_data = {
            "relationships": ["HAS_GOAL", "FOR_STUDENT"],
            "node_labels": ["Goal"],
            "properties": {
                "Student": ["fullName"]
            }
        }
        
        with open(self.test_file, 'w') as f:
            json.dump(overrides_data, f)
        
        result = load_allow_list_overrides(self.test_file)
        
        self.assertIsNotNone(result)
        self.assertEqual(result, overrides_data)
    
    def test_load_overrides_file_missing(self):
        """Test loading overrides when file is missing."""
        result = load_allow_list_overrides(self.test_file)
        
        self.assertIsNone(result)
    
    def test_load_overrides_invalid_json(self):
        """Test loading overrides with invalid JSON."""
        with open(self.test_file, 'w') as f:
            f.write("invalid json content")
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = load_allow_list_overrides(self.test_file)
        
        self.assertIsNone(result)
        mock_logger.warning.assert_called_once()
        self.assertIn("invalid JSON", mock_logger.warning.call_args[0][0])
    
    def test_load_overrides_invalid_structure(self):
        """Test loading overrides with invalid structure."""
        with open(self.test_file, 'w') as f:
            json.dump("not a dict", f)
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = load_allow_list_overrides(self.test_file)
        
        self.assertIsNone(result)
        mock_logger.warning.assert_called_once()
        self.assertIn("invalid structure", mock_logger.warning.call_args[0][0])
    
    def test_load_overrides_empty_file(self):
        """Test loading overrides from empty file."""
        with open(self.test_file, 'w') as f:
            f.write("")
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = load_allow_list_overrides(self.test_file)
        
        self.assertIsNone(result)
        mock_logger.warning.assert_called_once()
    
    def test_load_overrides_partial_structure(self):
        """Test loading overrides with partial structure."""
        overrides_data = {
            "relationships": ["HAS_GOAL"]
            # Missing node_labels and properties
        }
        
        with open(self.test_file, 'w') as f:
            json.dump(overrides_data, f)
        
        result = load_allow_list_overrides(self.test_file)
        
        self.assertIsNotNone(result)
        self.assertEqual(result, overrides_data)
    
    def test_load_overrides_default_path(self):
        """Test loading overrides with default path."""
        # Test with non-existent default path by patching the default path
        with patch('graph_rag.schema_manager.load_allow_list_overrides') as mock_load:
            mock_load.return_value = None
            result = load_allow_list_overrides("non_existent_file.json")
            self.assertIsNone(result)


class TestAllowListMergeIntegration(unittest.TestCase):
    """Integration tests for allow-list merge functionality."""
    
    def test_full_merge_workflow(self):
        """Test the complete merge workflow with realistic data."""
        # Base allow-list from Neo4j schema extraction
        base_allow_list = {
            "node_labels": ["Student", "Staff", "Document", "Chunk"],
            "relationship_types": ["MENTIONS", "HAS_CHUNK", "PART_OF"],
            "properties": {
                "Student": ["name", "age"],
                "Staff": ["title", "department"],
                "Document": ["content", "type"],
                "Chunk": ["text", "index"]
            }
        }
        
        # Live schema (what actually exists in Neo4j)
        live_schema = {
            "node_labels": ["Student", "Staff", "Document", "Chunk", "Goal", "Plan"],
            "relationship_types": ["MENTIONS", "HAS_CHUNK", "PART_OF", "HAS_GOAL", "FOR_STUDENT", "HAS_PLAN"],
            "properties": {
                "Student": ["name", "age", "fullName", "studentId"],
                "Staff": ["title", "department", "email"],
                "Document": ["content", "type"],
                "Chunk": ["text", "index"],
                "Goal": ["title", "status", "target"],
                "Plan": ["name", "type", "status"]
            }
        }
        
        # Overrides to add domain-specific relationships
        overrides = {
            "relationships": ["HAS_GOAL", "FOR_STUDENT", "HAS_PLAN", "UNKNOWN_REL"],
            "node_labels": ["Goal", "Plan", "UnknownLabel"],
            "properties": {
                "Student": ["fullName", "studentId", "invalidProp"],
                "Goal": ["title", "status"],
                "UnknownLabel": ["someProp"]
            }
        }
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = merge_allow_list_overrides(base_allow_list, overrides, live_schema)
        
        # Verify relationships were merged correctly
        expected_relationships = ["FOR_STUDENT", "HAS_CHUNK", "HAS_GOAL", "HAS_PLAN", "MENTIONS", "PART_OF"]
        self.assertEqual(sorted(result["relationship_types"]), expected_relationships)
        
        # Verify labels were merged correctly
        expected_labels = ["Chunk", "Document", "Goal", "Plan", "Staff", "Student"]
        self.assertEqual(sorted(result["node_labels"]), expected_labels)
        
        # Verify properties were merged correctly
        expected_student_props = ["age", "fullName", "name", "studentId"]
        expected_goal_props = ["status", "title"]  # Only the properties from overrides, not live schema
        
        self.assertEqual(sorted(result["properties"]["Student"]), expected_student_props)
        self.assertEqual(sorted(result["properties"]["Goal"]), expected_goal_props)
        
        # Verify warnings were logged for invalid elements
        warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
        
        self.assertTrue(any("unknown relationship types" in call for call in warning_calls))
        self.assertTrue(any("unknown node labels" in call for call in warning_calls))
        self.assertTrue(any("unknown properties" in call for call in warning_calls))
        self.assertTrue(any("unknown label" in call for call in warning_calls))


if __name__ == '__main__':
    unittest.main()
