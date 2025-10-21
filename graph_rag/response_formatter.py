# graph_rag/response_formatter.py
"""
Response formatting module for UI display and LLM prompt generation.
Provides utilities for transforming query results into various output formats.
"""
import json
from typing import List, Dict, Any, Optional
from graph_rag.observability import get_logger
from graph_rag.config_manager import get_config_value
from graph_rag.audit_store import audit_store

logger = get_logger(__name__)

def _serialize_value(value):
    """
    Deterministic serializer for safe value conversion.
    
    Primitives and lists/dicts pass through. Neo4j-like objects are converted
    to safe representations. Fallback to string conversion for unknown types.
    """
    # Primitives and lists/dicts pass through
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    # Neo4j-like node/rel detection by duck-typing
    try:
        if hasattr(value, "id"):
            return str(getattr(value, "id"))
        if hasattr(value, "labels"):
            return list(getattr(value, "labels"))
    except Exception:
        pass
    # Fallback to str
    return str(value)

def rows_to_table(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize a list of dictionaries into a consistent table format.
    
    This function ensures all rows have consistent structure and handles
    various data types that might come from Neo4j queries. It's designed
    to create clean, predictable output for UI display.
    
    Args:
        rows: List of dictionaries representing query results
        
    Returns:
        List of normalized dictionaries with consistent structure
        
    Example:
        >>> rows = [{"name": "John", "age": 30}, {"name": "Jane", "city": "NYC"}]
        >>> rows_to_table(rows)
        [{"name": "John", "age": 30, "city": None}, {"name": "Jane", "age": None, "city": "NYC"}]
    """
    if not rows:
        logger.debug("Empty rows list provided to rows_to_table")
        return []
    
    # Collect all unique keys from all rows in deterministic order
    all_keys = []
    for row in rows:
        if isinstance(row, dict):
            for k in row.keys():
                if k not in all_keys:
                    all_keys.append(k)
    
    # Normalize each row to have all keys
    normalized_rows = []
    for row in rows:
        if not isinstance(row, dict):
            audit_store.record({
                "event": "rows_to_table_skipped_non_dict",
                "type": str(type(row)),
                "note": "row skipped"
            })
            continue
            
        normalized_row = {}
        for key in all_keys:
            value = row.get(key)
            normalized_row[key] = _serialize_value(value)
        
        normalized_rows.append(normalized_row)
    
    logger.debug(f"Normalized {len(rows)} rows to table with {len(all_keys)} columns")
    return normalized_rows

def build_graph_payload(primary_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract node IDs and simple edges from primary query results for graph visualization.
    
    This function creates a lightweight payload suitable for graph visualization
    by extracting node identifiers and basic relationship information from
    query results. It's designed to be conservative and avoid exposing
    sensitive data.
    
    Args:
        primary_rows: List of dictionaries representing primary query results
        
    Returns:
        Dictionary containing:
        - nodes: List of node dictionaries with id and basic properties
        - edges: List of edge dictionaries with source, target, and type
        - metadata: Basic statistics about the graph
        
    Example:
        >>> rows = [{"id": "node1", "labels": ["Person"], "name": "John"}]
        >>> build_graph_payload(rows)
        {
            "nodes": [{"id": "node1", "labels": ["Person"], "name": "John"}],
            "edges": [],
            "metadata": {"node_count": 1, "edge_count": 0}
        }
    """
    if not primary_rows:
        logger.debug("Empty primary_rows provided to build_graph_payload")
        return {
            "nodes": [],
            "edges": [],
            "metadata": {"node_count": 0, "edge_count": 0}
        }
    
    # Get configurable sensitive fields
    sensitive_fields = set(get_config_value("response_formatter.sensitive_fields", ["embedding", "password", "secret"]))
    
    nodes = []
    edges = []
    node_ids = set()
    
    for row in primary_rows:
        if not isinstance(row, dict):
            continue
            
        # Extract node information
        node_id = row.get('id')
        if node_id and node_id not in node_ids:
            # Create safe node representation
            node = {
                "id": str(node_id),
                "labels": row.get('labels', []),
                "type": "node"
            }
            
            # Add safe properties (exclude sensitive fields)
            safe_properties = {}
            for key, value in row.items():
                if key not in sensitive_fields and key not in ['id', 'labels']:
                    safe_properties[key] = _serialize_value(value)
            
            if safe_properties:
                node["properties"] = safe_properties
            
            nodes.append(node)
            node_ids.add(node_id)
        
        # Extract edge information (if present)
        if 'relationship_type' in row and 'source_id' in row and 'target_id' in row:
            edge = {
                "source": str(row['source_id']),
                "target": str(row['target_id']),
                "type": str(row['relationship_type']),
                "id": f"{row['source_id']}-{row['relationship_type']}-{row['target_id']}"
            }
            edges.append(edge)
    
    metadata = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "primary_rows_count": len(primary_rows)
    }
    
    logger.info(f"Built graph payload: {metadata['node_count']} nodes, {metadata['edge_count']} edges")
    
    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": metadata
    }

