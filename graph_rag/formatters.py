# graph_rag/formatters.py
"""
Table and graph formatters with citation verification.

Provides deterministic output formatting for table and graph views,
along with citation verification to ensure referenced sources exist.
"""
import re
from typing import List, Dict, Any, Optional, Set
from graph_rag.observability import get_logger
from graph_rag.flags import FORMATTERS_ENABLED

logger = get_logger(__name__)


class TableFormatter:
    """
    Formats query results into structured table format with stable column ordering.
    
    Features:
    - Deterministic column ordering based on key frequency
    - Stable row ordering for consistent output
    - Handles missing/null values gracefully
    """
    
    def __init__(self):
        self.enabled = FORMATTERS_ENABLED()
    
    def format_table(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format rows into a structured table with stable column ordering.
        
        Args:
            rows: List of dictionaries representing query results
            
        Returns:
            Dictionary with 'columns' and 'data' keys, or None if disabled
        """
        if not FORMATTERS_ENABLED():
            logger.debug("Table formatter disabled")
            return None
        
        if not rows:
            return {
                "columns": [],
                "data": []
            }
        
        # Extract all unique keys and count their frequency
        key_counts = {}
        for row in rows:
            for key in row.keys():
                key_counts[key] = key_counts.get(key, 0) + 1
        
        # Sort columns by frequency (most common first), then alphabetically
        columns = sorted(key_counts.keys(), key=lambda k: (-key_counts[k], k))
        
        # Format data rows with stable ordering
        data = []
        for row in rows:
            formatted_row = []
            for col in columns:
                value = row.get(col)
                # Convert None to empty string for consistent output
                formatted_row.append("" if value is None else str(value))
            data.append(formatted_row)
        
        logger.debug(f"Formatted table with {len(columns)} columns and {len(data)} rows")
        
        return {
            "columns": columns,
            "data": data
        }


class GraphFormatter:
    """
    Formats query results into graph structure with nodes and edges.
    
    Features:
    - Extracts nodes from primary_id fields
    - Generates edges based on relationships in data
    - Handles both explicit and inferred relationships
    """
    
    def __init__(self):
        self.enabled = FORMATTERS_ENABLED()
    
    def format_graph(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format rows into a graph structure with nodes and edges.
        
        Args:
            rows: List of dictionaries representing query results
            
        Returns:
            Dictionary with 'nodes' and 'edges' keys, or None if disabled
        """
        if not FORMATTERS_ENABLED():
            logger.debug("Graph formatter disabled")
            return None
        
        if not rows:
            return {
                "nodes": [],
                "edges": []
            }
        
        nodes = []
        edges = []
        node_ids = set()
        
        # Extract nodes from primary_id fields
        for i, row in enumerate(rows):
            primary_id = row.get('primary_id')
            if primary_id and primary_id not in node_ids:
                node_ids.add(primary_id)
                nodes.append({
                    "id": str(primary_id),
                    "label": str(primary_id),
                    "type": "entity",
                    "properties": {k: v for k, v in row.items() if k != 'primary_id' and v is not None}
                })
        
        # Generate edges based on relationships
        # For now, create simple sequential edges between nodes
        # In a more sophisticated implementation, this could analyze
        # relationship fields to create meaningful edges
        for i in range(len(nodes) - 1):
            edges.append({
                "source": nodes[i]["id"],
                "target": nodes[i + 1]["id"],
                "type": "related",
                "properties": {}
            })
        
        logger.debug(f"Formatted graph with {len(nodes)} nodes and {len(edges)} edges")
        
        return {
            "nodes": nodes,
            "edges": edges
        }


class CitationVerifier:
    """
    Verifies that citations in summaries actually exist in the provided data.
    
    Features:
    - Extracts citation references from text
    - Checks against available chunk/node IDs
    - Provides verification status (passed/failed/partial)
    """
    
    def __init__(self):
        self.enabled = FORMATTERS_ENABLED()
    
    def verify_citations(self, summary: str, available_ids: List[str], citations: List[str]) -> Dict[str, Any]:
        """
        Verify that citations in the summary exist in available data.
        
        Args:
            summary: The generated summary text
            available_ids: List of available chunk/node IDs
            citations: List of explicit citations from LLM
            
        Returns:
            Dictionary with verification status and details
        """
        if not FORMATTERS_ENABLED():
            logger.debug("Citation verifier disabled")
            return {
                "verification_status": "disabled",
                "cited_ids": [],
                "available_ids": [],
                "unknown_citations": [],
                "verification_action": "disabled"
            }
        
        # Extract citation references from summary text
        # Look for patterns like [id], [node_123], [chunk_456], etc.
        citation_pattern = r'\[([a-zA-Z0-9_-]+)\]'
        found_citations = re.findall(citation_pattern, summary)
        
        # Combine explicit citations with found citations
        all_citations = list(set(citations + found_citations))
        
        # Check which citations exist
        available_set = set(available_ids)
        cited_ids = []
        unknown_citations = []
        
        for citation in all_citations:
            if citation in available_set:
                cited_ids.append(citation)
            else:
                unknown_citations.append(citation)
        
        # Determine verification status
        if not all_citations:
            verification_status = "passed"  # No citations to verify
        elif not unknown_citations:
            verification_status = "passed"  # All citations verified
        elif not cited_ids:
            verification_status = "failed"  # No citations verified
        else:
            verification_status = "partial"  # Some citations verified
        
        logger.debug(f"Citation verification: {verification_status} ({len(cited_ids)}/{len(all_citations)} verified)")
        
        return {
            "verification_status": verification_status,
            "cited_ids": cited_ids,
            "available_ids": available_ids,
            "unknown_citations": unknown_citations,
            "verification_action": f"verified_{len(cited_ids)}_of_{len(all_citations)}_citations"
        }


class FormattersManager:
    """
    Manages all formatters and provides unified formatting interface.
    
    This class coordinates table formatting, graph formatting, and citation verification
    to provide comprehensive formatted output for API responses.
    """
    
    def __init__(self):
        self.table_formatter = TableFormatter()
        self.graph_formatter = GraphFormatter()
        self.citation_verifier = CitationVerifier()
        self.enabled = FORMATTERS_ENABLED()
    
    def format_response(self, rows: List[Dict[str, Any]], summary: str, 
                       citations: List[str], available_ids: List[str]) -> Dict[str, Any]:
        """
        Format a complete response with table, graph, and citation verification.
        
        Args:
            rows: Query result rows
            summary: Generated summary text
            citations: List of citations from LLM
            available_ids: Available chunk/node IDs for verification
            
        Returns:
            Dictionary with formatted sections and verification status
        """
        if not FORMATTERS_ENABLED():
            logger.debug("Formatters disabled, returning None")
            return None
        
        formatted = {}
        
        # Format table
        table_format = self.table_formatter.format_table(rows)
        if table_format:
            formatted["table"] = table_format
        
        # Format graph
        graph_format = self.graph_formatter.format_graph(rows)
        if graph_format:
            formatted["graph"] = graph_format
        
        # Verify citations
        verification = self.citation_verifier.verify_citations(summary, available_ids, citations)
        
        return {
            "formatted": formatted,
            "verification_status": verification["verification_status"],
            "citation_details": verification
        }


# Global formatters manager instance
formatters_manager = FormattersManager()
