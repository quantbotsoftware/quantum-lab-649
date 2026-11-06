"""TU4-IP (S11): nucleul celor 3 ipoteze fizice — legea Fisher, eșantionare exactă, modelele H1/H2/H3, factorul e.

Protocol: tu4/PROTOCOL_TU4_IP.md + PROTOCOL_TU4_IP_H{1_MA,2_UZ,3_AD}.md, sigiliu tu4/SIGILIU_TU4_IP.json (21:16:29Z),
scrise ÎNAINTE de acest cod. Calcul clasic float64 (CPU/GPU). Fără popularitate, fără arhiva reală, fără LQG/WZW.
"""
from __future__ import annotations

import math

import numpy as np
import torch

DT = torch.float64
GAMES = {
    "649": dict(n=49, k=6, b=6, T=2595, D=0.04642096912015248, ball=None),
    "540": dict(n=40, k=6, b=5, T=2490, D=0.035248076774104575, ball=None),
    "joker": dict(n=45, k=5, b=5, T=2202, D=0.0517260340859611, ball=dict(n=20, k=1, D=0.019984140068430675)),
}
H = 520
LN_THR = math.log(900.0)
RHO = 2.0 ** (-1.0 / 312.0)
K_AD = 4
R = 1000
SEED_BASE = 2026102711
GAME_IDX = {"649": 0, "540": 1, "joker": 2}
CELL_IDX = {"U": 0, "A1": 1, "A2": 2, "A3": 3}
MODELS = ("H1", "H2", "H3")
COMPILE_MODE = "max-autotune-no-cudagraphs"   # "max-autotune-no-break" nu există în PyTorch 2.11 (protocol §0)
OU_GRID = 5


def seed_of(game: str, cell: str) -> int:
    return SEED_BASE + 100 * GAME_IDX[game] + CELL_IDX[cell]


def log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def dct_basis(n: int, K: int = K_AD, device="cpu") -> torch.Tensor:
    """b_m(i) = sqrt(2/n) cos(pi m (i - 1/2) / n), i = 1..n, m = 1..K  -> (n, K)."""
    i = torch.arange(1, n + 1, dtype=DT, device=device)[:, None]
    m = torch.arange(1, K + 1, dtype=DT, device=device)[None, :]
    return math.sqrt(2.0 / n) * torch.cos(math.pi * m * (i - 0.5) / n)


# ---------------------------------------------------------------- legea Fisher (Poisson condiționat)
def esp(w: torch.Tensor, k: int) -> torch.Tensor:
    """e_0..e_k(w) pe ultima axă: (..., n) -> (..., k+1)."""
    e = [torch.ones(w.shape[:-1], dtype=w.dtype, device=w.device)]
    e += [torch.zeros(w.shape[:-1], dtype=w.dtype, device=w.device) for _ in range(k)]
    for i in range(w.shape[-1]):
        wi = w[..., i]
        for j in range(k, 0, -1):
            e[j] = e[j] + wi * e[j - 1]
    return torch.stack(e, -1)


def info_D(logw: torch.Tensor, k: int) -> torch.Tensor:
    """D(w) = KL(P_w || U) exact: sum pi_i ln w_i - ln e_k(w) + ln C(n,k)."""
    n = logw.shape[-1]
    w = torch.exp(logw)
    e = esp(w, k)
    em = torch.ones_like(w)                     # e_0(w_{-i})
    for j in range(1, k):
        em = e[..., j:j + 1] - w * em           # e_j(w_{-i})
    pi = w * em / e[..., k:k + 1]
    return (pi * logw).sum(-1) - torch.log(e[..., k]) + log_comb(n, k)


def _log_e_factor(logw: torch.Tensor, x: torch.Tensor, k: int, lc: float) -> torch.Tensor:
    w = torch.exp(logw)
    e = [torch.ones_like(w[:, 0])] + [torch.zeros_like(w[:, 0]) for _ in range(k)]
    for i in range(w.shape[1]):
        wi = w[:, i]
        for j in range(k, 0, -1):
            e[j] = e[j] + wi * e[j - 1]
    return (x * logw).sum(1) - torch.log(e[k]) + lc


