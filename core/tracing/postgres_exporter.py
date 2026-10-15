from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult, SpanExporter

from db.base import get_sessionmaker
from db.models.span import SpanRow

logger = logging.getLogger(__name__)

_STOP = object()


class PostgresSpanExporter(SpanExporter):
    """Queues finished spans and writes them into the tracing schema.

    The OpenTelemetry export hook is synchronous and runs off the event-loop
    thread. ``export`` only enqueues. A task started with the app drains the
    queue through the existing async database session.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._task: asyncio.Task | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._queue = asyncio.Queue()
        self._task = loop.create_task(self._run(), name="tracing-postgres-writer")

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self._loop is None or self._queue is None:
            logger.error("tracing exporter received spans before the writer was started")
            return SpanExportResult.FAILURE
        rows = [_row_from_span(span) for span in spans]
        self._loop.call_soon_threadsafe(self._queue.put_nowait, rows)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        if self._loop is None or self._queue is None:
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, _STOP)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    async def wait_stopped(self) -> None:
        if self._task is None:
            return
        await self._task

    async def _run(self) -> None:
        assert self._queue is not None
        while True:
            item = await self._queue.get()
            try:
                if item is _STOP:
                    return
                await _insert_rows(item)
            except Exception:
                logger.exception("failed to persist trace spans")
            finally:
                self._queue.task_done()


def _row_from_span(span: ReadableSpan) -> dict[str, Any]:
    context = span.get_span_context()
    parent = span.parent
    attributes = dict(span.attributes or {})
    graph_id = _graph_id(attributes.get("skg.graph_id"))
    step_index = attributes.get("skg.step_index", 0)
    started_at = _from_nanos(span.start_time)
    ended_at = _from_nanos(span.end_time) if span.end_time is not None else None
    return {
        "trace_id": format(context.trace_id, "032x"),
        "span_id": format(context.span_id, "016x"),
        "parent_span_id": format(parent.span_id, "016x") if parent is not None else None,
        "graph_id": graph_id,
        "name": span.name,
        "step_index": int(step_index) if isinstance(step_index, int) else 0,
        "status": span.status.status_code.name,
        "started_at": started_at,
        "ended_at": ended_at,
        "attributes": _json_safe(attributes),
        "events": _json_safe([
            {
                "name": event.name,
                "timestamp": event.timestamp,
                "attributes": dict(event.attributes or {}),
            }
            for event in span.events
        ]),
    }


def _graph_id(value: Any) -> uuid.UUID | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _from_nanos(nanos: int | None) -> datetime:
    if nanos is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(nanos / 1_000_000_000, tz=timezone.utc)


async def _insert_rows(rows: list[dict[str, Any]]) -> None:
    async with get_sessionmaker()() as session:
        session.add_all([SpanRow(**row) for row in rows])
        await session.commit()
