# tests/test_api_format_types.py
import unittest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app


class TestAPIFormatTypes(unittest.TestCase):
    """Test API format_type parameter functionality."""
    
    def setUp(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    @patch('main.guardrail_check')
    @patch('main.rag_chain')
    def test_chat_endpoint_text_format(self, mock_rag_chain, mock_guardrail):
        """Test /api/chat with format_type='text'."""
        # Mock guardrail to allow the request
        mock_guardrail.return_value = True
        
        # Mock RAG chain response
        mock_response = {
            "question": "What are the goals for Isabella Thomas?",
            "answer": "Isabella Thomas has 3 goals: Math improvement, Reading comprehension, Social skills",
            "cypher": "MATCH (s:Student {fullName: 'Isabella Thomas'})-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal) RETURN g.title AS goal",
            "params": {"student": "Isabella Thomas"},
            "rows": [
                {"goal": "Math improvement"},
                {"goal": "Reading comprehension"},
                {"goal": "Social skills"}
            ],
            "row_count": 3,
            "snippets": [],
            "citations": [],
            "table": [],
            "plan": {"intent": "goals_for_student", "anchor_entity": "Isabella Thomas"},
            "citation_verification": {"verified": True},
            "trace_id": "test-trace-123",
            "audit_id": "test-audit-456"
        }
        
        mock_rag_chain.invoke.return_value = mock_response
        
        # Test request with format_type='text'
        response = self.client.post("/api/chat", json={
            "question": "What are the goals for Isabella Thomas?",
            "format_type": "text"
        })
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Should include trace_id and audit_id
        data = response.json()
        self.assertIn("trace_id", data)
        self.assertIn("audit_id", data)
        self.assertEqual(data["trace_id"], "test-trace-123")
        self.assertEqual(data["audit_id"], "test-audit-456")
        
        # Should call RAG chain with format_type
        mock_rag_chain.invoke.assert_called_once_with("What are the goals for Isabella Thomas?", "text")
    
    @patch('main.guardrail_check')
    @patch('main.rag_chain')
    def test_chat_endpoint_table_format(self, mock_rag_chain, mock_guardrail):
        """Test /api/chat with format_type='table'."""
        # Mock guardrail to allow the request
        mock_guardrail.return_value = True
        
        # Mock RAG chain response with formatted output
        mock_response = {
            "question": "What are the goals for Isabella Thomas?",
            "answer": "Isabella Thomas has 3 goals",
            "cypher": "MATCH (s:Student {fullName: 'Isabella Thomas'})-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal) RETURN g.title AS goal",
            "params": {"student": "Isabella Thomas"},
            "rows": [
                {"goal": "Math improvement"},
                {"goal": "Reading comprehension"},
                {"goal": "Social skills"}
            ],
            "row_count": 3,
            "snippets": [],
            "citations": [],
            "table": [],
            "plan": {"intent": "goals_for_student", "anchor_entity": "Isabella Thomas"},
            "citation_verification": {"verified": True},
            "trace_id": "test-trace-123",
            "audit_id": "test-audit-456",
            "formatted": {
                "table": {
                    "columns": ["goal"],
                    "data": [
                        ["Math improvement"],
                        ["Reading comprehension"],
                        ["Social skills"]
                    ]
                }
            },
            "verification_status": "passed"
        }
        
        mock_rag_chain.invoke.return_value = mock_response
        
        # Test request with format_type='table'
        response = self.client.post("/api/chat", json={
            "question": "What are the goals for Isabella Thomas?",
            "format_type": "table"
        })
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Should include trace_id and audit_id
        data = response.json()
        self.assertIn("trace_id", data)
        self.assertIn("audit_id", data)
        
        # Should call RAG chain with format_type
        mock_rag_chain.invoke.assert_called_once_with("What are the goals for Isabella Thomas?", "table")
    
    @patch('main.guardrail_check')
    @patch('main.rag_chain')
    def test_chat_endpoint_graph_format(self, mock_rag_chain, mock_guardrail):
        """Test /api/chat with format_type='graph'."""
        # Mock guardrail to allow the request
        mock_guardrail.return_value = True
        
        # Mock RAG chain response with graph formatting
        mock_response = {
            "question": "What are the goals for Isabella Thomas?",
            "answer": "Isabella Thomas has 3 goals",
            "cypher": "MATCH (s:Student {fullName: 'Isabella Thomas'})-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal) RETURN g.title AS goal",
            "params": {"student": "Isabella Thomas"},
            "rows": [
                {"goal": "Math improvement", "primary_id": "goal_1"},
                {"goal": "Reading comprehension", "primary_id": "goal_2"},
                {"goal": "Social skills", "primary_id": "goal_3"}
            ],
            "row_count": 3,
            "snippets": [],
            "citations": [],
            "table": [],
            "plan": {"intent": "goals_for_student", "anchor_entity": "Isabella Thomas"},
            "citation_verification": {"verified": True},
            "trace_id": "test-trace-123",
            "audit_id": "test-audit-456",
            "formatted": {
                "graph": {
                    "nodes": [
                        {"id": "goal_1", "label": "Goal", "properties": {"goal": "Math improvement"}},
                        {"id": "goal_2", "label": "Goal", "properties": {"goal": "Reading comprehension"}},
                        {"id": "goal_3", "label": "Goal", "properties": {"goal": "Social skills"}}
                    ],
                    "edges": []
                }
            },
            "verification_status": "passed"
        }
        
        mock_rag_chain.invoke.return_value = mock_response
        
        # Test request with format_type='graph'
        response = self.client.post("/api/chat", json={
            "question": "What are the goals for Isabella Thomas?",
            "format_type": "graph"
        })
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Should include trace_id and audit_id
        data = response.json()
        self.assertIn("trace_id", data)
        self.assertIn("audit_id", data)
        
        # Should call RAG chain with format_type
        mock_rag_chain.invoke.assert_called_once_with("What are the goals for Isabella Thomas?", "graph")
    
    @patch('main.guardrail_check')
    @patch('main.rag_chain')
    def test_chat_endpoint_no_format_type(self, mock_rag_chain, mock_guardrail):
        """Test /api/chat without format_type (backward compatibility)."""
        # Mock guardrail to allow the request
        mock_guardrail.return_value = True
        
        # Mock RAG chain response
        mock_response = {
            "question": "What are the goals for Isabella Thomas?",
            "answer": "Isabella Thomas has 3 goals",
            "cypher": "MATCH (s:Student {fullName: 'Isabella Thomas'})-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal) RETURN g.title AS goal",
            "params": {"student": "Isabella Thomas"},
            "rows": [{"goal": "Math improvement"}],
            "row_count": 1,
            "snippets": [],
            "citations": [],
            "table": [],
            "plan": {"intent": "goals_for_student", "anchor_entity": "Isabella Thomas"},
            "citation_verification": {"verified": True},
            "trace_id": "test-trace-123",
            "audit_id": "test-audit-456"
        }
        
        mock_rag_chain.invoke.return_value = mock_response
        
        # Test request without format_type
        response = self.client.post("/api/chat", json={
            "question": "What are the goals for Isabella Thomas?"
        })
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Should include trace_id and audit_id
        data = response.json()
        self.assertIn("trace_id", data)
        self.assertIn("audit_id", data)
        
        # Should call RAG chain with None format_type
        mock_rag_chain.invoke.assert_called_once_with("What are the goals for Isabella Thomas?", None)
    
    @patch('main.guardrail_check')
    @patch('main.rag_chain')
    def test_chat_endpoint_invalid_format_type(self, mock_rag_chain, mock_guardrail):
        """Test /api/chat with invalid format_type."""
        # Mock guardrail to allow the request
        mock_guardrail.return_value = True
        
        # Mock RAG chain response
        mock_response = {
            "question": "What are the goals for Isabella Thomas?",
            "answer": "Isabella Thomas has 3 goals",
            "cypher": "MATCH (s:Student {fullName: 'Isabella Thomas'})-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal) RETURN g.title AS goal",
            "params": {"student": "Isabella Thomas"},
            "rows": [{"goal": "Math improvement"}],
            "row_count": 1,
            "snippets": [],
            "citations": [],
            "table": [],
            "plan": {"intent": "goals_for_student", "anchor_entity": "Isabella Thomas"},
            "citation_verification": {"verified": True},
            "trace_id": "test-trace-123",
            "audit_id": "test-audit-456"
        }
        
        mock_rag_chain.invoke.return_value = mock_response
        
        # Test request with invalid format_type
        response = self.client.post("/api/chat", json={
            "question": "What are the goals for Isabella Thomas?",
            "format_type": "invalid_format"
        })
        
        # Should still return 200 (invalid format_type is handled gracefully)
        self.assertEqual(response.status_code, 200)
        
        # Should include trace_id and audit_id
        data = response.json()
        self.assertIn("trace_id", data)
        self.assertIn("audit_id", data)
        
        # Should call RAG chain with invalid format_type
        mock_rag_chain.invoke.assert_called_once_with("What are the goals for Isabella Thomas?", "invalid_format")
    
    @patch('main.guardrail_check')
    @patch('main.rag_chain')
    def test_chat_endpoint_missing_trace_audit_ids(self, mock_rag_chain, mock_guardrail):
        """Test /api/chat when RAG response is missing trace_id/audit_id."""
        # Mock guardrail to allow the request
        mock_guardrail.return_value = True
        
        # Mock RAG chain response without trace_id/audit_id
        mock_response = {
            "question": "What are the goals for Isabella Thomas?",
            "answer": "Isabella Thomas has 3 goals",
            "cypher": "MATCH (s:Student {fullName: 'Isabella Thomas'})-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal) RETURN g.title AS goal",
            "params": {"student": "Isabella Thomas"},
            "rows": [{"goal": "Math improvement"}],
            "row_count": 1,
            "snippets": [],
            "citations": [],
            "table": [],
            "plan": {"intent": "goals_for_student", "anchor_entity": "Isabella Thomas"},
            "citation_verification": {"verified": True}
        }
        
        mock_rag_chain.invoke.return_value = mock_response
        
        # Test request
        response = self.client.post("/api/chat", json={
            "question": "What are the goals for Isabella Thomas?"
        })
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Should include default trace_id and audit_id
        data = response.json()
        self.assertIn("trace_id", data)
        self.assertIn("audit_id", data)
        self.assertEqual(data["trace_id"], "no-trace")
        self.assertEqual(data["audit_id"], "no-audit")


class TestFormattersIntegration(unittest.TestCase):
    """Test formatters integration with format_type parameter."""
    
    @patch('graph_rag.formatters.FORMATTERS_ENABLED')
    def test_formatters_manager_text_format(self, mock_enabled):
        """Test FormattersManager with format_type='text'."""
        mock_enabled.return_value = True
        
        from graph_rag.formatters import FormattersManager
        
        manager = FormattersManager()
        
        rows = [{"goal": "Math improvement"}, {"goal": "Reading comprehension"}]
        summary = "Student has 2 goals"
        citations = []
        available_ids = []
        
        result = manager.format_response(rows, summary, citations, available_ids, "text")
        
        # Should return verification but no formatted sections
        self.assertIsNotNone(result)
        self.assertIn("verification_status", result)
        # For text format, formatted should be empty dict
        self.assertIn("formatted", result)
        self.assertEqual(result["formatted"], {})
    
    @patch('graph_rag.formatters.FORMATTERS_ENABLED')
    def test_formatters_manager_table_format(self, mock_enabled):
        """Test FormattersManager with format_type='table'."""
        mock_enabled.return_value = True
        
        from graph_rag.formatters import FormattersManager
        
        manager = FormattersManager()
        
        rows = [{"goal": "Math improvement"}, {"goal": "Reading comprehension"}]
        summary = "Student has 2 goals"
        citations = []
        available_ids = []
        
        result = manager.format_response(rows, summary, citations, available_ids, "table")
        
        # Should return table formatting
        self.assertIsNotNone(result)
        self.assertIn("formatted", result)
        self.assertIn("table", result["formatted"])
        self.assertNotIn("graph", result["formatted"])
    
    @patch('graph_rag.formatters.FORMATTERS_ENABLED')
    def test_formatters_manager_graph_format(self, mock_enabled):
        """Test FormattersManager with format_type='graph'."""
        mock_enabled.return_value = True
        
        from graph_rag.formatters import FormattersManager
        
        manager = FormattersManager()
        
        rows = [
            {"goal": "Math improvement", "primary_id": "goal_1"},
            {"goal": "Reading comprehension", "primary_id": "goal_2"}
        ]
        summary = "Student has 2 goals"
        citations = []
        available_ids = []
        
        result = manager.format_response(rows, summary, citations, available_ids, "graph")
        
        # Should return graph formatting
        self.assertIsNotNone(result)
        self.assertIn("formatted", result)
        self.assertIn("graph", result["formatted"])
        self.assertNotIn("table", result["formatted"])
    
    @patch('graph_rag.formatters.FORMATTERS_ENABLED')
    def test_formatters_manager_default_format(self, mock_enabled):
        """Test FormattersManager with no format_type (default behavior)."""
        mock_enabled.return_value = True
        
        from graph_rag.formatters import FormattersManager
        
        manager = FormattersManager()
        
        rows = [
            {"goal": "Math improvement", "primary_id": "goal_1"},
            {"goal": "Reading comprehension", "primary_id": "goal_2"}
        ]
        summary = "Student has 2 goals"
        citations = []
        available_ids = []
        
        result = manager.format_response(rows, summary, citations, available_ids, None)
        
        # Should return both table and graph formatting
        self.assertIsNotNone(result)
        self.assertIn("formatted", result)
        self.assertIn("table", result["formatted"])
        self.assertIn("graph", result["formatted"])


if __name__ == '__main__':
    unittest.main()
