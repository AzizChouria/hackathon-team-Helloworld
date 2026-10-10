import pytest

from arena_kit import benchmark as bench
from arena_kit import combined_benchmark as combined


@pytest.fixture
def private(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "PRIVATE", tmp_path / "private")
    monkeypatch.setattr(bench, "REPORTS", tmp_path / "reports")
    return tmp_path


def test_execution_gate_precedes_network(monkeypatch):
    monkeypatch.setattr(combined, "configure", lambda: pytest.fail("must not configure"))
    with pytest.raises(ValueError, match="authorization"):
        combined.run()


def test_reserve_is_unique_bounded_and_practice_only(private):
    frozen = {"commit": "test", "data_fingerprint": "test"}
    for c in combined.ORDER:
        combined.reserve(c, frozen)
    with pytest.raises(ValueError):
        combined.reserve(combined.ORDER[0], frozen)
    with pytest.raises(ValueError):
        combined.reserve("case:FINAL01", frozen)
    assert len(bench.records(combined.paths()[0])) == 10


def test_unresolved_session_cannot_be_recreated(private):
    combined.reserve("case:P01", {})
    with pytest.raises(ValueError, match="already attempted"):
        combined.reserve("case:P01", {})


def test_no_deal_is_a_result_but_timeouts_and_invalid_deals_stop():
    row = {"status": "completed", "result": {"deal": False}, "error": None, "buyer_timeouts": 0}
    assert combined.healthy(row)
    assert not combined.healthy({**row, "buyer_timeouts": 1})
    assert not combined.healthy({**row, "result": {"deal": True, "must_haves_ok": False}})


def test_empty_report_does_not_claim_full_mean(private):
    report = combined.summarize()
    assert report["full_10_case_mean"] is None
    assert len(report["not_tested"]) == 10
    assert report["model_calls"] == report["estimated_api_cost_usd"] == 0
