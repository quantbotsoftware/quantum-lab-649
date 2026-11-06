"""TU3 — modulul J: sistemul bipartit Joker (H_Main ⊗ H_Joker) pe CUDA.

Implementează EXACT definițiile din `PROTOCOL_TU3_P1.md` §2 (sigilat 15:43:01Z, sha `694d3545…6b04`),
cu clarificările `AMENDAMENT_TU3_01.md` (W9, L_A) și `AMENDAMENT_TU3_02.md` (sub-pași RK4).

Calcul CLASIC în float64 (PyTorch; CUDA implicit, fallback CPU jurnalizat). „Stare”, „entanglement”,
„holonomie”, „rupere de simetrie” sunt vocabular matematic aplicat tabelei de co-apariție main × Joker;
nicio pretenție fizică și niciun avantaj predictiv (positive_claims_allowed=false).

Convenții: indicii interni sunt 0-based (nodul principal j = 0..44 ↔ numărul j+1; Joker a = 0..19 ↔ a+1).
Toate funcțiile acceptă un lot B de universuri (prima dimensiune).
"""
from __future__ import annotations

import logging
import math

import torch

LOG = logging.getLogger("tu3.joker")

F64 = torch.float64
C128 = torch.complex128

N_MAIN = 45          # urna principală 5/45
M_JOKER = 20         # urna Joker 1/20
K_MAIN = 5
ETA = 0.5            # = interference_eta QL649 (P1 §2.5)
FORMAN_K = 6         # = forman_k QL649 (P1 §2.6)
KUR_KM = 2.0         # = kur_K QL649 (P1 §2.7)
KUR_DT = 0.05
KUR_STEPS = 400
LOCK_TOL = 1e-3      # |dθ/dt| < 1e-3 ⇒ blocat (P1 §2.7)
SUBSTEP_TARGET = 0.5  # AMENDAMENT_TU3_02: dt_sub·L ≤ 0.5
BETA_SYNTH = 1.0     # P1 §4

DEVICE_EVENTS: list[str] = []


def resolve_device(prefer: str = "cuda") -> torch.device:
    """CUDA implicit; CPU numai dacă CUDA lipsește/eșuează (eveniment jurnalizat în DEVICE_EVENTS)."""
    if prefer == "cpu":
        return torch.device("cpu")
    try:
        if not torch.cuda.is_available():
            raise RuntimeError("torch.cuda.is_available() == False")
        dev = torch.device("cuda")
        probe = torch.ones(8, device=dev, dtype=F64)
        if float(probe.sum().item()) != 8.0:
            raise RuntimeError("CUDA probe mismatch")
        return dev
    except Exception as exc:  # pragma: no cover - depinde de mediu
        msg = f"CUDA indisponibil, fallback CPU: {type(exc).__name__}: {exc}"
        DEVICE_EVENTS.append(msg)
        LOG.warning(msg)
        return torch.device("cpu")


def kappa_grid(device=None) -> torch.Tensor:
    """κ̃ ∈ logspace(−1, 2, 31) (P1 §2.7)."""
    return torch.logspace(-1.0, 2.0, 31, dtype=F64, device=device)


# ---------------------------------------------------------------------------
# Validare și tensorul comun P (P1 §2.1)
# ---------------------------------------------------------------------------
def validate_draws(main: torch.Tensor, joker: torch.Tensor, n: int = N_MAIN, m: int = M_JOKER,
                   k: int = K_MAIN) -> None:
    """main: [T,k] sau [B,T,k] cu numere 1..n distincte pe rând; joker: [T] sau [B,T] cu 1..m."""
    if main.shape[-1] != k:
        raise ValueError(f"fiecare extragere principală trebuie să aibă {k} numere, nu {main.shape[-1]}")
    if main.shape[:-1] != joker.shape:
        raise ValueError(f"forme incompatibile main {tuple(main.shape)} / joker {tuple(joker.shape)}")
    if main.numel() and (int(main.min()) < 1 or int(main.max()) > n):
        raise ValueError(f"numere principale în afara 1..{n}")
    if joker.numel() and (int(joker.min()) < 1 or int(joker.max()) > m):
        raise ValueError(f"Joker în afara 1..{m}")
    s = torch.sort(main, dim=-1).values
    if bool((s[..., 1:] == s[..., :-1]).any()):
        raise ValueError("numere principale repetate în aceeași extragere")


