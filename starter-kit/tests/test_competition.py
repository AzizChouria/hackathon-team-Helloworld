import copy
import json
import time

import pytest

from arena_kit.agents import BuyerAgent
from arena_kit.buyer_simulation import LocalTable
from arena_kit.cost import total_cost
from arena_kit.exchanges import same_exchange
from arena_kit.play import play_threads
from arena_kit.sim import load_cases


@pytest.fixture
def case():
    case = copy.deepcopy(load_cases()["case:S02"])
    case["suppliers"] = ["sup:A", "sup:B"]
    case["buyer"]["need_lead_time_days"] = 35
    case["buyer"]["must_haves"] = [{"field": "lead_time_days", "op": "<=", "value": 42}]
    return case


def quote(sid, price, status="open", payment=30, lead=35):
    return {
        "from": "supplier", "status": status, "_received_at": time.monotonic(),
        "body": "We can offer this complete combination of payment and production time.",
        "term_sheets": [{"term_sheet_id": f"offer:{sid}-{price}", "terms": {
            "unit_price": price, "payment_days": payment, "lead_time_days": lead,
        }}],
    }


def contacted(*replies):
    return [{"from": "buyer", "body": "Please quote."}, *replies]


def test_counter_follows_supplier_linked_preferences_at_same_buyer_value(case):
    response = quote("A", 20, payment=14, lead=42)
    offers = BuyerAgent().packages(case, "sup:A", [response])
    assert same_exchange(offers[0], response["term_sheets"][0]["terms"])
    costs = [total_cost(case, t) for t in offers]
    # Cent prices can differ by less than a cent per committed unit in cost.
    assert max(costs) - min(costs) < case["buyer"]["need_per_year"] * 0.025


def test_package_reordering_does_not_retract_previous_buyer_value(case):
    case["buyer"].update(interest_rate=0.4, late_cost_per_day=1000)
    previous = {"unit_price": 18, "payment_days": 14, "lead_time_days": 42}
    events = [
        quote("A", 22, payment=14, lead=42),
        {"from": "buyer", "term_sheets": [{"terms": previous}]},
        quote("A", 21, payment=14, lead=42),
    ]
    offers = BuyerAgent().packages(case, "sup:A", events)
    assert same_exchange(offers[0], previous)
    assert offers[0]["unit_price"] > previous["unit_price"]
    assert all(total_cost(case, t) >= total_cost(case, previous) for t in offers)


def test_noncompliant_supplier_preference_is_not_promoted(case):
    offers = BuyerAgent().packages(case, "sup:A", [quote("A", 20, lead=49)])
    assert all(t["lead_time_days"] <= 42 for t in offers)
    assert offers[0]["lead_time_days"] == 42


def test_incomplete_opening_is_repaired_without_demanding_unneeded_rush(case):
    opening = quote("A", 20, lead=49)
    opening["term_sheets"][0]["terms"].pop("payment_days")
    offers = BuyerAgent().packages(case, "sup:A", [opening])
    assert offers[0]["lead_time_days"] == 42


def test_cheaper_compliant_rival_is_used_even_if_model_omits_it(case):
    def model(*_):
        return json.dumps({"tactic": "cash", "evidence": [], "message": "Please compare the packages."})
    agent = BuyerAgent(complete=model)
    threads = {"sup:A": [quote("A", 24)], "sup:B": contacted(quote("B", 20))}
    decision = agent.decide_ready(case, threads, ["sup:A"])
    assert "offer:B-20" in decision["message"]["refs"]
    assert "EUR 20.00" in decision["message"]["body"]


def test_final_quote_gets_one_competitive_challenge_before_award(case):
    agent = BuyerAgent()
    threads = {"sup:A": contacted(quote("A", 20, "final_offer")), "sup:B": contacted(quote("B", 20.25))}
    decision = agent.decide(case, threads)
    assert decision["supplier_id"] == "sup:B"
    assert decision["message"].get("term_sheets")
    assert agent.trace[-1]["final_challenge"]
    threads["sup:B"] += [{**decision["message"], "from": "buyer"}, quote("B", 20.25)]
    # An unchanged response cannot extend the challenge indefinitely.
    assert agent.decide(case, threads)["message"]["action"]["type"] == "accept"


def test_rfq_accepts_a_complete_offer_that_meets_its_last_bid(case):
    agent = BuyerAgent()
    bid = {"from": "buyer", "term_sheets": [{"terms": {
        "unit_price": 20, "payment_days": 30, "lead_time_days": 35,
    }}]}
    threads = {
        "sup:A": [quote("A", 21), bid, quote("A", 20.5), bid, quote("A", 20.01)],
        "sup:B": contacted(quote("B", 22)),
    }

    decision = agent.decide(case, threads)

    assert decision["supplier_id"] == "sup:A"
    assert decision["message"]["action"]["type"] == "accept"


