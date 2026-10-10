# Repeated opening-anchor checks (2026-10-11)

The baseline buyer code matches `a6e1dcf`. Each sandbox run used the deterministic
`buyer` agent and a 480-second deadline. D02 was run three times and D01 twice
per source version. All sandbox runs closed compliant deals.

| Source | D01 scores / mean | D02 scores / mean |
| --- | --- | --- |
| Baseline (`a6e1dcf` code) | 0.90543, 0.90543 / **0.90543** | 0.51259, 0.51259, 0.51259 / **0.51259** |
| Variant A (`9a60a79`, lower anchors including RFQ) | 0.90543, 0.90543 / **0.90543** | 0.51259, 0.53366, 0.55472 / **0.53366** |
| Variant B (`6b0d06b`, lower anchor only for single suppliers) | 0.90543, 0.90543 / **0.90543** | 0.51259, 0.51259, 0.51259 / **0.51259** |

An earlier single Variant A D02 run scored 0.30575. The repeats show why that
one run was insufficient to judge the anchor. Variant B kept the multi-supplier
opening and rival-cost anchors identical to the baseline, and passed both
repeated sandbox gates. The code tests passed (126 passed, 1 skipped) and Ruff
passed before its hosted batch.

Variant B's one hosted practice batch used `buyer`, 10 cases in parallel, and a
480-second per-case deadline. Its mean was **0.671084**, below the required
**0.679**. All ten runs closed deals that met must-haves; no run errored. The
per-case scores, rounds, decisions, and sessions are in
[the batch report](anchor-variant-b-hosted-20261011.json).

Variant B failed the hosted mean gate and was reverted by `f6d146c`. Variant A
was then reverted by `c5177ac`, returning the buyer and tests exactly to
`a6e1dcf` code. Neither anchor variant remains active.
