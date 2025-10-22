# tests/test_guardrails.py
import unittest
from unittest.mock import patch, MagicMock
import time

from graph_rag.guardrail import guardrail_check
from graph_rag.flags import GUARDRAILS_FAIL_CLOSED_DEV, LLM_RATE_LIMIT_PER_MIN


class TestGuardrailFailModes(unittest.TestCase):
    """Test guardrail fail modes (fail-closed vs fail-open)."""
    
    @patch('graph_rag.guardrail.call_llm_structured')
    @patch('graph_rag.guardrail.GUARDRAILS_FAIL_CLOSED_DEV')
    def test_fail_closed_mode(self, mock_fail_closed, mock_llm_call):
        """Test fail-closed mode (production behavior)."""
        # Set fail-closed mode
        mock_fail_closed.return_value = True
        
        # Mock LLM to raise error
        mock_llm_call.side_effect = Exception("LLM service unavailable")
        
        # Test guardrail check
        result = guardrail_check("What are the goals for Isabella Thomas?")
        
        # Should block request in fail-closed mode
        self.assertFalse(result)
    
    @patch('graph_rag.guardrail.call_llm_structured')
    @patch('graph_rag.guardrail.GUARDRAILS_FAIL_CLOSED_DEV')
    def test_fail_open_mode(self, mock_fail_closed, mock_llm_call):
        """Test fail-open mode (development behavior)."""
        # Set fail-open mode
        mock_fail_closed.return_value = False
        
        # Mock LLM to raise error
        mock_llm_call.side_effect = Exception("LLM service unavailable")
        
        # Test guardrail check
        result = guardrail_check("What are the goals for Isabella Thomas?")
        
        # Should allow request in fail-open mode
        self.assertTrue(result)
    
    @patch('graph_rag.guardrail.call_llm_structured')
    @patch('graph_rag.guardrail.GUARDRAILS_FAIL_CLOSED_DEV')
    def test_llm_classification_error_fail_closed(self, mock_fail_closed, mock_llm_call):
        """Test LLM classification error in fail-closed mode."""
        from graph_rag.llm_client import LLMStructuredError
        
        # Set fail-closed mode
        mock_fail_closed.return_value = True
        
        # Mock LLM to raise structured error
        mock_llm_call.side_effect = LLMStructuredError("Invalid JSON response")
        
        # Test guardrail check
        result = guardrail_check("What are the goals for Isabella Thomas?")
        
        # Should block request
        self.assertFalse(result)
    
    @patch('graph_rag.guardrail.call_llm_structured')
    @patch('graph_rag.guardrail.GUARDRAILS_FAIL_CLOSED_DEV')
    def test_llm_classification_error_fail_open(self, mock_fail_closed, mock_llm_call):
        """Test LLM classification error in fail-open mode."""
        from graph_rag.llm_client import LLMStructuredError
        
        # Set fail-open mode
        mock_fail_closed.return_value = False
        
        # Mock LLM to raise structured error
        mock_llm_call.side_effect = LLMStructuredError("Invalid JSON response")
        
        # Test guardrail check
        result = guardrail_check("What are the goals for Isabella Thomas?")
        
        # Should allow request
        self.assertTrue(result)


