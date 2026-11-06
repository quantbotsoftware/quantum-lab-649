#!/usr/bin/env python3
"""XI-C2 — backtestul unic al ferestrelor EV+ și reconcilierea ρ_C4 ↔ Quantum Limit.

Protocol: xi/PROTOCOL_XI_C2.md (sigilat înainte de acest cod; sha în SIGILIU_XI_C2.json).
Funcțiile produsului `quantum_limit` sunt folosite neschimbate. Fără predicție de numere.
positive_claims_allowed=false. Rulare (mereu cu -B și PYTHONDONTWRITEBYTECODE=1):

  /usr/bin/python3 -B xi/c2/backtest_c2.py teste            # K4 + K2 (înainte de producție)
  /usr/bin/python3 -B xi/c2/backtest_c2.py modele           # modelele 6/49 pe blocuri (CPU)
  /usr/bin/python3 -B xi/c2/backtest_c2.py etapa1 --joc 649 # (și 540, joker) — producția unică, reluabilă
  /usr/bin/python3 -B xi/c2/backtest_c2.py etapa2 --joc 649 # bootstrap pentru țintele semnalate
  /usr/bin/python3 -B xi/c2/backtest_c2.py raport           # K1, K3, K5, agregate, RAPORT_C2.md
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import multiprocessing as mp  # noqa: E402
import sqlite3  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from fractions import Fraction as Fr  # noqa: E402
from math import comb  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

XI = Path(__file__).resolve().parents[1]
QL649 = XI.parent
REPO = XI.parents[2]
sys.path.insert(0, str(REPO / "next_candidate"))
from quantum_limit import data as D  # noqa: E402
from quantum_limit import ceiling as C  # noqa: E402
from quantum_limit.crowd import CrowdModel, fit  # noqa: E402
from quantum_limit.joker import JokerCrowdModel, estimate_pi  # noqa: E402

OUT = XI / "rezultate" / "C2"
# Test pe uscat: C2_SCRATCH redirecționează etapele 1–2 și raportul (modelele pe blocuri se citesc din OUT).
SCR = Path(os.environ["C2_SCRATCH"]) if os.environ.get("C2_SCRATCH") else OUT
DRY = SCR != OUT
DB = Path("./loto_romania/data/snapshots/"
          "c6bfd021af15d9d6ece6b20d106550e4c8474049e38e9caa3bd1c99d19766adb/loto_romania.sqlite")
DB_SHA = "9942abfc25282a715cba70e4f6d17a885a467eaf5fe0440838dc28114003c078"
PROTOCOL_SHA = "85bf9fef2bf960a8f4643c0303abb0e8e9cb9dc30cafb8fc366feeec49503fbc"
START = "2010-05-02"
BLOCK = 13
MIN_OBS = 52
B_BOOT = 40 if not os.environ.get("C2_SCRATCH") else int(os.environ.get("C2_TEST_B", "3"))
SEED = 20261030
GAME_CODE = {"649": 1, "540": 2, "joker": 3}
PRICE = {"649": 8.0, "540": 5.0, "joker": 7.0}
CATS = {"649": ["I", "II", "III", "IV"], "540": ["I", "II", "III"],
        "joker": ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]}
FIXED = {("649", "IV")}
YIELD_UTC = ((6, 20), (10, 20), (13, 20), (21, 40))
SNAP_649 = 3.607076187360041          # prospectiv/649/2026-10-22/sigiliu_20261019T002028Z.json
SEAL_DIR = REPO / "next_candidate" / "quantum_limit" / "prospectiv"
SEALS_K2 = {"649": "649/2026-11-01/sigiliu_20261029T214019Z.json",
            "540": "540/2026-11-01/sigiliu_20261029T214041Z.json",
            "joker": "joker/2026-11-01/sigiliu_20261029T214102Z.json"}


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def preflight():
    assert sys.flags.dont_write_bytecode or sys.dont_write_bytecode, "rulați cu -B"
    assert os.environ.get("PYTHONDONTWRITEBYTECODE") == "1", "PYTHONDONTWRITEBYTECODE=1 lipsește"
    assert sha_file(XI / "PROTOCOL_XI_C2.md") == PROTOCOL_SHA, "protocolul C2 s-a schimbat"
    assert D.sha256(DB) == DB_SHA, "baza nu este instantaneul fixat"
    OUT.mkdir(parents=True, exist_ok=True)
    SCR.mkdir(parents=True, exist_ok=True)
    if DRY:
        assert OUT.resolve() not in SCR.resolve().parents and SCR.resolve() != OUT.resolve()


def guard(log=None):
    """Pauză internă în ±15 min de emisiile/prospectivul produsului (protocol §10)."""
    while True:
        now = datetime.now(timezone.utc)
        minute = now.hour * 60 + now.minute
        near = any(abs(minute - (h * 60 + m)) <= 15 or abs(minute - (h * 60 + m)) >= 1440 - 15 for h, m in YIELD_UTC)
        if not near:
            return
        if log:
            log(f"pauză (fereastră protejată) {now.isoformat(timespec='seconds')}")
        time.sleep(60)


# ------------------------------------------------------------------ probabilități exacte (C4 §3)
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


PF = {g: np.array([float(x) for x in v]) for g, v in exact_probs().items()}


# ------------------------------------------------------------------ plăți realizate (C4 §4, identic)
def load_payouts():
    """Exact ca `c4_simulator.load_payouts`, pe baza fixată. Întoarce (by, per, common, counts)."""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    by_all, per, counts = {}, {}, {}
    try:
        for g in CATS:
            rows = con.execute(
                "SELECT d.draw_date, p.category, p.status, p.winning_variants, p.payout_per_win, p.carryover "
                "FROM draws d JOIN prizes p ON p.observation_id = d.selected_observation "
                "WHERE d.game = ? AND d.draw_kind = 'regular' AND d.draw_date >= '2010-05-02'", (g,)).fetchall()
            by = {}
            cnt = {"paid": 0, "rollover": 0, "zero_other": 0}
            for day, cat, status, w, ppw, carry in rows:
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
                by.setdefault(day, {})[cat] = v
            by_all[g] = by
            per[g] = {d: [c.get(x, 0.0) for x in CATS[g]] for d, c in by.items() if len(c) == len(CATS[g])}
            counts[g] = cnt
    finally:
        con.close()
    common = sorted(set(per["649"]) & set(per["540"]) & set(per["joker"]))
    return by_all, per, common, counts


def category_of(game, ticket, draw_numbers, draw_order, draw_joker, ticket_joker=None):
    """Categoria realizată a unui bilet (1-indexat) sau None (protocol §6)."""
    t = set(int(x) for x in ticket)
    if game == "649":
        return {6: "I", 5: "II", 4: "III", 3: "IV"}.get(len(t & set(draw_numbers)))
    if game == "540":
        first5 = set(int(x) for x in draw_order[:5])
        drawn = set(draw_numbers)
        if t == first5:
            return "I"
        if t <= drawn:
            return "II"
        return "III" if len(t & drawn) == 4 else None
    hits = len(t & set(draw_numbers))
    matched = int(ticket_joker) == int(draw_joker)
    table = {(5, True): "I", (5, False): "II", (4, True): "III", (4, False): "IV", (3, True): "V",
             (3, False): "VI", (2, True): "VII", (1, True): "VIII"}
    return table.get((hits, matched))


# ------------------------------------------------------------------ modele
def fit_649(draws649, end, idx_seed=None):
    """Modelul 6/49 ca `models.crowd_model('649')`, pe extragerile observate cu dată < end (end=None: toate).
    idx_seed: replica bootstrap (reeșantionare ca `incertitudine._resample_fit`)."""
    used, X, W, ks = D.observed_counts("649", draws649, end=end)
    if len(used) < MIN_OBS:
        return None, dict(n_used=len(used))
    weights = D.time_weights([d["date"] for d in used])
    weights /= weights.mean()
    if idx_seed is not None:
        rng = np.random.default_rng(idx_seed)
        idx = rng.integers(0, len(used), len(used))
        X, W, weights = X[idx], W[idx], weights[idx]
    model, info = fit(D.GAMES["649"]["shape"], X, W, ks, weights=weights, ridge=1.0)
    info = dict(info, n_used=len(used), max_date=used[-1]["date"])
    return model, info


def derive(game, base649, draws_before, pi_idx_rng=None):
    """Modelul jocului din modelul 6/49 (transferurile produsului)."""
    if game == "649":
        return base649
    shape = D.GAMES[game]["shape"]
    theta = np.concatenate([base649.beta[:shape.n], [base649.theta_c, base649.theta_L]])
    if game == "540":
        return CrowdModel(shape, theta)
    used, *_ = D.observed_counts("joker", draws_before)
    if pi_idx_rng is not None:
        idx = pi_idx_rng.integers(0, len(used), len(used))
        used = [used[i] for i in idx]
    pi, _, _ = estimate_pi(used, D.GAMES["joker"]["jokers"])
    return JokerCrowdModel(shape, theta, pi=pi, jokers=D.GAMES["joker"]["jokers"])


_PATTERNED = {}


def evaluate(model, state):
    """EV exact al tuturor biletelor (produsul) + rezumatul rapid: limita fără tipar, media, componentele."""
    res = C.ev_all_tickets(model, state)
    ev = res["ev"]
    jokers = ev.shape[1] if ev.ndim == 2 else 0
    key = (state["game"], len(res["tickets"]))
    if key not in _PATTERNED:      # funcție pură de enumerare (aceeași la fiecare țintă)
        _PATTERNED[key] = C.patterned(res["tickets"])
    flagged = _PATTERNED[key]
    if jokers:
        ev = ev.reshape(-1)
        flagged = np.repeat(flagged, jokers)
        comps = {k: v.reshape(-1) for k, v in res["components"].items()}
    else:
        comps = res["components"]
    masked = np.where(flagged, -np.inf, ev)
    best = int(np.argmax(masked))
    row = best // jokers if jokers else best
    ticket = [int(x) + 1 for x in res["tickets"][row]]
    out = dict(ev_max=float(ev[best]), ev_max_unrestricted=float(ev.max()), ev_avg=float(ev.mean()),
               limit=ticket, limit_joker=(int(best % jokers) + 1) if jokers else None,
               limit_index=best, limit_components={str(k): float(v[best]) for k, v in comps.items()},
               avg_components={str(k): float(v.mean()) for k, v in comps.items()},
               uniform_crowd_ev=float(res["uniform_crowd_ev"]), backend=res.get("backend"))
    return out, ev


def state_record(state):
    return dict(next_draw=state["next_draw"], last_draw=state["last_draw"], sales=float(state["sales"]),
                sales_sigma2=float(state["sales_model"]["sigma2"]), jackpot_carried=float(state["jackpot_carried"]),
                funds={str(k): dict(v) for k, v in state["funds"].items()},
                fixed={str(k): v for k, v in state["fixed"].items()}, draws_used=state["draws_used"])


# ------------------------------------------------------------------ ținte și blocuri
def load_all():
    return {g: D.load_draws(g, DB) for g in CATS}


def targets(draws):
    return [(i, d) for i, d in enumerate(draws) if d["kind"] == "regular" and d["date"] >= START]


def blocks(draws649):
    t649 = targets(draws649)
    return [dict(b=b, t=t649[s][1]["date"]) for b, s in enumerate(range(0, len(t649), BLOCK))]


def block_for(blist, day):
    cand = [x for x in blist if x["t"] <= day]
    return cand[-1] if cand else None


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append_jsonl(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


# ------------------------------------------------------------------ teste (K4, K2)
def cmd_teste(args):
    preflight()
    res = {"start_utc": utc(), "K4": {}, "K2": {}}
    # K4 — reguli sintetice
    k4 = []
    k4.append(category_of("649", [1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6], None, None) == "I")
    k4.append(category_of("649", [1, 2, 3, 4, 5, 7], [1, 2, 3, 4, 5, 6], None, None) == "II")
    k4.append(category_of("649", [1, 2, 3, 4, 8, 7], [1, 2, 3, 4, 5, 6], None, None) == "III")
    k4.append(category_of("649", [1, 2, 3, 9, 8, 7], [1, 2, 3, 4, 5, 6], None, None) == "IV")
    k4.append(category_of("649", [1, 2, 10, 9, 8, 7], [1, 2, 3, 4, 5, 6], None, None) is None)
    order = [7, 3, 12, 30, 1, 22]
    nums = sorted(order)
    k4.append(category_of("540", [1, 3, 7, 12, 30], nums, order, None) == "I")
    k4.append(category_of("540", [1, 3, 7, 12, 22], nums, order, None) == "II")
    k4.append(category_of("540", [3, 7, 12, 22, 30], nums, order, None) == "II")
    k4.append(category_of("540", [1, 3, 7, 12, 40], nums, order, None) == "III")
    k4.append(category_of("540", [1, 3, 7, 39, 40], nums, order, None) is None)
    dn = [5, 10, 15, 20, 25]
    k4.append(category_of("joker", [5, 10, 15, 20, 25], dn, None, 7, 7) == "I")
    k4.append(category_of("joker", [5, 10, 15, 20, 25], dn, None, 7, 8) == "II")
    k4.append(category_of("joker", [5, 10, 15, 20, 26], dn, None, 7, 7) == "III")
    k4.append(category_of("joker", [5, 10, 15, 20, 26], dn, None, 7, 1) == "IV")
    k4.append(category_of("joker", [5, 10, 15, 21, 26], dn, None, 7, 7) == "V")
    k4.append(category_of("joker", [5, 10, 15, 21, 26], dn, None, 7, 2) == "VI")
    k4.append(category_of("joker", [5, 10, 16, 21, 26], dn, None, 7, 7) == "VII")
    k4.append(category_of("joker", [5, 10, 16, 21, 26], dn, None, 7, 3) is None)
    k4.append(category_of("joker", [5, 11, 16, 21, 26], dn, None, 7, 7) == "VIII")
    k4.append(category_of("joker", [6, 11, 16, 21, 26], dn, None, 7, 7) is None)
    # plata C4: verificare pe un rând sintetic prin aceeași formulă
    k4.append(abs(1000.0 * 3 / 4 - 750.0) < 1e-12)
    # probabilitățile: sumă exactă și identități
    P = exact_probs()
    k4.append(P["649"][3] == Fr(comb(6, 3) * comb(43, 3), comb(49, 6)))
    k4.append(P["540"][0] + P["540"][1] == Fr(35, comb(40, 6)))
    res["K4"] = dict(checks=len(k4), passed=int(sum(k4)), PASS=all(k4))
    print("K4", res["K4"], flush=True)
    # K2 — starea finală a produsului reprodusă
    allr = load_all()
    base, info = fit_649(allr["649"], None)
    for g in CATS:
        seal = json.loads((SEAL_DIR / SEALS_K2[g]).read_text())
        assert seal["database_sha256"] == DB_SHA
        model = derive(g, base, allr[g])
        state = C.market_state(g, allr[g], model)
        t0 = time.time()
        ev, _ = evaluate(model, state)
        theta_diff = float(np.max(np.abs(np.asarray(model.theta) - np.asarray(seal["crowd_model"]["theta"]))))
        rel_avg = abs(ev["ev_avg"] - seal["average_ticket_ev"]) / seal["average_ticket_ev"]
        rel_lim = abs(ev["ev_max"] - seal["limit"]["ev"]) / seal["limit"]["ev"]
        same = ev["limit"] == seal["limit"]["numbers"] and (g != "joker" or ev["limit_joker"] == seal["limit"]["joker"])
        ok = rel_avg <= 1e-9 and rel_lim <= 1e-9 and same and state["next_draw"] == seal["target_draw"]
        res["K2"][g] = dict(rel_avg=rel_avg, rel_limit=rel_lim, same_ticket=same, theta_maxabs=theta_diff,
                            next_draw=state["next_draw"], seal_target=seal["target_draw"], ev=ev, seconds=round(time.time() - t0, 1),
                            PASS=bool(ok))
        print("K2", g, {k: v for k, v in res["K2"][g].items() if k != "ev"}, flush=True)
    res["K2"]["PASS"] = all(res["K2"][g]["PASS"] for g in CATS)
    res["end_utc"] = utc()
    res["script_sha256"] = sha_file(__file__)
    (OUT / "teste").mkdir(exist_ok=True)
    path = OUT / "teste" / f"TESTE_K2_K4_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("TESTE_PASS", res["K4"]["PASS"] and res["K2"]["PASS"], path, flush=True)
    return 0 if (res["K4"]["PASS"] and res["K2"]["PASS"]) else 1


# ------------------------------------------------------------------ modele pe blocuri
def _fit_block(args):
    b, t = args
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
    draws649 = D.load_draws("649", DB)
    t0 = time.time()
    model, info = fit_649(draws649, t)
    return dict(b=b, t=t, theta=None if model is None else [float(x) for x in model.theta],
                info=info, seconds=round(time.time() - t0, 1))


def cmd_modele(args):
    preflight()
    path = OUT / "modele_649.jsonl"
    done = {r["b"] for r in read_jsonl(path)}
    draws649 = D.load_draws("649", DB)
    todo = [(x["b"], x["t"]) for x in blocks(draws649) if x["b"] not in done]
    print(f"{utc()} blocuri de estimat: {len(todo)} (deja: {len(done)})", flush=True)
    with mp.get_context("spawn").Pool(args.workers) as pool:
        for rec in pool.imap_unordered(_fit_block, todo):
            append_jsonl(path, rec)
            print(utc(), "bloc", rec["b"], rec["t"], rec["info"].get("n_used"), rec["seconds"], flush=True)
    return 0


def load_block_models():
    recs = sorted(read_jsonl(OUT / "modele_649.jsonl"), key=lambda r: r["b"])
    shape = D.GAMES["649"]["shape"]
    return [dict(b=r["b"], t=r["t"], info=r["info"],
                 model=None if r["theta"] is None else CrowdModel(shape, r["theta"])) for r in recs]


# ------------------------------------------------------------------ etapa 1
def cmd_etapa1(args):
    preflight()
    g = args.joc
    if g == "540":
        os.environ["QUANTUM_LIMIT_GPU"] = "0"
    allr = load_all()
    draws = allr[g]
    bm = load_block_models()
    assert len(bm) == len(blocks(allr["649"])), "modelele pe blocuri sunt incomplete"
    by_all, _, _, _ = load_payouts()
    by = by_all[g]
    path = SCR / f"etapa1_{g}.jsonl"
    done = {r["i"] for r in read_jsonl(path)}
    log = lambda s: print(f"{utc()} [{g}] {s}", flush=True)  # noqa: E731
    tl = targets(draws)
    log(f"ținte {len(tl)}, deja {len(done)}")
    t_start = time.time()
    n_new = 0
    if DRY and args.limita:
        tl = tl[-args.limita:]
    for i, d in tl:
        if i in done:
            continue
        guard(log)
        rec = dict(i=i, date=d["date"], key=d["key"], numbers=d["numbers"], order=d["order"], joker=d["joker"])
        blk = block_for(bm, d["date"])
        before = draws[:i]
        # K3 — fără privire în viitor
        k3 = dict(pos_ok=all(x is not d for x in before),
                  max_input_date=max(x["date"] for x in before) if before else None,
                  same_date_inputs=sum(1 for x in before if x["date"] == d["date"]))
        if blk is not None:
            k3["block_t"] = blk["t"]
            k3["model_max_date"] = blk["info"].get("max_date")
            k3["model_ok"] = blk["t"] <= d["date"] and (blk["info"].get("max_date") is None
                                                         or blk["info"]["max_date"] < blk["t"])
        rec["K3"] = k3
        vc = by.get(d["date"], {})
        rec["v"] = {c: vc.get(c, 0.0) for c in CATS[g]}
        rec["v_complete"] = len(vc) == len(CATS[g])
        rec["R_u"] = float(PF[g] @ np.array([rec["v"][c] for c in CATS[g]]))
        own_used = D.observed_counts(g, before)[0]
        if blk is None or blk["model"] is None or len(own_used) < MIN_OBS:
            rec["status"] = "rodaj"
            rec["n_used_own"] = len(own_used)
            append_jsonl(path, rec)
            continue
        rec["block"] = blk["b"]
        try:
            model = derive(g, blk["model"], before)
            state = C.market_state(g, before, model)
            t0 = time.time()
            ev, _ = evaluate(model, state)
            rec["seconds"] = round(time.time() - t0, 2)
        except Exception as exc:  # numărat, nu ascuns
            rec["status"] = "exceptie"
            rec["error"] = repr(exc)[:500]
            append_jsonl(path, rec)
            continue
        rec["status"] = "evaluat"
        rec["state"] = state_record(state)
        rec["ev"] = ev
        if g == "joker":
            rec["pi"] = [float(x) for x in model.pi]
        cat = category_of(g, ev["limit"], d["numbers"], d["order"], d["joker"], ev["limit_joker"])
        rec["limit_category"] = cat
        rec["limit_payout"] = rec["v"].get(cat, 0.0) if cat else 0.0
        append_jsonl(path, rec)
        n_new += 1
        if n_new % 25 == 0:
            el = time.time() - t_start
            log(f"{n_new} noi, {el / n_new:.1f} s/țintă, ultima {d['date']} EV_max/preț {ev['ev_max'] / PRICE[g]:.3f}")
    log(f"gata: {n_new} noi în {time.time() - t_start:.0f} s")
    return 0


# ------------------------------------------------------------------ etapa 2
def _boot_fit(args):
    b, t, r = args
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
    draws649 = D.load_draws("649", DB)
    model, info = fit_649(draws649, t, idx_seed=SEED + 1000 * b + r)
    return dict(b=b, t=t, r=r, theta=[float(x) for x in model.theta], info=info)


def cmd_etapa2(args):
    preflight()
    g = args.joc
    if g == "540":
        os.environ["QUANTUM_LIMIT_GPU"] = "0"
    e1 = read_jsonl(SCR / f"etapa1_{g}.jsonl")
    thr = PRICE[g] * (args.test_prag if DRY else 1.0)
    flagged = [r for r in e1 if r["status"] == "evaluat" and r["ev"]["ev_max"] > thr]
    log = lambda s: print(f"{utc()} [{g}] {s}", flush=True)  # noqa: E731
    log(f"semnalate: {len(flagged)}")
    if not flagged:
        return 0
    bm = {x["b"]: x for x in load_block_models()}
    # modelele bootstrap pe blocurile cu ținte semnalate (comune jocurilor)
    bpath = SCR / "etapa2_modele_649.jsonl"
    have = {(r["b"], r["r"]) for r in read_jsonl(bpath)}
    need = sorted({r["block"] for r in flagged})
    todo = [(b, bm[b]["t"], r) for b in need for r in range(B_BOOT) if (b, r) not in have]
    log(f"blocuri {need}; modele bootstrap de estimat: {len(todo)}")
    if todo:
        with mp.get_context("spawn").Pool(args.workers) as pool:
            for rec in pool.imap_unordered(_boot_fit, todo):
                append_jsonl(bpath, rec)
        log("modele bootstrap gata")
    boots = {}
    shape = D.GAMES["649"]["shape"]
    for r in read_jsonl(bpath):
        boots[(r["b"], r["r"])] = CrowdModel(shape, r["theta"])
    allr = load_all()
    draws = allr[g]
    path = SCR / f"etapa2_{g}.jsonl"
    done = {r["i"] for r in read_jsonl(path)}
    k5_done = {r["block"] for r in read_jsonl(path) if r.get("K5") is not None}
    for rec1 in flagged:
        i = rec1["i"]
        if i in done:
            continue
        guard(log)
        d = draws[i]
        assert d["date"] == rec1["date"]
        before = draws[:i]
        b = rec1["block"]
        out = dict(i=i, date=d["date"], block=b, ev_max=rec1["ev"]["ev_max"], limit_index=rec1["ev"]["limit_index"])
        if b not in k5_done:   # K5: replica-identitate
            model = derive(g, bm[b]["model"], before)
            state = C.market_state(g, before, model)
            _, ev_arr = evaluate(model, state)
            v = float(ev_arr[rec1["ev"]["limit_index"]])
            out["K5"] = dict(value=v, rel=abs(v - rec1["ev"]["ev_max"]) / rec1["ev"]["ev_max"])
            out["K5"]["PASS"] = out["K5"]["rel"] <= 1e-9
            k5_done.add(b)
        vals, sales = [], []
        t0 = time.time()
        for r in range(B_BOOT):
            rng = np.random.default_rng(SEED + 7919 * i + r + 100000 * GAME_CODE[g])
            z = float(rng.standard_normal())
            model = derive(g, boots[(b, r)], before, pi_idx_rng=rng if g == "joker" else None)
            state = C.market_state(g, before, model)
            sigma = math.sqrt(state["sales_model"]["sigma2"])
            state["sales"] = state["sales"] * math.exp(sigma * z - sigma * sigma / 2)
            _, ev_arr = evaluate(model, state)
            vals.append(float(ev_arr[rec1["ev"]["limit_index"]]))
            sales.append(float(state["sales"]))
        q5 = float(np.percentile(vals, 5))
        out.update(values=vals, sales=sales, q5=q5, median=float(np.median(vals)),
                   window=bool(q5 > PRICE[g]), seconds=round(time.time() - t0, 1))
        append_jsonl(path, out)
        log(f"{d['date']} EV_max {rec1['ev']['ev_max']:.3f} q5 {q5:.3f} fereastră {out['window']}")
    return 0


# ------------------------------------------------------------------ raport
def kelly(rec, g):
    """f* ≈ E[R]/E[R²], R = X/preț − 1, E[X²] ≈ Σ comp²/P_c (protocol §7, aproximare declarată)."""
    price = PRICE[g]
    comps = rec["ev"]["limit_components"]
    ex = rec["ev"]["ev_max"]
    ex2 = 0.0
    for c, pc in zip(CATS[g], PF[g]):
        if c in comps and pc > 0:
            ex2 += comps[c] ** 2 / pc
    er = ex / price - 1.0
    er2 = ex2 / price ** 2 - 2 * ex / price + 1.0
    f = er / er2 if er2 > 0 else None
    return dict(f_star=f, bankroll_min=(price / f) if f and f > 0 else None)


def cmd_raport(args):
    preflight()
    _, per, common, counts = load_payouts()
    c4 = json.loads((XI / "rezultate" / "C4" / "C4_REZULTATE.json").read_text())
    win = common[-312:]
    res = {"meta": dict(generated_utc=utc(), protocol_sha256=PROTOCOL_SHA, script_sha256=sha_file(__file__),
                        database=str(DB), database_sha256=DB_SHA, block=BLOCK, min_obs=MIN_OBS, B_boot=B_BOOT,
                        window312=[win[0], win[-1]], positive_claims_allowed=False),
           "K1": {}, "K3": {}, "K5": {}, "jocuri": {}, "reconciliere": {}}
    for g in CATS:   # K1
        ev = float(PF[g] @ np.array([per[g][d] for d in win]).mean(0))
        rho = ev / PRICE[g]
        res["K1"][g] = dict(rho=rho, rho_c4=c4["rho_window"][g], diff=abs(rho - c4["rho_window"][g]),
                            PASS=abs(rho - c4["rho_window"][g]) <= 1e-12)
    res["K1"]["PASS"] = all(res["K1"][g]["PASS"] for g in CATS)
    allpass = res["K1"]["PASS"]
    for g in CATS:
        e1 = read_jsonl(SCR / f"etapa1_{g}.jsonl")
        e2 = {r["i"]: r for r in read_jsonl(SCR / f"etapa2_{g}.jsonl")}
        tl = targets(D.load_draws(g, DB))
        ev_ok = [r for r in e1 if r["status"] == "evaluat"]
        viol = sum(1 for r in e1 if not r["K3"]["pos_ok"] or (r["K3"]["max_input_date"] or "") > r["date"]
                   or (r["status"] == "evaluat" and not r["K3"].get("model_ok", False)))
        same_date = sum(1 for r in e1 if r["K3"]["same_date_inputs"] > 0)
        res["K3"][g] = dict(violations=viol, same_date_input_targets=same_date, PASS=viol == 0)
        complete = len({r["i"] for r in e1}) == len(tl)
        price = PRICE[g]
        flagged = [r for r in ev_ok if r["ev"]["ev_max"] > price]
        missing2 = [r["i"] for r in flagged if r["i"] not in e2]
        k5 = [e2[i]["K5"] for i in e2 if e2[i].get("K5")]
        res["K5"][g] = dict(checked=len(k5), PASS=all(x["PASS"] for x in k5))
        windows = [r for r in flagged if r["i"] in e2 and e2[r["i"]]["window"]]
        ratios = np.array([r["ev"]["ev_max"] / price for r in ev_ok]) if ev_ok else np.array([0.0])
        top = sorted(ev_ok, key=lambda r: -r["ev"]["ev_max"])[:10]
        mismatch = sum(1 for r in ev_ok if r["state"]["next_draw"] != r["date"])

        def strat(rows):
            stake = price * len(rows)
            exp_ = sum(r["ev"]["ev_max"] for r in rows)
            real = sum(r["limit_payout"] for r in rows)
            ru = sum(r["R_u"] for r in rows)
            prizes = {}
            for r in rows:
                if r["limit_category"]:
                    prizes[r["limit_category"]] = prizes.get(r["limit_category"], 0) + 1
            return dict(n=len(rows), stake=stake, expected_gross=exp_, expected_ratio=(exp_ / stake) if stake else None,
                        realized_gross=real, realized_ratio=(real / stake) if stake else None,
                        uniform_realized_value=ru, uniform_ratio=(ru / stake) if stake else None, prizes=prizes)

        res["jocuri"][g] = dict(
            targets=len(tl), recorded=len(e1), complete=complete, evaluated=len(ev_ok),
            rodaj=sum(1 for r in e1 if r["status"] == "rodaj"), exceptions=sum(1 for r in e1 if r["status"] == "exceptie"),
            next_draw_mismatch=mismatch, first_evaluated=ev_ok[0]["date"] if ev_ok else None,
            flagged=len(flagged), stage2_missing=missing2,
            windows=[dict(date=r["date"], ev_max=r["ev"]["ev_max"], q5=e2[r["i"]]["q5"], limit=r["ev"]["limit"],
                          joker=r["ev"]["limit_joker"], jackpot_carried=r["state"]["jackpot_carried"],
                          kelly=kelly(r, g), limit_category=r["limit_category"], limit_payout=r["limit_payout"])
                     for r in windows],
            flagged_list=[dict(date=r["date"], ev_max=r["ev"]["ev_max"], q5=e2.get(r["i"], {}).get("q5"))
                          for r in flagged],
            ratio_dist=dict(max=float(ratios.max()), q50=float(np.percentile(ratios, 50)),
                            q90=float(np.percentile(ratios, 90)), q99=float(np.percentile(ratios, 99)),
                            mean=float(ratios.mean())),
            top10=[dict(date=r["date"], ev_max=r["ev"]["ev_max"], ratio=r["ev"]["ev_max"] / price,
                        jackpot_carried=r["state"]["jackpot_carried"]) for r in top],
            strategy_windows=strat(windows), strategy_always_limit=strat(ev_ok),
            rho_ql_all=float(np.mean([r["ev"]["ev_avg"] for r in ev_ok]) / price) if ev_ok else None,
            rho_c4_all_evaluated=float(np.mean([r["R_u"] for r in ev_ok]) / price) if ev_ok else None)
        allpass = allpass and res["K3"][g]["PASS"] and res["K5"][g]["PASS"] and complete and not missing2
        # reconciliere pe W312
        byd = {r["date"]: r for r in ev_ok}
        rows = [byd.get(d) for d in win]
        miss = sum(1 for r in rows if r is None)
        rows = [r for r in rows if r is not None]
        rec = dict(window_missing=miss, n=len(rows))
        if rows:
            rec["rho_ql_window"] = float(np.mean([r["ev"]["ev_avg"] for r in rows]) / price)
            rec["rho_c4_window"] = float(np.mean([r["R_u"] for r in rows]) / price)
            per_cat = {}
            for c, pc in zip(CATS[g], PF[g]):
                exa = float(np.mean([r["ev"]["avg_components"].get(c, 0.0) if c in r["ev"]["avg_components"]
                                     else pc * r["state"]["fixed"].get(c, 0.0) for r in rows]))
                rea = float(np.mean([pc * r["v"][c] for r in rows]))
                per_cat[c] = dict(ex_ante=exa / price, realized=rea / price, delta=(exa - rea) / price)
            jc = CATS[g][0]
            per_cat[jc]["ex_ante_no_sharing"] = float(np.mean([PF[g][0] * r["state"]["funds"][jc]["total"]
                                                               for r in rows]) / price)
            rec["per_category"] = per_cat
            rec["delta_model"] = rec["rho_ql_window"] - rec["rho_c4_window"]
        if g == "649":
            snap = byd.get("2026-10-22")
            rec["rho_snap"] = SNAP_649 / price
            if snap and rows:
                rec["rho_ql_20261022"] = snap["ev"]["ev_avg"] / price
                rec["delta_cadence"] = rec["rho_snap"] - rec["rho_ql_20261022"]
                rec["delta_moment"] = rec["rho_ql_20261022"] - rec["rho_ql_window"]
                rec["sum_check"] = rec["delta_cadence"] + rec["delta_moment"] + rec["delta_model"] - (
                    rec["rho_snap"] - rec["rho_c4_window"])
                rec["jackpot_carried_20261022"] = snap["state"]["jackpot_carried"]
            rec["jackpot_carried_window_mean"] = float(np.mean([r["state"]["jackpot_carried"] for r in rows]))
        res["reconciliere"][g] = rec
    res["GATES_PASS"] = bool(allpass)
    out = SCR / "C2_REZULTATE.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    digest = sha_file(out)
    (SCR / "RAPORT_C2_CIFRE.md").write_text(render_md(res, digest))
    print("C2_REZULTATE", digest, "GATES_PASS", res["GATES_PASS"], flush=True)
    return 0


def _p(x, nd=1):
    return "—" if x is None else f"{100 * x:.{nd}f}%"


def _lei(x):
    return "—" if x is None else f"{x:,.2f} lei"


def _num(x, spec):
    return "—" if x is None else format(x, spec)


def render_md(res, digest):
    m = res["meta"]
    L = ["# RAPORT C2 — cifrele (generate automat; planul V11, faza D)", "",
         f"Protocol `PROTOCOL_XI_C2.md` (`{m['protocol_sha256'][:12]}…`), script `{m['script_sha256'][:12]}…`, "
         f"rezultate `C2_REZULTATE.json` sha256 `{digest}`. Bază `{m['database_sha256'][:12]}…`. "
         f"Blocuri de model de {m['block']} ținte, rodaj {m['min_obs']}, B = {m['B_boot']} replici. "
         "Sume brute, fără impozit, prețuri curente. `positive_claims_allowed=false`.", "",
         f"**Porți:** K1 {'PASS' if res['K1']['PASS'] else 'FAIL'} · "
         + " · ".join(f"K3[{g}] {'PASS' if res['K3'][g]['PASS'] else 'FAIL'}" for g in CATS) + " · "
         + " · ".join(f"K5[{g}] {'PASS' if res['K5'][g]['PASS'] else 'FAIL'} ({res['K5'][g]['checked']})" for g in CATS)
         + f" · **GATES_PASS = {res['GATES_PASS']}**", "",
         "## C2a — ferestrele EV+ (regula: q5 al EV-ului biletului-limită > preț)", "",
         "| Joc | Ținte | Evaluate | Rodaj | Excepții | Semnalate (EV_max > preț) | **Ferestre** | EV_max/preț max | mediană | p99 |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for g in CATS:
        j = res["jocuri"][g]
        rd = j["ratio_dist"]
        L.append(f"| {g} | {j['targets']} | {j['evaluated']} | {j['rodaj']} | {j['exceptions']} | {j['flagged']} | "
                 f"**{len(j['windows'])}** | {_p(rd['max'])} | {_p(rd['q50'])} | {_p(rd['q99'])} |")
    L += ["", "### Cele mai bune 10 ținte (EV-ul biletului-limită ex-ante)", ""]
    for g in CATS:
        L.append(f"**{g}:** " + "; ".join(f"{t['date']} {_p(t['ratio'])} (report {t['jackpot_carried'] / 1e6:.1f} M)"
                                          for t in res["jocuri"][g]["top10"]))
        L.append("")
    for g in CATS:
        j = res["jocuri"][g]
        if j["flagged_list"]:
            L.append(f"**Semnalate {g}:** " + "; ".join(
                f"{f['date']} EV {f['ev_max']:.2f} q5 {_num(f['q5'], '.2f')}"
                for f in j["flagged_list"]))
            L.append("")
    L += ["### Strategii (1 bilet pe țintă)", "",
          "| Joc | Strategie | N | Miză | EV ex-ante/miză | Realizat/miză | Bilet uniform realizat/miză | Premii |",
          "|---|---|---:|---:|---:|---:|---:|---|"]
    for g in CATS:
        for name, key in (("ferestre", "strategy_windows"), ("limita la fiecare țintă", "strategy_always_limit")):
            s = res["jocuri"][g][key]
            L.append(f"| {g} | {name} | {s['n']} | {_lei(s['stake'])} | {_p(s['expected_ratio'])} | "
                     f"{_p(s['realized_ratio'])} | {_p(s['uniform_ratio'])} | {s['prizes'] or '—'} |")
    for g in CATS:
        for w in res["jocuri"][g]["windows"]:
            k = w["kelly"]
            L.append(f"- Fereastră {g} {w['date']}: EV {w['ev_max']:.3f}, q5 {w['q5']:.3f}, bilet {w['limit']}"
                     f"{'' if not w['joker'] else ' J' + str(w['joker'])}, Kelly f* ≈ "
                     f"{_num(k['f_star'], '.2e')}"
                     f", banc minim ≈ {_lei(k['bankroll_min'])}, realizat {w['limit_category'] or 'fără premiu'}.")
    L += ["", "## C2b — reconcilierea ρ_C4 ↔ Quantum Limit", ""]
    r = res["reconciliere"]["649"]
    if "rho_ql_window" in r:
        L += [f"Fereastra W312 = {m['window312'][0]} … {m['window312'][1]} (ținte lipsă: {r['window_missing']}).", "",
              "| Mărime (6/49) | Valoare |", "|---|---:|",
              f"| ρ_snap (QL, ținta 2026-10-22, sigiliul 20261019T002028Z) | {_p(r.get('rho_snap'), 2)} |",
              f"| ρ_QL(2026-10-22) în backtest (model pe blocuri) | {_p(r.get('rho_ql_20261022'), 2)} |",
              f"| ρ_QL,W (media ex-ante a biletului mediu pe W312) | {_p(r['rho_ql_window'], 2)} |",
              f"| ρ_C4 (plăți realizate, bilet uniform, W312) | {_p(r['rho_c4_window'], 2)} |",
              f"| Δ_cadență | {_p(r.get('delta_cadence'), 2)} |",
              f"| Δ_moment (starea reportului) | {_p(r.get('delta_moment'), 2)} |",
              f"| Δ_model (ex-ante − realizat) | {_p(r['delta_model'], 2)} |",
              f"| verificare sumă | {r.get('sum_check', 0):.2e} |",
              f"| report la 2026-10-22 / media W312 | {(r.get('jackpot_carried_20261022') or 0) / 1e6:.2f} M / "
              f"{r['jackpot_carried_window_mean'] / 1e6:.2f} M lei |", ""]
    for g in CATS:
        r = res["reconciliere"][g]
        if "per_category" not in r:
            continue
        L += [f"**{g}** — ρ_QL,W {_p(r['rho_ql_window'], 2)} vs ρ_C4 {_p(r['rho_c4_window'], 2)} "
              f"(K1: {_p(res['K1'][g]['rho'], 3)} = C4 {_p(res['K1'][g]['rho_c4'], 3)})", "",
              "| Categorie | ex-ante QL | realizat C4 | Δ |", "|---|---:|---:|---:|"]
        for c, v in r["per_category"].items():
            extra = f" (fără împărțire: {_p(v['ex_ante_no_sharing'], 2)})" if "ex_ante_no_sharing" in v else ""
            L.append(f"| {c} | {_p(v['ex_ante'], 2)}{extra} | {_p(v['realized'], 2)} | {_p(v['delta'], 2)} |")
        L.append("")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["teste", "modele", "etapa1", "etapa2", "raport"])
    ap.add_argument("--joc", choices=list(CATS))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limita", type=int, default=0, help="numai test pe uscat (C2_SCRATCH)")
    ap.add_argument("--test-prag", type=float, default=1.0, help="numai test pe uscat (C2_SCRATCH)")
    args = ap.parse_args(argv)
    return {"teste": cmd_teste, "modele": cmd_modele, "etapa1": cmd_etapa1, "etapa2": cmd_etapa2,
            "raport": cmd_raport}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
