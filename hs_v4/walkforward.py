"""HS-V4 — Faza 2A: Walk-Forward Integral LIVE RO (s = 100 .. S-1), Ablație pe Canale
(O1, O1+O2, O1+O4, Full HS-V4) și Cache Incremental Verificat SHA-256 în hs_v4/cache/.

Protocol sigilat: hs_v4/PROTOCOL_HSV4.md (hs_v4/SIGILIU_PROTOCOL_HSV4.json).
Surse RO read-only: tu3/parser_multi.py (CURRENT_LIVE.json -> 649, 540, joker, step_offsets)
și hs_v4/meteo_ro.py (load_meteo_features_for_dates).
Calcul clasic exact în float64 pe GPU (CUDA / PyTorch) și CPU; positive_claims_allowed = False.
Zero metrici comerciale/contabile/financiare; zero sub-eșantionare a pașilor istorici.
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
import stat
import sys
import tempfile
import time
from dataclasses import dataclass
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

from hs_v4.core import (  # noqa: E402
    DEFAULT_PARAMS,
    EXPERT_GRID,
    HSV4Params,
    HSV4Space,
    HSV4State,
    _all_k_subsets_of_draw,
    _expert_field_tensors,
    advance_one_step,
    advance_steps,
    compute_prior_weights,
    elementary_symmetric_ek_and_marginals,
    evaluate_portfolio_full_space,
    extract_step_slices,
    forward_operators_from_state,
    gauss_hermite_exact_hs,
    get_cumulative_e_value,
    get_portfolio_weights,
    init_state,
    log_weight_hs_subset,
)
from hs_v4.meteo_ro import (  # noqa: E402
    CACHE_JSONL as METEO_CACHE_JSONL,
    PROVENANCE_JSON as METEO_PROVENANCE_JSON,
    load_meteo_features_for_dates,
)

WARMUP_STEPS: int = 100
EW_HALF_LIFE: float = 26.0
CACHE_DIR_DEFAULT: Path = HERE / "cache"
OUT_DIR_DEFAULT: Path = HERE / "rezultate"

RO_GAME_CONFIGS: Dict[str, Tuple[str, int, int, int, Optional[int]]] = {
    "649": ("Loto 6/49", 49, 6, 6, None),
    "540": ("Loto 5/40", 40, 6, 5, None),
    "joker": ("Joker", 45, 5, 5, 20),
}

# Studiul complet de ablație din PROTOCOL_HSV4.md §3.2:
# (config_key, label, enable_o1, enable_o2, enable_o4)
ABLATION_CONFIGS: Tuple[Tuple[str, str, bool, bool, bool], ...] = (
    ("O1", "O1 pur (Bosonic + Intrinsec)", True, False, False),
    ("O1_O2", "O1+O2 (Mecanic Aero-Bosonic)", True, True, False),
    ("O1_O4", "O1+O4 (Bosonic + Spectral RNG)", True, False, True),
    ("Full_HSV4", "Full HS-V4 (O1+O2+O3+O4)", True, True, True),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def atomic_write_json(path: Path, obj: Any) -> str:
    raw = (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    atomic_write_bytes(path, raw)
    return sha256_bytes(raw)


# ============================================================================
# 1. VERIFICARE INTEGRITATE PRERECHIZITE SESIUNEA 1 (READ-ONLY)
# ============================================================================

def verify_session1_prereqs() -> Dict[str, Any]:
    """Verifică read-only integritatea protocolului 0444, cache-ului meteo 0444 și calificării Q1–Q6."""
    proto_path = HERE / "PROTOCOL_HSV4.md"
    seal_path = HERE / "SIGILIU_PROTOCOL_HSV4.json"
    cal_path = OUT_DIR_DEFAULT / "CALIFICARE_Q.json"
    core_path = HERE / "core.py"

    for p in (proto_path, seal_path, METEO_PROVENANCE_JSON, METEO_CACHE_JSONL):
        if not p.is_file():
            raise RuntimeError(f"Fișier prerechizit absent: {p}")
        mode_bits = stat.S_IMODE(p.stat().st_mode)
        if (mode_bits & 0o222) != 0:
            raise RuntimeError(f"Fișierul sigilat {p} nu este read-only (mode={oct(mode_bits)})!")

    seal_obj = json.loads(seal_path.read_text(encoding="utf-8"))
    proto_sha = sha256_file(proto_path)
    if proto_sha != seal_obj.get("sha256"):
        raise RuntimeError(f"SHA-256 PROTOCOL_HSV4.md invalid: {proto_sha} != {seal_obj.get('sha256')}")
    if seal_obj.get("code_files_present") != [] or seal_obj.get("positive_claims_allowed") is not False:
        raise RuntimeError("SIGILIU_PROTOCOL_HSV4.json invalid!")

    meteo_prov = json.loads(METEO_PROVENANCE_JSON.read_text(encoding="utf-8"))
    meteo_sha = sha256_file(METEO_CACHE_JSONL)
    if meteo_sha != meteo_prov.get("sha256"):
        raise RuntimeError(f"SHA-256 cache meteo invalid: {meteo_sha} != {meteo_prov.get('sha256')}")

    if not cal_path.is_file():
        raise RuntimeError(f"Certificat CALIFICARE_Q.json absent: {cal_path}")
    cal_obj = json.loads(cal_path.read_text(encoding="utf-8"))
    core_sha = sha256_file(core_path)
    if (
        cal_obj.get("status") != "HSV4_QUALIFIED"
        or cal_obj.get("passed") != 6
        or cal_obj.get("total") != 6
        or cal_obj.get("protocol_sha256") != proto_sha
        or cal_obj.get("core_py_sha256") != core_sha
    ):
        raise RuntimeError("CALIFICARE_Q.json nu certifică 6/6 PASS pe hs_v4/core.py curent!")

    return {
        "protocol": seal_obj["protocol"],
        "protocol_sha256": proto_sha,
        "seal_sha256": sha256_file(seal_path),
        "meteo_provenance_sha256": sha256_file(METEO_PROVENANCE_JSON),
        "meteo_cache_sha256": meteo_sha,
        "meteo_total_days": int(meteo_prov["total_days"]),
        "core_py_sha256": core_sha,
        "calificare_q_status": cal_obj["status"],
        "calificare_q_passed": f"{cal_obj['passed']}/{cal_obj['total']}",
    }


# ============================================================================
# 2. REPERE CANONICE CAUZALE U, B, R & DESCOMPUNEREA MASELOR BAYESIENE
# ============================================================================

def cond_poisson_log_z_and_marginals(weights: np.ndarray, r: int) -> Tuple[float, np.ndarray]:
    """Pentru ponderi pozitive w_1..w_N (∑ w_i = 1), calculează exact în float64:
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

    er_u = max(float(F[N, r]), 1e-300)
    log_er_w = math.log(er_u) - float(r) * math.log(float(N))

    m_idx = np.arange(r)
    e_minus = (F[:N, m_idx] * G[1 : N + 1, (r - 1) - m_idx]).sum(axis=1)
    q_inc = (u * e_minus) / er_u
    return log_er_w, q_inc


def top_k_1based(weights: np.ndarray, k: int) -> np.ndarray:
    order = np.argsort(-weights, kind="mergesort")[:k]
    return np.sort(order + 1).astype(np.int64)


def decompose_channel_masses(w_vec: np.ndarray) -> Dict[str, float]:
    """Descompune vectorul celor 8 experți (∑_{m=0}^7 w_m = 1) în masele canalelor:
      w_0  = w[0] (abținere / uniform)
      w_O1 = w[1] + w[2] + w[3] + 0.5 * w[5]
      w_O2 = w[4] + 0.5 * w[5]
      w_O4 = w[6] + w[7]
    (cu w_0 + w_O1 + w_O2 + w_O4 == 1.0 exact, raportând separat și masele pure/cuplate).
    """
    w = np.asarray(w_vec, dtype=np.float64)
    return {
        "w_0": float(w[0]),
        "w_O1": float(w[1] + w[2] + w[3] + 0.5 * w[5]),
        "w_O2": float(w[4] + 0.5 * w[5]),
        "w_O4": float(w[6] + w[7]),
        "w_O1_pure": float(w[1] + w[2] + w[3]),
        "w_O2_pure": float(w[4]),
        "w_O1_O2_coupled": float(w[5]),
    }


# ============================================================================
# 3. EVALUARE EXACTĂ SUB-EXTRAGERE (GH + e_k PT. PICK 10) & KERNEL GPU MULTI-CONFIG
# ============================================================================

@torch.no_grad()
def gauss_hermite_subdraw_log_sum_w(
    space: HSV4Space,
    h_sub: torch.Tensor,
    V_sub: torch.Tensor,
    eta: float,
    gamma: float,
    k: int,
) -> float:
    """Calculează analitic în float64 ln ∑_{σ ⊂ D, |σ|=k} W_HS(σ | η, γ) pentru o extragere D (|D| = r >= k)
    prin identitatea exactă Hubbard–Stratonovich Gauss–Hermite + e_k (PROTOCOL_HSV4.md §2.1).
    Pentru Pick 10 (r=20, k=10, C(20,10)=184.756), rulează în ~0.05 ms cu eroare < 1e-13.
    """
    if gamma == 0.0:
        L = (eta * h_sub).unsqueeze(0)  # [1, r]
        c_shift = L.max(dim=1, keepdim=True).values
        ek_v, _ = elementary_symmetric_ek_and_marginals(torch.exp(L - c_shift), k)
        return float((float(k) * c_shift.squeeze() + torch.log(ek_v.squeeze())).item())

    s2g = math.sqrt(2.0 * gamma)
    L = eta * h_sub.unsqueeze(0) + s2g * (space.gh_x3 @ V_sub.T)  # [Q, r]
    c_shift = L.max(dim=1, keepdim=True).values                   # [Q, 1]
    ek_v, _ = elementary_symmetric_ek_and_marginals(torch.exp(L - c_shift), k)
    log_terms = space.gh_log_w3 + float(k) * c_shift.squeeze(1) + torch.log(ek_v)
    m_max = float(log_terms.max().item())
    w_sum = float(torch.exp(log_terms - m_max).sum().item())
    return m_max + math.log(w_sum)


@torch.no_grad()
def compute_all_experts_step_pack(
    space: HSV4Space,
    ops: Dict[str, torch.Tensor],
    draws_oh_step: torch.Tensor,
    joker_oh_step: Optional[torch.Tensor] = None,
    active_expert_mask: Optional[np.ndarray] = None,
) -> Dict[str, torch.Tensor]:
    """Calculează exact pentru toți experții activi m ∈ {1..7} la pasul s:
      - log_Z_m: [8]
      - pi_m: [8, N]
      - joker_prob_m: [8, M_J] (sau None)
      - draw_log_lrs: [m_draws, 8] (ln(P_m(D_u)/U(D_u)) per extragere individuală u)
      - step_log_lrs: [8] (∑_u draw_log_lrs[u, m])
    """
    dev = space.device
    N, r, k = space.N, space.r_draw, space.k_ticket
    has_joker = space.joker_m is not None and joker_oh_step is not None and bool(ops["joker_pack"])
    n_exp = len(EXPERT_GRID)

    log_z_m = torch.zeros(n_exp, dtype=torch.float64, device=dev)
    log_z_m[0] = math.log(float(space.total_states))

    pi_m = torch.zeros((n_exp, N), dtype=torch.float64, device=dev)
    pi_m[0] = float(k) / float(N)

    joker_m_prob = (
        torch.zeros((n_exp, int(space.joker_m)), dtype=torch.float64, device=dev)
        if has_joker
        else None
    )
    if has_joker and joker_m_prob is not None:
        joker_m_prob[0] = 1.0 / float(space.joker_m)

    expert_packs = []
    for m_idx in range(1, n_exp):
        if active_expert_mask is not None and not bool(active_expert_mask[m_idx]):
            continue
        h_m, h_j, J_mat, eta, gamma = _expert_field_tensors(ops, m_idx, has_joker)
        U_j = ops["joker_pack"]["U_joker"] if (has_joker and gamma > 0.0) else None
        gh_res = gauss_hermite_exact_hs(
            space, h_m, ops["V_s"], eta, gamma, h_joker=h_j, J_bipartite=J_mat, U_joker=U_j
        )
        lz = float(gh_res["log_Z"])
        log_z_m[m_idx] = lz
        pi_m[m_idx] = gh_res["pi_inclusion"]
        if has_joker and joker_m_prob is not None and gh_res["joker_prob"] is not None:
            joker_m_prob[m_idx] = gh_res["joker_prob"]
        expert_packs.append((m_idx, h_m, h_j, J_mat, U_j, eta, gamma, lz))

    m_draws = int(draws_oh_step.shape[0])
    draw_log_lrs = torch.zeros((m_draws, n_exp), dtype=torch.float64, device=dev)
    comb_rk = math.comb(r, k)
    log_norm_comb = math.log(float(space.total_states)) - math.log(float(comb_rk))
    use_gh_subdraw = (not has_joker) and (comb_rk > 256)

    for u in range(m_draws):
        balls_0 = sorted(int(x) for x in torch.nonzero(draws_oh_step[u] > 0.5, as_tuple=False).reshape(-1).tolist())
        if use_gh_subdraw:
            idx_t = torch.tensor(balls_0, dtype=torch.int64, device=dev)
            V_sub = ops["V_s"][idx_t]
            for m_idx, h_m, _, _, _, eta, gamma, lz in expert_packs:
                log_sum_w = gauss_hermite_subdraw_log_sum_w(space, h_m[idx_t], V_sub, eta, gamma, k)
                draw_log_lrs[u, m_idx] = log_norm_comb + (log_sum_w - lz)
        else:
            if r == k:
                subs = torch.tensor([balls_0], dtype=torch.int64, device=dev)
            else:
                subs = _all_k_subsets_of_draw(balls_0, k, dev)
            jb_idx = None
            if has_joker and joker_oh_step is not None:
                jb_val = int(torch.argmax(joker_oh_step[u]).item())
                jb_idx = torch.full((subs.shape[0],), jb_val, dtype=torch.int64, device=dev)
            for m_idx, h_m, h_j, J_mat, U_j, eta, gamma, lz in expert_packs:
                lw_subs = log_weight_hs_subset(subs, h_m, ops["V_s"], eta, gamma, jb_idx, h_j, J_mat, U_j)
                log_sum_p = float(torch.logsumexp(lw_subs - lz, dim=0).item())
                draw_log_lrs[u, m_idx] = log_norm_comb + log_sum_p

    step_log_lrs = draw_log_lrs.sum(dim=0)
    return {
        "log_Z_m": log_z_m,
        "pi_m": pi_m,
        "joker_prob_m": joker_m_prob,
        "draw_log_lrs": draw_log_lrs,
        "step_log_lrs": step_log_lrs,
    }


