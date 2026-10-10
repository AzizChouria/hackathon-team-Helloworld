"""Combined policy regressions: no hosted endpoints or paid model requests."""
import copy
import json
import time

import pytest

from arena_kit.agents.combined import CombinedAgent
from arena_kit.agents.proposals import check_terms
from arena_kit.buyer_simulation import LocalTable
from arena_kit.cli import agent_factory
from arena_kit.cost import total_cost
from arena_kit.data import DataPackage
from arena_kit.docs import standard_terms
from arena_kit.play import fetch_documents, play
from arena_kit.research import Evidence
from arena_kit.sim import load_cases


@pytest.fixture
def opened():
    case = copy.deepcopy(load_cases()["case:S01"])
    table = LocalTable(case)
    case, threads = table.open(case["case_id"])
    for events in threads.values():
        fetch_documents(table, events[-1])
    return case, threads


def broken_advisor(*args, **kwargs):
    raise TimeoutError("synthetic bounded timeout")


@pytest.mark.parametrize("case_id", ["case:S01", "case:S02", "case:S03"])
@pytest.mark.parametrize("advisor", [None, broken_advisor])
def test_complete_local_cases_despite_model_failure(case_id, advisor):
    case = load_cases()[case_id]
    table = LocalTable(case)
    agent = CombinedAgent(advisor)
    result = play(table, case_id, agent)
    assert result["ended"] and result["deal"] and result["must_haves_ok"]
    assert agent.diagnostics
    if advisor:
        assert any(d["fallback"] for d in agent.diagnostics)
        assert agent.advisor_calls <= agent.max_calls


def test_model_cannot_change_economic_packages(opened):
    case, threads = opened
    expected = CombinedAgent().decide(case, copy.deepcopy(threads))
    calls = []

    def advisor(system, context, **kwargs):
        calls.append(kwargs["schema"])
        return {"tactic": "approval", "evidence": []}

    agent = CombinedAgent(advisor)
    actual = agent.decide(case, copy.deepcopy(threads))
    assert calls and not calls[0]["additionalProperties"]
    assert actual["message"]["term_sheets"] == expected["message"]["term_sheets"]
    assert agent.diagnostics[-1]["model_called"]
    assert not agent.diagnostics[-1]["fallback"]


@pytest.mark.parametrize("answer", [None, {}, {"tactic": "approval", "evidence": [999]},
                                     {"tactic": "approval", "evidence": [True]},
                                     {"tactic": "approval", "evidence": [], "price": 1}])
def test_bad_model_answer_keeps_valid_counter(opened, answer):
    case, threads = opened
    agent = CombinedAgent(lambda *a, **k: answer)
    decision = agent.decide(case, threads)
    assert agent.diagnostics[-1]["fallback"]
    std = standard_terms(threads[decision["supplier_id"]])
    for sheet in decision["message"]["term_sheets"]:
        check_terms(case, sheet["terms"], std)


def test_model_skipped_when_deadline_is_close(opened):
    case, threads = opened
    calls = []
    for events in threads.values():
        events[-1]["_received_at"] = time.monotonic() - 20
    agent = CombinedAgent(lambda *a, **k: calls.append(1))
    agent.decide(case, threads)
    assert not calls
    assert agent.diagnostics[-1]["model_skipped"] == "deadline"


def test_missing_committed_payment_cannot_be_accepted(opened):
    case, threads = opened
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 45}]
    sid = next(iter(threads))
    threads = {sid: [{"from": "supplier", "status": "final_offer", "body": "Final",
                      "term_sheets": [{"term_sheet_id": "quote:incomplete", "terms": {"unit_price": 1}}]}]}
    decision = CombinedAgent().close(case, threads)
    assert decision["message"]["action"]["type"] == "walk_away"


def test_pending_thread_never_receives_a_move(opened):
    case, threads = opened
    agent = CombinedAgent()
    assert agent.decide_ready(case, threads, set()) is None


def test_ready_rfq_close_selects_cheapest_available_not_pending():
    case = copy.deepcopy(load_cases()["case:S02"])
    table = LocalTable(case)
    case, threads = table.open(case["case_id"])
    for events in threads.values():
        fetch_documents(table, events[-1])
        events[-1]["status"] = "final_offer"
        events[-1]["_received_at"] = time.monotonic() - 36
    sid = next(iter(threads))
    decision = CombinedAgent().decide_ready(case, threads, {sid})
    assert decision["supplier_id"] == sid
    assert decision["message"]["action"]["type"] == "accept"


def test_default_factory_has_no_model_and_isolates_state(monkeypatch):
    monkeypatch.delenv("HYBRID_PROPOSAL_MODE", raising=False)
    monkeypatch.delenv("HYBRID_TACTICAL_LLM", raising=False)
    factory = agent_factory("hybrid", None)
    a, b = factory(), factory()
    assert isinstance(a, CombinedAgent) and a.advisor is None
    assert a.research is not b.research
    assert a.intelligence.package is not b.intelligence.package
    a.diagnostics.append({"private": True})
    assert b.diagnostics == []


def test_explicit_case_change_resets_tactics_and_observations(opened):
    case, threads = opened
    agent = CombinedAgent(broken_advisor)
    agent.decide(case, threads)
    assert agent.advisor_calls == 1
    another = copy.deepcopy(case)
    another["case_id"] = "case:unseen"
    agent.prepare(another)
    assert not agent.diagnostics and agent.advisor_calls == 0
    assert not agent.reserved_refs


def test_proposals_improve_on_ready_quote(opened):
    case, threads = opened
    decision = CombinedAgent().decide(case, threads)
    sid = decision["supplier_id"]
    std = standard_terms(threads[sid])
    standing = min(total_cost(case, s["terms"], std) for s in threads[sid][-1]["term_sheets"])
    assert all(total_cost(case, s["terms"], std) < standing
               for s in decision["message"]["term_sheets"])


def test_refreshed_dataset_rebuilds_research(opened, tmp_path):
    case, _ = opened
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps({"fact:refresh": {"value": 1}}))
    agent = CombinedAgent(package=DataPackage(tmp_path))
    agent.prepare(case)
    assert agent.research.fact(case, "fact:refresh")["value"] == 1
    facts.write_text(json.dumps({"fact:refresh": {"value": 123456}}))
    agent.prepare(case)
    assert agent.research.fact(case, "fact:refresh")["value"] == 123456


def test_uncitable_claim_is_removed(opened, monkeypatch):
    from arena_kit.agents.buyer import BuyerAgent

    case, threads = opened
    agent = CombinedAgent()
    agent.prepare(case)
    monkeypatch.setattr(BuyerAgent, "unused_evidence", lambda *args: [
        Evidence("An unsupported assertion", ("invented:id",), "cost")])
    assert agent.unused_evidence(case, next(iter(threads)), threads) == []


def test_zero_advisor_budget_keeps_computed_strategy(opened, monkeypatch):
    monkeypatch.setenv("HYBRID_LLM_CALLS_PER_CASE", "0")
    case, threads = opened
    calls = []
    agent = CombinedAgent(lambda *a, **k: calls.append(1))
    assert agent.decide(case, threads)["message"]["term_sheets"]
    assert not calls and agent.diagnostics[-1]["model_skipped"] == "call_budget"
