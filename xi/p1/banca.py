#!/usr/bin/env python3
"""XI-P1 — banca de predictoare (planul V12, faza P1).

Implementează EXACT `xi/PROTOCOL_XI_P1.md` (731b6839…) cu `xi/AMENDAMENT_XI_P1_01.md` (661fbf75…).
Subcomenzi:
  teste      calificarea Q1–Q4 pe date SINTETICE (nu citește baza reală)
  productie  rularea unică pe arhiva RO (cod sigilat, sha-uri verificate; refuză repetarea)
Calcul clasic float64 pe CPU. positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
import math
import os
import sqlite3
import sys
import time
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
XI = HERE.parent
OUT = XI / "rezultate" / "P1"
CAL = OUT / "calificare"
DB = Path("${LOTO_RO_ROOT:-.}/loto_romania/data/snapshots/"
          "c6bfd021af15d9d6ece6b20d106550e4c8474049e38e9caa3bd1c99d19766adb/loto_romania.sqlite")
DB_SHA = "9942abfc25282a715cba70e4f6d17a885a467eaf5fe0440838dc28114003c078"
PROTOCOL_SHA = "731b6839ecd0d65df003c11466c568e812ddd24e7b7ada6079f921c02407cdd0"
AMEND_SHA = "661fbf75b28caf51116dc5dd232567f42697058ab72b3a74e74c13a14211a6a1"
SEED = 20261031
ALPHA = 0.01
E_THR = 1500.0

# subjocuri: (eticheta, n, k)
GAMES = {"649": [("649", 49, 6)], "540": [("540", 40, 6)], "joker": [("princ", 45, 5), ("bila", 20, 1)]}
T_EXPECTED = {"649": 2384, "540": 2341, "joker": 2203}

STAT_M = (100, 400, 1600, 6400)
DRIFT_H = (25, 100, 400)
DRIFT_R = (1, 4)
GAP_G = (-0.3, -0.1, 0.1, 0.3)
FERMI_M = (200, 800, 3200)
FAMILIES = ("STAT", "DRIFT", "GAP", "FERMI")
PREDICTORS = ("STAT", "DRIFT", "GAP", "FERMI", "COMB")


# ---------------------------------------------------------------- componente
def components(k: int) -> list[tuple[str, object]]:
    comp = [("U", None)]
    comp += [("STAT", m) for m in STAT_M]
    comp += [("DRIFT", (h, r)) for h in DRIFT_H for r in DRIFT_R]
    comp += [("GAP", g) for g in GAP_G]
    if k >= 2:
        comp += [("FERMI", m) for m in FERMI_M]
    return comp


def priors(pred: str, k: int, qualified=FAMILIES) -> np.ndarray:
    """Ponderile a priori ρ_j pe componentele `components(k)` (protocol §3, amendament §2)."""
    comp = components(k)
    rho = np.zeros(len(comp))
    rho[0] = 0.5
    if pred == "COMB":
        fams = [f for f in FAMILIES if f in qualified and (f != "FERMI" or k >= 2)]
    else:
        fams = [pred] if (pred in qualified and (pred != "FERMI" or k >= 2)) else []
    if not fams:
        rho[0] = 1.0
        return rho
    for f in fams:
        idx = [j for j, (fam, _) in enumerate(comp) if fam == f]
        for j in idx:
            rho[j] = 0.5 / len(fams) / len(idx)
    return rho


def esp(w: np.ndarray, k: int) -> np.ndarray:
    """e_0..e_k(w) prin recurența DP (fără scăderi)."""
    e = np.zeros(k + 1)
    e[0] = 1.0
    for x in w:
        e[1:] += x * e[:-1]
    return e


def esp_minus(w: np.ndarray, k: int) -> np.ndarray:
    """E[i, r] = e_r(w fără i), r = 0..k-1 (DP direct, fără scăderi)."""
    n = len(w)
    E = np.zeros((n, k))
    E[:, 0] = 1.0
    for l in range(n):
        f = np.full(n, w[l])
        f[l] = 0.0
        if k > 1:
            E[:, 1:] += f[:, None] * E[:, :-1]
    return E


def cb_eval(w: np.ndarray, k: int, S, need_marg: bool):
    w = w / w.mean()
    e = esp(w, k)
    lp = float(np.log(w[S]).sum() - math.log(e[k])) if S is not None else None
    marg = None
    if need_marg:
        marg = w * esp_minus(w, k)[:, k - 1] / e[k]
    return lp, marg


def fermi_L(c, C, Tp, m, n, k):
    p, q = k / n, k * (k - 1) / (n * (n - 1))
    pi = (c + m * p) / (Tp + m)
    pij = (C + m * q) / (Tp + m)
    phi = np.log(pij / q) - np.log(pi / p)[:, None] - np.log(pi / p)[None, :]
    A = np.sqrt(np.maximum(-phi, 0.0))
    np.fill_diagonal(A, 0.0)
    M = np.eye(n) + A
    mu, U = np.linalg.eigh(M)
    mu = np.maximum(mu, 1e-6)
    return mu, U


def fermi_eval(mu, U, k, S, need_marg):
    e = esp(mu, k)
    lp = None
    if S is not None:
        US = U[S]
        sign, ld = np.linalg.slogdet((US * mu) @ US.T)
        assert sign > 0
        lp = float(ld - math.log(e[k]))
    marg = None
    if need_marg:
        Em = esp_minus(mu, k)[:, k - 1]
        marg = (U ** 2) @ (mu * Em) / e[k]
    return lp, marg


def run_components(draws: list, n: int, k: int, need_marg=False, extra_step=False):
    """Log-probabilitățile tuturor componentelor pentru fiecare extragere („ca în ajun”).

    draws: listă de array-uri de indici 0-bazați. Returnează (LP[T, J], MARG[T(+1), J, n] sau None).
    Dacă extra_step: încă un pas (predicția pentru extragerea următoare, fără scor).
    """
    comp = components(k)
    J, T = len(comp), len(draws)
    p = k / n
    logU = -math.log(math.comb(n, k))
    LP = np.zeros((T, J))
    steps = T + (1 if extra_step else 0)
    MARG = np.zeros((steps, J, n)) if need_marg else None
    c = np.zeros(n)
    C = np.zeros((n, n))
    lam = {h: 2.0 ** (-1.0 / h) for h in DRIFT_H}
    cH = {h: np.zeros(n) for h in DRIFT_H}
    TH = {h: 0.0 for h in DRIFT_H}
    last = np.zeros(n)
    for t in range(1, steps + 1):
        S = draws[t - 1] if t <= T else None
        Tp = t - 1
        row = np.zeros(J)
        for j, (fam, par) in enumerate(comp):
            if fam == "U":
                lp, mg = (logU if S is not None else None), (np.full(n, p) if need_marg else None)
            elif fam == "STAT":
                f = (c + par * p) / (Tp + par)
                lp, mg = cb_eval(f / (1 - f), k, S, need_marg)
            elif fam == "DRIFT":
                h, r = par
                mm = r * h
                f = (cH[h] + mm * p) / (TH[h] + mm)
                lp, mg = cb_eval(f / (1 - f), k, S, need_marg)
            elif fam == "GAP":
                g = (t - 1) - last
                x = np.minimum(g * p / (1 - p), 5.0) - 1.0
                lp, mg = cb_eval(np.exp(par * x), k, S, need_marg)
            else:  # FERMI
                mu, U = fermi_L(c, C, Tp, par, n, k)
                lp, mg = fermi_eval(mu, U, k, S, need_marg)
            if S is not None:
                row[j] = lp
            if need_marg:
                MARG[t - 1, j] = mg
        if S is None:
            break
        LP[t - 1] = row
        c[S] += 1
        C[np.ix_(S, S)] += 1
        for h in DRIFT_H:
            cH[h] *= lam[h]
            cH[h][S] += 1.0
            TH[h] = lam[h] * TH[h] + 1.0
        last[S] = t
    return LP, MARG


def lse(a: np.ndarray, axis=None):
    m = np.max(a, axis=axis, keepdims=True)
    r = m + np.log(np.sum(np.exp(a - m), axis=axis, keepdims=True))
    return np.squeeze(r, axis=axis) if axis is not None else float(r.reshape(-1)[0])


def logE_closed(LP: np.ndarray, rho: np.ndarray, n: int, k: int) -> float:
    """Telescopare: log Σ_j ρ_j exp(Σ_t [log P_j(S_t) − log P_U])."""
    logU = -math.log(math.comb(n, k))
    tot = (LP - logU).sum(axis=0)
    mask = rho > 0
    return lse(np.log(rho[mask]) + tot[mask])


def mixture_seq(LP: np.ndarray, rho: np.ndarray, n: int, k: int, MARG=None):
    """Predictorul secvențial: log P_X(S_t), log E cumulat, marginalele mixturii (dacă MARG)."""
    logU = -math.log(math.comb(n, k))
    mask = rho > 0
    lr = np.log(rho[mask])
    L = LP[:, mask]
    T = L.shape[0]
    cum = np.vstack([np.zeros((1, L.shape[1])), np.cumsum(L, axis=0)])  # cum[t] = Σ_{s<t+1}
    logw = lr[None, :] + cum  # logw[t] = ponderile înaintea extragerii t+1 (0-bazat)
    lpx = lse(logw[:T] + L, axis=1) - lse(logw[:T], axis=1)
    marg = None
    if MARG is not None:
        W = np.exp(logw - lse(logw, axis=1)[:, None])
        steps = MARG.shape[0]
        marg = np.einsum("tj,tjn->tn", W[:steps], MARG[:, mask, :])
    return lpx, lpx - logU, marg


def ticket(marg: np.ndarray, k: int) -> list[int]:
    r = np.round(marg, 12)
    order = np.lexsort((np.arange(len(r)), -r))
    return sorted(int(i) for i in order[:k])


# ---------------------------------------------------------------- eșantionare sintetică
def cb_sampler_table(w, k):
    n = len(w)
    Es = np.zeros((n + 1, k + 1))
    Es[n, 0] = 1.0
    for i in range(n - 1, -1, -1):
        Es[i] = Es[i + 1]
        Es[i, 1:] += w[i] * Es[i + 1, :-1]
    return Es


def cb_sample(w, k, rng, Es=None):
    w = np.asarray(w, float)
    if Es is None:
        Es = cb_sampler_table(w, k)
    S, r = [], k
    for i in range(len(w)):
        if r == 0:
            break
        if rng.random() < w[i] * Es[i + 1, r - 1] / Es[i, r]:
            S.append(i)
            r -= 1
    return np.array(S, dtype=np.int64)


def blocks_of(n, b=7):
    return [list(range(s, min(s + b, n))) for s in range(0, n, b)]


def block_occupancies(sizes, k):
    out = []

    def rec(i, rem, cur):
        if i == len(sizes):
            if rem == 0:
                out.append(tuple(cur))
            return
        for m in range(0, min(sizes[i], rem) + 1):
            rec(i + 1, rem - m, cur + [m])
    rec(0, k, [])
    return out


def block_law(n, k, s, b=7):
    bl = blocks_of(n, b)
    sizes = [len(x) for x in bl]
    occ = block_occupancies(sizes, k)
    cnt = np.array([math.prod(math.comb(sz, m) for sz, m in zip(sizes, o)) for o in occ], float)
    wt = np.array([math.prod(1 + s * m for m in o) for o in occ], float)
    Z = float((cnt * wt).sum())
    return bl, occ, cnt, wt, Z


def kl_block(n, k, s, b=7):
    bl, occ, cnt, wt, Z = block_law(n, k, s, b)
    P = wt / Z
    return float((cnt * P * np.log(P * math.comb(n, k))).sum())


def block_sample(law, rng):
    bl, occ, cnt, wt, Z = law
    pr = cnt * wt / Z
    o = occ[rng.choice(len(occ), p=pr)]
    S = []
    for blk, m in zip(bl, o):
        if m:
            S += list(rng.choice(blk, m, replace=False))
    return np.array(sorted(S), dtype=np.int64)


def gen_history(kind: str, n: int, k: int, T: int, seed: int, param=None):
    rng = np.random.Generator(np.random.PCG64(seed))
    H = []
    if kind == "uniform":
        for _ in range(T):
            H.append(np.sort(rng.choice(n, k, replace=False)))
    elif kind == "stat":  # cote (1+δ) pentru i < n/2 (i ≤ 24 la 6/49), 1/(1+δ) altfel
        d = param
        w = np.where(np.arange(n) < 24, 1 + d, 1 / (1 + d))
        Es = cb_sampler_table(w, k)
        for _ in range(T):
            H.append(cb_sample(w, k, rng, Es))
    elif kind == "drift":
        for t0 in range(0, T, 150):
            hi = rng.choice(n, 24, replace=False)
            w = np.full(n, 1 / 1.5)
            w[hi] = 1.5
            Es = cb_sampler_table(w, k)
            for _ in range(min(150, T - t0)):
                H.append(cb_sample(w, k, rng, Es))
    elif kind == "gap":
        p = k / n
        last = np.zeros(n)
        for t in range(1, T + 1):
            g = (t - 1) - last
            x = np.minimum(g * p / (1 - p), 5.0) - 1.0
            S = cb_sample(np.exp(0.6 * x), k, rng)
            H.append(S)
            last[S] = t
    elif kind == "fermi":
        law = block_law(n, k, param)
        for _ in range(T):
            H.append(block_sample(law, rng))
    else:
        raise ValueError(kind)
    return H


def fermi_strength(n=49, k=6):
    for s in (0.5, 1, 2, 4, 8, 16):
        if kl_block(n, k, s) >= 0.05:
            return s
    raise RuntimeError("niciun s din grilă nu atinge KL ≥ 0.05")


# ---------------------------------------------------------------- statistică auxiliară
def gammaincc(a, x):
    if x <= 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1:
        ap, s = a, 1.0 / a
        term = s
        for _ in range(100000):
            ap += 1
            term *= x / ap
            s += term
            if abs(term) < abs(s) * 1e-16:
                break
        return max(0.0, 1.0 - s * math.exp(-x + a * math.log(x) - gln))
    FP = 1e-300
    b = x + 1 - a
    c = 1 / FP
    d = 1 / b
    h = d
    for i in range(1, 100000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = FP if abs(d) < FP else d
        c = b + an / c
        c = FP if abs(c) < FP else c
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-16:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def chi2_sf(x, dof):
    return gammaincc(dof / 2.0, x / 2.0)


def hyper_pmf(n, k):
    """Nimeriri ale unui bilet de k numere cu k extrase din n."""
    tot = math.comb(n, k)
    return np.array([math.comb(k, h) * math.comb(n - k, k - h) / tot for h in range(k + 1)])


def conv_power(pmf, T):
    out = np.array([1.0])
    base = pmf.copy()
    e = T
    while e:
        if e & 1:
            out = np.convolve(out, base)
        base = np.convolve(base, base)
        e >>= 1
    return out


def binom_sf(x, T, p):
    """P(X ≥ x), X ~ Bin(T, p), în spațiul logaritmic."""
    if x <= 0:
        return 1.0
    ks = np.arange(x, T + 1)
    lg = (np.array([math.lgamma(T + 1) - math.lgamma(kk + 1) - math.lgamma(T - kk + 1) for kk in ks])
          + ks * math.log(p) + (T - ks) * math.log1p(-p))
    return float(np.exp(lse(lg)))


def holm(pvals: dict, alpha=ALPHA):
    items = sorted(pvals.items(), key=lambda kv: (kv[1], kv[0]))
    M = len(items)
    rej = {key: False for key in pvals}
    for i, (key, pv) in enumerate(items):
        if pv <= alpha / (M - i):
            rej[key] = True
        else:
            break
    return rej


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def utcnow():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------- calificare
def _hist_task(spec):
    """Evaluează o istorie sintetică; întoarce log E pentru toți predictorii (telescopare)."""
    game, kind, param, seed, qualified = spec
    res = {}
    for i, (lab, n, k) in enumerate(GAMES[game]):
        T = T_EXPECTED[game] if kind == "uniform" else 2384
        H = gen_history(kind, n, k, T, seed + 7919 * i, param)
        LP, _ = run_components(H, n, k)
        for X in PREDICTORS:
            res.setdefault(X, 0.0)
            res[X] += logE_closed(LP, priors(X, k, qualified), n, k)
        res.setdefault("_min_sub", []).append(min(logE_closed(LP, priors(X, k, qualified), n, k)
                                                  for X in PREDICTORS))
    return spec, res


def q1(results):
    rng = np.random.Generator(np.random.PCG64(SEED + 1))
    out = {}
    # (a) CB exact în Fraction, n=10, k=3
    n, k = 10, 3
    wq = [Fraction(int(rng.integers(1, 50)), int(rng.integers(1, 50))) for _ in range(n)]
    Z = sum(math.prod(wq[i] for i in S) for S in itertools.combinations(range(n), k))
    w = np.array([float(x) for x in wq])
    err = 0.0
    for S in itertools.combinations(range(n), k):
        ex = math.prod(wq[i] for i in S) / Z
        lp, _ = cb_eval(w, k, list(S), False)
        err = max(err, abs(math.exp(lp) / float(ex) - 1))
    out["a_cb_fraction_n10k3_relerr"] = err
    ok_a1 = err <= 1e-12
    n, k = 12, 4
    w = rng.uniform(0.2, 3.0, n)
    _, mg = cb_eval(w, k, None, True)
    ex = np.zeros(n)
    Zf = 0.0
    for S in itertools.combinations(range(n), k):
        v = float(np.prod(w[list(S)]))
        Zf += v
        ex[list(S)] += v
    ex /= Zf
    out["a_cb_marg_n12k4_relerr"] = float(np.max(np.abs(mg / ex - 1)))
    ok_a2 = out["a_cb_marg_n12k4_relerr"] <= 1e-12
    n, k = 49, 6
    w = rng.uniform(0.5, 2.0, n)
    wn = w / w.mean()
    lz = math.log(esp(wn, k)[k])
    tot = 0.0
    combs = np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(n), k)),
                        dtype=np.int8, count=math.comb(n, k) * k).reshape(-1, k)
    lw = np.log(wn)
    for a in range(0, len(combs), 2_000_000):
        tot += float(np.exp(lw[combs[a:a + 2_000_000]].sum(axis=1) - lz).sum())
    del combs
    out["a_cb_sum_n49k6"] = tot
    ok_a3 = abs(tot - 1) <= 1e-9
    # (b) k-DPP (construcția din amendament), n=12, k=4
    n, k = 12, 4
    phi = rng.uniform(-1, 1, (n, n))
    phi = (phi + phi.T) / 2
    A = np.sqrt(np.maximum(-phi, 0))
    np.fill_diagonal(A, 0)
    mu, U = np.linalg.eigh(np.eye(n) + A)
    mu = np.maximum(mu, 1e-6)
    L = (U * mu) @ U.T
    Zd, mex = 0.0, np.zeros(n)
    for S in itertools.combinations(range(n), k):
        d = np.linalg.det(L[np.ix_(S, S)])
        Zd += d
        mex[list(S)] += d
    mex /= Zd
    ek = esp(mu, k)[k]
    _, mg = fermi_eval(mu, U, k, None, True)
    out["b_dpp_norm_n12k4_relerr"] = abs(Zd / ek - 1)
    out["b_dpp_marg_n12k4_relerr"] = float(np.max(np.abs(mg / mex - 1)))
    ok_b1 = out["b_dpp_norm_n12k4_relerr"] <= 1e-10 and out["b_dpp_marg_n12k4_relerr"] <= 1e-10
    n, k = 40, 6
    H = gen_history("uniform", n, k, 300, SEED + 2)
    c = np.zeros(n)
    C = np.zeros((n, n))
    for S in H:
        c[S] += 1
        C[np.ix_(S, S)] += 1
    mu, U = fermi_L(c, C, 300, 200, n, k)
    L = (U * mu) @ U.T
    lz = math.log(esp(mu, k)[k])
    combs = np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(n), k)),
                        dtype=np.int8, count=math.comb(n, k) * k).reshape(-1, k)
    tot = 0.0
    for a in range(0, len(combs), 250_000):
        cb = combs[a:a + 250_000].astype(np.int64)
        sub = L[cb[:, :, None], cb[:, None, :]]
        tot += float(np.exp(np.linalg.slogdet(sub)[1] - lz).sum())
    del combs
    out["b_dpp_sum_n40k6"] = tot
    ok_b2 = abs(tot - 1) <= 1e-8
    # (c) limita uniformă la t = 1
    worst = 0.0
    for game, subs in GAMES.items():
        for lab, n, k in subs:
            S = np.sort(rng.choice(n, k, replace=False))
            LP, MG = run_components([S], n, k, need_marg=True)
            worst = max(worst, float(np.max(np.abs(LP[0] + math.log(math.comb(n, k))))))
            worst = max(worst, float(np.max(np.abs(MG[0] / (k / n) - 1))))
    out["c_uniform_limit_maxabs"] = worst
    ok_c = worst <= 1e-12
    # (d) telescopare pe o istorie sintetică 6/49
    H = gen_history("uniform", 49, 6, 600, SEED + 3)
    LP, _ = run_components(H, 49, 6)
    dmax = 0.0
    for X in PREDICTORS:
        rho = priors(X, 6)
        _, lr, _ = mixture_seq(LP, rho, 49, 6)
        dmax = max(dmax, abs(float(lr.sum()) - logE_closed(LP, rho, 49, 6)))
    out["d_telescoping_maxabs"] = dmax
    ok_d = dmax <= 1e-9
    # (f) DPP pe blocuri: forma închisă vs det; eșantionatoare χ²
    n, k, s = 14, 4, 2.0
    bl = blocks_of(n)
    B = np.zeros((n, n))
    for blk in bl:
        B[np.ix_(blk, blk)] = 1
    L = np.eye(n) + s * B
    subsets = list(itertools.combinations(range(n), k))
    dets = np.array([np.linalg.det(L[np.ix_(S, S)]) for S in subsets])
    closed = np.array([math.prod(1 + s * sum(1 for i in S if i in blk) for blk in bl) for S in subsets])
    out["f_block_closed_vs_det_relerr"] = float(np.max(np.abs(closed / dets - 1)))
    law = block_law(n, k, s)
    rs = np.random.Generator(np.random.PCG64(SEED + 4))
    idx = {S: i for i, S in enumerate(subsets)}
    cnt = np.zeros(len(subsets))
    for _ in range(200_000):
        cnt[idx[tuple(int(x) for x in block_sample(law, rs))]] += 1
    expct = 200_000 * dets / dets.sum()
    x2 = float(((cnt - expct) ** 2 / expct).sum())
    out["f_block_sampler_chi2"] = x2
    out["f_block_sampler_p"] = chi2_sf(x2, len(subsets) - 1)
    n, k = 8, 3
    w = np.array([0.5, 1.0, 1.5, 2.0, 0.7, 1.2, 3.0, 0.9])
    subsets = list(itertools.combinations(range(n), k))
    idx = {S: i for i, S in enumerate(subsets)}
    pr = np.array([np.prod(w[list(S)]) for S in subsets])
    pr /= pr.sum()
    Es = cb_sampler_table(w, k)
    rs = np.random.Generator(np.random.PCG64(SEED + 5))
    cnt = np.zeros(len(subsets))
    for _ in range(200_000):
        cnt[idx[tuple(int(x) for x in cb_sample(w, k, rs, Es))]] += 1
    expct = 200_000 * pr
    x2 = float(((cnt - expct) ** 2 / expct).sum())
    out["g_cb_sampler_chi2"] = x2
    out["g_cb_sampler_p"] = chi2_sf(x2, len(subsets) - 1)
    out["chi2_sanity_3.841_1dof"] = chi2_sf(3.841458820694124, 1)
    ok_f = (out["f_block_closed_vs_det_relerr"] <= 1e-12 and out["f_block_sampler_p"] > 0.001
            and out["g_cb_sampler_p"] > 0.001 and abs(out["chi2_sanity_3.841_1dof"] - 0.05) < 1e-9)
    out["PASS"] = bool(ok_a1 and ok_a2 and ok_a3 and ok_b1 and ok_b2 and ok_c and ok_d and ok_f)
    out["parts"] = {"a1": ok_a1, "a2": ok_a2, "a3": ok_a3, "b1": ok_b1, "b2": ok_b2, "c": ok_c,
                    "d": ok_d, "f_g": ok_f}
    results["Q1"] = out


def q2(results):
    H = gen_history("uniform", 49, 6, 2384, SEED + 100)
    LP0, MG0 = run_components(H, 49, 6, need_marg=True)
    out = {"cuts": {}}
    ok = True
    for i, t0 in enumerate((500, 1200, 2000)):
        H2 = list(H[:t0 - 1]) + gen_history("uniform", 49, 6, 2384 - t0 + 1, SEED + 101 + i)
        LP1, MG1 = run_components(H2, 49, 6, need_marg=True)
        same_lp = bool(np.array_equal(LP0[:t0 - 1], LP1[:t0 - 1]))
        same_mg = bool(np.array_equal(MG0[:t0], MG1[:t0]))
        tick = True
        for X in PREDICTORS:
            rho = priors(X, 6)
            _, _, m0 = mixture_seq(LP0, rho, 49, 6, MG0)
            _, _, m1 = mixture_seq(LP1, rho, 49, 6, MG1)
            tick &= all(ticket(m0[t], 6) == ticket(m1[t], 6) for t in range(t0))
        out["cuts"][str(t0)] = {"logp_t_lt_t0_identical": same_lp, "marg_t_le_t0_identical": same_mg,
                                "tickets_t_le_t0_identical": bool(tick)}
        ok &= same_lp and same_mg and tick
    out["PASS"] = bool(ok)
    results["Q2"] = out


def q3q4(results, procs=24):
    specs = []
    for gi, game in enumerate(GAMES):
        for r in range(100):
            specs.append((game, "uniform", None, SEED + 1000 + 1000 * gi + r, FAMILIES))
    s_f = fermi_strength()
    sig = {"stat": 0.25, "drift": None, "gap": None, "fermi": s_f}
    for si, (kind, par) in enumerate(sig.items()):
        for r in range(20):
            specs.append(("649", kind, par, SEED + 10000 + 100 * si + r, FAMILIES))
    for di, d in enumerate((0.03, 0.05, 0.10, 0.15)):
        for r in range(20):
            specs.append(("649", "stat", d, SEED + 20000 + 100 * di + r, FAMILIES))
    t0 = time.time()
    with Pool(procs) as pool:
        outs = pool.map(_hist_task, specs, chunksize=1)
    q3 = {}
    minsub = min(min(res["_min_sub"]) for _, res in outs)
    for game in GAMES:
        rows = [res for (g, kind, _, _, _), res in outs if g == game and kind == "uniform"]
        q3[game] = {}
        for X in PREDICTORS:
            v = np.array([r[X] for r in rows])
            q3[game][X] = {"frac_E_ge_20": float(np.mean(v >= math.log(20))),
                           "frac_E_ge_1500": float(np.mean(v >= math.log(E_THR))),
                           "q05_q50_q95_max": [float(np.quantile(v, 0.05)), float(np.median(v)),
                                               float(np.quantile(v, 0.95)), float(v.max())]}
    ok3 = all(q3[g][X]["frac_E_ge_20"] <= 0.10 for g in GAMES for X in PREDICTORS)
    results["Q3"] = {"null_histories_per_game": 100, "per_game": q3, "PASS": bool(ok3)}
    results["Q1"]["e_min_sub_logE"] = minsub
    results["Q1"]["e_PASS"] = bool(minsub >= -math.log(2) - 1e-12)
    results["Q1"]["PASS"] = bool(results["Q1"]["PASS"] and results["Q1"]["e_PASS"])
    mat = {}
    for kind in sig:
        rows = [res for (g, kd, par, _, _), res in outs if kd == kind and g == "649"
                and (kind != "stat" or par == 0.25)]
        mat[kind] = {X: {"median_logE": float(np.median([r[X] for r in rows])),
                         "n_E_ge_1500": int(sum(r[X] >= math.log(E_THR) for r in rows)),
                         "n": len(rows)} for X in PREDICTORS}
    own = {"STAT": "stat", "DRIFT": "drift", "GAP": "gap", "FERMI": "fermi"}
    qual = [f for f in FAMILIES if mat[own[f]][f]["n_E_ge_1500"] >= 16]
    comb_ok = mat["stat"]["COMB"]["n_E_ge_1500"] >= 16
    power = {}
    for d in (0.03, 0.05, 0.10, 0.15):
        rows = [res for (g, kd, par, _, _), res in outs if kd == "stat" and par == d]
        power[str(d)] = {"frac_STAT_E_ge_1500": float(np.mean([r["STAT"] >= math.log(E_THR) for r in rows])),
                         "median_logE_STAT": float(np.median([r["STAT"] for r in rows])),
                         "frac_COMB_E_ge_1500": float(np.mean([r["COMB"] >= math.log(E_THR) for r in rows])),
                         "n": len(rows)}
    res_d = [d for d in (0.03, 0.05, 0.10, 0.15) if power[str(d)]["frac_STAT_E_ge_1500"] >= 0.8]
    results["Q4"] = {"fermi_s": s_f, "fermi_KL_nats_per_draw": kl_block(49, 6, s_f),
                     "matrix_predictor_x_signal": mat, "qualified_families": qual, "COMB_qualified": bool(comb_ok),
                     "power_STAT": power, "rezolutie_delta_min_putere_0_8": (res_d[0] if res_d else None),
                     "note": "familiile necalificate sunt excluse din productie si din COMB (protocol §5 Q4)"}
    results["Q3Q4_seconds"] = time.time() - t0


def cmd_teste():
    CAL.mkdir(parents=True, exist_ok=True)
    utc = utcnow()
    results = {"utc": utc, "code_sha256": sha_file(Path(__file__)), "protocol_sha256": PROTOCOL_SHA,
               "amendament_sha256": AMEND_SHA, "numpy": np.__version__, "seed": SEED,
               "baza_reala_citita": False}
    t0 = time.time()
    q1(results)
    print("Q1", results["Q1"]["PASS"], json.dumps(results["Q1"]["parts"]), flush=True)
    q2(results)
    print("Q2", results["Q2"]["PASS"], flush=True)
    q3q4(results)
    print("Q3", results["Q3"]["PASS"], "Q4 calificate", results["Q4"]["qualified_families"],
          "COMB", results["Q4"]["COMB_qualified"], flush=True)
    results["seconds"] = time.time() - t0
    results["PASS_Q1_Q3"] = bool(results["Q1"]["PASS"] and results["Q2"]["PASS"] and results["Q3"]["PASS"])
    results["positive_claims_allowed"] = False
    path = CAL / f"CALIFICARE_P1_{utc}.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    os.chmod(path, 0o444)
    print(path, sha_file(path))
    return 0 if results["PASS_Q1_Q3"] else 1


# ---------------------------------------------------------------- productie
def load_real():
    assert sha_file(DB) == DB_SHA, "sha baza"
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    data = {}
    for game in GAMES:
        rows = con.execute(
            "select draw_key, draw_date, draw_kind, n1, n2, n3, n4, n5, n6, joker, has_source_disagreement "
            "from draws where game=? and draw_kind in ('regular','special') "
            "order by draw_date, case draw_kind when 'regular' then 0 else 1 end, draw_key", (game,)).fetchall()
        assert len(rows) == T_EXPECTED[game], (game, len(rows))
        recs = []
        for key, date, kind, *nums, jk, dis in rows:
            if game == "joker":
                main = nums[:5]
                assert nums[5] is None and len(set(main)) == 5 and all(1 <= x <= 45 for x in main)
                assert jk is not None and 1 <= jk <= 20
                sets = [np.array(sorted(x - 1 for x in main)), np.array([jk - 1])]
            else:
                nn = 49 if game == "649" else 40
                assert len(set(nums)) == 6 and all(1 <= x <= nn for x in nums) and jk is None
                sets = [np.array(sorted(x - 1 for x in nums))]
            recs.append({"key": key, "date": date, "kind": kind, "dis": int(dis), "sets": sets})
        data[game] = recs
    con.close()
    return data


def cmd_productie():
    seal_p = HERE / "SIGILIU_COD_P1.json"
    assert seal_p.exists(), "codul nu este sigilat"
    seal = json.loads(seal_p.read_text())
    assert seal["files"]["xi/p1/banca.py"] == sha_file(Path(__file__)), "sha cod"
    assert sha_file(XI / "PROTOCOL_XI_P1.md") == PROTOCOL_SHA
    assert sha_file(XI / "AMENDAMENT_XI_P1_01.md") == AMEND_SHA
    qualified = tuple(seal["qualified_families"])
    comb_ok = bool(seal["COMB_qualified"])
    preds = [X for X in PREDICTORS if (X in qualified) or (X == "COMB" and comb_ok)]
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ("p1_pas.jsonl", "P1_REZULTATE.json", "RAPORT_P1_CIFRE.md"):
        if (OUT / f).exists():
            print("REFUZ: productia P1 a fost deja facuta:", OUT / f)
            return 2
    utc = utcnow()
    t_start = time.time()
    data = load_real()
    res = {"utc": utc, "db_sha256": DB_SHA, "code_sha256": sha_file(Path(__file__)),
           "protocol_sha256": PROTOCOL_SHA, "amendament_sha256": AMEND_SHA,
           "qualified_families": list(qualified), "COMB_qualified": comb_ok, "predictori": preds,
           "alpha": ALPHA, "games": {}}
    pas = open(OUT / "p1_pas.jsonl", "w")
    pvals = {}
    for game, subs in GAMES.items():
        recs = data[game]
        T = len(recs)
        g = {"T": T, "first": recs[0]["date"], "last": recs[-1]["date"],
             "n_source_disagreement": int(sum(r["dis"] for r in recs)),
             "n_special": int(sum(r["kind"] == "special" for r in recs)), "sub": {}, "pred": {}}
        i2010 = next(i for i, r in enumerate(recs) if r["date"] >= "2010-01-01")
        half = T // 2
        per_sub = {}
        for si, (lab, n, k) in enumerate(subs):
            H = [r["sets"][si] for r in recs]
            LP, MG = run_components(H, n, k, need_marg=True, extra_step=True)
            comp = components(k)
            per_sub[lab] = {"n": n, "k": k, "LP": LP, "MG": MG, "H": H, "comp": comp}
            g["sub"][lab] = {"n": n, "k": k, "componente": [f"{f}:{p}" for f, p in comp],
                             "logE_componente": [float(x) for x in
                                                 (LP + math.log(math.comb(n, k))).sum(axis=0)]}
        rows = [{"joc": game, "t": t + 1, "date": recs[t]["date"], "key": recs[t]["key"],
                 "S": {lab: [int(x) + 1 for x in per_sub[lab]["H"][t]] for lab in per_sub},
                 "logp_comp": {lab: [round(float(x), 12) for x in per_sub[lab]["LP"][t]] for lab in per_sub},
                 "logp_pred": {}, "bilet": {}, "hits": {}} for t in range(T)]
        for X in preds:
            tot_lr = np.zeros(T)
            pr = {"sub": {}}
            for lab, d in per_sub.items():
                n, k = d["n"], d["k"]
                rho = priors(X, k, qualified)
                lpx, lr, marg = mixture_seq(d["LP"], rho, n, k, d["MG"])
                tot_lr += lr
                tk = [ticket(marg[t], k) for t in range(T + 1)]
                hits = np.array([len(set(tk[t]) & set(int(x) for x in d["H"][t])) for t in range(T)])
                for t in range(T):
                    rows[t]["logp_pred"].setdefault(X, {})[lab] = round(float(lpx[t]), 12)
                    rows[t]["bilet"].setdefault(X, {})[lab] = [x + 1 for x in tk[t]]
                    rows[t]["hits"].setdefault(X, {})[lab] = int(hits[t])
                pmf = hyper_pmf(n, k)
                dist = conv_power(pmf, T)
                hsum = int(hits.sum())
                p3 = float(pmf[3:].sum()) if k >= 3 else None
                n3 = int((hits >= 3).sum()) if k >= 3 else None
                mask = rho > 0
                cum = np.log(rho[mask]) + (d["LP"][:, mask] + math.log(math.comb(n, k))).sum(axis=0)
                wfin = np.exp(cum - lse(cum))
                names = [f"{f}:{p}" for (f, p), m_ in zip(d["comp"], mask) if m_]
                pr["sub"][lab] = {
                    "logE": float(lr.sum()), "hits_sum": hsum, "hits_mean": hsum / T,
                    "hits_null_mean": T * k * k / n, "hits_p_one_sided": float(dist[hsum:].sum()),
                    "n_hits_ge_3": n3, "n_hits_ge_3_null_mean": (T * p3 if p3 is not None else None),
                    "n_hits_ge_3_p_one_sided": (binom_sf(n3, T, p3) if p3 is not None else None),
                    "F_XEB": float(math.comb(n, k) * np.mean(np.exp(lpx)) - 1),
                    "ponderi_finale": {nm: float(v) for nm, v in zip(names, wfin)},
                    "bilet_urmatoarea_extragere": [x + 1 for x in tk[T]],
                }
            logE = float(tot_lr.sum())
            pr["logE"] = logE
            pr["log10E"] = logE / math.log(10)
            pr["logE_prima_jumatate"] = float(tot_lr[:half].sum())
            pr["logE_a_doua_jumatate"] = float(tot_lr[half:].sum())
            pr["logE_din_2010"] = float(tot_lr[i2010:].sum())
            pr["p_ville"] = min(1.0, math.exp(-logE))
            pvals[f"{game}:{X}"] = pr["p_ville"]
            g["pred"][X] = pr
        for r in rows:
            pas.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
        res["games"][game] = g
    pas.close()
    rej = holm(pvals)
    res["holm"] = {"M": len(pvals), "p": pvals, "respinse": rej}
    cand = sorted(key for key, v in rej.items() if v)
    res["verdict"] = "P1_CANDIDATI" if cand else "P1_NICIUN_CANDIDAT"
    res["candidati"] = cand
    res["seconds"] = time.time() - t_start
    res["positive_claims_allowed"] = False
    (OUT / "P1_REZULTATE.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    write_cifre(res)
    for f in ("p1_pas.jsonl", "P1_REZULTATE.json", "RAPORT_P1_CIFRE.md"):
        os.chmod(OUT / f, 0o444)
    print(res["verdict"], cand)
    for f in ("p1_pas.jsonl", "P1_REZULTATE.json", "RAPORT_P1_CIFRE.md"):
        print(f, sha_file(OUT / f))
    return 0


def write_cifre(res):
    L = [f"# RAPORT P1 — cifre (generat automat, {res['utc']})", "",
         f"Verdict: **{res['verdict']}**; candidați: {res['candidati'] or 'niciunul'}. Holm α = {ALPHA}, "
         f"M = {res['holm']['M']}. Familii calificate: {', '.join(res['qualified_families'])}; "
         f"COMB calificat: {res['COMB_qualified']}. positive_claims_allowed=false.", "",
         "| Joc | Predictor | log10 E | E | p (Ville) | Holm | log E jum. 1 | log E jum. 2 | log E din 2010 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for game, g in res["games"].items():
        for X, pr in g["pred"].items():
            L.append(f"| {game} | {X} | {pr['log10E']:.4f} | {math.exp(pr['logE']):.4g} | {pr['p_ville']:.4g} | "
                     f"{'RESPINS' if res['holm']['respinse'][f'{game}:{X}'] else 'nu'} | "
                     f"{pr['logE_prima_jumatate']:.3f} | {pr['logE_a_doua_jumatate']:.3f} | {pr['logE_din_2010']:.3f} |")
    L += ["", "## Nimeriri ale biletului de vârf (descriptiv)", "",
          "| Joc | Sub | Predictor | nimeriri | nul | p unilateral | extrageri cu ≥3 | nul | p | F_XEB | bilet următor |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for game, g in res["games"].items():
        for X, pr in g["pred"].items():
            for lab, s in pr["sub"].items():
                n3 = "—" if s["n_hits_ge_3"] is None else s["n_hits_ge_3"]
                n3m = "—" if s["n_hits_ge_3_null_mean"] is None else f"{s['n_hits_ge_3_null_mean']:.1f}"
                n3p = "—" if s["n_hits_ge_3_p_one_sided"] is None else f"{s['n_hits_ge_3_p_one_sided']:.3g}"
                L.append(f"| {game} | {lab} | {X} | {s['hits_sum']} | {s['hits_null_mean']:.1f} | "
                         f"{s['hits_p_one_sided']:.3g} | {n3} | {n3m} | {n3p} | {s['F_XEB']:.5f} | "
                         f"{s['bilet_urmatoarea_extragere']} |")
    L += ["", "Biletele „următoare” sunt ieșiri de model: NU emise, NU recomandate; șansa reală rămâne uniformă "
          "cât timp niciun predictor nu este confirmat prospectiv (P3).", ""]
    for game, g in res["games"].items():
        L.append(f"- {game}: T = {g['T']} ({g['first']} … {g['last']}), speciale {g['n_special']}, "
                 f"cu dezacord de sursă {g['n_source_disagreement']}.")
    (OUT / "RAPORT_P1_CIFRE.md").write_text("\n".join(L) + "\n")


def main(argv):
    if len(argv) < 2 or argv[1] not in ("teste", "productie"):
        print(__doc__)
        return 2
    return cmd_teste() if argv[1] == "teste" else cmd_productie()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