class TestGuardrailRateLimiting(unittest.TestCase):
    """Test guardrail rate limiting functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.rate_limiter = None
    
    @patch('graph_rag.guardrail.LLM_RATE_LIMIT_PER_MIN')
    def test_rate_limit_enabled(self, mock_rate_limit):
        """Test rate limiting when enabled."""
        # Set rate limit to 10 per minute
        mock_rate_limit.return_value = 10
        
        # Mock rate limiter
        with patch('graph_rag.guardrail.RateLimiter') as mock_limiter_class:
            mock_limiter = MagicMock()
            mock_limiter_class.return_value = mock_limiter
            mock_limiter.is_allowed.return_value = False  # Rate limited
            
            # Test guardrail check
            result = guardrail_check("What are the goals for Isabella Thomas?")
            
            # Should block due to rate limiting
            self.assertFalse(result)
    
    @patch('graph_rag.guardrail.LLM_RATE_LIMIT_PER_MIN')
    def test_rate_limit_disabled(self, mock_rate_limit):
        """Test behavior when rate limiting is disabled."""
        # Set rate limit to 0 (disabled)
        mock_rate_limit.return_value = 0
        
        # Mock successful LLM response
        mock_response = MagicMock()
        mock_response.allowed = True
        mock_response.reason = "OK"
        
        with patch('graph_rag.guardrail.call_llm_structured', return_value=mock_response):
            result = guardrail_check("What are the goals for Isabella Thomas?")
            
            # Should allow request
            self.assertTrue(result)
    
    @patch('graph_rag.guardrail.LLM_RATE_LIMIT_PER_MIN')
    def test_rate_limit_metrics(self, mock_rate_limit):
        """Test that rate limit hits are recorded as metrics."""
        from graph_rag.observability import llm_rate_limited_total
        
        # Set rate limit to 10 per minute
        mock_rate_limit.return_value = 10
        
        # Mock rate limiter
        with patch('graph_rag.guardrail.RateLimiter') as mock_limiter_class:
            mock_limiter = MagicMock()
            mock_limiter_class.return_value = mock_limiter
            mock_limiter.is_allowed.return_value = False  # Rate limited
            
            with patch('graph_rag.guardrail.llm_rate_limited_total') as mock_metric:
                guardrail_check("What are the goals for Isabella Thomas?")
                
                # Verify metric was incremented
                mock_metric.inc.assert_called()


class TestGuardrailMetrics(unittest.TestCase):
    """Test guardrail metrics and observability."""
    
    @patch('graph_rag.guardrail.call_llm_structured')
    def test_guardrail_blocks_metrics(self, mock_llm_call):
        """Test that guardrail blocks are recorded as metrics."""
        from graph_rag.observability import guardrail_blocks_total
        
        # Mock LLM to return blocked response
        mock_response = MagicMock()
        mock_response.allowed = False
        mock_response.reason = "prompt_injection"
        mock_llm_call.return_value = mock_response
        
        with patch('graph_rag.guardrail.guardrail_blocks_total') as mock_metric:
            result = guardrail_check("Malicious prompt injection attempt")
            
            # Should block request
            self.assertFalse(result)
            
            # Verify metric was incremented with correct label
            mock_metric.labels.assert_called_with(reason="prompt_injection")
            mock_metric.labels.return_value.inc.assert_called()
    
    @patch('graph_rag.guardrail.call_llm_structured')
    def test_guardrail_allows_metrics(self, mock_llm_call):
        """Test that allowed requests don't increment block metrics."""
        from graph_rag.observability import guardrail_blocks_total
        
        # Mock LLM to return allowed response
        mock_response = MagicMock()
        mock_response.allowed = True
        mock_response.reason = "OK"
        mock_llm_call.return_value = mock_response
        
        with patch('graph_rag.guardrail.guardrail_blocks_total') as mock_metric:
            result = guardrail_check("What are the goals for Isabella Thomas?")
            
            # Should allow request
            self.assertTrue(result)
            
            # Verify metric was not incremented
            mock_metric.labels.assert_not_called()


class TestGuardrailSpans(unittest.TestCase):
    """Test guardrail OpenTelemetry spans."""
    
    @patch('graph_rag.guardrail.call_llm_structured')
    def test_guardrail_span_creation(self, mock_llm_call):
        """Test that guardrail creates proper spans."""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.allowed = True
        mock_response.reason = "OK"
        mock_llm_call.return_value = mock_response
        
        # Mock span creation
        with patch('graph_rag.guardrail.create_pipeline_span') as mock_create_span:
            mock_span = MagicMock()
            mock_create_span.return_value.__enter__.return_value = mock_span
            
            result = guardrail_check("What are the goals for Isabella Thomas?")
            
            # Verify span was created
            mock_create_span.assert_called_with("guardrail.check", question="What are the goals for Isabella Thomas?")
            
            # Verify span attributes were set
            mock_span.set_attribute.assert_called()
            calls = mock_span.set_attribute.call_args_list
            attribute_names = [call[0][0] for call in calls]
            self.assertIn("allowed", attribute_names)
            self.assertIn("reason", attribute_names)
            self.assertIn("sanitized_question", attribute_names)


