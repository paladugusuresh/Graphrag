# Development Roadmap - AI Agent GraphRAG

Based on requirements analysis, this roadmap outlines what needs to be built to achieve 95%+ compliance.

## 🎯 Quick Status: 72% → 95% (6-8 weeks)

---

## Phase 1: Critical User-Facing Features (3-4 weeks)

### 1.1 React Frontend Setup (Week 1)
**Priority: CRITICAL** - Blocks all user interaction requirements

```bash
# Create React app
npx create-react-app frontend --template typescript
cd frontend
npm install axios @tanstack/react-query recharts vis-network react-force-graph
```

**Files to create:**
- `frontend/src/components/ChatInterface.tsx` - Main chat UI
- `frontend/src/components/MessageHistory.tsx` - Conversation display
- `frontend/src/components/ResultViewer.tsx` - Switches between output formats
- `frontend/src/api/chatApi.ts` - Axios wrapper for backend API

**Key features:**
- Message bubbles (user vs assistant)
- Conversation history loading
- Loading states during query processing
- Error handling with retry

### 1.2 Output Format Handlers (Week 2)
**Priority: CRITICAL** - Required for structured data display

Create `graph_rag/formatters.py`:
```python
class TableFormatter:
    """Converts Cypher results to table JSON"""
    def format(self, results: list[dict]) -> dict:
        return {
            "format": "table",
            "columns": self._extract_columns(results),
            "rows": results
        }

class GraphFormatter:
    """Converts Cypher results to graph JSON (nodes + edges)"""
    def format(self, results: list[dict]) -> dict:
        nodes = []
        edges = []
        # Extract nodes and relationships from Cypher results
        return {"format": "graph", "nodes": nodes, "edges": edges}

class TextFormatter:
    """Returns LLM-generated summary (already exists in rag.py)"""
    pass
```

**Frontend components:**
- `TableView.tsx` - Render tabular data with sorting/filtering
- `GraphView.tsx` - D3.js or vis-network graph visualization
- `TextView.tsx` - Rich text with citations

### 1.3 Enhanced API Endpoints (Week 2)
Update `main.py`:
```python
@app.post("/api/chat")
def chat(req: ChatRequest):
    # ... existing code ...
    
    # Add format parameter
    format_type = req.format_type or "text"  # "table" | "graph" | "text"
    
    resp = rag_chain.invoke(req.question, format_type=format_type)
    # resp now includes formatted results
    return resp

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    question: str
    format_type: str = "text"  # NEW
```

### 1.4 Neo4j Vector Index Setup (Week 3)
**Priority: HIGH** - Required for embedding-based retrieval

Run in Neo4j browser or cypher-shell:
```cypher
// Create vector index for chunk embeddings
CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}}

// Verify index
SHOW INDEXES YIELD name, type, entityType, properties
WHERE name = 'chunk_embeddings'
```

Update ingestion to populate embeddings:
```python
# In graph_rag/ingest.py
def process_and_ingest_files():
    # ... existing chunking code ...
    
    # Generate embeddings for chunks
    embedding_provider = get_embedding_provider()
    chunk_texts = [chunk.page_content for chunk in chunks]
    embeddings = embedding_provider.get_embeddings(chunk_texts)
    
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        client.execute_write_query(
            """MATCH (d:Document {id: $id}) 
               MERGE (c:Chunk {id: $chunk_id}) 
               SET c.text = $text, c.embedding = $embedding
               MERGE (d)-[:HAS_CHUNK]->(c)""",
            {"id": doc_id, "chunk_id": chunk_id, 
             "text": chunk.page_content, "embedding": embedding}
        )
```

---

## Phase 2: Enhanced NLU (2 weeks)

### 2.1 Synonym Mapper (Week 4)
**Priority: HIGH** - Improves query understanding accuracy

