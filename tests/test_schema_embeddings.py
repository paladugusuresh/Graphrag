import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
import sys

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.schema_embeddings import collect_schema_terms, compute_embeddings, generate_schema_embeddings

class TestSchemaEmbeddings(unittest.TestCase):

    def setUp(self):
        # Clear module cache
        for module_name in ['graph_rag.schema_embeddings', 'graph_rag.embeddings']:
            if module_name in sys.modules:
                del sys.modules[module_name]

    @patch("builtins.open", new_callable=mock_open)
    def test_collect_schema_terms_basic(self, mock_file_open):
        """Test collecting schema terms from allow_list.json without synonyms."""
        
        # Mock config.yaml
        config_data = json.dumps({
            "schema": {"allow_list_path": "allow_list.json"},
            "schema_embeddings": {"include_synonyms_path": "schema_synonyms.json"}
        })
        
        # Mock allow_list.json
        allow_list_data = json.dumps({
            "node_labels": ["Person", "Organization", "Product"],
            "relationship_types": ["FOUNDED", "HAS_PRODUCT"],
            "properties": {
                "Person": ["name", "age"],
                "Organization": ["name", "industry"],
                "Product": ["name", "price"]
            }
        })
        
        # Configure mock to return different content for different files
        def mock_open_side_effect(filename, mode='r'):
            if filename == "config.yaml":
                return mock_open(read_data=config_data).return_value
            elif filename == "allow_list.json":
                return mock_open(read_data=allow_list_data).return_value
            else:
                raise FileNotFoundError(f"File not found: {filename}")
        
        mock_file_open.side_effect = mock_open_side_effect
        
        # Mock os.path.exists to return False for synonyms file
        with patch("os.path.exists", return_value=False):
            terms = collect_schema_terms()
        
        # Verify results
        self.assertGreater(len(terms), 0)
        
        # Check node labels
        label_terms = [t for t in terms if t['type'] == 'label']
        self.assertEqual(len(label_terms), 3)
        self.assertIn({"id": "label:Person", "term": "Person", "type": "label", "canonical_id": "Person"}, label_terms)
        self.assertIn({"id": "label:Organization", "term": "Organization", "type": "label", "canonical_id": "Organization"}, label_terms)
        self.assertIn({"id": "label:Product", "term": "Product", "type": "label", "canonical_id": "Product"}, label_terms)
        
        # Check relationship types
        rel_terms = [t for t in terms if t['type'] == 'relationship']
        self.assertEqual(len(rel_terms), 2)
        self.assertIn({"id": "relationship:FOUNDED", "term": "FOUNDED", "type": "relationship", "canonical_id": "FOUNDED"}, rel_terms)
        self.assertIn({"id": "relationship:HAS_PRODUCT", "term": "HAS_PRODUCT", "type": "relationship", "canonical_id": "HAS_PRODUCT"}, rel_terms)
        
        # Check properties (should be unique across all node types)
        prop_terms = [t for t in terms if t['type'] == 'property']
        expected_props = {"name", "age", "industry", "price"}  # unique properties
        actual_props = {t['term'] for t in prop_terms}
        self.assertEqual(actual_props, expected_props)

    @patch("builtins.open", new_callable=mock_open)
    def test_collect_schema_terms_with_synonyms(self, mock_file_open):
        """Test collecting schema terms with synonyms file."""
        
        # Mock config.yaml
        config_data = json.dumps({
            "schema": {"allow_list_path": "allow_list.json"},
            "schema_embeddings": {"include_synonyms_path": "schema_synonyms.json"}
        })
        
        # Mock allow_list.json
        allow_list_data = json.dumps({
            "node_labels": ["Person", "Organization"],
            "relationship_types": ["FOUNDED"],
            "properties": {"Person": ["name"]}
        })
        
        # Mock schema_synonyms.json
        synonyms_data = json.dumps({
            "label": {
                "Person": ["Individual", "Human"],
                "Organization": ["Company", "Business"]
            },
            "relationship": {
                "FOUNDED": ["CREATED", "ESTABLISHED"]
            },
            "property": {
                "name": ["title", "label"]
            }
        })
        
        # Configure mock to return different content for different files
        def mock_open_side_effect(filename, mode='r'):
            if filename == "config.yaml":
                return mock_open(read_data=config_data).return_value
            elif filename == "allow_list.json":
                return mock_open(read_data=allow_list_data).return_value
            elif filename == "schema_synonyms.json":
                return mock_open(read_data=synonyms_data).return_value
            else:
                raise FileNotFoundError(f"File not found: {filename}")
        
        mock_file_open.side_effect = mock_open_side_effect
        
        # Mock os.path.exists to return True for synonyms file
        with patch("os.path.exists", return_value=True):
            terms = collect_schema_terms()
        
        # Verify results include both canonical terms and synonyms
        self.assertGreater(len(terms), 4)  # Should have more than just the 4 canonical terms
        
        # Check that canonical terms exist
        canonical_terms = [t for t in terms if t['term'] == t['canonical_id']]
        self.assertEqual(len(canonical_terms), 4)  # 2 labels + 1 relationship + 1 property
        
        # Check that synonyms exist and point to canonical terms
        synonym_terms = [t for t in terms if t['term'] != t['canonical_id']]
        self.assertGreater(len(synonym_terms), 0)
        
        # Check specific synonyms
        person_synonyms = [t for t in synonym_terms if t['canonical_id'] == 'Person' and t['type'] == 'label']
        self.assertEqual(len(person_synonyms), 2)
        synonym_terms_set = {t['term'] for t in person_synonyms}
        self.assertEqual(synonym_terms_set, {"Individual", "Human"})

    @patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
    @patch("graph_rag.schema_embeddings.get_embedding_provider")
    def test_compute_embeddings(self, mock_get_embedding_provider):
        """Test computing embeddings for terms."""
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [
            [0.1, 0.2, 0.3],  # embedding for "Person"
            [0.4, 0.5, 0.6],  # embedding for "Organization"
            [0.7, 0.8, 0.9]   # embedding for "FOUNDED"
        ]
        mock_get_embedding_provider.return_value = mock_provider
        
        terms = ["Person", "Organization", "FOUNDED"]
        embeddings = compute_embeddings(terms)
        
        # Verify embeddings
        self.assertEqual(len(embeddings), 3)
        self.assertEqual(embeddings[0], [0.1, 0.2, 0.3])
        self.assertEqual(embeddings[1], [0.4, 0.5, 0.6])
        self.assertEqual(embeddings[2], [0.7, 0.8, 0.9])
        
        # Verify embedding provider was called correctly
        mock_provider.get_embeddings.assert_called_once_with(terms)

    def test_compute_embeddings_empty_list(self):
        """Test computing embeddings for empty list."""
        embeddings = compute_embeddings([])
        self.assertEqual(embeddings, [])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
    @patch("graph_rag.schema_embeddings.get_embedding_provider")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_schema_embeddings(self, mock_file_open, mock_get_embedding_provider):
        """Test generating complete schema embeddings."""
        
        # Mock config.yaml
        config_data = json.dumps({
            "schema": {"allow_list_path": "allow_list.json"},
            "schema_embeddings": {"include_synonyms_path": "schema_synonyms.json"}
        })
        
        # Mock allow_list.json
        allow_list_data = json.dumps({
            "node_labels": ["Person"],
            "relationship_types": ["FOUNDED"],
            "properties": {"Person": ["name"]}
        })
        
        # Configure mock files
        def mock_open_side_effect(filename, mode='r'):
            if filename == "config.yaml":
                return mock_open(read_data=config_data).return_value
            elif filename == "allow_list.json":
                return mock_open(read_data=allow_list_data).return_value
            else:
                raise FileNotFoundError(f"File not found: {filename}")
        
        mock_file_open.side_effect = mock_open_side_effect
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [
            [0.1, 0.2, 0.3],  # embedding for "Person"
            [0.4, 0.5, 0.6],  # embedding for "FOUNDED"
            [0.7, 0.8, 0.9]   # embedding for "name"
        ]
        mock_get_embedding_provider.return_value = mock_provider
        
        # Mock os.path.exists to return False for synonyms file
        with patch("os.path.exists", return_value=False):
            result = generate_schema_embeddings()
        
        # Verify results
        self.assertEqual(len(result), 3)
        
        # Check that each result has all required fields
        for item in result:
            self.assertIn("id", item)
            self.assertIn("term", item)
            self.assertIn("type", item)
            self.assertIn("canonical_id", item)
            self.assertIn("embedding", item)
            self.assertIsInstance(item["embedding"], list)
            self.assertEqual(len(item["embedding"]), 3)
        
        # Check specific items
        person_item = next(item for item in result if item["term"] == "Person")
        self.assertEqual(person_item["id"], "label:Person")
        self.assertEqual(person_item["type"], "label")
        self.assertEqual(person_item["canonical_id"], "Person")
        self.assertEqual(person_item["embedding"], [0.1, 0.2, 0.3])

    @patch("builtins.open", new_callable=mock_open)
    def test_collect_schema_terms_missing_allow_list(self, mock_file_open):
        """Test behavior when allow_list.json is missing."""
        
        # Mock config.yaml
        config_data = json.dumps({
            "schema": {"allow_list_path": "missing_allow_list.json"},
            "schema_embeddings": {"include_synonyms_path": "schema_synonyms.json"}
        })
        
        def mock_open_side_effect(filename, mode='r'):
            if filename == "config.yaml":
                return mock_open(read_data=config_data).return_value
            else:
                raise FileNotFoundError(f"File not found: {filename}")
        
        mock_file_open.side_effect = mock_open_side_effect
        
        terms = collect_schema_terms()
        
        # Should return empty list when allow_list.json is missing
        self.assertEqual(terms, [])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
    @patch("graph_rag.schema_embeddings.get_embedding_provider")
    def test_compute_embeddings_error_handling(self, mock_get_embedding_provider):
        """Test error handling in compute_embeddings."""
        
        # Mock embedding provider to raise an exception
        mock_provider = MagicMock()
        mock_provider.get_embeddings.side_effect = Exception("Embedding service error")
        mock_get_embedding_provider.return_value = mock_provider
        
        terms = ["Person", "Organization"]
        embeddings = compute_embeddings(terms)
        
        # Should return empty list on error
        self.assertEqual(embeddings, [])

if __name__ == '__main__':
    unittest.main()
