# Hybrid buyer agent

The hybrid agent uses the official cost model to compare validated packages. Public supplier
documents, selected SQL rows and fact IDs supply evidence. Astra selects packages, evidence and
a professional phrase/question from bounded choices. It cannot invent prices, citations, acceptance
actions or confidential disclosures. Naive and llm remain available.

## Setup and commands

From `starter-kit/`, Python 3.12 and uv:

```powershell
uv sync --extra sim
uv run --offline --extra sim pytest -q
uv run --offline ruff check .
uv run --offline python -m arena_kit.local_eval
uv run arena cases
uv run arena play case:P01 --agent hybrid --data ../data -v
uv run arena run --set practice --agent hybrid --data ../data --parallel 2
```

**Practice commands create sessions. Do not rerun them after the authorized benchmark.**
The comprehensive benchmark uses the individual commands below so P01 cannot be duplicated.
Normal tests cannot connect to a hosted arena; simulator tests use localhost.

```powershell
uv run python -m arena_kit.benchmark snapshot --label before
uv run python -m arena_kit.benchmark offline
uv run python -m arena_kit.benchmark probe --effort high
uv run python -m arena_kit.benchmark forecast
uv run python -m arena_kit.benchmark run --case case:P01 --effort high
uv run python -m arena_kit.benchmark snapshot --label after
uv run python -m arena_kit.benchmark report
```

Only use `run --case` for remaining authorized IDs, once each. The persistent
`starter-kit/.local/sessions.jsonl` reserves a slot BEFORE a session creation attempt. An ambiguous
failure consumes that slot; there is no automatic new session. Do not erase the ledger.
The old naive P01 baseline is outside this assignment. Team activity may continue independently.

## Private environment

Use the application's `load_env()`; existing environment values win over `.env`.
Never commit keys. Required names: `ARENA_URL`, `ARENA_API_KEY`, `LLM_MODEL`,
`LLM_API_KEY`. Data location: `ARENA_DATA` or `--data`; optional `ARENA_RELEASE`.
If the configured data folder is absent, hybrid explicitly reports use of the checked-in root
`data/` package. The existing private configuration is never rewritten.

OpenAI controls: `LLM_PROVIDER` (hybrid uses OpenAI), `LLM_BASE_URL`, `LLM_MODEL`,
`LLM_EFFORT`, `LLM_ENDPOINT` (responses or chat), `LLM_TIMEOUT_S` (default 22, maximum 30),
`LLM_MAX_OUTPUT_TOKENS` (default 1200), `LLM_BUDGET_USD` (hard maximum 5),
`LLM_USAGE_PATH`, `LLM_INPUT_USD_PER_M`, `LLM_OUTPUT_USD_PER_M`.
Rates default only for gpt-6-astra. Any other model requires explicit verified rates and approval.
No silent model or effort substitution occurs. The benchmark explicitly selects high in its
process; ordinary CLI commands honor the existing private environment.

Hybrid controls: `HYBRID_LLM_CALLS_PER_CASE` (default 2), `HYBRID_MAX_COUNTERS` (default 5),
`HYBRID_OFFLINE` (1 disables model calls; results must be labeled deterministic).
`HYBRID_RESPONSE_GUARD_S` (default/max 35) limits how long to wait on an available supplier
reply before deterministic closing; `HYBRID_STALL_ROUNDS` (minimum/default 2) protects a
concession after consecutive non-improving rounds. An unchanged opening does not trigger this rule.
Budget failure or a transport/schema failure produces a validated deterministic action.
Only local diagnostics and token/cost metrics are logged; prompts and provider error bodies are not.

## Architecture and economics

- `agents/hybrid.py`: per-case lifecycle, evidence/candidate coordination, fallback diagnostics,
  adaptive package ordering, and deterministic closing.
- `agents/intelligence.py`: case/supplier-scoped data and document research. Checks file metadata
  fingerprints when preparing a case and rebuilds package caches on changes.
- `agents/optimizer.py`: finite-domain beam search, complete valid packages, price hypotheses,
  must-haves and cross-supplier costs. Up to three distinct packages explore cash and planning terms.
- `agents/decision.py`: select the cheapest feasible standing sheet that beats the contractual
  alternative; otherwise walk. No-deal with no alternative is not treated as a fictional spot quote.
- `agents/strategy.py`: Responses or Chat Completions with reasoning effort and strict JSON.
  No sampling parameters; incomplete output, refusals, 429s and schema failures fall back without
  model retries. A daemon request worker bounds the buyer's wait even if the transport stalls.
- `play.py`: keeps RFQ requests in flight independently, excludes pending offers from acceptance,
  collects completed replies, and closes ready threads before their response guard. It can close
  a case while another supplier request is still running; that request is allowed to finish,
  with no further POST issued by the coordinator. Model calls are skipped when time is short.
- `local_eval.py`: compares deterministic current behavior against commit 08002e0 on 36 local
  synthetic fixtures. It never loads credentials, creates network connections, or calls a model.
- `benchmark.py`: isolated offline reporting, usage/session ledgers, snapshots and practice execution.
  The agent never imports it or reads leaderboards, replays, scores or c_best.

Reuse `cost_breakdown(case, terms, standard=None, supplier=None)`,
`total_cost(case, terms, standard=None, supplier=None)`,
`complete_offer(case, terms)`, `must_haves_ok(case, terms, standard=None)`.
Supplier defaults come from attached quote PDFs parsed by the existing document helpers. PDF/XLSX
attachments are ingested by the runner; no invented outgoing attachments are needed.

