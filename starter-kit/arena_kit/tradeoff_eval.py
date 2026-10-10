"""Offline preference-sensitive supplier scenarios; no model, network or private case data.

These fixtures expose economic-policy defects. They do not reproduce hosted suppliers.
"""
import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from .agents.hybrid import HybridAgent
from .cost import complete_offer, total_cost
from .local_eval import ROOT, LocalTable, baseline
from .play import play
from .sim import Sim, load_cases


class PreferenceSim(Sim):
    def __init__(self, cases, payment, floor, flexible=False):
        super().__init__(cases)
        self.payment, self.floor, self.flexible = payment, floor, flexible

    def open(self, team, case_id):
        response = super().open(team, case_id)
        session = self.sessions[response["session_id"]]
        case = session["case"]
        for sid, thread in session["threads"].items():
            terms = complete_offer(case, {"unit_price": thread["opening"]})
            for field in case["negotiable"]:
                options = case["term_options"].get(field, [])
                if field == "payment_days":
                    terms[field] = self.payment
                elif field in {"lead_time_days", "contract_months"}:
                    terms[field] = max(options)
                elif field == "incoterm":
                    terms[field] = "FCA" if "FCA" in options else options[0]
            thread["standard"] = {k: v for k, v in terms.items() if k != "unit_price"}
            thread["messages"].clear()
            self._mail(session, thread, "open", terms, "Please retain our quoted non-price terms.", ["quote.pdf"])
            response["threads"][sid] = copy.deepcopy(thread["messages"])
        return response

    def _answer(self, session, thread, message, sheets):
        eligible = [t for t in sheets if t["unit_price"] >= thread["opening"] * self.floor
                    and (self.flexible or all(t.get(k) == v for k, v in thread["standard"].items()))]
        if eligible:
            # Choose maximum unit price, break ties against the buyer: do not reward ordering.
            chosen = max(eligible, key=lambda t: (t["unit_price"], total_cost(session["case"], t)))
            return self._mail(session, thread, "agreed", chosen, "We agree.", ["quote.pdf"])
        status = "final_offer" if thread["round"] >= 5 else "open"
        return self._mail(session, thread, status, thread["stated"],
                          "Our non-price terms remain as quoted. Please revise the price.", ["quote.pdf"])


class PreferenceTable(LocalTable):
    def __init__(self, case, payment, floor, flexible):
        super().__init__(case)
        self.state = PreferenceSim({case["case_id"]: copy.deepcopy(case)}, payment, floor, flexible)


def compare(revision="5e21aac"):
    old, old_play = baseline(revision)
    rows = []
    for original in load_cases().values():
        for payment in (30, 45):
            for floor in (0.90, 0.94, 0.98):
                for interest in (0.0, 0.20):
                    for flexible in (False, True):
                        case = copy.deepcopy(original)
                        case["buyer"]["interest_rate"] = interest
                        row = {"case": case["case_id"], "payment_days": payment,
                               "supplier_price_floor_fraction": floor, "interest": interest,
                               "flexible_nonprice": flexible}
                        for label, cls, runner in (("before", old, old_play), ("after", HybridAgent, play)):
                            table = PreferenceTable(case, payment, floor, flexible)
                            result = runner(table, case["case_id"], cls())
                            session = table.state.sessions[table.session_id]
                            row[label] = {k: result[k] for k in ("deal", "must_haves_ok", "c_deal", "c_alt")}
                            row[label]["realized_cost"] = (result["c_deal"] if result["deal"]
                                                           and result["must_haves_ok"] else result["c_alt"])
                            row[label]["rounds"] = sum(t["round"] for t in session["threads"].values())
                            row[label]["timeouts"] = sum(len(t["late"]) for t in session["threads"].values())
                        row["cost_saved"] = round(row["before"]["realized_cost"] - row["after"]["realized_cost"], 2)
                        rows.append(row)
    return {"timestamp": datetime.now(UTC).isoformat(), "baseline_commit": revision,
            "scope": "72 synthetic development fixtures, NOT hosted performance or held-out evaluation",
            "hosted_sessions": 0, "model_calls": 0, "score": None,
            "score_caveat": "The standard simulator optimum does not describe these suppliers; report cost only.",
            "summary": {"fixtures": len(rows),
                        "lower_cost": sum(r["cost_saved"] > .01 for r in rows),
                        "equal_cost": sum(abs(r["cost_saved"]) <= .01 for r in rows),
                        "higher_cost": sum(r["cost_saved"] < -.01 for r in rows),
                        "after_valid_deals": sum(bool(r["after"]["deal"] and r["after"]["must_haves_ok"])
                                                 for r in rows),
                        "after_no_deals": sum(not r["after"]["deal"] for r in rows),
                        "after_timeouts": sum(r["after"]["timeouts"] for r in rows)}, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="5e21aac")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks" / "tradeoff_scenarios.json")
    args = parser.parse_args()
    result = compare(args.baseline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
