import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json

# Add the parent directory to the path so we can import graph_rag modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_rag.semantic_mapper import (
    SynonymMapper,
    _normalize_term,
    _pluralize,
    _singularize,
    _exact_match_fallback,
    _plural_fallback,
    _fuzzy_fallback
)


class TestNormalizationHelpers(unittest.TestCase):
    """Tests for normalization and string manipulation helpers"""

    def test_normalize_term(self):
        """Test term normalization"""
        self.assertEqual(_normalize_term("  Student  "), "student")
        self.assertEqual(_normalize_term("TEACHER"), "teacher")
        self.assertEqual(_normalize_term("Case  Worker"), "case worker")
        self.assertEqual(_normalize_term(""), "")

    def test_pluralize(self):
        """Test simple pluralization"""
        self.assertEqual(_pluralize("student"), "students")
        self.assertEqual(_pluralize("pupil"), "pupils")
        self.assertEqual(_pluralize("class"), "class")  # Already ends with 's', no change
        self.assertEqual(_pluralize("entry"), "entries")  # y -> ies
        self.assertEqual(_pluralize("classes"), "classes")  # Already plural

    def test_singularize(self):
        """Test simple singularization"""
        self.assertEqual(_singularize("students"), "student")
        self.assertEqual(_singularize("classes"), "classe")
        self.assertEqual(_singularize("entries"), "entry")
        self.assertEqual(_singularize("class"), "class")  # No change if doesn't end in s

    def test_exact_match_fallback(self):
        """Test exact match fallback"""
        schema_terms = ["Student", "Teacher", "Course"]
        
        # Exact match (case-insensitive)
        self.assertEqual(_exact_match_fallback("student", schema_terms), "Student")
        self.assertEqual(_exact_match_fallback("TEACHER", schema_terms), "Teacher")
        
        # No match
        self.assertIsNone(_exact_match_fallback("professor", schema_terms))

    def test_plural_fallback(self):
        """Test plural/singular fallback"""
        schema_terms = ["Student", "Teacher", "Course"]
        
        # Plural to singular
        self.assertEqual(_plural_fallback("students", schema_terms), "Student")
        self.assertEqual(_plural_fallback("teachers", schema_terms), "Teacher")
        
        # Singular to plural (if schema has plural)
        schema_with_plurals = ["Students", "Teachers"]
        self.assertEqual(_plural_fallback("student", schema_with_plurals), "Students")
        
        # No match
        self.assertIsNone(_plural_fallback("professors", schema_terms))

    def test_fuzzy_fallback(self):
        """Test fuzzy string matching fallback"""
        schema_terms = ["Student", "Teacher", "Course"]
        
        # Similar terms
        match = _fuzzy_fallback("studnt", schema_terms, threshold=0.6)
        self.assertIsNotNone(match)
        
        # No match (too dissimilar)
        self.assertIsNone(_fuzzy_fallback("xyz", schema_terms, threshold=0.7))


