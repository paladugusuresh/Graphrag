# graph_rag/planner.py
import yaml
from pydantic import BaseModel, Field
from graph_rag.observability import get_logger, tracer
from graph_rag.llm_client import call_llm_structured, LLMStructuredError
from graph_rag.cypher_generator import CypherGenerator
from graph_rag.neo4j_client import Neo4jClient
from graph_rag.embeddings import get_embedding_provider

logger = get_logger(__name__)
with open("config.yaml", 'r') as f:
    CFG = yaml.safe_load(f)

class ExtractedEntities(BaseModel):
    names: list[str] = Field(...)

class PlannerOutput(BaseModel):
    intent: str
    params: dict = {}
    confidence: float | None = None
    chain: list[str] | None = None   # optional list of template names to chain

class QueryPlan(BaseModel):
    intent: str
    anchor_entity: str | None = None
    question: str
    chain: list[dict] | None = None  # Optional chain of {"intent": name, "params": {...}}

def _build_template_summary() -> str:
    """Build a summary of available Cypher templates for the LLM to choose from."""
    cypher_gen = CypherGenerator()
    
    # Import CYPHER_TEMPLATES from the module
    from graph_rag.cypher_generator import CYPHER_TEMPLATES
    
    template_descriptions = []
    for template_name, template_info in CYPHER_TEMPLATES.items():
        schema_reqs = template_info.get("schema_requirements", {})
        labels = schema_reqs.get("labels", [])
        relationships = schema_reqs.get("relationships", [])
        
        if template_name == "general_rag_query":
            description = "General purpose query for any entity relationships and connections"
        elif template_name == "company_founder_query":
            description = "Find who founded a specific company/organization"
        else:
            description = f"Query template: {template_name}"
        
        template_desc = f"- {template_name}: {description}"
        if labels or relationships:
            template_desc += f" (requires labels: {labels}, relationships: {relationships})"
        
        template_descriptions.append(template_desc)
    
    return "\n".join(template_descriptions)

def _validate_and_build_chain(chain_template_names: list[str], base_params: dict, anchor_entity: str | None) -> list[dict]:
    """
    Validate chain template names and build chain structure with parameters.
    
    Args:
        chain_template_names: List of template names from PlannerOutput.chain
        base_params: Base parameters from PlannerOutput.params
        anchor_entity: Anchor entity extracted from parameters
        
    Returns:
        List of dicts with {"intent": name, "params": {...}} for each valid template
    """
    from graph_rag.cypher_generator import CYPHER_TEMPLATES
    
    validated_chain = []
    
    for i, template_name in enumerate(chain_template_names):
        # Validate template exists
        if template_name not in CYPHER_TEMPLATES:
            logger.warning(f"Invalid template '{template_name}' in chain at position {i}. Skipping.")
            continue
        
        # Build parameters for this step
        step_params = base_params.copy()  # Start with base parameters
        
        # Add anchor entity if available
        if anchor_entity:
            step_params["anchor"] = anchor_entity
        
        # For chained steps, we might want to pass results from previous steps
        # For now, we'll use the same base parameters for all steps
        # TODO: In future, implement result passing between chain steps
        
        validated_chain.append({
            "intent": template_name,
            "params": step_params
        })
        
        logger.debug(f"Chain step {i}: {template_name} with params {step_params}")
    
    return validated_chain

def _find_best_anchor_entity_semantic(candidate: str) -> str | None:
    """
    Use schema embeddings to find the best matching schema term for a candidate entity.
    
    Args:
        candidate: The candidate entity string to map
        
    Returns:
        Mapped entity label or None if no good match found
    """
    if not candidate or not candidate.strip():
        return None
    
    candidate = candidate.strip()
    
    try:
        with tracer.start_as_current_span("planner.semantic_mapping") as span:
            span.set_attribute("candidate_entity", candidate)
            
            # Get configuration
            schema_embeddings_config = CFG.get('schema_embeddings', {})
            index_name = schema_embeddings_config.get('index_name', 'schema_embeddings')
            top_k = schema_embeddings_config.get('top_k', 5)
            timeout = CFG.get('guardrails', {}).get('neo4j_timeout', 10)
            
            # Compute embedding for candidate
            embedding_provider = get_embedding_provider()
            embeddings = embedding_provider.get_embeddings([candidate])
            
            if not embeddings or not embeddings[0]:
                logger.warning(f"Failed to generate embedding for candidate '{candidate}'")
                return None
            
            candidate_embedding = embeddings[0]
            span.set_attribute("embedding_dimensions", len(candidate_embedding))
            
            # Query vector index for nearest schema terms
            neo4j_client = Neo4jClient()
            
            vector_query = f"""
            CALL db.index.vector.queryNodes('{index_name}', $top_k, $embedding) 
            YIELD node, score 
            RETURN node.id as id, node.term as term, node.type as type, 
                   node.canonical_id as canonical_id, score
            ORDER BY score DESC
            """
            
            params = {
                'top_k': top_k,
                'embedding': candidate_embedding
            }
            
            results = neo4j_client.execute_read_query(
                vector_query, 
                params, 
                timeout=timeout,
                query_name="semantic_schema_lookup"
            )
            
            if not results:
                logger.info(f"No schema embeddings found for candidate '{candidate}'")
                return None
            
            # Process results and find best label match
            cypher_gen = CypherGenerator()
            
            for result in results:
                schema_id = result.get('id')
                term = result.get('term')
                term_type = result.get('type')
                canonical_id = result.get('canonical_id')
                score = result.get('score', 0.0)
                
                span.add_event("schema_match_found", {
                    "schema_id": schema_id,
                    "term": term,
                    "type": term_type,
                    "canonical_id": canonical_id,
                    "similarity_score": score
                })
                
                # If it's a label type and exists in allow_list, use it
                if term_type == 'label':
                    # Validate the canonical term is in allow_list
                    if cypher_gen.validate_label(canonical_id):
                        logger.info(f"Semantic mapping: '{candidate}' -> '{canonical_id}' (score: {score:.3f})")
                        span.set_attribute("mapped_entity", canonical_id)
                        span.set_attribute("similarity_score", score)
                        return canonical_id
                    else:
                        logger.debug(f"Schema term '{canonical_id}' not in allow_list, skipping")
                
                # For relationship or property types, we might map them differently in the future
                # For now, focus on label mapping
            
            logger.info(f"No suitable label mapping found for candidate '{candidate}'")
            return None
            
    except Exception as e:
        logger.error(f"Semantic mapping failed for candidate '{candidate}': {e}")
        return None

