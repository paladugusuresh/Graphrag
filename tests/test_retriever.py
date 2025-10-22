# tests/test_retriever.py
import unittest
from unittest.mock import patch, MagicMock

from graph_rag.retriever import Retriever
from graph_rag.flags import RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED, RETRIEVAL_TOPK


class TestVectorRetrieval(unittest.TestCase):
    """Test vector retrieval functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.retriever = Retriever()
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_retrieve_chunks_by_embedding_enabled(self, mock_client_class, mock_provider_func, mock_enabled):
        """Test vector retrieval when enabled."""
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4]]
        mock_provider_func.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.return_value = [
            {"chunk_id": "chunk_1", "score": 0.95},
            {"chunk_id": "chunk_2", "score": 0.87},
            {"chunk_id": "chunk_3", "score": 0.82}
        ]
        
        # Test retrieval
        result = self.retriever.retrieve_chunks_by_embedding("What are the goals for Isabella Thomas?")
        
        # Verify results
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "chunk_1")
        self.assertEqual(result[1], "chunk_2")
        self.assertEqual(result[2], "chunk_3")
        
        # Verify embedding provider was called
        mock_provider.get_embeddings.assert_called_once_with(["What are the goals for Isabella Thomas?"])
        
        # Verify Neo4j query was executed
        mock_client.execute_read_query.assert_called_once()
        query_args = mock_client.execute_read_query.call_args
        self.assertIn("db.index.vector.queryNodes", query_args[0][0])
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    def test_retrieve_chunks_by_embedding_disabled(self, mock_enabled):
        """Test vector retrieval when disabled."""
        # Disable vector retrieval
        mock_enabled.return_value = False
        
        # Test retrieval
        result = self.retriever.retrieve_chunks_by_embedding("What are the goals for Isabella Thomas?")
        
        # Should return empty list
        self.assertEqual(result, [])
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_retrieve_chunks_custom_top_k(self, mock_client_class, mock_provider_func, mock_enabled):
        """Test vector retrieval with custom top_k parameter."""
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4]]
        mock_provider_func.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.return_value = [
            {"chunk_id": "chunk_1", "score": 0.95},
            {"chunk_id": "chunk_2", "score": 0.87}
        ]
        
        # Test retrieval with custom top_k
        result = self.retriever.retrieve_chunks_by_embedding("Test query", top_k=2)
        
        # Verify results
        self.assertEqual(len(result), 2)
        
        # Verify Neo4j query was called with correct top_k
        mock_client.execute_read_query.assert_called_once()
        query_args = mock_client.execute_read_query.call_args
        self.assertEqual(query_args[1]["top_k"], 2)
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.RETRIEVAL_TOPK')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_retrieve_chunks_default_top_k(self, mock_client_class, mock_provider_func, mock_topk, mock_enabled):
        """Test vector retrieval with default top_k from config."""
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Set default top_k
        mock_topk.return_value = 5
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4]]
        mock_provider_func.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.return_value = []
        
        # Test retrieval without top_k parameter
        result = self.retriever.retrieve_chunks_by_embedding("Test query")
        
        # Verify Neo4j query was called with default top_k
        mock_client.execute_read_query.assert_called_once()
        query_args = mock_client.execute_read_query.call_args
        self.assertEqual(query_args[1]["top_k"], 5)
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_retrieve_chunks_embedding_error(self, mock_client_class, mock_provider_func, mock_enabled):
        """Test vector retrieval when embedding generation fails."""
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Mock embedding provider to raise exception
        mock_provider = MagicMock()
        mock_provider.get_embeddings.side_effect = Exception("Embedding service unavailable")
        mock_provider_func.return_value = mock_provider
        
        # Test retrieval
        result = self.retriever.retrieve_chunks_by_embedding("Test query")
        
        # Should return empty list on error
        self.assertEqual(result, [])
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_retrieve_chunks_empty_embedding(self, mock_client_class, mock_provider_func, mock_enabled):
        """Test vector retrieval when embedding is empty."""
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Mock embedding provider to return empty embedding
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = []
        mock_provider_func.return_value = mock_provider
        
        # Test retrieval
        result = self.retriever.retrieve_chunks_by_embedding("Test query")
        
        # Should return empty list
        self.assertEqual(result, [])
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_retrieve_chunks_neo4j_error(self, mock_client_class, mock_provider_func, mock_enabled):
        """Test vector retrieval when Neo4j query fails."""
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4]]
        mock_provider_func.return_value = mock_provider
        
        # Mock Neo4j client to raise exception
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.side_effect = Exception("Neo4j connection failed")
        
        # Test retrieval
        result = self.retriever.retrieve_chunks_by_embedding("Test query")
        
        # Should return empty list on error
        self.assertEqual(result, [])


class TestRetrieverIntegration(unittest.TestCase):
    """Test retriever integration with other components."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.retriever = Retriever()
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_get_unstructured_context_with_vector(self, mock_client_class, mock_provider_func, mock_enabled):
        """Test _get_unstructured_context with vector retrieval enabled."""
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4]]
        mock_provider_func.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.return_value = [
            {"chunk_id": "chunk_1", "score": 0.95},
            {"chunk_id": "chunk_2", "score": 0.87}
        ]
        
        # Test unstructured context retrieval
        result = self.retriever._get_unstructured_context("What are the goals for Isabella Thomas?")
        
        # Should return chunk IDs from vector search
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "chunk_1")
        self.assertEqual(result[1], "chunk_2")
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    def test_get_unstructured_context_without_vector(self, mock_enabled):
        """Test _get_unstructured_context with vector retrieval disabled."""
        # Disable vector retrieval
        mock_enabled.return_value = False
        
        # Test unstructured context retrieval
        result = self.retriever._get_unstructured_context("What are the goals for Isabella Thomas?")
        
        # Should return empty list (legacy behavior)
        self.assertEqual(result, [])
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_retrieve_context_integration(self, mock_client_class, mock_provider_func, mock_enabled):
        """Test complete retrieve_context integration."""
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4]]
        mock_provider_func.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock vector search results
        mock_client.execute_read_query.side_effect = [
            [{"chunk_id": "chunk_1", "score": 0.95}],  # Vector search
            [{"id": "chunk_1", "text": "Isabella Thomas has math goals"}],  # Graph expansion
            []  # Structured context
        ]
        
        # Mock plan
        mock_plan = MagicMock()
        mock_plan.intent = "goals_for_student"
        mock_plan.anchor_entity = "Isabella Thomas"
        mock_plan.question = "What are the goals for Isabella Thomas?"
        
        # Test complete retrieval
        result = self.retriever.retrieve_context(mock_plan)
        
        # Verify result structure
        self.assertIn("structured", result)
        self.assertIn("unstructured", result)
        self.assertIn("chunk_ids", result)
        self.assertIn("vector_chunks", result)
        self.assertIn("total_chunks", result)
        
        # Verify vector chunks are tracked
        self.assertEqual(result["vector_chunks"], ["chunk_1"])
        self.assertEqual(result["total_chunks"], 1)


