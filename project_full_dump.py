# ======================================================================
# PROJECT FULL DUMP: GraphRAG Application
# Generated: 2025-10-01
# Repository Path: D:\consult_proj\spare\graphrag2
# This file is for REVIEW ONLY and must NOT be executed.
# ======================================================================

CONFIG_YAML = r"""
logging:
  level: "INFO"
  format: "%(message)s"

schema:
  allow_list_path: "allow_list.json"

retriever:
  max_chunks: 5

guardrails:
  neo4j_timeout: 10
  max_cypher_results: 25
  max_traversal_depth: 2

observability:
  metrics_enabled: true
  metrics_port: 8000

llm:
  provider: "openai"
  model: "gpt-4o"
  max_tokens: 512
  rate_limit_per_minute: 60
  redis_url: "redis://localhost:6379/0"

"""

ALLOW_LIST_JSON = r"""
{
  "node_labels": [
    "Document",
    "Chunk",
    "Entity",
    "__Entity__",
    "Person",
    "Organization",
    "Product"
  ],
  "relationship_types": [
    "PART_OF",
    "HAS_CHUNK",
    "MENTIONS",
    "FOUNDED",
    "HAS_PRODUCT"
  ],
  "properties": {}
}
"""

SCHEMA_CYPHER = r"""
CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

CREATE FULLTEXT INDEX entity_name_index IF NOT EXISTS FOR (e:__Entity__) ON EACH [e.id];

MERGE (:Predicate {id: 'PART_OF', name: 'PART_OF', inverse: 'HAS_PART', symmetric: false, transitive: true});
MERGE (:Predicate {id: 'HAS_CHUNK', name: 'HAS_CHUNK', inverse: 'CHUNK_OF', symmetric: false});
MERGE (:Predicate {id: 'MENTIONS', name: 'MENTIONS', inverse: 'MENTIONED_BY', symmetric: false});

RETURN "Schema setup complete. Constraints and indices are ready." AS status;

"""

# ======================================================================

# FILE LIST (Total: 37 files)
# ======================================================================
# Total Size: 99,349 bytes
#
# README.md                                          |        596 bytes | ada4248a1256a41b...
# config.yaml                                        |        398 bytes | 019df98e8bb6565f...
# requirements.txt                                   |        249 bytes | 05dc869eca45f132...
# Dockerfile                                         |        211 bytes | 7065cb4983772105...
# docker-compose.yml                                 |       1243 bytes | 3c5e47a68b6478b9...
# allow_list.json                                    |        267 bytes | c00b27d3b4e65e5b...
# database/schema.cypher                             |        688 bytes | e8e688360cdde9c6...
# main.py                                            |       1603 bytes | cfd681ddc970a8fd...
# graph_rag/__init__.py                              |         24 bytes | 8a5b4a2b8d68377b...
# graph_rag/audit_store.py                           |        725 bytes | 5b62dbf7b996d53b...
# graph_rag/conversation_store.py                    |       2010 bytes | 63bdfc8ea91c1bc4...
# graph_rag/cypher_generator.py                      |       3397 bytes | 00d2e2f4463ab42e...
# graph_rag/embeddings.py                            |       1736 bytes | 538343f263667932...
# graph_rag/ingest.py                                |       3712 bytes | 69199205566e6040...
# graph_rag/llm_client.py                            |       4366 bytes | f322991d0053f11a...
# graph_rag/neo4j_client.py                          |       4250 bytes | cd050e50944008cc...
# graph_rag/observability.py                         |       2251 bytes | f41caf6f75f4978f...
# graph_rag/planner.py                               |       1384 bytes | 5460b59190551c8a...
# graph_rag/rag.py                                   |       2947 bytes | 79ede17f215d8c41...
# graph_rag/retriever.py                             |       3764 bytes | 57190bd250c57daf...
# graph_rag/schema_catalog.py                        |       2013 bytes | cd500be0b6843c67...
# graph_rag/utils.py                                 |        133 bytes | 906176c39f3a193b...
# tests/test_api_endpoints.py                        |       7784 bytes | 209c32eb2967877d...
# tests/test_citation_verification.py                |       7943 bytes | c3f74ba2dce40cc2...
# tests/test_cypher_safety.py                        |        501 bytes | 40c01c86f01bf59f...
# tests/test_ingest_llm_validation.py                |       5714 bytes | 7596507e10e433c8...
# tests/test_label_sanitization.py                   |        728 bytes | 4a8668cbb1c59db8...
# tests/test_label_validation.py                     |       4338 bytes | 99f075bc78e63116...
# tests/test_llm_client_structured.py                |       5902 bytes | b1c3298b58af7abd...
# tests/test_neo4j_timeout.py                        |       1961 bytes | 9fc5e6f9026a99c4...
# tests/test_observability_import.py                 |       3487 bytes | 474471b9684ea009...
# tests/test_planner_llm_integration.py              |       4884 bytes | 5f1766252b640bcc...
# tests/test_tracing_integration.py                  |       9113 bytes | 5b7b9c498fb0dd4b...
# .github/workflows/ci.yml                           |        572 bytes | cf2232945fe7b843...
# docs/req_doc.txt                                   |       8103 bytes | a472c0faf9214e22...
# TASKS.md                                           |        352 bytes | 4991d3f81e225a38...
# audit_log.jsonl                                    |          0 bytes | e3b0c44298fc1c14...
# ======================================================================

# ======================================================================
# FILE: README.md
# SIZE: 596 bytes
# SHA256: ada4248a1256a41b2a677679d9101be4a61944eb900a7d8871d759842dab125c
# ======================================================================
# GraphRAG Application - Starter Scaffold

This is a minimal safe scaffold for a Graph-backed RAG application.

Key modules:

- `graph_rag/neo4j_client.py` - read-only Neo4j client with timeouts.
- `graph_rag/cypher_generator.py` - templates + label validation against `allow_list.json`.
- `graph_rag/observability.py` - OpenTelemetry + Prometheus metrics.
- `graph_rag/llm_client.py` - structured LLM calls + rate limiting scaffold.
- `graph_rag/ingest.py` - ingestion pipeline (LLM extraction must validate labels).
- `main.py` - FastAPI server skeleton.

Follow TASKS.md to harden and expand.


# ======================================================================
# FILE: config.yaml
# SIZE: 398 bytes
# SHA256: 019df98e8bb6565f668c7c65acd68d355ae788161c7a186c74b13168589c7c79
# ======================================================================
logging:
  level: "INFO"
  format: "%(message)s"

schema:
  allow_list_path: "allow_list.json"

retriever:
  max_chunks: 5

guardrails:
  neo4j_timeout: 10
  max_cypher_results: 25
  max_traversal_depth: 2

observability:
  metrics_enabled: true
  metrics_port: 8000

llm:
  provider: "openai"
  model: "gpt-4o"
  max_tokens: 512
  rate_limit_per_minute: 60
  redis_url: "redis://localhost:6379/0"


# ======================================================================
# FILE: requirements.txt
# SIZE: 249 bytes
# SHA256: 05dc869eca45f132cdc97cbae5b4862c0c956849aeb0e683b83eb3ce8774937e
# ======================================================================
fastapi
uvicorn[standard]
neo4j
python-dotenv
langchain-openai
langchain
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp-proto-http
opentelemetry-exporter-otlp-proto-grpc
prometheus-client
redis
structlog
pydantic
pytest
pytest-mock


# ======================================================================
# FILE: Dockerfile
# SIZE: 211 bytes
# SHA256: 7065cb4983772105fd2afefe6f1be7a4afd7b0842b09c82e43b3680320ab8396
# ======================================================================
FROM python:3.11-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]



# ======================================================================
# FILE: docker-compose.yml
# SIZE: 1243 bytes
# SHA256: 3c5e47a68b6478b915bee16a318efb9a0b9728f75aebd8ec35ec4240f44cdd9a
# ======================================================================
version: '3.8'

services:
  neo4j:
    image: neo4j:5.10-community
    hostname: neo4j
    ports:
      - "7687:7687"
      - "7474:7474" # For Neo4j Browser
    volumes:
      - neo4j_data:/data
      - ./neo4j/conf:/conf # Optional: for custom config
      - ./neo4j/plugins:/plugins # Optional: for plugins
    environment:
# SECRET REDACTED
      - NEO4J_AUTH=<REDACTED_SECRET>
      - NEO4J_dbms_connector_bolt_listen__address=0.0.0.0:7687
      - NEO4J_dbms_connector_http_listen__address=0.0.0.0:7474
      - NEO4J_dbms_memory_heap_initial__size=512m
      - NEO4J_dbms_memory_heap_max__size=1G

  redis:
    image: redis:7
    hostname: redis
    ports:
      - "6379:6379"

  app:
    build:
      context: .
      dockerfile: Dockerfile
    hostname: app
    ports:
      - "8000:8000"
    depends_on:
      - neo4j
      - redis
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USERNAME=${NEO4J_USERNAME}
# SECRET REDACTED
      - NEO4J_PASSWORD=<REDACTED_SECRET>
      - REDIS_URL=redis://redis:6379/0
# SECRET REDACTED
      - OPENAI_API_KEY=<REDACTED_SECRET>
    volumes:
      - .:/app # Mount current directory to /app for live reloading during development
    env_file:
      - .env

volumes:
  neo4j_data:



# ======================================================================
# FILE: allow_list.json
# SIZE: 267 bytes
# SHA256: c00b27d3b4e65e5bff50c24dea781836071bb0cae841ab2db273b33a68374e09
# ======================================================================
{
  "node_labels": [
    "Document",
    "Chunk",
    "Entity",
    "__Entity__",
    "Person",
    "Organization",
    "Product"
  ],
  "relationship_types": [
    "PART_OF",
    "HAS_CHUNK",
    "MENTIONS",
    "FOUNDED",
    "HAS_PRODUCT"
  ],
  "properties": {}
}

# ======================================================================
# FILE: database/schema.cypher
# SIZE: 688 bytes
# SHA256: e8e688360cdde9c6e63745b76fa653adc211fd501159688672ceea717e91d8e4
# ======================================================================
CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

CREATE FULLTEXT INDEX entity_name_index IF NOT EXISTS FOR (e:__Entity__) ON EACH [e.id];

MERGE (:Predicate {id: 'PART_OF', name: 'PART_OF', inverse: 'HAS_PART', symmetric: false, transitive: true});
MERGE (:Predicate {id: 'HAS_CHUNK', name: 'HAS_CHUNK', inverse: 'CHUNK_OF', symmetric: false});
MERGE (:Predicate {id: 'MENTIONS', name: 'MENTIONS', inverse: 'MENTIONED_BY', symmetric: false});

RETURN "Schema setup complete. Constraints and indices are ready." AS status;


# ======================================================================
# FILE: main.py
# SIZE: 1603 bytes
# SHA256: cfd681ddc970a8fde83405c7ee07980176c47533fce9dfb3b30db535882b28fc
# ======================================================================
# main.py
import os
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from graph_rag.rag import rag_chain
from graph_rag.observability import start_metrics_server, get_logger
from graph_rag.conversation_store import conversation_store
import uuid

with open("config.yaml", 'r') as f:
    cfg = yaml.safe_load(f)

logger = get_logger(__name__)
app = FastAPI(title="GraphRAG")

@app.on_event("startup")
def startup_event():
    conversation_store.init()
    if cfg.get("observability", {}).get("metrics_enabled", True):
        start_metrics_server()

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    question: str

@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.question:
        raise HTTPException(400, "Question is required")

    conv_id = req.conversation_id if req.conversation_id else str(uuid.uuid4())
    
    conversation_store.add_message(conv_id, {"role": "user", "text": req.question})

    try:
        resp = rag_chain.invoke(req.question)
        conversation_store.add_message(conv_id, {"role": "assistant", "text": resp.get("answer"), "trace_id": resp.get("trace_id")})
        resp["conversation_id"] = conv_id
        return resp
    except Exception as e:
        logger.error(f"Error in /api/chat: {e}")
        raise HTTPException(500, "internal error")

@app.get("/api/chat/{conversation_id}/history")
def get_history(conversation_id: str):
    history = conversation_store.get_history(conversation_id)
    if not history:
        raise HTTPException(404, "Conversation not found")
    return history


# ======================================================================
# FILE: graph_rag/__init__.py
# SIZE: 24 bytes
# SHA256: 8a5b4a2b8d68377b07886b4e8f1359263f78d3a61a192e50d291b0f68e9af42c
# ======================================================================
# graph_rag/__init__.py


# ======================================================================
# FILE: graph_rag/audit_store.py
# SIZE: 725 bytes
# SHA256: 5b62dbf7b996d53bd7089eb0c0b083253f71a1e0e9c452566460288cf342b54a
# ======================================================================
# graph_rag/audit_store.py

import json
import os

from graph_rag.observability import get_logger

logger = get_logger(__name__)

