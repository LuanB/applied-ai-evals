"""Deterministic detection. Arithmetic lives here and ONLY here.

The governing design rule, carried from an earlier production performance digest:

    The LLM must never decide whether a number moved.

A model deciding whether p95 shifted is slower, costlier and non-deterministic, and
it cannot be regression-tested. Detection is arithmetic; explanation is judgement.
This module does the arithmetic and emits a Finding — a movement stated in numbers,
with a window. The explain stage receives Findings as FACTS it may not recompute.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from substrate import Telemetry


@dataclass
class Finding:
    """One detected movement. This is the unit handed to the explain stage."""

    id: str
    metric: str
    summary: str            # numbers, already computed — the model restates, never recomputes
    window_start: dt.date   # search window for a causal commit
    window_end: dt.date
    subsystem_hints: tuple[str, ...] = ()   # path substrings for a bounded git query
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_prompt_facts(self) -> str:
        return (
            f"FINDING {self.id}\n"
            f"  metric : {self.metric}\n"
            f"  movement: {self.summary}\n"
            f"  window : {self.window_start} .. {self.window_end}\n"
        )


def _pct(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    i = min(int(len(sorted_vals) * q), len(sorted_vals) - 1)
    return sorted_vals[i]


# --------------------------------------------------------------------------
# detector 1 — field appearance
# --------------------------------------------------------------------------


def detect_field_appearance(tel: Telemetry, name: str,
                            min_rows: int = 20) -> Finding | None:
    """A telemetry field goes from absent to present.

    This is a distinct detector class from "a number moved", and it is the archetype
    of the hidden-cost incident: a quantity that is not emitted cannot be counted,
    so telemetry looks healthy while the invoice does not. The movement is in the
    SCHEMA, not in a value.
    """
    cov = tel.field_coverage(name)
    if not cov:
        return None
    days = sorted(cov)
    first = next((d for d in days if cov[d][0] >= min_rows), None)
    if first is None:
        return None

    all_days = sorted({d for d in tel.field_coverage("ts")} | set(days)) or days
    total, nonzero = cov[first]
    return Finding(
        id=f"field_appearance:{name}",
        metric=f"telemetry field `{name}`",
        summary=(
            f"absent from every row before {first}, then present on {total} rows "
            f"on {first} itself ({nonzero} of them non-zero). The field did not "
            f"start being non-zero — it started EXISTING."
        ),
        window_start=first - dt.timedelta(days=7),
        window_end=first,
        subsystem_hints=("telemetry", "cost", "pricing", "usage"),
        evidence={"first_day": first.isoformat(), "rows": total, "nonzero": nonzero},
    )


# --------------------------------------------------------------------------
# detector 2 — step change in a daily distribution
# --------------------------------------------------------------------------


def detect_step_change(daily: dict[dt.date, list[float]], metric: str, detector_id: str,
                       quantile: float = 0.9, min_days: int = 5, min_n: int = 5,
                       ratio: float = 2.0,
                       subsystem_hints: tuple[str, ...] = ()) -> Finding | None:
    """Largest sustained step in a daily quantile.

    Compares each day's quantile against the median of the preceding `min_days`
    eligible days. Reports the biggest ratio that clears `ratio`. Deliberately
    simple and fully deterministic — the point is that the same input always yields
    the same Finding, so the eval scores the EXPLANATION, never the detection.
    """
    days = [d for d in sorted(daily) if len(daily[d]) >= min_n]
    if len(days) < min_days + 1:
        return None

    best: tuple[float, dt.date, float, float] | None = None
    for i in range(min_days, len(days)):
        d = days[i]
        cur = _pct(daily[d], quantile)
        prior = sorted(_pct(daily[p], quantile) for p in days[i - min_days:i])
        base = prior[len(prior) // 2]
        if base <= 0:
            continue
        r = cur / base
        if r >= ratio and (best is None or r > best[0]):
            best = (r, d, base, cur)

    if best is None:
        return None
    r, d, base, cur = best
    qlabel = f"p{int(quantile * 100)}"
    return Finding(
        id=detector_id,
        metric=metric,
        summary=(
            f"{qlabel} rose from {base:.0f} (median of the 5 preceding active days) "
            f"to {cur:.0f} on {d} — a {r:.1f}x step."
        ),
        window_start=d - dt.timedelta(days=3),
        window_end=d + dt.timedelta(days=2),
        subsystem_hints=subsystem_hints,
        evidence={"day": d.isoformat(), "baseline": base, "value": cur, "ratio": round(r, 2)},
    )


def detect_tool_spiral(tel: Telemetry) -> Finding | None:
    daily = {d: [float(x) for x in v] for d, v in tel.tool_calls_per_run().items()}
    return detect_step_change(
        daily,
        metric="tool calls per agent run",
        detector_id="step:tool_calls_per_run",
        quantile=0.9,
        subsystem_hints=("agent", "tools", "budget", "connector"),
    )


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------


def run_all(tel: Telemetry) -> list[Finding]:
    out: list[Finding] = []
    for name in ("reasoningTokens",):
        f = detect_field_appearance(tel, name)
        if f:
            out.append(f)
    f = detect_tool_spiral(tel)
    if f:
        out.append(f)
    for kind, fld, hints in (
        ("live_asr_window", "audioDurationMs", ("asr", "perception", "window")),
        ("gather_turn", "promptTokens", ("gather", "prompt", "surfacing")),
    ):
        f = detect_step_change(
            tel.daily_values(kind, fld), metric=f"{kind}.{fld}",
            detector_id=f"step:{kind}.{fld}", subsystem_hints=hints,
        )
        if f:
            out.append(f)
    return out


if __name__ == "__main__":
    tel = Telemetry.load()
    lo, hi = tel.date_range()
    print(f"substrate: {len(tel.rows)} rows, {lo} .. {hi}\n")
    for f in run_all(tel):
        print(f.as_prompt_facts())
