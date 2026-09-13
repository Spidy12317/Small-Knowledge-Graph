from __future__ import annotations

import copy
import json
import uuid
from typing import Any

from sqlalchemy import select

from db.base import get_sessionmaker
from db.models.span import SpanRow
from models.graph import serialize_node
from repository import GraphRepository

_CONTEXT_PREFIX = "Graph context so far (rolling summary of all prior chunks):\n"
_CONTEXT_SUFFIX = "\n\nNew chunk:\n"


async def replay_steps(graph_id: uuid.UUID) -> dict[str, Any]:
    """Builds each graph update by replaying recorded decisions in order.

    Reads the current graph and the stored spans, then applies those decisions
    on an in-memory copy. Nothing is written back.
    """
    snapshot = await GraphRepository.get_full_graph(graph_id)
    async with get_sessionmaker()() as session:
        result = await session.execute(
            select(SpanRow)
            .where(SpanRow.graph_id == graph_id)
            .order_by(SpanRow.started_at, SpanRow.step_index)
        )
        spans = list(result.scalars().all())

    traces = _group_traces(spans)
    sim = _Sim.from_snapshot(snapshot)
    for trace in reversed(traces):
        _undo_trace(sim, trace)
    prior = _prior_context(_extract_user_prompt(traces[0])) if traces else None
    if prior is not None:
        sim.context = prior

    steps = []
    for index, trace in enumerate(traces, start=1):
        added_node_ids = _apply_trace(sim, trace)
        steps.append(_step_payload(index, trace, sim, added_node_ids))
    return {"graph_id": str(graph_id), "steps": steps}


def _group_traces(spans: list[SpanRow]) -> list[list[SpanRow]]:
    order: list[str] = []
    grouped: dict[str, list[SpanRow]] = {}
    for span in spans:
        if span.trace_id not in grouped:
            order.append(span.trace_id)
            grouped[span.trace_id] = []
        grouped[span.trace_id].append(span)
    return [sorted(grouped[trace_id], key=lambda span: span.step_index) for trace_id in order]


class _Sim:
    def __init__(self, graph_id: str, name: str, context: str, central_id: str) -> None:
        self.graph_id = graph_id
        self.name = name
        self.context = context
        self.central_id = central_id
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: set[tuple[str, str]] = set()
        self.relations: set[tuple[str, str]] = set()

    @classmethod
    def from_snapshot(cls, snapshot) -> _Sim:
        sim = cls(
            str(snapshot.graph_id),
            snapshot.name,
            snapshot.context or "",
            snapshot.central_id,
        )
        sim.nodes = {node.node_id: serialize_node(node) for node in snapshot.nodes}
        sim.edges = {(edge["source_id"], edge["target_id"]) for edge in snapshot.edges}
        sim.relations = {
            (relation["source_id"], relation["target_id"]) for relation in snapshot.data_relations
        }
        return sim

    def to_graph(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "name": self.name,
            "nodes": [copy.deepcopy(node) for node in self.nodes.values()],
            "edges": [{"source_id": source, "target_id": target} for source, target in sorted(self.edges)],
            "data_relations": [
                {"source_id": source, "target_id": target} for source, target in sorted(self.relations)
            ],
            "context": self.context,
            "central_id": self.central_id,
        }


def _undo_trace(sim: _Sim, spans: list[SpanRow]) -> None:
    plan = _mutation_plan(spans)
    if plan is None:
        return
    for source, target in _pairs(plan.get("data_relations_to_add")):
        sim.relations.discard((source, target))
    for source, target in _pairs(plan.get("edges_to_add")):
        sim.edges.discard((source, target))
    for source, target in _pairs(plan.get("edges_to_remove")):
        sim.edges.add((source, target))
    for node_id, before in _labels_before(spans).items():
        node = sim.nodes.get(node_id)
        if node is None:
            continue
        node["label"] = before["label"]
        node["description"] = before.get("description")
    for node in plan.get("nodes_to_add") or []:
        node_id = node.get("node_id")
        if not node_id:
            continue
        sim.nodes.pop(node_id, None)
        sim.edges = {edge for edge in sim.edges if node_id not in edge}
        sim.relations = {relation for relation in sim.relations if node_id not in relation}


