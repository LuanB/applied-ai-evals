# telemetry-attribution — eval report

**Gate: PASS ✅** · mode `replay` · headline `balanced_accuracy`

```
info agent-v1-raw:gpt-41-mini: ungated reference, balanced_accuracy 0.250
info agent-v1-raw:gpt-5-mini: ungated reference, balanced_accuracy 0.167
ok   agent-v2:gpt-41-mini: balanced_accuracy 0.750 beats best baseline 0.500 (margin 0.05)
ok   agent-v2:gpt-41-mini: within tolerance of floor 0.750
ok   agent-v2:gpt-5-mini: balanced_accuracy 0.750 beats best baseline 0.500 (margin 0.05)
ok   agent-v2:gpt-5-mini: within tolerance of floor 0.750
```

| system | balanced_accuracy | attribution_precision | model_refusal | accuracy | attribution_recall | correct_refusal | pass_all_trials | budget_exhausted | cost (USD) | wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| always-guess *(baseline)* | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0000 | 0.0 |
| always-refuse *(baseline)* | 50.0% | 0.0% | 0.0% | 60.0% | 0.0% | 100.0% | 60.0% | 0.0% | 0.0000 | 0.0 |
| agent-v1-raw:gpt-41-mini *(ungated reference)* | 25.0% | 100.0% | 0.0% | 20.0% | 50.0% | 0.0% | 20.0% | 20.0% | 0.0277 | 0.0 |
| agent-v1-raw:gpt-5-mini *(ungated reference)* | 16.7% | 0.0% | 33.3% | 20.0% | 0.0% | 33.3% | 20.0% | 26.7% | 0.0808 | 0.0 |
| **agent-v2:gpt-41-mini** | 75.0% | 50.0% | 0.0% | 80.0% | 50.0% | 100.0% | 80.0% | 0.0% | 0.0241 | 0.0 |
| **agent-v2:gpt-5-mini** | 75.0% | 21.4% | 33.3% | 80.0% | 50.0% | 100.0% | 80.0% | 0.0% | 0.0888 | 0.0 |

## agent-v1-raw:gpt-41-mini: 12 of 15 cases not passed