class AuditStore:
    def __init__(self, log_file: str = "audit_log.jsonl"):
        self.log_file = log_file
        self._ensure_log_file_exists()

    def _ensure_log_file_exists(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', encoding='utf-8') as f:
                pass # Create an empty file if it doesn't exist

    def record(self, entry: dict):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')

# Global instance for easy access, can be mocked in tests
audit_store = AuditStore()


# ======================================================================
# FILE: graph_rag/conversation_store.py
# SIZE: 2010 bytes
# SHA256: 63bdfc8ea91c1bc4e65e6d2dc78a10caa0cc4ddb027042e6b8bb7f0eb52b144f
# ======================================================================
# graph_rag/conversation_store.py
import json
import os
from typing import List, Dict

class ConversationStore:
    def __init__(self, storage_dir: str = "conversations"):
        self.storage_dir = storage_dir
        self.conversations: Dict[str, List[Dict]] = {}
        self._ensure_storage_dir_exists()

    def _ensure_storage_dir_exists(self):
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_conversation_file(self, conversation_id: str) -> str:
        return os.path.join(self.storage_dir, f"conv_{conversation_id}.jsonl")

    def init(self):
        """Initializes the conversation store by loading existing conversations."""
        for filename in os.listdir(self.storage_dir):
            if filename.startswith("conv_") and filename.endswith(".jsonl"):
                conversation_id = filename[len("conv_"):-len(".jsonl")]
                self.conversations[conversation_id] = self._load_conversation(conversation_id)

    def _load_conversation(self, conversation_id: str) -> List[Dict]:
        filepath = self._get_conversation_file(conversation_id)
        messages = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    messages.append(json.loads(line))
        return messages

    def add_message(self, conversation_id: str, message: Dict):
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append(message)
        self._persist_message(conversation_id, message)

    def _persist_message(self, conversation_id: str, message: Dict):
        filepath = self._get_conversation_file(conversation_id)
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message) + '\n')

    def get_history(self, conversation_id: str) -> List[Dict]:
        return self.conversations.get(conversation_id, [])

conversation_store = ConversationStore()


# ======================================================================
# FILE: graph_rag/cypher_generator.py
# SIZE: 3397 bytes
# SHA256: 00d2e2f4463ab42ea45b7279d2d0dabc229c30071aaf9fdc56a2a49633f2e0d4
# ======================================================================
# graph_rag/cypher_generator.py
import json
import re
import yaml
from graph_rag.observability import get_logger

logger = get_logger(__name__)

LABEL_REGEX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RELATIONSHIP_TYPE_REGEX = re.compile(r"^[A-Z_][A-Z0-9_]*$") # Cypher relationship types are typically uppercase

with open("config.yaml", 'r') as f:
    CFG = yaml.safe_load(f)

class CypherGenerator:
    def __init__(self, allow_list_path: str = None):
        path = allow_list_path or CFG['schema']['allow_list_path']
        try:
            with open(path, 'r') as fh:
                self.allow_list = json.load(fh)
        except FileNotFoundError:
            logger.error("allow_list.json not found; create it with schema_catalog.generate_schema_allow_list()")
            self.allow_list = {"node_labels": [], "relationship_types": [], "properties": {}}

    def _validate_label(self, label: str) -> bool:
        if not label or not LABEL_REGEX.match(label):
            return False
        return label in self.allow_list.get("node_labels", [])

    def _validate_relationship_type(self, rel_type: str) -> bool:
        if not rel_type or not RELATIONSHIP_TYPE_REGEX.match(rel_type):
            return False
        return rel_type in self.allow_list.get("relationship_types", [])

    def validate_label(self, label: str) -> str:
        if self._validate_label(label):
            return f"`{label}`"
        logger.warning(f"Invalid label '{label}' provided. Falling back to default 'Entity'.")
        return "`Entity`"

    def validate_relationship_type(self, rel_type: str) -> str:
        if self._validate_relationship_type(rel_type):
            return f"`{rel_type}`"
        logger.warning(f"Invalid relationship type '{rel_type}' provided. Falling back to default 'RELATED'.")
        return "`RELATED`"

    def _validate_template(self, template: dict) -> bool:
        reqs = template.get("schema_requirements", {})
        for label in reqs.get("labels", []):
            if not self._validate_label(label):
                logger.error(f"Template label {label} not in allow list")
                return False
        for rel in reqs.get("relationships", []):
            if not self._validate_relationship_type(rel):
                logger.error(f"Template rel {rel} not in allow list")
                return False
        return True

CYPHER_TEMPLATES = {
    "general_rag_query": {
        "cypher": """
            MATCH (e:__Entity__ {id: $anchor})
            CALL {
                WITH e
                MATCH (e)-[r]->(neighbor)
                WHERE type(r) <> 'HAS_CHUNK' AND type(r) <> 'MENTIONS'
                RETURN "(" + e.id + ")" + "-[:" + type(r) + "]->" + "(" + neighbor.id + ")" AS output
                UNION ALL
                WITH e
                MATCH (e)<-[r]-(neighbor)
                WHERE type(r) <> 'HAS_CHUNK' AND type(r) <> 'MENTIONS'
                RETURN "(" + neighbor.id + ")" + "-[:" + type(r) + "]->" + "(" + e.id + ")" AS output
            }
            RETURN output LIMIT 20
        """,
        "schema_requirements": {"labels": ["__Entity__"], "relationships": []}
    },
    "company_founder_query": {
        "cypher": "MATCH (p:Person)-[:FOUNDED]->(o:Organization {id: $anchor}) RETURN p.id AS founder",
        "schema_requirements": {"labels": ["Person", "Organization"], "relationships": ["FOUNDED"]}
    }
}


# ======================================================================
# FILE: graph_rag/embeddings.py
# SIZE: 1736 bytes
# SHA256: 538343f26366793232e323e470ca5d505d6487dc5d44563d1fc0b28655a706ec
# ======================================================================
# graph_rag/embeddings.py
import os
from dotenv import load_dotenv
from graph_rag.observability import get_logger, llm_calls_total

logger = get_logger(__name__)
# load_dotenv() # Moved to be called explicitly if needed, or mocked

# SECRET REDACTED
OPENAI_KEY =<REDACTED_SECRET>
if not OPENAI_KEY:
    logger.error("OPENAI_API_KEY not present in env")

try:
    from langchain_openai import OpenAIEmbeddings
except Exception:
    # placeholder: real environment should have langchain-openai package
    OpenAIEmbeddings = None

_embedding_provider_instance = None

class EmbeddingProvider:
    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model = model_name
        if OpenAIEmbeddings:
            self.client = OpenAIEmbeddings(model=model_name)
            logger.info("OpenAI embeddings client initialized")
        else:
            self.client = None
            logger.info("OpenAIEmbeddings not installed; running in mock mode")

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.client:
            # simple deterministic mock embeddings
            return [[float(len(t))] * 8 for t in texts]
        try:
            llm_calls_total.inc()
            return self.client.embed_documents(texts)
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return [[] for _ in texts]

def get_embedding_provider():
    global _embedding_provider_instance
    if _embedding_provider_instance is None:
        _embedding_provider_instance = EmbeddingProvider()
    return _embedding_provider_instance

# embedding_provider = EmbeddingProvider() # Removed module-level instantiation


# ======================================================================
# FILE: graph_rag/ingest.py
# SIZE: 3712 bytes
# SHA256: 69199205566e60401d919bdaac21b4501444ce4f8ccbb424a12d4ad2c2648113
# ======================================================================
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
from pydantic import BaseModel
from graph_rag.cypher_generator import CypherGenerator # Import the class, not the instance

