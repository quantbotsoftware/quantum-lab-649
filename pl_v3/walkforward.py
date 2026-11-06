"""PL-V3 — Walk-Forward Integral (B_steps = 32) și Motor Incremental Real-Time pe CURRENT_LIVE.json.

Protocol sigilat: pl_v3/PROTOCOL_PLV3.md (SIGILIU_PROTOCOL_PLV3.json).
Calcul clasic pe GPU (CUDA / PyTorch) și CPU; positive_claims_allowed = False.
Zero metrici comerciale/financiare/contabile; zero sub-eșantionare a pașilor istorici.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gc
import hashlib
import json
import logging
import math
import os
import sys
import tempfile
import time
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
TU3 = QL / "tu3"
for _p in (str(QL), str(TU3)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.getLogger("streamlit.runtime.caching.cache_data_api").setLevel(logging.ERROR)
import parser_multi as PM  # noqa: E402


def _resolve_live_source_and_key(mode: str, live_root: Optional[Path] = None) -> Tuple[Path, str]:
    """Rezolvă și verifică lanțul CURRENT_LIVE.json -> MANIFEST_LIVE.json -> JSONL și returnează (path, live_key)."""
    if live_root is None:
        resolved_path, prov = PM.resolve_live(mode)
        ui_mod = sys.modules.get("tu3.ui_tu3")
        if ui_mod is not None and hasattr(ui_mod, "live_key"):
            return resolved_path, str(ui_mod.live_key(mode))
        return resolved_path, str(prov["file_sha256"])
    resolved_path, prov = PM.resolve_live(mode, live_root=Path(live_root))
    return resolved_path, str(prov["file_sha256"])

from pl_v3.core import (  # noqa: E402
    DEFAULT_PARAMS,
    PLV3Params,
    PLV3State,
    SimplicialTopology,
    _eval_sg_cut,
    _select_jastrow_multiplet,
    advance_one_step,
    advance_steps,
    extract_step_slices,
    forward_operators_from_state,
    init_state,
    unrolled_hermitian_cholesky_logdet,
)

WARMUP_STEPS: int = 100
B_STEPS_DEFAULT: int = 32
EW_HALF_LIFE: float = 26.0
CACHE_DIR_DEFAULT: Path = HERE / "cache"
OUT_DIR_DEFAULT: Path = HERE / "rezultate"

GAME_CONFIGS: Dict[str, Tuple[int, int, int, Optional[int]]] = {
    "649": (49, 6, 6, None),
    "540": (40, 6, 5, None),
    "joker": (45, 5, 5, 20),
}

COMB6_5: Tuple[Tuple[int, ...], ...] = tuple(combinations(range(6), 5))


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _build_face_lookup(topo: SimplicialTopology) -> torch.Tensor:
    N = topo.N
    fi, fj, fk = topo.faces[:, 0], topo.faces[:, 1], topo.faces[:, 2]
    lookup = torch.full((N, N, N), -1, dtype=torch.int64, device=topo.device)
    lookup[fi, fj, fk] = torch.arange(topo.num_faces, dtype=torch.int64, device=topo.device)
    return lookup


# ============================================================================
# 1. KERNELURI COMPILATE MULTI-PAS (B_steps = 32) ȘI 1-PAS (REAL-TIME < 0.35s)
# ============================================================================

@torch.compile
def _eval_chunk_649_b32(
    comb: torch.Tensor,
    sub_f: torch.Tensor,
    K_re: torch.Tensor,
    K_im: torch.Tensor,
    K_diag: torch.Tensor,
    face_vort: torch.Tensor,
    sg_leaf_w: torch.Tensor,
    sg_masks: torch.Tensor,
    lut0: torch.Tensor,
    lut1: torch.Tensor,
    lut2: torch.Tensor,
    b_off: torch.Tensor,
) -> torch.Tensor:
    cols_re: List[List[Optional[torch.Tensor]]] = [[None] * 6 for _ in range(6)]
    cols_im: List[List[Optional[torch.Tensor]]] = [[None] * 6 for _ in range(6)]
    logdet = torch.zeros((comb.shape[0], 32), dtype=torch.float64, device=comb.device)
    for p in range(6):
        cp = comb[:, p]
        diag_p = K_diag[cp]
        for c in range(p):
            lr = cols_re[p][c]
            li = cols_im[p][c]
            assert lr is not None and li is not None
            diag_p = diag_p - (lr * lr + li * li)
        l_pp = torch.sqrt(diag_p.clamp(min=1e-30))
        logdet = logdet + 2.0 * torch.log(l_pp)
        inv_lpp = 1.0 / l_pp
        for r in range(p + 1, 6):
            idx_rp = comb[:, r] * 49 + cp
            sr = K_re[idx_rp]
            si = K_im[idx_rp]
            for c in range(p):
                rr, ri = cols_re[r][c], cols_im[r][c]
                pr, pi = cols_re[p][c], cols_im[p][c]
                assert rr is not None and ri is not None and pr is not None and pi is not None
                sr = sr - (rr * pr + ri * pi)
                si = si - (ri * pr - rr * pi)
            cols_re[r][p] = sr * inv_lpp
            cols_im[r][p] = si * inv_lpp

    curl_sum = face_vort[sub_f[:, 0]]
    for f_pos in range(1, 20):
        curl_sum = curl_sum + face_vort[sub_f[:, f_pos]]

    mask = sg_masks[comb[:, 0]]
    leaf_len = sg_leaf_w[comb[:, 0]]
    for d in range(1, 6):
        cd = comb[:, d]
        mask = mask | sg_masks[cd]
        leaf_len = leaf_len + sg_leaf_w[cd]

    b0 = (mask & 0xFFFF) * 32 + b_off
    b1 = ((mask >> 16) & 0xFFFF) * 32 + b_off
    b2 = ((mask >> 32) & 0xFFFF) * 32 + b_off
    sg_cut = lut0.take(b0) + lut1.take(b1) + lut2.take(b2) + leaf_len
    return logdet - (1.0 / math.sqrt(20.0)) * curl_sum - (1.0 / 6.0) * sg_cut


@torch.compile
def _eval_chunk_540_b32(
    comb: torch.Tensor,
    sub_f: torch.Tensor,
    K_re: torch.Tensor,
    K_im: torch.Tensor,
    K_diag: torch.Tensor,
    face_vort: torch.Tensor,
    sg_leaf_w: torch.Tensor,
    sg_masks: torch.Tensor,
    lut0: torch.Tensor,
    lut1: torch.Tensor,
    lut2: torch.Tensor,
    b_off: torch.Tensor,
) -> torch.Tensor:
    cols_re: List[List[Optional[torch.Tensor]]] = [[None] * 5 for _ in range(5)]
    cols_im: List[List[Optional[torch.Tensor]]] = [[None] * 5 for _ in range(5)]
    logdet = torch.zeros((comb.shape[0], 32), dtype=torch.float64, device=comb.device)
    for p in range(5):
        cp = comb[:, p]
        diag_p = K_diag[cp]
        for c in range(p):
            lr = cols_re[p][c]
            li = cols_im[p][c]
            assert lr is not None and li is not None
            diag_p = diag_p - (lr * lr + li * li)
        l_pp = torch.sqrt(diag_p.clamp(min=1e-30))
        logdet = logdet + 2.0 * torch.log(l_pp)
        inv_lpp = 1.0 / l_pp
        for r in range(p + 1, 5):
            idx_rp = comb[:, r] * 40 + cp
            sr = K_re[idx_rp]
            si = K_im[idx_rp]
            for c in range(p):
                rr, ri = cols_re[r][c], cols_im[r][c]
                pr, pi = cols_re[p][c], cols_im[p][c]
                assert rr is not None and ri is not None and pr is not None and pi is not None
                sr = sr - (rr * pr + ri * pi)
                si = si - (ri * pr - rr * pi)
            cols_re[r][p] = sr * inv_lpp
            cols_im[r][p] = si * inv_lpp

    curl_sum = face_vort[sub_f[:, 0]]
    for f_pos in range(1, 10):
        curl_sum = curl_sum + face_vort[sub_f[:, f_pos]]

    mask = sg_masks[comb[:, 0]]
    leaf_len = sg_leaf_w[comb[:, 0]]
    for d in range(1, 5):
        cd = comb[:, d]
        mask = mask | sg_masks[cd]
        leaf_len = leaf_len + sg_leaf_w[cd]

    b0 = (mask & 0xFFFF) * 32 + b_off
    b1 = ((mask >> 16) & 0xFFFF) * 32 + b_off
    b2 = ((mask >> 32) & 0xFFFF) * 32 + b_off
    sg_cut = lut0.take(b0) + lut1.take(b1) + lut2.take(b2) + leaf_len
    return logdet - (1.0 / math.sqrt(10.0)) * curl_sum - (1.0 / 5.0) * sg_cut


@torch.compile
def _eval_chunk_joker_b32(
    comb: torch.Tensor,
    sub_f: torch.Tensor,
    K_re: torch.Tensor,
    K_im: torch.Tensor,
    K_diag: torch.Tensor,
    face_vort: torch.Tensor,
    theta_faces: torch.Tensor,
    log_rho_joint: torch.Tensor,
    theta_joker: torch.Tensor,
    sg_leaf_w: torch.Tensor,
    sg_masks: torch.Tensor,
    lut0: torch.Tensor,
    lut1: torch.Tensor,
    lut2: torch.Tensor,
    b_off: torch.Tensor,
    lambda_cs: float,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Returnează (base_lw [M, 32], theta_sum [M, 32], joint_term [M, 32, 20]) fuzionate."""
    cols_re: List[List[Optional[torch.Tensor]]] = [[None] * 5 for _ in range(5)]
    cols_im: List[List[Optional[torch.Tensor]]] = [[None] * 5 for _ in range(5)]
    logdet = torch.zeros((comb.shape[0], 32), dtype=torch.float64, device=comb.device)
    for p in range(5):
        cp = comb[:, p]
        diag_p = K_diag[cp]
        for c in range(p):
            lr = cols_re[p][c]
            li = cols_im[p][c]
            assert lr is not None and li is not None
            diag_p = diag_p - (lr * lr + li * li)
        l_pp = torch.sqrt(diag_p.clamp(min=1e-30))
        logdet = logdet + 2.0 * torch.log(l_pp)
        inv_lpp = 1.0 / l_pp
        for r in range(p + 1, 5):
            idx_rp = comb[:, r] * 45 + cp
            sr = K_re[idx_rp]
            si = K_im[idx_rp]
            for c in range(p):
                rr, ri = cols_re[r][c], cols_im[r][c]
                pr, pi = cols_re[p][c], cols_im[p][c]
                assert rr is not None and ri is not None and pr is not None and pi is not None
                sr = sr - (rr * pr + ri * pi)
                si = si - (ri * pr - rr * pi)
            cols_re[r][p] = sr * inv_lpp
            cols_im[r][p] = si * inv_lpp

    f0 = sub_f[:, 0]
    curl_sum = face_vort[f0]
    theta_sum = theta_faces[f0]
    for f_pos in range(1, 10):
        fi_p = sub_f[:, f_pos]
        curl_sum = curl_sum + face_vort[fi_p]
        theta_sum = theta_sum + theta_faces[fi_p]

    c0 = comb[:, 0]
    mask = sg_masks[c0]
    leaf_len = sg_leaf_w[c0]
    j_sum = log_rho_joint[c0]
    for d in range(1, 5):
        cd = comb[:, d]
        mask = mask | sg_masks[cd]
        leaf_len = leaf_len + sg_leaf_w[cd]
        j_sum = j_sum + log_rho_joint[cd]

    b0 = (mask & 0xFFFF) * 32 + b_off
    b1 = ((mask >> 16) & 0xFFFF) * 32 + b_off
    b2 = ((mask >> 32) & 0xFFFF) * 32 + b_off
    sg_cut = lut0.take(b0) + lut1.take(b1) + lut2.take(b2) + leaf_len
    base_lw = logdet - (1.0 / math.sqrt(10.0)) * curl_sum - (1.0 / 5.0) * sg_cut

    phase_diff = theta_joker.unsqueeze(0) - (2.0 * math.pi) * theta_sum.unsqueeze(2)
    lw_full = base_lw.unsqueeze(2) + (0.2 * j_sum) - lambda_cs * (1.0 - torch.cos(phase_diff))
    j_max_val, j_max_idx = lw_full.max(dim=2)
    return lw_full, j_max_val, j_max_idx


COMB6_3: Tuple[Tuple[int, int, int], ...] = tuple(combinations(range(6), 3))
COMB5_3: Tuple[Tuple[int, int, int], ...] = tuple(combinations(range(5), 3))


@torch.compile
def _eval_chunk_1step_k6(
    comb: torch.Tensor,
    K_re: torch.Tensor,
    K_im: torch.Tensor,
    K_diag: torch.Tensor,
    curl_flat: torch.Tensor,
    sg_leaf_w: torch.Tensor,
    sg_masks: torch.Tensor,
    lut0: torch.Tensor,
    lut1: torch.Tensor,
    lut2: torch.Tensor,
) -> torch.Tensor:
    cs = [comb[:, d] for d in range(6)]
    cols_re: List[List[Optional[torch.Tensor]]] = [[None] * 6 for _ in range(6)]
    cols_im: List[List[Optional[torch.Tensor]]] = [[None] * 6 for _ in range(6)]
    logdet = torch.zeros(comb.shape[0], dtype=torch.float64, device=comb.device)
    for p in range(6):
        cp = cs[p]
        diag_p = K_diag[cp]
        for c in range(p):
            lr, li = cols_re[p][c], cols_im[p][c]
            assert lr is not None and li is not None
            diag_p = diag_p - (lr * lr + li * li)
        l_pp = torch.sqrt(diag_p.clamp(min=1e-30))
        logdet = logdet + 2.0 * torch.log(l_pp)
        inv_lpp = 1.0 / l_pp
        for r in range(p + 1, 6):
            idx_rp = cs[r] * 49 + cp
            sr, si = K_re[idx_rp], K_im[idx_rp]
            for c in range(p):
                rr, ri = cols_re[r][c], cols_im[r][c]
                pr, pi = cols_re[p][c], cols_im[p][c]
                assert rr is not None and ri is not None and pr is not None and pi is not None
                sr = sr - (rr * pr + ri * pi)
                si = si - (ri * pr - rr * pi)
            cols_re[r][p] = sr * inv_lpp
            cols_im[r][p] = si * inv_lpp
    curl_sum = torch.zeros_like(logdet)
    for a, b, c in COMB6_3:
        curl_sum = curl_sum + curl_flat[cs[a] * 2401 + cs[b] * 49 + cs[c]]
    mask = sg_masks[cs[0]]
    leaf_len = sg_leaf_w[cs[0]]
    for d in range(1, 6):
        cd = cs[d]
        mask = mask | sg_masks[cd]
        leaf_len = leaf_len + sg_leaf_w[cd]
    sg_cut = lut0[mask & 0xFFFF] + lut1[(mask >> 16) & 0xFFFF] + lut2[(mask >> 32) & 0xFFFF] + leaf_len
    return logdet - (1.0 / math.sqrt(20.0)) * curl_sum - (1.0 / 6.0) * sg_cut


