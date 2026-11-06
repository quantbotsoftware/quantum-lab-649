"""TU3 — modulul E40: motorul QL649 parametrizat în forma jocului (n, r, k). Protocol: PROTOCOL_TU3_E40.md
(sigilat în SIGILIU_TU3_E40.json ÎNAINTE de acest cod).

Produsul E40 = Loto 5/40: n = 40 numere în urnă, r = 6 numere la extragere, variante de EXACT k = 5 numere.
`SHAPE_649 = (49, 6, 6)` există numai ca martor de echivalență bit cu bit cu `engine.py` (E1).

Funcțiile generice în N din `engine.py` se IMPORTĂ nemodificate (RNG pe contor, O1 non-hermitic, disipare, Kuramoto,
`crowd_penalty`, `Config`); cele dependente de `N = 49` / `K6 = 6` sunt rescrise aici parametrizat, cu aceeași ordine a
operațiilor. `engine.py`, `parser.py` și `parser_multi.py` NU se modifică.

Calcul CLASIC (PyTorch, CUDA implicit; fallback CPU jurnalizat). Variantele sunt minime de energie, NU predicții;
motorul nu aduce informație nouă despre extragerea următoare. `positive_claims_allowed=false`.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, replace
from itertools import combinations
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
for _p in (str(QL), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import engine as QE  # noqa: E402  (engine.py al QL649, nemodificat)
import parser_multi as PM  # noqa: E402
from engine import (C128, F64, FORBID_PENALTY, PROTOCOL, TAG_BOLTZ, TAG_INIT, TAG_MCMC, TAG_SWAP, Config,  # noqa: E402,F401
                    _vram, crowd_penalty, dissipation, op_kuramoto, op_nonhermitian, poincare_dist, sha256_file,
                    splitmix, step_seed, stream, uniform)

PROTOCOL_FILE = HERE / "PROTOCOL_TU3_E40.md"
SEAL_FILE = HERE / "SIGILIU_TU3_E40.json"
POWER_FILE = HERE / "rezultate" / "E40" / "PUTERE_E40.json"


# ---------------------------------------------------------------------------
# Forma jocului (§2)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Shape:
    game: str
    n: int      # numere în urnă
    r: int      # numere pe extragere
    k: int      # numere pe variantă

    @property
    def P2(self) -> float:
        return float(self.r * (self.r - 1)) / float(self.n * (self.n - 1))

    @property
    def P3(self) -> float:
        return float(self.r * (self.r - 1) * (self.r - 2)) / float(self.n * (self.n - 1) * (self.n - 2))

    @property
    def pairs(self) -> list:
        return list(combinations(range(self.k), 2))


SHAPE_649 = Shape("649", 49, 6, 6)
SHAPE_540 = Shape("540", 40, 6, 5)
SHAPES = {"649": SHAPE_649, "540": SHAPE_540}
PROTOCOL_540 = replace(PROTOCOL, seed_master=540)


def protocol_config(shape: Shape) -> Config:
    return PROTOCOL if shape.game == "649" else PROTOCOL_540


# ---------------------------------------------------------------------------
# Triplete și prefixe cauzale (parametrizate)
# ---------------------------------------------------------------------------
_TRI_CACHE: dict = {}


def triples(shape: Shape, device) -> dict:
    key = (shape.n, shape.r, str(device))
    if key not in _TRI_CACHE:
        n = shape.n
        t = torch.tensor(list(combinations(range(n), 3)), dtype=torch.int64)
        lut = torch.full((n, n, n), -1, dtype=torch.int64)
        lut[t[:, 0], t[:, 1], t[:, 2]] = torch.arange(t.shape[0])
        pos = torch.tensor(list(combinations(range(shape.r), 3)), dtype=torch.int64)
        _TRI_CACHE[key] = {"I": t[:, 0].to(device), "J": t[:, 1].to(device), "L": t[:, 2].to(device),
                           "lut": lut.to(device), "pos": pos.to(device)}
    return _TRI_CACHE[key]


class Prefix:
    """Sume prefix pe extrageri și pe pași (ca `engine.Prefix`), pentru orice formă de joc."""

    def __init__(self, ds, shape: Shape, cfg: Config = PROTOCOL, device: torch.device | None = None):
        N = shape.n
        dev = torch.device(device) if device is not None else ds.device
        self.device, self.ds, self.shape = dev, ds, shape
        oh = ds.onehot.to(dev, torch.float32)
        if oh.shape[1] != N or ds.draws.shape[1] != shape.r:
            raise ValueError(f"forma datelor {tuple(ds.draws.shape)}/{tuple(oh.shape)} ≠ {shape}")
        nd = oh.shape[0]
        self.n_draws, self.n_steps = nd, ds.n_steps
        self.offsets = ds.step_offsets.to(dev)
        self.cum1 = torch.zeros(nd + 1, N, device=dev)
        self.cum1[1:] = torch.cumsum(oh, 0)
        self.cum2 = torch.zeros(nd + 1, N, N, device=dev)
        self.cum2[1:] = torch.cumsum(oh[:, :, None] * oh[:, None, :], 0)
        tri = triples(shape, dev)
        d0 = ds.draws.to(dev) - 1
        ids = tri["lut"][d0[:, tri["pos"][:, 0]], d0[:, tri["pos"][:, 1]], d0[:, tri["pos"][:, 2]]]
        m = torch.zeros(nd, tri["I"].shape[0], device=dev)
        m.scatter_(1, ids, 1.0)
        self.cum3 = torch.zeros(nd + 1, tri["I"].shape[0], device=dev)
        self.cum3[1:] = torch.cumsum(m, 0)
        del m
        sidx = ds.step_index.to(dev)
        cnt = torch.zeros(self.n_steps, N, device=dev, dtype=F64)
        cnt.index_add_(0, sidx, oh.to(F64))
        self.step_counts = cnt
        ar = torch.arange(self.n_steps, device=dev, dtype=torch.int64)[:, None].expand(-1, N)
        marks = torch.where(cnt > 0, ar, torch.full_like(ar, -1))
        self.last_seen = torch.cummax(marks, 0).values
        decay = 2.0 ** (-1.0 / cfg.ew_half_life)
        ew = torch.zeros(self.n_steps + 1, N, device=dev, dtype=F64)
        for s in range(1, self.n_steps + 1):
            ew[s] = ew[s - 1] * decay + cnt[s - 1]
        self.ew = ew

    def state(self, ks: torch.Tensor) -> dict:
        N = self.shape.n
        ks = ks.to(self.device, torch.int64)
        n = self.offsets[ks]
        last = torch.where(ks[:, None] >= 1, self.last_seen[(ks - 1).clamp(min=0)],
                           torch.full((ks.shape[0], N), -1, device=self.device, dtype=torch.int64))
        gap = torch.where(last >= 0, ks[:, None] - last, ks[:, None].expand(-1, N)).to(F64)
        return {"k": ks, "n": n.to(F64), "c": self.cum1[n].to(F64), "C": self.cum2[n].to(F64),
                "T": self.cum3[n].to(F64), "ew": self.ew[ks], "gap": gap}


def final_state(draws: torch.Tensor, step_index: torch.Tensor, n_steps: int, shape: Shape,
                cfg: Config = PROTOCOL) -> dict:
    """Starea la k = n_steps (toată istoria) pentru B universuri deodată. draws [B,T,r] (1..n), step_index [T]
    comun. Egală bit cu bit cu `Prefix.state(k = n_steps)` (martor E9); folosită de verificarea de putere."""
    N = shape.n
    dev = draws.device
    B, T, r = draws.shape
    if r != shape.r:
        raise ValueError(f"r={r} ≠ {shape.r}")
    d0 = draws.to(torch.int64) - 1
    oh = torch.zeros(B, T, N, dtype=F64, device=dev)
    oh.scatter_(2, d0, 1.0)
    c = oh.sum(1)
    C = oh.transpose(1, 2) @ oh
    tri = triples(shape, dev)
    ids = tri["lut"][d0[..., tri["pos"][:, 0]], d0[..., tri["pos"][:, 1]], d0[..., tri["pos"][:, 2]]]
    Tc = torch.zeros(B, tri["I"].shape[0], dtype=F64, device=dev)
    Tc.scatter_add_(1, ids.reshape(B, -1), torch.ones(B, ids.shape[1] * ids.shape[2], dtype=F64, device=dev))
    sidx = step_index.to(dev, torch.int64)
    cnt = torch.zeros(B, n_steps, N, dtype=F64, device=dev)
    cnt.index_add_(1, sidx, oh)
    ar = torch.arange(n_steps, device=dev, dtype=torch.int64)[None, :, None].expand(B, -1, N)
    last = torch.where(cnt > 0, ar, torch.full_like(ar, -1)).amax(1)
    k = torch.full((B,), n_steps, dtype=torch.int64, device=dev)
    gap = torch.where(last >= 0, k[:, None] - last, k[:, None].expand(-1, N)).to(F64)
    decay = 2.0 ** (-1.0 / cfg.ew_half_life)
    ew = torch.zeros(B, N, dtype=F64, device=dev)
    for s in range(n_steps):
        ew = ew * decay + cnt[:, s]
    return {"k": k, "n": torch.full((B,), float(T), dtype=F64, device=dev), "c": c, "C": C, "T": Tc,
            "ew": ew, "gap": gap}


# ---------------------------------------------------------------------------
# Exces pe perechi, O2, O3, O5 (parametrizate)
# ---------------------------------------------------------------------------
def pair_excess(C: torch.Tensor, n: torch.Tensor, shape: Shape) -> torch.Tensor:
    P2 = shape.P2
    E = (n * P2)[:, None, None]
    A = (C - E) / torch.sqrt(E * (1 - P2) + 1e-9)
    A = A * (1 - torch.eye(shape.n, device=C.device, dtype=F64))
    norm = torch.linalg.eigvalsh(A).abs().amax(-1)
    return torch.where(norm[:, None, None] > 0, A / norm.clamp(min=1e-300)[:, None, None], torch.zeros_like(A))


def op_amplituhedron(c, ew, T, n, shape: Shape, details: bool = False) -> dict:
    N = shape.n
    B = c.shape[0]
    dev = c.device
    tri = triples(shape, dev)
    I, J, L = tri["I"], tri["J"], tri["L"]
    cm = c.amax(-1, keepdim=True)
    em = ew.amax(-1, keepdim=True)
    z = torch.stack([torch.ones_like(c), torch.where(cm > 0, c / cm.clamp(min=1e-300), torch.zeros_like(c)),
                     torch.where(em > 0, ew / em.clamp(min=1e-300), torch.zeros_like(ew))], -1)
    zi, zj, zl = z[:, I], z[:, J], z[:, L]
    vol = (zi * torch.linalg.cross(zj, zl, dim=-1)).sum(-1).abs()
    w = (T + 1.0) / (n[:, None] * shape.P3 + 1.0)
    vw = vol * w
    V = torch.zeros(B, N, N, N, dtype=F64, device=dev)
    for p, q, r in ((I, J, L), (I, L, J), (J, I, L), (J, L, I), (L, I, J), (L, J, I)):
        V[:, p, q, r] = vw
    a = V.sum((-1, -2)) / 2.0
    am = a.mean(-1, keepdim=True)
    a = torch.where(am > 0, a / am.clamp(min=1e-300), torch.ones_like(a))
    out = {"amp": a, "vol_total": vol.sum(-1)}
    if details:
        out["pair_scatter"] = V.sum(-1)
        out["z"] = z
    return out


def op_poincare(C, n, A, shape: Shape, cfg: Config = PROTOCOL) -> dict:
    N = shape.n
    B = C.shape[0]
    dev = C.device
    eye = torch.eye(N, dtype=torch.bool, device=dev)
    E = (n * shape.P2)[:, None, None]
    delta = torch.log((E + 1) / (C + 1))
    big = torch.finfo(F64).max
    dmin = delta.masked_fill(eye, big).amin((-1, -2), keepdim=True)
    delta = delta - dmin + cfg.poincare_delta_min
    dmean = delta.masked_fill(eye, 0).sum((-1, -2), keepdim=True) / (N * (N - 1))
    delta = (delta * (cfg.poincare_delta_mean / dmean)).masked_fill(eye, 0)
    ang = 2 * math.pi * torch.arange(N, dtype=F64, device=dev) / N
    x0 = cfg.poincare_init_r * torch.stack([torch.cos(ang), torch.sin(ang)], -1)
    triu = torch.triu(torch.ones(N, N, dtype=torch.bool, device=dev), 1)
    with torch.inference_mode(False), torch.enable_grad():
        x = x0[None].expand(B, -1, -1).clone().requires_grad_(True)
        opt = torch.optim.Adam([x], lr=cfg.poincare_lr)
        dlt = delta.clone()
        for _ in range(cfg.poincare_iters):
            opt.zero_grad(set_to_none=True)
            xx = (x * x).sum(-1)
            d2 = ((x[:, :, None] - x[:, None]) ** 2).sum(-1)
            arg = 1 + 2 * d2 / ((1 - xx)[:, :, None] * (1 - xx)[:, None])
            arg = torch.where(triu, arg, torch.full_like(arg, 2.0)).clamp(min=1 + 1e-12)
            dh = torch.acosh(arg)
            loss = (((dh - dlt) ** 2) * triu).sum()
            loss.backward()
            opt.step()
            with torch.no_grad():
                rr = torch.linalg.vector_norm(x, dim=-1, keepdim=True)
                x.mul_(torch.where(rr > cfg.poincare_rmax, cfg.poincare_rmax / rr, torch.ones_like(rr)))
        x = x.detach()
    dh = poincare_dist(x[:, :, None], x[:, None]).masked_fill(eye, 0)
    stress = (((dh - delta) ** 2) * triu).sum((-1, -2))
    d0 = poincare_dist(x, torch.zeros_like(x))
    u = torch.exp(-d0)
    u = u / u.mean(-1, keepdim=True)
    order = torch.sort(u, dim=-1, descending=True, stable=True).indices
    anchors = order[:, : cfg.n_anchors] + 1
    Am = A.masked_fill(eye, -float("inf"))
    vals, idx = Am.topk(cfg.forman_k, dim=-1)
    adj = torch.zeros(B, N, N, dtype=torch.bool, device=dev)
    adj.scatter_(2, idx, vals > 0)
    adj = adj | adj.transpose(1, 2)
    deg = adj.sum(-1).to(F64)
    Fe = 4 - deg[:, :, None] - deg[:, None, :]
    forman = torch.where(deg > 0, (Fe * adj).sum(-1) / deg.clamp(min=1), torch.zeros_like(deg))
    return {"x": x, "u": u, "anchors": anchors, "radius_h": d0, "stress": stress, "forman": forman,
            "delta": delta}


def born_state(psi_walk, amp, u, theta, W, cfg: Config = PROTOCOL) -> dict:
    pw = psi_walk.to(C128)
    m = (pw.abs() ** 2) * amp * u
    m = m / m.sum(-1, keepdim=True)
    psi = torch.sqrt(m) * torch.exp(1j * (torch.angle(pw) + theta))
    Kphi = W.to(C128) * torch.exp(1j * (theta[:, :, None] - theta[:, None, :]))
    psi_f = psi + cfg.interference_eta * (Kphi @ psi[..., None])[..., 0]
    P = psi_f.abs() ** 2
    s = P.sum(-1, keepdim=True)
    P = torch.where(s > 0, P / s.clamp(min=1e-300), torch.full_like(P, 1.0 / P.shape[-1]))
    return {"psi_f": psi_f, "P": P}


def boltzmann_filter(P: torch.Tensor, seeds: torch.Tensor, shape: Shape, cfg: Config = PROTOCOL,
                     chunk: int = 4) -> dict:
    N, K = shape.n, shape.k
    B = P.shape[0]
    dev = P.device
    R = cfg.replicas
    beta = torch.logspace(cfg.beta_lo_exp, cfg.beta_hi_exp, R, dtype=F64, device=dev).to(torch.float32)
    logP = torch.log(P.clamp(min=1e-300))
    pis, cores = [], []
    ridx = torch.arange(R * N, device=dev, dtype=torch.int64)
    for s0 in range(0, B, chunk):
        sl = slice(s0, min(B, s0 + chunk))
        base = stream(seeds[sl].to(dev), TAG_BOLTZ)[:, None]
        u1 = 1.0 - uniform(base, 2 * ridx[None])
        u2 = uniform(base, 2 * ridx[None] + 1)
        eps = (torch.sqrt(-2.0 * torch.log(u1)) * torch.cos(2 * math.pi * u2)).to(torch.float32).view(-1, R, N)
        del u1, u2
        logits = beta[None, :, None] * (logP[sl].to(torch.float32)[:, None, :] + cfg.noise_sigma * eps)
        pr = torch.softmax(logits, -1)
        pis.append(pr.to(F64).mean(1))
        top = logits.topk(K, dim=-1).indices
        cnt = torch.zeros(top.shape[0], N, device=dev, dtype=F64)
        cnt.scatter_add_(1, top.reshape(top.shape[0], -1), torch.ones(top.shape[0], R * K, device=dev, dtype=F64))
        cores.append(cnt / R)
        del eps, logits, pr, top
    pi = torch.cat(pis, 0)
    pi = pi / pi.sum(-1, keepdim=True)
    top_frac = torch.cat(cores, 0)
    return {"pi": pi, "topk_frac": top_frac, "core": top_frac >= cfg.core_frac}


# ---------------------------------------------------------------------------
# O6 — energie și anealer QUBO pe combinații de exact k noduri
# ---------------------------------------------------------------------------
_PAIR_CACHE: dict = {}


def _pair_idx(shape: Shape, device):
    key = (shape.k, str(device))
    if key not in _PAIR_CACHE:
        pr = shape.pairs
        _PAIR_CACHE[key] = (torch.tensor([p[0] for p in pr]).to(device), torch.tensor([p[1] for p in pr]).to(device))
    return _PAIR_CACHE[key]


def code(S0: torch.Tensor, shape: Shape) -> torch.Tensor:
    s = torch.sort(S0, dim=-1).values
    w = torch.tensor([(shape.n + 1) ** (shape.k - 1 - i) for i in range(shape.k)], dtype=torch.int64,
                     device=S0.device)
    return (s * w).sum(-1)


def energy(S0: torch.Tensor, logpi: torch.Tensor, A: torch.Tensor, ov: torch.Tensor, shape: Shape, cfg: Config,
           forbid: torch.Tensor | None = None) -> torch.Tensor:
    """S0: [B,C,k] indici 0..n−1; logpi [B,n]; A [B,n,n]; ov [B,n]; forbid [B,F] coduri ale variantelor anterioare."""
    B = S0.shape[0]
    bidx = torch.arange(B, device=S0.device)[:, None, None]
    e = -logpi.gather(1, S0.reshape(B, -1)).reshape(S0.shape).sum(-1)
    pi_, pj_ = _pair_idx(shape, S0.device)
    e = e - cfg.lam_pair * A[bidx, S0[..., pi_], S0[..., pj_]].sum(-1)
    if cfg.crowd_shield:
        e = e + cfg.mu_crowd * crowd_penalty(S0 + 1)
    e = e + cfg.mu_overlap * ov.gather(1, S0.reshape(B, -1)).reshape(S0.shape).sum(-1)
    if forbid is not None and forbid.shape[1] > 0:
        hit = (code(S0, shape)[..., None] == forbid[:, None, :]).any(-1)
        e = e + FORBID_PENALTY * hit.to(e.dtype)
    return e


def mcmc_variant(logpi, A, ov, seeds, shape: Shape, cfg: Config = PROTOCOL, return_states: bool = False,
                 forbid=None):
    """Paralel tempering Metropolis pe combinații de EXACT k numere (mutare = schimb membru ↔ ne-membru)."""
    N, K = shape.n, shape.k
    B = logpi.shape[0]
    dev = logpi.device
    Tn, Cq = cfg.n_temps, cfg.chains_per_temp
    C = Tn * Cq
    temps = torch.logspace(math.log10(cfg.t_lo), math.log10(cfg.t_hi), Tn, dtype=F64, device=dev)
    tchain = temps.repeat_interleave(Cq)
    chain_ids = torch.arange(C, device=dev, dtype=torch.int64)
    base = splitmix(stream(seeds.to(dev), TAG_MCMC)[:, None] ^ chain_ids[None])
    ib = splitmix(stream(seeds.to(dev), TAG_INIT)[:, None] ^ chain_ids[None])
    keys = uniform(ib[..., None], torch.arange(N, device=dev, dtype=torch.int64))
    S = keys.topk(K, dim=-1).indices
    mask = torch.zeros(B, C, N, dtype=torch.bool, device=dev)
    mask.scatter_(2, S, True)
    E = energy(S, logpi, A, ov, shape, cfg, forbid)
    best_e = E.amin(1)
    cand = torch.where(E == best_e[:, None], code(S, shape), torch.full_like(code(S, shape), 1 << 62))
    bi = cand.argmin(1)
    best_s = S[torch.arange(B, device=dev), bi].clone()
    best_code = cand.gather(1, bi[:, None])[:, 0]
    sbase = splitmix(stream(seeds.to(dev), TAG_SWAP)[:, None] ^ torch.arange(Cq, device=dev)[None])
    ar = torch.arange(B, device=dev)
    for it in range(cfg.mcmc_steps):
        cnt0 = 4 * it
        up = uniform(base, cnt0)
        ur = uniform(base, cnt0 + 1)
        ua = uniform(base, cnt0 + 2)
        p = (up * K).floor().to(torch.int64).clamp(max=K - 1)
        r = (ur * (N - K)).floor().to(torch.int64).clamp(max=N - K - 1)
        nonmem = ~mask
        cs = torch.cumsum(nonmem.to(torch.int64), -1)
        b = ((cs == (r + 1)[..., None]) & nonmem).to(torch.int8).argmax(-1)
        a = S.gather(2, p[..., None])[..., 0]
        Sn = S.scatter(2, p[..., None], b[..., None])
        En = energy(Sn, logpi, A, ov, shape, cfg, forbid)
        acc = torch.log1p(-ua) < -(En - E) / tchain[None]
        S = torch.where(acc[..., None], Sn, S)
        E = torch.where(acc, En, E)
        accf = acc[..., None]
        mask.scatter_(2, a[..., None], mask.gather(2, a[..., None]) & ~accf)
        mask.scatter_(2, b[..., None], mask.gather(2, b[..., None]) | accf)
        emin = E.amin(1)
        codes = code(S, shape)
        cand = torch.where(E == emin[:, None], codes, torch.full_like(codes, 1 << 62))
        ci = cand.argmin(1)
        cc = cand.gather(1, ci[:, None])[:, 0]
        better = (emin < best_e) | ((emin == best_e) & (cc < best_code))
        best_s = torch.where(better[:, None], S[ar, ci], best_s)
        best_e = torch.where(better, emin, best_e)
        best_code = torch.where(better, cc, best_code)
        if (it + 1) % cfg.swap_every == 0:
            par = ((it + 1) // cfg.swap_every) % 2
            Sv = S.view(B, Tn, Cq, K)
            Ev = E.view(B, Tn, Cq)
            Mv = mask.view(B, Tn, Cq, N)
            for t in range(par, Tn - 1, 2):
                us = uniform(sbase, it * Tn + t)
                e_i, e_j = Ev[:, t], Ev[:, t + 1]
                lacc = (e_i - e_j) * (1.0 / temps[t] - 1.0 / temps[t + 1])
                sw = torch.log1p(-us) < lacc
                si, sj = Sv[:, t].clone(), Sv[:, t + 1].clone()
                Sv[:, t] = torch.where(sw[..., None], sj, si)
                Sv[:, t + 1] = torch.where(sw[..., None], si, sj)
                ei, ej = e_i.clone(), e_j.clone()
                Ev[:, t] = torch.where(sw, ej, ei)
                Ev[:, t + 1] = torch.where(sw, ei, ej)
                mi, mj = Mv[:, t].clone(), Mv[:, t + 1].clone()
                Mv[:, t] = torch.where(sw[..., None], mj, mi)
                Mv[:, t + 1] = torch.where(sw[..., None], mi, mj)
            S, E, mask = Sv.reshape(B, C, K), Ev.reshape(B, C), Mv.reshape(B, C, N)
    if return_states:
        return torch.sort(best_s, dim=-1).values + 1, best_e, torch.sort(S, dim=-1).values + 1, E
    return torch.sort(best_s, dim=-1).values + 1, best_e


def op_variants(logpi, A, seeds, shape: Shape, cfg: Config = PROTOCOL) -> dict:
    B = logpi.shape[0]
    ov = torch.zeros(B, shape.n, dtype=F64, device=logpi.device)
    forbid = torch.zeros(B, 0, dtype=torch.int64, device=logpi.device)
    vs, es = [], []
    for v in range(1, cfg.n_variants + 1):
        s, e = mcmc_variant(logpi, A, ov, seeds + v, shape, cfg, forbid=forbid)
        vs.append(s)
        es.append(e)
        ov = ov.clone()
        ov.scatter_add_(1, s - 1, torch.ones(B, shape.k, dtype=F64, device=logpi.device))
        forbid = torch.cat([forbid, code(s - 1, shape)[:, None]], 1)
    return {"variants": torch.stack(vs, 1), "energies": torch.stack(es, 1)}


# ---------------------------------------------------------------------------
# Orchestrare
# ---------------------------------------------------------------------------
def _score_chunk(st: dict, kb: torch.Tensor, seeds_b: torch.Tensor, shape: Shape, cfg: Config, details: bool,
                 tick) -> dict:
    N = shape.n
    dev = kb.device
    t0 = time.perf_counter()
    A = pair_excess(st["C"], st["n"], shape)
    D = dissipation(st["gap"])
    tick("state", t0)
    t0 = time.perf_counter()
    o1 = op_nonhermitian(A, D, cfg, details)
    tick("O1_nonhermitian_EP", t0)
    t0 = time.perf_counter()
    o2 = op_amplituhedron(st["c"], st["ew"], st["T"], st["n"], shape, details)
    tick("O2_amplituhedron", t0)
    t0 = time.perf_counter()
    o3 = op_poincare(st["C"], st["n"], A, shape, cfg)
    tick("O3_poincare", t0)
    t0 = time.perf_counter()
    o4 = op_kuramoto(A, st["c"], st["gap"], kb, cfg, record_every=4 if details else 0)
    tick("O4_kuramoto", t0)
    t0 = time.perf_counter()
    bsz = kb.shape[0]
    psi_w = o1["psi_walk"] if cfg.use_walk else torch.full((bsz, N), 1 / math.sqrt(N), dtype=torch.complex64, device=dev)
    amp = o2["amp"] if cfg.use_amplituhedron else torch.ones(bsz, N, dtype=F64, device=dev)
    u = o3["u"] if cfg.use_poincare else torch.ones(bsz, N, dtype=F64, device=dev)
    th = o4["theta"] if cfg.use_kuramoto else torch.zeros(bsz, N, dtype=F64, device=dev)
    Wk = o4["W"] if cfg.use_kuramoto else torch.zeros_like(A)
    o5 = born_state(psi_w, amp, u, th, Wk, cfg)
    bf = boltzmann_filter(o5["P"], seeds_b, shape, cfg)
    tick("O5_born_boltzmann", t0)
    rec = {"pi": bf["pi"], "A": A, "P": o5["P"], "gamma_q": o1["gamma_q"], "ep_gamma": o1["ep_gamma"],
           "ep_converged": o1["ep_converged"], "anchors": o3["anchors"], "core": bf["core"]}
    if details:
        rec.update({"psi_f": o5["psi_f"], "topk_frac": bf["topk_frac"], "o1": o1, "o2": o2, "o3": o3, "o4": o4,
                    "D": D, "state": st})
    return rec


def _ticker(dev, tm):
    def tick(name, t0):
        if dev.type == "cuda":
            torch.cuda.synchronize()
        tm[name] = tm.get(name, 0.0) + time.perf_counter() - t0
    return tick


def _collect(outs: dict) -> dict:
    res = {}
    for kk, vv in outs.items():
        res[kk] = torch.cat(vv, 0) if torch.is_tensor(vv[0]) else vv
    return res


def score_steps(prefix: Prefix, ks: torch.Tensor, cfg: Config = PROTOCOL, details: bool = False,
                chunk: int = 64, timings: dict | None = None) -> dict:
    """O1–O5 pentru pașii ks ai unui `Prefix` (sămânța pasului `step_seed(cfg, k)`, ca în `engine.score_steps`)."""
    dev = prefix.device
    ks = ks.to(dev, torch.int64)
    outs: dict[str, list] = {}
    tick = _ticker(dev, timings if timings is not None else {})
    for s0 in range(0, ks.shape[0], chunk):
        kb = ks[s0:s0 + chunk]
        t0 = time.perf_counter()
        st = prefix.state(kb)
        tick("state", t0)
        rec = _score_chunk(st, kb, step_seed(cfg, kb), prefix.shape, cfg, details, tick)
        for kk, vv in rec.items():
            outs.setdefault(kk, []).append(vv)
    return _collect(outs)


def score_states(st: dict, seeds: torch.Tensor, shape: Shape, cfg: Config = PROTOCOL, chunk: int = 64,
                 timings: dict | None = None) -> dict:
    """O1–O5 pe stări date explicit (ex. `final_state` pentru B universuri), cu semințe explicite."""
    ks = st["k"]
    dev = ks.device
    outs: dict[str, list] = {}
    tick = _ticker(dev, timings if timings is not None else {})
    for s0 in range(0, ks.shape[0], chunk):
        sl = slice(s0, s0 + chunk)
        sb = {kk: vv[sl] for kk, vv in st.items()}
        rec = _score_chunk(sb, ks[sl], seeds[sl].to(dev), shape, cfg, False, tick)
        for kk, vv in rec.items():
            outs.setdefault(kk, []).append(vv)
    return _collect(outs)


def variants_steps(pi: torch.Tensor, A: torch.Tensor, ks: torch.Tensor, shape: Shape, cfg: Config = PROTOCOL,
                   chunk: int = 1024, seeds: torch.Tensor | None = None) -> dict:
    outs_v, outs_e = [], []
    logpi = torch.log(pi.clamp(min=1e-300))
    sd = step_seed(cfg, ks.to(pi.device)) if seeds is None else seeds.to(pi.device)
    for s0 in range(0, pi.shape[0], chunk):
        sl = slice(s0, s0 + chunk)
        o = op_variants(logpi[sl], A[sl], sd[sl], shape, cfg)
        outs_v.append(o["variants"])
        outs_e.append(o["energies"])
    return {"variants": torch.cat(outs_v, 0), "energies": torch.cat(outs_e, 0)}


def run_full(ds, shape: Shape, cfg: Config | None = None, device=None, k: int | None = None) -> dict:
    """Produsul polimorf: toți operatorii la pasul k (implicit toată istoria). Variante = minime de energie."""
    cfg = protocol_config(shape) if cfg is None else cfg
    t_all = time.perf_counter()
    dev = ds.device if device is None else torch.device(device)
    if torch.cuda.is_available() and dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    prefix = Prefix(ds, shape, cfg, dev)
    kk = ds.n_steps if k is None else int(k)
    ks = torch.tensor([kk], dtype=torch.int64, device=dev)
    timings: dict = {}
    sc = score_steps(prefix, ks, cfg, details=True, timings=timings)
    t0 = time.perf_counter()
    vv = variants_steps(sc["pi"], sc["A"], ks, shape, cfg)
    if dev.type == "cuda":
        torch.cuda.synchronize()
    timings["O6_mcmc_qubo"] = time.perf_counter() - t0
    o1, o2, o3, o4 = sc["o1"][0], sc["o2"][0], sc["o3"][0], sc["o4"][0]
    st = sc["state"][0]
    N = shape.n
    tri = torch.triu_indices(N, N, 1, device=dev)
    ps = o2["pair_scatter"][0][tri[0], tri[1]]
    top_pairs = torch.sort(ps, descending=True, stable=True).indices[:15]
    proto = PROTOCOL_FILE if shape.game != "649" else QL / "PREINREGISTRARE_QL649.md"
    game = getattr(ds, "game", None)
    return {
        "game": shape.game, "shape": {"n": shape.n, "r": shape.r, "k": shape.k},
        "k": kk, "n_draws_used": int(st["n"][0].item()), "n_steps": ds.n_steps,
        "last_date": ds.step_dates[-1] if ds.step_dates else None,
        "device": str(dev), "config_digest": cfg.digest(), "is_protocol": cfg == protocol_config(shape),
        "protocol_sha256": sha256_file(proto) if proto.exists() else None,
        "source_sha256": ds.source_sha256, "source_kind": getattr(ds, "source_kind", None),
        "dataset_game": getattr(game, "code", None),
        "pi": sc["pi"][0], "P": sc["P"][0], "psi_f": sc["psi_f"][0], "core": sc["core"][0],
        "topk_frac": sc["topk_frac"][0], "A": sc["A"][0],
        "gamma_q": float(o1["gamma_q"][0]), "gap_q": float(o1["gap_q"][0]),
        "ep_gamma": complex(o1["ep_gamma"][0].item()), "ep_lambda": complex(o1["ep_lambda"][0].item()),
        "ep_residual": float(o1["ep_residual"][0]), "ep_converged": bool(o1["ep_converged"][0]),
        "ep_iters": int(o1["ep_iters"][0]), "ep_pair": (o1["ep_pair"][0] + 1).tolist(),
        "gamma_grid": o1["gamma_grid"], "gap_grid": o1["gap_grid"][0], "spectrum_grid": o1["spectrum_grid"][0],
        "spectrum_q": o1["spectrum_q"][0], "psi_walk": o1["psi_walk"][0],
        "amp": o2["amp"][0], "pair_scatter": o2["pair_scatter"][0], "vol_total": float(o2["vol_total"][0]),
        "top_pairs": [((int(tri[0][i]) + 1, int(tri[1][i]) + 1), float(ps[i])) for i in top_pairs],
        "x": o3["x"][0], "u": o3["u"][0], "anchors": o3["anchors"][0].tolist(), "radius_h": o3["radius_h"][0],
        "forman": o3["forman"][0], "stress": float(o3["stress"][0]),
        "theta": o4["theta"][0], "r_local": o4["r_local"][0], "spikes": o4["spikes"][0],
        "R_global": float(o4["R_global"][0]), "R_series": o4["R_series"][0],
        "variants": vv["variants"][0].tolist(), "energies": vv["energies"][0].tolist(),
        "timings_s": timings, "vram": _vram(), "elapsed_s": time.perf_counter() - t_all,
        "positive_claims_allowed": False,
        "note": "Variante = minime de energie, NU predicții. Calcul clasic.",
    }


def power_verdict() -> str | None:
    """Verdictul verificării de putere sintetice (PROTOCOL_TU3_E40 §4), sau None dacă nu a rulat."""
    if not POWER_FILE.exists():
        return None
    return json.loads(POWER_FILE.read_text()).get("verdict")


def run_full_540(ds=None, cfg: Config = PROTOCOL_540, device=None, k: int | None = None) -> dict:
    """Produsul E40 (5/40): intrare implicită `parser_multi.build_game_dataset("540", "live")`.
    Refuză datele reale înainte ca verificarea de putere sintetică să dea `E40_PASS` (§4)."""
    if power_verdict() != "E40_PASS":
        raise RuntimeError("E40: verificarea de putere sintetică nu a dat E40_PASS; nicio rulare pe date reale (§4)")
    if ds is None:
        ds = PM.build_game_dataset("540", "live", device=device)
    if getattr(ds, "game", None) is None or ds.game.code != "540":
        raise ValueError("run_full_540 cere un GameDataset 5/40")
    return run_full(ds, SHAPE_540, cfg, device, k)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="TU3 E40 — motorul 5/40 (variante = minime de energie, NU predicții)")
    ap.add_argument("--sursa", default="live", help="live (produs) sau frozen (protocoale sigilate)")
    a = ap.parse_args(argv)
    ds = PM.build_game_dataset("540", a.sursa)
    out = run_full_540(ds)
    show = {kk: vv for kk, vv in out.items() if not torch.is_tensor(vv)}
    print(json.dumps(show, indent=2, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