def joint_counts(main0: torch.Tensor, joker0: torch.Tensor, n: int = N_MAIN, m: int = M_JOKER) -> torch.Tensor:
    """Numărări de co-apariție [B,n,m] din indici 0-based (main0 [B,T,k], joker0 [B,T]) prin bincount pe GPU."""
    if main0.dim() == 2:
        main0, joker0 = main0[None], joker0[None]
    B = main0.shape[0]
    b = torch.arange(B, device=main0.device, dtype=torch.long)[:, None, None]
    flat = b * (n * m) + main0.long() * m + joker0.long()[..., None]
    cnt = torch.bincount(flat.reshape(-1), minlength=B * n * m)
    return cnt.reshape(B, n, m).to(F64)


def joint_counts_onehot(main0: torch.Tensor, joker0: torch.Tensor, n: int = N_MAIN, m: int = M_JOKER) -> torch.Tensor:
    """Aceleași numărări prin one-hot + einsum (referință pentru martorul W7)."""
    if main0.dim() == 2:
        main0, joker0 = main0[None], joker0[None]
    X = torch.zeros(*main0.shape[:2], n, dtype=F64, device=main0.device)
    X.scatter_(2, main0.long(), 1.0)
    Y = torch.nn.functional.one_hot(joker0.long(), m).to(F64)
    return torch.einsum("btj,bta->bja", X, Y)


def onehots(main0: torch.Tensor, joker0: torch.Tensor, n: int = N_MAIN, m: int = M_JOKER):
    X = torch.zeros(*main0.shape[:-1], n, dtype=F64, device=main0.device)
    X.scatter_(-1, main0.long(), 1.0)
    Y = torch.nn.functional.one_hot(joker0.long(), m).to(F64)
    return X, Y


def joint_tensor(counts: torch.Tensor):
    """P = counts / Σcounts (= Σ X Y /(kT)); p = P·1, q = Pᵀ·1."""
    P = counts / counts.sum((-1, -2), keepdim=True)
    return P, P.sum(-1), P.sum(-2)


# ---------------------------------------------------------------------------
# Cross-covarianță și starea bipartită (P1 §2.2–2.3)
# ---------------------------------------------------------------------------
def cross_covariance(P, p, q):
    C = P - p[..., :, None] * q[..., None, :]
    den = torch.sqrt(p[..., :, None] * q[..., None, :])
    Kt = torch.where(den > 0, C / den.clamp(min=1e-300), torch.zeros_like(C))
    return C, Kt


def schmidt(P):
    """Coeficienții Schmidt ai |Ψ⟩ = Σ √P_ja |j⟩|a⟩ (SVD batch), S_E și numărul Schmidt."""
    s = torch.linalg.svdvals(torch.sqrt(P))
    s2 = s * s
    s2 = s2 / s2.sum(-1, keepdim=True)
    S_E = -torch.special.xlogy(s2, s2).sum(-1)
    K_S = 1.0 / (s2 * s2).sum(-1)
    return s, S_E, K_S


def mutual_information(P, p, q):
    pq = p[..., :, None] * q[..., None, :]
    ratio = torch.where(P > 0, P / pq.clamp(min=1e-300), torch.ones_like(P))
    return torch.special.xlogy(P, ratio).sum((-1, -2))


# ---------------------------------------------------------------------------
# Holonomia Joker și ruperea de simetrie (P1 §2.4)
# ---------------------------------------------------------------------------
def joker_phases(m: int = M_JOKER, device=None) -> torch.Tensor:
    return 2 * math.pi * torch.arange(m, dtype=F64, device=device) / m


def holonomy(P, p, q, C, n_j):
    m = P.shape[-1]
    e = torch.exp(1j * joker_phases(m, P.device)).to(C128)
    pos = p > 0
    pc = p.clamp(min=1e-300).to(C128)
    h = torch.where(pos, (P.to(C128) @ e) / pc, torch.zeros((), dtype=C128, device=P.device))
    D = torch.where(pos, (C.to(C128) @ e) / pc, torch.zeros((), dtype=C128, device=P.device))
    a = D.abs()
    theta = torch.where(pos, torch.angle(h), torch.zeros_like(p))
    vartheta = torch.where(a > 0, torch.angle(D), torch.zeros_like(a))
    Phi = (p * a * a).sum(-1)
    Z = n_j * a * a
    return {"h": h, "theta": theta, "r": h.abs(), "Delta": D, "absDelta": a, "vartheta": vartheta,
            "Phi": Phi, "Z": Z}