class TestSynonymMapper(unittest.TestCase):
    """Tests for SynonymMapper class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_allow_list = {
            "node_labels": ["Student", "Teacher", "Course", "Grade"],
            "relationship_types": ["ENROLLED_IN", "TEACHES", "HAS_GRADE"],
            "properties": {
                "Student": ["name", "age", "gpa"],
                "Teacher": ["name", "subject"]
            }
        }

    @patch("graph_rag.semantic_mapper.get_config_value")
    def test_mapper_initialization(self, mock_config):
        """Test SynonymMapper initialization with config"""
        mock_config.side_effect = lambda key, default: {
            'mapper.min_similarity': 0.65,
            'mapper.top_k': 3,
            'mapper.fuzzy_threshold': 0.75
        }.get(key, default)
        
        mapper = SynonymMapper()
        
        self.assertEqual(mapper.min_similarity, 0.65)
        self.assertEqual(mapper.top_k, 3)
        self.assertEqual(mapper.fuzzy_threshold, 0.75)

    @patch("graph_rag.semantic_mapper.get_config_value")
    @patch("graph_rag.semantic_mapper.map_term")
    @patch("graph_rag.schema_manager.get_allow_list")
    @patch("graph_rag.semantic_mapper.audit_store")
    def test_map_label_embedding_match(self, mock_audit, mock_get_allow_list, mock_map_term, mock_config):
        """Test label mapping with high-confidence embedding match"""
        mock_config.return_value = 0.62  # min_similarity
        mock_get_allow_list.return_value = self.mock_allow_list
        
        # Mock embedding match
        mock_map_term.return_value = [{
            'term': 'Student',
            'canonical_id': 'Student',
            'type': 'label',
            'score': 0.85
        }]
        
        mapper = SynonymMapper()
        result = mapper.map_label("pupil")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['canonical_id'], 'Student')
        self.assertEqual(result['score'], 0.85)
        self.assertEqual(result['method'], 'embedding')
        
        # Verify audit was recorded
        self.assertTrue(mock_audit.record.called)
        audit_call = mock_audit.record.call_args[0][0]
        self.assertEqual(audit_call['event'], 'synonym_mapper_label')
        self.assertEqual(audit_call['candidate'], 'pupil')
        self.assertEqual(audit_call['mapped_term'], 'Student')

    @patch("graph_rag.semantic_mapper.get_config_value")
    @patch("graph_rag.semantic_mapper.map_term")
    @patch("graph_rag.schema_manager.get_allow_list")
    @patch("graph_rag.semantic_mapper.audit_store")
    def test_map_label_below_threshold_uses_fallback(self, mock_audit, mock_get_allow_list, mock_map_term, mock_config):
        """Test label mapping falls back to exact match when embedding score is low"""
        mock_config.return_value = 0.62  # min_similarity
        mock_get_allow_list.return_value = self.mock_allow_list
        
        # Mock low-confidence embedding match
        mock_map_term.return_value = [{
            'term': 'Student',
            'canonical_id': 'Student',
            'type': 'label',
            'score': 0.45  # Below threshold
        }]
        
        mapper = SynonymMapper()
        result = mapper.map_label("Student")  # Exact match available
        
        self.assertIsNotNone(result)
        self.assertEqual(result['canonical_id'], 'Student')
        self.assertEqual(result['score'], 1.0)  # Exact match score
        self.assertEqual(result['method'], 'exact')

    @patch("graph_rag.semantic_mapper.get_config_value")
    @patch("graph_rag.semantic_mapper.map_term")
    @patch("graph_rag.schema_manager.get_allow_list")
    @patch("graph_rag.semantic_mapper.audit_store")
    def test_map_label_plural_fallback(self, mock_audit, mock_get_allow_list, mock_map_term, mock_config):
        """Test label mapping uses plural fallback"""
        mock_config.return_value = 0.62
        mock_get_allow_list.return_value = self.mock_allow_list
        
        # No good embedding match
        mock_map_term.return_value = []
        
        mapper = SynonymMapper()
        result = mapper.map_label("students")  # Plural form
        
        self.assertIsNotNone(result)
        self.assertEqual(result['canonical_id'], 'Student')
        self.assertEqual(result['method'], 'plural')

    @patch("graph_rag.semantic_mapper.get_config_value")
    @patch("graph_rag.semantic_mapper.map_term")
    @patch("graph_rag.schema_manager.get_allow_list")
    def test_map_label_no_match(self, mock_get_allow_list, mock_map_term, mock_config):
        """Test label mapping returns None when no match found"""
        mock_config.return_value = 0.62
        mock_get_allow_list.return_value = self.mock_allow_list
        
        # No embedding match
        mock_map_term.return_value = []
        
        mapper = SynonymMapper()
        result = mapper.map_label("unknown_entity")
        
        self.assertIsNone(result)

    @patch("graph_rag.semantic_mapper.get_config_value")
    @patch("graph_rag.semantic_mapper.map_term")
    @patch("graph_rag.schema_manager.get_allow_list")
    @patch("graph_rag.semantic_mapper.audit_store")
    def test_map_relationship(self, mock_audit, mock_get_allow_list, mock_map_term, mock_config):
        """Test relationship mapping"""
        mock_config.return_value = 0.62
        mock_get_allow_list.return_value = self.mock_allow_list
        
        # Mock embedding match for relationship
        mock_map_term.return_value = [{
            'term': 'ENROLLED_IN',
            'canonical_id': 'ENROLLED_IN',
            'type': 'relationship',
            'score': 0.88
        }]
        
        mapper = SynonymMapper()
        result = mapper.map_relationship("enrolled in")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['canonical_id'], 'ENROLLED_IN')
        self.assertEqual(result['type'], 'relationship')
        self.assertEqual(result['method'], 'embedding')
        
        # Verify audit
        self.assertTrue(mock_audit.record.called)
        audit_call = mock_audit.record.call_args[0][0]
        self.assertEqual(audit_call['event'], 'synonym_mapper_relationship')

    @patch("graph_rag.semantic_mapper.get_config_value")
    @patch("graph_rag.semantic_mapper.map_term")
    @patch("graph_rag.schema_manager.get_allow_list")
    @patch("graph_rag.semantic_mapper.audit_store")
    def test_map_property(self, mock_audit, mock_get_allow_list, mock_map_term, mock_config):
        """Test property mapping"""
        mock_config.return_value = 0.62
        mock_get_allow_list.return_value = self.mock_allow_list
        
        # Mock embedding match for property
        mock_map_term.return_value = [{
            'term': 'gpa',
            'canonical_id': 'gpa',
            'type': 'property',
            'score': 0.92
        }]
        
        mapper = SynonymMapper()
        result = mapper.map_property("grade point average")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['canonical_id'], 'gpa')
        self.assertEqual(result['type'], 'property')
        
        # Verify audit
        self.assertTrue(mock_audit.record.called)
        audit_call = mock_audit.record.call_args[0][0]
        self.assertEqual(audit_call['event'], 'synonym_mapper_property')

    @patch("graph_rag.semantic_mapper.get_config_value")
    @patch("graph_rag.semantic_mapper.map_term")
    @patch("graph_rag.schema_manager.get_allow_list")
    def test_map_label_filters_by_type(self, mock_get_allow_list, mock_map_term, mock_config):
        """Test that label mapping only accepts label-type results"""
        mock_config.return_value = 0.62
        mock_get_allow_list.return_value = self.mock_allow_list
        
        # Mock match is relationship, not label
        mock_map_term.return_value = [{
            'term': 'ENROLLED_IN',
            'canonical_id': 'ENROLLED_IN',
            'type': 'relationship',  # Wrong type!
            'score': 0.95
        }]
        
        mapper = SynonymMapper()
        result = mapper.map_label("enrolled in")
        
        # Should fall back since the embedding match is wrong type
        self.assertIsNone(result)

    @patch("graph_rag.semantic_mapper.get_config_value")
    @patch("graph_rag.semantic_mapper.map_term")
    @patch("graph_rag.schema_manager.get_allow_list")
    def test_high_threshold_filtering(self, mock_get_allow_list, mock_map_term, mock_config):
        """Test that low scores are filtered out even if they match type"""
        # Set high threshold
        mock_config.side_effect = lambda key, default: 0.80 if key == 'mapper.min_similarity' else default
        mock_get_allow_list.return_value = self.mock_allow_list
        
        # Score below threshold
        mock_map_term.return_value = [{
            'term': 'Student',
            'canonical_id': 'Student',
            'type': 'label',
            'score': 0.65  # Below 0.80 threshold
        }]
        
        mapper = SynonymMapper()
        result = mapper.map_label("learner")
        
        # Should not use embedding match, falls back to fuzzy/exact
        # Since "learner" won't exact/plural/fuzzy match "Student", returns None
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()

