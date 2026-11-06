"""Teste motor QL649 (PREINREGISTRARE §6). Teste de inginerie, nu porți predictive.

Folosesc date SINTETICE (generate aici) pentru proprietăți; nu calculează scoruri
de performanță pe istoria reală.
"""
import datetime as dt
import json
import math
import sys
from dataclasses import replace
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine as E  # noqa: E402
import parser as qp  # noqa: E402

CUDA = torch.cuda.is_available()
DEV = torch.device("cuda" if CUDA else "cpu")
F64 = torch.float64
FAST = replace(E.PROTOCOL, mcmc_steps=400, replicas=4000, poincare_iters=120, kur_steps=80, gamma_grid=16)


def synth(tmp_path, n=150, seed=7, perm=None, name="s.jsonl"):
    rng = np.random.default_rng(seed)
    rows, day = [], 0
    for i in range(n):
        if not (i % 9 == 4):          # zile duble ocazionale
            day += 1
        nums = sorted(int(x) + 1 for x in rng.choice(49, 6, replace=False))
        if perm is not None:
            nums = sorted(int(perm[x - 1]) for x in nums)
        d = (dt.date(2000, 1, 1) + dt.timedelta(days=day)).isoformat()
        rows.append({"draw_date": d, "numbers_sorted": nums, "numbers_as_stored": nums,
                     "draw_key": f"649:{d}:{'-'.join(map(str, nums))}", "draw_kind_as_stored": "regular"})
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


# ---------------- RNG ----------------
def test_rng_device_and_batch_invariant():
    seeds = torch.tensor([1, 2, 3, 649], dtype=torch.int64)
    base = E.stream(seeds, E.TAG_BOLTZ)[:, None]
    ctr = torch.arange(10000, dtype=torch.int64)[None]
    u_cpu = E.uniform(base, ctr)
    assert u_cpu.min() >= 0 and u_cpu.max() < 1
    assert abs(float(u_cpu.mean()) - 0.5) < 0.01 and abs(float(u_cpu.var()) - 1 / 12) < 0.005
    u_one = E.uniform(E.stream(seeds[2:3], E.TAG_BOLTZ)[:, None], ctr)
    assert torch.equal(u_one[0], u_cpu[2])
    assert torch.equal(E.uniform(base, 77)[:, 0], u_cpu[:, 77])
    if CUDA:
        u_gpu = E.uniform(base.cuda(), ctr.cuda()).cpu()
        assert torch.equal(u_cpu, u_gpu)


# ---------------- O1 ----------------
@pytest.mark.parametrize("kappa", [0.3, 0.7, 1.4])
def test_ep_2x2_exact(kappa):
    A = torch.tensor([[[0.0, kappa], [kappa, 0.0]]], dtype=F64, device=DEV)
    D = torch.tensor([[1.0, -1.0]], dtype=F64, device=DEV)
    o = E.op_nonhermitian(A, D, E.PROTOCOL)
    assert bool(o["ep_converged"][0])
    assert abs(complex(o["ep_gamma"][0].item()) - kappa) < 1e-8
    assert abs(complex(o["ep_lambda"][0].item())) < 1e-4
    assert torch.allclose(torch.linalg.vector_norm(o["psi_walk"].to(torch.complex128), dim=-1),
                          torch.ones(1, dtype=F64, device=DEV), atol=1e-6)


def test_nonhermitian_permutation_invariant():
    g = torch.Generator().manual_seed(3)
    M = torch.randn(49, 49, generator=g, dtype=F64)
    A = (M + M.T) / 2
    A.fill_diagonal_(0)
    A = A / torch.linalg.eigvalsh(A).abs().max()
    D = torch.tanh(torch.randn(49, generator=g, dtype=F64))
    p = torch.randperm(49, generator=g)
    cfg = replace(E.PROTOCOL, gamma_grid=12)
    o1 = E.op_nonhermitian(A[None].to(DEV), D[None].to(DEV), cfg)
    o2 = E.op_nonhermitian(A[p][:, p][None].to(DEV), D[p][None].to(DEV), cfg)
    assert abs(float(o1["gamma_q"][0]) - float(o2["gamma_q"][0])) < 1e-12
    assert abs(complex(o1["ep_gamma"][0].item()) - complex(o2["ep_gamma"][0].item())) < 1e-6
    psi1 = o1["psi_walk"][0].abs()
    psi2 = o2["psi_walk"][0].abs()
    assert torch.allclose(psi1[p], psi2, atol=1e-5)


