"""Martorii E1–E11 ai modulului E40 (PROTOCOL_TU3_E40.md §3). Teste de inginerie, NU porți predictive.

E1–E10 folosesc numai date SINTETICE generate aici. E11 (fumul produsului pe LIVE 5/40) rulează numai după verdictul
`E40_PASS` al verificării de putere sintetice (§4); altfel este `skip`. Variantele NU se tipăresc și NU se salvează.
"""
import datetime as dt
import hashlib
import json
import math
import sys
from dataclasses import replace
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

HERE = Path(__file__).resolve().parents[1]
QL = HERE.parent
sys.path.insert(0, str(QL))
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import motor_n as M  # noqa: E402
import parser_multi as PM  # noqa: E402

CUDA = torch.cuda.is_available()
DEV = torch.device("cuda" if CUDA else "cpu")
F64 = torch.float64
FAST = replace(E.PROTOCOL, mcmc_steps=400, replicas=4000, poincare_iters=120, kur_steps=80, gamma_grid=16)
FAST540 = replace(FAST, seed_master=540)
S540, S649 = M.SHAPE_540, M.SHAPE_649


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def synth_rows(game, n_rows, seed, perm=None):
    """Rânduri sintetice în schema LIVE (zile duble ocazionale). Numai pentru teste."""
    g = PM.spec(game)
    rng = np.random.default_rng(seed)
    rows, day = [], 0
    for i in range(n_rows):
        if not (i % 9 == 4):
            day += 1
        nums = sorted(int(x) + 1 for x in rng.choice(g.n, g.r, replace=False))
        if perm is not None:
            nums = sorted(int(perm[x - 1]) for x in nums)
        d = (dt.date(2000, 1, 1) + dt.timedelta(days=day)).isoformat()
        rows.append({"draw_key": f"{game}:{d}:{i:05d}", "draw_date": d, "game": game, "numbers": nums,
                     "numbers_order_as_stored": nums, "draw_kind": "regular", "has_source_disagreement": False})
    return rows


def write_rows(tmp_path, rows, name):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def ds540(tmp_path, n_rows=150, seed=7, perm=None, name="s540.jsonl", device=DEV):
    return PM.build_game_dataset("540", write_rows(tmp_path, synth_rows("540", n_rows, seed, perm), name),
                                 device=device)


def ds649(n_rows=140, seed=11):
    rows = synth_rows("649", n_rows, seed)
    t = PM.build_tensors(PM.spec("649"), rows, DEV)
    return SimpleNamespace(n_steps=len(t["step_dates"]), **t, device=DEV)


