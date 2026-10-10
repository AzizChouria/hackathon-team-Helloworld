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
