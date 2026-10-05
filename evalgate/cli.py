"""evalgate run <project> [--only SYSTEM] [--limit N]
evalgate bless <project>      # promote latest.json to the regression floor
evalgate spend                # ledger summary against the caps

Exit code 1 when the gate fails, so CI blocks the merge.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time

from . import cassette, core, llm, report, spend, trace


def split(target: str) -> tuple[str, str | None]:
    project, _, name = target.partition(":")
    return project, name or None


def load_suite(target: str) -> core.Suite:
    project, name = split(target)
    path = core.ROOT / "projects" / project / "suite.py"
    if not path.exists():
        raise SystemExit(f"no suite at {path}")
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(f"suite_{project.replace('-', '_')}", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[spec.name] = mod  # dataclasses resolve annotations via sys.modules
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if name:
        return mod.SUITES[name]
    return mod.SUITE


def cmd_run(args: argparse.Namespace) -> int:
    project, _ = split(args.project)
    llm.set_project(project)
    suite = load_suite(args.project)
    mode = cassette.mode()
    run_id = f"{suite.name}-{time.strftime('%Y%m%d-%H%M%S')}"
    tpath = trace.setup(run_id)
    cases = suite.cases()
    if args.limit:
        cases = cases[: args.limit]
    print(f"{suite.name}: {len(cases)} cases, mode={mode}")
    runs: list[core.SystemRun] = []
    for b in suite.baselines():
        runs.append(core.run_system(suite, b, cases, is_baseline=True))
        print(f"  baseline {b.name:<34} {suite.headline}={runs[-1].metrics[suite.headline]:.3f}")
    for s in suite.systems():
        if args.only and s.name not in args.only:
            continue
        runs.append(core.run_system(suite, s, cases, is_baseline=False))
        r = runs[-1]
        print(f"  system   {s.name:<34} {suite.headline}={r.metrics[suite.headline]:.3f} "
              f"cost=${r.cost_usd:.4f}")
    g = core.gate(suite, runs, core.load_floor(project, suite.name))
    core.save(project, suite, runs, g, mode)
    text = report.render(suite, runs, g, mode, tpath)
    p = report.write(project, suite.name, text)
    print("\n".join("  " + r for r in g.reasons))
    print(f"GATE {'PASS' if g.passed else 'FAIL'}  report: {p.relative_to(core.ROOT)}")
    if mode != "replay":
        print(spend.summary())
    return 0 if g.passed else 1


def main() -> None:
    ap = argparse.ArgumentParser(prog="evalgate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("project")
    r.add_argument("--only", nargs="*")
    r.add_argument("--limit", type=int)
    b = sub.add_parser("bless")
    b.add_argument("project")
    sub.add_parser("spend")
    args = ap.parse_args()
    if args.cmd == "run":
        sys.exit(cmd_run(args))
    if args.cmd == "bless":
        project, _ = split(args.project)
        print(core.bless(project, load_suite(args.project).name))
    if args.cmd == "spend":
        print(spend.summary())


if __name__ == "__main__":
    main()
