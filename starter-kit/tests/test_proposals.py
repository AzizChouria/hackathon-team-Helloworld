"""Model package policy tests: mock models and localhost only, never hosted endpoints."""
import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from arena_kit.agents import proposals
from arena_kit.agents.hybrid import HybridAgent
from arena_kit.agents.strategy import BODIES
from arena_kit.cost import total_cost
from arena_kit.sim import load_cases


@pytest.fixture
def case(monkeypatch):
    monkeypatch.setenv("HYBRID_PROPOSAL_MODE", "model")
    monkeypatch.setenv("HYBRID_LLM_CALLS_PER_CASE", "5")
    return copy.deepcopy(load_cases()["case:S01"])


def thread(price=20):
    return [{"from": "sales", "status": "open", "body": "Payment timing matters to us.",
             "term_sheets": [{"term_sheet_id": "offer:local", "terms":
                              {"unit_price": price, "payment_days": 60}}]}]


def response(prices):
    return {"suppliers": {sid: {"packages": [{"unit_price": price, "payment_days": 60}],
                               "trade": "Private trade description", "evidence": [],
                               "question": "priorities", "body": BODIES[0]}
                          for sid, price in prices.items()}}


class Model:
    timeout = .01

    def __init__(self, *replies):
        self.replies = list(replies)
        self.contexts = []
        self.schemas = []

    def __call__(self, system, user, *, schema):
        self.contexts.append(json.loads(user))
        self.schemas.append(schema)
        reply = self.replies[min(len(self.contexts) - 1, len(self.replies) - 1)]
        if isinstance(reply, Exception):
            raise reply
        return copy.deepcopy(reply)


def test_prices_are_model_authored_and_no_legacy_generator(case, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Legacy generator must never run in model mode")
    monkeypatch.setattr("arena_kit.agents.hybrid.candidates", forbidden)
    model = Model(response({"A": 17.37}))
    agent = HybridAgent(model)
    decision = agent.decide(case, {"A": thread()})
    assert decision["message"]["term_sheets"][0]["terms"]["unit_price"] == 17.37
    assert agent.diagnostics[-1]["source"] == "model"
    assert not agent.diagnostics[-1]["fallback"]
    assert "Private trade" not in decision["message"]["body"]
    assert "buyer_economics_private" in model.contexts[0]


def test_multi_supplier_single_request_and_global_cost_comparison(case):
    model = Model(response({"A": 16.83, "B": 17.21}))
    agent = HybridAgent(model)
    actions = agent.decide_many(case, {"A": thread(20), "B": thread(18)})
    assert {a["supplier_id"] for a in actions} == {"A", "B"}
    assert len(model.contexts) == 1
    assert set(model.schemas[0]["properties"]["suppliers"]["properties"]) == {"A", "B"}
    assert model.contexts[0]["must_improve_total_eur"] == total_cost(case, {"unit_price": 18, "payment_days": 60})


@pytest.mark.parametrize("bad", [True, "17", 0, -1, float("inf"), float("nan")])
def test_invalid_model_price_never_sent(case, bad):
    model = Model(response({"A": bad}))
    agent = HybridAgent(model)
    move = agent.decide(case, {"A": thread()})
    assert move["message"]["action"]["type"] == "accept"
    assert agent.diagnostics[-1]["fallback"]
    assert len(model.contexts) <= 2


def test_cost_feedback_repair_does_not_clamp_model_price(case):
    bad = response({"A": 19.99})
    bad["suppliers"]["A"]["packages"][0]["payment_days"] = 14
    model = Model(bad, response({"A": 18.43}))
    agent = HybridAgent(model)
    move = agent.decide(case, {"A": thread()})
    assert move["message"]["term_sheets"][0]["terms"]["unit_price"] == 18.43
    feedback = model.contexts[1]["validation_feedback_private"][0]
    assert not feedback["valid"] and feedback["total_eur"] > total_cost(case, thread()[0]["term_sheets"][0]["terms"])
    assert "payment_terms" in feedback["components_eur"]
    assert agent.diagnostics[-1]["repairs"] == 1


@pytest.mark.parametrize("mutation", ["missing", "extra", "off_domain", "must_have", "wrong_supplier", "bad_citation"])
def test_schema_and_constraints(case, mutation):
    draft = response({"A": 17.37})
    p = draft["suppliers"]["A"]
    if mutation == "missing":
        del p["packages"][0]["payment_days"]
    elif mutation == "extra":
        p["packages"][0]["secret"] = "bad"
    elif mutation == "off_domain":
        p["packages"][0]["payment_days"] = 51
    elif mutation == "must_have":
        case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 90}]
    elif mutation == "wrong_supplier":
        draft["suppliers"]["unknown"] = draft["suppliers"].pop("A")
    else:
        p["evidence"] = [9999]
    agent = HybridAgent(Model(draft))
    move = agent.decide(case, {"A": thread()})
    assert "term_sheets" not in move["message"]
    assert agent.diagnostics[-1]["fallback"]


