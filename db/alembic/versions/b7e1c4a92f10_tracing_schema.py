"""tracing schema

Revision ID: b7e1c4a92f10
Revises: 30c6d4d2067d
Create Date: 2026-09-26 14:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b7e1c4a92f10"
down_revision: Union[str, Sequence[str], None] = "30c6d4d2067d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS tracing")
    op.create_table(
        "spans",
        sa.Column("span_id", sa.String(length=16), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("parent_span_id", sa.String(length=16), nullable=True),
        sa.Column("graph_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("events", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("span_id", name=op.f("pk_spans")),
        schema="tracing",
    )
    op.create_index(
        "ix_tracing_spans_graph_id_started_at",
        "spans",
        ["graph_id", "started_at"],
        unique=False,
        schema="tracing",
    )
    op.create_index(
        "ix_tracing_spans_trace_id_step_index",
        "spans",
        ["trace_id", "step_index"],
        unique=False,
        schema="tracing",
    )


def downgrade() -> None:
    op.drop_index("ix_tracing_spans_trace_id_step_index", table_name="spans", schema="tracing")
    op.drop_index("ix_tracing_spans_graph_id_started_at", table_name="spans", schema="tracing")
    op.drop_table("spans", schema="tracing")
    op.execute("DROP SCHEMA IF EXISTS tracing")
