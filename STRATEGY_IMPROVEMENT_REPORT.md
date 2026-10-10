# Strategy improvements and comparison readiness

These are local development results, not a new hosted benchmark. No hosted session or paid
model call was made in this improvement pass. The teammate comparison remains unproven online.

## Current evidence

| Measurement | Previous tested revision | This revision | Meaning |
|---|---:|---:|---|
| Last actual hosted ten-case mean | 0.531496 | Not tested | Historical original agent; not either local revision |
| Teammate supplied hosted ten-case mean | 0.627333 | N/A | Deterministic fallback: 43 model HTTP 404 failures |
| Standard S01-S03 local score at 8% | 98.5463/100 | 98.5463/100 | Synthetic simulator, model disabled |
| Original 36 synthetic reference mean | 70.0385/100 | 70.0385/100 | Reference optimum is not a hosted optimum |
| New 72 preference scenarios | Baseline `5e21aac` | 18 cheaper, 54 equal, 0 dearer | Full buyer costs, no purported competition score |

Across all 108 comparisons against `5e21aac`: **18 cheaper, 90 equal, 0 dearer**.
Original fixtures: 33 valid deals, 3 contractual no-deals; new fixtures: 72 valid deals.
No simulated buyer timeouts. All 19 cached practice cases pass economic/evidence/mocked-context
validation; those checks do not simulate all hosted suppliers and have no hosted scores.

For the new 72 fixtures, average per-fixture relative cost reduction is 0.8709%; among the
18 improved fixtures it is 3.4837%; largest reduction is 4.8639%. These percentages describe
buyer-cost changes, not negotiation-score percentage points. There are 24 fixtures per public
simulator case: S01 has 0 improvements/24 ties; S02 has 10/14; S03 has 8/16.

## What changed

- Apply each assigned field's must-have constraints before beam truncation can discard every
  economical feasible branch. Preserve explicit supplier standards outside enumerated options.
- Treat missing numeric defaults differently from an explicitly quoted no-index clause.
- Select package diversity within the cost ceiling of the best feasible standing offer.
- After the first supplier reply, consider keeping their non-price terms in exchange for an
  economically compensating price. This route never costs more than the most expensive
  otherwise selected package and never exceeds the available deal. It is bounded, validated,
  and omitted if uncertain supplier relationship costs prevent safe price solving.
- Track the best previous full-cost package when setting price concessions. A lower price
  offered to compensate for worse other terms must not reset the main package's price anchor.
- On the last configured counter, after three identical supplier term sets, allow a bounded
  price concession on the best economic profile only. Do not concede both price and payment
  or freight simultaneously. Deterministic closing and alternative comparisons still apply.

Implementation: `starter-kit/arena_kit/agents/optimizer.py` and `agents/hybrid.py`.
The model transport, model selection, budget, call limits, and hosted-session gates are unchanged.
The final-bid heuristic and commercial-profile option remain hypotheses about real suppliers.
No practice scores, teammate terms, replay policies, hidden optimum, or leaderboard information
were added to runtime code.

## Validation design and limitations

Final full suite: **95 passed, 1 optional MCP skip**, in 49.17 seconds. Ruff passes.

The new preference simulator varies 3 public simulator cases, 2 quoted payment terms,
3 private synthetic price thresholds, 2 buyer financing rates, and flexible versus fixed
non-price supplier requirements (72 combinations). Price thresholds are used only by the
synthetic supplier, never passed to the buyer. Among equally priced acceptable packages,
the simulator chooses the one with greater buyer cost, preventing favorable package ordering
from disguising unnecessary concessions. The fixtures contain no hosted supplier transcripts.

Several iterations initially regressed results. They exposed cross-package anchor contamination,
repeated discounts after rejection, and simultaneous final price/payment concessions. Those
were corrected before retaining the implementation. These fixtures were used in development;
**they are not held-out evidence, statistical confidence intervals, or proof of unseen superiority**.
A supplier may reward other timing or commercial compromises. A stochastic hosted agent can
perform differently, and model guidance was disabled in the local cost comparisons.

## Reproduce

Run from `starter-kit/`:

```powershell
uv run --offline --extra sim pytest -q
uv run --offline ruff check .
uv run --offline python -m arena_kit.benchmark offline
uv run --offline python -m arena_kit.local_eval --baseline 5e21aac --output ../benchmarks/local_tradeoff_comparison.json
uv run --offline python -m arena_kit.tradeoff_eval --baseline 5e21aac
```

The comparison files are `benchmarks/local_tradeoff_comparison.json` (36 fixtures) and
`benchmarks/tradeoff_scenarios.json` (72). The latter intentionally reports no score, because
its suppliers do not have the standard simulator's optimum. Normal tests use mocks/localhost.
The cached-case checker needs the existing private practice listing but makes no hosted calls.

## Online comparison still required

To beat the supplied teammate batch, the new agent must exceed **0.6273333070321647** over
all ten of the same hosted cases. A single successful batch establishes a higher observed
mean, not reliable superiority across randomness or unseen final cases. The team leaderboard's
best-per-case aggregate is a separate metric and cannot substitute for this batch mean.

The original ten-session authorization is exhausted. A separately authorized ten-case batch
is ready through `arena_kit.revised_benchmark`; do not run it until that new allowance is approved.
After committing changes, run `uv run --offline python -m arena_kit.revised_benchmark prepare`
to refresh the frozen source/data/configuration and read-only quota/budget checks. This does not
start negotiations. Execution needs explicit approval and the `run --execute-approved` command.
No indefinite repeat-until-winning loop is authorized or methodologically sound.

Last accounted development estimate: $0.56062. No extra spend here. The prepared full-batch
upper forecast was $4.57642 cumulative, below the $5 cap; preparation refreshes the ledger.
Astra/high was API-verified previously; this pass did not re-probe it or change effort.
No final runner, final submission, merge, or shared-main update was performed.