def _apply_trace(sim: _Sim, spans: list[SpanRow]) -> list[str]:
    new_context = _new_context(spans)
    if new_context is not None:
        sim.context = new_context
    plan = _mutation_plan(spans)
    if plan is None:
        return []
    added: list[str] = []
    for node in plan.get("nodes_to_add") or []:
        node_id = node.get("node_id")
        if not node_id:
            continue
        sim.nodes[node_id] = {
            "node_id": node_id,
            "label": node.get("label") or "",
            "node_type": node.get("node_type") or "data",
            "description": node.get("description"),
            "raw_text": node.get("raw_text"),
            "metadata": node.get("metadata") or {},
        }
        added.append(node_id)
    for update in plan.get("label_updates") or []:
        node = sim.nodes.get(update.get("node_id"))
        if node is None:
            continue
        node["label"] = update.get("label") or node["label"]
        node["description"] = update.get("description")
    for source, target in _pairs(plan.get("edges_to_remove")):
        sim.edges.discard((source, target))
    for node_id in plan.get("node_ids_to_remove") or []:
        sim.nodes.pop(node_id, None)
        sim.edges = {edge for edge in sim.edges if node_id not in edge}
        sim.relations = {relation for relation in sim.relations if node_id not in relation}
    for source, target in _pairs(plan.get("edges_to_add")):
        if source in sim.nodes and target in sim.nodes:
            sim.edges.add((source, target))
    for source, target in _pairs(plan.get("data_relations_to_add")):
        if source in sim.nodes and target in sim.nodes:
            sim.relations.add((source, target))
    return added


def _step_payload(index: int, spans: list[SpanRow], sim: _Sim, added_node_ids: list[str]) -> dict[str, Any]:
    root = spans[0]
    status = "ERROR" if any(span.status == "ERROR" for span in spans) else "OK"
    return {
        "index": index,
        "trace_id": root.trace_id,
        "started_at": root.started_at.isoformat(),
        "status": status,
        "chunk": _chunk(spans),
        "chunk_context": _chunk_context(spans),
        "added_node_ids": added_node_ids,
        "spans": [
            {"step_index": span.step_index, "name": span.name, "status": span.status}
            for span in spans
        ],
        "llm_calls": [_llm_call(span) for span in spans if span.name == "invoke_llm_and_parse_json"],
        "graph": sim.to_graph(),
    }


def _llm_call(span: SpanRow) -> dict[str, Any]:
    entered = _event_payload(span, "decision.input") or {}
    output = _event_payload(span, "decision.output")
    return {
        "step_index": span.step_index,
        "status": span.status,
        "system": entered.get("sys_msg") or "",
        "user": entered.get("user_prompt") or "",
        "output": output,
    }


def _mutation_plan(spans: list[SpanRow]) -> dict[str, Any] | None:
    for span in spans:
        if span.name != "apply_mutations":
            continue
        payload = _event_payload(span, "decision.input") or {}
        plan = payload.get("plan")
        if isinstance(plan, dict):
            return plan
    return None


def _labels_before(spans: list[SpanRow]) -> dict[str, dict[str, Any]]:
    befores: dict[str, dict[str, Any]] = {}
    for span in spans:
        if span.name != "_update_parent_node_label_and_description":
            continue
        payload = _event_payload(span, "decision.input") or {}
        parent = payload.get("parent_node") or {}
        node = parent.get("node") if isinstance(parent, dict) else None
        if not isinstance(node, dict) or not node.get("node_id"):
            continue
        node_id = node["node_id"]
        if node_id not in befores:
            befores[node_id] = {"label": node.get("label") or "", "description": node.get("description")}
    return befores


def _new_context(spans: list[SpanRow]) -> str | None:
    for span in spans:
        if span.name != "update_graph_context":
            continue
        payload = _event_payload(span, "decision.input") or {}
        new_context = payload.get("new_context")
        if isinstance(new_context, str):
            return new_context
    return None


def _chunk(spans: list[SpanRow]) -> str:
    for span in spans:
        if span.name != "insert_chunk":
            continue
        payload = _event_payload(span, "decision.input") or {}
        chunk = payload.get("chunk")
        if isinstance(chunk, str):
            return chunk
    return ""


def _chunk_context(spans: list[SpanRow]) -> str:
    for span in spans:
        if span.name != "insert_chunk":
            continue
        payload = _event_payload(span, "decision.output") or {}
        context = payload.get("chunk_context")
        if isinstance(context, str):
            return context
    return ""


def _extract_user_prompt(spans: list[SpanRow]) -> str:
    for span in spans:
        if span.name != "invoke_llm_and_parse_json":
            continue
        output = _event_payload(span, "decision.output")
        if not isinstance(output, dict) or "updated_graph_context" not in output:
            continue
        payload = _event_payload(span, "decision.input") or {}
        user = payload.get("user_prompt")
        if isinstance(user, str):
            return user
    return ""


def _prior_context(user_prompt: str) -> str | None:
    if _CONTEXT_PREFIX not in user_prompt or _CONTEXT_SUFFIX not in user_prompt:
        return None
    return user_prompt.split(_CONTEXT_PREFIX, 1)[1].split(_CONTEXT_SUFFIX, 1)[0]


def _event_payload(span: SpanRow, event_name: str) -> Any:
    for event in span.events or []:
        if event.get("name") != event_name:
            continue
        attributes = event.get("attributes") or {}
        payload = attributes.get("payload")
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return payload
        return payload
    return None


def _pairs(items: Any) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in items or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            pairs.append((str(item[0]), str(item[1])))
    return pairs
