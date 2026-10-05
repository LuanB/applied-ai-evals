# classify — eval report

**Gate: PASS ✅** · mode `replay` · headline `rvl_macro_f1`

```
ok   llm-text: rvl_macro_f1 0.618 beats best baseline 0.392 (margin 0.05)
ok   llm-vision: rvl_macro_f1 0.665 beats best baseline 0.392 (margin 0.05)
ok   cascade: rvl_macro_f1 0.675 beats best baseline 0.392 (margin 0.05)
```

| system | macro_f1 | rvl_accuracy | rvl_macro_f1 | trade_accuracy | trade_untitled_accuracy | escalation_rate | cost (USD) | wall (s) |
|---|---|---|---|---|---|---|---|---|
| majority *(baseline)* | 3.3% | 6.2% | 0.7% | 21.7% | 27.3% | — | 0.0000 | 0.0 |
| tfidf-centroid *(baseline)* | 69.6% | 43.8% | 39.2% | 100.0% | 100.0% | — | 0.4536 | 0.3 |
| **llm-text** | 80.9% | 63.7% | 61.8% | 100.0% | 100.0% | — | 0.5145 | 0.2 |
| **llm-vision** | 83.2% | 67.5% | 66.5% | 100.0% | 100.0% | — | 0.1795 | 0.3 |
| **cascade** | 83.8% | 68.8% | 67.5% | 100.0% | 100.0% | 15.9% | 0.5425 | 0.2 |

## llm-text: 58 of 252 cases not passed

| case | score | detail |
|---|---|---|
| `rvl-test-000` | 0.00 | pred=scientific report true=letter |
| `rvl-test-001` | 0.00 | pred=memo true=letter |
| `rvl-test-002` | 0.00 | pred=memo true=letter |
| `rvl-test-005` | 0.00 | pred=email true=letter |
| `rvl-test-007` | 0.00 | pred=memo true=letter |
| `rvl-test-008` | 0.00 | pred=memo true=letter |
| `rvl-test-010` | 0.00 | pred=letter true=form |
| `rvl-test-012` | 0.00 | pred=memo true=form |
| `rvl-test-014` | 0.00 | pred=invoice true=form |
| `rvl-test-016` | 0.00 | pred=specification true=form |
| `rvl-test-018` | 0.00 | pred=memo true=form |
| `rvl-test-019` | 0.00 | pred=scientific report true=form |
| `rvl-test-024` | 0.00 | pred=memo true=email |
| `rvl-test-030` | 0.00 | pred=memo true=handwritten |
| `rvl-test-031` | 0.00 | pred=letter true=handwritten |
| `rvl-test-032` | 0.00 | pred=specification true=handwritten |
| `rvl-test-033` | 0.00 | pred=memo true=handwritten |
| `rvl-test-035` | 0.00 | pred=budget true=handwritten |
| `rvl-test-037` | 0.00 | pred=letter true=handwritten |
| `rvl-test-038` | 0.00 | pred=memo true=handwritten |
| `rvl-test-039` | 0.00 | pred=letter true=handwritten |
| `rvl-test-047` | 0.00 | pred=news article true=advertisement |
| `rvl-test-053` | 0.00 | pred=memo true=scientific report |
| `rvl-test-056` | 0.00 | pred=invoice true=scientific report |
| `rvl-test-059` | 0.00 | pred=presentation true=scientific report |
| `rvl-test-063` | 0.00 | pred=scientific report true=scientific publication |
| `rvl-test-065` | 0.00 | pred=news article true=scientific publication |
| `rvl-test-069` | 0.00 | pred=scientific report true=scientific publication |
| `rvl-test-076` | 0.00 | pred=form true=specification |
| `rvl-test-077` | 0.00 | pred=scientific report true=specification |
| `rvl-test-080` | 0.00 | pred=form true=file folder |
| `rvl-test-081` | 0.00 | pred=handwritten true=file folder |
| `rvl-test-082` | 0.00 | pred=invoice true=file folder |
| `rvl-test-083` | 0.00 | pred=advertisement true=file folder |
| `rvl-test-084` | 0.00 | pred=scientific publication true=file folder |
| `rvl-test-085` | 0.00 | pred=handwritten true=file folder |
| `rvl-test-086` | 0.00 | pred=scientific report true=file folder |
| `rvl-test-087` | 0.00 | pred=invoice true=file folder |
| `rvl-test-089` | 0.00 | pred=memo true=file folder |
| `rvl-test-093` | 0.00 | pred=advertisement true=news article |

## llm-vision: 52 of 252 cases not passed

