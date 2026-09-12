from __future__ import annotations

import uuid
from typing import List

import services
from services.graph_service import utils, models


class GraphService:
    def __init__(self, graph_id: uuid.UUID, llm: services.LLMService):
        self._graph_id = graph_id
        self._llm = llm

    async def retrieve(self, query: str) -> List[models.CandidateNode]:
        return await utils.retrieve(query, self._graph_id, self._llm)

    async def insert_chunk(self, chunk: str, update_graph: bool = True) -> dict:
        return await utils.insert_chunk(chunk, self._graph_id, self._llm, update_graph=update_graph)
