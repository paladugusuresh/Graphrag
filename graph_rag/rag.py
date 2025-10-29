# graph_rag/rag.py
"""
LLM-driven RAG pipeline: Cypher generation → validation → execution → augmentation → summarization.
Replaces template-based approach with fully adaptive LLM-generated queries.
"""
import os
import re
import json
import uuid
from typing import Optional, List, Dict, Any
from graph_rag.planner import generate_plan
from graph_rag.retriever import Retriever
from graph_rag.observability import get_logger, tracer, create_pipeline_span, add_span_attributes, set_span_attr
from opentelemetry.trace import get_current_span
from graph_rag.audit_store import audit_store
from graph_rag.llm_client import call_llm_structured, LLMStructuredError
from graph_rag.config_manager import get_config_value
from graph_rag.schemas import CypherGenerationOutput, SummaryOutput
from graph_rag.cypher_validator import validate_cypher
from graph_rag.query_executor import safe_execute
from graph_rag.rag_augmentor import augment_results
from graph_rag.response_formatter import build_summary_prompt, rows_to_table
from graph_rag.schema_manager import get_allow_list
from graph_rag.formatters import formatters_manager

logger = get_logger(__name__)

def _build_error_response(
    question: str,
    error_message: str,
    trace_id: str,
    error_code: str = None,
    error_details: Dict[str, Any] = None,
    audit_id: str = None,
    cypher: str = None,
    params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Build a structured error response for failed queries.
    
    Args:
        question: Original user question
        error_message: Clean user-visible error message
        trace_id: Trace ID for debugging
        error_code: Machine-readable error code (e.g., "unknown_property", "max_hops_exceeded")
        error_details: Detailed error information for developers
        audit_id: Audit log entry ID
        cypher: Generated Cypher query (if available)
        params: Query parameters (if available)
        
    Returns:
        Structured error response dictionary
    """
    response = {
        "question": question,
        "error": error_message,
        "trace_id": trace_id
    }
    
    if error_code:
        response["error_code"] = error_code
    
    if error_details:
        # Provide detailed error information for developers
        response["error_details"] = error_details
    
    if audit_id:
        response["audit_id"] = audit_id
    
    if cypher:
        response["cypher"] = cypher
    
    if params:
        response["params"] = params
    
    return response


class RAGChain:
    def __init__(self):
        """Initialize RAG chain with new LLM-driven pipeline"""
        self.retriever = Retriever()

    def _build_cypher_generation_prompt(self, plan, allow_list: Dict[str, Any]) -> str:
        """
        Build prompt for LLM to generate Cypher query.
        
        Includes allow-list context to reduce hallucination and provides clear examples.
        """
        # Get top 20 labels and relationships from allow_list
        labels = allow_list.get('node_labels', [])[:20]
        relationships = allow_list.get('relationship_types', [])[:20]
        
        prompt = f"""You are a Cypher query generation expert for a Neo4j graph database.

**User Question:** "{plan.question}"

**Query Intent:** {plan.intent}

**Schema Information:**
Available Node Labels: {', '.join(labels)}
Available Relationship Types: {', '.join(relationships)}

**Anchor Entity:** {plan.anchor_entity if plan.anchor_entity else 'None'}
**Extracted Parameters:** {json.dumps(plan.params) if hasattr(plan, 'params') and plan.params else '{}'}

**Task:** Generate a Cypher query to answer the user's question using the provided schema.

**Guidelines:**
1. Use ONLY the node labels and relationship types listed above
2. Use the anchor entity and parameters to construct the query
3. Include appropriate LIMIT clauses (typically 10-20 results)
4. Return specific properties, not entire nodes
5. Use parameterized queries where appropriate
6. For student support queries:
   - Student information: MATCH (s:Student) WHERE...
   - Intervention plans: MATCH (s:Student)-[:HAS_INTERVENTION]->(i:InterventionPlan)
   - Goals: MATCH (s:Student)-[:HAS_GOAL]->(g:Goal)
   - Referrals: MATCH (s:Student)-[:HAS_REFERRAL]->(r:Referral)
   - Case workers: MATCH (s:Student)-[:ASSIGNED_TO]->(cw:CaseWorker)
7. If you return a node, ALWAYS return its ID using 'AS primary_id' (e.g., RETURN n.id AS primary_id, n.name AS name)

**Example Input/Output:**

Example 1:
Question: "What are the intervention plans for student Isabella Thomas?"
Intent: student_intervention_query
Output:
{{
  "cypher": "MATCH (s:Student {{name: $student_name}})-[:HAS_INTERVENTION]->(i:InterventionPlan) RETURN s.id AS primary_id, s.name AS student, i.plan_id AS plan_id, i.description AS description, i.start_date AS start_date LIMIT 10",
  "params": {{"student_name": "Isabella Thomas"}}
}}

Example 2:
Question: "Who are the students with active goals?"
Intent: student_goal_query
Output:
{{
  "cypher": "MATCH (s:Student)-[:HAS_GOAL]->(g:Goal) WHERE g.status = 'active' RETURN s.id AS primary_id, s.name AS student_name, count(g) AS goal_count ORDER BY goal_count DESC LIMIT 20",
  "params": {{}}
}}

**IMPORTANT:** Return ONLY valid JSON matching the required schema. No additional text or explanations.

**Required JSON Schema:**
{{
  "cypher": "string (the Cypher query)",
  "params": {{}} (object with query parameters)
}}

Generate the Cypher query now:"""
        
        return prompt

    def _build_template_params(self, plan, template_cypher: str) -> Dict[str, Any]:
        """
        Build parameters for Cypher template based on plan and template content.
        
        Uses canonical parameter name 'student_name' internally, but maps to legacy
        template parameter names (e.g., 'student') for backward compatibility.
        
        Args:
            plan: Query plan with intent and parameters
            template_cypher: The template Cypher query
            
        Returns:
            Dictionary of parameters for the template
        """
        params = {}
        
        # Extract student name from canonical parameter 'student_name' or fallback to legacy 'student'
        student_name = None
        if plan.params and 'student_name' in plan.params:
            student_name = plan.params['student_name']
        elif plan.params and 'student' in plan.params:
            # Legacy fallback for backward compatibility
            student_name = plan.params['student']
        elif plan.anchor_entity:
            student_name = plan.anchor_entity
        
        # Map to template parameter names
        # Legacy templates use $student, so map from canonical student_name
        if student_name:
            if '$student' in template_cypher:
                params['student'] = student_name
            # Also support new templates that might use $student_name
            if '$student_name' in template_cypher:
                params['student_name'] = student_name
        
        # Add default limit if not specified
        if '$limit' in template_cypher and 'limit' not in params:
            params['limit'] = 20
        
        # Add date range parameters for eval_reports_for_student_in_range
        if plan.intent == "eval_reports_for_student_in_range":
            if plan.params and 'from' in plan.params:
                params['from'] = plan.params['from']
            else:
                # Default to last 6 months if not specified
                from datetime import datetime, timedelta
                six_months_ago = datetime.now() - timedelta(days=180)
                params['from'] = six_months_ago.strftime('%Y-%m-%d')
            
            if plan.params and 'to' in plan.params:
                params['to'] = plan.params['to']
            else:
                # Default to today
                from datetime import datetime
                params['to'] = datetime.now().strftime('%Y-%m-%d')
        
        logger.debug(f"Built template parameters for intent '{plan.intent}': {params}")
        return params

    def _extract_primary_ids(self, rows: List[Dict[str, Any]]) -> List[str]:
        """
        Extract primary IDs from query result rows.
        
        Simplified logic: Only looks for the explicit 'primary_id' key that the LLM
        is instructed to return in the Cypher generation prompt (Guideline 7).
        This enforces an explicit contract and removes brittle guessing logic.
        """
        primary_ids = []
        
        for row in rows:
            if 'primary_id' in row and row['primary_id']:
                primary_ids.append(str(row['primary_id']))
        
        # Return unique IDs
        return list(set(primary_ids))

    def _verify_citations(self, summary: str, chunk_ids: List[str], question: str, trace_id: str) -> Dict[str, Any]:
        """
        Citation verification (DISABLED for MVP stability).
        
        Returns a default "verified" response without performing actual checks.
        This is an MVP trade-off to simplify output and remove a non-critical feature.
        """
        return {
            "verified": True,
            "cited_ids": [],
            "provided_ids": [],
            "unknown_citations": [],
            "verification_action": ""
        }

    def invoke(self, question: str, format_type: str | None = None) -> Dict[str, Any]:
        """
        Execute the complete LLM-driven RAG pipeline.
        
        Flow:
        1. Generate plan (intent + anchor entity)
        2. Generate Cypher query via LLM
        3. Validate Cypher
        4. Execute query safely
        5. Augment results with graph context
        6. Generate summary via LLM
        7. Apply formatting if requested (text/table/graph)
        8. Return comprehensive response
        
        Args:
            question: User question to process
            format_type: Optional format type ("text", "table", "graph")
        """
        with create_pipeline_span("rag.invoke", question=question[:100]) as span:
            current_span = get_current_span()
            trace_id = f"{current_span.context.trace_id:032x}" if current_span and current_span.context.is_valid else "no-trace"
            
            try:
                # Step 1: Generate plan
                with create_pipeline_span("rag.generate_plan") as plan_span:
                    plan = generate_plan(question)
                    add_span_attributes(plan_span,
                        intent=plan.intent,
                        anchor_entity=plan.anchor_entity or "none"
                    )
                    set_span_attr(span, "plan.intent", plan.intent)
                    set_span_attr(span, "plan.anchor_entity", plan.anchor_entity or "none")
                    logger.info(f"Plan generated: intent={plan.intent}, anchor={plan.anchor_entity}")
                
                # Step 2: Generate Cypher via Template or LLM
                with create_pipeline_span("rag.generate_cypher") as cypher_span:
                    try:
                        allow_list = get_allow_list()
                        
                        # Try template-based generation first
                        from graph_rag.cypher_generator import generate_cypher_with_template, generate_cypher_with_llm, try_load_template
                        
                        # Check if a template exists for this intent
                        template_cypher_raw = try_load_template(plan.intent)
                        
                        if template_cypher_raw:
                            # Build template parameters (maps canonical student_name to legacy template params)
                            template_params = self._build_template_params(plan, template_cypher_raw)
                            
                            # Validate and generate template Cypher
                            template_cypher = generate_cypher_with_template(plan.intent, template_params)
                            
                            if template_cypher:
                                # Use template with mapped parameters
                                cypher_output = CypherGenerationOutput(
                                    cypher=template_cypher,
                                    params=template_params
                                )
                            else:
                                # Template validation failed, template_cypher will be None
                                template_cypher = None
                        else:
                            template_cypher = None
                        
                        if template_cypher:
                            logger.info(f"Template Cypher used for intent '{plan.intent}': {template_cypher[:100]}...")
                            add_span_attributes(cypher_span,
                                template_used=True,
                                intent=plan.intent,
                                params_count=len(plan.params)
                            )
                            set_span_attr(cypher_span, "template_used", True)
                            set_span_attr(cypher_span, "intent", plan.intent)
                        else:
                            # Fall back to LLM generation with strict parameterization
                            try:
                                llm_cypher = generate_cypher_with_llm(plan.intent, plan.params, plan.question)
                                cypher_output = CypherGenerationOutput(
                                    cypher=llm_cypher,
                                    params=plan.params
                                )
                                logger.info(f"LLM Cypher generated for intent '{plan.intent}': {llm_cypher[:100]}...")
                                add_span_attributes(cypher_span,
                                    template_used=False,
                                    cypher_generated=llm_cypher[:100],
                                    params_count=len(plan.params)
                                )
                                set_span_attr(cypher_span, "template_used", False)
                                set_span_attr(cypher_span, "cypher_generated", llm_cypher[:100])
                            except RuntimeError as e:
                                logger.error(f"LLM Cypher generation failed: {e}")
                                raise LLMStructuredError(f"LLM Cypher generation failed: {e}") from e
                        
                        add_span_attributes(cypher_span,
                            cypher_generated=cypher_output.cypher[:100],
                            params_count=len(cypher_output.params)
                        )
                        set_span_attr(cypher_span, "cypher_generated", cypher_output.cypher[:100])
                        
                    except LLMStructuredError as e:
                        logger.error(f"Cypher generation failed: {e}")
                        
                        # Extract error details from LLMStructuredError if available
                        error_details = getattr(e, 'error_details', {})
                        error_code = error_details.get('error_code', 'cypher_generation_failed')
                        
                        # Record audit entry
                        audit_id = audit_store.record({
                            "event_type": "cypher_generation_failed",
                            "trace_id": trace_id,
                            "question": question,
                            "error": str(e),
                            "error_code": error_code,
                            "error_details": error_details
                        })
                        
                        return _build_error_response(
                            question=question,
                            error_message="Failed to generate query",
                            trace_id=trace_id,
                            error_code=error_code,
                            error_details={"reason": str(e), **error_details},
                            audit_id=audit_id
                        )
                
                # Step 3: Validate Cypher
                with create_pipeline_span("rag.validate_cypher") as validate_span:
                    is_valid, validation_details = validate_cypher(cypher_output.cypher)
                    
                    add_span_attributes(validate_span,
                        is_valid=is_valid,
                        validation_details=validation_details
                    )
                    
                    if not is_valid:
                        logger.warning(f"Cypher validation failed: {validation_details}")
                        
                        # Extract error code and build machine-readable hints
                        error_code = validation_details.get("blocked_reason") or "validation_failed"
                        
                        # Build developer-friendly hints
                        hints = []
                        if validation_details.get("invalid_properties"):
                            props = validation_details["invalid_properties"]
                            hints.append(f"Unknown properties: {', '.join(props)}. Check allow-list and schema.")
                        if validation_details.get("invalid_labels"):
                            labels = validation_details["invalid_labels"]
                            hints.append(f"Unknown labels: {', '.join(labels)}. Check allow-list and schema.")
                        if validation_details.get("invalid_relationships"):
                            rels = validation_details["invalid_relationships"]
                            hints.append(f"Unknown relationships: {', '.join(rels)}. Check allow-list and schema.")
                        if "max_hops" in error_code or "unbounded" in error_code:
                            hints.append(f"Traversal exceeds depth cap. Use simpler patterns or increase MAX_HOPS.")
                        if "limit" in error_code:
                            hints.append(f"Query missing or exceeds LIMIT. Ensure LIMIT $limit is present.")
                        
                        # Build error details for developers
                        error_details = {
                            "validation_details": validation_details,
                            "hints": hints,
                            "cypher_preview": cypher_output.cypher[:200]
                        }
                        
                        # Record audit entry
                        audit_id = audit_store.record({
                            "event_type": "cypher_validation_failed",
                            "trace_id": trace_id,
                            "question": question,
                            "cypher": cypher_output.cypher,
                            "error_code": error_code,
                            "validation_details": validation_details,
                            "hints": hints
                        })
                        
                        return _build_error_response(
                            question=question,
                            error_message="Invalid query",
                            trace_id=trace_id,
                            error_code=error_code,
                            error_details=error_details,
                            audit_id=audit_id,
                            cypher=cypher_output.cypher,
                            params=cypher_output.params
                        )
                
                # Step 4: Execute query safely
                with create_pipeline_span("rag.execute_query") as exec_span:
                    try:
                        primary_rows = safe_execute(
                            cypher=cypher_output.cypher,
                            params=cypher_output.params
                        )
                        
                        add_span_attributes(exec_span,
                            rows_returned=len(primary_rows),
                            result_count=len(primary_rows)
                        )
                        set_span_attr(exec_span, "rows_returned", len(primary_rows))
                        logger.info(f"Query executed successfully: {len(primary_rows)} rows returned")
                        
                    except Exception as e:
                        logger.error(f"Query execution failed: {e}")
                        
                        # Parse error message for specific error codes
                        error_str = str(e).lower()
                        if 'timeout' in error_str:
                            error_code = 'query_timeout'
                            hints = ["Query exceeded timeout limit. Consider simplifying the query or increasing timeout."]
                        elif 'property' in error_str and 'not found' in error_str:
                            error_code = 'unknown_property'
                            hints = ["Property not found on node. Check allow-list and schema."]
                        elif 'label' in error_str or 'node' in error_str:
                            error_code = 'schema_error'
                            hints = ["Schema mismatch. Verify labels and relationships in allow-list."]
                        elif 'memory' in error_str or 'resource' in error_str:
                            error_code = 'resource_exhaustion'
                            hints = ["Query consumed too many resources. Add LIMIT or simplify traversal."]
                        else:
                            error_code = 'execution_failed'
                            hints = []
                        
                        # Build error details
                        error_details = {
                            "reason": str(e),
                            "hints": hints,
                            "cypher_preview": cypher_output.cypher[:200]
                        }
                        
                        # Record audit entry
                        audit_id = audit_store.record({
                            "event_type": "query_execution_failed",
                            "trace_id": trace_id,
                            "question": question,
                            "cypher": cypher_output.cypher,
                            "error": str(e),
                            "error_code": error_code,
                            "hints": hints
                        })
                        
                        return _build_error_response(
                            question=question,
                            error_message="Query execution failed",
                            trace_id=trace_id,
                            error_code=error_code,
                            error_details=error_details,
                            audit_id=audit_id,
                            cypher=cypher_output.cypher,
                            params=cypher_output.params
                        )
                
                # Step 5: Augment with graph context
                with create_pipeline_span("rag.augment_results") as aug_span:
                    primary_ids = self._extract_primary_ids(primary_rows)
                    set_span_attr(aug_span, "primary_ids_count", len(primary_ids))
                    
                    if primary_ids:
                        try:
                            augmented = augment_results(primary_ids)
                            snippets = augmented.get('neighbors', [])
                            set_span_attr(aug_span, "snippets_count", len(snippets))
                            logger.info(f"Results augmented: {len(snippets)} snippets")
                        except Exception as e:
                            logger.warning(f"Augmentation failed: {e}")
                            snippets = []
                    else:
                        snippets = []
                        logger.info("No primary IDs extracted; skipping augmentation")
                
                # Step 6: Generate summary via LLM
                with create_pipeline_span("rag.generate_summary") as summary_span:
                    try:
                        # Prepare snippets dict for prompt
                        snippets_dict = {s.get('id', f"node_{i}"): s.get('text', '')[:200] for i, s in enumerate(snippets[:5])}
                        
                        summary_prompt = build_summary_prompt(
                            question=question,
                            rows=primary_rows,
                            snippets=snippets_dict,
                            allow_list=allow_list
                        )
                        
                        summary_output = call_llm_structured(
                            prompt=summary_prompt,
                            schema_model=SummaryOutput
                        )
                        
                        summary = summary_output.summary
                        citations = summary_output.citations
                        table = summary_output.table
                        
                        add_span_attributes(summary_span,
                            summary_length=len(summary),
                            citations_count=len(citations),
                            snippets_count=len(snippets_dict)
                        )
                        
                        logger.info(f"Summary generated: {len(summary)} chars, {len(citations)} citations")
                        
                    except LLMStructuredError as e:
                        logger.warning(f"Summary generation failed: {e}. Using fallback.")
                        # Fallback to simple concatenation
                        summary = f"Query returned {len(primary_rows)} results. "
                        if primary_rows:
                            summary += f"Sample: {json.dumps(primary_rows[0])}"
                        citations = []
                        table = rows_to_table(primary_rows) if primary_rows else []
                
                # Step 7: Apply formatters and verify citations
                all_chunk_ids = [s.get('id', '') for s in snippets] + primary_ids
                
                # Use formatters manager for comprehensive formatting
                formatting_result = formatters_manager.format_response(
                    rows=primary_rows,
                    summary=summary,
                    citations=citations,
                    available_ids=all_chunk_ids,
                    format_type=format_type
                )
                
                # Legacy citation verification (for backward compatibility)
                legacy_verification = self._verify_citations(summary, all_chunk_ids, question, trace_id)
                
                # Step 8: Build comprehensive response
                # Generate audit_id for tracking
                audit_id = str(uuid.uuid4())
                
                response = {
                    "question": question,
                    "answer": summary,
                    "cypher": cypher_output.cypher,
                    "params": cypher_output.params,
                    "rows": primary_rows,
                    "row_count": len(primary_rows),
                    "snippets": snippets,
                    "citations": citations,
                    "table": table,
                    "plan": plan.model_dump(),
                    "citation_verification": legacy_verification,
                    "trace_id": trace_id,
                    "audit_id": audit_id
                }
                
                # Add formatted output if formatters are enabled
                if formatting_result:
                    response["formatted"] = formatting_result["formatted"]
                    response["verification_status"] = formatting_result["verification_status"]
                    response["citation_details"] = formatting_result["citation_details"]
                
                # Add final pipeline attributes
                add_span_attributes(span,
                    total_rows=len(primary_rows),
                    total_snippets=len(snippets),
                    total_citations=len(citations),
                    pipeline_success=True
                )
                
                logger.info(f"RAG pipeline completed successfully for question: {question}")
                return response
                
            except Exception as e:
                logger.error(f"RAG pipeline failed: {e}")
                audit_store.record({
                    "event_type": "rag_pipeline_failed",
                    "trace_id": trace_id,
                    "question": question,
                    "error": str(e)
                })
                return {
                    "question": question,
                    "error": "RAG pipeline failed",
                    "error_details": str(e),
                    "trace_id": trace_id
                }

rag_chain = RAGChain()
