"""Telemetry configuration for the application using OpenTelemetry."""

import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.resourcedetector.docker import DockerResourceDetector
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_telemetry(service_name: str = 'va-enp-api') -> None:
    """Configure OpenTelemetry tracing and metrics for the application.

    Args:
        service_name: The name of the service to be used in telemetry data.
    """
    # Pull endpoint from env, fall back to OTel default
    endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')

    # Detect container resource attributes (container ID, image, etc.)
    docker_resource = DockerResourceDetector().detect()
    resource = Resource.create({'service.name': service_name}).merge(docker_resource)

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint, insecure=True))
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
