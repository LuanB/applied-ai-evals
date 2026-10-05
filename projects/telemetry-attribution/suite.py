"""P1 demo suite — telemetry-movement attribution.

An agent is handed a movement in production telemetry (already computed by a
deterministic detector) plus the commits in a release window, and has to name the
commit that caused it — or refuse when nothing in the window does.

Ground truth is the git history of a real product (Mayah). The refusal cases are the
same real movements shown with a window that excludes the cause: commits still exist
there, so an agent that pattern-matches "find the most plausible commit" confabulates.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "harness"))

import cases as cases_mod  # noqa: E402
import detect as detect_mod  # noqa: E402
from substrate import Commit, GitLog, Telemetry  # noqa: E402

from evalgate import llm  # noqa: E402
from evalgate.core import CaseResult, Suite  # noqa: E402

MAX_TOOL_CALLS = 8
TRIALS = 3

EXTRA_REFUSALS = [
    cases_mod.Case(
        id="refusal-before-field-existed",
        finding_id="field_appearance:reasoningTokens",
        expect_refusal=True,
        window_override=(dt.date(2026, 6, 15), dt.date(2026, 6, 22)),
        note="Window ends 11 days before the field first appears. Nothing in it can explain "
             "a field that did not exist yet.",
    ),
    cases_mod.Case(
        id="refusal-window-after-movement",
        finding_id="step:tool_calls_per_run",
        expect_refusal=True,
        window_override=(dt.date(2026, 7, 24), dt.date(2026, 7, 30)),
        note="Every commit in the window lands AFTER the 2026-07-18 movement. Causes do not "
             "run backwards; an agent that reads dates refuses.",
    ),
]

SYSTEM_PROMPT = """\
You explain movements in software telemetry by attributing them to a commit.

THE NUMBERS ARE ALREADY COMPUTED AND ARE NOT YOURS TO RECOMPUTE.
The finding was produced by a deterministic detector. Treat its numbers as fact. Your
job is judgement, not arithmetic: given that this movement happened, which commit in
the window explains it, and what is the evidence?

Method:
- Start with list_commits_in_window. You get subjects and file-change counts.
- Use describe_commit on the few that plausibly relate. Look at which files changed.
- Use sample_telemetry_rows only if you need to see the shape of the raw data.
- Then call submit_answer. You MUST finish by calling submit_answer.

REFUSAL IS A CORRECT ANSWER AND IS EXPECTED SOMETIMES.
There is always a commit in a window. That does not mean one of them caused the
movement. If no commit plausibly explains it, call submit_answer with refused=true and
commits=[]. A confident wrong attribution is worse than an honest refusal, because it
will be believed. Check dates: a commit after the movement cannot have caused it.