@torch.no_grad()
def evaluate_batch_sigma_alpha_multi_cfg(
    space: HSV4Space,
    ops_batch: Sequence[Dict[str, torch.Tensor]],
    log_z_batch: torch.Tensor,
    w_configs_batch: torch.Tensor,
    pi_configs_batch: torch.Tensor,
    params: HSV4Params = DEFAULT_PARAMS,
    exact_base_limit: int = 45_000_000,
    lw_configs_batch: Optional[torch.Tensor] = None,
) -> Dict[str, np.ndarray]:
    """Evaluează exact pe GPU biletul fundamental σ_α (și joker_α la jocuri bipartite) peste TOATE stările
    pentru un lot de B pași și C_cfg configurații simultan (ex. O1, O1+O2, O1+O4, Full HS-V4 într-o singură trecere!).

    Parametri:
      - ops_batch: listă de B dicționare forward_operators_from_state
      - log_z_batch: [B, 8]
      - w_configs_batch: [C_cfg, B, 8]
      - pi_configs_batch: [C_cfg, B, N]
      - lw_configs_batch: opțional [C_cfg, B, 8] log-averi exacte înainte de pasul s (elimină underflow-ul subnormal float64)
    Returnează:
      - sigma_alpha: [C_cfg, B, k] (1-based sortat)
      - alpha_log_prob: [C_cfg, B] (ln P_port(σ_α))
      - joker_alpha: [C_cfg, B] (1-based, sau None)
    """
    dev = space.device
    N, k = space.N, space.k_ticket
    B = len(ops_batch)
    C_cfg = int(w_configs_batch.shape[0])
    has_joker = space.joker_m is not None and bool(ops_batch[0]["joker_pack"])
    log_u = -math.log(float(space.total_states))

    # Calculăm log w_cond [C_cfg, B, 7] exact în spațiul logaritmic (imun la subnormale IEEE-754 chiar după >10.000 pași)
    w_act = w_configs_batch[:, :, 1:]                           # [C_cfg, B, 7]
    one_minus_w0 = w_act.sum(dim=2)                             # [C_cfg, B]
    log_thresh_15 = math.log(1e-15)
    if lw_configs_batch is not None:
        lw_act = lw_configs_batch[:, :, 1:]                     # [C_cfg, B, 7]
        lse_act = torch.logsumexp(lw_act, dim=2, keepdim=True)  # [C_cfg, B, 1]
        lw_cond_raw = torch.where(
            torch.isfinite(lse_act),
            lw_act - lse_act,
            torch.full_like(lw_act, math.log(1.0 / 7.0)),
        )
        lw_cond_cbm = torch.where(
            lw_cond_raw > log_thresh_15,
            lw_cond_raw,
            torch.full_like(lw_cond_raw, float("-inf")),
        )
    else:
        cond_sum = one_minus_w0.clamp(min=1e-290)
        w_cond = torch.where(
            one_minus_w0.unsqueeze(2) > 1e-290,
            w_act / cond_sum.unsqueeze(2),
            torch.full_like(w_act, 1.0 / 7.0),
        )
        lw_cond_cbm = torch.where(
            w_cond > 1e-15,
            torch.log(w_cond.clamp(min=1e-300)),
            torch.full_like(w_cond, float("-inf")),
        )  # [C_cfg, B, 7]

    # Caz spațiu uriaș (ex. Pick 10 10/80 cu C(80,10) = 1.646e12 > exact_base_limit):
    # aplicăm exact regula bazinului din marginale din core.evaluate_portfolio_full_space (liniile 1101-1117)
    if space.total_base_states > exact_base_limit:
        tickets_out = np.zeros((C_cfg, B, k), dtype=np.int64)
        lp_port_out = np.zeros((C_cfg, B), dtype=np.float64)
        m_pool_balls = min(max(k + 8, min(N, 22)), 16)
        comb_template = torch.tensor(
            list(combinations(range(m_pool_balls), k))[: params.pool_size],
            dtype=torch.int64,
            device=dev,
        )
        for b_i in range(B):
            ops_s = ops_batch[b_i]
            lz_s = log_z_batch[b_i]  # [8]
            for c_i in range(C_cfg):
                pi_port = pi_configs_batch[c_i, b_i]
                top_balls = torch.argsort(-pi_port)[: max(k + 8, min(N, 22))]
                sorted_top = torch.sort(top_balls[:m_pool_balls]).values
                cand_comb = sorted_top[comb_template]
                lp_terms = []
                for m_idx in range(1, len(EXPERT_GRID)):
                    lwc = float(lw_cond_cbm[c_i, b_i, m_idx - 1].item())
                    if not math.isfinite(lwc):
                        continue
                    h_m, h_j, J_mat, eta, gamma = _expert_field_tensors(ops_s, m_idx, False)
                    lw_sub = log_weight_hs_subset(cand_comb, h_m, ops_s["V_s"], eta, gamma, None, None, None, None)
                    lp_terms.append(lwc + lw_sub - float(lz_s[m_idx].item()))
                lp_act = lp_terms[0] if len(lp_terms) == 1 else torch.logsumexp(torch.stack(lp_terms, dim=0), dim=0)
                lp_np = lp_act.detach().cpu().numpy()
                best_idx = int(np.argsort(-lp_np, kind="mergesort")[0])
                best_lp_a = float(lp_np[best_idx])
                omw0 = float(one_minus_w0[c_i, b_i].item())
                lp_p = log_u + math.log1p(max(omw0 * (math.exp(best_lp_a - log_u) - 1.0), -0.999999999))
                tickets_out[c_i, b_i] = cand_comb[best_idx].detach().cpu().numpy().astype(np.int64) + 1
                lp_port_out[c_i, b_i] = lp_p
        return {
            "sigma_alpha": tickets_out,
            "alpha_log_prob": lp_port_out,
            "joker_alpha": None,
        }

    # Enumerare exactă pe GPU peste TOATE cele C(N, k) (sau C(N, k) × M_J) stări!
    space.ensure_comb_cache(max_cached_states=50_000_000)

    # Împachetăm cele 6 trăsături per bilă [h_int, h_aero, h_rng, V_0, V_1, V_2] într-un singur tensor [N, 6, B]
    F_pack = torch.empty((N, 6, B), dtype=torch.float64, device=dev)
    for b_i, ops_s in enumerate(ops_batch):
        F_pack[:, 0, b_i] = ops_s["h_int"]
        F_pack[:, 1, b_i] = ops_s["h_aero"]
        F_pack[:, 2, b_i] = ops_s["h_rng"]
        V_s = ops_s["V_s"]
        r_dim = V_s.shape[1]
        F_pack[:, 3 : 3 + r_dim, b_i] = V_s
        if r_dim < 3:
            F_pack[:, 3 + r_dim : 6, b_i] = 0.0
    F_flat = F_pack.reshape(N, 6 * B).contiguous()

    lz_17 = log_z_batch[:, 1:].T.contiguous()  # [7, B]
    # [C_cfg, 7, B] = lw_cond - log_Z_m
    offset_cbm = lw_cond_cbm.permute(0, 2, 1).contiguous() - lz_17.unsqueeze(0)  # [C_cfg, 7, B]
    active_m_any = [m_pos for m_pos in range(7) if bool(torch.isfinite(offset_cbm[:, m_pos, :]).any().item())]

    best_val = torch.full((C_cfg, B), float("-inf"), dtype=torch.float64, device=dev)
    best_rank = torch.zeros((C_cfg, B), dtype=torch.int64, device=dev)
    best_jok = torch.zeros((C_cfg, B), dtype=torch.int64, device=dev) if has_joker else None

    if not has_joker:
        chunk_sz = 262_144 if B <= 32 else 131_072
        inv_sqrt2 = 1.0 / math.sqrt(2.0)

        for start in range(0, space.total_base_states, chunk_sz):
            end = min(start + chunk_sz, space.total_base_states)
            comb = space.unrank_chunk(start, end)  # [C, k]
            C_len = comb.shape[0]

            s_flat = F_flat[comb[:, 0]]
            for d in range(1, k):
                s_flat = s_flat + F_flat[comb[:, d]]
            S6 = s_flat.view(C_len, 6, B)
            s_int = S6[:, 0, :]
            s_aero = S6[:, 1, :]
            s_rng = S6[:, 2, :]
            sv0, sv1, sv2 = S6[:, 3, :], S6[:, 4, :], S6[:, 5, :]
            q_bos = 0.5 * (sv0 * sv0 + sv1 * sv1 + sv2 * sv2)  # [C, B]

            # Calculăm lw_m [C, B] doar pentru experții activi
            lw_experts: Dict[int, torch.Tensor] = {}
            for m_pos in active_m_any:
                m_idx = m_pos + 1
                _, _, f_kind, eta, gamma, _ = EXPERT_GRID[m_idx]
                if f_kind in ("none", "zero"):
                    val = gamma * q_bos
                elif f_kind == "int":
                    val = eta * s_int + (gamma * q_bos if gamma > 0.0 else 0.0)
                elif f_kind == "aero":
                    val = eta * s_aero
                elif f_kind == "int_aero":
                    val = (eta * inv_sqrt2) * (s_int + s_aero) + gamma * q_bos
                else:
                    val = eta * s_rng
                lw_experts[m_pos] = val

            for c_i in range(C_cfg):
                terms_c = []
                for m_pos in active_m_any:
                    off_b = offset_cbm[c_i, m_pos]  # [B]
                    if bool(torch.isfinite(off_b).any().item()):
                        terms_c.append(lw_experts[m_pos] + off_b.unsqueeze(0))
                lp_act = terms_c[0] if len(terms_c) == 1 else torch.logsumexp(torch.stack(terms_c, dim=0), dim=0)  # [C, B]
                c_max, c_arg = lp_act.max(dim=0)
                better = c_max > best_val[c_i]
                best_val[c_i] = torch.where(better, c_max, best_val[c_i])
                best_rank[c_i] = torch.where(better, start + c_arg, best_rank[c_i])
    else:
        M = int(space.joker_m)
        inv_sqrt2 = 1.0 / math.sqrt(2.0)
        # Pre-împachetăm tensorii secundari M_J pe lotul B
        J_bip_pack = torch.stack([o["joker_pack"]["J_s"] for o in ops_batch], dim=1).contiguous()       # [N, B, M]
        J_bip_flat = J_bip_pack.reshape(N, B * M).contiguous()
        hj_int_bm = torch.stack([o["joker_pack"]["hj_int"] for o in ops_batch], dim=0).contiguous()     # [B, M]
        hj_aero_bm = torch.stack([o["joker_pack"]["hj_aero"] for o in ops_batch], dim=0).contiguous()   # [B, M]
        hj_rng_bm = torch.stack([o["joker_pack"]["hj_rng"] for o in ops_batch], dim=0).contiguous()     # [B, M]
        Uj_bmr = torch.stack([o["joker_pack"]["U_joker"] for o in ops_batch], dim=0).contiguous()       # [B, M, R]
        if Uj_bmr.shape[2] < 3:
            pad_u = torch.zeros((B, M, 3 - Uj_bmr.shape[2]), dtype=torch.float64, device=dev)
            Uj_bmr = torch.cat([Uj_bmr, pad_u], dim=2)

        chunk_sz = max(min(65_536, (32 * 65_536) // max(B * M // 10, 1)), 8_192)
        b_ar = torch.arange(B, dtype=torch.int64, device=dev)

        for start in range(0, space.total_base_states, chunk_sz):
            end = min(start + chunk_sz, space.total_base_states)
            comb = space.unrank_chunk(start, end)  # [C, k]
            C_len = comb.shape[0]

            s_flat = F_flat[comb[:, 0]]
            jb_flat = J_bip_flat[comb[:, 0]]
            for d in range(1, k):
                cd = comb[:, d]
                s_flat = s_flat + F_flat[cd]
                jb_flat = jb_flat + J_bip_flat[cd]

            S6 = s_flat.view(C_len, 6, B)
            s_int = S6[:, 0, :].unsqueeze(2)    # [C, B, 1]
            s_aero = S6[:, 1, :].unsqueeze(2)   # [C, B, 1]
            s_rng = S6[:, 2, :].unsqueeze(2)    # [C, B, 1]
            sv = S6[:, 3:6, :].permute(0, 2, 1).unsqueeze(2)  # [C, B, 1, 3]
            s_j_bip = jb_flat.view(C_len, B, M)               # [C, B, M]

            diff_v = sv + Uj_bmr.unsqueeze(0)                 # [C, B, M, 3]
            q_bos_jm = 0.5 * (diff_v * diff_v).sum(dim=3)     # [C, B, M]

            lw_experts_jm: Dict[int, torch.Tensor] = {}
            for m_pos in active_m_any:
                m_idx = m_pos + 1
                _, _, f_kind, eta, gamma, _ = EXPERT_GRID[m_idx]
                if f_kind in ("none", "zero"):
                    val = gamma * q_bos_jm
                elif f_kind == "int":
                    val = eta * (s_int + hj_int_bm.unsqueeze(0) + s_j_bip) + (gamma * q_bos_jm if gamma > 0.0 else 0.0)
                elif f_kind == "aero":
                    val = eta * (s_aero + hj_aero_bm.unsqueeze(0))
                elif f_kind == "int_aero":
                    val = (
                        (eta * inv_sqrt2) * ((s_int + s_aero) + (hj_int_bm + hj_aero_bm).unsqueeze(0))
                        + eta * s_j_bip
                        + gamma * q_bos_jm
                    )
                else:
                    val = eta * (s_rng + hj_rng_bm.unsqueeze(0))
                lw_experts_jm[m_pos] = val

            for c_i in range(C_cfg):
                terms_c = []
                for m_pos in active_m_any:
                    off_b = offset_cbm[c_i, m_pos]  # [B]
                    if bool(torch.isfinite(off_b).any().item()):
                        terms_c.append(lw_experts_jm[m_pos] + off_b.view(1, B, 1))
                lp_act_jm = terms_c[0] if len(terms_c) == 1 else torch.logsumexp(torch.stack(terms_c, dim=0), dim=0)  # [C, B, M]
                j_max_val, j_max_idx = lp_act_jm.max(dim=2)                      # [C, B], [C, B]
                c_max, c_arg = j_max_val.max(dim=0)                              # [B], [B]
                c_jok = j_max_idx[c_arg, b_ar]                                   # [B]
                better = c_max > best_val[c_i]
                best_val[c_i] = torch.where(better, c_max, best_val[c_i])
                best_rank[c_i] = torch.where(better, start + c_arg, best_rank[c_i])
                assert best_jok is not None
                best_jok[c_i] = torch.where(better, c_jok, best_jok[c_i])

    # Decodăm rangurile combinadice câștigătoare în bile 1-based
    tickets = np.zeros((C_cfg, B, k), dtype=np.int64)
    ranks_np = best_rank.detach().cpu().numpy()
    for c_i in range(C_cfg):
        for b_i in range(B):
            rk = int(ranks_np[c_i, b_i])
            c_row = space.unrank_chunk(rk, rk + 1)[0].detach().cpu().numpy()
            tickets[c_i, b_i] = c_row + 1

    lp_port = (
        log_u + torch.log1p((one_minus_w0 * (torch.exp(best_val - log_u) - 1.0)).clamp(min=-0.999999999))
    ).detach().cpu().numpy()

    joker_alpha = (best_jok.detach().cpu().numpy() + 1).astype(np.int64) if (has_joker and best_jok is not None) else None
    return {
        "sigma_alpha": tickets,
        "alpha_log_prob": lp_port,
        "joker_alpha": joker_alpha,
    }


def verify_fast_engine_against_core(device: Optional[torch.device] = None) -> Dict[str, Any]:
    """Certifică numeric (< 1e-12) și combinatorial (sigma_alpha identic) motorul multi-config față de hs_v4/core.py
    pe 649, 540, joker și Pick 10 (N=80, r=20, k=10).
    """
    from hs_v4.verify_q import _synth_universe_with_meteo

    dev = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    report: Dict[str, Any] = {}

    test_specs = [
        ("649", 49, 6, 6, None, 202601),
        ("540", 40, 6, 5, None, 202602),
        ("joker", 45, 5, 5, 20, 202603),
    ]
    cfgs = list(ABLATION_CONFIGS) + [("O2_only", "O2 Negative Control", False, True, False)]

    for code, N, r, k, jm, seed in test_specs:
        sp = HSV4Space(N=N, r_draw=r, k_ticket=k, device=dev, joker_m=jm)
        oh, offs, joh, met = _synth_universe_with_meteo(N, r, n_steps=16, seed=seed, device=dev, joker_m=jm)
        slices = extract_step_slices(oh, offs, joh, met)
        warmup_t = 10

        # 1. Rulare de referință independentă cu hs_v4.core pentru fiecare dintre cele 5 configurații
        ref_states: Dict[str, HSV4State] = {}
        ref_evals: Dict[str, Dict[str, Any]] = {}
        for c_key, _, eo1, eo2, eo4 in cfgs:
            st_c = init_state(sp, enable_o1=eo1, enable_o2=eo2, enable_o4=eo4)
            advance_steps(st_c, sp, slices[:15], update_portfolio=True, min_wealth_step=warmup_t)
            ops_c = forward_operators_from_state(st_c, sp, slices[15][2])
            ev_c = evaluate_portfolio_full_space(sp, ops_c)
            advance_one_step(st_c, sp, slices[15][0], slices[15][1], slices[15][2], update_portfolio=True, min_wealth_step=warmup_t)
            ref_states[c_key] = st_c
            ref_evals[c_key] = ev_c

        # 2. Rulare unificată multi-config
        st_u = init_state(sp, enable_o1=True, enable_o2=True, enable_o4=True)
        advance_steps(st_u, sp, slices[:warmup_t], update_portfolio=False)

        log_w_cfgs = {}
        for c_key, _, eo1, eo2, eo4 in cfgs:
            pr = compute_prior_weights(eo1, eo2, eo4)
            lw = torch.full((8,), float("-inf"), dtype=torch.float64, device=dev)
            for idx_p, pv in enumerate(pr):
                if pv > 0.0:
                    lw[idx_p] = math.log(pv)
            log_w_cfgs[c_key] = lw

        ops_list = []
        lz_list = []
        w_cfg_steps = {c_key: [] for c_key, *_ in cfgs}
        pi_cfg_steps = {c_key: [] for c_key, *_ in cfgs}

        for s in range(warmup_t, 16):
            oh_s, jh_s, met_s = slices[s]
            ops_s = forward_operators_from_state(st_u, sp, met_s)
            pack_s = compute_all_experts_step_pack(sp, ops_s, oh_s.to(torch.float64), jh_s.to(torch.float64) if jh_s is not None else None)
            ops_list.append(ops_s)
            lz_list.append(pack_s["log_Z_m"])

            for c_key, *_ in cfgs:
                lw_cur = log_w_cfgs[c_key]
                fin = torch.isfinite(lw_cur)
                m_max = lw_cur[fin].max()
                w_cur = torch.where(fin, torch.exp(lw_cur - m_max), torch.zeros_like(lw_cur))
                w_cur = w_cur / w_cur.sum()
                w_cfg_steps[c_key].append(w_cur)
                pi_cfg_steps[c_key].append((w_cur.unsqueeze(1) * pack_s["pi_m"]).sum(dim=0))
                log_w_cfgs[c_key] = torch.where(fin, lw_cur + pack_s["step_log_lrs"], lw_cur)

            advance_one_step(st_u, sp, oh_s, jh_s, met_s, update_portfolio=False)

        lz_batch = torch.stack(lz_list, dim=0)
        w_batch = torch.stack([torch.stack(w_cfg_steps[c_key], dim=0) for c_key, *_ in cfgs], dim=0)
        pi_batch = torch.stack([torch.stack(pi_cfg_steps[c_key], dim=0) for c_key, *_ in cfgs], dim=0)
        bat_alpha = evaluate_batch_sigma_alpha_multi_cfg(sp, ops_list, lz_batch, w_batch, pi_batch)

        max_w_err = 0.0
        max_pi_err = 0.0
        max_lp_err = 0.0
        tickets_ok = True
        for c_i, (c_key, *_) in enumerate(cfgs):
            lw_ref = ref_states[c_key].log_wealth
            lw_got = log_w_cfgs[c_key]
            fin = torch.isfinite(lw_ref)
            w_err = float((lw_ref[fin] - lw_got[fin]).abs().max().item())
            pi_err = float((pi_batch[c_i, -1] - ref_evals[c_key]["pi_inclusion"]).abs().max().item())
            lp_err = abs(float(bat_alpha["alpha_log_prob"][c_i, -1]) - float(ref_evals[c_key]["variants"][0]["log_prob"]))
            t_got = bat_alpha["sigma_alpha"][c_i, -1].tolist()
            t_ref = ref_evals[c_key]["variants"][0]["ticket"]
            j_ok = True
            if jm is not None and bat_alpha["joker_alpha"] is not None:
                j_ok = int(bat_alpha["joker_alpha"][c_i, -1]) == int(ref_evals[c_key]["variants"][0]["joker"])
            max_w_err = max(max_w_err, w_err)
            max_pi_err = max(max_pi_err, pi_err)
            max_lp_err = max(max_lp_err, lp_err)
            tickets_ok = tickets_ok and (t_got == t_ref) and j_ok

        if not (max_w_err < 1e-12 and max_pi_err < 1e-12 and max_lp_err < 1e-12 and tickets_ok):
            raise RuntimeError(
                f"Eroare aliniere multi-config {code}: w={max_w_err}, pi={max_pi_err}, lp={max_lp_err}, tickets={tickets_ok}"
            )
        report[code] = {
            "max_log_wealth_err": max_w_err,
            "max_pi_err": max_pi_err,
            "max_alpha_lp_err": max_lp_err,
            "tickets_exact_match": tickets_ok,
        }

    # 3. Certificare identitate GH + e_10 sub-extragere pentru Pick 10 (N=80, r=20, k=10, C(20,10)=184.756)
    sp_p10 = HSV4Space(N=80, r_draw=20, k_ticket=10, device=dev)
    oh_10, offs_10, _, met_10 = _synth_universe_with_meteo(80, 20, n_steps=8, seed=20268010, device=dev)
    slices_10 = extract_step_slices(oh_10, offs_10, None, met_10)
    st_10_ref = init_state(sp_p10)
    st_10_fast = init_state(sp_p10)
    advance_steps(st_10_ref, sp_p10, slices_10[:7], update_portfolio=False)
    advance_steps(st_10_fast, sp_p10, slices_10[:7], update_portfolio=False)

    ops_10 = forward_operators_from_state(st_10_fast, sp_p10, slices_10[7][2])
    fast_pack_10 = compute_all_experts_step_pack(sp_p10, ops_10, slices_10[7][0])
    advance_one_step(st_10_ref, sp_p10, slices_10[7][0], None, slices_10[7][2], update_portfolio=True, min_wealth_step=0)
    ref_lrs_10 = st_10_ref.log_wealth - st_10_fast.log_wealth
    p10_lr_err = float((ref_lrs_10 - fast_pack_10["step_log_lrs"]).abs().max().item())
    if p10_lr_err >= 1e-11:
        raise RuntimeError(f"Eroare GH sub-extragere Pick 10 (184.756 submulțimi): {p10_lr_err}")
    report["pick10_gh_subdraw_vs_184756_subsets_err"] = p10_lr_err
    return report


# ============================================================================
# 4. CATEGORII DE POTRIVIRI & REZUMAT STATISTIC PE FERESTRE
# ============================================================================

def compute_category_distribution(
    N: int,
    r_draw: int,
    k_ticket: int,
    joker_m: Optional[int],
    main_hits_hsv4: np.ndarray,
    main_hits_b: np.ndarray,
    main_hits_r: np.ndarray,
    joker_hits_hsv4: Optional[np.ndarray] = None,
    joker_hits_b: Optional[np.ndarray] = None,
    joker_hits_r: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Construiește distribuția completă pe categorii câștigătoare față de U (hipergeometric exact), B și R."""
    n_draws = int(main_hits_hsv4.shape[0])
    denom = float(math.comb(N, k_ticket))
    # Pentru un bilet de mărime k_ticket și o extragere de mărime r_draw din N:
    # P_U(|σ ∩ D| = h) = C(r_draw, h) * C(N - r_draw, k_ticket - h) / C(N, k_ticket)
    main_probs_u = {}
    for h in range(0, min(r_draw, k_ticket) + 1):
        if k_ticket - h <= N - r_draw:
            p_h = (math.comb(r_draw, h) * math.comb(N - r_draw, k_ticket - h)) / denom
        else:
            p_h = 0.0
        main_probs_u[h] = p_h

    hist_main = {}
    for h, p_h in main_probs_u.items():
        key = f"{h}/{k_ticket}"
        hist_main[key] = {
            "HSV4": int(np.sum(main_hits_hsv4 == h)),
            "B": int(np.sum(main_hits_b == h)),
            "R": int(np.sum(main_hits_r == h)),
            "expected_U": round(n_draws * p_h, 4),
        }

    tiers: Dict[str, Any] = {}
    for thresh in (3, 4, 5, 6, 7, 8, 9, 10):
        if thresh <= min(r_draw, k_ticket):
            p_ge = sum(v for h_k, v in main_probs_u.items() if h_k >= thresh)
            lbl = f"{thresh}+" if thresh < min(r_draw, k_ticket) else f"{thresh}/{k_ticket}"
            tiers[lbl] = {
                "HSV4": int(np.sum(main_hits_hsv4 >= thresh)),
                "B": int(np.sum(main_hits_b >= thresh)),
                "R": int(np.sum(main_hits_r >= thresh)),
                "expected_U": round(n_draws * p_ge, 4),
            }
            if thresh < min(r_draw, k_ticket):
                exact_lbl = f"exact_{thresh}/{k_ticket}"
                tiers[exact_lbl] = hist_main[f"{thresh}/{k_ticket}"]

    # Categorie specială Pick 10: 0/10 pe 20 bile extrase din 80 este de asemenea categorie oficială
    if r_draw == 20 and k_ticket == 10:
        tiers["exact_0/10"] = hist_main["0/10"]

    out: Dict[str, Any] = {
        "n_target_draws": n_draws,
        "main_histogram": hist_main,
        "winning_tiers": tiers,
    }

    if joker_m is not None and joker_hits_hsv4 is not None and joker_hits_b is not None and joker_hits_r is not None:
        pj1 = 1.0 / float(joker_m)
        pj0 = 1.0 - pj1
        joint_tiers: Dict[str, Any] = {}
        for h in range(min(r_draw, k_ticket), -1, -1):
            for j_hit in (1, 0):
                if h == 0 and j_hit == 0:
                    continue
                p_joint = main_probs_u.get(h, 0.0) * (pj1 if j_hit == 1 else pj0)
                j_lbl = f"{h}+Bonus" if j_hit == 1 else f"{h}+0"
                joint_tiers[j_lbl] = {
                    "HSV4": int(np.sum((main_hits_hsv4 == h) & (joker_hits_hsv4 == j_hit))),
                    "B": int(np.sum((main_hits_b == h) & (joker_hits_b == j_hit))),
                    "R": int(np.sum((main_hits_r == h) & (joker_hits_r == j_hit))),
                    "expected_U": round(n_draws * p_joint, 4),
                }
        out["bonus_ball_hits"] = {
            "HSV4": int(np.sum(joker_hits_hsv4 == 1)),
            "B": int(np.sum(joker_hits_b == 1)),
            "R": int(np.sum(joker_hits_r == 1)),
            "expected_U": round(n_draws * pj1, 4),
        }
        out["joint_bonus_tiers"] = joint_tiers

    return out


def summarize_window_metrics(
    step_mask: np.ndarray,
    draw_mask: np.ndarray,
    expected_hits_u: float,
    hits_hsv4: np.ndarray,
    hits_b: np.ndarray,
    hits_r: np.ndarray,
    log_step_hsv4: np.ndarray,
    log_step_u: np.ndarray,
    log_step_b: np.ndarray,
    log_step_r: np.ndarray,
    brier_draw_hsv4: np.ndarray,
    brier_draw_u: np.ndarray,
    brier_draw_b: np.ndarray,
    brier_draw_r: np.ndarray,
) -> Dict[str, Any]:
    n_steps_w = int(step_mask.sum())
    n_draws_w = int(draw_mask.sum())
    h_hs = int(hits_hsv4[draw_mask].sum())
    h_b = int(hits_b[draw_mask].sum())
    h_r = int(hits_r[draw_mask].sum())
    mean_h_hs = (float(h_hs) / float(n_draws_w)) if n_draws_w > 0 else 0.0
    return {
        "n_steps": n_steps_w,
        "n_draws": n_draws_w,
        "hits_HSV4": h_hs,
        "hits_B": h_b,
        "hits_R": h_r,
        "mean_hits_HSV4": round(mean_h_hs, 6),
        "expected_mean_hits_U": round(expected_hits_u, 6),
        "excess_hits_vs_U": round(mean_h_hs - expected_hits_u, 6),
        "log_score_HSV4": round(float(log_step_hsv4[step_mask].sum()), 6),
        "log_score_U": round(float(log_step_u[step_mask].sum()), 6),
        "log_score_B": round(float(log_step_b[step_mask].sum()), 6),
        "log_score_R": round(float(log_step_r[step_mask].sum()), 6),
        "brier_HSV4": round(float(brier_draw_hsv4[draw_mask].sum()), 6),
        "brier_U": round(float(brier_draw_u[draw_mask].sum()), 6),
        "brier_B": round(float(brier_draw_b[draw_mask].sum()), 6),
        "brier_R": round(float(brier_draw_r[draw_mask].sum()), 6),
    }


def evaluate_gates_g1_g6(
    win_total: Dict[str, Any],
    win_h1: Dict[str, Any],
    win_h2: Dict[str, Any],
    win_last100: Dict[str, Any],
    e_curve: np.ndarray,
) -> Tuple[List[Dict[str, Any]], int]:
    """Evaluează exact porțile G1–G6 din PROTOCOL_HSV4.md §3.2."""
    final_E = float(e_curve[-1])
    min_E = float(np.min(e_curve))
    max_E = float(np.max(e_curve))
    log10_final_E = math.log10(max(final_E, 1e-300))

    g1_pass = win_total["excess_hits_vs_U"] >= 0.20
    g2_pass = win_total["hits_HSV4"] > max(win_total["hits_B"], win_total["hits_R"])
    g3_pass = win_total["log_score_HSV4"] > max(
        win_total["log_score_U"], win_total["log_score_B"], win_total["log_score_R"]
    )
    g4_pass = win_total["brier_HSV4"] < min(
        win_total["brier_U"], win_total["brier_B"], win_total["brier_R"]
    )
    g5_pass = (
        (win_h1["log_score_HSV4"] > win_h1["log_score_B"])
        and (win_h2["log_score_HSV4"] > win_h2["log_score_B"])
        and (win_last100["log_score_HSV4"] > win_last100["log_score_B"])
    )
    g6_pass = final_E > 1.0

    gates = [
        {
            "id": "G1",
            "rule": "Exces mediu de potriviri σ_α peste media hipergeometrică uniformă >= +0.20",
            "pass": bool(g1_pass),
            "value": win_total["excess_hits_vs_U"],
            "threshold": 0.20,
        },
        {
            "id": "G2",
            "rule": "Hits(HS-V4) > max(Hits(B), Hits(R))",
            "pass": bool(g2_pass),
            "value": {
                "HSV4": win_total["hits_HSV4"],
                "B": win_total["hits_B"],
                "R": win_total["hits_R"],
            },
        },
        {
            "id": "G3",
            "rule": "LogScore(HS-V4) > max(LogScore(U), LogScore(B), LogScore(R))",
            "pass": bool(g3_pass),
            "value": {
                "HSV4": win_total["log_score_HSV4"],
                "U": win_total["log_score_U"],
                "B": win_total["log_score_B"],
                "R": win_total["log_score_R"],
                "diff_vs_U": round(win_total["log_score_HSV4"] - win_total["log_score_U"], 6),
                "diff_vs_B": round(win_total["log_score_HSV4"] - win_total["log_score_B"], 6),
                "diff_vs_R": round(win_total["log_score_HSV4"] - win_total["log_score_R"], 6),
            },
        },
        {
            "id": "G4",
            "rule": "Brier(HS-V4) < min(Brier(U), Brier(B), Brier(R))",
            "pass": bool(g4_pass),
            "value": {
                "HSV4": win_total["brier_HSV4"],
                "U": win_total["brier_U"],
                "B": win_total["brier_B"],
                "R": win_total["brier_R"],
            },
        },
        {
            "id": "G5",
            "rule": "LogScore(HS-V4) > LogScore(B) în ambele jumătăți ale arhivei și pe ultimii 100 pași",
            "pass": bool(g5_pass),
            "value": {
                "half1_diff_HSV4_minus_B": round(win_h1["log_score_HSV4"] - win_h1["log_score_B"], 6),
                "half2_diff_HSV4_minus_B": round(win_h2["log_score_HSV4"] - win_h2["log_score_B"], 6),
                "last100_diff_HSV4_minus_B": round(win_last100["log_score_HSV4"] - win_last100["log_score_B"], 6),
            },
        },
        {
            "id": "G6",
            "rule": "Valoarea martingală a portofoliului Bayesian E_S > 1.0 (garanție E_s >= 0.50)",
            "pass": bool(g6_pass),
            "value": {
                "E_S": round(final_E, 8),
                "log10_E_S": round(log10_final_E, 8),
                "min_E_s": round(min_E, 8),
                "max_E_s": round(max_E, 8),
                "guarantee_E_ge_050_all_steps": bool(min_E >= 0.50 - 1e-12),
            },
        },
    ]
    passed = sum(1 for g in gates if g["pass"])
    return gates, passed


# ============================================================================
# 5. MOTOR WALK-FORWARD MULTI-CONFIG REUTILIZABIL (FAZA 2A RO + FAZA 2B INTL)
# ============================================================================

@dataclass
class WalkForwardInput:
    game_code: str
    game_name: str
    N: int
    r_draw: int
    k_ticket: int
    joker_m: Optional[int]
    draws_1based: torch.Tensor
    onehot: torch.Tensor
    joker_1based: Optional[torch.Tensor]
    joker_onehot: Optional[torch.Tensor]
    step_offsets: torch.Tensor
    step_dates: List[str]
    keys: List[str]
    meteo_features: np.ndarray
    source_meta: Dict[str, Any]


def _sanitize_subnormal_ops_for_core(ops: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
    """Previne underflow-ul subnormal IEEE-754 (0 < 1 - w_0 < 1e-290) în core.evaluate_portfolio_full_space."""
    w_p = ops["w_portfolio"]
    omw0 = float(w_p[1:].sum().item())
    if 0.0 < omw0 < 1e-290:
        w_clean = torch.zeros_like(w_p)
        w_clean[0] = 1.0
        return {**ops, "w_portfolio": w_clean}
    return ops


@torch.no_grad()
def run_generic_walkforward_configs(
    wf_in: WalkForwardInput,
    configs: Sequence[Tuple[str, str, bool, bool, bool]],
    warmup: int = WARMUP_STEPS,
    params: HSV4Params = DEFAULT_PARAMS,
    save_npz_dir: Optional[Path] = None,
    npz_prefix: Optional[str] = None,
    compute_terminal_states: bool = True,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Rulează strict cauzal pe s = warmup .. S-1 una sau mai multe configurații (ex. cele 4 ablații)
    într-o singură parcurgere exactă a spațiului stărilor pe GPU.
    """
    t0 = time.perf_counter()
    dev = wf_in.onehot.device
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats()

    N, r, k, jm = wf_in.N, wf_in.r_draw, wf_in.k_ticket, wf_in.joker_m
    has_joker = jm is not None and wf_in.joker_onehot is not None and wf_in.joker_1based is not None
    S_total = len(wf_in.step_dates)
    if S_total <= warmup:
        raise RuntimeError(f"Arhivă prea scurtă pentru {wf_in.game_code}: S={S_total} <= warmup={warmup}")

    eval_steps = np.arange(warmup, S_total, dtype=np.int64)
    K_eval = int(eval_steps.shape[0])
    C_cfg = len(configs)

    # Parametri cu exact_state_limit ridicat la 300M astfel încât și Powerball (292.2M stări) să fie evaluat exact pe GPU
    run_params = HSV4Params(exact_state_limit=max(params.exact_state_limit, 300_000_000))
    space = HSV4Space(N=N, r_draw=r, k_ticket=k, device=dev, joker_m=jm, gh_order=run_params.gh_order)

    meteo_t = torch.as_tensor(wf_in.meteo_features, dtype=torch.float64, device=dev)
    slices = extract_step_slices(wf_in.onehot, wf_in.step_offsets, wf_in.joker_onehot, meteo_t)

    offs_np = wf_in.step_offsets.detach().cpu().numpy().astype(np.int64)
    oh_np = wf_in.onehot.detach().cpu().numpy().astype(np.float64)
    draws_np = wf_in.draws_1based.detach().cpu().numpy().astype(np.int64)
    jok_np = wf_in.joker_1based.detach().cpu().numpy().astype(np.int64) if has_joker else None
    joh_np = wf_in.joker_onehot.detach().cpu().numpy().astype(np.float64) if has_joker else None

    # 1. Pre-calcul strict cauzal repere canonice B și R (fără nicio scurgere din pasul curent!)
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

    # 2. Inițializare stare Markoviană + averi a priori pe fiecare configurație
    state = init_state(space, params=run_params, enable_o1=True, enable_o2=True, enable_o4=True)
    advance_steps(state, space, slices[:warmup], params=run_params, update_portfolio=False)

    log_wealth_cfgs: List[torch.Tensor] = []
    priors_cfgs: List[np.ndarray] = []
    active_exp_union = np.zeros(len(EXPERT_GRID), dtype=bool)
    for _, _, eo1, eo2, eo4 in configs:
        pr = compute_prior_weights(eo1, eo2, eo4, w0_prior=run_params.w0_prior)
        priors_cfgs.append(pr)
        active_exp_union |= (pr > 0.0)
        lw = torch.full((len(EXPERT_GRID),), float("-inf"), dtype=torch.float64, device=dev)
        for idx_p, pv in enumerate(pr):
            if pv > 0.0:
                lw[idx_p] = math.log(pv)
        log_wealth_cfgs.append(lw)

    # Alocare tablouri rezultate pe K_eval pași și n_target_draws extrageri
    first_draw = int(offs_np[warmup])
    n_draws_total = int(wf_in.draws_1based.shape[0])
    n_target_draws = n_draws_total - first_draw

    w_hist_cfgs = np.zeros((C_cfg, K_eval + 1, len(EXPERT_GRID)), dtype=np.float64)
    e_curve_cfgs = np.ones((C_cfg, K_eval + 1), dtype=np.float64)
    for c_i in range(C_cfg):
        w_hist_cfgs[c_i, 0] = priors_cfgs[c_i]
        e_curve_cfgs[c_i, 0] = 1.0

    sigma_alpha_cfgs = np.zeros((C_cfg, K_eval, k), dtype=np.int64)
    alpha_lp_cfgs = np.zeros((C_cfg, K_eval), dtype=np.float64)
    joker_alpha_cfgs = np.zeros((C_cfg, K_eval), dtype=np.int64) if has_joker else None

    log_step_cfgs = np.zeros((C_cfg, K_eval), dtype=np.float64)
    log_step_u = np.zeros(K_eval, dtype=np.float64)
    log_step_b = np.zeros(K_eval, dtype=np.float64)
    log_step_r = np.zeros(K_eval, dtype=np.float64)

    target_step_arr = np.zeros(n_target_draws, dtype=np.int64)
    log_draw_cfgs = np.zeros((C_cfg, n_target_draws), dtype=np.float64)
    log_draw_u = np.zeros(n_target_draws, dtype=np.float64)
    log_draw_b = np.zeros(n_target_draws, dtype=np.float64)
    log_draw_r = np.zeros(n_target_draws, dtype=np.float64)

    brier_draw_cfgs = np.zeros((C_cfg, n_target_draws), dtype=np.float64)
    brier_draw_u = np.zeros(n_target_draws, dtype=np.float64)
    brier_draw_b = np.zeros(n_target_draws, dtype=np.float64)
    brier_draw_r = np.zeros(n_target_draws, dtype=np.float64)

    hits_main_cfgs = np.zeros((C_cfg, n_target_draws), dtype=np.int64)
    hits_main_b = np.zeros(n_target_draws, dtype=np.int64)
    hits_main_r = np.zeros(n_target_draws, dtype=np.int64)

    hits_jok_cfgs = np.zeros((C_cfg, n_target_draws), dtype=np.int64) if has_joker else None
    hits_jok_b = np.zeros(n_target_draws, dtype=np.int64) if has_joker else None
    hits_jok_r = np.zeros(n_target_draws, dtype=np.int64) if has_joker else None

    log_u_draw_const = -math.log(float(math.comb(N, r) * (jm if has_joker else 1)))
    q_u_main = np.full(N, float(r) / float(N), dtype=np.float64)
    q_u_jok = np.full(jm or 1, 1.0 / float(jm or 1), dtype=np.float64)

    batch_sz = 16 if (has_joker and (jm or 1) >= 20) else (32 if has_joker else 64)
    num_batches = (K_eval + batch_sz - 1) // batch_sz
    draw_cursor = 0
    t_ops_sec = 0.0
    t_gpu_space_sec = 0.0

    for batch_idx, e_start in enumerate(range(0, K_eval, batch_sz)):
        e_end = min(e_start + batch_sz, K_eval)
        B_cur = e_end - e_start

        t1 = time.perf_counter()
        ops_batch: List[Dict[str, torch.Tensor]] = []
        packs_batch: List[Dict[str, torch.Tensor]] = []
        lw_cur_cb = torch.full((C_cfg, B_cur, len(EXPERT_GRID)), float("-inf"), dtype=torch.float64, device=dev)
        w_cur_cb = torch.zeros((C_cfg, B_cur, len(EXPERT_GRID)), dtype=torch.float64, device=dev)
        pi_cur_cb = torch.zeros((C_cfg, B_cur, N), dtype=torch.float64, device=dev)
        jp_cur_cb = torch.zeros((C_cfg, B_cur, jm or 1), dtype=torch.float64, device=dev) if has_joker else None

        for local_b in range(B_cur):
            idx_e = e_start + local_b
            s = warmup + idx_e
            oh_s, jh_s, met_s = slices[s]

            ops_s = forward_operators_from_state(state, space, meteo_raw_step=met_s, params=run_params)
            pack_s = compute_all_experts_step_pack(
                space,
                ops_s,
                oh_s.to(torch.float64),
                jh_s.to(torch.float64) if jh_s is not None else None,
                active_expert_mask=active_exp_union,
            )
            ops_batch.append(ops_s)
            packs_batch.append(pack_s)

            for c_i in range(C_cfg):
                lw_c = log_wealth_cfgs[c_i]
                lw_cur_cb[c_i, local_b] = lw_c
                fin = torch.isfinite(lw_c)
                m_max = lw_c[fin].max()
                w_c = torch.where(fin, torch.exp(lw_c - m_max), torch.zeros_like(lw_c))
                w_c = w_c / w_c.sum()
                w_cur_cb[c_i, local_b] = w_c
                pi_cur_cb[c_i, local_b] = (w_c.unsqueeze(1) * pack_s["pi_m"]).sum(dim=0)
                if has_joker and jp_cur_cb is not None and pack_s["joker_prob_m"] is not None:
                    jp_cur_cb[c_i, local_b] = (w_c.unsqueeze(1) * pack_s["joker_prob_m"]).sum(dim=0)

                # Raportul de verosimilitate al portofoliului pe pasul s
                act_m = w_c > 0.0
                log_port_lr = float(torch.logsumexp(torch.log(w_c[act_m]) + pack_s["step_log_lrs"][act_m], dim=0).item())
                m_draws_s = int(oh_s.shape[0])
                log_step_cfgs[c_i, idx_e] = float(m_draws_s) * log_u_draw_const + log_port_lr

                # Actualizare exactă avere W_m^(s+1) = W_m^(s) * L_m^(s)
                lw_next = torch.where(fin, lw_c + pack_s["step_log_lrs"], lw_c)
                log_wealth_cfgs[c_i] = lw_next

                # Înregistrăm ponderile post-pas și E_{s+1} = ∑_m W_m^(s+1) >= W_0 = 0.50
                m_max_n = float(lw_next[fin].max().item())
                exp_rel = torch.exp(lw_next[fin] - m_max_n)
                e_val_next = float(exp_rel.sum().item()) * math.exp(m_max_n)
                e_curve_cfgs[c_i, idx_e + 1] = e_val_next
                w_next = torch.where(fin, torch.exp(lw_next - m_max_n), torch.zeros_like(lw_next))
                w_next = w_next / w_next.sum()
                w_hist_cfgs[c_i, idx_e + 1] = w_next.detach().cpu().numpy()

            advance_one_step(state, space, oh_s, jh_s, met_s, params=run_params, update_portfolio=False)

        if dev.type == "cuda":
            torch.cuda.synchronize()
        t_ops_sec += time.perf_counter() - t1

        # Evaluare exactă pe GPU a biletului fundamental σ_α pe toate stările pentru întregul lot B_cur
        t2 = time.perf_counter()
        lz_batch = torch.stack([p["log_Z_m"] for p in packs_batch], dim=0)  # [B_cur, 8]
        bat_alpha = evaluate_batch_sigma_alpha_multi_cfg(
            space, ops_batch, lz_batch, w_cur_cb, pi_cur_cb, params=run_params, lw_configs_batch=lw_cur_cb
        )
        if dev.type == "cuda":
            torch.cuda.synchronize()
        t_gpu_space_sec += time.perf_counter() - t2

        sigma_alpha_cfgs[:, e_start:e_end, :] = bat_alpha["sigma_alpha"]
        alpha_lp_cfgs[:, e_start:e_end] = bat_alpha["alpha_log_prob"]
        if has_joker and joker_alpha_cfgs is not None and bat_alpha["joker_alpha"] is not None:
            joker_alpha_cfgs[:, e_start:e_end] = bat_alpha["joker_alpha"]

        pi_cur_np = pi_cur_cb.detach().cpu().numpy()  # [C_cfg, B_cur, N]
        jp_cur_np = jp_cur_cb.detach().cpu().numpy() if (has_joker and jp_cur_cb is not None) else None
        w_cur_np = w_cur_cb.detach().cpu().numpy()    # [C_cfg, B_cur, 8]

        # Scorare per extragere-țintă r_idx ∈ [offs[s], offs[s+1])
        for local_b in range(B_cur):
            idx_e = e_start + local_b
            s = warmup + idx_e
            a_dr, b_dr = int(offs_np[s]), int(offs_np[s + 1])

            wB_s = base_w_B[idx_e]
            wR_s = base_w_R[idx_e]
            log_er_B, q_B_main = cond_poisson_log_z_and_marginals(wB_s, r)
            log_er_R, q_R_main = cond_poisson_log_z_and_marginals(wR_s, r)
            t_B = set(int(x) for x in top_k_1based(wB_s, k).tolist())
            t_R = set(int(x) for x in top_k_1based(wR_s, k).tolist())

            if has_joker:
                jwB_s = base_jw_B[idx_e]
                jwR_s = base_jw_R[idx_e]
                j_B = int(top_k_1based(jwB_s, 1)[0])
                j_R = int(top_k_1based(jwR_s, 1)[0])

            # Marginale 1-bilă pe extragerea de mărime r pentru fiecare configurație
            q_cfgs_main = np.zeros((C_cfg, N), dtype=np.float64)
            t_alpha_sets = []
            for c_i in range(C_cfg):
                pi_s = pi_cur_np[c_i, local_b]
                if r == k:
                    q_cfgs_main[c_i] = pi_s
                else:
                    q_cfgs_main[c_i] = (float(r - k) + float(N - r) * pi_s) / float(N - k)
                t_alpha_sets.append(set(int(x) for x in bat_alpha["sigma_alpha"][c_i, local_b].tolist()))

            draw_lrs_np = packs_batch[local_b]["draw_log_lrs"].detach().cpu().numpy()  # [m_draws, 8]

            for u_pos, r_idx in enumerate(range(a_dr, b_dr)):
                d_balls = [int(x) for x in draws_np[r_idx].tolist()]
                d_set = set(d_balls)
                y_main = oh_np[r_idx]
                balls0 = [b_num - 1 for b_num in d_balls]
                d_jok = int(jok_np[r_idx]) if (has_joker and jok_np is not None) else None

                lp_u = log_u_draw_const
                lp_b = float(np.sum(np.log(wB_s[balls0])) - log_er_B)
                lp_r = float(np.sum(np.log(wR_s[balls0])) - log_er_R)

                br_u = float(np.sum((q_u_main - y_main) ** 2))
                br_b = float(np.sum((q_B_main - y_main) ** 2))
                br_r = float(np.sum((q_R_main - y_main) ** 2))

                hm_b = len(t_B & d_set)
                hm_r = len(t_R & d_set)

                if has_joker and joh_np is not None and d_jok is not None:
                    yj = joh_np[r_idx]
                    lp_b += float(math.log(jwB_s[d_jok - 1]))
                    lp_r += float(math.log(jwR_s[d_jok - 1]))
                    br_u += float(np.sum((q_u_jok - yj) ** 2))
                    br_b += float(np.sum((jwB_s - yj) ** 2))
                    br_r += float(np.sum((jwR_s - yj) ** 2))
                    assert hits_jok_b is not None and hits_jok_r is not None
                    hits_jok_b[draw_cursor] = int(j_B == d_jok)
                    hits_jok_r[draw_cursor] = int(j_R == d_jok)

                target_step_arr[draw_cursor] = s
                log_draw_u[draw_cursor] = lp_u
                log_draw_b[draw_cursor] = lp_b
                log_draw_r[draw_cursor] = lp_r
                brier_draw_u[draw_cursor] = br_u
                brier_draw_b[draw_cursor] = br_b
                brier_draw_r[draw_cursor] = br_r
                hits_main_b[draw_cursor] = hm_b
                hits_main_r[draw_cursor] = hm_r

                log_step_u[idx_e] += lp_u
                log_step_b[idx_e] += lp_b
                log_step_r[idx_e] += lp_r

                for c_i in range(C_cfg):
                    wc = w_cur_np[c_i, local_b]
                    act_c = wc > 0.0
                    l_terms = np.log(wc[act_c]) + draw_lrs_np[u_pos, act_c]
                    m_lt = float(np.max(l_terms))
                    lp_hs = lp_u + m_lt + math.log(float(np.sum(np.exp(l_terms - m_lt))))
                    br_hs = float(np.sum((q_cfgs_main[c_i] - y_main) ** 2))
                    hm_hs = len(t_alpha_sets[c_i] & d_set)

                    if has_joker and joh_np is not None and d_jok is not None and jp_cur_np is not None:
                        yj = joh_np[r_idx]
                        br_hs += float(np.sum((jp_cur_np[c_i, local_b] - yj) ** 2))
                        assert joker_alpha_cfgs is not None and hits_jok_cfgs is not None
                        j_a = int(joker_alpha_cfgs[c_i, idx_e])
                        hits_jok_cfgs[c_i, draw_cursor] = int(j_a == d_jok)

                    log_draw_cfgs[c_i, draw_cursor] = lp_hs
                    brier_draw_cfgs[c_i, draw_cursor] = br_hs
                    hits_main_cfgs[c_i, draw_cursor] = hm_hs

                draw_cursor += 1

        del ops_batch, packs_batch
        if verbose and ((batch_idx + 1) % 10 == 0 or (batch_idx + 1) == num_batches):
            e_last = e_curve_cfgs[-1, e_end]
            w0_last = w_hist_cfgs[-1, e_end, 0]
            print(
                f"  [{wf_in.game_code}] lot {batch_idx + 1}/{num_batches} ({e_end}/{K_eval} pași) | "
                f"ops={t_ops_sec:.2f}s space={t_gpu_space_sec:.2f}s | E_s={e_last:.6f} w_0={w0_last:.4f}",
                flush=True,
            )

    # 3. Calcul stări terminale post-arhivă (multiplet Jastrow α, β, γ + nucleu determinist) și rapoarte per config
    expected_u_hits = (float(k * r) / float(N)) + ((1.0 / float(jm)) if has_joker and jm is not None else 0.0)
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

    hits_tot_b = hits_main_b + (hits_jok_b if (has_joker and hits_jok_b is not None) else 0)
    hits_tot_r = hits_main_r + (hits_jok_r if (has_joker and hits_jok_r is not None) else 0)

    config_reports: Dict[str, Dict[str, Any]] = {}
    terminal_states_obj: Dict[str, HSV4State] = {}

    for c_i, (cfg_key, cfg_label, eo1, eo2, eo4) in enumerate(configs):
        hits_tot_hs = hits_main_cfgs[c_i] + (
            hits_jok_cfgs[c_i] if (has_joker and hits_jok_cfgs is not None) else 0
        )

        win_total = summarize_window_metrics(
            mask_all_s, mask_all_d, expected_u_hits,
            hits_tot_hs, hits_tot_b, hits_tot_r,
            log_step_cfgs[c_i], log_step_u, log_step_b, log_step_r,
            brier_draw_cfgs[c_i], brier_draw_u, brier_draw_b, brier_draw_r,
        )
        win_h1 = summarize_window_metrics(
            mask_h1_s, mask_h1_d, expected_u_hits,
            hits_tot_hs, hits_tot_b, hits_tot_r,
            log_step_cfgs[c_i], log_step_u, log_step_b, log_step_r,
            brier_draw_cfgs[c_i], brier_draw_u, brier_draw_b, brier_draw_r,
        )
        win_h2 = summarize_window_metrics(
            mask_h2_s, mask_h2_d, expected_u_hits,
            hits_tot_hs, hits_tot_b, hits_tot_r,
            log_step_cfgs[c_i], log_step_u, log_step_b, log_step_r,
            brier_draw_cfgs[c_i], brier_draw_u, brier_draw_b, brier_draw_r,
        )
        win_last100 = summarize_window_metrics(
            mask_last100_s, mask_last100_d, expected_u_hits,
            hits_tot_hs, hits_tot_b, hits_tot_r,
            log_step_cfgs[c_i], log_step_u, log_step_b, log_step_r,
            brier_draw_cfgs[c_i], brier_draw_u, brier_draw_b, brier_draw_r,
        )

        e_curve_c = e_curve_cfgs[c_i]  # lungime K_eval + 1 (inclusiv E_100 = 1.0)
        gates, gates_passed = evaluate_gates_g1_g6(win_total, win_h1, win_h2, win_last100, e_curve_c[1:])

        categories = compute_category_distribution(
            N=N,
            r_draw=r,
            k_ticket=k,
            joker_m=jm if has_joker else None,
            main_hits_hsv4=hits_main_cfgs[c_i],
            main_hits_b=hits_main_b,
            main_hits_r=hits_main_r,
            joker_hits_hsv4=hits_jok_cfgs[c_i] if (has_joker and hits_jok_cfgs is not None) else None,
            joker_hits_b=hits_jok_b if has_joker else None,
            joker_hits_r=hits_jok_r if has_joker else None,
        )

        # Evoluția maselor Bayesiene (w_0, w_O1, w_O2, w_O4)
        w_hist_c = w_hist_cfgs[c_i]  # [K_eval + 1, 8]
        ch_init = decompose_channel_masses(w_hist_c[0])
        ch_mid = decompose_channel_masses(w_hist_c[half_k])
        ch_final = decompose_channel_masses(w_hist_c[-1])
        ch_mean = decompose_channel_masses(w_hist_c[1:].mean(axis=0))

        bayesian_evolution = {
            "prior_initial": ch_init,
            "midpoint_half1": ch_mid,
            "mean_over_walkforward": ch_mean,
            "posterior_final": ch_final,
            "expert_weights_initial": {EXPERT_GRID[m][1]: round(float(w_hist_c[0, m]), 6) for m in range(8)},
            "expert_weights_final": {EXPERT_GRID[m][1]: round(float(w_hist_c[-1, m]), 6) for m in range(8)},
            "w0_min": round(float(np.min(w_hist_c[:, 0])), 6),
            "w0_max": round(float(np.max(w_hist_c[:, 0])), 6),
            "w_O2_contracted_vs_prior": bool(ch_final["w_O2"] <= ch_init["w_O2"] + 1e-12),
        }

        min_e_all = float(np.min(e_curve_c))
        final_e = float(e_curve_c[-1])
        if min_e_all < 0.50 - 1e-12:
            raise RuntimeError(f"Încălcare garanție algebrică E_s >= 0.50 pe {wf_in.game_code}/{cfg_key}: {min_e_all}")

        # Construim starea terminală exactă a configurației la pasul S_total
        st_cfg = state.clone()
        st_cfg.enable_o1 = bool(eo1)
        st_cfg.enable_o2 = bool(eo2)
        st_cfg.enable_o4 = bool(eo4)
        st_cfg.log_wealth = log_wealth_cfgs[c_i].clone()
        st_cfg.portfolio_steps = int(K_eval)
        terminal_states_obj[cfg_key] = st_cfg

        post_archive_state = None
        if compute_terminal_states:
            ops_term = _sanitize_subnormal_ops_for_core(
                forward_operators_from_state(st_cfg, space, meteo_raw_step=meteo_t[-1], params=run_params)
            )
            ev_term = evaluate_portfolio_full_space(space, ops_term, params=run_params)
            post_archive_state = {
                "epistemic_notice": (
                    "Minime de energie / stări statistice condiționate de istoric (multiplet ortogonal Coulomb–Jastrow), "
                    "NU predicții cu avantaj demonstrat. positive_claims_allowed=false."
                ),
                "step_index": int(S_total),
                "last_observed_date": wf_in.step_dates[-1],
                "variants_jastrow_multiplet": ev_term["variants"],
                "deterministic_core": ev_term["deterministic_core"],
                "distinct_balls_covered": int(ev_term["distinct_covered"]),
                "det_G3": round(float(ev_term["det_G3"]), 6),
                "prob_sum_exact": round(float(ev_term["prob_sum_exact"]), 12),
                "pi_inclusion": [round(float(x), 8) for x in ev_term["pi_inclusion"].detach().cpu().tolist()],
                "joker_prob": (
                    [round(float(x), 8) for x in ev_term["joker_prob"].detach().cpu().tolist()]
                    if ev_term["joker_prob"] is not None
                    else None
                ),
                "bosonic_eigenvalues_raw": [round(float(x), 6) for x in ops_term["lam_top"].detach().cpu().tolist()],
                "bosonic_eigenvalues_attenuated": [
                    round(float(x), 6) for x in ops_term["lam_tilde_pos"].detach().cpu().tolist()
                ],
                "jennrich_eigenvalues": [round(float(x), 6) for x in ops_term["jen_vals"].detach().cpu().tolist()],
            }

        npz_info = None
        if save_npz_dir is not None:
            save_npz_dir = Path(save_npz_dir)
            save_npz_dir.mkdir(parents=True, exist_ok=True)
            pref = npz_prefix if npz_prefix is not None else wf_in.game_code
            npz_name = f"{pref}_{cfg_key.lower()}_walkforward.npz"
            npz_path = save_npz_dir / npz_name
            npz_payload: Dict[str, Any] = {
                "eval_steps": eval_steps,
                "eval_dates": np.array(wf_in.step_dates[warmup:], dtype="U10"),
                "E_curve": e_curve_c[1:],
                "log10_E_curve": np.log10(np.maximum(e_curve_c[1:], 1e-300)),
                "w_portfolio_curve": w_hist_c[1:],
                "sigma_alpha": sigma_alpha_cfgs[c_i],
                "alpha_log_prob": alpha_lp_cfgs[c_i],
                "log_step_hsv4": log_step_cfgs[c_i],
                "log_step_u": log_step_u,
                "log_step_b": log_step_b,
                "log_step_r": log_step_r,
                "target_step": target_step_arr,
                "hits_main_hsv4": hits_main_cfgs[c_i],
                "hits_main_b": hits_main_b,
                "hits_main_r": hits_main_r,
                "brier_draw_hsv4": brier_draw_cfgs[c_i],
                "brier_draw_u": brier_draw_u,
                "brier_draw_b": brier_draw_b,
                "brier_draw_r": brier_draw_r,
            }
            if has_joker and joker_alpha_cfgs is not None and hits_jok_cfgs is not None:
                npz_payload["joker_alpha"] = joker_alpha_cfgs[c_i]
                npz_payload["hits_joker_hsv4"] = hits_jok_cfgs[c_i]
                npz_payload["hits_joker_b"] = hits_jok_b
                npz_payload["hits_joker_r"] = hits_jok_r
            np.savez_compressed(npz_path, **npz_payload)
            npz_info = {
                "file": npz_name,
                "sha256": sha256_file(npz_path),
                "bytes": npz_path.stat().st_size,
            }

        # Puncte eșantionate doar pt. sumarul JSON lizibil (curba completă pas-cu-pas este în .npz!)
        sample_idx = np.unique(np.linspace(0, K_eval, num=min(25, K_eval + 1), dtype=int))
        e_checkpoints = [
            {
                "eval_offset": int(ix),
                "step": int(warmup + ix),
                "date": wf_in.step_dates[min(warmup + ix - 1, S_total - 1)] if ix > 0 else wf_in.step_dates[warmup - 1],
                "E_s": round(float(e_curve_c[ix]), 6),
                "w_0": round(float(w_hist_c[ix, 0]), 6),
                "w_O1": round(float(w_hist_c[ix, 1] + w_hist_c[ix, 2] + w_hist_c[ix, 3] + 0.5 * w_hist_c[ix, 5]), 6),
                "w_O2": round(float(w_hist_c[ix, 4] + 0.5 * w_hist_c[ix, 5]), 6),
                "w_O4": round(float(w_hist_c[ix, 6] + w_hist_c[ix, 7]), 6),
            }
            for ix in sample_idx
        ]

        config_reports[cfg_key] = {
            "config_key": cfg_key,
            "label": cfg_label,
            "channels_enabled": {"O1": bool(eo1), "O2": bool(eo2), "O3_portfolio": True, "O4": bool(eo4)},
            "verdict_gates": f"{gates_passed} / 6",
            "gates_passed": int(gates_passed),
            "gates_total": 6,
            "status": "HSV4_PROMOTED_EXPLORATORY" if gates_passed == 6 else "HSV4_NO_PROMOTION_EXPLORATORY",
            "positive_claims_allowed": False,
            "gates": gates,
            "windows": {
                "total": win_total,
                "half1": win_h1,
                "half2": win_h2,
                "last100": win_last100,
            },
            "categories": categories,
            "martingale_trajectory": {
                "E_initial": 1.0,
                "E_S_final": round(final_e, 8),
                "log10_E_S": round(math.log10(max(final_e, 1e-300)), 8),
                "min_E_s": round(min_e_all, 8),
                "max_E_s": round(float(np.max(e_curve_c)), 8),
                "guarantee_E_ge_050_verified": bool(min_e_all >= 0.50 - 1e-12),
                "checkpoints": e_checkpoints,
            },
            "bayesian_masses": bayesian_evolution,
            "post_archive_state": post_archive_state,
            "trajectory_npz": npz_info,
        }

    peak_vram_mib = round(torch.cuda.max_memory_allocated() / (1024.0 ** 2), 2) if dev.type == "cuda" else 0.0
    total_sec = round(time.perf_counter() - t0, 3)

    return {
        "game_code": wf_in.game_code,
        "game_name": wf_in.game_name,
        "game_params": {
            "N": N,
            "r_draw": r,
            "k_ticket": k,
            "joker_m": jm,
            "state_space_size": int(space.total_states),
            "draw_space_size": int(math.comb(N, r) * (jm if has_joker and jm is not None else 1)),
            "exact_full_space_gpu": bool(space.total_base_states <= 45_000_000),
            "exact_gh_ek_partition": True,
        },
        "archive": {
            **wf_in.source_meta,
            "n_draws_total": n_draws_total,
            "n_steps_total": S_total,
            "warmup_steps": int(warmup),
            "evaluated_steps": K_eval,
            "evaluated_target_draws": n_target_draws,
            "first_date": wf_in.step_dates[0],
            "first_eval_date": wf_in.step_dates[warmup],
            "last_date": wf_in.step_dates[-1],
            "double_draw_days": int(np.sum((offs_np[1:] - offs_np[:-1]) > 1)),
            "subsampling_used": False,
        },
        "configs": config_reports,
        "_terminal_states": terminal_states_obj,
        "timings": {
            "operators_and_gh_sec": round(t_ops_sec, 3),
            "gpu_state_space_sec": round(t_gpu_space_sec, 3),
            "total_sec": total_sec,
            "ms_per_eval_step": round(1000.0 * total_sec / float(K_eval), 3),
        },
        "device": torch.cuda.get_device_name(0) if dev.type == "cuda" else "CPU",
        "peak_vram_mib": peak_vram_mib,
    }


# ============================================================================
# 6. CACHE INCREMENTAL VERIFICAT SHA-256 ÎN hs_v4/cache/ PENTRU RO LIVE
# ============================================================================

def _serialize_hsv4_state(state: HSV4State) -> Dict[str, Any]:
    cp = lambda t: None if t is None else t.detach().cpu().clone()
    return {
        "step_idx": int(state.step_idx),
        "n_eff_bos": float(state.n_eff_bos),
        "m1_bos": cp(state.m1_bos),
        "m2_bos": cp(state.m2_bos),
        "m3_dist": cp(state.m3_dist),
        "ema_int": cp(state.ema_int),
        "meteo_count": int(state.meteo_count),
        "meteo_mean": cp(state.meteo_mean),
        "meteo_m2": cp(state.meteo_m2),
        "aero_gram": cp(state.aero_gram),
        "aero_rhs": cp(state.aero_rhs),
        "prev_bar_x": cp(state.prev_bar_x),
        "rng_gram": cp(state.rng_gram),
        "rng_rhs": cp(state.rng_rhs),
        "log_wealth": cp(state.log_wealth),
        "portfolio_steps": int(state.portfolio_steps),
        "enable_o1": bool(state.enable_o1),
        "enable_o2": bool(state.enable_o2),
        "enable_o4": bool(state.enable_o4),
        "ema_joker_int": cp(state.ema_joker_int),
        "m1_joker": cp(state.m1_joker),
        "cross_m2": cp(state.cross_m2),
        "aero_rhs_joker": cp(state.aero_rhs_joker),
        "prev_bar_j": cp(state.prev_bar_j),
        "rng_gram_j": cp(state.rng_gram_j),
        "rng_rhs_j": cp(state.rng_rhs_j),
    }


def _deserialize_hsv4_state(d: Dict[str, Any], device: torch.device) -> HSV4State:
    mv = lambda t: None if t is None else t.to(device=device, dtype=torch.float64)
    return HSV4State(
        step_idx=int(d["step_idx"]),
        n_eff_bos=float(d["n_eff_bos"]),
        m1_bos=mv(d["m1_bos"]),
        m2_bos=mv(d["m2_bos"]),
        m3_dist=mv(d["m3_dist"]),
        ema_int=mv(d["ema_int"]),
        meteo_count=int(d["meteo_count"]),
        meteo_mean=mv(d["meteo_mean"]),
        meteo_m2=mv(d["meteo_m2"]),
        aero_gram=mv(d["aero_gram"]),
        aero_rhs=mv(d["aero_rhs"]),
        prev_bar_x=mv(d["prev_bar_x"]),
        rng_gram=mv(d["rng_gram"]),
        rng_rhs=mv(d["rng_rhs"]),
        log_wealth=mv(d["log_wealth"]),
        portfolio_steps=int(d["portfolio_steps"]),
        enable_o1=bool(d["enable_o1"]),
        enable_o2=bool(d["enable_o2"]),
        enable_o4=bool(d["enable_o4"]),
        ema_joker_int=mv(d["ema_joker_int"]),
        m1_joker=mv(d["m1_joker"]),
        cross_m2=mv(d["cross_m2"]),
        aero_rhs_joker=mv(d["aero_rhs_joker"]),
        prev_bar_j=mv(d["prev_bar_j"]),
        rng_gram_j=mv(d["rng_gram_j"]),
        rng_rhs_j=mv(d["rng_rhs_j"]),
    )


def _save_verified_checkpoint(cache_dir: Path, ckpt_name: str, payload: Dict[str, Any]) -> Tuple[Path, str]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    pt_path = cache_dir / ckpt_name
    sha_path = cache_dir / f"{ckpt_name}.sha256"

    fd, tmp_pt = tempfile.mkstemp(prefix=f".{ckpt_name}.", dir=str(cache_dir))
    os.close(fd)
    try:
        torch.save(payload, tmp_pt)
        raw_bytes = Path(tmp_pt).read_bytes()
        digest = sha256_bytes(raw_bytes)
        os.replace(tmp_pt, pt_path)
    finally:
        if os.path.exists(tmp_pt):
            try:
                os.unlink(tmp_pt)
            except OSError:
                pass

    atomic_write_bytes(sha_path, f"{digest}  {ckpt_name}\n".encode("utf-8"))

    # Actualizare CACHE_MANIFEST.json în hs_v4/cache/
    man_path = cache_dir / "CACHE_MANIFEST.json"
    man_obj: Dict[str, Any] = {"protocol": "HSV4-P1", "entries": {}, "positive_claims_allowed": False}
    if man_path.is_file():
        try:
            loaded = json.loads(man_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("entries"), dict):
                man_obj = loaded
        except ValueError:
            pass
    man_obj["entries"][ckpt_name] = {
        "sha256": digest,
        "bytes": pt_path.stat().st_size,
        "mode": payload.get("mode"),
        "config_key": payload.get("config_key"),
        "src_key": payload.get("src_key"),
        "step_idx": payload.get("step_idx"),
        "n_draws": payload.get("n_draws"),
        "last_date": payload.get("last_date"),
        "saved_utc": payload.get("saved_utc"),
    }
    man_obj["updated_utc"] = utc_now()
    atomic_write_json(man_path, man_obj)
    return pt_path, digest


def _load_verified_checkpoint(pt_path: Path) -> Dict[str, Any]:
    """Verifică obligatoriu SHA-256 al fișierului .pt ÎNAINTE de torch.load!"""
    pt_path = Path(pt_path)
    sha_path = pt_path.parent / f"{pt_path.name}.sha256"
    if not (pt_path.is_file() and sha_path.is_file()):
        raise FileNotFoundError(f"Checkpoint sau sigiliu .sha256 absent: {pt_path}")
    expected_sha = sha_path.read_text(encoding="utf-8").strip().split()[0]
    actual_sha = sha256_file(pt_path)
    if actual_sha != expected_sha:
        raise RuntimeError(f"Integritate cache HS-V4 eșuată pentru {pt_path.name}: {actual_sha} != {expected_sha}")
    man_path = pt_path.parent / "CACHE_MANIFEST.json"
    if man_path.is_file():
        man = json.loads(man_path.read_text(encoding="utf-8"))
        rec = man.get("entries", {}).get(pt_path.name)
        if rec is not None and rec.get("sha256") != actual_sha:
            raise RuntimeError(f"Neconcordanță CACHE_MANIFEST.json pentru {pt_path.name}")
    return torch.load(pt_path, map_location="cpu", weights_only=False)


def _resolve_live_source_and_key(mode: str, live_root: Optional[Path] = None) -> Tuple[Path, str, Dict[str, Any]]:
    if live_root is None:
        resolved_path, prov = PM.resolve_live(mode)
        ui_mod = sys.modules.get("tu3.ui_tu3")
        if ui_mod is not None and hasattr(ui_mod, "live_key"):
            return resolved_path, str(ui_mod.live_key(mode)), prov
        return resolved_path, str(prov["file_sha256"]), prov
    resolved_path, prov = PM.resolve_live(mode, live_root=Path(live_root))
    return resolved_path, str(prov["file_sha256"]), prov


def _dataset_prefix_digests(ds: PM.GameDataset, n_steps: int, n_draws: int) -> Tuple[str, str]:
    dates_sha = sha256_bytes(json.dumps(ds.step_dates[:n_steps]).encode("utf-8"))
    dr_bytes = ds.draws[:n_draws].detach().cpu().numpy().astype(np.int64).tobytes()
    jk_bytes = (
        ds.joker[:n_draws].detach().cpu().numpy().astype(np.int64).tobytes()
        if ds.joker is not None
        else b""
    )
    draws_sha = sha256_bytes(dr_bytes + jk_bytes)
    return dates_sha, draws_sha


def _find_verified_predecessor(
    mode: str,
    config_key: str,
    ds: PM.GameDataset,
    cache_dir: Path,
) -> Optional[Dict[str, Any]]:
    if not cache_dir.is_dir():
        return None
    best_ck = None
    best_step = -1
    offs_cpu = ds.step_offsets.detach().cpu().tolist()
    for pt_file in sorted(cache_dir.glob(f"state_{mode}_{config_key}_*.pt")):
        try:
            ck = _load_verified_checkpoint(pt_file)
        except Exception:
            continue
        if ck.get("mode") != mode or ck.get("config_key") != config_key:
            continue
        old_s = int(ck.get("step_idx", -1))
        old_nd = int(ck.get("n_draws", -1))
        if not (0 < old_s < ds.n_steps and 0 < old_nd < ds.n_draws):
            continue
        if int(offs_cpu[old_s]) != old_nd:
            continue
        d_sha, dr_sha = _dataset_prefix_digests(ds, old_s, old_nd)
        if d_sha == ck.get("step_dates_sha256") and dr_sha == ck.get("draws_prefix_sha256"):
            if old_s > best_step:
                best_step = old_s
                best_ck = ck
    return best_ck


@torch.no_grad()
def get_or_advance_live(
    mode: str,
    config_key: str = "Full_HSV4",
    live_root: Optional[Path] = None,
    deriv_root: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    warmup: int = WARMUP_STEPS,
    params: HSV4Params = DEFAULT_PARAMS,
    force_rebuild: bool = False,
) -> Dict[str, Any]:
    """Hook incremental real-time verificat SHA-256 peste CURRENT_LIVE.json pentru RO (649, 540, joker):
      1. Pe cache-hit verifică SHA-256 al checkpoint-ului .pt și returnează instantaneu (< 0.02s).
      2. La extrageri noi în CURRENT_LIVE.json, încarcă predecesorul verificat SHA-256, decontează cauzal
         doar pașii noi ΔS, calculează noul multiplet Jastrow (α, β, γ), salvează atomic noul checkpoint + .sha256
         și eliberează VRAM-ul GPU.
    """
    if mode not in RO_GAME_CONFIGS:
        raise ValueError(f"Mod necunoscut {mode!r}; permise: {sorted(RO_GAME_CONFIGS)}")
    cfg_map = {k_c: (lbl, o1, o2, o4) for k_c, lbl, o1, o2, o4 in ABLATION_CONFIGS}
    if config_key not in cfg_map:
        raise ValueError(f"Configurație necunoscută {config_key!r}; permise: {sorted(cfg_map)}")

    t0 = time.perf_counter()
    c_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR_DEFAULT
    c_dir.mkdir(parents=True, exist_ok=True)

    _, src_key, _ = _resolve_live_source_and_key(mode, live_root=live_root)
    ckpt_name = f"state_{mode}_{config_key}_{src_key[:12]}.pt"
    ckpt_path = c_dir / ckpt_name

    if not force_rebuild and ckpt_path.is_file() and (c_dir / f"{ckpt_name}.sha256").is_file():
        ck = _load_verified_checkpoint(ckpt_path)
        if ck.get("src_key") == src_key and ck.get("mode") == mode and ck.get("config_key") == config_key:
            sha_hex = (c_dir / f"{ckpt_name}.sha256").read_text(encoding="utf-8").split()[0]
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            vram_after = int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else 0
            return {
                **{k_p: v_p for k_p, v_p in ck.items() if k_p != "state"},
                "checkpoint_path": str(ckpt_path),
                "checkpoint_sha256": sha_hex,
                "cache_hit": True,
                "delta_steps": 0,
                "settled_new_draws": [],
                "elapsed_sec": round(time.perf_counter() - t0, 6),
                "vram_allocated_after_bytes": vram_after,
            }

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ds = None
    space = None
    state = None
    ops_term = None
    ev_term = None
    settled_new: List[Dict[str, Any]] = []

    try:
        lbl, eo1, eo2, eo4 = cfg_map[config_key]
        _, N, r, k, jm = RO_GAME_CONFIGS[mode]
        ds = PM.build_game_dataset(
            mode,
            "live",
            device=dev,
            live_root=Path(live_root) if live_root is not None else PM.LIVE,
            deriv_root=Path(deriv_root) if deriv_root is not None else PM.DERIV,
        )
        meteo_np = load_meteo_features_for_dates(ds.step_dates)
        meteo_t = torch.as_tensor(meteo_np, dtype=torch.float64, device=dev)
        slices = extract_step_slices(ds.onehot, ds.step_offsets, ds.joker_onehot, meteo_t)
        space = HSV4Space(N=N, r_draw=r, k_ticket=k, device=dev, joker_m=jm, gh_order=params.gh_order)

        pred_ck = None if force_rebuild else _find_verified_predecessor(mode, config_key, ds, c_dir)
        prior_history: List[Dict[str, Any]] = []

        if pred_ck is not None:
            s_start = int(pred_ck["step_idx"])
            delta_steps = ds.n_steps - s_start
            state = _deserialize_hsv4_state(pred_ck["state"], dev)
            prior_history = list(pred_ck.get("settlement_history", []))
            offs_cpu = ds.step_offsets.detach().cpu().tolist()
            draws_cpu = ds.draws.detach().cpu().tolist()
            jok_cpu = ds.joker.detach().cpu().tolist() if ds.joker is not None else None

            for s in range(s_start, ds.n_steps):
                oh_s, jh_s, met_s = slices[s]
                if s >= warmup:
                    ops_s = _sanitize_subnormal_ops_for_core(
                        forward_operators_from_state(state, space, meteo_raw_step=met_s, params=params)
                    )
                    ev_s = evaluate_portfolio_full_space(space, ops_s, params=params)
                    t_alpha = set(ev_s["variants"][0]["ticket"])
                    j_alpha = ev_s["variants"][0].get("joker")
                else:
                    t_alpha = set()
                    j_alpha = None

                _, step_info = advance_one_step(
                    state, space, oh_s, jh_s, met_s, params=params, update_portfolio=True, min_wealth_step=warmup
                )
                a_i, b_i = int(offs_cpu[s]), int(offs_cpu[s + 1])
                for r_idx in range(a_i, b_i):
                    d_balls = draws_cpu[r_idx]
                    rec_settle: Dict[str, Any] = {
                        "step": int(s),
                        "draw_key": ds.keys[r_idx],
                        "draw_date": ds.dates[r_idx],
                        "numbers": d_balls,
                        "alpha_ticket_pre_draw": sorted(t_alpha),
                        "main_hits": len(t_alpha & set(d_balls)) if t_alpha else 0,
                        "log_port_lr_step": round(float(step_info["log_port_lr"]), 6),
                        "E_after_step": round(get_cumulative_e_value(state), 6),
                    }
                    if jok_cpu is not None:
                        rec_settle["joker"] = int(jok_cpu[r_idx])
                        rec_settle["alpha_joker_pre_draw"] = j_alpha
                        rec_settle["joker_hit"] = int(j_alpha == int(jok_cpu[r_idx])) if j_alpha is not None else 0
                    settled_new.append(rec_settle)
        else:
            delta_steps = ds.n_steps
            state = init_state(space, params=params, enable_o1=eo1, enable_o2=eo2, enable_o4=eo4)
            advance_steps(state, space, slices, params=params, update_portfolio=True, min_wealth_step=warmup)

        ops_term = _sanitize_subnormal_ops_for_core(
            forward_operators_from_state(state, space, meteo_raw_step=meteo_t[-1], params=params)
        )
        ev_term = evaluate_portfolio_full_space(space, ops_term, params=params)
        w_vec = get_portfolio_weights(state).detach().cpu().numpy()
        e_val = get_cumulative_e_value(state)
        d_sha, dr_sha = _dataset_prefix_digests(ds, ds.n_steps, ds.n_draws)

        payload: Dict[str, Any] = {
            "protocol": "HSV4-P1",
            "mode": mode,
            "config_key": config_key,
            "config_label": lbl,
            "src_key": src_key,
            "step_idx": int(ds.n_steps),
            "n_draws": int(ds.n_draws),
            "last_date": ds.step_dates[-1] if ds.step_dates else None,
            "step_dates_sha256": d_sha,
            "draws_prefix_sha256": dr_sha,
            "state": _serialize_hsv4_state(state),
            "E_S": float(e_val),
            "log10_E_S": math.log10(max(e_val, 1e-300)),
            "channel_masses": decompose_channel_masses(w_vec),
            "expert_weights": {EXPERT_GRID[m][1]: float(w_vec[m]) for m in range(len(EXPERT_GRID))},
            "variants": ev_term["variants"],
            "deterministic_core": ev_term["deterministic_core"],
            "distinct_covered": int(ev_term["distinct_covered"]),
            "det_G3": float(ev_term["det_G3"]),
            "prob_sum_exact": float(ev_term["prob_sum_exact"]),
            "pi_inclusion": ev_term["pi_inclusion"].detach().cpu().tolist(),
            "pi_prob": ev_term["pi_prob"].detach().cpu().tolist(),
            "joker_prob": ev_term["joker_prob"].detach().cpu().tolist() if ev_term["joker_prob"] is not None else None,
            "telemetry": {
                "bosonic_lam_raw": ops_term["lam_top"].detach().cpu().tolist(),
                "bosonic_lam_attenuated": ops_term["lam_tilde_pos"].detach().cpu().tolist(),
                "jennrich_vals": ops_term["jen_vals"].detach().cpu().tolist(),
                "z_meteo_last": ops_term["z_met"].detach().cpu().tolist(),
            },
            "settlement_history": prior_history + settled_new,
            "saved_utc": utc_now(),
            "positive_claims_allowed": False,
        }
        pt_saved, sha_hex = _save_verified_checkpoint(c_dir, ckpt_name, payload)
    finally:
        del ds, space, state, ops_term, ev_term
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    vram_after = int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else 0
    return {
        **{k_p: v_p for k_p, v_p in payload.items() if k_p != "state"},
        "checkpoint_path": str(pt_saved),
        "checkpoint_sha256": sha_hex,
        "cache_hit": False,
        "delta_steps": int(delta_steps),
        "settled_new_draws": settled_new,
        "elapsed_sec": round(time.perf_counter() - t0, 6),
        "vram_allocated_after_bytes": vram_after,
    }


def save_ro_checkpoints_from_walkforward(
    mode: str,
    ds: PM.GameDataset,
    src_key: str,
    wf_result: Dict[str, Any],
    cache_dir: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """Salvează direct în hs_v4/cache/ checkpoint-urile verificate SHA-256 ale celor 4 configurații
    rezultate la finalul walk-forward-ului RO (fără dublarea calculului).
    """
    c_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR_DEFAULT
    d_sha, dr_sha = _dataset_prefix_digests(ds, ds.n_steps, ds.n_draws)
    saved_info: Dict[str, Dict[str, Any]] = {}

    meteo_np = load_meteo_features_for_dates([ds.step_dates[-1]])
    met_last = torch.as_tensor(meteo_np[0], dtype=torch.float64, device=ds.onehot.device)
    _, N, r, k, jm = RO_GAME_CONFIGS[mode]
    space = HSV4Space(N=N, r_draw=r, k_ticket=k, device=ds.onehot.device, joker_m=jm)

    for cfg_key, cfg_rep in wf_result["configs"].items():
        st_cfg: HSV4State = wf_result["_terminal_states"][cfg_key]
        ops_term = forward_operators_from_state(st_cfg, space, meteo_raw_step=met_last)
        post_st = cfg_rep["post_archive_state"]
        w_vec = get_portfolio_weights(st_cfg).detach().cpu().numpy()
        e_val = get_cumulative_e_value(st_cfg)
        ckpt_name = f"state_{mode}_{cfg_key}_{src_key[:12]}.pt"
        payload: Dict[str, Any] = {
            "protocol": "HSV4-P1",
            "mode": mode,
            "config_key": cfg_key,
            "config_label": cfg_rep["label"],
            "src_key": src_key,
            "step_idx": int(ds.n_steps),
            "n_draws": int(ds.n_draws),
            "last_date": ds.step_dates[-1],
            "step_dates_sha256": d_sha,
            "draws_prefix_sha256": dr_sha,
            "state": _serialize_hsv4_state(st_cfg),
            "E_S": float(e_val),
            "log10_E_S": math.log10(max(e_val, 1e-300)),
            "channel_masses": decompose_channel_masses(w_vec),
            "expert_weights": {EXPERT_GRID[m][1]: float(w_vec[m]) for m in range(len(EXPERT_GRID))},
            "variants": post_st["variants_jastrow_multiplet"],
            "deterministic_core": post_st["deterministic_core"],
            "distinct_covered": int(post_st["distinct_balls_covered"]),
            "det_G3": float(post_st["det_G3"]),
            "prob_sum_exact": float(post_st["prob_sum_exact"]),
            "pi_inclusion": post_st["pi_inclusion"],
            "pi_prob": [x / float(k) for x in post_st["pi_inclusion"]],
            "joker_prob": post_st["joker_prob"],
            "telemetry": {
                "bosonic_lam_raw": ops_term["lam_top"].detach().cpu().tolist(),
                "bosonic_lam_attenuated": ops_term["lam_tilde_pos"].detach().cpu().tolist(),
                "jennrich_vals": ops_term["jen_vals"].detach().cpu().tolist(),
                "z_meteo_last": ops_term["z_met"].detach().cpu().tolist(),
            },
            "settlement_history": [],
            "saved_utc": utc_now(),
            "positive_claims_allowed": False,
        }
        pt_p, sha_hex = _save_verified_checkpoint(c_dir, ckpt_name, payload)
        saved_info[cfg_key] = {"file": pt_p.name, "sha256": sha_hex, "bytes": pt_p.stat().st_size}

    del space
    return saved_info


def _write_temp_live_sandbox(live_root: Path, version_tag: str, lines_by_mode: Dict[str, List[str]]) -> None:
    vdir_rel = f"versiuni/{version_tag}"
    vdir = live_root / vdir_rel
    vdir.mkdir(parents=True, exist_ok=True)
    games_man: Dict[str, Any] = {}
    games_ptr: Dict[str, Any] = {}

    for m, (_, _, r_m, _, _) in RO_GAME_CONFIGS.items():
        lines = lines_by_mode[m]
        p = vdir / f"extrageri_{m}.jsonl"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        f_sha = sha256_file(p)
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
    man_sha = sha256_bytes(man_bytes)
    ptr_obj = {
        "updated_utc": utc_now(),
        "run_id": f"hsv4_regtest_{version_tag}",
        "database_sha256": man_sha,
        "version_dir": vdir_rel,
        "manifest_sha256": man_sha,
        "games": games_ptr,
    }
    (live_root / "CURRENT_LIVE.json").write_text(
        json.dumps(ptr_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def verify_incremental_cache_ro(modes: Sequence[str] = ("649", "540", "joker")) -> Dict[str, Any]:
    """Verifică într-un sandbox temporar (read-only față de tu3/date/live) că:
      - avansarea incrementală S-3 -> S prin get_or_advance_live == rularea 0 -> S (< 1e-12);
      - integritatea SHA-256 din hs_v4/cache/ blochează orice corupere și servește cache-hit instantaneu.
    """
    raw_lines_full: Dict[str, List[str]] = {}
    lines_s3: Dict[str, List[str]] = {}
    for m in modes:
        src_p, _ = PM.resolve_live(m)
        raw_lines_full[m] = [ln for ln in src_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        ds_m = PM.build_game_dataset(m, "live", device="cpu")
        c3 = ds_m.step_dates[ds_m.n_steps - 3]
        lines_s3[m] = [ln for ln in raw_lines_full[m] if json.loads(ln)["draw_date"] < c3]

    out_modes: Dict[str, Any] = {}
    all_ok = True
    with tempfile.TemporaryDirectory(prefix="hsv4_inc_reg_") as tmp_d:
        tmp_root = Path(tmp_d)
        live_root = tmp_root / "live"
        deriv_root = tmp_root / "derivat"
        cache_inc = tmp_root / "cache_inc"
        cache_ref = tmp_root / "cache_ref"

        _write_temp_live_sandbox(live_root, "v_full", raw_lines_full)
        refs = {
            m: get_or_advance_live(m, live_root=live_root, deriv_root=deriv_root, cache_dir=cache_ref, force_rebuild=True)
            for m in modes
        }

        _write_temp_live_sandbox(live_root, "v_s3", lines_s3)
        for m in modes:
            _ = get_or_advance_live(m, live_root=live_root, deriv_root=deriv_root, cache_dir=cache_inc, force_rebuild=True)

        _write_temp_live_sandbox(live_root, "v_full_after_s3", raw_lines_full)
        for m in modes:
            r_inc = get_or_advance_live(m, live_root=live_root, deriv_root=deriv_root, cache_dir=cache_inc)
            r_hit = get_or_advance_live(m, live_root=live_root, deriv_root=deriv_root, cache_dir=cache_inc)
            r_ref = refs[m]

            e_err = abs(float(r_inc["E_S"]) - float(r_ref["E_S"]))
            pi_err = float(np.max(np.abs(np.array(r_inc["pi_inclusion"]) - np.array(r_ref["pi_inclusion"]))))
            j_err = (
                float(np.max(np.abs(np.array(r_inc["joker_prob"]) - np.array(r_ref["joker_prob"]))))
                if r_ref["joker_prob"] is not None
                else 0.0
            )
            tickets_eq = [v["ticket"] for v in r_inc["variants"]] == [v["ticket"] for v in r_ref["variants"]]
            ok_m = (
                e_err < 1e-12
                and pi_err < 1e-12
                and j_err < 1e-12
                and tickets_eq
                and int(r_inc["delta_steps"]) == 3
                and len(r_inc["settled_new_draws"]) >= 3
                and bool(r_hit["cache_hit"])
            )
            all_ok = all_ok and ok_m
            out_modes[m] = {
                "pass": bool(ok_m),
                "delta_steps": int(r_inc["delta_steps"]),
                "settled_new_draws": len(r_inc["settled_new_draws"]),
                "E_S_err": e_err,
                "pi_err": pi_err,
                "joker_prob_err": j_err,
                "variants_exact_match": bool(tickets_eq),
                "cache_hit_sec": r_hit["elapsed_sec"],
                "delta3_sec": r_inc["elapsed_sec"],
                "vram_after_bytes": r_inc["vram_allocated_after_bytes"],
            }

    return {"pass": bool(all_ok), "modes": out_modes}


# ============================================================================
# 7. EXECUȚIE COMPLETĂ FAZA 2A (WALKFORWARD_RO.json + ABLATIE_RO.json)
# ============================================================================

def run_phase2a_ro(
    modes: Sequence[str] = ("649", "540", "joker"),
    out_dir: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    run_inc_regression: bool = True,
    verbose: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    t0 = time.perf_counter()
    prereqs = verify_session1_prereqs()
    if verbose:
        print(f"[HS-V4 2A] Prerechizite Sesiunea 1 verificate: {prereqs['calificare_q_status']} ({prereqs['calificare_q_passed']})", flush=True)
        print("[HS-V4 2A] Certificare aliniere motor multi-config față de hs_v4/core.py...", flush=True)

    align_check = verify_fast_engine_against_core()
    if verbose:
        print(f"[HS-V4 2A] Aliniere motor PASS (< 1e-12): {json.dumps(align_check)}", flush=True)

    out_d = Path(out_dir) if out_dir is not None else OUT_DIR_DEFAULT
    c_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR_DEFAULT
    out_d.mkdir(parents=True, exist_ok=True)
    c_dir.mkdir(parents=True, exist_ok=True)

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    wf_games_out: Dict[str, Any] = {}
    ablation_games_out: Dict[str, Any] = {}
    cache_checkpoints_out: Dict[str, Any] = {}

    for mode in modes:
        game_name, N, r, k, jm = RO_GAME_CONFIGS[mode]
        _, src_key, prov = _resolve_live_source_and_key(mode)
        ds = PM.build_game_dataset(mode, "live", device=dev)
        meteo_np = load_meteo_features_for_dates(ds.step_dates)

        if verbose:
            print(
                f"\n[HS-V4 2A] Start {mode.upper()} ({game_name}): {ds.n_draws} extrageri, {ds.n_steps} pași "
                f"({ds.step_dates[0]}..{ds.step_dates[-1]}), 4 configurații ablație simultan...",
                flush=True,
            )

        wf_in = WalkForwardInput(
            game_code=mode,
            game_name=game_name,
            N=N,
            r_draw=r,
            k_ticket=k,
            joker_m=jm,
            draws_1based=ds.draws,
            onehot=ds.onehot,
            joker_1based=ds.joker,
            joker_onehot=ds.joker_onehot,
            step_offsets=ds.step_offsets,
            step_dates=list(ds.step_dates),
            keys=list(ds.keys),
            meteo_features=meteo_np,
            source_meta={
                "source_kind": "live",
                "src_key": src_key,
                "version_dir": prov.get("version_dir"),
                "manifest_sha256": prov.get("manifest_sha256"),
                "file_sha256": prov.get("file_sha256"),
            },
        )

        res_m = run_generic_walkforward_configs(
            wf_in,
            configs=ABLATION_CONFIGS,
            warmup=WARMUP_STEPS,
            save_npz_dir=out_d,
            npz_prefix=f"ro_{mode}",
            compute_terminal_states=True,
            verbose=verbose,
        )

        saved_ckpts = save_ro_checkpoints_from_walkforward(mode, ds, src_key, res_m, cache_dir=c_dir)
        # Verificăm imediat citirea cache-hit verificată SHA-256
        hit_check = get_or_advance_live(mode, config_key="Full_HSV4", cache_dir=c_dir)
        if not hit_check["cache_hit"]:
            raise RuntimeError(f"Cache-hit verificare SHA-256 eșuat pentru {mode}")
        cache_checkpoints_out[mode] = {
            "checkpoints": saved_ckpts,
            "cache_hit_verified": True,
            "cache_hit_sec": hit_check["elapsed_sec"],
        }

        full_cfg = res_m["configs"]["Full_HSV4"]
        wf_games_out[mode] = {
            "game_code": mode,
            "game_name": game_name,
            "game_params": res_m["game_params"],
            "archive": res_m["archive"],
            **full_cfg,
            "cache_checkpoint": saved_ckpts["Full_HSV4"],
            "timings": res_m["timings"],
            "device": res_m["device"],
            "peak_vram_mib": res_m["peak_vram_mib"],
        }

        # Tabel comparativ concis + date complete ale celor 4 configurații pentru ABLATIE_RO.json
        comp_rows = []
        for c_key, _, _, _, _ in ABLATION_CONFIGS:
            c_rep = res_m["configs"][c_key]
            wt = c_rep["windows"]["total"]
            bm = c_rep["bayesian_masses"]["posterior_final"]
            mt = c_rep["martingale_trajectory"]
            comp_rows.append({
                "config_key": c_key,
                "label": c_rep["label"],
                "verdict_gates": c_rep["verdict_gates"],
                "gates_passed": c_rep["gates_passed"],
                "hits_HSV4": wt["hits_HSV4"],
                "hits_B": wt["hits_B"],
                "hits_R": wt["hits_R"],
                "excess_hits_vs_U": wt["excess_hits_vs_U"],
                "log_score_HSV4": wt["log_score_HSV4"],
                "log_score_U": wt["log_score_U"],
                "log_score_B": wt["log_score_B"],
                "log_score_R": wt["log_score_R"],
                "log_diff_vs_U": round(wt["log_score_HSV4"] - wt["log_score_U"], 6),
                "log_diff_vs_B": round(wt["log_score_HSV4"] - wt["log_score_B"], 6),
                "brier_HSV4": wt["brier_HSV4"],
                "brier_U": wt["brier_U"],
                "brier_B": wt["brier_B"],
                "E_S": mt["E_S_final"],
                "min_E_s": mt["min_E_s"],
                "guarantee_E_ge_050": mt["guarantee_E_ge_050_verified"],
                "w_0_final": round(bm["w_0"], 6),
                "w_O1_final": round(bm["w_O1"], 6),
                "w_O2_final": round(bm["w_O2"], 6),
                "w_O4_final": round(bm["w_O4"], 6),
            })

        ablation_games_out[mode] = {
            "game_code": mode,
            "game_name": game_name,
            "archive": res_m["archive"],
            "comparison_table": comp_rows,
            "configs": res_m["configs"],
        }

        if verbose:
            wt = full_cfg["windows"]["total"]
            mt = full_cfg["martingale_trajectory"]
            bm = full_cfg["bayesian_masses"]["posterior_final"]
            print(
                f"=== [{mode.upper()} Full HS-V4] Porți: {full_cfg['verdict_gates']} | "
                f"Hits={wt['hits_HSV4']} (B={wt['hits_B']}, R={wt['hits_R']}, exces={wt['excess_hits_vs_U']:+.5f}) | "
                f"Log={wt['log_score_HSV4']:.2f} (U={wt['log_score_U']:.2f}, B={wt['log_score_B']:.2f}) | "
                f"E_S={mt['E_S_final']:.6f} (min={mt['min_E_s']:.6f}) | "
                f"w0={bm['w_0']:.4f} wO1={bm['w_O1']:.4f} wO2={bm['w_O2']:.4f} wO4={bm['w_O4']:.4f} | "
                f"{res_m['timings']['total_sec']}s ===",
                flush=True,
            )

        del ds, res_m
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    inc_reg = None
    if run_inc_regression:
        if verbose:
            print("\n[HS-V4 2A] Verificare regresie cache incremental (S-3 -> S == Full < 1e-12)...", flush=True)
        inc_reg = verify_incremental_cache_ro(modes)
        if not inc_reg["pass"]:
            raise RuntimeError(f"Regresia incrementală RO a eșuat: {inc_reg}")
        if verbose:
            print(f"[HS-V4 2A] Regresie incrementală PASS: {json.dumps(inc_reg['modes'])}", flush=True)

    wf_py_sha = sha256_file(Path(__file__))
    elapsed_all = round(time.perf_counter() - t0, 3)

    walkforward_ro_doc = {
        "protocol": "HSV4-P1",
        "phase": "2A_WALKFORWARD_LIVE_RO",
        "prereqs_verified": prereqs,
        "walkforward_py_sha256": wf_py_sha,
        "engine_alignment_verification": align_check,
        "incremental_cache_verification": inc_reg,
        "cache_directory": "hs_v4/cache",
        "cache_manifest_sha256": sha256_file(c_dir / "CACHE_MANIFEST.json"),
        "cache_checkpoints": cache_checkpoints_out,
        "games": wf_games_out,
        "total_elapsed_sec": elapsed_all,
        "generated_utc": utc_now(),
        "positive_claims_allowed": False,
    }

    ablatie_ro_doc = {
        "protocol": "HSV4-P1",
        "phase": "2A_ABLATIE_CANALE_RO",
        "prereqs_verified": prereqs,
        "walkforward_py_sha256": wf_py_sha,
        "ablation_configs": [
            {"key": k_c, "label": lbl, "O1": o1, "O2": o2, "O3": True, "O4": o4}
            for k_c, lbl, o1, o2, o4 in ABLATION_CONFIGS
        ],
        "games": ablation_games_out,
        "total_elapsed_sec": elapsed_all,
        "generated_utc": utc_now(),
        "positive_claims_allowed": False,
    }

    atomic_write_json(out_d / "WALKFORWARD_RO.json", walkforward_ro_doc)
    atomic_write_json(out_d / "ABLATIE_RO.json", ablatie_ro_doc)
    return walkforward_ro_doc, ablatie_ro_doc


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="HS-V4 Faza 2A — Walk-Forward LIVE RO & Ablație Canale.")
    ap.add_argument("--mode", choices=["649", "540", "joker", "all"], default="all")
    ap.add_argument("--only-live", action="store_true", help="Rulează doar hook-ul cache incremental get_or_advance_live.")
    ap.add_argument("--skip-inc-regression", action="store_true")
    args = ap.parse_args(argv)

    modes = ["649", "540", "joker"] if args.mode == "all" else [args.mode]
    if args.only_live:
        for m in modes:
            r_live = get_or_advance_live(m)
            print(
                f"[HS-V4 LIVE {m}] step={r_live['step_idx']} hit={r_live['cache_hit']} "
                f"ΔS={r_live['delta_steps']} E_S={r_live['E_S']:.6f} α={r_live['variants'][0]['ticket']} "
                f"({r_live['elapsed_sec']:.4f}s)"
            )
        return 0

    run_phase2a_ro(modes=modes, run_inc_regression=not args.skip_inc_regression, verbose=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
