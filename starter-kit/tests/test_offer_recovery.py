"""A rejected accept may only recover server-confirmed current offer terms."""

import copy

from arena_kit.agents import BuyerAgent
from arena_kit.client import ArenaError
from arena_kit.play import RemoteTable, play
from arena_kit.sim import load_cases


class Client:
    def __init__(self, messages, current="offer:current", timeouts=None, status="final_offer"):
        self.messages = messages
        self.current = current
        self.timeouts = timeouts or []
        self.status = status

    def session(self, sid):
        return {"status": "active"}

    def thread(self, sid, supplier):
        return {"offer_id": self.current, "status": self.status, "closed": False,
                "timeouts": self.timeouts, "messages": self.messages}


def refresh(client, status=422):
    table = RemoteTable(client)
    table.session_id = "synthetic"
    return table.missed("supplier", ArenaError(status, "not a standing offer"))


def test_refresh_preserves_current_quote_and_its_alternatives():
    message = {"from": "supplier", "status": "final_offer", "body": "Final package",
               "attachments": [], "term_sheets": [
                   {"term_sheet_id": "offer:current", "terms": {"unit_price": 10}},
                   {"term_sheet_id": "offer:alt", "terms": {"unit_price": 9}},
               ]}
    refreshed = refresh(Client([message]))
    assert refreshed["term_sheets"] == message["term_sheets"]
    assert refreshed["_received_at"] is not None


def test_timeout_uses_only_terms_bound_to_current_offer_id():
    old = {"from": "supplier", "term_sheets": [
        {"term_sheet_id": "offer:old", "terms": {"unit_price": 8}}]}
    timeouts = [
        {"offer_id": "offer:old", "terms": {"unit_price": 8}},
        {"offer_id": "offer:current", "terms": {"unit_price": 11}},
    ]
    refreshed = refresh(Client([old], timeouts=timeouts), status=409)
    assert refreshed["term_sheets"] == [
        {"term_sheet_id": "offer:current", "terms": {"unit_price": 11}}]


def test_unknown_current_id_does_not_revive_historical_quote_or_timeout():
    old = {"from": "supplier", "term_sheets": [
        {"term_sheet_id": "offer:old", "terms": {"unit_price": 8}}]}
    stale = [{"offer_id": "offer:old", "terms": {"unit_price": 8}}]
    assert refresh(Client([old], current="offer:new", timeouts=stale))["term_sheets"] == []


def test_closed_thread_has_no_recoverable_offer():
    old = {"from": "supplier", "term_sheets": [
        {"term_sheet_id": "offer:current", "terms": {"unit_price": 8}}]}
    assert refresh(Client([old], status="walked_away"))["term_sheets"] == []


def test_rfq_tries_cheapest_alternative_then_uses_next_valid_supplier():
    case = copy.deepcopy(load_cases()["case:S01"])
    case["suppliers"] = ["sup:A", "sup:B"]
    a = {"from": "supplier", "status": "final_offer", "body": "Final package", "attachments": [],
         "term_sheets": [{"term_sheet_id": "offer:A", "terms": {"unit_price": 20, "payment_days": 30}}]}
    b = {"from": "supplier", "status": "final_offer", "body": "Two packages", "attachments": [],
         "term_sheets": [
             {"term_sheet_id": "offer:B", "terms": {"unit_price": 22, "payment_days": 30}},
             {"term_sheet_id": "offer:B-alt", "terms": {"unit_price": 19, "payment_days": 30}},
         ]}

    class RejectAlternative:
        def __init__(self):
            self.attempts = []

        def open_session(self, case_id):
            return {"session_id": "synthetic", "case": case,
                    "threads": {"sup:A": [copy.deepcopy(a)], "sup:B": [copy.deepcopy(b)]}}

        def session(self, sid):
            return {"status": "active"}

        def thread(self, sid, supplier):
            return {"offer_id": "offer:B", "status": "final_offer", "closed": False,
                    "timeouts": [], "messages": [copy.deepcopy(b)]}

        def send_message(self, sid, supplier, message):
            ref = message["action"]["term_sheet_id"]
            self.attempts.append(ref)
            if ref == "offer:B-alt":
                raise ArenaError(422, "not a standing offer in this session")
            assert ref == "offer:A"
            return {"result": {"ended": True, "deal": True, "must_haves_ok": True}}

    client = RejectAlternative()
    result = play(RemoteTable(client), case["case_id"], BuyerAgent())
    assert result["deal"] and result["must_haves_ok"]
    assert client.attempts == ["offer:B-alt", "offer:A"]
