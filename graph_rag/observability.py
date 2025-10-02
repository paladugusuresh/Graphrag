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

def start_metrics_server():
    port = int(os.getenv("PROMETHEUS_PORT", 8000))
    start_http_server(port)
    logging.info(f"Prometheus metrics server started on port {port}")

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
