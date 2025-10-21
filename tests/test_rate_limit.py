import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
import time

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.rate_limit import (
    rate_limited_llm,
    RateLimitExceeded,
    consume_token_with_limit,
    _build_rate_limit_key,
    get_current_rate_limit_usage
)


class TestRateLimitKey(unittest.TestCase):
    """Tests for rate limit key building"""

    def test_build_rate_limit_key(self):
        """Test that rate limit keys are built correctly"""
        key = _build_rate_limit_key("call_llm_raw", "gemini-2.0-flash-exp")
        self.assertEqual(key, "graphrag:llm:rate_limit:call_llm_raw:gemini-2.0-flash-exp")

    def test_build_rate_limit_key_sanitizes_colons(self):
        """Test that colons are sanitized in keys"""
        key = _build_rate_limit_key("my:endpoint", "my:model")
        self.assertEqual(key, "graphrag:llm:rate_limit:my_endpoint:my_model")

    def test_build_rate_limit_key_sanitizes_spaces(self):
        """Test that spaces are sanitized in keys"""
        key = _build_rate_limit_key("my endpoint", "my model")
        self.assertEqual(key, "graphrag:llm:rate_limit:my_endpoint:my_model")


class TestConsumeTokenWithLimit(unittest.TestCase):
    """Tests for token consumption"""

    @patch("graph_rag.rate_limit._get_redis_client")
    def test_consume_token_disabled_when_zero(self, mock_redis_getter):
        """Test that rate limiting is disabled when limit is 0"""
        result = consume_token_with_limit("test_endpoint", "test_model", rate_limit_per_min=0)
        self.assertTrue(result)
        # Redis should not be called
        mock_redis_getter.assert_not_called()

    @patch("graph_rag.rate_limit._get_redis_client")
    def test_consume_token_success(self, mock_redis_getter):
        """Test successful token consumption"""
        mock_redis = MagicMock()
        mock_redis.eval.return_value = 1  # Success
        mock_redis_getter.return_value = mock_redis
        
        result = consume_token_with_limit("test_endpoint", "test_model", rate_limit_per_min=10)
        
        self.assertTrue(result)
        self.assertTrue(mock_redis.eval.called)

    @patch("graph_rag.rate_limit._get_redis_client")
    def test_consume_token_rate_limit_exceeded(self, mock_redis_getter):
        """Test token consumption when rate limit exceeded"""
        mock_redis = MagicMock()
        mock_redis.eval.return_value = 0  # Rate limit exceeded
        mock_redis_getter.return_value = mock_redis
        
        result = consume_token_with_limit("test_endpoint", "test_model", rate_limit_per_min=10)
        
        self.assertFalse(result)
        self.assertTrue(mock_redis.eval.called)

    @patch("graph_rag.rate_limit._get_redis_client")
    def test_consume_token_redis_error_fails_open(self, mock_redis_getter):
        """Test that Redis errors fail open (allow request)"""
        mock_redis = MagicMock()
        mock_redis.eval.side_effect = Exception("Redis connection error")
        mock_redis_getter.return_value = mock_redis
        
        result = consume_token_with_limit("test_endpoint", "test_model", rate_limit_per_min=10)
        
        # Should fail open
        self.assertTrue(result)