# ---------------- O2 ----------------
def test_amplituhedron_degenerate_and_positive():
    B = 2
    c = torch.ones(B, 49, dtype=F64, device=DEV) * 5
    ew = torch.ones(B, 49, dtype=F64, device=DEV) * 2
    T = torch.zeros(B, 18424, dtype=F64, device=DEV)
    n = torch.full((B,), 10.0, dtype=F64, device=DEV)
    o = E.op_amplituhedron(c, ew, T, n, details=True)
    assert float(o["vol_total"].abs().max()) < 1e-12
    assert torch.allclose(o["amp"], torch.ones_like(o["amp"]))
    g = torch.Generator().manual_seed(5)
    c2 = torch.rand(B, 49, generator=g, dtype=F64).to(DEV) * 50
    ew2 = torch.rand(B, 49, generator=g, dtype=F64).to(DEV) * 5
    o2 = E.op_amplituhedron(c2, ew2, T, n, details=True)
    assert (o2["amp"] >= 0).all() and torch.allclose(o2["amp"].mean(-1), torch.ones(B, dtype=F64, device=DEV))
    S = o2["pair_scatter"]
    assert torch.allclose(S, S.transpose(1, 2)) and (S >= 0).all()
    # verificare brută pe un triplet
    z = o2["z"][0].cpu()
    i, j, l = 3, 17, 40
    v = abs(float(torch.det(torch.stack([z[i], z[j], z[l]]))))
    w = 1.0 / (10 * E.P3 + 1)
    tot = sum(abs(float(torch.det(torch.stack([z[i], z[a], z[b]])))) * w
              for a, b in combinations([x for x in range(49) if x != i], 2))
    S_ij = float(S[0, i, j].cpu())
    S_ref = sum(abs(float(torch.det(torch.stack([z[i], z[j], z[m]])))) * w for m in range(49) if m not in (i, j))
    assert abs(S_ij - S_ref) < 1e-9 * max(1.0, S_ref)
    assert v >= 0 and tot > 0


# ---------------- O3 ----------------
def test_poincare_distance_closed_form():
    r = torch.tensor([0.0, 0.3, 0.6, 0.9, 0.99], dtype=F64)
    x = torch.stack([r, torch.zeros_like(r)], -1)
    d = E.poincare_dist(x, torch.zeros_like(x))
    assert torch.allclose(d, 2 * torch.atanh(r), atol=1e-12)
    a = torch.tensor([[0.2, 0.1]], dtype=F64)
    b = torch.tensor([[-0.4, 0.5]], dtype=F64)
    assert torch.allclose(E.poincare_dist(a, b), E.poincare_dist(b, a))


def test_poincare_stress_decreases_and_anchors(tmp_path):
    ds = qp.build_dataset(synth(tmp_path), device=DEV)
    pre = E.Prefix(ds, E.PROTOCOL, DEV)
    st = pre.state(torch.tensor([ds.n_steps], device=DEV))
    A = E.pair_excess(st["C"], st["n"])
    o0 = E.op_poincare(st["C"], st["n"], A, replace(E.PROTOCOL, poincare_iters=0))
    o1 = E.op_poincare(st["C"], st["n"], A, E.PROTOCOL)
    o2 = E.op_poincare(st["C"], st["n"], A, replace(E.PROTOCOL, poincare_iters=800))
    s0, s1, s2 = (float(o["stress"][0]) for o in (o0, o1, o2))
    assert s1 < 0.8 * s0                      # descreștere substanțială față de inițializare
    assert s2 > 0.95 * s1                     # convergență: dublarea iterațiilor câștigă < 5%
    assert (torch.linalg.vector_norm(o1["x"], dim=-1) < 1).all()
    an = o1["anchors"][0].tolist()
    assert len(set(an)) == 3 and all(1 <= a <= 49 for a in an)
    order = torch.sort(o1["u"][0], descending=True, stable=True).indices[:3] + 1
    assert order.tolist() == an


