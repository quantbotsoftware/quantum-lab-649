"""BO649 — detecția bayesiană online a rupturilor de regim (Adams & MacKay 2007).

Protocol: PREINREGISTRARE_BO649.md (BO649-P1), sigilat în SIGILIU_PROTOCOL_BO649.json
ÎNAINTE de acest cod. Calcul clasic exact: NumPy float64 (CPU) + certificate în Q
(fractions.Fraction). Nu importă și nu rulează modele închise (QL649 engine/validare,
DL, etc.); folosește doar `parser.py` din QL649 pentru ingestie (§1).

Comenzi:
  --qualify          Q1–Q6 (date construite/sintetice; arhiva NU este citită) -> rezultate/CALIFICARE.json
  --real             backtest unic pe arhivă (refuză dacă START.json există sau calificarea lipsește)
  --null M           descriptiv: M universuri nule sintetice -> rezultate/nule/SUMAR.json
  --sens             descriptiv: grila de sensibilitate declarată în §6 -> rezultate/SENSIBILITATE.json
"""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
import math
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
QL = HERE.parent
OUT = HERE / "rezultate"
PROTO = HERE / "PREINREGISTRARE_BO649.md"
SEAL = HERE / "SIGILIU_PROTOCOL_BO649.json"

N49, K6 = 49, 6
H_PROTO = 1.0 / 250.0
M0_PROTO = 12.0
WARMUP = 100
HALF_LIFE = 26.0
LAM0, QEPS = 0.5, 1e-4
RECENT_R = 100
SENS_GRID = [(h, m0) for h in (1 / 100, 1 / 250, 1 / 1000) for m0 in (6.0, 12.0, 48.0)]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Modelul BO — implementarea float64 (generică pe N, κ)
# ---------------------------------------------------------------------------
def bocpd(steps: list[np.ndarray], N: int, kappa: int, h: float, m0: float, keep_post: tuple = ()) -> dict:
    """Recursie exactă BOCPD Beta–Bernoulli, fără trunchiere.

    steps[s]: array (n_s, N) cu 0/1 (extragerile pasului s). Returnează predicțiile prior
    (din date < s) pentru fiecare pas: q[K,N], E[r], P(r<=100), plus log-evidența totală.
    keep_post: pași pentru care se păstrează posteriorul prior-predictiv pe lungimi (UI/descriptiv).
    """
    a0, b0 = m0 * kappa / N, m0 * (N - kappa) / N
    K = len(steps)
    q = np.empty((K, N))
    Er = np.empty(K)
    prec = np.empty(K)
    lh, l1h = math.log(h), math.log1p(-h)
    n = np.zeros(0)
    C = np.zeros((0, N))
    logw = np.zeros(0)
    logZ = 0.0
    posts = {}
    for s in range(K):
        if s == 0:
            n = np.zeros(1)
            C = np.zeros((1, N))
            lp = np.zeros(1)
        else:
            lp = np.concatenate(([lh], l1h + logw))
            n = np.concatenate(([0.0], n))
            C = np.vstack((np.zeros((1, N)), C))
        w = np.exp(lp - lp.max())
        w /= w.sum()
        q[s] = w @ ((a0 + C) / (m0 + n)[:, None])
        r = np.arange(n.shape[0])
        Er[s] = float(w @ r)
        prec[s] = float(w[r <= RECENT_R].sum())
        if s in keep_post:
            posts[s] = w.copy()
        ll = np.zeros(n.shape[0])
        for y in steps[s]:
            y = np.asarray(y, dtype=np.float64)
            ll += (y * np.log(a0 + C) + (1.0 - y) * np.log(b0 + n[:, None] - C)).sum(1) - N * np.log(m0 + n)
            C = C + y
            n = n + 1.0
        lpost = lp + ll
        mx = lpost.max()
        lse = mx + math.log(np.exp(lpost - mx).sum())
        logZ += lse
        logw = lpost - lse
    return {"q": q, "Er": Er, "p_recent": prec, "logZ": logZ, "posts": posts}


