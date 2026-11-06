"""TU4-FR (S10) — frontiera matematică a abaterii fizice a urnei: 6/49, 5/40, Joker (principal + bilă).

Protocol: tu4/PROTOCOL_TU4_FR.md (sigiliu tu4/SIGILIU_TU4_FR.json). Calcul clasic pe CPU (NumPy + SciPy).
Modelul abaterii fizice: Poisson condiționat P_w(S) = prod_{i in S} w_i / e_k(w) (marginal), legea suprapunerilor
consecutive înclinată față de hipergeometrica exactă (serial), multinomial pe 20 (bila Joker).
NU emite predicții, NU alege bilete. positive_claims_allowed=false.

Utilizare:
  python -B tu4/frontiera.py --martori      # W1–W5 (înainte de arhivele reale) → MARTORI_FR.json
  python -B tu4/frontiera.py --real         # numai după MARTORI PASS → FR_REZULTATE.json (o singură dată)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import itertools
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import chi2

QL = Path(__file__).resolve().parents[1]
OUT = QL / "tu4" / "rezultate" / "FR"
SEAL = QL / "tu4" / "SIGILIU_TU4_FR.json"
GAMES = {
    "649": dict(path=QL.parent / "predictie_numere/probe_date/extrageri_649.jsonl", n=49, k=6, b=6,
                field="numbers_sorted", kind="draw_kind_as_stored", ball=False, seed=2026102701),
    "540": dict(path=QL / "tu3/date/extrageri_540.jsonl", n=40, k=6, b=5, field="numbers", kind="draw_kind",
                ball=False, seed=2026102702),
    "joker": dict(path=QL / "tu3/date/extrageri_joker.jsonl", n=45, k=5, b=5, field="numbers", kind="draw_kind",
                  ball=True, seed=2026102703),
}
NB = 20                      # bila Joker 1..20
R_MC = 10_000
LEVEL = 0.95
ALPHA_COMP = 0.01 / 15
ALPHA_E = 0.01
M_MODELS = 3
K_BLOCKS = 4
FEASIBLE, SLOW, PER_YEAR = 520, 2080, 104


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ Poisson condiționat (exact)
def esym(w: np.ndarray, k: int) -> np.ndarray:
    """e_0..e_k(w) prin recurența standard (exactă în aritmetica float64)."""
    e = np.zeros(k + 1)
    e[0] = 1.0
    for x in w:
        e[1:] = e[1:] + x * e[:-1]
    return e


def incl(w: np.ndarray, k: int) -> np.ndarray:
    """pi_i = w_i e_{k-1}(w_{-i}) / e_k(w)."""
    e = esym(w, k)
    out = np.empty(len(w))
    for i, x in enumerate(w):
        em = np.zeros(k)          # e_j(w_{-i}), j = 0..k-1
        em[0] = 1.0
        for j in range(1, k):
            em[j] = e[j] - x * em[j - 1]
        out[i] = x * em[k - 1] / e[k]
    return out


def kl_cp(w: np.ndarray, k: int) -> float:
    n = len(w)
    p = incl(w, k)
    return float(np.dot(p, np.log(w)) - math.log(esym(w, k)[k]) + math.log(math.comb(n, k)))


def solve_w(f: np.ndarray, k: int, tol: float = 1e-13, itmax: int = 200_000) -> np.ndarray:
    """w cu pi(w) = f (iterația w_i <- w_i f_i / pi_i(w)), normalizat la media geometrică 1."""
    f = np.asarray(f, float)
    if not (np.all(f > 0) and np.all(f < 1) and abs(f.sum() - k) < 1e-9):
        raise ValueError("f în afara domeniului (0,1) cu suma k")
    w = f / (1 - f)
    for _ in range(itmax):
        p = incl(w, k)
        if np.max(np.abs(p - f)) < tol:
            break
        w = w * f / p
        w = w / math.exp(np.mean(np.log(w)))
    else:
        raise RuntimeError("solve_w nu a convergit")
    return w / math.exp(np.mean(np.log(w)))


def suffix_tables(w: np.ndarray, k: int) -> np.ndarray:
    n = len(w)
    E = np.zeros((n + 1, k + 1))
    E[n, 0] = 1.0
    for i in range(n - 1, -1, -1):
        E[i, 0] = 1.0
        E[i, 1:] = E[i + 1, 1:] + w[i] * E[i + 1, :-1]
    return E


def sample_cp(w: np.ndarray, k: int, T: int, rng: np.random.Generator) -> np.ndarray:
    """Eșantionare EXACTĂ din P_w (parcurgere secvențială cu tabelele sufix). Întoarce indicatori T×n (bool)."""
    n = len(w)
    E = suffix_tables(w, k)
    X = np.zeros((T, n), bool)
    r = np.full(T, k)
    for i in range(n):
        act = r > 0
        if not act.any():
            break
        rr = r[act]
        p = w[i] * E[i + 1, rr - 1] / E[i, rr]
        take = rng.random(act.sum()) < p
        idx = np.flatnonzero(act)[take]
        X[idx, i] = True
        r[idx] -= 1
    assert np.all(r == 0)
    return X


def seq_prob(w: np.ndarray, k: int, S: tuple) -> float:
    """Probabilitatea exactă cu care sample_cp produce S (pentru martorul W1)."""
    E = suffix_tables(w, k)
    r, pr = k, 1.0
    for i in range(len(w)):
        if r == 0:
            break
        p = w[i] * E[i + 1, r - 1] / E[i, r]
        if i in S:
            pr *= p
            r -= 1
        else:
            pr *= 1 - p
    return pr


# ------------------------------------------------------------------ date
def load(game: str) -> dict:
    g = GAMES[game]
    rows = [json.loads(line) for line in g["path"].read_text(encoding="utf-8").splitlines() if line.strip()]

    def key(r):
        w = r.get("within_day_sequence")
        return (r["draw_date"], w if isinstance(w, int) else 0, r["draw_key"])

    rows.sort(key=key)
    n, k = g["n"], g["k"]
    X = np.zeros((len(rows), n), bool)
    balls, regular = [], []
    for t, r in enumerate(rows):
        nums = r[g["field"]]
        if len(nums) != k or len(set(nums)) != k or not all(isinstance(x, int) and 1 <= x <= n for x in nums):
            raise ValueError(f"extragere invalidă {r['draw_key']}")
        X[t, np.array(nums) - 1] = True
        if g["ball"]:
            j = r["joker"]
            if not (isinstance(j, int) and 1 <= j <= NB):
                raise ValueError(f"bilă invalidă {r['draw_key']}")
            balls.append(j)
        regular.append(r.get(g["kind"]) == "regular")
    return {"X": X, "balls": np.array(balls, int) if g["ball"] else None, "regular": np.array(regular),
            "sha256": sha(g["path"]), "T": len(rows)}


# ------------------------------------------------------------------ statistici
def x2_marg(counts: np.ndarray, T, n: int, k: int):
    p = k / n
    return (n - 1) / n * np.sum((counts - T * p) ** 2, axis=-1) / (T * p * (1 - p))


def hyper(n: int, k: int) -> np.ndarray:
    return np.array([math.comb(k, o) * math.comb(n - k, k - o) for o in range(k + 1)], float) / math.comb(n, k)


def pooling(h: np.ndarray, N: int) -> list[list[int]]:
    groups = [[o] for o in range(len(h))]
    while len(groups) > 2 and N * sum(h[o] for o in groups[-1]) < 5:
        last = groups.pop()
        groups[-1] = groups[-1] + last
    return groups


def pooled(vec: np.ndarray, groups) -> np.ndarray:
    return np.stack([vec[..., g].sum(-1) for g in groups], -1)


def x2_pearson(obs: np.ndarray, exp: np.ndarray):
    return np.sum((obs - exp) ** 2 / exp, axis=-1)


def overlap_counts(X: np.ndarray, k: int) -> np.ndarray:
    """X: (..., T, n) → numărul de perechi consecutive cu suprapunerea o, o = 0..k."""
    o = np.sum(X[..., 1:, :] & X[..., :-1, :], axis=-1)
    return np.stack([np.sum(o == v, axis=-1) for v in range(k + 1)], -1)


def stats_main(X: np.ndarray, n: int, k: int, groups):
    """Statisticile C1–C4 pentru indicatori X de formă (B, T, n) sau (T, n)."""
    T = X.shape[-2]
    c = X.sum(-2)
    x2m = x2_marg(c, T, n, k)
    oc = pooled(overlap_counts(X, k), groups)
    h = pooled(hyper(n, k), groups)
    x2o = x2_pearson(oc, (T - 1) * h)
    Xf = X.astype(np.float32)
    A = np.matmul(np.swapaxes(Xf, -1, -2), Xf)
    iu = np.triu_indices(n, 1)
    a = A[..., iu[0], iu[1]].astype(np.float64)      # numărări întregi exacte în float32 (< 2^24)
    Ep = T * k * (k - 1) / (n * (n - 1))
    x2p = np.sum((a - Ep) ** 2 / Ep, axis=-1)
    blocks = np.array_split(np.arange(T), K_BLOCKS)
    x2d = sum(x2_marg(X[..., b, :].sum(-2), len(b), n, k) for b in blocks) - x2m
    return {"C1": x2m, "C2": x2o, "C3": x2p, "C4": x2d}


def stats_ball(J: np.ndarray):
    """J: (..., T) bile 1..20."""
    T = J.shape[-1]
    c = np.stack([np.sum(J == v, axis=-1) for v in range(1, NB + 1)], -1)
    x2c = x2_pearson(c, T / NB)
    rep = np.sum(J[..., 1:] == J[..., :-1], axis=-1)
    N = T - 1
    x2s = (rep - N / NB) ** 2 / (N / NB) + ((N - rep) - N * (NB - 1) / NB) ** 2 / (N * (NB - 1) / NB)
    blocks = np.array_split(np.arange(T), K_BLOCKS)
    x2d = 0.0
    for b in blocks:
        cb = np.stack([np.sum(J[..., b] == v, axis=-1) for v in range(1, NB + 1)], -1)
        x2d = x2d + x2_pearson(cb, len(b) / NB)
    return {"B1": x2c, "B2": x2s, "B4": x2d - x2c}


def uniform_batch(rng, B, T, n, k):
    r = rng.random((B, T, n))
    th = np.partition(r, k - 1, axis=2)[..., k - 1:k]
    return r <= th


def monte_carlo(game: str, T: int, R: int, seed: int, batch: int = 40):
    g = GAMES[game]
    n, k = g["n"], g["k"]
    groups = pooling(hyper(n, k), T - 1)
    rng = np.random.default_rng(seed)
    acc: dict[str, list] = {}
    done = 0
    while done < R:
        B = min(batch, R - done)
        st = stats_main(uniform_batch(rng, B, T, n, k), n, k, groups)
        if g["ball"]:
            st.update(stats_ball(rng.integers(1, NB + 1, size=(B, T))))
        for key, v in st.items():
            acc.setdefault(key, []).append(np.asarray(v, float))
        done += B
    return {key: np.concatenate(v) for key, v in acc.items()}


# ------------------------------------------------------------------ frontieră
def kl(p: np.ndarray, q: np.ndarray) -> float:
    m = p > 0
    return float(np.sum(p[m] * np.log(p[m] / q[m])))


def n_learner(D: float, df: int, target: float) -> int:
    if D <= 0:
        return 10 ** 12
    f = lambda N: N * D - df / 2 * math.log(N) - target
    lo, hi = 1, 2
    while f(hi) < 0:
        hi *= 2
        if hi > 10 ** 12:
            return 10 ** 12
    while lo < hi:
        mid = (lo + hi) // 2
        if f(mid) >= 0:
            hi = mid
        else:
            lo = mid + 1
    return lo


def horizon(D: float, df: int) -> dict:
    nl = n_learner(D, df, math.log(100 * M_MODELS))
    tag = "FR_FEZABIL" if nl <= FEASIBLE else ("FR_LENT" if nl <= SLOW else "FR_NEFEZABIL")
    return {"N_oracle_alpha_0.01": math.ceil(math.log(1 / ALPHA_E) / D) if D > 0 else None,
            "N_oracle_alpha_0.01_M3": math.ceil(math.log(100 * M_MODELS) / D) if D > 0 else None,
            "N_learner_M3": nl, "years_learner": round(nl / PER_YEAR, 2), "feasibility": tag}


def frontier_marg(c: np.ndarray, T: int, n: int, k: int, b: int, x2obs: float) -> dict:
    df = n - 1
    q = float(chi2.ppf(LEVEL, df))
    u = k / n
    f = c / T
    scale = 1 + math.sqrt(q / x2obs)
    fs = u + (f - u) * scale
    ws = solve_w(fs, k)
    wh = solve_w(f, k)
    Dmax, Dhat = kl_cp(ws, k), kl_cp(wh, k)
    top = np.sort(fs)[::-1][:b]
    return {"df": df, "q95": q, "scale": scale, "D_hat": Dhat, "D_max": Dmax,
            "D_max_local": (math.sqrt(x2obs) + math.sqrt(q)) ** 2 / (2 * T),
            "pi_star_range": [float(fs.min()), float(fs.max())],
            "oracle_ticket": [int(i) + 1 for i in np.argsort(-fs)[:b]],
            "oracle_expected_hits": float(top.sum()), "uniform_expected_hits": b * k / n,
            "excess_hits": float(top.sum() - b * k / n), "excess_pct": float(100 * (top.sum() / (b * k / n) - 1)),
            "w_star_range": [float(ws.min()), float(ws.max())], **horizon(Dmax, df)}


def frontier_cat(f: np.ndarray, u: np.ndarray, N: int, x2obs: float, df: int) -> dict:
    q = float(chi2.ppf(LEVEL, df))
    scale = 1 + math.sqrt(q / x2obs)
    fs = u + (f - u) * scale
    if np.any(fs <= 0):
        raise ValueError("punctul extrem iese din simplex")
    Dmax = kl(fs, u)
    return {"df": df, "q95": q, "scale": scale, "D_hat": kl(f, u), "D_max": Dmax,
            "D_max_local": (math.sqrt(x2obs) + math.sqrt(q)) ** 2 / (2 * N),
            "f_star": [float(x) for x in fs], **horizon(Dmax, df)}


# ------------------------------------------------------------------ martori
def martori() -> dict:
    res = {"start_utc": utc()}
    # W1
    rng = np.random.default_rng(1)
    w1 = []
    subsets = list(itertools.combinations(range(10), 3))
    for _ in range(5):
        w = np.exp(rng.normal(0, 0.7, 10))
        P = np.array([np.prod(w[list(S)]) for S in subsets])
        Z = P.sum()
        P /= Z
        pi_enum = np.array([sum(P[s] for s, S in enumerate(subsets) if i in S) for i in range(10)])
        kl_enum = float(np.sum(P * np.log(P * math.comb(10, 3))))
        seq = np.array([seq_prob(w, 3, S) for S in subsets])
        w1.append(max(abs(esym(w, 3)[3] - Z) / Z, np.max(np.abs(incl(w, 3) - pi_enum)),
                      abs(kl_cp(w, 3) - kl_enum), np.max(np.abs(seq - P)), abs(incl(w, 3).sum() - 3)))
    res["W1"] = {"max_abs_err": float(max(w1)), "pass": max(w1) <= 1e-12}
    # W2
    rng = np.random.default_rng(11)
    T, n, k = 2595, 49, 6
    groups = pooling(hyper(n, k), T - 1)
    r1 = r2 = 0
    q1 = chi2.ppf(LEVEL, n - 1)
    q2 = chi2.ppf(LEVEL, len(groups) - 1)
    for _ in range(10):
        st = stats_main(uniform_batch(rng, 40, T, n, k), n, k, groups)
        r1 += int(np.sum(st["C1"] > q1))
        r2 += int(np.sum(st["C2"] > q2))
    res["W2"] = {"rate_C1": r1 / 400, "rate_C2": r2 / 400, "pass": 0.02 <= r1 / 400 <= 0.08 and 0.02 <= r2 / 400 <= 0.08}
    # W3
    z = np.random.default_rng(21).normal(0, 1, n)
    w3 = {}
    ok3 = True
    for Dt in (1e-3, 3e-3):
        lo, hi = 0.0, 2.0
        for _ in range(100):
            s = (lo + hi) / 2
            lo, hi = (s, hi) if kl_cp(np.exp(s * z), k) < Dt else (lo, s)
        w = np.exp(s * z)
        Dtrue = kl_cp(w, k)
        wn = w / math.exp(np.mean(np.log(w)))
        rt = float(np.max(np.abs(solve_w(incl(w, k), k) / wn - 1)))
        cover = 0
        rng = np.random.default_rng(31 if Dt == 1e-3 else 32)
        for _ in range(100):
            X = sample_cp(w, k, T, rng)
            c = X.sum(0)
            fr = frontier_marg(c, T, n, k, 6, float(x2_marg(c, T, n, k)))
            cover += int(Dtrue <= fr["D_max"])
        w3[str(Dt)] = {"D_true": Dtrue, "coverage": cover / 100, "roundtrip_rel": rt}
        ok3 &= cover / 100 >= 0.90 and rt <= 1e-8
    res["W3"] = {**w3, "pass": ok3}
    # W4
    h = hyper(n, k)
    lo, hi = 0.0, 3.0
    for _ in range(100):
        beta = (lo + hi) / 2
        p = h * np.exp(beta * np.arange(k + 1))
        p /= p.sum()
        lo, hi = (beta, hi) if kl(p, h) < 3e-3 else (lo, beta)
    hp = pooled(h, groups)
    Dt_pooled = kl(pooled(p, groups), hp)
    rng = np.random.default_rng(41)
    cover = 0
    for _ in range(100):
        X = np.zeros((T, n), bool)
        X[0, rng.choice(n, k, replace=False)] = True
        os_ = rng.choice(k + 1, size=T - 1, p=p)
        for t in range(1, T):
            prev = np.flatnonzero(X[t - 1])
            rest = np.flatnonzero(~X[t - 1])
            o = os_[t - 1]
            X[t, rng.choice(prev, o, replace=False)] = True
            X[t, rng.choice(rest, k - o, replace=False)] = True
        oc = pooled(overlap_counts(X, k), groups)
        x2 = float(x2_pearson(oc, (T - 1) * hp))
        fr = frontier_cat(oc / (T - 1), hp, T - 1, x2, len(groups) - 1)
        cover += int(Dt_pooled <= fr["D_max"])
    res["W4"] = {"D_true_full": kl(p, h), "D_true_pooled": Dt_pooled, "coverage": cover / 100, "pass": cover / 100 >= 0.90}
    # W5
    a = monte_carlo("joker", 300, 50, 7, batch=25)
    b2 = monte_carlo("joker", 300, 50, 7, batch=25)
    res["W5"] = {"pass": all(np.array_equal(a[x], b2[x]) for x in a)}
    res["verdict"] = "MARTORI_PASS" if all(res[w]["pass"] for w in ("W1", "W2", "W3", "W4", "W5")) else "FR_NECALIFICAT"
    res["end_utc"] = utc()
    return res


# ------------------------------------------------------------------ rularea reală
def analyse(game: str) -> dict:
    g = GAMES[game]
    n, k, b = g["n"], g["k"], g["b"]
    d = load(game)
    X, T = d["X"], d["T"]
    groups = pooling(hyper(n, k), T - 1)
    obs = {key: float(v) for key, v in stats_main(X, n, k, groups).items()}
    if g["ball"]:
        obs.update({key: float(v) for key, v in stats_ball(d["balls"]).items()})
    t0 = time.time()
    sims = monte_carlo(game, T, R_MC, g["seed"])
    dfs = {"C1": n - 1, "C2": len(groups) - 1, "C3": None, "C4": (K_BLOCKS - 1) * (n - 1),
           "B1": NB - 1, "B2": 1, "B4": (K_BLOCKS - 1) * (NB - 1)}
    comps = {}
    for key, x in obs.items():
        p_mc = (1 + int(np.sum(sims[key] >= x))) / (R_MC + 1)
        comps[key] = {"X2": x, "df": dfs[key], "p_mc": p_mc,
                      "p_chi2": float(chi2.sf(x, dfs[key])) if dfs[key] else None,
                      "null_mean_mc": float(np.mean(sims[key])),
                      "verdict": "FR_ABATERE_DESCRIPTIVA" if p_mc <= ALPHA_COMP else "FR_COMPATIBIL_UNIFORM"}
    c = X.sum(0)
    fr = {"C1": frontier_marg(c, T, n, k, b, obs["C1"])}
    hp = pooled(hyper(n, k), groups)
    oc = pooled(overlap_counts(X, k), groups)
    fr["C2"] = frontier_cat(oc / (T - 1), hp, T - 1, obs["C2"], len(groups) - 1)
    out = {"game": game, "n": n, "k": k, "ticket": b, "T": T, "source_sha256": d["sha256"],
           "overlap_groups": groups, "overlap_counts": [int(x) for x in oc],
           "counts": [int(x) for x in c], "components": comps, "frontier": fr, "mc_seconds": round(time.time() - t0, 1)}
    if g["ball"]:
        J = d["balls"]
        cb = np.array([np.sum(J == v) for v in range(1, NB + 1)])
        f1 = frontier_cat(cb / T, np.full(NB, 1 / NB), T, obs["B1"], NB - 1)
        f1["oracle_ball"] = int(np.argmax(f1["f_star"])) + 1
        f1["excess_prob"] = float(max(f1["f_star"]) - 1 / NB)
        rep = int(np.sum(J[1:] == J[:-1]))
        fr["B1"] = f1
        fr["B2"] = frontier_cat(np.array([rep, T - 1 - rep]) / (T - 1), np.array([1 / NB, 1 - 1 / NB]), T - 1,
                                obs["B2"], 1)
        out["ball_counts"] = [int(x) for x in cb]
        out["ball_repeats"] = rep
    reg = d["regular"]
    Xr = X[reg]
    out["sensitivity_regular_only"] = {"T": int(reg.sum()),
                                       "C1_X2": float(x2_marg(Xr.sum(0), int(reg.sum()), n, k)),
                                       "C1_p_chi2": float(chi2.sf(x2_marg(Xr.sum(0), int(reg.sum()), n, k), n - 1))}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--martori", action="store_true")
    ap.add_argument("--real", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    if a.martori:
        dst = OUT / "MARTORI_FR.json"
        if dst.exists():
            print("MARTORI_FR.json există deja; refuz suprascrierea.")
            return 2
        res = {"protocol": "TU4-FR", "seal_sha256": sha(SEAL), "code_sha256": sha(Path(__file__)), **martori()}
        dst.write_text(json.dumps(res, indent=1) + "\n")
        os.chmod(dst, 0o444)
        print(json.dumps({k: res[k] for k in ("W1", "W2", "W3", "W4", "W5", "verdict")}, indent=1))
        return 0 if res["verdict"] == "MARTORI_PASS" else 1
    if a.real:
        mart = OUT / "MARTORI_FR.json"
        dst = OUT / "FR_REZULTATE.json"
        if not mart.exists() or json.loads(mart.read_text())["verdict"] != "MARTORI_PASS":
            print("Martorii nu sunt PASS; rularea reală este interzisă.")
            return 2
        if dst.exists():
            print("FR_REZULTATE.json există deja; rularea reală este unică.")
            return 2
        for p, v in seal["sources"].items():
            if sha(QL / p) != v:
                raise SystemExit(f"sursa {p} diferă de sigiliu")
        res = {"protocol": "TU4-FR", "seal_sha256": sha(SEAL), "code_sha256": sha(Path(__file__)),
               "martori_sha256": sha(mart), "start_utc": utc(), "games": {}}
        for game in GAMES:
            print(f"[frontiera] {game} …", flush=True)
            res["games"][game] = analyse(game)
            gg = res["games"][game]
            print(f"[frontiera] {game}: " + ", ".join(f"{k} p={v['p_mc']:.4f}" for k, v in gg["components"].items())
                  + f" | C1 D_max={gg['frontier']['C1']['D_max']:.3e} N={gg['frontier']['C1']['N_learner_M3']}", flush=True)
        res["end_utc"] = utc()
        res["positive_claims_allowed"] = False
        dst.write_text(json.dumps(res, indent=1) + "\n")
        os.chmod(dst, 0o444)
        print(f"[frontiera] scris {dst.name} {sha(dst)}")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
