#!/usr/bin/env python3
"""XI-C1 §3 — căutare locală pe GPU pentru designuri cu premiu garantat (explorare; verificarea e separată, §4).

Reprezentare: universul extragerilor este împachetat pe biți (int64). Pentru fiecare număr x există vectorul
indicator I[x] (bitul D = 1 dacă x ∈ D). Acoperirea unui bilet se calculează prin numărare bit-sliced:
  A3(s) = „cel puțin 3 nimeriri”, A1(s) = „cel puțin 1 nimerire”.
Planuri: 6/49 → 1 plan (acoperire = A3); Joker → 20 de planuri J (acoperire = A3 ∪ [J = j]·A1).
Contorul exact c[plan, D] = numărul de bilete care acoperă (plan, D); Z0 = (c = 0), Z1 = (c = 1).
Mutare: un bilet ales aleator este înlocuit de unul dintre vecinii lui (un număr schimbat; la Joker și Jokerul),
toți vecinii sunt evaluați exact în lot; alegerea este de tip baie termică (softmax(−Δ/T)).
La f = 0 (zero necâștigătoare) se scrie designul și se elimină biletul cu cea mai mică acoperire unică.

Utilizare: .venv/bin/python -B xi/c1/cautare.py {joker|649} --minute M [--start design.json] [--n0 N]
positive_claims_allowed=false. Calcul clasic.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import designuri as DS  # noqa: E402

XI = HERE.parent
LOGS = XI / "rezultate" / "C1" / "cautare"
dev = torch.device("cuda")
LUT = torch.tensor([bin(i).count("1") for i in range(256)], dtype=torch.int32, device=dev)
SHIFTS = torch.arange(64, dtype=torch.int64, device=dev)


M1, M2, M4, H01 = 0x5555555555555555, 0x3333333333333333, 0x0F0F0F0F0F0F0F0F, 0x0101010101010101


def popcount(x: torch.Tensor) -> torch.Tensor:
    """Numărul de biți pe ultima axă (SWAR pe int64, fără tabele intermediare)."""
    x = x - ((x >> 1) & M1)
    x = (x & M2) + ((x >> 2) & M2)
    x = (x + (x >> 4)) & M4
    return ((x * H01) >> 56 & 0xFF).sum(-1)


def bitslice_count(planes: torch.Tensor, bits: int = 5) -> list[torch.Tensor]:
    """Contor binar bit-sliced al numărului de planuri care au bitul setat: planes (P, W) → [C_0, …, C_{bits−1}]."""
    C = [torch.zeros(planes.shape[-1], dtype=torch.int64, device=dev) for _ in range(bits)]
    for v in planes:
        carry = v
        for k in range(bits):
            nc = C[k] & carry
            C[k] = C[k] ^ carry
            carry = nc
    return C


def pack(bits: torch.Tensor) -> torch.Tensor:
    """bool (..., 64·W) → int64 (..., W)."""
    sh = bits.shape[:-1] + (bits.shape[-1] // 64, 64)
    return (bits.view(sh).to(torch.int64) << SHIFTS).sum(-1)


def unpack(words: torch.Tensor) -> torch.Tensor:
    return ((words.unsqueeze(-1) >> SHIFTS) & 1).flatten(-2).to(torch.int8)


class Universe:
    def __init__(self, game: str):
        self.game = game
        self.n, self.k = (45, 5) if game == "joker" else (49, 6)
        self.tk = 5 if game == "joker" else 6
        self.P = 20 if game == "joker" else 1
        total = comb(self.n, self.k)
        W = (total + 63) // 64
        self.total, self.W = total, W
        D = np.fromiter((x for c in combinations(range(self.n), self.k) for x in c), dtype=np.int8,
                        count=total * self.k).reshape(total, self.k)
        ind = np.zeros((self.n, W * 64), dtype=bool)
        rows = np.arange(total)
        for col in range(self.k):
            ind[D[:, col], rows] = True
        self.D = D                                                              # (total, k) int8, pentru ținte
        packed = np.packbits(ind, axis=1, bitorder="little")
        self.I = torch.from_numpy(packed.view(np.int64).copy()).to(dev)          # (n, W)
        valid = np.zeros(W * 64, dtype=bool)
        valid[:total] = True
        self.valid = torch.from_numpy(np.packbits(valid, bitorder="little").view(np.int64).copy()).to(dev)

    def cover(self, nums: torch.Tensor, jok: torch.Tensor) -> torch.Tensor:
        """nums (B, tk) 0-based, jok (B,) 0-based → acoperirea (B, P, W)."""
        V = self.I[nums]                                                        # (B, tk, W)
        c0 = torch.zeros_like(V[:, 0])
        c1 = torch.zeros_like(c0)
        c2 = torch.zeros_like(c0)
        for i in range(self.tk):
            v = V[:, i]
            carry = c0 & v
            c0 = c0 ^ v
            carry2 = c1 & carry
            c1 = c1 ^ carry
            c2 = c2 | carry2
        a3 = (c2 | (c1 & c0)) & self.valid
        if self.P == 1:
            return a3.unsqueeze(1)
        a1 = (c0 | c1 | c2) & self.valid
        B = nums.shape[0]
        out = a3.unsqueeze(1).expand(B, self.P, self.W).clone()
        out[torch.arange(B, device=dev), jok] |= a1
        return out


class State:
    def __init__(self, U: Universe, tickets: list[list[int]]):
        self.U = U
        self.nums = torch.tensor([sorted(t[:U.tk]) for t in tickets], dtype=torch.long, device=dev) - 1
        self.jok = torch.tensor([t[U.tk] - 1 if U.game == "joker" else 0 for t in tickets], device=dev)
        self.c = torch.zeros((U.P, U.W * 64), dtype=torch.int8, device=dev)
        for a in range(0, len(tickets), 8):
            cov = U.cover(self.nums[a:a + 8], self.jok[a:a + 8])
            self.c += unpack(cov).sum(0, dtype=torch.int8)
        self.refresh()

    def refresh(self):
        U = self.U
        self.Z0 = pack(self.c == 0) & U.valid
        self.Z1 = pack(self.c == 1)
        self.f = int(popcount(self.Z0).sum())

    def tickets(self) -> list[list[int]]:
        n = (self.nums + 1).tolist()
        if self.U.game == "joker":
            return [sorted(a) + [int(j) + 1] for a, j in zip(n, self.jok.tolist())]
        return [sorted(a) for a in n]

    def neighbors(self, i: int):
        U = self.U
        cur = self.nums[i]
        inside = torch.zeros(U.n, dtype=torch.bool, device=dev)
        inside[cur] = True
        outside = torch.nonzero(~inside).flatten()
        pos = torch.arange(U.tk, device=dev).repeat_interleave(len(outside))
        new = cur.repeat(len(pos), 1)
        new[torch.arange(len(pos), device=dev), pos] = outside.repeat(U.tk)
        jok = self.jok[i].repeat(len(pos))
        if U.game == "joker":
            others = torch.tensor([j for j in range(20) if j != int(self.jok[i])], device=dev)
            new = torch.cat([new, cur.repeat(len(others), 1)])
            jok = torch.cat([jok, others])
        return new, jok

    def deltas(self, i: int, new: torch.Tensor, jok: torch.Tensor) -> torch.Tensor:
        """Δf exact pentru vecinii din `neighbors(i)`, în aceeași ordine (poziție × număr exterior, apoi Jokeri).

        Pentru poziția p, contorul bit-sliced al celor tk−1 numere rămase se calculează o dată; candidatul x dă
        a3 = ge3 | (ge2 & I[x]) și a1 = ge1 | I[x]. La Joker, sumele pe cele 20 de planuri se fac prin contoare
        bit-sliced ale planurilor Y = Z1 & O și X = Z0 & ~O (5 biți), plus corecția planului j."""
        U = self.U
        cur = self.nums[i]
        j0 = int(self.jok[i])
        O = U.cover(cur.view(1, -1), self.jok[i:i + 1])[0]                         # (P, W)
        inside = torch.zeros(U.n, dtype=torch.bool, device=dev)
        inside[cur] = True
        outside = torch.nonzero(~inside).flatten()
        Ix = U.I[outside]                                                          # (n−tk, W)
        if U.P > 1:
            Y, X = self.Z1 & O, self.Z0 & ~O
            CY, CX = bitslice_count(Y), bitslice_count(X)
        outs = []
        for p in range(U.tk):
            rest = torch.cat([cur[:p], cur[p + 1:]])
            c0 = torch.zeros(U.W, dtype=torch.int64, device=dev)
            c1, c2 = c0.clone(), c0.clone()
            for v in U.I[rest]:
                carry = c0 & v
                c0 = c0 ^ v
                carry2 = c1 & carry
                c1 = c1 ^ carry
                c2 = c2 | carry2
            ge3, ge2, ge1 = c2 | (c1 & c0), c2 | c1, c0 | c1 | c2
            a3 = ge3 | (ge2 & Ix)                                                  # (K, W)
            if U.P == 1:
                outs.append(popcount(self.Z1[0] & O[0] & ~a3) - popcount(self.Z0[0] & a3))
            else:
                a1 = ge1 | Ix
                lost = sum((1 << k) * popcount(CY[k] & ~a3) for k in range(len(CY))) - popcount(Y[j0] & ~a3 & a1)
                gain = sum((1 << k) * popcount(CX[k] & a3) for k in range(len(CX))) + popcount(X[j0] & a1 & ~a3)
                outs.append(lost - gain)
        if U.P > 1:  # schimbarea Jokerului: a3 = o3, a1 = o1, j variază
            o3 = O[(j0 + 1) % 20]                      # pe un plan J ≠ j0 acoperirea este exact A3
            o1 = O[j0] & ~o3                            # A1 \ A3 (suficient pentru formule)
            others = jok[len(jok) - 19:]
            base_l = sum((1 << k) * popcount(CY[k] & ~o3) for k in range(len(CY)))
            base_g = sum((1 << k) * popcount(CX[k] & o3) for k in range(len(CX)))
            lost = base_l - popcount(Y[others] & ~o3 & o1)
            gain = base_g + popcount(X[others] & o1 & ~o3)
            outs.append(lost - gain)
        return torch.cat(outs).long()

    def apply(self, i: int, nums: torch.Tensor, jok):
        O = self.U.cover(self.nums[i:i + 1], self.jok[i:i + 1])[0]
        N = self.U.cover(nums.view(1, -1), torch.as_tensor([int(jok)], device=dev))[0]
        self.c += unpack(N) - unpack(O)
        self.nums[i] = nums
        self.jok[i] = int(jok)
        self.refresh()

    def sample_uncovered(self, rng):
        """O extragere necâștigătoare aleatoare: (plan J, numerele ei 0-based)."""
        counts = popcount(self.Z0).double()
        p = int(torch.multinomial(counts, 1))
        nz = torch.nonzero(self.Z0[p]).flatten()
        w = int(nz[int(rng.integers(len(nz)))])
        word = int(self.Z0[p, w]) & ((1 << 64) - 1)
        bits = [b for b in range(64) if word >> b & 1]
        idx = 64 * w + bits[int(rng.integers(len(bits)))]
        return p, torch.tensor(self.U.D[idx].astype(np.int64), device=dev)

    def pick_ticket(self, tgt, rng) -> int:
        p, dn = tgt
        ov = torch.isin(self.nums, dn).sum(1)
        ok = (ov >= 2) if self.U.P == 1 else ((self.jok == p) | (ov >= 1))
        idx = torch.nonzero(ok).flatten()
        if len(idx) == 0:
            return int(rng.integers(len(self.nums)))
        return int(idx[int(rng.integers(len(idx)))])

    def covers_target(self, new, jok, tgt) -> torch.Tensor:
        p, dn = tgt
        h = torch.isin(new, dn).sum(1)
        return (h >= 3) if self.U.P == 1 else ((h >= 3) | ((jok == p) & (h >= 1)))

    def unique_cover(self) -> torch.Tensor:
        out = torch.empty(len(self.nums), dtype=torch.long, device=dev)
        for a in range(0, len(self.nums), 64):
            cov = self.U.cover(self.nums[a:a + 64], self.jok[a:a + 64])
            out[a:a + 64] = popcount(self.Z1 & cov).sum(-1)
        return out

    def remove(self, i: int):
        O = self.U.cover(self.nums[i:i + 1], self.jok[i:i + 1])[0]
        self.c -= unpack(O)
        keep = torch.ones(len(self.nums), dtype=torch.bool, device=dev)
        keep[i] = False
        self.nums, self.jok = self.nums[keep], self.jok[keep]
        self.refresh()


def random_tickets(U: Universe, N: int, rng: np.random.Generator):
    seen, out = set(), []
    while len(out) < N:
        t = tuple(sorted((rng.choice(U.n, U.tk, replace=False) + 1).tolist()))
        j = int(rng.integers(1, 21)) if U.game == "joker" else None
        key = t + ((j,) if j else ())
        if key not in seen:
            seen.add(key)
            out.append(list(key))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game", choices=["joker", "649"])
    ap.add_argument("--minute", type=float, required=True)
    ap.add_argument("--start", type=Path)
    ap.add_argument("--n0", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261030)
    ap.add_argument("--T0", type=float, default=2.0)
    ap.add_argument("--eticheta", default="")
    ap.add_argument("--tinta", type=float, default=0.7)
    a = ap.parse_args()
    t0 = time.time()
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    U = Universe(a.game)
    if a.start:
        tickets = json.loads(a.start.read_text())["tickets"]
    else:
        tickets = random_tickets(U, a.n0, rng)
    S = State(U, tickets)
    LOGS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    logf = LOGS / f"CAUTARE_{a.game}{a.eticheta}_{stamp}.jsonl"
    log = logf.open("a")

    def rec(**kw):
        kw.update(t=round(time.time() - t0, 1), N=len(S.nums), f=S.f)
        log.write(json.dumps(kw) + "\n")
        log.flush()
        print(json.dumps(kw), flush=True)

    rec(ev="start", game=a.game, seed=a.seed, start=str(a.start) if a.start else "aleator", W=U.W)
    best = {}
    T = a.T0
    it = 0
    last_print = time.time()
    stuck = 0
    best_f = S.f
    while time.time() - t0 < a.minute * 60:
        if S.f == 0:
            tl = [tuple(x) for x in S.tickets()]
            if len(set(tl)) < len(tl):  # duplicat: acoperire unică 0, se elimină fără să schimbe f
                seen = set()
                dup = next(i for i, x in enumerate(tl) if x in seen or seen.add(x))
                S.remove(dup)
                rec(ev="duplicat_eliminat")
                continue
            N = len(S.nums)
            name = f"{'JS' if a.game == 'joker' else 'SS'}{N}{a.eticheta}"
            f = DS.write_design(a.game, name, S.tickets(), {"constructie": "XI-C1 §3 cautare GPU", "seed": a.seed,
                                                          "start": str(a.start) if a.start else "aleator",
                                                          "iteratii": it})
            best[N] = str(f)
            rec(ev="design", name=name, file=str(f))
            uc = S.unique_cover()
            S.remove(int(torch.argmin(uc)))
            rec(ev="eliminare", unic=int(uc.min()))
            T = a.T0
            stuck = 0
            best_f = S.f
            continue
        tgt = S.sample_uncovered(rng) if rng.random() < a.tinta else None   # v3: mutări țintite
        i = S.pick_ticket(tgt, rng) if tgt else int(rng.integers(len(S.nums)))
        new, jok = S.neighbors(i)
        d = S.deltas(i, new, jok).double()
        if tgt:
            okm = S.covers_target(new, jok, tgt)
            if bool(okm.any()):
                d = torch.where(okm, d, torch.full_like(d, float("inf")))
        # v4: opțiunea „rămâi pe loc” (Δ = 0) în baia termică
        dz = torch.cat([d, torch.zeros(1, dtype=d.dtype, device=dev)])
        w = torch.softmax(-dz / max(T, 1e-3), 0)
        k = int(torch.multinomial(w, 1))
        it += 1
        T = max(0.05, T * 0.9995)
        if k == len(d):
            stuck += 1
            if stuck >= 4000:
                T, stuck, best_f = a.T0, 0, S.f
                rec(ev="reincalzire", it=it)
            continue
        fb = S.f
        S.apply(i, new[k], jok[k])
        assert S.f == fb + int(d[k]), (S.f, fb, int(d[k]))
        if S.f < best_f:
            best_f, stuck = S.f, 0
        else:
            stuck += 1
        if stuck >= 4000:  # reîncălzire
            T, stuck, best_f = a.T0, 0, S.f
            rec(ev="reincalzire", it=it)
        if time.time() - last_print > 30:
            rec(ev="progres", it=it, T=round(T, 3))
            last_print = time.time()
    rec(ev="stop", it=it, best=best)
    return 0


if __name__ == "__main__":
    sys.exit(main())
