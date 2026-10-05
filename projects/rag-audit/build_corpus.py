"""Parse the OAIC Australian Privacy Principles guidelines into chunks.

Source: Office of the Australian Information Commissioner, Australian Privacy
Principles guidelines (chapter B and chapters 1–13), CC BY 4.0.
https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines

Chunks follow the document's own structure: one chunk per section under a heading,
split at paragraph boundaries when a section runs past ~350 words. Each chunk keeps its
chapter, heading path and the guideline paragraph numbers it covers (e.g. 12.71–12.74),
so a citation can be checked against the source.

Run: python build_corpus.py   (reads data/raw/*.html, writes data/corpus.jsonl)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
MAX_WORDS = 350
PARA_NO = re.compile(r"^\s*([A-D]?\d{0,2}\.\d{1,3})\s+")


def chapter_name(fname: str) -> str:
    m = re.match(r"chapter-([0-9b]+)", fname)
    return "B" if m.group(1) == "b" else f"APP {m.group(1)}"


def parse(path: Path) -> list[dict]:
    soup = BeautifulSoup(path.read_text(errors="ignore"), "html.parser")
    main = soup.find("main") or soup
    chap = chapter_name(path.name)
    chunks: list[dict] = []
    h2 = h3 = ""
    buf: list[str] = []
    paras: list[str] = []

    def flush():
        nonlocal buf, paras
        text = "\n".join(buf).strip()
        if len(text.split()) >= 25:
            chunks.append({"chapter": chap, "heading": " > ".join(x for x in (h2, h3) if x),
                           "paras": f"{paras[0]}–{paras[-1]}" if len(paras) > 1 else (paras[0] if paras else ""),
                           "text": text})
        buf, paras = [], []

    for el in main.find_all(["h2", "h3", "p", "li"]):
        t = " ".join(el.get_text(" ", strip=True).split())
        if not t:
            continue
        if el.name == "h2":
            flush(); h2, h3 = t, ""
            continue
        if el.name == "h3":
            flush(); h3 = t
            continue
        if el.name == "li" and el.find_parent(["nav", "footer", "header"]):
            continue
        m = PARA_NO.match(t)
        if m:
            paras.append(m.group(1))
        buf.append(t)
        if sum(len(x.split()) for x in buf) > MAX_WORDS:
            flush()
    flush()
    # drop site chrome that survives as text
    return [c for c in chunks if not re.search(r"cookie|subscribe to|was this page helpful|love to hear more", c["text"], re.I)
            and not c["heading"].startswith("Footnotes")]


def main() -> None:
    order = ["chapter-b"] + [f"chapter-{i}-" for i in range(1, 14)]
    files = sorted(RAW.glob("*.html"), key=lambda p: next(i for i, o in enumerate(order) if p.name.startswith(o)))
    out = []
    for f in files:
        for i, c in enumerate(parse(f)):
            cid = f"{c['chapter'].replace(' ', '').lower()}-{i:03d}"
            out.append({"id": cid, **c})
    (HERE / "data" / "corpus.jsonl").write_text("\n".join(json.dumps(c) for c in out) + "\n")
    words = sum(len(c["text"].split()) for c in out)
    print(f"{len(out)} chunks, {words:,} words, from {len(files)} chapters")


if __name__ == "__main__":
    main()
