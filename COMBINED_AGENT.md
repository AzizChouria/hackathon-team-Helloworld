> Hosted follow-up: [COMBINED_BENCHMARK_REPORT.md](COMBINED_BENCHMARK_REPORT.md).
> Ten-case mean **0.626295**, nine deals, one RFQ timeout; team leaderboard unchanged at 71.7/100.
> A subsequent acceptance-recovery fix is locally tested only. The integration narrative below describes the earlier local validation.

# Combined buyer agent

The default `hybrid` CLI policy now combines the economic planner from team branch
`codex/main-preflight-eval-20261010` with our stricter acceptance checks, dataset refresh,
case isolation, bounded OpenAI adapter and persistent spending ledger. No hosted sessions
or paid model calls were used for this integration. It is ready for a controlled practice
comparison; its hosted performance is untested.

## What runs

`agents/combined.py` extends the imported `BuyerAgent`:

- Python ranks complete packages using the official total-cost function, including the
  relationship estimate when available. Small menus use exact search; larger menus use
  a bounded beam. Beam results are candidates, not a guaranteed global optimum.
- The planner exchanges payment, indexation, duration, delivery and quality against
  price at comparable buyer cost. It tracks complete-package concessions and rotates
  RFQ bidders. Live competing quotes can constrain an expensive opening anchor.
- Our guards recheck every outgoing sheet and every acceptance. Buyer-plan defaults do
  not establish a missing supplier commitment to a must-have. Pending quotes cannot
  be accepted while their replacement is in flight. Invalid or more costly proposals
  cannot override a feasible ready offer.
- Research uses public dataset facts, documents and supplier-specific estimates.
  Only verified fact IDs and observed quote IDs may be cited. Private contractual
  alternatives are not presented to suppliers as competitor offers. Cache fingerprints
  trigger research reload when the dataset changes.
- Optional LLM advice selects a tactic and at most two verified evidence entries through
  strict structured JSON. It cannot change numeric terms or the acceptance decision.
  A failed, invalid, late or budget-blocked model call retains the computed strategy.
- The coordinator handles supplier replies and attachment reads separately, preserving
  ready offers while other threads are pending. It does not recreate a session on 429
  or blindly repeat a negotiation POST.

There are generic heuristics, including opening discount anchors, concession pacing,
RFQ tolerances and deadline margins. There are no practice-case-specific target prices,
hidden best costs, leaderboard inputs or replay-derived answer tables. Generic heuristics
can still be wrong for an unfamiliar supplier. Full-cost mathematics and constraints
transfer more reliably than assumptions about willingness to concede.

The advisor is **off by default**: local evidence supports the planner, while model advice
has no demonstrated incremental hosted benefit for this combined version. Enabling it is
an experiment, not a prerequisite for useful negotiations. Previous `model` and `legacy`
modes, the `naive` and `llm` examples, and historical benchmark runners remain available.
Existing environment overrides can select an older mode, so set the mode explicitly.

## Reproduce locally

Run from `starter-kit/` using PowerShell. These commands create no hosted sessions:

```powershell
uv run --offline --extra sim pytest -q
uv run --offline ruff check .
uv run --offline --extra sim python -m arena_kit.combined_eval --output ../benchmarks/combined_local_comparison.json
uv run --offline python -m arena_kit.combined_eval --public-cases .local/practice_cases.json --data ../data --output ../benchmarks/combined_public_fixtures.json
```

The last command needs the existing cached public case descriptions. It invents opening
quotes to check term menus and evidence; it does not reconstruct hosted negotiations.
Do not commit the private cache or fetch new sessions to rebuild it. Unit tests also
complete S01, S02 and S03 with both no advisor and an advisor that always raises a timeout.

Select the combined policy explicitly in the environment used by the runner:

```powershell
$env:HYBRID_PROPOSAL_MODE='combined'
$env:HYBRID_TACTICAL_LLM='0'
```

For an explicitly enabled advisor, use `HYBRID_TACTICAL_LLM=1`; `HYBRID_OFFLINE=1` always
disables it. Relevant settings are `HYBRID_LLM_CALLS_PER_CASE` (default 2),
`HYBRID_RESPONSE_GUARD_S` (default and maximum 35), `LLM_MODEL`, `LLM_EFFORT`,
`LLM_ENDPOINT`, `LLM_TIMEOUT_S`, `LLM_MAX_OUTPUT_TOKENS`, `LLM_BUDGET_USD`,
`LLM_USAGE_PATH`, `LLM_INPUT_USD_PER_M`, and `LLM_OUTPUT_USD_PER_M`.
Credentials stay in the existing normal environment loader. No `.env` is rewritten.

The retained adapter previously verified `gpt-6-astra` through Responses. Medium effort
completed three representative earlier OpenAI-only proposal probes; high effort timed
out on a representative probe and one earlier hosted run. Those are historical tests of
a different response schema, not verification of this new tactical schema or its quality.
The new tactical schema is covered with mocked replies; do a bounded OpenAI-only smoke
check before enabling it online. Do not silently change model IDs or label deterministic
results as Astra performance. The shared $5 accounting limit and unresolved timeout
reservations remain in force.

Final local validation: **262 tests passed, 1 skipped**. The skipped test is optional;
no hosted endpoint or paid model call is part of the normal suite. Ruff passes.

