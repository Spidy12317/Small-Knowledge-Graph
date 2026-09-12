from __future__ import annotations

import uuid
import asyncio
import logging
from typing import List

from core import constants, configs, enums
import services
from repository import GraphRepository
from repository.graph_repository.models import GraphMutationPlan, NodeLabelUpdate
from services.graph_service import models
from services.graph_service.utils.llm_utils import invoke_llm_and_parse_json

logger = logging.getLogger(__name__)

_NEW_CHUNK_SENTINEL_ID = "00000000-0000-0000-0000-000000000000"

graph_settings = configs.get_graph_settings()
MAX_ROOT_CHILDREN = graph_settings.GRAPH_MAX_ROOT_CHILDREN
MAX_NODE_CHILDREN = graph_settings.GRAPH_MAX_NODE_CHILDREN
MAX_CONCURRENT_INSERTIONS = graph_settings.GRAPH_MAX_CONCURRENT_INSERTIONS


async def insert(
    chunk: str,
    insertion_points: List[models.CandidateNode],
    graph_id: uuid.UUID,
    llm: services.LLMService,
    chunk_context: str = "",
    update_graph: bool = True,
) -> tuple[models.Node, List[dict], List[dict]]:
    # Step 1: classify insertion points by node type
    central_insertion_point, category_insertion_points, data_insertion_points = (
        _classify_insertion_points_by_node_type(insertion_points)
    )

    # Step 2: single bulk prefetch — all nodes, children, and parents needed for the
    # entire operation, plus the central node id, in a fixed handful of queries
    # regardless of how many insertion points there are.
    prefetch, central_node = await asyncio.gather(
        GraphRepository.prefetch_insertion_context(graph_id, [ip.node_id for ip in insertion_points]),
        GraphRepository.get_central_node(graph_id),
    )

    # Step 3: resolve to unique parents (DATA points resolved to their parent via prefetch)
    resolved_parent_nodes = _resolve_parent_nodes(
        central_insertion_point,
        category_insertion_points,
        data_insertion_points,
        prefetch.nodes,
        prefetch.parents_map,
        central_node.node_id,
    )

    # Step 4: concurrently generate the new node label, plan all parent attachments,
    # and refresh the label/description of every non-central resolved parent so it reflects
    # that content related to this chunk now lives beneath it
    concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_INSERTIONS)
    plan_attachment_tasks = [
        asyncio.create_task(
            _determine_attachment_plan_for_parent(parent_node, chunk, prefetch.children_map, llm, concurrency_semaphore, chunk_context=chunk_context)
        )
        for parent_node in resolved_parent_nodes
    ]
    parent_label_description_update_tasks = [
        asyncio.create_task(
            _update_parent_node_label_and_description(parent_node, chunk, llm, concurrency_semaphore, chunk_context=chunk_context)
        )
        for parent_node in resolved_parent_nodes
        if parent_node["node"].node_type != enums.NodeType.CENTRAL
    ]
    generate_new_node_task = asyncio.create_task(_generate_new_data_node(chunk, insertion_points, llm, chunk_context=chunk_context))

    # Gather all results concurrently
    newly_inserted_node, parent_attachment_plans, parent_label_description_updates = await asyncio.gather(
        generate_new_node_task,
        asyncio.gather(*plan_attachment_tasks),
        asyncio.gather(*parent_label_description_update_tasks),
    )

    # Step 5: collect sibling data node IDs that will receive a data_relation to the new node
    sibling_data_node_ids = [dp.node_id for dp in data_insertion_points]

    # Step 6: build the full mutation plan (pure Python — no DB calls) and apply it
    # in one transaction
    if update_graph:
        mutation_plan = _build_graph_mutation_plan(
            newly_inserted_node,
            parent_attachment_plans,
            parent_label_description_updates,
            sibling_data_node_ids,
            prefetch.children_map,
        )
        await GraphRepository.apply_mutations(graph_id, mutation_plan)
    return newly_inserted_node, parent_attachment_plans, parent_label_description_updates


