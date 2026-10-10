# Supplier preferences and competitive closing

Implementation and evaluation on **10 October 2026**. This builds on the
[equal-value packages](package-exchange-validation.md), with the configured `buyer-llm` model
unchanged: `gpt-6.1-sol`, low reasoning effort, ten-second decision limit.

## Why another change was needed

The previous P05 hosted transcript showed a concrete mismatch. A supplier repeatedly explained
that the requested 35-day delivery required overtime and offered a 42-day alternative, which
met our delivery requirement. The buyer kept making 35-day packages. Another bidder reached
a final offer and the RFQ closed while the capacity-constrained bidder still had room to reply.
This identified an opportunity to improve the negotiation process; it did not reveal the
supplier's private floor or prove that a particular price was achievable.

## Implemented policy

1. **Counter the supplier's combination of terms.** A complete compliant quote reveals an
   operationally workable combination. Price that combination at our own full-cost target and
   present it first. Linked preferences, such as early payment with more production time, stay
   together. Other equal-value packages remain available, within the three-package limit.
2. **Repair an infeasible opening with the smallest permitted change.** If a quoted lead time
   exceeds a hard limit, counter with the nearest allowed compliant value. Do not automatically
   demand an even shorter lead time merely because it minimizes delay costs at an unchanged
   price. The price reduction must still pay for the modelled delay cost.
3. **Carry concessions forward by total cost.** When the preferred package changes, convert the
   previous bid's total cost into the new term basis before applying the existing concession
   rule. A cash price for one payment/delivery combination is not a price commitment for another.
4. **Use verified competition.** A cheaper compliant rival already selected by the evidence
   checks takes priority in the RFQ message even if the model omits it. The code preserves
   citation limits and never invents a rival or treats an infeasible quote as usable leverage.
5. **Anchor opening RFQ bids to the market.** Use the smaller of our computed opening cost
   and a compliant rival's full cost times the existing opening factor (86%, or 90% for a
   strategic case). Translate that budget into each supplier's own term basis. This applies
   only before our first priced proposal, so it cannot retract a previous bid. Infeasible
   rival quotes are excluded; an infeasible cost target does not create an invalid package.
6. **Protect the best offer while challenging another bidder.** When any bidder becomes final,
   keep the cheapest ready quote available to accept. An active *other* bidder within 3% of
   that incumbent's full cost can receive one more proposal. This is limited to one challenge
   per bidder and terminal quote during the run. Pending challenges use a 45-second age guard;
   ordinary waiting uses 30 seconds. Both the incumbent's reply clock and the final quote's
   clock are checked, and the wave closing reserve still applies. The 3% threshold is a
   heuristic, not an estimate of a supplier's remaining margin.

The production change is in [buyer.py](../starter-kit/arena_kit/agents/buyer.py), with focused
[regression tests](../starter-kit/tests/test_competition.py). The original package exchange
pricing remains in [exchanges.py](../starter-kit/arena_kit/exchanges.py). No supplier IDs, case
IDs, private scoring references or private supplier floors enter the new policy.

## Local comparison before the hosted test

The reference is the immediately preceding equal-value buyer. Both versions used the unchanged
stress evaluator and its existing seeds. The holdout varies economic parameters but uses the
same scripted supplier styles; these are not estimates of hosted performance.

| Metric | Previous buyer | New buyer |
|---|---:|---:|
| Development mean, 48 cases | 0.837962 | **0.850448** |
| Parameter holdout mean, 48 cases | 0.828592 | **0.842956** |
| Holdout RFQ mean | 0.731745 | **0.805474** |
| Holdout worst case | 0.511330 | 0.511330 |
| Errors / must-have breaches, both splits | 0 / 0 | 0 / 0 |

