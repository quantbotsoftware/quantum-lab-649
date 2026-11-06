#!/usr/bin/env python3
"""Diagnostic POST-HOC C2 (scris DUPĂ rezultatele producției; descriptiv, nu poartă, nu schimbă nicio cifră C2).

Întrebare: de unde vin țintele semnalate EV+? Se compară, pe cuantile ale lui κ = vânzări prognozate / alocarea mediană
a unei categorii fără report (6/49 III, 5/40 III, Joker VIII), normalizat la mediana sa, valoarea ex-ante a categoriilor
fără jackpot cu valoarea realizată (regulile C4). Plus descompunerea Δ_moment pe categorii (6/49).
Nu importă quantum_limit. Rulare: /usr/bin/python3 -B xi/c2/diagnostic_posthoc.py
"""
import json
import sys
from math import comb
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parents[1] / "rezultate" / "C2"
h = {m: comb(5, m) * comb(40, 5 - m) / comb(45, 5) for m in range(6)}
P = {"649": [comb(6, k) * comb(43, 6 - k) / comb(49, 6) for k in (6, 5, 4, 3)],
     "540": [1 / comb(40, 5), 35 / comb(40, 6) - 1 / comb(40, 5), comb(5, 4) * comb(35, 2) / comb(40, 6)],
     "joker": [h[5] / 20, h[5] * 19 / 20, h[4] / 20, h[4] * 19 / 20, h[3] / 20, h[3] * 19 / 20, h[2] / 20, h[1] / 20]}
CATS = {"649": ["I", "II", "III", "IV"], "540": ["I", "II", "III"],
        "joker": ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]}
REF = {"649": "III", "540": "III", "joker": "VIII"}
PRICE = {"649": 8.0, "540": 5.0, "joker": 7.0}


def main():
    res = {"note": "post-hoc, descriptiv; scris după rezultatele C2", "positive_claims_allowed": False, "jocuri": {}}
    for g in CATS:
        rows = [x for x in map(json.loads, open(OUT / f"etapa1_{g}.jsonl")) if x["status"] == "evaluat"]
        k = np.array([x["state"]["sales"] / x["state"]["funds"][REF[g]]["allocation"] for x in rows])
        k = k / np.median(k)
        nonj = CATS[g][1:]
        ea = np.array([sum(x["ev"]["avg_components"].get(c, 0.0) for c in nonj) for x in rows]) / PRICE[g]
        re = np.array([sum(p * x["v"][c] for c, p in zip(CATS[g], P[g]) if c in nonj) for x in rows]) / PRICE[g]
        em = np.array([x["ev"]["ev_max"] for x in rows]) / PRICE[g]
        q = np.quantile(k, [0, .1, .25, .5, .75, .9, 1])
        bins = []
        for lo, hi in zip(q[:-1], q[1:]):
            m = (k >= lo) & (k <= hi)
            bins.append(dict(kappa=[float(lo), float(hi)], n=int(m.sum()), ex_ante_nonjackpot=float(ea[m].mean()),
                             realized_nonjackpot=float(re[m].mean()), ev_max_ratio=float(em[m].mean())))
        fl = em > 1.0
        res["jocuri"][g] = dict(bins=bins, flagged=dict(
            n=int(fl.sum()), kappa_median=float(np.median(k[fl])) if fl.any() else None,
            ex_ante_nonjackpot=float(ea[fl].mean()) if fl.any() else None,
            realized_nonjackpot=float(re[fl].mean()) if fl.any() else None),
            corr_kappa_bias=float(np.corrcoef(k, ea - re)[0, 1]))
    rows = [x for x in map(json.loads, open(OUT / "etapa1_649.jsonl")) if x["status"] == "evaluat"]
    c2 = json.loads((OUT / "C2_REZULTATE.json").read_text())
    w = c2["meta"]["window312"]
    win = [x for x in rows if w[0] <= x["date"] <= w[1]]
    snap = next(x for x in rows if x["date"] == "2026-10-22")
    dm = {c: (snap["ev"]["avg_components"][c] - float(np.mean([x["ev"]["avg_components"][c] for x in win]))) / 8.0
          for c in CATS["649"]}
    iv_change = [x["date"] for x in rows if x["v"]["IV"] == 50.0][:1]
    res["delta_moment_649_per_category"] = dm
    res["delta_moment_649_sum"] = float(sum(dm.values()))
    res["prima_plata_IV_50_lei"] = iv_change
    res["W312_IV_50_lei_share"] = float(np.mean([x["v"]["IV"] == 50.0 for x in win]))
    out = OUT / "DIAGNOSTIC_POSTHOC_C2.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
