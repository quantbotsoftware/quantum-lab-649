"""HS-V4 — Calificarea algebrică și fizico-statistică Q1..Q6 pe GPU (fără citirea arhivei reale RO).

Rulează cu: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B hs_v4/verify_q.py
Scrie certificatul în hs_v4/rezultate/CALIFICARE_Q.json (6/6 PASS obligatoriu).
Calcul clasic exact în float64; positive_claims_allowed = False.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import stat
import sys
import time
from pathlib import Path
from typing import Tuple

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
if str(QL) not in sys.path:
    sys.path.insert(0, str(QL))

from hs_v4.core import (  # noqa: E402
    DEFAULT_PARAMS,
    HSV4Params,
    HSV4Space,
    advance_one_step,
    advance_steps,
    elementary_symmetric_ek_and_marginals,
    evaluate_portfolio_full_space,
    evaluate_single_hs_gpu,
    extract_step_slices,
    forward_operators_from_state,
    gauss_hermite_exact_hs,
    get_cumulative_e_value,
    get_portfolio_weights,
    init_state,
)
from hs_v4.meteo_ro import PROVENANCE_JSON, CACHE_JSONL  # noqa: E402


def _synth_universe_with_meteo(
    N: int,
    r: int,
    n_steps: int,
    seed: int,
    device: torch.device,
    joker_m: int | None = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor | None, torch.Tensor]:
    """Generează un univers sintetic fără întoarcere (cu zile duble în step_offsets + serie meteo exogenă)."""
    rng = np.random.default_rng(seed)
    offs = [0]
    rows = []
    j_rows = []
    met_rows = []

    for s in range(n_steps):
        rho_air = 1.215 + 0.065 * math.cos(2.0 * math.pi * s / 37.0) + 0.015 * float(rng.standard_normal())
        rh_pct = 58.0 + 18.0 * math.sin(2.0 * math.pi * s / 29.0) + 4.0 * float(rng.standard_normal())
        dp_24h = 3.5 * math.sin(2.0 * math.pi * s / 11.0) + 1.5 * float(rng.standard_normal())
        met_rows.append([rho_air, min(max(rh_pct, 10.0), 100.0), dp_24h])

        m_s = 2 if (s % 9 == 4) else 1
        # Valiză latentă oscilantă + ușor cuplaj la densitatea aerului pentru a activa toate canalele O1–O2
        mode_sign = 1.0 if (s % 2 == 0) else -1.0
        for _ in range(m_s):
            logits = (
                0.42 * mode_sign * np.cos(2.0 * math.pi * np.arange(N) / float(N))
                + 0.25 * ((rho_air - 1.215) / 0.065) * np.sin(2.0 * math.pi * np.arange(N) / float(N))
            )
            probs = np.exp(logits)
            probs /= probs.sum()
            chosen = rng.choice(N, size=r, replace=False, p=probs)
            oh = np.zeros(N, dtype=np.float64)
            oh[chosen] = 1.0
            rows.append(oh)

            if joker_m is not None:
                j_logits = 0.35 * mode_sign * np.sin(2.0 * math.pi * np.arange(joker_m) / float(joker_m))
                jp = np.exp(j_logits)
                jp /= jp.sum()
                jb = int(rng.choice(joker_m, p=jp))
                joh = np.zeros(joker_m, dtype=np.float64)
                joh[jb] = 1.0
                j_rows.append(joh)
        offs.append(len(rows))

    onehot = torch.as_tensor(np.stack(rows), dtype=torch.float64, device=device)
    step_offsets = torch.as_tensor(offs, dtype=torch.int64, device=device)
    joker_oh = torch.as_tensor(np.stack(j_rows), dtype=torch.float64, device=device) if joker_m is not None else None
    meteo_t = torch.as_tensor(np.array(met_rows, dtype=np.float64), dtype=torch.float64, device=device)
    return onehot, step_offsets, joker_oh, meteo_t


def _baseline_top_k(onehot: torch.Tensor, k: int) -> Tuple[list[int], list[int]]:
    """Reperele canonice 1-corp B (frecvență brută) și R (recență exponențială τ=26) în 1-based."""
    H = onehot.detach().cpu().numpy().astype(np.float64)
    freq = H.sum(axis=0)
    top_B = sorted((int(x) + 1) for x in np.argsort(-freq, kind="mergesort")[:k])
    T = H.shape[0]
    decay = np.power(2.0, -np.arange(T - 1, -1, -1, dtype=np.float64) / 26.0)
    rec = (H * decay[:, None]).sum(axis=0)
    top_R = sorted((int(x) + 1) for x in np.argsort(-rec, kind="mergesort")[:k])
    return top_B, top_R


def _ek_scalar(weights: np.ndarray, k: int) -> float:
    dp = np.zeros(k + 1, dtype=np.float64)
    dp[0] = 1.0
    for val in weights:
        for j in range(k, 0, -1):
            dp[j] += float(val) * dp[j - 1]
    return float(dp[k])


def run_qualification() -> dict:
    t0 = time.perf_counter()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    # Verificare prealabilă integritate protocol sigilat 0444 + cache meteo
    proto_path = HERE / "PROTOCOL_HSV4.md"
    seal_path = HERE / "SIGILIU_PROTOCOL_HSV4.json"
    seal_obj = json.loads(seal_path.read_text(encoding="utf-8"))
    proto_sha = hashlib.sha256(proto_path.read_bytes()).hexdigest()
    proto_ro = (stat.S_IMODE(proto_path.stat().st_mode) == 0o444) and (stat.S_IMODE(seal_path.stat().st_mode) == 0o444)
    if proto_sha != seal_obj["sha256"] or not proto_ro or seal_obj.get("code_files_present") != []:
        raise RuntimeError("Sigiliul PROTOCOL_HSV4.md nu este valid sau nu are permisiuni 0444!")

    meteo_prov = json.loads(PROVENANCE_JSON.read_text(encoding="utf-8"))
    meteo_sha = hashlib.sha256(CACHE_JSONL.read_bytes()).hexdigest()
    if meteo_sha != meteo_prov["sha256"]:
        raise RuntimeError("Cache-ul meteo București nu corespunde cu PROVENIENTA_METEO.json!")

    checks = []

    # =========================================================================
    # Q1: Certificare algebrică Z_HS pe GPU vs Gauss–Hermite + e_k în float64 (< 1e-12)
    #     și probabilități exacte însumate la 1.0 pe toate stările (649, 540, joker)
    # =========================================================================
    sp_649 = HSV4Space(N=49, r_draw=6, k_ticket=6, device=device)
    oh_649, offs_649, _, met_649 = _synth_universe_with_meteo(49, 6, n_steps=45, seed=20260649, device=device)
    st_649 = advance_steps(init_state(sp_649), sp_649, extract_step_slices(oh_649, offs_649, None, met_649))
    ops_649 = forward_operators_from_state(st_649, sp_649, met_649[-1])
    h_c_649 = (ops_649["h_int"] + ops_649["h_aero"]) / math.sqrt(2.0)
    gpu_649 = evaluate_single_hs_gpu(sp_649, h_c_649, ops_649["V_s"], eta=0.40, gamma=0.45)
    gh_649 = gauss_hermite_exact_hs(sp_649, h_c_649, ops_649["V_s"], eta=0.40, gamma=0.45)
    port_649 = evaluate_portfolio_full_space(sp_649, ops_649)

    rel_z_649 = abs(gpu_649["Z_exact"] - gh_649["Z_exact"]) / max(gh_649["Z_exact"], 1e-30)
    pi_err_649 = float((gpu_649["pi_inclusion"] - gh_649["pi_inclusion"]).abs().max().item())
    psum_err_649 = max(abs(gpu_649["prob_sum_exact"] - 1.0), abs(port_649["prob_sum_exact"] - 1.0))

    sp_540 = HSV4Space(N=40, r_draw=6, k_ticket=5, device=device)
    oh_540, offs_540, _, met_540 = _synth_universe_with_meteo(40, 6, n_steps=40, seed=20260540, device=device)
    st_540 = advance_steps(init_state(sp_540), sp_540, extract_step_slices(oh_540, offs_540, None, met_540))
    ops_540 = forward_operators_from_state(st_540, sp_540, met_540[-1])
    h_c_540 = (ops_540["h_int"] + ops_540["h_aero"]) / math.sqrt(2.0)
    gpu_540 = evaluate_single_hs_gpu(sp_540, h_c_540, ops_540["V_s"], eta=0.40, gamma=0.45)
    gh_540 = gauss_hermite_exact_hs(sp_540, h_c_540, ops_540["V_s"], eta=0.40, gamma=0.45)
    port_540 = evaluate_portfolio_full_space(sp_540, ops_540)

    rel_z_540 = abs(gpu_540["Z_exact"] - gh_540["Z_exact"]) / max(gh_540["Z_exact"], 1e-30)
    pi_err_540 = float((gpu_540["pi_inclusion"] - gh_540["pi_inclusion"]).abs().max().item())
    psum_err_540 = max(abs(gpu_540["prob_sum_exact"] - 1.0), abs(port_540["prob_sum_exact"] - 1.0))

    sp_jok = HSV4Space(N=45, r_draw=5, k_ticket=5, device=device, joker_m=20)
    oh_j, offs_j, jh_j, met_j = _synth_universe_with_meteo(45, 5, n_steps=40, seed=20264520, device=device, joker_m=20)
    st_jok = advance_steps(init_state(sp_jok), sp_jok, extract_step_slices(oh_j, offs_j, jh_j, met_j))
    ops_jok = forward_operators_from_state(st_jok, sp_jok, met_j[-1])
    jp = ops_jok["joker_pack"]
    h_c_j = (ops_jok["h_int"] + ops_jok["h_aero"]) / math.sqrt(2.0)
    hj_c = (jp["hj_int"] + jp["hj_aero"]) / math.sqrt(2.0)
    gpu_jok = evaluate_single_hs_gpu(sp_jok, h_c_j, ops_jok["V_s"], 0.40, 0.45, hj_c, jp["J_s"], jp["U_joker"])
    gh_jok = gauss_hermite_exact_hs(sp_jok, h_c_j, ops_jok["V_s"], 0.40, 0.45, hj_c, jp["J_s"], jp["U_joker"])
    port_jok = evaluate_portfolio_full_space(sp_jok, ops_jok)

    rel_z_jok = abs(gpu_jok["Z_exact"] - gh_jok["Z_exact"]) / max(gh_jok["Z_exact"], 1e-30)
    pi_err_jok = float((gpu_jok["pi_inclusion"] - gh_jok["pi_inclusion"]).abs().max().item())
    jp_err_jok = float((gpu_jok["joker_prob"] - gh_jok["joker_prob"]).abs().max().item())
    psum_err_jok = max(abs(gpu_jok["prob_sum_exact"] - 1.0), abs(port_jok["prob_sum_exact"] - 1.0))

    q1_pass = (
        max(rel_z_649, rel_z_540, rel_z_jok) < 1e-12
        and max(psum_err_649, psum_err_540, psum_err_jok) < 1e-12
        and max(pi_err_649, pi_err_540, pi_err_jok, jp_err_jok) < 1e-12
    )
    checks.append({
        "id": "Q1",
        "name": "Certificare algebrică Z_HS pe GPU vs Gauss–Hermite + e_k (< 1e-12) și ∑ P = 1.0 (649, 540, joker)",
        "pass": bool(q1_pass),
        "detail": {
            "rel_err_Z_649": rel_z_649,
            "rel_err_Z_540": rel_z_540,
            "rel_err_Z_joker": rel_z_jok,
            "prob_sum_err_649": psum_err_649,
            "prob_sum_err_540": psum_err_540,
            "prob_sum_err_joker": psum_err_jok,
            "marginal_gh_vs_gpu_max_err": max(pi_err_649, pi_err_540, pi_err_jok, jp_err_jok),
            "states_evaluated": [sp_649.total_states, sp_540.total_states, sp_jok.total_states],
        },
    })

    # =========================================================================
    # Q2: Exactitate deconvoluție subspațiu bosonic O1 (amestec valize cu marginale plate r/N)
    #     + canal electronic O4 (detectare bias sintetic modulo 2^b mod N)
    # =========================================================================
    rng_q2 = np.random.default_rng(2026)
    B_suit = np.zeros((49, 3), dtype=np.float64)
    # 3 moduri Walsh–Rademacher ortogonale pe 48 bile (suma fiecărei coloane = 0 -> marginale 1-corp plate r/N!)
    for idx_b in range(48):
        B_suit[idx_b, 0] = 1.0 if (idx_b % 2 == 0) else -1.0
        B_suit[idx_b, 1] = 1.0 if ((idx_b // 2) % 2 == 0) else -1.0
        B_suit[idx_b, 2] = 1.0 if ((idx_b // 4) % 2 == 0) else -1.0
    D_true = B_suit / np.linalg.norm(B_suit, axis=0, keepdims=True)

    # Varianță de ordin 2 egală pe toate cele 3 moduri (astfel PCA simplu amestecă modurile), dar asimetrie cubică distinctă
    var_mode = 0.26
    probs_skew = (0.22, 0.35, 0.50)
    T_q2a = 4500
    X_q2a = np.zeros((T_q2a, 49), dtype=np.float64)
    for t_step in range(T_q2a):
        m_mode = t_step % 3
        pv = probs_skew[m_mode]
        amp = math.sqrt(var_mode) * (
            math.sqrt((1.0 - pv) / pv) if rng_q2.random() < pv else -math.sqrt(pv / (1.0 - pv))
        )
        w_balls = (1.0 + amp * B_suit[:, m_mode]) / 49.0
        X_q2a[t_step, rng_q2.choice(49, size=6, replace=False, p=w_balls)] = 1.0

    offs_q2a = torch.arange(0, T_q2a + 1, dtype=torch.int64, device=device)
    oh_q2a = torch.as_tensor(X_q2a, dtype=torch.float64, device=device)
    # Orizont lung pentru testul de exactitate al deconvoluției Jennrich pe amestecul de valize cu varianță egală
    params_q2a = HSV4Params(tau_bos=2500.0)
    st_q2a = advance_steps(
        init_state(sp_649, params=params_q2a, enable_o1=True, enable_o2=False, enable_o4=False),
        sp_649,
        extract_step_slices(oh_q2a, offs_q2a),
        params=params_q2a,
        update_portfolio=False,
    )
    ops_q2a = forward_operators_from_state(st_q2a, sp_649, params=params_q2a)
    W_jen_np = ops_q2a["W_jen"].detach().cpu().numpy()
    U_pca_np = ops_q2a["U_R"].detach().cpu().numpy()

    flat_1body_err = float(np.max(np.abs(X_q2a.mean(axis=0) - (6.0 / 49.0))))
    subspace_capture = float(np.linalg.norm(U_pca_np.T @ D_true) ** 2 / 3.0)
    jen_cosines = np.abs(W_jen_np.T @ D_true).max(axis=0)
    pca_cosines = np.abs(U_pca_np.T @ D_true).max(axis=0)

    # Partea B: Canalul electronic O4 pe extrageri RNG cu bias de respingere incompletă (X ∈ {0..63} -> X mod 49)
    rng_q2b = np.random.default_rng(20260064)
    T_q2b = 260
    X_q2b = np.zeros((T_q2b, 49), dtype=np.float64)
    for t_step in range(T_q2b):
        picked: set[int] = set()
        while len(picked) < 6:
            # Generator pe 6 biți fără rejection sampling: reziduurile 0..14 (2^6 mod 49 = 15) au dublă preimagine!
            raw_u6 = int(rng_q2b.integers(0, 64))
            ball_u = raw_u6 % 49
            picked.add(ball_u)
        for b_idx in picked:
            X_q2b[t_step, b_idx] = 1.0

    offs_q2b = torch.arange(0, T_q2b + 1, dtype=torch.int64, device=device)
    oh_q2b = torch.as_tensor(X_q2b, dtype=torch.float64, device=device)
    st_q2b = advance_steps(
        init_state(sp_649, enable_o1=True, enable_o2=True, enable_o4=True),
        sp_649,
        extract_step_slices(oh_q2b, offs_q2b),
        update_portfolio=True,
        min_wealth_step=25,
    )
    ops_q2b = forward_operators_from_state(st_q2b, sp_649)
    psi_mod64 = sp_649.o4_main["static"][:, 0].detach().cpu().numpy()  # profilul teoretic 2^6 mod 49
    h_rng_np = ops_q2b["h_rng"].detach().cpu().numpy()
    h_rng_unit = h_rng_np / max(float(np.linalg.norm(h_rng_np)), 1e-12)
    o4_mod64_cosine = float(np.dot(h_rng_unit, psi_mod64))
    w_port_q2b = get_portfolio_weights(st_q2b).detach().cpu().numpy()
    w_o4_mass = float(w_port_q2b[6] + w_port_q2b[7])
    e_val_q2b = get_cumulative_e_value(st_q2b)

    q2_pass = (
        flat_1body_err < 0.025
        and subspace_capture > 0.90
        and float(jen_cosines.min()) > 0.90
        and float(jen_cosines.mean()) > float(pca_cosines.mean())
        and o4_mod64_cosine > 0.85
        and w_o4_mass > 0.85
        and e_val_q2b > 100.0
    )
    checks.append({
        "id": "Q2",
        "name": "Exactitate deconvoluție Jennrich O1 (marginale plate r/N) + detecție RNG modulo 2^b mod N în O4",
        "pass": bool(q2_pass),
        "detail": {
            "flat_1body_max_err": round(flat_1body_err, 5),
            "o1_subspace_capture": round(subspace_capture, 5),
            "o1_jennrich_cosines": [round(float(x), 4) for x in jen_cosines],
            "o1_plain_pca_cosines": [round(float(x), 4) for x in pca_cosines],
            "o4_mod64_cosine": round(o4_mod64_cosine, 4),
            "o4_posterior_mass": round(w_o4_mass, 6),
            "o4_log10_E_S": round(math.log10(max(e_val_q2b, 1e-30)), 4),
        },
    })

    # =========================================================================
    # Q3: Echivarianță exactă S_49, S_40 și S_45 × S_20 a nucleului mecanic O1–O2
    # =========================================================================
    rng_perm = np.random.default_rng(49404520)

    # S_49 pe 6/49 (O1+O2 active, O4 dezactivat conform specificației nucleului mecanic)
    st_m649 = advance_steps(
        init_state(sp_649, enable_o1=True, enable_o2=True, enable_o4=False),
        sp_649,
        extract_step_slices(oh_649, offs_649, None, met_649),
    )
    ops_m649 = forward_operators_from_state(st_m649, sp_649, met_649[-1])
    ev_m649 = evaluate_portfolio_full_space(sp_649, ops_m649)

    perm_49 = torch.as_tensor(rng_perm.permutation(49), dtype=torch.long, device=device)
    st_m649_p = advance_steps(
        init_state(sp_649, enable_o1=True, enable_o2=True, enable_o4=False),
        sp_649,
        extract_step_slices(oh_649[:, perm_49], offs_649, None, met_649),
    )
    ops_m649_p = forward_operators_from_state(st_m649_p, sp_649, met_649[-1])
    ev_m649_p = evaluate_portfolio_full_space(sp_649, ops_m649_p)
    pi_eq_649 = float((ev_m649_p["pi_inclusion"] - ev_m649["pi_inclusion"][perm_49]).abs().max().item())
    w_eq_649 = float((ev_m649_p["w_portfolio"] - ev_m649["w_portfolio"]).abs().max().item())
    lz_eq_649 = float((ev_m649_p["log_Z_experts"] - ev_m649["log_Z_experts"]).abs().max().item())
    ticket_649_orig = sorted(ev_m649["variants"][0]["ticket"])
    ticket_649_perm = sorted(int(perm_49[b - 1].item()) + 1 for b in ev_m649_p["variants"][0]["ticket"])

    # S_40 pe 5/40
    st_m540 = advance_steps(
        init_state(sp_540, enable_o1=True, enable_o2=True, enable_o4=False),
        sp_540,
        extract_step_slices(oh_540, offs_540, None, met_540),
    )
    ops_m540 = forward_operators_from_state(st_m540, sp_540, met_540[-1])
    ev_m540 = evaluate_portfolio_full_space(sp_540, ops_m540)

    perm_40 = torch.as_tensor(rng_perm.permutation(40), dtype=torch.long, device=device)
    st_m540_p = advance_steps(
        init_state(sp_540, enable_o1=True, enable_o2=True, enable_o4=False),
        sp_540,
        extract_step_slices(oh_540[:, perm_40], offs_540, None, met_540),
    )
    ops_m540_p = forward_operators_from_state(st_m540_p, sp_540, met_540[-1])
    ev_m540_p = evaluate_portfolio_full_space(sp_540, ops_m540_p)
    pi_eq_540 = float((ev_m540_p["pi_inclusion"] - ev_m540["pi_inclusion"][perm_40]).abs().max().item())
    w_eq_540 = float((ev_m540_p["w_portfolio"] - ev_m540["w_portfolio"]).abs().max().item())

    # S_45 × S_20 pe Joker
    st_mj = advance_steps(
        init_state(sp_jok, enable_o1=True, enable_o2=True, enable_o4=False),
        sp_jok,
        extract_step_slices(oh_j, offs_j, jh_j, met_j),
    )
    ops_mj = forward_operators_from_state(st_mj, sp_jok, met_j[-1])
    ev_mj = evaluate_portfolio_full_space(sp_jok, ops_mj)

    perm_45 = torch.as_tensor(rng_perm.permutation(45), dtype=torch.long, device=device)
    perm_20 = torch.as_tensor(rng_perm.permutation(20), dtype=torch.long, device=device)
    st_mj_p = advance_steps(
        init_state(sp_jok, enable_o1=True, enable_o2=True, enable_o4=False),
        sp_jok,
        extract_step_slices(oh_j[:, perm_45], offs_j, jh_j[:, perm_20], met_j),
    )
    ops_mj_p = forward_operators_from_state(st_mj_p, sp_jok, met_j[-1])
    ev_mj_p = evaluate_portfolio_full_space(sp_jok, ops_mj_p)
    pi_eq_45 = float((ev_mj_p["pi_inclusion"] - ev_mj["pi_inclusion"][perm_45]).abs().max().item())
    pi_eq_20 = float((ev_mj_p["joker_prob"] - ev_mj["joker_prob"][perm_20]).abs().max().item())
    w_eq_j = float((ev_mj_p["w_portfolio"] - ev_mj["w_portfolio"]).abs().max().item())

    q3_pass = (
        max(pi_eq_649, pi_eq_540, pi_eq_45, pi_eq_20) < 1e-12
        and max(w_eq_649, w_eq_540, w_eq_j, lz_eq_649) < 1e-12
        and (ticket_649_orig == ticket_649_perm)
    )
    checks.append({
        "id": "Q3",
        "name": "Echivarianță exactă S_49, S_40 și S_45 × S_20 a nucleului mecanic O1–O2",
        "pass": bool(q3_pass),
        "detail": {
            "pi_equiv_649_err": pi_eq_649,
            "pi_equiv_540_err": pi_eq_540,
            "pi_equiv_joker45_err": pi_eq_45,
            "pi_equiv_joker20_err": pi_eq_20,
            "portfolio_weight_equiv_max_err": max(w_eq_649, w_eq_540, w_eq_j),
            "ground_ticket_equivariant": (ticket_649_orig == ticket_649_perm),
        },
    })

    # =========================================================================
    # Q4: Cauzalitate strictă (step_offsets cu zile duble, standardizare meteo fără scurgere,
    #     incremental == full < 1e-12)
    # =========================================================================
    s_cut = 32
    draw_cut = int(offs_649[s_cut].item())
    slices_full = extract_step_slices(oh_649, offs_649, None, met_649)

    # 1. Perturbăm extrem atât extragerile viitoare (>= s_cut), cât și meteo viitor (> s_cut)
    oh_pert = oh_649.clone()
    oh_pert[draw_cut:] = 0.0
    oh_pert[draw_cut:, :6] = 1.0
    met_pert = met_649.clone()
    met_pert[s_cut + 1 :] = torch.tensor([999.0, 0.1, -500.0], dtype=torch.float64, device=device)

    st_cut_a = advance_steps(init_state(sp_649), sp_649, extract_step_slices(oh_649[:draw_cut], offs_649[: s_cut + 1], None, met_649[:s_cut]))
    st_cut_b = advance_steps(init_state(sp_649), sp_649, extract_step_slices(oh_pert, offs_649, None, met_pert)[:s_cut])
    ops_cut_a = forward_operators_from_state(st_cut_a, sp_649, met_649[s_cut])
    ops_cut_b = forward_operators_from_state(st_cut_b, sp_649, met_pert[s_cut])

    leak_z_met = float((ops_cut_a["z_met"] - ops_cut_b["z_met"]).abs().max().item())
    leak_vs = float((ops_cut_a["V_s"] - ops_cut_b["V_s"]).abs().max().item())
    leak_aero = float((ops_cut_a["h_aero"] - ops_cut_b["h_aero"]).abs().max().item())
    leak_rng = float((ops_cut_a["h_rng"] - ops_cut_b["h_rng"]).abs().max().item())
    leak_w = float((ops_cut_a["w_portfolio"] - ops_cut_b["w_portfolio"]).abs().max().item())
    max_future_leak = max(leak_z_met, leak_vs, leak_aero, leak_rng, leak_w)

    # 2. Invarianța la inversarea ordinii extragerilor din aceeași zi în toate zilele duble (m_s == 2)
    slices_swapped = []
    double_days_count = 0
    for oh_s, jh_s, met_s in slices_full:
        if oh_s.shape[0] > 1:
            double_days_count += 1
            slices_swapped.append((torch.flip(oh_s, dims=[0]), jh_s, met_s))
        else:
            slices_swapped.append((oh_s, jh_s, met_s))
    st_swapped = advance_steps(init_state(sp_649), sp_649, slices_swapped)
    ops_swapped = forward_operators_from_state(st_swapped, sp_649, met_649[-1])
    swap_err = max(
        float((ops_swapped["V_s"] - ops_649["V_s"]).abs().max().item()),
        float((ops_swapped["w_portfolio"] - ops_649["w_portfolio"]).abs().max().item()),
        float((ops_swapped["h_rng"] - ops_649["h_rng"]).abs().max().item()),
    )

    # 3. Rulare incrementală (0 -> s_cut -> 45) vs. rulare completă (0 -> 45)
    st_inc = advance_steps(st_cut_a.clone(), sp_649, slices_full[s_cut:])
    ops_inc = forward_operators_from_state(st_inc, sp_649, met_649[-1])
    inc_err = max(
        float((st_inc.m2_bos - st_649.m2_bos).abs().max().item()),
        float((st_inc.m3_dist - st_649.m3_dist).abs().max().item()),
        float((ops_inc["V_s"] - ops_649["V_s"]).abs().max().item()),
        float((ops_inc["h_aero"] - ops_649["h_aero"]).abs().max().item()),
        float((ops_inc["h_rng"] - ops_649["h_rng"]).abs().max().item()),
        float((ops_inc["w_portfolio"] - ops_649["w_portfolio"]).abs().max().item()),
    )

    q4_pass = (max_future_leak == 0.0) and (double_days_count >= 4) and (swap_err < 1e-13) and (inc_err < 1e-12)
    checks.append({
        "id": "Q4",
        "name": "Cauzalitate strictă (step_offsets cu zile duble, meteo fără scurgere, incremental == full < 1e-12)",
        "pass": bool(q4_pass),
        "detail": {
            "future_leak_max_err": max_future_leak,
            "double_draw_days_tested": double_days_count,
            "same_day_order_swap_err": swap_err,
            "incremental_vs_full_err": inc_err,
        },
    })

    # =========================================================================
    # Q5: Martor de Separare Fizică — Z=2 valize latente opuse (+δ / -δ) trase cu moneda 1/2
    #     B, R și k-DPP respingător au E <= 1 / marginale oarbe, iar HS-V4 obține E_S > 1000
    # =========================================================================
    rng_q5 = np.random.default_rng(20261102)
    signs_q5 = np.zeros(49, dtype=np.float64)
    signs_q5[:24] = 1.0
    signs_q5[24:48] = -1.0
    S_q5 = 260
    s_eval_start = 40
    alpha_suit = 0.72

    draws_q5 = []
    X_q5 = np.zeros((S_q5, 49), dtype=np.float64)
    for s_idx in range(S_q5):
        coin = 1.0 if rng_q5.random() < 0.5 else -1.0
        w_suit = (1.0 + alpha_suit * coin * signs_q5) / 49.0
        d_balls = rng_q5.choice(49, size=6, replace=False, p=w_suit)
        draws_q5.append(d_balls)
        X_q5[s_idx, d_balls] = 1.0

    st_q5 = init_state(sp_649, enable_o1=True, enable_o2=True, enable_o4=True)
    comb_49_6 = float(math.comb(49, 6))
    P_np = np.eye(49, dtype=np.float64) - np.ones((49, 49), dtype=np.float64) / 49.0
    sig0_49 = (6.0 * 43.0) / (49.0 * 48.0)

    log_lr_b = 0.0
    log_lr_r = 0.0
    log_lr_dpp = 0.0

    for s_idx in range(S_q5):
        oh_step_q5 = torch.as_tensor(X_q5[s_idx : s_idx + 1], dtype=torch.float64, device=device)
        if s_idx >= s_eval_start:
            X_past = X_q5[:s_idx]
            d_cur = draws_q5[s_idx]

            # Reper B (frecvență 1-corp netezită Laplace fără întoarcere)
            wb = X_past.sum(axis=0) + 1.0
            p_b = float(np.prod(wb[d_cur])) / _ek_scalar(wb, 6)
            log_lr_b += math.log(p_b * comb_49_6)

            # Reper R (recență exponențială τ=26 fără întoarcere)
            dec_r = np.power(2.0, -np.arange(s_idx - 1, -1, -1, dtype=np.float64) / 26.0)
            wr = (X_past * dec_r[:, None]).sum(axis=0) + 0.5
            p_r = float(np.prod(wr[d_cur])) / _ek_scalar(wr, 6)
            log_lr_r += math.log(p_r * comb_49_6)

            # Model k-DPP respingător canonic K = exp(0.5 * C_deb)
            m1_p = X_past.mean(axis=0)
            cov_p = (X_past.T @ X_past) / float(s_idx) - np.outer(m1_p, m1_p)
            c_tilde = P_np @ ((cov_p / sig0_49) - P_np) @ P_np
            ev_c, vc_c = np.linalg.eigh(c_tilde)
            k_eigs = np.exp(0.5 * ev_c)
            K_dpp = (vc_c * k_eigs[None, :]) @ vc_c.T
            det_sub = float(np.linalg.det(K_dpp[np.ix_(d_cur, d_cur)]))
            p_dpp = max(det_sub, 1e-300) / _ek_scalar(k_eigs, 6)
            log_lr_dpp += math.log(p_dpp * comb_49_6)

        advance_one_step(
            st_q5,
            sp_649,
            oh_step_q5,
            update_portfolio=True,
            min_wealth_step=s_eval_start,
        )

    E_hsv4_q5 = get_cumulative_e_value(st_q5)
    E_b_q5 = math.exp(max(min(log_lr_b, 700.0), -700.0))
    E_r_q5 = math.exp(max(min(log_lr_r, 700.0), -700.0))
    E_dpp_q5 = math.exp(max(min(log_lr_dpp, 700.0), -700.0))
    marg_blind_err = float(np.max(np.abs(X_q5.mean(axis=0) - (6.0 / 49.0))))
    # Sub moneda echilibrată 1/2, E[p_i] = 1/49 exact (0.0 bias 1-corp); fluctuația binomială pe S=260 are σ≈0.020
    theoretical_1body_bias = float(np.max(np.abs(0.5 * (1.0 + alpha_suit * signs_q5) / 49.0 + 0.5 * (1.0 - alpha_suit * signs_q5) / 49.0 - (1.0 / 49.0))))
    w_q5 = get_portfolio_weights(st_q5).detach().cpu().numpy()

    q5_pass = (
        E_hsv4_q5 > 1000.0
        and E_b_q5 <= 1.0
        and E_r_q5 <= 1.0
        and E_dpp_q5 <= 1.0
        and theoretical_1body_bias < 1e-16
        and marg_blind_err < 0.065
    )
    checks.append({
        "id": "Q5",
        "name": "Martor de Separare Fizică (Z=2 valize opuse cu moneda): B, R, k-DPP <= 1 vs HS-V4 E_S > 1000",
        "pass": bool(q5_pass),
        "detail": {
            "log10_E_HSV4": round(math.log10(E_hsv4_q5), 4),
            "log10_E_B": round(log_lr_b / math.log(10.0), 4),
            "log10_E_R": round(log_lr_r / math.log(10.0), 4),
            "log10_E_kDPP_repulsive": round(log_lr_dpp / math.log(10.0), 4),
            "theoretical_1body_bias": theoretical_1body_bias,
            "empirical_1body_max_dev": round(marg_blind_err, 5),
            "posterior_o1_bosonic_mass": round(float(w_q5[1] + w_q5[2] + w_q5[3]), 6),
        },
    })

    # =========================================================================
    # Q6: Martor de Siguranță sub Nul / CSPRNG + Multiplet Jastrow Distinct (det G > 0)
    # =========================================================================
    rng_q6 = np.random.default_rng(20260000)
    S_q6 = 260
    X_q6 = np.zeros((S_q6, 49), dtype=np.float64)
    met_q6 = np.zeros((S_q6, 3), dtype=np.float64)
    for s_idx in range(S_q6):
        X_q6[s_idx, rng_q6.choice(49, size=6, replace=False)] = 1.0
        met_q6[s_idx] = [
            1.21 + 0.05 * float(rng_q6.standard_normal()),
            60.0 + 12.0 * float(rng_q6.standard_normal()),
            2.5 * float(rng_q6.standard_normal()),
        ]

    st_q6 = init_state(sp_649, enable_o1=True, enable_o2=True, enable_o4=True)
    w0_initial = float(get_portfolio_weights(st_q6)[0].item())
    min_e_trajectory = 1.0

    for s_idx in range(S_q6):
        oh_s = torch.as_tensor(X_q6[s_idx : s_idx + 1], dtype=torch.float64, device=device)
        met_s = torch.as_tensor(met_q6[s_idx], dtype=torch.float64, device=device)
        advance_one_step(st_q6, sp_649, oh_s, meteo_raw_step=met_s, update_portfolio=True, min_wealth_step=20)
        cur_e = get_cumulative_e_value(st_q6)
        if cur_e < min_e_trajectory:
            min_e_trajectory = cur_e

    final_e_q6 = get_cumulative_e_value(st_q6)
    w0_final = float(get_portfolio_weights(st_q6)[0].item())

    ops_q6 = forward_operators_from_state(
        st_q6, sp_649, torch.as_tensor(met_q6[-1], dtype=torch.float64, device=device)
    )
    ev_q6 = evaluate_portfolio_full_space(sp_649, ops_q6)
    oh_q6_t = torch.as_tensor(X_q6, dtype=torch.float64, device=device)
    top_B_q6, top_R_q6 = _baseline_top_k(oh_q6_t, 6)
    t_alpha = ev_q6["variants"][0]["ticket"]
    t_beta = ev_q6["variants"][1]["ticket"]
    t_gamma = ev_q6["variants"][2]["ticket"]

    # Verificăm și fibrele distincte pe Joker din port_jok
    joker_fibers = [v["joker"] for v in port_jok["variants"]]
    joker_distinct_fibers = len(set(joker_fibers)) == 3

    q6_pass = (
        min_e_trajectory >= 0.50 - 1e-15
        and final_e_q6 >= 0.50 - 1e-15
        and w0_final > 0.75
        and w0_final > w0_initial
        and ev_q6["det_G3"] > 1e-4
        and ev_q6["distinct_covered"] >= 14
        and joker_distinct_fibers
        and (t_alpha != top_B_q6)
        and (t_alpha != top_R_q6)
    )
    checks.append({
        "id": "Q6",
        "name": "Martor de Siguranță sub Nul / CSPRNG (E_S >= 0.50, w_0 crește, det G > 0, multiplet distinct de B/R)",
        "pass": bool(q6_pass),
        "detail": {
            "w0_initial": round(w0_initial, 4),
            "w0_final_null": round(w0_final, 6),
            "min_E_s_trajectory": round(min_e_trajectory, 6),
            "final_E_S_null": round(final_e_q6, 6),
            "det_G3_649": round(ev_q6["det_G3"], 6),
            "distinct_covered_649": ev_q6["distinct_covered"],
            "alpha_649": t_alpha,
            "beta_649": t_beta,
            "gamma_649": t_gamma,
            "baseline_B": top_B_q6,
            "baseline_R": top_R_q6,
            "joker_fibers_abc": joker_fibers,
        },
    })

    passed = sum(1 for c in checks if c["pass"])
    peak_mib = round(torch.cuda.max_memory_allocated() / (1024 ** 2), 2) if torch.cuda.is_available() else 0.0
    elapsed = round(time.perf_counter() - t0, 3)

    report = {
        "protocol": "HSV4-P1",
        "protocol_sha256": proto_sha,
        "seal_sha256": hashlib.sha256(seal_path.read_bytes()).hexdigest(),
        "meteo_provenance_sha256": hashlib.sha256(PROVENANCE_JSON.read_bytes()).hexdigest(),
        "meteo_cache_sha256": meteo_sha,
        "core_py_sha256": hashlib.sha256((HERE / "core.py").read_bytes()).hexdigest(),
        "status": "HSV4_QUALIFIED" if passed == 6 else "HSV4_NOT_QUALIFIED",
        "passed": passed,
        "total": 6,
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "peak_vram_mib": peak_mib,
        "elapsed_sec": elapsed,
        "real_ro_archive_read": False,
        "positive_claims_allowed": False,
        "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
    }

    out_dir = HERE / "rezultate"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "CALIFICARE_Q.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    rep = run_qualification()
    print(
        f"=== {rep['status']} ({rep['passed']}/{rep['total']}) | GPU: {rep['device']} | "
        f"VRAM vârf: {rep['peak_vram_mib']} MiB | {rep['elapsed_sec']} s ==="
    )
    for ch in rep["checks"]:
        tag = "PASS" if ch["pass"] else "FAIL"
        print(f"  [{tag}] {ch['id']} — {ch['name']}: {json.dumps(ch['detail'], ensure_ascii=False)}")
    sys.exit(0 if rep["passed"] == 6 else 1)
