from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Query

from models.graph import serialize_node
from repository import GraphRepository
from repository.graph_repository.models import GraphSnapshot
from services.app_state import DEFAULT_GRAPH_NAME, state

router = APIRouter(tags=["graph"])


def _serialize_snapshot(snapshot: GraphSnapshot) -> dict:
    return {
        "graph_id": str(snapshot.graph_id),
        "name": snapshot.name,
        "nodes": [serialize_node(n) for n in snapshot.nodes],
        "edges": snapshot.edges,
        "data_relations": snapshot.data_relations,
        "context": snapshot.context,
        "central_id": snapshot.central_id,
    }


@router.get("")
async def get_graph(graph_id: uuid.UUID | None = Query(default=None)):
    snapshot = await GraphRepository.get_full_graph(graph_id or state.graph_id)
    return _serialize_snapshot(snapshot)


@router.get("/nodes/{node_id}")
async def get_node(node_id: str, graph_id: uuid.UUID | None = Query(default=None)):
    target_graph_id = graph_id or state.graph_id
    node = await GraphRepository.get_node(target_graph_id, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found")

    children_map, parents_map = await asyncio.gather(
        GraphRepository.get_children_batch(target_graph_id, [node_id]),
        GraphRepository.get_parents_batch(target_graph_id, [node_id]),
    )
    return {
        "node": serialize_node(node),
        "children": [serialize_node(n) for n in children_map.get(node_id, [])],
        "parents": [serialize_node(n) for n in parents_map.get(node_id, [])],
    }


@router.post("/reset")
async def reset_graph(graph_id: uuid.UUID | None = Query(default=None)):
    target_graph_id = graph_id or state.graph_id

    name = await GraphRepository.get_graph_name(target_graph_id)
    if name is None:
        raise HTTPException(status_code=404, detail=f"Graph {target_graph_id} not found")

    # The bundled sample data only makes sense for the bootstrap graph — any other
    # graph resets back to empty (a single central node) rather than the demo content.
    new_graph_id = await GraphRepository.reset_graph(
        target_graph_id, name, reseed_from_json=name == DEFAULT_GRAPH_NAME,
    )

    if target_graph_id == state.graph_id:
        state.graph_id = new_graph_id

    snapshot = await GraphRepository.get_full_graph(new_graph_id)
    return _serialize_snapshot(snapshot)
