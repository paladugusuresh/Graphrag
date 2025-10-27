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
    prompt = f"""You are a Cypher query generator for a Student Support graph database. Generate a safe, parameterized Cypher query using ONLY the allowed schema elements listed below.

QUESTION: {question}
INTENT: {intent}
PARAMETERS AVAILABLE: {params}

====== MANDATORY SCHEMA CONSTRAINTS (USE ONLY THESE - NO EXCEPTIONS) ======
{schema_hints}
====== END OF SCHEMA ======

⚠️ ABSOLUTE REQUIREMENTS - VIOLATION = QUERY REJECTION ⚠️

1. SCHEMA ADHERENCE (STRICTEST PRIORITY):
   
   MUST ONLY USE LABELS FROM THE LIST ABOVE:
   - You MUST use ONLY the node labels listed in "ALLOWED NODE LABELS" above
   - DO NOT invent, guess, or use ANY label not explicitly listed
   - If a label you want is not in the list, pick the closest allowed label or omit it
   - Example: If only "Student" exists, NEVER use "Person" or "User"
   
   MUST ONLY USE RELATIONSHIPS FROM THE LIST ABOVE:
   - You MUST use ONLY the relationship types listed in "ALLOWED RELATIONSHIPS" above
   - DO NOT invent, guess, or use ANY relationship not explicitly listed
   - If a relationship you want is not in the list, pick the closest allowed one or use a simpler query
   
   MUST ONLY USE PROPERTIES FROM THE LIST ABOVE:
   - For each label, you MUST use ONLY the properties listed for that label in "ALLOWED PROPERTIES" above
   - DO NOT reference ANY property not explicitly listed for that label
   - If the user asks for a property not in the list (e.g., "title" when only "goalType" exists), either:
     a) Use the closest allowed property (e.g., use "goalType" instead of "title")
     b) Omit that property from the query entirely
   - Example: For "Goal" label, if allowed properties are [goalType, id, description], 
              you MUST NOT use g.title, g.status, or any other property
   
2. READ-ONLY OPERATIONS ONLY:
   ✅ ALLOWED: MATCH, OPTIONAL MATCH, RETURN, WHERE, ORDER BY, LIMIT, WITH, UNWIND, CASE, COALESCE
   ❌ FORBIDDEN: CREATE, MERGE, SET, DELETE, REMOVE, DROP, CALL, LOAD CSV, FOREACH, INDEX, CONSTRAINT, apoc.*, dbms.*

3. MANDATORY PARAMETERIZATION (NO STRING LITERALS FOR USER DATA):
   ✅ ALL user input data MUST use parameter placeholders ($param) - NEVER string literals
   ✅ Example: WHERE toLower(s.fullName) = toLower($student_name)
   ❌ NEVER: WHERE s.fullName = 'John Doe' or WHERE s.fullName = "{params.get('student_name')}"
   ❌ NEVER: Any hardcoded user data in quotes

4. MANDATORY LIMIT CLAUSE:
   ✅ EVERY query MUST end with: LIMIT $limit
   ✅ MUST use the $limit parameter (not a hardcoded number)
   ❌ NEVER: LIMIT 20 or LIMIT 100 (hardcoded limits)

5. SAFE NAME-MATCHING PATTERNS (REQUIRED for person queries):
   ✅ ALWAYS use case-insensitive comparison with toLower() for person names
   ✅ Pattern: WHERE toLower(p.fullName) = toLower($person_name) OR toLower(p.name) = toLower($person_name)
   ❌ NEVER: WHERE p.fullName = $person_name (case-sensitive - will fail on "John" vs "john")

CRITICAL REMINDERS:
• The schema list above is EXHAUSTIVE - it contains ALL allowed elements
• DO NOT be creative - use ONLY what is explicitly listed
• When in doubt, use simpler queries with fewer elements rather than guessing
• Prefer omitting a property over inventing one not in the schema
• Use COALESCE(property, '') for optional properties to handle nulls safely

VALID QUERY PATTERN (follows all rules):
MATCH (s:Student)-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal)
WHERE toLower(s.fullName) = toLower($student_name)
RETURN coalesce(g.goalType, '') AS goal_type, coalesce(g.description, '') AS description
ORDER BY g.goalType
LIMIT $limit

Generate the Cypher query now. It MUST use ONLY the schema elements listed above, MUST use parameters (no string literals), and MUST end with LIMIT $limit:"""

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
        
        # Ensure LIMIT clause is present and parameterized
        cypher_query, params = _ensure_limit_clause(cypher_query, params)
        
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


