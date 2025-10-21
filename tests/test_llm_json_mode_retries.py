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


class TestLLMJsonModeRetries(unittest.TestCase):
    """
    Tests for LLM JSON mode, temperature=0, and retry logic.
    Tests the LLM_JSON_MODE_ENABLED flag integration.
    """

    def setUp(self):
        """Clean up modules before each test"""
        modules_to_clear = [
            'graph_rag.llm_client',
            'graph_rag.audit_store',
            'graph_rag.flags',
            'graph_rag.config_manager'
        ]
        for module in modules_to_clear:
            if module in sys.modules:
                del sys.modules[module]
        
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {
        "REDIS_URL": "redis://localhost:6379/0",
        "DEV_MODE": "true",
        "LLM_JSON_MODE_ENABLED": "true"
    }, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {"model": "gemini-2.0-flash-exp", "max_tokens": 512, "rate_limit_per_minute": 60}
    }))
    def test_retry_on_invalid_json_success_on_second_attempt(self, mock_file, mock_audit, mock_call_raw, mock_redis):
        """Test that invalid JSON on first try is retried and succeeds on second attempt"""
        # Mock Redis to allow token consumption
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = 1
        mock_redis.return_value = mock_redis_instance
        
        # First call returns invalid JSON, second call returns valid JSON
        mock_call_raw.side_effect = [
            "this is not json",
            json.dumps({"field_a": "value", "field_b": 123})
        ]
        
        import graph_rag.llm_client
        result = graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        # Should succeed after retry
        self.assertIsInstance(result, DummySchema)
        self.assertEqual(result.field_a, "value")
        self.assertEqual(result.field_b, 123)
        
        # Should have been called twice
        self.assertEqual(mock_call_raw.call_count, 2)
        
        # Verify JSON mode was enabled in both calls
        for call in mock_call_raw.call_args_list:
            self.assertTrue(call.kwargs.get('json_mode'))
            self.assertEqual(call.kwargs.get('temperature'), 0.0)

    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {
        "REDIS_URL": "redis://localhost:6379/0",
        "DEV_MODE": "true",
        "LLM_JSON_MODE_ENABLED": "true"
    }, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {"model": "gemini-2.0-flash-exp", "max_tokens": 512, "rate_limit_per_minute": 60}
    }))
    def test_retry_on_validation_error_success_on_third_attempt(self, mock_file, mock_audit, mock_call_raw, mock_redis):
        """Test that validation errors are retried up to 2 times"""
        # Mock Redis to allow token consumption
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = 1
        mock_redis.return_value = mock_redis_instance
        
        # First two calls have wrong schema, third is correct
        mock_call_raw.side_effect = [
            json.dumps({"field_a": "value"}),  # Missing field_b
            json.dumps({"field_b": 123}),  # Missing field_a
            json.dumps({"field_a": "value", "field_b": 123})  # Correct
        ]
        
        import graph_rag.llm_client
        result = graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        # Should succeed after 2 retries
        self.assertIsInstance(result, DummySchema)
        self.assertEqual(result.field_a, "value")
        self.assertEqual(result.field_b, 123)
        
        # Should have been called 3 times (initial + 2 retries)
        self.assertEqual(mock_call_raw.call_count, 3)

    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {
        "REDIS_URL": "redis://localhost:6379/0",
        "DEV_MODE": "true",
        "LLM_JSON_MODE_ENABLED": "true"
    }, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {"model": "gemini-2.0-flash-exp", "max_tokens": 512, "rate_limit_per_minute": 60}
    }))
    def test_retry_exhausted_raises_error(self, mock_file, mock_audit, mock_call_raw, mock_redis):
        """Test that after max retries (2), error is raised"""
        # Mock Redis to allow token consumption
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = 1
        mock_redis.return_value = mock_redis_instance
        
        # All calls return invalid JSON
        mock_call_raw.return_value = "this is not json"
        
        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError
        
        with self.assertRaises(LLMStructuredError) as cm:
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        self.assertIn("Invalid JSON from LLM", str(cm.exception))
        
        # Should have been called 3 times (initial + 2 retries)
        self.assertEqual(mock_call_raw.call_count, 3)
        
        # Audit should be recorded
        self.assertTrue(mock_audit.record.called)
        audit_call = mock_audit.record.call_args[1]['entry']
        self.assertEqual(audit_call['type'], 'llm_parse_failure')
        self.assertEqual(audit_call['attempts'], 3)

    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {
        "REDIS_URL": "redis://localhost:6379/0",
        "DEV_MODE": "true",
        "LLM_JSON_MODE_ENABLED": "false"
    }, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {"model": "gemini-2.0-flash-exp", "max_tokens": 512, "rate_limit_per_minute": 60}
    }))
    def test_no_retry_when_json_mode_disabled(self, mock_file, mock_audit, mock_call_raw, mock_redis):
        """Test that retries don't happen when LLM_JSON_MODE_ENABLED=false"""
        # Mock Redis to allow token consumption
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = 1
        mock_redis.return_value = mock_redis_instance
        
        # Return invalid JSON
        mock_call_raw.return_value = "this is not json"
        
        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError
        
        with self.assertRaises(LLMStructuredError):
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        # Should have been called only once (no retries)
        self.assertEqual(mock_call_raw.call_count, 1)
        
        # Verify JSON mode was NOT enabled
        call_kwargs = mock_call_raw.call_args.kwargs
        self.assertFalse(call_kwargs.get('json_mode'))

    @patch("graph_rag.llm_client._get_redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {
        "REDIS_URL": "redis://localhost:6379/0",
        "DEV_MODE": "true",
        "LLM_JSON_MODE_ENABLED": "true"
    }, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {"model": "gemini-2.0-flash-exp", "max_tokens": 512, "rate_limit_per_minute": 60}
    }))
    def test_json_mode_parameters_passed_correctly(self, mock_file, mock_audit, mock_call_raw, mock_redis):
        """Test that JSON mode and temperature=0 are passed to call_llm_raw"""
        # Mock Redis to allow token consumption
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = 1
        mock_redis.return_value = mock_redis_instance
        
        # Return valid JSON
        mock_call_raw.return_value = json.dumps({"field_a": "value", "field_b": 123})
        
        import graph_rag.llm_client
        result = graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        # Verify parameters
        call_kwargs = mock_call_raw.call_args.kwargs
        self.assertTrue(call_kwargs.get('json_mode'))
        self.assertEqual(call_kwargs.get('temperature'), 0.0)
        self.assertEqual(call_kwargs.get('max_tokens'), 512)


