"""SE649 — „Anotimpurile bilelor”: Bayes liniar ierarhic exact, etichetă × anotimp meteorologic.

Protocol: PREINREGISTRARE_SE649.md (SE649-P1), sigilat în SIGILIU_PROTOCOL_SE649.json ÎNAINTE de
acest cod. Predictorul este calculat EXACT în Q (fractions.Fraction); float64 numai pentru legea
marginală și scoruri. Nu importă și nu rulează modele închise (QL649 engine/validare, BO649, WU649,
GL649, DL); folosește doar `parser.py` din QL649 pentru ingestie (§1). Funcțiile generice
(eliminarea exactă Bareiss, comparatorii B/R, legea λ, scorurile, porțile) sunt copiate cu
proveniență din gl649/gl649.py (aceleași definiții QL649 §5), nu importate.

Comenzi:
  --qualify          Q1–Q6 (date construite/sintetice; numerele arhivei NU sunt folosite) -> rezultate/CALIFICARE.json
  --real             backtest unic pe arhivă (refuză dacă START.json există sau calificarea lipsește)
  --null M           descriptiv: M universuri nule sintetice -> rezultate/nule/SUMAR.json
  --power M1 M2      descriptiv: M1 universuri la scara priorului + M2 la jumătatea interacțiunii
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
PROTO = HERE / "PREINREGISTRARE_SE649.md"
SEAL = HERE / "SIGILIU_PROTOCOL_SE649.json"

N49, K6, NS = 49, 6, 4
P0 = Fraction(6, 49)
TA2 = Fraction(9, 240100)    # (p0/20)^2
TB2 = Fraction(36, 60025)    # (p0/5)^2
SIGMA0_2 = Fraction(43, 392)  # p0(1-p0)·49/48
WARMUP = 100
HALF_LIFE = 26.0
LAM0, QEPS = 0.5, 1e-4
BO_HITS_B, BO_HITS_R, BO_TARGETS = 1847, 1821, 2495
SENS = [("p0/20", "p0/10", P0 * P0 / 400, P0 * P0 / 100),
        ("p0/20", "p0/4", P0 * P0 / 400, P0 * P0 / 16),
        ("p0/10", "p0/5", P0 * P0 / 100, P0 * P0 / 25)]
SEASON_NAMES = ["iarnă", "primăvară", "vară", "toamnă"]

assert TA2 == P0 * P0 / 400 and TB2 == P0 * P0 / 25 and SIGMA0_2 == P0 * (1 - P0) * Fraction(49, 48)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def season_of(date_str: str) -> int:
    """Anotimp meteorologic (§0): 0 iarnă (dec–feb), 1 primăvară, 2 vară, 3 toamnă."""
    m = dt.date.fromisoformat(date_str).month
    return (m % 12) // 3


# ---------------------------------------------------------------------------
# Algebră exactă (copiată din gl649.py, eliminare Bareiss pe rânduri scalate la întregi)
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


# ---------------------------------------------------------------------------
# Modelul SE (§2)
# ---------------------------------------------------------------------------
def se_weights(ns, phi: int, ta2: Fraction = TA2, tb2: Fraction = TB2) -> dict[int, Fraction]:
    """Ponderile w_φ în formă închisă (Sherman–Morrison), pentru anotimpurile observate O."""
    O = [f for f in range(NS) if ns[f] > 0]
    assert O, "nicio extragere în istorie"
    nu = {f: SIGMA0_2 / int(ns[f]) for f in O}
    D = {f: tb2 + nu[f] for f in O}
    S = sum(1 / D[f] for f in O)
    kappa = ta2 / (1 + ta2 * S)
    if phi in O:
        fac = nu[phi] / D[phi]
        return {f: kappa * fac / D[f] + (tb2 / D[phi] if f == phi else 0) for f in O}
    return {f: kappa / D[f] for f in O}


def se_weights_direct(ns, phi: int, ta2: Fraction = TA2, tb2: Fraction = TB2) -> dict[int, Fraction]:
    """Rezolvarea directă exactă a sistemului |O|×|O|  Σ_d w = s (Q1.1)."""
    O = [f for f in range(NS) if ns[f] > 0]
    A = [[ta2 + ((tb2 + SIGMA0_2 / int(ns[f])) if f == g else 0) for g in O] for f in O]
    s = [[ta2 + (tb2 if f == phi else 0)] for f in O]
    w = solve_exact(A, s)
    return {f: w[i][0] for i, f in enumerate(O)}


def se_predict_counts(C4, ns, phi: int, ta2: Fraction = TA2, tb2: Fraction = TB2, direct: bool = False) -> dict:
    """p̂ = p0·1 + Σ_φ w_φ (c_φ/n_φ − p0·1), exact în Q."""
    ns = [int(x) for x in ns]
    for f in range(NS):
        assert sum(int(t) for t in C4[f]) == K6 * ns[f]
    w = (se_weights_direct if direct else se_weights)(ns, phi, ta2, tb2)
    p = []
    for j in range(N49):
        v = P0
        for f, wf in w.items():
            v += wf * (Fraction(int(C4[f][j]), ns[f]) - P0)
        p.append(v)
    return {"p": p, "w": w}


def ticket_exact(p: list[Fraction]) -> list[int]:
    return sorted(j + 1 for j in sorted(range(N49), key=lambda j: (-p[j], j))[:K6])


# ---------------------------------------------------------------------------
# Comparatori, legi marginale, scoruri (copiate din gl649.py; definiții QL649 §5)
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
        ("1", "ExcesSE/U >= 0.20", t["excess_SE"] >= 0.20, t["excess_SE"]),
        ("2", "hitsSE > hitsB și hitsSE > hitsR", t["hits_SE"] > t["hits_B"] and t["hits_SE"] > t["hits_R"],
         [t["hits_SE"], t["hits_B"], t["hits_R"]]),
        ("3", "logSE−logU > 0 și logSE−logB > 0", t["log_SE"] - t["log_U"] > 0 and t["log_SE"] - t["log_B"] > 0,
         [t["log_SE"] - t["log_U"], t["log_SE"] - t["log_B"]]),
        ("4", "BrierSE < BrierU, BrierB, BrierR", t["brier_SE"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
         [t["brier_SE"], t["brier_U"], t["brier_B"], t["brier_R"]]),
        ("5", "ambele jumătăți: exces > 0 și hitsSE−hitsB > 0",
         all(h["excess_SE"] > 0 and h["hits_SE"] - h["hits_B"] > 0 for h in (h1, h2)),
         [[h["excess_SE"], h["hits_SE"] - h["hits_B"]] for h in (h1, h2)]),
        ("6", "ambele jumătăți: logSE−logB > 0", all(h["log_SE"] - h["log_B"] > 0 for h in (h1, h2)),
         [h["log_SE"] - h["log_B"] for h in (h1, h2)]),
    ]
    return [{"gate": a, "rule": b, "pass": bool(c), "value": d} for a, b, c, d in g]


def summarize(sl: slice, S: dict) -> dict:
    n = int(S["y"][sl].shape[0])
    o = {"targets": n}
    for name in ("SE", "B", "R"):
        o[f"hits_{name}"] = int(S[f"hits_{name}"][sl].sum())
        o[f"excess_{name}"] = o[f"hits_{name}"] / n - 36.0 / 49.0 if n else 0.0
    for name in ("SE", "B", "R", "U"):
        o[f"log_{name}"] = float(S[f"log_{name}"][sl].sum())
        o[f"brier_{name}"] = float(S[f"brier_{name}"][sl].sum())
    return o


# ---------------------------------------------------------------------------
# Numărări pe anotimpuri, predicții și scor pe o istorie (reală sau sintetică)
# ---------------------------------------------------------------------------
def season_prefix(steps: list[np.ndarray], seasons: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """C4[k] (4×49), N4[k] (4): numărări / extrageri pe anotimpuri din pașii < k."""
    K = len(steps)
    C4 = np.zeros((K + 1, NS, N49), dtype=np.int64)
    N4 = np.zeros((K + 1, NS), dtype=np.int64)
    for s in range(K):
        C4[s + 1] = C4[s]
        N4[s + 1] = N4[s]
        C4[s + 1, seasons[s]] += steps[s].sum(0).astype(np.int64)
        N4[s + 1, seasons[s]] += steps[s].shape[0]
    return C4, N4


def targets_of(steps: list[np.ndarray], warmup: int):
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    t_step = np.concatenate([np.full(steps[k].shape[0], k, dtype=np.int64) for k in ks])
    y = np.concatenate([steps[k] for k in ks]).astype(np.float64)
    return ks, t_step, y


def predict(steps: list[np.ndarray], seasons: np.ndarray, warmup: int = WARMUP, ta2: Fraction = TA2,
            tb2: Fraction = TB2, keep_exact: bool = False) -> dict:
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    C4, N4 = season_prefix(steps, seasons)
    p_float = np.zeros((len(ks), N49))
    tickets = np.zeros((len(ks), K6), dtype=np.int64)
    sum_ok, range_ok, wsum_ok = True, True, True
    exact, wexact = [], []
    for i, k in enumerate(ks):
        r = se_predict_counts(C4[k], N4[k], int(seasons[k]), ta2, tb2)
        p = r["p"]
        sum_ok &= (sum(p) == K6)
        range_ok &= all(0 < t < 1 for t in p)
        wsum_ok &= (sum(r["w"].values()) < 1)
        p_float[i] = [float(t) for t in p]
        tickets[i] = ticket_exact(p)
        if keep_exact:
            exact.append([f"{t.numerator}/{t.denominator}" for t in p])
            wexact.append({str(f): f"{w.numerator}/{w.denominator}" for f, w in r["w"].items()})
    cmp_ = comparators(steps, ks)
    return {"ks": ks, "p_SE": p_float, "ticket_SE": tickets, "piB": cmp_["piB"], "piR": cmp_["piR"],
            "ticket_B": top6(cmp_["piB"]), "ticket_R": top6(cmp_["piR"]), "phi": seasons[ks].astype(np.int64),
            "n4": N4[ks], "sum_exact_ok": bool(sum_ok), "range_ok": bool(range_ok), "wsum_lt1_ok": bool(wsum_ok),
            "exact": exact, "w_exact": wexact}


def score(steps: list[np.ndarray], pred: dict, warmup: int = WARMUP) -> dict:
    ks, t_step, y = targets_of(steps, warmup)
    assert np.array_equal(ks, pred["ks"])
    row = t_step - warmup
    laws = {"SE": marginal_q(pred["p_SE"] / K6), "B": marginal_q(pred["piB"]), "R": marginal_q(pred["piR"])}
    tick = {"SE": pred["ticket_SE"], "B": pred["ticket_B"], "R": pred["ticket_R"]}
    S = {"y": y}
    for name in ("SE", "B", "R"):
        sb = score_block(laws[name][row], tick[name][row], y)
        S[f"hits_{name}"], S[f"log_{name}"], S[f"brier_{name}"] = sb["hits"], sb["log"], sb["brier"]
    sU = score_block(np.full_like(y, 6.0 / N49), None, y)
    S["log_U"], S["brier_U"] = sU["log"], sU["brier"]
    n = y.shape[0]
    half = n // 2
    t, h1, h2 = summarize(slice(0, n), S), summarize(slice(0, half), S), summarize(slice(half, n), S)
    g = gates(t, h1, h2)
    passed = sum(x["pass"] for x in g)
    tS = tick["SE"]
    lawS = laws["SE"]
    phi_t = pred["phi"][row]
    by_season = {}
    for f in range(NS):
        m = phi_t == f
        nt = int(m.sum())
        by_season[SEASON_NAMES[f]] = {
            "targets": nt, "hits_SE": int(S["hits_SE"][m].sum()), "hits_B": int(S["hits_B"][m].sum()),
            "hits_R": int(S["hits_R"][m].sum()),
            "excess_SE": float(S["hits_SE"][m].sum() / nt - 36 / 49) if nt else None,
            "logSE_minus_B": float((S["log_SE"][m] - S["log_B"][m]).sum()),
            "logSE_minus_U": float((S["log_SE"][m] - S["log_U"][m]).sum())}
    return {
        "n_targets": int(n), "n_steps_predicted": int(ks.shape[0]), "total": t, "half1": h1, "half2": h2,
        "gates": g, "gates_passed": int(passed),
        "verdict": "SE_PROMOVAT_EXPLORATORIU" if passed == 6 else "SE_NO_PROMOTION_EXPLORATORY",
        "tickets_changed_vs_B_steps": int((tS != tick["B"]).any(-1).sum()),
        "tickets_changed_vs_R_steps": int((tS != tick["R"]).any(-1).sum()),
        "tickets_changed_vs_B_targets": int((tS[row] != tick["B"][row]).any(-1).sum()),
        "tickets_changed_vs_R_targets": int((tS[row] != tick["R"][row]).any(-1).sum()),
        "by_target_season": by_season,
        "match_dist_SE": np.bincount(S["hits_SE"].astype(int), minlength=7).tolist(),
        "match_expected_U": (hyper_pmf() * n).tolist(),
        "law_SE_in_01": bool(((lawS > 0) & (lawS < 1)).all()),
        "p_SE_in_01": bool(((pred["p_SE"] > 0) & (pred["p_SE"] < 1)).all()),
        "per_target": {"step": t_step.tolist(), "hits_SE": S["hits_SE"].astype(int).tolist(),
                       "log_SE": S["log_SE"].tolist()},
    }


def g_statistic(steps: list[np.ndarray], seasons: np.ndarray) -> float:
    """G = 2 Σ c_{jφ} ln(c_{jφ} / (6 n_φ / 49)) pe întreaga istorie (§6, descriptiv)."""
    C4, N4 = season_prefix(steps, seasons)
    c, n = C4[-1].astype(float), N4[-1].astype(float)
    e = 6.0 * n[:, None] / N49
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(c > 0, c * np.log(c / e), 0.0)
    return float(2.0 * t.sum())


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
    seasons = np.array([season_of(d) for d in ds.step_dates], dtype=np.int64)
    meta = {"source": ds.source, "source_sha256": ds.source_sha256, "n_draws": ds.n_draws, "n_steps": ds.n_steps,
            "parser_sha256": sha256_file(QL / "parser.py"), "first_date": ds.step_dates[0],
            "last_date": ds.step_dates[-1]}
    return steps, seasons, ds.step_dates, meta


def real_step_structure() -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Structura pașilor (extrageri pe zi) și anotimpurile datelor — inventar calendaristic, fără numere."""
    sys.path.insert(0, str(QL))
    import parser as P  # noqa: E402
    recs, _ = P.load_records(P.DEFAULT_SOURCE)
    clean, _ = P.clean_records(recs)
    dates = [r["draw_date"] for r in clean]
    sizes, sdates = [], []
    for i, d in enumerate(dates):
        if i == 0 or d != dates[i - 1]:
            sizes.append(1)
            sdates.append(d)
        else:
            sizes[-1] += 1
    return np.array(sizes, dtype=np.int64), np.array([season_of(d) for d in sdates], dtype=np.int64), sdates


