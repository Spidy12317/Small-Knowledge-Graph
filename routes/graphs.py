from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from models.graph import CreateGraphRequest
from repository import GraphRepository
from services.app_state import state

router = APIRouter(tags=["graphs"])


@router.get("")
async def list_graphs():
    summaries = await GraphRepository.list_graphs()
    return {
        "graphs": [
            {
                "id": str(s.id),
                "name": s.name,
                "node_count": s.node_count,
                "is_default": s.id == state.graph_id,
            }
            for s in summaries
        ],
        "default_graph_id": str(state.graph_id),
    }


@router.post("")
async def create_graph(payload: CreateGraphRequest):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name must not be empty")

    existing_id = await GraphRepository.get_graph_id_by_name(name)
    if existing_id is not None:
        raise HTTPException(status_code=409, detail=f"A graph named {name!r} already exists")

    graph_id = await GraphRepository.create_graph(name)
    return {"id": str(graph_id), "name": name, "node_count": 1}


@router.delete("/{graph_id}")
async def delete_graph(graph_id: uuid.UUID):
    if graph_id == state.graph_id:
        raise HTTPException(status_code=400, detail="Cannot delete the default graph")

    name = await GraphRepository.get_graph_name(graph_id)
    if name is None:
        raise HTTPException(status_code=404, detail=f"Graph {graph_id} not found")

    await GraphRepository.delete_graph(graph_id)
    return {"deleted": True}
