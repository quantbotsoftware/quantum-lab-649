"""Teste de inginerie WU649 — numai date construite/sintetice (nu sunt porți predictive)."""
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wu649 as W  # noqa: E402


def test_race_identity_exact_in_Q():
    w = [Fraction(3, 2), Fraction(1), Fraction(7, 4), Fraction(2, 3), Fraction(5)]
    tot = Fraction(0)
    for S in ([0, 1], [1, 3], [2, 4], [0, 4], [3, 4]):
        assert W.p_order_exact(S, w) == W.ie_parts_exact(S, w)[0]
    for i in range(5):
        for j in range(i + 1, 5):
            tot += W.ie_parts_exact([i, j], w)[0]
    assert tot == 1


def test_quadrature_and_inclusion_match_exact():
    w = [Fraction(3, 2), Fraction(1), Fraction(7, 4), Fraction(1, 4), Fraction(5)]
    th = np.log([float(x) for x in w])
    sets = [[i, j, k] for i in range(5) for j in range(i + 1, 5) for k in range(j + 1, 5)]
    pex = {tuple(S): W.ie_parts_exact(S, w)[0] for S in sets}
    for S in sets:
        mem, nonmem = W._mem_nonmem([S], 5)
        lp = W.draw_terms(th, mem, nonmem, deriv=False)["logP"][0]
        assert abs(np.exp(lp) - float(pex[tuple(S)])) <= 1e-12 * float(pex[tuple(S)])
    pi = W.inclusion(th, 3)
    for j in range(5):
        assert abs(pi[j] - float(sum(p for S, p in pex.items() if j in S))) <= 1e-12


def test_inclusion_sums_to_kappa_n49():
    th = np.random.default_rng(3).normal(0, 0.3, 49)
    assert abs(W.inclusion(th, 6).sum() - 6) <= 1e-12


def test_fixture_counts_and_B_tie():
    st = W.fixture_hplus()
    c = np.concatenate(st).sum(0)
    assert len(st) == 1200 and np.all(c[:7] == 400) and c[7:].sum() == 4400


def test_real_and_null_refused_when_not_qualified():
    assert W.run_real() == 3
    assert W.run_null(1) == 3
    assert not (W.OUT / "backtest_unic").exists()