## Measured local comparison

The comparison freezes 48 scenarios per split: six families, four concession styles,
two variants. The imported suite supplied development seed 1103 and holdout seed 7607.
An additional transfer seed 20261011 was chosen before inspecting combined-agent scores.
That transfer split changes numerical conditions within the same simulator families; it
is not an independent real-supplier evaluation. No score tuning followed these results.
Private simulator reservation costs are used only by post-negotiation scoring.

| Policy | Development | Holdout | New transfer seed | Overall mean |
|---|---:|---:|---:|---:|
| Previous hybrid, deterministic legacy mode | 0.42655 | 0.38334 | 0.42706 | 0.41231 |
| Imported buyer planner | 0.84461 | 0.83892 | 0.82615 | 0.83656 |
| Combined policy, advisor disabled | 0.84155 | 0.83684 | 0.83061 | 0.83633 |

Each policy closed **144/144 valid deals**, with zero evaluator errors and zero must-have
breaches: 432 synthetic negotiations in total. Combined median is 0.83362, minimum
0.48904 and maximum 1.0. Compared with previous legacy hybrid, combined improved 143
scenarios and tied one. Compared with imported buyer, it improved three, tied 132 and
scored lower on nine. The combined overall mean is 0.000225 below the imported planner;
there is no demonstrated overall score advantage over that planner.

Combined local whole-negotiation time averaged 0.090 seconds, maximum 0.234 seconds.
These timings exclude hosted supplier latency and LLM calls; they are not Arena buyer
response latency or final-wave capacity measurements. Thread scheduling may introduce
small differences across repeated local runs.

| Family | Previous legacy | Imported buyer | Combined |
|---|---:|---:|---:|
| Price increase | 0.39583 | 0.91301 | 0.91412 |
| Renewal | 0.62912 | 0.89055 | 0.89055 |
| RFQ | 0.18815 | 0.77560 | 0.77449 |
| Quality | 0.10698 | 0.87207 | 0.87330 |
| Capacity | 0.53382 | 0.74960 | 0.74701 |
| Indexation | 0.61998 | 0.81853 | 0.81853 |

All **19 cached public cases / 22 suppliers** produced valid economic packages with
verified citations under synthetic opening quotes. Their scores are deliberately null.
This includes data-only cases; none is counted as a hosted run.

Machine-readable evidence: `benchmarks/combined_local_comparison.json` and
`benchmarks/combined_public_fixtures.json`. The former includes suite and source hashes,
per-scenario outcomes, costs and timings, but omits negotiation transcripts.

These numbers cannot be compared directly with the teammate's hosted 0.62733 or the
team leaderboard mean around 0.7. The previous model-authored approach is not included
in this no-API comparison. A high scripted score does not establish a high hosted score.

## Remaining priorities and the next online check

1. Capacity and RFQ are the weakest synthetic families. Test supplier response timing,
   volume/lead-time tradeoffs and closing opportunity cost against unfamiliar behaviours.
2. The optional advisor may help interpret objections but its impact is unmeasured.
   Its fixed language is intentionally limited; it cannot invent bespoke commitments.
3. Enlarge independent scenarios before tuning anchors. Current scripts share structure
   with the imported planner's development suite. Do not optimize toward hidden floors.
4. Review supplier standards when attachments arrive late. Strict validation can reject
   an attractive incomplete quote; it must not guess a missing commitment to a must-have.
5. A ten-case concurrent final wave remains unverified for this version. Local runtimes
   alone do not establish network, rate-limit or hosted supplier capacity.

No hosted benchmark was started, no leaderboard position refreshed, and no final runner
or submission executed. The previous failed `model_proposals_01` report remains unchanged.
Its bounded journal has two unused authorized slots (P03 and P04), subject to fresh
reconciliation with other team activity. Do not run all ten or reuse an old frozen plan:
that would either exceed remaining authorization or test the wrong source version.
Prepare a new explicit remaining-slot plan with this exact commit before any online test;
additional sessions require separate authorization. The raw `arena play` CLI does not
replace that persistent budget/session accounting. No claim that this version beats the
teammate online is justified yet.

## Provenance and integration choices

Imported from `origin/codex/main-preflight-eval-20261010` at
`c598f8c42db653f5291c3c25d074ad58a5a52621`: `agents/buyer.py`, `research.py`,
`strategy.py`, `commercial.py`, `exchanges.py`, synthetic evaluator helpers, and associated
regression tests. The comparison branch itself was not checked out, merged or modified.
Its benchmark/stress modules were renamed `buyer_simulation.py` and `buyer_stress.py`
to preserve our existing accounting tools. Its bounded RFQ coordinator was adapted into
`play.py`; our session-open policy and existing runner remain.

We did not adopt its separate OpenAI adapter, CLI aliases or automatic session recreation.
Imported tests for those different interfaces were excluded; our combined factory, model
failure, missing commitment, pending reply, case isolation and cache-refresh tests replace
them. The existing OpenAI transport/budget tests still exercise our adapter. The production
entry point is `CombinedAgent`; the imported `BuyerAgent` is also retained as the explicit
local baseline. Tests and evaluation changes are recorded in the feature-branch commit.
