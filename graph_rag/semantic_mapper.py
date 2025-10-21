# graph_rag/semantic_mapper.py
"""
Semantic mapping module for mapping candidate terms to schema terms using embeddings.

Provides SynonymMapper class with type-specific mapping (labels, relationships, properties)
and fallback heuristics (exact, plural, fuzzy matching) when embedding similarity is low.
"""
from typing import List, Dict, Any, Optional
import re
from graph_rag.observability import get_logger, embedding_match_score
from graph_rag.config_manager import get_config_value
from graph_rag.embeddings import get_embedding_provider
from graph_rag.neo4j_client import Neo4jClient
from graph_rag.dev_stubs import is_dev_mode
from graph_rag.audit_store import audit_store
from graph_rag.flags import get_all_flags
from opentelemetry.trace import get_current_span

logger = get_logger(__name__)


def normalize_person_name(name: str) -> str:
    """
    Normalize a person name by stripping common honorifics and trimming whitespace.
    
    This function handles common honorifics (Ms., Mrs., Mr., Dr., etc.) and ensures
    consistent name formatting for person-based queries.
    
    Args:
        name: Raw person name (e.g., "Ms. Garcia", "DR. SMITH", "mr. brooks")
        
    Returns:
        Normalized name with honorifics removed and whitespace trimmed
        
    Examples:
        "Ms. Garcia" -> "Garcia"
        "DR. SMITH" -> "SMITH" 
        "mr. brooks" -> "brooks"
        "Mrs. Rosa Garcia" -> "Rosa Garcia"
        "Dr. John Smith Jr." -> "John Smith Jr."
    """
    if not name or not name.strip():
        return ""
    
    # Common honorifics to remove (case-insensitive)
    honorifics = [
        r'^mr\.?\s+', r'^mrs\.?\s+', r'^ms\.?\s+', r'^miss\.?\s+',
        r'^dr\.?\s+', r'^prof\.?\s+', r'^professor\.?\s+',
        r'^sir\.?\s+', r'^madam\.?\s+', r'^madame\.?\s+',
        r'^rev\.?\s+', r'^reverend\.?\s+', r'^father\.?\s+',
        r'^captain\.?\s+', r'^capt\.?\s+', r'^lieutenant\.?\s+',
        r'^sergeant\.?\s+', r'^sgt\.?\s+', r'^colonel\.?\s+',
        r'^general\.?\s+', r'^admiral\.?\s+', r'^major\.?\s+',
        r'^lt\.?\s+', r'^col\.?\s+', r'^gen\.?\s+', r'^adm\.?\s+'
    ]
    
    normalized_name = name.strip()
    
    # Remove honorifics (case-insensitive)
    for honorific_pattern in honorifics:
        normalized_name = re.sub(honorific_pattern, '', normalized_name, flags=re.IGNORECASE)
    
    # Clean up any extra whitespace
    normalized_name = re.sub(r'\s+', ' ', normalized_name.strip())
    
    logger.debug(f"Name normalization: '{name}' -> '{normalized_name}'")
    return normalized_name


def _normalize_term(term: str) -> str:
    """Normalize term for comparison: lowercase, trim, remove extra spaces"""
    return re.sub(r'\s+', ' ', term.strip().lower())


def _pluralize(term: str) -> str:
    """Simple pluralization heuristic"""
    term = term.strip()
    if term.endswith('s'):
        return term
    elif term.endswith('y'):
        return term[:-1] + 'ies'
    else:
        return term + 's'


def _singularize(term: str) -> str:
    """Simple singularization heuristic"""
    term = term.strip()
    if term.endswith('ies'):
        return term[:-3] + 'y'
    elif term.endswith('s') and not term.endswith('ss'):
        return term[:-1]
    else:
        return term


def _exact_match_fallback(candidate: str, schema_terms: List[str]) -> Optional[str]:
    """Try exact match (case-insensitive) against schema terms"""
    normalized_candidate = _normalize_term(candidate)
    
    for term in schema_terms:
        if _normalize_term(term) == normalized_candidate:
            logger.debug(f"Exact match fallback: '{candidate}' -> '{term}'")
            return term
    
    return None


