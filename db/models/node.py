from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.enums import NodeType
from db.base import Base

if TYPE_CHECKING:
    from db.models.graph import GraphRow


class NodeRow(Base):
    __tablename__ = "nodes"
    __table_args__ = (
        UniqueConstraint("graph_id", "node_id", name="uq_nodes_graph_id_node_id"),
        # Every graph has exactly one central node.
        Index(
            "uq_nodes_one_central_per_graph",
            "graph_id",
            unique=True,
            postgresql_where=text(f"node_type = '{NodeType.CENTRAL.value}'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    graph_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False,
    )

    # Business/domain identifier used by the app (e.g. "central_0" or a uuid4 string),
    # unique per graph — distinct from the surrogate `id` used for FKs below.
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)

    label: Mapped[str] = mapped_column(Text, nullable=False)
    node_type: Mapped[NodeType] = mapped_column(
        SqlEnum(NodeType, name="node_type_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    node_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    graph: Mapped["GraphRow"] = relationship(back_populates="nodes")

    def __repr__(self) -> str:
        return f"NodeRow(node_id={self.node_id!r}, node_type={self.node_type!r})"
