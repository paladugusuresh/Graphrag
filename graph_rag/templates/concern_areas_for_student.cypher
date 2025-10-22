MATCH (s:Student {fullName: $student})-[:HAS_CONCERN]->(c:ConcernArea)
RETURN c.name AS concernArea
ORDER BY concernArea
LIMIT $limit
