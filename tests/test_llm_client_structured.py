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

    @patch("graph_rag.llm_client.redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gpt-4o",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_malformed_json(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_redis_client):
        # Mock consume_token to always allow consumption
        mock_redis_client.eval.return_value = 1

        mock_call_llm_raw.return_value = "this is not json"
        
        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError

        with self.assertRaises(LLMStructuredError) as cm:
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        self.assertIn("Invalid JSON from LLM", str(cm.exception))
        mock_audit_store.record.assert_called_once_with(
            entry={
                "type": "llm_parse_failure",
                "prompt": "test prompt",
                "response": "this is not json",
                "error": unittest.mock.ANY,
                "trace_id": unittest.mock.ANY # trace_id can be None in this test context
            }
        )

    @patch("graph_rag.llm_client.redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gpt-4o",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_validation_error(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_redis_client):
        # Mock consume_token to always allow consumption
        mock_redis_client.eval.return_value = 1

        mock_call_llm_raw.return_value = json.dumps({"field_a": "value", "field_c": 123}) # Missing field_b

        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError

        with self.assertRaises(LLMStructuredError) as cm:
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        self.assertIn("Structured output failed validation", str(cm.exception))
        mock_audit_store.record.assert_called_once_with(
            entry={
                "type": "llm_validation_failed",
                "prompt": "test prompt",
                "response": json.dumps({"field_a": "value", "field_c": 123}),
                "error": unittest.mock.ANY,
                "trace_id": unittest.mock.ANY # trace_id can be None in this test context
            }
        )

    @patch("graph_rag.llm_client.redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gpt-4o",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_rate_limit_exceeded(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_redis_client):
        # Mock consume_token to deny consumption
        mock_redis_client.eval.return_value = 0

        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError

        with self.assertRaises(LLMStructuredError) as cm:
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        self.assertIn("LLM rate limit exceeded", str(cm.exception))
        mock_call_llm_raw.assert_not_called()
        mock_audit_store.record.assert_not_called()

    @patch("graph_rag.llm_client.redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gpt-4o",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_success(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_redis_client):
        # Mock consume_token to always allow consumption
        mock_redis_client.eval.return_value = 1
        mock_call_llm_raw.return_value = json.dumps({"field_a": "value", "field_b": 123})

        import graph_rag.llm_client
        result = graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)

        self.assertIsInstance(result, DummySchema)
        self.assertEqual(result.field_a, "value")
        self.assertEqual(result.field_b, 123)
        mock_audit_store.record.assert_not_called()
