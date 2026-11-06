"""WU649 — „Urna ponderată”: cursa exponențială Luce cu ordinea nevăzută marginalizată exact.

Protocol: PREINREGISTRARE_WU649.md (WU649-P1), sigilat în SIGILIU_PROTOCOL_WU649.json ÎNAINTE
de acest cod; Amendamentul 01 (toleranța de zgomot Armijo) sigilat tot înainte de cod.
Calcul clasic: NumPy float64 (CPU, procese paralele pe pași independenți) + certificate în Q
(fractions.Fraction). Nu importă și nu rulează modele închise (QL649 engine/validare, BO649,
DL etc.); folosește doar `parser.py` din QL649 pentru ingestie (§1).

Comenzi:
  --qualify          Q1–Q6 (date construite/sintetice; arhiva NU este citită) -> rezultate/CALIFICARE.json
  --real             backtest unic pe arhivă (refuză dacă START.json există sau calificarea lipsește)
  --null M           descriptiv: M universuri nule sintetice -> rezultate/nule/SUMAR.json
  --sens             descriptiv: σ ∈ {0.05, 0.2, 0.8} -> rezultate/SENSIBILITATE.json
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"  # Amendamentul 01: BLAS cu un singur fir în fiecare proces (determinism bit cu bit)

import datetime as dt
import hashlib
import itertools
import json
import math
import multiprocessing as mp
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
QL = HERE.parent
OUT = HERE / "rezultate"
PROTO = HERE / "PREINREGISTRARE_WU649.md"
SEAL = HERE / "SIGILIU_PROTOCOL_WU649.json"
AMEND = HERE / "AMENDAMENT_01.md"
AMEND_SEAL = HERE / "SIGILIU_AMENDAMENT_01.json"

N49, K6 = 49, 6
SIGMA = 0.2
WARMUP = 100
HALF_LIFE = 26.0
LAM0, QEPS = 0.5, 1e-4
H_Q, K_Q = 1.0 / 16.0, 64          # tanh-sinh, 129 noduri
H_Q2, K_Q2 = 1.0 / 32.0, 128       # certificat de precizie, 257 noduri
GTOL, MAXIT = 1e-8, 200
ARM_C, ARM_MAX, TAU = 1e-4, 60, 1e-10
SENS_SIGMAS = (0.05, 0.2, 0.8)
NWORKERS = max(1, min(22, (os.cpu_count() or 2) - 2))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Cuadratura tanh-sinh pe (0,1)
# ---------------------------------------------------------------------------
def ts_nodes(h: float, K: int) -> tuple[np.ndarray, np.ndarray]:
    """(log x_k, log pondere_k) pentru x_k = 1/(1+e^{-π sinh t_k}), t_k = k h, |k| ≤ K."""
    t = np.arange(-K, K + 1, dtype=np.float64) * h
    s = math.pi * np.sinh(t)
    logx = -np.logaddexp(0.0, -s)
    log1mx = -np.logaddexp(0.0, s)
    logw = math.log(h * math.pi) + np.log(np.cosh(t)) + logx + log1mx
    return logx, logw


NODES = ts_nodes(H_Q, K_Q)
NODES2 = ts_nodes(H_Q2, K_Q2)


def _logsumexp(a: np.ndarray, axis: int) -> np.ndarray:
    m = a.max(axis=axis, keepdims=True)
    return (m + np.log(np.exp(a - m).sum(axis=axis, keepdims=True))).squeeze(axis)


# ---------------------------------------------------------------------------
# Verosimilitatea (forma 3'), gradient și hessiană analitice în θ
# ---------------------------------------------------------------------------
def draw_terms(theta: np.ndarray, mem: np.ndarray, nonmem: np.ndarray, nodes=NODES, deriv: bool = True) -> dict:
    """mem: [n,κ] indici membri; nonmem: [n,N] 1.0 pentru ne-membri. Întoarce log P pe extragere
    și, dacă deriv, gradientul și hessiana totale (fără prior)."""
    logx, logw = nodes
    w = np.exp(theta)
    N = theta.shape[0]
    wn = nonmem * w[None, :]
    Wc = wn.sum(1)                                   # [n]
    r = w[mem] / Wc[:, None]                         # [n,κ]
    rL = r[:, :, None] * logx[None, None, :]         # [n,κ,M]
    om = -np.expm1(rL)                               # 1 - x^r
    la = np.log(om).sum(1) + logw[None, :]           # [n,M]
    logP = _logsumexp(la, 1)                         # [n]
    out = {"logP": logP}
    if not deriv:
        return out
    rho = np.exp(la - logP[:, None])                 # [n,M], Σ_m = 1
    v = np.exp(rL)
    L = logx[None, None, :]
    b = -L * v / om
    c = -(L * L) * v / (om * om)
    Eb = np.einsum("nm,nim->ni", rho, b)
    Ec = np.einsum("nm,nim->ni", rho, c)
    Ebb = np.einsum("nm,nim,njm->nij", rho, b, b)
    e = r * Eb                                       # ∂logP/∂d_i
    Hd = r[:, :, None] * r[:, None, :] * (Ebb - Eb[:, :, None] * Eb[:, None, :])
    idx = np.arange(mem.shape[1])
    Hd[:, idx, idx] += r * r * Ec + r * Eb
    g7 = -e.sum(1)                                   # ∂logP/∂z7, z7 = log Wc
    h7 = -Hd.sum(2)                                  # H_z[i,7]
    h77 = Hd.sum((1, 2))                             # H_z[7,7]
    rho_l = wn / Wc[:, None]                         # [n,N], softmax pe ne-membri
    n = mem.shape[0]
    grad = np.bincount(mem.ravel(), weights=e.ravel(), minlength=N) + (g7[:, None] * rho_l).sum(0)
    flat = (mem[:, :, None] * N + mem[:, None, :]).ravel()
    H = np.bincount(flat, weights=Hd.ravel(), minlength=N * N).reshape(N, N)
    A = np.zeros((n, N))
    A[np.arange(n)[:, None], mem] = h7
    C = A.T @ rho_l
    H += C + C.T
    H += (rho_l * (h77 - g7)[:, None]).T @ rho_l
    H[np.arange(N), np.arange(N)] += (g7[:, None] * rho_l).sum(0)
    out.update({"grad": grad, "H": H})
    return out


def posterior_eval(theta, mem, nonmem, sigma, nodes=NODES, deriv=True) -> dict:
    d = draw_terms(theta, mem, nonmem, nodes, deriv)
    s2 = sigma * sigma
    d["lp"] = float(d["logP"].sum() - (theta @ theta) / (2 * s2))
    if deriv:
        d["g"] = d["grad"] - theta / s2
        d["Hp"] = d["H"] - np.eye(theta.shape[0]) / s2
    return d


def _chol_ok(A: np.ndarray) -> bool:
    try:
        np.linalg.cholesky(A)
        return True
    except np.linalg.LinAlgError:
        return False


def map_fit(mem, nonmem, N: int, sigma: float = SIGMA, theta0=None, nodes=NODES) -> dict:
    """MAP Newton–Levenberg cu backtracking Armijo (Amendamentul 01). Pornire implicită θ=0."""
    theta = np.zeros(N) if theta0 is None else np.array(theta0, dtype=np.float64)
    s2 = sigma * sigma
    ev = posterior_eval(theta, mem, nonmem, sigma, nodes)
    it, fail = 0, ""
    while True:
        gnorm = float(np.abs(ev["g"]).max())
        if gnorm <= GTOL:
            break
        if it >= MAXIT:
            fail = "maxit"
            break
        A = -ev["Hp"]
        mu = 0.0
        if not _chol_ok(A):
            mu = 1e-6 * float(np.abs(ev["Hp"]).max())
            while not _chol_ok(A + mu * np.eye(N)):
                mu *= 2.0
        delta = np.linalg.solve(A + mu * np.eye(N), ev["g"])
        gd = float(ev["g"] @ delta)
        step, acc = 1.0, False
        for _ in range(ARM_MAX):
            th_n = theta + step * delta
            ev_n = posterior_eval(th_n, mem, nonmem, sigma, nodes)
            diff = float((ev_n["logP"] - ev["logP"]).sum() - (th_n @ th_n - theta @ theta) / (2 * s2))
            if diff >= ARM_C * step * gd - TAU:
                acc = True
                break
            step *= 0.5
        if not acc:
            fail = "armijo"
            break
        theta, ev = th_n, ev_n
        it += 1
    gnorm = float(np.abs(ev["g"]).max())
    nd = _chol_ok(-ev["Hp"])
    return {"theta": theta, "iters": it, "gnorm": gnorm, "nd": nd, "cert": bool(gnorm <= GTOL and nd),
            "lp": ev["lp"], "fail": fail}


# ---------------------------------------------------------------------------
# Probabilitatea de includere π_j(w) (substituția v = u^{w_j})
# ---------------------------------------------------------------------------
def inclusion(theta: np.ndarray, kappa: int, nodes=NODES) -> np.ndarray:
    logx, logw = nodes
    N = theta.shape[0]
    a = np.exp(theta[None, :] - theta[:, None])      # a[j,l] = w_l / w_j
    aL = a[:, :, None] * logx[None, None, :]         # [N,N,M]
    p = -np.expm1(aL)                                # sosit
    s = np.exp(aL)                                   # nesosit
    j = np.arange(N)
    p[j, j, :] = 0.0
    s[j, j, :] = 1.0
    M = logx.shape[0]
    P = np.zeros((N, M, kappa))
    P[:, :, 0] = 1.0
    for l in range(N):
        pl, sl = p[:, l, :][:, :, None], s[:, l, :][:, :, None]
        newP = P * sl
        newP[:, :, 1:] += P[:, :, :-1] * pl
        P = newP
    G = P.sum(-1)                                    # P(N_{-j} ≤ κ-1)
    return G @ np.exp(logw)


# ---------------------------------------------------------------------------
# Rularea walk-forward (paralel pe pași independenți)
# ---------------------------------------------------------------------------
_G: dict = {}


def _prep(steps: list[np.ndarray]):
    D = np.concatenate(steps, 0)
    off = np.concatenate([[0], np.cumsum([s.shape[0] for s in steps])]).astype(np.int64)
    mem = np.sort(np.argsort(-D, axis=1, kind="stable")[:, :int(D[0].sum())], axis=1)
    return D, off, mem


def fit_prefix(D, off, mem, k: int, sigma: float, nodes=NODES) -> dict:
    n = int(off[k])
    m = mem[:n]
    nonmem = 1.0 - D[:n]
    f = map_fit(m, nonmem, D.shape[1], sigma, nodes=nodes)
    f["q"] = inclusion(f["theta"], m.shape[1], nodes)
    return f


def _worker(k: int):
    f = fit_prefix(_G["D"], _G["off"], _G["mem"], k, _G["sigma"])
    return k, f["theta"], f["q"], f["iters"], f["gnorm"], f["nd"], f["cert"], f["lp"], f["fail"]


def run_steps(steps: list[np.ndarray], ks: np.ndarray, sigma: float = SIGMA, workers: int = NWORKERS) -> dict:
    D, off, mem = _prep(steps)
    _G.update({"D": D, "off": off, "mem": mem, "sigma": sigma})
    res = {}
    if workers <= 1:
        for k in ks:
            r = _worker(int(k))
            res[r[0]] = r
    else:
        ctx = mp.get_context("fork")
        with ctx.Pool(workers) as pool:
            for r in pool.imap_unordered(_worker, [int(k) for k in ks[::-1]], chunksize=2):
                res[r[0]] = r
    rows = [res[int(k)] for k in ks]
    return {"ks": np.asarray(ks, dtype=np.int64), "theta": np.stack([r[1] for r in rows]),
            "q": np.stack([r[2] for r in rows]), "iters": np.array([r[3] for r in rows]),
            "gnorm": np.array([r[4] for r in rows]), "nd": np.array([r[5] for r in rows]),
            "cert": np.array([r[6] for r in rows]), "lp": np.array([r[7] for r in rows]),
            "fail": [r[8] for r in rows]}


# ---------------------------------------------------------------------------
# Comparatori, legi marginale, scoruri (definiții QL649 §5 / BO649 §3, reimplementate aici)
# ---------------------------------------------------------------------------
def marginal_q(pi: np.ndarray) -> np.ndarray:
    base = 6.0 / N49
    d = 6.0 * pi - base
    with np.errstate(divide="ignore", invalid="ignore"):
        up = np.where(d > 0, (1 - QEPS - base) / d, np.inf)
        dn = np.where(d < 0, (base - QEPS) / (-d), np.inf)
    lam = np.minimum(LAM0, np.minimum(up.min(-1), dn.min(-1)))[..., None]
    return base + lam * d


def top6(score: np.ndarray) -> np.ndarray:
    order = np.argsort(-score, axis=-1, kind="stable")
    return np.sort(order[..., :K6] + 1, -1)


def comparators(steps: list[np.ndarray], ks: np.ndarray) -> dict:
    S = np.stack([s.sum(0) for s in steps])
    P = np.vstack((np.zeros((1, S.shape[1])), np.cumsum(S, 0)))
    c = P[ks]
    K = S.shape[0]
    sidx = np.arange(K)
    W = np.where(sidx[None, :] < ks[:, None], 2.0 ** (-(ks[:, None] - 1 - sidx[None, :]) / HALF_LIFE), 0.0)
    ew = W @ S
    piB = (c + 1.0) / (c + 1.0).sum(-1, keepdims=True)
    piR = (ew + 0.5) / (ew + 0.5).sum(-1, keepdims=True)
    return {"piB": piB, "piR": piR, "counts": c}


def score_block(q, ticket, y) -> dict:
    out = {"log": (y * np.log(q) + (1 - y) * np.log(1 - q)).sum(-1), "brier": ((q - y) ** 2).sum(-1)}
    if ticket is not None:
        out["hits"] = np.take_along_axis(y, ticket - 1, axis=1).sum(-1)
    return out


def hyper_pmf() -> np.ndarray:
    return np.array([math.comb(6, i) * math.comb(43, 6 - i) / math.comb(49, 6) for i in range(7)])


def exact_tail(total_hits: int, n: int) -> float:
    pmf = hyper_pmf()
    dist = np.array([1.0])
    for _ in range(n):
        dist = np.convolve(dist, pmf)
    return float(dist[total_hits:].sum())


def gates(t: dict, h1: dict, h2: dict) -> list[dict]:
    g = [
        ("1", "ExcesWU/U >= 0.20", t["excess_WU"] >= 0.20, t["excess_WU"]),
        ("2", "hitsWU > hitsB și hitsWU > hitsR", t["hits_WU"] > t["hits_B"] and t["hits_WU"] > t["hits_R"],
         [t["hits_WU"], t["hits_B"], t["hits_R"]]),
        ("3", "logWU−logU > 0 și logWU−logB > 0", t["log_WU"] - t["log_U"] > 0 and t["log_WU"] - t["log_B"] > 0,
         [t["log_WU"] - t["log_U"], t["log_WU"] - t["log_B"]]),
        ("4", "BrierWU < BrierU, BrierB, BrierR", t["brier_WU"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
         [t["brier_WU"], t["brier_U"], t["brier_B"], t["brier_R"]]),
        ("5", "ambele jumătăți: exces > 0 și hitsWU−hitsB > 0",
         all(h["excess_WU"] > 0 and h["hits_WU"] - h["hits_B"] > 0 for h in (h1, h2)),
         [[h["excess_WU"], h["hits_WU"] - h["hits_B"]] for h in (h1, h2)]),
        ("6", "ambele jumătăți: logWU−logB > 0", all(h["log_WU"] - h["log_B"] > 0 for h in (h1, h2)),
         [h["log_WU"] - h["log_B"] for h in (h1, h2)]),
    ]
    return [{"gate": a, "rule": b, "pass": bool(c), "value": d} for a, b, c, d in g]


def summarize(sl: slice, S: dict) -> dict:
    n = int(S["y"][sl].shape[0])
    o = {"targets": n}
    for name in ("WU", "B", "R"):
        o[f"hits_{name}"] = int(S[f"hits_{name}"][sl].sum())
        o[f"excess_{name}"] = o[f"hits_{name}"] / n - 36.0 / 49.0 if n else 0.0
    for name in ("WU", "B", "R", "U"):
        o[f"log_{name}"] = float(S[f"log_{name}"][sl].sum())
        o[f"brier_{name}"] = float(S[f"brier_{name}"][sl].sum())
    return o


def targets_of(steps, warmup):
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    t_step = np.concatenate([np.full(steps[k].shape[0], k, dtype=np.int64) for k in ks])
    y = np.concatenate([steps[k] for k in ks]).astype(np.float64)
    return ks, t_step, y


def predict(steps: list[np.ndarray], sigma: float = SIGMA, warmup: int = WARMUP, workers: int = NWORKERS) -> dict:
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    r = run_steps(steps, ks, sigma, workers)
    cmp_ = comparators(steps, ks)
    return {"ks": ks, "theta": r["theta"], "q_WU": r["q"], "ticket_WU": top6(r["q"]), "piB": cmp_["piB"],
            "piR": cmp_["piR"], "ticket_B": top6(cmp_["piB"]), "ticket_R": top6(cmp_["piR"]),
            "iters": r["iters"], "gnorm": r["gnorm"], "nd": r["nd"], "cert": r["cert"], "lp": r["lp"],
            "fail": np.array(r["fail"])}


def score(steps: list[np.ndarray], pred: dict, warmup: int = WARMUP) -> dict:
    ks, t_step, y = targets_of(steps, warmup)
    assert np.array_equal(ks, pred["ks"])
    row = t_step - warmup
    laws = {"WU": marginal_q(pred["q_WU"] / K6), "B": marginal_q(pred["piB"]), "R": marginal_q(pred["piR"])}
    tick = {"WU": pred["ticket_WU"], "B": pred["ticket_B"], "R": pred["ticket_R"]}
    S = {"y": y}
    for name in ("WU", "B", "R"):
        sb = score_block(laws[name][row], tick[name][row], y)
        S[f"hits_{name}"], S[f"log_{name}"], S[f"brier_{name}"] = sb["hits"], sb["log"], sb["brier"]
    sU = score_block(np.full_like(y, 6.0 / N49), None, y)
    S["log_U"], S["brier_U"] = sU["log"], sU["brier"]
    n = y.shape[0]
    half = n // 2
    t, h1, h2 = summarize(slice(0, n), S), summarize(slice(0, half), S), summarize(slice(half, n), S)
    g = gates(t, h1, h2)
    passed = sum(x["pass"] for x in g)
    tW = tick["WU"]
    return {
        "n_targets": int(n), "n_steps_predicted": int(ks.shape[0]), "total": t, "half1": h1, "half2": h2,
        "gates": g, "gates_passed": int(passed),
        "verdict": "WU_PROMOVAT_EXPLORATORIU" if passed == 6 else "WU_NO_PROMOTION_EXPLORATORY",
        "tickets_changed_vs_B_steps": int((tW != tick["B"]).any(-1).sum()),
        "tickets_changed_vs_R_steps": int((tW != tick["R"]).any(-1).sum()),
        "tickets_changed_vs_B_targets": int((tW[row] != tick["B"][row]).any(-1).sum()),
        "tickets_changed_vs_R_targets": int((tW[row] != tick["R"][row]).any(-1).sum()),
        "match_dist_WU": np.bincount(S["hits_WU"].astype(int), minlength=7).tolist(),
        "match_expected_U": (hyper_pmf() * n).tolist(),
        "sum_q_max_abs_err": float(np.abs(pred["q_WU"].sum(-1) - K6).max()),
        "certificates": {"all_cert": bool(np.all(pred["cert"])), "n_uncert": int((~pred["cert"].astype(bool)).sum()),
                         "gnorm_max": float(pred["gnorm"].max()), "iters_max": int(pred["iters"].max()),
                         "iters_mean": float(pred["iters"].mean())},
        "theta_sd_last": float(pred["theta"][-1].std()),
        "per_target": {"step": t_step.tolist(), "hits_WU": S["hits_WU"].astype(int).tolist(),
                       "log_WU": S["log_WU"].tolist()},
    }


# ---------------------------------------------------------------------------
# Date: arhiva reală (prin parser QL649) și universuri sintetice
# ---------------------------------------------------------------------------
def load_real():
    sys.path.insert(0, str(QL))
    import parser as P  # noqa: E402  (ingestie QL649 §1; nu este model)
    ds = P.build_dataset(device="cpu")
    oh = ds.onehot.numpy().astype(np.float64)
    off = ds.step_offsets.numpy()
    steps = [oh[off[s]:off[s + 1]] for s in range(len(off) - 1)]
    meta = {"source": ds.source, "source_sha256": ds.source_sha256, "n_draws": ds.n_draws, "n_steps": ds.n_steps,
            "parser_sha256": sha256_file(QL / "parser.py"), "first_date": ds.step_dates[0],
            "last_date": ds.step_dates[-1]}
    return steps, meta


def real_step_sizes() -> np.ndarray:
    """Structura pașilor (numărul de extrageri pe zi) — inventar, fără numere extrase."""
    sys.path.insert(0, str(QL))
    import parser as P  # noqa: E402
    recs, _ = P.load_records(P.DEFAULT_SOURCE)
    clean, _ = P.clean_records(recs)
    dates = [r["draw_date"] for r in clean]
    sizes = []
    for i, d in enumerate(dates):
        if i == 0 or d != dates[i - 1]:
            sizes.append(1)
        else:
            sizes[-1] += 1
    return np.array(sizes, dtype=np.int64)


def synthetic_steps(sizes: np.ndarray, seed) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    out = []
    for sz in sizes:
        a = np.zeros((int(sz), N49))
        for i in range(int(sz)):
            a[i, rng.choice(N49, K6, replace=False)] = 1.0
        out.append(a)
    return out


# ---------------------------------------------------------------------------
# Certificate exacte în Q (Q1)
# ---------------------------------------------------------------------------
def p_order_exact(S, w):
    W = sum(w)
    tot = Fraction(0)
    for perm in itertools.permutations(S):
        pr, rem = Fraction(1), W
        for i in perm:
            pr *= w[i] / rem
            rem -= w[i]
        tot += pr
    return tot


def ie_parts_exact(S, w):
    """P, ∂P/∂w_i (i∈S), ∂P/∂Wc, ∂²P/∂w_i∂w_k, ∂²P/∂w_i∂Wc, ∂²P/∂Wc² — exact, din forma 2."""
    k = len(S)
    Wc = sum(w[l] for l in range(len(w)) if l not in S)
    P = Fraction(0)
    dP = [Fraction(0)] * k
    dW = Fraction(0)
    d2 = [[Fraction(0)] * k for _ in range(k)]
    d2W = [Fraction(0)] * k
    dWW = Fraction(0)
    for mask in range(1 << k):
        A = [a for a in range(k) if mask >> a & 1]
        sg = -1 if len(A) % 2 else 1
        wA = sum((w[S[a]] for a in A), Fraction(0))
        den = Wc + wA
        P += sg * Wc / den
        dW += sg * wA / den ** 2
        dWW += sg * (-2 * wA) / den ** 3
        for a in A:
            dP[a] += sg * (-Wc) / den ** 2
            d2W[a] += sg * (-(wA - Wc)) / den ** 3
            for b in A:
                d2[a][b] += sg * 2 * Wc / den ** 3
    return P, dP, dW, d2, d2W, dWW


def logp_grad_hess_exact(S, w):
    """Gradientul și hessiana lui log P(S) în θ = log w, exact în Q."""
    N = len(w)
    P, dP, dW, d2, d2W, dWW = ie_parts_exact(S, w)
    pos = {s: a for a, s in enumerate(S)}

    def Pw(a):
        return dP[pos[a]] if a in pos else dW

    def Pww(a, b):
        if a in pos and b in pos:
            return d2[pos[a]][pos[b]]
        if a in pos:
            return d2W[pos[a]]
        if b in pos:
            return d2W[pos[b]]
        return dWW

    g = [w[a] * Pw(a) / P for a in range(N)]
    H = [[(w[a] * w[b] * Pww(a, b) + (w[a] * Pw(a) if a == b else 0)) / P - g[a] * g[b] for b in range(N)]
         for a in range(N)]
    return P, g, H


def luce_sample(rng, w: np.ndarray, kappa: int) -> list[int]:
    rem = list(range(len(w)))
    out = []
    for _ in range(kappa):
        p = w[rem] / w[rem].sum()
        i = int(rng.choice(len(rem), p=p))
        out.append(rem.pop(i))
    return sorted(out)


def _mem_nonmem(sets: list[list[int]], N: int):
    mem = np.array(sets, dtype=np.int64)
    nonmem = np.ones((len(sets), N))
    nonmem[np.arange(len(sets))[:, None], mem] = 0.0
    return mem, nonmem


def q1_exact() -> dict:
    rng = np.random.default_rng([649, 8, 1])
    combos = [(N, k) for N in (4, 5, 6) for k in (2, 3) if k < N]
    worst = {"rel_P": 0.0, "abs_pi": 0.0, "grad": 0.0, "hess": 0.0, "multistart_dtheta": 0.0}
    ok = {"order_eq_ie": True, "sum_one": True, "sum_pi_kappa": True, "multistart_cert": True}
    n_inst, n_sets = 0, 0
    for it in range(42):
        N, k = combos[it % len(combos)]
        a = rng.integers(1, 10, size=N)
        bden = rng.integers(1, 5, size=N)
        w = [Fraction(int(x), int(y)) for x, y in zip(a, bden)]
        theta = np.log(np.array([float(x) for x in w]))
        sets = [list(S) for S in itertools.combinations(range(N), k)]
        Pex = {}
        tot = Fraction(0)
        for S in sets:
            p1 = p_order_exact(S, w)
            P, g, H = logp_grad_hess_exact(S, w)
            ok["order_eq_ie"] &= (p1 == P)
            tot += P
            Pex[tuple(S)] = P
            mem, nonmem = _mem_nonmem([S], N)
            d = draw_terms(theta, mem, nonmem)
            worst["rel_P"] = max(worst["rel_P"], abs(math.exp(d["logP"][0]) - float(P)) / float(P))
            gf = np.array([float(x) for x in g])
            Hf = np.array([[float(x) for x in row] for row in H])
            worst["grad"] = max(worst["grad"], float((np.abs(d["grad"] - gf) / np.maximum(1, np.abs(gf))).max()))
            worst["hess"] = max(worst["hess"], float((np.abs(d["H"] - Hf) / np.maximum(1, np.abs(Hf))).max()))
            n_sets += 1
        ok["sum_one"] &= (tot == 1)
        piex = [sum((Pex[tuple(S)] for S in sets if j in S), Fraction(0)) for j in range(N)]
        ok["sum_pi_kappa"] &= (sum(piex) == k)
        pif = inclusion(theta, k)
        worst["abs_pi"] = max(worst["abs_pi"], float(np.abs(pif - np.array([float(x) for x in piex])).max()))
        # MAP multi-start pe o istorie Luce mică
        T = int(rng.integers(8, 21))
        hist = [luce_sample(rng, np.exp(theta), k) for _ in range(T)]
        mem, nonmem = _mem_nonmem(hist, N)
        fits = [map_fit(mem, nonmem, N)]
        for _ in range(7):
            fits.append(map_fit(mem, nonmem, N, theta0=rng.normal(0, 1, N)))
        ok["multistart_cert"] &= all(f["cert"] for f in fits)
        th0 = fits[0]["theta"]
        worst["multistart_dtheta"] = max(worst["multistart_dtheta"],
                                         max(float(np.abs(f["theta"] - th0).max()) for f in fits))
        n_inst += 1
    passed = (all(ok.values()) and n_inst >= 40 and worst["rel_P"] <= 1e-12 and worst["abs_pi"] <= 1e-12
              and worst["grad"] <= 1e-10 and worst["hess"] <= 1e-10 and worst["multistart_dtheta"] <= 1e-8)
    return {"id": "Q1", "name": "exactitate în Q + multi-start", "pass": bool(passed),
            "detail": {"instances": n_inst, "sets": n_sets, **ok, **worst}}


# ---------------------------------------------------------------------------
# Fixture Q5/Q6
# ---------------------------------------------------------------------------
def fixture_hplus() -> list[np.ndarray]:
    rest = list(range(8, 50))
    steps = []
    for i in range(400):
        beta = [7] + [rest[(5 * i + m) % 42] for m in range(5)]
        gamma = [rest[(6 * i + m + 21) % 42] for m in range(6)]
        alpha = [1, 2, 3, 4, 5, 6]
        for S in (beta, gamma, alpha):
            a = np.zeros((1, N49))
            a[0, np.array(S) - 1] = 1.0
            steps.append(a)
    return steps


def swap_labels(steps, i: int, j: int):
    out = []
    for s in steps:
        t = s.copy()
        t[:, [i - 1, j - 1]] = t[:, [j - 1, i - 1]]
        out.append(t)
    return out


def next_prediction(steps: list[np.ndarray], sigma: float = SIGMA) -> dict:
    D, off, mem = _prep(steps)
    f = fit_prefix(D, off, mem, len(steps), sigma)
    k = np.array([len(steps)])
    ext = steps + [np.zeros((1, N49))]
    c = comparators(ext, k)
    return {"theta": f["theta"], "q_WU": f["q"], "cert": f["cert"], "gnorm": f["gnorm"], "piB": c["piB"][0],
            "piR": c["piR"][0], "t_WU": top6(f["q"]), "t_B": top6(c["piB"][0]), "t_R": top6(c["piR"][0]),
            "counts": c["counts"][0]}


# ---------------------------------------------------------------------------
# Calificare Q1–Q6
# ---------------------------------------------------------------------------
def qualify() -> dict:
    t0 = time.time()
    checks = [q1_exact()]
    print(f"Q1 {checks[-1]['pass']} {checks[-1]['detail']} ({time.time() - t0:.0f}s)", flush=True)

    # Q2: univers nul sintetic complet
    sizes = real_step_sizes()
    st = synthetic_steps(sizes, [649, 8, 999])
    t1 = time.time()
    pred = predict(st)
    t_run = time.time() - t1
    q = pred["q_WU"]
    sums = float(np.abs(q.sum(-1) - K6).max())
    inside = bool(((q > 0) & (q < 1)).all())
    sum_theta = float(np.abs(pred["theta"].sum(-1)).max())
    D, off, mem = _prep(st)
    sample = np.arange(0, len(pred["ks"]), 97)
    dq2, g2 = 0.0, 0.0
    for i in sample:
        k = int(pred["ks"][i])
        th = pred["theta"][i]
        q_fine = inclusion(th, K6, NODES2)
        dq2 = max(dq2, float(np.abs(q_fine - q[i]).max()))
        ev = posterior_eval(th, mem[:off[k]], 1.0 - D[:off[k]], SIGMA, NODES2)
        g2 = max(g2, float(np.abs(ev["g"]).max()))
    q2 = (sums <= 1e-10 and inside and bool(pred["cert"].all()) and sum_theta <= 1e-7 and dq2 <= 1e-11)
    checks.append({"id": "Q2", "name": "identități pe univers nul complet", "pass": bool(q2),
                   "detail": {"steps": int(len(pred["ks"])), "sum_q_max_err": sums, "q_in_01": inside,
                              "all_cert": bool(pred["cert"].all()), "n_uncert": int((~pred["cert"]).sum()),
                              "gnorm_max": float(pred["gnorm"].max()), "iters_max": int(pred["iters"].max()),
                              "iters_mean": float(pred["iters"].mean()), "sum_theta_max": sum_theta,
                              "fine_nodes_max_dq_same_theta": dq2, "fine_nodes_gnorm_max": g2,
                              "fine_sample_steps": int(len(sample)), "run_seconds": t_run,
                              "note": "Precizia cuadraturii: q și gradientul cu h=1/32 la același θ̂ (§4 Q2)."}})
    print(f"Q2 {checks[-1]['pass']} {checks[-1]['detail']}", flush=True)

    # Q3: cauzalitate — istorie trunchiată, bit cu bit
    eq = True
    for i in sample:
        k = int(pred["ks"][i])
        Dk, offk, memk = _prep(st[:k])
        f = fit_prefix(Dk, offk, memk, k, SIGMA)
        eq &= bool(np.array_equal(f["theta"], pred["theta"][i]) and np.array_equal(f["q"], q[i]))
    checks.append({"id": "Q3", "name": "cauzalitate (trunchiat ≡ complet, bit cu bit)", "pass": bool(eq),
                   "detail": {"sampled_steps": int(len(sample))}})
    print(f"Q3 {checks[-1]['pass']}", flush=True)

    # Q4: echivarianță la permutarea etichetelor
    perm = np.random.default_rng([649, 8, 4]).permutation(N49)
    stp = []
    for s in st:
        t = np.zeros_like(s)
        t[:, perm] = s
        stp.append(t)
    Dp, offp, memp = _prep(stp)
    dperm = 0.0
    for i in sample:
        k = int(pred["ks"][i])
        f = fit_prefix(Dp, offp, memp, k, SIGMA)
        dperm = max(dperm, float(np.abs(f["q"][perm] - q[i]).max()))
    checks.append({"id": "Q4", "name": "echivarianță la permutări", "pass": bool(dperm <= 1e-9),
                   "detail": {"max_abs_dq": dperm, "sampled_steps": int(len(sample))}})
    print(f"Q4 {checks[-1]['pass']} {dperm}", flush=True)

    # Q5/Q6: martorii de informație și decizie
    Hp = fixture_hplus()
    Hm = swap_labels(Hp, 6, 7)
    a, b = next_prediction(Hp), next_prediction(Hm)
    order = np.random.default_rng([649, 8, 5]).permutation(len(Hp))
    c = next_prediction([Hp[i] for i in order])
    dq = float(np.abs(a["q_WU"] - b["q_WU"]).max())
    dord = float(np.abs(a["q_WU"] - c["q_WU"]).max())
    B_same = bool(np.array_equal(a["piB"], b["piB"]) and np.array_equal(a["t_B"], b["t_B"]))
    q5 = B_same and dq >= 1e-3 and dord <= 1e-9 and a["cert"] and b["cert"] and c["cert"]
    checks.append({"id": "Q5", "name": "martor de informație (aceleași numărări, altă compoziție)", "pass": bool(q5),
                   "detail": {"B_identical": B_same, "max_abs_dq_WU": dq, "order_invariance_max_dq": dord,
                              "q6_q7_Hplus": [float(a["q_WU"][5]), float(a["q_WU"][6])],
                              "theta6_theta7_Hplus": [float(a["theta"][5]), float(a["theta"][6])],
                              "counts_1_8": a["counts"][:8].tolist(), "cert": [a["cert"], b["cert"], c["cert"]]}})
    print(f"Q5 {checks[-1]['pass']} {checks[-1]['detail']}", flush=True)
    sW, sB, sR = set(a["t_WU"].tolist()), set(a["t_B"].tolist()), set(a["t_R"].tolist())
    q6 = sW != sB and sW != sR
    checks.append({"id": "Q6", "name": "martor de decizie (WU≠B, WU≠R)", "pass": bool(q6),
                   "detail": {"ticket_WU": sorted(sW), "ticket_B": sorted(sB), "ticket_R": sorted(sR),
                              "anticipation_q7_gt_q6": bool(a["q_WU"][6] > a["q_WU"][5])}})
    print(f"Q6 {checks[-1]['pass']} {checks[-1]['detail']}", flush=True)

    passed = sum(c["pass"] for c in checks)
    return {"utc": utc_now(), "protocol_sha256": sha256_file(PROTO), "amendment01_sha256": sha256_file(AMEND),
            "code_sha256": sha256_file(Path(__file__)), "status": "WU_QUALIFIED" if passed == 6 else "WU_NOT_QUALIFIED",
            "passed": int(passed), "checks": checks, "seconds": time.time() - t0, "real_archive_read": False}


# ---------------------------------------------------------------------------
# Rulări
# ---------------------------------------------------------------------------
def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_seal() -> dict:
    seal = json.loads(SEAL.read_text())
    assert sha256_file(PROTO) == seal["sha256"], "protocolul diferă de sigiliu"
    aseal = json.loads(AMEND_SEAL.read_text())
    assert sha256_file(AMEND) == aseal["sha256"], "amendamentul 01 diferă de sigiliu"
    return seal


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = np.argsort(np.argsort(a, kind="stable"), kind="stable").astype(float)
    rb = np.argsort(np.argsort(b, kind="stable"), kind="stable").astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def run_real() -> int:
    run = OUT / "backtest_unic"
    if (run / "START.json").exists():
        print("REFUZ: backtestul unic WU649 a fost deja pornit (START.json există).")
        return 2
    seal = check_seal()
    qf = OUT / "CALIFICARE.json"
    if not qf.exists() or json.loads(qf.read_text())["status"] != "WU_QUALIFIED":
        print("REFUZ: calificarea lipsește sau nu este WU_QUALIFIED.")
        return 3
    steps, meta = load_real()
    start = {"utc": utc_now(), "protocol_sha256": seal["sha256"], "amendment01_sha256": sha256_file(AMEND),
             "qualification_sha256": sha256_file(qf), "code_sha256": sha256_file(Path(__file__)),
             "config": {"sigma": SIGMA, "warmup": WARMUP, "half_life_R": HALF_LIFE, "lambda0": LAM0,
                        "quad": {"h": H_Q, "K": K_Q}, "gtol": GTOL, "tau": TAU}, **meta}
    write_json(run / "START.json", start)
    t0 = time.time()
    pred = predict(steps)
    tp = time.time() - t0
    npz = run / "PREDICTII.npz"
    np.savez(npz, **pred)
    psha = sha256_file(npz)
    write_json(run / "PREDICTII_SIGILIU.json", {"utc": utc_now(), "sha256": psha, "file": npz.name,
                                                "all_cert": bool(pred["cert"].all())})
    if not bool(pred["cert"].all()):
        print("OPRIT: există pași fără certificat valid; scorul NU se calculează (§5). Necesită amendament.")
        return 4
    P = dict(np.load(npz))
    res = score(steps, P)
    res["p_exact_hits_WU_ge"] = exact_tail(res["total"]["hits_WU"], res["n_targets"])
    # descriptiv §6
    D, off, mem = _prep(steps)
    fin = fit_prefix(D, off, mem, len(steps), SIGMA)
    lp0 = posterior_eval(np.zeros(N49), mem, 1.0 - D, SIGMA, deriv=False)["logP"].sum()
    lpf = posterior_eval(fin["theta"], mem, 1.0 - D, SIGMA, deriv=False)["logP"].sum()
    counts = D.sum(0)
    sample = np.arange(0, len(P["ks"]), 97)
    dq2 = 0.0
    for i in sample:
        dq2 = max(dq2, float(np.abs(inclusion(P["theta"][i], K6, NODES2) - P["q_WU"][i]).max()))
    res["descriptive"] = {
        "final_all_data": {"theta_sd": float(fin["theta"].std()), "theta_min": float(fin["theta"].min()),
                           "theta_max": float(fin["theta"].max()), "argmin": int(fin["theta"].argmin()) + 1,
                           "argmax": int(fin["theta"].argmax()) + 1, "cert": fin["cert"],
                           "spearman_theta_counts": _spearman(fin["theta"], counts),
                           "loglik_theta_minus_zero": float(lpf - lp0), "ticket_next": top6(fin["q"]).tolist(),
                           "theta": fin["theta"].tolist(), "q": fin["q"].tolist()},
        "fine_nodes_max_dq_sample97": dq2,
    }
    res.update({"start": start, "predictions_sha256": psha, "predict_seconds": tp, "positive_claims_allowed": False})
    write_json(run / "REZULTATE.json", res)
    print(json.dumps({k: res[k] for k in ("verdict", "gates_passed", "n_targets")} | {"total": res["total"]}, indent=2))
    return 0


def run_null(M: int) -> int:
    check_seal()
    qf = OUT / "CALIFICARE.json"
    if not qf.exists() or json.loads(qf.read_text())["status"] != "WU_QUALIFIED":
        print("REFUZ: universurile nule descriptive aparțin experimentului; calificarea nu este WU_QUALIFIED.")
        return 3
    sizes = real_step_sizes()
    out = []
    for u in range(M):
        st = synthetic_steps(sizes, [649, 8, u])
        t0 = time.time()
        pr = predict(st)
        r = score(st, pr)
        t = r["total"]
        out.append({"u": u, "excess_WU": t["excess_WU"], "hits_WU": t["hits_WU"], "hits_B": t["hits_B"],
                    "hits_R": t["hits_R"], "logWU_minus_B": t["log_WU"] - t["log_B"],
                    "logWU_minus_U": t["log_WU"] - t["log_U"], "brier_WU_minus_B": t["brier_WU"] - t["brier_B"],
                    "gates_passed": r["gates_passed"], "all_cert": r["certificates"]["all_cert"],
                    "tickets_changed_vs_B_targets": r["tickets_changed_vs_B_targets"],
                    "theta_sd_last": r["theta_sd_last"], "seconds": time.time() - t0})
        print(f"u{u:03d} {out[-1]}", flush=True)
        write_json(OUT / "nule" / "SUMAR.json", {"utc": utc_now(), "M_planned": M, "M_done": len(out),
                                                 "seed": "[649, 8, u]", "descriptive": True, "universes": out})
    return 0


def run_sens() -> int:
    check_seal()
    base = OUT / "backtest_unic" / "REZULTATE.json"
    if not base.exists():
        print("REFUZ: sensibilitatea descriptivă se rulează după backtestul unic.")
        return 2
    steps, meta = load_real()
    rows = []
    for sg in SENS_SIGMAS:
        if sg == SIGMA:
            r = json.loads(base.read_text())
            src = "backtest_unic (aceeași configurație, nerecalculată)"
        else:
            r = score(steps, predict(steps, sigma=sg))
            src = "recalculat"
        t = r["total"]
        rows.append({"sigma": sg, "hits_WU": t["hits_WU"], "excess_WU": t["excess_WU"],
                     "logWU_minus_U": t["log_WU"] - t["log_U"], "logWU_minus_B": t["log_WU"] - t["log_B"],
                     "brier_WU": t["brier_WU"], "gates_passed": r["gates_passed"],
                     "all_cert": r["certificates"]["all_cert"],
                     "tickets_changed_vs_B_targets": r["tickets_changed_vs_B_targets"], "source": src})
        print(rows[-1], flush=True)
    write_json(OUT / "SENSIBILITATE.json", {"utc": utc_now(), "descriptive_only": True,
                                           "note": "nicio configurație alternativă nu poate fi promovată sau selectată",
                                           "source_sha256": meta["source_sha256"], "rows": rows})
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--qualify"]:
        check_seal()
        q = qualify()
        write_json(OUT / "CALIFICARE.json", q)
        print(json.dumps({"status": q["status"], "passed": q["passed"],
                          "checks": [{k: v for k, v in c.items() if k != "detail"} for c in q["checks"]]}, indent=2))
        return 0 if q["status"] == "WU_QUALIFIED" else 1
    if argv[:1] == ["--real"]:
        return run_real()
    if argv[:1] == ["--null"]:
        return run_null(int(argv[1]))
    if argv[:1] == ["--sens"]:
        return run_sens()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