# ---------------- O4 ----------------
def test_kuramoto_free_rotation_and_sync():
    g = torch.Generator().manual_seed(11)
    th0 = (torch.rand(2, 49, generator=g, dtype=F64) * 2 * math.pi).to(DEV)
    om = torch.rand(2, 49, generator=g, dtype=F64).to(DEV)
    W0 = torch.zeros(2, 49, 49, dtype=F64, device=DEV)
    cfg0 = replace(E.PROTOCOL, kur_K=0.0)
    o = E.kuramoto_run(th0, om, W0, cfg0)
    T = cfg0.kur_dt * cfg0.kur_steps
    assert torch.allclose(o["theta"], torch.remainder(th0 + om * T, 2 * math.pi), atol=1e-9) or \
        torch.allclose(torch.cos(o["theta"]), torch.cos(th0 + om * T), atol=1e-9)
    assert float(o["spikes"].sum()) == 0
    Wf = (torch.ones(1, 49, 49, dtype=F64, device=DEV) - torch.eye(49, dtype=F64, device=DEV)) / 48
    o2 = E.kuramoto_run(th0[:1], torch.zeros(1, 49, dtype=F64, device=DEV), Wf, replace(E.PROTOCOL, kur_K=5.0, kur_steps=400))
    assert float(o2["R_global"][0]) > 0.999


def test_kuramoto_jump_only_partners():
    W = torch.zeros(1, 49, 49, dtype=F64, device=DEV)
    W[0, 0, 1] = W[0, 1, 0] = 1.0
    W[0, 0, 2] = W[0, 2, 0] = 1.0
    th0 = torch.zeros(1, 49, dtype=F64, device=DEV)
    th0[0, 1], th0[0, 2] = 0.9, -0.9   # r_0 sub prag la început
    th0[0, 3] = 2.0
    om = torch.zeros(1, 49, dtype=F64, device=DEV)
    o = E.kuramoto_run(th0, om, W, replace(E.PROTOCOL, kur_K=1.0, kur_steps=100))
    assert float(o["spikes"][0, 0]) >= 1
    assert abs(float(o["theta"][0, 3]) - 2.0) < 1e-12        # neconectat: neatins
    for j in range(4, 49):
        assert float(o["theta"][0, j]) == 0.0


# ---------------- O5 ----------------
def test_born_normalized_and_plain():
    g = torch.Generator().manual_seed(2)
    pw = torch.randn(3, 49, generator=g, dtype=F64) + 1j * torch.randn(3, 49, generator=g, dtype=F64)
    pw = (pw / torch.linalg.vector_norm(pw, dim=-1, keepdim=True)).to(torch.complex64).to(DEV)
    amp = torch.rand(3, 49, generator=g, dtype=F64).to(DEV) + 0.1
    u = torch.rand(3, 49, generator=g, dtype=F64).to(DEV) + 0.1
    th = torch.rand(3, 49, generator=g, dtype=F64).to(DEV) * 6
    W = torch.rand(3, 49, 49, generator=g, dtype=F64).to(DEV)
    W = (W + W.transpose(1, 2)) / 100
    o = E.born_state(pw, amp, u, th, W)
    assert torch.allclose(o["P"].sum(-1), torch.ones(3, dtype=F64, device=DEV)) and (o["P"] >= 0).all()
    o0 = E.born_state(pw, amp, u, th, torch.zeros_like(W))
    m = (pw.to(torch.complex128).abs() ** 2) * amp * u
    assert torch.allclose(o0["P"], m / m.sum(-1, keepdim=True), atol=1e-6)


def test_boltzmann_deterministic_chunk_and_device():
    g = torch.Generator().manual_seed(4)
    P = torch.softmax(torch.randn(5, 49, generator=g, dtype=F64), -1)
    seeds = torch.tensor([10, 11, 12, 13, 14])
    cfg = replace(E.PROTOCOL, replicas=6000)
    a = E.boltzmann_filter(P.to(DEV), seeds, cfg, chunk=5)
    b = E.boltzmann_filter(P.to(DEV), seeds, cfg, chunk=1)
    assert torch.allclose(a["pi"], b["pi"], atol=1e-12, rtol=0)
    assert torch.allclose(a["pi"].sum(-1), torch.ones(5, dtype=F64, device=DEV))
    assert torch.allclose(a["top6_frac"].sum(-1), torch.full((5,), 6.0, dtype=F64, device=DEV))
    if CUDA:
        c = E.boltzmann_filter(P, seeds, cfg, chunk=2)
        assert torch.allclose(a["pi"].cpu(), c["pi"], atol=1e-6)


