"""Teste unitare CS649 (date construite; numerele arhivei nu sunt folosite)."""
from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cs649 as C  # noqa: E402


def _hist(seed, n, k0=0, two=0.0):
    rng = np.random.default_rng(seed)
    h = []
    for t in range(n):
        sz = 2 if rng.random() < two else 1
        h.append((k0 + t, np.stack([C.uniform_draw(rng) for _ in range(sz)])))
    return h


def test_levels_and_zstar():
    assert C.levels_of(0) == [0, 1, 4, 9]
    assert C.levels_of(104) == [0, 1 + 104 % 3, 4 + 104 % 5, 9 + 104 % 7]
    assert sum(C.zstar(17)) == 4


def test_henderson_equals_primal_small():
    h = _hist([1, 2, 3], 9, k0=41, two=0.3)
    st = C.state_from(h)
    assert C.cs_predict_state(st, 50)["p"] == C.primal_predict(h, 50)


def test_sum_six_and_methods_agree():
    h = _hist([4, 5, 6], 23, k0=3)
    st = C.state_from(h)
    a = C.cs_predict_state(st, 26)
    b = C.cs_predict_state(st, 26, method="gauss_jordan")
    assert sum(a["p"]) == 6 and a["p"] == b["p"]
    f = C.cs_predict_float(st, 26, float(C.TA2), float(C.T2))
    assert max(abs(float(x) - y) for x, y in zip(a["p"], f)) < 1e-12


def test_closed_form_balanced_105():
    h = _hist([7, 8, 9], 105)
    st = C.state_from(h)
    assert C.cs_predict_state(st, 105)["p"] == C.closed_form_balanced(h, 105)


def test_lambda_constants():
    assert C.lam_K(3, 105) == Fraction(90, 391)
    assert C.lam_K(5, 105) == Fraction(54, 355)
    assert C.lam_K(7, 105) == Fraction(270, 2377)
    assert C.lam_0(105) == Fraction(6768, 17303)


def test_ticket_tie_rule():
    p = [Fraction(1, 10)] * 49
    assert C.ticket_exact(p) == [1, 2, 3, 4, 5, 6]


def test_real_refuses_when_started(tmp_path, monkeypatch):
    run = tmp_path / "backtest_unic"
    run.mkdir()
    (run / "START.json").write_text("{}")
    monkeypatch.setattr(C, "OUT", tmp_path)
    assert C.run_real() == 2
