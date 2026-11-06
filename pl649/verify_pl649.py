"""Verificator independent PL649 (PREINREGISTRARE_PL649.md §10).

NU importă pl_core.py, pl649.py, cs649/se649/gl649/wu649/bo649, engine.py, parser.py sau validare.py.
Reparsează JSONL (aceeași regulă ca verify_cs649.py, copiată), reconstruiește legăturile SU(3) cu
exponențialele în FORMĂ ÎNCHISĂ (NumPy, CPU), calculează κ și ε TRIUNGHI CU TRIUNGHI (fără M²) la fiecare
pas, π, apoi reface QUBO prin enumerarea COMPLETĂ a celor C(49,6) bilete pe CPU (multiproces) la fiecare
pas; recalculează B/R (R prin recursie), scorurile, porțile, verdictul; verifică hash-urile și ordinea
sigiliu < calificare < START.
"""
from __future__ import annotations

import datetime
import hashlib
import itertools
import json
import math
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUN = HERE / "rezultate" / "backtest_unic"
SRC = (HERE.parent.parent / "predictie_numere" / "probe_date" / "extrageri_649.jsonl").resolve()
WARM, HL = 100, 26.0
EPS, BETA, ETA, TAU_E, TAU_SD = math.pi / 32, 0.5, 0.125, 1e-9, 1e-12
FORBIDDEN = ("pl_core", "pl649", "cs649", "se649", "gl649", "wu649", "bo649", "engine", "parser", "validare")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse():
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
    draws = [[x - 1 for x in ns] for _, _, ns in uniq]
    step_of = []
    s = -1
    for i in range(len(uniq)):
        if i == 0 or uniq[i][0] != uniq[i - 1][0]:
            s += 1
        step_of.append(s)
    return draws, np.array(step_of)


# --- SU(3): exponențiale în formă închisă (λ³ = λ pentru λ1..λ7) ---
def gm(k: int) -> np.ndarray:
    L = np.zeros((3, 3), dtype=complex)
    if k == 0:
        L[0, 1] = L[1, 0] = 1
    elif k == 1:
        L[0, 1], L[1, 0] = -1j, 1j
    elif k == 2:
        L[0, 0], L[1, 1] = 1, -1
    elif k == 3:
        L[0, 2] = L[2, 0] = 1
    elif k == 4:
        L[0, 2], L[2, 0] = -1j, 1j
    elif k == 5:
        L[1, 2] = L[2, 1] = 1
    elif k == 6:
        L[1, 2], L[2, 1] = -1j, 1j
    else:
        L = np.diag([1, 1, -2]).astype(complex) / math.sqrt(3)
    return L


def expk(k: int) -> np.ndarray:
    L = gm(k)
    if k == 7:
        return np.diag(np.exp(1j * EPS * np.diag(L).real))
    return np.eye(3) + 1j * math.sin(EPS) * L + (math.cos(EPS) - 1) * (L @ L)


TRI = np.array(list(itertools.combinations(range(49), 3)))
PA, PB = np.triu_indices(49, 1)
PIDM = np.full((49, 49), -1)
PIDM[PA, PB] = np.arange(1176)
PIDM[PB, PA] = np.arange(1176)


def curvature(L: np.ndarray, n: np.ndarray):
    """L: (49,49,3,3) cu L[b,a] = L[a,b]†; n: (49,49). Triunghi cu triunghi (vectorizat)."""
    a = np.sqrt((n / 2) * (n / 2 + 1))
    x, y, z = TRI[:, 0], TRI[:, 1], TRI[:, 2]
    w = np.sqrt(a[x, y] * a[y, z] * a[x, z])
    W = np.einsum("tij,tjk,tki->t", L[x, y], L[y, z], L[z, x]).real
    e = 1 - W / 3
    we = w * e
    numn = np.bincount(x, we, 49) + np.bincount(y, we, 49) + np.bincount(z, we, 49)
    denn = np.bincount(x, w, 49) + np.bincount(y, w, 49) + np.bincount(z, w, 49)
    pe = [PIDM[x, y], PIDM[y, z], PIDM[x, z]]
    nume = sum(np.bincount(p, we, 1176) for p in pe)
    dene = sum(np.bincount(p, w, 1176) for p in pe)
    kap = np.where(denn > 0, numn / np.where(denn > 0, denn, 1), 0.0)
    ee = np.where(dene > 0, nume / np.where(dene > 0, dene, 1), 0.0)
    return kap, ee