# ---------------- O6 ----------------
def test_crowd_penalty_cases():
    S = torch.tensor([[1, 2, 3, 10, 20, 30], [5, 10, 15, 20, 25, 30], [1, 11, 21, 31, 41, 45],
                      [4, 17, 23, 36, 42, 49]])
    assert E.crowd_penalty(S).tolist() == [2.0, 2.0, 1.0, 0.0]


def test_mcmc_matches_exact_boltzmann():
    """Instanță mică: doar 8 numere au energie finită → 28 de stări; distribuția finală a 4096 de lanțuri
    la T=1 trebuie să urmeze Boltzmann exact (χ², p > 0.001)."""
    from scipy.stats import chisquare
    good = [2, 7, 11, 19, 23, 31, 40, 47]
    g = torch.Generator().manual_seed(9)
    logpi = torch.full((1, 49), -60.0, dtype=F64)
    logpi[0, good] = torch.log(torch.rand(8, generator=g, dtype=F64) * 0.8 + 0.2)
    A = torch.zeros(1, 49, 49, dtype=F64)
    for a, b in combinations(good, 2):
        A[0, a, b] = A[0, b, a] = float(torch.randn(1, generator=g)) * 0.5
    ov = torch.zeros(1, 49, dtype=F64)
    cfg = replace(E.PROTOCOL, n_temps=1, chains_per_temp=4096, t_lo=1.0, t_hi=1.0, mcmc_steps=1500,
                  crowd_shield=False)
    _, _, S, En = E.mcmc_variant(logpi.to(DEV), A.to(DEV), ov.to(DEV), torch.tensor([123]), cfg, return_states=True)
    S = S[0].cpu()
    states = [tuple(sorted(x + 1 for x in c)) for c in combinations(good, 6)]
    idx = {s: i for i, s in enumerate(states)}
    obs = np.zeros(len(states))
    for row in S.tolist():
        obs[idx[tuple(row)]] += 1
    Es = E.energy(torch.tensor([[list(x - 1 for x in s) for s in states]]), logpi, A, ov, cfg)[0]
    w = torch.exp(-(Es - Es.min()))
    exp = (w / w.sum() * S.shape[0]).numpy()
    assert obs.sum() == S.shape[0]
    assert chisquare(obs, exp).pvalue > 0.001


@pytest.mark.skipif(not CUDA, reason="CUDA absent")
def test_mcmc_finds_global_minimum_exhaustive():
    """Protocol MCMC complet vs enumerare exhaustivă a tuturor celor 13 983 816 combinații pe GPU."""
    g = torch.Generator().manual_seed(21)
    pi = torch.softmax(torch.randn(1, 49, generator=g, dtype=F64) * 0.6, -1).cuda()
    M = torch.randn(49, 49, generator=g, dtype=F64)
    A = ((M + M.T) / 2).fill_diagonal_(0)
    A = (A / torch.linalg.eigvalsh(A).abs().max())[None].cuda()
    logpi = torch.log(pi)
    ov = torch.zeros(1, 49, dtype=F64, device="cuda")
    best, be = E.mcmc_variant(logpi, A, ov, torch.tensor([5]), E.PROTOCOL)
    c4 = torch.tensor(list(combinations(range(49), 4)), device="cuda")
    emin, arg, total = float("inf"), None, 0
    for a in range(49):
        blocks = []
        for b in range(a + 1, 49):
            rest = c4[c4[:, 0] > b]
            if rest.shape[0]:
                ab = torch.tensor([a, b], device="cuda").expand(rest.shape[0], 2)
                blocks.append(torch.cat([ab, rest], 1))
        if not blocks:
            continue
        allc = torch.cat(blocks, 0)
        total += allc.shape[0]
        e = E.energy(allc[None], logpi, A, ov, E.PROTOCOL)[0]
        m = float(e.min())
        if m < emin:
            emin, arg = m, (allc[int(e.argmin())] + 1).tolist()
    assert total == math.comb(49, 6)
    assert abs(float(be[0]) - emin) < 1e-9, (best.tolist(), arg, float(be[0]), emin)
    assert best[0].tolist() == arg


