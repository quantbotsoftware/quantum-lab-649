#!/usr/bin/env python3
"""Verificator independent Python/NumPy pentru motorul nativ Rust KJ-V5 (PROTOCOL_KJV5_RUST_V2.md §6).

Nu importă niciun modul de producție sau motor anterior: recalculează independent din ecuațiile
matematice (K1 Krawtchouk, K2 Koopman V_2 cu np.linalg.eigh, K3 Schnakenberg V_1, K4 Gauss–Hermite 2D
în complex128 + polinoame simetrice elementare) operatorii și rapoartele de verosimilitate L_{s,m} pe
arhivele RO LIVE, verifică alinierea comparatoarelor B / R / U cu HS-V4 pe toate fluxurile cu aceeași
arhivă, verifică garanția martingală E_s >= 0.50 peste toate cele 22 rulări (12 ablații RO + 10 INTL/RNG)
și certifică sigiliile SHA-256 / permisiunile 0444.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(".")
QL_ROOT = REPO_ROOT / "next_candidate" / "quantum_lab_649"
KJV5_DIR = QL_ROOT / "kj_v5"
REZ_DIR = KJV5_DIR / "rezultate"

WARMUP_STEPS = 100
TAU_SHELL = 128.0
N0_SHELL = 24.0
AMP_SHELL = 0.55
TAU_K2 = 160.0
LAMBDA_K2 = 16.0
AMP_K2 = 2.5
GAIN_K2 = 4.0
SPECTRAL_GAP_EPS = 1e-8
TAU_K3 = 128.0
LAMBDA_K3 = 16.0
K3_LAG_WEIGHTS = (0.55, 0.30, 0.15)

GH14_X = np.array(
    [
        -4.304448570473632,
        -3.4626569336022706,
        -2.7484707249854026,
        -2.0951832585077166,
        -1.4766827311411408,
        -0.8787137873293994,
        -0.29174551067256205,
        0.29174551067256205,
        0.8787137873293994,
        1.4766827311411408,
        2.0951832585077166,
        2.7484707249854026,
        3.4626569336022706,
        4.304448570473632,
    ],
    dtype=np.float64,
)
GH14_WN = np.array(
    [
        4.8681612577483665e-9,
        2.6609913440676266e-6,
        0.00020033955376074378,
        0.004428919106947404,
        0.038650108824253446,
        0.15408333984251354,
        0.3026346268130195,
        0.3026346268130195,
        0.15408333984251354,
        0.038650108824253446,
        0.004428919106947404,
        0.00020033955376074378,
        2.6609913440676266e-6,
        4.8681612577483665e-9,
    ],
    dtype=np.float64,
)

EXPERT_SPECS = [
    ("m0_uniform", 0.50, 0.00, 0.00, "None", 0.00, 0.00),
    ("m1_k1_mild", 0.08, 0.50, 0.00, "None", 0.00, 0.00),
    ("m2_k1_strong", 0.07, 1.00, 0.00, "None", 0.00, 0.00),
    ("m3_k2_anti", 0.09, 0.00, 0.70, "Anti", 0.00, 0.00),
    ("m4_k2_dir", 0.08, 0.00, 0.65, "Dir", 0.00, 0.00),
    ("m5_k3_schnak", 0.06, 0.00, 0.00, "None", 0.50, 0.50),
    ("m6_k1_k2_mild", 0.06, 0.55, 0.55, "Mix", 0.00, 0.00),
    ("m7_full_kjv5", 0.06, 0.75, 0.75, "Mix", 0.45, 0.45),
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_mode_0444(path: Path) -> bool:
    return stat.S_IMODE(path.stat().st_mode) == 0o444


def build_krawtchouk_basis(n: int, r: int, k: int):
    u_min = max(0, k + r - n)
    u_max = min(k, r)
    mean_u = (r * k) / float(n)
    p0 = np.zeros(u_max + 1, dtype=np.float64)
    tot = math.comb(n, k)
    for u in range(u_min, u_max + 1):
        p0[u] = (math.comb(r, u) * math.comb(n - r, k - u)) / float(tot)
    p0 /= p0.sum()

    psi = np.zeros((4, u_max + 1), dtype=np.float64)
    psi[0, u_min : u_max + 1] = 1.0
    active = [False, False, False]
    u_vals = np.arange(u_max + 1, dtype=np.float64)
    for m in range(1, 4):
        v = np.zeros(u_max + 1, dtype=np.float64)
        v[u_min : u_max + 1] = (u_vals[u_min : u_max + 1] - mean_u) ** m
        for _ in range(2):
            for j in range(m):
                if j > 0 and not active[j - 1]:
                    continue
                dot = float(np.sum(p0[u_min : u_max + 1] * v[u_min : u_max + 1] * psi[j, u_min : u_max + 1]))
                v[u_min : u_max + 1] -= dot * psi[j, u_min : u_max + 1]
        norm = math.sqrt(float(np.sum(p0[u_min : u_max + 1] * v[u_min : u_max + 1] ** 2)))
        if norm > 1e-12:
            active[m - 1] = True
            psi[m, u_min : u_max + 1] = v[u_min : u_max + 1] / norm
    return u_min, u_max, p0, psi, active


def project_v2_py(mat: np.ndarray) -> np.ndarray:
    n = mat.shape[0]
    p = mat.copy()
    np.fill_diagonal(p, 0.0)
    row_sums = p.sum(axis=1)
    s_tot = float(row_sums.sum())
    q = p - (row_sums[:, None] + row_sums[None, :]) / (n - 2.0) + s_tot / ((n - 1.0) * (n - 2.0))
    np.fill_diagonal(q, 0.0)
    return q


def project_perp_phi_py(q: np.ndarray, phi: np.ndarray) -> np.ndarray:
    n2 = float(np.sum(phi * phi))
    if n2 <= 1e-15:
        return q.copy()
    return q - (float(np.sum(q * phi)) / n2) * phi


def extremal_modes_py(q_raw: np.ndarray):
    n = q_raw.shape[0]
    fn = float(np.linalg.norm(q_raw, "fro"))
    if fn < 1e-12:
        return 0.0, np.zeros(n), 0.0, np.zeros(n)
    q_tilde = q_raw * (AMP_K2 * math.tanh(GAIN_K2 * fn) / fn)
    q_sym = 0.5 * (q_tilde + q_tilde.T)
    fn_t = float(np.linalg.norm(q_sym, "fro"))
    if fn_t < 1e-13:
        return 0.0, np.zeros(n), 0.0, np.zeros(n)
    evals, evecs = np.linalg.eigh(q_sym)
    if evals[-1] > 1e-12 and (evals[-1] - evals[-2]) > SPECTRAL_GAP_EPS:
        lp = float(evals[-1])
        up = evecs[:, -1].copy()
        up -= up.mean()
        up /= np.linalg.norm(up)
    else:
        lp, up = 0.0, np.zeros(n)
    if evals[0] < -1e-12 and (evals[1] - evals[0]) > SPECTRAL_GAP_EPS:
        lm = float(evals[0])
        um = evecs[:, 0].copy()
        um -= um.mean()
        um /= np.linalg.norm(um)
    else:
        lm, um = 0.0, np.zeros(n)
    return lp, up, lm, um


def normalize_centered_py(h_raw: np.ndarray) -> np.ndarray:
    n = h_raw.shape[0]
    h = h_raw - h_raw.mean()
    nrm = float(np.linalg.norm(h))
    if nrm < 1e-14:
        return np.zeros(n, dtype=np.float64)
    rms = max(nrm / math.sqrt(n), 1e-12)
    h = h * (math.tanh(nrm) / rms)
    return h - h.mean()


def elem_sym_py(z: np.ndarray, max_deg: int) -> np.ndarray:
    deg = min(max_deg, z.shape[0])
    e = np.zeros(deg + 1, dtype=np.complex128)
    e[0] = 1.0 + 0.0j
    for zj in z:
        e[1 : deg + 1] = e[1 : deg + 1] + zj * e[0:deg]
    return e


def gh_nodes_py(gamma_2: float, lp: float, lm: float):
    hp = gamma_2 > 0.0 and lp > 1e-13
    hm = gamma_2 > 0.0 and lm < -1e-13
    if not hp and not hm:
        return [(1.0, 0.0, 0.0)]
    if hp and not hm:
        ap = math.sqrt(2.0 * gamma_2 * lp)
        return [(float(GH14_WN[q]), float(ap * GH14_X[q]), 0.0) for q in range(14)]
    if not hp and hm:
        am = math.sqrt(2.0 * gamma_2 * abs(lm))
        return [(float(GH14_WN[q]), 0.0, float(am * GH14_X[q])) for q in range(14)]
    ap = math.sqrt(2.0 * gamma_2 * lp)
    am = math.sqrt(2.0 * gamma_2 * abs(lm))
    out = []
    for qp in range(14):
        for qm in range(14):
            out.append((float(GH14_WN[qp] * GH14_WN[qm]), float(ap * GH14_X[qp]), float(am * GH14_X[qm])))
    return out


def eval_z_and_subsum_py(
    n: int,
    r: int,
    k: int,
    m_bonus: int | None,
    gamma_sh: float,
    gamma_2: float,
    eta: float,
    eta_b: float,
    theta_sh: np.ndarray,
    theta_b: tuple[float, float],
    h_anti: np.ndarray,
    h_b_anti: np.ndarray,
    modes: tuple[float, np.ndarray, float, np.ndarray],
    d_prev: list[int],
    jb_prev: int | None,
    target_draws: list[tuple[list[int], int | None]],
):
    lp, up, lm, um = modes
    in_d = np.zeros(n, dtype=bool)
    in_d[d_prev] = True
    d_idx = np.array(d_prev, dtype=int)
    dc_idx = np.where(~in_d)[0]
    u_min = max(0, k + r - n)
    u_max = min(k, r)
    g_sh = np.array([math.exp(gamma_sh * theta_sh[u]) if u >= u_min else 0.0 for u in range(u_max + 1)])
    nodes = gh_nodes_py(gamma_2, lp, lm)

    z_main = 0.0
    for wn, ax, ay in nodes:
        re_all = eta * h_anti + ax * up
        im_all = ay * um
        z_all = np.exp(re_all) * (np.cos(im_all) + 1j * np.sin(im_all))
        ed = elem_sym_py(z_all[d_idx], u_max)
        edc = elem_sym_py(z_all[dc_idx], k - u_min)
        acc = 0.0j
        for u in range(u_min, u_max + 1):
            v = k - u
            if u < len(ed) and v < len(edc):
                acc += g_sh[u] * ed[u] * edc[v]
        z_main += wn * acc.real

    pi_b = None
    if m_bonus is not None:
        wb = np.zeros(m_bonus, dtype=np.float64)
        for b in range(m_bonus):
            th_b = gamma_sh * (theta_b[1] if jb_prev == b else theta_b[0])
            wb[b] = math.exp(th_b + eta_b * h_b_anti[b])
        pi_b = wb / wb.sum()

    norm_comb = math.comb(n, k) / float(math.comb(r, k))
    sub_lrs = []
    for d_targ, jb_targ in target_draws:
        if len(d_targ) == k:
            ov = sum(1 for x in d_targ if in_d[x])
            sh = gamma_sh * theta_sh[ov]
            lin = eta * float(np.sum(h_anti[d_targ]))
            sp = float(np.sum(up[d_targ]))
            sm = float(np.sum(um[d_targ]))
            quad = 0.5 * gamma_2 * (lp * sp * sp + lm * sm * sm)
            sum_sub = math.exp(sh + lin + quad)
        else:
            a_idx = np.array([x for x in d_targ if in_d[x]], dtype=int)
            b_idx = np.array([x for x in d_targ if not in_d[x]], dtype=int)
            u_lo = max(0, k - len(b_idx))
            u_hi = min(k, len(a_idx))
            sum_sub = 0.0
            for wn, ax, ay in nodes:
                re_all = eta * h_anti + ax * up
                im_all = ay * um
                z_all = np.exp(re_all) * (np.cos(im_all) + 1j * np.sin(im_all))
                ea = elem_sym_py(z_all[a_idx], u_hi)
                eb = elem_sym_py(z_all[b_idx], k - u_lo)
                acc = 0.0j
                for u in range(u_lo, u_hi + 1):
                    v = k - u
                    if u < len(ea) and v < len(eb):
                        acc += math.exp(gamma_sh * theta_sh[u]) * ea[u] * eb[v]
                sum_sub += wn * acc.real
        lr_c = norm_comb * (sum_sub / z_main)
        if m_bonus is not None and jb_targ is not None:
            lr_c *= m_bonus * float(pi_b[jb_targ])
        sub_lrs.append(lr_c)
    return sub_lrs


def load_ro_canonical_steps_py(game_code: str, n: int, r: int, m_bonus: int | None):
    live_dir = QL_ROOT / "tu3" / "date" / "live"
    cur = json.loads((live_dir / "CURRENT_LIVE.json").read_text())
    vdir = live_dir / cur["version_dir"]
    man = json.loads((vdir / "MANIFEST_LIVE.json").read_text())
    fpath = vdir / man["games"][game_code]["file"]
    by_date: dict[str, list[tuple[list[int], int | None]]] = {}
    for ln in fpath.read_text().splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        b0 = sorted(x - 1 for x in rec["numbers"])
        jb = (rec.get("joker") or rec.get("bonus"))
        jb0 = (jb - 1) if (m_bonus is not None and jb is not None) else None
        by_date.setdefault(rec["draw_date"], []).append((b0, jb0))

    steps = []
    for dt_s in sorted(by_date.keys()):
        drs = sorted(by_date[dt_s])
        m_s = float(len(drs))
        xt = np.full(n, -r / float(n), dtype=np.float64)
        pbar = np.zeros((n, n), dtype=np.float64)
        for b0, _ in drs:
            for i in b0:
                xt[i] += 1.0 / m_s
            for idx_a in range(len(b0)):
                u = b0[idx_a]
                for v in b0[idx_a + 1 :]:
                    pbar[u, v] += 1.0 / m_s
                    pbar[v, u] += 1.0 / m_s
        yt = np.zeros(m_bonus or 0, dtype=np.float64)
        if m_bonus is not None:
            yt[:] = -1.0 / float(m_bonus)
            for _, jb0 in drs:
                if jb0 is not None:
                    yt[jb0] += 1.0 / m_s
        phi_v2 = project_v2_py(pbar)
        phi_n2 = float(np.sum(phi_v2 * phi_v2))
        steps.append((dt_s, drs, xt, yt, pbar, phi_v2, phi_n2))
    return steps


def independent_walkforward_audit_ro(game_code: str, n: int, r: int, k: int, m_bonus: int | None, rust_game_doc: dict):
    steps = load_ro_canonical_steps_py(game_code, n, r, m_bonus)
    _, _, _, draw_psi, _ = build_krawtchouk_basis(n, r, r)
    tkt_umin, tkt_umax, _, tkt_psi, tkt_active = build_krawtchouk_basis(n, r, k)
    psi_b0 = -1.0 / math.sqrt(m_bonus - 1) if m_bonus else 0.0
    psi_b1 = math.sqrt(m_bonus - 1) if m_bonus else 0.0

    audits_by_step = {a["step_index"]: a for a in rust_game_doc["sample_step_audit"]}

    s_sh = np.zeros(3, dtype=np.float64)
    s_sh_b = 0.0
    n_sh = 0.0
    c_to = np.zeros((n, n), dtype=np.float64)
    c_to_b = np.zeros((m_bonus or 0, m_bonus or 0), dtype=np.float64)
    c_xb = np.zeros((n, m_bonus or 0), dtype=np.float64)
    n_k3 = 0.0

    priors = np.array([sp[1] for sp in EXPERT_SPECS], dtype=np.float64)
    log_w = np.log(priors)

    rho_sh = math.exp(-1.0 / TAU_SHELL)
    rho_k2 = math.exp(-1.0 / TAU_K2)
    rho_k3 = math.exp(-1.0 / TAU_K3)

    max_err = 0.0
    checked_audits = 0

    # Rulăm exact tranzițiile K1 + K3 pe toți pașii și evaluăm complet K1–K4 pe pașii din sample_step_audit
    # plus verificăm identitatea algebrică pe fiecare pas auditat!
    for s_idx, step_cur in enumerate(steps):
        if s_idx in audits_by_step:
            aud = audits_by_step[s_idx]
            assert aud["date"] == step_cur[0], f"Date mismatch at {s_idx}"

            # K1
            c_m = np.zeros(3, dtype=np.float64)
            for m_ord in range(1, 4):
                if tkt_active[m_ord - 1]:
                    c_m[m_ord - 1] = AMP_SHELL * math.tanh(s_sh[m_ord - 1] / (n_sh + N0_SHELL))
            theta_sh = np.zeros(tkt_umax + 1, dtype=np.float64)
            for u in range(tkt_umin, tkt_umax + 1):
                theta_sh[u] = float(np.sum(c_m * tkt_psi[1:4, u]))
            theta_b = (0.0, 0.0)
            if m_bonus is not None:
                cb = AMP_SHELL * math.tanh(s_sh_b / (n_sh + N0_SHELL))
                theta_b = (cb * psi_b0, cb * psi_b1)

            err_sh = float(np.max(np.abs(c_m - np.array(aud["shell_coeffs"]))))

            # K2
            phi_trig = steps[s_idx - 1][5]
            z2_eff = LAMBDA_K2
            acc_dir = np.zeros((n, n), dtype=np.float64)
            acc_anti = np.zeros((n, n), dtype=np.float64)
            wt = 1.0
            for t in range(s_idx - 1, 0, -1):
                st_prev = steps[t - 1]
                st_t = steps[t]
                z2_eff += wt * st_prev[6]
                kf = float(np.sum(st_prev[4] * phi_trig))
                kr = float(np.sum(st_t[4] * phi_trig))
                acc_dir += (wt * kf) * st_t[4]
                acc_anti += (0.5 * wt * kf) * st_t[4] - (0.5 * wt * kr) * st_prev[4]
                wt *= rho_k2
            acc_dir /= z2_eff
            acc_anti /= z2_eff
            q_dir_raw = project_v2_py(acc_dir)
            q_anti_raw = project_perp_phi_py(project_v2_py(acc_anti), phi_trig)
            q_mix_raw = 0.5 * (q_anti_raw + q_dir_raw)

            err_qa = abs(float(np.linalg.norm(q_anti_raw, "fro")) - aud["q_anti_raw_norm"])
            err_qd = abs(float(np.linalg.norm(q_dir_raw, "fro")) - aud["q_dir_raw_norm"])
            lie_dot = abs(float(np.sum(q_anti_raw * phi_trig)))
            assert lie_dot < 1e-13, f"Lie orthogonality violated: {lie_dot}"

            m_zero = (0.0, np.zeros(n), 0.0, np.zeros(n))
            m_anti = extremal_modes_py(q_anti_raw)
            m_dir = extremal_modes_py(q_dir_raw)
            m_mix = extremal_modes_py(q_mix_raw)

            err_la = max(abs(m_anti[0] - aud["modes_anti_lambda"][0]), abs(m_anti[2] - aud["modes_anti_lambda"][1]))
            err_ld = max(abs(m_dir[0] - aud["modes_dir_lambda"][0]), abs(m_dir[2] - aud["modes_dir_lambda"][1]))

            # K3
            denom_k3 = LAMBDA_K3 + n_k3
            j1 = 0.5 * (c_to - c_to.T) / denom_k3
            h_anti = normalize_centered_py(j1.T @ steps[s_idx - 1][2])
            h_b_anti = np.zeros(m_bonus or 0, dtype=np.float64)
            if m_bonus is not None:
                jb1 = 0.5 * (c_to_b - c_to_b.T) / denom_k3
                hb_raw = (jb1.T @ steps[s_idx - 1][3]) + 0.5 * ((c_xb / denom_k3).T @ steps[s_idx - 1][2])
                h_b_anti = normalize_centered_py(hb_raw)

            # K4: step_lrs peste toți cei 8 experți
            prev_drs = steps[s_idx - 1][1]
            targ_drs = step_cur[1]
            py_step_lrs = [1.0]
            for m_i in range(1, 8):
                _, _, g_sh_m, g_2_m, v2_src, eta_m, eta_bm = EXPERT_SPECS[m_i]
                md = {"None": m_zero, "Anti": m_anti, "Dir": m_dir, "Mix": m_mix}[v2_src]
                per_targ = np.zeros(len(targ_drs), dtype=np.float64)
                for dp, jbp in prev_drs:
                    lrs_cond = eval_z_and_subsum_py(
                        n, r, k, m_bonus, g_sh_m, g_2_m, eta_m, eta_bm,
                        theta_sh, theta_b, h_anti, h_b_anti, md, dp, jbp, targ_drs,
                    )
                    per_targ += np.array(lrs_cond) / float(len(prev_drs))
                py_step_lrs.append(float(np.mean(per_targ)))

            err_lrs = float(np.max(np.abs(np.array(py_step_lrs) - np.array(aud["step_lrs"]))))
            step_max_err = max(err_sh, err_qa, err_qd, err_la, err_ld, err_lrs)
            max_err = max(max_err, step_max_err)
            checked_audits += 1

        # Actualizare cauzală K1 + K3 pentru tranziția s_idx - 1 -> s_idx
        if s_idx >= 1:
            prev_drs = steps[s_idx - 1][1]
            cur_drs = step_cur[1]
            pair_cnt = float(len(prev_drs) * len(cur_drs))
            bar_psi = np.zeros(3, dtype=np.float64)
            bar_b = 0.0
            for dp, jbp in prev_drs:
                sp_set = set(dp)
                for dc, jbc in cur_drs:
                    ov = sum(1 for x in dc if x in sp_set)
                    bar_psi += draw_psi[1:4, ov] / pair_cnt
                    if m_bonus is not None and jbp is not None and jbc is not None:
                        bar_b += (psi_b1 if jbp == jbc else psi_b0) / pair_cnt
            s_sh = rho_sh * s_sh + bar_psi
            s_sh_b = rho_sh * s_sh_b + bar_b
            n_sh = rho_sh * n_sh + 1.0

            c_to *= rho_k3
            c_to_b *= rho_k3
            c_xb *= rho_k3
            n_k3 = rho_k3 * n_k3 + 1.0
            for lag_i, w_lag in enumerate(K3_LAG_WEIGHTS):
                lag = lag_i + 1
                if s_idx >= lag:
                    st_l = steps[s_idx - lag]
                    c_to += w_lag * np.outer(st_l[2], step_cur[2])
                    if m_bonus is not None:
                        c_to_b += w_lag * np.outer(st_l[3], step_cur[3])
            if m_bonus is not None:
                c_xb += np.outer(steps[s_idx - 1][2], step_cur[3])

    return checked_audits, max_err


def main() -> int:
    checks = []

    # V1: Sigilii SHA-256 și permisiuni 0444
    sealed_files = [
        KJV5_DIR / "PROTOCOL_KJV5_RUST_V2.md",
        KJV5_DIR / "SIGILIU_PROTOCOL_KJV5.json",
        KJV5_DIR / "INCIDENT_TEHNIC_01.json",
        KJV5_DIR / "AMENDAMENT_TEHNIC_01.md",
        KJV5_DIR / "SIGILIU_COD_KJV5.json",
        REZ_DIR / "CALIFICARE_Q_KJV5.json",
        REZ_DIR / "WALKFORWARD_RO_KJV5.json",
        REZ_DIR / "ABLATIE_RO_KJV5.json",
        REZ_DIR / "INTERNATIONAL_RNG_KJV5.json",
    ]
    all_exist = all(p.exists() for p in sealed_files)
    all_0444 = all_exist and all(is_mode_0444(p) for p in sealed_files)

    qual = json.loads((REZ_DIR / "CALIFICARE_Q_KJV5.json").read_text())
    seal_code = json.loads((KJV5_DIR / "SIGILIU_COD_KJV5.json").read_text())
    wf_ro = json.loads((REZ_DIR / "WALKFORWARD_RO_KJV5.json").read_text())
    abl_ro = json.loads((REZ_DIR / "ABLATIE_RO_KJV5.json").read_text())
    intl_kj = json.loads((REZ_DIR / "INTERNATIONAL_RNG_KJV5.json").read_text())

    ui_replacements = {}
    for rep_p in sorted(KJV5_DIR.glob("INLOCUIRE_UI_*.json")):
        if not is_mode_0444(rep_p):
            all_0444 = False
        rep_doc = json.loads(rep_p.read_text())
        for rel_f, rinfo in rep_doc.get("replacements", {}).items():
            if rel_f.startswith("rust_core_v2/ui/"):
                ui_replacements[rel_f] = (rinfo["previous_sha256"], rinfo["new_sha256"])

    code_hashes_ok = True
    for rel, exp in qual["kjv5_code_sha256"].items():
        if sha256_file(REPO_ROOT / rel) != exp:
            code_hashes_ok = False
    for rel, exp in seal_code["code_sha256"].items():
        cur_sha = sha256_file(REPO_ROOT / rel)
        if cur_sha != exp:
            if rel in ui_replacements and ui_replacements[rel] == (exp, cur_sha):
                continue
            code_hashes_ok = False

    v1_ok = all_0444 and code_hashes_ok
    checks.append(
        {
            "id": "V1_SEALS_0444_AND_CODE_SHA256",
            "pass": v1_ok,
            "detail": f"9 fișiere 0444={all_0444}, sha256_cod_intact={code_hashes_ok}",
        }
    )

    # V2: Calificare pre-arhivă Q1–Q6
    v2_ok = (
        qual["status"] == "KJV5_QUALIFIED"
        and qual["passed"] == 6
        and qual["total"] == 6
        and qual["archive_files_read"] == 0
        and qual["technical_incidents"] == 1
        and qual["positive_claims_allowed"] is False
    )
    checks.append(
        {
            "id": "V2_PREARCHIVE_QUALIFICATION_6_OF_6",
            "pass": v2_ok,
            "detail": f"status={qual['status']}, passed={qual['passed']}/{qual['total']}, incidents={qual['technical_incidents']}",
        }
    )

    # V3: Recalculare independentă Python/NumPy a operatorilor K1–K4 și step_lrs pe 649, 540, joker
    max_step_err = 0.0
    total_audit_pts = 0
    for gcode, (n, r, k, mb) in [
        ("649", (49, 6, 6, None)),
        ("540", (40, 6, 5, None)),
        ("joker", (45, 5, 5, 20)),
    ]:
        cnt, err = independent_walkforward_audit_ro(gcode, n, r, k, mb, wf_ro["games"][gcode])
        total_audit_pts += cnt
        max_step_err = max(max_step_err, err)

    v3_ok = total_audit_pts == 9 and max_step_err < 1e-11
    checks.append(
        {
            "id": "V3_INDEPENDENT_PYTHON_NUMPY_K1_K4_PARITY",
            "pass": v3_ok,
            "detail": f"puncte_audit={total_audit_pts}, max_abs_err={max_step_err:.3e} (< 1e-11)",
        }
    )

    # V4: Alinierea exactă a comparatoarelor B / R / U cu HS-V4 pe toate arhivele identice (RO + 10 INTL/RNG)
    hsv4_wf = json.loads((QL_ROOT / "hs_v4" / "rezultate" / "WALKFORWARD_RO.json").read_text())
    hsv4_intl = json.loads((QL_ROOT / "hs_v4" / "rezultate" / "INTERNATIONAL_RNG_EVAL.json").read_text())
    comp_aligned = True
    comp_streams_checked = 0
    max_comp_float_diff = 0.0

    for gcode in ["649", "540", "joker"]:
        kj_g = wf_ro["games"][gcode]
        hs_g = hsv4_wf["games"][gcode]
        if kj_g["archive"]["evaluated_steps"] == hs_g["windows"]["total"]["n_steps"]:
            kw = kj_g["windows"]["total"]
            hw = hs_g["windows"]["total"]
            if kw["hits_B"] != hw["hits_B"] or kw["hits_R"] != hw["hits_R"]:
                comp_aligned = False
            for fk in ["log_score_U", "log_score_B", "log_score_R", "brier_U", "brier_B", "brier_R"]:
                d = abs(kw[fk] - hw[fk])
                max_comp_float_diff = max(max_comp_float_diff, d)
                if d > 2e-4:
                    comp_aligned = False
            comp_streams_checked += 1

    for grp in ["mechanical_external", "electronic_rng"]:
        for scode, kj_s in intl_kj[grp].items():
            hs_s = hsv4_intl[grp][scode]["configs"]["Full_HSV4"]
            kw = kj_s["windows"]["total"]
            hw = hs_s["windows"]["total"]
            if kw["hits_B"] != hw["hits_B"] or kw["hits_R"] != hw["hits_R"]:
                comp_aligned = False
            for fk in ["log_score_U", "log_score_B", "log_score_R", "brier_U", "brier_B", "brier_R"]:
                d = abs(kw[fk] - hw[fk])
                max_comp_float_diff = max(max_comp_float_diff, d)
                if d > 2e-4:
                    comp_aligned = False
            comp_streams_checked += 1

    v4_ok = comp_aligned and comp_streams_checked >= 10
    checks.append(
        {
            "id": "V4_COMPARATOR_B_R_U_EXACT_ALIGNMENT_WITH_HSV4",
            "pass": v4_ok,
            "detail": f"fluxuri_aliniate={comp_streams_checked}, max_diff_rotunjire={max_comp_float_diff:.2e}",
        }
    )

    # V5: Garanția martingală E_s >= 0.50 pe toate cele 22 rulări + Skandináv 1312 zile + positive_claims_allowed=false
    min_e_global = float("inf")
    runs_checked = 0
    pca_all_false = (
        wf_ro["positive_claims_allowed"] is False
        and abl_ro["positive_claims_allowed"] is False
        and intl_kj["positive_claims_allowed"] is False
    )

    for gcode in ["649", "540", "joker"]:
        for ckey, crep in abl_ro["games"][gcode]["configs"].items():
            me = crep["martingale_trajectory"]["min_E_s"]
            min_e_global = min(min_e_global, me)
            if crep["positive_claims_allowed"] is not False:
                pca_all_false = False
            runs_checked += 1

    for grp in ["mechanical_external", "electronic_rng"]:
        for scode, srep in intl_kj[grp].items():
            me = srep["martingale_trajectory"]["min_E_s"]
            min_e_global = min(min_e_global, me)
            if srep["positive_claims_allowed"] is not False:
                pca_all_false = False
            runs_checked += 1

    sk_ok = (
        intl_kj["paired_skandinav_comparison"]["same_dates_verified"] is True
        and intl_kj["paired_skandinav_comparison"]["evaluated_steps"] == 1312
    )
    v5_ok = runs_checked == 22 and min_e_global >= 0.50 - 1e-12 and sk_ok and pca_all_false
    checks.append(
        {
            "id": "V5_MARTINGALE_E_GE_050_ALL_22_RUNS_AND_SKANDINAV",
            "pass": v5_ok,
            "detail": f"rulări={runs_checked}, min_E_s_global={min_e_global:.8f}, skandinav_1312={sk_ok}, pca_false={pca_all_false}",
        }
    )

    passed_n = sum(1 for c in checks if c["pass"])
    verdict = "PASS" if passed_n == len(checks) else "FAIL"
    out_doc = {
        "protocol_id": "KJV5-RCV2-P1",
        "verifier": "kj_v5/verifica_kjv5.py",
        "verdict": verdict,
        "passed_checks": passed_n,
        "total_checks": len(checks),
        "max_abs_step_err": max_step_err,
        "min_E_s_global_22_runs": min_e_global,
        "comparator_streams_aligned": comp_streams_checked,
        "checks": checks,
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "positive_claims_allowed": False,
    }

    out_path = REZ_DIR / "VERIFICARE_KJV5.json"
    if out_path.exists():
        os.chmod(out_path, 0o644)
    out_path.write_text(json.dumps(out_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(out_path, 0o444)
    print(json.dumps(out_doc, indent=2, ensure_ascii=False))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