# ---------------------------------------------------------------------------
# Câmpul urnei principale (P1 §2.5)
# ---------------------------------------------------------------------------
def main_field(p, vartheta, Kt, eta: float = ETA):
    psi = torch.sqrt(p).to(C128) * torch.exp(1j * vartheta.to(C128))
    interference = 2 * torch.real(psi[..., :, None] * psi.conj()[..., None, :])
    G = Kt @ Kt.transpose(-1, -2)
    G = G - torch.diag_embed(torch.diagonal(G, dim1=-2, dim2=-1))
    rs = G.abs().sum(-1).amax(-1, keepdim=True)[..., None]
    Gh = torch.where(rs > 0, G / rs.clamp(min=1e-300), torch.zeros_like(G))
    psi_f = psi + eta * (Gh.to(C128) @ psi[..., None])[..., 0]
    PB = psi_f.abs() ** 2
    s = PB.sum(-1, keepdim=True)
    PB = torch.where(s > 0, PB / s.clamp(min=1e-300), torch.full_like(PB, 1.0 / PB.shape[-1]))
    return {"psi": psi, "interference": interference, "G": G, "G_hat": Gh, "psi_f": psi_f, "P_born": PB}


# ---------------------------------------------------------------------------
# Disc Poincaré, δ-Gromov, Forman (P1 §2.6)
# ---------------------------------------------------------------------------
def poincare_dist(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    xx = (x * x).sum(-1)
    yy = (y * y).sum(-1)
    d2 = ((x - y) ** 2).sum(-1)
    arg = 1 + 2 * d2 / ((1 - xx) * (1 - yy))
    return torch.acosh(arg.clamp(min=1.0))


def poincare_embed(Z, vartheta):
    rho = torch.log1p(Z)
    r = torch.tanh(rho / 2).clamp(max=1 - 1e-12)
    x = torch.stack([r * torch.cos(vartheta), r * torch.sin(vartheta)], -1)
    dH = poincare_dist(x[..., :, None, :], x[..., None, :, :])
    n = x.shape[-2]
    dH = dH.masked_fill(torch.eye(n, dtype=torch.bool, device=x.device), 0.0)
    return {"rho": rho, "x": x, "dH": dH}


_QUAD_CACHE: dict = {}


def _quadruples(n: int, device) -> torch.Tensor:
    key = (n, str(device))
    if key not in _QUAD_CACHE:
        _QUAD_CACHE[key] = torch.combinations(torch.arange(n, device=device), r=4)
    return _QUAD_CACHE[key]


def gromov_delta(D: torch.Tensor, chunk: int = 1 << 18) -> dict:
    """δ-Gromov (patru puncte) pe TOATE cvadruplele; D [n,n] sau [B,n,n]."""
    single = D.dim() == 2
    if single:
        D = D[None]
    n = D.shape[-1]
    Q = _quadruples(n, D.device)
    best = torch.zeros(D.shape[0], dtype=F64, device=D.device)
    for s0 in range(0, Q.shape[0], chunk):
        q = Q[s0:s0 + chunk]
        i, j, k, l = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
        s = torch.stack([D[:, i, j] + D[:, k, l], D[:, i, k] + D[:, j, l], D[:, i, l] + D[:, j, k]], -1)
        s = torch.sort(s, dim=-1).values
        best = torch.maximum(best, ((s[..., 2] - s[..., 1]) / 2).amax(-1))
    diam = D.amax((-1, -2))
    rel = torch.where(diam > 0, 2 * best / diam.clamp(min=1e-300), torch.zeros_like(best))
    out = {"delta": best, "diam": diam, "delta_rel": rel, "n_quadruples": int(Q.shape[0])}
    if single:
        out = {k2: (v[0] if torch.is_tensor(v) else v) for k2, v in out.items()}
    return out


def forman_curvature(G: torch.Tensor, k: int = FORMAN_K) -> dict:
    n = G.shape[-1]
    eye = torch.eye(n, dtype=torch.bool, device=G.device)
    vals, idx = G.masked_fill(eye, -float("inf")).topk(k, dim=-1)
    adj = torch.zeros(G.shape, dtype=torch.bool, device=G.device)
    adj.scatter_(-1, idx, vals > 0)
    adj = adj | adj.transpose(-1, -2)
    deg = adj.sum(-1).to(F64)
    Fe = 4 - deg[..., :, None] - deg[..., None, :]
    node = torch.where(deg > 0, (Fe * adj).sum(-1) / deg.clamp(min=1), torch.zeros_like(deg))
    return {"adj": adj, "deg": deg, "forman": node}


# ---------------------------------------------------------------------------
# Kuramoto condus de holonomie (P1 §2.7, AMENDAMENT 01/02)
# ---------------------------------------------------------------------------
def kuramoto_holonomy(p, absDelta, vartheta, Km: float = KUR_KM, ktilde: torch.Tensor | None = None,
                      dt: float = KUR_DT, steps: int = KUR_STEPS, record: bool = True) -> dict:
    """dθ_j/dt = ω_j + κ|Δ_j| sin(ϑ_j − θ_j) + (K_m/n) Σ_l sin(θ_l − θ_j), lot [B, G(κ̃), n]."""
    single = p.dim() == 1
    if single:
        p, absDelta, vartheta = p[None], absDelta[None], vartheta[None]
    n = p.shape[-1]
    if ktilde is None:
        ktilde = kappa_grid(p.device)
    omega = n * p - 1.0                                         # [B,n]
    ma = absDelta.mean(-1)
    # std populațional (correction=0); κ = κ̃·std(ω)/mean|Δ| (0 dacă mean|Δ| = 0)
    scale = torch.where(ma > 0, omega.std(-1, correction=0) / ma.clamp(min=1e-300), torch.zeros_like(ma))
    kappa = ktilde[None, :] * scale[:, None]                    # [B,G]
    w = omega[:, None, :]
    ka = kappa[:, :, None] * absDelta[:, None, :]               # [B,G,n]
    vt = vartheta[:, None, :]

    def f(th):
        mf = Km * (torch.sin(th).mean(-1, keepdim=True) * torch.cos(th)
                   - torch.cos(th).mean(-1, keepdim=True) * torch.sin(th))
        return w + ka * torch.sin(vt - th) + mf

    L = float(ka.amax()) + abs(Km) + float(omega.abs().amax())
    sub = max(1, math.ceil(dt * L / SUBSTEP_TARGET))
    h = dt / sub
    th = torch.zeros_like(ka)
    series = [torch.abs(torch.exp(1j * th).mean(-1))] if record else []
    for _ in range(steps):
        for _ in range(sub):
            k1 = f(th)
            k2 = f(th + 0.5 * h * k1)
            k3 = f(th + 0.5 * h * k2)
            k4 = f(th + h * k3)
            th = th + h / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        if record:
            series.append(torch.abs(torch.exp(1j * th).mean(-1)))
    vel = f(th)
    locked = vel.abs() < LOCK_TOL
    out = {
        "ktilde": ktilde, "kappa": kappa, "omega": omega, "theta": th, "velocity": vel, "locked": locked,
        "L_num": locked.to(F64).mean(-1),
        "L_adler": (omega.abs()[:, None, :] <= ka).to(F64).mean(-1),
        "R_final": torch.abs(torch.exp(1j * th).mean(-1)),
        "alignment": torch.abs((p[:, None, :].to(C128) * torch.exp(1j * (th - vt))).sum(-1)),
        "substeps": sub, "Km": Km, "dt": dt, "steps": steps,
    }
    if record:
        out["R_series"] = torch.stack(series, -1)               # [B,G,steps+1]
    if single:
        out = {k2: (v[0] if torch.is_tensor(v) and v.dim() > 0 and k2 != "ktilde" else v) for k2, v in out.items()}
    return out


def adler_reference(omega, ka, t_final: float):
    """Clasificare analitică Adler (K_m = 0) + masca nodurilor ne-frontieră (AMENDAMENT_TU3_01 §1)."""
    lock = omega.abs() <= ka
    ratio = torch.where(ka > 0, omega.abs() / ka.clamp(min=1e-300), torch.full_like(ka, float("inf")))
    lam = torch.sqrt((ka * ka - omega * omega).clamp(min=0))
    frontier = ((ratio - 1).abs() < 0.02) | (lock & (lam * t_final < 20)) | (~lock & (omega.abs() - ka < 1e-2))
    theta_star = torch.where(lock, torch.asin((omega / ka.clamp(min=1e-300)).clamp(-1, 1)), torch.zeros_like(ka))
    return {"locked": lock, "frontier": frontier, "theta_star_minus_vartheta": theta_star}


# ---------------------------------------------------------------------------
# Statistici de lot (pentru nul/putere) și rularea completă
# ---------------------------------------------------------------------------
def batch_stats(counts: torch.Tensor) -> dict:
    """I, S_E, Φ pentru un lot de tabele de numărări [B,n,m]."""
    P, p, q = joint_tensor(counts)
    C, _ = cross_covariance(P, p, q)
    _, S_E, K_S = schmidt(P)
    hol = holonomy(P, p, q, C, counts.sum(-1))
    return {"I": mutual_information(P, p, q), "S_E": S_E, "K_S": K_S, "Phi": hol["Phi"]}


def synth_universes(B: int, T: int, gamma: float, generator: torch.Generator, device, beta: float = BETA_SYNTH,
                    n: int = N_MAIN, m: int = M_JOKER, k: int = K_MAIN):
    """Generator P1 §4: Joker uniform; cu prob. γ, main = Gumbel-top-k din β·cos(ψ_j − φ_a); altfel uniform.

    Întoarce indici 0-based main0 [B,T,k], joker0 [B,T]."""
    joker0 = torch.randint(0, m, (B, T), generator=generator, device=device)
    tilt = torch.rand((B, T), generator=generator, device=device, dtype=F64) < gamma
    psi = 2 * math.pi * torch.arange(n, dtype=F64, device=device) / n
    phi = joker_phases(m, device)
    logits = beta * torch.cos(psi[None, None, :] - phi[joker0][..., None]) * tilt[..., None].to(F64)
    u = torch.rand((B, T, n), generator=generator, device=device, dtype=F64).clamp(min=1e-300, max=1 - 1e-16)
    gumbel = -torch.log(-torch.log(u))
    main0 = torch.topk(logits + gumbel, k, dim=-1).indices
    return main0, joker0


def run_joker(main: torch.Tensor, joker: torch.Tensor, device=None, with_gromov: bool = True,
              with_kuramoto: bool = True) -> dict:
    """Rulare completă pe o arhivă (numere 1-based): main [T,5], joker [T]. Întoarce tensori pe `device`."""
    dev = torch.device(device) if device is not None else resolve_device()
    main = torch.as_tensor(main, dtype=torch.long, device=dev)
    joker = torch.as_tensor(joker, dtype=torch.long, device=dev)
    validate_draws(main, joker)
    counts = joint_counts(main - 1, joker - 1)[0]
    P, p, q = joint_tensor(counts)
    C, Kt = cross_covariance(P, p, q)
    s, S_E, K_S = schmidt(P)
    hol = holonomy(P, p, q, C, counts.sum(-1))
    out = {"device": str(dev), "T": int(main.shape[0]), "counts": counts, "P": P, "p": p, "q": q, "C": C, "K": Kt,
           "schmidt": s, "S_E": S_E, "K_S": K_S, "I": mutual_information(P, p, q), **hol}
    out["field"] = main_field(p, hol["vartheta"], Kt)
    out["poincare"] = poincare_embed(hol["Z"], hol["vartheta"])
    out["forman"] = forman_curvature(out["field"]["G"])
    if with_gromov:
        out["gromov"] = gromov_delta(out["poincare"]["dH"])
    if with_kuramoto:
        out["kuramoto_Km0"] = kuramoto_holonomy(p, hol["absDelta"], hol["vartheta"], Km=0.0)
        out["kuramoto_Km2"] = kuramoto_holonomy(p, hol["absDelta"], hol["vartheta"], Km=KUR_KM)
    if dev.type == "cuda":
        out["vram"] = {"allocated": int(torch.cuda.memory_allocated(dev)),
                       "peak": int(torch.cuda.max_memory_allocated(dev))}
    out["device_events"] = list(DEVICE_EVENTS)
    return out