# ---------------- E1: echivalență bit cu bit cu engine.py la 6/49 ----------------
def test_E1_equivalence_with_engine_649():
    ds = ds649()
    pe, pm = E.Prefix(ds, FAST, DEV), M.Prefix(ds, S649, FAST, DEV)
    ks = torch.tensor([30, 77, ds.n_steps], device=DEV)
    se, sm = pe.state(ks), pm.state(ks)
    for key in se:
        assert torch.equal(se[key], sm[key]), key
    Ae, Am = E.pair_excess(se["C"], se["n"]), M.pair_excess(sm["C"], sm["n"], S649)
    assert torch.equal(Ae, Am)
    oe = E.op_amplituhedron(se["c"], se["ew"], se["T"], se["n"], True)
    om = M.op_amplituhedron(sm["c"], sm["ew"], sm["T"], sm["n"], S649, True)
    for key in oe:
        assert torch.equal(oe[key], om[key]), key
    qe, qm = E.op_poincare(se["C"], se["n"], Ae, FAST), M.op_poincare(sm["C"], sm["n"], Am, S649, FAST)
    for key in qe:
        assert torch.equal(qe[key], qm[key]), key
    sce = E.score_steps(pe, ks, FAST, details=True)
    scm = M.score_steps(pm, ks, FAST, details=True)
    for key in ("pi", "A", "P", "anchors", "core", "gamma_q", "ep_gamma", "psi_f"):
        assert torch.equal(sce[key], scm[key]), key
    assert torch.equal(sce["top6_frac"], scm["topk_frac"])
    th = sce["o4"][0]["theta"]
    W = sce["o4"][0]["W"]
    be = E.born_state(sce["o1"][0]["psi_walk"], sce["o2"][0]["amp"], sce["o3"][0]["u"], th, W, FAST)
    bm = M.born_state(sce["o1"][0]["psi_walk"], sce["o2"][0]["amp"], sce["o3"][0]["u"], th, W, FAST)
    assert torch.equal(be["P"], bm["P"]) and torch.equal(be["psi_f"], bm["psi_f"])
    seeds = E.step_seed(FAST, ks)
    fe, fm = E.boltzmann_filter(be["P"], seeds, FAST), M.boltzmann_filter(bm["P"], seeds, S649, FAST)
    assert torch.equal(fe["pi"], fm["pi"]) and torch.equal(fe["top6_frac"], fm["topk_frac"])
    ve = E.variants_steps(sce["pi"], sce["A"], ks, FAST)
    vm = M.variants_steps(scm["pi"], scm["A"], ks, S649, FAST)
    assert torch.equal(ve["variants"], vm["variants"]) and torch.equal(ve["energies"], vm["energies"])
    S0 = torch.randint(0, 49, (3, 7, 6), device=DEV)
    assert torch.equal(E._code(S0), M.code(S0, S649))


# ---------------- E2: forma 5/40 ----------------
def test_E2_shape_540_invariants(tmp_path):
    ds = ds540(tmp_path)
    assert ds.draws.shape[1] == 6 and ds.onehot.shape[1] == 40
    pre = M.Prefix(ds, S540, FAST540, DEV)
    ks = torch.tensor([ds.n_steps], device=DEV)
    sc = M.score_steps(pre, ks, FAST540, details=True)
    pi, A = sc["pi"][0], sc["A"][0]
    assert pi.shape == (40,) and (pi >= 0).all() and abs(float(pi.sum()) - 1) < 1e-12
    assert A.shape == (40, 40) and torch.equal(A, A.T) and torch.equal(torch.diagonal(A), torch.zeros(40, dtype=F64, device=DEV))
    assert abs(float(torch.linalg.eigvalsh(A).abs().max()) - 1.0) < 1e-12
    W = sc["o4"][0]["W"][0]
    assert W.shape == (40, 40) and (W >= 0).all() and abs(float(W.sum(-1).max()) - 1.0) < 1e-12
    assert abs(float(sc["topk_frac"][0].sum()) - 5.0) < 1e-9
    tri = M.triples(S540, DEV)
    assert tri["I"].shape[0] == math.comb(40, 3) == 9880 and tri["pos"].shape[0] == 20
    o1 = E.op_nonhermitian(sc["A"], sc["D"], replace(FAST540, walk_steps=0))
    assert torch.equal(o1["psi_walk"], torch.full((1, 40), 1 / math.sqrt(40), dtype=torch.complex128,
                                                  device=DEV).to(torch.complex64))
    vv = M.variants_steps(sc["pi"], sc["A"], ks, S540, FAST540)
    V = vv["variants"][0].tolist()
    assert len(V) == 3 and len({tuple(v) for v in V}) == 3
    for v in V:
        assert len(v) == 5 and len(set(v)) == 5 and v == sorted(v) and all(1 <= x <= 40 for x in v)
    assert (vv["energies"] < 1e5).all()


