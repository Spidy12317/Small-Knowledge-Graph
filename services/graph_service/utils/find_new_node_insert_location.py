from __future__ import annotations

import math
import asyncio
import logging
import uuid
from typing import List

from core import constants, configs, enums

import services
from core.tracing import traced
from repository import GraphRepository
from services.graph_service import models, utils

logger = logging.getLogger(__name__)

graph_settings = configs.get_graph_settings()

MAX_CONCURRENT_EVALUATIONS = graph_settings.GRAPH_MAX_CONCURRENT_EVALUATIONS
DATA_BATCH_SIZE = graph_settings.GRAPH_MAX_NODE_CHILDREN


@traced
async def find_insert_location(
    chunk: str,
    graph_id: uuid.UUID,
    llm: services.LLMService,
    chunk_context: str = "",
) -> List[models.CandidateNode]:
    potential_parent_nodes: List[models.CandidateNode] = []
    seen_nodes: set[str] = set()

    # Rolling window of data nodes — trimmed as full batches are dispatched to LLM
    data_nodes_awaiting_batch_scoring: List[models.CandidateNode] = []
    # Complete record of every data node encountered with its parent context — never trimmed, used at end
    all_collected_data_nodes_with_parent: List[tuple[models.CandidateNode, models.CandidateNode]] = []
    # All data LLM scoring results accumulated in order — processed together after the loop
    all_data_llm_scoring_results: List[dict] = []

    central_node = await GraphRepository.get_central_node(graph_id)
    nodes_queue: List[models.CandidateNode] = [
        models.CandidateNode(
            node=central_node,
            node_id=central_node.node_id,
            node_type=enums.NodeType.CENTRAL,
            path_to_node=[[central_node]]
        )
    ]

    while nodes_queue:
        # Step 1: Pop the next batch from the frontier
        current_batch = nodes_queue[:MAX_CONCURRENT_EVALUATIONS]
        nodes_queue = nodes_queue[MAX_CONCURRENT_EVALUATIONS:]

        # Step 2: Gather and categorize all child nodes for the current batch
        children_nodes = await _fetch_children_nodes(current_batch, graph_id)

        # Record all new data nodes with their parent context immediately — children_nodes already has them
        for parent_node in current_batch:
            for data_child in children_nodes.get(parent_node.node_id, {}).get('data_nodes', []):
                all_collected_data_nodes_with_parent.append((data_child, parent_node))

        # Step 3: Build category scoring tasks and any ready data scoring tasks.
        parents_with_category_children, category_tasks, data_tasks = _build_traversal_tasks_for_insertion_point(
            current_batch, children_nodes, data_nodes_awaiting_batch_scoring, chunk, llm, chunk_context=chunk_context)

        # Step 4: Concurrently run category and data scoring tasks
        category_results, data_results = await asyncio.gather(
            asyncio.gather(*category_tasks),
            asyncio.gather(*data_tasks),
        )

        # Store data scoring results for post-loop processing
        all_data_llm_scoring_results.extend(data_results)
        # Trim the dispatched data nodes from the rolling window
        number_of_data_nodes_dispatched_this_iteration = len(data_results) * DATA_BATCH_SIZE
        data_nodes_awaiting_batch_scoring = data_nodes_awaiting_batch_scoring[number_of_data_nodes_dispatched_this_iteration:]

        # Step 5: Identify category-level insertion points (leaf categories only — no data children)
        _identify_category_insertion_points(
            current_batch, parents_with_category_children, children_nodes, category_results,
            nodes_queue, seen_nodes, potential_parent_nodes,
        )

    # Step 6: Flush any remaining data nodes that didn't fill a full batch during the loop
    if data_nodes_awaiting_batch_scoring:
        flush_tasks = _build_data_node_traversal_tasks_for_insertion_point(
            data_nodes_awaiting_batch_scoring, chunk, llm, include_remainder=True, chunk_context=chunk_context)
        flush_results = await asyncio.gather(*flush_tasks)
        all_data_llm_scoring_results.extend(flush_results)

    # Step 7: Process all accumulated data scoring results grouped by parent to find insertion points
    if all_collected_data_nodes_with_parent:
        _identify_data_insertion_points(
            all_collected_data_nodes_with_parent, all_data_llm_scoring_results,
            seen_nodes, potential_parent_nodes,
        )

    return potential_parent_nodes


