"""Markdown report: gate verdict, per-system metrics, failing cases, cost and latency.

Written to projects/<name>/results/REPORT.md and, inside GitHub Actions, appended to
the job summary so the verdict is readable on the PR without opening logs.
"""

from __future__ import annotations

import os
from pathlib import Path

from .core import GateResult, Suite, SystemRun, results_dir


COUNT_PREFIXES = ("wrong_", "n_", "count_")


def _fmt(key: str, x: float) -> str:
    if key.startswith(COUNT_PREFIXES):
        return f"{x:g}"
    return f"{x * 100:.1f}%" if 0 <= x <= 1 else f"{x:.3f}"


def render(suite: Suite, runs: list[SystemRun], g: GateResult, mode: str,
           trace_path: Path | None) -> str:
    keys: list[str] = []
    for r in runs:  # union, in first-seen order: candidates may report extra metrics
        keys += [k for k in r.metrics if k not in keys]
    out = [f"# {suite.name} — eval report", "",
           f"**Gate: {'PASS ✅' if g.passed else 'FAIL ❌'}** · mode `{mode}` · "
           f"headline `{suite.headline}`", ""]
    out += ["```", *g.reasons, "```", ""]
    out += ["| system | " + " | ".join(keys) + " | cost (USD) | wall (s) |",
            "|---|" + "---|" * len(keys) + "---|---|"]
    for r in runs:
        label = (f"{r.system} *(baseline)*" if r.is_baseline
                 else f"{r.system} *(ungated reference)*" if not r.gated else f"**{r.system}**")
        out.append(f"| {label} | " + " | ".join(_fmt(k, r.metrics[k]) if k in r.metrics else "—" for k in keys)
                   + f" | {r.cost_usd:.4f} | {r.wall_s:.1f} |")
    out.append("")
    cand = [r for r in runs if not r.is_baseline]
    for r in cand:
        bad = [c for c in r.results if not c.passed]
        out.append(f"## {r.system}: {len(bad)} of {len(r.results)} cases not passed")
        if bad:
            out += ["", "| case | score | detail |", "|---|---|---|"]
            for c in bad[:40]:
                d = (c.error or c.detail).replace("|", "/").replace("\n", " ")[:160]
                out.append(f"| `{c.case_id}` | {c.score:.2f} | {d} |")
        out.append("")
    if mode == "replay":
        out.append("_Replayed from cassettes: $0 spent on this run. Costs shown are what the "
                   "recorded calls cost when they were made live._")
    if trace_path:
        out.append(f"\nTrace: `{trace_path.relative_to(trace_path.parents[1])}`")
    return "\n".join(out) + "\n"


def write(project: str, suite: str, text: str) -> Path:
    p = results_dir(project, suite) / "REPORT.md"
    p.write_text(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(text + "\n")
    return p
