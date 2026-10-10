"""Local-only adversarial checks; no hosted clients or paid model calls."""
import copy
import threading
import time

import httpx
import pytest

from arena_kit.agents.hybrid import HybridAgent
from arena_kit.agents.intelligence import Intelligence
from arena_kit.agents.optimizer import valid
from arena_kit.cost import complete_offer, total_cost
from arena_kit.data import DataPackage
from arena_kit.play import play
from arena_kit.sim import load_cases


@pytest.fixture
def case():
    return copy.deepcopy(next(iter(load_cases().values())))


def mail(price=20, sid="A", **extra):
    return {"from": "supplier", "status": "open", "body": "", "attachments": [],
            "term_sheets": [{"term_sheet_id": f"offer:{sid}:{price}", "terms": {"unit_price": price}}], **extra}


@pytest.mark.parametrize("slow_sid", ["A", "B"])
def test_rfq_closes_ready_thread_before_slow_reply(case, slow_sid):
    case["suppliers"] = ["A", "B"]
    release = threading.Event()
    finished = threading.Event()
    calls = []
    fast_sid = "B" if slow_sid == "A" else "A"

    class Table:
        def open(self, _):
            return case, {s: [mail(20, s)] for s in case["suppliers"]}

        def send(self, sid, message):
            calls.append(sid)
            if sid == slow_sid:
                try:
                    assert release.wait(3), "Coordinator waited for the slowest reply"
                finally:
                    finished.set()
            return mail(18, sid, status="final_offer")

        def close(self, sid, message):
            assert sid == fast_sid
            assert not finished.is_set()
            release.set()
            return {"ended": True, "deal": True, "supplier_id": sid}

    agent = HybridAgent()
    agent.response_guard_s = 0.15  # compress time only, preserve actual scheduling
    try:
        result = play(Table(), case["case_id"], agent)
        assert result["supplier_id"] == fast_sid
        assert sorted(calls) == ["A", "B"]
        assert finished.wait(2)
    finally:
        release.set()


def test_ambiguous_post_is_not_reissued(case):
    calls = []

    class Table:
        def open(self, _):
            return case, {"A": [mail()]}

        def send(self, sid, message):
            calls.append(sid)
            raise httpx.ReadTimeout("ambiguous completion")

    with pytest.raises(httpx.ReadTimeout):
        play(Table(), case["case_id"], HybridAgent())
    assert calls == ["A"]


def test_model_skipped_when_its_budget_cannot_fit(case):
    calls = []

    def model(*_):
        calls.append(True)
        raise AssertionError("Should not be called")

    model.timeout = 30
    agent = HybridAgent(model)
    agent.decide(case, {"A": [mail(_received_at=time.monotonic() - 25)]})
    assert not calls
    assert not agent.diagnostics[-1]["model_called"]


def test_all_proposed_packages_improve_best_standing_cost(case):
    threads = {"A": [mail(20)], "B": [mail(18)]}
    agent = HybridAgent()
    for decision in agent.decide_many(case, threads):
        for sheet in decision["message"].get("term_sheets", []):
            assert total_cost(case, sheet["terms"]) < total_cost(case, {"unit_price": 18})


def test_no_cost_improving_package_closes_existing_offer(case, monkeypatch):
    import arena_kit.agents.hybrid as module
    expensive = complete_offer(case, {"unit_price": 100})
    monkeypatch.setattr(module, "candidates", lambda *args, **kwargs: [expensive])
    move = HybridAgent().decide(case, {"A": [mail()]})
    assert move["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:A:20"}


def test_missing_standard_is_not_replaced_by_buyer_preference(case):
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 45}]
    assert not valid(case, {"unit_price": 20}, {"payment_days": None})
    assert valid(case, {"unit_price": 20, "payment_days": 60})
    case["fixed_terms"]["payment_days"] = 60
    assert valid(case, {"unit_price": 20})


def test_sunday_trigger_has_first_priority_without_sqlite(tmp_path, case):
    import json
    ref = "doc:sunday-trigger"
    (tmp_path / "facts.json").write_text(json.dumps({ref: {"body": "Fresh negotiation trigger"}}))
    case["trigger_doc"] = ref
    intel = Intelligence(DataPackage(tmp_path))
    assert intel.prepare(case, case["suppliers"][0])["notes"][0] == "Fresh negotiation trigger"


def test_same_case_id_changed_scenario_invalidates_brief(tmp_path, case):
    import json
    sid = case["suppliers"][0]
    (tmp_path / "facts.json").write_text(json.dumps({"sc:new": {"supplier": sid, "ppm": 555}}))
    case["facts"] = {}
    intel = Intelligence(DataPackage(tmp_path))
    assert not intel.prepare(case, sid)["evidence"]
    case["type"] = "quality"
    assert "555 ppm" in intel.prepare(case, sid)["evidence"][0]["text"]


def test_deteriorating_offer_does_not_trigger_more_concessions(case):
    agent = HybridAgent()
    threads = {"A": [mail(20)]}
    first = agent.decide(case, threads)
    threads["A"].extend([{**first["message"], "from": "buyer"}, mail(19)])
    second = agent.decide(case, threads)
    threads["A"].extend([{**second["message"], "from": "buyer"}, mail(19.2)])
    final = agent.decide(case, threads)
    assert final["message"]["action"]["type"] == "accept"
    # Old 19.0 quote was withdrawn: never accept a historical/non-standing identifier.
    assert final["message"]["action"]["term_sheet_id"] == "offer:A:19.2"


