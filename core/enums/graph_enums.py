from enum import Enum


class NodeType(str, Enum):
    CENTRAL = "central"
    CATEGORY = "category"
    DATA = "data"