| case | score | detail |
|---|---|---|
| `rvl-test-001` | 0.00 | pred=memo true=letter |
| `rvl-test-002` | 0.00 | pred=memo true=letter |
| `rvl-test-005` | 0.00 | pred=email true=letter |
| `rvl-test-007` | 0.00 | pred=memo true=letter |
| `rvl-test-010` | 0.00 | pred=letter true=form |
| `rvl-test-012` | 0.00 | pred=memo true=form |
| `rvl-test-014` | 0.00 | pred=invoice true=form |
| `rvl-test-016` | 0.00 | pred=specification true=form |
| `rvl-test-018` | 0.00 | pred=memo true=form |
| `rvl-test-024` | 0.00 | pred=memo true=email |
| `rvl-test-032` | 0.00 | pred=form true=handwritten |
| `rvl-test-037` | 0.00 | pred=letter true=handwritten |
| `rvl-test-038` | 0.00 | pred=memo true=handwritten |
| `rvl-test-039` | 0.00 | pred=letter true=handwritten |
| `rvl-test-053` | 0.00 | pred=memo true=scientific report |
| `rvl-test-056` | 0.00 | pred=file folder true=scientific report |
| `rvl-test-059` | 0.00 | pred=presentation true=scientific report |
| `rvl-test-063` | 0.00 | pred=scientific report true=scientific publication |
| `rvl-test-065` | 0.00 | pred=advertisement true=scientific publication |
| `rvl-test-069` | 0.00 | pred=scientific report true=scientific publication |
| `rvl-test-074` | 0.00 | pred=handwritten true=specification |
| `rvl-test-080` | 0.00 | pred=invoice true=file folder |
| `rvl-test-082` | 0.00 | pred=specification true=file folder |
| `rvl-test-084` | 0.00 | pred=scientific publication true=file folder |
| `rvl-test-087` | 0.00 | pred=handwritten true=file folder |
| `rvl-test-089` | 0.00 | pred=presentation true=file folder |
| `rvl-test-102` | 0.00 | pred=handwritten true=budget |
| `rvl-test-103` | 0.00 | pred=scientific report true=budget |
| `rvl-test-104` | 0.00 | pred=invoice true=budget |
| `rvl-test-105` | 0.00 | pred=invoice true=budget |
| `rvl-test-106` | 0.00 | pred=memo true=budget |
| `rvl-test-107` | 0.00 | pred=advertisement true=budget |
| `rvl-test-108` | 0.00 | pred=specification true=budget |
| `rvl-test-109` | 0.00 | pred=file folder true=budget |
| `rvl-test-113` | 0.00 | pred=memo true=invoice |
| `rvl-test-116` | 0.00 | pred=memo true=invoice |
| `rvl-test-120` | 0.00 | pred=memo true=presentation |
| `rvl-test-122` | 0.00 | pred=memo true=presentation |
| `rvl-test-123` | 0.00 | pred=news article true=presentation |
| `rvl-test-124` | 0.00 | pred=memo true=presentation |

## cascade: 50 of 252 cases not passed

| case | score | detail |
|---|---|---|
| `rvl-test-000` | 0.00 | pred=scientific report true=letter |
| `rvl-test-001` | 0.00 | pred=memo true=letter |
| `rvl-test-002` | 0.00 | pred=memo true=letter |
| `rvl-test-005` | 0.00 | pred=email true=letter |
| `rvl-test-007` | 0.00 | pred=memo true=letter |
| `rvl-test-008` | 0.00 | pred=memo true=letter |
| `rvl-test-010` | 0.00 | pred=letter true=form |
| `rvl-test-012` | 0.00 | pred=memo true=form |
| `rvl-test-014` | 0.00 | pred=invoice true=form |
| `rvl-test-016` | 0.00 | pred=specification true=form |
| `rvl-test-018` | 0.00 | pred=memo true=form |
| `rvl-test-024` | 0.00 | pred=memo true=email |
| `rvl-test-031` | 0.00 | pred=letter true=handwritten |
| `rvl-test-032` | 0.00 | pred=form true=handwritten |
| `rvl-test-037` | 0.00 | pred=letter true=handwritten |
| `rvl-test-038` | 0.00 | pred=memo true=handwritten |
| `rvl-test-039` | 0.00 | pred=letter true=handwritten |
| `rvl-test-053` | 0.00 | pred=memo true=scientific report |
| `rvl-test-056` | 0.00 | pred=file folder true=scientific report |
| `rvl-test-059` | 0.00 | pred=presentation true=scientific report |
| `rvl-test-063` | 0.00 | pred=scientific report true=scientific publication |
| `rvl-test-065` | 0.00 | pred=advertisement true=scientific publication |
| `rvl-test-069` | 0.00 | pred=scientific report true=scientific publication |
| `rvl-test-076` | 0.00 | pred=form true=specification |
| `rvl-test-080` | 0.00 | pred=invoice true=file folder |
| `rvl-test-082` | 0.00 | pred=specification true=file folder |
| `rvl-test-084` | 0.00 | pred=scientific publication true=file folder |
| `rvl-test-087` | 0.00 | pred=handwritten true=file folder |
| `rvl-test-089` | 0.00 | pred=presentation true=file folder |
| `rvl-test-102` | 0.00 | pred=handwritten true=budget |
| `rvl-test-103` | 0.00 | pred=scientific report true=budget |
| `rvl-test-104` | 0.00 | pred=invoice true=budget |
| `rvl-test-105` | 0.00 | pred=invoice true=budget |
| `rvl-test-106` | 0.00 | pred=invoice true=budget |
| `rvl-test-108` | 0.00 | pred=specification true=budget |
| `rvl-test-109` | 0.00 | pred=file folder true=budget |
| `rvl-test-116` | 0.00 | pred=memo true=invoice |
| `rvl-test-120` | 0.00 | pred=memo true=presentation |
| `rvl-test-122` | 0.00 | pred=memo true=presentation |
| `rvl-test-123` | 0.00 | pred=news article true=presentation |

_Replayed from cassettes: $0 spent on this run. Costs shown are what the recorded calls cost when they were made live._

Trace: `traces/classify-20261004-153236.jsonl`
