# Gap analysis - where the remaining score is (Sun 2026-10-11, ~01:00)

Source: latest hosted batch on a6e1dcf (`GET /v1/sessions/{sid}` results + back office), practice
case files. Offline study only - nothing here is read by the agent at runtime.

## Finding: our opening bid is already above the best achievable price

`best ~` = deal price minus (c_deal - c_best) / committed units - an approximation, since c_best may
use other terms. Opening bid = our first unit_price in the case.

| Case | Type / goal | Quote | Our opening bid | Best ~ | Best/quote | Opening vs best |
|---|---|---|---|---|---|---|
| P01 | price_increase / stabilise | 138.55 | 135.78 | 134.67 | 0.97 | +0.8% |
| P02 | price_increase / stabilise | 370.96 | 362.33 | 361.27 | 0.97 | +0.3% |
| P03 | renewal / stabilise | 438.21 | 429.45 | 429.31 | 0.98 | 0.0% |
| P05 | rfq / leverage | 36.00 | (mixed bidders) | 26.15 | **0.73** | above |
| P08 | raw_material / leverage | 6.05 | 5.20 | 5.05 | **0.84** | +2.9% |
| P10 | capacity / secure_supply | 32.20 | 28.98 | 27.35 | **0.85** | +5.9% |
| P18 | raw_material / leverage | 6.10 | 5.25 | 4.68 | **0.77** | +12.1% |
| P04, P07, P11 | routine / quality | | | | 0.88-0.99 | opening below best - fine |

The anchor is hard-coded in `agents/buyer.py` (`packages()`):
`anchor = theirs * (0.90 if strategic else 0.86)` and `0.90` for `secure_supply`.
For stabilise cases the should-cost margin floor raises it (correct: relationship penalty).

When the opening bid is above the supplier's acceptable floor, no concession schedule can reach
c_best - and suppliers answer `agreed` quickly (P01 r3, P02 r2, P05 sup:70210 r3 "My call: accept").
**A fast `agreed` is a signal that we bid too high.**

## Experiments (in order; each gated on held-out D01 >= 0.90 and D02 >= 0.51, plus a 10-case batch)

1. **Lower opening anchor for non-strategic goals** (leverage, routine, secure_supply, quality_first):
   start around 0.78 x quote instead of 0.86 (0.82 instead of 0.90 for secure_supply).
   Better, principled version: if a `should_cost` row exists for the part, anchor near
   `should_cost x (1 + small margin)`, clamped to [0.72, 0.90] x quote (should-cost error 5-15%,
   country factors in `data/company.md`). Keep the stabilise logic unchanged.
2. **Don't take a fast `agreed` at face value** when the deal is still far from our estimated
   floor and rounds remain: it is fine to accept (score is fine), but log it - if it happens often
   in a case type, the anchor for that type is still too high. (Do NOT counter an `agreed` offer;
   accepting is the safe close.)
3. **P05 RFQ:** c_best is ~26.15 but we accepted sup:70210 at 31.01. Check whether sup:70240's
   final offer (bid path 26.6 -> 29.6) was cheaper in total cost or excluded by the lead-time
   must-have (<= 42 days). If excluded, offer it a compliant lead time early instead of only price.

## Other cost items left on the table (smaller)

- P10: `late_delivery` EUR 33,600 (lead 56 vs need 42 at EUR 2,400/day) - lead_time is negotiable [35, 42, 56].
- P11: `quality` EUR 10,732 (ppm 1500 = the must-have limit, chargeback 0) - ppm/chargeback are the levers.
- P02: `relationship` EUR 23,990 + `index_risk` EUR 17,770 on the 90-day indexed package.
- P01: `payment_terms` EUR 10,989 (14 days) - fixed FCA freight, so payment is the only non-price lever.
