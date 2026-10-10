# Validation of the active buyer strategy

Recorded on **10 October 2026**. These are hosted **practice** observations, not hidden-case or
final-wave results. The active `buyer-llm` uses the [runtime prompt](hidden-case-agent-prompt.md),
deterministic package valuation and a ten-second model decision limit. The latest configuration
requested `gpt-6.1-astra` at low reasoning effort, but the endpoint returned HTTP 404; the full
hosted batch therefore used the deterministic fallback. Earlier model-backed runs below used
`gpt-6.1-sol`. Credentials and private decision text are excluded here.

The latest [full hosted run](all-hosted-current-evaluation.md) averaged **0.627333** across all
10 practice cases, with **10 valid deals**, all must-haves met, and no execution errors. Three
cases exceeded 0.8; the overall target remains unmet. All 43 model completion attempts returned
404. This is a fallback-policy result, not an evaluation of Astra. Exactly **10 sessions** were
used, leaving **483**. Scores, replay links, quota and configuration diagnostics are saved in the
[machine-readable report](all-hosted-current-evaluation.json).

The latest [supplier-preference and competition changes](competitive-strategy-validation.md)
have a **0.842956 local parameter-holdout mean** and **117 passing tests**. Two new hosted P05
attempts scored **0.350283** and, after a timing correction, **0.458784**. The latter is only a
small gain over the previous 0.451910; it does not meet 0.8. Both attempts are retained below.

## What was tested

| Practice batch | Cases | Mean score, counting errors as zero | Outcome |
|---|---:|---:|---|
| Prompt activated, implicit medium effort | 4 | 0.548 | 4 valid deals; two model fallbacks in one case. |
| Same four case IDs, low effort | 4 | 0.552 | 4 valid deals; no model fallbacks observed. |
| Ten cases at low effort, before session-capacity retry | 10 | 0.423 | 7 valid deals; 3 cases failed to open when the key reached its ten-open-session limit. |
| Ten cases at low effort, with capacity retry | 10 | **0.621** | **10 valid deals**, all must-haves met and no acceptance errors. |
| Current code, configured Astra unavailable, deterministic fallback | 10 | **0.627** | **10 valid deals**, all must-haves met; 43 model requests returned 404. |

The earlier 0.621 batch used ten parallel workers and a **480-second per-case budget**, matching the
final wave's case duration. Its slowest case took **240.39 seconds**. The source fingerprint
recorded in the private report is `d48c5f5dde1a` (first 12 hex digits). The retry waits only for
the specific open-session capacity error and preserves the 90-second closing reserve. The later
optimization used local tests; the single hosted follow-up below was subsequently requested explicitly.

## Earlier ten-case rehearsal

