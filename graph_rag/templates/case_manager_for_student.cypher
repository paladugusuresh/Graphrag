MATCH (s:Student {fullName: $student})-[:HAS_CASE_MANAGER]->(st:Staff)
RETURN st.fullName AS caseManager, coalesce(st.role,'') AS role
LIMIT 1
