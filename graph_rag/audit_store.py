# graph_rag/audit_store.py

from graph_rag.observability import get_logger

logger = get_logger(__name__)

class AuditStore:
    def record(self, **kwargs):
        logger.info("Audit record: %s", kwargs)

audit_store = AuditStore()
