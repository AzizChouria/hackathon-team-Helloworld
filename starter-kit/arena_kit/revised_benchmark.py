"""Prepare a frozen, sequential revised practice benchmark. Preparation never starts sessions.

Execution requires a separate explicit --execute-approved flag AFTER user authorization.
Only revised_01 is supported; the original ten-session ledger and its reports are preserved.
This module is offline benchmark tooling and must never be imported by a negotiation agent.
"""
import argparse
import json
import os
import statistics
import subprocess

from . import benchmark as bench
from .agents.intelligence import Intelligence
from .cli import load_env
from .client import ArenaClient
from .play import hosted

BATCH = "revised_01"
ORDER = [f"case:P{n:02}" for n in (1, 5, 2, 18, 8, 10, 11, 7, 3, 4)]
CONFIG = {
    "LLM_PROVIDER": "openai", "LLM_BASE_URL": "https://api.openai.com/v1",
    "LLM_MODEL": "gpt-6-astra", "LLM_EFFORT": "high", "LLM_ENDPOINT": "responses",
    "LLM_TIMEOUT_S": "22", "LLM_MAX_OUTPUT_TOKENS": "1200", "LLM_BUDGET_USD": "5",
    "LLM_INPUT_USD_PER_M": "10", "LLM_OUTPUT_USD_PER_M": "50",
    "HYBRID_PROPOSAL_MODE": "legacy", "HYBRID_LLM_CALLS_PER_CASE": "2", "HYBRID_MAX_COUNTERS": "5",
    "HYBRID_RESPONSE_GUARD_S": "35", "HYBRID_STALL_ROUNDS": "2", "HYBRID_OFFLINE": "0",
}


def configure():
    # Process-local settings only; do not modify .env or credentials.
    os.environ.update(CONFIG)
    os.environ["LLM_USAGE_PATH"] = str(bench.PRIVATE / "llm_usage.jsonl")


def identity():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=bench.ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", "starter-kit/arena_kit"],
                                    cwd=bench.ROOT, text=True).strip()
    if dirty:
        raise ValueError("Commit tested runtime code before preparing the revised benchmark")
    data = bench.package()
    try:
        fingerprint = Intelligence(data).fingerprint()
    finally:
        if data.db:
            data.db.close()
    return {"commit": commit, "data_fingerprint": fingerprint}


def team_snapshot(client):
    me, board = client.me(), client.leaderboard("practice")
    teams = board.get("teams", [])
    own = next((t for t in teams if t.get("team_name") == me.get("team_name")), None)
    leader = min(teams, key=lambda t: t.get("rank", float("inf"))) if teams else None
    return {"timestamp": bench.now(), "team_name": me.get("team_name"), "quota": me.get("practice"),
            "team": own, "leader": leader, "team_best": me.get("best", {}),
            "gap": leader["total"] - own["total"] if leader and own else None}


def preflight():
    configure()
    missing = [k for k in ("ARENA_URL", "ARENA_API_KEY", "LLM_API_KEY") if not os.environ.get(k)]
    if missing:
        raise ValueError("Missing required variables: " + ", ".join(missing))
    if os.environ["ARENA_URL"].rstrip("/") != "https://arena.tacto.ai":
        raise ValueError("This benchmark is restricted to the official practice arena")
    frozen = identity()
    forecast = bench.forecast(BATCH)
    if forecast["forecast_total_upper_usd"] > 5:
        raise ValueError("Full coverage exceeds the existing cumulative $5 ceiling")
    client = ArenaClient(retries=0)
    snapshot = team_snapshot(client)
    cases = {c["case_id"]: c for c in hosted(client.cases("practice"))}
    if not set(ORDER) <= set(cases):
        raise ValueError("A prepared case is not hosted; do not silently substitute another case")
    if snapshot["quota"]["left"] < forecast["remaining_sessions"]:
        raise ValueError("Team quota cannot cover every remaining case")
    return {"batch": BATCH, "prepared_at": bench.now(), **frozen, "configuration": CONFIG,
            "parallel_cases": 1, "order": ORDER, "forecast": forecast, "snapshot": snapshot,
            "cases": {c: cases[c] for c in ORDER}, "execution_approved": False}


