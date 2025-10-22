# graph_rag/cypher_validator.py
"""
Conservative Cypher validation module for safety gate.
Extracts labels and relationship types from Cypher queries and validates against allow-list.

Note: This uses regex-based extraction which is conservative but may reject some valid Cypher.
For production use, consider implementing a proper Cypher parser for more accurate validation.
"""
import re
from typing import List, Dict, Any, Tuple
from graph_rag.observability import get_logger, cypher_validation_failures
from graph_rag.config_manager import get_config_value
from graph_rag.cypher_generator import validate_label, validate_relationship_type, load_allow_list
from graph_rag.audit_store import audit_store
from graph_rag.flags import GUARDRAILS_MAX_HOPS

logger = get_logger(__name__)

# Conservative regex patterns for extracting labels and relationships
# These patterns are designed to be safe and may miss some edge cases
LABEL_PATTERN = re.compile(r'\(\s*[a-zA-Z_][a-zA-Z0-9_]*\s*:\s*([A-Za-z_][A-Za-z0-9_]*)')
RELATIONSHIP_PATTERN = re.compile(r'\[:\s*([A-Z_][A-Z0-9_]*)\s*\]')

# Property extraction patterns for validation
PROPERTY_PATTERN = re.compile(r'(\w+)\.(\w+)')
RETURN_PROPERTY_PATTERN = re.compile(r'RETURN\s+.*?(\w+)\.(\w+)', re.IGNORECASE)
WHERE_PROPERTY_PATTERN = re.compile(r'WHERE\s+.*?(\w+)\.(\w+)', re.IGNORECASE)
ORDER_BY_PROPERTY_PATTERN = re.compile(r'ORDER\s+BY\s+.*?(\w+)\.(\w+)', re.IGNORECASE)

# LIMIT clause patterns
LIMIT_PATTERN = re.compile(r'LIMIT\s+(\d+|\$\w+)', re.IGNORECASE)
LIMIT_CLAUSE_PATTERN = re.compile(r'LIMIT\s+', re.IGNORECASE)

# Regex to find dangerous keywords that are not inside quotes
WRITE_PROC_RE = re.compile(
    r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP|LOAD\s+CSV|CALL|UNWIND|FOREACH|DETACH\s+DELETE|apoc\.|db\.)\b",
    re.IGNORECASE
)

# Regex for unbounded traversals: [*], [*..], [..], [:TYPE*], [:TYPE*..], [alias:TYPE*], etc.
# This matches patterns with or without relationship types and aliases
UNBOUNDED_TRAVERSAL_RE = re.compile(r"\[(?:\w+\s*:\s*)?[A-Z_][A-Z0-9_]*\s*\*(?!\d+)(?:\s*\.\.)?\s*\]|\[\s*:\s*[A-Z_][A-Z0-9_]*\s*\*(?!\d+)(?:\s*\.\.)?\s*\]|\[\s*\*(?!\d+)(?:\s*\.\.)?\s*\]") 

# Regex for bounded traversals: [*N..M], [*..M], [*N..], [:TYPE*N..M], etc.
BOUNDED_TRAVERSAL_RE = re.compile(r"\[(?::[A-Z_][A-Z0-9_]*)?\s*\*(\d*)\s*(\.\.)?\s*(\d*)\s*\]")

# Additional patterns for variable-length path detection
VARIABLE_LENGTH_PATTERN_RE = re.compile(r"-\s*\[\s*\*(\d*)\s*(\.\.)?\s*(\d*)\s*\]\s*-|-\s*\*\s*-|\*\s*\.\.|\*\d+\s*\.\.\s*\d+|\*\d+\s*\.\.")

def _mask_string_literals(text: str) -> str:
    """Replaces single and double-quoted strings with a placeholder to avoid false positives."""
    if not text:
        return ""
    # This regex handles escaped quotes inside strings
    return re.sub(r"('([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\")", "''", text)

