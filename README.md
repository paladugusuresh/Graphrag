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
