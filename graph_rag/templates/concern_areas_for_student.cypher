// Concern areas for a student, with related goals and interventions
MATCH (s:Student)
WHERE toLower(s.fullName) = toLower($student_name)
MATCH (s)-[:HAS_CONCERN]->(c:ConcernArea)

// Optional links to goals and interventions
OPTIONAL MATCH (c)-[:TARGETS_GOAL]->(g:Goal)
OPTIONAL MATCH (g)<-[:HAS_GOAL]-(p:Plan)
OPTIONAL MATCH (ip:InterventionPlan)-[:HAS_GOAL]->(g)

WITH c, g, p, ip
RETURN DISTINCT
  c.name                         AS concernArea,
  g.goalType                     AS goalType,
  g.description                  AS goalDescription,
  g.status                       AS goalStatus,
  collect(DISTINCT p.planType)   AS relatedPlans,
  collect(DISTINCT ip.interventionName) AS relatedInterventions
ORDER BY concernArea
LIMIT $limit
