"""HS-V4 Core — Motor GPU (CUDA / PyTorch) pentru Deconvoluție Bosonică Hubbard–Stratonovich (O1),
Cuplaj Aero-Fizic Exogen București (O2), Portofoliu Bayesian cu Masă de Abținere w_0=0.50 (O3)
și Canal Spectral Bitwise/Modular pentru Extrageri Electronice Online RNG (O4).

Protocol sigilat: hs_v4/PROTOCOL_HSV4.md (hs_v4/SIGILIU_PROTOCOL_HSV4.json).
Calcul clasic exact în float64; positive_claims_allowed = False.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch


@dataclass(frozen=True)
class HSV4Params:
    rank_r: int = 3
    tau_bos: float = 160.0
    tau_int: Tuple[float, float, float] = (16.0, 64.0, 256.0)
    int_weights: Tuple[float, float, float] = (0.50, 0.30, 0.20)
    tau_joker: float = 128.0
    kappa_joker: float = 0.50
    lambda_aero: float = 24.0
    tau_aero: float = 256.0
    meteo_warmup: int = 5
    meteo_zmax: float = 4.0
    lambda_rng: float = 16.0
    tau_rng: float = 192.0
    w0_prior: float = 0.50
    gamma_jastrow: float = 0.50
    pool_size: int = 2048
    gh_order: int = 16
    chunk_size: int = 500_000
    exact_state_limit: int = 50_000_000
    rms_floor: float = 1e-4


DEFAULT_PARAMS = HSV4Params()

# Grila fixată a celor 8 experți din PROTOCOL_HSV4.md §2.4:
# (id, name, field_kind, eta, gamma, base_prior)
EXPERT_GRID: Tuple[Tuple[int, str, str, float, float, float], ...] = (
    (0, "m0_uniform_abstention", "none", 0.00, 0.00, 0.50),
    (1, "m1_o1_bosonic_mild", "zero", 0.00, 0.35, 0.10),
    (2, "m2_o1_bosonic_strong", "zero", 0.00, 0.75, 0.08),
    (3, "m3_o1_int_bosonic", "int", 0.35, 0.40, 0.08),
    (4, "m4_o2_aero_pure", "aero", 0.45, 0.00, 0.06),
    (5, "m5_o1_o2_coupled", "int_aero", 0.40, 0.45, 0.06),
    (6, "m6_o4_rng_mild", "rng", 0.45, 0.00, 0.06),
    (7, "m7_o4_rng_strong", "rng", 0.95, 0.00, 0.06),
)


def compute_prior_weights(
    enable_o1: bool = True,
    enable_o2: bool = True,
    enable_o4: bool = True,
    w0_prior: float = 0.50,
) -> np.ndarray:
    """Calculează vectorul de mase a priori w^(0) cu w_0 = 0.50 fixat (PROTOCOL_HSV4.md §2.4)."""
    active = np.zeros(len(EXPERT_GRID), dtype=np.float64)
    for idx, _, f_kind, _, gm, base_p in EXPERT_GRID:
        if idx == 0:
            continue
        ok = True
        if idx in (1, 2, 3) and not enable_o1:
            ok = False
        elif idx == 4 and not enable_o2:
            ok = False
        elif idx == 5 and not (enable_o1 and enable_o2):
            ok = False
        elif idx in (6, 7) and not enable_o4:
            ok = False
        if ok:
            active[idx] = base_p

    rem_sum = float(active.sum())
    w = np.zeros(len(EXPERT_GRID), dtype=np.float64)
    if rem_sum <= 0.0:
        w[0] = 1.0
    else:
        w[0] = w0_prior
        w[1:] = (1.0 - w0_prior) * (active[1:] / rem_sum)
    return w


# ============================================================================
# 0. SPAȚIUL DE STĂRI, COMBINADICE PE GPU & BAZA ARITMETICĂ O4
# ============================================================================

class HSV4Space:
    """Spațiul combinatorial C(N, k) (sau bipartit C(N, k) × M_J), cvadratura GH și bazele O4."""

    def __init__(
        self,
        N: int,
        r_draw: int,
        k_ticket: int,
        device: torch.device,
        joker_m: Optional[int] = None,
        gh_order: int = DEFAULT_PARAMS.gh_order,
    ):
        self.N = int(N)
        self.r_draw = int(r_draw)
        self.k_ticket = int(k_ticket)
        self.joker_m = int(joker_m) if joker_m is not None else None
        self.device = device

        self.total_base_states = math.comb(self.N, self.k_ticket)
        self.total_states = self.total_base_states * (self.joker_m if self.joker_m is not None else 1)
        self.binom_table = self._build_binom_table(self.N, self.k_ticket, device)
        self._comb_u8_cache: Optional[torch.Tensor] = None

        # Proiector P_perp = I_N - (1/N) 1 1^T și masca tripletelor distincte i != j != k
        eye_n = torch.eye(self.N, dtype=torch.float64, device=device)
        ones_n = torch.ones((self.N, self.N), dtype=torch.float64, device=device) / float(self.N)
        self.P_perp = eye_n - ones_n
        self.sig0_var = float(self.r_draw * (self.N - self.r_draw)) / float(self.N * (self.N - 1))
        self.mu3_unif = (
            float(self.r_draw * (self.r_draw - 1) * (self.r_draw - 2))
            / float(self.N * (self.N - 1) * (self.N - 2))
            if self.N >= 3 and self.r_draw >= 3
            else 0.0
        )

        grid = torch.arange(self.N, device=device)
        ii, jj, kk = torch.meshgrid(grid, grid, grid, indexing="ij")
        self.dist3_mask = ((ii != jj) & (jj != kk) & (ii != kk)).to(torch.float64)

        # Cvadratură Gauss–Hermite 3D (M_GH^3 noduri) în float64 pentru identitatea exactă Hubbard–Stratonovich
        gx, gw = np.polynomial.hermite.hermgauss(int(gh_order))
        gw = gw / math.sqrt(math.pi)
        self.gh_x_1d = gx.astype(np.float64)
        self.gh_w_1d = gw.astype(np.float64)
        g1, g2, g3 = np.meshgrid(gx, gx, gx, indexing="ij")
        w3 = (gw[:, None, None] * gw[None, :, None] * gw[None, None, :]).reshape(-1)
        x3 = np.stack([g1.reshape(-1), g2.reshape(-1), g3.reshape(-1)], axis=1)
        self.gh_x3 = torch.as_tensor(x3, dtype=torch.float64, device=device)          # [Q, 3]
        self.gh_log_w3 = torch.as_tensor(np.log(w3), dtype=torch.float64, device=device)  # [Q]

        # Precalcul tabele statice O4 pe urna principală N (și opțional secundară M_J)
        self.o4_main = self._precompute_o4_tables(self.N, device)
        self.o4_joker = self._precompute_o4_tables(self.joker_m, device) if self.joker_m is not None else None

    @staticmethod
    def _build_binom_table(N: int, k: int, device: torch.device) -> torch.Tensor:
        t = torch.zeros((N + 1, k + 1), dtype=torch.int64, device=device)
        for n in range(N + 1):
            for r in range(min(n, k) + 1):
                t[n, r] = math.comb(n, r)
        return t

    @staticmethod
    def _center_and_norm(col: np.ndarray) -> np.ndarray:
        c = col.astype(np.float64) - float(np.mean(col))
        nrm = float(np.linalg.norm(c))
        return c / nrm if nrm > 1e-12 else np.zeros_like(c)

    @classmethod
    def _precompute_o4_tables(cls, size_n: int, device: torch.device) -> Dict[str, torch.Tensor]:
        u = np.arange(size_n, dtype=np.int64)
        n_bits = max(int(math.ceil(math.log2(max(size_n, 2)))), 1)
        static_cols: List[np.ndarray] = []

        # 1. Bias de modulo la respingere incompletă: u < (2^b mod N) pentru b ∈ {6, 7, 8}
        for b_width in (6, 7, 8):
            rem_b = (1 << b_width) % size_n
            ind = (u < rem_b).astype(np.float64) if rem_b > 0 else np.zeros(size_n, dtype=np.float64)
            static_cols.append(cls._center_and_norm(ind))

        # 2. Reziduuri prime statice p ∈ {3, 5, 7}
        prime_mod_mats: List[np.ndarray] = []
        for p_mod in (3, 5, 7):
            for res_c in range(p_mod - 1):
                ind_p = ((u % p_mod) == res_c).astype(np.float64)
                static_cols.append(cls._center_and_norm(ind_p))
            p_mat = np.zeros((size_n, p_mod), dtype=np.float64)
            for res_c in range(p_mod):
                p_mat[:, res_c] = ((u % p_mod) == res_c).astype(np.float64)
            prime_mod_mats.append(p_mat)

        # 3. Semne pe biți (2*bit_l(u) - 1) și paritate Hamming (-1)^popcount(u)
        bit_raw = np.zeros((size_n, n_bits), dtype=np.float64)
        bit_cent = np.zeros((size_n, n_bits), dtype=np.float64)
        popc = np.zeros(size_n, dtype=np.int64)
        for ell in range(n_bits):
            b_ell = (u >> ell) & 1
            popc += b_ell
            s_ell = 2.0 * b_ell.astype(np.float64) - 1.0
            bit_raw[:, ell] = s_ell
            sc = cls._center_and_norm(s_ell)
            bit_cent[:, ell] = sc
            static_cols.append(sc)

        hp_raw = np.where((popc % 2) == 0, 1.0, -1.0)
        hp_cent = cls._center_and_norm(hp_raw)
        static_cols.append(hp_cent)

        # Matricea de similaritate bitwise XOR: 1 - 2 * popcount(u ^ v) / n_bits
        xor_mat = u[:, None] ^ u[None, :]
        xor_pop = np.zeros_like(xor_mat, dtype=np.float64)
        for ell in range(n_bits):
            xor_pop += ((xor_mat >> ell) & 1).astype(np.float64)
        xor_sim = 1.0 - (2.0 * xor_pop / float(n_bits))
        # Centrare pe coloana țintă u (prima axă) astfel încât ∑_u xor_sim_cent[u, v] = 0 pentru orice v
        xor_sim_cent = xor_sim - xor_sim.mean(axis=0, keepdims=True)

        # Numărul total de trăsături d_rng:
        # static_cols + 2*3 (tranziții mod 3,5,7 shift 0 și +1) + n_bits (XOR bit-persistence) + 1 (XOR kernel) + 1 (Hamming trans)
        static_np = np.stack(static_cols, axis=1)  # [N, d_static]
        d_total = static_np.shape[1] + 6 + n_bits + 2

        return {
            "static": torch.as_tensor(static_np, dtype=torch.float64, device=device),
            "mod3": torch.as_tensor(prime_mod_mats[0], dtype=torch.float64, device=device),
            "mod5": torch.as_tensor(prime_mod_mats[1], dtype=torch.float64, device=device),
            "mod7": torch.as_tensor(prime_mod_mats[2], dtype=torch.float64, device=device),
            "bit_raw": torch.as_tensor(bit_raw, dtype=torch.float64, device=device),
            "bit_cent": torch.as_tensor(bit_cent, dtype=torch.float64, device=device),
            "hp_raw": torch.as_tensor(hp_raw, dtype=torch.float64, device=device),
            "hp_cent": torch.as_tensor(hp_cent, dtype=torch.float64, device=device),
            "xor_sim_cent": torch.as_tensor(xor_sim_cent, dtype=torch.float64, device=device),
            "d_total": torch.tensor(d_total, dtype=torch.int64, device=device),
        }

    def unrank_chunk(self, start_idx: int, end_idx: int) -> torch.Tensor:
        if self._comb_u8_cache is not None:
            return self._comb_u8_cache[start_idx:end_idx].to(torch.int64)
        ranks = torch.arange(start_idx, end_idx, dtype=torch.int64, device=self.device)
        simplices = torch.empty((ranks.shape[0], self.k_ticket), dtype=torch.int64, device=self.device)
        rem = ranks
        for d in range(self.k_ticket, 0, -1):
            col_d = self.binom_table[: self.N, d].contiguous()
            c = (torch.searchsorted(col_d, rem, right=True) - 1).clamp_(0, self.N - 1)
            simplices[:, d - 1] = c
            rem = rem - col_d[c]
        return simplices

    def ensure_comb_cache(self, max_cached_states: int = 15_000_000) -> None:
        """Memorează în VRAM (uint8, ~84 MB pt. 6/49) toate C(N, k) stări pentru evaluare rapidă."""
        if self._comb_u8_cache is not None or self.total_base_states > max_cached_states or self.N > 255:
            return
        buf = torch.empty((self.total_base_states, self.k_ticket), dtype=torch.uint8, device=self.device)
        step = 1_000_000
        for s in range(0, self.total_base_states, step):
            e = min(s + step, self.total_base_states)
            ranks = torch.arange(s, e, dtype=torch.int64, device=self.device)
            rem = ranks
            for d in range(self.k_ticket, 0, -1):
                col_d = self.binom_table[: self.N, d].contiguous()
                c = (torch.searchsorted(col_d, rem, right=True) - 1).clamp_(0, self.N - 1)
                buf[s:e, d - 1] = c.to(torch.uint8)
                rem = rem - col_d[c]
        self._comb_u8_cache = buf


def build_o4_dictionary(
    o4_tab: Dict[str, torch.Tensor],
    prev_bar_x: torch.Tensor,
    r_draw: float,
) -> torch.Tensor:
    """Construiește dicționarul cauzal zero-sum Ψ_s ∈ R^{N × d_rng} (∑_u Ψ_{s,u,m} = 0 exact)."""
    N = prev_bar_x.shape[0]
    dx = prev_bar_x - (float(r_draw) / float(N))  # ∑ dx = 0 sub uniform
    dyn_cols: List[torch.Tensor] = []

    for key in ("mod3", "mod5", "mod7"):
        P_mod = o4_tab[key]  # [N, p]
        q_prev = (dx @ P_mod) / float(r_draw)  # [p]
        c0 = P_mod @ q_prev
        c0 = c0 - c0.mean()
        c1 = P_mod @ torch.roll(q_prev, shifts=1, dims=0)
        c1 = c1 - c1.mean()
        dyn_cols.extend([c0, c1])

    # Tranziții pe biți (XOR bit-persistence / alternation)
    b_prev = (dx @ o4_tab["bit_raw"]) / float(r_draw)  # [n_bits]
    bit_trans = o4_tab["bit_cent"] * b_prev.unsqueeze(0)  # [N, n_bits], deja zero-sum pe axa 0!

    # Kernel XOR global față de extragerea s-1
    xor_col = (o4_tab["xor_sim_cent"] @ dx) / float(r_draw)
    xor_col = xor_col - xor_col.mean()

    # Tranziție paritate Hamming s-1 -> s
    hp_prev = float((dx @ o4_tab["hp_raw"]).item()) / float(r_draw)
    hp_trans = o4_tab["hp_cent"] * hp_prev

    dyn_mat = torch.cat(
        [
            torch.stack(dyn_cols, dim=1),
            bit_trans,
            xor_col.unsqueeze(1),
            hp_trans.unsqueeze(1),
        ],
        dim=1,
    )
    return torch.cat([o4_tab["static"], dyn_mat], dim=1)  # [N, d_rng]


# ============================================================================
# 1. STAREA CAUZALĂ MARKOVIANĂ & OPERATORII O1, O2, O4, O3
# ============================================================================

@dataclass
class HSV4State:
    step_idx: int
    n_eff_bos: float
    m1_bos: torch.Tensor
    m2_bos: torch.Tensor
    m3_dist: torch.Tensor
    ema_int: torch.Tensor
    meteo_count: int
    meteo_mean: torch.Tensor
    meteo_m2: torch.Tensor
    aero_gram: torch.Tensor
    aero_rhs: torch.Tensor
    prev_bar_x: torch.Tensor
    rng_gram: torch.Tensor
    rng_rhs: torch.Tensor
    log_wealth: torch.Tensor
    portfolio_steps: int
    enable_o1: bool = True
    enable_o2: bool = True
    enable_o4: bool = True
    ema_joker_int: Optional[torch.Tensor] = None
    m1_joker: Optional[torch.Tensor] = None
    cross_m2: Optional[torch.Tensor] = None
    aero_rhs_joker: Optional[torch.Tensor] = None
    prev_bar_j: Optional[torch.Tensor] = None
    rng_gram_j: Optional[torch.Tensor] = None
    rng_rhs_j: Optional[torch.Tensor] = None

    def clone(self) -> "HSV4State":
        cp = lambda t: None if t is None else t.clone()
        return HSV4State(
            step_idx=int(self.step_idx),
            n_eff_bos=float(self.n_eff_bos),
            m1_bos=self.m1_bos.clone(),
            m2_bos=self.m2_bos.clone(),
            m3_dist=self.m3_dist.clone(),
            ema_int=self.ema_int.clone(),
            meteo_count=int(self.meteo_count),
            meteo_mean=self.meteo_mean.clone(),
            meteo_m2=self.meteo_m2.clone(),
            aero_gram=self.aero_gram.clone(),
            aero_rhs=self.aero_rhs.clone(),
            prev_bar_x=self.prev_bar_x.clone(),
            rng_gram=self.rng_gram.clone(),
            rng_rhs=self.rng_rhs.clone(),
            log_wealth=self.log_wealth.clone(),
            portfolio_steps=int(self.portfolio_steps),
            enable_o1=bool(self.enable_o1),
            enable_o2=bool(self.enable_o2),
            enable_o4=bool(self.enable_o4),
            ema_joker_int=cp(self.ema_joker_int),
            m1_joker=cp(self.m1_joker),
            cross_m2=cp(self.cross_m2),
            aero_rhs_joker=cp(self.aero_rhs_joker),
            prev_bar_j=cp(self.prev_bar_j),
            rng_gram_j=cp(self.rng_gram_j),
            rng_rhs_j=cp(self.rng_rhs_j),
        )


def init_state(
    space: HSV4Space,
    params: HSV4Params = DEFAULT_PARAMS,
    enable_o1: bool = True,
    enable_o2: bool = True,
    enable_o4: bool = True,
) -> HSV4State:
    N, r, dev = space.N, space.r_draw, space.device
    p0 = float(r) / float(N)
    p2_off = float(r * (r - 1)) / float(N * (N - 1))

    m1_bos = torch.full((N,), p0, dtype=torch.float64, device=dev)
    m2_bos = torch.full((N, N), p2_off, dtype=torch.float64, device=dev)
    m2_bos.fill_diagonal_(p0)
    m3_dist = space.dist3_mask * space.mu3_unif
    ema_int = torch.full((3, N), p0, dtype=torch.float64, device=dev)

    d_rng = int(space.o4_main["d_total"].item())
    priors = compute_prior_weights(enable_o1=enable_o1, enable_o2=enable_o2, enable_o4=enable_o4, w0_prior=params.w0_prior)
    log_w = torch.full((len(EXPERT_GRID),), float("-inf"), dtype=torch.float64, device=dev)
    for idx, pv in enumerate(priors):
        if pv > 0.0:
            log_w[idx] = math.log(pv)

    ema_j = m1_j = cross_m2 = aero_rhs_j = prev_j = rg_j = rr_j = None
    if space.joker_m is not None:
        M = space.joker_m
        pj0 = 1.0 / float(M)
        ema_j = torch.full((3, M), pj0, dtype=torch.float64, device=dev)
        m1_j = torch.full((M,), pj0, dtype=torch.float64, device=dev)
        cross_m2 = torch.full((N, M), p0 * pj0, dtype=torch.float64, device=dev)
        aero_rhs_j = torch.zeros((3, M), dtype=torch.float64, device=dev)
        prev_j = torch.full((M,), pj0, dtype=torch.float64, device=dev)
        d_rng_j = int(space.o4_joker["d_total"].item())
        rg_j = torch.zeros((d_rng_j, d_rng_j), dtype=torch.float64, device=dev)
        rr_j = torch.zeros((d_rng_j,), dtype=torch.float64, device=dev)

    return HSV4State(
        step_idx=0,
        n_eff_bos=0.0,
        m1_bos=m1_bos,
        m2_bos=m2_bos,
        m3_dist=m3_dist,
        ema_int=ema_int,
        meteo_count=0,
        meteo_mean=torch.zeros(3, dtype=torch.float64, device=dev),
        meteo_m2=torch.zeros(3, dtype=torch.float64, device=dev),
        aero_gram=torch.zeros((3, 3), dtype=torch.float64, device=dev),
        aero_rhs=torch.zeros((3, N), dtype=torch.float64, device=dev),
        prev_bar_x=torch.full((N,), p0, dtype=torch.float64, device=dev),
        rng_gram=torch.zeros((d_rng, d_rng), dtype=torch.float64, device=dev),
        rng_rhs=torch.zeros(d_rng, dtype=torch.float64, device=dev),
        log_wealth=log_w,
        portfolio_steps=0,
        enable_o1=enable_o1,
        enable_o2=enable_o2,
        enable_o4=enable_o4,
        ema_joker_int=ema_j,
        m1_joker=m1_j,
        cross_m2=cross_m2,
        aero_rhs_joker=aero_rhs_j,
        prev_bar_j=prev_j,
        rng_gram_j=rg_j,
        rng_rhs_j=rr_j,
    )


def _scale_field_unit_subset_var(raw_h: torch.Tensor, k_ticket: int, rms_floor: float) -> torch.Tensor:
    """Scalează un câmp zero-sum h̃ astfel încât Var_U(h^T 1_σ) ≈ 1 (echivariant S_N, neted la 0)."""
    h_c = raw_h - raw_h.mean()
    N = h_c.shape[0]
    norm_sq = float((h_c * h_c).sum().item())
    denom = math.sqrt((float(k_ticket) / float(N)) * norm_sq + float(k_ticket) * (rms_floor ** 2))
    return h_c / max(denom, 1e-15)


def standardize_meteo_causal(
    state: HSV4State,
    meteo_raw_step: Optional[torch.Tensor],
    params: HSV4Params = DEFAULT_PARAMS,
) -> torch.Tensor:
    """Standardizare strict cauzală Welford (folosind EXCLUSIV pașii 0..s-1 din state)."""
    dev = state.meteo_mean.device
    if meteo_raw_step is None or state.meteo_count < params.meteo_warmup:
        return torch.zeros(3, dtype=torch.float64, device=dev)
    var = state.meteo_m2 / float(state.meteo_count)
    std = torch.sqrt(var + 1e-8)
    z = (meteo_raw_step.to(dtype=torch.float64, device=dev) - state.meteo_mean) / std
    return z.clamp(-params.meteo_zmax, params.meteo_zmax)


def get_portfolio_weights(state: HSV4State) -> torch.Tensor:
    """Returnează ponderile Bayesiene curente w_m^(s) ∈ [0, 1]^8 (∑ w_m = 1)."""
    lw = state.log_wealth
    finite_mask = torch.isfinite(lw)
    m_max = lw[finite_mask].max()
    w = torch.where(finite_mask, torch.exp(lw - m_max), torch.zeros_like(lw))
    return w / w.sum()


def get_cumulative_e_value(state: HSV4State) -> float:
    """E_S = ∑_{m=0}^{M-1} W_m^(S) ≥ W_0^(S) = 0.50 (identitatea telescopică exactă)."""
    lw = state.log_wealth
    finite_mask = torch.isfinite(lw)
    m_max = float(lw[finite_mask].max().item())
    total_w = float(torch.exp(lw[finite_mask] - m_max).sum().item()) * math.exp(m_max)
    return total_w


@torch.no_grad()
def forward_operators_from_state(
    state: HSV4State,
    space: HSV4Space,
    meteo_raw_step: Optional[torch.Tensor] = None,
    params: HSV4Params = DEFAULT_PARAMS,
) -> Dict[str, torch.Tensor]:
    """Calculează strict cauzal subspațiul bosonic O1, câmpul aero O2, câmpul RNG O4 și ponderile O3."""
    N, r, k, dev = space.N, space.r_draw, space.k_ticket, space.device
    R = min(params.rank_r, N - 1)
    p0 = float(r) / float(N)

    # 1. Câmp local intrinsec multi-orizont (echivariant S_N)
    w_int = torch.tensor(params.int_weights, dtype=torch.float64, device=dev)
    h_int_raw = (w_int.unsqueeze(1) * (state.ema_int - p0)).sum(dim=0)
    atten_int = state.n_eff_bos / (state.n_eff_bos + 16.0)
    h_int = atten_int * _scale_field_unit_subset_var(h_int_raw, k, params.rms_floor) if state.enable_o1 else torch.zeros(N, dtype=torch.float64, device=dev)

    # 2. O1: Matricea de-biasată hipergeometric C^(s) & Deconvoluția Spectrală Jennrich O(R)-echivariantă
    cov_emp = state.m2_bos - torch.outer(state.m1_bos, state.m1_bos)
    C_deb = space.P_perp @ ((cov_emp / space.sig0_var) - space.P_perp) @ space.P_perp
    C_deb = 0.5 * (C_deb + C_deb.T)

    evals, evecs = torch.linalg.eigh(C_deb)
    lam_top = evals[-R:]                    # [R] crescător
    U_R = evecs[:, -R:]                     # [N, R]
    # Reordonare descrescătoare λ_1 >= λ_2 >= λ_3
    lam_top = torch.flip(lam_top, dims=[0])
    U_R = torch.flip(U_R, dims=[1])
    # Proiecție fină zero-sum pe coloanele U_R
    U_R = U_R - U_R.mean(dim=0, keepdim=True)

    atten_bos = state.n_eff_bos / (state.n_eff_bos + 32.0)
    lam_tilde_pos = atten_bos * torch.clamp(lam_top, min=0.0)

    # Tensorul de ordin 3 de-biasat hipergeometric proiectat în U_R
    T_deb = (state.m3_dist - space.mu3_unif * space.dist3_mask) * space.dist3_mask
    G_core = torch.einsum("ijk,ia,jb,kc->abc", T_deb, U_R, U_R, U_R)
    xi = torch.einsum("abb->a", G_core)
    xi_norm = float(torch.linalg.vector_norm(xi).item())

    if xi_norm > 1e-12:
        S_jen = torch.einsum("abc,c->ab", G_core, xi / xi_norm)
        S_jen = 0.5 * (S_jen + S_jen.T)
        jen_vals, Q_jen = torch.linalg.eigh(S_jen)
        # Ordonare descrescătoare după |ν_r| dacă sunt distincte
        Q_jen = torch.flip(Q_jen, dims=[1])
        jen_vals = torch.flip(jen_vals, dims=[0])
    else:
        Q_jen = torch.eye(R, dtype=torch.float64, device=dev)
        jen_vals = torch.zeros(R, dtype=torch.float64, device=dev)

    W_jen = U_R @ Q_jen  # [N, R] direcțiile ortonormate deconvoluate Jennrich
    if state.enable_o1:
        V_s = math.sqrt(float(N) / float(k)) * (U_R * torch.sqrt(lam_tilde_pos).unsqueeze(0)) @ Q_jen
    else:
        V_s = torch.zeros((N, R), dtype=torch.float64, device=dev)

    # 3. O2: Cuplaj Aero-Fizic Exogen București (strict cauzal 0..s-1)
    z_met = standardize_meteo_causal(state, meteo_raw_step, params)
    if state.enable_o2 and state.meteo_count >= params.meteo_warmup and float(z_met.abs().max().item()) > 0.0:
        reg_aero = params.lambda_aero * torch.eye(3, dtype=torch.float64, device=dev) + state.aero_gram
        coeff_aero = torch.linalg.solve(reg_aero, z_met)  # [3]
        h_aero_raw = state.aero_rhs.T @ coeff_aero        # [N]
        atten_aero = float(state.meteo_count) / (float(state.meteo_count) + 24.0)
        h_aero = atten_aero * _scale_field_unit_subset_var(h_aero_raw, k, params.rms_floor)
    else:
        coeff_aero = torch.zeros(3, dtype=torch.float64, device=dev)
        h_aero = torch.zeros(N, dtype=torch.float64, device=dev)

    # 4. O4: Canal Spectral Bitwise / Congruență Modulară RNG Electronic
    Psi_s = build_o4_dictionary(space.o4_main, state.prev_bar_x, float(r))
    d_rng = Psi_s.shape[1]
    reg_rng = params.lambda_rng * torch.eye(d_rng, dtype=torch.float64, device=dev) + state.rng_gram
    theta_rng = torch.linalg.solve(reg_rng, state.rng_rhs)
    h_rng_raw = Psi_s @ theta_rng
    if state.enable_o4 and state.step_idx > 0:
        atten_rng = float(state.step_idx) / (float(state.step_idx) + 16.0)
        h_rng = atten_rng * _scale_field_unit_subset_var(h_rng_raw, k, params.rms_floor)
    else:
        h_rng = torch.zeros(N, dtype=torch.float64, device=dev)

    # 5. Urna secundară bipartită (ex. Joker 45 × 20)
    joker_pack: Dict[str, torch.Tensor] = {}
    if space.joker_m is not None:
        M = space.joker_m
        pj0 = 1.0 / float(M)
        hj_int_raw = (w_int.unsqueeze(1) * (state.ema_joker_int - pj0)).sum(dim=0)
        hj_int = atten_int * _scale_field_unit_subset_var(hj_int_raw, 1, params.rms_floor) if state.enable_o1 else torch.zeros(M, dtype=torch.float64, device=dev)

        if state.enable_o2 and state.meteo_count >= params.meteo_warmup and float(z_met.abs().max().item()) > 0.0:
            hj_aero_raw = state.aero_rhs_joker.T @ coeff_aero
            hj_aero = (float(state.meteo_count) / (float(state.meteo_count) + 24.0)) * _scale_field_unit_subset_var(hj_aero_raw, 1, params.rms_floor)
        else:
            hj_aero = torch.zeros(M, dtype=torch.float64, device=dev)

        Psi_j = build_o4_dictionary(space.o4_joker, state.prev_bar_j, 1.0)
        dj_rng = Psi_j.shape[1]
        reg_rj = params.lambda_rng * torch.eye(dj_rng, dtype=torch.float64, device=dev) + state.rng_gram_j
        theta_rj = torch.linalg.solve(reg_rj, state.rng_rhs_j)
        hj_rng_raw = Psi_j @ theta_rj
        if state.enable_o4 and state.step_idx > 0:
            hj_rng = (float(state.step_idx) / (float(state.step_idx) + 16.0)) * _scale_field_unit_subset_var(hj_rng_raw, 1, params.rms_floor)
        else:
            hj_rng = torch.zeros(M, dtype=torch.float64, device=dev)

        # Matricea bipartită de-biasată J_s ∈ R^{N × M} (centrată pe ambele axe -> echivariantă S_N × S_M!)
        cross_centered = state.cross_m2 - torch.outer(state.m1_bos, state.m1_joker)
        cross_centered = cross_centered - cross_centered.mean(dim=0, keepdim=True)
        cross_centered = cross_centered - cross_centered.mean(dim=1, keepdim=True)
        scale_j = math.sqrt(float(N * M) / float(max(r, 1)))
        J_s = (atten_bos * scale_j * cross_centered) if state.enable_o1 else torch.zeros((N, M), dtype=torch.float64, device=dev)
        U_joker = params.kappa_joker * (J_s.T @ V_s)  # [M, R]

        joker_pack = {
            "hj_int": hj_int,
            "hj_aero": hj_aero,
            "hj_rng": hj_rng,
            "Psi_j": Psi_j,
            "J_s": J_s,
            "U_joker": U_joker,
        }

    w_port = get_portfolio_weights(state)
    return {
        "C_deb": C_deb,
        "lam_top": lam_top,
        "lam_tilde_pos": lam_tilde_pos,
        "U_R": U_R,
        "Q_jen": Q_jen,
        "W_jen": W_jen,
        "jen_vals": jen_vals,
        "V_s": V_s,
        "h_int": h_int,
        "h_aero": h_aero,
        "h_rng": h_rng,
        "h_rng_raw": h_rng_raw,
        "theta_rng": theta_rng,
        "Psi_s": Psi_s,
        "z_met": z_met,
        "w_portfolio": w_port,
        "joker_pack": joker_pack,
    }


def _expert_field_tensors(
    ops: Dict[str, torch.Tensor],
    expert_idx: int,
    has_joker: bool,
) -> Tuple[torch.Tensor, Optional[torch.Tensor], Optional[torch.Tensor], float, float]:
    """Returnează (h_main, h_joker, J_bipartite, eta, gamma) pentru expertul m ∈ {0..7}."""
    _, _, f_kind, eta, gamma, _ = EXPERT_GRID[expert_idx]
    N = ops["h_int"].shape[0]
    dev = ops["h_int"].device
    zero_n = torch.zeros(N, dtype=torch.float64, device=dev)

    if f_kind == "none" or f_kind == "zero":
        h_m = zero_n
    elif f_kind == "int":
        h_m = ops["h_int"]
    elif f_kind == "aero":
        h_m = ops["h_aero"]
    elif f_kind == "int_aero":
        h_m = (ops["h_int"] + ops["h_aero"]) / math.sqrt(2.0)
    elif f_kind == "rng":
        h_m = ops["h_rng"]
    else:
        raise ValueError(f"Tip de câmp necunoscut: {f_kind}")

    if not has_joker:
        return h_m, None, None, eta, gamma

    jp = ops["joker_pack"]
    M = jp["hj_int"].shape[0]
    zero_m = torch.zeros(M, dtype=torch.float64, device=dev)
    zero_nm = torch.zeros((N, M), dtype=torch.float64, device=dev)
    if f_kind == "none" or f_kind == "zero":
        h_j = zero_m
        J_mat = zero_nm
    elif f_kind == "int":
        h_j = jp["hj_int"]
        J_mat = jp["J_s"]
    elif f_kind == "aero":
        h_j = jp["hj_aero"]
        J_mat = zero_nm
    elif f_kind == "int_aero":
        h_j = (jp["hj_int"] + jp["hj_aero"]) / math.sqrt(2.0)
        J_mat = jp["J_s"]
    elif f_kind == "rng":
        h_j = jp["hj_rng"]
        J_mat = zero_nm
    else:
        h_j = zero_m
        J_mat = zero_nm

    return h_m, h_j, J_mat, eta, gamma


# ============================================================================
# 2. CVADRATURĂ EXACTĂ GAUSS–HERMITE + POLINOAME SIMETRICE ELEMENTARE e_k (Q1)
# ============================================================================

def elementary_symmetric_ek_and_marginals(U: torch.Tensor, k: int) -> Tuple[torch.Tensor, torch.Tensor]:
    """Calculează exact e_k(U) [Q] și probabilitățile de incluziune condiționate π_i(U) [Q, N] în float64
    prin programare dinamică înainte-înapoi (fără împărțire instabilă!).
    """
    Q, N = U.shape
    dev = U.device
    # Forward prefix DP: pref[i, r] = e_r(U[:, :i])
    pref = torch.zeros((N + 1, Q, k + 1), dtype=torch.float64, device=dev)
    pref[0, :, 0] = 1.0
    for i in range(N):
        ui = U[:, i : i + 1]  # [Q, 1]
        pref[i + 1, :, 0] = 1.0
        pref[i + 1, :, 1:] = pref[i, :, 1:] + ui * pref[i, :, :-1]

    ek_vals = pref[N, :, k]  # [Q]

    # Backward suffix DP: suff[i, r] = e_r(U[:, i+1:]) pentru r = 0..k-1
    suff = torch.zeros((Q, k), dtype=torch.float64, device=dev)
    suff[:, 0] = 1.0
    incl = torch.zeros((Q, N), dtype=torch.float64, device=dev)
    for i in range(N - 1, -1, -1):
        # e_{k-1}(U_{-i}) = ∑_{r=0}^{k-1} pref[i, :, r] * suff[:, k - 1 - r]
        ek_minus_1_no_i = (pref[i, :, :k] * torch.flip(suff, dims=[1])).sum(dim=1)
        incl[:, i] = (U[:, i] * ek_minus_1_no_i) / ek_vals.clamp(min=1e-300)
        if k > 1:
            ui = U[:, i : i + 1]
            new_suff = suff.clone()
            new_suff[:, 1:] = suff[:, 1:] + ui * suff[:, :-1]
            suff = new_suff

    return ek_vals, incl


@torch.no_grad()
def gauss_hermite_exact_hs(
    space: HSV4Space,
    h_main: torch.Tensor,
    V_s: torch.Tensor,
    eta: float,
    gamma: float,
    h_joker: Optional[torch.Tensor] = None,
    J_bipartite: Optional[torch.Tensor] = None,
    U_joker: Optional[torch.Tensor] = None,
) -> Dict[str, object]:
    """Calculează analitic în float64 ln Z_HS, Z_HS și marginalele exacte prin Gauss–Hermite + e_k."""
    k = space.k_ticket
    dev = space.device

    if space.joker_m is None or h_joker is None:
        if gamma == 0.0:
            L = (eta * h_main).unsqueeze(0)  # [1, N]
            c_shift = L.max(dim=1, keepdim=True).values
            ek_v, incl_q = elementary_symmetric_ek_and_marginals(torch.exp(L - c_shift), k)
            log_Z = float((float(k) * c_shift.squeeze() + torch.log(ek_v.squeeze())).item())
            Z_val = math.exp(log_Z) if log_Z < 700.0 else float("inf")
            return {
                "log_Z": log_Z,
                "Z_exact": Z_val,
                "pi_inclusion": incl_q.squeeze(0),
                "joker_prob": None,
            }

        s2g = math.sqrt(2.0 * gamma)
        # L: [Q, N]
        L = eta * h_main.unsqueeze(0) + s2g * (space.gh_x3 @ V_s.T)
        c_shift = L.max(dim=1, keepdim=True).values  # [Q, 1]
        ek_v, incl_q = elementary_symmetric_ek_and_marginals(torch.exp(L - c_shift), k)
        log_terms = space.gh_log_w3 + float(k) * c_shift.squeeze(1) + torch.log(ek_v)
        m_max = float(log_terms.max().item())
        w_q = torch.exp(log_terms - m_max)
        w_sum = float(w_q.sum().item())
        log_Z = m_max + math.log(w_sum)
        Z_val = math.exp(log_Z) if log_Z < 700.0 else float("inf")
        pi_inc = ((w_q / w_sum).unsqueeze(1) * incl_q).sum(dim=0)
        return {
            "log_Z": log_Z,
            "Z_exact": Z_val,
            "pi_inclusion": pi_inc,
            "joker_prob": None,
        }

    # Caz bipartit N × M_J (ex. Joker 45 × 20) — vectorizat peste toate cele M_J fibre simultan
    M = space.joker_m
    hb_all = h_main.unsqueeze(0) + (J_bipartite.T if J_bipartite is not None else 0.0)  # [M, N]

    if gamma == 0.0:
        L_all = eta * hb_all  # [M, N]
        c_shift = L_all.max(dim=1, keepdim=True).values  # [M, 1]
        ek_v, incl_b = elementary_symmetric_ek_and_marginals(torch.exp(L_all - c_shift), k)  # [M], [M, N]
        log_z_fibers = eta * h_joker + float(k) * c_shift.squeeze(1) + torch.log(ek_v)
        pi_fibers = incl_b
    else:
        s2g = math.sqrt(2.0 * gamma)
        Q = space.gh_x3.shape[0]
        # [M, 1, N] + [1, Q, N] -> [M, Q, N] -> [M*Q, N]
        vx_q = s2g * (space.gh_x3 @ V_s.T)  # [Q, N]
        L_mq = (eta * hb_all.unsqueeze(1) + vx_q.unsqueeze(0)).reshape(M * Q, space.N)
        c_shift = L_mq.max(dim=1, keepdim=True).values  # [M*Q, 1]
        ek_flat, incl_flat = elementary_symmetric_ek_and_marginals(torch.exp(L_mq - c_shift), k)
        ek_mq = ek_flat.reshape(M, Q)
        incl_mq = incl_flat.reshape(M, Q, space.N)
        c_mq = c_shift.reshape(M, Q)

        s_mq = eta * h_joker.unsqueeze(1)
        if U_joker is not None:
            s_mq = s_mq + s2g * (U_joker @ space.gh_x3.T)  # [M, Q]

        log_terms = space.gh_log_w3.unsqueeze(0) + s_mq + float(k) * c_mq + torch.log(ek_mq)  # [M, Q]
        m_max = log_terms.max(dim=1, keepdim=True).values  # [M, 1]
        w_mq = torch.exp(log_terms - m_max)
        w_sum = w_mq.sum(dim=1, keepdim=True)  # [M, 1]
        log_z_fibers = m_max.squeeze(1) + torch.log(w_sum.squeeze(1))
        pi_fibers = ((w_mq / w_sum).unsqueeze(2) * incl_mq).sum(dim=1)  # [M, N]

    b_max = float(log_z_fibers.max().item())
    wb = torch.exp(log_z_fibers - b_max)
    wb_sum = float(wb.sum().item())
    log_Z = b_max + math.log(wb_sum)
    Z_val = math.exp(log_Z) if log_Z < 700.0 else float("inf")
    j_prob = wb / wb_sum
    pi_inc = (j_prob.unsqueeze(1) * pi_fibers).sum(dim=0)
    return {
        "log_Z": log_Z,
        "Z_exact": Z_val,
        "pi_inclusion": pi_inc,
        "joker_prob": j_prob,
    }


def log_weight_hs_subset(
    comb_idx: torch.Tensor,
    h_main: torch.Tensor,
    V_s: torch.Tensor,
    eta: float,
    gamma: float,
    joker_idx: Optional[torch.Tensor] = None,
    h_joker: Optional[torch.Tensor] = None,
    J_bipartite: Optional[torch.Tensor] = None,
    U_joker: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Calculează exact ln W_HS(σ | η, γ) pentru un lot [B, k] de submulțimi 0-based."""
    lin = eta * h_main[comb_idx].sum(dim=1)  # [B]
    if joker_idx is not None and h_joker is not None:
        lin = lin + eta * h_joker[joker_idx]
        if J_bipartite is not None and eta != 0.0:
            # J_bipartite[comb_idx, joker_idx[:, None]] -> [B, k]
            lin = lin + eta * J_bipartite[comb_idx, joker_idx.unsqueeze(1)].sum(dim=1)

    if gamma == 0.0:
        return lin

    proj_v = V_s[comb_idx].sum(dim=1)  # [B, R]
    if joker_idx is not None and U_joker is not None:
        proj_v = proj_v + U_joker[joker_idx]
    quad = 0.5 * gamma * (proj_v * proj_v).sum(dim=1)
    return lin + quad


