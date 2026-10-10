# RFQ refusal check, 11 October 2026

P05's replay showed repeated requests for a cost breakdown after a bidder had
declined to provide one. The buyer already cites current, compliant rival
`offer:` IDs to other bidders, keeps their threads active, and awards the lowest
feasible total-cost standing sheet. This change broadens the general refusal
detector so the buyer changes its request instead of repeating it. It does not
match a supplier name, case ID, or exact replay sentence.

| Check | Before | After |
|---|---:|---:|
| D01 held-out | 0.829 | 0.829 |
| D02 held-out | 0.449 | 0.449 |
| P05 targeted practice | 0.510 | 0.518 |

The first combined wording and detector candidate was rejected: its paired D02
result fell from 0.449 to 0.428. The narrower detector change above passed the
held-out checks. All 19 local `arena-sim` practice cases passed without crashes,
must-have breaks or timeouts. The full suite passed (124 passed, 1 skipped).
The practice score difference is small and is not evidence of hidden-final gain.
[Targeted run details](rfq-refusal-p05-20261011.json).
