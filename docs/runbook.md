# GraphRAG Operations Runbook

## Debugging & Troubleshooting

### Planner Mismatch Debugging

When the planner returns unexpected results, use the `trace_id` for debugging:

#### 1. Find the Trace ID

Every RAG response includes a `trace_id`:

```json
{
  "question": "Who founded Microsoft?",
  "answer": "Bill Gates and Paul Allen founded Microsoft [chunk1].",
  "trace_id": "1234567890abcdef1234567890abcdef",
  "plan": {
    "intent": "company_founder_query",
    "anchor_entity": "Microsoft"
  }
}
```

#### 2. Check Audit Logs

```bash
# Search for events related to this trace
grep "1234567890abcdef1234567890abcdef" audit_log.jsonl

# Common issues to look for:
grep "llm_validation_failed" audit_log.jsonl
grep "citation_verification_failed" audit_log.jsonl
```

#### 3. Debug Planner Logic

```python
from graph_rag.planner import generate_plan
from graph_rag.observability import get_logger

# Enable debug logging
logger = get_logger("graph_rag.planner")
logger.setLevel("DEBUG")

# Test the planner
plan = generate_plan("Who founded Microsoft?")
print(f"Intent: {plan.intent}")
print(f"Anchor: {plan.anchor_entity}")
print(f"Chain: {plan.chain}")
```

#### 4. Verify Schema Embeddings

If semantic mapping isn't working:

```python
from graph_rag.planner import _find_best_anchor_entity_semantic

# Test semantic mapping
result = _find_best_anchor_entity_semantic("Microsoft")
print(f"Semantic mapping result: {result}")
```

### Schema Embeddings Regeneration

#### When to Regenerate

- After updating `allow_list.json`
- After adding new synonyms in `schema_synonyms.json`
- When semantic mapping quality degrades
- After Neo4j schema changes

#### Step-by-Step Regeneration

1. **Backup Current Embeddings** (optional):

   ```cypher
   MATCH (s:SchemaTerm)
   RETURN s.id, s.term, s.type, s.canonical_id, s.embedding
   ```

2. **Clear Existing Embeddings**:

   ```cypher
   MATCH (s:SchemaTerm) DELETE s;
   DROP INDEX schema_embeddings IF EXISTS;
   ```

3. **Update Schema Files**:

   ```bash
   # Update allow_list.json if needed
   python -c "from graph_rag.schema_catalog import generate_schema_allow_list; generate_schema_allow_list()"

   # Edit schema_synonyms.json if needed
   # Add new synonym mappings
   ```

4. **Regenerate Embeddings**:

   ```bash
   python -m graph_rag.schema_embeddings
   ```

5. **Verify Results**:

   ```cypher
   MATCH (s:SchemaTerm)
   RETURN s.type, count(*) as count
   ORDER BY s.type;

   // Check vector index
   SHOW INDEXES YIELD name, type WHERE type = "VECTOR";
   ```

### Adding Synonyms

#### 1. Edit Synonyms File

Create or update `schema_synonyms.json`:

```json
{
  "Organization": [
    "Company",
    "Corp",
    "Corporation",
    "Business",
    "Enterprise",
    "Firm",
    "Agency",
    "Institution",
    "Foundation"
  ],
  "Person": [
    "Individual",
    "User",
    "Employee",
    "Staff",
    "Member",
    "Developer",
    "Engineer",
    "Manager",
    "Executive"
  ],
  "Product": [
    "Service",
    "Application",
    "Tool",
    "Platform",
    "System",
    "Software",
    "Solution",
    "Framework",
    "Library"
  ]
}
```

#### 2. Regenerate Embeddings

```bash
python -m graph_rag.schema_embeddings
```

#### 3. Test Synonym Mapping

```python
from graph_rag.planner import _find_best_anchor_entity_semantic

# Test various synonyms
test_terms = ["Microsoft Corp", "Apple Inc", "Google LLC", "Meta Platforms"]
for term in test_terms:
    result = _find_best_anchor_entity_semantic(term)
    print(f"{term} -> {result}")
```

