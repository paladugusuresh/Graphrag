# tests/test_domain_metrics.py
"""
Test domain-specific metrics and spans for pipeline stages.
"""
import unittest
from unittest.mock import patch, MagicMock
import time

from graph_rag.observability import (
    planner_latency_seconds,
    mapping_similarity,
    executor_latency_seconds,
    augmentation_size,
    guardrail_blocks_total,
    llm_rate_limited_total,
    create_pipeline_span,
    add_span_attributes
)


class TestDomainMetrics(unittest.TestCase):
    """Test domain-specific metrics functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Note: Prometheus metrics don't have a clear() method in this version
        # Tests will work with accumulated values
        pass
    
    def test_planner_latency_histogram(self):
        """Test planner latency histogram recording."""
        # Test histogram recording
        with planner_latency_seconds.time():
            time.sleep(0.001)  # Small delay to ensure measurable time
        
        # Check that histogram recorded a value
        samples = planner_latency_seconds.collect()[0].samples
        self.assertGreater(len(samples), 0)
        
        # Check that the recorded value is reasonable
        total_samples = sum(sample.value for sample in samples)
        self.assertGreater(total_samples, 0)
    
    def test_mapping_similarity_histogram(self):
        """Test mapping similarity histogram recording."""
        # Get initial state
        initial_samples = mapping_similarity.collect()[0].samples
        initial_total = sum(sample.value for sample in initial_samples)
        
        # Test various similarity scores
        test_scores = [0.1, 0.5, 0.8, 0.95]
        
        for score in test_scores:
            mapping_similarity.observe(score)
        
        # Check that histogram recorded values
        samples = mapping_similarity.collect()[0].samples
        self.assertGreater(len(samples), 0)
        
        # Check that we have samples in different buckets
        bucket_counts = sum(sample.value for sample in samples)
        self.assertGreaterEqual(bucket_counts, initial_total + len(test_scores))
    
    def test_executor_latency_histogram(self):
        """Test executor latency histogram recording."""
        with executor_latency_seconds.time():
            time.sleep(0.001)  # Small delay
        
        samples = executor_latency_seconds.collect()[0].samples
        self.assertGreater(len(samples), 0)
        
        total_samples = sum(sample.value for sample in samples)
        self.assertGreater(total_samples, 0)
    
    def test_augmentation_size_histogram(self):
        """Test augmentation size histogram recording."""
        # Get initial state
        initial_samples = augmentation_size.collect()[0].samples
        initial_total = sum(sample.value for sample in initial_samples)
        
        # Test various augmentation sizes
        test_sizes = [1, 5, 10, 50, 100]
        
        for size in test_sizes:
            augmentation_size.observe(size)
        
        samples = augmentation_size.collect()[0].samples
        self.assertGreater(len(samples), 0)
        
        bucket_counts = sum(sample.value for sample in samples)
        self.assertGreaterEqual(bucket_counts, initial_total + len(test_sizes))
    
    def test_guardrail_blocks_counter(self):
        """Test guardrail blocks counter with labels."""
        # Get initial state
        initial_samples = guardrail_blocks_total.collect()[0].samples
        initial_count = len(initial_samples)
        
        # Test different block reasons
        reasons = ["prompt_injection", "malicious_query", "llm_classification_error"]
        
        for reason in reasons:
            guardrail_blocks_total.labels(reason=reason).inc()
        
        # Check that counter recorded values
        samples = guardrail_blocks_total.collect()[0].samples
        self.assertGreaterEqual(len(samples), initial_count + len(reasons))
        
        # Check that each reason has at least one count
        reason_labels = [sample.labels['reason'] for sample in samples]
        for reason in reasons:
            self.assertIn(reason, reason_labels)
    
    def test_llm_rate_limited_counter(self):
        """Test LLM rate limited counter."""
        # Get initial state
        initial_samples = llm_rate_limited_total.collect()[0].samples
        initial_value = initial_samples[0].value if initial_samples else 0
        
        # Increment counter multiple times
        for _ in range(3):
            llm_rate_limited_total.inc()
        
        samples = llm_rate_limited_total.collect()[0].samples
        self.assertGreaterEqual(len(samples), 1)
        self.assertGreaterEqual(samples[0].value, initial_value + 3)
    
    def test_create_pipeline_span(self):
        """Test pipeline span creation with attributes."""
        with patch('graph_rag.observability.tracer') as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
            
            with create_pipeline_span("test.operation", test_attr="test_value"):
                pass
            
            # Verify span was created with attributes
            mock_tracer.start_as_current_span.assert_called_once_with(
                "test.operation", 
                attributes={"test_attr": "test_value"}
            )
    
    def test_add_span_attributes(self):
        """Test adding attributes to existing span."""
        mock_span = MagicMock()
        
        add_span_attributes(mock_span, 
                           attr1="value1", 
                           attr2=42, 
                           attr3=True)
        
        # Verify attributes were set
        self.assertEqual(mock_span.set_attribute.call_count, 3)
        
        # Check specific calls
        calls = mock_span.set_attribute.call_args_list
        expected_calls = [
            (("attr1", "value1"),),
            (("attr2", 42),),
            (("attr3", True),)
        ]
        
        for call in calls:
            self.assertIn(call, expected_calls)
    
    def test_metrics_integration(self):
        """Test metrics integration across pipeline stages."""
        # Get initial states
        initial_planner = sum(sample.value for sample in planner_latency_seconds.collect()[0].samples)
        initial_mapping = sum(sample.value for sample in mapping_similarity.collect()[0].samples)
        initial_executor = sum(sample.value for sample in executor_latency_seconds.collect()[0].samples)
        initial_augmentation = sum(sample.value for sample in augmentation_size.collect()[0].samples)
        initial_guardrail = len(guardrail_blocks_total.collect()[0].samples)
        
        # Simulate a complete pipeline run
        with planner_latency_seconds.time():
            time.sleep(0.001)
        
        mapping_similarity.observe(0.75)
        
        with executor_latency_seconds.time():
            time.sleep(0.001)
        
        augmentation_size.observe(25)
        
        guardrail_blocks_total.labels(reason="test_block").inc()
        
        # Verify all metrics recorded values
        planner_samples = planner_latency_seconds.collect()[0].samples
        mapping_samples = mapping_similarity.collect()[0].samples
        executor_samples = executor_latency_seconds.collect()[0].samples
        augmentation_samples = augmentation_size.collect()[0].samples
        guardrail_samples = guardrail_blocks_total.collect()[0].samples
        
        self.assertGreater(len(planner_samples), 0)
        self.assertGreater(len(mapping_samples), 0)
        self.assertGreater(len(executor_samples), 0)
        self.assertGreater(len(augmentation_samples), 0)
        self.assertGreaterEqual(len(guardrail_samples), initial_guardrail + 1)
        
        # Verify increases
        self.assertGreaterEqual(sum(sample.value for sample in planner_samples), initial_planner + 1)
        self.assertGreaterEqual(sum(sample.value for sample in mapping_samples), initial_mapping + 1)
        self.assertGreaterEqual(sum(sample.value for sample in executor_samples), initial_executor + 1)
        self.assertGreaterEqual(sum(sample.value for sample in augmentation_samples), initial_augmentation + 1)


class TestPipelineSpans(unittest.TestCase):
    """Test pipeline span functionality."""
    
    @patch('graph_rag.observability.tracer')
    def test_span_hierarchy(self, mock_tracer):
        """Test nested span hierarchy."""
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        # Test nested spans
        with create_pipeline_span("parent.operation"):
            with create_pipeline_span("child.operation"):
                pass
        
        # Verify both spans were created
        self.assertEqual(mock_tracer.start_as_current_span.call_count, 2)
        
        calls = mock_tracer.start_as_current_span.call_args_list
        self.assertEqual(calls[0][0][0], "parent.operation")
        self.assertEqual(calls[1][0][0], "child.operation")
    
    @patch('graph_rag.observability.tracer')
    def test_span_attributes_preservation(self, mock_tracer):
        """Test that span attributes are preserved correctly."""
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        with create_pipeline_span("test.operation", 
                                 question="test question",
                                 intent="test_intent",
                                 result_count=5):
            add_span_attributes(mock_span,
                               additional_attr="additional_value",
                               numeric_attr=42)
        
        # Verify initial attributes
        initial_call = mock_tracer.start_as_current_span.call_args
        self.assertEqual(initial_call[1]['attributes']['question'], "test question")
        self.assertEqual(initial_call[1]['attributes']['intent'], "test_intent")
        self.assertEqual(initial_call[1]['attributes']['result_count'], 5)
        
        # Verify additional attributes
        self.assertEqual(mock_span.set_attribute.call_count, 2)
        calls = mock_span.set_attribute.call_args_list
        self.assertIn((("additional_attr", "additional_value"),), calls)
        self.assertIn((("numeric_attr", 42),), calls)


if __name__ == '__main__':
    unittest.main()
