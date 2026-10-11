# AGENTS.md - handoff for coding agents (Team "Helllo World")

Tacto Negotiation Arena hackathon. We build an AI **buyer agent** that negotiates by e-mail with
the arena's supplier bots and closes the cheapest total deal (or walks away). Code freeze and
Live Final: **Sun 2026-10-11 12:00**.

## CURRENT STATE (Sun 2026-10-11, ~02:30) - read this first

- **Final code: `bebb481`** on `codex/main-preflight-eval-20261010`. Fallback: tag `safe-final-a47ea0d`.
- **Final agent: `--agent buyer`** (rules only, no LLM calls). Hosted 10-case mean 0.679,
  10/10 compliant deals, 0 timeouts; held-out sandbox D01 0.905, D02 0.513.
  `buyer-llm` scored lower (0.617 vs 0.654 on the same code) with 0 fallbacks.
- **Strategy is frozen.** Rejected after testing: lower opening anchor (variants A/B,
  `docs/anchor-repeat-check-20261011.md`), Hamza's combined agent (0.626, one zero).
- Analysis docs: `docs/replay-findings.md`, `docs/gap-analysis.md`,
  `docs/robustness-validation-20261011.md`.
- Only allowed changes now: crash/robustness fixes with tests + D01/D02 + 10-case gate.
  The sections below are the original Saturday handoff (partly outdated).

## Read first (in this order)

1. `brief/brief.md` - rules, scoring, timeline.
2. `brief/api.md` - API, claim checking, the cost formula C, Live Final waves.
3. `docs/solution.md` - **our** agent's design (written by a teammate). `docs/pitch.md` - slides draft.
4. `starter-kit/README.md` - kit usage. Data docs: `data/README.md`, `data/company.md`,
   `data/KNOWN_ISSUES.md`, `data/SCORECARD.md`.

## How scoring works (the essentials)

- Case score = `(C_open - C_deal) / (C_open - C_best)`, clipped 0..1. C = total cost over the
  case's need and horizon: price, uncovered need, payment terms, freight, lead time, quality,
  tooling, index clause, and (for `stabilise`/`secure_supply`) a supplier-margin penalty.
  `starter-kit/arena_kit/cost.py` implements it exactly - **numbers come from code, never the LLM**.
- A broken must-have scores 0. No deal scores the alternative (0 if none).
- Only term sheets bind; omitted fields close on the supplier's standard terms (quote PDF).
- Cited data is checked against `data/facts.json`: max 3 claims per message, each ID once per
  case; a wrong figure / unknown ID (`contradicted`) costs trust.
