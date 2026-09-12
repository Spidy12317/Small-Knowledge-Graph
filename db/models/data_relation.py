from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.graph import GraphRow


class DataRelationRow(Base):
    """An undirected cross-reference between two sibling data nodes (source_id < target_id)."""

    __tablename__ = "data_relations"
    __table_args__ = (
        UniqueConstraint(
            "graph_id", "source_id", "target_id", name="uq_data_relations_graph_source_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    graph_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    graph: Mapped["GraphRow"] = relationship(back_populates="data_relations")

    def __repr__(self) -> str:
        return f"DataRelationRow(source_id={self.source_id!r}, target_id={self.target_id!r})"