# ---------------------------------------------------------------------------
# Certificate în Q: recursie Fraction și sumă brută peste segmentări
# ---------------------------------------------------------------------------
def _pred_lik(y, n, C, a0, b0, m0):
    lik = Fraction(1)
    for j, yj in enumerate(y):
        lik *= (a0 + C[j]) / (m0 + n) if yj else (b0 + n - C[j]) / (m0 + n)
    return lik


def bocpd_exact(steps, N: int, kappa: int, h: Fraction, m0: Fraction) -> dict:
    a0, b0 = m0 * kappa / N, m0 * (N - kappa) / N
    runs = []
    qs, evid = [], Fraction(1)
    for s, ys in enumerate(steps):
        zero = tuple(Fraction(0) for _ in range(N))
        prior = [(Fraction(1), 0, zero)] if s == 0 else [(h, 0, zero)] + [((1 - h) * w, n, C) for w, n, C in runs]
        qs.append([sum((w * (a0 + C[j]) / (m0 + n) for w, n, C in prior), Fraction(0)) for j in range(N)])
        post = []
        for w, n, C in prior:
            lik = Fraction(1)
            for y in ys:
                lik *= _pred_lik(y, n, C, a0, b0, m0)
                C = tuple(C[j] + y[j] for j in range(N))
                n += 1
            post.append((w * lik, n, C))
        Zs = sum((p[0] for p in post), Fraction(0))
        evid *= Zs
        runs = [(w / Zs, n, C) for w, n, C in post]
    return {"q": qs, "evidence": evid}


def _segment_lik(ys_list, N, a0, b0, m0):
    n, C, lik = 0, [Fraction(0)] * N, Fraction(1)
    for ys in ys_list:
        for y in ys:
            lik *= _pred_lik(y, n, C, a0, b0, m0)
            C = [C[j] + y[j] for j in range(N)]
            n += 1
    return lik, n, C


def bocpd_brute(steps, N: int, kappa: int, h: Fraction, m0: Fraction) -> dict:
    """Suma explicită peste toate segmentările (indicatorii de ruptură pentru pașii 1..s)."""
    a0, b0 = m0 * kappa / N, m0 * (N - kappa) / N
    T = len(steps)
    qs = []
    for s in range(T):
        num = [Fraction(0)] * N
        den = Fraction(0)
        for cps in itertools.product((0, 1), repeat=s):
            prior = Fraction(1)
            for c in cps:
                prior *= h if c else (1 - h)
            starts = [0] + [i + 1 for i, c in enumerate(cps) if c]
            wgt = prior
            for a, b in zip(starts, starts[1:] + [s + 1]):
                b_eff = min(b, s)  # datele pasului s nu se văd
                lik, n, C = _segment_lik(steps[a:b_eff], N, a0, b0, m0)
                wgt *= lik
            # segmentul curent: de la ultimul start până la s (exclusiv s)
            _, n, C = _segment_lik(steps[starts[-1]:s], N, a0, b0, m0)
            den += wgt
            for j in range(N):
                num[j] += wgt * (a0 + C[j]) / (m0 + n)
        qs.append([x / den for x in num])
    evid = Fraction(0)
    for cps in itertools.product((0, 1), repeat=T - 1):
        prior = Fraction(1)
        for c in cps:
            prior *= h if c else (1 - h)
        starts = [0] + [i + 1 for i, c in enumerate(cps) if c]
        wgt = prior
        for a, b in zip(starts, starts[1:] + [T]):
            wgt *= _segment_lik(steps[a:b], N, a0, b0, m0)[0]
        evid += wgt
    return {"q": qs, "evidence": evid}


# ---------------------------------------------------------------------------
# Comparatori, legi marginale, scoruri (definiții QL649 §5, reimplementate aici)
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


def step_counts(steps: list[np.ndarray]) -> np.ndarray:
    return np.stack([s.sum(0) for s in steps])  # [K,N]


