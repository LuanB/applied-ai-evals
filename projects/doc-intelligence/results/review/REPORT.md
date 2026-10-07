# review — eval report

**Gate: PASS ✅** · mode `replay` · headline `auto_accept_precision`

```
ok   two-reader: auto_accept_precision 0.998 beats best baseline 0.979 (margin 0.01)
ok   two-reader: within tolerance of floor 0.998
ok   two-reader: review_rate 0.043 <= 0.1
```

| system | auto_accept_precision | review_rate | wrong_fields_auto_accepted | pages_needing_no_review | cost (USD) | wall (s) |
|---|---|---|---|---|---|---|
| accept-all(llm-vision) *(baseline)* | 97.9% | 0.0% | 13 | 100.0% | 0.0775 | 0.1 |
| **two-reader** | 99.8% | 4.3% | 1 | 72.8% | 1.2110 | 0.1 |

## two-reader: 1 of 92 cases not passed

| case | score | detail |
|---|---|---|
| `test-B15-01` | 0.88 | flagged []; auto-accepted wrong ['hs_code'] |

_Replayed from cassettes: $0 spent on this run. Costs shown are what the recorded calls cost when they were made live._

Trace: `traces/review-20261007-182557.jsonl`
