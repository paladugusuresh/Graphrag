# graph_rag/planner.py
"""
Simplified query planner for Student Support domain that generates intent+params without template selection.
The planner extracts intent and entities (students, staff, interventions, goals), using semantic mapping for anchor resolution.
Aligned with Student, Goal, InterventionPlan, Referral, and CaseWorker entities.
"""
from pydantic import BaseModel, Field
from graph_rag.observability import get_logger, tracer, planner_latency_seconds, mapping_similarity, create_pipeline_span, add_span_attributes
from graph_rag.llm_client import call_llm_structured, LLMStructuredError
from graph_rag.cypher_generator import validate_label, load_allow_list
from graph_rag.semantic_mapper import map_term, get_best_match, SynonymMapper
from graph_rag.config_manager import get_config_value
from graph_rag.flags import MAPPER_ENABLED

logger = get_logger(__name__)

# Global SynonymMapper instance (lazy initialization)
_synonym_mapper = None


def _get_synonym_mapper() -> SynonymMapper:
    """Get or create the global SynonymMapper instance"""
    global _synonym_mapper
    if _synonym_mapper is None:
        _synonym_mapper = SynonymMapper()
    return _synonym_mapper

class ExtractedEntities(BaseModel):
    """Model for extracted entity names from a question."""
    names: list[str] = Field(default_factory=list, description="List of entity names extracted from the question")

class PlannerOutput(BaseModel):
    """Simplified planner output with intent and parameters."""
    intent: str = Field(description="Query intent label for LLM guidance (advisory only)")
    params: dict = Field(default_factory=dict, description="Extracted parameters and entities")
    confidence: float | None = Field(default=None, description="Confidence score for intent classification")

class QueryPlan(BaseModel):
    """Simplified query plan with intent, anchor entity, and question."""
    intent: str = Field(description="Query intent label (advisory for LLM)")
    anchor_entity: str | None = Field(default=None, description="Resolved anchor entity label")
    question: str = Field(description="Original user question")
    params: dict = Field(default_factory=dict, description="Additional parameters extracted from question")

def _find_best_anchor_entity_semantic(candidate: str) -> str | None:
    """
    Use semantic mapper to find the best matching schema term for a candidate entity.
    
    Args:
        candidate: The candidate entity string to map
        
    Returns:
        Mapped entity label or None if no good match found
    """
    if not candidate or not candidate.strip():
        return None
    
    candidate = candidate.strip()
    
    # Check if mapper is enabled
    if not MAPPER_ENABLED():
        logger.debug("SynonymMapper disabled, skipping semantic mapping")
        return None
    
    try:
        with tracer.start_as_current_span("planner.semantic_mapping") as span:
            span.set_attribute("candidate_entity", candidate)
            span.set_attribute("mapper_enabled", True)
            
            # Use SynonymMapper for label mapping
            mapper = _get_synonym_mapper()
            mapping_result = mapper.map_label(candidate)
            
            if mapping_result:
                canonical_id = mapping_result.get('canonical_id')
                score = mapping_result.get('score', 0.0)
                method = mapping_result.get('method', 'unknown')
                
                span.add_event("schema_match_found", {
                    "term": mapping_result.get('term'),
                    "type": "label",
                    "canonical_id": canonical_id,
                    "similarity_score": score,
                    "method": method
                })
                
                # Record mapping similarity metric
                mapping_similarity.observe(score)
                
                # Validate the canonical term is in allow_list
                allow_list = load_allow_list()
                if validate_label(canonical_id, allow_list) != "`Entity`":  # Check if it's not the fallback
                    logger.info(f"Synonym mapping: '{candidate}' -> '{canonical_id}' (score: {score:.3f}, method: {method})")
                    span.set_attribute("mapped_entity", canonical_id)
                    span.set_attribute("similarity_score", score)
                    span.set_attribute("mapping_method", method)
                    return canonical_id
                else:
                    logger.debug(f"Schema term '{canonical_id}' not in allow_list, skipping")
            
            logger.info(f"No suitable label mapping found for candidate '{candidate}'")
            return None
            
    except Exception as e:
        logger.error(f"Semantic mapping failed for candidate '{candidate}': {e}")
        return None

def _detect_intent(question: str) -> str:
    """
    Simple rule-based intent detection for fallback scenarios.
    Aligned with Student Support domain.
    
    Args:
        question: User question
        
    Returns:
        Intent label (advisory only, not for template selection)
    """
    q = question.lower()
    
    # Simple pattern matching for student support domain intents
    if "intervention" in q or "intervention plan" in q:
        return "student_intervention_query"
    if "goal" in q and ("student" in q or "academic" in q or "behavioral" in q):
        return "student_goal_query"
    if "referral" in q or "refer" in q:
        return "student_referral_query"
    if "progress" in q or "performance" in q or "achievement" in q:
        return "student_progress_query"
    if "case" in q and ("manager" in q or "worker" in q or "staff" in q):
        return "case_management_query"
    if "support" in q or "assistance" in q or "help" in q:
        return "student_support_query"
    if "student" in q and ("info" in q or "details" in q or "about" in q):
        return "student_info_query"
    
    # Default to general query
    return "general_query"

