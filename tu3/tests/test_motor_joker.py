"""Martorii EJ1–EJ12 ai modulului E-J (PROTOCOL_TU3_EJ.md §3). Teste de inginerie, NU porți predictive.

EJ1–EJ11 folosesc numai date SINTETICE generate aici. EJ12 (fumul produsului pe LIVE Joker) rulează numai după
verdictul `EJ_PASS` al verificării de putere sintetice (§4); altfel este `skip`. Variantele NU se tipăresc/salvează.
"""
import datetime as dt
import hashlib
import json
import math
import sys
from dataclasses import replace
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest
import torch

HERE = Path(__file__).resolve().parents[1]
QL = HERE.parent
sys.path.insert(0, str(QL))
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import joker_entanglement as JE  # noqa: E402
import motor_joker as MJ  # noqa: E402
import motor_n as M  # noqa: E402
import parser_multi as PM  # noqa: E402

CUDA = torch.cuda.is_available()
DEV = torch.device("cuda" if CUDA else "cpu")
F64 = torch.float64
SJ = MJ.SHAPE_JOKER
FASTJ = replace(MJ.PROTOCOL_JOKER, mcmc_steps=400, replicas=4000, poincare_iters=120, kur_steps=80, gamma_grid=16)


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def synth_rows(n_rows, seed, perm=None, jshift=0):
    """Rânduri Joker sintetice în schema LIVE (zile duble ocazionale). Numai pentru teste."""
    rng = np.random.default_rng(seed)
    rows, day = [], 0
    for i in range(n_rows):
        if not (i % 9 == 4):
            day += 1
        nums = sorted(int(x) + 1 for x in rng.choice(45, 5, replace=False))
        jk = int(rng.integers(1, 21))
        if perm is not None:
            nums = sorted(int(perm[x - 1]) for x in nums)
        jk = (jk - 1 + jshift) % 20 + 1
        d = (dt.date(2000, 1, 1) + dt.timedelta(days=day)).isoformat()
        rows.append({"draw_key": f"joker:{d}:{i:05d}", "draw_date": d, "game": "joker", "numbers": nums,
                     "numbers_order_as_stored": nums, "joker": jk, "draw_kind": "regular",
                     "has_source_disagreement": False})
    return rows


def write_rows(tmp_path, rows, name):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def dsJ(tmp_path, n_rows=150, seed=7, perm=None, jshift=0, name="sj.jsonl", device=DEV):
    return PM.build_game_dataset("joker", write_rows(tmp_path, synth_rows(n_rows, seed, perm, jshift), name),
                                 device=device)


def rand_variants(B, Vn, seed):
    g = torch.Generator().manual_seed(seed)
    return torch.stack([torch.stack([torch.randperm(45, generator=g)[:5] for _ in range(Vn)]) for _ in range(B)])


# ---------------- EJ1: constante ----------------
def test_EJ1_constants():
    assert SJ.n == 45 and SJ.r == 5 and SJ.k == 5
    assert SJ.P2 == 20.0 / 1980.0 and abs(SJ.P2 - math.comb(43, 3) / math.comb(45, 5)) < 1e-17
    assert SJ.P3 == 60.0 / 85140.0 and abs(SJ.P3 - math.comb(42, 2) / math.comb(45, 5)) < 1e-17
    tri = M.triples(SJ, DEV)
    assert tri["I"].shape[0] == math.comb(45, 3) == 14190 and tri["pos"].shape[0] == 10
    assert len(SJ.pairs) == 10
    assert MJ.PROTOCOL_JOKER == replace(E.PROTOCOL, seed_master=4520)
    assert M.step_seed(MJ.PROTOCOL_JOKER, 7) == 4520 * 100003 + 7
    S0 = torch.tensor([[[0, 1, 2, 3, 44]]])
    assert int(M.code(S0, SJ)[0, 0]) == 0 * 46**4 + 1 * 46**3 + 2 * 46**2 + 3 * 46 + 44


