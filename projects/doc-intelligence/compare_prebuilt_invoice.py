"""Side comparison (not gated): Azure Document Intelligence's prebuilt-invoice model vs
the two LLM extractors, on the 20 commercial invoices, over the fields prebuilt-invoice
has an equivalent for. Run through evalgate, so it is cassette-backed and capped.

    EVALGATE_MODE=record python projects/doc-intelligence/compare_prebuilt_invoice.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from evalgate import llm  # noqa: E402

llm.set_project("doc-intelligence")
import suite as S  # noqa: E402

MAP = {"invoice_number": "InvoiceId", "invoice_date": "InvoiceDate", "seller": "VendorName",
       "buyer": "CustomerName", "total_amount": "InvoiceTotal"}

pages = [p for p in S.load("trade", "test") if p.label == "commercial_invoice"]
score = {"prebuilt-invoice": [0, 0], "prebuilt-invoice(en-AU)": [0, 0], "llm-layout": [0, 0],
         "llm-vision": [0, 0]}
misses: dict[str, list[str]] = {k: [] for k in score}
for p in pages:
    pre = llm.di_analyze("prebuilt-invoice", p.path, p.id)["fields"]
    # Same model, told the documents are Australian: dates are day-first.
    au = llm.di_analyze("prebuilt-invoice", p.path, p.id, locale="en-AU")["fields"]
    got = {"prebuilt-invoice": {k: (pre.get(v) or {}).get("value") for k, v in MAP.items()},
           "prebuilt-invoice(en-AU)": {k: (au.get(v) or {}).get("value") for k, v in MAP.items()},
           "llm-layout": S.LlmLayout().extract(p), "llm-vision": S.LlmVisionExtract().extract(p)}
    for system, g in got.items():
        for k in MAP:
            ok = S.norm(k, g.get(k)) == S.norm(k, p.fields[k])
            score[system][0] += ok
            score[system][1] += 1
            if not ok:
                misses[system].append(f"{p.id} {k}: {g.get(k)!r} vs {p.fields[k]!r}")

lines = ["# prebuilt-invoice vs LLM extraction (20 invoices, 5 shared fields)", "",
         "| system | fields right |", "|---|---|"]
for system, (r, n) in score.items():
    lines.append(f"| {system} | {r}/{n} ({100 * r / n:.0f}%) |")
for system, m in misses.items():
    if m:
        lines += ["", f"**{system} misses:**", *[f"- `{x}`" for x in m[:10]]]
out = Path(__file__).parent / "results" / "prebuilt_invoice.md"
out.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