| case | score | detail |
|---|---|---|
| `case3-tool-call-spiral#0` | 0.00 | missed ['77d9c90']; named [] — tool budget exhausted after 11 calls without submit_answer |
| `case3-tool-call-spiral#1` | 0.00 | missed ['77d9c90']; named [] — tool budget exhausted after 11 calls without submit_answer |
| `case3-tool-call-spiral#2` | 0.00 | missed ['77d9c90']; named [] — tool budget exhausted after 11 calls without submit_answer |
| `refusal-shifted-window#0` | 0.00 | should have refused; named ['36a2807'] — The movement is a sharp increase in tool calls per agent run. The commit 36a2807 (2026-06-24) explicitly adds per-turn  |
| `refusal-shifted-window#1` | 0.00 | should have refused; named ['36a2807'] — The movement is a sharp rise in tool calls per agent run on 2026-07-18. Among commits in the window, commit 36a2807 (da |
| `refusal-shifted-window#2` | 0.00 | should have refused; named ['36a2807'] — The movement is a large step increase in tool calls per run. The commit 36a2807 (2026-06-24) explicitly added per-turn  |
| `refusal-before-field-existed#0` | 0.00 | should have refused; named ['7b99e09'] — The movement is the appearance of the telemetry field 'reasoningTokens' starting 2026-07-03. Among the commits in the w |
| `refusal-before-field-existed#1` | 0.00 | should have refused; named ['7b99e09'] — The movement is the appearance of the telemetry field 'reasoningTokens' starting 2026-07-03. Among the commits in the w |
| `refusal-before-field-existed#2` | 0.00 | should have refused; named ['7b99e09'] — The movement is the appearance of the telemetry field 'reasoningTokens' starting 2026-07-03. Among the commits in the w |
| `refusal-window-after-movement#0` | 0.00 | should have refused; named ['52a5e8b', '0cacdb5', 'a119a87'] — The movement in tool calls per agent run (p90 rose from 7 to 27 on 2026-07-18) is plausibly expla |
| `refusal-window-after-movement#1` | 0.00 | should have refused; named ['52a5e8b', '0cacdb5'] — The movement in tool calls per agent run (p90 rose from 7 to 27 on 2026-07-18) falls within the window 2026- |
| `refusal-window-after-movement#2` | 0.00 | should have refused; named ['52a5e8b', '0cacdb5'] — The movement in tool calls per agent run (p90 rose from 7 to 27 on 2026-07-18) is best explained by commits  |

## agent-v1-raw:gpt-5-mini: 12 of 15 cases not passed

| case | score | detail |
|---|---|---|
| `case1-hidden-thinking-tokens#0` | 0.00 | missed ['5c0d634']; named [] — tool budget exhausted after 8 calls without submit_answer |
| `case1-hidden-thinking-tokens#1` | 0.00 | missed ['5c0d634']; named [] — tool budget exhausted after 8 calls without submit_answer |
| `case1-hidden-thinking-tokens#2` | 0.00 | missed ['5c0d634']; named [] — tool budget exhausted after 8 calls without submit_answer |
| `case3-tool-call-spiral#0` | 0.00 | missed ['77d9c90']; named ['fd10d27', '1b7d725', 'fbca50e'] — All three July 18 commits touch the agent runtime and search-budget code paths that control how ma |
| `case3-tool-call-spiral#1` | 0.00 | missed ['77d9c90']; named ['fd10d27', 'fbca50e', '1b7d725'] — All three commits on 2026-07-18 touch the agent search-budget and run-time budgeting code that dir |
| `case3-tool-call-spiral#2` | 0.00 | missed ['77d9c90']; named ['fd10d27', 'fbca50e', '1b7d725'] — All three commits on 2026-07-18 change the agent’s search/call-budget logic or the runner that con |
| `refusal-shifted-window#0` | 0.00 | should have refused; named ['36a2807', '1a6f26a', '7b99e09'] — Primary suspect: 36a2807 (2026-06-24) — touches electron/agent/providers/*/toolLoop.ts and electr |
| `refusal-shifted-window#1` | 0.00 | should have refused; named ['36a2807', '7b99e09'] — Why these commits: the p90 jump in "tool calls per agent run" means many runs began invoking more tools (or  |
| `refusal-shifted-window#2` | 0.00 | should have refused; named ['36a2807', '7b99e09', '7728f7f'] — All three commits in the window touch the agent providers’ tool-loop logic and telemetry and ther |
| `refusal-before-field-existed#0` | 0.00 | should have refused; named [] — tool budget exhausted after 8 calls without submit_answer |
| `refusal-before-field-existed#1` | 0.00 | should have refused; named ['7b99e09', '03d07b1'] — Reasoning: the new telemetry field reasoningTokens looks like a token-count / cost-instrumentation metric em |
| `refusal-before-field-existed#2` | 0.00 | should have refused; named ['7b99e09', '03d07b1'] — The most plausible cause is commit 7b99e09 (2026-06-22): its subject is “cost-instrument ASR/detect/enrichme |

## agent-v2:gpt-41-mini: 3 of 15 cases not passed

| case | score | detail |
|---|---|---|
| `case3-tool-call-spiral#0` | 0.00 | missed ['77d9c90']; named ['aed9ba8'] — The commit aed9ba8 on 2026-07-16 titled 'openai R2: local web_search tool with a deterministic egress scrub' changed 16  |
| `case3-tool-call-spiral#1` | 0.00 | missed ['77d9c90']; named ['aed9ba8'] — The commit aed9ba8 on 2026-07-16 titled 'openai R2: local web_search tool with a deterministic egress scrub' changed man |
| `case3-tool-call-spiral#2` | 0.00 | missed ['77d9c90']; named ['aed9ba8'] — The commit aed9ba8 on 2026-07-16 titled 'openai R2: local web_search tool with a deterministic egress scrub' changed man |

## agent-v2:gpt-5-mini: 3 of 15 cases not passed

| case | score | detail |
|---|---|---|
| `case3-tool-call-spiral#0` | 0.00 | missed ['77d9c90']; named ['fd10d27', '1b7d725', 'fbca50e'] — All three July 18 commits touch the agent runtime and search-budget code paths that control how ma |
| `case3-tool-call-spiral#1` | 0.00 | missed ['77d9c90']; named ['fd10d27', 'fbca50e', '1b7d725'] — All three commits on 2026-07-18 touch the agent search-budget and run-time budgeting code that dir |
| `case3-tool-call-spiral#2` | 0.00 | missed ['77d9c90']; named ['fd10d27', 'fbca50e', '1b7d725'] — Deterministic detector flagged a step increase in tool calls on 2026-07-18. Three commits on that  |

_Replayed from cassettes: $0 spent on this run. Costs shown are what the recorded calls cost when they were made live._

Trace: `traces/telemetry-attribution-20261005-161031.jsonl`
