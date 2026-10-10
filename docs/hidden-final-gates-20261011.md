# Hidden-final validation gates (11 October 2026)

The target is reliable performance on unseen suppliers under each wave's eight-minute cap.
Practice score is diagnostic, not the optimization target.

## Required sequence for a strategy edit

1. Run deterministic `buyer` on hosted sandbox `case:D01` and `case:D02`; save scores, rounds,
   end reasons and session IDs as the before baseline. Sandbox sessions consume no practice quota.
2. Make one general strategy change. Explain it using `arena_kit/cost.py` or a negotiation
   principle that applies across suppliers. Do not key behavior to a case ID, supplier ID,
   leaderboard entry or replay phrase.
3. Run `buyer` on D01 and D02 again. Reject the edit if either case worsens. Because suppliers
   may vary their responses, inspect the replay and cost breakdown before attributing a small
   score difference to the code.
4. Run `python scripts/smoke_practice_sim.py --cases .local/practice-cases.json --out <report>`
   from `starter-kit/`. This uses the local `arena-sim` implementation with the real 60-second
   clock and a 480-second deadline. It must pass all 19 practice case files, including the nine
   not hosted for practice: no exception, failed must-have, or timeout.
5. Run one bounded hosted ten-case batch with deterministic `buyer`, `--parallel 10` and
   `--seconds 480`; save the report. This consumes ten practice sessions. Use the results to
   check concurrent reliability and broad regressions, not to tune a single case.

`--fetch` on the smoke command refreshes the public practice case files without opening a
hosted session. The local simulator has one scripted supplier and validates API and cost
mechanics; its scores do not estimate hidden-supplier performance. Fast local execution also
does not recreate hosted reply delays. The hosted ten-case batch checks that timing separately.

## Rule audit

| Rule family | General basis | Limit |
|---|---|---|
| `cost.py`, `optimise`, `at_cost`, `close` | Price every complete term sheet over the case horizon; enforce must-haves and compare the alternative. | The supplier-health term uses an estimated full cost where available. |
| Multiple priced packages | A supplier can value payment, duration, quality risk, material indexing and capacity differently; price each exchange to the same buyer-cost budget. | The simulator does not model those preferences. |
| Opening discount and bounded concessions | Anchor below the quote, then concede toward a mutually acceptable package in response to actual counteroffers. | The 0.86/0.90 anchors, 0.22 step, and movement thresholds are heuristics, not deductions from the cost formula. Their transfer to hidden suppliers is uncertain. |
| Supplier signals and objections | React to current, broadly phrased cash, capacity, pricing, approval and confidentiality constraints; avoid repeating a refused request. | Text patterns are imperfect and must remain generic. |
| Evidence selection | Cite exact facts once, and only when relevant; compare a current compliant rival offer, not an old RFQ. | A verified fact may still fail to persuade a supplier. |
| RFQ scheduling and close guard | Keep each bidder's reply clock alive, solicit competition, and secure a feasible standing offer before it expires or the wave cap arrives. | The 30/45-second and 1%/3% thresholds are timing and challenge heuristics. |

Search of runtime buyer, strategy, commercial and exchange code found no branch on a practice
case ID or supplier ID, and no remaining phrase tied to one supplier's replay. **Case-only rules
flagged: none.** The heuristic constants above remain the main generalization risk.

## Results

- Baseline local smoke: 19/19 passed; all 19 ended with a compliant deal and zero timeouts.
  [Per-case report](hidden-final-local-smoke-20261011.json).
- Baseline hosted sandbox: D01 score 0.829, 7 rounds, zero timeouts, session
  `a0e10d32e5531330`; D02 score 0.428, 8 rounds, zero timeouts, session
  `6a3245ded0348881`. Both ended in accepted deals. These are the held-out
  reference results for any later strategy edit. No strategy edit was made in
  this validation pass, so there is no after-change sandbox comparison.
- Final ten-case hosted batch: 10/10 accepted deals, 10/10 compliant must-haves,
  zero thread timeouts, zero runner errors; slowest case P08 took 113.69 seconds,
  below the 480-second case deadline. Mean score was 0.681, used only as a broad
  diagnostic. 395 practice sessions remained at the end of this batch.
  [Per-case report](hidden-final-hosted-20261011.json).
