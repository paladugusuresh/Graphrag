// Goals for a student, with context (plans, concerns, interventions, manager, progress signal)
MATCH (s:Student)
WHERE toLower(s.fullName) = toLower($student_name)

MATCH (s)-[:HAS_PLAN]->(p:Plan)-[:HAS_GOAL]->(g:Goal)

OPTIONAL MATCH (ip:InterventionPlan)-[:HAS_GOAL]->(g)
OPTIONAL MATCH (ca:ConcernArea)-[:TARGETS_GOAL]->(g)
OPTIONAL MATCH (pn:ProgressNote)-[:LINKED_GOAL]->(g)    
OPTIONAL MATCH (s)-[:HAS_CASE_MANAGER]->(cm:Staff)

WITH g, p, ip, ca, pn, cm
WITH
  g,
  collect(DISTINCT p.planType)          AS planTypes,
  collect(DISTINCT ip.interventionName) AS interventionNames,
  collect(DISTINCT ca.name)             AS concernAreas,
  head(collect(DISTINCT cm.fullName))   AS caseManager,
  count(pn)                             AS progressNoteCount,
  max(coalesce(pn.date, pn.noteDate))   AS latestProgressNoteDate

RETURN DISTINCT
  g.id              AS id,
  g.goalType        AS goalType,
  g.description     AS description,
  g.status          AS status,
  g.startDate       AS startDate,
  g.endDate         AS endDate,
  g.measurementTool AS measurementTool,
  g.progressStatus  AS progressStatus,
  planTypes,
  interventionNames,
  concernAreas,
  caseManager,
  progressNoteCount,
  latestProgressNoteDate
LIMIT $limit
