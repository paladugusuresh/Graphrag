# tests/test_synonyms_loader.py
"""
Test synonyms loader functionality.
"""
import unittest
import json
import tempfile
import os
from unittest.mock import patch

from graph_rag.schema_manager import load_synonyms_optional


class TestSynonymsLoader(unittest.TestCase):
    """Test synonyms loader functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test_synonyms.json")
    
    def tearDown(self):
        """Clean up test fixtures."""
        try:
            if os.path.exists(self.test_file):
                if os.path.isdir(self.test_file):
                    os.rmdir(self.test_file)
                else:
                    os.remove(self.test_file)
            if os.path.exists(self.temp_dir):
                os.rmdir(self.temp_dir)
        except (PermissionError, OSError):
            # Ignore cleanup errors in tests
            pass
    
    def test_load_synonyms_file_missing(self):
        """Test loading synonyms when file is missing."""
        result = load_synonyms_optional("nonexistent_file.json")
        self.assertIsNone(result)
    
    def test_load_synonyms_file_malformed_json(self):
        """Test loading synonyms when file contains malformed JSON."""
        with open(self.test_file, 'w') as f:
            f.write('{"labels": {"Person": ["Student"]')  # Missing closing brace
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = load_synonyms_optional(self.test_file)
            
        self.assertIsNone(result)
        mock_logger.warning.assert_called_once()
        self.assertIn("invalid JSON", mock_logger.warning.call_args[0][0])
    
    def test_load_synonyms_file_invalid_structure(self):
        """Test loading synonyms when file has invalid structure."""
        with open(self.test_file, 'w') as f:
            json.dump("invalid_string", f)  # Should be dict, not string
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = load_synonyms_optional(self.test_file)
            
        self.assertIsNone(result)
        mock_logger.warning.assert_called_once()
        self.assertIn("invalid structure", mock_logger.warning.call_args[0][0])
    
    def test_load_synonyms_file_present(self):
        """Test loading synonyms when file is present and valid."""
        synonyms_data = {
            "labels": {
                "Person": ["Student", "Pupil"],
                "Company": ["Organization", "Corporation"]
            },
            "relationships": {
                "WORKS_FOR": ["EMPLOYED_BY", "WORKS_AT"]
            },
            "properties": {
                "name": ["title", "identifier"]
            }
        }
        
        with open(self.test_file, 'w') as f:
            json.dump(synonyms_data, f)
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = load_synonyms_optional(self.test_file)
        
        self.assertIsNotNone(result)
        self.assertEqual(result, synonyms_data)
        
        # Check debug log was called
        mock_logger.debug.assert_called_once()
        debug_msg = mock_logger.debug.call_args[0][0]
        self.assertIn("Loaded synonyms (labels:2, rels:1, props:1)", debug_msg)
    
    def test_load_synonyms_file_empty(self):
        """Test loading synonyms when file is empty."""
        with open(self.test_file, 'w') as f:
            json.dump({}, f)
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = load_synonyms_optional(self.test_file)
        
        self.assertIsNotNone(result)
        self.assertEqual(result, {})
        
        # Check debug log was called
        mock_logger.debug.assert_called_once()
        debug_msg = mock_logger.debug.call_args[0][0]
        self.assertIn("Loaded synonyms (labels:0, rels:0, props:0)", debug_msg)
    
    def test_load_synonyms_file_partial_structure(self):
        """Test loading synonyms when file has partial structure."""
        synonyms_data = {
            "labels": {
                "Person": ["Student", "Pupil"]
            }
            # Missing relationships and properties
        }
        
        with open(self.test_file, 'w') as f:
            json.dump(synonyms_data, f)
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = load_synonyms_optional(self.test_file)
        
        self.assertIsNotNone(result)
        self.assertEqual(result, synonyms_data)
        
        # Check debug log was called
        mock_logger.debug.assert_called_once()
        debug_msg = mock_logger.debug.call_args[0][0]
        self.assertIn("Loaded synonyms (labels:1, rels:0, props:0)", debug_msg)
    
    def test_load_synonyms_file_io_error(self):
        """Test loading synonyms when file cannot be read."""
        # Create a directory with the same name as the file to cause IO error
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.temp_dir)
        os.makedirs(self.test_file)
        
        with patch('graph_rag.schema_manager.logger') as mock_logger:
            result = load_synonyms_optional(self.test_file)
        
        self.assertIsNone(result)
        mock_logger.warning.assert_called_once()
        self.assertIn("Failed to load synonyms", mock_logger.warning.call_args[0][0])
    
    def test_load_synonyms_default_path(self):
        """Test loading synonyms with default path."""
        # Test that it doesn't crash with default path
        # Use a non-existent path to ensure it returns None
        result = load_synonyms_optional("nonexistent_default.json")
        self.assertIsNone(result)
    
    def test_load_synonyms_integration_with_schema_embeddings(self):
        """Test that synonyms integrate correctly with schema embeddings."""
        synonyms_data = {
            "labels": {
                "Person": ["Student", "Pupil"]
            },
            "relationships": {
                "WORKS_FOR": ["EMPLOYED_BY"]
            },
            "properties": {
                "name": ["title"]
            }
        }
        
        with open(self.test_file, 'w') as f:
            json.dump(synonyms_data, f)
        
        # Test the integration by importing and calling collect_schema_terms
        from graph_rag.schema_embeddings import collect_schema_terms
        
        # Mock the allow_list.json to avoid file dependency
        mock_allow_list = {
            "node_labels": ["Person", "Company"],
            "relationship_types": ["WORKS_FOR", "MENTIONS"],
            "properties": {
                "Person": ["name", "age"],
                "Company": ["name", "founded"]
            }
        }
        
        with patch('graph_rag.schema_embeddings.get_config_value') as mock_config, \
             patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps(mock_allow_list))), \
             patch('os.path.exists', return_value=True), \
             patch('graph_rag.schema_manager.load_synonyms_optional', return_value=synonyms_data):
            
            # Mock config to return the test file path for allow_list
            mock_config.side_effect = lambda key, default: self.test_file if key == 'schema.allow_list_path' else default
            
            terms = collect_schema_terms()
        
        # Verify that synonyms were added
        person_synonyms = [t for t in terms if t['canonical_id'] == 'Person' and t['term'] != 'Person']
        works_for_synonyms = [t for t in terms if t['canonical_id'] == 'WORKS_FOR' and t['term'] != 'WORKS_FOR']
        name_synonyms = [t for t in terms if t['canonical_id'] == 'name' and t['term'] != 'name']
        
        self.assertEqual(len(person_synonyms), 2)  # Student, Pupil
        self.assertEqual(len(works_for_synonyms), 1)  # EMPLOYED_BY
        self.assertEqual(len(name_synonyms), 1)  # title
        
        # Verify synonym structure
        student_term = next(t for t in terms if t['term'] == 'Student')
        self.assertEqual(student_term['canonical_id'], 'Person')
        self.assertEqual(student_term['type'], 'label')
        self.assertEqual(student_term['id'], 'label:Student')


if __name__ == '__main__':
    unittest.main()
