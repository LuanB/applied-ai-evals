"""Bounded read-only accessors over the offline substrate.

This module IS the agent's future tool surface. Every function here is a tool the
explain stage will be allowed to call, and every one of them returns a BOUNDED
result: names and stats first, drill-down on request. Nothing here calls an API.

Design rule carried from an earlier production digest: the model never does arithmetic.
Anything numeric is computed here or in detect.py and handed to the model as a fact.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELEMETRY = os.path.join(ROOT, "telemetry", "events-signal.ndjson")
GIT_DIR = os.path.join(ROOT, "git")
COST_DIR = os.path.join(ROOT, "cost")

# Result bounds. A tool that returns everything is a tool that blows the context
# window and teaches the model nothing about drilling in.
MAX_COMMITS = 40
MAX_FILES_PER_COMMIT = 25
MAX_ROWS = 50


def _utc_date(ts_ms: int) -> dt.date:
    return dt.datetime.fromtimestamp(ts_ms / 1000, dt.UTC).date()


# --------------------------------------------------------------------------
# telemetry
# --------------------------------------------------------------------------


@dataclass
class Telemetry:
    rows: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, path: str = TELEMETRY) -> "Telemetry":
        rows = []
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "ts" in r:
                    rows.append(r)
        rows.sort(key=lambda r: r["ts"])
        return cls(rows)

    def date_range(self) -> tuple[dt.date, dt.date]:
        return _utc_date(self.rows[0]["ts"]), _utc_date(self.rows[-1]["ts"])

    def iter_kind(self, kind: str, phase: str | None = None) -> Iterator[dict[str, Any]]:
        for r in self.rows:
            if r.get("kind") != kind:
                continue
            if phase is not None and r.get("phase") != phase:
                continue
            yield r

    def field_coverage(self, name: str) -> dict[dt.date, tuple[int, int]]:
        """day -> (rows carrying the field, rows where it is non-zero/truthy).

        Used by the field-appearance detector. Coverage is itself a signal: a field
        that does not exist cannot be billed for, which is the whole archetype of
        case 1.
        """
        out: dict[dt.date, list[int]] = defaultdict(lambda: [0, 0])
        for r in self.rows:
            if name in r:
                d = _utc_date(r["ts"])
                out[d][0] += 1
                if r.get(name):
                    out[d][1] += 1
        return {k: (v[0], v[1]) for k, v in sorted(out.items())}

    def tool_calls_per_run(self) -> dict[dt.date, list[int]]:
        """day -> sorted list of tool-call counts, one entry per runId."""
        counts: dict[str, int] = defaultdict(int)
        day_of: dict[str, dt.date] = {}
        for r in self.iter_kind("tool_call"):
            rid = r.get("runId")
            if not rid:
                continue
            counts[rid] += 1
            day_of.setdefault(rid, _utc_date(r["ts"]))
        out: dict[dt.date, list[int]] = defaultdict(list)
        for rid, n in counts.items():
            out[day_of[rid]].append(n)
        return {k: sorted(v) for k, v in sorted(out.items())}

    def daily_values(self, kind: str, numeric_field: str,
                     phase: str | None = None) -> dict[dt.date, list[float]]:
        out: dict[dt.date, list[float]] = defaultdict(list)
        for r in self.iter_kind(kind, phase):
            v = r.get(numeric_field)
            if isinstance(v, (int, float)):
                out[_utc_date(r["ts"])].append(float(v))
        return {k: sorted(v) for k, v in sorted(out.items())}

    def sample_rows(self, kind: str, day: dt.date, limit: int = 5) -> list[dict[str, Any]]:
        """Bounded drill-down: a handful of raw rows so a claim can be checked."""
        out = []
        for r in self.iter_kind(kind):
            if _utc_date(r["ts"]) == day:
                out.append(r)
                if len(out) >= min(limit, MAX_ROWS):
                    break
        return out


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------


@dataclass
class Commit:
    sha: str
    date: dt.date
    subject: str
    repo: str
    files: list[str] = field(default_factory=list)

    @property
    def short(self) -> str:
        return self.sha[:7]


class GitLog:
    """Parsed `sha|date|author|subject` logs plus the files-changed variant."""

    def __init__(self, commits: list[Commit]):
        self.commits = sorted(commits, key=lambda c: c.date)
        self._by_short = {c.short: c for c in self.commits}

    @classmethod
    def load(cls, git_dir: str = GIT_DIR) -> "GitLog":
        commits: dict[str, Commit] = {}
        for fn in sorted(os.listdir(git_dir)):
            path = os.path.join(git_dir, fn)
            repo = fn.split("-log")[0]
            if fn.endswith("-log.txt"):
                with open(path) as fh:
                    for line in fh:
                        parts = line.rstrip("\n").split("|", 3)
                        if len(parts) < 4:
                            continue
                        sha, date_s, _author, subject = parts
                        commits.setdefault(sha, Commit(sha, _parse_date(date_s), subject, repo))
            elif fn.endswith("-log-files.txt"):
                with open(path) as fh:
                    cur: Commit | None = None
                    for line in fh:
                        line = line.rstrip("\n")
                        if line.startswith("==="):
                            parts = line[3:].split("|", 2)
                            if len(parts) < 3:
                                cur = None
                                continue
                            sha, date_s, subject = parts
                            cur = commits.setdefault(
                                sha, Commit(sha, _parse_date(date_s), subject, repo)
                            )
                        elif line and cur is not None:
                            cur.files.append(line)
        return cls(list(commits.values()))

    def in_window(self, start: dt.date, end: dt.date,
                  touching: tuple[str, ...] | None = None) -> list[Commit]:
        """Commits in [start, end], optionally filtered to those touching a path
        substring. Bounded — this is a tool result, not a data dump."""
        out = [c for c in self.commits if start <= c.date <= end]
        if touching:
            out = [c for c in out
                   if any(t in f for f in c.files for t in touching)]
        return out[:MAX_COMMITS]

    def get(self, short_or_full: str) -> Commit | None:
        s = short_or_full[:7]
        return self._by_short.get(s)

    def describe(self, c: Commit) -> dict[str, Any]:
        """Bounded commit view: subject + change stats first, file list truncated."""
        return {
            "sha": c.short,
            "date": c.date.isoformat(),
            "repo": c.repo,
            "subject": c.subject,
            "files_changed": len(c.files),
            "files": c.files[:MAX_FILES_PER_COMMIT],
            "files_truncated": max(0, len(c.files) - MAX_FILES_PER_COMMIT),
        }


def _parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s.strip().split(" ")[0])


# --------------------------------------------------------------------------
# cost
# --------------------------------------------------------------------------


def load_cost(cost_dir: str = COST_DIR) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not os.path.isdir(cost_dir):
        return rows
    for fn in sorted(os.listdir(cost_dir)):
        if not fn.endswith(".csv"):
            continue
        with open(os.path.join(cost_dir, fn), newline="") as fh:
            rows.extend(dict(r) for r in csv.DictReader(fh))
    return rows
