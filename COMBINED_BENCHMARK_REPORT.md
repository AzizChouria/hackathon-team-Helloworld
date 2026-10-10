# Combined agent: ten-case hosted practice benchmark

Runtime commit: `844cb8066008736558c6f845dc27c5a7b19b756a`. Batch: `combined_01`.

One newly authorized session per hosted case. Deterministic combined agent; LLM advisor disabled.
No model substitution, OpenAI calls, additional API spend, automatic session recreation, or live-final execution.

**Mean: 0.626295; median: 0.676381; range: 0.000000-0.922833; population standard deviation: 0.254167.**

Completed 10/10; valid deals 9/10; timeouts verified from completed replay traces: 1.

## Official leaderboard

| Snapshot (UTC) | Team rank | Team score / 100 | Leader / 100 | Gap | Quota used / left |
|---|---:|---:|---:|---:|---|
| 2026-10-10T22:45:26.708913+00:00 | 14 | 71.7 | 87.7 | 16.0 | 220 / 380 |
| 2026-10-10T23:01:36.885125+00:00 | 14 | 71.7 | 88.0 | 16.3 | 230 / 370 |

Team: Helllo World. Ten contributing cases. Leaderboard scores aggregate each case's best run; they are not the mean of this batch. Rank and leader scores can change independently during the benchmark.

New case bests relative to the starting snapshot: none.

## Individual hosted results

