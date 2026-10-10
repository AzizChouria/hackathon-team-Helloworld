# Revised hosted benchmark: stopped after seven sessions

Report generated 2026-10-10T21:14:33.560975+00:00. Tested commit: `d4fc5935484d67cbbb62821c4a2a33f717457c7e`.

## Outcome

The revised agent did **not** beat the supplied teammate results. Seven sessions were started, six completed autonomously, and P11 was manually recovered as a valid zero-score deal after an API failure. Three cases were not started. No complete ten-case mean exists.

Including recovery, our seven-case mean is **0.365154**, versus **0.546784** for the teammate on those same seven cases. We won one case (P08), lost six. The six clean completions alone average 0.426014; omitting the failure would bias the performance assessment.

Even three remaining perfect scores would produce at most **0.555608**, below the teammate's full-batch **0.627333**. No further sessions were spent after the safety stop. The teammate's configured model returned 43 HTTP 404 errors, so their supplied scores measure fallback behavior; this batch's ten model calls all returned the configured Astra model successfully.

## Per-case results

All attempted cases used `gpt-6-astra`, `high`, Responses, sequential case execution.

| Case | Status | Our score | Teammate | Difference | Deal cost EUR | Replay |
|---|---|---:|---:|---:|---:|---|
| P01 | automated completion | 0.543795 | 0.870550 | -0.326755 | 1,122,803.04 | [Replay](https://arena.tacto.ai/replay/ee51de5e98fc70fc) |
| P02 | automated completion | 0.304102 | 0.318973 | -0.014871 | 2,268,467.21 | [Replay](https://arena.tacto.ai/replay/554c1051cf9c6aea) |
| P03 | Not started: safety stop | ? | 0.922833 | ? | ? | ? |
| P04 | Not started: safety stop | ? | 0.860445 | ? | ? | ? |
| P05 | automated completion | 0.358909 | 0.458784 | -0.099874 | 276,071.04 | [Replay](https://arena.tacto.ai/replay/82c8e005d6d266cb) |
| P07 | Not started: safety stop | ? | 0.662570 | ? | ? | ? |
| P08 | automated completion | 0.484863 | 0.416011 | +0.068852 | 1,050,756.04 | [Replay](https://arena.tacto.ai/replay/fbaded89f7877936) |
| P10 | automated completion | 0.539045 | 0.670711 | -0.131666 | 1,607,143.20 | [Replay](https://arena.tacto.ai/replay/1909208439523c5e) |
| P11 | manual recovery; runner failed | 0.000000 | 0.619591 | -0.619591 | 819,486.00 | [Replay](https://arena.tacto.ai/replay/01197ce70f36548e) |
| P18 | automated completion | 0.325367 | 0.472865 | -0.147498 | 271,576.98 | [Replay](https://arena.tacto.ai/replay/be99eb9cc81f5a18) |

The machine-readable `analysis.json` contains all seven opening/deal/best costs and cost components. Hidden post-run best costs are used only in this report, never by the negotiation agent. No data-only case was presented as hosted.

## Failure and recovery audit

P11 failed after its first negotiation message. The server had recorded the buyer message and supplier reply; the runner recorded only `ArenaError`, without HTTP status or operation. It is therefore unknown whether the original error came from the negotiation POST response or a subsequent attachment GET. Later read-only tests returned HTTP 200 for both P11 attachments; a persistent missing document was not reproduced. Do not claim a confirmed attachment root cause.

The original failed row and session journal were preserved. During investigation, two buyer timeouts advanced the standing quote. The first manual recovery attempted an older alternative from message history and received HTTP 422. Reading the current timeout quote allowed a second, distinct acceptance to close the same session at EUR 819,486, with must-haves satisfied and score zero. No session was recreated and no ambiguous POST was blindly retried. Manual recovery used no model call.

The raw runner originally reported zero timeouts because its captured state preceded those recovery delays; `recovery_outcome.json` and `analysis.json` explicitly add the two subsequently verified thread timeouts. The ordinary `summary.json` is the original stopped-run snapshot, with only six completed scores; use this report and `analysis.json` for the recovery-adjusted seven-case assessment.

## Performance and spend

Seven attempted outcomes: median 0.358909, range 0.000000?0.543795, population standard deviation 0.175323. Autonomous completion: 6/7 (85.7%). After manual recovery: 7/7 valid deals. This is not a 100% autonomous completion rate.

Ten model calls: mean 10.623 s, median 10.156 s, maximum 15.563 s. Input tokens 13,860; output tokens 4,376, including 3,896 reasoning tokens. No model failures or retries. 5 decisions deliberately used the deterministic policy; these are not API failures.

Estimated batch cost **$0.35740**, cumulative development estimate **$0.91802**. Rates are the previously verified configured $10/M input and $50/M output, without cache discounts; billing is not invoice-reconciled. No new paid calls were used for diagnosis or local fixes. Model latency excludes supplier/network time and manual recovery.

Claim-result counts excluding acceptance confirmations: `{"verified": 8}`. These are observed verification labels, not a causal estimate of negotiation value.

## Leaderboard

Before (2026-10-10T21:01:21.552397+00:00): team **Helllo World**, rank 14, score 69.6/100, ten contributing cases; leader 86.8/100, gap 17.2 points.

After (2026-10-10T21:10:56.148829+00:00): rank 14, score 69.6/100; leader 86.9/100, gap 17.3. Team best-per-case scores did not improve. Quota moved from 160 to 167 used of 600; 433 remained at the snapshot. That seven-session increase matches this batch. Team best-per-case aggregation is not this batch's mean.

## Observed weaknesses and generalizable next steps

1. **Operational recovery comes first.** A single API failure stopped the batch and recovery delays lost the useful standing alternative. Preserve request operation/status, distinguish POST ambiguity from optional-document failure, bound document reads, and rebuild current offers from timeout records before accepting. These are reliability requirements, not supplier-specific strategy.
2. **RFQ closure is too eager.** P05 accepted the first-round Dralveck agreement while the other two suppliers were still open. All three had been contacted. The current any-firm-offer closing rule curtailed further competition. A future policy should preserve a valid agreement while assessing remaining supplier opportunities within deadlines; its economic gain is untested.
3. **Effective dates must reflect likely settled prices.** P01 ended at EUR 134.30 with November effectiveness, versus the supplied teammate EUR 135.38 with April effectiveness. Our lower unit price still cost EUR 18,613.26 more overall. The public cost model supports testing date/price sensitivity and alternatives spanning both increases and discounts. Do not hardcode a practice date or price.
4. **Financing and indexation concessions remain expensive.** P02 matched our older deal: EUR 22,705.90 financing, EUR 17,769.84 index risk, EUR 5,570.63 relationship charge. P18 repeated the earlier outcome and lost an initially available cheaper quote by EUR 1,034.63 during another counter. Package diversity alone is not proof of a better economic trade.
5. **Strong model access does not compensate for restrictive strategy.** The model can select among Python packages and fixed language; it cannot introduce new economic trade structures. The successful Astra calls did not demonstrate better supplier outcomes. Broader grounded reasoning or package generation changes require targeted offline checks and fresh authorized hosted evidence.

These observations guide general strategies; no replay text, competitor results or hidden values were added as runtime inputs. One run per case is not a causal model comparison. Local improvements had not predicted these hosted results.

## Post-run local fixes and remaining limitations

The following fixes were made only after the batch stopped and did not produce any of the scores above: non-retried attachment GETs with five-second HTTP operation timeouts; retained structured offers when auxiliary attachments return selected transient/unavailable errors; propagated authentication failures; reconstructed current timeout offers on resume; and added secret-free HTTP status/method/operation fields to future benchmark errors. Missing document evidence is not replaced with fabricated defaults. The original failure cause is still unknown, so these changes are not a proven fix of that hosted failure.

Post-fix local validation: **105 passed, 1 optional MCP skip**, in 56.87 seconds; Ruff passed. HTTP operation timeouts are not a strict end-to-end guarantee for every possible network response. No hosted retest was run. The frozen plan still refers to the measured pre-fix commit and the stopped journal prevents silent resumption. Three authorized slots remain unused; no replacement P11 session is permitted within the once-per-case batch. New source must be explicitly reviewed before a further benchmark, with mixed-version results labeled if only the remaining three are run. No final run, final submission or merge was performed.