def _validate_parameterization(cypher: str) -> bool:
    """
    Validate that Cypher query uses proper parameterization instead of string literals.
    
    Args:
        cypher: The Cypher query string to validate
        
    Returns:
        True if query uses proper parameterization, False otherwise
    """
    if not cypher or not cypher.strip():
        return True  # Empty queries are valid
    
    # Find all string literals
    string_literal_pattern = r"['\"]([^'\"]*)['\"]"
    literals = re.findall(string_literal_pattern, cypher)
    
    # Filter out allowed literals (empty strings, numbers, keywords)
    allowed_literals = {'', '0', '1', 'true', 'false', 'asc', 'desc', 'ascending', 'descending'}
    problematic_literals = []
    
    for literal in literals:
        # Allow empty strings, numbers, and common keywords
        if literal not in allowed_literals:
            # Check if this looks like user data (names, etc.)
            if len(literal) > 2 and not literal.isdigit():
                # Check if it's a common name pattern (First Last)
                if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', literal):
                    problematic_literals.append(literal)
                # Check if it's a single name that could be a person
                elif re.match(r'^[A-Z][a-z]+$', literal) and len(literal) > 3:
                    problematic_literals.append(literal)
    
    if problematic_literals:
        logger.debug(f"Found problematic string literals: {problematic_literals}")
        return False
    
    return True

def extract_properties(cypher: str) -> List[Tuple[str, str]]:
    """
    Extract property references (node.property) from Cypher query.
    
    Args:
        cypher: The Cypher query string
        
    Returns:
        List of tuples (node_alias, property_name) found in the query
    """
    if not cypher:
        return []
    
    properties = []
    
    # Extract from RETURN clauses
    return_matches = RETURN_PROPERTY_PATTERN.findall(cypher)
    for node_alias, prop_name in return_matches:
        properties.append((node_alias, prop_name))
    
    # Extract from WHERE clauses
    where_matches = WHERE_PROPERTY_PATTERN.findall(cypher)
    for node_alias, prop_name in where_matches:
        properties.append((node_alias, prop_name))
    
    # Extract from ORDER BY clauses
    order_matches = ORDER_BY_PROPERTY_PATTERN.findall(cypher)
    for node_alias, prop_name in order_matches:
        properties.append((node_alias, prop_name))
    
    # Extract general property patterns
    general_matches = PROPERTY_PATTERN.findall(cypher)
    for node_alias, prop_name in general_matches:
        properties.append((node_alias, prop_name))
    
    # Remove duplicates
    unique_properties = list(set(properties))
    logger.debug(f"Extracted properties from Cypher: {unique_properties}")
    
    return unique_properties


