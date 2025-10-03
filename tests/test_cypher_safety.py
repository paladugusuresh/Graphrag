# tests/test_cypher_safety.py
import pytest
from graph_rag.cypher_generator import CYPHER_TEMPLATES, CypherGenerator

@pytest.fixture
def cypher_generator_instance():
    return CypherGenerator()

def test_template_validation_blocking(cypher_generator_instance):
    # Temporarily craft a template with an invalid label and test
    bad_template = {"schema_requirements": {"labels": ["NonExistentLabel"], "relationships": []}}
    assert not cypher_generator_instance._validate_template(bad_template)
