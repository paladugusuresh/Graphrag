# tests/test_label_sanitization.py
import pytest
from graph_rag.cypher_generator import CypherGenerator

@pytest.fixture
def cypher_generator_instance():
    return CypherGenerator()

def test_invalid_label_rejected(cypher_generator_instance):
    assert not cypher_generator_instance._validate_label("User`) DETACH DELETE (n)") 

def test_known_label_allowed(cypher_generator_instance):
    # This depends on allow_list.json — if empty, skip
    labels = cypher_generator_instance.allow_list.get("node_labels", [])
    if not labels:
        pytest.skip("allow_list.json not present")
    assert labels[0] in cypher_generator_instance.allow_list["node_labels"]
    assert cypher_generator_instance._validate_label(labels[0])
