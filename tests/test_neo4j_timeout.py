import unittest
from unittest.mock import patch, MagicMock
import os
from neo4j import exceptions
import sys
from prometheus_client import REGISTRY

# Patch environment variables and GraphDatabase.driver at the module level
# so they are active when graph_rag.neo4j_client is imported.
@patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}, clear=True)
@patch("graph_rag.neo4j_client.GraphDatabase")
class TestNeo4jClientTimeout(unittest.TestCase):

    def setUp(self):
        # Clear the module cache to ensure a fresh import for each test
        if 'graph_rag.neo4j_client' in sys.modules:
            del sys.modules['graph_rag.neo4j_client']
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("graph_rag.neo4j_client.db_query_failed")
    def test_execute_read_query_timeout(self, mock_db_query_failed, mock_graph_database):
        mock_driver_instance = MagicMock()
        mock_graph_database.driver.return_value = mock_driver_instance
        mock_driver_instance.verify_connectivity.return_value = None  # Mock verify_connectivity

        mock_session = MagicMock()
        mock_driver_instance.session.return_value.__enter__.return_value = mock_session
        
        # Simulate a timeout by raising a ClientError
        mock_session.begin_transaction.side_effect = exceptions.ClientError("a", "b", "The transaction has been terminated due to a timeout")

        import graph_rag.neo4j_client
        client = graph_rag.neo4j_client.Neo4jClient()

        result = client.execute_read_query("MATCH (n) RETURN n", timeout=0.1)
        self.assertEqual(result, [])
        mock_driver_instance.session.assert_called_once_with(default_access_mode="READ")
        mock_session.begin_transaction.assert_called_once_with(timeout=0.1)
        mock_db_query_failed.inc.assert_called_once()
