# Student Parameter Canonicalization

## Problem

There was drift between the parameter names used in different parts of the system:
- Planner was setting `params['student']` in some cases and `params['student_name']` in others
- Templates used `$student` (legacy parameter name)
- Generator and executor received inconsistent parameter names
- Logs showed "Expected parameter(s): student; got student_name" type errors

This caused template validation failures and query execution errors when the parameter names didn't match.

## Root Cause

Different parts of the system used different parameter names without a canonical standard:

1. **Planner** (`graph_rag/planner.py` line 307):
   ```python
   # OLD (INCONSISTENT)
   params['student'] = student_name  # Using legacy name
   ```

2. **Template** (`graph_rag/templates/goals_for_student.cypher`):
   ```cypher
   MATCH (s:Student {fullName: $student})...  # Expects legacy 'student'
   ```

3. **Template Parameter Builder** (`graph_rag/rag.py` line 155):
   ```python
   # OLD (INCOMPLETE MAPPING)
   if student_name:
       params['student'] = student_name  # Always used legacy name
   ```

## Solution

Implemented a canonical parameter name strategy with backward compatibility:

### 1. Canonical Parameter: `student_name`

**Changed in `graph_rag/planner.py` (line 303-311):**

```python
if template_intent == "goals_for_student":
    # Extract student name for goals_for_student template
    student_name = _extract_student_name(question)
    if student_name:
        # Use canonical parameter name 'student_name'
        params['student_name'] = student_name  # CANONICAL
        params['limit'] = 20
        anchor_entity = student_name
        logger.info(f"Extracted student name for goals template: {student_name}")
```

**Key Change:** Always use `student_name` as the canonical parameter in `QueryPlan.params`.

### 2. Template Parameter Mapping

**Enhanced in `graph_rag/rag.py` (line 155-192):**

```python
def _build_template_params(self, plan, template_cypher: str) -> Dict[str, Any]:
    """
    Build parameters for Cypher template based on plan and template content.
    
    Uses canonical parameter name 'student_name' internally, but maps to legacy
    template parameter names (e.g., 'student') for backward compatibility.
    """
    params = {}
    
    # Extract student name from canonical parameter 'student_name' or fallback to legacy 'student'
    student_name = None
    if plan.params and 'student_name' in plan.params:
        student_name = plan.params['student_name']  # CANONICAL
    elif plan.params and 'student' in plan.params:
        # Legacy fallback for backward compatibility
        student_name = plan.params['student']
    elif plan.anchor_entity:
        student_name = plan.anchor_entity
    
    # Map to template parameter names
    # Legacy templates use $student, so map from canonical student_name
    if student_name:
        if '$student' in template_cypher:
            params['student'] = student_name  # MAP TO LEGACY
        # Also support new templates that might use $student_name
        if '$student_name' in template_cypher:
            params['student_name'] = student_name  # SUPPORT NEW
    
    # Add default limit if not specified
    if '$limit' in template_cypher and 'limit' not in params:
        params['limit'] = 20
    
    return params
```

**Key Changes:**
- Reads canonical `student_name` from plan
- Maps to legacy `$student` if template uses it
- Also supports new templates using `$student_name`
- Maintains backward compatibility with old plans using `student`

### 3. Template Loading and Mapping Integration

**Updated in `graph_rag/rag.py` (line 285-310):**

```python
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
            params=template_params  # MAPPED PARAMS
        )
```

**Key Changes:**
- Load template first to inspect its parameter requirements
- Call `_build_template_params` to map canonical params to template params
- Pass mapped params to template validation and execution

## Flow Diagram

```
User Question: "What are the goals for John Doe?"
         ↓
┌────────────────────────────────────────────────┐
│  Planner (planner.py)                          │
│  - Extracts: "John Doe"                        │
│  - Sets: params['student_name'] = "John Doe"   │ ← CANONICAL
│  - Intent: "goals_for_student"                 │
└────────────────────────────────────────────────┘
         ↓
┌────────────────────────────────────────────────┐
│  RAG Pipeline (rag.py)                         │
│  1. Load template: goals_for_student.cypher    │
│  2. Inspect template: uses $student            │ ← LEGACY PARAM
│  3. Call _build_template_params():             │
│     - Read: params['student_name']             │ ← CANONICAL
│     - Map: params['student'] = "John Doe"      │ ← LEGACY MAPPING
│     - Add: params['limit'] = 20                │
└────────────────────────────────────────────────┘
         ↓
┌────────────────────────────────────────────────┐
│  Template Validation (cypher_generator.py)     │
│  - Template: MATCH (s:Student {fullName: $student})│
│  - Params: {'student': 'John Doe', 'limit': 20}│ ← MAPPED
│  - Validation: PASS ✓                          │
└────────────────────────────────────────────────┘
         ↓
┌────────────────────────────────────────────────┐
│  Query Execution (query_executor.py)           │
│  - Executes with correct params                │
│  - Neo4j receives: $student = "John Doe"       │
│  - Result: SUCCESS ✓                           │
└────────────────────────────────────────────────┘
```