def _plural_fallback(candidate: str, schema_terms: List[str]) -> Optional[str]:
    """Try plural/singular variants against schema terms"""
    normalized_candidate = _normalize_term(candidate)
    plural_candidate = _normalize_term(_pluralize(candidate))
    singular_candidate = _normalize_term(_singularize(candidate))
    
    for term in schema_terms:
        normalized_term = _normalize_term(term)
        if normalized_term in [plural_candidate, singular_candidate]:
            logger.debug(f"Plural/singular fallback: '{candidate}' -> '{term}'")
            return term
    
    return None


def _fuzzy_fallback(candidate: str, schema_terms: List[str], threshold: float = 0.7) -> Optional[str]:
    """Try fuzzy string matching using simple character overlap"""
    normalized_candidate = _normalize_term(candidate)
    best_match = None
    best_score = 0.0
    
    for term in schema_terms:
        normalized_term = _normalize_term(term)
        
        # Calculate simple character overlap ratio
        if not normalized_candidate or not normalized_term:
            continue
        
        # Jaccard similarity on character level
        set_candidate = set(normalized_candidate)
        set_term = set(normalized_term)
        intersection = len(set_candidate & set_term)
        union = len(set_candidate | set_term)
        
        if union > 0:
            score = intersection / union
            if score > best_score and score >= threshold:
                best_score = score
                best_match = term
    
    if best_match:
        logger.debug(f"Fuzzy fallback: '{candidate}' -> '{best_match}' (score: {best_score:.3f})")
        return best_match
    
    return None