# ---------------- Orchestrare ----------------
def test_causality_and_batch_invariance(tmp_path):
    p = synth(tmp_path, n=140)
    ds = qp.build_dataset(p, device=DEV)
    k = 90
    full = E.score_steps(E.Prefix(ds, FAST, DEV), torch.tensor([k]), FAST)
    # set trunchiat: numai pașii < k
    rows = [json.loads(l) for l in p.read_text().splitlines()]
    keep_dates = set(ds.step_dates[:k])
    q = tmp_path / "trunc.jsonl"
    q.write_text("\n".join(json.dumps(r) for r in rows if r["draw_date"] in keep_dates) + "\n")
    dt = qp.build_dataset(q, device=DEV)
    assert dt.n_steps == k
    trunc = E.score_steps(E.Prefix(dt, FAST, DEV), torch.tensor([k]), FAST)
    assert torch.allclose(full["pi"], trunc["pi"], atol=1e-12, rtol=0)
    assert torch.equal(full["anchors"], trunc["anchors"])
    many = E.score_steps(E.Prefix(ds, FAST, DEV), torch.tensor([40, k, 120]), FAST)
    assert torch.allclose(many["pi"][1], full["pi"][0], atol=1e-9, rtol=0)


def test_permutation_equivariance_of_amp_and_A(tmp_path):
    perm = np.random.default_rng(1).permutation(49) + 1       # număr j → perm[j-1]
    d1 = qp.build_dataset(synth(tmp_path, name="a.jsonl"), device=DEV)
    d2 = qp.build_dataset(synth(tmp_path, perm=perm, name="b.jsonl"), device=DEV)
    k = torch.tensor([d1.n_steps])
    s1 = E.Prefix(d1, FAST, DEV).state(k)
    s2 = E.Prefix(d2, FAST, DEV).state(k)
    P = torch.as_tensor(perm - 1)
    A1, A2 = E.pair_excess(s1["C"], s1["n"]), E.pair_excess(s2["C"], s2["n"])
    assert torch.allclose(A2[0][P][:, P], A1[0], atol=1e-12)
    o1 = E.op_amplituhedron(s1["c"], s1["ew"], s1["T"], s1["n"])
    o2 = E.op_amplituhedron(s2["c"], s2["ew"], s2["T"], s2["n"])
    assert torch.allclose(o2["amp"][0][P], o1["amp"][0], atol=1e-9)


def test_variants_invariants_and_cpu_gpu(tmp_path):
    ds = qp.build_dataset(synth(tmp_path, n=120), device=DEV)
    ks = torch.tensor([ds.n_steps])
    sc = E.score_steps(E.Prefix(ds, FAST, DEV), ks, FAST)
    vv = E.variants_steps(sc["pi"], sc["A"], ks, FAST)
    V = vv["variants"][0].tolist()
    assert len(V) == 3
    for v in V:
        assert len(v) == 6 and len(set(v)) == 6 and v == sorted(v) and all(1 <= x <= 49 for x in v)
    assert len({tuple(v) for v in V}) == 3
    assert torch.allclose(sc["pi"].sum(-1), torch.ones(1, dtype=F64, device=DEV))
    if CUDA:
        dc = ds.to("cpu")
        scc = E.score_steps(E.Prefix(dc, FAST, "cpu"), ks.cpu(), FAST)
        assert torch.allclose(scc["pi"], sc["pi"].cpu(), atol=2e-5)


def test_variants_unique_under_concentrated_pi_amendment02():
    """AMENDAMENT_02: π foarte concentrat pe 6 numere → fără interdicție varianta 2 ar repeta varianta 1."""
    pi = torch.full((2, 49), 1e-4, dtype=F64)
    pi[:, [3, 9, 14, 27, 33, 41]] = 0.2
    pi = pi / pi.sum(-1, keepdim=True)
    A = torch.zeros(2, 49, 49, dtype=F64)
    cfg = replace(E.PROTOCOL, mcmc_steps=600)
    o = E.op_variants(torch.log(pi).to(DEV), A.to(DEV), torch.tensor([1, 2]), cfg)
    for b in range(2):
        V = [tuple(v) for v in o["variants"][b].tolist()]
        assert len(set(V)) == 3, V
        assert V[0] == (4, 10, 15, 28, 34, 42)
    assert (o["energies"] < 1e5).all()
