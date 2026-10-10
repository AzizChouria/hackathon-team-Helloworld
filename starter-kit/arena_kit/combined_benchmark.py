"""Explicitly authorized ten-case combined practice pass; never imported by the agent."""
import argparse
import json
import os
import statistics
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from . import benchmark as bench
from .agents.combined import CombinedAgent
from .cli import load_env
from .client import ArenaClient
from .play import RemoteTable, hosted, play
from .revised_benchmark import identity, team_snapshot

BATCH = "combined_01"
ORDER = [f"case:P{n:02}" for n in (1, 2, 3, 4, 5, 7, 8, 10, 11, 18)]
CONFIG = {"HYBRID_PROPOSAL_MODE": "combined", "HYBRID_TACTICAL_LLM": "0",
          "HYBRID_OFFLINE": "1", "HYBRID_RESPONSE_GUARD_S": "35"}
AUTHORIZATION = "User: lets test all suppliers online and see what happens in the leaderboard; one new ten-case pass"


def configure():
    os.environ.update(CONFIG)
    missing = [k for k in ("ARENA_URL", "ARENA_API_KEY") if not os.getenv(k)]
    if missing:
        raise ValueError("Missing variables: " + ", ".join(missing))
    if os.environ["ARENA_URL"].rstrip("/") != "https://arena.tacto.ai":
        raise ValueError("Practice benchmark restricted to official Arena")


def paths():
    return bench.PRIVATE / f"{BATCH}_sessions.jsonl", bench.REPORTS / BATCH, bench.PRIVATE / BATCH


def budget_accounted():
    records = bench.records(bench.PRIVATE / "llm_usage.jsonl")
    settled = {r["call_id"]: r for r in records if r["event"] == "finished"}
    return sum(settled.get(r["call_id"], r)["charged_upper_usd"] for r in records if r["event"] == "reserved")


def reserve(case_id, frozen):
    journal, _, _ = paths()
    uses = bench.records(journal)
    if case_id not in ORDER or len(uses) >= 10 or case_id in {r["case_id"] for r in uses}:
        raise ValueError("Case unauthorized, already attempted, or ten-session limit exhausted")
    entry = {"case_id": case_id, "reserved_at": bench.now(), **frozen, "batch": BATCH,
             "session_slot": len(uses) + 1, "model": None, "effort": None}
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return entry


def healthy(row):
    return (row["status"] == "completed" and not row.get("error") and not row.get("buyer_timeouts")
            and not (row["result"].get("deal") and not row["result"].get("must_haves_ok")))


class MeasuredAgent(CombinedAgent):
    def __init__(self, package):
        super().__init__(package=package)
        self.decision_times = []

    def decide_ready(self, *args):
        start = time.monotonic()
        try:
            return super().decide_ready(*args)
        finally:
            self.decision_times.append(time.monotonic() - start)


def one(client, case, reservation):
    _, _, private = paths()
    agent = MeasuredAgent(bench.package())
    agent.prepare(case)
    table = RemoteTable(client, case)
    started = time.monotonic()
    result, state, error = {}, {}, None
    try:
        result = play(table, case["case_id"], agent, deadline=time.time() + 480)
    except Exception as exc:
        error = {"type": type(exc).__name__, "http_status": getattr(exc, "status", None),
                 "operation": getattr(exc, "operation", None)}
    if table.session_id:
        try:
            state = client.session(table.session_id)
            bench.write(private / f"{case['case_id'].replace(':', '_')}_state.json", state)
            if not result and state.get("status") == "ended":
                result = state.get("result") or {}
        except Exception as exc:
            error = error or {"type": type(exc).__name__, "operation": "read_final_state"}
    replay = state.get("replay_url")
    if replay and replay.startswith("/"):
        replay = os.environ["ARENA_URL"].rstrip("/") + replay
    result = {k: v for k, v in (result or {}).items() if k != "trace"}
    return {**reservation, "scenario": case["type"], "suppliers": case["suppliers"],
            "session_id": table.session_id, "replay_url": replay, "result": result,
            "status": "completed" if result.get("ended") else "failed", "error": error,
            "wall_s": time.monotonic() - started, "turns": state.get("rounds"),
            "buyer_timeouts": sum(m.get("move", {}).get("type") == "timeout" for m in state.get("moves", [])),
            "decision_times_s": agent.decision_times, "decisions": agent.diagnostics,
            "model_calls": [], "model_tokens": 0, "estimated_api_cost_usd": 0, "network_retries": 0}