The holdout contains **23 improvements, 21 ties and 4 regressions**; its largest regression is
0.018142 in a renewal case. Development contains 21 improvements, 21 ties and 6 regressions.
RFQ thread scheduling varies: the previous report measured the same reference buyer at
0.834394 on the holdout, compared with 0.828592 in this paired run. The new mean exceeds both,
but the observed difference is not a statistically established effect size.

The supplied S01–S03 benchmark scores remain **0.888, 0.886 and 0.927**. The complete suite passes
**117 tests, with 2 optional tests skipped**, and Ruff passes. New tests cover linked preferences,
minimal delivery repair, total-cost continuity, verified rival evidence, bounded final challenges,
expiry protection and an improved challenger winning through the real local coordinator.
The timing regression specifically holds the best open quote ready while another bidder is
pending, then verifies that the agent accepts that protected quote at the waiting limit.

[Machine-readable local results](competitive-strategy-local.json) include individual scores,
regressions and source/suite fingerprints. The baseline snapshot used for comparison is local
at `/tmp/buyer-before-competitive-improvement.py`, not a repository artifact.

## Hosted discovery and correction

The first candidate had a local holdout mean of 0.837533 and passed 113 tests, but its single P05
hosted test scored **0.350283**, below the earlier 0.451910. It produced a valid deal at
**€276,779.44**, with six verified claims. [Replay](https://arena.tacto.ai/replay/1a8579dfab749578).

It challenged both active bidders after a more expensive bidder became final. At the waiting
limit, both potentially better offers were in flight, so only the expensive final quote was
ready to accept. The timing flaw was not covered by the fast scripted opponents. The corrected
policy above preserves the cheapest ready quote, checks its expiry, and adds the market-based
opening anchor. The failed attempt remains in the evaluation record rather than being excluded.

The corrected candidate was rechecked locally before a second, final P05 hosted verification.

| Hosted P05 attempt | Score | Total cost | Outcome |
|---|---:|---:|---|
| Earlier minimal test, before this work | 0.451910 | €268,433.76 | Valid deal with supplier 70210 |
| First candidate: timing flaw | 0.350283 | €276,779.44 | Valid deal, but cheaper bidders were pending |
| Corrected candidate | **0.458784** | **€267,869.28** | Valid deal with supplier 70250 |

The corrected run took **222.20 seconds** of its 480-second budget. It closed at **€31.50 per
unit**, 14-day payment, 35-day delivery and a 600-ppm commitment. All must-haves passed;
the host reported **7 verified claims** and no contradicted claims. No rule fallback was
observed. [Corrected replay](https://arena.tacto.ai/replay/7722d97f5c8f6090).

The improvement over the earlier minimal test is **0.006874 score points** and **€564.48**,
entirely explained by the winning supplier's lower modelled defect cost. The unit price did
not improve. This is **a small gain, not the requested major breakthrough**, and remains below
the earlier observed P05 best of 0.503577. Reaching 0.8 would require total cost no greater
than €239,848.33, still €28,020.95 below this deal. Those figures are post-run analysis;
the buyer does not receive the private scoring reference during negotiation.

The corrected hosted run issued **zero final challenges**, so it did not exercise the protected
challenge path. That path has local regression coverage. The first run issued two challenges
and exposed the flaw. One observation per changing version cannot establish a causal effect or
a reliable hosted mean. The synthetic holdout score is not a substitute for this hosted result.

**Exactly two hosted sessions were used in this iteration.** The service reported 495 practice
sessions available before them and 493 afterward. Both runs, their source fingerprints, claim
counts and terms are retained in the [hosted record](competitive-strategy-hosted.json).
The corrected hosted fingerprint begins `cf0c3cf3ecff`; the current runtime source matches it.

## Reproduce local checks

From `starter-kit`:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/python -m arena_kit.stress --split dev --out /tmp/competitive-dev.json
.venv/bin/python -m arena_kit.stress --split holdout --out /tmp/competitive-holdout.json
.venv/bin/arena benchmark --data ../data --out /tmp/competitive-original.json
```
