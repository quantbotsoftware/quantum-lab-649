"""PL649 — motorul v2.0 „Singularitatea Planck” (PyTorch CUDA nativ; calcul CLASIC).

Implementează EXACT PREINREGISTRARE_PL649.md (PL649-P1, sigilat înainte de acest fișier):
- conexiunea SU(3) pe muchiile rețelei de spin (impulsuri exp(i ε λ_k), orientate după vechime) §3.1;
- spinii j = n/2, spectrul de arie √(j(j+1)), aria nodului, volumul-PROXY (S³)_aa/2 §3.2;
- buclele Wilson ale tuturor triunghiurilor printr-o singură înmulțire M·M pe GPU, curbura pe muchie/nod §3.3;
- legea PL și biletul = vidul QUBO certificat prin enumerarea COMPLETĂ a C(49,6) bilete pe GPU §3.4–3.5;
- anealerul Higgs (Langevin, rupere de simetrie Z2, 50.000 replici) și monopolii XY (Kuramoto) §8;
- telemetria produsului §9.
Termenii fizici sunt inspirație matematică; nu există hardware cuantic sau avantaj cuantic.
`positive_claims_allowed=false`. Nu importă și nu modifică engine.py (QL649, sigilat).
"""
from __future__ import annotations

import math
import time
from functools import lru_cache

import numpy as np
import torch

N = 49
K6 = 6
NP = N * (N - 1) // 2          # 1176 muchii
EPS = math.pi / 32
BETA = 0.5
ETA = 0.125
RHO = 0.5
TAU_E = 1e-9
TAU_SD = 1e-12
QEPS = 1e-4
LAM0 = 0.5
CDT = torch.complex128
RDT = torch.float64

PA, PB = np.triu_indices(N, 1)                 # perechile a<b, ordinea canonică
PID = np.full((N, N), -1, dtype=np.int64)
PID[PA, PB] = np.arange(NP)
PID[PB, PA] = np.arange(NP)
# cele 15 perechi (poziții i<j) dintr-un bilet sortat de 6
P15 = np.array([(i, j) for i in range(K6) for j in range(i + 1, K6)], dtype=np.int64)


def resolve_device(prefer: str = "cuda") -> torch.device:
    if prefer == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def gell_mann(device) -> torch.Tensor:
    L = torch.zeros(8, 3, 3, dtype=CDT)
    L[0, 0, 1] = L[0, 1, 0] = 1
    L[1, 0, 1], L[1, 1, 0] = -1j, 1j
    L[2, 0, 0], L[2, 1, 1] = 1, -1
    L[3, 0, 2] = L[3, 2, 0] = 1
    L[4, 0, 2], L[4, 2, 0] = -1j, 1j
    L[5, 1, 2] = L[5, 2, 1] = 1
    L[6, 1, 2], L[6, 2, 1] = -1j, 1j
    L[7, 0, 0] = L[7, 1, 1] = 1 / math.sqrt(3)
    L[7, 2, 2] = -2 / math.sqrt(3)
    return L.to(device)


def kick_matrices(device, eps: float = EPS) -> torch.Tensor:
    """E_k = exp(i ε λ_{k+1}), k = 0..7 (torch.linalg.matrix_exp)."""
    return torch.linalg.matrix_exp(1j * eps * gell_mann(device))


