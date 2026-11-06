"""QL649 — STEP 2: motorul „Quantum-Limit” (engine.py).

Implementează exact operatorii O1–O6 din PREINREGISTRARE_QL649.md (sigilat):
  O1 walk non-hermitic H(γ)=A+iγD + puncte excepționale (grilă + Newton complex128)
  O2 volume de politop pozitiv „inspirate din Amplituhedron” pe toate cele 18424 triplete
  O3 încorporare în discul Poincaré (stres hiperbolic, Adam) + 3 ancore + curbură Forman
  O4 rețea Kuramoto RK4 cu salturi de interferență instantanee pe partenerii încâlciți
  O5 colaps Born P=|Ψ|² + filtru Boltzmann pe 50 000 de replici paralele
  O6 MCMC geometric (paralel tempering, 10 000 pași) + QUBO secvențial pentru 3 variante

Totul este calcul CLASIC (PyTorch, GPU NVIDIA implicit, CPU numai ca fallback).
Inspirația cuantică este strict matematică; motorul nu aduce informație nouă despre
extragerea următoare și nu revendică avantaj (`positive_claims_allowed=false`).

Cauzalitate: la pasul k se folosesc NUMAI extragerile din pașii < k (o zi = un pas).
Numerele aleatoare vin dintr-un RNG pe contor (SplitMix64 în aritmetică int64),
cheiat pe seed-ul pasului: rezultatele nu depind de împărțirea în loturi și sunt
identice pe CPU și GPU pentru aceleași intrări.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, replace
from itertools import combinations
from pathlib import Path

import torch

from parser import DEFAULT_SOURCE, Dataset, build_dataset, resolve_device

ROOT = Path(__file__).resolve().parent
N = 49
K6 = 6
F64, C128 = torch.float64, torch.complex128
P2 = 30.0 / 2352.0               # P(pereche în extragere)
P3 = 120.0 / 110544.0            # P(triplet în extragere)


@dataclass(frozen=True)
class Config:
    """Hiperparametri fixați de protocolul QL649-P1. Valorile implicite = protocol."""
    gamma_max: float = 2.0
    gamma_grid: int = 48
    newton_h: float = 1e-6
    newton_iters: int = 40
    newton_tol: float = 1e-10
    walk_dt: float = 0.15
    walk_steps: int = 24
    ew_half_life: float = 26.0
    poincare_lr: float = 0.02
    poincare_iters: int = 400
    poincare_init_r: float = 0.5
    poincare_delta_min: float = 0.1
    poincare_delta_mean: float = 2.0
    poincare_rmax: float = 1.0 - 1e-5
    n_anchors: int = 3
    forman_k: int = 6
    kur_K: float = 2.0
    kur_dt: float = 0.05
    kur_steps: int = 200
    kur_spike: float = 0.8
    kur_jump: float = 0.35
    interference_eta: float = 0.5
    replicas: int = 50000
    beta_lo_exp: float = -1.0
    beta_hi_exp: float = 1.0
    noise_sigma: float = 0.5
    core_frac: float = 0.5
    lam_pair: float = 0.5
    mu_crowd: float = 0.25
    mu_overlap: float = 1.0
    crowd_shield: bool = True
    n_variants: int = 3
    n_temps: int = 8
    chains_per_temp: int = 32
    t_lo: float = 0.05
    t_hi: float = 2.0
    mcmc_steps: int = 10000
    swap_every: int = 10
    seed_master: int = 649
    seed_mult: int = 100003
    # Comutatoare de ablație (UI). Protocolul = toate True; orice False este NON-protocol.
    use_walk: bool = True
    use_amplituhedron: bool = True
    use_poincare: bool = True
    use_kuramoto: bool = True

    def is_protocol(self) -> bool:
        return self == Config()

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


PROTOCOL = Config()


def step_seed(cfg: Config, k):
    return cfg.seed_master * cfg.seed_mult + k


# ---------------------------------------------------------------------------
# RNG pe contor (SplitMix64) — independent de dispozitiv și de loturi
# ---------------------------------------------------------------------------
def _s64(v: int) -> int:
    return v - (1 << 64) if v >= (1 << 63) else v


_G = _s64(0x9E3779B97F4A7C15)
_M1 = _s64(0xBF58476D1CE4E5B9)
_M2 = _s64(0x94D049BB133111EB)
TAG_BOLTZ = 0x426F6C747A
TAG_MCMC = 0x4D434D43
TAG_INIT = 0x494E4954
TAG_SWAP = 0x53574150


def _srl(x: torch.Tensor, s: int) -> torch.Tensor:
    return (x >> s) & ((1 << (64 - s)) - 1)


def splitmix(x: torch.Tensor) -> torch.Tensor:
    z = x + _G
    z = (z ^ _srl(z, 30)) * _M1
    z = (z ^ _srl(z, 27)) * _M2
    return z ^ _srl(z, 31)


def stream(seed: torch.Tensor, tag: int) -> torch.Tensor:
    return splitmix(splitmix(seed.to(torch.int64)) ^ tag)


def uniform(base: torch.Tensor, counter) -> torch.Tensor:
    """U[0,1) float64 pentru (bază, contor) — SplitMix64 în flux."""
    if not torch.is_tensor(counter):
        off = _s64((int(counter) * 0x9E3779B97F4A7C15) & ((1 << 64) - 1))
        z = splitmix(base + off)
        return _srl(z, 11).to(F64) * (2.0 ** -53)
    z = splitmix(base + counter.to(torch.int64) * _G)
    return _srl(z, 11).to(F64) * (2.0 ** -53)


# ---------------------------------------------------------------------------
# Indicii tripletelor și prefixele cauzale
# ---------------------------------------------------------------------------
_TRI_CACHE: dict = {}


def triples(device) -> dict:
    key = str(device)
    if key not in _TRI_CACHE:
        t = torch.tensor(list(combinations(range(N), 3)), dtype=torch.int64)
        lut = torch.full((N, N, N), -1, dtype=torch.int64)
        lut[t[:, 0], t[:, 1], t[:, 2]] = torch.arange(t.shape[0])
        pos = torch.tensor(list(combinations(range(K6), 3)), dtype=torch.int64)
        _TRI_CACHE[key] = {"I": t[:, 0].to(device), "J": t[:, 1].to(device), "L": t[:, 2].to(device),
                           "lut": lut.to(device), "pos6": pos.to(device)}
    return _TRI_CACHE[key]


PAIR15 = list(combinations(range(K6), 2))


class Prefix:
    """Sume prefix pe extrageri și pe pași: stare cauzală O(1) pentru orice pas k."""

    def __init__(self, ds: Dataset, cfg: Config = PROTOCOL, device: torch.device | None = None):
        dev = torch.device(device) if device is not None else ds.device
        self.device, self.ds = dev, ds
        oh = ds.onehot.to(dev, torch.float32)
        nd = oh.shape[0]
        self.n_draws, self.n_steps = nd, ds.n_steps
        self.offsets = ds.step_offsets.to(dev)
        self.cum1 = torch.zeros(nd + 1, N, device=dev)
        self.cum1[1:] = torch.cumsum(oh, 0)
        self.cum2 = torch.zeros(nd + 1, N, N, device=dev)
        self.cum2[1:] = torch.cumsum(oh[:, :, None] * oh[:, None, :], 0)
        tri = triples(dev)
        d0 = ds.draws.to(dev) - 1
        ids = tri["lut"][d0[:, tri["pos6"][:, 0]], d0[:, tri["pos6"][:, 1]], d0[:, tri["pos6"][:, 2]]]
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
        self.last_seen = torch.cummax(marks, 0).values  # [S,49]
        decay = 2.0 ** (-1.0 / cfg.ew_half_life)
        ew = torch.zeros(self.n_steps + 1, N, device=dev, dtype=F64)
        for s in range(1, self.n_steps + 1):
            ew[s] = ew[s - 1] * decay + cnt[s - 1]
        self.ew = ew

    def state(self, ks: torch.Tensor) -> dict:
        ks = ks.to(self.device, torch.int64)
        n = self.offsets[ks]
        last = torch.where(ks[:, None] >= 1, self.last_seen[(ks - 1).clamp(min=0)], torch.full((ks.shape[0], N), -1, device=self.device, dtype=torch.int64))
        gap = torch.where(last >= 0, ks[:, None] - last, ks[:, None].expand(-1, N)).to(F64)
        return {"k": ks, "n": n.to(F64), "c": self.cum1[n].to(F64), "C": self.cum2[n].to(F64),
                "T": self.cum3[n].to(F64), "ew": self.ew[ks], "gap": gap}


# ---------------------------------------------------------------------------
# Matricea de exces pe perechi și disiparea
# ---------------------------------------------------------------------------
def pair_excess(C: torch.Tensor, n: torch.Tensor) -> torch.Tensor:
    E = (n * P2)[:, None, None]
    A = (C - E) / torch.sqrt(E * (1 - P2) + 1e-9)
    A = A * (1 - torch.eye(N, device=C.device, dtype=F64))
    norm = torch.linalg.eigvalsh(A).abs().amax(-1)
    return torch.where(norm[:, None, None] > 0, A / norm.clamp(min=1e-300)[:, None, None], torch.zeros_like(A))


def dissipation(gap: torch.Tensor) -> torch.Tensor:
    z = (gap - gap.mean(-1, keepdim=True)) / (gap.std(-1, unbiased=False, keepdim=True) + 1e-9)
    return torch.tanh(z)


# ---------------------------------------------------------------------------
# O1 — walk non-hermitic și puncte excepționale
# ---------------------------------------------------------------------------
def _track(ev, la, lb):
    da = (ev - la[:, None]).abs()
    ia = da.argmin(1)
    db = (ev - lb[:, None]).abs()
    db.scatter_(1, ia[:, None], float("inf"))
    ib = db.argmin(1)
    return ev.gather(1, ia[:, None])[:, 0], ev.gather(1, ib[:, None])[:, 0]


def _hgam(A, D, gam):
    """H(γ) = A + iγ·diag(D); γ complex [B] sau grilă reală [G]."""
    return A.to(C128) + 1j * gam[..., None, None] * torch.diag_embed(D.to(C128))


def op_nonhermitian(A: torch.Tensor, D: torch.Tensor, cfg: Config = PROTOCOL, details: bool = False) -> dict:
    B, n, _ = A.shape
    dev = A.device
    gam = torch.linspace(0.0, cfg.gamma_max, cfg.gamma_grid, dtype=F64, device=dev)
    H = A.to(C128)[:, None] + 1j * gam[None, :, None, None] * torch.diag_embed(D.to(C128))[:, None]
    ev = torch.linalg.eigvals(H)                                   # [B,G,n]
    eye = torch.eye(n, device=dev, dtype=torch.bool)
    diff = (ev[..., :, None] - ev[..., None, :]).abs().masked_fill(eye, float("inf"))
    gapmin = diff.amin((-1, -2))                                   # [B,G]
    gi = gapmin.argmin(1)                                          # primul minim = γ mai mic
    ar = torch.arange(B, device=dev)
    gq = gam[gi]
    evq = ev[ar, gi]
    flat = diff[ar, gi].reshape(B, -1).argmin(1)
    ia, ib = flat // n, flat % n
    la, lb = evq[ar, ia], evq[ar, ib]
    # Newton complex128 pe g(γ)=(λa−λb)², urmărire prin cel mai apropiat vecin
    g_c = gq.to(C128).clone()
    active = torch.ones(B, dtype=torch.bool, device=dev)
    iters = torch.zeros(B, dtype=torch.int64, device=dev)
    for _ in range(cfg.newton_iters):
        idx = active.nonzero()[:, 0]
        if idx.numel() == 0:
            break
        Ai, Di, gi_c = A[idx], D[idx], g_c[idx]
        e0 = torch.linalg.eigvals(_hgam(Ai, Di, gi_c))
        a0, b0 = _track(e0, la[idx], lb[idx])
        g0 = (a0 - b0) ** 2
        la[idx], lb[idx] = a0, b0
        conv = g0.abs() < cfg.newton_tol
        e1 = torch.linalg.eigvals(_hgam(Ai, Di, gi_c + cfg.newton_h))
        a1, b1 = _track(e1, a0, b0)
        dg = ((a1 - b1) ** 2 - g0) / cfg.newton_h
        ok = (~conv) & (dg.abs() > 0) & torch.isfinite(dg.abs())
        step = torch.where(ok, g0 / torch.where(ok, dg, torch.ones_like(dg)), torch.zeros_like(g0))
        g_c[idx] = gi_c - step
        iters[idx] += 1
        still = ok & torch.isfinite(g_c[idx].abs())
        active[idx] = still
    ef = torch.linalg.eigvals(_hgam(A, D, g_c))
    af, bf = _track(ef, la, lb)
    resid = ((af - bf) ** 2).abs()
    # Walk deschis non-unitar la quasi-EP-ul real γ_q
    U = torch.linalg.matrix_exp(-1j * cfg.walk_dt * _hgam(A, D, gq.to(C128)))
    psi = torch.full((B, n), 1.0 / math.sqrt(n), dtype=C128, device=dev)
    for _ in range(cfg.walk_steps):
        psi = (U @ psi[..., None])[..., 0]
        psi = psi / torch.linalg.vector_norm(psi, dim=-1, keepdim=True)
    out = {"gamma_q": gq, "gap_q": gapmin[ar, gi], "ep_gamma": g_c, "ep_lambda": 0.5 * (af + bf),
           "ep_residual": resid, "ep_converged": resid < cfg.newton_tol, "ep_iters": iters,
           "ep_pair": torch.stack([ia, ib], 1), "psi_walk": psi.to(torch.complex64)}
    if details:
        out.update({"gamma_grid": gam, "gap_grid": gapmin, "spectrum_grid": ev, "spectrum_q": evq})
    return out


# ---------------------------------------------------------------------------
# O2 — volume de politop pozitiv (inspirat din Amplituhedron)
# ---------------------------------------------------------------------------
def op_amplituhedron(c, ew, T, n, details: bool = False) -> dict:
    B = c.shape[0]
    dev = c.device
    tri = triples(dev)
    I, J, L = tri["I"], tri["J"], tri["L"]
    cm = c.amax(-1, keepdim=True)
    em = ew.amax(-1, keepdim=True)
    z = torch.stack([torch.ones_like(c), torch.where(cm > 0, c / cm.clamp(min=1e-300), torch.zeros_like(c)),
                     torch.where(em > 0, ew / em.clamp(min=1e-300), torch.zeros_like(ew))], -1)   # [B,49,3]
    zi, zj, zl = z[:, I], z[:, J], z[:, L]
    vol = (zi * torch.linalg.cross(zj, zl, dim=-1)).sum(-1).abs()                                  # [B,18424]
    w = (T + 1.0) / (n[:, None] * P3 + 1.0)
    vw = vol * w
    V = torch.zeros(B, N, N, N, dtype=F64, device=dev)            # simetric, scriere fără acumulare
    for p, q, r in ((I, J, L), (I, L, J), (J, I, L), (J, L, I), (L, I, J), (L, J, I)):
        V[:, p, q, r] = vw
    a = V.sum((-1, -2)) / 2.0
    am = a.mean(-1, keepdim=True)
    a = torch.where(am > 0, a / am.clamp(min=1e-300), torch.ones_like(a))
    out = {"amp": a, "vol_total": vol.sum(-1)}
    if details:
        out["pair_scatter"] = V.sum(-1)                           # S_ij = Σ_l vol·w
        out["z"] = z
    return out


# ---------------------------------------------------------------------------
# O3 — disc Poincaré, ancore hiperbolice, curbură Forman
# ---------------------------------------------------------------------------
def poincare_dist(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    xx = (x * x).sum(-1)
    yy = (y * y).sum(-1)
    d2 = ((x - y) ** 2).sum(-1)
    arg = 1 + 2 * d2 / ((1 - xx) * (1 - yy))
    return torch.acosh(arg.clamp(min=1.0))


def op_poincare(C, n, A, cfg: Config = PROTOCOL) -> dict:
    B = C.shape[0]
    dev = C.device
    eye = torch.eye(N, dtype=torch.bool, device=dev)
    E = (n * P2)[:, None, None]
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
                r = torch.linalg.vector_norm(x, dim=-1, keepdim=True)
                x.mul_(torch.where(r > cfg.poincare_rmax, cfg.poincare_rmax / r, torch.ones_like(r)))
        x = x.detach()
    dh = poincare_dist(x[:, :, None], x[:, None]).masked_fill(eye, 0)
    stress = (((dh - delta) ** 2) * triu).sum((-1, -2))
    d0 = poincare_dist(x, torch.zeros_like(x))
    u = torch.exp(-d0)
    u = u / u.mean(-1, keepdim=True)
    order = torch.sort(u, dim=-1, descending=True, stable=True).indices
    anchors = order[:, : cfg.n_anchors] + 1
    # Curbură Forman descriptivă pe graful top-k vecini pozitivi
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


# ---------------------------------------------------------------------------
# O4 — Kuramoto cu salturi de interferență
# ---------------------------------------------------------------------------
def _wrap(x):
    return torch.atan2(torch.sin(x), torch.cos(x))


def kuramoto_coupling(A: torch.Tensor) -> torch.Tensor:
    W = A.clamp(min=0)
    m = W.sum(-1).amax(-1)
    return torch.where(m[:, None, None] > 0, W / m.clamp(min=1e-300)[:, None, None], torch.zeros_like(W))


def local_order(theta, W):
    cs, sn = torch.cos(theta), torch.sin(theta)
    rc = (W @ cs[..., None])[..., 0]
    rs = (W @ sn[..., None])[..., 0]
    rsum = W.sum(-1)
    return torch.where(rsum > 0, torch.sqrt(rc ** 2 + rs ** 2) / rsum.clamp(min=1e-300), torch.zeros_like(rsum))


def kuramoto_run(theta0, omega, W, cfg: Config = PROTOCOL, record_every: int = 0) -> dict:
    K, dt = cfg.kur_K, cfg.kur_dt

    def f(th):
        cs, sn = torch.cos(th), torch.sin(th)
        ws = (W @ sn[..., None])[..., 0]
        wc = (W @ cs[..., None])[..., 0]
        return omega + K * (cs * ws - sn * wc)

    th = theta0.clone()
    r_prev = local_order(th, W)
    spikes = torch.zeros_like(th)
    series = []
    for s in range(cfg.kur_steps):
        k1 = f(th)
        k2 = f(th + 0.5 * dt * k1)
        k3 = f(th + 0.5 * dt * k2)
        k4 = f(th + dt * k3)
        th = th + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        r_now = local_order(th, W)
        spk = (r_prev <= cfg.kur_spike) & (r_now > cfg.kur_spike)
        if bool(spk.any()):
            wr = _wrap(th[:, :, None] - th[:, None, :])            # [b,i,j] = wrap(θ_i − θ_j)
            jump = cfg.kur_jump * (spk.to(th.dtype)[:, :, None] * W * wr).sum(1)
            th = th + jump
            spikes = spikes + spk.to(th.dtype)
            r_now = local_order(th, W)
        r_prev = r_now
        if record_every and (s % record_every == 0 or s == cfg.kur_steps - 1):
            series.append(torch.abs(torch.exp(1j * th).mean(-1)))
    out = {"theta": torch.remainder(th, 2 * math.pi), "r_local": r_prev, "spikes": spikes,
           "R_global": torch.abs(torch.exp(1j * th).mean(-1))}
    if record_every:
        out["R_series"] = torch.stack(series, -1)
    return out


def op_kuramoto(A, c, gap, k, cfg: Config = PROTOCOL, record_every: int = 0) -> dict:
    kf = k.to(F64)[:, None]
    nu = kf / (c + 1.0)
    pos = nu > 0
    theta0 = torch.where(pos, torch.remainder(2 * math.pi * gap / nu.clamp(min=1e-300), 2 * math.pi), torch.zeros_like(nu))
    omega = torch.where(pos, 2 * math.pi / nu.clamp(min=1e-300), torch.zeros_like(nu))
    W = kuramoto_coupling(A)
    out = kuramoto_run(theta0, omega, W, cfg, record_every)
    out["W"] = W
    return out


# ---------------------------------------------------------------------------
# O5 — colaps Born + filtru Boltzmann pe 50 000 replici
# ---------------------------------------------------------------------------
def born_state(psi_walk, amp, u, theta, W, cfg: Config = PROTOCOL) -> dict:
    pw = psi_walk.to(C128)
    m = (pw.abs() ** 2) * amp * u
    m = m / m.sum(-1, keepdim=True)
    psi = torch.sqrt(m) * torch.exp(1j * (torch.angle(pw) + theta))
    Kphi = W.to(C128) * torch.exp(1j * (theta[:, :, None] - theta[:, None, :]))
    psi_f = psi + cfg.interference_eta * (Kphi @ psi[..., None])[..., 0]
    P = psi_f.abs() ** 2
    s = P.sum(-1, keepdim=True)
    P = torch.where(s > 0, P / s.clamp(min=1e-300), torch.full_like(P, 1.0 / N))
    return {"psi_f": psi_f, "P": P}


def boltzmann_filter(P: torch.Tensor, seeds: torch.Tensor, cfg: Config = PROTOCOL, chunk: int = 4) -> dict:
    B = P.shape[0]
    dev = P.device
    R = cfg.replicas
    beta = torch.logspace(cfg.beta_lo_exp, cfg.beta_hi_exp, R, dtype=F64, device=dev).to(torch.float32)
    logP = torch.log(P.clamp(min=1e-300))
    pis, cores = [], []
    ridx = torch.arange(R * N, device=dev, dtype=torch.int64)
    for s0 in range(0, B, chunk):
        sl = slice(s0, min(B, s0 + chunk))
        base = stream(seeds[sl].to(dev), TAG_BOLTZ)[:, None]          # [b,1]
        u1 = 1.0 - uniform(base, 2 * ridx[None])
        u2 = uniform(base, 2 * ridx[None] + 1)
        eps = (torch.sqrt(-2.0 * torch.log(u1)) * torch.cos(2 * math.pi * u2)).to(torch.float32).view(-1, R, N)
        del u1, u2
        logits = beta[None, :, None] * (logP[sl].to(torch.float32)[:, None, :] + cfg.noise_sigma * eps)
        pr = torch.softmax(logits, -1)
        pis.append(pr.to(F64).mean(1))
        top = logits.topk(K6, dim=-1).indices
        cnt = torch.zeros(top.shape[0], N, device=dev, dtype=F64)
        cnt.scatter_add_(1, top.reshape(top.shape[0], -1), torch.ones(top.shape[0], R * K6, device=dev, dtype=F64))
        cores.append(cnt / R)
        del eps, logits, pr, top
    pi = torch.cat(pis, 0)
    pi = pi / pi.sum(-1, keepdim=True)
    top_frac = torch.cat(cores, 0)
    return {"pi": pi, "top6_frac": top_frac, "core": top_frac >= cfg.core_frac}


# ---------------------------------------------------------------------------
# O6 — energie, Scutul Anti-Mulțime, MCMC paralel tempering, 3 variante
# ---------------------------------------------------------------------------
def crowd_penalty(S1: torch.Tensor) -> torch.Tensor:
    """S1: [...,6] numere 1..49 (orice ordine). Întoarce penalizarea euristică întreagă (float64)."""
    s = torch.sort(S1, dim=-1).values
    d = s[..., 1:] - s[..., :-1]
    low = (s[..., -1] <= 31)
    run3 = ((d[..., 1:] == 1) & (d[..., :-1] == 1)).any(-1)
    ap = (d == d[..., :1]).all(-1)
    digit = torch.remainder(s, 10)
    same = (digit[..., :, None] == digit[..., None, :]).sum(-1).amax(-1) >= 4
    return low.to(F64) + run3.to(F64) + ap.to(F64) + same.to(F64)


_PI = torch.tensor([p[0] for p in PAIR15])
_PJ = torch.tensor([p[1] for p in PAIR15])


FORBID_PENALTY = 1e6             # AMENDAMENT_02: interdicție tare pentru variante identice


def energy(S0: torch.Tensor, logpi: torch.Tensor, A: torch.Tensor, ov: torch.Tensor, cfg: Config,
           forbid: torch.Tensor | None = None) -> torch.Tensor:
    """S0: [B,C,6] indici 0..48; logpi [B,49]; A [B,49,49]; ov [B,49] (# variante anterioare);
    forbid [B,F] coduri ale variantelor anterioare (AMENDAMENT_02: identic ⇒ +1e6)."""
    B = S0.shape[0]
    bidx = torch.arange(B, device=S0.device)[:, None, None]
    e = -logpi.gather(1, S0.reshape(B, -1)).reshape(S0.shape).sum(-1)
    pi_, pj_ = _PI.to(S0.device), _PJ.to(S0.device)
    e = e - cfg.lam_pair * A[bidx, S0[..., pi_], S0[..., pj_]].sum(-1)
    if cfg.crowd_shield:
        e = e + cfg.mu_crowd * crowd_penalty(S0 + 1)
    e = e + cfg.mu_overlap * ov.gather(1, S0.reshape(B, -1)).reshape(S0.shape).sum(-1)
    if forbid is not None and forbid.shape[1] > 0:
        hit = (_code(S0)[..., None] == forbid[:, None, :]).any(-1)
        e = e + FORBID_PENALTY * hit.to(e.dtype)
    return e


def _code(S0):
    s = torch.sort(S0, dim=-1).values
    w = torch.tensor([50 ** (K6 - 1 - i) for i in range(K6)], dtype=torch.int64, device=S0.device)
    return (s * w).sum(-1)


def mcmc_variant(logpi, A, ov, seeds, cfg: Config = PROTOCOL, return_states: bool = False, forbid=None):
    """Paralel tempering Metropolis pe combinații de 6. Întoarce (cea mai bună combinație 1..49, energia);
    cu `return_states=True` întoarce și stările finale ale tuturor lanțurilor (pentru testul Boltzmann)."""
    B = logpi.shape[0]
    dev = logpi.device
    Tn, Cq = cfg.n_temps, cfg.chains_per_temp
    C = Tn * Cq
    temps = torch.logspace(math.log10(cfg.t_lo), math.log10(cfg.t_hi), Tn, dtype=F64, device=dev)
    tchain = temps.repeat_interleave(Cq)                              # [C]
    chain_ids = torch.arange(C, device=dev, dtype=torch.int64)
    base = splitmix(stream(seeds.to(dev), TAG_MCMC)[:, None] ^ chain_ids[None])     # [B,C]
    # inițializare: 6 numere distincte pe lanț (chei aleatoare → top-6)
    ib = splitmix(stream(seeds.to(dev), TAG_INIT)[:, None] ^ chain_ids[None])
    keys = uniform(ib[..., None], torch.arange(N, device=dev, dtype=torch.int64))
    S = keys.topk(K6, dim=-1).indices                                 # [B,C,6]
    mask = torch.zeros(B, C, N, dtype=torch.bool, device=dev)
    mask.scatter_(2, S, True)
    E = energy(S, logpi, A, ov, cfg, forbid)
    best_e = E.amin(1)
    cand = torch.where(E == best_e[:, None], _code(S), torch.full_like(_code(S), 1 << 62))
    bi = cand.argmin(1)
    best_s = S[torch.arange(B, device=dev), bi].clone()
    best_code = cand.gather(1, bi[:, None])[:, 0]
    sbase = splitmix(stream(seeds.to(dev), TAG_SWAP)[:, None] ^ torch.arange(Cq, device=dev)[None])   # [B,Cq]
    ar = torch.arange(B, device=dev)
    for it in range(cfg.mcmc_steps):
        cnt0 = 4 * it
        up = uniform(base, cnt0)
        ur = uniform(base, cnt0 + 1)
        ua = uniform(base, cnt0 + 2)
        p = (up * K6).floor().to(torch.int64).clamp(max=K6 - 1)
        r = (ur * (N - K6)).floor().to(torch.int64).clamp(max=N - K6 - 1)
        nonmem = ~mask
        cs = torch.cumsum(nonmem.to(torch.int64), -1)
        b = ((cs == (r + 1)[..., None]) & nonmem).to(torch.int8).argmax(-1)
        a = S.gather(2, p[..., None])[..., 0]
        Sn = S.scatter(2, p[..., None], b[..., None])
        En = energy(Sn, logpi, A, ov, cfg, forbid)
        acc = torch.log1p(-ua) < -(En - E) / tchain[None]
        S = torch.where(acc[..., None], Sn, S)
        E = torch.where(acc, En, E)
        accf = acc[..., None]
        mask.scatter_(2, a[..., None], mask.gather(2, a[..., None]) & ~accf)
        mask.scatter_(2, b[..., None], mask.gather(2, b[..., None]) | accf)
        # actualizare optim (ties: cod lexicografic minim)
        emin = E.amin(1)
        codes = _code(S)
        cand = torch.where(E == emin[:, None], codes, torch.full_like(codes, 1 << 62))
        ci = cand.argmin(1)
        cc = cand.gather(1, ci[:, None])[:, 0]
        better = (emin < best_e) | ((emin == best_e) & (cc < best_code))
        best_s = torch.where(better[:, None], S[ar, ci], best_s)
        best_e = torch.where(better, emin, best_e)
        best_code = torch.where(better, cc, best_code)
        if (it + 1) % cfg.swap_every == 0:
            par = ((it + 1) // cfg.swap_every) % 2
            Sv = S.view(B, Tn, Cq, K6)
            Ev = E.view(B, Tn, Cq)
            Mv = mask.view(B, Tn, Cq, N)
            for t in range(par, Tn - 1, 2):
                us = uniform(sbase, it * Tn + t)                      # [B,Cq]
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
            S, E, mask = Sv.reshape(B, C, K6), Ev.reshape(B, C), Mv.reshape(B, C, N)
    if return_states:
        return torch.sort(best_s, dim=-1).values + 1, best_e, torch.sort(S, dim=-1).values + 1, E
    return torch.sort(best_s, dim=-1).values + 1, best_e


def op_variants(logpi, A, seeds, cfg: Config = PROTOCOL) -> dict:
    B = logpi.shape[0]
    ov = torch.zeros(B, N, dtype=F64, device=logpi.device)
    forbid = torch.zeros(B, 0, dtype=torch.int64, device=logpi.device)
    vs, es = [], []
    for v in range(1, cfg.n_variants + 1):
        s, e = mcmc_variant(logpi, A, ov, seeds + v, cfg, forbid=forbid)
        vs.append(s)
        es.append(e)
        ov = ov.clone()
        ov.scatter_add_(1, s - 1, torch.ones(B, K6, dtype=F64, device=logpi.device))
        forbid = torch.cat([forbid, _code(s - 1)[:, None]], 1)
    return {"variants": torch.stack(vs, 1), "energies": torch.stack(es, 1)}


# ---------------------------------------------------------------------------
# Orchestrare
# ---------------------------------------------------------------------------
def score_steps(prefix: Prefix, ks: torch.Tensor, cfg: Config = PROTOCOL, details: bool = False,
                chunk: int = 64, timings: dict | None = None) -> dict:
    """O1–O5 pentru pașii ks: π_QL [B,49] și A [B,49,49] (+ detalii pentru UI)."""
    dev = prefix.device
    ks = ks.to(dev, torch.int64)
    outs: dict[str, list] = {}
    tm = timings if timings is not None else {}

    def tick(name, t0):
        if dev.type == "cuda":
            torch.cuda.synchronize()
        tm[name] = tm.get(name, 0.0) + time.perf_counter() - t0

    for s0 in range(0, ks.shape[0], chunk):
        kb = ks[s0:s0 + chunk]
        t0 = time.perf_counter()
        st = prefix.state(kb)
        A = pair_excess(st["C"], st["n"])
        D = dissipation(st["gap"])
        tick("state", t0)
        t0 = time.perf_counter()
        o1 = op_nonhermitian(A, D, cfg, details)
        tick("O1_nonhermitian_EP", t0)
        t0 = time.perf_counter()
        o2 = op_amplituhedron(st["c"], st["ew"], st["T"], st["n"], details)
        tick("O2_amplituhedron", t0)
        t0 = time.perf_counter()
        o3 = op_poincare(st["C"], st["n"], A, cfg)
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
        bf = boltzmann_filter(o5["P"], step_seed(cfg, kb), cfg)
        tick("O5_born_boltzmann", t0)
        rec = {"pi": bf["pi"], "A": A, "P": o5["P"], "gamma_q": o1["gamma_q"], "ep_gamma": o1["ep_gamma"],
               "ep_converged": o1["ep_converged"], "anchors": o3["anchors"], "core": bf["core"]}
        if details:
            rec.update({"psi_f": o5["psi_f"], "top6_frac": bf["top6_frac"], "o1": o1, "o2": o2, "o3": o3, "o4": o4,
                        "D": D, "state": st})
        for kk, vv in rec.items():
            outs.setdefault(kk, []).append(vv)
    res = {}
    for kk, vv in outs.items():
        res[kk] = torch.cat(vv, 0) if torch.is_tensor(vv[0]) else vv
    return res


def variants_steps(pi: torch.Tensor, A: torch.Tensor, ks: torch.Tensor, cfg: Config = PROTOCOL, chunk: int = 1024) -> dict:
    outs_v, outs_e = [], []
    logpi = torch.log(pi.clamp(min=1e-300))
    for s0 in range(0, pi.shape[0], chunk):
        sl = slice(s0, s0 + chunk)
        o = op_variants(logpi[sl], A[sl], step_seed(cfg, ks[sl].to(pi.device)), cfg)
        outs_v.append(o["variants"])
        outs_e.append(o["energies"])
    return {"variants": torch.cat(outs_v, 0), "energies": torch.cat(outs_e, 0)}


def _vram() -> dict:
    if not torch.cuda.is_available():
        return {"allocated_mib": 0.0, "peak_mib": 0.0, "total_mib": 0.0}
    return {"allocated_mib": torch.cuda.memory_allocated() / 2 ** 20,
            "peak_mib": torch.cuda.max_memory_allocated() / 2 ** 20,
            "total_mib": torch.cuda.get_device_properties(0).total_memory / 2 ** 20}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_full(ds: Dataset | None = None, cfg: Config = PROTOCOL, device=None, k: int | None = None) -> dict:
    """Produsul: toți operatorii la pasul k (implicit K = toată istoria → extragerea următoare)."""
    t_all = time.perf_counter()
    dev = resolve_device() if device is None else torch.device(device)
    if ds is None:
        ds = build_dataset(DEFAULT_SOURCE, dev)
    if torch.cuda.is_available() and dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    prefix = Prefix(ds, cfg, dev)
    kk = ds.n_steps if k is None else int(k)
    ks = torch.tensor([kk], dtype=torch.int64, device=dev)
    timings: dict = {}
    sc = score_steps(prefix, ks, cfg, details=True, timings=timings)
    t0 = time.perf_counter()
    vv = variants_steps(sc["pi"], sc["A"], ks, cfg)
    if dev.type == "cuda":
        torch.cuda.synchronize()
    timings["O6_mcmc_qubo"] = time.perf_counter() - t0
    o1, o2, o3, o4 = sc["o1"][0], sc["o2"][0], sc["o3"][0], sc["o4"][0]
    st = sc["state"][0]
    A = sc["A"][0]
    tri = torch.triu_indices(N, N, 1, device=dev)
    ps = o2["pair_scatter"][0][tri[0], tri[1]]
    top_pairs = torch.sort(ps, descending=True, stable=True).indices[:15]
    proto_path = ROOT / "PREINREGISTRARE_QL649.md"
    res = {
        "k": kk, "n_draws_used": int(st["n"][0].item()), "n_steps": ds.n_steps,
        "last_date": ds.step_dates[-1] if ds.step_dates else None,
        "device": str(dev), "config_digest": cfg.digest(), "is_protocol": cfg.is_protocol(),
        "protocol_sha256": sha256_file(proto_path) if proto_path.exists() else None,
        "source_sha256": ds.source_sha256,
        "pi": sc["pi"][0], "P": sc["P"][0], "psi_f": sc["psi_f"][0], "core": sc["core"][0],
        "top6_frac": sc["top6_frac"][0], "A": A,
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
    }
    return res


if __name__ == "__main__":
    out = run_full()
    show = {k: v for k, v in out.items() if not torch.is_tensor(v)}
    print(json.dumps(show, indent=2, default=str))