@torch.compile
def _eval_chunk_1step_k5(
    comb: torch.Tensor,
    N_stride: int,
    K_re: torch.Tensor,
    K_im: torch.Tensor,
    K_diag: torch.Tensor,
    curl_flat: torch.Tensor,
    sg_leaf_w: torch.Tensor,
    sg_masks: torch.Tensor,
    lut0: torch.Tensor,
    lut1: torch.Tensor,
    lut2: torch.Tensor,
) -> torch.Tensor:
    cs = [comb[:, d] for d in range(5)]
    n2 = N_stride * N_stride
    cols_re: List[List[Optional[torch.Tensor]]] = [[None] * 5 for _ in range(5)]
    cols_im: List[List[Optional[torch.Tensor]]] = [[None] * 5 for _ in range(5)]
    logdet = torch.zeros(comb.shape[0], dtype=torch.float64, device=comb.device)
    for p in range(5):
        cp = cs[p]
        diag_p = K_diag[cp]
        for c in range(p):
            lr, li = cols_re[p][c], cols_im[p][c]
            assert lr is not None and li is not None
            diag_p = diag_p - (lr * lr + li * li)
        l_pp = torch.sqrt(diag_p.clamp(min=1e-30))
        logdet = logdet + 2.0 * torch.log(l_pp)
        inv_lpp = 1.0 / l_pp
        for r in range(p + 1, 5):
            idx_rp = cs[r] * N_stride + cp
            sr, si = K_re[idx_rp], K_im[idx_rp]
            for c in range(p):
                rr, ri = cols_re[r][c], cols_im[r][c]
                pr, pi = cols_re[p][c], cols_im[p][c]
                assert rr is not None and ri is not None and pr is not None and pi is not None
                sr = sr - (rr * pr + ri * pi)
                si = si - (ri * pr - rr * pi)
            cols_re[r][p] = sr * inv_lpp
            cols_im[r][p] = si * inv_lpp
    curl_sum = torch.zeros_like(logdet)
    for a, b, c in COMB5_3:
        curl_sum = curl_sum + curl_flat[cs[a] * n2 + cs[b] * N_stride + cs[c]]
    mask = sg_masks[cs[0]]
    leaf_len = sg_leaf_w[cs[0]]
    for d in range(1, 5):
        cd = cs[d]
        mask = mask | sg_masks[cd]
        leaf_len = leaf_len + sg_leaf_w[cd]
    sg_cut = lut0[mask & 0xFFFF] + lut1[(mask >> 16) & 0xFFFF] + lut2[(mask >> 32) & 0xFFFF] + leaf_len
    return logdet - (1.0 / math.sqrt(10.0)) * curl_sum - (1.0 / 5.0) * sg_cut


