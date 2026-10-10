# P05 RFQ close audit (2026-10-11)

Read-only review of completed hosted session `536c41a58688e195` from the
`a6e1dcf` buyer code. Totals below use the published `total_cost` formula,
the P05 case, and the quote PDF standard terms.

| Supplier / sheet | Price | Payment | Lead | Compliant | Total cost |
| --- | ---: | ---: | ---: | --- | ---: |
| `sup:70250`, `offer:70250-3-a` | EUR 31.00 | 14 days | 35 days | Yes | EUR 263,626.35 |
| `sup:70210`, accepted `offer:70210-3` | EUR 31.01 | 14 days | 35 days | Yes | EUR 264,275.69 |
| `sup:70250`, current `offer:70250-3` | EUR 31.50 | 30 days | 35 days | Yes | EUR 266,928.48 |

The buyer decision trace selected the cheaper `sup:70250` alternative first,
then selected `sup:70210`. The server's final thread state lists
`offer:70250-3` as the current offer ID. The intervening rejected acceptance
is inferred from the two close decisions and the runner's recovery path; the
session replay does not record the rejected request itself. The buyer did not
skip the cheaper sheet during cost comparison. Once that alternative could no
longer be accepted, the `sup:70210` deal was cheaper than `sup:70250`'s
current primary sheet.

The general risk is offer recovery after a rejected acceptance. Commit
`39ecc1a` makes recovery use the server's current offer ID and matching terms.
The RFQ regression in `tests/test_offer_recovery.py` verifies that a cheaper
alternative is attempted and a valid rival is selected after its rejection.
No P05-specific strategy rule was added. Hamza's reported EUR 268,434 deal
refers to a different run; this audit uses the session ID above.
