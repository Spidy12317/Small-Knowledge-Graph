from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import services
from core.tracing import traced

if TYPE_CHECKING:
    from services.graph_service.utils.insert_audit import InsertAuditCollector


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    return re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE).strip()


@traced
async def invoke_llm_and_parse_json(
    sys_msg: str,
    user_prompt: str,
    llm: services.LLMService,
    *,
    collector: InsertAuditCollector | None = None,
    audit_seq: int | None = None,
) -> dict:
    result = await llm.complete(system_prompt=sys_msg, user_prompt=user_prompt)
    raw = result.content
    retry_raw: str | None = None
    try:
        parsed = json.loads(_strip_markdown(raw))
    except Exception as e:
        retry = await llm.complete(
            system_prompt=sys_msg,
            user_prompt=user_prompt + f"\n\nYour previous response caused a parse error: {e}\nReturn JSON only, nothing else.",
        )
        retry_raw = retry.content
        parsed = json.loads(_strip_markdown(retry_raw))

    if collector is not None and audit_seq is not None:
        collector.complete_call(
            audit_seq,
            raw,
            parsed,
            retry_raw=retry_raw,
            retry_parsed=parsed if retry_raw is not None else None,
        )

    return parsed


async def invoke_llm_traced(
    sys_msg: str,
    user_prompt: str,
    llm: services.LLMService,
    collector: InsertAuditCollector | None,
    phase: str,
    purpose: str,
    **context,
) -> dict:
    audit_seq: int | None = None
    if collector is not None:
        audit_seq = collector.reserve_call(phase, purpose, sys_msg, user_prompt, **context)
    return await invoke_llm_and_parse_json(
        sys_msg,
        user_prompt,
        llm,
        collector=collector,
        audit_seq=audit_seq,
    )