# ---------------- EJ2: forma 5/45 + variante 5+1 ----------------
def test_EJ2_shape_joker_invariants(tmp_path):
    ds = dsJ(tmp_path)
    assert ds.draws.shape[1] == 5 and ds.onehot.shape[1] == 45 and ds.cross_counts.shape == (45, 20)
    ks = torch.tensor([ds.n_steps], device=DEV)
    sc = M.score_steps(M.Prefix(ds, SJ, FASTJ, DEV), ks, FASTJ, details=True)
    W = sc["o4"][0]["W"][0]
    assert W.shape == (45, 45) and (W >= 0).all() and abs(float(W.sum(-1).max()) - 1.0) < 1e-12
    assert abs(float(sc["topk_frac"][0].sum()) - 5.0) < 1e-9
    out = MJ.engine_joker(ds, FASTJ, DEV)
    pi, A = out["pi"], out["A"]
    assert pi.shape == (45,) and (pi >= 0).all() and abs(float(pi.sum()) - 1) < 1e-12
    assert A.shape == (45, 45) and torch.equal(A, A.T) and torch.equal(torch.diagonal(A), torch.zeros(45, dtype=F64, device=DEV))
    assert abs(float(torch.linalg.eigvalsh(A).abs().max()) - 1.0) < 1e-12
    V = out["variants_5plus1"]
    assert len(V) == 3 and len({(tuple(v), a) for v, a in V}) == 3 and len({tuple(v) for v, _ in V}) == 3
    for v, a in V:
        assert len(v) == 5 and len(set(v)) == 5 and v == sorted(v) and all(1 <= x <= 45 for x in v)
        assert isinstance(a, int) and 1 <= a <= 20
    assert all(e < 1e5 for e in out["energies_main"])
    q = out["q_joker"]
    assert q.shape == (3, 20) and (q >= 0).all() and torch.allclose(q.sum(-1), torch.ones(3, dtype=F64, device=DEV), atol=1e-12)
    assert out["is_protocol"] is False and out["game"] == "joker" and out["positive_claims_allowed"] is False
    assert out["protocol_sha256"] == sha(HERE / "PROTOCOL_TU3_EJ.md")
    for et, em, ej in zip(out["energies_total"], out["energies_main"], out["energies_joker"]):
        assert et == em + ej


# ---------------- EJ3: tensorul comun ----------------
def test_EJ3_joint_tensor(tmp_path):
    ds = dsJ(tmp_path, n_rows=200, seed=3)
    N = MJ.cross_prefix(ds, ds.n_steps)
    assert torch.equal(N, ds.cross_counts.to(F64))
    jc = JE.joint_counts(ds.draws - 1, ds.joker - 1)[0]
    assert torch.equal(N, jc)
    assert torch.equal(N.sum(-1), ds.onehot.sum(0).to(F64))
    assert torch.equal(N.sum(0), 5 * torch.bincount(ds.joker - 1, minlength=20).to(F64))
    assert float(N.sum()) == 5 * ds.n_draws


# ---------------- EJ4: condiționată + holonomie ----------------
def test_EJ4_conditional_and_holonomy(tmp_path):
    ds = dsJ(tmp_path, n_rows=200, seed=4)
    N = MJ.cross_prefix(ds, ds.n_steps)
    V0 = rand_variants(1, 6, 4).to(DEV)
    q = MJ.joker_conditional(N[None], V0)[0]
    P, p, qm = JE.joint_tensor(N[None])
    C, _ = JE.cross_covariance(P, p, qm)
    hj = JE.holonomy(P, p, qm, C, N.sum(-1)[None])["h"][0]
    hV = MJ.variant_holonomy(q[None])[0]
    for v in range(6):
        idx = V0[0, v]
        ref = P[0, idx].sum(0) / p[0, idx].sum()
        assert torch.allclose(q[v], ref, atol=1e-12, rtol=0)
        assert abs(float(q[v].sum()) - 1.0) < 1e-12
        href = (p[0, idx].to(torch.complex128) * hj[idx]).sum() / p[0, idx].sum()
        assert abs(complex(hV[v]) - complex(href)) < 1e-12


# ---------------- EJ5: alegerea Joker-ului ----------------
def test_EJ5_joker_choice_exhaustive_and_constructed():
    g = torch.Generator().manual_seed(5)
    N = torch.randint(0, 6, (4, 45, 20), generator=g).to(F64)
    V0 = rand_variants(4, 3, 55)
    ch = MJ.choose_jokers(MJ.joker_conditional(N, V0), MJ.PROTOCOL_JOKER)
    mu = MJ.PROTOCOL_JOKER.mu_overlap
    for b in range(4):
        ov = [0] * 20
        for v in range(3):
            num = [sum(float(N[b, j, a]) for j in V0[b, v].tolist()) for a in range(20)]
            den = sum(num)
            q = [x / den for x in num] if den > 0 else [1 / 20] * 20
            Es = [-math.log(max(q[a], 1e-300)) + mu * ov[a] for a in range(20)]
            best = 0
            for a in range(1, 20):
                if Es[a] < Es[best]:
                    best = a
            assert int(ch["jokers"][b, v]) == best + 1
            assert abs(float(ch["E_J"][b, v]) - Es[best]) < 1e-12
            ov[best] += 1
    # modul marginal ≠ modul condiționat ⇒ se alege cel condiționat
    Nc = torch.zeros(1, 45, 20, dtype=F64)
    Nc[0, 10:, 0] = 50.0
    Nc[0, :5, 7] = 3.0
    Nc[0, :5, 0] = 1.0
    Vc = torch.arange(5)[None, None]
    assert int(Nc[0].sum(0).argmax()) == 0
    assert int(MJ.choose_jokers(MJ.joker_conditional(Nc, Vc))["jokers"][0, 0]) == 8
    # numitor 0 ⇒ uniform ⇒ Joker-ii 1, 2, 3
    Nz = torch.randint(1, 5, (1, 45, 20), generator=g).to(F64)
    Nz[0, :5] = 0.0
    Vz = torch.arange(5)[None, None].expand(1, 3, 5)
    qz = MJ.joker_conditional(Nz, Vz)
    assert torch.equal(qz, torch.full_like(qz, 1 / 20))
    assert MJ.choose_jokers(qz)["jokers"][0].tolist() == [1, 2, 3]


