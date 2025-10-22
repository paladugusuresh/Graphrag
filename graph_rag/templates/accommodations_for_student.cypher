MATCH (s:Student {fullName: $student})-[:USES_ACCOMMODATION]->(a:Accommodation)
RETURN a.name AS accommodation
ORDER BY accommodation
LIMIT $limit