logger = get_logger(__name__)
with open("config.yaml", 'r') as f:
    CFG = yaml.safe_load(f)

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
        client.execute_write_query("MERGE (d:Document {id: $id}) SET d += $props", {"id": doc_id, "props": metadata}, timeout=CFG['guardrails']['neo4j_timeout'])
        doc = Document(page_content=body, metadata=metadata)
        chunks = text_splitter.split_documents([doc])
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}-chunk-{i}"
            client.execute_write_query(
                "MATCH (d:Document {id: $id}) MERGE (c:Chunk {id: $chunk_id}) SET c.text = $text MERGE (d)-[:HAS_CHUNK]->(c)",
                {"id": doc_id, "chunk_id": chunk_id, "text": chunk.page_content},
                timeout=CFG['guardrails']['neo4j_timeout']
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
                    client.execute_write_query(f"MERGE (n:{validated_label} {{id: $id}})", {"id": node.id}, timeout=CFG['guardrails']['neo4j_timeout'])
                    client.execute_write_query("MATCH (c:Chunk {id:$cid}) MATCH (e {id:$eid}) MERGE (c)-[:MENTIONS]->(e)", {"cid": chunk_id, "eid": node.id}, timeout=CFG['guardrails']['neo4j_timeout'])
            except LLMStructuredError as e:
                logger.error(f"LLM extraction failed for chunk {chunk_id}: {e}")
                # create human review record, skip for now


# ======================================================================
# FILE: graph_rag/llm_client.py
# SIZE: 4366 bytes
# SHA256: f322991d0053f11a4c77fb5ef2bd4cf01e89306cf65e21ae021197fba0915411
# ======================================================================
# graph_rag/llm_client.py
import os
import time
import json
import yaml
import redis
from pydantic import BaseModel, ValidationError
from graph_rag.observability import get_logger, tracer, llm_calls_total
from graph_rag.audit_store import audit_store

logger = get_logger(__name__)
with open("config.yaml", 'r') as f:
    CFG = yaml.safe_load(f)

REDIS_URL = CFG['llm'].get('redis_url', os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# Internal variable to store the Redis client instance
_redis_client_instance = None

def _get_redis_client():
    global _redis_client_instance
    if _redis_client_instance is None:
        _redis_client_instance = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client_instance

RATE_LIMIT_KEY = "graphrag:llm:tokens"
RATE_LIMIT_PER_MINUTE = CFG['llm'].get('rate_limit_per_minute', 60)

# Lua script for atomic token consumption
# KEYS[1] - rate limit key
# ARGV[1] - tokens to consume
# ARGV[2] - rate limit per minute
# ARGV[3] - current timestamp (integer seconds)
RATE_LIMIT_LUA_SCRIPT = """
    local key = KEYS[1]
    local tokens_to_consume = tonumber(ARGV[1])
    local rate_limit_per_minute = tonumber(ARGV[2])
    local current_time = tonumber(ARGV[3])

    local window = math.floor(current_time / 60)
    local window_key = key .. ":" .. window

    local current_tokens = tonumber(redis.call('get', window_key) or rate_limit_per_minute)

    if current_tokens - tokens_to_consume >= 0 then
        redis.call('decrby', window_key, tokens_to_consume)
        -- Set expiry to the end of the current window + a buffer (e.g., 60 seconds)
        redis.call('expire', window_key, (window + 1) * 60 - current_time + 60)
        return 1
    else
        return 0
    end
"""

def consume_token(key=RATE_LIMIT_KEY, tokens=1) -> bool:
    """
    Consumes tokens from a Redis-backed token bucket using a Lua script for atomicity.
    Returns True if tokens were consumed, False otherwise.
    """
    now = int(time.time())
    redis_client = _get_redis_client()
    result = redis_client.eval(RATE_LIMIT_LUA_SCRIPT, 1, key, tokens, RATE_LIMIT_PER_MINUTE, now)
    return result == 1

class LLMStructuredError(Exception):
    pass

def call_llm_raw(prompt: str, model: str, max_tokens: int = 512) -> str:
    """
    Placeholder raw LLM caller. Integrate OpenAI/other in prod.
    Must be wrapped by call_llm_structured() which validates outputs.
    """
    llm_calls_total.inc()
    # TODO: integrate real provider
    # For now return a JSON-like string or plain text (for dev)
    return '{"intent":"general_rag_query","anchor":null}'

def call_llm_structured(prompt: str, schema_model: BaseModel, model: str = None, max_tokens: int = None):
    """
    Calls LLM and validates JSON output against schema_model (a Pydantic model class).
    Returns validated object instance or raises LLMStructuredError.
    """
    if not consume_token():
        raise LLMStructuredError("LLM rate limit exceeded")

    model = model or CFG['llm']['model']
    max_tokens = max_tokens or CFG['llm']['max_tokens']
    response = call_llm_raw(prompt, model=model, max_tokens=max_tokens)

    # Try to parse JSON safely
    try:
        parsed = json.loads(response)
    except Exception:
        # attempt to extract JSON substring
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            parsed = json.loads(response[start:end])
        except Exception as e:
            logger.error(f"LLM returned non-JSON and extraction failed: {response}")
            audit_store.record(entry={"type":"llm_parse_failure", "prompt": prompt, "response":response, "error":str(e), "trace_id": str(tracer.get_current_span().context.trace_id) if tracer.get_current_span() else None})
            raise LLMStructuredError("Invalid JSON from LLM") from e

    try:
        validated = schema_model.model_validate(parsed) # Use model_validate for Pydantic v2+
        return validated
    except ValidationError as e:
        logger.warning(f"LLM output failed validation: {e}")
        audit_store.record(entry={"type":"llm_validation_failed", "prompt": prompt, "response":response, "error":str(e), "trace_id": str(tracer.get_current_span().context.trace_id) if tracer.get_current_span() else None})
        raise LLMStructuredError("Structured output failed validation") from e


# ======================================================================
# FILE: graph_rag/neo4j_client.py
# SIZE: 4250 bytes
# SHA256: cd050e50944008cc973e6f8ee22b487ee6fcad10302a8cc485d210e05f00f73b
# ======================================================================
# graph_rag/neo4j_client.py
import os
import yaml
from time import perf_counter
from neo4j import GraphDatabase, exceptions
from dotenv import load_dotenv
from graph_rag.observability import get_logger, tracer, db_query_total, db_query_failed, db_query_latency, inflight_queries

logger = get_logger(__name__)

with open("config.yaml", 'r') as f:
    CONFIG = yaml.safe_load(f)

load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME")
# SECRET REDACTED
NEO4J_PASSWORD =<REDACTED_SECRET>

if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
    logger.error("Missing Neo4j credentials in env")

class Neo4jClient:
    def __init__(self, driver=None):
        if driver:
            self._driver = driver
        else:
# SECRET REDACTED
            self._driver =<REDACTED_SECRET>
        try:
            self._driver.verify_connectivity()
            logger.info("Connected to Neo4j")
        except Exception as e:
            logger.error(f"Neo4j connectivity failed: {e}")
            raise

    def close(self):
        self._driver.close()
        logger.info("Neo4j driver closed")

    def _execute_query(self, query: str, params: dict | None = None, access_mode=None, timeout: float | None = None, query_name: str | None = None):
        params = params or {}
        query_name = query_name or "generic_query"
        
        with tracer.start_as_current_span("neo4j.query") as span:
            span.set_attribute("db.system", "neo4j")
            span.set_attribute("db.statement", query)
            if query_name:
                span.set_attribute("db.statement.summary", query_name)
            
            inflight_queries.inc()
            start = perf_counter()
            status = "failure"
            try:
                with self._driver.session(default_access_mode=access_mode) as session:
                    if timeout:
                        tx = session.begin_transaction(timeout=timeout)
                        result = tx.run(query, params)
                        records = [r.data() for r in result]
                        try:
                            tx.commit()
                            status = "success"
                        except exceptions.ClientError as e:
                            logger.warning(f"Transaction commit failed for query '{query_name}': {e}")
                            status = "failure"
                        except Exception:
                            status = "failure"
                    else:
                        result = session.run(query, params)
                        records = [r.data() for r in result]
                        status = "success"
                duration = perf_counter() - start
                db_query_latency.observe(duration)
                db_query_total.labels(status=status).inc()
                return records
            except exceptions.CypherSyntaxError as e:
                db_query_total.labels(status="failure").inc()
                db_query_failed.inc()
                logger.error(f"Cypher syntax error for query '{query_name}': {e}")
                return []
            except exceptions.ClientError as e:
                db_query_total.labels(status="failure").inc()
                db_query_failed.inc()
                logger.error(f"Neo4j client error for query '{query_name}': {e}")
                return []
            except Exception as e:
                db_query_total.labels(status="failure").inc()
                db_query_failed.inc()
                logger.error(f"Unexpected DB error for query '{query_name}': {e}")
                return []
            finally:
                inflight_queries.dec()

    def execute_read_query(self, query: str, params: dict | None = None, timeout: float | None = None, query_name: str | None = None):
        return self._execute_query(query, params=params, access_mode="READ", timeout=timeout, query_name=query_name)

    def execute_write_query(self, query: str, params: dict | None = None, timeout: float | None = None, query_name: str | None = None):
        # write only used by ingestion/admin flows
        return self._execute_query(query, params=params, access_mode="WRITE", timeout=timeout, query_name=query_name)


# ======================================================================
# FILE: graph_rag/observability.py
# SIZE: 2251 bytes
# SHA256: f41caf6f75f4978fc593e697fa1d6a55ab3e4462dac034f6b8f0bcc45ffdbb77
# ======================================================================
# graph_rag/observability.py
import os
import logging
import structlog
from prometheus_client import start_http_server, Counter, Histogram, Gauge
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# OpenTelemetry Tracer
resource = Resource.create({
    "service.name": os.getenv("OTEL_SERVICE_NAME", "graphrag-application"),
    "service.version": os.getenv("OTEL_SERVICE_VERSION", "0.1.0"),
})

provider = TracerProvider(resource=resource)

otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
if otlp_endpoint:
    span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
else:
    span_exporter = ConsoleSpanExporter()

provider.add_span_processor(BatchSpanProcessor(span_exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# Prometheus Metrics
db_query_total = Counter("db_query_total", "Total number of database queries.", ["status"])
db_query_failed = Counter("db_query_failed", "Number of failed database queries.")
db_query_latency = Histogram("db_query_latency_seconds", "Latency of database queries.", buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')))
inflight_queries = Gauge("inflight_queries", "Number of currently inflight database queries.")
llm_calls_total = Counter("llm_calls_total", "Total number of LLM calls.")

def start_metrics_server():
    port = int(os.getenv("PROMETHEUS_PORT", 8000))
    start_http_server(port)
    logging.info(f"Prometheus metrics server started on port {port}")

# Structured Logger

def get_logger(name: str):
    structlog.configure(
        processors=[
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger(name)


# ======================================================================
# FILE: graph_rag/planner.py
# SIZE: 1384 bytes
# SHA256: 5460b59190551c8a147e7878c2fcf3e6420e7f1ebb41f24cefbe9f192d8bc93d
# ======================================================================
# graph_rag/planner.py
import yaml
from pydantic import BaseModel, Field
from graph_rag.observability import get_logger
from graph_rag.llm_client import call_llm_structured, LLMStructuredError

logger = get_logger(__name__)
with open("config.yaml", 'r') as f:
    CFG = yaml.safe_load(f)

class ExtractedEntities(BaseModel):
    names: list[str] = Field(...)

class QueryPlan(BaseModel):
    intent: str
    anchor_entity: str | None = None
    question: str

def _detect_intent(question: str):
    q = question.lower()
    if "who founded" in q:
        return "company_founder_query"
    if "product" in q:
        return "company_product_query"
    return "general_rag_query"

def generate_plan(question: str) -> QueryPlan:
    # Get candidate entities via LLM structured output (or local NER in production)
    try:
        prompt = f"Extract person and organization entity names from: {question}"
        extracted = call_llm_structured(prompt, ExtractedEntities)
        names = extracted.names
    except LLMStructuredError as e:
        logger.warning(f"LLM entity extraction failed: {e}. Falling back to empty entities.")
        names = []

    intent = _detect_intent(question)
    # Anchor validation against DB happens in the Planner caller; here we return a simple plan
    return QueryPlan(intent=intent, anchor_entity=(names[0] if names else None), question=question)


# ======================================================================
# FILE: graph_rag/rag.py
# SIZE: 2947 bytes
# SHA256: 79ede17f215d8c41f0aaacfe0655fad744013573ea6f3f9c31102e539cccb84e
# ======================================================================
# graph_rag/rag.py
import re
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from graph_rag.planner import generate_plan
from graph_rag.retriever import Retriever # Import the class, not the instance
from graph_rag.observability import get_logger, tracer
from opentelemetry.trace import get_current_span
from graph_rag.audit_store import audit_store

logger = get_logger(__name__)

class RAGChain:
    def __init__(self):
        self.llm = ChatOpenAI(temperature=0, model_name="gpt-4o")
        self.retriever = Retriever() # Instantiate Retriever locally

    def _verify_citations(self, answer, provided_chunk_ids, question, trace_id):
        cited = set(re.findall(r'\[([^\]]+)\]', answer))
        provided = set(provided_chunk_ids)
        unknown = cited - provided
        
        verification_result = {
            "cited_ids": list(cited),
            "provided_ids": list(provided_chunk_ids),
            "unknown_citations": list(unknown),
            "verified": not bool(unknown),
            "verification_action": ""
        }
        
        if unknown:
            verification_result["verification_action"] = "human_review_required"
            audit_store.record({
                "event_type": "citation_verification_failed",
                "trace_id": trace_id,
                "question": question,
                "unknown_citations": list(unknown)
            })
            
        return verification_result

    def invoke(self, question: str):
        with tracer.start_as_current_span("rag.invoke") as span:
            plan = generate_plan(question)
            span.set_attribute("plan.intent", plan.intent)
            current_span = get_current_span()
            trace_id_hex = f"{current_span.context.trace_id:x}" if current_span and current_span.context.is_valid else None

            rc = self.retriever.retrieve_context(plan)
            prompt_template = """
            You are an expert Q&A system. Use ONLY the context provided below.
            Structured:
            {structured}
            Unstructured:
            {unstructured}
            Question:
            {question}
            """
            prompt = prompt_template.format(structured=rc['structured'], unstructured=rc['unstructured'], question=question)
            answer = self.llm.generate([{"role":"user","content":prompt}]).generations[0][0].text
            
            verification = self._verify_citations(answer, rc.get("chunk_ids", []), question, trace_id_hex)
            
            response = {
                "question": question,
                "answer": answer,
                "plan": plan.model_dump(),
                "sources": rc.get("chunk_ids", []),
                "citation_verification": verification,
                "trace_id": trace_id_hex # Include trace_id in response
            }
            return response

rag_chain = RAGChain()


# ======================================================================
# FILE: graph_rag/retriever.py
# SIZE: 3764 bytes
# SHA256: 57190bd250c57dafafee29f335f1b8a8b499ec9c299349cd971d3abc26691676
# ======================================================================
# graph_rag/retriever.py
import yaml
from graph_rag.observability import get_logger, tracer
from graph_rag.neo4j_client import Neo4jClient # Import the class, not the instance
from graph_rag.embeddings import get_embedding_provider # Import the getter function
from graph_rag.cypher_generator import CypherGenerator # Import the class, not the instance

logger = get_logger(__name__)
with open("config.yaml", 'r') as f:
    CFG = yaml.safe_load(f)

class Retriever:
    def __init__(self, max_chunks: int = None):
        self.max_chunks = max_chunks or CFG['retriever']['max_chunks']
        self.neo4j_client = Neo4jClient()
        self.embedding_provider = get_embedding_provider()
        self.cypher_generator = CypherGenerator()

    def _get_structured_context(self, plan):
        with tracer.start_as_current_span("retriever.structured_query") as span:
            span.set_attribute("template_name", plan.intent)
            span.set_attribute("anchor_entity", plan.anchor_entity)
            cypher, params = self.cypher_generator.CYPHER_TEMPLATES.get(plan.intent, {}).get("cypher"), {"anchor": plan.anchor_entity}
            if not cypher:
                return ""
            result = self.neo4j_client.execute_read_query(cypher, params=params, timeout=CFG['guardrails']['neo4j_timeout'])
            return "\n".join([list(r.values())[0] for r in result])

    def _get_unstructured_context(self, question):
        with tracer.start_as_current_span("retriever.vector_search"):
            emb = self.embedding_provider.get_embeddings([question])[0]
            if not emb:
                return []
            q = """
            CALL db.index.vector.queryNodes('chunk_embeddings', $top_k, $embedding)
            YIELD node
            RETURN node.id AS chunk_id
            """
            rows = self.neo4j_client.execute_read_query(q, {"top_k": self.max_chunks, "embedding": emb}, timeout=CFG['guardrails']['neo4j_timeout'])
            return [r['chunk_id'] for r in rows]

    def _expand_with_hierarchy(self, chunk_ids):
        with tracer.start_as_current_span("retriever.hierarchy_expand") as span:
            if not chunk_ids:
                return []
            span.add_event("citations", attributes={"chunk_ids": chunk_ids})
            q = """
            UNWIND $chunk_ids AS cid
            MATCH (initial_chunk:Chunk {id: cid})
            MATCH (source_doc:Document)-[:HAS_CHUNK]->(initial_chunk)
            CALL { WITH source_doc MATCH (source_doc)-[:PART_OF*0..$max_hops]->(p:Document) RETURN collect(DISTINCT p) AS parents }
            WITH source_doc, parents
            UNWIND parents + [source_doc] AS related_doc
            MATCH (related_doc)-[:HAS_CHUNK]->(related_chunk:Chunk)
            RETURN DISTINCT related_chunk.id AS id, related_chunk.text AS text
            LIMIT $max_chunks
            """
            rows = self.neo4j_client.execute_read_query(q, {"chunk_ids": chunk_ids, "max_hops": CFG['guardrails']['max_traversal_depth'], "max_chunks": self.max_chunks}, timeout=CFG['guardrails']['neo4j_timeout'])
            return rows

    def retrieve_context(self, plan):
        with tracer.start_as_current_span("retriever.retrieve_context"):
            structured = self._get_structured_context(plan)
            initial_chunks = self._get_unstructured_context(plan.question)
            expanded = self._expand_with_hierarchy(initial_chunks)
            # return structured and flattened unstructured context as text
            unstructured_text = "\n\n".join([f"[{r['id']}]\n{r['text']}" for r in expanded])
            return {"structured": structured, "unstructured": unstructured_text, "chunk_ids": [r['id'] for r in expanded]}

# retriever = Retriever() # Removed module-level instantiation


# ======================================================================
# FILE: graph_rag/schema_catalog.py
# SIZE: 2013 bytes
# SHA256: cd500be0b6843c676caab45ba7f997eef0db5c229cc9a0fbfbb59e86466a8077
# ======================================================================
# graph_rag/schema_catalog.py
import json
import yaml
from graph_rag.neo4j_client import Neo4jClient
from graph_rag.observability import get_logger

logger = get_logger(__name__)

def generate_schema_allow_list(output_path: str = None):
    with open("config.yaml", 'r') as f:
        cfg = yaml.safe_load(f)
    output_path = output_path or cfg['schema']['allow_list_path']

    try:
        client = Neo4jClient()
        labels = [r['label'] for r in client.execute_read_query("CALL db.labels() YIELD label RETURN label")]
        rels = [r['relationshipType'] for r in client.execute_read_query("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")]
        schema_result = client.execute_read_query("CALL db.schema.visualization()")
        nodes = schema_result[0].get('nodes', []) if schema_result else []
        properties = {}
        for node in nodes:
            name = node.get('name')
            prop_rows = client.execute_read_query(f"MATCH (n:`{name}`) UNWIND keys(n) AS key RETURN DISTINCT key")
            properties[name] = [p['key'] for p in prop_rows]
        allow = {"node_labels": labels, "relationship_types": rels, "properties": properties}
        with open(output_path, 'w') as fh:
            json.dump(allow, fh, indent=2)
        logger.info(f"Allow-list written to {output_path}")
        return allow
    except Exception as e:
        logger.warning(f"Failed to generate schema allow-list from Neo4j: {e}. Creating a stub allow_list.json.")
        # Create a conservative allow_list.json stub
        stub_allow_list = {
            "node_labels": ["Document","Chunk","Entity","__Entity__","Person","Organization","Product"],
            "relationship_types": ["PART_OF","HAS_CHUNK","MENTIONS","FOUNDED","HAS_PRODUCT"],
            "properties": {}
        }
        with open(output_path, 'w') as fh:
            json.dump(stub_allow_list, fh, indent=2)
        logger.info(f"Stub allow-list written to {output_path}")
        return stub_allow_list


# ======================================================================
# FILE: graph_rag/utils.py
# SIZE: 133 bytes
# SHA256: 906176c39f3a193b57390a5369fa2e58da2445d7da7e0fc10911f5e45eec852c
# ======================================================================
# graph_rag/utils.py
def approx_tokens(text: str) -> int:
    # rough heuristic: 1 token ~ 4 chars
    return max(1, len(text) // 4)


# ======================================================================
# FILE: tests/test_api_endpoints.py
# SIZE: 7784 bytes
# SHA256: 209c32eb2967877d7a557aa1bdfa4cb2fba2210bfa32d775d5a6c2252e51e264
# ======================================================================
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json
from fastapi.testclient import TestClient
from pydantic import BaseModel
from prometheus_client import REGISTRY
from opentelemetry.trace import SpanContext, TraceFlags

# Dummy Pydantic models for mocking LLM structured output
class QueryPlan(BaseModel):
    intent: str
    anchor: str | None = None

class ExtractedEntities(BaseModel):
    names: list[str]

class RAGChain:
    def invoke(self, question: str):
        return {"answer": f"Mocked answer for {question}", "trace_id": "mock_trace_id", "sources": ["mock_chunk_id"]}

class TestAPIEndpoints(unittest.TestCase):

    def setUp(self):
        # Ensure modules are reloaded for each test
        for module_name in [
            'main', 'graph_rag.rag', 'graph_rag.retriever', 'graph_rag.planner',
            'graph_rag.llm_client', 'graph_rag.cypher_generator', 'graph_rag.neo4j_client',
            'graph_rag.embeddings', 'graph_rag.ingest', 'graph_rag.audit_store',
            'graph_rag.conversation_store'
        ]:
            if module_name in sys.modules:
                del sys.modules[module_name]
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

        # Set up a temporary directory for conversations for each test
        self.test_conversations_dir = "temp_test_conversations"
        os.makedirs(self.test_conversations_dir, exist_ok=True)

        # Patch conversation_store to use the temporary directory
        self.patcher_conv_store_init = patch(
            "graph_rag.conversation_store.ConversationStore.__init__",
            autospec=True,
            return_value=None
        )
        self.mock_conv_store_init = self.patcher_conv_store_init.start()
        self.mock_conv_store_init.return_value = None # Explicitly set return_value

        self.patcher_conv_store_add = patch(
            "graph_rag.conversation_store.ConversationStore.add_message",
            autospec=True
        )
        self.mock_conv_store_add = self.patcher_conv_store_add.start()

        self.patcher_conv_store_get_history = patch(
            "graph_rag.conversation_store.ConversationStore.get_history",
            autospec=True
        )
        self.mock_conv_store_get_history = self.patcher_conv_store_get_history.start()

        self.patcher_conv_store_instance = patch(
            "graph_rag.conversation_store.conversation_store",
            MagicMock(spec=type("MockConversationStore", (object,), {
                "init": MagicMock(),
                "add_message": MagicMock(),
                "get_history": MagicMock(),
                "storage_dir": self.test_conversations_dir # Mock the storage_dir
            }))
        )
        self.mock_conv_store_instance = self.patcher_conv_store_instance.start()


        # Mock config.yaml
        self.mock_open = mock_open(read_data=json.dumps({
            "observability": {"metrics_enabled": False},
            "llm": {"model": "gpt-4o", "max_tokens": 512, "rate_limit_per_minute": 60, "redis_url": "redis://localhost:6379/0"},
            "retriever": {"max_chunks": 5}
        }))
        self.mock_open_patch = patch("builtins.open", new=self.mock_open).start()

        # Mock rag_chain
        self.patcher_rag_chain = patch("main.rag_chain", autospec=True)
        self.mock_rag_chain = self.patcher_rag_chain.start()
        self.mock_rag_chain.invoke.return_value = {
            "question": "Who founded Microsoft?",
            "answer": "Bill Gates founded Microsoft [chunk1].",
            "plan": {"intent": "general_rag_query", "anchor": "Microsoft"},
            "sources": ["chunk1"],
            "citation_verification": {"cited_ids": ["chunk1"], "provided_ids": ["chunk1"], "unknown_citations": [], "verified": True, "verification_action": ""},
            "trace_id": "test_trace_id_123"
        }

        # Mock OpenTelemetry tracer and get_current_span
        self.mock_tracer = MagicMock()
        self.mock_tracer_patch = patch("main.tracer", new=self.mock_tracer).start()

        self.mock_current_span = MagicMock(context=SpanContext(trace_id=0x1234, span_id=0x5678, is_remote=False, trace_flags=TraceFlags.SAMPLED))
        self.mock_get_current_span_patch = patch("main.get_current_span", return_value=self.mock_current_span).start()

        # Import app after all mocks are set up
        from main import app
        self.client = TestClient(app)

    def tearDown(self):
        self.patcher_conv_store_init.stop()
        self.patcher_conv_store_add.stop()
        self.patcher_conv_store_get_history.stop()
        self.patcher_conv_store_instance.stop()
        self.mock_open_patch.stop()
        self.patcher_rag_chain.stop()
        self.mock_tracer_patch.stop()
        self.mock_get_current_span_patch.stop()

        # Clean up the temporary conversation directory
        if os.path.exists(self.test_conversations_dir):
            for file in os.listdir(self.test_conversations_dir):
                os.remove(os.path.join(self.test_conversations_dir, file))
            os.rmdir(self.test_conversations_dir)

    def test_post_chat_new_conversation(self):
        response = self.client.post("/api/chat", json={"question": "Test question"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("conversation_id", data)
        self.assertEqual(data["answer"], "Bill Gates founded Microsoft [chunk1].")
        self.assertEqual(data["trace_id"], "test_trace_id_123")
        self.mock_conv_store_add.assert_any_call(
            self.mock_conv_store_instance, unittest.mock.ANY, {"role": "user", "text": "Test question"}
        )
        self.mock_conv_store_add.assert_any_call(
            self.mock_conv_store_instance, unittest.mock.ANY, {"role": "assistant", "text": "Bill Gates founded Microsoft [chunk1].", "trace_id": "test_trace_id_123"}
        )

    def test_post_chat_existing_conversation(self):
        conversation_id = "test_conv_123"
        response = self.client.post("/api/chat", json={"conversation_id": conversation_id, "question": "Another question"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["conversation_id"], conversation_id)
        self.mock_conv_store_add.assert_any_call(
            self.mock_conv_store_instance, conversation_id, {"role": "user", "text": "Another question"}
        )
        self.mock_conv_store_add.assert_any_call(
            self.mock_conv_store_instance, conversation_id, {"role": "assistant", "text": "Bill Gates founded Microsoft [chunk1].", "trace_id": "test_trace_id_123"}
        )

    def test_get_chat_history_found(self):
        conversation_id = "history_conv_456"
        mock_history = [
            {"role": "user", "text": "Hi"},
            {"role": "assistant", "text": "Hello!"}
        ]
        self.mock_conv_store_get_history.return_value = mock_history

        response = self.client.get(f"/api/chat/{conversation_id}/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mock_history)
        self.mock_conv_store_get_history.assert_called_once_with(self.mock_conv_store_instance, conversation_id)

    def test_get_chat_history_not_found(self):
        conversation_id = "non_existent_conv"
        self.mock_conv_store_get_history.return_value = []

        response = self.client.get(f"/api/chat/{conversation_id}/history")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Conversation not found"})
        self.mock_conv_store_get_history.assert_called_once_with(self.mock_conv_store_instance, conversation_id)


# ======================================================================
# FILE: tests/test_citation_verification.py
# SIZE: 7943 bytes
# SHA256: c3f74ba2dce40cc23064e727c5ddb72d483fc7a5bdd0b56f80c8e3bec87823cc
# ======================================================================
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from pydantic import BaseModel, Field
from prometheus_client import REGISTRY
from opentelemetry.trace import TraceFlags, SpanContext

class ExtractedEntities(BaseModel):
    names: list[str] = Field(...)

class ExtractedNode(BaseModel):
    id: str
    type: str

class ExtractedGraph(BaseModel):
    nodes: list[ExtractedNode] = []
    relationships: list[dict] = []

@patch("builtins.open", new_callable=mock_open)
# SECRET REDACTED
@patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password", "OPENAI_API_KEY": "mock_openai_key"}, clear=<REDACTED_SECRET>
@patch("graph_rag.llm_client._get_redis_client")
@patch("graph_rag.cypher_generator.CypherGenerator")
@patch("graph_rag.embeddings.get_embedding_provider")
@patch("graph_rag.planner.call_llm_structured")
@patch("graph_rag.rag.ChatOpenAI")
@patch("graph_rag.rag.tracer")
@patch("graph_rag.rag.get_current_span")
@patch("graph_rag.rag.audit_store.record") # Patch audit_store.record
@patch("graph_rag.planner.logger")
@patch("graph_rag.retriever.logger")
@patch("graph_rag.rag.logger")
@patch("graph_rag.ingest.logger")
@patch("graph_rag.ingest.glob.glob")
@patch("langchain.docstore.document.Document")
@patch("langchain.text_splitter.TokenTextSplitter")
@patch("graph_rag.rag.Retriever")
@patch("graph_rag.retriever.Neo4jClient")
@patch("graph_rag.neo4j_client.Neo4jClient")
class TestCitationVerification(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

        for module_name in ['graph_rag.rag', 'graph_rag.retriever', 'graph_rag.planner', 'graph_rag.llm_client', 'graph_rag.cypher_generator', 'graph_rag.neo4j_client', 'graph_rag.embeddings', 'graph_rag.ingest', 'graph_rag.audit_store']:
            if module_name in sys.modules:
                del sys.modules[module_name]
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    def test_unknown_citation_flags_verification_failure_and_audits(self, mock_neo4j_client_class, mock_retriever_neo4j_client_class, mock_rag_retriever_class, mock_token_text_splitter_class, mock_document_class, mock_glob, mock_ingest_logger, mock_rag_logger, mock_retriever_logger, mock_planner_logger, mock_audit_store_record, mock_get_current_span, mock_rag_tracer, mock_chat_openai_class, mock_call_llm_structured_planner, mock_get_embedding_provider_class, mock_cypher_generator_class, mock_get_redis_client, mock_open):
        # Configure mock_open side_effect
        mock_open.side_effect = [
            mock_open(read_data=json.dumps({
                "schema": { "allow_list_path": "allow_list.json" },
                "guardrails": { "neo4j_timeout": 10, "max_traversal_depth": 2 },
                "llm": { "model": "gpt-4o", "max_tokens": 512, "rate_limit_per_minute": 60, "redis_url": "redis://localhost:6379/0" },
                "retriever": {"max_chunks": 5}
            })).return_value, # For config.yaml
            mock_open(read_data=json.dumps({
                "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
                "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_CHUNK"],
                "properties": {}
            })).return_value, # For allow_list.json
        ]

        # Mock OpenTelemetry current span for trace_id
        test_trace_id = 0x1234567890abcdef1234567890abcdef
        mock_span_context = SpanContext(trace_id=test_trace_id, span_id=0x1234567890abcdef, is_remote=False, trace_flags=TraceFlags.SAMPLED)
        mock_current_span = MagicMock(context=mock_span_context)
        
        mock_tracer_context_manager = MagicMock()
        mock_tracer_context_manager.__enter__.return_value = mock_current_span
        mock_rag_tracer.start_as_current_span.return_value = mock_tracer_context_manager

        mock_get_current_span.return_value = mock_current_span

        # Configure mocks for module-level initializations
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance
        mock_redis_instance.eval.return_value = 1

        mock_cypher_generator_instance = MagicMock()
        mock_cypher_generator_class.return_value = mock_cypher_generator_instance
        mock_cypher_generator_instance.allow_list = {
            "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
            "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_CHUNK"],
            "properties": {}
        }
        mock_cypher_generator_instance.CYPHER_TEMPLATES = {
            "general_rag_query": {"cypher": "MATCH (n) RETURN n LIMIT 1"},
            "company_founder_query": {"cypher": "MATCH (n:Person) RETURN n LIMIT 1"},
        }

        mock_embedding_provider_instance = MagicMock()
        mock_get_embedding_provider_class.return_value = mock_embedding_provider_instance
        mock_embedding_provider_instance.get_embeddings.return_value = [[0.1]*8]

        # Mock Neo4jClient instances
        mock_neo4j_client_instance = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client_instance
        mock_neo4j_client_instance.verify_connectivity.return_value = None
        mock_neo4j_client_instance.execute_read_query.side_effect = [
            [{"output": "structured context"}],
            [{"chunk_id": "chunk1"}],
            [{"id": "chunk1", "text": "chunk1 content"}]
        ]
        
        mock_retriever_neo4j_client_instance = MagicMock()
        mock_retriever_neo4j_client_class.return_value = mock_retriever_neo4j_client_instance
        mock_retriever_neo4j_client_instance.execute_read_query.side_effect = [
            [{"output": "structured context"}],
            [{"chunk_id": "chunk1"}],
            [{"id": "chunk1", "text": "chunk1 content"}]
        ]
        mock_retriever_neo4j_client_instance.verify_connectivity.return_value = None

        mock_chat_openai_instance = MagicMock()
        mock_chat_openai_class.return_value = mock_chat_openai_instance
        # Simulate an answer with an unknown citation "chunk_unknown"
        mock_chat_openai_instance.generate.return_value = MagicMock(generations=[[MagicMock(text="Answer with [chunk1] and [chunk_unknown]")]])

        mock_call_llm_structured_planner.return_value = MagicMock(names=["Microsoft"])

        # Mock the Retriever instance that RAGChain will use, providing only "chunk1"
        mock_retriever_instance = MagicMock()
        mock_rag_retriever_class.return_value = mock_retriever_instance
        mock_retriever_instance.retrieve_context.return_value = {
            "structured": "mock structured context",
            "unstructured": "mock unstructured context [chunk1]",
            "chunk_ids": ["chunk1"] # Only "chunk1" is provided
        }

        # Import rag and instantiate rag_chain AFTER all mocks are set up
        from graph_rag.rag import RAGChain
        rag_chain = RAGChain()

        question = "Who founded Microsoft?"
        response = rag_chain.invoke(question)

        # Assertions for citation verification
        self.assertIn("citation_verification", response)
        self.assertFalse(response["citation_verification"]["verified"])
        self.assertIn("chunk_unknown", response["citation_verification"]["unknown_citations"])
        self.assertEqual(response["citation_verification"]["verification_action"], "human_review_required")

        # Assert audit entry was created
        mock_audit_store_record.assert_called_once_with({
            "event_type": "citation_verification_failed",
            "trace_id": f"{test_trace_id:x}",
            "question": question,
            "unknown_citations": ["chunk_unknown"]
        })


# ======================================================================
# FILE: tests/test_cypher_safety.py
# SIZE: 501 bytes
# SHA256: 40c01c86f01bf59fb5a41bcbcb48abb5bcdd50dede6783eb2fda57cc815c153f
# ======================================================================
# tests/test_cypher_safety.py
import pytest
from graph_rag.cypher_generator import CYPHER_TEMPLATES, CypherGenerator

@pytest.fixture
def cypher_generator_instance():
    return CypherGenerator()

def test_template_validation_blocking(cypher_generator_instance):
    # Temporarily craft a template with an invalid label and test
    bad_template = {"schema_requirements": {"labels": ["NonExistentLabel"], "relationships": []}}
    assert not cypher_generator_instance._validate_template(bad_template)


# ======================================================================
# FILE: tests/test_ingest_llm_validation.py
# SIZE: 5714 bytes
# SHA256: 7596507e10e433c86e7ccdc75cbd45790e50cbb5727315fc6b0a1ed1830f1694
# ======================================================================
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from pydantic import BaseModel
from prometheus_client import REGISTRY

class ExtractedNode(BaseModel):
    id: str
    type: str

class ExtractedGraph(BaseModel):
    nodes: list[ExtractedNode] = []
    relationships: list[dict] = []

# Global patches for module-level imports
@patch("builtins.open", new_callable=mock_open)
# SECRET REDACTED
@patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password", "OPENAI_API_KEY": "mock_openai_key"}, clear=<REDACTED_SECRET>
@patch("graph_rag.llm_client._get_redis_client") # Patch the lazy getter function
@patch("graph_rag.neo4j_client.GraphDatabase")
@patch("graph_rag.neo4j_client.Neo4jClient") # Patch Neo4jClient in its original module
@patch("graph_rag.cypher_generator.CypherGenerator") # Patch CypherGenerator in its original module
@patch("graph_rag.ingest.call_llm_structured") # Patch where it's used
@patch("graph_rag.ingest.logger")
@patch("graph_rag.ingest.glob.glob")
@patch("langchain.docstore.document.Document") # Patch Document from langchain
@patch("langchain.text_splitter.TokenTextSplitter") # Patch TokenTextSplitter from langchain
class TestIngestLLMValidation(unittest.TestCase):

    def setUp(self):
        # Add the project root to sys.path for module discovery
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

        if 'graph_rag.ingest' in sys.modules:
            del sys.modules['graph_rag.ingest']
        if 'graph_rag.cypher_generator' in sys.modules:
            del sys.modules['graph_rag.cypher_generator']
        if 'graph_rag.neo4j_client' in sys.modules:
            del sys.modules['graph_rag.neo4j_client']
        if 'graph_rag.llm_client' in sys.modules:
            del sys.modules['graph_rag.llm_client']
        if 'graph_rag.embeddings' in sys.modules:
            del sys.modules['graph_rag.embeddings']
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    def test_ingest_with_invalid_label_fallback(self, mock_token_text_splitter_class, mock_document_class, mock_glob, mock_logger, mock_call_llm_structured_ingest, mock_cypher_generator_class, mock_neo4j_client_class, mock_graph_database_class, mock_get_redis_client, mock_open):
        # Configure mock_open side_effect
        mock_open.side_effect = [
            mock_open(read_data=json.dumps({
                "schema": {
                    "allow_list_path": "allow_list.json"
                },
                "guardrails": {
                    "neo4j_timeout": 10
                },
                "llm": {
                    "model": "gpt-4o",
                    "max_tokens": 512,
                    "rate_limit_per_minute": 60,
                    "redis_url": "redis://localhost:6379/0"
                }
            })).return_value, # For config.yaml
            mock_open(read_data=json.dumps({
                "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
                "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_PRODUCT"],
                "properties": {}
            })).return_value, # For allow_list.json read by schema_catalog
            mock_open(read_data="---\nid: doc1\n---\ncontent").return_value # For the .md file
        ]
        mock_glob.return_value = ["data/doc1.md"]

        # Configure mocks for module-level initializations
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance # Use the patched getter
# SECRET REDACTED
        mock_redis_instance.eval.return_value =<REDACTED_SECRET>

        mock_driver_instance = MagicMock()
        mock_graph_database_class.driver.return_value = mock_driver_instance
        mock_driver_instance.verify_connectivity.return_value = None

        mock_cypher_generator_instance = MagicMock()
        mock_cypher_generator_class.return_value = mock_cypher_generator_instance
        mock_cypher_generator_instance.allow_list = {
            "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
            "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_PRODUCT"],
            "properties": {}
        }

        # Mock Neo4jClient instance
        mock_client_instance = MagicMock()
        mock_neo4j_client_class.return_value = mock_client_instance
        mock_client_instance.verify_connectivity.return_value = None

        # Mock call_llm_structured to return an invalid node type
        invalid_node_type = "Invalid-Label"
        mock_call_llm_structured_ingest.return_value = ExtractedGraph(nodes=[
            ExtractedNode(id="node1", type=invalid_node_type)
        ])

        # Mock cypher_generator.validate_label
        mock_cypher_generator_instance.validate_label.return_value = "`Entity`"
        
        from graph_rag import ingest
        ingest.process_and_ingest_files()

        # Assert that validate_label was called with the invalid type
        mock_cypher_generator_instance.validate_label.assert_called_once_with(invalid_node_type)
        
        # Assert that the MERGE query used the fallback 'Entity' label
        mock_client_instance.execute_write_query.assert_any_call(
            f"MERGE (n:`Entity` {{id: $id}})", 
            {"id": "node1"}, 
            timeout=10
        )

        # Assert that a warning was logged (though validate_label handles this now)
        # mock_logger.warning.assert_called_once() # This is now handled inside cypher_generator


# ======================================================================
# FILE: tests/test_label_sanitization.py
# SIZE: 728 bytes
# SHA256: 4a8668cbb1c59db8f9e80dd3547187042372e6a8a1beaf5f865d6007c4901b4d
# ======================================================================
# tests/test_label_sanitization.py
import pytest
from graph_rag.cypher_generator import CypherGenerator

@pytest.fixture
def cypher_generator_instance():
    return CypherGenerator()

def test_invalid_label_rejected(cypher_generator_instance):
    assert not cypher_generator_instance._validate_label("User`) DETACH DELETE (n)") 

def test_known_label_allowed(cypher_generator_instance):
    # This depends on allow_list.json — if empty, skip
    labels = cypher_generator_instance.allow_list.get("node_labels", [])
    if not labels:
        pytest.skip("allow_list.json not present")
    assert labels[0] in cypher_generator_instance.allow_list["node_labels"]
    assert cypher_generator_instance._validate_label(labels[0])


# ======================================================================
# FILE: tests/test_label_validation.py
# SIZE: 4338 bytes
# SHA256: 99f075bc78e6311613a5f6392084e897fa2b10f66f935b16f3e80204111f4318
# ======================================================================
import unittest
from unittest.mock import patch, mock_open
import json
import os
import sys
from prometheus_client import REGISTRY

class TestLabelValidation(unittest.TestCase):

    def setUp(self):
        # Clear module caches to ensure fresh imports
        if 'graph_rag.cypher_generator' in sys.modules:
            del sys.modules['graph_rag.cypher_generator']
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_label_valid(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_label("Document"), "`Document`")
        mock_logger.warning.assert_not_called()

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_label_invalid_regex(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_label("bad-label"), "`Entity`")
        mock_logger.warning.assert_called_with("Invalid label 'bad-label' provided. Falling back to default 'Entity'.")

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_label_not_in_allow_list(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_label("NonExistentLabel"), "`Entity`")
        mock_logger.warning.assert_called_with("Invalid label 'NonExistentLabel' provided. Falling back to default 'Entity'.")

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_relationship_type_valid(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_relationship_type("HAS_CHUNK"), "`HAS_CHUNK`")
        mock_logger.warning.assert_not_called()

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_relationship_type_invalid_regex(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_relationship_type("bad-rel"), "`RELATED`")
        mock_logger.warning.assert_called_with("Invalid relationship type 'bad-rel' provided. Falling back to default 'RELATED'.")

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "node_labels": ["Document", "Entity", "Person"],
        "relationship_types": ["HAS_CHUNK", "MENTIONS"],
        "properties": {}
    }))
    @patch("graph_rag.cypher_generator.logger")
    def test_validate_relationship_type_not_in_allow_list(self, mock_logger, mock_file_open):
        import graph_rag.cypher_generator
        gen = graph_rag.cypher_generator.CypherGenerator()
        
        self.assertEqual(gen.validate_relationship_type("NonExistentREL"), "`RELATED`")
        mock_logger.warning.assert_called_with("Invalid relationship type 'NonExistentREL' provided. Falling back to default 'RELATED'.")


# ======================================================================
# FILE: tests/test_llm_client_structured.py
# SIZE: 5902 bytes
# SHA256: b1c3298b58af7abd74a199af3f2cc5e47cff8c649c570c07cee13de7a4e0882d
# ======================================================================
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json
from pydantic import BaseModel
from prometheus_client import REGISTRY

class DummySchema(BaseModel):
    field_a: str
    field_b: int

class TestLLMClientStructured(unittest.TestCase):

    def setUp(self):
        if 'graph_rag.llm_client' in sys.modules:
            del sys.modules['graph_rag.llm_client']
        if 'graph_rag.audit_store' in sys.modules:
            del sys.modules['graph_rag.audit_store']
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("graph_rag.llm_client.redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gpt-4o",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_malformed_json(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_redis_client):
        # Mock consume_token to always allow consumption
        mock_redis_client.eval.return_value = 1

        mock_call_llm_raw.return_value = "this is not json"
        
        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError

        with self.assertRaises(LLMStructuredError) as cm:
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        self.assertIn("Invalid JSON from LLM", str(cm.exception))
        mock_audit_store.record.assert_called_once_with(
            entry={
                "type": "llm_parse_failure",
                "prompt": "test prompt",
                "response": "this is not json",
                "error": unittest.mock.ANY,
                "trace_id": unittest.mock.ANY # trace_id can be None in this test context
            }
        )

    @patch("graph_rag.llm_client.redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gpt-4o",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_validation_error(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_redis_client):
        # Mock consume_token to always allow consumption
        mock_redis_client.eval.return_value = 1

        mock_call_llm_raw.return_value = json.dumps({"field_a": "value", "field_c": 123}) # Missing field_b

        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError

        with self.assertRaises(LLMStructuredError) as cm:
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        self.assertIn("Structured output failed validation", str(cm.exception))
        mock_audit_store.record.assert_called_once_with(
            entry={
                "type": "llm_validation_failed",
                "prompt": "test prompt",
                "response": json.dumps({"field_a": "value", "field_c": 123}),
                "error": unittest.mock.ANY,
                "trace_id": unittest.mock.ANY # trace_id can be None in this test context
            }
        )

    @patch("graph_rag.llm_client.redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gpt-4o",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_rate_limit_exceeded(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_redis_client):
        # Mock consume_token to deny consumption
        mock_redis_client.eval.return_value = 0

        import graph_rag.llm_client
        from graph_rag.llm_client import LLMStructuredError

        with self.assertRaises(LLMStructuredError) as cm:
            graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)
        
        self.assertIn("LLM rate limit exceeded", str(cm.exception))
        mock_call_llm_raw.assert_not_called()
        mock_audit_store.record.assert_not_called()

    @patch("graph_rag.llm_client.redis_client")
    @patch("graph_rag.llm_client.call_llm_raw")
    @patch("graph_rag.llm_client.audit_store")
    @patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True)
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gpt-4o",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        }
    }))
    def test_call_llm_structured_success(self, mock_open, mock_audit_store, mock_call_llm_raw, mock_redis_client):
        # Mock consume_token to always allow consumption
        mock_redis_client.eval.return_value = 1
        mock_call_llm_raw.return_value = json.dumps({"field_a": "value", "field_b": 123})

        import graph_rag.llm_client
        result = graph_rag.llm_client.call_llm_structured("test prompt", DummySchema)

        self.assertIsInstance(result, DummySchema)
        self.assertEqual(result.field_a, "value")
        self.assertEqual(result.field_b, 123)
        mock_audit_store.record.assert_not_called()


# ======================================================================
# FILE: tests/test_neo4j_timeout.py
# SIZE: 1961 bytes
# SHA256: 9fc5e6f9026a99c4713d8c50359ccbef1586ed7ef00f407f2a0410138f44ab1a
# ======================================================================
import unittest
from unittest.mock import patch, MagicMock
import os
from neo4j import exceptions
import sys
from prometheus_client import REGISTRY

# Patch environment variables and GraphDatabase.driver at the module level
# so they are active when graph_rag.neo4j_client is imported.
# SECRET REDACTED
@patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}, clear=<REDACTED_SECRET>
@patch("graph_rag.neo4j_client.GraphDatabase")
class TestNeo4jClientTimeout(unittest.TestCase):

    def setUp(self):
        # Clear the module cache to ensure a fresh import for each test
        if 'graph_rag.neo4j_client' in sys.modules:
            del sys.modules['graph_rag.neo4j_client']
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("graph_rag.neo4j_client.db_query_failed")
    def test_execute_read_query_timeout(self, mock_db_query_failed, mock_graph_database):
        mock_driver_instance = MagicMock()
        mock_graph_database.driver.return_value = mock_driver_instance
        mock_driver_instance.verify_connectivity.return_value = None  # Mock verify_connectivity

        mock_session = MagicMock()
        mock_driver_instance.session.return_value.__enter__.return_value = mock_session
        
        # Simulate a timeout by raising a ClientError
        mock_session.begin_transaction.side_effect = exceptions.ClientError("a", "b", "The transaction has been terminated due to a timeout")

        import graph_rag.neo4j_client
        client = graph_rag.neo4j_client.Neo4jClient()

        result = client.execute_read_query("MATCH (n) RETURN n", timeout=0.1)
        self.assertEqual(result, [])
        mock_driver_instance.session.assert_called_once_with(default_access_mode="READ")
        mock_session.begin_transaction.assert_called_once_with(timeout=0.1)
        mock_db_query_failed.inc.assert_called_once()


# ======================================================================
# FILE: tests/test_observability_import.py
# SIZE: 3487 bytes
# SHA256: 474471b9684ea009348d44c3d2027ace83eafac4974e33705f3cbe710ad8d29d
# ======================================================================
import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from prometheus_client import REGISTRY

class TestObservability(unittest.TestCase):
    def setUp(self):
        # Clear the module cache to ensure a fresh import for each test
        if 'graph_rag.observability' in sys.modules:
            del sys.modules['graph_rag.observability']
        # Clear Prometheus registry to prevent duplicated timeseries errors
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch.dict(os.environ, {"PROMETHEUS_PORT": "0"}, clear=True)
    @patch("graph_rag.observability.start_http_server")
    def test_observability_import_and_metrics_server(self, mock_start_http_server):
        import graph_rag.observability
        self.assertIsNotNone(graph_rag.observability.tracer)
        self.assertIsNotNone(graph_rag.observability.db_query_total)
        self.assertIsNotNone(graph_rag.observability.get_logger(__name__))
        
        graph_rag.observability.start_metrics_server()
        mock_start_http_server.assert_called_once_with(0)

    @patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"}, clear=True)
    @patch("opentelemetry.sdk.trace.TracerProvider")
    @patch("opentelemetry.trace.set_tracer_provider")
    @patch("opentelemetry.sdk.trace.export.BatchSpanProcessor")
    @patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter")
    def test_otel_exporter_otlp_endpoint(self, mock_otlp_span_exporter_class, mock_batch_span_processor_class, mock_set_tracer_provider, mock_tracer_provider_class):
        import graph_rag.observability
        
        mock_tracer_provider_class.assert_called_once()
        mock_provider_instance = mock_tracer_provider_class.return_value
        mock_provider_instance.add_span_processor.assert_called_once()
        
        mock_batch_span_processor_class.assert_called_once()
        
        mock_otlp_span_exporter_class.assert_called_once_with(endpoint="http://localhost:4317")
        span_exporter_instance = mock_otlp_span_exporter_class.return_value

        (call_args, _) = mock_batch_span_processor_class.call_args
        span_exporter_passed_to_processor = call_args[0]
        
        self.assertEqual(span_exporter_passed_to_processor, span_exporter_instance)

    @patch.dict(os.environ, {}, clear=True)
    @patch("opentelemetry.sdk.trace.TracerProvider")
    @patch("opentelemetry.trace.set_tracer_provider")
    @patch("opentelemetry.sdk.trace.export.BatchSpanProcessor")
    @patch("opentelemetry.sdk.trace.export.ConsoleSpanExporter")
    def test_otel_exporter_console_fallback(self, mock_console_span_exporter_class, mock_batch_span_processor_class, mock_set_tracer_provider, mock_tracer_provider_class):
        import graph_rag.observability
        
        mock_tracer_provider_class.assert_called_once()
        mock_provider_instance = mock_tracer_provider_class.return_value
        mock_provider_instance.add_span_processor.assert_called_once()

        mock_batch_span_processor_class.assert_called_once()
        
        mock_console_span_exporter_class.assert_called_once()
        span_exporter_instance = mock_console_span_exporter_class.return_value

        (call_args, _) = mock_batch_span_processor_class.call_args
        span_exporter_passed_to_processor = call_args[0]
        
        self.assertEqual(span_exporter_passed_to_processor, span_exporter_instance)


# ======================================================================
# FILE: tests/test_planner_llm_integration.py
# SIZE: 4884 bytes
# SHA256: 5f1766252b640bcce733741adf7285e1a428cb09521d9f1be79de6dba42f8b9f
# ======================================================================
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json
from pydantic import BaseModel
from prometheus_client import REGISTRY

# Global patches for module-level imports
@patch("graph_rag.llm_client._get_redis_client") # Patch the lazy getter function
@patch("graph_rag.neo4j_client.GraphDatabase")
@patch("graph_rag.cypher_generator.CypherGenerator")
class TestPlannerLLMIntegration(unittest.TestCase):

    def setUp(self):
        # Clear module caches to ensure fresh imports
        if 'graph_rag.planner' in sys.modules:
            del sys.modules['graph_rag.planner']
        if 'graph_rag.llm_client' in sys.modules:
            del sys.modules['graph_rag.llm_client']
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch("graph_rag.planner.call_llm_structured") # Patch where it's used in planner
    @patch("graph_rag.planner.logger")
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gpt-4o",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        },
        "schema": {"allow_list_path": "allow_list.json"}
    }))
    def test_generate_plan_with_llm_entities(self, mock_open, mock_logger, mock_call_llm_structured_planner, mock_cypher_generator_class, mock_graph_database_class, mock_get_redis_client):
        # Configure mocks for module-level initializations
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance # Use the patched getter
        mock_redis_instance.eval.return_value = 1 # Allow token consumption

        mock_driver_instance = MagicMock()
        mock_graph_database_class.driver.return_value = mock_driver_instance
        mock_driver_instance.verify_connectivity.return_value = None

        mock_cypher_generator_instance = MagicMock()
        mock_cypher_generator_class.return_value = mock_cypher_generator_instance
        mock_cypher_generator_instance.allow_list = {
            "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
            "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_PRODUCT"],
            "properties": {}
        }

        mock_call_llm_structured_planner.return_value = MagicMock(names=["Alice", "Bob"])
        import graph_rag.planner
        plan = graph_rag.planner.generate_plan("Who founded Microsoft?")
        self.assertEqual(plan.intent, "company_founder_query")
        self.assertEqual(plan.anchor_entity, "Alice")
        self.assertEqual(plan.question, "Who founded Microsoft?")
        mock_logger.warning.assert_not_called()

    @patch("graph_rag.planner.call_llm_structured") # Patch where it's used in planner
    @patch("graph_rag.planner.logger")
    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({
        "llm": {
            "model": "gpt-4o",
            "max_tokens": 512,
            "rate_limit_per_minute": 60,
            "redis_url": "redis://localhost:6379/0"
        },
        "schema": {"allow_list_path": "allow_list.json"}
    }))
    def test_generate_plan_llm_error_fallback(self, mock_open, mock_logger, mock_call_llm_structured_planner, mock_cypher_generator_class, mock_graph_database_class, mock_get_redis_client):
        # Configure mocks for module-level initializations
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance # Use the patched getter
        mock_redis_instance.eval.return_value = 1 # Allow token consumption

        mock_driver_instance = MagicMock()
        mock_graph_database_class.driver.return_value = mock_driver_instance
        mock_driver_instance.verify_connectivity.return_value = None

        mock_cypher_generator_instance = MagicMock()
        mock_cypher_generator_class.return_value = mock_cypher_generator_instance
        mock_cypher_generator_instance.allow_list = {
            "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
            "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_PRODUCT"],
            "properties": {}
        }

        from graph_rag.llm_client import LLMStructuredError
        mock_call_llm_structured_planner.side_effect = LLMStructuredError("LLM failed")
        import graph_rag.planner
        plan = graph_rag.planner.generate_plan("Who founded Microsoft?")
        self.assertEqual(plan.intent, "company_founder_query")
        self.assertIsNone(plan.anchor_entity)
        self.assertEqual(plan.question, "Who founded Microsoft?")
        mock_logger.warning.assert_called_once_with("LLM entity extraction failed: LLM failed. Falling back to empty entities.")