def _classify_insertion_points_by_node_type(
    insertion_points: List[models.CandidateNode],
) -> tuple[models.CandidateNode | None, List[models.CandidateNode], List[models.CandidateNode]]:
    central_insertion_point: models.CandidateNode | None = None
    category_insertion_points: List[models.CandidateNode] = []
    data_insertion_points: List[models.CandidateNode] = []

    for insertion_point in insertion_points:
        match insertion_point.node_type:
            case enums.NodeType.CENTRAL:
                central_insertion_point = insertion_point
            case enums.NodeType.CATEGORY:
                category_insertion_points.append(insertion_point)
            case enums.NodeType.DATA:
                data_insertion_points.append(insertion_point)

    return central_insertion_point, category_insertion_points, data_insertion_points


def _resolve_parent_nodes(
    central_insertion_point: models.CandidateNode | None,
    category_insertion_points: List[models.CandidateNode],
    data_insertion_points: List[models.CandidateNode],
    prefetched_nodes: dict[str, models.Node],
    prefetched_parents: dict[str, list[models.Node]],
    central_id: str,
) -> List[dict]:
    resolved_parent_map: dict[str, dict] = {}

    if central_insertion_point:
        resolved_parent_map[central_insertion_point.node_id] = {
            "node_id": central_insertion_point.node_id,
            "node": prefetched_nodes[central_insertion_point.node_id],
            "capacity_limit": MAX_ROOT_CHILDREN,
        }

    for category_point in category_insertion_points:
        if category_point.node_id not in resolved_parent_map:
            resolved_parent_map[category_point.node_id] = {
                "node_id": category_point.node_id,
                "node": prefetched_nodes[category_point.node_id],
                "capacity_limit": MAX_NODE_CHILDREN,
            }

    for data_insertion_point in data_insertion_points:
        for parent_of_data_node in prefetched_parents.get(data_insertion_point.node_id, []):
            if parent_of_data_node.node_id not in resolved_parent_map:
                resolved_parent_map[parent_of_data_node.node_id] = {
                    "node_id": parent_of_data_node.node_id,
                    "node": parent_of_data_node,
                    "capacity_limit": (
                        MAX_ROOT_CHILDREN if parent_of_data_node.node_id == central_id else MAX_NODE_CHILDREN
                    ),
                }

    return list(resolved_parent_map.values())

def _build_graph_paths_text(insertion_points: List[models.CandidateNode]) -> str:
    seen_path_strings: set[str] = set()
    unique_path_lines: list[str] = []
    for candidate_node in insertion_points:
        for path_to_node in candidate_node.path_to_node:
            path_line = " → ".join(n.label for n in path_to_node)
            if path_line not in seen_path_strings:
                seen_path_strings.add(path_line)
                unique_path_lines.append(path_line)
    return "\n".join(f"  - {p}" for p in unique_path_lines)


async def _generate_new_data_node(
    chunk: str,
    insertion_points: List[models.CandidateNode],
    llm: services.LLMService,
    chunk_context: str = "",
) -> models.Node:
    graph_paths_text = _build_graph_paths_text(insertion_points)
    sys_msg, user_prompt = constants.Prompts.generate_node_label_and_description(
        chunk=chunk,
        paths_text=graph_paths_text,
        chunk_context=chunk_context,
        llm_provider=llm.provider,
    )
    llm_response = await invoke_llm_and_parse_json(sys_msg, user_prompt, llm)
    new_node = models.Node(
        node_id=str(uuid.uuid4()),
        label=llm_response["label"],
        description=llm_response.get("description"),
        node_type=enums.NodeType.DATA,
        raw_text=chunk,
    )
    return new_node