Create `graph_rag/synonym_mapper.py`:
```python
class SynonymMapper:
    def __init__(self):
        self.schema_terms = self._load_schema_from_allow_list()
        self.schema_embeddings = self._generate_schema_embeddings()
    
    def _load_schema_from_allow_list(self) -> dict:
        """Loads labels, relationships, properties from allow_list.json"""
        with open("allow_list.json") as f:
            return json.load(f)
    
    def _generate_schema_embeddings(self) -> dict:
        """Pre-generates embeddings for all schema terms"""
        embedding_provider = get_embedding_provider()
        embeddings = {}
        
        # Embed node labels
        labels = self.schema_terms["node_labels"]
        embeddings["labels"] = {
            label: embedding_provider.get_embeddings([label])[0]
            for label in labels
        }
        
        # Embed relationship types
        rels = self.schema_terms["relationship_types"]
        embeddings["relationships"] = {
            rel: embedding_provider.get_embeddings([rel])[0]
            for rel in rels
        }
        
        return embeddings
    
    def find_matching_label(self, user_term: str, top_k: int = 3) -> list[tuple[str, float]]:
        """Returns top-k matching labels with similarity scores"""
        user_embedding = get_embedding_provider().get_embeddings([user_term])[0]
        
        scores = []
        for label, label_embedding in self.schema_embeddings["labels"].items():
            similarity = self._cosine_similarity(user_embedding, label_embedding)
            scores.append((label, similarity))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        import numpy as np
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

### 2.2 Enhanced Planner (Week 4-5)
Update `graph_rag/planner.py`:
```python
from graph_rag.synonym_mapper import SynonymMapper

def generate_plan(question: str) -> QueryPlan:
    synonym_mapper = SynonymMapper()
    
    # Extract candidate terms from question
    prompt = f"Extract key entities and their types from: {question}"
    extracted = call_llm_structured(prompt, ExtractedEntities)
    
    # Map to schema using embeddings
    mapped_entities = []
    for name in extracted.names:
        matches = synonym_mapper.find_matching_label(name, top_k=1)
        if matches and matches[0][1] > 0.7:  # Threshold for similarity
            mapped_entities.append({
                "user_term": name,
                "schema_label": matches[0][0],
                "confidence": matches[0][1]
            })
    
    intent = _detect_intent(question)
    anchor = mapped_entities[0]["schema_label"] if mapped_entities else None
    
    return QueryPlan(
        intent=intent, 
        anchor_entity=anchor, 
        question=question,
        entity_mappings=mapped_entities  # NEW
    )
```

---

## Phase 3: User Engagement Features (1 week)

### 3.1 Feedback System (Week 5)
Create `graph_rag/feedback_store.py`:
```python
class FeedbackStore:
    def __init__(self):
        self.client = Neo4jClient()
    
    def record_feedback(self, trace_id: str, rating: int, comment: str = None):
        """Stores user feedback linked to query trace"""
        self.client.execute_write_query(
            """CREATE (f:Feedback {
                trace_id: $trace_id,
                rating: $rating,
                comment: $comment,
                timestamp: datetime()
            })""",
            {"trace_id": trace_id, "rating": rating, "comment": comment}
        )
    
    def get_feedback_stats(self) -> dict:
        """Returns aggregate feedback metrics"""
        result = self.client.execute_read_query(
            """MATCH (f:Feedback)
               RETURN avg(f.rating) as avg_rating,
                      count(f) as total_feedback"""
        )
        return result[0] if result else {}

feedback_store = FeedbackStore()
```

Add API endpoint in `main.py`:
```python
@app.post("/api/feedback")
def submit_feedback(trace_id: str, rating: int, comment: str = None):
    feedback_store.record_feedback(trace_id, rating, comment)
    return {"status": "success"}
