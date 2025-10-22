import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import tempfile
import shutil

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set environment variables before importing ingest module
os.environ["APP_MODE"] = "admin"

from graph_rag.ingest import process_and_ingest_files, parse_frontmatter


class TestChunkEmbeddingIngest(unittest.TestCase):
    """Tests for chunk embedding persistence during ingestion"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary data directory
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = os.getenv("DATA_DIR", "data/")
        
        # Mock the DATA_DIR constant
        with patch("graph_rag.ingest.DATA_DIR", self.temp_dir):
            pass

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_file(self, filename, content):
        """Helper to create a test markdown file"""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path

    @patch("graph_rag.ingest.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.ingest.get_embedding_provider")
    @patch("graph_rag.ingest.Neo4jClient")
    @patch("graph_rag.ingest.ensure_schema_loaded")
    @patch("graph_rag.ingest.call_llm_structured")
    @patch.dict(os.environ, {"APP_MODE": "admin"})
    def test_chunk_embedding_enabled_creates_embeddings(self, mock_llm, mock_schema, mock_client_class, mock_get_provider, mock_flag):
        """Test that chunks get embeddings when flag is enabled"""
        # Setup mocks
        mock_flag.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]  # 5 dimensions
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock schema loading
        mock_schema.return_value = {
            "node_labels": ["Document", "Chunk", "Entity"],
            "relationship_types": ["HAS_CHUNK", "MENTIONS"],
            "properties": {}
        }
        
        # Mock LLM extraction
        mock_llm.return_value = MagicMock(nodes=[], relationships=[])
        
        # Create test file
        test_content = """---
id: test-doc
title: Test Document
---

