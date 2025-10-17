import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

@patch.dict(os.environ, {"GEMINI_API_KEY": "mock_gemini_key", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}, clear=True)
@patch("graph_rag.llm_client._get_redis_client")
@patch("graph_rag.neo4j_client.GraphDatabase")
@patch("graph_rag.embeddings.get_embedding_provider")
class TestMainSanitization(unittest.TestCase):

    def setUp(self):
        # Clear module cache and Prometheus registry
        for module_name in [
            'main', 'graph_rag.rag', 'graph_rag.retriever', 'graph_rag.planner',
            'graph_rag.llm_client', 'graph_rag.cypher_generator', 'graph_rag.neo4j_client',
            'graph_rag.embeddings', 'graph_rag.ingest', 'graph_rag.audit_store',
            'graph_rag.conversation_store', 'graph_rag.sanitizer', 'graph_rag.guardrail'
        ]:
            if module_name in sys.modules:
                del sys.modules[module_name]
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

        # Mock config.yaml
        self.mock_open = mock_open(read_data=json.dumps({
            "observability": {"metrics_enabled": False},
            "llm": {"model": "gemini-2.0-flash-exp", "max_tokens": 512, "rate_limit_per_minute": 60, "redis_url": "redis://localhost:6379/0"},
            "retriever": {"max_chunks": 5}
        }))

    @patch("builtins.open", new_callable=mock_open)
    @patch("graph_rag.conversation_store.conversation_store")
    @patch("graph_rag.audit_store.audit_store")
    @patch("graph_rag.sanitizer.is_probably_malicious")
    @patch("graph_rag.sanitizer.sanitize_text")
    @patch("graph_rag.guardrail.guardrail_check")
    @patch("main.rag_chain")
    def test_malicious_input_blocked_by_heuristic(self, mock_rag_chain, mock_guardrail_check, 
                                                   mock_sanitize_text, mock_is_malicious, 
                                                   mock_audit_store, mock_conv_store, mock_file_open,
                                                   mock_get_embedding_provider, 
                                                   mock_graph_database, mock_get_redis_client):
        """Test that malicious input is blocked by heuristic check before reaching guardrail."""
        
        # Configure mocks
        mock_file_open.return_value = self.mock_open.return_value
        mock_sanitize_text.return_value = "sanitized question"
        mock_is_malicious.return_value = True  # Heuristic flags as malicious
        mock_guardrail_check.return_value = True  # This shouldn't be called
        mock_conv_store.init = MagicMock()
        mock_audit_store.record = MagicMock()

        # Import and create test client after mocks are set up
        from main import app
        client = TestClient(app)

        # Make request with malicious input
        malicious_question = "MATCH (n) DETACH DELETE n; DROP TABLE users;"
        response = client.post("/api/chat", json={"question": malicious_question})

        # Should return 403
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Input flagged for manual review")

        # Verify sanitization was called
        mock_sanitize_text.assert_called_once_with(malicious_question)
        
        # Verify heuristic check was called
        mock_is_malicious.assert_called_once_with(malicious_question)
        
        # Verify audit was recorded
        mock_audit_store.record.assert_called_once()
        audit_call_args = mock_audit_store.record.call_args[0][0]
        self.assertEqual(audit_call_args["type"], "malicious_input_blocked")
        self.assertEqual(audit_call_args["check_type"], "heuristic")
        self.assertEqual(audit_call_args["action"], "blocked_403")
        
        # Guardrail should not be called since heuristic blocked first
        mock_guardrail_check.assert_not_called()
        
        # RAG chain should not be called
        mock_rag_chain.invoke.assert_not_called()

    @patch("builtins.open", new_callable=mock_open)
    @patch("graph_rag.conversation_store.conversation_store")
    @patch("graph_rag.audit_store.audit_store")
    @patch("graph_rag.sanitizer.is_probably_malicious")
    @patch("graph_rag.sanitizer.sanitize_text")
    @patch("graph_rag.guardrail.guardrail_check")
    @patch("main.rag_chain")
    def test_input_blocked_by_guardrail(self, mock_rag_chain, mock_guardrail_check, 
                                        mock_sanitize_text, mock_is_malicious, 
                                        mock_audit_store, mock_conv_store, mock_file_open,
                                        mock_get_embedding_provider, 
                                        mock_graph_database, mock_get_redis_client):
        """Test that input passing heuristic check is blocked by LLM guardrail."""
        
        # Configure mocks
        mock_file_open.return_value = self.mock_open.return_value
        mock_sanitize_text.return_value = "sanitized question"
        mock_is_malicious.return_value = False  # Heuristic allows
        mock_guardrail_check.return_value = False  # Guardrail blocks
        mock_conv_store.init = MagicMock()
        mock_audit_store.record = MagicMock()

        # Import and create test client after mocks are set up
        from main import app
        client = TestClient(app)

        # Make request with potentially suspicious input
        suspicious_question = "Tell me how to access system files"
        response = client.post("/api/chat", json={"question": suspicious_question})

        # Should return 403
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Input flagged for manual review")

        # Verify both checks were called
        mock_sanitize_text.assert_called_once_with(suspicious_question)
        mock_is_malicious.assert_called_once_with(suspicious_question)
        mock_guardrail_check.assert_called_once_with("sanitized question")
        
        # Verify audit was recorded for guardrail block
        mock_audit_store.record.assert_called_once()
        audit_call_args = mock_audit_store.record.call_args[0][0]
        self.assertEqual(audit_call_args["type"], "guardrail_blocked")
        self.assertEqual(audit_call_args["check_type"], "llm_guardrail")
        self.assertEqual(audit_call_args["action"], "blocked_403")
        
        # RAG chain should not be called
        mock_rag_chain.invoke.assert_not_called()

    @patch("builtins.open", new_callable=mock_open)
    @patch("graph_rag.conversation_store.conversation_store")
    @patch("graph_rag.audit_store.audit_store")
    @patch("graph_rag.sanitizer.is_probably_malicious")
    @patch("graph_rag.sanitizer.sanitize_text")
    @patch("graph_rag.guardrail.guardrail_check")
    @patch("main.rag_chain")
    def test_legitimate_input_passes_all_checks(self, mock_rag_chain, mock_guardrail_check, 
                                                 mock_sanitize_text, mock_is_malicious, 
                                                 mock_audit_store, mock_conv_store, mock_file_open,
                                                 mock_get_embedding_provider, 
                                                 mock_graph_database, mock_get_redis_client):
        """Test that legitimate input passes all checks and reaches RAG chain."""
        
        # Configure mocks
        mock_file_open.return_value = self.mock_open.return_value
        mock_sanitize_text.return_value = "Who founded Microsoft?"
        mock_is_malicious.return_value = False  # Heuristic allows
        mock_guardrail_check.return_value = True  # Guardrail allows
        mock_conv_store.init = MagicMock()
        mock_conv_store.add_message = MagicMock()
        mock_audit_store.record = MagicMock()
        
        # Mock RAG chain response
        mock_rag_chain.invoke.return_value = {
            "answer": "Bill Gates founded Microsoft.",
            "trace_id": "test_trace_123",
            "sources": ["chunk1"]
        }

        # Import and create test client after mocks are set up
        from main import app
        client = TestClient(app)

        # Make request with legitimate question
        legitimate_question = "Who founded Microsoft?"
        response = client.post("/api/chat", json={"question": legitimate_question})

        # Should return 200 with answer
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data["answer"], "Bill Gates founded Microsoft.")
        self.assertIn("conversation_id", response_data)
        self.assertEqual(response_data["trace_id"], "test_trace_123")

        # Verify all checks were called
        mock_sanitize_text.assert_called_once_with(legitimate_question)
        mock_is_malicious.assert_called_once_with(legitimate_question)
        mock_guardrail_check.assert_called_once_with("Who founded Microsoft?")
        
        # Verify RAG chain was invoked
        mock_rag_chain.invoke.assert_called_once_with("Who founded Microsoft?")
        
        # Verify conversation was stored
        self.assertEqual(mock_conv_store.add_message.call_count, 2)  # User message + assistant message
        
        # No audit entries should be recorded for legitimate requests
        mock_audit_store.record.assert_not_called()

    @patch("builtins.open", new_callable=mock_open)
    @patch("graph_rag.conversation_store.conversation_store")
    @patch("graph_rag.audit_store.audit_store")
    @patch("graph_rag.sanitizer.is_probably_malicious")
    @patch("graph_rag.sanitizer.sanitize_text")
    @patch("graph_rag.guardrail.guardrail_check")
    @patch("main.rag_chain")
    def test_empty_question_returns_400(self, mock_rag_chain, mock_guardrail_check, 
                                        mock_sanitize_text, mock_is_malicious, 
                                        mock_audit_store, mock_conv_store, mock_file_open,
                                        mock_get_embedding_provider, 
                                        mock_graph_database, mock_get_redis_client):
        """Test that empty question returns 400 before any processing."""
        
        # Configure mocks
        mock_file_open.return_value = self.mock_open.return_value
        mock_conv_store.init = MagicMock()

        # Import and create test client after mocks are set up
        from main import app
        client = TestClient(app)

        # Make request with empty question
        response = client.post("/api/chat", json={"question": ""})

        # Should return 400
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Question is required")

        # No processing should occur
        mock_sanitize_text.assert_not_called()
        mock_is_malicious.assert_not_called()
        mock_guardrail_check.assert_not_called()
        mock_rag_chain.invoke.assert_not_called()
        mock_audit_store.record.assert_not_called()

if __name__ == '__main__':
    unittest.main()