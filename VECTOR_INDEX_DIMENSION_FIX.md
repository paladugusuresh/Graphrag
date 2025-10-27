# Vector Index Dimension Mismatch Fix

## Problem Statement

When switching embedding providers (e.g., from mock 8-dimensional embeddings to production 768-dimensional embeddings from Gemini), the Neo4j vector index dimension becomes mismatched with the runtime embedding dimension.

**Error Symptom:**
```
db.index.vector.queryNodes() error: 
"index query vector has 768 dimensions, but indexed vectors have 8 dimensions"
```

This occurs because the vector index was created with one dimension but the application is now using embeddings with a different dimension.

---

## Root Cause

The vector index dimension is determined at **bootstrap time** when the index is first created:

1. **Schema ingestion** generates embeddings for schema terms (labels, relationships, properties)
2. **First embedding dimension** is detected: `embedding_dim = len(schema_data[0]['embedding'])`
3. **Vector index is created** with this dimension: 
   ```cypher
   CREATE VECTOR INDEX schema_term_embeddings FOR (n:SchemaTerm) 
   ON n.embedding 
   OPTIONS {indexConfig: {`vector.dimensions`: <detected_dim>, `vector.similarity_function`: 'cosine'}}
   ```
4. **Index dimension is immutable** - once created, it cannot be changed

**When Dimension Mismatch Occurs:**
- Initial bootstrap with mock embeddings (8 dimensions) → index created with dimension=8
- Later switch to Gemini embeddings (768 dimensions) → queries fail because index expects 8 dimensions

---

## Solution: Drop and Recreate Vector Index

The **only** way to fix dimension mismatch is to **drop the old index and recreate it** with the new dimension.

### Option 1: Use Admin API (Recommended)

The application provides a dedicated admin endpoint for schema refresh that handles this automatically.

#### Steps:

1. **Start server in admin mode:**
   ```bash
   APP_MODE=admin ALLOW_WRITES=true python main.py
   ```

2. **Trigger schema refresh via admin API:**
   ```bash
   curl -X POST http://localhost:8000/admin/schema/refresh
   ```

3. **Verify response:**
   ```json
   {
     "status": "success",
     "duration_s": 2.47
   }
   ```

**What happens internally:**
- `ensure_schema_loaded(force=True)` regenerates schema fingerprint and allow-list
- `upsert_schema_embeddings()` generates new embeddings with current provider
- `ensure_chunk_vector_index()` drops old index if dimension mismatch detected, creates new index with correct dimension

---

### Option 2: Use Smoke Test Script

A convenience script is provided for quick bootstrap verification:

```bash
# From project root
bash scripts/smoke_bootstrap.sh
```

**What it does:**
1. Sets `APP_MODE=admin` and `ALLOW_WRITES=true`
2. Starts the application
3. Hits `/admin/schema/refresh` endpoint
4. Verifies indexes were created
5. Returns exit code 0 on success

---

### Option 3: Manual Neo4j Cypher (Advanced)

If you need manual control, you can drop and recreate the index directly in Neo4j:

```cypher
// 1. Drop existing vector index
DROP INDEX schema_term_embeddings IF EXISTS;

// 2. Create new index with correct dimension
// Replace <NEW_DIMENSION> with your embedding dimension (e.g., 768 for Gemini)
CREATE VECTOR INDEX schema_term_embeddings FOR (n:SchemaTerm) 
ON n.embedding 
OPTIONS {
  indexConfig: {
    `vector.dimensions`: <NEW_DIMENSION>,
    `vector.similarity_function`: 'cosine'
  }
};

// 3. Verify index was created
SHOW INDEXES;
```

**Important:** After manual index recreation, you must also regenerate embeddings:
```bash
curl -X POST http://localhost:8000/admin/schema/refresh
```

---

## Verification

After index recreation, verify that semantic queries work correctly:

### Test 1: Check Index Status
```bash
curl http://localhost:8000/health
```

Look for:
```json
{
  "status": "healthy",
  "neo4j": "connected",
  "vector_index": "exists",
  "embedding_dimension": 768
}
```

### Test 2: Test Semantic Mapping
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the goals for Isabella Thomas?"}'
```

**Expected:** Query completes successfully without dimension errors.

**Before Fix:**
```json
{
  "error": "Query execution failed",
  "detail": "index query vector has 768 dimensions, but indexed vectors have 8"
}
```

**After Fix:**
```json
{
  "summary": "Found 3 goals for Isabella Thomas...",
  "rows": [...],
  "cypher": "..."
}
```

---

## When to Trigger Index Refresh

You must refresh the vector index whenever:

1. **Switching embedding providers:**
   - From mock (8-dim) to production (Gemini 768-dim)
   - From OpenAI (1536-dim) to Gemini (768-dim)
   - Between any providers with different dimensions

2. **Changing embedding model:**
   - From `text-embedding-004` (768-dim) to `text-embedding-ada-002` (1536-dim)
   - Between model versions with different output dimensions

3. **Schema updates:**
   - After adding new labels, relationships, or properties
   - When allow-list changes significantly

4. **Database migration:**
   - After restoring from backup with different embedding dimension
   - When moving between dev/staging/prod with different configs

---

## Configuration

The embedding dimension is **automatically detected** from the first generated embedding. No configuration is required.

**Relevant Config Values:**
```yaml
# config.yaml
embeddings:
  provider: "gemini"  # or "openai", "mock", etc.
  model: "models/text-embedding-004"  # Gemini model (768-dim)
  
