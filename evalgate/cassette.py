"""Record / replay for every billed call.

Mode comes from EVALGATE_MODE:

    replay (default) — answer from the cassette; a miss raises CassetteMiss. Costs $0.
    record           — answer from the cassette if present, otherwise call live and save.
    live             — always call live, overwrite the cassette.

The key is a hash of the canonical request (model, messages, tools, params). So a
prompt edit, a tool-schema change or a new case is a cassette MISS in CI — the gate
fails loudly and says the change needs a live re-record, instead of silently scoring
yesterday's answers against today's prompt.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable


class CassetteMiss(RuntimeError):
    pass


def mode() -> str:
    m = os.environ.get("EVALGATE_MODE", "replay")
    if m not in ("replay", "record", "live"):
        raise ValueError(f"EVALGATE_MODE must be replay|record|live, got {m!r}")
    return m


def key(request: dict[str, Any]) -> str:
    canon = json.dumps(request, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode()).hexdigest()[:24]


class Cassette:
    """One JSON file per request, grouped in a directory per project."""

    def __init__(self, directory: Path):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, k: str) -> Path:
        return self.dir / f"{k}.json"

    def call(self, kind: str, request: dict[str, Any],
             live: Callable[[], dict[str, Any]]) -> tuple[dict[str, Any], bool]:
        """-> (response, was_live)"""
        k = key({"kind": kind, **request})
        p = self._path(k)
        m = mode()
        if m != "live" and p.exists():
            return json.loads(p.read_text())["response"], False
        if m == "replay":
            raise CassetteMiss(
                f"no recorded response for this {kind} request ({k}) in {self.dir.name}/. "
                "The prompt, tools, model or case changed since the last recording. "
                "Re-record with EVALGATE_MODE=record (this bills the provider).")
        resp = live()
        p.write_text(json.dumps({"kind": kind, "request": request, "response": resp},
                                indent=1, default=str))
        return resp, True
