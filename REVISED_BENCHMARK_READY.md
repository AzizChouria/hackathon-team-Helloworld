# Revised hosted benchmark: prepared, not started

> Subsequent hosted outcome: the approved revised batch stopped after seven sessions,
> including one API failure and manual recovery. The seven-case mean was 0.365154;
> three cases remain unstarted. See [REVISED_BENCHMARK_REPORT.md](REVISED_BENCHMARK_REPORT.md).
> The preparation and local results below are historical and do not establish hosted superiority.

## Selected configuration

- Model: API-verified `gpt-6-astra`; reasoning `high`; Responses with strict JSON.
- Maximum 22 seconds per model request and two model calls per case.
- Sequential cases; RFQ suppliers within a case use the asynchronous coordinator.
- Exactly the ten supported practice IDs, once each: P01, P05, P02, P18, P08, P10,
  P11, P07, P03, P04. P01 first, then the RFQ to exercise the deadline fix early.
- Cumulative development budget stays at $5, including previous spending. After the new
  preflight probe, $0.56062 is accounted. A conservative additional $4.0158 forecasts $4.57642
  total, using previously verified rates and token reservations. Preparation refreshes the ledger.
- No silent model or effort substitution. The existing .env is not changed; launch settings are
  explicit process-local overrides. An unexpected returned model ID triggers deterministic fallback.

## Readiness improvements

The model now sees bounded recent negotiation history, remaining rounds, and package costs
computed by Python. This supports contextual package selection without delegating arithmetic.
The finite response schema still prevents free-form factual claims or disclosure of internal costs.
These conversational changes pass mocked tests across all 19 cached cases. A single OpenAI
preflight on 2026-10-10T18:27:08Z returned gpt-6-astra/high with valid structured output in
8.781 seconds (1,032 input, 357 output, including 309 reasoning tokens; estimated $0.02817).
No fallback or retry occurred. This was synthetic context, not a hosted supplier negotiation;
conversational benefits remain unmeasured online.

The runner freezes the Git commit, public dataset fingerprint, exact case data and configuration.
It rechecks them before starting and before each case. Shared locking and a second ledger check
under the lock prevent duplicate reservations. Original session records and reports are preserved.
Each new attempt is recorded before opening its session. A failed or ambiguous attempt is never
recreated automatically. Invalid deals, buyer timeouts, request errors, or model/strategy failures
stop the batch and also block automatic resumption. Deliberate deterministic turns are not failures.

## Prepare safely

From `starter-kit/`, after tested code is committed:

```powershell
uv run --offline python -m arena_kit.revised_benchmark prepare
```

This loads credentials through the normal environment loader and performs only GET checks of
quota, hosted availability and practice leaderboard. It makes no OpenAI requests and creates no
negotiation sessions. The private frozen plan is `.local/revised_01_plan.json`; its public readiness
summary is `../benchmarks/revised_01/readiness.json`. Preparation explicitly records that execution
is not approved. Keep the working data and source unchanged after preparing.

## Execution is a separate action

The original authorization covered ten sessions and is exhausted. Fresh explicit permission is
required before invoking this command; it is documented only and has NOT been executed:

```powershell
uv run --offline python -m arena_kit.revised_benchmark run --execute-approved
```

`--offline` controls uv dependency downloads; this execution command WOULD use the hosted APIs.
The command without `--execute-approved` fails before making requests. The new batch is fixed to
`revised_01`; arbitrary new batch names cannot bypass the ten-session cap. Its journal is
`.local/revised_01_sessions.jsonl`. The shared model-cost ledger remains `.local/llm_usage.jsonl`.
Never delete either ledger to obtain more sessions or spending capacity.

After execution, sanitized per-case results, before/after leaderboard snapshots and summary live
under `benchmarks/revised_01/`. Raw session states remain private under `.local/revised_01/`.
A full ten-case mean is reported only after all ten numeric scores exist. Partial completion is
labeled separately. Another team member's best-per-case improvement cannot be attributed to this
batch solely because the leaderboard changed.

## Performance interpretation

Current deterministic local scores are 98.5463/100 across standard S01-S03 at 8% financing,
and 70.0385/100 across 36 stress fixtures using the standard simulator reference. Against commit
08002e0, cost is lower in 11 fixtures, equal in 25 and higher in none. These are development
fixtures, not held-out results or hosted supplier scores. All 19 cached economic fixtures pass.
The last measured hosted batch remains 53.1496/100. The latest read-only team check showed
69.6/100 (rank 9), aggregated from team best scores; that is a different metric. The current
readiness snapshot supersedes that historical quota/rank if teammates have since run cases.

No promise of a hosted mean above 0.7 is made. Success for the next batch means comparable,
valid measurements first; then assess per-case cost savings, mean, failures and leaderboard impact.
No final run, final submission, or merge to main is part of this preparation.

## Final preparation validation

- Full local suite: **87 passed, 1 optional MCP skip** in 53.66 seconds.
- Ruff: passed.
- All 19 cached cases pass economics, evidence and mocked-context checks; maximum observed
  synthetic context is 2,539 bytes, below the 12,000-byte limit.
- All 36 deterministic local comparisons retain their prior outcomes and scores. The richer
  model context does not change those deterministic baselines.
- Fresh Astra/high preflight: valid response, 8.781 seconds, no fallback/retry, $0.02817 estimated.
- No new hosted negotiation session was started. The readiness command is run only after commit.


## Subsequent preference-sensitive strategy validation

See [STRATEGY_IMPROVEMENT_REPORT.md](STRATEGY_IMPROVEMENT_REPORT.md) for the latest changes
and limitations. Against the previously tested commit `5e21aac`, the 36 existing comparisons
are unchanged; 72 additional synthetic preference scenarios produce 18 lower costs, 54 ties,
and no higher costs, with all 72 valid deals and no timeouts. These are development fixtures,
not hosted supplier results. The revised hosted mean remains unmeasured. Source changes
invalidate the old frozen benchmark plan; refresh preparation after committing this revision.
