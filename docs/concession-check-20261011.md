# Reciprocal concession check, 11 October 2026

The previous rule raised our bid on nearly every turn and sometimes made only a
cent-scale move. The new rule measures the supplier's last two compliant standing
packages using full-horizon cost. It holds the buyer-cost budget when the supplier
has not improved it by at least 0.1%, makes a conditional quarter-gap step for an
incomplete but improved quote, and makes a larger step for a confirmed complete
exchange. This is a general reciprocity rule, not a supplier-wording rule.

| Check | Before this change | Refined rule |
|---|---:|---:|
| D01 held-out | 0.829 | 0.905 |
| D02 held-out | 0.449 | 0.513 |
| P02 targeted | 0.707 | 0.707 |
| P18 targeted | 0.532 | 0.532 |

The first candidate held too firmly on incomplete quotes and failed the local
S03 benchmark test; it was refined before this commit. The final rule passes
that test and the full suite (125 passed, 1 skipped). All 19 practice case files
completed in `arena-sim` with zero crashes, must-have breaks or timeouts. The
scripted simulator walked away on two cases, including P11; this is a risk to
watch in the ten-case hosted batch, not a hidden-supplier score estimate.

[Refined targeted report](concession-refined-p02-p18-20261011.json).