This is test content for chunk embedding.
It should be split into chunks and get embeddings.
"""
        self._create_test_file("test.md", test_content)
        
        # Run ingestion
        with patch("graph_rag.ingest.DATA_DIR", self.temp_dir):
            process_and_ingest_files()
        
        # Verify embedding provider was called
        mock_provider.get_embeddings.assert_called()
        
        # Verify embedding was set on chunk
        embedding_calls = [call for call in mock_client.execute_write_query.call_args_list 
                         if "SET c.embedding" in str(call)]
        self.assertGreater(len(embedding_calls), 0, "Should have calls to set chunk embeddings")

    @patch("graph_rag.ingest.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.ingest.Neo4jClient")
    @patch("graph_rag.ingest.ensure_schema_loaded")
    @patch("graph_rag.ingest.call_llm_structured")
    @patch.dict(os.environ, {"APP_MODE": "admin"})
    def test_chunk_embedding_disabled_skips_embeddings(self, mock_llm, mock_schema, mock_client_class, mock_flag):
        """Test that chunks don't get embeddings when flag is disabled"""
        # Setup mocks
        mock_flag.return_value = False
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock schema loading
        mock_schema.return_value = {
            "node_labels": ["Document", "Chunk", "Entity"],
            "relationship_types": ["HAS_CHUNK", "MENTIONS"],
            "properties": {}
        }
        
        # Mock LLM extraction
        mock_llm.return_value = MagicMock(nodes=[], relationships=[])
        
        # Create test file
        test_content = """---
id: test-doc
title: Test Document
---

This is test content for chunk embedding.
"""
        self._create_test_file("test.md", test_content)
        
        # Run ingestion
        with patch("graph_rag.ingest.DATA_DIR", self.temp_dir):
            process_and_ingest_files()
        
        # Verify no embedding calls were made
        embedding_calls = [call for call in mock_client.execute_write_query.call_args_list 
                         if "SET c.embedding" in str(call)]
        self.assertEqual(len(embedding_calls), 0, "Should not have calls to set chunk embeddings when disabled")

    @patch("graph_rag.ingest.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.ingest.get_embedding_provider")
    @patch("graph_rag.ingest.Neo4jClient")
    @patch("graph_rag.ingest.ensure_schema_loaded")
    @patch("graph_rag.ingest.call_llm_structured")
    @patch("graph_rag.ingest.audit_store")
    @patch.dict(os.environ, {"APP_MODE": "admin"})
    def test_embedding_generation_failure_continues_processing(self, mock_audit, mock_llm, mock_schema, mock_client_class, mock_get_provider, mock_flag):
        """Test that embedding generation failure doesn't stop ingestion"""
        # Setup mocks
        mock_flag.return_value = True
        
        # Mock embedding provider to fail
        mock_provider = MagicMock()
        mock_provider.get_embeddings.side_effect = Exception("Embedding API error")
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock schema loading
        mock_schema.return_value = {
            "node_labels": ["Document", "Chunk", "Entity"],
            "relationship_types": ["HAS_CHUNK", "MENTIONS"],
            "properties": {}
        }
        
        # Mock LLM extraction
        mock_llm.return_value = MagicMock(nodes=[], relationships=[])
        
        # Create test file
        test_content = """---
id: test-doc
title: Test Document
---

This is test content for chunk embedding.
"""
        self._create_test_file("test.md", test_content)
        
        # Run ingestion
        with patch("graph_rag.ingest.DATA_DIR", self.temp_dir):
            process_and_ingest_files()
        
        # Verify audit log was recorded for embedding failure
        audit_calls = mock_audit.record.call_args_list
        embedding_failure_calls = [call for call in audit_calls 
                                   if "chunk_embedding_failed" in str(call)]
        self.assertGreater(len(embedding_failure_calls), 0, "Should audit log embedding failures")
        
        # Verify chunk creation still happened (not stopped by embedding failure)
        chunk_creation_calls = [call for call in mock_client.execute_write_query.call_args_list 
                               if "MERGE (c:Chunk" in str(call)]
        self.assertGreater(len(chunk_creation_calls), 0, "Should still create chunks despite embedding failure")

    @patch("graph_rag.ingest.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.ingest.get_embedding_provider")
    @patch("graph_rag.ingest.Neo4jClient")
    @patch("graph_rag.ingest.ensure_schema_loaded")
    @patch("graph_rag.ingest.call_llm_structured")
    @patch("graph_rag.ingest.audit_store")
    @patch.dict(os.environ, {"APP_MODE": "admin"})
    def test_empty_embedding_result_logs_warning(self, mock_audit, mock_llm, mock_schema, mock_client_class, mock_get_provider, mock_flag):
        """Test that empty embedding results are handled gracefully"""
        # Setup mocks
        mock_flag.return_value = True
        
        # Mock embedding provider to return empty result
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = []  # Empty result
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock schema loading
        mock_schema.return_value = {
            "node_labels": ["Document", "Chunk", "Entity"],
            "relationship_types": ["HAS_CHUNK", "MENTIONS"],
            "properties": {}
        }
        
        # Mock LLM extraction
        mock_llm.return_value = MagicMock(nodes=[], relationships=[])
        
        # Create test file
        test_content = """---
id: test-doc
title: Test Document
---

This is test content for chunk embedding.
"""
        self._create_test_file("test.md", test_content)
        
        # Run ingestion
        with patch("graph_rag.ingest.DATA_DIR", self.temp_dir):
            process_and_ingest_files()
        
        # Verify audit log was recorded for empty embedding result
        audit_calls = mock_audit.record.call_args_list
        empty_embedding_calls = [call for call in audit_calls 
                                if "empty_embedding_result" in str(call)]
        self.assertGreater(len(empty_embedding_calls), 0, "Should audit log empty embedding results")

    @patch("graph_rag.ingest.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.ingest.get_embedding_provider")
    @patch("graph_rag.ingest.Neo4jClient")
    @patch("graph_rag.ingest.ensure_schema_loaded")
    @patch("graph_rag.ingest.call_llm_structured")
    @patch.dict(os.environ, {"APP_MODE": "admin"})
    def test_embedding_dimensions_logged(self, mock_llm, mock_schema, mock_client_class, mock_get_provider, mock_flag):
        """Test that embedding dimensions are logged"""
        # Setup mocks
        mock_flag.return_value = True
        
        # Mock embedding provider with specific dimensions
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1] * 768]  # 768 dimensions
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock schema loading
        mock_schema.return_value = {
            "node_labels": ["Document", "Chunk", "Entity"],
            "relationship_types": ["HAS_CHUNK", "MENTIONS"],
            "properties": {}
        }
        
        # Mock LLM extraction
        mock_llm.return_value = MagicMock(nodes=[], relationships=[])
        
        # Create test file
        test_content = """---
id: test-doc
title: Test Document
---

This is test content for chunk embedding.
"""
        self._create_test_file("test.md", test_content)
        
        # Run ingestion
        with patch("graph_rag.ingest.DATA_DIR", self.temp_dir):
            with patch("graph_rag.ingest.logger") as mock_logger:
                process_and_ingest_files()
        
        # Verify embedding dimensions were logged
        debug_calls = mock_logger.debug.call_args_list
        dimension_calls = [call for call in debug_calls 
                          if "dimensions: 768" in str(call)]
        self.assertGreater(len(dimension_calls), 0, "Should log embedding dimensions")

    def test_parse_frontmatter(self):
        """Test frontmatter parsing helper function"""
        # Test with frontmatter
        content = """---
id: test-doc
title: Test Document
---

This is the body content.
"""
        metadata, body = parse_frontmatter(content)
        self.assertEqual(metadata["id"], "test-doc")
        self.assertEqual(metadata["title"], "Test Document")
        self.assertEqual(body.strip(), "This is the body content.")
        
        # Test without frontmatter
        content = "This is just plain content."
        metadata, body = parse_frontmatter(content)
        self.assertEqual(metadata, {})
        self.assertEqual(body, "This is just plain content.")


