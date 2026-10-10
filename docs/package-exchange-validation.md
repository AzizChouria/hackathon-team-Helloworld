# Equal-value package exchanges: local validation

Recorded **10 October 2026**. Implemented and tested locally, with **zero hosted sessions and
zero model calls**. This follows the P05 hosted result of 0.452; it does not replace that result
or establish a hosted score of 0.8.

## The problem with the previous planner

The planner optimized commercial terms at a fixed unit price. That misses exchanges in which
the supplier's saving exceeds the buyer's cost. For example, another week of production time
can avoid expensive overtime, even when that week creates a smaller lateness cost for us.
Choosing only the best delivery time at the same price never tests that possibility.

The early-payment discount also covered only part of the buyer's financing cost. Its lower
headline price could therefore cost more overall. The saved P05 decision trace shows higher
estimated total costs for the cash alternatives. That identifies a pricing weakness; the trace
alone does not prove which change would have improved the hosted outcome.

## The new strategy

Keep the primary bid and use its full-horizon cost as a common budget. Price each alternative
so that accepting it costs no more than that budget:

```text
For each permitted commercial package:
    choose the highest cent price with total_cost(package) <= primary_bid_cost
    retain the package only if all requirements hold
```

This lets the supplier select the exchange that best fits its operation. Earlier payment must
earn enough discount to cover financing. Lower complaint liability must earn enough discount
to cover residual defects. Index exposure must be paid for. A new delivery alternative offers
the longest permitted lead time that meets the must-haves, with a price reduction covering
the modelled delay cost. Up to three complete packages are sent.

The planner includes estimated relationship penalties when present. Because these can make
cost fall and then rise with price, it searches the upper feasible price branch rather than
assuming that a lower price always helps. It preserves previous prices for identical complete
exchanges; an alternative that cannot fit the budget without retracting that price is omitted.
Prices for different delivery or liability terms remain distinct commitments.

Implementation: [exchange pricing](../starter-kit/arena_kit/exchanges.py),
[buyer integration](../starter-kit/arena_kit/agents/buyer.py), and
[mechanism tests](../starter-kit/tests/test_exchanges.py). The configured model and runtime
prompt remain unchanged: `gpt-6.1-sol` with low reasoning effort chooses tactics and prose,
while code sets binding terms. These local tests exercise the deterministic policy.

## Comparison on the unchanged stress suite

The reference is the immediately preceding buyer, not the much older 0.611 baseline.
Both versions used the same frozen scenarios, private supplier profiles and scoring oracle.
The evaluator was not changed.

| Metric | Previous buyer | New buyer |
|---|---:|---:|
| Development mean, 48 cases | 0.823568 | **0.839578** |
| Parameter holdout mean, 48 cases | 0.815851 | **0.834394** |
| Holdout worst case | 0.500493 | **0.511330** |
| Errors / requirement breaches, both splits | 0 / 0 | 0 / 0 |

In the paired holdout, **33 cases improved, 15 tied and none worsened**. Development had
35 improvements and 13 ties. The three supplied simulator scores remained **0.888, 0.886 and
0.927**. The initial development prototype scored 0.837962; the final run scored 0.839578.
Their differences were confined to RFQ cases, where thread scheduling can vary. This is not
evidence of a statistically stable gain of exactly this size.

| Holdout family | Previous buyer | New buyer |
|---|---:|---:|
| Price | 0.942466 | 0.950875 |
| Renewal | 0.870992 | 0.881970 |
| RFQ | 0.719268 | 0.766555 |
| Quality | 0.851809 | 0.864999 |
| Capacity | 0.675569 | 0.694526 |
| Indexation | 0.835000 | 0.847436 |

The holdout changes parameters but retains the same scripted opponent styles. Capacity and
RFQ remain weaker families, and a mean above 0.8 does not mean every case reaches 0.8.
Actual supplier reasoning, latency and model-written persuasion remain untested by this suite.

## Independent delivery mechanism check

A separate fixed-price supplier test uses no round-based concessions. Its private price changes
only with production time. The buyer sees neither its floor nor its saving. Both buyers negotiate
through the real local play loop, including acceptance and requirement checks.

| Supplier saving from an extra week, per unit | Previous total cost | New total cost |
|---|---:|---:|
| €0.00 | €634,600.93 | €634,600.93 |
| €0.50 | €634,600.93 | €617,336.20 |
| €2.00 | €634,600.93 | €561,342.00 |

When the supplier gains nothing from waiting, the buyer retains the shorter lead time.
When the saving exceeds our delay cost, the new exchange unlocks the cheaper compliant deal.
These are constructed mechanism tests, not forecasts for P05 or other hosted cases.

## Verification and reproduction

**102 tests passed, 2 optional tests skipped; Ruff passed.** Added checks cover financing,
delivery, index and defect costs, cent rounding, nonlinear relationship costs, infeasible
exchanges, prior commitments and end-to-end supplier choice.

From `starter-kit`:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/python -m arena_kit.stress --split dev --out /tmp/exchange-dev.json
.venv/bin/python -m arena_kit.stress --split holdout --out /tmp/exchange-holdout.json
.venv/bin/arena benchmark --data ../data --out /tmp/exchange-original.json
```

[Machine-readable results](package-exchange-validation.json) record paired case scores, costs,
suite fingerprints and source hashes, including the new exchange module. The previous buyer
was preserved locally as `/tmp/buyer-before-package-rethink.py` for the comparison; that temporary
snapshot is not a repository artifact. Reproduction commands above test the current buyer.
