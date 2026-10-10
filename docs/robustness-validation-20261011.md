# Robustness validation (2026-10-11)

Strategy code remains equivalent to `a6e1dcf`. Two separate commits add
recovery after a rejected acceptance and a regression covering RFQ fallback:
`39ecc1a` and `1b47bd9`.

- Full local suite: **130 passed, 1 skipped**; Ruff clean.
- Free hosted sandbox: D01 **0.9054308542**, D02 **0.5125937285**; both
  closed compliant deals and matched the unchanged-code baseline.
- One hosted practice batch: `buyer`, 10 cases, parallel 10, 480-second case
  deadline. Mean **0.6785258493**, above the approximately 0.67 keep gate.
  **10/10 deals**, all meeting must-haves, no run errors. The detailed report
  is [robustness-hosted-batch-20261011.json](robustness-hosted-batch-20261011.json).
- P05 logged a rejected 422 acceptance for `sup:70250`; the runner refreshed
  current offers and still closed a compliant deal.

This batch matches the earlier `a6e1dcf` mean. It supports retaining the
recovery change for resilience; it does not establish a score improvement.
