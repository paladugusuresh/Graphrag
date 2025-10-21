# graph_rag/cypher_generator.py
"""
Legacy template definitions moved to legacy/; this module now manages allow-list validation and template loading.
"""
import json
import re
import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
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

def generate_cypher_with_template(intent: str, params: dict) -> str | None:
    """
    Generate Cypher query using template if available, otherwise return None.
    
    Args:
        intent: The intent name (e.g., "goals_for_student")
        params: Parameters for the template
        
    Returns:
        Cypher query string if template exists and params are valid, None otherwise
    """
    if not intent or not isinstance(intent, str):
        logger.debug("Invalid intent provided for template generation")
        return None
    
    # Try to load template
    template_content = try_load_template(intent)
    if not template_content:
        logger.debug(f"No template available for intent: {intent}")
        return None
    
    # Validate parameters
    if not _validate_template_params(template_content, params, intent):
        logger.warning(f"Parameter validation failed for intent: {intent}")
        return None
    
    logger.info(f"Generated Cypher from template for intent: {intent}")
    return template_content


def _validate_template_params(template_content: str, params: dict, intent: str) -> bool:
    """
    Validate that all required parameters are provided for a template.
    
    Args:
        template_content: The Cypher template content
        params: Parameters provided
        intent: Intent name for logging
        
    Returns:
        True if all required parameters are provided, False otherwise
    """
    try:
        # Extract parameter placeholders from template ($param)
        param_pattern = r'\$(\w+)'
        required_params = set(re.findall(param_pattern, template_content))
        
        # Check if all required parameters are provided
        provided_params = set(params.keys())
        missing_params = required_params - provided_params
        
        if missing_params:
            logger.warning(f"Template for intent '{intent}' missing required parameters: {missing_params}")
            return False
        
        logger.debug(f"Parameter validation passed for intent: {intent}")
        return True
        
    except Exception as e:
        logger.error(f"Parameter validation error for intent '{intent}': {e}")
        return False


def generate_cypher_with_llm(intent: str, params: dict, question: str) -> str:
    """
    Generate Cypher query using LLM with strict parameterization enforcement and dynamic schema hints.
    
    Args:
        intent: The intent name
        params: Parameters extracted from the question
        question: Original user question
        
    Returns:
        Generated Cypher query string
        
    Raises:
        RuntimeError: If LLM generation fails or produces invalid Cypher
    """
    from graph_rag.llm_client import call_llm_structured
    from graph_rag.audit_store import audit_store
    from graph_rag.schema_manager import build_schema_hints
    
    # Get dynamic schema hints from allow-list
    schema_hints = build_schema_hints(max_items_per_category=50)
    
    # Create a structured prompt that enforces parameterization with live schema
    prompt = f"""You are a Cypher query generator for a Student Support graph database. Generate a safe, parameterized Cypher query using ONLY the allowed schema elements below.

QUESTION: {question}
INTENT: {intent}
PARAMETERS AVAILABLE: {params}

====== LIVE SCHEMA (USE ONLY THESE ELEMENTS) ======
{schema_hints}
====== END OF SCHEMA ======

CRITICAL REQUIREMENTS:
1. Use ONLY parameter placeholders ($param) for user data - NEVER use string literals
2. Use ONLY labels, relationships, and properties from the schema above
3. Include LIMIT $limit clause in ALL queries (use provided $limit parameter)
4. Use ONLY read operations (MATCH, RETURN, WHERE, ORDER BY, LIMIT, WITH)
5. For person name matching, ALWAYS use case-insensitive comparison with toLower()
6. NO write operations: CREATE, MERGE, SET, DELETE, REMOVE, DROP, CALL apoc.*, CALL dbms.* are FORBIDDEN

SAFE NAME-MATCHING PATTERNS (REQUIRED for person queries):
When matching person names (students, staff, case workers), use this pattern:
WITH toLower($person_name) AS normalized_name
MATCH (p:PersonLabel)
WHERE toLower(p.fullName) = normalized_name OR toLower(p.name) = normalized_name

Alternative single-line pattern:
WHERE toLower(p.fullName) = toLower($person_name) OR toLower(p.name) = toLower($person_name)

PARAMETERIZATION EXAMPLES:
✅ GOOD: WHERE toLower(s.fullName) = toLower($student_name)
✅ GOOD: WHERE toLower(s.fullName) = toLower($student_name) OR toLower(s.name) = toLower($student_name)
✅ GOOD: WITH toLower($student_name) AS q MATCH (s:Student) WHERE toLower(s.fullName) = q
❌ BAD: WHERE s.fullName = 'John Doe'
❌ BAD: WHERE s.fullName = $student_name (missing toLower)

✅ GOOD: LIMIT $limit
❌ BAD: LIMIT 20

EXAMPLE VALID QUERY WITH SAFE NAME MATCHING:
MATCH (s:Student)-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal)
WHERE toLower(s.fullName) = toLower($student_name) OR toLower(s.name) = toLower($student_name)
RETURN g.title AS goal, coalesce(g.status, '') AS status
ORDER BY g.title
LIMIT $limit

Generate the Cypher query now (use ONLY the schema elements listed above):"""

    try:
        # Use a simple response model for Cypher generation
        from pydantic import BaseModel
        from typing import Optional
        
        class CypherResponse(BaseModel):
            cypher: str = Field(description="Generated Cypher query")
            explanation: Optional[str] = Field(default="", description="Brief explanation of the query (optional)")
        
        response = call_llm_structured(
            prompt=prompt,
            schema_model=CypherResponse,
            model=None,  # Use default model
            max_tokens=512,
            force_json_mode=True,
            force_temperature_zero=True
        )
        
        cypher_query = response.cypher.strip()
        
        # Validate the generated Cypher
        if not _validate_generated_cypher(cypher_query, params, intent):
            error_msg = f"LLM generated invalid Cypher for intent: {intent}"
            logger.error(error_msg)
            audit_store.record({
                "event": "cypher_generation_failed",
                "reason": "invalid_cypher_generated",
                "intent": intent,
                "cypher_preview": cypher_query[:100],
                "question_preview": question[:100]
            })
            raise RuntimeError(error_msg)
        
        logger.info(f"Generated Cypher from LLM for intent: {intent}")
        return cypher_query
        
    except Exception as e:
        error_msg = f"LLM Cypher generation failed for intent '{intent}': {e}"
        logger.error(error_msg)
        audit_store.record({
            "event": "cypher_generation_failed",
            "reason": "llm_generation_error",
            "intent": intent,
            "error": str(e),
            "question_preview": question[:100]
        })
        raise RuntimeError(error_msg) from e


