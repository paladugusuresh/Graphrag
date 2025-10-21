# graph_rag/ingest.py
import os
import glob
import yaml
from langchain.docstore.document import Document
from langchain.text_splitter import TokenTextSplitter
from graph_rag.neo4j_client import Neo4jClient
from graph_rag.embeddings import get_embedding_provider # Import the getter function
from graph_rag.observability import get_logger
from graph_rag.schema_manager import ensure_schema_loaded
from graph_rag.llm_client import call_llm_structured, LLMStructuredError
from graph_rag.config_manager import get_config_value
from pydantic import BaseModel
from graph_rag.cypher_generator import validate_label, validate_relationship_type, load_allow_list
from graph_rag.audit_store import audit_store
from graph_rag.flags import RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED

logger = get_logger(__name__)

# NOTE: Schema embeddings (SchemaTerm nodes) are managed by schema_manager/schema_embeddings
# at startup or via the admin endpoint. ingest.py must not create SchemaTerm nodes.

# enforce admin-only execution for writes
if os.getenv("APP_MODE", "read_only").lower() != "admin" and os.getenv("ALLOW_WRITES", "false").lower() not in ("1", "true", "yes"):
    raise RuntimeError("Ingest must be run with APP_MODE=admin or ALLOW_WRITES=true")

DATA_DIR = "data/"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 24

class ExtractedNode(BaseModel):
    id: str
    type: str

class ExtractedGraph(BaseModel):
    nodes: list[ExtractedNode] = []
    relationships: list[dict] = []

def parse_frontmatter(text: str):
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            meta = text[3:end]
            body = text[end+3:].strip()
            return yaml.safe_load(meta), body
    return {}, text

def process_and_ingest_files():
    audit_store.record({"event":"ingest.started", "timestamp": __import__("time").time()})
    logger.info("Ingest started (admin mode).")
    
    # Get canonical allow-list (idempotent). ensure_schema_loaded will write allow_list.json and stub in DEV_MODE.
    allow_list = ensure_schema_loaded(force=True)

    text_splitter = TokenTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    for path in glob.glob(os.path.join(DATA_DIR, "*.md")):
        with open(path, 'r', encoding='utf-8') as fh:
            content = fh.read()
        metadata, body = parse_frontmatter(content)
        if 'id' not in metadata:
            logger.warning(f"Skipping {path}: no id in frontmatter")
            continue
        doc_id = metadata['id']
        # Create Document
        client = Neo4jClient() # Instantiate Neo4jClient here
        try:
            client.execute_write_query("MERGE (d:Document {id: $id}) SET d += $props", {"id": doc_id, "props": metadata}, timeout=get_config_value('guardrails.neo4j_timeout', 10))
        except Exception as e:
            logger.error(f"Failed to create Document {doc_id}: {e}")
            audit_store.record({"event":"ingest.document_creation_failed", "doc_id": doc_id, "error": str(e)})
            continue
        
        doc = Document(page_content=body, metadata=metadata)
        chunks = text_splitter.split_documents([doc])
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}-chunk-{i}"
            try:
                # Create the chunk first
                client.execute_write_query(
                    "MATCH (d:Document {id: $id}) MERGE (c:Chunk {id: $chunk_id}) SET c.text = $text MERGE (d)-[:HAS_CHUNK]->(c)",
                    {"id": doc_id, "chunk_id": chunk_id, "text": chunk.page_content},
                    timeout=get_config_value('guardrails.neo4j_timeout', 10)
                )
                
                # Generate and persist chunk embedding if enabled
                if RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED():
                    try:
                        # Get embedding for the chunk content
                        embedding_provider = get_embedding_provider()
                        embeddings = embedding_provider.get_embeddings([chunk.page_content])
                        
                        if embeddings and len(embeddings) > 0:
                            embedding_vector = embeddings[0]
                            
                            # Update the chunk with the embedding
                            client.execute_write_query(
                                "MATCH (c:Chunk {id: $chunk_id}) SET c.embedding = $embedding",
                                {"chunk_id": chunk_id, "embedding": embedding_vector},
                                timeout=get_config_value('guardrails.neo4j_timeout', 10)
                            )
                            
                            logger.debug(f"Added embedding to chunk {chunk_id} (dimensions: {len(embedding_vector)})")
                        else:
                            logger.warning(f"Failed to generate embedding for chunk {chunk_id}")
                            audit_store.record({
                                "event": "ingest.chunk_embedding_failed",
                                "chunk_id": chunk_id,
                                "reason": "empty_embedding_result"
                            })
                    except Exception as embed_error:
                        logger.error(f"Failed to generate embedding for chunk {chunk_id}: {embed_error}")
                        audit_store.record({
                            "event": "ingest.chunk_embedding_failed",
                            "chunk_id": chunk_id,
                            "error": str(embed_error)
                        })
                        # Continue processing - embedding failure shouldn't stop ingestion
                
            except Exception as e:
                logger.error(f"Failed to create Chunk {chunk_id}: {e}")
                audit_store.record({"event":"ingest.chunk_creation_failed", "chunk_id": chunk_id, "doc_id": doc_id, "error": str(e)})
                continue
            # Ask LLM to extract graph for chunk - MUST be structured
            prompt = f"Extract nodes and relationships as JSON for the text:\n\n{chunk.page_content[:1000]}"
            try:
                # In production, schema_model would be a Pydantic model; here we just call raw for dev
                g = call_llm_structured(prompt, ExtractedGraph)
                # ingest nodes safely: validate label against allow-list via cypher_generator
                for node in g.nodes:
                    try:
                        validated_label = validate_label(node.type, allow_list)
                        client.execute_write_query(f"MERGE (n:{validated_label} {{id: $id}})", {"id": node.id}, timeout=get_config_value('guardrails.neo4j_timeout', 10))
                        client.execute_write_query("MATCH (c:Chunk {id:$cid}) MATCH (e {id:$eid}) MERGE (c)-[:MENTIONS]->(e)", {"cid": chunk_id, "eid": node.id}, timeout=get_config_value('guardrails.neo4j_timeout', 10))
                    except Exception as db_error:
                        logger.error(f"DB write failed for node {node.id} in chunk {chunk_id}: {db_error}")
                        audit_store.record({"event":"ingest.db_write_failed", "chunk_id": chunk_id, "node_id": node.id, "error": str(db_error)})
                        # Continue with next node
                        continue
            except LLMStructuredError as e:
                logger.error(f"LLM extraction failed for chunk {chunk_id}: {e}")
                audit_store.record({"event":"ingest.llm_extraction_failed", "chunk_id": chunk_id, "error": str(e)})
                # Continue with next chunk
                continue
            except Exception as e:
                logger.exception(f"Unexpected ingest error for chunk {chunk_id}: {e}")
                audit_store.record({"event":"ingest.chunk_failed", "chunk_id": chunk_id, "error": str(e)})
                # Continue with next chunk
                continue
    
    audit_store.record({"event":"ingest.completed", "timestamp": __import__("time").time()})
    logger.info("Ingest completed.")
