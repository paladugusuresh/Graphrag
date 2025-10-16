# graph_rag/ingest.py
import os
import glob
import yaml
from langchain.docstore.document import Document
from langchain.text_splitter import TokenTextSplitter
from graph_rag.neo4j_client import Neo4jClient
from graph_rag.embeddings import get_embedding_provider # Import the getter function
from graph_rag.observability import get_logger
from graph_rag.schema_catalog import generate_schema_allow_list
from graph_rag.llm_client import call_llm_structured, LLMStructuredError
from graph_rag.config_manager import get_config_value
from pydantic import BaseModel
from graph_rag.cypher_generator import CypherGenerator # Import the class, not the instance

logger = get_logger(__name__)

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
    # Generate allow-list first (admin)
    generate_schema_allow_list()

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
        client.execute_write_query("MERGE (d:Document {id: $id}) SET d += $props", {"id": doc_id, "props": metadata}, timeout=get_config_value('guardrails.neo4j_timeout', 10))
        doc = Document(page_content=body, metadata=metadata)
        chunks = text_splitter.split_documents([doc])
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}-chunk-{i}"
            client.execute_write_query(
                "MATCH (d:Document {id: $id}) MERGE (c:Chunk {id: $chunk_id}) SET c.text = $text MERGE (d)-[:HAS_CHUNK]->(c)",
                {"id": doc_id, "chunk_id": chunk_id, "text": chunk.page_content},
                timeout=get_config_value('guardrails.neo4j_timeout', 10)
            )
            # Ask LLM to extract graph for chunk - MUST be structured
            prompt = f"Extract nodes and relationships as JSON for the text:\n\n{chunk.page_content[:1000]}"
            try:
                # In production, schema_model would be a Pydantic model; here we just call raw for dev
                g = call_llm_structured(prompt, ExtractedGraph)
                # ingest nodes safely: validate label against allow-list via cypher_generator
                local_cypher_generator = CypherGenerator() # Instantiate CypherGenerator locally
                for node in g.nodes:
                    validated_label = local_cypher_generator.validate_label(node.type)
                    client.execute_write_query(f"MERGE (n:{validated_label} {{id: $id}})", {"id": node.id}, timeout=get_config_value('guardrails.neo4j_timeout', 10))
                    client.execute_write_query("MATCH (c:Chunk {id:$cid}) MATCH (e {id:$eid}) MERGE (c)-[:MENTIONS]->(e)", {"cid": chunk_id, "eid": node.id}, timeout=get_config_value('guardrails.neo4j_timeout', 10))
            except LLMStructuredError as e:
                logger.error(f"LLM extraction failed for chunk {chunk_id}: {e}")
                # create human review record, skip for now
