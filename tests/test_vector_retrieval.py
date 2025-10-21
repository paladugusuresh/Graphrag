import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.retriever import Retriever


class TestVectorRetrieval(unittest.TestCase):
    """Tests for vector KNN retrieval functionality"""

    @patch("graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.retriever.get_embedding_provider")
    @patch("graph_rag.retriever.Neo4jClient")
    def test_retrieve_chunks_by_embedding_success(self, mock_client_class, mock_get_provider, mock_flag):
        """Test successful vector KNN retrieval"""
        # Setup mocks
        mock_flag.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]  # 5 dimensions
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.return_value = [
            {"chunk_id": "chunk-1", "score": 0.95},
            {"chunk_id": "chunk-2", "score": 0.87},
            {"chunk_id": "chunk-3", "score": 0.82}
        ]
        
        # Create retriever with mocked dependencies
        retriever = Retriever(max_chunks=5)
        
        # Test retrieval
        result = retriever.retrieve_chunks_by_embedding("test query", top_k=3)
        
        # Verify results
        self.assertEqual(result, ["chunk-1", "chunk-2", "chunk-3"])
        
        # Verify embedding provider was called
        mock_provider.get_embeddings.assert_called_once_with(["test query"])
        
        # Verify Neo4j query was called with correct parameters
        mock_client.execute_read_query.assert_called_once()
        call_args = mock_client.execute_read_query.call_args
        # Check positional and keyword arguments
        if len(call_args[0]) > 1:  # Positional args
            params = call_args[0][1]
        else:  # Keyword args
            params = call_args[1]
        self.assertEqual(params["top_k"], 3)
        self.assertEqual(params["embedding"], [0.1, 0.2, 0.3, 0.4, 0.5])

    @patch("graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.retriever.Neo4jClient")
    def test_retrieve_chunks_by_embedding_disabled_flag(self, mock_client_class, mock_flag):
        """Test that retrieval is skipped when flag is disabled"""
        mock_flag.return_value = False
        
        # Create retriever with mocked dependencies
        retriever = Retriever(max_chunks=5)
        
        result = retriever.retrieve_chunks_by_embedding("test query")
        
        self.assertEqual(result, [])

    @patch("graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.retriever.RETRIEVAL_TOPK")
    @patch("graph_rag.retriever.get_embedding_provider")
    @patch("graph_rag.retriever.Neo4jClient")
    def test_retrieve_chunks_by_embedding_uses_default_topk(self, mock_client_class, mock_get_provider, mock_topk, mock_flag):
        """Test that retrieval uses RETRIEVAL_TOPK flag when top_k not specified"""
        # Setup mocks
        mock_flag.return_value = True
        mock_topk.return_value = 7
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.return_value = []
        
        # Create retriever with mocked dependencies
        retriever = Retriever(max_chunks=5)
        
        # Test retrieval without top_k parameter
        retriever.retrieve_chunks_by_embedding("test query")
        
        # Verify RETRIEVAL_TOPK was used
        mock_topk.assert_called_once()
        call_args = mock_client.execute_read_query.call_args
        # Check positional and keyword arguments
        if len(call_args[0]) > 1:  # Positional args
            params = call_args[0][1]
        else:  # Keyword args
            params = call_args[1]
        self.assertEqual(params["top_k"], 7)

    @patch("graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.retriever.get_embedding_provider")
    @patch("graph_rag.retriever.Neo4jClient")
    def test_retrieve_chunks_by_embedding_empty_embedding(self, mock_client_class, mock_get_provider, mock_flag):
        """Test handling of empty embedding result"""
        # Setup mocks
        mock_flag.return_value = True
        
        # Mock embedding provider to return empty result
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = []
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Create retriever with mocked dependencies
        retriever = Retriever(max_chunks=5)
        
        # Test retrieval
        result = retriever.retrieve_chunks_by_embedding("test query")
        
        # Verify empty result
        self.assertEqual(result, [])
        
        # Verify Neo4j was not called
        mock_client.execute_read_query.assert_not_called()

    @patch("graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.retriever.get_embedding_provider")
    @patch("graph_rag.retriever.Neo4jClient")
    def test_retrieve_chunks_by_embedding_neo4j_error(self, mock_client_class, mock_get_provider, mock_flag):
        """Test handling of Neo4j errors"""
        # Setup mocks
        mock_flag.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client to raise exception
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.side_effect = Exception("Neo4j connection error")
        
        # Create retriever with mocked dependencies
        retriever = Retriever(max_chunks=5)
        
        # Test retrieval
        result = retriever.retrieve_chunks_by_embedding("test query")
        
        # Verify empty result on error
        self.assertEqual(result, [])

    @patch("graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.retriever.Neo4jClient")
    def test_get_unstructured_context_uses_vector_retrieval(self, mock_client_class, mock_flag):
        """Test that _get_unstructured_context uses vector retrieval when enabled"""
        mock_flag.return_value = True
        
        # Create retriever with mocked dependencies
        retriever = Retriever(max_chunks=5)
        
        with patch.object(retriever, 'retrieve_chunks_by_embedding') as mock_retrieve:
            mock_retrieve.return_value = ["chunk-1", "chunk-2"]
            
            result = retriever._get_unstructured_context("test question")
            
            self.assertEqual(result, ["chunk-1", "chunk-2"])
            mock_retrieve.assert_called_once_with("test question", retriever.max_chunks)

    @patch("graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.retriever.Neo4jClient")
    def test_get_unstructured_context_disabled_flag(self, mock_client_class, mock_flag):
        """Test that _get_unstructured_context returns empty when flag disabled"""
        mock_flag.return_value = False
        
        # Create retriever with mocked dependencies
        retriever = Retriever(max_chunks=5)
        
        result = retriever._get_unstructured_context("test question")
        
        self.assertEqual(result, [])


