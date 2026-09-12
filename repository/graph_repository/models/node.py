from typing import Any

from pydantic import BaseModel, Field


class Node(BaseModel):
    node_id: str
    label: str
    node_type: str
    description: str | None = None
    raw_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)