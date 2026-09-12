from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from pathlib import Path

from sqlalchemy import delete, func, select, tuple_, update
from sqlalchemy.orm import aliased

from core.enums import NodeType
from core.exceptions import NotFoundError
from db.base import get_sessionmaker
from db.models import DataRelationRow, EdgeRow, GraphRow, NodeRow
from repository.graph_repository.models import (
    GraphMutationPlan,
    GraphSnapshot,
    GraphSummary,
    Node,
    PrefetchInsertionContext,
)

logger = logging.getLogger(__name__)

DEFAULT_SEED_JSON_PATH = Path(__file__).resolve().parents[2] / "data" / "graph.json"


def _to_domain_node(row: NodeRow) -> Node:
    return Node(
        node_id=row.node_id,
        label=row.label,
        node_type=row.node_type,
        description=row.description,
        raw_text=row.raw_text,
        metadata=row.node_metadata,
    )

class GraphRepository:

    @staticmethod
    def _generate_id() -> uuid.UUID:
        """Single point of control for every surrogate id this repository mints —
        change the scheme (e.g. a different uuid version, ULIDs) here only."""
        return uuid.uuid4()

    @staticmethod
    def _build_empty_graph_rows(
        graph_id: uuid.UUID, name: str,
    ) -> tuple[GraphRow, list[NodeRow], list[EdgeRow], list[DataRelationRow]]:
        graph_row = GraphRow(id=graph_id, name=name, context="")
        central_row = NodeRow(
            id=GraphRepository._generate_id(), graph_id=graph_id,
            node_id=f"central_{GraphRepository._generate_id().hex[:8]}",
            label="Central", node_type=NodeType.CENTRAL,
        )
        return graph_row, [central_row], [], []

    @staticmethod
    def _build_seeded_graph_rows(
        graph_id: uuid.UUID, name: str, json_path: str | Path,
    ) -> tuple[GraphRow, list[NodeRow], list[EdgeRow], list[DataRelationRow]]:
        with open(json_path) as f:
            data = json.load(f)

        node_row_id_by_node_id: dict[str, uuid.UUID] = {}
        node_rows = []
        for n in data["nodes"]:
            row_id = GraphRepository._generate_id()
            node_row_id_by_node_id[n["node_id"]] = row_id
            node_rows.append(NodeRow(
                id=row_id, graph_id=graph_id, node_id=n["node_id"], label=n["label"],
                node_type=NodeType(n["node_type"]), description=n.get("description"),
                raw_text=n.get("raw_text"), node_metadata=n.get("metadata", {}),
            ))

        edge_rows = [
            EdgeRow(
                graph_id=graph_id,
                source_id=node_row_id_by_node_id[e["source_id"]],
                target_id=node_row_id_by_node_id[e["target_id"]],
            )
            for e in data.get("edges", [])
        ]
        data_relation_rows = [
            DataRelationRow(
                graph_id=graph_id,
                source_id=node_row_id_by_node_id[r["source_id"]],
                target_id=node_row_id_by_node_id[r["target_id"]],
            )
            for r in data.get("data_relations", [])
        ]

        graph_row = GraphRow(id=graph_id, name=name, context=data.get("context", ""))
        return graph_row, node_rows, edge_rows, data_relation_rows

    @staticmethod
    async def create_graph(name: str) -> uuid.UUID:
        """Creates a new, empty graph seeded with a single central node."""
        graph_id = GraphRepository._generate_id()
        graph_row, node_rows, edge_rows, relation_rows = GraphRepository._build_empty_graph_rows(
            graph_id, name,
        )
        async with get_sessionmaker()() as session:
            session.add(graph_row)
            session.add_all(node_rows)
            await session.commit()
        return graph_id

    @staticmethod
    async def seed_from_json(name: str, json_path: str | Path = DEFAULT_SEED_JSON_PATH) -> uuid.UUID:
        """Bulk-loads a graph.json snapshot (the old in-memory Graph's serialization
        format) into a brand-new graph row. Used to bootstrap demo/seed data."""
        graph_id = GraphRepository._generate_id()
        graph_row, node_rows, edge_rows, relation_rows = GraphRepository._build_seeded_graph_rows(
            graph_id, name, json_path,
        )
        async with get_sessionmaker()() as session:
            session.add(graph_row)
            session.add_all(node_rows)
            await session.flush()
            session.add_all([*edge_rows, *relation_rows])
            await session.commit()
        return graph_id

    @staticmethod
    async def reset_graph(graph_id: uuid.UUID, name: str, *, reseed_from_json: bool) -> uuid.UUID:
        """Atomically replaces a graph with a fresh one under the same name, in ONE
        transaction. Delete-then-recreate as two separate calls can be interrupted
        in between (a crash, a reload) and leave zero graphs with this name — this
        can't, since nothing commits until both the delete and the insert succeed."""
        new_graph_id = GraphRepository._generate_id()
        graph_row, node_rows, edge_rows, relation_rows = (
            GraphRepository._build_seeded_graph_rows(new_graph_id, name, DEFAULT_SEED_JSON_PATH)
            if reseed_from_json
            else GraphRepository._build_empty_graph_rows(new_graph_id, name)
        )

        async with get_sessionmaker()() as session:
            await session.execute(delete(GraphRow).where(GraphRow.id == graph_id))
            session.add(graph_row)
            session.add_all(node_rows)
            await session.flush()
            session.add_all([*edge_rows, *relation_rows])
            await session.commit()

        return new_graph_id

    @staticmethod
    async def delete_graph(graph_id: uuid.UUID) -> None:
        """Deletes a graph and (via FK cascade) all of its nodes/edges/data_relations."""
        async with get_sessionmaker()() as session:
            await session.execute(delete(GraphRow).where(GraphRow.id == graph_id))
            await session.commit()

    @staticmethod
    async def get_graph_id_by_name(name: str) -> uuid.UUID | None:
        async with get_sessionmaker()() as session:
            result = await session.execute(select(GraphRow.id).where(GraphRow.name == name))
            return result.scalar_one_or_none()

    @staticmethod
    async def get_graph_name(graph_id: uuid.UUID) -> str | None:
        async with get_sessionmaker()() as session:
            result = await session.execute(select(GraphRow.name).where(GraphRow.id == graph_id))
            return result.scalar_one_or_none()

    @staticmethod
    async def list_graphs() -> list[GraphSummary]:
        """One bulk query (graphs LEFT JOIN nodes, grouped) for the whole switcher list —
        never one node-count query per graph."""
        async with get_sessionmaker()() as session:
            result = await session.execute(
                select(GraphRow.id, GraphRow.name, func.count(NodeRow.id))
                .select_from(GraphRow)
                .join(NodeRow, NodeRow.graph_id == GraphRow.id, isouter=True)
                .group_by(GraphRow.id, GraphRow.name)
                .order_by(GraphRow.created_at)
            )
            return [
                GraphSummary(id=graph_id, name=name, node_count=node_count)
                for graph_id, name, node_count in result.all()
            ]

    @staticmethod
    async def get_central_node(graph_id: uuid.UUID) -> Node:
        async with get_sessionmaker()() as session:
            result = await session.execute(
                select(NodeRow).where(
                    NodeRow.graph_id == graph_id, NodeRow.node_type == NodeType.CENTRAL,
                )
            )
            row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"Graph {graph_id} has no central node")
        return _to_domain_node(row)

    @staticmethod
    async def get_graph_context(graph_id: uuid.UUID) -> str:
        async with get_sessionmaker()() as session:
            result = await session.execute(select(GraphRow.context).where(GraphRow.id == graph_id))
            context = result.scalar_one_or_none()
        return context or ""

    @staticmethod
    async def update_graph_context(graph_id: uuid.UUID, new_context: str) -> None:
        async with get_sessionmaker()() as session:
            await session.execute(
                update(GraphRow).where(GraphRow.id == graph_id).values(context=new_context)
            )
            await session.commit()

    @staticmethod
    async def get_node(graph_id: uuid.UUID, node_id: str) -> Node | None:
        async with get_sessionmaker()() as session:
            result = await session.execute(
                select(NodeRow).where(NodeRow.graph_id == graph_id, NodeRow.node_id == node_id)
            )
            row = result.scalar_one_or_none()
        return _to_domain_node(row) if row is not None else None

    @staticmethod
    async def get_nodes_batch(graph_id: uuid.UUID, node_ids: list[str]) -> dict[str, Node]:
        if not node_ids:
            return {}
        async with get_sessionmaker()() as session:
            result = await session.execute(
                select(NodeRow).where(NodeRow.graph_id == graph_id, NodeRow.node_id.in_(node_ids))
            )
            rows = result.scalars().all()
        return {row.node_id: _to_domain_node(row) for row in rows}

    @staticmethod
    async def get_children_batch(
        graph_id: uuid.UUID, parent_node_ids: list[str],
    ) -> dict[str, list[Node]]:
        """One bulk join for every parent's children at once — the core traversal
        primitive both retrieval BFS and insertion-point search page through level by level."""
        if not parent_node_ids:
            return {}
        parent_alias = aliased(NodeRow)
        child_alias = aliased(NodeRow)
        async with get_sessionmaker()() as session:
            result = await session.execute(
                select(parent_alias.node_id, child_alias)
                .select_from(EdgeRow)
                .join(parent_alias, EdgeRow.source_id == parent_alias.id)
                .join(child_alias, EdgeRow.target_id == child_alias.id)
                .where(EdgeRow.graph_id == graph_id, parent_alias.node_id.in_(parent_node_ids))
            )
            rows = result.all()

        children_by_parent_node_id: dict[str, list[Node]] = defaultdict(list)
        for parent_node_id, child_row in rows:
            children_by_parent_node_id[parent_node_id].append(_to_domain_node(child_row))
        return dict(children_by_parent_node_id)

    @staticmethod
    async def get_parents_batch(
        graph_id: uuid.UUID, node_ids: list[str],
    ) -> dict[str, list[Node]]:
        if not node_ids:
            return {}
        child_alias = aliased(NodeRow)
        parent_alias = aliased(NodeRow)
        async with get_sessionmaker()() as session:
            result = await session.execute(
                select(child_alias.node_id, parent_alias)
                .select_from(EdgeRow)
                .join(child_alias, EdgeRow.target_id == child_alias.id)
                .join(parent_alias, EdgeRow.source_id == parent_alias.id)
                .where(EdgeRow.graph_id == graph_id, child_alias.node_id.in_(node_ids))
            )
            rows = result.all()

        parents_by_child_node_id: dict[str, list[Node]] = defaultdict(list)
        for child_node_id, parent_row in rows:
            parents_by_child_node_id[child_node_id].append(_to_domain_node(parent_row))
        return dict(parents_by_child_node_id)

    @staticmethod
    async def get_node_ids_with_children(
        graph_id: uuid.UUID, node_ids: list[str],
    ) -> set[str]:
        """Bulk existence-of-children check for a candidate set of node ids —
        used to filter out leaf nodes from a BFS frontier without a call per node."""
        if not node_ids:
            return set()
        parent_alias = aliased(NodeRow)
        async with get_sessionmaker()() as session:
            result = await session.execute(
                select(parent_alias.node_id)
                .distinct()
                .select_from(EdgeRow)
                .join(parent_alias, EdgeRow.source_id == parent_alias.id)
                .where(EdgeRow.graph_id == graph_id, parent_alias.node_id.in_(node_ids))
            )
            return set(result.scalars().all())

    @staticmethod
    async def prefetch_insertion_context(
        graph_id: uuid.UUID, insertion_point_ids: list[str],
    ) -> PrefetchInsertionContext:
        """Single-pass bulk prefetch of everything `insert_new_node` needs: the
        insertion points, their parents, their children, and grandchildren of any
        category children — 4 bulk queries total regardless of how many insertion
        points there are (mirrors the old in-memory Graph.prefetch_context_for_insertion)."""
        if not insertion_point_ids:
            return PrefetchInsertionContext()

        nodes: dict[str, Node] = {}
        children_map: dict[str, list[Node]] = defaultdict(list)
        parents_map: dict[str, list[Node]] = defaultdict(list)

        parent_alias = aliased(NodeRow)
        child_alias = aliased(NodeRow)

        async with get_sessionmaker()() as session:
            # 1. the insertion points themselves
            result = await session.execute(
                select(NodeRow).where(
                    NodeRow.graph_id == graph_id, NodeRow.node_id.in_(insertion_point_ids),
                )
            )
            for row in result.scalars():
                nodes[row.node_id] = _to_domain_node(row)

            # 2. their parents
            result = await session.execute(
                select(child_alias.node_id, parent_alias)
                .select_from(EdgeRow)
                .join(child_alias, EdgeRow.target_id == child_alias.id)
                .join(parent_alias, EdgeRow.source_id == parent_alias.id)
                .where(EdgeRow.graph_id == graph_id, child_alias.node_id.in_(insertion_point_ids))
            )
            for child_node_id, parent_row in result.all():
                parent_node = nodes.setdefault(parent_row.node_id, _to_domain_node(parent_row))
                parents_map[child_node_id].append(parent_node)

            relevant_node_ids = list(nodes.keys())  # insertion points ∪ their parents

            # 3. children of everything relevant so far
            result = await session.execute(
                select(parent_alias.node_id, child_alias)
                .select_from(EdgeRow)
                .join(parent_alias, EdgeRow.source_id == parent_alias.id)
                .join(child_alias, EdgeRow.target_id == child_alias.id)
                .where(EdgeRow.graph_id == graph_id, parent_alias.node_id.in_(relevant_node_ids))
            )
            category_child_node_ids: list[str] = []
            for parent_node_id, child_row in result.all():
                child_node = nodes.setdefault(child_row.node_id, _to_domain_node(child_row))
                children_map[parent_node_id].append(child_node)
                if child_node.node_type == NodeType.CATEGORY:
                    category_child_node_ids.append(child_row.node_id)

            # 4. grandchildren — children of any category child found in step 3
            if category_child_node_ids:
                result = await session.execute(
                    select(parent_alias.node_id, child_alias)
                    .select_from(EdgeRow)
                    .join(parent_alias, EdgeRow.source_id == parent_alias.id)
                    .join(child_alias, EdgeRow.target_id == child_alias.id)
                    .where(
                        EdgeRow.graph_id == graph_id,
                        parent_alias.node_id.in_(category_child_node_ids),
                    )
                )
                for parent_node_id, grandchild_row in result.all():
                    grandchild_node = nodes.setdefault(
                        grandchild_row.node_id, _to_domain_node(grandchild_row),
                    )
                    children_map[parent_node_id].append(grandchild_node)

        return PrefetchInsertionContext(
            nodes=nodes,
            children_map=dict(children_map),
            parents_map=dict(parents_map),
        )

    @staticmethod
    async def get_full_graph(graph_id: uuid.UUID) -> GraphSnapshot:
        async with get_sessionmaker()() as session:
            graph_row = await session.get(GraphRow, graph_id)
            if graph_row is None:
                raise NotFoundError(f"Graph {graph_id} not found")

            node_rows = (await session.execute(
                select(NodeRow).where(NodeRow.graph_id == graph_id)
            )).scalars().all()
            node_id_by_row_id = {row.id: row.node_id for row in node_rows}
            central_id = next(row.node_id for row in node_rows if row.node_type == NodeType.CENTRAL)

            edge_rows = (await session.execute(
                select(EdgeRow.source_id, EdgeRow.target_id).where(EdgeRow.graph_id == graph_id)
            )).all()
            relation_rows = (await session.execute(
                select(DataRelationRow.source_id, DataRelationRow.target_id)
                .where(DataRelationRow.graph_id == graph_id)
            )).all()

            return GraphSnapshot(
                graph_id=graph_row.id,
                name=graph_row.name,
                context=graph_row.context or "",
                central_id=central_id,
                nodes=[_to_domain_node(row) for row in node_rows],
                edges=[
                    {"source_id": node_id_by_row_id[s], "target_id": node_id_by_row_id[t]}
                    for s, t in edge_rows
                ],
                data_relations=[
                    {"source_id": node_id_by_row_id[s], "target_id": node_id_by_row_id[t]}
                    for s, t in relation_rows
                ],
            )

    @staticmethod
    async def apply_mutations(graph_id: uuid.UUID, plan: GraphMutationPlan) -> None:
        """Applies a fully-resolved GraphMutationPlan in one transaction: a handful
        of batched INSERT/UPDATE/DELETE statements, never one call per node/edge."""
        if not any([
            plan.nodes_to_add, plan.label_updates, plan.edges_to_add,
            plan.edges_to_remove, plan.node_ids_to_remove, plan.data_relations_to_add,
        ]):
            return

        referenced_node_ids = {
            node_id
            for source_id, target_id in (
                *plan.edges_to_add, *plan.edges_to_remove, *plan.data_relations_to_add,
            )
            for node_id in (source_id, target_id)
        } | {update_.node_id for update_ in plan.label_updates}

        async with get_sessionmaker()() as session:
            row_id_by_node_id: dict[str, uuid.UUID] = {}
            if referenced_node_ids:
                result = await session.execute(
                    select(NodeRow.node_id, NodeRow.id).where(
                        NodeRow.graph_id == graph_id, NodeRow.node_id.in_(referenced_node_ids),
                    )
                )
                row_id_by_node_id = dict(result.all())

            new_node_rows = [
                NodeRow(
                    id=GraphRepository._generate_id(), graph_id=graph_id, node_id=node.node_id, label=node.label,
                    node_type=node.node_type, description=node.description,
                    raw_text=node.raw_text, node_metadata=node.metadata,
                )
                for node in plan.nodes_to_add
            ]
            if new_node_rows:
                session.add_all(new_node_rows)
                await session.flush()
                for row in new_node_rows:
                    row_id_by_node_id[row.node_id] = row.id

            if plan.label_updates:
                update_params = [
                    {"id": row_id_by_node_id[u.node_id], "label": u.label, "description": u.description}
                    for u in plan.label_updates
                    if u.node_id in row_id_by_node_id
                ]
                if update_params:
                    await session.execute(update(NodeRow), update_params)

            if plan.edges_to_remove:
                edge_row_id_pairs = [
                    (row_id_by_node_id[s], row_id_by_node_id[t])
                    for s, t in plan.edges_to_remove
                    if s in row_id_by_node_id and t in row_id_by_node_id
                ]
                if edge_row_id_pairs:
                    await session.execute(
                        delete(EdgeRow).where(
                            EdgeRow.graph_id == graph_id,
                            tuple_(EdgeRow.source_id, EdgeRow.target_id).in_(edge_row_id_pairs),
                        )
                    )

            if plan.edges_to_add:
                session.add_all([
                    EdgeRow(graph_id=graph_id, source_id=row_id_by_node_id[s], target_id=row_id_by_node_id[t])
                    for s, t in plan.edges_to_add
                    if s in row_id_by_node_id and t in row_id_by_node_id
                ])

            if plan.data_relations_to_add:
                session.add_all([
                    DataRelationRow(
                        graph_id=graph_id, source_id=row_id_by_node_id[s], target_id=row_id_by_node_id[t],
                    )
                    for s, t in plan.data_relations_to_add
                    if s in row_id_by_node_id and t in row_id_by_node_id
                ])

            if plan.node_ids_to_remove:
                row_ids_to_remove = [
                    row_id_by_node_id[node_id]
                    for node_id in plan.node_ids_to_remove
                    if node_id in row_id_by_node_id
                ]
                if row_ids_to_remove:
                    # FK cascade (nodes -> edges/data_relations) cleans up any
                    # remaining references automatically.
                    await session.execute(delete(NodeRow).where(NodeRow.id.in_(row_ids_to_remove)))

            await session.commit()
