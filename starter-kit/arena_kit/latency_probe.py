"""Four bounded model-only probes on public cached data; never opens an arena session."""
import argparse
import copy
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .agents import proposals
from .agents.hybrid import HybridAgent
from .agents.optimizer import standing_offers
from .agents.strategy import OpenAI
from .benchmark import PRIVATE, package
from .cli import load_env
from .cost import complete_offer

ORDER = [("case:P07", "high"), ("case:P07", "medium"), ("case:P05", "medium"), ("case:P08", "medium")]
SETTINGS = {"LLM_MODEL": "gpt-6-astra", "LLM_ENDPOINT": "responses", "LLM_TIMEOUT_S": "22",
            "LLM_MAX_OUTPUT_TOKENS": "2400", "LLM_MAX_INPUT_BOUND": "19000", "LLM_BUDGET_USD": "5",
            "LLM_INPUT_USD_PER_M": "10", "LLM_OUTPUT_USD_PER_M": "50", "HYBRID_PROPOSAL_MODE": "model"}


def run(output):
    load_env()
    if output.exists():
        raise ValueError("Preserve previous probe evidence; choose a new output path")
    os.environ.update(SETTINGS)
    os.environ["LLM_USAGE_PATH"] = str(PRIVATE / "llm_usage.jsonl")
    cases = {c["case_id"]: c for c in json.loads((PRIVATE / "practice_cases.json").read_text())}
    os.environ["LLM_EFFORT"] = "high"
    before = OpenAI().spent()
    # Reserve worst-case room for these four probes AND eight calls in the two unused hosted slots.
    upper = (19000 * 10 + 2400 * 50) / 1e6
    if before + 12 * upper > 5:
        raise ValueError("Probe forecast would consume the budget reserved for remaining hosted slots")
    source = b"".join((Path(__file__).parent / "agents" / f"{name}.py").read_bytes()
                      for name in ("hybrid", "proposals", "strategy", "intelligence"))
    report = {"timestamp": datetime.now(UTC).isoformat(), "kind": "cached_public_data_synthetic_quotes",
              "source_sha256": hashlib.sha256(source).hexdigest(), "settings": SETTINGS, "hosted_sessions": 0,
              "score": None, "budget_before_usd": before, "probe_upper_usd": 4 * upper,
              "limitation": "Single samples, invented quotes and replies; no supplier acceptance or score measured.",
              "results": []}
    for cid, effort in ORDER:
        os.environ["LLM_EFFORT"] = effort
        case = copy.deepcopy(cases[cid])
        model = OpenAI()
        agent = HybridAgent(model, package(), proposal_mode="model")
        agent.max_calls = 1  # one call only, no repair or recovery for this latency measurement
        agent.prepare(case)
        price = case["buyer"].get("current_unit_price") or case["buyer"]["fallback_unit_price"]
        terms = complete_offer(case, {"unit_price": round(price * 1.1, 2)})
        threads = {sid: [{"from": "sales", "status": "open",
                         "body": "Synthetic opening quote for API testing. Please discuss payment, volume "
                                 "and delivery trade-offs for a commercially workable agreement.",
                         "term_sheets": [{"term_sheet_id": "synthetic:quote", "terms": terms}]}]
                   for sid in case["suppliers"]}
        estimates = agent._estimates(case, threads)
        context, _ = proposals.context(case, threads, agent.intelligence, set(), estimates,
                                       standing_offers(case, threads, estimates))
        encoded = proposals.compact(context)
        schema = proposals.response_schema(case, threads)
        context_hash = hashlib.sha256((encoded + json.dumps(schema)).encode()).hexdigest()
        actions = agent.decide_many(case, threads)
        row = {"case_context": cid, "effort": effort, "supplier_count": len(threads),
               "context_bytes": len(encoded.encode()), "context_schema_sha256": context_hash,
               "valid_packages": sum(len(a["message"].get("term_sheets", [])) for a in actions),
               "diagnostics": agent.diagnostics, "calls": model.metrics}
        report["results"].append(row)
        report["budget_after_usd"] = model.spent()
        report["accounted_probe_usd"] = model.spent() - before
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(row), flush=True)
    print(json.dumps({k: v for k, v in report.items() if k != "results"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(".local/latency_probe.json"))
    args = parser.parse_args()
    if not args.live:
        parser.error("Explicit --live required for up to four paid OpenAI-only calls")
    run(args.output)


if __name__ == "__main__":
    main()
