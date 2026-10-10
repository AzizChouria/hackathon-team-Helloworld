"""A rejected accept may only recover server-confirmed current offer terms."""

from arena_kit.client import ArenaError
from arena_kit.play import RemoteTable


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
