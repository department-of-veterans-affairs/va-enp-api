"""Test suite for logging configurations with Loguru."""

import logging
import sys
from unittest.mock import ANY, patch

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.constants import DEPLOYMENT_ENVS, ENV
from app.logging.logging_config import (
    LOGLEVEL_DEBUG,
    CustomizeLogger,
    InterceptHandler,
    get_trace_context,
)


def test_make_logger() -> None:
    """Test to ensure the logger is configured correctly using CustomizeLogger."""
    with (
        patch('app.logging.logging_config.loguru_logger') as logger_mock,
    ):
        # Create references to the loggers before calling make_logger
        fastapi_logger = logging.getLogger('fastapi')
        uvicorn_loggers = [logging.getLogger(name) for name in ('uvicorn', 'uvicorn.access', 'uvicorn.error')]

        # Call the method under test
        CustomizeLogger.make_logger()

        # Check logger.add was called with correct parameters
        logger_mock.add.assert_any_call(
            sys.stdout,
            enqueue=True,
            backtrace=False,
            level=LOGLEVEL_DEBUG,
            filter=ANY,
            serialize=ENV in DEPLOYMENT_ENVS,
        )
        logger_mock.add.assert_any_call(
            sys.stderr,
            enqueue=True,
            backtrace=False,
            level='ERROR',
            serialize=ENV in DEPLOYMENT_ENVS,
        )

        # Verify that the InterceptHandler was added to the appropriate loggers
        assert all(isinstance(handler, InterceptHandler) for handler in fastapi_logger.handlers)

        for logger in uvicorn_loggers:
            assert all(isinstance(handler, InterceptHandler) for handler in logger.handlers)


def test_trace_context_returns_valid_ids_inside_active_span() -> None:
    """When a span is active, trace_id and span_id should be real hex values."""
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer('test')

    with tracer.start_as_current_span('test-span'):
        ctx = get_trace_context()

    assert ctx['trace_id'] != 'none'
    assert ctx['span_id'] != 'none'
    assert len(ctx['trace_id']) == 32
    assert len(ctx['span_id']) == 16


def test_trace_context_returns_none_outside_active_span() -> None:
    """When no span is active, trace_id and span_id should be 'none'."""
    trace.set_tracer_provider(TracerProvider())

    ctx = get_trace_context()

    assert ctx['trace_id'] == 'none'
    assert ctx['span_id'] == 'none'
