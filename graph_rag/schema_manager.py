# graph_rag/schema_manager.py
"""
Schema management module for handling schema extraction, fingerprinting, and allow-list persistence.
This module serves as the Pipeline 1 center for schema operations.
"""
import json
import hashlib
import os
from typing import Dict, Any, Optional
from graph_rag.observability import get_logger
from graph_rag.config_manager import get_config_value
from graph_rag.dev_stubs import is_dev_mode
from graph_rag.flags import RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED

logger = get_logger(__name__)


def _is_write_allowed() -> bool:
    """
    Check if schema writes are allowed based on APP_MODE and ALLOW_WRITES env vars.
    
    Write operations are allowed if:
    - APP_MODE=admin, OR
    - ALLOW_WRITES=true
    
    Returns:
        True if writes are allowed, False otherwise
    """
    app_mode = os.getenv("APP_MODE", "read_only").lower()
    allow_writes = os.getenv("ALLOW_WRITES", "false").lower()
    
    is_admin = app_mode == "admin"
    writes_enabled = allow_writes in ("true", "1", "yes", "on")
    
    return is_admin or writes_enabled

def _compute_fingerprint(allow_list: Dict[str, Any]) -> str:
    """Compute SHA256 fingerprint of canonical JSON representation of allow list."""
    # Create canonical JSON representation (sorted keys for consistency)
    canonical_json = json.dumps(allow_list, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

def _read_fingerprint(fingerprint_path: str) -> str:
    """Read existing fingerprint from file, return empty string if not found."""
    try:
        if os.path.exists(fingerprint_path):
            with open(fingerprint_path, 'r') as f:
                return f.read().strip()
    except Exception as e:
        logger.warning(f"Failed to read fingerprint file {fingerprint_path}: {e}")
    return ""

def _write_fingerprint(fingerprint: str, fingerprint_path: str) -> None:
    """Write fingerprint to file."""
    try:
        with open(fingerprint_path, 'w') as f:
            f.write(fingerprint)
        logger.debug(f"Schema fingerprint written to {fingerprint_path}")
    except Exception as e:
        logger.error(f"Failed to write fingerprint file {fingerprint_path}: {e}")
        raise


def get_schema_fingerprint() -> Optional[str]:
    """
    Get the current schema fingerprint from the live database.
    
    This computes a fingerprint from the current allow list to detect schema changes.
    Used for idempotent schema ingestion and testing.
    
    Returns:
        SHA256 fingerprint of the current schema, or None if schema extraction fails
    """
    try:
        from graph_rag.schema_catalog import generate_schema_allow_list
        # Generate schema without writing to disk
        allow_list = generate_schema_allow_list(allow_list_path=None, write_to_disk=False)
        return _compute_fingerprint(allow_list)
    except Exception as e:
        logger.error(f"Failed to compute schema fingerprint: {e}")
        return None

def ensure_schema_loaded(force: bool = False) -> Dict[str, Any]:
    """
    Ensure schema allow-list is loaded and up-to-date.
    
    This function implements idempotent schema ingestion with write guards:
    - Only performs writes if APP_MODE=admin or ALLOW_WRITES=true
    - Uses fingerprinting to skip regeneration if schema unchanged
    - In read-only mode, only loads existing allow-list
    
    Args:
        force: If True, regenerate schema even if fingerprint hasn't changed
        
    Returns:
        Dict containing the allow-list (node_labels, relationship_types, properties)
        
    Raises:
        RuntimeError: If schema generation fails and not in DEV_MODE
        FileNotFoundError: If allow-list doesn't exist in read-only mode
    """
    allow_list_path = get_config_value('schema.allow_list_path', 'allow_list.json')
    fingerprint_path = '.schema_fingerprint'
    
    # Check write permissions
    write_allowed = _is_write_allowed()
    
    if not write_allowed:
        # Read-only mode: only load existing allow-list
        logger.info("Running in read-only mode, loading existing allow-list")
        if not os.path.exists(allow_list_path):
            error_msg = f"Allow-list file not found: {allow_list_path}. Schema writes require APP_MODE=admin or ALLOW_WRITES=true"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        with open(allow_list_path, 'r') as f:
            existing_allow_list = json.load(f)
        logger.info(f"Loaded existing allow-list with {len(existing_allow_list.get('node_labels', []))} labels")
        return existing_allow_list
    
    # Write mode: check if we need to regenerate schema
    if not force:
        try:
            # Read existing allow list
            if os.path.exists(allow_list_path):
                with open(allow_list_path, 'r') as f:
                    existing_allow_list = json.load(f)
                
                # Check fingerprint
                existing_fingerprint = _read_fingerprint(fingerprint_path)
                current_fingerprint = _compute_fingerprint(existing_allow_list)
                
                if existing_fingerprint == current_fingerprint:
                    logger.info("Schema fingerprint unchanged, skipping regeneration")
                    return existing_allow_list
                else:
                    logger.info("Schema fingerprint changed, regenerating allow list")
            else:
                logger.info("Allow list file not found, generating new schema")
        except Exception as e:
            logger.warning(f"Failed to check existing schema: {e}, proceeding with regeneration")
    else:
        logger.info("Force refresh requested, regenerating schema")
    
    # Generate new schema allow list
    try:
        logger.info("Generating schema allow list from database")
        from graph_rag.schema_catalog import generate_schema_allow_list
        allow_list = generate_schema_allow_list(allow_list_path)
        
        # Compute and write fingerprint
        fingerprint = _compute_fingerprint(allow_list)
        _write_fingerprint(fingerprint, fingerprint_path)
        
        logger.info(f"Schema allow list generated successfully with {len(allow_list.get('node_labels', []))} labels and {len(allow_list.get('relationship_types', []))} relationship types")
        return allow_list
        
    except Exception as e:
        error_msg = f"Failed to generate schema allow list: {e}"
        logger.error(error_msg)
        
        # In DEV_MODE, create a stub allow list instead of failing
        if is_dev_mode():
            logger.warning("Running in DEV_MODE, creating stub allow list")
            stub_allow_list = {
                "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
                "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_PRODUCT"],
                "properties": {}
            }
            
            try:
                with open(allow_list_path, 'w') as f:
                    json.dump(stub_allow_list, f, indent=2)
                logger.info(f"Stub allow list written to {allow_list_path}")
                
                # Write fingerprint for stub
                fingerprint = _compute_fingerprint(stub_allow_list)
                _write_fingerprint(fingerprint, fingerprint_path)
                
                return stub_allow_list
            except Exception as stub_error:
                logger.error(f"Failed to create stub allow list: {stub_error}")
                raise RuntimeError(f"Could not create stub allow list: {stub_error}")
        else:
            # In production mode, re-raise the original error
            raise RuntimeError(error_msg)