# ---------------------------------------------------------------------------
# Starea rețelei (loturi de B universuri cu aceeași structură de pași)
# ---------------------------------------------------------------------------
class LinkState:
    def __init__(self, B: int, device, eps: float = EPS, dtype=CDT):
        self.B, self.device = B, device
        self.U = torch.eye(3, dtype=dtype, device=device).expand(B, NP, 3, 3).clone()
        self.n = torch.zeros(B, NP, dtype=torch.int64, device=device)       # co-extrageri (= m)
        self.last = torch.full((B, N), -1, dtype=torch.int64, device=device)  # -1 ≡ −∞
        self.counts = torch.zeros(B, N, dtype=torch.int64, device=device)
        self.E = kick_matrices(device, eps).to(dtype)
        self.Ed = self.E.conj().transpose(-1, -2)
        self.bidx = torch.arange(B, device=device)[:, None]
        self.pid = torch.as_tensor(PID, device=device)
        self.p15 = torch.as_tensor(P15, device=device)
        self.steps_done = 0

    def add_step(self, s: int, draws: torch.Tensor) -> None:
        """draws: (B, nd, 6) indici 0-based. Vechimile din pașii strict anteriori (§3.1)."""
        draws = torch.sort(draws.to(self.device), -1).values
        ages = self.last.clone()
        for d in range(draws.shape[1]):
            x = draws[:, d, :]                                   # (B,6)
            a, b = x[:, self.p15[:, 0]], x[:, self.p15[:, 1]]    # (B,15), a<b
            pid = self.pid[a, b]
            ga, gb = ages.gather(1, a), ages.gather(1, b)
            gen = self.n.gather(1, pid) % 8
            Ek = self.E[gen]
            Uc = self.U[self.bidx, pid]
            left = Ek @ Uc                                       # a mai vechi: U_{a→b} ← E U_{a→b}
            right = Uc @ self.Ed[gen]                            # b mai vechi: U_ab ← U_ab E†
            new = torch.where((ga < gb)[..., None, None], left, torch.where((gb < ga)[..., None, None], right, Uc))
            self.U[self.bidx, pid] = new
            self.n[self.bidx, pid] += 1
            self.counts[self.bidx, x] += 1
        mem = torch.zeros(self.B, N, dtype=torch.bool, device=self.device)
        mem[self.bidx.expand(-1, draws.shape[1] * K6), draws.reshape(self.B, -1)] = True
        self.last = torch.where(mem, torch.full_like(self.last, s), self.last)
        self.steps_done += 1

    def snapshot(self) -> dict:
        return {"U": self.U.clone(), "n": self.n.clone(), "last": self.last.clone(), "counts": self.counts.clone()}


# ---------------------------------------------------------------------------
# Geometrie: arii, volum-proxy, bucle Wilson, curburi (§3.2–3.3)
# ---------------------------------------------------------------------------
def unitarity_error(U: torch.Tensor) -> dict:
    I = torch.eye(3, dtype=U.dtype, device=U.device)
    e = (U.conj().transpose(-1, -2) @ U - I).abs().amax((-1, -2))
    d = (torch.linalg.det(U) - 1).abs()
    return {"max_unitarity": float(e.max()), "max_det": float(d.max()),
            "frac_links_err_gt_1e-12": float((e > 1e-12).double().mean())}


def geometry(U: torch.Tensor, n: torch.Tensor, chunk: int = 128) -> dict:
    """U: (B,1176,3,3), n: (B,1176). Întoarce κ (B,49), ε (B,1176), A, V (B,49), a (B,1176)."""
    B, dev = U.shape[0], U.device
    rdt = torch.float64 if U.dtype == torch.complex128 else torch.float32
    pa, pb = torch.as_tensor(PA, device=dev), torch.as_tensor(PB, device=dev)
    kap, eps_e, Aout, Vout, aout = [], [], [], [], []
    for c0 in range(0, B, chunk):
        Uc, nc = U[c0:c0 + chunk], n[c0:c0 + chunk].to(rdt)
        b = Uc.shape[0]
        j = nc / 2
        a = torch.sqrt(j * (j + 1))                                   # spectrul de arie
        sa = torch.sqrt(a)
        S = torch.zeros(b, N, N, dtype=rdt, device=dev)
        S[:, pa, pb] = sa
        S[:, pb, pa] = sa
        M5 = torch.zeros(b, N, N, 3, 3, dtype=Uc.dtype, device=dev)
        M5[:, pa, pb] = sa.to(Uc.dtype)[..., None, None] * Uc
        M5[:, pb, pa] = sa.to(Uc.dtype)[..., None, None] * Uc.conj().transpose(-1, -2)
        M = M5.permute(0, 1, 3, 2, 4).reshape(b, 3 * N, 3 * N)       # bloc (a,b) = √a_ab U_{a→b}
        del M5
        M2 = M @ M                                                     # toate buclele Wilson
        T = (M * M2.transpose(-1, -2)).reshape(b, N, 3, N, 3).sum((2, 4)).real   # tr(M_ab (M²)_ba)
        S2 = S @ S
        den_e = 3 * S * S2                                             # 3 √a_ab (S²)_ab
        num_e = T
        ee = torch.where(den_e > 0, 1 - num_e / torch.where(den_e > 0, den_e, torch.ones_like(den_e)),
                         torch.zeros_like(den_e))
        den_n = (S * S2).sum(-1)                                       # (S³)_aa
        num_n = T.sum(-1)
        kk = torch.where(den_n > 0, 1 - num_n / (3 * torch.where(den_n > 0, den_n, torch.ones_like(den_n))),
                         torch.zeros_like(den_n))
        kap.append(kk)
        eps_e.append(ee[:, pa, pb])
        Aout.append(S.pow(2).sum(-1))
        Vout.append(den_n / 2)
        aout.append(a)
    return {"kappa": torch.cat(kap), "eps_edge": torch.cat(eps_e), "A": torch.cat(Aout), "V": torch.cat(Vout),
            "a": torch.cat(aout)}


