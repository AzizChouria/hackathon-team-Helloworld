"""Finite-domain economic search. The published cost function remains authoritative."""
import itertools
import math

from ..cost import closing_terms, complete_offer, must_haves_ok, total_cost
from ..docs import standard_terms
from ..play import latest, live_threads


def valid(case, terms, standard=None, complete=False):
    std = standard or {}
    if complete and set(terms) != set(case["negotiable"]):
        return False
    t = closing_terms(case, terms, std)
    p = t.get("unit_price")
    if isinstance(p, bool) or not isinstance(p, int | float) or not math.isfinite(p) or p <= 0:
        return False
    for field in case["negotiable"]:
        value = t.get(field)
        if isinstance(value, float) and not math.isfinite(value):
            return False
        options = case.get("term_options", {}).get(field)
        if field != "unit_price" and options and value not in options and value != std.get(field):
            return False
    try:
        return must_haves_ok(case, terms, std) and math.isfinite(total_cost(case, terms, std))
    except (ValueError, TypeError, KeyError, ZeroDivisionError):
        return False


def alternative_cost(case):
    alt = case["buyer"].get("alternative") or {}
    if alt.get("kind") not in (None, "none") and alt.get("terms", {}).get("unit_price"):
        return total_cost(case, alt["terms"])
    # No contractual alternative: walking away scores zero, NOT a hypothetical spot purchase.
    return math.inf


def standing_offers(case, threads, estimates=None):
    offers = []
    for sid in live_threads(threads):
        std = standard_terms(threads[sid])
        estimate = (estimates or {}).get(sid)
        for sheet in latest(threads[sid]).get("term_sheets") or []:
            terms = sheet.get("terms", {})
            if valid(case, terms, std):
                base = total_cost(case, terms, std)
                cost = total_cost(case, terms, std, estimate)
                offers.append({"supplier_id": sid, "id": sheet["term_sheet_id"], "terms": terms,
                               "cost": cost, "base_cost": base})
    return sorted(offers, key=lambda x: (x["cost"], x["base_cost"], x["supplier_id"]))


def candidates(case, standing, std, turn=0, estimate=None, previous=()):
    """Beam-search all field domains, retaining diversity; prices are hypotheses, never hidden floors."""
    base = complete_offer(case, closing_terms(case, standing, std))
    price = standing.get("unit_price") or case["buyer"].get("current_unit_price")
    price = price or case["buyer"]["fallback_unit_price"]
    prior = [t["unit_price"] for t in previous if t.get("unit_price")]
    anchor = price * (0.90 if turn == 0 else 0.96)
    if prior:
        anchor = max(anchor, min(prior) + (price - min(prior)) * 0.35)
    prices = sorted({round(max(0.01, x), 2) for x in (anchor, price * 0.98, price)})
    # Supplier-specific should-cost is uncertain; include a sustainable option, not a hard floor.
    if estimate:
        margin = case["buyer"].get("sustainable_margin_pct", 3) / 100
        prices.append(round(estimate["full_cost"] / max(0.5, 1 - margin), 2))
    beam = [{**base, "unit_price": p} for p in prices if p <= price * 1.05]
    fields = [f for f in case["negotiable"] if f != "unit_price"]
    for field in fields:
        options = list(case.get("term_options", {}).get(field) or [base.get(field)])
        if field in std and std[field] not in options:
            options.append(std[field])
        expanded = [{**t, field: v} for t, v in itertools.product(beam, options)]
        # Constraints are evaluated after all fields have been filled.
        expanded.sort(key=lambda t: total_cost(case, t, std, estimate))
        beam = expanded[:192]
        # Preserve supplier-friendly branches otherwise lost in the buyer-only beam.
        for v in options:
            group = [t for t in expanded if t[field] == v]
            beam.extend(group[:4])
    unique = {str(sorted(t.items())): t for t in beam if valid(case, t, std, complete=True)}
    feasible = sorted(unique.values(), key=lambda t: total_cost(case, t, std, estimate))
    if not feasible:
        return []
    # Three economically ranked but commercially distinct packages: cost, liquidity, stability.
    def economical(group):
        return min(group, key=lambda t: total_cost(case, t, std, estimate))
    choices = [feasible[0]]
    if "payment_days" in fields:
        fastest = min(t["payment_days"] for t in feasible)
        choices.append(economical([t for t in feasible if t["payment_days"] == fastest]))
    if "contract_months" in fields:
        longest = max(t["contract_months"] for t in feasible)
        choices.append(economical([t for t in feasible if t["contract_months"] == longest]))
    elif "effective_date" in fields:
        earliest = min(t["effective_date"] for t in feasible)
        choices.append(economical([t for t in feasible if t["effective_date"] == earliest]))
    elif "index_clause" in fields:
        group = [t for t in feasible if t.get("index_clause")]
        if group:
            choices.append(economical(group))
    # A counter must not simply repeat a previously rejected package.
    out = []
    for t in choices + feasible[:6]:
        if t not in out and t not in previous:
            out.append(t)
        if len(out) == 3:
            break
    return out
