# Negotiation strategy to use

**Optimise the complete agreement, offer something the supplier values, and protect the opportunity to close.**
Use a different commercial approach for each case family while keeping the same cost calculation,
must-have checks and acceptance rules. Our next priority is reliable RFQ settlement; further price
tuning comes after that.

This playbook uses the 34 recorded hosted practice runs from 10 October 2026. Results and replay
links are in [the evaluation report](evaluation.md), with every experiment preserved in
[evaluation.json](evaluation.json). These are observations across several versions, not proof of
performance on hidden cases.

The later [local score optimization](local-score-optimization.md) tests the current opening and
concession rules on a separate synthetic suite. Its scores must not be combined with hosted results.

## 1. What the results tell us

| Observation | Decision for our strategy |
|---|---|
| P03 renewal scored 0.900–0.919 in the baseline/revised/full runs; offering the asking price as an alternative produced 0.762. | Keep a price target while trading duration and payment. A stated price freeze is a reason to seek approval of a package, not to grant the asking price immediately. |
| P04 repeatedly scored 0.815, but the asking-price experiment fell to 0.056. | Preserve the renewal approach. Evaluate payment and contract length together; a long payment period alone does not make a good deal. |
| P10 capacity improved from 0.477 to 0.555–0.570. | Offer firm coverage and a longer commitment; allow the delivery time the buyer actually needs. |
| P11 quality scored 0.314 initially, 0.307 in the broad validation, and 0.536 after adding a simpler compliant package. | Offer a route that meets the required quality threshold with less complaint liability, alongside stronger protection packages. |
| P02 scored 0.503 in two runs; indexed raw-material deals scored 0.614–0.679 on P08. | Keep a priced, symmetric index alternative available when indexation is negotiable. Include its future cost and risk. |
| P05 reached 0.504, but also suffered a failed acceptance; the more conservative closing follow-up scored 0.304. | Treat RFQ timing as unresolved. Protect expiring offers, but measure the price of closing early before tuning the waiting policy. |
| P18 had an acceptance error in the ten-case run; subsequent runs closed at 0.467. | Refresh rejected offers, exclude the rejected ID, and revalue the remaining choices. A good negotiated price is useful only if settlement succeeds. |

The same five cases averaged **0.583 in the baseline and 0.620 in the later ten-case run**.
The complete ten-case run averaged **0.559**, counting its P18 error as zero. Those averages answer
different questions; do not compare unmatched case sets or replace failures with earlier best scores.

## 2. Select the commercial approach

Classify the case from its goal, negotiable fields, constraints and supplier documents. The case
IDs below are examples; the live agent must apply these rules to unfamiliar suppliers and parts.

| Case family | Supplier interest to investigate | Opening exchange | Boundary |
|---|---|---|---|
| Strategic price increase — P01 | Cash flow, justification for the increase, continuity | Later effective date; faster payment for a lower price; relevant index or notice evidence | Preserve estimated supplier sustainability. Offer payment changes only if permitted. |
| Framework renewal — P03/P04 | Firm demand, administrative simplicity, approval authority | Cover the full demand horizon; exchange a longer commitment for price/payment improvements | Do not let a 12-month agreement hide an expensive uncovered second year. Do not pay for unnecessary excess volume. |
| Routine bundling — P07 | Consolidated business, fewer orders, committee approval | Longer framework and predictable purchasing, with a priced cash alternative | Fixed volume stays fixed. A forecast is evidence, not a promise of extra orders. |
| Competitive RFQ — P05 | Cash, spare capacity, reference business, delivery feasibility | Contact all bidders; compare compliant offers; use a cheaper valid competing quote | A cheaper quote that misses the delivery requirement is not equivalent leverage. Protect standing offers from expiry. |
| Constrained capacity — P10 | Production planning and dependable commitment | Required annual allocation, longer duration, and the longest delivery time that adds no buyer cost | Meet the minimum allocation. Avoid paying for speed the case does not value. |
| Quality correction — P11 | Margin, liability exposure, practical corrective action | Compare stronger protection with the minimum compliant quality guarantee and lower chargebacks | Never cross the defect limit. Payment may be fixed even when the supplier asks for cash relief. |
| Indexed/material pricing — P02/P08/P18 | Material exposure, existing purchase cover, price approval | Compare a fixed package and a permitted symmetric index package; negotiate base price separately | Price the material share, deadband, base month, expected path and index risk. Do not charge the same material movement twice. |

## 3. Build complete, comparable packages

Before opening the negotiation, load the case, supplier notes, contracts, quote standards,
cost estimates and relevant evidence. Separate fixed fields, negotiable menus and must-haves.

