import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from prometheus_client import REGISTRY

class TestObservability(unittest.TestCase):
    def setUp(self):
        # Clear the module cache to ensure a fresh import for each test
        if 'graph_rag.observability' in sys.modules:
            del sys.modules['graph_rag.observability']
        # Clear Prometheus registry to prevent duplicated timeseries errors
        if hasattr(REGISTRY, '_names_to_collectors'):
            REGISTRY._names_to_collectors.clear()

    @patch.dict(os.environ, {"PROMETHEUS_PORT": "0"}, clear=True)
    @patch("graph_rag.observability.start_http_server")
    def test_observability_import_and_metrics_server(self, mock_start_http_server):
        import graph_rag.observability
        self.assertIsNotNone(graph_rag.observability.tracer)
        self.assertIsNotNone(graph_rag.observability.db_query_total)
        self.assertIsNotNone(graph_rag.observability.get_logger(__name__))
        
        graph_rag.observability.start_metrics_server()
        mock_start_http_server.assert_called_once_with(0)

    @patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"}, clear=True)
    @patch("opentelemetry.sdk.trace.TracerProvider")
    @patch("opentelemetry.trace.set_tracer_provider")
    @patch("opentelemetry.sdk.trace.export.BatchSpanProcessor")
    @patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter")
    def test_otel_exporter_otlp_endpoint(self, mock_otlp_span_exporter_class, mock_batch_span_processor_class, mock_set_tracer_provider, mock_tracer_provider_class):
        import graph_rag.observability
        
        mock_tracer_provider_class.assert_called_once()
        mock_provider_instance = mock_tracer_provider_class.return_value
        mock_provider_instance.add_span_processor.assert_called_once()
        
        mock_batch_span_processor_class.assert_called_once()
        
        mock_otlp_span_exporter_class.assert_called_once_with(endpoint="http://localhost:4317")
        span_exporter_instance = mock_otlp_span_exporter_class.return_value

        (call_args, _) = mock_batch_span_processor_class.call_args
        span_exporter_passed_to_processor = call_args[0]
        
        self.assertEqual(span_exporter_passed_to_processor, span_exporter_instance)

    @patch.dict(os.environ, {}, clear=True)
    @patch("opentelemetry.sdk.trace.TracerProvider")
    @patch("opentelemetry.trace.set_tracer_provider")
    @patch("opentelemetry.sdk.trace.export.BatchSpanProcessor")
    @patch("opentelemetry.sdk.trace.export.ConsoleSpanExporter")
    def test_otel_exporter_console_fallback(self, mock_console_span_exporter_class, mock_batch_span_processor_class, mock_set_tracer_provider, mock_tracer_provider_class):
        import graph_rag.observability
        
        mock_tracer_provider_class.assert_called_once()
        mock_provider_instance = mock_tracer_provider_class.return_value
        mock_provider_instance.add_span_processor.assert_called_once()

        mock_batch_span_processor_class.assert_called_once()
        
        mock_console_span_exporter_class.assert_called_once()
        span_exporter_instance = mock_console_span_exporter_class.return_value

        (call_args, _) = mock_batch_span_processor_class.call_args
        span_exporter_passed_to_processor = call_args[0]
        
        self.assertEqual(span_exporter_passed_to_processor, span_exporter_instance)
