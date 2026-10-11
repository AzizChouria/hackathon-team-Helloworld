# Helllo World — final submission

## Approach (10 lines)

1. Prepare one deterministic `buyer` agent per case; no model call is required during play.
2. Load the published base package and Sunday release into the supplier research dossiers.
3. Read the case's need, horizon, negotiable terms, supplier threads, and must-haves.
4. Parse quote documents to recover standard terms that bind when a sheet omits a field.
5. Compute every package's full-horizon buyer cost with the published cost formula.
6. Propose only complete, compliant packages and price payment, delivery, quality, and index exchanges.
7. Run RFQ supplier threads concurrently so each bidder stays engaged within the reply clock.
8. Cite only verified, relevant research IDs, respecting the per-message and per-case claim limits.
9. Close on the cheapest current, compliant standing sheet that beats the alternative.
10. Walk away when no feasible standing deal beats the available alternative.

## Final machine and run

Configure `ARENA_URL` and `ARENA_API_KEY` in `starter-kit/.env` or the process
environment. `ARENA_DATA` may point at the downloaded package, but the command
below explicitly selects `../data`. The deterministic buyer does not require
`LLM_API_KEY`, `LLM_MODEL`, or `LLM_PROVIDER`. Do not put credential values in
the submission or logs.

```bash
cd ~/hackathon-team-Helloworld/starter-kit
unset FINAL_RUN_WAVES                  # rehearsal override; final uses five waves
uv run arena data --out ../data       # refresh the public Sunday release
test -f ../data/release-sunday/facts.json
uv run arena me                       # check team connection before the start
./scripts/final_run.sh                # sleep inhibitor, timestamped log, restart on crash
```

Start the script before 12:00 Europe/Berlin and leave the laptop powered and
connected. It waits through the pre-final 403, plays each wave with 10 parallel
cases, exits after five waves, and resumes existing final sessions after a
process restart. Submit the repository, `git rev-parse HEAD`, this approach,
and the slides before the deadline. Local rehearsal evidence is in
[final-rehearsal-20261011.md](final-rehearsal-20261011.md).
