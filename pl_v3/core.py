"""PL-V3 Core — Operatori O1..O5 pe GPU (CUDA / PyTorch) pentru 6/49, 5/40 și Joker.

Protocol sigilat: pl_v3/PROTOCOL_PLV3.md (SIGILIU_PROTOCOL_PLV3.json).
Calcul clasic; positive_claims_allowed = False. Zero scurtături de tip z_norm aditiv.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch


@dataclass(frozen=True)
class PLV3Params:
    tau_horiz: Tuple[float, float, float] = (16.0, 64.0, 256.0)
    tau_cooc: float = 48.0
    tau_ruelle: float = 96.0
    ruelle_lags: Tuple[int, int, int, int] = (1, 2, 3, 5)
    ruelle_weights: Tuple[float, float, float, float] = (0.45, 0.25, 0.18, 0.12)
    gamma_base: float = 0.02
    gamma_span: float = 0.10
    tau_bochner: float = 0.35
    beta_kernel: float = 0.75
    beta_joker: float = 0.85
    lambda_cs: float = 0.25
    gamma_jastrow: float = 0.50
    chunk_size: int = 250_000
    pool_size: int = 2048


DEFAULT_PARAMS = PLV3Params()


# ============================================================================
# 0. TOPOLOGIA 2-COMPLEXULUI SIMPLICIAL K_N & OPERATORII DE FRONTIERĂ EXACȚI
# ============================================================================

class SimplicialTopology:
    """2-complexul complet K_N = (V, E, F) și tabelele combinadice pe GPU."""

    def __init__(self, N: int, r_draw: int, k_ticket: int, device: torch.device, joker_m: Optional[int] = None):
        self.N = int(N)
        self.r_draw = int(r_draw)
        self.k_ticket = int(k_ticket)
        self.joker_m = int(joker_m) if joker_m is not None else None
        self.device = device

        idx_i, idx_j = torch.triu_indices(N, N, offset=1, device=device)
        self.edges = torch.stack([idx_i, idx_j], dim=1)
        self.num_edges = int(self.edges.shape[0])

        self.edge_lookup = torch.full((N, N), -1, dtype=torch.long, device=device)
        e_arange = torch.arange(self.num_edges, device=device)
        self.edge_lookup[idx_i, idx_j] = e_arange
        self.edge_lookup[idx_j, idx_i] = e_arange

        grid = torch.arange(N, device=device)
        ii, jj, kk = torch.meshgrid(grid, grid, grid, indexing="ij")
        mask_f = (ii < jj) & (jj < kk)
        self.faces = torch.stack([ii[mask_f], jj[mask_f], kk[mask_f]], dim=1)
        self.num_faces = int(self.faces.shape[0])

        # ∂_2(i,j,k) = (j,k) - (i,k) + (i,j)
        self.face_edges = torch.stack([
            self.edge_lookup[self.faces[:, 1], self.faces[:, 2]],
            self.edge_lookup[self.faces[:, 0], self.faces[:, 2]],
            self.edge_lookup[self.faces[:, 0], self.faces[:, 1]],
        ], dim=1)

        # B1: [N, E] dens în float64 (49 x 1176 = 460 KB -> înmulțiri dense instantanee și exacte pe GPU)
        B1 = torch.zeros((N, self.num_edges), dtype=torch.float64, device=device)
        B1[self.edges[:, 0], e_arange] = -1.0
        B1[self.edges[:, 1], e_arange] = 1.0
        self.B1 = B1
        self.d0 = B1.T.contiguous()  # [E, N]

        # ∂_2(i,j,k) = (j,k) - (i,k) + (i,j) — verificare omologică exactă ∂_1 ∘ ∂_2 = 0 fără sparse overhead
        fe0, fe1, fe2 = self.face_edges[:, 0], self.face_edges[:, 1], self.face_edges[:, 2]
        chain_err = (self.B1[:, fe0] - self.B1[:, fe1] + self.B1[:, fe2]).abs().max().item()
        if chain_err > 1e-15:
            raise RuntimeError(f"Eroare omologică ∂1∘∂2 != 0: {chain_err}")

        # Baza Gell-Mann hermitiană Λ_1..Λ_8 [8, 3, 3] complex128
        self.gell_mann = self._build_gell_mann(device)

        # Combinadic & sub-simplexuri pe k_ticket
        self.total_base_states = math.comb(N, k_ticket)
        self.binom_table = self._build_binom_table(N, k_ticket, device)
        gk = torch.arange(k_ticket, device=device)
        f_i, f_j, f_k = torch.meshgrid(gk, gk, gk, indexing="ij")
        fm = (f_i < f_j) & (f_j < f_k)
        self.sub_fi = f_i[fm]
        self.sub_fj = f_j[fm]
        self.sub_fk = f_k[fm]
        self.num_sub_faces = int(self.sub_fi.shape[0])

    @staticmethod
    def _build_gell_mann(device: torch.device) -> torch.Tensor:
        L = torch.zeros((8, 3, 3), dtype=torch.complex128, device=device)
        L[0, 0, 1] = L[0, 1, 0] = 1.0
        L[1, 0, 1] = -1j
        L[1, 1, 0] = 1j
        L[2, 0, 0] = 1.0
        L[2, 1, 1] = -1.0
        L[3, 0, 2] = L[3, 2, 0] = 1.0
        L[4, 0, 2] = -1j
        L[4, 2, 0] = 1j
        L[5, 1, 2] = L[5, 2, 1] = 1.0
        L[6, 1, 2] = -1j
        L[6, 2, 1] = 1j
        L[7, 0, 0] = 1.0 / math.sqrt(3.0)
        L[7, 1, 1] = 1.0 / math.sqrt(3.0)
        L[7, 2, 2] = -2.0 / math.sqrt(3.0)
        return L

    @staticmethod
    def _build_binom_table(N: int, k: int, device: torch.device) -> torch.Tensor:
        t = torch.zeros((N + 1, k + 1), dtype=torch.int64, device=device)
        for n in range(N + 1):
            for r in range(min(n, k) + 1):
                t[n, r] = math.comb(n, r)
        return t

    def unrank_chunk(self, start_idx: int, end_idx: int) -> torch.Tensor:
        ranks = torch.arange(start_idx, end_idx, dtype=torch.int64, device=self.device)
        simplices = torch.empty((ranks.shape[0], self.k_ticket), dtype=torch.int64, device=self.device)
        rem = ranks
        for d in range(self.k_ticket, 0, -1):
            col_d = self.binom_table[: self.N, d].contiguous()
            c = (torch.searchsorted(col_d, rem, right=True) - 1).clamp_(0, self.N - 1)
            simplices[:, d - 1] = c
            rem = rem - col_d[c]
        return simplices


# ============================================================================
# 1. EXPONENȚIALA ANALITICĂ SU(3) & STAREA MARKOVIANĂ INCREMENTALĂ (O1)
# ============================================================================

def su3_exp_hermitian(H_in: torch.Tensor) -> torch.Tensor:
    """Calculează analitic exp(i H) ∈ SU(3) pentru H hermitian fără urmă [..., 3, 3] în complex128."""
    orig_shape = H_in.shape[:-2]
    device = H_in.device
    H = H_in.reshape(-1, 3, 3).to(torch.complex128)
    H = 0.5 * (H + H.conj().transpose(-1, -2))
    I3 = torch.eye(3, dtype=torch.complex128, device=device).unsqueeze(0)
    tr_H = torch.diagonal(H, dim1=-2, dim2=-1).sum(-1, keepdim=True).unsqueeze(-1)
    H = H - (tr_H / 3.0) * I3

    H2 = torch.bmm(H, H)
    H3 = torch.bmm(H2, H)

    c1 = (0.5 * torch.diagonal(H2, dim1=-2, dim2=-1).sum(-1).real).clamp(min=0.0)
    c0 = (1.0 / 3.0) * torch.diagonal(H3, dim1=-2, dim2=-1).sum(-1).real

    q = (c1 / 3.0).clamp(min=1e-36)
    q_sqrt = torch.sqrt(q)
    c0_max = 2.0 * q * q_sqrt
    cos_3theta = (c0 / c0_max).clamp(-1.0, 1.0)
    theta = torch.acos(cos_3theta) / 3.0

    two_sqrt_q = 2.0 * q_sqrt
    l1 = two_sqrt_q * torch.cos(theta)
    l2 = two_sqrt_q * torch.cos(theta - 2.0 * math.pi / 3.0)
    l3 = -(l1 + l2)

    def div_exp(la: torch.Tensor, lb: torch.Tensor) -> torch.Tensor:
        mean = 0.5 * (la + lb)
        half_diff = 0.5 * (la - lb)
        return 1j * torch.exp(1j * mean) * torch.sinc(half_diff / math.pi)

    e1 = torch.exp(1j * l1)
    d12 = div_exp(l1, l2)
    d23 = div_exp(l2, l3)

    diff_13 = l1 - l3
    reg = diff_13.abs() > 1e-7
    denom = torch.where(reg, diff_13, torch.ones_like(diff_13)).to(torch.complex128)
    d123 = torch.where(reg, (d12 - d23) / denom, -0.5 * torch.ones_like(d12))

    f2 = d123
    f1 = d12 - d123 * (l1 + l2).to(torch.complex128)
    f0 = e1 - d12 * l1.to(torch.complex128) + d123 * (l1 * l2).to(torch.complex128)

    U = (
        f0.unsqueeze(-1).unsqueeze(-1) * I3
        + f1.unsqueeze(-1).unsqueeze(-1) * H
        + f2.unsqueeze(-1).unsqueeze(-1) * H2
    )
    # Proiecție fină a determinantului la 1 fără salt de ramură (det(U) e deja 1 ± 1e-15)
    det_U = torch.linalg.det(U)
    U = U * torch.exp(-1j * torch.angle(det_U) / 3.0).unsqueeze(-1).unsqueeze(-1)
    return U.reshape(*orig_shape, 3, 3)


@dataclass
class PLV3State:
    step_idx: int
    U_full: torch.Tensor               # [N, N, 3, 3] complex128
    pair_cooc: torch.Tensor            # [N, N] int64
    last_step: torch.Tensor            # [N] int64
    ball_count: torch.Tensor           # [N] int64
    ema_node: torch.Tensor             # [3, N] float64
    ema_cooc: torch.Tensor             # [N, N] float64
    ruelle_hist: torch.Tensor          # [5, N] float64 (index 0 = lag 1, ..., index 4 = lag 5)
    ruelle_trans: torch.Tensor         # [4, N, N] float64
    joker_ema: Optional[torch.Tensor] = None       # [3, M] float64
    joker_hist: Optional[torch.Tensor] = None      # [5, M] float64
    joker_ruelle: Optional[torch.Tensor] = None    # [4, M, M] float64
    cross_ema0: Optional[torch.Tensor] = None      # [N, M] float64
    cross_ema1: Optional[torch.Tensor] = None      # [N, M] float64

    def clone(self) -> "PLV3State":
        mv = lambda x: None if x is None else x.clone()
        return PLV3State(
            step_idx=int(self.step_idx),
            U_full=self.U_full.clone(),
            pair_cooc=self.pair_cooc.clone(),
            last_step=self.last_step.clone(),
            ball_count=self.ball_count.clone(),
            ema_node=self.ema_node.clone(),
            ema_cooc=self.ema_cooc.clone(),
            ruelle_hist=self.ruelle_hist.clone(),
            ruelle_trans=self.ruelle_trans.clone(),
            joker_ema=mv(self.joker_ema),
            joker_hist=mv(self.joker_hist),
            joker_ruelle=mv(self.joker_ruelle),
            cross_ema0=mv(self.cross_ema0),
            cross_ema1=mv(self.cross_ema1),
        )


def init_state(topo: SimplicialTopology) -> PLV3State:
    N, r, dev = topo.N, topo.r_draw, topo.device
    I3 = torch.eye(3, dtype=torch.complex128, device=dev)
    U_full = I3.view(1, 1, 3, 3).expand(N, N, 3, 3).clone()
    p0 = float(r) / float(N)
    p_co0 = float(r * (r - 1)) / float(N * (N - 1))
    ema_cooc = torch.full((N, N), p_co0, dtype=torch.float64, device=dev)
    ema_cooc.fill_diagonal_(0.0)

    j_ema = j_hist = j_ruelle = c_ema0 = c_ema1 = None
    if topo.joker_m is not None:
        M = topo.joker_m
        j_ema = torch.full((3, M), 1.0 / float(M), dtype=torch.float64, device=dev)
        j_hist = torch.zeros((5, M), dtype=torch.float64, device=dev)
        j_ruelle = torch.zeros((4, M, M), dtype=torch.float64, device=dev)
        c_ema0 = torch.full((N, M), p0 / float(M), dtype=torch.float64, device=dev)
        c_ema1 = torch.zeros((N, M), dtype=torch.float64, device=dev)

    return PLV3State(
        step_idx=0,
        U_full=U_full,
        pair_cooc=torch.zeros((N, N), dtype=torch.int64, device=dev),
        last_step=torch.full((N,), -1, dtype=torch.int64, device=dev),
        ball_count=torch.zeros((N,), dtype=torch.int64, device=dev),
        ema_node=torch.full((3, N), p0, dtype=torch.float64, device=dev),
        ema_cooc=ema_cooc,
        ruelle_hist=torch.zeros((5, N), dtype=torch.float64, device=dev),
        ruelle_trans=torch.zeros((4, N, N), dtype=torch.float64, device=dev),
        joker_ema=j_ema,
        joker_hist=j_hist,
        joker_ruelle=j_ruelle,
        cross_ema0=c_ema0,
        cross_ema1=c_ema1,
    )


def extract_step_slices(
    onehot: torch.Tensor,
    step_offsets: torch.Tensor,
    joker_onehot: Optional[torch.Tensor] = None,
) -> List[Tuple[torch.Tensor, Optional[torch.Tensor]]]:
    """Grupează extragerile pe pași-zi conform step_offsets (zero scurgere intra-zi)."""
    offs = step_offsets.tolist()
    out: List[Tuple[torch.Tensor, Optional[torch.Tensor]]] = []
    for s in range(len(offs) - 1):
        a, b = offs[s], offs[s + 1]
        j_slice = None if joker_onehot is None else joker_onehot[a:b]
        out.append((onehot[a:b], j_slice))
    return out


def _jensen_shannon_rate(ema_short: torch.Tensor, ema_long: torch.Tensor, params: PLV3Params) -> float:
    p = (ema_short.clamp(min=1e-12)) / ema_short.clamp(min=1e-12).sum()
    q = (ema_long.clamp(min=1e-12)) / ema_long.clamp(min=1e-12).sum()
    m = 0.5 * (p + q)
    kl_pm = (p * torch.log(p / m)).sum()
    kl_qm = (q * torch.log(q / m)).sum()
    jsd = (0.5 * (kl_pm + kl_qm)).clamp(min=0.0)
    ratio = torch.sqrt(jsd / math.log(2.0)).clamp(0.0, 1.0).item()
    return params.gamma_base + params.gamma_span * ratio


def advance_one_step(
    state: PLV3State,
    topo: SimplicialTopology,
    step_onehot: torch.Tensor,
    step_joker_oh: Optional[torch.Tensor] = None,
    params: PLV3Params = DEFAULT_PARAMS,
) -> None:
    """Avansează in-place starea de la pasul s la s+1 (strict cauzal și echivariant S_N)."""
    N, r, dev = topo.N, topo.r_draw, topo.device
    s = state.step_idx
    X = step_onehot.to(device=dev, dtype=torch.float64)  # [m_s, N]
    m_s = float(X.shape[0])
    x_bar = X.mean(dim=0)  # [N]

    # 1. Pasul de curgere Yang-Mills Lüscher / Morningstar-Peardon (exact gauge-covariant!)
    gamma_s = _jensen_shannon_rate(state.ema_node[0], state.ema_node[2], params)
    U = state.U_full
    # Suma de capse triunghiulare Σ_{ij} = (1/(N-2)) ∑_{k != i,j} U_{ik} U_{kj}
    U_zero_diag = U.clone()
    diag_idx = torch.arange(N, device=dev)
    U_zero_diag[diag_idx, diag_idx] = 0.0
    staple = torch.einsum("ikab,kjbc->ijac", U_zero_diag, U_zero_diag) / float(N - 2)
    omega = torch.matmul(staple, U.conj().transpose(-1, -2))  # Ω_{ij} = Σ_{ij} U_{ij}†
    diff_om = 0.5j * (omega.conj().transpose(-1, -2) - omega)
    I3 = torch.eye(3, dtype=torch.complex128, device=dev)
    tr_diff = torch.diagonal(diff_om, dim1=-2, dim2=-1).sum(-1, keepdim=True).unsqueeze(-1)
    F_ym = diff_om - (tr_diff / 3.0) * I3
    F_ym[diag_idx, diag_idx] = 0.0
    U_flow = torch.matmul(su3_exp_hermitian(gamma_s * F_ym), U)
    U_flow[diag_idx, diag_idx] = I3

    # 2. Impuls neabelian palindromic Strang pe perechile co-extrase la pasul s
    cooc_mat = (X.T @ X)
    cooc_mat.fill_diagonal_(0.0)
    active_pairs = cooc_mat > 0.5  # perechi {i,j} co-extrase în pasul s

    if active_pairs.any():
        # Canalul generatorului din n_{ij}(s⁻) mod 8 (invariant la permutarea etichetelor)
        chan = torch.remainder(state.pair_cooc, 8)  # [N, N] în 0..7
        gen_ij = topo.gell_mann[chan]  # [N, N, 3, 3]

        # Orientare intrinsecă σ_{ij}(s) din vechimea g(s⁻), cu tie-break pe ball_count(s⁻)
        g_diff = state.last_step.unsqueeze(0) - state.last_step.unsqueeze(1)  # g_j - g_i
        c_diff = state.ball_count.unsqueeze(0) - state.ball_count.unsqueeze(1)  # c_j - c_i
        sigma = torch.sign(g_diff)
        sigma = torch.where(sigma == 0, torch.sign(c_diff), sigma).to(torch.float64)
        # Ponderat cu multiplicitatea medie în ziua dublă (1 pentru zi simplă)
        mult = (cooc_mat / m_s) * active_pairs.to(torch.float64)
        eps_half = 0.5 * (math.pi / (8.0 * math.sqrt(float(r))))
        H_half = (eps_half * sigma * mult).to(torch.complex128).unsqueeze(-1).unsqueeze(-1) * gen_ij
        dU_half = su3_exp_hermitian(H_half)
        U_next = torch.matmul(torch.matmul(dU_half, U_flow), dU_half)
        U_next[diag_idx, diag_idx] = I3
    else:
        U_next = U_flow

    state.U_full = U_next

    # 3. Actualizarea contoarelor strict anterioare pentru pasul următor
    state.pair_cooc = state.pair_cooc + cooc_mat.to(torch.int64)
    appeared = X.sum(dim=0) > 0.5
    state.last_step = torch.where(appeared, torch.full_like(state.last_step, s), state.last_step)
    state.ball_count = state.ball_count + X.sum(dim=0).to(torch.int64)

    # 4. Orizonturi exponențiale și memorie de tranziție Ruelle
    for h_idx, tau_h in enumerate(params.tau_horiz):
        a_h = 1.0 - math.exp(-1.0 / tau_h)
        state.ema_node[h_idx] = (1.0 - a_h) * state.ema_node[h_idx] + a_h * x_bar

    a_co = 1.0 - math.exp(-1.0 / params.tau_cooc)
    state.ema_cooc = (1.0 - a_co) * state.ema_cooc + a_co * (cooc_mat / m_s)

    p0 = float(r) / float(N)
    x_tilde = x_bar - p0
    a_ru = 1.0 - math.exp(-1.0 / params.tau_ruelle)
    for l_idx, lag in enumerate(params.ruelle_lags):
        if s >= lag:
            past_vec = state.ruelle_hist[lag - 1]
            state.ruelle_trans[l_idx] = (
                (1.0 - a_ru) * state.ruelle_trans[l_idx] + a_ru * torch.outer(past_vec, x_tilde)
            )
    state.ruelle_hist = torch.cat([x_tilde.unsqueeze(0), state.ruelle_hist[:-1]], dim=0)

    # 5. Fluxul cuplat al urnei secundare Joker (dacă e activă)
    if topo.joker_m is not None and step_joker_oh is not None:
        M = topo.joker_m
        Y = step_joker_oh.to(device=dev, dtype=torch.float64)  # [m_s, M]
        y_bar = Y.mean(dim=0)
        y_tilde = y_bar - (1.0 / float(M))

        for h_idx, tau_h in enumerate(params.tau_horiz):
            a_h = 1.0 - math.exp(-1.0 / tau_h)
            state.joker_ema[h_idx] = (1.0 - a_h) * state.joker_ema[h_idx] + a_h * y_bar

        for l_idx, lag in enumerate(params.ruelle_lags):
            if s >= lag:
                past_j = state.joker_hist[lag - 1]
                state.joker_ruelle[l_idx] = (
                    (1.0 - a_ru) * state.joker_ruelle[l_idx] + a_ru * torch.outer(past_j, y_tilde)
                )

        # Cuplaj inter-urne la lag 0 (același studio) și lag 1 (s-1 -> s)
        cross_s = (X.T @ Y) / m_s
        state.cross_ema0 = (1.0 - a_co) * state.cross_ema0 + a_co * cross_s
        if s >= 1:
            # state.ruelle_hist[1] este x_tilde de la s-1 (deoarece ruelle_hist a fost deja shiftat mai sus!)
            state.cross_ema1 = (1.0 - a_ru) * state.cross_ema1 + a_ru * torch.outer(state.ruelle_hist[1], y_tilde)

        state.joker_hist = torch.cat([y_tilde.unsqueeze(0), state.joker_hist[:-1]], dim=0)

    state.step_idx = s + 1


def advance_steps(
    state: PLV3State,
    topo: SimplicialTopology,
    step_slices: List[Tuple[torch.Tensor, Optional[torch.Tensor]]],
    params: PLV3Params = DEFAULT_PARAMS,
) -> PLV3State:
    for x_s, j_s in step_slices:
        advance_one_step(state, topo, x_s, j_s, params)
    return state


# ============================================================================
# 2. OPERATORII O2, O3, O4 DIN STAREA CURENTĂ (FĂRĂ SCURGERE, FĂRĂ Z-NORM)
# ============================================================================

def _build_ultrametric_spin_glass_lut(dist_mat: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Construiește dendrograma single-linkage (N-1 <= 48 noduri interne) cu Δh(u) = h(parent(u)) - h(u) >= 0.

    Returnează:
      leaf_weights: [N] float64 = h(parent(leaf)) / h_scale
      leaf_masks: [N] int64 (biții strămoșilor interni în 0..47)
      lut0, lut1, lut2: [65536] float64 pentru biții 0..15, 16..31, 32..47 (scalate cu h_scale).
    """
    device = dist_mat.device
    D_np = dist_mat.detach().cpu().numpy().astype(np.float64)
    N = D_np.shape[0]
    num_internal = N - 1

    # Extragem muchiile i < j ordonate crescător după distanță (egalitățile dau Δh = 0 -> invariant la tie-break!)
    iu, ju = np.triu_indices(N, k=1)
    weights = D_np[iu, ju]
    order = np.argsort(weights, kind="mergesort")

    parent_comp = list(range(2 * N - 1))

    def find_root(x: int) -> int:
        while parent_comp[x] != x:
            parent_comp[x] = parent_comp[parent_comp[x]]
            x = parent_comp[x]
        return x

    tree_parent = [-1] * (2 * N - 1)
    node_height = np.zeros(2 * N - 1, dtype=np.float64)
    next_internal = N

    for idx in order:
        ra = find_root(int(iu[idx]))
        rb = find_root(int(ju[idx]))
        if ra != rb:
            u = next_internal
            next_internal += 1
            node_height[u] = max(float(weights[idx]), node_height[ra], node_height[rb])
            tree_parent[ra] = u
            tree_parent[rb] = u
            parent_comp[ra] = u
            parent_comp[rb] = u
            if next_internal == 2 * N - 1:
                break

    h_root = float(node_height[2 * N - 2]) if N > 1 else 1.0
    h_scale = max(h_root, 1e-8)

    # Δh(u) pentru nodurile interne u = N .. 2N-2 (indexate b = u - N ∈ 0 .. N-2)
    delta_h = np.zeros(48, dtype=np.float64)
    for b in range(num_internal):
        u = N + b
        p = tree_parent[u]
        if p != -1:
            delta_h[b] = max(0.0, (node_height[p] - node_height[u]) / h_scale)

    leaf_w = np.zeros(N, dtype=np.float64)
    leaf_masks = np.zeros(N, dtype=np.int64)
    for leaf in range(N):
        p = tree_parent[leaf]
        leaf_w[leaf] = (node_height[p] / h_scale) if p != -1 else 0.0
        cur = p
        mask = 0
        while cur != -1:
            b = cur - N
            mask |= (1 << b)
            cur = tree_parent[cur]
        leaf_masks[leaf] = mask

    # Construim cele 3 tabele LUT de 16 biți (65536 intrări fiecare) vectorizat în NumPy
    bits16 = np.arange(65536, dtype=np.uint32)
    bit_mat = ((bits16[:, None] >> np.arange(16, dtype=np.uint32)[None, :]) & 1).astype(np.float64)
    lut0 = bit_mat @ delta_h[0:16]
    lut1 = bit_mat @ delta_h[16:32]
    lut2 = bit_mat @ delta_h[32:48]

    return (
        torch.as_tensor(leaf_w, dtype=torch.float64, device=device),
        torch.as_tensor(leaf_masks, dtype=torch.int64, device=device),
        torch.as_tensor(lut0, dtype=torch.float64, device=device),
        torch.as_tensor(lut1, dtype=torch.float64, device=device),
        torch.as_tensor(lut2, dtype=torch.float64, device=device),
    )