## Monitoring & Maintenance

### Health Checks

#### 1. System Health

```bash
# Check service status
curl http://localhost:8000/health

# Check Neo4j connectivity
curl http://localhost:7474/db/data/

# Check Redis connectivity
redis-cli ping
```

#### 2. Schema Embeddings Health

```cypher
// Check embedding counts
MATCH (s:SchemaTerm)
RETURN s.type, count(*) as count,
       avg(size(s.embedding)) as avg_embedding_size
ORDER BY s.type;

// Check for missing embeddings
MATCH (s:SchemaTerm)
WHERE s.embedding IS NULL OR size(s.embedding) = 0
RETURN count(*) as missing_embeddings;
```

#### 3. Audit Log Analysis

```bash
# Count events by type (last 24 hours)
grep "$(date -d '1 day ago' '+%Y-%m-%d')" audit_log.jsonl | \
  jq -r '.event_type' | sort | uniq -c

# Check for high error rates
grep "llm_validation_failed\|citation_verification_failed" audit_log.jsonl | \
  tail -20
```

### Performance Tuning

#### 1. LLM Rate Limiting

Adjust in `config.yaml`:

```yaml
llm:
  rate_limit_per_minute: 60 # Increase for higher throughput
  redis_url: "redis://localhost:6379/0"
```

#### 2. Neo4j Query Timeouts

```yaml
guardrails:
  neo4j_timeout: 10 # Increase for complex queries
  max_cypher_results: 25 # Limit result size
```

#### 3. Schema Embeddings Performance

```yaml
schema_embeddings:
  top_k: 5 # Reduce for faster semantic search
  embedding_model: "text-embedding-3-small" # Use smaller model
```

### Backup & Recovery

#### 1. Neo4j Backup

```bash
# Backup Neo4j data
docker-compose exec neo4j neo4j-admin dump --database=neo4j --to=/backups/neo4j-backup.dump

# Copy backup from container
docker cp $(docker-compose ps -q neo4j):/backups/neo4j-backup.dump ./backups/
```

#### 2. Configuration Backup

```bash
# Backup configuration files
tar -czf config-backup-$(date +%Y%m%d).tar.gz \
  config.yaml allow_list.json schema_synonyms.json
```

#### 3. Audit Log Rotation

```bash
# Rotate audit logs (keep last 30 days)
find . -name "audit_log.jsonl.*" -mtime +30 -delete

# Archive current log
mv audit_log.jsonl audit_log.jsonl.$(date +%Y%m%d)
touch audit_log.jsonl
```

## Troubleshooting Common Issues

### Issue: High Citation Verification Failures

**Symptoms**: Many `citation_verification_failed` events in audit log
**Causes**:

- LLM hallucinating non-existent chunk IDs
- Retriever not providing chunk IDs correctly
  **Solutions**:

1. Check retriever chunk ID format
2. Adjust LLM prompts to be more conservative
3. Review RAG context quality

### Issue: Poor Semantic Mapping Results

**Symptoms**: Entities not mapping to correct schema terms
**Causes**:

- Outdated embeddings
- Missing synonyms
- Poor embedding model quality
  **Solutions**:

1. Regenerate schema embeddings
2. Add more synonyms
3. Use higher-quality embedding model

### Issue: Guardrail Blocking Legitimate Queries

**Symptoms**: Valid questions getting 403 responses
**Causes**:

- Overly strict guardrail prompts
- False positives in heuristic checks
  **Solutions**:

1. Review and adjust guardrail prompts
2. Fine-tune sanitization rules
3. Add whitelist patterns

### Issue: Slow Query Performance

**Symptoms**: High response times, timeouts
**Causes**:

- Complex Cypher queries
- Large result sets
- Neo4j performance issues
  **Solutions**:

1. Optimize Cypher templates
2. Add database indexes
3. Increase timeout values
4. Limit result set sizes
