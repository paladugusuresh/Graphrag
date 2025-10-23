MATCH (s:Student {fullName: $student})-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal)
RETURN coalesce(g.title, g.name, g.goalTitle, g.goalType) AS goal,
       coalesce(g.status, g.id) AS id
LIMIT $limit

