"""The execution gate and batch persistence are tested with fake clients only."""
import json

import pytest

from arena_kit import benchmark as bench
from arena_kit import revised_benchmark as revised


@pytest.fixture
def prepared_env(tmp_path, monkeypatch):
    private, reports = tmp_path / "private", tmp_path / "reports"
    private.mkdir()
    monkeypatch.setattr(bench, "PRIVATE", private)
    monkeypatch.setattr(bench, "REPORTS", reports)
    for key, value in revised.CONFIG.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("LLM_USAGE_PATH", str(private / "llm_usage.jsonl"))
    monkeypatch.setenv("ARENA_URL", "https://arena.tacto.ai")
    monkeypatch.setenv("ARENA_API_KEY", "local-test-only")
    monkeypatch.setenv("LLM_API_KEY", "local-test-only")
    monkeypatch.setattr(revised, "identity", lambda: {"commit": "tested", "data_fingerprint": "fresh"})
    calls = []

    class Client:
        def __init__(self, retries):
            assert retries == 0

        def me(self):
            calls.append("me")
            return {"team_name": "local", "practice": {"left": 10}, "best": {}}

        def leaderboard(self, set_):
            assert set_ == "practice"
            calls.append("board")
            return {"teams": [{"team_name": "local", "rank": 1, "total": 0}]}

        def cases(self, set_):
            assert set_ == "practice"
            calls.append("cases")
            return [{"case_id": c, "hosted": True} for c in revised.ORDER]

        def open_session(self, *args):
            raise AssertionError("Preparation must never open a session")

    monkeypatch.setattr(revised, "ArenaClient", Client)
    return calls


def test_unapproved_execution_fails_before_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network or preparation before authorization")
    monkeypatch.setattr(revised, "preflight", forbidden)
    with pytest.raises(ValueError, match="Not authorized"):
        revised.run()


def test_original_ledger_stays_exhausted_and_new_batch_is_gated(prepared_env):
    old = bench.PRIVATE / "sessions.jsonl"
    old.write_text("\n".join(json.dumps({"case_id": c}) for c in revised.ORDER))
    previous = old.read_bytes()
    assert bench.forecast()["remaining_sessions"] == 0
    assert bench.forecast(revised.BATCH)["remaining_sessions"] == 10
    with pytest.raises(ValueError, match="fresh explicit approval"):
        bench.run("case:P01", batch=revised.BATCH)
    with pytest.raises(ValueError, match="exhausted"):
        bench.run("case:P01")
    assert old.read_bytes() == previous


def test_prepare_reads_only_and_records_frozen_configuration(prepared_env):
    plan = revised.prepare()
    assert plan["execution_approved"] is False
    assert plan["configuration"]["LLM_EFFORT"] == "high"
    assert plan["forecast"]["maximum_remaining_model_calls"] == 20
    assert prepared_env == ["me", "board", "cases"]
    journal, reports, _ = bench.batch_paths(revised.BATCH)
    assert not journal.exists()
    assert (reports / "readiness.json").exists()
    assert not (reports / "hosted_results.jsonl").exists()


def test_changed_commit_blocks_execution(prepared_env, monkeypatch):
    revised.prepare()
    monkeypatch.setattr(revised, "identity", lambda: {"commit": "changed", "data_fingerprint": "fresh"})
    with pytest.raises(ValueError, match="Code or data changed"):
        revised.run(approved=True)


def test_unknown_batch_cannot_bypass_session_cap():
    with pytest.raises(ValueError, match="Unknown benchmark batch"):
        bench.batch_paths("extra_unlimited")


def test_missing_or_mismatched_model_configuration_blocks(prepared_env, monkeypatch):
    revised.prepare()
    path = bench.PRIVATE / "revised_01_plan.json"
    plan = json.loads(path.read_text())
    plan["configuration"]["LLM_MODEL"] = "different"
    bench.write(path, plan)
    with pytest.raises(ValueError, match="configuration changed"):
        revised.run(approved=True)


def test_failure_stops_batch_and_cannot_auto_resume(prepared_env, monkeypatch):
    revised.prepare()
    attempts = []

    def attempt(case_id, **kwargs):
        attempts.append(case_id)
        assert kwargs["approved"] is True
        journal, reports, _ = bench.batch_paths(kwargs["batch"])
        row = {"case_id": case_id, "status": "completed", "error": None, "buyer_timeouts": 1,
               "model_calls": [], "decisions": [], "result": {"score": 0.4, "deal": True, "must_haves_ok": True}}
        bench.append(journal, {"case_id": case_id})
        bench.append(reports / "hosted_results.jsonl", row)
        return row

    monkeypatch.setattr(bench, "run", attempt)
    with pytest.raises(ValueError, match="Stopped after"):
        revised.run(approved=True)
    assert attempts == ["case:P01"]
    assert revised.summarize()["full_10_case_mean"] is None
    with pytest.raises(ValueError, match="Prior batch failure"):
        revised.run(approved=True)
    assert attempts == ["case:P01"]


def test_insufficient_cumulative_budget_blocks_before_network(prepared_env, monkeypatch):
    monkeypatch.setattr(bench, "forecast", lambda _: {"forecast_total_upper_usd": 5.01})
    with pytest.raises(ValueError, match="cumulative"):
        revised.prepare()
    assert not prepared_env


def test_mock_batch_runs_ten_once_and_preserves_original_ledger(prepared_env, monkeypatch):
    original = bench.PRIVATE / "sessions.jsonl"
    original.write_text("\n".join(json.dumps({"case_id": c}) for c in revised.ORDER))
    before = original.read_bytes()
    revised.prepare()
    attempts = []

    def attempt(case_id, **kwargs):
        assert kwargs["batch"] == revised.BATCH and kwargs["approved"]
        assert kwargs["expected_case"]["case_id"] == case_id
        attempts.append(case_id)
        journal, reports, _ = bench.batch_paths(revised.BATCH)
        row = {"case_id": case_id, "status": "completed", "error": None, "buyer_timeouts": 0,
               "model_calls": [], "decisions": [], "result": {"score": 0.7, "deal": True, "must_haves_ok": True}}
        bench.append(journal, {"case_id": case_id})
        bench.append(reports / "hosted_results.jsonl", row)
        return row

    monkeypatch.setattr(bench, "run", attempt)
    revised.run(approved=True)
    assert attempts == revised.ORDER
    assert revised.summarize()["full_10_case_mean"] == pytest.approx(0.7)
    revised.run(approved=True)
    assert attempts == revised.ORDER  # a repeated command cannot create another session
    assert original.read_bytes() == before
