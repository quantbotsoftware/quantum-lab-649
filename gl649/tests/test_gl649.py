"""Teste de inginerie GL649 (componente generice; nu sunt porți predictive și nu ating arhiva)."""
from fractions import Fraction
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gl649 as M  # noqa: E402


def test_glyph_matrix():
    G = M.G_INT
    assert G[0][1] == 1 and sum(G[0]) == 1          # 1
    assert G[9][1] == 1 and G[9][0] == 1            # 10
    assert G[10][1] == 2 and sum(G[10]) == 2        # 11
    assert G[48][4] == 1 and G[48][9] == 1          # 49
    assert sum(map(sum, G)) == 9 + 2 * 40
    assert M.G_COLSUM[0] == 4


def test_solve_exact_random():
    rng = np.random.default_rng(1)
    for n in (1, 2, 5, 10):
        A = [[Fraction(int(rng.integers(-9, 10)), int(rng.integers(1, 7))) for _ in range(n)] for _ in range(n)]
        for i in range(n):
            A[i][i] += 50
        B = [[Fraction(int(rng.integers(-9, 10)), int(rng.integers(1, 5))) for _ in range(2)] for _ in range(n)]
        X = M.solve_exact(A, B)
        for i in range(n):
            for c in range(2):
                assert sum(A[i][j] * X[j][c] for j in range(n)) == B[i][c]


def test_solve_exact_needs_pivot():
    A = [[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]]
    X = M.solve_exact(A, [[Fraction(3)], [Fraction(5)]])
    assert X == [[Fraction(5)], [Fraction(3)]]


def test_rotation_history_counts():
    rng = np.random.default_rng(2)
    c = [int(t) for t in rng.multinomial(6 * 60, [1 / 49] * 49)]
    while max(c) > 60:
        c = [int(t) for t in rng.multinomial(6 * 60, [1 / 49] * 49)]
    st = M.rotation_history(c)
    assert len(st) == 60
    assert (np.stack([s[0] for s in st]).sum(0) == np.array(c)).all()
    assert all(s.sum() == 6 for s in st)


def test_digit_perm_is_automorphism():
    for mp in (M.CYCLE5, M.TRANS59, M.compose(M.CYCLE5, M.TRANS59)):
        perm = M.digit_perm(mp)
        for j in range(49):
            gj = M.G_INT[j]
            gp = M.G_INT[perm[j] - 1]
            assert all(gp[mp.get(d, d)] == gj[d] for d in range(10))


def test_real_refuses_repeat():
    if (M.OUT / "backtest_unic" / "START.json").exists():
        assert M.run_real() == 2
