"""Price commercial exchanges against a buyer cost budget, not a headline price."""

import math

from .cost import RELATIONSHIP_GOALS, cost_breakdown, must_haves_ok, supplier_value, total_cost


def at_cost(case, template, budget, standard=None, supplier=None):
    """Highest cent price within the budget for these exact non-price terms.

    Ordinary cost is affine in price. A strategic relationship penalty can make
    it U-shaped: locate its minimum before searching the upper feasible branch.
    The template is never relaxed to make the arithmetic work.
    """
    if "unit_price" not in case["negotiable"] or not math.isfinite(budget):
        return None
    # The public cost function rounds the *total* to cents. Preserve prices
    # exactly on that boundary; still verify the returned rounded cost below.
    limit = budget + 0.005 - 1e-8

    def terms(price):
        return {**template, "unit_price": price}

    def cash_cost(price):
        return sum(cost_breakdown(case, terms(price), standard).values())

    base = cash_cost(0.01)
    slope = cash_cost(1.01) - base
    if not math.isfinite(slope) or slope <= 0:
        return None  # no positive, identifiable price exposure
    ceiling = 0.01 + (limit - base) / slope
    if ceiling < 0.01 or not math.isfinite(ceiling):
        return None
    lower = 0.01
    b = case["buyer"]
    nonlinear = (
        supplier and b.get("category_goal") in RELATIONSHIP_GOALS
        and b.get("relationship_eur_per_point") and b.get("sustainable_margin_pct")
    )

    def cost(price):
        return sum(cost_breakdown(case, terms(price), standard, supplier).values())

    if nonlinear:
        # Supplier margin is defined only for positive supplier value.
        worth = supplier_value(case, terms(lower), supplier)
        gain = supplier_value(case, terms(lower + 1), supplier) - worth
        if gain <= 0:
            return None
        lower = max(lower, lower - worth / gain + 1e-6)
        if lower > ceiling:
            return None
        left, right = lower, ceiling
        for _ in range(64):
            a, z = (2 * left + right) / 3, (left + 2 * right) / 3
            if cost(a) <= cost(z):
                right = z
            else:
                left = a
        # There may be no feasible cent even when the continuous minimum fits.
        cents = {max(math.ceil(lower * 100), int(p * 100)) for p in (left, right)}
        cents |= {c + 1 for c in cents}
        feasible = [c / 100 for c in cents if c / 100 <= ceiling and cost(c / 100) <= limit]
        if not feasible:
            return None
        lower = max(feasible)
        left, right = lower, ceiling
        for _ in range(48):
            middle = (left + right) / 2
            if cost(middle) <= limit:
                left = middle
            else:
                right = middle
        ceiling = left
    price = math.floor(ceiling * 100 + 1e-7) / 100
    result = terms(price)
    if price < lower - 1e-7 or not must_haves_ok(case, result, standard):
        return None
    return result if total_cost(case, result, standard, supplier) <= budget else None


def same_exchange(left, right):
    """A price concession belongs to its commercial package, not to every package."""
    return {k: v for k, v in left.items() if k != "unit_price"} == {
        k: v for k, v in right.items() if k != "unit_price"
    }


def value_equivalent(case, first, templates, standard, supplier, events):
    """Keep the main bid; offer at most two distinct exchanges at its total cost.

    Do not retract a higher price already offered for identical complete terms.
    If that commitment exceeds today's budget, omit the exchange instead.
    """
    budget = total_cost(case, first, standard, supplier)
    previous = [
        sheet["terms"] for message in events if message.get("from") == "buyer"
        for sheet in message.get("term_sheets") or []
    ]
    out = [first]
    for template in templates:
        if any(same_exchange(template, existing) for existing in out):
            continue
        priced = at_cost(case, template, budget, standard, supplier)
        if priced is None:
            continue
        if any(same_exchange(priced, old) and priced["unit_price"] < old["unit_price"] for old in previous):
            continue
        out.append(priced)
        if len(out) == 3:
            break
    return out
