import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json
from pydantic import BaseModel
from prometheus_client import REGISTRY

class DummySchema(BaseModel):
    field_a: str
    field_b: int

class TestLLMClientStructured(unittest.TestCase):

    def setUp(self):
        if 'graph_rag.llm_client' in sys.modules:
            del sys.modules['graph_rag.llm_client']
        if 'graph_rag.audit_store' in sys.modules:
            del sys.modules['graph_rag.audit_store']
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0", "DEV_MODE": "true"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gemini-2.0-flash-exp",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_malformed_json(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_get_redis_client):
        # Mock consume_token to always allow consumption
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = 1
        mock_get_redis_client.return_value = mock_redis_instance

        mock_call_llm_raw.return_value = "this is not json"
        
        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError

        with self.assertRaises(LLMStructuredError) as cm:
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        self.assertIn("Invalid JSON from LLM", str(cm.exception))
        # Verify audit was recorded (with retries, it will try 3 times)
        self.assertTrue(mock_audit_store.record.called)
        audit_entry = mock_audit_store.record.call_args[1]['entry']
        self.assertEqual(audit_entry['type'], 'llm_parse_failure')
        self.assertEqual(audit_entry['response'], 'this is not json')
        self.assertEqual(audit_entry['schema_model'], 'DummySchema')
        self.assertEqual(audit_entry['attempts'], 3)  # Should retry 2 times (3 total attempts)

    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0", "DEV_MODE": "true"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gemini-2.0-flash-exp",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_validation_error(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_get_redis_client):
        # Mock consume_token to always allow consumption
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = 1
        mock_get_redis_client.return_value = mock_redis_instance

        mock_call_llm_raw.return_value = json.dumps({"field_a": "value", "field_c": 123}) # Missing field_b

        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError

        with self.assertRaises(LLMStructuredError) as cm:
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        self.assertIn("Structured output failed validation", str(cm.exception))
        # Verify audit was recorded (with retries, it will try 3 times)
        self.assertTrue(mock_audit_store.record.called)
        audit_entry = mock_audit_store.record.call_args[1]['entry']
        self.assertEqual(audit_entry['type'], 'llm_validation_failed')
        self.assertEqual(audit_entry['response'], json.dumps({"field_a": "value", "field_c": 123}))
        self.assertEqual(audit_entry['schema_model'], 'DummySchema')
        self.assertEqual(audit_entry['attempts'], 3)  # Should retry 2 times (3 total attempts)

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    @patch("graph_rag.rate_limit._get_redis_client")
    @patch("graph_rag.rate_limit.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0", "DEV_MODE": "true"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gemini-2.0-flash-exp",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_rate_limit_exceeded(self, mock_open, mock_audit_store, mock_get_redis_client, mock_limit_flag):
        # Enable rate limiting and simulate limit exceeded
        mock_limit_flag.return_value = 1  # Very low limit
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = 0  # Rate limit exceeded
        mock_get_redis_client.return_value = mock_redis_instance

        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError

        with self.assertRaises(LLMStructuredError) as cm:
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        self.assertIn("rate limit exceeded", str(cm.exception).lower())
        # Verify audit was called by the rate_limit module
        self.assertTrue(mock_audit_store.record.called)
        # Verify audit contains rate limit information
        audit_call = mock_audit_store.record.call_args[0][0]
        self.assertEqual(audit_call["event"], "llm_rate_limit_exceeded")

    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0", "DEV_MODE": "true"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gemini-2.0-flash-exp",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_success(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_get_redis_client):
        # Mock consume_token to always allow consumption
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = 1
        mock_get_redis_client.return_value = mock_redis_instance
        mock_call_llm_raw.return_value = json.dumps({"field_a": "value", "field_b": 123})

        import graph_rag.llm_client
        result = graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)

        self.assertIsInstance(result, DummySchema)
        self.assertEqual(result.field_a, "value")
        self.assertEqual(result.field_b, 123)
        mock_audit_store.record.assert_not_called()
