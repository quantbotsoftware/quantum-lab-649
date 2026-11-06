#!/usr/bin/env python3
"""XI-P4 — „Amestecare insuficientă”: perechi vecine și blocuri de încărcare (planul V12, faza P4).

Implementează EXACT `xi/PROTOCOL_XI_P4.md` (8d56aeaf…) sub `xi/AMENDAMENT_V12_01.md` (7db003c5…).
Subcomenzi:
  teste        calificarea tehnică Q1–Q5 + curba de rezoluție P4c pe date SINTETICE (nu citește date reale)
  dezvoltare   rularea unică pe arhiva RO + cele 4 arhive străine `dev.json` (cod sigilat; refuză repetarea)
  confirmare   rularea unică pe `rezerva.json`, NUMAI dacă există supraviețuitori străini și sigiliu valid
Calcul clasic float64 pe CPU. Nimic din `quantum_limit` sau modele închise nu este importat.
positive_claims_allowed=false.
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
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

sys.dont_write_bytecode = True
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
XI = HERE.parent
ROOT = XI.parent
DATE_P2 = XI / "date_p2"
OUT = XI / "rezultate" / "P4"
CAL = OUT / "calificare"
CONF = HERE / "SIGILIU_CONFIRMARE_P4.json"

PROTOCOL_SHA = "8d56aeafdb602befb9c91ac644a744e6b1d449774168d82fdc4ebd804fe66af3"
SIGILIU_PROT_SHA = "f2a23e175bfd4d97f022bb34ccc989bc400413db9c673c48079c0c8524e2796b"
AMEND_V12_SHA = "7db003c5b920bddd3fd9d8e86d405ba80deb60519f4f8190545ee3f2bf13e9fe"
PLAN_V12_SHA = "a675289e736f6754e3ca14593e89f4c58be3297f0a3f27b05af927124d302bd1"

DB_RO = Path("./loto_romania/data/snapshots/"
             "c6bfd021af15d9d6ece6b20d106550e4c8474049e38e9caa3bd1c99d19766adb/loto_romania.sqlite")
DB_RO_SHA = "9942abfc25282a715cba70e4f6d17a885a467eaf5fe0440838dc28114003c078"

DEV_STRAIN_SHA = {
    "HU_otos": "b6024d3ad27d4dc6b09b411b5da680d3a4e16a8fa453222618fa40d30a7de557",
    "FR_loto": "eec4e4d3751804a029f89e92ee108047776c724dc5b9592ba0f0d9eefeb9e636",
    "US_powerball": "cd5aa83ad627c296117bfaf5df0451b10343983abc1e154b38a5351b85985e40",
    "HU_hatos": "951d6eaf19fd434dbbc8d9af95dec2b2340e3e648fae061c289138e95dbfd784",
}
HU_HATOS_CLEAN_START = "2007-07-29"

RO_GAMES = {
    "RO_649": [("649", 49, 6)],
    "RO_540": [("540", 40, 6)],
    "RO_joker": [("princ", 45, 5), ("bila", 20, 1)],
}
RO_T_EXPECTED = {"RO_649": 2384, "RO_540": 2341, "RO_joker": 2203}

FOREIGN_GAMES = {
    "HU_otos": [("princ", 90, 5)],
    "FR_loto": [("princ", 49, 5), ("bila", 10, 1)],
    "US_powerball": [("princ", 69, 5), ("bila", 26, 1)],
    "HU_hatos": [("princ", 45, 6)],
}
FOREIGN_TDEV_EXPECTED = {"HU_otos": 2908, "FR_loto": 1980, "US_powerball": 1141, "HU_hatos": 694}
EXCLUDED_P2_GAMES = ("DE_6aus49_sambata", "US_megamillions")

SEED = 202611014
ALPHA = 0.01
E_THR = 1500.0
PROCS = 24

VEC_RADII = (1, 2)
VEC_BETAS = (-1.20, -0.60, -0.30, -0.15, -0.07, 0.07, 0.15, 0.30, 0.60, 1.20)
BLOC_TYPES = ("CONT", "MOD")
BLOC_BS = (5, 7, 10)
BLOC_BETAS = (-0.80, -0.40, -0.20, -0.08, 0.08, 0.20, 0.40, 0.80)

FAMILIES = ("VEC", "BLOC")
PREDICTORS = ("VEC", "BLOC", "COMB")


def sha_b(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_f(p: Path | str) -> str:
    return sha_b(Path(p).read_bytes())


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def lse(a: np.ndarray, axis=None):
    m = np.max(a, axis=axis, keepdims=True)
    r = m + np.log(np.sum(np.exp(a - m), axis=axis, keepdims=True))
    return np.squeeze(r, axis=axis) if axis is not None else float(r.reshape(-1)[0])


# ---------------------------------------------------------------- garda rezervei
def citeste_date(path: Path, conf: Path = CONF, dev_rez: Path | None = None) -> bytes:
    """Orice citire de date din `date_p2` trece prin această gardă (protocol §4.3, §5 Q5)."""
    p = Path(path).resolve()
    if "sigilat" in p.parts or p.name.startswith("rezerva"):
        if not conf.exists():
            raise PermissionError(f"rezerva este sigilată (lipsește {conf.name}): {p.name}")
        s = json.loads(conf.read_text())
        if not s.get("supravietuitori_dev_strain"):
            raise PermissionError("niciun supraviețuitor străin: rezerva rămâne sigilată")
        dr = dev_rez if dev_rez is not None else OUT / "P4_DEV_REZULTATE.json"
        if not dr.exists() or sha_f(dr) != s.get("dev_rezultate_sha256"):
            raise PermissionError("sha-ul rezultatelor de dezvoltare nu corespunde sigiliului de confirmare")
    return p.read_bytes()


# ---------------------------------------------------------------- modelele VEC și BLOC (exacte, fără enumerare)
def components(k: int) -> list[tuple[str, object]]:
    comp: list[tuple[str, object]] = [("U", None)]
    if k >= 2:
        for r in VEC_RADII:
            for beta in VEC_BETAS:
                comp.append(("VEC", (r, beta)))
        for tip in BLOC_TYPES:
            for b in BLOC_BS:
                for beta in BLOC_BETAS:
                    comp.append(("BLOC", (tip, b, beta)))
    return comp


def priors(pred: str, k: int, qualified=FAMILIES) -> np.ndarray:
    comp = components(k)
    rho = np.zeros(len(comp), dtype=np.float64)
    if k < 2:
        rho[0] = 1.0
        return rho
    rho[0] = 0.5
    if pred == "COMB":
        fams = [f for f in FAMILIES if f in qualified]
    else:
        fams = [pred] if pred in qualified else []
    if not fams:
        rho[0] = 1.0
        return rho
    for f in fams:
        idx = [j for j, (fam, _) in enumerate(comp) if fam == f]
        for j in idx:
            rho[j] = 0.5 / len(fams) / len(idx)
    return rho


def vec_tables(n: int, k: int, r: int, beta: float):
    """Programare dinamică înainte-înapoi pe lanțul 0..n-1 pentru P_{r,beta}(S) ∝ exp(beta * A_{vec,r}(S))."""
    assert r in (1, 2) and 1 <= k <= n
    ns = 1 << r
    mask = ns - 1
    s0 = [((s << 1) & mask) for s in range(ns)]
    s1 = [(((s << 1) | 1) & mask) for s in range(ns)]
    w1 = [math.exp(beta * s.bit_count()) for s in range(ns)]

    F = np.zeros((n + 1, k + 1, ns), dtype=np.float64)
    F[0, 0, 0] = 1.0
    for i in range(n):
        Fi = F[i]
        Fn = F[i + 1]
        for s in range(ns):
            Fn[:, s0[s]] += Fi[:, s]
            Fn[1:, s1[s]] += Fi[:-1, s] * w1[s]
    Z = float(F[n, k, :].sum())

    B = np.zeros((n + 1, k + 1, ns), dtype=np.float64)
    B[n, 0, :] = 1.0
    for i in range(n - 1, -1, -1):
        Bn = B[i + 1]
        Bi = B[i]
        for s in range(ns):
            Bi[:, s] = Bn[:, s0[s]]
            Bi[1:, s] += w1[s] * Bn[:-1, s1[s]]

    marg = np.zeros(n, dtype=np.float64)
    for i in range(n):
        acc = 0.0
        for s in range(ns):
            acc += w1[s] * float(np.dot(F[i, :k, s], B[i + 1, k - 1::-1, s1[s]]))
        marg[i] = acc / Z
    return Z, marg, B, s0, s1, w1


def vec1_vandermonde_logZ(n: int, k: int, beta: float) -> float:
    """Forma închisă Vandermonde pentru r=1: Σ_{a=0..k-1} C(k-1,a)*C(n-k+1,k-a)*exp(beta*a)."""
    terms = np.array(
        [math.log(math.comb(k - 1, a)) + math.log(math.comb(n - k + 1, k - a)) + beta * a
         for a in range(k) if k - a <= n - k + 1],
        dtype=np.float64,
    )
    return lse(terms)


def vec_sample(n: int, k: int, r: int, beta: float, rng: np.random.Generator, pre=None) -> np.ndarray:
    if pre is None:
        pre = vec_tables(n, k, r, beta)
    _, _, B, s0, s1, w1 = pre
    S = []
    rem = k
    s = 0
    for i in range(n):
        if rem == 0:
            break
        p1 = w1[s] * B[i + 1, rem - 1, s1[s]] / B[i, rem, s]
        if rng.random() < p1:
            S.append(i)
            rem -= 1
            s = s1[s]
        else:
            s = s0[s]
    return np.array(S, dtype=np.int64)


def make_partition(n: int, tip: str, b: int) -> list[np.ndarray]:
    if tip == "CONT":
        return [np.arange(a, min(a + b, n), dtype=np.int64) for a in range(0, n, b)]
    if tip == "MOD":
        return [np.arange(r, n, b, dtype=np.int64) for r in range(min(b, n))]
    raise ValueError(tip)


def bloc_tables(n: int, k: int, tip: str, b: int, beta: float):
    """Convoluție exactă de polinoame pe blocurile partiției Π_{tip, b}."""
    blocks = make_partition(n, tip, b)
    sizes = [len(blk) for blk in blocks]
    M = len(blocks)
    P = np.zeros((M, k + 1), dtype=np.float64)
    for q, sq in enumerate(sizes):
        for u in range(min(sq, k) + 1):
            P[q, u] = math.comb(sq, u) * math.exp(beta * (u * (u - 1) // 2))

    D = np.zeros((M + 1, k + 1), dtype=np.float64)
    D[0, 0] = 1.0
    for q, sq in enumerate(sizes):
        for u in range(min(sq, k) + 1):
            D[q + 1, u:] += D[q, :k + 1 - u] * P[q, u]
    Z = float(D[M, k])

    Rsuf = np.zeros((M + 1, k + 1), dtype=np.float64)
    Rsuf[M, 0] = 1.0
    for q in range(M - 1, -1, -1):
        sq = sizes[q]
        for u in range(min(sq, k) + 1):
            Rsuf[q, u:] += P[q, u] * Rsuf[q + 1, :k + 1 - u]

    marg = np.zeros(n, dtype=np.float64)
    for q, sq in enumerate(sizes):
        acc = 0.0
        for u in range(1, min(sq, k) + 1):
            rem = k - u
            eminus = float(np.dot(D[q, :rem + 1], Rsuf[q + 1, rem::-1]))
            acc += math.comb(sq - 1, u - 1) * math.exp(beta * (u * (u - 1) // 2)) * eminus
        marg[blocks[q]] = acc / Z
    return Z, marg, blocks, sizes, P, Rsuf


def bloc_sample(n: int, k: int, tip: str, b: int, beta: float, rng: np.random.Generator, pre=None) -> np.ndarray:
    if pre is None:
        pre = bloc_tables(n, k, tip, b, beta)
    _, _, blocks, sizes, P, Rsuf = pre
    rem = k
    chosen = []
    for q, sq in enumerate(sizes):
        if rem == 0:
            break
        umax = min(sq, rem)
        probs = np.array([P[q, u] * Rsuf[q + 1, rem - u] for u in range(umax + 1)], dtype=np.float64)
        probs /= probs.sum()
        u = int(rng.choice(umax + 1, p=probs))
        if u > 0:
            chosen.extend(int(x) for x in rng.choice(blocks[q], u, replace=False))
            rem -= u
    return np.array(sorted(chosen), dtype=np.int64)


_SUBGAME_CACHE: dict[tuple[int, int], tuple[list, np.ndarray, np.ndarray]] = {}


def subgame_model_tables(n: int, k: int):
    """Precalculează exact (comp, logZ[J], MARG_comp[J, n]) pentru subjocul (n, k)."""
    key = (n, k)
    if key in _SUBGAME_CACHE:
        return _SUBGAME_CACHE[key]
    comp = components(k)
    J = len(comp)
    logZ = np.zeros(J, dtype=np.float64)
    marg_c = np.zeros((J, n), dtype=np.float64)
    logZ[0] = math.log(math.comb(n, k))
    marg_c[0, :] = k / n
    for j in range(1, J):
        fam, par = comp[j]
        if fam == "VEC":
            r, beta = par
            Z, mg, *_ = vec_tables(n, k, r, beta)
            logZ[j] = math.log(Z)
            marg_c[j] = mg
        elif fam == "BLOC":
            tip, b, beta = par
            Z, mg, *_ = bloc_tables(n, k, tip, b, beta)
            logZ[j] = math.log(Z)
            marg_c[j] = mg
        else:
            raise ValueError(fam)
    _SUBGAME_CACHE[key] = (comp, logZ, marg_c)
    return comp, logZ, marg_c


def draw_statistics(draws: list[np.ndarray], k: int) -> dict:
    """Calculează toate statisticile suficiente A_c(S_t) pentru lista de extrageri 0-bazate."""
    T = len(draws)
    if T == 0 or k < 2:
        return {}
    arr = np.asarray(draws, dtype=np.int64)
    assert arr.shape == (T, k), (arr.shape, T, k)
    assert np.all(arr[:, 1:] > arr[:, :-1]), "extragerile trebuie să fie strict crescătoare"
    diff = np.abs(arr[:, :, None] - arr[:, None, :])
    off = ~np.eye(k, dtype=bool)
    st = {}
    for r in VEC_RADII:
        st[("VEC", r)] = ((diff >= 1) & (diff <= r)).sum(axis=(1, 2)) // 2
    for b in BLOC_BS:
        qc = arr // b
        st[("BLOC", "CONT", b)] = ((qc[:, :, None] == qc[:, None, :]) & off[None, :, :]).sum(axis=(1, 2)) // 2
        qm = arr % b
        st[("BLOC", "MOD", b)] = ((qm[:, :, None] == qm[:, None, :]) & off[None, :, :]).sum(axis=(1, 2)) // 2
    return st


def eval_components(draws: list[np.ndarray], n: int, k: int):
    """Returnează LP[T, J] = log P_j(S_t) și MARG_comp[J, n]."""
    comp, logZ, marg_c = subgame_model_tables(n, k)
    T = len(draws)
    J = len(comp)
    LP = np.empty((T, J), dtype=np.float64)
    LP[:, 0] = -logZ[0]
    if k >= 2 and T > 0:
        st = draw_statistics(draws, k)
        for j in range(1, J):
            fam, par = comp[j]
            if fam == "VEC":
                r, beta = par
                LP[:, j] = beta * st[("VEC", r)] - logZ[j]
            else:
                tip, b, beta = par
                LP[:, j] = beta * st[("BLOC", tip, b)] - logZ[j]
    return LP, marg_c, comp


def logE_closed(LP: np.ndarray, rho: np.ndarray, n: int, k: int) -> float:
    logU = -math.log(math.comb(n, k))
    tot = (LP - logU).sum(axis=0)
    mask = rho > 0
    return lse(np.log(rho[mask]) + tot[mask])


def mixture_seq(LP: np.ndarray, rho: np.ndarray, n: int, k: int, marg_c: np.ndarray | None = None, extra_step=False):
    """Secvența prequențială exactă: log P_X(S_t|H_{t-1}), log LR_t, marginalele [T (+1), n] și ponderile finale."""
    logU = -math.log(math.comb(n, k))
    mask = rho > 0
    lr = np.log(rho[mask])
    L = LP[:, mask]
    T = L.shape[0]
    cum = np.vstack([np.zeros((1, L.shape[1])), np.cumsum(L, axis=0)])
    logw = lr[None, :] + cum  # shape (T+1, J_active); logw[t] folosit înaintea pasului t (0-bazat)
    lpx = lse(logw[:T] + L, axis=1) - lse(logw[:T], axis=1)
    W_all = np.exp(logw - lse(logw, axis=1)[:, None])
    marg = None
    if marg_c is not None:
        steps = T + 1 if extra_step else T
        marg = W_all[:steps] @ marg_c[mask]
    # W_full pe toate componentele la final (după T pași)
    W_final = np.zeros(len(rho), dtype=np.float64)
    W_final[mask] = W_all[T]
    return lpx, lpx - logU, marg, W_final


def ticket(marg: np.ndarray, k: int) -> list[int]:
    r = np.round(marg, 12)
    order = np.lexsort((np.arange(len(r)), -r))
    return sorted(int(i) for i in order[:k])


# ---------------------------------------------------------------- statistici auxiliare (Holm, hipergeometric, chi2)
def gammaincc(a: float, x: float) -> float:
    if x <= 0.0:
        return 1.0
    if x < a + 1.0:
        ap = a
        s = del_ = 1.0 / a
        for _ in range(400):
            ap += 1.0
            del_ *= x / ap
            s += del_
            if abs(del_) < abs(s) * 1e-15:
                break
        p = s * math.exp(-x + a * math.log(x) - math.lgamma(a))
        return max(0.0, 1.0 - p)
    b = x + 1.0 - a
    c = 1.0 / 1e-300
    d = 1.0 / b
    h = d
    for i in range(1, 400):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        del_ = d * c
        h *= del_
        if abs(del_ - 1.0) < 1e-15:
            break
    return max(0.0, h * math.exp(-x + a * math.log(x) - math.lgamma(a)))


def chi2_sf(x: float, dof: int) -> float:
    return gammaincc(0.5 * dof, 0.5 * x)


def hyper_pmf(n: int, k: int) -> np.ndarray:
    c = math.comb(n, k)
    return np.array([math.comb(k, h) * math.comb(n - k, k - h) / c for h in range(k + 1)], dtype=np.float64)


def conv_power(pmf: np.ndarray, T: int) -> np.ndarray:
    res = np.array([1.0], dtype=np.float64)
    base = pmf.copy()
    m = T
    while m > 0:
        if m & 1:
            res = np.convolve(res, base)
        m >>= 1
        if m:
            base = np.convolve(base, base)
    return res


def binom_sf(x: int, T: int, p: float) -> float:
    if x <= 0:
        return 1.0
    if x > T:
        return 0.0
    lp = math.log(p)
    lq = math.log1p(-p)
    terms = [math.lgamma(T + 1) - math.lgamma(i + 1) - math.lgamma(T - i + 1) + i * lp + (T - i) * lq
             for i in range(x, T + 1)]
    return min(1.0, math.exp(lse(np.array(terms, dtype=np.float64))))


def holm(pvals: dict[str, float], alpha: float = ALPHA) -> dict:
    order = sorted(pvals, key=lambda key: (pvals[key], key))
    M = len(order)
    rej = {key: False for key in pvals}
    thresholds = {}
    still = True
    for idx, key in enumerate(order):
        thr = alpha / (M - idx)
        thresholds[key] = thr
        if still and pvals[key] <= thr:
            rej[key] = True
        else:
            still = False
    return {"M": M, "alpha": alpha, "ordine": order, "praguri": thresholds, "respinse": rej}


# ---------------------------------------------------------------- calificare sintetică Q1–Q5
def gen_uniform(n: int, k: int, T: int, seed: int) -> list[np.ndarray]:
    rng = np.random.Generator(np.random.PCG64(seed))
    return [np.sort(rng.choice(n, k, replace=False)) for _ in range(T)]


def gen_signal(kind: str, n: int, k: int, T: int, seed: int, beta: float) -> list[np.ndarray]:
    rng = np.random.Generator(np.random.PCG64(seed))
    if kind == "vec1":
        pre = vec_tables(n, k, 1, beta)
        return [vec_sample(n, k, 1, beta, rng, pre) for _ in range(T)]
    if kind == "bloc_cont7":
        pre = bloc_tables(n, k, "CONT", 7, beta)
        return [bloc_sample(n, k, "CONT", 7, beta, rng, pre) for _ in range(T)]
    if kind == "bloc_mod10":
        pre = bloc_tables(n, k, "MOD", 10, beta)
        return [bloc_sample(n, k, "MOD", 10, beta, rng, pre) for _ in range(T)]
    raise ValueError(kind)


def _combs_arr(n: int, k: int) -> np.ndarray:
    return np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(n), k)),
                       dtype=np.int8, count=math.comb(n, k) * k).reshape(-1, k)


def q1_exactness() -> dict:
    out: dict = {}
    # Q1a — enumerare completă pe (10, 3) și (12, 4) pentru toate cele 68 de componente non-uniforme
    enum_small = {}
    for n, k in ((10, 3), (12, 4)):
        combs = [np.array(c, dtype=np.int64) for c in itertools.combinations(range(n), k)]
        LP, marg_c, comp = eval_components(combs, n, k)
        P = np.exp(LP)  # shape (C(n,k), J)
        sum_err = float(np.max(np.abs(P.sum(axis=0) - 1.0)))
        # marginale prin enumerare directă
        inc = np.zeros((len(combs), n), dtype=np.float64)
        for idx, s in enumerate(combs):
            inc[idx, s] = 1.0
        marg_enum = P.T @ inc
        marg_err = float(np.max(np.abs(marg_c - marg_enum)))
        msum_err = float(np.max(np.abs(marg_c.sum(axis=1) - k)))
        enum_small[f"{n}_{k}"] = {
            "n_comp": len(comp), "sum_err": sum_err, "marg_err": marg_err, "marg_sum_err": msum_err,
            "PASS": bool(sum_err <= 1e-12 and marg_err <= 1e-12 and msum_err <= 1e-12),
        }
    out["Q1a_small_enum"] = enum_small

    # Q1a — toate subjocurile reale cu k >= 2: suma marginalelor = k și Vandermonde r=1
    real_subs = {}
    for n, k in ((49, 6), (40, 6), (45, 5), (49, 5), (69, 5), (90, 5)):
        comp, logZ, marg_c = subgame_model_tables(n, k)
        msum_err = float(np.max(np.abs(marg_c.sum(axis=1) - k)))
        vand_err = max(
            abs(logZ[j] - vec1_vandermonde_logZ(n, k, par[1]))
            for j, (fam, par) in enumerate(comp) if fam == "VEC" and par[0] == 1
        )
        real_subs[f"{n}_{k}"] = {
            "marg_sum_err": msum_err, "vandermonde_r1_err": float(vand_err),
            "PASS": bool(msum_err <= 1e-11 and vand_err <= 1e-12),
        }
    # Enumerare completă pe (49, 6) (13 983 816 mulțimi) pentru VEC(r=2, beta=0.60) și BLOC(CONT, 7, beta=0.40)
    combs49 = _combs_arr(49, 6)
    z_vec49, *_ = vec_tables(49, 6, 2, 0.60)
    lz_vec49 = math.log(z_vec49)
    z_bl49, *_ = bloc_tables(49, 6, "CONT", 7, 0.40)
    lz_bl49 = math.log(z_bl49)
    tot_vec = 0.0
    tot_bl = 0.0
    off6 = ~np.eye(6, dtype=bool)
    for a in range(0, len(combs49), 1_000_000):
        chunk = combs49[a:a + 1_000_000].astype(np.int16)
        # r=2 pe mulțimi strict crescătoare: d1 = y_{m+1}-y_m <= 2 și d2 = y_{m+2}-y_m <= 2
        avec2 = ((chunk[:, 1:] - chunk[:, :-1]) <= 2).sum(axis=1) + ((chunk[:, 2:] - chunk[:, :-2]) <= 2).sum(axis=1)
        tot_vec += float(np.exp(0.60 * avec2 - lz_vec49).sum())
        qb = chunk // 7
        abloc = ((qb[:, :, None] == qb[:, None, :]) & off6[None, :, :]).sum(axis=(1, 2)) // 2
        tot_bl += float(np.exp(0.40 * abloc - lz_bl49).sum())
    del combs49
    out["Q1a_enum_49_6"] = {
        "vec_r2_b060_sum": tot_vec, "bloc_cont7_b040_sum": tot_bl,
        "PASS": bool(abs(tot_vec - 1.0) <= 1e-9 and abs(tot_bl - 1.0) <= 1e-9),
    }
    out["Q1a_real_subs"] = real_subs

    # Q1b — subjocuri k=1 și telescopare BMA
    k1_errs = {}
    for n in (20, 10, 26):
        H1 = [np.array([i % n], dtype=np.int64) for i in range(50)]
        LP1, mg1, _ = eval_components(H1, n, 1)
        for X in PREDICTORS:
            rho = priors(X, 1)
            lpx, lr1, _, _ = mixture_seq(LP1, rho, n, 1, mg1)
            k1_errs[f"{n}_{X}"] = max(float(np.max(np.abs(lpx + math.log(n)))), abs(float(lr1.sum())))
    H_tel = gen_uniform(49, 6, 400, SEED + 11)
    LP_t, mg_t, _ = eval_components(H_tel, 49, 6)
    tel_errs = {}
    for X in PREDICTORS:
        rho = priors(X, 6)
        _, lr_t, _, _ = mixture_seq(LP_t, rho, 49, 6, mg_t)
        tel_errs[X] = abs(float(lr_t.sum()) - logE_closed(LP_t, rho, 49, 6))
    out["Q1b"] = {
        "k1_max_err": max(k1_errs.values()),
        "telescoping_max_err": max(tel_errs.values()),
        "PASS": bool(max(k1_errs.values()) <= 1e-12 and max(tel_errs.values()) <= 1e-9),
    }

    # Q1c — eșantionatoare exacte pe (8, 3), 200 000 de extrageri, chi2 față de exact
    combs8 = [tuple(c) for c in itertools.combinations(range(8), 3)]
    idx8 = {c: i for i, c in enumerate(combs8)}
    arr8 = [np.array(c, dtype=np.int64) for c in combs8]
    LP8, _, comp8 = eval_components(arr8, 8, 3)
    N_samp = 200_000
    chi_res = {}
    specs_c = [
        ("vec_r2_pos", "VEC", (2, 0.60), SEED + 21),
        ("vec_r1_neg", "VEC", (1, -0.60), SEED + 22),
        ("bloc_c3_pos", "BLOC", None, SEED + 23),
    ]
    for name, fam, par, sd in specs_c:
        rng = np.random.Generator(np.random.PCG64(sd))
        counts = np.zeros(len(combs8), dtype=np.int64)
        if fam == "VEC":
            r, beta = par
            j = comp8.index(("VEC", (r, beta)))
            probs = np.exp(LP8[:, j])
            pre = vec_tables(8, 3, r, beta)
            for _ in range(N_samp):
                s = tuple(int(x) for x in vec_sample(8, 3, r, beta, rng, pre))
                counts[idx8[s]] += 1
        else:
            # BLOC(CONT, b=3, beta=0.80) pe (8, 3)
            Z_b, _, bl_b, sz_b, P_b, Rs_b = pre = bloc_tables(8, 3, "CONT", 3, 0.80)
            probs = np.array([
                math.exp(0.80 * sum(math.comb(int(np.isin(c, blk).sum()), 2) for blk in bl_b)) / Z_b
                for c in arr8
            ], dtype=np.float64)
            for _ in range(N_samp):
                s = tuple(int(x) for x in bloc_sample(8, 3, "CONT", 3, 0.80, rng, pre))
                counts[idx8[s]] += 1
        expected = N_samp * probs
        chi2 = float(((counts - expected) ** 2 / expected).sum())
        pval = chi2_sf(chi2, len(combs8) - 1)
        chi_res[name] = {"chi2": chi2, "dof": len(combs8) - 1, "p": pval, "PASS": bool(pval > 0.001)}
    out["Q1c_samplers"] = chi_res

    # Q1d — martorii analitici de informație și decizie (protocol §3.1 și §3.2)
    # 1) Formulele închise pe (6, 3), r=1
    w_vec_err = 0.0
    for beta in VEC_BETAS:
        u = math.exp(beta)
        Z_th = 4.0 * (1.0 + 3.0 * u + u * u)
        mg_th = np.array([3 + 6 * u + u * u, 1 + 7 * u + 2 * u * u, 2 + 5 * u + 3 * u * u,
                          2 + 5 * u + 3 * u * u, 1 + 7 * u + 2 * u * u, 3 + 6 * u + u * u], dtype=np.float64) / Z_th
        Z_dp, mg_dp, *_ = vec_tables(6, 3, 1, beta)
        w_vec_err = max(w_vec_err, abs(Z_dp - Z_th) / Z_th, float(np.max(np.abs(mg_dp - mg_th))))
    # Istoriile martor H_+ și H_- (lungime 8, 0-bazate)
    H_plus = [np.array([0, 1, 2]), np.array([3, 4, 5])] * 4
    H_minus = [np.array([0, 2, 4]), np.array([1, 3, 5])] * 4
    c_plus = np.bincount(np.concatenate(H_plus), minlength=6)
    c_minus = np.bincount(np.concatenate(H_minus), minlength=6)
    # STAT și FERMI pe H_+ și H_- (verificare directă din ecuațiile XI-P1 §3)
    fermi_unif_ok = True
    for Hw in (H_plus, H_minus):
        Cmat = np.zeros((6, 6), dtype=np.float64)
        for s in Hw:
            Cmat[np.ix_(s, s)] += 1.0
        for m_sh in (200.0, 800.0, 3200.0):
            pi_i = (4.0 + m_sh * 0.5) / (8.0 + m_sh)  # = 0.5 exact
            pi_ij = (Cmat + m_sh * 0.2) / (8.0 + m_sh)
            Kmat = np.sqrt(np.maximum(pi_i * pi_i - pi_ij, 0.0))
            np.fill_diagonal(Kmat, 0.5)
            ev, V = np.linalg.eigh(Kmat)
            ev = np.clip(ev, 1e-9, 1.0 - 1e-9)
            ell = ev / (1.0 - ev)
            # e_3(ell) și e_2(ell_{-j})
            e = np.zeros(4)
            e[0] = 1.0
            for x in ell:
                e[1:] += x * e[:-1]
            mg_f = np.zeros(6)
            for j in range(6):
                ej = np.zeros(3)
                ej[0] = 1.0
                for idx_l, x in enumerate(ell):
                    if idx_l != j:
                        ej[1:] += x * ej[:-1]
                mg_f += (V[:, j] ** 2) * (ell[j] * ej[2] / e[3])
            fermi_unif_ok &= bool(np.max(np.abs(mg_f - 0.5)) <= 1e-12 and [x + 1 for x in ticket(mg_f, 3)] == [1, 2, 3])
    # VEC pe H_+ și H_- pentru pasul t = 9 (după cele 8 extrageri)
    s_cl = np.array([0, 1, 2], dtype=np.int64)
    s_sp = np.array([0, 2, 4], dtype=np.int64)
    LP_p_cl, mg6, _ = eval_components(H_plus + [s_cl], 6, 3)
    LP_p_sp, _, _ = eval_components(H_plus + [s_sp], 6, 3)
    LP_m_cl, _, _ = eval_components(H_minus + [s_cl], 6, 3)
    LP_m_sp, _, _ = eval_components(H_minus + [s_sp], 6, 3)
    rho_vec6 = priors("VEC", 3)
    lpx_p_cl, _, mg_seq_p, _ = mixture_seq(LP_p_cl, rho_vec6, 6, 3, mg6)
    lpx_p_sp, _, _, _ = mixture_seq(LP_p_sp, rho_vec6, 6, 3, mg6)
    lpx_m_cl, _, mg_seq_m, _ = mixture_seq(LP_m_cl, rho_vec6, 6, 3, mg6)
    lpx_m_sp, _, _, _ = mixture_seq(LP_m_sp, rho_vec6, 6, 3, mg6)
    p_plus_cl = math.exp(float(lpx_p_cl[8]))
    p_plus_sp = math.exp(float(lpx_p_sp[8]))
    p_minus_cl = math.exp(float(lpx_m_cl[8]))
    p_minus_sp = math.exp(float(lpx_m_sp[8]))
    t_plus = [x + 1 for x in ticket(mg_seq_p[8], 3)]
    t_minus = [x + 1 for x in ticket(mg_seq_m[8], 3)]

    # 2) Martorul BLOC pe (7, 3), CONT, b=5
    w_bloc_err = 0.0
    t_bloc_pos_ok = True
    t_bloc_neg_ok = True
    for beta in BLOC_BETAS:
        w = math.exp(beta)
        Z_th = 5.0 * w * (5.0 + 2.0 * w * w)
        pi_b1 = (9.0 + 6.0 * w * w) / (5.0 * (5.0 + 2.0 * w * w))
        pi_b2 = 15.0 / (5.0 * (5.0 + 2.0 * w * w))
        mg_th = np.array([pi_b1] * 5 + [pi_b2] * 2, dtype=np.float64)
        Z_dp, mg_dp, *_ = bloc_tables(7, 3, "CONT", 5, beta)
        w_bloc_err = max(w_bloc_err, abs(Z_dp - Z_th) / Z_th, float(np.max(np.abs(mg_dp - mg_th))))
        tk = [x + 1 for x in ticket(mg_dp, 3)]
        if beta > 0:
            t_bloc_pos_ok &= (tk == [1, 2, 3])
        else:
            t_bloc_neg_ok &= (tk == [1, 6, 7])

    q1d_pass = bool(
        w_vec_err <= 1e-13
        and c_plus.tolist() == [4] * 6 and c_minus.tolist() == [4] * 6
        and fermi_unif_ok
        and (p_plus_cl > 0.05 > p_plus_sp)
        and (p_minus_sp > 0.05 > p_minus_cl)
        and t_plus == [2, 3, 4]
        and t_minus == [1, 3, 6]
        and w_bloc_err <= 1e-13 and t_bloc_pos_ok and t_bloc_neg_ok
    )
    out["Q1d_witnesses"] = {
        "vec_closed_form_err": w_vec_err,
        "counts_plus": c_plus.tolist(), "counts_minus": c_minus.tolist(),
        "stat_fermi_uniform_ticket_123": fermi_unif_ok,
        "P_VEC_plus_123_vs_135": [p_plus_cl, p_plus_sp],
        "P_VEC_minus_123_vs_135": [p_minus_cl, p_minus_sp],
        "ticket_VEC_H_plus": t_plus,
        "ticket_VEC_H_minus": t_minus,
        "bloc_closed_form_err": w_bloc_err,
        "bloc_tickets_pos_123_neg_167": bool(t_bloc_pos_ok and t_bloc_neg_ok),
        "PASS": q1d_pass,
    }
    out["PASS"] = bool(
        all(v["PASS"] for v in enum_small.values())
        and all(v["PASS"] for v in real_subs.values())
        and out["Q1a_enum_49_6"]["PASS"]
        and out["Q1b"]["PASS"]
        and all(v["PASS"] for v in chi_res.values())
        and out["Q1d_witnesses"]["PASS"]
    )
    return out


def q2_predictability() -> dict:
    H = gen_uniform(49, 6, 2000, SEED + 100)
    LP0, mg0, _ = eval_components(H, 49, 6)
    res = {}
    ok_all = True
    for idx, t0 in enumerate((400, 1000, 1600)):
        H2 = list(H[:t0 - 1]) + gen_uniform(49, 6, 2000 - t0 + 1, SEED + 110 + idx)
        LP1, mg1, _ = eval_components(H2, 49, 6)
        same_lp = bool(np.array_equal(LP0[:t0 - 1], LP1[:t0 - 1]))
        same_pred = True
        for X in PREDICTORS:
            rho = priors(X, 6)
            lpx0, _, m0, _ = mixture_seq(LP0, rho, 49, 6, mg0)
            lpx1, _, m1, _ = mixture_seq(LP1, rho, 49, 6, mg1)
            same_pred &= bool(np.array_equal(lpx0[:t0 - 1], lpx1[:t0 - 1]))
            same_pred &= all(ticket(m0[t], 6) == ticket(m1[t], 6) for t in range(t0))
        res[str(t0)] = {"same_lp": same_lp, "same_pred_and_tickets": same_pred}
        ok_all &= same_lp and same_pred
    res["PASS"] = bool(ok_all)
    return res


def _sim_task(spec):
    tag, subs, T, kind, beta, seed = spec
    out = {X: 0.0 for X in PREDICTORS}
    min_sub = float("inf")
    for si, (_lab, n, k) in enumerate(subs):
        if kind == "uniform" or si > 0:
            H = gen_uniform(n, k, T, seed + 9973 * si)
        else:
            H = gen_signal(kind, n, k, T, seed, beta)
        LP, _, _ = eval_components(H, n, k)
        for X in PREDICTORS:
            le = logE_closed(LP, priors(X, k), n, k)
            out[X] += le
            if le < min_sub:
                min_sub = le
    out["_min_sub"] = min_sub
    return spec, out


def q3_q4_synthetic() -> tuple[dict, dict, dict]:
    all_games = {}
    for g, subs in RO_GAMES.items():
        all_games[g] = (subs, RO_T_EXPECTED[g])
    for g, subs in FOREIGN_GAMES.items():
        all_games[g] = (subs, FOREIGN_TDEV_EXPECTED[g])

    tasks = []
    for gi, (g, (subs, T)) in enumerate(all_games.items()):
        for r in range(100):
            tasks.append((f"Q3:{g}:{r}", subs, T, "uniform", 0.0, SEED + 10_000 + 1000 * gi + r))

    q4_scenarios = [
        ("Sigma_VEC_pos", "vec1", 0.35, 1),
        ("Sigma_VEC_neg", "vec1", -0.45, 2),
        ("Sigma_BLOC_pos", "bloc_cont7", 0.25, 3),
        ("Sigma_BLOC_neg", "bloc_mod10", -0.30, 4),
    ]
    for sc_name, kind, beta, sc_id in q4_scenarios:
        for r in range(20):
            tasks.append((f"Q4:{sc_name}:{r}", [("649", 49, 6)], 2384, kind, beta, SEED + 50_000 + 100 * sc_id + r))

    res_betas = (0.05, 0.10, 0.15, 0.20, 0.30, -0.10, -0.20, -0.30)
    for bi, bval in enumerate(res_betas):
        for r in range(20):
            tasks.append((f"RES_VEC:{bval}:{r}", [("649", 49, 6)], 2384, "vec1", bval, SEED + 70_000 + 100 * bi + r))
            tasks.append((f"RES_BLOC:{bval}:{r}", [("649", 49, 6)], 2384, "bloc_cont7", bval, SEED + 80_000 + 100 * bi + r))

    with Pool(PROCS) as pool:
        raw = dict((sp[0], val) for sp, val in pool.map(_sim_task, tasks, chunksize=4))

    min_sub_all = min(v["_min_sub"] for v in raw.values())
    min_sub_ok = bool(min_sub_all >= -math.log(2.0) - 1e-12)

    # Agregare Q3
    q3 = {"min_sub_logE_all_sims": min_sub_all, "min_sub_bound_ok": min_sub_ok, "games": {}}
    q3_ok = min_sub_ok
    for g in all_games:
        q3["games"][g] = {}
        for X in PREDICTORS:
            arr = np.array([raw[f"Q3:{g}:{r}"][X] for r in range(100)], dtype=np.float64)
            f20 = float(np.mean(arr >= math.log(20.0)))
            f1500 = float(np.mean(arr >= math.log(1500.0)))
            q3["games"][g][X] = {
                "frac_E_ge_20": f20, "frac_E_ge_1500": f1500,
                "median_logE": float(np.median(arr)), "max_logE": float(np.max(arr)),
            }
            q3_ok &= (f20 <= 0.10)
    # GLOBAL străin pe cele 100 de replici
    q3["GLOBAL_strain"] = {}
    for X in PREDICTORS:
        arr = np.array([sum(raw[f"Q3:{g}:{r}"][X] for g in FOREIGN_GAMES) for r in range(100)], dtype=np.float64)
        f20 = float(np.mean(arr >= math.log(20.0)))
        q3["GLOBAL_strain"][X] = {
            "frac_E_ge_20": f20, "frac_E_ge_1500": float(np.mean(arr >= math.log(1500.0))),
            "median_logE": float(np.median(arr)), "max_logE": float(np.max(arr)),
        }
        q3_ok &= (f20 <= 0.10)
    q3["PASS"] = bool(q3_ok)

    # Agregare Q4
    q4 = {"scenarios": {}}
    for sc_name, kind, beta, _ in q4_scenarios:
        q4["scenarios"][sc_name] = {"kind": kind, "beta": beta, "predictors": {}}
        for X in PREDICTORS:
            arr = np.array([raw[f"Q4:{sc_name}:{r}"][X] for r in range(20)], dtype=np.float64)
            n_hit = int(np.sum(arr >= math.log(E_THR)))
            q4["scenarios"][sc_name]["predictors"][X] = {
                "hits_E_ge_1500": n_hit, "frac": n_hit / 20.0, "median_logE": float(np.median(arr)),
            }
    vec_qual = (q4["scenarios"]["Sigma_VEC_pos"]["predictors"]["VEC"]["hits_E_ge_1500"] >= 16
                and q4["scenarios"]["Sigma_VEC_neg"]["predictors"]["VEC"]["hits_E_ge_1500"] >= 16)
    bloc_qual = (q4["scenarios"]["Sigma_BLOC_pos"]["predictors"]["BLOC"]["hits_E_ge_1500"] >= 16
                 and q4["scenarios"]["Sigma_BLOC_neg"]["predictors"]["BLOC"]["hits_E_ge_1500"] >= 16)
    comb_qual = all(q4["scenarios"][sc]["predictors"]["COMB"]["hits_E_ge_1500"] >= 16 for sc, *_ in q4_scenarios)
    qual_fams = [f for f, ok in (("VEC", vec_qual), ("BLOC", bloc_qual)) if ok]
    q4["qualified_families"] = qual_fams
    q4["COMB_qualified"] = bool(comb_qual)
    q4["PASS"] = bool(vec_qual and bloc_qual and comb_qual)

    # Curba de rezoluție P4c + raportul așteptat E_beta[A] / E_U[A]
    mean_u_vec1 = 6 * 5 / 49.0  # = 30/49
    mean_u_bloc7 = 7 * math.comb(7, 2) * (6 * 5) / (49 * 48)  # = 1.875
    res_curve = {"VEC_r1_649": {}, "BLOC_CONT7_649": {}}
    for bval in res_betas:
        # E_beta[A_vec1] exact
        cnt_v = np.array([math.comb(5, a) * math.comb(44, 6 - a) for a in range(6)], dtype=np.float64)
        wt_v = cnt_v * np.exp(bval * np.arange(6))
        eb_vec = float((wt_v * np.arange(6)).sum() / wt_v.sum())
        arr_v = np.array([raw[f"RES_VEC:{bval}:{r}"]["VEC"] for r in range(20)], dtype=np.float64)
        arr_vc = np.array([raw[f"RES_VEC:{bval}:{r}"]["COMB"] for r in range(20)], dtype=np.float64)
        res_curve["VEC_r1_649"][str(bval)] = {
            "E_beta_A": eb_vec, "E_U_A": mean_u_vec1, "ratio_pairs_vs_U": eb_vec / mean_u_vec1,
            "VEC_frac_E_ge_1500": float(np.mean(arr_v >= math.log(E_THR))),
            "VEC_median_logE": float(np.median(arr_v)),
            "COMB_frac_E_ge_1500": float(np.mean(arr_vc >= math.log(E_THR))),
        }
        # E_beta[A_bloc7] exact prin diferențiere pe ocupări sau două polinoame
        _, _, _, _, P_b, _ = bloc_tables(49, 6, "CONT", 7, bval)
        # D2[q, m, a] pe a = 0..15
        dp_a = np.zeros((7, 16), dtype=np.float64)
        dp_a[0, 0] = 1.0
        for _ in range(7):
            ndp = np.zeros_like(dp_a)
            for u in range(7):
                pa = u * (u - 1) // 2
                c_u = math.comb(7, u) * math.exp(bval * pa)
                if u == 0:
                    ndp += dp_a
                else:
                    ndp[u:, pa:] += dp_a[:7 - u, :16 - pa] * c_u
            dp_a = ndp
        eb_bl = float((dp_a[6] * np.arange(16)).sum() / dp_a[6].sum())
        arr_b = np.array([raw[f"RES_BLOC:{bval}:{r}"]["BLOC"] for r in range(20)], dtype=np.float64)
        arr_bc = np.array([raw[f"RES_BLOC:{bval}:{r}"]["COMB"] for r in range(20)], dtype=np.float64)
        res_curve["BLOC_CONT7_649"][str(bval)] = {
            "E_beta_A": eb_bl, "E_U_A": mean_u_bloc7, "ratio_pairs_vs_U": eb_bl / mean_u_bloc7,
            "BLOC_frac_E_ge_1500": float(np.mean(arr_b >= math.log(E_THR))),
            "BLOC_median_logE": float(np.median(arr_b)),
            "COMB_frac_E_ge_1500": float(np.mean(arr_bc >= math.log(E_THR))),
        }
    return q3, q4, res_curve


def q5_reserve_guard() -> dict:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        fake_rez = tmp / "rezerva.json"
        fake_rez.write_text('{"extrageri": []}\n')
        sig_dir = tmp / "sigilat"
        sig_dir.mkdir()
        fake_sig = sig_dir / "brut.csv"
        fake_sig.write_text("x\n")
        fake_dev = tmp / "dev.json"
        fake_dev.write_text('{"ok": true}\n')
        fake_conf = tmp / "SIGILIU_INEXISTENT.json"

        ok_dev = json.loads(citeste_date(fake_dev, conf=fake_conf))["ok"] is True
        refused_no_seal = False
        try:
            citeste_date(fake_rez, conf=fake_conf)
        except PermissionError:
            refused_no_seal = True
        refused_sig = False
        try:
            citeste_date(fake_sig, conf=fake_conf)
        except PermissionError:
            refused_sig = True
        empty_conf = tmp / "SIGILIU_GOL.json"
        empty_conf.write_text('{"supravietuitori_dev_strain": []}\n')
        refused_empty = False
        try:
            citeste_date(fake_rez, conf=empty_conf)
        except PermissionError:
            refused_empty = True
        passed = bool(ok_dev and refused_no_seal and refused_sig and refused_empty)
        return {
            "dev_allowed": ok_dev, "refused_no_seal": refused_no_seal,
            "refused_sigilat": refused_sig, "refused_empty_survivors": refused_empty,
            "PASS": passed,
        }


def cmd_teste() -> int:
    assert sha_f(XI / "PROTOCOL_XI_P4.md") == PROTOCOL_SHA, "sha protocol P4"
    assert sha_f(XI / "SIGILIU_XI_P4.json") == SIGILIU_PROT_SHA, "sha sigiliu protocol P4"
    t0 = time.time()
    CAL.mkdir(parents=True, exist_ok=True)
    r_q1 = q1_exactness()
    r_q2 = q2_predictability()
    r_q3, r_q4, res_curve = q3_q4_synthetic()
    r_q5 = q5_reserve_guard()
    utc = utcnow()
    all_pass = bool(r_q1["PASS"] and r_q2["PASS"] and r_q3["PASS"] and r_q4["PASS"] and r_q5["PASS"])
    doc = {
        "utc": utc,
        "protocol_sha256": PROTOCOL_SHA,
        "code_sha256": sha_f(__file__),
        "seed": SEED,
        "durata_sec": round(time.time() - t0, 3),
        "Q1": r_q1,
        "Q2": r_q2,
        "Q3": r_q3,
        "Q4": r_q4,
        "Q5": r_q5,
        "rezolutie_P4c": res_curve,
        "PASS_Q1_Q5": all_pass,
        "positive_claims_allowed": False,
    }
    out_p = CAL / f"CALIFICARE_P4_{utc}.json"
    out_p.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    os.chmod(out_p, 0o444)
    print("CALIFICARE_P4:", "PASS" if all_pass else "FAIL", out_p, sha_f(out_p))
    return 0 if all_pass else 1


# ---------------------------------------------------------------- citirea datelor reale (RO + străin dev)
def load_ro() -> dict[str, list[dict]]:
    assert sha_f(DB_RO) == DB_RO_SHA, "sha baza RO"
    con = sqlite3.connect(f"file:{DB_RO}?mode=ro", uri=True)
    out = {}
    for gname, subs in RO_GAMES.items():
        db_game = "649" if gname == "RO_649" else ("540" if gname == "RO_540" else "joker")
        rows = con.execute(
            "select draw_key, draw_date, draw_kind, n1, n2, n3, n4, n5, n6, joker, has_source_disagreement "
            "from draws where game=? and draw_kind in ('regular','special') "
            "order by draw_date, case draw_kind when 'regular' then 0 else 1 end, draw_key",
            (db_game,),
        ).fetchall()
        assert len(rows) == RO_T_EXPECTED[gname], (gname, len(rows))
        recs = []
        for key, date, kind, *nums, jk, dis in rows:
            if db_game == "joker":
                main = nums[:5]
                assert nums[5] is None and len(set(main)) == 5 and all(1 <= x <= 45 for x in main)
                assert jk is not None and 1 <= jk <= 20
                sets = {"princ": sorted(int(x) for x in main), "bila": [int(jk)]}
            else:
                nn = subs[0][1]
                assert len(set(nums)) == 6 and all(1 <= x <= nn for x in nums) and jk is None
                sets = {subs[0][0]: sorted(int(x) for x in nums)}
            recs.append({"cheie": key, "data": date, "kind": kind, "dis": int(dis), "sets": sets})
        out[gname] = recs
    con.close()
    return out


def load_foreign_dev() -> dict[str, tuple[list[dict], dict]]:
    out = {}
    for gname, subs in FOREIGN_GAMES.items():
        p = DATE_P2 / gname / "dev.json"
        raw = citeste_date(p)
        assert sha_b(raw) == DEV_STRAIN_SHA[gname], f"sha dev.json {gname}"
        d = json.loads(raw)
        assert [tuple(s) for s in d["subjocuri"]] == subs, (gname, d["subjocuri"])
        ext = d["extrageri"]
        excluded_pre2007 = 0
        if gname == "HU_hatos":
            # Protocol §4.2: perioada curată fără pótszám data >= "2007-07-29" (20 câmpuri)
            clean = [e for e in ext if (e["data"] is not None and e["data"] >= HU_HATOS_CLEAN_START)]
            excluded_pre2007 = len(ext) - len(clean)
            assert excluded_pre2007 == 794 and ext[794:] == clean, (excluded_pre2007, len(clean))
            ext = clean
        assert len(ext) == FOREIGN_TDEV_EXPECTED[gname], (gname, len(ext))
        for e in ext:
            for lab, n, k in subs:
                vals = e["sets"][lab]
                assert len(vals) == k and len(set(vals)) == k and all(1 <= x <= n for x in vals)
                assert vals == sorted(vals)
        meta = {
            "dev_sha256": DEV_STRAIN_SHA[gname],
            "rezerva_sha256": d["rezerva_sha256"],
            "T_dev": len(ext),
            "R": int(d["R"]),
            "excluded_pre2007_potszam": excluded_pre2007,
            "prima_data": ext[0]["data"],
            "ultima_data": ext[-1]["data"],
        }
        out[gname] = (ext, meta)
    return out


def _evaluate_game(gname: str, subs: list[tuple[str, int, int]], recs: list[dict],
                   qual: tuple[str, ...], preds: list[str], pas_fh):
    T = len(recs)
    half = T // 2
    idx_2010 = next((t for t, r in enumerate(recs) if r["data"] and r["data"] >= "2010-01-01"), None)

    sub_data = {}
    for lab, n, k in subs:
        H = [np.array([x - 1 for x in r["sets"][lab]], dtype=np.int64) for r in recs]
        LP, marg_c, comp = eval_components(H, n, k)
        # Statistici descriptive empirice de perechi pe subjoc
        emp_stats = {}
        if k >= 2:
            st = draw_statistics(H, k)
            emp_stats["A_vec1_mean"] = float(st[("VEC", 1)].mean())
            emp_stats["A_vec1_expected_U"] = k * (k - 1) / n
            emp_stats["A_vec2_mean"] = float(st[("VEC", 2)].mean())
            emp_stats["A_vec2_expected_U"] = (2 * n - 3) * k * (k - 1) / (n * (n - 1))
            for b in BLOC_BS:
                bl_c = make_partition(n, "CONT", b)
                pairs_c = sum(math.comb(len(blk), 2) for blk in bl_c)
                emp_stats[f"A_CONT{b}_mean"] = float(st[("BLOC", "CONT", b)].mean())
                emp_stats[f"A_CONT{b}_expected_U"] = pairs_c * k * (k - 1) / (n * (n - 1))
                bl_m = make_partition(n, "MOD", b)
                pairs_m = sum(math.comb(len(blk), 2) for blk in bl_m)
                emp_stats[f"A_MOD{b}_mean"] = float(st[("BLOC", "MOD", b)].mean())
                emp_stats[f"A_MOD{b}_expected_U"] = pairs_m * k * (k - 1) / (n * (n - 1))
        pred_sub = {}
        for X in preds:
            rho = priors(X, k, qual)
            lpx, lr, mseq, w_fin = mixture_seq(LP, rho, n, k, marg_c, extra_step=True)
            closed = logE_closed(LP, rho, n, k)
            assert abs(float(lr.sum()) - closed) <= 1e-8, (gname, lab, X)
            tickets_t = [[x + 1 for x in ticket(mseq[t], k)] for t in range(T)]
            next_tk = [x + 1 for x in ticket(mseq[T], k)]
            hits_t = [len(set(tickets_t[t]) & set(recs[t]["sets"][lab])) for t in range(T)]
            hsum = int(sum(hits_t))
            pmf = hyper_pmf(n, k)
            dist = conv_power(pmf, T)
            p_hits = float(dist[hsum:].sum())
            ge3 = int(sum(1 for h in hits_t if h >= 3)) if k >= 3 else None
            p3 = float(pmf[3:].sum()) if k >= 3 else None
            # mase posterioare pe U, beta > 0, beta < 0
            w_u = float(w_fin[0])
            w_pos = float(sum(w_fin[j] for j in range(1, len(comp)) if comp[j][1][-1] > 0))
            w_neg = float(sum(w_fin[j] for j in range(1, len(comp)) if comp[j][1][-1] < 0))
            pred_sub[X] = {
                "lpx": lpx, "lr": lr, "tickets": tickets_t, "hits": hits_t,
                "summary": {
                    "logE": float(lr.sum()),
                    "E": math.exp(min(700.0, float(lr.sum()))),
                    "logE_closed_diff": abs(float(lr.sum()) - closed),
                    "F_XEB": float(math.comb(n, k) * np.mean(np.exp(lpx)) - 1.0),
                    "hits_sum": hsum,
                    "hits_expected_U": T * k * k / n,
                    "hits_p_one_sided": p_hits,
                    "hits_ge3": ge3,
                    "hits_ge3_expected_U": (T * p3 if p3 is not None else None),
                    "hits_ge3_p_binom": (binom_sf(ge3, T, p3) if p3 is not None else None),
                    "w_final_U": w_u,
                    "w_final_beta_pos": w_pos,
                    "w_final_beta_neg": w_neg,
                    "bilet_urmator_model": next_tk,
                },
            }
        sub_data[lab] = {"LP": LP, "emp_stats": emp_stats, "pred": pred_sub}

    for t in range(T):
        row = {
            "joc": gname,
            "t": t + 1,
            "cheie": recs[t]["cheie"],
            "data": recs[t]["data"],
            "S": recs[t]["sets"],
            "logp_comp": {lab: [float(x) for x in sub_data[lab]["LP"][t]] for lab, _, _ in subs},
            "logp_pred": {X: {lab: float(sub_data[lab]["pred"][X]["lpx"][t]) for lab, _, _ in subs} for X in preds},
            "bilet": {X: {lab: sub_data[lab]["pred"][X]["tickets"][t] for lab, _, _ in subs} for X in preds},
            "hits": {X: {lab: sub_data[lab]["pred"][X]["hits"][t] for lab, _, _ in subs} for X in preds},
        }
        pas_fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    game_preds = {}
    for X in preds:
        tot_lr = sum(sub_data[lab]["pred"][X]["lr"] for lab, _, _ in subs)
        le = float(tot_lr.sum())
        game_preds[X] = {
            "logE": le,
            "E": math.exp(min(700.0, le)),
            "p_ville": min(1.0, math.exp(-le)),
            "logE_prima_jumatate": float(tot_lr[:half].sum()),
            "logE_a_doua_jumatate": float(tot_lr[half:].sum()),
            "logE_dupa_2010": (float(tot_lr[idx_2010:].sum()) if idx_2010 is not None else None),
            "sub": {lab: sub_data[lab]["pred"][X]["summary"] for lab, _, _ in subs},
        }
    return {
        "T": T,
        "subjocuri": [list(s) for s in subs],
        "prima_data": recs[0]["data"],
        "ultima_data": recs[-1]["data"],
        "statistici_perechi": {lab: sub_data[lab]["emp_stats"] for lab, _, _ in subs},
        "pred": game_preds,
    }


def _write_dev_cifre(res: dict) -> str:
    lines = [
        "# RAPORT P4 DEZVOLTARE — CIFRE GENERATE AUTOMAT",
        "",
        f"- UTC: `{res['utc']}`",
        f"- Protocol: `{res['protocol_sha256'][:12]}…`, sigiliu cod: `{res['code_seal_sha256'][:12]}…`",
        f"- Predictori calificați: `{', '.join(res['predictori'])}`",
        f"- Verdict RO: **`{res['verdict_ro']}`** (candidați RO: `{res['candidati_ro']}`)",
        f"- Verdict dezvoltare străină: **`{res['verdict_dev_strain']}`** (supraviețuitori: `{res['supravietuitori_dev_strain']}`)",
        "",
        "## 1. E-valori pe arhiva României (explorată, fără rezervă oarbă)",
        "",
        "| Joc | T | " + " | ".join(f"{X} (E / logE)" for X in res["predictori"]) + " |",
        "|---|---:|" + "|".join("---:" for _ in res["predictori"]) + "|",
    ]
    for g in RO_GAMES:
        gd = res["ro_games"][g]
        cells = [f"{gd['pred'][X]['E']:.4f} ({gd['pred'][X]['logE']:+.4f})" for X in res["predictori"]]
        lines.append(f"| `{g}` | {gd['T']} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## 2. E-valori pe arhivele străine de dezvoltare (poarta către rezerva oarbă)",
        "",
        "| Joc | T_dev | " + " | ".join(f"{X} (E / logE)" for X in res["predictori"]) + " |",
        "|---|---:|" + "|".join("---:" for _ in res["predictori"]) + "|",
    ]
    for g in FOREIGN_GAMES:
        gd = res["foreign_games"][g]
        cells = [f"{gd['pred'][X]['E']:.4f} ({gd['pred'][X]['logE']:+.4f})" for X in res["predictori"]]
        lines.append(f"| `{g}` | {gd['T']} | " + " | ".join(cells) + " |")
    gcells = [f"{res['global_strain'][X]['E']:.4f} ({res['global_strain'][X]['logE']:+.4f})"
              for X in res["predictori"]]
    lines.append("| **`GLOBAL`** | 6723 | " + " | ".join(gcells) + " |")
    lines.append("")
    return "\n".join(lines)


def cmd_dezvoltare() -> int:
    seal_p = HERE / "SIGILIU_COD_P4.json"
    assert seal_p.exists(), "codul P4 nu este sigilat"
    seal = json.loads(seal_p.read_text())
    assert seal["files"]["xi/p4/p4.py"] == sha_f(__file__), "sha p4.py"
    assert sha_f(XI / "PROTOCOL_XI_P4.md") == PROTOCOL_SHA
    assert sha_f(XI / "SIGILIU_XI_P4.json") == SIGILIU_PROT_SHA
    assert sha_f(XI / "AMENDAMENT_V12_01.md") == AMEND_V12_SHA

    OUT.mkdir(parents=True, exist_ok=True)
    for fn in ("p4_dev_pas.jsonl", "P4_DEV_REZULTATE.json", "RAPORT_P4_DEV_CIFRE.md"):
        if (OUT / fn).exists():
            print("REFUZ: dezvoltarea P4 a fost deja rulată:", OUT / fn)
            return 2

    qual = tuple(seal["qualified_families"])
    comb_ok = bool(seal["COMB_qualified"])
    preds = [X for X in PREDICTORS if (X in qual) or (X == "COMB" and comb_ok)]

    t0 = time.time()
    utc = utcnow()
    ro_data = load_ro()
    f_data = load_foreign_dev()

    ro_res = {}
    f_res = {}
    with open(OUT / "p4_dev_pas.jsonl", "w") as pas_fh:
        for g, subs in RO_GAMES.items():
            ro_res[g] = _evaluate_game(g, subs, ro_data[g], qual, preds, pas_fh)
            ro_res[g]["disagreements_count"] = sum(r["dis"] for r in ro_data[g])
        for g, subs in FOREIGN_GAMES.items():
            recs, meta = f_data[g]
            f_res[g] = _evaluate_game(g, subs, recs, qual, preds, pas_fh)
            f_res[g]["meta_separare"] = meta

    # Holm RO (9 teste)
    pvals_ro = {f"{g}:{X}": ro_res[g]["pred"][X]["p_ville"] for g in RO_GAMES for X in preds}
    holm_ro = holm(pvals_ro, ALPHA)
    cand_ro = sorted(k for k, v in holm_ro["respinse"].items() if v)

    # Holm dezvoltare străină (12 pe jocuri + 3 GLOBAL = 15 teste)
    global_strain = {}
    pvals_f = {f"{g}:{X}": f_res[g]["pred"][X]["p_ville"] for g in FOREIGN_GAMES for X in preds}
    for X in preds:
        gle = sum(f_res[g]["pred"][X]["logE"] for g in FOREIGN_GAMES)
        ge = math.exp(min(700.0, gle))
        pv = min(1.0, math.exp(-gle))
        global_strain[X] = {"logE": gle, "E": ge, "p_ville": pv}
        pvals_f[f"GLOBAL:{X}"] = pv
    holm_f = holm(pvals_f, ALPHA)
    surv_f = sorted(k for k, v in holm_f["respinse"].items() if v)

    verdict_ro = "P4_CANDIDATI_RO" if cand_ro else "P4_NICIUN_CANDIDAT_RO"
    verdict_f = "P4_SUPRAVIETUITORI_DEV_STRAIN" if surv_f else "P4_NICIUN_SUPRAVIETUITOR"

    res = {
        "utc": utc,
        "durata_sec": round(time.time() - t0, 3),
        "protocol_sha256": PROTOCOL_SHA,
        "amendament_v12_01_sha256": AMEND_V12_SHA,
        "code_seal_sha256": sha_f(seal_p),
        "db_ro_sha256": DB_RO_SHA,
        "dev_strain_sha256": DEV_STRAIN_SHA,
        "excluded_p2_games": list(EXCLUDED_P2_GAMES),
        "qualified_families": list(qual),
        "COMB_qualified": comb_ok,
        "predictori": preds,
        "alpha": ALPHA,
        "ro_games": ro_res,
        "holm_ro": holm_ro,
        "candidati_ro": cand_ro,
        "verdict_ro": verdict_ro,
        "foreign_games": f_res,
        "global_strain": global_strain,
        "holm_dev_strain": holm_f,
        "supravietuitori_dev_strain": surv_f,
        "verdict_dev_strain": verdict_f,
        "rezerve_citite": False,
        "positive_claims_allowed": False,
    }
    (OUT / "P4_DEV_REZULTATE.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    (OUT / "RAPORT_P4_DEV_CIFRE.md").write_text(_write_dev_cifre(res) + "\n")
    for fn in ("p4_dev_pas.jsonl", "P4_DEV_REZULTATE.json", "RAPORT_P4_DEV_CIFRE.md"):
        os.chmod(OUT / fn, 0o444)
    print("DEZVOLTARE_P4:", verdict_ro, "|", verdict_f, "supravietuitori_strain:", surv_f)
    print(OUT / "P4_DEV_REZULTATE.json", sha_f(OUT / "P4_DEV_REZULTATE.json"))
    return 0


def cmd_confirmare() -> int:
    if not CONF.exists():
        print("REFUZ: lipsește SIGILIU_CONFIRMARE_P4.json")
        return 2
    conf = json.loads(CONF.read_text())
    surv = conf.get("supravietuitori_dev_strain", [])
    if not surv:
        print("REFUZ: supravietuitori_dev_strain este goală — rezervele rămân SIGILATE și NECITITE.")
        return 2
    if (OUT / "P4_REZ_REZULTATE.json").exists():
        print("REFUZ: confirmarea pe rezervă a fost deja rulată.")
        return 2
    dev_res = json.loads((OUT / "P4_DEV_REZULTATE.json").read_text())
    assert sha_f(OUT / "P4_DEV_REZULTATE.json") == conf["dev_rezultate_sha256"]
    seal = json.loads((HERE / "SIGILIU_COD_P4.json").read_text())
    assert seal["files"]["xi/p4/p4.py"] == sha_f(__file__)
    qual = tuple(seal["qualified_families"])
    preds = dev_res["predictori"]

    need_all = any(k.startswith("GLOBAL:") for k in surv)
    games_to_run = list(FOREIGN_GAMES) if need_all else sorted({k.split(":")[0] for k in surv})
    f_dev = load_foreign_dev()

    games_rez = {}
    for g in games_to_run:
        dev_ext, meta = f_dev[g]
        rb = citeste_date(DATE_P2 / g / "rezerva.json")
        assert sha_b(rb) == meta["rezerva_sha256"], f"sha rezerva {g}"
        rez_doc = json.loads(rb)
        rez_ext = rez_doc["extrageri"]
        Td = len(dev_ext)
        R = len(rez_ext)
        assert R == meta["R"], (g, R, meta["R"])
        subs = FOREIGN_GAMES[g]
        tot_rez = {X: 0.0 for X in preds}
        for lab, n, k in subs:
            H_all = [np.array([x - 1 for x in e["sets"][lab]], dtype=np.int64) for e in dev_ext + rez_ext]
            LP, _, _ = eval_components(H_all, n, k)
            for X in preds:
                _, lr, _, _ = mixture_seq(LP, priors(X, k, qual), n, k)
                tot_rez[X] += float(lr[Td:].sum())
        games_rez[g] = {"Td": Td, "R": R, "logE_rez": tot_rez}

    logE_surv = {}
    pvals = {}
    for key in surv:
        g, X = key.split(":")
        val = sum(games_rez[gg]["logE_rez"][X] for gg in FOREIGN_GAMES) if g == "GLOBAL" else games_rez[g]["logE_rez"][X]
        logE_surv[key] = val
        pvals[key] = min(1.0, math.exp(-val))
    hm = holm(pvals, ALPHA)
    conf_list = sorted(k for k, v in hm["respinse"].items() if v)
    verdict = "CONFIRMAT_PE_ARHIVA" if conf_list else "P4_NECONFIRMAT_PE_REZERVA"
    out = {
        "utc": utcnow(),
        "sigiliu_confirmare_sha256": sha_f(CONF),
        "supravietuitori_testati": surv,
        "games": games_rez,
        "logE_rezerva_supravietuitori": logE_surv,
        "holm": hm,
        "confirmati_pe_arhiva": conf_list,
        "verdict_final": verdict,
        "positive_claims_allowed": False,
    }
    p = OUT / "P4_REZ_REZULTATE.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    os.chmod(p, 0o444)
    print("CONFIRMARE_P4:", verdict, conf_list, p, sha_f(p))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("teste", "dezvoltare", "confirmare"):
        print("Utilizare: p4.py {teste|dezvoltare|confirmare}")
        return 2
    if argv[1] == "teste":
        return cmd_teste()
    if argv[1] == "dezvoltare":
        return cmd_dezvoltare()
    return cmd_confirmare()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