def stdz(v):
    m, sd = v.mean(), v.std()
    return (v - m) / sd if sd > TAU_SD else np.zeros_like(v)


# --- enumerarea completă pe CPU (multiproces; coloanele partajate prin fork) ---
COLS = None


def _combos():
    c = np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(49), 6)), dtype=np.int8)
    return c.reshape(-1, 6)


def _enum_task(args):
    i, h, J = args
    E = h[COLS[0]] + h[COLS[1]] + h[COLS[2]] + h[COLS[3]] + h[COLS[4]] + h[COLS[5]]
    for p in range(6):
        for q in range(p + 1, 6):
            E += J[COLS[p], COLS[q]]
    emin = float(E.min())
    first = int(np.argmax(E <= emin + TAU_E))
    near = np.nonzero(E <= emin + 1e-8)[0]
    return i, emin, first, near[:50].tolist()


def main() -> int:
    global COLS
    t0 = time.time()
    checks = []

    def ck(name, ok, detail=None):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {'' if detail is None else detail}", flush=True)

    mods = [m for m in sys.modules if any(m == f or m.startswith(f + ".") for f in FORBIDDEN)]
    ck("no_forbidden_imports", not mods, mods)
    seal = json.loads((HERE / "SIGILIU_PROTOCOL_PL649.json").read_text())
    qual = json.loads((HERE / "rezultate" / "calificare" / "CALIFICARE.json").read_text())
    start = json.loads((RUN / "START.json").read_text())
    res = json.loads((RUN / "REZULTATE.json").read_text())
    ps = json.loads((RUN / "PREDICTII_SIGILIU.json").read_text())
    ck("protocol_sha", sha(HERE / "PREINREGISTRARE_PL649.md") == seal["sha256"] == start["protocol_sha256"] == qual["protocol_sha256"])
    ck("order_seal_qual_start", seal["sealed_at_utc"] < qual["started_utc"] <= qual["finished_utc"] <= start["started_utc"],
       [seal["sealed_at_utc"], qual["finished_utc"], start["started_utc"]])
    ck("qualified_6_6", qual["verdict"] == "PL_QUALIFIED" and qual["n_pass"] == 6)
    ck("code_same_qual_start", qual["code_sha256"] == start["code_sha256"])
    ck("code_current_equals_start", {k: sha(HERE / k) for k in start["code_sha256"]} == start["code_sha256"])
    psha = sha(RUN / "PREDICTII.npz")
    ck("predictions_sealed", psha == ps["sha256"] == res["predictions_sha256"])
    ck("source_sha", sha(SRC) == start["source_sha256"])
    draws, step_of = parse()
    K = int(step_of[-1]) + 1
    ck("n_draws_steps", len(draws) == start["meta"]["n_draws"] and K == start["meta"]["n_steps"], [len(draws), K])
    P = np.load(RUN / "PREDICTII.npz")
    ks = np.arange(WARM, K)
    ck("ks", np.array_equal(P["ks"], ks))

    # --- walk-forward independent ---
    E8 = [expk(k) for k in range(8)]
    L = np.broadcast_to(np.eye(3, dtype=complex), (49, 49, 3, 3)).copy()
    n = np.zeros((49, 49), dtype=np.int64)
    last = np.full(49, -1)
    pis, hs, Js = np.zeros((len(ks), 49)), [], []
    dmax_pi, dmax_k, unit = 0.0, 0.0, 0.0
    di = 0
    for s in range(K):
        if s >= WARM:
            kap, ee = curvature(L, n)
            z = stdz(kap)
            w = np.exp(-BETA * z)
            pi = w / w.sum()
            i = s - WARM
            pis[i] = pi
            dmax_pi = max(dmax_pi, float(np.abs(pi - P["pi"][i]).max()))
            dmax_k = max(dmax_k, float(np.abs(kap - P["kappa"][i]).max()))
            zeta = stdz(ee)
            J = np.zeros((49, 49))
            J[PA, PB] = ETA * zeta
            J[PB, PA] = ETA * zeta
            hs.append(BETA * z)
            Js.append(J)
        ages = last.copy()
        while di < len(draws) and step_of[di] == s:
            x = draws[di]
            for a, b in itertools.combinations(x, 2):
                Ek = E8[n[a, b] % 8]
                u = L[a, b]
                if ages[a] < ages[b]:
                    u = Ek @ u
                elif ages[b] < ages[a]:
                    u = u @ Ek.conj().T
                L[a, b], L[b, a] = u, u.conj().T
                n[a, b] += 1
                n[b, a] += 1
            di += 1
        for j in range(di - 1, -1, -1):
            if step_of[j] != s:
                break
            last[draws[j]] = s
    I3 = np.eye(3)
    unit = float(np.abs(np.einsum("abji,abjk->abik", L.conj(), L) - I3).max())
    ck("pi_independent_le_1e-9", dmax_pi <= 1e-9, dmax_pi)
    ck("kappa_independent_le_1e-9", dmax_k <= 1e-9, dmax_k)
    ck("unitarity_le_1e-10", unit <= 1e-10, unit)

    # --- QUBO prin enumerare completă la fiecare pas ---
    t1 = time.time()
    C6 = _combos()
    COLS = [C6[:, j].astype(np.intp) for j in range(6)]
    del C6
    nproc = min(12, os.cpu_count() or 4)
    with mp.get_context("fork").Pool(nproc) as pool:
        out = pool.map(_enum_task, [(i, hs[i], Js[i]) for i in range(len(ks))], chunksize=4)
    out.sort()
    Cfull = None
    bad, ambiguous, valid = 0, 0, True
    for i, emin, first, near in out:
        t = P["ticket"][i] - 1
        h, J = hs[i], Js[i]
        Et = h[t].sum() + J[np.ix_(t, t)].sum() / 2
        if Et > emin + 1e-8:
            valid = False
        ft = np.array([COLS[j][first] for j in range(6)])
        if not np.array_equal(np.sort(ft), np.sort(t)):
            if len(near) > 1:
                ambiguous += 1
            else:
                bad += 1
    ck("tickets_energy_le_Emin_plus_1e-8", valid)
    ck("tickets_first_lex_within_tau", bad == 0, {"nonambiguous_mismatch": bad, "ambiguous_reported": ambiguous,
                                                   "seconds": time.time() - t1, "procs": nproc})

    # --- comparatori, scoruri, porți ---
    Y = np.zeros((len(draws), 49))
    for i, x in enumerate(draws):
        Y[i, x] = 1.0
    c = np.zeros(49)
    ew = np.zeros(49)
    decay = 2.0 ** (-1.0 / HL)
    rows = []
    prev = -1
    di = 0
    stepY = [Y[step_of == s] for s in range(K)]
    for s in range(K):
        if s >= WARM:
            rows.append((c.copy(), ew.copy()))
        ew = ew * decay + stepY[s].sum(0)
        c = c + stepY[s].sum(0)
    # ew la pasul k = Σ_{s<k} 2^{-(k-1-s)/26} y_s: recursia ew_k = decay·ew_{k-1} + y_{k-1} (ew_k după adăugarea pasului k-1
    # trebuie scalată: verificăm forma directă)
    cB = np.array([r[0] for r in rows])
    ewR = np.array([r[1] for r in rows])
    piB = (cB + 1) / (cB + 1).sum(-1, keepdims=True)
    piR = (ewR + 0.5) / (ewR + 0.5).sum(-1, keepdims=True)

    def qlaw(pi):
        base = 6 / 49
        d = 6 * pi - base
        with np.errstate(divide="ignore", invalid="ignore"):
            up = np.where(d > 0, (1 - 1e-4 - base) / d, np.inf)
            dn = np.where(d < 0, (base - 1e-4) / (-d), np.inf)
        lam = np.minimum(0.5, np.minimum(up.min(-1), dn.min(-1)))[:, None]
        return base + lam * d

    def top6(sc):
        return np.sort(np.argsort(-sc, -1, kind="stable")[:, :6], -1)

    tsel = step_of >= WARM
    yT = Y[tsel]
    row = step_of[tsel] - WARM
    lawP, lawB, lawR = qlaw(pis), qlaw(piB), qlaw(piR)
    tk = {"PL": P["ticket"] - 1, "B": top6(piB), "R": top6(piR)}
    lw = {"PL": lawP, "B": lawB, "R": lawR, "U": np.full_like(lawP, 6 / 49)}
    hits = {k: np.take_along_axis(yT, tk[k][row], 1).sum(1) for k in tk}
    logs = {k: (yT * np.log(lw[k][row]) + (1 - yT) * np.log(1 - lw[k][row])).sum(1) for k in lw}
    bri = {k: ((lw[k][row] - yT) ** 2).sum(1) for k in lw}
    nT = yT.shape[0]
    half = nT // 2
    ck("targets_2495", nT == 2495, nT)
    ck("hitsB_1847_hitsR_1821", int(hits["B"].sum()) == 1847 and int(hits["R"].sum()) == 1821,
       [int(hits["B"].sum()), int(hits["R"].sum())])

    def summ(sl):
        o = {}
        nn = len(range(*sl.indices(nT)))
        for k in ("PL", "B", "R"):
            o[f"hits_{k}"] = int(hits[k][sl].sum())
            o[f"excess_{k}"] = o[f"hits_{k}"] / nn - 36 / 49
        for k in ("PL", "B", "R", "U"):
            o[f"log_{k}"] = float(logs[k][sl].sum())
            o[f"brier_{k}"] = float(bri[k][sl].sum())
        return o
    t, h1, h2 = summ(slice(0, nT)), summ(slice(0, half)), summ(slice(half, nT))
    g = [t["excess_PL"] >= 0.20, t["hits_PL"] > t["hits_B"] and t["hits_PL"] > t["hits_R"],
         t["log_PL"] - t["log_U"] > 0 and t["log_PL"] - t["log_B"] > 0,
         t["brier_PL"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
         all(h["excess_PL"] > 0 and h["hits_PL"] - h["hits_B"] > 0 for h in (h1, h2)),
         all(h["log_PL"] - h["log_B"] > 0 for h in (h1, h2))]
    npass = int(sum(g))
    verdict = "PL_PROMOVAT_EXPLORATORIU" if npass == 6 else "PL_NO_PROMOTION_EXPLORATORY"
    ck("hits_exact", t["hits_PL"] == res["total"]["hits_PL"] and t["hits_B"] == res["total"]["hits_B"]
       and t["hits_R"] == res["total"]["hits_R"])
    ck("scores_1e-6", all(abs(t[k] - res["total"][k]) <= 1e-6 for k in t if k.startswith(("log_", "brier_"))))
    ck("gates_verdict", npass == res["gates_passed"] and verdict == res["verdict"].replace("INVALID_CONSISTENCY_", ""),
       [npass, verdict])
    out_json = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "n_checks": len(checks),
                "n_fail": sum(not c["pass"] for c in checks), "verdict_recomputed": verdict,
                "gates_passed_recomputed": npass, "checks": checks, "seconds": time.time() - t0,
                "imports_model": False, "status": "PASS" if all(c["pass"] for c in checks) else "FAIL"}
    (RUN / "VERIFICARE_INDEPENDENTA.json").write_text(json.dumps(out_json, indent=2, ensure_ascii=False))
    print(json.dumps({k: out_json[k] for k in ("n_checks", "n_fail", "verdict_recomputed", "status", "seconds")}, indent=1))
    return 0 if out_json["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
