"""P3 — RAG you can audit: Q&A over the OAIC Australian Privacy Principles guidelines.

308 chunks (chapter B + APP 1–13, CC BY 4.0, OAIC). 50 hand-written questions:
40 answerable from the corpus, each with key facts the answer must contain and an
evidence phrase that a supporting chunk must contain; 10 plausible privacy questions
the corpus does NOT answer (GDPR fines, the Spam Act unsubscribe deadline, data breach
notification timing…), where the only correct answer is to say so.

Headline (chosen before the first run): grounded balanced accuracy =
  mean( answered correctly AND cited a chunk that holds the evidence,
        refused correctly on out-of-corpus questions )
A right answer with no valid citation does not count: the point of RAG here is an
answer someone can check against the source.

Systems: always-refuse and no-retrieval (the model's own knowledge) as baselines;
BM25, vector (text-embedding-3-small) and hybrid (reciprocal rank fusion) retrieval,
each feeding the same gpt-4.1-mini answer step with k=5 chunks.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

from evalgate import llm
from evalgate.core import CaseResult, Suite

HERE = Path(__file__).resolve().parent
MODEL = "gpt-41-mini"
K = 5
EMBED_DIM = 256  # text-embedding-3 supports truncation; keeps cassettes small


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("’", "'").replace("‘", "'").lower())


@dataclass
class Q:
    id: str
    q: str
    facts: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)
    ooc: bool = False
    note: str = ""


class Corpus:
    _lock = threading.Lock()
    _inst: "Corpus | None" = None

    def __init__(self):
        self.chunks = [json.loads(l) for l in (HERE / "data" / "corpus.jsonl").read_text().splitlines()]
        self.by_id = {c["id"]: c for c in self.chunks}
        self.bm25 = BM25Okapi([self._tok(c["heading"] + " " + c["text"]) for c in self.chunks])
        self._vecs: np.ndarray | None = None

    @classmethod
    def get(cls) -> "Corpus":
        with cls._lock:
            if cls._inst is None:
                cls._inst = Corpus()
            return cls._inst

    @staticmethod
    def _tok(s: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", s.lower())

    def gold(self, q: Q) -> set[str]:
        e = q.evidence
        phrases = [norm(x) for x in e["phrase"].split("|")]
        return {c["id"] for c in self.chunks if any(p in norm(c["text"]) for p in phrases)
                and (not e.get("chapter") or c["chapter"] == e["chapter"])}

    # ---- retrievers ---------------------------------------------------------
    def bm25_rank(self, query: str) -> list[str]:
        scores = self.bm25.get_scores(self._tok(query))
        return [self.chunks[i]["id"] for i in np.argsort(-scores)]

    def vecs(self) -> np.ndarray:
        with self._lock:
            if self._vecs is None:
                texts = [f"{c['chapter']} — {c['heading']}\n{c['text']}" for c in self.chunks]
                out: list[list[float]] = []
                for i in range(0, len(texts), 64):
                    out += llm.embed(texts[i:i + 64], dimensions=EMBED_DIM)
                v = np.array(out, dtype=np.float32)
                self._vecs = v / np.linalg.norm(v, axis=1, keepdims=True)
            return self._vecs

    def vector_rank(self, query: str) -> list[str]:
        qv = np.array(llm.embed([query], dimensions=EMBED_DIM)[0], dtype=np.float32)
        qv /= np.linalg.norm(qv)
        return [self.chunks[i]["id"] for i in np.argsort(-(self.vecs() @ qv))]

    def hybrid_rank(self, query: str, k_rrf: int = 60) -> list[str]:
        score: dict[str, float] = {}
        for ranking in (self.bm25_rank(query), self.vector_rank(query)):
            for r, cid in enumerate(ranking):
                score[cid] = score.get(cid, 0.0) + 1.0 / (k_rrf + r + 1)
        return sorted(score, key=lambda c: -score[c])


ANSWER_PROMPT = """You answer questions about Australian privacy law using ONLY the numbered
excerpts from the OAIC Australian Privacy Principles guidelines provided.

- If the excerpts contain the answer, answer in 1-3 sentences and cite the excerpt ids
  you relied on.
