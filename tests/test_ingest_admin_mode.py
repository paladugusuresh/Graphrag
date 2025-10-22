#!/usr/bin/env python3
"""
Tests for ingest.py admin mode functionality and schema embedding separation.
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock, call

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestIngestAdminMode:
    """Test ingest.py admin mode requirements and schema embedding separation."""
    
    def test_ingest_does_not_call_upsert_schema_embeddings(self, monkeypatch, tmp_path):
        """Test that ingest.py does not call upsert_schema_embeddings()."""
        # Set up environment
        monkeypatch.setenv("APP_MODE", "admin")
        monkeypatch.setenv("DEV_MODE", "true")
        monkeypatch.setenv("ALLOW_WRITES", "true")
        
        # Create temporary data directory and file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_file = data_dir / "test.md"
        test_file.write_text("""---
id: test-doc-1
title: Test Document
---
This is test content.
""")
        
        # Mock upsert_schema_embeddings to detect calls
        upsert_calls = []
        def mock_upsert_schema_embeddings():
            upsert_calls.append("called")
            return {"status": "success"}
        
        # Mock Neo4jClient
        mock_client = MagicMock()
        mock_client.execute_write_query.return_value = []
        
        # Mock LLM to avoid actual LLM calls
        mock_graph = MagicMock()
        mock_graph.nodes = []
        mock_graph.relationships = []
        
        with patch('graph_rag.ingest.Neo4jClient', return_value=mock_client), \
             patch('graph_rag.ingest.call_llm_structured', return_value=mock_graph), \
             patch('graph_rag.schema_embeddings.upsert_schema_embeddings', side_effect=mock_upsert_schema_embeddings), \
             patch('graph_rag.ingest.DATA_DIR', str(data_dir)):
            
            # Import and run ingest
            from graph_rag.ingest import process_and_ingest_files
            process_and_ingest_files()
        
        # Assert upsert_schema_embeddings was not called
        assert len(upsert_calls) == 0, f"upsert_schema_embeddings was called {len(upsert_calls)} times"
    
    def test_ingest_calls_ensure_schema_loaded(self, monkeypatch, tmp_path):
        """Test that ingest.py calls ensure_schema_loaded(force=True)."""
        # Set up environment
        monkeypatch.setenv("APP_MODE", "admin")
        monkeypatch.setenv("DEV_MODE", "true")
        monkeypatch.setenv("ALLOW_WRITES", "true")
        
        # Create temporary data directory and file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_file = data_dir / "test.md"
        test_file.write_text("""---
id: test-doc-1
title: Test Document
---
This is test content.
""")
        
        # Track calls to ensure_schema_loaded
        ensure_schema_calls = []
        def mock_ensure_schema_loaded(force=False):
            ensure_schema_calls.append({"force": force})
            return {"node_labels": ["Student"], "relationship_types": ["HAS_GOAL"]}
        
        # Mock Neo4jClient
        mock_client = MagicMock()
        mock_client.execute_write_query.return_value = []
        
        # Mock LLM to avoid actual LLM calls
        mock_graph = MagicMock()
        mock_graph.nodes = []
        mock_graph.relationships = []
        
        with patch('graph_rag.ingest.Neo4jClient', return_value=mock_client), \
             patch('graph_rag.ingest.call_llm_structured', return_value=mock_graph), \
             patch('graph_rag.ingest.ensure_schema_loaded', side_effect=mock_ensure_schema_loaded), \
             patch('graph_rag.ingest.DATA_DIR', str(data_dir)):
            
            # Import and run ingest
            from graph_rag.ingest import process_and_ingest_files
            process_and_ingest_files()
        
        # Assert ensure_schema_loaded was called with force=True
        assert len(ensure_schema_calls) > 0, "ensure_schema_loaded was not called"
        assert any(call["force"] for call in ensure_schema_calls), "ensure_schema_loaded was not called with force=True"
    
    def test_ingest_creates_allow_list_file(self, monkeypatch, tmp_path):
        """Test that ingest.py creates allow_list.json file."""
        # Set up environment
        monkeypatch.setenv("APP_MODE", "admin")
        monkeypatch.setenv("DEV_MODE", "true")
        monkeypatch.setenv("ALLOW_WRITES", "true")
        
        # Create temporary data directory and file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_file = data_dir / "test.md"
        test_file.write_text("""---