def comparators(steps: list[np.ndarray], ks: np.ndarray) -> dict:
    S = step_counts(steps)
    P = np.vstack((np.zeros((1, S.shape[1])), np.cumsum(S, 0)))  # P[k] = numărări din pașii < k
    c = P[ks]
    K = S.shape[0]
    sidx = np.arange(K)
    W = np.where(sidx[None, :] < ks[:, None], 2.0 ** (-(ks[:, None] - 1 - sidx[None, :]) / HALF_LIFE), 0.0)
    ew = W @ S
    piB = (c + 1.0) / (c + 1.0).sum(-1, keepdims=True)
    piR = (ew + 0.5) / (ew + 0.5).sum(-1, keepdims=True)
    return {"piB": piB, "piR": piR}


def score_block(q: np.ndarray, ticket: np.ndarray | None, y: np.ndarray) -> dict:
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
        ("1", "ExcesBO/U >= 0.20", t["excess_BO"] >= 0.20, t["excess_BO"]),
        ("2", "hitsBO > hitsB și hitsBO > hitsR", t["hits_BO"] > t["hits_B"] and t["hits_BO"] > t["hits_R"],
         [t["hits_BO"], t["hits_B"], t["hits_R"]]),
        ("3", "logBO−logU > 0 și logBO−logB > 0", t["log_BO"] - t["log_U"] > 0 and t["log_BO"] - t["log_B"] > 0,
         [t["log_BO"] - t["log_U"], t["log_BO"] - t["log_B"]]),
        ("4", "BrierBO < BrierU, BrierB, BrierR", t["brier_BO"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
         [t["brier_BO"], t["brier_U"], t["brier_B"], t["brier_R"]]),
        ("5", "ambele jumătăți: exces > 0 și hitsBO−hitsB > 0",
         all(h["excess_BO"] > 0 and h["hits_BO"] - h["hits_B"] > 0 for h in (h1, h2)),
         [[h["excess_BO"], h["hits_BO"] - h["hits_B"]] for h in (h1, h2)]),
        ("6", "ambele jumătăți: logBO−logB > 0", all(h["log_BO"] - h["log_B"] > 0 for h in (h1, h2)),
         [h["log_BO"] - h["log_B"] for h in (h1, h2)]),
    ]
    return [{"gate": a, "rule": b, "pass": bool(c), "value": d} for a, b, c, d in g]


def summarize(sl: slice, S: dict) -> dict:
    n = int(S["y"][sl].shape[0])
    o = {"targets": n}
    for name in ("BO", "B", "R"):
        o[f"hits_{name}"] = int(S[f"hits_{name}"][sl].sum())
        o[f"excess_{name}"] = o[f"hits_{name}"] / n - 36.0 / 49.0 if n else 0.0
    for name in ("BO", "B", "R", "U"):
        o[f"log_{name}"] = float(S[f"log_{name}"][sl].sum())
        o[f"brier_{name}"] = float(S[f"brier_{name}"][sl].sum())
    return o


# ---------------------------------------------------------------------------
# Predicții și scor pe o istorie (reală sau sintetică)
# ---------------------------------------------------------------------------
def targets_of(steps: list[np.ndarray], warmup: int):
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    t_step = np.concatenate([np.full(steps[k].shape[0], k, dtype=np.int64) for k in ks])
    y = np.concatenate([steps[k] for k in ks]).astype(np.float64)
    return ks, t_step, y


def predict(steps: list[np.ndarray], h: float = H_PROTO, m0: float = M0_PROTO, warmup: int = WARMUP,
            keep_post: tuple = ()) -> dict:
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    bo = bocpd(steps, N49, K6, h, m0, keep_post=keep_post)
    cmp_ = comparators(steps, ks)
    qBO = bo["q"][ks]
    return {"ks": ks, "q_BO": qBO, "ticket_BO": top6(qBO), "piB": cmp_["piB"], "piR": cmp_["piR"],
            "ticket_B": top6(cmp_["piB"]), "ticket_R": top6(cmp_["piR"]), "Er": bo["Er"][ks],
            "p_recent": bo["p_recent"][ks], "logZ": np.array(bo["logZ"]), "posts": bo["posts"]}


