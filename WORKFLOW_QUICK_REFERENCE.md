# GraphRAG Workflow - Quick Reference

## 🎯 Current Status: 72% Complete, Structure is WORKABLE ✅

---

## Architecture Flow

```
User Question
    ↓
[Planner] Extract entities, detect intent
    ↓
[Retriever] Dual retrieval:
    ├─ Structured: Cypher templates
    └─ Unstructured: Vector similarity + hierarchy expansion
    ↓
[RAG Chain] Generate answer with LLM
    ↓
[Citation Verification] Validate sources
    ↓
[Audit Store] Log trace
    ↓
Response to User
```

---

## Critical Security Patterns (ALWAYS FOLLOW)

### 1. Label Validation
```python
# ❌ NEVER do this
query = f"MATCH (n:{user_input}) RETURN n"

# ✅ ALWAYS do this
cypher_generator = CypherGenerator()
safe_label = cypher_generator.validate_label(user_input)
query = f"MATCH (n:{safe_label}) RETURN n"
```

### 2. LLM Structured Output
```python
# ❌ NEVER do this
response = call_llm_raw(prompt)

# ✅ ALWAYS do this
class MySchema(BaseModel):
    field: str

response = call_llm_structured(prompt, MySchema)
```

### 3. Read-Only Execution
- Default: All queries are read-only
- Write queries only in `ingest.py` (admin flow)

---

## Key Commands

### Development
```powershell
# Setup environment
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USERNAME="neo4j"
$env:NEO4J_PASSWORD="password"
$env:OPENAI_API_KEY="sk-..."

# Install dependencies
pip install -r requirements.txt

# Generate allow_list.json
python -c "from graph_rag.schema_catalog import generate_schema_allow_list; generate_schema_allow_list()"

# Run server
uvicorn main:app --reload --port 8000
```

### Testing
```powershell
pytest tests/                           # All tests
pytest tests/test_cypher_safety.py      # Security tests
pytest tests/test_citation_verification.py  # Citation tests
```

### Docker
```powershell
docker-compose up -d                    # Start all services
docker-compose logs -f app              # View app logs
```

---

## File Organization

### Core Modules
| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `graph_rag/planner.py` | Entity extraction & intent detection | `generate_plan()` |
| `graph_rag/retriever.py` | Dual retrieval (Cypher + vector) | `Retriever.retrieve_context()` |
| `graph_rag/rag.py` | Answer generation & citation verification | `RAGChain.invoke()` |
| `graph_rag/cypher_generator.py` | Safe Cypher templates | `CypherGenerator.validate_label()` |
| `graph_rag/neo4j_client.py` | Database client with timeouts | `Neo4jClient.execute_read_query()` |
| `graph_rag/llm_client.py` | Rate-limited LLM calls | `call_llm_structured()` |

### Configuration
| File | Purpose |
|------|---------|
| `config.yaml` | All tunable parameters |
| `allow_list.json` | Schema validation whitelist |
| `.env` | Secrets (Neo4j, OpenAI, Redis) |

---

## Adding Features

### New Cypher Query Intent
1. Add template to `cypher_generator.py`:
   ```python
   CYPHER_TEMPLATES = {
       "my_new_intent": {
           "cypher": "MATCH ...",
           "schema_requirements": {"labels": [...], "relationships": [...]}
       }
   }
   ```
2. Update intent detection in `planner.py`:
   ```python
   def _detect_intent(question: str):
       if "my keywords" in question.lower():
           return "my_new_intent"
   ```
3. Regenerate `allow_list.json` if schema changed

### New Data Ingestion
1. Add `.md` files to `data/` with YAML frontmatter
2. Run `python -m graph_rag.ingest` (if entry point exists)
3. Verify chunks created in Neo4j

---

## Observability

### Metrics (Prometheus)
- `http://localhost:8000` - Metrics endpoint
- `db_query_total` - Query counts by status
- `db_query_latency_seconds` - Query duration histogram
- `inflight_queries` - Concurrent queries
- `llm_calls_total` - LLM invocations

### Tracing (OpenTelemetry)
- Set `OTEL_EXPORTER_OTLP_ENDPOINT` to export traces
- Every operation creates spans with attributes
- Trace IDs returned in API responses

### Logs (Structured JSON)
- Location: stdout (structured JSON via `structlog`)
- Filter by severity: `INFO`, `WARNING`, `ERROR`

### Audit Trail
- Location: `audit_log.jsonl`
- Contains: Citation verification failures, security violations

---

## Common Issues

| Issue | Solution |
|-------|----------|
| `LLMStructuredError: rate limit exceeded` | Increase `llm.rate_limit_per_minute` in `config.yaml` |
| Query timeout | Increase `guardrails.neo4j_timeout` |
| Invalid label warning | Run `generate_schema_allow_list()` to update `allow_list.json` |
| Empty retrieval results | Check if vector index exists in Neo4j |
| Test failures with mocking | Ensure `mock_open` includes `config.yaml` content |

---

## What's Missing (See REQUIREMENTS_GAP_ANALYSIS.md)

### Critical (Blocks user requirements)
- ❌ React frontend chatbot UI
- ❌ Output formatters (table/graph/text views)
- ❌ User feedback system (thumbs up/down)

### Important (Improves accuracy)
- ⚠️ Synonym expansion for schema mapping
- ⚠️ Embedding similarity for term matching
- ⚠️ More Cypher templates (only 2 currently)

### Enhancement (Nice to have)
- 🔜 Admin dashboard for feedback review
- 🔜 Query complexity analysis
- 🔜 Multi-hop reasoning

---

## Next Steps (Priority Order)

1. **Build React frontend** (Week 1-2)
   - Chat interface with message history
   - Result viewer with format switching

2. **Create output formatters** (Week 2)
   - `formatters.py` with Table/Graph/Text classes

3. **Set up vector index** (Week 3)
   - Run Neo4j vector index creation
   - Update ingestion to populate embeddings

4. **Implement synonym mapper** (Week 4)
   - `synonym_mapper.py` for semantic term matching
   - Enhance planner with embedding similarity

5. **Expand query templates** (Week 5-6)
   - Add 10-15 domain-specific Cypher templates
   - Improve intent detection logic

---

## Quick Links

- **Architecture Guide**: `.github/copilot-instructions.md`
- **Gap Analysis**: `REQUIREMENTS_GAP_ANALYSIS.md`
- **Roadmap**: `DEVELOPMENT_ROADMAP.md`
- **Tasks**: `TASKS.md`

---

## Module Instantiation Pattern

```python
# ✅ Current pattern (instance-level)
class RAGChain:
    def __init__(self):
        self.retriever = Retriever()  # Instantiate locally

# ❌ Old pattern (avoid)
retriever = Retriever()  # Module-level singleton
```

**Why**: Better for testing (easier mocking) and thread safety

---

## Testing Patterns

```python
import unittest
from unittest.mock import patch, MagicMock, mock_open

class TestMyFeature(unittest.TestCase):
    @patch('graph_rag.my_module.Neo4jClient')
    @patch('builtins.open', new_callable=mock_open, read_data='config: value')
    def test_something(self, mock_open, mock_neo4j):
        # Mock Neo4j
        mock_neo4j.return_value.execute_read_query.return_value = [{"result": "data"}]
        
        # Test your code
        result = my_function()
        
        # Assert
        self.assertEqual(result, expected)
```

---

**Last Updated**: Based on codebase analysis October 2025
**Compliance**: 72% → Target 95% in 6-8 weeks
