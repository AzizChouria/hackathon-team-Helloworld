"""Evidence-backed offers; Python controls economics, the LLM adapts the conversation."""
import json
import logging
import os
import re
import time

from ..docs import standard_terms
from ..play import latest, live_threads, moves_left, standing
from .decision import close
from .intelligence import Intelligence
from .optimizer import candidates, standing_offers
from .strategy import QUESTIONS, SYSTEM, validate

log = logging.getLogger("arena")


class HybridAgent:
    def __init__(self, complete=None, package=None):
        self.complete = complete
        self.intelligence = Intelligence(package)
        self.max_calls = int(os.environ.get("HYBRID_LLM_CALLS_PER_CASE", "2"))
        self.calls = 0
        self.case_id = None
        self.diagnostics = []

    def prepare(self, case):
        self.intelligence.refresh()
        for sid in case["suppliers"]:
            self.intelligence.prepare(case, sid)

    def _estimates(self, case, threads):
        return {s: self.intelligence.estimate(case, s, standard_terms(ev)) for s, ev in threads.items()}

    def closing_move(self, case, threads):
        return close(case, threads, self._estimates(case, threads))

    def decide(self, case, threads):
        decisions = self.decide_many(case, threads)
        return decisions[0]

    def decide_many(self, case, threads):
        start = time.monotonic()
        if self.case_id != case["case_id"]:
            self.case_id, self.calls = case["case_id"], 0
            self.prepare(case)
        live = live_threads(threads)
        if not live:
            return [close(case, threads)]
        estimates = self._estimates(case, threads)
        offers = standing_offers(case, threads, estimates)
        # Close on any firm finish using the cheapest feasible offer across ALL suppliers.
        if any(latest(threads[s]).get("status") in {"agreed", "final_offer"}
               or moves_left(case, threads[s]) <= 1 for s in live):
            decision = close(case, threads, estimates)
            if decision["message"]["action"]["type"] == "accept" or all(
                    latest(threads[s]).get("status") in {"agreed", "final_offer"} for s in live):
                return [decision]
        out = []
        for sid in live:
            events = threads[sid]
            if latest(events).get("status") in {"agreed", "final_offer"} or moves_left(case, events) <= 1:
                continue
            turn = sum(e.get("from") == "buyer" for e in events)
            if turn >= int(os.environ.get("HYBRID_MAX_COUNTERS", "5")):
                return [close(case, threads, estimates)]
            previous = [s["terms"] for e in events if e.get("from") == "buyer" for s in e.get("term_sheets", [])]
            _, terms = standing(events)
            packages = candidates(case, terms, standard_terms(events), turn, estimates.get(sid), previous)
            if not packages:
                continue
            intel = self.intelligence.prepare(case, sid)
            used = {r for ev in threads.values() for e in ev if e.get("from") == "buyer"
                    for r in e.get("refs", [])}
            evidence = [e for e in intel["evidence"] if not used.intersection(e["refs"])]
            kind = {"quality": "quality", "capacity": "capacity"}.get(
                case.get("type"), "cost" if turn == 0 else "approval")
            strategy = {"package_order": list(range(len(packages))), "evidence": [0] if evidence else [],
                        "question": kind, "body": ""}
            fallback = self.complete is None
            # For RFQs keep all thread clocks safe: only one model call per batch.
            if self.complete and self.calls < self.max_calls and not out and turn in {0, 2}:
                self.calls += 1
                context = {"scenario": case.get("type"), "supplier": sid,
                           "notes": intel["notes"][:4], "hypotheses": intel["hypotheses"],
                           "reply": latest(events).get("body", "")[:1800],
                           "attachments": [a.get("text", "")[:700] for a in latest(events).get("attachments", [])][:2],
                           "packages": packages, "evidence": evidence[:6],
                           "instruction": "Select packages and a grounded negotiating approach."}
                try:
                    strategy = validate(self.complete(SYSTEM, json.dumps(context, default=str)),
                                        len(packages), min(len(evidence), 6))
                except Exception as exc:
                    fallback = True
                    log.warning("hybrid fallback: %s", type(exc).__name__)
            elif self.complete:
                fallback = True  # deliberate deterministic step, distinguished by model_called below
            chosen = list(dict.fromkeys(strategy["package_order"])) or [0]
            selected = [packages[i] for i in chosen]
            body = strategy["body"].strip()
            # No generated figures, identifiers or confidential bargaining language reach suppliers.
            if (not body or len(body) > 550 or re.search(
                    r"\d|:|budget|reservation|urgent|deadline|alternative|competitor|cash.flow|"
                    r"financial|insolven|contract.right|our.limit|must.have|fallback", body, re.I)):
                body = ("Thank you for reviewing the commercial terms. We can discuss the attached "
                        "packages as alternatives. Please indicate the reciprocal improvement you can support.")
            claims = [evidence[i] for i in dict.fromkeys(strategy["evidence"])][:2]
            body += " " + " ".join(e["text"] for e in claims)
            body += " " + QUESTIONS[strategy["question"]]
            out.append({"supplier_id": sid, "message": {"subject": case["title"][:300], "body": body,
                       "refs": [r for e in claims for r in e["refs"]],
                       "term_sheets": [{"terms": t} for t in selected]}})
            self.diagnostics.append({"case_id": case["case_id"], "supplier_id": sid, "turn": turn,
                                     "decision_s": time.monotonic() - start, "fallback": fallback,
                                     "standing_costs": [{"supplier_id": o["supplier_id"], "cost": o["cost"],
                                                         "base_cost": o["base_cost"]} for o in offers]})
        return out or [close(case, threads, estimates)]
