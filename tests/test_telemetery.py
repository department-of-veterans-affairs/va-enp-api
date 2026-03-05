"""Tests for telemetry configuration in app.telemetry."""

import os
from unittest.mock import patch

from opentelemetry import metrics, trace

from app.telemetry import configure_telemetry


def test_configure_telemetry_no_endpoint_does_not_set_providers() -> None:
    """Should return early when OTEL_EXPORTER_OTLP_ENDPOINT is not set."""
    with patch.dict(os.environ, {'OTEL_EXPORTER_OTLP_ENDPOINT': ''}, clear=True):
        configure_telemetry()
        # If the endpoint is not set, then provider is ProxyTracerProvider, which is the default no-op provider
        assert trace.get_tracer_provider().__class__.__name__ == 'ProxyTracerProvider'


def test_configure_telemetry_configures_providers_when_endpoint_set() -> None:
    """Should configure trace and meter providers when endpoint is set."""
    with patch.dict(os.environ, {'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://localhost:4317'}):
        configure_telemetry()
        # If the endpoint is set, then provider is TracerProvider, which means it was configured successfully
        assert trace.get_tracer_provider().__class__.__name__ == 'TracerProvider'
        assert metrics.get_meter_provider().__class__.__name__ == 'MeterProvider'
