MATCH (s:Student {fullName: $student})
      -[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal)
RETURN g.title AS goal, coalesce(g.status,'') AS status
ORDER BY g.title
LIMIT $limit