def _detect_intent(question: str):
    q = question.lower()
    if "who founded" in q:
        return "company_founder_query"
    if "product" in q:
        return "company_product_query"
    return "general_rag_query"

def generate_plan(question: str) -> QueryPlan:
    """Generate a query plan using LLM-driven intent classification and parameter extraction."""
    
    # Build template summary for LLM
    template_summary = _build_template_summary()
    
    # Create prompt for LLM-driven planning
    prompt = f"""You are a query planner for a graph database system. Your task is to analyze the user question and select the best template intent with appropriate parameters.

Available Templates:
{template_summary}

User Question: "{question}"

Instructions:
1. Select the most appropriate template intent from the available templates
2. Extract any entity names, company names, or other parameters needed for the query
3. Provide a confidence score (0.0 to 1.0) for your classification
4. If the query is complex and might need multiple steps, suggest a chain of template names

Guidelines:
- For questions about company founders, use "company_founder_query"
- For general questions about entities and relationships, use "general_rag_query"
- Extract specific entity names (companies, people, products) as parameters
- Set confidence based on how clear the intent is
- Use chain only for multi-step queries that need multiple templates

Respond with your classification:"""

    try:
        # Use planner-specific model from config
        planner_model = CFG.get('llm', {}).get('planner_model', CFG['llm']['model'])
        planner_max_tokens = CFG.get('llm', {}).get('planner_max_tokens', 256)
        
        planner_output = call_llm_structured(
            prompt=prompt,
            schema_model=PlannerOutput,
            model=planner_model,
            max_tokens=planner_max_tokens
        )
        
        # Validate the returned intent is in available templates
        from graph_rag.cypher_generator import CYPHER_TEMPLATES
        if planner_output.intent not in CYPHER_TEMPLATES:
            logger.warning(f"LLM returned invalid intent '{planner_output.intent}'. Falling back to 'general_rag_query'.")
            planner_output.intent = "general_rag_query"
        
        # Extract anchor entity from params or fallback to entity extraction
        anchor_entity = None
        if 'anchor' in planner_output.params:
            anchor_entity = planner_output.params['anchor']
        elif 'entity' in planner_output.params:
            anchor_entity = planner_output.params['entity']
        elif 'company' in planner_output.params:
            anchor_entity = planner_output.params['company']
        
        # If no anchor found in params, try entity extraction as fallback
        if not anchor_entity:
            try:
                entity_prompt = f"Extract person and organization entity names from: {question}"
                extracted = call_llm_structured(entity_prompt, ExtractedEntities)
                if extracted.names:
                    # Try semantic mapping for the first extracted entity
                    candidate_entity = extracted.names[0]
                    semantic_anchor = _find_best_anchor_entity_semantic(candidate_entity)
                    if semantic_anchor:
                        anchor_entity = semantic_anchor
                        logger.info(f"Using semantic mapping result: {candidate_entity} -> {anchor_entity}")
                    else:
                        # Fall back to the original extracted entity
                        anchor_entity = candidate_entity
                        logger.info(f"No semantic mapping found, using original entity: {anchor_entity}")
            except LLMStructuredError as e:
                logger.warning(f"Entity extraction fallback failed: {e}")
        
        # Process and validate chain if present
        validated_chain = None
        if planner_output.chain:
            validated_chain = _validate_and_build_chain(planner_output.chain, planner_output.params, anchor_entity)
            logger.info(f"LLM Planner - Chain: {[step['intent'] for step in validated_chain]}")
        
        logger.info(f"LLM Planner - Intent: {planner_output.intent}, Anchor: {anchor_entity}, Confidence: {planner_output.confidence}")
        
        return QueryPlan(
            intent=planner_output.intent,
            anchor_entity=anchor_entity,
            question=question,
            chain=validated_chain
        )
        
    except LLMStructuredError as e:
        logger.error(f"LLM planning failed: {e}. Falling back to rule-based detection.")
        
        # Fallback to simple rule-based detection
        intent = _detect_intent(question)
        
        # Try entity extraction as fallback
        anchor_entity = None
        try:
            entity_prompt = f"Extract person and organization entity names from: {question}"
            extracted = call_llm_structured(entity_prompt, ExtractedEntities)
            if extracted.names:
                # Try semantic mapping for the first extracted entity
                candidate_entity = extracted.names[0]
                semantic_anchor = _find_best_anchor_entity_semantic(candidate_entity)
                if semantic_anchor:
                    anchor_entity = semantic_anchor
                    logger.info(f"Fallback semantic mapping: {candidate_entity} -> {anchor_entity}")
                else:
                    # Fall back to the original extracted entity
                    anchor_entity = candidate_entity
                    logger.info(f"Fallback: no semantic mapping, using original entity: {anchor_entity}")
        except LLMStructuredError:
            logger.warning("Entity extraction also failed. Using no anchor entity.")
        
        return QueryPlan(
            intent=intent,
            anchor_entity=anchor_entity,
            question=question,
            chain=None  # No chain for fallback
        )
