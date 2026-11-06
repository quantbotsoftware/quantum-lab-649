"""Martorii W1–W12 ai protocolului TU3-SR (tu3/PROTOCOL_TU3_SR.md §5.3 + AMENDAMENT_TU3_SR_01).

W1 identitatea pe 6/49 (scor + SCI) · W2 nucleele MPS · W3 eșantionatorul · W4 fazele · W5 entanglement/min-cut/Dicke ·
W6 formulele §2 · W7 SCI generalizat · W8 mersul înainte (cauzalitate, FAST numai în test) · W9 garda „fără arhivă reală”
și refuzurile `--real` · W10 plafonul VRAM + monitorul termic · W11 sigiliul, fișierele înghețate, importurile ·
W12 (după rulare) PUTERE_SR.json. Testele NU ating serverul de pe 8649 și NU rulează `--real`.
"""
from __future__ import annotations

import ast
import hashlib
import itertools
import json
import math
import os
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
TU3 = ROOT / "tu3"
for _p in (str(ROOT), str(TU3)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import scor_real as SR  # noqa: E402

SEAL = json.loads((TU3 / "SIGILIU_TU3_SR.json").read_text())
ASEAL = json.loads((TU3 / "SIGILIU_AMENDAMENT_TU3_SR_01.json").read_text())
CUDA = torch.cuda.is_available()
FAST = dict(mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60, gamma_grid=12)


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _ro(p) -> bool:
    return (os.stat(p).st_mode & 0o222) == 0


def _close(a, b, rel=1e-9, abs_=0.0):
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_close(x, y, rel, abs_) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    return math.isclose(float(a), float(b), rel_tol=rel, abs_tol=abs_)


def _enumerate_law(mps: SR.UrnMPS) -> dict:
    """|ψ|² pe TOATE configurațiile (b, s_1..s_n[, a]) prin contracția directă a nucleelor (instanțe mici)."""
    cores = [c[0].cpu() for c in mps.cores]
    rb = mps.rb.cpu()
    law = {}
    dims = [c.shape[1] for c in cores]
    for cfg in itertools.product(*[range(d) for d in dims]):
        v = torch.ones(1, dtype=SR.C64)
        for c, s in zip(cores, cfg):
            v = v @ c[:, s, :]
        amp = (v @ rb) if mps.m is None else v[0]
        p = float((amp.abs() ** 2).sum())
        if p > 0:
            b = cfg[0]
            bits = tuple(j for j in range(mps.n) if cfg[1 + j] == 1)
            key = (bits, cfg[-1]) if mps.m is not None else bits
            law[key] = law.get(key, 0.0) + p
    return law


def _exact_law(n, r, gamma, H, m=None, a_star=None, beta=1.0, beta_j=1.0) -> dict:
    subsets = list(itertools.combinations(range(n), r))
    w = [math.exp(beta * (j in H)) if H is not None else 1.0 for j in range(n)]
    Z1 = sum(math.prod(w[j] for j in S) for S in subsets)
    law = {}
    if m is not None:
        ph = [2 * math.pi * a / m for a in range(m)]
        v1 = [math.exp(beta_j * math.cos(ph[a] - ph[a_star])) if a_star is not None else 1.0 for a in range(m)]
        z1 = sum(v1)
    for S in subsets:
        p0 = (1 - gamma) / len(subsets)
        p1 = gamma * math.prod(w[j] for j in S) / Z1 if gamma > 0 else 0.0
        if m is None:
            law[S] = p0 + p1
        else:
            for a in range(m):
                law[(S, a)] = p0 / m + (p1 * v1[a] / z1 if gamma > 0 else 0.0)
    return law


# ---------------- W1: identitatea pe 6/49 ----------------
def _ds649(device):
    import parser as QP
    return QP.build_dataset(QP.DEFAULT_SOURCE, device)


def test_W1_score_identity_649():
    ref = json.loads((ROOT / "rezultate" / "backtest_unic" / "REZULTATE.json").read_text())
    ds = _ds649("cpu")
    res = SR.score_649_from_file(ds.onehot.numpy(), ds.step_offsets.numpy(),
                                 ROOT / "rezultate" / "backtest_unic" / "PREDICTII.npz")
    for part in ("total", "half1", "half2"):
        for k, v in ref[part].items():
            assert _close(res[part][k], v), (part, k, res[part][k], v)
    for g_ref, g in zip(ref["gates"], res["gates"]):
        assert g_ref["gate"] == g["gate"] and g_ref["pass"] == g["pass"] and _close(g["value"], g_ref["value"])
    for k in ("gates_passed", "verdict", "match_dist_QL_v1", "n_targets", "n_steps_predicted", "tickets_changed_vs_B"):
        assert res[k] == ref[k], k
    assert _close(res["match_expected_U"], ref["match_expected_U"])
    assert _close(res["p_exact_hits_QL_ge"], ref["p_exact_hits_QL_ge"])
    assert res["per_target"] == ref["per_target"]
    assert SR.URN_649.tau == 0.20 and SR.URN_649.e_u == 36.0 / 49.0


@pytest.mark.skipif(not CUDA, reason="SCI.json a fost calculat pe CUDA")
def test_W1_sci_identity_649():
    ref = json.loads((ROOT / "rezultate" / "backtest_unic" / "SCI.json").read_text())
    got = SR.sci_649_identity(_ds649("cuda"))
    for k in ("chi_freq", "chi_pair", "overlap"):
        assert _close(got["stats_real"][k], ref["stats_real"][k], rel=1e-12), k
    assert _close(got["stats_real"]["chi_gap"], ref["stats_real"]["chi_gap"], rel=1e-6)
    for part in ("null_mean", "null_std", "z"):
        for k, v in ref[part].items():
            assert _close(got[part][k], v, rel=1e-6, abs_=1e-9), (part, k)
    assert _close(got["SCI"], ref["SCI"], rel=1e-6) and _close(got["p_empirical"], ref["p_empirical"], rel=1e-6)


# ---------------- W2: nucleele MPS = legea exactă ----------------
@pytest.mark.parametrize("gamma", [0.0, 0.5])
def test_W2_cores_exact_law(gamma):
    H = torch.tensor([[0, 2, 5]]) if gamma > 0 else None
    mps = SR.UrnMPS(8, 3, gamma, H=H, n_univ=1)
    law = _enumerate_law(mps)
    ex = _exact_law(8, 3, gamma, {0, 2, 5} if gamma > 0 else None)
    assert set(law) == set(ex) and abs(sum(law.values()) - 1) < 2e-5
    assert max(abs(law[k] - ex[k]) for k in ex) <= 2e-5


def test_W2_null_conditionals():
    n, r = 9, 4
    mps = SR.UrnMPS(n, r, 0.0)
    for j in range(1, n + 1):
        A, Rn = mps.cores[j][0], mps.R[j + 1][0]
        for c in range(0, r + 1):
            if r - c > n - j + 1 or c > j - 1:
                continue
            e = torch.zeros(1, mps.D, dtype=SR.C64)
            e[0, c] = 1.0
            p = [float(((e @ A[:, s, :]) @ Rn @ (e @ A[:, s, :]).conj().T).real) for s in (0, 1)]
            if sum(p) <= 0:
                continue
            assert abs(p[1] / sum(p) - (r - c) / (n - j + 1)) <= 2e-5, (j, c)


# ---------------- W3: eșantionatorul (χ² față de legea exactă) ----------------
def _chi2_p(obs: dict, law: dict, N: int) -> float:
    x = sum((obs.get(k, 0) - N * p) ** 2 / (N * p) for k, p in law.items())
    df = len(law) - 1
    return float(torch.special.gammaincc(torch.tensor(df / 2, dtype=torch.float64), torch.tensor(x / 2,
                                                                                                    dtype=torch.float64)))


@pytest.mark.parametrize("gamma", [0.0, 0.5])
def test_W3_sampler_main(gamma):
    dev = "cuda" if CUDA else "cpu"
    H = torch.tensor([[1, 4, 6]], device=dev) if gamma > 0 else None
    mps = SR.UrnMPS(8, 3, gamma, H=H, device=dev, n_univ=1)
    N = 200_000
    s = mps.sample(N, torch.Generator(device=dev).manual_seed(11), n_univ=1)["main"][0].cpu().numpy()
    assert (s.sum(-1) == 3).all() and set(np.unique(s)) <= {0.0, 1.0}
    obs = {}
    for row in s:
        key = tuple(np.nonzero(row)[0].tolist())
        obs[key] = obs.get(key, 0) + 1
    assert _chi2_p(obs, _exact_law(8, 3, gamma, {1, 4, 6} if gamma > 0 else None), N) > 1e-3


def test_W3_sampler_joker_small():
    dev = "cuda" if CUDA else "cpu"
    mps = SR.UrnMPS(8, 3, 0.5, H=torch.tensor([[0, 3, 7]], device=dev), m=5,
                    a_star=torch.tensor([2], device=dev), device=dev, n_univ=1)
    N = 200_000
    out = mps.sample(N, torch.Generator(device=dev).manual_seed(12), n_univ=1)
    s, a = out["main"][0].cpu().numpy(), out["joker"][0].cpu().numpy()
    assert (s.sum(-1) == 3).all() and a.min() >= 0 and a.max() <= 4
    obs = {}
    for row, aa in zip(s, a):
        key = (tuple(np.nonzero(row)[0].tolist()), int(aa))
        obs[key] = obs.get(key, 0) + 1
    assert _chi2_p(obs, _exact_law(8, 3, 0.5, {0, 3, 7}, m=5, a_star=2), N) > 1e-3
    law = _enumerate_law(mps)
    ex = _exact_law(8, 3, 0.5, {0, 3, 7}, m=5, a_star=2)
    assert max(abs(law[k] - ex[k]) for k in ex) <= 2e-5


# ---------------- W4: fazele nu schimbă legea și nici spectrul ----------------
def test_W4_phases_invariance():
    kw = dict(H=torch.tensor([[0, 3, 7]]), m=5, a_star=torch.tensor([1]), n_univ=1)
    a, b = SR.UrnMPS(8, 3, 0.5, phases=True, **kw), SR.UrnMPS(8, 3, 0.5, phases=False, **kw)
    la, lb = _enumerate_law(a), _enumerate_law(b)
    assert max(abs(la[k] - lb[k]) for k in la) <= 1e-5
    sa, sb = a.joker_cut(), b.joker_cut()
    assert abs(float(sa["S"][0]) - float(sb["S"][0])) <= 1e-5


# ---------------- W5: entanglement, min-cut, Dicke ----------------
def _exact_urn_entropy(m, a_star, gamma, beta_j=1.0):
    ph = np.array([2 * math.pi * a / m for a in range(m)])
    v0 = np.ones(m) / m
    v1 = np.exp(beta_j * np.cos(ph - ph[a_star]))
    v1 = v1 / v1.sum()
    c0, c1 = np.sqrt(v0), np.sqrt(v1)
    rho = (1 - gamma) * np.outer(c0, c0) + gamma * np.outer(c1, c1)
    lam = np.clip(np.linalg.eigvalsh(rho), 0, None)
    lam = lam[lam > 0]
    return float(-(lam * np.log(lam)).sum())


def test_W5_entanglement_and_min_cut():
    nul = SR.UrnMPS(45, 5, 0.0, m=20)
    jc = nul.joker_cut()
    assert float(jc["S"][0]) <= 1e-6 and int(jc["chi_eff"][0]) == 1 and float(jc["min_cut"][0]) == 0.0
    H = torch.tensor([[0, 7, 13, 22, 40], [1, 2, 3, 4, 5]])
    sig = SR.UrnMPS(45, 5, 0.5, H=H, m=20, a_star=torch.tensor([4, 17]), n_univ=2)
    jc = sig.joker_cut()
    for u, a in enumerate((4, 17)):
        S = float(jc["S"][u])
        assert 0 < S <= math.log(2) + 1e-6 and int(jc["chi_eff"][u]) == 2
        assert abs(float(jc["min_cut"][u]) - math.log(2)) < 1e-12 and S <= float(jc["min_cut"][u]) + 1e-6
        assert abs(S - _exact_urn_entropy(20, a, 0.5)) <= 1e-4
    caps = [0.3, 1.2, 0.05, 2.0]
    assert abs(SR.min_cut_chain(caps, 5, range(0, 4)) - 2.0) < 1e-12
    assert abs(SR.min_cut_chain(caps, 5, range(0, 3)) - 0.05) < 1e-12


@pytest.mark.parametrize("n,r", [(40, 6), (45, 5), (20, 1)])
def test_W5_dicke_profile(n, r):
    d = SR.dicke_profile(n, r)
    assert d["max_abs_err"] <= 1e-4
    assert all(s <= b + 1e-6 for s, b in zip(d["S_mps"], d["bound"]))


# ---------------- W6: formulele §2 ----------------
def test_W6_hypergeometric_and_tail():
    small = SR.Urn("t", 10, 4, 3)
    cnt = np.zeros(4)
    ticket = {0, 1, 2}
    for S in itertools.combinations(range(10), 4):
        cnt[len(ticket & set(S))] += 1
    assert np.allclose(SR.hyper_pmf(small), cnt / cnt.sum(), atol=1e-15)
    for u in (SR.URN_540, SR.URN_JMAIN, SR.URN_JBALL, SR.URN_649):
        pmf = SR.hyper_pmf(u)
        assert abs(pmf.sum() - 1) < 1e-12 and abs((pmf * np.arange(len(pmf))).sum() - u.e_u) < 1e-12
    for u in (small, SR.URN_JBALL):
        pmf = SR.hyper_pmf(u)
        T = 3
        brute = np.zeros(T * (len(pmf) - 1) + 1)
        for hs in itertools.product(range(len(pmf)), repeat=T):
            brute[sum(hs)] += math.prod(pmf[h] for h in hs)
        for h in range(len(brute)):
            assert abs(SR.exact_tail(h, T, u) - brute[h:].sum()) < 1e-12


def test_W6_marginal_rule_and_tau():
    rng = np.random.default_rng(0)
    for u in (SR.URN_540, SR.URN_JMAIN, SR.URN_JBALL):
        pi = rng.dirichlet(np.ones(u.n), size=50)
        q = SR.marginal_q(pi, u)
        assert (q >= 1e-4 - 1e-15).all() and (q <= 1 - 1e-4 + 1e-15).all()
        flat = np.full((1, u.n), 1.0 / u.n)
        assert np.allclose(SR.marginal_q(flat, u), u.p0)
        assert np.allclose(SR.marginal_q(pi, u).sum(-1), u.r, atol=1e-9)
    spike = np.zeros((1, 20))
    spike[0, 3] = 1.0
    q = SR.marginal_q(spike, SR.URN_JBALL)
    assert abs(q[0, 3] - (0.05 + 0.5 * 0.95)) < 1e-12
    assert abs(SR.URN_540.tau - 0.2041666667) < 1e-9 and abs(SR.URN_JMAIN.tau - 0.1512345679) < 1e-9
    assert abs(SR.URN_JBALL.tau - 0.0136111111) < 1e-9
    assert (SR.top_k(np.array([[0.1, 0.3, 0.3, 0.3]]), 2) == np.array([[2, 3]])).all()


# ---------------- W7: SCI generalizat ----------------
def test_W7_sci_generalized():
    n, r, Nd = 10, 3, 40
    rng = np.random.default_rng(1)
    oh = np.zeros((1, Nd, n), dtype=np.float32)
    for t in range(Nd):
        oh[0, t, rng.choice(n, r, replace=False)] = 1
    x = torch.tensor(oh)
    sidx, sizes = torch.arange(Nd), torch.ones(Nd, dtype=torch.int64)
    raw = SR.sci_raw(x, sidx, sizes, Nd, r)
    c = oh[0].sum(0).astype(np.float64)
    e1 = r * Nd / n
    assert abs(float(raw["chi_freq"][0]) - ((c - e1) ** 2 / e1).sum()) < 1e-9
    C = oh[0].T.astype(np.float64) @ oh[0]
    e2 = Nd * r * (r - 1) / (n * (n - 1))
    pc = C[np.triu_indices(n, 1)]
    assert abs(float(raw["chi_pair"][0]) - ((pc - e2) ** 2 / e2).sum()) < 1e-9
    oh1 = torch.zeros(1, Nd, n)
    for t in range(Nd):
        oh1[0, t, t % n] = 1.0
    assert "chi_pair" not in SR.sci_raw(oh1, sidx, sizes, Nd, 1)
    assert len(SR.stat_names("joker")) == 8 and len(SR.stat_names("540")) == 4
    ref = {"names": ["a", "b"], "K": 2, "M": 3, "mu": {"a": 0.0, "b": 1.0}, "sd": {"a": 1.0, "b": 2.0}, "ebar": {},
           "sci_null": torch.tensor([0.0, 1.0, 5.0], dtype=torch.float64)}
    ev = SR.sci_evaluate("x", {"a": torch.tensor([1.0], dtype=torch.float64), "b": torch.tensor([3.0],
                                                                                              dtype=torch.float64)}, ref)
    assert abs(float(ev["SCI"][0]) - 2.0 / math.sqrt(2)) < 1e-12 and abs(float(ev["p"][0]) - 2 / 4) < 1e-12
    jo = torch.zeros(2, 50, 20)
    mo = torch.zeros(2, 50, 45)
    for t in range(50):
        jo[:, t, t % 20] = 1
        mo[:, t, [(t + i) % 45 for i in range(5)]] = 1
    cc = SR.cross_chi(mo, jo, 5, 45, 20)
    N = (mo[0].T @ jo[0]).double().numpy()
    E = 50 * (5 / 45) * (1 / 20)
    assert abs(float(cc[0]) - ((N - E) ** 2 / E).sum()) < 1e-9


# ---------------- W8: mersul înainte (cauzalitate, FAST numai în test) ----------------
@pytest.mark.parametrize("game", ["540", "joker"])
def test_W8_walk_forward_causal(game):
    dev = torch.device("cuda" if CUDA else "cpu")
    L = 130
    gen = torch.Generator(device=dev).manual_seed(5)
    U = SR.mps_universes(game, 1, L, 0.5, gen, dev)
    main, jo = U["main"][0], (U["joker_oh"][0] if game == "joker" else None)
    cfg = replace(SR.GAMES[game]["cfg"], **FAST)
    ks = np.array([100, 110, 120])
    seeds = SR.wf_seeds(game, 99, 0, ks)
    p1 = SR.wf_predict(SR.synth_dataset(game, main, jo), game, torch.as_tensor(ks), cfg=cfg, seeds=seeds)
    main2 = main.clone()
    main2[120:] = torch.flip(main2[120:], dims=[-1])
    jo2 = None if jo is None else torch.roll(jo.clone(), 3, dims=-1)
    if jo2 is not None:
        jo2[:120] = jo[:120]
    p2 = SR.wf_predict(SR.synth_dataset(game, main2, jo2), game, torch.as_tensor(ks), cfg=cfg, seeds=seeds)
    for key in ("pi_QL", "piB", "piR") + (("pi_J", "piB_J", "piR_J") if game == "joker" else ()):
        assert np.allclose(p1[key], p2[key], atol=1e-12, rtol=0), key
    assert (p1["variants"] == p2["variants"]).all()
    urn = SR.GAMES[game]["urns"][0]
    V = p1["variants"]
    assert V.shape == (3, 3, urn.k) and V.min() >= 1 and V.max() <= urn.n
    assert all(len(set(v.tolist())) == urn.k for v in V.reshape(-1, urn.k))
    if game == "joker":
        assert (p1["jokers"] == p2["jokers"]).all() and p1["jokers"].min() >= 1 and p1["jokers"].max() <= 20
    comps = SR.score_predictions(game, p1, main.cpu().numpy(), None if jo is None else jo.cpu().numpy(),
                                 np.arange(L + 1))
    assert len(comps) == (2 if game == "joker" else 1) and all(c["n_targets"] == 3 for c in comps)
    d1 = SR.detection_d1(game, comps)
    assert d1["alpha_each"] == (0.005 if game == "joker" else 0.01) and len(d1["p_values"]) == len(comps)


def test_W8_grid_and_seeds():
    g = SR.grid_steps(2490)
    assert len(g) == 192 and g[0] == 100 and g[-1] == 100 + (191 * 2390) // 192 and (np.diff(g) > 0).all()
    s = SR.wf_seeds("joker", 12, 3, np.array([100]))
    assert int(s[0]) == 7 * 10**12 + 452 * 10**9 + 12 * 10**7 + 3 * 10**4 + 100


# ---------------- W9: garda „fără arhivă reală” și refuzurile --real ----------------
def test_W9_guard_and_real_refusals(tmp_path):
    import parser as QP
    import parser_multi as PM
    with SR.forbid_real_archive():
        for f in (lambda: PM.build_game_dataset("540", "frozen"), lambda: PM.resolve_live("joker"),
                  lambda: QP.build_dataset()):
            with pytest.raises(RuntimeError):
                f()
    assert PM.build_game_dataset.__name__ == "build_game_dataset"
    pw = tmp_path / "PUTERE_SR.json"
    called = []
    orig = PM.build_game_dataset
    PM.build_game_dataset = lambda *a, **k: called.append(1)
    try:
        assert SR.run_real("540", "S8", tmp_path, pw, log=lambda *_: None) == 2           # fără PUTERE_SR
        pw.write_text(json.dumps({"games": {"540": {"verdict": "SR_P_FAIL"}}}))
        assert SR.run_real("540", "S8", tmp_path, pw, log=lambda *_: None) == 2           # FAIL
        pw.write_text(json.dumps({"games": {"540": {"verdict": "SR_P_PASS"}}}))
        assert SR.run_real("540", None, tmp_path, pw, log=lambda *_: None) == 2           # fără --sesiune S8
        (tmp_path / "540").mkdir()
        (tmp_path / "540" / "START.json").write_text("{}")
        assert SR.run_real("540", "S8", tmp_path, pw, log=lambda *_: None) == 2           # START există
        assert SR.real_gate("xyz", "S8", tmp_path, pw) is not None
    finally:
        PM.build_game_dataset = orig
    assert called == []
    tree = ast.parse((TU3 / "scor_real.py").read_text())
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and fn.name.startswith("power"):
            names = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
            assert not names & {"build_game_dataset", "resolve_frozen", "resolve_live", "build_dataset"}, fn.name


# ---------------- W10: plafonul VRAM și monitorul termic ----------------
@pytest.mark.skipif(not CUDA, reason="CUDA absent")
def test_W10_vram_cap():
    info = SR.apply_vram_cap("cuda")
    assert info["applied"] and abs(info["fraction"] - 6.2e9 / info["total_bytes"]) < 1e-12
    with pytest.raises(torch.OutOfMemoryError):
        torch.empty(int(6.3e9), dtype=torch.uint8, device="cuda")
    torch.cuda.empty_cache()


def test_W10_thermal_guard():
    seq = iter([60, 70, 68, 66, 64, 60, 66, 63, 62, 50, 50, 50])
    logs = []
    g = SR.ThermalGuard(reader=lambda: next(seq), period=0.0, sleep=lambda s: None, start=False, log=logs.append)
    assert g.wait("general") is True            # 70 ≥ 69 ⇒ pauză până la ≤ 64
    assert g.current == 64
    assert g.wait("general") is False           # 60
    assert g.wait("o6") is True                 # 66 ≥ 66 ⇒ pauză până la ≤ 62
    assert g.current == 62
    st = g.stop()
    assert st["t_max_c"] == 70 and st["pauses"] == 2 and st["temperature_target_met"] is True
    assert st["rule"] == {"general": [69, 64], "o6": [66, 62], "target_lt": 71}


# ---------------- W11: sigiliul, fișierele înghețate, importurile ----------------
def test_W11_seal_frozen_imports():
    assert _sha(TU3 / "PROTOCOL_TU3_SR.md") == SEAL["sha256"] and SEAL["code_files_present"] == []
    assert SEAL["results_present"] is False and SEAL["positive_claims_allowed"] is False
    assert _ro(TU3 / "PROTOCOL_TU3_SR.md") and _ro(TU3 / "SIGILIU_TU3_SR.json")
    assert _sha(TU3 / "AMENDAMENT_TU3_SR_01.md") == ASEAL["sha256"] and ASEAL["code_files_present"] == []
    assert ASEAL["protocol_seal"]["sha256"] == _sha(TU3 / "SIGILIU_TU3_SR.json") and ASEAL["sealed_utc"] > SEAL["sealed_utc"]
    assert _ro(TU3 / "AMENDAMENT_TU3_SR_01.md") and _ro(TU3 / "SIGILIU_AMENDAMENT_TU3_SR_01.json")
    assert SEAL["previous_seal"]["sha256"] == _sha(TU3 / "SIGILIU_TU3_T7C.json") and SEAL["replaceable"] == {}
    # TU3-SR-R (S8, PROTOCOL_TU3_SR_R §4.3 a): fișierele din `replaceable` al sigiliului S8 pot diferi de sigiliul SR
    # numai printr-un lanț inlocuiri_tu3 format EXCLUSIV din înregistrări ale sigiliului tu3/SIGILIU_TU3_SR_R.json
    import inlocuiri_tu3 as INL
    seal_r = json.loads((TU3 / "SIGILIU_TU3_SR_R.json").read_text())
    valid_r = [r for r in INL.load_records(ROOT)[0] if r["seal"] == "tu3/SIGILIU_TU3_SR_R.json"]
    valid_r += [r for r in INL.load_records(ROOT)[0] if r["seal"] == "tu4/SIGILIU_TU4_UI.json"]  # TU4-UI (S14) P4: lanțul sigilat ulterior
    valid_r += [r for r in INL.load_records(ROOT)[0] if r["seal"] == "pl_v3/SIGILIU_PLV3_UI.json"]  # PLV3-UI P4: lanțul sigilat ulterior
    valid_r += [r for r in INL.load_records(ROOT)[0] if r["seal"] == "hs_v4/SIGILIU_HSV4_UI.json"]  # HSV4-UI P4: lanțul sigilat ulterior
    bad = []
    for k, h in SEAL["frozen_hashes"].items():
        if (ROOT / k).is_file() and _sha(ROOT / k) == h:
            continue
        if k in seal_r["replaceable"] and INL.resolve_one(k, h, ROOT, valid_r)[0] == "inlocuit":
            continue
        bad.append(k)
    bad += [k for k, h in SEAL["frozen_external"].items() if _sha(k) != h]
    assert bad == [], bad
    for k in ("engine.py", "parser.py", "tu3/parser_multi.py", "tu3/motor_n.py", "tu3/motor_joker.py", "validare.py",
              "app.py", "tu3/ui_tu3.py", "tests/test_app_tu3.py", "tu3/porturi_712.py", "tu3/inlocuiri_tu3.py"):
        assert k in SEAL["frozen_hashes"], k
    for f in SEAL["new_files_planned"][:2]:
        assert f not in SEAL["frozen_hashes"]
    mods = set()
    for node in ast.walk(ast.parse((TU3 / "scor_real.py").read_text())):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    allowed = set(sys.stdlib_module_names) | {"__future__", "numpy", "torch", "engine", "motor_n", "motor_joker",
                                              "parser_multi", "parser"}
    assert mods <= allowed, mods - allowed
    assert not mods & {"validare", "cs649", "pl649", "gl649", "se649", "bo649", "wu649", "streamlit", "ui_tu3"}
    # TU3-SR-R (S8, PROTOCOL_TU3_SR_R §4.3 b): orice INLOCUIRE_SR_* e validă, trimite la sigiliul S8 și e scrisă după el
    names_r = {r["_name"] for r in valid_r}
    for p in (TU3 / "inlocuiri").glob("INLOCUIRE_SR_*.json"):
        rec = json.loads(p.read_text())
        assert p.name in names_r and rec["seal"] == "tu3/SIGILIU_TU3_SR_R.json", p.name
        assert rec["written_utc"] > seal_r["sealed_utc"], p.name


# ---------------- W12: PUTERE_SR.json (după rulare) ----------------
def test_W12_power_file():
    p = TU3 / "rezultate" / "SR" / "PUTERE_SR.json"
    if not p.exists():
        pytest.skip("PUTERE_SR.json nu există încă (W12 rulează după --putere)")
    d = json.loads(p.read_text())
    assert _ro(p) and d["real_archive_read"] is False and d["positive_claims_allowed"] is False
    assert d["protocol_sha256"] == SEAL["sha256"] and d["amendment_sha256"] == ASEAL["sha256"]
    assert d["start_utc"] > ASEAL["sealed_utc"] and d["witnesses_W1_W11"]["pass"] in (True, False)
    for g, v in d["games"].items():
        sci, wf = v["SCI"], v["walk_forward"]
        assert sci["sets"]["gamma_1_2"]["B"] == 512 and sci["sets"]["control"]["B"] == 512 and sci["M_null"] == 8192
        assert wf["signal"]["B"] == 20 and wf["null"]["B"] == 6 and wf["G"] == 192
        p1 = sci["sets"]["gamma_1_2"]["detected"] / 512 >= 0.90
        p2 = sci["sets"]["control"]["detected"] / 512 <= 0.02
        p3 = sum(u["detected"] for u in wf["signal"]["universes"]) >= 19
        p4 = sum(u["detected"] for u in wf["null"]["universes"]) <= 1
        ok = p1 and p2 and p3 and p4 and d["witnesses_W1_W11"]["pass"]
        assert v["verdict"] == ("SR_P_PASS" if ok else "SR_P_FAIL")
        a = SR.GAMES[g]["alpha_each"]
        for u in wf["signal"]["universes"] + wf["null"]["universes"]:
            assert u["detected"] == any(pv <= a for pv in u["p_values"])
            assert u["targets"] == 192
        if g == "joker":
            assert wf["signal"]["min_cut_ok"] is True
            assert all(u["entanglement"]["S_urns"] <= 1e-6 for u in wf["null"]["universes"])
    s7 = all(v["verdict"] == "SR_P_PASS" for v in d["games"].values())
    assert d["S7_verdict"] == ("S7_PASS" if s7 else "S7_FAIL")
    assert d["resources"]["peak_reserved_bytes"] < 6.2e9 and d["resources"]["vram_under_cap"] is True
