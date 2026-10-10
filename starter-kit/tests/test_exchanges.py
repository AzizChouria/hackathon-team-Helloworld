import copy

import pytest

from arena_kit.agents import BuyerAgent
from arena_kit.benchmark import LocalTable
from arena_kit.cost import closing_terms, complete_offer, must_haves_ok, total_cost
from arena_kit.exchanges import at_cost, value_equivalent
from arena_kit.play import play
from arena_kit.sim import Sim, load_cases


@pytest.fixture
def case():
    case = copy.deepcopy(load_cases()["case:S02"])
    case["buyer"]["need_lead_time_days"] = 35
    case["buyer"]["must_haves"] = [{"field": "lead_time_days", "op": "<=", "value": 42}]
    case["suppliers"] = ["sup:exchange-test"]
    return case


@pytest.mark.parametrize("payment,lead", [(14, 35), (60, 42), (90, 42)])
def test_exchange_discount_pays_for_financing_and_delay(case, payment, lead):
    first = complete_offer(case, {"unit_price": 20, "payment_days": 90, "lead_time_days": 35})
    budget = total_cost(case, first)
    template = {**first, "payment_days": payment, "lead_time_days": lead}
    result = at_cost(case, template, budget)
    # Independently compute the financing and delay compensation per unit.
    b = case["buyer"]
    units = b["need_per_year"] * b["horizon_years"]
    expected = (20 * (1 + b["interest_rate"] * (60 - 90) / 360)
                - (lead - 35) * b["late_cost_per_day"] / units)
    expected /= 1 + b["interest_rate"] * (60 - payment) / 360
    assert expected - 0.01 < result["unit_price"] <= expected
    assert total_cost(case, result) <= budget
    assert total_cost(case, {**result, "unit_price": result["unit_price"] + 0.01}) > budget
    assert {k: v for k, v in result.items() if k != "unit_price"} == {
        k: v for k, v in template.items() if k != "unit_price"
    }


def test_does_not_buy_a_discount_by_breaking_requirements(case):
    first = complete_offer(case, {"unit_price": 20, "payment_days": 90, "lead_time_days": 35})
    assert at_cost(case, {**first, "lead_time_days": 49}, total_cost(case, first)) is None
    # No unit price can pay for costs that already exceed the budget.
    case["fixed_terms"]["tooling_eur"] = 1_000_000
    assert at_cost(case, first, 100) is None


def test_index_and_quality_exchanges_include_their_full_cost(case):
    case["negotiable"] += ["index_clause", "ppm_commitment", "chargeback_eur_per_complaint"]
    case["fixed_terms"].pop("index_clause")
    case["buyer"]["index_paths"] = {"MATERIAL": 0.2}
    first = complete_offer(case, {
        "unit_price": 20, "payment_days": 90, "lead_time_days": 35,
        "index_clause": None, "ppm_commitment": 500, "chargeback_eur_per_complaint": 50,
    })
    exchange = {
        **first, "ppm_commitment": 1500, "chargeback_eur_per_complaint": 0,
        "index_clause": {"series": "MATERIAL", "material_share": 0.5, "deadband_pct": 3},
    }
    budget = total_cost(case, first)
    result = at_cost(case, exchange, budget)
    assert result["unit_price"] < 19
    assert total_cost(case, result) <= budget
    assert total_cost(case, {**result, "unit_price": result["unit_price"] + 0.01}) > budget


def test_relationship_penalty_uses_upper_feasible_price_not_cheapest_price(case):
    case["buyer"].update(category_goal="stabilise", sustainable_margin_pct=10, relationship_eur_per_point=100000)
    standard = closing_terms(case, {"unit_price": 20, "payment_days": 60})
    supplier = {"standard": standard, "full_cost": 19, "interest_rate": 0.15}
    template = complete_offer(case, {"unit_price": 22, "payment_days": 14, "lead_time_days": 35})
    # This budget cuts through both sides of the U-shaped cost curve.
    budget = total_cost(case, template, standard, supplier)
    result = at_cost(case, template, budget, standard, supplier)
    feasible = [
        cents / 100 for cents in range(1500, 2501)
        if total_cost(case, {**template, "unit_price": cents / 100}, standard, supplier) <= budget
    ]
    assert result["unit_price"] == max(feasible)
    assert result["unit_price"] >= 22
    assert at_cost(case, template, 100, standard, supplier) is None


def test_prior_prices_are_preserved_only_for_identical_exchanges(case):
    first = complete_offer(case, {"unit_price": 20, "payment_days": 90, "lead_time_days": 35})
    cash = {**first, "payment_days": 14}
    previous = [{"from": "buyer", "term_sheets": [{"terms": cash}]}]
    # A previous, more generous cash bid must not silently be retracted.
    assert value_equivalent(case, first, [cash], {}, None, previous) == [first]
    different = {**cash, "lead_time_days": 42}
    result = value_equivalent(case, first, [different], {}, None, previous)
    assert len(result) == 2
    assert result[1]["unit_price"] < cash["unit_price"]


@pytest.mark.parametrize("saving_per_unit", [0, 0.5, 2])
def test_supplier_can_choose_delivery_exchange_through_real_play_loop(case, saving_per_unit):
    """Independent fixed-price supplier: no concessions triggered by round number.

    It values one more week of production time, and counterquotes the offered
    package with the greatest surplus against its private costs.
    """
    class DeliveryShop(Sim):
        def _answer(self, session, thread, message, sheets):
            def floor(terms):
                return 17 - (saving_per_unit if terms["lead_time_days"] >= 42 else 0)

            best = max(sheets, key=lambda t: t["unit_price"] - floor(t))
            return self._mail(session, thread, "final_offer", {**best, "unit_price": floor(best)}, "Firm quote.")

    table = LocalTable(case)
    table.sim = DeliveryShop({case["case_id"]: case}, no_clock=True)
    result = play(table, case["case_id"], BuyerAgent())
    assert result["deal"] and result["must_haves_ok"]
    rushed_cost = total_cost(case, {"unit_price": 17, "payment_days": 90, "lead_time_days": 35})
    assert result["c_deal"] <= rushed_cost
    if saving_per_unit:
        assert result["terms"]["lead_time_days"] == 42
        assert result["c_deal"] < rushed_cost
    else:
        assert result["terms"]["lead_time_days"] == 35


def test_agent_exposes_only_compliant_equivalent_packages(case):
    sid = case["suppliers"][0]
    events = [{"from": "supplier", "term_sheets": [{"terms": {"unit_price": 20}}]}]
    packages = BuyerAgent().packages(case, sid, events)
    assert len(packages) == 3
    assert any(t["lead_time_days"] == 42 for t in packages)
    assert all(set(t) == set(case["negotiable"]) and must_haves_ok(case, t) for t in packages)
    budget = total_cost(case, packages[0])
    assert all(total_cost(case, t) <= budget for t in packages)
