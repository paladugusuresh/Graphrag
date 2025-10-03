# GraphRAG Application - AI Agent Workflow Guide

## System Architecture

This is a **Graph-backed RAG (Retrieval Augmented Generation)** system with security-first design principles. The architecture combines Neo4j knowledge graphs with LLM-powered retrieval and generation.

### Core Flow: Question → Plan → Retrieve → Generate → Audit
1. **Planner** (`graph_rag/planner.py`) - Extracts entities from user question via LLM structured output, determines query intent
2. **Retriever** (`graph_rag/retriever.py`) - Dual retrieval: structured (Cypher templates) + unstructured (vector similarity with hierarchy expansion)
3. **RAG Chain** (`graph_rag/rag.py`) - Generates answer with citation verification, traces execution with OpenTelemetry
4. **Audit Store** (`graph_rag/audit_store.py`) - Records security violations and verification failures to `audit_log.jsonl`

### Key Components

- **Neo4j Client** (`graph_rag/neo4j_client.py`) - Read-only by default, enforces timeouts (10s default), instruments all queries with Prometheus metrics
- **Cypher Generator** (`graph_rag/cypher_generator.py`) - Template-based, validates labels/relationships against `allow_list.json` to prevent injection
- **LLM Client** (`graph_rag/llm_client.py`) - Rate-limited (Redis token bucket), structured output validation with Pydantic, raw LLM calls forbidden without schema validation
- **Observability** (`graph_rag/observability.py`) - OpenTelemetry tracing + Prometheus metrics on port 8000

## Critical Security Patterns

### Label Validation (MANDATORY)
**Never** use user input directly in Cypher. Always validate via `CypherGenerator`:
```python
cypher_generator = CypherGenerator()
safe_label = cypher_generator.validate_label(user_label)  # Returns backticked safe label or fallback
```
- Valid labels: `^[A-Za-z_][A-Za-z0-9_]*$`, must exist in `allow_list.json`
- Invalid → falls back to `Entity` with warning logged

### LLM Structured Output (REQUIRED)
All LLM calls MUST use `call_llm_structured()` with Pydantic schema:
```python
from graph_rag.llm_client import call_llm_structured, LLMStructuredError
class MySchema(BaseModel):
    field: str
try:
    result = call_llm_structured(prompt, MySchema)
except LLMStructuredError:
    # Rate limit exceeded or validation failed
```
- Rate limiting enforced via Redis (60 calls/min default in `config.yaml`)
- Direct `call_llm_raw()` calls are internal-only

### Citation Verification
All RAG answers validate citations against provided chunks in `rag.py`:
```python
def _verify_citations(self, answer, provided_chunk_ids, question, trace_id):
    # Extracts [chunk_id] citations, flags unknown ones for human review
```
- Unknown citations trigger audit log entries
- Response includes `citation_verification` field with verification status

## Developer Workflows

### Local Development Setup
```powershell
# Set environment variables
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USERNAME="neo4j"
$env:NEO4J_PASSWORD="password"
$env:OPENAI_API_KEY="sk-..."

# Install dependencies
pip install -r requirements.txt

# Initialize Neo4j schema (run once)
# Execute database/schema.cypher in Neo4j browser or:
cat database/schema.cypher | cypher-shell -u neo4j -p password

# Generate allow_list.json from live schema
python -c "from graph_rag.schema_catalog import generate_schema_allow_list; generate_schema_allow_list()"

# Run FastAPI server
uvicorn main:app --reload --port 8000
```

### Testing
```powershell
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/test_cypher_safety.py      # Injection prevention
pytest tests/test_citation_verification.py  # Citation validation
pytest tests/test_llm_client_structured.py  # LLM schema enforcement
```

Tests use `unittest.TestCase` with heavy mocking. Key patterns:
- Mock `Neo4jClient` to avoid DB dependency
- Mock `call_llm_structured` for deterministic LLM responses
- Use `mock_open` for config.yaml reads

### Adding New Cypher Templates
Edit `graph_rag/cypher_generator.py`:
```python
CYPHER_TEMPLATES = {
    "new_intent": {
        "cypher": "MATCH (n:ValidatedLabel {id: $anchor}) RETURN n.prop",
        "schema_requirements": {
            "labels": ["ValidatedLabel"],       # Must exist in allow_list.json
            "relationships": ["VALIDATED_REL"]  # Must exist in allow_list.json
        }
    }
}
```
1. Add template to `CYPHER_TEMPLATES` dict
2. Update `planner.py` intent detection in `_detect_intent()`
3. Regenerate allow_list if schema changed: `generate_schema_allow_list()`

### Observability & Debugging

