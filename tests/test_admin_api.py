# tests/test_admin_api.py
"""
Unit tests for Admin API endpoints.

Tests the /admin/schema/refresh endpoint functionality including:
- Successful schema refresh
- Error handling
- Component invocation verification
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_schema_refresh_triggers_all_components(monkeypatch):
    """
    Test that /admin/schema/refresh triggers all three schema components.
    
    Verifies that:
    1. ensure_schema_loaded is called with force=True
    2. upsert_schema_embeddings is called
    3. ensure_chunk_vector_index is called
    4. Response is 200 OK with success status
    """
    # Track which functions were called
    called = {"load": False, "embed": False, "index": False}
    
    # Mock the schema functions
    def mock_ensure_schema_loaded(**kwargs):
        assert kwargs.get('force') == True, "force=True should be passed"
        called["load"] = True
        return {"node_labels": ["Test"], "relationship_types": ["TEST"], "properties": {}}
    
    def mock_upsert_schema_embeddings():
        called["embed"] = True
        return {"status": "success", "nodes_created": 10}
    
    def mock_ensure_chunk_vector_index():
        called["index"] = True
        return {"status": "exists"}
    
    # Apply mocks
    monkeypatch.setattr("graph_rag.schema_manager.ensure_schema_loaded", mock_ensure_schema_loaded)
    monkeypatch.setattr("graph_rag.schema_embeddings.upsert_schema_embeddings", mock_upsert_schema_embeddings)
    monkeypatch.setattr("graph_rag.schema_manager.ensure_chunk_vector_index", mock_ensure_chunk_vector_index)
    
    # Import main app after monkeypatching
    from main import app
    client = TestClient(app)
    
    # Call the endpoint
    response = client.post("/admin/schema/refresh")
    
    # Verify response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert data["status"] == "success", f"Expected success status, got: {data}"
    assert "duration_s" in data, "Response should include duration_s"
    assert isinstance(data["duration_s"], (int, float)), "duration_s should be numeric"
    
    # Verify all components were called
    assert all(called.values()), f"Not all components were called: {called}"
    
    print("✅ All schema components were triggered successfully")


def test_schema_refresh_error_handling(monkeypatch):
    """
    Test that /admin/schema/refresh handles errors gracefully.
    
    Verifies that:
    1. Exceptions are caught and logged
    2. Response is 500 with error detail
    3. Error message is included in response
    """
    # Mock ensure_schema_loaded to raise an exception
    def mock_ensure_schema_loaded(**kwargs):
        raise RuntimeError("Database connection failed")
    
    # Mock other functions (they shouldn't be called)
    def mock_upsert_schema_embeddings():
        pytest.fail("Should not be called when ensure_schema_loaded fails")
    
    def mock_ensure_chunk_vector_index():
        pytest.fail("Should not be called when ensure_schema_loaded fails")
    
    # Apply mocks to admin_api module (where they're actually used)
    monkeypatch.setattr("graph_rag.admin_api.ensure_schema_loaded", mock_ensure_schema_loaded)
    monkeypatch.setattr("graph_rag.admin_api.upsert_schema_embeddings", mock_upsert_schema_embeddings)
    monkeypatch.setattr("graph_rag.admin_api.ensure_chunk_vector_index", mock_ensure_chunk_vector_index)
    
    # Import main app after monkeypatching
    from main import app
    client = TestClient(app)
    
    # Call the endpoint
    response = client.post("/admin/schema/refresh")
    
    # Verify error response
    assert response.status_code == 500, f"Expected 500, got {response.status_code}"
    
    data = response.json()
    assert "detail" in data, "Error response should include detail"
    assert "Database connection failed" in data["detail"], f"Error detail should mention the exception: {data}"
    
    print("✅ Error handling works correctly")


def test_schema_refresh_response_structure(monkeypatch):
    """
    Test that /admin/schema/refresh returns the expected response structure.
    
    Verifies:
    1. Response includes all required fields
    2. Field types are correct
    3. Steps completed list is present
    """
    # Mock the schema functions with simple returns
    monkeypatch.setattr("graph_rag.schema_manager.ensure_schema_loaded", 
                       lambda **kw: {"node_labels": [], "relationship_types": [], "properties": {}})
    monkeypatch.setattr("graph_rag.schema_embeddings.upsert_schema_embeddings", 
                       lambda: {"status": "success"})
    monkeypatch.setattr("graph_rag.schema_manager.ensure_chunk_vector_index", 
                       lambda: {"status": "exists"})
    
    # Import main app after monkeypatching
    from main import app
    client = TestClient(app)
    
    # Call the endpoint
    response = client.post("/admin/schema/refresh")
    
    # Verify response structure
    assert response.status_code == 200
    
    data = response.json()
    
    # Check required fields
    required_fields = ["status", "duration_s", "steps_completed"]
    for field in required_fields:
        assert field in data, f"Response missing required field: {field}"
    
    # Check field types
    assert isinstance(data["status"], str), "status should be a string"
    assert isinstance(data["duration_s"], (int, float)), "duration_s should be numeric"
    assert isinstance(data["steps_completed"], list), "steps_completed should be a list"
    
    # Check status value
    assert data["status"] == "success", f"Expected success status, got: {data['status']}"
    
    # Check steps_completed content
    expected_steps = [
        "ensure_schema_loaded",
        "upsert_schema_embeddings",
        "ensure_chunk_vector_index"
    ]
    assert data["steps_completed"] == expected_steps, f"Unexpected steps: {data['steps_completed']}"
    
    print("✅ Response structure is correct")


def test_schema_status_endpoint(monkeypatch):
    """
    Test that /admin/schema/status returns current schema information.
    
    Verifies:
    1. Endpoint is accessible
    2. Response includes schema status information
    3. Status information is accurate
    """
    # Mock the schema functions
    def mock_get_schema_fingerprint():
        return "abc123def456" + "0" * 50  # 64-char fingerprint
    
    def mock_get_allow_list():
        return {
            "node_labels": ["Student", "Staff", "Goal"],
            "relationship_types": ["HAS_PLAN", "HAS_GOAL"],
            "properties": {"Student": ["name"], "Goal": ["title"]}
        }
    
    # Apply mocks
    monkeypatch.setattr("graph_rag.schema_manager.get_schema_fingerprint", mock_get_schema_fingerprint)
    monkeypatch.setattr("graph_rag.schema_manager.get_allow_list", mock_get_allow_list)
    
    # Import main app after monkeypatching
    from main import app
    client = TestClient(app)
    
    # Call the endpoint
    response = client.get("/admin/schema/status")
    
    # Verify response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    
    # Check required fields
    assert "status" in data, "Response missing status field"
    assert "fingerprint" in data, "Response missing fingerprint field"
    assert "labels_count" in data, "Response missing labels_count field"
    assert "relationships_count" in data, "Response missing relationships_count field"
    assert "properties_count" in data, "Response missing properties_count field"
    
    # Check values
    assert data["status"] == "loaded", f"Expected loaded status, got: {data['status']}"
    # Fingerprint should be truncated to 16 chars + "..."
    assert data["fingerprint"].endswith("..."), f"Fingerprint should end with '...': {data['fingerprint']}"
    assert len(data["fingerprint"]) == 19, f"Fingerprint should be 16 chars + '...', got: {data['fingerprint']}"
    assert data["labels_count"] == 3, f"Expected 3 labels, got: {data['labels_count']}"
    assert data["relationships_count"] == 2, f"Expected 2 relationships, got: {data['relationships_count']}"
    assert data["properties_count"] == 2, f"Expected 2 properties, got: {data['properties_count']}"
    
    print("✅ Schema status endpoint works correctly")


def test_admin_router_integration():
    """
    Test that admin router is properly integrated into the FastAPI app.
    
    Verifies:
    1. Admin routes are accessible
    2. Routes are under /admin prefix
    3. Routes are tagged as "admin"
    """
    from main import app
    
    # Get all routes
    routes = [route for route in app.routes if hasattr(route, 'path')]
    
    # Find admin routes
    admin_routes = [route for route in routes if route.path.startswith('/admin')]
    
    # Verify admin routes exist
    assert len(admin_routes) > 0, "No admin routes found"
    
    # Check for specific routes
    admin_paths = [route.path for route in admin_routes]
    assert "/admin/schema/refresh" in admin_paths, "Schema refresh route not found"
    assert "/admin/schema/status" in admin_paths, "Schema status route not found"
    
    print(f"✅ Found {len(admin_routes)} admin routes: {admin_paths}")


if __name__ == '__main__':
    print("Admin API Unit Tests")
    print("=" * 70)
    
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
    
    print("\n" + "=" * 70)
    print("Admin API Test Summary")
    print("=" * 70)
    print("These tests verify:")
    print("   - Schema refresh endpoint triggers all components")
    print("   - Error handling returns proper 500 responses")
    print("   - Response structure matches specification")
    print("   - Schema status endpoint provides current information")
    print("   - Admin router is properly integrated")
    print("\nRun these tests to verify admin API correctness!")