def get_allow_list() -> Dict[str, Any]:
    """
    Get the current allow list from allow_list.json.
    
    Returns:
        Dict containing the allow-list (node_labels, relationship_types, properties)
        
    Raises:
        FileNotFoundError: If allow_list.json doesn't exist
        json.JSONDecodeError: If allow_list.json is malformed
    """
    allow_list_path = get_config_value('schema.allow_list_path', 'allow_list.json')
    
    if not os.path.exists(allow_list_path):
        raise FileNotFoundError(f"Allow list file not found: {allow_list_path}. Run ensure_schema_loaded() first.")
    
    try:
        with open(allow_list_path, 'r') as f:
            allow_list = json.load(f)
        
        logger.debug(f"Allow list loaded from {allow_list_path}")
        return allow_list
        
    except json.JSONDecodeError as e:
        logger.error(f"Malformed JSON in allow list file {allow_list_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to read allow list file {allow_list_path}: {e}")
        raise


def _get_embedding_dimensions() -> Optional[int]:
    """
    Get embedding dimensions from the embedding provider.
    
    Returns:
        Number of dimensions for embeddings, or None if unable to determine
    """
    try:
        from graph_rag.embeddings import get_embedding_provider
        
        # Get a test embedding to determine dimensions
        provider = get_embedding_provider()
        test_embeddings = provider.get_embeddings(["test"])
        
        if test_embeddings and len(test_embeddings) > 0:
            dimensions = len(test_embeddings[0])
            logger.debug(f"Detected embedding dimensions: {dimensions}")
            return dimensions
        else:
            logger.warning("Failed to get test embedding for dimension detection")
            return None
            
    except Exception as e:
        logger.error(f"Failed to detect embedding dimensions: {e}")
        return None


def _check_chunk_vector_index_exists() -> bool:
    """
    Check if the chunk_embeddings vector index exists and is online.
    
    Returns:
        True if index exists and is online, False otherwise
    """
    try:
        from graph_rag.neo4j_client import Neo4jClient
        
        client = Neo4jClient()
        
        # Query to check for existing vector index
        query = """
        SHOW INDEXES 
        WHERE type = 'VECTOR' 
        AND name = 'chunk_embeddings'
        AND state = 'ONLINE'
        """
        
        results = client.execute_read_query(query, query_name="check_chunk_vector_index")
        
        # Check if we found an online vector index
        exists = len(results) > 0
        logger.debug(f"Chunk vector index exists and online: {exists}")
        
        return exists
        
    except Exception as e:
        logger.error(f"Failed to check chunk vector index existence: {e}")
        return False


def _create_chunk_vector_index(dimensions: int) -> bool:
    """
    Create the chunk_embeddings vector index with HNSW algorithm.
    
    Args:
        dimensions: Number of dimensions for the vector index
        
    Returns:
        True if index creation succeeded, False otherwise
    """
    try:
        from graph_rag.neo4j_client import Neo4jClient
        
        client = Neo4jClient()
        
        # Create vector index with HNSW algorithm
        query = f"""
        CREATE VECTOR INDEX chunk_embeddings 
        FOR (c:Chunk) ON (c.embedding) 
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {dimensions},
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
        
        logger.info(f"Creating chunk vector index with {dimensions} dimensions")
        results = client.execute_write_query(query, query_name="create_chunk_vector_index")
        
        logger.info("Chunk vector index creation initiated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create chunk vector index: {e}")
        return False


def ensure_chunk_vector_index() -> bool:
    """
    Ensure chunk vector index exists and is online.
    
    This function:
    1. Checks if RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED is true (skip if false)
    2. Detects embedding dimensions from provider
    3. Checks if index already exists and is online
    4. Creates index if it doesn't exist
    
    Returns:
        True if index exists/created successfully, False otherwise
    """
    # Check if chunk embeddings are enabled
    if not RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED():
        logger.debug("Chunk embeddings disabled, skipping vector index creation")
        return True  # Not an error, just skipped
    
    # Check write permissions
    if not _is_write_allowed():
        logger.warning("Write operations not allowed, cannot create vector index")
        return False
    
    # Check if index already exists
    if _check_chunk_vector_index_exists():
        logger.info("Chunk vector index already exists and is online")
        return True
    
    # Detect embedding dimensions
    dimensions = _get_embedding_dimensions()
    if dimensions is None:
        logger.error("Cannot determine embedding dimensions, skipping vector index creation")
        return False
    
    # Create the index
    success = _create_chunk_vector_index(dimensions)
    if success:
        logger.info(f"Chunk vector index creation completed with {dimensions} dimensions")
    else:
        logger.error("Failed to create chunk vector index")
    
    return success
