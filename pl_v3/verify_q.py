"""PL-V3 — Verificarea algebrică și tehnică Q1..Q6 pe GPU (fără atingerea arhivei reale).

Rulează cu: .venv/bin/python -B pl_v3/verify_q.py
Scrie certificatul în pl_v3/rezultate/CALIFICARE_Q.json. Calcul clasic; positive_claims_allowed = False.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
if str(QL) not in sys.path:
    sys.path.insert(0, str(QL))

from pl_v3.core import (  # noqa: E402
    DEFAULT_PARAMS,
    SimplicialTopology,
    advance_steps,
    cauchy_binet_exact_ek,
    evaluate_full_space,
    extract_step_slices,
    forward_operators_from_state,
    init_state,
    su3_exp_hermitian,
    unrolled_hermitian_cholesky_logdet,
)


def _synth_universe(N: int, r: int, n_steps: int, seed: int, device: torch.device, joker_m: int | None = None):
    """Generează un univers sintetic fără întoarcere (cu zile duble în step_offsets) strict pentru Q1..Q6."""
    rng = np.random.default_rng(seed)
    offs = [0]
    rows = []
    j_rows = []
    for s in range(n_steps):
        m_s = 2 if (s % 11 == 5) else 1  # zile cu dublă extragere
        for _ in range(m_s):
            # Ponderea variază ușor cu s pentru a activa toate canalele neabeliene fără degenerare banală
            logits = 0.35 * np.sin(2.0 * math.pi * (np.arange(N) / float(N) + s / 19.0))
            probs = np.exp(logits)
            probs /= probs.sum()
            chosen = rng.choice(N, size=r, replace=False, p=probs)
            oh = np.zeros(N, dtype=np.float32)
            oh[chosen] = 1.0
            rows.append(oh)
            if joker_m is not None:
                jp = np.exp(0.30 * np.cos(2.0 * math.pi * (np.arange(joker_m) / float(joker_m) - s / 13.0)))
                jp /= jp.sum()
                jb = int(rng.choice(joker_m, p=jp))
                joh = np.zeros(joker_m, dtype=np.float32)
                joh[jb] = 1.0
                j_rows.append(joh)
        offs.append(len(rows))

    onehot = torch.as_tensor(np.stack(rows), dtype=torch.float32, device=device)
    step_offsets = torch.as_tensor(offs, dtype=torch.int64, device=device)
    joker_oh = torch.as_tensor(np.stack(j_rows), dtype=torch.float32, device=device) if joker_m is not None else None
    return onehot, step_offsets, joker_oh


def _baseline_top_k(onehot: torch.Tensor, k: int) -> tuple[list[int], list[int]]:
    """Reperele canonice B (frecvență brută) și R (recență exponențială τ=26) în 1-based."""
    H = onehot.detach().cpu().numpy().astype(np.float64)
    freq = H.sum(axis=0)
    top_B = sorted((int(x) + 1) for x in np.argsort(-freq, kind="mergesort")[:k])
    T = H.shape[0]
    decay = np.power(2.0, -np.arange(T - 1, -1, -1, dtype=np.float64) / 26.0)
    rec = (H * decay[:, None]).sum(axis=0)
    top_R = sorted((int(x) + 1) for x in np.argsort(-rec, kind="mergesort")[:k])
    return top_B, top_R


def run_qualification() -> dict:
    t0 = time.perf_counter()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    checks = []

    # Pregătire stare 6/49 pe univers sintetic cu 45 de pași-zi (inclusiv zile duble)
    topo_649 = SimplicialTopology(N=49, r_draw=6, k_ticket=6, device=device)
    oh_649, offs_649, _ = _synth_universe(49, 6, n_steps=45, seed=20261101, device=device)
    slices_649 = extract_step_slices(oh_649, offs_649)
    st_649 = advance_steps(init_state(topo_649), topo_649, slices_649)
    ops_649 = forward_operators_from_state(st_649, topo_649)

    # ------------------------------------------------------------------
    # Q1: Identitatea Analitică Cauchy-Binet pe toate cele 13.983.816 stări (6/49) + 658.008 (5/40)
    # ------------------------------------------------------------------
    ev_det_649 = evaluate_full_space(topo_649, ops_649, pure_determinantal=True, precision_c128=True)
    ek_649 = cauchy_binet_exact_ek(ops_649["k_eigs"], 6)
    rel_err_649 = abs(ev_det_649["Z_exact"] - ek_649) / max(ek_649, 1e-30)

    # Cross-check independent Cholesky despachetat vs NumPy CPU slogdet pe 64 submatrici
    comb_sample = topo_649.unrank_chunk(100_000, 100_064)
    K_sub = ops_649["K_kernel"][comb_sample.unsqueeze(2), comb_sample.unsqueeze(1)]
    ld_gpu = unrolled_hermitian_cholesky_logdet(K_sub, 6).detach().cpu().numpy()
    _, ld_np = np.linalg.slogdet(K_sub.detach().cpu().numpy())
    chol_vs_np_err = float(np.max(np.abs(ld_gpu - ld_np)))

    # Verificare și pe 5/40 (N=40, r=6, k=5 -> 658.008 stări)
    topo_540 = SimplicialTopology(N=40, r_draw=6, k_ticket=5, device=device)
    oh_540, offs_540, _ = _synth_universe(40, 6, n_steps=35, seed=20260540, device=device)
    st_540 = advance_steps(init_state(topo_540), topo_540, extract_step_slices(oh_540, offs_540))
    ops_540 = forward_operators_from_state(st_540, topo_540)
    ev_det_540 = evaluate_full_space(topo_540, ops_540, pure_determinantal=True, precision_c128=True)
    ek_540 = cauchy_binet_exact_ek(ops_540["k_eigs"], 5)
    rel_err_540 = abs(ev_det_540["Z_exact"] - ek_540) / max(ek_540, 1e-30)
    marg_sum_err = abs(float(ev_det_649["pi_inclusion"].sum().item()) - 6.0)

    q1_pass = (rel_err_649 < 1e-11) and (rel_err_540 < 1e-11) and (chol_vs_np_err < 1e-13) and (marg_sum_err < 1e-11)
    checks.append({
        "id": "Q1",
        "name": "Cauchy-Binet exact pe 13.983.816 (6×6) și 658.008 (5×5) determinanți",
        "pass": bool(q1_pass),
        "detail": {
            "rel_err_649": rel_err_649,
            "rel_err_540": rel_err_540,
            "cholesky_vs_numpy_err": chol_vs_np_err,
            "marginal_sum_err": marg_sum_err,
            "eval_649_sec": round(ev_det_649["eval_sec"], 4),
        },
    })

    # ------------------------------------------------------------------
    # Q2: Ortogonalitatea Pitagora-Hodge & Unitaritatea Varietății SU(3)
    # ------------------------------------------------------------------
    U = st_649.U_full
    I3 = torch.eye(3, dtype=torch.complex128, device=device)
    unit_err = float(torch.linalg.matrix_norm(torch.matmul(U.conj().transpose(-1, -2), U) - I3, ord="fro").max().item())
    det_err = float((torch.linalg.det(U) - 1.0).abs().max().item())
    adj_err = float((U.permute(1, 0, 2, 3) - U.conj().transpose(-1, -2)).abs().max().item())
    hodge_orth_err = float(ops_649["hodge_inner_err"])
    div_curl_err = float(ops_649["delta1_curl"].abs().max().item())
    recon_j_err = float((ops_649["J_1form"] - ops_649["J_exact"] - ops_649["J_curl"]).abs().max().item())

    q2_pass = (
        unit_err < 1e-13
        and det_err < 1e-13
        and adj_err < 1e-14
        and hodge_orth_err < 1e-13
        and div_curl_err < 1e-13
        and recon_j_err < 1e-14
    )
    checks.append({
        "id": "Q2",
        "name": "Ortogonalitate Pitagora-Hodge & Unitaritate/Adjoint SU(3)",
        "pass": bool(q2_pass),
        "detail": {
            "su3_unitarity_err": unit_err,
            "su3_det_err": det_err,
            "su3_adjoint_err": adj_err,
            "hodge_orth_err": hodge_orth_err,
            "delta1_curl_err": div_curl_err,
            "curl_energy_fraction": round(ops_649["curl_energy_ratio"], 6),
        },
    })

    # ------------------------------------------------------------------
    # Q3: Invarianță Gauge Locală SU(3) & Independență de Faza Solverului eigh
    # ------------------------------------------------------------------
    ev_full_649 = evaluate_full_space(topo_649, ops_649, pure_determinantal=False, precision_c128=True)
    gen_g = torch.Generator(device=device).manual_seed(777)
    rand_coeff = torch.randn((49, 8), generator=gen_g, dtype=torch.float64, device=device)
    H_omega = torch.einsum("na,aij->nij", rand_coeff.to(torch.complex128), topo_649.gell_mann)
    Omega = su3_exp_hermitian(H_omega)  # [49, 3, 3] ∈ SU(3)

    st_gauged = st_649.clone()
    st_gauged.U_full = torch.einsum("iab,ijbc,jdc->ijad", Omega, st_649.U_full, Omega.conj())
    twist_phases = torch.randn(3 * 49, generator=gen_g, dtype=torch.float64, device=device) * math.pi
    ops_gauged = forward_operators_from_state(st_gauged, topo_649, eigh_phase_twist=twist_phases)
    ev_gauged = evaluate_full_space(topo_649, ops_gauged, pure_determinantal=False, precision_c128=True)

    wilson_g_err = float((ops_gauged["W_faces"] - ops_649["W_faces"]).abs().max().item())
    kernel_g_err = float((ops_gauged["K_kernel"] - ops_649["K_kernel"]).abs().max().item())
    logz_g_err = abs(ev_gauged["log_Z"] - ev_full_649["log_Z"])
    pi_g_err = float((ev_gauged["pi_inclusion"] - ev_full_649["pi_inclusion"]).abs().max().item())

    q3_pass = (wilson_g_err < 1e-13) and (kernel_g_err < 1e-12) and (logz_g_err < 1e-12) and (pi_g_err < 1e-12)
    checks.append({
        "id": "Q3",
        "name": "Invarianță Gauge Locală SU(3) + Independență Faze eigh",
        "pass": bool(q3_pass),
        "detail": {
            "wilson_err": wilson_g_err,
            "kernel_K_err": kernel_g_err,
            "log_Z_err": logz_g_err,
            "pi_marginal_err": pi_g_err,
        },
    })

    # ------------------------------------------------------------------
    # Q4: Echivarianță Exactă S_49 (6/49) ȘI S_45 × S_20 pe 24.435.180 stări (Joker)
    # ------------------------------------------------------------------
    rng_p = np.random.default_rng(4242)
    perm_49 = torch.as_tensor(rng_p.permutation(49), dtype=torch.long, device=device)
    inv_perm_49 = torch.argsort(perm_49)
    # σH: bila veche i se mută pe poziția nouă inv_perm_49[i], deci oh_perm[:, new_pos] = oh[:, perm_49[new_pos]]
    oh_649_perm = oh_649[:, perm_49]
    st_649_p = advance_steps(init_state(topo_649), topo_649, extract_step_slices(oh_649_perm, offs_649))
    ops_649_p = forward_operators_from_state(st_649_p, topo_649)
    ev_649_p = evaluate_full_space(topo_649, ops_649_p, pure_determinantal=False, precision_c128=True)
    pi_equiv_649_err = float((ev_649_p["pi_inclusion"] - ev_full_649["pi_inclusion"][perm_49]).abs().max().item())

    # Joker bipartit S_45 × S_20
    topo_jok = SimplicialTopology(N=45, r_draw=5, k_ticket=5, device=device, joker_m=20)
    oh_j, offs_j, joh_j = _synth_universe(45, 5, n_steps=35, seed=20260999, device=device, joker_m=20)
    st_j = advance_steps(init_state(topo_jok), topo_jok, extract_step_slices(oh_j, offs_j, joh_j))
    ops_j = forward_operators_from_state(st_j, topo_jok)
    ev_j = evaluate_full_space(topo_jok, ops_j, pure_determinantal=False, precision_c128=True)

    perm_45 = torch.as_tensor(rng_p.permutation(45), dtype=torch.long, device=device)
    perm_20 = torch.as_tensor(rng_p.permutation(20), dtype=torch.long, device=device)
    st_j_p = advance_steps(
        init_state(topo_jok),
        topo_jok,
        extract_step_slices(oh_j[:, perm_45], offs_j, joh_j[:, perm_20]),
    )
    ops_j_p = forward_operators_from_state(st_j_p, topo_jok)
    ev_j_p = evaluate_full_space(topo_jok, ops_j_p, pure_determinantal=False, precision_c128=True)

    pi_equiv_45_err = float((ev_j_p["pi_inclusion"] - ev_j["pi_inclusion"][perm_45]).abs().max().item())
    pi_equiv_20_err = float((ev_j_p["joker_prob"] - ev_j["joker_prob"][perm_20]).abs().max().item())

    # Biletul fundamental permutat: dacă new_pos este în ev_649_p, bila originală este perm_49[new_pos]
    orig_alpha = sorted(ev_full_649["variants"][0]["ticket"])
    perm_alpha_mapped = sorted(int(perm_49[b - 1].item()) + 1 for b in ev_649_p["variants"][0]["ticket"])
    ticket_equiv_ok = (orig_alpha == perm_alpha_mapped)

    q4_pass = (
        pi_equiv_649_err < 1e-11
        and pi_equiv_45_err < 1e-11
        and pi_equiv_20_err < 1e-11
        and ticket_equiv_ok
    )
    checks.append({
        "id": "Q4",
        "name": "Echivarianță S_49 (6/49) și S_45 × S_20 (Joker, 24.435.180 stări)",
        "pass": bool(q4_pass),
        "detail": {
            "pi_equiv_649_err": pi_equiv_649_err,
            "pi_equiv_joker45_err": pi_equiv_45_err,
            "pi_equiv_joker20_err": pi_equiv_20_err,
            "ground_ticket_equivariant": ticket_equiv_ok,
            "joker_eval_sec": round(ev_j["eval_sec"], 4),
            "joker_s_vn": round(float(ops_j["joker_pack"]["s_vn"].item()), 6),
        },
    })

    # ------------------------------------------------------------------
    # Q5: Cauzalitate Strictă pe step_offsets & Rulare Incrementală == Full
    # ------------------------------------------------------------------
    s_cut = 38
    draw_cut = int(offs_649[s_cut].item())
    # Adăugăm extrageri viitoare complet diferite după s_cut și verificăm că la pasul s_cut nu pătrunde nimic
    oh_mod = oh_649.clone()
    oh_mod[draw_cut:] = 0.0
    oh_mod[draw_cut:, :6] = 1.0

    st_trunc_a = advance_steps(init_state(topo_649), topo_649, extract_step_slices(oh_649[:draw_cut], offs_649[: s_cut + 1]))
    st_trunc_b = advance_steps(init_state(topo_649), topo_649, extract_step_slices(oh_mod, offs_649)[:s_cut])
    causal_u_err = float((st_trunc_a.U_full - st_trunc_b.U_full).abs().max().item())

    # Avansăm incremental st_trunc_a pe ultimii 7 pași (38 -> 45) și comparăm cu st_649 (0 -> 45)
    st_inc = advance_steps(st_trunc_a.clone(), topo_649, slices_649[s_cut:])
    inc_u_err = float((st_inc.U_full - st_649.U_full).abs().max().item())
    ops_inc = forward_operators_from_state(st_inc, topo_649)
    inc_k_err = float((ops_inc["K_kernel"] - ops_649["K_kernel"]).abs().max().item())

    q5_pass = (causal_u_err == 0.0) and (inc_u_err < 1e-13) and (inc_k_err < 1e-13)
    checks.append({
        "id": "Q5",
        "name": "Cauzalitate strictă step_offsets (inclusiv zile duble) & Incremental == Full",
        "pass": bool(q5_pass),
        "detail": {
            "future_leak_U_err": causal_u_err,
            "incremental_U_err": inc_u_err,
            "incremental_K_err": inc_k_err,
        },
    })

    # ------------------------------------------------------------------
    # Q6: Multiplet Jastrow Ortogonal (α, β, γ) & Decizie Distinctă de B și R
    # ------------------------------------------------------------------
    top_B, top_R = _baseline_top_k(oh_649, 6)
    v649 = ev_full_649["variants"]
    t_a, t_b, t_c = v649[0]["ticket"], v649[1]["ticket"], v649[2]["ticket"]

    sets = [set(t_a), set(t_b), set(t_c)]
    G3 = np.array([[len(sets[u] & sets[v]) / 6.0 for v in range(3)] for u in range(3)], dtype=np.float64)
    det_G3 = float(np.linalg.det(G3))

    vj = ev_j["variants"]
    joker_fibers = [vj[0]["joker"], vj[1]["joker"], vj[2]["joker"]]
    joker_distinct_fibers = len(set(joker_fibers)) == 3
    distinct_from_BR = (t_a != top_B) and (t_a != top_R)

    q6_pass = (
        det_G3 > 1e-4
        and ev_full_649["distinct_covered"] >= 14
        and joker_distinct_fibers
        and distinct_from_BR
    )
    checks.append({
        "id": "Q6",
        "name": "Multiplet Coulomb-Jastrow ortogonal (det G > 0) & distinct de B și R",
        "pass": bool(q6_pass),
        "detail": {
            "alpha_649": t_a,
            "beta_649": t_b,
            "gamma_649": t_c,
            "baseline_B": top_B,
            "baseline_R": top_R,
            "det_G3_649": round(det_G3, 6),
            "distinct_covered_649": ev_full_649["distinct_covered"],
            "joker_fibers_abc": joker_fibers,
        },
    })

    passed = sum(1 for c in checks if c["pass"])
    peak_mib = round(torch.cuda.max_memory_allocated() / (1024 ** 2), 2) if torch.cuda.is_available() else 0.0
    total_sec = round(time.perf_counter() - t0, 3)

    seal_path = HERE / "SIGILIU_PROTOCOL_PLV3.json"
    seal_sha = hashlib.sha256(seal_path.read_bytes()).hexdigest()
    core_sha = hashlib.sha256((HERE / "core.py").read_bytes()).hexdigest()

    report = {
        "protocol": "PLV3-P1",
        "seal_sha256": seal_sha,
        "core_py_sha256": core_sha,
        "status": "PLV3_QUALIFIED" if passed == 6 else "PLV3_NOT_QUALIFIED",
        "passed": passed,
        "total": 6,
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "peak_vram_mib": peak_mib,
        "elapsed_sec": total_sec,
        "positive_claims_allowed": False,
        "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
    }

    out_dir = HERE / "rezultate"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "CALIFICARE_Q.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


if __name__ == "__main__":
    rep = run_qualification()
    print(f"=== {rep['status']} ({rep['passed']}/{rep['total']}) | GPU: {rep['device']} | VRAM vârf: {rep['peak_vram_mib']} MiB | {rep['elapsed_sec']} s ===")
    for ch in rep["checks"]:
        st = "PASS" if ch["pass"] else "FAIL"
        print(f"  [{st}] {ch['id']} — {ch['name']}: {json.dumps(ch['detail'], ensure_ascii=False)}")
    sys.exit(0 if rep["passed"] == 6 else 1)