_KERNELS: dict = {}
COMPILE_STATUS: dict = {}


def kernel(n: int, k: int, compiled: bool = True):
    """Factorul e: ln e = sum_{i in S} ln w_i - ln e_k(w) + ln C(n,k), pe loturi (B, n)."""
    key = (n, k, compiled)
    if key not in _KERNELS:
        lc = log_comb(n, k)

        def f(logw, x):
            return _log_e_factor(logw, x, k, lc)
        if compiled:
            try:
                _KERNELS[key] = torch.compile(f, mode=COMPILE_MODE, fullgraph=True, dynamic=False)
                COMPILE_STATUS[f"{n}_{k}"] = "compiled:" + COMPILE_MODE
            except Exception as exc:  # declarat (protocol §0)
                _KERNELS[key] = f
                COMPILE_STATUS[f"{n}_{k}"] = "eager_fallback:" + repr(exc)[:200]
        else:
            _KERNELS[key] = f
    return _KERNELS[key]


def run_kernel(n, k, logw, x, compiled=True):
    fn = kernel(n, k, compiled)
    try:
        return fn(logw, x)
    except Exception as exc:  # eșec la prima execuție a nucleului compilat => eager, declarat
        if compiled:
            COMPILE_STATUS[f"{n}_{k}"] = "eager_fallback_runtime:" + repr(exc)[:200]
            _KERNELS[(n, k, True)] = kernel(n, k, False)
            return _KERNELS[(n, k, True)](logw, x)
        raise


# ---------------------------------------------------------------- modelele (ln ŵ din statistici)
def theta_x2(c, N, N2, n, k):
    p = k / n
    th = (n - 1) / n * (c / N[..., None] - p) / (p * (1 - p))
    x2 = (n - 1) / n * ((c - N[..., None] * p) ** 2).sum(-1) / (N2 * p * (1 - p))
    return th, x2


def logw_h1(c, N, n, k):
    th, x2 = theta_x2(c, N, N, n, k)
    lam = torch.clamp(1.0 - (n - 3) / x2, min=0.0)
    return lam[..., None] * th, lam


def logw_h2(ct, Nt, N2t, n, k):
    th, x2 = theta_x2(ct, Nt, N2t, n, k)
    lam = torch.clamp(1.0 - (n - 3) / x2, min=0.0)
    return lam[..., None] * th, lam


def logw_h3(c, N, n, k, B):
    p = k / n
    z = math.sqrt((n - 1) / n) * (c - N[..., None] * p) / torch.sqrt(N[..., None] * p * (1 - p))
    x2s = ((z @ B) ** 2).sum(-1)
    th, _ = theta_x2(c, N, N, n, k)
    ths = (th @ B) @ B.T
    lam = torch.clamp(1.0 - (B.shape[1] - 2) / x2s, min=0.0)
    return lam[..., None] * ths, lam


def disc_N(m: int, rho: float = RHO):
    """Ñ = sum_{a<m} rho^a, N2 = sum_{a<m} rho^{2a}."""
    return (1 - rho ** m) / (1 - rho), (1 - rho ** (2 * m)) / (1 - rho ** 2)


def model_logw_all(Xa: torch.Tensor, Xf: torch.Tensor, n: int, k: int, B: torch.Tensor):
    """Xa (W, T, n), Xf (W, H, n) float64 {0,1}. Întoarce dict model -> ln ŵ (W, H, n) folosind NUMAI extragerile < t."""
    W, T, _ = Xa.shape
    Hh = Xf.shape[1]
    dev = Xa.device
    t = torch.arange(Hh, dtype=DT, device=dev)                       # t-1 = 0..H-1
    cum = torch.cumsum(Xf, 1)
    prev = torch.cat([torch.zeros_like(cum[:, :1]), cum[:, :-1]], 1)  # numărările viitoare < t
    C = Xa.sum(1)[:, None, :] + prev
    N = (T + t)[None, :].expand(W, Hh)
    out = {"H1": logw_h1(C, N, n, k)[0], "H3": logw_h3(C, N, n, k, B)[0]}
    ages = torch.arange(T - 1, -1, -1, dtype=DT, device=dev)          # vârsta arhivei la t = 1
    c1 = torch.einsum("wtn,t->wn", Xa, RHO ** ages)
    s = torch.arange(1, Hh + 1, dtype=DT, device=dev)
    Z = torch.cumsum(Xf * (RHO ** (-s))[None, :, None], 1)
    Zp = torch.cat([torch.zeros_like(Z[:, :1]), Z[:, :-1]], 1)
    ct = (RHO ** t)[None, :, None] * (c1[:, None, :] + Zp)
    m = T + t                                                        # numărul extragerilor < t
    Nt = ((1 - RHO ** m) / (1 - RHO))[None, :].expand(W, Hh)
    N2t = ((1 - RHO ** (2 * m)) / (1 - RHO ** 2))[None, :].expand(W, Hh)
    out["H2"] = logw_h2(ct, Nt, N2t, n, k)[0]
    return out