```

Frontend component:
```typescript
// FeedbackButton.tsx
const FeedbackButton = ({ traceId }: { traceId: string }) => {
    const [rating, setRating] = useState<number | null>(null);
    
    const submitFeedback = async (value: number) => {
        await axios.post('/api/feedback', {
            trace_id: traceId,
            rating: value
        });
        setRating(value);
    };
    
    return (
        <div>
            <button onClick={() => submitFeedback(1)}>👍</button>
            <button onClick={() => submitFeedback(-1)}>👎</button>
        </div>
    );
};
```

---

## Phase 4: Query Intent Expansion (1 week)

### 4.1 Expand Cypher Templates (Week 6)
Update `graph_rag/cypher_generator.py`:
```python
CYPHER_TEMPLATES = {
    # Existing templates...
    "general_rag_query": {...},
    "company_founder_query": {...},
    
    # NEW templates
    "product_by_company": {
        "cypher": """
            MATCH (o:Organization {id: $anchor})-[:HAS_PRODUCT]->(p:Product)
            RETURN p.id AS product_name, p.description AS description
        """,
        "schema_requirements": {
            "labels": ["Organization", "Product"],
            "relationships": ["HAS_PRODUCT"]
        }
    },
    
    "employee_list": {
        "cypher": """
            MATCH (p:Person)-[:WORKS_FOR]->(o:Organization {id: $anchor})
            RETURN p.id AS employee_name, p.title AS title
        """,
        "schema_requirements": {
            "labels": ["Person", "Organization"],
            "relationships": ["WORKS_FOR"]
        }
    },
    
    "relationship_path": {
        "cypher": """
            MATCH path = (start:__Entity__ {id: $anchor})-[*1..3]-(end:__Entity__ {id: $target})
            WITH path, relationships(path) as rels
            RETURN [r in rels | type(r)] AS relationship_chain
            LIMIT 5
        """,
        "schema_requirements": {
            "labels": ["__Entity__"],
            "relationships": []
        }
    },
    
    # Add 10-15 more domain-specific templates
}
```

Update `planner.py` intent detection:
```python
def _detect_intent(question: str):
    q = question.lower()
    
    # Existing
    if "who founded" in q:
        return "company_founder_query"
    if "product" in q or "what does" in q and "make" in q:
        return "product_by_company"
    
    # NEW
    if "employee" in q or "who works" in q:
        return "employee_list"
    if "how" in q and "related" in q:
        return "relationship_path"
    if "when" in q or "date" in q:
        return "temporal_query"
    
    return "general_rag_query"
```

---

## Testing Checklist

### Backend Tests
- [ ] `test_synonym_mapper.py` - Embedding similarity matching
- [ ] `test_formatters.py` - Output format conversion
- [ ] `test_feedback_store.py` - Feedback recording
- [ ] `test_enhanced_planner.py` - Entity mapping with embeddings
- [ ] `test_cypher_templates.py` - New query intent validation

### Frontend Tests
- [ ] `ChatInterface.test.tsx` - Message sending/receiving
- [ ] `TableView.test.tsx` - Table rendering
- [ ] `GraphView.test.tsx` - Graph visualization
- [ ] `FeedbackButton.test.tsx` - Rating submission

### Integration Tests
- [ ] End-to-end query flow with all output formats
- [ ] Conversation persistence across sessions
- [ ] Feedback linked to trace IDs
- [ ] Synonym mapping improves query accuracy

---

## Deployment Checklist

### Infrastructure
- [ ] Update `docker-compose.yml` to include frontend service
- [ ] Configure Nginx reverse proxy for frontend + backend
- [ ] Set up environment-specific configs (dev/staging/prod)

### Neo4j Setup
- [ ] Run `database/schema.cypher` in production
- [ ] Create vector index for embeddings
- [ ] Verify allow_list.json matches production schema

### Monitoring
- [ ] Confirm Prometheus metrics endpoint accessible
- [ ] Set up Grafana dashboards for:
  - Query latency
  - Feedback ratings over time
  - Error rates
  - LLM token usage
- [ ] Configure OpenTelemetry export to Jaeger/Honeycomb

---

## Success Metrics

After implementation, verify:
1. ✅ Frontend loads and connects to backend API
2. ✅ Users can send questions and receive formatted responses
3. ✅ All 3 output formats (table, graph, text) work correctly
4. ✅ Synonym mapping improves entity recognition (measure with test queries)
5. ✅ Feedback system records ratings linked to trace IDs
6. ✅ Conversation history persists across sessions
7. ✅ 95%+ requirements compliance (run gap analysis again)

---

## Quick Start for New Developers

```bash
# 1. Clone and setup
git clone <repo>
cd graphrag2

# 2. Backend setup
pip install -r requirements.txt
python -c "from graph_rag.schema_catalog import generate_schema_allow_list; generate_schema_allow_list()"
uvicorn main:app --reload

# 3. Frontend setup (once created)
cd frontend
npm install
npm start

# 4. Run tests
pytest tests/
cd frontend && npm test
```

See `.github/copilot-instructions.md` for architecture details and `REQUIREMENTS_GAP_ANALYSIS.md` for current status.
