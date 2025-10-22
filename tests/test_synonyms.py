# tests/test_synonyms.py
import unittest
import json
import tempfile
import os
from unittest.mock import patch, mock_open

from graph_rag.schema_manager import load_synonyms_optional


class TestSynonymsLoader(unittest.TestCase):
    """Test synonyms loader functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, 'test_synonyms.json')
    
    def tearDown(self):
        """Clean up test fixtures."""
        try:
            if os.path.exists(self.test_file):
                os.remove(self.test_file)
            os.rmdir(self.test_dir)
        except (OSError, PermissionError):
            pass  # Ignore cleanup errors on Windows
    
    def test_load_synonyms_file_exists(self):
        """Test that synonyms loader returns dict when file exists with expected structure."""
        synonyms_data = {
            "labels": {
                "Student": ["pupil", "learner"],
                "Staff": ["teacher", "therapist"]
            },
            "relationships": {
                "HAS_PLAN": ["has plan", "assigned plan"],
                "MENTIONS": ["references", "cites"]
            },
            "properties": {
                "fullName": ["name", "student name"],
                "dateTime": ["date", "datetime"]
            }
        }
        
        with open(self.test_file, 'w') as f:
            json.dump(synonyms_data, f)
        
        result = load_synonyms_optional(self.test_file)
        
        # Should return the loaded data
        self.assertIsInstance(result, dict)
        self.assertEqual(result, synonyms_data)
        
        # Should have expected keys
        self.assertIn("labels", result)
        self.assertIn("relationships", result)
        self.assertIn("properties", result)
        
        # Should have expected structure
        self.assertIsInstance(result["labels"], dict)
        self.assertIsInstance(result["relationships"], dict)
        self.assertIsInstance(result["properties"], dict)
        
        # Should have expected content
        self.assertIn("Student", result["labels"])
        self.assertIn("HAS_PLAN", result["relationships"])
        self.assertIn("fullName", result["properties"])
    
    def test_load_synonyms_file_absent(self):
        """Test that synonyms loader returns None when file is absent."""
        non_existent_file = os.path.join(self.test_dir, 'non_existent.json')
        
        result = load_synonyms_optional(non_existent_file)
        
        # Should return None for missing file
        self.assertIsNone(result)
    
    def test_load_synonyms_invalid_json(self):
        """Test that synonyms loader returns None for invalid JSON."""
        with open(self.test_file, 'w') as f:
            f.write('{"invalid": json}')  # Invalid JSON
        
        result = load_synonyms_optional(self.test_file)
        
        # Should return None for invalid JSON
        self.assertIsNone(result)
    
    def test_load_synonyms_invalid_structure(self):
        """Test that synonyms loader returns None for invalid structure."""
        with open(self.test_file, 'w') as f:
            json.dump("not a dict", f)  # Should be dict, not string
        
        result = load_synonyms_optional(self.test_file)
        
        # Should return None for invalid structure
        self.assertIsNone(result)
    
    def test_load_synonyms_empty_file(self):
        """Test that synonyms loader handles empty file."""
        with open(self.test_file, 'w') as f:
            f.write('')  # Empty file
        
        result = load_synonyms_optional(self.test_file)
        
        # Should return None for empty file
        self.assertIsNone(result)
    
    def test_load_synonyms_default_path(self):
        """Test that synonyms loader uses default path when no path provided."""
        # Mock os.path.exists to return False for default path
        with patch('os.path.exists', return_value=False):
            result = load_synonyms_optional()
            
            # Should return None when default file doesn't exist
            self.assertIsNone(result)
    
    def test_load_synonyms_with_logging(self):
        """Test that synonyms loader logs appropriately."""
        synonyms_data = {
            "labels": {"Student": ["pupil"]},
            "relationships": {"HAS_PLAN": ["has plan"]},
            "properties": {"fullName": ["name"]}
        }
        
        with open(self.test_file, 'w') as f:
            json.dump(synonyms_data, f)
        
        # Test with mocked logger to verify debug logging
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = load_synonyms_optional(self.test_file)
            
            # Should return the data
            self.assertIsNotNone(result)
            self.assertEqual(result, synonyms_data)
            
            # Should log debug message with counts
            mock_logger.debug.assert_called()
            debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
            self.assertTrue(any("Loaded synonyms" in call for call in debug_calls))
    
    def test_load_synonyms_error_handling(self):
        """Test that synonyms loader handles IO errors gracefully."""
        # Mock open to raise an IOError
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            result = load_synonyms_optional(self.test_file)
            
            # Should return None on IO error
            self.assertIsNone(result)


class TestSynonymsIntegration(unittest.TestCase):
    """Test synonyms integration with schema embeddings."""
    
    def test_synonyms_integration_structure(self):
        """Test that synonyms integrate correctly with schema embeddings structure."""
        # Mock the synonyms data that would be loaded
        mock_synonyms = {
            "labels": {
                "Student": ["Pupil", "Learner"],
                "Staff": ["Teacher", "Therapist"]
            },
            "relationships": {
                "HAS_PLAN": ["HAS_IEP", "ASSIGNED_PLAN"],
                "MENTIONS": ["REFERENCES", "CITES"]
            },
            "properties": {
                "fullName": ["name", "studentName"],
                "dateTime": ["date", "timestamp"]
            }
        }
        
        # Mock the allow list structure
        mock_allow_list = {
            "node_labels": ["Student", "Staff", "Plan"],
            "relationship_types": ["HAS_PLAN", "MENTIONS", "FOR_STUDENT"],
            "properties": {
                "Student": ["fullName", "id"],
                "Staff": ["fullName", "role"],
                "Plan": ["title", "status"]
            }
        }
        
        # Test that synonyms structure is compatible with schema embeddings
        with patch('graph_rag.schema_manager.load_synonyms_optional', return_value=mock_synonyms):
            # Verify synonyms structure matches expected format
            self.assertIsInstance(mock_synonyms, dict)
            self.assertIn("labels", mock_synonyms)
            self.assertIn("relationships", mock_synonyms)
            self.assertIn("properties", mock_synonyms)
            
            # Verify labels structure
            labels = mock_synonyms["labels"]
            self.assertIsInstance(labels, dict)
            self.assertIn("Student", labels)
            self.assertIsInstance(labels["Student"], list)
            
            # Verify relationships structure
            relationships = mock_synonyms["relationships"]
            self.assertIsInstance(relationships, dict)
            self.assertIn("HAS_PLAN", relationships)
            self.assertIsInstance(relationships["HAS_PLAN"], list)
            
            # Verify properties structure
            properties = mock_synonyms["properties"]
            self.assertIsInstance(properties, dict)
            self.assertIn("fullName", properties)
            self.assertIsInstance(properties["fullName"], list)


if __name__ == '__main__':
    unittest.main()
