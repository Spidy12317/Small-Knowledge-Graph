from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class SpanRow(Base):
    """One finished OpenTelemetry span for a graph-update decision."""

    __tablename__ = "spans"
    __table_args__ = (
        Index("ix_tracing_spans_graph_id_started_at", "graph_id", "started_at"),
        Index("ix_tracing_spans_trace_id_step_index", "trace_id", "step_index"),
        {"schema": "tracing"},
    )

    span_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(String(16))
    graph_id: Mapped[uuid.UUID | None] = mapped_column()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    events: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