def synthetic_steps(sizes: np.ndarray, seed, seasons: np.ndarray | None = None,
                    pmat: np.ndarray | None = None) -> list[np.ndarray]:
    """Extrageri uniforme sau (dacă pmat este dat) alegere secvențială ponderată cu p(φ) al anotimpului."""
    rng = np.random.default_rng(seed)
    out = []
    for s, sz in enumerate(sizes):
        a = np.zeros((int(sz), N49))
        for i in range(int(sz)):
            if pmat is None:
                a[i, rng.choice(N49, K6, replace=False)] = 1.0
            else:
                w = pmat[seasons[s]]
                a[i, rng.choice(N49, K6, replace=False, p=w / w.sum())] = 1.0
        out.append(a)
    return out


def block_history(blocks: list[tuple[str, list[int]]]) -> tuple[list[np.ndarray], list[str]]:
    """Construcția rotativă pe blocuri sezoniere (§4): o extragere pe zi de la data de start."""
    steps, dates = [], []
    for start, c in blocks:
        n = sum(c) // K6
        assert sum(c) == K6 * n and max(c) <= n
        L = [j + 1 for j in range(N49) for _ in range(c[j])]
        d0 = dt.date.fromisoformat(start)
        for i in range(n):
            s = {L[i + r * n] for r in range(K6)}
            assert len(s) == K6
            a = np.zeros((1, N49))
            a[0, [t - 1 for t in s]] = 1.0
            steps.append(a)
            dates.append((d0 + dt.timedelta(days=i)).isoformat())
    assert dates == sorted(dates) and len(set(dates)) == len(dates)
    return steps, dates


