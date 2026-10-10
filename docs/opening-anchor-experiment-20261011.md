# Opening-anchor experiment (2026-10-11)

Base commit: `a6e1dcf`. Candidate changed first offers for non-stabilise goals to
0.78 times the quote (0.82 for `secure_supply`), or 1.04 times a comparable
should-cost estimate clamped to 0.72-0.90 times the quote. The RFQ rival-cost
anchor used the matching 0.78/0.82 factor. Stabilise remained unchanged.

The candidate passed 125 tests (1 skipped) and Ruff. Free hosted sandbox gates:

| Case | Required | Candidate | Result |
| --- | ---: | ---: | --- |
| D01 | 0.90 | 0.90543 | Pass |
| D02 | 0.51 | 0.30575 | Fail |

Rejected and fully reverted. No 10-case hosted batch was run because D02 failed
the required held-out gate. The repository strategy remains the `a6e1dcf` one.
The D02 replay was not used to tune the candidate.

Follow-up: repeated free sandbox runs showed that the single 0.30575 D02 score
was not representative. See [the repeat and Variant B results](anchor-repeat-check-20261011.md).
