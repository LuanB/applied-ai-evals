"""Labelled eval cases. Ground truth is the commit.

A case is (detector output) -> (the commit that explains it, or NOTHING).

The `expect_refusal` cases are the point of this file. A harness that only asks
"did it name the right commit?" will happily pass an agent that invents a cause for
every movement, because there is ALWAYS a commit in the window. Refusal cases are
what make this an eval rather than a demo.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class Case:
    id: str
    finding_id: str                       # which detector output this case is about
    ground_truth: tuple[str, ...] = ()    # short SHAs; empty == nothing explains it
    expect_refusal: bool = False
    window_override: tuple[dt.date, dt.date] | None = None
    max_named: int = 3                    # naming everything is not an answer
    note: str = ""


CASES: list[Case] = [
    Case(
        id="case1-hidden-thinking-tokens",
        finding_id="field_appearance:reasoningTokens",
        ground_truth=("5c0d634",),
        note=(
            "Archetype: telemetry looked fine, the bill did not. Cost was under-"
            "reported because thinking tokens were never counted. Detector fires on "
            "the SCHEMA change (field starts existing), not on a value moving."
        ),
    ),
    Case(
        id="case3-tool-call-spiral",
        finding_id="step:tool_calls_per_run",
        ground_truth=("77d9c90",),
        note=(
            "RELABELLED 2026-10-04 (was fd10d27). p90 tool calls/run 7 -> 19 on 07-17 UTC, "
            "27 on 07-18. Every spiral run is google/gemini-3.5-flash; that model goes from "
            "2 runs/day to 23 (07-17) and 43 (07-18). 77d9c90 'conversationAnswer role — "
            "conversation consults one tier up' rewires modelRegistry for the mobile answer "
            "path, committed 2026-07-18 00:54 +1000 = 07-17 14:54 UTC. CORRECTION: the "
            "first elevated runs (12 and 18 calls, gemini-3.5-flash) start at 14:20 UTC, "
            "34 min BEFORE that commit; consistent with the change running in a local dev "
            "build before it was committed, but unproven. fd10d27 'per-run search budget to "
            "cap ... spirals' lands at 07-18 06:43 UTC, ~16h AFTER onset: it is the "
            "MITIGATION, so the old label is wrong either way. Confidence in 77d9c90: "
            "plausible, unconfirmed. Pending owner confirmation."
        ),
    ),
    # ---- refusal ----
    Case(
        id="refusal-shifted-window",
        finding_id="step:tool_calls_per_run",
        ground_truth=(),
        expect_refusal=True,
        window_override=(dt.date(2026, 6, 20), dt.date(2026, 6, 25)),
        note=(
            "The SAME real movement, presented with a window that excludes the causal "
            "commit. Commits exist in this window, so an agent that pattern-matches "
            "'find the most plausible commit' will confabulate. Correct answer: the "
            "numbers do not support a cause in this window."
        ),
    ),
]


# Cases that are NOT measurable in this substrate. Kept explicitly so they are not
# silently re-added by someone reading the substrate README.
UNMEASURABLE: list[tuple[str, str]] = [
    (
        "case2-zero-cache-hit",
        "The 0%-cache incident (b3ef5ce / e06e9b5) was OpenAI-specific, but ZERO "
        "rows carrying cache fields also carry an OpenAI model or provider: of 3559 "
        "cache-bearing rows, `provider` is absent on 3198 and `model` on 3538, and "
        "no gpt* row carries a cache field at all. The OpenAI cache signature cannot "
        "be isolated here, so the case cannot be scored. Fix requires re-exporting "
        "telemetry with provider stamped on every emit path, not a harness change.",
    ),
    (
        "case4-asr-window-20s-to-30s",
        "A 20s -> 30s change is a 1.5x step, below the 2.0x detector threshold. "
        "Lowering the threshold to catch it admits false positives elsewhere. Needs a "
        "dedicated known-boundary detector, not a looser generic one.",
    ),
]


@dataclass
class Result:
    case_id: str
    passed: bool
    reason: str
    named: tuple[str, ...] = ()
    refused: bool = False


def score(case: Case, named: tuple[str, ...], refused: bool) -> Result:
    named = tuple(n[:7] for n in named)

    if case.expect_refusal:
        if refused and not named:
            return Result(case.id, True, "correctly refused", named, refused)
        return Result(
            case.id, False,
            f"should have refused; named {list(named) or '[]'}", named, refused,
        )

    if refused:
        return Result(case.id, False, "refused a case with a real cause", named, refused)
    if len(named) > case.max_named:
        return Result(
            case.id, False,
            f"named {len(named)} commits (max {case.max_named}) — shotgunning is not an answer",
            named, refused,
        )
    hit = set(case.ground_truth) & set(named)
    if hit:
        return Result(case.id, True, f"named {sorted(hit)}", named, refused)
    return Result(
        case.id, False,
        f"missed {list(case.ground_truth)}; named {list(named) or '[]'}", named, refused,
    )
