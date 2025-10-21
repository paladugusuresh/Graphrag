# graph_rag/schema_embeddings.py
import json
import os
from typing import List, Dict, Any
from graph_rag.observability import get_logger
from graph_rag.embeddings import get_embedding_provider
from graph_rag.neo4j_client import Neo4jClient
from graph_rag.config_manager import get_config, get_config_value

logger = get_logger(__name__)

def collect_schema_terms() -> List[Dict[str, Any]]:
    """
    Extract schema terms from allow_list.json and optionally from schema_synonyms.json.
    
    Returns:
        List of dicts with schema term information:
        [{"id": "<type>:<term>", "term": "<term>", "type": "label|relationship|property", "canonical_id": "<term>"}]
    """
    # Load configuration at runtime
    allow_list_path = get_config_value('schema.allow_list_path', 'allow_list.json')
    try:
        with open(allow_list_path, 'r') as f:
            allow_list = json.load(f)
    except FileNotFoundError:
        logger.error(f"Allow list file not found: {allow_list_path}")
        return []
    
    terms = []
    
    # Extract node labels
    for label in allow_list.get('node_labels', []):
        terms.append({
            "id": f"label:{label}",
            "term": label,
            "type": "label",
            "canonical_id": label
        })
    
    # Extract relationship types
    for rel_type in allow_list.get('relationship_types', []):
        terms.append({
            "id": f"relationship:{rel_type}",
            "term": rel_type,
            "type": "relationship",
            "canonical_id": rel_type
        })
    
    # Extract property keys
    properties = allow_list.get('properties', {})
    unique_properties = set()
    for node_props in properties.values():
        unique_properties.update(node_props)
    
    for prop in unique_properties:
        terms.append({
            "id": f"property:{prop}",
            "term": prop,
            "type": "property",
            "canonical_id": prop
        })
    
    # Load synonyms if available
    from graph_rag.schema_manager import load_synonyms_optional
    synonyms = load_synonyms_optional("config/synonyms.json")
    
    if synonyms:
        # Add synonyms for existing terms
        for term_data in terms[:]:  # Create copy to avoid modifying during iteration
            canonical_id = term_data['canonical_id']
            term_type = term_data['type']
            
            # Map term_type to synonyms structure
            synonyms_key = 'labels' if term_type == 'label' else 'relationships' if term_type == 'relationship' else 'properties'
            
            # Check if this term has synonyms
            if canonical_id in synonyms.get(synonyms_key, {}):
                for synonym in synonyms[synonyms_key][canonical_id]:
                    terms.append({
                        "id": f"{term_type}:{synonym}",
                        "term": synonym,
                        "type": term_type,
                        "canonical_id": canonical_id  # Points to the original term
                    })
        
        logger.info(f"Loaded synonyms from config/synonyms.json")
    
    logger.info(f"Collected {len(terms)} schema terms ({len([t for t in terms if t['term'] == t['canonical_id']])} canonical + {len([t for t in terms if t['term'] != t['canonical_id']])} synonyms)")
    return terms

def compute_embeddings(terms: List[str]) -> List[List[float]]:
    """
    Compute embeddings for a list of terms using the configured embedding provider.
    
    Args:
        terms: List of term strings to embed
        
    Returns:
        List of embedding vectors (one per term)
    """
    if not terms:
        return []
    
    try:
        embedding_provider = get_embedding_provider()
        embeddings = embedding_provider.get_embeddings(terms)
        logger.info(f"Computed embeddings for {len(terms)} terms")
        return embeddings
    except Exception as e:
        logger.error(f"Failed to compute embeddings: {e}")
        return []

def generate_schema_embeddings() -> List[Dict[str, Any]]:
    """
    Generate complete schema embeddings by collecting terms and computing embeddings.
    
    Returns:
        List of dicts with term info and embeddings:
        [{"id": "<type>:<term>", "term": "<term>", "type": "label|relationship|property", 
          "canonical_id": "<canonical>", "embedding": [...]}]
    """
    # Collect schema terms
    terms_data = collect_schema_terms()
    if not terms_data:
        logger.warning("No schema terms collected")
        return []
    
    # Extract just the term strings for embedding
    term_strings = [term_data['term'] for term_data in terms_data]
    
    # Compute embeddings
    embeddings = compute_embeddings(term_strings)
    if len(embeddings) != len(term_strings):
        logger.error(f"Mismatch: {len(term_strings)} terms but {len(embeddings)} embeddings")
        return []
    
    # Combine term data with embeddings
    result = []
    for term_data, embedding in zip(terms_data, embeddings):
        result.append({
            **term_data,
            "embedding": embedding
        })
    
    logger.info(f"Generated schema embeddings for {len(result)} terms")
    return result