def standardize(x: torch.Tensor) -> torch.Tensor:
    m = x.mean(-1, keepdim=True)
    sd = x.std(-1, unbiased=False, keepdim=True)
    return torch.where(sd > TAU_SD, (x - m) / torch.where(sd > TAU_SD, sd, torch.ones_like(sd)), torch.zeros_like(x))


def law(kappa: torch.Tensor, beta: float = BETA) -> dict:
    z = standardize(kappa)
    pi = torch.softmax(-beta * z, -1)
    return {"z": z, "pi": pi}


def marginal_q(pi: np.ndarray) -> np.ndarray:
    base = 6.0 / N
    d = 6.0 * pi - base
    with np.errstate(divide="ignore", invalid="ignore"):
        up = np.where(d > 0, (1 - QEPS - base) / d, np.inf)
        dn = np.where(d < 0, (base - QEPS) / (-d), np.inf)
    lam = np.minimum(LAM0, np.minimum(up.min(-1), dn.min(-1)))[..., None]
    return base + lam * d


def qubo_terms(z: torch.Tensor, eps_edge: torch.Tensor, beta: float = BETA, eta: float = ETA):
    """h = β z (B,49); J = η ζ (B,49,49) simetric, diag 0 (§3.5)."""
    zeta = standardize(eps_edge)
    B, dev = z.shape[0], z.device
    J = torch.zeros(B, N, N, dtype=torch.float64, device=dev)
    pa, pb = torch.as_tensor(PA, device=dev), torch.as_tensor(PB, device=dev)
    J[:, pa, pb] = eta * zeta.double()
    J[:, pb, pa] = eta * zeta.double()
    return beta * z.double(), J


# ---------------------------------------------------------------------------
# Enumerarea completă C(49,6) pe GPU (certificatul vidului)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _combos_np(n: int, r: int) -> np.ndarray:
    if r == 0:
        return np.zeros((1, 0), dtype=np.uint8)
    parts = []
    for first in range(n - r + 1):
        sub = _combos_np(n - first - 1, r - 1).astype(np.int16) + first + 1
        parts.append(np.hstack([np.full((sub.shape[0], 1), first, dtype=np.int16), sub]).astype(np.uint8))
    return np.vstack(parts)


