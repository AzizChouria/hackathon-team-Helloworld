# Benchmark report

> Subsequent hosted outcome: the approved revised batch stopped after seven sessions,
> including one API failure and manual recovery. The seven-case mean was 0.365154;
> three cases remain unstarted. See [REVISED_BENCHMARK_REPORT.md](REVISED_BENCHMARK_REPORT.md).
> The preparation and local results below are historical and do not establish hosted superiority.

Generated 2026-10-10T17:05:13.800322+00:00.

Hosted practice is measured once per case. Offline fixtures and the scripted local simulator are not hosted results. Leaderboard uses best-per-case aggregation, not this run mean.

| Case | Status | Score | Deal | C deal | Model / effort | Replay |
|---|---|---:|---|---:|---|---|
| case:P01 | completed | 0.5215388817771789 | True | 1124070.82 | gpt-6-astra / high | [replay](https://arena.tacto.ai/replay/084c088e49bc4af8) |
| case:P02 | completed | 0.3041020884649592 | True | 2268467.21 | gpt-6-astra / high | [replay](https://arena.tacto.ai/replay/bb7c8f3e1881d77e) |
| case:P03 | completed | 0.8015505457748919 | True | 3975974.33 | gpt-6-astra / high | [replay](https://arena.tacto.ai/replay/48bf2049ac371f98) |
| case:P04 | completed | 0.8153309653389462 | True | 196957.2 | gpt-6-astra / high | [replay](https://arena.tacto.ai/replay/2a665ae94e12a73c) |
| case:P05 | completed | 0.34857592090870065 | True | 276919.63 | gpt-6-astra / high | [replay](https://arena.tacto.ai/replay/1bd880ed4fa35dd5) |
| case:P07 | completed | 0.6344263514955618 | True | 332796.0 | gpt-6-astra / high | [replay](https://arena.tacto.ai/replay/9329c0f136d34c5a) |
| case:P08 | completed | 0.4848629340985013 | True | 1050756.04 | gpt-6-astra / high | [replay](https://arena.tacto.ai/replay/508320e994eb9575) |
| case:P10 | completed | 0.5390452124905989 | True | 1607143.2 | gpt-6-astra / high | [replay](https://arena.tacto.ai/replay/774770dae9bd6ba2) |
| case:P11 | completed | 0.5401566167055717 | True | 766221.0 | gpt-6-astra / high | [replay](https://arena.tacto.ai/replay/3b8e51df05966742) |
| case:P18 | completed | 0.3253669647097238 | True | 271576.98 | gpt-6-astra / high | [replay](https://arena.tacto.ai/replay/bed6b17335733ae7) |

## Aggregate evidence

```json
{
  "count": 10,
  "mean": 0.5314956481764634,
  "median": 0.5302920471338889,
  "min": 0.3041020884649592,
  "max": 0.8153309653389462,
  "population_stdev": 0.1715077584127625,
  "deals": 10,
  "completed": 10,
  "valid_deals": 10,
  "hosted_model_calls": 16,
  "hosted_model_failures": 0,
  "hosted_latency_mean_s": 10.572187499999927,
  "hosted_latency_max_s": 15.235000000000582,
  "all_input_tokens": 18850,
  "all_output_tokens": 6879,
  "all_reasoning_tokens": 6048,
  "all_estimated_cost_usd": 0.53245,
  "all_accounted_upper_usd": 0.53245
}
```

## Leaderboard

before: 2026-10-10T15:52:50.074715+00:00

```json
{
  "timestamp": "2026-10-10T15:52:50.074715+00:00",
  "me": {
    "team_name": "Helllo World",
    "status": "active",
    "practice": {
      "used": 49,
      "left": 151,
      "limit": 200,
      "resets_at": "2026-10-11T12:34:32.024144+00:00"
    },
    "best": {
      "case:P01": 0.8037745269114009,
      "case:P03": 0.9194563231244482,
      "case:P07": 0.7466905323485927,
      "case:P18": 0.5324730605736524,
      "case:P11": 0.5577158875272699,
      "case:P08": 0.6786754259290533,
      "case:P02": 0.5026557732658966,
      "case:P10": 0.5702676838822193,
      "case:P04": 0.8153309653389462,
      "case:P05": 0.503576865249348
    }
  },
  "team": {
    "team_name": "Helllo World",
    "played": 10,
    "total": 66.3,
    "deals": 10,
    "rounds": 55,
    "rank": 4
  },
  "leader": {
    "team_name": "TakeTheMoneyAndRun",
    "played": 10,
    "total": 74.9,
    "deals": 10,
    "rounds": 52,
    "rank": 1
  },
  "case_count": 10,
  "teams_count": 21,
  "gap": 8.600000000000009
}
```

## Baseline and limitations

Prior genuine naive P01 baseline: 0.5828313200135649. Hybrid P01: 0.5215388817771789. Single runs are not controlled causal comparisons; no other measured naive/LLM baselines.

Exact relationship charges require hidden supplier economics; runtime estimates use public supplier-specific should-cost and an explicitly uncertain financing assumption. No hidden c_best, board, rankings, or replay data enter the agent. Price-unit metadata is preserved; the published arena cost helper uses case units directly.

Billing is estimated at verified Astra standard prices ($10/M input, $50/M output), conservatively without cache discounts. It is not an invoice. Timed-out/unknown calls retain their full reservation. See machine-readable call metrics for model IDs, effort and fallbacks.

Nine data-only cases have economic fixtures in benchmarks/offline_cases.json; no supplier behavior or scores are claimed. No final session was started. See HYBRID_README.md for operations.

## After-benchmark engineering update

All hosted measurements above belong to commit **08002e0**, not the subsequent local fixes.
The pre-benchmark board showed **Helllo World, rank 4/21, 66.3**, behind **TakeTheMoneyAndRun,
74.9**, a gap of **8.6**. No measured run beat the recorded team per-case best (P04 tied).
**An after-benchmark board snapshot is unavailable. Current rank and gap are not verified.**
User-reported later team usage is 110/200; this report contains only our ten authorized runs.

P01 scored 52.15/100 versus the supplied naive baseline 58.28: a 6.13-point decline and a
EUR 3,491.46 higher deal cost. P03/P04 renewals were strongest. P02 copper, P18 alloy and P05 RFQ
were weakest. One P05 buyer timeout occurred despite successful model calls; the old batch
barrier consumed time on a faster supplier. Repeated same-batch evidence also lost citation
credit. P18 closed above an earlier offer after more bargaining; the old offer was no longer
standing. These observations motivate general cost/deadline fixes, not case-specific answers.

P02 financing (EUR 22,705.90) and index risk (EUR 17,769.84), P08 index cost/risk
(EUR 27,234.14 / EUR 4,539.02), and P11 freight (EUR 24,486.00) are significant non-price
components. They are opportunities to trade, not guaranteed removable costs. Pure price-focused
comparisons would miss them. Deterministic fallbacks include deliberate non-model turns; zero
model failures does not mean zero fallback decisions. Recorded retries were zero.

See **LOCAL_VALIDATION.md** for the subsequent fixes, 76 passing tests, 19 offline economic
fixtures and 36 synthetic before/after comparisons. Revised hosted performance is **untested**.
No additional hosted session or paid OpenAI call was used for the local revision. No final run,
submission, main merge or force operation was performed. Medium negotiation and alternate-model
comparisons remain unmeasured; connectivity probes do not establish negotiation quality.
