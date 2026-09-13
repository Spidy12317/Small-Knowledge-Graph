from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from db.base import get_sessionmaker
from db.models.span import SpanRow


async def list_traces(graph_id: uuid.UUID) -> list[dict[str, Any]]:
    """Every graph update for this graph, oldest first, without span payloads."""
    async with get_sessionmaker()() as session:
        result = await session.execute(
            select(
                SpanRow.trace_id,
                SpanRow.graph_id,
                SpanRow.name,
                SpanRow.step_index,
                SpanRow.status,
                SpanRow.started_at,
            )
            .where(SpanRow.graph_id == graph_id)
            .order_by(SpanRow.started_at, SpanRow.step_index)
        )
        rows = result.all()

    grouped: dict[str, dict[str, Any]] = {}
    for trace_id, row_graph_id, name, step_index, status, started_at in rows:
        entry = grouped.get(trace_id)
        if entry is None:
            entry = {
                "trace_id": trace_id,
                "graph_id": str(row_graph_id) if row_graph_id is not None else None,
                "started_at": _iso(started_at),
                "root_name": name,
                "span_count": 0,
                "status": "OK",
            }
            grouped[trace_id] = entry
        entry["span_count"] += 1
        if step_index == 0:
            entry["root_name"] = name
            entry["started_at"] = _iso(started_at)
        if status == "ERROR":
            entry["status"] = "ERROR"
    return list(grouped.values())


async def get_trace(trace_id: str) -> dict[str, Any] | None:
    """One graph update: its spans in decision order, with inputs and outputs parsed."""
    async with get_sessionmaker()() as session:
        result = await session.execute(
            select(SpanRow).where(SpanRow.trace_id == trace_id).order_by(SpanRow.step_index, SpanRow.started_at)
        )
        spans = list(result.scalars().all())
    if not spans:
        return None

    first = spans[0]
    return {
        "trace_id": trace_id,
        "graph_id": str(first.graph_id) if first.graph_id is not None else None,
        "started_at": _iso(first.started_at),
        "spans": [_span_dict(span) for span in spans],
    }


def _span_dict(span: SpanRow) -> dict[str, Any]:
    return {
        "span_id": span.span_id,
        "parent_span_id": span.parent_span_id,
        "name": span.name,
        "step_index": span.step_index,
        "status": span.status,
        "started_at": _iso(span.started_at),
        "ended_at": _iso(span.ended_at) if span.ended_at is not None else None,
        "attributes": span.attributes,
        "events": [_event_dict(event) for event in span.events or []],
    }


def _event_dict(event: dict[str, Any]) -> dict[str, Any]:
    attributes = dict(event.get("attributes") or {})
    payload = attributes.get("payload")
    if isinstance(payload, str):
        try:
            attributes["payload"] = json.loads(payload)
        except json.JSONDecodeError:
            pass
    return {"name": event.get("name"), "attributes": attributes}


def _iso(value: datetime) -> str:
    return value.isoformat()
