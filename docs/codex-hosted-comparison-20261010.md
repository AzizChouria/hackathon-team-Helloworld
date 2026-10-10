# Hosted comparison after integration with `e41db33`

The agent source was `20f6410` for both batches. Each batch ran the ten hosted practice
cases once with a 480-second case deadline and four parallel sessions. The model batch
used `gpt-6.1-sol`; its tactical preflight passed in 3.12 seconds before opening a
session. Scores are single samples from hosted suppliers, not estimates of expected
performance. The leaderboard uses each case's best historical score.

| Case | Buyer score | Buyer rounds | Buyer-LLM score | LLM rounds | Model calls succeeded | Fallbacks |
|---|---:|---:|---:|---:|---:|---:|
| P01 | 0.862 | 4 | 0.710 | 6 | 5 | 0 |
| P02 | 0.507 | 6 | 0.295 | 6 | 5 | 0 |
| P03 | 0.923 | 6 | 0.919 | 6 | 5 | 0 |
| P04 | 0.860 | 4 | 0.860 | 4 | 3 | 0 |
| P05 | 0.510 | 12 | 0.452 | 13 | 11 | 0 |
| P07 | 0.650 | 5 | 0.689 | 5 | 4 | 0 |
| P08 | 0.471 | 6 | 0.493 | 6 | 5 | 0 |
| P10 | 0.663 | 3 | 0.663 | 3 | 2 | 0 |
| P11 | 0.620 | 8 | 0.620 | 8 | 7 | 0 |
| P18 | 0.473 | 5 | 0.473 | 5 | 4 | 0 |
| **Mean** | **0.654** | | **0.617** | | **51** | **0** |

The complete private reports are `/tmp/arena-main-buyer-20261010.json` and
`/tmp/arena-main-buyer-llm-20261010.json`. They include session IDs, replay links,
binding terms, cost breakdowns and private decision reasons. They are intentionally
excluded from Git because decision reasons and supplier correspondence may be private.

## Weak-case replay findings

- P02: the model's longer exchange ended at EUR 373.64 / 90 days; the rule buyer
  reached EUR 371.88 / 90 days. The supplier described material and labor cost
  pressure, but accepted a volume commitment and did consider payment alternatives.
  An indexed 90-day alternative was missing from the opening packages even though
  the case allows it.
- P05: a supplier offered EUR 31.00 with 14-day payment and 35-day lead time, close
  to the buyer's complete EUR 30.98 bid. Another round replaced that standing offer
  and the model batch closed at EUR 31.50. A bounded RFQ close guard can preserve a
  near-matched complete offer.
- P18: the supplier repeatedly required an index clause for the long contract. Both
  batches closed EUR 5.40 with 14-day payment and indexation. A 90-day indexed
  alternative lets the supplier keep material protection without forcing early cash.

The revisions use only current case terms, public cost arithmetic, and live supplier
messages. They contain no practice case IDs or supplier-specific answers at runtime.

## Targeted replay-derived rerun

At `ea70aa5`, the buyer added a bounded longer-payment indexed route and a guard that
closes an RFQ offer when it has essentially matched a complete buyer bid. The local
regressions and full suite passed before the three-case retests.

| Case | Original buyer | Revised buyer | Original LLM | Revised LLM | Revised LLM calls |
|---|---:|---:|---:|---:|---:|
| P02 | 0.507 / 6 rounds | **0.707 / 2** | 0.295 / 6 | **0.707 / 2** | 1 success, 0 fallback |
| P05 | 0.510 / 12 | 0.510 / 13 | 0.452 / 13 | 0.459 / 11 | 8 success, 0 fallback |
| P18 | 0.473 / 5 | **0.532 / 5** | 0.473 / 5 | **0.532 / 5** | 4 success, 0 fallback |

Both revised P02 sessions accepted EUR 363.54 at 90-day payment with a 5% deadband
index clause, exactly the previously missing package type. Both revised P18 sessions
accepted EUR 5.40 at 90-day payment with indexation, rather than 14-day payment.
P05 still had three buyer timeouts in the revised LLM replay, despite 8/8 model calls
returning successfully.

At `b2bc4cf`, the RFQ runner began making supplier replies available before their later
attachments finish downloading, and the buyer prioritized reply clocks nearing 60 seconds.
One further P05 model session scored **0.522 in 8 rounds**, with **7 successes, 0 fallbacks,
and 0 buyer timeouts**. It accepted EUR 30.89 at 14-day payment, 35-day delivery, and
600 ppm. This is a single hosted sample; the team's older P05 best remains 0.543.

After these runs the team's best-per-case practice total was 71.7 and rank 14. P02 set a
new team best at 0.707. The team best for P18 remains 0.546 from an earlier run.
