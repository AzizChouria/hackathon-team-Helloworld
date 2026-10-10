"""Closing is deterministic and compares every feasible standing supplier sheet."""
from .optimizer import alternative_cost, standing_offers


def close(case, threads, estimates=None):
    best = standing_offers(case, threads, estimates)
    cap = alternative_cost(case)
    if best and best[0]["cost"] <= cap:
        offer = best[0]
        return {"supplier_id": offer["supplier_id"],
                "message": {"action": {"type": "accept", "term_sheet_id": offer["id"]}}}
    return {"supplier_id": next(iter(threads)),
            "message": {"action": {"type": "walk_away"}}}