| Case | Score | Teammate score | Deal cost EUR | Rounds | Wall seconds | Replay |
|---|---:|---:|---:|---:|---:|---|
| case:P01 | 0.853391 | 0.870550 | 1105167.21 | 4 | 90.8 | [replay](https://arena.tacto.ai/replay/92211f266420577b) |
| case:P02 | 0.707348 | 0.318973 | 2249372.15 | 2 | 26.8 | [replay](https://arena.tacto.ai/replay/44bef23e1438cbfc) |
| case:P03 | 0.922833 | 0.922833 | 3935069.22 | 6 | 159.6 | [replay](https://arena.tacto.ai/replay/ea71292195593852) |
| case:P04 | 0.860445 | 0.860445 | 196852.67 | 4 | 67.4 | [replay](https://arena.tacto.ai/replay/ba2182cd3c7e66d6) |
| case:P05 | 0.451910 | 0.458784 | 268433.76 | 12 | 280.1 | [replay](https://arena.tacto.ai/replay/8d4990ed54ca9663) |
| case:P07 | 0.682050 | 0.662570 | 328424.8 | 5 | 87.3 | [replay](https://arena.tacto.ai/replay/8c73d0dca42a878b) |
| case:P08 | 0.494670 | 0.416011 | 1049034.05 | 6 | 132.8 | [replay](https://arena.tacto.ai/replay/482b0ecfe6edc1a4) |
| case:P10 | 0.670711 | 0.670711 | 1527674.4 | 3 | 43.7 | [replay](https://arena.tacto.ai/replay/eb70c70438d0850c) |
| case:P11 | 0.619591 | 0.619591 | 758668.5 | 8 | 205.2 | [replay](https://arena.tacto.ai/replay/a084a36616767f20) |
| case:P18 | 0.000000 | 0.472865 | - | 5 | 108.0 | [replay](https://arena.tacto.ai/replay/35552bdc658fc43a) |

Against the user-supplied teammate batch (0.627333), the mean difference is -0.001038: 3 higher, 4 tied, 3 lower case scores.

That reference batch's configured model returned 43 HTTP 404 errors: it measured deterministic fallback, not successful Astra calls. These are different runs and runtime policies, not a controlled causal model comparison.

## Reliability and measurement

Claim checks from the replays: `{'verified': 36, 'duplicate': 3}`. Network retries configured: zero. Three attachment ReadTimeout warnings were observed; negotiations continued, but their effect was not isolated. No model fallback was needed because no model was enabled.

Action/closing validation computation averaged 0.0800 s, maximum 0.3910 s. These include repeated closing validations; raw coordinator invocation averages also include no-action polling. Neither measures supplier generation time or exact arrival-to-send latency. Whole-case times appear separately above.

OpenAI input/output/reasoning tokens: 0/0/0. Batch API spend: $0. The prior shared accounting balance remains $1.53832, including unresolved earlier timeout reservations; it is not a verified invoice total.

## Observed weaknesses

- P18: no deal, score zero. The agent diagnostics record an acceptance attempt followed by recovery and walk-away, despite a final supplier quote in the replay. The exact rejected HTTP response was handled internally and not recorded, so its status/cause cannot be proved from this log. Source inspection found that RemoteTable.missed reconstructs terms only from timeout records: with no timeout record it replaces a real current quote with empty terms. This recovery defect was reproduced and corrected offline after the benchmark, as described below.

- P05: one timeout on the Hrvelec thread. A post-run read of Fuchsreiter's final actionable alternative found EUR 31.00, 14-day payment and 35-day lead time, with a verified 600 ppm standard. It passed validation and cost EUR 263,626.35, versus the awarded Dralveck package at EUR 268,433.76: EUR 4,807.41 more. The remaining uncertainty is when this alternative became available to the client relative to the closing decision. Audit pending responses, server processing queues and offer freshness before treating it as a purely mathematical ranking defect.

- P08: the supplier explicitly refused detailed cost breakdowns, yet the fixed cost tactic continued asking for them. The agent did move to an indexed/90-day-payment package, but objection handling needs to stop repeating declined requests and negotiate a concrete permissible exchange.

- P03/P04: repeated supplier prices preceded final offers. These runs matched existing scores, but several extra rounds produced no observed price movement. Any earlier-close policy needs tests for non-price concessions and standing-offer withdrawal risk.

These observations are offline diagnostics only. They were not supplied to the running agent, and no case-specific policy changes or retests were made during the pass.

## Limits and follow-up

This is one observation per hosted case. It does not establish robustness on unseen suppliers. The earlier local mean of 0.83633 described scripted opponents and must not be substituted for this hosted mean.

P06, P09, P12-P17 and P19 remain data-only, covered by offline economic fixtures only. No online scores are invented for them. All participating supplier threads in hosted RFQs are handled within their case session; the official score belongs to the final case outcome.

Runtime source and data stayed frozen for the pass. After seven completions, the runner paused on a P05 RFQ timeout. A reviewed continuation completed only the three unopened single-supplier cases sequentially, within the same authorization. Do not repeat this batch: its ten-session journal is exhausted. Any additional online experiments need separate authorization.

Evidence: `benchmarks/combined_01/hosted_results.jsonl`, `summary.json`, `analysis.json`, `replay_analysis.json`, and timestamped leaderboard snapshots. Raw replay transcripts remain private and are not committed or passed into the negotiation agent.

Validation before execution: existing combined implementation 262 passed / 1 skipped; new benchmark gates plus combined regressions 27 passed; Ruff passed.


## Post-benchmark offline correction

A recovery regression was reproduced with a fake API: rejecting a cheaper alternative
while a valid primary quote remains caused the old code to walk away. Two regression
tests failed before the correction. The runner now retrieves the message matching the
server's current offer ID, preserves its verified sheets, and lets the coordinator exclude
the explicitly rejected sheet before comparing the remaining offers. Matching timeout
replacements take precedence; unmatched historical quotes are never revived. No ambiguous
POST is blindly replayed. Rejection status is now logged without raw response content.

This is a general recovery correction, not a practice-case price rule. It was implemented
only after all ten hosted runs. The benchmark runtime remains commit `844cb8066008736558c6f845dc27c5a7b19b756a`;
the correction has no new hosted score. The RFQ timing/offer-collection issue and repeated
objection handling remain unresolved and should be addressed before claiming final readiness.

Post-correction validation: **271 tests passed, 1 skipped; Ruff passed**. No hosted retest.

Offline recovery-fix commit: `5a12534`. This commit was not retested against hosted suppliers.
