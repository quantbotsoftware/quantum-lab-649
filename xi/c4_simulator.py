#!/usr/bin/env python3
"""XI-C4 — simulatorul probabilității de profit (PROTOCOL_XI_C4.md + AMENDAMENT_XI_C4_01.md, sigilate înainte de cod).

Bilete uniforme, probabilități exacte, extrageri uniforme simulate exact pe GPU (măști one-hot + matmul), plăți
din istoricul real (fereastra principală: ultimele 312 date comune). Fără predicție. positive_claims_allowed=false.
Rulare unică de producție:  .venv/bin/python -B xi/c4_simulator.py
"""
import hashlib
import json
import math
import sqlite3
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction as Fr
from math import comb
from pathlib import Path

import numpy as np
import torch

XI = Path(__file__).resolve().parent
REPO = XI.parents[2]
sys.path.insert(0, str(REPO / "next_candidate"))
from quantum_limit import data as D  # noqa: E402
from quantum_limit.combinatorics import all_subsets  # noqa: E402

OUT = XI / "rezultate" / "C4"
SEALS = {"PROTOCOL_XI_C4.md": "e139bc188c972c6020a13f6363b1a08fc39b87d72dd527d1a7c9c1d14cdcd1c4"}
SEED = 20261030
M = 1_000_000
CHUNK = 1 << 18
YEARS = (1, 5, 10)
T = 104 * max(YEARS)
WINDOW = 312
PRICE = {"649": 8.0, "540": 5.0, "joker": 7.0}
CATS = {"649": ["I", "II", "III", "IV"], "540": ["I", "II", "III"],
        "joker": ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]}
FIXED = {("649", "IV")}
BIG = 1000.0


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ probabilități exacte (§3)
def exact_probs():
    P = {}
    N649 = comb(49, 6)
    P["649"] = [Fr(comb(6, h) * comb(43, 6 - h), N649) for h in (6, 5, 4, 3)]
    N540 = comb(40, 6)
    p5 = Fr(comb(35, 1), N540)
    pI = Fr(1, comb(40, 5))
    P["540"] = [pI, p5 - pI, Fr(comb(5, 4) * comb(35, 2), N540)]
    NJ = comb(45, 5)
    h = {m: Fr(comb(5, m) * comb(40, 5 - m), NJ) for m in range(6)}
    j, nj = Fr(1, 20), Fr(19, 20)
    P["joker"] = [h[5] * j, h[5] * nj, h[4] * j, h[4] * nj, h[3] * j, h[3] * nj, h[2] * j, h[1] * j]
    return P


def verify_probs(P):
    """V2: enumerare exhaustivă a numărului de nimeriri față de un bilet fix + identități exacte."""
    res = {}
    for g, n, k, tk in (("649", 49, 6, 6), ("540", 40, 6, 5), ("joker", 45, 5, 5)):
        S = all_subsets(n, k).astype(np.int16)
        hits = (S < tk).sum(1)  # biletul fix = {0..tk-1}
        cnt = np.bincount(hits, minlength=k + 1)
        total = comb(n, k)
        assert cnt.sum() == total
        hd = {m: Fr(int(cnt[m]), total) for m in range(k + 1)}
        if g == "649":
            ok = [hd[6], hd[5], hd[4], hd[3]] == P[g]
        elif g == "540":
            ok = (hd[5] / 6 == P[g][0]) and (hd[5] - hd[5] / 6 == P[g][1]) and hd[4] == P[g][2]
        else:
            j, nj = Fr(1, 20), Fr(19, 20)
            ok = [hd[5] * j, hd[5] * nj, hd[4] * j, hd[4] * nj, hd[3] * j, hd[3] * nj, hd[2] * j, hd[1] * j] == P[g]
        res[g] = {"exhaustive_states": total, "hit_counts": cnt.tolist(), "match_exact": bool(ok),
                  "P_any_prize": str(sum(P[g], Fr(0))), "one_in": float(1 / sum(P[g], Fr(0)))}
        del S
    res["PASS"] = all(v["match_exact"] for v in res.values() if isinstance(v, dict))
    return res


# ------------------------------------------------------------------ plăți (§4)
def load_payouts():
    db = Path(D.default_database())
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    per = {}
    counts = {}
    for g in CATS:
        rows = con.execute(
            "SELECT d.draw_date, p.category, p.status, p.winning_variants, p.payout_per_win, p.carryover "
            "FROM draws d JOIN prizes p ON p.observation_id = d.selected_observation "
            "WHERE d.game = ? AND d.draw_kind = 'regular' AND d.draw_date >= '2010-05-02'", (g,)).fetchall()
        by = {}
        cnt = {"paid": 0, "rollover": 0, "zero_other": 0}
        for date, cat, status, w, ppw, carry in rows:
            if cat not in CATS[g]:
                continue
            v = 0.0
            try:
                if status == "paid" and ppw is not None:
                    v = float(ppw) if (g, cat) in FIXED else float(ppw) * int(w) / (int(w) + 1)
                    cnt["paid"] += 1
                elif status == "rollover" and carry is not None:
                    v = float(carry)
                    cnt["rollover"] += 1
                else:
                    cnt["zero_other"] += 1
            except (TypeError, ValueError):
                v = 0.0
                cnt["zero_other"] += 1
            by.setdefault(date, {})[cat] = v
        per[g] = {d: [c.get(x, 0.0) for x in CATS[g]] for d, c in by.items() if len(c) == len(CATS[g])}
        counts[g] = cnt
    common = sorted(set(per["649"]) & set(per["540"]) & set(per["joker"]))
    return db, per, common, counts


