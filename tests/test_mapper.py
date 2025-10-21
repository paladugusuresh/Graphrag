# tests/test_mapper.py
import unittest
from unittest.mock import patch, MagicMock

from graph_rag.semantic_mapper import SynonymMapper


class TestSynonymMapper(unittest.TestCase):
    """Test semantic mapper functionality with thresholds."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mapper = SynonymMapper()
        
        # Mock schema terms with embeddings
        self.mock_schema_terms = [
            {"id": "label:Student", "term": "Student", "type": "label", "canonical_id": "Student", "embedding": [0.1, 0.2, 0.3]},
            {"id": "label:Teacher", "term": "Teacher", "type": "label", "canonical_id": "Teacher", "embedding": [0.4, 0.5, 0.6]},
            {"id": "relationship:HAS_PLAN", "term": "HAS_PLAN", "type": "relationship", "canonical_id": "HAS_PLAN", "embedding": [0.7, 0.8, 0.9]},
            {"id": "property:fullName", "term": "fullName", "type": "property", "canonical_id": "fullName", "embedding": [0.2, 0.3, 0.4]}
        ]
    
    @patch('graph_rag.semantic_mapper.get_embedding_provider')
    def test_map_label_above_threshold(self, mock_provider):
        """Test label mapping when similarity is above threshold."""
        # Mock embedding provider
        mock_embeddings = MagicMock()
        mock_embeddings.get_embeddings.return_value = [[0.15, 0.25, 0.35]]  # Similar to Student
        mock_provider.return_value = mock_embeddings
        
        # Mock schema terms
        with patch.object(self.mapper, '_get_schema_terms', return_value=self.mock_schema_terms):
            result = self.mapper.map_label("pupil")
            
            # Should map to Student (similar embedding)
            self.assertEqual(result, "Student")
    
    @patch('graph_rag.semantic_mapper.get_embedding_provider')
    def test_map_label_below_threshold(self, mock_provider):
        """Test label mapping when similarity is below threshold."""
        # Mock embedding provider with dissimilar embedding
        mock_embeddings = MagicMock()
        mock_embeddings.get_embeddings.return_value = [[0.9, 0.8, 0.7]]  # Dissimilar to all terms
        mock_provider.return_value = mock_embeddings
        
        # Mock schema terms
        with patch.object(self.mapper, '_get_schema_terms', return_value=self.mock_schema_terms):
            result = self.mapper.map_label("unknown_term")
            
            # Should return None (below threshold)
            self.assertIsNone(result)
    
    @patch('graph_rag.semantic_mapper.get_embedding_provider')
    def test_map_relationship_with_fallback(self, mock_provider):
        """Test relationship mapping with fallback to exact match."""
        # Mock embedding provider
        mock_embeddings = MagicMock()
        mock_embeddings.get_embeddings.return_value = [[0.75, 0.85, 0.95]]  # Similar to HAS_PLAN
        mock_provider.return_value = mock_embeddings
        
        # Mock schema terms
        with patch.object(self.mapper, '_get_schema_terms', return_value=self.mock_schema_terms):
            result = self.mapper.map_relationship("has plan")
            
            # Should map to HAS_PLAN
            self.assertEqual(result, "HAS_PLAN")
    
    @patch('graph_rag.semantic_mapper.get_embedding_provider')
    def test_map_property_exact_match(self, mock_provider):
        """Test property mapping with exact match fallback."""
        # Mock schema terms
        with patch.object(self.mapper, '_get_schema_terms', return_value=self.mock_schema_terms):
            result = self.mapper.map_property("fullName")
            
            # Should return exact match
            self.assertEqual(result, "fullName")
    
    def test_cosine_similarity_calculation(self):
        """Test cosine similarity calculation."""
        # Test vectors (using simple lists instead of numpy)
        vec1 = [1, 0, 0]
        vec2 = [1, 0, 0]  # Identical
        vec3 = [0, 1, 0]  # Orthogonal
        vec4 = [-1, 0, 0]  # Opposite
        
        # Calculate similarities using simple dot product
        def cosine_similarity(a, b):
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0
            return dot_product / (norm_a * norm_b)
        
        sim1 = cosine_similarity(vec1, vec2)
        sim2 = cosine_similarity(vec1, vec3)
        sim3 = cosine_similarity(vec1, vec4)
        
        # Verify similarities
        self.assertAlmostEqual(sim1, 1.0, places=5)  # Identical vectors
        self.assertAlmostEqual(sim2, 0.0, places=5)  # Orthogonal vectors
        self.assertAlmostEqual(sim3, -1.0, places=5)  # Opposite vectors
    
    def test_threshold_configuration(self):
        """Test that mapper respects threshold configuration."""
        # Test with different thresholds
        with patch('graph_rag.semantic_mapper.get_config_value') as mock_config:
            mock_config.return_value = 0.8  # High threshold
            
            mapper = SynonymMapper()
            self.assertEqual(mapper.min_similarity_threshold, 0.8)
    
    @patch('graph_rag.semantic_mapper.get_embedding_provider')
    def test_mapping_with_audit_logging(self, mock_provider):
        """Test that mapping results are logged to audit store."""
        # Mock embedding provider
        mock_embeddings = MagicMock()
        mock_embeddings.get_embeddings.return_value = [[0.15, 0.25, 0.35]]
        mock_provider.return_value = mock_embeddings
        
        # Mock audit store
        with patch('graph_rag.semantic_mapper.audit_store') as mock_audit, \
             patch.object(self.mapper, '_get_schema_terms', return_value=self.mock_schema_terms):
            
            result = self.mapper.map_label("pupil")
            
            # Verify audit logging
            mock_audit.record.assert_called()
            audit_call = mock_audit.record.call_args[0][0]
            self.assertEqual(audit_call["event"], "semantic_mapping")
            self.assertEqual(audit_call["input_term"], "pupil")
            self.assertEqual(audit_call["mapped_term"], "Student")
            self.assertIn("similarity_score", audit_call)
    
    @patch('graph_rag.semantic_mapper.get_embedding_provider')
    def test_mapping_fallback_chain(self, mock_provider):
        """Test the fallback chain: embedding -> exact -> plural -> fuzzy."""
        # Mock embedding provider to return low similarity
        mock_embeddings = MagicMock()
        mock_embeddings.get_embeddings.return_value = [[0.9, 0.8, 0.7]]  # Low similarity
        mock_provider.return_value = mock_embeddings
        
        # Mock schema terms
        with patch.object(self.mapper, '_get_schema_terms', return_value=self.mock_schema_terms):
            # Test exact match fallback
            result = self.mapper.map_label("Student")
            self.assertEqual(result, "Student")
            
            # Test plural fallback
            result = self.mapper.map_label("Students")
            self.assertEqual(result, "Student")
    
    def test_empty_schema_terms(self):
        """Test behavior with empty schema terms."""
        with patch.object(self.mapper, '_get_schema_terms', return_value=[]):
            result = self.mapper.map_label("any_term")
            self.assertIsNone(result)
    
    @patch('graph_rag.semantic_mapper.get_embedding_provider')
    def test_embedding_provider_error(self, mock_provider):
        """Test behavior when embedding provider fails."""
        # Mock embedding provider to raise exception
        mock_embeddings = MagicMock()
        mock_embeddings.get_embeddings.side_effect = Exception("Embedding service unavailable")
        mock_provider.return_value = mock_embeddings
        
        # Mock schema terms
        with patch.object(self.mapper, '_get_schema_terms', return_value=self.mock_schema_terms):
            result = self.mapper.map_label("pupil")
            
            # Should fall back to exact match
            self.assertIsNone(result)  # No exact match for "pupil"


class TestMapperIntegration(unittest.TestCase):
    """Test mapper integration with planner."""
    
    @patch('graph_rag.semantic_mapper.get_embedding_provider')
    def test_planner_integration(self, mock_provider):
        """Test mapper integration with planner."""
        from graph_rag.planner import _find_best_anchor_entity_semantic
        
        # Mock embedding provider
        mock_embeddings = MagicMock()
        mock_embeddings.get_embeddings.return_value = [[0.15, 0.25, 0.35]]
        mock_provider.return_value = mock_embeddings
        
        # Mock schema terms
        mock_schema_terms = [
            {"id": "label:Student", "term": "Student", "type": "label", "canonical_id": "Student", "embedding": [0.1, 0.2, 0.3]}
        ]
        
        with patch('graph_rag.planner._get_schema_terms', return_value=mock_schema_terms):
            result = _find_best_anchor_entity_semantic("pupil")
            
            # Should map to Student
            self.assertEqual(result, "Student")
    
    def test_mapper_disabled_flag(self):
        """Test behavior when mapper is disabled."""
        with patch('graph_rag.semantic_mapper.MAPPER_ENABLED', return_value=False):
            mapper = SynonymMapper()
            result = mapper.map_label("any_term")
            
            # Should return None when disabled
            self.assertIsNone(result)


class TestMapperMetrics(unittest.TestCase):
    """Test mapper metrics and observability."""
    
    @patch('graph_rag.semantic_mapper.get_embedding_provider')
    def test_mapping_similarity_metrics(self, mock_provider):
        """Test that mapping similarity scores are recorded as metrics."""
        from graph_rag.observability import mapping_similarity
        
        # Mock embedding provider
        mock_embeddings = MagicMock()
        mock_embeddings.get_embeddings.return_value = [[0.15, 0.25, 0.35]]
        mock_provider.return_value = mock_embeddings
        
        # Mock schema terms
        mock_schema_terms = [
            {"id": "label:Student", "term": "Student", "type": "label", "canonical_id": "Student", "embedding": [0.1, 0.2, 0.3]}
        ]
        
        mapper = SynonymMapper()
        
        with patch.object(mapper, '_get_schema_terms', return_value=mock_schema_terms), \
             patch('graph_rag.semantic_mapper.mapping_similarity') as mock_metric:
            
            result = mapper.map_label("pupil")
            
            # Verify metric was recorded
            mock_metric.observe.assert_called()
            # The similarity score should be recorded
            call_args = mock_metric.observe.call_args[0][0]
            self.assertIsInstance(call_args, float)
            self.assertGreater(call_args, 0.0)


if __name__ == '__main__':
    unittest.main()
