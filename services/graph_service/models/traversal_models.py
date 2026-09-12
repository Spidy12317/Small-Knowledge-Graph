from typing import NamedTuple

from core import enums
from repository.graph_repository.models import Node


class CandidateNode(NamedTuple):
    node: Node
    node_id: str
    node_type: enums.NodeType
    path_to_node: list[list[Node]]
    reasoning: str = ""