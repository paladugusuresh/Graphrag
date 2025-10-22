import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.schema_manager import (
    _get_embedding_dimensions,
    _check_chunk_vector_index_exists,
    _create_chunk_vector_index,
    ensure_chunk_vector_index,
    _is_write_allowed
)


class TestEmbeddingDimensions(unittest.TestCase):
    """Tests for embedding dimension detection"""

    @patch("graph_rag.embeddings.get_embedding_provider")
    def test_get_embedding_dimensions_success(self, mock_get_provider):
        """Test successful dimension detection"""
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]  # 5 dimensions
        mock_get_provider.return_value = mock_provider
        
        dimensions = _get_embedding_dimensions()
        
        self.assertEqual(dimensions, 5)
        mock_provider.get_embeddings.assert_called_once_with(["test"])

    @patch("graph_rag.embeddings.get_embedding_provider")
    def test_get_embedding_dimensions_empty_result(self, mock_get_provider):
        """Test dimension detection with empty result"""
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = []
        mock_get_provider.return_value = mock_provider
        
        dimensions = _get_embedding_dimensions()
        
        self.assertIsNone(dimensions)

    @patch("graph_rag.embeddings.get_embedding_provider")
    def test_get_embedding_dimensions_exception(self, mock_get_provider):
        """Test dimension detection with exception"""
        mock_get_provider.side_effect = Exception("Provider error")
        
        dimensions = _get_embedding_dimensions()
        
        self.assertIsNone(dimensions)


class TestChunkVectorIndexExists(unittest.TestCase):
    """Tests for checking chunk vector index existence"""

    @patch("graph_rag.neo4j_client.Neo4jClient")
    def test_index_exists_and_online(self, mock_client_class):
        """Test when index exists and is online"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.return_value = [{"name": "chunk_embeddings", "state": "ONLINE"}]
        
        exists = _check_chunk_vector_index_exists()
        
        self.assertTrue(exists)
        mock_client.execute_read_query.assert_called_once()

    @patch("graph_rag.neo4j_client.Neo4jClient")
    def test_index_does_not_exist(self, mock_client_class):
        """Test when index does not exist"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.return_value = []  # No results
        
        exists = _check_chunk_vector_index_exists()
        
        self.assertFalse(exists)

    @patch("graph_rag.neo4j_client.Neo4jClient")
    def test_index_exists_but_not_online(self, mock_client_class):
        """Test when index exists but is not online"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        # Query filters for state = 'ONLINE', so POPULATING state returns no results
        mock_client.execute_read_query.return_value = []
        
        exists = _check_chunk_vector_index_exists()
        
        self.assertFalse(exists)

    @patch("graph_rag.neo4j_client.Neo4jClient")
    def test_check_index_exception(self, mock_client_class):
        """Test exception handling in index check"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.side_effect = Exception("Neo4j error")
        
        exists = _check_chunk_vector_index_exists()
        
        self.assertFalse(exists)


class TestCreateChunkVectorIndex(unittest.TestCase):
    """Tests for creating chunk vector index"""

    @patch("graph_rag.neo4j_client.Neo4jClient")
    def test_create_index_success(self, mock_client_class):
        """Test successful index creation"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_write_query.return_value = []
        
        success = _create_chunk_vector_index(768)
        
        self.assertTrue(success)
        mock_client.execute_write_query.assert_called_once()
        
        # Verify the query contains correct dimensions
        call_args = mock_client.execute_write_query.call_args
        query = call_args[0][0]  # First positional argument
        self.assertIn("768", query)
        self.assertIn("chunk_embeddings", query)
        self.assertIn("cosine", query)

    @patch("graph_rag.neo4j_client.Neo4jClient")
    def test_create_index_exception(self, mock_client_class):
        """Test index creation with exception"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_write_query.side_effect = Exception("Neo4j error")
        
        success = _create_chunk_vector_index(768)
        
        self.assertFalse(success)