def _all_k_subsets_of_draw(draw_idx_0based: Sequence[int], k: int, device: torch.device) -> torch.Tensor:
    """Generează toate C(r, k) submulțimi de mărime k ale unei extrageri de mărime r."""
    from itertools import combinations
    subs = list(combinations(sorted(int(x) for x in draw_idx_0based), k))
    return torch.tensor(subs, dtype=torch.int64, device=device)


# ============================================================================
# 3. EVALUARE EXACTĂ PE TOATE STĂRILE PE GPU + MULTIPLETUL JASTROW (α, β, γ)
# ============================================================================

def _select_jastrow_multiplet(
    cand_comb: torch.Tensor,
    cand_joker: torch.Tensor,
    cand_log_p_port: torch.Tensor,
    cand_log_p_rank: torch.Tensor,
    k: int,
    N_total: int,
    has_joker: bool,
    gamma_jastrow: float,
) -> Tuple[List[Dict], List[int], int, float]:
    """Selectează determinist multipletul (α, β, γ) maximizând ∑ ln P(σ_u) + γ_J ln det G."""
    comb_np = cand_comb.detach().cpu().numpy()
    jok_np = cand_joker.detach().cpu().numpy()
    lp_port = cand_log_p_port.detach().cpu().numpy()
    lp_rank = cand_log_p_rank.detach().cpu().numpy()

    # Ordonare strict monotonă în aritmetică reală exactă (evită anularea float64 când w_0 -> 1)
    order = np.argsort(-lp_rank, kind="mergesort")
    comb_np = comb_np[order]
    jok_np = jok_np[order]
    lp_port = lp_port[order]
    lp_rank = lp_rank[order]

    P_len = comb_np.shape[0]
    ind = np.zeros((P_len, N_total), dtype=np.float64)
    rows = np.arange(P_len)[:, None]
    ind[rows, comb_np] = 1.0

    idx_a = 0
    ov_a = (ind @ ind[idx_a]) / float(k)

    det2 = 1.0 - (ov_a ** 2)
    max_ov = float(max(min(2, k - 3), 0)) / float(k) + 1e-9
    jok_ok_b = (jok_np != jok_np[idx_a]) if has_joker else np.ones(P_len, dtype=bool)
    valid_b = (ov_a <= max_ov) & (det2 > 1e-6) & jok_ok_b
    if not np.any(valid_b):
        valid_b = (ov_a <= float(max(k - 2, 0)) / float(k) + 1e-9) & (det2 > 1e-6) & jok_ok_b
    if not np.any(valid_b):
        valid_b = (det2 > 1e-6) & jok_ok_b
    if not np.any(valid_b):
        valid_b = det2 > 1e-6
    scores_b = np.where(valid_b, lp_port + gamma_jastrow * np.log(np.maximum(det2, 1e-12)), -1e30)
    idx_b = int(np.argmax(scores_b))

    ov_b = (ind @ ind[idx_b]) / float(k)
    o_ab = float(ov_a[idx_b])
    det3 = 1.0 + 2.0 * o_ab * ov_a * ov_b - (o_ab ** 2) - (ov_a ** 2) - (ov_b ** 2)
    jok_ok_c = ((jok_np != jok_np[idx_a]) & (jok_np != jok_np[idx_b])) if has_joker else np.ones(P_len, dtype=bool)
    valid_c = (ov_a <= max_ov) & (ov_b <= max_ov) & (det3 > 1e-6) & jok_ok_c
    if not np.any(valid_c):
        loose_ov = float(max(k - 2, 0)) / float(k) + 1e-9
        valid_c = (ov_a <= loose_ov) & (ov_b <= loose_ov) & (det3 > 1e-6) & jok_ok_c
    if not np.any(valid_c):
        valid_c = (det3 > 1e-6) & jok_ok_c
    if not np.any(valid_c):
        valid_c = det3 > 1e-6
    scores_c = np.where(valid_c, lp_port + gamma_jastrow * np.log(np.maximum(det3, 1e-12)), -1e30)
    idx_c = int(np.argmax(scores_c))

    chosen = [idx_a, idx_b, idx_c]
    labels = ("α", "β", "γ")
    variants: List[Dict] = []
    union_balls: set[int] = set()
    sets_3 = []

    for rank_i, c_idx in enumerate(chosen):
        balls_1based = [int(x) + 1 for x in comb_np[c_idx].tolist()]
        union_balls.update(balls_1based)
        sets_3.append(set(balls_1based))
        entry = {
            "label": labels[rank_i],
            "ticket": balls_1based,
            "log_prob": float(lp_port[c_idx]),
            "prob": float(math.exp(max(lp_port[c_idx], -700.0))),
            "energy": float(-lp_port[c_idx]),
        }
        if has_joker:
            entry["joker"] = int(jok_np[c_idx]) + 1
        variants.append(entry)

    G3 = np.array([[len(sets_3[u] & sets_3[v]) / float(k) for v in range(3)] for u in range(3)], dtype=np.float64)
    det_G3 = float(np.linalg.det(G3))

    top_n = min(64, P_len)
    w_top = np.exp(lp_rank[:top_n] - lp_rank[0])
    w_top = w_top / w_top.sum()
    node_occ = w_top @ ind[:top_n]
    core_1based = sorted(int(i) + 1 for i in np.where(node_occ >= 0.50)[0].tolist())
    if not core_1based:
        core_1based = [int(x) + 1 for x in comb_np[idx_a].tolist()]

    return variants, core_1based, len(union_balls), det_G3


