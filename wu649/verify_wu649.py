"""Verificator independent WU649 (PREINREGISTRARE_WU649.md §7).

NU importă wu649.py, bo649.py, engine.py, parser.py sau validare.py. Reparsează JSONL după
QL649 §1 și recalculează totul într-o formulare diferită: cuadratură Gauss–Legendre (200 de
noduri) pe u ∈ (0,1) în spațiul probabilităților (forma 3 cu prefactorul W_c u^{W_c−1}),
derivate în coordonatele (w_S, W_c), programare dinamică proprie pentru π_j, Newton propriu
pentru re-optimizări, comparatori (R prin recursie), scoruri, porți și verdict. Compară apoi cu
artefactele sigilate din rezultate/backtest_unic/.

STARE: `main()` este cod condiționat NEVALIDAT și NERULAT. Calificarea WU649 s-a încheiat
`WU_NOT_QUALIFIED` (5/6, Q6 eșuat), deci backtestul unic nu există și `main()` nu are ce
verifica. Funcțiile de formulare independentă (lik_terms, post, newton, incl) sunt reutilizate
de verify_necalificare_wu649.py pe fixture-ul construit, fără arhiva reală.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"

import datetime
import hashlib
import itertools
import json
import math
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUN = HERE / "rezultate" / "backtest_unic"
SRC = (HERE.parent.parent / "predictie_numere" / "probe_date" / "extrageri_649.jsonl").resolve()
SIG, WARM, HL = 0.2, 100, 26.0
U, UW = np.polynomial.legendre.leggauss(200)
U, UW = 0.5 * (U + 1.0), 0.5 * UW
LNU = np.log(U)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse() -> tuple[np.ndarray, np.ndarray]:
    rows = []
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(o, dict):
            continue
        k, d, ns = o.get("draw_key"), o.get("draw_date"), o.get("numbers_sorted")
        if not (isinstance(k, str) and k and isinstance(d, str)):
            continue
        try:
            datetime.date.fromisoformat(d)
        except ValueError:
            continue
        if not (isinstance(ns, list) and len(ns) == 6 and all(type(x) is int and 1 <= x <= 49 for x in ns)
                and len(set(ns)) == 6):
            continue
        rows.append((d, k, tuple(sorted(ns))))
    keys, sets, uniq = set(), set(), []
    for d, k, ns in rows:
        if k in keys or (d, ns) in sets:
            continue
        keys.add(k)
        sets.add((d, ns))
        uniq.append((d, k, ns))
    uniq.sort(key=lambda r: (r[0], r[1]))
    Y = np.zeros((len(uniq), 49))
    for i, (_, _, ns) in enumerate(uniq):
        Y[i, [x - 1 for x in ns]] = 1.0
    off = [0]
    for i in range(1, len(uniq)):
        if uniq[i][0] != uniq[i - 1][0]:
            off.append(i)
    off.append(len(uniq))
    return Y, np.array(off)


# ---------------------------------------------------------------------------
# Formulare independentă: forma 3 în u, Gauss–Legendre, coordonate (w_S, W_c)
# ---------------------------------------------------------------------------
def lik_terms(theta: np.ndarray, Y: np.ndarray, want_h: bool = True):
    w = np.exp(theta)
    n = Y.shape[0]
    MEM = np.array([np.flatnonzero(y) for y in Y])          # [n,6]
    Wn = (1.0 - Y) * w[None, :]
    Wc = Wn.sum(1)
    wm = w[MEM]                                             # [n,6]
    uw = U[None, None, :] ** wm[:, :, None]                 # u^{w_i}
    one = 1.0 - uw
    F = Wc[:, None] * U[None, :] ** (Wc[:, None] - 1.0) * one.prod(1) * UW[None, :]   # [n,200]
    P = F.sum(1)
    R = F / P[:, None]
    a = -uw * LNU / one                                     # ∂ log F / ∂ w_i
    c = 1.0 / Wc[:, None] + LNU[None, :]                    # ∂ log F / ∂ W_c
    Ea = (R[:, None, :] * a).sum(2)
    Ec = (R * c).sum(1)
    gw_m = Ea                                               # ∂logP/∂w_i
    gc = Ec                                                 # ∂logP/∂W_c
    g = np.zeros(49)
    np.add.at(g, MEM, wm * gw_m)
    g += (gc[:, None] * Wn).sum(0)
    if not want_h:
        return np.log(P), g, None
    b = -(LNU ** 2) * uw / one ** 2
    Eaa = np.einsum("nm,nim,njm->nij", R, a, a)
    Eb = (R[:, None, :] * b).sum(2)
    Hmm = Eaa - Ea[:, :, None] * Ea[:, None, :]
    idx = np.arange(6)
    Hmm[:, idx, idx] += Eb
    Hmc = (R[:, None, :] * a * c[:, None, :]).sum(2) - Ea * Ec[:, None]
    Hcc = (R * (c * c - 1.0 / Wc[:, None] ** 2)).sum(1) - Ec ** 2
    H = np.zeros((49, 49))
    T = wm[:, :, None] * wm[:, None, :] * Hmm
    T[:, idx, idx] += wm * gw_m
    np.add.at(H, (MEM[:, :, None], MEM[:, None, :]), T)
    A = np.zeros((n, 49))
    np.put_along_axis(A, MEM, wm * Hmc, axis=1)
    X = A.T @ Wn
    H += X + X.T
    H += (Wn * Hcc[:, None]).T @ Wn
    H += np.diag((gc[:, None] * Wn).sum(0))
    return np.log(P), g, H


def post(theta, Y, want_h=True):
    lP, g, H = lik_terms(theta, Y, want_h)
    lp = lP.sum() - theta @ theta / (2 * SIG * SIG)
    g = g - theta / SIG ** 2
    if H is not None:
        H = H - np.eye(49) / SIG ** 2
    return lp, g, H


def newton(Y):
    th = np.zeros(49)
    for _ in range(300):
        lp, g, H = post(th, Y)
        if np.abs(g).max() <= 1e-9:
            break
        d = np.linalg.solve(-H, g)
        st = 1.0
        while st > 1e-12:
            lp2 = post(th + st * d, Y, False)[0]
            if lp2 >= lp - 1e-9:
                break
            st /= 2
        th = th + st * d
    return th


def incl(theta: np.ndarray) -> np.ndarray:
    w = np.exp(theta)
    out = np.empty(49)
    pu = U[None, :] ** w[:, None]                           # u^{w_l}, [49,200]
    for j in range(49):
        dp = np.zeros((6, U.shape[0]))
        dp[0] = 1.0
        for l in range(49):
            if l == j:
                continue
            arr, stay = 1.0 - pu[l], pu[l]
            dp[1:] = dp[1:] * stay + dp[:-1] * arr
            dp[0] = dp[0] * stay
        out[j] = (w[j] * U ** (w[j] - 1.0) * dp.sum(0) * UW).sum()
    return out


def p_orders(S, w) -> float:
    W = w.sum()
    tot = 0.0
    for perm in itertools.permutations(S):
        pr, rem = 1.0, W
        for i in perm:
            pr *= w[i] / rem
            rem -= w[i]
        tot += pr
    return tot


_C: dict = {}


def _step_check(i: int):
    k = int(_C["ks"][i])
    Yk = _C["Y"][: _C["off"][k]]
    th = _C["theta"][i]
    lp, g, H = post(th, Yk)
    try:
        np.linalg.cholesky(-H)
        nd = True
    except np.linalg.LinAlgError:
        nd = False
    q = incl(th)
    dth = None
    if i % 25 == 0:
        dth = float(np.abs(newton(Yk) - th).max())
    return i, float(np.abs(g).max()), nd, q, dth


def law(pi: np.ndarray) -> np.ndarray:
    base = 6 / 49
    d = 6 * pi - base
    lam = np.full(pi.shape[0], 0.5)
    for t in range(pi.shape[0]):
        for x in d[t]:
            if x > 0:
                lam[t] = min(lam[t], (1 - 1e-4 - base) / x)
            elif x < 0:
                lam[t] = min(lam[t], (base - 1e-4) / (-x))
    return base + lam[:, None] * d


def tick(score: np.ndarray) -> np.ndarray:
    out = np.empty((score.shape[0], 6), dtype=np.int64)
    for t in range(score.shape[0]):
        idx = sorted(range(49), key=lambda j: (-score[t, j], j))[:6]
        out[t] = sorted(j + 1 for j in idx)
    return out


def main() -> int:
    checks = []

    def chk(name, ok, val=None):
        checks.append({"check": name, "pass": bool(ok), "value": val})

    start = json.loads((RUN / "START.json").read_text())
    res = json.loads((RUN / "REZULTATE.json").read_text())
    seal = json.loads((HERE / "SIGILIU_PROTOCOL_WU649.json").read_text())
    aseal = json.loads((HERE / "SIGILIU_AMENDAMENT_01.json").read_text())
    psig = json.loads((RUN / "PREDICTII_SIGILIU.json").read_text())
    chk("protocol_sha_file_eq_seal", sha(HERE / "PREINREGISTRARE_WU649.md") == seal["sha256"])
    chk("amendment01_sha_file_eq_seal", sha(HERE / "AMENDAMENT_01.md") == aseal["sha256"] == start["amendment01_sha256"])
    chk("start_protocol_sha_eq_seal", start["protocol_sha256"] == seal["sha256"])
    chk("seals_before_start", seal["sealed_at_utc"] < aseal["sealed_at_utc"] < start["utc"],
        [seal["sealed_at_utc"], aseal["sealed_at_utc"], start["utc"]])
    qual = json.loads((HERE / "rezultate" / "CALIFICARE.json").read_text())
    chk("qualified_before_start", qual["status"] == "WU_QUALIFIED" and qual["passed"] == 6 and qual["utc"] < start["utc"])
    chk("qualification_sha_eq_start", sha(HERE / "rezultate" / "CALIFICARE.json") == start["qualification_sha256"])
    chk("predictions_sha_eq_seal", sha(RUN / "PREDICTII.npz") == psig["sha256"] == res["predictions_sha256"])
    chk("source_sha", sha(SRC) == start["source_sha256"], start["source_sha256"])
    Y, off = parse()
    K = off.shape[0] - 1
    chk("n_draws", Y.shape[0] == start["n_draws"] == 2595, Y.shape[0])
    chk("n_steps", K == start["n_steps"] == 2527, K)
    cfg = start["config"]
    chk("config", cfg["sigma"] == SIG and cfg["warmup"] == WARM and cfg["half_life_R"] == HL)

    P = np.load(RUN / "PREDICTII.npz")
    ks = np.arange(WARM, K)
    chk("ks", np.array_equal(P["ks"], ks))
    chk("model_certificates_all", bool(P["cert"].all()) and float(P["gnorm"].max()) <= 1e-8,
        float(P["gnorm"].max()))
    theta, qM = P["theta"], P["q_WU"]
    chk("sum_theta_zero", float(np.abs(theta.sum(1)).max()) <= 1e-7, float(np.abs(theta.sum(1)).max()))

    _C.update({"ks": ks, "Y": Y, "off": off, "theta": theta})
    ctx = mp.get_context("fork")
    with ctx.Pool(max(1, min(22, (os.cpu_count() or 2) - 2))) as pool:
        out = sorted(pool.map(_step_check, range(len(ks)), chunksize=8))
    gmax = max(o[1] for o in out)
    nd_all = all(o[2] for o in out)
    qV = np.stack([o[3] for o in out])
    dths = [o[4] for o in out if o[4] is not None]
    chk("indep_gradient_all_steps_le_1e-6", gmax <= 1e-6, gmax)
    chk("indep_hessian_nd_all_steps", nd_all)
    dq = float(np.abs(qV - qM).max())
    chk("q_WU_max_abs_diff_le_1e-9", dq <= 1e-9, dq)
    chk("sum_q_eq_6", float(np.abs(qV.sum(1) - 6).max()) < 1e-9, float(np.abs(qV.sum(1) - 6).max()))
    chk("reopt_every25_dtheta_le_1e-7", len(dths) == len(range(0, len(ks), 25)) and max(dths) <= 1e-7,
        [len(dths), max(dths)])

    # identitatea cursei (forma 1, 720 de ordini) la θ̂ final, 200 de extrageri reale eșantionate fix
    rng = np.random.default_rng([649, 8, 7])
    samp = np.sort(rng.choice(Y.shape[0], 200, replace=False))
    wf = np.exp(theta[-1])
    lPq = lik_terms(theta[-1], Y[samp], want_h=False)[0]
    rel = max(abs(p_orders(list(np.flatnonzero(Y[i])), wf) - math.exp(lPq[t])) / math.exp(lPq[t])
              for t, i in enumerate(samp))
    chk("race_identity_720_orders_rel_le_1e-10", rel <= 1e-10, rel)

    # comparatori: B din prefix, R prin recursie
    S = np.stack([Y[off[s]:off[s + 1]].sum(0) for s in range(K)])
    c = np.cumsum(np.vstack((np.zeros((1, 49)), S)), 0)
    ew = np.zeros((K + 1, 49))
    gm = 2.0 ** (-1.0 / HL)
    for k in range(1, K + 1):
        ew[k] = ew[k - 1] * gm + S[k - 1]
    piB = (c[ks] + 1) / (c[ks] + 1).sum(1, keepdims=True)
    piR = (ew[ks] + 0.5) / (ew[ks] + 0.5).sum(1, keepdims=True)
    chk("piB_diff", float(np.abs(piB - P["piB"]).max()) < 1e-12)
    chk("piR_diff", float(np.abs(piR - P["piR"]).max()) < 1e-9)
    tW = tick(qM)
    chk("ticket_WU_rule_on_saved_q", np.array_equal(tW, P["ticket_WU"]))
    marg = []
    for t in range(len(ks)):
        inside = tW[t] - 1
        rest = np.setdiff1d(np.arange(49), inside)
        marg.append(qV[t, inside].min() - qV[t, rest].max())
    chk("ticket_WU_valid_top6_under_indep_q", min(marg) >= -1e-9, float(min(marg)))
    tB, tR = tick(piB), tick(piR)
    chk("ticket_B_exact", np.array_equal(tB, P["ticket_B"]))
    chk("ticket_R_exact", np.array_equal(tR, P["ticket_R"]))

    rows, ys = [], []
    for k in ks:
        for i in range(off[k], off[k + 1]):
            rows.append(k - WARM)
            ys.append(Y[i])
    rows, y = np.array(rows), np.array(ys)
    n = y.shape[0]
    chk("n_targets", n == res["n_targets"] == 2495, n)
    laws = {"WU": law(qV / 6), "B": law(piB), "R": law(piR)}
    tk = {"WU": tW, "B": tB, "R": tR}
    sc = {}
    for m in ("WU", "B", "R"):
        qq = laws[m][rows]
        sc[f"log_{m}"] = np.array([sum(math.log(qq[t, j]) if y[t, j] else math.log(1 - qq[t, j]) for j in range(49))
                                   for t in range(n)])
        sc[f"brier_{m}"] = ((qq - y) ** 2).sum(1)
        sc[f"hits_{m}"] = np.array([int(y[t, tk[m][rows[t]] - 1].sum()) for t in range(n)])
    sc["log_U"] = y.sum(1) * math.log(6 / 49) + (49 - y.sum(1)) * math.log(43 / 49)
    sc["brier_U"] = ((6 / 49 - y) ** 2).sum(1)
    chk("per_target_hits_WU", sc["hits_WU"].tolist() == res["per_target"]["hits_WU"])
    half = n // 2
    parts = {"total": slice(0, n), "half1": slice(0, half), "half2": slice(half, n)}
    agg = {}
    for pname, sl in parts.items():
        a = {}
        for m in ("WU", "B", "R"):
            a[f"hits_{m}"] = int(sc[f"hits_{m}"][sl].sum())
            a[f"excess_{m}"] = a[f"hits_{m}"] / (sl.stop - sl.start) - 36 / 49
        for m in ("WU", "B", "R", "U"):
            a[f"log_{m}"] = float(sc[f"log_{m}"][sl].sum())
            a[f"brier_{m}"] = float(sc[f"brier_{m}"][sl].sum())
        agg[pname] = a
        for kk, v in a.items():
            ok = (v == res[pname][kk]) if kk.startswith("hits") else abs(v - res[pname][kk]) < 1e-6
            chk(f"{pname}.{kk}", ok, [v, res[pname][kk]])
    t, h1, h2 = agg["total"], agg["half1"], agg["half2"]
    gp = [t["excess_WU"] >= 0.20,
          t["hits_WU"] > t["hits_B"] and t["hits_WU"] > t["hits_R"],
          t["log_WU"] > t["log_U"] and t["log_WU"] > t["log_B"],
          t["brier_WU"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
          all(h["excess_WU"] > 0 and h["hits_WU"] > h["hits_B"] for h in (h1, h2)),
          all(h["log_WU"] > h["log_B"] for h in (h1, h2))]
    for i, ok in enumerate(gp):
        chk(f"gate_{i + 1}_eq", ok == res["gates"][i]["pass"], ok)
    verdict = "WU_PROMOVAT_EXPLORATORIU" if all(gp) else "WU_NO_PROMOTION_EXPLORATORY"
    chk("verdict", verdict == res["verdict"] and sum(gp) == res["gates_passed"], [verdict, sum(gp)])
    chk("positive_claims_allowed_false", res.get("positive_claims_allowed") is False)
    banned = [m for m in ("wu649", "bo649", "parser", "engine", "validare", "torch") if m in sys.modules]
    chk("no_forbidden_imports", not banned, banned)
    nf = sum(not c_["pass"] for c_ in checks)
    out = {"status": "PASS" if nf == 0 else "FAIL", "n_checks": len(checks), "n_fail": nf,
           "imports_model": bool(banned), "verdict_recomputed": verdict, "checks": checks}
    (RUN / "VERIFICARE_INDEPENDENTA.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "checks"}, indent=2))
    return 0 if nf == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
