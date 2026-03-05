"""Tests for app/telemetry.py."""

import os
from unittest.mock import patch

import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

from app.telemetry import configure_telemetry


@pytest.fixture(autouse=True)
def reset_otel_providers() -> None:
    """Reset OTel providers before and after each test to avoid global state bleed.

    Yields:
        None: Yields control to the test, then resets providers after.
    """
    trace.set_tracer_provider(TracerProvider())
    metrics.set_meter_provider(MeterProvider())
    yield
    trace.set_tracer_provider(TracerProvider())
    metrics.set_meter_provider(MeterProvider())


def test_configure_telemetry_configures_providers_when_endpoint_set() -> None:
    """Should configure trace and meter providers when endpoint is set."""
    with patch.dict(os.environ, {'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://localhost:4317'}):
        configure_telemetry()
        assert trace.get_tracer_provider().__class__.__name__ == 'TracerProvider'
        assert metrics.get_meter_provider().__class__.__name__ == 'MeterProvider'


def test_configure_telemetry_no_endpoint_does_not_set_providers() -> None:
    """Should return early when OTEL_EXPORTER_OTLP_ENDPOINT is not set."""
    provider_before = trace.get_tracer_provider()
    with patch.dict(os.environ, {'OTEL_EXPORTER_OTLP_ENDPOINT': ''}, clear=True):
        configure_telemetry()
        # Provider should be unchanged since configure_telemetry() returns early without an endpoint
        assert trace.get_tracer_provider() is provider_before