def log_e_all(Xa, Xf, n, k, B, compiled=True):
    """dict model -> ln e_t (W, H)."""
    lw = model_logw_all(Xa, Xf, n, k, B)
    W, Hh, _ = Xf.shape
    xf = Xf.reshape(W * Hh, n).contiguous()
    return {m: run_kernel(n, k, lw[m].reshape(W * Hh, n).contiguous(), xf, compiled).reshape(W, Hh) for m in MODELS}


def summarize(le: torch.Tensor):
    """ln E traiectorie -> (final, max, primul t (1-bazat) cu ln E >= ln 900 sau 0)."""
    L = torch.cumsum(le, 1)
    hit = L >= LN_THR
    first = torch.where(hit.any(1), hit.float().argmax(1) + 1, torch.zeros_like(hit[:, 0], dtype=torch.long))
    return L[:, -1], L.max(1).values, first


# ---------------------------------------------------------------- eșantionare exactă din P_w
def suffix_tables(w: torch.Tensor, k: int) -> torch.Tensor:
    """w (..., n) -> E (..., n+1, k+1), E[..., i, r] = e_r(w_i..w_{n-1})."""
    n = w.shape[-1]
    E = torch.zeros(w.shape[:-1] + (n + 1, k + 1), dtype=w.dtype, device=w.device)
    E[..., n, 0] = 1.0
    for i in range(n - 1, -1, -1):
        E[..., i, 0] = 1.0
        E[..., i, 1:] = E[..., i + 1, 1:] + w[..., i, None] * E[..., i + 1, :-1]
    return E


def sample_cp(logw: torch.Tensor, k: int, Tn: int, gen: torch.Generator) -> torch.Tensor:
    """logw (W, n) fix sau (W, Tn, n) variabil în timp -> indicatori uint8 (W, Tn, n), exact din P_w."""
    W = logw.shape[0]
    n = logw.shape[-1]
    dev = logw.device
    w = torch.exp(logw)
    E = suffix_tables(w, k)
    if logw.dim() == 2:
        E = E[:, None].expand(W, Tn, n + 1, k + 1)
        w = w[:, None, :].expand(W, Tn, n)
    r = torch.full((W, Tn), k, dtype=torch.long, device=dev)
    X = torch.zeros((W, Tn, n), dtype=torch.uint8, device=dev)
    for i in range(n):
        Ei1 = E[:, :, i + 1, :]
        Ei = E[:, :, i, :]
        num = w[:, :, i] * torch.gather(Ei1, 2, (r - 1).clamp(min=0)[..., None])[..., 0]
        den = torch.gather(Ei, 2, r[..., None])[..., 0]
        p = torch.where(r > 0, num / den, torch.zeros_like(num))
        u = torch.rand((W, Tn), dtype=DT, device=dev, generator=gen)
        take = u < p
        X[:, :, i] = take.to(torch.uint8)
        r = r - take.long()
    assert bool((r == 0).all()), "eșantionare: locuri rămase"
    return X


def unit_dirs(W: int, n: int, gen: torch.Generator, dev) -> torch.Tensor:
    v = torch.randn((W, n), dtype=DT, device=dev, generator=gen)
    v = v - v.mean(1, keepdim=True)
    return v / v.norm(dim=1, keepdim=True)