# ======================================================================
# FILE: tests/test_tracing_integration.py
# SIZE: 9113 bytes
# SHA256: 5b7b9c498fb0dd4b9385a6bf9c0a629a0fdc8386dbf9f5f8e5555cb19c727538
# ======================================================================
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from pydantic import BaseModel, Field
from prometheus_client import REGISTRY
from opentelemetry.trace import TraceFlags, SpanContext, Status, StatusCode

class ExtractedEntities(BaseModel):
    names: list[str] = Field(...)

class ExtractedNode(BaseModel):
    id: str
    type: str

class ExtractedGraph(BaseModel):
    nodes: list[ExtractedNode] = []
    relationships: list[dict] = []

# Global patches for module-level imports
@patch("builtins.open", new_callable=mock_open)
# SECRET REDACTED
@patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password", "OPENAI_API_KEY": "mock_openai_key"}, clear=<REDACTED_SECRET>
@patch("graph_rag.llm_client._get_redis_client") # Patch the lazy getter function
@patch("graph_rag.cypher_generator.CypherGenerator") # Patch CypherGenerator in its original module
@patch("graph_rag.embeddings.get_embedding_provider") # Patch the embedding getter function
@patch("graph_rag.planner.call_llm_structured") # Patch where it's used in planner
@patch("graph_rag.rag.ChatOpenAI") # Patch ChatOpenAI in rag
@patch("graph_rag.rag.tracer") # Patch tracer in rag
@patch("graph_rag.rag.get_current_span") # Patch get_current_span in rag
@patch("graph_rag.planner.logger")
@patch("graph_rag.retriever.logger")
@patch("graph_rag.rag.logger")
@patch("graph_rag.ingest.logger")
@patch("graph_rag.ingest.glob.glob")
@patch("langchain.docstore.document.Document") # Patch Document from langchain
@patch("langchain.text_splitter.TokenTextSplitter") # Patch TokenTextSplitter from langchain
@patch("graph_rag.rag.Retriever") # Patch Retriever in rag
@patch("graph_rag.retriever.Neo4jClient") # Patch Neo4jClient in retriever module
@patch("graph_rag.neo4j_client.Neo4jClient") # Patch Neo4jClient in its original module
class TestTracingIntegration(unittest.TestCase):

    def setUp(self):
        # Add the project root to sys.path for module discovery
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

        # Clear module caches to ensure fresh imports
        for module_name in ['graph_rag.rag', 'graph_rag.retriever', 'graph_rag.planner', 'graph_rag.llm_client', 'graph_rag.cypher_generator', 'graph_rag.neo4j_client', 'graph_rag.embeddings', 'graph_rag.ingest']:
            if module_name in sys.modules:
                del sys.modules[module_name]
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    def test_rag_chain_returns_trace_id_and_sources(self, mock_neo4j_client_class, mock_retriever_neo4j_client_class, mock_rag_retriever_class, mock_token_text_splitter_class, mock_document_class, mock_glob, mock_ingest_logger, mock_rag_logger, mock_retriever_logger, mock_planner_logger, mock_get_current_span, mock_rag_tracer, mock_chat_openai_class, mock_call_llm_structured_planner, mock_get_embedding_provider_class, mock_cypher_generator_class, mock_get_redis_client, mock_open):
        # Configure mock_open side_effect
        mock_open.side_effect = [
            mock_open(read_data=json.dumps({
                "schema": {
                    "allow_list_path": "allow_list.json"
                },
                "guardrails": {
                    "neo4j_timeout": 10,
                    "max_traversal_depth": 2
                },
                "llm": {
                    "model": "gpt-4o",
                    "max_tokens": 512,
                    "rate_limit_per_minute": 60,
                    "redis_url": "redis://localhost:6379/0"
                },
                "retriever": {"max_chunks": 5}
            })).return_value, # For config.yaml
            mock_open(read_data=json.dumps({
                "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
                "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_CHUNK"],
                "properties": {}
            })).return_value, # For allow_list.json read by schema_catalog
        ]

        # Mock OpenTelemetry current span for trace_id
        test_trace_id = 0x1234567890abcdef1234567890abcdef # Changed to valid hexadecimal literal
        mock_span_context = SpanContext(trace_id=test_trace_id, span_id=0x1234567890abcdef, is_remote=False, trace_flags=TraceFlags.SAMPLED) # Set non-zero span_id
        mock_current_span = MagicMock(context=mock_span_context) # Mock a Span object with a context attribute
        
        # Configure mock_rag_tracer.start_as_current_span to return a context manager that yields mock_current_span
        mock_tracer_context_manager = MagicMock()
        mock_tracer_context_manager.__enter__.return_value = mock_current_span
        mock_rag_tracer.start_as_current_span.return_value = mock_tracer_context_manager

        mock_get_current_span.return_value = mock_current_span # Directly mock get_current_span

        # Configure mocks for module-level initializations
        mock_redis_instance = MagicMock()
        mock_get_redis_client.return_value = mock_redis_instance # Use the patched getter
