from __future__ import annotations

import uuid

import services
from core import constants
from repository import GraphRepository
from services.graph_service.utils.llm_utils import invoke_llm_and_parse_json


async def extract_chunk_context(chunk: str, graph_id: uuid.UUID, llm: services.LLMService) -> str:
    current_context = await GraphRepository.get_graph_context(graph_id)
    sys_msg, user_prompt = constants.Prompts.extract_chunk_context(
        chunk=chunk,
        graph_context=current_context,
        llm_provider=llm.provider,
    )
    result = await invoke_llm_and_parse_json(sys_msg, user_prompt, llm)
    updated_context = result.get("updated_graph_context", current_context)
    await GraphRepository.update_graph_context(graph_id, updated_context)
    return result.get("chunk_context", "")
