"""Teste unitare rapide pentru tu4/ip_core.py (S11 IP). Nu evaluează fixturile (sunt martori, nu teste)."""
import itertools
import math
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ip_core as C  # noqa: E402


def _enum_q(lw, k):
    n = len(lw)
    logs = np.array([lw[list(S)].sum() for S in itertools.combinations(range(n), k)])
    return logs


def test_normalizare_modele():
    rng = np.random.default_rng(1)
    for n, k in ((10, 3), (20, 1)):
        p = k / n
        N = 200
        z = rng.normal(size=n)
        z -= z.mean()
        c = N * p + 2 * math.sqrt(N * p * (1 - p)) * z
        Nt, N2t = C.disc_N(N)
        for lw in (C.lw_h1_np(c, N, n, k)[0], C.lw_h2_np(c * Nt / N, Nt, N2t, n, k)[0], C.lw_h3_np(c, N, n, k)[0]):
            logs = _enum_q(lw, k)
            lek = float(torch.log(C.esp(torch.exp(C._t(lw)), k)[k]))
            assert abs(np.exp(logs - lek).sum() - 1) < 1e-12


def test_info_D_enumerare():
    rng = np.random.default_rng(2)
    for n, k in ((9, 3), (20, 1)):
        lw = rng.normal(scale=0.5, size=n)
        logs = _enum_q(lw, k)
        q = np.exp(logs - logs.max())
        q /= q.sum()
        D = float((q * np.log(q * math.comb(n, k))).sum())
        assert abs(D - C.D_np(lw, k)) < 1e-12


def test_esantionare_exacta():
    n, k, T = 6, 2, 60000
    lw = np.array([0.4, -0.2, 0.1, 0.0, -0.5, 0.2])
    g = torch.Generator().manual_seed(3)
    X = C.sample_cp(C._t(lw)[None], k, T, g)[0].numpy()
    assert (X.sum(1) == k).all()
    subsets = list(itertools.combinations(range(n), k))
    pr = np.array([math.exp(lw[list(S)].sum()) for S in subsets])
    pr /= pr.sum()
    idx = {S: j for j, S in enumerate(subsets)}
    cnt = np.zeros(len(subsets))
    for row in X:
        cnt[idx[tuple(np.flatnonzero(row))]] += 1
    chi = ((cnt - T * pr) ** 2 / (T * pr)).sum()
    assert chi < 50   # df 14; p ~ 1e-5


def _naive(Xa, Xf, n, k, B):
    """Implementare pas cu pas (bucle explicite) a celor 3 modele, pentru comparația cu varianta vectorizată."""
    W, T, _ = Xa.shape
    out = {m: np.zeros((W, Xf.shape[1], n)) for m in C.MODELS}
    for w in range(W):
        hist = list(Xa[w])
        for t in range(Xf.shape[1]):
            Hm = np.array(hist)
            c = Hm.sum(0)
            N = len(hist)
            out["H1"][w, t] = C.lw_h1_np(c, N, n, k)[0]
            out["H3"][w, t] = C.lw_h3_np(c, N, n, k)[0]
            ages = np.arange(N - 1, -1, -1)
            wts = C.RHO ** ages
            ct = (Hm * wts[:, None]).sum(0)
            out["H2"][w, t] = C.lw_h2_np(ct, wts.sum(), (wts ** 2).sum(), n, k)[0]
            hist.append(Xf[w, t])
    return out


def test_vectorizat_egal_naiv_si_predictibil():
    n, k = 12, 4
    g = torch.Generator().manual_seed(4)
    strong = 1.2 * torch.linspace(-1, 1, n, dtype=C.DT)[None].expand(3, n).contiguous()
    Xa = C.sample_cp(strong, k, 80, g).to(C.DT)
    Xf = C.sample_cp(strong, k, 15, g).to(C.DT)
    B = C.dct_basis(n)
    v = C.model_logw_all(Xa, Xf, n, k, B)
    nv = _naive(Xa.numpy(), Xf.numpy(), n, k, B)
    for m in C.MODELS:
        assert np.max(np.abs(v[m].numpy() - nv[m])) < 1e-9, m


def test_calibrare():
    g = torch.Generator().manual_seed(5)
    d = C.unit_dirs(3, 49, g, "cpu")
    eps = C.calibrate(d, 6, 0.0464)
    D = C.info_D(eps[:, None] * d, 6)
    assert torch.allclose(D, torch.full_like(D, 0.0464), rtol=1e-10, atol=0)
    s = C.smooth_dirs(2, 20, g, "cpu")
    assert abs(float(s.sum(1).abs().max())) < 1e-12


def test_bilet_si_baza():
    assert C.ticket(np.array([0.1, 0.3, 0.3, -1.0]), 2) == [2, 3]
    B = C.dct_basis(49)
    assert torch.allclose(B.T @ B, torch.eye(4, dtype=C.DT), atol=1e-12)
    assert float((B.sum(0)).abs().max()) < 1e-12