async def _update_parent_node_label_and_description(
    parent_node: dict,
    chunk: str,
    llm: services.LLMService,
    semaphore: asyncio.Semaphore | None = None,
    chunk_context: str = "",
) -> dict:
    if semaphore is not None:
        async with semaphore:
            return await _update_parent_node_label_and_description(parent_node, chunk, llm, chunk_context=chunk_context)

    parent_node_obj: models.Node = parent_node["node"]
    sys_msg, user_prompt = constants.Prompts.update_parent_node_label_and_description(
        current_label=parent_node_obj.label,
        current_description=parent_node_obj.description or "(no description)",
        chunk=chunk,
        chunk_context=chunk_context,
        llm_provider=llm.provider,
    )
    llm_response = await invoke_llm_and_parse_json(sys_msg, user_prompt, llm)
    return {
        "node_id": parent_node_obj.node_id,
        "label": llm_response["label"],
        "description": llm_response.get("description"),
    }


async def _determine_attachment_plan_for_parent(
    parent_node: dict,
    chunk: str,
    prefetched_children: dict[str, list[models.Node]],
    llm: services.LLMService,
    semaphore: asyncio.Semaphore | None = None,
    chunk_context: str = "",
) -> dict:
    if semaphore is not None:
        async with semaphore:
            return await _determine_attachment_plan_for_parent(parent_node, chunk, prefetched_children, llm, chunk_context=chunk_context)

    parent_id = parent_node["node_id"]
    parent = parent_node["node"]
    capacity_limit = parent_node["capacity_limit"]
    children = prefetched_children.get(parent_id, [])

    if len(children) < capacity_limit:
        return {
            "parent_id": parent_id,
            "actions": [],
            "new_node_attachment_point": parent_id,
        }

    # Parent is at capacity — ask LLM to propose reorganization groups for its children
    children_text = ""
    for child in children:
        if child.node_type == enums.NodeType.CATEGORY:
            child_count = len(prefetched_children.get(child.node_id, []))
            children_text += (
                f"  - node_id={child.node_id!r}, label={child.label!r}, "
                f"node_type=category, description={child.description!r}, child_count={child_count}\n"
            )
        else:
            children_text += (
                f"  - node_id={child.node_id!r}, label={child.label!r}, "
                f"node_type=data, description={child.description!r}, raw_text={child.raw_text!r}\n"
            )
    children_text += (
        f"  - node_id={_NEW_CHUNK_SENTINEL_ID!r}, label='[NEW]', "
        f"node_type=data, description={chunk!r}\n"
    )
    sys_msg, user_prompt = constants.Prompts.propose_reorganize_groups(
        parent_label=parent.label,
        parent_type=parent.node_type,
        children_text=children_text.rstrip(),
        chunk_context=chunk_context,
        llm_provider=llm.provider,
    )
    proposed_groups = await invoke_llm_and_parse_json(sys_msg, user_prompt, llm)

    # Turn the LLM's proposed groups into an attachment plan in three steps.
    validated_groups = _validate_proposed_groups(proposed_groups, children, prefetched_children)
    selected_groups, action_type = _select_groups_to_apply(validated_groups)

    if selected_groups is None:
        logger.warning(
            "No valid reorganization solution found for parent %r — will request LLM-generated umbrella label",
            parent_id,
        )
        return await _generate_umbrella_fallback_plan(
            parent_id, parent, children, prefetched_children, llm,
        )

    return _build_reorganization_plan(selected_groups, action_type, parent_id)


