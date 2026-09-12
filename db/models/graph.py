from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.data_relation import DataRelationRow
    from db.models.edge import EdgeRow
    from db.models.node import NodeRow


class GraphRow(Base):
    __tablename__ = "graphs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    nodes: Mapped[list["NodeRow"]] = relationship(
        back_populates="graph", cascade="all, delete-orphan", passive_deletes=True,
    )
    edges: Mapped[list["EdgeRow"]] = relationship(
        back_populates="graph", cascade="all, delete-orphan", passive_deletes=True,
    )
    data_relations: Mapped[list["DataRelationRow"]] = relationship(
        back_populates="graph", cascade="all, delete-orphan", passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"GraphRow(id={self.id!r}, name={self.name!r})"
