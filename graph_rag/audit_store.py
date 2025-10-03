# graph_rag/audit_store.py

import json
import os

from graph_rag.observability import get_logger

logger = get_logger(__name__)

class AuditStore:
    def __init__(self, log_file: str = "audit_log.jsonl"):
        self.log_file = log_file
        self._ensure_log_file_exists()

    def _ensure_log_file_exists(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', encoding='utf-8') as f:
                pass # Create an empty file if it doesn't exist

    def record(self, entry: dict):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')

# Global instance for easy access, can be mocked in tests
audit_store = AuditStore()
