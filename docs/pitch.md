---
marp: true
title: Hello World Buyer
paginate: true
---

# Hello World Buyer: buy the whole deal

An autonomous buyer that negotiates the cost of supply, not just the number on the quote.

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

# Let the model negotiate; let code price the deal

| Model | Deterministic planner |
|---|---|
| Read the supplier's priorities | Search allowed commercial terms |
| Answer objections and request approval | Compute total cost and check requirements |
| Choose verified supporting evidence | Control binding offers and acceptance |

A slow or invalid model response uses a computed strategy. Numerical claims come from code.

Trade early payment, duration, indexation and complaint liability at the same buyer total cost.
Test extra permitted delivery time when a price reduction can cover its cost.

<!-- 60 seconds: explain why this division makes decisions inspectable. -->

---

# A replay we can explain

In the capacity case, the buyer needs the full allocation within the required delivery window.
Asking for an even shorter lead time adds supplier effort without reducing the buyer's cost.

Our planner offers a longer firm commitment and the delivery time the buyer actually needs.
It compares the resulting agreement on total cost and verifies the allocation before accepting.

Each decision retains its evidence, estimated costs and closing reason. Concurrent RFQs reserve
citations before replies arrive, so parallel messages do not spend the same evidence twice.

<!-- 45 seconds: open the capacity replay linked in evaluation.md and explain the actual terms. -->

---

# Hosted evidence and the next priority

| Practice case | Baseline | Later observation |
|---|---:|---:|
| Renewal P03 | 0.906 | 0.919 |
| Capacity P10 | 0.477 | 0.555 |
| Quality P11 | 0.314 | 0.536 |
| RFQ P05 | 0.400 | 0.304 |

RFQ timing remains the priority: protect settlement without giving up too much negotiation value.
An earlier ten-case batch averaged **0.559**, including one acceptance failure. The later
480-second rehearsal averaged **0.621** with ten valid deals. Later RFQ and concession changes
have local tests and one hosted P05 follow-up scoring **0.452**. These observations span versions and supplier
randomness, so they are not a controlled trial.

[Latest rehearsal and replays](hidden-case-validation.md) · [Earlier sessions](evaluation.md) · [Operating strategy](strategy.md)

<!-- 55 seconds: explain the quality trade, disclose the RFQ regression and describe the next repeated comparison. -->
