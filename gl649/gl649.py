"""GL649 — „Masa glifelor”: Bayes liniar exact pe structura cifrelor tipărite.

Protocol: PREINREGISTRARE_GL649.md (GL649-P1), sigilat în SIGILIU_PROTOCOL_GL649.json
ÎNAINTE de acest cod. Predictorul este calculat EXACT în Q (fractions.Fraction); float64 numai
pentru legea marginală și scoruri. Nu importă și nu rulează modele închise (QL649 engine/validare,
BO649, WU649, DL); folosește doar `parser.py` din QL649 pentru ingestie (§1).

Comenzi:
  --qualify          Q1–Q6 (date construite/sintetice; numerele arhivei NU sunt folosite) -> rezultate/CALIFICARE.json
  --real             backtest unic pe arhivă (refuză dacă START.json există sau calificarea lipsește)
  --null M           descriptiv: M universuri nule sintetice -> rezultate/nule/SUMAR.json
  --power M          descriptiv: M universuri sintetice sub H_GL -> rezultate/putere/SUMAR.json
  --sens             descriptiv: sensibilitatea declarată în §6 -> rezultate/SENSIBILITATE.json
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
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
PROTO = HERE / "PREINREGISTRARE_GL649.md"
SEAL = HERE / "SIGILIU_PROTOCOL_GL649.json"

N49, K6 = 49, 6
P0 = Fraction(6, 49)
SG2 = Fraction(9, 60025)     # (p0/10)^2
SE2 = Fraction(9, 240100)    # (p0/20)^2
SIGMA0_2 = Fraction(43, 392)  # p0(1-p0)·49/48
WARMUP = 100
HALF_LIFE = 26.0
LAM0, QEPS = 0.5, 1e-4
BO_HITS_B, BO_HITS_R, BO_TARGETS = 1847, 1821, 2495
SENS = [("p0/20", "p0/20", P0 * P0 / 400, P0 * P0 / 400),
        ("p0/5", "p0/20", P0 * P0 / 25, P0 * P0 / 400),
        ("p0/10", "p0/5", P0 * P0 / 100, P0 * P0 / 25)]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Structura glifelor (a priori, din scrierea zecimală a etichetelor)
# ---------------------------------------------------------------------------
def glyph_matrix() -> list[list[int]]:
    G = [[0] * 10 for _ in range(N49)]
    for j in range(1, N49 + 1):
        for ch in str(j):
            G[j - 1][int(ch)] += 1
    return G


G_INT = glyph_matrix()
G_COLSUM = [sum(G_INT[j][d] for j in range(N49)) for d in range(10)]
H_FR = [[Fraction(G_INT[j][d]) - Fraction(G_COLSUM[d], N49) for d in range(10)] for j in range(N49)]
HTH = [[sum(Fraction(G_INT[j][d] * G_INT[j][e]) for j in range(N49)) - Fraction(G_COLSUM[d] * G_COLSUM[e], N49)
        for e in range(10)] for d in range(10)]


# ---------------------------------------------------------------------------
# Algebră exactă: rezolvare prin eliminare Bareiss (fără fracții) pe rânduri scalate la întregi
# ---------------------------------------------------------------------------
def solve_exact(A: list[list[Fraction]], B: list[list[Fraction]]) -> list[list[Fraction]]:
    """Rezolvă A X = B exact (A pătrată nesingulară). B: listă de rânduri (n×m)."""
    n = len(A)
    m = len(B[0])
    rows = []
    for i in range(n):
        r = [Fraction(x) for x in A[i]] + [Fraction(x) for x in B[i]]
        L = 1
        for x in r:
            L = L * x.denominator // math.gcd(L, x.denominator)
        rows.append([int(x * L) for x in r])
    prev = 1
    for k in range(n):
        piv = next((i for i in range(k, n) if rows[i][k] != 0), None)
        if piv is None:
            raise ZeroDivisionError("matrice singulară")
        if piv != k:
            rows[k], rows[piv] = rows[piv], rows[k]
        rk = rows[k]
        akk = rk[k]
        for i in range(k + 1, n):
            ri = rows[i]
            aik = ri[k]
            rows[i] = [(akk * ri[j] - aik * rk[j]) // prev if j > k else 0 for j in range(n + m)]
        prev = akk
    X = [[Fraction(0)] * m for _ in range(n)]
    for c in range(m):
        for i in range(n - 1, -1, -1):
            s = Fraction(rows[i][n + c])
            for j in range(i + 1, n):
                if rows[i][j]:
                    s -= rows[i][j] * X[j][c]
            X[i][c] = s / rows[i][i]
    return X


# ---------------------------------------------------------------------------
# Modelul GL (§2) — Woodbury exact
# ---------------------------------------------------------------------------
def gl_core(v: list[Fraction], nu: Fraction, sg2: Fraction = SG2, se2: Fraction = SE2) -> list[Fraction]:
    """z = (PKP + νP)^+ v pentru v ⟂ 1, prin Woodbury (§2)."""
    a = se2 + nu
    Htv = [sum(G_INT[j][d] * v[j] for j in range(N49) if G_INT[j][d]) for d in range(10)]
    M = [[HTH[d][e] + (a / sg2 if d == e else 0) for e in range(10)] for d in range(10)]
    y = [r[0] for r in solve_exact(M, [[t] for t in Htv])]
    return [(v[j] - sum(H_FR[j][d] * y[d] for d in range(10))) / a for j in range(N49)]


def gl_predict_counts(c, n: int, sg2: Fraction = SG2, se2: Fraction = SE2) -> dict:
    c = [int(x) for x in c]
    assert sum(c) == K6 * n and n > 0
    x = [Fraction(cj, n) for cj in c]
    v = [xj - P0 for xj in x]
    nu = SIGMA0_2 / n
    z = gl_core(v, nu, sg2, se2)
    p = [x[j] - nu * z[j] for j in range(N49)]
    gamma = [sg2 * sum(H_FR[j][d] * z[j] for j in range(N49)) for d in range(10)]
    return {"p": p, "z": z, "gamma": gamma, "nu": nu}


def pkp_matrix(sg2: Fraction = SG2, se2: Fraction = SE2) -> list[list[Fraction]]:
    return [[se2 * ((1 if i == j else 0) - Fraction(1, N49)) + sg2 * sum(H_FR[i][d] * H_FR[j][d] for d in range(10))
             for j in range(N49)] for i in range(N49)]


PKP = None


def gl_predict_direct(c, n: int) -> list[Fraction]:
    """Rezolvarea directă exactă 49×49 (PKP + νP + J) w = v; p̂ = p0 + PKP w (Q1.1)."""
    global PKP
    if PKP is None:
        PKP = pkp_matrix()
    nu = SIGMA0_2 / n
    v = [Fraction(int(cj), n) - P0 for cj in c]
    A = [[PKP[i][j] + nu * ((1 if i == j else 0) - Fraction(1, N49)) + 1 for j in range(N49)] for i in range(N49)]
    w = [r[0] for r in solve_exact(A, [[t] for t in v])]
    return [P0 + sum(PKP[i][j] * w[j] for j in range(N49)) for i in range(N49)]


def ticket_exact(p: list[Fraction]) -> list[int]:
    return sorted(j + 1 for j in sorted(range(N49), key=lambda j: (-p[j], j))[:K6])


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


def prefix_counts(steps: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    S = np.stack([s.sum(0) for s in steps]).astype(np.int64)
    C = np.vstack((np.zeros((1, N49), dtype=np.int64), np.cumsum(S, 0)))
    nd = np.concatenate(([0], np.cumsum([s.shape[0] for s in steps]))).astype(np.int64)
    return C, nd  # C[k], nd[k] = numărări / extrageri din pașii < k


def comparators(steps: list[np.ndarray], ks: np.ndarray) -> dict:
    S = np.stack([s.sum(0) for s in steps]).astype(np.float64)
    P = np.vstack((np.zeros((1, S.shape[1])), np.cumsum(S, 0)))
    c = P[ks]
    K = S.shape[0]
    sidx = np.arange(K)
    W = np.where(sidx[None, :] < ks[:, None], 2.0 ** (-(ks[:, None] - 1 - sidx[None, :]) / HALF_LIFE), 0.0)
    ew = W @ S
    piB = (c + 1.0) / (c + 1.0).sum(-1, keepdims=True)
    piR = (ew + 0.5) / (ew + 0.5).sum(-1, keepdims=True)
    return {"piB": piB, "piR": piR, "ew": ew}


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
        ("1", "ExcesGL/U >= 0.20", t["excess_GL"] >= 0.20, t["excess_GL"]),
        ("2", "hitsGL > hitsB și hitsGL > hitsR", t["hits_GL"] > t["hits_B"] and t["hits_GL"] > t["hits_R"],
         [t["hits_GL"], t["hits_B"], t["hits_R"]]),
        ("3", "logGL−logU > 0 și logGL−logB > 0", t["log_GL"] - t["log_U"] > 0 and t["log_GL"] - t["log_B"] > 0,
         [t["log_GL"] - t["log_U"], t["log_GL"] - t["log_B"]]),
        ("4", "BrierGL < BrierU, BrierB, BrierR", t["brier_GL"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
         [t["brier_GL"], t["brier_U"], t["brier_B"], t["brier_R"]]),
        ("5", "ambele jumătăți: exces > 0 și hitsGL−hitsB > 0",
         all(h["excess_GL"] > 0 and h["hits_GL"] - h["hits_B"] > 0 for h in (h1, h2)),
         [[h["excess_GL"], h["hits_GL"] - h["hits_B"]] for h in (h1, h2)]),
        ("6", "ambele jumătăți: logGL−logB > 0", all(h["log_GL"] - h["log_B"] > 0 for h in (h1, h2)),
         [h["log_GL"] - h["log_B"] for h in (h1, h2)]),
    ]
    return [{"gate": a, "rule": b, "pass": bool(c), "value": d} for a, b, c, d in g]


def summarize(sl: slice, S: dict) -> dict:
    n = int(S["y"][sl].shape[0])
    o = {"targets": n}
    for name in ("GL", "B", "R"):
        o[f"hits_{name}"] = int(S[f"hits_{name}"][sl].sum())
        o[f"excess_{name}"] = o[f"hits_{name}"] / n - 36.0 / 49.0 if n else 0.0
    for name in ("GL", "B", "R", "U"):
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


def predict(steps: list[np.ndarray], warmup: int = WARMUP, sg2: Fraction = SG2, se2: Fraction = SE2,
            keep_exact: bool = False) -> dict:
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    C, nd = prefix_counts(steps)
    p_float = np.zeros((len(ks), N49))
    tickets = np.zeros((len(ks), K6), dtype=np.int64)
    sum_ok, z_ok = True, True
    exact = []
    gamma_last = None
    for i, k in enumerate(ks):
        r = gl_predict_counts(C[k], int(nd[k]), sg2, se2)
        p = r["p"]
        sum_ok &= (sum(p) == K6)
        z_ok &= (sum(r["z"]) == 0)
        p_float[i] = [float(t) for t in p]
        tickets[i] = ticket_exact(p)
        if keep_exact:
            exact.append([f"{t.numerator}/{t.denominator}" for t in p])
        gamma_last = r["gamma"]
    cmp_ = comparators(steps, ks)
    return {"ks": ks, "p_GL": p_float, "ticket_GL": tickets, "piB": cmp_["piB"], "piR": cmp_["piR"],
            "ticket_B": top6(cmp_["piB"]), "ticket_R": top6(cmp_["piR"]), "n_draws": nd[ks],
            "sum_exact_ok": bool(sum_ok), "z_perp_ok": bool(z_ok), "exact": exact,
            "gamma_last": [float(g) / float(P0) for g in gamma_last] if gamma_last is not None else None}


def score(steps: list[np.ndarray], pred: dict, warmup: int = WARMUP) -> dict:
    ks, t_step, y = targets_of(steps, warmup)
    assert np.array_equal(ks, pred["ks"])
    row = t_step - warmup
    laws = {"GL": marginal_q(pred["p_GL"] / K6), "B": marginal_q(pred["piB"]), "R": marginal_q(pred["piR"])}
    tick = {"GL": pred["ticket_GL"], "B": pred["ticket_B"], "R": pred["ticket_R"]}
    S = {"y": y}
    for name in ("GL", "B", "R"):
        sb = score_block(laws[name][row], tick[name][row], y)
        S[f"hits_{name}"], S[f"log_{name}"], S[f"brier_{name}"] = sb["hits"], sb["log"], sb["brier"]
    sU = score_block(np.full_like(y, 6.0 / N49), None, y)
    S["log_U"], S["brier_U"] = sU["log"], sU["brier"]
    n = y.shape[0]
    half = n // 2
    t, h1, h2 = summarize(slice(0, n), S), summarize(slice(0, half), S), summarize(slice(half, n), S)
    g = gates(t, h1, h2)
    passed = sum(x["pass"] for x in g)
    tG = tick["GL"]
    lawG = laws["GL"]
    return {
        "n_targets": int(n), "n_steps_predicted": int(ks.shape[0]), "total": t, "half1": h1, "half2": h2,
        "gates": g, "gates_passed": int(passed),
        "verdict": "GL_PROMOVAT_EXPLORATORIU" if passed == 6 else "GL_NO_PROMOTION_EXPLORATORY",
        "tickets_changed_vs_B_steps": int((tG != tick["B"]).any(-1).sum()),
        "tickets_changed_vs_R_steps": int((tG != tick["R"]).any(-1).sum()),
        "tickets_changed_vs_B_targets": int((tG[row] != tick["B"][row]).any(-1).sum()),
        "tickets_changed_vs_R_targets": int((tG[row] != tick["R"][row]).any(-1).sum()),
        "match_dist_GL": np.bincount(S["hits_GL"].astype(int), minlength=7).tolist(),
        "match_expected_U": (hyper_pmf() * n).tolist(),
        "law_GL_in_01": bool(((lawG > 0) & (lawG < 1)).all()),
        "p_GL_in_01": bool(((pred["p_GL"] > 0) & (pred["p_GL"] < 1)).all()),
        "per_target": {"step": t_step.tolist(), "hits_GL": S["hits_GL"].astype(int).tolist(),
                       "log_GL": S["log_GL"].tolist()},
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
    """Structura pașilor (numărul de extrageri pe zi) — inventar al datelor calendaristice, fără numere."""
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


def synthetic_steps(sizes: np.ndarray, seed, weights: np.ndarray | None = None) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    out = []
    for sz in sizes:
        a = np.zeros((int(sz), N49))
        for i in range(int(sz)):
            if weights is None:
                a[i, rng.choice(N49, K6, replace=False)] = 1.0
            else:
                a[i, rng.choice(N49, K6, replace=False, p=weights / weights.sum())] = 1.0
        out.append(a)
    return out


def rotation_history(c: list[int]) -> list[np.ndarray]:
    """Construcția rotativă (§4): o extragere pe pas, numărări exact c."""
    n = sum(c) // K6
    assert sum(c) == K6 * n and max(c) <= n
    L = [j + 1 for j in range(N49) for _ in range(c[j])]
    steps = []
    for i in range(n):
        s = {L[i + r * n] for r in range(K6)}
        assert len(s) == K6
        a = np.zeros((1, N49))
        a[0, [t - 1 for t in s]] = 1.0
        steps.append(a)
    return steps


def relabel(steps: list[np.ndarray], perm: list[int]) -> list[np.ndarray]:
    """perm[j] = imaginea etichetei j+1 (1-indexată)."""
    idx = np.array([perm[j] - 1 for j in range(N49)])
    out = []
    for s in steps:
        b = np.zeros_like(s)
        b[:, idx] = s
        out.append(b)
    return out


def digit_perm(mapping: dict[int, int]) -> list[int]:
    """Permutarea etichetelor indusă de o permutare a cifrelor unităților din {5..9}."""
    perm = []
    for j in range(1, N49 + 1):
        t, u = divmod(j, 10)
        perm.append(10 * t + mapping.get(u, u))
    assert sorted(perm) == list(range(1, N49 + 1))
    return perm


CYCLE5 = {5: 6, 6: 7, 7: 8, 8: 9, 9: 5}
TRANS59 = {5: 9, 9: 5}


def compose(m1: dict, m2: dict) -> dict:
    return {u: m1.get(m2.get(u, u), m2.get(u, u)) for u in range(10)}


# ---------------------------------------------------------------------------
# Calificare Q1–Q6 (§4)
# ---------------------------------------------------------------------------
def sector_lambdas(n: int, sg2: Fraction = SG2, se2: Fraction = SE2) -> tuple[Fraction, Fraction]:
    nu = SIGMA0_2 / n
    return se2 / (se2 + nu), (se2 + 5 * sg2) / (se2 + 5 * sg2 + nu)


def random_counts(rng, n: int) -> list[int]:
    c = [0] * N49
    for _ in range(n):
        for t in rng.choice(N49, K6, replace=False):
            c[int(t)] += 1
    return c


def q1() -> dict:
    rng = np.random.default_rng([649, 9, 1])
    det = {"instances": 40, "woodbury_eq_direct": True, "sum6": True, "z_perp": True, "bl_identity": True,
           "equivariance": True, "sector_formula": True}
    perms = [digit_perm(CYCLE5), digit_perm(TRANS59), digit_perm(compose(CYCLE5, TRANS59))]
    global PKP
    if PKP is None:
        PKP = pkp_matrix()
    for inst in range(40):
        n = int(rng.integers(49, 401))
        c = random_counts(rng, n)
        r = gl_predict_counts(c, n)
        det["woodbury_eq_direct"] &= (r["p"] == gl_predict_direct(c, n))
        det["sum6"] &= (sum(r["p"]) == K6)
        det["z_perp"] &= (sum(r["z"]) == 0)
        for perm in perms:
            cp = [0] * N49
            for j in range(N49):
                cp[perm[j] - 1] = c[j]
            rp = gl_predict_counts(cp, n)
            det["equivariance"] &= all(rp["p"][perm[j] - 1] == r["p"][j] for j in range(N49))
        if inst < 5:
            nu = SIGMA0_2 / n
            for j in range(N49):
                Pe = [Fraction(1 if i == j else 0) - Fraction(1, N49) for i in range(N49)]
                w = [sum(PKP[i][l] * Pe[l] for l in range(N49)) + nu * Pe[i] for i in range(N49)]
                z = gl_core(w, nu)
                adj = [w[i] - nu * z[i] for i in range(N49)]
                target = [sum(PKP[i][l] * Pe[l] for l in range(N49)) for i in range(N49)]
                det["bl_identity"] &= (adj == target)
    for _ in range(20):
        d, dp = [int(t) for t in rng.choice([5, 6, 7, 8, 9], 2, replace=False)]
        m = int(rng.integers(1, 9))
        n, b = 49 * m, 6 * m
        a = [int(t) for t in rng.integers(-5, 6, size=5)]
        c = [b] * N49
        for t in range(5):
            c[10 * t + d - 1] = b + a[t]
            c[10 * t + dp - 1] = b - a[t]
        r = gl_predict_counts(c, n)
        l0, l1 = sector_lambdas(n)
        u = [Fraction(at, n) for at in a]
        ub = sum(u) / 5
        Au = [l0 * (ut - ub) + l1 * ub for ut in u]
        exp_p = [P0] * N49
        for t in range(5):
            exp_p[10 * t + d - 1] = P0 + Au[t]
            exp_p[10 * t + dp - 1] = P0 - Au[t]
        det["sector_formula"] &= (r["p"] == exp_p)
    ok = all(v for k, v in det.items() if k != "instances")
    return {"pass": bool(ok), "detail": det}


def q2_q3_q4(sizes: np.ndarray) -> tuple[dict, dict, dict]:
    t0 = time.time()
    steps = synthetic_steps(sizes, [649, 9, 999])
    pred = predict(steps)
    laws = marginal_q(pred["p_GL"] / K6)
    ks = pred["ks"]
    sample = [int(k) for k in ks if (k - WARMUP) % 97 == 0]
    C, nd = prefix_counts(steps)
    direct_ok = True
    for k in sample:
        direct_ok &= (gl_predict_counts(C[k], int(nd[k]))["p"] == gl_predict_direct(C[k], int(nd[k])))
    d2 = {"steps": int(len(ks)), "sum_exact_ok": pred["sum_exact_ok"], "z_perp_ok": pred["z_perp_ok"],
          "law_in_01": bool(((laws > 0) & (laws < 1)).all()), "direct_eq_woodbury_sample": bool(direct_ok),
          "sample_steps": len(sample), "p_min": float(pred["p_GL"].min()), "p_max": float(pred["p_GL"].max()),
          "run_seconds": time.time() - t0}
    Q2 = {"pass": bool(d2["sum_exact_ok"] and d2["z_perp_ok"] and d2["law_in_01"] and direct_ok), "detail": d2}
    # Q3: istoria trunchiată la < k (recalculată din lista trunchiată)
    q3_ok = True
    for k in sample:
        trunc = steps[:k]
        S = np.stack([s.sum(0) for s in trunc]).sum(0).astype(np.int64)
        nk = int(sum(s.shape[0] for s in trunc))
        p_tr = gl_predict_counts(S, nk)["p"]
        p_full = gl_predict_counts(C[k], int(nd[k]))["p"]
        q3_ok &= (p_tr == p_full) and (ticket_exact(p_tr) == pred["ticket_GL"][k - WARMUP].tolist())
    Q3 = {"pass": bool(q3_ok), "detail": {"sample_steps": len(sample)}}
    # Q4: echivarianță la automorfismul ciclului (5 6 7 8 9)
    perm = digit_perm(CYCLE5)
    st_p = relabel(steps, perm)
    Cp, ndp = prefix_counts(st_p)
    q4_ok = True
    non_aut_dev = 0.0
    swap = list(range(1, N49 + 1))
    swap[16], swap[18] = 19, 17
    st_s = relabel(steps, swap)
    Cs, nds = prefix_counts(st_s)
    for k in sample:
        p = gl_predict_counts(C[k], int(nd[k]))["p"]
        pp = gl_predict_counts(Cp[k], int(ndp[k]))["p"]
        q4_ok &= all(pp[perm[j] - 1] == p[j] for j in range(N49))
        ps = gl_predict_counts(Cs[k], int(nds[k]))["p"]
        non_aut_dev = max(non_aut_dev, max(abs(float(ps[swap[j] - 1] - p[j])) for j in range(N49)))
    Q4 = {"pass": bool(q4_ok), "detail": {"sample_steps": len(sample),
                                          "descriptive_non_automorphism_17_19_max_abs_dp": non_aut_dev}}
    return Q2, Q3, Q4


def fixture_F5() -> list[int]:
    c = [24] * N49
    c[7 - 1], c[8 - 1] = 36, 12
    return c


def fixture_F6() -> list[int]:
    c = [24] * N49
    c[7 - 1], c[8 - 1] = 23, 25
    for t in range(1, 5):
        c[10 * t + 7 - 1], c[10 * t + 8 - 1] = 25, 23
    return c


def predict_next(steps: list[np.ndarray]) -> dict:
    """Predicția pentru pasul următor istoriei date (k = len(steps))."""
    C, nd = prefix_counts(steps)
    k = len(steps)
    r = gl_predict_counts(C[k], int(nd[k]))
    cmp_ = comparators(steps, np.array([k]))
    return {"p": r["p"], "ticket_GL": ticket_exact(r["p"]), "piB": cmp_["piB"][0], "piR": cmp_["piR"][0],
            "ew": cmp_["ew"][0], "ticket_B": top6(cmp_["piB"])[0].tolist(), "ticket_R": top6(cmp_["piR"])[0].tolist(),
            "counts": C[k].tolist(), "n": int(nd[k])}


def q5() -> dict:
    c = fixture_F5()
    st = rotation_history(c)
    r = predict_next(st)
    n = r["n"]
    l0, l1 = sector_lambdas(n)
    p = r["p"]
    gap_exact = p[17 - 1] - p[19 - 1]
    gap_expected = Fraction(12) * (l1 - l0) / (5 * n)
    law = marginal_q(np.array([float(t) for t in p]) / K6)
    lawB = marginal_q(r["piB"])
    rng = np.random.default_rng([649, 9, 5])
    order = rng.permutation(len(st))
    r2 = predict_next([st[i] for i in order])
    det = {"n": n, "counts_ok": r["counts"] == c, "c17_eq_c19": c[16] == c[18],
           "B_law_17_eq_19": bool(lawB[16] == lawB[18]), "p19_eq_p0": p[18] == P0,
           "gap_exact_eq_closed_form": gap_exact == gap_expected, "gap_float": float(gap_exact),
           "sign_p17_gt_p19": gap_exact > 0, "law_gap": float(law[16] - law[18]),
           "law_gap_ge_1e-3": bool(law[16] - law[18] >= 1e-3), "order_invariance_exact": r2["p"] == p,
           "lambda0": float(l0), "lambda1": float(l1)}
    ok = all(det[k] for k in ("counts_ok", "c17_eq_c19", "B_law_17_eq_19", "p19_eq_p0", "gap_exact_eq_closed_form",
                              "sign_p17_gt_p19", "law_gap_ge_1e-3", "order_invariance_exact"))
    return {"pass": bool(ok), "detail": det}


def q6() -> dict:
    c = fixture_F6()
    st = rotation_history(c)
    r = predict_next(st)
    n = r["n"]
    l0, l1 = sector_lambdas(n)
    p = r["p"]
    above = sorted(j + 1 for j in range(N49) if p[j] > P0)
    below = sorted(j + 1 for j in range(N49) if p[j] < P0)
    ew = r["ew"]
    last = sorted(int(t) + 1 for t in np.nonzero(st[-1][0])[0])
    det = {"n": n, "counts_ok": r["counts"] == c, "ticket_GL": r["ticket_GL"], "ticket_B": r["ticket_B"],
           "ticket_R": r["ticket_R"], "above_p0": above, "below_p0": below,
           "three_l1_gt_eight_l0": 3 * l1 > 8 * l0, "lambda0": float(l0), "lambda1": float(l1),
           "ew_1": float(ew[0]), "ew_1_bound": 2 ** (-172 / 26) / (1 - 2 ** (-1 / 26)),
           "last_draw_labels": last, "min_ew_last_draw": float(min(ew[t - 1] for t in last))}
    ok = (det["counts_ok"] and r["ticket_GL"] == [1, 7, 17, 27, 37, 47] and r["ticket_B"] == [1, 8, 17, 27, 37, 47]
          and 1 not in r["ticket_R"] and r["ticket_R"] != r["ticket_GL"] and det["three_l1_gt_eight_l0"]
          and above == [7, 17, 27, 37, 47] and below == [8, 18, 28, 38, 48])
    return {"pass": bool(ok), "detail": det}


def qualify() -> dict:
    log = []
    t0 = time.time()
    res = {}
    res["Q1"] = q1()
    log.append(f"Q1 {res['Q1']['pass']} {res['Q1']['detail']} ({time.time() - t0:.0f}s)")
    print(log[-1], flush=True)
    sizes = real_step_sizes()
    res["Q2"], res["Q3"], res["Q4"] = q2_q3_q4(sizes)
    for q in ("Q2", "Q3", "Q4"):
        log.append(f"{q} {res[q]['pass']} {res[q]['detail']} ({time.time() - t0:.0f}s)")
        print(log[-1], flush=True)
    res["Q5"] = q5()
    log.append(f"Q5 {res['Q5']['pass']} {res['Q5']['detail']}")
    print(log[-1], flush=True)
    res["Q6"] = q6()
    log.append(f"Q6 {res['Q6']['pass']} {res['Q6']['detail']}")
    print(log[-1], flush=True)
    names = {"Q1": "exactitate în Q (Woodbury = direct, Bayes liniar, echivarianță, sector)",
             "Q2": "identități pe univers nul complet", "Q3": "cauzalitate (trunchiat ≡ complet, exact)",
             "Q4": "echivarianță la automorfismul cifrelor (5 6 7 8 9)", "Q5": "martor de informație (analitic)",
             "Q6": "martor de decizie (analitic)"}
    checks = [{"id": q, "name": names[q], "pass": res[q]["pass"], "detail": res[q]["detail"]} for q in names]
    passed = sum(c["pass"] for c in checks)
    (HERE / "jurnal").mkdir(exist_ok=True)
    (HERE / "jurnal" / "calificare.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    return {"utc": utc_now(), "protocol_sha256": json.loads(SEAL.read_text())["sha256"],
            "code_sha256": sha256_file(Path(__file__)), "status": "GL_QUALIFIED" if passed == 6 else "GL_NOT_QUALIFIED",
            "passed": int(passed), "checks": checks, "seconds": time.time() - t0,
            "archive_numbers_used": False, "note": "Q2 citește numai structura pașilor (datele calendaristice)."}


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
        print("REFUZ: backtestul unic GL649 a fost deja pornit (START.json există).")
        return 2
    seal = check_seal()
    qf = OUT / "CALIFICARE.json"
    if not qf.exists() or json.loads(qf.read_text())["status"] != "GL_QUALIFIED":
        print("REFUZ: calificarea lipsește sau nu este GL_QUALIFIED.")
        return 3
    steps, meta = load_real()
    start = {"utc": utc_now(), "protocol_sha256": seal["sha256"], "qualification_sha256": sha256_file(qf),
             "code_sha256": sha256_file(Path(__file__)),
             "config": {"s_g2": str(SG2), "s_e2": str(SE2), "sigma0_2": str(SIGMA0_2), "warmup": WARMUP,
                        "half_life_R": HALF_LIFE, "lambda0": LAM0}, **meta}
    write_json(run / "START.json", start)
    t0 = time.time()
    pred = predict(steps, keep_exact=True)
    tp = time.time() - t0
    npz = run / "PREDICTII.npz"
    np.savez(npz, ks=pred["ks"], p_GL=pred["p_GL"], ticket_GL=pred["ticket_GL"], piB=pred["piB"], piR=pred["piR"],
             ticket_B=pred["ticket_B"], ticket_R=pred["ticket_R"], n_draws=pred["n_draws"])
    exf = run / "PREDICTII_EXACTE.json.gz"
    with open(exf, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(json.dumps({"ks": pred["ks"].tolist(), "p_hat": pred["exact"]}).encode())
    psha, esha = sha256_file(npz), sha256_file(exf)
    write_json(run / "PREDICTII_SIGILIU.json", {"utc": utc_now(), "npz": npz.name, "npz_sha256": psha,
                                                "exact": exf.name, "exact_sha256": esha,
                                                "sum_exact_ok": pred["sum_exact_ok"], "z_perp_ok": pred["z_perp_ok"]})
    P = dict(np.load(npz))
    res = score(steps, P)
    consist = {"hits_B": res["total"]["hits_B"], "hits_R": res["total"]["hits_R"], "targets": res["n_targets"],
               "expected_BO649": [BO_HITS_B, BO_HITS_R, BO_TARGETS]}
    consist["ok"] = (consist["hits_B"], consist["hits_R"], consist["targets"]) == (BO_HITS_B, BO_HITS_R, BO_TARGETS)
    res["consistency_with_BO649"] = consist
    res["valid_run"] = bool(consist["ok"] and pred["sum_exact_ok"] and pred["z_perp_ok"])
    res["p_exact_hits_GL_ge"] = exact_tail(res["total"]["hits_GL"], res["n_targets"])
    res["gamma_last_relative"] = pred["gamma_last"]
    pl = P["p_GL"][-1]
    cl = prefix_counts(steps)[0][-1]
    rk = lambda a: np.argsort(np.argsort(a, kind="stable"), kind="stable").astype(float)
    res["final_step"] = {"rel_dev_std": float((pl / float(P0) - 1).std()), "rel_dev_min": float((pl / float(P0) - 1).min()),
                         "rel_dev_max": float((pl / float(P0) - 1).max()),
                         "spearman_p_vs_counts_prefix": float(np.corrcoef(rk(pl), rk(prefix_counts(steps)[0][len(steps) - 1].astype(float)))[0, 1]),
                         "counts_all": cl.tolist()}
    res.update({"start": start, "predictions_sha256": psha, "exact_predictions_sha256": esha, "predict_seconds": tp,
                "positive_claims_allowed": False})
    write_json(run / "REZULTATE.json", res)
    print(json.dumps({k: res[k] for k in ("verdict", "gates_passed", "n_targets", "valid_run")} |
                     {"total": res["total"], "consistency": consist}, indent=2))
    return 0


def run_null(M: int) -> int:
    check_seal()
    sizes = real_step_sizes()
    out = []
    for u in range(M):
        st = synthetic_steps(sizes, [649, 9, u])
        r = score(st, predict(st))
        t = r["total"]
        out.append({"u": u, "excess_GL": t["excess_GL"], "hits_GL": t["hits_GL"], "hits_B": t["hits_B"],
                    "hits_R": t["hits_R"], "logGL_minus_B": t["log_GL"] - t["log_B"],
                    "logGL_minus_U": t["log_GL"] - t["log_U"], "gates_passed": r["gates_passed"],
                    "tickets_changed_vs_B_targets": r["tickets_changed_vs_B_targets"]})
        print(f"u{u:03d} {out[-1]}", flush=True)
    write_json(OUT / "nule" / "SUMAR.json", {"utc": utc_now(), "M": M, "seed": "[649, 9, u]", "descriptive": True,
                                            "universes": out})
    return 0


def run_power(M: int) -> int:
    check_seal()
    sizes = real_step_sizes()
    out = []
    G = np.array(G_INT, dtype=float)
    Pm = np.eye(N49) - 1.0 / N49
    for u in range(M):
        rng = np.random.default_rng([649, 9, 1000 + u])
        gam = rng.normal(0, 0.1, 10)
        eps = rng.normal(0, 0.05, N49)
        p = float(P0) * (1 + Pm @ (G @ gam + eps))
        p = np.clip(p, 0.2 * float(P0), 1.8 * float(P0))
        st = synthetic_steps(sizes, [649, 9, 1000 + u, 1], weights=p)
        r = score(st, predict(st))
        t = r["total"]
        top_true = set((np.argsort(-p, kind="stable")[:6] + 1).tolist())
        out.append({"u": u, "excess_GL": t["excess_GL"], "hits_GL": t["hits_GL"], "hits_B": t["hits_B"],
                    "hits_R": t["hits_R"], "logGL_minus_B": t["log_GL"] - t["log_B"],
                    "logGL_minus_U": t["log_GL"] - t["log_U"], "gates_passed": r["gates_passed"],
                    "true_top6": sorted(top_true), "p_rel_sd": float((p / float(P0) - 1).std())})
        print(f"h{u:03d} {out[-1]}", flush=True)
    write_json(OUT / "putere" / "SUMAR.json", {"utc": utc_now(), "M": M, "seed": "[649, 9, 1000+u]",
                                              "descriptive": True, "generator": "alegere secvențială ponderată p_j",
                                              "universes": out})
    return 0


def run_sens() -> int:
    check_seal()
    if not (OUT / "backtest_unic" / "REZULTATE.json").exists():
        print("REFUZ: sensibilitatea descriptivă se rulează după backtestul unic.")
        return 2
    steps, meta = load_real()
    rows = []
    for nm_g, nm_e, sg2, se2 in SENS:
        r = score(steps, predict(steps, sg2=sg2, se2=se2))
        t = r["total"]
        rows.append({"s_g": nm_g, "s_e": nm_e, "hits_GL": t["hits_GL"], "excess_GL": t["excess_GL"],
                     "logGL_minus_U": t["log_GL"] - t["log_U"], "logGL_minus_B": t["log_GL"] - t["log_B"],
                     "brier_GL": t["brier_GL"], "gates_passed": r["gates_passed"],
                     "tickets_changed_vs_B_targets": r["tickets_changed_vs_B_targets"]})
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
        return 0 if q["status"] == "GL_QUALIFIED" else 1
    if argv[:1] == ["--real"]:
        return run_real()
    if argv[:1] == ["--null"]:
        return run_null(int(argv[1]))
    if argv[:1] == ["--power"]:
        return run_power(int(argv[1]))
    if argv[:1] == ["--sens"]:
        return run_sens()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
