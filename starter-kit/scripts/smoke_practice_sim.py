"""Run every published practice case against the local arena-sim contract model.

The hosted endpoint is used only to fetch case files when --fetch is given. Playing
the cases uses the in-process Sim class and opens no hosted sessions.
"""

import argparse
import json
import time
from pathlib import Path

from arena_kit.benchmark import LocalTable
from arena_kit.cli import agent_factory, load_env
from arena_kit.client import ArenaClient
from arena_kit.play import play


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path(".local/practice-cases.json"))
    parser.add_argument("--fetch", action="store_true", help="refresh public case files; no sessions opened")
    parser.add_argument("--data", default="../data")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    load_env()
    if args.fetch:
        cases = ArenaClient().cases("practice")
        args.cases.parent.mkdir(parents=True, exist_ok=True)
        args.cases.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    else:
        cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if len(cases) != 19 or len({c["case_id"] for c in cases}) != 19:
        raise SystemExit(f"expected 19 unique practice cases, got {len(cases)}")

    factory = agent_factory("buyer", args.data)
    records = []
    for case in cases:
        agent = factory()
        table = LocalTable(case, agent.research.facts)
        table.sim.no_clock = False
        started = time.time()
        try:
            result = play(table, case["case_id"], agent, deadline=started + 480)
            state = table.sim.sessions[table.session_id]
            record = {
                "case_id": case["case_id"],
                "hosted": case.get("hosted", False),
                "seconds": round(time.time() - started, 2),
                "rounds": sum(t["round"] for t in state["threads"].values()),
                "end_reason": state["end_reason"],
                "deal": result.get("deal"),
                "must_haves_ok": result.get("must_haves_ok"),
                "timeouts": sum(t["timeouts"] for t in state["threads"].values()),
                "score": result.get("score"),
            }
            record["passed"] = (
                record["seconds"] < 480
                and record["end_reason"] != "timeout"
                and record["timeouts"] == 0
                and record["must_haves_ok"] is not False
                and result.get("ended") is True
            )
        except Exception as exc:
            record = {"case_id": case["case_id"], "hosted": case.get("hosted", False),
                      "passed": False, "error": f"{type(exc).__name__}: {exc}"}
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    if not all(r["passed"] for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