def _ensure_limit_clause(cypher: str, params: dict) -> tuple[str, dict]:
    """
    Ensure that the Cypher query has a LIMIT $limit clause.
    If missing, automatically append it and add the limit parameter.
    
    Args:
        cypher: Generated Cypher query
        params: Parameters dictionary
        
    Returns:
        Tuple of (modified_cypher, updated_params)
    """
    cypher_upper = cypher.upper()
    
    # Check if LIMIT is already present
    if 'LIMIT' in cypher_upper:
        # Check if it's using $limit parameter
        if '$limit' in cypher:
            return cypher, params
        else:
            # Replace hardcoded LIMIT with $limit parameter
            limit_pattern = r'LIMIT\s+\d+'
            modified_cypher = re.sub(limit_pattern, 'LIMIT $limit', cypher, flags=re.IGNORECASE)
            return modified_cypher, params
    
    # No LIMIT clause found - append it
    default_limit = get_config_value('cypher.default_limit', 20)
    
    # Ensure params has limit
    if 'limit' not in params:
        params = params.copy()
        params['limit'] = default_limit
    
    # Append LIMIT clause
    modified_cypher = cypher.rstrip() + f"\nLIMIT $limit"
    
    logger.debug(f"Added LIMIT $limit clause to Cypher query (default: {default_limit})")
    return modified_cypher, params


def _validate_generated_cypher(cypher: str, params: dict, intent: str) -> bool:
    """
    Validate that generated Cypher uses proper parameterization, schema compliance, and safety rules.
    
    Args:
        cypher: Generated Cypher query
        params: Expected parameters
        intent: Intent name for logging
        
    Returns:
        True if Cypher is valid, False otherwise
    """
    try:
        # 1. Check for forbidden write operations
        forbidden_keywords = [
            'CREATE', 'MERGE', 'SET', 'DELETE', 'REMOVE', 'DROP', 
            'CALL', 'LOAD CSV', 'FOREACH', 'INDEX', 'CONSTRAINT'
        ]
        
        cypher_upper = cypher.upper()
        for keyword in forbidden_keywords:
            if keyword in cypher_upper:
                logger.warning(f"Generated Cypher for intent '{intent}' contains forbidden keyword: {keyword}")
                return False
        
        # Check for apoc.* and dbms.* procedures
        if 'APOC.' in cypher_upper or 'DBMS.' in cypher_upper:
            logger.warning(f"Generated Cypher for intent '{intent}' contains forbidden procedures (apoc.* or dbms.*)")
            return False
        
        # 2. Check for string literals (should use parameters instead)
        string_literal_pattern = r"['\"][^'\"]*['\"]"
        literals = re.findall(string_literal_pattern, cypher)
        
        # Filter out allowed literals (empty strings, numbers, keywords)
        allowed_literals = {
            '""', "''", '"0"', '"1"', '"true"', '"false"', '"asc"', '"desc"',
            '"ascending"', '"descending"', '"null"', '"NULL"'
        }
        
        problematic_literals = []
        for literal in literals:
            if literal not in allowed_literals:
                # Check if this looks like user data (names, etc.)
                clean_literal = literal.replace('"', '').replace("'", '')
                if len(clean_literal) > 2 and not clean_literal.isdigit():
                    problematic_literals.append(literal)
        
        if problematic_literals:
            logger.warning(f"Generated Cypher for intent '{intent}' contains string literals: {problematic_literals}")
            return False
        
        # 3. Check for mandatory LIMIT clause
        if 'LIMIT' not in cypher_upper:
            logger.warning(f"Generated Cypher for intent '{intent}' missing mandatory LIMIT clause")
            return False
        
        # Check that LIMIT uses parameter, not hardcoded value
        limit_pattern = r'LIMIT\s+(\d+)'
        hardcoded_limits = re.findall(limit_pattern, cypher_upper)
        if hardcoded_limits:
            logger.warning(f"Generated Cypher for intent '{intent}' uses hardcoded LIMIT: {hardcoded_limits}")
            return False
        
        # 4. Check for required parameters
        param_pattern = r'\$(\w+)'
        used_params = set(re.findall(param_pattern, cypher))
        
        # Check that $limit parameter is used
        if 'limit' not in used_params:
            logger.warning(f"Generated Cypher for intent '{intent}' doesn't use $limit parameter")
            return False
        
        # 5. Check for safe name-matching patterns (case-insensitive)
        # Look for person name comparisons that might be case-sensitive
        person_name_patterns = [
            r'WHERE\s+\w+\.(?:fullName|name)\s*=\s*\$\w+',  # Case-sensitive comparison
            r'WHERE\s+\w+\.(?:fullName|name)\s*=\s*["\'][^"\']*["\']'  # String literal comparison
        ]
        
        for pattern in person_name_patterns:
            matches = re.findall(pattern, cypher, re.IGNORECASE)
            if matches:
                logger.warning(f"Generated Cypher for intent '{intent}' may have unsafe name matching: {matches}")
                return False
        
        # 6. Check for conservative schema adherence (basic check)
        # Look for obvious non-schema elements (this is a basic check, validator does detailed validation)
        suspicious_patterns = [
            r':\w*[a-z]\w*',  # Lowercase labels (should be PascalCase)
            r'\[:\w*[a-z]\w*\]',  # Lowercase relationship types (should be UPPER_CASE)
        ]
        
        for pattern in suspicious_patterns:
            matches = re.findall(pattern, cypher)
            if matches:
                logger.warning(f"Generated Cypher for intent '{intent}' may contain non-standard schema elements: {matches}")
                # Don't fail here, just warn - let the validator do detailed checking
        
        logger.debug(f"Generated Cypher for intent '{intent}' passed all safety validations")
        return True
        
    except Exception as e:
        logger.error(f"Error validating generated Cypher for intent '{intent}': {e}")
        return False
