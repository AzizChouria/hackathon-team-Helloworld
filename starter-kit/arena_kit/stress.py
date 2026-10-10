"""Frozen synthetic negotiation exercises: no network, credentials, or language model.

The supplied simulator teaches the API and has one fixed concession schedule. These
exercises add private term costs, different concession styles and new case economics.
They measure local behaviour only; they do not approximate a hosted score statistically.
Private profiles and the exhaustive scoring oracle never enter the agent's input.
"""

import argparse
import copy
import hashlib
import inspect
import itertools
import json
import math
import random
import statistics
import time
from pathlib import Path

from .agents import BuyerAgent
from .benchmark import LocalTable
from .cost import closing_terms, cost_breakdown, must_haves_ok, score, total_cost
from .play import play
from .sim import Sim, load_cases

VERSION = 1
SEEDS = {"dev": 1103, "holdout": 7607}
FAMILIES = ("price", "renewal", "rfq", "quality", "capacity", "index")
STYLES = ("steady", "late", "reciprocal", "impatient")


def scenarios(split):
    """Two variants per family/style, with a separate fixed seed for the holdout."""
    rng = random.Random(SEEDS[split])
    templates = load_cases()
    out = []
    for family, style, variant in itertools.product(FAMILIES, STYLES, range(2)):
        tag = hashlib.sha256(f"{SEEDS[split]}:{family}:{style}:{variant}".encode()).hexdigest()[:10]
        source = (
            "case:S02" if family in {"rfq", "capacity"}
            else "case:S03" if family in {"renewal", "index"} else "case:S01"
        )
        case = copy.deepcopy(templates[source])
        case.update(case_id=f"case:L{tag}", title="Local procurement exercise", parts=[], refs=[], facts={})
        case["briefing"] = "Synthetic local exercise; use the requirements and supplier correspondence."
        case["suppliers"] = [f"sup:L{tag}{i}" for i in range(3 if family == "rfq" else 1)]
        need, price = rng.randrange(3000, 19000, 500), rng.choice([12.5, 37.5, 125, 270])
        buyer = case["buyer"]
        buyer.update(
            need_per_year=need,
            current_unit_price=price,
            fallback_unit_price=round(price * rng.uniform(1.12, 1.3), 2),
            interest_rate=rng.choice([0.05, 0.08, 0.12]),
            reference_payment_days=60,
            cost_per_defect=price * 2,
            late_cost_per_day=price * need * 0.003,
            freight_eur_per_unit={"EXW": price * 0.025, "FCA": price * 0.015, "DAP": 0},
            alternative={"kind": "none", "terms": {}},
            must_haves=[],
        )
        case["fixed_terms"]["volume_per_year"] = need
        case["round_limit"] = 12

        def menu(field, values, case=case):
            if field not in case["negotiable"]:
                case["negotiable"].append(field)
            case["fixed_terms"].pop(field, None)
            case["term_options"][field] = values

        if family == "quality":
            buyer["category_goal"] = "quality_first"
            case["negotiable"].remove("payment_days")
            case["term_options"].pop("payment_days")
            case["fixed_terms"]["payment_days"] = 60
            menu("ppm_commitment", [300, 800, 1500, 3000])
            menu("chargeback_eur_per_complaint", [0, price, price * 2])
            buyer["must_haves"] = [{"field": "ppm_commitment", "op": "<=", "value": 1500}]
        if family in {"renewal", "capacity", "index"}:
            menu("contract_months", [12, 24, 36])
        if family == "capacity":
            buyer["category_goal"] = "secure_supply"
            menu("volume_per_year", [int(need * 0.75), need, int(need * 1.2)])
            buyer["must_haves"] = [
                {"field": "volume_per_year", "op": ">=", "value": need},
                {"field": "lead_time_days", "op": "<=", "value": 42},
            ]
        if family == "rfq":
            buyer["must_haves"] = [{"field": "lead_time_days", "op": "<=", "value": 42}]
        if family == "index":
            buyer["index_paths"] = {"LOCAL-MATERIAL": rng.choice([-0.15, -0.08, 0.1])}
            menu("index_clause", [None, *[
                {"series": "LOCAL-MATERIAL", "material_share": share, "deadband_pct": 3, "base_month": "2026-01"}
                for share in (0.25, 0.5)
            ]])
        profiles = {
            sid: {
                "style": style,
                "floor_ratio": rng.uniform(0.78, 0.94),
                "final_round": rng.randint(3, 5) if style == "impatient" else rng.randint(6, 9),
                "finance_rate": rng.uniform(0.07, 0.3),
                "duration_discount": rng.uniform(0.005, 0.025),
                "index_discount": rng.uniform(0.005, 0.025),
                "quality_premium": rng.uniform(0.01, 0.05),
            }
            for sid in case["suppliers"]
        }
        out.append({"case": case, "profiles": profiles, "family": family, "style": style})
    return out


def reservation(case, profile, opening, terms):
    """Private supplier unit-price floor; separate from the buyer cost calculation."""
    t = closing_terms(case, terms)
    price = opening * profile["floor_ratio"]
    price *= 1 + profile["finance_rate"] * (t["payment_days"] - 30) / 360
    price -= opening * profile["duration_discount"] * min(2, max(0, t["contract_months"] / 12 - 1))
    if t.get("index_clause"):
        price -= opening * profile["index_discount"]
    price += case["buyer"]["freight_eur_per_unit"]["EXW"] - case["buyer"]["freight_eur_per_unit"][t["incoterm"]]
    price += opening * max(0, 35 - t["lead_time_days"]) * 0.001
    if t.get("ppm_commitment"):
        price += opening * profile["quality_premium"] * max(0, 1500 / t["ppm_commitment"] - 1)
        price += 0.001 * (t.get("chargeback_eur_per_complaint") or 0)
    return math.ceil(max(0.01, price) * 100 - 1e-8) / 100


