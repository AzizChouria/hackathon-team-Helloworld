# Development Notes

Tacto Negotiation Arena is a Python starter kit for a procurement buyer agent representing the fictional Hollerau Pumpenwerke. Agents negotiate with supplier services through the arena API. The repository includes the challenge documentation, example agents, a local simulator, and procurement data.

## Repository structure

| Path | Purpose |
| --- | --- |
| `README.md` | Project overview, quickstart, event information, and links. |
| `brief/README.md` | Index of the challenge documents. |
| `brief/brief.md` | Participant story, task, data, negotiation flow, scoring, and rules. |
| `brief/api.md` | HTTP API reference: cases, sessions, messages, documents, results, and limits. |
| `brief/submission.md` | Submission requirements and pitch instructions. |
| `starter-kit/README.md` | Setup, practice agents, simulator, custom agents, and MCP usage. |
| `starter-kit/pyproject.toml`, `uv.lock` | Python package configuration, dependencies, CLI entry points, and locked dependency versions. |
| `starter-kit/arena_kit/` | Client, CLI, agents, negotiation runner, data access, cost calculation, document parsing, simulator, and MCP server. |
| `starter-kit/arena_kit/sim_cases/` | Three local simulator scenarios: S01, S02, and S03. |
| `starter-kit/tests/` | Kit and simulator tests, with PDF and XLSX fixtures. |
| `starter-kit/Dockerfile` | Container configuration for the simulator. |
| `data/` | Procurement data package v1.0.0, dated 2026-09-30. |
| `.github/` | README artwork and issue-template configuration. |
| `.env.example`, `starter-kit/.env.example` | Environment configuration templates; their contents were not inspected for this note. |
| `LICENSE`, `LICENSE-data` | MIT code licence and CC BY 4.0 data/documentation licence. |

The root also contains `notes.md` and local tooling/configuration directories such as `.claude/`, `.codex/`, `.entire/`, and `.idea/`.

### Starter-kit modules

- `cli.py`: exposes `arena` commands and loads `.env` from the current working directory. Existing environment variables take precedence.
- `client.py`: `ArenaClient`, HTTP requests, pacing, retries, and practice-quota tracking.
- `play.py`: single-case, parallel-case, and final-wave runners; `RemoteTable` connects agents to the API.
- `agents/naive.py`: default baseline agent; anchors 10% below the opening price, splits the price gap, and accepts early. It requires no LLM provider.
- `agents/llm.py`: optional model-backed example agent using case information and the data package.
- `cost.py`: total-cost calculation, scoring helpers, must-haves, and offer completion.
- `docs.py`: PDF/XLSX extraction and supplier terms parsing.
- `data.py`: data-package access, citable facts, read-only SQL, and document lookup.
- `sim.py`: local API simulator with scripted suppliers.
- `mcp_server.py`: read-only MCP access to the data package.

### Data layout

- `data/data/*.csv`: 24 source tables covering suppliers, parts, sourcing, prices, contracts, purchase orders, receipts, invoices, quality, forecasts, RFQs, quotes, spend, market indices, cost estimates, news, and documents.
- `data/datapackage.json`: table schemas and package metadata.
- `data/world.sqlite`: the CSV tables packaged as SQLite.
- `data/facts.json`: citable IDs and their associated values.
- `data/contracts/`: contract texts; `data/correspondence/`: letters, emails, and notes.
- `data/README.md`: table inventory, relationships, and SQL examples.
- `data/company.md`, `SCORECARD.md`, `KNOWN_ISSUES.md`, `ATTRIBUTION.md`: business context, scorecard methodology, data caveats, and source attribution.

Company data is synthetic; market series use real open data. Prices use the recorded `price_unit`, which may represent 1, 100, or 1,000 units.

## Running the existing practice agent

These are reference commands only; none were executed while preparing this file. Commands below use PowerShell and assume the repository root as the starting directory.

### Setup

Install Python 3.12 and `uv`. The package requires Python `>=3.12,<3.13`.

```powershell
Set-Location .\starter-kit
uv sync --all-extras
# Only create .env if one does not already exist:
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Configure `starter-kit/.env` privately with `ARENA_URL=https://arena.tacto.ai` and the team's `ARENA_API_KEY`. No credential values are included here. Run the remaining commands from `starter-kit/` so the CLI finds that file. The naive agent does not need an LLM key or a downloaded data package.

### Hosted practice

The following inspection commands contact the configured arena without starting a negotiation:

```powershell
uv run arena me
uv run arena cases --set practice
uv run arena board --set practice
```

The next command **starts a hosted practice negotiation** and consumes practice quota. It is documented here for future use, not executed as part of this inspection:

```powershell
uv run arena play case:P01 --agent naive -v
```

`--agent naive` is the default, so `uv run arena play case:P01 -v` is equivalent. The CLI prints deal details, cost/score information, a replay link when available, and remaining practice quota. The repository documents a limit of 200 practice sessions per team per rolling 24 hours.

### Optional LLM agent

Privately configure `LLM_PROVIDER` and `LLM_MODEL`, plus the appropriate provider credentials: `LLM_API_KEY` and optionally `LLM_BASE_URL` for an OpenAI-compatible endpoint, or `ANTHROPIC_API_KEY` for Anthropic.

The checked-in data can be used directly with `--data ..\data`. This command also starts a hosted practice negotiation:

```powershell
uv run arena play case:P01 --agent llm --data ..\data -v
```

The documented data-refresh command is `uv run arena data`; it downloads and unpacks data beneath `starter-kit/data/` by default. If using that downloaded package, pass `--data data/package` or set `ARENA_DATA=data/package`. Refreshing data writes files and was not performed during this inspection.

## Local simulator and development checks

For future local development, start the scripted simulator from `starter-kit/`:

```powershell
uv run arena-sim serve --no-clock --data ..\data
```

It listens on `http://127.0.0.1:8000` by default. `--no-clock` disables the reply deadline; `--data` is optional. Local cases are `case:S01` through `case:S03`, distinct from hosted practice cases. The simulator is an API-contract exercise, not a model of the hosted suppliers' strategy. Its registration and authentication steps are in `starter-kit/README.md`; no simulator was started or credentials generated during this inspection.

Other documented development commands, run from `starter-kit/`:

```powershell
uv run pytest
uv run ruff check .
uv run arena mcp --data ..\data
```

Tests normally use the local simulator. The starter-kit README also documents hosted test configuration through `ARENA_TEST_URL` and `ARENA_TEST_KEY`; do not configure hosted tests when only local validation is intended. The MCP command exposes the checked-in data over stdio.

## Inspection scope

This note was checked against the repository documentation, package configuration, CLI, and relevant source files. No dependencies were installed, tests or negotiations run, API keys accessed or printed, existing files edited, or Git commits/pushes created. Pre-existing changes in `.claude/settings.json` and `.codex/hooks.json` were left untouched.