class TestRetrieverMetrics(unittest.TestCase):
    """Test retriever metrics and observability."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.retriever = Retriever()
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_augmentation_size_metrics(self, mock_client_class, mock_provider_func, mock_enabled):
        """Test that augmentation size is recorded as metrics."""
        from graph_rag.observability import augmentation_size
        
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4]]
        mock_provider_func.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock results
        mock_client.execute_read_query.side_effect = [
            [{"chunk_id": "chunk_1", "score": 0.95}],  # Vector search
            [{"id": "chunk_1", "text": "Text 1"}, {"id": "chunk_2", "text": "Text 2"}],  # Graph expansion
            []  # Structured context
        ]
        
        # Mock plan
        mock_plan = MagicMock()
        mock_plan.intent = "goals_for_student"
        mock_plan.anchor_entity = "Isabella Thomas"
        mock_plan.question = "What are the goals for Isabella Thomas?"
        
        with patch('graph_rag.retriever.augmentation_size') as mock_metric:
            result = self.retriever.retrieve_context(mock_plan)
            
            # Verify metric was recorded
            mock_metric.observe.assert_called_with(2)  # 2 expanded chunks
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_retriever_spans(self, mock_client_class, mock_provider_func, mock_enabled):
        """Test that retriever creates proper spans."""
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4]]
        mock_provider_func.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.return_value = []
        
        # Mock plan
        mock_plan = MagicMock()
        mock_plan.intent = "goals_for_student"
        mock_plan.anchor_entity = "Isabella Thomas"
        mock_plan.question = "What are the goals for Isabella Thomas?"
        
        with patch('graph_rag.retriever.create_pipeline_span') as mock_create_span:
            mock_span = MagicMock()
            mock_create_span.return_value.__enter__.return_value = mock_span
            
            result = self.retriever.retrieve_context(mock_plan)
            
            # Verify span was created
            mock_create_span.assert_called_with(
                "retriever.retrieve_context",
                intent="goals_for_student",
                anchor_entity="Isabella Thomas"
            )
            
            # Verify span attributes were set
            mock_span.set_attribute.assert_called()
            calls = mock_span.set_attribute.call_args_list
            attribute_names = [call[0][0] for call in calls]
            self.assertIn("vector_chunks_count", attribute_names)
            self.assertIn("total_chunks", attribute_names)
            self.assertIn("augmentation_size", attribute_names)


class TestRetrieverErrorHandling(unittest.TestCase):
    """Test retriever error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.retriever = Retriever()
    
    @patch('graph_rag.retriever.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED')
    @patch('graph_rag.retriever.get_embedding_provider')
    @patch('graph_rag.retriever.Neo4jClient')
    def test_retrieve_context_error_handling(self, mock_client_class, mock_provider_func, mock_enabled):
        """Test error handling in retrieve_context."""
        # Enable vector retrieval
        mock_enabled.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4]]
        mock_provider_func.return_value = mock_provider
        
        # Mock Neo4j client to raise exception
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_read_query.side_effect = Exception("Database error")
        
        # Mock plan
        mock_plan = MagicMock()
        mock_plan.intent = "goals_for_student"
        mock_plan.anchor_entity = "Isabella Thomas"
        mock_plan.question = "What are the goals for Isabella Thomas?"
        
        # Should handle error gracefully
        result = self.retriever.retrieve_context(mock_plan)
        
        # Should return empty result structure
        self.assertIn("structured", result)
        self.assertIn("unstructured", result)
        self.assertIn("chunk_ids", result)
        self.assertIn("vector_chunks", result)
        self.assertIn("total_chunks", result)
        
        # Should have empty results
        self.assertEqual(result["structured"], [])
        self.assertEqual(result["unstructured"], "")
        self.assertEqual(result["chunk_ids"], [])
        self.assertEqual(result["vector_chunks"], [])
        self.assertEqual(result["total_chunks"], 0)


if __name__ == '__main__':
    unittest.main()