| Case | Score | Replay |
|---|---:|---|
| P01 | 0.702 | [View](https://arena.tacto.ai/replay/02393309cb980529) |
| P02 | 0.503 | [View](https://arena.tacto.ai/replay/c0f583d69262f39c) |
| P03 | 0.900 | [View](https://arena.tacto.ai/replay/8e5f9887c5900a7f) |
| P04 | 0.815 | [View](https://arena.tacto.ai/replay/1d053375fe9e3ab5) |
| P05 | 0.304 | [View](https://arena.tacto.ai/replay/70d5ad36a81df779) |
| P07 | 0.720 | [View](https://arena.tacto.ai/replay/162bb82d3acbe053) |
| P08 | 0.646 | [View](https://arena.tacto.ai/replay/e5f6a4a5048295e7) |
| P10 | 0.555 | [View](https://arena.tacto.ai/replay/c6fd6bd9d56c) |
| P11 | 0.536 | [View](https://arena.tacto.ai/replay/f8eafb9d1d6b3da1) |
| P18 | 0.532 | [View](https://arena.tacto.ai/replay/116d34fc6f42f19d) |

The P05 replay remains the clearest weakness: the agent settled with a valid bidder while a
slower bidder's better quote was still pending. That hosted run used a fixed 30-second final-offer
age guard. The code now extends the wait to 45 seconds when the pending bidder's last compliant
quote is at least 1% cheaper on full estimated cost, and can settle a ready offer while another
request remains pending near the wave cap. These changes have local RFQ regression tests and
the later single-case hosted follow-up below. The earlier ten-case result cannot be attributed
to this code revision.

These batches contain supplier randomness and changed code between some runs. The difference
between the earlier [historical ten-case result](evaluation.md) of 0.559 and this 0.621 rehearsal
does not isolate the prompt, model setting or retry as a cause, and neither average predicts a
hidden-case score. The next comparison should use matched cases and repeat runs only when quota
permits. At that revision, the local suite passed **91 tests with 2 skipped**; the local simulator benchmark retained
its S01–S03 results, and Ruff passes. A synthetic local RFQ test covers a pending better final
quote; the benchmark itself does not include an RFQ timing case.

## Subsequent local score optimization

The current opening and concession rules were improved using 48 synthetic development cases
and checked on 48 held-out parameter variants. The holdout mean rose from **0.611 to 0.816–0.821**,
with no errors or must-have breaches. These runs used no hosted sessions or language model.
The hosted 0.621 result above predates these changes. See the
[local score report](local-score-optimization.md) for the iteration record, weaker families,
source fingerprints and reproduction commands. The local mean does not establish a hosted
or hidden-case score of 0.8.

## Minimal hosted follow-up of the optimized buyer

On **10 October 2026**, one P05 practice session tested the current `buyer-llm` with
`gpt-6.1-sol` at low reasoning effort and a 480-second budget. No other hosted case was opened.

| Metric | Result |
|---|---:|
| Score | **0.451910** |
| Deal / must-haves | Valid deal; all must-haves met |
| Total cost | €268,433.76 |
| Unit price | €31.50 |
| Payment / delivery | 14 days / 35 days |
| Duration | 283.25 seconds |
| Claim checks | 4 verified; no contradicted claims reported |
| Remaining practice quota reported by the service | 496 |

[Replay](https://arena.tacto.ai/replay/f31b2c0830b7780b) ·
[Sanitized machine-readable record](hosted-minimal-score-test.json)

The score exceeds P05's 0.304 in the earlier ten-case rehearsal, equals the earlier low-effort
four-case run, and is below the earlier observed best of 0.504. It **does not meet 0.8** and
does not establish a general hosted improvement. Under this case's returned scoring reference,
a 0.8 score requires total cost at most €239,848.33, compared with the realized €268,433.76.
This is a result-analysis target, not a private supplier floor available to the running agent.
The recorded source fingerprint begins `b6ef8fa95114`. No production code changed during this test.

## Subsequent competition-policy hosted tests

Two further P05 sessions tested supplier-preferred packages and competitive RFQ closing. The
first scored **0.350283**: both cheaper active bidders had been challenged, leaving only a more
expensive final quote ready at the waiting limit. The correction keeps the cheapest ready bid
available during challenges and anchors opening RFQ bids to compliant market cost.

After local regression checks, the corrected run scored **0.458784**, with a valid deal and
all must-haves met. Total cost was **€267,869.28**, with **7 verified claims**, no contradicted
claims reported, and a duration of **222.20 seconds**. The €564.48 saving against the previous
minimal run comes from lower modelled defect costs; the €31.50 unit price is unchanged.

[Corrected replay](https://arena.tacto.ai/replay/7722d97f5c8f6090) ·
[First-attempt replay](https://arena.tacto.ai/replay/1a8579dfab749578) ·
[Both hosted results](competitive-strategy-hosted.json) ·
[Policy, local comparison and limitations](competitive-strategy-validation.md)

The corrected run issued no final challenges, so that specific protection is validated locally,
not demonstrated by this run. Two hosted sessions were used; the service reported 493 remaining.
The runtime fingerprint begins `cf0c3cf3ecff`. No further hosted session was opened during that
iteration. The subsequent full hosted batch at the top of this document used the same source.