def prepare():
    journal, reports, _ = bench.batch_paths(BATCH)
    if bench.records(journal):
        raise ValueError("Batch already attempted; preserve its frozen plan and inspect results")
    plan = preflight()
    bench.write(bench.PRIVATE / "revised_01_plan.json", plan)
    public = {k: v for k, v in plan.items() if k != "cases"}
    public["status"] = "prepared only; no hosted sessions or model calls started"
    bench.write(reports / "readiness.json", public)
    print(json.dumps(public, indent=2))
    return plan


def summarize():
    _, reports, _ = bench.batch_paths(BATCH)
    rows = bench.records(reports / "hosted_results.jsonl")
    scores = [r.get("result", {}).get("score") for r in rows]
    numeric = [s for s in scores if isinstance(s, int | float)]
    calls = [c for r in rows for c in r.get("model_calls", [])]
    summary = {"batch": BATCH, "attempted": len(rows), "planned": len(ORDER),
               "completed": sum(r.get("status") == "completed" for r in rows),
               "mean_completed_score": statistics.mean(numeric) if numeric else None,
               "full_10_case_mean": statistics.mean(numeric) if len(numeric) == len(ORDER) else None,
               "buyer_timeouts": sum(r.get("buyer_timeouts", 0) for r in rows),
               "model_calls": len(calls), "model_failures": sum(c.get("fallback", False) for c in calls),
               "estimated_batch_usd": sum(c.get("estimated_cost_usd") or 0 for c in calls),
               "not_tested": [c for c in ORDER if c not in {r["case_id"] for r in rows}]}
    bench.write(reports / "summary.json", summary)
    return summary


def failed(row):
    return bool(row.get("error") or row["status"] != "completed" or row.get("buyer_timeouts", 0)
                or row["result"].get("deal") and not row["result"].get("must_haves_ok")
                or any(c.get("fallback") for c in row["model_calls"])
                or any(d.get("model_called") and d.get("fallback") for d in row["decisions"]))


def run(*, approved=False):
    if not approved:
        raise ValueError("Not authorized: use --execute-approved only after explicit approval for ten new sessions")
    configure()
    plan_path = bench.PRIVATE / "revised_01_plan.json"
    if not plan_path.exists():
        raise ValueError("Prepare and review the frozen benchmark first")
    plan = json.loads(plan_path.read_text())
    if plan["configuration"] != CONFIG or plan["order"] != ORDER:
        raise ValueError("Prepared configuration changed; review and prepare again")
    if identity() != {k: plan[k] for k in ("commit", "data_fingerprint")}:
        raise ValueError("Code or data changed since preparation")
    fresh = preflight()
    if fresh["cases"] != plan["cases"]:
        raise ValueError("Hosted case data changed since preparation")
    journal, reports, _ = bench.batch_paths(BATCH)
    uses = bench.records(journal)
    rows = bench.records(reports / "hosted_results.jsonl")
    if any(failed(r) for r in rows):
        raise ValueError("Prior batch failure needs review; cannot resume automatically")
    completed = {r["case_id"] for r in rows if r["status"] == "completed" and not r.get("error")}
    if any(r["case_id"] not in completed for r in uses):
        raise ValueError("An earlier attempt is unresolved; no automatic session recreation")
    if not uses:
        bench.write(reports / "leaderboard_before.json", fresh["snapshot"])
    for case_id in ORDER:
        if case_id in {r["case_id"] for r in uses}:
            continue
        if identity() != {k: plan[k] for k in ("commit", "data_fingerprint")}:
            raise ValueError("Code or data changed during the frozen benchmark")
        row = bench.run(case_id, batch=BATCH, approved=True, expected_case=plan["cases"][case_id])
        summarize()
        if failed(row):
            raise ValueError("Stopped after a failed/late/model-fallback case; inspect before more sessions")
        uses.append({"case_id": case_id})
    bench.write(reports / "leaderboard_after.json", team_snapshot(ArenaClient(retries=0)))
    print(json.dumps(summarize(), indent=2))


def main():
    load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run", "report"])
    parser.add_argument("--execute-approved", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "run":
        run(approved=args.execute_approved)
    else:
        print(json.dumps(summarize(), indent=2))


if __name__ == "__main__":
    main()
