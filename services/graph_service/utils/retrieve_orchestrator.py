from __future__ import annotations

import asyncio
import logging
import uuid
from typing import List

from core import constants, configs, enums
import services
from repository import GraphRepository
from services.graph_service import models, utils

logger = logging.getLogger(__name__)

graph_settings = configs.get_graph_settings()

MAX_CONCURRENT_EVALUATIONS = graph_settings.GRAPH_MAX_CONCURRENT_EVALUATIONS
HIGH_CONFIDENCE_SCORE_THRESHOLD = graph_settings.GRAPH_HIGH_CONFIDENCE_SCORE_THRESHOLD


async def retrieve(
    query: str,
    graph_id: uuid.UUID,
    llm: services.LLMService,
) -> List[models.CandidateNode]:
    accumulated_nodes: List[models.CandidateNode] = []
    restrict_to_high_confidence = False
    central_node = await GraphRepository.get_central_node(graph_id)
    nodes_queue: List[models.CandidateNode] = [
        models.CandidateNode(
            node=central_node,
            node_id=central_node.node_id,
            node_type=enums.NodeType.CENTRAL,
            path_to_node=[[central_node]],
        )
    ]

    while nodes_queue:
        # Step 1: Pop the next batch from the frontier
        current_batch = nodes_queue[:MAX_CONCURRENT_EVALUATIONS]
        nodes_queue = nodes_queue[MAX_CONCURRENT_EVALUATIONS:]

        # Step 2: Fetch children for each candidate node in the batch — one bulk query
        children_map: dict[str, list[models.Node]] = await GraphRepository.get_children_batch(
            graph_id, [c.node_id for c in current_batch]
        )

        # Step 3: Build LLM evaluation tasks for each candidate node
        tasks = _build_traversal_tasks(current_batch, children_map, query, llm)

        # Step 4: Concurrently run traversal tasks
        evaluations: list[dict] = list(await asyncio.gather(*tasks))

        # Step 5: Collect retrieved nodes and queue next candidates from evaluation scores
        await _collect_retrieved_nodes(current_batch, evaluations, children_map, accumulated_nodes, graph_id)

        nodes_queue, restrict_to_high_confidence = await _queue_next_nodes(
            nodes_queue=nodes_queue,
            evaluations=evaluations,
            children_map=children_map,
            current_batch=current_batch,
            graph_id=graph_id,
            restrict_to_high_confidence=restrict_to_high_confidence,
            confidence_threshold=HIGH_CONFIDENCE_SCORE_THRESHOLD,
        )

    return accumulated_nodes


def _build_traversal_tasks(
    batch: List[models.CandidateNode],
    children_map: dict[str, list[models.Node]],
    query: str,
    llm: services.LLMService,
) -> list:
    tasks = []
    for candidate in batch:
        children = children_map[candidate.node_id]

        formatted_children = []
        for child in children:
            child_fields = [
                f"node_id={child.node_id!r}",
                f"label={child.label!r}",
                f"type={child.node_type}",
            ]
            if child.description:
                child_fields.append(f"description={child.description!r}")
            if child.raw_text and child.node_type == enums.NodeType.DATA:
                child_fields.append(f"content={child.raw_text!r}")
            formatted_children.append("  - " + ", ".join(child_fields))

        sys_msg, user_prompt = constants.Prompts.graph_navigation(
            query=query,
            current_label=candidate.node.label,
            current_type=candidate.node_type,
            children_text="\n".join(formatted_children),
            llm_provider=llm.provider,
        )
        task = asyncio.create_task(utils.invoke_llm_and_parse_json(sys_msg, user_prompt, llm))
        tasks.append(task)

    return tasks


async def _collect_retrieved_nodes(
    current_batch: List[models.CandidateNode],
    evaluations: list[dict],
    children_map: dict[str, list[models.Node]],
    accumulated_nodes: List[models.CandidateNode],
    graph_id: uuid.UUID,
) -> None:
    seen_ids = {n.node_id for n in accumulated_nodes}
    for parent, evaluation in zip(current_batch, evaluations):

        reasoning = evaluation.get("reasoning", "")
        retrieved_ids = evaluation.get("retrieved_ids", [])
        if not retrieved_ids:
            continue

        children_by_id = {child.node_id: child for child in children_map.get(parent.node_id, [])}
        for node_id in retrieved_ids:
            if node_id in seen_ids:
                continue
            # Normal path: the LLM chose one of the children we offered it — no DB call.
            # Fallback path (should be rare): the LLM returned some other node id, so
            # verify it actually exists with a single lookup rather than trusting it blindly.
            node = children_by_id.get(node_id)
            if node is None:
                node = await GraphRepository.get_node(graph_id, node_id)
            if node is None:
                continue
            seen_ids.add(node_id)
            accumulated_nodes.append(models.CandidateNode(
                node=node,
                node_id=node_id,
                node_type=enums.NodeType(node.node_type),
                path_to_node=[path + [node] for path in parent.path_to_node],
                reasoning=reasoning,
            ))


def _fetch_candidate_nodes(
    child_nodes: list[models.Node],
    node_scores: dict[str, float],
    parent_path: list[list[models.Node]],
    node_ids_with_children: set[str],
    high_confidence_only: bool,
    confidence_threshold: float,
) -> List[models.CandidateNode]:
    scored = []
    for child in child_nodes:
        score = node_scores.get(child.node_id, 0)
        if child.node_id not in node_ids_with_children:
            continue
        if score == 0:
            continue
        if high_confidence_only and score < confidence_threshold:
            continue
        scored.append((score, child))
    scored.sort(key=lambda x: -x[0])
    return [
        models.CandidateNode(
            node=child,
            node_id=child.node_id,
            node_type=enums.NodeType(child.node_type),
            path_to_node=[path + [child] for path in parent_path],
        )
        for _, child in scored
    ]


async def _queue_next_nodes(
    nodes_queue: List[models.CandidateNode],
    evaluations: list[dict],
    children_map: dict[str, list[models.Node]],
    current_batch: List[models.CandidateNode],
    graph_id: uuid.UUID,
    restrict_to_high_confidence: bool,
    confidence_threshold: float,
) -> tuple[List[models.CandidateNode], bool]:
    restrict_to_high_confidence = restrict_to_high_confidence or any(e.get("done") for e in evaluations)

    # One bulk "which of these candidates have children" check for the whole level,
    # instead of asking the database once per candidate node.
    all_child_node_ids = [child.node_id for children in children_map.values() for child in children]
    node_ids_with_children = await GraphRepository.get_node_ids_with_children(graph_id, all_child_node_ids)

    parent_node_by_node_id = {c.node_id: c.node for c in current_batch}
    for evaluation, (node_id, children) in zip(evaluations, children_map.items()):
        parent_node = parent_node_by_node_id[node_id]
        nodes_queue.extend(_fetch_candidate_nodes(
            child_nodes=children,
            node_scores=evaluation.get("scores", {}),
            parent_path=[[parent_node]],
            node_ids_with_children=node_ids_with_children,
            high_confidence_only=restrict_to_high_confidence,
            confidence_threshold=confidence_threshold,
        ))
    return nodes_queue, restrict_to_high_confidence
