#!/usr/bin/env python3
"""
Unit tests for hardened response_formatter.py (RF-001)
Tests deterministic serialization, config-driven limits, and audit logging.
"""
import sys
import os
import json
import tempfile

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DEV_MODE for testing
os.environ["DEV_MODE"] = "true"

from graph_rag.response_formatter import (
    _serialize_value,
    rows_to_table, 
    build_graph_payload, 
    build_summary_prompt,
    get_formatting_stats
)

# Mock object for testing Neo4j-like serialization
class MockNeo4jNode:
    def __init__(self, node_id, labels):
        self.id = node_id
        self.labels = labels

class MockNeo4jRel:
    def __init__(self, rel_id):
        self.id = rel_id

def test_rows_to_table_deterministic_keys_and_serialization():
    """Test deterministic key ordering and safe serialization."""
    print("Testing deterministic rows_to_table with serialization...")
    
    # Test with different key orders and Neo4j-like objects
    rows = [
        {"name": "John", "age": 30, "node": MockNeo4jNode("node1", ["Person"])},
        {"city": "NYC", "name": "Jane", "rel": MockNeo4jRel("rel1")},
        {"name": "Bob", "age": 25, "city": "LA"}
    ]
    
    result = rows_to_table(rows)
    
    # Check deterministic key ordering (should be based on first occurrence)
    expected_keys = ["name", "age", "node", "city", "rel"]
    actual_keys = list(result[0].keys())
    
    print(f"   Expected key order: {expected_keys}")
    print(f"   Actual key order: {actual_keys}")
    print(f"   Keys match: {actual_keys == expected_keys}")
    
    # Check serialization of Neo4j-like objects
    first_row = result[0]
    print(f"   Node serialized: {first_row['node']}")
    print(f"   Node is string: {isinstance(first_row['node'], str)}")
    
    # Check all rows have same keys
    all_same_keys = all(set(row.keys()) == set(expected_keys) for row in result)
    print(f"   All rows have same keys: {all_same_keys}")
    
    # Check non-dict items are skipped (test with audit logging)
    mixed_rows = [{"name": "John"}, "invalid", {"name": "Jane"}]
    result_mixed = rows_to_table(mixed_rows)
    print(f"   Mixed input: {len(mixed_rows)} items")
    print(f"   Result: {len(result_mixed)} rows")
    print(f"   Non-dict filtered: {len(result_mixed) == 2}")
    
    if actual_keys == expected_keys and all_same_keys and len(result_mixed) == 2:
        print("   Status: PASS - Deterministic serialization working")
        return True
    else:
        print("   Status: FAIL - Serialization issues")
        return False

def test_build_summary_prompt_uses_json_and_truncates():
    """Test JSON serialization and truncation with audit logging."""
    print("Testing build_summary_prompt with JSON and truncation...")
    
    # Create large dataset to trigger truncation
    large_rows = [{"company": f"Company{i}", "id": f"id{i}"} for i in range(15)]
    large_snippets = {f"node{i}": f"Text content for node {i} with extra long content that should be truncated" for i in range(8)}
    
    question = "List all companies"
    
    # Capture audit log before
    audit_file = "audit_log.jsonl"
    initial_audit_size = 0
    if os.path.exists(audit_file):
        with open(audit_file, 'r') as f:
            initial_audit_size = len(f.readlines())
    
    prompt = build_summary_prompt(question, large_rows, large_snippets)
    
    # Check audit log after
    final_audit_size = 0
    truncation_audits = []
    if os.path.exists(audit_file):
        with open(audit_file, 'r') as f:
            lines = f.readlines()
            final_audit_size = len(lines)
            # Check for truncation audit entries
            for line in lines[initial_audit_size:]:
                try:
                    audit_entry = json.loads(line.strip())
                    if audit_entry.get("event") == "prompt_truncated":
                        truncation_audits.append(audit_entry)
                except:
                    pass
    
    print(f"   Prompt length: {len(prompt)} characters")
    print(f"   Contains question: {'List all companies' in prompt}")
    
    # Check JSON serialization
    if "Data:" in prompt:
        data_section = prompt.split("Data:")[1]
        if "Additional Context:" in data_section:
            data_section = data_section.split("Additional Context:")[0]
        elif "Canonical IDs" in data_section:
            data_section = data_section.split("Canonical IDs")[0]
        elif "Please provide" in data_section:
            data_section = data_section.split("Please provide")[0]
        
        data_section = data_section.strip()
        
        # Find the JSON array in the data section
        json_start = data_section.find('[')
        json_end = data_section.rfind(']') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_data = data_section[json_start:json_end]
            try:
                parsed_data = json.loads(json_data)
                print(f"   JSON parsing successful: {isinstance(parsed_data, list)}")
                print(f"   Data rows in prompt: {len(parsed_data)}")
                print(f"   Data truncated correctly: {len(parsed_data) <= 10}")
            except json.JSONDecodeError as e:
                print(f"   JSON parsing failed: {e}")
                print(f"   JSON data: {json_data[:100]}...")
                return False
        else:
            print("   No JSON array found in data section")
            return False
    else:
        print("   No Data: section found in prompt")
        return False
    
    # Check snippets truncation
    if "Additional Context:" in prompt:
        context_section = prompt.split("Additional Context:")[1].split("Canonical IDs")[0].strip()
        snippet_count = context_section.count("node")
        print(f"   Snippets in prompt: {snippet_count}")
        print(f"   Snippets truncated correctly: {snippet_count <= 5}")
    
    # Check audit logging
    print(f"   Audit entries added: {final_audit_size - initial_audit_size}")
    print(f"   Truncation audits: {len(truncation_audits)}")
    
    if len(truncation_audits) > 0 and len(parsed_data) <= 10:
        print("   Status: PASS - JSON serialization and truncation working")
        return True
    else:
        print("   Status: FAIL - Truncation or JSON issues")
        return False

