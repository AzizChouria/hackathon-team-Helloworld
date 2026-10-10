# Model-authored offers: first experiment

The `hybrid` agent now lets OpenAI propose the commercial terms. Python no longer supplies
percentage-based price anchors in `HYBRID_PROPOSAL_MODE=model`. The model receives verified
case evidence, allowed terms, supplier replies, standing offers and private buyer economics.
It proposes up to two complete packages per active supplier in one structured request.
Python calculates the official total cost, checks allowed values and must-haves, and rejects
packages that fail to improve the cheapest available feasible deal or contractual alternative.
A cheaper unit price alone is insufficient if financing, freight, timing or coverage makes it worse.

The first experiment deliberately retains the existing closing policy and outward message
choices. This is an incremental change, not a claim that the whole agent is free of heuristics.
The five-counter limit, plateau/deterioration protection and firm-offer closing remain. Those
may close too early; measuring them separately is the next useful experiment. Supplier
acceptance, confidence in evidence and a calibrated closing decision remain open limitations.

## Modes and bounded execution

- `HYBRID_PROPOSAL_MODE=model`: default when a model adapter is present; model writes terms.
- `HYBRID_PROPOSAL_MODE=legacy`: preserves the previous percentage-based proposal search.
- `HYBRID_OFFLINE=1` without explicit model mode uses legacy behavior; its historical local
  scores do not measure the new model policy. Explicit model mode without a model closes safely.
- `HYBRID_LLM_CALLS_PER_CASE`: default 5 in model mode, 2 in legacy mode. Repairs count here.
- `LLM_MAX_OUTPUT_TOKENS`: default 2400 in model mode, 1200 in legacy mode; maximum 4096.
- `LLM_TIMEOUT_S`: default 22 seconds. `HYBRID_RESPONSE_GUARD_S`: at most 35 seconds.
- At most one economic-validation repair is attempted, only if call and response-time budgets
  allow it. Provider errors are not retried. Invalid packages are never clamped to another price.
- A failed call, exhausted budget or no viable proposal triggers an explicitly logged safe close:
  accept the cheapest valid standing offer within the alternative cost, otherwise walk away.
  This can sacrifice further savings; it does not silently invoke the old price generator.
- Model trade descriptions stay internal. Outward messages use existing templates and validated
  evidence indices. Free-form adaptive messages are intentionally a later experiment.

The existing strict JSON adapter supports the per-case nested schema. See the official
[Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
The shared persistent API spending ledger and $5 ceiling remain active. Never reset the ledger.
`LLM_MODEL`, `LLM_EFFORT`, `LLM_ENDPOINT`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_USAGE_PATH`,
`LLM_INPUT_USD_PER_M`, `LLM_OUTPUT_USD_PER_M`, `LLM_BUDGET_USD`, `ARENA_DATA`, `ARENA_URL`
and `ARENA_API_KEY` retain their existing meanings. Credentials belong only in the normal loader.

## Run local tests

From `starter-kit/`:

```powershell
uv run --offline --extra sim pytest tests/test_proposals.py -q
uv run --offline --extra sim pytest -q
uv run --offline ruff check .
```

Verified local results: **129 passed, 1 optional skip** in 55.64 seconds; Ruff passed.
The new proposal module contributes 24 tests, including all three simulator cases.
Offline context/schema generation also passed for all 19 cached cases (22 supplier entries);
context sizes were 2,802-5,899 bytes under the 12,000-byte cap. This includes data-only cases
and uses synthetic standing quotes, not hosted runs. See
[context-check evidence](benchmarks/model_proposal_contexts.json).

The new tests use mocked models and the localhost simulator S01-S03. They cover authoring
prices, all-supplier routing, economic repair, constraints, invalid output, repeated proposals,
provider errors, call budgets, deadlines, schema nesting and concurrent case isolation. They
prove behavior and API plumbing, not performance against an intelligent hosted supplier.
The simulator's scripted concessions cannot establish a competitive negotiation mean.

## Optional paid API smoke test (zero hosted sessions)

```powershell
$env:HYBRID_PROPOSAL_MODE = 'model'
$env:LLM_MODEL = 'gpt-6-astra'
$env:LLM_EFFORT = 'high'
$env:LLM_ENDPOINT = 'responses'
$env:LLM_MAX_OUTPUT_TOKENS = '2400'
uv run --offline python -m arena_kit.proposal_probe --live
```

This explicitly paid command makes at most two OpenAI calls on synthetic opening quotes. It
never constructs an Arena client, contacts a hosted supplier, reads a leaderboard or claims a
negotiation score. It writes a sanitized report to `.local/model_proposal_probe.json` by default.
Each additional invocation costs money; ordinary tests never invoke it.

Verified on 2026-10-10 at 21:40 UTC: two HTTP 200 Responses calls returned `gpt-6-astra` at high
reasoning, one single-supplier case and one synthetic two-supplier RFQ with a nested index-clause
schema. All three generated packages passed validation. Call latencies were 12.953 and 10.328
seconds (mean 11.641, max 12.953); decision latencies 12.969 and 10.344 seconds. No fallback,
repair or retry occurred. Usage was 2,957 input and 1,127 output tokens, including 704 reasoning
tokens. Estimated incremental cost: $0.08592; cumulative ledger charge: $1.00394. Estimates use
the existing verified $10/M input and $50/M output rates, not invoice reconciliation.
See [machine-readable evidence](benchmarks/model_proposal_probe.json).

## Before another hosted comparison

No hosted sessions were opened for this revision. Its hosted mean is unknown. The last revised
seven-case mean remains 0.365154; do not relabel historical or synthetic scores as this revision.

The old benchmark runners are explicitly pinned to legacy mode and reject the new mode: their
old two-call forecasts are unsuitable for five larger model requests. The stopped historical batch
remains stopped, and all session journals are preserved. Before testing online, prepare a new
reviewable session plan using the remaining authorized slots, current team quota and larger
schema/token costs. The existing raw `arena play ... --agent hybrid` command supports this
policy, but bypassing the benchmark journal would lose its duplicate/session-count protection.
Do not start a full practice or final run just to test this change.

Prioritize evidence from actual negotiation outcomes: accepted full cost versus opening,
proposal rejection reasons, unresolved cost drivers, fallback frequency and whether early closing
missed realistic concessions. Use matched cases/configurations for comparison. A valid cheaper
proposal is not an agreed deal, and no local fixture guarantees beating another team's score.


## Subsequent hosted result

The first hosted model-proposal case (P07) hit the 22-second API timeout and closed via
walk-away fallback, score 0.121058. The experiment stopped; P03/P04 were not started.
See [MODEL_PROPOSAL_BENCHMARK_REPORT.md](MODEL_PROPOSAL_BENCHMARK_REPORT.md).
The earlier smoke-test success does not establish hosted reliability or a competitive mean.