class TestGuardrailFailClosed(unittest.TestCase):
    """
    Tests for guardrail fail-closed behavior with GUARDRAILS_FAIL_CLOSED_DEV flag.
    """

    def setUp(self):
        """Clean up modules before each test"""
        modules_to_clear = [
            'graph_rag.guardrail',
            'graph_rag.llm_client',
            'graph_rag.audit_store',
            'graph_rag.flags',
            'graph_rag.config_manager'
        ]
        for module in modules_to_clear:
            if module in sys.modules:
                del sys.modules[module]
        
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("graph_rag.guardrail.call_llm_structured")
    @patch("graph_rag.guardrail.audit_store")
    @patch.dict(os.environ, {
        "DEV_MODE": "true",
        "GUARDRAILS_FAIL_CLOSED_DEV": "false"
    }, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({}))
    def test_guardrail_fails_open_in_dev_mode(self, mock_file, mock_audit, mock_llm):
        """Test that guardrail allows request when LLM fails in DEV mode (fail open)"""
        from graph_rag.llm_client import LLMStructuredError
        
        # Simulate LLM failure
        mock_llm.side_effect = LLMStructuredError("Invalid JSON from LLM")
        
        import graph_rag.guardrail
        result = graph_rag.guardrail.guardrail_check("test question")
        
        # Should ALLOW (fail open) in dev mode
        self.assertTrue(result)
        
        # Verify audit log
        self.assertTrue(mock_audit.record.called)
        audit_call = mock_audit.record.call_args[0][0]
        self.assertEqual(audit_call['event'], 'guardrail_classification_failed_allowed')
        self.assertEqual(audit_call['fail_mode'], 'open')

    @patch("graph_rag.guardrail.call_llm_structured")
    @patch("graph_rag.guardrail.audit_store")
    @patch.dict(os.environ, {
        "DEV_MODE": "false",
        "GUARDRAILS_FAIL_CLOSED_DEV": "true"
    }, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({}))
    def test_guardrail_fails_closed_in_prod_mode(self, mock_file, mock_audit, mock_llm):
        """Test that guardrail blocks request when LLM fails in PROD mode (fail closed)"""
        from graph_rag.llm_client import LLMStructuredError
        
        # Simulate LLM failure
        mock_llm.side_effect = LLMStructuredError("Invalid JSON from LLM")
        
        import graph_rag.guardrail
        result = graph_rag.guardrail.guardrail_check("test question")
        
        # Should BLOCK (fail closed) in prod mode
        self.assertFalse(result)
        
        # Verify audit log
        self.assertTrue(mock_audit.record.called)
        audit_call = mock_audit.record.call_args[0][0]
        self.assertEqual(audit_call['event'], 'guardrail_classification_failed')
        self.assertEqual(audit_call['fail_mode'], 'closed')

    @patch("graph_rag.guardrail.call_llm_structured")
    @patch("graph_rag.guardrail.audit_store")
    @patch.dict(os.environ, {"DEV_MODE": "true"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({}))
    def test_guardrail_success_returns_llm_decision(self, mock_file, mock_audit, mock_llm):
        """Test that successful guardrail check returns LLM decision"""
        from graph_rag.guardrail import GuardrailResponse
        
        # Simulate successful LLM response - allowed
        mock_llm.return_value = GuardrailResponse(allowed=True, reason="Legitimate business question")
        
        import graph_rag.guardrail
        result = graph_rag.guardrail.guardrail_check("What is the revenue of Company XYZ?")
        
        # Should return the LLM's decision (allowed)
        self.assertTrue(result)
        
        # Simulate successful LLM response - blocked
        mock_llm.return_value = GuardrailResponse(allowed=False, reason="Potential SQL injection")
        result = graph_rag.guardrail.guardrail_check("DROP TABLE users;")
        
        # Should return the LLM's decision (blocked)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()