@torch.no_grad()
def evaluate_full_space_fast(
    topo: SimplicialTopology,
    ops: Dict[str, Any],
    params: PLV3Params = DEFAULT_PARAMS,
    face_lookup: Optional[torch.Tensor] = None,
) -> Dict[str, Any]:
    """Evaluator 1-pas fuzionat pe GPU (< 0.25s pe 6/49, < 0.08s pe Joker, < 0.03s pe 5/40),
    numeric identic (< 1e-14) cu pl_v3.core.evaluate_full_space.
    """
    if topo.device.type != "cuda":
        from pl_v3.core import evaluate_full_space
        return evaluate_full_space(topo, ops, params=params)

    t_start = time.perf_counter()
    dev = topo.device
    N, k = topo.N, topo.k_ticket
    has_joker = topo.joker_m is not None and bool(ops["joker_pack"])

    K_mat = ops["K_kernel"].to(torch.complex128)
    K_re = K_mat.real.reshape(-1).contiguous()
    K_im = K_mat.imag.reshape(-1).contiguous()
    K_diag = torch.diagonal(K_mat).real.contiguous()
    curl_flat = ops["Curl3D"].reshape(-1).contiguous()
    sg_leaf_w = ops["sg_leaf_w"]
    sg_masks = ops["sg_masks"]
    lut0, lut1, lut2 = ops["sg_lut0"], ops["sg_lut1"], ops["sg_lut2"]

    run_max_t = torch.tensor(float("-inf"), dtype=torch.float64, device=dev)
    run_sum_z_t = torch.tensor(0.0, dtype=torch.float64, device=dev)
    run_sum_w_lnw_t = torch.tensor(0.0, dtype=torch.float64, device=dev)
    run_marg_main = torch.zeros(N, dtype=torch.float64, device=dev)
    run_marg_joker = torch.zeros(topo.joker_m or 1, dtype=torch.float64, device=dev)

    pool_k = min(params.pool_size, topo.total_base_states)
    best_lw = torch.full((pool_k,), float("-inf"), dtype=torch.float64, device=dev)
    best_comb = torch.zeros((pool_k, k), dtype=torch.int64, device=dev)
    best_jok = torch.zeros((pool_k,), dtype=torch.int64, device=dev)

    if has_joker:
        jp = ops["joker_pack"]
        log_rho_joint = jp["log_rho_joint"]
        theta_joker = jp["theta_joker"]
        Theta3D = jp["Theta3D"]

    chunk_sz = params.chunk_size
    for start in range(0, topo.total_base_states, chunk_sz):
        end = min(start + chunk_sz, topo.total_base_states)
        comb = topo.unrank_chunk(start, end)
        m_len = comb.shape[0]
        if m_len < chunk_sz and topo.total_base_states > chunk_sz:
            comb_in = torch.cat([comb, comb[:1].expand(chunk_sz - m_len, -1)], dim=0)
        else:
            comb_in = comb

        if k == 6 and N == 49:
            base_lw = _eval_chunk_1step_k6(
                comb_in, K_re, K_im, K_diag, curl_flat, sg_leaf_w, sg_masks, lut0, lut1, lut2
            )[:m_len]
        else:
            base_lw = _eval_chunk_1step_k5(
                comb_in, N, K_re, K_im, K_diag, curl_flat, sg_leaf_w, sg_masks, lut0, lut1, lut2
            )[:m_len]

        if has_joker:
            M_j = int(topo.joker_m)
            joint_term = log_rho_joint[comb].mean(dim=1)
            theta_sum = Theta3D[comb[:, topo.sub_fi], comb[:, topo.sub_fj], comb[:, topo.sub_fk]].sum(dim=1)
            phase_diff = theta_joker.unsqueeze(0) - (2.0 * math.pi) * theta_sum.unsqueeze(1)
            lw_full = base_lw.unsqueeze(1) + joint_term - params.lambda_cs * (1.0 - torch.cos(phase_diff))

            c_max = lw_full.max()
            m_new = torch.maximum(run_max_t, c_max)
            alpha_old = torch.where(run_max_t > float("-inf"), torch.exp(run_max_t - m_new), torch.zeros_like(m_new))
            w_rel = torch.exp(lw_full - m_new)

            run_sum_z_t = run_sum_z_t * alpha_old + w_rel.sum()
            run_sum_w_lnw_t = run_sum_w_lnw_t * alpha_old + (w_rel * lw_full).sum()
            w_main = w_rel.sum(dim=1)
            run_marg_main = run_marg_main * alpha_old
            run_marg_main.scatter_add_(0, comb.reshape(-1), w_main.unsqueeze(1).expand(-1, k).reshape(-1))
            run_marg_joker = run_marg_joker * alpha_old + w_rel.sum(dim=0)
            run_max_t = m_new

            flat_lw = lw_full.reshape(-1)
            if start == 0:
                take = min(pool_k, flat_lw.shape[0])
                best_lw, top_idx = torch.topk(flat_lw, k=take, largest=True)
                best_comb = comb[top_idx // M_j]
                best_jok = top_idx % M_j
            else:
                cand_idx = torch.nonzero(flat_lw >= best_lw[-1], as_tuple=False).squeeze(1)
                if cand_idx.numel() > 0:
                    cand_vals = flat_lw[cand_idx]
                    if cand_vals.numel() > pool_k:
                        cand_vals, sub_i = torch.topk(cand_vals, k=pool_k, largest=True)
                        cand_idx = cand_idx[sub_i]
                    m_lw = torch.cat([best_lw, cand_vals])
                    m_cb = torch.cat([best_comb, comb[cand_idx // M_j]], dim=0)
                    m_jk = torch.cat([best_jok, cand_idx % M_j], dim=0)
                    best_lw, keep = torch.topk(m_lw, k=pool_k, largest=True)
                    best_comb, best_jok = m_cb[keep], m_jk[keep]
        else:
            c_max = base_lw.max()
            m_new = torch.maximum(run_max_t, c_max)
            alpha_old = torch.where(run_max_t > float("-inf"), torch.exp(run_max_t - m_new), torch.zeros_like(m_new))
            w_rel = torch.exp(base_lw - m_new)

            run_sum_z_t = run_sum_z_t * alpha_old + w_rel.sum()
            run_sum_w_lnw_t = run_sum_w_lnw_t * alpha_old + (w_rel * base_lw).sum()
            run_marg_main = run_marg_main * alpha_old
            run_marg_main.scatter_add_(0, comb.reshape(-1), w_rel.unsqueeze(1).expand(-1, k).reshape(-1))
            run_max_t = m_new

            if start == 0:
                take = min(pool_k, base_lw.shape[0])
                best_lw, top_idx = torch.topk(base_lw, k=take, largest=True)
                best_comb = comb[top_idx]
            else:
                cand_idx = torch.nonzero(base_lw >= best_lw[-1], as_tuple=False).squeeze(1)
                if cand_idx.numel() > 0:
                    cand_vals = base_lw[cand_idx]
                    if cand_vals.numel() > pool_k:
                        cand_vals, sub_i = torch.topk(cand_vals, k=pool_k, largest=True)
                        cand_idx = cand_idx[sub_i]
                    m_lw = torch.cat([best_lw, cand_vals])
                    m_cb = torch.cat([best_comb, comb[cand_idx]], dim=0)
                    m_jk = torch.cat([best_jok, torch.zeros_like(cand_idx)], dim=0)
                    best_lw, keep = torch.topk(m_lw, k=pool_k, largest=True)
                    best_comb, best_jok = m_cb[keep], m_jk[keep]

    run_max = float(run_max_t.item())
    run_sum_z = float(run_sum_z_t.item())
    run_sum_w_lnw = float(run_sum_w_lnw_t.item())
    log_Z = run_max + math.log(run_sum_z)
    Z_exact = math.exp(log_Z) if log_Z < 700.0 else float("inf")
    shannon_entropy_nats = log_Z - (run_sum_w_lnw / run_sum_z)

    pi_inclusion = run_marg_main / run_sum_z
    pi_prob = pi_inclusion / float(k)
    joker_prob = (run_marg_joker / run_sum_z) if has_joker else None

    cand_log_p = best_lw - log_Z
    sorted_lp, _ = torch.sort(cand_log_p, descending=True)
    gap_ln_w = float((sorted_lp[0] - sorted_lp[1]).item()) if sorted_lp.shape[0] > 1 else 0.0

    variants, det_core, distinct_covered = _select_jastrow_multiplet(
        best_comb, best_jok, cand_log_p, k, has_joker, params.gamma_jastrow
    )
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
        "eval_sec": time.perf_counter() - t_start,
        "total_states_evaluated": topo.total_base_states * (int(topo.joker_m) if has_joker else 1),
    }


def warmup_realtime_kernels(device: Optional[torch.device] = None) -> None:
    """Pre-compilează kernelurile 1-pas pe GPU pentru ca apelul live incremental să ruleze sub 0.35s."""
    dev = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if dev.type != "cuda":
        return
    for mode in ("649", "540", "joker"):
        N, r, k, jm = GAME_CONFIGS[mode]
        topo = SimplicialTopology(N=N, r_draw=r, k_ticket=k, device=dev, joker_m=jm)
        st = init_state(topo)
        ops = forward_operators_from_state(st, topo)
        _ = evaluate_full_space_fast(topo, ops)
        del topo, st, ops
    gc.collect()
    torch.cuda.empty_cache()
    gc.freeze()


# ============================================================================
# 2. PROBABILITATE EXACTĂ PE EXTRAGEREA D_s ȘI REPERE CAUZALE U, B, R
# ============================================================================

@torch.no_grad()
def eval_subsets_log_weight(
    topo: SimplicialTopology,
    ops: Dict[str, Any],
    comb_0based: torch.Tensor,
    joker_0based: Optional[torch.Tensor] = None,
    params: PLV3Params = DEFAULT_PARAMS,
    face_lookup: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Calculează exact ln W(σ) (sau ln W(σ, j) la Joker) în float64 pentru un lot mic de k-submulțimi."""
    dev = topo.device
    k = topo.k_ticket
    comb = comb_0based.to(device=dev, dtype=torch.int64)
    K_mat = ops["K_kernel"].to(device=dev, dtype=torch.complex128)
    sg_leaf_w = ops["sg_leaf_w"].to(device=dev, dtype=torch.float64)
    sg_masks = ops["sg_masks"].to(device=dev, dtype=torch.int64)
    lut0 = ops["sg_lut0"].to(device=dev, dtype=torch.float64)
    lut1 = ops["sg_lut1"].to(device=dev, dtype=torch.float64)
    lut2 = ops["sg_lut2"].to(device=dev, dtype=torch.float64)

    K_sub = K_mat[comb.unsqueeze(2), comb.unsqueeze(1)]
    log_det = unrolled_hermitian_cholesky_logdet(K_sub, k)
    if ops.get("Curl3D") is not None:
        Curl3D = ops["Curl3D"].to(device=dev, dtype=torch.float64)
        curl_sum = Curl3D[comb[:, topo.sub_fi], comb[:, topo.sub_fj], comb[:, topo.sub_fk]].sum(dim=1)
    else:
        fl = face_lookup if face_lookup is not None else _build_face_lookup(topo)
        f_idx = fl[comb[:, topo.sub_fi], comb[:, topo.sub_fj], comb[:, topo.sub_fk]]
        fv = ops["face_vort"].to(device=dev, dtype=torch.float64)
        curl_sum = fv[f_idx].sum(dim=1)
    sg_cut = _eval_sg_cut(comb, sg_leaf_w, sg_masks, lut0, lut1, lut2)

    inv_sqrt_faces = 1.0 / math.sqrt(float(max(topo.num_sub_faces, 1)))
    base_lw = log_det - inv_sqrt_faces * curl_sum - (1.0 / float(k)) * sg_cut

    if topo.joker_m is not None and bool(ops["joker_pack"]) and joker_0based is not None:
        jp = ops["joker_pack"]
        j_idx = joker_0based.to(device=dev, dtype=torch.int64)
        log_rho = jp["log_rho_joint"].to(device=dev, dtype=torch.float64)  # [45, 20]
        theta_j = jp["theta_joker"].to(device=dev, dtype=torch.float64)    # [20]
        rows_ar = torch.arange(comb.shape[0], device=dev)
        joint_all = log_rho[comb].mean(dim=1)                              # [M, 20]
        joint_sel = joint_all[rows_ar, j_idx]                              # [M]
        if jp.get("Theta3D") is not None:
            Theta3D = jp["Theta3D"].to(device=dev, dtype=torch.float64)
            theta_sum = Theta3D[comb[:, topo.sub_fi], comb[:, topo.sub_fj], comb[:, topo.sub_fk]].sum(dim=1)
        else:
            fl = face_lookup if face_lookup is not None else _build_face_lookup(topo)
            f_idx = fl[comb[:, topo.sub_fi], comb[:, topo.sub_fj], comb[:, topo.sub_fk]]
            tf = jp["theta_faces"].to(device=dev, dtype=torch.float64)
            theta_sum = tf[f_idx].sum(dim=1)
        phase_diff = theta_j[j_idx] - (2.0 * math.pi) * theta_sum
        cs_pen = params.lambda_cs * (1.0 - torch.cos(phase_diff))
        return base_lw + joint_sel - cs_pen

    return base_lw


def exact_draw_log_prob(
    mode: str,
    topo: SimplicialTopology,
    ops: Dict[str, Any],
    log_Z: float,
    draw_balls_1based: Sequence[int],
    draw_joker_1based: Optional[int] = None,
    params: PLV3Params = DEFAULT_PARAMS,
    face_lookup: Optional[torch.Tensor] = None,
) -> float:
    """Calculează exact ln P_s(D) pe spațiul extragerilor (∑_D P_s(D) = 1 la precizie mașină):
      - 649 (r=6, k=6): ln W(D) - ln Z_s;
      - 540 (r=6, k=5): ln( (1/35) ∑_{σ⊂D, |σ|=5} P_s^(5)(σ) ) = LSE_{σ⊂D}(ln W(σ) - ln Z_s) - ln 35;
      - joker (5/45 + 1/20): ln W(σ_D, j_D) - ln Z_s pe 24.435.180 stări.
    """
    balls0 = sorted(int(x) - 1 for x in draw_balls_1based)
    if mode == "649":
        comb = torch.tensor([balls0], dtype=torch.int64, device=topo.device)
        lw = float(eval_subsets_log_weight(topo, ops, comb, None, params, face_lookup)[0].item())
        return lw - log_Z
    if mode == "540":
        subs = [[balls0[i] for i in idx5] for idx5 in COMB6_5]
        comb = torch.tensor(subs, dtype=torch.int64, device=topo.device)
        lws = eval_subsets_log_weight(topo, ops, comb, None, params, face_lookup).detach().cpu().numpy() - log_Z
        m = float(np.max(lws))
        return m + math.log(float(np.sum(np.exp(lws - m)))) - math.log(float(topo.N - topo.k_ticket))
    if mode == "joker":
        assert draw_joker_1based is not None
        comb = torch.tensor([balls0], dtype=torch.int64, device=topo.device)
        jok = torch.tensor([int(draw_joker_1based) - 1], dtype=torch.int64, device=topo.device)
        lw = float(eval_subsets_log_weight(topo, ops, comb, jok, params, face_lookup)[0].item())
        return lw - log_Z
    raise ValueError(f"Mod necunoscut: {mode}")


def _cond_poisson_log_z_and_marginals(weights: np.ndarray, r: int) -> Tuple[float, np.ndarray]:
    """Pentru ponderi pozitive w_1..w_N (∑ w_i = 1), calculează exact în O(N·r):
      - ln e_r(w) = ln ∑_{|D|=r} ∏_{i∈D} w_i
      - marginalele exacte de incluziune q_i = P(i ∈ D) = w_i e_{r-1}(w_{-i}) / e_r(w), cu ∑ q_i = r.
    """
    N = int(weights.shape[0])
    u = weights.astype(np.float64) * float(N)
    F = np.zeros((N + 1, r + 1), dtype=np.float64)
    F[0, 0] = 1.0
    for i in range(N):
        F[i + 1, 0] = 1.0
        ui = u[i]
        for m in range(1, min(i + 1, r) + 1):
            F[i + 1, m] = F[i, m] + ui * F[i, m - 1]

    G = np.zeros((N + 1, r + 1), dtype=np.float64)
    G[N, 0] = 1.0
    for i in range(N - 1, -1, -1):
        G[i, 0] = 1.0
        ui = u[i]
        max_m = min(N - i, r)
        for m in range(1, max_m + 1):
            G[i, m] = G[i + 1, m] + ui * G[i + 1, m - 1]

    er_u = float(F[N, r])
    log_er_w = math.log(er_u) - float(r) * math.log(float(N))

    m_idx = np.arange(r)
    e_minus = (F[:N, m_idx] * G[1 : N + 1, (r - 1) - m_idx]).sum(axis=1)
    q = (u * e_minus) / er_u
    return log_er_w, q


def _top_k_1based(weights: np.ndarray, k: int) -> np.ndarray:
    order = np.argsort(-weights, kind="mergesort")[:k]
    return np.sort(order + 1).astype(np.int64)


# ============================================================================
# 3. EVALUARE BATCHING MULTI-PAS (B_steps = 32) PE FIECARE CHUNK COMBINADIC
# ============================================================================

@torch.no_grad()
def evaluate_batch_steps(
    mode: str,
    topo: SimplicialTopology,
    ops_list: List[Dict[str, Any]],
    face_lookup: torch.Tensor,
    params: PLV3Params = DEFAULT_PARAMS,
) -> Dict[str, np.ndarray]:
    """Evaluează simultan B <= 32 pași istorici pe fiecare chunk combinadic unranked în float64."""
    B_actual = len(ops_list)
    assert 1 <= B_actual <= 32
    dev = topo.device
    N, k = topo.N, topo.k_ticket
    has_joker = mode == "joker"

    ops_pad = ops_list if B_actual == 32 else (ops_list + [ops_list[0]] * (32 - B_actual))
    B = 32

    fi, fj, fk = topo.faces[:, 0], topo.faces[:, 1], topo.faces[:, 2]
    K_stack = torch.stack([o["K_kernel"] for o in ops_pad], dim=-1).to(torch.complex128).contiguous()
    K_re = K_stack.real.reshape(N * N, B).contiguous()
    K_im = K_stack.imag.reshape(N * N, B).contiguous()
    K_diag = torch.diagonal(K_stack, dim1=0, dim2=1).real.T.contiguous()
    face_vort = torch.stack([o["Curl3D"][fi, fj, fk] for o in ops_pad], dim=1).to(torch.float64).contiguous()

    sg_leaf_w = torch.stack([o["sg_leaf_w"] for o in ops_pad], dim=1).to(torch.float64).contiguous()
    sg_masks = torch.stack([o["sg_masks"] for o in ops_pad], dim=1).to(torch.int64).contiguous()
    lut0 = torch.stack([o["sg_lut0"] for o in ops_pad], dim=1).to(torch.float64).reshape(-1).contiguous()
    lut1 = torch.stack([o["sg_lut1"] for o in ops_pad], dim=1).to(torch.float64).reshape(-1).contiguous()
    lut2 = torch.stack([o["sg_lut2"] for o in ops_pad], dim=1).to(torch.float64).reshape(-1).contiguous()
    b_off = torch.arange(B, dtype=torch.int64, device=dev).unsqueeze(0)
    b_ar = torch.arange(B, dtype=torch.int64, device=dev)

    if has_joker:
        theta_faces = torch.stack([o["joker_pack"]["Theta3D"][fi, fj, fk] for o in ops_pad], dim=1).to(torch.float64).contiguous()
        log_rho_joint = torch.stack([o["joker_pack"]["log_rho_joint"] for o in ops_pad], dim=1).to(torch.float64).contiguous()  # [45, 32, 20]
        theta_joker = torch.stack([o["joker_pack"]["theta_joker"] for o in ops_pad], dim=0).to(torch.float64).contiguous()      # [32, 20]
        chunk_sz = 32_768
    else:
        chunk_sz = 131_072

    run_max = torch.full((B,), float("-inf"), dtype=torch.float64, device=dev)
    run_sum_z = torch.zeros((B,), dtype=torch.float64, device=dev)
    run_marg_main = torch.zeros((N, B), dtype=torch.float64, device=dev)
    run_marg_joker = torch.zeros((B, topo.joker_m or 1), dtype=torch.float64, device=dev)

    best_val = torch.full((B,), float("-inf"), dtype=torch.float64, device=dev)
    best_rank = torch.zeros((B,), dtype=torch.int64, device=dev)
    best_jok = torch.zeros((B,), dtype=torch.int64, device=dev)

    for start in range(0, topo.total_base_states, chunk_sz):
        end = min(start + chunk_sz, topo.total_base_states)
        comb = topo.unrank_chunk(start, end)
        m_len = comb.shape[0]
        if m_len < chunk_sz:
            comb_p = torch.cat([comb, comb[:1].expand(chunk_sz - m_len, -1)], dim=0)
        else:
            comb_p = comb
        sub_f = face_lookup[comb_p[:, topo.sub_fi], comb_p[:, topo.sub_fj], comb_p[:, topo.sub_fk]]

        if mode == "649":
            lw = _eval_chunk_649_b32(
                comb_p, sub_f, K_re, K_im, K_diag, face_vort, sg_leaf_w, sg_masks, lut0, lut1, lut2, b_off
            )[:m_len]
        elif mode == "540":
            lw = _eval_chunk_540_b32(
                comb_p, sub_f, K_re, K_im, K_diag, face_vort, sg_leaf_w, sg_masks, lut0, lut1, lut2, b_off
            )[:m_len]
        else:
            lw_full_p, j_max_val_p, j_max_idx_p = _eval_chunk_joker_b32(
                comb_p, sub_f, K_re, K_im, K_diag, face_vort, theta_faces, log_rho_joint, theta_joker,
                sg_leaf_w, sg_masks, lut0, lut1, lut2, b_off, params.lambda_cs,
            )
            lw_full = lw_full_p[:m_len]
            j_max_val = j_max_val_p[:m_len]
            j_max_idx = j_max_idx_p[:m_len]

            c_max, c_arg = j_max_val.max(dim=0)
            c_jok = j_max_idx[c_arg, b_ar]
            better = c_max > best_val
            best_val = torch.where(better, c_max, best_val)
            best_rank = torch.where(better, start + c_arg, best_rank)
            best_jok = torch.where(better, c_jok, best_jok)

            m_new = torch.maximum(run_max, c_max)
            alpha_old = torch.where(run_max > float("-inf"), torch.exp(run_max - m_new), torch.zeros_like(m_new))
            w_rel = torch.exp(lw_full - m_new.view(1, B, 1))
            run_sum_z = run_sum_z * alpha_old + w_rel.sum(dim=(0, 2))
            w_main = w_rel.sum(dim=2)
            run_marg_main = run_marg_main * alpha_old.unsqueeze(0)
            for d in range(k):
                run_marg_main.index_add_(0, comb[:, d], w_main)
            run_marg_joker = run_marg_joker * alpha_old.unsqueeze(1) + w_rel.sum(dim=0)
            run_max = m_new
            continue

        c_max, c_arg = lw.max(dim=0)
        better = c_max > best_val
        best_val = torch.where(better, c_max, best_val)
        best_rank = torch.where(better, start + c_arg, best_rank)

        m_new = torch.maximum(run_max, c_max)
        alpha_old = torch.where(run_max > float("-inf"), torch.exp(run_max - m_new), torch.zeros_like(m_new))
        w_rel = torch.exp(lw - m_new.unsqueeze(0))
        run_sum_z = run_sum_z * alpha_old + w_rel.sum(dim=0)
        run_marg_main = run_marg_main * alpha_old.unsqueeze(0)
        for d in range(k):
            run_marg_main.index_add_(0, comb[:, d], w_rel)
        run_max = m_new

    log_Z = (run_max + torch.log(run_sum_z))[:B_actual]
    pi_inc = (run_marg_main / run_sum_z.unsqueeze(0)).T[:B_actual]  # [B_actual, N]

    tickets = np.zeros((B_actual, k), dtype=np.int64)
    ranks_cpu = best_rank[:B_actual].detach().cpu().tolist()
    for b_i, rk in enumerate(ranks_cpu):
        c_row = topo.unrank_chunk(int(rk), int(rk) + 1)[0].detach().cpu().numpy()
        tickets[b_i] = c_row + 1

    out: Dict[str, np.ndarray] = {
        "log_Z": log_Z.detach().cpu().numpy(),
        "pi_inclusion": pi_inc.detach().cpu().numpy(),
        "sigma_alpha": tickets,
        "alpha_log_prob": (best_val[:B_actual] - log_Z).detach().cpu().numpy(),
    }
    if has_joker:
        j_prob = (run_marg_joker / run_sum_z.unsqueeze(1))[:B_actual]
        out["joker_prob"] = j_prob.detach().cpu().numpy()
        out["joker_alpha"] = (best_jok[:B_actual].detach().cpu().numpy() + 1).astype(np.int64)
    return out


def verify_b32_kernels_against_core(device: Optional[torch.device] = None) -> Dict[str, Any]:
    """Auto-verificare sintetică (< 1e-13) a kernelurilor B_steps=32 față de pl_v3.core.evaluate_full_space."""
    from pl_v3.verify_q import _synth_universe

    dev = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    summary: Dict[str, Any] = {}
    for mode, seed in (("649", 9101), ("540", 9102), ("joker", 9103)):
        N, r, k, jm = GAME_CONFIGS[mode]
        topo = SimplicialTopology(N=N, r_draw=r, k_ticket=k, device=dev, joker_m=jm)
        oh, offs, joh = _synth_universe(N, r, n_steps=12, seed=seed, device=dev, joker_m=jm)
        slices = extract_step_slices(oh, offs, joh)
        st = advance_steps(init_state(topo), topo, slices[:8])
        ops_list = []
        for s in range(8, 12):
            ops_list.append(forward_operators_from_state(st, topo))
            advance_one_step(st, topo, slices[s][0], slices[s][1])
        fl = _build_face_lookup(topo)
        bat = evaluate_batch_steps(mode, topo, ops_list, fl)
        ref_last = evaluate_full_space_fast(topo, ops_list[-1], face_lookup=fl)

        from pl_v3.core import evaluate_full_space
        core_last = evaluate_full_space(topo, ops_list[-1])

        lz_err = abs(float(bat["log_Z"][-1]) - float(core_last["log_Z"]))
        lz_fast_err = abs(float(ref_last["log_Z"]) - float(core_last["log_Z"]))
        pi_err = float(np.max(np.abs(bat["pi_inclusion"][-1] - core_last["pi_inclusion"].detach().cpu().numpy())))
        ticket_ok = bat["sigma_alpha"][-1].tolist() == core_last["variants"][0]["ticket"]
        if not (lz_err < 1e-12 and lz_fast_err < 1e-12 and pi_err < 1e-12 and ticket_ok):
            raise RuntimeError(f"Eroare aliniere kernel {mode}: lz={lz_err}, pi={pi_err}, ticket={ticket_ok}")
        summary[mode] = {
            "log_Z_err": lz_err,
            "fast_1step_log_Z_err": lz_fast_err,
            "pi_err": pi_err,
            "ticket_match": ticket_ok,
        }
    return summary


# ============================================================================
# 4. HOOK INCREMENTAL REAL-TIME PE CURRENT_LIVE.json & CHECKPOINT .pt
# ============================================================================

def _serialize_state(state: PLV3State) -> Dict[str, Any]:
    cpu = lambda x: None if x is None else x.detach().cpu().clone()
    return {
        "step_idx": int(state.step_idx),
        "U_full": cpu(state.U_full),
        "pair_cooc": cpu(state.pair_cooc),
        "last_step": cpu(state.last_step),
        "ball_count": cpu(state.ball_count),
        "ema_node": cpu(state.ema_node),
        "ema_cooc": cpu(state.ema_cooc),
        "ruelle_hist": cpu(state.ruelle_hist),
        "ruelle_trans": cpu(state.ruelle_trans),
        "joker_ema": cpu(state.joker_ema),
        "joker_hist": cpu(state.joker_hist),
        "joker_ruelle": cpu(state.joker_ruelle),
        "cross_ema0": cpu(state.cross_ema0),
        "cross_ema1": cpu(state.cross_ema1),
    }


def _deserialize_state(d: Dict[str, Any], device: torch.device) -> PLV3State:
    mv = lambda x: None if x is None else x.to(device=device).clone()
    return PLV3State(
        step_idx=int(d["step_idx"]),
        U_full=mv(d["U_full"]),
        pair_cooc=mv(d["pair_cooc"]),
        last_step=mv(d["last_step"]),
        ball_count=mv(d["ball_count"]),
        ema_node=mv(d["ema_node"]),
        ema_cooc=mv(d["ema_cooc"]),
        ruelle_hist=mv(d["ruelle_hist"]),
        ruelle_trans=mv(d["ruelle_trans"]),
        joker_ema=mv(d.get("joker_ema")),
        joker_hist=mv(d.get("joker_hist")),
        joker_ruelle=mv(d.get("joker_ruelle")),
        cross_ema0=mv(d.get("cross_ema0")),
        cross_ema1=mv(d.get("cross_ema1")),
    )


def _serialize_ops_for_settlement(ops: Dict[str, Any], topo: SimplicialTopology) -> Dict[str, Any]:
    cpu = lambda x: None if x is None else x.detach().cpu().clone()
    fi, fj, fk = topo.faces[:, 0], topo.faces[:, 1], topo.faces[:, 2]
    face_vort = ops["Curl3D"][fi, fj, fk].detach().cpu().clone()
    jp_cpu: Dict[str, Any] = {}
    if ops.get("joker_pack"):
        jp = ops["joker_pack"]
        jp_cpu["log_rho_joint"] = cpu(jp["log_rho_joint"])
        jp_cpu["theta_joker"] = cpu(jp["theta_joker"])
        jp_cpu["theta_faces"] = jp["Theta3D"][fi, fj, fk].detach().cpu().clone()
        jp_cpu["s_vn"] = cpu(jp["s_vn"])
    return {
        "K_kernel": cpu(ops["K_kernel"]),
        "face_vort": face_vort,
        "sg_leaf_w": cpu(ops["sg_leaf_w"]),
        "sg_masks": cpu(ops["sg_masks"]),
        "sg_lut0": cpu(ops["sg_lut0"]),
        "sg_lut1": cpu(ops["sg_lut1"]),
        "sg_lut2": cpu(ops["sg_lut2"]),
        "joker_pack": jp_cpu,
    }


def _extract_telemetry(state: PLV3State, ops: Dict[str, Any]) -> Dict[str, Any]:
    U = state.U_full
    I3 = torch.eye(3, dtype=torch.complex128, device=U.device)
    unit_err = float(torch.linalg.matrix_norm(torch.matmul(U.conj().transpose(-1, -2), U) - I3, ord="fro").max().item())
    W_f = ops["W_faces"]
    ym_t = (1.0 - W_f).clamp(min=0.0)
    r_eigs = ops["ruelle_eigs"]
    b_evals = ops["bochner_evals"]
    s_vn = float(ops["joker_pack"]["s_vn"].item()) if ops.get("joker_pack") else None
    return {
        "curl_energy_ratio": float(ops["curl_energy_ratio"]),
        "hodge_inner_err": float(ops["hodge_inner_err"]),
        "wilson_mean": float(W_f.mean().item()),
        "wilson_min": float(W_f.min().item()),
        "wilson_max": float(W_f.max().item()),
        "ym_tension_mean": float(ym_t.mean().item()),
        "su3_unitarity_err": unit_err,
        "bochner_evals_min": float(b_evals.min().item()),
        "bochner_evals_max": float(b_evals.max().item()),
        "ruelle_spectral_radius": float(r_eigs.abs().max().item()),
        "s_vn_joker": s_vn,
        "xyz_3d": ops["xyz_3d"].detach().cpu().tolist(),
        "rho_emp": ops["rho_emp"].detach().cpu().tolist(),
    }


def _prefix_digests(ds: PM.GameDataset, n_steps: int, n_draws: int) -> Tuple[str, str]:
    dates_sha = _sha256_bytes(json.dumps(ds.step_dates[:n_steps]).encode("utf-8"))
    draws_np = ds.draws[:n_draws].detach().cpu().numpy().astype(np.int64)
    buf = draws_np.tobytes()
    if ds.joker is not None:
        buf += ds.joker[:n_draws].detach().cpu().numpy().astype(np.int64).tobytes()
    return dates_sha, _sha256_bytes(buf)


def _raw_jsonl_fingerprint(src_path: Path) -> Tuple[int, str, List[str]]:
    nonblank = [ln for ln in Path(src_path).read_text(encoding="utf-8").splitlines() if ln.strip()]
    raw_sha = _sha256_bytes("\n".join(nonblank).encode("utf-8"))
    return len(nonblank), raw_sha, nonblank


def _settle_draw_records(
    mode: str,
    topo: SimplicialTopology,
    ops_pre: Dict[str, Any],
    log_Z_pre: float,
    variants_pre: List[Dict[str, Any]],
    step_s: int,
    draw_index_start: int,
    dates_slice: Sequence[str],
    keys_slice: Sequence[str],
    draws_slice: Sequence[Sequence[int]],
    jokers_slice: Sequence[Optional[int]],
    params: PLV3Params = DEFAULT_PARAMS,
    face_lookup: Optional[torch.Tensor] = None,
) -> List[Dict[str, Any]]:
    N, r, _, jm = GAME_CONFIGS[mode]
    log_u = -math.log(float(math.comb(N, r) * (jm if jm is not None else 1)))

    t_sets = [set(v["ticket"]) for v in variants_pre]
    union3 = t_sets[0] | t_sets[1] | t_sets[2]
    settled: List[Dict[str, Any]] = []

    for local_i, d_raw in enumerate(draws_slice):
        r_idx = draw_index_start + local_i
        d_balls = [int(x) for x in d_raw]
        d_set = set(d_balls)
        d_jok = int(jokers_slice[local_i]) if jokers_slice[local_i] is not None else None
        lp = exact_draw_log_prob(mode, topo, ops_pre, log_Z_pre, d_balls, d_jok, params, face_lookup)
        ratio_u = math.exp(max(min(lp - log_u, 700.0), -700.0))
        ville_fac = 0.5 + 0.5 * ratio_u

        h_main_a = len(t_sets[0] & d_set)
        h_main_b = len(t_sets[1] & d_set)
        h_main_c = len(t_sets[2] & d_set)
        h_union_main = len(union3 & d_set)

        entry: Dict[str, Any] = {
            "step": int(step_s),
            "draw_index": int(r_idx),
            "draw_date": dates_slice[local_i],
            "draw_key": keys_slice[local_i],
            "numbers": d_balls,
            "joker": d_jok,
            "alpha_ticket": list(variants_pre[0]["ticket"]),
            "beta_ticket": list(variants_pre[1]["ticket"]),
            "gamma_ticket": list(variants_pre[2]["ticket"]),
            "log_prob_plv3": float(lp),
            "log_prob_uniform": float(log_u),
            "ville_factor": float(ville_fac),
            "settled_utc": _utc_now(),
        }
        if mode == "joker":
            ja = int(variants_pre[0]["joker"])
            jb = int(variants_pre[1]["joker"])
            jc = int(variants_pre[2]["joker"])
            hj_a = int(ja == d_jok)
            hj_b = int(jb == d_jok)
            hj_c = int(jc == d_jok)
            entry.update(
                alpha_joker=ja,
                hits_545=h_main_a,
                hits_120=hj_a,
                hits_alpha=h_main_a + hj_a,
                hits_beta=h_main_b + hj_b,
                hits_gamma=h_main_c + hj_c,
                hits_union3=h_union_main + int(d_jok in {ja, jb, jc}),
            )
        else:
            entry.update(
                hits_alpha=h_main_a,
                hits_beta=h_main_b,
                hits_gamma=h_main_c,
                hits_union3=h_union_main,
            )
        settled.append(entry)
    return settled


def _settle_step_draws(
    mode: str,
    topo: SimplicialTopology,
    ops_pre: Dict[str, Any],
    log_Z_pre: float,
    variants_pre: List[Dict[str, Any]],
    ds: PM.GameDataset,
    step_s: int,
    params: PLV3Params = DEFAULT_PARAMS,
    face_lookup: Optional[torch.Tensor] = None,
) -> List[Dict[str, Any]]:
    offs = ds.step_offsets.detach().cpu().tolist()
    a, b = int(offs[step_s]), int(offs[step_s + 1])
    draws_cpu = ds.draws[a:b].detach().cpu().tolist()
    jok_cpu = ds.joker[a:b].detach().cpu().tolist() if ds.joker is not None else [None] * (b - a)
    return _settle_draw_records(
        mode, topo, ops_pre, log_Z_pre, variants_pre,
        step_s, a, ds.dates[a:b], ds.keys[a:b], draws_cpu, jok_cpu, params, face_lookup,
    )


def _save_checkpoint_atomic(ckpt_path: Path, payload: Dict[str, Any], latest_ptr_path: Path) -> None:
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{ckpt_path.stem}_", suffix=".pt", dir=ckpt_path.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        torch.save(payload, tmp_path)
        os.replace(tmp_path, ckpt_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    ptr_data = {
        "mode": payload["mode"],
        "src_key": payload["src_key"],
        "checkpoint_file": ckpt_path.name,
        "step_idx": payload["step_idx"],
        "n_draws": payload["n_draws"],
        "last_date": payload["last_date"],
        "updated_utc": payload["saved_utc"],
    }
    fd2, tmp_json = tempfile.mkstemp(prefix=f".latest_{payload['mode']}_", suffix=".json", dir=ckpt_path.parent)
    with os.fdopen(fd2, "w", encoding="utf-8") as f:
        json.dump(ptr_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_json, latest_ptr_path)


def _candidate_checkpoint_paths(mode: str, cache_dir: Path) -> List[Path]:
    if not cache_dir.is_dir():
        return []
    candidates: List[Path] = []
    latest_ptr = cache_dir / f"latest_{mode}.json"
    if latest_ptr.is_file():
        try:
            meta = json.loads(latest_ptr.read_text(encoding="utf-8"))
            p = cache_dir / str(meta.get("checkpoint_file", ""))
            if p.is_file():
                candidates.append(p)
        except (OSError, ValueError, TypeError):
            pass

    for p in sorted(cache_dir.glob(f"state_{mode}_*.pt"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p not in candidates:
            candidates.append(p)
    return candidates


def _find_best_predecessor_checkpoint(
    mode: str,
    ds: PM.GameDataset,
    cache_dir: Path,
) -> Optional[Dict[str, Any]]:
    candidates = _candidate_checkpoint_paths(mode, cache_dir)
    best_ckpt: Optional[Dict[str, Any]] = None
    for p in candidates:
        try:
            ck = torch.load(p, map_location="cpu", weights_only=False)
        except Exception:
            continue
        if not isinstance(ck, dict) or ck.get("mode") != mode:
            continue
        s_old = int(ck.get("step_idx", -1))
        nd_old = int(ck.get("n_draws", -1))
        if not (0 <= s_old <= ds.n_steps and 0 <= nd_old <= ds.n_draws):
            continue
        if int(ds.step_offsets[s_old].item()) != nd_old:
            continue
        d_sha, dr_sha = _prefix_digests(ds, s_old, nd_old)
        if ck.get("step_dates_sha256") != d_sha or ck.get("draws_prefix_sha256") != dr_sha:
            continue
        if best_ckpt is None or s_old > int(best_ckpt["step_idx"]):
            best_ckpt = ck
    return best_ckpt


def _try_incremental_tail(
    mode: str,
    resolved_path: Path,
    cache_dir: Path,
    device: torch.device,
) -> Optional[Dict[str, Any]]:
    """Fast-path incremental exact pe coada JSONL când prefixul istoric este nemodificat și noile extrageri au dată > last_date.
    Orice abatere (modificare în istoric, extragere în aceeași zi cu ultimul pas, anomalie de validare) returnează None
    și declanșează automat reconstrucția completă prin PM.build_game_dataset.
    """
    candidates = _candidate_checkpoint_paths(mode, cache_dir)
    if not candidates:
        return None

    raw_n, raw_sha_full, nonblank = _raw_jsonl_fingerprint(resolved_path)
    g_spec = PM.spec(mode)
    N, r, _, jm = GAME_CONFIGS[mode]

    for p in candidates:
        try:
            ck = torch.load(p, map_location="cpu", weights_only=False)
        except Exception:
            continue
        if not isinstance(ck, dict) or ck.get("mode") != mode:
            continue
        req_keys = ("raw_nonblank_count", "raw_prefix_sha256", "step_dates_list", "keys_list", "draws_bytes")
        if not all(k_req in ck for k_req in req_keys):
            continue
        old_raw_n = int(ck["raw_nonblank_count"])
        old_s = int(ck.get("step_idx", -1))
        old_nd = int(ck.get("n_draws", -1))
        if not (0 < old_raw_n < raw_n and old_s > 0 and old_nd > 0):
            continue
        if len(ck["step_dates_list"]) != old_s or len(ck["keys_list"]) != old_nd:
            continue
        if len(ck["draws_bytes"]) != old_nd * r * 8:
            continue
        prefix_sha = _sha256_bytes("\n".join(nonblank[:old_raw_n]).encode("utf-8"))
        if prefix_sha != ck["raw_prefix_sha256"]:
            continue

        old_last_date = str(ck.get("last_date") or "")
        old_keys_set = set(ck["keys_list"])
        tail_recs: List[Dict[str, Any]] = []
        seen_tail_keys = set()
        seen_tail_sets = set()
        valid_tail = True
        for ln in nonblank[old_raw_n:]:
            try:
                rec = json.loads(ln)
            except ValueError:
                valid_tail = False
                break
            if not isinstance(rec, dict) or PM.validate_record(g_spec, rec) is not None:
                valid_tail = False
                break
            if str(rec["draw_date"]) <= old_last_date:
                valid_tail = False
                break
            d_key = str(rec["draw_key"])
            nums_sorted = tuple(sorted(int(x) for x in rec["numbers"]))
            jk_val = rec.get("joker")
            sk = (str(rec["draw_date"]), nums_sorted, jk_val)
            if d_key in old_keys_set or d_key in seen_tail_keys or sk in seen_tail_sets:
                valid_tail = False
                break
            seen_tail_keys.add(d_key)
            seen_tail_sets.add(sk)
            tail_recs.append(rec)

        if not valid_tail or not tail_recs:
            continue

        tail_recs.sort(key=lambda rec_x: (rec_x["draw_date"], rec_x["draw_key"]))
        T_tail = len(tail_recs)
        tail_draws_list = [[int(x) for x in sorted(rec_x["numbers"])] for rec_x in tail_recs]
        tail_dates = [str(rec_x["draw_date"]) for rec_x in tail_recs]
        tail_keys = [str(rec_x["draw_key"]) for rec_x in tail_recs]
        tail_jokers_list: List[Optional[int]] = [
            int(rec_x["joker"]) if jm is not None else None for rec_x in tail_recs
        ]

        new_step_dates: List[str] = []
        tail_offsets = [0]
        for idx_t, d_str in enumerate(tail_dates):
            if not new_step_dates or new_step_dates[-1] != d_str:
                if new_step_dates:
                    tail_offsets.append(idx_t)
                new_step_dates.append(d_str)
        tail_offsets.append(T_tail)

        tail_draws_t = torch.tensor(tail_draws_list, dtype=torch.int64)
        tail_oh = torch.zeros((T_tail, N), dtype=torch.float32)
        tail_oh.scatter_(1, tail_draws_t - 1, 1.0)
        tail_oh_d = tail_oh.to(device)
        tail_offs_d = torch.tensor(tail_offsets, dtype=torch.int64, device=device)

        if jm is not None:
            jk_t = torch.tensor([int(x) for x in tail_jokers_list if x is not None], dtype=torch.int64)
            jo = torch.zeros((T_tail, jm), dtype=torch.float32)
            jo.scatter_(1, (jk_t - 1)[:, None], 1.0)
            tail_jo_d: Optional[torch.Tensor] = jo.to(device)
            tail_joker_bytes = jk_t.numpy().astype(np.int64).tobytes()
        else:
            tail_jo_d = None
            tail_joker_bytes = b""

        tail_slices = extract_step_slices(tail_oh_d, tail_offs_d, tail_jo_d)
        step_dates_full = list(ck["step_dates_list"]) + new_step_dates
        keys_full = list(ck["keys_list"]) + tail_keys
        draws_bytes_full = bytes(ck["draws_bytes"]) + tail_draws_t.numpy().astype(np.int64).tobytes()
        joker_bytes_full = bytes(ck.get("joker_bytes", b"")) + tail_joker_bytes

        dates_sha = _sha256_bytes(json.dumps(step_dates_full).encode("utf-8"))
        draws_sha = _sha256_bytes(draws_bytes_full + (joker_bytes_full if jm is not None else b""))

        return {
            "pred_ckpt": ck,
            "raw_n": raw_n,
            "raw_sha_full": raw_sha_full,
            "tail_offsets": tail_offsets,
            "tail_dates": tail_dates,
            "tail_keys": tail_keys,
            "tail_draws_list": tail_draws_list,
            "tail_jokers_list": tail_jokers_list,
            "tail_slices": tail_slices,
            "new_step_dates": new_step_dates,
            "step_dates_full": step_dates_full,
            "keys_full": keys_full,
            "draws_bytes_full": draws_bytes_full,
            "joker_bytes_full": joker_bytes_full,
            "dates_sha": dates_sha,
            "draws_sha": draws_sha,
        }
    return None


def _format_live_response(
    ckpt: Dict[str, Any],
    ckpt_path: Path,
    cache_hit: bool,
    delta_steps: int,
    settled_new: List[Dict[str, Any]],
    elapsed_sec: float,
) -> Dict[str, Any]:
    vram_after = int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else 0
    return {
        "mode": ckpt["mode"],
        "src_key": ckpt["src_key"],
        "checkpoint_path": str(ckpt_path),
        "cache_hit": bool(cache_hit),
        "delta_steps": int(delta_steps),
        "n_steps": int(ckpt["step_idx"]),
        "n_draws": int(ckpt["n_draws"]),
        "last_date": ckpt["last_date"],
        "variants": ckpt["variants"],
        "deterministic_core": ckpt["deterministic_core"],
        "distinct_covered": int(ckpt["distinct_covered"]),
        "log_Z": float(ckpt["log_Z"]),
        "Z_exact": float(ckpt["Z_exact"]),
        "shannon_entropy_nats": float(ckpt["shannon_entropy_nats"]),
        "ground_gap_ln_w": float(ckpt["ground_gap_ln_w"]),
        "pi_inclusion": ckpt["pi_inclusion"],
        "pi_prob": ckpt["pi_prob"],
        "joker_prob": ckpt["joker_prob"],
        "telemetry": ckpt["telemetry"],
        "settled_new_draws": settled_new,
        "settlement_history": ckpt.get("settlement_history", []),
        "elapsed_sec": round(elapsed_sec, 6),
        "vram_allocated_after_bytes": vram_after,
        "positive_claims_allowed": False,
    }


def get_or_advance_live(
    mode: str,
    live_root: Optional[Path] = None,
    deriv_root: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    params: PLV3Params = DEFAULT_PARAMS,
    force_rebuild: bool = False,
) -> Dict[str, Any]:
    """Hook incremental real-time peste CURRENT_LIVE.json și live_key(mode):
      1. Dacă checkpoint-ul pl_v3/cache/state_{mode}_{src_key[:12]}.pt există, returnează instantaneu (< 0.01s).
      2. Dacă au intrat extrageri noi în CURRENT_LIVE.json, decontează automat extragerile noi față de
         distribuția salvată la pasul anterior, avansează DOAR pașii noi ΔS, calculează noile variante (α, β, γ)
         și telemetria, salvează noul checkpoint și eliberează VRAM-ul (gc.collect(); torch.cuda.empty_cache()).
    """
    if mode not in GAME_CONFIGS:
        raise ValueError(f"Mod necunoscut {mode!r}; permise: {sorted(GAME_CONFIGS)}")

    t0 = time.perf_counter()
    c_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR_DEFAULT
    c_dir.mkdir(parents=True, exist_ok=True)

    resolved_path, src_key = _resolve_live_source_and_key(mode, live_root=live_root)
    ckpt_path = c_dir / f"state_{mode}_{src_key[:12]}.pt"
    latest_ptr = c_dir / f"latest_{mode}.json"

    if not force_rebuild and ckpt_path.is_file():
        ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        if isinstance(ck, dict) and ck.get("src_key") == src_key and ck.get("mode") == mode:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            return _format_live_response(ck, ckpt_path, True, 0, [], time.perf_counter() - t0)

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ds = None
    inc_pack = None
    topo = None
    fl = None
    state = None
    ops_term = None
    ev_term = None
    settled_new: List[Dict[str, Any]] = []
    prior_history: List[Dict[str, Any]] = []
    try:
        N, r, k, jm = GAME_CONFIGS[mode]
        topo = SimplicialTopology(N=N, r_draw=r, k_ticket=k, device=dev, joker_m=jm)
        fl = _build_face_lookup(topo)

        if not force_rebuild:
            inc_pack = _try_incremental_tail(mode, resolved_path, c_dir, dev)

        if inc_pack is not None:
            pred_ckpt = inc_pack["pred_ckpt"]
            s_start = int(pred_ckpt["step_idx"])
            old_nd = int(pred_ckpt["n_draws"])
            tail_slices = inc_pack["tail_slices"]
            tail_offs = inc_pack["tail_offsets"]
            delta_steps = len(tail_slices)
            S_target = s_start + delta_steps
            n_draws_total = old_nd + len(inc_pack["tail_draws_list"])
            state = _deserialize_state(pred_ckpt["state"], dev)
            prior_history = list(pred_ckpt.get("settlement_history", []))

            for local_s in range(delta_steps):
                s_abs = s_start + local_s
                if local_s == 0 and "settlement_ops" in pred_ckpt:
                    ops_s = pred_ckpt["settlement_ops"]
                    lz_s = float(pred_ckpt["log_Z"])
                    vars_s = pred_ckpt["variants"]
                else:
                    ops_s = forward_operators_from_state(state, topo, params)
                    ev_s = evaluate_full_space_fast(topo, ops_s, params, face_lookup=fl)
                    lz_s = float(ev_s["log_Z"])
                    vars_s = ev_s["variants"]
                a_t, b_t = tail_offs[local_s], tail_offs[local_s + 1]
                settled_new.extend(
                    _settle_draw_records(
                        mode, topo, ops_s, lz_s, vars_s,
                        s_abs, old_nd + a_t,
                        inc_pack["tail_dates"][a_t:b_t],
                        inc_pack["tail_keys"][a_t:b_t],
                        inc_pack["tail_draws_list"][a_t:b_t],
                        inc_pack["tail_jokers_list"][a_t:b_t],
                        params, fl,
                    )
                )
                advance_one_step(state, topo, tail_slices[local_s][0], tail_slices[local_s][1], params)

            raw_n = int(inc_pack["raw_n"])
            raw_sha = str(inc_pack["raw_sha_full"])
            step_dates_full = inc_pack["step_dates_full"]
            keys_full = inc_pack["keys_full"]
            draws_bytes_full = inc_pack["draws_bytes_full"]
            joker_bytes_full = inc_pack["joker_bytes_full"]
            dates_sha = str(inc_pack["dates_sha"])
            draws_sha = str(inc_pack["draws_sha"])
        else:
            ds = PM.build_game_dataset(
                mode,
                "live",
                device=dev,
                live_root=Path(live_root) if live_root is not None else PM.LIVE,
                deriv_root=Path(deriv_root) if deriv_root is not None else PM.DERIV,
            )
            slices = extract_step_slices(ds.onehot, ds.step_offsets, ds.joker_onehot)
            S_target = ds.n_steps
            n_draws_total = ds.n_draws
            pred_ckpt = None if force_rebuild else _find_best_predecessor_checkpoint(mode, ds, c_dir)

            if pred_ckpt is not None:
                s_start = int(pred_ckpt["step_idx"])
                delta_steps = S_target - s_start
                state = _deserialize_state(pred_ckpt["state"], dev)
                prior_history = list(pred_ckpt.get("settlement_history", []))

                for s in range(s_start, S_target):
                    if s == s_start and "settlement_ops" in pred_ckpt:
                        ops_s = pred_ckpt["settlement_ops"]
                        lz_s = float(pred_ckpt["log_Z"])
                        vars_s = pred_ckpt["variants"]
                    else:
                        ops_s = forward_operators_from_state(state, topo, params)
                        ev_s = evaluate_full_space_fast(topo, ops_s, params, face_lookup=fl)
                        lz_s = float(ev_s["log_Z"])
                        vars_s = ev_s["variants"]
                    settled_new.extend(_settle_step_draws(mode, topo, ops_s, lz_s, vars_s, ds, s, params, fl))
                    advance_one_step(state, topo, slices[s][0], slices[s][1], params)
            else:
                delta_steps = S_target
                state = advance_steps(init_state(topo), topo, slices, params)

            raw_n, raw_sha, _ = _raw_jsonl_fingerprint(resolved_path)
            step_dates_full = list(ds.step_dates)
            keys_full = list(ds.keys)
            draws_bytes_full = ds.draws.detach().cpu().numpy().astype(np.int64).tobytes()
            joker_bytes_full = (
                ds.joker.detach().cpu().numpy().astype(np.int64).tobytes() if ds.joker is not None else b""
            )
            dates_sha, draws_sha = _prefix_digests(ds, S_target, ds.n_draws)

        ops_term = forward_operators_from_state(state, topo, params)
        ev_term = evaluate_full_space_fast(topo, ops_term, params, face_lookup=fl)
        telemetry = _extract_telemetry(state, ops_term)

        payload: Dict[str, Any] = {
            "protocol": "PLV3-P1",
            "mode": mode,
            "src_key": src_key,
            "step_idx": int(S_target),
            "n_draws": int(n_draws_total),
            "last_date": step_dates_full[-1] if step_dates_full else None,
            "step_dates_sha256": dates_sha,
            "draws_prefix_sha256": draws_sha,
            "raw_nonblank_count": int(raw_n),
            "raw_prefix_sha256": raw_sha,
            "step_dates_list": step_dates_full,
            "keys_list": keys_full,
            "draws_bytes": draws_bytes_full,
            "joker_bytes": joker_bytes_full,
            "state": _serialize_state(state),
            "settlement_ops": _serialize_ops_for_settlement(ops_term, topo),
            "log_Z": float(ev_term["log_Z"]),
            "Z_exact": float(ev_term["Z_exact"]),
            "shannon_entropy_nats": float(ev_term["shannon_entropy_nats"]),
            "ground_gap_ln_w": float(ev_term["ground_gap_ln_w"]),
            "pi_inclusion": ev_term["pi_inclusion"].detach().cpu().tolist(),
            "pi_prob": ev_term["pi_prob"].detach().cpu().tolist(),
            "joker_prob": ev_term["joker_prob"].detach().cpu().tolist() if ev_term["joker_prob"] is not None else None,
            "variants": ev_term["variants"],
            "deterministic_core": ev_term["deterministic_core"],
            "distinct_covered": int(ev_term["distinct_covered"]),
            "telemetry": telemetry,
            "settlement_history": prior_history + settled_new,
            "saved_utc": _utc_now(),
            "positive_claims_allowed": False,
        }
        _save_checkpoint_atomic(ckpt_path, payload, latest_ptr)
    finally:
        del ds, inc_pack, topo, fl, state, ops_term, ev_term
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return _format_live_response(payload, ckpt_path, False, delta_steps, settled_new, time.perf_counter() - t0)


# ============================================================================
# 5. WALK-FORWARD INTEGRAL (s = 100 .. S-1) ȘI PORȚILE G1–G6
# ============================================================================

def _summarize_window(
    step_mask: np.ndarray,
    draw_mask: np.ndarray,
    expected_hits_u: float,
    hits_plv3: np.ndarray,
    hits_b: np.ndarray,
    hits_r: np.ndarray,
    log_step_plv3: np.ndarray,
    log_step_u: np.ndarray,
    log_step_b: np.ndarray,
    log_step_r: np.ndarray,
    brier_draw_plv3: np.ndarray,
    brier_draw_u: np.ndarray,
    brier_draw_b: np.ndarray,
    brier_draw_r: np.ndarray,
) -> Dict[str, Any]:
    n_steps_w = int(step_mask.sum())
    n_draws_w = int(draw_mask.sum())
    h_pl = int(hits_plv3[draw_mask].sum())
    h_b = int(hits_b[draw_mask].sum())
    h_r = int(hits_r[draw_mask].sum())
    mean_h_pl = (float(h_pl) / float(n_draws_w)) if n_draws_w > 0 else 0.0
    return {
        "n_steps": n_steps_w,
        "n_draws": n_draws_w,
        "hits_PLV3": h_pl,
        "hits_B": h_b,
        "hits_R": h_r,
        "mean_hits_PLV3": mean_h_pl,
        "expected_mean_hits_U": expected_hits_u,
        "excess_hits_vs_U": mean_h_pl - expected_hits_u,
        "log_score_PLV3": float(log_step_plv3[step_mask].sum()),
        "log_score_U": float(log_step_u[step_mask].sum()),
        "log_score_B": float(log_step_b[step_mask].sum()),
        "log_score_R": float(log_step_r[step_mask].sum()),
        "brier_PLV3": float(brier_draw_plv3[draw_mask].sum()),
        "brier_U": float(brier_draw_u[draw_mask].sum()),
        "brier_B": float(brier_draw_b[draw_mask].sum()),
        "brier_R": float(brier_draw_r[draw_mask].sum()),
    }


def run_walkforward(
    mode: str,
    b_steps: int = B_STEPS_DEFAULT,
    warmup: int = WARMUP_STEPS,
    out_dir: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    save_live_checkpoint: bool = True,
    params: PLV3Params = DEFAULT_PARAMS,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Rulează walk-forward integral (fără sub-eșantionare) pe s = 100 .. ds.n_steps - 1 pentru mode."""
    if mode not in GAME_CONFIGS:
        raise ValueError(f"Mod necunoscut: {mode}")
    if b_steps != 32:
        raise ValueError("Protocolul impune batching exact B_steps = 32.")

    t_start = time.perf_counter()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    resolved_path, src_key = _resolve_live_source_and_key(mode)
    ds = PM.build_game_dataset(mode, "live", device=dev)
    N, r, k, jm = GAME_CONFIGS[mode]
    has_joker = jm is not None
    topo = SimplicialTopology(N=N, r_draw=r, k_ticket=k, device=dev, joker_m=jm)
    fl = _build_face_lookup(topo)

    slices = extract_step_slices(ds.onehot, ds.step_offsets, ds.joker_onehot)
    S_total = ds.n_steps
    if S_total <= warmup:
        raise RuntimeError(f"Arhivă prea scurtă ({S_total} <= {warmup}) pentru {mode}.")

    eval_steps = np.arange(warmup, S_total, dtype=np.int64)
    K_eval = int(eval_steps.shape[0])

    offs_np = ds.step_offsets.detach().cpu().numpy().astype(np.int64)
    oh_np = ds.onehot.detach().cpu().numpy().astype(np.float64)
    draws_np = ds.draws.detach().cpu().numpy().astype(np.int64)
    jok_np = ds.joker.detach().cpu().numpy().astype(np.int64) if has_joker else None
    joh_np = ds.joker_onehot.detach().cpu().numpy().astype(np.float64) if has_joker else None

    # Pre-calculăm strict cauzal contoarele reperelor B și R pe toți pașii 0..S_total-1
    decay = 2.0 ** (-1.0 / EW_HALF_LIFE)
    ew_main = np.zeros(N, dtype=np.float64)
    cnt_cum_main = np.zeros(N, dtype=np.float64)
    ew_jok = np.zeros(jm or 1, dtype=np.float64)
    cnt_cum_jok = np.zeros(jm or 1, dtype=np.float64)

    base_w_B = np.zeros((K_eval, N), dtype=np.float64)
    base_w_R = np.zeros((K_eval, N), dtype=np.float64)
    base_jw_B = np.zeros((K_eval, jm or 1), dtype=np.float64)
    base_jw_R = np.zeros((K_eval, jm or 1), dtype=np.float64)

    for s in range(S_total):
        a, b = int(offs_np[s]), int(offs_np[s + 1])
        if s >= warmup:
            idx_e = s - warmup
            base_w_B[idx_e] = (cnt_cum_main + 1.0) / np.sum(cnt_cum_main + 1.0)
            base_w_R[idx_e] = (ew_main + 0.5) / np.sum(ew_main + 0.5)
            if has_joker:
                base_jw_B[idx_e] = (cnt_cum_jok + 1.0) / np.sum(cnt_cum_jok + 1.0)
                base_jw_R[idx_e] = (ew_jok + 0.5) / np.sum(ew_jok + 0.5)
        step_sum = oh_np[a:b].sum(axis=0)
        cnt_cum_main += step_sum
        ew_main = ew_main * decay + step_sum
        if has_joker and joh_np is not None:
            j_sum = joh_np[a:b].sum(axis=0)
            cnt_cum_jok += j_sum
            ew_jok = ew_jok * decay + j_sum

    # Warmup PL-V3 pe s = 0 .. warmup - 1
    state = advance_steps(init_state(topo), topo, slices[:warmup], params)

    log_Z_arr = np.zeros(K_eval, dtype=np.float64)
    pi_inc_arr = np.zeros((K_eval, N), dtype=np.float64)
    sigma_alpha_arr = np.zeros((K_eval, k), dtype=np.int64)
    alpha_lp_arr = np.zeros(K_eval, dtype=np.float64)
    joker_prob_arr = np.zeros((K_eval, jm), dtype=np.float64) if has_joker else None
    joker_alpha_arr = np.zeros(K_eval, dtype=np.int64) if has_joker else None

    # Predicții per extragere-țintă r ∈ [offs[100], n_draws)
    first_draw = int(offs_np[warmup])
    n_target_draws = int(ds.n_draws - first_draw)
    target_step_arr = np.zeros(n_target_draws, dtype=np.int64)
    log_p_draw_plv3 = np.zeros(n_target_draws, dtype=np.float64)
    log_p_draw_u = np.zeros(n_target_draws, dtype=np.float64)
    log_p_draw_b = np.zeros(n_target_draws, dtype=np.float64)
    log_p_draw_r = np.zeros(n_target_draws, dtype=np.float64)

    brier_draw_plv3 = np.zeros(n_target_draws, dtype=np.float64)
    brier_draw_u = np.zeros(n_target_draws, dtype=np.float64)
    brier_draw_b = np.zeros(n_target_draws, dtype=np.float64)
    brier_draw_r = np.zeros(n_target_draws, dtype=np.float64)

    hits_draw_plv3 = np.zeros(n_target_draws, dtype=np.int64)
    hits_draw_b = np.zeros(n_target_draws, dtype=np.int64)
    hits_draw_r = np.zeros(n_target_draws, dtype=np.int64)

    hits_545_plv3 = np.zeros(n_target_draws, dtype=np.int64) if has_joker else None
    hits_120_plv3 = np.zeros(n_target_draws, dtype=np.int64) if has_joker else None
    hits_545_b = np.zeros(n_target_draws, dtype=np.int64) if has_joker else None
    hits_120_b = np.zeros(n_target_draws, dtype=np.int64) if has_joker else None
    hits_545_r = np.zeros(n_target_draws, dtype=np.int64) if has_joker else None
    hits_120_r = np.zeros(n_target_draws, dtype=np.int64) if has_joker else None

    log_p_step_plv3 = np.zeros(K_eval, dtype=np.float64)
    log_p_step_u = np.zeros(K_eval, dtype=np.float64)
    log_p_step_b = np.zeros(K_eval, dtype=np.float64)
    log_p_step_r = np.zeros(K_eval, dtype=np.float64)
    e_factor_step = np.zeros(K_eval, dtype=np.float64)

    log_u_const = -math.log(float(math.comb(N, r) * (jm if jm is not None else 1)))
    q_u_main = np.full(N, float(r) / float(N), dtype=np.float64)
    q_u_jok = np.full(jm or 1, 1.0 / float(jm or 1), dtype=np.float64)

    t_o14 = 0.0
    t_o5 = 0.0
    draw_cursor = 0
    num_batches = (K_eval + b_steps - 1) // b_steps

    for batch_idx, e_start in enumerate(range(0, K_eval, b_steps)):
        e_end = min(e_start + b_steps, K_eval)
        B_cur = e_end - e_start

        t1 = time.perf_counter()
        ops_batch: List[Dict[str, Any]] = []
        for idx_e in range(e_start, e_end):
            s = warmup + idx_e
            ops_batch.append(forward_operators_from_state(state, topo, params))
            advance_one_step(state, topo, slices[s][0], slices[s][1], params)
        if dev.type == "cuda":
            torch.cuda.synchronize()
        t_o14 += time.perf_counter() - t1

        t2 = time.perf_counter()
        bat_out = evaluate_batch_steps(mode, topo, ops_batch, fl, params)
        if dev.type == "cuda":
            torch.cuda.synchronize()
        t_o5 += time.perf_counter() - t2

        log_Z_arr[e_start:e_end] = bat_out["log_Z"]
        pi_inc_arr[e_start:e_end] = bat_out["pi_inclusion"]
        sigma_alpha_arr[e_start:e_end] = bat_out["sigma_alpha"]
        alpha_lp_arr[e_start:e_end] = bat_out["alpha_log_prob"]
        if has_joker and joker_prob_arr is not None and joker_alpha_arr is not None:
            joker_prob_arr[e_start:e_end] = bat_out["joker_prob"]
            joker_alpha_arr[e_start:e_end] = bat_out["joker_alpha"]

        for local_b in range(B_cur):
            idx_e = e_start + local_b
            s = warmup + idx_e
            ops_s = ops_batch[local_b]
            lz_s = float(bat_out["log_Z"][local_b])
            pi_s = bat_out["pi_inclusion"][local_b]
            t_alpha = set(int(x) for x in bat_out["sigma_alpha"][local_b].tolist())

            if mode == "540":
                q_pl_main = (1.0 + float(N - k - 1) * pi_s) / float(N - k)
            else:
                q_pl_main = pi_s

            wB_s = base_w_B[idx_e]
            wR_s = base_w_R[idx_e]
            log_er_B, q_B_main = _cond_poisson_log_z_and_marginals(wB_s, r)
            log_er_R, q_R_main = _cond_poisson_log_z_and_marginals(wR_s, r)
            t_B = set(int(x) for x in _top_k_1based(wB_s, k).tolist())
            t_R = set(int(x) for x in _top_k_1based(wR_s, k).tolist())

            if has_joker and joker_prob_arr is not None and joker_alpha_arr is not None:
                q_pl_j = joker_prob_arr[idx_e]
                j_alpha = int(joker_alpha_arr[idx_e])
                jwB_s = base_jw_B[idx_e]
                jwR_s = base_jw_R[idx_e]
                j_B = int(_top_k_1based(jwB_s, 1)[0])
                j_R = int(_top_k_1based(jwR_s, 1)[0])

            a_dr, b_dr = int(offs_np[s]), int(offs_np[s + 1])
            ratios_step: List[float] = []
            for r_idx in range(a_dr, b_dr):
                d_balls = [int(x) for x in draws_np[r_idx].tolist()]
                d_set = set(d_balls)
                y_main = oh_np[r_idx]
                d_jok = int(jok_np[r_idx]) if (has_joker and jok_np is not None) else None

                lp_pl = exact_draw_log_prob(mode, topo, ops_s, lz_s, d_balls, d_jok, params)
                lp_u = log_u_const
                balls0 = [b_num - 1 for b_num in d_balls]
                lp_b = float(np.sum(np.log(wB_s[balls0])) - log_er_B)
                lp_r = float(np.sum(np.log(wR_s[balls0])) - log_er_R)

                br_pl = float(np.sum((q_pl_main - y_main) ** 2))
                br_u = float(np.sum((q_u_main - y_main) ** 2))
                br_b = float(np.sum((q_B_main - y_main) ** 2))
                br_r = float(np.sum((q_R_main - y_main) ** 2))

                hm_pl = len(t_alpha & d_set)
                hm_b = len(t_B & d_set)
                hm_r = len(t_R & d_set)

                if has_joker and joh_np is not None and d_jok is not None:
                    yj = joh_np[r_idx]
                    lp_b += float(math.log(jwB_s[d_jok - 1]))
                    lp_r += float(math.log(jwR_s[d_jok - 1]))
                    br_pl += float(np.sum((q_pl_j - yj) ** 2))
                    br_u += float(np.sum((q_u_jok - yj) ** 2))
                    br_b += float(np.sum((jwB_s - yj) ** 2))
                    br_r += float(np.sum((jwR_s - yj) ** 2))
                    hj_pl = int(j_alpha == d_jok)
                    hj_b = int(j_B == d_jok)
                    hj_r = int(j_R == d_jok)
                    assert hits_545_plv3 is not None and hits_120_plv3 is not None
                    assert hits_545_b is not None and hits_120_b is not None
                    assert hits_545_r is not None and hits_120_r is not None
                    hits_545_plv3[draw_cursor] = hm_pl
                    hits_120_plv3[draw_cursor] = hj_pl
                    hits_545_b[draw_cursor] = hm_b
                    hits_120_b[draw_cursor] = hj_b
                    hits_545_r[draw_cursor] = hm_r
                    hits_120_r[draw_cursor] = hj_r
                    h_tot_pl = hm_pl + hj_pl
                    h_tot_b = hm_b + hj_b
                    h_tot_r = hm_r + hj_r
                else:
                    h_tot_pl = hm_pl
                    h_tot_b = hm_b
                    h_tot_r = hm_r

                target_step_arr[draw_cursor] = s
                log_p_draw_plv3[draw_cursor] = lp_pl
                log_p_draw_u[draw_cursor] = lp_u
                log_p_draw_b[draw_cursor] = lp_b
                log_p_draw_r[draw_cursor] = lp_r
                brier_draw_plv3[draw_cursor] = br_pl
                brier_draw_u[draw_cursor] = br_u
                brier_draw_b[draw_cursor] = br_b
                brier_draw_r[draw_cursor] = br_r
                hits_draw_plv3[draw_cursor] = h_tot_pl
                hits_draw_b[draw_cursor] = h_tot_b
                hits_draw_r[draw_cursor] = h_tot_r

                log_p_step_plv3[idx_e] += lp_pl
                log_p_step_u[idx_e] += lp_u
                log_p_step_b[idx_e] += lp_b
                log_p_step_r[idx_e] += lp_r
                ratios_step.append(math.exp(max(min(lp_pl - lp_u, 700.0), -700.0)))
                draw_cursor += 1

            mean_ratio = float(np.mean(ratios_step))
            e_factor_step[idx_e] = 0.5 + 0.5 * mean_ratio

        del ops_batch
        if verbose and ((batch_idx + 1) % 10 == 0 or (batch_idx + 1) == num_batches):
            cur_l10e = float(np.sum(np.log10(np.maximum(e_factor_step[:e_end], 1e-300))))
            print(
                f"[{mode}] lot {batch_idx + 1}/{num_batches} (pași {e_end}/{K_eval}) | "
                f"O1..O4={t_o14:.1f}s O5={t_o5:.1f}s | log10(E)={cur_l10e:+.5f}",
                flush=True,
            )

    # La finalul buclei, `state` este exact la pasul terminal S = ds.n_steps!
    if save_live_checkpoint:
        c_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR_DEFAULT
        ckpt_path = c_dir / f"state_{mode}_{src_key[:12]}.pt"
        latest_ptr = c_dir / f"latest_{mode}.json"
        ops_term = forward_operators_from_state(state, topo, params)
        ev_term = evaluate_full_space_fast(topo, ops_term, params, face_lookup=fl)
        dates_sha, draws_sha = _prefix_digests(ds, S_total, ds.n_draws)
        raw_n, raw_sha, _ = _raw_jsonl_fingerprint(resolved_path)
        payload = {
            "protocol": "PLV3-P1",
            "mode": mode,
            "src_key": src_key,
            "step_idx": int(S_total),
            "n_draws": int(ds.n_draws),
            "last_date": ds.step_dates[-1] if ds.step_dates else None,
            "step_dates_sha256": dates_sha,
            "draws_prefix_sha256": draws_sha,
            "raw_nonblank_count": int(raw_n),
            "raw_prefix_sha256": raw_sha,
            "step_dates_list": list(ds.step_dates),
            "keys_list": list(ds.keys),
            "draws_bytes": ds.draws.detach().cpu().numpy().astype(np.int64).tobytes(),
            "joker_bytes": ds.joker.detach().cpu().numpy().astype(np.int64).tobytes() if ds.joker is not None else b"",
            "state": _serialize_state(state),
            "settlement_ops": _serialize_ops_for_settlement(ops_term, topo),
            "log_Z": float(ev_term["log_Z"]),
            "Z_exact": float(ev_term["Z_exact"]),
            "shannon_entropy_nats": float(ev_term["shannon_entropy_nats"]),
            "ground_gap_ln_w": float(ev_term["ground_gap_ln_w"]),
            "pi_inclusion": ev_term["pi_inclusion"].detach().cpu().tolist(),
            "pi_prob": ev_term["pi_prob"].detach().cpu().tolist(),
            "joker_prob": ev_term["joker_prob"].detach().cpu().tolist() if ev_term["joker_prob"] is not None else None,
            "variants": ev_term["variants"],
            "deterministic_core": ev_term["deterministic_core"],
            "distinct_covered": int(ev_term["distinct_covered"]),
            "telemetry": _extract_telemetry(state, ops_term),
            "settlement_history": [],
            "saved_utc": _utc_now(),
            "positive_claims_allowed": False,
        }
        _save_checkpoint_atomic(ckpt_path, payload, latest_ptr)
        del ops_term, ev_term

    log10_E_curve = np.cumsum(np.log10(np.maximum(e_factor_step, 1e-300)))
    final_log10_E = float(log10_E_curve[-1])
    final_E_S = float(10.0 ** min(final_log10_E, 300.0))

    if mode == "649":
        expected_u_hits = 36.0 / 49.0
    elif mode == "540":
        expected_u_hits = 5.0 * 6.0 / 40.0  # 0.75
    else:
        expected_u_hits = (25.0 / 45.0) + (1.0 / 20.0)  # 5/45 + 1/20 = 109/180

    half_k = K_eval // 2
    mask_all_s = np.ones(K_eval, dtype=bool)
    mask_h1_s = np.arange(K_eval) < half_k
    mask_h2_s = np.arange(K_eval) >= half_k
    mask_last100_s = np.arange(K_eval) >= max(0, K_eval - 100)

    mid_step_val = int(eval_steps[half_k])
    last100_step_val = int(eval_steps[max(0, K_eval - 100)])
    mask_all_d = np.ones(n_target_draws, dtype=bool)
    mask_h1_d = target_step_arr < mid_step_val
    mask_h2_d = target_step_arr >= mid_step_val
    mask_last100_d = target_step_arr >= last100_step_val

    win_total = _summarize_window(
        mask_all_s, mask_all_d, expected_u_hits,
        hits_draw_plv3, hits_draw_b, hits_draw_r,
        log_p_step_plv3, log_p_step_u, log_p_step_b, log_p_step_r,
        brier_draw_plv3, brier_draw_u, brier_draw_b, brier_draw_r,
    )
    win_h1 = _summarize_window(
        mask_h1_s, mask_h1_d, expected_u_hits,
        hits_draw_plv3, hits_draw_b, hits_draw_r,
        log_p_step_plv3, log_p_step_u, log_p_step_b, log_p_step_r,
        brier_draw_plv3, brier_draw_u, brier_draw_b, brier_draw_r,
    )
    win_h2 = _summarize_window(
        mask_h2_s, mask_h2_d, expected_u_hits,
        hits_draw_plv3, hits_draw_b, hits_draw_r,
        log_p_step_plv3, log_p_step_u, log_p_step_b, log_p_step_r,
        brier_draw_plv3, brier_draw_u, brier_draw_b, brier_draw_r,
    )
    win_last100 = _summarize_window(
        mask_last100_s, mask_last100_d, expected_u_hits,
        hits_draw_plv3, hits_draw_b, hits_draw_r,
        log_p_step_plv3, log_p_step_u, log_p_step_b, log_p_step_r,
        brier_draw_plv3, brier_draw_u, brier_draw_b, brier_draw_r,
    )

    g1_pass = win_total["excess_hits_vs_U"] >= 0.20
    g2_pass = win_total["hits_PLV3"] > max(win_total["hits_B"], win_total["hits_R"])
    g3_pass = win_total["log_score_PLV3"] > max(
        win_total["log_score_U"], win_total["log_score_B"], win_total["log_score_R"]
    )
    g4_pass = win_total["brier_PLV3"] < min(
        win_total["brier_U"], win_total["brier_B"], win_total["brier_R"]
    )
    g5_pass = (
        (win_h1["log_score_PLV3"] > win_h1["log_score_B"])
        and (win_h2["log_score_PLV3"] > win_h2["log_score_B"])
        and (win_last100["log_score_PLV3"] > win_last100["log_score_B"])
    )
    g6_pass = final_log10_E > 0.0  # echivalent exact cu E_S > 1.0

    gates = [
        {
            "id": "G1",
            "rule": "Exces potriviri σ_α peste media hipergeometrică uniformă >= +0.20",
            "pass": bool(g1_pass),
            "value": round(win_total["excess_hits_vs_U"], 6),
            "threshold": 0.20,
        },
        {
            "id": "G2",
            "rule": "Hits(PL-V3) > max(Hits(B), Hits(R))",
            "pass": bool(g2_pass),
            "value": {
                "PLV3": win_total["hits_PLV3"],
                "B": win_total["hits_B"],
                "R": win_total["hits_R"],
            },
        },
        {
            "id": "G3",
            "rule": "LogScore_exact(PL-V3) > max(LogScore(U), LogScore(B), LogScore(R))",
            "pass": bool(g3_pass),
            "value": {
                "PLV3": round(win_total["log_score_PLV3"], 6),
                "U": round(win_total["log_score_U"], 6),
                "B": round(win_total["log_score_B"], 6),
                "R": round(win_total["log_score_R"], 6),
                "diff_vs_U": round(win_total["log_score_PLV3"] - win_total["log_score_U"], 6),
                "diff_vs_B": round(win_total["log_score_PLV3"] - win_total["log_score_B"], 6),
                "diff_vs_R": round(win_total["log_score_PLV3"] - win_total["log_score_R"], 6),
            },
        },
        {
            "id": "G4",
            "rule": "Brier(PL-V3) < min(Brier(U), Brier(B), Brier(R))",
            "pass": bool(g4_pass),
            "value": {
                "PLV3": round(win_total["brier_PLV3"], 6),
                "U": round(win_total["brier_U"], 6),
                "B": round(win_total["brier_B"], 6),
                "R": round(win_total["brier_R"], 6),
            },
        },
        {
            "id": "G5",
            "rule": "LogScore(PL-V3) > LogScore(B) pe ambele jumătăți + ultimii 100 pași",
            "pass": bool(g5_pass),
            "value": {
                "half1_diff_PLV3_minus_B": round(win_h1["log_score_PLV3"] - win_h1["log_score_B"], 6),
                "half2_diff_PLV3_minus_B": round(win_h2["log_score_PLV3"] - win_h2["log_score_B"], 6),
                "last100_diff_PLV3_minus_B": round(win_last100["log_score_PLV3"] - win_last100["log_score_B"], 6),
            },
        },
        {
            "id": "G6",
            "rule": "Martingala defensivă Ville E_S = ∏_{s=100}^{S-1} (0.5 + 0.5 · P_s(D_s)/U(D_s)) > 1.0",
            "pass": bool(g6_pass),
            "value": {
                "E_S": round(final_E_S, 8),
                "log10_E_S": round(final_log10_E, 8),
                "max_log10_E": round(float(np.max(log10_E_curve)), 8),
                "min_log10_E": round(float(np.min(log10_E_curve)), 8),
            },
        },
    ]

    gates_passed = sum(1 for g in gates if g["pass"])
    peak_vram_mib = round(torch.cuda.max_memory_allocated() / (1024.0 ** 2), 2) if torch.cuda.is_available() else 0.0
    total_sec = round(time.perf_counter() - t_start, 3)

    joker_breakdown: Optional[Dict[str, Any]] = None
    if has_joker and hits_545_plv3 is not None and hits_120_plv3 is not None:
        assert hits_545_b is not None and hits_120_b is not None
        assert hits_545_r is not None and hits_120_r is not None
        h5_pl = int(hits_545_plv3.sum())
        h1_pl = int(hits_120_plv3.sum())
        joker_breakdown = {
            "joint_state_space": 24_435_180,
            "main_5_45": {
                "hits_PLV3": h5_pl,
                "hits_B": int(hits_545_b.sum()),
                "hits_R": int(hits_545_r.sum()),
                "mean_hits_PLV3": round(h5_pl / float(n_target_draws), 6),
                "expected_U": round(25.0 / 45.0, 6),
                "excess_vs_U": round(h5_pl / float(n_target_draws) - (25.0 / 45.0), 6),
            },
            "ball_1_20": {
                "hits_PLV3": h1_pl,
                "hits_B": int(hits_120_b.sum()),
                "hits_R": int(hits_120_r.sum()),
                "mean_hits_PLV3": round(h1_pl / float(n_target_draws), 6),
                "expected_U": 0.05,
                "excess_vs_U": round(h1_pl / float(n_target_draws) - 0.05, 6),
            },
        }

    out_d = Path(out_dir) if out_dir is not None else OUT_DIR_DEFAULT
    out_d.mkdir(parents=True, exist_ok=True)
    npz_path = out_d / f"{mode}_walkforward.npz"
    json_path = out_d / f"{mode}_walkforward.json"

    npz_dict: Dict[str, Any] = {
        "steps": eval_steps,
        "step_dates": np.array(ds.step_dates[warmup:], dtype="U10"),
        "log_Z": log_Z_arr,
        "pi_inclusion": pi_inc_arr,
        "sigma_alpha": sigma_alpha_arr,
        "alpha_log_prob": alpha_lp_arr,
        "log_p_step_plv3": log_p_step_plv3,
        "log_p_step_u": log_p_step_u,
        "log_p_step_b": log_p_step_b,
        "log_p_step_r": log_p_step_r,
        "e_factor_step": e_factor_step,
        "log10_E_curve": log10_E_curve,
        "target_step": target_step_arr,
        "log_p_draw_plv3": log_p_draw_plv3,
        "log_p_draw_u": log_p_draw_u,
        "log_p_draw_b": log_p_draw_b,
        "log_p_draw_r": log_p_draw_r,
        "brier_draw_plv3": brier_draw_plv3,
        "brier_draw_u": brier_draw_u,
        "brier_draw_b": brier_draw_b,
        "brier_draw_r": brier_draw_r,
        "hits_draw_plv3": hits_draw_plv3,
        "hits_draw_b": hits_draw_b,
        "hits_draw_r": hits_draw_r,
    }
    if has_joker and joker_prob_arr is not None and joker_alpha_arr is not None:
        npz_dict["joker_prob"] = joker_prob_arr
        npz_dict["joker_alpha"] = joker_alpha_arr
        npz_dict["hits_545_plv3"] = hits_545_plv3
        npz_dict["hits_120_plv3"] = hits_120_plv3
        npz_dict["hits_545_b"] = hits_545_b
        npz_dict["hits_120_b"] = hits_120_b
        npz_dict["hits_545_r"] = hits_545_r
        npz_dict["hits_120_r"] = hits_120_r

    np.savez_compressed(npz_path, **npz_dict)
    npz_sha = _sha256_file(npz_path)

    report = {
        "protocol": "PLV3-P1",
        "protocol_sha256": _sha256_file(HERE / "PROTOCOL_PLV3.md"),
        "core_py_sha256": _sha256_file(HERE / "core.py"),
        "walkforward_py_sha256": _sha256_file(Path(__file__)),
        "mode": mode,
        "game_params": {
            "N": N,
            "r_draw": r,
            "k_ticket": k,
            "joker_m": jm,
            "states_evaluated_per_step": int(math.comb(N, k) * (jm if jm is not None else 1)),
            "draw_space_size": int(math.comb(N, r) * (jm if jm is not None else 1)),
        },
        "source_live": {
            "src_key": src_key,
            "n_draws_total": int(ds.n_draws),
            "n_steps_total": int(S_total),
            "warmup_steps": int(warmup),
            "evaluated_steps": int(K_eval),
            "evaluated_target_draws": int(n_target_draws),
            "first_eval_date": ds.step_dates[warmup],
            "last_eval_date": ds.step_dates[-1],
            "batch_steps": int(b_steps),
            "subsampling_used": False,
        },
        "verdict_gates": f"{gates_passed} / 6",
        "gates_passed": int(gates_passed),
        "gates_total": 6,
        "status": "PLV3_PROMOTED_EXPLORATORY" if gates_passed == 6 else "PLV3_NO_PROMOTION_EXPLORATORY",
        "positive_claims_allowed": False,
        "gates": gates,
        "windows": {
            "total": win_total,
            "half1": win_h1,
            "half2": win_h2,
            "last100": win_last100,
        },
        "joker_breakdown": joker_breakdown,
        "ville_martingale": {
            "E_S": final_E_S,
            "log10_E_S": final_log10_E,
            "max_log10_E": float(np.max(log10_E_curve)),
            "min_log10_E": float(np.min(log10_E_curve)),
        },
        "npz_file": npz_path.name,
        "npz_sha256": npz_sha,
        "timings": {
            "O1_O4_sec": round(t_o14, 3),
            "O5_batch32_sec": round(t_o5, 3),
            "total_sec": total_sec,
            "ms_per_step": round(1000.0 * total_sec / float(K_eval), 3),
        },
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "peak_vram_mib": peak_vram_mib,
        "generated_utc": _utc_now(),
    }
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    del ds, topo, fl, state
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return report


# ============================================================================
# 6. VERIFICARE REGRESIE INCREMENTALĂ (S-3 -> S == RULARE COMPLETĂ < 1e-12)
# ============================================================================

def _write_temp_live_version(
    live_root: Path,
    version_tag: str,
    lines_by_mode: Dict[str, List[str]],
) -> None:
    vdir_rel = f"versiuni/{version_tag}"
    vdir = live_root / vdir_rel
    vdir.mkdir(parents=True, exist_ok=True)
    games_man: Dict[str, Any] = {}
    games_ptr: Dict[str, Any] = {}

    for m, (N_m, r_m, _, _) in GAME_CONFIGS.items():
        lines = lines_by_mode[m]
        p = vdir / f"extrageri_{m}.jsonl"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        f_sha = _sha256_file(p)
        last_obj = json.loads(lines[-1])
        games_man[m] = {
            "file": f"extrageri_{m}.jsonl",
            "draw_size": r_m,
            "records": len(lines),
            "last_date": last_obj["draw_date"],
            "last_key": last_obj["draw_key"],
            "sha256": f_sha,
            "excluded": [],
        }
        games_ptr[m] = {
            "records": len(lines),
            "last_date": last_obj["draw_date"],
            "last_key": last_obj["draw_key"],
            "sha256": f_sha,
        }

    man_bytes = (json.dumps({"games": games_man}, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (vdir / "MANIFEST_LIVE.json").write_bytes(man_bytes)
    man_sha = _sha256_bytes(man_bytes)
    ptr_obj = {
        "updated_utc": _utc_now(),
        "run_id": f"regtest_{version_tag}",
        "database_sha256": man_sha,
        "version_dir": vdir_rel,
        "manifest_sha256": man_sha,
        "games": games_ptr,
    }
    (live_root / "CURRENT_LIVE.json").write_text(json.dumps(ptr_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verify_incremental_regression(
    modes: Sequence[str] = ("649", "540", "joker"),
) -> Dict[str, Any]:
    """Verifică pe arhiva LIVE reală (într-un sandbox temporar read-only față de tu3/date/live):
      1. S-3 -> S prin get_or_advance_live == rulare completă 0 -> S (< 1e-12 pe U_full, K, ln Z, π);
      2. Decontarea automată exactă a extragerilor din pașii S-3, S-2, S-1;
      3. Timpul real-time get_or_advance_live la ΔS = 1 (S-1 -> S) și ΔS = 0 (cache hit) < 0.35 s,
         plus eliberarea VRAM după apel.
    """
    warmup_realtime_kernels()

    raw_lines_full: Dict[str, List[str]] = {}
    cutoff_s3_dates: Dict[str, str] = {}
    cutoff_s1_dates: Dict[str, str] = {}

    for m in modes:
        src_path, _ = PM.resolve_live(m)
        raw_lines_full[m] = [ln for ln in src_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        ds_m = PM.build_game_dataset(m, "live", device="cpu")
        S_m = ds_m.n_steps
        cutoff_s3_dates[m] = ds_m.step_dates[S_m - 3]
        cutoff_s1_dates[m] = ds_m.step_dates[S_m - 1]

    lines_s3: Dict[str, List[str]] = {}
    lines_s1: Dict[str, List[str]] = {}
    for m in modes:
        c3 = cutoff_s3_dates[m]
        c1 = cutoff_s1_dates[m]
        lines_s3[m] = [ln for ln in raw_lines_full[m] if json.loads(ln)["draw_date"] < c3]
        lines_s1[m] = [ln for ln in raw_lines_full[m] if json.loads(ln)["draw_date"] < c1]

    results: Dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="plv3_inc_reg_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        live_root = tmp_root / "live"
        deriv_root = tmp_root / "derivat"
        cache_inc = tmp_root / "cache_inc"
        cache_full = tmp_root / "cache_full"
        cache_rt1 = tmp_root / "cache_rt1"

        # 1. Rulare completă 0 -> S pe fiecare mod
        _write_temp_live_version(live_root, "v_full_ref", raw_lines_full)
        full_refs: Dict[str, Dict[str, Any]] = {}
        full_ckpts: Dict[str, Dict[str, Any]] = {}
        for m in modes:
            res_f = get_or_advance_live(m, live_root=live_root, deriv_root=deriv_root, cache_dir=cache_full, force_rebuild=True)
            full_refs[m] = res_f
            full_ckpts[m] = torch.load(res_f["checkpoint_path"], map_location="cpu", weights_only=False)

        # 2. Checkpoint la S-3, urmat de tranziție CURRENT_LIVE.json -> S (ΔS = 3)
        _write_temp_live_version(live_root, "v_s_minus_3", lines_s3)
        for m in modes:
            _ = get_or_advance_live(m, live_root=live_root, deriv_root=deriv_root, cache_dir=cache_inc, force_rebuild=True)

        _write_temp_live_version(live_root, "v_s_full_after_s3", raw_lines_full)
        inc_s3_res: Dict[str, Dict[str, Any]] = {}
        inc_s3_ckpts: Dict[str, Dict[str, Any]] = {}
        for m in modes:
            r_inc = get_or_advance_live(m, live_root=live_root, deriv_root=deriv_root, cache_dir=cache_inc)
            inc_s3_res[m] = r_inc
            inc_s3_ckpts[m] = torch.load(r_inc["checkpoint_path"], map_location="cpu", weights_only=False)

        # 3. Măsurare latență real-time ΔS = 1 (S-1 -> S) și ΔS = 0 (cache hit)
        _write_temp_live_version(live_root, "v_s_minus_1", lines_s1)
        for m in modes:
            _ = get_or_advance_live(m, live_root=live_root, deriv_root=deriv_root, cache_dir=cache_rt1, force_rebuild=True)

        _write_temp_live_version(live_root, "v_s_full_rt1", raw_lines_full)
        rt1_sec: Dict[str, float] = {}
        hit_sec: Dict[str, float] = {}
        for m in modes:
            r1 = get_or_advance_live(m, live_root=live_root, deriv_root=deriv_root, cache_dir=cache_rt1)
            rt1_sec[m] = float(r1["elapsed_sec"])
            r0 = get_or_advance_live(m, live_root=live_root, deriv_root=deriv_root, cache_dir=cache_rt1)
            assert r0["cache_hit"] is True and r0["delta_steps"] == 0
            hit_sec[m] = float(r0["elapsed_sec"])

        all_pass = True
        for m in modes:
            ck_f = full_ckpts[m]
            ck_i = inc_s3_ckpts[m]
            r_f = full_refs[m]
            r_i = inc_s3_res[m]

            u_err = float((ck_i["state"]["U_full"] - ck_f["state"]["U_full"]).abs().max().item())
            k_err = float((ck_i["settlement_ops"]["K_kernel"] - ck_f["settlement_ops"]["K_kernel"]).abs().max().item())
            lz_err = abs(float(r_i["log_Z"]) - float(r_f["log_Z"]))
            pi_err = float(np.max(np.abs(np.array(r_i["pi_inclusion"]) - np.array(r_f["pi_inclusion"]))))
            jok_err = (
                float(np.max(np.abs(np.array(r_i["joker_prob"]) - np.array(r_f["joker_prob"]))))
                if r_f["joker_prob"] is not None
                else 0.0
            )
            tickets_match = [v["ticket"] for v in r_i["variants"]] == [v["ticket"] for v in r_f["variants"]]
            digests_match = (
                ck_i["step_dates_sha256"] == ck_f["step_dates_sha256"]
                and ck_i["draws_prefix_sha256"] == ck_f["draws_prefix_sha256"]
            )
            delta_ok = int(r_i["delta_steps"]) == 3 and len(r_i["settled_new_draws"]) >= 3
            rt_ok = rt1_sec[m] < 0.35 and hit_sec[m] < 0.35
            err_max = max(u_err, k_err, lz_err, pi_err, jok_err)
            m_pass = (err_max < 1e-12) and tickets_match and digests_match and delta_ok and rt_ok
            all_pass = all_pass and m_pass

            results[m] = {
                "pass": bool(m_pass),
                "delta_steps_tested": int(r_i["delta_steps"]),
                "settled_draws_count": len(r_i["settled_new_draws"]),
                "max_U_full_err": u_err,
                "max_K_kernel_err": k_err,
                "log_Z_err": lz_err,
                "pi_inclusion_err": pi_err,
                "joker_prob_err": jok_err,
                "max_overall_err": err_max,
                "variants_exact_match": bool(tickets_match),
                "realtime_delta1_sec": round(rt1_sec[m], 4),
                "realtime_cache_hit_sec": round(hit_sec[m], 5),
                "vram_after_bytes": int(r_i["vram_allocated_after_bytes"]),
            }

    reg_report = {
        "protocol": "PLV3-P1",
        "pass": bool(all_pass),
        "threshold": 1e-12,
        "realtime_budget_sec": 0.35,
        "modes": results,
        "positive_claims_allowed": False,
        "generated_utc": _utc_now(),
    }
    out_p = OUT_DIR_DEFAULT / "REGRESIE_INCREMENTALA.json"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(reg_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return reg_report


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="PL-V3 Walk-Forward Integral (B_steps=32) & Real-Time Hook.")
    ap.add_argument("--mode", choices=["649", "540", "joker", "all"], default="all")
    ap.add_argument("--only-live", action="store_true", help="Rulează doar get_or_advance_live(mode).")
    ap.add_argument("--only-regression", action="store_true", help="Rulează doar regresia incrementală S-3 -> S.")
    ap.add_argument("--skip-regression", action="store_true", help="Sare peste verificarea regresiei incrementale.")
    args = ap.parse_args(argv)

    modes = ["649", "540", "joker"] if args.mode == "all" else [args.mode]

    if args.only_live:
        warmup_realtime_kernels()
        for m in modes:
            res = get_or_advance_live(m)
            print(
                f"[LIVE {m}] step={res['n_steps']} cache_hit={res['cache_hit']} ΔS={res['delta_steps']} "
                f"sec={res['elapsed_sec']:.4f}s α={res['variants'][0]['ticket']}"
            )
        return 0

    if args.only_regression:
        reg = verify_incremental_regression(modes)
        print(json.dumps(reg, indent=2, ensure_ascii=False))
        return 0 if reg["pass"] else 1

    print("[PL-V3] Verificare aliniere kerneluri B_steps=32 vs core.evaluate_full_space...", flush=True)
    align = verify_b32_kernels_against_core()
    print(f"[PL-V3] Aliniere kerneluri PASS: {json.dumps(align)}", flush=True)

    for m in modes:
        rep = run_walkforward(m, b_steps=32, save_live_checkpoint=True, verbose=True)
        w = rep["windows"]["total"]
        print(
            f"=== [{m.upper()}] Verdict: {rep['verdict_gates']} ({rep['status']}) | "
            f"Hits PLV3={w['hits_PLV3']} B={w['hits_B']} R={w['hits_R']} (exces={w['excess_hits_vs_U']:+.5f}) | "
            f"LogPLV3={w['log_score_PLV3']:.2f} LogU={w['log_score_U']:.2f} LogB={w['log_score_B']:.2f} | "
            f"log10(E_S)={rep['ville_martingale']['log10_E_S']:+.5f} | {rep['timings']['total_sec']}s ===",
            flush=True,
        )

    if not args.skip_regression:
        print("[PL-V3] Verificare regresie incrementală (S-3 -> S == Full < 1e-12) și latență < 0.35s...", flush=True)
        reg = verify_incremental_regression(modes)
        print(f"[PL-V3] Regresie incrementală: pass={reg['pass']} | {json.dumps(reg['modes'])}", flush=True)
        if not reg["pass"]:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
