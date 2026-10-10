# Hosted practice evidence

Recorded on **10 October 2026**. These are practice sessions, including the experiment whose
temporary filename was `final.json`; none is a live-final result.

The [strategy](strategy.md) draws on **34 sessions across nine experiments**. The
[machine-readable record](evaluation.json) preserves scores, terms, costs, errors, available
source fingerprints and replay links. Private decision text and credentials are excluded.

## Experiment record

| Experiment | Cases | Mean score | Successful deals | Interpretation |
|---|---:|---:|---:|---|
| Baseline | 5 | 0.583 | 5/5 | Original buyer on P03, P04, P05, P10 and P11. |
| Candidate | 5 | 0.457 | 5/5 | Asking-price alternatives damaged renewal results. |
| Broad | 5 | 0.650 | 5/5 | P01, P02, P07, P08 and P18; a different case mix. |
| Revised | 5 | 0.569 | 4/5 | Renewals recovered; an RFQ acceptance failed. |
| Full practice | 10 | 0.559 | 9/10 | All hosted case types; P18 acceptance failed. |
| RFQ recovery follow-up | 1 | 0.304 | 1/1 | Valid settlement, but lower score than the earlier 0.504. |
| Quality options follow-up | 1 | 0.536 | 1/1 | Added a simpler compliant quality package. |
| Index recovery follow-up | 1 | 0.467 | 1/1 | P18 settled successfully. |
| Settlement follow-up | 1 | 0.467 | 1/1 | Latest rejected-ID handling present; P18 settled successfully. |

Errors count as zero in experiment averages. All 32 completed deals passed the arena's must-have
checks. Two experiment runs returned an acceptance error instead of a result.

On the **same five baseline cases**, the full-practice batch averaged **0.620**, compared with
**0.583** initially. This is one observation per case and version, with several simultaneous
strategy changes. It does not isolate causality or establish statistical confidence.

## Latest completed observation per case

This table combines the full-practice batch with later targeted follow-ups. It is **not a single
batch at one code revision**, and it deliberately retains the lower RFQ follow-up score.

| Case | Latest score | Relevant terms or lesson | Replay |
|---|---:|---|---|
| P01 — strategic increase | 0.627 | €138.80; increase deferred to April; payment in 14 days. An earlier run reached 0.804, showing variability. | [P01](https://arena.tacto.ai/replay/6962fd3666d5c5b1) |
| P02 — copper-linked motor | 0.503 | €363.54; 45-day payment; 20% copper share and 5% deadband. | [P02](https://arena.tacto.ai/replay/9d570147583757fb) |
| P03 — renewal | 0.919 | €432.29; 90-day payment; 36-month agreement. | [P03](https://arena.tacto.ai/replay/5585ad0a54073811) |
| P04 — routine renewal | 0.815 | €4.86; 14-day payment; 36-month agreement. | [P04](https://arena.tacto.ai/replay/f30235fe1dccdf67) |
| P05 — competitive RFQ | 0.304 | €33.00; 35-day delivery; valid deal after the timing changes. Earlier successful runs reached 0.504. | [P05](https://arena.tacto.ai/replay/7e00f8a6c7bf39a9) |
| P07 — bundling | 0.747 | €5.32; 14-day payment; 36-month agreement. | [P07](https://arena.tacto.ai/replay/d601bf8f79c41816) |
| P08 — raw material | 0.614 | €5.41; 90-day payment; 36 months; indexed pricing. | [P08](https://arena.tacto.ai/replay/a169056c222e5880) |
| P10 — capacity | 0.555 | Full allocation of 23,400/year; 42-day delivery; 36 months; €33.80. | [P10](https://arena.tacto.ai/replay/aac83f7379af15b2) |
| P11 — quality | 0.536 | €46.00; 1,500 ppm; no complaint chargebacks; payment remains fixed at 60 days. | [P11](https://arena.tacto.ai/replay/278ce5b59cde9081) |
| P18 — raw material | 0.467 | €5.50; 90-day payment; 36 months; indexed pricing. | [P18](https://arena.tacto.ai/replay/360a5a28e3864784) |

## What the failures establish

The revised P05 run returned `HTTP 422: not a standing offer in this session`; a subsequent
thread inspection showed that the selected supplier had withdrawn following a timeout. The
full-practice P18 run received the same error while accepting an alternative sheet. That error
alone does not establish why the P18 ID became unacceptable.

The runner now downloads attachments concurrently, limits waiting on an aging final RFQ offer,
refreshes rejected offers, excludes rejected IDs and reruns the acceptance checks. Local regression
tests exercise expiry, refreshed offers and a rejected alternative still listed by the service.
Later hosted runs settled successfully; successful settlement alone does not prove that those
runs exercised every recovery branch.

The published claim-check counts in the nine successful runs of the full-practice batch contain
**15 verified claims and no recorded contradicted claims**. This describes reported checks,
not a semantic audit of all model-written prose. Earlier reports did not collect these counts.

## Reproduce and compare

Use `arena evaluate` as shown in the [strategy](strategy.md#8-validation-and-live-final-procedure).
Keep case selection, model, time budget and concurrency consistent between versions; the current
experiments used a 390-second budget per case and varying concurrency. Evaluate the actual
480-second final setup separately. Keep failed runs in the denominator and report results by
case family before quoting an overall average.
