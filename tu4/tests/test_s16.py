"""Teste TU4-S16 (protocol tu4/PROTOCOL_TU4_S16.md): identitățile martorilor W0–W4 pe dimensiuni mici."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import s16_martori as M  # noqa: E402


@pytest.fixture(scope="module")
def ip():
    return M.load_ip_core()


@pytest.mark.parametrize("n", [5, 8, 9, 12, 16])
def test_frft_construction_and_unitarity(n):
    basis = M.frft_basis(n)
    I = np.eye(n)
    assert np.abs(M.frft_matrix(n, 0.0, basis) - I).max() <= 1e-10
    assert np.abs(M.frft_matrix(n, 1.0, basis) - M.dft_unitary(n)).max() <= 1e-8
    for a in (0.3, 0.7, 1.9):
        F = M.frft_matrix(n, a, basis)
        assert np.abs(F.conj().T @ F - I).max() <= 1e-10
    assert np.abs(M.frft_matrix(n, 0.3, basis) @ M.frft_matrix(n, 0.4, basis)
                  - M.frft_matrix(n, 0.7, basis)).max() <= 1e-8


def test_orders_hermite():
    for n in (8, 9):
        _, r = M.frft_basis(n)
        exp = list(range(n - 1)) + [n - 1 + int(n % 2 == 0)]
        assert sorted(r.astype(int).tolist()) == exp


def test_fixtures_x2():
    n, k, N = M.NG, M.KG, M.N_DRAWS
    p = k / n
    for (name, x2) in (("F1", 50.0), ("I1", 400.0), ("G", 100.0)):
        c = M.fixtures()[name]
        got = (n - 1) / n * float(((c - N * p) ** 2).sum()) / (N * p * (1 - p))
        assert abs(got - x2) <= 1e-9 * x2
        assert abs(float(c.sum()) - N * k) <= 1e-8


def test_roundtrip_h1_h3(ip):
    checks = M.run_w2_w3(ip)
    assert len(checks) == 3 * len(M.A_GRID) * 3
    assert all(c["ok"] for c in checks)


def test_load_ip_core_refuses_wrong_sha(monkeypatch):
    monkeypatch.setattr(M, "IP_SHA", "0" * 64)
    with pytest.raises(RuntimeError):
        M.load_ip_core()


def test_w4_small_enumeration_identity(ip):
    n, k = 12, 3
    v = M.profile_v(n)
    v = v - v.mean()
    vhat = v / np.linalg.norm(v)
    D = 0.01
    eps = M.calibrate_eps(ip, vhat, k, D)
    lnw = eps * vhat
    cf = M.closed_form(ip, lnw, k)
    assert abs(cf["D_info"] - D) <= 1e-10 * D
    idx = M.all_subsets(n, k)
    assert idx.shape == (math.comb(n, k), k)
    cpu = M.enum_cpu(lnw, idx)
    eag = M.enum_gpu(lnw, idx, compiled=False)
    i1 = M.S_GRID.index(1.0)
    for j in range(len(M.S_GRID)):
        assert abs(cpu["G_P"][j] - cf["G_P"][j]) <= 1e-12
        assert abs(cpu["G_U"][j] - cf["G_U"][j]) <= 1e-12
        assert abs(eag["G_P"][j] - cpu["G_P"][j]) <= 1e-12
        assert cpu["G_P"][j] <= D + 1e-12
        assert cpu["G_U"][j] <= 1e-12
    assert abs(cpu["G_P"][i1] - D) <= 1e-12
    assert abs(cpu["sumP"] - 1.0) <= 1e-12


def test_overbetting_lowers_growth(ip):
    """Supra-pariul (s > 1) scade panta sub legea reală; sub uniform orice pariu are pantă ≤ 0."""
    n, k = 12, 3
    v = M.profile_v(n)
    v = v - v.mean()
    vhat = v / np.linalg.norm(v)
    lnw = M.calibrate_eps(ip, vhat, k, 0.01) * vhat
    cf = M.closed_form(ip, lnw, k, s_grid=(1.0, 2.0, 4.0))
    assert cf["G_P"][0] > cf["G_P"][1] > cf["G_P"][2]
    assert max(cf["G_U"]) < 0