def build_summary_prompt(question: str, rows: List[Dict[str, Any]], snippets: Dict[str, str] = None, allow_list: Dict[str, Any] = None) -> str:
    """
    Build a deterministic LLM prompt for generating structured summaries.
    
    This function creates a focused, deterministic prompt that instructs the LLM
    to generate a SummaryOutput with proper citations and structured data.
    The prompt is designed to be small and efficient to limit token usage.
    
    Args:
        question: The original user question
        rows: Query results to summarize
        snippets: Optional text snippets for additional context
        allow_list: Optional allow list for canonical ID validation
        
    Returns:
        Formatted prompt string for LLM processing
        
    Example:
        >>> prompt = build_summary_prompt("Who founded Apple?", [{"founder": "Steve Jobs"}])
        >>> "Question: Who founded Apple?\\n\\nData:\\n[{\"founder\": \"Steve Jobs\"}]\\n\\n..."
    """
    if not question:
        logger.warning("Empty question provided to build_summary_prompt")
        question = "No question provided"
    
    # Get config-driven limits
    max_table_rows = get_config_value("response_formatter.max_table_rows", 10)
    max_snippets = get_config_value("response_formatter.max_snippets", 5)
    max_snippet_length = get_config_value("response_formatter.max_snippet_length", 200)
    max_canonical_ids = get_config_value("response_formatter.max_canonical_ids", 10)
    max_prompt_length = get_config_value("response_formatter.max_prompt_length", 2000)
    
    # Normalize rows to table format
    table_data = rows_to_table(rows) if rows else []
    
    # Apply table truncation with audit logging
    if len(table_data) > max_table_rows:
        original_count = len(table_data)
        table_data = table_data[:max_table_rows]
        audit_store.record({
            "event": "prompt_truncated",
            "what": "table_rows",
            "original": original_count,
            "kept": max_table_rows
        })
        logger.info(f"Truncated table data from {original_count} to {max_table_rows} rows for prompt efficiency")
    
    # Build the prompt components
    prompt_parts = [
        "You are a helpful assistant that provides structured summaries of data.",
        "",
        f"Question: {question}",
        "",
        f"Data:\n{json.dumps(table_data, default=str, ensure_ascii=False)}"
    ]
    
    # Add snippets if available with truncation
    if snippets:
        snippet_items = list(snippets.items())[:max_snippets]
        if len(snippets) > max_snippets:
            audit_store.record({
                "event": "prompt_truncated",
                "what": "snippets",
                "original": len(snippets),
                "kept": max_snippets
            })
        
        snippet_text = "\\n".join([
            f"{node_id}: {text[:max_snippet_length]}..." if len(text) > max_snippet_length else f"{node_id}: {text}"
            for node_id, text in snippet_items
        ])
        prompt_parts.extend([
            "",
            "Additional Context:",
            snippet_text
        ])
    
    # Add canonical ID instruction with deterministic ordering
    canonical_ids = []
    if allow_list:
        canonical_ids.extend(allow_list.get('node_labels', []))
        canonical_ids.extend(allow_list.get('relationship_types', []))
    
    if canonical_ids:
        # Sort for deterministic ordering and limit
        canonical_ids = sorted(canonical_ids)[:max_canonical_ids]
        prompt_parts.extend([
            "",
            f"Canonical IDs to use in citations: {', '.join(canonical_ids)}"
        ])
    
    # Add JSON schema and instructions
    prompt_parts.extend([
        "",
        "Please provide a structured response in this exact JSON format:",
        "{",
        '  "summary": "Concise answer to the question",',
        '  "citations": ["canonical_id_1", "canonical_id_2"],',
        '  "table": [{"column1": "value1", "column2": "value2"}]',
        "}",
        "",
        "Instructions:",
        "- Use only canonical IDs from the provided list for citations",
        "- Keep summary concise but informative",
        "- Include relevant data in the table field",
        "- If no relevant data found, use empty arrays for citations and table"
    ])
    
    prompt = "\\n".join(prompt_parts)
    
    # Log prompt length for monitoring
    prompt_length = len(prompt)
    logger.info(f"Built summary prompt: {prompt_length} characters")
    
    if prompt_length > max_prompt_length:
        logger.warning(f"Prompt length ({prompt_length}) exceeds limit ({max_prompt_length})")
        audit_store.record({
            "event": "prompt_too_long",
            "length": prompt_length,
            "max": max_prompt_length
        })
    
    return prompt

def format_error_response(error_message: str, error_type: str = "general") -> Dict[str, Any]:
    """
    Format error responses in a consistent structure.
    
    Args:
        error_message: The error message to include
        error_type: Type of error (e.g., "validation", "execution", "general")
        
    Returns:
        Formatted error response dictionary
    """
    return {
        "error": True,
        "error_type": error_type,
        "message": error_message,
        "summary": f"Error occurred: {error_message}",
        "citations": [],
        "table": []
    }

def format_success_response(summary: str, citations: List[str] = None, table: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Format successful responses in a consistent structure.
    
    Args:
        summary: The summary text
        citations: List of citation IDs
        table: Table data
        
    Returns:
        Formatted success response dictionary
    """
    return {
        "error": False,
        "summary": summary,
        "citations": citations or [],
        "table": table or []
    }

def get_formatting_stats() -> Dict[str, Any]:
    """
    Get current formatting configuration and limits.
    
    Returns:
        Dictionary containing formatting configuration
    """
    return {
        "max_table_rows_in_prompt": get_config_value("response_formatter.max_table_rows", 10),
        "max_snippets_in_prompt": get_config_value("response_formatter.max_snippets", 5),
        "max_canonical_ids_in_prompt": get_config_value("response_formatter.max_canonical_ids", 10),
        "max_snippet_length": get_config_value("response_formatter.max_snippet_length", 200),
        "max_prompt_length": get_config_value("response_formatter.max_prompt_length", 2000),
        "sensitive_fields": get_config_value("response_formatter.sensitive_fields", ["embedding", "password", "secret"])
    }