**Tracing**: All components instrument spans with `graph_rag.observability.tracer`
```python
from graph_rag.observability import tracer
with tracer.start_as_current_span("my_operation") as span:
    span.set_attribute("key", "value")
```
- Set `OTEL_EXPORTER_OTLP_ENDPOINT` to export to Jaeger/Honeycomb
- Defaults to console export for local dev

**Metrics**: Prometheus endpoint at `http://localhost:8000` when `observability.metrics_enabled: true`
- `db_query_total{status="success|failure"}` - Query counts
- `db_query_latency_seconds` - Query duration histogram
- `inflight_queries` - Concurrent query gauge
- `llm_calls_total` - LLM invocation counter

**Logs**: Structured JSON via `structlog` (`graph_rag/observability.py`)
```python
from graph_rag.observability import get_logger
logger = get_logger(__name__)
logger.warning("event", extra_field="value")  # Outputs JSON
```

## Data Ingestion Pattern

**Location**: `graph_rag/ingest.py` processes `data/*.md` files with YAML frontmatter

Key steps (see `process_and_ingest_files()`):
1. Parse frontmatter (requires `id` field)
2. Create `Document` node
3. Chunk text with `TokenTextSplitter` (512 tokens, 24 overlap)
4. For each chunk:
   - Create `Chunk` node with `HAS_CHUNK` relationship
   - Extract entities via `call_llm_structured(prompt, ExtractedGraph)`
   - **Validate** extracted labels via `cypher_generator.validate_label()`
   - Create entity nodes and `MENTIONS` relationships

**Critical**: Ingestion validates all LLM-extracted labels before database writes. Invalid labels log warnings and fall back to `Entity`.

## Module Instantiation Convention

**Pattern**: Components instantiate dependencies locally rather than using module-level singletons
```python
# ❌ Old pattern (avoid)
retriever = Retriever()  # Module-level

# ✅ Current pattern
class RAGChain:
    def __init__(self):
        self.retriever = Retriever()  # Instance-level
```
This enables better testing (easier mocking) and thread safety. See `rag.py`, `ingest.py`, `retriever.py`.

## Configuration

**File**: `config.yaml` - All tunable parameters
- `guardrails.neo4j_timeout`: Query timeout in seconds (default 10)
- `guardrails.max_cypher_results`: Result set limit (default 25)
- `guardrails.max_traversal_depth`: Graph traversal depth (default 2)
- `llm.rate_limit_per_minute`: Token bucket size (default 60)
- `retriever.max_chunks`: Vector search top-k (default 5)

**Environment**: `.env` for secrets
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
- `OPENAI_API_KEY`
- `REDIS_URL` (default: `redis://localhost:6379/0`)
- `OTEL_EXPORTER_OTLP_ENDPOINT` (optional)

## Common Pitfalls

1. **Forgetting label validation**: Always use `cypher_generator.validate_label()` for dynamic labels
2. **Calling `call_llm_raw()` directly**: Use `call_llm_structured()` with Pydantic schema
3. **Missing allow_list.json**: Run `generate_schema_allow_list()` after schema changes
4. **Timeout errors**: Check `guardrails.neo4j_timeout` in config.yaml
5. **Rate limit errors**: Adjust `llm.rate_limit_per_minute` or scale Redis

## Project Status & Requirements Compliance

**Overall: 72% complete** - See `REQUIREMENTS_GAP_ANALYSIS.md` for detailed breakdown

**Fully Implemented (100%):**
- ✅ Schema catalog & embeddings (`schema_catalog.py`, `embeddings.py`)
- ✅ Query generation with validation (`cypher_generator.py`)
- ✅ Guardrails & observability (timeouts, metrics, tracing, audit logs)
- ✅ Security enforcement (read-only, label validation, citation verification)
- ✅ Backend API with conversation history (`main.py`, `conversation_store.py`)

**Partially Implemented (40-85%):**
- ⚠️ NLU (60%) - Has LLM entity extraction, missing synonym expansion & embedding similarity for schema mapping
- ⚠️ User features (40%) - Backend ready, missing React frontend & result formatters (table/graph views)
- ⚠️ Execution & response (85%) - GraphRAG working, missing structured output formatting

**Critical Gaps:**
- ❌ Frontend chatbot UI (requirement specifies React)
- ❌ Synonym expansion for schema term mapping
- ❌ Multiple output formats (tabular, graph visualization, text)
- ❌ User feedback mechanism (thumbs up/down)

**Next Priorities (see REQUIREMENTS_GAP_ANALYSIS.md):**
1. Build React frontend with chatbot interface
2. Implement `SynonymMapper` for semantic schema matching
3. Create output formatters (`formatters.py`) for table/graph/text views
4. Set up Neo4j vector index for chunk embeddings
5. Expand Cypher template library beyond 2 current intents
