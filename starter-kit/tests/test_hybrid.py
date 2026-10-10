import copy
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from arena_kit.agents.decision import close
from arena_kit.agents.hybrid import HybridAgent
from arena_kit.agents.intelligence import Intelligence
from arena_kit.agents.optimizer import candidates, standing_offers, valid
from arena_kit.agents.strategy import BudgetExceeded, OpenAI, validate
from arena_kit.client import ArenaClient
from arena_kit.cost import complete_offer, total_cost
from arena_kit.data import DataPackage
from arena_kit.play import RemoteTable, play_all
from arena_kit.sim import load_cases


@pytest.fixture
def case():
    return copy.deepcopy(next(iter(load_cases().values())))


def thread(price=20, status="open", supplier="A", **terms):
    return [{"from": "sales", "status": status, "body": "", "term_sheets": [
        {"term_sheet_id": f"offer:{supplier}", "terms": {"unit_price": price, **terms}}]}]


def test_full_domain_candidates_and_nonrepeat(case):
    previous = candidates(case, {"unit_price": 20}, {})
    assert previous and all(valid(case, t, complete=True) for t in previous)
    again = candidates(case, {"unit_price": 20}, {}, turn=1, previous=previous)
    assert not any(t in previous for t in again)


@pytest.mark.parametrize("price", [float("nan"), float("inf"), -1, 0, True, "10"])
def test_reject_bad_price(case, price):
    assert not valid(case, {"unit_price": price})


def test_constraints_and_standard_values(case):
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 45}]
    assert not valid(case, {"unit_price": 20, "payment_days": 14})
    assert valid(case, {"unit_price": 20}, {"payment_days": 45})
    assert not valid(case, {"unit_price": 20, "payment_days": 51})
    assert valid(case, {"unit_price": 20, "payment_days": 51}, {"payment_days": 51})


def test_close_chooses_best_all_sheets(case):
    threads = {"A": thread(20), "B": thread(18, supplier="B")}
    threads["B"][0]["term_sheets"].append({"term_sheet_id": "offer:B2", "terms": {"unit_price": 17}})
    assert close(case, threads)["message"]["action"]["term_sheet_id"] == "offer:B2"
    threads["B"][0]["status"] = "walked_away"
    assert close(case, threads)["supplier_id"] == "A"


def test_no_deal_and_invalid_offers(case):
    case["buyer"]["alternative"] = {"kind": "quote", "terms": {"unit_price": 1}}
    assert close(case, {"A": thread(20)})["message"]["action"]["type"] == "walk_away"
    assert close(case, {"A": thread(0)})["message"]["action"]["type"] == "walk_away"


def test_model_cannot_override_cheap_standing_or_must_haves(case):
    agent = HybridAgent(lambda *_: {"action": "accept", "supplier_id": "expensive"})
    threads = {"A": thread(20, "final_offer"), "B": thread(15, supplier="B")}
    assert agent.decide(case, threads)["supplier_id"] == "B"


def test_fallback_is_valid_and_case_isolated(case):
    def broken(*_):
        raise TimeoutError
    agent = HybridAgent(broken)
    threads = {case["suppliers"][0]: thread()}
    result = agent.decide(case, threads)
    assert all(valid(case, x["terms"], complete=True) for x in result["message"]["term_sheets"])
    assert agent.diagnostics[-1]["fallback"]
    other = copy.deepcopy(case)
    other["case_id"] = "case:new"
    agent.decide(other, threads)
    assert agent.calls == 1


def test_intelligence_missing_and_changed_dataset(tmp_path, case):
    path = tmp_path / "facts.json"
    path.write_text("{}")
    intel = Intelligence(DataPackage(tmp_path))
    before = intel.prepare(case, case["suppliers"][0])
    assert not before["evidence"]
    path.write_text(json.dumps({"sc:x@2026Q3": {"supplier": case["suppliers"][0], "ppm": 700, "otd_pct": 90}}))
    intel.refresh()
    case["type"] = "quality"
    after = intel.prepare(case, case["suppliers"][0])
    assert after["fingerprint"] != before["fingerprint"]
    assert "700 ppm" in after["evidence"][0]["text"]


@pytest.fixture
def model_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gpt-6-astra")
    monkeypatch.setenv("LLM_EFFORT", "high")
    monkeypatch.setenv("LLM_ENDPOINT", "responses")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "1200")
    monkeypatch.setenv("LLM_BUDGET_USD", "5")