def predict_at(steps: list[np.ndarray], dates: list[str], target_date: str) -> dict:
    """Predicția pentru un pas-țintă cu data dată, după istoria completă (k = len(steps))."""
    seasons = np.array([season_of(d) for d in dates] + [season_of(target_date)], dtype=np.int64)
    C4, N4 = season_prefix(steps, seasons[:-1])
    k = len(steps)
    r = se_predict_counts(C4[k], N4[k], int(seasons[k]))
    cmp_ = comparators(steps, np.array([k]))
    tot = C4[k].sum(0)
    return {"p": r["p"], "w": r["w"], "ticket_SE": ticket_exact(r["p"]), "piB": cmp_["piB"][0],
            "piR": cmp_["piR"][0], "ew": cmp_["ew"][0], "ticket_B": top6(cmp_["piB"])[0].tolist(),
            "ticket_R": top6(cmp_["piR"])[0].tolist(), "counts_total": tot.tolist(), "C4": C4[k].tolist(),
            "N4": N4[k].tolist(), "phi": int(seasons[k])}


# ---------------------------------------------------------------------------
# Calificare Q1–Q6 (§4)
# ---------------------------------------------------------------------------
def random_counts(rng, n: int) -> list[int]:
    c = [0] * N49
    for _ in range(n):
        for t in rng.choice(N49, K6, replace=False):
            c[int(t)] += 1
    return c


