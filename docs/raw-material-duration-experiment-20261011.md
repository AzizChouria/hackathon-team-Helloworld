# Raw-material duration experiment — rejected, 2026-10-11

Candidate `e46dfbd`, on `exp-raw-material` in `/home/chouria/wt-codex`.
The starting source was the restored `abfb9f6` baseline after the first rejected
index experiment. The hosted gate completed around 11:00 Europe/Berlin, before
the 11:05 deadline. **Rejected and reverted in `e8642e8`.**

## Hypothesis

The first experiment's supplier replies explicitly refused fixed prices over
36 months. Both public case menus permit 12, 24 and 36 months, while the buyer's
horizon is two years. The published cost formula gives no extra coverage value
to the third year. A general trade was therefore worth testing: fixed price for
the shortest complete buying horizon, alongside the existing longer indexed
alternatives with their protected deadband.

At equal total cost, the candidate selected the shortest full-horizon fixed
raw-material contract, retained that fixed package as the lead, and explicitly
described its fixed price and lack of index adjustment. Existing indexed
alternatives, anchors, concession steps and closing comparisons remained.
Mandatory longer contracts and beneficial indexed terms remained eligible.

No supplier/case IDs, copied supplier wording, replay data, hidden supplier
parameters or `c_best` were used in runtime decisions. The change was grounded
in the buyer's published horizon, allowed terms, must-haves and cost formula.

## Validation

Full suite: **142 passed, 1 skipped**. Ruff passed. Generic tests covered fixed
24-month versus indexed 36-month offers, a must-have requiring 36 months,
beneficial index paths, and agreement between the lead sheet and its prose.

Hosted agent: `buyer`, no model calls. Published base data and Sunday release.
Exactly **four practice sessions plus one free D01**. Four workers, with a team
capacity check before opening; the runner initially waited for the concurrent
team sessions to finish. All five deals were accepted and compliant. There were
no runner errors or forced closes at the cap. Elapsed times below include any
wait for capacity. The eight-minute per-case cap was also bounded by the
experiment's deadline.

| Case | Reference | Run 1 | Run 2 | Mean | Delta |
|---|---:|---:|---:|---:|---:|
| P18 | 0.532473 | 0.466961 | 0.532473 | 0.499717 | -0.032756 |
| P08 | 0.581261 | 0.527142 | 0.581261 | 0.554201 | -0.027060 |
| D01 | 0.905431 | 0.905431 | — | 0.905431 | 0.000000 |

References are the same existing replays used for the first experiment:
P18 `87e7bff15db90699` and P08 `e2b4af4be7469e0a`. No new control batch was
opened. The P18 mean also fails against both immediately preceding reference
runs, which each scored 0.532473.

| Case / repeat | Session | Rounds | Elapsed seconds |
|---|---|---:|---:|
| P18 / 1 | `305abdc063920b88` | 5 | 117.75 |
| P18 / 2 | `eb89875cb409150f` | 5 | 132.43 |
| P08 / 1 | `4fedafe10d2cccdb` | 6 | 164.38 |
| P08 / 2 | `fce4842ec66f6d2a` | 6 | 177.59 |
| D01 / 1 | `26533dfb9341acab` | 7 | 6.00 |

## Result and limits

Neither supplier selected the proposed shorter fixed-price package. P18
explicitly refused fixed pricing even for 24 months and continued with the
indexed 36-month alternative. Its two final prices were EUR 5.50 and EUR 5.40,
with 90-day payment and the protected 5% deadband. P08 also stayed indexed for
36 months, finishing at EUR 5.49 and EUR 5.44 on the same payment/deadband terms.

The candidate did not improve either target's mean, so it was reverted. D01
was unchanged, but that cannot compensate for the failed target gate. This is
evidence against the tested duration/presentation policy, not proof that every
possible raw-material strategy is exhausted.

Both tested candidates are now reverted. Source and tests match `abfb9f6`;
the experiment branch adds the two experiment reports and their JSON evidence.
No experiment change was pushed to the final branch.

[Machine-readable results](raw-material-duration-experiment-20261011.json).