def test_provider_failure_clarifies_once_without_retry_or_invented_terms(case):
    model = Model(TimeoutError("local test"))
    agent = HybridAgent(model)
    move = agent.decide(case, {"A": thread()})
    assert len(model.contexts) == 1
    assert "action" not in move["message"] and "term_sheets" not in move["message"]
    assert agent.diagnostics[-1]["source"] == "clarification_recovery"


def test_call_budget_does_not_trigger_legacy_mode(case, monkeypatch):
    monkeypatch.setenv("HYBRID_LLM_CALLS_PER_CASE", "0")
    model = Model(response({"A": 17.37}))
    agent = HybridAgent(model)
    assert agent.decide(case, {"A": thread()})["message"]["action"]["type"] == "accept"
    assert not model.contexts
    assert agent.diagnostics[-1]["fallback_reason"] == "call_budget"


def test_deadline_reserves_time_for_sending(case):
    events = thread()
    events[0]["_received_at"] = time.monotonic() - 20
    model = Model(response({"A": 17.37}))
    model.timeout = 22
    agent = HybridAgent(model)
    assert agent.decide(case, {"A": events})["message"]["action"]["type"] == "accept"
    assert not model.contexts


def test_no_duplicate_packages(case):
    events = thread()
    events.insert(0, {"from": "buyer", "term_sheets": [{"terms": {"unit_price": 17.37, "payment_days": 60}}]})
    agent = HybridAgent(Model(response({"A": 17.37})))
    assert "term_sheets" not in agent.decide(case, {"A": events})["message"]
    assert agent.diagnostics[-1]["fallback"]


