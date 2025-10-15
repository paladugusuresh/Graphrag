# graph_rag/neo4j_client.py
import os
from time import perf_counter
from typing import Optional, Dict, Any
from neo4j import GraphDatabase, exceptions
from dotenv import load_dotenv
from graph_rag.observability import get_logger, tracer, db_query_total, db_query_failed, db_query_latency, inflight_queries
from graph_rag.config_manager import get_config, subscribe_to_config_reload

logger = get_logger(__name__)

# Load environment variables once at import
load_dotenv()

def _get_neo4j_credentials() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Get Neo4j credentials from environment, returning None if missing"""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    
    dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
    
    if not all([uri, user, password]) and not dev_mode:
        logger.error("Missing Neo4j credentials in env")
    
    return uri, user, password

class Neo4jClient:
    def __init__(self, driver=None):
        """Initialize Neo4j client with optional driver injection for testing"""
        self._driver = driver
        self._config = None
        
        # If no driver provided, create one lazily
        if not driver:
            uri, user, password = _get_neo4j_credentials()
            if uri and user and password:
                self._driver = GraphDatabase.driver(uri, auth=(user, password))
                try:
                    self._driver.verify_connectivity()
                    logger.info("Connected to Neo4j")
                except Exception as e:
                    dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
                    if dev_mode:
                        logger.warning(f"Neo4j connectivity failed in DEV_MODE: {e}")
                    else:
                        logger.error(f"Neo4j connectivity failed: {e}")
                        raise
            else:
                dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
                if not dev_mode:
                    raise ValueError("Neo4j credentials not provided and not in DEV_MODE")
                logger.info("Neo4j client initialized in DEV_MODE without credentials")
        
        # Subscribe to config reloads
        subscribe_to_config_reload(self._on_config_reload)
    
    def _on_config_reload(self, new_config: Dict[str, Any]):
        """Handle config reload notification"""
        self._config = new_config
        logger.info("Neo4jClient received config reload notification")

    def close(self):
        """Close the Neo4j driver connection"""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j driver closed")

    def _execute_query(self, query: str, params: dict | None = None, access_mode=None, timeout: float | None = None, query_name: str | None = None):
        """Execute a query against Neo4j with observability"""
        params = params or {}
        query_name = query_name or "generic_query"
        
        # Check if driver is available
        if not self._driver:
            dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
            if dev_mode:
                logger.warning(f"Neo4j driver not available in DEV_MODE, returning empty result for query: {query_name}")
                return []
            else:
                raise RuntimeError("Neo4j driver not initialized")
        
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