- **Timing:** 60 s per buyer message per thread (from the supplier's reply); 3 timeouts in a row
  end a thread. Supplier replies take up to ~1 min. **Final waves have an 8-minute hard cap**,
  so realistically only ~5-7 rounds per case in the final (practice has no cap).

## Code map (what exists now)

All code is in `starter-kit/arena_kit/`.

| File | What |
|---|---|
| `agents/buyer.py` | **Our agent.** `BuyerAgent(research, complete=None, model_timeout=8.0)`. Package search over term options against C, tactic choice, closing guard. `decide`, `decide_ready` (RFQ), `close`. |
| `research.py` | `Research`: per-supplier dossiers from CSVs/facts/documents (+ Sunday release), precomputed citable evidence. |
| `play.py` | Kit runner + our `play_threads`: RFQ threads run concurrently (one request in flight per supplier) - fixes the RFQ timeout bug. |
| `benchmark.py` | Offline benchmark vs naive on simulator cases S01-S03 (no network/keys). |
| `cli.py` | `--agent naive | llm | buyer | buyer-llm` (default `buyer`), plus `benchmark` command. |
| `agents/llm.py` | Kit's example LLM agent; `llm_from_env(timeout, max_tokens)`. |
| `cost.py`, `docs.py`, `data.py`, `client.py`, `sim.py` | Kit: cost function, PDF/XLSX reading, data package, API client, local simulator. |
| `tests/test_buyer.py` | Tests for our agent. |

- `buyer`: rules only, no LLM calls.
- `buyer-llm`: the model picks a tactic and up to 2 computed arguments; code writes the e-mail and
  all numbers. Model failure or a slow model falls back to the rules.

## Environment and gotchas

- Python via `uv`. Run everything from `starter-kit/`.
- `starter-kit/.env` holds `ARENA_URL`, `ARENA_API_KEY`, `ARENA_DATA`, `LLM_PROVIDER=openai`,
  `LLM_BASE_URL=https://api.openai.com/v1`, `LLM_MODEL=gpt-6.1-sol`, `LLM_API_KEY`.
  **Never print, log or commit keys.** `.env` is gitignored - keep it that way.
- **pytest breaks on this machine** because of a system ROS install on `PYTHONPATH`. Use:
  `env -u PYTHONPATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest -q`
  (currently 57 passed, 1 skipped). Lint: `uv run ruff check .` (clean).
- Data: committed base data is in `../data`; `uv run arena data` also downloaded
  `starter-kit/data/package`. Sunday release becomes public **2026-10-11 08:00 local (06:00 UTC)**.

## Commands

```bash
cd starter-kit
uv run arena me                                                     # quota + our best scores
uv run arena play case:D02 --agent buyer-llm --data ../data -v      # sandbox: FREE, no quota
uv run arena play case:P01 --agent buyer-llm --data ../data -v      # practice: 1 session
uv run arena run --set practice --agent buyer-llm --data ../data --parallel 8 -v   # 10 sessions
uv run arena benchmark --data ../data --out /tmp/arena-benchmark.json              # offline
```

**Quota:** 200 practice sessions per rolling 24 h (~150 left). Sandbox (`case:D01`, `case:D02`)
does not count - use it for plumbing tests. Don't brute-force practice.

## Results so far

- Practice leaderboard: we are **4th, mean 0.66** (top: 0.74, 0.72, 0.70). P08 went 0.13 -> 0.68.
- Naive agent on P01: 0.583. `buyer-llm` on P01: 0.755.
- Kit's `llm` agent on sandbox: D01 0.81, D02 (RFQ) 0.44. The D02 loss was the RFQ timeout bug: it
  talked only to one bidder, the other thread got 2 timeouts and jumped to a final offer.
  `play_threads` is meant to fix this - **verify on D02**.

## Open tasks (priority order)

1. **Model latency vs the 8 s budget.** `buyer-llm` uses `model_timeout=8.0` (`buyer.py`) and
   `llm_from_env(timeout=12.0, ...)` (`cli.py`). Observed `gpt-6.1-sol` calls took 7-10 s, so
   many moves may silently fall back to rules. Run one case with `-v`, count fallback warnings,
   then tune the timeout or model. Hard limit: decision + overhead must stay well under 60 s.
2. **Benchmark per case.** Run `buyer` and `buyer-llm` across the 10 hosted practice cases; record
   case, agent, commit, score, rounds, c_open/c_deal/c_best, cost breakdown (e.g. CSV). Find the
   weakest cases.
3. **Learn from replays.** For the weakest cases, `GET /v1/sessions/{sid}` (after the end it has
   the trace with the supplier's reasons in words). Write findings in `notes.md`. Turn general
   patterns (not case-specific hacks) into strategy - hidden final cases use new suppliers.
4. **Final-wave fit.** Test with the 8-minute deadline (`play(..., deadline=...)`); the agent
   should get most value in the first 4-5 rounds. Rehearse
   `arena run --set practice --parallel 10` on the final laptop.
5. **Sunday 08:00:** `uv run arena data --out ../data`, confirm `Research` loads the release.

## Rules you must not break

- During the Live Final the agent must **not** read `/v1/events`, `/screen`, `/leaderboard`,
  `/results` (or their JSON). No human in the loop after 12:00.
- One API key per team. No attacks on the service.
- Commit to branches; don't push secrets. Keep tests passing.

## Sunday checklist

- 08:00 refresh data. 09:00 one practice case on the final machine and network.
- Before 12:00: submit repo, commit hash (`git rev-parse HEAD`), description, slides on ehl.gg.
- Start and leave running (log to file, laptop on power, no sleep):
  `uv run arena run --set final --agent buyer --data ../data --parallel 10 -v 2>&1 | tee final.log`