id: test-doc-1
title: Test Document
---
This is test content.
""")
        
        # Mock Neo4jClient
        mock_client = MagicMock()
        mock_client.execute_write_query.return_value = []
        
        # Mock LLM to avoid actual LLM calls
        mock_graph = MagicMock()
        mock_graph.nodes = []
        mock_graph.relationships = []
        
        with patch('graph_rag.ingest.Neo4jClient', return_value=mock_client), \
             patch('graph_rag.ingest.call_llm_structured', return_value=mock_graph), \
             patch('graph_rag.ingest.DATA_DIR', str(data_dir)):
            
            # Import and run ingest
            from graph_rag.ingest import process_and_ingest_files
            process_and_ingest_files()
        
        # Assert allow_list.json was created
        assert os.path.exists("allow_list.json"), "allow_list.json was not created"
        
        # Verify it's valid JSON
        import json
        with open("allow_list.json", "r") as f:
            allow_list = json.load(f)
        assert "node_labels" in allow_list, "allow_list.json missing node_labels"
        assert "relationship_types" in allow_list, "allow_list.json missing relationship_types"
    
    def test_ingest_requires_admin_mode(self, monkeypatch):
        """Test that ingest.py raises RuntimeError without admin mode."""
        # Set up non-admin environment
        monkeypatch.setenv("APP_MODE", "read_only")
        monkeypatch.setenv("ALLOW_WRITES", "false")
        
        # The RuntimeError is raised at module import time, so we need to test the import
        with pytest.raises(RuntimeError, match="Ingest must be run with APP_MODE=admin or ALLOW_WRITES=true"):
            # Force reimport by removing from sys.modules if present
            if 'graph_rag.ingest' in sys.modules:
                del sys.modules['graph_rag.ingest']
            import graph_rag.ingest
    
    def test_ingest_allows_writes_env_var(self, monkeypatch, tmp_path):
        """Test that ingest.py allows ALLOW_WRITES=true without APP_MODE=admin."""
        # Set up environment with ALLOW_WRITES=true but APP_MODE=read_only
        monkeypatch.setenv("APP_MODE", "read_only")
        monkeypatch.setenv("ALLOW_WRITES", "true")
        monkeypatch.setenv("DEV_MODE", "true")
        
        # Create temporary data directory and file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_file = data_dir / "test.md"
        test_file.write_text("""---
id: test-doc-1
title: Test Document
---
This is test content.
""")
        
        # Mock Neo4jClient
        mock_client = MagicMock()
        mock_client.execute_write_query.return_value = []
        
        # Mock LLM to avoid actual LLM calls
        mock_graph = MagicMock()
        mock_graph.nodes = []
        mock_graph.relationships = []
        
        with patch('graph_rag.ingest.Neo4jClient', return_value=mock_client), \
             patch('graph_rag.ingest.call_llm_structured', return_value=mock_graph), \
             patch('graph_rag.ingest.DATA_DIR', str(data_dir)):
            
            # Import and run ingest - should not raise RuntimeError
            from graph_rag.ingest import process_and_ingest_files
            process_and_ingest_files()  # Should complete without error
    
    def test_ingest_uses_schema_manager_not_schema_embeddings(self, monkeypatch, tmp_path):
        """Test that ingest.py imports and uses schema_manager, not schema_embeddings."""
        # Set up environment
        monkeypatch.setenv("APP_MODE", "admin")
        monkeypatch.setenv("DEV_MODE", "true")
        monkeypatch.setenv("ALLOW_WRITES", "true")
        
        # Create temporary data directory and file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_file = data_dir / "test.md"
        test_file.write_text("""---
id: test-doc-1
title: Test Document
---
This is test content.
""")
        
        # Track imports
        schema_manager_called = False
        schema_embeddings_called = False
        
        def mock_ensure_schema_loaded(force=False):
            nonlocal schema_manager_called
            schema_manager_called = True
            return {"node_labels": ["Student"], "relationship_types": ["HAS_GOAL"]}
        
        def mock_upsert_schema_embeddings():
            nonlocal schema_embeddings_called
            schema_embeddings_called = True
            return {"status": "success"}
        
        # Mock Neo4jClient
        mock_client = MagicMock()
        mock_client.execute_write_query.return_value = []
        
        # Mock LLM to avoid actual LLM calls
        mock_graph = MagicMock()
        mock_graph.nodes = []
        mock_graph.relationships = []
        
        with patch('graph_rag.ingest.Neo4jClient', return_value=mock_client), \
             patch('graph_rag.ingest.call_llm_structured', return_value=mock_graph), \
             patch('graph_rag.ingest.ensure_schema_loaded', side_effect=mock_ensure_schema_loaded), \
             patch('graph_rag.schema_embeddings.upsert_schema_embeddings', side_effect=mock_upsert_schema_embeddings), \
             patch('graph_rag.ingest.DATA_DIR', str(data_dir)):
            
            # Import and run ingest
            from graph_rag.ingest import process_and_ingest_files
            process_and_ingest_files()
        
        # Assert schema_manager was used, schema_embeddings was not
        assert schema_manager_called, "ensure_schema_loaded from schema_manager was not called"
        assert not schema_embeddings_called, "upsert_schema_embeddings from schema_embeddings was called"
    
    def test_ingest_file_content_separation(self):
        """Test that ingest.py file content does not import schema_embeddings."""
        with open('graph_rag/ingest.py', 'r') as f:
            content = f.read()
        
        # Should import schema_manager
        assert "from graph_rag.schema_manager import ensure_schema_loaded" in content, \
            "Missing import of ensure_schema_loaded from schema_manager"
        
        # Should NOT import schema_embeddings
        assert "from graph_rag.schema_embeddings import" not in content, \
            "Found import from schema_embeddings - should not be present"
        
        # Should have ownership comment
        assert "Schema embeddings (SchemaTerm nodes) are managed by schema_manager/schema_embeddings" in content, \
            "Missing ownership comment about schema embeddings"
        
        # Should use ensure_schema_loaded
        assert "allow_list = ensure_schema_loaded(force=True)" in content, \
            "Missing call to ensure_schema_loaded(force=True)"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