# ---------------- EJ6: covarianță Z_20 ----------------
def test_EJ6_z20_covariance(tmp_path):
    s = 7
    d1 = dsJ(tmp_path, n_rows=600, seed=61, name="z1.jsonl")
    d2 = dsJ(tmp_path, n_rows=600, seed=61, jshift=s, name="z2.jsonl")
    assert torch.equal(d1.draws, d2.draws)
    N1, N2 = MJ.cross_prefix(d1, d1.n_steps), MJ.cross_prefix(d2, d2.n_steps)
    assert torch.equal(N2, torch.roll(N1, s, dims=-1))
    ks = torch.tensor([d1.n_steps], device=DEV)
    sc1 = M.score_steps(M.Prefix(d1, SJ, FASTJ, DEV), ks, FASTJ)
    sc2 = M.score_steps(M.Prefix(d2, SJ, FASTJ, DEV), ks, FASTJ)
    assert torch.equal(sc1["pi"], sc2["pi"]) and torch.equal(sc1["A"], sc2["A"])
    V = M.variants_steps(sc1["pi"], sc1["A"], ks, SJ, FASTJ)["variants"]
    V2 = M.variants_steps(sc2["pi"], sc2["A"], ks, SJ, FASTJ)["variants"]
    assert torch.equal(V, V2)
    j1, j2 = MJ.joker_stage(N1[None], V, FASTJ), MJ.joker_stage(N2[None], V, FASTJ)
    assert torch.equal(j2["q"], torch.roll(j1["q"], s, dims=-1))
    Es = torch.sort(j1["E_J_all"][0], dim=-1).values
    assert bool((Es[:, 1] > Es[:, 0]).all()), "fixtura trebuie să aibă minim unic"
    assert torch.equal(j2["jokers"], (j1["jokers"] - 1 + s) % 20 + 1)
    # q continuu aleator (minime unice a.s.)
    g = torch.Generator().manual_seed(6)
    q = torch.softmax(torch.randn(8, 3, 20, generator=g, dtype=F64), -1)
    a1, a2 = MJ.choose_jokers(q)["jokers"], MJ.choose_jokers(torch.roll(q, s, dims=-1))["jokers"]
    assert torch.equal(a2, (a1 - 1 + s) % 20 + 1)


# ---------------- EJ7: cauzalitate ----------------
def test_EJ7_causality(tmp_path):
    rows = synth_rows(140, 3)
    ds = PM.build_game_dataset("joker", write_rows(tmp_path, rows, "a.jsonl"), device=DEV)
    k = 90
    full = MJ.engine_joker(ds, FASTJ, DEV, k=k)
    keep = set(ds.step_dates[:k])
    dt_ = PM.build_game_dataset("joker", write_rows(tmp_path, [r for r in rows if r["draw_date"] in keep], "t.jsonl"),
                                device=DEV)
    assert dt_.n_steps == k
    trunc = MJ.engine_joker(dt_, FASTJ, DEV)
    assert torch.allclose(full["pi"], trunc["pi"], atol=1e-12, rtol=0)
    assert full["variants"] == trunc["variants"]
    assert torch.equal(full["cross_counts"], trunc["cross_counts"])
    assert torch.equal(full["cross_counts"], dt_.cross_counts.to(F64))
    assert torch.equal(full["q_joker"], trunc["q_joker"]) and full["jokers"] == trunc["jokers"]