class SynonymMapper:
    """
    Synonym mapper using embedding similarity and fallback heuristics.
    
    Maps user terms to canonical schema terms (labels, relationships, properties)
    using:
    1. Embedding-based semantic similarity (primary)
    2. Exact match fallback (case-insensitive)
    3. Plural/singular variant fallback
    4. Fuzzy string matching fallback
    
    Configurable via:
    - mapper.min_similarity: Minimum cosine similarity threshold (default: 0.62)
    - mapper.top_k: Number of candidates to consider (default: 5)
    - mapper.fuzzy_threshold: Fuzzy match threshold (default: 0.7)
    """
    
    def __init__(self):
        """Initialize the synonym mapper with config values"""
        self.min_similarity = get_config_value('mapper.min_similarity', 0.62)
        self.top_k = get_config_value('mapper.top_k', 5)
        self.fuzzy_threshold = get_config_value('mapper.fuzzy_threshold', 0.7)
        self._allow_list_cache = None
        logger.info(f"SynonymMapper initialized: min_sim={self.min_similarity}, top_k={self.top_k}")
    
    def _get_allow_list(self) -> Dict[str, Any]:
        """Get cached allow list or load it"""
        if self._allow_list_cache is None:
            from graph_rag.schema_manager import get_allow_list
            self._allow_list_cache = get_allow_list()
        return self._allow_list_cache
    
    def _map_with_fallback(self, candidate: str, term_type: str) -> Optional[Dict[str, Any]]:
        """
        Map a candidate term using embeddings and fallbacks.
        
        Args:
            candidate: Term to map
            term_type: Type filter ('label', 'relationship', 'property')
            
        Returns:
            Dict with fields: term, canonical_id, type, score, method
        """
        if not candidate or not candidate.strip():
            return None
        
        # Get schema terms of the requested type
        allow_list = self._get_allow_list()
        if term_type == 'label':
            schema_terms = allow_list.get('node_labels', [])
        elif term_type == 'relationship':
            schema_terms = allow_list.get('relationship_types', [])
        elif term_type == 'property':
            # Extract all unique properties
            properties_dict = allow_list.get('properties', {})
            schema_terms = list(set(prop for props in properties_dict.values() for prop in props))
        else:
            logger.warning(f"Unknown term type: {term_type}")
            return None
        
        if not schema_terms:
            logger.warning(f"No schema terms found for type: {term_type}")
            return None
        
        # Try embedding-based mapping first
        matches = map_term(candidate, top_k=self.top_k)
        
        # Filter by type and threshold
        for match in matches:
            if match.get('type') == term_type and match.get('score', 0.0) >= self.min_similarity:
                canonical_id = match.get('canonical_id', match.get('term'))
                score = match.get('score', 0.0)
                
                logger.info(f"Embedding match: '{candidate}' -> '{canonical_id}' ({term_type}, score: {score:.3f})")
                
                return {
                    'term': match.get('term'),
                    'canonical_id': canonical_id,
                    'type': term_type,
                    'score': score,
                    'method': 'embedding'
                }
        
        # Try exact match fallback
        exact_match = _exact_match_fallback(candidate, schema_terms)
        if exact_match:
            logger.info(f"Exact match fallback: '{candidate}' -> '{exact_match}' ({term_type})")
            return {
                'term': exact_match,
                'canonical_id': exact_match,
                'type': term_type,
                'score': 1.0,
                'method': 'exact'
            }
        
        # Try plural/singular fallback
        plural_match = _plural_fallback(candidate, schema_terms)
        if plural_match:
            logger.info(f"Plural fallback: '{candidate}' -> '{plural_match}' ({term_type})")
            return {
                'term': plural_match,
                'canonical_id': plural_match,
                'type': term_type,
                'score': 0.95,
                'method': 'plural'
            }
        
        # Try fuzzy match fallback
        fuzzy_match = _fuzzy_fallback(candidate, schema_terms, threshold=self.fuzzy_threshold)
        if fuzzy_match:
            logger.info(f"Fuzzy match fallback: '{candidate}' -> '{fuzzy_match}' ({term_type})")
            return {
                'term': fuzzy_match,
                'canonical_id': fuzzy_match,
                'type': term_type,
                'score': 0.80,
                'method': 'fuzzy'
            }
        
        logger.debug(f"No mapping found for '{candidate}' ({term_type})")
        return None
    
    def map_label(self, term: str) -> Optional[Dict[str, Any]]:
        """
        Map a candidate term to a canonical label (node type).
        
        Args:
            term: Candidate label term
            
        Returns:
            Mapping result or None if no suitable match
        """
        result = self._map_with_fallback(term, 'label')
        
        if result:
            # Record mapping to audit log
            try:
                current_span = get_current_span()
                trace_id = f"{current_span.context.trace_id:032x}" if current_span and hasattr(current_span, 'context') and current_span.context.is_valid else "no-trace"
            except:
                trace_id = "no-trace"
            
            audit_store.record({
                "event": "synonym_mapper_label",
                "candidate": term,
                "mapped_term": result['canonical_id'],
                "score": result['score'],
                "method": result['method'],
                "trace_id": trace_id
            })
        
        return result
    
    def map_relationship(self, term: str) -> Optional[Dict[str, Any]]:
        """
        Map a candidate term to a canonical relationship type.
        
        Args:
            term: Candidate relationship term
            
        Returns:
            Mapping result or None if no suitable match
        """
        result = self._map_with_fallback(term, 'relationship')
        
        if result:
            # Record mapping to audit log
            try:
                current_span = get_current_span()
                trace_id = f"{current_span.context.trace_id:032x}" if current_span and hasattr(current_span, 'context') and current_span.context.is_valid else "no-trace"
            except:
                trace_id = "no-trace"
            
            audit_store.record({
                "event": "synonym_mapper_relationship",
                "candidate": term,
                "mapped_term": result['canonical_id'],
                "score": result['score'],
                "method": result['method'],
                "trace_id": trace_id
            })
        
        return result
    
    def map_property(self, term: str) -> Optional[Dict[str, Any]]:
        """
        Map a candidate term to a canonical property name.
        
        Args:
            term: Candidate property term
            
        Returns:
            Mapping result or None if no suitable match
        """
        result = self._map_with_fallback(term, 'property')
        
        if result:
            # Record mapping to audit log
            try:
                current_span = get_current_span()
                trace_id = f"{current_span.context.trace_id:032x}" if current_span and hasattr(current_span, 'context') and current_span.context.is_valid else "no-trace"
            except:
                trace_id = "no-trace"
            
            audit_store.record({
                "event": "synonym_mapper_property",
                "candidate": term,
                "mapped_term": result['canonical_id'],
                "score": result['score'],
                "method": result['method'],
                "trace_id": trace_id
            })
        
        return result


# Legacy functions (kept for backward compatibility)