def test_second_model_call_interprets_first_supplier_reply(case):
    from arena_kit.agents.strategy import BODIES
    calls = []

    def model(system, user):
        calls.append(user)
        return {"package_order": [0], "evidence": [], "question": "priorities", "body": BODIES[0]}

    agent = HybridAgent(model)
    threads = {"A": [mail()]}
    action = agent.decide(case, threads)
    threads["A"].extend([{**action["message"], "from": "buyer"}, mail(19)])
    agent.decide(case, threads)
    assert len(calls) == 2


def test_repeated_opening_does_not_trigger_premature_close(case):
    agent = HybridAgent()
    threads = {"A": [mail(20)]}
    for _ in range(3):
        move = agent.decide(case, threads)
        assert not move["message"].get("action")
        threads["A"].extend([{**move["message"], "from": "buyer"}, mail(20)])


def test_model_receives_history_and_python_costs(case):
    import json

    from arena_kit.agents.strategy import BODIES
    captured = []

    def model(system, user):
        context = json.loads(user)
        captured.append(context)
        assert context["package_costs_eur"] == [total_cost(case, p) for p in context["packages"]]
        assert len(user.encode()) <= 12000
        return {"package_order": [0], "evidence": [], "question": "priorities", "body": BODIES[0]}

    agent = HybridAgent(model)
    threads = {"A": [mail(body="Payment timing matters to us.")]}
    action = agent.decide(case, threads)
    threads["A"].extend([{**action["message"], "from": "buyer"}, mail(19, body="Please trade payment for price.")])
    agent.decide(case, threads)
    assert captured[1]["buyer_round"] == 1
    assert captured[1]["recent_exchange"][0]["body"] == "Payment timing matters to us."
    assert captured[1]["moves_remaining"] == case["round_limit"] - 1


def test_beam_keeps_expensive_hard_constraint_before_truncation(case):
    from arena_kit.agents.optimizer import candidates
    case["negotiable"] = ["unit_price", "payment_days", "tooling_eur"]
    case["fixed_terms"].pop("tooling_eur", None)
    case["term_options"] = {"payment_days": [14, 90], "tooling_eur": list(range(100))}
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": "==", "value": 14}]
    proposals = candidates(case, {"unit_price": 20}, {})
    assert proposals and all(p["payment_days"] == 14 for p in proposals)
    assert min(total_cost(case, p) for p in proposals) == total_cost(case, {"unit_price": 18, "payment_days": 14})


def test_candidate_diversity_selected_inside_economic_ceiling(case):
    from arena_kit.agents.optimizer import candidates
    unconstrained = candidates(case, {"unit_price": 20}, {})
    ceiling = total_cost(case, unconstrained[0]) + 1
    proposals = candidates(case, {"unit_price": 20}, {}, ceiling=ceiling)
    assert proposals and all(total_cost(case, p) < ceiling - .01 for p in proposals)


def test_supplier_standard_outside_options_remains_available(case):
    from arena_kit.agents.optimizer import candidates
    standard = {"payment_days": 51}
    proposals = candidates(case, {"unit_price": 20, "payment_days": 51}, standard, turn=1)
    assert any(p["payment_days"] == 51 for p in proposals)
    assert all(valid(case, p, standard, complete=True) for p in proposals)


def test_unknown_standard_does_not_erase_numeric_defaults(case):
    from arena_kit.agents.optimizer import candidates
    assert candidates(case, {"unit_price": 20}, {"payment_days": None})


def test_conditional_discount_does_not_reset_main_concession_anchor(case):
    from arena_kit.agents.optimizer import candidates
    case["buyer"]["interest_rate"] = .20
    previous = [{"unit_price": 18, "payment_days": 90}, {"unit_price": 17.9, "payment_days": 14}]
    base = candidates(case, {"unit_price": 18.3}, {}, turn=3, previous=previous[:1])
    conditional = candidates(case, {"unit_price": 18.3}, {}, turn=3, previous=previous)
    assert conditional[0] == base[0]


def test_preference_sensitive_supplier_can_accept_reciprocal_package(case):
    from arena_kit.tradeoff_eval import PreferenceTable
    table = PreferenceTable(case, payment=30, floor=.94, flexible=False)
    result = play(table, case["case_id"], HybridAgent())
    assert result["deal"] and result["must_haves_ok"]
    assert result["terms"]["payment_days"] == 30
    assert result["c_deal"] < result["c_open"]


def test_last_counter_after_stalemate_improves_price_without_overspending(case):
    agent = HybridAgent()
    threads = {"A": [mail(20)]}
    proposals = []
    for _ in range(5):
        move = agent.decide(case, threads)
        assert not move["message"].get("action")
        proposals.append(move["message"]["term_sheets"])
        threads["A"].extend([{**move["message"], "from": "buyer"}, mail(20)])
    assert len(proposals[-1]) == 1
    assert proposals[-1][0]["terms"]["unit_price"] >= 19.6
    assert all(total_cost(case, p["terms"]) < total_cost(case, {"unit_price": 20}) for p in proposals[-1])
    assert agent.decide(case, threads)["message"]["action"]["type"] == "accept"


def test_explicit_no_index_standard_is_a_real_option(case):
    from arena_kit.agents.optimizer import candidates
    case["negotiable"].append("index_clause")
    case["fixed_terms"].pop("index_clause", None)
    clause = {"series": "synthetic", "material_share": .5, "deadband_pct": 0, "base_month": "2026-08"}
    case["term_options"]["index_clause"] = [clause]
    case["buyer"]["index_paths"] = {"synthetic": .1}
    proposals = candidates(case, {"unit_price": 20}, {"index_clause": None})
    assert proposals[0]["index_clause"] is None