def generate_plan(question: str) -> QueryPlan:
    """
    Generate a simplified query plan with intent and anchor entity.
    
    The planner no longer selects templates but provides advisory intent labels
    that can guide LLM Cypher generation. The intent is descriptive, not prescriptive.
    
    Args:
        question: User question
        
    Returns:
        QueryPlan with intent, anchor_entity, and params
    """
    
    with create_pipeline_span("planner.generate_plan", question=question[:100]) as span:
        with planner_latency_seconds.time():
            # Create prompt for LLM-driven intent classification (Student Support domain)
    prompt = f"""You are a query planner for a Student Support graph database system. Your task is to analyze the user question and identify the query intent with appropriate parameters.

User Question: "{question}"

Instructions:
1. Identify the query intent as a descriptive label for student support queries
2. Extract any entity names (student names, staff names, goal types, intervention types) as parameters
3. Provide a confidence score (0.0 to 1.0) for your classification

Guidelines:
- For questions about intervention plans, use "student_intervention_query"
- For questions about student goals (academic, behavioral, social), use "student_goal_query"
- For questions about referrals, use "student_referral_query"
- For questions about student progress or performance, use "student_progress_query"
- For questions about case workers or case management, use "case_management_query"
- For questions about support services or assistance, use "student_support_query"
- For questions about student information or details, use "student_info_query"
- For general relationship queries, use "general_query"
- Extract student names, staff names, dates, and other specific entities as parameters
- Use descriptive parameter keys: "student_name", "staff_name", "goal_type", "intervention_type", "date_range"

Example intents: "student_intervention_query", "student_goal_query", "student_referral_query", "student_progress_query", "case_management_query", "student_support_query", "general_query"

Respond with your classification:"""

    try:
        # Use planner-specific model from config
        planner_model = get_config_value('llm.planner_model') or get_config_value('llm.model', 'gemini-2.0-flash-exp')
        planner_max_tokens = get_config_value('llm.planner_max_tokens', 256)
        
        planner_output = call_llm_structured(
            prompt=prompt,
            schema_model=PlannerOutput,
            model=planner_model,
            max_tokens=planner_max_tokens
        )
        
        logger.info(f"LLM Planner - Intent: {planner_output.intent}, Confidence: {planner_output.confidence}")
        
        add_span_attributes(span, 
            intent=planner_output.intent,
            confidence=planner_output.confidence,
            planner_model=planner_model
        )
        
        # Extract anchor entity from params
        anchor_entity = None
        candidate_entity = None
        
        # Check common param keys for entity names (student support domain)
        for key in ['anchor', 'entity', 'student_name', 'staff_name', 'student', 'staff', 'person', 'case_worker']:
            if key in planner_output.params:
                candidate_entity = planner_output.params[key]
                break
        
        # If no anchor found in params, try entity extraction as fallback
        if not candidate_entity:
            try:
                entity_prompt = f"Extract student names, staff names, and case worker names from: {question}"
                extracted = call_llm_structured(entity_prompt, ExtractedEntities)
                if extracted.names:
                    candidate_entity = extracted.names[0]
                    logger.debug(f"Extracted entity from question: {candidate_entity}")
            except LLMStructuredError as e:
                logger.warning(f"Entity extraction fallback failed: {e}")
        
        # If we have a candidate entity, try semantic mapping
        if candidate_entity:
            semantic_anchor = _find_best_anchor_entity_semantic(candidate_entity)
            if semantic_anchor:
                anchor_entity = semantic_anchor
                logger.info(f"Using semantic mapping result: {candidate_entity} -> {anchor_entity}")
            else:
                # Fall back to the original extracted entity
                anchor_entity = candidate_entity
                logger.info(f"No semantic mapping found, using original entity: {anchor_entity}")
        
        add_span_attributes(span,
            candidate_entity=candidate_entity,
            anchor_entity=anchor_entity,
            params_count=len(planner_output.params)
        )
        
        return QueryPlan(
            intent=planner_output.intent,
            anchor_entity=anchor_entity,
            question=question,
            params=planner_output.params
        )
        
    except LLMStructuredError as e:
        logger.error(f"LLM planning failed: {e}. Falling back to rule-based detection.")
        
        # Fallback to simple rule-based detection
        intent = _detect_intent(question)
        
        # Try entity extraction as fallback
        anchor_entity = None
        candidate_entity = None
        
        try:
            entity_prompt = f"Extract student names, staff names, and case worker names from: {question}"
            extracted = call_llm_structured(entity_prompt, ExtractedEntities)
            if extracted.names:
                candidate_entity = extracted.names[0]
                logger.debug(f"Fallback: extracted entity from question: {candidate_entity}")
        except LLMStructuredError:
            logger.warning("Entity extraction also failed in fallback.")
        
        # Try semantic mapping for fallback entity
        if candidate_entity:
            semantic_anchor = _find_best_anchor_entity_semantic(candidate_entity)
            if semantic_anchor:
                anchor_entity = semantic_anchor
                logger.info(f"Fallback semantic mapping: {candidate_entity} -> {anchor_entity}")
            else:
                # Fall back to the original extracted entity
                anchor_entity = candidate_entity
                logger.info(f"Fallback: no semantic mapping, using original entity: {anchor_entity}")
        
        return QueryPlan(
            intent=intent,
            anchor_entity=anchor_entity,
            question=question,
            params={}
        )
