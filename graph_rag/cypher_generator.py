# graph_rag/cypher_generator.py
"""
Legacy template definitions moved to legacy/; this module now manages allow-list validation and template loading.
"""
import json
import re
import os
from typing import Optional, Dict, Any
from graph_rag.observability import get_logger
from graph_rag.config_manager import get_config_value

logger = get_logger(__name__)

LABEL_REGEX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RELATIONSHIP_TYPE_REGEX = re.compile(r"^[A-Z_][A-Z0-9_]*$") # Cypher relationship types are typically uppercase

def try_load_template(intent_name: str) -> Optional[str]:
    """
    Load a Cypher template for a known intent.
    
    This function loads parameterized Cypher templates for frequent intents,
    providing optimized queries for common SPED/MTSS/IEP use cases.
    
    Args:
        intent_name: The intent name to load template for (e.g., "goals_for_student")
        
    Returns:
        Cypher template string if found and valid, None otherwise
        
    Template Mapping:
        - "goals_for_student" -> goals_for_student.cypher
        - "accommodations_for_student" -> accommodations_for_student.cypher
        - "case_manager_for_student" -> case_manager_for_student.cypher
        - "eval_reports_for_student_in_range" -> eval_reports_for_student_in_range.cypher
        - "concern_areas_for_student" -> concern_areas_for_student.cypher
    """
    if not intent_name or not isinstance(intent_name, str):
        logger.debug(f"Invalid intent name provided: {intent_name}")
        return None
    
    # Map intent names to template files
    template_mapping = {
        "goals_for_student": "goals_for_student.cypher",
        "accommodations_for_student": "accommodations_for_student.cypher", 
        "case_manager_for_student": "case_manager_for_student.cypher",
        "eval_reports_for_student_in_range": "eval_reports_for_student_in_range.cypher",
        "concern_areas_for_student": "concern_areas_for_student.cypher"
    }
    
    template_filename = template_mapping.get(intent_name)
    if not template_filename:
        logger.debug(f"No template mapping found for intent: {intent_name}")
        return None
    
    # Load template file
    templates_dir = get_config_value('templates.directory', 'graph_rag/templates')
    template_path = os.path.join(templates_dir, template_filename)
    
    try:
        if not os.path.exists(template_path):
            logger.debug(f"Template file not found: {template_path}")
            return None
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read().strip()
        
        if not template_content:
            logger.warning(f"Template file is empty: {template_path}")
            return None
        
        # Validate template against allow-list
        if not _validate_template(template_content, intent_name):
            logger.warning(f"Template validation failed for intent: {intent_name}")
            return None
        
        logger.info(f"Loaded template for intent '{intent_name}' from {template_path}")
        return template_content
        
    except Exception as e:
        logger.warning(f"Failed to load template for intent '{intent_name}': {e}")
        return None


def _validate_template(template_content: str, intent_name: str) -> bool:
    """
    Validate a Cypher template against the allow-list and safety rules.
    
    Args:
        template_content: The Cypher template content
        intent_name: The intent name for logging
        
    Returns:
        True if template is valid, False otherwise
    """
    try:
        # Load allow-list for validation
        allow_list = load_allow_list()
        
        # Basic safety checks
        template_upper = template_content.upper()
        
        # Check for write operations
        write_operations = ['CREATE', 'DELETE', 'SET', 'REMOVE', 'MERGE', 'DROP']
        for op in write_operations:
            if op in template_upper:
                logger.warning(f"Template for intent '{intent_name}' contains write operation '{op}' - rejecting")
                return False
        
        # Check for unbounded traversals
        if '*' in template_content and '..' in template_content:
            logger.warning(f"Template for intent '{intent_name}' contains unbounded traversal - rejecting")
            return False
        
        # Extract labels and relationships for validation
        # Labels: :LabelName (but not in relationship brackets)
        labels = re.findall(r'(?<!\[):(\w+)', template_content)
        relationships = re.findall(r'\[:(\w+)\]', template_content)
        
        # Validate labels
        for label in labels:
            if label not in allow_list.get("node_labels", []):
                logger.warning(f"Template for intent '{intent_name}' uses unknown label '{label}' - rejecting")
                return False
        
        # Validate relationships
        for rel in relationships:
            if rel not in allow_list.get("relationship_types", []):
                logger.warning(f"Template for intent '{intent_name}' uses unknown relationship '{rel}' - rejecting")
                return False
        
        # Check for LIMIT clause (safety requirement)
        if 'LIMIT' not in template_upper:
            logger.warning(f"Template for intent '{intent_name}' missing LIMIT clause - rejecting")
            return False
        
        logger.debug(f"Template validation passed for intent: {intent_name}")
        return True
        
    except Exception as e:
        logger.error(f"Template validation error for intent '{intent_name}': {e}")
        return False


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