def _validate_proposed_groups(
    proposed_groups: dict,
    current_children: list[models.Node],
    prefetched_children: dict[str, list[models.Node]],
) -> list[dict]:
    node_type_map = {c.node_id: c.node_type for c in current_children}
    node_type_map[_NEW_CHUNK_SENTINEL_ID] = enums.NodeType.DATA
    all_node_id_set = set(node_type_map)

    group_label_to_config = proposed_groups.get("groups", {})
    node_id_to_evaluation = proposed_groups.get("node_evaluations", {})

    group_label_to_member_node_ids: dict[str, list[str]] = {label: [] for label in group_label_to_config}
    group_label_to_node_reasoning: dict[str, dict[str, str]] = {label: {} for label in group_label_to_config}

    for node_id, node_evaluation in node_id_to_evaluation.items():
        if node_id not in all_node_id_set:
            continue
        for group_membership in node_evaluation.get("belongs_to", []):
            belongs_to_label = group_membership.get("label")
            if belongs_to_label not in group_label_to_member_node_ids:
                continue
            group_label_to_member_node_ids[belongs_to_label].append(node_id)
            group_label_to_node_reasoning[belongs_to_label][node_id] = group_membership.get("reasoning", "")

    validated_groups = []
    for label, group_config in group_label_to_config.items():
        valid_node_ids = group_label_to_member_node_ids.get(label, [])
        if len(valid_node_ids) <= 1:
            continue

        grandchild_count = sum(
            len(prefetched_children.get(nid, [])) if node_type_map.get(nid) == enums.NodeType.CATEGORY else 1
            for nid in valid_node_ids
        )

        validated_groups.append({
            "label": label,
            "description": group_config.get("description", ""),
            "node_ids": valid_node_ids,
            "node_id_to_reasoning": group_label_to_node_reasoning[label],
            "grandchild_count": grandchild_count,
            "new_node_in_group": _NEW_CHUNK_SENTINEL_ID in valid_node_ids,
            # Every group becomes a new CATEGORY node, so its capacity is always MAX_NODE_CHILDREN —
            # not the parent's own capacity_limit (which is MAX_ROOT_CHILDREN when the parent is central).
            "is_under_capacity": grandchild_count <= MAX_NODE_CHILDREN,
        })

    return validated_groups


def _select_groups_to_apply(
    validated_groups: list[dict],
) -> tuple[list[dict], str] | tuple[None, None]:
    if not validated_groups:
        return None, None

    mergeable_groups = [group for group in validated_groups if group["is_under_capacity"]]
    umbrella_groups = [group for group in validated_groups if not group["is_under_capacity"]]

    if mergeable_groups:
        # A node may belong to more than one group, so every mergeable group is applied
        # as its own action rather than picking one exclusive, non-overlapping subset.
        return mergeable_groups, "merge"

    umbrella_groups.sort(key=lambda group: len(group["node_ids"]), reverse=True)
    return [umbrella_groups[0]], "group"


def _build_reorganization_plan(
    selected_groups: list[dict],
    action_type: str,
    parent_node_id: str,
) -> dict:
    new_node_attachment_point = parent_node_id
    actions = []
    for selected_group in selected_groups:
        new_category_node_id = str(uuid.uuid4())
        nodes_to_group = [nid for nid in selected_group["node_ids"] if nid != _NEW_CHUNK_SENTINEL_ID]
        actions.append({
            "node_id": new_category_node_id,
            "action_type": action_type,
            "label": selected_group["label"],
            "description": selected_group["description"],
            "nodes_to_group": nodes_to_group,
            "reasoning": {
                node_id_to_group: selected_group["node_id_to_reasoning"].get(node_id_to_group, "")
                for node_id_to_group in nodes_to_group
            },
        })
        if selected_group["new_node_in_group"]:
            new_node_attachment_point = new_category_node_id

    return {
        "parent_id": parent_node_id,
        "actions": actions,
        "new_node_attachment_point": new_node_attachment_point,
    }


async def _generate_umbrella_fallback_plan(
    parent_node_id: str,
    parent_node: models.Node,
    nodes_to_wrap: list[models.Node],
    prefetched_children: dict[str, list[models.Node]],
    llm: services.LLMService,
) -> dict:
    children_text = ""
    for child in nodes_to_wrap:
        child_count = len(prefetched_children.get(child.node_id, []))
        children_text += (
            f"  - node_id={child.node_id!r}, label={child.label!r}, "
            f"description={child.description!r}, child_count={child_count}\n"
        )
    sys_msg, user_prompt = constants.Prompts.generate_umbrella_category_label(
        parent_label=parent_node.label,
        parent_type=parent_node.node_type,
        children_text=children_text.rstrip(),
        llm_provider=llm.provider,
    )
    llm_response = await invoke_llm_and_parse_json(sys_msg, user_prompt, llm)
    return {
        "parent_id": parent_node_id,
        "actions": [
            {
                "node_id":  str(uuid.uuid4()),
                "action_type": "umbrella",
                "label": llm_response.get("label", f"{parent_node.label} Subcategories"),
                "description": llm_response.get("description", ""),
                "nodes_to_group": [c.node_id for c in nodes_to_wrap],
            }
        ],
        "new_node_attachment_point": parent_node_id,
    }


