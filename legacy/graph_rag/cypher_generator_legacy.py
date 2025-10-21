# graph_rag/cypher_generator.py - LEGACY VERSION
# This file contains the original template-based logic that was moved to legacy/
import json
import re
from graph_rag.observability import get_logger
from graph_rag.config_manager import get_config_value

logger = get_logger(__name__)

LABEL_REGEX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RELATIONSHIP_TYPE_REGEX = re.compile(r"^[A-Z_][A-Z0-9_]*$") # Cypher relationship types are typically uppercase

class CypherGenerator:
    def __init__(self, allow_list_path: str = None):
        """Initialize CypherGenerator with allow list from file"""
        path = allow_list_path or get_config_value('schema.allow_list_path', 'allow_list.json')
        try:
            with open(path, 'r') as fh:
                self.allow_list = json.load(fh)
        except FileNotFoundError:
            logger.error("allow_list.json not found; create it with schema_catalog.generate_schema_allow_list()")
            self.allow_list = {"node_labels": [], "relationship_types": [], "properties": {}}

    def _validate_label(self, label: str) -> bool:
        if not label or not LABEL_REGEX.match(label):
            return False
        return label in self.allow_list.get("node_labels", [])

    def _validate_relationship_type(self, rel_type: str) -> bool:
        if not rel_type or not RELATIONSHIP_TYPE_REGEX.match(rel_type):
            return False
        return rel_type in self.allow_list.get("relationship_types", [])

    def validate_label(self, label: str) -> str:
        if self._validate_label(label):
            return f"`{label}`"
        logger.warning(f"Invalid label '{label}' provided. Falling back to default 'Entity'.")
        return "`Entity`"

    def validate_relationship_type(self, rel_type: str) -> str:
        if self._validate_relationship_type(rel_type):
            return f"`{rel_type}`"
        logger.warning(f"Invalid relationship type '{rel_type}' provided. Falling back to default 'RELATED'.")
        return "`RELATED`"

    def _validate_template(self, template: dict) -> bool:
        reqs = template.get("schema_requirements", {})
        for label in reqs.get("labels", []):
            if not self._validate_label(label):
                logger.error(f"Template label {label} not in allow list")
                return False
        for rel in reqs.get("relationships", []):
            if not self._validate_relationship_type(rel):
                logger.error(f"Template rel {rel} not in allow list")
                return False
        return True

CYPHER_TEMPLATES = {
    "general_rag_query": {
        "cypher": """
            MATCH (e:__Entity__ {id: $anchor})
            CALL {
                WITH e
                MATCH (e)-[r]->(neighbor)
                WHERE type(r) <> 'HAS_CHUNK' AND type(r) <> 'MENTIONS'
                RETURN "(" + e.id + ")" + "-[:" + type(r) + "]->" + "(" + neighbor.id + ")" AS output
                UNION ALL
                WITH e
                MATCH (e)<-[r]-(neighbor)
                WHERE type(r) <> 'HAS_CHUNK' AND type(r) <> 'MENTIONS'
                RETURN "(" + neighbor.id + ")" + "-[:" + type(r) + "]->" + "(" + e.id + ")" AS output
            }
            RETURN output LIMIT 20
        """,
        "schema_requirements": {"labels": ["__Entity__"], "relationships": []}
    },
    "company_founder_query": {
        "cypher": "MATCH (p:Person)-[:FOUNDED]->(o:Organization {id: $anchor}) RETURN p.id AS founder",
        "schema_requirements": {"labels": ["Person", "Organization"], "relationships": ["FOUNDED"]}
    }
}