class Enumerator:
    """Toate biletele în ordine lexicografică; energii fp64 pe GPU, în blocuri."""

    def __init__(self, device, chunk: int = 2_000_000):
        self.device, self.chunk = device, chunk
        C = _combos_np(N, K6)
        assert C.shape[0] == math.comb(N, K6)
        self.C = torch.as_tensor(C, device=device)                                   # uint8
        fl = (C[:, P15[:, 0]].astype(np.int16) * N + C[:, P15[:, 1]].astype(np.int16))
        self.F = torch.as_tensor(fl, device=device)                                  # int16
        self.total = C.shape[0]

    def _energy(self, h: torch.Tensor, Jf: torch.Tensor, lo: int, hi: int, extra=None) -> torch.Tensor:
        c = self.C[lo:hi].long()
        e = h[c].sum(-1) + Jf[self.F[lo:hi].long()].sum(-1)
        if extra is not None:
            e = e + extra(c)
        return e

    def minimize(self, h: torch.Tensor, J: torch.Tensor, tau: float = TAU_E, extra=None) -> dict:
        """h: (49,), J: (49,49). Biletul = primul lexicografic cu E ≤ E_min + τ."""
        Jf = J.reshape(-1)
        mins = []
        for lo in range(0, self.total, self.chunk):
            e = self._energy(h, Jf, lo, min(lo + self.chunk, self.total), extra)
            mins.append(torch.topk(e, 2, largest=False).values)
        mv = torch.sort(torch.cat(mins)).values
        emin, esec = mv[0], mv[1]
        thr = emin + tau
        best = None
        for lo in range(0, self.total, self.chunk):
            e = self._energy(h, Jf, lo, min(lo + self.chunk, self.total), extra)
            ok = torch.nonzero(e <= thr)
            if ok.numel():
                best = lo + int(ok[0, 0])
                break
        t = (self.C[best].long() + 1).tolist()
        return {"ticket": t, "index": best, "E_min": float(emin), "E_second": float(esec)}

    def variants(self, h: torch.Tensor, J: torch.Tensor, k: int = 3, rho: float = RHO) -> list[dict]:
        """Produs §3.5: varianta 1 = vidul; varianta i minimizează E + ρ Σ|s∩v| peste biletele noi."""
        out = []
        for _ in range(k):
            prev = [torch.as_tensor([x - 1 for x in v["ticket"]], device=self.device) for v in out]

            def extra(c, prev=prev):
                pen = torch.zeros(c.shape[0], dtype=torch.float64, device=c.device)
                for p in prev:
                    mask = torch.zeros(N, dtype=torch.float64, device=c.device)
                    mask[p] = 1.0
                    ov = mask[c].sum(-1)
                    pen = pen + rho * ov + torch.where(ov >= K6, torch.full_like(ov, float("inf")), torch.zeros_like(ov))
                return pen
            r = self.minimize(h, J, extra=extra if prev else None)
            r["E_base"] = energy_of(r["ticket"], h, J)
            out.append(r)
        return out


def energy_of(ticket: list[int], h: torch.Tensor, J: torch.Tensor) -> float:
    idx = [x - 1 for x in ticket]
    return float(h[idx].sum() + J[idx][:, idx].sum() / 2)


# ---------------------------------------------------------------------------
# Predicția la un pas (folosită de calificare, backtest și produs)
# ---------------------------------------------------------------------------
def predict_state(U, n, enum: Enumerator | None = None, need_ticket: bool = True) -> dict:
    g = geometry(U, n)
    L = law(g["kappa"])
    out = {"kappa": g["kappa"], "eps_edge": g["eps_edge"], "A": g["A"], "V": g["V"], "a": g["a"],
           "z": L["z"], "pi": L["pi"]}
    if need_ticket and enum is not None:
        h, J = qubo_terms(L["z"], g["eps_edge"])
        tk = [enum.minimize(h[i], J[i]) for i in range(h.shape[0])]
        out["qubo"] = tk
        out["h"], out["J"] = h, J
    return out


def steps_to_tensor(step: np.ndarray, device) -> torch.Tensor:
    """step: (nd,49) one-hot → (1,nd,6) indici."""
    idx = np.stack([np.nonzero(r)[0] for r in step])
    return torch.as_tensor(idx, dtype=torch.int64, device=device)[None]


