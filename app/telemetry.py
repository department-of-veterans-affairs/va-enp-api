"""Telemetry configuration for the application using OpenTelemetry."""

import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.resource.detector.containerid import ContainerResourceDetector
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.logging.logging_config import logger


def configure_telemetry(service_name: str = 'va-enp-api') -> tuple[TracerProvider, MeterProvider] | None:
    """Configure OpenTelemetry tracing and metrics for the application.

    Args:
        service_name: The name of the service to be used in telemetry data.

    Returns:
        A tuple of (TracerProvider, MeterProvider) if configured, or None if no endpoint is set.
    """
    endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')

    if not endpoint:
        logger.warning('OTEL_EXPORTER_OTLP_ENDPOINT not set.')
        logger.warning('OpenTelemetry will not be configured. Set OTEL_EXPORTER_OTLP_ENDPOINT to enable telemetry.')
        return None

    logger.info(f'Configuring OpenTelemetry with OTLP endpoint: {endpoint}')

    # Detect container resource attributes (container ID, image, etc.)
    docker_resource = ContainerResourceDetector().detect()
    resource = Resource.create({'service.name': service_name}).merge(docker_resource)

    # Configure tracing
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(tracer_provider)

    # Configure metrics
    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint, insecure=True))
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    logger.info('OpenTelemetry configured successfully.')
    return tracer_provider, meter_provider
