"""P2 — document intelligence on Azure: page classification + field extraction.

Two suites:

  doc-intelligence:classify  252 pages, two datasets scored separately
      rvl    160 real 1990s office scans (RVL-CDIP sample, 16 classes)
      trade   92 synthetic import-shipment pages (6 classes, a third untitled)
  doc-intelligence:extract    the 92 trade pages, every field scored

Systems compared (classification):
  majority         baseline: always the most common training class
  tfidf-centroid   baseline: classical bag-of-words on Document Intelligence OCR,
                   fitted on a DISJOINT training split, never on scored pages
  llm-text         gpt-4.1-mini reads the OCR text
  llm-vision       gpt-4.1-mini looks at the page image
  cascade          text first; escalate to vision only when the model is not sure

Systems compared (extraction; true class picks the schema so extraction is scored
on its own, not on top of classification errors):
  regex-on-ocr     baseline: one pattern per field, written from the field NAME the way
                   a developer reading the spec would — not from the generator's wording
  llm-layout       Document Intelligence layout (markdown, keeps tables and key/value
                   adjacency) -> gpt-4.1-mini structured output
  llm-vision       page image -> gpt-4.1-mini structured output
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evalgate import cassette, llm
from evalgate.core import CaseResult, Suite

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
MODEL = "gpt-41-mini"

RVL_CLASSES = ["letter", "form", "email", "handwritten", "advertisement", "scientific report",
               "scientific publication", "specification", "file folder", "news article", "budget",
               "invoice", "presentation", "questionnaire", "resume", "memo"]
TRADE_CLASSES = ["commercial_invoice", "packing_list", "bill_of_lading", "certificate_of_origin",
                 "phytosanitary_certificate", "fumigation_certificate"]


@dataclass
class Page:
    id: str
    dataset: str
    label: str
    path: Path
    fields: dict[str, str] = field(default_factory=dict)
    titled: bool = True

    @property
    def classes(self) -> list[str]:
        return RVL_CLASSES if self.dataset == "rvl" else TRADE_CLASSES


def load(dataset: str, split: str) -> list[Page]:
    if dataset == "rvl":
        rows = json.loads((DATA / f"rvl_{split}_labels.json").read_text())
        return [Page(r["id"], "rvl", r["label"], DATA / "raw" / f"rvl_{split}" / f"{r['id']}.png")
                for r in rows]
    name = "trade_labels.json" if split == "test" else "trade_train_labels.json"
    folder = "synthetic" if split == "test" else "synthetic_train"
    rows = json.loads((DATA / name).read_text())
    return [Page(f"{split}-{r['id']}", "trade", r["label"], DATA / folder / f"{r['id']}.jpg",
                 r["fields"], r["titled"]) for r in rows]


def ocr(p: Page) -> str:
    return llm.di_analyze("prebuilt-read", p.path, p.id)["content"]


def image_or_placeholder(p: Page) -> dict[str, Any]:
    # In replay (CI) the images are not in the repo; the cassette is keyed on page id,
    # so the message body is never sent and a placeholder is enough.
    if p.path.exists():
        return llm.image_part(p.path)
    if cassette.mode() != "replay":
        raise FileNotFoundError(f"{p.path} — run fetch/generate before a live run")
    return {"type": "text", "text": f"[image {p.id} not present; replaying]"}


# ==========================================================================
# classification
# ==========================================================================

def result(p: Page, pred: str, extra: dict[str, Any] | None = None) -> CaseResult:
    ok = pred == p.label
    return CaseResult(p.id, ok, float(ok), f"pred={pred} true={p.label}",
                      tags={"dataset": p.dataset, "pred": pred, "true": p.label,
                            "titled": p.titled, **(extra or {})})


class Majority:
    name = "majority"

    def __init__(self):
        self.top = {d: Counter(x.label for x in load(d, "train")).most_common(1)[0][0]
                    for d in ("rvl", "trade")}

    def run(self, p: Page) -> CaseResult:
        return result(p, self.top[p.dataset])


TOKEN = re.compile(r"[a-z]{3,}")


class TfidfCentroid:
    """Classical baseline: tf-idf vectors, one centroid per class, cosine nearest."""

    name = "tfidf-centroid"

    def __init__(self):
        import threading
        self.models: dict[str, tuple[dict[str, float], dict[str, dict[str, float]]]] = {}
        self.lock = threading.Lock()

    def _fit(self, dataset: str):
        from concurrent.futures import ThreadPoolExecutor
        train = load(dataset, "train")
        with ThreadPoolExecutor(8) as pool:
            texts = list(pool.map(ocr, train))
        docs = [(x.label, Counter(TOKEN.findall(t.lower()))) for x, t in zip(train, texts)]
        df = Counter(t for _, c in docs for t in c)
        idf = {t: math.log(len(docs) / n) + 1 for t, n in df.items()}
        cents: dict[str, Counter] = {}
        for label, c in docs:
            cents.setdefault(label, Counter()).update({t: v * idf[t] for t, v in c.items()})
        self.models[dataset] = (idf, {k: self._norm(v) for k, v in cents.items()})

    @staticmethod
    def _norm(v: dict[str, float]) -> dict[str, float]:
        n = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {k: x / n for k, x in v.items()}

    def run(self, p: Page) -> CaseResult:
        with self.lock:  # fit once, not once per worker thread
            if p.dataset not in self.models:
                self._fit(p.dataset)
        idf, cents = self.models[p.dataset]
        c = Counter(TOKEN.findall(ocr(p).lower()))
        v = self._norm({t: n * idf.get(t, 0.0) for t, n in c.items()})
        best = max(cents, key=lambda k: sum(v.get(t, 0) * w for t, w in cents[k].items()))
        return result(p, best)


CLASSIFY_PROMPT = """You classify one scanned document page. Choose exactly one label from the
list. Judge by what the document IS, not by documents it mentions: an invoice that
quotes a packing list number is still an invoice. Report confidence honestly: "high"
only when the page is unambiguous."""


def _label_schema(classes: list[str]) -> dict[str, Any]:
    return {"type": "json_schema", "json_schema": {"name": "page_label", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": ["label", "confidence"],
        "properties": {"label": {"type": "string", "enum": classes},
                       "confidence": {"type": "string", "enum": ["high", "medium", "low"]}}}}}


def _parse(resp: dict[str, Any]) -> dict[str, str]:
    try:
        return json.loads(llm.message(resp).get("content") or "{}")
    except json.JSONDecodeError:
        return {"label": "unparseable", "confidence": "low"}


class LlmText:
    name = "llm-text"

    def classify(self, p: Page) -> dict[str, str]:
        text = ocr(p)[:6000]
        msgs = [{"role": "system", "content": CLASSIFY_PROMPT},
                {"role": "user", "content": f"Labels: {', '.join(p.classes)}\n\nOCR text of the page:\n{text}"}]
        return _parse(llm.chat(MODEL, msgs, temperature=0.0,
                               response_format=_label_schema(p.classes)))

    def run(self, p: Page) -> CaseResult:
        out = self.classify(p)
        return result(p, out.get("label", ""), {"confidence": out.get("confidence")})


class LlmVision:
    name = "llm-vision"

    def classify(self, p: Page) -> dict[str, str]:
        msgs = [{"role": "system", "content": CLASSIFY_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Labels: {', '.join(p.classes)}"},
                    image_or_placeholder(p)]}]
        return _parse(llm.chat(MODEL, msgs, temperature=0.0, response_format=_label_schema(p.classes),
                               cassette_key={"vision_classify": p.id, "classes": p.classes,
                                             "prompt": CLASSIFY_PROMPT}))

    def run(self, p: Page) -> CaseResult:
        out = self.classify(p)
        return result(p, out.get("label", ""), {"confidence": out.get("confidence")})


class Cascade:
    """Cheap text pass first; pay for vision only when the text pass is not sure."""

    name = "cascade"

    def __init__(self):
        self.text, self.vision = LlmText(), LlmVision()

    def run(self, p: Page) -> CaseResult:
        out = self.text.classify(p)
        escalated = out.get("confidence") != "high"
        if escalated:
            out = self.vision.classify(p)
        return result(p, out.get("label", ""), {"escalated": escalated,
                                                "confidence": out.get("confidence")})


def macro_f1(rs: list[CaseResult]) -> float:
    labels = {r.tags["true"] for r in rs}
    f1s = []
    for c in labels:
        tp = sum(r.tags["pred"] == c and r.tags["true"] == c for r in rs)
        fp = sum(r.tags["pred"] == c and r.tags["true"] != c for r in rs)
        fn = sum(r.tags["pred"] != c and r.tags["true"] == c for r in rs)
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(f1s) / len(f1s) if f1s else 0.0


class ClassifySuite(Suite):
    name = "classify"
    workers = 8
    # Headline is the REAL-scan set. The synthetic trade set saturated on the first run
    # (every system incl. the tf-idf baseline scored 100%, untitled pages too), so it
    # cannot discriminate and stays as a sanity check, not as part of the score.
    headline = "rvl_macro_f1"
    margin = 0.05
    tolerance = 0.05

    def cases(self) -> list[Page]:
        return load("rvl", "test") + load("trade", "test")

    def case_tags(self, p: Page) -> dict[str, Any]:
        return {"dataset": p.dataset, "true": p.label, "pred": "<error>", "titled": p.titled}

    def baselines(self):
        return [Majority(), TfidfCentroid()]

    def systems(self):
        return [LlmText(), LlmVision(), Cascade()]

    def metrics(self, results: list[CaseResult]) -> dict[str, float]:
        rvl = [r for r in results if r.tags.get("dataset") == "rvl"]
        trade = [r for r in results if r.tags.get("dataset") == "trade"]
        untitled = [r for r in trade if not r.tags.get("titled")]
        m = {
            # mean of the two datasets' macro-F1, so 160 easy-ish pages cannot drown 92
            "macro_f1": (macro_f1(rvl) + macro_f1(trade)) / 2 if rvl and trade else macro_f1(results),
            "rvl_accuracy": sum(r.passed for r in rvl) / (len(rvl) or 1),
            "rvl_macro_f1": macro_f1(rvl),
            "trade_accuracy": sum(r.passed for r in trade) / (len(trade) or 1),
            "trade_untitled_accuracy": sum(r.passed for r in untitled) / (len(untitled) or 1),
        }
        esc = [r for r in results if "escalated" in r.tags]
        if esc:
            m["escalation_rate"] = sum(r.tags["escalated"] for r in esc) / len(esc)
        return m


# ==========================================================================
# extraction
# ==========================================================================

SCHEMAS: dict[str, dict[str, str]] = {
    "commercial_invoice": {"invoice_number": "invoice number", "invoice_date": "invoice date",
                           "seller": "seller / exporter name", "buyer": "buyer / importer name",
                           "currency": "ISO currency code", "total_amount": "invoice total",
                           "incoterm": "Incoterm (e.g. FOB, CIF)", "hs_code": "HS tariff code"},
    "packing_list": {"packing_list_number": "packing list number",
                     "invoice_number": "referenced invoice number", "total_packages": "total packages",
                     "gross_weight_kg": "total gross weight in kg", "net_weight_kg": "total net weight in kg",
                     "container_number": "container number"},
    "bill_of_lading": {"bl_number": "bill of lading number", "shipper": "shipper", "consignee": "consignee",
                       "vessel": "vessel name", "voyage": "voyage number",
                       "port_of_loading": "port of loading", "port_of_discharge": "port of discharge",
                       "container_number": "container number (without seal)"},
    "certificate_of_origin": {"certificate_number": "certificate number", "exporter": "exporter",
                              "consignee": "consignee", "country_of_origin": "country of origin",
                              "hs_code": "HS tariff code"},
    "phytosanitary_certificate": {"certificate_number": "certificate number", "exporter": "exporter",
                                  "consignee": "consignee", "botanical_name": "botanical name",
                                  "place_of_origin": "place of origin"},
    "fumigation_certificate": {"certificate_number": "certificate number", "fumigant": "fumigant",
                               "dosage": "dosage rate", "exposure_hours": "exposure period in hours",
                               "date_of_fumigation": "date of fumigation",
                               "container_number": "container number"},
}

# What a developer writes from the field name alone.
REGEX_LABELS: dict[str, str] = {
    "invoice_number": r"invoice\s*(?:no|number)\.?", "invoice_date": r"(?:invoice\s*)?date",
    "seller": r"seller", "buyer": r"buyer", "currency": r"currency", "total_amount": r"total",
    "incoterm": r"incoterms?", "hs_code": r"hs\s*code", "packing_list_number": r"packing\s*list\s*(?:no|number)\.?",
    "total_packages": r"total\s*packages", "gross_weight_kg": r"gross\s*weight(?:\s*\(kg\))?",
    "net_weight_kg": r"net\s*weight(?:\s*\(kg\))?", "container_number": r"container(?:\s*no\.?)?",
    "bl_number": r"b/?l\s*no\.?", "shipper": r"shipper", "consignee": r"consignee", "vessel": r"vessel",
    "voyage": r"voyage", "port_of_loading": r"port\s*of\s*loading", "port_of_discharge": r"port\s*of\s*discharge",
    "certificate_number": r"certificate\s*no\.?", "exporter": r"exporter",
    "country_of_origin": r"country\s*of\s*origin", "botanical_name": r"botanical\s*name",
    "place_of_origin": r"place\s*of\s*origin", "fumigant": r"fumigant", "dosage": r"dosage(?:\s*rate)?",
    "exposure_hours": r"exposure(?:\s*period)?", "date_of_fumigation": r"date\s*of\s*fumigation",
}

DATE = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$|^(\d{4})-(\d{2})-(\d{2})$")


def norm(field_name: str, v: Any) -> str:
    s = str(v if v is not None else "").strip().lower()
    m = DATE.match(s)
    if m:
        dd, mm, yy = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(6), m.group(5), m.group(4))
        return f"{int(dd):02d}/{int(mm):02d}/{yy}"
    if field_name.endswith(("_kg", "_amount", "packages", "hours")):
        s = re.sub(r"[^\d.]", "", s).rstrip(".")
        try:
            return f"{float(s):.2f}"
        except ValueError:
            return s
    s = re.sub(r"[\s.,]+", " ", s).strip()
    return s


def score_fields(p: Page, got: dict[str, Any], system: str) -> CaseResult:
    want = p.fields
    right = [k for k in want if norm(k, got.get(k)) == norm(k, want[k])]
    wrong = {k: (got.get(k), want[k]) for k in want if k not in right}
    frac = len(right) / len(want)
    return CaseResult(p.id, frac == 1.0, frac,
                      "; ".join(f"{k}: got {g!r} want {w!r}" for k, (g, w) in list(wrong.items())[:3]),
                      tags={"right": len(right), "total": len(want), "class": p.label,
                            "wrong_fields": list(wrong), "got": {k: got.get(k) for k in want}})


class RegexOnOcr:
    name = "regex-on-ocr"

    def run(self, p: Page) -> CaseResult:
        text = ocr(p)
        got = {}
        for k in SCHEMAS[p.label]:
            m = re.search(REGEX_LABELS[k] + r"\s*:?\s*([^\n]+)", text, re.I)
            got[k] = m.group(1).strip() if m else None
        return score_fields(p, got, self.name)


EXTRACT_PROMPT = """Extract the requested fields from this shipping document page. Copy each value
exactly as printed (same spelling, same number format). Use null when a field is not
on the page. Do not infer values from other documents the page refers to."""


def _field_schema(fields: dict[str, str]) -> dict[str, Any]:
    return {"type": "json_schema", "json_schema": {"name": "fields", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": list(fields),
        "properties": {k: {"type": ["string", "null"], "description": d} for k, d in fields.items()}}}}


class LlmLayout:
    name = "llm-layout"

    def run(self, p: Page) -> CaseResult:
        return score_fields(p, self.extract(p), self.name)

    def extract(self, p: Page) -> dict[str, Any]:
        md = llm.di_analyze("prebuilt-layout", p.path, p.id, markdown=True)["content"][:8000]
        schema = SCHEMAS[p.label]
        msgs = [{"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": f"Document type: {p.label}\n\nPage (markdown from layout analysis):\n{md}"}]
        resp = llm.chat(MODEL, msgs, temperature=0.0, response_format=_field_schema(schema))
        try:
            return json.loads(llm.message(resp).get("content") or "{}")
        except json.JSONDecodeError:
            return {}


class LlmVisionExtract:
    name = "llm-vision"

    def run(self, p: Page) -> CaseResult:
        return score_fields(p, self.extract(p), self.name)

    def extract(self, p: Page) -> dict[str, Any]:
        schema = SCHEMAS[p.label]
        msgs = [{"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": [{"type": "text", "text": f"Document type: {p.label}"},
                                             image_or_placeholder(p)]}]
        resp = llm.chat(MODEL, msgs, temperature=0.0, response_format=_field_schema(schema),
                        cassette_key={"vision_extract": p.id, "schema": schema, "prompt": EXTRACT_PROMPT})
        try:
            return json.loads(llm.message(resp).get("content") or "{}")
        except json.JSONDecodeError:
            return {}


class ExtractSuite(Suite):
    name = "extract"
    workers = 8
    headline = "field_accuracy"
    margin = 0.05
    tolerance = 0.03

    def cases(self) -> list[Page]:
        return load("trade", "test")

    def case_tags(self, p: Page) -> dict[str, Any]:
        return {"right": 0, "total": len(p.fields), "class": p.label}

    def baselines(self):
        return [RegexOnOcr()]

    def systems(self):
        return [LlmLayout(), LlmVisionExtract()]

    def metrics(self, results: list[CaseResult]) -> dict[str, float]:
        right = sum(r.tags.get("right", 0) for r in results)
        total = sum(r.tags.get("total", 0) for r in results) or 1
        return {"field_accuracy": right / total,
                "page_all_fields_right": sum(r.passed for r in results) / (len(results) or 1)}


# ==========================================================================
# review routing: two independent readers, a human only where they disagree
# ==========================================================================

def review_result(p: Page, accepted: dict[str, Any], flagged: list[str]) -> CaseResult:
    want = p.fields
    acc_right = [k for k in accepted if norm(k, accepted[k]) == norm(k, want[k])]
    missed = [k for k in accepted if k not in acc_right]  # wrong AND auto-accepted: the costly kind
    return CaseResult(p.id, not missed, len(acc_right) / len(want),
                      f"flagged {flagged}; auto-accepted wrong {missed}" if (flagged or missed) else "",
                      tags={"accepted": len(accepted), "accepted_right": len(acc_right),
                            "flagged": len(flagged), "missed": missed, "total": len(want)})


class AcceptAllVision:
    """Baseline: trust the better single reader, review nothing."""
    name = "accept-all(llm-vision)"

    def run(self, p: Page) -> CaseResult:
        return review_result(p, LlmVisionExtract().extract(p), [])


class TwoReader:
    """Layout+LLM and vision+LLM read the page independently. Agreement (after the same
    normalisation the scorer uses) is auto-accepted; disagreement goes to a person.
    Their failure modes differ — OCR speckle becomes stray dots in IDs on one side,
    O/0 confusion on the other — which is what makes agreement informative."""
    name = "two-reader"

    def run(self, p: Page) -> CaseResult:
        a, b = LlmLayout().extract(p), LlmVisionExtract().extract(p)
        accepted, flagged = {}, []
        for k in SCHEMAS[p.label]:
            if norm(k, a.get(k)) == norm(k, b.get(k)):
                accepted[k] = a.get(k)
            else:
                flagged.append(k)
        return review_result(p, accepted, flagged)


class ReviewSuite(Suite):
    name = "review"
    workers = 8
    headline = "auto_accept_precision"
    margin = 0.01
    tolerance = 0.005
    constraints = {"review_rate": ("<=", 0.10)}  # a reviewer for every field defeats the point

    def cases(self) -> list[Page]:
        return load("trade", "test")

    def baselines(self):
        return [AcceptAllVision()]

    def systems(self):
        return [TwoReader()]

    def metrics(self, results: list[CaseResult]) -> dict[str, float]:
        acc = sum(r.tags.get("accepted", 0) for r in results)
        right = sum(r.tags.get("accepted_right", 0) for r in results)
        total = sum(r.tags.get("total", 0) for r in results) or 1
        return {"auto_accept_precision": right / acc if acc else 0.0,
                "review_rate": sum(r.tags.get("flagged", 0) for r in results) / total,
                "wrong_fields_auto_accepted": float(sum(len(r.tags.get("missed", [])) for r in results)),
                "pages_needing_no_review": sum(r.tags.get("flagged", 0) == 0 for r in results) / (len(results) or 1)}


SUITES = {"classify": ClassifySuite(), "extract": ExtractSuite(), "review": ReviewSuite()}
SUITE = SUITES["classify"]