# ---------------- E3: constante ----------------
def test_E3_constants():
    assert S540.P2 == math.comb(38, 4) / math.comb(40, 6) or abs(S540.P2 - math.comb(38, 4) / math.comb(40, 6)) < 1e-17
    assert S540.P2 == 30.0 / 1560.0 and S540.P3 == 120.0 / 59280.0
    assert abs(S540.P3 - math.comb(37, 3) / math.comb(40, 6)) < 1e-17
    assert S649.P2 == E.P2 and S649.P3 == E.P3
    assert len(S540.pairs) == 10 and len(S649.pairs) == 15 and S649.pairs == E.PAIR15
    assert M.PROTOCOL_540 == replace(E.PROTOCOL, seed_master=540)
    assert M.step_seed(M.PROTOCOL_540, 7) == 540 * 100003 + 7


# ---------------- E4: cauzalitate și lot ----------------
def test_E4_causality_and_batch(tmp_path):
    rows = synth_rows("540", 140, 3)
    ds = PM.build_game_dataset("540", write_rows(tmp_path, rows, "a.jsonl"), device=DEV)
    k = 90
    full = M.score_steps(M.Prefix(ds, S540, FAST540, DEV), torch.tensor([k]), FAST540)
    keep = set(ds.step_dates[:k])
    dt_ = PM.build_game_dataset("540", write_rows(tmp_path, [r for r in rows if r["draw_date"] in keep], "t.jsonl"),
                                device=DEV)
    assert dt_.n_steps == k
    trunc = M.score_steps(M.Prefix(dt_, S540, FAST540, DEV), torch.tensor([k]), FAST540)
    assert torch.allclose(full["pi"], trunc["pi"], atol=1e-12, rtol=0)
    assert torch.equal(full["anchors"], trunc["anchors"])
    many = M.score_steps(M.Prefix(ds, S540, FAST540, DEV), torch.tensor([40, k, 120]), FAST540)
    assert torch.allclose(many["pi"][1], full["pi"][0], atol=1e-9, rtol=0)


# ---------------- E5: echivarianță ----------------
def test_E5_permutation_equivariance(tmp_path):
    perm = np.random.default_rng(1).permutation(40) + 1
    d1 = ds540(tmp_path, name="p1.jsonl")
    d2 = ds540(tmp_path, perm=perm, name="p2.jsonl")
    k = torch.tensor([d1.n_steps])
    s1 = M.Prefix(d1, S540, FAST540, DEV).state(k)
    s2 = M.Prefix(d2, S540, FAST540, DEV).state(k)
    P = torch.as_tensor(perm - 1)
    A1, A2 = M.pair_excess(s1["C"], s1["n"], S540), M.pair_excess(s2["C"], s2["n"], S540)
    assert torch.allclose(A2[0][P][:, P], A1[0], atol=1e-12)
    o1 = M.op_amplituhedron(s1["c"], s1["ew"], s1["T"], s1["n"], S540)
    o2 = M.op_amplituhedron(s2["c"], s2["ew"], s2["T"], s2["n"], S540)
    assert torch.allclose(o2["amp"][0][P], o1["amp"][0], atol=1e-9)