# ---------------- EJ8: echivarianță la permutarea etichetelor principale ----------------
def test_EJ8_main_permutation(tmp_path):
    perm = np.random.default_rng(1).permutation(45) + 1
    d1 = dsJ(tmp_path, name="p1.jsonl")
    d2 = dsJ(tmp_path, perm=perm, name="p2.jsonl")
    P = torch.as_tensor(perm - 1, device=DEV)
    N1, N2 = MJ.cross_prefix(d1, d1.n_steps), MJ.cross_prefix(d2, d2.n_steps)
    assert torch.equal(N2[P], N1)
    V0 = rand_variants(1, 5, 8).to(DEV)
    q1 = MJ.joker_conditional(N1[None], V0)
    q2 = MJ.joker_conditional(N2[None], P[V0])
    assert torch.equal(q1, q2)
    k = torch.tensor([d1.n_steps])
    s1 = M.Prefix(d1, SJ, FASTJ, DEV).state(k)
    s2 = M.Prefix(d2, SJ, FASTJ, DEV).state(k)
    A1, A2 = M.pair_excess(s1["C"], s1["n"], SJ), M.pair_excess(s2["C"], s2["n"], SJ)
    assert torch.allclose(A2[0][P][:, P], A1[0], atol=1e-12)


# ---------------- EJ9: GPU = CPU, final_state, lot ----------------
def test_EJ9_device_final_state_and_batch(tmp_path):
    ds = dsJ(tmp_path, n_rows=120)
    ks = torch.tensor([ds.n_steps])
    sc = M.score_steps(M.Prefix(ds, SJ, FASTJ, DEV), ks, FASTJ)
    V0 = rand_variants(1, 3, 9)
    if CUDA:
        dc = ds.to("cpu")
        scc = M.score_steps(M.Prefix(dc, SJ, FASTJ, "cpu"), ks.cpu(), FASTJ)
        assert torch.allclose(scc["pi"], sc["pi"].cpu(), atol=2e-5)
        Nc, Ng = MJ.cross_prefix(dc, dc.n_steps), MJ.cross_prefix(ds, ds.n_steps)
        assert torch.equal(Nc, Ng.cpu())
        jc, jg = MJ.joker_stage(Nc[None], V0 + 1), MJ.joker_stage(Ng[None], (V0 + 1).to(DEV))
        assert torch.equal(jc["q"], jg["q"].cpu()) and torch.equal(jc["jokers"], jg["jokers"].cpu())
    dss = [dsJ(tmp_path, n_rows=120, seed=s, name=f"u{s}.jsonl") for s in (7, 8, 9)]
    assert all(torch.equal(d.step_index, dss[0].step_index) for d in dss)
    assert int((dss[0].step_offsets[1:] - dss[0].step_offsets[:-1]).max()) > 1   # zile duble prezente
    draws = torch.stack([d.draws for d in dss])
    fs = M.final_state(draws, dss[0].step_index, dss[0].n_steps, SJ, FASTJ)
    for b, d in enumerate(dss):
        st = M.Prefix(d, SJ, FASTJ, DEV).state(torch.tensor([d.n_steps]))
        for key in st:
            assert torch.equal(st[key][0], fs[key][b]), key
    seeds = torch.tensor([11, 12, 13])
    allb = M.score_states(fs, seeds, SJ, FASTJ)
    for b in range(3):
        one = M.score_states({kk: vv[b:b + 1] for kk, vv in fs.items()}, seeds[b:b + 1], SJ, FASTJ)
        assert torch.allclose(one["pi"][0], allb["pi"][b], atol=1e-9, rtol=0)
    Nb = JE.joint_counts(draws - 1, torch.stack([d.joker for d in dss]) - 1)
    Vb = (rand_variants(3, 3, 10) + 1).to(DEV)
    jb = MJ.joker_stage(Nb, Vb)
    for b, d in enumerate(dss):
        assert torch.equal(Nb[b], MJ.cross_prefix(d, d.n_steps))
        j1 = MJ.joker_stage(Nb[b:b + 1], Vb[b:b + 1])
        assert torch.equal(j1["q"][0], jb["q"][b]) and torch.equal(j1["jokers"][0], jb["jokers"][b])


