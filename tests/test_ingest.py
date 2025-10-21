# tests/test_ingest.py
import unittest
from unittest.mock import patch, MagicMock
import os

# Mock environment before importing ingest module
with patch.dict(os.environ, {'APP_MODE': 'admin'}):
    from graph_rag.ingest import (
        ExtractedNode, ExtractedRelationship, ExtractedGraph,
        process_and_ingest_files, parse_frontmatter
    )


class TestIngestModels(unittest.TestCase):
    """Test Pydantic models for ingestion."""
    
    def test_extracted_node_model(self):
        """Test ExtractedNode model."""
        node = ExtractedNode(
            id="node_123",
            type="Student"
        )
        
        self.assertEqual(node.id, "node_123")
        self.assertEqual(node.type, "Student")
    
    def test_extracted_relationship_model(self):
        """Test ExtractedRelationship model."""
        rel = ExtractedRelationship(
            source_id="student_001",
            target_id="plan_001",
            relationship_type="HAS_PLAN",
            source_label="Student",
            target_label="Plan"
        )
        
        self.assertEqual(rel.source_id, "student_001")
        self.assertEqual(rel.target_id, "plan_001")
        self.assertEqual(rel.relationship_type, "HAS_PLAN")
        self.assertEqual(rel.source_label, "Student")
        self.assertEqual(rel.target_label, "Plan")
    
    def test_extracted_graph_model(self):
        """Test ExtractedGraph model."""
        nodes = [
            ExtractedNode(id="node_1", type="Student"),
            ExtractedNode(id="node_2", type="Plan")
        ]
        
        relationships = [
            ExtractedRelationship(
                source_id="node_1", target_id="node_2",
                relationship_type="HAS_PLAN",
                source_label="Student", target_label="Plan"
            )
        ]
        
        graph = ExtractedGraph(nodes=nodes, relationships=relationships)
        
        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(len(graph.relationships), 1)


class TestParseFrontmatter(unittest.TestCase):
    """Test frontmatter parsing functionality."""
    
    def test_parse_frontmatter_with_yaml(self):
        """Test parsing frontmatter with YAML content."""
        text = """---
id: doc_001
title: Test Document
---
This is the body content."""
        
        metadata, body = parse_frontmatter(text)
        
        self.assertEqual(metadata["id"], "doc_001")
        self.assertEqual(metadata["title"], "Test Document")
        self.assertEqual(body.strip(), "This is the body content.")
    
    def test_parse_frontmatter_without_yaml(self):
        """Test parsing text without frontmatter."""
        text = "This is plain text without frontmatter."
        
        metadata, body = parse_frontmatter(text)
        
        self.assertEqual(metadata, {})
        self.assertEqual(body, "This is plain text without frontmatter.")
    
    def test_parse_frontmatter_empty_yaml(self):
        """Test parsing frontmatter with empty YAML."""
        text = """---
---
This is the body content."""
        
        metadata, body = parse_frontmatter(text)
        
        self.assertEqual(metadata, {})
        self.assertEqual(body.strip(), "This is the body content.")


