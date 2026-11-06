"""Verificatorul SEPARAT al TU4-FR (S10). Numai biblioteca standard + NumPy; NU importă tu4/frontiera.py, SciPy,
torch sau vreun modul al proiectului. Re-implementează din PROTOCOL_TU4_FR: citirea arhivelor, statisticile C1–C4 și
B1/B2/B4, quantilele χ² (gamma regularizată proprie + bisecție), rezolvarea w* prin metoda Newton (algoritm diferit
de iterația multiplicativă din frontiera.py), D_max, excesul de potriviri, orizonturile N și verdictele; plus un
Monte Carlo independent (R = 2000, semințe +500, generator prin argsort). Scrie VERIFICARE_FR.json (0444).

Utilizare:  python3 -B tu4/verifica_fr.py            (refuză suprascrierea)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

QL = Path(__file__).resolve().parents[1]
OUT = QL / "tu4" / "rezultate" / "FR"
CFG = {"649": (QL.parent / "predictie_numere/probe_date/extrageri_649.jsonl", 49, 6, 6, "numbers_sorted", False),
       "540": (QL / "tu3/date/extrageri_540.jsonl", 40, 6, 5, "numbers", False),
       "joker": (QL / "tu3/date/extrageri_joker.jsonl", 45, 5, 5, "numbers", True)}
SEEDS = {"649": 2026102701, "540": 2026102702, "joker": 2026102703}
RV, KB, NB = 2000, 4, 20
TOL = 1e-9


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------- χ² propriu
def gammainc_lower_reg(a, x):
    if x <= 0:
        return 0.0
    gln = math.lgamma(a)
    if x < a + 1:
        s, term, ap = 1.0 / a, 1.0 / a, a
        for _ in range(100000):
            ap += 1
            term *= x / ap
            s += term
            if abs(term) < abs(s) * 1e-17:
                break
        return s * math.exp(-x + a * math.log(x) - gln)
    b, c, d = x + 1 - a, 1e300, 1 / (x + 1 - a)
    h = d
    for i in range(1, 100000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-17:
            break
    return 1 - math.exp(-x + a * math.log(x) - gln) * h


def chi2_cdf(x, df):
    return gammainc_lower_reg(df / 2, x / 2)


def chi2_ppf(p, df):
    lo, hi = 0.0, max(10.0, 10 * df)
    for _ in range(300):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if chi2_cdf(mid, df) < p else (lo, mid)
    return (lo + hi) / 2


# ---------------- Poisson condiționat (DP cu excludere directă + Newton)
def e_all(w, k):
    e = [1.0] + [0.0] * k
    for x in w:
        for j in range(k, 0, -1):
            e[j] += x * e[j - 1]
    return e


def pi_and_cov(w, k):
    n = len(w)
    ek = e_all(w, k)[k]
    pi = np.array([w[i] * e_all(np.delete(w, i), k - 1)[k - 1] / ek for i in range(n)])
    C = np.empty((n, n))
    for i in range(n):
        wi = np.delete(w, i)
        for j in range(i + 1, n):
            pij = w[i] * w[j] * e_all(np.delete(wi, j - 1), k - 2)[k - 2] / ek
            C[i, j] = C[j, i] = pij - pi[i] * pi[j]
        C[i, i] = pi[i] * (1 - pi[i])
    return pi, C


def solve_newton(f, k):
    th = np.log(f / (1 - f))
    for _ in range(100):
        w = np.exp(th - th.mean())
        pi, C = pi_and_cov(w, k)
        r = f - pi
        if np.max(np.abs(r)) < 1e-14:
            break
        th = th - th.mean() + np.linalg.pinv(C, rcond=1e-12) @ r
    w = np.exp(th - th.mean())
    return w


def kl_cp(w, k):
    n = len(w)
    ek = e_all(w, k)[k]
    pi = np.array([w[i] * e_all(np.delete(w, i), k - 1)[k - 1] / ek for i in range(n)])
    return float(np.dot(pi, np.log(w)) - math.log(ek) + math.log(math.comb(n, k)))


def kl(p, q):
    p, q = np.asarray(p, float), np.asarray(q, float)
    m = p > 0
    return float(np.sum(p[m] * np.log(p[m] / q[m])))


# ---------------- date și statistici
def read(game):
    path, n, k, b, field, ball = CFG[game]
    rows = [json.loads(s) for s in open(path, encoding="utf-8") if s.strip()]
    rows.sort(key=lambda r: (r["draw_date"], r.get("within_day_sequence") if isinstance(r.get("within_day_sequence"), int) else 0, r["draw_key"]))
    X = np.zeros((len(rows), n), dtype=np.int64)
    J = []
    for t, r in enumerate(rows):
        nums = r[field]
        assert len(set(nums)) == k == len(nums) and min(nums) >= 1 and max(nums) <= n
        X[t, [x - 1 for x in nums]] = 1
        if ball:
            assert 1 <= r["joker"] <= NB
            J.append(r["joker"])
    return X, (np.array(J) if ball else None)


def hyp(n, k):
    return np.array([math.comb(k, o) * math.comb(n - k, k - o) / math.comb(n, k) for o in range(k + 1)])


def groups_for(n, k, N):
    h = hyp(n, k)
    g = [[o] for o in range(k + 1)]
    while len(g) > 2 and N * h[g[-1]].sum() < 5:
        last = g.pop()
        g[-1] = g[-1] + last
    return g


def stats(X, J, n, k, g):
    T = X.shape[0]
    p = k / n
    x2m = lambda c, TT: (n - 1) / n * float(((c - TT * p) ** 2).sum()) / (TT * p * (1 - p))
    c = X.sum(0)
    out = {"C1": x2m(c, T)}
    o = (X[1:] * X[:-1]).sum(1)
    oc = np.array([sum(int((o == v).sum()) for v in grp) for grp in g])
    hp = np.array([hyp(n, k)[grp].sum() for grp in g])
    out["C2"] = float(((oc - (T - 1) * hp) ** 2 / ((T - 1) * hp)).sum())
    A = X.T @ X
    a = A[np.triu_indices(n, 1)].astype(float)
    E = T * k * (k - 1) / (n * (n - 1))
    out["C3"] = float(((a - E) ** 2 / E).sum())
    out["C4"] = sum(x2m(X[blk].sum(0), len(blk)) for blk in np.array_split(np.arange(T), KB)) - out["C1"]
    if J is not None:
        cb = np.bincount(J, minlength=NB + 1)[1:]
        out["B1"] = float(((cb - T / NB) ** 2 / (T / NB)).sum())
        rep = int((J[1:] == J[:-1]).sum())
        N = T - 1
        out["B2"] = (rep - N / NB) ** 2 / (N / NB) + (N - rep - N * (NB - 1) / NB) ** 2 / (N * (NB - 1) / NB)
        out["B4"] = sum(float(((np.bincount(J[blk], minlength=NB + 1)[1:] - len(blk) / NB) ** 2 / (len(blk) / NB)).sum())
                        for blk in np.array_split(np.arange(T), KB)) - out["B1"]
    return out, c, oc, hp


def n_learner(D, df, target):
    N = 1
    while N * D - df / 2 * math.log(N) < target:
        N *= 2
        if N > 10 ** 12:
            return 10 ** 12
    lo, hi = max(1, N // 2), N
    while lo < hi:
        m = (lo + hi) // 2
        if m * D - df / 2 * math.log(m) >= target:
            hi = m
        else:
            lo = m + 1
    return lo


def tag(N):
    return "FR_FEZABIL" if N <= 520 else ("FR_LENT" if N <= 2080 else "FR_NEFEZABIL")


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-300)


def main():
    dst = OUT / "VERIFICARE_FR.json"
    if dst.exists():
        print("VERIFICARE_FR.json există; refuz suprascrierea.")
        return 2
    R = json.loads((OUT / "FR_REZULTATE.json").read_text())
    seal = json.loads((QL / "tu4/SIGILIU_TU4_FR.json").read_text())
    checks, fails = {}, []

    def chk(name, ok, detail=None):
        checks[name] = {"pass": bool(ok), **({"detail": detail} if detail is not None else {})}
        if not ok:
            fails.append(name)

    chk("seal_sha", R["seal_sha256"] == sha(QL / "tu4/SIGILIU_TU4_FR.json"))
    chk("martori_pass", json.loads((OUT / "MARTORI_FR.json").read_text())["verdict"] == "MARTORI_PASS")
    for p, v in seal["sources"].items():
        chk(f"source:{Path(p).name}", sha(QL / p) == v)
    for game, (path, n, k, b, field, ball) in CFG.items():
        G = R["games"][game]
        X, J = read(game)
        T = X.shape[0]
        g = groups_for(n, k, T - 1)
        chk(f"{game}:T_groups", T == G["T"] and g == G["overlap_groups"])
        st, c, oc, hp = stats(X, J, n, k, g)
        chk(f"{game}:counts", [int(x) for x in c] == G["counts"] and [int(x) for x in oc] == G["overlap_counts"])
        for key, x in st.items():
            chk(f"{game}:{key}:X2", rel(x, G["components"][key]["X2"]) <= TOL, [x, G["components"][key]["X2"]])
        # frontiera C1
        F1 = G["frontier"]["C1"]
        q = chi2_ppf(0.95, n - 1)
        chk(f"{game}:C1:q95", rel(q, F1["q95"]) <= TOL, [q, F1["q95"]])
        f = c / T
        fs = k / n + (f - k / n) * (1 + math.sqrt(q / st["C1"]))
        ws = solve_newton(fs, k)
        D = kl_cp(ws, k)
        chk(f"{game}:C1:D_max", rel(D, F1["D_max"]) <= TOL, [D, F1["D_max"]])
        chk(f"{game}:C1:D_hat", rel(kl_cp(solve_newton(f, k), k), F1["D_hat"]) <= TOL)
        top = np.sort(fs)[::-1][:b].sum()
        chk(f"{game}:C1:excess", abs((top - b * k / n) - F1["excess_hits"]) <= 1e-12)
        nl = n_learner(F1["D_max"], n - 1, math.log(300))
        chk(f"{game}:C1:N", nl == F1["N_learner_M3"] and tag(nl) == F1["feasibility"]
            and math.ceil(math.log(100) / F1["D_max"]) == F1["N_oracle_alpha_0.01"])
        # frontiera C2
        F2 = G["frontier"]["C2"]
        df2 = len(g) - 1
        q2 = chi2_ppf(0.95, df2)
        f2 = oc / (T - 1)
        fs2 = hp + (f2 - hp) * (1 + math.sqrt(q2 / st["C2"]))
        chk(f"{game}:C2:D_max", rel(kl(fs2, hp), F2["D_max"]) <= TOL, [kl(fs2, hp), F2["D_max"]])
        nl2 = n_learner(F2["D_max"], df2, math.log(300))
        chk(f"{game}:C2:N", nl2 == F2["N_learner_M3"] and tag(nl2) == F2["feasibility"])
        if ball:
            cb = np.bincount(J, minlength=NB + 1)[1:] / T
            u = np.full(NB, 1 / NB)
            fsb = u + (cb - u) * (1 + math.sqrt(chi2_ppf(0.95, NB - 1) / st["B1"]))
            chk("joker:B1:D_max", rel(kl(fsb, u), G["frontier"]["B1"]["D_max"]) <= TOL)
            rep = int((J[1:] == J[:-1]).sum())
            ub = np.array([1 / NB, 1 - 1 / NB])
            fb2 = np.array([rep, T - 1 - rep]) / (T - 1)
            fsb2 = ub + (fb2 - ub) * (1 + math.sqrt(chi2_ppf(0.95, 1) / st["B2"]))
            chk("joker:B2:D_max", rel(kl(fsb2, ub), G["frontier"]["B2"]["D_max"]) <= TOL)
        # MC independent
        rng = np.random.default_rng(SEEDS[game] + 500)
        sims = {key: [] for key in st}
        for _ in range(RV):
            Xs = np.zeros((T, n), dtype=np.int64)
            idx = np.argsort(rng.random((T, n)), axis=1)[:, :k]
            np.put_along_axis(Xs, idx, 1, axis=1)
            Js = rng.integers(1, NB + 1, T) if ball else None
            s, *_ = stats(Xs, Js, n, k, g)
            for key in st:
                sims[key].append(s[key])
        for key in st:
            pv = (1 + sum(1 for v in sims[key] if v >= st[key])) / (RV + 1)
            p = G["components"][key]["p_mc"]
            pb = (pv + p) / 2
            ok = abs(pv - p) <= 4 * math.sqrt(pb * (1 - pb) / RV) + 3 / RV
            verdict = "FR_ABATERE_DESCRIPTIVA" if p <= 0.01 / 15 else "FR_COMPATIBIL_UNIFORM"
            chk(f"{game}:{key}:p_mc", ok and verdict == G["components"][key]["verdict"], [pv, p])
        print(f"[verifica_fr] {game}: {sum(1 for kk in checks if kk.startswith(game + ':') and checks[kk]['pass'])}"
              f"/{sum(1 for kk in checks if kk.startswith(game + ':'))} OK", flush=True)
    rep = {"protocol": "TU4-FR", "results_sha256": sha(OUT / "FR_REZULTATE.json"), "checks": checks, "failed": fails,
           "n_checks": len(checks), "verdict": "VERIFICARE_FR_PASS" if not fails else "VERIFICARE_FR_FAIL",
           "positive_claims_allowed": False}
    dst.write_text(json.dumps(rep, indent=1) + "\n")
    os.chmod(dst, 0o444)
    print(json.dumps({"verdict": rep["verdict"], "n_checks": rep["n_checks"], "failed": fails}, indent=1))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
