"""PL-V3 UI — Randarea multipletului Coulomb-Jastrow (α, β, γ) și a telemetriei predictive/fizice (0 / 6 porți)
pe toate cele 3 moduri din bara laterală (`649`, `540`, `joker`).

Protocol: `pl_v3/PROTOCOL_PLV3_UI.md` (sigilat în `pl_v3/SIGILIU_PLV3_UI.json` ÎNAINTE de acest fișier).
Sincronizare automată cu `parser_multi.live_key(mode)` prin `pl_v3.walkforward.get_or_advance_live(mode)`.
Calcul clasic; variantele sunt moduri determinantale/Jastrow, NU predicții cu avantaj demonstrat.
`positive_claims_allowed=false`.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
TU3 = QL / "tu3"
for _p in (str(QL), str(TU3)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import parser_multi as PM  # noqa: E402
from pl_v3.core import DEFAULT_PARAMS  # noqa: E402
from pl_v3.walkforward import GAME_CONFIGS, get_or_advance_live  # noqa: E402

HONEST_LABEL = (
    "PLV3_NO_PROMOTION_EXPLORATORY · 0 / 6 porți · calcul clasic · "
    "variantele sunt moduri determinantale/Jastrow, NU predicții cu avantaj demonstrat · "
    "positive_claims_allowed=false"
)

NEON = {
    "cyan": "#00f5ff",
    "mag": "#ff2bd6",
    "lime": "#b6ff00",
    "amber": "#ffb000",
    "violet": "#8f5bff",
    "bg": "#04010b",
    "panel": "#0d0624",
    "text": "#d7fbff",
    "dim": "#6f86a0",
    "red": "#ff3860",
}

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(13,6,36,0.65)",
    font=dict(family="JetBrains Mono, Fira Code, monospace", color=NEON["text"], size=12),
    margin=dict(l=40, r=20, t=50, b=40),
)

EXTRA_CSS = """
<style>
.ql-ball.jk { background:radial-gradient(circle at 30% 28%, #ffffff 0%, #ffb000 40%, #6b4a00 100%) !important;
  box-shadow:0 0 18px rgba(255,176,0,0.8) !important; border:2px dashed #fff; }
.ql-plus { display:inline-block; font-size:1.6rem; font-weight:800; color:#ffb000; margin:0 4px;
  text-shadow:0 0 10px rgba(255,176,0,0.7); vertical-align:middle; }
</style>
"""

MODE_META: dict[str, dict[str, Any]] = {
    "649": {
        "title": "⚛ QUANTUM LAB 649 · PL-V3",
        "game": "LOTO 6/49 RO",
        "rule": "6 numere distincte din 1..49",
        "space_desc": "C(49, 6) = 13 983 816 stări exacte",
    },
    "540": {
        "title": "🌀 QUANTUM LAB 540 · PL-V3",
        "game": "LOTO 5/40 RO",
        "rule": "5 numere distincte din 1..40 (extragere 6 din 40)",
        "space_desc": "C(40, 5) = 658 008 stări exacte",
    },
    "joker": {
        "title": "🃏 QUANTUM LAB JOKER · PL-V3",
        "game": "JOKER RO",
        "rule": "5 numere distincte din 1..45 + 1 Joker din 1..20",
        "space_desc": "C(45, 5) × 20 = 24 435 180 stări exacte",
    },
}

VARIANT_TITLES = (
    "VARIANTA 1 · STARE FUNDAMENTALĂ α",
    "VARIANTA 2 · EXCITATĂ ORTOGONALĂ β",
    "VARIANTA 3 · EXCITATĂ ORTOGONALĂ γ",
)


def _card(k: str, v: str, cls: str = "") -> str:
    cls_part = f" {cls}" if cls else ""
    return f'<div class="ql-card"><div class="ql-k">{k}</div><div class="ql-v{cls_part}">{v}</div></div>'


def _fig(**kw: Any) -> go.Figure:
    f = go.Figure()
    f.update_layout(**PLOT_LAYOUT, **kw)
    return f


def compute_jastrow_gram(tickets: list[list[int]], k: int) -> dict[str, Any]:
    """Calculează matricea Gram normalizată G_{uv} = |σ_u ∩ σ_v| / k și minorii principali det G_1, det G_2, det G_3."""
    sets = [set(int(x) for x in t) for t in tickets]
    G = np.eye(3, dtype=np.float64)
    ov_counts = np.zeros((3, 3), dtype=np.int64)
    for u in range(3):
        ov_counts[u, u] = k
        for v in range(u + 1, 3):
            inter = len(sets[u] & sets[v])
            ov_counts[u, v] = ov_counts[v, u] = inter
            G[u, v] = G[v, u] = float(inter) / float(k)
    det_g1 = 1.0
    det_g2 = float(max(0.0, 1.0 - G[0, 1] ** 2))
    det_g3 = float(max(0.0, np.linalg.det(G)))
    return {
        "G": G,
        "ov_counts": ov_counts,
        "det_G1": det_g1,
        "det_G2": det_g2,
        "det_G3": det_g3,
    }


@st.cache_data(show_spinner=False)
def _cached_ruelle_spectrum(mode: str, src_key: str, ckpt_path: str) -> dict[str, Any]:
    """Extrage spectrul complex exact λ(L̃_Ruelle) din starea salvată în checkpoint (CPU, < 1 ms)."""
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    r_trans = ck["state"]["ruelle_trans"].detach().to(torch.float64).cpu().numpy()  # [3, N, N]
    N = int(r_trans.shape[1])
    L_ruelle = np.zeros((N, N), dtype=np.float64)
    for idx, w_l in enumerate(DEFAULT_PARAMS.ruelle_weights):
        L_ruelle = L_ruelle + float(w_l) * r_trans[idx]
    std_val = max(float(np.std(L_ruelle)), 1e-12)
    L_tilde = (L_ruelle - float(np.mean(L_ruelle))) / (std_val * math.sqrt(float(N)))
    eigs = np.linalg.eigvals(L_tilde)
    order = np.argsort(-np.abs(eigs), kind="mergesort")
    eigs = eigs[order]
    return {
        "mode": mode,
        "src_key": src_key,
        "re": eigs.real.astype(float).tolist(),
        "im": eigs.imag.astype(float).tolist(),
        "abs": np.abs(eigs).astype(float).tolist(),
        "spectral_radius": float(np.max(np.abs(eigs))) if eigs.size else 0.0,
    }


@st.cache_data(show_spinner=False)
def _cached_static_reports(mode: str) -> dict[str, Any]:
    """Încarcă certificatele preînregistrate CALIFICARE_Q.json, {mode}_walkforward.{json,npz} și REGRESIE_INCREMENTALA.json."""
    rez_dir = HERE / "rezultate"
    cal_q = json.loads((rez_dir / "CALIFICARE_Q.json").read_text(encoding="utf-8"))
    wf_json = json.loads((rez_dir / f"{mode}_walkforward.json").read_text(encoding="utf-8"))
    reg_p = rez_dir / "REGRESIE_INCREMENTALA.json"
    reg_json = json.loads(reg_p.read_text(encoding="utf-8")) if reg_p.is_file() else None

    with np.load(rez_dir / f"{mode}_walkforward.npz", allow_pickle=False) as npz:
        steps = npz["steps"].astype(np.int64).tolist()
        step_dates = [str(x) for x in npz["step_dates"].tolist()]
        log10_E = npz["log10_E_curve"].astype(float).tolist()
        e_factor = npz["e_factor_step"].astype(float).tolist()
        log_p_plv3 = npz["log_p_step_plv3"].astype(float).tolist()
        log_p_u = npz["log_p_step_u"].astype(float).tolist()
        t_step = npz["target_step"].astype(np.int64)
        h_pl = npz["hits_draw_plv3"].astype(np.int64)
        h_b = npz["hits_draw_b"].astype(np.int64)
        h_r = npz["hits_draw_r"].astype(np.int64)

        tail_rows: list[dict[str, Any]] = []
        n_tail = min(10, len(steps))
        for idx_s in range(len(steps) - n_tail, len(steps)):
            s_val = int(steps[idx_s])
            mask_d = t_step == s_val
            tail_rows.append(
                {
                    "Pas": s_val,
                    "Data": step_dates[idx_s],
                    "Extrageri": int(np.sum(mask_d)),
                    "Hits α (PL-V3)": int(np.sum(h_pl[mask_d])),
                    "Hits B": int(np.sum(h_b[mask_d])),
                    "Hits R": int(np.sum(h_r[mask_d])),
                    "ln P(D_s)": round(float(log_p_plv3[idx_s]), 4),
                    "ln U(D_s)": round(float(log_p_u[idx_s]), 4),
                    "Factor Ville": round(float(e_factor[idx_s]), 6),
                    "log10(E_s)": round(float(log10_E[idx_s]), 5),
                }
            )

    return {
        "cal_q": cal_q,
        "wf": wf_json,
        "reg": reg_json,
        "curve": {
            "steps": steps,
            "step_dates": step_dates,
            "log10_E": log10_E,
            "tail_rows": tail_rows,
        },
    }


def clear_ui_caches() -> None:
    """Eliberează cache-urile auxiliare ale UI-ului PL-V3 la schimbarea modului."""
    _cached_ruelle_spectrum.clear()
    _cached_static_reports.clear()


def _cauchy_binet_error(mode: str, cal_q: dict[str, Any]) -> float:
    q1 = next((c["detail"] for c in cal_q.get("checks", []) if c.get("id") == "Q1"), {})
    if mode == "649":
        return float(q1.get("rel_err_649", 0.0))
    if mode == "540":
        return float(q1.get("rel_err_540", 0.0))
    return float(max(q1.get("rel_err_540", 0.0), q1.get("cholesky_vs_numpy_err", 0.0)))


def _resolve_live_sync(mode: str) -> tuple[str, dict[str, Any]]:
    live_root_env = os.environ.get("QL649_PLV3_LIVE_ROOT")
    deriv_root_env = os.environ.get("QL649_PLV3_DERIV_ROOT")
    cache_dir_env = os.environ.get("QL649_PLV3_CACHE_DIR")

    live_root = Path(live_root_env) if live_root_env else None
    deriv_root = Path(deriv_root_env) if deriv_root_env else None
    cache_dir = Path(cache_dir_env) if cache_dir_env else None

    if live_root is None:
        import ui_tu3 as _ui_mod

        cur_key = str(_ui_mod.live_key(mode))
    else:
        resolved_p, _ = PM.resolve_live(mode, live_root=live_root)
        cur_key = PM.sha256_file(resolved_p)

    res = get_or_advance_live(
        mode,
        live_root=live_root,
        deriv_root=deriv_root,
        cache_dir=cache_dir,
    )
    return cur_key, res


def _build_extended_ville_curve(
    base_curve: dict[str, Any],
    settlement_history: list[dict[str, Any]],
) -> tuple[list[str], list[float], int]:
    dates = list(base_curve["step_dates"])
    vals = list(base_curve["log10_E"])
    last_step = int(base_curve["steps"][-1]) if base_curve["steps"] else -1
    cur_log10 = float(vals[-1]) if vals else 0.0

    # Grupăm eventualii pași decontați incremental după step_idx > last_step
    by_step: dict[int, list[dict[str, Any]]] = {}
    for rec in settlement_history:
        s_idx = int(rec.get("step_idx", -1))
        if s_idx > last_step:
            by_step.setdefault(s_idx, []).append(rec)

    added = 0
    for s_idx in sorted(by_step):
        recs = by_step[s_idx]
        # Pentru zile duble, factorul de pas este media/produsul conform definiției; pe extragere individuală e exact ville_factor
        mean_ratio = float(np.mean([max(float(r.get("prob_over_uniform", 0.0)), 0.0) for r in recs]))
        e_step = max(0.5 + 0.5 * mean_ratio, 1e-300)
        cur_log10 += math.log10(e_step)
        dates.append(str(recs[-1].get("draw_date", f"s={s_idx}")))
        vals.append(cur_log10)
        added += 1

    return dates, vals, added


def _format_gate_value(g: dict[str, Any]) -> tuple[str, str]:
    gid = g["id"]
    val = g["value"]
    if gid == "G1":
        return f"{float(val):+.6f}", f">= +{float(g.get('threshold', 0.20)):.2f}"
    if gid == "G2":
        return f"PL-V3={val['PLV3']} · B={val['B']} · R={val['R']}", f"> max({val['B']}, {val['R']})"
    if gid == "G3":
        return (
            f"PL-V3={val['PLV3']:.2f} (ΔU={val['diff_vs_U']:+.2f}, ΔB={val['diff_vs_B']:+.2f})",
            f"> {max(val['U'], val['B'], val['R']):.2f}",
        )
    if gid == "G4":
        return (
            f"PL-V3={val['PLV3']:.2f} · U={val['U']:.2f} · B={val['B']:.2f}",
            f"< {min(val['U'], val['B'], val['R']):.2f}",
        )
    if gid == "G5":
        return (
            f"H1={val['half1_diff_PLV3_minus_B']:+.2f} · H2={val['half2_diff_PLV3_minus_B']:+.2f} · "
            f"L100={val['last100_diff_PLV3_minus_B']:+.2f}",
            "toate 3 > 0",
        )
    if gid == "G6":
        return f"log10(E_S) = {val['log10_E_S']:+.4f} (E_S = {val['E_S']:.3e})", "E_S > 1.0 (log10 > 0)"
    return str(val), "—"


def render_pl_v3(mode: str) -> None:
    """Randează panoul principal PL-V3 pentru universul selectat (`649`, `540`, `joker`)."""
    if mode not in GAME_CONFIGS:
        st.error(f"Mod necunoscut pentru PL-V3: {mode!r}")
        return

    st.markdown(EXTRA_CSS, unsafe_allow_html=True)

    N, r_draw, k_ticket, joker_m = GAME_CONFIGS[mode]
    n_states = int(math.comb(N, k_ticket) * (joker_m if joker_m is not None else 1))
    meta_info = MODE_META[mode]

    # 1. Sincronizare automată real-time cu CURRENT_LIVE.json / live_key(mode)
    cur_live_key, live = _resolve_live_sync(mode)
    static_pack = _cached_static_reports(mode)
    cal_q = static_pack["cal_q"]
    wf = static_pack["wf"]
    ruelle_spec = _cached_ruelle_spectrum(mode, live["src_key"], live["checkpoint_path"])

    # 2. Antet & Eticheta Onestă Permanentă
    st.markdown(f'<div class="ql-title">{meta_info["title"]}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="ql-sub">{meta_info["game"]} · {meta_info["rule"]} · {meta_info["space_desc"]} · '
        f'Holonomie SU(3) + Hodge + Bochner DPP + Ultrametrică Spin-Glass</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="ql-warn"><b>{HONEST_LABEL}</b></div>', unsafe_allow_html=True)

    sync_badge = (
        f"CACHE HIT ({live['elapsed_sec'] * 1000.0:.2f} ms)"
        if live["cache_hit"]
        else f"AVANS INCREMENTAL ΔS={live['delta_steps']} ({live['elapsed_sec'] * 1000.0:.1f} ms)"
    )
    key_match_ok = cur_live_key == live["src_key"]
    st.caption(
        f"🛰 Sincronizare `live_key({mode})` = `{cur_live_key[:16]}…` ({'OK == checkpoint' if key_match_ok else 'MISMATCH'}) · "
        f"{sync_badge} · {live['n_draws']} extrageri · {live['n_steps']} pași-zi · ultima dată arhivă LIVE: "
        f"**{live['last_date']}**"
    )

    # 3. Cele 3 Carduri Principale cu Bile: (α, β, γ)
    variants = live["variants"]
    tickets_main = [[int(x) for x in v["ticket"]] for v in variants]
    gram_info = compute_jastrow_gram(tickets_main, k_ticket)
    log_Z = float(live["log_Z"])
    ov = gram_info["ov_counts"]
    det_per_card = (gram_info["det_G1"], gram_info["det_G2"], gram_info["det_G3"])

    cols_v = st.columns(3)
    for i, v in enumerate(variants):
        t_nums = [int(x) for x in v["ticket"]]
        balls_html = "".join(f'<span class="ql-ball">{num}</span>' for num in t_nums)
        if mode == "joker" and "joker" in v:
            balls_html += f'<span class="ql-plus">+</span><span class="ql-ball jk">{int(v["joker"])}</span>'

        ln_w = float(v["log_prob"]) + log_Z
        prob_exact = float(v["prob"])
        ratio_u = prob_exact * float(n_states)
        if i == 0:
            orth_txt = f"det G = {gram_info['det_G3']:.4f} (det G₁ = {det_per_card[0]:.4f})"
        elif i == 1:
            orth_txt = f"det G = {det_per_card[1]:.4f} (|α∩β| = {ov[0, 1]}/{k_ticket} · det G₃ = {gram_info['det_G3']:.4f})"
        else:
            orth_txt = (
                f"det G = {det_per_card[2]:.4f} "
                f"(|α∩γ| = {ov[0, 2]}/{k_ticket}, |β∩γ| = {ov[1, 2]}/{k_ticket})"
            )

        meta_html = (
            f"ln W(σ) = {ln_w:+.5f} · P(σ) = {prob_exact:.4e} ({ratio_u:.2f}×U)<br>"
            f"ortogonalitate Jastrow: {orth_txt}"
        )
        cols_v[i].markdown(
            f'<div class="ql-variant v{i + 1}">'
            f'<div class="ql-vlabel">{VARIANT_TITLES[i]}</div>'
            f"{balls_html}"
            f'<div class="ql-meta">{meta_html}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    # 4. Carduri KPI sub variante
    cb_err = _cauchy_binet_error(mode, cal_q)
    core_list = [int(x) for x in live["deterministic_core"]]
    core_str = " ".join(str(x) for x in core_list) if core_list else "∅ (π_i < 0.50)"
    distinct_str = f"{live['distinct_covered']} / {3 * k_ticket}"
    if mode == "joker":
        jok_distinct = len({int(v["joker"]) for v in variants if "joker" in v})
        distinct_str += f" · J:{jok_distinct}/3"

    vram_now_mib = float(live["vram_allocated_after_bytes"]) / (1024.0 ** 2)
    rel_events = st.session_state.get("tu3_release_log", [])
    vram_str = f"{vram_now_mib:.1f} MiB" + (f" · elib. ({len(rel_events)})" if rel_events else " · eliberat")
    gpu_time_str = f"{live['elapsed_sec'] * 1000.0:.2f} ms"

    kpi_r1 = st.columns(3)
    kpi_r1[0].markdown(_card("NUMERE DISTINCTE ACOPERITE", distinct_str, "lime"), unsafe_allow_html=True)
    kpi_r1[1].markdown(_card("NUCLEU DETERMINIST", core_str, "mag"), unsafe_allow_html=True)
    kpi_r1[2].markdown(_card("EROARE CAUCHY-BINET", f"{cb_err:.2e}"), unsafe_allow_html=True)

    kpi_r2 = st.columns(3)
    kpi_r2[0].markdown(_card("GAP FUNDAMENTAL ΔlnW", f"{live['ground_gap_ln_w']:.5f}", "amber"), unsafe_allow_html=True)
    kpi_r2[1].markdown(_card("TIMP MOTOR GPU", gpu_time_str, "amber"), unsafe_allow_html=True)
    kpi_r2[2].markdown(_card("VRAM", vram_str), unsafe_allow_html=True)

    st.markdown("---")

    # 5. Telemetrie Fizică Coomologică, Ruelle Argand & Joker S_vN
    tel = live["telemetry"]
    curl_ratio = float(tel["curl_energy_ratio"])
    hodge_err = float(tel["hodge_inner_err"])
    wilson_mean = float(tel["wilson_mean"])
    ym_mean = float(tel["ym_tension_mean"])
    su3_err = float(tel["su3_unitarity_err"])
    s_vn_val = tel.get("s_vn_joker")

    st.markdown("### 🧭 TELEMETRIE FIZICĂ COOMOLOGICĂ & SPECTRALĂ (FĂRĂ AVANTAJ PREDICTIV)")
    phys_cols = st.columns(4)
    phys_cols[0].markdown(
        _card("FRACȚIE VORTICITATE ‖J_curl‖²/‖J‖²", f"{curl_ratio:.6f} ({curl_ratio * 100.0:.2f}%)", "cyan"),
        unsafe_allow_html=True,
    )
    phys_cols[1].markdown(
        _card("ORTOGONALITATE HODGE ⟨J_ex, J_curl⟩", f"{hodge_err:.2e}", "lime"),
        unsafe_allow_html=True,
    )
    phys_cols[2].markdown(
        _card("HOLONOMIE WILSON SU(3) ⟨W_△⟩", f"{wilson_mean:.5f} (YM {ym_mean:.4f})", "mag"),
        unsafe_allow_html=True,
    )
    if mode == "joker" and s_vn_val is not None:
        phys_cols[3].markdown(
            _card("ENTROPIE ÎNCURCARE S_vN (45⊗20)", f"{float(s_vn_val):.5f} nats", "amber"),
            unsafe_allow_html=True,
        )
    else:
        phys_cols[3].markdown(
            _card(
                "SPECTRU RUELLE ρ(L̃) · UNITARITATE SU(3)",
                f"ρ={ruelle_spec['spectral_radius']:.4f} · {su3_err:.1e}",
                "amber",
            ),
            unsafe_allow_html=True,
        )

    col_argand, col_dist = st.columns(2)
    with col_argand:
        theta_grid = np.linspace(0.0, 2.0 * math.pi, 200)
        rho_r = float(ruelle_spec["spectral_radius"])
        fig_arg = _fig(
            title="DIAGRAMA ARGAND RUELLE · SPECTRUL λ(L̃_Ruelle)",
            xaxis_title="Re λ",
            yaxis_title="Im λ",
            height=380,
        )
        fig_arg.add_scatter(
            x=np.cos(theta_grid),
            y=np.sin(theta_grid),
            mode="lines",
            line=dict(color=NEON["dim"], dash="dot", width=1),
            name="|z| = 1",
        )
        if rho_r > 0:
            fig_arg.add_scatter(
                x=rho_r * np.cos(theta_grid),
                y=rho_r * np.sin(theta_grid),
                mode="lines",
                line=dict(color=NEON["amber"], dash="dash", width=1.3),
                name=f"ρ(L̃) = {rho_r:.3f}",
            )
        fig_arg.add_scatter(
            x=ruelle_spec["re"],
            y=ruelle_spec["im"],
            mode="markers",
            marker=dict(
                size=8,
                color=ruelle_spec["abs"],
                colorscale="Plasma",
                showscale=True,
                colorbar=dict(title="|λ|"),
                line=dict(width=0.6, color="#ffffff"),
            ),
            name="λ_i(L̃_Ruelle)",
        )
        fig_arg.update_yaxes(scaleanchor="x", scaleratio=1)
        st.plotly_chart(fig_arg, width="stretch")

    with col_dist:
        if mode == "joker" and live.get("joker_prob") is not None:
            j_probs = [float(x) for x in live["joker_prob"]]
            sel_jokers = {int(v["joker"]): lbl for v, lbl in zip(variants, ("α", "β", "γ")) if "joker" in v}
            bar_colors = []
            for b_idx in range(1, 21):
                lbl = sel_jokers.get(b_idx)
                if lbl == "α":
                    bar_colors.append(NEON["cyan"])
                elif lbl == "β":
                    bar_colors.append(NEON["mag"])
                elif lbl == "γ":
                    bar_colors.append(NEON["lime"])
                else:
                    bar_colors.append(NEON["violet"])
            s_vn_disp = float(s_vn_val) if s_vn_val is not None else 0.0
            fig_jok = _fig(
                title=f"DISTRIBUȚIA CELOR 20 BILE JOKER · S_vN = {s_vn_disp:.5f} nats (max ln 20 = {math.log(20):.4f})",
                xaxis_title="Bila Joker b (1..20)",
                yaxis_title="P_J(b)",
                height=380,
            )
            fig_jok.add_bar(
                x=list(range(1, 21)),
                y=j_probs,
                marker=dict(color=bar_colors),
                name="P_J(b) exact",
            )
            fig_jok.add_hline(
                y=1.0 / 20.0,
                line=dict(color=NEON["amber"], dash="dot"),
                annotation_text="uniform 1/20 = 0.05",
            )
            st.plotly_chart(fig_jok, width="stretch")
        else:
            pi_inc = [float(x) for x in live["pi_inclusion"]]
            alpha_set = set(tickets_main[0])
            beta_set = set(tickets_main[1])
            gamma_set = set(tickets_main[2])
            bar_colors = []
            for b_idx in range(1, N + 1):
                if b_idx in alpha_set:
                    bar_colors.append(NEON["cyan"])
                elif b_idx in beta_set:
                    bar_colors.append(NEON["mag"])
                elif b_idx in gamma_set:
                    bar_colors.append(NEON["lime"])
                else:
                    bar_colors.append(NEON["dim"])
            fig_pi = _fig(
                title=f"INCLUZIUNI MARGINALE EXACTE π_i = P(i ∈ σ) · S_H = {live['shannon_entropy_nats']:.3f} nats",
                xaxis_title=f"Număr 1..{N}",
                yaxis_title="π_i",
                height=380,
            )
            fig_pi.add_bar(x=list(range(1, N + 1)), y=pi_inc, marker=dict(color=bar_colors), name="π_i exact")
            fig_pi.add_hline(
                y=float(k_ticket) / float(N),
                line=dict(color=NEON["amber"], dash="dot"),
                annotation_text=f"uniform {k_ticket}/{N}",
            )
            st.plotly_chart(fig_pi, width="stretch")
            q4_det = next((c["detail"] for c in cal_q.get("checks", []) if c.get("id") == "Q4"), {})
            st.caption(
                f"Notă bipartită Joker (Q4): entropia de încurcare S_vN(ρ_20) este activă pe H_45 ⊗ H_20 în modul Joker "
                f"(referință Q4 S_vN = {q4_det.get('joker_s_vn', 0.0):.5f} nats)."
            )

    # 6. WALK-FORWARD ARHIVĂ LIVE (G1–G6: 0/6) + Curba Plotly log10(E_s) a E-procesului Ville
    st.markdown(
        f"### 📉 WALK-FORWARD ARHIVĂ LIVE (G1–G6: {wf['gates_passed']}/{wf['gates_total']} · {wf['status']})"
    )
    st.caption(
        f"Evaluare strict cauzală pe `{wf['source_live']['evaluated_steps']}` pași-zi "
        f"(`{wf['source_live']['evaluated_target_draws']}` extrageri-țintă, "
        f"`{wf['source_live']['first_eval_date']}` → `{wf['source_live']['last_eval_date']}`, "
        f"warmup = `{wf['source_live']['warmup_steps']}`, fără sub-eșantionare)."
    )

    curve_dates, curve_vals, added_live_pts = _build_extended_ville_curve(
        static_pack["curve"],
        live.get("settlement_history", []),
    )
    fig_ville = _fig(
        title="E-PROCESUL DEFENSIV VILLE · log10(E_s) PE TOATĂ ARHIVA LA ZI",
        xaxis_title="Data pasului s",
        yaxis_title="log10(E_s)",
        height=340,
    )
    fig_ville.add_scatter(
        x=curve_dates,
        y=curve_vals,
        mode="lines",
        line=dict(color=NEON["cyan"], width=1.8),
        name="log10(E_s) PL-V3",
    )
    fig_ville.add_hline(
        y=0.0,
        line=dict(color=NEON["amber"], dash="dash"),
        annotation_text="log10(E) = 0 (E = 1 · poarta G6)",
    )
    fig_ville.add_hline(
        y=math.log10(20.0),
        line=dict(color=NEON["mag"], dash="dot"),
        annotation_text="log10(20) ≈ +1.301 (α = 0.05)",
    )
    st.plotly_chart(fig_ville, width="stretch")
    if added_live_pts > 0:
        st.caption(f"Curba `log10(E_s)` include `{added_live_pts}` pași suplimentari decontați live din `CURRENT_LIVE.json`.")

    gate_rows = []
    for g in wf["gates"]:
        obs_str, thr_str = _format_gate_value(g)
        gate_rows.append(
            {
                "Poartă": g["id"],
                "Criteriu Preînregistrat": g["rule"],
                "Valoare Observată": obs_str,
                "Prag / Reper": thr_str,
                "Verdict": "PASS" if g["pass"] else "FAIL",
            }
        )
    st.dataframe(pd.DataFrame(gate_rows), width="stretch", hide_index=True)

    win_labels = {
        "total": "Total Arhivă",
        "half1": "Prima Jumătate",
        "half2": "A Doua Jumătate",
        "last100": "Ultimii 100 Pași",
    }
    win_rows = []
    for wk, wtitle in win_labels.items():
        w = wf["windows"][wk]
        win_rows.append(
            {
                "Fereastră": wtitle,
                "Pași": w["n_steps"],
                "Extrageri": w["n_draws"],
                "Hits PL-V3": w["hits_PLV3"],
                "Hits B": w["hits_B"],
                "Hits R": w["hits_R"],
                "Exces vs U": f"{w['excess_hits_vs_U']:+.5f}",
                "LogScore PL-V3": f"{w['log_score_PLV3']:.2f}",
                "LogScore U": f"{w['log_score_U']:.2f}",
                "LogScore B": f"{w['log_score_B']:.2f}",
                "Brier PL-V3": f"{w['brier_PLV3']:.2f}",
                "Brier U": f"{w['brier_U']:.2f}",
            }
        )
    st.dataframe(pd.DataFrame(win_rows), width="stretch", hide_index=True)

    if mode == "joker" and wf.get("joker_breakdown"):
        jb = wf["joker_breakdown"]
        m5, b1 = jb["main_5_45"], jb["ball_1_20"]
        st.caption(
            f"Defalcare Joker (`24 435 180` stări comune): "
            f"**Urna 5/45** Hits PL-V3=`{m5['hits_PLV3']}` / B=`{m5['hits_B']}` / R=`{m5['hits_R']}` "
            f"(exces `{m5['excess_vs_U']:+.5f}`) · "
            f"**Bila Joker 1/20** Hits PL-V3=`{b1['hits_PLV3']}` / B=`{b1['hits_B']}` / R=`{b1['hits_R']}` "
            f"(exces `{b1['excess_vs_U']:+.5f}`)."
        )

    # 7. CALIFICARE Q1–Q6 (6/6 PASS)
    st.markdown(
        f"### 🧪 CALIFICARE Q1–Q6 ({cal_q['passed']}/{cal_q['total']} PASS · {cal_q['status']})"
    )
    q_rows = []
    for chk in cal_q.get("checks", []):
        det_str = ", ".join(
            f"{k}={v:.2e}" if isinstance(v, float) and (abs(v) < 1e-4 and v != 0.0) else f"{k}={v}"
            for k, v in list(chk.get("detail", {}).items())[:4]
        )
        q_rows.append(
            {
                "ID": chk["id"],
                "Test Algebric / Cauzalitate": chk["name"],
                "Statut": "PASS" if chk["pass"] else "FAIL",
                "Metrici Certificate": det_str,
            }
        )
    st.dataframe(pd.DataFrame(q_rows), width="stretch", hide_index=True)

    # 8. Istoricul Decontărilor Automate Live & Profilul GPU pe Operator
    st.markdown("### 📜 ISTORICUL DECONTĂRILOR AUTOMATE LIVE (`CURRENT_LIVE.json`)")
    hist = list(live.get("settlement_history", []))
    if hist:
        st.caption(
            f"`{len(hist)}` extrageri decontate automat incremental peste checkpoint "
            f"(`{len(live.get('settled_new_draws', []))}` noi în acest ciclu)."
        )
        hist_rows = []
        for rec in reversed(hist[-25:]):
            nums_s = " ".join(str(x) for x in rec.get("numbers", []))
            if rec.get("joker") is not None:
                nums_s += f" + J:{rec['joker']}"
            hist_rows.append(
                {
                    "Data": rec.get("draw_date"),
                    "Cheie": rec.get("draw_key"),
                    "Extragere": nums_s,
                    "Hits α": rec.get("hits_alpha"),
                    "Hits β": rec.get("hits_beta"),
                    "Hits γ": rec.get("hits_gamma"),
                    "ln P(D)": round(float(rec.get("log_prob", 0.0)), 4),
                    "ln U(D)": round(float(rec.get("log_uniform", 0.0)), 4),
                    "Factor Ville": round(float(rec.get("ville_factor", 1.0)), 6),
                    "Decontat UTC": rec.get("settled_utc"),
                }
            )
        st.dataframe(pd.DataFrame(hist_rows), width="stretch", hide_index=True)
    else:
        st.caption(
            f"Checkpoint sincronizat la zi cu `CURRENT_LIVE.json` (`{live['last_date']}`, `0` extrageri noi neprocesate). "
            "La apariția unei extrageri noi în `CURRENT_LIVE.json`, `get_or_advance_live` decontează automat pasul anterior "
            "în `< 0.35 s`. Mai jos sunt ultimii 10 pași decontați din arhiva LIVE la zi:"
        )
        st.dataframe(pd.DataFrame(static_pack["curve"]["tail_rows"]), width="stretch", hide_index=True)

    tm_wf = wf["timings"]
    io_other = max(0.0, round(float(tm_wf["total_sec"]) - float(tm_wf["O1_O4_sec"]) - float(tm_wf["O5_batch32_sec"]), 3))
    op_profile = {
        "Sync Real-Time get_or_advance_live (pas curent)": round(float(live["elapsed_sec"]), 6),
        "I/O, Reper B/R & Martingală Ville (walk-forward)": io_other,
        "O1–O4 · SU(3) + Hodge + Bochner + Spin-Glass/Joker (WF)": float(tm_wf["O1_O4_sec"]),
        "O5 · Cauchy-Binet Exhaustiv & Multiplet Jastrow (WF)": float(tm_wf["O5_batch32_sec"]),
    }
    fig_prof = _fig(title="PROFIL GPU PE OPERATOR (secunde)", xaxis_title="s", height=300)
    fig_prof.add_bar(
        y=list(op_profile.keys()),
        x=list(op_profile.values()),
        orientation="h",
        marker=dict(color=[NEON["lime"], NEON["amber"], NEON["mag"], NEON["cyan"]]),
    )
    st.plotly_chart(fig_prof, width="stretch")