# SECRET REDACTED
        mock_redis_instance.eval.return_value =<REDACTED_SECRET>

        # Configure the mock Neo4jClient instance that graph_rag.neo4j_client.Neo4jClient will return
        mock_neo4j_client_instance = MagicMock()
        mock_neo4j_client_class.return_value = mock_neo4j_client_instance
        mock_neo4j_client_instance.verify_connectivity.return_value = None # Explicitly mock verify_connectivity to do nothing
        mock_neo4j_client_instance.execute_read_query.side_effect = [
            [{"output": "structured context"}], # For structured query
            [{"chunk_id": "chunk1"}], # For unstructured query (vector search)
            [{"id": "chunk1", "text": "chunk1 content"}] # For hierarchy expand
        ]

        # Mock Neo4jClient within the retriever module
        mock_retriever_neo4j_client_instance = MagicMock()
        mock_retriever_neo4j_client_class.return_value = mock_retriever_neo4j_client_instance
        mock_retriever_neo4j_client_instance.execute_read_query.side_effect = [
            [{"output": "structured context"}], # For structured query
            [{"chunk_id": "chunk1"}], # For unstructured query (vector search)
            [{"id": "chunk1", "text": "chunk1 content"}] # For hierarchy expand
        ]
        mock_retriever_neo4j_client_instance.verify_connectivity.return_value = None # Ensure connectivity check passes

        mock_cypher_generator_instance = MagicMock()
        mock_cypher_generator_class.return_value = mock_cypher_generator_instance
        mock_cypher_generator_instance.allow_list = {
            "node_labels": ["Document", "Chunk", "Entity", "__Entity__", "Person", "Organization", "Product"],
            "relationship_types": ["PART_OF", "HAS_CHUNK", "MENTIONS", "FOUNDED", "HAS_CHUNK"],
            "properties": {}
        }
        mock_cypher_generator_instance.CYPHER_TEMPLATES = {
            "general_rag_query": {"cypher": "MATCH (n) RETURN n LIMIT 1"},
            "company_founder_query": {"cypher": "MATCH (n:Person) RETURN n LIMIT 1"},
        }

        mock_embedding_provider_instance = MagicMock()
        mock_get_embedding_provider_class.return_value = mock_embedding_provider_instance
        mock_embedding_provider_instance.get_embeddings.return_value = [[0.1]*8] # Mock embedding

        mock_chat_openai_instance = MagicMock()
        mock_chat_openai_class.return_value = mock_chat_openai_instance
        mock_chat_openai_instance.generate.return_value = MagicMock(generations=[[MagicMock(text="Answer with [chunk1]")]])

        mock_call_llm_structured_planner.return_value = MagicMock(names=["Microsoft"])

        # Mock the Retriever instance that RAGChain will use
        mock_retriever_instance = MagicMock()
        mock_rag_retriever_class.return_value = mock_retriever_instance
        mock_retriever_instance.retrieve_context.return_value = {
            "structured": "mock structured context",
            "unstructured": "mock unstructured context [chunk1]",
            "chunk_ids": ["chunk1"]
        }

        # Import rag and instantiate rag_chain AFTER all mocks are set up
        from graph_rag.rag import RAGChain
        rag_chain = RAGChain()

        question = "Who founded Microsoft?"
        response = rag_chain.invoke(question)

        self.assertIn("trace_id", response)
        self.assertEqual(response["trace_id"], f"{test_trace_id:x}")
        self.assertIn("sources", response)
        self.assertEqual(response["sources"], ["chunk1"])

        # Verify spans were created (simplified check, more robust checks would involve OTLP mock receiver)
        mock_rag_tracer.start_as_current_span.assert_any_call("rag.invoke")
        # Verify retriever spans are called
        # These will now be called within the mocked retriever, so we check on the mock_retriever_instance
        mock_retriever_instance.retrieve_context.assert_called_once()


