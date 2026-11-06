#!/usr/bin/env python3
"""Verificatorul independent XI-P1 (protocol §7). NU importă nimic din `banca.py`.

Algoritmi diferiți de producție: polinoamele simetrice elementare prin arbore de produse de polinoame
(convoluții), marginalele prin produse prefix/sufix, log-det prin Cholesky, citirea bazei cu altă interogare
și sortare în Python, mixturile prin formula închisă și prin recurență proprie, convoluția nulă secvențială.
Scrie xi/rezultate/P1/VERIFICARE_P1.json. positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sqlite3
import sys
from pathlib import Path

import numpy as np

XI = Path(__file__).resolve().parent.parent
OUT = XI / "rezultate" / "P1"
DB = Path("./loto_romania/data/snapshots/"
          "c6bfd021af15d9d6ece6b20d106550e4c8474049e38e9caa3bd1c99d19766adb/loto_romania.sqlite")
DB_SHA = "9942abfc25282a715cba70e4f6d17a885a467eaf5fe0440838dc28114003c078"
SUBS = {"649": [("649", 49, 6)], "540": [("540", 40, 6)], "joker": [("princ", 45, 5), ("bila", 20, 1)]}
TOL_STEP, TOL_AGG = 1e-8, 1e-6


def h(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def polyprod(ws, k):
    """Coeficienții 0..k ai ∏(1 + w x), prin arbore de produse."""
    polys = [np.array([1.0, w]) for w in ws]
    if not polys:
        return np.concatenate([[1.0], np.zeros(k)])
    while len(polys) > 1:
        nxt = []
        for i in range(0, len(polys), 2):
            if i + 1 < len(polys):
                nxt.append(np.convolve(polys[i], polys[i + 1])[:k + 1])
            else:
                nxt.append(polys[i][:k + 1])
        polys = nxt
    out = np.zeros(k + 1)
    out[:min(k + 1, len(polys[0]))] = polys[0][:k + 1]
    return out


def ek_minus_all(ws, k):
    """e_{k-1}(w fără i) pentru toți i, prin produse prefix/sufix."""
    n = len(ws)
    pre = [np.concatenate([[1.0], np.zeros(k)])]
    for w in ws:
        pre.append(np.convolve(pre[-1], [1.0, w])[:k + 1])
    suf = [np.concatenate([[1.0], np.zeros(k)])]
    for w in ws[::-1]:
        suf.append(np.convolve(suf[-1], [1.0, w])[:k + 1])
    suf = suf[::-1]
    return np.array([np.convolve(pre[i], suf[i + 1])[k - 1] for i in range(n)])


def cb(wraw, k, S):
    w = np.asarray(wraw, float)
    w = w / w.sum() * len(w)
    ek = polyprod(list(w), k)[k]
    lp = float(np.sum(np.log(w[S])) - math.log(ek))
    marg = w * ek_minus_all(list(w), k) / ek
    return lp, marg


def dpp(c, C, Tp, m, n, k, S):
    p, q = k / n, k * (k - 1) / (n * (n - 1))
    a = (c + m * p) / (Tp + m)
    b = (C + m * q) / (Tp + m)
    la = np.log(a / p)
    phi = np.log(b / q) - la[:, None] - la[None, :]
    A = np.where(phi < 0, np.sqrt(np.abs(np.minimum(phi, 0))), 0.0)
    for i in range(n):
        A[i, i] = 0.0
    mu, U = np.linalg.eigh(np.eye(n) + A)
    mu = np.where(mu < 1e-6, 1e-6, mu)
    ek = polyprod(list(mu), k)[k]
    lp = None
    if S is not None:
        LS = (U[S] * mu) @ U[S].T
        ch = np.linalg.cholesky(LS)
        lp = float(2 * np.sum(np.log(np.diag(ch))) - math.log(ek))
    marg = (U * U) @ (mu * ek_minus_all(list(mu), k)) / ek
    return lp, marg


def comps(k):
    c = [("U", None)] + [("STAT", m) for m in (100, 400, 1600, 6400)]
    c += [("DRIFT", (hh, r)) for hh in (25, 100, 400) for r in (1, 4)]
    c += [("GAP", g) for g in (-0.3, -0.1, 0.1, 0.3)]
    if k > 1:
        c += [("FERMI", m) for m in (200, 800, 3200)]
    return c


def rho_of(X, k, qual):
    cs = comps(k)
    fams = ["STAT", "DRIFT", "GAP", "FERMI"]
    if X == "COMB":
        use = [f for f in fams if f in qual and not (f == "FERMI" and k == 1)]
    else:
        use = [X] if X in qual and not (X == "FERMI" and k == 1) else []
    r = np.zeros(len(cs))
    if not use:
        r[0] = 1.0
        return r
    r[0] = 0.5
    for f in use:
        js = [j for j, (ff, _) in enumerate(cs) if ff == f]
        r[js] = 0.5 / len(use) / len(js)
    return r


def load():
    assert h(DB) == DB_SHA
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    out = {}
    for g in SUBS:
        rows = [r for r in con.execute("select * from draws where game=?", (g,)).fetchall()]
        cols = [d[0] for d in con.execute("select * from draws limit 1").description]
        recs = [dict(zip(cols, r)) for r in rows]
        recs = [r for r in recs if r["draw_kind"] in ("regular", "special")]
        recs.sort(key=lambda r: (r["draw_date"], 0 if r["draw_kind"] == "regular" else 1, r["draw_key"]))
        out[g] = recs
    con.close()
    return out


def sets_of(g, r):
    if g == "joker":
        return [sorted(r[f"n{i}"] - 1 for i in range(1, 6)), [r["joker"] - 1]]
    return [sorted(r[f"n{i}"] - 1 for i in range(1, 7))]


def components_all(H, n, k):
    cs = comps(k)
    T = len(H)
    p = k / n
    LP = np.zeros((T, len(cs)))
    MG = np.zeros((T + 1, len(cs), n))
    cnt = np.zeros(n)
    pair = np.zeros((n, n))
    ew = {25: np.zeros(n), 100: np.zeros(n), 400: np.zeros(n)}
    ewT = {25: 0.0, 100: 0.0, 400: 0.0}
    seen = np.zeros(n)
    for t in range(T + 1):  # t = numărul de extrageri deja văzute
        S = H[t] if t < T else None
        for j, (f, par) in enumerate(cs):
            if f == "U":
                lp, mg = -math.log(math.comb(n, k)), np.full(n, p)
            elif f == "STAT":
                fr = (cnt + par * p) / (t + par)
                lp, mg = cb(fr / (1 - fr), k, S) if S is not None else (None, cb(fr / (1 - fr), k, [0])[1])
            elif f == "DRIFT":
                hh, r = par
                fr = (ew[hh] + r * hh * p) / (ewT[hh] + r * hh)
                lp, mg = cb(fr / (1 - fr), k, S) if S is not None else (None, cb(fr / (1 - fr), k, [0])[1])
            elif f == "GAP":
                x = np.minimum((t - seen) * p / (1 - p), 5.0) - 1.0
                lp, mg = cb(np.exp(par * x), k, S) if S is not None else (None, cb(np.exp(par * x), k, [0])[1])
            else:
                lp, mg = dpp(cnt, pair, t, par, n, k, S)
            if S is not None:
                LP[t, j] = lp
            MG[t, j] = mg
        if S is None:
            break
        cnt[S] += 1
        for a in S:
            for b in S:
                pair[a, b] += 1
        for hh in ew:
            lam = 0.5 ** (1.0 / hh)
            ew[hh] = lam * ew[hh]
            ew[hh][S] += 1
            ewT[hh] = lam * ewT[hh] + 1
        seen[S] = t + 1
    return LP, MG


def lse(v):
    m = np.max(v)
    return float(m + math.log(np.sum(np.exp(v - m))))


def main():
    checks = {}
    fails = []

    def ck(name, ok, info=None):
        checks[name] = {"ok": bool(ok), "info": info}
        if not ok:
            fails.append(name)

    res = json.loads((OUT / "P1_REZULTATE.json").read_text())
    seal = json.loads((XI / "p1" / "SIGILIU_COD_P1.json").read_text())
    ck("sha_cod_productie", res["code_sha256"] == seal["files"]["xi/p1/banca.py"] == h(XI / "p1" / "banca.py"))
    ck("sha_protocol", h(XI / "PROTOCOL_XI_P1.md") == res["protocol_sha256"])
    ck("sha_amendament", h(XI / "AMENDAMENT_XI_P1_01.md") == res["amendament_sha256"])
    qual = res["qualified_families"]
    preds = res["predictori"]
    ck("predictori_conform_sigiliu", preds == [X for X in ("STAT", "DRIFT", "GAP", "FERMI", "COMB")
                                               if X in seal["qualified_families"]
                                               or (X == "COMB" and seal["COMB_qualified"])])
    pas = {}
    with open(OUT / "p1_pas.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            pas[(r["joc"], r["t"])] = r
    data = load()
    pv = {}
    tie_tol_used = 0
    for g, subs in SUBS.items():
        recs = data[g]
        T = len(recs)
        ck(f"{g}_T", T == res["games"][g]["T"], T)
        Hs = [sets_of(g, r) for r in recs]
        ck(f"{g}_S_identice", all(pas[(g, t + 1)]["S"][lab] == [x + 1 for x in Hs[t][si]]
                                   for t in range(T) for si, (lab, _, _) in enumerate(subs)))
        LPs, MGs = {}, {}
        for si, (lab, n, k) in enumerate(subs):
            H = [np.array(x[si]) for x in Hs]
            LP, MG = components_all(H, n, k)
            LPs[lab], MGs[lab] = LP, MG
            d = max(abs(LP[t, j] - pas[(g, t + 1)]["logp_comp"][lab][j]) for t in range(T) for j in range(LP.shape[1]))
            ck(f"{g}_{lab}_logp_componente", d <= TOL_STEP, d)
        i2010 = next(i for i, r in enumerate(recs) if r["draw_date"] >= "2010-01-01")
        for X in preds:
            tot = np.zeros(T)
            for si, (lab, n, k) in enumerate(subs):
                LP, MG = LPs[lab], MGs[lab]
                rho = rho_of(X, k, qual)
                js = np.where(rho > 0)[0]
                logU = -math.log(math.comb(n, k))
                closed = lse(np.log(rho[js]) + (LP[:, js] - logU).sum(axis=0))
                lw = np.log(rho[js]).copy()
                seq = np.zeros(T)
                tk_ok, hits = True, []
                for t in range(T + 1):
                    wn = np.exp(lw - lse(lw))
                    mg = (wn[:, None] * MG[t, js]).sum(axis=0)
                    order = sorted(range(n), key=lambda i: (-mg[i], i))
                    mine = sorted(order[:k])
                    if t < T:
                        prod = [x - 1 for x in pas[(g, t + 1)]["bilet"][X][lab]]
                    else:
                        prod = [x - 1 for x in res["games"][g]["pred"][X]["sub"][lab]["bilet_urmatoarea_extragere"]]
                    if mine != prod:
                        a = set(mine) ^ set(prod)
                        if max(mg[list(a)]) - min(mg[list(a)]) <= 1e-9:
                            tie_tol_used += 1
                        else:
                            tk_ok = False
                    if t == T:
                        break
                    hits.append(len(set(prod) & set(Hs[t][si])))
                    seq[t] = lse(lw + LP[t, js]) - lse(lw) - logU
                    lw = lw + LP[t, js]
                    if abs(seq[t] + logU - pas[(g, t + 1)]["logp_pred"][X][lab]) > TOL_STEP:
                        tk_ok = False
                ck(f"{g}_{X}_{lab}_bilete_si_logp_pred", tk_ok)
                ck(f"{g}_{X}_{lab}_telescopare", abs(seq.sum() - closed) <= TOL_AGG, float(seq.sum() - closed))
                s = res["games"][g]["pred"][X]["sub"][lab]
                ck(f"{g}_{X}_{lab}_logE", abs(seq.sum() - s["logE"]) <= TOL_AGG, float(seq.sum() - s["logE"]))
                hs = int(sum(hits))
                pmf = np.array([math.comb(k, x) * math.comb(n - k, k - x) for x in range(k + 1)], float)
                pmf /= math.comb(n, k)
                dist = np.array([1.0])
                for _ in range(T):
                    dist = np.convolve(dist, pmf)
                ptail = float(dist[hs:].sum())
                ck(f"{g}_{X}_{lab}_nimeriri", hs == s["hits_sum"] and
                   abs(ptail - s["hits_p_one_sided"]) <= 1e-6 * max(1.0, ptail), [hs, ptail])
                tot += seq
            pr = res["games"][g]["pred"][X]
            ck(f"{g}_{X}_logE_total", abs(tot.sum() - pr["logE"]) <= TOL_AGG)
            ck(f"{g}_{X}_jumatati_2010", abs(tot[:T // 2].sum() - pr["logE_prima_jumatate"]) <= TOL_AGG and
               abs(tot[T // 2:].sum() - pr["logE_a_doua_jumatate"]) <= TOL_AGG and
               abs(tot[i2010:].sum() - pr["logE_din_2010"]) <= TOL_AGG)
            pv[f"{g}:{X}"] = min(1.0, math.exp(-tot.sum()))
    # Holm propriu
    order = sorted(pv, key=lambda key: (pv[key], key))
    M = len(order)
    rej = {key: False for key in pv}
    for i, key in enumerate(order):
        if pv[key] <= 0.01 / (M - i):
            rej[key] = True
        else:
            break
    ck("holm", rej == res["holm"]["respinse"] and M == res["holm"]["M"])
    cand = sorted(key for key, v in rej.items() if v)
    ck("verdict", res["verdict"] == ("P1_CANDIDATI" if cand else "P1_NICIUN_CANDIDAT") and cand == res["candidati"])
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {"utc": utc, "verifier_sha256": h(__file__), "n_checks": len(checks), "n_fail": len(fails),
           "fails": fails, "tie_tolerance_used": tie_tol_used, "checks": checks,
           "rezultate_sha256": h(OUT / "P1_REZULTATE.json"), "pas_sha256": h(OUT / "p1_pas.jsonl"),
           "VERDICT": "PASS" if not fails else "FAIL", "positive_claims_allowed": False}
    p = OUT / "VERIFICARE_P1.json"
    if p.exists():
        p = OUT / f"VERIFICARE_P1_{utc}.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    p.chmod(0o444)
    print(out["VERDICT"], f"{len(checks) - len(fails)}/{len(checks)}", "ties", tie_tol_used, p, h(p))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
