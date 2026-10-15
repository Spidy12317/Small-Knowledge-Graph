from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

_STEP_GRAPH_FILE = re.compile(r"^step(\d+)\.json$")

from repository.graph_repository.repository import DEFAULT_SEED_JSON_PATH

logger = logging.getLogger(__name__)

# Same directory as data/graph.json (repo root / data /)
SNAPSHOT_ROOT = DEFAULT_SEED_JSON_PATH.parent


class InsertAuditCollector:
    """Records insert-time LLM calls in dispatch order (reserve before scheduling tasks)."""

    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model
        self._calls: list[dict[str, Any]] = []
        self._seq = 0

    def reserve_call(
        self,
        phase: str,
        purpose: str,
        system: str,
        user: str,
        **context: Any,
    ) -> int:
        self._seq += 1
        entry: dict[str, Any] = {
            "seq": self._seq,
            "phase": phase,
            "purpose": purpose,
            "input": {"system": system, "user": user},
            "output": {},
        }
        if context:
            entry["context"] = context
        self._calls.append(entry)
        return self._seq

    def complete_call(
        self,
        seq: int,
        raw: str,
        parsed: dict,
        *,
        retry_raw: str | None = None,
        retry_parsed: dict | None = None,
    ) -> None:
        entry = self._calls[seq - 1]
        if entry["seq"] != seq:
            raise ValueError(f"seq mismatch: expected {entry['seq']}, got {seq}")
        output: dict[str, Any] = {"raw": raw, "parsed": parsed}
        if retry_raw is not None:
            output["retry_raw"] = retry_raw
        if retry_parsed is not None:
            output["retry_parsed"] = retry_parsed
        entry["output"] = output

    def llm_section(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "calls": self._calls,
        }


def graph_checkpoint_dir(graph_id: uuid.UUID) -> Path:
    return SNAPSHOT_ROOT / str(graph_id)


def allocate_next_step(graph_id: uuid.UUID) -> int:
    directory = graph_checkpoint_dir(graph_id)
    if not directory.is_dir():
        return 1
    max_step = 0
    for path in directory.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if name.endswith(".audit.json") and name.startswith("step"):
            suffix = name.removesuffix(".audit.json")[4:]
        elif name.endswith(".json") and name.startswith("step"):
            suffix = name.removesuffix(".json")[4:]
        else:
            continue
        if suffix.isdigit():
            max_step = max(max_step, int(suffix))
    return max_step + 1


def snapshot_to_dict(snapshot) -> dict:
    from models.graph import serialize_node

    return {
        "graph_id": str(snapshot.graph_id),
        "name": snapshot.name,
        "context": snapshot.context,
        "central_id": snapshot.central_id,
        "nodes": [serialize_node(n) for n in snapshot.nodes],
        "edges": snapshot.edges,
        "data_relations": snapshot.data_relations,
    }


def save_graph_snapshot(graph_id: uuid.UUID, snapshot, step: int) -> Path:
    directory = graph_checkpoint_dir(graph_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"step{step}.json"
    path.write_text(json.dumps(snapshot_to_dict(snapshot), indent=2), encoding="utf-8")
    logger.info("Wrote graph checkpoint %s", path.resolve())
    return path


def save_insert_audit(
    graph_id: uuid.UUID,
    step: int,
    *,
    inserted_at: str,
    chunk: str,
    collector: InsertAuditCollector,
    outcomes: dict[str, Any],
) -> Path:
    directory = graph_checkpoint_dir(graph_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"step{step}.audit.json"
    document = {
        "schema_version": 1,
        "graph_id": str(graph_id),
        "step": step,
        "inserted_at": inserted_at,
        "checkpoint_graph_file": f"step{step}.json",
        "chunk": {"text": chunk, "length": len(chunk)},
        "llm": collector.llm_section(),
        "outcomes": outcomes,
    }
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    logger.info("Wrote insert audit %s", path.resolve())
    return path


def checkpoint_paths(graph_id: uuid.UUID, step: int) -> dict[str, str]:
    base = graph_checkpoint_dir(graph_id)
    return {
        "step": step,
        "graph_file": str(base / f"step{step}.json"),
        "audit_file": str(base / f"step{step}.audit.json"),
    }


def list_checkpoint_graph_ids() -> list[str]:
    """Graph UUID folder names under data/ that contain at least one stepN.json snapshot."""
    if not SNAPSHOT_ROOT.is_dir():
        return []
    ids: list[str] = []
    for entry in SNAPSHOT_ROOT.iterdir():
        if not entry.is_dir():
            continue
        if any(_STEP_GRAPH_FILE.match(p.name) for p in entry.iterdir() if p.is_file()):
            ids.append(entry.name)
    return sorted(ids)


def list_checkpoint_steps(graph_id: uuid.UUID) -> list[int]:
    directory = graph_checkpoint_dir(graph_id)
    if not directory.is_dir():
        return []
    steps: list[int] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        match = _STEP_GRAPH_FILE.match(path.name)
        if match:
            steps.append(int(match.group(1)))
    return sorted(steps)


def load_checkpoint_graph(graph_id: uuid.UUID, step: int) -> dict[str, Any]:
    path = graph_checkpoint_dir(graph_id) / f"step{step}.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))
