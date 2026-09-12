from __future__ import annotations

from fastapi import APIRouter

from models.graph import QueryRequest, serialize_candidate
from services.app_state import state
from services.graph_service.service import GraphService

router = APIRouter(tags=["query"])


@router.post("/query")
async def query_graph(payload: QueryRequest):
    graph_service = GraphService(payload.graph_id or state.graph_id, state.llm)
    async with state.lock:
        candidates = await graph_service.retrieve(payload.query)
    return {
        "query": payload.query,
        "results": [serialize_candidate(c) for c in candidates],
    }
