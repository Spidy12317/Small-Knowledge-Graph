from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


def _span_to_dict(span: ReadableSpan) -> dict:
    trace_id = format(span.context.trace_id, "032x")
    span_id = format(span.context.span_id, "016x")
    parent_span_id = format(span.parent.span_id, "016x") if span.parent else None
    start_ns = span.start_time or 0
    end_ns = span.end_time or 0

    events = []
    for event in span.events:
        events.append({
            "name": event.name,
            "timestamp_unix_nano": event.timestamp,
            "attributes": dict(event.attributes) if event.attributes else {},
        })

    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "name": span.name,
        "kind": span.kind.name,
        "start_time_unix_nano": start_ns,
        "end_time_unix_nano": end_ns,
        "duration_ms": round((end_ns - start_ns) / 1_000_000, 3),
        "status": {
            "code": span.status.status_code.name if span.status else "UNSET",
            "description": (span.status.description or "") if span.status else "",
        },
        "attributes": dict(span.attributes) if span.attributes else {},
        "events": events,
        "resource": dict(span.resource.attributes) if span.resource else {},
    }


class JSONLFileSpanExporter(SpanExporter):
    def __init__(self, path: str):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            with self._lock:
                with open(self._path, "a", encoding="utf-8") as f:
                    for span in spans:
                        f.write(json.dumps(_span_to_dict(span)) + "\n")
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        pass
