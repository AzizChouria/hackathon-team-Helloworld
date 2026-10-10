"""Bounded hosted practice experiments with replay links and reproducible result files."""

import hashlib
import json
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from .play import RemoteTable, hosted, play


def evaluate(client, new_agent, case_ids=None, parallel=5, seconds=390, out=None, agent_name=None):
    if seconds <= 90:
        raise ValueError("seconds must exceed the 90-second closing reserve")
    cases = {c["case_id"]: c for c in hosted(client.cases("practice"))}
    ids = list(dict.fromkeys(case_ids or cases))
    if missing := set(ids) - cases.keys():
        raise ValueError(f"not hosted practice cases: {sorted(missing)}")
    remaining = client.me().get("practice", {}).get("left")
    if remaining is not None and len(ids) > remaining:
        raise ValueError(f"experiment needs {len(ids)} sessions; {remaining} remain")
    digest = hashlib.sha256()
    root = Path(__file__).parent
    for source in sorted(root.rglob("*.py")):
        digest.update(str(source.relative_to(root)).encode())
        digest.update(source.read_bytes())
    report = {
        "set": "practice",
        "case_ids": ids,
        "seconds_per_case": seconds,
        "runs": [],
        "started_at": datetime.now(UTC).isoformat(),
        "agent": agent_name,
        "source_sha256": digest.hexdigest(),
    }
    if not ids:
        raise ValueError("no hosted practice cases available")

    def save():
        if out:
            path = Path(out)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temp.replace(path)

    def one(cid):
        agent = new_agent()
        if hasattr(agent, "prepare"):
            agent.prepare(cases[cid])
        table = RemoteTable(client)
        start = time.time()
        try:
            result = play(table, cid, agent, deadline=start + seconds)
            state = client.session(table.session_id)
            claim_counts = Counter(
                claim["result"]
                for turn in (state.get("result") or {}).get("trace", [])
                for claim in turn.get("move", {}).get("claim_results", [])
            )
            return {
                "case_id": cid,
                "session_id": table.session_id,
                "seconds": round(time.time() - start, 2),
                "rounds": state.get("rounds"),
                "result": result,
                "replay_url": state.get("replay_url"),
                "claim_counts": dict(claim_counts),
                "decisions": getattr(agent, "trace", []),
                "model_calls": {
                    "succeeded": getattr(agent, "model_successes", 0),
                    "fell_back": getattr(agent, "model_fallbacks", 0),
                },
            }
        except Exception as exc:
            # Persist partial runs. An error is a zero in the experiment's aggregate.
            return {
                "case_id": cid,
                "session_id": table.session_id,
                "seconds": round(time.time() - start, 2),
                "error": f"{type(exc).__name__}: {exc}",
                "model_calls": {
                    "succeeded": getattr(agent, "model_successes", 0),
                    "fell_back": getattr(agent, "model_fallbacks", 0),
                },
            }

    # A broken model must not silently spend an entire hosted batch on fallback.
    # Keep the preflight outside session timers and fail before creating a table.
    probe = new_agent()
    if hasattr(probe, "preflight"):
        try:
            report["model_preflight"] = probe.preflight(cases[ids[0]])
        except Exception as exc:
            report["model_preflight"] = {"ok": False, "error": str(exc)}
            save()
            raise
    save()
    with ThreadPoolExecutor(max_workers=min(10, max(1, parallel))) as pool:
        futures = [pool.submit(one, cid) for cid in ids]
        for future in as_completed(futures):
            run = future.result()
            report["runs"].append(run)
            result = run.get("result", {})
            print(
                f"{run['case_id']} score={result.get('score')} deal={result.get('deal')} "
                f"rounds={run.get('rounds')} model={run['model_calls']['succeeded']}/"
                f"{run['model_calls']['succeeded'] + run['model_calls']['fell_back']} "
                f"seconds={run['seconds']} replay={run.get('replay_url')} error={run.get('error')}",
                flush=True,
            )
            save()
    report["mean_score"] = statistics.mean((r.get("result", {}).get("score") or 0) for r in report["runs"])
    report["practice_remaining"] = client.practice_remaining
    save()
    return report