# ---------------- E6: QUBO exact-5 vs enumerare exhaustivă ----------------
def test_E6_energy_formula_and_exhaustive_minimum():
    g = torch.Generator().manual_seed(21)
    pi = torch.softmax(torch.randn(1, 40, generator=g, dtype=F64) * 0.6, -1)
    Mx = torch.randn(40, 40, generator=g, dtype=F64)
    A = ((Mx + Mx.T) / 2).fill_diagonal_(0)
    A = (A / torch.linalg.eigvalsh(A).abs().max())[None]
    logpi = torch.log(pi)
    ov = torch.zeros(1, 40, dtype=F64)
    ov[0, [3, 17]] = 1.0
    cfg = M.PROTOCOL_540
    # formula explicită (buclă Python)
    S = torch.stack([torch.randperm(40, generator=g)[:5] for _ in range(64)])[None]
    e = M.energy(S, logpi, A, ov, S540, cfg)[0]
    for i in range(64):
        s = S[0, i].tolist()
        ref = -sum(float(logpi[0, j]) for j in s) - cfg.lam_pair * sum(float(A[0, a, b]) for a, b in combinations(s, 2))
        ref += cfg.mu_crowd * float(E.crowd_penalty(torch.tensor([[x + 1 for x in s]]))[0])
        ref += cfg.mu_overlap * sum(float(ov[0, j]) for j in s)
        assert abs(float(e[i]) - ref) < 1e-12
    # MCMC cu protocolul complet vs toate cele 658 008 combinații
    lp, Ad, ovd = logpi.to(DEV), A.to(DEV), torch.zeros(1, 40, dtype=F64, device=DEV)
    best, be = M.mcmc_variant(lp, Ad, ovd, torch.tensor([5]), S540, cfg)
    allc = torch.tensor(list(combinations(range(40), 5)), device=DEV)
    assert allc.shape[0] == math.comb(40, 5) == 658008
    ea = torch.cat([M.energy(allc[None, s0:s0 + 131072], lp, Ad, ovd, S540, cfg)[0]
                    for s0 in range(0, allc.shape[0], 131072)])
    emin = float(ea.min())
    arg = (allc[int(ea.argmin())] + 1).tolist()
    assert abs(float(be[0]) - emin) < 1e-9, (best.tolist(), arg)
    assert best[0].tolist() == arg


# ---------------- E7: Boltzmann exact pe 56 de stări ----------------
def test_E7_mcmc_matches_exact_boltzmann():
    from scipy.stats import chisquare
    good = [2, 7, 11, 19, 23, 31, 36, 39]
    g = torch.Generator().manual_seed(9)
    logpi = torch.full((1, 40), -60.0, dtype=F64)
    logpi[0, good] = torch.log(torch.rand(8, generator=g, dtype=F64) * 0.8 + 0.2)
    A = torch.zeros(1, 40, 40, dtype=F64)
    for a, b in combinations(good, 2):
        A[0, a, b] = A[0, b, a] = float(torch.randn(1, generator=g)) * 0.5
    ov = torch.zeros(1, 40, dtype=F64)
    cfg = replace(M.PROTOCOL_540, n_temps=1, chains_per_temp=4096, t_lo=1.0, t_hi=1.0, mcmc_steps=1500,
                  crowd_shield=False)
    _, _, S, _ = M.mcmc_variant(logpi.to(DEV), A.to(DEV), ov.to(DEV), torch.tensor([123]), S540, cfg,
                                return_states=True)
    states = [tuple(x + 1 for x in c) for c in combinations(good, 5)]
    assert len(states) == 56
    idx = {s: i for i, s in enumerate(states)}
    obs = np.zeros(len(states))
    for row in S[0].cpu().tolist():
        obs[idx[tuple(row)]] += 1
    Es = M.energy(torch.tensor([[list(x - 1 for x in s) for s in states]]), logpi, A, ov, S540, cfg)[0]
    w = torch.exp(-(Es - Es.min()))
    exp = (w / w.sum() * S.shape[1]).numpy()
    assert obs.sum() == 4096
    assert chisquare(obs, exp).pvalue > 0.001


# ---------------- E8: π concentrat ⇒ varianta 1 = cele 5, variante distincte ----------------
def test_E8_concentrated_pi():
    pi = torch.full((2, 40), 1e-4, dtype=F64)
    pi[:, [4, 13, 22, 30, 38]] = 0.2
    pi = pi / pi.sum(-1, keepdim=True)
    A = torch.zeros(2, 40, 40, dtype=F64)
    cfg = replace(M.PROTOCOL_540, mcmc_steps=600)
    o = M.op_variants(torch.log(pi).to(DEV), A.to(DEV), torch.tensor([1, 2]), S540, cfg)
    for b in range(2):
        V = [tuple(v) for v in o["variants"][b].tolist()]
        assert len(set(V)) == 3, V
        assert V[0] == (5, 14, 23, 31, 39)
    assert (o["energies"] < 1e5).all()