class TestRateLimitedDecorator(unittest.TestCase):
    """Tests for @rate_limited_llm decorator"""

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    @patch("graph_rag.rate_limit.consume_token_with_limit")
    def test_decorator_disabled_when_limit_zero(self, mock_consume, mock_limit_flag):
        """Test that decorator is disabled when LLM_RATE_LIMIT_PER_MIN=0"""
        mock_limit_flag.return_value = 0
        
        @rate_limited_llm(endpoint_name="test_endpoint")
        def test_func(prompt: str, model: str):
            return "success"
        
        result = test_func("test prompt", "test-model")
        
        self.assertEqual(result, "success")
        mock_consume.assert_not_called()

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    @patch("graph_rag.rate_limit.consume_token_with_limit")
    def test_decorator_allows_when_under_limit(self, mock_consume, mock_limit_flag):
        """Test that decorator allows calls when under limit"""
        mock_limit_flag.return_value = 10
        mock_consume.return_value = True  # Under limit
        
        @rate_limited_llm(endpoint_name="test_endpoint")
        def test_func(prompt: str, model: str):
            return "success"
        
        result = test_func("test prompt", "test-model")
        
        self.assertEqual(result, "success")
        mock_consume.assert_called_once_with("test_endpoint", "test-model", 10)

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    @patch("graph_rag.rate_limit.consume_token_with_limit")
    @patch("graph_rag.rate_limit.llm_rate_limit_hits")
    @patch("graph_rag.rate_limit.audit_store")
    def test_decorator_blocks_when_over_limit(self, mock_audit, mock_metric, mock_consume, mock_limit_flag):
        """Test that decorator blocks calls when over limit"""
        mock_limit_flag.return_value = 1
        mock_consume.return_value = False  # Over limit
        
        @rate_limited_llm(endpoint_name="test_endpoint")
        def test_func(prompt: str, model: str):
            return "success"
        
        with self.assertRaises(RateLimitExceeded) as context:
            test_func("test prompt", "test-model")
        
        self.assertIn("rate limit exceeded", str(context.exception).lower())
        self.assertEqual(context.exception.endpoint, "test_endpoint")
        self.assertEqual(context.exception.model, "test-model")
        
        # Verify metric incremented
        mock_metric.labels.assert_called_once_with(endpoint="test_endpoint", model="test-model")
        mock_metric.labels.return_value.inc.assert_called_once()
        
        # Verify audit log
        self.assertTrue(mock_audit.record.called)

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    @patch("graph_rag.rate_limit.consume_token_with_limit")
    def test_decorator_extracts_model_from_kwargs(self, mock_consume, mock_limit_flag):
        """Test that decorator extracts model from kwargs"""
        mock_limit_flag.return_value = 10
        mock_consume.return_value = True
        
        @rate_limited_llm(endpoint_name="test_endpoint")
        def test_func(prompt: str, model: str = None):
            return "success"
        
        test_func("test prompt", model="kwarg-model")
        
        mock_consume.assert_called_once_with("test_endpoint", "kwarg-model", 10)

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    @patch("graph_rag.rate_limit.consume_token_with_limit")
    @patch("graph_rag.rate_limit.get_config_value")
    def test_decorator_uses_default_model_when_not_provided(self, mock_config, mock_consume, mock_limit_flag):
        """Test that decorator uses default model when not provided"""
        mock_limit_flag.return_value = 10
        mock_consume.return_value = True
        mock_config.return_value = "default-model"
        
        @rate_limited_llm(endpoint_name="test_endpoint")
        def test_func(prompt: str):
            return "success"
        
        test_func("test prompt")
        
        mock_consume.assert_called_once_with("test_endpoint", "default-model", 10)

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    @patch("graph_rag.rate_limit.consume_token_with_limit")
    def test_decorator_uses_function_name_as_default_endpoint(self, mock_consume, mock_limit_flag):
        """Test that decorator uses function name as default endpoint"""
        mock_limit_flag.return_value = 10
        mock_consume.return_value = True
        
        @rate_limited_llm()
        def my_custom_function(prompt: str, model: str):
            return "success"
        
        my_custom_function("test prompt", "test-model")
        
        mock_consume.assert_called_once_with("my_custom_function", "test-model", 10)


class TestGetCurrentRateLimitUsage(unittest.TestCase):
    """Tests for get_current_rate_limit_usage"""

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    def test_usage_when_disabled(self, mock_limit_flag):
        """Test usage info when rate limiting is disabled"""
        mock_limit_flag.return_value = 0
        
        usage = get_current_rate_limit_usage("test_endpoint", "test_model")
        
        self.assertEqual(usage["remaining"], float('inf'))
        self.assertEqual(usage["limit"], 0)
        self.assertTrue(usage["disabled"])

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    @patch("graph_rag.rate_limit._get_redis_client")
    def test_usage_with_tokens_remaining(self, mock_redis_getter, mock_limit_flag):
        """Test usage info with tokens remaining"""
        mock_limit_flag.return_value = 10
        mock_redis = MagicMock()
        mock_redis.get.return_value = "7"  # 7 tokens remaining
        mock_redis_getter.return_value = mock_redis
        
        usage = get_current_rate_limit_usage("test_endpoint", "test_model")
        
        self.assertEqual(usage["remaining"], 7)
        self.assertEqual(usage["limit"], 10)
        self.assertFalse(usage["disabled"])
        self.assertIsNotNone(usage["reset_at"])

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    @patch("graph_rag.rate_limit._get_redis_client")
    def test_usage_when_no_tokens_consumed_yet(self, mock_redis_getter, mock_limit_flag):
        """Test usage info when no tokens consumed yet (key doesn't exist)"""
        mock_limit_flag.return_value = 10
        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # Key doesn't exist yet
        mock_redis_getter.return_value = mock_redis
        
        usage = get_current_rate_limit_usage("test_endpoint", "test_model")
        
        self.assertEqual(usage["remaining"], 10)
        self.assertEqual(usage["limit"], 10)


class TestRateLimitIntegration(unittest.TestCase):
    """Integration tests simulating actual usage"""

    @patch("graph_rag.rate_limit.LLM_RATE_LIMIT_PER_MIN")
    @patch("graph_rag.rate_limit._get_redis_client")
    def test_two_calls_with_limit_one_blocks_second(self, mock_redis_getter, mock_limit_flag):
        """Test that with limit=1, second call in a minute is blocked"""
        mock_limit_flag.return_value = 1
        
        # Mock Redis to simulate token bucket
        call_count = [0]
        def mock_eval(script, num_keys, key, tokens, limit, timestamp):
            call_count[0] += 1
            if call_count[0] == 1:
                return 1  # First call succeeds
            else:
                return 0  # Second call blocked
        
        mock_redis = MagicMock()
        mock_redis.eval.side_effect = mock_eval
        mock_redis_getter.return_value = mock_redis
        
        @rate_limited_llm(endpoint_name="test_endpoint")
        def test_func(prompt: str, model: str):
            return "success"
        
        # First call should succeed
        result1 = test_func("prompt1", "test-model")
        self.assertEqual(result1, "success")
        
        # Second call should be blocked
        with self.assertRaises(RateLimitExceeded):
            test_func("prompt2", "test-model")


if __name__ == '__main__':
    unittest.main()

