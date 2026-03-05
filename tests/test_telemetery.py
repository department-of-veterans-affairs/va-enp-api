"""Tests for app/telemetry.py."""

import os
from unittest.mock import patch

from opentelemetry import metrics, trace

from app.telemetry import configure_telemetry


def test_configure_telemetry_configures_providers_when_endpoint_set() -> None:
    """Should configure trace and meter providers when endpoint is set."""
    with patch.dict(os.environ, {'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://localhost:4317'}):
        configure_telemetry()
        assert trace.get_tracer_provider().__class__.__name__ == 'TracerProvider'
        assert metrics.get_meter_provider().__class__.__name__ == 'MeterProvider'


def test_configure_telemetry_no_endpoint_does_not_configure_providers() -> None:
    """Should not configure providers when OTEL_EXPORTER_OTLP_ENDPOINT is not set."""
    with patch.dict(os.environ, {'OTEL_EXPORTER_OTLP_ENDPOINT': ''}, clear=True):
        with patch('app.telemetry.TracerProvider') as mock_tracer:
            configure_telemetry()
            mock_tracer.assert_not_called()
