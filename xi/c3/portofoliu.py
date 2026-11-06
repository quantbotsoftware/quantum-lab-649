#!/usr/bin/env python3
"""XI-C3 — optimizatorul de portofoliu sub buget (planul V11, faza E).

Protocol: xi/PROTOCOL_XI_C3.md (sigilat înainte de acest cod; sha în SIGILIU_XI_C3.json).
Funcțiile produsului `quantum_limit` sunt folosite neschimbate, numai pentru citire. Fără predicție de numere.
positive_claims_allowed=false. Calcul clasic (CPU + GPU/CuPy); „SQA” = recoacere cuantică SIMULATĂ (integrala de drum).
Rulare (mereu cu -B și PYTHONDONTWRITEBYTECODE=1):

  /usr/bin/python3 -B xi/c3/portofoliu.py teste          # T1–T6 (înainte de calibrare/G4/producție)
  /usr/bin/python3 -B xi/c3/portofoliu.py calibrare      # grila de parametri (instanțe separate)
  /usr/bin/python3 -B xi/c3/portofoliu.py g4             # poarta G4 (după sigilarea codului)
  /usr/bin/python3 -B xi/c3/portofoliu.py productie      # cele 81 de instanțe (unică, reluabilă)
  /usr/bin/python3 -B xi/c3/portofoliu.py raport         # C3_REZULTATE.json + RAPORT_C3_CIFRE.md
  /usr/bin/python3 -B xi/c3/portofoliu.py optimizeaza --joc 649 --buget 100 --mu 1000   # utilizare
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from decimal import Decimal, getcontext  # noqa: E402
from fractions import Fraction as Fr  # noqa: E402
from math import comb  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import cupy as cp  # noqa: E402

XI = Path(__file__).resolve().parents[1]
QL649 = XI.parent
REPO = XI.parents[2]
sys.path.insert(0, str(REPO / "next_candidate"))
from quantum_limit import data as D  # noqa: E402
from quantum_limit import ceiling as C  # noqa: E402
from quantum_limit import combinatorics as cb  # noqa: E402
from quantum_limit.crowd import CrowdModel, GameShape, fit, expected_share  # noqa: E402
from quantum_limit.joker import JokerCrowdModel, estimate_pi  # noqa: E402

OUT = XI / "rezultate" / "C3"
SCR = Path(os.environ["C3_SCRATCH"]) if os.environ.get("C3_SCRATCH") else OUT
DB = Path("./loto_romania/data/snapshots/"
          "c6bfd021af15d9d6ece6b20d106550e4c8474049e38e9caa3bd1c99d19766adb/loto_romania.sqlite")
DB_SHA = "9942abfc25282a715cba70e4f6d17a885a467eaf5fe0440838dc28114003c078"
PROTOCOL_SHA = "7cfa9680d5dbb1fb99f24aa086b9af18c69a7436b8128474be676c717e0399e0"
GAMES = ("649", "540", "joker")
CODE = {"649": 1, "540": 2, "joker": 3}
PRICE = {"649": 8.0, "540": 5.0, "joker": 7.0}
BUDGETS = (40, 100, 500)
MU_P = (0.0, 100.0, 1000.0, 1e4, 1e5, 1e8)
MU_S = (0.0, 1000.0, 1e8)
M_POOL = 4096
L_CAND = 32
SEED = 20261031
N_RND = 64
DESIGN_DIR = XI / "rezultate" / "C1" / "designuri"
DESIGNS = {"649": ("SG324Q.json", "b830503075cb52209497352a40bbd21b4680efcd41a2e27a8454e8aa4f4f86c5"),
           "joker": ("JS135Q.json", "add35bb780f3983a73623010b6f22d353cb731d521621ac8c13c73cd8feb96fd")}
SEAL_DIR = REPO / "next_candidate" / "quantum_limit" / "prospectiv"
SEALS = {"649": "649/2026-11-01/sigiliu_20261029T214019Z.json",
         "540": "540/2026-11-01/sigiliu_20261029T214041Z.json",
         "joker": "joker/2026-11-01/sigiliu_20261029T214102Z.json"}
C2_DIR = XI / "rezultate" / "C2"
C2_ROWS = {"649": ("etapa1_649.jsonl", "d7cd663948cd18d1bec72332a019b360f5cea52ae9b34e8a84532d63e681b4d8"),
           "540": ("etapa1_540.jsonl", "209a90eaca7650ebdad47de0c8427204c6edcaa6cf5b4cc8d03f1e39df2f5318"),
           "joker": ("etapa1_joker.jsonl", "72162919ca61a4d63fb9ba14dbfe77265a5a62d0286f25b649da49ab93d9b8d7")}
REF = {"649": "III", "540": "III", "joker": "VIII"}
YIELD_UTC = ((6, 20), (10, 20), (13, 20), (21, 40))

# Grila de calibrare (protocol §5) și parametrii aleși (completați după calibrare, înainte de sigilarea codului).
GRID_SQA = [dict(P=P, ratio=r) for P in (16, 32) for r in (0.5, 1.0)]
GRID_SA = [dict(T0=a, T1=b) for a in (1.0, 3.0) for b in (1e-2, 1e-3)]
GRID_PT = [dict(Tmax=a) for a in (1.0, 3.0)]
PARAMS = dict(SQA=dict(P=32, ratio=0.5), SA=dict(T0=1.0, T1=1e-3), PT=dict(Tmax=3.0))
# ↑ regula §5 aplicată pe calibrare/CALIBRARE_C3_20261031T143411Z.json (sha 689280df…): toate configurațiile 12/12
#   optime pe instanțele mici; departajare după media energiei normalizate pe instanțele de producție.


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def preflight():
    assert sys.flags.dont_write_bytecode or sys.dont_write_bytecode, "rulați cu -B"
    assert os.environ.get("PYTHONDONTWRITEBYTECODE") == "1", "PYTHONDONTWRITEBYTECODE=1 lipsește"
    assert sha_file(XI / "PROTOCOL_XI_C3.md") == PROTOCOL_SHA, "protocolul C3 s-a schimbat"
    assert D.sha256(DB) == DB_SHA, "baza nu este instantaneul fixat"
    for g, (name, sha) in DESIGNS.items():
        assert sha_file(DESIGN_DIR / name) == sha, f"designul {name} s-a schimbat"
    for g, (name, sha) in C2_ROWS.items():
        assert sha_file(C2_DIR / name) == sha, f"{name} s-a schimbat"
    OUT.mkdir(parents=True, exist_ok=True)
    SCR.mkdir(parents=True, exist_ok=True)


def guard(log=print):
    """Pauză internă în jurul emisiilor/prospectivului produsului și al C1 de duminică (protocol §9)."""
    while True:
        now = datetime.now(timezone.utc)
        minute = now.hour * 60 + now.minute
        near = False
        for h, m in YIELD_UTC:
            d = (minute - (h * 60 + m)) % 1440
            if d <= 15 or d >= 1440 - 18:
                near = True
        if now.date().isoformat() == "2026-11-01" and 13 * 60 <= minute < 14 * 60:
            near = True
        if not near:
            return
        log(f"pauză (fereastră protejată) {now.isoformat(timespec='seconds')}")
        time.sleep(60)


# ====================================================================== G(m, λ) exact
_GL_X, _GL_W = np.polynomial.legendre.leggauss(64)
GL_U = (_GL_X + 1.0) / 2.0
GL_W = _GL_W / 2.0


def G(m, lam, xp=cp):
    """G(m, λ) = E[m/(m+W)], W ~ Poisson(λ); G(0, ·) = 0 (protocol §3)."""
    m = xp.asarray(m)
    lam = xp.asarray(lam, dtype=xp.float64)
    m, lam = xp.broadcast_arrays(m, lam)
    out = xp.zeros(lam.shape, dtype=xp.float64)
    sel = m > 0
    if not bool(sel.any()):
        return out
    mm = m[sel].astype(xp.float64)
    ll = lam[sel]
    safe = xp.where(ll > 0, ll, 1.0)
    I = xp.where(ll > 1e-12, -xp.expm1(-ll) / xp.where(ll > 1e-12, ll, 1.0), 1.0 - ll / 2.0)
    res = xp.where(mm == 1, I, 0.0)
    mmax = int(mm.max())
    with np.errstate(all="ignore"):
        for k in range(1, mmax):
            I = (1.0 - k * I) / safe
            res = xp.where(mm == k + 1, (k + 1) * I, res)
    quad = (ll < mm) & (mm >= 2)
    if bool(quad.any()):
        qi = xp.nonzero(quad)[0]
        u = xp.asarray(GL_U)[None, :]
        w = xp.asarray(GL_W)[None, :]
        for s0 in range(0, int(qi.shape[0]), 1 << 20):       # bucăți de 2^20 (memorie)
            q = qi[s0:s0 + (1 << 20)]
            mq = mm[q][:, None]
            lq = ll[q][:, None]
            res[q] = (w * xp.exp((mq - 1.0) * xp.log1p(-u) - lq * u)).sum(axis=1) * mq[:, 0]
    out[sel] = res
    return out


def g1(lam, xp=np):
    return G(xp.ones_like(xp.asarray(lam, dtype=xp.float64)), lam, xp=xp)


def delta(lam, xp=cp):
    """δ(λ) = 2g(λ) − G(2, λ): pierderea exactă când două bilete proprii împart o categorie."""
    lam = xp.asarray(lam, dtype=xp.float64)
    return 2.0 * G(xp.ones(lam.shape, dtype=xp.int64), lam, xp=xp) - G(xp.full(lam.shape, 2, dtype=xp.int64), lam, xp=xp)


def g_inverse(gbar):
    """λ cu g(λ) = ḡ (ḡ în (0, 1]); bisecție în log λ, vectorizată (numpy)."""
    gbar = np.clip(np.asarray(gbar, dtype=np.float64), 1e-300, 1.0)
    lo = np.full(gbar.shape, -40.0)
    hi = np.full(gbar.shape, 40.0)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        val = g1(np.exp(mid))
        big = val > gbar            # g descrescătoare ⇒ λ prea mic
        lo = np.where(big, mid, lo)
        hi = np.where(big, hi, mid)
    lam = np.exp(0.5 * (lo + hi))
    return np.where(gbar >= 1.0 - 1e-15, 0.0, lam)


# ====================================================================== specificația jocului
class Spec:
    """Forma și categoriile unui joc (real sau mic, pentru teste)."""

    def __init__(self, game, shape, jokers=0):
        cfg = D.GAMES[game]
        self.game = game
        self.n, self.m, self.r = shape.n, shape.m, shape.r
        self.shape = shape
        self.structure = "joker" if cfg.get("structure") == "joker" else ("540" if game == "540" else "same")
        self.J = jokers if self.structure == "joker" else 0
        self.cats = list(cfg["categories"])
        self.hits = dict(cfg["categories"])
        self.matched = dict(cfg.get("matched", {}))
        self.fixed = tuple(cfg["fixed"])
        n, m, r = self.n, self.m, self.r
        self.Pc = {}
        if self.structure == "same":
            for c, k in self.hits.items():
                self.Pc[c] = comb(m, k) * comb(n - m, m - k) / comb(n, m)
        elif self.structure == "joker":
            J = self.J
            for c, h in self.hits.items():
                hy = comb(m, h) * comb(n - m, m - h) / comb(n, m)
                self.Pc[c] = hy * ((1.0 / J) if self.matched[c] else ((J - 1.0) / J))
        else:
            nd = comb(n, r)
            self.Pc["I"] = (n - m) / (r * nd)
            self.Pc["II"] = (n - m) * m / (r * nd)
            self.Pc["III"] = comb(r, m - 1) * comb(n - r, 1) / comb(n, m)
        self.p_any = float(sum(self.Pc.values()))

    def cat_same(self, h):
        for c, k in self.hits.items():
            if k == h:
                return c
        return None

    def cat_joker(self, h, matched):
        for c in self.cats:
            if self.hits[c] == h and self.matched[c] == matched:
                return c
        return None


def masks_of(sets):
    sets = np.asarray(sets, dtype=np.int64)
    return (np.left_shift(np.uint64(1), sets.astype(np.uint64))).sum(axis=1, dtype=np.uint64) if sets.size else \
        np.zeros(0, dtype=np.uint64)


def popc(x):
    return cp.bitwise_count(x).astype(cp.int16)


# ====================================================================== tabelele de perechi (numărare exactă)
def pair_tables(spec):
    """Numărări exacte (întregi) ale stărilor în care ambele bilete câștigă ceva / sunt în aceeași categorie.

    Cheie: t = |s ∩ s'| (6/49, 5/40) sau (t, e) cu e = [Joker egal] (Joker). Întoarce (tab, total_stări)."""
    n, m, r = spec.n, spec.m, spec.r
    tab = {}
    if spec.structure in ("same", "joker"):
        total = comb(n, m) * (spec.J if spec.structure == "joker" else 1)
        for t in range(max(0, 2 * m - n), m + 1):
            byh = {}
            for a in range(t + 1):
                for b in range(m - t + 1):
                    for c in range(m - t + 1):
                        o = m - a - b - c
                        if o < 0 or o > n - 2 * m + t:
                            continue
                        cnt = comb(t, a) * comb(m - t, b) * comb(m - t, c) * comb(n - 2 * m + t, o)
                        byh[(a + b, a + c)] = byh.get((a + b, a + c), 0) + cnt
            if spec.structure == "same":
                if t == m:
                    continue
                anyc, per = 0, {c: 0 for c in spec.cats}
                for (h1, h2), cnt in byh.items():
                    c1, c2 = spec.cat_same(h1), spec.cat_same(h2)
                    if c1 is not None and c2 is not None:
                        anyc += cnt
                        if c1 == c2:
                            per[c1] += cnt
                tab[t] = (anyc, per)
            else:
                J = spec.J
                for e in (0, 1):
                    if e == 1 and t == m:
                        continue
                    combos = [(True, True, 1), (False, False, J - 1)] if e else \
                        [(True, False, 1), (False, True, 1), (False, False, J - 2)]
                    anyc, per = 0, {c: 0 for c in spec.cats}
                    for (h1, h2), cnt in byh.items():
                        for m1, m2, wj in combos:
                            c1, c2 = spec.cat_joker(h1, m1), spec.cat_joker(h2, m2)
                            if c1 is not None and c2 is not None:
                                anyc += cnt * wj
                                if c1 == c2:
                                    per[c1] += cnt * wj
                    tab[(t, e)] = (anyc, per)
        return tab, total
    # 5/40: bilet m, extragere r = m + 1 în ordine (poziția bilei a șasea)
    total = comb(n, r) * r
    for t in range(max(0, 2 * m - n), m):
        anyc, per = 0, {c: 0 for c in spec.cats}
        for a in range(t + 1):
            for b in range(m - t + 1):
                for c in range(m - t + 1):
                    o = r - a - b - c
                    if o < 0 or o > n - 2 * m + t:
                        continue
                    cnt = comb(t, a) * comb(m - t, b) * comb(m - t, c) * comb(n - 2 * m + t, o)
                    h1, h2 = a + b, a + c
                    if h1 >= m - 1 and h2 >= m - 1:
                        anyc += cnt * r
                    if h1 == m - 1 and h2 == m - 1:
                        per["III"] += cnt * r
                    if h1 == m and h2 == m:
                        per["II"] += cnt * (m - 1)      # bila a șasea în s ∩ s' ⇒ ambele „cinci din șase”
        tab[t] = (anyc, per)
    return tab, total