def forward_operators_from_state(
    state: PLV3State,
    topo: SimplicialTopology,
    params: PLV3Params = DEFAULT_PARAMS,
    eigh_phase_twist: Optional[torch.Tensor] = None,
) -> Dict[str, torch.Tensor]:
    """Calculează O2 (Hodge), O3 (Bochner-Kernel K) și O4 (Spin-Glass + Bipartit Joker) din PLV3State."""
    t0 = time.perf_counter()
    N, dev = topo.N, topo.device
    ei, ej = topo.edges[:, 0], topo.edges[:, 1]
    fi, fj, fk = topo.faces[:, 0], topo.faces[:, 1], topo.faces[:, 2]
    U = state.U_full  # [N, N, 3, 3] complex128

    # --- O2: Holonomia SU(3) & Descompunerea Coomologică Exactă Helmholtz-Hodge ---
    hol_loop = torch.bmm(torch.bmm(U[fi, fj], U[fj, fk]), U[fk, fi])  # [F, 3, 3]
    tr1 = torch.diagonal(hol_loop, dim1=-2, dim2=-1).sum(-1)          # [F] complex128
    W_faces = (1.0 / 3.0) * tr1.real                                  # în [-0.5, 1.0], fără clamp la -1/3!
    ym_tension = (1.0 - W_faces).clamp(min=0.0)                       # în [0.0, 1.5]

    rho_emp = (0.50 * state.ema_node[0] + 0.30 * state.ema_node[1] + 0.20 * state.ema_node[2]).clamp(min=1e-8)
    rho_emp = rho_emp / rho_emp.sum()
    w0 = (rho_emp * float(N)).clamp(min=1e-4)  # adimensional, medie = 1

    cooc_e = state.ema_cooc[ei, ej].clamp(min=0.0)
    denom_e = (state.ema_node[1, ei] + state.ema_node[1, ej] - cooc_e).clamp(min=1e-6)
    affinity_e = cooc_e / denom_e
    w1 = ((affinity_e + 0.05) / (affinity_e.mean() + 0.05)).clamp(min=1e-4)  # adimensional, medie = 1
    w2 = (1.0 / (1.0 + ym_tension))
    w2 = (w2 / w2.mean().clamp(min=1e-8)).clamp(min=1e-4)

    # Curentul cauzal antisimetric Ruelle multi-pas
    L_ruelle = torch.zeros((N, N), dtype=torch.float64, device=dev)
    for l_idx, w_l in enumerate(params.ruelle_weights):
        L_ruelle = L_ruelle + w_l * state.ruelle_trans[l_idx]

    J_anti = 0.5 * (L_ruelle - L_ruelle.T)
    j_scale = torch.linalg.matrix_norm(J_anti, ord="fro") / math.sqrt(float(max(topo.num_edges, 1))) + 1e-12
    J_1form = J_anti[ei, ej] / j_scale  # [E] float64

    # Sistemul exact Hodge: (B1 W1 B1^T) φ = B1 W1 J_1form cu gauge ∑ φ_i = 0
    B1_W1 = topo.B1 * w1.unsqueeze(0)  # [N, E]
    L0_hodge = B1_W1 @ topo.d0         # [N, N] simetric pozitiv semidefinit
    rhs_0 = B1_W1 @ J_1form            # [N]
    # Proiecție ortogonală pe subspațiul de medie zero (elimină modul nul constant exact!)
    ones_proj = torch.full((N, N), 1.0 / float(N), dtype=torch.float64, device=dev)
    phi = torch.linalg.solve(L0_hodge + ones_proj, rhs_0)
    phi = phi - phi.mean()

    J_exact = topo.d0 @ phi            # [E]
    J_curl = J_1form - J_exact         # [E] ∈ ker(δ_1) la precizie mașină!
    delta1_curl = (B1_W1 @ J_curl) / w0

    fe0, fe1, fe2 = topo.face_edges[:, 0], topo.face_edges[:, 1], topo.face_edges[:, 2]
    Omega_curl = J_curl[fe0] - J_curl[fe1] + J_curl[fe2]  # (d_1 J_curl)[f], exact în float64
    # Tensor 3D simetric al vorticității de 3 corpuri |Ω_curl(f)| + tensiunea neabeliană YM
    face_vorticity = 0.5 * Omega_curl.abs() + 0.5 * ym_tension
    Curl3D = torch.zeros((N, N, N), dtype=torch.float64, device=dev)
    Curl3D[fi, fj, fk] = face_vorticity
    Curl3D[fj, fk, fi] = face_vorticity
    Curl3D[fk, fi, fj] = face_vorticity
    Curl3D[fj, fi, fk] = face_vorticity
    Curl3D[fi, fk, fj] = face_vorticity
    Curl3D[fk, fj, fi] = face_vorticity
    t_hodge = time.perf_counter()

    # --- O3: Laplacianul Magnetic Bochner & Kernelul Fermionic Gauge-Invariant K ---
    W_adj = torch.zeros((N, N), dtype=torch.float64, device=dev)
    W_adj[ei, ej] = w1
    W_adj[ej, ei] = w1
    deg = W_adj.sum(dim=1)
    I3 = torch.eye(3, dtype=torch.complex128, device=dev)
    Bochner_Lap = (
        torch.kron(torch.diag(deg.to(torch.complex128)), I3)
        - torch.einsum("ij,ijab->iajb", W_adj.to(torch.complex128), U).reshape(3 * N, 3 * N)
    )
    Bochner_Lap = 0.5 * (Bochner_Lap + Bochner_Lap.conj().T)

    evals_B, evecs_B = torch.linalg.eigh(Bochner_Lap)
    if eigh_phase_twist is not None:
        # Pentru Q3: verificare explicită că rotirea fazelor vectorilor proprii nu schimbă nimic!
        evecs_B = evecs_B * torch.exp(1j * eigh_phase_twist.to(device=dev, dtype=torch.float64)).unsqueeze(0)

    deg_scale = deg.mean().clamp(min=1e-8)
    heat_weights = torch.exp(-params.tau_bochner * evals_B.clamp(min=0.0) / deg_scale).to(torch.complex128)
    # G_bochner = V diag(heat_weights) V† -> fazele individuale ale coloanelor V se anulează identic!
    G_bochner = (evecs_B * heat_weights.unsqueeze(0)) @ evecs_B.conj().T
    G_blocks = G_bochner.reshape(N, 3, N, 3).permute(0, 2, 1, 3)  # [N, N, 3, 3]

    # T_{ij} = (1/3) Tr_{C^3}( G_{ij}(τ_B) U_{ij}† ) = (1/3) ∑_{a,b} G_{ij,ab} conj(U_{ij,ab})
    T_overlap = (1.0 / 3.0) * torch.einsum("ijab,ijab->ij", G_blocks, U.conj())
    T_overlap = 0.5 * (T_overlap + T_overlap.conj().T)

    amp_rho = torch.sqrt((rho_emp * float(N)).clamp(min=1e-8)).to(torch.complex128)
    M_mat = T_overlap * torch.outer(amp_rho, amp_rho) + torch.diag(phi.to(torch.complex128))
    M_mat = 0.5 * (M_mat + M_mat.conj().T)

    evals_M, evecs_M = torch.linalg.eigh(M_mat)
    if eigh_phase_twist is not None:
        evecs_M = evecs_M * torch.exp(1j * eigh_phase_twist[:N].to(device=dev, dtype=torch.float64)).unsqueeze(0)
    m_norm_scale = evals_M.abs().max().clamp(min=1e-8)
    k_eigs = torch.exp(params.beta_kernel * (evals_M / m_norm_scale))
    K_kernel = (evecs_M * k_eigs.to(torch.complex128).unsqueeze(0)) @ evecs_M.conj().T
    K_kernel = 0.5 * (K_kernel + K_kernel.conj().T)
    t_bochner = time.perf_counter()

    # --- O4: Ultrametrica Spin-Glass & Operatorul Bipartit Încurcat Joker ---
    diag_T = torch.diagonal(T_overlap).real.clamp(min=1e-12)
    coh_ij = (T_overlap.abs() / torch.sqrt(torch.outer(diag_T, diag_T))).clamp(0.0, 1.0)
    dist_sg = (1.0 - coh_ij).clamp(min=0.0)
    dist_sg.fill_diagonal_(0.0)
    sg_leaf_w, sg_masks, sg_lut0, sg_lut1, sg_lut2 = _build_ultrametric_spin_glass_lut(dist_sg)

    # Spectrul Ruelle pentru telemetrie Argand
    ruelle_std = L_ruelle.std().clamp(min=1e-12)
    L_ruelle_tilde = (L_ruelle - L_ruelle.mean()) / (ruelle_std * math.sqrt(float(N)))
    ruelle_eigs = torch.linalg.eigvals(L_ruelle_tilde)

    joker_pack: Dict[str, torch.Tensor] = {}
    if topo.joker_m is not None and state.joker_ema is not None:
        M_j = topo.joker_m
        rho_j = (0.50 * state.joker_ema[0] + 0.30 * state.joker_ema[1] + 0.20 * state.joker_ema[2]).clamp(min=1e-8)
        rho_j = rho_j / rho_j.sum()

        L_j = torch.zeros((M_j, M_j), dtype=torch.float64, device=dev)
        for l_idx, w_l in enumerate(params.ruelle_weights):
            L_j = L_j + w_l * state.joker_ruelle[l_idx]
        S_j = 0.5 * (L_j + L_j.T)
        A_j = 0.5 * (L_j - L_j.T)

        # Faza intrinsecă Ruelle ϑ_b ∈ (-π, π] a fiecărei bile Joker (100% echivariantă S_20, fără faze eigh!)
        z_j_phase = (S_j @ rho_j) + 1j * (A_j @ rho_j)
        theta_joker = torch.angle(z_j_phase)  # [20]

        # Hamiltonianul bipartit încurcat H_{45⊗20} (900 x 900)
        H_45 = -M_mat.real / m_norm_scale  # [45, 45]
        s_j_scale = S_j.abs().max().clamp(min=1e-8)
        H_20 = -S_j / s_j_scale - torch.diag(torch.log((rho_j * float(M_j)).clamp(min=1e-6)))
        h20_scale = torch.linalg.matrix_norm(H_20, ord=2).clamp(min=1e-8)
        H_20 = H_20 / h20_scale

        # Cuplaj inter-urne PMI cauzal (lag 0 + lag 1)
        indep = torch.outer(state.ema_node[1].clamp(min=1e-6), state.joker_ema[1].clamp(min=1e-6))
        pmi_0 = torch.log((state.cross_ema0.clamp(min=1e-8) + 1e-4) / (indep + 1e-4))
        c1_scale = state.cross_ema1.abs().max().clamp(min=1e-8)
        V_int_diag = -(pmi_0 + 0.5 * (state.cross_ema1 / c1_scale))  # [45, 20]
        v_scale = V_int_diag.abs().max().clamp(min=1e-8)
        V_int_diag = V_int_diag / v_scale

        I_45 = torch.eye(N, dtype=torch.float64, device=dev)
        I_20 = torch.eye(M_j, dtype=torch.float64, device=dev)
        H_joint = (
            torch.kron(H_45, I_20)
            + torch.kron(I_45, H_20)
            + torch.diag(V_int_diag.reshape(-1))
        )
        H_joint = 0.5 * (H_joint + H_joint.T)
        evals_J, evecs_J = torch.linalg.eigh(H_joint)
        boltz_J = torch.exp(-params.beta_joker * (evals_J - evals_J[0]))
        boltz_J = boltz_J / boltz_J.sum()
        rho_joint_diag = ((evecs_J ** 2) @ boltz_J).reshape(N, M_j).clamp(min=1e-15)  # [45, 20]

        # Urma parțială ρ_20 = Tr_{45}(ρ_{45⊗20}) și Entropia de Încurcare Von Neumann S_vN
        rho_blocks = ((evecs_J * boltz_J.unsqueeze(0)) @ evecs_J.T).reshape(N, M_j, N, M_j)
        rho_20 = torch.einsum("iaib->ab", rho_blocks)
        rho_20 = 0.5 * (rho_20 + rho_20.T)
        eigs_20 = torch.linalg.eigvalsh(rho_20).clamp(min=1e-15)
        eigs_20 = eigs_20 / eigs_20.sum()
        s_vn = -(eigs_20 * torch.log(eigs_20)).sum()

        # Faza Cartan orientată intrinsec cu tanh(Ω_curl) -> simetrică S_45 și invariantă gauge SU(3)!
        loop2 = torch.bmm(hol_loop, hol_loop)
        tr2 = torch.diagonal(loop2, dim1=-2, dim2=-1).sum(-1)
        cartan_raw = torch.angle(tr1 + 0.5 * tr2) / (2.0 * math.pi)
        curl_scale = Omega_curl.abs().mean().clamp(min=1e-12)
        chiral_sign = torch.tanh(Omega_curl / curl_scale)
        theta_sym = chiral_sign * cartan_raw  # produs de două 2-forme antisimetrice => simetric S_45!

        Theta3D = torch.zeros((N, N, N), dtype=torch.float64, device=dev)
        Theta3D[fi, fj, fk] = theta_sym
        Theta3D[fj, fk, fi] = theta_sym
        Theta3D[fk, fi, fj] = theta_sym
        Theta3D[fj, fi, fk] = theta_sym
        Theta3D[fi, fk, fj] = theta_sym
        Theta3D[fk, fj, fi] = theta_sym

        joker_pack = {
            "log_rho_joint": torch.log(rho_joint_diag * float(N * M_j)),  # [45, 20] raport față de uniform
            "theta_joker": theta_joker,                                    # [20]
            "Theta3D": Theta3D,                                            # [45, 45, 45]
            "s_vn": s_vn,
            "rho_20_diag": torch.diagonal(rho_20).real,
        }

    t_sg = time.perf_counter()

    # Coordonate spectrale 3D ale nodurilor pentru vizualizare Plotly WebGL
    L_norm = torch.eye(N, dtype=torch.float64, device=dev) - (
        W_adj / torch.sqrt(torch.outer(deg.clamp(min=1e-8), deg.clamp(min=1e-8)))
    )
    _, evecs_vis = torch.linalg.eigh(0.5 * (L_norm + L_norm.T))
    xyz_3d = evecs_vis[:, 1:4]

    hodge_norm_sq = (w1 * (J_1form ** 2)).sum().clamp(min=1e-20)
    curl_energy_ratio = ((w1 * (J_curl ** 2)).sum() / hodge_norm_sq).item()
    hodge_inner_err = ((w1 * J_exact * J_curl).sum().abs() / hodge_norm_sq).item()

    return {
        "K_kernel": K_kernel,
        "k_eigs": k_eigs,
        "Curl3D": Curl3D,
        "sg_leaf_w": sg_leaf_w,
        "sg_masks": sg_masks,
        "sg_lut0": sg_lut0,
        "sg_lut1": sg_lut1,
        "sg_lut2": sg_lut2,
        "joker_pack": joker_pack,
        "W_faces": W_faces,
        "J_1form": J_1form,
        "J_exact": J_exact,
        "J_curl": J_curl,
        "w1": w1,
        "delta1_curl": delta1_curl,
        "hodge_inner_err": hodge_inner_err,
        "curl_energy_ratio": curl_energy_ratio,
        "ruelle_eigs": ruelle_eigs,
        "bochner_evals": evals_B,
        "xyz_3d": xyz_3d,
        "rho_emp": rho_emp,
        "timings_op": {
            "O2_hodge_sec": t_hodge - t0,
            "O3_bochner_sec": t_bochner - t_hodge,
            "O4_ultrametric_joker_sec": t_sg - t_bochner,
        },
    }