def summarize():
    journal, reports, _ = paths()
    rows = bench.records(reports / "hosted_results.jsonl")
    scores = [r["result"]["score"] for r in rows if isinstance(r["result"].get("score"), int | float)]
    times = [t for r in rows for t in r["decision_times_s"]]
    result = {"batch": BATCH, "timestamp": bench.now(), "agent": "combined", "model": None, "effort": None,
              "attempted": len(bench.records(journal)), "completed": sum(r["status"] == "completed" for r in rows),
              "mean_completed_score": statistics.mean(scores) if scores else None,
              "full_10_case_mean": statistics.mean(scores) if len(scores) == 10 else None,
              "median": statistics.median(scores) if scores else None,
              "min": min(scores) if scores else None, "max": max(scores) if scores else None,
              "population_stdev": statistics.pstdev(scores) if scores else None,
              "valid_deals": sum(bool(r["result"].get("deal") and r["result"].get("must_haves_ok")) for r in rows),
              "buyer_timeouts": sum(r["buyer_timeouts"] for r in rows),
              "mean_decision_s": statistics.mean(times) if times else None,
              "max_decision_s": max(times) if times else None, "model_calls": 0, "estimated_api_cost_usd": 0,
              "not_tested": [c for c in ORDER if c not in {r["case_id"] for r in rows}]}
    bench.write(reports / "summary.json", result)
    return result


def run(approved=False):
    if not approved:
        raise ValueError("Explicit authorization required before any network/session activity")
    configure()
    journal, reports, _ = paths()
    lock_path = bench.PRIVATE / "benchmark.lock"
    bench.PRIVATE.mkdir(parents=True, exist_ok=True)
    with lock_path.open("x") as lock:
        lock.write(str(os.getpid()))
    client = None
    try:
        uses = bench.records(journal)
        rows = bench.records(reports / "hosted_results.jsonl")
        if len({r["case_id"] for r in uses}) != len(uses) or len(uses) > 10:
            raise ValueError("Corrupt or exhausted journal")
        if {r["case_id"] for r in uses} != {r["case_id"] for r in rows} or any(not healthy(r) for r in rows):
            raise ValueError("Unresolved or failed prior attempt; no automatic recreation")
        frozen = identity()
        plan_path = bench.PRIVATE / f"{BATCH}_plan.json"
        client = ArenaClient(retries=0)
        snapshot = team_snapshot(client)
        cases = {c["case_id"]: c for c in hosted(client.cases("practice"))}
        if not set(ORDER) <= set(cases) or snapshot["quota"]["left"] < 10 - len(uses):
            raise ValueError("Hosted case availability or team quota insufficient")
        if plan_path.exists():
            plan = json.loads(plan_path.read_text())
            if any(plan[k] != v for k, v in frozen.items()) or plan["configuration"] != CONFIG:
                raise ValueError("Frozen code/data/configuration changed")
            if plan["cases"] != {c: cases[c] for c in ORDER}:
                raise ValueError("Frozen public cases changed")
        else:
            if uses:
                raise ValueError("Journal exists without frozen plan")
            plan = {**frozen, "configuration": CONFIG, "authorization": AUTHORIZATION, "prepared_at": bench.now(),
                    "order": ORDER, "parallel": 2, "cases": {c: cases[c] for c in ORDER},
                    "openai_batch_forecast_usd": 0, "already_accounted_usd": budget_accounted()}
            bench.write(plan_path, plan)
            bench.write(reports / "readiness.json", {k: v for k, v in plan.items() if k != "cases"})
            bench.write(reports / "leaderboard_before.json", snapshot)
        gate = threading.Event()

        def launch(case_id):
            if identity() != frozen:
                raise ValueError("Code/data changed during benchmark")
            if client.me()["practice"]["left"] < 1:
                raise ValueError("Team practice quota exhausted")
            reservation = reserve(case_id, frozen)
            print(json.dumps({"starting": case_id, "slot": reservation["session_slot"]}), flush=True)
            return reservation

        def collect(row):
            bench.append(reports / "hosted_results.jsonl", row)
            summarize()
            print(json.dumps({"completed": row["case_id"], "score": row["result"].get("score"),
                              "deal": row["result"].get("deal"), "error": row["error"],
                              "seconds": round(row["wall_s"], 2), "replay": row["replay_url"]}), flush=True)
            if not healthy(row):
                gate.set()

        missing = [c for c in ORDER if c not in {r["case_id"] for r in uses}]
        # Verify the first hosted case before scheduling at most two others at once.
        if not uses and missing:
            first = missing.pop(0)
            collect(one(client, cases[first], launch(first)))
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = {}
            while pending or missing and not gate.is_set():
                while missing and len(pending) < 2 and not gate.is_set():
                    c = missing.pop(0)
                    pending[pool.submit(one, client, cases[c], launch(c))] = c
                if pending:
                    done, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                    for future in done:
                        del pending[future]
                        collect(future.result())
        if gate.is_set():
            raise ValueError("Stopped scheduling after failed/late/invalid case; inspect saved results")
    finally:
        if client:
            try:
                bench.write(reports / "leaderboard_after.json", team_snapshot(client))
            finally:
                client.http.close()
        lock_path.unlink()
        print(json.dumps(summarize()), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-approved", action="store_true")
    args = parser.parse_args()
    load_env()
    run(args.execute_approved)


if __name__ == "__main__":
    main()
