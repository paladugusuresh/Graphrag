# graph_rag/retriever.py
from graph_rag.observability import get_logger, tracer
from graph_rag.neo4j_client import Neo4jClient # Import the class, not the instance
from graph_rag.embeddings import get_embedding_provider # Import the getter function
from graph_rag.cypher_generator import validate_label, validate_relationship_type, load_allow_list
from graph_rag.config_manager import get_config_value

logger = get_logger(__name__)

class Retriever:
    def __init__(self, max_chunks: int = None):
        """Initialize Retriever with Neo4j client and embedding provider"""
        self.max_chunks = max_chunks or get_config_value('retriever.max_chunks', 5)
        self.neo4j_client = Neo4jClient()
        self.embedding_provider = get_embedding_provider()

    def _get_structured_context(self, plan):
        """
        Simplified structured context retrieval without template-driven queries.
        
        Structured querying is now done via LLM-generated Cypher + query_executor.safe_execute().
        This method returns minimal contextual information to maintain backward compatibility.
        
        For legacy template-based queries, see legacy/graph_rag/retriever_legacy.py
        """
        with tracer.start_as_current_span("retriever.structured_query") as span:
            span.set_attribute("intent", plan.intent)
            span.set_attribute("anchor_entity", plan.anchor_entity)
            
            # Return minimal contextual string indicating that structured queries
            # are now handled by LLM-generated Cypher, not templates
            context_note = f"Intent: {plan.intent}"
            if plan.anchor_entity:
                context_note += f" | Anchor: {plan.anchor_entity}"
            
            # Add parameter information if available
            if hasattr(plan, 'params') and plan.params:
                param_summary = ", ".join([f"{k}={v}" for k, v in list(plan.params.items())[:3]])
                context_note += f" | Params: {param_summary}"
            
            span.add_event("structured_context_minimal", {
                "note": "No template execution; LLM will generate Cypher",
                "intent": plan.intent
            })
            
            logger.debug(f"Structured context (minimal): {context_note}")
            return ""  # Return empty string; LLM will generate necessary Cypher

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
            rows = self.neo4j_client.execute_read_query(q, {"top_k": self.max_chunks, "embedding": emb}, timeout=get_config_value('guardrails.neo4j_timeout', 10))
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
            rows = self.neo4j_client.execute_read_query(q, {"chunk_ids": chunk_ids, "max_hops": get_config_value('guardrails.max_traversal_depth', 2), "max_chunks": self.max_chunks}, timeout=get_config_value('guardrails.neo4j_timeout', 10))
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
