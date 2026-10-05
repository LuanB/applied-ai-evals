"""Spend ledger with a hard cap.

Every live (billed) call appends one line to `spend/ledger.jsonl` with its estimated
cost. Before a live call is made, the ledger is summed; if the provider's total would
pass its cap, the call is refused with SpendCapExceeded. Replayed calls cost nothing
and are never written.

Prices are list prices per 1M tokens (or per 1K pages), padded by PRICE_PAD so the
estimate errs high. The ledger is an estimate; the provider invoice is the truth, and
the two are reconciled by hand in spend/RECONCILE.md.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "spend" / "ledger.jsonl"
PRICE_PAD = 1.2

# USD per 1M tokens: (input, cached_input, output)
TOKEN_PRICES: dict[str, tuple[float, float, float]] = {
    "gpt-41-mini": (0.40, 0.10, 1.60),
    "gpt-5-mini": (0.25, 0.025, 2.00),
    "gpt-oss-120b": (0.15, 0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.02, 0.0),
    # Bedrock (ap-southeast-2 / global inference profiles)
    "claude-haiku-4-5": (1.00, 0.10, 5.00),
    "nova-lite": (0.06, 0.015, 0.24),
}
# USD per 1K pages
PAGE_PRICES: dict[str, float] = {
    "prebuilt-read": 1.50,
    "prebuilt-layout": 10.00,
    "prebuilt-invoice": 10.00,
    "prebuilt-receipt": 10.00,
}
# USD per 1K text records
RECORD_PRICES: dict[str, float] = {
    "prompt-shields": 0.38,
}

DEFAULT_CAPS = {"azure": 85.0, "aws": 15.0}
# Owner-approved ceiling across ALL providers (raised to $100 combined, 2026-10-04). Per-provider caps are
# working limits; a provider may run past its own cap only while the combined total
# stays under this, and only with EVALGATE_ALLOW_COMBINED=1.
COMBINED_CAP = 100.0

_lock = threading.Lock()


class SpendCapExceeded(RuntimeError):
    pass


def cap(provider: str) -> float:
    env = os.environ.get(f"EVALGATE_CAP_{provider.upper()}_USD")
    return float(env) if env else DEFAULT_CAPS[provider]


def total(provider: str) -> float:
    if not LEDGER.exists():
        return 0.0
    s = 0.0
    for line in LEDGER.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row["provider"] == provider:
                s += row["usd"]
    return s


def token_cost(model: str, prompt: int, completion: int, cached: int = 0) -> float:
    key = next((k for k in TOKEN_PRICES if k in model), None)
    if key is None:
        raise KeyError(f"no price for model '{model}' — add it to TOKEN_PRICES before a live run")
    pin, pcached, pout = TOKEN_PRICES[key]
    usd = ((prompt - cached) * pin + cached * pcached + completion * pout) / 1e6
    return usd * PRICE_PAD


def page_cost(model: str, pages: int) -> float:
    return PAGE_PRICES[model] * pages / 1000 * PRICE_PAD


def record_cost(service: str, records: int) -> float:
    return RECORD_PRICES[service] * records / 1000 * PRICE_PAD


def combined_total() -> float:
    return sum(total(p) for p in DEFAULT_CAPS)


def check(provider: str, upcoming_usd: float = 0.0) -> None:
    if combined_total() + upcoming_usd > COMBINED_CAP:
        raise SpendCapExceeded(f"combined spend would pass the ${COMBINED_CAP:.2f} owner-approved ceiling")
    spent = total(provider)
    if os.environ.get("EVALGATE_ALLOW_COMBINED") == "1":
        return
    if spent + upcoming_usd > cap(provider):
        raise SpendCapExceeded(
            f"{provider} spend ${spent:.4f} + ${upcoming_usd:.4f} would pass the "
            f"${cap(provider):.2f} cap. Raise EVALGATE_CAP_{provider.upper()}_USD only "
            f"with the account owner's say-so.")


def record(provider: str, model: str, usd: float, project: str, detail: str = "") -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "provider": provider, "model": model,
           "usd": round(usd, 6), "project": project, "detail": detail[:80]}
    with _lock, LEDGER.open("a") as f:
        f.write(json.dumps(row) + "\n")


def summary() -> str:
    if not LEDGER.exists():
        return "no live spend recorded"
    by: dict[tuple[str, str], float] = {}
    for line in LEDGER.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            by[(r["provider"], r["project"])] = by.get((r["provider"], r["project"]), 0) + r["usd"]
    lines = [f"{p:<6} {proj:<28} ${usd:8.4f}" for (p, proj), usd in sorted(by.items())]
    for p in DEFAULT_CAPS:
        lines.append(f"{p:<6} {'TOTAL':<28} ${total(p):8.4f} of ${cap(p):.2f} cap")
    lines.append(f"{'all':<6} {'COMBINED':<28} ${combined_total():8.4f} of ${COMBINED_CAP:.2f} ceiling")
    return "\n".join(lines)
