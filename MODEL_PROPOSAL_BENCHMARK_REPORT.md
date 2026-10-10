# Model-proposal hosted experiment: stopped after P07

Executed 2026-10-10, 21:49:56-21:50:21 UTC on runtime commit
`923ef95f6376ec020e185fa3dc62e7e341e738dd`. Requested model: `gpt-6-astra`, high effort,
Responses strict JSON, 22-second model timeout, 2,400 maximum output tokens. The returned
model ID is unavailable for this timed-out request; previous independent probes verified access.

The authorized plan used only the three unused slots of the revised ten-session allowance:
P07, P03 and P04, sequentially. Four calls per case were allowed, versus the new policy default
of five, so the conservative forecast was $4.72394 including prior calls. The 19,000-byte input
bound (including schema and protocol allowance) is enforced before requests. The persistent
session journal is shared with the prior revised batch. No session was retried or recreated.

| Case | Status | Score | Outcome | Teammate supplied score | Replay |
|---|---|---:|---|---:|---|
| P07 | Completed through fallback | 0.1210577963 | Walked away; no supplier deal | 0.6625701047 | [Replay](https://arena.tacto.ai/replay/fcd4381854d2f053) |
| P03 | Not started: stop on model failure | Unmeasured | Unmeasured | 0.9228331930 | - |
| P04 | Not started: stop on model failure | Unmeasured | Unmeasured | 0.8604451427 | - |

The one-observation mean is **0.1210577963**. There is no three-case or ten-case mean for this
policy. The observed P07 score is 0.5415123084 below the teammate's supplied P07 score and below
our original hybrid P07 score of 0.6344263515. It does not beat those measurements. This is an
end-to-end reliability failure, not evidence about the quality of a completed model proposal.

## What actually happened

The saved session trace contains the opening supplier quote and the buyer's walk-away action;
no counteroffer was submitted. One OpenAI request exceeded the 22-second wall-clock limit.
The adapter recorded `ReadTimeout`; no HTTP status, response, returned model ID or usage was
available. The fallback evaluated the standing offer against the contractual alternative and
walked away. The session ended in one recorded round, after 23.297 seconds overall. There were
zero recorded Arena buyer timeouts, zero network retries and one model/decision fallback.

The arena reported `c_open=391027.40`, `c_alt=379916.00`, no `c_deal`, and post-run
`c_best=299241.49`. The positive score reflects the cheaper alternative, not a negotiated supplier
deal. These post-run hidden scoring values appear only in benchmark reporting, never agent inputs.
The timeout cause beyond the observed lack of a response within 22 seconds is unknown.

## Spending and leaderboard

Actual token usage and the timed-out request's final bill are **unknown**, not zero. The ledger
retains its full $0.20442 conservative reservation. Cumulative accounted spending is $1.20836,
including previous experiments and this unresolved reservation. No further paid calls were made.
The machine-readable summary distinguishes unknown usage from known estimated spending.

Before: 21:49:42 UTC. After: 21:50:21 UTC. Team **Helllo World** remained **rank 14**, with
**71.7/100** across ten contributing cases. Leader remained 86.9/100; gap 15.2 points. Team best
scores did not change; P07's team best remains 0.7466905323. Quota moved from 193 used/407 left
to 194 used/406 left out of 600. The team leaderboard uses best-per-case aggregation and is not
this experiment's mean. This experiment consumed one session; two authorized slots remain.

## Findings and next experiment

Verified: the high-effort call failed the operational time budget despite two earlier synthetic
probes succeeding in 10.3-13.0 seconds. Those probes were insufficient evidence of worst-case
latency. The fallback safely avoided a costly agreement, but immediately ended the negotiation
before attempting any counteroffer.

Recommended next changes, not yet implemented or proven better:

1. Test latency and valid structured output on representative full contexts, including medium
   effort on the same verified model. Record the effort change explicitly; do not label it high.
2. On an isolated model failure with ample rounds/time remaining, consider a bounded, grounded
   clarification message to keep the negotiation open. It should not invent a price or accept an
   invalid deal. Bound repeated failures and preserve the final closing deadline.
3. Test that recovery locally before using P03/P04. Do not retry P07 without new session approval.

The historical failed batch stays frozen. Automatic resumption of this failed experiment is
blocked, so an explicit reviewed recovery plan is needed before the unused slots are consumed.
No final event was started, no submission made and no merge to main performed.

## Artifacts and validation

Sanitized evidence lives in `benchmarks/model_proposals_01/`: readiness/configuration,
leaderboard before/after, hosted results and summary. Raw supplier/session traces stay ignored
under `starter-kit/.local/`. The negotiation runtime cannot access benchmark results through
its proposal context.

Before execution: 74 relevant regression tests passed; Ruff passed. After reporting changes,
the complete local suite passed **136 tests, 1 optional skip** in 56.52 seconds; Ruff passed. Run local checks from `starter-kit/` with
`uv run --offline --extra sim pytest -q` and `uv run --offline ruff check .`.
