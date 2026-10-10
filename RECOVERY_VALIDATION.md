# Bounded recovery and measured effort selection

The first model-proposal hosted run ended P07 after a 22-second model timeout. This revision
fixes that control-flow failure. It does not claim to repair or improve the already completed
P07 result, and it does not create any new hosted sessions.

## Implemented behavior

In model proposal mode, the first transient provider failure may produce one short clarification
message, without terms, citations or invented prices. All active RFQ suppliers are serviced.
A subsequent model request happens only after a fresh supplier reply; the failed request is not
blindly retried. The agent retains its selected model and effort throughout the case.

Recovery requires another model call available, at least three remaining moves per active
supplier, and at least five seconds inside the 35-second response guard for sending the message.
It is disabled at firm closing states and does not risk an already earned concession. The
runner's final-wave closing path still takes precedence. `HYBRID_RECOVERY_TURNS` defaults to
one and is capped at one; zero disables it. Recovery counts reset between cases.

A second failure, exhausted budget, invalid schema/constraints, authentication failure or
imminent deadline still closes economically: accept the cheapest feasible standing offer within
the available alternative cost, otherwise walk away. Closing is explicit in diagnostics.
Provider HTTP 408/429/500/502/503/504 and transport/timeouts are classified as transient;
400/401/404 are not. No exception body, credentials or model-private trade description is sent.

An optional repair request can also fail after some packages have passed validation. Those
valid packages are now retained, rather than discarded by the error path. This is logged as
`validated_before_repair_error`. Clarification recovery is logged as `clarification_recovery`,
including the recovery count and failure type. Neither is misreported as a successful model call.

## Local validation

**152 passed, 1 optional skip** in 57.37 seconds; Ruff passed. The complete suite includes:

- A full simulated 22-second timeout followed by a clarification within the response guard.
- Fresh-reply recovery, repeated failure and exhausted budgets.
- Authentication/configuration errors versus temporary provider statuses.
- Deadline, remaining-round and earned-concession protection.
- RFQ routing, case isolation and retention of valid packages after a failed repair.
- S01-S03 localhost simulator completion with a forced first model failure in every case.

These simulator/model doubles verify execution, not hosted supplier intelligence or scores.
Run from `starter-kit/`:

```powershell
uv run --offline --extra sim pytest -q
uv run --offline ruff check .
```

## Actual API-only checks

Used current cached public case data and intelligence, with clearly synthetic quotes/replies.
No replay-derived answers, hidden optima or leaderboard information were supplied to the model.
The same P07 context/schema hash was used for high and medium effort. Each fixture allowed one
call, deliberately disabling repair/recovery for a clean latency measurement. There were no
hosted suppliers, no acceptance results and no negotiation scores.

| Context | Effort | API result | Request seconds | Valid packages |
|---|---|---|---:|---:|
| P07, one supplier | high | Timed out | 22.000 cutoff | 0 |
| Same P07 context | medium | HTTP 200, returned gpt-6-astra | 7.390 | 1 |
| P05, three suppliers | medium | HTTP 200, returned gpt-6-astra | 16.765 | 4 |
| P08, index-clause schema | medium | HTTP 200, returned gpt-6-astra | 8.265 | 1 |

Medium succeeded in 3/3 samples, with six valid packages, no repair/fallback/retry, mean request
latency 10.807 seconds and maximum 16.765 seconds. Usage: 6,500 input and 1,417 output tokens,
including 633 reasoning tokens; known estimated cost $0.13585. The high-effort timeout has
unknown usage and retains its $0.19411 reservation. Total additional accounted cost: $0.32996;
cumulative shared-ledger charge: **$1.53832**, below $5. This is not invoice reconciliation.

Evidence: [sanitized probe data](benchmarks/recovery_latency_probe.json). The artifact records a
source hash, exact settings and context/schema hashes. UTC timestamp is 2026-10-10T21:58:04;
this work crossed midnight locally in Europe/Berlin. One sample per context is insufficient to
establish worst-case latency or prove medium has equal negotiation quality.

I recommend explicitly selecting medium for the next controlled experiment. This is consistent
with the latency/quality trade-off described in the official
[OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning), but the measured
API responses above establish access for this key. No model ID substitution was made.

```powershell
$env:HYBRID_PROPOSAL_MODE = 'model'
$env:HYBRID_RECOVERY_TURNS = '1'
$env:HYBRID_LLM_CALLS_PER_CASE = '4'
$env:LLM_MODEL = 'gpt-6-astra'
$env:LLM_EFFORT = 'medium'
$env:LLM_ENDPOINT = 'responses'
$env:LLM_TIMEOUT_S = '22'
$env:LLM_MAX_OUTPUT_TOKENS = '2400'
$env:LLM_MAX_INPUT_BOUND = '19000'
```

These are explicit process-local settings; `.env` and existing credentials were not changed.
The default effort remains governed by the existing environment loader, so apply the settings
above when intentionally testing medium. Do not claim a high-effort run when using them.

For a repeat of the paid API-only experiment, explicitly run
`uv run --offline python -m arena_kit.latency_probe --live --output .local/latency_probe_02.json`.
It refuses to overwrite an existing report and forecasts all four calls plus budget room for
the two remaining hosted slots before starting. Repetition costs money and was not performed.

## Remaining limits

The two authorized slots, P03/P04, remain unused. Historical failed benchmark plans stay frozen;
a fresh reviewed recovery plan is required before execution. Existing code/data identity checks
intentionally prevent silent resumption. No hosted retest, final run or submission occurred.

The latest hosted score remains P07 = 0.1210577963, and the last fetched team leaderboard remains
71.7/100, rank 14 (21:50 UTC); the board was not refreshed during this code-only task. The new
recovery behavior and medium effort have **no hosted mean**. Supplier reactions to clarification,
closing timing, five-counter limit and template-based language remain unverified limitations.