Name at most 3 commits.
"""

TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "list_commits_in_window",
        "description": "Commits in the finding's window: sha, date, subject, files_changed.",
        "parameters": {"type": "object", "properties": {
            "only_touching": {"type": "string",
                              "description": "Optional path substring filter, e.g. 'telemetry'."}}}}},
    {"type": "function", "function": {
        "name": "describe_commit",
        "description": "One commit in detail: subject, file count, and the file list (truncated).",
        "parameters": {"type": "object", "properties": {"sha": {"type": "string"}},
                       "required": ["sha"]}}},
    {"type": "function", "function": {
        "name": "sample_telemetry_rows",
        "description": "A few raw telemetry rows of a given kind on a given day (YYYY-MM-DD).",
        "parameters": {"type": "object", "properties": {
            "kind": {"type": "string"}, "day": {"type": "string"}},
            "required": ["kind", "day"]}}},
    {"type": "function", "function": {
        "name": "submit_answer",
        "description": "Terminal. Submit the attribution, or refuse.",
        "parameters": {"type": "object", "properties": {
            "commits": {"type": "array", "items": {"type": "string"},
                        "description": "Short SHAs. Empty if refusing."},
            "refused": {"type": "boolean"},
            "rationale": {"type": "string"}},
            "required": ["commits", "refused", "rationale"]}}},
]


@dataclass
class Trial:
    case: cases_mod.Case
    finding: detect_mod.Finding
    window: list[Commit]
    trial: int

    @property
    def id(self) -> str:
        return f"{self.case.id}#{self.trial}"


class _Data:
    tel: Telemetry | None = None
    gl: GitLog | None = None

    @classmethod
    def get(cls) -> tuple[Telemetry, GitLog]:
        if cls.tel is None:
            cls.tel, cls.gl = Telemetry.load(), GitLog.load()
        return cls.tel, cls.gl  # type: ignore[return-value]


def build_window(gl: GitLog, f: detect_mod.Finding, case: cases_mod.Case) -> list[Commit]:
    start, end = case.window_override or (f.window_start, f.window_end)
    hinted = gl.in_window(start, end, touching=f.subsystem_hints or None)
    return hinted or gl.in_window(start, end)


def score(t: Trial, named: tuple[str, ...], refused: bool, why: str) -> CaseResult:
    r = cases_mod.score(t.case, named, refused)
    return CaseResult(t.id, r.passed, float(r.passed), f"{r.reason} — {why}"[:240],
                      tags={"case": t.case.id, "refusal_case": t.case.expect_refusal,
                            "named": list(named), "refused": refused})


LAG_DAYS = 7


def movement_day(f: detect_mod.Finding) -> dt.date:
    return dt.date.fromisoformat(f.evidence.get("day") or f.evidence["first_day"])


def temporal_check(t: Trial, named: tuple[str, ...]) -> tuple[tuple[str, ...], list[str]]:
    """Deterministic: a cause lands on or up to LAG_DAYS before the movement.

    Same rule as the detector — dates are arithmetic, so the model does not get to
    decide them. v1 named commits dated AFTER the movement in 3 of 3 trials.
    """
    _, gl = _Data.get()
    day = movement_day(t.finding)
    keep, drop = [], []
    for sha in named:
        c = gl.get(sha)
        if c and day - dt.timedelta(days=LAG_DAYS) <= c.date <= day:
            keep.append(sha)
        else:
            drop.append(sha)
    return tuple(keep), drop


class AlwaysGuess:
    name = "always-guess"

    def run(self, t: Trial) -> CaseResult:
        pick = max(t.window, key=lambda c: len(c.files)) if t.window else None
        return score(t, (pick.short,) if pick else (), False, "largest changeset in window")


class AlwaysRefuse:
    name = "always-refuse"

    def run(self, t: Trial) -> CaseResult:
        return score(t, (), True, "declines to attribute")


class ToolLoopAgent:
    """Agent loop: hard tool budget, forced terminal tool, every call through evalgate."""

    def __init__(self, deployment: str, guarded: bool = True, **params: Any):
        self.deployment = deployment
        self.params = params
        # v1 = the raw loop, kept as an ungated "before" so the report shows what the
        # guards bought. v2 = forced terminal turn + deterministic date check.
        self.guarded = guarded
        self.gated = guarded
        self.name = f"agent-v2:{deployment}" if guarded else f"agent-v1-raw:{deployment}"

    def _dispatch(self, name: str, args: dict[str, Any], t: Trial) -> str:
        tel, gl = _Data.get()
        if name == "list_commits_in_window":
            only = args.get("only_touching")
            rows = t.window
            if only:
                rows = [c for c in t.window if any(only in f for f in c.files)] or t.window
            return json.dumps([{"sha": c.short, "date": c.date.isoformat(), "repo": c.repo,
                                "subject": c.subject, "files_changed": len(c.files)} for c in rows])
        if name == "describe_commit":
            c = gl.get(str(args.get("sha", "")))
            return json.dumps(gl.describe(c) if c else {"error": "unknown sha"})
        if name == "sample_telemetry_rows":
            try:
                day = dt.date.fromisoformat(str(args.get("day", "")))
            except ValueError:
                return json.dumps({"error": "day must be YYYY-MM-DD"})
            return json.dumps(tel.sample_rows(str(args.get("kind", "")), day, limit=5))
        return json.dumps({"error": f"unknown tool {name}"})

    def run(self, t: Trial) -> CaseResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": t.finding.as_prompt_facts()
             + f"\n{len(t.window)} commits are in this window. Attribute the movement, or refuse."},
        ]
        used = 0
        while used < MAX_TOOL_CALLS:
            params = dict(self.params)
            if self.guarded and used >= MAX_TOOL_CALLS - 2:
                # Evidence: 20-27% of v1 runs spent the whole budget exploring and never
                # answered. On the last turn the only legal move is to answer.
                params["tool_choice"] = {"type": "function", "function": {"name": "submit_answer"}}
            resp = llm.chat(self.deployment, messages, TOOLS, salt=f"trial{t.trial}", **params)
            msg = llm.message(resp)
            calls = msg.get("tool_calls") or []
            if not calls:
                return score(t, (), False, f"no tool call, no answer: {str(msg.get('content'))[:80]}")
            messages.append({"role": "assistant", "content": msg.get("content"),
                             "tool_calls": calls})
            for call in calls:
                fn = call["function"]["name"]
                args = llm.tool_args(call)
                if fn == "submit_answer":
                    named = tuple(str(s)[:7] for s in (args.get("commits") or []))
                    refused = bool(args.get("refused"))
                    why = str(args.get("rationale", ""))[:160]
                    rejected: list[str] = []
                    if self.guarded and named:
                        named, rejected = temporal_check(t, named)
                        if not named:
                            refused = True
                            why = f"date check rejected {rejected}: none lands just before the movement"
                    r = score(t, named, refused, why)
                    r.tags["date_rejected"] = rejected
                    r.tags["model_refused"] = bool(args.get("refused"))
                    r.tags["tool_calls"] = used
                    return r
                if self.guarded and used >= MAX_TOOL_CALLS - 1:
                    # A single turn can carry 6 parallel calls and jump straight past
                    # the forced-answer turn (v1 hit 11 calls on an 8 budget). Every
                    # call id still needs a reply, so the overflow gets a refusal note.
                    messages.append({"role": "tool", "tool_call_id": call["id"],
                                     "content": json.dumps({"error": "tool budget reached; submit_answer now"})})
                    continue
                used += 1
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": self._dispatch(fn, args, t)})
        r = score(t, (), False, f"tool budget exhausted after {used} calls without submit_answer")
        r.tags["tool_calls"] = used
        r.tags["budget_exhausted"] = True
        return r


class TelemetryAttributionSuite(Suite):
    name = "telemetry-attribution"
    # Balanced, not raw: 9 of 15 trials are refusal cases, so raw accuracy hands
    # always-refuse 60% for doing nothing. Balanced accuracy gives it exactly 50%.
    headline = "balanced_accuracy"
    margin = 0.05
    tolerance = 0.10

    def cases(self) -> list[Trial]:
        tel, gl = _Data.get()
        findings = {f.id: f for f in detect_mod.run_all(tel)}
        out = []
        for c in cases_mod.CASES + EXTRA_REFUSALS:
            f = findings[c.finding_id]
            w = build_window(gl, f, c)
            out += [Trial(c, f, w, k) for k in range(TRIALS)]
        return out

    def baselines(self):
        return [AlwaysGuess(), AlwaysRefuse()]

    def systems(self):
        return [ToolLoopAgent("gpt-41-mini", guarded=False, temperature=0.0),
                ToolLoopAgent("gpt-5-mini", guarded=False),
                ToolLoopAgent("gpt-41-mini", temperature=0.0),
                ToolLoopAgent("gpt-5-mini")]

    def metrics(self, results: list[CaseResult]) -> dict[str, float]:
        n = len(results) or 1
        pos = [r for r in results if not r.tags.get("refusal_case")]
        neg = [r for r in results if r.tags.get("refusal_case")]
        by_case: dict[str, list[bool]] = {}
        for r in results:
            by_case.setdefault(r.tags.get("case", r.case_id), []).append(r.passed)
        recall = sum(r.passed for r in pos) / (len(pos) or 1)
        refusal = sum(r.passed for r in neg) / (len(neg) or 1)
        truth = {c.id: set(c.ground_truth) for c in cases_mod.CASES}
        named_total = sum(len(r.tags.get("named") or []) for r in pos)
        named_right = sum(len(set(r.tags.get("named") or []) & truth.get(r.tags.get("case"), set()))
                          for r in pos)
        return {
            "balanced_accuracy": (recall + refusal) / 2,
            # Of the commits it named on real-cause cases, how many were the cause. The
            # scorer passes a case if ANY named commit is right; this shows the shotgun.
            "attribution_precision": named_right / named_total if named_total else 0.0,
            # Refusals the MODEL chose, as opposed to ones the date check forced.
            "model_refusal": sum(bool(r.tags.get("model_refused")) for r in neg) / (len(neg) or 1),
            "accuracy": sum(r.passed for r in results) / n,
            "attribution_recall": recall,
            "correct_refusal": refusal,
            # pass^k: a case counts only if EVERY trial passed — the consistency bar
            "pass_all_trials": sum(all(v) for v in by_case.values()) / (len(by_case) or 1),
            "budget_exhausted": sum(bool(r.tags.get("budget_exhausted")) for r in results) / n,
        }


SUITE = TelemetryAttributionSuite()