# DEV_MODE uses mock embeddings (8-dim)
dev_mode: false  # Set to false for production embeddings
```

**Environment Variables:**
```bash
DEV_MODE=false  # Use real embeddings (not 8-dim mock)
APP_MODE=admin  # Required for write operations (index creation)
ALLOW_WRITES=true  # Required for write operations
```

---

## Prevention: Always Bootstrap After Provider Changes

To avoid dimension mismatch errors in the future:

### Recommended Workflow:

```bash
# 1. Update configuration (change embedding provider)
# Edit config.yaml or set environment variables

# 2. Drop existing data (optional but recommended for clean slate)
# In Neo4j Browser:
# MATCH (n:SchemaTerm) DELETE n;
# DROP INDEX schema_term_embeddings IF EXISTS;

# 3. Bootstrap with new provider
APP_MODE=admin ALLOW_WRITES=true python main.py &
sleep 5  # Wait for server to start

# 4. Trigger schema refresh
curl -X POST http://localhost:8000/admin/schema/refresh

# 5. Verify
curl http://localhost:8000/health

# 6. Restart in production mode
# Kill admin server
APP_MODE=read_only python main.py
```

---

## Troubleshooting

### Error: "Index already exists with different dimension"

**Symptom:**
```
Cannot create index: schema_term_embeddings already exists with dimension 8
```

**Solution:**
Drop the existing index first:
```cypher
DROP INDEX schema_term_embeddings IF EXISTS;
```

Then retry the schema refresh.

---

### Error: "No write access in read_only mode"

**Symptom:**
```
Write query blocked: write queries disabled in read_only mode
```

**Solution:**
Start server in admin mode:
```bash
APP_MODE=admin ALLOW_WRITES=true python main.py
```

---

### Error: "Embedding dimension changed at runtime"

**Symptom:**
```
Expected embedding dimension 8, got 768
```

**Solution:**
This indicates DEV_MODE changed between bootstrap and runtime. Ensure consistent mode:
```bash
DEV_MODE=false APP_MODE=admin python main.py
```

Then refresh:
```bash
curl -X POST http://localhost:8000/admin/schema/refresh
```

---

## Acceptance Criteria

✅ After refresh, semantic mapping queries work without dimension errors  
✅ Health endpoint reports correct embedding dimension  
✅ Vector index shows correct dimension in Neo4j (`SHOW INDEXES`)  
✅ Schema terms have embeddings with correct dimension  
✅ Retrieval queries (KNN search) complete successfully  

---

## Implementation Notes

The vector index dimension detection logic is in `graph_rag/schema_embeddings.py`:

```python
def upsert_schema_embeddings():
    # Generate embeddings for all schema terms
    schema_data = [...]
    embeddings = embedding_provider.get_embeddings([term['name'] for term in schema_data])
    
    # Detect dimension from first embedding
    embedding_dim = len(embeddings[0]) if embeddings else 768
    
    # Store embeddings
    for term, embedding in zip(schema_data, embeddings):
        term['embedding'] = embedding
    
    # Upsert to Neo4j
    # (vector index is created separately by ensure_chunk_vector_index())
```

The index creation logic is in `graph_rag/schema_manager.py`:

```python
def ensure_chunk_vector_index():
    # Check if index exists
    existing_indexes = get_existing_indexes()
    
    # If exists, check dimension
    if 'schema_term_embeddings' in existing_indexes:
        current_dim = get_index_dimension('schema_term_embeddings')
        expected_dim = get_current_embedding_dimension()
        
        if current_dim != expected_dim:
            logger.warning(f"Dimension mismatch: dropping index")
            drop_index('schema_term_embeddings')
    
    # Create index with correct dimension
    if 'schema_term_embeddings' not in existing_indexes:
        create_vector_index('schema_term_embeddings', expected_dim)
```

**Note:** No code changes are needed. This is purely an operational procedure to trigger the existing index refresh logic.

---

## Summary

**Problem:** Vector index dimension mismatch causes runtime errors  
**Root Cause:** Index created with one dimension, application using different dimension  
**Solution:** Drop and recreate index via `/admin/schema/refresh` endpoint  
**Prevention:** Always bootstrap after changing embedding providers  
**Acceptance:** Semantic queries work without dimension errors  

**Quick Fix:**
```bash
APP_MODE=admin ALLOW_WRITES=true python main.py &
curl -X POST http://localhost:8000/admin/schema/refresh
```