# ============================================================================
# 3. CHOLESKY DESPACHETAT k×k, CAUCHY-BINET EXACT & ONLINE LOG-SUM-EXP (O5)
# ============================================================================

def cauchy_binet_exact_ek(eigs: torch.Tensor, k: int) -> float:
    """Calculează exact polinomul simetric elementar e_k(λ_1..λ_N) = ∑_{|σ|=k} ∏_{i∈σ} λ_i în float64."""
    lam = eigs.detach().to(torch.float64).cpu().numpy()
    dp = np.zeros(k + 1, dtype=np.float64)
    dp[0] = 1.0
    for val in lam:
        for r in range(k, 0, -1):
            dp[r] += val * dp[r - 1]
    return float(dp[k])


def unrolled_hermitian_cholesky_logdet(A: torch.Tensor, k: int) -> torch.Tensor:
    """Calculează exact ln det(A) pentru un lot [M, k, k] de matrici hermitiene pozitiv-definite
    prin factorizare Cholesky despachetată în registre (fără apel torch.linalg.det/cholesky!).
    """
    cols: List[List[torch.Tensor]] = [[None] * k for _ in range(k)]  # type: ignore[list-item]
    logdet = torch.zeros(A.shape[0], dtype=torch.float64, device=A.device)

    for p in range(k):
        diag_p = A[:, p, p].real.to(torch.float64)
        for c in range(p):
            l_pc = cols[p][c]
            diag_p = diag_p - (l_pc.real ** 2 + l_pc.imag ** 2)
        l_pp = torch.sqrt(diag_p.clamp(min=1e-30))
        cols[p][p] = l_pp.to(A.dtype)
        logdet = logdet + 2.0 * torch.log(l_pp)

        inv_lpp = (1.0 / l_pp).to(A.dtype)
        for r in range(p + 1, k):
            s_rp = A[:, r, p]
            for c in range(p):
                s_rp = s_rp - cols[r][c] * cols[p][c].conj()
            cols[r][p] = s_rp * inv_lpp

    return logdet