# ---------------- E9: GPU = CPU, final_state = Prefix.state, lot = unul câte unul ----------------
def test_E9_device_final_state_and_universe_batch(tmp_path):
    ds = ds540(tmp_path, n_rows=120)
    ks = torch.tensor([ds.n_steps])
    sc = M.score_steps(M.Prefix(ds, S540, FAST540, DEV), ks, FAST540)
    if CUDA:
        dc = ds.to("cpu")
        scc = M.score_steps(M.Prefix(dc, S540, FAST540, "cpu"), ks.cpu(), FAST540)
        assert torch.allclose(scc["pi"], sc["pi"].cpu(), atol=2e-5)
    # final_state vectorizat = Prefix.state(n_steps), bit cu bit (cu zile duble)
    dss = [ds540(tmp_path, n_rows=120, seed=s, name=f"u{s}.jsonl") for s in (7, 8, 9)]
    assert all(torch.equal(d.step_index, dss[0].step_index) for d in dss)
    draws = torch.stack([d.draws for d in dss])
    fs = M.final_state(draws, dss[0].step_index, dss[0].n_steps, S540, FAST540)
    for b, d in enumerate(dss):
        st = M.Prefix(d, S540, FAST540, DEV).state(torch.tensor([d.n_steps]))
        for key in st:
            assert torch.equal(st[key][0], fs[key][b]), key
    # universuri în lot = unul câte unul
    seeds = torch.tensor([11, 12, 13])
    allb = M.score_states(fs, seeds, S540, FAST540)
    for b in range(3):
        one = M.score_states({kk: vv[b:b + 1] for kk, vv in fs.items()}, seeds[b:b + 1], S540, FAST540)
        assert torch.allclose(one["pi"][0], allb["pi"][b], atol=1e-9, rtol=0)


# ---------------- E10: integritate ----------------
def test_E10_integrity_hashes():
    seal = json.loads((HERE / "SIGILIU_TU3_E40.json").read_text())
    assert sha(HERE / "PROTOCOL_TU3_E40.md") == seal["sha256"]
    assert seal["code_files_present"] == [] and seal["results_present"] is False
    assert sha(QL / "engine.py") == seal["engine_sha256"] == "1da9be4e05bcefe401c299b6e6cd0ca7e4d6057939756057822cb43c951cb2ae"
    assert sha(QL / "parser.py") == seal["parser_sha256"] == "219e5d2085a72e960583830a6acd009e376f01079381ad0e09824fd200ee8968"
    assert sha(HERE / "parser_multi.py") == seal["parser_multi_sha256"]
    assert sha(HERE / "PROTOCOL_TU3_P1.md") == seal["parent_protocol_sha256"]


# ---------------- E11: fumul produsului pe LIVE (numai după E40_PASS) ----------------
@pytest.mark.skipif(M.power_verdict() != "E40_PASS", reason="E11 cere verdictul E40_PASS al verificării de putere (§4)")
def test_E11_live_product_smoke():
    ds = PM.build_game_dataset("540", "live", device=DEV)
    out = M.run_full_540(ds)
    assert out["is_protocol"] is True and out["source_kind"] == "live" and out["positive_claims_allowed"] is False
    assert out["game"] == "540" and out["dataset_game"] == "540" and out["n_steps"] == ds.n_steps
    assert out["protocol_sha256"] == json.loads((HERE / "SIGILIU_TU3_E40.json").read_text())["sha256"]
    pi, A = out["pi"], out["A"]
    assert pi.shape == (40,) and abs(float(pi.sum()) - 1) < 1e-12 and torch.equal(A, A.T)
    V = out["variants"]
    assert len(V) == 3 and len({tuple(v) for v in V}) == 3
    for v in V:
        assert len(v) == 5 and len(set(v)) == 5 and v == sorted(v) and all(1 <= x <= 40 for x in v)
    assert all(e < 1e5 for e in out["energies"])
