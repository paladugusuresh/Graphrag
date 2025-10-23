import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json
from fastapi.testclient import TestClient
from pydantic import BaseModel
from prometheus_client import REGISTRY
from opentelemetry.trace import SpanContext, TraceFlags

# Dummy Pydantic models for mocking LLM structured output
class QueryPlan(BaseModel):
    intent: str
    anchor: str | None = None

class ExtractedEntities(BaseModel):
    names: list[str]

class RAGChain:
    def invoke(self, question: str):
        return {"answer": f"Mocked answer for {question}", "trace_id": "mock_trace_id", "sources": ["mock_chunk_id"]}

class TestAPIEndpoints(unittest.TestCase):

    def setUp(self):
        # Ensure modules are reloaded for each test
        for module_name in [
            'main', 'graph_rag.rag', 'graph_rag.retriever', 'graph_rag.planner',
            'graph_rag.llm_client', 'graph_rag.cypher_generator', 'graph_rag.neo4j_client',
            'graph_rag.embeddings', 'graph_rag.ingest', 'graph_rag.audit_store',
            'graph_rag.conversation_store'
        ]:
            if module_name in sys.modules:
                del sys.modules[module_name]
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

        # Set up a temporary directory for conversations for each test
        self.test_conversations_dir = "temp_test_conversations"
        os.makedirs(self.test_conversations_dir, exist_ok=True)

        # Patch conversation_store to use the temporary directory
        self.patcher_conv_store_init = patch(
            "graph_rag.conversation_store.ConversationStore.__init__",
            autospec=True,
            return_value=None
        )
        self.mock_conv_store_init = self.patcher_conv_store_init.start()
        self.mock_conv_store_init.return_value = None # Explicitly set return_value

        self.patcher_conv_store_add = patch(
            "graph_rag.conversation_store.ConversationStore.add_message",
            autospec=True
        )
        self.mock_conv_store_add = self.patcher_conv_store_add.start()

        self.patcher_conv_store_get_history = patch(
            "graph_rag.conversation_store.ConversationStore.get_history",
            autospec=True
        )
        self.mock_conv_store_get_history = self.patcher_conv_store_get_history.start()

        self.patcher_conv_store_instance = patch(
            "graph_rag.conversation_store.conversation_store",
            MagicMock(spec=type("MockConversationStore", (object,), {
                "init": MagicMock(),
                "add_message": MagicMock(),
                "get_history": MagicMock(),
                "storage_dir": self.test_conversations_dir # Mock the storage_dir
            }))
        )
        self.mock_conv_store_instance = self.patcher_conv_store_instance.start()


        # Mock config.yaml
        self.mock_open = mock_open(read_data=json.dumps({
            "observability": {"metrics_enabled": False},
            "llm": {"model": "gemini-2.0-flash-exp", "max_tokens": 512, "rate_limit_per_minute": 60, "redis_url": "redis://localhost:6379/0"},
            "retriever": {"max_chunks": 5}
        }))
        self.mock_open_patch = patch("builtins.open", new=self.mock_open).start()

        # Mock rag_chain
        self.patcher_rag_chain = patch("main.rag_chain", autospec=True)
        self.mock_rag_chain = self.patcher_rag_chain.start()
        self.mock_rag_chain.invoke.return_value = {
            "question": "Who founded Microsoft?",
            "answer": "Bill Gates founded Microsoft [chunk1].",
            "plan": {"intent": "general_rag_query", "anchor": "Microsoft"},
            "sources": ["chunk1"],
            "citation_verification": {"cited_ids": ["chunk1"], "provided_ids": ["chunk1"], "unknown_citations": [], "verified": True, "verification_action": ""},
            "trace_id": "test_trace_id_123"
        }

        # Mock OpenTelemetry tracer and get_current_span
        self.mock_tracer = MagicMock()
        self.mock_tracer_patch = patch("main.tracer", new=self.mock_tracer).start()

        self.mock_current_span = MagicMock(context=SpanContext(trace_id=0x1234, span_id=0x5678, is_remote=False, trace_flags=TraceFlags.SAMPLED))
        self.mock_get_current_span_patch = patch("main.get_current_span", return_value=self.mock_current_span).start()

        # Import app after all mocks are set up
        from main import app
        self.client = TestClient(app)

    def tearDown(self):
        self.patcher_conv_store_init.stop()
        self.patcher_conv_store_add.stop()
        self.patcher_conv_store_get_history.stop()
        self.patcher_conv_store_instance.stop()
        self.mock_open_patch.stop()
        self.patcher_rag_chain.stop()
        self.mock_tracer_patch.stop()
        self.mock_get_current_span_patch.stop()

        # Clean up the temporary conversation directory
        if os.path.exists(self.test_conversations_dir):
            for file in os.listdir(self.test_conversations_dir):
                os.remove(os.path.join(self.test_conversations_dir, file))
            os.rmdir(self.test_conversations_dir)

    def test_post_chat_new_conversation(self):
        response = self.client.post("/api/chat", json={"question": "Test question"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("conversation_id", data)
        self.assertEqual(data["answer"], "Bill Gates founded Microsoft [chunk1].")
        self.assertEqual(data["trace_id"], "test_trace_id_123")
        self.mock_conv_store_add.assert_any_call(
            self.mock_conv_store_instance, unittest.mock.ANY, {"role": "user", "text": "Test question"}
        )
        self.mock_conv_store_add.assert_any_call(
            self.mock_conv_store_instance, unittest.mock.ANY, {"role": "assistant", "text": "Bill Gates founded Microsoft [chunk1].", "trace_id": "test_trace_id_123"}
        )

    def test_post_chat_existing_conversation(self):
        conversation_id = "test_conv_123"
        response = self.client.post("/api/chat", json={"conversation_id": conversation_id, "question": "Another question"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["conversation_id"], conversation_id)
        self.mock_conv_store_add.assert_any_call(
            self.mock_conv_store_instance, conversation_id, {"role": "user", "text": "Another question"}
        )
        self.mock_conv_store_add.assert_any_call(
            self.mock_conv_store_instance, conversation_id, {"role": "assistant", "text": "Bill Gates founded Microsoft [chunk1].", "trace_id": "test_trace_id_123"}
        )

    def test_get_chat_history_found(self):
        conversation_id = "history_conv_456"
        mock_history = [
            {"role": "user", "text": "Hi"},
            {"role": "assistant", "text": "Hello!"}
        ]
        self.mock_conv_store_get_history.return_value = mock_history

        response = self.client.get(f"/api/chat/{conversation_id}/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mock_history)
        self.mock_conv_store_get_history.assert_called_once_with(self.mock_conv_store_instance, conversation_id)

    def test_get_chat_history_not_found(self):
        conversation_id = "non_existent_conv"
        self.mock_conv_store_get_history.return_value = []

        response = self.client.get(f"/api/chat/{conversation_id}/history")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Conversation not found"})
        self.mock_conv_store_get_history.assert_called_once_with(self.mock_conv_store_instance, conversation_id)
