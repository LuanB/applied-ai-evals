# P1 — An eval gate for an agent, and the label it caught

**The question:** an agent is shown a movement in production telemetry and the commits in
the release window. Can it name the commit that caused the movement, and refuse when
nothing in the window did?

**Ground truth** is the git history of a product I built (Mayah, an AI meetings copilot).
The full substrate was 14,911 content-free telemetry rows and 694 commits. This public copy
keeps only what the suite reads: the 97 commits that appear in a case window, and the two
telemetry signals the detectors use (tool calls per run, and which rows carry
`reasoningTokens`), reduced to timestamps and run ids. Every result below replays
identically on the reduced data. The movements are detected by plain
arithmetic in `harness/detect.py`; the model never decides whether a number moved, only
which commit explains it.

| | result |
|---|---|
| Raw tool-loop agent (v1) | **17–25% balanced accuracy**, below an agent that refuses everything (50%) |
| With a forced final answer and a date check (v2) | **75%** on both gpt-4.1-mini and gpt-5-mini |
| Where v2's refusals come from | **the date check, not the model.** gpt-5-mini refused on its own only in the window where every commit came after the movement |
| What building the eval found | **my own label for case 3 was wrong.** It named the fix, not the cause |
| Cost of a full live run | about $0.11 (4 agents × 15 trials). Replaying in CI costs $0 |

## The cases

Three real movements, each tried 3 times (15 trials per system):

| case | answer | what it tests |
|---|---|---|
| `case1-hidden-thinking-tokens` | `5c0d634` | a telemetry field starts existing: the hidden-cost incident |
| `case3-tool-call-spiral` | `77d9c90` *(relabelled, see below)* | p90 tool calls per run 7 → 27 |
| `refusal-shifted-window` | refuse | the same real spiral, window moved to June |
| `refusal-before-field-existed` | refuse | window ends 11 days before the field appears |
| `refusal-window-after-movement` | refuse | every commit lands after the spike; causes don't run backwards |

The refusal cases are the real movements shown with a window that leaves out the cause.
There are always commits in a window, so an agent that just finds the most plausible
commit will make something up. That's what the raw agents did: gpt-4.1-mini named a commit
in all 9 refusal trials, including the window that sits entirely after the movement.

## What changed between v1 and v2

Two changes, each added only because a failure showed up repeatedly in v1:

1. **Forced final answer.** 20–27% of v1 runs used the whole 8-call tool budget exploring
   and never answered. In v2, the last turn can only be `submit_answer`. A bug turned up
   along the way: one gpt-4.1-mini turn issued 6 parallel tool calls and jumped straight
   past the forced turn (11 calls on an 8-call budget). Calls beyond the budget now get a
   "submit now" reply.
2. **Deterministic date check.** A named commit must land on the movement day or up to 7
   days before it, otherwise it's rejected. Dates are arithmetic, so they live in code
   with the detector, not in the model.

The report keeps v1 as an *ungated reference* so the before/after is always visible.

## The label it caught

Case 3 was labelled `fd10d27`, *"Add per-run search budget to cap connector/repo tool
spirals."* gpt-4.1-mini kept answering `aed9ba8` (a new web_search tool) instead, so I went
back to the raw data rather than the label:

- The spike starts 17 July at 14:20 UTC, and every spiral run is on `gemini-3.5-flash`.
  Runs on that model jump from 2 a day to 23, then 43.
- The tool doing the spiralling is `search_transcript` (196 calls that day), not
  web_search. So `aed9ba8` was wrong too.
- Git dates are in Melbourne time; telemetry is in UTC. `fd10d27` landed about 16 hours
  *after* the spike started. It's the fix.
- `77d9c90`, *"conversationAnswer role — conversation consults one tier up"*, rewired the
  model registry for the mobile answer path. It was **committed 34 minutes after** the first
  elevated run. I first wrote "35 minutes before", working from a list of only the largest
  runs; plotting every run showed the mistake. The timing fits the change running in a local
  dev build before it was committed, but that's an inference.

The old label rewarded naming the fix. After relabelling (free: the cassettes replay the
same model answers against the corrected key), **no model finds the true cause in any of 6
v2 trials.** Attribution recall is 50%: case 1 only. Confidence in the new label is
"plausible, unconfirmed": the telemetry has no field recording which role a run served,
and the commit time trails the onset. The old label is wrong either way.

## Honest limits

- Five cases is a small suite. It's here to exercise the gate; P2–P4 have suites of 40 to
  250 cases.
- The date check covers windows that are clearly too early or too late. A decoy commit
  inside the 7-day lag still depends on the model's judgement, and the case-3 result shows
  that judgement is weak.
- `attribution_precision` is low (21–50%) because the scorer passes a case if *any* of up to
  3 named commits is right. The metric is there so that shotgunning is visible.

## Run

```bash
evalgate run telemetry-attribution                        # replay, $0
EVALGATE_MODE=record evalgate run telemetry-attribution   # live, ~$0.11
```
