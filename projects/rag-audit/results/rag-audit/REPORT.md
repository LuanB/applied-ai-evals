# rag-audit — eval report

**Gate: PASS ✅** · mode `replay` · headline `grounded_balanced`

```
ok   rag-bm25: grounded_balanced 0.900 beats best baseline 0.500 (margin 0.05)
ok   rag-vector: grounded_balanced 0.963 beats best baseline 0.500 (margin 0.05)
ok   rag-hybrid: grounded_balanced 0.900 beats best baseline 0.500 (margin 0.05)
```

| system | grounded_balanced | answer_balanced | grounded_accuracy | answer_accuracy | correct_refusal | false_refusal | recall_at_5 | mrr | cost (USD) | wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| always-refuse *(baseline)* | 50.0% | 50.0% | 0.0% | 0.0% | 100.0% | 100.0% | — | — | 0.0000 | 0.6 |
| no-retrieval *(baseline)* | 5.0% | 33.8% | 0.0% | 57.5% | 10.0% | 0.0% | — | — | 0.0102 | 0.5 |
| **rag-bm25** | 90.0% | 90.0% | 90.0% | 90.0% | 90.0% | 5.0% | 90.0% | 78.4% | 0.0531 | 0.6 |
| **rag-vector** | 96.2% | 96.2% | 92.5% | 92.5% | 100.0% | 0.0% | 92.5% | 76.4% | 0.0519 | 0.6 |
| **rag-hybrid** | 90.0% | 90.0% | 90.0% | 90.0% | 90.0% | 2.5% | 90.0% | 78.5% | 0.0485 | 0.6 |

## rag-bm25: 5 of 50 cases not passed

| case | score | detail |
|---|---|---|
| `q02` | 0.00 | missing key fact |
| `q11` | 0.00 | missing key fact |
| `q31` | 0.00 | refused an answerable question |
| `q33` | 0.00 | refused an answerable question |
| `x05` | 0.00 | answered an out-of-corpus question: The Children's Online Privacy Code, as referenced in the context of the Online Safety Act 2021, requires age-restricted  |

## rag-vector: 3 of 50 cases not passed

| case | score | detail |
|---|---|---|
| `q02` | 0.00 | missing key fact |
| `q14` | 0.00 | missing key fact |
| `q17` | 0.00 | missing key fact |

## rag-hybrid: 5 of 50 cases not passed

| case | score | detail |
|---|---|---|
| `q02` | 0.00 | missing key fact |
| `q14` | 0.00 | missing key fact |
| `q17` | 0.00 | missing key fact |
| `q31` | 0.00 | refused an answerable question |
| `x05` | 0.00 | answered an out-of-corpus question: The Children's Online Privacy Code requires age-restricted social media platforms to take 'reasonable steps' to prevent  |

_Replayed from cassettes: $0 spent on this run. Costs shown are what the recorded calls cost when they were made live._

Trace: `traces/rag-audit-20261004-155215.jsonl`