# ------------------------------------------------------------------ simulare (§6 + AMENDAMENT_XI_C4_01)
def random_tickets(rng, n_num, k, count):
    seen, out = set(), []
    while len(out) < count:
        t = tuple(sorted(rng.choice(n_num, k, replace=False).tolist()))
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def onehot(tickets, n_num):
    m = np.zeros((len(tickets), n_num), dtype=np.float32)
    for i, t in enumerate(tickets):
        m[i, list(t)] = 1
    return m


def strategies(rho):
    best = max(rho, key=rho.get)
    S = [("U_649", {"649": 1}), ("U_540", {"540": 1}), ("U_joker", {"joker": 1}),
         ("U_3", {"649": 1, "540": 1, "joker": 1})]
    for x in (40, 100, 500):
        S.append((f"B{x}_opt", {best: int(x // PRICE[best])}))
        S.append((f"B{x}_egal", {g: int((x / 3) // PRICE[g]) for g in CATS}))
    return S, best


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "C4_REZULTATE.json"
    if target.exists():
        sys.exit("refuz suprascrierea: " + str(target))
    for f, h in SEALS.items():
        assert sha_file(XI / f) == h, f
    t0 = time.time()
    dev = torch.device("cuda")
    meta = {"start_utc": utc(), "script_sha256": sha_file(__file__), "protocol_sha256": SEALS["PROTOCOL_XI_C4.md"],
            "amendament_sha256": sha_file(XI / "AMENDAMENT_XI_C4_01.md"), "torch": torch.__version__,
            "gpu": torch.cuda.get_device_name(0), "M": M, "T": T, "seed": SEED, "positive_claims_allowed": False}
    P = exact_probs()
    v2 = verify_probs(P)
    print("V2", json.dumps(v2)[:400], flush=True)
    db, per, common, counts = load_payouts()
    win = common[-WINDOW:]
    meta.update(database=str(db), database_sha256=D.sha256(db), common_dates=len(common), window=[win[0], win[-1]],
                payout_status_counts=counts)
    pay = {g: torch.tensor([per[g][d] for d in win], dtype=torch.float64, device=dev) for g in CATS}
    pay_all = {g: np.array([per[g][d] for d in common]) for g in CATS}
    pf = {g: np.array([float(x) for x in P[g]]) for g in CATS}
    ev = {g: float(pf[g] @ pay[g].mean(0).cpu().numpy()) for g in CATS}
    ev_all = {g: float(pf[g] @ pay_all[g].mean(0)) for g in CATS}
    rho = {g: ev[g] / PRICE[g] for g in CATS}
    rho_all = {g: ev_all[g] / PRICE[g] for g in CATS}
    print("EV", ev, "rho", rho, "rho_all", rho_all, flush=True)
    S, best = strategies(rho)
    # bilete fixe per strategie (AMENDAMENT_XI_C4_01)
    shape = {"649": (49, 6), "540": (40, 5), "joker": (45, 5)}
    tick, slices, jok = {g: [] for g in CATS}, {}, []
    for si, (name, alloc) in enumerate(S):
        rng = np.random.default_rng(SEED + si)
        for g, n in alloc.items():
            if n <= 0:
                continue
            ts = random_tickets(rng, *shape[g], n)
            a = len(tick[g])
            tick[g].extend(ts)
            slices[(name, g)] = (a, a + n)
            if g == "joker":
                jok.extend(rng.integers(0, 20, n).tolist())
    TK = {g: torch.tensor(onehot(tick[g], shape[g][0]), device=dev) for g in CATS if tick[g]}
    JK = torch.tensor(jok, device=dev)
    stake = {name: sum(n * PRICE[g] for g, n in alloc.items()) for name, alloc in S}
    gen = torch.Generator(device=dev).manual_seed(SEED)
    marks = [104 * y for y in YEARS]
    acc = {name: {y: [] for y in YEARS} for name, _ in S}
    big = {name: {y: [] for y in YEARS} for name, _ in S}
    first_any = {g: [] for g in ("649", "540", "joker")}
    season_mean = {name: [] for name, _ in S}
    for c0 in range(0, M, CHUNK):
        B = min(CHUNK, M - c0)
        cum = {name: torch.zeros(B, dtype=torch.float64, device=dev) for name, _ in S}
        bigf = {name: torch.zeros(B, dtype=torch.bool, device=dev) for name, _ in S}
        for t in range(T):
            idx = torch.randint(0, WINDOW, (B,), generator=gen, device=dev)
            cats = {}
            for g in CATS:
                n_num, k = shape[g][0], (6 if g != "joker" else 5)
                order = torch.rand(B, n_num, generator=gen, device=dev).topk(k, dim=1).indices  # ordine de extragere
                oh = torch.zeros(B, n_num, device=dev).scatter_(1, order, 1.0)
                hits = (oh @ TK[g].T).round().to(torch.int8)                                    # (B, n_tickets)
                if g == "649":
                    cat = torch.full_like(hits, -1)
                    for ci, h in enumerate((6, 5, 4, 3)):
                        cat = torch.where(hits == h, torch.full_like(hits, ci), cat)
                elif g == "540":
                    oh5 = torch.zeros(B, n_num, device=dev).scatter_(1, order[:, :5], 1.0)
                    h5 = (oh5 @ TK[g].T).round().to(torch.int8)
                    cat = torch.full_like(hits, -1)
                    cat = torch.where(hits == 4, torch.full_like(hits, 2), cat)
                    cat = torch.where(hits == 5, torch.full_like(hits, 1), cat)
                    cat = torch.where(h5 == 5, torch.full_like(hits, 0), cat)
                else:
                    jd = torch.randint(0, 20, (B, 1), generator=gen, device=dev)
                    jm = (jd == JK[None, :])
                    cat = torch.full_like(hits, -1)
                    table = {(5, 1): 0, (5, 0): 1, (4, 1): 2, (4, 0): 3, (3, 1): 4, (3, 0): 5, (2, 1): 6, (1, 1): 7}
                    for (m, jj), ci in table.items():
                        cond = (hits == m) & (jm if jj else ~jm)
                        cat = torch.where(cond, torch.full_like(hits, ci), cat)
                cats[g] = cat
                if t == 0:
                    a, b = slices[(f"U_{g}", g)]
                    first_any[g].append((cat[:, a] >= 0).float().mean().item() * B)
            for name, alloc in S:
                tot = torch.zeros(B, dtype=torch.float64, device=dev)
                for g in alloc:
                    if (name, g) not in slices:
                        continue
                    a, b = slices[(name, g)]
                    cg = cats[g][:, a:b].long()
                    rowpay = pay[g][idx]                                                        # (B, C)
                    val = torch.gather(rowpay, 1, cg.clamp_min(0)) * (cg >= 0)
                    win_t = val.sum(1)
                    tot += win_t
                    bigf[name] |= (val >= BIG).any(1)
                cum[name] += tot - stake[name]
            if t + 1 in marks:
                y = YEARS[marks.index(t + 1)]
                for name, _ in S:
                    acc[name][y].append(cum[name].cpu().numpy().copy())
                    big[name][y].append(bigf[name].cpu().numpy().copy())
        for name, _ in S:
            season_mean[name].append((cum[name] / T).cpu().numpy())
        print(f"chunk {c0 // CHUNK + 1}/{math.ceil(M / CHUNK)} {time.time() - t0:.0f}s", flush=True)
    # porți și rezultate
    out = {"meta": meta, "V2_probabilitati": v2, "ev_window": ev, "ev_since_2010": ev_all, "rho_window": rho,
           "rho_since_2010": rho_all, "best_game_window": best, "strategies": {}}
    gates_ok = v2["PASS"]
    for name, alloc in S:
        analytic = sum(n * (ev[g] - PRICE[g]) for g, n in alloc.items() if n > 0)
        sm = np.concatenate(season_mean[name])
        sim, se = float(sm.mean()), float(sm.std(ddof=1) / math.sqrt(len(sm)))
        v1 = abs(sim - analytic) <= 4 * se
        gates_ok &= v1
        rec = {"alloc": alloc, "stake_per_date": stake[name], "V1": {"analytic_net_per_date": analytic,
               "sim_net_per_date": sim, "se": se, "pass": bool(v1)}, "horizons": {}}
        for y in YEARS:
            x = np.concatenate(acc[name][y])
            bg = np.concatenate(big[name][y])
            q = np.percentile(x, [1, 5, 25, 50, 75, 95, 99])
            rec["horizons"][str(y)] = {"P_net_ge_0": float((x >= 0).mean()), "stake_total": stake[name] * 104 * y,
                                       "net_mean": float(x.mean()), "net_quantiles_1_5_25_50_75_95_99": q.tolist(),
                                       "return_mean": float(1 + x.mean() / (stake[name] * 104 * y)),
                                       "P_any_prize_ge_1000": float(bg.mean())}
        out["strategies"][name] = rec
    v3 = {}
    for g in ("649", "540", "joker"):
        p_exact = float(sum(P[g], Fr(0)))
        p_sim = sum(first_any[g]) / M
        se = math.sqrt(p_exact * (1 - p_exact) / M)
        v3[g] = {"exact": p_exact, "sim": p_sim, "se": se, "pass": abs(p_sim - p_exact) <= 4 * se}
        gates_ok &= v3[g]["pass"]
    out["V3_prima_data"] = v3
    out["GATES_PASS"] = bool(gates_ok)
    meta["end_utc"] = utc()
    meta["seconds"] = round(time.time() - t0, 1)
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    target.chmod(0o444)
    print("GATES_PASS", gates_ok, "SHA", sha_file(target), flush=True)


if __name__ == "__main__":
    main()
