"""CS649 — „Caruselul seturilor”: rotație deterministă ipotetică a seturilor de bile/urnelor.

Protocol: PREINREGISTRARE_CS649.md (CS649-P1), sigilat în SIGILIU_PROTOCOL_CS649.json ÎNAINTE de acest
cod. Model: θ(k) = p0·1 + a + b³(k mod 3) + b⁵(k mod 5) + b⁷(k mod 7), așteptare ajustată Bayes liniară
prin ecuațiile Henderson 16×16, EXACT în Q (fractions.Fraction); float64 numai pentru legea marginală,
scoruri și rulările descriptive din §6. Nu importă și nu rulează modele închise (QL649 engine/validare,
BO649, WU649, GL649, SE649, DL); folosește doar `parser.py` din QL649 pentru ingestie (§1). Funcțiile
generice (eliminarea exactă Bareiss, comparatorii B/R, legea λ, scorurile, porțile) sunt copiate cu
proveniență din se649/se649.py (aceleași definiții QL649 §5), nu importate.

Comenzi:
  --qualify          Q1–Q6 (date construite/sintetice; numerele arhivei NU sunt folosite) -> rezultate/CALIFICARE.json
  --real             backtest unic pe arhivă (refuză dacă START.json există sau calificarea lipsește)
  --null M           descriptiv: M universuri nule sintetice -> rezultate/nule/SUMAR.json
  --power M1 M2      descriptiv: M1 universuri la scara priorului + M2 cu o singură rotație
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
PROTO = HERE / "PREINREGISTRARE_CS649.md"
SEAL = HERE / "SIGILIU_PROTOCOL_CS649.json"

N49, K6 = 49, 6
PERIODS = (3, 5, 7)
OFFS = {3: 1, 5: 4, 7: 9}          # nivelul 0 = a; (K, r) -> OFFS[K] + r
NL = 16
P0 = Fraction(6, 49)
TA2 = Fraction(9, 240100)          # (p0/20)^2
T2 = Fraction(9, 9604)             # (p0/4)^2
SIGMA0_2 = Fraction(43, 392)       # p0(1-p0)·49/48
WARMUP = 100
HALF_LIFE = 26.0
LAM0, QEPS = 0.5, 1e-4
BO_HITS_B, BO_HITS_R, BO_TARGETS = 1847, 1821, 2495
SENS = [("p0/20", "p0/8", P0 * P0 / 400, P0 * P0 / 64),
        ("p0/20", "p0/2", P0 * P0 / 400, P0 * P0 / 4),
        ("p0/10", "p0/4", P0 * P0 / 100, P0 * P0 / 16)]

assert TA2 == P0 * P0 / 400 and T2 == P0 * P0 / 16 and SIGMA0_2 == P0 * (1 - P0) * Fraction(49, 48)
assert SIGMA0_2 / TA2 == Fraction(52675, 18) and SIGMA0_2 / T2 == Fraction(2107, 18)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def levels_of(k: int) -> list[int]:
    """Nivelurile de incidență ale pasului k: a și (K, k mod K) pentru K ∈ {3,5,7} (§2)."""
    return [0] + [OFFS[K] + (k % K) for K in PERIODS]


def zstar(k: int) -> list[int]:
    z = [0] * NL
    for l in levels_of(k):
        z[l] = 1
    return z


# ---------------------------------------------------------------------------
# Algebră exactă: Bareiss (copiat din se649.py) și Gauss–Jordan cu fracții (a doua implementare, Q2)
# ---------------------------------------------------------------------------
def solve_exact(A: list[list[Fraction]], B: list[list[Fraction]]) -> list[list[Fraction]]:
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


def solve_gauss_jordan(A: list[list[Fraction]], b: list[Fraction]) -> list[Fraction]:
    n = len(A)
    M = [[Fraction(x) for x in A[i]] + [Fraction(b[i])] for i in range(n)]
    for c in range(n):
        piv = next(i for i in range(c, n) if M[i][c] != 0)
        M[c], M[piv] = M[piv], M[c]
        inv = 1 / M[c][c]
        M[c] = [x * inv for x in M[c]]
        for i in range(n):
            if i != c and M[i][c] != 0:
                f = M[i][c]
                M[i] = [x - f * y for x, y in zip(M[i], M[c])]
    return [M[i][n] for i in range(n)]


# ---------------------------------------------------------------------------
# Starea suficientă: NN = ZᵀZ (16×16, întregi), C = numărări pe niveluri (16×49, întregi)
# ---------------------------------------------------------------------------
class State:
    def __init__(self):
        self.NN = np.zeros((NL, NL), dtype=np.int64)
        self.C = np.zeros((NL, N49), dtype=np.int64)

    def add_step(self, k: int, draws: np.ndarray) -> None:
        lv = levels_of(k)
        nd = int(draws.shape[0])
        cnt = draws.sum(0).astype(np.int64)
        for l1 in lv:
            self.C[l1] += cnt
            for l2 in lv:
                self.NN[l1, l2] += nd

    def copy(self) -> "State":
        s = State()
        s.NN, s.C = self.NN.copy(), self.C.copy()
        return s


def state_from(hist: list[tuple[int, np.ndarray]]) -> State:
    s = State()
    for k, d in hist:
        s.add_step(k, d)
    return s


def henderson_M(NN: np.ndarray, ta2: Fraction, t2: Fraction) -> list[list[Fraction]]:
    ginv = [SIGMA0_2 / ta2] + [SIGMA0_2 / t2] * (NL - 1)
    return [[Fraction(int(NN[i, j])) + (ginv[i] if i == j else 0) for j in range(NL)] for i in range(NL)]


def cs_predict_state(st: State, kstar: int, ta2: Fraction = TA2, t2: Fraction = T2,
                     method: str = "bareiss") -> dict:
    """p̂_j = p0 + Σ_ℓ v_ℓ (c_{ℓj} − p0 n_ℓ), v = M⁻¹ z*, exact în Q (§2)."""
    M = henderson_M(st.NN, ta2, t2)
    z = zstar(kstar)
    if method == "bareiss":
        v = [x[0] for x in solve_exact(M, [[Fraction(t)] for t in z])]
    else:
        v = solve_gauss_jordan(M, [Fraction(t) for t in z])
    den = 1
    for x in v:
        den = den * x.denominator // math.gcd(den, x.denominator)
    V = [int(x * den) for x in v]
    nl = [int(st.NN[l, l]) for l in range(NL)]
    T = Fraction(sum(V[l] * nl[l] for l in range(NL)), den)
    base = P0 * (1 - T)
    p = []
    for j in range(N49):
        p.append(base + Fraction(sum(V[l] * int(st.C[l, j]) for l in range(NL)), den))
    return {"p": p, "v": v}


def cs_predict_float(st: State, kstar: int, ta2: float, t2: float) -> np.ndarray:
    s0 = float(SIGMA0_2)
    M = st.NN.astype(np.float64) + np.diag([s0 / ta2] + [s0 / t2] * (NL - 1))
    v = np.linalg.solve(M, np.array(zstar(kstar), dtype=np.float64))
    n = np.diag(st.NN).astype(np.float64)
    p0 = 6.0 / N49
    return p0 + v @ (st.C.astype(np.float64) - p0 * n[:, None])


def primal_predict(hist: list[tuple[int, np.ndarray]], kstar: int, ta2: Fraction = TA2,
                   t2: Fraction = T2) -> list[Fraction]:
    """Forma primală N×N: p̂ − p0 = z*ᵀ G Zᵀ (Z G Zᵀ + σ0² I)⁻¹ (Y − p0), exact (Q1.1)."""
    rows = [(k, d[i]) for k, d in hist for i in range(d.shape[0])]
    N = len(rows)
    ph = [[k % K for K in PERIODS] for k, _ in rows]
    phs = [kstar % K for K in PERIODS]
    A = [[ta2 + sum(t2 for a, b in zip(ph[i], ph[j]) if a == b) + (SIGMA0_2 if i == j else 0)
          for j in range(N)] for i in range(N)]
    rhs = [[ta2 + sum(t2 for a, b in zip(ph[i], phs) if a == b)] for i in range(N)]
    alpha = [x[0] for x in solve_exact(A, rhs)]
    p = []
    for j in range(N49):
        p.append(P0 + sum(alpha[i] * (int(rows[i][1][j]) - P0) for i in range(N)))
    return p


def closed_form_balanced(hist: list[tuple[int, np.ndarray]], kstar: int, ta2: Fraction = TA2,
                         t2: Fraction = T2) -> list[Fraction]:
    """Derivarea C (plan echilibrat, n = 105·m, o extragere pe pas, indici 0..n−1)."""
    n = len(hist)
    assert n % 105 == 0 and [k for k, _ in hist] == list(range(n)) and all(d.shape[0] == 1 for _, d in hist)
    c = [sum(int(d[0, j]) for _, d in hist) for j in range(N49)]
    S = ta2 + t2 * (Fraction(1, 3) + Fraction(1, 5) + Fraction(1, 7))
    lam0 = S / (S + SIGMA0_2 / n)
    p = []
    for j in range(N49):
        xb = Fraction(c[j], n)
        v = P0 + lam0 * (xb - P0)
        for K in PERIODS:
            lamK = t2 / (t2 + K * SIGMA0_2 / n)
            r = kstar % K
            cKr = sum(int(d[0, j]) for k, d in hist if k % K == r)
            v += lamK * (Fraction(cKr * K, n) - xb)
        p.append(v)
    return p


def ticket_exact(p: list[Fraction]) -> list[int]:
    return sorted(j + 1 for j in sorted(range(N49), key=lambda j: (-p[j], j))[:K6])


# ---------------------------------------------------------------------------
# Comparatori, legi marginale, scoruri (copiate din se649.py; definiții QL649 §5)
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
        ("1", "ExcesCS/U >= 0.20", t["excess_CS"] >= 0.20, t["excess_CS"]),
        ("2", "hitsCS > hitsB și hitsCS > hitsR", t["hits_CS"] > t["hits_B"] and t["hits_CS"] > t["hits_R"],
         [t["hits_CS"], t["hits_B"], t["hits_R"]]),
        ("3", "logCS−logU > 0 și logCS−logB > 0", t["log_CS"] - t["log_U"] > 0 and t["log_CS"] - t["log_B"] > 0,
         [t["log_CS"] - t["log_U"], t["log_CS"] - t["log_B"]]),
        ("4", "BrierCS < BrierU, BrierB, BrierR", t["brier_CS"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
         [t["brier_CS"], t["brier_U"], t["brier_B"], t["brier_R"]]),
        ("5", "ambele jumătăți: exces > 0 și hitsCS−hitsB > 0",
         all(h["excess_CS"] > 0 and h["hits_CS"] - h["hits_B"] > 0 for h in (h1, h2)),
         [[h["excess_CS"], h["hits_CS"] - h["hits_B"]] for h in (h1, h2)]),
        ("6", "ambele jumătăți: logCS−logB > 0", all(h["log_CS"] - h["log_B"] > 0 for h in (h1, h2)),
         [h["log_CS"] - h["log_B"] for h in (h1, h2)]),
    ]
    return [{"gate": a, "rule": b, "pass": bool(c), "value": d} for a, b, c, d in g]


def summarize(sl: slice, S: dict) -> dict:
    n = int(S["y"][sl].shape[0])
    o = {"targets": n}
    for name in ("CS", "B", "R"):
        o[f"hits_{name}"] = int(S[f"hits_{name}"][sl].sum())
        o[f"excess_{name}"] = o[f"hits_{name}"] / n - 36.0 / 49.0 if n else 0.0
    for name in ("CS", "B", "R", "U"):
        o[f"log_{name}"] = float(S[f"log_{name}"][sl].sum())
        o[f"brier_{name}"] = float(S[f"brier_{name}"][sl].sum())
    return o


# ---------------------------------------------------------------------------
# Predicții walk-forward (exact sau float64 descriptiv) și scor
# ---------------------------------------------------------------------------
def targets_of(steps: list[np.ndarray], warmup: int):
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    t_step = np.concatenate([np.full(steps[k].shape[0], k, dtype=np.int64) for k in ks])
    y = np.concatenate([steps[k] for k in ks]).astype(np.float64)
    return ks, t_step, y


def predict(steps: list[np.ndarray], warmup: int = WARMUP, ta2: Fraction = TA2, t2: Fraction = T2,
            exact: bool = True, keep_exact: bool = False, keep_at: set | None = None) -> dict:
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    st = State()
    for s in range(warmup):
        st.add_step(s, steps[s])
    p_float = np.zeros((len(ks), N49))
    tickets = np.zeros((len(ks), K6), dtype=np.int64)
    sum_ok, out01 = True, 0
    ex, vex, kept = [], [], {}
    for i, k in enumerate(ks):
        k = int(k)
        if exact:
            r = cs_predict_state(st, k, ta2, t2)
            p = r["p"]
            sum_ok &= (sum(p) == K6)
            out01 += int(not all(0 < t < 1 for t in p))
            p_float[i] = [float(t) for t in p]
            tickets[i] = ticket_exact(p)
            if keep_exact:
                ex.append([f"{t.numerator}/{t.denominator}" for t in p])
                vex.append([f"{t.numerator}/{t.denominator}" for t in r["v"]])
            if keep_at is not None and k in keep_at:
                kept[k] = {"p": p, "state": st.copy()}
        else:
            pf = cs_predict_float(st, k, float(ta2), float(t2))
            sum_ok &= abs(pf.sum() - 6.0) < 1e-9
            out01 += int(not ((pf > 0) & (pf < 1)).all())
            p_float[i] = pf
            tickets[i] = top6(pf)
        st.add_step(k, steps[k])
    cmp_ = comparators(steps, ks)
    phases = np.stack([ks % K for K in PERIODS], 1)
    return {"ks": ks, "p_CS": p_float, "ticket_CS": tickets, "piB": cmp_["piB"], "piR": cmp_["piR"],
            "ticket_B": top6(cmp_["piB"]), "ticket_R": top6(cmp_["piR"]), "phases": phases,
            "sum_exact_ok": bool(sum_ok), "steps_p_outside_01": int(out01), "exact": ex, "v_exact": vex,
            "kept": kept, "final_state": st}


def score(steps: list[np.ndarray], pred: dict, warmup: int = WARMUP) -> dict:
    ks, t_step, y = targets_of(steps, warmup)
    assert np.array_equal(ks, pred["ks"])
    row = t_step - warmup
    laws = {"CS": marginal_q(pred["p_CS"] / K6), "B": marginal_q(pred["piB"]), "R": marginal_q(pred["piR"])}
    tick = {"CS": pred["ticket_CS"], "B": pred["ticket_B"], "R": pred["ticket_R"]}
    S = {"y": y}
    for name in ("CS", "B", "R"):
        sb = score_block(laws[name][row], tick[name][row], y)
        S[f"hits_{name}"], S[f"log_{name}"], S[f"brier_{name}"] = sb["hits"], sb["log"], sb["brier"]
    sU = score_block(np.full_like(y, 6.0 / N49), None, y)
    S["log_U"], S["brier_U"] = sU["log"], sU["brier"]
    n = y.shape[0]
    half = n // 2
    t, h1, h2 = summarize(slice(0, n), S), summarize(slice(0, half), S), summarize(slice(half, n), S)
    g = gates(t, h1, h2)
    passed = sum(x["pass"] for x in g)
    tC = tick["CS"]
    lawC = laws["CS"]
    by_phase = {}
    for K in PERIODS:
        ph = t_step % K
        d = {}
        for r in range(K):
            m = ph == r
            nt = int(m.sum())
            d[str(r)] = {"targets": nt, "hits_CS": int(S["hits_CS"][m].sum()), "hits_B": int(S["hits_B"][m].sum()),
                         "hits_R": int(S["hits_R"][m].sum()),
                         "excess_CS": float(S["hits_CS"][m].sum() / nt - 36 / 49) if nt else None,
                         "logCS_minus_B": float((S["log_CS"][m] - S["log_B"][m]).sum())}
        by_phase[f"K{K}"] = d
    return {
        "n_targets": int(n), "n_steps_predicted": int(ks.shape[0]), "total": t, "half1": h1, "half2": h2,
        "gates": g, "gates_passed": int(passed),
        "verdict": "CS_PROMOVAT_EXPLORATORIU" if passed == 6 else "CS_NO_PROMOTION_EXPLORATORY",
        "tickets_changed_vs_B_steps": int((tC != tick["B"]).any(-1).sum()),
        "tickets_changed_vs_R_steps": int((tC != tick["R"]).any(-1).sum()),
        "tickets_changed_vs_B_targets": int((tC[row] != tick["B"][row]).any(-1).sum()),
        "tickets_changed_vs_R_targets": int((tC[row] != tick["R"][row]).any(-1).sum()),
        "by_target_phase": by_phase,
        "match_dist_CS": np.bincount(S["hits_CS"].astype(int), minlength=7).tolist(),
        "match_expected_U": (hyper_pmf() * n).tolist(),
        "law_CS_in_01": bool(((lawC > 0) & (lawC < 1)).all()),
        "p_CS_in_01_all_steps": bool(((pred["p_CS"] > 0) & (pred["p_CS"] < 1)).all()),
        "steps_p_outside_01": int(pred["steps_p_outside_01"]),
        "per_target": {"step": t_step.tolist(), "hits_CS": S["hits_CS"].astype(int).tolist(),
                       "log_CS": S["log_CS"].tolist()},
    }


def g_statistics(steps: list[np.ndarray]) -> dict:
    """G_K = 2 Σ c ln(c / (6 n_{Kr}/49)) pe tabelele etichetă × fază (§6, descriptiv)."""
    st = state_from(list(enumerate(steps)))
    out = {}
    for K in PERIODS:
        lv = [OFFS[K] + r for r in range(K)]
        c = st.C[lv].astype(float)
        n = np.array([st.NN[l, l] for l in lv], dtype=float)
        e = 6.0 * n[:, None] / N49
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(c > 0, c * np.log(c / e), 0.0)
        out[f"G{K}"] = float(2.0 * t.sum())
    out["G_sum"] = out["G3"] + out["G5"] + out["G7"]
    return out


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


def real_step_structure() -> np.ndarray:
    """Numărul de extrageri pe zi (structura pașilor) — fără numere și fără date în model."""
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


def synthetic_steps(sizes: np.ndarray, seed, pfun=None) -> list[np.ndarray]:
    """Extrageri uniforme sau (dacă pfun este dat) alegere secvențială ponderată cu p(k)."""
    rng = np.random.default_rng(seed)
    out = []
    for s, sz in enumerate(sizes):
        a = np.zeros((int(sz), N49))
        w = None if pfun is None else pfun(s)
        for i in range(int(sz)):
            if w is None:
                a[i, rng.choice(N49, K6, replace=False)] = 1.0
            else:
                a[i, rng.choice(N49, K6, replace=False, p=w / w.sum())] = 1.0
        out.append(a)
    return out


def onehot(sets: list[int]) -> np.ndarray:
    a = np.zeros((1, N49))
    a[0, [t - 1 for t in sets]] = 1.0
    return a


def constant_phase_history(K: int, A: list[list[int]], n: int = 105) -> list[np.ndarray]:
    """Construcția „set constant pe fază” (§4): extragerea pasului k este A[k mod K]."""
    assert len(A) == K and all(len(set(x)) == K6 for x in A)
    return [onehot(A[k % K]) for k in range(n)]


def predict_at(steps: list[np.ndarray], kstar: int) -> dict:
    st = state_from(list(enumerate(steps)))
    r = cs_predict_state(st, kstar)
    out = {"p": r["p"], "v": r["v"], "ticket_CS": ticket_exact(r["p"]),
           "counts_total": st.C[0].tolist()}
    if kstar == len(steps):
        cmp_ = comparators(steps, np.array([kstar]))
        out.update({"piB": cmp_["piB"][0], "piR": cmp_["piR"][0], "ew": cmp_["ew"][0],
                    "ticket_B": top6(cmp_["piB"])[0].tolist(), "ticket_R": top6(cmp_["piR"])[0].tolist()})
    return out


# ---------------------------------------------------------------------------
# Calificare Q1–Q6 (§4)
# ---------------------------------------------------------------------------
def uniform_draw(rng) -> np.ndarray:
    a = np.zeros(N49)
    a[rng.choice(N49, K6, replace=False)] = 1.0
    return a


def relabel(steps: list[np.ndarray], perm: list[int]) -> list[np.ndarray]:
    idx = np.array([perm[j] - 1 for j in range(N49)])
    out = []
    for s in steps:
        b = np.zeros_like(s)
        b[:, idx] = s
        out.append(b)
    return out


def q1() -> dict:
    rng = np.random.default_rng([649, 11, 1])
    prng = np.random.default_rng([649, 11, 11])
    perms = [[int(t) + 1 for t in prng.permutation(N49)] for _ in range(3)]
    det = {"instances": 40, "henderson_eq_primal": True, "sum6": True, "equivariance": True,
           "cases_empty_levels": 0, "cases_two_draw_steps": 0, "max_draws": 0}
    for inst in range(40):
        k0 = int(rng.integers(0, 105))
        n = int(rng.integers(1, 7)) if inst < 6 else int(rng.integers(1, 41))
        hist = []
        for t in range(n):
            sz = 2 if rng.random() < 0.15 else 1
            hist.append((k0 + t, np.stack([uniform_draw(rng) for _ in range(sz)])))
        kstar = k0 + n
        st = state_from(hist)
        r = cs_predict_state(st, kstar)
        pp = primal_predict(hist, kstar)
        det["henderson_eq_primal"] &= (r["p"] == pp)
        det["sum6"] &= (sum(r["p"]) == K6)
        det["cases_empty_levels"] += int(any(st.NN[l, l] == 0 for l in range(NL)))
        det["cases_two_draw_steps"] += int(any(d.shape[0] == 2 for _, d in hist))
        det["max_draws"] = max(det["max_draws"], int(st.NN[0, 0]))
        for perm in perms:
            hp = [(k, relabel([d], perm)[0]) for k, d in hist]
            rp = cs_predict_state(state_from(hp), kstar)
            det["equivariance"] &= all(rp["p"][perm[j] - 1] == r["p"][j] for j in range(N49))
    rng2 = np.random.default_rng([649, 11, 2])
    bal = []
    for n in (105, 210):
        hist = [(k, uniform_draw(rng2)[None, :]) for k in range(n)]
        st = state_from(hist)
        for kstar in (n, n + 1):
            r = cs_predict_state(st, kstar)
            bal.append({"n": n, "kstar": kstar, "eq": r["p"] == closed_form_balanced(hist, kstar)})
    det["balanced_closed_form"] = bal
    ok = all(det[k] for k in ("henderson_eq_primal", "sum6", "equivariance")) and all(b["eq"] for b in bal)
    ok &= det["cases_empty_levels"] >= 5 and len(bal) == 4
    return {"pass": bool(ok), "detail": det}


def q2_q3_q4(sizes: np.ndarray) -> tuple[dict, dict, dict]:
    t0 = time.time()
    steps = synthetic_steps(sizes, [649, 11, 999])
    K = len(steps)
    sample = [k for k in range(WARMUP, K) if (k - WARMUP) % 97 == 0]
    pred = predict(steps, keep_at=set(sample))
    laws = marginal_q(pred["p_CS"] / K6)
    inc_ok, gj_ok = True, True
    for k in sample:
        st_s = state_from(list(enumerate(steps[:k])))
        kept = pred["kept"][k]
        inc_ok &= np.array_equal(st_s.NN, kept["state"].NN) and np.array_equal(st_s.C, kept["state"].C)
        gj_ok &= (cs_predict_state(st_s, k, method="gauss_jordan")["p"] == kept["p"])
    d2 = {"steps": int(len(pred["ks"])), "sum_exact_ok": pred["sum_exact_ok"],
          "law_in_01": bool(((laws > 0) & (laws < 1)).all()), "incremental_eq_scratch_sample": bool(inc_ok),
          "bareiss_eq_gauss_jordan_sample": bool(gj_ok), "sample_steps": len(sample),
          "steps_p_outside_01": pred["steps_p_outside_01"],
          "p_min": float(pred["p_CS"].min()), "p_max": float(pred["p_CS"].max()), "run_seconds": time.time() - t0}
    Q2 = {"pass": bool(d2["sum_exact_ok"] and d2["law_in_01"] and inc_ok and gj_ok), "detail": d2}
    # Q3: istoria trunchiată la < k (recalculată din lista trunchiată)
    q3_ok = True
    for k in sample:
        trunc = steps[:k]
        p_tr = cs_predict_state(state_from(list(enumerate(trunc))), k)["p"]
        q3_ok &= (p_tr == pred["kept"][k]["p"]) and (ticket_exact(p_tr) == pred["ticket_CS"][k - WARMUP].tolist())
    Q3 = {"pass": bool(q3_ok), "detail": {"sample_steps": len(sample)}}
    # Q4(a): echivarianță la o permutare aleatoare fixă a etichetelor
    perm = [int(t) + 1 for t in np.random.default_rng([649, 11, 4]).permutation(N49)]
    st_p = relabel(steps, perm)
    q4a = True
    for k in sample:
        p = pred["kept"][k]["p"]
        pp = cs_predict_state(state_from(list(enumerate(st_p[:k]))), k)["p"]
        q4a &= all(pp[perm[j] - 1] == p[j] for j in range(N49))
    # Q4(b): permutarea extragerilor între pașii cu o singură extragere din aceeași clasă k mod 105
    kf = K - 1
    single = [s for s in range(kf) if steps[s].shape[0] == 1]
    rng = np.random.default_rng([649, 11, 44])
    st_b = list(steps[:kf])
    for c in range(105):
        idx = [s for s in single if s % 105 == c]
        sh = rng.permutation(len(idx))
        for a, b in zip(idx, [idx[t] for t in sh]):
            st_b[a] = steps[b]
    p_fin = cs_predict_state(state_from(list(enumerate(steps[:kf]))), kf)["p"]
    p_b = cs_predict_state(state_from(list(enumerate(st_b))), kf)["p"]
    q4b = (p_b == p_fin) and any(not np.array_equal(st_b[s], steps[s]) for s in single)
    st_x = list(steps[:kf])
    sh = rng.permutation(len(single))
    for a, b in zip(single, [single[t] for t in sh]):
        st_x[a] = steps[b]
    p_x = cs_predict_state(state_from(list(enumerate(st_x))), kf)["p"]
    dev_x = max(abs(float(p_x[j] - p_fin[j])) for j in range(N49))
    Q4 = {"pass": bool(q4a and q4b), "detail": {"sample_steps": len(sample), "label_equivariance": bool(q4a),
                                                "within_class_mod105_order_invariance": bool(q4b),
                                                "descriptive_cross_class_perm_max_abs_dp": dev_x}}
    return Q2, Q3, Q4


def lam_K(K: int, n: int) -> Fraction:
    return T2 / (T2 + K * SIGMA0_2 / n)


def lam_0(n: int) -> Fraction:
    S = TA2 + T2 * Fraction(71, 105)
    return S / (S + SIGMA0_2 / n)


def fixture_F5(K: int) -> list[list[int]]:
    A0 = [5, 20, 21, 22, 23, 24]
    A1 = [9, 20, 21, 22, 23, 24]
    Ar = [30, 31, 32, 33, 34, 35]
    return [A0, A1] + [Ar] * (K - 2)


def q5() -> dict:
    det, ok = {}, True
    for K in PERIODS:
        steps = constant_phase_history(K, fixture_F5(K))
        r = predict_at(steps, 105)
        r6 = predict_at(steps, 106)
        r7 = predict_at(steps, 107)
        lk = lam_K(K, 105)
        p = r["p"]
        law = marginal_q(np.array([float(t) for t in p]) / K6)
        lawB = marginal_q(r["piB"])
        tot = r["counts_total"]
        ew = r["ew"]
        d = {"lambda_K": str(lk), "lambda_K_float": float(lk), "c5": tot[4], "c9": tot[8],
             "c5_eq_c9_eq_105_over_K": tot[4] == tot[8] == 105 // K,
             "B_law_5_eq_9": bool(lawB[4] == lawB[8]),
             "gap_105_exact_eq_lambda": p[4] - p[8] == lk, "gap_105_float": float(p[4] - p[8]),
             "sign_p5_gt_p9": p[4] > p[8], "law_gap": float(law[4] - law[8]),
             "law_gap_ge_1e-3": bool(law[4] - law[8] >= 1e-3),
             "gap_106_exact_eq_minus_lambda": r6["p"][4] - r6["p"][8] == -lk,
             "gap_107_exact_zero": r7["p"][4] - r7["p"][8] == 0,
             "ew5": float(ew[4]), "ew9": float(ew[8]),
             "ew9_eq_2pow_1_26_ew5": bool(abs(ew[8] - 2 ** (1 / 26) * ew[4]) <= 1e-12 * ew[8]),
             "ew9_gt_ew5": bool(ew[8] > ew[4])}
        okK = all(d[k] for k in ("c5_eq_c9_eq_105_over_K", "B_law_5_eq_9", "gap_105_exact_eq_lambda",
                                 "sign_p5_gt_p9", "law_gap_ge_1e-3", "gap_106_exact_eq_minus_lambda",
                                 "gap_107_exact_zero", "ew9_eq_2pow_1_26_ew5", "ew9_gt_ew5"))
        d["pass"] = bool(okK)
        det[f"K{K}"] = d
        ok &= okK
    return {"pass": bool(ok), "detail": det}


def q6() -> dict:
    A = [[44, 45, 46, 47, 48, 49], [1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]]
    steps = constant_phase_history(3, A)
    r = predict_at(steps, 105)
    p = r["p"]
    l0, l3 = lam_0(105), lam_K(3, 105)
    e44 = P0 + l0 * (Fraction(1, 3) - P0) + Fraction(2, 3) * l3
    e1 = P0 + l0 * (Fraction(2, 3) - P0) - Fraction(2, 3) * l3
    e7 = P0 * (1 - l0)
    exp_ok = (all(p[j] == e44 for j in range(43, 49)) and all(p[j] == e1 for j in range(6))
              and all(p[j] == e7 for j in range(6, 43)))
    ew = r["ew"]
    det = {"lambda0": str(l0), "lambda3": str(l3), "diff_44_1": str(p[43] - p[0]),
           "diff_expected": str((4 * l3 - l0) / 3), "diff_eq_expected": p[43] - p[0] == Fraction(1194264, 6765473),
           "p44": float(p[43]), "p1": float(p[0]), "p7": float(p[6]),
           "p_values_exact_as_derived": bool(exp_ok), "totals": sorted(set(r["counts_total"])),
           "ticket_CS": r["ticket_CS"], "ticket_B": r["ticket_B"], "ticket_R": r["ticket_R"],
           "ew_1": float(ew[0]), "max_ew_44_49": float(max(ew[43:49])),
           "ew1_gt_2max_ew44_49": bool(ew[0] > 2 * max(ew[43:49]))}
    ok = (exp_ok and det["diff_eq_expected"] and r["ticket_CS"] == [44, 45, 46, 47, 48, 49]
          and r["ticket_B"] == [1, 2, 3, 4, 5, 6] and det["ew1_gt_2max_ew44_49"]
          and r["ticket_R"] != r["ticket_CS"] and det["totals"] == [0, 35, 70])
    return {"pass": bool(ok), "detail": det}


def qualify() -> dict:
    log = []
    t0 = time.time()
    res = {}
    res["Q1"] = q1()
    log.append(f"Q1 {res['Q1']['pass']} {res['Q1']['detail']} ({time.time() - t0:.0f}s)")
    print(log[-1], flush=True)
    sizes = real_step_structure()
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
    names = {"Q1": "exactitate în Q (Henderson = primal N×N, Σ=6, echivarianță, formă închisă echilibrată)",
             "Q2": "identități pe univers nul complet (incremental = de la zero, Bareiss = Gauss–Jordan)",
             "Q3": "cauzalitate (trunchiat ≡ complet, exact)",
             "Q4": "echivarianță la etichete și invarianță la ordinea din clasa k mod 105",
             "Q5": "martor de informație (analitic, Derivarea C, K = 3, 5, 7)", "Q6": "martor de decizie (analitic)"}
    checks = [{"id": q, "name": names[q], "pass": res[q]["pass"], "detail": res[q]["detail"]} for q in names]
    passed = sum(c["pass"] for c in checks)
    (HERE / "jurnal").mkdir(exist_ok=True)
    (HERE / "jurnal" / "calificare.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    return {"utc": utc_now(), "protocol_sha256": json.loads(SEAL.read_text())["sha256"],
            "code_sha256": sha256_file(Path(__file__)), "status": "CS_QUALIFIED" if passed == 6 else "CS_NOT_QUALIFIED",
            "passed": int(passed), "checks": checks, "seconds": time.time() - t0,
            "archive_numbers_used": False,
            "note": "Q2–Q4 citesc numai structura pașilor (numărul de extrageri pe zi), fără numere."}


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


def level_name(l: int) -> str:
    if l == 0:
        return "a"
    for K in PERIODS:
        if OFFS[K] <= l < OFFS[K] + K:
            return f"K{K}r{l - OFFS[K]}"
    raise ValueError(l)


def run_real() -> int:
    run = OUT / "backtest_unic"
    if (run / "START.json").exists():
        print("REFUZ: backtestul unic CS649 a fost deja pornit (START.json există).")
        return 2
    seal = check_seal()
    qf = OUT / "CALIFICARE.json"
    if not qf.exists() or json.loads(qf.read_text())["status"] != "CS_QUALIFIED":
        print("REFUZ: calificarea lipsește sau nu este CS_QUALIFIED.")
        return 3
    steps, meta = load_real()
    start = {"utc": utc_now(), "protocol_sha256": seal["sha256"], "qualification_sha256": sha256_file(qf),
             "code_sha256": sha256_file(Path(__file__)),
             "config": {"tau_a2": str(TA2), "tau2": str(T2), "sigma0_2": str(SIGMA0_2), "warmup": WARMUP,
                        "half_life_R": HALF_LIFE, "lambda0": LAM0, "periods": list(PERIODS),
                        "phase_index": "indicele pasului (zi distinctă) din parser, de la 0"}, **meta}
    write_json(run / "START.json", start)
    t0 = time.time()
    pred = predict(steps, keep_exact=True)
    tp = time.time() - t0
    npz = run / "PREDICTII.npz"
    np.savez(npz, ks=pred["ks"], p_CS=pred["p_CS"], ticket_CS=pred["ticket_CS"], piB=pred["piB"], piR=pred["piR"],
             ticket_B=pred["ticket_B"], ticket_R=pred["ticket_R"], phases=pred["phases"])
    exf = run / "PREDICTII_EXACTE.json.gz"
    with open(exf, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(json.dumps({"ks": pred["ks"].tolist(), "phases": pred["phases"].tolist(),
                                 "levels": [level_name(l) for l in range(NL)], "p_hat": pred["exact"],
                                 "v": pred["v_exact"]}).encode())
    psha, esha = sha256_file(npz), sha256_file(exf)
    write_json(run / "PREDICTII_SIGILIU.json", {"utc": utc_now(), "npz": npz.name, "npz_sha256": psha,
                                                "exact": exf.name, "exact_sha256": esha,
                                                "sum_exact_ok": pred["sum_exact_ok"],
                                                "steps_p_outside_01": pred["steps_p_outside_01"]})
    P = dict(np.load(npz))
    P["steps_p_outside_01"] = pred["steps_p_outside_01"]
    res = score(steps, P)
    consist = {"hits_B": res["total"]["hits_B"], "hits_R": res["total"]["hits_R"], "targets": res["n_targets"],
               "expected_BO649_GL649_SE649": [BO_HITS_B, BO_HITS_R, BO_TARGETS]}
    consist["ok"] = (consist["hits_B"], consist["hits_R"], consist["targets"]) == (BO_HITS_B, BO_HITS_R, BO_TARGETS)
    res["consistency_with_BO649_GL649_SE649"] = consist
    res["valid_run"] = bool(consist["ok"] and pred["sum_exact_ok"] and res["law_CS_in_01"])
    res["p_exact_hits_CS_ge"] = exact_tail(res["total"]["hits_CS"], res["n_targets"])
    st = pred["final_state"]
    kf = len(steps)
    vf = cs_predict_state(st, kf)["v"]
    res["final_state"] = {"n_per_level": {level_name(l): int(st.NN[l, l]) for l in range(NL)},
                          "v_for_next_index": {level_name(l): float(vf[l]) for l in range(NL)},
                          "next_index": kf, "next_phases": [kf % K for K in PERIODS]}
    pl = P["p_CS"][-1]
    res["final_step"] = {"phases": P["phases"][-1].tolist(), "rel_dev_std": float((pl / float(P0) - 1).std()),
                         "rel_dev_min": float((pl / float(P0) - 1).min()),
                         "rel_dev_max": float((pl / float(P0) - 1).max())}
    res["G_label_x_phase"] = g_statistics(steps)
    res.update({"start": start, "predictions_sha256": psha, "exact_predictions_sha256": esha, "predict_seconds": tp,
                "positive_claims_allowed": False})
    write_json(run / "REZULTATE.json", res)
    print(json.dumps({k: res[k] for k in ("verdict", "gates_passed", "n_targets", "valid_run")} |
                     {"total": res["total"], "consistency": consist}, indent=2))
    return 0


def null_row(st: list[np.ndarray], r: dict) -> dict:
    t = r["total"]
    return {"excess_CS": t["excess_CS"], "excess_B": t["excess_B"], "hits_CS": t["hits_CS"], "hits_B": t["hits_B"],
            "hits_R": t["hits_R"], "logCS_minus_B": t["log_CS"] - t["log_B"],
            "logCS_minus_U": t["log_CS"] - t["log_U"], "brier_CS_minus_U": t["brier_CS"] - t["brier_U"],
            "gates_passed": r["gates_passed"], "gates": [g["pass"] for g in r["gates"]],
            "tickets_changed_vs_B_targets": r["tickets_changed_vs_B_targets"],
            "steps_p_outside_01": r["steps_p_outside_01"]}


def run_null(M: int) -> int:
    check_seal()
    sizes = real_step_structure()
    out = []
    for u in range(M):
        st = synthetic_steps(sizes, [649, 11, u])
        r = score(st, predict(st, exact=False))
        out.append({"u": u, **null_row(st, r), **g_statistics(st)})
        print(f"u{u:03d} {out[-1]}", flush=True)
    write_json(OUT / "nule" / "SUMAR.json", {"utc": utc_now(), "M": M, "seed": "[649, 11, u]", "descriptive": True,
                                            "predictor": "aceleași ecuații Henderson în float64 (§6)",
                                            "universes": out})
    return 0


def run_power(M1: int, M2: int) -> int:
    check_seal()
    sizes = real_step_structure()
    Pm = np.eye(N49) - 1.0 / N49
    p0 = float(P0)
    out = []
    for kind, M, base in (("prior", M1, 1000), ("single", M2, 2000)):
        for u in range(M):
            rng = np.random.default_rng([649, 11, base + u])
            a = rng.normal(0, 0.05, N49)
            if kind == "prior":
                b = {K: rng.normal(0, 0.25, (K, N49)) for K in PERIODS}
                K0 = None
            else:
                K0 = [3, 5, 7, 3, 5, 7, 3, 5][u % 8]
                b = {K: (rng.normal(0, 0.25, (K, N49)) if K == K0 else np.zeros((K, N49))) for K in PERIODS}

            def pfun(k, a=a, b=b):
                eff = a + sum(b[K][k % K] for K in PERIODS)
                return np.clip(p0 * (1 + Pm @ eff), 0.2 * p0, 1.8 * p0)

            st = synthetic_steps(sizes, [649, 11, base + u, 1], pfun=pfun)
            r = score(st, predict(st, exact=False))
            rel = np.stack([pfun(k) / p0 - 1 for k in range(105)])
            out.append({"kind": kind, "K0": K0, "u": u, **null_row(st, r),
                        "p_rel_sd_mean_over_105_phases": float(rel.std(1).mean())})
            print(f"{kind}-{u:03d} {out[-1]}", flush=True)
    write_json(OUT / "putere" / "SUMAR.json", {"utc": utc_now(), "M_prior_scale": M1, "M_single_rotation": M2,
                                              "seed": "[649, 11, 1000+u] / [649, 11, 2000+u]", "descriptive": True,
                                              "generator": "alegere secvențială ponderată p_j(k) după fazele k mod 3,5,7",
                                              "predictor": "aceleași ecuații Henderson în float64 (§6)",
                                              "universes": out})
    return 0


def run_sens() -> int:
    check_seal()
    if not (OUT / "backtest_unic" / "REZULTATE.json").exists():
        print("REFUZ: sensibilitatea descriptivă se rulează după backtestul unic.")
        return 2
    steps, meta = load_real()
    rows = []
    for nm_a, nm_t, ta2, t2 in SENS:
        r = score(steps, predict(steps, ta2=ta2, t2=t2, exact=False))
        t = r["total"]
        rows.append({"tau_a": nm_a, "tau": nm_t, "hits_CS": t["hits_CS"], "excess_CS": t["excess_CS"],
                     "logCS_minus_U": t["log_CS"] - t["log_U"], "logCS_minus_B": t["log_CS"] - t["log_B"],
                     "brier_CS": t["brier_CS"], "gates_passed": r["gates_passed"],
                     "tickets_changed_vs_B_targets": r["tickets_changed_vs_B_targets"]})
        print(rows[-1], flush=True)
    write_json(OUT / "SENSIBILITATE.json", {"utc": utc_now(), "descriptive_only": True,
                                           "note": "nicio configurație alternativă nu poate fi promovată sau selectată",
                                           "predictor": "aceleași ecuații Henderson în float64 (§6)",
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
        return 0 if q["status"] == "CS_QUALIFIED" else 1
    if argv[:1] == ["--real"]:
        return run_real()
    if argv[:1] == ["--null"]:
        return run_null(int(argv[1]))
    if argv[:1] == ["--power"]:
        return run_power(int(argv[1]), int(argv[2]))
    if argv[:1] == ["--sens"]:
        return run_sens()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
