from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from core.configs import get_tracing_settings
from core.tracing.postgres_exporter import PostgresSpanExporter

logger = logging.getLogger(__name__)

_provider: TracerProvider | None = None
_postgres_exporter: PostgresSpanExporter | None = None


def setup_tracing() -> None:
    """Installs the process-wide tracer. Call once at startup, before requests."""
    global _provider, _postgres_exporter

    settings = get_tracing_settings()
    exporter_name = settings.exporter()
    provider = TracerProvider(resource=Resource.create({"service.name": settings.OTEL_SERVICE_NAME}))

    if exporter_name == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        _postgres_exporter = None
        logger.info("tracing exporter=otlp endpoint=%s", settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    else:
        _postgres_exporter = PostgresSpanExporter()
        exporter = _postgres_exporter
        logger.info("tracing exporter=postgres schema=tracing")

    provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=500))
    trace.set_tracer_provider(provider)
    _provider = provider


def bind_postgres_writer() -> None:
    """Starts the async writer. Must run on the application event loop."""
    if _postgres_exporter is None:
        return
    import asyncio

    _postgres_exporter.bind(asyncio.get_running_loop())


async def shutdown_tracing() -> None:
    """Flushes queued spans, then lets the Postgres writer drain them."""
    if _provider is not None:
        _provider.force_flush()
        _provider.shutdown()
    if _postgres_exporter is not None:
        await _postgres_exporter.wait_stopped()
