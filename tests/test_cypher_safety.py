# tests/test_cypher_safety.py
"""
Test Cypher safety validation - Updated for LLM-driven approach (Task 21)
Tests the standalone validation functions instead of template-based validation.
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DEV_MODE for testing
os.environ["DEV_MODE"] = "true"

from graph_rag.cypher_generator import validate_label, validate_relationship_type, load_allow_list

@pytest.fixture
def sample_allow_list():
    """Provide a sample allow list for testing."""
    return {
        "node_labels": ["Student", "Goal", "InterventionPlan", "CaseWorker", "Service"],
        "relationship_types": ["HAS_GOAL", "HAS_INTERVENTION", "ASSIGNED_TO", "PROVIDES"],
        "properties": {}
    }

def test_label_validation_valid(sample_allow_list):
    """Test that valid labels pass validation."""
    
    # Mock the allow list
    with pytest.MonkeyPatch().context() as m:
        m.setattr("graph_rag.cypher_generator.load_allow_list", lambda: sample_allow_list)
        
        # Test valid labels (returned with backticks for Cypher formatting)
        assert validate_label("Student") == "`Student`"
        assert validate_label("Goal") == "`Goal`"
        assert validate_label("InterventionPlan") == "`InterventionPlan`"
        assert validate_label("CaseWorker") == "`CaseWorker`"

def test_label_validation_invalid(sample_allow_list):
    """Test that invalid labels are rejected."""
    
    # Mock the allow list
    with pytest.MonkeyPatch().context() as m:
        m.setattr("graph_rag.cypher_generator.load_allow_list", lambda: sample_allow_list)
        
        # Test invalid labels (fallback to Entity with backticks)
        assert validate_label("NonExistentLabel") == "`Entity`"  # Fallback to Entity
        assert validate_label("InvalidLabel") == "`Entity`"
        assert validate_label("") == "`Entity`"

def test_relationship_validation_valid(sample_allow_list):
    """Test that valid relationship types pass validation."""
    
    # Mock the allow list
    with pytest.MonkeyPatch().context() as m:
        m.setattr("graph_rag.cypher_generator.load_allow_list", lambda: sample_allow_list)
        
        # Test valid relationship types (returned with backticks for Cypher formatting)
        assert validate_relationship_type("HAS_GOAL") == "`HAS_GOAL`"
        assert validate_relationship_type("HAS_INTERVENTION") == "`HAS_INTERVENTION`"
        assert validate_relationship_type("ASSIGNED_TO") == "`ASSIGNED_TO`"
        assert validate_relationship_type("PROVIDES") == "`PROVIDES`"

def test_relationship_validation_invalid(sample_allow_list):
    """Test that invalid relationship types are rejected."""
    
    # Mock the allow list
    with pytest.MonkeyPatch().context() as m:
        m.setattr("graph_rag.cypher_generator.load_allow_list", lambda: sample_allow_list)
        
        # Test invalid relationship types (fallback to RELATED with backticks)
        assert validate_relationship_type("INVALID_REL") == "`RELATED`"  # Fallback
        assert validate_relationship_type("NonExistentRel") == "`RELATED`"
        assert validate_relationship_type("") == "`RELATED`"

def test_allow_list_loading():
    """Test that allow list can be loaded."""
    
    # This will use the actual allow_list.json if it exists, or mock in DEV_MODE
    allow_list = load_allow_list()
    
    assert isinstance(allow_list, dict)
    assert "node_labels" in allow_list
    assert "relationship_types" in allow_list
    assert isinstance(allow_list["node_labels"], list)
    assert isinstance(allow_list["relationship_types"], list)

def test_validation_case_sensitivity(sample_allow_list):
    """Test that validation is case-sensitive."""
    
    # Mock the allow list
    with pytest.MonkeyPatch().context() as m:
        m.setattr("graph_rag.cypher_generator.load_allow_list", lambda: sample_allow_list)
        
        # Test case sensitivity
        assert validate_label("student") == "`Entity`"  # lowercase should fail
        assert validate_label("Student") == "`Student`"  # correct case should pass
        
        assert validate_relationship_type("has_goal") == "`RELATED`"  # lowercase should fail
        assert validate_relationship_type("HAS_GOAL") == "`HAS_GOAL`"  # correct case should pass

def test_validation_with_empty_allow_list():
    """Test validation behavior with empty allow list."""
    
    empty_allow_list = {
        "node_labels": [],
        "relationship_types": [],
        "properties": {}
    }
    
    # Mock the allow list
    with pytest.MonkeyPatch().context() as m:
        m.setattr("graph_rag.cypher_generator.load_allow_list", lambda: empty_allow_list)
        
        # All labels should fallback to Entity with backticks
        assert validate_label("AnyLabel") == "`Entity`"
        assert validate_label("Student") == "`Entity`"
        
        # All relationships should fallback to RELATED with backticks
        assert validate_relationship_type("AnyRel") == "`RELATED`"
        assert validate_relationship_type("HAS_GOAL") == "`RELATED`"
