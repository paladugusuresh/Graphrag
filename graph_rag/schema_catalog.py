# graph_rag/schema_catalog.py
import json
from graph_rag.neo4j_client import Neo4jClient
from graph_rag.observability import get_logger
from graph_rag.config_manager import get_config_value
from graph_rag.dev_stubs import get_neo4j_client_or_mock

logger = get_logger(__name__)

def generate_schema_allow_list(output_path: str = None):
    """Generate schema allow-list from Neo4j database or create stub if unavailable"""
    output_path = output_path or get_config_value("schema.allow_list_path", "allow_list.json")

    try:
        client = Neo4jClient()
        labels = [r['label'] for r in client.execute_read_query("CALL db.labels() YIELD label RETURN label")]
        rels = [r['relationshipType'] for r in client.execute_read_query("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")]
        schema_result = client.execute_read_query("CALL db.schema.visualization()")
        nodes = schema_result[0].get('nodes', []) if schema_result else []
        properties = {}
        for node in nodes:
            name = node.get('name')
            prop_rows = client.execute_read_query(f"MATCH (n:`{name}`) UNWIND keys(n) AS key RETURN DISTINCT key")
            properties[name] = [p['key'] for p in prop_rows]
        allow = {"node_labels": labels, "relationship_types": rels, "properties": properties}
        with open(output_path, 'w') as fh:
            json.dump(allow, fh, indent=2)
        logger.info(f"Allow-list written to {output_path}")
        return allow
    except Exception as e:
        logger.warning(f"Failed to generate schema allow-list from Neo4j: {e}. Creating a stub allow_list.json.")
        # Create a conservative allow_list.json stub
        stub_allow_list = {
            "node_labels": ["Document","Chunk","Entity","__Entity__","Person","Organization","Product"],
            "relationship_types": ["PART_OF","HAS_CHUNK","MENTIONS","FOUNDED","HAS_PRODUCT"],
            "properties": {}
        }
        with open(output_path, 'w') as fh:
            json.dump(stub_allow_list, fh, indent=2)
        logger.info(f"Stub allow-list written to {output_path}")
        return stub_allow_list
