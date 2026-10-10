"""Offline reporting and explicitly bounded practice benchmark. NEVER imported by the agent."""
import argparse
import json
import os
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from .agents.hybrid import HybridAgent
from .agents.optimizer import candidates, valid
from .agents.strategy import BODIES, SCHEMA, SYSTEM, OpenAI
from .cli import load_env
from .client import ArenaClient
from .cost import closing_terms, total_cost
from .data import DataPackage
from .play import RemoteTable, hosted, play

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / "starter-kit" / ".local"
REPORTS = ROOT / "benchmarks"
AUTHORIZED = [f"case:P{n:02}" for n in (1, 2, 3, 4, 5, 7, 8, 10, 11, 18)]


def now():
    return datetime.now(UTC).isoformat()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def append(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def snapshot(label):
    client = ArenaClient(retries=0)
    me, board, cases = client.me(), client.leaderboard("practice"), client.cases("practice")
    # Store only our own team and the leader in the publishable leaderboard evidence.
    teams = board.get("teams", [])
    own = next((t for t in teams if t.get("team_name") == me.get("team_name")), None)
    leader = min(teams, key=lambda t: t.get("rank", float("inf"))) if teams else None
    result = {"timestamp": now(), "me": me, "team": own, "leader": leader,
              "case_count": board.get("cases"), "teams_count": len(teams),
              "gap": leader["total"] - own["total"] if leader and own else None}
    write(REPORTS / f"leaderboard_{label}.json", result)
    write(PRIVATE / "practice_cases.json", cases)
    print(json.dumps(result, ensure_ascii=True))


def package():
    configured = Path(os.environ.get("ARENA_DATA", ""))
    root = configured if (configured / "facts.json").exists() else ROOT / "data"
    return DataPackage(root)


def offline():
    cases = json.loads((PRIVATE / "practice_cases.json").read_text())
    results = []
    for case in cases:
        context_sizes = []

        def choose(system, user, context_sizes=context_sizes):
            context_sizes.append(len(user.encode()))
            assert context_sizes[-1] <= 12000
            context = json.loads(user)
            return {"package_order": list(range(len(context["packages"]))), "evidence": [],
                    "question": "priorities", "body": BODIES[0]}

        agent = HybridAgent(choose, package=package())
        agent.prepare(case)
        count = 0
        minimum = None
        for sid in case["suppliers"]:
            seed = {"unit_price": case["buyer"].get("current_unit_price")
                    or case["buyer"]["fallback_unit_price"]}
            offers = candidates(case, seed, {})
            assert offers and all(valid(case, t, complete=True) for t in offers)
            count += len(offers)
            value = min(total_cost(case, t) for t in offers)
            minimum = min(minimum, value) if minimum is not None else value
            intel = agent.intelligence.prepare(case, sid)
            facts = {**agent.intelligence.package.facts, **case.get("facts", {})}
            assert all(ref in facts for e in intel["evidence"] for ref in e["refs"])
        synthetic = {sid: [{"from": "supplier", "status": "open", "body": "Local economic fixture.",
                            "term_sheets": [{"term_sheet_id": f"fixture:{sid}", "terms": seed}]}]
                     for sid in case["suppliers"]}
        actions = agent.decide_many(case, synthetic)
        assert actions and all(valid(case, s["terms"], complete=True)
                               for a in actions for s in a["message"].get("term_sheets", []))
        assert not any(d.get("model_called") and d.get("fallback") for d in agent.diagnostics)
        results.append({"case_id": case["case_id"], "hosted_available": case.get("hosted"),
                        "mock_model_context_bytes": context_sizes,
                        "status": "offline economic fixture only", "valid_candidates": count,
                        "fixture_min_cost_excluding_relationship": minimum,
                        "supplier_behavior_tested": False, "score": None})
    write(REPORTS / "offline_cases.json", results)
    print(json.dumps({"offline_cases": len(results), "valid": True}))


def probe():
    cases = json.loads((PRIVATE / "practice_cases.json").read_text())
    case = cases[0]
    model = OpenAI()
    agent = HybridAgent(model, package())
    agent.prepare(case)
    sid = case["suppliers"][0]
    terms = closing_terms(case, {"unit_price": case["buyer"]["current_unit_price"] * 1.095})
    threads = {sid: [{"from": "supplier", "status": "open", "body": "Please review our price proposal.",
                     "term_sheets": [{"term_sheet_id": "offer:probe", "terms": terms}]}]}
    start = time.monotonic()
    decision = agent.decide(case, threads)
    row = {"timestamp": now(), "kind": "synthetic negotiation context, no Tacto session",
           "model": model.model, "effort": model.effort, "decision_s": time.monotonic() - start,
           "metrics": model.metrics, "valid_action": bool(decision), "diagnostics": agent.diagnostics}
    append(REPORTS / "model_probes.jsonl", row)
    print(json.dumps(row, ensure_ascii=True))


def batch_paths(batch="original"):
    if batch == "original":
        return PRIVATE / "sessions.jsonl", REPORTS, PRIVATE
    if batch == "revised_01":
        return PRIVATE / "revised_01_sessions.jsonl", REPORTS / batch, PRIVATE / batch
    raise ValueError("Unknown benchmark batch; additional batches need explicit authorization")


def forecast(batch="original"):
    journal, _, _ = batch_paths(batch)
    model = OpenAI()
    input_bound = 12000 + len((SYSTEM + json.dumps(SCHEMA)).encode()) + 512
    per_call = (input_bound * model.input_rate + model.max_tokens * model.output_rate) / 1e6
    remaining = max(0, 10 - len(records(journal)))
    expected_calls = remaining * int(os.environ.get("HYBRID_LLM_CALLS_PER_CASE", "2"))
    return {"remaining_sessions": remaining, "maximum_remaining_model_calls": expected_calls,
            "per_call_upper_usd": per_call, "remaining_upper_usd": per_call * expected_calls,
            "already_accounted_usd": model.spent(),
            "forecast_total_upper_usd": model.spent() + per_call * expected_calls}


def run(case_id, *, batch="original", approved=False, expected_case=None):
    journal, report_dir, trace_dir = batch_paths(batch)
    if batch != "original" and not approved:
        raise ValueError("Revised hosted sessions need fresh explicit approval; preparation is not execution")
    if case_id not in AUTHORIZED:
        raise ValueError("Only the ten authorized practice IDs may be benchmarked")
    uses = records(journal)
    if len(uses) >= 10 or case_id in {r["case_id"] for r in uses}:
        raise ValueError("Session authorization exhausted or case already attempted; no retry")
    # Refuse overlapping benchmark processes, including stale/crashed ones until manually audited.
    lock_path = PRIVATE / "benchmark.lock"
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with lock_path.open("x") as lock:
        lock.write(str(os.getpid()))
    try:
        # Re-read under the shared lock; never reserve using a stale pre-lock snapshot.
        uses = records(journal)
        if len(uses) >= 10 or case_id in {r["case_id"] for r in uses}:
            raise ValueError("Session authorization exhausted or case already attempted; no retry")
        forecast_ = forecast(batch)
        if forecast_["forecast_total_upper_usd"] > 5:
            raise ValueError("Full-coverage forecast exceeds $5; approval required")
        client = ArenaClient(retries=0)
        me = client.me()
        if me["practice"]["left"] < 1:
            raise ValueError("No team practice quota")
        cases = client.cases("practice")
        case = next(c for c in hosted(cases) if c["case_id"] == case_id)
        if expected_case is not None and case != expected_case:
            raise ValueError("Case changed since preparation; review and prepare again")
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain", "--", "starter-kit/arena_kit"],
                                         cwd=ROOT, text=True).strip()
        if status:
            raise ValueError("Commit tested runtime code before a hosted benchmark")
        model = OpenAI()
        agent = HybridAgent(model, package())
        agent.prepare(case)  # research before the supplier's clock starts
        table = RemoteTable(client, case)
        started = now()
        append(journal, {"case_id": case_id, "reserved_at": started, "commit": commit,
                         "model": model.model, "effort": model.effort})
        print(json.dumps({"starting": case_id, "session_slot": len(uses) + 1, "forecast": forecast_}), flush=True)
        result, error, replay = None, None, None
        wall = time.monotonic()
        state = {}
        try:
            result = play(table, case_id, agent)
        except Exception as exc:
            error = type(exc).__name__
        if table.session_id:
            try:
                state = client.session(table.session_id)
                replay = state.get("replay_url")
                if not result and state.get("status") == "ended":
                    result = state.get("result")
                # Private trace for post-run review, excluded from Git.
                write(trace_dir / f"{case_id.replace(':', '_')}_state.json", state)
            except Exception as exc:
                error = error or type(exc).__name__
        if replay and replay.startswith("/"):
            replay = os.environ["ARENA_URL"].rstrip("/") + replay
        result = {k: v for k, v in (result or {}).items() if k != "trace"}
        row = {"batch": batch, "case_id": case_id, "scenario": case["type"], "suppliers": case["suppliers"],
               "timestamp": started, "commit": commit, "model": model.model, "effort": model.effort,
               "status": "completed" if result.get("ended") else "failed", "result": result,
               "session_id": table.session_id, "replay_url": replay, "error": error,
               "buyer_timeouts": sum(m.get("move", {}).get("type") == "timeout"
                                     for m in state.get("moves", [])),
               "turns": state.get("rounds"), "wall_s": time.monotonic() - wall,
               "model_calls": model.metrics, "decisions": agent.diagnostics,
               "network_retries": 0, "session_attempt": len(uses) + 1}
        append(report_dir / "hosted_results.jsonl", row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
        return row
    finally:
        lock_path.unlink()


def report():
    rows = records(REPORTS / "hosted_results.jsonl")
    by_case = {r["case_id"]: r for r in rows}
    scores = [r["result"]["score"] for r in rows if isinstance(r["result"].get("score"), int | float)]
    calls = [c for r in rows for c in r["model_calls"]]
    times = [c["end_to_end_s"] for c in calls]
    usage = records(PRIVATE / "llm_usage.jsonl")
    finished = [r for r in usage if r["event"] == "finished"]
    stats = {"count": len(scores), "mean": statistics.mean(scores) if scores else None,
             "median": statistics.median(scores) if scores else None,
             "min": min(scores) if scores else None, "max": max(scores) if scores else None,
             "population_stdev": statistics.pstdev(scores) if scores else None,
             "deals": sum(bool(r["result"].get("deal")) for r in rows),
             "completed": sum(r["status"] == "completed" for r in rows),
             "valid_deals": sum(r["result"].get("must_haves_ok") is True for r in rows),
             "hosted_model_calls": len(calls), "hosted_model_failures": sum(c["fallback"] for c in calls),
             "hosted_latency_mean_s": statistics.mean(times) if times else None,
             "hosted_latency_max_s": max(times) if times else None,
             "all_input_tokens": sum(c.get("input_tokens", 0) for c in finished),
             "all_output_tokens": sum(c.get("output_tokens", 0) for c in finished),
             "all_reasoning_tokens": sum(c.get("reasoning_tokens") or 0 for c in finished),
             "all_estimated_cost_usd": sum(c.get("estimated_cost_usd") or 0 for c in finished),
             "all_accounted_upper_usd": OpenAI().spent()}
    write(REPORTS / "summary.json", stats)
    lines = ["# Benchmark report", "", f"Generated {now()}.", "",
             "Hosted practice is measured once per case. Offline fixtures and the scripted local simulator "
             "are not hosted results. Leaderboard uses best-per-case aggregation, not this run mean.", "",
             "| Case | Status | Score | Deal | C deal | Model / effort | Replay |",
             "|---|---|---:|---|---:|---|---|"]
    for case_id in AUTHORIZED:
        row = by_case.get(case_id)
        if not row:
            lines.append(f"| {case_id} | Not tested: pending authorization gates/budget | - | - | - | - | - |")
            continue
        r = row["result"]
        lines.append(f"| {case_id} | {row['status']} | {r.get('score')} | {r.get('deal')} | "
                     f"{r.get('c_deal')} | {row['model']} / {row['effort']} | "
                     f"[replay]({row.get('replay_url')}) |")
    lines += ["", "## Aggregate evidence", "", "```json", json.dumps(stats, indent=2), "```", "",
              "## Leaderboard", ""]
    for label in ("before", "after"):
        path = REPORTS / f"leaderboard_{label}.json"
        if path.exists():
            data = json.loads(path.read_text())
            lines += [f"{label}: {data['timestamp']}", "", "```json",
                      json.dumps(data, indent=2), "```", ""]
    p01 = by_case.get("case:P01", {}).get("result", {}).get("score")
    lines += ["## Baseline and limitations", "",
              f"Prior genuine naive P01 baseline: 0.5828313200135649. Hybrid P01: {p01}. "
              "Single runs are not controlled causal comparisons; no other measured naive/LLM baselines.", "",
              "Exact relationship charges require hidden supplier economics; runtime estimates use public "
              "supplier-specific should-cost and an explicitly uncertain financing assumption. "
              "No hidden c_best, board, rankings, or replay data enter the agent. "
              "Price-unit metadata is preserved; the published arena cost helper uses case units directly.", "",
              "Billing is estimated at verified Astra standard prices ($10/M input, $50/M output), "
              "conservatively without cache discounts. It is not an invoice. Timed-out/unknown calls retain "
              "their full reservation. See machine-readable call metrics for model IDs, effort and fallbacks.", "",
              "Nine data-only cases have economic fixtures in benchmarks/offline_cases.json; no supplier "
              "behavior or scores are claimed. No final session was started. See HYBRID_README.md for operations.",
              ""]
    (ROOT / "BENCHMARK_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(stats))


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["snapshot", "offline", "probe", "forecast", "run", "report"])
    ap.add_argument("--label", choices=["before", "after"], default="before")
    ap.add_argument("--case")
    ap.add_argument("--effort", choices=["high", "medium"], default="high")
    args = ap.parse_args()
    # Deliberate process-local override, recorded on every call; private .env is untouched.
    os.environ["LLM_EFFORT"] = args.effort
    os.environ["LLM_USAGE_PATH"] = str(PRIVATE / "llm_usage.jsonl")
    if args.command == "snapshot":
        snapshot(args.label)
    elif args.command == "offline":
        offline()
    elif args.command == "probe":
        probe()
    elif args.command == "forecast":
        print(json.dumps(forecast()))
    elif args.command == "run":
        run(args.case)
    else:
        report()


if __name__ == "__main__":
    main()
