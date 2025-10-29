MATCH (s:Student {fullName: $student})-[:HAS_PLAN]->(:Plan)-[:HAS_GOAL]->(g:Goal)
RETURN g.goalType AS goal, g.id AS id, g.name as name
LIMIT $limit