# graph_rag/retriever.py
from graph_rag.observability import get_logger, tracer, augmentation_size, create_pipeline_span, add_span_attributes
from graph_rag.neo4j_client import Neo4jClient # Import the class, not the instance
from graph_rag.embeddings import get_embedding_provider # Import the getter function
from graph_rag.cypher_generator import validate_label, validate_relationship_type, load_allow_list
from graph_rag.config_manager import get_config_value
from graph_rag.flags import RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED, RETRIEVAL_TOPK

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

    def retrieve_chunks_by_embedding(self, query_text: str, top_k: int = None) -> list[str]:
        """
        Retrieve chunks using vector KNN similarity on chunk embeddings.
        
        Args:
            query_text: The query text to embed and search for
            top_k: Number of top chunks to retrieve (defaults to RETRIEVAL_TOPK flag)
            
        Returns:
            List of chunk IDs ordered by similarity score
        """
        if not RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED():
            logger.debug("Chunk embeddings disabled, skipping vector retrieval")
            return []
        
        if top_k is None:
            top_k = RETRIEVAL_TOPK()
        
        with tracer.start_as_current_span("retriever.vector_knn") as span:
            span.set_attribute("query_text", query_text[:100])  # Truncate for logging
            span.set_attribute("top_k", top_k)
            
            try:
                # Generate embedding for query text
                embeddings = self.embedding_provider.get_embeddings([query_text])
                if not embeddings or len(embeddings) == 0:
                    logger.warning("Failed to generate embedding for query text")
                    return []
                
                query_embedding = embeddings[0]
                
                # Query vector index for similar chunks
                q = """
                CALL db.index.vector.queryNodes('chunk_embeddings', $top_k, $embedding)
                YIELD node, score
                RETURN node.id AS chunk_id, score
                ORDER BY score DESC
                """
                
                rows = self.neo4j_client.execute_read_query(
                    q, 
                    {"top_k": top_k, "embedding": query_embedding}, 
                    timeout=get_config_value('guardrails.neo4j_timeout', 10)
                )
                
                chunk_ids = [r['chunk_id'] for r in rows]
                
                span.add_event("vector_knn_results", {
                    "chunks_found": len(chunk_ids),
                    "top_score": rows[0]['score'] if rows else None
                })
                
                logger.debug(f"Vector KNN retrieved {len(chunk_ids)} chunks for query")
                return chunk_ids
                
            except Exception as e:
                logger.error(f"Vector KNN retrieval failed: {e}")
                span.add_event("vector_knn_error", {"error": str(e)})
                return []

    def _get_unstructured_context(self, question):
        """
        Legacy method for backward compatibility.
        Now uses retrieve_chunks_by_embedding when embeddings are enabled.
        """
        if RETRIEVAL_CHUNK_EMBEDDINGS_ENABLED():
            return self.retrieve_chunks_by_embedding(question, self.max_chunks)
        else:
            # Fallback to expansion-only behavior when embeddings disabled
            logger.debug("Chunk embeddings disabled, using expansion-only retrieval")
            return []

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
        with create_pipeline_span("retriever.retrieve_context", 
                                  intent=plan.intent,
                                  anchor_entity=plan.anchor_entity) as span:
            structured = self._get_structured_context(plan)
            
            # Get initial chunks via vector similarity (if enabled) or empty list
            initial_chunks = self._get_unstructured_context(plan.question)
            
            # Expand with graph neighbors (bounded by max_traversal_depth)
            expanded = self._expand_with_hierarchy(initial_chunks)
            
            # Record augmentation size metric
            augmentation_size.observe(len(expanded))
            
            # Merge vector results with graph-neighbor context
            # The expanded results already include the initial chunks plus their neighbors
            unstructured_text = "\n\n".join([f"[{r['id']}]\n{r['text']}" for r in expanded])
            
            add_span_attributes(span,
                vector_chunks_count=len(initial_chunks),
                total_chunks=len(expanded),
                augmentation_size=len(expanded)
            )
            
            return {
                "structured": structured, 
                "unstructured": unstructured_text, 
                "chunk_ids": [r['id'] for r in expanded],
                "vector_chunks": initial_chunks,  # Track which chunks came from vector similarity
                "total_chunks": len(expanded)
            }

# retriever = Retriever() # Removed module-level instantiation
