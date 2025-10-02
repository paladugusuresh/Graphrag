# tests/test_cypher_safety.py
import pytest
from graph_rag.cypher_generator import CYPHER_TEMPLATES, cypher_generator

def test_template_validation_blocking():
    # Temporarily craft a template with an invalid label and test
    bad_template = {"schema_requirements": {"labels": ["NonExistentLabel"], "relationships": []}}
    assert not cypher_generator._validate_template(bad_template)
