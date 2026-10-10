import copy
import json

import pytest

from arena_kit import buyer_stress as stress
from arena_kit.cost import total_cost


def test_local_splits_are_reproducible_disjoint_and_do_not_expose_private_profiles():
    dev, holdout = stress.scenarios("dev"), stress.scenarios("holdout")
    assert dev == stress.scenarios("dev")
    assert len(dev) == len(holdout) == 48
    assert not ({s["case"]["case_id"] for s in dev} & {s["case"]["case_id"] for s in holdout})
    opened = stress.StressSim(dev[0]).open("local-test", dev[0]["case"]["case_id"])
    assert "floor_ratio" not in json.dumps(opened)
    assert "profiles" not in json.dumps(opened)


@pytest.mark.parametrize("bid", [87.99, 88.0, 105.0])
def test_private_reservation_and_independent_score_calculation(bid):
    scenario = copy.deepcopy(stress.scenarios("dev")[0])
    case = scenario["case"]
    case["negotiable"] = ["unit_price"]
    case["fixed_terms"]["payment_days"] = 30
    case["buyer"].update(current_unit_price=100, interest_rate=0, freight_eur_per_unit={"EXW": 0, "FCA": 0, "DAP": 0})
    sid = case["suppliers"][0]
    scenario["profiles"][sid].update(floor_ratio=0.8, final_round=1, finance_rate=0)
    sim = stress.StressSim(scenario)
    session = sim.open("local-test", case["case_id"])["session_id"]
    reply = sim.message("local-test", session, sid, {"term_sheets": [{"terms": {"unit_price": bid}}]})
    if bid < 88:
        assert reply["status"] == "final_offer"
        assert reply["term_sheets"][0]["terms"]["unit_price"] == 88
    accepted = max(88, bid)
    closed = sim.message("local-test", session, sid, {
        "action": {"type": "accept", "term_sheet_id": reply["term_sheets"][0]["term_sheet_id"]},
    })["result"]
    assert closed["c_best"] == total_cost(case, {"unit_price": 88})
    assert closed["score"] == pytest.approx((110 - accepted) / 22)


def test_failed_local_runs_stay_in_the_denominator(monkeypatch):
    scenario = stress.scenarios("dev")[0]
    monkeypatch.setattr(stress, "scenarios", lambda _: [scenario])

    class BrokenBuyer:
        def decide(self, *_):
            raise ValueError("local injected failure")

    result = stress.evaluate(new_agent=BrokenBuyer)
    assert result["mean_score"] == 0
    assert result["errors"] == 1
    assert result["runs"][0]["error"] == "ValueError: local injected failure"
