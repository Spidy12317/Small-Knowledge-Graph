from __future__ import annotations

import uuid

from pydantic import BaseModel


def serialize_node(node) -> dict:
    return {
        "node_id": node.node_id,
        "label": node.label,
        "node_type": node.node_type,
        "description": node.description,
        "raw_text": node.raw_text,
        "metadata": node.metadata,
    }


def serialize_candidate(candidate) -> dict:
    node_type = candidate.node_type
    return {
        "node_id": candidate.node_id,
        "node": serialize_node(candidate.node),
        "node_type": node_type.value if hasattr(node_type, "value") else node_type,
        "reasoning": candidate.reasoning,
        "path_to_node": [
            [serialize_node(n) for n in path] for path in candidate.path_to_node
        ],
    }


class InsertRequest(BaseModel):
    chunk: str
    graph_id: uuid.UUID | None = None


class QueryRequest(BaseModel):
    query: str
    graph_id: uuid.UUID | None = None


class CreateGraphRequest(BaseModel):
    name: str
