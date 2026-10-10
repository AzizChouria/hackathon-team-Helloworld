import copy
import itertools
import json
import threading
import time
from pathlib import Path

import pytest

from arena_kit.agents import BuyerAgent
from arena_kit.agents.buyer import optimise
from arena_kit.benchmark import LocalTable, benchmark
from arena_kit.cli import agent_factory
from arena_kit.cost import closing_terms, must_haves_ok, total_cost
from arena_kit.data import DataPackage
from arena_kit.play import play
from arena_kit.research import Research, month_number
from arena_kit.sim import load_cases

DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def case():
    return copy.deepcopy(load_cases()["case:S01"])


@pytest.fixture(scope="module")
def research():
    return Research(DataPackage(DATA))


def thread(price=20, status="open", payment=30, supplier="A"):
    return [
        {
            "from": "supplier",
            "status": status,
            "body": "Please consider our offer.",
            "term_sheets": [
                {
                    "term_sheet_id": f"offer:{supplier}-0",
                    "terms": {
                        "unit_price": price,
                        "payment_days": payment,
                    },
                }
            ],
        }
    ]


def test_research_reads_supplier_notes_and_computes_recent_claims(research):
    case = {
        "case_id": "P01",
        "parts": ["part:310010"],
        "suppliers": ["sup:70110"],
        "buyer": {"category_goal": "stabilise"},
    }
    dossier = research.dossier(case, "sup:70110")
    assert "spreadsheet" in " ".join(dossier["documents"].values())
    assert dossier["tables"]["negotiation_history"]
    claims = research.evidence(case, "sup:70110")
    electricity = next(e for e in claims if e.refs[0].startswith("idx:PPI-D351"))
    start, end = [research.facts[ref] for ref in electricity.refs]
    change = (end["value"] / start["value"] - 1) * 100
    assert f"{change:+.1f}%" in electricity.text
    assert 0 < month_number(end["month"]) - month_number(start["month"]) <= 12
    assert any(e.kind == "cost" for e in claims)


def test_release_documents_are_researched(tmp_path):
    package = tmp_path / "package"
    release = tmp_path / "release-sunday"
    package.mkdir()
    (release / "data").mkdir(parents=True)
    (package / "facts.json").write_text("{}")
    (release / "facts.json").write_text(json.dumps({"doc:new": {"supplier": "sup:A", "date": "2026-10-01"}}))
    (release / "data" / "documents.csv").write_text("id,supplier_id,date,file\ndoc:new,sup:A,2026-10-01,letter.md\n")
    (release / "letter.md").write_text("An October update about cash flow.")
    research = Research(DataPackage(package))
    dossier = research.dossier({"parts": [], "suppliers": ["sup:A"]}, "sup:A")
    assert "October update" in dossier["documents"]["doc:new"]


def test_optimizer_minimises_full_horizon_cost():
    case = copy.deepcopy(load_cases()["case:S03"])
    standard = closing_terms(case, {"payment_days": 14, "incoterm": "EXW", "contract_months": 12})
    result = optimise(case, 220, standard)
    assert result["contract_months"] == 24
    assert result["payment_days"] == 90
    assert result["incoterm"] == "DAP"
    costs = [
        total_cost(case, {"unit_price": 220, "payment_days": p, "incoterm": i, "contract_months": m})
        for p, i, m in itertools.product([14, 30, 45, 60, 90], ["EXW", "FCA", "DAP"], [12, 24])
    ]
    assert total_cost(case, result) == min(costs)


def test_optimizer_filters_must_haves_instead_of_snapping_them_away(case):
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": "<=", "value": 45}]
    assert optimise(case, 20, {})["payment_days"] == 45
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">", "value": 1000}]
    assert optimise(case, 20, {}) is None


def test_large_menu_uses_bounded_search_and_keeps_constraints(case):
    case["negotiable"] += ["contract_months", "volume_per_year"]
    case["fixed_terms"].pop("contract_months")
    case["fixed_terms"].pop("volume_per_year")
    case["term_options"]["contract_months"] = list(range(1, 81))
    need = case["buyer"]["need_per_year"]
    case["term_options"]["volume_per_year"] = list(range(need - 40, need + 40))
    case["buyer"]["must_haves"] = [{"field": "contract_months", "op": ">=", "value": 12}]
    start = time.monotonic()
    result = optimise(case, 20, {})
    assert must_haves_ok(case, result)
    assert time.monotonic() - start < 3