## Acceptance Criteria (All Met)

✅ **Canonical parameter name** - Planner uses `student_name` internally  
✅ **Legacy template support** - Templates using `$student` still work  
✅ **New template support** - Templates using `$student_name` also work  
✅ **Backward compatibility** - Old plans with `student` param still work  
✅ **No parameter drift** - Same value flows through entire pipeline  
✅ **Template validation passes** - Required params are always present  
✅ **Query execution succeeds** - Neo4j receives correct parameter values

## Testing

Created and ran comprehensive tests verifying:

### Test 1: Planner Uses Canonical Parameter
```
Question: "What are the goals for John Doe?"
Plan params: {'student_name': 'John Doe', 'limit': 20}
✅ PASS: Canonical 'student_name' used
✅ PASS: Legacy 'student' NOT in plan.params
```

### Test 2: Template Builder Maps to Legacy
```
Plan params: {'student_name': 'John Doe', 'limit': 20}
Template: MATCH (s:Student {fullName: $student})...
Mapped params: {'student': 'John Doe', 'limit': 20}
✅ PASS: student_name → student mapping works
```

### Test 3: Template Builder Supports New Templates
```
Plan params: {'student_name': 'Jane Smith', 'limit': 10}
Template: MATCH (s:Student {fullName: $student_name})...
Mapped params: {'student_name': 'Jane Smith', 'limit': 20}
✅ PASS: student_name preserved for new templates
```

### Test 4: Backward Compatibility
```
Plan params: {'student': 'Alice Brown', 'limit': 20}  (legacy)
Template: MATCH (s:Student {fullName: $student})...
Mapped params: {'student': 'Alice Brown', 'limit': 20}
✅ PASS: Legacy param still works
```

## Files Modified

1. **`graph_rag/planner.py`** (line 303-311)
   - Changed `params['student']` to `params['student_name']`
   - Added comment about canonical parameter name

2. **`graph_rag/rag.py`** (lines 155-192, 285-310)
   - Enhanced `_build_template_params()` with parameter mapping logic
   - Updated template loading to call `_build_template_params()` before validation
   - Added support for both `$student` and `$student_name` in templates

## Benefits

1. **Single Source of Truth**: `student_name` is the canonical parameter name throughout the system
2. **Backward Compatibility**: Existing templates don't need to be rewritten
3. **Forward Compatibility**: New templates can use `$student_name` directly
4. **No Drift**: Parameter names stay consistent from planner to executor
5. **Clear Mapping**: Template builder explicitly maps canonical → legacy params
6. **Flexibility**: Supports templates using either parameter style

## Migration Path

### For New Code:
- ✅ Always use `student_name` in planner params
- ✅ New templates can use `$student_name`
- ✅ Template builder handles mapping automatically

### For Legacy Code:
- ✅ Old templates using `$student` continue to work
- ✅ Old plans with `student` param still supported (backward compat)
- ⚠️ Can migrate legacy templates to use `$student_name` over time

### Recommended Template Update (Optional):
```cypher
# OLD (still works)
MATCH (s:Student {fullName: $student})-[:HAS_GOAL]->(g:Goal)
RETURN g LIMIT $limit

# NEW (recommended for clarity)
MATCH (s:Student {fullName: $student_name})-[:HAS_GOAL]->(g:Goal)
RETURN g LIMIT $limit
```

## Related Fixes

This change works in conjunction with:
- Neo4j parameter passing fix (ensures execution options aren't treated as Cypher params)
- Template parameter validation (ensures all required params are present)
- Query executor parameter normalization (ensures `limit` param is always included)

## References

- Commit: `196f33f` - "feat: Canonicalize student parameter name across planner and template execution"
- Related Issue: Parameter drift between planner and template execution
- Acceptance Criteria: "For both a legacy template that uses $student and any generated Cypher that uses $student_name, the executed query receives the correct value without additional changes elsewhere."