def q1() -> dict:
    rng = np.random.default_rng([649, 10, 1])
    prng = np.random.default_rng([649, 10, 11])
    perms = [[int(t) + 1 for t in prng.permutation(N49)] for _ in range(3)]
    det = {"instances": 40, "closed_eq_direct": True, "sum6": True, "wsum_lt1": True, "range01": True,
           "bl_orthogonality": True, "equivariance": True, "cases_phi_absent": 0, "cases_other_absent": 0}
    for inst in range(40):
        phi = int(rng.integers(0, NS))
        ns = [int(rng.integers(0, 121)) for _ in range(NS)]
        if inst < 5:
            ns[phi] = 0
        elif inst < 10:
            other = int(rng.choice([f for f in range(NS) if f != phi]))
            ns = [max(1, x) for x in ns]
            ns[other] = 0
        if sum(ns) == 0:
            ns[(phi + 1) % NS] = 1
        det["cases_phi_absent"] += int(ns[phi] == 0)
        det["cases_other_absent"] += int(any(ns[f] == 0 for f in range(NS) if f != phi))
        C4 = [random_counts(rng, ns[f]) for f in range(NS)]
        r = se_predict_counts(C4, ns, phi)
        rd = se_predict_counts(C4, ns, phi, direct=True)
        det["closed_eq_direct"] &= (r["w"] == rd["w"]) and (r["p"] == rd["p"])
        det["sum6"] &= (sum(r["p"]) == K6)
        det["wsum_lt1"] &= (sum(r["w"].values()) < 1)
        det["range01"] &= all(0 < t < 1 for t in r["p"])
        if 10 <= inst < 15:
            O = sorted(r["w"])
            D = {f: TB2 + SIGMA0_2 / ns[f] for f in O}
            for psi in O:
                for l in range(N49):
                    Pe = [Fraction(1 if i == l else 0) - Fraction(1, N49) for i in range(N49)]
                    applied = [sum(r["w"][f] * (TA2 + (D[psi] if f == psi else 0)) for f in O) * Pe[i]
                               for i in range(N49)]
                    target = [(TA2 + (TB2 if psi == phi else 0)) * Pe[i] for i in range(N49)]
                    det["bl_orthogonality"] &= (applied == target)
        for perm in perms:
            Cp = [[0] * N49 for _ in range(NS)]
            for f in range(NS):
                for j in range(N49):
                    Cp[f][perm[j] - 1] = C4[f][j]
            rp = se_predict_counts(Cp, ns, phi)
            det["equivariance"] &= all(rp["p"][perm[j] - 1] == r["p"][j] for j in range(N49))
    ok = all(det[k] for k in ("closed_eq_direct", "sum6", "wsum_lt1", "range01", "bl_orthogonality", "equivariance"))
    ok &= det["cases_phi_absent"] >= 5 and det["cases_other_absent"] >= 5
    return {"pass": bool(ok), "detail": det}