async def _fetch_children_nodes(
    batch: list[models.CandidateNode],
    graph_id: uuid.UUID,
) -> dict[str, dict[str, list[models.CandidateNode]]]:

    children_nodes_dict: dict[str, list[models.Node]] = await GraphRepository.get_children_batch(
        graph_id, [node.node_id for node in batch]
    )

    zip_candidate_nodes: list[tuple[models.CandidateNode, list[models.Node]]] = [
        (node, children_nodes_dict.get(node.node_id, []))
        for node in batch
    ]

    grouped_children: dict[str, dict[str, list[models.CandidateNode]]] = {}

    for parent_node, children in zip_candidate_nodes:

        category_nodes: list[models.CandidateNode] = []
        data_nodes: list[models.CandidateNode] = []

        for child in children:
            candidate = models.CandidateNode(
                node=child,
                node_id=child.node_id,
                node_type=child.node_type,
                path_to_node=[path + [child] for path in parent_node.path_to_node],
            )
            match child.node_type:
                case enums.NodeType.CATEGORY:
                    category_nodes.append(candidate)
                case enums.NodeType.DATA:
                    data_nodes.append(candidate)

        grouped_children[parent_node.node_id] = {
            "category_nodes": category_nodes,
            "data_nodes": data_nodes,
        }

    return grouped_children


def _build_candidate_nodes_text(candidates: List[models.CandidateNode]) -> str:
    text: str = ""
    for candidate in candidates:
        text += f"  - node_id={candidate.node_id!r}, label={candidate.node.label!r}"
        if candidate.node.description:
            text += f", description={candidate.node.description!r}"
        if candidate.node.raw_text:
            text += f", content={candidate.node.raw_text!r}"
        text += "\n"
    return text


def _build_category_node_traversal_tasks_for_insertion_point(
    current_batch: List[models.CandidateNode],
    children_nodes: dict[str, dict[str, List[models.CandidateNode]]],
    chunk: str,
    llm: services.LLMService,
    chunk_context: str = "",
) -> tuple[List[models.CandidateNode], list]:
    parents_with_category_children: List[models.CandidateNode] = []
    category_tasks: list = []

    for parent_node in current_batch:
        children_of_parent = children_nodes.get(parent_node.node_id, {})
        category_children_of_parent: List[models.CandidateNode] = []
        if children_of_parent:
            category_children_of_parent = children_of_parent['category_nodes']

        if not category_children_of_parent:
            continue

        children_text: str = _build_candidate_nodes_text(category_children_of_parent)

        sys_msg, user_prompt = constants.Prompts.score_category_node_for_insertion(
            chunk=chunk,
            current_label=parent_node.node.label,
            current_type=parent_node.node_type,
            children_text=children_text,
            chunk_context=chunk_context,
            llm_provider=llm.provider,
        )

        task = asyncio.create_task(
            utils.invoke_llm_and_parse_json(sys_msg, user_prompt, llm))
        parents_with_category_children.append(parent_node)
        category_tasks.append(task)

    return parents_with_category_children, category_tasks


def _build_data_node_traversal_tasks_for_insertion_point(
    batch_data_nodes: List[models.CandidateNode],
    chunk: str,
    llm: services.LLMService,
    include_remainder: bool = False,
    chunk_context: str = "",
) -> list:
    data_tasks: list = []

    num_batches = math.ceil(len(
        batch_data_nodes) / DATA_BATCH_SIZE) if include_remainder else len(batch_data_nodes) // DATA_BATCH_SIZE

    for i in range(num_batches):
        data_batch: List[models.CandidateNode] = batch_data_nodes[i * DATA_BATCH_SIZE: (i + 1) * DATA_BATCH_SIZE]

        data_children_text: str = _build_candidate_nodes_text(data_batch)

        sys_msg, user_prompt = constants.Prompts.score_data_node_for_insertion(
            chunk=chunk,
            children_text=data_children_text,
            chunk_context=chunk_context,
            llm_provider=llm.provider,
        )

        task = asyncio.create_task(
            utils.invoke_llm_and_parse_json(sys_msg, user_prompt, llm))
        data_tasks.append(task)

    return data_tasks