- If the excerpts do not contain the answer, set in_corpus=false and say the
  guidelines provided do not cover it. Do NOT answer from general knowledge, even if
  you know the answer: an uncited answer cannot be checked."""

NO_CONTEXT_PROMPT = """You answer questions about Australian privacy law. Answer in 1-3
sentences. If you do not know, set in_corpus=false."""

SCHEMA = {"type": "json_schema", "json_schema": {"name": "answer", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["answer", "citations", "in_corpus"],
    "properties": {"answer": {"type": "string"},
                   "citations": {"type": "array", "items": {"type": "string"}},
                   "in_corpus": {"type": "boolean"}}}}}


def facts_ok(q: Q, answer: str) -> bool:
    a = norm(answer)
    return all(any(alt.strip() in a for alt in f.split("|")) for f in q.facts)


def score(q: Q, out: dict[str, Any], retrieved: list[str] | None) -> CaseResult:
    corpus = Corpus.get()
    refused = not out.get("in_corpus", True)
    cites = [c for c in out.get("citations") or [] if isinstance(c, str)]
    tags: dict[str, Any] = {"ooc": q.ooc, "refused": refused, "citations": cites,
                            "answer": (out.get("answer") or "")[:300]}
    if q.ooc:
        return CaseResult(q.id, refused, float(refused),
                          "" if refused else f"answered an out-of-corpus question: {tags['answer'][:120]}", tags=tags)
    gold = corpus.gold(q)
    correct = (not refused) and facts_ok(q, out.get("answer", ""))
    cited_ok = bool(set(cites) & gold)
    tags.update(correct=correct, cited_ok=cited_ok, grounded=correct and cited_ok,
                false_refusal=refused, gold=sorted(gold))
    if retrieved is not None:
        top = retrieved[:K]
        tags["hit_at_k"] = bool(set(top) & gold)
        ranks = [i for i, c in enumerate(retrieved[:50]) if c in gold]
        tags["rr"] = 1.0 / (ranks[0] + 1) if ranks else 0.0
    why = ("refused an answerable question" if refused else
           "missing key fact" if not correct else "no valid citation" if not cited_ok else "")
    return CaseResult(q.id, correct and cited_ok, float(correct and cited_ok), why, tags=tags)


class AlwaysRefuse:
    name = "always-refuse"

    def run(self, q: Q) -> CaseResult:
        return score(q, {"answer": "", "citations": [], "in_corpus": False}, None)


class NoRetrieval:
    """The model's own knowledge, no corpus. It can be right; it can never cite."""
    name = "no-retrieval"

    def run(self, q: Q) -> CaseResult:
        resp = llm.chat(MODEL, [{"role": "system", "content": NO_CONTEXT_PROMPT},
                                {"role": "user", "content": q.q}],
                        temperature=0.0, response_format=SCHEMA)
        return score(q, json.loads(llm.message(resp)["content"]), None)


class Rag:
    def __init__(self, retriever: str):
        self.retriever = retriever
        self.name = f"rag-{retriever}"

    def run(self, q: Q) -> CaseResult:
        corpus = Corpus.get()
        ranked = getattr(corpus, f"{self.retriever}_rank")(q.q)
        ctx = "\n\n".join(
            f"[{cid}] ({corpus.by_id[cid]['chapter']}, paras {corpus.by_id[cid]['paras'] or 'n/a'}, "
            f"{corpus.by_id[cid]['heading'][:80]})\n{corpus.by_id[cid]['text']}" for cid in ranked[:K])
        resp = llm.chat(MODEL, [{"role": "system", "content": ANSWER_PROMPT},
                                {"role": "user", "content": f"Excerpts:\n{ctx}\n\nQuestion: {q.q}"}],
                        temperature=0.0, response_format=SCHEMA)
        return score(q, json.loads(llm.message(resp)["content"]), ranked)


class RagSuite(Suite):
    name = "rag-audit"
    workers = 8
    headline = "grounded_balanced"
    margin = 0.05
    tolerance = 0.03

    def cases(self) -> list[Q]:
        return [Q(**{k: v for k, v in d.items()}) for d in json.loads((HERE / "data" / "questions.json").read_text())]

    def case_tags(self, q: Q) -> dict[str, Any]:
        return {"ooc": q.ooc}

    def baselines(self):
        return [AlwaysRefuse(), NoRetrieval()]

    def systems(self):
        return [Rag("bm25"), Rag("vector"), Rag("hybrid")]

    def metrics(self, results: list[CaseResult]) -> dict[str, float]:
        inc = [r for r in results if not r.tags.get("ooc")]
        ooc = [r for r in results if r.tags.get("ooc")]
        f = lambda rs, k: sum(bool(r.tags.get(k)) for r in rs) / (len(rs) or 1)  # noqa: E731
        refusal = f(ooc, "refused")
        m = {
            "grounded_balanced": (f(inc, "grounded") + refusal) / 2,
            "answer_balanced": (f(inc, "correct") + refusal) / 2,
            "grounded_accuracy": f(inc, "grounded"),
            "answer_accuracy": f(inc, "correct"),
            "correct_refusal": refusal,
            "false_refusal": f(inc, "false_refusal"),
        }
        if any("hit_at_k" in r.tags for r in inc):
            m["recall_at_5"] = f(inc, "hit_at_k")
            m["mrr"] = sum(r.tags.get("rr", 0.0) for r in inc) / (len(inc) or 1)
        return m


SUITE = RagSuite()