def relabel(steps: list[np.ndarray], perm: list[int]) -> list[np.ndarray]:
    idx = np.array([perm[j] - 1 for j in range(N49)])
    out = []
    for s in steps:
        b = np.zeros_like(s)
        b[:, idx] = s
        out.append(b)
    return out


def q2_q3_q4(sizes: np.ndarray, seasons: np.ndarray) -> tuple[dict, dict, dict]:
    t0 = time.time()
    steps = synthetic_steps(sizes, [649, 10, 999])
    pred = predict(steps, seasons)
    laws = marginal_q(pred["p_SE"] / K6)
    ks = pred["ks"]
    sample = [int(k) for k in ks if (k - WARMUP) % 97 == 0]
    C4, N4 = season_prefix(steps, seasons)
    direct_ok = True
    for k in sample:
        direct_ok &= (se_predict_counts(C4[k], N4[k], int(seasons[k]))["p"]
                      == se_predict_counts(C4[k], N4[k], int(seasons[k]), direct=True)["p"])
    d2 = {"steps": int(len(ks)), "sum_exact_ok": pred["sum_exact_ok"], "range_ok": pred["range_ok"],
          "wsum_lt1_ok": pred["wsum_lt1_ok"], "law_in_01": bool(((laws > 0) & (laws < 1)).all()),
          "closed_eq_direct_sample": bool(direct_ok), "sample_steps": len(sample),
          "p_min": float(pred["p_SE"].min()), "p_max": float(pred["p_SE"].max()), "run_seconds": time.time() - t0}
    Q2 = {"pass": bool(d2["sum_exact_ok"] and d2["range_ok"] and d2["law_in_01"] and direct_ok), "detail": d2}
    # Q3: istoria trunchiată la < k (recalculată din lista trunchiată)
    q3_ok = True
    for k in sample:
        trunc = steps[:k]
        Ct, Nt = season_prefix(trunc, seasons[:k])
        p_tr = se_predict_counts(Ct[k], Nt[k], int(seasons[k]))["p"]
        p_full = se_predict_counts(C4[k], N4[k], int(seasons[k]))["p"]
        q3_ok &= (p_tr == p_full) and (ticket_exact(p_tr) == pred["ticket_SE"][k - WARMUP].tolist())
    Q3 = {"pass": bool(q3_ok), "detail": {"sample_steps": len(sample)}}
    # Q4(a): echivarianță la o permutare aleatoare fixă a etichetelor
    perm = [int(t) + 1 for t in np.random.default_rng([649, 10, 4]).permutation(N49)]
    st_p = relabel(steps, perm)
    Cp, Np = season_prefix(st_p, seasons)
    q4a = True
    for k in sample:
        p = se_predict_counts(C4[k], N4[k], int(seasons[k]))["p"]
        pp = se_predict_counts(Cp[k], Np[k], int(seasons[k]))["p"]
        q4a &= all(pp[perm[j] - 1] == p[j] for j in range(N49))
    # Q4(b): permutarea extragerilor între pașii cu o singură extragere din același anotimp
    kf = len(steps) - 1
    single = [s for s in range(kf) if steps[s].shape[0] == 1]
    rng = np.random.default_rng([649, 10, 44])
    st_b = list(steps)
    for f in range(NS):
        idx = [s for s in single if seasons[s] == f]
        sh = rng.permutation(len(idx))
        for a, b in zip(idx, [idx[t] for t in sh]):
            st_b[a] = steps[b]
    Cb, Nb = season_prefix(st_b, seasons)
    p_fin = se_predict_counts(C4[kf], N4[kf], int(seasons[kf]))["p"]
    p_b = se_predict_counts(Cb[kf], Nb[kf], int(seasons[kf]))["p"]
    q4b = (p_b == p_fin) and any(not np.array_equal(st_b[s], steps[s]) for s in single)
    # descriptiv: permutare între anotimpuri diferite
    st_x = list(steps)
    sh = rng.permutation(len(single))
    for a, b in zip(single, [single[t] for t in sh]):
        st_x[a] = steps[b]
    Cx, Nx = season_prefix(st_x, seasons)
    p_x = se_predict_counts(Cx[kf], Nx[kf], int(seasons[kf]))["p"]
    dev_x = max(abs(float(p_x[j] - p_fin[j])) for j in range(N49))
    Q4 = {"pass": bool(q4a and q4b), "detail": {"sample_steps": len(sample), "label_equivariance": bool(q4a),
                                                "within_season_order_invariance": bool(q4b),
                                                "descriptive_cross_season_perm_max_abs_dp": dev_x}}
    return Q2, Q3, Q4


