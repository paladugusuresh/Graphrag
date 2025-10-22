MATCH (s:Student {fullName: $student})
      -[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal)
RETURN coalesce(g.title, g.name, g.goalTitle, '') AS goal,
       coalesce(g.status, '') AS status
ORDER BY coalesce(g.title, g.name, g.goalTitle, '')
LIMIT $limit