def test_strict_schema_nested_index_clause(case):
    clause = {"series": "local", "material_share": .3, "base_month": "2026-08", "deadband_pct": 5}
    case["negotiable"].append("index_clause")
    case["term_options"]["index_clause"] = [None, clause]
    schema = proposals.response_schema(case, {"A": thread()})
    def visit(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(schema)
    assert "anyOf" in json.dumps(schema)


def test_parallel_case_isolation_and_no_hidden_benchmark_context(case):
    def run(i):
        c = copy.deepcopy(case)
        c.update(case_id=f"local:{i}", c_best=123456789, leaderboard="PRIVATE_SENTINEL")
        model = Model(response({str(i): 17.37}))
        agent = HybridAgent(model)
        agent.decide(c, {str(i): thread()})
        return model.contexts[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        contexts = list(pool.map(run, range(2)))
    assert set(contexts[0]["suppliers"]) == {"0"}
    assert set(contexts[1]["suppliers"]) == {"1"}
    assert "PRIVATE_SENTINEL" not in json.dumps(contexts)
    assert "123456789" not in json.dumps(contexts)


def test_mandatory_context_not_silently_truncated():
    with pytest.raises(ValueError, match="Mandatory"):
        proposals.compact({"suppliers": {}, "constraints": "x" * 13000})


def test_historical_runner_cannot_use_wrong_model_cost_forecast(monkeypatch):
    from arena_kit import benchmark
    monkeypatch.setenv("HYBRID_PROPOSAL_MODE", "model")
    with pytest.raises(ValueError, match="Historical benchmark"):
        benchmark.run("case:P01")


@pytest.mark.parametrize("inject_timeout", [False, True])
def test_model_proposals_through_all_local_simulator_cases(sim, monkeypatch, inject_timeout):
    from arena_kit.client import ArenaClient
    from arena_kit.cost import complete_offer
    from arena_kit.play import RemoteTable, play_all
    monkeypatch.setenv("HYBRID_PROPOSAL_MODE", "model")
    monkeypatch.setenv("HYBRID_LLM_CALLS_PER_CASE", "5")
    class FixtureModel:
        timeout = .01
        def __init__(self):
            self.calls = 0
        def __call__(self, system, user, *, schema):
            self.calls += 1
            if inject_timeout and self.calls == 1:
                raise TimeoutError("Injected model outage")
            ctx = json.loads(user)
            draft = {"suppliers": {}}
            for sid, supplier in ctx["suppliers"].items():
                # Scripted test double only: it checks transport, not model quality.
                case = {"buyer": ctx["buyer_economics_private"], "negotiable": ctx["negotiable"],
                        "fixed_terms": ctx["fixed_terms"]}
                terms = complete_offer(case, supplier["standing_terms"][0])
                terms["unit_price"] = round(terms["unit_price"] - .01, 2)
                draft["suppliers"][sid] = {"packages": [terms], "trade": "Test fixture", "evidence": [],
                                            "body": BODIES[0], "question": "priorities"}
            return draft
    signup = ArenaClient(sim[0], rate=1000)
    key = signup.register("model-proposal-local", "sim")["api_key"]
    client = ArenaClient(sim[0], key, rate=1000)
    ids = [c["case_id"] for c in client.cases()]
    agents = []
    def factory():
        agent = HybridAgent(FixtureModel(), proposal_mode="model")
        agents.append(agent)
        return agent
    results = play_all(lambda: RemoteTable(client), ids, factory, parallel=3)
    assert len(results) == 3
    assert all(isinstance(r, dict) and r["ended"] and r["must_haves_ok"] for r in results.values())
    assert all(any(d["source"] == "model" for d in a.diagnostics) for a in agents)
    if inject_timeout:
        assert all(a.recoveries == 1 for a in agents)


def advance(events, move):
    return events + [{**move["message"], "from": "buyer"}, copy.deepcopy(events[-1])]


def test_second_transient_failure_closes_without_endless_questions(case):
    model = Model(TimeoutError())
    agent = HybridAgent(model)
    events = thread()
    first = agent.decide(case, {"A": events})
    second = agent.decide(case, {"A": advance(events, first)})
    assert second["message"]["action"]["type"] == "accept"
    assert len(model.contexts) == 2
    assert agent.recoveries == 1


def test_new_supplier_reply_allows_fresh_model_proposal_after_timeout(case):
    model = Model(TimeoutError(), response({"A": 17.37}))
    agent = HybridAgent(model)
    events = thread()
    first = agent.decide(case, {"A": events})
    second = agent.decide(case, {"A": advance(events, first)})
    assert second["message"]["term_sheets"][0]["terms"]["unit_price"] == 17.37
    assert len(model.contexts) == 2
    assert not agent.diagnostics[-1]["fallback"]


@pytest.mark.parametrize("status,recover", [(429, True), (503, True), (401, False), (404, False), (400, False)])
def test_recovery_only_for_transient_provider_errors(case, status, recover):
    from arena_kit.agents.strategy import ProviderError
    agent = HybridAgent(Model(ProviderError(status)))
    move = agent.decide(case, {"A": thread()})
    assert ("action" not in move["message"]) == recover


@pytest.mark.parametrize("limit", ["calls", "rounds", "deadline", "disabled"])
def test_no_recovery_without_safe_future_turn(case, monkeypatch, limit):
    if limit == "calls":
        monkeypatch.setenv("HYBRID_LLM_CALLS_PER_CASE", "1")
    elif limit == "rounds":
        case["round_limit"] = 2
    elif limit == "disabled":
        monkeypatch.setenv("HYBRID_RECOVERY_TURNS", "0")
    model = Model(TimeoutError())
    agent = HybridAgent(model)
    if limit == "deadline":
        clock = [100.0]
        monkeypatch.setattr("arena_kit.agents.hybrid.time.monotonic", lambda: clock[0])
        def delayed(*args, **kwargs):
            clock[0] += 31
            raise TimeoutError()
        agent.complete = delayed
    move = agent.decide(case, {"A": thread()})
    assert move["message"]["action"]["type"] == "accept"
    assert agent.recoveries == 0


def test_recovery_services_all_rfq_suppliers_and_resets_between_cases(case):
    agent = HybridAgent(Model(TimeoutError()))
    moves = agent.decide_many(case, {"A": thread(), "B": thread(18)})
    assert {m["supplier_id"] for m in moves} == {"A", "B"}
    assert all("action" not in m["message"] for m in moves)
    case["case_id"] = "local:new"
    assert "action" not in agent.decide(case, {"C": thread()})["message"]
    assert agent.recoveries == 1


def test_valid_packages_survive_optional_repair_timeout(case):
    draft = response({"A": 17.37})
    draft["suppliers"]["A"]["packages"].append({"unit_price": 25, "payment_days": 14})
    agent = HybridAgent(Model(draft, TimeoutError()))
    move = agent.decide(case, {"A": thread()})
    assert move["message"]["term_sheets"] == [{"terms": {"unit_price": 17.37, "payment_days": 60}}]
    assert agent.diagnostics[-1]["source"] == "validated_before_repair_error"


def test_timeout_does_not_risk_an_earned_concession(case):
    agent = HybridAgent(Model(response({"A": 17.37}), TimeoutError()))
    first = agent.decide(case, {"A": thread(20)})
    events = thread(20) + [{**first["message"], "from": "buyer"}] + thread(18)
    move = agent.decide(case, {"A": events})
    assert move["message"]["action"]["type"] == "accept"
    assert agent.recoveries == 0


def test_full_22_second_timeout_still_leaves_safe_clarification_window(case, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("arena_kit.agents.hybrid.time.monotonic", lambda: clock[0])
    def timeout(*args, **kwargs):
        clock[0] += 22
        raise TimeoutError()
    agent = HybridAgent(timeout)
    move = agent.decide(case, {"A": thread()})
    assert "action" not in move["message"]
    assert agent.diagnostics[-1]["decision_s"] == 22
