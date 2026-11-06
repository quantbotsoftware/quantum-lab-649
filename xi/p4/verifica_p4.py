#!/usr/bin/env python3
"""Verificatorul independent XI-P4 (protocol §6). NU importă nimic din `p4.py` sau `banca.py`.

Algoritmi matematici complet independenți de `p4.py`:
- `VEC`: polinoame generatoare EXACTE în Z[z] construite în coordonate de poziții ale particulelor
  0 <= y_1 < ... < y_k <= n-1, cu verificarea identităților întregi exacte Σ_a C_a = C(n,k),
  C_a = C(k-1,a)*C(n-k+1,k-a) pentru r=1, Σ_a C^(i)_a = C(n-1,k-1) și Σ_i C^(i)_a = k*C_a;
- `BLOC`: histograme 2D EXACTE în Z (ocupare x perechi în bloc), cu aceleași identități întregi;
- Recurență prequențială proprie, bilete cu toleranța de egalitate 10^-9 la graniță, nimeriri,
  convoluții hipergeometrice exacte, jumătăți, sufix 2010, produsul GLOBAL și Holm.

Subcomenzi:
  dev   verifică dezvoltarea (RO + străin) ⇒ xi/rezultate/P4/VERIFICARE_P4_DEV.json
  rez   verifică confirmarea pe rezervă (numai cu SIGILIU_CONFIRMARE_P4.json) ⇒ VERIFICARE_P4_REZ.json
positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import sqlite3
import sys
from multiprocessing import Pool
from pathlib import Path

sys.dont_write_bytecode = True
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
XI = HERE.parent
DATE_P2 = XI / "date_p2"
OUT = XI / "rezultate" / "P4"

PROTOCOL_SHA = "8d56aeafdb602befb9c91ac644a744e6b1d449774168d82fdc4ebd804fe66af3"
SIGILIU_PROT_SHA = "f2a23e175bfd4d97f022bb34ccc989bc400413db9c673c48079c0c8524e2796b"
AMEND_V12_SHA = "7db003c5b920bddd3fd9d8e86d405ba80deb60519f4f8190545ee3f2bf13e9fe"
DB_RO = Path("./loto_romania/data/snapshots/"
             "c6bfd021af15d9d6ece6b20d106550e4c8474049e38e9caa3bd1c99d19766adb/loto_romania.sqlite")
DB_RO_SHA = "9942abfc25282a715cba70e4f6d17a885a467eaf5fe0440838dc28114003c078"
HU_HATOS_CLEAN_START = "2007-07-29"

VEC_RADII = (1, 2)
VEC_BETAS = (-1.20, -0.60, -0.30, -0.15, -0.07, 0.07, 0.15, 0.30, 0.60, 1.20)
BLOC_TYPES = ("CONT", "MOD")
BLOC_BS = (5, 7, 10)
BLOC_BETAS = (-0.80, -0.40, -0.20, -0.08, 0.08, 0.20, 0.40, 0.80)

TOL_STEP = 1e-8
TOL_AGG = 1e-6


def h_file(p: Path | str) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def lse_1d(arr: np.ndarray) -> float:
    m = float(np.max(arr))
    return m + math.log(float(np.sum(np.exp(arr - m))))


def poly_mul_int(p: list[int], q: list[int]) -> list[int]:
    out = [0] * (len(p) + len(q) - 1)
    for i, pi in enumerate(p):
        if pi:
            for j, qj in enumerate(q):
                if qj:
                    out[i + j] += pi * qj
    return out


def vec_integer_polys(n: int, k: int, r: int) -> tuple[list[int], list[list[int]]]:
    """Polinoame întregi exacte C[a] și C^(i)[a] în coordonate de poziții 0 <= y_1 < ... < y_k <= n-1."""
    amax = (k - 1) if r == 1 else max(0, 2 * k - 3)
    nflags = 1 if r == 1 else 2

    # L[m][pos][flag][a], m = 1..k
    L = [[[[0] * (amax + 1) for _ in range(nflags)] for _ in range(n)] for _ in range(k + 1)]
    for pos in range(n):
        L[1][pos][0][0] = 1

    for m in range(1, k):
        # sumă cumulată pentru salturile >= r+1 (care adaugă 0 perechi și dau flag'=0)
        far_sum = [0] * (amax + 1)
        for pos in range(n):
            # înainte de a procesa pos ca destinație y_{m+1}, adăugăm în far_sum poziția pos - (r + 1)
            src_far = pos - (r + 1)
            if src_far >= 0:
                for fl in range(nflags):
                    src_poly = L[m][src_far][fl]
                    for a in range(amax + 1):
                        far_sum[a] += src_poly[a]
            # tranziție din far_sum -> flag' = 0, da = 0
            dst0 = L[m + 1][pos][0]
            for a in range(amax + 1):
                dst0[a] += far_sum[a]
            # tranziție din pos - 1 (dacă >= 0)
            if pos - 1 >= 0:
                if r == 1:
                    src_poly = L[m][pos - 1][0]
                    for a in range(amax):
                        dst0[a + 1] += src_poly[a]
                else:
                    dst1 = L[m + 1][pos][1]
                    for fl in range(2):
                        da = 1 + fl
                        src_poly = L[m][pos - 1][fl]
                        for a in range(amax + 1 - da):
                            dst1[a + da] += src_poly[a]
            # tranziție din pos - 2 pentru r = 2 (da = 1, flag' = 0)
            if r == 2 and pos - 2 >= 0:
                for fl in range(2):
                    src_poly = L[m][pos - 2][fl]
                    for a in range(amax):
                        dst0[a + 1] += src_poly[a]

    # R[rem][pos][flag][a], rem = 0..k-1
    R = [[[[0] * (amax + 1) for _ in range(nflags)] for _ in range(n)] for _ in range(k)]
    for pos in range(n):
        for fl in range(nflags):
            R[0][pos][fl][0] = 1

    for rem in range(1, k):
        far_sum = [0] * (amax + 1)
        for pos in range(n - 1, -1, -1):
            nxt_far = pos + (r + 1)
            if nxt_far < n:
                nxt_poly = R[rem - 1][nxt_far][0]
                for a in range(amax + 1):
                    far_sum[a] += nxt_poly[a]
            for fl in range(nflags):
                dst = R[rem][pos][fl]
                for a in range(amax + 1):
                    dst[a] += far_sum[a]
                if pos + 1 < n:
                    if r == 1:
                        np1 = R[rem - 1][pos + 1][0]
                        for a in range(amax):
                            dst[a + 1] += np1[a]
                    else:
                        da = 1 + fl
                        np1 = R[rem - 1][pos + 1][1]
                        for a in range(amax + 1 - da):
                            dst[a + da] += np1[a]
                if r == 2 and pos + 2 < n:
                    np2 = R[rem - 1][pos + 2][0]
                    for a in range(amax):
                        dst[a + 1] += np2[a]

    C = [0] * (amax + 1)
    for pos in range(n):
        for fl in range(nflags):
            for a in range(amax + 1):
                C[a] += L[k][pos][fl][a]

    assert sum(C) == math.comb(n, k), (n, k, r, sum(C), math.comb(n, k))
    if r == 1:
        for a in range(amax + 1):
            v = math.comb(k - 1, a) * math.comb(n - k + 1, k - a) if k - a <= n - k + 1 else 0
            assert C[a] == v, (n, k, a, C[a], v)

    Ci = [[0] * (amax + 1) for _ in range(n)]
    for i in range(n):
        acc = [0] * (amax + 1)
        for m in range(1, k + 1):
            rem = k - m
            for fl in range(nflags):
                lp = L[m][i][fl]
                rp = R[rem][i][fl]
                prod = poly_mul_int(lp, rp)
                for a in range(min(amax + 1, len(prod))):
                    acc[a] += prod[a]
        assert sum(acc) == math.comb(n - 1, k - 1), (n, k, r, i, sum(acc))
        Ci[i] = acc

    for a in range(amax + 1):
        assert sum(Ci[i][a] for i in range(n)) == k * C[a], (n, k, r, a)
    return C, Ci


def bloc_integer_polys(n: int, k: int, tip: str, b: int) -> tuple[list[int], list[int], list[list[int]]]:
    """Histograme 2D întregi exacte pe ocupările blocurilor: C[a] și C_bloc[q][a]."""
    if tip == "CONT":
        blocks = [list(range(s, min(s + b, n))) for s in range(0, n, b)]
    else:
        blocks = [list(range(r, n, b)) for r in range(min(b, n))]
    sizes = [len(blk) for blk in blocks]
    M = len(blocks)
    amax = k * (k - 1) // 2

    # H_pref[q][m][a], H_suf[q][m][a]
    H_pref = [[[0] * (amax + 1) for _ in range(k + 1)] for _ in range(M + 1)]
    H_pref[0][0][0] = 1
    for q, sq in enumerate(sizes):
        for m in range(k + 1):
            row = H_pref[q][m]
            if not any(row):
                continue
            for u in range(min(sq, k - m) + 1):
                c_u = math.comb(sq, u)
                pa = u * (u - 1) // 2
                dst = H_pref[q + 1][m + u]
                for a in range(amax + 1 - pa):
                    if row[a]:
                        dst[a + pa] += row[a] * c_u

    H_suf = [[[0] * (amax + 1) for _ in range(k + 1)] for _ in range(M + 1)]
    H_suf[M][0][0] = 1
    for q in range(M - 1, -1, -1):
        sq = sizes[q]
        for m in range(k + 1):
            row = H_suf[q + 1][m]
            if not any(row):
                continue
            for u in range(min(sq, k - m) + 1):
                c_u = math.comb(sq, u)
                pa = u * (u - 1) // 2
                dst = H_suf[q][m + u]
                for a in range(amax + 1 - pa):
                    if row[a]:
                        dst[a + pa] += row[a] * c_u

    C = H_pref[M][k]
    assert sum(C) == math.comb(n, k)

    Ci = [[0] * (amax + 1) for _ in range(n)]
    for q, sq in enumerate(sizes):
        # polinomul celorlalte blocuri pentru rem = k - u
        cq = [0] * (amax + 1)
        for u in range(1, min(sq, k) + 1):
            rem = k - u
            c_u1 = math.comb(sq - 1, u - 1)
            pa = u * (u - 1) // 2
            # convoluția H_pref[q][m] * H_suf[q+1][rem - m]
            other = [0] * (amax + 1)
            for m in range(rem + 1):
                pr = poly_mul_int(H_pref[q][m], H_suf[q + 1][rem - m])
                for a in range(min(amax + 1, len(pr))):
                    other[a] += pr[a]
            for a in range(amax + 1 - pa):
                if other[a]:
                    cq[a + pa] += c_u1 * other[a]
        assert sum(cq) == math.comb(n - 1, k - 1)
        for idx in blocks[q]:
            Ci[idx] = cq

    for a in range(amax + 1):
        assert sum(Ci[i][a] for i in range(n)) == k * C[a]
    return C, sizes, Ci


def eval_poly_log(C: list[int], beta: float) -> float:
    terms = [math.log(c) + beta * a for a, c in enumerate(C) if c > 0]
    return lse_1d(np.array(terms, dtype=np.float64))


def indep_subgame_tables(n: int, k: int):
    if k < 2:
        return [("U", None)], np.array([math.log(n)], dtype=np.float64), np.full((1, n), 1.0 / n, dtype=np.float64)
    comp = [("U", None)]
    logZ_list = [math.log(math.comb(n, k))]
    marg_list = [np.full(n, k / n, dtype=np.float64)]

    for r in VEC_RADII:
        C, Ci = vec_integer_polys(n, k, r)
        for beta in VEC_BETAS:
            lz = eval_poly_log(C, beta)
            mg = np.array([math.exp(eval_poly_log(Ci[i], beta) - lz) for i in range(n)], dtype=np.float64)
            comp.append(("VEC", (r, beta)))
            logZ_list.append(lz)
            marg_list.append(mg)

    for tip in BLOC_TYPES:
        for b in BLOC_BS:
            C, _, Ci = bloc_integer_polys(n, k, tip, b)
            for beta in BLOC_BETAS:
                lz = eval_poly_log(C, beta)
                mg = np.array([math.exp(eval_poly_log(Ci[i], beta) - lz) for i in range(n)], dtype=np.float64)
                comp.append(("BLOC", (tip, b, beta)))
                logZ_list.append(lz)
                marg_list.append(mg)

    return comp, np.array(logZ_list, dtype=np.float64), np.vstack(marg_list)


def indep_rho(pred: str, comp: list, qual: list[str], k: int) -> np.ndarray:
    rho = np.zeros(len(comp), dtype=np.float64)
    if k < 2:
        rho[0] = 1.0
        return rho
    rho[0] = 0.5
    fams = [f for f in ("VEC", "BLOC") if f in qual] if pred == "COMB" else ([pred] if pred in qual else [])
    if not fams:
        rho[0] = 1.0
        return rho
    for f in fams:
        idx = [j for j, (fam, _) in enumerate(comp) if fam == f]
        for j in idx:
            rho[j] = 0.5 / len(fams) / len(idx)
    return rho


def indep_A_stats(S0: list[int], fam: str, par) -> int:
    k = len(S0)
    if fam == "VEC":
        r, _ = par
        return sum(1 for a in range(k) for b_ in range(a + 1, k) if 1 <= abs(S0[a] - S0[b_]) <= r)
    tip, b, _ = par
    if tip == "CONT":
        return sum(1 for a in range(k) for b_ in range(a + 1, k) if (S0[a] // b) == (S0[b_] // b))
    return sum(1 for a in range(k) for b_ in range(a + 1, k) if (S0[a] % b) == (S0[b_] % b))


def _load_source_records(gname: str) -> tuple[list[tuple[str, int, int]], list[dict], str]:
    if gname.startswith("RO_"):
        sha = h_file(DB_RO)
        con = sqlite3.connect(f"file:{DB_RO}?mode=ro", uri=True)
        db_g = "649" if gname == "RO_649" else ("540" if gname == "RO_540" else "joker")
        subs = [("649", 49, 6)] if gname == "RO_649" else (
            [("540", 40, 6)] if gname == "RO_540" else [("princ", 45, 5), ("bila", 20, 1)]
        )
        rows = con.execute(
            "select draw_key, draw_date, draw_kind, n1, n2, n3, n4, n5, n6, joker "
            "from draws where game=? and draw_kind in ('regular','special') "
            "order by draw_date, case draw_kind when 'regular' then 0 else 1 end, draw_key",
            (db_g,),
        ).fetchall()
        con.close()
        recs = []
        for key, date, _kind, *nums, jk in rows:
            if db_g == "joker":
                sets = {"princ": sorted(int(x) for x in nums[:5]), "bila": [int(jk)]}
            else:
                sets = {subs[0][0]: sorted(int(x) for x in nums)}
            recs.append({"cheie": key, "data": date, "sets": sets})
        return subs, recs, sha
    p = DATE_P2 / gname / "dev.json"
    sha = h_file(p)
    d = json.loads(p.read_text())
    subs = [tuple(s) for s in d["subjocuri"]]
    ext = d["extrageri"]
    if gname == "HU_hatos":
        ext = [e for e in ext if e["data"] is not None and e["data"] >= HU_HATOS_CLEAN_START]
    return subs, ext, sha


def _verify_one_game(args):
    gname, res_g, qual, preds, pas_rows, expected_sha = args
    checks, fails = {}, []
    ties = 0

    def ck(name: str, ok: bool, info=None):
        checks[f"{gname}_{name}"] = {"ok": bool(ok), "info": info}
        if not ok:
            fails.append(f"{gname}_{name}")

    subs, recs, actual_sha = _load_source_records(gname)
    ck("source_sha", actual_sha == expected_sha)
    T = len(recs)
    ck("T_match", T == res_g["T"] == len(pas_rows), [T, res_g["T"], len(pas_rows)])
    ck("S_identice", all(pas_rows[t]["S"][lab] == recs[t]["sets"][lab] for t in range(T) for lab, _, _ in subs))

    tot_lr = {X: np.zeros(T, dtype=np.float64) for X in preds}
    for lab, n, k in subs:
        comp, logZ, marg_c = indep_subgame_tables(n, k)
        J = len(comp)
        LP = np.empty((T, J), dtype=np.float64)
        LP[:, 0] = -logZ[0]
        if k >= 2:
            for t in range(T):
                S0 = [x - 1 for x in recs[t]["sets"][lab]]
                for j in range(1, J):
                    fam, par = comp[j]
                    beta = par[-1]
                    LP[t, j] = beta * indep_A_stats(S0, fam, par) - logZ[j]
        max_lp_diff = max(abs(float(LP[t, j]) - pas_rows[t]["logp_comp"][lab][j]) for t in range(T) for j in range(J))
        ck(f"{lab}_logp_comp", max_lp_diff <= TOL_STEP, max_lp_diff)

        logU = -math.log(math.comb(n, k))
        for X in preds:
            rho = indep_rho(X, comp, qual, k)
            js = np.where(rho > 0)[0]
            closed = lse_1d(np.log(rho[js]) + (LP[:, js] - logU).sum(axis=0))
            lw = np.log(rho[js]).copy()
            seq = np.zeros(T, dtype=np.float64)
            ok_step = True
            hits = []
            for t in range(T):
                wn = np.exp(lw - lse_1d(lw))
                mg = (wn[:, None] * marg_c[js]).sum(axis=0)
                order = sorted(range(n), key=lambda i: (-mg[i], i))
                mine = sorted(order[:k])
                prod = [x - 1 for x in pas_rows[t]["bilet"][X][lab]]
                if mine != prod:
                    diff_set = list(set(mine) ^ set(prod))
                    if float(np.max(mg[diff_set]) - np.min(mg[diff_set])) <= 1e-9:
                        ties += 1
                    else:
                        ok_step = False
                hh = len(set(pas_rows[t]["bilet"][X][lab]) & set(recs[t]["sets"][lab]))
                hits.append(hh)
                if hh != pas_rows[t]["hits"][X][lab]:
                    ok_step = False
                lpx_t = lse_1d(lw + LP[t, js]) - lse_1d(lw)
                seq[t] = lpx_t - logU
                lw = lw + LP[t, js]
                if abs(lpx_t - pas_rows[t]["logp_pred"][X][lab]) > TOL_STEP:
                    ok_step = False
            ck(f"{X}_{lab}_pas_bilete_hits", ok_step)
            ck(f"{X}_{lab}_telescopare", abs(float(seq.sum()) - closed) <= TOL_AGG, float(seq.sum()) - closed)
            s_sub = res_g["pred"][X]["sub"][lab]
            ck(f"{X}_{lab}_logE", abs(float(seq.sum()) - s_sub["logE"]) <= TOL_AGG, float(seq.sum()) - s_sub["logE"])

            hs = int(sum(hits))
            pmf = np.array([math.comb(k, x) * math.comb(n - k, k - x) for x in range(k + 1)], dtype=np.float64) / math.comb(n, k)
            dist = np.array([1.0], dtype=np.float64)
            base = pmf.copy()
            m_ = T
            while m_ > 0:
                if m_ & 1:
                    dist = np.convolve(dist, base)
                m_ >>= 1
                if m_:
                    base = np.convolve(base, base)
            ptail = float(dist[hs:].sum())
            ck(f"{X}_{lab}_hits_p", hs == s_sub["hits_sum"] and abs(ptail - s_sub["hits_p_one_sided"]) <= 1e-6 * max(1.0, ptail),
               [hs, ptail])
            tot_lr[X] += seq

    idx_2010 = next((t for t, r in enumerate(recs) if r["data"] and r["data"] >= "2010-01-01"), None)
    for X in preds:
        pr = res_g["pred"][X]
        ck(f"{X}_logE_total", abs(float(tot_lr[X].sum()) - pr["logE"]) <= TOL_AGG)
        ck(f"{X}_jumatati",
           abs(float(tot_lr[X][:T // 2].sum()) - pr["logE_prima_jumatate"]) <= TOL_AGG
           and abs(float(tot_lr[X][T // 2:].sum()) - pr["logE_a_doua_jumatate"]) <= TOL_AGG)
        if idx_2010 is not None:
            ck(f"{X}_dupa_2010", abs(float(tot_lr[X][idx_2010:].sum()) - pr["logE_dupa_2010"]) <= TOL_AGG)
    return gname, checks, fails, ties, {X: float(tot_lr[X].sum()) for X in preds}


def _indep_holm(pv: dict[str, float], alpha: float = 0.01) -> dict[str, bool]:
    order = sorted(pv, key=lambda key: (pv[key], key))
    M = len(order)
    rej = {key: False for key in pv}
    for i, key in enumerate(order):
        if pv[key] <= alpha / (M - i):
            rej[key] = True
        else:
            break
    return rej


def cmd_dev() -> int:
    res = json.loads((OUT / "P4_DEV_REZULTATE.json").read_text())
    seal = json.loads((HERE / "SIGILIU_COD_P4.json").read_text())
    checks, fails = {}, []

    def ck(name: str, ok: bool, info=None):
        checks[name] = {"ok": bool(ok), "info": info}
        if not ok:
            fails.append(name)

    ck("protocol_sha", h_file(XI / "PROTOCOL_XI_P4.md") == PROTOCOL_SHA == res["protocol_sha256"])
    ck("sigiliu_prot_sha", h_file(XI / "SIGILIU_XI_P4.json") == SIGILIU_PROT_SHA)
    ck("amendament_v12_01_sha", h_file(XI / "AMENDAMENT_V12_01.md") == AMEND_V12_SHA == res["amendament_v12_01_sha256"])
    ck("sha_cod_sigilat", all(h_file(XI.parent / rel) == s for rel, s in seal["files"].items()))
    ck("sha_sigiliu_in_rezultate", res["code_seal_sha256"] == h_file(HERE / "SIGILIU_COD_P4.json"))

    qual = seal["qualified_families"]
    preds = [X for X in ("VEC", "BLOC", "COMB") if X in qual or (X == "COMB" and seal["COMB_qualified"])]
    ck("predictori", preds == res["predictori"])

    pas: dict[str, list[dict]] = {}
    with open(OUT / "p4_dev_pas.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            pas.setdefault(r["joc"], []).append(r)

    ro_list = list(res["ro_games"].keys())
    f_list = list(res["foreign_games"].keys())
    ck("jocuri_asteptate", ro_list == ["RO_649", "RO_540", "RO_joker"]
       and f_list == ["HU_otos", "FR_loto", "US_powerball", "HU_hatos"])

    for g in ro_list + f_list:
        ck(f"{g}_ordine_t", [r["t"] for r in pas[g]] == list(range(1, len(pas[g]) + 1)))

    work = []
    for g in ro_list:
        work.append((g, res["ro_games"][g], qual, preds, pas[g], DB_RO_SHA))
    for g in f_list:
        work.append((g, res["foreign_games"][g], qual, preds, pas[g], res["dev_strain_sha256"][g]))

    with Pool(len(work)) as pool:
        outs = pool.map(_verify_one_game, work, chunksize=1)

    ties_total = 0
    logE_map = {}
    for g, c, fl, ti, le in outs:
        checks.update(c)
        fails.extend(fl)
        ties_total += ti
        logE_map[g] = le

    # Holm RO
    pv_ro = {f"{g}:{X}": min(1.0, math.exp(-logE_map[g][X])) for g in ro_list for X in preds}
    rej_ro = _indep_holm(pv_ro, 0.01)
    cand_ro = sorted(k for k, v in rej_ro.items() if v)
    ck("holm_ro", rej_ro == res["holm_ro"]["respinse"] and cand_ro == res["candidati_ro"])

    # Holm dezvoltare străină + GLOBAL
    pv_f = {f"{g}:{X}": min(1.0, math.exp(-logE_map[g][X])) for g in f_list for X in preds}
    for X in preds:
        gle = sum(logE_map[g][X] for g in f_list)
        ck(f"GLOBAL_{X}_logE", abs(gle - res["global_strain"][X]["logE"]) <= TOL_AGG * len(f_list))
        pv_f[f"GLOBAL:{X}"] = min(1.0, math.exp(-gle))
    rej_f = _indep_holm(pv_f, 0.01)
    surv_f = sorted(k for k, v in rej_f.items() if v)
    ck("holm_dev_strain", rej_f == res["holm_dev_strain"]["respinse"] and surv_f == res["supravietuitori_dev_strain"])
    ck("verdict_dev_strain", res["verdict_dev_strain"] ==
       ("P4_SUPRAVIETUITORI_DEV_STRAIN" if surv_f else "P4_NICIUN_SUPRAVIETUITOR"))

    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {
        "utc": utc,
        "verifier_sha256": h_file(__file__),
        "n_checks": len(checks),
        "n_fail": len(fails),
        "fails": fails,
        "tie_tolerance_used": ties_total,
        "checks": checks,
        "rezultate_sha256": h_file(OUT / "P4_DEV_REZULTATE.json"),
        "pas_sha256": h_file(OUT / "p4_dev_pas.jsonl"),
        "VERDICT": "PASS" if not fails else "FAIL",
        "positive_claims_allowed": False,
    }
    p = OUT / "VERIFICARE_P4_DEV.json"
    if p.exists():
        p = OUT / f"VERIFICARE_P4_DEV_{utc}.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    os.chmod(p, 0o444)
    print("VERIFICARE_P4_DEV:", out["VERDICT"], f"{len(checks) - len(fails)}/{len(checks)}", "ties", ties_total, p, h_file(p))
    return 0 if not fails else 1


def _rez_one_game(args):
    gname, qual, preds = args
    subs, dev_ext, _ = _load_source_records(gname)
    dev_raw = json.loads((DATE_P2 / gname / "dev.json").read_text())
    rb = (DATE_P2 / gname / "rezerva.json").read_bytes()
    assert hashlib.sha256(rb).hexdigest() == dev_raw["rezerva_sha256"]
    rez_ext = json.loads(rb)["extrageri"]
    Td = len(dev_ext)
    all_ext = dev_ext + rez_ext
    T = len(all_ext)
    out = {X: 0.0 for X in preds}
    for lab, n, k in subs:
        comp, logZ, _ = indep_subgame_tables(n, k)
        J = len(comp)
        LP = np.empty((T, J), dtype=np.float64)
        LP[:, 0] = -logZ[0]
        if k >= 2:
            for t in range(T):
                S0 = [x - 1 for x in all_ext[t]["sets"][lab]]
                for j in range(1, J):
                    fam, par = comp[j]
                    LP[t, j] = par[-1] * indep_A_stats(S0, fam, par) - logZ[j]
        logU = -math.log(math.comb(n, k))
        for X in preds:
            rho = indep_rho(X, comp, qual, k)
            js = np.where(rho > 0)[0]
            lw = np.log(rho[js]) + LP[:Td, js].sum(axis=0)
            for t in range(Td, T):
                out[X] += lse_1d(lw + LP[t, js]) - lse_1d(lw) - logU
                lw = lw + LP[t, js]
    return gname, out


def cmd_rez() -> int:
    conf = json.loads((HERE / "SIGILIU_CONFIRMARE_P4.json").read_text())
    surv = conf["supravietuitori_dev_strain"]
    assert surv, "niciun supraviețuitor străin"
    assert h_file(OUT / "P4_DEV_REZULTATE.json") == conf["dev_rezultate_sha256"]
    res = json.loads((OUT / "P4_REZ_REZULTATE.json").read_text())
    dev_res = json.loads((OUT / "P4_DEV_REZULTATE.json").read_text())
    seal = json.loads((HERE / "SIGILIU_COD_P4.json").read_text())
    qual = seal["qualified_families"]
    preds = dev_res["predictori"]
    jocs = sorted(res["games"].keys())
    with Pool(len(jocs)) as pool:
        le = dict(pool.map(_rez_one_game, [(j, qual, preds) for j in jocs], chunksize=1))
    checks, fails = {}, []
    pv = {}
    for k_ in surv:
        g, X = k_.split(":")
        val = sum(le[gg][X] for gg in ("HU_otos", "FR_loto", "US_powerball", "HU_hatos")) if g == "GLOBAL" else le[g][X]
        ok = abs(val - res["logE_rezerva_supravietuitori"][k_]) <= TOL_AGG * 5
        checks[k_] = {"ok": bool(ok), "info": val}
        if not ok:
            fails.append(k_)
        pv[k_] = min(1.0, math.exp(-val))
    rej = _indep_holm(pv, 0.01)
    if rej != res["holm"]["respinse"]:
        fails.append("holm")
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {
        "utc": utc, "verifier_sha256": h_file(__file__), "checks": checks, "fails": fails,
        "VERDICT": "PASS" if not fails else "FAIL", "positive_claims_allowed": False,
    }
    p = OUT / "VERIFICARE_P4_REZ.json"
    if p.exists():
        p = OUT / f"VERIFICARE_P4_REZ_{utc}.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    os.chmod(p, 0o444)
    print("VERIFICARE_P4_REZ:", out["VERDICT"], p, h_file(p))
    return 0 if not fails else 1


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("dev", "rez"):
        print("Utilizare: verifica_p4.py {dev|rez}")
        sys.exit(2)
    sys.exit(cmd_dev() if sys.argv[1] == "dev" else cmd_rez())
