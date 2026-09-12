from __future__ import annotations

import uuid
from collections import Counter

from fastapi import APIRouter, Query

from core import configs
from repository import GraphRepository
from services.app_state import state

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(graph_id: uuid.UUID | None = Query(default=None)):
    snapshot = await GraphRepository.get_full_graph(graph_id or state.graph_id)
    type_counts = Counter(n.node_type for n in snapshot.nodes)

    anthropic = configs.get_anthropic_settings()
    openai = configs.get_openai_settings()
    azure = configs.get_azure_openai_settings()
    azure_gpt5 = configs.get_azure_gpt5_settings()
    groq = configs.get_groq_settings()
    graph_settings = configs.get_graph_settings()

    return {
        "status": "ok",
        "llm": {
            "provider": state.llm.llm_provider,
            "model": state.llm.deployment,
            "providers_configured": {
                "anthropic": anthropic.is_configured(),
                "openai": openai.is_configured(),
                "azure_openai": azure.is_configured(),
                "azure_openai_gpt5": azure_gpt5.is_configured(),
                "groq": groq.is_configured(),
            },
        },
        "graph_settings": {
            "max_root_children": graph_settings.GRAPH_MAX_ROOT_CHILDREN,
            "max_node_children": graph_settings.GRAPH_MAX_NODE_CHILDREN,
            "max_concurrent_evaluations": graph_settings.GRAPH_MAX_CONCURRENT_EVALUATIONS,
            "high_confidence_score_threshold": graph_settings.GRAPH_HIGH_CONFIDENCE_SCORE_THRESHOLD,
            "max_concurrent_insertions": graph_settings.GRAPH_MAX_CONCURRENT_INSERTIONS,
        },
        "stats": {
            "num_nodes": len(snapshot.nodes),
            "num_edges": len(snapshot.edges),
            "num_data_relations": len(snapshot.data_relations),
            "by_type": dict(type_counts),
        },
    }
