"""An explicitly rejected acceptance must not erase another verified standing sheet."""
import copy

from arena_kit.agents.combined import CombinedAgent
from arena_kit.client import ArenaError
from arena_kit.cost import complete_offer
from arena_kit.play import RemoteTable, play
from arena_kit.sim import load_cases


class Client:
    def __init__(self, message, current="offer:current", timeouts=None):
        self.message, self.current, self.timeouts = message, current, timeouts or []

    def session(self, sid):
        return {"status": "active"}

    def thread(self, sid, supplier):
        return {"offer_id": self.current, "status": "final_offer", "closed": False,
                "timeouts": self.timeouts, "messages": [self.message]}


def test_refresh_preserves_current_quote_without_timeout_record():
    message = {"from": "supplier", "status": "final_offer", "body": "Final package",
               "attachments": [], "term_sheets": [{"term_sheet_id": "offer:current", "terms": {"unit_price": 10}},
                                                   {"term_sheet_id": "offer:alt", "terms": {"unit_price": 9}}]}
    table = RemoteTable(Client(message))
    table.session_id = "synthetic"
    refreshed = table.missed("supplier", ArenaError(422, "not a standing offer"))
    assert refreshed["term_sheets"] == message["term_sheets"]


def test_timeout_replacement_takes_precedence_over_stale_message():
    message = {"from": "supplier", "term_sheets": [{"term_sheet_id": "offer:old", "terms": {"unit_price": 8}}]}
    client = Client(message, timeouts=[{"offer_id": "offer:current", "terms": {"unit_price": 11}}])
    table = RemoteTable(client)
    table.session_id = "synthetic"
    refreshed = table.missed("supplier", ArenaError(409, "late"))
    assert refreshed["term_sheets"] == [{"term_sheet_id": "offer:current", "terms": {"unit_price": 11}}]


def test_rejected_alternative_falls_back_to_valid_primary_without_repeating_post():
    case = copy.deepcopy(load_cases()["case:S01"])
    supplier = case["suppliers"][0]
    price = case["buyer"]["current_unit_price"]
    primary = complete_offer(case, {"unit_price": price})
    cheaper = {**primary, "unit_price": round(price * .98, 2)}
    message = {"from": "supplier", "status": "final_offer", "body": "Choose a package", "attachments": [],
               "term_sheets": [{"term_sheet_id": "offer:current", "terms": primary},
                               {"term_sheet_id": "offer:alt", "terms": cheaper}]}

    class RejectAlternative(Client):
        def __init__(self):
            super().__init__(message)
            self.accepts = []

        def open_session(self, case_id):
            return {"session_id": "synthetic", "case": case, "threads": {supplier: [copy.deepcopy(message)]}}

        def send_message(self, session_id, sid, move):
            action = move["action"]
            assert action["type"] == "accept", "Recovery must retain the valid primary quote"
            self.accepts.append(action["term_sheet_id"])
            if action["term_sheet_id"] == "offer:alt":
                raise ArenaError(422, "not a standing offer in this session")
            return {"result": {"ended": True, "deal": True, "must_haves_ok": True}}

    client = RejectAlternative()
    result = play(RemoteTable(client, case), case["case_id"], CombinedAgent())
    assert result["deal"]
    assert client.accepts == ["offer:alt", "offer:current"]


def test_unknown_current_id_does_not_revive_historical_offer():
    message = {"from": "supplier", "term_sheets": [{"term_sheet_id": "offer:old", "terms": {"unit_price": 8}}]}
    table = RemoteTable(Client(message, current="offer:new"))
    table.session_id = "synthetic"
    assert table.missed("supplier", ArenaError(422, "not a standing offer"))["term_sheets"] == []