def _build_traversal_tasks_for_insertion_point(
    current_batch: List[models.CandidateNode],
    children_nodes: dict[str, dict[str, List[models.CandidateNode]]],
    data_nodes_awaiting_batch_scoring: List[models.CandidateNode],
    chunk: str,
    llm: services.LLMService,
    chunk_context: str = "",
) -> tuple[List[models.CandidateNode], list, list]:
    for _, children in children_nodes.items():
        data_nodes_awaiting_batch_scoring.extend(children['data_nodes'])

    parents_with_category_children, category_tasks = _build_category_node_traversal_tasks_for_insertion_point(
        current_batch, children_nodes, chunk, llm, chunk_context=chunk_context,
    )

    if len(data_nodes_awaiting_batch_scoring) < DATA_BATCH_SIZE:
        return parents_with_category_children, category_tasks, []

    data_tasks = _build_data_node_traversal_tasks_for_insertion_point(
        data_nodes_awaiting_batch_scoring, chunk, llm, chunk_context=chunk_context,
    )
    return parents_with_category_children, category_tasks, data_tasks


def _identify_category_insertion_points(
    current_batch: List[models.CandidateNode],
    parents_with_category_children: List[models.CandidateNode],
    children_nodes: dict[str, dict[str, List[models.CandidateNode]]],
    category_results: tuple,
    nodes_queue: List[models.CandidateNode],
    seen_nodes: set[str],
    potential_parent_nodes: List[models.CandidateNode],
) -> None:
    for parent_node, result in zip(parents_with_category_children, category_results):
        children_of_parent = children_nodes.get(parent_node.node_id, {})
        category_children_of_parent: List[models.CandidateNode] = children_of_parent.get('category_nodes', [])

        for category_child in category_children_of_parent:
            child_result = result.get(category_child.node_id, {})

            if not child_result:
                continue
            if float(child_result.get("score", 0)) == 0:
                continue
            if category_child.node_id in seen_nodes:
                continue

            nodes_queue.append(category_child._replace(reasoning=child_result.get("reasoning", "")))
            seen_nodes.add(parent_node.node_id)

    # A parent with no positively scored category children and no data children is itself the insertion point
    for parent_node in current_batch:
        if parent_node.node_id in seen_nodes:
            continue

        data_children_of_parent = children_nodes.get(parent_node.node_id, {}).get('data_nodes', [])
        if not data_children_of_parent:
            seen_nodes.add(parent_node.node_id)
            potential_parent_nodes.append(parent_node)


def _identify_data_insertion_points(
    all_collected_data_nodes_with_parent: List[tuple[models.CandidateNode, models.CandidateNode]],
    all_data_llm_scoring_results: List[dict],
    seen_nodes: set[str],
    potential_parent_nodes: List[models.CandidateNode],
) -> None:
    all_data_node_scores_by_node_id: dict[str, dict] = {}
    for scoring_result in all_data_llm_scoring_results:
        all_data_node_scores_by_node_id.update(scoring_result)

    data_children_grouped_by_parent_id: dict[str, list[models.CandidateNode]] = {}
    parent_candidate_node_by_id: dict[str, models.CandidateNode] = {}
    for data_node, parent_node in all_collected_data_nodes_with_parent:
        parent_candidate_node_by_id[parent_node.node_id] = parent_node
        data_children_grouped_by_parent_id.setdefault(parent_node.node_id, []).append(data_node)

    for parent_id, data_children_of_parent in data_children_grouped_by_parent_id.items():
        if parent_id in seen_nodes:
            continue

        found_matching_data_child_node = False
        for data_child in data_children_of_parent:
            child_result = all_data_node_scores_by_node_id.get(data_child.node_id, {})

            if not child_result:
                continue

            if float(child_result.get("score", 0)) == 0:
                continue

            if data_child.node_id in seen_nodes:
                continue

            seen_nodes.add(data_child.node_id)
            potential_parent_nodes.append(data_child._replace(reasoning=child_result.get("reasoning", "")))
            found_matching_data_child_node = True

        if not found_matching_data_child_node:
            seen_nodes.add(parent_id)
            potential_parent_nodes.append(parent_candidate_node_by_id[parent_id])
