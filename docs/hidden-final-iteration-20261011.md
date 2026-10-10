# Hidden-final iteration, 11 October 2026

Work started from the pushed and tagged safe commit `a47ea0d`. Strategy changes
were committed separately so either can be reverted without losing the other.
No D02 replay was used to choose or tune a rule.

| Change | Commit | General basis | Held-out result |
|---|---|---|---|
| Recognize broad refusals to provide a cost breakdown in RFQs | `6648052` | Stop repeating a declined request; cite the current compliant rival `offer:` where available. Existing code already keeps bidder threads active and accepts the lowest feasible full-horizon cost. | D01 0.829 → 0.829; D02 0.449 → 0.449. |
| Hold buyer cost when the supplier does not improve its complete offer; make larger conditional or full steps after movement | `6576d0c` | Reciprocal concessions priced by the published total-cost formula, with fewer visible steps. | D01 0.829 → 0.905; D02 0.449 → 0.513. |

The first RFQ wording candidate was rejected after its paired D02 check fell
from 0.449 to 0.428. The first concession candidate failed a local contract
simulator benchmark because it held on incomplete supplier terms even after
price movement; it was refined and passed the full suite before commit.

## Rehearsal after both changes

`buyer`, ten hosted practice cases, `--parallel 10`, 480-second deadline.
All ten accepted compliant deals, with zero runner errors and zero thread
timeouts. Slowest was P05 at 256 seconds, below the case deadline. Mean was
**0.679**, versus the requested 0.654 reference (**+0.025**). It is slightly
below the earlier same-branch 0.681 batch. P05 scored 0.503 and P11 0.536,
so RFQ strength and the hold rule still have transfer risk. P02 0.707 and
P18 0.532 were unchanged in targeted runs. This batch is diagnostic for
hidden suppliers, not a performance guarantee.

The final rule passed 19/19 local practice files under the simulator's clock
and eight-minute deadline: no crashes, must-have breaks or timeouts. The
scripted simulator walked away on two cases; that signal is recorded as a
limitation. The full Python suite passed (125 passed, 1 skipped); Ruff clean.

[Per-case hosted batch](hidden-final-batch-after-changes-20261011.json) ·
[RFQ check](rfq-refusal-check-20261011.md) ·
[Concession check](concession-check-20261011.md)
