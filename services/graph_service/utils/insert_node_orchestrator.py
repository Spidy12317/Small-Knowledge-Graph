from __future__ import annotations

import uuid

import services
from core.tracing import traced
from services.graph_service.utils.find_new_node_insert_location import find_insert_location
from services.graph_service.utils.extract_chunk_context import extract_chunk_context
from services.graph_service.utils.insert_audit import InsertAuditCollector
from services.graph_service.utils.insert_new_node import insert


@traced
async def insert_chunk(
    chunk: str,
    graph_id: uuid.UUID,
    llm: services.LLMService,
    update_graph: bool = True,
) -> dict:
    """Runs the full insertion pipeline and returns a trace of every step —
    chunk context, candidate insertion points, and the resulting attachment
    plan — for the UI to display alongside the mutated graph."""
    audit_collector = InsertAuditCollector(llm.llm_provider, llm.deployment)
    chunk_context = await extract_chunk_context(chunk, graph_id, llm, collector=audit_collector)
    insertion_points = await find_insert_location(
        chunk, graph_id, llm, chunk_context=chunk_context, collector=audit_collector,
    )
    newly_inserted_node, parent_attachment_plans, parent_label_description_updates = await insert(
        chunk,
        insertion_points,
        graph_id,
        llm,
        chunk_context=chunk_context,
        update_graph=update_graph,
        collector=audit_collector,
    )
    return {
        "chunk_context": chunk_context,
        "insertion_points": insertion_points,
        "newly_inserted_node": newly_inserted_node,
        "parent_attachment_plans": parent_attachment_plans,
        "parent_label_description_updates": parent_label_description_updates,
        "audit_collector": audit_collector,
    }