def _eval_sg_cut(
    comb: torch.Tensor,
    sg_leaf_w: torch.Tensor,
    sg_masks: torch.Tensor,
    lut0: torch.Tensor,
    lut1: torch.Tensor,
    lut2: torch.Tensor,
) -> torch.Tensor:
    leaves_m = sg_masks[comb]  # [M, k]
    mask = leaves_m[:, 0]
    for idx in range(1, comb.shape[1]):
        mask = mask | leaves_m[:, idx]
    b0 = mask & 0xFFFF
    b1 = (mask >> 16) & 0xFFFF
    b2 = (mask >> 32) & 0xFFFF
    internal_len = lut0[b0] + lut1[b1] + lut2[b2]
    leaf_len = sg_leaf_w[comb].sum(dim=1)
    return internal_len + leaf_len


def _select_jastrow_multiplet(
    cand_comb: torch.Tensor,
    cand_joker: torch.Tensor,
    cand_log_p: torch.Tensor,
    k: int,
    has_joker: bool,
    gamma_jastrow: float,
) -> Tuple[List[Dict], List[int], int]:
    """Selectează determinist multipletul (α, β, γ) maximizând ∑ ln P(σ_u) + γ_J ln det G."""
    comb_np = cand_comb.detach().cpu().numpy()   # [P, k] 0-based
    jok_np = cand_joker.detach().cpu().numpy()   # [P] 0-based
    lp_np = cand_log_p.detach().cpu().numpy()    # [P]

    order = np.argsort(-lp_np, kind="mergesort")
    comb_np = comb_np[order]
    jok_np = jok_np[order]
    lp_np = lp_np[order]

    P_len = comb_np.shape[0]
    N_max = int(comb_np.max()) + 1
    ind = np.zeros((P_len, N_max), dtype=np.float64)
    rows = np.arange(P_len)[:, None]
    ind[rows, comb_np] = 1.0

    # α: starea fundamentală globală
    idx_a = 0
    ov_a = (ind @ ind[idx_a]) / float(k)  # [P] în [0, 1]

    # β: maximizează lp[u] + γ_J ln(1 - ov_{αu}²), cu |σ_α ∩ σ_u| <= k - 2 și Joker diferit
    det2 = 1.0 - (ov_a ** 2)
    valid_b = (ov_a <= float(k - 2) / float(k) + 1e-9) & (det2 > 1e-6)
    if has_joker:
        valid_b = valid_b & (jok_np != jok_np[idx_a])
    if not np.any(valid_b):
        valid_b = det2 > 1e-6
    scores_b = np.where(valid_b, lp_np + gamma_jastrow * np.log(np.maximum(det2, 1e-12)), -1e30)
    idx_b = int(np.argmax(scores_b))

    # γ: maximizează lp[v] + γ_J ln det G_3, cu Joker diferit de α și β
    ov_b = (ind @ ind[idx_b]) / float(k)
    o_ab = float(ov_a[idx_b])
    det3 = 1.0 + 2.0 * o_ab * ov_a * ov_b - (o_ab ** 2) - (ov_a ** 2) - (ov_b ** 2)
    max_ov = float(k - 2) / float(k) + 1e-9
    valid_c = (ov_a <= max_ov) & (ov_b <= max_ov) & (det3 > 1e-6)
    if has_joker:
        valid_c = valid_c & (jok_np != jok_np[idx_a]) & (jok_np != jok_np[idx_b])
    if not np.any(valid_c):
        valid_c = det3 > 1e-6
    scores_c = np.where(valid_c, lp_np + gamma_jastrow * np.log(np.maximum(det3, 1e-12)), -1e30)
    idx_c = int(np.argmax(scores_c))

    chosen = [idx_a, idx_b, idx_c]
    labels = ("α", "β", "γ")
    variants: List[Dict] = []
    union_balls: set[int] = set()
    freq_core: Dict[int, int] = {}

    for rank_i, c_idx in enumerate(chosen):
        balls_1based = [int(x) + 1 for x in comb_np[c_idx].tolist()]
        union_balls.update(balls_1based)
        for b_num in balls_1based:
            freq_core[b_num] = freq_core.get(b_num, 0) + 1
        entry = {
            "label": labels[rank_i],
            "ticket": balls_1based,
            "log_prob": float(lp_np[c_idx]),
            "prob": float(math.exp(max(lp_np[c_idx], -700.0))),
            "energy": float(-lp_np[c_idx]),
        }
        if has_joker:
            entry["joker"] = int(jok_np[c_idx]) + 1
        variants.append(entry)

    # Nucleu determinist din top-64 stări ponderate cu probabilitatea lor relativă
    top_n = min(64, P_len)
    w_top = np.exp(lp_np[:top_n] - lp_np[0])
    w_top = w_top / w_top.sum()
    node_occ = w_top @ ind[:top_n]
    core_1based = sorted(int(i) + 1 for i in np.where(node_occ >= 0.50)[0].tolist())
    if not core_1based:
        core_1based = [int(x) + 1 for x in comb_np[idx_a].tolist()]

    return variants, core_1based, len(union_balls)


