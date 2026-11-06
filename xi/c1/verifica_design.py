#!/usr/bin/env python3
"""XI-C1 §4 — verificatorul exhaustiv SEPARAT al designurilor (CPU, numpy; independent de codul de căutare).

Utilizare:
  verifica_design.py <design.json> [...]     verifică fiecare design pe tot spațiul și scrie raportul JSON (0444)
  verifica_design.py --martori               martorii negativi obligatorii (J180−1, J140−1 ⇒ > 0 necâștigătoare)
G2 PASS ⇔ 0 extrageri necâștigătoare. positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np

XI = Path(__file__).resolve().parents[1]
OUT = XI / "rezultate" / "C1" / "verificari"
SPACE = {"joker": (45, 5), "649": (49, 6)}
JCAT = {(5, 1): "I", (5, 0): "II", (4, 1): "III", (4, 0): "IV", (3, 1): "V", (3, 0): "VI", (2, 1): "VII", (1, 1): "VIII"}
JRANK = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}


def draw_masks(n: int, k: int) -> np.ndarray:
    """Toate k-submulțimile lui 1..n ca măști int64 (bitul x-1 pentru numărul x), construite independent."""
    total = comb(n, k)
    out = np.empty(total, dtype=np.int64)
    i = 0
    buf = []
    for c in combinations(range(n), k):
        m = 0
        for x in c:
            m |= 1 << x
        buf.append(m)
        if len(buf) == 1 << 20:
            out[i:i + len(buf)] = buf
            i += len(buf)
            buf = []
    out[i:i + len(buf)] = buf
    assert i + len(buf) == total
    return out


def mask(nums) -> int:
    m = 0
    for x in nums:
        m |= 1 << (int(x) - 1)
    return m


def check_format(game: str, tickets) -> list[str]:
    n, k = SPACE[game]
    errs = []
    for t in tickets:
        nums = t[:5] if game == "joker" else t
        if len(nums) != (5 if game == "joker" else 6) or len(set(nums)) != len(nums) \
                or not all(1 <= x <= n for x in nums):
            errs.append(f"bilet invalid {t}")
        if game == "joker" and (len(t) != 6 or not 1 <= t[5] <= 20):
            errs.append(f"Joker invalid {t}")
    keys = [tuple(t) for t in tickets]
    if len(set(keys)) != len(keys):
        errs.append("bilete duplicate")
    return errs


def verify_joker(tickets, D: np.ndarray) -> dict:
    nD = len(D)
    best_m = np.zeros((nD, 20), dtype=np.int8)   # max nimeriri pe biletele cu Joker J
    best_u = np.zeros(nD, dtype=np.int8)         # max nimeriri pe orice bilet
    for t in tickets:
        h = np.bitwise_count(D & mask(t[:5])).astype(np.int8)
        j = t[5] - 1
        np.maximum(best_m[:, j], h, out=best_m[:, j])
        np.maximum(best_u, h, out=best_u)
    # cea mai bună categorie pe (D, J): rang 1..8; 9 = fără premiu
    rank = np.full((nD, 20), 9, dtype=np.int8)
    for (h, matched), name in JCAT.items():
        r = JRANK[name]
        if matched:
            cond = best_m == h
        else:
            cond = np.broadcast_to((best_u == h)[:, None], rank.shape)
        np.minimum(rank, np.where(cond, r, 9).astype(np.int8), out=rank)
    cnt = np.bincount(rank.ravel(), minlength=10)
    dist = {name: int(cnt[JRANK[name]]) for name in JRANK}
    return {"space": nD * 20, "losing": int(cnt[9]), "best_category_distribution": dist}


def verify_649(tickets, D: np.ndarray) -> dict:
    best = np.zeros(len(D), dtype=np.int8)
    for t in tickets:
        np.maximum(best, np.bitwise_count(D & mask(t)).astype(np.int8), out=best)
    cnt = np.bincount(best, minlength=7)
    return {"space": len(D), "losing": int(cnt[:3].sum()),
            "best_hits_distribution": {str(h): int(cnt[h]) for h in range(7)}}


_DCACHE: dict = {}


def verify(game: str, tickets) -> dict:
    if game not in _DCACHE:
        _DCACHE[game] = draw_masks(*SPACE[game])
    D = _DCACHE[game]
    t0 = time.time()
    errs = check_format(game, tickets)
    res = verify_joker(tickets, D) if game == "joker" else verify_649(tickets, D)
    res.update(format_errors=errs, n_tickets=len(tickets), seconds=round(time.time() - t0, 1),
               G2_PASS=bool(res["losing"] == 0 and not errs))
    return res


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_report(name: str, doc: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    f = OUT / f"VERIFICARE_{name}_{stamp}.json"
    while f.exists():
        time.sleep(1)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        f = OUT / f"VERIFICARE_{name}_{stamp}.json"
    doc = {**doc, "utc": stamp, "verifier_sha256": sha(Path(__file__)), "protocol": "XI-C1 §4",
           "positive_claims_allowed": False}
    f.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    os.chmod(f, 0o444)
    return f


def main(argv) -> int:
    if argv == ["--martori"]:  # AMENDAMENT_XI_C1_01: valori exacte calculate analitic înainte de rulare
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import designuri as DS
        B = DS.blocks()
        j140, j180 = DS.j140(), DS.j180()
        b3j1, b4j1, b1j1 = B[2] + [1], B[3] + [1], B[0] + [1]
        assert b3j1 in j140 and b4j1 in j140 and b1j1 in j180
        # M5: numărare directă pe blocuri (fără măști): 5-submulțimi ale B1..B4 cu cel mult 2 pe bloc
        pool = [x for b in B[:4] for x in b]
        m5 = sum(1 for c in combinations(pool, 5) if max(sum(1 for x in c if x in b) for b in B[:4]) <= 2)
        cases = (("M1_J140_fara_B3J1", "joker", [t for t in j140 if t != b3j1], 1500),
                 ("M2_J180_fara_Joker1", "joker", [t for t in j180 if t[5] != 1], 1149750),
                 ("M3_649_un_bilet", "649", [[1, 2, 3, 4, 5, 6]], 13723192),
                 ("M4_J180_fara_B1J1", "joker", [t for t in j180 if t != b1j1], 0),
                 ("M5_J140_fara_B3J1_B4J1", "joker", [t for t in j140 if t not in (b3j1, b4j1)], m5))
        rows = {}
        for name, game, t, exp in cases:
            r = verify(game, t)
            rows[name] = {"losing": r["losing"], "asteptat": exp, "n": r["n_tickets"], "martor_ok": r["losing"] == exp}
            print(name, rows[name], flush=True)
        ok = all(v["martor_ok"] for v in rows.values())
        f = write_report("MARTORI", {"martori": rows, "MARTORI_PASS": ok})
        print("MARTORI_PASS", ok, f, sha(f))
        return 0 if ok else 1
    rc = 0
    for a in argv:
        p = Path(a)
        d = json.loads(p.read_text())
        r = verify(d["game"], d["tickets"])
        f = write_report(d["name"], {"design": str(p), "design_sha256": sha(p), "game": d["game"],
                                     "name": d["name"], **r})
        print(d["name"], json.dumps({k: r[k] for k in ("n_tickets", "losing", "G2_PASS", "seconds")}), f, sha(f),
              flush=True)
        rc |= 0 if r["G2_PASS"] else 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