class TestChunkEmbeddingIntegration(unittest.TestCase):
    """Integration tests for chunk embedding functionality"""

    @patch("graph_rag.ingest.RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED")
    @patch("graph_rag.ingest.get_embedding_provider")
    @patch("graph_rag.ingest.Neo4jClient")
    @patch("graph_rag.ingest.ensure_schema_loaded")
    @patch("graph_rag.ingest.call_llm_structured")
    @patch.dict(os.environ, {"APP_MODE": "admin"})
    def test_multiple_chunks_get_embeddings(self, mock_llm, mock_schema, mock_client_class, mock_get_provider, mock_flag):
        """Test that multiple chunks in a document all get embeddings"""
        # Setup mocks
        mock_flag.return_value = True
        
        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.get_embeddings.return_value = [[0.1, 0.2, 0.3]]  # 3 dimensions
        mock_get_provider.return_value = mock_provider
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock schema loading
        mock_schema.return_value = {
            "node_labels": ["Document", "Chunk", "Entity"],
            "relationship_types": ["HAS_CHUNK", "MENTIONS"],
            "properties": {}
        }
        
        # Mock LLM extraction
        mock_llm.return_value = MagicMock(nodes=[], relationships=[])
        
        # Create test file with content that will be split into multiple chunks
        test_content = """---
id: test-doc
title: Test Document
---

""" + "This is a very long piece of content. " * 100  # Force multiple chunks
        temp_dir = tempfile.mkdtemp()
        try:
            test_file = os.path.join(temp_dir, "test.md")
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(test_content)
            
            # Run ingestion
            with patch("graph_rag.ingest.DATA_DIR", temp_dir):
                process_and_ingest_files()
            
            # Verify embedding provider was called multiple times (once per chunk)
            self.assertGreater(mock_provider.get_embeddings.call_count, 1, "Should generate embeddings for multiple chunks")
            
            # Verify multiple embedding updates were made
            embedding_calls = [call for call in mock_client.execute_write_query.call_args_list 
                             if "SET c.embedding" in str(call)]
            self.assertGreater(len(embedding_calls), 1, "Should set embeddings for multiple chunks")
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