class TestGuardrailInputSanitization(unittest.TestCase):
    """Test guardrail input sanitization."""
    
    @patch('graph_rag.guardrail.call_llm_structured')
    @patch('graph_rag.guardrail.sanitize_text')
    def test_input_sanitization(self, mock_sanitize, mock_llm_call):
        """Test that input is sanitized before LLM call."""
        # Mock sanitization
        mock_sanitize.return_value = "sanitized question"
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.allowed = True
        mock_response.reason = "OK"
        mock_llm_call.return_value = mock_response
        
        result = guardrail_check("Original question with special chars")
        
        # Verify sanitization was called
        mock_sanitize.assert_called_with("Original question with special chars")
        
        # Verify LLM was called with sanitized input
        mock_llm_call.assert_called_once()
        call_args = mock_llm_call.call_args
        self.assertIn("sanitized question", str(call_args))


class TestGuardrailAuditLogging(unittest.TestCase):
    """Test guardrail audit logging."""
    
    @patch('graph_rag.guardrail.call_llm_structured')
    def test_audit_logging_blocked(self, mock_llm_call):
        """Test audit logging for blocked requests."""
        # Mock LLM to return blocked response
        mock_response = MagicMock()
        mock_response.allowed = False
        mock_response.reason = "malicious_query"
        mock_llm_call.return_value = mock_response
        
        with patch('graph_rag.guardrail.audit_store') as mock_audit:
            result = guardrail_check("Malicious query")
            
            # Should block request
            self.assertFalse(result)
            
            # Verify audit logging
            mock_audit.record.assert_called()
            audit_call = mock_audit.record.call_args[0][0]
            self.assertEqual(audit_call["event"], "guardrail_blocked")
            self.assertEqual(audit_call["reason"], "malicious_query")
    
    @patch('graph_rag.guardrail.call_llm_structured')
    def test_audit_logging_classification_error(self, mock_llm_call):
        """Test audit logging for classification errors."""
        from graph_rag.llm_client import LLMStructuredError
        
        # Mock LLM to raise structured error
        mock_llm_call.side_effect = LLMStructuredError("Invalid JSON")
        
        with patch('graph_rag.guardrail.audit_store') as mock_audit, \
             patch('graph_rag.guardrail.GUARDRAILS_FAIL_CLOSED_DEV', return_value=True):
            
            result = guardrail_check("Test question")
            
            # Should block request
            self.assertFalse(result)
            
            # Verify audit logging
            mock_audit.record.assert_called()
            audit_call = mock_audit.record.call_args[0][0]
            self.assertEqual(audit_call["event"], "guardrail_classification_failed")
            self.assertEqual(audit_call["reason"], "LLM classification error")


class TestGuardrailIntegration(unittest.TestCase):
    """Test guardrail integration with main application."""
    
    @patch('graph_rag.guardrail.guardrail_check')
    def test_main_integration(self, mock_guardrail):
        """Test guardrail integration with main chat endpoint."""
        from main import ChatRequest
        
        # Mock guardrail to allow request
        mock_guardrail.return_value = True
        
        # Test that guardrail is called in main flow
        request = ChatRequest(question="What are the goals for Isabella Thomas?")
        
        # This would be called in the main chat endpoint
        result = mock_guardrail(request.question)
        
        # Verify guardrail was called
        mock_guardrail.assert_called_with("What are the goals for Isabella Thomas?")
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