class TestIngestProcess(unittest.TestCase):
    """Test ingestion process functionality."""
    
    @patch('graph_rag.ingest.glob.glob')
    @patch('graph_rag.ingest.open')
    @patch('graph_rag.ingest.Neo4jClient')
    @patch('graph_rag.ingest.ensure_schema_loaded')
    @patch('graph_rag.ingest.call_llm_structured')
    def test_process_and_ingest_files_success(self, mock_llm, mock_schema, mock_client_class, mock_open, mock_glob):
        """Test successful file processing and ingestion."""
        # Mock glob to return test files
        mock_glob.return_value = ["data/test.md"]
        
        # Mock file content
        mock_file_content = """---
id: test_doc
title: Test Document
---
Isabella Thomas is a student with an IEP plan."""
        
        mock_file = MagicMock()
        mock_file.read.return_value = mock_file_content
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock schema loading
        mock_allow_list = {
            "node_labels": ["Student", "Plan", "Chunk"],
            "relationship_types": ["HAS_PLAN", "MENTIONS"],
            "properties": {
                "Student": ["id"],
                "Plan": ["id"],
                "Chunk": ["id", "text"]
            }
        }
        mock_schema.return_value = mock_allow_list
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock LLM response
        mock_graph = ExtractedGraph(
            nodes=[
                ExtractedNode(id="student_001", type="Student")
            ],
            relationships=[]
        )
        mock_llm.return_value = mock_graph
        
        # Test ingestion
        process_and_ingest_files()
        
        # Verify Neo4j operations were called
        self.assertGreater(mock_client.execute_write_query.call_count, 0)
        
        # Verify LLM was called
        mock_llm.assert_called()
    
    @patch('graph_rag.ingest.glob.glob')
    @patch('graph_rag.ingest.open')
    @patch('graph_rag.ingest.Neo4jClient')
    @patch('graph_rag.ingest.ensure_schema_loaded')
    def test_process_and_ingest_files_no_id(self, mock_schema, mock_client_class, mock_open, mock_glob):
        """Test file processing with missing ID in frontmatter."""
        # Mock glob to return test files
        mock_glob.return_value = ["data/test.md"]
        
        # Mock file content without ID
        mock_file_content = """---
title: Test Document
---
Isabella Thomas is a student with an IEP plan."""
        
        mock_file = MagicMock()
        mock_file.read.return_value = mock_file_content
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock schema loading
        mock_schema.return_value = {}
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Test ingestion
        process_and_ingest_files()
        
        # Verify no Neo4j operations were called (file skipped)
        mock_client.execute_write_query.assert_not_called()


class TestIngestAuditLogging(unittest.TestCase):
    """Test audit logging during ingestion."""
    
    @patch('graph_rag.ingest.glob.glob')
    @patch('graph_rag.ingest.open')
    @patch('graph_rag.ingest.Neo4jClient')
    @patch('graph_rag.ingest.ensure_schema_loaded')
    @patch('graph_rag.ingest.call_llm_structured')
    def test_audit_logging_start_complete(self, mock_llm, mock_schema, mock_client_class, mock_open, mock_glob):
        """Test audit logging for start and complete events."""
        # Mock glob to return empty list (no files)
        mock_glob.return_value = []
        
        # Mock schema loading
        mock_schema.return_value = {}
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        with patch('graph_rag.ingest.audit_store') as mock_audit:
            process_and_ingest_files()
            
            # Verify audit logging
            mock_audit.record.assert_called()
            audit_calls = mock_audit.record.call_args_list
            
            # Check for start and complete events
            start_calls = [call for call in audit_calls if "ingest.started" in str(call)]
            complete_calls = [call for call in audit_calls if "ingest.completed" in str(call)]
            
            self.assertGreater(len(start_calls), 0)
            self.assertGreater(len(complete_calls), 0)


class TestIngestErrorHandling(unittest.TestCase):
    """Test error handling during ingestion."""
    
    @patch('graph_rag.ingest.glob.glob')
    @patch('graph_rag.ingest.open')
    @patch('graph_rag.ingest.Neo4jClient')
    @patch('graph_rag.ingest.ensure_schema_loaded')
    def test_database_error_handling(self, mock_schema, mock_client_class, mock_open, mock_glob):
        """Test handling of database errors during ingestion."""
        # Mock glob to return test files
        mock_glob.return_value = ["data/test.md"]
        
        # Mock file content
        mock_file_content = """---
id: test_doc
title: Test Document
---
Test content."""
        
        mock_file = MagicMock()
        mock_file.read.return_value = mock_file_content
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock schema loading
        mock_schema.return_value = {}
        
        # Mock Neo4j client to raise exception
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.execute_write_query.side_effect = Exception("Database connection failed")
        
        # Should handle error gracefully and continue
        process_and_ingest_files()
        
        # Verify error was handled (no exception raised)
        self.assertTrue(True)  # If we get here, error was handled


if __name__ == '__main__':
    unittest.main()