"""Repeatable, entirely in-process comparison. No arena client, credentials, or model calls.

The supplier scripts are synthetic. Their scores must never be compared with hosted scores.
Historical code is read from an explicit local Git commit, never downloaded or checked out.
"""
import argparse
import copy
import importlib.util
import json
import re
import subprocess
import sys
import threading
import types
from datetime import UTC, datetime
from pathlib import Path

from .agents.hybrid import HybridAgent
from .client import ArenaError
from .play import play
from .sim import Fail, Sim, load_cases

ROOT = Path(__file__).resolve().parents[2]


def baseline(revision):
    if not re.fullmatch(r"[0-9a-f]{7,40}", revision):
        raise ValueError("Use a local commit hash, not a branch or shell expression")
    package_name = "arena_kit._local_baseline"
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package

    def load(name, path):
        source = subprocess.run(["git", "show", f"{revision}:{path}"], cwd=ROOT,
                                check=True, capture_output=True, text=True, encoding="utf-8-sig").stdout
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
        sys.modules[name] = module
        exec(compile(source, f"git:{revision}/{path}", "exec"), module.__dict__)
        return module

    for name in ("optimizer", "intelligence", "strategy", "decision", "hybrid"):
        module = load(f"{package_name}.{name}", f"starter-kit/arena_kit/agents/{name}.py")
    runner = load("arena_kit._local_baseline_play", "starter-kit/arena_kit/play.py")
    return module.HybridAgent, runner.play


class ScriptedSim(Sim):
    """Stress paths, not fitted reproductions of any hosted supplier."""
    def __init__(self, cases, trajectory=None):
        super().__init__(cases)
        self.trajectory = trajectory

    def _answer(self, session, thread, message, sheets):
        if self.trajectory is None:
            return super()._answer(session, thread, message, sheets)
        i = min(thread["round"] - 1, len(self.trajectory) - 1)
        price = round(thread["opening"] * self.trajectory[i], 2)
        accepted = [t for t in sheets if t["unit_price"] >= price]
        if accepted:
            best = max(accepted, key=lambda t: t["unit_price"])
            return self._mail(session, thread, "agreed", best, "We agree.", ["quote.pdf"])
        status = "final_offer" if thread["round"] >= 5 else "open"
        return self._mail(session, thread, status, {"unit_price": price},
                          "Please review our current offer.", ["quote.pdf"])


class LocalTable:
    """Same runner interface, direct calls to an isolated Sim instance; no sockets."""
    def __init__(self, case, trajectory=None):
        self.state = ScriptedSim({case["case_id"]: copy.deepcopy(case)}, trajectory)
        self.lock = threading.Lock()
        self.session_id = None

    def invoke(self, method, *args):
        with self.lock:
            try:
                return copy.deepcopy(method("local-evaluation", *args))
            except Fail as exc:
                raise ArenaError(exc.status, exc.detail) from exc

    def open(self, case_id):
        r = self.invoke(self.state.open, case_id)
        self.session_id = r["session_id"]
        return r["case"], r["threads"]

    def send(self, sid, message):
        return self.invoke(self.state.message, self.session_id, sid, message)

    def close(self, sid, message):
        return self.send(sid, message)["result"]

    def attachment(self, attachment_id):
        return self.invoke(self.state.attachment, self.session_id, attachment_id)[0]

    def result(self):
        return self.invoke(self.state.state, self.session_id)["result"]


def compare(revision="08002e0"):
    old_agent, old_play = baseline(revision)
    scripts = {"standard_simulator": None,
               "plateau_then_withdrawal": [0.95, 0.95, 0.95, 1.02, 1.05],
               "delayed_concession": [1.0, 1.0, 0.92, 0.90, 0.90],
               "gradual_concessions": [0.98, 0.96, 0.94, 0.92, 0.90]}
    rows = []
    for original in load_cases().values():
        for script, trajectory in scripts.items():
            for interest in (0.0, 0.08, 0.20):
                case = copy.deepcopy(original)
                case["buyer"]["interest_rate"] = interest
                row = {"case": case["case_id"], "script": script, "buyer_interest": interest}
                for label, agent_type, runner in (("before", old_agent, old_play), ("after", HybridAgent, play)):
                    table = LocalTable(case, trajectory)
                    result = runner(table, case["case_id"], agent_type())
                    session = table.state.sessions[table.session_id]
                    row[label] = {k: result[k] for k in ("deal", "must_haves_ok", "c_deal", "c_alt")}
                    row[label]["rounds"] = sum(t["round"] for t in session["threads"].values())
                    row[label]["timeouts"] = sum(len(t["late"]) for t in session["threads"].values())
                for label in ("before", "after"):
                    r = row[label]
                    r["realized_cost"] = r["c_deal"] if r["deal"] and r["must_haves_ok"] else r["c_alt"]
                row["cost_saved"] = round(row["before"]["realized_cost"] - row["after"]["realized_cost"], 2) if all(
                    row[k]["realized_cost"] is not None for k in ("before", "after")) else None
                rows.append(row)
    savings = [r["cost_saved"] for r in rows if r["cost_saved"] is not None]
    return {"timestamp": datetime.now(UTC).isoformat(), "baseline_commit": revision,
            "scope": "36 synthetic local fixtures, deterministic agent; NOT hosted supplier performance",
            "hosted_sessions": 0, "model_calls": 0, "rows": rows,
            "summary": {"fixtures": len(rows), "lower_cost": sum(v > 0.01 for v in savings),
                        "equal_cost": sum(abs(v) <= 0.01 for v in savings),
                        "higher_cost": sum(v < -0.01 for v in savings),
                        "after_valid_deals": sum(r["after"]["deal"] and r["after"]["must_haves_ok"] for r in rows),
                        "after_no_deals": sum(not r["after"]["deal"] for r in rows),
                        "after_timeouts": sum(r["after"]["timeouts"] for r in rows)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="08002e0")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks" / "local_comparison.json")
    args = parser.parse_args()
    result = compare(args.baseline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
