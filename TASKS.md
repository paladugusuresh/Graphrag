1. Add observability (graph_rag/observability.py)
2. Harden neo4j client (timeouts + metrics)
3. Generate allow_list.json via schema_catalog
4. Add label validation & sanitize dynamic labels
5. Add llm_client (structured + rate limiter)
6. Refactor planner/ingest to use llm_client
7. Instrument retriever/rag for tracing & citations
8. Add tests + CI
