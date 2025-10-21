import unittest
import sys
import os
from unittest.mock import patch

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.flags import (
    GUARDRAILS_FAIL_CLOSED_DEV,
    LLM_JSON_MODE_ENABLED,
    LLM_RATE_LIMIT_PER_MIN,
    GUARDRAILS_MAX_HOPS,
    SCHEMA_BOOTSTRAP_ENABLED,
    RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED,
    get_all_flags
)


class TestFeatureFlags(unittest.TestCase):

    def setUp(self):
        """Clear environment variables before each test."""
        # Clear relevant environment variables
        env_vars_to_clear = [
            'GUARDRAILS_FAIL_CLOSED_DEV',
            'LLM_JSON_MODE_ENABLED',
            'LLM_RATE_LIMIT_PER_MIN',
            'GUARDRAILS_MAX_HOPS',
            'SCHEMA_BOOTSTRAP_ENABLED',
            'RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED'
        ]
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]

    def test_guardrails_fail_closed_dev_default(self):
        """Test that GUARDRAILS_FAIL_CLOSED_DEV defaults to False."""
        result = GUARDRAILS_FAIL_CLOSED_DEV()
        self.assertFalse(result)

    def test_guardrails_fail_closed_dev_env_true(self):
        """Test that GUARDRAILS_FAIL_CLOSED_DEV reads True from environment."""
        os.environ['GUARDRAILS_FAIL_CLOSED_DEV'] = 'true'
        result = GUARDRAILS_FAIL_CLOSED_DEV()
        self.assertTrue(result)

    def test_guardrails_fail_closed_dev_env_false(self):
        """Test that GUARDRAILS_FAIL_CLOSED_DEV reads False from environment."""
        os.environ['GUARDRAILS_FAIL_CLOSED_DEV'] = 'false'
        result = GUARDRAILS_FAIL_CLOSED_DEV()
        self.assertFalse(result)

    def test_llm_json_mode_enabled_default(self):
        """Test that LLM_JSON_MODE_ENABLED defaults to True."""
        result = LLM_JSON_MODE_ENABLED()
        self.assertTrue(result)

    def test_llm_json_mode_enabled_env_false(self):
        """Test that LLM_JSON_MODE_ENABLED reads False from environment."""
        os.environ['LLM_JSON_MODE_ENABLED'] = 'false'
        result = LLM_JSON_MODE_ENABLED()
        self.assertFalse(result)

    def test_llm_rate_limit_per_min_default(self):
        """Test that LLM_RATE_LIMIT_PER_MIN defaults to 0."""
        result = LLM_RATE_LIMIT_PER_MIN()
        self.assertEqual(result, 0)

    def test_llm_rate_limit_per_min_env_value(self):
        """Test that LLM_RATE_LIMIT_PER_MIN reads integer from environment."""
        os.environ['LLM_RATE_LIMIT_PER_MIN'] = '120'
        result = LLM_RATE_LIMIT_PER_MIN()
        self.assertEqual(result, 120)

    def test_llm_rate_limit_per_min_env_invalid(self):
        """Test that LLM_RATE_LIMIT_PER_MIN falls back to default on invalid env value."""
        os.environ['LLM_RATE_LIMIT_PER_MIN'] = 'invalid'
        result = LLM_RATE_LIMIT_PER_MIN()
        self.assertEqual(result, 0)

    def test_guardrails_max_hops_default(self):
        """Test that GUARDRAILS_MAX_HOPS defaults to 2."""
        result = GUARDRAILS_MAX_HOPS()
        self.assertEqual(result, 2)

    def test_guardrails_max_hops_env_value(self):
        """Test that GUARDRAILS_MAX_HOPS reads integer from environment."""
        os.environ['GUARDRAILS_MAX_HOPS'] = '5'
        result = GUARDRAILS_MAX_HOPS()
        self.assertEqual(result, 5)

    def test_schema_bootstrap_enabled_default(self):
        """Test that SCHEMA_BOOTSTRAP_ENABLED defaults to True."""
        result = SCHEMA_BOOTSTRAP_ENABLED()
        self.assertTrue(result)

    def test_schema_bootstrap_enabled_env_false(self):
        """Test that SCHEMA_BOOTSTRAP_ENABLED reads False from environment."""
        os.environ['SCHEMA_BOOTSTRAP_ENABLED'] = 'false'
        result = SCHEMA_BOOTSTRAP_ENABLED()
        self.assertFalse(result)

    def test_retrieval_chunk_embeddings_enabled_default(self):
        """Test that RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED defaults to False."""
        result = RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED()
        self.assertFalse(result)

    def test_retrieval_chunk_embeddings_enabled_env_true(self):
        """Test that RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED reads True from environment."""
        os.environ['RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED'] = 'true'
        result = RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED()
        self.assertTrue(result)

    def test_get_all_flags(self):
        """Test that get_all_flags returns all flags with their current values."""
        flags = get_all_flags()
        
        # Check that all expected flags are present
        expected_flags = [
            'GUARDRAILS_FAIL_CLOSED_DEV',
            'LLM_JSON_MODE_ENABLED',
            'LLM_RATE_LIMIT_PER_MIN',
            'GUARDRAILS_MAX_HOPS',
            'SCHEMA_BOOTSTRAP_ENABLED',
            'RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED'
        ]
        
        for flag in expected_flags:
            self.assertIn(flag, flags)
        
        # Check default values
        self.assertFalse(flags['GUARDRAILS_FAIL_CLOSED_DEV'])
        self.assertTrue(flags['LLM_JSON_MODE_ENABLED'])
        self.assertEqual(flags['LLM_RATE_LIMIT_PER_MIN'], 0)
        self.assertEqual(flags['GUARDRAILS_MAX_HOPS'], 2)
        self.assertTrue(flags['SCHEMA_BOOTSTRAP_ENABLED'])
        self.assertFalse(flags['RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED'])

    def test_get_all_flags_with_env_overrides(self):
        """Test that get_all_flags reflects environment variable overrides."""
        # Set some environment variables
        os.environ['GUARDRAILS_FAIL_CLOSED_DEV'] = 'true'
        os.environ['LLM_RATE_LIMIT_PER_MIN'] = '100'
        os.environ['RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED'] = 'true'
        
        flags = get_all_flags()
        
        # Check that environment overrides are reflected
        self.assertTrue(flags['GUARDRAILS_FAIL_CLOSED_DEV'])
        self.assertEqual(flags['LLM_RATE_LIMIT_PER_MIN'], 100)
        self.assertTrue(flags['RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED'])
        
        # Check that other flags still have defaults
        self.assertTrue(flags['LLM_JSON_MODE_ENABLED'])
        self.assertEqual(flags['GUARDRAILS_MAX_HOPS'], 2)
        self.assertTrue(flags['SCHEMA_BOOTSTRAP_ENABLED'])

    def test_boolean_env_variations(self):
        """Test that boolean flags handle various environment value formats."""
        test_cases = [
            ('true', True),
            ('TRUE', True),
            ('1', True),
            ('yes', True),
            ('YES', True),
            ('on', True),
            ('ON', True),
            ('false', False),
            ('FALSE', False),
            ('0', False),
            ('no', False),
            ('NO', False),
            ('off', False),
            ('OFF', False),
        ]
        
        for env_value, expected in test_cases:
            with self.subTest(env_value=env_value):
                os.environ['GUARDRAILS_FAIL_CLOSED_DEV'] = env_value
                result = GUARDRAILS_FAIL_CLOSED_DEV()
                self.assertEqual(result, expected)

    @patch('graph_rag.flags.get_config_value')
    def test_config_file_override(self, mock_get_config_value):
        """Test that flags can be overridden via config file."""
        # Mock config values
        mock_get_config_value.side_effect = lambda key, default=None: {
            'flags.guardrails_fail_closed_dev': True,
            'flags.llm_rate_limit_per_min': 200,
            'flags.retrieval_chunk_embeddings_enabled': True,
        }.get(key, default)
        
        # Test that config values override defaults
        self.assertTrue(GUARDRAILS_FAIL_CLOSED_DEV())
        self.assertEqual(LLM_RATE_LIMIT_PER_MIN(), 200)
        self.assertTrue(RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED())
        
        # Test that environment variables still take precedence
        os.environ['GUARDRAILS_FAIL_CLOSED_DEV'] = 'false'
        self.assertFalse(GUARDRAILS_FAIL_CLOSED_DEV())


if __name__ == '__main__':
    unittest.main()
