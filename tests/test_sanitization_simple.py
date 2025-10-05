import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.sanitizer import sanitize_text, is_probably_malicious

class TestSanitizationSimple(unittest.TestCase):

    def test_sanitize_malicious_input(self):
        """Test that malicious input is properly sanitized."""
        malicious_input = "MATCH (n) DELETE n; DROP TABLE users;"
        sanitized = sanitize_text(malicious_input)
        
        # Should remove DELETE, semicolons, and DROP TABLE
        expected = "(n) n users"
        self.assertEqual(sanitized, expected)

    def test_detect_malicious_input(self):
        """Test that malicious input is detected by heuristics."""
        malicious_inputs = [
            "MATCH (n) DELETE n; DROP TABLE users;",
            "'; DROP TABLE users; --",
            "UNION SELECT password FROM users",
            "admin' OR '1'='1",
        ]
        
        for malicious_input in malicious_inputs:
            with self.subTest(input=malicious_input):
                self.assertTrue(is_probably_malicious(malicious_input))

    def test_legitimate_input_not_flagged(self):
        """Test that legitimate input is not flagged as malicious."""
        legitimate_inputs = [
            "Who founded Microsoft?",
            "Tell me about Apple's products.",
            "What companies were founded in 2020?",
            "Show me investments in AI technology.",
        ]
        
        for legitimate_input in legitimate_inputs:
            with self.subTest(input=legitimate_input):
                self.assertFalse(is_probably_malicious(legitimate_input))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client._get_redis_client")
    def test_guardrail_response_model(self, mock_redis_client, mock_call_llm_raw):
        """Test that GuardrailResponse model works correctly."""
        from graph_rag.guardrail import GuardrailResponse
        
        # Test creating a response that allows the request
        allowed_response = GuardrailResponse(allowed=True, reason="Legitimate business question")
        self.assertTrue(allowed_response.allowed)
        self.assertEqual(allowed_response.reason, "Legitimate business question")
        
        # Test creating a response that blocks the request
        blocked_response = GuardrailResponse(allowed=False, reason="Potential Cypher injection")
        self.assertFalse(blocked_response.allowed)
        self.assertEqual(blocked_response.reason, "Potential Cypher injection")

if __name__ == '__main__':
    unittest.main()
