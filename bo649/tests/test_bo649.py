"""Teste de inginerie BO649 — numai date construite/sintetice (nu sunt porți predictive)."""
import math
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bo649 as B  # noqa: E402


def _rand_steps(rng, N, kappa, T, maxd=2):
    out = []
    for _ in range(T):
        rows = []
        for _ in range(int(rng.integers(1, maxd + 1))):
            y = [0] * N
            for j in rng.choice(N, kappa, replace=False):
                y[int(j)] = 1
            rows.append(tuple(y))
        out.append(rows)
    return out


def test_exact_recursion_equals_brute_force_in_Q():
    rng = np.random.default_rng(11)
    for h, m0 in [(Fraction(1, 4), Fraction(3)), (Fraction(1, 250), Fraction(12)), (Fraction(5, 6), Fraction(1, 2))]:
        st = _rand_steps(rng, 4, 2, 7)
        ex, br = B.bocpd_exact(st, 4, 2, h, m0), B.bocpd_brute(st, 4, 2, h, m0)
        assert ex["q"] == br["q"] and ex["evidence"] == br["evidence"]
        assert all(sum(q) == 2 for q in ex["q"])


def test_float_matches_exact():
    rng = np.random.default_rng(12)
    st = _rand_steps(rng, 5, 2, 9)
    ex = B.bocpd_exact(st, 5, 2, Fraction(1, 7), Fraction(5, 2))
    fl = B.bocpd([np.array(r, float) for r in st], 5, 2, 1 / 7, 2.5)
    assert np.abs(fl["q"] - np.array([[float(x) for x in q] for q in ex["q"]])).max() < 1e-12
    assert abs(fl["logZ"] - math.log(ex["evidence"])) < 1e-9


def test_h_one_is_prior_and_h_zero_limit_is_full_history():
    rng = np.random.default_rng(13)
    st = [np.array(r, float) for r in _rand_steps(rng, 6, 2, 30)]
    # h → 1: fiecare pas începe un regim nou → predicția = media priorului κ/N
    fl = B.bocpd(st, 6, 2, 1 - 1e-15, 12.0)
    assert np.allclose(fl["q"][1:], 2 / 6, atol=1e-9)
    # h → 0: un singur regim → predicția Beta–Bernoulli pe toată istoria
    fl0 = B.bocpd(st, 6, 2, 1e-300, 12.0)
    c = np.cumsum([s.sum(0) for s in st], 0)
    n = np.cumsum([s.shape[0] for s in st])
    a0 = 12 * 2 / 6
    for s in range(1, 30):
        assert np.allclose(fl0["q"][s], (a0 + c[s - 1]) / (12 + n[s - 1]), atol=1e-9)


def test_marginal_law_and_tickets():
    q = np.full((1, 49), 6 / 49)
    assert np.allclose(B.marginal_q(q / 6), 6 / 49)
    s = np.zeros((1, 49))
    s[0, [48, 3, 7]] = 1.0
    assert B.top6(s).tolist() == [[1, 2, 3, 4, 8, 49]]  # 4, 8, 49 + egalități → numerele mai mici


def test_score_on_synthetic_and_gates_shape():
    sizes = np.array([1] * 150 + [2] * 10 + [1] * 40)
    st = B.synthetic_steps(sizes, [1, 2, 3])
    r = B.score(st, B.predict(st))
    assert r["n_targets"] == int(sizes[100:].sum())
    assert len(r["gates"]) == 6 and r["sum_q_max_abs_err"] < 1e-9
    assert r["verdict"] in ("BO_PROMOVAT_EXPLORATORIU", "BO_NO_PROMOTION_EXPLORATORY")
