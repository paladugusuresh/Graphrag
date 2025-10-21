import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
import sys

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.schema_embeddings import upsert_schema_embeddings

class TestSchemaEmbeddingsUpsert(unittest.TestCase):

    def setUp(self):
        # Clear module cache
        for module_name in [
            'graph_rag.schema_embeddings', 
            'graph_rag.embeddings', 
            'graph_rag.neo4j_client',
            'graph_rag.observability'
        ]:
            if module_name in sys.modules:
                del sys.modules[module_name]
        
        # Clear Prometheus registry to prevent metric conflicts
        try:
            from prometheus_client import REGISTRY
            REGISTRY._names_to_collectors.clear()
        except ImportError:
            pass

    @patch("graph_rag.schema_embeddings.Neo4jClient")
    @patch("graph_rag.schema_embeddings.generate_schema_embeddings")
    @patch("builtins.open", new_callable=mock_open)
    def test_upsert_schema_embeddings_success(self, mock_file_open, mock_generate_embeddings, mock_neo4j_client_class):
        """Test successful upsert of schema embeddings."""
        
        # Mock config.yaml with YAML format
        config_data = """
        guardrails:
          neo4j_timeout: 15
        schema_embeddings:
          index_name: test_schema_embeddings
          node_label: SchemaTerm
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock schema embeddings data
        mock_embeddings_data = [
            {
                "id": "label:Person",
                "term": "Person",
                "type": "label",
                "canonical_id": "Person",
                "embedding": [0.1, 0.2, 0.3]
            },
            {
                "id": "relationship:FOUNDED",
                "term": "FOUNDED",
                "type": "relationship",
                "canonical_id": "FOUNDED",
                "embedding": [0.4, 0.5, 0.6]
            }
        ]
        mock_generate_embeddings.return_value = mock_embeddings_data
        
        # Mock Neo4j client
        mock_neo4j_client = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client
        
        # Mock write query responses
        mock_neo4j_client.execute_write_query.side_effect = [
            [{"id": "label:Person", "operation": "created"}],  # First term
            [{"id": "relationship:FOUNDED", "operation": "updated"}],  # Second term
            []  # Index creation (no return expected)
        ]
        
        # Execute upsert
        result = upsert_schema_embeddings()
        
        # Verify results
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["nodes_created"], 1)
        self.assertEqual(result["nodes_updated"], 1)
        self.assertEqual(result["total_terms"], 2)
        self.assertEqual(result["index_name"], "test_schema_embeddings")
        self.assertEqual(result["index_status"], "created_or_verified")
        self.assertEqual(result["embedding_dimensions"], 3)
        
        # Verify Neo4j client was called correctly
        self.assertEqual(mock_neo4j_client.execute_write_query.call_count, 3)
        
        # Check first upsert call (Person)
        first_call_args = mock_neo4j_client.execute_write_query.call_args_list[0]
        self.assertIn("MERGE (s:SchemaTerm {id: $id})", first_call_args[0][0])
        self.assertEqual(first_call_args[0][1]["id"], "label:Person")
        self.assertEqual(first_call_args[0][1]["term"], "Person")
        self.assertEqual(first_call_args[0][1]["type"], "label")
        self.assertEqual(first_call_args[0][1]["embedding"], [0.1, 0.2, 0.3])
        self.assertEqual(first_call_args[1]["timeout"], 15)
        self.assertEqual(first_call_args[1]["query_name"], "upsert_schema_term")
        
        # Check second upsert call (FOUNDED)
        second_call_args = mock_neo4j_client.execute_write_query.call_args_list[1]
        self.assertEqual(second_call_args[0][1]["id"], "relationship:FOUNDED")
        self.assertEqual(second_call_args[0][1]["term"], "FOUNDED")
        self.assertEqual(second_call_args[0][1]["type"], "relationship")
        
        # Check index creation call
        third_call_args = mock_neo4j_client.execute_write_query.call_args_list[2]
        index_query = third_call_args[0][0]
        self.assertIn("CREATE VECTOR INDEX `test_schema_embeddings`", index_query)
        self.assertIn("FOR (s:SchemaTerm) ON (s.embedding)", index_query)
        self.assertIn("`vector.dimensions`: 3", index_query)
        self.assertIn("`vector.similarity_function`: 'cosine'", index_query)
        self.assertEqual(third_call_args[1]["timeout"], 15)
        self.assertEqual(third_call_args[1]["query_name"], "create_schema_vector_index")

    @patch("graph_rag.schema_embeddings.Neo4jClient")
    @patch("graph_rag.schema_embeddings.generate_schema_embeddings")
    @patch("builtins.open", new_callable=mock_open)
    def test_upsert_schema_embeddings_no_data(self, mock_file_open, mock_generate_embeddings, mock_neo4j_client_class):
        """Test upsert when no schema embeddings are generated."""
        
        # Mock config.yaml with YAML format
        config_data = """
        guardrails:
          neo4j_timeout: 10
        schema_embeddings:
          index_name: schema_embeddings
          node_label: SchemaTerm
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock empty embeddings data
        mock_generate_embeddings.return_value = []
        
        # Execute upsert
        result = upsert_schema_embeddings()
        
        # Verify results
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "no_embeddings")
        self.assertEqual(result["nodes_created"], 0)
        
        # Verify Neo4j client was not instantiated
        mock_neo4j_client_class.assert_not_called()

    @patch("graph_rag.schema_embeddings.Neo4jClient")
    @patch("graph_rag.schema_embeddings.generate_schema_embeddings")
    @patch("builtins.open", new_callable=mock_open)
    def test_upsert_schema_embeddings_db_error(self, mock_file_open, mock_generate_embeddings, mock_neo4j_client_class):
        """Test upsert with database errors."""
        
        # Mock config.yaml with YAML format
        config_data = """
        guardrails:
          neo4j_timeout: 10
        schema_embeddings:
          index_name: schema_embeddings
          node_label: SchemaTerm
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock schema embeddings data
        mock_embeddings_data = [
            {
                "id": "label:Person",
                "term": "Person", 
                "type": "label",
                "canonical_id": "Person",
                "embedding": [0.1, 0.2, 0.3]
            }
        ]
        mock_generate_embeddings.return_value = mock_embeddings_data
        
        # Mock Neo4j client with errors
        mock_neo4j_client = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client
        
        # Mock database error for node upsert
        mock_neo4j_client.execute_write_query.side_effect = [
            Exception("Database connection error"),  # Node upsert fails
            []  # Index creation succeeds
        ]
        
        # Execute upsert
        result = upsert_schema_embeddings()
        
        # Verify results - should complete despite node error
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["nodes_created"], 0)
        self.assertEqual(result["nodes_updated"], 0)
        self.assertEqual(result["total_terms"], 1)
        self.assertEqual(result["index_status"], "created_or_verified")

    @patch("graph_rag.schema_embeddings.Neo4jClient")
    @patch("graph_rag.schema_embeddings.generate_schema_embeddings")
    @patch("builtins.open", new_callable=mock_open)
    def test_upsert_schema_embeddings_index_error(self, mock_file_open, mock_generate_embeddings, mock_neo4j_client_class):
        """Test upsert with index creation error."""
        
        # Mock config.yaml with YAML format
        config_data = """
        guardrails:
          neo4j_timeout: 10
        schema_embeddings:
          index_name: schema_embeddings
          node_label: SchemaTerm
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock schema embeddings data
        mock_embeddings_data = [
            {
                "id": "label:Person",
                "term": "Person",
                "type": "label", 
                "canonical_id": "Person",
                "embedding": [0.1, 0.2, 0.3]
            }
        ]
        mock_generate_embeddings.return_value = mock_embeddings_data
        
        # Mock Neo4j client
        mock_neo4j_client = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client
        
        # Mock successful node upsert but failed index creation
        mock_neo4j_client.execute_write_query.side_effect = [
            [{"id": "label:Person", "operation": "created"}],  # Node upsert succeeds
            Exception("Index creation failed")  # Index creation fails
        ]
        
        # Execute upsert
        result = upsert_schema_embeddings()
        
        # Verify results
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["nodes_created"], 1)
        self.assertEqual(result["nodes_updated"], 0)
        self.assertEqual(result["total_terms"], 1)
        self.assertEqual(result["index_status"], "failed")

    @patch("graph_rag.schema_embeddings.Neo4jClient")
    @patch("graph_rag.schema_embeddings.generate_schema_embeddings")
    @patch("builtins.open", new_callable=mock_open)
    def test_upsert_schema_embeddings_invalid_data(self, mock_file_open, mock_generate_embeddings, mock_neo4j_client_class):
        """Test upsert with invalid/missing data fields."""
        
        # Mock config.yaml with YAML format
        config_data = """
        guardrails:
          neo4j_timeout: 10
        schema_embeddings:
          index_name: schema_embeddings
          node_label: SchemaTerm
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock schema embeddings data with missing fields
        mock_embeddings_data = [
            {
                "id": "label:Person",
                "term": "Person",
                "type": "label",
                "canonical_id": "Person",
                "embedding": [0.1, 0.2, 0.3]
            },
            {
                "id": "label:Invalid",
                "term": "Invalid",
                # Missing 'type' and 'embedding' fields
                "canonical_id": "Invalid"
            }
        ]
        mock_generate_embeddings.return_value = mock_embeddings_data
        
        # Mock Neo4j client
        mock_neo4j_client = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client
        
        # Mock successful response for valid data
        mock_neo4j_client.execute_write_query.side_effect = [
            [{"id": "label:Person", "operation": "created"}],  # Valid term
            []  # Index creation
        ]
        
        # Execute upsert
        result = upsert_schema_embeddings()
        
        # Verify results - should process only valid data
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["nodes_created"], 1)
        self.assertEqual(result["nodes_updated"], 0)
        self.assertEqual(result["total_terms"], 2)  # Total includes invalid data
        
        # Should only call execute_write_query twice (1 valid term + 1 index)
        self.assertEqual(mock_neo4j_client.execute_write_query.call_count, 2)

    @patch("graph_rag.schema_embeddings.Neo4jClient")
    @patch("graph_rag.schema_embeddings.generate_schema_embeddings")  
    @patch("builtins.open", new_callable=mock_open)
    def test_upsert_parameterized_queries(self, mock_file_open, mock_generate_embeddings, mock_neo4j_client_class):
        """Test that all queries are properly parameterized."""
        
        # Mock config.yaml with YAML format
        config_data = """
        guardrails:
          neo4j_timeout: 20
        schema_embeddings:
          index_name: test_index
          node_label: SchemaTerm
        """
        
        mock_file_open.return_value.__enter__.return_value.read.return_value = config_data
        
        # Mock schema embeddings data
        mock_embeddings_data = [
            {
                "id": "label:TestEntity",
                "term": "TestEntity",
                "type": "label",
                "canonical_id": "TestEntity", 
                "embedding": [0.1, 0.2, 0.3, 0.4]
            }
        ]
        mock_generate_embeddings.return_value = mock_embeddings_data
        
        # Mock Neo4j client
        mock_neo4j_client = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client
        mock_neo4j_client.execute_write_query.side_effect = [
            [{"id": "label:TestEntity", "operation": "created"}],
            []
        ]
        
        # Execute upsert
        result = upsert_schema_embeddings()
        
        # Verify parameterized node upsert query
        node_call_args = mock_neo4j_client.execute_write_query.call_args_list[0]
        node_query = node_call_args[0][0]
        node_params = node_call_args[0][1]
        
        # Check query uses parameters
        self.assertIn("MERGE (s:SchemaTerm {id: $id})", node_query)
        self.assertIn("SET s.term = $term", node_query)
        self.assertIn("s.type = $type", node_query)
        self.assertIn("s.canonical_id = $canonical_id", node_query)
        self.assertIn("s.embedding = $embedding", node_query)
        
        # Check parameters are correctly passed
        expected_params = {
            'id': 'label:TestEntity',
            'term': 'TestEntity',
            'type': 'label',
            'canonical_id': 'TestEntity',
            'embedding': [0.1, 0.2, 0.3, 0.4]
        }
        for key, value in expected_params.items():
            self.assertEqual(node_params[key], value)
        
        # Verify index query
        index_call_args = mock_neo4j_client.execute_write_query.call_args_list[1]
        index_query = index_call_args[0][0]
        
        # Check index query structure (note: index name is embedded in query for Neo4j syntax)
        self.assertIn("CREATE VECTOR INDEX `test_index`", index_query)
        self.assertIn("FOR (s:SchemaTerm) ON (s.embedding)", index_query)
        self.assertIn("`vector.dimensions`: 4", index_query)
        self.assertIn("`vector.similarity_function`: 'cosine'", index_query)

if __name__ == '__main__':
    unittest.main()
