#!/usr/bin/env python3
"""XI-C1 §3 + AMENDAMENT_XI_C1_03 — design 6/49 (≥ 3 nimeriri la fiecare extragere): greedy GPU + reducere țintită.

Etapa G: construcție greedy (R = 8 porniri: 4 extrageri neacoperite + 4 bilete aleatoare; urcare locală ≤ 15 pași pe
vecinii cu un număr schimbat, câștig exact |A3(t) ∩ Z0|). Etapa R: elimină biletul cu acoperirea unică minimă, apoi
recoacere (ca v4: 0.7 mutări țintite, baie termică cu „rămâi”, T0 = 2, ×0.9995, min 0.05, reîncălzire la 4 000).
Contorul exact c[D] este ținut în 8 planuri de biți (incrementare/decrementare bit-sliced), Z0/Z1 direct din planuri.
Controale: f_nou = f + Δ la fiecare mutare; recalculare completă la 2 000 de mutări și la fiecare design; martor M3.

Utilizare: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B xi/c1/cautare649.py --minute-g 15 --minute 125
           [--reia design.json]   (reluare unică după eroare tehnică, aceiași parametri)
positive_claims_allowed=false. Calcul clasic. Nu importă quantum_limit.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cautare as CA  # noqa: E402  (Universe, popcount; nemodificat)
import designuri as DS  # noqa: E402

dev = CA.dev
popcount = CA.popcount
NPL = 8
LOGS = HERE.parent / "rezultate" / "C1" / "cautare"


class S649:
    def __init__(self, U: "CA.Universe", tickets: list[list[int]]):
        self.U = U
        self.nums = torch.zeros((0, 6), dtype=torch.long, device=dev)
        self.P = torch.zeros((NPL, U.W), dtype=torch.int64, device=dev)
        if tickets:
            self.nums = torch.tensor([sorted(t) for t in tickets], dtype=torch.long, device=dev) - 1
        self.P = self.recount()
        self.refresh()

    # --- acoperire și contor pe planuri ---
    def cover(self, nums: torch.Tensor) -> torch.Tensor:
        return self.U.cover(nums, torch.zeros(len(nums), dtype=torch.long, device=dev))[:, 0]   # (B, W)

    @staticmethod
    def _inc(P: torch.Tensor, m: torch.Tensor):
        carry = m
        for k in range(NPL):
            nc = P[k] & carry
            P[k] ^= carry
            carry = nc
        assert not bool(carry.any()), "depășire contor"

    @staticmethod
    def _dec(P: torch.Tensor, m: torch.Tensor):
        b = m
        for k in range(NPL):
            nb = (~P[k]) & b
            P[k] ^= b
            b = nb
        assert not bool(b.any()), "contor negativ"

    def recount(self) -> torch.Tensor:
        P = torch.zeros((NPL, self.U.W), dtype=torch.int64, device=dev)
        for a in range(0, len(self.nums), 32):
            cov = self.cover(self.nums[a:a + 32])
            for row in cov:
                self._inc(P, row)
        return P

    def refresh(self):
        hi = self.P[1]
        for k in range(2, NPL):
            hi = hi | self.P[k]
        self.Z0 = ~(self.P[0] | hi) & self.U.valid
        self.Z1 = self.P[0] & ~hi
        self.f = int(popcount(self.Z0))

    def check(self):
        assert torch.equal(self.recount(), self.P), "contor diferit la recalculare"

    def add(self, t: torch.Tensor):
        self._inc(self.P, self.cover(t.view(1, -1))[0])
        self.nums = torch.cat([self.nums, t.view(1, -1)])
        self.refresh()

    def remove(self, i: int):
        self._dec(self.P, self.cover(self.nums[i:i + 1])[0])
        keep = torch.ones(len(self.nums), dtype=torch.bool, device=dev)
        keep[i] = False
        self.nums = self.nums[keep]
        self.refresh()

    def apply(self, i: int, new: torch.Tensor):
        self._dec(self.P, self.cover(self.nums[i:i + 1])[0])
        self._inc(self.P, self.cover(new.view(1, -1))[0])
        self.nums[i] = new
        self.refresh()

    def tickets(self) -> list[list[int]]:
        return [sorted(x) for x in (self.nums + 1).tolist()]

    # --- vecinii unui bilet: poziția p înlocuită cu un număr din afară (ordinea p-major) ---
    def neighbors(self, cur: torch.Tensor):
        inside = torch.zeros(49, dtype=torch.bool, device=dev)
        inside[cur] = True
        outside = torch.nonzero(~inside).flatten()
        pos = torch.arange(6, device=dev).repeat_interleave(len(outside))
        new = cur.repeat(len(pos), 1)
        new[torch.arange(len(pos), device=dev), pos] = outside.repeat(6)
        return new, outside

    def _a3_per_pos(self, cur: torch.Tensor, outside: torch.Tensor):
        Ix = self.U.I[outside]
        for p in range(6):
            rest = torch.cat([cur[:p], cur[p + 1:]])
            c0 = torch.zeros(self.U.W, dtype=torch.int64, device=dev)
            c1, c2 = c0.clone(), c0.clone()
            for v in self.U.I[rest]:
                carry = c0 & v
                c0 = c0 ^ v
                carry2 = c1 & carry
                c1 = c1 ^ carry
                c2 = c2 | carry2
            yield (c2 | (c1 & c0)) | ((c2 | c1) & Ix)                      # A3 pentru cei 43 de vecini

    def gains(self, cur: torch.Tensor):
        """Câștigul exact |A3 ∩ Z0| pentru toți cei 258 de vecini (etapa G)."""
        new, outside = self.neighbors(cur)
        g = torch.cat([popcount(a3 & self.Z0) for a3 in self._a3_per_pos(cur, outside)])
        return new, g

    def deltas(self, i: int, allowed: torch.Tensor | None = None):
        """Δf exact pentru vecinii biletului i (etapa R): Δ = |Z1 ∩ O \\ A3'| − |Z0 ∩ A3'|.

        Cu `allowed` (mască booleană pe cei 258 de vecini, mutarea țintită), Δ se calculează numai pentru vecinii
        permiși; ceilalți primesc +inf, exact ca filtrul din v4 (aceeași distribuție de alegere, calcul mai puțin)."""
        cur = self.nums[i]
        new, outside = self.neighbors(cur)
        Z1O = self.Z1 & self.cover(cur.view(1, -1))[0]
        if allowed is None:
            d = torch.cat([popcount(Z1O & ~a3) - popcount(self.Z0 & a3) for a3 in self._a3_per_pos(cur, outside)])
            return new, d.double()
        d = torch.full((len(new),), float("inf"), dtype=torch.float64, device=dev)
        K = len(outside)
        am = allowed.view(6, K)
        for p in torch.nonzero(am.any(1)).flatten().tolist():
            sel = torch.nonzero(am[p]).flatten()
            rest = torch.cat([cur[:p], cur[p + 1:]])
            c0 = torch.zeros(self.U.W, dtype=torch.int64, device=dev)
            c1, c2 = c0.clone(), c0.clone()
            for v in self.U.I[rest]:
                carry = c0 & v
                c0 = c0 ^ v
                carry2 = c1 & carry
                c1 = c1 ^ carry
                c2 = c2 | carry2
            a3 = (c2 | (c1 & c0)) | ((c2 | c1) & self.U.I[outside[sel]])
            d[p * K + sel] = (popcount(Z1O & ~a3) - popcount(self.Z0 & a3)).double()
        return new, d

    def unique_cover(self) -> torch.Tensor:
        out = torch.empty(len(self.nums), dtype=torch.long, device=dev)
        for a in range(0, len(self.nums), 32):
            out[a:a + 32] = popcount(self.Z1 & self.cover(self.nums[a:a + 32]))
        return out

    def sample_uncovered(self, rng) -> torch.Tensor:
        nz = torch.nonzero(self.Z0).flatten()
        w = int(nz[int(rng.integers(len(nz)))])
        word = int(self.Z0[w]) & ((1 << 64) - 1)
        bits = [b for b in range(64) if word >> b & 1]
        idx = 64 * w + bits[int(rng.integers(len(bits)))]
        return torch.tensor(self.U.D[idx].astype(np.int64), device=dev)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minute-g", type=float, default=15.0)
    ap.add_argument("--minute", type=float, default=125.0)
    ap.add_argument("--seed", type=int, default=20261030)
    ap.add_argument("--reia", type=Path)
    a = ap.parse_args()
    assert sys.flags.dont_write_bytecode, "rulați cu -B"
    t0 = time.time()
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    U = CA.Universe("649")
    LOGS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    log = (LOGS / f"CAUTARE649_v5_{stamp}.jsonl").open("a")
    S = None

    def rec(**kw):
        kw.update(t=round(time.time() - t0, 1), utc=time.strftime("%H:%M:%SZ", time.gmtime()))
        if S is not None:
            kw.update(N=len(S.nums), f=S.f)
        log.write(json.dumps(kw) + "\n")
        log.flush()
        print(json.dumps(kw), flush=True)

    # martor M3 (AMENDAMENT_XI_C1_01): un singur bilet {1..6}
    m3 = S649(U, [[1, 2, 3, 4, 5, 6]])
    assert m3.f == 13723192, m3.f
    del m3
    rec(ev="start", seed=a.seed, W=U.W, martor_M3=13723192, reia=str(a.reia) if a.reia else None,
        amendament="XI_C1_03")

    def write(prefix: str):
        S.check()
        N = len(S.nums)
        tl = S.tickets()
        assert len({tuple(t) for t in tl}) == N, "bilete duplicate"
        f = DS.write_design("649", f"{prefix}{N}", tl, {"constructie": f"XI-C1 AMENDAMENT_XI_C1_03 etapa {prefix[1]}",
                                                          "seed": a.seed, "iteratii": it, "secunde": round(time.time() - t0)})
        rec(ev="design", name=f"{prefix}{N}", file=str(f))
        return f

    it = 0
    first_r = True
    if a.reia:
        S = S649(U, json.loads(a.reia.read_text())["tickets"])
        first_r = True                      # designul reluat este deja scris; nu se rescrie la același N
        rec(ev="reluare", file=str(a.reia))
    else:
        # ---------------- etapa G ----------------
        S = S649(U, [])
        while S.f > 0:
            if time.time() - t0 > a.minute_g * 60:
                rec(ev="G_buget_epuizat")
                return 1
            starts = [S.sample_uncovered(rng) for _ in range(4)]
            starts += [torch.tensor(np.sort(rng.choice(49, 6, replace=False)), device=dev) for _ in range(4)]
            best, bg = None, -1
            for t in starts:
                g = int(popcount(S.cover(t.view(1, -1))[0] & S.Z0))
                for _ in range(15):
                    new, gs = S.gains(t)
                    k = int(torch.argmax(gs))
                    if int(gs[k]) > g:
                        t, g = new[k], int(gs[k])
                    else:
                        break
                if g > bg:
                    best, bg = t.clone(), g
            fb = S.f
            S.add(best)
            assert S.f == fb - bg, (S.f, fb, bg)
            if len(S.nums) % 10 == 0:
                rec(ev="G_progres", gain=bg)
        write("SG")
    # ---------------- etapa R ----------------
    T, stuck, best_f = 2.0, 0, S.f
    last_print = time.time()
    while time.time() - t0 < a.minute * 60:
        if S.f == 0:
            if not first_r:
                write("SR")
            first_r = False
            uc = S.unique_cover()
            k = int(torch.argmin(uc))
            S.remove(k)
            rec(ev="eliminare", unic=int(uc[k]))
            T, stuck, best_f = 2.0, 0, S.f
            continue
        tgt = S.sample_uncovered(rng) if rng.random() < 0.7 else None
        if tgt is not None:
            ov = torch.isin(S.nums, tgt).sum(1)
            idx = torch.nonzero(ov >= 2).flatten()
            i = int(idx[int(rng.integers(len(idx)))]) if len(idx) else int(rng.integers(len(S.nums)))
        else:
            i = int(rng.integers(len(S.nums)))
        okm = None
        if tgt is not None:
            new0, _ = S.neighbors(S.nums[i])
            okm = torch.isin(new0, tgt).sum(1) >= 3
            if not bool(okm.any()):
                okm = None
        new, d = S.deltas(i, okm)
        if it < 300 and okm is not None:  # control de echivalență la început: subsetul = filtrul complet v4
            _, dfull = S.deltas(i)
            dref = torch.where(okm, dfull, torch.full_like(dfull, float("inf")))
            assert torch.equal(dref, d), "Δ pe subset diferit de Δ complet filtrat"
        dz = torch.cat([d, torch.zeros(1, dtype=d.dtype, device=dev)])
        w = torch.softmax(-dz / max(T, 1e-3), 0)
        k = int(torch.multinomial(w, 1))
        it += 1
        T = max(0.05, T * 0.9995)
        if k < len(d):
            fb = S.f
            S.apply(i, new[k])
            assert S.f == fb + int(d[k]), (S.f, fb, int(d[k]))
        if it % 2000 == 0:
            S.check()
        if S.f < best_f:
            best_f, stuck = S.f, 0
        else:
            stuck += 1
        if stuck >= 4000:
            T, stuck, best_f = 2.0, 0, S.f
            rec(ev="reincalzire", it=it)
        if time.time() - last_print > 30:
            rec(ev="progres", it=it, T=round(T, 3))
            last_print = time.time()
    rec(ev="stop", it=it)
    return 0


if __name__ == "__main__":
    sys.exit(main())
