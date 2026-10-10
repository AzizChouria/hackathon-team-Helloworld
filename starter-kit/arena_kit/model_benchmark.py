"""Three remaining authorized slots only; historical batch and results stay unchanged."""
import argparse
import json
import os
import statistics

from . import benchmark as bench
from . import revised_benchmark as old
from .agents.strategy import OpenAI
from .cli import load_env
from .client import ArenaClient
from .play import hosted

BATCH = "model_proposals_01"
ORDER = ["case:P07", "case:P03", "case:P04"]
PRIOR = {"case:P01", "case:P05", "case:P02", "case:P18", "case:P08", "case:P10", "case:P11"}
CONFIG = {**old.CONFIG, "HYBRID_PROPOSAL_MODE": "model", "HYBRID_LLM_CALLS_PER_CASE": "4",
          "LLM_MAX_OUTPUT_TOKENS": "2400", "LLM_MAX_INPUT_BOUND": "19000"}


def configure():
    os.environ.update(CONFIG)
    os.environ["LLM_USAGE_PATH"] = str(bench.PRIVATE / "llm_usage.jsonl")


def audit():
    uses = bench.records(bench.batch_paths(BATCH)[0])
    ids = [r["case_id"] for r in uses]
    if len(ids) != len(set(ids)) or set(ids[:7]) != PRIOR or len(ids) > 10 or not set(ids[7:]) <= set(ORDER):
        raise ValueError("Unexpected authorization journal; inspect without starting sessions")
    rows = bench.records(bench.REPORTS / BATCH / "hosted_results.jsonl")
    complete = {r["case_id"] for r in rows if not old.failed(r)}
    if any(old.failed(r) for r in rows) or set(ids[7:]) != complete:
        raise ValueError("Failed or unresolved new attempt; no automatic restart")
    return uses


def prepare():
    configure()
    uses = audit()
    path = bench.PRIVATE / f"{BATCH}_plan.json"
    if path.exists() or len(uses) != 7:
        raise ValueError("Plan already exists or attempts started; do not overwrite")
    frozen = old.identity()
    estimate = bench.forecast(BATCH)
    if estimate["forecast_total_upper_usd"] > 5:
        raise ValueError("Forecast exceeds $5")
    client = ArenaClient(retries=0)
    snapshot = old.team_snapshot(client)
    cases = {c["case_id"]: c for c in hosted(client.cases("practice"))}
    if not set(ORDER) <= set(cases) or snapshot["quota"]["left"] < 3:
        raise ValueError("Hosted availability or quota insufficient")
    plan = {"batch": BATCH, "prepared_at": bench.now(), **frozen, "configuration": CONFIG,
            "order": ORDER, "parallel": 1, "forecast": estimate, "snapshot": snapshot,
            "cases": {c: cases[c] for c in ORDER},
            "authorization": "User lets run; consume only three unused slots of revised authorization"}
    bench.write(path, plan)
    bench.write(bench.REPORTS / BATCH / "readiness.json", {k: v for k, v in plan.items() if k != "cases"})
    bench.write(bench.REPORTS / BATCH / "leaderboard_before.json", snapshot)
    print(json.dumps({k: v for k, v in plan.items() if k != "cases"}, indent=2))


def summarize():
    rows = bench.records(bench.REPORTS / BATCH / "hosted_results.jsonl")
    scores = [r["result"]["score"] for r in rows if isinstance(r["result"].get("score"), int | float)]
    calls = [m for r in rows for m in r["model_calls"]]
    latencies = [m["end_to_end_s"] for m in calls]
    unknown_usage = sum("input_tokens" not in c for c in calls)
    known_cost = sum(c.get("estimated_cost_usd") or 0 for c in calls)
    summary = {"batch": BATCH, "timestamp": bench.now(), "attempted": len(rows), "planned": len(ORDER),
               "completed": sum(r["status"] == "completed" for r in rows),
               "mean_score": statistics.mean(scores) if scores else None,
               "median_score": statistics.median(scores) if scores else None,
               "min_score": min(scores) if scores else None, "max_score": max(scores) if scores else None,
               "full_three_case_mean": statistics.mean(scores) if len(scores) == 3 else None,
               "valid_deals": sum(r["result"].get("deal") and r["result"].get("must_haves_ok") for r in rows),
               "model_calls": len(calls), "model_failures": sum(c["fallback"] for c in calls),
               "decision_fallbacks": sum(d.get("fallback", False) for r in rows for d in r["decisions"]),
               "latency_mean_s": statistics.mean(latencies) if latencies else None,
               "latency_max_s": max(latencies) if latencies else None,
               "input_tokens": None if unknown_usage else sum(c.get("input_tokens", 0) for c in calls),
               "output_tokens": None if unknown_usage else sum(c.get("output_tokens", 0) for c in calls),
               "reasoning_tokens": None if unknown_usage else sum(c.get("reasoning_tokens") or 0 for c in calls),
               "estimated_batch_usd": None if unknown_usage else known_cost,
               "known_estimated_batch_usd": known_cost, "unknown_usage_calls": unknown_usage,
               "reserved_or_charged_upper_usd": sum(c["charged_upper_usd"] for c in calls),
               "cumulative_budget_charge_usd": OpenAI().spent(),
               "not_tested": [c for c in ORDER if c not in {r["case_id"] for r in rows}],
               "limitation": "Three-case sample; not a full ten-case mean or evidence of causal improvement."}
    bench.write(bench.REPORTS / BATCH / "summary.json", summary)
    return summary


def run(approved=False):
    if not approved:
        raise ValueError("Explicit execution approval required")
    configure()
    plan = json.loads((bench.PRIVATE / f"{BATCH}_plan.json").read_text())
    if plan["configuration"] != CONFIG or plan["order"] != ORDER:
        raise ValueError("Configuration changed")
    if old.identity() != {k: plan[k] for k in ("commit", "data_fingerprint")}:
        raise ValueError("Code or data changed")
    uses = audit()
    try:
        for case_id in ORDER:
            if case_id in {r["case_id"] for r in uses}:
                continue
            if old.identity() != {k: plan[k] for k in ("commit", "data_fingerprint")}:
                raise ValueError("Code or data changed")
            row = bench.run(case_id, batch=BATCH, approved=True, expected_case=plan["cases"][case_id])
            summarize()
            if old.failed(row):
                raise ValueError("Stopped on failed/late/model-fallback case; inspect before more sessions")
            uses.append({"case_id": case_id})
    finally:
        bench.write(bench.REPORTS / BATCH / "leaderboard_after.json", old.team_snapshot(ArenaClient(retries=0)))
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
        run(args.execute_approved)
    else:
        configure()
        print(json.dumps(summarize(), indent=2))


if __name__ == "__main__":
    main()