def _build_graph_mutation_plan(
    newly_inserted_node: models.Node,
    parent_attachment_plans: List[dict],
    parent_label_description_updates: List[dict],
    sibling_data_node_ids: List[str],
    prefetched_children: dict[str, list[models.Node]],
) -> GraphMutationPlan:
    """Pure Python planning pass — no DB calls. Resolves every node/edge add and
    remove up front so GraphRepository.apply_mutations can execute the whole
    thing as a handful of batched statements in one transaction."""
    nodes_to_add: list[models.Node] = [newly_inserted_node]
    label_updates = [
        NodeLabelUpdate(
            node_id=update["node_id"], label=update["label"], description=update["description"],
        )
        for update in parent_label_description_updates
    ]
    edges_to_add: list[tuple[str, str]] = []
    edges_to_remove: list[tuple[str, str]] = []
    node_ids_to_remove: list[str] = []
    removed_node_ids: set[str] = set()

    for attachment_plan in parent_attachment_plans:
        parent_node_id = attachment_plan["parent_id"]
        children_by_node_id = {n.node_id: n for n in prefetched_children.get(parent_node_id, [])}

        for action in attachment_plan["actions"]:
            new_category_node = models.Node(
                node_id=action["node_id"],
                label=action["label"],
                description=action["description"],
                node_type=enums.NodeType.CATEGORY,
            )
            nodes_to_add.append(new_category_node)

            if action["action_type"] == "merge":
                # A node can now belong to multiple groups, so a category node grouped by an
                # earlier action in this same pass may already be planned for removal —
                # skip it here rather than re-dissolving an already-removed node.
                category_node_ids_to_dissolve = [
                    node_id for node_id in action["nodes_to_group"]
                    if node_id not in removed_node_ids
                    and children_by_node_id.get(node_id) is not None
                    and children_by_node_id[node_id].node_type == enums.NodeType.CATEGORY
                ]
                data_node_ids_to_reparent = [
                    node_id for node_id in action["nodes_to_group"]
                    if node_id not in removed_node_ids
                    and children_by_node_id.get(node_id) is not None
                    and children_by_node_id[node_id].node_type == enums.NodeType.DATA
                ]
                for original_cat_id in category_node_ids_to_dissolve:
                    for grandchild in prefetched_children.get(original_cat_id, []):
                        edges_to_remove.append((original_cat_id, grandchild.node_id))
                        edges_to_add.append((new_category_node.node_id, grandchild.node_id))
                for node_id_to_dissolve in category_node_ids_to_dissolve:
                    if node_id_to_dissolve not in removed_node_ids:
                        node_ids_to_remove.append(node_id_to_dissolve)
                        removed_node_ids.add(node_id_to_dissolve)

                for data_node_id_to_reparent in data_node_ids_to_reparent:
                    edges_to_remove.append((parent_node_id, data_node_id_to_reparent))
                    edges_to_add.append((new_category_node.node_id, data_node_id_to_reparent))
            else:
                for node_id_to_wrap in action["nodes_to_group"]:
                    edges_to_remove.append((parent_node_id, node_id_to_wrap))
                    edges_to_add.append((new_category_node.node_id, node_id_to_wrap))

            edges_to_add.append((parent_node_id, new_category_node.node_id))

        edges_to_add.append((attachment_plan["new_node_attachment_point"], newly_inserted_node.node_id))

    data_relations_to_add = [
        (newly_inserted_node.node_id, sibling_data_node_id)
        for sibling_data_node_id in sibling_data_node_ids
    ]

    return GraphMutationPlan(
        nodes_to_add=nodes_to_add,
        label_updates=label_updates,
        edges_to_add=edges_to_add,
        edges_to_remove=edges_to_remove,
        node_ids_to_remove=node_ids_to_remove,
        data_relations_to_add=data_relations_to_add,
    )
