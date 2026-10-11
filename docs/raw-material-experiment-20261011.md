# Raw-material index experiment — rejected, 2026-10-11

## Scope and decision

Base: `abfb9f6`, incorporating the teammate changes through `04d25f7`.
Candidate: `c7b7ec7`, developed only in `/home/chouria/wt-codex` on
`exp-raw-material`. The experiment completed before the 11:05 Europe/Berlin
deadline. **Reject and revert:** neither target cleared its reference score.
The experiment was not merged or pushed to the final branch.

The preceding final-launch task was already committed as `d75cde7`. The requested
`git pull --no-rebase` reported up to date; its suite passed 138 tests with one
skipped, and the final-branch push reported up to date before experiment work.

## Hypothesis and implementation

The latest completed P18 and P08 replays showed that both suppliers opened with
fixed prices, but our opening alternatives volunteered an index clause. Final
index cost plus risk was EUR 2,303.64 for P18 and EUR 9,282.82 for P08.

The single candidate rule preserved a fixed raw-material quote's risk allocation:
when the optimizer selected a feasible fixed-price package and no current
supplier sheet contained an index, it did not add a clause that increased public
total cost at the same price. Fixed early/late payment trades remained available.
If the supplier subsequently proposed an index, normal risk-priced alternatives
became available again. Beneficial index clauses remained eligible throughout.

This was a general negotiation hypothesis based on the published cost formula.
It used no case or supplier IDs, copied supplier wording, replay data, private
supplier reasons, or `c_best` at runtime. Acceptance and must-have checks were
unchanged. Four new generic regression checks covered fixed payment trades,
supplier-proposed primary/alternative indexed quotes, and favorable index paths.

## Hosted gate

Agent: deterministic `buyer`, no LLM. Data: the same published base package and
Sunday release as the final runner. Exactly four hosted practice sessions and
one free sandbox session were used. The runner allowed at most four concurrent
sessions, checked team capacity before opening, and set an eight-minute cap per
case. All five ended with accepted, compliant deals; no runner errors occurred.

| Case | Reference | Run 1 | Run 2 | Candidate mean | Delta |
|---|---:|---:|---:|---:|---:|
| P18 | 0.532473 | 0.453061 | 0.453061 | 0.453061 | -0.079412 |
| P08 | 0.581261 | 0.548790 | 0.581887 | 0.565338 | -0.015923 |
| D01 | 0.905431 | 0.905431 | — | 0.905431 | 0.000000 |

The reference replays were P18 `87e7bff15db90699` and P08 `e2b4af4be7469e0a`.
Their immediately preceding runs were P18 `ad8d7473e6bd2513` (0.532473) and
P08 `e9483d6f87f6e663` (0.537966). We conservatively used the stronger, latest
P08 result as the gate reference. These were existing runs; there was no fresh
contemporaneous control batch. P18 fails even against its two-run reference mean.

| Case / repeat | Session | Rounds | Seconds |
|---|---|---:|---:|
| P18 / 1 | `0d42417e11932885` | 4 | 79.57 |
| P18 / 2 | `bb1f654def064edb` | 4 | 91.29 |
| P08 / 1 | `1964c412d12e7e51` | 4 | 82.24 |
| P08 / 2 | `26326bddb56eba58` | 4 | 98.40 |
| D01 / 1 | `b6380c3c85caa059` | 7 | 11.05 |

## What the replays establish

Both P18 repeats still closed at EUR 5.40 with 90-day payment, but the supplier
introduced an index clause with a 0% deadband. The baseline's 5% deadband had
limited index movement. The new clause raised index cost from EUR 1,151.82 to
EUR 6,910.92, adding EUR 5,759.10 without a price reduction. Omitting our clause
did not secure a fixed-price agreement.

P08 varied: one run closed at EUR 5.47 with a 5% deadband; the other at EUR 5.32
with a 0% deadband. The cheaper headline price in the second run was largely
offset by extra index exposure. Its average did not beat the chosen reference.

This rejects the tested policy of withholding an index until the supplier asks.
It does not establish that fixed-price negotiation can never work. The evidence
supports retaining the existing protected clause proposal and evaluating every
complete standing offer on total cost.

Candidate checks: **142 passed, 1 skipped; Ruff clean.** After the failed hosted
gate, the candidate code and its tests were reverted. The experiment branch's
source and tests match `abfb9f6`; only this report and its JSON evidence remain
as differences. The final branch received no experiment changes.

Machine-readable scores and cost breakdowns:
[raw-material-experiment-20261011.json](raw-material-experiment-20261011.json).
