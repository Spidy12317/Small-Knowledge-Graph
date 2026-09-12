from __future__ import annotations

import atexit

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from core.telemetry.exporter import JSONLFileSpanExporter

_initialized = False


def setup_telemetry() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    from core.configs import get_otel_settings
    settings = get_otel_settings()

    if not settings.OTEL_ENABLED:
        return

    resource = Resource(attributes={SERVICE_NAME: settings.OTEL_SERVICE_NAME})
    exporter = JSONLFileSpanExporter(path=settings.OTEL_TRACES_FILE)
    processor = SimpleSpanProcessor(exporter)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    atexit.register(provider.shutdown)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)