class TestRetrieveContextIntegration(unittest.TestCase):
    """Integration tests for retrieve_context method"""

    @patch("graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.retriever.get_embedding_provider")
    @patch("graph_rag.retriever.Neo4jClient")
    def test_retrieve_context_with_vector_embeddings(self, mock_client_class, mock_get_provider, mock_flag):
        """Test full retrieve_context workflow with vector embeddings"""
        # Setup mocks
        mock_flag.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock vector retrieval results
        mock_client.execute_read_query.side_effect = [
            # First call: vector KNN query
            [{"chunk_id": "chunk-1", "score": 0.95}, {"chunk_id": "chunk-2", "score": 0.87}],
            # Second call: hierarchy expansion
            [
                {"id": "chunk-1", "text": "Content of chunk 1"},
                {"id": "chunk-2", "text": "Content of chunk 2"},
                {"id": "chunk-3", "text": "Content of chunk 3"}  # Additional neighbor
            ]
        ]
        
        # Create retriever with mocked dependencies
        retriever = Retriever(max_chunks=5)
        
        # Create mock plan
        mock_plan = MagicMock()
        mock_plan.question = "test question"
        mock_plan.intent = "test intent"
        mock_plan.anchor_entity = "test entity"
        
        # Test retrieval
        result = retriever.retrieve_context(mock_plan)
        
        # Verify results
        self.assertIn("structured", result)
        self.assertIn("unstructured", result)
        self.assertIn("chunk_ids", result)
        self.assertIn("vector_chunks", result)
        self.assertIn("total_chunks", result)
        
        # Verify vector chunks are tracked
        self.assertEqual(result["vector_chunks"], ["chunk-1", "chunk-2"])
        
        # Verify total chunks include expanded results
        self.assertEqual(result["total_chunks"], 3)
        self.assertEqual(result["chunk_ids"], ["chunk-1", "chunk-2", "chunk-3"])
        
        # Verify unstructured text includes chunk content
        self.assertIn("Content of chunk 1", result["unstructured"])
        self.assertIn("Content of chunk 2", result["unstructured"])
        self.assertIn("Content of chunk 3", result["unstructured"])

    @patch("graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.retriever.Neo4jClient")
    def test_retrieve_context_without_vector_embeddings(self, mock_client_class, mock_flag):
        """Test retrieve_context when vector embeddings are disabled"""
        # Setup mocks
        mock_flag.return_value = False
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock hierarchy expansion (should return empty since no initial chunks)
        mock_client.execute_read_query.return_value = []
        
        # Create retriever with mocked dependencies
        retriever = Retriever(max_chunks=5)
        
        # Create mock plan
        mock_plan = MagicMock()
        mock_plan.question = "test question"
        mock_plan.intent = "test intent"
        mock_plan.anchor_entity = "test entity"
        
        # Test retrieval
        result = retriever.retrieve_context(mock_plan)
        
        # Verify results
        self.assertEqual(result["vector_chunks"], [])
        self.assertEqual(result["total_chunks"], 0)
        self.assertEqual(result["chunk_ids"], [])
        self.assertEqual(result["unstructured"], "")

    @patch("graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.retriever.get_embedding_provider")
    @patch("graph_rag.retriever.Neo4jClient")
    def test_retrieve_context_stable_chunk_ids(self, mock_client_class, mock_get_provider, mock_flag):
        """Test that chunk IDs are stable for seeded data"""
        # Setup mocks
        mock_flag.return_value = True
        
        # Mock embedding provider with deterministic results
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client with stable results
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock stable vector retrieval results
        stable_vector_results = [
            {"chunk_id": "doc1-chunk-0", "score": 0.95},
            {"chunk_id": "doc1-chunk-1", "score": 0.87},
            {"chunk_id": "doc2-chunk-0", "score": 0.82}
        ]
        
        stable_expansion_results = [
            {"id": "doc1-chunk-0", "text": "First chunk content"},
            {"id": "doc1-chunk-1", "text": "Second chunk content"},
            {"id": "doc2-chunk-0", "text": "Third chunk content"}
        ]
        
        mock_client.execute_read_query.side_effect = [
            stable_vector_results,
            stable_expansion_results,
            stable_vector_results,  # Second call gets same results
            stable_expansion_results
        ]
        
        # Create retriever with mocked dependencies
        retriever = Retriever(max_chunks=5)
        
        # Create mock plan
        mock_plan = MagicMock()
        mock_plan.question = "test query"
        mock_plan.intent = "test intent"
        mock_plan.anchor_entity = "test entity"
        
        # Test retrieval multiple times
        result1 = retriever.retrieve_context(mock_plan)
        result2 = retriever.retrieve_context(mock_plan)
        
        # Verify stable results
        self.assertEqual(result1["vector_chunks"], result2["vector_chunks"])
        self.assertEqual(result1["chunk_ids"], result2["chunk_ids"])
        self.assertEqual(result1["total_chunks"], result2["total_chunks"])
        
        # Verify expected chunk IDs
        expected_vector_chunks = ["doc1-chunk-0", "doc1-chunk-1", "doc2-chunk-0"]
        self.assertEqual(result1["vector_chunks"], expected_vector_chunks)


if __name__ == '__main__':
    unittest.main()