# ======================================================================
# FILE: .github/workflows/ci.yml
# SIZE: 572 bytes
# SHA256: cf2232945fe7b8439f9ccc74527586b40084050a756dd058a1520dc7bb77b284
# ======================================================================
name: Python CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python 3.11
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Run tests
      run: |
        python -m pytest -q
        # Optional: Run flake8 if available
        # pip install flake8
        # flake8 .


# ======================================================================
# FILE: docs/req_doc.txt
# SIZE: 8103 bytes
# SHA256: a472c0faf9214e22b879e564513db3d9f414f6fc96765d9be8e3131ddc8b6e60
# ======================================================================
1.0 Introduction 
This document outlines the solution requirements for an AI Agent using a Graph 
Database. The project aims to develop an intelligent web application that enables end 
users to interact with a Neo4j GraphRAG through a natural language (NL) conversational 
chatbot. The system will leverage Natural Language Processing (NLP), embedding 
similarity, and a Graph RAG (Retrieval-Augmented Generation) approach to convert user 
queries into validated Cypher queries, providing structured, contextual, and secure 
responses. 

2.0 Project Objectives 
The primary goal is to build a robust and user-friendly platform that makes complex graph 
data accessible to a broad audience. The key objectives are: 
• Provide a Conversational Interface: Offer a chatbot that allows users to ask 
questions in natural, human-like language. 
• Intelligent Query Translation: Accurately convert user's natural language 
questions into valid and safe Cypher queries. 
• Deliver Rich, Contextual Responses: Present query results in structured formats 
(tabular, graph, etc.), augmented with summaries, citations, and explanations.

