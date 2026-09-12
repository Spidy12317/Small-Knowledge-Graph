from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.graph import GraphRow


class EdgeRow(Base):
    """A directed parent → child edge between two nodes in the same graph."""

    __tablename__ = "edges"
    __table_args__ = (
        UniqueConstraint("graph_id", "source_id", "target_id", name="uq_edges_graph_source_target"),
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

    graph: Mapped["GraphRow"] = relationship(back_populates="edges")

    def __repr__(self) -> str:
        return f"EdgeRow(source_id={self.source_id!r}, target_id={self.target_id!r})"