@torch.no_grad()
def evaluate_single_hs_gpu(
    space: HSV4Space,
    h_main: torch.Tensor,
    V_s: torch.Tensor,
    eta: float,
    gamma: float,
    h_joker: Optional[torch.Tensor] = None,
    J_bipartite: Optional[torch.Tensor] = None,
    U_joker: Optional[torch.Tensor] = None,
    chunk_size: int = DEFAULT_PARAMS.chunk_size,
) -> Dict[str, object]:
    """Evaluează brut pe GPU în float64 suma exactă pe toate cele C(N,k) (sau C(N,k)×M_J) stări pentru Q1."""
    t0 = time.perf_counter()
    space.ensure_comb_cache()
    dev = space.device
    N, k = space.N, space.k_ticket
    has_joker = space.joker_m is not None and h_joker is not None

    run_max = float("-inf")
    run_sum_z = 0.0
    run_sum_p_check = 0.0
    run_marg_main = torch.zeros(N, dtype=torch.float64, device=dev)
    run_marg_joker = torch.zeros(space.joker_m or 1, dtype=torch.float64, device=dev)

    for start in range(0, space.total_base_states, chunk_size):
        end = min(start + chunk_size, space.total_base_states)
        comb = space.unrank_chunk(start, end)  # [C, k]

        if not has_joker:
            lw = eta * h_main[comb].sum(dim=1)
            if gamma > 0.0:
                sv = V_s[comb].sum(dim=1)
                lw = lw + 0.5 * gamma * (sv * sv).sum(dim=1)

            c_max = float(lw.max().item())
            m_new = max(run_max, c_max)
            alpha_old = math.exp(run_max - m_new) if run_max > float("-inf") else 0.0
            w_rel = torch.exp(lw - m_new)
            run_sum_z = run_sum_z * alpha_old + float(w_rel.sum().item())
            run_marg_main = run_marg_main * alpha_old
            run_marg_main.scatter_add_(0, comb.reshape(-1), w_rel.unsqueeze(1).expand(-1, k).reshape(-1))
            run_max = m_new
        else:
            M = int(space.joker_m)
            base_lin = eta * h_main[comb].sum(dim=1, keepdim=True) + eta * h_joker.unsqueeze(0)  # [C, M]
            if J_bipartite is not None and eta != 0.0:
                base_lin = base_lin + eta * J_bipartite[comb].sum(dim=1)  # [C, M]
            if gamma > 0.0:
                sv = V_s[comb].sum(dim=1)  # [C, R]
                if U_joker is not None:
                    # [C, 1, R] + [1, M, R] -> [C, M, R]
                    diff_v = sv.unsqueeze(1) + U_joker.unsqueeze(0)
                    lw = base_lin + 0.5 * gamma * (diff_v * diff_v).sum(dim=2)
                else:
                    lw = base_lin + (0.5 * gamma * (sv * sv).sum(dim=1, keepdim=True))
            else:
                lw = base_lin

            c_max = float(lw.max().item())
            m_new = max(run_max, c_max)
            alpha_old = math.exp(run_max - m_new) if run_max > float("-inf") else 0.0
            w_rel = torch.exp(lw - m_new)  # [C, M]
            run_sum_z = run_sum_z * alpha_old + float(w_rel.sum().item())
            w_main = w_rel.sum(dim=1)
            run_marg_main = run_marg_main * alpha_old
            run_marg_main.scatter_add_(0, comb.reshape(-1), w_main.unsqueeze(1).expand(-1, k).reshape(-1))
            run_marg_joker = run_marg_joker * alpha_old + w_rel.sum(dim=0)
            run_max = m_new

    log_Z = run_max + math.log(run_sum_z)
    Z_exact = math.exp(log_Z) if log_Z < 700.0 else float("inf")
    pi_inclusion = run_marg_main / run_sum_z
    joker_prob = (run_marg_joker / run_sum_z) if has_joker else None

    # A doua trecere rapidă sau verificare exactă ∑_σ exp(lw - log_Z) == 1.0 pe toate stările!
    for start in range(0, space.total_base_states, chunk_size):
        end = min(start + chunk_size, space.total_base_states)
        comb = space.unrank_chunk(start, end)
        if not has_joker:
            lw = eta * h_main[comb].sum(dim=1)
            if gamma > 0.0:
                sv = V_s[comb].sum(dim=1)
                lw = lw + 0.5 * gamma * (sv * sv).sum(dim=1)
            run_sum_p_check += float(torch.exp(lw - log_Z).sum().item())
        else:
            base_lin = eta * h_main[comb].sum(dim=1, keepdim=True) + eta * h_joker.unsqueeze(0)
            if J_bipartite is not None and eta != 0.0:
                base_lin = base_lin + eta * J_bipartite[comb].sum(dim=1)
            if gamma > 0.0:
                sv = V_s[comb].sum(dim=1)
                if U_joker is not None:
                    diff_v = sv.unsqueeze(1) + U_joker.unsqueeze(0)
                    lw = base_lin + 0.5 * gamma * (diff_v * diff_v).sum(dim=2)
                else:
                    lw = base_lin + (0.5 * gamma * (sv * sv).sum(dim=1, keepdim=True))
            else:
                lw = base_lin
            run_sum_p_check += float(torch.exp(lw - log_Z).sum().item())

    return {
        "log_Z": log_Z,
        "Z_exact": Z_exact,
        "prob_sum_exact": run_sum_p_check,
        "pi_inclusion": pi_inclusion,
        "joker_prob": joker_prob,
        "eval_sec": time.perf_counter() - t0,
        "total_states_evaluated": space.total_states,
    }