def map_term(candidate: str, top_k: int = None) -> List[Dict[str, Any]]:
    """
    Map a candidate term to schema terms using semantic similarity.
    
    Args:
        candidate: The term to map
        top_k: Number of top matches to return (defaults to config value)
        
    Returns:
        List of dictionaries with fields: id, term, type, canonical_id, score
    """
    if not candidate or not candidate.strip():
        logger.warning("Empty candidate term provided for mapping")
        return []
    
    try:
        # Get configuration values
        index_name = get_config_value('schema_embeddings.index_name', 'schema_embeddings')
        default_top_k = get_config_value('schema_embeddings.top_k', 5)
        top_k = top_k or default_top_k
        
        logger.debug(f"Mapping candidate '{candidate}' using index '{index_name}' with top_k={top_k}")
        
        # Get embedding for the candidate term
        embedding_provider = get_embedding_provider()
        embeddings = embedding_provider.get_embeddings([candidate])
        
        if not embeddings or not embeddings[0]:
            logger.warning(f"No embedding generated for candidate '{candidate}'")
            return []
        
        embedding = embeddings[0]
        
        # Perform vector similarity search in Neo4j
        neo4j_client = Neo4jClient()
        
        # Cypher query for vector similarity search
        cypher_query = f"""
        CALL db.index.vector.queryNodes('{index_name}', $top_k, $embedding)
        YIELD node, score
        RETURN node.id as id, 
               node.term as term, 
               node.type as type, 
               node.canonical_id as canonical_id, 
               score
        ORDER BY score DESC
        """
        
        params = {
            "top_k": top_k,
            "embedding": embedding
        }
        
        results = neo4j_client.execute_read_query(
            cypher_query, 
            params=params, 
            query_name="semantic_mapping"
        )
        
        # Log mapping results and record metrics
        if results:
            logger.info(f"Found {len(results)} semantic matches for '{candidate}': {[r.get('term', 'unknown') for r in results]}")
            # Log individual scores for observability and record metrics
            for result in results:
                score = result.get('score', 0.0)
                term = result.get('term', 'unknown')
                canonical_id = result.get('canonical_id', 'unknown')
                logger.debug(f"Semantic match: '{candidate}' -> '{term}' (score: {score:.3f})")
                # Record embedding match score metric
                embedding_match_score.observe(score)
            
            # Audit log the best match for traceability
            if results:
                best_match = results[0]
                try:
                    current_span = get_current_span()
                    trace_id = f"{current_span.context.trace_id:032x}" if current_span and hasattr(current_span, 'context') and current_span.context.is_valid else "no-trace"
                except:
                    trace_id = "no-trace"
                
                audit_store.record({
                    "event": "semantic_mapping",
                    "candidate": candidate,
                    "mapped_term": best_match.get('term', 'unknown'),
                    "mapped_canonical_id": best_match.get('canonical_id', 'unknown'),
                    "score": best_match.get('score', 0.0),
                    "total_matches": len(results),
                    "trace_id": trace_id
                })
        else:
            logger.info(f"No semantic matches found for candidate '{candidate}'")
        
        return results
        
    except Exception as e:
        logger.error(f"Error during semantic mapping for candidate '{candidate}': {e}")
        if is_dev_mode():
            logger.warning(f"Semantic mapping failed in DEV_MODE, returning empty result for '{candidate}'")
        return []

def map_terms(terms: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Map multiple candidate terms to schema terms.
    
    Args:
        terms: List of candidate terms to map
        
    Returns:
        Dictionary mapping input terms to their semantic matches
    """
    if not terms:
        logger.warning("Empty terms list provided for mapping")
        return {}
    
    logger.info(f"Mapping {len(terms)} terms: {terms}")
    
    results = {}
    for term in terms:
        if term and term.strip():
            matches = map_term(term)
            results[term] = matches
        else:
            logger.warning(f"Skipping empty term in batch mapping")
            results[term] = []
    
    # Log summary
    total_matches = sum(len(matches) for matches in results.values())
    logger.info(f"Batch mapping complete: {len(terms)} terms mapped, {total_matches} total matches found")
    
    return results

def get_best_match(candidate: str, threshold: float = 0.7) -> Optional[Dict[str, Any]]:
    """
    Get the best semantic match for a candidate term if it meets the threshold.
    
    Args:
        candidate: The term to map
        threshold: Minimum similarity score threshold (default 0.7)
        
    Returns:
        Best match dictionary or None if no match meets threshold
    """
    matches = map_term(candidate, top_k=1)
    
    if not matches:
        return None
    
    best_match = matches[0]
    score = best_match.get('score', 0.0)
    
    if score >= threshold:
        logger.info(f"Best match for '{candidate}': '{best_match.get('term', 'unknown')}' (score: {score:.3f})")
        return best_match
    else:
        logger.debug(f"Best match for '{candidate}' score {score:.3f} below threshold {threshold}")
        return None
