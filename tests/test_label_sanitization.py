# tests/test_label_sanitization.py
import pytest
from graph_rag.cypher_generator import cypher_generator

def test_invalid_label_rejected():
    assert not cypher_generator._validate_label("User`) DETACH DELETE (n)") 

def test_known_label_allowed():
    # This depends on allow_list.json — if empty, skip
    labels = cypher_generator.allow_list.get("node_labels", [])
    if not labels:
        pytest.skip("allow_list.json not present")
    assert labels[0] in cypher_generator.allow_list["node_labels"]
    assert cypher_generator._validate_label(labels[0])
