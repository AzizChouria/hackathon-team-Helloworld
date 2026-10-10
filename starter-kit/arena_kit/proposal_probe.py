"""Explicitly paid OpenAI-only smoke test. No hosted arena client or session is used."""
import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from .agents.hybrid import HybridAgent
from .agents.strategy import OpenAI
from .cli import load_env
from .cost import complete_offer
from .sim import load_cases


def fixtures():
    cases = load_cases()
    single = copy.deepcopy(cases["case:S01"])
    multi = copy.deepcopy(cases["case:S03"])
    multi.update(case_id="synthetic:RFQ", type="rfq", title="Synthetic two-supplier API test",
                 suppliers=["synthetic:A", "synthetic:B"])
    multi["negotiable"].append("index_clause")
    multi["fixed_terms"].pop("index_clause", None)
    multi["term_options"]["index_clause"] = [None, {
        "series": "SYNTHETIC", "material_share": .3, "deadband_pct": 5.0, "base_month": "2026-08"}]
    return [single, multi]


def run(output):
    load_env()
    model = OpenAI()
    before = model.spent()
    results = []
    for case in fixtures():
        # These are invented opening quotes for API validation, never supplier results.
        terms = complete_offer(case, {"unit_price": round(case["buyer"]["current_unit_price"] * 1.1, 2)})
        threads = {sid: [{"from": "sales", "status": "open", "body":
                         "Synthetic quote. Earlier payment would help; discuss reciprocal price savings.",
                         "term_sheets": [{"term_sheet_id": f"synthetic:{i}", "terms": terms}]}]
                   for i, sid in enumerate(case["suppliers"])}
        agent = HybridAgent(model, proposal_mode="model")
        agent.max_calls = 1  # no repair calls; exactly one attempt per fixture at most
        offset = len(model.metrics)
        moves = agent.decide_many(case, threads)
        results.append({"fixture": case["case_id"], "supplier_count": len(threads),
                        "validated_packages": sum(len(m["message"].get("term_sheets", [])) for m in moves),
                        "diagnostics": agent.diagnostics, "api_metrics": model.metrics[offset:]})
    report = {"timestamp": datetime.now(UTC).isoformat(), "kind": "openai_only_synthetic_smoke",
              "hosted_sessions": 0, "score": None, "model": model.model, "effort": model.effort,
              "max_output_tokens": model.max_tokens, "timeout_s": model.timeout,
              "estimated_cost_usd": model.spent() - before, "cumulative_budget_charge_usd": model.spent(),
              "limitation": "Tests schema and proposal validity, not supplier acceptance or negotiation quality.",
              "results": results}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return all(r["validated_packages"] and r["diagnostics"] and not r["diagnostics"][-1]["fallback"] for r in results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Authorize up to two paid API calls within shared budget")
    parser.add_argument("--output", type=Path, default=Path(".local/model_proposal_probe.json"))
    args = parser.parse_args()
    if not args.live:
        parser.error("Use --live explicitly; ordinary unit tests never call OpenAI")
    if not run(args.output):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
