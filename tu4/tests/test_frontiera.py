"""Teste unitare rapide pentru tu4/frontiera.py (TU4-FR, S10). Nu citesc arhivele reale."""
import itertools
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import frontiera as F  # noqa: E402


def test_esym_incl_kl_vs_enumerare():
    w = np.array([0.5, 1.3, 2.0, 0.7, 1.1, 0.9])
    subs = list(itertools.combinations(range(6), 2))
    P = np.array([w[i] * w[j] for i, j in subs])
    Z = P.sum()
    P = P / Z
    assert abs(F.esym(w, 2)[2] - Z) < 1e-12
    pi = np.array([sum(P[s] for s, S in enumerate(subs) if i in S) for i in range(6)])
    assert np.max(np.abs(F.incl(w, 2) - pi)) < 1e-12
    assert abs(F.kl_cp(w, 2) - float(np.sum(P * np.log(P * 15)))) < 1e-12


def test_solve_w_roundtrip_si_uniform():
    rng = np.random.default_rng(3)
    w = np.exp(rng.normal(0, 0.3, 49))
    f = F.incl(w, 6)
    w2 = F.solve_w(f, 6)
    assert np.max(np.abs(w2 / (w / math.exp(np.mean(np.log(w)))) - 1)) < 1e-8
    u = F.solve_w(np.full(49, 6 / 49), 6)
    assert np.max(np.abs(u - 1)) < 1e-12 and abs(F.kl_cp(u, 6)) < 1e-12


def test_hyper_si_pooling():
    h = F.hyper(49, 6)
    assert abs(h.sum() - 1) < 1e-15 and abs(np.dot(np.arange(7), h) - 36 / 49) < 1e-12
    g = F.pooling(h, 2594)
    assert sum(len(x) for x in g) == 7 and all(2594 * h[x].sum() >= 5 for x in g)


def test_statistici_formate():
    rng = np.random.default_rng(5)
    X = F.uniform_batch(rng, 3, 200, 40, 6)
    assert np.all(X.sum(-1) == 6)
    g = F.pooling(F.hyper(40, 6), 199)
    st = F.stats_main(X, 40, 6, g)
    assert all(v.shape == (3,) for v in st.values())
    single = F.stats_main(X[0], 40, 6, g)
    assert all(abs(float(single[k]) - float(st[k][0])) < 1e-6 for k in st)
    sb = F.stats_ball(rng.integers(1, 21, size=(2, 300)))
    assert set(sb) == {"B1", "B2", "B4"}


def test_esantionare_exacta_suma_unu():
    w = np.exp(np.random.default_rng(9).normal(0, 0.5, 8))
    tot = sum(F.seq_prob(w, 3, S) for S in itertools.combinations(range(8), 3))
    assert abs(tot - 1) < 1e-12
