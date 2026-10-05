# P3 — RAG you can audit: answers, citations and refusals on Australian privacy guidance

**Question answering over the OAIC Australian Privacy Principles guidelines**, scored on
whether each answer is right, whether it cites a passage that actually supports it, and
whether it refuses questions the guidelines don't answer.

| | result |
|---|---|
| Vector RAG (text-embedding-3-small, k=5, gpt-4.1-mini) | **96.2% grounded balanced accuracy**: 37/40 answers correct *and* properly cited, 10/10 out-of-scope questions refused |
| The model with no retrieval | 57.5% of answers correct, **0 checkable citations**, and it answered **9 of 10** questions the guidelines don't cover (GDPR fines, Spam Act deadlines…) |
| BM25 vs vector vs hybrid | 90% / 96.2% / 90%. **Too close to call:** vector beats BM25 on 4 questions and loses on 2. Hybrid added nothing here |
| Answer key | **two errors in my own labels found** while building it, both fixed and logged in `data/questions.json` |
| Cost | $0.05 per 50-question run per retriever, live. CI replays for $0 |

## Corpus and questions

- **Corpus**: Chapter B (key concepts) and Chapters 1–13 of the APP guidelines, from
  oaic.gov.au, licensed **CC BY 4.0 by the Office of the Australian Information
  Commissioner**. `build_corpus.py` cuts them into 308 chunks along the document's own
  headings, keeping the guideline paragraph numbers (e.g. `12.82–12.87`) so a citation can
  be checked against the source.
- **40 answerable questions**, each paraphrased away from the source wording so retrieval
  can't win on exact matches. Each has:
  - `facts`: phrases the answer must contain (alternatives allowed), checked by string
    match, with no LLM judge.
  - `evidence`: a phrase (optionally pinned to a chapter) that a supporting chunk must
    contain. Every chunk containing it counts as correct support, so the guidelines'
    repetition can't penalise a correct citation.
- **10 out-of-scope questions** on plausible Australian and overseas privacy topics that
  this corpus doesn't answer. Each topic's absence was checked against the corpus text
  before writing. One is a deliberate trap: the Spam Act *is* mentioned, but its
  unsubscribe deadline isn't.

## Metric (fixed before the first run)

`grounded_balanced = mean(answered correctly AND cited a supporting chunk, refused correctly on out-of-scope)`

A correct answer with no valid citation scores zero. The point of RAG here is an answer
someone can check, so the metric doesn't reward the model for knowing the answer anyway.

## Results (`evalgate run rag-audit`)

| system | grounded balanced | answers correct | correct + cited | out-of-scope refused | answerable refused | recall@5 | MRR |
|---|---|---|---|---|---|---|---|
| always-refuse *(baseline)* | 50.0% | 0% | 0% | 100% | 100% | — | — |
| no retrieval *(baseline)* | 5.0% | 57.5% | 0% | 10% | 0% | — | — |
| BM25 | 90.0% | 90.0% | 90.0% | 90% | 5.0% | 90.0% | 0.78 |
| **vector** | **96.2%** | 92.5% | 92.5% | **100%** | 0% | 92.5% | 0.76 |
| hybrid (reciprocal rank fusion) | 90.0% | 90.0% | 90.0% | 90% | 2.5% | 90.0% | 0.79 |

## Failures worth knowing

1. **Retrieval miss → confidently wrong.** On "can a customer let a company use their
   Medicare number as its customer ID?", none of the three retrievers put the chunk saying
   *an individual cannot consent* in the top 5. Hybrid then answered *"Yes, a company can
   adopt a customer's Medicare number…"*, the opposite of the guideline. Recall@5 is the
   number to watch: every wrong answer here traces to a retrieval miss.
2. **The right number from the wrong passage.** "How many permitted general situations does
   s 16A list?" Vector and hybrid retrieved the APP 8 passage, which lists the *five* that
   apply to cross-border disclosure, and answered "five". The answer is seven. The retrieved
   text was accurate; it just answered a different question.
3. **A grounded-looking merge.** The corpus mentions the Online Safety Act's under-16
   social media rule (para 3.40) but never the Children's Online Privacy Code. Asked about
   the code, BM25 and hybrid RAG merged the two and **cited a real chunk**. A citation
   proves that a passage was retrieved. It doesn't prove the passage says what the answer
   claims. Vector RAG refused.
4. **No retrieval is a scoping failure, not a knowledge failure.** The model knew 57.5% of
   the answers, but answered 9 of 10 out-of-scope questions with confident specifics, and
   none of its answers can be traced to a source.

## Answer-key corrections

- **q25 (caught before any run).** The first draft pointed at *"a reasonable period would
  generally be 30 days"* (para 7.47). The evidence check showed that passage is about
  telling someone the **source** of their data, not about stopping marketing after an
  opt-out. The opt-out guidance is para 7.37, *"no more than 30 days"*: same number,
  different rule.
- **q34 (caught after the first run).** A correct, cited answer was scored "no valid
  citation" because my evidence phrase missed the chunk that states the rule (`app3-012`,
  *"APP 3.3 imposes an additional requirement of consent"*). Widened, and rescored from the
  cassettes for $0.

## Run

```bash
evalgate run rag-audit                        # replay, $0
python projects/rag-audit/build_corpus.py     # after re-fetching the HTML into data/raw/
EVALGATE_MODE=record evalgate run rag-audit   # live, ~$0.17 for all five systems
```

Vector store: an in-memory numpy matrix (308 × 256 dims). At this size a database adds
nothing. The retriever is one method, so pgvector or Azure AI Search drops in without
touching the eval.
