from __future__ import annotations

import json
import re

import services
from core.tracing import traced


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    return re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE).strip()


@traced
async def invoke_llm_and_parse_json(
    sys_msg: str,
    user_prompt: str,
    llm: services.LLMService,
) -> dict:
    result = await llm.complete(system_prompt=sys_msg, user_prompt=user_prompt)
    try:
        parsed = json.loads(_strip_markdown(result.content))
    except Exception as e:
        retry = await llm.complete(
            system_prompt=sys_msg,
            user_prompt=user_prompt + f"\n\nYour previous response caused a parse error: {e}\nReturn JSON only, nothing else.",
        )
        parsed = json.loads(_strip_markdown(retry.content))

    return parsed