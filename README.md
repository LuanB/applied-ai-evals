# applied-ai-evals

Five applied-AI projects. Every one ships with an **answer key**, **baselines it has to
beat**, and a **CI gate** that blocks a merge when it stops beating them.

Most AI demos show the system working. These show how often it works on a fixed,
labelled set, what it costs per case, and the cases where it's still wrong.

| # | project | what it shows | headline |
|---|---|---|---|
| P1 | [`evalgate`](evalgate/) + [telemetry-attribution](projects/telemetry-attribution/) | LLM eval gate in CI · record/replay · OpenTelemetry traces · spend cap | raw agent 17–25% balanced accuracy → 75% with a forced answer + date check; caught a wrong label in my own answer key |
| P2 | [doc-intelligence](projects/doc-intelligence/) | Azure Document Intelligence + Azure OpenAI · page classification · field extraction · review routing | 99.8% of auto-accepted fields correct with 4.3% sent to review; prebuilt-invoice 94%→100% via `locale="en-AU"` |
| P3 | [rag-audit](projects/rag-audit/) | RAG with retrieval evals · BM25 vs vector vs hybrid · citations · refusal on out-of-scope questions | vector RAG 96.2% grounded balanced (37/40 correct+cited, 10/10 refusals) vs no-retrieval 5%; retrievers too close to call at n=50 |
| P4 | agent-guardrails | MCP agent · human approval gate · prompt-injection red-team suite | _in progress, not yet published_ |
| P5 | bedrock-serverless | Same agent on AWS: Bedrock · Lambda · API Gateway · DynamoDB · CDK | _in progress, not yet published_ |

## Writing

- [Reproducible and wrong](https://medium.com/@luan_bui/reproducible-and-wrong-6071a9adfaea): six models
  through the attribution eval that P1 grew out of, on Azure, three runs each. The two that gave the same answer every time
  were the two that were consistently wrong.
- [An agent's cost is set by what it can't answer](https://medium.com/@luan_bui/an-agents-cost-is-set-by-what-it-can-t-answer-b53b459b6bf0):
  an agent over corpus data took 3 turns on a question it could answer and 37 on one it couldn't.

## Run it

```bash
uv venv --python 3.13 && uv pip install -e ".[docs,rag,agent,dev]"
evalgate run telemetry-attribution          # replay: $0, deterministic, no keys
EVALGATE_MODE=record evalgate run <project> # live: bills Azure, capped by evalgate/spend.py
evalgate spend                              # ledger vs caps
docker build -t evalgate . && docker run --rm evalgate
```

## How the gate works

1. **Baselines first.** Each suite ships degenerate systems (always refuse, always
   guess, keyword-only…). If a baseline scores well, the cases aren't binding and the
   suite's numbers mean nothing.
2. **Record/replay.** Every billed call goes through one function, `evalgate.llm.billed`,
   which keys a cassette on the exact request. CI replays for $0. A prompt, model or
   tool change misses the cassette and the build fails, saying it needs a live re-record,
   rather than scoring old answers against a new prompt.
3. **Gate rules.** Each candidate must beat the best baseline by a margin, stay within
   tolerance of its blessed floor, and meet any hard constraints (e.g. a false-block rate
   cap).
4. **Traces and cost.** Each case is an OpenTelemetry span with model calls as children,
   carrying tokens, cost and latency. Each live call is written to `spend/ledger.jsonl`,
   and a hard cap refuses the call before it bills.
