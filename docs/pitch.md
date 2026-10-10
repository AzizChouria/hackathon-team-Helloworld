---
marp: true
title: Hello World Buyer
paginate: true
---

# Hello World Buyer

Autonomous procurement with grounded arguments and explicit deal checks.

Research the supplier → propose complete packages → compare total cost → close or walk away.

<!-- 40 seconds: introduce Hollerau and the challenge. -->

---

# A low price can be an expensive deal

- Short contracts leave demand uncovered.
- Payment, freight, delivery and quality change the economics.
- Strategic suppliers need a sustainable relationship.
- One broken must-have gives a zero score.

We optimise the published cost of covering the full need.

<!-- 45 seconds: explain the 12-month versus 24-month example from the brief. -->

---

# Read what matters to this supplier

- Notes and letters reveal cash needs, priorities and relationship history.
- Contracts and quote PDFs establish the terms.
- Market indices and scorecards supply reproducible arguments.
- Sunday updates join the same research pipeline.

Every outgoing numerical claim is computed and attached to its source IDs.

<!-- 55 seconds: use Brandlhuber's outdated index spreadsheet and relationship note as examples. -->

---

# Give the model a bounded job

The model selects relevant evidence and a negotiation tactic.

Python searches the allowed terms, computes total cost, enforces requirements and writes the
grounded message. A slow or invalid model response uses the computed strategy.

The planner can trade price against early payment or a longer commitment.

<!-- 60 seconds: explain why this division makes decisions inspectable. -->

---

# Keep every supplier thread moving

Independent requests run concurrently. Each supplier has at most one message in flight.

Before accepting, compare complete standing offers against the alternative. Apply the same
checks when the final wave's deadline forces closure.

Private traces retain the evidence, tactic, estimated costs and closing reason.

<!-- 45 seconds: walk through a local benchmark decision or a future hosted replay. -->

---

# Local evidence, clear limits

| Scripted case | Starter | Buyer |
|---|---:|---:|
| Price negotiation | 0.521 | 0.888 |
| Competing quotes | 0.513 | 0.886 |
| Framework renewal | 0.678 | 0.927 |

The hosted P01 practice run closed at **0.755** with the configured model and verified claims.
The final small concession adjustment was tested locally afterward. Simulator scores demonstrate
working mechanics; this one hosted run is not a prediction of final competition results.

<!-- 55 seconds: explain limits and replace or supplement this slide with actual hosted results when available. -->
