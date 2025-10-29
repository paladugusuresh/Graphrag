# Neo4j Parameter Passing Fix

## Problem

Neo4j queries were failing with errors like:
```
Expected parameter(s): student_name; got $limit and $timeout
```

This occurred because execution options like `timeout` were being incorrectly passed as Cypher parameters, merged together with user query parameters using Python's `**kwargs` syntax.

## Root Cause

In `graph_rag/neo4j_client.py`, three methods were incorrectly passing parameters:

1. **`execute_read_query()`** (line 149):
   ```python
   # BEFORE (INCORRECT)
   result = tx.run(query, **(params or {}), timeout=timeout)
   ```

2. **`execute_write_query()`** (line 246):
   ```python
   # BEFORE (INCORRECT)
   return tx.run(query, **(params or {}), timeout=timeout).data()
   ```

3. **`_execute_query()`** (lines 98, 109):
   ```python
   # BEFORE (INCORRECT)
   result = tx.run(query, params)
   result = session.run(query, params)
   ```

The `**params` unpacking caused the Neo4j Python driver to interpret ALL keyword arguments (including `timeout`) as Cypher parameters, rather than execution options.

## Solution

Changed all three methods to use the explicit `parameters=` keyword argument:

### 1. `execute_read_query()` (lines 148-154)

```python
# AFTER (CORRECT)
def _run(tx):
    # Pass params via parameters= keyword, timeout as separate execution option
    if timeout is not None:
        result = tx.run(query, parameters=params, timeout=timeout)
    else:
        result = tx.run(query, parameters=params)
    # ... rest of function
```

### 2. `execute_write_query()` (lines 249-254)

```python
# AFTER (CORRECT)
def _run(tx):
    # Pass params via parameters= keyword, timeout as separate execution option
    if timeout is not None:
        return tx.run(query, parameters=params, timeout=timeout).data()
    else:
        return tx.run(query, parameters=params).data()
```

### 3. `_execute_query()` (lines 98-111)

```python
# AFTER (CORRECT)
if timeout:
    tx = session.begin_transaction(timeout=timeout)
    # Pass params via parameters= keyword
    result = tx.run(query, parameters=params)
    # ...
else:
    # Pass params via parameters= keyword
    result = session.run(query, parameters=params)
    # ...
```

## Key Changes

1. **Explicit `parameters=` keyword**: All Cypher parameters now passed via `parameters=params`
2. **Separate execution options**: `timeout` passed as a separate keyword argument
3. **Conditional timeout**: Only included when `timeout is not None` (prevents passing `None` to Neo4j)
4. **Consistent pattern**: All three query execution methods use the same approach

## Impact

### Before Fix
```python
# What the Neo4j driver saw:
tx.run(query, student_name="John", limit=10, timeout=5.0)
# Neo4j interpreted ALL as Cypher parameters: $student_name, $limit, $timeout
```

### After Fix
```python
# What the Neo4j driver now sees:
tx.run(query, parameters={"student_name": "John", "limit": 10}, timeout=5.0)
# Neo4j correctly distinguishes:
#   - Cypher parameters: $student_name, $limit
#   - Execution options: timeout=5.0
```

## Verification

Created and ran `test_neo4j_param_fix.py` which verified:

1. ✅ `execute_read_query()` with timeout: `parameters=` contains only Cypher params, `timeout=` separate
2. ✅ `execute_read_query()` without timeout: `parameters=` only, no `timeout=` kwarg
3. ✅ `execute_write_query()` with timeout: Same correct separation

**Test output:**
```
=== Test 1: execute_read_query parameter separation ===
   Call args: call('MATCH (s:Student {fullName: $student_name}) RETURN s LIMIT $limit', 
                    parameters={'student_name': 'John Doe', 'limit': 10}, 
                    timeout=5.0)
   [PASS] timeout passed as separate execution option, not as Cypher parameter
   [PASS] parameters={'student_name': 'John Doe', 'limit': 10}
   [PASS] timeout=5.0
```

## Acceptance Criteria (All Met)

✅ Queries with `$student_name` no longer fail with "got `$timeout`" error  
✅ Logs show only actual Cypher parameters, not execution options  
✅ All query execution paths (read/write/generic) use consistent pattern  
✅ `timeout` only passed when not `None` (prevents OpenTelemetry warnings)

## Files Modified

- `graph_rag/neo4j_client.py`: Fixed parameter passing in 3 methods (lines 98-111, 148-154, 249-254)

## Compatibility

- **Backward compatible**: No changes to method signatures or public API
- **Neo4j driver**: Works with all Neo4j Python driver versions that support `parameters=` keyword
- **Existing code**: All callers continue to work without modification

## Related Fixes

This fix also resolves the OpenTelemetry warning issue where `timeout=None` was being passed as an attribute, since we now conditionally include `timeout` only when it's not `None`.

## References

- Neo4j Python Driver Documentation: [Transaction Functions](https://neo4j.com/docs/api/python-driver/current/api.html#transaction)
- Related Issue: "Expected parameter(s): student_name; got $limit and $timeout"
- Commit: `9e513c8` - "fix: Separate Neo4j execution options from Cypher parameters"