# ---------------------------------------------------------------------------
# Anealerul Higgs (§8)
# ---------------------------------------------------------------------------
def higgs_anneal(h: torch.Tensor, J: torch.Tensor, R: int = 50_000, n_steps: int = 1500, dt: float = 0.02,
                 seed: int = 649, record_every: int = 50, max_descent: int = 50) -> dict:
    dev = h.device
    g = torch.Generator(device=dev)
    g.manual_seed(seed)
    hf, Jf = h.float(), J.float()
    phi = 0.1 * torch.randn(R, N, generator=g, device=dev)
    traj = []
    t0 = time.time()
    for t in range(n_steps):
        frac = t / n_steps
        mu2 = 1.0 - 2.0 * frac
        T = 0.5 * (1.0 - frac) ** 2
        th = torch.tanh(phi)
        occ = (1 + th) / 2
        dn = (1 - th * th) / 2
        field = hf + occ @ Jf + 4.0 * (occ.sum(-1, keepdim=True) - K6)
        grad = mu2 * phi + phi ** 3 + field * dn
        phi = phi - dt * grad + math.sqrt(2 * dt * T) * torch.randn(R, N, generator=g, device=dev)
        if t % record_every == 0 or t == n_steps - 1:
            traj.append({"t": t, "mu2": mu2, "T": T, "order_param": float(phi.abs().mean()),
                         "mean_occ": float(occ.sum(-1).mean()), "occ_node": occ.mean(0).tolist()})
    # proiecție pe |s| = 6 și coborâre deterministă 1↔1 (fp64)
    top = torch.topk(phi, K6, -1).indices
    x = torch.zeros(R, N, dtype=torch.float64, device=dev)
    x.scatter_(1, top, 1.0)
    hd, Jd = h.double(), J.double()
    for _ in range(max_descent):
        f = x @ Jd                                                    # Σ_{c∈s} J_·c
        gain = hd + f                                                 # (R,49)
        # Δ(a out, b in) = gain_b − gain_a − J_ab
        D = gain[:, None, :] - gain[:, :, None] - Jd[None]
        valid = (x[:, :, None] > 0.5) & (x[:, None, :] < 0.5)
        D = torch.where(valid, D, torch.full_like(D, float("inf")))
        best = D.reshape(R, -1).min(-1)
        imp = best.values < -1e-12
        if not bool(imp.any()):
            break
        ab = best.indices
        a_out, b_in = ab // N, ab % N
        rows = torch.nonzero(imp)[:, 0]
        x[rows, a_out[rows]] = 0.0
        x[rows, b_in[rows]] = 1.0
        del D, valid
    E = (x @ hd) + 0.5 * ((x @ Jd) * x).sum(-1)
    w = (2 ** torch.arange(N, device=dev, dtype=torch.int64))
    code = (x.long() * w).sum(-1)
    uniq, inv = torch.unique(code, return_inverse=True)
    Eu = torch.full((uniq.shape[0],), float("inf"), dtype=torch.float64, device=dev)
    Eu = Eu.scatter_reduce(0, inv, E, reduce="amin")
    order = torch.argsort(Eu)
    states = []
    for i in order[:10].tolist():
        c = int(uniq[i])
        states.append({"ticket": [j + 1 for j in range(N) if (c >> j) & 1], "E": float(Eu[i]),
                       "replicas": int((inv == i).sum())})
    sym_break = next((p["t"] for p in traj if p["mu2"] < 0), None)
    return {"states": states, "trajectory": traj, "n_distinct": int(uniq.shape[0]), "R": R,
            "symmetry_breaking_step": sym_break, "seconds": time.time() - t0}


# ---------------------------------------------------------------------------
# Monopoli XY (Kuramoto pe rețeaua de spin, §8)
# ---------------------------------------------------------------------------
_TRI = None


def triangles(device) -> torch.Tensor:
    global _TRI
    if _TRI is None or _TRI.device != device:
        import itertools
        _TRI = torch.as_tensor(list(itertools.combinations(range(N), 3)), device=device)
    return _TRI


