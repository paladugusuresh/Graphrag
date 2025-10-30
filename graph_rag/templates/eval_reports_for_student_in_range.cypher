// Evaluation reports (and evaluators) for a student in date range
MATCH (s:Student)
WHERE toLower(s.fullName) = toLower($student_name)
MATCH (r:EvaluationReport)-[:FOR_STUDENT]->(s)
WHERE r.date >= $from AND r.date < $to

// Optional: who evaluated the student and other context
OPTIONAL MATCH (r)-[:HAS_EVALUATOR]->(st:Staff)
OPTIONAL MATCH (r)-[:HAS_ASSESSMENT]->(ti:TestInstrument)
OPTIONAL MATCH (r)-[:HAS_GOAL]->(g:Goal)

WITH r, st, ti, g
RETURN DISTINCT
  r.reportId        AS reportId,
  r.evaluationType  AS evaluationType,
  r.date            AS date,
  r.fileName        AS fileName,
  collect(DISTINCT st.fullName)       AS evaluators,
  collect(DISTINCT st.role)           AS evaluatorRoles,
  collect(DISTINCT ti.instrumentName) AS instruments,
  collect(DISTINCT g.description)     AS relatedGoals,
  r.findings        AS findings
ORDER BY date DESC
LIMIT $limit
