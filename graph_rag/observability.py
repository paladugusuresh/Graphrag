# graph_rag/observability.py
import os
import logging
import structlog
from prometheus_client import start_http_server, Counter, Histogram, Gauge
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# OpenTelemetry Tracer
resource = Resource.create({
    "service.name": os.getenv("OTEL_SERVICE_NAME", "graphrag-application"),
    "service.version": os.getenv("OTEL_SERVICE_VERSION", "0.1.0"),
})

provider = TracerProvider(resource=resource)

otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
if otlp_endpoint:
    span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
else:
    span_exporter = ConsoleSpanExporter()

provider.add_span_processor(BatchSpanProcessor(span_exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# Prometheus Metrics
db_query_total = Counter("db_query_total", "Total number of database queries.", ["status"])
db_query_failed = Counter("db_query_failed", "Number of failed database queries.")
db_query_latency = Histogram("db_query_latency_seconds", "Latency of database queries.", buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')))
inflight_queries = Gauge("inflight_queries", "Number of currently inflight database queries.")
llm_calls_total = Counter("llm_calls_total", "Total number of LLM calls.")
embedding_match_score = Histogram("embedding_match_score", "Schema embedding similarity scores", buckets=(0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0))
cypher_validation_failures = Counter("cypher_validation_failures", "Cypher validation failures")

# Domain-specific Pipeline Metrics
planner_latency_seconds = Histogram(
    "planner_latency_seconds", 
    "Latency of query planning operations", 
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, float('inf'))
)

mapping_similarity = Histogram(
    "mapping_similarity", 
    "Semantic mapping similarity scores", 
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)

executor_latency_seconds = Histogram(
    "executor_latency_seconds", 
    "Latency of query execution operations", 
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, float('inf'))
)

augmentation_size = Histogram(
    "augmentation_size", 
    "Number of augmented results/neighbors", 
    buckets=(0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, float('inf'))
)

# Event Counters
guardrail_blocks_total = Counter(
    "guardrail_blocks_total", 
    "Total number of guardrail blocks", 
    ["reason"]
)

llm_rate_limited_total = Counter(
    "llm_rate_limited_total", 
    "Total number of LLM rate limit hits"
)

def start_metrics_server():
    port = int(os.getenv("PROMETHEUS_PORT", 8000))
    start_http_server(port)
    logging.info(f"Prometheus metrics server started on port {port}")

# Pipeline Span Helpers
def create_pipeline_span(operation_name: str, **attributes):
    """
    Create a pipeline span with standard attributes.
    
    Args:
        operation_name: Name of the pipeline operation
        **attributes: Additional span attributes
        
    Returns:
        OpenTelemetry span context manager
    """
    return tracer.start_as_current_span(operation_name, attributes=attributes)

def add_span_attributes(span, **attributes):
    """
    Add attributes to an existing span.
    
    Args:
        span: OpenTelemetry span
        **attributes: Attributes to add
    """
    for key, value in attributes.items():
        span.set_attribute(key, value)

# Structured Logger

def get_logger(name: str):
    structlog.configure(
        processors=[
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger(name)
