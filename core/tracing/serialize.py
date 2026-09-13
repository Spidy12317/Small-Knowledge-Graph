from __future__ import annotations

import dataclasses
import inspect
import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any


def to_jsonable(value: Any, depth: int = 0) -> Any:
    """Converts decision inputs and outputs into JSON-safe values.

    Live clients (the LLM service, semaphores, sessions) are replaced with a
    short marker so a span can record that the argument existed without
    dumping the object.
    """
    if depth > 12:
        return {"_skipped": type(value).__name__}

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, BaseException):
        return {"_error": f"{type(value).__name__}: {value}"}

    skipped = _skipped_marker(value)
    if skipped is not None:
        return skipped

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value), depth + 1)
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return to_jsonable(value.model_dump(), depth + 1)
    if hasattr(value, "_asdict") and callable(value._asdict):
        return to_jsonable(value._asdict(), depth + 1)
    if isinstance(value, dict):
        return {str(key): to_jsonable(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(item, depth + 1) for item in value]
    return {"_skipped": type(value).__name__}


def _skipped_marker(value: Any) -> dict[str, str] | None:
    if inspect.isfunction(value) or inspect.ismethod(value) or inspect.iscoroutine(value):
        return {"_skipped": type(value).__name__}
    type_name = type(value).__name__
    if type_name in {"LLMService", "Semaphore", "AsyncSession", "Session", "Lock"}:
        return {"_skipped": type_name}
    return None
