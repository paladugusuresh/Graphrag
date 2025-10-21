# graph_rag/cypher_generator.py
"""
Legacy template definitions moved to legacy/; this module now only manages allow-list validation.
"""
import json
import re
from graph_rag.observability import get_logger
from graph_rag.config_manager import get_config_value

logger = get_logger(__name__)

LABEL_REGEX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RELATIONSHIP_TYPE_REGEX = re.compile(r"^[A-Z_][A-Z0-9_]*$") # Cypher relationship types are typically uppercase

def load_allow_list(allow_list_path: str = None) -> dict:
    """Load allow list from JSON file and return as dictionary."""
    path = allow_list_path or get_config_value('schema.allow_list_path', 'allow_list.json')
    try:
        with open(path, 'r') as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.error("allow_list.json not found; create it with schema_catalog.generate_schema_allow_list()")
        return {"node_labels": [], "relationship_types": [], "properties": {}}

def validate_label(label: str, allow_list: dict = None) -> str:
    """Validate a label against the allow list and return formatted label."""
    if allow_list is None:
        allow_list = load_allow_list()
    
    if not label or not LABEL_REGEX.match(label):
        logger.warning(f"Invalid label '{label}' provided. Falling back to default 'Entity'.")
        return "`Entity`"
    
    if label not in allow_list.get("node_labels", []):
        logger.warning(f"Label '{label}' not in allow list. Falling back to default 'Entity'.")
        return "`Entity`"
    
    return f"`{label}`"

def validate_relationship_type(rel_type: str, allow_list: dict = None) -> str:
    """Validate a relationship type against the allow list and return formatted relationship type."""
    if allow_list is None:
        allow_list = load_allow_list()
    
    if not rel_type or not RELATIONSHIP_TYPE_REGEX.match(rel_type):
        logger.warning(f"Invalid relationship type '{rel_type}' provided. Falling back to default 'RELATED'.")
        return "`RELATED`"
    
    if rel_type not in allow_list.get("relationship_types", []):
        logger.warning(f"Relationship type '{rel_type}' not in allow list. Falling back to default 'RELATED'.")
        return "`RELATED`"
    
    return f"`{rel_type}`"
