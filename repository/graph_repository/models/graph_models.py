from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from repository.graph_repository.models.node import Node


class PrefetchInsertionContext(BaseModel):
    """Everything `insert_new_node` needs to plan an insertion, fetched in one bulk pass:
    the insertion points, their parents, their children, and grandchildren of any
    category children — mirrors the old in-memory Graph.prefetch_context_for_insertion."""

    nodes: dict[str, Node] = Field(default_factory=dict)
    children_map: dict[str, list[Node]] = Field(default_factory=dict)
    parents_map: dict[str, list[Node]] = Field(default_factory=dict)


class NodeLabelUpdate(BaseModel):
    node_id: str
    label: str
    description: str | None = None


class GraphMutationPlan(BaseModel):
    """The full set of writes produced by planning a single chunk insertion,
    applied by GraphRepository.apply_mutations in one transaction."""

    nodes_to_add: list[Node] = Field(default_factory=list)
    label_updates: list[NodeLabelUpdate] = Field(default_factory=list)
    edges_to_add: list[tuple[str, str]] = Field(default_factory=list)
    edges_to_remove: list[tuple[str, str]] = Field(default_factory=list)
    node_ids_to_remove: list[str] = Field(default_factory=list)
    data_relations_to_add: list[tuple[str, str]] = Field(default_factory=list)


class GraphSnapshot(BaseModel):
    """Full dump of one graph — nodes, edges, data relations, context — for API reads."""

    graph_id: uuid.UUID
    name: str
    context: str
    central_id: str
    nodes: list[Node] = Field(default_factory=list)
    edges: list[dict[str, str]] = Field(default_factory=list)
    data_relations: list[dict[str, str]] = Field(default_factory=list)


class GraphSummary(BaseModel):
    """One row for a graph switcher — enough to list and pick a graph without
    fetching its full contents."""

    id: uuid.UUID
    name: str
    node_count: int