def smooth_dirs(W: int, n: int, gen: torch.Generator, dev) -> torch.Tensor:
    a = torch.randn((W, K_AD), dtype=DT, device=dev, generator=gen)
    a = a / a.norm(dim=1, keepdim=True)
    return a @ dct_basis(n, K_AD, dev).T


def ou_paths(W: int, Tn: int, n: int, gen: torch.Generator, dev) -> torch.Tensor:
    phi = RHO
    eta = torch.randn((W, Tn, n), dtype=DT, device=dev, generator=gen)
    eta = eta - eta.mean(2, keepdim=True)
    x = torch.empty_like(eta)
    x[:, 0] = eta[:, 0]
    s = math.sqrt(1 - phi * phi)
    for t in range(1, Tn):
        x[:, t] = phi * x[:, t - 1] + s * eta[:, t]
    return x


def calibrate(dirs: torch.Tensor, k: int, D: float, iters: int = 60) -> torch.Tensor:
    """eps > 0 pe lume cu D(eps*dir) = D (dirs (W, n)) sau media pe grilă = D (dirs (W, G, n))."""
    def f(eps):
        if dirs.dim() == 2:
            return info_D(eps[:, None] * dirs, k)
        return info_D(eps[:, None, None] * dirs, k).mean(1)
    W = dirs.shape[0]
    lo = torch.zeros(W, dtype=DT, device=dirs.device)
    hi = torch.ones(W, dtype=DT, device=dirs.device)
    for _ in range(80):
        bad = f(hi) <= D
        if not bool(bad.any()):
            break
        hi = torch.where(bad, hi * 2, hi)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        up = f(mid) > D
        hi = torch.where(up, mid, hi)
        lo = torch.where(up, lo, mid)
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------- fixturile (CPU, float64)
def ticket(logw: np.ndarray, b: int) -> list:
    order = np.argsort(-np.asarray(logw), kind="stable")
    return sorted(int(i) + 1 for i in order[:b])


def _t(a):
    return torch.as_tensor(np.asarray(a, float), dtype=DT)


def lw_h1_np(c, N, n, k):
    lw, lam = logw_h1(_t(c)[None], _t([N]), n, k)
    return lw[0].numpy(), float(lam[0])


def lw_h2_np(ct, Nt, N2t, n, k):
    lw, lam = logw_h2(_t(ct)[None], _t([Nt]), _t([N2t]), n, k)
    return lw[0].numpy(), float(lam[0])


def lw_h3_np(c, N, n, k):
    lw, lam = logw_h3(_t(c)[None], _t([N]), n, k, dct_basis(n))
    return lw[0].numpy(), float(lam[0])


def lw_b_np(c, N, n, k):
    p = k / n
    th = (n - 1) / n * (np.asarray(c) / N - p) / (p * (1 - p))
    return th


def D_np(lw, k):
    return float(info_D(_t(lw)[None], k)[0])


def scale_to_x2(direction: np.ndarray, N: float, n: int, k: int, x2: float) -> np.ndarray:
    """c = Np + gamma*direction cu X²(c) = x2 (direction centrat)."""
    p = k / n
    gam = math.sqrt(x2 * N * p * (1 - p) * n / ((n - 1) * float(np.dot(direction, direction))))
    return N * p + gam * direction