BLOCK_START = {0: "2000-12-01", 1: "2001-03-01", 2: "2001-06-01", 3: "2001-09-01"}
TARGET_WINTER, TARGET_SUMMER = "2002-01-15", "2002-07-15"


def fixture_F5() -> list[tuple[str, list[int]]]:
    blocks = []
    for f in range(NS):
        c = [6] * N49
        if f == 0:
            c[5 - 1], c[9 - 1] = 9, 3
        if f == 2:
            c[5 - 1], c[9 - 1] = 3, 9
        blocks.append((BLOCK_START[f], c))
    return blocks


def fixture_F6() -> list[tuple[str, list[int]]]:
    cw = [0] * 6 + [6] * 37 + [12] * 6
    cs = [12] * 6 + [6] * 37 + [0] * 6
    return [(BLOCK_START[0], cw), (BLOCK_START[2], cs)]


def q5() -> dict:
    steps, dates = block_history(fixture_F5())
    r = predict_at(steps, dates, TARGET_WINTER)
    rs = predict_at(steps, dates, TARGET_SUMMER)
    n = 49
    D = TB2 + SIGMA0_2 / n
    gap_expected = 6 * TB2 / (49 * D)
    p = r["p"]
    law = marginal_q(np.array([float(t) for t in p]) / K6)
    lawB = marginal_q(r["piB"])
    rng = np.random.default_rng([649, 10, 5])
    st2 = []
    for b in range(NS):
        blk = steps[49 * b:49 * (b + 1)]
        st2 += [blk[i] for i in rng.permutation(49)]
    r2 = predict_at(st2, dates, TARGET_WINTER)
    tot = r["counts_total"]
    det = {"N4": r["N4"], "phi_target": r["phi"], "totals_all_equal": len(set(tot)) == 1, "c5_eq_c9": tot[4] == tot[8],
           "B_law_5_eq_9": bool(lawB[4] == lawB[8]),
           "gap_exact_eq_closed_form": p[4] - p[8] == gap_expected, "gap_float": float(p[4] - p[8]),
           "symmetric_about_p0": p[4] - P0 == P0 - p[8],
           "others_eq_p0": all(p[j] == P0 for j in range(N49) if j not in (4, 8)),
           "sign_p5_gt_p9": p[4] > p[8], "law_gap": float(law[4] - law[8]),
           "law_gap_ge_1e-3": bool(law[4] - law[8] >= 1e-3),
           "summer_target_gap_flips_exact": rs["p"][4] - rs["p"][8] == -gap_expected, "summer_phi": rs["phi"],
           "within_block_order_invariance_exact": r2["p"] == p and any(
               not np.array_equal(a, b) for a, b in zip(st2, steps)),
           "tb2_over_D": float(TB2 / D)}
    ok = all(det[k] for k in ("totals_all_equal", "c5_eq_c9", "B_law_5_eq_9", "gap_exact_eq_closed_form",
                              "symmetric_about_p0", "others_eq_p0", "sign_p5_gt_p9", "law_gap_ge_1e-3",
                              "summer_target_gap_flips_exact", "within_block_order_invariance_exact"))
    ok &= r["phi"] == 0 and rs["phi"] == 2 and r["N4"] == [49, 49, 49, 49]
    return {"pass": bool(ok), "detail": det}


def q6() -> dict:
    steps, dates = block_history(fixture_F6())
    r = predict_at(steps, dates, TARGET_WINTER)
    n = 49
    D = TB2 + SIGMA0_2 / n
    delta = 6 * TB2 / (49 * D)
    p = r["p"]
    ew = r["ew"]
    exp_ok = (all(p[j] == P0 + delta for j in range(43, 49)) and all(p[j] == P0 - delta for j in range(6))
              and all(p[j] == P0 for j in range(6, 43)))
    det = {"k": len(steps), "N4": r["N4"], "phi_target": r["phi"], "totals": sorted(set(r["counts_total"])),
           "ticket_SE": r["ticket_SE"], "ticket_B": r["ticket_B"], "ticket_R": r["ticket_R"],
           "p_values_exact_as_derived": bool(exp_ok), "delta_float": float(delta),
           "ew_1": float(ew[0]), "ew_1_lower_bound": 12 * 2 ** (-48 / 26),
           "max_ew_44_49": float(max(ew[43:49])), "ew_44_49_upper_bound": 12 * 2 ** (-49 / 26)}
    ok = (len(steps) == 98 and r["phi"] == 0 and r["N4"] == [49, 0, 49, 0] and det["totals"] == [12] and exp_ok
          and r["ticket_SE"] == [44, 45, 46, 47, 48, 49] and r["ticket_B"] == [1, 2, 3, 4, 5, 6]
          and ew[0] > max(ew[43:49]) and r["ticket_R"] != r["ticket_SE"])
    return {"pass": bool(ok), "detail": det}


