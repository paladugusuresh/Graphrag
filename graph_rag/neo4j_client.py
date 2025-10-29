# graph_rag/neo4j_client.py
import os
from time import perf_counter
from typing import Optional, Dict, Any
from neo4j import GraphDatabase, exceptions
from dotenv import load_dotenv
from graph_rag.observability import get_logger, tracer, db_query_total, db_query_failed, db_query_latency, inflight_queries
from graph_rag.config_manager import get_config, subscribe_to_config_reload
from graph_rag.audit_store import AuditStore

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
        self._audit_store = AuditStore()
        
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
                        # Pass params via parameters= keyword
                        result = tx.run(query, parameters=params)
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
                        # Pass params via parameters= keyword
                        result = session.run(query, parameters=params)
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
        """Execute a read query using Neo4j's read transaction API"""
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
        
        def _run(tx):
            # Pass params via parameters= keyword, timeout as separate execution option
            if timeout is not None:
                result = tx.run(query, parameters=params, timeout=timeout)
            else:
                result = tx.run(query, parameters=params)
            records = result.data()
            
            # Capture and log Neo4j notifications
            if hasattr(result, 'consume'):
                summary = result.consume()
                if hasattr(summary, 'notifications') and summary.notifications:
                    self._log_neo4j_notifications(summary.notifications, query, query_name)
            
            return records
        
        with self._driver.session() as session:
            return session.execute_read(_run)  # true READ transaction
    
    def _log_neo4j_notifications(self, notifications, query: str, query_name: str):
        """Log Neo4j notifications with actionable hints"""
        for notification in notifications:
            severity = getattr(notification, 'severity', 'UNKNOWN')
            code = getattr(notification, 'code', 'UNKNOWN')
            title = getattr(notification, 'title', 'Unknown notification')
            description = getattr(notification, 'description', '')
            
            # Build actionable hints based on notification code
            hints = []
            if 'UnknownProperty' in code or 'property' in description.lower():
                # Extract property name from description if possible
                import re
                prop_match = re.search(r"property[:\s]+['\"]?(\w+)['\"]?", description, re.IGNORECASE)
                if prop_match:
                    prop_name = prop_match.group(1)
                    hints.append(f"Property '{prop_name}' not found. Check allow-list and schema.")
                else:
                    hints.append("Property not found. Check allow-list and schema.")
            elif 'UnknownLabel' in code or 'label' in description.lower():
                hints.append("Label not found. Check allow-list and schema.")
            elif 'UnknownRelationship' in code or 'relationship' in description.lower():
                hints.append("Relationship type not found. Check allow-list and schema.")
            elif 'Cartesian' in code:
                hints.append("Cartesian product detected. Consider adding relationship patterns or WHERE clauses.")
            elif 'EagerOperator' in code:
                hints.append("Query requires eager loading. Consider optimizing query pattern.")
            
            # Log notification with hints
            log_level = 'warning' if severity in ['WARNING', 'INFORMATION'] else 'error'
            log_message = f"Neo4j notification [{severity}] {code}: {title}"
            if hints:
                log_message += f" - Hint: {'; '.join(hints)}"
            
            if log_level == 'warning':
                logger.warning(log_message)
            else:
                logger.error(log_message)
            
            # Record in audit store
            self._audit_store.record({
                "event": "neo4j_notification",
                "query_name": query_name,
                "query_preview": query[:200],
                "severity": severity,
                "code": code,
                "title": title,
                "description": description,
                "hints": hints
            })

    def execute_write_query(self, query: str, params: dict | None = None, timeout: float | None = None, query_name: str | None = None):
        """Execute a write query using Neo4j's write transaction API"""
        params = params or {}
        query_name = query_name or "generic_query"
        
        # Write-protection guard: disallow writes unless admin mode or explicit env var
        if os.getenv("APP_MODE", "read_only").lower() != "admin" and os.getenv("ALLOW_WRITES","false").lower() not in ("1","true","yes"):
            error_msg = "Write queries disabled in application run mode. Set APP_MODE=admin or ALLOW_WRITES=true to permit writes."
            logger.error(f"Write query blocked: {error_msg}")
            
            # Record the violation in audit store
            self._audit_store.record({
                "event": "write_query_blocked",
                "query_name": query_name or "unknown",
                "query_preview": query[:100] + "..." if len(query) > 100 else query,
                "reason": "write_protection_guard",
                "app_mode": os.getenv("APP_MODE", "read_only"),
                "allow_writes": os.getenv("ALLOW_WRITES", "false")
            })
            
            raise RuntimeError(error_msg)
        
        # Check if driver is available
        if not self._driver:
            dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
            if dev_mode:
                logger.warning(f"Neo4j driver not available in DEV_MODE, returning empty result for query: {query_name}")
                return []
            else:
                raise RuntimeError("Neo4j driver not initialized")
        
        def _run(tx):
            # Pass params via parameters= keyword, timeout as separate execution option
            if timeout is not None:
                return tx.run(query, parameters=params, timeout=timeout).data()
            else:
                return tx.run(query, parameters=params).data()
        
        with self._driver.session() as session:
            return session.execute_write(_run)  # true WRITE transaction