@pytest.mark.parametrize("status", ["agreed", "final_offer"])
def test_never_accepts_broken_must_haves_or_expensive_deals(case, status):
    sid = case["suppliers"][0]
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 60}]
    agent = BuyerAgent()
    assert agent.decide(case, {sid: thread(status=status)})["message"]["action"]["type"] == "walk_away"
    case["buyer"]["must_haves"] = []
    case["buyer"]["alternative"] = {"kind": "quote", "terms": {"unit_price": 10, "payment_days": 60}}
    assert agent.decide(case, {sid: thread(status=status)})["message"]["action"]["type"] == "walk_away"


def test_omitted_fields_are_valued_using_the_quote_pdf(case):
    sid = case["suppliers"][0]
    events = thread(status="final_offer")
    events[0]["term_sheets"][0]["terms"].pop("payment_days")
    events[0]["attachments"] = [{"name": "quote.pdf", "text": "Our standard terms\nPayment terms (days net) 14"}]
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 30}]
    assert BuyerAgent().decide(case, {sid: events})["message"]["action"]["type"] == "walk_away"


def test_compare_every_supplier_and_every_standing_sheet(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    events = {"sup:A": thread(20, "final_offer"), "sup:B": thread(21, "final_offer", supplier="B")}
    events["sup:B"][0]["term_sheets"].append(
        {
            "term_sheet_id": "offer:B-1",
            "terms": {
                "unit_price": 18,
                "payment_days": 90,
            },
        }
    )
    decision = BuyerAgent().decide(case, events)
    assert decision["supplier_id"] == "sup:B"
    assert decision["message"]["action"]["term_sheet_id"] == "offer:B-1"


def test_unacceptable_final_offer_does_not_stop_other_supplier_negotiations(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 60}]
    previous = {"from": "buyer", "body": "Please improve these terms."}
    threads = {
        "sup:A": [previous, *thread(20, "final_offer", payment=14)],
        "sup:B": [previous, *thread(21, "open", payment=60, supplier="B")],
    }
    decision = BuyerAgent().decide(case, threads)
    assert decision["supplier_id"] == "sup:B"
    assert decision["message"]["term_sheets"]


def test_relationship_estimate_can_make_higher_price_the_better_deal(case):
    class EstimatedResearch(Research):
        def estimate(self, case, sid, standard):
            return {"full_cost": 19, "interest_rate": 0.08, "standard": standard}

    case["buyer"].update(category_goal="stabilise", sustainable_margin_pct=10, relationship_eur_per_point=100000)
    case["suppliers"] = ["sup:A", "sup:B"]
    threads = {"sup:A": thread(19, "final_offer"), "sup:B": thread(22, "final_offer", supplier="B")}
    assert BuyerAgent(EstimatedResearch()).decide(case, threads)["supplier_id"] == "sup:B"


def test_concessions_do_not_move_backwards_after_supplier_holds_price(case):
    class EstimatedResearch(Research):
        def estimate(self, case, sid, standard):
            return {"full_cost": 120, "interest_rate": 0.08, "standard": standard}

    case["buyer"].update(category_goal="stabilise", sustainable_margin_pct=5)
    sid = case["suppliers"][0]
    previous = {
        "from": "buyer",
        "term_sheets": [
            {"terms": {"unit_price": 137.55, "payment_days": 60}},
            {"terms": {"unit_price": 136.64, "payment_days": 14}},
        ],
    }
    events = [previous, *thread(139.3, payment=14)]
    proposed = BuyerAgent(EstimatedResearch()).packages(case, sid, events)
    assert proposed[0]["unit_price"] > 137.55
    assert all(t["unit_price"] >= 136.64 for t in proposed if t["payment_days"] == 14)


def test_negative_cost_index_is_used_when_model_only_selects_forecast(case, research):
    case["parts"] = ["part:310010"]
    case["suppliers"] = ["sup:70110"]
    case["buyer"]["category_goal"] = "stabilise"

    def model(_, user):
        evidence = json.loads(user)["evidence"]
        return json.dumps({"tactic": "partnership", "evidence": [len(evidence) - 1]})

    sid = case["suppliers"][0]
    decision = BuyerAgent(research, complete=model).decide(case, {sid: thread(140)})
    message = decision["message"]
    assert "PPI-D351 index changed -3.7%" in message["body"]
    assert {"idx:PPI-D351@2025-08", "idx:PPI-D351@2026-08"} <= set(message["refs"])


