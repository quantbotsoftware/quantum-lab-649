"""Verificator SEPARAT TU4-IP (S11). Numai biblioteca standard + NumPy: fără torch, fără SciPy, fără import din
tu4/ip_core.py sau tu4/ip_run.py. Protocol tu4/PROTOCOL_TU4_IP.md §7. Scrie tu4/rezultate/IP/VERIFICARE_IP.json (0444).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tu4/rezultate/IP"
SEAL = ROOT / "tu4/SIGILIU_TU4_IP.json"
SSD = Path("./ssd_data/QL649_S11")
G = {"649": (49, 6, 6, 2595, 0.04642096912015248, None),
     "540": (40, 6, 5, 2490, 0.035248076774104575, None),
     "joker": (45, 5, 5, 2202, 0.0517260340859611, (20, 1, 0.019984140068430675))}
H, R, K = 520, 1000, 4
RHO = 2.0 ** (-1.0 / 312.0)
THR = math.log(900.0)
MODELS = ("H1", "H2", "H3")
CELLS = ("U", "A1", "A2", "A3")
NV = 40
checks = []


def ok(name, cond, detail=None):
    checks.append({"check": name, "pass": bool(cond), "detail": detail})
    return bool(cond)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def parts(game):
    n, k, b, T, D, ball = G[game]
    ps = [("main", n, k, D)]
    if ball:
        ps.append(("ball", ball[0], ball[1], ball[2]))
    return ps


def lcomb(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


# ---------------------------------------------------------------- algebra proprie
def esp_np(w, k):
    """w (..., n) -> (..., k+1)."""
    e = np.zeros(w.shape[:-1] + (k + 1,))
    e[..., 0] = 1.0
    for i in range(w.shape[-1]):
        e[..., 1:] = e[..., 1:] + w[..., i:i + 1] * e[..., :-1]
    return e


def D_np(lw, k):
    """KL(P_w||U) cu pi prin convoluția prefix/sufix (algoritm diferit de recurența subtractivă)."""
    lw = np.asarray(lw, float)
    n = lw.shape[-1]
    w = np.exp(lw)
    sh = w.shape[:-1]
    P = np.zeros(sh + (n + 1, k + 1))
    P[..., 0, 0] = 1.0
    for i in range(n):
        P[..., i + 1, :] = P[..., i, :]
        P[..., i + 1, 1:] += w[..., i:i + 1] * P[..., i, :-1]
    S = np.zeros(sh + (n + 1, k + 1))
    S[..., n, 0] = 1.0
    for i in range(n - 1, -1, -1):
        S[..., i, :] = S[..., i + 1, :]
        S[..., i, 1:] += w[..., i:i + 1] * S[..., i + 1, :-1]
    ek = P[..., n, k]
    pi = np.zeros(sh + (n,))
    for i in range(n):
        acc = np.zeros(sh)
        for j in range(k):
            acc = acc + P[..., i, j] * S[..., i + 1, k - 1 - j]
        pi[..., i] = w[..., i] * acc / ek
    return (pi * lw).sum(-1) - np.log(ek) + lcomb(n, k)


def basis(n):
    i = np.arange(1, n + 1)[:, None]
    m = np.arange(1, K + 1)[None, :]
    return math.sqrt(2.0 / n) * np.cos(math.pi * m * (i - 0.5) / n)


def lw_models(c, N, ct, Nt, N2t, n, k, Bm):
    """Formulele protocolului, rescrise: întoarce dict model -> ln ŵ (W, n)."""
    p = k / n
    a = (n - 1) / n
    th = a * (c / N[:, None] - p) / (p * (1 - p))
    x2 = a * ((c - N[:, None] * p) ** 2).sum(1) / (N * p * (1 - p))
    with np.errstate(divide="ignore"):
        l1 = np.maximum(0.0, 1.0 - (n - 3) / x2)
    th2 = a * (ct / Nt[:, None] - p) / (p * (1 - p))
    x22 = a * ((ct - Nt[:, None] * p) ** 2).sum(1) / (N2t * p * (1 - p))
    with np.errstate(divide="ignore"):
        l2 = np.maximum(0.0, 1.0 - (n - 3) / x22)
    z = math.sqrt(a) * (c - N[:, None] * p) / np.sqrt(N[:, None] * p * (1 - p))
    x2s = ((z @ Bm) ** 2).sum(1)
    with np.errstate(divide="ignore"):
        l3 = np.maximum(0.0, 1.0 - (K - 2) / x2s)
    return {"H1": l1[:, None] * th, "H2": l2[:, None] * th2, "H3": l3[:, None] * ((th @ Bm) @ Bm.T)}


def ticket(lw, b):
    order = sorted(range(len(lw)), key=lambda i: (-lw[i], i))
    return sorted(i + 1 for i in order[:b])


# ---------------------------------------------------------------- Clopper–Pearson prin CDF binomială exactă
def binom_cdf(x, n, p):
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if x >= n else 0.0
    s = 0.0
    lp, lq = math.log(p), math.log1p(-p)
    for i in range(0, x + 1):
        s += math.exp(lcomb(n, i) + i * lp + (n - i) * lq)
    return min(1.0, s)


def cp_lower(s, n, a=0.05):
    if s == 0:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if 1 - binom_cdf(s - 1, n, mid) < a:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def cp_upper(f, n, a=0.05):
    if f == n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if binom_cdf(f, n, mid) > a:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------- V3: e-procesul recalculat incremental
def replay(game, cell, per):
    n0, k0, b, T, D, ball = G[game]
    tot = {m: np.zeros((NV, H)) for m in MODELS}
    for name, n, k, _ in parts(game):
        X = np.load(SSD / f"{game}_{cell}" / f"X_{name}.npy", mmap_mode="r")[:NV].astype(float)
        Bm = basis(n)
        c = np.zeros((NV, n))
        ct = np.zeros((NV, n))
        Nt = 0.0
        N2t = 0.0
        for t in range(T):
            x = X[:, t]
            c += x
            ct = RHO * ct + x
            Nt = RHO * Nt + 1.0
            N2t = RHO * RHO * N2t + 1.0
        N = float(T)
        lc = lcomb(n, k)
        for t in range(H):
            x = X[:, T + t]
            lws = lw_models(c, np.full(NV, N), ct, np.full(NV, Nt), np.full(NV, N2t), n, k, Bm)
            for m in MODELS:
                lw = lws[m]
                ek = esp_np(np.exp(lw), k)[:, k]
                tot[m][:, t] += (x * lw).sum(1) - np.log(ek) + lc
            c += x
            ct = RHO * ct + x
            Nt = RHO * Nt + 1.0
            N2t = RHO * RHO * N2t + 1.0
            N += 1.0
    dev = 0.0
    for m in MODELS:
        L = np.cumsum(tot[m], 1)
        dev = max(dev, float(np.max(np.abs(L[:, -1] - per[f"{game}_{cell}_{m}_final"][:NV]))),
                  float(np.max(np.abs(L.max(1) - per[f"{game}_{cell}_{m}_max"][:NV]))))
    return dev


# ---------------------------------------------------------------- V5: fixturile reimplementate
def fixtures():
    n, k, N, b = 49, 6, 2595.0, 6
    p = k / n
    a_ = (n - 1) / n
    i = np.arange(1, n + 1)
    v = ((5 * i) % 49 - 24).astype(float)
    Bm = basis(n)

    def scale(dirn, x2):
        gam = math.sqrt(x2 * N * p * (1 - p) / (a_ * float(dirn @ dirn)))
        return N * p + gam * dirn

    def m1(c, NN=N):
        r = lw_models(c[None], np.array([NN]), c[None], np.array([NN]), np.array([NN]), n, k, Bm)
        th = a_ * (c / NN - p) / (p * (1 - p))
        lam = float(np.max(np.abs(r["H1"][0]))) / max(float(np.max(np.abs(th))), 1e-300)
        return r, th, lam
    top_v = ticket(v, b)
    top_mv = ticket(-v, b)
    out = {}
    for name, x2 in (("F1", 50.0), ("I1", 400.0)):
        c = scale(v, x2)
        r, th, lam = m1(c)
        d1, dB = float(D_np(r["H1"][0], k)), float(D_np(th, k))
        out[name] = {"pass": (d1 <= 0.1 * dB and ticket(r["H1"][0], b) == top_v) if name == "F1"
                     else (lam >= 0.85 and d1 >= 0.5 * dB), "D_H1": d1, "D_B": dB, "lambda_H1": lam}
    vh = v / np.linalg.norm(v)
    a = math.sqrt(300 * p * (1 - p) / (a_ * 2295))
    ages = np.arange(2595)
    wts = RHO ** ages
    Nt, N2t = wts.sum(), (wts ** 2).sum()

    def hist(blocks):
        c = np.zeros(n)
        ct = np.zeros(n)
        for dev, a0, a1 in blocks:
            c += (p + dev) * (a1 - a0)
            ct += (p + dev) * wts[a0:a1].sum()
        return c, ct

    def both(c, ct):
        return lw_models(c[None], np.array([N]), ct[None], np.array([Nt]), np.array([N2t]), n, k, Bm)
    cA, ctA = hist([(a * vh, 300, 2595), (-4 * a * vh, 0, 300)])
    cB, ctB = hist([(-4 * a * vh, 2295, 2595), (a * vh, 0, 2295)])
    rA, rB = both(cA, ctA), both(cB, ctB)
    out["F2"] = {"pass": bool(np.abs(rA["H1"][0]).max() > 0 and np.abs(rA["H2"][0]).max() > 0
                              and ticket(rA["H1"][0], b) == top_v and ticket(rA["H2"][0], b) == top_mv),
                 "ticket_H1": ticket(rA["H1"][0], b), "ticket_H2": ticket(rA["H2"][0], b)}
    out["I2"] = {"pass": bool(np.abs(rA["H1"][0] - rB["H1"][0]).max() <= 1e-12
                              and ticket(rA["H2"][0], b) != ticket(rB["H2"][0], b))}
    g = math.sqrt(2.0) * np.cos(np.pi * (i - 0.5) / n)
    V = [15, 20, 25, 30, 35, 40]
    h = np.full(n, -18.0 / 43.0)
    h[np.array(V) - 1] = 3.0
    c = scale(g + h, 400.0)
    r, _, _ = m1(c)
    t3 = ticket(r["H3"][0], b)
    out["F3"] = {"pass": bool(ticket(r["H1"][0], b) == V and np.abs(r["H3"][0]).max() > 0
                              and t3 == list(range(t3[0], t3[0] + b)) and not set(t3) & set(V)),
                 "ticket_H1": ticket(r["H1"][0], b), "ticket_H3": t3}
    c0 = scale(g, 100.0)
    cp = np.empty(n)
    cp[(5 * i) % 49] = c0
    r0, _, _ = m1(c0)
    rp, _, _ = m1(cp)
    d1a, d1b = float(D_np(r0["H1"][0], k)), float(D_np(rp["H1"][0], k))
    d3a, d3b = float(D_np(r0["H3"][0], k)), float(D_np(rp["H3"][0], k))
    out["I3"] = {"pass": bool(abs(d1a - d1b) <= 1e-12 and d3a >= 10 * d3b), "D_H3_c": d3a, "D_H3_cperm": d3b}
    return out


# ---------------------------------------------------------------- V6: reclasificarea FR-01 prin bisecție
def n_cald_bisect(D, df, T):
    f = lambda N: N * D - 0.5 * df * math.log1p(N / T) - math.log(300.0)  # noqa: E731
    lo = max(0, int(df / (2 * D) - T))          # minimul funcției convexe f
    hi = max(lo + 1, 1)
    while f(hi) < 0:
        hi *= 2
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if f(mid) >= 0:
            hi = mid
        else:
            lo = mid
    return hi


def main() -> int:
    outp = OUT / "VERIFICARE_IP.json"
    if outp.exists():
        print("refuz: VERIFICARE_IP.json există", file=sys.stderr)
        return 2
    seal = json.loads(SEAL.read_text())
    cal = json.loads((OUT / "CALIFICARE_IP.json").read_text())
    mart = json.loads((OUT / "MARTORI_IP.json").read_text())
    # V7
    ok("V7_documente_sigilate", all(sha(ROOT / f) == v["sha256"] for f, v in seal["documents"].items()))
    ok("V7_inghetate", all(sha(ROOT / f) == v for f, v in seal["frozen_hashes"].items()))
    ok("V7_cod_neschimbat", all(sha(ROOT / f) == v for f, v in cal["code_sha256"].items())
       and cal["code_sha256"] == mart["code_sha256"])
    ok("V7_sigiliu_in_rezultate", cal["seal_sha256"] == sha(SEAL) == mart["seal_sha256"])
    ok("V7_martori_hash", cal["martori_sha256"] == sha(OUT / "MARTORI_IP.json"))
    npz = OUT / "PER_LUME_IP.npz"
    ok("V7_per_lume_hash", cal["per_world_sha256"] == sha(npz))
    man = json.loads((OUT / "MANIFEST_SSD_IP.json").read_text())
    ok("V7_manifest_hash", cal["manifest_sha256"] == sha(OUT / "MANIFEST_SSD_IP.json"))
    bad = [f for f, v in man["files"].items() if sha(SSD / f) != v["sha256"]]
    ok("V7_fisiere_SSD", not bad and len(man["files"]) > 0, {"n_files": len(man["files"]), "bad": bad})
    per = dict(np.load(npz))
    # V1 + V2
    for game in G:
        n0, k0, b, T, D0, ball = G[game]
        for cell in CELLS:
            for name, n, k, D in parts(game):
                X = np.load(SSD / f"{game}_{cell}" / f"X_{name}.npy", mmap_mode="r")
                good = X.shape == (R, T + H, n)
                for w0 in range(0, R, 100):
                    blk = np.asarray(X[w0:w0 + 100])
                    good = good and bool((blk.sum(2, dtype=np.int64) == k).all()) and int(blk.max()) <= 1
                ok(f"V1_{game}_{cell}_{name}", good)
                if cell == "U":
                    continue
                LW = np.load(SSD / f"{game}_{cell}" / f"LW_{name}.npy", mmap_mode="r")
                if cell in ("A1", "A3"):
                    lw = np.asarray(LW)
                    Dv = D_np(lw, k)
                    rel = float(np.max(np.abs(Dv - D) / D))
                    extra = float(np.abs(lw.sum(1)).max())
                    if cell == "A3":
                        Bm = basis(n)
                        extra = max(extra, float(np.abs(lw - (lw @ Bm) @ Bm.T).max()))
                    ok(f"V2_{game}_{cell}_{name}", rel <= 1e-8 and extra <= 1e-10, {"rel": rel, "struct": extra})
                else:
                    lw = np.asarray(LW[:50, ::5])
                    Dv = D_np(lw, k).mean(1)
                    rel = float(np.max(np.abs(Dv - D) / D))
                    ok(f"V2_{game}_{cell}_{name}", rel <= 1e-8 and float(np.abs(lw.sum(2)).max()) <= 1e-10,
                       {"rel": rel})
    # V3
    for game in G:
        for cell in CELLS:
            dv = replay(game, cell, per)
            ok(f"V3_{game}_{cell}", dv <= 1e-7, {"max_abs_dev": dv})
    # V5
    fx = fixtures()
    for key in ("F1", "F2", "F3", "I1", "I2", "I3"):
        ok(f"V5_{key}", fx[key]["pass"] == mart["fixtures"][key]["pass"], {"verifier": fx[key]["pass"],
                                                                         "martori": mart["fixtures"][key]["pass"]})
    # V4
    for game in G:
        for kk, m in enumerate(MODELS, start=1):
            g = cal["gates"][f"{m}_{game}"]
            s = int((per[f"{game}_A{kk}_{m}_max"] >= THR).sum())
            f = int((per[f"{game}_U_{m}_max"] >= THR).sum())
            L, U = cp_lower(s, R), cp_upper(f, R)
            means = {mm: float(per[f"{game}_A{kk}_{mm}_final"].mean()) for mm in MODELS}
            q3a = all(means[m] > means[o] for o in MODELS if o != m) and means[m] > 0
            q1, q2 = L >= 0.80, U <= 0.01
            qual = q1 and q2 and q3a and fx[f"I{kk}"]["pass"] and fx[f"F{kk}"]["pass"] and mart["Q5_pass"] \
                and mart["Q6_pass"]
            ok(f"V4_{m}_{game}", s == g["successes"] and f == g["false_positives"] and abs(L - g["power_LCB95"]) < 1e-6
               and abs(U - g["fpr_UCB95"]) < 1e-6 and q1 == g["Q1"] and q2 == g["Q2"] and q3a == g["Q3a"]
               and qual == g["qualified"], {"s": s, "f": f, "LCB": L, "UCB": U, "qualified": qual})
    # V6
    rec = json.loads((ROOT / "tu4/rezultate/FR/RECLASIFICARE_FR01.json").read_text())
    fr = json.loads((ROOT / "tu4/rezultate/FR/FR_REZULTATE.json").read_text())
    good = True
    for f in rec["families"]:
        v = fr["games"][f["game"]]["frontier"][f["family"]]
        N = n_cald_bisect(v["D_max"], v["df"], fr["games"][f["game"]]["T"])
        cls = "FR_FEZABIL" if N <= 520 else ("FR_LENT" if N <= 2080 else "FR_NEFEZABIL")
        good = good and N == f["N_cald"] and cls == f["feasibility_amended"]
    ok("V6_reclasificare", good)
    verdict = "VERIFICARE_IP_PASS" if all(c["pass"] for c in checks) else "VERIFICARE_IP_FAIL"
    res = {"verdict": verdict, "n_checks": len(checks), "n_pass": sum(c["pass"] for c in checks), "checks": checks,
           "verifier_sha256": sha(Path(__file__)), "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "positive_claims_allowed": False}
    outp.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    os.chmod(outp, 0o444)
    print(verdict, res["n_pass"], "/", res["n_checks"])
    for c in checks:
        if not c["pass"]:
            print("FAIL", c)
    return 0 if verdict == "VERIFICARE_IP_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
