"""Paired offline evaluation. Never loads credentials or calls a hosted/model endpoint."""
import argparse
import hashlib
import json
import os
import statistics
from datetime import UTC, datetime
from pathlib import Path

from . import buyer_stress
from .agents.buyer import BuyerAgent
from .agents.combined import CombinedAgent
from .agents.hybrid import HybridAgent
from .agents.proposals import check_terms
from .cost import complete_offer
from .data import DataPackage


def public_fixtures(cases, data):
    """Validate public menus with invented quotes; never simulate actual supplier behaviour."""
    rows = []
    for case in cases:
        agent = CombinedAgent(package=DataPackage(data))
        seed = complete_offer(case, {"unit_price": case["buyer"].get("current_unit_price")
                                    or case["buyer"]["fallback_unit_price"]})
        threads = {sid: [{"from": "supplier", "status": "open", "body": "Synthetic public-case fixture.",
                          "term_sheets": [{"term_sheet_id": "synthetic:" + sid, "terms": seed}]}]
                   for sid in case["suppliers"]}
        decision = agent.decide(case, threads)
        counts = {}
        agent._ceiling = float("inf")
        for sid, events in threads.items():
            packages = agent.packages(case, sid, events)
            for terms in packages:
                check_terms(case, terms, {})
            if not packages:
                raise ValueError(f"No valid fixture package for {case['case_id']} / {sid}")
            claims = agent.unused_evidence(case, sid, threads)
            cited = (ref for e in claims for ref in e.refs)
            if not all(agent.research.fact(case, ref) or ref.startswith("synthetic:") for ref in cited):
                raise ValueError("Unverified fixture citation")
            counts[sid] = len(packages)
        rows.append({"case_id": case["case_id"], "hosted_available": case.get("hosted"),
                     "supplier_valid_package_counts": counts,
                     "decision": decision["message"].get("action", {}).get("type", "counter"),
                     "score": None, "supplier_behavior_tested": False})
    return {"environment": "Offline public-case economics with invented supplier opening quotes",
            "hosted_sessions": 0, "model_calls": 0, "cases": len(rows),
            "supplier_count": sum(len(r["supplier_valid_package_counts"]) for r in rows), "runs": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--public-cases", type=Path, help="Local cached public cases JSON; economics only")
    parser.add_argument("--data", default="../data")
    args = parser.parse_args()
    if args.public_cases:
        report = public_fixtures(json.loads(args.public_cases.read_text()), args.data)
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "runs"}))
        return
    # Additional seed frozen before inspecting any combined-policy scores.
    buyer_stress.SEEDS["transfer"] = 20261011
    os.environ["HYBRID_PROPOSAL_MODE"] = "legacy"
    os.environ["HYBRID_OFFLINE"] = "1"
    report = {"generated_at": datetime.now(UTC).isoformat(), "environment": "offline synthetic",
              "limitation": "Local scripted scores are not hosted scores or evidence of beating another team.",
              "runs": []}
    for split in ("dev", "holdout", "transfer"):
        for label, cls in (("imported_buyer", BuyerAgent), ("previous_hybrid", HybridAgent),
                           ("combined", CombinedAgent)):
            result = buyer_stress.evaluate(split, cls)
            for row in result["runs"]:
                row.pop("decisions", None)  # no raw negotiation transcripts
            result["agent"] = label
            result["median_score"] = statistics.median(r["result"]["score"] for r in result["runs"])
            result["valid_deals"] = sum(bool(r["result"].get("deal") and r["result"].get("must_haves_ok"))
                                       for r in result["runs"])
            report["runs"].append(result)
            summary = {k: v for k, v in result.items() if k not in {"runs", "by_style", "by_family"}}
            print(json.dumps(summary), flush=True)
    report["source_sha256"] = {
        str(p.relative_to(Path(__file__).parent)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in Path(__file__).parent.rglob("*.py")
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
