#!/usr/bin/env python3
"""XI-C1 §6 — evaluarea designurilor garantate în simulatorul C4 (o singură rulare de producție).

Reutilizează din xi/c4_simulator.py (importat, nemodificat) probabilitățile exacte și verificarea lor (V2) și metoda
extragerilor uniforme reale pe măști. Plăți brute din istoric (ultimele 312 date comune) cu PARTAJARE EXACTĂ:
k bilete câștigătoare ale noastre la categoria c cu w câștigători istorici ⇒ total k·ppw·w/(w+k); rollover ⇒ carryover
(o dată, indiferent de k); 6/49 IV fix ⇒ k·ppw; alte stări ⇒ 0.
Utilizare: .venv/bin/python -B xi/c1/c1_evaluare.py --joker <design.json> [--649 <design.json>]
positive_claims_allowed=false. Calcul clasic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction as Fr
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
XI = HERE.parent
sys.path.insert(0, str(XI))
import c4_simulator as C4  # noqa: E402  (nemodificat; main() nu se execută)

D = C4.D
OUT = XI / "rezultate" / "C1"
SEED, M, CHUNK, YEARS, T, WINDOW = C4.SEED, C4.M, C4.CHUNK, C4.YEARS, C4.T, C4.WINDOW
PRICE, CATS, FIXED = C4.PRICE, C4.CATS, C4.FIXED
SEALS = {"PROTOCOL_XI_C1.md": "63813dcdb8a871ac4fc7d30033f0f74ea807179dd5d3e9c8163a8d11f7c82112",
         "c4_simulator.py": "c8ff356aebc1af15011427991c27226d1251e1c4fff6743ec6c5c67992df89f4"}


def sha_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_prizes():
    """Pe dată și categorie: (stare 0=paid/1=rollover/2=altceva, ppw, w, carryover). Același SQL ca C4."""
    db = Path(D.default_database())
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    per, counts = {}, {}
    for g in ("649", "joker"):
        rows = con.execute(
            "SELECT d.draw_date, p.category, p.status, p.winning_variants, p.payout_per_win, p.carryover "
            "FROM draws d JOIN prizes p ON p.observation_id = d.selected_observation "
            "WHERE d.game = ? AND d.draw_kind = 'regular' AND d.draw_date >= '2010-05-02'", (g,)).fetchall()
        by, cnt = {}, {"paid": 0, "rollover": 0, "zero_other": 0}
        for date, cat, status, w, ppw, carry in rows:
            if cat not in CATS[g]:
                continue
            rec = (2, 0.0, 0.0, 0.0)
            try:
                if status == "paid" and ppw is not None and w is not None and int(w) > 0:
                    rec = (0, float(ppw), float(int(w)), 0.0)
                    cnt["paid"] += 1
                elif status == "rollover" and carry is not None:
                    rec = (1, 0.0, 0.0, float(carry))
                    cnt["rollover"] += 1
                else:
                    cnt["zero_other"] += 1
            except (TypeError, ValueError):
                cnt["zero_other"] += 1
            by.setdefault(date, {})[cat] = rec
        per[g] = {d: [c[x] for x in CATS[g]] for d, c in by.items() if len(c) == len(CATS[g])}
        counts[g] = cnt
    # datele comune ale celor 3 jocuri, ca în C4 (fereastra identică)
    _, _, common, _ = C4.load_payouts()
    return db, per, common, counts


def load_design(p: Path):
    d = json.loads(p.read_text())
    return d, sha_file(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--joker", type=Path, required=True)
    ap.add_argument("--649", dest="d649", type=Path)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "C1_EVALUARE.json"
    if target.exists():
        sys.exit("refuz suprascrierea: " + str(target))
    for f, h in SEALS.items():
        assert sha_file(XI / f) == h, f
    t0 = time.time()
    dev = torch.device("cuda")
    P = C4.exact_probs()
    v2 = C4.verify_probs(P)
    db, per, common, counts = load_prizes()
    win = common[-WINDOW:]
    meta = {"start_utc": datetime.now(timezone.utc).isoformat(), "script_sha256": sha_file(__file__),
            "seals": SEALS, "database": str(db), "database_sha256": D.sha256(db), "window": [win[0], win[-1]],
            "M": M, "T": T, "seed": SEED, "gpu": torch.cuda.get_device_name(0), "payout_status_counts": counts,
            "positive_claims_allowed": False}
    designs = {}
    dj, hj = load_design(a.joker)
    assert dj["game"] == "joker"
    designs["joker"] = (dj, hj)
    if a.d649:
        d6, h6 = load_design(a.d649)
        assert d6["game"] == "649"
        designs["649"] = (d6, h6)
    games = list(designs)
    shape = {"649": (49, 6), "joker": (45, 5)}
    TK, JK, NT = {}, None, {}
    for g in games:
        d = designs[g][0]
        tk = [t[:shape[g][1]] for t in d["tickets"]]
        NT[g] = len(tk)
        m = np.zeros((len(tk), shape[g][0]), dtype=np.float32)
        for i, t in enumerate(tk):
            m[i, [x - 1 for x in t]] = 1
        TK[g] = torch.tensor(m, device=dev)
        if g == "joker":
            JK = torch.tensor([t[5] - 1 for t in d["tickets"]], device=dev)
    # tabele de plată pe GPU: (WINDOW, C)
    tab = {}
    for g in games:
        arr = np.array([[per[g][dd][c] for c in range(len(CATS[g]))] for dd in win], dtype=np.float64)  # (W,C,4)
        tab[g] = {k: torch.tensor(arr[:, :, i], device=dev) for i, k in enumerate(("st", "ppw", "w", "carry"))}
    fixed = {g: torch.tensor([(g, c) in FIXED for c in CATS[g]], device=dev) for g in games}
    strategies = [("D_" + g, [g]) for g in games] + ([("D_ambele", games)] if len(games) > 1 else [])
    stake = {name: sum(NT[g] * PRICE[g] for g in gl) for name, gl in strategies}
    gen = torch.Generator(device=dev).manual_seed(SEED)
    marks = [104 * y for y in YEARS]
    acc = {name: {y: [] for y in YEARS} for name, _ in strategies}
    season_mean = {name: [] for name, _ in strategies}
    kc_season = {g: [] for g in games}                 # (B, C) medii pe dată ale numărului de bilete câștigătoare
    zero_dates = {g: 0 for g in games}
    min_pay = {g: float("inf") for g in games}
    pay_hist = {g: [] for g in games}
    for c0 in range(0, M, CHUNK):
        B = min(CHUNK, M - c0)
        cum = {name: torch.zeros(B, dtype=torch.float64, device=dev) for name, _ in strategies}
        kc_sum = {g: torch.zeros(B, len(CATS[g]), dtype=torch.float64, device=dev) for g in games}
        for t in range(T):
            idx = torch.randint(0, WINDOW, (B,), generator=gen, device=dev)
            tot = {}
            for g in games:
                n_num, k = shape[g]
                order = torch.rand(B, n_num, generator=gen, device=dev).topk(k, dim=1).indices
                oh = torch.zeros(B, n_num, device=dev).scatter_(1, order, 1.0)
                hits = (oh @ TK[g].T).round().to(torch.int8)                         # (B, N)
                if g == "649":
                    kc = torch.stack([(hits == h).sum(1) for h in (6, 5, 4, 3)], 1)
                else:
                    jd = torch.randint(0, 20, (B, 1), generator=gen, device=dev)
                    jm = (jd == JK[None, :])
                    table = [(5, 1), (5, 0), (4, 1), (4, 0), (3, 1), (3, 0), (2, 1), (1, 1)]
                    kc = torch.stack([((hits == m) & (jm if jj else ~jm)).sum(1) for m, jj in table], 1)
                kcf = kc.double()                                                    # (B, C)
                kc_sum[g] += kcf
                st, ppw, w, carry = (tab[g][x][idx] for x in ("st", "ppw", "w", "carry"))
                paid = torch.where(fixed[g][None, :], kcf * ppw, kcf * ppw * w / (w + kcf).clamp_min(1e-12))
                val = torch.where(st == 0, paid, torch.where(st == 1, carry * (kcf > 0), torch.zeros_like(paid)))
                val = torch.where(kcf > 0, val, torch.zeros_like(val))
                tg = val.sum(1)
                tot[g] = tg
                anyprize = (kc.sum(1) > 0)
                zero_dates[g] += int((~anyprize).sum())
                min_pay[g] = min(min_pay[g], float(tg.min()))
                if c0 == 0 and t < 104:
                    pay_hist[g].append(tg[:4096].cpu().numpy())
            for name, gl in strategies:
                cum[name] += sum(tot[g] for g in gl) - stake[name]
            if t + 1 in marks:
                y = YEARS[marks.index(t + 1)]
                for name, _ in strategies:
                    acc[name][y].append(cum[name].cpu().numpy().copy())
        for name, _ in strategies:
            season_mean[name].append((cum[name] / T).cpu().numpy())
        for g in games:
            kc_season[g].append((kc_sum[g] / T).cpu().numpy())
        print(f"chunk {c0 // CHUNK + 1}/{math.ceil(M / CHUNK)} {time.time() - t0:.0f}s", flush=True)
    out = {"meta": meta, "V2_probabilitati": v2, "designs": {}, "strategies": {}}
    gates = {"E3_V2": bool(v2["PASS"])}
    for g in games:
        d, h = designs[g]
        ks = np.concatenate(kc_season[g])                                            # (M, C)
        exact = [NT[g] * float(p) for p in P[g]]
        e2 = []
        for ci, c in enumerate(CATS[g]):
            mu, se = float(ks[:, ci].mean()), float(ks[:, ci].std(ddof=1) / math.sqrt(len(ks)))
            e2.append({"cat": c, "exact": exact[ci], "sim": mu, "se": se,
                       "pass": abs(mu - exact[ci]) <= 4 * se + 1e-12})
        ph = np.concatenate(pay_hist[g])
        out["designs"][g] = {"name": d["name"], "file_sha256": h, "n_tickets": NT[g], "cost_per_date": NT[g] * PRICE[g],
                             "E1_dates_without_prize": zero_dates[g], "E2": e2, "min_prize_per_date": min_pay[g],
                             "prize_per_date_quantiles_1_5_50_95_99": np.percentile(ph, [1, 5, 50, 95, 99]).tolist(),
                             "prize_per_date_mean_sample": float(ph.mean())}
        gates[f"E1_{g}"] = zero_dates[g] == 0
        gates[f"E2_{g}"] = all(x["pass"] for x in e2)
    for name, gl in strategies:
        sm = np.concatenate(season_mean[name])
        rec = {"games": gl, "stake_per_date": stake[name], "net_per_date_mean": float(sm.mean()),
               "net_per_date_se": float(sm.std(ddof=1) / math.sqrt(len(sm))), "horizons": {}}
        for y in YEARS:
            x = np.concatenate(acc[name][y])
            q = np.percentile(x, [1, 5, 25, 50, 75, 95, 99])
            rec["horizons"][str(y)] = {"P_net_ge_0": float((x >= 0).mean()), "stake_total": stake[name] * 104 * y,
                                       "net_mean": float(x.mean()), "net_quantiles_1_5_25_50_75_95_99": q.tolist(),
                                       "return_mean": float(1 + x.mean() / (stake[name] * 104 * y))}
        out["strategies"][name] = rec
    out["gates"] = gates
    out["GATES_PASS"] = all(gates.values())
    meta["end_utc"] = datetime.now(timezone.utc).isoformat()
    meta["seconds"] = round(time.time() - t0, 1)
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    target.chmod(0o444)
    print("GATES", gates, "GATES_PASS", out["GATES_PASS"], "SHA", sha_file(target), flush=True)


if __name__ == "__main__":
    main()
