import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json
import tempfile
import shutil

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.schema_manager import (
    _compute_fingerprint,
    _read_fingerprint,
    _write_fingerprint,
    _is_write_allowed,
    get_schema_fingerprint,
    ensure_schema_loaded
)


class TestSchemaFingerprint(unittest.TestCase):
    """Tests for schema fingerprinting functionality"""

    def test_compute_fingerprint_deterministic(self):
        """Test that fingerprint computation is deterministic"""
        allow_list = {
            "node_labels": ["Person", "Company"],
            "relationship_types": ["WORKS_AT"],
            "properties": {"Person": ["name", "age"]}
        }
        
        fp1 = _compute_fingerprint(allow_list)
        fp2 = _compute_fingerprint(allow_list)
        
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 64)  # SHA256 hex digest

    def test_compute_fingerprint_order_independent(self):
        """Test that fingerprint is same regardless of key order (sorted internally)"""
        allow_list1 = {
            "node_labels": ["Person", "Company"],
            "relationship_types": ["WORKS_AT"],
            "properties": {}
        }
        
        allow_list2 = {
            "relationship_types": ["WORKS_AT"],
            "properties": {},
            "node_labels": ["Person", "Company"]
        }
        
        fp1 = _compute_fingerprint(allow_list1)
        fp2 = _compute_fingerprint(allow_list2)
        
        self.assertEqual(fp1, fp2)

    def test_compute_fingerprint_content_sensitive(self):
        """Test that different content produces different fingerprints"""
        allow_list1 = {
            "node_labels": ["Person"],
            "relationship_types": [],
            "properties": {}
        }
        
        allow_list2 = {
            "node_labels": ["Person", "Company"],
            "relationship_types": [],
            "properties": {}
        }
        
        fp1 = _compute_fingerprint(allow_list1)
        fp2 = _compute_fingerprint(allow_list2)
        
        self.assertNotEqual(fp1, fp2)

    def test_read_fingerprint_file_exists(self):
        """Test reading fingerprint from file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("abc123def456")
            temp_path = f.name
        
        try:
            result = _read_fingerprint(temp_path)
            self.assertEqual(result, "abc123def456")
        finally:
            os.unlink(temp_path)

    def test_read_fingerprint_file_not_exists(self):
        """Test reading fingerprint when file doesn't exist"""
        result = _read_fingerprint("/nonexistent/path/fingerprint.txt")
        self.assertEqual(result, "")

    def test_write_fingerprint(self):
        """Test writing fingerprint to file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            fp_path = os.path.join(temp_dir, "test_fingerprint")
            _write_fingerprint("test123abc", fp_path)
            
            with open(fp_path, 'r') as f:
                content = f.read()
            
            self.assertEqual(content, "test123abc")

    @patch.dict(os.environ, {"APP_MODE": "admin"}, clear=True)
    def test_is_write_allowed_admin_mode(self):
        """Test write permission in admin mode"""
        self.assertTrue(_is_write_allowed())

    @patch.dict(os.environ, {"APP_MODE": "read_only", "ALLOW_WRITES": "true"}, clear=True)
    def test_is_write_allowed_explicit_writes(self):
        """Test write permission with ALLOW_WRITES=true"""
        self.assertTrue(_is_write_allowed())

    @patch.dict(os.environ, {"APP_MODE": "read_only", "ALLOW_WRITES": "false"}, clear=True)
    def test_is_write_allowed_read_only(self):
        """Test write permission denied in read-only mode"""
        self.assertFalse(_is_write_allowed())

    @patch.dict(os.environ, {}, clear=True)
    def test_is_write_allowed_defaults_read_only(self):
        """Test write permission defaults to read-only"""
        self.assertFalse(_is_write_allowed())


class TestEnsureSchemaLoadedIdempotent(unittest.TestCase):
    """Tests for idempotent schema loading behavior"""

    def setUp(self):
        """Create temporary directory for test files"""
        self.temp_dir = tempfile.mkdtemp()
        self.allow_list_path = os.path.join(self.temp_dir, "allow_list.json")
        self.fingerprint_path = os.path.join(self.temp_dir, ".schema_fingerprint")
        
        self.test_allow_list = {
            "node_labels": ["Document", "Chunk"],
            "relationship_types": ["HAS_CHUNK"],
            "properties": {}
        }

    def tearDown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir)

    @patch("graph_rag.schema_manager.get_config_value")
    @patch.dict(os.environ, {"APP_MODE": "read_only"}, clear=True)
    def test_read_only_mode_loads_existing(self, mock_config):
        """Test that read-only mode loads existing allow-list without regeneration"""
        mock_config.return_value = self.allow_list_path
        
        # Write existing allow list
        with open(self.allow_list_path, 'w') as f:
            json.dump(self.test_allow_list, f)
        
        result = ensure_schema_loaded()
        
        self.assertEqual(result, self.test_allow_list)
        # Fingerprint should not be created in read-only mode
        self.assertFalse(os.path.exists(self.fingerprint_path))

    @patch("graph_rag.schema_manager.get_config_value")
    @patch.dict(os.environ, {"APP_MODE": "read_only"}, clear=True)
    def test_read_only_mode_fails_without_allow_list(self, mock_config):
        """Test that read-only mode raises error if allow-list doesn't exist"""
        mock_config.return_value = self.allow_list_path
        
        with self.assertRaises(FileNotFoundError) as cm:
            ensure_schema_loaded()
        
        self.assertIn("APP_MODE=admin", str(cm.exception))

    @patch("graph_rag.schema_manager.get_config_value")
    @patch("graph_rag.schema_catalog.generate_schema_allow_list")
    @patch.dict(os.environ, {"APP_MODE": "admin"}, clear=True)
    def test_admin_mode_generates_schema_first_time(self, mock_generate, mock_config):
        """Test that admin mode generates schema on first run"""
        mock_config.return_value = self.allow_list_path
        mock_generate.return_value = self.test_allow_list
        
        with patch("graph_rag.schema_manager._write_fingerprint") as mock_write_fp:
            result = ensure_schema_loaded()
            
            self.assertEqual(result, self.test_allow_list)
            # generate_schema_allow_list should be called with the path
            mock_generate.assert_called_once_with(self.allow_list_path)
            # Fingerprint write should be called
            mock_write_fp.assert_called_once()

    @patch("graph_rag.schema_manager.get_config_value")
    @patch("graph_rag.schema_catalog.generate_schema_allow_list")
    @patch.dict(os.environ, {"APP_MODE": "admin"}, clear=True)
    def test_admin_mode_skips_regeneration_when_unchanged(self, mock_generate, mock_config):
        """Test that second boot skips regeneration when fingerprint unchanged"""
        mock_config.return_value = self.allow_list_path
        
        # First boot: create allow list and fingerprint
        with open(self.allow_list_path, 'w') as f:
            json.dump(self.test_allow_list, f)
        
        fingerprint = _compute_fingerprint(self.test_allow_list)
        with open(self.fingerprint_path, 'w') as f:
            f.write(fingerprint)
        
        # Second boot: should skip regeneration
        result = ensure_schema_loaded()
        
        self.assertEqual(result, self.test_allow_list)
        # generate_schema_allow_list should NOT be called
        mock_generate.assert_not_called()

    @patch("graph_rag.schema_manager.get_config_value")
    @patch("graph_rag.schema_catalog.generate_schema_allow_list")
    @patch.dict(os.environ, {"APP_MODE": "admin"}, clear=True)
    def test_admin_mode_regenerates_when_fingerprint_changed(self, mock_generate, mock_config):
        """Test that schema is regenerated when fingerprint changes"""
        mock_config.return_value = self.allow_list_path
        
        # Create old allow list with old fingerprint
        old_allow_list = {"node_labels": ["Old"], "relationship_types": [], "properties": {}}
        with open(self.allow_list_path, 'w') as f:
            json.dump(old_allow_list, f)
        
        # Write WRONG fingerprint to simulate schema change
        with open(self.fingerprint_path, 'w') as f:
            f.write("old_fingerprint_that_doesnt_match")
        
        # Mock new schema generation
        mock_generate.return_value = self.test_allow_list
        
        result = ensure_schema_loaded()
        
        self.assertEqual(result, self.test_allow_list)
        # Should regenerate because fingerprint doesn't match
        mock_generate.assert_called_once()

    @patch("graph_rag.schema_manager.get_config_value")
    @patch("graph_rag.schema_catalog.generate_schema_allow_list")
    @patch.dict(os.environ, {"APP_MODE": "admin"}, clear=True)
    def test_force_refresh_ignores_fingerprint(self, mock_generate, mock_config):
        """Test that force=True always regenerates regardless of fingerprint"""
        mock_config.return_value = self.allow_list_path
        
        # Create existing allow list with matching fingerprint
        with open(self.allow_list_path, 'w') as f:
            json.dump(self.test_allow_list, f)
        
        fingerprint = _compute_fingerprint(self.test_allow_list)
        with open(self.fingerprint_path, 'w') as f:
            f.write(fingerprint)
        
        # Mock new schema generation
        new_allow_list = {"node_labels": ["New"], "relationship_types": [], "properties": {}}
        mock_generate.return_value = new_allow_list
        
        # Call with force=True
        result = ensure_schema_loaded(force=True)
        
        self.assertEqual(result, new_allow_list)
        # Should regenerate even though fingerprint matches
        mock_generate.assert_called_once()


class TestGetSchemaFingerprint(unittest.TestCase):
    """Tests for get_schema_fingerprint public API"""

    @patch("graph_rag.schema_catalog.generate_schema_allow_list")
    def test_get_schema_fingerprint_success(self, mock_generate):
        """Test successful fingerprint computation from live database"""
        test_allow_list = {
            "node_labels": ["Person", "Company"],
            "relationship_types": ["WORKS_AT"],
            "properties": {}
        }
        mock_generate.return_value = test_allow_list
        
        result = get_schema_fingerprint()
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 64)  # SHA256 hex digest
        # Verify it matches computed fingerprint
        self.assertEqual(result, _compute_fingerprint(test_allow_list))
        # Verify it called with write_to_disk=False
        mock_generate.assert_called_once_with(allow_list_path=None, write_to_disk=False)

    @patch("graph_rag.schema_catalog.generate_schema_allow_list")
    def test_get_schema_fingerprint_failure(self, mock_generate):
        """Test fingerprint computation returns None on error"""
        mock_generate.side_effect = Exception("Database connection failed")
        
        result = get_schema_fingerprint()
        
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()

