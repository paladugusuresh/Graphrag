# graph_rag/rag_augmentor.py
"""
GraphRAG augmentation module for enriching query results with graph context.
Provides bounded neighbor fetching and snippet extraction for enhanced retrieval.
"""
from typing import List, Dict, Any, Optional
from graph_rag.observability import get_logger
from graph_rag.config_manager import get_config_value
from graph_rag.neo4j_client import Neo4jClient

logger = get_logger(__name__)

def augment_results(primary_ids: List[str], max_neighbors: int = None) -> Dict[str, Any]:
    """
    Augment primary results with adjacent nodes and text snippets from the graph.
    
    This function enriches query results by fetching bounded neighbors of primary nodes,
    providing additional context for RAG applications. It returns node information
    including labels, IDs, and text snippets where available.
    
    Args:
        primary_ids: List of primary node IDs to augment with neighbors
        max_neighbors: Maximum number of neighbors to fetch per primary node (default from config)
        
    Returns:
        Dictionary containing:
        - primary_ids: Original list of primary node IDs
        - neighbors: List of neighbor node dictionaries with id, labels, text snippets
        - total_neighbors: Total number of neighbors found
        - truncated: Boolean indicating if results were truncated
        
    Example:
        >>> augment_results(["node_123", "node_456"], max_neighbors=5)
        {
            "primary_ids": ["node_123", "node_456"],
            "neighbors": [
                {"id": "neighbor_1", "labels": ["Person"], "text": "Sample text..."},
                {"id": "neighbor_2", "labels": ["Document"], "text": "Document content..."}
            ],
            "total_neighbors": 2,
            "truncated": False
        }
    """
    if not primary_ids:
        logger.warning("Empty primary_ids list provided to augment_results")
        return {
            "primary_ids": [],
            "neighbors": [],
            "total_neighbors": 0,
            "truncated": False
        }
    
    # Get configuration values
    if max_neighbors is None:
        max_neighbors = get_config_value('rag.max_neighbors', 5)
    
    max_snippet_length = get_config_value('rag.max_snippet_length', 500)
    query_timeout = get_config_value('guardrails.query_timeout', 30)
    
    logger.info(f"Augmenting {len(primary_ids)} primary nodes with up to {max_neighbors} neighbors each")
    
    try:
        # Initialize Neo4j client
        neo4j_client = Neo4jClient()
        
        # Build parameterized Cypher query to fetch neighbors
        # This query:
        # 1. Finds nodes matching primary_ids
        # 2. Fetches their neighbors (bounded by max_neighbors)
        # 3. Returns neighbor info conservatively (id, labels, text snippet only)
        cypher_query = """
        UNWIND $primary_ids AS primary_id
        MATCH (primary)
        WHERE primary.id = primary_id
        CALL {
            WITH primary
            MATCH (primary)-[r]-(neighbor)
            RETURN neighbor
            LIMIT $max_neighbors
        }
        WITH DISTINCT neighbor
        RETURN 
            neighbor.id AS id,
            labels(neighbor) AS labels,
            CASE 
                WHEN neighbor.text IS NOT NULL THEN substring(neighbor.text, 0, $max_snippet_length)
                WHEN neighbor.content IS NOT NULL THEN substring(neighbor.content, 0, $max_snippet_length)
                ELSE NULL
            END AS text
        LIMIT $total_limit
        """
        
        # Calculate total limit to prevent excessive results
        total_limit = len(primary_ids) * max_neighbors
        
        # Execute query with parameters to prevent injection
        params = {
            "primary_ids": primary_ids,
            "max_neighbors": max_neighbors,
            "max_snippet_length": max_snippet_length,
            "total_limit": total_limit
        }
        
        logger.debug(f"Executing neighbor query with params: primary_ids count={len(primary_ids)}, max_neighbors={max_neighbors}")
        
        results = neo4j_client.execute_read_query(
            query=cypher_query,
            params=params,
            timeout=query_timeout,
            query_name="rag_augmentation"
        )
        
        # Process results conservatively
        neighbors = []
        for record in results:
            neighbor_data = {
                "id": record.get("id"),
                "labels": record.get("labels", []),
                "text": record.get("text")
            }
            
            # Only include neighbors with valid IDs
            if neighbor_data["id"]:
                neighbors.append(neighbor_data)
        
        # Determine if results were truncated
        truncated = len(neighbors) >= total_limit
        
        logger.info(f"Augmentation complete: found {len(neighbors)} neighbors for {len(primary_ids)} primary nodes")
        
        if truncated:
            logger.warning(f"Results truncated at {total_limit} neighbors")
        
        return {
            "primary_ids": primary_ids,
            "neighbors": neighbors,
            "total_neighbors": len(neighbors),
            "truncated": truncated
        }
        
    except Exception as e:
        error_msg = f"Error during augmentation: {str(e)}"
        logger.error(error_msg)
        
        # Return empty results on error to prevent downstream failures
        return {
            "primary_ids": primary_ids,
            "neighbors": [],
            "total_neighbors": 0,
            "truncated": False,
            "error": str(e)
        }

def get_node_snippets(node_ids: List[str], max_snippet_length: int = None) -> Dict[str, str]:
    """
    Fetch text snippets for specific node IDs.
    
    This is a lightweight function to retrieve only text content for known node IDs,
    useful for getting additional context without full neighbor traversal.
    
    Args:
        node_ids: List of node IDs to fetch snippets for
        max_snippet_length: Maximum length of text snippets (default from config)
        
    Returns:
        Dictionary mapping node IDs to their text snippets
    """
    if not node_ids:
        logger.warning("Empty node_ids list provided to get_node_snippets")
        return {}
    
    if max_snippet_length is None:
        max_snippet_length = get_config_value('rag.max_snippet_length', 500)
    
    query_timeout = get_config_value('guardrails.query_timeout', 30)
    
    try:
        neo4j_client = Neo4jClient()
        
        # Parameterized query to fetch snippets
        cypher_query = """
        UNWIND $node_ids AS node_id
        MATCH (n)
        WHERE n.id = node_id
        RETURN 
            n.id AS id,
            CASE 
                WHEN n.text IS NOT NULL THEN substring(n.text, 0, $max_snippet_length)
                WHEN n.content IS NOT NULL THEN substring(n.content, 0, $max_snippet_length)
                ELSE NULL
            END AS text
        """
        
        params = {
            "node_ids": node_ids,
            "max_snippet_length": max_snippet_length
        }
        
        results = neo4j_client.execute_read_query(
            query=cypher_query,
            params=params,
            timeout=query_timeout,
            query_name="snippet_fetch"
        )
        
        # Build dictionary mapping node IDs to snippets
        snippets = {}
        for record in results:
            node_id = record.get("id")
            text = record.get("text")
            if node_id and text:
                snippets[node_id] = text
        
        logger.info(f"Fetched {len(snippets)} snippets for {len(node_ids)} node IDs")
        
        return snippets
        
    except Exception as e:
        logger.error(f"Error fetching snippets: {str(e)}")
        return {}

def get_augmentation_stats() -> Dict[str, Any]:
    """
    Get current augmentation configuration and limits.
    
    Returns:
        Dictionary containing augmentation configuration
    """
    return {
        "max_neighbors": get_config_value('rag.max_neighbors', 5),
        "max_snippet_length": get_config_value('rag.max_snippet_length', 500),
        "query_timeout": get_config_value('guardrails.query_timeout', 30)
    }