def score(steps: list[np.ndarray], pred: dict, warmup: int = WARMUP) -> dict:
    ks, t_step, y = targets_of(steps, warmup)
    assert np.array_equal(ks, pred["ks"])
    row = t_step - warmup
    laws = {"BO": marginal_q(pred["q_BO"] / K6), "B": marginal_q(pred["piB"]), "R": marginal_q(pred["piR"])}
    tick = {"BO": pred["ticket_BO"], "B": pred["ticket_B"], "R": pred["ticket_R"]}
    S = {"y": y}
    for name in ("BO", "B", "R"):
        sb = score_block(laws[name][row], tick[name][row], y)
        S[f"hits_{name}"], S[f"log_{name}"], S[f"brier_{name}"] = sb["hits"], sb["log"], sb["brier"]
    sU = score_block(np.full_like(y, 6.0 / N49), None, y)
    S["log_U"], S["brier_U"] = sU["log"], sU["brier"]
    n = y.shape[0]
    half = n // 2
    t, h1, h2 = summarize(slice(0, n), S), summarize(slice(0, half), S), summarize(slice(half, n), S)
    g = gates(t, h1, h2)
    passed = sum(x["pass"] for x in g)
    tB = tick["BO"]
    return {
        "n_targets": int(n), "n_steps_predicted": int(ks.shape[0]), "total": t, "half1": h1, "half2": h2,
        "gates": g, "gates_passed": int(passed),
        "verdict": "BO_PROMOVAT_EXPLORATORIU" if passed == 6 else "BO_NO_PROMOTION_EXPLORATORY",
        "tickets_changed_vs_B_steps": int((tB != tick["B"]).any(-1).sum()),
        "tickets_changed_vs_R_steps": int((tB != tick["R"]).any(-1).sum()),
        "tickets_changed_vs_B_targets": int((tB[row] != tick["B"][row]).any(-1).sum()),
        "match_dist_BO": np.bincount(S["hits_BO"].astype(int), minlength=7).tolist(),
        "match_expected_U": (hyper_pmf() * n).tolist(),
        "Er": {"min": float(pred["Er"].min()), "median": float(np.median(pred["Er"])), "max": float(pred["Er"].max()),
               "last": float(pred["Er"][-1])},
        "steps_p_recent_gt_half": int((pred["p_recent"] > 0.5).sum()),
        "sum_q_max_abs_err": float(np.abs(pred["q_BO"].sum(-1) - K6).max()),
        "per_target": {"step": t_step.tolist(), "hits_BO": S["hits_BO"].astype(int).tolist(),
                       "log_BO": S["log_BO"].tolist()},
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


def synthetic_steps(sizes: np.ndarray, seed) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    out = []
    for sz in sizes:
        a = np.zeros((int(sz), N49))
        for i in range(int(sz)):
            a[i, rng.choice(N49, K6, replace=False)] = 1.0
        out.append(a)
    return out


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


# ---------------------------------------------------------------------------
# Martorii Q5/Q6 (fixture construite)
# ---------------------------------------------------------------------------
F1, F2, F3 = list(range(0, 6)), list(range(6, 12)), list(range(12, 18))


def weighted_draw(rng, weights: np.ndarray) -> np.ndarray:
    p = weights / weights.sum()
    a = np.zeros(N49)
    a[rng.choice(N49, K6, replace=False, p=p)] = 1.0
    return a


def regime_fixture(seed: int, nA: int = 600, nB: int = 300, nC: int = 40) -> list[np.ndarray]:
    """Regim vechi lung (F1 favorizat), regim intermediar (F2 și F3 favorizate, F3 crescând lent)
    și o fluctuație recentă scurtă (F3 ușor peste F2)."""
    rng = np.random.default_rng([649, 6, seed])
    steps = []
    for s in range(nA):
        w = np.ones(N49)
        w[F1] = 2.5
        steps.append(weighted_draw(rng, w)[None])
    for s in range(nB):
        w = np.ones(N49)
        w[F2] = 2.6
        w[F3] = 2.0
        steps.append(weighted_draw(rng, w)[None])
    for s in range(nC):
        w = np.ones(N49)
        w[F2] = 2.0
        w[F3] = 2.8
        steps.append(weighted_draw(rng, w)[None])
    return steps


def final_tickets(steps: list[np.ndarray]) -> dict:
    """Predicțiile pentru pasul următor după `steps` (k = len(steps))."""
    ext = steps + [np.zeros((1, N49))]
    k = np.array([len(steps)])
    bo = bocpd(ext, N49, K6, H_PROTO, M0_PROTO)
    q = bo["q"][-1]
    c = comparators(ext, k)
    return {"q_BO": q, "piB": c["piB"][0], "piR": c["piR"][0], "t_BO": top6(q), "t_B": top6(c["piB"][0]),
            "t_R": top6(c["piR"][0]), "Er": float(bo["Er"][-1])}


# ---------------------------------------------------------------------------
# Calificare Q1–Q6
# ---------------------------------------------------------------------------
def qualify() -> dict:
    t0 = time.time()
    rng = np.random.default_rng([649, 1])
    checks = []

    # Q1 — exactitate în Q și paritate float64
    inst = []
    hs = [Fraction(1, 3), Fraction(1, 7), Fraction(2, 5), Fraction(1, 250), Fraction(9, 10)]
    ms = [Fraction(1), Fraction(12), Fraction(5, 2), Fraction(48)]
    ok_exact = ok_float = True
    max_dq = 0.0
    for i in range(48):
        N = int(rng.integers(3, 6))
        kappa = int(rng.integers(1, 3))
        T = int(rng.integers(6, 10))
        h, m0 = hs[i % len(hs)], ms[(i // len(hs)) % len(ms)]
        steps_i = []
        for _ in range(T):
            nd = int(rng.integers(1, 3))
            rows = []
            for _ in range(nd):
                y = [0] * N
                for j in rng.choice(N, kappa, replace=False):
                    y[int(j)] = 1
                rows.append(tuple(y))
            steps_i.append(rows)
        ex = bocpd_exact(steps_i, N, kappa, h, m0)
        br = bocpd_brute(steps_i, N, kappa, h, m0)
        eq = ex["q"] == br["q"] and ex["evidence"] == br["evidence"]
        sumk = all(sum(qs) == kappa for qs in ex["q"])
        fl = bocpd([np.array(r, dtype=np.float64) for r in steps_i], N, kappa, float(h), float(m0))
        dq = float(np.abs(fl["q"] - np.array([[float(x) for x in qs] for qs in ex["q"]])).max())
        dz = abs(fl["logZ"] - (math.log(ex["evidence"].numerator) - math.log(ex["evidence"].denominator)))
        max_dq = max(max_dq, dq)
        ok_exact &= bool(eq and sumk)
        ok_float &= bool(dq < 1e-12 and dz < 1e-9)
        inst.append({"N": N, "kappa": kappa, "T": T, "h": str(h), "m0": str(m0), "exact_eq_brute": bool(eq),
                     "sum_q_eq_kappa_in_Q": bool(sumk), "float_max_dq": dq, "float_dlogZ": dz,
                     "segmentations": 2 ** (T - 1)})
    checks.append({"id": "Q1", "pass": ok_exact and ok_float, "instances": len(inst),
                   "certificates_in_Q": sum(x["exact_eq_brute"] for x in inst),
                   "segmentations_total": sum(x["segmentations"] for x in inst), "float_max_dq": max_dq,
                   "detail": inst})

    # Q2 — identități pe un univers nul sintetic complet
    sizes = real_step_sizes()
    null = synthetic_steps(sizes, [649, 2, 999])
    bo = bocpd(null, N49, K6, H_PROTO, M0_PROTO)
    err = float(np.abs(bo["q"].sum(1) - K6).max())
    inside = bool((bo["q"] > 0).all() and (bo["q"] < 1).all())
    checks.append({"id": "Q2", "pass": err < 1e-9 and inside, "sum_q_max_abs_err": err, "q_in_open_unit": inside,
                   "n_steps": len(null), "logZ": bo["logZ"]})

    # Q3 — cauzalitate (istorie trunchiată ≡ rulare completă)
    ksamp = list(range(97, len(null), 97))
    diffs = []
    for k in ksamp:
        tr = bocpd(null[:k] + [np.zeros((1, N49))], N49, K6, H_PROTO, M0_PROTO)
        diffs.append(float(np.abs(tr["q"][k] - bo["q"][k]).max()))
    checks.append({"id": "Q3", "pass": max(diffs) == 0.0, "k_sampled": len(ksamp), "max_abs_diff": max(diffs)})

    # Q4 — echivarianță la permutarea etichetelor
    sigma = np.random.default_rng([649, 4]).permutation(N49)
    permd = [s[:, sigma] for s in null[:600]]
    b1 = bocpd(null[:600], N49, K6, H_PROTO, M0_PROTO)
    b2 = bocpd(permd, N49, K6, H_PROTO, M0_PROTO)
    dperm = float(np.abs(b2["q"] - b1["q"][:, sigma]).max())
    checks.append({"id": "Q4", "pass": dperm < 1e-12, "max_abs_diff": dperm, "steps": 600})

    # Q5 — martor de informație: aceeași multi-mulțime, altă ordine temporală
    Hp = regime_fixture(0)
    order = np.random.default_rng([649, 5]).permutation(len(Hp))
    Hm = [Hp[i] for i in order]
    fp, fm = final_tickets(Hp), final_tickets(Hm)
    same_multiset = sorted(tuple(np.flatnonzero(s[0]).tolist()) for s in Hp) == \
        sorted(tuple(np.flatnonzero(s[0]).tolist()) for s in Hm)
    sameB = bool(np.array_equal(fp["piB"], fm["piB"]) and np.array_equal(fp["t_B"], fm["t_B"]))
    lawBp, lawBm = marginal_q(fp["piB"][None]), marginal_q(fm["piB"][None])
    sameB_law = bool(np.array_equal(lawBp, lawBm))
    dq5 = float(np.abs(fp["q_BO"] - fm["q_BO"]).max())
    checks.append({"id": "Q5", "pass": bool(same_multiset and sameB and sameB_law and dq5 >= 1e-3),
                   "same_multiset": bool(same_multiset), "B_law_and_ticket_identical": sameB and sameB_law,
                   "max_abs_dq_BO": dq5, "ticket_BO_plus": fp["t_BO"].tolist(), "ticket_BO_minus": fm["t_BO"].tolist(),
                   "ticket_B": fp["t_B"].tolist(), "Er_plus": fp["Er"], "Er_minus": fm["Er"]})

    # Q6 — martor de decizie: BO ≠ B și BO ≠ R (prima semință 0..999 care realizează proprietatea)
    found = None
    tried = 0
    for seed in range(1000):
        tried += 1
        f = final_tickets(regime_fixture(seed))
        if set(f["t_BO"].tolist()) != set(f["t_B"].tolist()) and set(f["t_BO"].tolist()) != set(f["t_R"].tolist()):
            found = (seed, f)
            break
    if found:
        seed, f = found
        checks.append({"id": "Q6", "pass": True, "fixture_seed": seed, "seeds_tried": tried,
                       "ticket_BO": f["t_BO"].tolist(), "ticket_B": f["t_B"].tolist(), "ticket_R": f["t_R"].tolist(),
                       "Er_BO": f["Er"], "F1": [x + 1 for x in F1], "F2": [x + 1 for x in F2],
                       "F3": [x + 1 for x in F3]})
    else:
        checks.append({"id": "Q6", "pass": False, "seeds_tried": tried})

    passed = sum(c["pass"] for c in checks)
    return {"protocol": "BO649-P1", "protocol_sha256": sha256_file(PROTO), "utc": utc_now(),
            "status": "BO_QUALIFIED" if passed == 6 else "BO_NOT_QUALIFIED", "passed": passed, "checks": checks,
            "archive_numbers_used": False,
            "archive_note": "din arhivă se folosește numai structura pașilor (numărul de extrageri pe zi, din date); "
                            "numerele extrase nu intră în niciun calcul de calificare",
            "seconds": time.time() - t0, "code_sha256": sha256_file(Path(__file__))}


# ---------------------------------------------------------------------------
# Rulări
# ---------------------------------------------------------------------------
def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_seal() -> dict:
    seal = json.loads(SEAL.read_text())
    assert sha256_file(PROTO) == seal["sha256"], "protocolul diferă de sigiliu"
    return seal


def run_real() -> int:
    run = OUT / "backtest_unic"
    if (run / "START.json").exists():
        print("REFUZ: backtestul unic BO649 a fost deja pornit (START.json există).")
        return 2
    seal = check_seal()
    qf = OUT / "CALIFICARE.json"
    if not qf.exists() or json.loads(qf.read_text())["status"] != "BO_QUALIFIED":
        print("REFUZ: calificarea lipsește sau nu este BO_QUALIFIED.")
        return 3
    steps, meta = load_real()
    start = {"utc": utc_now(), "protocol_sha256": seal["sha256"], "qualification_sha256": sha256_file(qf),
             "code_sha256": sha256_file(Path(__file__)), "config": {"h": H_PROTO, "m0": M0_PROTO, "warmup": WARMUP,
                                                                     "half_life_R": HALF_LIFE, "lambda0": LAM0}, **meta}
    write_json(run / "START.json", start)
    t0 = time.time()
    keep = (len(steps) - 1,)
    pred = predict(steps, keep_post=keep)
    tp = time.time() - t0
    npz = run / "PREDICTII.npz"
    np.savez(npz, **{k: v for k, v in pred.items() if k != "posts"},
             post_last=pred["posts"][keep[0]])
    psha = sha256_file(npz)
    write_json(run / "PREDICTII_SIGILIU.json", {"utc": utc_now(), "sha256": psha, "file": npz.name})
    P = dict(np.load(npz))
    res = score(steps, P)
    res["p_exact_hits_BO_ge"] = exact_tail(res["total"]["hits_BO"], res["n_targets"])
    res.update({"start": start, "predictions_sha256": psha, "predict_seconds": tp, "positive_claims_allowed": False})
    write_json(run / "REZULTATE.json", res)
    print(json.dumps({k: res[k] for k in ("verdict", "gates_passed", "n_targets")} | {"total": res["total"]}, indent=2))
    return 0


def run_null(M: int) -> int:
    check_seal()
    sizes = real_step_sizes()
    out = []
    for u in range(M):
        st = synthetic_steps(sizes, [649, 2, u])
        r = score(st, predict(st))
        t = r["total"]
        out.append({"u": u, "excess_BO": t["excess_BO"], "hits_BO": t["hits_BO"], "hits_B": t["hits_B"],
                    "hits_R": t["hits_R"], "logBO_minus_B": t["log_BO"] - t["log_B"],
                    "logBO_minus_U": t["log_BO"] - t["log_U"], "gates_passed": r["gates_passed"],
                    "Er_last": r["Er"]["last"]})
        print(f"u{u:03d} {out[-1]}", flush=True)
    write_json(OUT / "nule" / "SUMAR.json", {"utc": utc_now(), "M": M, "seed": "[649, 2, u]", "descriptive": True,
                                            "universes": out})
    return 0


def run_sens() -> int:
    check_seal()
    if not (OUT / "backtest_unic" / "REZULTATE.json").exists():
        print("REFUZ: sensibilitatea descriptivă se rulează după backtestul unic.")
        return 2
    steps, meta = load_real()
    rows = []
    for h, m0 in SENS_GRID:
        r = score(steps, predict(steps, h=h, m0=m0))
        t = r["total"]
        rows.append({"h": h, "m0": m0, "hits_BO": t["hits_BO"], "excess_BO": t["excess_BO"],
                     "logBO_minus_U": t["log_BO"] - t["log_U"], "logBO_minus_B": t["log_BO"] - t["log_B"],
                     "brier_BO": t["brier_BO"], "gates_passed": r["gates_passed"], "Er_last": r["Er"]["last"]})
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
        return 0 if q["status"] == "BO_QUALIFIED" else 1
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
