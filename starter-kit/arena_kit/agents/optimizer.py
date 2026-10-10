"""Finite-domain economic search. The published cost function remains authoritative."""
import itertools
import math

from ..cost import OPS, closing_terms, complete_offer, must_haves_ok, total_cost
from ..docs import standard_terms
from ..play import latest, live_threads


def valid(case, terms, standard=None, complete=False):
    std = standard or {}
    if complete and set(terms) != set(case["negotiable"]):
        return False
    # Cost estimation fills gaps from the buyer plan. That is NOT supplier agreement.
    known = {}
    for layer in (std, case.get("fixed_terms", {}), terms):
        known.update({k: v for k, v in layer.items() if v is not None})
    if any(m["field"] not in known and m.get("value") is not None
           for m in case["buyer"].get("must_haves", [])):
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


def candidates(case, standing, std, turn=0, estimate=None, previous=(), *, ceiling=math.inf, closing_bid=False):
    """Beam-search all field domains, retaining diversity; prices are hypotheses, never hidden floors."""
    base = complete_offer(case, closing_terms(case, standing, std))
    # Supplier standard values are explicitly allowed, even outside the enumerated options.
    stated = closing_terms(case, standing, std)
    for field in case["negotiable"]:
        if (field != "unit_price" and field in std and stated.get(field) == std[field]
                and (std[field] is not None or field == "index_clause")):
            base[field] = std[field]
    price = standing.get("unit_price") or case["buyer"].get("current_unit_price")
    price = price or case["buyer"]["fallback_unit_price"]
    prior_terms = [t for t in previous if t.get("unit_price")]
    # Compare concessions in full-cost space: a lower price compensating for worse
    # non-price terms must not pull the main package's next price anchor down.
    prior = ([min(prior_terms, key=lambda t: total_cost(case, t, std, estimate))["unit_price"]]
             if prior_terms else [])
    anchor = price * (0.90 if turn == 0 else 0.96)
    if prior:
        anchor = max(anchor, min(prior) + (price - min(prior)) * 0.35)
    # A bounded last bid after repeated unchanged supplier offers avoids spending
    # the final round cycling equivalent non-price profiles at a rejected price.
    if closing_bid:
        anchor = max(anchor, price * 0.98)
    prices = sorted({round(max(0.01, x), 2) for x in (anchor, price * 0.98, price)})
    # Supplier-specific should-cost is uncertain; include a sustainable option, not a hard floor.
    if estimate:
        margin = case["buyer"].get("sustainable_margin_pct", 3) / 100
        prices.append(round(estimate["full_cost"] / max(0.5, 1 - margin), 2))
    beam = [{**base, "unit_price": p} for p in prices if p <= price * 1.05]
    fields = [f for f in case["negotiable"] if f != "unit_price"]
    for field in fields:
        options = list(case.get("term_options", {}).get(field) or [base.get(field)])
        if (field in std and (std[field] is not None or field == "index_clause")
                and std[field] not in options):
            options.append(std[field])
        expanded = [{**t, field: v} for t, v in itertools.product(beam, options)]
        # Filter constraints as each field is assigned, before beam truncation can erase
        # every feasible branch (e.g. a costly minimum-volume or maximum-payment condition).
        constraints = [m for m in case["buyer"].get("must_haves", []) if m["field"] == field]
        expanded = [t for t in expanded if all(
            (t[field] is not None or m["op"] in ("==", "!=")) and OPS[m["op"]](t[field], m["value"])
            for m in constraints)]
        expanded.sort(key=lambda t: total_cost(case, t, std, estimate))
        beam = expanded[:192]
        # Preserve supplier-friendly branches otherwise lost in the buyer-only beam.
        for v in options:
            group = [t for t in expanded if t[field] == v]
            beam.extend(group[:4])
    # Retain a price-only route on the supplier's own terms. Beam search otherwise tends
    # to erase this commercially plausible branch in favour of changing every field.
    beam.extend({**base, "unit_price": p} for p in prices if p <= price * 1.05)
    unique = {str(sorted(t.items())): t for t in beam
              if valid(case, t, std, complete=True)
              and total_cost(case, t, std, estimate) < ceiling - 0.01}
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
    out, profiles = [], set()
    for t in choices + feasible:
        profile = repr(sorted((k, v) for k, v in t.items() if k != "unit_price"))
        if profile not in profiles and t not in previous:
            out.append(t)
            profiles.add(profile)
        if len(out) == 3:
            break
    if closing_bid:
        # Make the late price concession conditional on our best economic profile;
        # do not simultaneously give away financing or freight at that higher price.
        return out[:1]
    if turn == 1 and len(out) >= 2:
        # After feedback, include a low-disruption route only at a reciprocal price that
        # keeps its buyer cost no worse than the most expensive package already selected.
        target = max(total_cost(case, t, std, estimate) for t in out)
        profile = {**base, "unit_price": min(prices)}
        high = profile["unit_price"]
        low = 0.01
        if total_cost(case, profile, std, estimate) > target:
            # Relationship penalties can make cost non-monotonic below supplier cost;
            # do not solve by bisection in that case.
            if estimate:
                return out
            for _ in range(32):
                middle = (low + high) / 2
                if total_cost(case, {**profile, "unit_price": middle}, std) <= target:
                    low = middle
                else:
                    high = middle
            profile["unit_price"] = math.floor(low * 100) / 100
        signature = repr(sorted((k, v) for k, v in profile.items() if k != "unit_price"))
        if (signature not in profiles and profile not in previous
                and profile["unit_price"] >= min(prices) * 0.90
                and valid(case, profile, std, complete=True)
                and total_cost(case, profile, std, estimate) <= target
                and total_cost(case, profile, std, estimate) < ceiling - 0.01):
            out = out[:2] + [profile]
    return out
