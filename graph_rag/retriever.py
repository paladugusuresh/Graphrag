# graph_rag/retriever.py
import yaml
from graph_rag.observability import get_logger, tracer
from graph_rag.neo4j_client import Neo4jClient # Import the class, not the instance
from graph_rag.embeddings import get_embedding_provider # Import the getter function
from graph_rag.cypher_generator import CypherGenerator # Import the class, not the instance

logger = get_logger(__name__)
with open("config.yaml", 'r') as f:
    CFG = yaml.safe_load(f)

class Retriever:
    def __init__(self, max_chunks: int = None):
        self.max_chunks = max_chunks or CFG['retriever']['max_chunks']
        self.neo4j_client = Neo4jClient()
        self.embedding_provider = get_embedding_provider()
        self.cypher_generator = CypherGenerator()

    def _get_structured_context(self, plan):
        with tracer.start_as_current_span("retriever.structured_query") as span:
            span.set_attribute("template_name", plan.intent)
            span.set_attribute("anchor_entity", plan.anchor_entity)
            cypher, params = self.cypher_generator.CYPHER_TEMPLATES.get(plan.intent, {}).get("cypher"), {"anchor": plan.anchor_entity}
            if not cypher:
                return ""
            result = self.neo4j_client.execute_read_query(cypher, params=params, timeout=CFG['guardrails']['neo4j_timeout'])
            return "\n".join([list(r.values())[0] for r in result])

    def _get_unstructured_context(self, question):
        with tracer.start_as_current_span("retriever.vector_search"):
            emb = self.embedding_provider.get_embeddings([question])[0]
            if not emb:
                return []
            q = """
            CALL db.index.vector.queryNodes('chunk_embeddings', $top_k, $embedding)
            YIELD node
            RETURN node.id AS chunk_id
            """
            rows = self.neo4j_client.execute_read_query(q, {"top_k": self.max_chunks, "embedding": emb}, timeout=CFG['guardrails']['neo4j_timeout'])
            return [r['chunk_id'] for r in rows]

    def _expand_with_hierarchy(self, chunk_ids):
        with tracer.start_as_current_span("retriever.hierarchy_expand") as span:
            if not chunk_ids:
                return []
            span.add_event("citations", attributes={"chunk_ids": chunk_ids})
            q = """
            UNWIND $chunk_ids AS cid
            MATCH (initial_chunk:Chunk {id: cid})
            MATCH (source_doc:Document)-[:HAS_CHUNK]->(initial_chunk)
            CALL { WITH source_doc MATCH (source_doc)-[:PART_OF*0..$max_hops]->(p:Document) RETURN collect(DISTINCT p) AS parents }
            WITH source_doc, parents
            UNWIND parents + [source_doc] AS related_doc
            MATCH (related_doc)-[:HAS_CHUNK]->(related_chunk:Chunk)
            RETURN DISTINCT related_chunk.id AS id, related_chunk.text AS text
            LIMIT $max_chunks
            """
            rows = self.neo4j_client.execute_read_query(q, {"chunk_ids": chunk_ids, "max_hops": CFG['guardrails']['max_traversal_depth'], "max_chunks": self.max_chunks}, timeout=CFG['guardrails']['neo4j_timeout'])
            return rows

    def retrieve_context(self, plan):
        with tracer.start_as_current_span("retriever.retrieve_context"):
            structured = self._get_structured_context(plan)
            initial_chunks = self._get_unstructured_context(plan.question)
            expanded = self._expand_with_hierarchy(initial_chunks)
            # return structured and flattened unstructured context as text
            unstructured_text = "\n\n".join([f"[{r['id']}]\n{r['text']}" for r in expanded])
            return {"structured": structured, "unstructured": unstructured_text, "chunk_ids": [r['id'] for r in expanded]}

# retriever = Retriever() # Removed module-level instantiation
