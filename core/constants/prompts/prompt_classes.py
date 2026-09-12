import logging

from core import enums
from core.constants.prompts.raw_prompts import *

logger = logging.getLogger(__name__)

_DEFAULTS: dict[str, tuple[str, str]] = {
    "graph_navigation": (DEFAULT_GRAPH_NAVIGATION_SYSTEM_MESSAGE, DEFAULT_GRAPH_NAVIGATION_USER_TEMPLATE),
    "score_category_node_for_insertion": (DEFAULT_GRAPH_SCORE_NODE_FOR_INSERTION_SYSTEM_MESSAGE, DEFAULT_GRAPH_SCORE_CATEGORY_NODE_FOR_INSERTION_USER_TEMPLATE),
    "score_data_node_for_insertion": (DEFAULT_GRAPH_SCORE_NODE_FOR_INSERTION_SYSTEM_MESSAGE, DEFAULT_GRAPH_SCORE_DATA_NODE_FOR_INSERTION_USER_TEMPLATE),
    "generate_node_label_and_description": (DEFAULT_GENERATE_NODE_LABEL_SYSTEM_MESSAGE, DEFAULT_GENERATE_NODE_LABEL_USER_TEMPLATE),
    "generate_umbrella_category_label": (DEFAULT_GENERATE_UMBRELLA_CATEGORY_LABEL_SYSTEM_MESSAGE, DEFAULT_GENERATE_UMBRELLA_CATEGORY_LABEL_USER_TEMPLATE),
    "propose_reorganize_groups": (DEFAULT_REORGANIZE_SYSTEM_MESSAGE, DEFAULT_PROPOSE_REORGANIZE_GROUPS_USER_TEMPLATE),
    "extract_chunk_context": (DEFAULT_EXTRACT_CHUNK_CONTEXT_SYSTEM_MESSAGE, DEFAULT_EXTRACT_CHUNK_CONTEXT_USER_TEMPLATE),
    "update_parent_node_label_and_description": (DEFAULT_UPDATE_PARENT_NODE_LABEL_DESCRIPTION_SYSTEM_MESSAGE, DEFAULT_UPDATE_PARENT_NODE_LABEL_DESCRIPTION_USER_TEMPLATE),
}
_PROMPTS: dict[str, dict[enums.LLMProvider, tuple[str, str]]] = {
    name: {enums.LLMProvider.AZURE_OPENAI: default_prompts}
    for name, default_prompts in _DEFAULTS.items()
}

class Prompts:
    @staticmethod
    def _render(name: str, llm_provider: enums.LLMProvider, **fields: str) -> tuple[str, str]:
        provider_prompts = _PROMPTS.get(name, {})
        if llm_provider not in provider_prompts:
            logger.warning(
                "No %s prompt for provider %s, using default", name, llm_provider)
            sys_msg, template = _DEFAULTS[name]
        else:
            sys_msg, template = provider_prompts[llm_provider]
        return sys_msg, template.format(**fields)

    @staticmethod
    def graph_navigation(
        query: str,
        current_label: str,
        current_type: str,
        children_text: str,
        llm_provider: enums.LLMProvider = enums.LLMProvider.AZURE_OPENAI,
    ) -> tuple[str, str]:
        return Prompts._render(
            "graph_navigation", llm_provider,
            query=query, current_label=current_label,
            current_type=current_type, children_text=children_text,
        )

    @staticmethod
    def score_category_node_for_insertion(
        chunk: str,
        current_label: str,
        current_type: str,
        children_text: str,
        chunk_context: str = "",
        llm_provider: enums.LLMProvider = enums.LLMProvider.AZURE_OPENAI,
    ) -> tuple[str, str]:
        chunk_context_section = (
            f"Preceding discussion context (what was being discussed before this chunk):\n{chunk_context}\n\n"
            if chunk_context else ""
        )
        return Prompts._render(
            "score_category_node_for_insertion", llm_provider,
            chunk=chunk, current_label=current_label,
            current_type=current_type, children_text=children_text,
            chunk_context_section=chunk_context_section,
        )

    @staticmethod
    def score_data_node_for_insertion(
        chunk: str,
        children_text: str,
        chunk_context: str = "",
        llm_provider: enums.LLMProvider = enums.LLMProvider.AZURE_OPENAI,
    ) -> tuple[str, str]:
        chunk_context_section = (
            f"Preceding discussion context (what was being discussed before this chunk):\n{chunk_context}\n\n"
            if chunk_context else ""
        )
        return Prompts._render(
            "score_data_node_for_insertion", llm_provider,
            chunk=chunk, children_text=children_text,
            chunk_context_section=chunk_context_section,
        )

    @staticmethod
    def generate_node_label_and_description(
        chunk: str,
        paths_text: str,
        chunk_context: str = "",
        llm_provider: enums.LLMProvider = enums.LLMProvider.AZURE_OPENAI,
    ) -> tuple[str, str]:
        chunk_context_section = (
            f"Preceding discussion context (what was being discussed before this chunk):\n{chunk_context}\n\n"
            if chunk_context else ""
        )
        return Prompts._render(
            "generate_node_label_and_description", llm_provider,
            chunk=chunk, paths_text=paths_text, chunk_context_section=chunk_context_section,
        )

    @staticmethod
    def generate_umbrella_category_label(
        parent_label: str,
        parent_type: str,
        children_text: str,
        llm_provider: enums.LLMProvider = enums.LLMProvider.AZURE_OPENAI,
    ) -> tuple[str, str]:
        return Prompts._render(
            "generate_umbrella_category_label", llm_provider,
            parent_label=parent_label,
            parent_type=parent_type,
            children_text=children_text,
        )

    @staticmethod
    def propose_reorganize_groups(
        parent_label: str,
        parent_type: str,
        children_text: str,
        chunk_context: str = "",
        llm_provider: enums.LLMProvider = enums.LLMProvider.AZURE_OPENAI,
    ) -> tuple[str, str]:
        chunk_context_section = (
            f"Preceding discussion context (what was being discussed before this chunk):\n{chunk_context}\n\n"
            if chunk_context else ""
        )
        return Prompts._render(
            "propose_reorganize_groups", llm_provider,
            parent_label=parent_label,
            parent_type=parent_type,
            children_text=children_text,
            chunk_context_section=chunk_context_section,
        )

    @staticmethod
    def extract_chunk_context(
        chunk: str,
        graph_context: str,
        llm_provider: enums.LLMProvider = enums.LLMProvider.AZURE_OPENAI,
    ) -> tuple[str, str]:
        return Prompts._render(
            "extract_chunk_context", llm_provider,
            chunk=chunk,
            graph_context=graph_context or "(no prior context)",
        )

    @staticmethod
    def update_parent_node_label_and_description(
        current_label: str,
        current_description: str,
        chunk: str,
        chunk_context: str = "",
        llm_provider: enums.LLMProvider = enums.LLMProvider.AZURE_OPENAI,
    ) -> tuple[str, str]:
        chunk_context_section = (
            f"Preceding discussion context (what was being discussed before this chunk):\n{chunk_context}\n\n"
            if chunk_context else ""
        )
        return Prompts._render(
            "update_parent_node_label_and_description", llm_provider,
            current_label=current_label,
            current_description=current_description,
            chunk=chunk,
            chunk_context_section=chunk_context_section,
        )

