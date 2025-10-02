import unittest
from unittest.mock import patch, mock_open
import json
import os
import sys
from prometheus_client import REGISTRY

class TestLabelValidation(unittest.TestCase):

    def setUp(self):
        # Clear module caches to ensure fresh imports
        if 'graph_rag.cypher_generator' in sys.modules:
            del sys.modules['graph_rag.cypher_generator']
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_label_valid(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_label("Document"), "`Document`")
        mock_logger.warning.assert_not_called()

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_label_invalid_regex(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_label("bad-label"), "`Entity`")
        mock_logger.warning.assert_called_with("Invalid label 'bad-label' provided. Falling back to default 'Entity'.")

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_label_not_in_allow_list(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_label("NonExistentLabel"), "`Entity`")
        mock_logger.warning.assert_called_with("Invalid label 'NonExistentLabel' provided. Falling back to default 'Entity'.")

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_relationship_type_valid(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_relationship_type("HAS_CHUNK"), "`HAS_CHUNK`")
        mock_logger.warning.assert_not_called()

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_relationship_type_invalid_regex(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_relationship_type("bad-rel"), "`RELATED`")
        mock_logger.warning.assert_called_with("Invalid relationship type 'bad-rel' provided. Falling back to default 'RELATED'.")

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_relationship_type_not_in_allow_list(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_relationship_type("NonExistentREL"), "`RELATED`")
        mock_logger.warning.assert_called_with("Invalid relationship type 'NonExistentREL' provided. Falling back to default 'RELATED'.")
