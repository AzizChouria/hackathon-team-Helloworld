import json

import pytest

from arena_kit import benchmark as bench
from arena_kit import model_benchmark as batch
from arena_kit.agents.strategy import BudgetExceeded, OpenAI


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "PRIVATE", tmp_path / "private")
    monkeypatch.setattr(bench, "REPORTS", tmp_path / "reports")
    bench.PRIVATE.mkdir()
    for key, value in batch.CONFIG.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("LLM_USAGE_PATH", str(bench.PRIVATE / "llm_usage.jsonl"))
    journal = bench.batch_paths(batch.BATCH)[0]
    for cid in sorted(batch.PRIOR):
        bench.append(journal, {"case_id": cid})
    return journal


def test_shared_authorization_counter_and_forecast(configured):
    assert bench.batch_paths(batch.BATCH)[0] == bench.batch_paths("revised_01")[0]
    assert len(batch.audit()) == 7
    forecast = bench.forecast(batch.BATCH)
    assert forecast["remaining_sessions"] == 3
    assert forecast["maximum_remaining_model_calls"] == 12
    assert forecast["remaining_upper_usd"] == pytest.approx(3.72)


def test_no_retesting_old_case_slots(configured):
    with pytest.raises(ValueError, match="Only the three"):
        bench.run("case:P01", batch=batch.BATCH, approved=True)


def test_ambiguous_attempt_blocks_restart(configured):
    bench.append(configured, {"case_id": "case:P07"})
    with pytest.raises(ValueError, match="unresolved"):
        batch.audit()


def test_input_forecast_bound_enforced_before_request(configured):
    model = OpenAI()
    with pytest.raises(BudgetExceeded, match="input budget"):
        model("x" * 20000, "{}")
    assert not model.ledger.exists()
    assert not model.metrics


def test_no_approval_no_network():
    with pytest.raises(ValueError, match="approval"):
        batch.run()


def test_remaining_three_run_once_with_frozen_identity(configured, monkeypatch):
    frozen = {"commit": "test", "data_fingerprint": "fixed"}
    monkeypatch.setattr(batch.old, "identity", lambda: frozen)
    monkeypatch.setattr(batch.old, "team_snapshot", lambda client: {})
    monkeypatch.setattr(batch, "ArenaClient", lambda **kwargs: None)
    cases = {cid: {"case_id": cid} for cid in batch.ORDER}
    bench.write(bench.PRIVATE / f"{batch.BATCH}_plan.json",
                {**frozen, "configuration": batch.CONFIG, "order": batch.ORDER, "cases": cases})
    attempts = []
    def attempt(cid, **kwargs):
        assert kwargs["approved"] and kwargs["expected_case"] == cases[cid]
        attempts.append(cid)
        row = {"case_id": cid, "status": "completed", "error": None, "buyer_timeouts": 0,
               "model_calls": [], "decisions": [], "result": {"score": .5, "deal": True, "must_haves_ok": True}}
        bench.append(configured, {"case_id": cid})
        bench.append(bench.REPORTS / batch.BATCH / "hosted_results.jsonl", row)
        return row
    monkeypatch.setattr(bench, "run", attempt)
    batch.run(approved=True)
    batch.run(approved=True)
    assert attempts == batch.ORDER
    assert len(bench.records(configured)) == 10
    summary = json.loads((bench.REPORTS / batch.BATCH / "summary.json").read_text())
    assert summary["full_three_case_mean"] == .5