def test_pending_challenge_has_bounded_extra_reply_time(case):
    agent = BuyerAgent()
    threads = {"sup:A": contacted(quote("A", 20, "final_offer")), "sup:B": contacted(quote("B", 20.25))}
    assert agent.decide(case, threads)["supplier_id"] == "sup:B"
    threads["sup:A"][-1]["_received_at"] = time.monotonic() - 31
    assert agent.decide_ready(case, threads, ["sup:A"]) is None
    threads["sup:A"][-1]["_received_at"] = time.monotonic() - 46
    assert agent.decide_ready(case, threads, ["sup:A"])["message"]["action"]["type"] == "accept"


@pytest.mark.parametrize("price,age", [(25, 0), (20.25, 31)])
def test_uncompetitive_or_late_challenger_does_not_risk_final_offer(case, price, age):
    final = quote("A", 20, "final_offer")
    final["_received_at"] -= age
    threads = {"sup:A": contacted(final), "sup:B": contacted(quote("B", price))}
    decision = BuyerAgent().decide(case, threads)
    assert decision["supplier_id"] == "sup:A"
    assert decision["message"]["action"]["type"] == "accept"


def test_competition_compares_cost_including_payment_and_delivery(case):
    threads = {
        "sup:A": contacted(quote("A", 20, "final_offer", payment=90)),
        "sup:B": contacted(quote("B", 20.3, payment=14, lead=42)),
    }
    decision = BuyerAgent().decide(case, threads)
    assert decision["message"]["action"]["type"] == "accept"


def test_real_rfq_loop_collects_improved_challenger_before_award(case):
    threads = {"sup:A": contacted(quote("A", 20, "final_offer")), "sup:B": contacted(quote("B", 20.25))}

    class Table(LocalTable):
        calls = 0

        def send(self, sid, message):
            self.calls += 1
            assert sid == "sup:B"
            return quote("B", 18, "final_offer")

        def close(self, sid, message):
            return {"supplier_id": sid, "offer": message["action"]["term_sheet_id"]}

    table = Table(case)
    result = play_threads(table, case, threads, BuyerAgent())
    assert result["supplier_id"] == "sup:B"
    assert table.calls == 1


def test_best_ready_offer_is_preserved_while_other_challenger_is_pending(case):
    case["suppliers"].append("sup:C")
    threads = {
        "sup:A": contacted(quote("A", 22, "final_offer")),
        "sup:B": contacted(quote("B", 20)),
        "sup:C": contacted(quote("C", 20.25)),
    }
    agent = BuyerAgent()
    decision = agent.decide(case, threads)
    assert decision["supplier_id"] == "sup:C"
    assert decision["message"].get("term_sheets")
    # The cheaper B quote must remain ready throughout a slow C response.
    assert agent.decide_ready(case, threads, ["sup:A", "sup:B"]) is None
    threads["sup:A"][-1]["_received_at"] = time.monotonic() - 46
    decision = agent.decide_ready(case, threads, ["sup:A", "sup:B"])
    assert decision["supplier_id"] == "sup:B"
    assert decision["message"]["action"]["type"] == "accept"


def test_protected_open_quote_expiry_is_respected(case):
    case["suppliers"].append("sup:C")
    threads = {
        "sup:A": contacted(quote("A", 22, "final_offer")),
        "sup:B": contacted(quote("B", 20)),
        "sup:C": contacted(quote("C", 20.25)),
    }
    threads["sup:B"][-1]["_received_at"] = time.monotonic() - 31
    decision = BuyerAgent().decide(case, threads)
    assert decision["supplier_id"] == "sup:B"
    assert decision["message"]["action"]["type"] == "accept"


def test_opening_anchor_uses_compliant_market_cost(case):
    threads = {"sup:A": [quote("A", 40)], "sup:B": [quote("B", 20)]}
    offers = BuyerAgent().decide_ready(case, threads, ["sup:A"])["message"]["term_sheets"]
    assert all(total_cost(case, s["terms"]) <= 0.86 * total_cost(case, threads["sup:B"][0]["term_sheets"][0]["terms"])
               for s in offers)


def test_infeasible_rival_cannot_reset_our_opening_anchor(case):
    threads = {"sup:A": [quote("A", 40)], "sup:B": [quote("B", 10, lead=49)]}
    offers = BuyerAgent().decide_ready(case, threads, ["sup:A"])["message"]["term_sheets"]
    assert min(s["terms"]["unit_price"] for s in offers) > 30
