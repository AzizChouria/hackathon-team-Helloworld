# Replay findings - deterministic batch 23:22 vs earlier best (Sat 2026-10-10)

Source: `GET /v1/sessions/{sid}` traces (supplier reasons in words) for the weakest cases.
Sessions: P02 `62a9a97d32ae5c8f` (buyer 0.507) / `3957b6812d798a11` (buyer-llm 0.295);
P08 `ba3d14d67ec0e3e3` (best 0.679) / `9ba607369125a1e1` (latest 0.471); P18 `aa8f9eb0d410327b` (0.473).
All patterns below repeat across cases - they are general, not case-specific.

## 1. Penny concessions get punished (P02, P18, P08) - biggest issue

Our price path rises by a few cents every round (P18: 5.13 -> 5.14 -> 5.17; P02: 366.74 -> 370.85
-> 371.07). The suppliers say it outright and then send `final_offer`:

- P18 r3: "As your target price has only been adjusted by a marginal amount, we cannot justify further concessions."
- P18 r4: "the minor adjustment in your target price does not allow for further concessions" -> final_offer
- P02 r5: "the minor adjustments do not provide sufficient grounds for further price revisions" -> final_offer

The bots reciprocate the **size** of our move. Tiny steps burn rounds AND stop the supplier.
Fix: fewer, meaningful moves (e.g. 2-3 visible steps planned across the round budget), hold
position when the supplier did not move, never step by a rounding amount. Remember the final has
an 8-minute cap (~5 rounds), so a slow cent-by-cent ladder never reaches the end anyway.

## 2. Package order decides the deal - and we lead with value-destroying early payment (P08, P18)

The supplier adopts whichever package we put first and builds its counter on it.

- P08 best run (0.679) led with **90 days** -> deal 5.35 @ 90d, payment_terms **-6,762 EUR**.
- P08 latest (0.471) led with **14 days** -> supplier "adopted" 14 days, deal 5.45 @ 14d,
  payment_terms **+10,563 EUR**. ~17k swing from payment terms alone, AND a higher price.
- P18 (0.473): same - lead package 14 days + index clause, supplier locked onto it, paid +2,616.

Early payment costs us `interest_rate x days / 360` (8%: 76 days ~ 1.7% of spend). Only lead with
an early-payment package when its price discount clearly exceeds that, and the supplier has a
cash signal. Otherwise lead with reference/long payment terms; offer early payment as the 2nd/3rd
sheet so it is a probe, not the anchor.

## 3. Repeating the same boilerplate every round (all cases)

P08 latest: "We can commit to the longer framework in the term sheets..." in all 5 rounds.
P02/P18: "Please submit these complete packages to your pricing committee..." 4x.
The approval request worked once (P02 r3: "We have submitted your request to our pricing
committee ... substantial concession"), then stopped working. Each tactic should be used once,
then change argument. Track tactics already used per thread.

## 4. Suppliers ask for data and we don't send any

"Which figures is that based on? Please send us the data." appears in P02 r2, P08 r3, P18 r3.
After round 1 our messages carry no new citation. When asked, answer with an unused verified
fact (forecast/volume, scorecard OTD/PPM, a rival quote, an index that is NOT hedged).

## 5. The LLM concedes the supplier's argument (P02: llm 0.295 vs rules 0.507)

The model's prose: "We recognise the copper and labour pressures cited in your offer" /
"We understand that material and labour cost pressures limit your flexibility". The supplier
then leans on it: "the significant increases in copper and labor costs limit our flexibility".
Prompt fix: never validate the supplier's cost drivers; acknowledge politely but counter with
data or move to a trade.

## 6. Hedged index -> index decline argument fails, and the index clause costs us (P08, P18)

"That is not our reality: our AS-14404 is covered at fixed prices until March" - the falling-index
argument is rejected. We then accept the supplier's AS-14404 index clause, which adds
index_clause + index_risk (~9k EUR in P08, ~2.3k in P18). If the supplier is hedged, the material
cost is fixed for them: push for a fixed price (no clause) or a larger deadband / smaller
material share, instead of accepting their clause.

## Suggested order of fixes

1. Lead-package selection (#2) - pure cost math, big EUR effect, easy to test.
2. Concession schedule (#1) - fewer, larger, reciprocal steps.
3. Tactic rotation + answering data requests (#3, #4).
4. LLM prompt: no validation of supplier cost claims (#5).
Re-run only P02, P08, P18 (and P05) after each change; compare against this batch.
