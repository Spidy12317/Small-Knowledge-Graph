from __future__ import annotations

import asyncio
import uuid
from collections import deque

from core import enums
from repository import GraphRepository
from services.llm_service import LLMService

DEFAULT_GRAPH_NAME = "default"
MAX_PIPELINE_TRACE_HISTORY_PER_GRAPH = 200


class AppState:
    def __init__(self) -> None:
        self.llm: LLMService = LLMService(provider=enums.LLMProvider.GEMINI)
        self.graph_id: uuid.UUID | None = None
        self.lock = asyncio.Lock()
        # Display-only trace of recent chunk inserts per graph, kept purely in memory
        # (never persisted, capped, lost on restart) so the Steps UI can show a
        # timeline of pipeline runs however they were triggered — through the
        # browser or a notebook hitting the API directly.
        self.pipeline_trace_history_by_graph_id: dict[uuid.UUID, deque[dict]] = {}

    async def bootstrap(self) -> None:
        """Finds or seeds the default graph. Must be awaited once at app startup —
        DB access can't happen at import time, unlike the old JSON-file singleton."""
        graph_id = await GraphRepository.get_graph_id_by_name(DEFAULT_GRAPH_NAME)
        if graph_id is None:
            graph_id = await GraphRepository.seed_from_json(DEFAULT_GRAPH_NAME)
        self.graph_id = graph_id

    def record_pipeline_trace(self, graph_id: uuid.UUID, trace: dict) -> None:
        history = self.pipeline_trace_history_by_graph_id.setdefault(
            graph_id, deque(maxlen=MAX_PIPELINE_TRACE_HISTORY_PER_GRAPH),
        )
        history.append(trace)


state = AppState()
