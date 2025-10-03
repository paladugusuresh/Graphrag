# graph_rag/conversation_store.py
import json
import os
from typing import List, Dict

class ConversationStore:
    def __init__(self, storage_dir: str = "conversations"):
        self.storage_dir = storage_dir
        self.conversations: Dict[str, List[Dict]] = {}
        self._ensure_storage_dir_exists()

    def _ensure_storage_dir_exists(self):
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_conversation_file(self, conversation_id: str) -> str:
        return os.path.join(self.storage_dir, f"conv_{conversation_id}.jsonl")

    def init(self):
        """Initializes the conversation store by loading existing conversations."""
        for filename in os.listdir(self.storage_dir):
            if filename.startswith("conv_") and filename.endswith(".jsonl"):
                conversation_id = filename[len("conv_"):-len(".jsonl")]
                self.conversations[conversation_id] = self._load_conversation(conversation_id)

    def _load_conversation(self, conversation_id: str) -> List[Dict]:
        filepath = self._get_conversation_file(conversation_id)
        messages = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    messages.append(json.loads(line))
        return messages

    def add_message(self, conversation_id: str, message: Dict):
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append(message)
        self._persist_message(conversation_id, message)

    def _persist_message(self, conversation_id: str, message: Dict):
        filepath = self._get_conversation_file(conversation_id)
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message) + '\n')

    def get_history(self, conversation_id: str) -> List[Dict]:
        return self.conversations.get(conversation_id, [])

conversation_store = ConversationStore()
