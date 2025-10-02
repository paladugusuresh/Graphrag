# graph_rag/neo4j_client.py
import os
import yaml
from time import perf_counter
from neo4j import GraphDatabase, exceptions
from dotenv import load_dotenv
from graph_rag.observability import get_logger, tracer, db_query_total, db_query_failed, db_query_latency, inflight_queries

logger = get_logger(__name__)

with open("config.yaml", 'r') as f:
    CONFIG = yaml.safe_load(f)

load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
    logger.error("Missing Neo4j credentials in env")

class Neo4jClient:
    def __init__(self, driver=None):
        if driver:
            self._driver = driver
        else:
            self._driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        try:
            self._driver.verify_connectivity()
            logger.info("Connected to Neo4j")
        except Exception as e:
            logger.error(f"Neo4j connectivity failed: {e}")
            raise

    def close(self):
        self._driver.close()
        logger.info("Neo4j driver closed")

    def _execute_query(self, query: str, params: dict | None = None, access_mode=None, timeout: float | None = None, query_name: str | None = None):
        params = params or {}
        query_name = query_name or "generic_query"
        
        with tracer.start_as_current_span("neo4j.query") as span:
            span.set_attribute("db.system", "neo4j")
            span.set_attribute("db.statement", query)
            if query_name:
                span.set_attribute("db.statement.summary", query_name)
            
            inflight_queries.inc()
            start = perf_counter()
            status = "failure"
            try:
                with self._driver.session(default_access_mode=access_mode) as session:
                    if timeout:
                        tx = session.begin_transaction(timeout=timeout)
                        result = tx.run(query, params)
                        records = [r.data() for r in result]
                        try:
                            tx.commit()
                            status = "success"
                        except exceptions.ClientError as e:
                            logger.warning(f"Transaction commit failed for query '{query_name}': {e}")
                            status = "failure"
                        except Exception:
                            status = "failure"
                    else:
                        result = session.run(query, params)
                        records = [r.data() for r in result]
                        status = "success"
                duration = perf_counter() - start
                db_query_latency.observe(duration)
                db_query_total.labels(status=status).inc()
                return records
            except exceptions.CypherSyntaxError as e:
                db_query_total.labels(status="failure").inc()
                db_query_failed.inc()
                logger.error(f"Cypher syntax error for query '{query_name}': {e}")
                return []
            except exceptions.ClientError as e:
                db_query_total.labels(status="failure").inc()
                db_query_failed.inc()
                logger.error(f"Neo4j client error for query '{query_name}': {e}")
                return []
            except Exception as e:
                db_query_total.labels(status="failure").inc()
                db_query_failed.inc()
                logger.error(f"Unexpected DB error for query '{query_name}': {e}")
                return []
            finally:
                inflight_queries.dec()

    def execute_read_query(self, query: str, params: dict | None = None, timeout: float | None = None, query_name: str | None = None):
        return self._execute_query(query, params=params, access_mode="READ", timeout=timeout, query_name=query_name)

    def execute_write_query(self, query: str, params: dict | None = None, timeout: float | None = None, query_name: str | None = None):
        # write only used by ingestion/admin flows
        return self._execute_query(query, params=params, access_mode="WRITE", timeout=timeout, query_name=query_name)
