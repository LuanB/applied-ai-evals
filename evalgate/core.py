"""Suite contract, runner and gate.

A project plugs in by exposing `SUITE` in projects/<name>/suite.py:

    cases()      -> the labelled cases (the answer key)
    systems()    -> the candidate systems under test
    baselines()  -> degenerate systems the candidate MUST beat
    metrics()    -> results -> {metric: value}; `headline` names the one the gate uses

The gate passes only if, for every candidate:
  1. its headline metric beats the BEST baseline by at least `margin`, and
  2. it has not regressed more than `tolerance` below the blessed floor
     (results/floor.json), and
  3. every hard constraint in `constraints` holds (e.g. false_block_rate <= 0.10).

Baselines come first for a reason: before trusting a scorer, prove it can fail. If a
baseline that refuses everything scores 90%, the cases are not binding and every
number the suite produces is meaningless.
"""

from __future__ import annotations

import json
import operator
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from . import llm
from .trace import tracer

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    score: float               # 0..1; for pass/fail cases score == float(passed)
    detail: str = ""
    tags: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0
    wall_s: float = 0.0
    error: str = ""


class System(Protocol):
    name: str

    def run(self, case: Any) -> CaseResult: ...


@dataclass
class SystemRun:
    system: str
    is_baseline: bool
    results: list[CaseResult]
    metrics: dict[str, float]
    cost_usd: float
    wall_s: float
    gated: bool = True


OPS: dict[str, Callable[[float, float], bool]] = {
    "<=": operator.le, ">=": operator.ge, "<": operator.lt, ">": operator.gt,
}


class Suite:
    name: str = "suite"
    headline: str = "accuracy"
    margin: float = 0.0
    tolerance: float = 0.05
    workers: int = 1
    constraints: dict[str, tuple[str, float]] = {}

    def cases(self) -> list[Any]:
        raise NotImplementedError

    def systems(self) -> list[System]:
        raise NotImplementedError

    def baselines(self) -> list[System]:
        return []

    def case_tags(self, case: Any) -> dict[str, Any]:
        """Tags an errored case still carries, so metrics can bucket it."""
        return {}

    def case_id(self, case: Any) -> str:
        return getattr(case, "id", str(case))

    def metrics(self, results: list[CaseResult]) -> dict[str, float]:
        n = len(results) or 1
        return {"accuracy": sum(r.score for r in results) / n,
                "pass_rate": sum(r.passed for r in results) / n}


def _run_case(suite: Suite, system: System, case: Any, parent_ctx) -> CaseResult:
    from opentelemetry import context as otel_context
    token = otel_context.attach(parent_ctx)
    try:
        cid = suite.case_id(case)
        with tracer().start_as_current_span("case") as span:
            span.set_attribute("evalgate.suite", suite.name)
            span.set_attribute("evalgate.system", system.name)
            span.set_attribute("evalgate.case", cid)
            llm.reset_case_cost()
            t0 = time.perf_counter()
            try:
                r = system.run(case)
            except Exception as e:  # a crash is a failed case, never a skipped one
                r = CaseResult(cid, False, 0.0, error=f"{type(e).__name__}: {e}"[:300],
                               tags=suite.case_tags(case))
            r.cost_usd = round(llm.case_cost(), 6)
            r.wall_s = round(time.perf_counter() - t0, 2)
            span.set_attribute("evalgate.passed", r.passed)
            span.set_attribute("evalgate.score", r.score)
            span.set_attribute("evalgate.cost_usd", r.cost_usd)
            if r.error:
                span.set_attribute("evalgate.error", r.error)
        return r
    finally:
        otel_context.detach(token)


def run_system(suite: Suite, system: System, cases: Iterable[Any], is_baseline: bool) -> SystemRun:
    import contextvars
    from concurrent.futures import ThreadPoolExecutor

    from opentelemetry import context as otel_context
    t_sys = time.perf_counter()
    cases = list(cases)
    ctx = otel_context.get_current()
    if suite.workers > 1:
        with ThreadPoolExecutor(suite.workers) as pool:
            futs = [pool.submit(contextvars.copy_context().run, _run_case, suite, system, c, ctx)
                    for c in cases]
            results = [f.result() for f in futs]
    else:
        results = [_run_case(suite, system, c, ctx) for c in cases]
    return SystemRun(system.name, is_baseline, results, suite.metrics(results),
                     round(sum(r.cost_usd for r in results), 6),
                     round(time.perf_counter() - t_sys, 2),
                     gated=getattr(system, "gated", True))


@dataclass
class GateResult:
    passed: bool
    reasons: list[str]


def gate(suite: Suite, runs: list[SystemRun], floor: dict[str, float] | None) -> GateResult:
    reasons: list[str] = []
    ok = True
    base = [r for r in runs if r.is_baseline]
    cand = [r for r in runs if not r.is_baseline and r.gated]
    for r in runs:
        if not r.is_baseline and not r.gated:
            reasons.append(f"info {r.system}: ungated reference, {suite.headline} "
                           f"{r.metrics[suite.headline]:.3f}")
    best_base = max((r.metrics[suite.headline] for r in base), default=None)
    for c in cand:
        h = c.metrics[suite.headline]
        errors = sum(1 for r in c.results if r.error)
        if errors:
            ok = False
            reasons.append(f"FAIL {c.system}: {errors} case(s) errored (see report)")
        if best_base is not None:
            if h > best_base + suite.margin - 1e-9:
                reasons.append(f"ok   {c.system}: {suite.headline} {h:.3f} beats best baseline "
                               f"{best_base:.3f} (margin {suite.margin:.2f})")
            else:
                ok = False
                reasons.append(f"FAIL {c.system}: {suite.headline} {h:.3f} does not beat best "
                               f"baseline {best_base:.3f} by margin {suite.margin:.2f}")
        if floor and c.system in floor:
            f = floor[c.system]
            if h + suite.tolerance < f:
                ok = False
                reasons.append(f"FAIL {c.system}: regressed {h:.3f} vs blessed floor {f:.3f} "
                               f"(tolerance {suite.tolerance:.2f})")
            else:
                reasons.append(f"ok   {c.system}: within tolerance of floor {f:.3f}")
        for metric, (op, limit) in suite.constraints.items():
            v = c.metrics.get(metric)
            if v is None or not OPS[op](v, limit):
                ok = False
                reasons.append(f"FAIL {c.system}: constraint {metric} {op} {limit} (got {v})")
            else:
                reasons.append(f"ok   {c.system}: {metric} {v:.3f} {op} {limit}")
    return GateResult(ok, reasons)


def results_dir(project: str, suite: str | None = None) -> Path:
    d = ROOT / "projects" / project / "results" / (suite or project)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(project: str, suite: Suite, runs: list[SystemRun], g: GateResult, mode: str) -> Path:
    out = {
        "suite": suite.name, "headline": suite.headline, "mode": mode,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "gate": asdict(g),
        "runs": [asdict(r) for r in runs],
    }
    p = results_dir(project, suite.name) / "latest.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    return p


def load_floor(project: str, suite: str) -> dict[str, float] | None:
    p = results_dir(project, suite) / "floor.json"
    return json.loads(p.read_text()) if p.exists() else None


def bless(project: str, suite: str) -> dict[str, float]:
    latest = json.loads((results_dir(project, suite) / "latest.json").read_text())
    floor = {r["system"]: r["metrics"][latest["headline"]]
             for r in latest["runs"] if not r["is_baseline"] and r.get("gated", True)}
    (results_dir(project, suite) / "floor.json").write_text(json.dumps(floor, indent=1))
    return floor