def _validate_generated_cypher(cypher: str, params: dict, intent: str) -> bool:
    """
    Validate that generated Cypher uses proper parameterization and schema compliance.
    
    Args:
        cypher: Generated Cypher query
        params: Expected parameters
        intent: Intent name for logging
        
    Returns:
        True if Cypher is valid, False otherwise
    """
    try:
        # Check for string literals (should use parameters instead)
        string_literal_pattern = r"['\"][^'\"]*['\"]"
        literals = re.findall(string_literal_pattern, cypher)
        
        # Filter out allowed literals (empty strings, numbers, etc.)
        problematic_literals = []
        for literal in literals:
            # Allow empty strings, numbers, and common keywords
            if literal not in ['""', "''", '"0"', '"1"', '"true"', '"false"', '"asc"', '"desc"']:
                # Check if this looks like user data (names, etc.)
                if len(literal) > 2 and not literal.replace('"', '').replace("'", '').isdigit():
                    problematic_literals.append(literal)
        
        if problematic_literals:
            logger.warning(f"Generated Cypher for intent '{intent}' contains string literals: {problematic_literals}")
            return False
        
        # Check for required parameters
        param_pattern = r'\$(\w+)'
        used_params = set(re.findall(param_pattern, cypher))
        provided_params = set(params.keys())
        
        # Check if all used parameters are provided
        missing_params = used_params - provided_params
        if missing_params:
            logger.warning(f"Generated Cypher for intent '{intent}' uses undefined parameters: {missing_params}")
            return False
        
        # Basic safety checks
        cypher_upper = cypher.upper()
        write_operations = ['CREATE', 'DELETE', 'SET', 'REMOVE', 'MERGE', 'DROP']
        for op in write_operations:
            if op in cypher_upper:
                logger.warning(f"Generated Cypher for intent '{intent}' contains write operation '{op}'")
                return False
        
        # Check for LIMIT clause
        if 'LIMIT' not in cypher_upper:
            logger.warning(f"Generated Cypher for intent '{intent}' missing LIMIT clause")
            return False
        
        logger.debug(f"Generated Cypher validation passed for intent: {intent}")
        return True
        
    except Exception as e:
        logger.error(f"Generated Cypher validation error for intent '{intent}': {e}")
        return False
