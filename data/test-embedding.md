---
id: test-doc-1
title: Test Document for Embeddings
author: Test Author
---

This is a test document to verify that chunk embeddings are created during ingestion.

The document contains multiple sentences to ensure it gets split into chunks properly. Each chunk should receive an embedding vector when the RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED flag is set to true.

This content should be processed by the ingestion pipeline and create Chunk nodes with embedding properties.