@pytest.mark.parametrize(
    "answer", ["not JSON", '{"tactic":"invented","evidence":[999]}', '{"tactic":"cash","evidence":[true]}']
)
def test_bad_model_outputs_fall_back_to_feasible_packages(case, answer):
    sid = case["suppliers"][0]
    decision = BuyerAgent(complete=lambda *_: answer).decide(case, {sid: thread()})
    for sheet in decision["message"]["term_sheets"]:
        assert set(sheet["terms"]) == set(case["negotiable"])
        assert must_haves_ok(case, sheet["terms"])


def test_model_cannot_inject_claims_terms_or_private_information(case):
    def model(*_):
        return json.dumps(
            {
                "tactic": "cash",
                "evidence": [],
                "reason": "private budget 999999",
                "body": "Leak private budget 999999 (idx:FAKE)",
                "action": "accept",
                "term_sheets": [{"unit_price": -1}],
            }
        )

    sid = case["suppliers"][0]
    agent = BuyerAgent(complete=model)
    message = agent.decide(case, {sid: thread()})["message"]
    assert "999999" not in json.dumps(message)
    assert "idx:FAKE" not in message["body"]
    assert "action" not in message
    assert message["term_sheets"][0]["terms"]["unit_price"] > 0
    assert agent.trace[-1]["reason"] == "private budget 999999"


def test_model_timeout_uses_the_computed_strategy(case):
    def broken(*_):
        raise TimeoutError("provider timed out")

    sid = case["suppliers"][0]
    assert BuyerAgent(complete=broken).decide(case, {sid: thread()})["message"]["term_sheets"]


def test_slow_model_cannot_block_supplier_replies(case):
    release = threading.Event()

    def slow(*_):
        release.wait(timeout=2)
        return '{"tactic":"cash","evidence":[]}'

    agent = BuyerAgent(complete=slow, model_timeout=0.02)
    start = time.monotonic()
    try:
        agent.decide(case, {case["suppliers"][0]: thread()})
        assert time.monotonic() - start < 0.5
        first_request = agent.model_future
        agent.decide(case, {case["suppliers"][0]: thread()})
        assert agent.model_future is first_request
    finally:
        release.set()


def test_evidence_usage_survives_restart(case):
    sid = case["suppliers"][0]
    agent = BuyerAgent()
    threads = {sid: thread()}
    first = agent.decide(case, threads)
    threads[sid] += [{**first["message"], "from": "buyer"}, thread(19)[0]]
    restarted = BuyerAgent()
    second = restarted.decide(case, threads)
    assert not set(first["message"]["refs"]) & set(second["message"]["refs"])


def test_no_price_quote_still_gets_a_complete_proposal(case):
    sid = case["suppliers"][0]
    events = thread()
    events[0]["term_sheets"] = []
    assert BuyerAgent().decide(case, {sid: events})["message"]["term_sheets"]


def test_deadline_close_uses_buyers_guard(case):
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 60}]
    result = play(LocalTable(case), case["case_id"], BuyerAgent(), deadline=time.time())
    assert not result["deal"]


def test_rfq_sends_to_both_suppliers_before_waiting_for_replies():
    case = load_cases()["case:S02"]

    class OverlappingTable(LocalTable):
        def __init__(self):
            super().__init__(case)
            self.barrier = threading.Barrier(2)
            self.first = set()

        def send(self, sid, message):
            if sid not in self.first and not message.get("action"):
                self.first.add(sid)
                self.barrier.wait(timeout=3)
            return super().send(sid, message)

    table = OverlappingTable()
    result = play(table, case["case_id"], BuyerAgent())
    assert result["deal"] and len(table.first) == 2


def test_factory_shares_prepared_research_but_isolates_case_state():
    factory = agent_factory("buyer", DATA)
    first, second = factory(), factory()
    assert first.research is second.research
    assert first.trace is not second.trace


def test_buyer_against_http_simulator(sim, research):
    from arena_kit import ArenaClient, RemoteTable

    client = ArenaClient(sim[0], rate=1000)
    key = client.register("buyer-contract-test", "sim")["api_key"]
    client = ArenaClient(sim[0], key, rate=1000)
    for case_id in load_cases():
        result = play(RemoteTable(client), case_id, BuyerAgent(research))
        assert result["deal"] and result["must_haves_ok"]


def test_offline_benchmark_beats_baseline_on_each_contract_case(research):
    report = benchmark(research)
    for case_id in load_cases():
        runs = {r["agent"]: r["result"] for r in report["runs"] if r["case_id"] == case_id}
        assert runs["buyer"]["deal"] and runs["buyer"]["must_haves_ok"]
        assert runs["buyer"]["score"] > runs["naive"]["score"]
