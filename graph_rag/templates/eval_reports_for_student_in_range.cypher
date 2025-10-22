MATCH (s:Student {fullName: $student})<-[:FOR_STUDENT]-(r:EvaluationReport)
WHERE r.dateTime >= $from AND r.dateTime < $to
RETURN r.title AS report, r.dateTime AS date
ORDER BY date DESC
LIMIT $limit