3.0 Scope of Work 
The scope of this project encompasses the entire pipeline, from user interaction to data 
retrieval and response generation. The following components are in scope: 
3.1 Chatbot & User Interface 
The front-end will feature a conversational chatbot interface capable of displaying different 
types of query results. 
• Conversational Chatbot: The core interface for user interaction. 
• Structured Result Views: Support for displaying results in multiple formats, 
including tabular data, network graphs, and free-text summaries. 
3.2 Natural Language Understanding (NLU) 
The system will process and interpret user queries to understand their intent and the 
entities they are referencing. 
• User Query Ingestion: Accepts and processes natural language questions from the 
user. 
• Semantic Mapping: Uses embeddings and heuristic matching to map user
provided terms (e.g., "products," "customers") to the correct Neo4j schema terms 
(e.g., node labels, relationship types, property names). 
3.3 Schema Catalog & Embeddings 
A critical part of the NLU process involves a pre-built knowledge base of the graph schema. 
• Allow-Listed Graph Schema: The system will maintain a strict catalog of the Neo4j 
schema, including labels, relationships, property names, and their data types. 
• Embedding Generation: A pipeline will generate and store vector embeddings for 
all schema terms and potential synonyms, which will be used for similarity search. 
3.4 Query Generation 
The system's intelligence is rooted in its ability to securely and accurately create Cypher 
queries. 
• Validated Cypher Generation: Convert NL queries into a parameterized, validated 
Cypher query. 
• Security & Constraints: Enforce strict adherence to the allow-listed schema to 
prevent unauthorized or malicious queries. All generated queries will be restricted 
to the predefined data model. 
3.5 Execution & Response 
This phase covers the execution of the generated query and the post-processing of the 
results. 
• Cypher Execution: The system will execute the generated Cypher query against the 
Neo4j database. 
• GraphRAG Augmentation: Results will be enriched by fetching adjacent nodes, 
related documents, and snippets to provide context. 
• LLM Integration: A large language model (LLM) will be used to generate a 
contextual summary and explanation of the structured results. 
• Structured Output: The final response will include the structured data view and an 
optional textual summary with citations linking back to the source data. 
3.6 Guardrails & Observability 
To ensure reliability and security, the system will include robust monitoring and control 
mechanisms. 
• System Guardrails: Implement safeguards such as query timeouts, graph 
traversal depth limits, and a strict read-only execution mode to prevent data 
modification. 
• Observability: Comprehensive logging, monitoring, and dashboards will be 
implemented to track key metrics like query latency, error rates, and embedding 
match scores. 

