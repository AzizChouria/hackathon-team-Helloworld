import json

import pytest

from arena_kit.agents import BuyerAgent
from arena_kit.benchmark import LocalTable
from arena_kit.evaluation import evaluate
from arena_kit.sim import load_cases


class Client:
    practice_remaining = 20

    def cases(self, _):
        return list(load_cases().values())

    def me(self):
        return {"practice": {"left": self.practice_remaining}}

    def session(self, sid):
        return {"replay_url": f"/replay/{sid}"}


def test_evaluation_persists_scores_and_counts_failed_runs(monkeypatch, tmp_path):
    class Table(LocalTable):
        session_id = "local-session"

        def __init__(self, _):
            pass

        def open(self, case_id):
            if case_id == "case:S02":
                raise RuntimeError("deliberate transport failure")
            super().__init__(load_cases()[case_id])
            return super().open(case_id)

    monkeypatch.setattr("arena_kit.evaluation.RemoteTable", Table)
    path = tmp_path / "run.json"
    report = evaluate(Client(), BuyerAgent, ["case:S01", "case:S02", "case:S01"], out=path)
    assert len(report["runs"]) == 2
    scores = [r.get("result", {}).get("score", 0) for r in report["runs"]]
    assert report["mean_score"] == sum(scores) / 2
    assert any("deliberate transport failure" in r.get("error", "") for r in report["runs"])
    assert json.loads(path.read_text()) == report


def test_evaluation_rejects_wrong_cases_and_insufficient_quota():
    with pytest.raises(ValueError, match="not hosted"):
        evaluate(Client(), BuyerAgent, ["case:FINAL"])
    client = Client()
    client.practice_remaining = 0
    with pytest.raises(ValueError, match="sessions"):
        evaluate(client, BuyerAgent, ["case:S01"])
    with pytest.raises(ValueError, match="closing reserve"):
        evaluate(Client(), BuyerAgent, seconds=30)