The official cost helper covers timing, volume/coverage, uncovered need, financing, freight,
late delivery, quality/chargebacks, tooling, index and relationship terms. ERP values are per
price_unit; the official case cost convention is preserved, without a second conversion.
Relationship charges are estimates: supplier-specific should-cost with at least 5% uncertainty
and assumed 12% financing. True supplier economics and c_best are unavailable during negotiation.
A beam-search optimum is not a proven acceptable supplier floor.

Only exact fact-based sentences are cited. Index changes use same-series windows up to twelve
months, price history excludes stale-condition order rows, and rolling scorecards distinguish OTD
from PPM. Up to two claims per move leave room under the arena's three-claim cap. Historical quotes
and invoices provide internal context; they are not represented as active competitor offers.
Should-cost and credit evidence do not establish financial distress.

## Local simulator

```powershell
uv run arena-sim serve --data ../data --no-clock
```

Use a separate terminal/process with a localhost ARENA_URL and a simulator-only key. Do not
overwrite the hosted key. Tests automatically register a disposable local team and run S01-S03
in parallel, including document parsing. The supplier is a fixed script; its scores predict no
hosted performance. Nineteen case economic fixtures use case files from a read-only practice
listing; nine are data-only, with no claimed hosted scores.

## Verified rules and Sunday procedure

Repository `brief/brief.md`, `brief/api.md`, `brief/submission.md` specify Sunday 12:00 freeze
and submission on ehl.gg; the dated Sunday data release is 2026-10-11T06:00:00Z (08:00 Berlin).
Thus October 11 is supported by the dated API example and weekend schedule; confirm the event
clock with organizers. Jury weighting and Saturday closing time still contain placeholders.

1. After 08:00, run `uv run arena data`. Point `--data` at the downloaded package with
   release-sunday alongside it, or set ARENA_RELEASE. Verify new IDs loaded, rerun tests, then
   restart the runner after refresh. No persistent intelligence cache survives a process restart.
2. The rules request a 09:00 practice preflight on the final machine. **That needs fresh session
   authorization once these ten are used.** Do not consume an eleventh session automatically.
3. By 11:30 check `arena me`, data, power, no-sleep settings, network, paid API credits and actual
   account RPM/TPM. Ten concurrent cases need ten active sessions and share a client paced at
   nine HTTP calls/s (server allows ten). Each case uses at most two model calls by default.
4. Review actual measured model latency and RFQ behavior. Supplier replies may take a minute;
   buyer has 60 seconds per thread. The revised coordinator removes the slowest-reply batch
   barrier and has adversarial local timing tests. Revised behavior has NOT been hosted-tested.
   Ten-way concurrency passes locally; actual final API/account capacity remains unverified.
5. Set the intended final model/effort explicitly in the launch process. Review development budget
   headroom: the default hard $5 ledger also applies to ordinary hybrid CLI runs. Do not erase
   development spend or raise its cap to evade authorization. A separately approved final budget
   policy is needed if the remaining $5 cannot cover all waves.
6. The following is **prepared only, never executed during development**:

```powershell
uv run arena run --set final --agent hybrid --data data/package --parallel 10
```

Start before 12:00 only with explicit final-run authorization. The runner polls your own case list,
plays one session per case, closes before the cap, resumes existing final sessions and stops after
five waves. No board, event feed, screen or results requests belong in this process.
No humans in the loop after the freeze.

Submit on ehl.gg: repository https://github.com/AzizChouria/hackathon-team-Helloworld,
the exact reviewed Git commit, approach description, and pitch slides. Verify both jury and tum.ai
can open the repository. Submission and final execution are manual, not performed by this mission.
Top ten pitch from 13:00: five minutes plus two minutes questions. Explain one negotiation, evidence,
trade-offs, and limitations; do not imply the model computed or knew hidden supplier economics.

## Model evidence and limits

Official sources checked 2026-10-10:
[GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra),
[pricing](https://developers.openai.com/api/docs/pricing),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
Astra supports high and medium reasoning and structured output. Minimal live requests verified the
returned model ID and Responses schema on this key. Usage is estimated at standard $10/M input
and $50/M output (no cache discount assumed), not reconciled with an invoice.
Simple-probe latency does not establish a worst-case bound or account concurrency capacity.
See BENCHMARK_REPORT.md and benchmarks/ for measured outcomes and the actual deployed revision.

## Local validation after the hosted benchmark

See [LOCAL_VALIDATION.md](LOCAL_VALIDATION.md) for exact evidence and limitations.
All four pending regressions are fixed. The full suite passes 76 tests (one optional MCP test
skipped), Ruff passes, and all 19 cached economic fixtures validate. On 36 identical synthetic
fixtures, revised deterministic behavior costs less in 11, ties in 25, and costs more in none
against the prior commit. These are not hosted scores or evidence of beating team leaderboard bests.

Missing quote defaults cannot establish must-have compliance from the buyer plan. Counteroffers
must improve on the cheapest feasible standing offer, non-price package profiles are unique, and
evidence is reserved across pending RFQ moves. The second model call interprets the first reply;
its numeric terms and acceptance decisions remain controlled by Python. Trigger documents lead
the evidence brief, including Sunday-release documents absent from SQLite.