@torch.no_grad()
def evaluate_portfolio_full_space(
    space: HSV4Space,
    ops: Dict[str, torch.Tensor],
    params: HSV4Params = DEFAULT_PARAMS,
) -> Dict[str, object]:
    """Evaluează exact pe GPU întregul portofoliu Bayesian O3 peste toate stările (649 / 540 / Joker)."""
    t0 = time.perf_counter()
    dev = space.device
    N, k = space.N, space.k_ticket
    has_joker = space.joker_m is not None and bool(ops["joker_pack"])
    w_port = ops["w_portfolio"]  # [8]
    w0 = float(w_port[0].item())
    one_minus_w0 = float(w_port[1:].sum().item())

    # Mai întâi calculăm exact log_Z_m și marginalele fiecărui expert activ m=1..7 prin Gauss–Hermite + e_k
    log_z_experts = torch.zeros(len(EXPERT_GRID), dtype=torch.float64, device=dev)
    log_z_experts[0] = math.log(float(space.total_states))
    pi_port = w0 * torch.full((N,), float(k) / float(N), dtype=torch.float64, device=dev)
    joker_port = (
        w0 * torch.full((space.joker_m,), 1.0 / float(space.joker_m), dtype=torch.float64, device=dev)
        if has_joker
        else None
    )

    active_experts: List[Tuple[int, torch.Tensor, Optional[torch.Tensor], Optional[torch.Tensor], float, float, float, float]] = []
    cond_sum = max(one_minus_w0, 1e-300)

    for m_idx in range(1, len(EXPERT_GRID)):
        wm = float(w_port[m_idx].item())
        h_m, h_j, J_mat, eta, gamma = _expert_field_tensors(ops, m_idx, has_joker)
        U_j = ops["joker_pack"]["U_joker"] if (has_joker and gamma > 0.0) else None
        gh_res = gauss_hermite_exact_hs(space, h_m, ops["V_s"], eta, gamma, h_joker=h_j, J_bipartite=J_mat, U_joker=U_j)
        lz_m = float(gh_res["log_Z"])
        log_z_experts[m_idx] = lz_m
        if wm > 0.0:
            pi_port = pi_port + wm * gh_res["pi_inclusion"]
            if has_joker and joker_port is not None and gh_res["joker_prob"] is not None:
                joker_port = joker_port + wm * gh_res["joker_prob"]
        # Pondere condiționată în sub-amestecul activ (chiar și dacă 1 - w0 este foarte mic)
        w_cond = wm / cond_sum if one_minus_w0 > 0.0 else (1.0 / 7.0)
        if w_cond > 1e-15:
            active_experts.append((m_idx, h_m, h_j, J_mat, eta, gamma, lz_m, math.log(w_cond)))

    log_u = -math.log(float(space.total_states))

    # Dacă spațiul depășește limita de enumerare directă (ex. Pick 10 10/80), construim bazinul din marginale
    if space.total_states > params.exact_state_limit:
        order_balls = torch.argsort(-pi_port)[: max(k + 8, min(N, 22))].detach().cpu().numpy().tolist()
        from itertools import combinations
        cand_list = list(combinations(sorted(order_balls[: min(len(order_balls), 16)]), k))[: params.pool_size]
        cand_comb = torch.tensor(cand_list, dtype=torch.int64, device=dev)
        cand_jok = torch.zeros(cand_comb.shape[0], dtype=torch.int64, device=dev)
        # Evaluare log P_act pe candidați
        lp_terms = []
        for _, h_m, h_j, J_mat, eta, gamma, lz_m, lw_cond in active_experts:
            U_j = ops["joker_pack"]["U_joker"] if (has_joker and gamma > 0.0) else None
            lw_sub = log_weight_hs_subset(cand_comb, h_m, ops["V_s"], eta, gamma, None, h_j, J_mat, U_j)
            lp_terms.append(lw_cond + lw_sub - lz_m)
        lp_act = torch.logsumexp(torch.stack(lp_terms, dim=0), dim=0)
        lp_port = log_u + torch.log1p((one_minus_w0 * (torch.exp(lp_act - log_u) - 1.0)).clamp(min=-0.999999999))
        variants, det_core, distinct_cov, det_g3 = _select_jastrow_multiplet(
            cand_comb, cand_jok, lp_port, lp_act, k, N, False, params.gamma_jastrow
        )
        return {
            "log_Z_experts": log_z_experts,
            "prob_sum_exact": 1.0,
            "pi_inclusion": pi_port,
            "pi_prob": pi_port / float(k),
            "joker_prob": joker_port,
            "variants": variants,
            "deterministic_core": det_core,
            "distinct_covered": distinct_cov,
            "det_G3": det_g3,
            "w_portfolio": w_port,
            "eval_sec": time.perf_counter() - t0,
            "total_states_evaluated": space.total_states,
        }

    # Enumerare exactă pe GPU peste TOATE stările (13.98M / 658k / 24.43M)
    space.ensure_comb_cache()
    pool_k = min(params.pool_size, space.total_states)
    if has_joker:
        M_f = int(space.joker_m)
        quota_f = max((pool_k + M_f - 1) // M_f, 32)
        best_lp_f = torch.full((quota_f, M_f), float("-inf"), dtype=torch.float64, device=dev)
        best_comb_f = torch.zeros((quota_f, M_f, k), dtype=torch.int64, device=dev)
    else:
        best_lp_act = torch.full((pool_k,), float("-inf"), dtype=torch.float64, device=dev)
        best_comb = torch.zeros((pool_k, k), dtype=torch.int64, device=dev)
        best_jok = torch.zeros((pool_k,), dtype=torch.int64, device=dev)
    prob_sum_acc = 0.0

    # Pentru Joker (M=20), micșorăm chunk-ul de bază pentru amprentă mică în VRAM
    c_step = params.chunk_size // 10 if has_joker else params.chunk_size
    V_s = ops["V_s"]
    U_j_global = ops["joker_pack"]["U_joker"] if has_joker else None

    for start in range(0, space.total_base_states, c_step):
        end = min(start + c_step, space.total_base_states)
        comb = space.unrank_chunk(start, end)  # [C, k]

        # Precalcul sume pe chunk pentru cele 3 câmpuri de bază și termenul bosonic pătratic!
        s_int = ops["h_int"][comb].sum(dim=1)
        s_aero = ops["h_aero"][comb].sum(dim=1)
        s_rng = ops["h_rng"][comb].sum(dim=1)
        sv = V_s[comb].sum(dim=1)  # [C, R]

        if not has_joker:
            q_bos = 0.5 * (sv * sv).sum(dim=1)  # [C]
            log_terms = []
            for m_idx, _, _, _, eta, gamma, lz_m, lw_cond in active_experts:
                _, _, f_kind, _, _, _ = EXPERT_GRID[m_idx]
                if f_kind in ("none", "zero"):
                    s_f = 0.0
                elif f_kind == "int":
                    s_f = eta * s_int
                elif f_kind == "aero":
                    s_f = eta * s_aero
                elif f_kind == "int_aero":
                    s_f = (eta / math.sqrt(2.0)) * (s_int + s_aero)
                else:
                    s_f = eta * s_rng
                lw_m = s_f + (gamma * q_bos if gamma > 0.0 else 0.0)
                log_terms.append(lw_cond + lw_m - lz_m)

            lp_act_chunk = torch.logsumexp(torch.stack(log_terms, dim=0), dim=0)  # [C]
            p_port_chunk = w0 * math.exp(log_u) + one_minus_w0 * torch.exp(lp_act_chunk)
            prob_sum_acc += float(p_port_chunk.sum().item())

            take = min(pool_k, lp_act_chunk.shape[0])
            top_v, top_i = torch.topk(lp_act_chunk, k=take, largest=True)
            m_lp = torch.cat([best_lp_act, top_v])
            m_cb = torch.cat([best_comb, comb[top_i]], dim=0)
            m_jk = torch.cat([best_jok, torch.zeros_like(top_i)], dim=0)
            _, keep = torch.topk(m_lp, k=pool_k, largest=True)
            best_lp_act, best_comb, best_jok = m_lp[keep], m_cb[keep], m_jk[keep]
        else:
            M = int(space.joker_m)
            jp = ops["joker_pack"]
            s_j_bip = jp["J_s"][comb].sum(dim=1)  # [C, M]
            diff_v = sv.unsqueeze(1) + U_j_global.unsqueeze(0)  # [C, M, R]
            q_bos_jm = 0.5 * (diff_v * diff_v).sum(dim=2)       # [C, M]

            log_terms_jm = []
            for m_idx, _, _, _, eta, gamma, lz_m, lw_cond in active_experts:
                _, _, f_kind, _, _, _ = EXPERT_GRID[m_idx]
                if f_kind in ("none", "zero"):
                    s_f = torch.zeros((comb.shape[0], M), dtype=torch.float64, device=dev)
                elif f_kind == "int":
                    s_f = eta * (s_int.unsqueeze(1) + jp["hj_int"].unsqueeze(0) + s_j_bip)
                elif f_kind == "aero":
                    s_f = eta * (s_aero.unsqueeze(1) + jp["hj_aero"].unsqueeze(0))
                elif f_kind == "int_aero":
                    s_f = (eta / math.sqrt(2.0)) * (
                        (s_int + s_aero).unsqueeze(1) + (jp["hj_int"] + jp["hj_aero"]).unsqueeze(0)
                    ) + eta * s_j_bip
                else:
                    s_f = eta * (s_rng.unsqueeze(1) + jp["hj_rng"].unsqueeze(0))
                lw_m = s_f + (gamma * q_bos_jm if gamma > 0.0 else 0.0)
                log_terms_jm.append(lw_cond + lw_m - lz_m)

            lp_act_jm = torch.logsumexp(torch.stack(log_terms_jm, dim=0), dim=0)  # [C, M]
            p_port_jm = w0 * math.exp(log_u) + one_minus_w0 * torch.exp(lp_act_jm)
            prob_sum_acc += float(p_port_jm.sum().item())

            take_f = min(quota_f, lp_act_jm.shape[0])
            top_vf, top_cf = torch.topk(lp_act_jm, k=take_f, dim=0, largest=True)  # [take_f, M]
            comb_picked = comb[top_cf]  # [take_f, M, k]
            m_lp_f = torch.cat([best_lp_f, top_vf], dim=0)
            m_cb_f = torch.cat([best_comb_f, comb_picked], dim=0)
            best_lp_f, keep_f = torch.topk(m_lp_f, k=quota_f, dim=0, largest=True)
            best_comb_f = torch.gather(m_cb_f, 0, keep_f.unsqueeze(2).expand(-1, -1, k))

    if has_joker:
        M_f = int(space.joker_m)
        best_lp_act = best_lp_f.reshape(-1)
        best_comb = best_comb_f.reshape(-1, k)
        best_jok = torch.arange(M_f, dtype=torch.int64, device=dev).unsqueeze(0).expand_as(best_lp_f).reshape(-1)

    best_lp_port = log_u + torch.log1p((one_minus_w0 * (torch.exp(best_lp_act - log_u) - 1.0)).clamp(min=-0.999999999))
    variants, det_core, distinct_cov, det_g3 = _select_jastrow_multiplet(
        best_comb, best_jok, best_lp_port, best_lp_act, k, N, has_joker, params.gamma_jastrow
    )

    return {
        "log_Z_experts": log_z_experts,
        "prob_sum_exact": prob_sum_acc,
        "pi_inclusion": pi_port,
        "pi_prob": pi_port / float(k),
        "joker_prob": joker_port,
        "variants": variants,
        "deterministic_core": det_core,
        "distinct_covered": distinct_cov,
        "det_G3": det_g3,
        "w_portfolio": w_port,
        "eval_sec": time.perf_counter() - t0,
        "total_states_evaluated": space.total_states,
    }


# ============================================================================
# 4. ACTUALIZARE CAUZALĂ PE PAS (INCLUSIV ZILE DUBLE step_offsets & O3 WEALTH)
# ============================================================================

def extract_step_slices(
    onehot: torch.Tensor,
    step_offsets: torch.Tensor,
    joker_onehot: Optional[torch.Tensor] = None,
    meteo_steps: Optional[torch.Tensor] = None,
) -> List[Tuple[torch.Tensor, Optional[torch.Tensor], Optional[torch.Tensor]]]:
    """Extrage feliile per pas calendaristic din step_offsets (inclusiv zile cu extragere dublă)."""
    offs = step_offsets.detach().cpu().tolist()
    n_steps = len(offs) - 1
    slices = []
    for s in range(n_steps):
        a, b = int(offs[s]), int(offs[s + 1])
        oh_s = onehot[a:b]
        jh_s = joker_onehot[a:b] if joker_onehot is not None else None
        met_s = meteo_steps[s] if meteo_steps is not None else None
        slices.append((oh_s, jh_s, met_s))
    return slices


@torch.no_grad()
def compute_step_expert_log_lrs(
    space: HSV4Space,
    ops: Dict[str, torch.Tensor],
    draws_oh_step: torch.Tensor,
    joker_oh_step: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, float, Dict[str, object]]:
    """Calculează exact ln L_m^(s)(D_s) pentru toți cei 8 experți și raportul portofoliului L_port^(s)."""
    dev = space.device
    N, r, k = space.N, space.r_draw, space.k_ticket
    has_joker = space.joker_m is not None and joker_oh_step is not None and bool(ops["joker_pack"])
    w_port = ops["w_portfolio"]

    # Precalculăm funcțiile de partiție și marginalele experților m=1..7 prin Gauss–Hermite + e_k
    log_z_m = torch.zeros(len(EXPERT_GRID), dtype=torch.float64, device=dev)
    log_z_m[0] = math.log(float(space.total_states))
    pi_port = float(w_port[0].item()) * torch.full((N,), float(k) / float(N), dtype=torch.float64, device=dev)
    joker_port = (
        float(w_port[0].item()) * torch.full((space.joker_m,), 1.0 / float(space.joker_m), dtype=torch.float64, device=dev)
        if has_joker
        else None
    )

    expert_packs = []
    for m_idx in range(1, len(EXPERT_GRID)):
        h_m, h_j, J_mat, eta, gamma = _expert_field_tensors(ops, m_idx, has_joker)
        U_j = ops["joker_pack"]["U_joker"] if (has_joker and gamma > 0.0) else None
        gh_res = gauss_hermite_exact_hs(space, h_m, ops["V_s"], eta, gamma, h_joker=h_j, J_bipartite=J_mat, U_joker=U_j)
        lz = float(gh_res["log_Z"])
        log_z_m[m_idx] = lz
        wm = float(w_port[m_idx].item())
        if wm > 0.0:
            pi_port = pi_port + wm * gh_res["pi_inclusion"]
            if has_joker and joker_port is not None and gh_res["joker_prob"] is not None:
                joker_port = joker_port + wm * gh_res["joker_prob"]
        expert_packs.append((m_idx, h_m, h_j, J_mat, U_j, eta, gamma, lz))

    # Evaluare ln L_m(D) = ∑_{u=1}^{m_s} ln [ (C(N,k)*M_J / C(r,k)) ∑_{σ ⊂ D_u, |σ|=k} P_m(σ, b_u) ]
    log_lrs = torch.zeros(len(EXPERT_GRID), dtype=torch.float64, device=dev)
    m_draws = draws_oh_step.shape[0]
    comb_rk = math.comb(r, k)
    log_norm_comb = math.log(float(space.total_states)) - math.log(float(comb_rk))

    for u in range(m_draws):
        balls_0 = torch.nonzero(draws_oh_step[u] > 0.5, as_tuple=False).reshape(-1).tolist()
        if r == k:
            subs = torch.tensor([sorted(int(x) for x in balls_0)], dtype=torch.int64, device=dev)
        else:
            subs = _all_k_subsets_of_draw(balls_0, k, dev)  # [C(r,k), k]

        jb_idx = None
        if has_joker and joker_oh_step is not None:
            jb_val = int(torch.argmax(joker_oh_step[u]).item())
            jb_idx = torch.full((subs.shape[0],), jb_val, dtype=torch.int64, device=dev)

        for m_idx, h_m, h_j, J_mat, U_j, eta, gamma, lz in expert_packs:
            lw_subs = log_weight_hs_subset(subs, h_m, ops["V_s"], eta, gamma, jb_idx, h_j, J_mat, U_j)
            log_sum_p = float(torch.logsumexp(lw_subs - lz, dim=0).item())
            log_lrs[m_idx] = log_lrs[m_idx] + (log_norm_comb + log_sum_p)

    # Raportul de verosimilitate al portofoliului: L_port = ∑_m w_m * exp(log_lrs[m])
    active_mask = w_port > 0.0
    log_terms_port = torch.log(w_port[active_mask]) + log_lrs[active_mask]
    log_port_lr = float(torch.logsumexp(log_terms_port, dim=0).item())

    return log_lrs, log_port_lr, {
        "pi_inclusion": pi_port,
        "joker_prob": joker_port,
        "log_Z_experts": log_z_m,
    }


@torch.no_grad()
def advance_one_step(
    state: HSV4State,
    space: HSV4Space,
    draws_oh_step: torch.Tensor,
    joker_oh_step: Optional[torch.Tensor] = None,
    meteo_raw_step: Optional[torch.Tensor] = None,
    params: HSV4Params = DEFAULT_PARAMS,
    update_portfolio: bool = True,
    min_wealth_step: int = 0,
) -> Tuple[HSV4State, Dict[str, object]]:
    """Avansează strict cauzal starea cu un pas calendaristic (1 sau mai multe extrageri în aceeași zi)."""
    dev = space.device
    N, r = space.N, space.r_draw
    X_step = draws_oh_step.to(dtype=torch.float64, device=dev)
    m_s = float(X_step.shape[0])
    J_step = joker_oh_step.to(dtype=torch.float64, device=dev) if joker_oh_step is not None else None
    met_vec = meteo_raw_step.to(dtype=torch.float64, device=dev) if meteo_raw_step is not None else None

    # 1. Calcul operatori strict pre-extragere (folosind EXCLUSIV 0..s-1)
    need_wealth = update_portfolio and (state.step_idx >= min_wealth_step)
    if need_wealth:
        ops = forward_operators_from_state(state, space, meteo_raw_step=met_vec, params=params)
    else:
        ops = {
            "z_met": standardize_meteo_causal(state, met_vec, params),
            "Psi_s": build_o4_dictionary(space.o4_main, state.prev_bar_x, float(r)),
            "joker_pack": (
                {"Psi_j": build_o4_dictionary(space.o4_joker, state.prev_bar_j, 1.0)}
                if space.joker_m is not None
                else {}
            ),
        }

    # 2. Actualizare exactă a portofoliului Bayesian O3 (dacă step_idx >= min_wealth_step)
    step_info: Dict[str, object] = {"ops": ops, "log_port_lr": 0.0}
    if need_wealth:
        log_lrs, log_port_lr, port_pack = compute_step_expert_log_lrs(space, ops, X_step, J_step)
        finite_mask = torch.isfinite(state.log_wealth)
        state.log_wealth = torch.where(finite_mask, state.log_wealth + log_lrs, state.log_wealth)
        state.portfolio_steps += 1
        step_info["log_lrs"] = log_lrs
        step_info["log_port_lr"] = log_port_lr
        step_info["port_pack"] = port_pack

    # 3.Statistici simetrice pe pasul curent (100% invariante la ordinea extragerilor din aceeași zi!)
    bar_x = X_step.mean(dim=0)                                        # [N]
    step_m2 = (X_step.T @ X_step) / m_s                               # [N, N]
    step_m3 = (torch.einsum("bi,bj,bk->ijk", X_step, X_step, X_step) / m_s) * space.dist3_mask
    y_cent = bar_x - (float(r) / float(N))

    # Actualizare O1 momente bosonic + intrinsec
    rho_bos = math.exp(-1.0 / params.tau_bos)
    state.n_eff_bos = rho_bos * state.n_eff_bos + 1.0
    state.m1_bos = rho_bos * state.m1_bos + (1.0 - rho_bos) * bar_x
    state.m2_bos = rho_bos * state.m2_bos + (1.0 - rho_bos) * step_m2
    state.m3_dist = rho_bos * state.m3_dist + (1.0 - rho_bos) * step_m3

    for h_idx, tau_h in enumerate(params.tau_int):
        rho_h = math.exp(-1.0 / tau_h)
        state.ema_int[h_idx] = rho_h * state.ema_int[h_idx] + (1.0 - rho_h) * bar_x

    # Actualizare O2 regresie ridge online + Welford meteo
    z_met = ops["z_met"]
    rho_aero = math.exp(-1.0 / params.tau_aero)
    if met_vec is not None:
        if state.meteo_count >= params.meteo_warmup:
            state.aero_gram = rho_aero * state.aero_gram + torch.outer(z_met, z_met)
            state.aero_rhs = rho_aero * state.aero_rhs + torch.outer(z_met, y_cent)
        # Actualizare Welford DUPĂ folosirea z_met la pasul s -> zero scurgere!
        state.meteo_count += 1
        delta = met_vec - state.meteo_mean
        state.meteo_mean = state.meteo_mean + delta / float(state.meteo_count)
        delta2 = met_vec - state.meteo_mean
        state.meteo_m2 = state.meteo_m2 + delta * delta2

    # Actualizare O4 regresie ridge online pe dicționarul Ψ_s
    Psi_s = ops["Psi_s"]
    rho_rng = math.exp(-1.0 / params.tau_rng)
    state.rng_gram = rho_rng * state.rng_gram + (Psi_s.T @ Psi_s)
    state.rng_rhs = rho_rng * state.rng_rhs + (Psi_s.T @ y_cent)
    state.prev_bar_x = bar_x

    # Actualizare urnă secundară bipartită (ex. Joker)
    if space.joker_m is not None and J_step is not None:
        M = space.joker_m
        bar_j = J_step.mean(dim=0)
        yj_cent = bar_j - (1.0 / float(M))
        step_cross = (X_step.T @ J_step) / m_s
        rho_j = math.exp(-1.0 / params.tau_joker)

        state.m1_joker = rho_j * state.m1_joker + (1.0 - rho_j) * bar_j
        state.cross_m2 = rho_j * state.cross_m2 + (1.0 - rho_j) * step_cross
        for h_idx, tau_h in enumerate(params.tau_int):
            rho_h = math.exp(-1.0 / tau_h)
            state.ema_joker_int[h_idx] = rho_h * state.ema_joker_int[h_idx] + (1.0 - rho_h) * bar_j

        if met_vec is not None and (state.meteo_count - 1) >= params.meteo_warmup:
            state.aero_rhs_joker = rho_aero * state.aero_rhs_joker + torch.outer(z_met, yj_cent)

        Psi_j = ops["joker_pack"]["Psi_j"]
        state.rng_gram_j = rho_rng * state.rng_gram_j + (Psi_j.T @ Psi_j)
        state.rng_rhs_j = rho_rng * state.rng_rhs_j + (Psi_j.T @ yj_cent)
        state.prev_bar_j = bar_j

    state.step_idx += 1
    return state, step_info


@torch.no_grad()
def advance_steps(
    state: HSV4State,
    space: HSV4Space,
    slices: Sequence[Tuple[torch.Tensor, Optional[torch.Tensor], Optional[torch.Tensor]]],
    params: HSV4Params = DEFAULT_PARAMS,
    update_portfolio: bool = True,
    min_wealth_step: int = 0,
) -> HSV4State:
    """Avansează secvențial o listă de pași calendaristici."""
    for oh_s, jh_s, met_s in slices:
        advance_one_step(
            state,
            space,
            oh_s,
            joker_oh_step=jh_s,
            meteo_raw_step=met_s,
            params=params,
            update_portfolio=update_portfolio,
            min_wealth_step=min_wealth_step,
        )
    return state