def upsert_schema_embeddings() -> Dict[str, Any]:
    """
    Upsert schema embeddings into Neo4j as SchemaTerm nodes and create vector index.
    
    Returns:
        Dict with operation results and statistics
    """
    # Get configuration at runtime
    timeout = get_config_value('guardrails.neo4j_timeout', 10)
    index_name = get_config_value('schema_embeddings.index_name', 'schema_embeddings')
    node_label = get_config_value('schema_embeddings.node_label', 'SchemaTerm')
    
    # Generate schema embeddings
    schema_data = generate_schema_embeddings()
    if not schema_data:
        logger.warning("No schema embeddings generated")
        return {"status": "skipped", "reason": "no_embeddings", "nodes_created": 0}
    
    # Initialize Neo4j client
    neo4j_client = Neo4jClient()
    
    # Upsert schema term nodes
    nodes_created = 0
    nodes_updated = 0
    
    logger.info(f"Upserting {len(schema_data)} schema term nodes...")
    
    for term_data in schema_data:
        # Validate required fields
        if not all(key in term_data for key in ['id', 'term', 'type', 'embedding']):
            logger.warning(f"Skipping term with missing fields: {term_data}")
            continue
        
        # Prepare parameters for Cypher query
        params = {
            'id': term_data['id'],
            'term': term_data['term'],
            'type': term_data['type'],
            'canonical_id': term_data.get('canonical_id', term_data['term']),
            'embedding': term_data['embedding']
        }
        
        # Parameterized MERGE query
        cypher_query = """
        MERGE (s:SchemaTerm {id: $id})
        SET s.term = $term, 
            s.type = $type, 
            s.canonical_id = $canonical_id,
            s.embedding = $embedding,
            s.updated_at = datetime()
        RETURN s.id as id, 
               CASE WHEN s.created_at IS NULL THEN 'created' ELSE 'updated' END as operation
        """
        
        try:
            result = neo4j_client.execute_write_query(
                cypher_query, 
                params, 
                timeout=timeout,
                query_name="upsert_schema_term"
            )
            
            if result and len(result) > 0:
                operation = result[0].get('operation', 'unknown')
                if operation == 'created':
                    nodes_created += 1
                else:
                    nodes_updated += 1
                    
        except Exception as e:
            logger.error(f"Failed to upsert schema term {term_data['id']}: {e}")
            continue
    
    logger.info(f"Schema term upsert complete: {nodes_created} created, {nodes_updated} updated")
    
    # Create vector index
    try:
        # Get embedding dimensions from first embedding
        embedding_dim = len(schema_data[0]['embedding']) if schema_data else 1536
        
        # Create vector index with parameterized query
        index_query = f"""
        CREATE VECTOR INDEX `{index_name}` IF NOT EXISTS 
        FOR (s:SchemaTerm) ON (s.embedding) 
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {embedding_dim}, 
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
        
        neo4j_client.execute_write_query(
            index_query, 
            {}, 
            timeout=timeout,
            query_name="create_schema_vector_index"
        )
        
        logger.info(f"Vector index '{index_name}' created/verified with {embedding_dim} dimensions")
        index_status = "created_or_verified"
        
    except Exception as e:
        logger.error(f"Failed to create vector index '{index_name}': {e}")
        index_status = "failed"
    
    return {
        "status": "completed",
        "nodes_created": nodes_created,
        "nodes_updated": nodes_updated,
        "total_terms": len(schema_data),
        "index_name": index_name,
        "index_status": index_status,
        "embedding_dimensions": embedding_dim
    }

# CLI entry point
if __name__ == "__main__":
    print("=== Schema Embeddings Upsert ===")
    result = upsert_schema_embeddings()
    print(f"Result: {result}")
    
    if result["status"] == "completed":
        print(f"✅ Successfully processed {result['total_terms']} schema terms")
        print(f"   - Created: {result['nodes_created']} nodes")
        print(f"   - Updated: {result['nodes_updated']} nodes")
        print(f"   - Index: {result['index_name']} ({result['index_status']})")
    else:
        print(f"⚠️  Operation {result['status']}: {result.get('reason', 'unknown')}")
