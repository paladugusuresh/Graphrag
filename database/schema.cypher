CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

CREATE FULLTEXT INDEX entity_name_index IF NOT EXISTS FOR (e:__Entity__) ON EACH [e.id];

MERGE (:Predicate {id: 'PART_OF', name: 'PART_OF', inverse: 'HAS_PART', symmetric: false, transitive: true});
MERGE (:Predicate {id: 'HAS_CHUNK', name: 'HAS_CHUNK', inverse: 'CHUNK_OF', symmetric: false});
MERGE (:Predicate {id: 'MENTIONS', name: 'MENTIONS', inverse: 'MENTIONED_BY', symmetric: false});

RETURN "Schema setup complete. Constraints and indices are ready." AS status;