@torch.no_grad()
def evaluate_full_space(
    topo: SimplicialTopology,
    ops: Dict[str, torch.Tensor],
    params: PLV3Params = DEFAULT_PARAMS,
    pure_determinantal: bool = False,
    precision_c128: bool = True,
) -> Dict:
    """Evaluează exact toate cele C(N,k) (sau C(45,5)×20) stări prin Cholesky despachetat + Online Log-Sum-Exp."""
    t_start = time.perf_counter()
    dev = topo.device
    N, k = topo.N, topo.k_ticket
    has_joker = topo.joker_m is not None and bool(ops["joker_pack"])
    K_mat = ops["K_kernel"].to(torch.complex128 if precision_c128 else torch.complex64)
    Curl3D = ops["Curl3D"]
    sg_leaf_w = ops["sg_leaf_w"]
    sg_masks = ops["sg_masks"]
    lut0, lut1, lut2 = ops["sg_lut0"], ops["sg_lut1"], ops["sg_lut2"]

    inv_sqrt_faces = 1.0 / math.sqrt(float(max(topo.num_sub_faces, 1)))
    inv_k = 1.0 / float(k)

    # Acumulatori Online Log-Sum-Exp în float64
    run_max = float("-inf")
    run_sum_z = 0.0
    run_sum_w_lnw = 0.0  # pentru entropia Shannon exactă H = ln Z - (∑ W ln W) / Z
    run_marg_main = torch.zeros(N, dtype=torch.float64, device=dev)
    run_marg_joker = torch.zeros(topo.joker_m or 1, dtype=torch.float64, device=dev)

    pool_k = min(params.pool_size, topo.total_base_states)
    best_lw = torch.full((pool_k,), float("-inf"), dtype=torch.float64, device=dev)
    best_comb = torch.zeros((pool_k, k), dtype=torch.int64, device=dev)
    best_jok = torch.zeros((pool_k,), dtype=torch.int64, device=dev)

    if has_joker:
        jp = ops["joker_pack"]
        log_rho_joint = jp["log_rho_joint"]   # [45, 20]
        theta_joker = jp["theta_joker"]       # [20]
        Theta3D = jp["Theta3D"]               # [45, 45, 45]

    for start in range(0, topo.total_base_states, params.chunk_size):
        end = min(start + params.chunk_size, topo.total_base_states)
        comb = topo.unrank_chunk(start, end)  # [M, k]

        K_sub = K_mat[comb.unsqueeze(2), comb.unsqueeze(1)]  # [M, k, k]
        log_det = unrolled_hermitian_cholesky_logdet(K_sub, k)  # [M] float64

        if pure_determinantal:
            base_lw = log_det
        else:
            curl_sum = Curl3D[
                comb[:, topo.sub_fi], comb[:, topo.sub_fj], comb[:, topo.sub_fk]
            ].sum(dim=1)
            sg_cut = _eval_sg_cut(comb, sg_leaf_w, sg_masks, lut0, lut1, lut2)
            base_lw = log_det - inv_sqrt_faces * curl_sum - inv_k * sg_cut

        if has_joker and not pure_determinantal:
            M_c = comb.shape[0]
            M_j = int(topo.joker_m)
            # Cuplaj bipartit [M, 20] + fază Cartan continuă (fără round înainte de cos!)
            joint_term = log_rho_joint[comb].mean(dim=1)  # [M, 20]
            theta_sum = Theta3D[
                comb[:, topo.sub_fi], comb[:, topo.sub_fj], comb[:, topo.sub_fk]
            ].sum(dim=1)  # [M]
            phase_diff = theta_joker.unsqueeze(0) - (2.0 * math.pi) * theta_sum.unsqueeze(1)  # [M, 20]
            cs_pen = params.lambda_cs * (1.0 - torch.cos(phase_diff))
            lw_full = base_lw.unsqueeze(1) + joint_term - cs_pen  # [M, 20]

            c_max = float(lw_full.max().item())
            m_new = max(run_max, c_max)
            alpha_old = math.exp(run_max - m_new) if run_max > float("-inf") else 0.0
            w_rel = torch.exp(lw_full - m_new)  # [M, 20]

            run_sum_z = run_sum_z * alpha_old + float(w_rel.sum().item())
            run_sum_w_lnw = run_sum_w_lnw * alpha_old + float((w_rel * lw_full).sum().item())
            w_main = w_rel.sum(dim=1)  # [M]
            run_marg_main = run_marg_main * alpha_old
            run_marg_main.scatter_add_(0, comb.reshape(-1), w_main.unsqueeze(1).expand(-1, k).reshape(-1))
            run_marg_joker = run_marg_joker * alpha_old + w_rel.sum(dim=0)
            run_max = m_new

            flat_lw = lw_full.reshape(-1)
            take = min(pool_k, flat_lw.shape[0])
            top_vals, top_idx = torch.topk(flat_lw, k=take, largest=True)
            top_c_idx = top_idx // M_j
            top_j_idx = top_idx % M_j
            m_lw = torch.cat([best_lw, top_vals])
            m_cb = torch.cat([best_comb, comb[top_c_idx]], dim=0)
            m_jk = torch.cat([best_jok, top_j_idx], dim=0)
            _, keep = torch.topk(m_lw, k=pool_k, largest=True)
            best_lw, best_comb, best_jok = m_lw[keep], m_cb[keep], m_jk[keep]
        else:
            c_max = float(base_lw.max().item())
            m_new = max(run_max, c_max)
            alpha_old = math.exp(run_max - m_new) if run_max > float("-inf") else 0.0
            w_rel = torch.exp(base_lw - m_new)  # [M]

            run_sum_z = run_sum_z * alpha_old + float(w_rel.sum().item())
            run_sum_w_lnw = run_sum_w_lnw * alpha_old + float((w_rel * base_lw).sum().item())
            run_marg_main = run_marg_main * alpha_old
            run_marg_main.scatter_add_(0, comb.reshape(-1), w_rel.unsqueeze(1).expand(-1, k).reshape(-1))
            run_max = m_new

            take = min(pool_k, base_lw.shape[0])
            top_vals, top_idx = torch.topk(base_lw, k=take, largest=True)
            m_lw = torch.cat([best_lw, top_vals])
            m_cb = torch.cat([best_comb, comb[top_idx]], dim=0)
            m_jk = torch.cat([best_jok, torch.zeros_like(top_idx)], dim=0)
            _, keep = torch.topk(m_lw, k=pool_k, largest=True)
            best_lw, best_comb, best_jok = m_lw[keep], m_cb[keep], m_jk[keep]

    log_Z = run_max + math.log(run_sum_z)
    Z_exact = math.exp(log_Z) if log_Z < 700.0 else float("inf")
    mean_lnw = run_sum_w_lnw / run_sum_z
    shannon_entropy_nats = log_Z - mean_lnw

    pi_inclusion = run_marg_main / run_sum_z  # ∑ π_i = k
    pi_prob = pi_inclusion / float(k)         # ∑ p_i = 1
    joker_prob = (run_marg_joker / run_sum_z) if (has_joker and not pure_determinantal) else None

    cand_log_p = best_lw - log_Z
    sorted_lp, sort_ord = torch.sort(cand_log_p, descending=True)
    gap_ln_w = float((sorted_lp[0] - sorted_lp[1]).item()) if sorted_lp.shape[0] > 1 else 0.0

    variants, det_core, distinct_covered = _select_jastrow_multiplet(
        best_comb, best_jok, cand_log_p, k, has_joker and not pure_determinantal, params.gamma_jastrow
    )
    elapsed_eval = time.perf_counter() - t_start

    return {
        "log_Z": log_Z,
        "Z_exact": Z_exact,
        "shannon_entropy_nats": shannon_entropy_nats,
        "pi_inclusion": pi_inclusion,
        "pi_prob": pi_prob,
        "joker_prob": joker_prob,
        "variants": variants,
        "deterministic_core": det_core,
        "distinct_covered": distinct_covered,
        "ground_gap_ln_w": gap_ln_w,
        "eval_sec": elapsed_eval,
        "total_states_evaluated": topo.total_base_states * (int(topo.joker_m) if (has_joker and not pure_determinantal) else 1),
    }