def xy_monopoles(z: torch.Tensor, a: torch.Tensor, R: int = 4096, n_steps: int = 2000, dt: float = 0.05,
                 T: float = 0.05, seed=(649, 12, 77)) -> dict:
    dev = z.device
    rng = np.random.default_rng(list(seed))
    theta = torch.as_tensor(rng.uniform(0, 2 * math.pi, (R, N)), dtype=torch.float32, device=dev)
    pa, pb = torch.as_tensor(PA, device=dev), torch.as_tensor(PB, device=dev)
    K = torch.zeros(N, N, dtype=torch.float32, device=dev)
    spun = a > 0
    am = a[spun].mean() if bool(spun.any()) else torch.tensor(1.0, device=dev)
    K[pa, pb] = (a / am).float()
    K[pb, pa] = (a / am).float()
    om = z.float()
    g = torch.Generator(device=dev)
    g.manual_seed(int(649 * 1000 + 77))
    for _ in range(n_steps):
        s, c = torch.sin(theta), torch.cos(theta)
        drive = c * (s @ K) - s * (c @ K)
        theta = theta + dt * (om + drive) + math.sqrt(2 * T * dt) * torch.randn(R, N, generator=g, device=dev)
    tri = triangles(dev)
    A_ = torch.zeros(N, N, dtype=torch.bool, device=dev)
    A_[pa, pb] = spun
    A_[pb, pa] = spun
    ok = A_[tri[:, 0], tri[:, 1]] & A_[tri[:, 1], tri[:, 2]] & A_[tri[:, 0], tri[:, 2]]
    tri = tri[ok]

    def wrap(x):
        return torch.remainder(x + math.pi, 2 * math.pi) - math.pi
    ta, tb, tc = theta[:, tri[:, 0]], theta[:, tri[:, 1]], theta[:, tri[:, 2]]
    q = torch.round((wrap(tb - ta) + wrap(tc - tb) + wrap(ta - tc)) / (2 * math.pi)).to(torch.int8)
    pos = (q > 0).float().mean(0)
    neg = (q < 0).float().mean(0)
    pers = torch.maximum(pos, neg)
    keep = pers >= 0.9
    r_loc = torch.abs(torch.exp(1j * theta.double()).mean(0))
    top = torch.argsort(pers, descending=True)[:10]
    return {"n_triangles": int(tri.shape[0]), "mean_vortices_per_replica": float((q != 0).float().sum(1).mean()),
            "persistent_monopoles": int(keep.sum()),
            "top": [{"triangle": [int(v) + 1 for v in tri[i]], "persistence": float(pers[i]),
                     "charge": 1 if float(pos[i]) >= float(neg[i]) else -1} for i in top.tolist()],
            "order_r_global_mean": float(torch.abs(torch.exp(1j * theta.double()).mean(1)).mean()),
            "replica_phase_coherence_node": r_loc.tolist(), "R": R}


# ---------------------------------------------------------------------------
# Telemetrie și vizualizare (§9)
# ---------------------------------------------------------------------------
def null_total_area(n_draws: int, device, R: int = 4096, seed: int = 649, chunk_draws: int = 256) -> dict:
    g = torch.Generator(device=device)
    g.manual_seed(seed)
    cnt = torch.zeros(R, NP, dtype=torch.int64, device=device)
    pid = torch.as_tensor(PID, device=device)
    p15 = torch.as_tensor(P15, device=device)
    done = 0
    while done < n_draws:
        m = min(chunk_draws, n_draws - done)
        x = torch.sort(torch.topk(torch.rand(R, m, N, generator=g, device=device), K6, -1).indices, -1).values
        ids = pid[x[..., p15[:, 0]], x[..., p15[:, 1]]].reshape(R, -1)
        cnt.scatter_add_(1, ids, torch.ones_like(ids))
        done += m
    j = cnt.double() / 2
    tot = torch.sqrt(j * (j + 1)).sum(-1)
    return {"mean": float(tot.mean()), "sd": float(tot.std()), "R": R}


def spectral_layout(a: torch.Tensor) -> np.ndarray:
    dev = a.device
    pa, pb = torch.as_tensor(PA, device=dev), torch.as_tensor(PB, device=dev)
    W = torch.zeros(N, N, dtype=torch.float64, device=dev)
    W[pa, pb] = a.double()
    W[pb, pa] = a.double()
    d = W.sum(-1).clamp_min(1e-12)
    Lm = torch.eye(N, dtype=torch.float64, device=dev) - W / torch.sqrt(d[:, None] * d[None, :])
    ev, vec = torch.linalg.eigh(Lm)
    X = vec[:, 1:4]
    sgn = torch.sign(X.gather(0, X.abs().argmax(0, keepdim=True)))
    X = X * sgn
    X = X / X.abs().max().clamp_min(1e-12)
    return X.cpu().numpy()


def vram() -> dict:
    if not torch.cuda.is_available():
        return {"cuda": False}
    free, total = torch.cuda.mem_get_info()
    return {"cuda": True, "device": torch.cuda.get_device_name(0),
            "allocated_MiB": torch.cuda.memory_allocated() / 2 ** 20,
            "reserved_MiB": torch.cuda.memory_reserved() / 2 ** 20,
            "max_allocated_MiB": torch.cuda.max_memory_allocated() / 2 ** 20,
            "free_MiB": free / 2 ** 20, "total_MiB": total / 2 ** 20,
            "sm_count": torch.cuda.get_device_properties(0).multi_processor_count}