def response_data(text=None, **overrides):
    value = {"package_order": [0], "evidence": [], "question": "cost", "body": "Thank you."}
    return {"model": "gpt-6-astra", "status": "completed",
            "usage": {"input_tokens": 100, "output_tokens": 30,
                      "output_tokens_details": {"reasoning_tokens": 10}},
            "output": [{"content": [{"type": "output_text", "text": text or json.dumps(value)}]}], **overrides}


def test_responses_transport_usage_and_parameters(tmp_path, model_env):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=response_data())
    api = OpenAI(transport=httpx.MockTransport(handler), ledger=tmp_path / "usage.jsonl")
    assert api("system", "user")["question"] == "cost"
    assert seen[0]["reasoning"] == {"effort": "high"}
    assert "temperature" not in seen[0]
    assert seen[0]["text"]["format"]["strict"]
    assert api.metrics[0]["reasoning_tokens"] == 10
    assert api.spent() == pytest.approx(0.0025)


@pytest.mark.parametrize("mode", ["incomplete", "refusal", "empty", "rate_limit", "timeout", "bad_json"])
def test_provider_failures_no_retry(tmp_path, model_env, mode):
    calls = []
    def handler(request):
        calls.append(request)
        if mode == "timeout":
            raise httpx.ReadTimeout("test")
        if mode == "rate_limit":
            return httpx.Response(429, json={"error": {"message": "do not log"}})
        data = response_data()
        if mode == "incomplete":
            data["status"] = "incomplete"
        elif mode == "refusal":
            data["output"] = [{"content": [{"type": "refusal"}]}]
        elif mode == "empty":
            data["output"] = []
        elif mode == "bad_json":
            data = response_data("nonsense")
        return httpx.Response(200, json=data)
    api = OpenAI(transport=httpx.MockTransport(handler), ledger=tmp_path / "usage.jsonl")
    with pytest.raises((ValueError, RuntimeError, httpx.ReadTimeout)):
        api("s", "u")
    assert len(calls) == 1 and api.metrics[-1]["fallback"]
    assert api.spent() > 0


def test_chat_effort_and_structured_schema(tmp_path, model_env, monkeypatch):
    monkeypatch.setenv("LLM_ENDPOINT", "chat")
    def handler(request):
        b = json.loads(request.content)
        assert b["reasoning_effort"] == "high"
        assert b["response_format"]["json_schema"]["strict"]
        return httpx.Response(200, json={"model": "gpt-6-astra", "choices": [
            {"finish_reason": "stop", "message": {"content": "{}"}}]})
    api = OpenAI(transport=httpx.MockTransport(handler), ledger=tmp_path / "u")
    assert api("s", "u") == {}


def test_parallel_budget_reservations_persist(tmp_path, model_env, monkeypatch):
    monkeypatch.setenv("LLM_BUDGET_USD", "0.07")
    def handler(_):
        raise httpx.ReadTimeout("unknown billing")
    path = tmp_path / "usage.jsonl"
    def call(_):
        api = OpenAI(transport=httpx.MockTransport(handler), ledger=path)
        try:
            api("s", "u")
        except (BudgetExceeded, httpx.ReadTimeout) as exc:
            return type(exc).__name__
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(call, [1, 2]))
    assert "BudgetExceeded" in results


def test_strategy_rejects_unknown_indices():
    with pytest.raises(ValueError):
        validate({"package_order": [100], "evidence": [], "question": "cost", "body": ""}, 2, 0)


def test_simulator_all_three_and_parallel_isolation(sim):
    client = ArenaClient(sim[0], rate=1000)
    key = client.register("hybrid-offline", "sim")["api_key"]
    client = ArenaClient(sim[0], key, rate=1000)
    ids = [c["case_id"] for c in client.cases()]
    results = play_all(lambda: RemoteTable(client), ids, HybridAgent, parallel=3)
    assert len(results) == 3
    assert all(isinstance(r, dict) and r["ended"] and r["must_haves_ok"] for r in results.values())


def test_official_cost_convention_no_double_price_unit_conversion(case):
    case["price_unit"] = 100
    terms = complete_offer(case, {"unit_price": 20})
    offers = standing_offers(case, {"A": thread(**terms)})
    assert offers[0]["base_cost"] == total_cost(case, terms)
