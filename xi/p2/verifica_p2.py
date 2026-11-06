#!/usr/bin/env python3
"""Verificatorul independent XI-P2 (protocol A §7). NU importă nimic din `banca.py` sau `p2.py`.

Folosește algoritmii independenți din `xi/p1/verifica_p1.py` (sha d39f914f…: polinoame simetrice prin arbore de
convoluții, marginale prefix/sufix, log-det prin Cholesky) + cod propriu: citirea `dev.json`, recurența mixturilor,
biletele (cu toleranța de egalitate 10⁻⁹ la graniță), nimeririle, produsul global și Holm.
  dev   verifică producția pe dezvoltare ⇒ xi/rezultate/P2/VERIFICARE_P2_DEV.json
  rez   verifică confirmarea pe rezervă (numai cu sigiliul de confirmare) ⇒ VERIFICARE_P2_REZ.json
positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import sys
from multiprocessing import Pool
from pathlib import Path

sys.dont_write_bytecode = True
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):  # un fir BLAS per proces (Pool)
    os.environ.setdefault(_v, "1")
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
XI = HERE.parent
DATE = XI / "date_p2"
OUT = XI / "rezultate" / "P2"
V1_SHA = "d39f914f6c4bc454a064b0878ab8b48a98d7af50978a549ba3b99cb83af6ef93"
TOL_STEP, TOL_AGG = 1e-8, 1e-6


def h(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _v1():
    p = XI / "p1" / "verifica_p1.py"
    assert h(p) == V1_SHA, "sha verifica_p1.py"
    spec = importlib.util.spec_from_file_location("verifica_p1_indep", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


V1 = _v1()


def _verify_game(args):
    joc, res_g, qual, preds, pas_rows = args
    checks, fails = {}, []
    tie = 0

    def ck(name, ok, info=None):
        checks[f"{joc}_{name}"] = {"ok": bool(ok), "info": info}
        if not ok:
            fails.append(f"{joc}_{name}")
    p = DATE / joc / "dev.json"
    ck("dev_sha", h(p) == res_g["dev_sha256"])
    d = json.loads(p.read_text())
    subs = [tuple(s) for s in d["subjocuri"]]
    T = len(d["extrageri"])
    ck("T", T == res_g["T_dev"] == len(pas_rows), [T, res_g["T_dev"], len(pas_rows)])
    ck("S_identice", all(pas_rows[t]["S"][lab] == d["extrageri"][t]["sets"][lab] for t in range(T) for lab, _, _ in subs))
    tot = {X: np.zeros(T) for X in preds}
    for lab, n, k in subs:
        H = [np.array([x - 1 for x in e["sets"][lab]]) for e in d["extrageri"]]
        LP, MG = V1.components_all(H, n, k)
        dd = max(abs(LP[t, j] - pas_rows[t]["logp_comp"][lab][j]) for t in range(T) for j in range(LP.shape[1]))
        ck(f"{lab}_logp_componente", dd <= TOL_STEP, dd)
        logU = -math.log(math.comb(n, k))
        for X in preds:
            rho = V1.rho_of(X, k, qual)
            js = np.where(rho > 0)[0]
            closed = V1.lse(np.log(rho[js]) + (LP[:, js] - logU).sum(axis=0))
            lw = np.log(rho[js]).copy()
            seq = np.zeros(T)
            ok, hits = True, []
            for t in range(T):
                wn = np.exp(lw - V1.lse(lw))
                mg = (wn[:, None] * MG[t, js]).sum(axis=0)
                order = sorted(range(n), key=lambda i: (-mg[i], i))
                mine = sorted(order[:k])
                prod = [x - 1 for x in pas_rows[t]["bilet"][X][lab]]
                if mine != prod:
                    a = list(set(mine) ^ set(prod))
                    if max(mg[a]) - min(mg[a]) <= 1e-9:
                        tie += 1
                    else:
                        ok = False
                hh = len(set(prod) & set(int(x) for x in H[t]))
                hits.append(hh)
                if hh != pas_rows[t]["hits"][X][lab]:
                    ok = False
                seq[t] = V1.lse(lw + LP[t, js]) - V1.lse(lw) - logU
                lw = lw + LP[t, js]
                if abs(seq[t] + logU - pas_rows[t]["logp_pred"][X][lab]) > TOL_STEP:
                    ok = False
            ck(f"{X}_{lab}_bilete_nimeriri_logp_pred", ok)
            ck(f"{X}_{lab}_telescopare", abs(seq.sum() - closed) <= TOL_AGG, float(seq.sum() - closed))
            s = res_g["pred"][X]["sub"][lab]
            ck(f"{X}_{lab}_logE", abs(seq.sum() - s["logE"]) <= TOL_AGG, float(seq.sum() - s["logE"]))
            hs = int(sum(hits))
            pmf = np.array([math.comb(k, x) * math.comb(n - k, k - x) for x in range(k + 1)], float) / math.comb(n, k)
            dist = np.array([1.0])
            for _ in range(T):
                dist = np.convolve(dist, pmf)
            ptail = float(dist[hs:].sum())
            ck(f"{X}_{lab}_nimeriri_p", hs == s["hits_sum"] and abs(ptail - s["hits_p_one_sided"]) <= 1e-6 * max(1.0, ptail),
               [hs, ptail])
            tot[X] += seq
    for X in preds:
        pr = res_g["pred"][X]
        ck(f"{X}_logE_total", abs(tot[X].sum() - pr["logE"]) <= TOL_AGG)
        ck(f"{X}_jumatati", abs(tot[X][:T // 2].sum() - pr["logE_prima_jumatate"]) <= TOL_AGG
           and abs(tot[X][T // 2:].sum() - pr["logE_a_doua_jumatate"]) <= TOL_AGG)
    return joc, checks, fails, tie, {X: float(tot[X].sum()) for X in preds}


def cmd_dev():
    res = json.loads((OUT / "P2_DEV_REZULTATE.json").read_text())
    seal = json.loads((HERE / "SIGILIU_COD_P2.json").read_text())
    checks, fails = {}, []

    def ck(name, ok, info=None):
        checks[name] = {"ok": bool(ok), "info": info}
        if not ok:
            fails.append(name)
    ck("sha_cod_sigilat", all(h(XI.parent / rel) == s for rel, s in seal["files"].items()))
    ck("sha_sigiliu_in_rezultate", res["code_seal_sha256"] == h(HERE / "SIGILIU_COD_P2.json"))
    s1 = json.loads((XI / "p1" / "SIGILIU_COD_P1.json").read_text())
    qual = s1["qualified_families"]
    preds = [X for X in ("STAT", "DRIFT", "GAP", "FERMI", "COMB") if X in qual or (X == "COMB" and s1["COMB_qualified"])]
    ck("predictori", preds == res["predictori"])
    surse = json.loads((HERE / "SURSE_P2.json").read_text())
    inc = [g["joc"] for g in surse["incluse"]]
    act = []
    for joc in inc:
        ex = (DATE / joc / "EXCLUS.json").exists()
        dv = (DATE / joc / "dev.json").exists()
        ck(f"{joc}_stare_unica", ex != dv)
        if dv:
            act.append(joc)
    ck("jocuri_active", act == res["jocuri_active"], act)
    pas = {}
    with open(OUT / "p2_dev_pas.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            pas.setdefault(r["joc"], []).append(r)
    for joc in act:
        ck(f"{joc}_ordine_t", [r["t"] for r in pas[joc]] == list(range(1, len(pas[joc]) + 1)))
    with Pool(len(act)) as pool:
        outs = pool.map(_verify_game, [(j, res["games"][j], qual, preds, pas[j]) for j in act], chunksize=1)
    tie = 0
    logE = {}
    for joc, c, f, t, le in outs:
        checks.update(c)
        fails += f
        tie += t
        logE[joc] = le
    pv = {f"{j}:{X}": min(1.0, math.exp(-logE[j][X])) for j in act for X in preds}
    if len(act) >= 2:
        for X in preds:
            g = sum(logE[j][X] for j in act)
            ck(f"GLOBAL_{X}_logE", abs(g - res["global"][X]["logE"]) <= TOL_AGG * len(act))
            pv[f"GLOBAL:{X}"] = min(1.0, math.exp(-g))
    order = sorted(pv, key=lambda key: (pv[key], key))
    M = len(order)
    rej = {key: False for key in pv}
    for i, key in enumerate(order):
        if pv[key] <= 0.01 / (M - i):
            rej[key] = True
        else:
            break
    ck("holm", rej == res["holm"]["respinse"] and M == res["holm"]["M"], M)
    surv = sorted(k for k, v in rej.items() if v)
    ck("supravietuitori_verdict", surv == res["supravietuitori"] and res["verdict_dezvoltare"] ==
       ("P2_SUPRAVIETUITORI" if surv else "P2_NICIUN_SUPRAVIETUITOR"))
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {"utc": utc, "verifier_sha256": h(__file__), "n_checks": len(checks), "n_fail": len(fails), "fails": fails,
           "tie_tolerance_used": tie, "checks": checks, "rezultate_sha256": h(OUT / "P2_DEV_REZULTATE.json"),
           "pas_sha256": h(OUT / "p2_dev_pas.jsonl"), "VERDICT": "PASS" if not fails else "FAIL",
           "positive_claims_allowed": False}
    p = OUT / "VERIFICARE_P2_DEV.json"
    if p.exists():
        p = OUT / f"VERIFICARE_P2_DEV_{utc}.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    p.chmod(0o444)
    print(out["VERDICT"], f"{len(checks) - len(fails)}/{len(checks)}", "ties", tie, p, h(p))
    return 0 if not fails else 1


def _rez_game(args):
    joc, qual, preds = args
    dev = json.loads((DATE / joc / "dev.json").read_text())
    rb = (DATE / joc / "rezerva.json").read_bytes()
    assert hashlib.sha256(rb).hexdigest() == dev["rezerva_sha256"]
    rez = json.loads(rb)
    Td = len(dev["extrageri"])
    out = {X: 0.0 for X in preds}
    for lab, n, k in [tuple(s) for s in dev["subjocuri"]]:
        H = [np.array([x - 1 for x in e["sets"][lab]]) for e in dev["extrageri"] + rez["extrageri"]]
        LP, _ = V1.components_all(H, n, k)
        logU = -math.log(math.comb(n, k))
        for X in preds:
            rho = V1.rho_of(X, k, qual)
            js = np.where(rho > 0)[0]
            lw = np.log(rho[js]) + LP[:Td, js].sum(axis=0)
            for t in range(Td, len(H)):
                out[X] += V1.lse(lw + LP[t, js]) - V1.lse(lw) - logU
                lw = lw + LP[t, js]
    return joc, out


def cmd_rez():
    conf = json.loads((HERE / "SIGILIU_CONFIRMARE_P2.json").read_text())
    assert conf["supravietuitori"], "niciun supraviețuitor"
    assert h(OUT / "P2_DEV_REZULTATE.json") == conf["dev_rezultate_sha256"]
    res = json.loads((OUT / "P2_REZ_REZULTATE.json").read_text())
    dev_res = json.loads((OUT / "P2_DEV_REZULTATE.json").read_text())
    s1 = json.loads((XI / "p1" / "SIGILIU_COD_P1.json").read_text())
    qual = s1["qualified_families"]
    preds = dev_res["predictori"]
    jocs = sorted(res["games"])
    with Pool(len(jocs)) as pool:
        le = dict(pool.map(_rez_game, [(j, qual, preds) for j in jocs], chunksize=1))
    checks, fails = {}, []
    pv = {}
    for k_ in conf["supravietuitori"]:
        j, X = k_.split(":")
        v = sum(le[g][X] for g in dev_res["jocuri_active"]) if j == "GLOBAL" else le[j][X]
        ok = abs(v - res["logE_rezerva_supravietuitori"][k_]) <= TOL_AGG * 10
        checks[k_] = {"ok": ok, "info": v}
        if not ok:
            fails.append(k_)
        pv[k_] = min(1.0, math.exp(-v))
    order = sorted(pv, key=lambda key: (pv[key], key))
    rej = {key: False for key in pv}
    for i, key in enumerate(order):
        if pv[key] <= 0.01 / (len(order) - i):
            rej[key] = True
        else:
            break
    if rej != res["holm"]["respinse"]:
        fails.append("holm")
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {"utc": utc, "verifier_sha256": h(__file__), "checks": checks, "fails": fails,
           "VERDICT": "PASS" if not fails else "FAIL", "positive_claims_allowed": False}
    p = OUT / "VERIFICARE_P2_REZ.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    p.chmod(0o444)
    print(out["VERDICT"], p, h(p))
    return 0 if not fails else 1


def main(argv):
    if len(argv) >= 2 and argv[1] == "dev":
        return cmd_dev()
    if len(argv) >= 2 and argv[1] == "rez":
        return cmd_rez()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
