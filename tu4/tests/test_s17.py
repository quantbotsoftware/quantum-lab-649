"""Teste TU4-S17 (protocol tu4/PROTOCOL_TU4_S17.md): definiția liniarității, numărarea progresiilor și
corectitudinea enumerării exacte best-first (A2) față de forța brută, pe dimensiuni mici."""
from __future__ import annotations

import itertools
import math
import random
import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import s17_admisibil as A  # noqa: E402

SEED = 2026102817


def test_is_linear_definition():
    assert A.is_linear([1, 2, 3, 4, 5, 6])
    assert A.is_linear([1, 2, 3, 4, 5])
    assert A.is_linear([30, 5, 10, 25, 15, 20])
    assert A.is_linear([3, 10, 17, 24, 31, 38])
    assert not A.is_linear([1, 2, 3, 4, 5, 7])
    assert not A.is_linear([4, 5, 6, 12, 25, 36])
    assert not A.is_linear([1, 3, 6, 10, 15, 21])
    with pytest.raises(ValueError):
        A.is_linear([1, 2])
    with pytest.raises(ValueError):
        A.is_linear([1, 1, 2])


@pytest.mark.parametrize("n,b", [(n, b) for n in range(6, 16) for b in (3, 4, 5, 6) if b < n])
def test_ap_count_closed_form(n, b):
    brute = sum(A.is_linear(t) for t in itertools.combinations(range(1, n + 1), b))
    assert brute == A.ap_count(n, b)


def _vectors(n):
    rng = random.Random(SEED * 100 + n)
    v_rand = [rng.uniform(-0.05, 0.05) for _ in range(n)]
    pool = [rng.uniform(-0.05, 0.05) for _ in range(3)]
    v_rep = [pool[rng.randrange(3)] for _ in range(n)]
    v_const = [0.0] * n
    return {"aleator": v_rand, "repetat": v_rep, "constant": v_const}


@pytest.mark.parametrize("n,b", [(n, b) for n in range(6, 13) for b in (3, 4, 5)])
def test_heap_equals_brute_force(n, b):
    for name, lw in _vectors(n).items():
        F = [Fraction(x) for x in lw]
        brute = sorted(itertools.combinations(range(1, n + 1), b), key=lambda t: A.exact_key(t, F))
        m = min(40, len(brute))
        got = [t for _, t, _, _ in A.heap_order(lw, b, limit=m)]
        assert got == brute[:m], (name, n, b)
        exp_adm = next(t for t in brute if not A.is_linear(t))
        ah = A.admissible_heap(lw, b)
        assert tuple(ah["admissible"]) == exp_adm, (name, n, b)
        assert ah["rank"] == brute.index(exp_adm) + 1
        assert ah["s_adm"] <= ah["s_top"]


def test_top_matches_stable_argsort():
    import numpy as np
    rng = random.Random(SEED)
    for _ in range(50):
        n = rng.randint(8, 49)
        lw = [round(rng.uniform(-0.03, 0.03), 3) for _ in range(n)]   # multe egalități
        b = rng.randint(3, 6)
        order = np.argsort(-np.asarray(lw), kind="stable")
        exp = sorted(int(i) + 1 for i in order[:b])
        assert sorted(A.label_order(lw)[:b]) == exp


def test_constant_law_gives_lowest_labels_then_first_nonlinear():
    ah = A.admissible_heap([0.0] * 49, 6)
    assert ah["top"] == [1, 2, 3, 4, 5, 6] and ah["admissible"] == [1, 2, 3, 4, 5, 7] and ah["rank"] == 2


def test_log_esp_matches_bruteforce():
    rng = random.Random(SEED + 1)
    lw = [rng.uniform(-0.1, 0.1) for _ in range(9)]
    e = sum(math.exp(sum(lw[i - 1] for i in t)) for t in itertools.combinations(range(1, 10), 4))
    assert abs(A.log_esp(lw, 4) - math.log(e)) <= 1e-12
