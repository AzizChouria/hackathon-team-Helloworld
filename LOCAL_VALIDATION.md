# Local validation and strategy changes

This revision fixes the four failing hybrid regressions and adds adversarial checks. No hosted
practice sessions, paid model requests, final runs, submissions, or leaderboard requests were
made during this local improvement pass. The user reported team usage of 110/200; it was not
independently refreshed. These checks do not consume that quota.

## Verified results

- Full suite: **76 passed, 1 skipped** in 53.69 seconds. Skip: optional MCP dependency.
- Ruff: all checks passed.
- Cached case economics: **19 cases valid**; no hosted supplier behavior is simulated by that check.
- Deterministic comparison: **36 fixtures**, before = commit `08002e0`, after = this revision.
- Revised total cost: **11 lower, 25 equal, 0 higher**. These are fixture counts, not scores.
- Both revisions: 33 valid deals and 3 no-deals exercising the contractual alternative.
- Revised simulator timeouts: 0. Separate asynchronous tests exercise blocked suppliers in both
  thread orderings and verify the ready supplier closes before the blocked reply finishes.
- On the unmodified standard supplier script with 8% buyer financing, cost falls 0.56% for S01,
  ties S02, and falls 0.60% for S03. Across the constructed stress fixtures, the largest cost
  reduction is 9.53%. That is not a forecast for real suppliers.

Machine-readable evidence: `benchmarks/local_comparison.json`, including all fixture costs,
no-deal alternative costs, rounds and timeout counts. `local_comparison_initial.json` preserves
an earlier iteration which exposed premature closing. The final rule was revised, and a regression
now ensures unchanged opening offers do not force early closure. The initial summary counted
only paired valid deals; the final summary also compares realized contractual alternative cost.

## Changes and rationale

1. Replace the RFQ batch barrier with a coordinator that tracks outstanding requests and timestamps
   each response before attachment parsing. An in-flight supplier's old sheet is never accepted.
   Near a ready thread's guard, close deterministically using available offers; skip extra model
   time. A late closure 409 is reconciled from server state, without creating another session.
2. Require known supplier/explicit/fixed terms to prove numeric must-haves. Buyer planning
   defaults remain available to the official cost helper but cannot fabricate agreement.
3. Offer at most three different non-price profiles, each cheaper than the best feasible standing
   offer. Do not expose multiple prices for identical terms. This makes financing, freight,
   duration and indexation concessions conditional on reciprocal economic benefit.
4. Stop additional concessions after deterioration or a plateau in an earned price/cost concession,
   provided the currently available deal beats the contractual alternative. Repetition of an
   unchanged opening alone is not enough. No expired historic offer ID is accepted.
5. Reserve cited facts across RFQ batches, cap distinct cited IDs to three, prioritize fresh trigger
   documents, and invalidate cached briefs when case contents or dataset files change.
6. Use the second bounded model call on the first supplier reply, when there is time. Log actual
   model invocation separately from deliberate deterministic fallback.

## Repeat locally

From `starter-kit/`:

```powershell
uv run --offline --extra sim pytest -q
uv run --offline ruff check .
uv run --offline python -m arena_kit.benchmark offline
uv run --offline python -m arena_kit.local_eval --baseline 08002e0
```

The first command starts its own localhost simulators. The comparison is entirely in process;
no API configuration is required. It loads trusted historical source from the specified local
Git commit and uses four supplier scripts across S01-S03 and financing rates of 0%, 8%, and 20%.
The cached-case command requires the existing private practice case listing. Do not run a hosted
`arena play`, `arena run --set practice`, or `benchmark run` command to reproduce these checks.

## Limits and next decisions

Local scripts are not the hosted suppliers. The 36 fixtures were used during development,
so the comparison is a regression check, not a held-out performance estimate. The model was
mocked/disabled and its conversational benefits are unmeasured in this revision. A supplier
could concede after an apparent plateau, or reject terms a script accepts. The 35-second guard
starts at local response receipt, with reserve for network/processing time; server timing and
venue network delays still matter. A request already sent cannot be canceled remotely.

The unchanged historical hosted mean is 53.15/100 at commit 08002e0. No revised hosted score,
new team rank, or improvement over the team's best runs is claimed. To establish that requires
separately authorized hosted comparisons. There is no honest local-only stopping criterion that
proves the revised agent beats unseen hosted suppliers. Before the final, refresh the data, run
these checks, verify actual account/network limits and jury access, and review the final-run
procedure in HYBRID_README.md. No final execution is authorized by this document.

## Subsequent benchmark preparation

The next preparation revision passes **87 tests with one optional skip** and Ruff. It adds a
separately gated benchmark runner, stronger model identity checks, model history/cost context,
and all-19-case mocked context checks. Deterministic local results remain unchanged.
See REVISED_BENCHMARK_READY.md for the selected configuration, fresh API probe and budget.
No revised hosted supplier results exist yet.


## Subsequent preference-sensitive strategy validation

See [STRATEGY_IMPROVEMENT_REPORT.md](STRATEGY_IMPROVEMENT_REPORT.md) for the latest changes
and limitations. Against the previously tested commit `5e21aac`, the 36 existing comparisons
are unchanged; 72 additional synthetic preference scenarios produce 18 lower costs, 54 ties,
and no higher costs, with all 72 valid deals and no timeouts. These are development fixtures,
not hosted supplier results. The revised hosted mean remains unmeasured. Source changes
invalidate the old frozen benchmark plan; refresh preparation after committing this revision.


## Reliability checks after the stopped revised hosted batch

105 tests pass, one optional MCP test is skipped, and Ruff passes. Added checks cover unavailable
attachments, authentication errors, per-operation download timeouts without retries, safe error
metadata, and recovery from a current timeout quote rather than stale message history.
These post-run changes have not been hosted-tested. They do not establish the root cause of
P11's original ArenaError. See REVISED_BENCHMARK_REPORT.md for the failed run and manual recovery.