def test_build_graph_payload_filters_sensitive_fields_from_config():
    """Test configurable sensitive field filtering."""
    print("Testing configurable sensitive field filtering...")
    
    # Test with default sensitive fields
    rows_default = [
        {"id": "node1", "labels": ["Person"], "name": "John", "embedding": [1, 2, 3], "password": "secret123"},
        {"id": "node2", "labels": ["Company"], "name": "Apple", "secret": "confidential", "public": "visible"}
    ]
    
    result_default = build_graph_payload(rows_default)
    
    # Check that sensitive fields are filtered
    node1_props = result_default["nodes"][0].get("properties", {})
    print(f"   Node1 properties: {list(node1_props.keys())}")
    print(f"   Embedding filtered: {'embedding' not in node1_props}")
    print(f"   Password filtered: {'password' not in node1_props}")
    
    node2_props = result_default["nodes"][1].get("properties", {})
    print(f"   Node2 properties: {list(node2_props.keys())}")
    print(f"   Secret filtered: {'secret' not in node2_props}")
    print(f"   Public kept: {'public' in node2_props}")
    
    # Test that the function uses config values (check stats)
    stats = get_formatting_stats()
    sensitive_fields = stats.get("sensitive_fields", [])
    print(f"   Config sensitive fields: {sensitive_fields}")
    print(f"   Has expected fields: {'embedding' in sensitive_fields and 'password' in sensitive_fields}")
    
    if (node1_props.get("embedding") is None and 
        node1_props.get("password") is None and
        node2_props.get("secret") is None and
        node2_props.get("public") == "visible" and
        'embedding' in sensitive_fields and 'password' in sensitive_fields):
        print("   Status: PASS - Configurable sensitive field filtering working")
        return True
    else:
        print("   Status: FAIL - Sensitive field filtering issues")
        return False

def test_config_driven_limits():
    """Test that configuration values are properly used."""
    print("Testing config-driven limits...")
    
    stats = get_formatting_stats()
    print(f"   Stats: {stats}")
    
    # Check that all expected config keys are present
    expected_keys = [
        "max_table_rows_in_prompt",
        "max_snippets_in_prompt", 
        "max_canonical_ids_in_prompt",
        "max_snippet_length",
        "max_prompt_length",
        "sensitive_fields"
    ]
    
    has_all_keys = all(key in stats for key in expected_keys)
    print(f"   Has all config keys: {has_all_keys}")
    
    # Check that values are reasonable
    reasonable_values = (
        stats["max_table_rows_in_prompt"] > 0 and
        stats["max_snippets_in_prompt"] > 0 and
        stats["max_canonical_ids_in_prompt"] > 0 and
        stats["max_snippet_length"] > 0 and
        stats["max_prompt_length"] > 0 and
        isinstance(stats["sensitive_fields"], list)
    )
    print(f"   Values are reasonable: {reasonable_values}")
    
    if has_all_keys and reasonable_values:
        print("   Status: PASS - Config-driven limits working")
        return True
    else:
        print("   Status: FAIL - Config issues")
        return False

def test_serialize_value_edge_cases():
    """Test _serialize_value with various edge cases."""
    print("Testing _serialize_value edge cases...")
    
    # Test primitives
    assert _serialize_value(None) is None
    assert _serialize_value("string") == "string"
    assert _serialize_value(42) == 42
    assert _serialize_value(3.14) == 3.14
    assert _serialize_value(True) is True
    
    # Test collections
    assert _serialize_value([1, 2, 3]) == [1, 2, 3]
    assert _serialize_value({"key": "value"}) == {"key": "value"}
    
    # Test Neo4j-like objects
    mock_node = MockNeo4jNode("node123", ["Person", "Employee"])
    serialized_node = _serialize_value(mock_node)
    print(f"   Mock node serialized: {serialized_node}")
    print(f"   Is string: {isinstance(serialized_node, str)}")
    
    # Test nested structures
    nested = {"node": mock_node, "list": [1, mock_node, "text"]}
    serialized_nested = _serialize_value(nested)
    print(f"   Nested structure serialized: {serialized_nested}")
    
    # Test unknown object fallback
    class UnknownObject:
        def __str__(self):
            return "unknown_object"
    
    unknown = UnknownObject()
    serialized_unknown = _serialize_value(unknown)
    print(f"   Unknown object serialized: {serialized_unknown}")
    print(f"   Is string: {isinstance(serialized_unknown, str)}")
    
    if (isinstance(serialized_node, str) and 
        isinstance(serialized_nested, dict) and
        isinstance(serialized_unknown, str)):
        print("   Status: PASS - Serialization edge cases handled")
        return True
    else:
        print("   Status: FAIL - Serialization edge case issues")
        return False

def main():
    """Run all hardening tests."""
    print("Running hardened response_formatter tests (RF-001)...")
    
    tests = [
        test_rows_to_table_deterministic_keys_and_serialization,
        test_build_summary_prompt_uses_json_and_truncates,
        test_build_graph_payload_filters_sensitive_fields_from_config,
        test_config_driven_limits,
        test_serialize_value_edge_cases
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"   Test {test.__name__} failed with exception: {e}")
        print()
    
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All hardening tests PASSED!")
        return True
    else:
        print("Some hardening tests FAILED!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
