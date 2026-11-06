#!/usr/bin/env python3
"""XI-C1 §5 — permutarea anti-mulțime a unui design verificat (aceeași garanție, EV mai mare după modelul mulțimii).

EV: quantum_limit.ceiling.ev_all_tickets(model, state) pe baza curentă (read-only). Obiectiv: Σ_t EV(π(t)).
Recoacere pe transpoziții de numere; la Joker, pentru π fix, permutarea Jokerilor optimă exact (asignare 20×20).
Comparatori: identitatea și 1 000 de permutări aleatoare (seed 20261030).
Utilizare: .venv/bin/python -B xi/c1/permutare.py <design.json> [--iter 200000]
positive_claims_allowed=false. EV-ul este al modelului mulțimii, nu un avantaj demonstrat.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = Path(__file__).resolve().parent
XI = HERE.parent
REPO = XI.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "next_candidate"))
import designuri as DS  # noqa: E402
from quantum_limit import data as D  # noqa: E402
from quantum_limit import combinatorics as cb  # noqa: E402
from quantum_limit.ceiling import ev_all_tickets, market_state, patterned  # noqa: E402
from quantum_limit.models import crowd_model  # noqa: E402

OUT = XI / "rezultate" / "C1" / "permutare"
SEED = 20261030


class EVTable:
    def __init__(self, game: str):
        db = Path(D.default_database())
        draws = D.load_draws(game, db)
        model, info, source = crowd_model(game, db, draws)
        state = market_state(game, draws, model)
        res = ev_all_tickets(model, state)
        self.game, self.db, self.db_sha = game, str(db), D.sha256(db)
        self.n = 45 if game == "joker" else 49
        self.ev = np.asarray(res["ev"], dtype=np.float64)        # (count,) sau (count, 20)
        tickets = np.asarray(res["tickets"])
        self.table = cb.binomial_table(self.n)
        ranks = cb.rank(tickets, self.table)
        self.inv = np.empty(len(ranks), dtype=np.int64)
        self.inv[ranks] = np.arange(len(ranks))
        self.state_info = {k: state.get(k) for k in ("game", "sales", "next_date") if k in state}
        self.source = source

    def rows(self, nums0: np.ndarray) -> np.ndarray:
        """nums0: (N, k) 0-based, nesortate → rândurile în enumerare."""
        s = np.sort(nums0, axis=1)
        return self.inv[cb.rank(s, self.table)]


def objective(T: EVTable, nums0, jok0, perm):
    """Σ EV pentru eticheta perm (array n → n); la Joker cu asignarea optimă a Jokerilor. Întoarce (valoare, sigma)."""
    r = T.rows(perm[nums0])
    if T.game != "joker":
        return float(T.ev[r].sum()), None
    E = T.ev[r]                                                     # (N, 20)
    M = np.zeros((20, 20))
    np.add.at(M, jok0, E)                                           # M[j_design, j_nou]
    a, b = linear_sum_assignment(-M)
    sigma = np.empty(20, dtype=np.int64)
    sigma[a] = b
    return float(M[a, b].sum()), sigma


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design", type=Path)
    ap.add_argument("--iter", type=int, default=200000)
    a = ap.parse_args()
    t0 = time.time()
    d = json.loads(a.design.read_text())
    game = d["game"]
    T = EVTable(game)
    tk = 5 if game == "joker" else 6
    tick = np.array([t[:tk] for t in d["tickets"]], dtype=np.int64) - 1
    jok = np.array([t[5] - 1 for t in d["tickets"]], dtype=np.int64) if game == "joker" else None
    rng = np.random.default_rng(SEED)
    ident = np.arange(T.n)
    v_id, _ = objective(T, tick, jok, ident)
    if game == "joker":  # identitatea strictă (fără reasignarea Jokerilor), informativ
        v_id_strict = float(T.ev[T.rows(tick), jok].sum())
    else:
        v_id_strict = v_id
    def npat(p):  # AMENDAMENT_XI_C1_02: bilete în afara domeniului validat al modelului
        return int(patterned(np.sort(p[tick], axis=1) + 1).sum())

    rand, rand_ok, perms_ok = [], [], []
    for _ in range(1000):
        p = rng.permutation(T.n)
        v, _ = objective(T, tick, jok, p)
        rand.append(v)
        if npat(p) == 0:
            rand_ok.append(v)
            perms_ok.append(p)
    rand, rand_ok = np.array(rand), np.array(rand_ok)
    # recoacere pe transpoziții, numai prin stări fără bilete marcate, de la cea mai bună permutare aleatoare validă
    perm = perms_ok[int(np.argmax(rand_ok))].copy()
    cur, sig = objective(T, tick, jok, perm)
    best, best_perm, best_sig = cur, perm.copy(), sig
    temp0 = max(1e-9, float(rand_ok.std()) / 5)
    for it in range(a.iter):
        temp = temp0 * (1 - it / a.iter) + 1e-12
        i, j = rng.choice(T.n, 2, replace=False)
        perm[i], perm[j] = perm[j], perm[i]
        if npat(perm) > 0:
            perm[i], perm[j] = perm[j], perm[i]
            continue
        v, s = objective(T, tick, jok, perm)
        if v >= cur or rng.random() < math.exp((v - cur) / temp):
            cur, sig = v, s
            if v > best:
                best, best_perm, best_sig = v, perm.copy(), s
        else:
            perm[i], perm[j] = perm[j], perm[i]
    newt = (best_perm[tick] + 1).tolist()
    if game == "joker":
        tickets = [sorted(x) + [int(best_sig[j]) + 1] for x, j in zip(newt, jok)]
    else:
        tickets = [sorted(x) for x in newt]
    v_chk, _ = objective(T, best_perm[tick] - best_perm[tick] + np.array([t[:tk] for t in tickets]) - 1,
                         np.array([t[5] - 1 for t in tickets]) if game == "joker" else None, ident)
    price = 7.0 if game == "joker" else 8.0
    N = len(tickets)
    name = d["name"] + "Q"
    assert npat(best_perm) == 0
    f = DS.write_design(game, name, tickets, {"constructie": "XI-C1 §5 permutare anti-mulțime",
                                              "din": d["name"], "din_sha256": d["sha256_tickets"],
                                              "perm_numere_1based": (best_perm + 1).tolist(),
                                              "perm_joker_1based": ((best_sig + 1).tolist() if game == "joker" else None)})
    rep = {"design": d["name"], "design_permutat": name, "fisier": str(f),
           "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "game": game, "n_tickets": N,
           "cost_lei": N * price, "database": T.db, "database_sha256": T.db_sha, "crowd_source": T.source,
           "EV_identitate_lei": v_id_strict, "EV_identitate_cu_asignare_joker_lei": v_id,
           "EV_aleator": {"medie": float(rand.mean()), "q05": float(np.quantile(rand, .05)),
                          "q50": float(np.quantile(rand, .5)), "q95": float(np.quantile(rand, .95)),
                          "max": float(rand.max())},
           "EV_aleator_fara_marcate": {"n": int(len(rand_ok)), "medie": float(rand_ok.mean()),
                                       "q05": float(np.quantile(rand_ok, .05)), "q50": float(np.quantile(rand_ok, .5)),
                                       "q95": float(np.quantile(rand_ok, .95)), "max": float(rand_ok.max())},
           "bilete_marcate_identitate": npat(ident), "bilete_marcate_optimizat": npat(best_perm),
           "castig_fata_de_media_aleatoare_valida_lei": best - float(rand_ok.mean()),
           "amendament": "AMENDAMENT_XI_C1_02 (zero bilete marcate patterned)",
           "EV_optimizat_lei": best, "EV_recalculat_pe_biletele_scrise": v_chk,
           "castig_fata_de_identitate_lei": best - v_id_strict,
           "castig_fata_de_media_aleatoare_lei": best - float(rand.mean()),
           "castig_pct_din_cost_fata_de_identitate": 100 * (best - v_id_strict) / (N * price),
           "randament_EV_optimizat": best / (N * price), "iteratii": a.iter, "seed": SEED,
           "secunde": round(time.time() - t0, 1),
           "nota": "EV individual al biletelor (fără partajarea între propriile bilete); modelul mulțimii QL",
           "positive_claims_allowed": False}
    OUT.mkdir(parents=True, exist_ok=True)
    rf = OUT / f"PERMUTARE_{name}.json"
    assert not rf.exists()
    rf.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    os.chmod(rf, 0o444)
    print(json.dumps({k: rep[k] for k in ("design_permutat", "n_tickets", "cost_lei", "EV_identitate_lei",
                                          "EV_optimizat_lei", "castig_fata_de_identitate_lei",
                                          "randament_EV_optimizat", "secunde")}, ensure_ascii=False))
    print(rf, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
