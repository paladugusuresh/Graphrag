# Embedding Migration Guide: OpenAI → Gemini

## Summary

The migration from OpenAI to Google Gemini changes the embedding dimensions:
- **OpenAI text-embedding-3-small**: 1536 dimensions
- **Gemini text-embedding-004**: 768 dimensions

## Impact

The codebase **automatically handles dimension changes** through dynamic detection in `graph_rag/schema_embeddings.py` (line 227):

```python
embedding_dim = len(schema_data[0]['embedding']) if schema_data else 1536
```

## Migration Steps

### Option 1: Fresh Start (Recommended for Development)

1. **Drop existing vector indices:**
   ```cypher
   DROP INDEX chunk_embeddings IF EXISTS;
   DROP INDEX schema_embeddings IF EXISTS;
   ```

2. **Re-run schema embedding population:**
   ```python
   from graph_rag.schema_embeddings import upsert_schema_embeddings
   upsert_schema_embeddings(neo4j_client, schema_data, index_name="schema_embeddings")
   ```
   
   The index will be created automatically with 768 dimensions.

3. **Re-ingest documents:**
   ```python
   from graph_rag.ingest import ingest_documents
   ingest_documents(["path/to/docs"])
   ```

### Option 2: Preserve Existing Data (Production)

If you must preserve existing embedded data:

1. **Keep using OpenAI for embeddings temporarily** by setting environment variable:
   ```bash
   # This is NOT recommended long-term but allows gradual migration
   # You would need to maintain both embedding models
   ```

2. **OR Re-embed all existing data:**
   - Export existing document IDs
   - Delete old embeddings
   - Re-ingest with new Gemini embeddings

### For Testing

Tests use **mock embeddings with 8 dimensions** which remain unchanged and work correctly:

```python
# graph_rag/embeddings.py
return [[float(len(t))] * 8 for t in texts]  # Mock embeddings
```

## Code Changes

### ✅ Automatic Dimension Detection

The `upsert_schema_embeddings()` function automatically detects dimensions from the actual embeddings:

```python
# graph_rag/schema_embeddings.py:227
embedding_dim = len(schema_data[0]['embedding']) if schema_data else 1536
```

### ⚠️ Fallback Dimension

There's a hardcoded fallback to `1536` when no schema data exists. Update this if needed:

```python
# Before
embedding_dim = len(schema_data[0]['embedding']) if schema_data else 1536

# Suggested (if you want to default to Gemini dimensions)
embedding_dim = len(schema_data[0]['embedding']) if schema_data else 768
```

## Verification

After migration, verify vector indices:

```cypher
SHOW INDEXES YIELD name, type, options 
WHERE type = 'VECTOR'
RETURN name, options;
```

Expected output should show `vector.dimensions: 768` for Gemini embeddings.

## No Migration Script Needed

The codebase handles dimension changes **automatically**. Simply:
1. Drop old indices (or let them be recreated)
2. Re-run embedding population with new Gemini API
3. Indices are created with correct dimensions automatically

## References

- Gemini Embedding API: https://ai.google.dev/gemini-api/docs/embeddings
- Model: `models/text-embedding-004` (768 dimensions)
- Neo4j Vector Index: https://neo4j.com/docs/cypher-manual/current/indexes-for-vector-search/