4.0 Functional Requirements 
4.1 User Features 
• Chat Interface with History: The application shall provide a continuous 
conversation history for the user. 
• Interaction Options: Users shall have the ability to rephrase questions or drill down 
into details from a previous response. 
• Output Formats: The system shall display results in multiple formats: 
o Tabular: For simple, structured data. 
o Graph View: To visualize relationships between nodes. 
o Plain Text: For contextual summaries and explanations. 
• Contextual Information: The system shall provide citations and contextual 
explanations alongside the core data. 
• User Feedback: Users shall be able to provide feedback on the accuracy of the 
answer (e.g., a "thumbs up/down" or rating). 
4.2 System Features 
• Automated Schema Ingestion: The system shall automatically ingest and parse 
the schema from the Neo4j database. 
• Synonym Expansion: The system shall support synonym expansion and leverage 
embedding similarity for accurate term mapping. 
• Parameterized Queries: The system shall generate parameterized Cypher queries 
to prevent Cypher injection attacks. 
• GraphRAG Integration: The system shall augment query results with related data 
points to provide context for the LLM. 
• Monitoring & Metrics: The system shall track and expose metrics for query latency, 
error rates, and the quality of embedding matches. 

5.0 Technical Requirements 
5.1 Application Architecture 
• Frontend: The user interface will be built using React. 
• Backend: The business logic and API layer will be implemented in Python or .NET. 
• Database: Neo4j will serve as the primary graph database. 
• Vector Store: Vector embeddings will be stored and managed using Neo4j's native 
vector index or an external vector store. 
• LLM Integration: The system will integrate with a pre-selected LLM provider (e.g., 
OpenAI/GPT) for summarization and query generation. 
5.2 Schema Management 
• Schema Extraction: The system shall include an automated process to extract the 
graph schema directly from Neo4j. 
• Allow-Listed Schema: The extracted schema will be stored as an allow-list, serving 
as the single source of truth for query generation. 
• Embedding Pipeline: An automated pipeline will generate and update embeddings 
for schema elements and their synonyms, ensuring the NLU model remains current 
with the graph data model. 
5.3 Query Processing Pipeline 
The user query will follow a well-defined pipeline: 
1. NL Query Input: User submits a natural language question. 
2. Semantic Search: An embedding similarity search combined with heuristics 
matches NL terms to the allow-listed schema. 
3. Cypher Generation: The system constructs a parameterized Cypher query based 
on the matched schema terms and query intent. 
4. Guardrail Enforcement: The query is checked against guardrails for safety (e.g., 
traversal depth, read-only mode). 
5. Cypher Execution: The query is executed against the Neo4j database. 
6. GraphRAG Augmentation: Results are retrieved and enriched with additional 
contextual information from the graph. 
7. LLM Summarization: The LLM receives the structured results and augmented 
context to generate a natural language summary. 
8. Response Delivery: A final, structured response with optional summaries and 
citations is returned to the user. 
5.4 Security & Governance 
• Read-Only Execution: All queries executed by the AI agent will be read-only (no 
writes or mutations) to protect data integrity. 
• Input Validation: All user inputs will be sanitized and validated to prevent malicious 
input. 
• Observability: The system will implement detailed logging and monitoring for audit 
trails of all user queries and system responses. 
• Audit Trail: A complete record of all user queries, generated Cypher, and system 
responses will be maintained for auditing and debugging

# ======================================================================
# FILE: TASKS.md
# SIZE: 352 bytes
# SHA256: 4991d3f81e225a382a68f8b7d01febf299637b707024ecf86af5db1698548ddd
# ======================================================================
1. Add observability (graph_rag/observability.py)
2. Harden neo4j client (timeouts + metrics)
3. Generate allow_list.json via schema_catalog
4. Add label validation & sanitize dynamic labels
5. Add llm_client (structured + rate limiter)
6. Refactor planner/ingest to use llm_client
7. Instrument retriever/rag for tracing & citations
8. Add tests + CI


# ======================================================================
# FILE: audit_log.jsonl
# SIZE: 0 bytes
# SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
# ======================================================================


# ======================================================================
# MANIFEST
# ======================================================================

MANIFEST = {
  "README.md": {
    "start_line": 120,
    "end_line": 141,
    "size_bytes": 596,
    "sha256": "ada4248a1256a41b2a677679d9101be4a61944eb900a7d8871d759842dab125c"
  },
  "config.yaml": {
    "start_line": 142,
    "end_line": 174,
    "size_bytes": 398,
    "sha256": "019df98e8bb6565f668c7c65acd68d355ae788161c7a186c74b13168589c7c79"
  },
  "requirements.txt": {
    "start_line": 175,
    "end_line": 198,
    "size_bytes": 249,
    "sha256": "05dc869eca45f132cdc97cbae5b4862c0c956849aeb0e683b83eb3ce8774937e"
  },
  "Dockerfile": {
    "start_line": 199,
    "end_line": 219,
    "size_bytes": 211,
    "sha256": "7065cb4983772105fd2afefe6f1be7a4afd7b0842b09c82e43b3680320ab8396"
  },
  "docker-compose.yml": {
    "start_line": 220,
    "end_line": 280,
    "size_bytes": 1243,
    "sha256": "3c5e47a68b6478b915bee16a318efb9a0b9728f75aebd8ec35ec4240f44cdd9a"
  },
  "allow_list.json": {
    "start_line": 281,
    "end_line": 306,
    "size_bytes": 267,
    "sha256": "c00b27d3b4e65e5bff50c24dea781836071bb0cae841ab2db273b33a68374e09"
  },
  "database/schema.cypher": {
    "start_line": 307,
    "end_line": 325,
    "size_bytes": 688,
    "sha256": "e8e688360cdde9c6e63745b76fa653adc211fd501159688672ceea717e91d8e4"
  },
  "main.py": {
    "start_line": 326,
    "end_line": 383,
    "size_bytes": 1603,
    "sha256": "cfd681ddc970a8fde83405c7ee07980176c47533fce9dfb3b30db535882b28fc"
  },
  "graph_rag/__init__.py": {
    "start_line": 384,
    "end_line": 392,
    "size_bytes": 24,
    "sha256": "8a5b4a2b8d68377b07886b4e8f1359263f78d3a61a192e50d291b0f68e9af42c"
  },
  "graph_rag/audit_store.py": {
    "start_line": 393,
    "end_line": 425,
    "size_bytes": 725,
    "sha256": "5b62dbf7b996d53bd7089eb0c0b083253f71a1e0e9c452566460288cf342b54a"
  },
  "graph_rag/conversation_store.py": {
    "start_line": 426,
    "end_line": 481,
    "size_bytes": 2010,
    "sha256": "63bdfc8ea91c1bc4e65e6d2dc78a10caa0cc4ddb027042e6b8bb7f0eb52b144f"
  },
  "graph_rag/cypher_generator.py": {
    "start_line": 482,
    "end_line": 571,
    "size_bytes": 3397,
    "sha256": "00d2e2f4463ab42ea45b7279d2d0dabc229c30071aaf9fdc56a2a49633f2e0d4"
  },
  "graph_rag/embeddings.py": {
    "start_line": 572,
    "end_line": 630,
    "size_bytes": 1736,
    "sha256": "538343f26366793232e323e470ca5d505d6487dc5d44563d1fc0b28655a706ec"
  },
  "graph_rag/ingest.py": {
    "start_line": 631,
    "end_line": 716,
    "size_bytes": 3712,
    "sha256": "69199205566e60401d919bdaac21b4501444ce4f8ccbb424a12d4ad2c2648113"
  },
  "graph_rag/llm_client.py": {
    "start_line": 717,
    "end_line": 834,
    "size_bytes": 4366,
    "sha256": "f322991d0053f11a4c77fb5ef2bd4cf01e89306cf65e21ae021197fba0915411"
  },
  "graph_rag/neo4j_client.py": {
    "start_line": 835,
    "end_line": 941,
    "size_bytes": 4250,
    "sha256": "cd050e50944008cc973e6f8ee22b487ee6fcad10302a8cc485d210e05f00f73b"
  },
  "graph_rag/observability.py": {
    "start_line": 942,
    "end_line": 1006,
    "size_bytes": 2251,
    "sha256": "f41caf6f75f4978fc593e697fa1d6a55ab3e4462dac034f6b8f0bcc45ffdbb77"
  },
  "graph_rag/planner.py": {
    "start_line": 1007,
    "end_line": 1053,
    "size_bytes": 1384,
    "sha256": "5460b59190551c8a147e7878c2fcf3e6420e7f1ebb41f24cefbe9f192d8bc93d"
  },
  "graph_rag/rag.py": {
    "start_line": 1054,
    "end_line": 1136,
    "size_bytes": 2947,
    "sha256": "79ede17f215d8c41f0aaacfe0655fad744013573ea6f3f9c31102e539cccb84e"
  },
  "graph_rag/retriever.py": {
    "start_line": 1137,
    "end_line": 1214,
    "size_bytes": 3764,
    "sha256": "57190bd250c57dafafee29f335f1b8a8b499ec9c299349cd971d3abc26691676"
  },
  "graph_rag/schema_catalog.py": {
    "start_line": 1215,
    "end_line": 1263,
    "size_bytes": 2013,
    "sha256": "cd500be0b6843c676caab45ba7f997eef0db5c229cc9a0fbfbb59e86466a8077"
  },
  "graph_rag/utils.py": {
    "start_line": 1264,
    "end_line": 1275,
    "size_bytes": 133,
    "sha256": "906176c39f3a193b57390a5369fa2e58da2445d7da7e0fc10911f5e45eec852c"
  },
  "tests/test_api_endpoints.py": {
    "start_line": 1276,
    "end_line": 1452,
    "size_bytes": 7784,
    "sha256": "209c32eb2967877d7a557aa1bdfa4cb2fba2210bfa32d775d5a6c2252e51e264"
  },
  "tests/test_citation_verification.py": {
    "start_line": 1453,
    "end_line": 1615,
    "size_bytes": 7943,
    "sha256": "c3f74ba2dce40cc23064e727c5ddb72d483fc7a5bdd0b56f80c8e3bec87823cc"
  },
  "tests/test_cypher_safety.py": {
    "start_line": 1616,
    "end_line": 1635,
    "size_bytes": 501,
    "sha256": "40c01c86f01bf59fb5a41bcbcb48abb5bcdd50dede6783eb2fda57cc815c153f"
  },
  "tests/test_ingest_llm_validation.py": {
    "start_line": 1636,
    "end_line": 1764,
    "size_bytes": 5714,
    "sha256": "7596507e10e433c86e7ccdc75cbd45790e50cbb5727315fc6b0a1ed1830f1694"
  },
  "tests/test_label_sanitization.py": {
    "start_line": 1765,
    "end_line": 1790,
    "size_bytes": 728,
    "sha256": "4a8668cbb1c59db8f9e80dd3547187042372e6a8a1beaf5f865d6007c4901b4d"
  },
  "tests/test_label_validation.py": {
    "start_line": 1791,
    "end_line": 1891,
    "size_bytes": 4338,
    "sha256": "99f075bc78e6311613a5f6392084e897fa2b10f66f935b16f3e80204111f4318"
  },
  "tests/test_llm_client_structured.py": {
    "start_line": 1892,
    "end_line": 2041,
    "size_bytes": 5902,
    "sha256": "b1c3298b58af7abd74a199af3f2cc5e47cff8c649c570c07cee13de7a4e0882d"
  },
  "tests/test_neo4j_timeout.py": {
    "start_line": 2042,
    "end_line": 2090,
    "size_bytes": 1961,
    "sha256": "9fc5e6f9026a99c4713d8c50359ccbef1586ed7ef00f407f2a0410138f44ab1a"
  },
  "tests/test_observability_import.py": {
    "start_line": 2091,
    "end_line": 2167,
    "size_bytes": 3487,
    "sha256": "474471b9684ea009348d44c3d2027ace83eafac4974e33705f3cbe710ad8d29d"
  },
  "tests/test_planner_llm_integration.py": {
    "start_line": 2168,
    "end_line": 2272,
    "size_bytes": 4884,
    "sha256": "5f1766252b640bcce733741adf7285e1a428cb09521d9f1be79de6dba42f8b9f"
  },
  "tests/test_tracing_integration.py": {
    "start_line": 2273,
    "end_line": 2446,
    "size_bytes": 9113,
    "sha256": "5b7b9c498fb0dd4b9385a6bf9c0a629a0fdc8386dbf9f5f8e5555cb19c727538"
  },
  ".github/workflows/ci.yml": {
    "start_line": 2447,
    "end_line": 2481,
    "size_bytes": 572,
    "sha256": "cf2232945fe7b8439f9ccc74527586b40084050a756dd058a1520dc7bb77b284"
  },
  "docs/req_doc.txt": {
    "start_line": 2482,
    "end_line": 2627,
    "size_bytes": 8103,
    "sha256": "a472c0faf9214e22b879e564513db3d9f414f6fc96765d9be8e3131ddc8b6e60"
  },
  "TASKS.md": {
    "start_line": 2628,
    "end_line": 2643,
    "size_bytes": 352,
    "sha256": "4991d3f81e225a382a68f8b7d01febf299637b707024ecf86af5db1698548ddd"
  },
  "audit_log.jsonl": {
    "start_line": 2644,
    "end_line": 2651,
    "size_bytes": 0,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  }
}

TOTAL_FILES = 37
TOTAL_BYTES = 99349

# ======================================================================
# END OF DUMP
# ======================================================================