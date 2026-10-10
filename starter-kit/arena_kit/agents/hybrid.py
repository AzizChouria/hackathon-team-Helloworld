"""Evidence-backed offers; Python controls economics, the LLM adapts the conversation."""
import json
import logging
import math
import os
import re
import time

from ..cost import total_cost
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
        self.used_refs = set()
        self.best_seen = None
        self.opening_cost = None
        self.last_cost = None
        self.stalls = 0
        self.response_guard_s = min(35.0, max(1.0, float(os.getenv("HYBRID_RESPONSE_GUARD_S", "35"))))
        self.stall_rounds = max(2, int(os.getenv("HYBRID_STALL_ROUNDS", "2")))

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

    def decide_many(self, case, threads, *, allow_model=True):
        start = time.monotonic()
        if self.case_id != case["case_id"]:
            self.case_id, self.calls = case["case_id"], 0
            self.used_refs = set()
            self.best_seen = self.last_cost = self.opening_cost = None
            self.stalls = 0
            self.diagnostics = []
            self.prepare(case)
        live = live_threads(threads)
        if not live:
            return [close(case, threads)]
        estimates = self._estimates(case, threads)
        offers = standing_offers(case, threads, estimates)
        age = max((time.monotonic() - latest(threads[s]).get("_received_at", start) for s in live), default=0)
        if age >= self.response_guard_s:
            return [close(case, threads, estimates)]
        # Only compare successive complete RFQ views; a pending supplier is not an available offer.
        if offers and allow_model:
            current = offers[0]["cost"]
            if self.opening_cost is None:
                self.opening_cost = current
            self.stalls = self.stalls + 1 if self.last_cost is not None and current >= self.last_cost - 0.01 else 0
            deteriorated = self.best_seen is not None and current > self.best_seen + 0.01
            self.best_seen = min(current, self.best_seen) if self.best_seen is not None else current
            self.last_cost = current
            # Repetition of an unimproved opening is not evidence of a good closing point.
            # Only protect an earned concession; keep exploring when the alternative still wins.
            earned_concession = current < self.opening_cost - 0.01
            if deteriorated or earned_concession and self.stalls >= self.stall_rounds:
                decision = close(case, threads, estimates)
                if decision["message"]["action"]["type"] == "accept":
                    return [decision]
        # Close on any firm finish using the cheapest feasible offer across ALL suppliers.
        if any(latest(threads[s]).get("status") in {"agreed", "final_offer"}
               or moves_left(case, threads[s]) <= 1 for s in live):
            decision = close(case, threads, estimates)
            if decision["message"]["action"]["type"] == "accept" or all(
                    latest(threads[s]).get("status") in {"agreed", "final_offer"} for s in live):
                return [decision]
        out = []
        self.used_refs.update(r for ev in threads.values() for e in ev if e.get("from") == "buyer"
                              for r in e.get("refs", []))
        for sid in live:
            events = threads[sid]
            if latest(events).get("status") in {"agreed", "final_offer"} or moves_left(case, events) <= 1:
                continue
            turn = sum(e.get("from") == "buyer" for e in events)
            if turn >= int(os.environ.get("HYBRID_MAX_COUNTERS", "5")):
                return [close(case, threads, estimates)]
            previous = [s["terms"] for e in events if e.get("from") == "buyer" for s in e.get("term_sheets", [])]
            _, terms = standing(events)
            supplier_sheets = [e.get("term_sheets") for e in events if e.get("from") != "buyer"][-3:]
            unchanged = len(supplier_sheets) == 3 and all(
                [s.get("terms") for s in sheets or []] == [s.get("terms") for s in supplier_sheets[-1] or []]
                for sheets in supplier_sheets)
            last_counter = turn == int(os.environ.get("HYBRID_MAX_COUNTERS", "5")) - 1
            packages = candidates(case, terms, standard_terms(events), turn, estimates.get(sid), previous,
                                  ceiling=offers[0]["cost"] if offers else math.inf,
                                  closing_bid=last_counter and unchanged)
            if offers:
                # No model-selected concession may cost more than the best currently feasible deal.
                ceiling = offers[0]["cost"]
                packages = [t for t in packages
                            if total_cost(case, t, standard_terms(events), estimates.get(sid)) < ceiling - 0.01]
            if not packages:
                continue
            intel = self.intelligence.prepare(case, sid)
            evidence = [e for e in intel["evidence"] if not self.used_refs.intersection(e["refs"])]
            kind = {"quality": "quality", "capacity": "capacity"}.get(
                case.get("type"), "cost" if turn == 0 else "approval")
            strategy = {"package_order": list(range(len(packages))), "evidence": [0] if evidence else [],
                        "question": kind, "body": ""}
            fallback = self.complete is None
            # For RFQs keep all thread clocks safe: only one model call per batch.
            model_called = False
            model_budget = getattr(self.complete, "timeout", 30.0)
            clock_safe = age + (time.monotonic() - start) + model_budget + 10 < 60
            if (allow_model and clock_safe and self.complete and self.calls < self.max_calls
                    and not out and turn in {0, 1}):
                model_called = True
                self.calls += 1
                context = {"scenario": case.get("type"), "supplier": sid,
                           "notes": [n[:600] for n in intel["notes"][:4]], "hypotheses": intel["hypotheses"],
                           "buyer_round": turn, "moves_remaining": moves_left(case, events),
                           "recent_exchange": [{"from": e.get("from"), "body": e.get("body", "")[:350]}
                                               for e in events[-4:]],
                           "package_costs_eur": [total_cost(case, p, standard_terms(events), estimates.get(sid))
                                                 for p in packages],
                           "reply": latest(events).get("body", "")[:1800],
                           "attachments": [a.get("text", "")[:700] for a in latest(events).get("attachments", [])][:2],
                           "packages": packages, "evidence": evidence[:6],
                           "instruction": "Select packages and a grounded negotiating approach."}
                try:
                    strategy = validate(self.complete(SYSTEM, json.dumps(context, default=str, ensure_ascii=False)),
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
            claims, claim_refs = [], set()
            for i in dict.fromkeys(strategy["evidence"]):
                if len(claims) < 2 and len(claim_refs | set(evidence[i]["refs"])) <= 3:
                    claims.append(evidence[i])
                    claim_refs.update(evidence[i]["refs"])
            self.used_refs.update(r for e in claims for r in e["refs"])
            body += " " + " ".join(e["text"] for e in claims)
            body += " " + QUESTIONS[strategy["question"]]
            out.append({"supplier_id": sid, "message": {"subject": case["title"][:300], "body": body,
                       "refs": [r for e in claims for r in e["refs"]],
                       "term_sheets": [{"terms": t} for t in selected]}})
            self.diagnostics.append({"case_id": case["case_id"], "supplier_id": sid, "turn": turn,
                                     "decision_s": time.monotonic() - start, "fallback": fallback,
                                     "model_called": model_called, "oldest_reply_age_s": age,
                                     "standing_costs": [{"supplier_id": o["supplier_id"], "cost": o["cost"],
                                                         "base_cost": o["base_cost"]} for o in offers]})
        return out or [close(case, threads, estimates)]
