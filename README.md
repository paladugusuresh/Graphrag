# GraphRAG Application - AI Agent with Neo4j

A security-first Graph-backed RAG (Retrieval Augmented Generation) system that combines Neo4j knowledge graphs with LLM-powered retrieval and generation.

## 🎯 Current Status: 72% Complete, Structure is WORKABLE ✅

The backend architecture is solid (85%+ complete) with production-ready security, observability, and GraphRAG pipeline. Main gaps: Frontend UI and enhanced NLU features.

## 📚 Documentation

**Start Here**: [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) - Complete guide to all documentation

### Quick Links by Role
- **New Developer**: [WORKFLOW_QUICK_REFERENCE.md](WORKFLOW_QUICK_REFERENCE.md) - One-page quick reference
- **Understanding Architecture**: [.github/copilot-instructions.md](.github/copilot-instructions.md) - Comprehensive guide
- **Product/Stakeholder**: [REQUIREMENTS_GAP_ANALYSIS.md](REQUIREMENTS_GAP_ANALYSIS.md) - What's done, what's missing
- **Implementation**: [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) - 6-8 week plan to 95%

## 🚀 Quick Start

```powershell
# 1. Set environment variables
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USERNAME="neo4j"
$env:NEO4J_PASSWORD="password"
$env:OPENAI_API_KEY="sk-..."

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize schema and allow-list
# Run database/schema.cypher in Neo4j browser, then:
python -c "from graph_rag.schema_catalog import generate_schema_allow_list; generate_schema_allow_list()"

# 4. Start server
uvicorn main:app --reload --port 8000
```

## 🏗️ Architecture

```
Question → Planner → Retriever (Cypher + Vector) → RAG Chain → Audit → Response
```

**Key Modules:**
- `graph_rag/planner.py` - Entity extraction & intent detection
- `graph_rag/retriever.py` - Dual retrieval (structured + unstructured)
- `graph_rag/rag.py` - Answer generation with citation verification
- `graph_rag/cypher_generator.py` - Safe Cypher templates with validation
- `graph_rag/neo4j_client.py` - Read-only client with timeouts
- `graph_rag/observability.py` - OpenTelemetry + Prometheus

## 🔒 Security Features

✅ Read-only database execution  
✅ Label/relationship validation against allow-list  
✅ LLM structured output enforcement  
✅ Rate limiting (Redis token bucket)  
✅ Citation verification with audit logging  
✅ Query timeouts and traversal depth limits  

## 📊 Observability

- **Metrics**: Prometheus at `http://localhost:8000`
- **Tracing**: OpenTelemetry (set `OTEL_EXPORTER_OTLP_ENDPOINT`)
- **Logs**: Structured JSON via `structlog`
- **Audit**: `audit_log.jsonl`

## 🧪 Testing

```powershell
pytest tests/                           # All tests
pytest tests/test_cypher_safety.py      # Security tests
pytest tests/test_citation_verification.py  # Citation validation
```

## 📋 What's Next

See [REQUIREMENTS_GAP_ANALYSIS.md](REQUIREMENTS_GAP_ANALYSIS.md) and [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) for detailed implementation plan.

**Priority 1**: React frontend with chatbot UI  
**Priority 2**: Output formatters (table/graph/text views)  
**Priority 3**: Synonym expansion for better NLU
