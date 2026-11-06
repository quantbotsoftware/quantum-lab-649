"""HS-V4 UI — Randarea motorului Bosonic Hubbard–Stratonovich · Aero-Meteo ERA5 · RNG O4 · Portofoliu O3
pe modurile RO (`649`, `540`, `joker`) și a tab-ului dedicat `🌍 Internațional & Extrageri Electronice Online`.

Protocol: `hs_v4/PROTOCOL_HSV4_UI.md` (sigilat `0444` în `hs_v4/SIGILIU_HSV4_UI.json` ÎNAINTE de acest fișier).
Sincronizare cauzală automată cu `CURRENT_LIVE.json` prin `hs_v4.walkforward.get_or_advance_live(mode, config_key)`.
Calcul clasic exact în float64; variantele multipletului Coulomb–Jastrow (α, β, γ) și nucleul determinist sunt
minime de energie / stări statistice condiționate de istoric, NU predicții și fără promisiuni de câștig.
`positive_claims_allowed=false`.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).resolve().parent
QL = HERE.parent
TU3 = QL / "tu3"
for _p in (str(QL), str(TU3)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import parser_multi as PM  # noqa: E402
from hs_v4.core import EXPERT_GRID  # noqa: E402
from hs_v4.meteo_ro import CACHE_JSONL as METEO_CACHE_JSONL, PROVENANCE_JSON as METEO_PROVENANCE_JSON  # noqa: E402
from hs_v4.walkforward import (  # noqa: E402
    ABLATION_CONFIGS,
    RO_GAME_CONFIGS,
    get_or_advance_live,
)

HONEST_LABEL = (
    "HSV4_NO_PROMOTION_EXPLORATORY · Calificare Q1–Q6: 6/6 PASS · calcul clasic float64 · "
    "variantele multipletului Coulomb–Jastrow (α, β, γ) și nucleul determinist sunt minime de energie / "
    "stări statistice condiționate de istoric, NU predicții și fără promisiuni de câștig · "
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
    margin=dict(l=42, r=20, t=48, b=40),
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
        "title": "⚛ QUANTUM LAB 649 · HS-V4",
        "game": "LOTO 6/49 RO",
        "rule": "6 numere distincte din 1..49",
        "space_desc": "C(49, 6) = 13 983 816 stări exacte",
    },
    "540": {
        "title": "🌀 QUANTUM LAB 540 · HS-V4",
        "game": "LOTO 5/40 RO",
        "rule": "5 numere distincte din 1..40 (extragere 6 din 40)",
        "space_desc": "C(40, 5) = 658 008 stări exacte",
    },
    "joker": {
        "title": "🃏 QUANTUM LAB JOKER · HS-V4",
        "game": "JOKER RO",
        "rule": "5 numere distincte din 1..45 + 1 Joker din 1..20",
        "space_desc": "C(45, 5) × 20 = 24 435 180 stări exacte",
    },
}

_RAW_CFG_LABELS: dict[str, str] = {k: f"{k} — {lbl}" for k, lbl, _, _, _ in ABLATION_CONFIGS}
CONFIG_LABELS: dict[str, str] = {
    k: _RAW_CFG_LABELS[k] for k in ("Full_HSV4", "O1_O2", "O1_O4", "O1") if k in _RAW_CFG_LABELS
}
RO_NPZ_MAP: dict[str, str] = {
    "Full_HSV4": "full_hsv4",
    "O1": "o1",
    "O1_O2": "o1_o2",
    "O1_O4": "o1_o4",
}

VARIANT_TITLES = (
    "STAREA STATISTICĂ 1 · MINIM DE ENERGIE α (NU predicție)",
    "STAREA STATISTICĂ 2 · MOD ORTOGONAL β (NU predicție)",
    "STAREA STATISTICĂ 3 · MOD ORTOGONAL γ (NU predicție)",
)

MECHANICAL_ORDER = ("fr_loto", "hu_hatoslotto", "hu_otoslotto", "us_powerball")
ELECTRONIC_ORDER = ("fdj_eurodreams", "ny_take5", "ny_cash4life", "ny_pick10")
ALL_INTL_ORDER = (
    "fr_loto",
    "hu_hatoslotto",
    "hu_otoslotto",
    "us_powerball",
    "fdj_eurodreams",
    "ny_take5",
    "ny_cash4life",
    "ny_pick10",
    "hu_skandinav_mech",
    "hu_skandinav_rng",
)


def _card(k: str, v: str, cls: str = "") -> str:
    cls_part = f" {cls}" if cls else ""
    return f'<div class="ql-card"><div class="ql-k">{k}</div><div class="ql-v{cls_part}">{v}</div></div>'


def _fig(**kw: Any) -> go.Figure:
    f = go.Figure()
    f.update_layout(**PLOT_LAYOUT, **kw)
    return f


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _npz_rel_name(t_npz: Any) -> str:
    return str(t_npz["file"]) if isinstance(t_npz, dict) else str(t_npz)


def _decimate_indices(arr: np.ndarray, max_points: int = 1800) -> np.ndarray:
    n = int(arr.shape[0])
    if n <= max_points or max_points < 8:
        return np.arange(n, dtype=np.int64)
    stride = max(1, n // (max_points - 4))
    base = set(range(0, n, stride))
    base.update({0, n - 1, int(np.argmin(arr)), int(np.argmax(arr))})
    return np.array(sorted(base), dtype=np.int64)


def compute_jastrow_gram(tickets: list[list[int]], k: int) -> dict[str, Any]:
    """Calculează matricea Gram normalizată G_{uv} = |σ_u ∩ σ_v| / k și minorii det G_1, det G_2, det G_3."""
    sets = [set(int(x) for x in t) for t in tickets]
    G = np.eye(3, dtype=np.float64)
    ov_counts = np.zeros((3, 3), dtype=np.int64)
    for u in range(3):
        ov_counts[u, u] = k
        for v in range(u + 1, 3):
            inter = len(sets[u] & sets[v])
            ov_counts[u, v] = ov_counts[v, u] = inter
            G[u, v] = G[v, u] = float(inter) / float(k)
    return {
        "G": G,
        "ov_counts": ov_counts,
        "det_G1": 1.0,
        "det_G2": float(max(0.0, 1.0 - G[0, 1] ** 2)),
        "det_G3": float(max(0.0, np.linalg.det(G))),
    }


def _channel_curves_from_portfolio(w_port: np.ndarray) -> dict[str, np.ndarray]:
    """Descompune curba [S, 8] a experților în (w_0, w_O1, w_O2, w_O4) cu sumă exactă 1.0 la fiecare pas."""
    w0 = w_port[:, 0]
    w_o1_pure = w_port[:, 1] + w_port[:, 2] + w_port[:, 3]
    w_o2_pure = w_port[:, 4]
    w_o1_o2 = w_port[:, 5]
    w_o4 = w_port[:, 6] + w_port[:, 7]
    return {
        "w_0": w0,
        "w_O1": w_o1_pure + 0.5 * w_o1_o2,
        "w_O2": w_o2_pure + 0.5 * w_o1_o2,
        "w_O4": w_o4,
    }


@st.cache_data(show_spinner=False)
def _cached_ro_static_bundle(mode: str, config_key: str) -> dict[str, Any]:
    """Încarcă rapoartele preînregistrate CALIFICARE_Q, WALKFORWARD_RO, ABLATIE_RO și traiectoriile .npz."""
    rez_dir = HERE / "rezultate"
    cal_q = json.loads((rez_dir / "CALIFICARE_Q.json").read_text(encoding="utf-8"))
    wf_ro = json.loads((rez_dir / "WALKFORWARD_RO.json").read_text(encoding="utf-8"))
    abl_ro = json.loads((rez_dir / "ABLATIE_RO.json").read_text(encoding="utf-8"))

    npz_slug = RO_NPZ_MAP.get(config_key, "full_hsv4")
    npz_path = rez_dir / f"ro_{mode}_{npz_slug}_walkforward.npz"
    with np.load(npz_path, allow_pickle=False) as npz:
        eval_steps = npz["eval_steps"].astype(np.int64)
        eval_dates = np.array([str(x) for x in npz["eval_dates"].tolist()], dtype=object)
        e_curve = npz["E_curve"].astype(np.float64)
        log10_e = npz["log10_E_curve"].astype(np.float64)
        w_port = npz["w_portfolio_curve"].astype(np.float64)
        ch_curves = _channel_curves_from_portfolio(w_port)

        t_step = npz["target_step"].astype(np.int64)
        h_main = npz["hits_main_hsv4"].astype(np.int64)
        h_b = npz["hits_main_b"].astype(np.int64)
        h_r = npz["hits_main_r"].astype(np.int64)
        h_jok = npz["hits_joker_hsv4"].astype(np.int64) if "hits_joker_hsv4" in npz.files else None
        sig_alpha = npz["sigma_alpha"].astype(np.int64)
        jok_alpha = npz["joker_alpha"].astype(np.int64) if "joker_alpha" in npz.files else None
        lp_hs = npz["log_step_hsv4"].astype(np.float64)
        lp_u = npz["log_step_u"].astype(np.float64)

        tail_rows: list[dict[str, Any]] = []
        n_tail = min(10, int(eval_steps.shape[0]))
        for idx_s in range(int(eval_steps.shape[0]) - n_tail, int(eval_steps.shape[0])):
            s_val = int(eval_steps[idx_s])
            m_d = t_step == s_val
            ticket_s = [int(x) for x in sig_alpha[idx_s].tolist()]
            label_t = " ".join(f"{b:02d}" for b in ticket_s)
            if jok_alpha is not None:
                label_t += f" + J{int(jok_alpha[idx_s]):02d}"
            jok_str = f" (+J:{int(h_jok[m_d].sum())})" if h_jok is not None and bool(m_d.any()) else ""
            tail_rows.append(
                {
                    "Pas s": s_val,
                    "Data": str(eval_dates[idx_s]),
                    "Minim energie α pre-pas": label_t,
                    "Potriviri α": f"{int(h_main[m_d].sum())}{jok_str}",
                    "Potriviri B": int(h_b[m_d].sum()),
                    "Potriviri R": int(h_r[m_d].sum()),
                    "Δ ln P vs U": round(float(lp_hs[idx_s] - lp_u[idx_s]), 5),
                    "E_s": round(float(e_curve[idx_s]), 6),
                    "w_0": round(float(ch_curves["w_0"][idx_s]), 6),
                }
            )

    abl_curves: dict[str, dict[str, Any]] = {}
    for cfg_k, slug in RO_NPZ_MAP.items():
        p_c = rez_dir / f"ro_{mode}_{slug}_walkforward.npz"
        with np.load(p_c, allow_pickle=False) as zc:
            ec = zc["E_curve"].astype(np.float64)
            ed = [str(x) for x in zc["eval_dates"].tolist()]
            idx_d = _decimate_indices(ec, max_points=1200)
            abl_curves[cfg_k] = {
                "dates": [ed[int(i)] for i in idx_d],
                "E_curve": [float(ec[int(i)]) for i in idx_d],
                "min_E": float(ec.min()),
                "final_E": float(ec[-1]),
            }

    idx_main = _decimate_indices(e_curve, max_points=1600)
    return {
        "cal_q": cal_q,
        "wf_ro": wf_ro,
        "abl_ro": abl_ro,
        "traj": {
            "dates": [str(eval_dates[int(i)]) for i in idx_main],
            "steps": [int(eval_steps[int(i)]) for i in idx_main],
            "E_curve": [float(e_curve[int(i)]) for i in idx_main],
            "log10_E": [float(log10_e[int(i)]) for i in idx_main],
            "w_0": [float(ch_curves["w_0"][int(i)]) for i in idx_main],
            "w_O1": [float(ch_curves["w_O1"][int(i)]) for i in idx_main],
            "w_O2": [float(ch_curves["w_O2"][int(i)]) for i in idx_main],
            "w_O4": [float(ch_curves["w_O4"][int(i)]) for i in idx_main],
            "min_E_exact": float(e_curve.min()),
            "max_E_exact": float(e_curve.max()),
            "final_E_exact": float(e_curve[-1]),
            "n_eval_steps": int(eval_steps.shape[0]),
            "tail_rows": tail_rows,
        },
        "abl_curves": abl_curves,
    }


@st.cache_data(show_spinner=False)
def _cached_meteo_snapshot(target_date: str, window_days: int = 90) -> dict[str, Any]:
    """Citește read-only cache-ul sigilat 0444 bucuresti_era5_18h.jsonl pentru data curentă și ultimele 90 zile."""
    prov = json.loads(METEO_PROVENANCE_JSON.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    matched: dict[str, Any] | None = None
    last_before: dict[str, Any] | None = None
    with METEO_CACHE_JSONL.open("r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            rec = json.loads(s)
            d_str = str(rec["date"])
            if d_str <= target_date:
                rows.append(rec)
                last_before = rec
                if d_str == target_date:
                    matched = rec
    chosen = matched if matched is not None else (last_before if last_before is not None else rows[-1])
    tail = rows[-window_days:] if len(rows) > window_days else rows
    return {
        "provenance": prov,
        "record": chosen,
        "exact_date_match": matched is not None,
        "tail_dates": [str(r["date"]) for r in tail],
        "tail_rho": [float(r["rho_air_kg_m3"]) for r in tail],
        "tail_rh": [float(r["rh_2m_pct"]) for r in tail],
        "tail_dp": [float(r["dp_24h_hpa"]) for r in tail],
    }


@st.cache_data(show_spinner=False)
def _cached_intl_overview() -> dict[str, Any]:
    """Încarcă INTERNATIONAL_RNG_EVAL.json, PROVENIENTA_INTL.json și curbele pereche Skandináv + control negativ O2."""
    rez_dir = HERE / "rezultate"
    intl = json.loads((rez_dir / "INTERNATIONAL_RNG_EVAL.json").read_text(encoding="utf-8"))
    prov_p = HERE / "date_intl" / "PROVENIENTA_INTL.json"
    prov = json.loads(prov_p.read_text(encoding="utf-8"))
    prov_sha_ok = _sha256_file(prov_p) == intl.get("provenance_intl_sha256")

    sk_curves: dict[str, dict[str, Any]] = {}
    for g_code in ("hu_skandinav_mech", "hu_skandinav_rng"):
        fam = "mechanical_external" if g_code == "hu_skandinav_mech" else "electronic_rng"
        npz_name = _npz_rel_name(intl[fam][g_code]["configs"]["Full_HSV4"]["trajectory_npz"])
        with np.load(rez_dir / npz_name, allow_pickle=False) as zn:
            ec = zn["E_curve"].astype(np.float64)
            wp = zn["w_portfolio_curve"].astype(np.float64)
            ed = [str(x) for x in zn["eval_dates"].tolist()]
            idx = _decimate_indices(ec, max_points=1350)
            sk_curves[g_code] = {
                "dates": [ed[int(i)] for i in idx],
                "E_curve": [float(ec[int(i)]) for i in idx],
                "active_mass": [float(1.0 - wp[int(i), 0]) for i in idx],
            }

    o2_ctrl_curves: dict[str, dict[str, Any]] = {}
    for row in intl["o2_negative_control_summary"]["streams"]:
        gc_code = str(row["game_code"])
        npz_name = _npz_rel_name(intl["electronic_rng"][gc_code]["configs"]["O2_NegCtrl"]["trajectory_npz"])
        with np.load(rez_dir / npz_name, allow_pickle=False) as zn:
            wp = zn["w_portfolio_curve"].astype(np.float64)
            ch = _channel_curves_from_portfolio(wp)
            w_o2 = ch["w_O2"]
            # Primele 400 de pași + eșantionare completă pentru a vedea clar contracția rapidă 0.50 -> 0.0
            head_idx = set(range(min(300, int(w_o2.shape[0]))))
            dec_idx = set(_decimate_indices(w_o2, max_points=900).tolist())
            idx = sorted(head_idx | dec_idx)
            steps = zn["eval_steps"].astype(np.int64)
            o2_ctrl_curves[gc_code] = {
                "steps_rel": [int(steps[i] - steps[0] + 1) for i in idx],
                "w_O2": [float(w_o2[i]) for i in idx],
                "E_min": float(zn["E_curve"].min()),
            }

    return {
        "intl": intl,
        "prov": prov,
        "prov_sha_ok": bool(prov_sha_ok),
        "sk_curves": sk_curves,
        "o2_ctrl_curves": o2_ctrl_curves,
    }


@st.cache_data(show_spinner=False)
def _cached_intl_game_trajectory(npz_filename: str) -> dict[str, Any]:
    """Încarcă și decimează cu păstrarea extremelor curba .npz a unui joc internațional / electronic RNG."""
    npz_p = HERE / "rezultate" / npz_filename
    with np.load(npz_p, allow_pickle=False) as zn:
        ec = zn["E_curve"].astype(np.float64)
        l10 = zn["log10_E_curve"].astype(np.float64)
        wp = zn["w_portfolio_curve"].astype(np.float64)
        ch = _channel_curves_from_portfolio(wp)
        ed = [str(x) for x in zn["eval_dates"].tolist()]
        es = zn["eval_steps"].astype(np.int64)
        idx = _decimate_indices(ec, max_points=1600)
        return {
            "dates": [ed[int(i)] for i in idx],
            "steps": [int(es[int(i)]) for i in idx],
            "E_curve": [float(ec[int(i)]) for i in idx],
            "log10_E": [float(l10[int(i)]) for i in idx],
            "w_0": [float(ch["w_0"][int(i)]) for i in idx],
            "w_O1": [float(ch["w_O1"][int(i)]) for i in idx],
            "w_O2": [float(ch["w_O2"][int(i)]) for i in idx],
            "w_O4": [float(ch["w_O4"][int(i)]) for i in idx],
            "min_E_exact": float(ec.min()),
            "max_E_exact": float(ec.max()),
            "final_E_exact": float(ec[-1]),
            "n_steps": int(es.shape[0]),
        }


@st.cache_data(show_spinner=False)
def _cached_oneclick_ro_and_abroad(config_key: str) -> dict[str, Any]:
    """Calculează într-un singur apel read-only toate potrivirile cauzale (CÂTE și UNDE) dacă s-ar fi jucat
    simultan toate cele 3 jocuri România (6/49 + 5/40 + Joker):
      1. În România (pe arhivele oficiale 6/49, 5/40, Joker);
      2. În afara României (verificare cauzală d_RO < d_ext pe loteriile externe cu format compatibil k_RO = k_ext).
    """
    rez_dir = HERE / "rezultate"
    abl_ro = json.loads((rez_dir / "ABLATIE_RO.json").read_text(encoding="utf-8"))
    npz_slug = RO_NPZ_MAP.get(config_key, "full_hsv4")

    ro_summary_rows: list[dict[str, Any]] = []
    ro_where_rows: list[dict[str, Any]] = []
    ro_trajs: dict[str, tuple[list[str], list[list[int]], list[int | None]]] = {}

    tot_ro_draws = 0
    tot_ro_3p, tot_ro_u3p = 0, 0.0
    tot_ro_4p, tot_ro_u4p = 0, 0.0
    tot_ro_5p, tot_ro_u5p = 0, 0.0
    tot_ro_6, tot_ro_2j, tot_ro_jok = 0, 0, 0

    for m_code in ("649", "540", "joker"):
        g_label, _, _, k_m, _ = RO_GAME_CONFIGS[m_code]
        cfg_rep = abl_ro["games"][m_code]["configs"][config_key]
        cats = cfg_rep["categories"]
        tiers = cats["winning_tiers"]
        jb = cats.get("joint_bonus_tiers", {})
        bh = cats.get("bonus_ball_hits", {})

        n_dr = int(cats["n_target_draws"])
        c3 = int(tiers.get("3+", {}).get("HSV4", 0))
        u3 = float(tiers.get("3+", {}).get("expected_U", 0.0))
        c4 = int(tiers.get("4+", {}).get("HSV4", 0))
        u4 = float(tiers.get("4+", {}).get("expected_U", 0.0))
        k5_key = "5+" if "5+" in tiers else "5/5"
        c5 = int(tiers.get(k5_key, {}).get("HSV4", 0))
        u5 = float(tiers.get(k5_key, {}).get("expected_U", 0.0))
        c6 = int(tiers.get("6/6", {}).get("HSV4", 0)) if "6/6" in tiers else 0
        c2j = int(jb.get("2+Bonus", {}).get("HSV4", 0)) if jb else 0
        cjok = int(bh.get("HSV4", 0)) if bh else 0

        tot_ro_draws += n_dr
        tot_ro_3p += c3
        tot_ro_u3p += u3
        tot_ro_4p += c4
        tot_ro_u4p += u4
        tot_ro_5p += c5
        tot_ro_u5p += u5
        tot_ro_6 += c6
        tot_ro_2j += c2j
        tot_ro_jok += cjok

        ro_summary_rows.append(
            {
                "Joc România": f"{g_label} ({m_code.upper()})",
                "Extrageri evaluate": n_dr,
                "Potriviri 3+ (vs U)": f"{c3} (U: {u3:.1f})",
                "Potriviri 4+ (vs U)": f"{c4} (U: {u4:.2f})",
                "Potriviri 5+ (vs U)": f"{c5} (U: {u5:.2f})",
                "6/6": str(c6) if m_code == "649" else "—",
                "2 + Joker / +Joker total": f"{c2j} / {cjok}" if m_code == "joker" else "—",
            }
        )

        ds = PM.build_game_dataset(m_code, "live", device="cpu")
        with np.load(rez_dir / f"ro_{m_code}_{npz_slug}_walkforward.npz", allow_pickle=False) as zn:
            eval_steps = zn["eval_steps"].astype(np.int64).tolist()
            eval_dates = [str(x) for x in zn["eval_dates"].tolist()]
            sig_a = zn["sigma_alpha"].astype(np.int64).tolist()
            jok_a = (
                [int(x) for x in zn["joker_alpha"].astype(np.int64).tolist()]
                if "joker_alpha" in zn.files
                else [None] * len(eval_dates)
            )
        ro_trajs[m_code] = (eval_dates, sig_a, jok_a)

        offs = ds.step_offsets.tolist()
        draws = ds.draws.tolist()
        joks = ds.joker.tolist() if ds.joker is not None else None
        for idx_s, s_val in enumerate(eval_steps):
            ta = [int(x) for x in sig_a[idx_s]]
            ta_set = set(ta)
            ja = jok_a[idx_s]
            for r_i in range(offs[s_val], offs[s_val + 1]):
                db = [int(x) for x in draws[r_i]]
                common = sorted(ta_set & set(db))
                jh = int(ja == int(joks[r_i])) if (ja is not None and joks is not None) else 0
                if len(common) >= 3 or (len(common) >= 2 and jh == 1):
                    cat_lbl = f"{len(common)}/{k_m}" + (" + Joker" if jh == 1 else "")
                    ta_fmt = " ".join(f"{b:02d}" for b in ta) + (f" + J{ja:02d}" if ja is not None else "")
                    db_fmt = " ".join(f"{b:02d}" for b in db) + (
                        f" + J{int(joks[r_i]):02d}" if joks is not None else ""
                    )
                    ro_where_rows.append(
                        {
                            "_rank": len(common) * 10 + jh,
                            "Data": str(ds.dates[r_i]),
                            "Unde (Joc RO)": g_label,
                            "Categorie": cat_lbl,
                            "Numere potrivite": " ".join(f"{b:02d}" for b in common)
                            + (f" (+J{ja:02d})" if jh == 1 and ja is not None else ""),
                            "Starea α pre-extragere": ta_fmt,
                            "Extragerea oficială RO": db_fmt,
                        }
                    )

    ro_summary_rows.append(
        {
            "Joc România": "TOTAL CUMULAT (6/49 + 5/40 + Joker)",
            "Extrageri evaluate": tot_ro_draws,
            "Potriviri 3+ (vs U)": f"{tot_ro_3p} (U: {tot_ro_u3p:.1f})",
            "Potriviri 4+ (vs U)": f"{tot_ro_4p} (U: {tot_ro_u4p:.2f})",
            "Potriviri 5+ (vs U)": f"{tot_ro_5p} (U: {tot_ro_u5p:.2f})",
            "6/6": str(tot_ro_6),
            "2 + Joker / +Joker total": f"{tot_ro_2j} / {tot_ro_jok}",
        }
    )
    ro_where_rows.sort(key=lambda r: (-int(r["_rank"]), r["Data"]), reverse=False)
    # Sortăm descrescător după rang și dată mai recentă la egalitate
    ro_where_rows.sort(key=lambda r: (int(r["_rank"]), r["Data"]), reverse=True)

    # 2. Verificare cauzală în afara României (d_RO < d_ext, format identic de bilet k_RO == k_ext și max(bilet) <= N_ext)
    prov_intl = json.loads((HERE / "date_intl" / "PROVENIENTA_INTL.json").read_text(encoding="utf-8"))
    intl_summary_rows: list[dict[str, Any]] = []
    intl_where_rows: list[dict[str, Any]] = []

    tot_ext_valid = 0
    tot_ext_3p, tot_ext_u3p = 0, 0.0
    tot_ext_4p, tot_ext_u4p = 0, 0.0
    tot_ext_5p = 0
    tot_ext_2b = 0

    for m_code in ("649", "540", "joker"):
        g_ro_lbl, _, _, k_ro, _ = RO_GAME_CONFIGS[m_code]
        ed_ro, sa_ro, ja_ro = ro_trajs[m_code]
        for gc in ALL_INTL_ORDER:
            meta = prov_intl["datasets"].get(gc)
            if not meta:
                continue
            N_ext = int(meta["N"])
            r_ext = int(meta["r_draw"])
            k_ext = int(meta["k_ticket"])
            bm_ext = meta.get("bonus_m")
            if k_ro != k_ext:
                continue

            denom = float(math.comb(N_ext, k_ro))
            p3p = sum(
                math.comb(r_ext, h) * math.comb(N_ext - r_ext, k_ro - h) / denom
                for h in range(3, min(r_ext, k_ro) + 1)
                if k_ro - h <= N_ext - r_ext
            )
            p4p = sum(
                math.comb(r_ext, h) * math.comb(N_ext - r_ext, k_ro - h) / denom
                for h in range(4, min(r_ext, k_ro) + 1)
                if k_ro - h <= N_ext - r_ext
            )

            rows_ext = [
                json.loads(ln)
                for ln in (QL / meta["jsonl_file"]).read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
            n_val, c3, c4, c5, c2b = 0, 0, 0, 0, 0
            for row in rows_ext:
                d_ext = str(row["draw_date"])
                pos = bisect.bisect_left(ed_ro, d_ext) - 1  # strict anterior datei externe (cauzal!)
                if pos < 0:
                    continue
                ticket = sa_ro[pos]
                if max(ticket) > N_ext:
                    continue
                n_val += 1
                j_ro = ja_ro[pos]
                b_ext = row.get("bonus")
                b_hit = (
                    int(int(j_ro) == int(b_ext))
                    if (bm_ext and j_ro is not None and b_ext is not None and int(j_ro) <= int(bm_ext))
                    else 0
                )
                ext_nums = [int(x) for x in row["numbers"]]
                common = sorted(set(ticket) & set(ext_nums))
                hc = len(common)
                if hc >= 3:
                    c3 += 1
                if hc >= 4:
                    c4 += 1
                if hc >= 5:
                    c5 += 1
                if hc == 2 and b_hit == 1:
                    c2b += 1
                if hc >= 3 or (hc >= 2 and b_hit == 1):
                    cat_e = f"{hc}/{k_ro}" + (" + Bonus" if b_hit == 1 else "")
                    t_fmt = " ".join(f"{b:02d}" for b in ticket) + (f" + J{int(j_ro):02d}" if j_ro is not None else "")
                    d_fmt = " ".join(f"{b:02d}" for b in ext_nums) + (
                        f" + B{int(b_ext):02d}" if b_ext is not None else ""
                    )
                    intl_where_rows.append(
                        {
                            "_rank": hc * 10 + b_hit,
                            "Data externă": d_ext,
                            "Joc RO jucat": g_ro_lbl,
                            "Unde în afara României": str(meta["game_name"]),
                            "Categorie": cat_e,
                            "Numere potrivite": " ".join(f"{b:02d}" for b in common)
                            + (f" (+B{int(b_ext):02d})" if b_hit == 1 and b_ext is not None else ""),
                            "Starea α RO (data RO)": f"{t_fmt} ({ed_ro[pos]})",
                            "Extragerea externă": d_fmt,
                        }
                    )

            if n_val > 0:
                tot_ext_valid += n_val
                tot_ext_3p += c3
                tot_ext_u3p += n_val * p3p
                tot_ext_4p += c4
                tot_ext_u4p += n_val * p4p
                tot_ext_5p += c5
                tot_ext_2b += c2b
                intl_summary_rows.append(
                    {
                        "Joc RO sursă": g_ro_lbl,
                        "Unde în afara României (Urnă compatibilă)": str(meta["game_name"]),
                        "Extrageri valide cauzal": n_val,
                        "Potriviri 3+ (vs U)": f"{c3} (U: {n_val * p3p:.1f})",
                        "Potriviri 4+ (vs U)": f"{c4} (U: {n_val * p4p:.2f})",
                        "Potriviri 5+": c5,
                        "2 + Bonus": str(c2b) if (m_code == "joker" and bm_ext) else "—",
                    }
                )

    intl_summary_rows.append(
        {
            "Joc RO sursă": "TOTAL CELE 3 JOCURI RO ÎN AFARA ROMÂNIEI",
            "Unde în afara României (Urnă compatibilă)": "Toate loteriile externe compatibile (k_RO = k_ext)",
            "Extrageri valide cauzal": tot_ext_valid,
            "Potriviri 3+ (vs U)": f"{tot_ext_3p} (U: {tot_ext_u3p:.1f})",
            "Potriviri 4+ (vs U)": f"{tot_ext_4p} (U: {tot_ext_u4p:.2f})",
            "Potriviri 5+": tot_ext_5p,
            "2 + Bonus": str(tot_ext_2b),
        }
    )
    intl_where_rows.sort(key=lambda r: (int(r["_rank"]), r["Data externă"]), reverse=True)

    return {
        "ro_totals": {
            "draws": tot_ro_draws,
            "c3": tot_ro_3p,
            "u3": tot_ro_u3p,
            "c4": tot_ro_4p,
            "u4": tot_ro_u4p,
            "c5": tot_ro_5p,
            "c6": tot_ro_6,
            "c2j": tot_ro_2j,
            "cjok": tot_ro_jok,
        },
        "ext_totals": {
            "valid_draws": tot_ext_valid,
            "c3": tot_ext_3p,
            "u3": tot_ext_u3p,
            "c4": tot_ext_4p,
            "u4": tot_ext_u4p,
            "c5": tot_ext_5p,
            "c2b": tot_ext_2b,
        },
        "ro_summary_rows": ro_summary_rows,
        "ro_where_rows": [{k: v for k, v in r.items() if k != "_rank"} for r in ro_where_rows],
        "ro_where_4plus": [{k: v for k, v in r.items() if k != "_rank"} for r in ro_where_rows if int(r["_rank"]) >= 40],
        "intl_summary_rows": intl_summary_rows,
        "intl_where_rows": [{k: v for k, v in r.items() if k != "_rank"} for r in intl_where_rows],
        "intl_where_4plus": [
            {k: v for k, v in r.items() if k != "_rank"} for r in intl_where_rows if int(r["_rank"]) >= 40
        ],
    }


def _render_oneclick_all_ro_matches(config_key: str) -> None:
    """Panou 1-Click: afișează instantaneu CÂTE și UNDE ar fi fost potriviri jucând toate cele 3 jocuri RO
    (6/49 + 5/40 + Joker), atât în România cât și în afara României."""
    data = _cached_oneclick_ro_and_abroad(config_key)
    rt = data["ro_totals"]
    et = data["ext_totals"]

    st.markdown(
        f"### 🎯 Raport 1-Click: Câte & Unde Ar Fi Fost Potriviri Jucând Toate Cele 3 Jocuri România (`6/49 + 5/40 + Joker` · `{config_key}`)"
    )
    st.caption(
        "Evaluare strict cauzală pre-extragere (fără scurgere din viitor): fiecare variantă `α` a fost generată "
        "exclusiv din istoricul anterior extragerii verificate. Variantele sunt **minime de energie / stări statistice "
        "condiționate de istoric, NU predicții** și fără promisiuni de câștig (`positive_claims_allowed=false`)."
    )

    st.markdown(
        '<div class="ql-grid">'
        + _card("EXTRAGERI RO EVALUATE (3 JOCURI)", f"{rt['draws']}", "cyan")
        + _card("ÎN ROMÂNIA · POTRIVIRI 4+", f"{rt['c4']} (U: {rt['u4']:.1f})", "lime")
        + _card("ÎN ROMÂNIA · POTRIVIRI 3+", f"{rt['c3']} (U: {rt['u3']:.1f})", "amber")
        + _card("ÎN ROMÂNIA · 2+JOKER / +JOKER", f"{rt['c2j']} / {rt['cjok']}")
        + _card("ÎN AFARA RO · POTRIVIRI 4+", f"{et['c4']} (U: {et['u4']:.1f})", "lime")
        + _card("ÎN AFARA RO · POTRIVIRI 3+", f"{et['c3']} (U: {et['u3']:.1f})", "mag")
        + "</div>",
        unsafe_allow_html=True,
    )

    only_4plus = st.checkbox(
        " Afișează în tabelele «UNDE» doar potrivirile mari (4+ numere principale)",
        value=False,
        key="hsv4_oneclick_only4p",
    )

    st.markdown("#### 🇷🇴 1. În România — Cumulat pe Toate Cele 3 Jocuri (`Loto 6/49` + `Loto 5/40` + `Joker`)")
    st.dataframe(pd.DataFrame(data["ro_summary_rows"]), width="stretch", hide_index=True)

    ro_loc = data["ro_where_4plus"] if only_4plus else data["ro_where_rows"]
    st.markdown(
        f"**Unde exact s-au produs potrivirile în România (`{len(ro_loc)}` extrageri afișate — `6/6: {rt['c6']}`, `5+: {rt['c5']}`, `4+: {rt['c4']}`, `3+: {rt['c3']}`, `2+Joker: {rt['c2j']}`):**"
    )
    st.dataframe(pd.DataFrame(ro_loc), width="stretch", hide_index=True)

    st.markdown(
        "#### 🌍 2. În Afara României — Dacă Aceleași Variante din Cele 3 Jocuri România (`6/49`, `5/40`, `Joker`) "
        "Ar Fi Fost Jucate pe Loteriile Externe Compatibile (`k_RO = k_ext`, `d_RO < d_ext`)"
    )
    st.dataframe(pd.DataFrame(data["intl_summary_rows"]), width="stretch", hide_index=True)

    ext_loc = data["intl_where_4plus"] if only_4plus else data["intl_where_rows"]
    st.markdown(
        f"**Unde exact în afara României s-ar fi potrivit variantele celor 3 jocuri RO (`{len(ext_loc)}` extrageri afișate — `5+: {et['c5']}`, `4+: {et['c4']}`, `3+: {et['c3']}`, `2+Bonus: {et['c2b']}`):**"
    )
    st.dataframe(pd.DataFrame(ext_loc), width="stretch", hide_index=True)
    st.markdown("---")


def clear_ui_caches() -> None:
    """Eliberează cache-urile UI HS-V4 la comutarea modului din bara laterală."""
    _cached_ro_static_bundle.clear()
    _cached_meteo_snapshot.clear()
    _cached_intl_overview.clear()
    _cached_intl_game_trajectory.clear()
    _cached_oneclick_ro_and_abroad.clear()


def _resolve_live_sync(mode: str, config_key: str = "Full_HSV4") -> dict[str, Any]:
    """Rulează sincronizarea cauzală verificată SHA-256 cu hs_v4/cache/ (suportă override env în teste)."""
    live_env = os.environ.get("QL649_HSV4_LIVE_ROOT")
    deriv_env = os.environ.get("QL649_HSV4_DERIV_ROOT")
    cache_env = os.environ.get("QL649_HSV4_CACHE_DIR")
    return get_or_advance_live(
        mode,
        config_key=config_key,
        live_root=Path(live_env) if live_env else None,
        deriv_root=Path(deriv_env) if deriv_env else None,
        cache_dir=Path(cache_env) if cache_env else None,
    )


def _render_multiplet_cards(
    variants: list[dict[str, Any]],
    k_ticket: int,
    total_states: int,
    det_core: list[int],
    distinct_cov: int,
    det_g3_reported: float,
) -> None:
    """Randează cele 3 carduri .ql-variant pentru multipletul (α, β, γ) ca stări statistice / minime de energie."""
    gram = compute_jastrow_gram([v["ticket"] for v in variants], k_ticket)
    ov = gram["ov_counts"]
    p_unif = 1.0 / float(total_states)

    vcols = st.columns(3)
    for idx_v, (col, var) in enumerate(zip(vcols, variants)):
        with col:
            balls_html = "".join(f'<span class="ql-ball">{int(b):02d}</span>' for b in var["ticket"])
            if "joker" in var and var["joker"] is not None:
                balls_html += f'<span class="ql-plus">+</span><span class="ql-ball jk">{int(var["joker"]):02d}</span>'
            ratio_u = float(var["prob"]) / p_unif
            if idx_v == 0:
                gram_line = f"Stare fundamentală portofoliu · <code>det G₁ = {gram['det_G1']:.4f}</code>"
            elif idx_v == 1:
                gram_line = (
                    f"Suprapunere <code>|α∩β| = {int(ov[0, 1])}/{k_ticket}</code> · "
                    f"<code>det G₂ = {gram['det_G2']:.4f}</code>"
                )
            else:
                gram_line = (
                    f"<code>|α∩γ| = {int(ov[0, 2])}/{k_ticket}</code> · "
                    f"<code>|β∩γ| = {int(ov[1, 2])}/{k_ticket}</code> · "
                    f"<code>det G₃ = {det_g3_reported:.4f}</code>"
                )
            st.markdown(
                f'<div class="ql-variant">'
                f'<div class="ql-vtitle">{VARIANT_TITLES[idx_v]}</div>'
                f'<div style="text-align:center;margin:8px 0 10px 0;">{balls_html}</div>'
                f'<div style="font-size:0.78rem;color:{NEON["dim"]};text-align:center;">'
                f'Energie <code>E(σ) = {var["energy"]:.5f}</code> · '
                f'<code>ln P = {var["log_prob"]:.4f}</code><br>'
                f'<code>P(σ) = {var["prob"]:.3e}</code> (<code>{ratio_u:.3f}× U</code>)<br>'
                f'{gram_line}</div></div>',
                unsafe_allow_html=True,
            )

    core_str = " ".join(f"{int(x):02d}" for x in det_core) if det_core else "∅ (disjuncte)"
    st.caption(
        f"Încadrare epistemică obligatorie: variantele (α, β, γ) și nucleul determinist [{core_str}] "
        f"(acoperire {distinct_cov} numere distincte, det G₃ = {det_g3_reported:.4f}) reprezintă "
        f"**minime de energie / stări statistice condiționate de istoric, NU predicții** și fără promisiuni de câștig."
    )


def _render_categories_section(cat_obj: dict[str, Any], k_ticket: int, label_prefix: str = "RO") -> None:
    """Randează tabelul și histograma distribuției pe categorii câștigătoare (3+, 4+, 5+, 6/6, +Joker/Bonus) vs U, B, R."""
    n_td = int(cat_obj["n_target_draws"])
    st.markdown(
        f"#### 🎯 Distribuția pe Categorii Câștigătoare ({label_prefix} · `{n_td}` extrageri evaluate vs `U`, `B`, `R`)"
    )

    tier_rows: list[dict[str, Any]] = []
    for t_name, t_vals in cat_obj.get("winning_tiers", {}).items():
        tier_rows.append(
            {
                "Categorie": t_name,
                "HS-V4 (α)": int(t_vals["HSV4"]),
                "Așteptat U (hipergeom.)": round(float(t_vals["expected_U"]), 4),
                "Frecvențe B": int(t_vals["B"]),
                "Recență R": int(t_vals["R"]),
                "Δ(HS-V4 − U)": round(float(t_vals["HSV4"]) - float(t_vals["expected_U"]), 4),
            }
        )
    if "bonus_ball_hits" in cat_obj and cat_obj["bonus_ball_hits"] is not None:
        bh = cat_obj["bonus_ball_hits"]
        tier_rows.append(
            {
                "Categorie": "+Joker / +Bonus (bilă secundară)",
                "HS-V4 (α)": int(bh["HSV4"]),
                "Așteptat U (hipergeom.)": round(float(bh["expected_U"]), 4),
                "Frecvențe B": int(bh["B"]),
                "Recență R": int(bh["R"]),
                "Δ(HS-V4 − U)": round(float(bh["HSV4"]) - float(bh["expected_U"]), 4),
            }
        )
    st.dataframe(pd.DataFrame(tier_rows), width="stretch", hide_index=True)

    hist_main = cat_obj.get("main_histogram", {})
    if hist_main:
        keys_h = list(hist_main.keys())
        f_cat = _fig(
            title=f"Histograma potrivirilor principale 0/{k_ticket} .. {k_ticket}/{k_ticket} vs Hipergeometric U, B, R",
            height=320,
            barmode="group",
            xaxis_title="Potriviri pe urna principală",
            yaxis_title="Număr de extrageri",
        )
        f_cat.add_trace(
            go.Bar(name="HS-V4 (α)", x=keys_h, y=[int(hist_main[h]["HSV4"]) for h in keys_h], marker_color=NEON["cyan"])
        )
        f_cat.add_trace(
            go.Bar(
                name="Așteptat U",
                x=keys_h,
                y=[float(hist_main[h]["expected_U"]) for h in keys_h],
                marker_color=NEON["dim"],
            )
        )
        f_cat.add_trace(
            go.Bar(name="Frecvențe B", x=keys_h, y=[int(hist_main[h]["B"]) for h in keys_h], marker_color=NEON["amber"])
        )
        f_cat.add_trace(
            go.Bar(name="Recență R", x=keys_h, y=[int(hist_main[h]["R"]) for h in keys_h], marker_color=NEON["mag"])
        )
        st.plotly_chart(f_cat, width="stretch")

    if "joint_bonus_tiers" in cat_obj and cat_obj["joint_bonus_tiers"]:
        jb = cat_obj["joint_bonus_tiers"]
        jb_rows = [
            {
                "Categorie Bipartită (+Joker / +Bonus)": k_jb,
                "HS-V4 (α)": int(v_jb["HSV4"]),
                "Așteptat U": round(float(v_jb["expected_U"]), 4),
                "Frecvențe B": int(v_jb["B"]),
                "Recență R": int(v_jb["R"]),
            }
            for k_jb, v_jb in jb.items()
        ]
        st.markdown("##### Categorii compuse cu bila secundară (`+Joker` / `+Bonus`)")
        st.dataframe(pd.DataFrame(jb_rows), width="stretch", hide_index=True)


def _render_tab_ro_states(mode: str, config_key: str, live: dict[str, Any], bundle: dict[str, Any]) -> None:
    """Tab 1: Multipletul (α, β, γ), nucleu determinist, spectru bosonic/Jennrich, meteo ERA5 și decontare cauzală."""
    _, N, r_draw, k_ticket, joker_m = RO_GAME_CONFIGS[mode]
    total_states = math.comb(N, k_ticket) * (joker_m if joker_m is not None else 1)

    st.markdown(
        f"### Multipletul Ortogonal Coulomb–Jastrow (α, β, γ) — `{CONFIG_LABELS[config_key]}`  \n"
        f"**Minime de energie / stări statistice condiționate de istoric, NU predicții** și fără promisiuni de câștig "
        f"(ultima dată în arhivă: `{live['last_date']}`, pas `{live['step_idx']}`, `{live['n_draws']}` extrageri)."
    )

    _render_multiplet_cards(
        variants=live["variants"],
        k_ticket=k_ticket,
        total_states=total_states,
        det_core=live["deterministic_core"],
        distinct_cov=int(live["distinct_covered"]),
        det_g3_reported=float(live["det_G3"]),
    )

    core_str = " ".join(f"{int(x):02d}" for x in live["deterministic_core"]) if live["deterministic_core"] else "∅"
    ch_m = live["channel_masses"]
    st.markdown(
        '<div class="ql-grid">'
        + _card("NUCLEU DETERMINIST", core_str)
        + _card("ACOPERIRE DISTINCTĂ", f"{live['distinct_covered']} / {3 * k_ticket}", "lime")
        + _card("DET G₃ (JASTROW)", f"{live['det_G3']:.4f}")
        + _card("MARTINGALA E_S (≥ 0.50)", f"{live['E_S']:.6f}", "lime" if live["E_S"] >= 0.50 else "mag")
        + _card("MASA ABSTENȚIEI w₀", f"{ch_m['w_0']:.6f}", "amber")
        + _card("NORMALIZARE EXACTĂ ∑P", f"{live['prob_sum_exact']:.12f}")
        + "</div>",
        unsafe_allow_html=True,
    )

    # Spectrul bosonic O1 + Jennrich și vectorul meteo ERA5 București
    col_sp, col_met = st.columns(2)
    tel = live["telemetry"]
    lam_raw = [float(x) for x in tel["bosonic_lam_raw"]]
    lam_att = [float(x) for x in tel["bosonic_lam_attenuated"]]
    jen_vals = [float(x) for x in tel["jennrich_vals"]]
    z_met = [float(x) for x in tel["z_meteo_last"]]

    with col_sp:
        st.markdown("#### 🔬 Spectrul Bosonic `O1` (`λ₁..λ₃`) & Tensorial Jennrich (`ν₁..ν₃`)")
        spec_df = pd.DataFrame(
            [
                {
                    "Mod r": f"r = {i + 1}",
                    "λ_r brut (K_pair)": round(lam_raw[i], 6),
                    "λ̃_r,+ atenuat (HS)": round(lam_att[i], 6),
                    "ν_r Jennrich (cumulant ord. 3)": round(jen_vals[i], 6),
                }
                for i in range(len(lam_raw))
            ]
        )
        st.dataframe(spec_df, width="stretch", hide_index=True)

        f_sp = _fig(
            title="Valori proprii bosonice Hubbard–Stratonovich & Jennrich",
            height=280,
            barmode="group",
            xaxis_title=" Mod spectral",
            yaxis_title="Amplitudine",
        )
        x_modes = [f"Mod {i + 1}" for i in range(len(lam_raw))]
        f_sp.add_trace(go.Bar(name="λ brut", x=x_modes, y=lam_raw, marker_color=NEON["cyan"]))
        f_sp.add_trace(go.Bar(name="λ̃_+ atenuat", x=x_modes, y=lam_att, marker_color=NEON["lime"]))
        f_sp.add_trace(go.Bar(name="|ν| Jennrich", x=x_modes, y=[abs(v) for v in jen_vals], marker_color=NEON["mag"]))
        st.plotly_chart(f_sp, width="stretch")

    with col_met:
        st.markdown("#### 🌦 Vectorul Meteo Exogen ERA5 București (`18:00 Europe/Bucharest`)")
        met_snap = _cached_meteo_snapshot(str(live["last_date"]))
        m_rec = met_snap["record"]
        m_prov = met_snap["provenance"]
        met_df = pd.DataFrame(
            [
                {
                    " Componentă": "ρ_air (densitate aer umed)",
                    "Valoare 18:00": f"{float(m_rec['rho_air_kg_m3']):.6f} kg/m³",
                    "z_met cauzal Welford": f"{z_met[0]:+.4f}",
                },
                {
                    " Componentă": "RH_2m (umiditate relativă)",
                    "Valoare 18:00": f"{float(m_rec['rh_2m_pct']):.2f} %",
                    "z_met cauzal Welford": f"{z_met[1]:+.4f}",
                },
                {
                    " Componentă": "ΔP_24h (variație presiune 24h)",
                    "Valoare 18:00": f"{float(m_rec['dp_24h_hpa']):+.2f} hPa",
                    "z_met cauzal Welford": f"{z_met[2]:+.4f}",
                },
                {
                    " Componentă": "T_2m / P_surf (auxiliar ERA5)",
                    "Valoare 18:00": f"{float(m_rec['temp_2m_c']):.1f} °C / {float(m_rec['surface_pressure_hpa']):.1f} hPa",
                    "z_met cauzal Welford": f"data {m_rec['date']} ({m_rec['source']})",
                },
            ]
        )
        st.dataframe(met_df, width="stretch", hide_index=True)

        f_met = _fig(
            title=f"Ultimele {len(met_snap['tail_dates'])} zile ERA5 București 18:00 — ρ_air (kg/m³)",
            height=280,
            xaxis_title="Data (Europe/Bucharest)",
            yaxis_title="ρ_air [kg/m³]",
        )
        f_met.add_trace(
            go.Scatter(
                x=met_snap["tail_dates"],
                y=met_snap["tail_rho"],
                mode="lines",
                name="ρ_air (kg/m³)",
                line=dict(color=NEON["amber"], width=2),
            )
        )
        st.plotly_chart(f_met, width="stretch")
        st.caption(
            f"Cache meteo sigilat `0444`: `{m_prov['total_days']}` zile (`{m_prov['start_date']}..{m_prov['end_date']}`), "
            f"SHA-256 `{m_prov['sha256'][:16]}…`."
        )

    # Marginale de incluziune π_i (și fibra Joker 1..20)
    pi_inc = np.asarray(live["pi_inclusion"], dtype=np.float64)
    u_inc = float(k_ticket) / float(N)
    ticket_sets = [set(int(x) for x in v["ticket"]) for v in live["variants"]]
    bar_colors = [
        NEON["cyan"] if (i + 1) in ticket_sets[0] else (
            NEON["mag"] if (i + 1) in (ticket_sets[1] | ticket_sets[2]) else "#2b3b55"
        )
        for i in range(N)
    ]
    f_pi = _fig(
        title=f"Probabilități marginale exacte de incluziune π_i = P_port(i ∈ σ) vs reper uniform k/N = {u_inc:.5f}",
        height=310,
        xaxis_title=f"Număr urnă (1..{N})",
        yaxis_title="π_i (∑ π_i = k)",
    )
    f_pi.add_trace(go.Bar(x=list(range(1, N + 1)), y=pi_inc.tolist(), marker_color=bar_colors, name="π_i HS-V4"))
    f_pi.add_hline(y=u_inc, line_dash="dash", line_color=NEON["amber"], annotation_text="Uniform k/N")
    st.plotly_chart(f_pi, width="stretch")

    if joker_m is not None and live.get("joker_prob") is not None:
        jp = np.asarray(live["joker_prob"], dtype=np.float64)
        f_jk = _fig(
            title=f"Distribuția marginală pe fibra secundară Joker (1..{joker_m}) vs 1/{joker_m} = {1.0/joker_m:.4f}",
            height=250,
            xaxis_title="Număr Joker (1..20)",
            yaxis_title="P_port(J = b)",
        )
        j_sel = int(live["variants"][0].get("joker", -1))
        jk_cols = [NEON["amber"] if (b + 1) == j_sel else NEON["violet"] for b in range(joker_m)]
        f_jk.add_trace(go.Bar(x=list(range(1, joker_m + 1)), y=jp.tolist(), marker_color=jk_cols, name="P_J(b)"))
        f_jk.add_hline(y=1.0 / float(joker_m), line_dash="dash", line_color=NEON["cyan"], annotation_text="1/20")
        st.plotly_chart(f_jk, width="stretch")

    st.markdown("#### 🔄 Jurnal Decontare Cauzală Automată & Ultimii Pași Walk-Forward")
    hist = list(live.get("settlement_history") or [])
    if hist:
        st.success(
            f"Decontare incrementală cauzală înregistrată: `{len(hist)}` extrageri decontate peste checkpoint-ul de bază "
            f"(`delta_steps={live['delta_steps']}` la apelul curent)."
        )
        st.dataframe(pd.DataFrame(hist[-15:]), width="stretch", hide_index=True)
    else:
        st.caption(
            f"Nicio extragere suplimentară față de checkpoint-ul verificat SHA-256 (`{live['checkpoint_sha256'][:16]}…`, "
            f"`cache_hit={live['cache_hit']}`). Mai jos sunt ultimii 10 pași evaluați cauzal în walk-forward:"
        )
    st.dataframe(pd.DataFrame(bundle["traj"]["tail_rows"]), width="stretch", hide_index=True)


def _render_tab_ro_qualification_ablation(mode: str, bundle: dict[str, Any]) -> None:
    """Tab 2: Calificare Q1–Q6 (6/6 PASS), Porți G1–G6 (X / 6) și Studiul Complet de Ablație RO."""
    cal_q = bundle["cal_q"]
    wf_ro = bundle["wf_ro"]
    abl_ro = bundle["abl_ro"]
    g_wf = wf_ro["games"][mode]

    st.markdown(
        f"### Certificat Pre-Arhivă `Q1–Q6`: `{cal_q['status']}` (`{cal_q['passed']} / {cal_q['total']} PASS`)  \n"
        f"`real_ro_archive_read = {cal_q['real_ro_archive_read']}` · `positive_claims_allowed = {cal_q['positive_claims_allowed']}` · "
        f"Protocol SHA-256 `{cal_q['protocol_sha256'][:16]}…`"
    )
    q_rows = [
        {
            "Test": str(c["id"]),
            "Criteriu algebric / cauzal / martor / control negativ": str(c["name"]),
            "Statut": "PASS" if c["pass"] else "FAIL",
            "Detaliu numeric": json.dumps(c["detail"], ensure_ascii=False)[:150],
        }
        for c in cal_q["checks"]
    ]
    st.dataframe(pd.DataFrame(q_rows), width="stretch", hide_index=True)

    st.markdown(
        f"### Porțile Walk-Forward `G1–G6` pe `{g_wf['game_name']}` — Verdict: `{g_wf['verdict_gates']}` "
        f"(`{g_wf['status']}`)"
    )
    gate_rows = [
        {
            "Poartă": str(g["id"]),
            "Regulă preînregistrată (PROTOCOL_HSV4.md §3.3)": str(g["rule"]),
            "Valoare măsurată": json.dumps(g["value"], ensure_ascii=False)
            if isinstance(g["value"], dict)
            else f"{float(g['value']):.6f}",
            "Statut": "PASS" if g["pass"] else "FAIL",
        }
        for g in g_wf["gates"]
    ]
    st.dataframe(pd.DataFrame(gate_rows), width="stretch", hide_index=True)

    win_names = [
        ("total", "Arhiva completă (s ≥ 100)"),
        ("half1", "Prima jumătate (H1)"),
        ("half2", "A doua jumătate (H2)"),
        ("last100", "Ultimii 100 pași"),
    ]
    w_rows = []
    for wk, w_lbl in win_names:
        w = g_wf["windows"][wk]
        w_rows.append(
            {
                "Fereastră": w_lbl,
                "Pași / Extrageri": f"{w['n_steps']} / {w['n_draws']}",
                "Potriviri HS-V4 / B / R": f"{w['hits_HSV4']} / {w['hits_B']} / {w['hits_R']}",
                "Exces mediu vs U": f"{w['excess_hits_vs_U']:+.6f}",
                "ΔLog(HS-V4 − U)": f"{w['log_score_HSV4'] - w['log_score_U']:+.4f}",
                "ΔLog(HS-V4 − B)": f"{w['log_score_HSV4'] - w['log_score_B']:+.4f}",
                "Brier HS-V4 / U / B": f"{w['brier_HSV4']:.2f} / {w['brier_U']:.2f} / {w['brier_B']:.2f}",
            }
        )
    st.dataframe(pd.DataFrame(w_rows), width="stretch", hide_index=True)

    st.markdown(f"### 🧪 Studiul Complet de Ablație pe `{g_wf['game_name']}` (`O1`, `O1+O2`, `O1+O4`, `Full HS-V4`)")
    abl_tbl = abl_ro["games"][mode]["comparison_table"]
    abl_rows = [
        {
            "Configurație": f"{r['config_key']} — {r['label']}",
            "Porți": str(r["verdict_gates"]),
            "Potriviri α / B / R": f"{r['hits_HSV4']} / {r['hits_B']} / {r['hits_R']}",
            "Exces vs U": f"{r['excess_hits_vs_U']:+.6f}",
            "ΔLog vs U": f"{r['log_diff_vs_U']:+.6f}",
            "ΔLog vs B": f"{r['log_diff_vs_B']:+.4f}",
            "Brier HS-V4 / U": f"{r['brier_HSV4']:.2f} / {r['brier_U']:.2f}",
            "E_S final": f"{r['E_S']:.6f}",
            "min E_s (≥ 0.50)": f"{r['min_E_s']:.6f} ({'OK' if r['guarantee_E_ge_050'] else 'ERR'})",
        }
        for r in abl_tbl
    ]
    st.dataframe(pd.DataFrame(abl_rows), width="stretch", hide_index=True)

    f_abl = _fig(
        title=f"Comparația traiectoriilor martingale E_s pe cele 4 configurații de ablație ({g_wf['game_name']})",
        height=340,
        xaxis_title="Data pașilor walk-forward",
        yaxis_title="Martingala E_s (prag garantat ≥ 0.50)",
    )
    palette = {"O1": NEON["cyan"], "O1_O2": NEON["amber"], "O1_O4": NEON["violet"], "Full_HSV4": NEON["lime"]}
    for cfg_k in ("O1", "O1_O2", "O1_O4", "Full_HSV4"):
        ac = bundle["abl_curves"][cfg_k]
        f_abl.add_trace(
            go.Scatter(
                x=ac["dates"],
                y=ac["E_curve"],
                mode="lines",
                name=CONFIG_LABELS[cfg_k],
                line=dict(color=palette[cfg_k], width=2.2 if cfg_k == "Full_HSV4" else 1.5),
            )
        )
    f_abl.add_hline(y=1.0, line_dash="dot", line_color=NEON["dim"], annotation_text="Reper neutru E = 1.0")
    f_abl.add_hline(y=0.50, line_dash="dash", line_color=NEON["red"], annotation_text="Prag garantat E ≥ 0.50")
    st.plotly_chart(f_abl, width="stretch")

    st.markdown("#### Sinteză Comparativă pe Toate Cele 3 Jocuri RO (`649`, `540`, `joker` — `Full HS-V4`)")
    ro_all_rows = []
    for m_code in ("649", "540", "joker"):
        gm = wf_ro["games"][m_code]
        wt = gm["windows"]["total"]
        mt = gm["martingale_trajectory"]
        tm = gm["timings"]
        ro_all_rows.append(
            {
                "Univers RO": gm["game_name"],
                "Porți G1–G6": gm["verdict_gates"],
                "Statut": gm["status"],
                "Pași / Extrageri": f"{wt['n_steps']} / {wt['n_draws']}",
                "Potriviri HS-V4 / B / R": f"{wt['hits_HSV4']} / {wt['hits_B']} / {wt['hits_R']}",
                "E_S final (min E_s)": f"{mt['E_S_final']:.4f} ({mt['min_E_s']:.4f})",
                "Timp GPU total (ms/pas)": f"{tm['total_sec']:.1f}s ({tm['ms_per_eval_step']:.1f} ms)",
            }
        )
    st.dataframe(pd.DataFrame(ro_all_rows), width="stretch", hide_index=True)


def _render_tab_ro_martingale_categories(
    mode: str,
    config_key: str,
    live: dict[str, Any],
    bundle: dict[str, Any],
) -> None:
    """Tab 3: Traiectoria martingală E_s (≥ 0.50), evoluția maselor Bayesiene (w_0, w_O1, w_O2, w_O4) și categorii."""
    _, _, _, k_ticket, _ = RO_GAME_CONFIGS[mode]
    abl_cfg_rep = bundle["abl_ro"]["games"][mode]["configs"][config_key]
    traj = bundle["traj"]

    dates_plot = list(traj["dates"])
    e_plot = list(traj["E_curve"])
    for rec in live.get("settlement_history") or []:
        dates_plot.append(str(rec["draw_date"]))
        e_plot.append(float(rec["E_after_step"]))

    st.markdown(
        f"### 📈 Traiectoria Martingală $E_s$ și Garanția Algebrică $E_s \\ge 0.50$ (`{CONFIG_LABELS[config_key]}`)"
    )
    m_info = abl_cfg_rep["martingale_trajectory"]
    st.markdown(
        '<div class="ql-grid">'
        + _card("E_0 INIȚIAL", f"{m_info['E_initial']:.4f}")
        + _card("E_S FINAL", f"{live['E_S']:.6f}", "lime" if live["E_S"] >= 0.50 else "mag")
        + _card("MIN E_s PE ARHIVĂ", f"{traj['min_E_exact']:.6f}", "lime")
        + _card("MAX E_s PE ARHIVĂ", f"{traj['max_E_exact']:.6f}", "cyan")
        + _card("GARANȚIE E_s ≥ 0.50", "VERIFICATĂ (100%)" if m_info["guarantee_E_ge_050_verified"] else "EROARE", "lime")
        + _card("PAȘI EVALUAȚI", f"{traj['n_eval_steps']}")
        + "</div>",
        unsafe_allow_html=True,
    )

    f_e = _fig(
        title=f"Evoluția cauzală a martingalei E_s = ∑ w_m^(0) E_s^(m) ({mode.upper()} · {config_key})",
        height=330,
        xaxis_title="Data pașilor walk-forward",
        yaxis_title="E_s",
    )
    f_e.add_trace(go.Scatter(x=dates_plot, y=e_plot, mode="lines", name="E_s portofoliu O3", line=dict(color=NEON["lime"], width=2)))
    f_e.add_hline(y=1.0, line_dash="dot", line_color=NEON["dim"], annotation_text="E = 1.0 (paritate cu U)")
    f_e.add_hline(y=0.50, line_dash="dash", line_color=NEON["red"], annotation_text="Prag garantat w_0 = 0.50 → E_s ≥ 0.50")
    st.plotly_chart(f_e, width="stretch")

    st.markdown("### ⚖ Evoluția Maselor Bayesiene $(w_0, w_{\\text{O1}}, w_{\\text{O2}}, w_{\\text{O4}})$")
    f_w = _fig(
        title="Mase posterioare cauzale pe canale (w_0 + w_O1 + w_O2 + w_O4 = 1.0)",
        height=330,
        xaxis_title="Data pașilor walk-forward",
        yaxis_title="Masă posterioară Bayesiană",
    )
    f_w.add_trace(go.Scatter(x=traj["dates"], y=traj["w_0"], mode="lines", name="w_0 (Abstenție uniformă U)", line=dict(color=NEON["amber"], width=2)))
    f_w.add_trace(go.Scatter(x=traj["dates"], y=traj["w_O1"], mode="lines", name="w_O1 (Bosonic + Jennrich)", line=dict(color=NEON["cyan"], width=1.8)))
    f_w.add_trace(go.Scatter(x=traj["dates"], y=traj["w_O2"], mode="lines", name="w_O2 (Aero-Meteo ERA5)", line=dict(color=NEON["mag"], width=1.8)))
    f_w.add_trace(go.Scatter(x=traj["dates"], y=traj["w_O4"], mode="lines", name="w_O4 (Spectral-Aritmetic RNG)", line=dict(color=NEON["violet"], width=1.8)))
    st.plotly_chart(f_w, width="stretch")

    bm = abl_cfg_rep["bayesian_masses"]
    bm_stages = [
        ("Prior inițial (s = 100)", bm["prior_initial"]),
        ("Mijlocul primei jumătăți", bm["midpoint_half1"]),
        ("Media pe walk-forward", bm["mean_over_walkforward"]),
        ("Posterior final post-arhivă", live["channel_masses"]),
    ]
    bm_rows = [
        {
            "Reper temporal": lbl_b,
            "w_0 (Uniform U)": f"{d_b['w_0']:.6f}",
            "w_O1 (Bosonic)": f"{d_b['w_O1']:.6e}",
            "w_O2 (Aero-Meteo)": f"{d_b['w_O2']:.6e}",
            "w_O4 (RNG Spectral)": f"{d_b['w_O4']:.6e}",
            "w_O1_O2 cuplat": f"{d_b['w_O1_O2_coupled']:.6e}",
        }
        for lbl_b, d_b in bm_stages
    ]
    st.dataframe(pd.DataFrame(bm_rows), width="stretch", hide_index=True)

    with st.expander("Detaliu grilă completă de 8 experți cauzali (m = 0..7)"):
        ew_init = bm["expert_weights_initial"]
        ew_fin = live["expert_weights"]
        exp_rows = [
            {
                "Index": m_i,
                "Expert": name_e,
                "Câmp 1-corp": f_kind,
                "η": eta_v,
                "γ (HS)": gam_v,
                "Prior w_m^(0)": f"{float(ew_init.get(name_e, 0.0)):.4f}",
                "Posterior curent w_m^(S)": f"{float(ew_fin.get(name_e, 0.0)):.6e}",
            }
            for m_i, name_e, f_kind, eta_v, gam_v, _ in EXPERT_GRID
        ]
        st.dataframe(pd.DataFrame(exp_rows), width="stretch", hide_index=True)

    _render_categories_section(abl_cfg_rep["categories"], k_ticket=k_ticket, label_prefix=f"RO {mode.upper()} · {config_key}")


def _intl_summary_row(entry: dict[str, Any], prov_ds: dict[str, Any]) -> dict[str, Any]:
    """Construiește un rând sintetic pentru tabelele de loterii mecanice externe / electronice RNG."""
    cfg = entry["configs"]["Full_HSV4"]
    wt = cfg["windows"]["total"]
    mt = cfg["martingale_trajectory"]
    post_m = cfg["bayesian_masses"]["posterior_final"]
    gp = entry["game_params"]
    urn_desc = f"{gp['k_ticket']}/{gp['N']}" + (f" (extr. {gp['r_draw']})" if gp["r_draw"] != gp["k_ticket"] else "")
    if gp.get("bonus_m"):
        urn_desc += f" + 1/{gp['bonus_m']}"
    t3 = cfg["categories"]["winning_tiers"].get("3+", {})
    t3_str = f"{t3.get('HSV4', 0)} (U:{t3.get('expected_U', 0.0):.1f})" if t3 else "—"
    return {
        "Cod": entry["game_code"],
        "Joc / Sursă oficială": f"{entry['game_name']} · {prov_ds.get('source_description', '')}",
        "Urnă": urn_desc,
        "Interval arhivă": f"{entry['archive']['first_date']} .. {entry['archive']['last_date']}",
        "Pași eval.": int(wt["n_steps"]),
        "Porți G1–G6": str(cfg["verdict_gates"]),
        "Potriviri α / B / R": f"{wt['hits_HSV4']} / {wt['hits_B']} / {wt['hits_R']}",
        "Exces vs U": f"{wt['excess_hits_vs_U']:+.5f}",
        "ΔLog vs U": f"{wt['log_score_HSV4'] - wt['log_score_U']:+.4f}",
        "E_S (min E_s)": f"{mt['E_S_final']:.4f} ({mt['min_E_s']:.4f})",
        "w_0 / w_O2 / w_O4 final": f"{post_m['w_0']:.4f} / {post_m['w_O2']:.2e} / {post_m['w_O4']:.2e}",
        "Categorii 3+": t3_str,
    }


def _render_tab_international() -> None:
    """Tab 4: 🌍 Internațional & Extrageri Electronice Online (Mecanic extern, RNG online, Skandináv 7/35, martor O2)."""
    ov = _cached_intl_overview()
    intl = ov["intl"]
    prov = ov["prov"]
    ds_meta = prov["datasets"]

    st.markdown("### 🌍 Internațional & Extrageri Electronice Online (`HS-V4` Faza 2B)")
    st.caption(
        f"Arhive publice oficiale verificate SHA-256 (`PROVENIENTA_INTL.json`: "
        f"`{'OK' if ov['prov_sha_ok'] else 'DRIFT'}`, `api_keys_used={prov['api_keys_used']}`, "
        f"`positive_claims_allowed={intl['positive_claims_allowed']}`). "
        f"Toate variantele `(α, β, γ)` afișate mai jos sunt **minime de energie / stări statistice condiționate de istoric, "
        f"NU predicții** și fără promisiuni de câștig."
    )

    # 1. Loterii mecanice externe
    st.markdown("#### ⚙ 1. Loterii Mecanice Externe (`FR Loto`, `HU Hatoslottó`, `HU Ötöslottó`, `US Powerball`)")
    mech_rows = [
        _intl_summary_row(intl["mechanical_external"][gc], ds_meta.get(gc, {}))
        for gc in MECHANICAL_ORDER
    ]
    st.dataframe(pd.DataFrame(mech_rows), width="stretch", hide_index=True)

    # 2. Extrageri electronice online RNG
    st.markdown("#### 💻 2. Extrageri Electronice Online RNG (`FDJ EuroDreams`, `NY Take 5`, `NY Cash4Life`, `NY Pick 10`)")
    rng_rows = [
        _intl_summary_row(intl["electronic_rng"][gc], ds_meta.get(gc, {}))
        for gc in ELECTRONIC_ORDER
    ]
    st.dataframe(pd.DataFrame(rng_rows), width="stretch", hide_index=True)

    # 3. Comparația directă pereche pe aceeași urnă 7/35 (HU Skandináv Lottó)
    st.markdown(
        "#### ⚖ 3. Comparația Directă Pereche pe Aceeași Urnă `7/35` — `HU Skandináv Lottó` "
        "(Tragerea 1 Mecanică `kézi` vs. Tragerea 2 Electronică RNG `gépi`)"
    )
    sk = intl["paired_skandinav_comparison"]
    sk_m = sk["mechanical"]
    sk_e = sk["electronic_rng"]
    st.markdown(
        '<div class="ql-grid">'
        + _card("URNĂ COMUNĂ PERECHE", str(sk["urn"]))
        + _card("PAȘI SINCRONIZAȚI", f"{sk['evaluated_steps']} ({sk['first_eval_date']}..{sk['last_date']})", "cyan")
        + _card("TRAGEREA 1 MECANICĂ (KÉZI)", f"Porți {sk_m['verdict_gates']} · Hits {sk_m['hits_HSV4']}", "lime")
        + _card("TRAGEREA 2 RNG (GÉPI)", f"Porți {sk_e['verdict_gates']} · Hits {sk_e['hits_HSV4']}", "amber")
        + _card("TIER 4+ KÉZI vs GÉPI", f"{sk_m['tier_4plus_HSV4']} vs {sk_e['tier_4plus_HSV4']} (U: {sk_m['tier_4plus_expected_U']:.1f})")
        + _card("ALINIERE DATE & COLOANE", "VERIFICATĂ" if (sk["same_dates_verified"] and sk["column_mapping_verified"]) else "EROARE", "lime")
        + "</div>",
        unsafe_allow_html=True,
    )

    col_map = sk["column_mapping_verified"] if isinstance(sk["column_mapping_verified"], dict) else {}
    sk_df = pd.DataFrame(
        [
            {
                "Regim fizic / algoritmic pe aceeași urnă 7/35": (
                    f"Tragerea 1 — Urnă Mecanică Fizică ({col_map.get('mechanical_manual_kezi', 'kézi sorsolás')})"
                ),
                "Porți G1–G6": sk_m["verdict_gates"],
                "Potriviri HS-V4 / B / R": f"{sk_m['hits_HSV4']} / {sk_m['hits_B']} / {sk_m['hits_R']}",
                "Exces vs U": f"{sk_m['excess_hits_vs_U']:+.6f}",
                "Log-Score HS-V4 (vs U)": f"{sk_m['log_score_HSV4']:.3f} ({sk_m['log_score_HSV4'] - sk_m['log_score_U']:+.4f})",
                "Brier HS-V4": f"{sk_m['brier_HSV4']:.2f}",
                "E_S (min E_s)": f"{sk_m['E_S']:.4f} ({sk_m['min_E_s']:.4f})",
                "Categorii 4+ (vs U)": f"{sk_m['tier_4plus_HSV4']} ({sk_m['tier_4plus_expected_U']:.2f})",
            },
            {
                "Regim fizic / algoritmic pe aceeași urnă 7/35": (
                    f"Tragerea 2 — Extragere Electronică RNG ({col_map.get('electronic_rng_gepi', 'gépi sorsolás')})"
                ),
                "Porți G1–G6": sk_e["verdict_gates"],
                "Potriviri HS-V4 / B / R": f"{sk_e['hits_HSV4']} / {sk_e['hits_B']} / {sk_e['hits_R']}",
                "Exces vs U": f"{sk_e['excess_hits_vs_U']:+.6f}",
                "Log-Score HS-V4 (vs U)": f"{sk_e['log_score_HSV4']:.3f} ({sk_e['log_score_HSV4'] - sk_e['log_score_U']:+.4f})",
                "Brier HS-V4": f"{sk_e['brier_HSV4']:.2f}",
                "E_S (min E_s)": f"{sk_e['E_S']:.4f} ({sk_e['min_E_s']:.4f})",
                "Categorii 4+ (vs U)": f"{sk_e['tier_4plus_HSV4']} ({sk_e['tier_4plus_expected_U']:.2f})",
            },
        ]
    )
    st.dataframe(sk_df, width="stretch", hide_index=True)

    c_sk1, c_sk2 = st.columns(2)
    sk_cm = ov["sk_curves"]["hu_skandinav_mech"]
    sk_ce = ov["sk_curves"]["hu_skandinav_rng"]
    with c_sk1:
        f_sk_e = _fig(
            title="HU Skandináv 7/35 — Martingala E_s: Kézi (Mecanic) vs Gépi (RNG)",
            height=290,
            xaxis_title="Data extragerii duble",
            yaxis_title="E_s (≥ 0.50)",
        )
        f_sk_e.add_trace(go.Scatter(x=sk_cm["dates"], y=sk_cm["E_curve"], mode="lines", name="Tragerea 1 Mecanică (kézi)", line=dict(color=NEON["lime"], width=2)))
        f_sk_e.add_trace(go.Scatter(x=sk_ce["dates"], y=sk_ce["E_curve"], mode="lines", name="Tragerea 2 Electronică RNG (gépi)", line=dict(color=NEON["mag"], width=2)))
        f_sk_e.add_hline(y=0.50, line_dash="dash", line_color=NEON["red"], annotation_text="E ≥ 0.50")
        st.plotly_chart(f_sk_e, width="stretch")
    with c_sk2:
        f_sk_w = _fig(
            title="HU Skandináv 7/35 — Masa activă (1 − w_0): Kézi vs Gépi",
            height=290,
            xaxis_title="Data extragerii duble",
            yaxis_title="1 − w_0^(s)",
        )
        f_sk_w.add_trace(go.Scatter(x=sk_cm["dates"], y=sk_cm["active_mass"], mode="lines", name="1 − w_0 (Mecanic kézi)", line=dict(color=NEON["cyan"], width=2)))
        f_sk_w.add_trace(go.Scatter(x=sk_ce["dates"], y=sk_ce["active_mass"], mode="lines", name="1 − w_0 (Electronic gépi)", line=dict(color=NEON["amber"], width=2)))
        st.plotly_chart(f_sk_w, width="stretch")

    # 4. Martorul de control negativ O2 pe fluxurile pur electronice RNG
    o2_sum = intl["o2_negative_control_summary"]
    st.markdown(
        f"#### 🛡 4. Martorul de Control Negativ `O2` pe Fluxurile Pur Electronice RNG "
        f"(`all_contracted={o2_sum['all_contracted']}`, `all_E_ge_050={o2_sum['all_E_ge_050']}`)"
    )
    o2_rows = [
        {
            "Flux electronic RNG": s_r["game_name"],
            "Pași evaluați": int(s_r["evaluated_steps"]),
            "Prior w_O2 (Ctrl O2)": f"{s_r['ctrl_w_O2_prior']:.2f}",
            "Final w_O2 (Ctrl O2)": f"{s_r['ctrl_w_O2_final']:.3e}",
            "Final w_0 (Ctrl O2)": f"{s_r['ctrl_w_0_final']:.6f}",
            "Prior → Final w_O2 (Full HS-V4)": f"{s_r['full_w_O2_prior']:.2f} → {s_r['full_w_O2_final']:.3e}",
            "min E_s (Ctrl / Full)": f"{s_r['ctrl_min_E_s']:.4f} / {s_r['full_min_E_s']:.4f}",
            "Contracție O2 & E_s ≥ 0.50": "PASS" if (s_r["contraction_verified"] and s_r["guarantee_E_ge_050"]) else "FAIL",
        }
        for s_r in o2_sum["streams"]
    ]
    st.dataframe(pd.DataFrame(o2_rows), width="stretch", hide_index=True)

    f_o2 = _fig(
        title="Contracția masei canalului fizic aero-mecanic w_O2^(s) pe extragerile pur electronice RNG (Control Negativ O2)",
        height=300,
        xaxis_title="Pas walk-forward relativ (s − warmup + 1, scară log)",
        yaxis_title="w_O2^(s) (plecare din prior 0.50)",
    )
    f_o2.update_xaxes(type="log")
    o2_colors = [NEON["cyan"], NEON["mag"], NEON["lime"], NEON["amber"], NEON["violet"]]
    for idx_c, s_r in enumerate(o2_sum["streams"]):
        gc_code = str(s_r["game_code"])
        c_data = ov["o2_ctrl_curves"][gc_code]
        f_o2.add_trace(
            go.Scatter(
                x=c_data["steps_rel"],
                y=c_data["w_O2"],
                mode="lines",
                name=gc_code,
                line=dict(color=o2_colors[idx_c % len(o2_colors)], width=2),
            )
        )
    st.plotly_chart(f_o2, width="stretch")

    # 5. Selector detaliat pentru orice joc internațional / electronic RNG
    st.markdown("---")
    st.markdown("#### 🔍 5. Inspector Detaliat Joc Internațional / Flux Electronic Online (`Full HS-V4`)")
    game_entries: dict[str, dict[str, Any]] = {}
    for gc in ALL_INTL_ORDER:
        if gc in intl["mechanical_external"]:
            game_entries[gc] = intl["mechanical_external"][gc]
        elif gc in intl["electronic_rng"]:
            game_entries[gc] = intl["electronic_rng"][gc]

    sel_intl = st.selectbox(
        "Selectează loteria externă (mecanică sau electronică online RNG)",
        list(game_entries.keys()),
        format_func=lambda k: f"{game_entries[k]['game_name']} [{ 'Mecanic Extern' if k in intl['mechanical_external'] else 'Electronic Online RNG' }]",
        key="hsv4_intl_game",
    )
    g_sel = game_entries[sel_intl]
    cfg_sel = g_sel["configs"]["Full_HSV4"]
    gp_sel = g_sel["game_params"]
    post_sel = cfg_sel["post_archive_state"]
    total_st_sel = math.comb(int(gp_sel["N"]), int(gp_sel["k_ticket"])) * (
        int(gp_sel["bonus_m"]) if gp_sel.get("bonus_m") else 1
    )

    st.markdown(
        f"##### Stări Statistice Post-Arhivă `(α, β, γ)` — `{g_sel['game_name']}` "
        f"(ultima dată `{g_sel['archive']['last_date']}`, verdict `{cfg_sel['verdict_gates']}`, `{cfg_sel['status']}`)  \n"
        f"**Minime de energie / stări statistice condiționate de istoric, NU predicții** și fără promisiuni de câștig."
    )
    _render_multiplet_cards(
        variants=post_sel["variants_jastrow_multiplet"],
        k_ticket=int(gp_sel["k_ticket"]),
        total_states=total_st_sel,
        det_core=post_sel["deterministic_core"],
        distinct_cov=int(post_sel["distinct_balls_covered"]),
        det_g3_reported=float(post_sel["det_G3"]),
    )

    itraj = _cached_intl_game_trajectory(_npz_rel_name(cfg_sel["trajectory_npz"]))
    ci1, ci2 = st.columns(2)
    with ci1:
        f_ie = _fig(
            title=f"Martingala E_s ({g_sel['game_code']} · min E_s = {itraj['min_E_exact']:.4f})",
            height=290,
            xaxis_title="Data",
            yaxis_title="E_s",
        )
        f_ie.add_trace(go.Scatter(x=itraj["dates"], y=itraj["E_curve"], mode="lines", name="E_s", line=dict(color=NEON["lime"], width=2)))
        f_ie.add_hline(y=0.50, line_dash="dash", line_color=NEON["red"], annotation_text="E ≥ 0.50")
        st.plotly_chart(f_ie, width="stretch")
    with ci2:
        f_iw = _fig(
            title=f"Mase Bayesiene (w_0, w_O1, w_O2, w_O4) — {g_sel['game_code']}",
            height=290,
            xaxis_title="Data",
            yaxis_title="Masă Bayesiană",
        )
        f_iw.add_trace(go.Scatter(x=itraj["dates"], y=itraj["w_0"], mode="lines", name="w_0", line=dict(color=NEON["amber"], width=2)))
        f_iw.add_trace(go.Scatter(x=itraj["dates"], y=itraj["w_O1"], mode="lines", name="w_O1", line=dict(color=NEON["cyan"], width=1.7)))
        f_iw.add_trace(go.Scatter(x=itraj["dates"], y=itraj["w_O2"], mode="lines", name="w_O2", line=dict(color=NEON["mag"], width=1.7)))
        f_iw.add_trace(go.Scatter(x=itraj["dates"], y=itraj["w_O4"], mode="lines", name="w_O4", line=dict(color=NEON["violet"], width=1.7)))
        st.plotly_chart(f_iw, width="stretch")

    ig_rows = [
        {
            "Poartă": str(g["id"]),
            "Regulă": str(g["rule"]),
            "Valoare": json.dumps(g["value"], ensure_ascii=False)
            if isinstance(g["value"], dict)
            else f"{float(g['value']):.6f}",
            "Statut": "PASS" if g["pass"] else "FAIL",
        }
        for g in cfg_sel["gates"]
    ]
    st.dataframe(pd.DataFrame(ig_rows), width="stretch", hide_index=True)
    _render_categories_section(
        cfg_sel["categories"],
        k_ticket=int(gp_sel["k_ticket"]),
        label_prefix=g_sel["game_name"],
    )


def render_hs_v4(mode: str) -> None:
    """Punctul principal de randare pentru motorul HS-V4 pe RO (`649`, `540`, `joker`) + tab Internațional & RNG."""
    if mode not in MODE_META:
        st.error(f"Mod necunoscut pentru HS-V4: {mode!r}")
        return

    st.markdown(EXTRA_CSS, unsafe_allow_html=True)
    meta = MODE_META[mode]

    st.markdown(f'<div class="ql-title">{meta["title"]}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="ql-sub">{meta["game"]} · {meta["rule"]} · {meta["space_desc"]} · '
        f"Hubbard–Stratonovich O1 + Aero-Meteo ERA5 O2 + Portofoliu Martingal O3 + Spectral RNG O4</div>",
        unsafe_allow_html=True,
    )
    st.info(f"⚖ **{HONEST_LABEL}**")

    with st.sidebar:
        config_key = st.selectbox(
            "Configurație canal HS-V4 (RO)",
            list(CONFIG_LABELS.keys()),
            format_func=CONFIG_LABELS.get,
            key="hsv4_ro_config",
        )

    live = _resolve_live_sync(mode, config_key=config_key)
    bundle = _cached_ro_static_bundle(mode, config_key=config_key)
    wf_mode = bundle["wf_ro"]["games"][mode]

    sync_badge = (
        f"CACHE HIT SHA-256 ({live['elapsed_sec']*1000:.1f} ms)"
        if live["cache_hit"]
        else f"AVANS CAUZAL +{live['delta_steps']} PAȘI ({live['elapsed_sec']:.2f} s)"
    )
    vram_mib = float(live["vram_allocated_after_bytes"]) / (1024.0 * 1024.0)
    st.caption(
        f"Sincronizare `hs_v4/cache/`: **{sync_badge}** · cheie sursă `{live['src_key'][:12]}…` · "
        f"checkpoint `{Path(live['checkpoint_path']).name}` (`{live['checkpoint_sha256'][:12]}…`) · "
        f"Calificare `Q1–Q6: 6/6 PASS` · Porți `{mode.upper()}: {wf_mode['verdict_gates']}` (`{wf_mode['status']}`) · "
        f"VRAM rezidual: `{vram_mib:.2f} MiB`."
    )

    is_open = bool(st.session_state.get("hsv4_oneclick_open", False))
    btn_label = (
        "✖ Închide panoul 1-Click: Potriviri Cele 3 Jocuri România (în RO & în Afara României)"
        if is_open
        else "🎯 1-CLICK: Vezi Câte & Unde Ar Fi Fost Potriviri — Toate Cele 3 Jocuri România (6/49 + 5/40 + Joker, în RO & în Afara României)"
    )
    if st.button(btn_label, key="hsv4_oneclick_btn", type="primary", width="stretch"):
        is_open = not is_open
        st.session_state["hsv4_oneclick_open"] = is_open
    if is_open:
        _render_oneclick_all_ro_matches(config_key=config_key)

    tab_states, tab_gates, tab_mart, tab_intl = st.tabs(
        [
            "⚛ Stări Statistice (α, β, γ) · Spectru & Meteo ERA5",
            "📉 Calificare Q1–Q6 · Porți G1–G6 & Ablație RO",
            "📊 Martingala E_s · Mase Bayesiene & Categorii RO",
            "🌍 Internațional & Extrageri Electronice Online",
        ]
    )

    with tab_states:
        _render_tab_ro_states(mode, config_key, live, bundle)
    with tab_gates:
        _render_tab_ro_qualification_ablation(mode, bundle)
    with tab_mart:
        _render_tab_ro_martingale_categories(mode, config_key, live, bundle)
    with tab_intl:
        _render_tab_international()
