"""The gate's own tests: it must fail when it should."""

import json

import pytest

from evalgate import cassette, core, spend


class Fixed:
    def __init__(self, name, scores, gated=True):
        self.name, self.scores, self.gated = name, scores, gated

    def run(self, case):
        s = self.scores[case]
        return core.CaseResult(str(case), s >= 1, float(s))


class TinySuite(core.Suite):
    name = "tiny"
    margin = 0.1

    def cases(self):
        return [0, 1, 2, 3]


def _runs(suite, cand, base):
    cs = suite.cases()
    return [core.run_system(suite, base, cs, True), core.run_system(suite, cand, cs, False)]


def test_candidate_must_beat_best_baseline_by_margin():
    s = TinySuite()
    g = core.gate(s, _runs(s, Fixed("c", [1, 1, 0, 0]), Fixed("b", [1, 1, 0, 0])), None)
    assert not g.passed  # a tie is a failure


def test_candidate_that_beats_baseline_passes():
    s = TinySuite()
    g = core.gate(s, _runs(s, Fixed("c", [1, 1, 1, 0]), Fixed("b", [1, 0, 0, 0])), None)
    assert g.passed


def test_regression_below_floor_fails():
    s = TinySuite()
    runs = _runs(s, Fixed("c", [1, 1, 0, 0]), Fixed("b", [0, 0, 0, 0]))
    assert not core.gate(s, runs, {"c": 0.9}).passed


def test_crashing_case_is_a_failure_not_a_skip():
    class Boom:
        name = "boom"

        def run(self, case):
            raise RuntimeError("provider down")

    s = TinySuite()
    r = core.run_system(s, Boom(), s.cases(), False)
    assert all(not c.passed and "provider down" in c.error for c in r.results)


def test_ungated_reference_is_reported_not_gated():
    s = TinySuite()
    runs = _runs(s, Fixed("c", [1, 1, 1, 1]), Fixed("b", [0, 0, 0, 0]))
    runs.append(core.run_system(s, Fixed("old", [0, 0, 0, 0], gated=False), s.cases(), False))
    assert core.gate(s, runs, None).passed


def test_replay_miss_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALGATE_MODE", "replay")
    c = cassette.Cassette(tmp_path)
    with pytest.raises(cassette.CassetteMiss):
        c.call("chat", {"messages": ["hi"]}, lambda: {"never": "called"})


def test_record_then_replay_is_identical(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALGATE_MODE", "record")
    c = cassette.Cassette(tmp_path)
    first, live = c.call("chat", {"m": 1}, lambda: {"answer": 42})
    assert live and first == {"answer": 42}
    monkeypatch.setenv("EVALGATE_MODE", "replay")
    again, live = c.call("chat", {"m": 1}, lambda: {"answer": "different"})
    assert not live and again == {"answer": 42}


def test_spend_cap_blocks_the_call(tmp_path, monkeypatch):
    monkeypatch.setattr(spend, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setenv("EVALGATE_CAP_AZURE_USD", "0.01")
    spend.record("azure", "gpt-41-mini", 0.009, "t")
    with pytest.raises(spend.SpendCapExceeded):
        spend.check("azure", 0.002)