def _validate_properties(cypher: str, allow_list: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate that all property references in the query are in the allow-list.
    
    Args:
        cypher: The Cypher query string
        allow_list: The schema allow-list containing properties
        
    Returns:
        Tuple of (is_valid, details_dict)
    """
    if not cypher:
        return True, {}
    
    details = {
        "found_properties": [],
        "invalid_properties": [],
        "blocked_reason": None
    }
    
    # Extract all property references
    properties = extract_properties(cypher)
    details["found_properties"] = properties
    
    # Get allowed properties from allow-list
    allowed_properties = allow_list.get("properties", {})
    
    # Special handling for Goal entity - ensure goalType and id are allowed
    if "Goal" in allowed_properties:
        goal_props = set(allowed_properties["Goal"])
        # Add goalType and id if not already present
        if "goalType" not in goal_props:
            goal_props.add("goalType")
        if "id" not in goal_props:
            goal_props.add("id")
        allowed_properties["Goal"] = list(goal_props)
    
    # Check each property reference
    invalid_properties = []
    for node_alias, prop_name in properties:
        # Find the label for this node alias by looking at the query
        # This is a simplified approach - in practice, you might need more sophisticated parsing
        node_label = None
        
        # Try to find the label by looking for patterns like (alias:Label)
        label_match = re.search(rf'\(\s*{re.escape(node_alias)}\s*:\s*([A-Za-z_][A-Za-z0-9_]*)', cypher)
        if label_match:
            node_label = label_match.group(1)
        
        # If we found a label, check if the property is allowed
        if node_label and node_label in allowed_properties:
            allowed_props = set(allowed_properties[node_label])
            if prop_name not in allowed_props:
                invalid_properties.append(f"{node_label}.{prop_name}")
        elif node_label:
            # Label exists but no properties defined - this might be an issue
            logger.warning(f"Node label '{node_label}' found but no properties defined in allow-list")
            invalid_properties.append(f"{node_label}.{prop_name}")
        else:
            # Couldn't determine the label - be conservative and reject
            logger.warning(f"Could not determine label for node alias '{node_alias}'")
            invalid_properties.append(f"{node_alias}.{prop_name}")
    
    details["invalid_properties"] = invalid_properties
    
    if invalid_properties:
        reason = "unknown_property"
        logger.warning(f"Property validation failed. Invalid properties: {invalid_properties}")
        cypher_validation_failures.inc()
        
        details["blocked_reason"] = f"Query references unknown properties: {', '.join(invalid_properties)}"
        
        # Audit log
        audit_store.record({
            "event": "cypher_validation_failed",
            "reason": reason,
            "invalid_properties": invalid_properties,
            "cypher_preview": cypher[:200]
        })
        
        return False, details
    
    logger.debug("Property validation passed")
    return True, details


def _validate_limit_clause(cypher: str, params: Dict[str, Any] = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate and enforce LIMIT clause in Cypher query.
    
    Args:
        cypher: The Cypher query string
        params: Query parameters (may be modified to add limit)
        
    Returns:
        Tuple of (is_valid, modified_cypher, details_dict)
    """
    if not cypher:
        return True, cypher, {}
    
    details = {
        "has_limit": False,
        "limit_value": None,
        "limit_exceeded": False,
        "blocked_reason": None
    }
    
    # Get configuration values
    max_limit = get_config_value("validator.max_limit", 100)
    default_limit = get_config_value("validator.default_limit", 20)
    
    # Check if LIMIT clause exists
    limit_match = LIMIT_PATTERN.search(cypher)
    if limit_match:
        details["has_limit"] = True
        limit_value = limit_match.group(1)
        details["limit_value"] = limit_value
        
        # Check if it's a parameter ($limit) or a literal number
        if limit_value.startswith('$'):
            # It's a parameter - check if it exceeds max_limit
            if params and limit_value[1:] in params:
                param_value = params[limit_value[1:]]
                if isinstance(param_value, int) and param_value > max_limit:
                    details["limit_exceeded"] = True
                    reason = "limit_exceeded"
                    logger.warning(f"LIMIT clause exceeds maximum allowed limit: {param_value} > {max_limit}")
                    cypher_validation_failures.inc()
                    
                    details["blocked_reason"] = f"LIMIT value ({param_value}) exceeds maximum allowed limit ({max_limit})"
                    
                    # Audit log
                    audit_store.record({
                        "event": "cypher_validation_failed",
                        "reason": reason,
                        "limit_value": param_value,
                        "max_limit": max_limit,
                        "cypher_preview": cypher[:200]
                    })
                    
                    return False, cypher, details
        else:
            # It's a literal number
            try:
                literal_limit = int(limit_value)
                if literal_limit > max_limit:
                    details["limit_exceeded"] = True
                    reason = "limit_exceeded"
                    logger.warning(f"LIMIT clause exceeds maximum allowed limit: {literal_limit} > {max_limit}")
                    cypher_validation_failures.inc()
                    
                    details["blocked_reason"] = f"LIMIT value ({literal_limit}) exceeds maximum allowed limit ({max_limit})"
                    
                    # Audit log
                    audit_store.record({
                        "event": "cypher_validation_failed",
                        "reason": reason,
                        "limit_value": literal_limit,
                        "max_limit": max_limit,
                        "cypher_preview": cypher[:200]
                    })
                    
                    return False, cypher, details
            except ValueError:
                # Invalid limit value
                reason = "invalid_limit_value"
                logger.warning(f"Invalid LIMIT value: {limit_value}")
                cypher_validation_failures.inc()
                
                details["blocked_reason"] = f"Invalid LIMIT value: {limit_value}"
                
                # Audit log
                audit_store.record({
                    "event": "cypher_validation_failed",
                    "reason": reason,
                    "limit_value": limit_value,
                    "cypher_preview": cypher[:200]
                })
                
                return False, cypher, details
    else:
        # No LIMIT clause found - add one
        logger.debug("No LIMIT clause found, adding default LIMIT")
        
        # Add LIMIT clause at the end
        modified_cypher = cypher.rstrip().rstrip(';')
        if not modified_cypher.upper().endswith('LIMIT'):
            modified_cypher += f" LIMIT $limit"
        
        # Add default limit to parameters if provided
        if params is not None:
            params["limit"] = default_limit
        
        details["limit_added"] = True
        details["default_limit"] = default_limit
        
        logger.debug(f"Added LIMIT $limit with default value {default_limit}")
        return True, modified_cypher, details
    
    logger.debug("LIMIT clause validation passed")
    return True, cypher, details


def extract_labels(cypher: str) -> List[str]:
    """
    Extract node labels from Cypher query using conservative regex.
    
    Args:
        cypher: The Cypher query string
        
    Returns:
        List of unique labels found in the query
    """
    if not cypher:
        return []
    
    # Find all label matches
    matches = LABEL_PATTERN.findall(cypher)
    
    # Remove duplicates and return
    unique_labels = list(set(matches))
    logger.debug(f"Extracted labels from Cypher: {unique_labels}")
    
    return unique_labels

def extract_rels(cypher: str) -> List[str]:
    """
    Extract relationship types from Cypher query using conservative regex.
    
    Args:
        cypher: The Cypher query string
        
    Returns:
        List of unique relationship types found in the query
    """
    if not cypher:
        return []
    
    # Find all relationship type matches
    matches = RELATIONSHIP_PATTERN.findall(cypher)
    
    # Remove duplicates and return
    unique_rels = list(set(matches))
    logger.debug(f"Extracted relationship types from Cypher: {unique_rels}")
    
    return unique_rels


def _enforce_depth_caps(cypher: str, max_hops: int = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Enforce maximum traversal depth caps on Cypher query.
    
    Scans for relationship expansion patterns and rejects queries with:
    - Unbounded traversals: [*], [*..], [..]
    - Over-depth patterns: [*..N] where N > max_hops
    - Variable upper bounds: [*N..] (unbounded)
    
    Args:
        cypher: The Cypher query string (should be string-masked)
        max_hops: Maximum allowed traversal depth (defaults to GUARDRAILS_MAX_HOPS flag)
        
    Returns:
        Tuple of (is_valid, details_dict)
        - is_valid: True if depth constraints satisfied, False otherwise
        - details_dict: Contains violation info, patterns found, and blocked_reason
    """
    if not cypher:
        return True, {}
    
    # Get max_hops from flag if not provided
    if max_hops is None:
        max_hops = GUARDRAILS_MAX_HOPS()
    
    details = {
        "variable_length_patterns": [],
        "blocked_reason": None,
        "depth_limit": max_hops
    }
    
    logger.debug(f"Enforcing depth cap: max_hops={max_hops}")
    
    # 1. Check for unbounded traversals: [*], [*..], [..], [:TYPE*], etc.
    unbounded_matches = UNBOUNDED_TRAVERSAL_RE.findall(cypher)
    if unbounded_matches:
        reason = "unbounded_traversal_detected"
        logger.warning(f"Depth cap violation: Unbounded traversal detected. Max hops: {max_hops}")
        cypher_validation_failures.inc()
        
        # Build pattern list - matches are now full pattern strings
        for match in unbounded_matches:
            details["variable_length_patterns"].append(match)
        
        details["blocked_reason"] = f"Unbounded traversal (e.g., [*] or [*..]) exceeds depth cap ({max_hops})."
        
        # Audit log
        audit_store.record({
            "event": "cypher_validation_failed",
            "reason": reason,
            "depth_cap": max_hops,
            "patterns": details["variable_length_patterns"],
            "cypher_preview": cypher[:200]
        })
        
        return False, details
    
    # 2. Check bounded traversals: [*N..M], [*..M], [*N..]
    bounded_matches = list(BOUNDED_TRAVERSAL_RE.finditer(cypher))
    for match in bounded_matches:
        lower, dots, upper = match.groups()
        pattern = match.group(0)
        details["variable_length_patterns"].append(pattern)
        
        # Check upper bound exists and is within limit
        if upper and int(upper) > max_hops:
            reason = "traversal_depth_exceeds_limit"
            logger.warning(f"Depth cap violation: Traversal depth ({upper}) exceeds limit ({max_hops}). Pattern: {pattern}")
            cypher_validation_failures.inc()
            
            details["blocked_reason"] = f"Traversal depth ({upper}) exceeds depth cap ({max_hops})."
            details["violating_pattern"] = pattern
            details["requested_depth"] = int(upper)
            
            # Audit log
            audit_store.record({
                "event": "cypher_validation_failed",
                "reason": reason,
                "depth_cap": max_hops,
                "requested_depth": upper,
                "pattern": pattern,
                "cypher_preview": cypher[:200]
            })
            
            return False, details
        
        # Check for variable upper bound: [*N..] (unbounded)
        if dots and not upper:
            reason = "unbounded_traversal_detected"
            logger.warning(f"Depth cap violation: Variable upper bound traversal {pattern} exceeds depth cap ({max_hops}).")
            cypher_validation_failures.inc()
            
            details["blocked_reason"] = f"Traversal with no upper bound (e.g., [*2..]) exceeds depth cap ({max_hops})."
            details["violating_pattern"] = pattern
            
            # Audit log
            audit_store.record({
                "event": "cypher_validation_failed",
                "reason": reason,
                "depth_cap": max_hops,
                "pattern": pattern,
                "cypher_preview": cypher[:200]
            })
            
            return False, details
    
    # 3. Additional variable-length pattern detection
    additional_patterns = VARIABLE_LENGTH_PATTERN_RE.findall(cypher)
    for pattern_match in additional_patterns:
        if isinstance(pattern_match, tuple) and len(pattern_match) > 0:
            pattern_str = pattern_match[0] if pattern_match[0] else "unbounded"
            if pattern_str and pattern_str not in details["variable_length_patterns"]:
                details["variable_length_patterns"].append(pattern_str)
        elif isinstance(pattern_match, str) and pattern_match not in details["variable_length_patterns"]:
            details["variable_length_patterns"].append(pattern_match)
    
    logger.debug(f"Depth cap check passed. Patterns found: {details['variable_length_patterns']}")
    return True, details

def validate_cypher(cypher: str, params: Dict[str, Any] = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate Cypher query against allow-list and security rules.
    This is the core security firewall with enhanced validation.
    
    Args:
        cypher: The Cypher query string to validate
        params: Query parameters (may be modified to add limit)
        
    Returns:
        Tuple of (is_valid, details_dict)
    """
    if not cypher or not cypher.strip():
        logger.warning("Empty Cypher query provided for validation")
        return False, {"error": "Empty query"}

    details = {
        "found_labels": [],
        "found_relationships": [],
        "found_properties": [],
        "invalid_labels": [],
        "invalid_relationships": [],
        "invalid_properties": [],
        "invalid_clauses": [],
        "invalid_procedures": [],
        "variable_length_patterns": [],
        "limit_details": {},
        "blocked_reason": None,
    }
    
    try:
        # 1. Mask strings to prevent false positives in checks
        sanitized_cypher = _mask_string_literals(cypher)
        
        # 2. CRITICAL: Check for Write/Procedure keywords
        write_match = WRITE_PROC_RE.search(sanitized_cypher)
        if write_match:
            blocked_keyword = write_match.group(0)
            reason = "write_or_procedure_detected"
            logger.warning(f"Cypher validation failed. Dangerous keyword found: {blocked_keyword}")
            cypher_validation_failures.inc()
            audit_store.record({
                "event": "cypher_validation_failed",
                "reason": reason,
                "cypher_preview": cypher[:200],
                "blocked_keyword": blocked_keyword
            })
            details["blocked_reason"] = f"Use of blocked keyword: {blocked_keyword}"
            
            # Populate invalid_clauses and invalid_procedures
            if blocked_keyword.upper() in ['CALL', 'APOC.', 'DB.']:
                details["invalid_procedures"].append(blocked_keyword)
            else:
                details["invalid_clauses"].append(blocked_keyword)
            
            return False, details

        # 3. CRITICAL: Enforce depth caps using dedicated function
        depth_valid, depth_details = _enforce_depth_caps(sanitized_cypher)
        if not depth_valid:
            # Merge depth violation details into main details
            details["blocked_reason"] = depth_details.get("blocked_reason")
            details["variable_length_patterns"] = depth_details.get("variable_length_patterns", [])
            if "violating_pattern" in depth_details:
                details["violating_pattern"] = depth_details["violating_pattern"]
            if "requested_depth" in depth_details:
                details["requested_depth"] = depth_details["requested_depth"]
            if "depth_limit" in depth_details:
                details["depth_limit"] = depth_details["depth_limit"]
            return False, details
        
        # Merge variable_length_patterns from depth check
        details["variable_length_patterns"] = depth_details.get("variable_length_patterns", [])

        # 4. Check for string literals that should be parameters
        if not _validate_parameterization(cypher):
            reason = "parameterization_violation"
            logger.warning(f"Cypher validation failed. Query contains string literals that should use parameters")
            cypher_validation_failures.inc()
            audit_store.record({
                "event": "cypher_validation_failed",
                "reason": reason,
                "cypher_preview": cypher[:200]
            })
            details["blocked_reason"] = "Query contains string literals that should use parameters ($param)"
            return False, details

        # 5. Load allow list
        allow_list = load_allow_list()
        allow_list_labels = set(allow_list.get("node_labels", []))
        allow_list_rels = set(allow_list.get("relationship_types", []))

        # 6. Extract and Validate Labels/Relationships
        found_labels = extract_labels(cypher)
        found_relationships = extract_rels(cypher)
        
        details["found_labels"] = found_labels
        details["found_relationships"] = found_relationships

        invalid_labels = [l for l in found_labels if l not in allow_list_labels]
        invalid_relationships = [r for r in found_relationships if r not in allow_list_rels]
        
        details["invalid_labels"] = invalid_labels
        details["invalid_relationships"] = invalid_relationships

        if invalid_labels or invalid_relationships:
            reason = "schema_violation"
            logger.warning(f"Cypher validation failed. Invalid labels: {invalid_labels}, Invalid rels: {invalid_relationships}")
            cypher_validation_failures.inc()
            audit_store.record({
                "event": "cypher_validation_failed",
                "reason": reason,
                "cypher_preview": cypher[:200],
                "invalid_labels": invalid_labels,
                "invalid_relationships": invalid_relationships
            })
            details["blocked_reason"] = "Query uses schema terms not in the allow-list."
            return False, details

        # 7. NEW: Validate Properties
        prop_valid, prop_details = _validate_properties(cypher, allow_list)
        if not prop_valid:
            # Merge property validation details
            details["found_properties"] = prop_details.get("found_properties", [])
            details["invalid_properties"] = prop_details.get("invalid_properties", [])
            details["blocked_reason"] = prop_details.get("blocked_reason")
            return False, details
        
        # Merge property details
        details["found_properties"] = prop_details.get("found_properties", [])

        # 8. NEW: Validate and Enforce LIMIT clause
        limit_valid, modified_cypher, limit_details = _validate_limit_clause(cypher, params)
        if not limit_valid:
            details["limit_details"] = limit_details
            details["blocked_reason"] = limit_details.get("blocked_reason")
            return False, details
        
        # Merge limit details
        details["limit_details"] = limit_details
        
        # If LIMIT was added, update the cypher
        if limit_details.get("limit_added", False):
            details["modified_cypher"] = modified_cypher
            logger.info(f"Added LIMIT clause to query: {modified_cypher[:100]}...")

        logger.info(f"Cypher validation passed for query: {cypher[:100]}...")
        return True, details

    except Exception as e:
        # CRITICAL: Fail-Closed Behavior
        logger.error(f"Error during Cypher validation: {e}")
        reason = "validation_process_error"
        cypher_validation_failures.inc()
        audit_store.record({
            "event": "cypher_validation_error",
            "cypher_preview": cypher[:200],
            "error": str(e),
            "reason": reason
        })
        details["blocked_reason"] = f"An internal error occurred during validation: {e}"
        return False, details

def validate_cypher_safe(cypher: str, params: Dict[str, Any] = None) -> bool:
    """
    Simple boolean validation wrapper for cases where only pass/fail is needed.
    
    Args:
        cypher: The Cypher query string to validate
        params: Query parameters (may be modified to add limit)
        
    Returns:
        True if query is valid, False otherwise
    """
    is_valid, _ = validate_cypher(cypher, params)
    return is_valid
