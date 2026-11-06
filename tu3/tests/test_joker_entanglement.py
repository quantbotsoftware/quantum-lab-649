"""Martorii analitici W1–W10 ai modulului J (PROTOCOL_TU3_P1 §3, AMENDAMENT_TU3_01). Toleranță 1e-10 (float64)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joker_entanglement as J  # noqa: E402

TOL = 1e-10
DEV = J.resolve_device()


def _stats_full(P):
    p, q = P.sum(-1), P.sum(-2)
    C, Kt = J.cross_covariance(P, p, q)
    s, S_E, K_S = J.schmidt(P)
    n_j = P.sum(-1) * 1000.0
    hol = J.holonomy(P, p, q, C, n_j)
    return dict(p=p, q=q, C=C, s=s, S_E=S_E, K_S=K_S, I=J.mutual_information(P, p, q), **hol)


def _rand_P(gen, n=45, m=20):
    P = torch.rand((n, m), generator=gen, dtype=J.F64, device=DEV) + 0.05
    return P / P.sum()


def test_w1_product_state():
    g = torch.Generator(device=DEV).manual_seed(1)
    p = torch.rand(45, generator=g, dtype=J.F64, device=DEV) + 0.1
    q = torch.rand(20, generator=g, dtype=J.F64, device=DEV) + 0.1
    p, q = p / p.sum(), q / q.sum()
    st = _stats_full(torch.outer(p, q))
    assert st["C"].abs().max() < TOL
    assert abs(float(st["S_E"])) < TOL and abs(float(st["I"])) < TOL
    assert float(st["s"][1:].abs().max()) < 1e-7          # rang Schmidt 1 (s ~ √eps numeric)
    assert float(st["absDelta"].max()) < TOL and abs(float(st["Phi"])) < TOL


def test_w2_maximal_correlation():
    P = torch.zeros(45, 20, dtype=J.F64, device=DEV)
    P[torch.arange(20), torch.arange(20)] = 1 / 20
    st = _stats_full(P)
    s2 = st["s"] ** 2
    assert torch.allclose(s2, torch.full_like(s2, 1 / 20), atol=TOL)
    assert abs(float(st["S_E"]) - math.log(20)) < TOL
    assert abs(float(st["I"]) - math.log(20)) < TOL
    assert abs(float(st["K_S"]) - 20) < 1e-8


def test_w3_pure_holonomy():
    g = torch.Generator(device=DEV).manual_seed(3)
    P = torch.zeros(45, 20, dtype=J.F64, device=DEV)
    a_of_j = torch.arange(45, device=DEV) % 20
    P[torch.arange(45, device=DEV), a_of_j] = torch.rand(45, generator=g, dtype=J.F64, device=DEV) + 0.1
    P = P / P.sum()
    st = _stats_full(P)
    phi = J.joker_phases(20, DEV)[a_of_j]
    assert (torch.remainder(st["theta"] - phi + math.pi, 2 * math.pi) - math.pi).abs().max() < TOL
    assert (st["r"] - 1).abs().max() < TOL


@pytest.mark.parametrize("shift", [1, 7, 13])
def test_w4_z20_covariance(shift):
    g = torch.Generator(device=DEV).manual_seed(4)
    P = _rand_P(g)
    a, b = _stats_full(P), _stats_full(torch.roll(P, shifts=shift, dims=1))
    rot = 2 * math.pi * shift / 20
    wrap = lambda x: torch.remainder(x + math.pi, 2 * math.pi) - math.pi  # noqa: E731
    assert wrap(b["theta"] - a["theta"] - rot).abs().max() < TOL
    assert wrap(b["vartheta"] - a["vartheta"] - rot).abs().max() < TOL
    for key in ("S_E", "I", "Phi"):
        assert abs(float(a[key] - b[key])) < TOL
    for key in ("Z", "r"):
        assert (a[key] - b[key]).abs().max() < TOL


def test_w5_main_permutation():
    g = torch.Generator(device=DEV).manual_seed(5)
    P = _rand_P(g)
    perm = torch.randperm(45, generator=g, device=DEV)
    a, b = _stats_full(P), _stats_full(P[perm])
    for key in ("S_E", "I", "Phi"):
        assert abs(float(a[key] - b[key])) < TOL
    assert (a["Z"][perm] - b["Z"]).abs().max() < TOL
    assert (a["r"][perm] - b["r"]).abs().max() < TOL


def _synth(B, T, gamma, seed):
    g = torch.Generator(device=DEV).manual_seed(seed)
    return J.synth_universes(B, T, gamma, g, DEV)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="cere CUDA")
def test_w6_gpu_equals_cpu():
    main0, jok0 = _synth(1, 2201, 0.5, 6)
    main, jok = (main0[0] + 1), (jok0[0] + 1)
    a = J.run_joker(main, jok, device="cuda", with_gromov=True, with_kuramoto=True)
    b = J.run_joker(main.cpu(), jok.cpu(), device="cpu", with_gromov=True, with_kuramoto=True)
    for key in ("P", "C", "K", "schmidt", "S_E", "I", "Phi", "Z", "theta", "vartheta"):
        assert (a[key].cpu() - b[key]).abs().max() < TOL, key
    assert (a["field"]["P_born"].cpu() - b["field"]["P_born"]).abs().max() < TOL
    assert abs(float(a["gromov"]["delta"].cpu() - b["gromov"]["delta"])) < 1e-9
    for km in ("kuramoto_Km0", "kuramoto_Km2"):
        assert (a[km]["R_series"].cpu() - b[km]["R_series"]).abs().max() < 1e-8


def test_w7_onehot_and_bincount():
    main0, jok0 = _synth(3, 500, 0.5, 7)
    X, Y = J.onehots(main0, jok0)
    assert torch.all(X.sum(-1) == 5) and torch.all(Y.sum(-1) == 1)
    assert torch.equal(J.joint_counts(main0, jok0), J.joint_counts_onehot(main0, jok0))
    J.validate_draws(main0 + 1, jok0 + 1)
    with pytest.raises(ValueError):
        bad = (main0 + 1).clone()
        bad[0, 0, 1] = bad[0, 0, 0]
        J.validate_draws(bad, jok0 + 1)
    with pytest.raises(ValueError):
        J.validate_draws(main0 + 1, jok0 + 2)          # Joker 21 apare cu probabilitate ~1
    with pytest.raises(ValueError):
        J.validate_draws(main0[..., :4] + 1, jok0 + 1)


def test_w8_gromov():
    n = 7
    star = torch.full((n, n), 2.0, dtype=J.F64, device=DEV)
    star[0, :] = 1.0
    star[:, 0] = 1.0
    star.fill_diagonal_(0.0)
    assert abs(float(J.gromov_delta(star)["delta"])) < TOL
    c4 = torch.tensor([[0, 1, 2, 1], [1, 0, 1, 2], [2, 1, 0, 1], [1, 2, 1, 0]], dtype=J.F64, device=DEV)
    assert abs(float(J.gromov_delta(c4)["delta"]) - 1.0) < TOL
    assert J.gromov_delta(torch.zeros(45, 45, dtype=J.F64, device=DEV))["n_quadruples"] == 148995


def _check_adler(p, absDelta, vartheta):
    out = J.kuramoto_holonomy(p, absDelta, vartheta, Km=0.0, record=False)
    ka = out["kappa"][:, :, None] * absDelta[:, None, :]
    ref = J.adler_reference(out["omega"][:, None, :].expand_as(ka), ka, J.KUR_DT * J.KUR_STEPS)
    ok = ~ref["frontier"]
    assert torch.equal(out["locked"][ok], ref["locked"][ok])
    lk = ok & ref["locked"]
    target = vartheta[:, None, :] + ref["theta_star_minus_vartheta"]
    err = torch.remainder(out["theta"] - target + math.pi, 2 * math.pi) - math.pi
    if bool(lk.any()):
        assert float(err[lk].abs().max()) < 1e-4
    return int(ok.sum()), int(ref["frontier"].sum()), int(lk.sum()), out["substeps"]


def test_w9_adler_null_universe():
    main0, jok0 = _synth(1, 2201, 0.0, 649010)
    counts = J.joint_counts(main0, jok0)
    P, p, q = J.joint_tensor(counts)
    C, _ = J.cross_covariance(P, p, q)
    hol = J.holonomy(P, p, q, C, counts.sum(-1))
    n_ok, n_front, n_lock, sub = _check_adler(p, hol["absDelta"], hol["vartheta"])
    print(f"W9 nul: comparate {n_ok}, frontieră {n_front}, blocate verificate {n_lock}, sub-pași {sub}")
    assert n_ok > 0


def test_w9_adler_fixture():
    g = torch.Generator(device=DEV).manual_seed(9)
    p = torch.rand(1, 45, generator=g, dtype=J.F64, device=DEV) + 0.2
    p = p / p.sum()
    absDelta = torch.rand(1, 45, generator=g, dtype=J.F64, device=DEV) + 0.1
    vartheta = 2 * math.pi * torch.rand(1, 45, generator=g, dtype=J.F64, device=DEV)
    n_ok, n_front, n_lock, sub = _check_adler(p, absDelta, vartheta)
    print(f"W9 fixtură: comparate {n_ok}, frontieră {n_front}, blocate verificate {n_lock}, sub-pași {sub}")
    assert n_lock > 0 and n_ok > n_front


def test_w10_batch_equals_single():
    main0, jok0 = _synth(3, 800, 0.5, 10)
    batch = J.batch_stats(J.joint_counts(main0, jok0))
    for b in range(3):
        one = J.batch_stats(J.joint_counts(main0[b:b + 1], jok0[b:b + 1]))
        for key in ("I", "S_E", "Phi", "K_S"):
            assert abs(float(batch[key][b] - one[key][0])) < TOL, key
