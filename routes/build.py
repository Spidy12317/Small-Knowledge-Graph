from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from core.tracing import current_trace_id
from core.tracing.reader import get_trace, list_traces
from core.tracing.replay import replay_steps
from models.graph import InsertRequest, serialize_candidate, serialize_node
from repository import GraphRepository
from services.app_state import state
from services.graph_service.service import GraphService

router = APIRouter(tags=["build"])


@router.get("/pipeline-history")
async def get_pipeline_history(graph_id: uuid.UUID | None = Query(default=None)):
    """Returns every insert's pipeline trace recorded for this graph since the
    server started, oldest first, however each insert was triggered (UI or a
    direct API call)."""
    target_graph_id = graph_id or state.graph_id
    return list(state.pipeline_trace_history_by_graph_id.get(target_graph_id, []))


@router.get("/traces")
async def get_graph_traces(graph_id: uuid.UUID | None = Query(default=None)):
    """Graph updates recorded for this graph, oldest first."""
    target_graph_id = graph_id or state.graph_id
    if target_graph_id is None:
        return []
    return await list_traces(target_graph_id)


@router.get("/steps")
async def get_replayed_steps(graph_id: uuid.UUID | None = Query(default=None)):
    """Each recorded graph update, with the graph as it would look after that
    update. Replayed in memory from the stored decisions. Nothing is written."""
    target_graph_id = graph_id or state.graph_id
    if target_graph_id is None:
        return {"graph_id": None, "steps": []}
    return await replay_steps(target_graph_id)


@router.get("/traces/{trace_id}")
async def get_graph_trace(trace_id: str):
    """One graph update and the decisions made during it, in step order."""
    trace = await get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return trace


@router.post("/insert")
async def insert_chunk(payload: InsertRequest):
    chunk = payload.chunk.strip()
    if not chunk:
        raise HTTPException(status_code=400, detail="chunk must not be empty")

    target_graph_id = payload.graph_id or state.graph_id
    graph_service = GraphService(target_graph_id, state.llm)

    async with state.lock:
        before = await GraphRepository.get_full_graph(target_graph_id)
        before_nodes_by_id = {n.node_id: n for n in before.nodes}
        before_edges = {(e["source_id"], e["target_id"]) for e in before.edges}

        pipeline_trace = await graph_service.insert_chunk(chunk, update_graph=True)

        after = await GraphRepository.get_full_graph(target_graph_id)
        after_nodes_by_id = {n.node_id: n for n in after.nodes}
        after_edges = {(e["source_id"], e["target_id"]) for e in after.edges}

    added_node_ids = set(after_nodes_by_id) - set(before_nodes_by_id)
    removed_node_ids = set(before_nodes_by_id) - set(after_nodes_by_id)
    updated_node_ids = {
        node_id
        for node_id in set(after_nodes_by_id) & set(before_nodes_by_id)
        if before_nodes_by_id[node_id].label != after_nodes_by_id[node_id].label
        or before_nodes_by_id[node_id].description != after_nodes_by_id[node_id].description
    }

    added_edges = after_edges - before_edges
    removed_edges = before_edges - after_edges

    response = {
        "trace_id": current_trace_id(),
        "chunk": chunk,
        "inserted_at": datetime.now(timezone.utc).isoformat(),
        "graph": {
            "graph_id": str(after.graph_id),
            "name": after.name,
            "nodes": [serialize_node(n) for n in after.nodes],
            "edges": after.edges,
            "data_relations": after.data_relations,
            "context": after.context,
            "central_id": after.central_id,
        },
        "diff": {
            "added_nodes": [serialize_node(after_nodes_by_id[nid]) for nid in added_node_ids],
            "removed_node_ids": list(removed_node_ids),
            "updated_nodes": [serialize_node(after_nodes_by_id[nid]) for nid in updated_node_ids],
            "added_edges": [{"source_id": s, "target_id": t} for s, t in added_edges],
            "removed_edges": [{"source_id": s, "target_id": t} for s, t in removed_edges],
        },
        "pipeline": {
            "chunk_context": pipeline_trace["chunk_context"],
            "insertion_points": [
                serialize_candidate(c) for c in pipeline_trace["insertion_points"]
            ],
            "new_node": serialize_node(pipeline_trace["newly_inserted_node"]),
            "parent_attachment_plans": pipeline_trace["parent_attachment_plans"],
            "parent_label_description_updates": pipeline_trace["parent_label_description_updates"],
        },
    }
    state.record_pipeline_trace(target_graph_id, response)
    return response