def fixtures() -> dict:
    n, k, N, b = 49, 6, 2595, 6
    p = k / n
    i = np.arange(1, n + 1)
    v = ((5 * i) % 49 - 24).astype(float)
    top_v = sorted(int(x) for x in i[np.argsort(-v, kind="stable")[:b]])
    top_mv = sorted(int(x) for x in i[np.argsort(v, kind="stable")[:b]])
    out = {}
    # F1 / I1
    for name, x2, in (("F1", 50.0), ("I1", 400.0)):
        c = scale_to_x2(v, N, n, k, x2)
        lw1, lam1 = lw_h1_np(c, N, n, k)
        lwB = lw_b_np(c, N, n, k)
        d1, dB = D_np(lw1, k), D_np(lwB, k)
        rec = {"X2": x2, "lambda_H1": lam1, "D_H1": d1, "D_B": dB, "ratio": d1 / dB, "ticket_H1": ticket(lw1, b),
               "top_v": top_v}
        if name == "F1":
            rec["pass"] = bool(d1 <= 0.1 * dB and ticket(lw1, b) == top_v)
        else:
            rec["pass"] = bool(lam1 >= 0.85 and d1 >= 0.5 * dB)
        out[name] = rec
    # F2 / I2 (blocuri, numărări așteptate)
    vh = v / np.linalg.norm(v)
    a = math.sqrt(300 * p * (1 - p) * n / ((n - 1) * 2295))
    Nt, N2t = disc_N(N)

    def wsum(a0, a1):  # sum_{age=a0}^{a1-1} rho^age
        return (RHO ** a0 - RHO ** a1) / (1 - RHO)

    def hist(blocks):  # blocks: list of (dev_vector, age0, age1)
        c = np.zeros(n)
        ct = np.zeros(n)
        for dev, a0, a1 in blocks:
            c += (p + dev) * (a1 - a0)
            ct += (p + dev) * wsum(a0, a1)
        return c, ct
    cA, ctA = hist([(a * vh, 300, 2595), (-4 * a * vh, 0, 300)])
    cB, ctB = hist([(-4 * a * vh, 2295, 2595), (a * vh, 0, 2295)])
    lw1A, l1A = lw_h1_np(cA, N, n, k)
    lw2A, l2A = lw_h2_np(ctA, Nt, N2t, n, k)
    lw1B, _ = lw_h1_np(cB, N, n, k)
    lw2B, l2B = lw_h2_np(ctB, Nt, N2t, n, k)
    out["F2"] = {"lambda_H1": l1A, "lambda_H2": l2A, "ticket_H1": ticket(lw1A, b), "ticket_H2": ticket(lw2A, b),
                 "top_v": top_v, "top_minus_v": top_mv,
                 "pass": bool(l1A > 0 and l2A > 0 and ticket(lw1A, b) == top_v and ticket(lw2A, b) == top_mv)}
    dlw = float(np.max(np.abs(lw1A - lw1B)))
    out["I2"] = {"max_abs_dlogw_H1": dlw, "ticket_H2_A": ticket(lw2A, b), "ticket_H2_Aprime": ticket(lw2B, b),
                 "lambda_H2_Aprime": l2B, "pass": bool(dlw <= 1e-12 and ticket(lw2A, b) != ticket(lw2B, b))}
    # F3 / I3
    g = math.sqrt(2.0) * np.cos(np.pi * (i - 0.5) / n)
    V = [15, 20, 25, 30, 35, 40]
    h = np.full(n, -18.0 / 43.0)
    h[np.array(V) - 1] = 3.0
    c = scale_to_x2(g + h, N, n, k, 400.0)
    lw1, _ = lw_h1_np(c, N, n, k)
    lw3, l3 = lw_h3_np(c, N, n, k)
    t3 = ticket(lw3, b)
    contig = t3 == list(range(t3[0], t3[0] + b))
    out["F3"] = {"lambda_H3": l3, "ticket_H1": ticket(lw1, b), "ticket_H3": t3, "V": V, "contiguous": bool(contig),
                 "pass": bool(ticket(lw1, b) == V and l3 > 0 and contig and not set(t3) & set(V))}
    c0 = scale_to_x2(g, N, n, k, 100.0)
    sig = (5 * i) % 49          # sigma(i) - 1 (0-bazat)
    cp = np.empty(n)
    cp[sig] = c0
    d1a, d1b = D_np(lw_h1_np(c0, N, n, k)[0], k), D_np(lw_h1_np(cp, N, n, k)[0], k)
    d3a, d3b = D_np(lw_h3_np(c0, N, n, k)[0], k), D_np(lw_h3_np(cp, N, n, k)[0], k)
    out["I3"] = {"D_H1_c": d1a, "D_H1_cperm": d1b, "D_H3_c": d3a, "D_H3_cperm": d3b,
                 "ratio_H3": d3a / d3b if d3b > 0 else float("inf"),
                 "pass": bool(abs(d1a - d1b) <= 1e-12 and d3a >= 10 * d3b)}
    return out
