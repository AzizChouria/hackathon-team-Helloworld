# Local score optimization

This records the earlier opening/concession optimization. The subsequent
[equal-value package change](package-exchange-validation.md) reached **0.834394** on the same
holdout, versus **0.815851** for this version in a new paired comparison, using no hosted runs.

On 10 October 2026, the candidate reached a **0.816–0.821 mean on the 48-case local holdout**,
compared with **0.611** for the starting buyer. Development runs reached **0.824–0.825**, up from
**0.590**. No evaluated case failed or breached a must-have. These are synthetic local scores;
the last hosted rehearsal remains **0.621** and predates these changes.

A subsequently requested [single hosted P05 test](hidden-case-validation.md#minimal-hosted-follow-up-of-the-optimized-buyer)
scored **0.452** with a valid deal. It did not reach 0.8; the synthetic mean has not translated into
an established hosted mean of 0.8.

## Evaluation design

[The local evaluator](../starter-kit/arena_kit/stress.py) uses the supplied simulator's message
validation, documents, acceptance and cost calculation. It adds six case families—price,
renewal, RFQ, quality, capacity and indexation—and four scripted supplier styles: steady,
late-conceding, reciprocal and impatient. Each family/style has two economic variants per split.
Case and supplier IDs are new; supplier reservation prices and term costs stay private to the
evaluator. An exhaustive search over compliant term combinations provides its scoring reference.

Development and holdout seeds were fixed before tuning. The holdout changes prices, demand,
financing costs and supplier parameters, but uses the **same four opponent styles**. It is not
a test of unseen supplier behaviour. Failures count as zero and no cases are dropped. The
[machine-readable record](local-score-optimization.json) contains per-case outcomes, source and
suite fingerprints, iteration summaries and repeat results.

## Changes retained

- Quality cases open at 86% of the asking price instead of 96%; the planner still offers only
  compliant quality packages. Strategic cases open at 90% instead of 96% when an estimate does
  not require a higher anchor. Existing sustainable-margin estimates and relationship-cost
  valuation remain active.
- Once the supplier explicitly confirms the non-price terms of a proposed package, concessions
  use the remaining round budget. A meaningful fall in compliant full cost slows the next price
  move; explicit resistance requires a larger reciprocal move. The policy uses transcript data,
  not case IDs or private supplier floors.
- Price-only counters retain the original 22% gap step. This protects the chance to secure
  contract coverage, payment or warranty terms before the supplier's final offer.

## Iteration results

| Development version | Mean | Observation |
|---|---:|---|
| Starting buyer | 0.590 | Quality and capacity openings gave away value. |
| Firmer quality opening | 0.660 | Quality improved while retaining must-have compliance. |
| Responsive concession pace | 0.790 | Supplier movement no longer automatically triggers a large buyer concession. |
| Firmer strategic opening | 0.824 | Capacity improved, but the original renewal simulator exposed a regression. |
| Slow concessions only after commercial terms are confirmed | **0.825** | Restored the original simulator results while retaining the broader gains. |

The renewal regression was material: slowing every price concession let the supplier finish on
its shorter standard contract, dropping S03 to 0.291. The confirmation condition restored S03
to 0.927. This candidate retains S01 **0.888**, S02 **0.886** and S03 **0.927**.

## Holdout comparison

| Family | Starting buyer | Candidate |
|---|---:|---:|
| Price | 0.787 | 0.942 |
| Renewal | 0.794 | 0.871 |
| RFQ | 0.599 | 0.719 |
| Quality | 0.263 | 0.852 |
| Capacity | 0.477 | 0.676 |
| Indexation | 0.746 | 0.835 |
| **All 48 cases** | **0.611** | **0.816** |

In this first paired holdout comparison, 47 cases improved and one tied. Repeating the unchanged
candidate twice produced holdout means of 0.816 and 0.821. RFQ thread scheduling can change the
result; these repeats check scheduling variation, not independent new economic scenarios.
The worst holdout case scored **0.500**, so the 0.8 target is met as a mean, not for every case.

At this revision the complete local test suite passed **91 tests, with 2 skipped**; Ruff passed. Tests cover the
concession rules, retention of full contract terms, private test profiles, scoring arithmetic and
failed-run accounting, alongside the existing negotiation and timing checks.

## Reproduce locally

From `starter-kit` with dependencies installed:

```bash
.venv/bin/python -m arena_kit.stress --split dev --out /tmp/score-dev.json
.venv/bin/python -m arena_kit.stress --split holdout --out /tmp/score-holdout.json
.venv/bin/arena benchmark --data ../data --out /tmp/original-simulator.json
.venv/bin/pytest -q
.venv/bin/ruff check .
```

These commands open no hosted sessions and make no model calls. The stress suite exercises the
deterministic buyer policy; it does not validate model-written tactics, real supplier latency,
or unknown supplier preferences. It does not model private strategic relationship costs in the
synthetic score. An actual hosted mean of 0.8 remains unverified.