# ---------------- EJ10: QUBO exact-5 la n = 45 vs enumerare exhaustivă ----------------
def test_EJ10_energy_formula_and_exhaustive_minimum():
    g = torch.Generator().manual_seed(21)
    pi = torch.softmax(torch.randn(1, 45, generator=g, dtype=F64) * 0.6, -1)
    Mx = torch.randn(45, 45, generator=g, dtype=F64)
    A = ((Mx + Mx.T) / 2).fill_diagonal_(0)
    A = (A / torch.linalg.eigvalsh(A).abs().max())[None]
    logpi = torch.log(pi)
    ov = torch.zeros(1, 45, dtype=F64)
    ov[0, [3, 17]] = 1.0
    cfg = MJ.PROTOCOL_JOKER
    S = torch.stack([torch.randperm(45, generator=g)[:5] for _ in range(64)])[None]
    e = M.energy(S, logpi, A, ov, SJ, cfg)[0]
    for i in range(64):
        s = S[0, i].tolist()
        ref = -sum(float(logpi[0, j]) for j in s) - cfg.lam_pair * sum(float(A[0, a, b]) for a, b in combinations(s, 2))
        ref += cfg.mu_crowd * float(E.crowd_penalty(torch.tensor([[x + 1 for x in s]]))[0])
        ref += cfg.mu_overlap * sum(float(ov[0, j]) for j in s)
        assert abs(float(e[i]) - ref) < 1e-12
    lp, Ad, ovd = logpi.to(DEV), A.to(DEV), torch.zeros(1, 45, dtype=F64, device=DEV)
    best, be = M.mcmc_variant(lp, Ad, ovd, torch.tensor([5]), SJ, cfg)
    allc = torch.tensor(list(combinations(range(45), 5)), device=DEV)
    assert allc.shape[0] == math.comb(45, 5) == 1221759
    ea = torch.cat([M.energy(allc[None, s0:s0 + 131072], lp, Ad, ovd, SJ, cfg)[0]
                    for s0 in range(0, allc.shape[0], 131072)])
    emin = float(ea.min())
    arg = (allc[int(ea.argmin())] + 1).tolist()
    assert abs(float(be[0]) - emin) < 1e-9, (best.tolist(), arg)
    assert best[0].tolist() == arg


# ---------------- EJ11: integritate ----------------
def test_EJ11_integrity_hashes():
    seal = json.loads((HERE / "SIGILIU_TU3_EJ.json").read_text())
    assert sha(HERE / "PROTOCOL_TU3_EJ.md") == seal["sha256"]
    assert seal["code_files_present"] == [] and seal["results_present"] is False
    assert sha(QL / "engine.py") == seal["engine_sha256"] == "1da9be4e05bcefe401c299b6e6cd0ca7e4d6057939756057822cb43c951cb2ae"
    assert sha(QL / "parser.py") == seal["parser_sha256"] == "219e5d2085a72e960583830a6acd009e376f01079381ad0e09824fd200ee8968"
    assert sha(HERE / "parser_multi.py") == seal["parser_multi_sha256"] == "4c4b0f34cdac96e8b590649113d8db4331a1c6cdfa6169bb8b3017bdb92aef2a"
    assert sha(HERE / "motor_n.py") == seal["motor_n_sha256"] == "28e8eede1de49070da90291c3734c64a8389551167b0649f396e68bbd98add17"
    assert sha(HERE / "joker_entanglement.py") == seal["joker_entanglement_sha256"] == "52feb5b575f4c507289091b7504efbe480e49f810de109c3f05b0a8d5b99933e"
    assert sha(HERE / "PROTOCOL_TU3_P1.md") == seal["parent_protocol_sha256"]
    assert sha(HERE / "PROTOCOL_TU3_E40.md") == seal["e40_protocol_sha256"]


# ---------------- EJ12: fumul produsului pe LIVE (numai după EJ_PASS) ----------------
@pytest.mark.skipif(MJ.power_verdict() != "EJ_PASS", reason="EJ12 cere verdictul EJ_PASS al verificării de putere (§4)")
def test_EJ12_live_product_smoke():
    ds = PM.build_game_dataset("joker", "live", device=DEV)
    out = MJ.run_full_joker(ds)
    assert out["is_protocol"] is True and out["source_kind"] == "live" and out["positive_claims_allowed"] is False
    assert out["game"] == "joker" and out["dataset_game"] == "joker" and out["n_steps"] == ds.n_steps
    assert out["protocol_sha256"] == json.loads((HERE / "SIGILIU_TU3_EJ.json").read_text())["sha256"]
    assert torch.equal(out["cross_counts"], ds.cross_counts.to(F64))
    pi, A = out["pi"], out["A"]
    assert pi.shape == (45,) and abs(float(pi.sum()) - 1) < 1e-12 and torch.equal(A, A.T)
    V = out["variants_5plus1"]
    assert len(V) == 3 and len({tuple(v) for v, _ in V}) == 3
    for v, a in V:
        assert len(v) == 5 and len(set(v)) == 5 and v == sorted(v) and all(1 <= x <= 45 for x in v)
        assert 1 <= a <= 20
    assert all(e < 1e5 for e in out["energies_main"])
    assert out["q_joker"].shape == (3, 20)