class StressSim(Sim):
    def __init__(self, scenario):
        self.profiles = scenario["profiles"]
        case = scenario["case"]
        super().__init__({case["case_id"]: copy.deepcopy(case)}, no_clock=True)

    def _answer(self, s, th, msg, sheets):
        case, sid = s["case"], f"sup:{th['key']}"
        p = self.profiles[sid]
        if th["status"] == "final_offer":
            th["closed"] = "walked_away"
            return self._mail(s, th, "walked_away", th["stated"], "Our final offer was firm.")
        if not sheets:
            return self._mail(s, th, th["status"], th["stated"], "Please offer a complete package.")
        best = max(sheets, key=lambda t: t["unit_price"] - reservation(case, p, th["opening"], t))
        surplus = best["unit_price"] - reservation(case, p, th["opening"], best)
        improved = surplus > th.get("buyer_surplus", -math.inf) + 0.0001
        th["buyer_surplus"] = max(surplus, th.get("buyer_surplus", -math.inf))
        th["stalls"] = 0 if improved else th.get("stalls", 0) + 1
        if p["style"] != "reciprocal" or improved:
            th["progress"] = th.get("progress", 0) + 1
        fraction = min(1, th.get("progress", 0) / p["final_round"])
        remaining = 1 - fraction ** (2 if p["style"] == "late" else 1)
        premium = th["opening"] * (1 - p["floor_ratio"]) * remaining
        ask = math.ceil((reservation(case, p, th["opening"], best) + premium) * 100 - 1e-8) / 100
        accepted = [t for t in sheets if t["unit_price"] >= reservation(case, p, th["opening"], t) + premium - 1e-8]
        if accepted:
            terms = max(accepted, key=lambda t: t["unit_price"] - reservation(case, p, th["opening"], t))
            status, text = "agreed", "We can agree to this complete package."
        else:
            terms = {**best, "unit_price": ask}
            final = fraction >= 1 or (p["style"] == "reciprocal" and th["stalls"] >= 2)
            status = "final_offer" if final else "open"
            text = (
                "This is our final package." if final
                else "We have reviewed the complete package and improved our price."
            )
            if not improved and p["style"] == "reciprocal":
                text += " We need a reciprocal concession; an unchanged proposal cannot unlock another reduction."
            if p["finance_rate"] >= 0.15:
                text += " Cash flow matters; earlier payment can support a better price."
            if "ppm_commitment" in case["negotiable"]:
                text += " A tighter defect commitment and complaint liability both raise our costs."
            if "contract_months" in case["negotiable"]:
                text += " A longer firm commitment supports production planning."
        return self._mail(s, th, status, terms, text, ["quote.pdf"])

    def _end(self, s, reason, sup):
        # Exhaustive oracle uses private floors, but only after the negotiation ends.
        super()._end(s, reason, sup)
        case, best = s["case"], math.inf
        fields = [f for f in case["negotiable"] if f != "unit_price"]
        for sid, th in s["threads"].items():
            menus = [case["term_options"].get(f) or [th["standard"].get(f)] for f in fields]
            for values in itertools.product(*menus):
                terms = dict(zip(fields, values, strict=True))
                terms["unit_price"] = reservation(case, self.profiles[sid], th["opening"], terms)
                if must_haves_ok(case, terms, th["standard"]):
                    best = min(best, total_cost(case, terms, th["standard"]))
        result = s["result"]
        result["c_best"] = best
        if sup:
            result["cost_breakdown"] = cost_breakdown(case, result["terms"])
        result["score"] = score(result["c_open"], result["c_deal"] if sup else result["c_alt"], best)
        if sup and not result["must_haves_ok"]:
            result["score"] = 0.0


def evaluate(split="dev", new_agent=BuyerAgent):
    records = []
    suite = scenarios(split)
    for scenario in suite:
        case = scenario["case"]
        table = LocalTable(case)
        table.sim = StressSim(scenario)
        agent, started = new_agent(), time.monotonic()
        record = {"case_id": case["case_id"], "family": scenario["family"], "style": scenario["style"]}
        try:
            result = play(table, case["case_id"], agent)
            record.update(
                result=result,
                rounds=sum(t["round"] for t in table.sim.sessions[table.session_id]["threads"].values()),
            )
        except Exception as exc:
            record.update(error=f"{type(exc).__name__}: {exc}", result={"score": 0.0})
        record.update(seconds=round(time.monotonic() - started, 3), decisions=getattr(agent, "trace", []))
        records.append(record)
    scores = [r["result"]["score"] for r in records]
    return {
        "environment": "Synthetic local counterparties; no hosted or model calls.",
        "limitation": "This score is specific to these scripts and does not predict a hosted score.",
        "version": VERSION,
        "split": split,
        "suite_sha256": hashlib.sha256(json.dumps(suite, sort_keys=True).encode()).hexdigest(),
        "buyer_sha256": hashlib.sha256(Path(inspect.getfile(new_agent)).read_bytes()).hexdigest(),
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "mean_score": statistics.mean(scores),
        "worst_score": min(scores),
        "errors": sum("error" in r for r in records),
        "breaches": sum(r["result"].get("must_haves_ok") is False for r in records),
        "by_family": {
            f: statistics.mean(r["result"]["score"] for r in records if r["family"] == f)
            for f in sorted({r["family"] for r in records})
        },
        "by_style": {
            s: statistics.mean(r["result"]["score"] for r in records if r["style"] == s)
            for s in sorted({r["style"] for r in records})
        },
        "runs": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=SEEDS, default="dev")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = evaluate(args.split)
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "runs"}, indent=2))


if __name__ == "__main__":
    main()
