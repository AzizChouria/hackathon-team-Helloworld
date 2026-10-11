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
from arena_kit.client import ArenaError
from arena_kit.commercial import objections
from arena_kit.cost import closing_terms, must_haves_ok, total_cost
from arena_kit.data import DataPackage
from arena_kit.play import fetch_documents, play, play_threads
from arena_kit.research import Evidence, Research, month_number
from arena_kit.sim import load_cases
from arena_kit.strategy import safe_message, supplier_signals

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


def test_cheaper_pending_rival_gets_a_short_extra_wait(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    previous = {"from": "buyer", "body": "Please quote."}
    threads = {"sup:A": [previous, *thread(20, "final_offer")], "sup:B": [previous, *thread(15, supplier="B")]}
    agent = BuyerAgent()
    assert agent.decide_ready(case, threads, ["sup:A"]) is None
    threads["sup:A"][-1]["_received_at"] = time.monotonic() - 31
    assert agent.decide_ready(case, threads, ["sup:A"]) is None
    threads["sup:A"][-1]["_received_at"] = time.monotonic() - 46
    decision = agent.decide_ready(case, threads, ["sup:A"])
    assert decision["supplier_id"] == "sup:A"
    assert decision["message"]["action"]["type"] == "accept"


def test_final_offer_closes_at_original_guard_without_better_pending_quote(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    previous = {"from": "buyer", "body": "Please quote."}
    threads = {"sup:A": [previous, *thread(20, "final_offer")], "sup:B": [previous, *thread(25, supplier="B")]}
    threads["sup:A"][-1]["_received_at"] = time.monotonic() - 31
    decision = BuyerAgent().decide_ready(case, threads, ["sup:A"])
    assert decision["message"]["action"]["type"] == "accept"


def test_final_offer_does_not_wait_for_noncompliant_pending_quote(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 30}]
    previous = {"from": "buyer", "body": "Please quote."}
    threads = {
        "sup:A": [previous, *thread(20, "final_offer")],
        "sup:B": [previous, *thread(15, payment=14, supplier="B")],
    }
    threads["sup:A"][-1]["_received_at"] = time.monotonic() - 31
    decision = BuyerAgent().decide_ready(case, threads, ["sup:A"])
    assert decision["message"]["action"]["type"] == "accept"


def test_lower_pending_unit_price_does_not_override_worse_full_cost(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    previous = {"from": "buyer", "body": "Please quote."}
    threads = {
        "sup:A": [previous, *thread(20, "final_offer", payment=90)],
        "sup:B": [previous, *thread(19.70, payment=14, supplier="B")],
    }
    threads["sup:A"][-1]["_received_at"] = time.monotonic() - 31
    decision = BuyerAgent().decide_ready(case, threads, ["sup:A"])
    assert decision["message"]["action"]["type"] == "accept"


def test_local_rfq_collects_better_pending_final_quote(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    previous = {"from": "buyer", "body": "Please quote."}
    threads = {
        "sup:A": [previous, *thread(20, "final_offer")],
        "sup:B": [previous, *thread(15, supplier="B")],
    }
    threads["sup:A"][-1]["_received_at"] = time.monotonic() - 31
    release = threading.Event()

    class Table:
        def send(self, sid, _):
            assert sid == "sup:B"
            assert release.wait(timeout=3)
            return thread(15, "final_offer", supplier="B")[0]

        def close(self, sid, _):
            return {"deal": True, "supplier_id": sid}

    class Agent(BuyerAgent):
        first = True

        def decide_ready(self, case, threads, ready):
            if self.first:
                self.first = False
                return {"supplier_id": "sup:B", "message": {"body": "Please improve."}}
            decision = super().decide_ready(case, threads, ready)
            if decision is None:
                release.set()
            return decision

    try:
        result = play_threads(Table(), case, threads, Agent())
    finally:
        release.set()
    assert result == {"deal": True, "supplier_id": "sup:B"}


def test_rfq_can_use_reply_while_its_attachment_is_still_loading(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    release = threading.Event()

    class Table:
        def send(self, sid, _message):
            assert sid == "sup:B"
            reply = thread(18, "final_offer", supplier="B")[0]
            reply["attachments"] = [{"attachment_id": "att:B", "name": "cost.txt"}]
            return reply

        def attachment(self, _ref):
            assert release.wait(timeout=2)
            return b"The document."

        def close(self, sid, _message):
            release.set()
            return {"deal": True, "supplier_id": sid}

    class Agent:
        called = False

        def decide_ready(self, _case, threads, _ready):
            if not self.called:
                self.called = True
                return {"supplier_id": "sup:B", "message": {"body": "Please revise."}}
            assert "text" not in threads["sup:B"][-1]["attachments"][0]
            return {"supplier_id": "sup:B", "message": {
                "action": {"type": "accept", "term_sheet_id": "offer:B-0"}
            }}

    threads = {"sup:A": thread(20, supplier="A"), "sup:B": thread(21, supplier="B")}
    try:
        result = play_threads(Table(), case, threads, Agent())
    finally:
        release.set()
    assert result == {"deal": True, "supplier_id": "sup:B"}


def test_wave_deadline_accepts_ready_offer_while_another_bidder_is_pending(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    sending = threading.Event()
    release = threading.Event()

    class Table:
        closed = False

        def send(self, sid, _):
            assert sid == "sup:B"
            sending.set()
            assert release.wait(timeout=3)
            return thread(19, "final_offer", supplier="B")[0]

        def close(self, sid, message):
            assert sid == "sup:A"
            assert message["action"] == {"type": "accept", "term_sheet_id": "offer:A-0"}
            self.closed = True
            release.set()
            return {"deal": True}

    class Agent:
        def decide_ready(self, _, __, ready):
            if "sup:B" not in ready:
                return None
            return {"supplier_id": "sup:B", "message": {"body": "Please confirm."}}

        def close(self, _, threads):
            assert list(threads) == ["sup:A"]
            return {"supplier_id": "sup:A", "message": {"action": {"type": "accept", "term_sheet_id": "offer:A-0"}}}

    table = Table()
    threads = {"sup:A": thread(20, "final_offer"), "sup:B": thread(21, supplier="B")}
    try:
        result = play_threads(
            table,
            case,
            threads,
            Agent(),
            deadline=lambda: time.time() + (1 if sending.is_set() else 300),
        )
    finally:
        release.set()
    assert table.closed and result["deal"]


@pytest.mark.parametrize("case_id", ["case:S01", "case:S02"])
def test_expired_offer_is_refreshed_and_revalued_before_retry(case_id):
    case = load_cases()[case_id]

    class ExpiringTable(LocalTable):
        recovered = False

        def close(self, sid, message):
            if not self.recovered:
                raise ArenaError(422, "not a standing offer in this session")
            return super().close(sid, message)

        def missed(self, sid, error):
            self.recovered = True
            return self.send(sid, {"body": "Please confirm your current offer."})

    table = ExpiringTable(case)
    result = play(table, case_id, BuyerAgent())
    assert table.recovered and result["deal"] and result["must_haves_ok"]


def test_attachments_are_downloaded_concurrently():
    class Table:
        barrier = threading.Barrier(2)

        def attachment(self, ref):
            self.barrier.wait(timeout=2)
            return b"The document."

    message = {"attachments": [{"attachment_id": f"att:{i}", "name": f"{i}.txt"} for i in range(2)]}
    fetch_documents(Table(), message)
    assert all(a["text"] == "The document." for a in message["attachments"])


def test_rejected_alternative_falls_back_to_fresh_valid_sheet(case):
    sid = case["suppliers"][0]
    message = thread(20, "final_offer")[0]
    message["term_sheets"].append(
        {"term_sheet_id": "offer:unavailable", "terms": {"unit_price": 19, "payment_days": 90}}
    )

    class Table:
        attempts = []

        def open(self, _):
            return case, {sid: [copy.deepcopy(message)]}

        def close(self, supplier, request):
            ref = request["action"]["term_sheet_id"]
            self.attempts.append(ref)
            if ref == "offer:unavailable":
                raise ArenaError(422, "not a standing offer in this session")
            return {"deal": True}

        def missed(self, *_):
            return copy.deepcopy(message)  # endpoint still lists the rejected alternative

    table = Table()
    assert play(table, case["case_id"], BuyerAgent())["deal"]
    assert table.attempts == ["offer:unavailable", "offer:A-0"]


def test_relationship_estimate_can_make_higher_price_the_better_deal(case):
    class EstimatedResearch(Research):
        def estimate(self, case, sid, standard):
            return {"full_cost": 19, "interest_rate": 0.08, "standard": standard}

    case["buyer"].update(category_goal="stabilise", sustainable_margin_pct=10, relationship_eur_per_point=100000)
    case["suppliers"] = ["sup:A", "sup:B"]
    threads = {"sup:A": thread(19, "final_offer"), "sup:B": thread(22, "final_offer", supplier="B")}
    assert BuyerAgent(EstimatedResearch()).decide(case, threads)["supplier_id"] == "sup:B"


def test_price_only_counter_does_not_slow_the_trade_for_complete_terms(case):
    sid = case["suppliers"][0]
    buyer = {"from": "buyer", "term_sheets": [{"terms": {"unit_price": 18, "payment_days": 90}}]}
    events = [*thread(21, payment=90), buyer, *thread(20, payment=90)]
    agent = BuyerAgent()
    complete = agent.concession_step(case, sid, events, {"resistant": False})
    events[-1]["term_sheets"][0]["terms"].pop("payment_days")
    incomplete = agent.concession_step(case, sid, events, {"resistant": False})
    assert complete > incomplete > 0


def test_concession_pace_recognises_full_cost_and_resistance(case):
    sid = case["suppliers"][0]
    buyer = {"from": "buyer", "term_sheets": [{"terms": {"unit_price": 18, "payment_days": 14}}]}
    events = [*thread(21, payment=90), buyer, *thread(20.99, payment=14)]
    agent = BuyerAgent()
    worse_cost = agent.concession_step(case, sid, events, {"resistant": False})
    events[-1]["term_sheets"][0]["terms"]["unit_price"] = 19.5
    better_cost = agent.concession_step(case, sid, events, {"resistant": False})
    resistant = agent.concession_step(case, sid, events, {"resistant": True})
    assert worse_cost == 0 and better_cost >= 1 / 3 and resistant == better_cost


def test_no_supplier_movement_does_not_raise_buyer_cost_bid(case):
    sid = case["suppliers"][0]
    prior = {"unit_price": 18, "payment_days": 90}
    events = [
        *thread(21, payment=90),
        {"from": "buyer", "term_sheets": [{"terms": prior}]},
        *thread(21, payment=90),
    ]
    lead = BuyerAgent().packages(case, sid, events)[0]
    assert total_cost(case, lead) <= total_cost(case, prior)


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
    events = thread(140)
    events[0]["body"] = "Our material costs and energy prices increased."
    decision = BuyerAgent(research, complete=model).decide(case, {sid: events})
    message = decision["message"]
    claim = next(e for e in research.evidence(case, sid) if e.refs[0].startswith("idx:PPI-D351"))
    assert "changed -" in claim.text
    assert claim.text in message["body"]
    assert set(claim.refs) <= set(message["refs"])


def test_cost_index_is_not_forced_into_cash_objection(case, research):
    case["parts"] = ["part:310010"]
    case["suppliers"] = ["sup:70110"]
    case["buyer"]["category_goal"] = "stabilise"
    sid = case["suppliers"][0]
    events = thread(140)
    events[0]["body"] = "Our cash flow requires earlier payment."
    agent = BuyerAgent(research, complete=lambda *_: json.dumps({"tactic": "cash", "evidence": []}))
    message = agent.decide(case, {sid: events})["message"]
    assert not any(ref.startswith("idx:") for ref in message["refs"])


def test_equal_cost_leaves_supplier_more_delivery_time_and_contract_security(case):
    case["negotiable"] += ["lead_time_days", "contract_months"]
    case["fixed_terms"].pop("lead_time_days")
    case["fixed_terms"].pop("contract_months")
    case["buyer"]["need_lead_time_days"] = 42
    case["term_options"].update(lead_time_days=[28, 35, 42, 56], contract_months=[12, 24, 36])
    offer = optimise(case, 20, {})
    assert offer["lead_time_days"] == 42
    assert offer["contract_months"] == 36
    assert total_cost(case, offer) == total_cost(case, {**offer, "lead_time_days": 28, "contract_months": 12})


def test_model_receives_real_contract_scope_and_can_answer_supplier(case):
    prose = "Please ask finance to compare the attached cash package and confirm the corresponding concession."

    def model(_, payload):
        context = json.loads(payload)
        assert context["fixed_terms"] == case["fixed_terms"]
        assert context["negotiable"] == case["negotiable"]
        assert context["proposed_packages"]
        assert context["standing_packages"]
        return json.dumps({"tactic": "cash", "evidence": [], "message": prose})

    message = BuyerAgent(complete=model).decide(case, {case["suppliers"][0]: thread()})["message"]
    assert prose in message["body"]


def test_quality_negotiation_cannot_offer_fixed_payment_changes(case):
    case["buyer"]["category_goal"] = "quality_first"
    case["negotiable"] = ["unit_price", "ppm_commitment", "chargeback_eur_per_complaint"]
    case["fixed_terms"]["payment_days"] = 60
    case["term_options"] = {
        "ppm_commitment": [300, 800, 1500, 2500],
        "chargeback_eur_per_complaint": [0, 150, 300, 500],
    }
    case["buyer"]["cost_per_defect"] = 450
    case["buyer"]["must_haves"] = [{"field": "ppm_commitment", "op": "<=", "value": 1500}]
    agent = BuyerAgent(
        complete=lambda *_: json.dumps(
            {"tactic": "cash", "evidence": [], "message": "We can offer faster payment in return for a lower price."}
        )
    )
    message = agent.decide(case, {case["suppliers"][0]: thread()})["message"]
    assert "faster payment" not in message["body"]
    assert "quality manager" in message["body"]
    assert agent.trace[-1]["tactic"] == "quality"
    assert {s["terms"]["chargeback_eur_per_complaint"] for s in message["term_sheets"]} == {0, 300, 500}
    assert all(must_haves_ok(case, s["terms"]) for s in message["term_sheets"])
    # When chargebacks already recover the entire defect cost, demanding a stricter
    # ppm guarantee adds supplier effort without improving the buyer's modelled cost.
    assert message["term_sheets"][0]["terms"]["ppm_commitment"] == 1500
    assert message["term_sheets"][-1]["terms"]["ppm_commitment"] == 1500


@pytest.mark.parametrize(
    "prose",
    [
        "Our budget allows us to accept your price.",
        "We can pay EUR 500 for the full order.",
        "The evidence is documented at https://invented.example.",
        "Our deadline means we must accept your proposal.",
    ],
)
def test_supplier_facing_prose_rejects_figures_and_sensitive_information(prose):
    assert safe_message(prose) is None


def test_infeasible_rival_quote_is_not_used_as_like_for_like_leverage(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 60}]
    threads = {"sup:A": thread(20, payment=60), "sup:B": thread(18, payment=14, supplier="B")}
    agent = BuyerAgent()
    agent.prepare(case)
    assert not any(e.kind == "rival" for e in agent.unused_evidence(case, "sup:A", threads))


def test_static_rival_evidence_requires_explicit_compliant_alternative(case):
    sid = case["suppliers"][0]
    ref = "quote:outside"
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 60}]
    case["buyer"]["alternative"] = {
        "kind": "quote",
        "ref": ref,
        "terms": {"unit_price": 18, "payment_days": 14},
    }
    agent = BuyerAgent()
    agent.prepare(case)
    agent.claims[sid] = [Evidence("Rival quote is EUR 18.", (ref,), "rival")]
    assert not agent.unused_evidence(case, sid, {sid: thread()})
    case["buyer"]["alternative"]["terms"]["payment_days"] = 60
    assert agent.unused_evidence(case, sid, {sid: thread()})[0].kind == "rival"


def test_live_rival_alternative_is_usable_when_it_is_best(case):
    case["suppliers"] = ["sup:A", "sup:B"]
    threads = {"sup:A": thread(20), "sup:B": thread(21, supplier="B")}
    threads["sup:B"][0]["term_sheets"].append(
        {"term_sheet_id": "offer:B-1", "terms": {"unit_price": 18, "payment_days": 90}}
    )
    agent = BuyerAgent()
    agent.prepare(case)
    rivals = [e for e in agent.unused_evidence(case, "sup:A", threads) if e.kind == "rival"]
    assert len(rivals) == 1
    assert rivals[0].refs == ("offer:B-1",)


def test_index_alternative_is_explicit_and_within_menu(case):
    clause = {"series": "METAL", "material_share": 0.2, "deadband_pct": 5, "base_month": "2026-08"}
    case["negotiable"].append("index_clause")
    case["fixed_terms"].pop("index_clause")
    case["term_options"]["index_clause"] = [None, clause]
    case["buyer"]["index_risk_pct"] = 3
    offers = BuyerAgent().packages(case, case["suppliers"][0], thread())
    assert any(t["index_clause"] is None for t in offers)
    assert any(t["index_clause"] == clause for t in offers)


@pytest.fixture
def raw_material_case(case):
    case["type"] = "raw_material"
    case["negotiable"].append("index_clause")
    case["fixed_terms"].pop("index_clause")
    clause = {"series": "GENERIC_METAL", "material_share": 0.4,
              "deadband_pct": 5, "base_month": "2026-08"}
    case["term_options"]["index_clause"] = [None, clause]
    case["buyer"]["index_paths"] = {"GENERIC_METAL": 0.06}
    case["buyer"]["index_risk_pct"] = 1
    return case


def test_raw_material_fixed_quote_retains_payment_trades_without_adding_index_risk(raw_material_case):
    case = raw_material_case
    events = thread()
    events[0]["term_sheets"][0]["terms"]["index_clause"] = None

    offers = BuyerAgent().packages(case, case["suppliers"][0], events)

    assert all(t["index_clause"] is None for t in offers)
    assert {14, 90}.issubset({t["payment_days"] for t in offers})
    assert all(must_haves_ok(case, t) for t in offers)
    cash = next(t for t in offers if t["payment_days"] == 14)
    late = next(t for t in offers if t["payment_days"] == 90)
    assert cash["unit_price"] < late["unit_price"]
    assert total_cost(case, cash) <= total_cost(case, late)


@pytest.mark.parametrize("alternative", [False, True])
def test_raw_material_supplier_indexed_quote_remains_a_priced_option(raw_material_case, alternative):
    case = raw_material_case
    clause = case["term_options"]["index_clause"][1]
    events = thread()
    fixed = events[0]["term_sheets"][0]
    fixed["terms"]["index_clause"] = None
    if alternative:
        events[0]["term_sheets"].append({
            "term_sheet_id": "offer:A-indexed",
            "terms": {**fixed["terms"], "unit_price": 21, "index_clause": clause},
        })
    else:
        fixed["terms"]["index_clause"] = clause

    offers = BuyerAgent().packages(case, case["suppliers"][0], events)

    assert any(t["index_clause"] == clause for t in offers)
    assert all(must_haves_ok(case, t) for t in offers)


def test_raw_material_beneficial_index_is_available_even_from_fixed_quote(raw_material_case):
    case = raw_material_case
    case["buyer"]["index_paths"]["GENERIC_METAL"] = -0.12
    clause = case["term_options"]["index_clause"][1]
    events = thread()
    events[0]["term_sheets"][0]["terms"]["index_clause"] = None

    offers = BuyerAgent().packages(case, case["suppliers"][0], events)

    indexed = next(t for t in offers if t["index_clause"] == clause)
    assert total_cost(case, indexed) < total_cost(case, {**indexed, "index_clause": None})
    assert all(must_haves_ok(case, t) for t in offers)


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


def test_parallel_rfq_reserves_citations_before_the_first_reply(case, research):
    case["parts"] = ["part:320070"]
    case["suppliers"] = ["sup:70210", "sup:70250"]
    agent = BuyerAgent(research)
    threads = {sid: thread(38, supplier=sid) for sid in case["suppliers"]}
    first = agent.decide_ready(case, threads, ["sup:70210"])
    second = agent.decide_ready(case, threads, ["sup:70250"])
    assert first["message"]["refs"]
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


def test_busy_open_session_retries_when_capacity_frees(case):
    class BusyTable(LocalTable):
        attempts = 0

        def open(self, case_id):
            self.attempts += 1
            if self.attempts == 1:
                raise ArenaError(429, "at most 10 open sessions per key")
            return super().open(case_id)

    table = BusyTable(case)
    result = play(table, case["case_id"], BuyerAgent(), deadline=time.time() + 300)
    assert table.attempts == 2
    assert result["deal"] and result["must_haves_ok"]


def test_practice_quota_is_not_retried_as_session_capacity(case):
    class QuotaTable(LocalTable):
        attempts = 0

        def open(self, case_id):
            self.attempts += 1
            raise ArenaError(429, "practice limit: wait until reset")

    table = QuotaTable(case)
    with pytest.raises(ArenaError, match="practice limit"):
        play(table, case["case_id"], BuyerAgent(), deadline=time.time() + 300)
    assert table.attempts == 1


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


def test_live_model_uses_low_effort_with_override(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-6.1-sol")
    monkeypatch.setenv("LLM_BASE_URL", "https://unused.example/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    requests = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"tactic":"cost","evidence":[]}'}}]}

    def post(*args, **kwargs):
        requests.append(kwargs["json"])
        return Response()

    monkeypatch.setattr("arena_kit.agents.llm.httpx.post", post)
    agent = agent_factory("buyer-llm", DATA)()
    agent.complete("system", "user")
    assert requests[-1]["model"] == "gpt-6.1-sol"
    assert requests[-1]["reasoning_effort"] == "low"
    monkeypatch.setenv("LLM_REASONING_EFFORT", "medium")
    agent.complete("system", "user")
    assert requests[-1]["reasoning_effort"] == "medium"


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


def test_practice_model_preflight_stops_before_arena_client(monkeypatch):
    import arena_kit.agents as agents
    import arena_kit.cli as cli

    def no_arena(*_args, **_kwargs):
        raise AssertionError("arena client must not be created")

    def unavailable(*_args, **_kwargs):
        raise ValueError("invalid model")

    monkeypatch.setattr(cli, "ArenaClient", no_arena)
    monkeypatch.setattr(agents, "llm_from_env", unavailable)
    monkeypatch.setenv("LLM_MODEL", "invalid-model")

    with pytest.raises(SystemExit, match="Model preflight failed.*no arena session opened"):
        cli.main(["play", "case:P02", "--agent", "buyer-llm"])


def test_model_call_counts_include_fallbacks(case):
    replies = iter([
        ValueError("model failed"),
        '{"tactic":"cost","evidence":[],"message":"Please review the full commercial proposal."}',
    ])

    def complete(*_args):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    agent = BuyerAgent(complete=complete)
    agent.prepare(case)
    sid = case["suppliers"][0]
    events = [{"from": "supplier", "body": "Please review the proposal.", "term_sheets": []}]
    agent.tactic(case, sid, events, [], [])
    agent.tactic(case, sid, events, [], [])

    assert agent.model_fallbacks == 1
    assert agent.model_successes == 1


def test_supplier_signals_use_general_language():
    dossier = {"documents": {"memo": "Our machines have available capacity next quarter."}}
    events = [{"from": "supplier", "body": "Management approval is needed; our price is fixed."}]

    signals = supplier_signals(dossier, events)

    assert signals["spare_capacity"]
    assert signals["approval_needed"]
    assert signals["price_locked"]
    assert objections([{"from": "supplier", "body": "The cost calculation is confidential."}])[
        "breakdown_refused"
    ]
    assert objections([{"from": "supplier", "body": "We cannot provide a cost breakdown."}])[
        "breakdown_refused"
    ]
    assert objections([{"from": "supplier", "body": "We don't do cost breakdowns."}])[
        "breakdown_refused"
    ]


def test_indexed_quote_keeps_a_longer_payment_option():
    case = copy.deepcopy(load_cases()["case:S03"])
    clause = {"series": "GENERIC", "material_share": 0.4, "deadband_pct": 5, "base_month": "2026-08"}
    case["negotiable"].append("index_clause")
    case["term_options"]["index_clause"] = [None, clause]
    case["buyer"]["index_paths"] = {"GENERIC": 0.06}
    case["buyer"]["category_goal"] = "leverage"
    sid = case["suppliers"][0]
    events = thread(price=220, payment=14)
    events[0]["term_sheets"][0]["terms"].update({"contract_months": 24, "index_clause": clause})

    packages = BuyerAgent().packages(case, sid, events)

    assert any(p["index_clause"] == clause and p["payment_days"] == 90 for p in packages)


def test_supplier_signals_read_sunday_release_letter_wording():
    from arena_kit.strategy import supplier_signals

    def sig(text):
        return supplier_signals({"documents": {"doc": text}})

    locked = sig("our price list 2027 applies to all customers without exception; our board has "
                 "ruled out individual price reductions for the coming year.")
    assert locked["price_locked"]
    assert sig("Our prices are set centrally from now on: we can no longer grant individual "
               "price reductions.")["price_locked"]
    assert sig("we bought our bright and cold-drawn bar requirement forward at fixed prices "
               "until June 2027.")["hedged"]
    cash = sig("Our bank is watching our figures every month: we kindly ask you to pay our "
               "invoices within 10 days from November.")
    assert cash["cash_sensitive"]
    neutral = sig("Thank you for your enquiry. Please find our quotation for the 2027 volume attached.")
    assert not any(neutral[k] for k in ("price_locked", "hedged", "cash_sensitive"))


def test_required_terms_reads_noncompliant_rival_price_at_the_must_have_bound():
    from arena_kit.agents.buyer import required_terms

    case = {"buyer": {"must_haves": [{"field": "lead_time_days", "op": "<=", "value": 42}],
                      "need_per_year": 100, "horizon_years": 1, "reference_payment_days": 60,
                      "need_lead_time_days": 35, "freight_eur_per_unit": {"DAP": 0.0}},
            "fixed_terms": {}}
    late = {"unit_price": 31.0, "lead_time_days": 52}
    assert required_terms(case, late) == {"unit_price": 31.0, "lead_time_days": 42}
    ok = {"unit_price": 30.0, "lead_time_days": 35}
    assert required_terms(case, ok) == ok
    assert required_terms(case, {"lead_time_days": 35}) is None