def qualify() -> dict:
    log = []
    t0 = time.time()
    res = {}
    res["Q1"] = q1()
    log.append(f"Q1 {res['Q1']['pass']} {res['Q1']['detail']} ({time.time() - t0:.0f}s)")
    print(log[-1], flush=True)
    sizes, seasons, _ = real_step_structure()
    res["Q2"], res["Q3"], res["Q4"] = q2_q3_q4(sizes, seasons)
    for q in ("Q2", "Q3", "Q4"):
        log.append(f"{q} {res[q]['pass']} {res[q]['detail']} ({time.time() - t0:.0f}s)")
        print(log[-1], flush=True)
    res["Q5"] = q5()
    log.append(f"Q5 {res['Q5']['pass']} {res['Q5']['detail']}")
    print(log[-1], flush=True)
    res["Q6"] = q6()
    log.append(f"Q6 {res['Q6']['pass']} {res['Q6']['detail']}")
    print(log[-1], flush=True)
    names = {"Q1": "exactitate în Q (formă închisă = direct, Σ=6, ortogonalitate Bayes liniară, echivarianță)",
             "Q2": "identități pe univers nul complet", "Q3": "cauzalitate (trunchiat ≡ complet, exact)",
             "Q4": "echivarianță la etichete și invarianță la ordinea din anotimp",
             "Q5": "martor de informație (analitic, Derivarea B)", "Q6": "martor de decizie (analitic)"}
    checks = [{"id": q, "name": names[q], "pass": res[q]["pass"], "detail": res[q]["detail"]} for q in names]
    passed = sum(c["pass"] for c in checks)
    (HERE / "jurnal").mkdir(exist_ok=True)
    (HERE / "jurnal" / "calificare.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    return {"utc": utc_now(), "protocol_sha256": json.loads(SEAL.read_text())["sha256"],
            "code_sha256": sha256_file(Path(__file__)), "status": "SE_QUALIFIED" if passed == 6 else "SE_NOT_QUALIFIED",
            "passed": int(passed), "checks": checks, "seconds": time.time() - t0,
            "archive_numbers_used": False,
            "note": "Q2–Q4 citesc numai structura pașilor și anotimpurile datelor (calendar), fără numere."}


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
        print("REFUZ: backtestul unic SE649 a fost deja pornit (START.json există).")
        return 2
    seal = check_seal()
    qf = OUT / "CALIFICARE.json"
    if not qf.exists() or json.loads(qf.read_text())["status"] != "SE_QUALIFIED":
        print("REFUZ: calificarea lipsește sau nu este SE_QUALIFIED.")
        return 3
    steps, seasons, sdates, meta = load_real()
    start = {"utc": utc_now(), "protocol_sha256": seal["sha256"], "qualification_sha256": sha256_file(qf),
             "code_sha256": sha256_file(Path(__file__)),
             "config": {"tau_a2": str(TA2), "tau_b2": str(TB2), "sigma0_2": str(SIGMA0_2), "warmup": WARMUP,
                        "half_life_R": HALF_LIFE, "lambda0": LAM0, "seasons": "DJF/MAM/JJA/SON"}, **meta}
    write_json(run / "START.json", start)
    t0 = time.time()
    pred = predict(steps, seasons, keep_exact=True)
    tp = time.time() - t0
    npz = run / "PREDICTII.npz"
    np.savez(npz, ks=pred["ks"], p_SE=pred["p_SE"], ticket_SE=pred["ticket_SE"], piB=pred["piB"], piR=pred["piR"],
             ticket_B=pred["ticket_B"], ticket_R=pred["ticket_R"], phi=pred["phi"], n4=pred["n4"])
    exf = run / "PREDICTII_EXACTE.json.gz"
    with open(exf, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(json.dumps({"ks": pred["ks"].tolist(), "phi": pred["phi"].tolist(), "p_hat": pred["exact"],
                                 "w": pred["w_exact"]}).encode())
    psha, esha = sha256_file(npz), sha256_file(exf)
    write_json(run / "PREDICTII_SIGILIU.json", {"utc": utc_now(), "npz": npz.name, "npz_sha256": psha,
                                                "exact": exf.name, "exact_sha256": esha,
                                                "sum_exact_ok": pred["sum_exact_ok"], "range_ok": pred["range_ok"],
                                                "wsum_lt1_ok": pred["wsum_lt1_ok"]})
    P = dict(np.load(npz))
    P["phi"] = P["phi"].astype(np.int64)
    res = score(steps, P)
    consist = {"hits_B": res["total"]["hits_B"], "hits_R": res["total"]["hits_R"], "targets": res["n_targets"],
               "expected_BO649_GL649": [BO_HITS_B, BO_HITS_R, BO_TARGETS]}
    consist["ok"] = (consist["hits_B"], consist["hits_R"], consist["targets"]) == (BO_HITS_B, BO_HITS_R, BO_TARGETS)
    res["consistency_with_BO649_GL649"] = consist
    res["valid_run"] = bool(consist["ok"] and pred["sum_exact_ok"] and pred["range_ok"])
    res["p_exact_hits_SE_ge"] = exact_tail(res["total"]["hits_SE"], res["n_targets"])
    C4, N4 = season_prefix(steps, seasons)
    kf = len(steps)
    res["final_state"] = {"n_per_season": N4[kf].tolist(),
                          "weights_by_target_season": {SEASON_NAMES[f]: {SEASON_NAMES[g]: float(w) for g, w in
                                                                         se_weights(N4[kf], f).items()}
                                                       for f in range(NS)}}
    pl = P["p_SE"][-1]
    res["final_step"] = {"phi": int(P["phi"][-1]), "rel_dev_std": float((pl / float(P0) - 1).std()),
                         "rel_dev_min": float((pl / float(P0) - 1).min()),
                         "rel_dev_max": float((pl / float(P0) - 1).max())}
    res["G_label_x_season"] = g_statistic(steps, seasons)
    res.update({"start": start, "predictions_sha256": psha, "exact_predictions_sha256": esha, "predict_seconds": tp,
                "positive_claims_allowed": False})
    write_json(run / "REZULTATE.json", res)
    print(json.dumps({k: res[k] for k in ("verdict", "gates_passed", "n_targets", "valid_run")} |
                     {"total": res["total"], "consistency": consist}, indent=2))
    return 0


def run_null(M: int) -> int:
    check_seal()
    sizes, seasons, _ = real_step_structure()
    out = []
    for u in range(M):
        st = synthetic_steps(sizes, [649, 10, u])
        r = score(st, predict(st, seasons))
        t = r["total"]
        out.append({"u": u, "excess_SE": t["excess_SE"], "hits_SE": t["hits_SE"], "hits_B": t["hits_B"],
                    "hits_R": t["hits_R"], "logSE_minus_B": t["log_SE"] - t["log_B"],
                    "logSE_minus_U": t["log_SE"] - t["log_U"], "brier_SE_minus_U": t["brier_SE"] - t["brier_U"],
                    "gates_passed": r["gates_passed"], "gates": [g["pass"] for g in r["gates"]],
                    "tickets_changed_vs_B_targets": r["tickets_changed_vs_B_targets"],
                    "G_label_x_season": g_statistic(st, seasons)})
        print(f"u{u:03d} {out[-1]}", flush=True)
    write_json(OUT / "nule" / "SUMAR.json", {"utc": utc_now(), "M": M, "seed": "[649, 10, u]", "descriptive": True,
                                            "universes": out})
    return 0


def run_power(M1: int, M2: int) -> int:
    check_seal()
    sizes, seasons, _ = real_step_structure()
    Pm = np.eye(N49) - 1.0 / N49
    out = []
    for scale, M, base in ((0.2, M1, 1000), (0.1, M2, 2000)):
        for u in range(M):
            rng = np.random.default_rng([649, 10, base + u])
            a = rng.normal(0, 0.05, N49)
            b = rng.normal(0, scale, (NS, N49))
            pmat = np.stack([float(P0) * (1 + Pm @ (a + b[f])) for f in range(NS)])
            pmat = np.clip(pmat, 0.2 * float(P0), 1.8 * float(P0))
            st = synthetic_steps(sizes, [649, 10, base + u, 1], seasons=seasons, pmat=pmat)
            r = score(st, predict(st, seasons))
            t = r["total"]
            out.append({"scale_b": scale, "u": u, "excess_SE": t["excess_SE"], "excess_B": t["excess_B"],
                        "hits_SE": t["hits_SE"], "hits_B": t["hits_B"], "hits_R": t["hits_R"],
                        "logSE_minus_B": t["log_SE"] - t["log_B"], "logSE_minus_U": t["log_SE"] - t["log_U"],
                        "gates_passed": r["gates_passed"], "gates": [g["pass"] for g in r["gates"]],
                        "p_rel_sd_by_season": [float((pmat[f] / float(P0) - 1).std()) for f in range(NS)]})
            print(f"h{scale}-{u:03d} {out[-1]}", flush=True)
    write_json(OUT / "putere" / "SUMAR.json", {"utc": utc_now(), "M_prior_scale": M1, "M_half_scale": M2,
                                              "seed": "[649, 10, 1000+u] / [649, 10, 2000+u]", "descriptive": True,
                                              "generator": "alegere secvențială ponderată p_j(φ) a anotimpului datei",
                                              "universes": out})
    return 0


def run_sens() -> int:
    check_seal()
    if not (OUT / "backtest_unic" / "REZULTATE.json").exists():
        print("REFUZ: sensibilitatea descriptivă se rulează după backtestul unic.")
        return 2
    steps, seasons, _, meta = load_real()
    rows = []
    for nm_a, nm_b, ta2, tb2 in SENS:
        r = score(steps, predict(steps, seasons, ta2=ta2, tb2=tb2))
        t = r["total"]
        rows.append({"tau_a": nm_a, "tau_b": nm_b, "hits_SE": t["hits_SE"], "excess_SE": t["excess_SE"],
                     "logSE_minus_U": t["log_SE"] - t["log_U"], "logSE_minus_B": t["log_SE"] - t["log_B"],
                     "brier_SE": t["brier_SE"], "gates_passed": r["gates_passed"],
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
        return 0 if q["status"] == "SE_QUALIFIED" else 1
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