class TestEnsureChunkVectorIndex(unittest.TestCase):
    """Tests for ensure_chunk_vector_index function"""

    @patch("graph_rag.schema_manager.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    def test_disabled_flag_skips_creation(self, mock_flag):
        """Test that disabled flag skips index creation"""
        mock_flag.return_value = False
        
        result = ensure_chunk_vector_index()
        
        self.assertTrue(result)  # Not an error, just skipped

    @patch("graph_rag.schema_manager._is_write_allowed")
    @patch("graph_rag.schema_manager.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    def test_write_not_allowed_returns_false(self, mock_flag, mock_write_allowed):
        """Test that write not allowed returns False"""
        mock_flag.return_value = True
        mock_write_allowed.return_value = False
        
        result = ensure_chunk_vector_index()
        
        self.assertFalse(result)

    @patch("graph_rag.schema_manager._check_chunk_vector_index_exists")
    @patch("graph_rag.schema_manager._is_write_allowed")
    @patch("graph_rag.schema_manager.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    def test_index_already_exists_returns_true(self, mock_flag, mock_write_allowed, mock_check_exists):
        """Test that existing index returns True"""
        mock_flag.return_value = True
        mock_write_allowed.return_value = True
        mock_check_exists.return_value = True
        
        result = ensure_chunk_vector_index()
        
        self.assertTrue(result)
        mock_check_exists.assert_called_once()

    @patch("graph_rag.schema_manager._create_chunk_vector_index")
    @patch("graph_rag.schema_manager._get_embedding_dimensions")
    @patch("graph_rag.schema_manager._check_chunk_vector_index_exists")
    @patch("graph_rag.schema_manager._is_write_allowed")
    @patch("graph_rag.schema_manager.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    def test_create_index_success(self, mock_flag, mock_write_allowed, mock_check_exists, mock_get_dims, mock_create):
        """Test successful index creation"""
        mock_flag.return_value = True
        mock_write_allowed.return_value = True
        mock_check_exists.return_value = False
        mock_get_dims.return_value = 768
        mock_create.return_value = True
        
        result = ensure_chunk_vector_index()
        
        self.assertTrue(result)
        mock_get_dims.assert_called_once()
        mock_create.assert_called_once_with(768)

    @patch("graph_rag.schema_manager._get_embedding_dimensions")
    @patch("graph_rag.schema_manager._check_chunk_vector_index_exists")
    @patch("graph_rag.schema_manager._is_write_allowed")
    @patch("graph_rag.schema_manager.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    def test_cannot_determine_dimensions_returns_false(self, mock_flag, mock_write_allowed, mock_check_exists, mock_get_dims):
        """Test that inability to determine dimensions returns False"""
        mock_flag.return_value = True
        mock_write_allowed.return_value = True
        mock_check_exists.return_value = False
        mock_get_dims.return_value = None
        
        result = ensure_chunk_vector_index()
        
        self.assertFalse(result)

    @patch("graph_rag.schema_manager._create_chunk_vector_index")
    @patch("graph_rag.schema_manager._get_embedding_dimensions")
    @patch("graph_rag.schema_manager._check_chunk_vector_index_exists")
    @patch("graph_rag.schema_manager._is_write_allowed")
    @patch("graph_rag.schema_manager.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    def test_create_index_failure_returns_false(self, mock_flag, mock_write_allowed, mock_check_exists, mock_get_dims, mock_create):
        """Test that index creation failure returns False"""
        mock_flag.return_value = True
        mock_write_allowed.return_value = True
        mock_check_exists.return_value = False
        mock_get_dims.return_value = 768
        mock_create.return_value = False
        
        result = ensure_chunk_vector_index()
        
        self.assertFalse(result)


class TestWriteAllowed(unittest.TestCase):
    """Tests for _is_write_allowed function"""

    @patch.dict(os.environ, {"APP_MODE": "admin"})
    def test_admin_mode_allows_writes(self):
        """Test that admin mode allows writes"""
        result = _is_write_allowed()
        self.assertTrue(result)

    @patch.dict(os.environ, {"APP_MODE": "read_only", "ALLOW_WRITES": "true"})
    def test_allow_writes_true_allows_writes(self):
        """Test that ALLOW_WRITES=true allows writes"""
        result = _is_write_allowed()
        self.assertTrue(result)

    @patch.dict(os.environ, {"APP_MODE": "read_only", "ALLOW_WRITES": "false"})
    def test_read_only_mode_denies_writes(self):
        """Test that read-only mode denies writes"""
        result = _is_write_allowed()
        self.assertFalse(result)

    @patch.dict(os.environ, {"APP_MODE": "read_only", "ALLOW_WRITES": "1"})
    def test_allow_writes_one_allows_writes(self):
        """Test that ALLOW_WRITES=1 allows writes"""
        result = _is_write_allowed()
        self.assertTrue(result)

    @patch.dict(os.environ, {"APP_MODE": "read_only", "ALLOW_WRITES": "yes"})
    def test_allow_writes_yes_allows_writes(self):
        """Test that ALLOW_WRITES=yes allows writes"""
        result = _is_write_allowed()
        self.assertTrue(result)


class TestVectorIndexIntegration(unittest.TestCase):
    """Integration tests for vector index functionality"""

    @patch("graph_rag.neo4j_client.Neo4jClient")
    @patch("graph_rag.embeddings.get_embedding_provider")
    @patch("graph_rag.schema_manager.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch.dict(os.environ, {"APP_MODE": "admin"})
    def test_full_workflow_create_index(self, mock_flag, mock_get_provider, mock_client_class):
        """Test full workflow when index needs to be created"""
        # Setup mocks
        mock_flag.return_value = True
        
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1] * 768]  # 768 dimensions
        mock_get_provider.return_value = mock_provider
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        # First call (check exists) returns empty, second call (create) succeeds
        mock_client.execute_read_query.return_value = []
        mock_client.execute_write_query.return_value = []
        
        result = ensure_chunk_vector_index()
        
        self.assertTrue(result)
        self.assertEqual(mock_client.execute_read_query.call_count, 1)
        self.assertEqual(mock_client.execute_write_query.call_count, 1)

    @patch("graph_rag.neo4j_client.Neo4jClient")
    @patch("graph_rag.schema_manager.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch.dict(os.environ, {"APP_MODE": "admin"})
    def test_full_workflow_index_exists(self, mock_flag, mock_client_class):
        """Test full workflow when index already exists"""
        # Setup mocks
        mock_flag.return_value = True
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.return_value = [{"name": "chunk_embeddings", "state": "ONLINE"}]
        
        result = ensure_chunk_vector_index()
        
        self.assertTrue(result)
        self.assertEqual(mock_client.execute_read_query.call_count, 1)
        self.assertEqual(mock_client.execute_write_query.call_count, 0)


if __name__ == '__main__':
    unittest.main()