Calculate the full horizon cost for every candidate: purchases, uncovered demand and fallback
risk, payment financing, freight, lateness, quality, tooling, indexation and estimated relationship
cost. Compare that total with the available alternative. The published model is in
[cost.py](../starter-kit/arena_kit/cost.py) and [the scoring rules](../brief/api.md#cost-and-score).

Send at most three complete alternatives, each making a distinct trade:

| Package | Purpose |
|---|---|
| Target | Our preferred feasible combination at a defensible opening price. |
| Cash exchange, when allowed | Earlier payment for a corresponding price reduction; include the buyer's financing cost. |
| Case-specific exchange | Extra compliant production time, index protection, a useful longer commitment, or lower quality liability that may unlock a better price. |

Price alternatives to the **same full-cost budget as the primary bid**, rounding the unit price
down to cents. This makes the supplier's choice reveal its preferences without charging us more
for the exchange. A longer lead time can be worth testing even when it incurs a delay cost,
provided the corresponding price discount covers that cost and the delivery requirement still
holds. Include estimated relationship costs; a lower unit price can otherwise make a strategic
deal worse. Preserve prior prices for identical complete exchanges.

The [local exchange validation](package-exchange-validation.md) records this implementation and
its 0.834394 parameter-holdout mean at that revision.

The [subsequent competition policy](competitive-strategy-validation.md) promotes a supplier's
workable combination of terms, minimally repairs an infeasible opening, and converts prior
concessions by total cost when switching packages. This prevents a low price tied to early
payment from becoming an accidental lower bid on a different commercial basis.
It also anchors opening RFQ bids to compliant market cost and preserves the cheapest ready
offer while another bidder is challenged. The latest hosted P05 result is **0.458784** after
correcting a failed first attempt at 0.350283; a major hosted score improvement remains unproven.

For quality cases with fixed payment, use the three slots for quality/liability choices instead:
strong complaint recovery, a lower chargeback package, and a simpler package meeting the defect
limit with minimal chargebacks. Evaluate the residual defect cost in that last option.

**Worked example:** P11's baseline deal cost €787,686 under the arena model: €48.00 per unit,
300 ppm and €500 chargebacks. The simpler follow-up cost €766,618.50: €46.00, 1,500 ppm and no
chargebacks. It met the 1,500 ppm requirement and reduced modelled total cost by **€21,067.50**.
It provided less quality protection; the lower price outweighed the modelled residual defect cost.
This is an arena-specific comparison, not a general rule to weaken quality commitments.

When buyer costs tie, prefer terms that reduce supplier effort: adequate delivery time and useful
commitment. The arena ignores commitments beyond its horizon in its cost calculation; that
modelling assumption must not be mistaken for free commitments in real procurement.

## 4. Concede deliberately

Start from the case's economics and supplier context. Use should-cost information as an estimate,
with uncertainty, rather than claiming to know the supplier's private floor. Strategic cases must
also account for the relationship cost of an unsustainable deal.

The current implementation keeps the 22% upward price-gap step while the supplier has not
explicitly confirmed the non-price terms of a proposed package. Once those terms are confirmed,
the step is `1 / max(4, remaining_messages - 1)`, reserving a closing move. A reduction of more
than 0.5% in compliant full cost halves that step; resistance raises it to at least 20%:

```text
next price = previous price + step × max(0, supplier price − previous price)
```

These remain working heuristics. The broader local suite supports them, including a separate
parameter holdout. A later single hosted P05 follow-up scored 0.452; the broader hosted impact
has not been established.

With each concession, state the exchange: price for payment, duration for allocation, or reduced
liability for a lower price. Recompute the complete package. Do not describe a concession already
granted in the previous round as new. If a supplier repeatedly rejects the same argument, switch
to another permitted trade or seek approval from the relevant decision-maker.

The asking-price alternative hurt both renewal cases. Do not reintroduce it as a general shortcut
to agreement. A particular concession still needs to justify its total cost.

## 5. Use evidence to answer the current objection

Use one or two relevant facts per message. Read the reply before choosing the next argument.

- **Cost pressure:** cite a relevant, reproducible index movement with explicit dates. A recent
  decline does not disprove a rise over a different period.
- **Cash pressure:** present an actual permitted payment package. More market statistics will
  not necessarily resolve a financing problem.
- **Capacity pressure:** discuss the offered allocation and duration with production planning.
- **Quality concerns:** use the scorecard and corrective-action report, then obtain binding terms.
- **Approval limits:** ask finance, management or the pricing committee to approve the complete exchange.

Reserve source IDs when sending a message, so concurrent RFQ threads do not reuse the same
one-use evidence. Cite rival offers only when they are available and meet the relevant requirements.
Verified evidence establishes accuracy; it does not guarantee a concession.

Each email should acknowledge the latest objection, explain the package exchange, include the
selected evidence, and ask for a concrete decision. The model writes the response; code supplies
numeric claims and binding sheets. Neither prose nor a document should override the case's fixed terms.

## 6. Treat closing as part of the negotiation

1. Compare all eligible standing sheets using complete terms and supplier standards.
2. Reject any deal that fails a must-have. Accept only a feasible offer whose estimated total cost
   beats or matches the available alternative.
3. Respond to final offers with a closing decision. In RFQs, collect outstanding replies when time permits.
4. Keep the 30-second age guard for an actionable final offer. Extend it to 45 seconds only when a
   pending bidder's current, compliant standing quote has at least 1% lower estimated full cost.
   This leaves 15 seconds on the supplier reply clock to settle the ready offer. The extension
   is locally tested and was present in the single P05 follow-up; no complete hosted rehearsal
   has tested it yet.
5. On an expired or rejected offer ID, refresh the thread, exclude that ID and rerun the cost and
   feasibility checks. Do not blindly accept another sheet or repeatedly retry the same ID.
6. Begin wave closure with at least the configured 90-second reserve, or more if observed response
   latency requires it. Confirm the returned settlement result.

Keep model decisions bounded at ten seconds and download attachments concurrently. A model
timeout uses the computed strategy. Supplier response time is excluded from the published
60-second reply clock, but waiting on other threads and doing our own work still require careful scheduling.

Walking away is a valid outcome when the available alternative is better. A valid deal rate alone
is therefore insufficient; track correct decisions, total cost, scores and technical failures.

## 7. What we use now, and what we test next

| Priority | Action | Status |
|---|---|---|
| P0 | Complete sheets, total-cost valuation, must-have and alternative checks | Implemented; keep enabled. |
| P0 | Concurrent attachment reads, expiring-offer handling and rejected-ID recovery | Implemented with local regression tests; hosted follow-ups closed successfully. The newest run did not establish that every recovery path was exercised. |
| P1 | Preserve renewal and indexed-package approaches | Supported by the recorded runs; avoid unnecessary changes before a full validation. |
| P1 | Offer a simpler compliant quality package | Implemented; one targeted run improved to 0.536. Repeat before claiming a stable advantage. |
| P1 | Improve RFQ waiting based on offer age and the value of a pending bidder's standing quote | A bounded 45-second extension has local tests and was present in the P05 follow-up. Its individual timing and value effects are not isolated. |
| P2 | Close stalled negotiations when offers repeat and no valuable trade remains | **Next experiment.** P11 spent several rounds at the same price. This early-stop policy is not implemented. |
| P2 | Tune price anchors and concession sizes | Firmer openings and responsive concessions passed the local suite; one hosted P05 follow-up scored 0.452. Broader hosted impact remains unverified. |

## 8. Validation and live-final procedure

For the next experiment, prioritise P05, P11 and P18. Run the same cases on the reference and
candidate versions, repeat each at least three times if quota permits, and alternate version order.
Preserve every result, including errors. Compare mean score, worst result, must-have failures,
settlement errors, duration and model fallbacks. Promote a change only after a complete ten-case
run shows no material regression; repeated runs are needed because supplier replies vary.

Check quota before spending sessions. Use one immutable code revision per batch, record the
model configuration without keys, and retain the report's source fingerprint and replay links.
The practice leaderboard's best-ever scores are useful records, but they are not an estimate of
the reliability of one live-final attempt.

From `starter-kit`, with the existing environment configured:

```bash
.venv/bin/arena evaluate --cases case:P05 case:P11 case:P18 \
  --agent buyer-llm --data ../data --parallel 3 --out /tmp/targeted-strategy.json

.venv/bin/arena evaluate --agent buyer-llm --data ../data \
  --parallel 10 --seconds 480 --out /tmp/final-rehearsal.json
```

Before the live final, download the Sunday release, run a pre-flight through the actual machine
and provider, record the committed version, and start the unattended wave runner before the start.
It must use each wave's supplied deadline and the permitted case/session/attachment endpoints.
It must not read live leaderboard, results, screen or event feeds, or rely on human intervention.

```bash
.venv/bin/arena data --out ../data
.venv/bin/arena run --set final --agent buyer-llm --data ../data --parallel 10 -v
```

Our pitch should demonstrate one replay and its cost breakdown: what the supplier valued, what
we exchanged, why the agreement met the requirements, and why we closed. Use the recorded
results with their limitations; a first-place finish has not been established by these tests.