def table_key(spec, t, e=None):
    return (t, e) if spec.structure == "joker" else t


# ====================================================================== contextul exact (stări pe GPU)
class Ctx:
    """Starea produsului + enumerarea stărilor pe GPU pentru evaluatorul exact (protocol §3)."""

    def __init__(self, spec, model, state, res):
        self.spec = spec
        self.state = state
        n, m, r = spec.n, spec.m, spec.r
        self.N = float(state["sales"])
        self.tickets = np.asarray(res["tickets"])
        self.count = len(self.tickets)
        self.tmask = masks_of(self.tickets)
        ev = np.asarray(res["ev"])
        self.J = spec.J
        if spec.structure == "joker":
            self.ev = ev.reshape(-1)
            self.comps = {k: np.asarray(v).reshape(-1) for k, v in res["components"].items()}
            self.pi = np.asarray(res["pi"], dtype=np.float64)
        else:
            self.ev = ev
            self.comps = {k: np.asarray(v) for k, v in res["components"].items()}
            self.pi = None
        self.shared = [c for c in spec.cats if c in state["funds"]]
        self.A = {c: float(state["funds"][c]["total"]) for c in self.shared}
        self.fixedv = {c: float(v) for c, v in state.get("fixed", {}).items()}
        self.Dm = cp.asarray(self.tmask)
        q = res["q"]
        if spec.structure == "same":
            self.lam = {c: cp.asarray(self.N * np.asarray(q[spec.hits[c]])) for c in self.shared}
        elif spec.structure == "joker":
            self.Qh = {h: cp.asarray(np.asarray(q[h])) for h in sorted(set(spec.hits[c] for c in self.shared))}
        else:
            table = cb.binomial_table(n)
            draws = cb.all_subsets(n, r)
            self.nd = len(draws)
            self.Dm = cp.asarray(masks_of(draws))
            row_of_rank = np.empty(self.count, dtype=np.int64)
            row_of_rank[cb.rank(self.tickets, table)] = np.arange(self.count)
            p = np.asarray(res["p"])
            pm = np.empty((self.nd, r))
            yb = np.empty((self.nd, r), dtype=np.uint64)
            for y in range(r):
                keep = [i for i in range(r) if i != y]
                pm[:, y] = p[row_of_rank[cb.rank(draws[:, keep], table)]]
                yb[:, y] = np.left_shift(np.uint64(1), draws[:, y].astype(np.uint64))
            self.pminus = cp.asarray(pm)
            self.ybit = cp.asarray(yb)
            self.q5 = cp.asarray(np.asarray(q[m]))
            self.q4 = cp.asarray(np.asarray(q[m - 1]))
        self.flagged = C.patterned(self.tickets)
        if self.J:
            self.flagged = np.repeat(self.flagged, self.J)
        self.table = cb.binomial_table(n)

    # ---------------------------------------------------------- bilete
    def flat_count(self):
        return self.count * (self.J or 1)

    def mask_joker(self, flat):
        flat = np.asarray(flat, dtype=np.int64)
        if self.J:
            return self.tmask[flat // self.J], (flat % self.J).astype(np.int64)
        return self.tmask[flat], np.full(len(flat), -1, dtype=np.int64)

    def numbers(self, flat):
        flat = int(flat)
        if self.J:
            return [int(x) + 1 for x in self.tickets[flat // self.J]] + [int(flat % self.J) + 1]
        return [int(x) + 1 for x in self.tickets[flat]]

    def flat_of(self, numbers_list):
        out = []
        row_of_rank = None
        for nums in numbers_list:
            if self.J:
                *nn, j = nums
            else:
                nn, j = nums, None
            rk = cb.rank(np.array([[x - 1 for x in sorted(nn)]]), self.table)[0]
            if row_of_rank is None:
                row_of_rank = np.empty(self.count, dtype=np.int64)
                row_of_rank[cb.rank(self.tickets, self.table)] = np.arange(self.count)
            row = int(row_of_rank[rk])
            out.append(row * self.J + (int(j) - 1) if self.J else row)
        return np.array(out, dtype=np.int64)

    # ---------------------------------------------------------- evaluatorul exact
    def evaluate(self, flat):
        """EV(S), P_any(S), P(≥1 în categoria c) — enumerare completă a stărilor (protocol §3)."""
        spec = self.spec
        masks, jok = self.mask_joker(flat)
        out_cat = {c: 0.0 for c in spec.cats}
        if spec.structure == "same":
            cnt = {c: cp.zeros(self.count, dtype=cp.int16) for c in spec.cats}
            anyw = cp.zeros(self.count, dtype=cp.bool_)
            for s in masks:
                h = popc(self.Dm & cp.uint64(int(s)))
                for c in spec.cats:
                    hit = h == spec.hits[c]
                    cnt[c] += hit
                    anyw |= hit
            ev = 0.0
            for c in self.shared:
                ev += self.A[c] * float(G(cnt[c], self.lam[c]).sum())
            for c, v in self.fixedv.items():
                ev += v * float(cnt[c].sum())
            ev /= self.count
            for c in spec.cats:
                out_cat[c] = float((cnt[c] > 0).sum()) / self.count
            p_any = float(anyw.sum()) / self.count
        elif spec.structure == "joker":
            ev, anyc = 0.0, 0
            catc = {c: 0 for c in spec.cats}
            hs = [popc(self.Dm & cp.uint64(int(s))) for s in masks]
            for js in range(self.J):
                cnt = {c: cp.zeros(self.count, dtype=cp.int16) for c in spec.cats}
                anyw = cp.zeros(self.count, dtype=cp.bool_)
                for h, j in zip(hs, jok):
                    mt = int(j) == js
                    for c in spec.cats:
                        if spec.matched[c] == mt:
                            hit = h == spec.hits[c]
                            cnt[c] += hit
                            anyw |= hit
                for c in self.shared:
                    f = self.pi[js] if spec.matched[c] else 1.0 - self.pi[js]
                    ev += self.A[c] * float(G(cnt[c], self.N * f * self.Qh[spec.hits[c]]).sum())
                for c in spec.cats:
                    catc[c] += int((cnt[c] > 0).sum())
                anyc += int(anyw.sum())
            tot = self.count * self.J
            ev /= tot
            p_any = anyc / tot
            out_cat = {c: catc[c] / tot for c in spec.cats}
        else:
            r, m = spec.r, spec.m
            hs = [popc(self.Dm & cp.uint64(int(s))) for s in masks]
            outs = [self.Dm & ~cp.uint64(int(s)) for s in masks]
            anyw = cp.zeros(self.nd, dtype=cp.bool_)
            for h in hs:
                anyw |= h >= m - 1
            ev = 0.0
            catc = {c: 0 for c in spec.cats}
            for y in range(r):
                cI = cp.zeros(self.nd, dtype=cp.int16)
                cII = cp.zeros(self.nd, dtype=cp.int16)
                cIII = cp.zeros(self.nd, dtype=cp.int16)
                for h, o in zip(hs, outs):
                    five = h == m
                    isI = five & (o == self.ybit[:, y])
                    cI += isI
                    cII += five & ~isI
                    cIII += h == m - 1
                lamI = self.N * self.pminus[:, y]
                lamII = self.N * cp.maximum(self.q5 - self.pminus[:, y], 0.0)
                lamIII = self.N * self.q4
                for c, cc, ll in (("I", cI, lamI), ("II", cII, lamII), ("III", cIII, lamIII)):
                    if c in self.shared:
                        ev += self.A[c] * float(G(cc, ll).sum())
                    catc[c] += int((cc > 0).sum())
            tot = self.nd * r
            ev /= tot
            p_any = float(anyw.sum()) / self.nd
            out_cat = {c: catc[c] / tot for c in spec.cats}
        return dict(ev=float(ev), p_any=float(p_any), p_cat=out_cat)

    # ---------------------------------------------------------- numărare directă (T4b)
    def pair_counts_direct(self, f1, f2):
        spec = self.spec
        (s1, s2), (j1, j2) = self.mask_joker([f1, f2])
        per = {c: 0 for c in spec.cats}
        anyc = 0
        if spec.structure == "same":
            h1 = popc(self.Dm & cp.uint64(int(s1)))
            h2 = popc(self.Dm & cp.uint64(int(s2)))
            w1 = cp.zeros(self.count, dtype=cp.bool_)
            w2 = cp.zeros(self.count, dtype=cp.bool_)
            for c in spec.cats:
                a, b = h1 == spec.hits[c], h2 == spec.hits[c]
                per[c] = int((a & b).sum())
                w1 |= a
                w2 |= b
            anyc = int((w1 & w2).sum())
        elif spec.structure == "joker":
            h1 = popc(self.Dm & cp.uint64(int(s1)))
            h2 = popc(self.Dm & cp.uint64(int(s2)))
            for js in range(self.J):
                w1 = cp.zeros(self.count, dtype=cp.bool_)
                w2 = cp.zeros(self.count, dtype=cp.bool_)
                for c in spec.cats:
                    a = (h1 == spec.hits[c]) & (spec.matched[c] == (int(j1) == js))
                    b = (h2 == spec.hits[c]) & (spec.matched[c] == (int(j2) == js))
                    per[c] += int((a & b).sum())
                    w1 |= a
                    w2 |= b
                anyc += int((w1 & w2).sum())
        else:
            m = spec.m
            h1 = popc(self.Dm & cp.uint64(int(s1)))
            h2 = popc(self.Dm & cp.uint64(int(s2)))
            o1 = self.Dm & ~cp.uint64(int(s1))
            o2 = self.Dm & ~cp.uint64(int(s2))
            anyc = int(((h1 >= m - 1) & (h2 >= m - 1)).sum()) * spec.r
            for y in range(spec.r):
                i1 = (h1 == m) & (o1 == self.ybit[:, y])
                i2 = (h2 == m) & (o2 == self.ybit[:, y])
                per["I"] += int((i1 & i2).sum())
                per["II"] += int(((h1 == m) & ~i1 & (h2 == m) & ~i2).sum())
                per["III"] += int(((h1 == m - 1) & (h2 == m - 1)).sum())
        return anyc, per


# ====================================================================== starea produsului (ca testul K2 al C2)
def fit_649(draws649):
    used, X, W, ks = D.observed_counts("649", draws649)
    weights = D.time_weights([d["date"] for d in used])
    weights /= weights.mean()
    model, info = fit(D.GAMES["649"]["shape"], X, W, ks, weights=weights, ridge=1.0)
    return model, dict(info, n_used=len(used), max_date=used[-1]["date"])


def derive(game, base649, draws):
    if game == "649":
        return base649
    shape = D.GAMES[game]["shape"]
    theta = np.concatenate([base649.beta[:shape.n], [base649.theta_c, base649.theta_L]])
    if game == "540":
        return CrowdModel(shape, theta)
    used, *_ = D.observed_counts("joker", draws)
    pi, _, _ = estimate_pi(used, D.GAMES["joker"]["jokers"])
    return JokerCrowdModel(shape, theta, pi=pi, jokers=D.GAMES["joker"]["jokers"])


_CACHE = {}


def product_states():
    if "states" not in _CACHE:
        allr = {g: D.load_draws(g, DB) for g in GAMES}
        base, info = fit_649(allr["649"])
        st = {}
        for g in GAMES:
            model = derive(g, base, allr[g])
            st[g] = (model, C.market_state(g, allr[g], model))
        _CACHE["states"] = st
        _CACHE["fit_info"] = info
    return _CACHE["states"]


def c2_rows(game):
    name, _ = C2_ROWS[game]
    rows = [json.loads(x) for x in (C2_DIR / name).read_text().splitlines() if x.strip()]
    return [x for x in rows if x.get("status") == "evaluat"]


def kappa_info(game, state):
    """κ (definiția C2) și κ_c^rec pentru varianta S (protocol §6)."""
    rows = c2_rows(game)
    jackpot = D.GAMES[game]["categories"] and next(iter(D.GAMES[game]["categories"]))
    ref = REF[game]
    ratio_all = np.array([x["state"]["sales"] / x["state"]["funds"][ref]["allocation"] for x in rows
                          if x["state"]["funds"][ref]["allocation"] > 0])
    now_ref = state["sales"] / state["funds"][ref]["allocation"]
    kappa = now_ref / float(np.median(ratio_all))
    quant = float((ratio_all / np.median(ratio_all) <= kappa).mean())
    rec = {}
    last = rows[-104:]
    for c, f in state["funds"].items():
        if c == jackpot or f["allocation"] <= 0:
            continue
        rr = np.array([x["state"]["sales"] / x["state"]["funds"][c]["allocation"] for x in last
                       if x["state"]["funds"].get(c, {}).get("allocation", 0) > 0])
        rec[c] = float((state["sales"] / f["allocation"]) / np.median(rr))
    diag = json.loads((C2_DIR / "DIAGNOSTIC_POSTHOC_C2.json").read_text())
    binfo = None
    for b in diag["jocuri"][game]["bins"]:
        if b["kappa"][0] <= kappa <= b["kappa"][1]:
            binfo = b
            break
    return dict(kappa=float(kappa), kappa_quantile_C2=quant, ref_category=ref, kappa_rec=rec, c2_bin=binfo,
                sales=float(state["sales"]))


def variant_state(game, state, variant):
    if variant == "P":
        return state, None
    k = kappa_info(game, state)
    st = dict(state)
    funds = {c: dict(v) for c, v in state["funds"].items()}
    for c, kr in k["kappa_rec"].items():
        funds[c]["allocation"] = funds[c]["allocation"] * kr
        funds[c]["total"] = funds[c]["carried"] + funds[c]["allocation"]
    st["funds"] = funds
    return st, k


# ====================================================================== pool, surogat, QUBO
class Instance:
    """Pool-ul (M bilete) + coeficienții QUBO pentru o variantă de fonduri (protocol §4)."""

    def __init__(self, ctx, design_numbers=None, M=M_POOL):
        self.ctx = ctx
        spec = ctx.spec
        ev = ctx.ev
        flat_n = ctx.flat_count()
        pool = []
        seen = set()
        if design_numbers:
            for f in ctx.flat_of(design_numbers):
                f = int(f)
                if not ctx.flagged[f] and f not in seen:
                    pool.append(f)
                    seen.add(f)
        self.n_design = len(pool)
        need = M - len(pool)
        masked = np.where(ctx.flagged, -np.inf, ev)
        k = min(flat_n - 1, need + len(pool) + 16)
        cand = np.argpartition(-masked, k)[:k + 1]
        cand = cand[np.lexsort((cand, -masked[cand]))]
        for f in cand:
            if len(pool) >= M:
                break
            f = int(f)
            if f not in seen and np.isfinite(masked[f]):
                pool.append(f)
                seen.add(f)
        self.flat = np.array(pool, dtype=np.int64)
        self.M = len(self.flat)
        self.a_np = ev[self.flat].astype(np.float64)
        self.a = cp.asarray(self.a_np)
        masks, jok = ctx.mask_joker(self.flat)
        self.masks = masks
        self.jok = jok
        # tabele
        tab, total = pair_tables(spec)
        self.tab, self.total = tab, total
        mg = cp.asarray(masks)
        T = popc(mg[:, None] & mg[None, :]).astype(cp.int64)
        if spec.structure == "joker":
            jg = cp.asarray(jok)
            E = (jg[:, None] == jg[None, :]).astype(cp.int64)
            keyidx = T * 2 + E
            nkeys = (spec.m + 1) * 2
            keyof = lambda kk: kk[0] * 2 + kk[1]  # noqa: E731
        else:
            keyidx = T
            nkeys = spec.m + 1
            keyof = lambda kk: kk  # noqa: E731
        pany = np.zeros(nkeys)
        pcat = {c: np.zeros(nkeys) for c in spec.cats}
        for kk, (anyc, per) in tab.items():
            pany[keyof(kk)] = anyc / total
            for c in spec.cats:
                pcat[c][keyof(kk)] = per[c] / total
        self.P2 = cp.asarray(pany)[keyidx]
        Dsum = cp.zeros((self.M, self.M), dtype=cp.float64)
        self.lam_eff = {}
        for c in ctx.shared:
            if ctx.A[c] <= 0 or not np.any(pcat[c] > 0):
                continue
            gbar = ctx.comps[c][self.flat] / (ctx.A[c] * spec.Pc[c])
            le = g_inverse(gbar)
            self.lam_eff[c] = le
            lg = cp.asarray(le)
            pc = cp.asarray(pcat[c])
            for r0 in range(0, self.M, 512):                    # pe rânduri (memorie)
                r1 = min(self.M, r0 + 512)
                Dsum[r0:r1] += ctx.A[c] * pc[keyidx[r0:r1]] * delta(0.5 * (lg[r0:r1, None] + lg[None, :]))
        idx = cp.arange(self.M)
        Dsum[idx, idx] = 0.0
        self.P2[idx, idx] = 0.0
        self.Dsum = Dsum
        rng = np.random.default_rng(12345)
        ii = rng.integers(0, self.M, 20000)
        jj = rng.integers(0, self.M, 20000)
        ok = ii != jj
        self.p2_median = float(np.median(cp.asnumpy(self.P2[cp.asarray(ii[ok]), cp.asarray(jj[ok])])))
        self.a_std = float(np.std(self.a_np))

    def problem(self, K, mu):
        return Problem(self.a, self.Dsum + mu * self.P2, K, self.a_std + mu * self.p2_median, mu)

    def F_surrogate(self, E, K, mu):
        return -float(E) + mu * K * self.ctx.spec.p_any


class Problem:
    def __init__(self, a, Q, K, sE, mu):
        self.a, self.Q, self.K, self.sE, self.mu = a, Q, int(K), float(sE), float(mu)
        self.M = int(a.shape[0])

    def energy(self, sel):
        sel = cp.asarray(sel)
        if sel.ndim == 1:
            sel = sel[None, :]
        lin = -self.a[sel].sum(axis=1)
        sub = self.Q[sel[:, :, None], sel[:, None, :]]
        return lin + 0.5 * sub.sum(axis=(1, 2))


# ====================================================================== optimizatoarele (protocol §5)
class Walkers:
    def __init__(self, prob, W, rng):
        self.prob = prob
        M, K = prob.M, prob.K
        self.W = W
        self.ar = cp.arange(W)
        keys = rng.random_sample((W, M))
        self.sel = cp.argsort(keys, axis=1)[:, :K].astype(cp.int64)
        self.mask = cp.zeros((W, M), dtype=cp.bool_)
        self.mask[self.ar[:, None], self.sel] = True
        self.h = cp.zeros((W, M), dtype=cp.float64)
        for k in range(K):
            self.h += prob.Q[self.sel[:, k]]
        self.E = -prob.a[self.sel].sum(axis=1) + 0.5 * self.h[self.ar[:, None], self.sel].sum(axis=1)
        self.bestE = self.E.copy()
        self.bestSel = self.sel.copy()

    def propose(self, w, rng):
        prob = self.prob
        nw = int(w.shape[0])
        pos = rng.randint(0, prob.K, size=nw)
        i = self.sel[w, pos]
        j = rng.randint(0, prob.M, size=nw)
        valid = ~self.mask[w, j]
        dE = prob.a[i] - prob.a[j] + self.h[w, j] - prob.Q[i, j] - self.h[w, i]
        return pos, i, j, valid, dE

    def apply(self, w, pos, i, j, dE, acc):
        k = cp.nonzero(acc)[0]
        if k.size == 0:
            return
        ww, ii, jj = w[k], i[k], j[k]
        self.mask[ww, ii] = False
        self.mask[ww, jj] = True
        self.sel[ww, pos[k]] = jj
        self.h[ww] += self.prob.Q[jj] - self.prob.Q[ii]
        self.E[ww] += dE[k]

    def track(self):
        better = self.E < self.bestE
        self.bestE = cp.where(better, self.E, self.bestE)
        self.bestSel = cp.where(better[:, None], self.sel, self.bestSel)

    def check(self):
        """T5: energia incrementală = energia recalculată (și pentru cele mai bune stări)."""
        tol = 1e-9 * max(1.0, self.prob.sE * self.prob.K)
        e1 = float(cp.abs(self.prob.energy(self.sel) - self.E).max())
        e2 = float(cp.abs(self.prob.energy(self.bestSel) - self.bestE).max())
        assert e1 <= tol and e2 <= tol, f"T5 FAIL: {e1} {e2} tol {tol}"
        return max(e1, e2)


def steps_for(K):
    return 20000 + 200 * K


def run_sa(prob, T0, T1, seed, steps=None, W=1024):
    steps = steps or steps_for(prob.K)
    rng = cp.random.RandomState(seed)
    st = Walkers(prob, W, rng)
    t0, t1 = T0 * prob.sE, T1 * prob.sE
    for t in range(steps):
        T = t0 * (t1 / t0) ** (t / max(1, steps - 1))
        pos, i, j, valid, dE = st.propose(st.ar, rng)
        acc = valid & (cp.log(rng.random_sample(W)) < -dE / T)
        st.apply(st.ar, pos, i, j, dE, acc)
        st.track()
    err = st.check()
    return st, err


def run_pt(prob, Tmax, seed, steps=None, chains=32, R=32):
    steps = steps or steps_for(prob.K)
    rng = cp.random.RandomState(seed)
    W = chains * R
    st = Walkers(prob, W, rng)
    Tl = cp.asarray(np.geomspace(1e-3 * prob.sE, Tmax * prob.sE, R))
    wot = cp.arange(W).reshape(chains, R)                 # walker care ține temperatura r în lanțul c
    Tw = cp.empty(W)
    Tw[wot] = cp.broadcast_to(Tl[None, :], wot.shape)
    nex = 0
    for t in range(steps):
        pos, i, j, valid, dE = st.propose(st.ar, rng)
        acc = valid & (cp.log(rng.random_sample(W)) < -dE / Tw)
        st.apply(st.ar, pos, i, j, dE, acc)
        st.track()
        if (t + 1) % 10 == 0:
            par = nex % 2
            nex += 1
            r = cp.arange(par, R - 1, 2)
            wa, wb = wot[:, r], wot[:, r + 1]
            logp = (1.0 / Tl[r] - 1.0 / Tl[r + 1])[None, :] * (st.E[wa] - st.E[wb])
            ok = cp.log(rng.random_sample(logp.shape)) < logp
            wot[:, r] = cp.where(ok, wb, wa)
            wot[:, r + 1] = cp.where(ok, wa, wb)
            Tw[wot] = cp.broadcast_to(Tl[None, :], wot.shape)
    err = st.check()
    return st, err


def run_sqa(prob, P, ratio, seed, steps=None, chains=32):
    """Integrala de drum (Suzuki–Trotter): P felii, J⊥ = −½ ln tanh(Γ/(P·T)), Γ liniar Γ₀ → Γ₁ (protocol §5)."""
    steps = steps or steps_for(prob.K)
    rng = cp.random.RandomState(seed)
    W = chains * P
    st = Walkers(prob, W, rng)
    PT = ratio * prob.sE                                   # P·T
    g0, g1_ = 2.0 * prob.sE, 1e-3 * prob.sE
    c = cp.arange(W) // P
    k = cp.arange(W) % P
    wp = c * P + (k + 1) % P
    wm = c * P + (k - 1) % P
    halves = [cp.nonzero(k % 2 == par)[0] for par in (0, 1)]
    for t in range(steps):
        gam = g0 + (g1_ - g0) * t / max(1, steps - 1)
        jp = -0.5 * math.log(math.tanh(gam / PT))
        for w in halves:
            pos, i, j, valid, dE = st.propose(w, rng)
            mk = st.mask
            si = (2.0 * mk[wm[w], i] - 1.0) + (2.0 * mk[wp[w], i] - 1.0)
            sj = (2.0 * mk[wm[w], j] - 1.0) + (2.0 * mk[wp[w], j] - 1.0)
            logacc = -dE / PT + jp * (-2.0 * si + 2.0 * sj)
            acc = valid & (cp.log(rng.random_sample(int(w.shape[0]))) < logacc)
            st.apply(w, pos, i, j, dE, acc)
        st.track()
    err = st.check()
    return st, err


def run_greedy(prob):
    gain = prob.a.copy()
    chosen = []
    taken = cp.zeros(prob.M, dtype=cp.bool_)
    for _ in range(prob.K):
        j = int(cp.argmax(cp.where(taken, -cp.inf, gain)))
        chosen.append(j)
        taken[j] = True
        gain -= prob.Q[j]
    sel = cp.asarray(np.array(chosen, dtype=np.int64))
    return sel, float(prob.energy(sel)[0])


def brute_force(prob, chunk=2_000_000):
    """Optimul exact al surogatului: enumerarea tuturor C(M, K) submulțimilor (protocol §5, G4)."""
    M, K = prob.M, prob.K
    total = comb(M, K)
    it = itertools.combinations(range(M), K)
    best, best_sel, done = np.inf, None, 0
    pairs = [(p, q) for p in range(K) for q in range(p + 1, K)]
    while done < total:
        n = min(chunk, total - done)
        arr = np.fromiter(itertools.chain.from_iterable(itertools.islice(it, n)), dtype=np.int64, count=n * K)
        c = cp.asarray(arr.reshape(n, K))
        E = -prob.a[c].sum(axis=1)
        for p, q in pairs:
            E += prob.Q[c[:, p], c[:, q]]
        k = int(cp.argmin(E))
        if float(E[k]) < best:
            best, best_sel = float(E[k]), cp.asnumpy(c[k])
        done += n
    return best, best_sel, total


# ====================================================================== o instanță completă
def solve(inst, K, mu, seed, params, log=print, with_exact=True):
    prob = inst.problem(K, mu)
    t0 = time.time()
    res = dict(K=K, mu=mu, seed=seed, sE=prob.sE, solvers={})
    states = []
    runs = [("SQA", lambda: run_sqa(prob, params["SQA"]["P"], params["SQA"]["ratio"], seed + 1)),
            ("SA", lambda: run_sa(prob, params["SA"]["T0"], params["SA"]["T1"], seed + 2)),
            ("PT", lambda: run_pt(prob, params["PT"]["Tmax"], seed + 3))]
    for name, fn in runs:
        ts = time.time()
        st, err = fn()
        bE = cp.asnumpy(st.bestE)
        bS = cp.asnumpy(st.bestSel)
        res["solvers"][name] = dict(best=float(bE.min()), seconds=round(time.time() - ts, 2), t5_err=err)
        for e, s in zip(bE, bS):
            states.append((float(e), tuple(sorted(int(x) for x in s)), name))
    gsel, gE = run_greedy(prob)
    res["solvers"]["greedy"] = dict(best=gE)
    states.append((gE, tuple(sorted(int(x) for x in cp.asnumpy(gsel))), "greedy"))
    top = np.argsort(-inst.a_np, kind="stable")[:K]
    cE = float(prob.energy(cp.asarray(top))[0])
    states.append((cE, tuple(sorted(int(x) for x in top)), "C_EV"))
    states.sort(key=lambda x: x[0])
    found = {}
    for e, s, name in states:
        found.setdefault(s, [e, set()])[1].add(name)
    uniq = []
    for e, s, name in states:
        if s not in [u[1] for u in uniq]:
            uniq.append((e, s))
        if len(uniq) >= L_CAND:
            break
    res["best_surrogate_E"] = states[0][0]
    res["best_surrogate_by"] = sorted(found[states[0][1]][1])
    res["seconds_solvers"] = round(time.time() - t0, 2)
    if not with_exact:
        res["best_sel"] = list(states[0][1])
        return res
    cands = []
    for e, s in uniq:
        flat = inst.flat[list(s)]
        ex = inst.ctx.evaluate(flat)
        F = ex["ev"] + mu * ex["p_any"]
        cands.append(dict(E=e, sel=list(s), F_exact=F, F_surrogate=inst.F_surrogate(e, K, mu), **ex))
    cands.sort(key=lambda x: (-x["F_exact"], x["E"]))
    ch = cands[0]
    res["chosen"] = dict(ch, tickets=[inst.ctx.numbers(f) for f in inst.flat[ch["sel"]]],
                         found_by=sorted(found[tuple(ch["sel"])][1]),
                         rho=ch["ev"] / (K * PRICE_OF(inst)), gap_F=ch["F_exact"] - ch["F_surrogate"])
    res["surrogate_best_exact_F"] = next(c["F_exact"] for c in cands if tuple(c["sel"]) == states[0][1])
    res["n_candidates"] = len(cands)
    res["seconds"] = round(time.time() - t0, 2)
    return res


def PRICE_OF(inst):
    return PRICE.get(inst.ctx.spec.game, 1.0)


# ====================================================================== pregătirea jocurilor reale
def design_numbers(game):
    if game not in DESIGNS:
        return None
    return json.loads((DESIGN_DIR / DESIGNS[game][0]).read_text())["tickets"]


def prepare(game, variant="P", log=print):
    key = (game, variant)
    if key in _CACHE:
        return _CACHE[key]
    states = product_states()
    model, state = states[game]
    st, kinfo = variant_state(game, state, variant)
    t0 = time.time()
    res = C.ev_all_tickets(model, st)
    spec = Spec(game, model.shape, jokers=len(model.pi) if game == "joker" else 0)
    ctx = Ctx(spec, model, st, res)
    inst = Instance(ctx, design_numbers(game))
    log(f"pregătit {game}/{variant}: pool {inst.M} (design {inst.n_design}), {round(time.time() - t0, 1)} s")
    _CACHE[key] = (ctx, inst, kinfo if kinfo else kappa_info(game, state))
    return _CACHE[key]


def release(game, variant):
    _CACHE.pop((game, variant), None)
    cp.get_default_memory_pool().free_all_blocks()


# ====================================================================== teste T1–T6
def naive_game(game, n, J=0, seed=1, N=40.0):
    """Joc mic + model aleator + stare sintetică; întoarce (spec, model, state, res_produs)."""
    rng = np.random.default_rng(seed)
    cfg = D.GAMES[game]
    if game == "649":
        shape = GameShape(n, 6, 6, 5)
    elif game == "540":
        shape = GameShape(n, 5, 6, 5)
    else:
        shape = GameShape(n, 5, 5, 5)
    theta = rng.normal(0, 0.6, n + 2)
    if game == "joker":
        pi = rng.dirichlet(np.ones(J) * 2.0)
        model = JokerCrowdModel(shape, theta, pi=pi, jokers=J)
    else:
        model = CrowdModel(shape, theta)
    funds = {}
    for idx, c in enumerate(cfg["categories"]):
        if c in cfg["fixed"]:
            continue
        tot = float(rng.uniform(50, 5000)) * (3.0 ** (len(cfg["categories"]) - idx))
        funds[c] = dict(carried=0.0, allocation=tot, total=tot)
    state = dict(game=game, sales=N, funds=funds, fixed={c: 30.0 for c in cfg["fixed"]}, next_draw="test",
                 last_draw="test")
    res = C.ev_all_tickets(model, state)
    spec = Spec(game, shape, jokers=J)
    return spec, model, state, res


def naive_poisson_G(m, lam):
    if m == 0:
        return 0.0
    term = math.exp(-lam)
    s, w = 0.0, 0
    while True:
        s += term * m / (m + w)
        w += 1
        term *= lam / w
        if w > lam + 50 and term < 1e-20:
            break
    return s


def naive_cat_matrix(spec, model, res):
    """Categoriile (cod sau −1) pentru fiecare bilet al mulțimii × fiecare stare, din definiții (Python pur)."""
    tickets = [frozenset(int(x) for x in t) for t in np.asarray(res["tickets"])]
    p = np.asarray(res["p"])
    cats = spec.cats
    if spec.structure == "same":
        states = [(t, None) for t in tickets]
        crowd = [(t, None, p[i]) for i, t in enumerate(tickets)]
    elif spec.structure == "joker":
        pi = np.asarray(res["pi"])
        states = [(t, js) for t in tickets for js in range(spec.J)]
        crowd = [(t, j, p[i] * pi[j]) for i, t in enumerate(tickets) for j in range(spec.J)]
    else:
        draws = [tuple(int(x) for x in d) for d in cb.all_subsets(spec.n, spec.r)]
        states = [(frozenset(d), d[y]) for d in draws for y in range(spec.r)]
        crowd = [(t, None, p[i]) for i, t in enumerate(tickets)]

    def cat(t, j, st):
        Dset, x = st
        h = len(t & Dset)
        if spec.structure == "same":
            return spec.cat_same(h)
        if spec.structure == "joker":
            return spec.cat_joker(h, j == x)
        if h == spec.m:
            return "I" if (Dset - t) == {x} else "II"
        return "III" if h == spec.m - 1 else None

    M = np.full((len(crowd), len(states)), -1, dtype=np.int8)
    for a, (t, j, _) in enumerate(crowd):
        for b, stt in enumerate(states):
            c = cat(t, j, stt)
            if c is not None:
                M[a, b] = cats.index(c)
    weights = np.array([w for _, _, w in crowd])
    return M, weights, states, crowd


def naive_eval(spec, state, catM, weights, portfolio):
    N = float(state["sales"])
    nst = catM.shape[1]
    ev, anyc = 0.0, 0
    lam = {}
    for ci, c in enumerate(spec.cats):
        lam[c] = N * (weights[:, None] * (catM == ci)).sum(axis=0)
    for b in range(nst):
        col = catM[portfolio, b]
        if (col >= 0).any():
            anyc += 1
        for ci, c in enumerate(spec.cats):
            mcount = int((col == ci).sum())
            if mcount == 0:
                continue
            if c in state["funds"]:
                ev += state["funds"][c]["total"] * naive_poisson_G(mcount, float(lam[c][b]))
            elif c in state.get("fixed", {}):
                ev += state["fixed"][c] * mcount
    return ev / nst, anyc / nst


def decimal_G(ms, lam, digits=50):
    getcontext().prec = digits
    L = Decimal(repr(float(lam)))
    out = {m: Decimal(0) for m in ms}
    if L == 0:
        return {m: Decimal(1) for m in ms}
    term = (-L).exp()
    w = 0
    lim = int(float(lam) + 40 * math.sqrt(float(lam)) + 200)
    while w <= lim:
        for m in ms:
            out[m] += term * m / (m + w)
        w += 1
        term = term * L / w
    return out


def cmd_teste(args):
    preflight()
    res = {"start_utc": utc(), "protocol_sha256": PROTOCOL_SHA}
    ok_all = True
    # ---------------- T2
    ms = list(range(1, 9)) + [16, 64]
    lams = [0.0, 1e-8, 1e-3, 0.1, 0.5, 1, 2, 5, 10, 50, 100, 1e3, 1e4, 1e5]
    worst = 0.0
    for lam in lams:
        ref = decimal_G(ms, lam)
        got = cp.asnumpy(G(cp.asarray(ms), cp.full(len(ms), float(lam))))
        for m, gv in zip(ms, got):
            rv = float(ref[m])
            worst = max(worst, abs(gv - rv) / rv)
    es = float(np.max(np.abs(cp.asnumpy(G(cp.ones(len(lams), dtype=cp.int64), cp.asarray(lams, dtype=cp.float64)))
                             - expected_share(np.array(lams))) / expected_share(np.array(lams))))
    res["T2"] = dict(worst_rel=worst, expected_share_rel=es, PASS=bool(worst <= 1e-12 and es <= 1e-14))
    print("T2", res["T2"], flush=True)
    # ---------------- T3
    t3 = {}
    for game, n, J in (("649", 10, 0), ("540", 9, 0), ("joker", 10, 3)):
        spec, model, state, pres = naive_game(game, n, J, seed=CODE[game])
        ctx = Ctx(spec, model, state, pres)
        flat_n = ctx.flat_count()
        # (a)
        wa = 0.0
        for f in range(flat_n):
            e = ctx.evaluate([f])["ev"]
            wa = max(wa, abs(e - ctx.ev[f]) / abs(ctx.ev[f]))
        # (b)
        catM, weights, states, crowd = naive_cat_matrix(spec, model, pres)
        rng = np.random.default_rng(100 + CODE[game])
        wb_ev, wb_p = 0.0, 0.0
        for _ in range(200):
            K = int(rng.integers(2, 7))
            pf = rng.choice(flat_n, K, replace=False)
            ne, npy = naive_eval(spec, state, catM, weights, pf)
            ex = ctx.evaluate(pf)
            wb_ev = max(wb_ev, abs(ex["ev"] - ne) / abs(ne))
            wb_p = max(wb_p, abs(ex["p_any"] - npy) / max(npy, 1e-300))
        # (c)
        tab, total = pair_tables(spec)
        assert total == catM.shape[1]
        ind = (catM >= 0).astype(np.int64)
        both_any = ind @ ind.T
        per = {c: ((catM == ci).astype(np.int64) @ (catM == ci).astype(np.int64).T) for ci, c in enumerate(spec.cats)}
        masks, jok = ctx.mask_joker(np.arange(flat_n))
        bad = 0
        npairs = 0
        for x in range(flat_n):
            for y in range(x + 1, flat_n):
                t = int(bin(int(masks[x]) & int(masks[y])).count("1"))
                e = int(jok[x] == jok[y]) if spec.J else None
                if spec.J and t == spec.m and e == 1:
                    continue
                kk = table_key(spec, t, e)
                anyc, pc = tab[kk]
                npairs += 1
                if anyc != both_any[x, y] or any(pc[c] != per[c][x, y] for c in spec.cats):
                    bad += 1
        t3[game] = dict(a_worst_rel=wa, b_worst_rel_ev=wb_ev, b_worst_rel_p=wb_p, c_pairs=npairs, c_mismatch=bad,
                        PASS=bool(wa <= 1e-10 and wb_ev <= 1e-10 and wb_p <= 1e-10 and bad == 0))
        print("T3", game, t3[game], flush=True)
    t3["PASS"] = all(v["PASS"] for v in t3.values())
    res["T3"] = t3
    # ---------------- T6
    rng = np.random.default_rng(6)
    a = rng.normal(0, 1, 10)
    Qn = rng.normal(0, 0.5, (10, 10))
    Qn = (Qn + Qn.T) / 2
    np.fill_diagonal(Qn, 0)
    prob = Problem(cp.asarray(a), cp.asarray(Qn), 3, 1.0, 0.0)
    bE, bS, tot = brute_force(prob, chunk=7)
    ref = min((-sum(a[list(s)]) + sum(Qn[p, q] for p, q in itertools.combinations(s, 2)), s)
              for s in itertools.combinations(range(10), 3))
    res["T6"] = dict(brute=bE, itertools=ref[0], sel=[int(x) for x in bS], ref_sel=list(ref[1]),
                     PASS=bool(abs(bE - ref[0]) <= 1e-12 and tuple(int(x) for x in bS) == ref[1] and tot == 120))
    print("T6", res["T6"], flush=True)
    # ---------------- T1 + T4 (jocuri reale)
    states = product_states()
    t1, t4 = {}, {}
    for g in GAMES:
        model, state = states[g]
        seal = json.loads((SEAL_DIR / SEALS[g]).read_text())
        assert seal["database_sha256"] == DB_SHA
        ctx, inst, kinfo = prepare(g, "P")
        flagged = ctx.flagged
        masked = np.where(flagged, -np.inf, ctx.ev)
        best = int(np.argmax(masked))
        lim = ctx.numbers(best)
        same = lim[:5 if g == "joker" else len(lim)] == seal["limit"]["numbers"] and \
            (g != "joker" or lim[-1] == seal["limit"]["joker"])
        rel_avg = abs(float(ctx.ev.mean()) - seal["average_ticket_ev"]) / seal["average_ticket_ev"]
        rel_lim = abs(float(ctx.ev[best]) - seal["limit"]["ev"]) / seal["limit"]["ev"]
        t1[g] = dict(rel_avg=rel_avg, rel_limit=rel_lim, same_ticket=bool(same), next_draw=state["next_draw"],
                     seal_target=seal["target_draw"],
                     PASS=bool(rel_avg <= 1e-9 and rel_lim <= 1e-9 and same and state["next_draw"] == seal["target_draw"]))
        print("T1", g, t1[g], flush=True)
        # T4a
        rng = np.random.default_rng(400 + CODE[g])
        picks = [best] + [int(x) for x in rng.integers(0, ctx.flat_count(), 50)]
        wa = 0.0
        for f in picks:
            e = ctx.evaluate([f])["ev"]
            wa = max(wa, abs(e - ctx.ev[f]) / abs(ctx.ev[f]))
        # T4b + T4c
        tab, total = inst.tab, inst.total
        bad, wp, errs = 0, 0.0, []
        for _ in range(200):
            x, y = (int(v) for v in rng.choice(inst.M, 2, replace=False))
            f1, f2 = int(inst.flat[x]), int(inst.flat[y])
            anyc, per = ctx.pair_counts_direct(f1, f2)
            t = int(bin(int(inst.masks[x]) & int(inst.masks[y])).count("1"))
            e = int(inst.jok[x] == inst.jok[y]) if ctx.J else None
            ta, tp = tab[table_key(ctx.spec, t, e)]
            if ta != anyc or any(tp[c] != per[c] for c in ctx.spec.cats):
                bad += 1
            e1, e2, e12 = ctx.evaluate([f1]), ctx.evaluate([f2]), ctx.evaluate([f1, f2])
            pid = abs(e12["p_any"] - (2 * ctx.spec.p_any - ta / total))
            wp = max(wp, pid)
            exact_loss = e1["ev"] + e2["ev"] - e12["ev"]
            errs.append(dict(t=t, e=e, surrogate=float(inst.Dsum[x, y]), exact=exact_loss))
        dif = np.array([z["surrogate"] - z["exact"] for z in errs])
        exl = np.array([z["exact"] for z in errs])
        t4[g] = dict(a_worst_rel=wa, b_mismatch=bad, b_pany_identity_abs=wp,
                     c_abs_err_max=float(np.abs(dif).max()), c_abs_err_mean=float(np.abs(dif).mean()),
                     c_exact_loss_max=float(exl.max()), c_exact_loss_mean=float(exl.mean()),
                     PASS=bool(wa <= 1e-9 and bad == 0 and wp <= 1e-12))
        print("T4", g, {k: v for k, v in t4[g].items()}, flush=True)
        t4[g]["c_pairs"] = errs[:40]
        t4[g]["kappa"] = kinfo
    t1["PASS"] = all(v["PASS"] for v in t1.values())
    t4["PASS"] = all(v["PASS"] for v in t4.values() if isinstance(v, dict) and "PASS" in v)
    res["T1"], res["T4"] = t1, t4
    # ---------------- T5 (scurt, pe o instanță reală mică; aserția rulează în fiecare rulare)
    ctx, inst, _ = prepare("649", "P")
    prob = inst.problem(5, 1000.0)
    _, e_sa = run_sa(prob, 1.0, 1e-3, 5, steps=300, W=64)
    _, e_pt = run_pt(prob, 1.0, 6, steps=300, chains=2, R=8)
    _, e_sq = run_sqa(prob, 8, 1.0, 7, steps=300, chains=4)
    res["T5"] = dict(sa=e_sa, pt=e_pt, sqa=e_sq, PASS=True)
    print("T5", res["T5"], flush=True)
    ok_all = all(res[k]["PASS"] for k in ("T1", "T2", "T3", "T4", "T5", "T6"))
    res["TESTE_PASS"] = bool(ok_all)
    res["end_utc"] = utc()
    res["script_sha256"] = sha_file(__file__)
    (SCR / "teste").mkdir(parents=True, exist_ok=True)
    path = SCR / "teste" / f"TESTE_C3_{stamp()}.json"
    path.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    print("TESTE_PASS", ok_all, path, flush=True)
    return 0 if ok_all else 1


# ====================================================================== sub-pooluri mici
def subproblem(inst, Ms, K, mu, seed):
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(inst.M, Ms, replace=False))
    ig = cp.asarray(idx)
    a = inst.a[ig]
    Q = (inst.Dsum + mu * inst.P2)[ig[:, None], ig[None, :]]
    iu, ju = np.triu_indices(Ms, 1)
    p2 = cp.asnumpy(inst.P2[ig[:, None], ig[None, :]])[iu, ju]
    sE = float(np.std(inst.a_np[idx])) + mu * float(np.median(p2))     # toate perechile sub-pool-ului
    return Problem(a, Q, K, sE, mu), idx


def solve_small(prob, params, seed, which=("SQA", "SA", "PT", "greedy")):
    out = {}
    if "SQA" in which:
        st, _ = run_sqa(prob, params["SQA"]["P"], params["SQA"]["ratio"], seed + 1)
        out["SQA"] = float(st.bestE.min())
    if "SA" in which:
        st, _ = run_sa(prob, params["SA"]["T0"], params["SA"]["T1"], seed + 2)
        out["SA"] = float(st.bestE.min())
    if "PT" in which:
        st, _ = run_pt(prob, params["PT"]["Tmax"], seed + 3)
        out["PT"] = float(st.bestE.min())
    if "greedy" in which:
        out["greedy"] = run_greedy(prob)[1]
    return out


# ====================================================================== calibrare
def cmd_calibrare(args):
    preflight()
    res = {"start_utc": utc(), "small": [], "prod": []}
    small_sizes = ((40, 5), (64, 5))
    mus = (50.0, 3000.0)
    idx = 0
    for g in GAMES:
        ctx, inst, _ = prepare(g, "P")
        for mu in mus:
            for Ms, K in small_sizes:
                guard()
                prob, _ = subproblem(inst, Ms, K, mu, 77000 + idx)
                Eopt, _, tot = brute_force(prob)
                row = dict(game=g, mu=mu, Ms=Ms, K=K, Eopt=Eopt, sE=prob.sE, runs={})
                for name, grid in (("SQA", GRID_SQA), ("SA", GRID_SA), ("PT", GRID_PT)):
                    for ci, cfg in enumerate(grid):
                        guard()
                        seed = 77000 + 100 * idx + ci * 7
                        if name == "SQA":
                            st, _ = run_sqa(prob, cfg["P"], cfg["ratio"], seed)
                        elif name == "SA":
                            st, _ = run_sa(prob, cfg["T0"], cfg["T1"], seed)
                        else:
                            st, _ = run_pt(prob, cfg["Tmax"], seed)
                        e = float(st.bestE.min())
                        row["runs"][f"{name}{ci}"] = dict(E=e, hit=bool(e <= Eopt + 1e-9 * max(1, abs(Eopt))))
                res["small"].append(row)
                print("calibrare mică", g, mu, Ms, K, {k: v["hit"] for k, v in row["runs"].items()}, flush=True)
                idx += 1
        for B in (100, 500):
            K = int(B // PRICE[g])
            for mu in mus:
                guard()
                prob = inst.problem(K, mu)
                row = dict(game=g, B=B, K=K, mu=mu, sE=prob.sE, runs={})
                for name, grid in (("SQA", GRID_SQA), ("SA", GRID_SA), ("PT", GRID_PT)):
                    for ci, cfg in enumerate(grid):
                        guard()
                        seed = 78000 + 100 * idx + ci * 7
                        ts = time.time()
                        if name == "SQA":
                            st, _ = run_sqa(prob, cfg["P"], cfg["ratio"], seed)
                        elif name == "SA":
                            st, _ = run_sa(prob, cfg["T0"], cfg["T1"], seed)
                        else:
                            st, _ = run_pt(prob, cfg["Tmax"], seed)
                        row["runs"][f"{name}{ci}"] = dict(E=float(st.bestE.min()), seconds=round(time.time() - ts, 1))
                bestb = min(v["E"] for v in row["runs"].values())
                for v in row["runs"].values():
                    v["norm"] = (v["E"] - bestb) / prob.sE
                res["prod"].append(row)
                print("calibrare producție", g, B, mu, {k: round(v["norm"], 4) for k, v in row["runs"].items()},
                      flush=True)
                idx += 1
        release(g, "P")
    choice = {}
    for name, grid in (("SQA", GRID_SQA), ("SA", GRID_SA), ("PT", GRID_PT)):
        scores = []
        for ci in range(len(grid)):
            hits = sum(r["runs"][f"{name}{ci}"]["hit"] for r in res["small"])
            norm = float(np.mean([r["runs"][f"{name}{ci}"]["norm"] for r in res["prod"]]))
            scores.append((-hits, norm, ci))
        scores.sort()
        ci = scores[0][2]
        choice[name] = dict(grid[ci], index=ci, hits=-scores[0][0], mean_norm=scores[0][1],
                            all=[dict(index=s[2], hits=-s[0], mean_norm=s[1]) for s in sorted(scores, key=lambda z: z[2])])
    res["choice"] = choice
    res["end_utc"] = utc()
    res["script_sha256"] = sha_file(__file__)
    (SCR / "calibrare").mkdir(parents=True, exist_ok=True)
    path = SCR / "calibrare" / f"CALIBRARE_C3_{stamp()}.json"
    path.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("CALIBRARE", json.dumps(choice), path, flush=True)
    return 0


# ====================================================================== G4
def need_params():
    assert PARAMS is not None, "PARAMS nefixați (calibrarea și sigilarea codului vin înainte)"
    return PARAMS


def cmd_g4(args):
    preflight()
    params = need_params()
    path = SCR / "G4.jsonl"
    done = {(r["game"], r["mu"], r["Ms"], r["K"]) for r in read_jsonl(path)}
    idx = 0
    for g in GAMES:
        ctx, inst, _ = prepare(g, "P")
        for mu in (0.0, 1000.0, 100000.0):
            for Ms, K in ((24, 4), (40, 5), (48, 6), (64, 5)):
                seed = SEED + idx
                idx += 1
                if (g, mu, Ms, K) in done:
                    continue
                guard()
                prob, sub = subproblem(inst, Ms, K, mu, seed)
                ts = time.time()
                Eopt, osel, tot = brute_force(prob)
                tb = time.time() - ts
                got = solve_small(prob, params, seed)
                tol = 1e-9 * max(1.0, abs(Eopt))
                hits = {k: bool(v <= Eopt + tol) for k, v in got.items()}
                row = dict(game=g, mu=mu, Ms=Ms, K=K, seed=seed, subsets=tot, Eopt=Eopt,
                           opt=[int(x) for x in osel], found=got, hits=hits, ensemble_hit=bool(any(hits.values())),
                           brute_seconds=round(tb, 1), seconds=round(time.time() - ts, 1), utc=utc())
                append_jsonl(path, row)
                print("G4", g, mu, Ms, K, hits, flush=True)
        release(g, "P")
    rows = read_jsonl(path)
    summ = dict(n=len(rows), ensemble_hits=sum(r["ensemble_hit"] for r in rows),
                per_solver={k: sum(r["hits"][k] for r in rows) for k in ("SQA", "SA", "PT", "greedy")})
    summ["G4_PASS"] = bool(summ["n"] == 36 and summ["ensemble_hits"] == 36)
    (SCR / "G4_REZUMAT.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    print("G4_REZUMAT", summ, flush=True)
    return 0


# ====================================================================== producția
def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def append_jsonl(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=float) + "\n")
        f.flush()
        os.fsync(f.fileno())


def comparators(inst, K, seed_rnd):
    ctx = inst.ctx
    out = {}
    top = np.argsort(-inst.a_np, kind="stable")[:K]
    out["C_EV"] = dict(ctx.evaluate(inst.flat[top]), tickets=[ctx.numbers(f) for f in inst.flat[top]])
    if inst.n_design:
        d = np.arange(inst.n_design)
        d = d[np.argsort(-inst.a_np[d], kind="stable")][:K]
        out["C_DES"] = dict(ctx.evaluate(inst.flat[d]))
    rng = np.random.default_rng(seed_rnd)
    allowed = np.nonzero(~ctx.flagged)[0]
    evs, ps = [], []
    for _ in range(N_RND):
        pf = rng.choice(allowed, K, replace=False)
        ex = ctx.evaluate(pf)
        evs.append(ex["ev"])
        ps.append(ex["p_any"])
    out["C_RND"] = dict(ev_mean=float(np.mean(evs)), ev_q=[float(x) for x in np.quantile(evs, [0.05, 0.5, 0.95])],
                        p_any_mean=float(np.mean(ps)), p_any_q=[float(x) for x in np.quantile(ps, [0.05, 0.5, 0.95])],
                        n=N_RND)
    out["union_bound_p_any"] = K * ctx.spec.p_any
    out["sum_ev_bound_topK"] = float(inst.a_np[top].sum())
    return out


def cmd_productie(args):
    preflight()
    params = need_params()
    path = SCR / "productie.jsonl"
    comp_path = SCR / "comparatori.jsonl"
    done = {(r["game"], r["variant"], r["B"], r["mu"]) for r in read_jsonl(path)}
    cdone = {(r["game"], r["variant"], r["B"]) for r in read_jsonl(comp_path)}
    games = [args.joc] if getattr(args, "joc", None) else list(GAMES)
    for g in games:
        for variant, mus in (("P", MU_P), ("S", MU_S)):
            todo = [(ib, B, im, mu) for ib, B in enumerate(BUDGETS) for im, mu in enumerate(mus)
                    if (g, variant, B, mu) not in done]
            ctodo = [B for B in BUDGETS if (g, variant, B) not in cdone]
            if not todo and not ctodo:
                continue
            guard()
            ctx, inst, kinfo = prepare(g, variant)
            for ib, B in enumerate(BUDGETS):
                K = int(B // PRICE[g])
                if B in ctodo:
                    guard()
                    cmp_ = comparators(inst, K, SEED + 7 + 100 * CODE[g] + ib + (50 if variant == "S" else 0))
                    append_jsonl(comp_path, dict(game=g, variant=variant, B=B, K=K, utc=utc(), **cmp_))
                    print("comparatori", g, variant, B, flush=True)
                for (jb, BB, im, mu) in todo:
                    if BB != B:
                        continue
                    guard()
                    seed = SEED + 1000 * CODE[g] + 100 * ib + im + (50 if variant == "S" else 0)
                    r = solve(inst, K, mu, seed, params)
                    rec = dict(game=g, variant=variant, B=B, utc=utc(), kappa=kinfo,
                               pool=dict(M=inst.M, n_design=inst.n_design))
                    rec.update(r)                          # r conține K și mu (AMENDAMENT_XI_C3_01)
                    append_jsonl(path, rec)
                    ch = r["chosen"]
                    print("producție", g, variant, B, mu, "EV", round(ch["ev"], 3), "rho", round(ch["rho"], 4),
                          "P_any", round(ch["p_any"], 5), "by", ch["found_by"], r["seconds"], "s", flush=True)
            release(g, variant)
    return 0


# ====================================================================== raport automat
def cmd_raport(args):
    preflight()
    rows = read_jsonl(SCR / "productie.jsonl")
    comps = {(r["game"], r["variant"], r["B"]): r for r in read_jsonl(SCR / "comparatori.jsonl")}
    g4 = json.loads((SCR / "G4_REZUMAT.json").read_text()) if (SCR / "G4_REZUMAT.json").exists() else None
    out = dict(protocol_sha256=PROTOCOL_SHA, script_sha256=sha_file(__file__), database_sha256=DB_SHA,
               n_instances=len(rows), G4=g4, params=PARAMS, positive_claims_allowed=False, instances=[])
    lines = ["# RAPORT C3 — cifre (generat automat)", "",
             f"Instanțe: {len(rows)} / 81. G4: {g4}. Parametri: {json.dumps(PARAMS)}.", ""]
    rho_flag = []
    for g in GAMES:
        k = next((r["kappa"] for r in rows if r["game"] == g), None)
        if k:
            lines.append(f"## {g} — κ = {k['kappa']:.3f} (cuantila C2 {k['kappa_quantile_C2']:.3f}); "
                         f"κ_rec = {json.dumps({c: round(v, 3) for c, v in k['kappa_rec'].items()})}")
        for variant in ("P", "S"):
            for B in BUDGETS:
                sub = sorted([r for r in rows if r["game"] == g and r["variant"] == variant and r["B"] == B],
                             key=lambda r: r["mu"])
                if not sub:
                    continue
                cm = comps.get((g, variant, B))
                lines += ["", f"### {g} · varianta {variant} · buget {B} lei (K = {sub[0]['K']})", "",
                          "| μ | EV exact (lei) | ρ | P_any | F exact − F surogat | găsit de | s |",
                          "|---:|---:|---:|---:|---:|---|---:|"]
                for r in sub:
                    ch = r["chosen"]
                    if ch["rho"] >= 1.0:
                        rho_flag.append((g, variant, B, r["mu"], ch["rho"]))
                    lines.append(f"| {r['mu']:g} | {ch['ev']:.4f} | {ch['rho']:.4f} | {ch['p_any']:.5f} | "
                                 f"{ch['gap_F']:.3e} | {','.join(ch['found_by'])} | {r['seconds']} |")
                    out["instances"].append(dict(game=g, variant=variant, B=B, K=r["K"], mu=r["mu"], ev=ch["ev"],
                                                 rho=ch["rho"], p_any=ch["p_any"], p_cat=ch["p_cat"],
                                                 tickets=ch["tickets"], found_by=ch["found_by"], gap_F=ch["gap_F"],
                                                 solvers=r["solvers"]))
                if cm:
                    cost = sub[0]["K"] * PRICE[g]
                    lines.append("")
                    lines.append(f"Comparatori: C_EV EV {cm['C_EV']['ev']:.4f} (ρ {cm['C_EV']['ev'] / cost:.4f}), "
                                 f"P_any {cm['C_EV']['p_any']:.5f}; "
                                 + (f"C_DES EV {cm['C_DES']['ev']:.4f}, P_any {cm['C_DES']['p_any']:.5f}; "
                                    if "C_DES" in cm else "")
                                 + f"C_RND EV medie {cm['C_RND']['ev_mean']:.4f} (ρ {cm['C_RND']['ev_mean'] / cost:.4f}), "
                                 f"P_any medie {cm['C_RND']['p_any_mean']:.5f}; marginea de reuniune "
                                 f"{cm['union_bound_p_any']:.5f}.")
    out["rho_ge_1"] = rho_flag
    lines += ["", f"ρ ≥ 1: {rho_flag if rho_flag else 'niciuna'}", "",
              "positive_claims_allowed=false. Calcul clasic; SQA = simulare pe GPU."]
    (SCR / "C3_REZULTATE.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
    (SCR / "RAPORT_C3_CIFRE.md").write_text("\n".join(lines) + "\n")
    print("RAPORT", len(rows), "rho>=1:", rho_flag, flush=True)
    return 0


# ====================================================================== utilizare
def cmd_optimizeaza(args):
    preflight()
    params = need_params()
    g = args.joc
    ctx, inst, kinfo = prepare(g, args.varianta)
    K = int(args.buget // PRICE[g])
    r = solve(inst, K, float(args.mu), int(args.seed), params)
    ch = r["chosen"]
    out = dict(game=g, variant=args.varianta, budget=args.buget, K=K, mu=args.mu, tickets=ch["tickets"],
               ev=ch["ev"], rho=ch["rho"], p_any=ch["p_any"], p_cat=ch["p_cat"], kappa=kinfo,
               boundaries=dict(predicts_numbers=False, probability_of_winning_changed=False,
                               positive_claims_allowed=False, quantum_hardware=False))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("teste")
    sub.add_parser("calibrare")
    sub.add_parser("g4")
    p = sub.add_parser("productie")
    p.add_argument("--joc", choices=GAMES)
    sub.add_parser("raport")
    o = sub.add_parser("optimizeaza")
    o.add_argument("--joc", choices=GAMES, required=True)
    o.add_argument("--buget", type=float, required=True)
    o.add_argument("--mu", type=float, default=0.0)
    o.add_argument("--varianta", choices=("P", "S"), default="P")
    o.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    return dict(teste=cmd_teste, calibrare=cmd_calibrare, g4=cmd_g4, productie=cmd_productie, raport=cmd_raport,
                optimizeaza=cmd_optimizeaza)[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
