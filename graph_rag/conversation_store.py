# graph_rag/conversation_store.py
import json
import os
from typing import List, Dict
from datetime import datetime

def normalize_message(m: dict) -> dict:
    """
    Normalize a message to ensure it has required fields.
    
    This ensures backwards compatibility with legacy message formats
    while standardizing the structure for new messages.
    
    Args:
        m: Raw message dictionary
        
    Returns:
        Normalized message with guaranteed fields
    """
    return {
        "role": m.get("role", "user"),
        "text": m.get("text", ""),
        "trace_id": m.get("trace_id", None),
        "timestamp": m.get("timestamp", datetime.utcnow().isoformat())
    }

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
        """
        Load a conversation from disk.
        
        Messages are normalized during loading to ensure backwards compatibility
        with legacy message formats.
        
        Args:
            conversation_id: Unique identifier for the conversation
            
        Returns:
            List of normalized messages
        """
        filepath = self._get_conversation_file(conversation_id)
        messages = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    raw_message = json.loads(line)
                    # Normalize legacy messages for backwards compatibility
                    normalized = normalize_message(raw_message)
                    messages.append(normalized)
        return messages

    def add_message(self, conversation_id: str, message: Dict):
        """
        Add a message to the conversation history.
        
        Messages are normalized to ensure consistent structure before being
        stored, providing backwards compatibility with legacy formats.
        
        Args:
            conversation_id: Unique identifier for the conversation
            message: Message dictionary to add
        """
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        # Normalize message to ensure consistent structure
        normalized = normalize_message(message)
        
        self.conversations[conversation_id].append(normalized)
        self._persist_message(conversation_id, normalized)

    def _persist_message(self, conversation_id: str, message: Dict):
        filepath = self._get_conversation_file(conversation_id)
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message) + '\n')

    def get_history(self, conversation_id: str) -> List[Dict]:
        return self.conversations.get(conversation_id, [])

conversation_store = ConversationStore()
