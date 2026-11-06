"""QL649 — STEP 3: dashboard Streamlit „Quantum Lab 649” (app.py).

Terminal de laborator cuantic (estetică cyberpunk) peste motorul clasic GPU din engine.py.
Pornire:  .venv/bin/streamlit run app.py   (sau ./run_app.sh) → http://localhost:8649

Onestitate (permanent în UI): calcul clasic pe GPU; inspirația cuantică este matematică;
variantele sunt minimele energiei modelului, NU combinații cu șanse mai mari;
positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import torch

import engine as E
import validare as V
from parser import DEFAULT_SOURCE, build_dataset, device_events, resolve_device

ROOT = Path(__file__).resolve().parent
BT_DIR = ROOT / "rezultate" / "backtest_unic"
NULL_DIR = ROOT / "rezultate" / "multivers_pipeline"
SEAL_DIR = Path(os.environ.get("QL649_SEAL_DIR", str(ROOT / "rezultate" / "sigilii")))
FAST_MODE = os.environ.get("QL649_CONFIG", "") == "fast"
BASE_CFG = replace(E.PROTOCOL, mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60, gamma_grid=12) \
    if FAST_MODE else E.PROTOCOL

NEON = {"cyan": "#00f5ff", "mag": "#ff2bd6", "lime": "#b6ff00", "amber": "#ffb000", "violet": "#8f5bff",
        "bg": "#04010b", "panel": "#0d0624", "text": "#d7fbff", "dim": "#6f86a0", "red": "#ff3860"}
PLOT_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,6,36,0.65)",
                   font=dict(family="JetBrains Mono, Fira Code, monospace", color=NEON["text"], size=12),
                   margin=dict(l=40, r=20, t=50, b=40))

st.set_page_config(page_title="QL649 · Quantum Lab", page_icon="⚛", layout="wide", initial_sidebar_state="collapsed")

CSS = f"""
<style>
:root {{ --cyan:{NEON['cyan']}; --mag:{NEON['mag']}; --lime:{NEON['lime']}; --amber:{NEON['amber']}; }}
html, body, [data-testid="stAppViewContainer"] {{
  background: radial-gradient(ellipse at 20% 0%, #1a0b3d 0%, {NEON['bg']} 55%) fixed !important;
  font-family: 'JetBrains Mono','Fira Code','Consolas',monospace !important; }}
[data-testid="stAppViewContainer"]::before {{ content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
  background: repeating-linear-gradient(0deg, rgba(0,245,255,0.035) 0px, rgba(0,245,255,0.035) 1px, transparent 2px, transparent 4px); }}
h1,h2,h3 {{ font-family:'Orbitron','JetBrains Mono',monospace !important; letter-spacing:0.08em; }}
.ql-title {{ font-size:2.6rem !important; line-height:1.15; font-weight:800; letter-spacing:0.18em; margin:0;
  background: linear-gradient(90deg, var(--cyan), var(--mag) 60%, var(--amber)); -webkit-background-clip:text; color:transparent;
  text-shadow: 0 0 24px rgba(0,245,255,0.25); }}
.ql-sub {{ color:{NEON['dim']}; font-size:0.85rem; letter-spacing:0.12em; margin-top:-4px; }}
.ql-card {{ border:1px solid rgba(0,245,255,0.35); border-radius:10px; padding:12px 14px; background:rgba(13,6,36,0.78);
  box-shadow: 0 0 18px rgba(0,245,255,0.12), inset 0 0 22px rgba(255,43,214,0.06); }}
.ql-k {{ color:{NEON['dim']}; font-size:0.72rem; letter-spacing:0.14em; text-transform:uppercase; }}
.ql-v {{ color:var(--cyan); font-size:1.55rem; font-weight:700; text-shadow:0 0 12px rgba(0,245,255,0.55); }}
.ql-v.mag {{ color:var(--mag); text-shadow:0 0 12px rgba(255,43,214,0.55); }}
.ql-v.lime {{ color:var(--lime); text-shadow:0 0 12px rgba(182,255,0,0.5); }}
.ql-v.amber {{ color:var(--amber); text-shadow:0 0 12px rgba(255,176,0,0.5); }}
.ql-warn {{ border-left:3px solid var(--amber); padding:8px 12px; background:rgba(255,176,0,0.07); color:#ffe2a8; font-size:0.82rem; }}
.ql-variant {{ border:2px solid var(--cyan); border-radius:14px; padding:18px 10px 14px 10px; margin-bottom:14px; text-align:center;
  background:linear-gradient(160deg, rgba(0,245,255,0.08), rgba(255,43,214,0.06)); box-shadow:0 0 30px rgba(0,245,255,0.18); }}
.ql-variant.v2 {{ border-color:var(--mag); box-shadow:0 0 30px rgba(255,43,214,0.2); }}
.ql-variant.v3 {{ border-color:var(--lime); box-shadow:0 0 30px rgba(182,255,0,0.16); }}
.ql-vlabel {{ font-size:0.8rem; letter-spacing:0.3em; color:{NEON['dim']}; margin-bottom:10px; }}
.ql-ball {{ display:inline-flex; align-items:center; justify-content:center; width:62px; height:62px; margin:5px; border-radius:50%;
  font-size:1.55rem; font-weight:800; color:#04010b; background:radial-gradient(circle at 30% 28%, #ffffff 0%, var(--cyan) 38%, #006c80 100%);
  box-shadow:0 0 18px rgba(0,245,255,0.75); }}
.v2 .ql-ball {{ background:radial-gradient(circle at 30% 28%, #ffffff 0%, var(--mag) 40%, #6d0059 100%); box-shadow:0 0 18px rgba(255,43,214,0.75); }}
.v3 .ql-ball {{ background:radial-gradient(circle at 30% 28%, #ffffff 0%, var(--lime) 40%, #3f5c00 100%); box-shadow:0 0 18px rgba(182,255,0,0.7); }}
.ql-meta {{ color:{NEON['dim']}; font-size:0.78rem; margin-top:8px; }}
[data-testid="stTabs"] button p {{ font-size:0.95rem; letter-spacing:0.06em; }}
[data-testid="stTabs"] button[aria-selected="true"] p {{ color:var(--cyan); text-shadow:0 0 8px rgba(0,245,255,0.7); }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Calcul (în cache) — tensori → NumPy pentru vizualizare
# ---------------------------------------------------------------------------
def _np(x):
    if torch.is_tensor(x):
        x = x.detach().cpu()
        return x.numpy() if not x.is_complex() else x.numpy()
    return x


@st.cache_resource(show_spinner=False)
def get_dataset():
    dev = resolve_device()
    return build_dataset(DEFAULT_SOURCE, dev)


@st.cache_resource(show_spinner=False)
def run_engine(cfg_json: str) -> dict:
    cfg = E.Config(**json.loads(cfg_json))
    ds = get_dataset()
    res = E.run_full(ds, cfg, ds.device)
    return {k: _np(v) for k, v in res.items()}


@st.cache_resource(show_spinner=False)
def get_sci() -> dict:
    p = BT_DIR / "SCI.json"
    if p.exists():
        d = json.loads(p.read_text())
        d["origin"] = "backtest_unic/SCI.json"
        return d
    ds = get_dataset()
    d = V.compute_sci(ds, M=2048 if FAST_MODE else V.M_NULL)
    d["origin"] = "calcul live (Multivers Nul)"
    return d


def load_json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _round(v, nd: int = 4):
    if isinstance(v, float):
        return round(v, nd)
    if isinstance(v, list):
        return [_round(x, nd) for x in v]
    return v


def union_expected(res: dict):
    """Așteptarea uniformă a reuniunii celor 3 variante, condiționată de mărimea reală a reuniunii."""
    try:
        P = np.load(BT_DIR / "PREDICTII.npz")
        V, k0 = P["variants"], int(P["ks"][0])
        usz = np.array([len(set(V[i].ravel().tolist())) for i in range(V.shape[0])])
        steps = np.asarray(res["per_target"]["step"]) - k0
        return float((usz[steps] * 6 / 49).sum()), float(usz.mean())
    except Exception:
        return None, None


def card(k: str, v: str, cls: str = "") -> str:
    return f'<div class="ql-card"><div class="ql-k">{k}</div><div class="ql-v {cls}">{v}</div></div>'


def fig(**kw) -> go.Figure:
    f = go.Figure()
    f.update_layout(**PLOT_LAYOUT, **kw)
    return f


# ---------------------------------------------------------------------------
# Antet
# ---------------------------------------------------------------------------
st.markdown('<div class="ql-title">⚛ QUANTUM LAB 649</div>'
            '<p class="ql-sub">NON-HERMITIAN · AMPLITUHEDRON · POINCARÉ · KURAMOTO · BORN–BOLTZMANN · MCMC — LOTO 6/49 RO</p>',
            unsafe_allow_html=True)

with st.spinner("Inițializare câmp cuantic pe GPU… (prima rulare ≈ 30–40 s)"):
    ds = get_dataset()
    R = run_engine(json.dumps(asdict(BASE_CFG), sort_keys=True))
    SCI = get_sci()

h = st.columns([1.1, 1, 1, 1.2, 1.3])
h[0].markdown(card("extrageri analizate", f"{R['n_draws_used']:,}".replace(",", " ")), unsafe_allow_html=True)
h[1].markdown(card("pași (zile)", f"{R['n_steps']:,}".replace(",", " "), "mag"), unsafe_allow_html=True)
h[2].markdown(card("ultima extragere", f"{R['last_date']}", "amber"), unsafe_allow_html=True)
sci_cls = "lime" if SCI["p_empirical"] > 0.05 else "mag"
h[3].markdown(card("indice coerență structurală", f"{SCI['SCI']:+.2f}σ · p={SCI['p_empirical']:.3f}", sci_cls),
              unsafe_allow_html=True)


@st.fragment(run_every="2s")
def vram_widget():
    if torch.cuda.is_available():
        alloc = torch.cuda.memory_allocated() / 2 ** 20
        peak = torch.cuda.max_memory_allocated() / 2 ** 20
        tot = torch.cuda.get_device_properties(0).total_memory / 2 ** 20
        st.markdown(card(f"VRAM · {torch.cuda.get_device_name(0).replace('NVIDIA GeForce ', '')}",
                         f"{alloc:,.0f} / {tot:,.0f} MiB"), unsafe_allow_html=True)
        st.progress(min(1.0, alloc / tot), text=f"vârf {peak:,.0f} MiB · {dt.datetime.now().strftime('%H:%M:%S')}")
    else:
        st.markdown(card("dispozitiv", "CPU (fallback)", "amber"), unsafe_allow_html=True)


with h[4]:
    vram_widget()

st.markdown(
    f'<div class="ql-warn">⚠ Calcul <b>clasic</b> pe {R["device"].upper()} (PyTorch). Inspirația cuantică este strict matematică — '
    f'fără hardware cuantic, fără avantaj cuantic. Dacă extragerile sunt uniforme și independente, niciun operator nu poate '
    f'prezice extragerea următoare. Variantele sunt <b>minimele energiei modelului</b>, nu combinații cu șanse mai mari. '
    f'<code>positive_claims_allowed=false</code> · protocol <code>{(R.get("protocol_sha256") or "")[:12]}…</code> · '
    f'config <code>{R["config_digest"][:12]}…</code>{" · <b>MOD FAST (test)</b>" if FAST_MODE else ""}</div>',
    unsafe_allow_html=True)
if device_events():
    st.caption("Evenimente dispozitiv: " + " | ".join(device_events()))

tabs = st.tabs(["⚛ Colapsul funcției de undă", "🌀 Singularitate hiperbolică & Amplituhedron",
                "♾ Convergența terminală — Limita Cuantică", "🌌 Multiversul Nul", "⏳ Mașina Timpului",
                "🧪 Ablație & Sigiliu temporal", "📉 Rupturi de regim (BO649)", "🎱 Urna ponderată (WU649)",
                "🔢 Masa glifelor (GL649)", "🍂 Anotimpurile bilelor (SE649)", "🎠 Caruselul seturilor (CS649)",
                "🌌 Orizontul evenimentelor (PL649)"])

# ---------------------------------------------------------------------------
# Tab 1 — Colaps
# ---------------------------------------------------------------------------
with tabs[0]:
    P, psi, pi = R["P"], R["psi_f"], R["pi"]
    top = np.argsort(-P, kind="stable")[:10]
    nums = top + 1
    phase = np.angle(psi[top])
    c1, c2 = st.columns([1.15, 1])
    with c1:
        f = fig(title="TOP-10 AMPLITUDINI POST-COLAPS  P = |Ψ|²", xaxis_title="număr", yaxis_title="P (Born)")
        f.add_bar(x=[f"#{n}" for n in nums], y=P[top],
                  marker=dict(color=phase, colorscale="Twilight", cmin=-math.pi, cmax=math.pi,
                              colorbar=dict(title="arg Ψ"), line=dict(color=NEON["cyan"], width=1)),
                  hovertemplate="număr %{x}<br>P=%{y:.4f}<extra></extra>")
        f.update_xaxes(type="category", categoryorder="array", categoryarray=[f"#{n}" for n in nums])
        f.add_hline(y=1 / 49, line=dict(color=NEON["amber"], dash="dot"), annotation_text="uniform 1/49")
        st.plotly_chart(f, width="stretch")
    with c2:
        f = fig(title="COORDONATE DE FAZĂ ÎN PLANUL COMPLEX", xaxis_title="Re Ψ", yaxis_title="Im Ψ")
        allidx = np.arange(49)
        f.add_scatter(x=psi.real, y=psi.imag, mode="markers", marker=dict(size=6, color=NEON["dim"], opacity=0.5),
                      text=[f"#{i + 1}" for i in allidx], hoverinfo="text", name="toate 49")
        for i, n in zip(top, nums):
            f.add_scatter(x=[0, psi[i].real], y=[0, psi[i].imag], mode="lines",
                          line=dict(color=NEON["cyan"], width=1), showlegend=False, hoverinfo="skip")
        f.add_scatter(x=psi[top].real, y=psi[top].imag, mode="markers+text", text=[str(n) for n in nums],
                      textposition="top center", marker=dict(size=13, color=phase, colorscale="Twilight",
                                                              line=dict(color="#fff", width=1)), name="top-10")
        f.update_yaxes(scaleanchor="x", scaleratio=1)
        st.plotly_chart(f, width="stretch")
    df = pd.DataFrame({"număr": nums, "P Born": P[top], "|Ψ|": np.abs(psi[top]), "arg Ψ (rad)": phase,
                       "π_QL (după Boltzmann)": pi[top], "în top-6 la % replici": 100 * R["top6_frac"][top],
                       "nucleu ≥50%": R["core"][top], "fază Kuramoto θ": R["theta"][top], "ordine locală r": R["r_local"][top]})
    st.dataframe(df.style.format(precision=4), width="stretch", hide_index=True)
    c3, c4 = st.columns(2)
    with c3:
        f = fig(title=f"SINCRONIZARE KURAMOTO  R(t) · salturi de interferență: {int(R['spikes'].sum())}",
                xaxis_title="eșantion RK4 (×4 pași)", yaxis_title="R global")
        f.add_scatter(y=R["R_series"], mode="lines", line=dict(color=NEON["mag"], width=2), fill="tozeroy",
                      fillcolor="rgba(255,43,214,0.12)")
        st.plotly_chart(f, width="stretch")
    with c4:
        f = go.Figure(go.Barpolar(r=R["r_local"], theta=np.degrees(R["theta"]), width=[6] * 49,
                                  marker=dict(color=R["spikes"], colorscale="Plasma", line=dict(color="#000", width=0.5)),
                                  text=[f"#{i + 1}" for i in range(49)], hovertemplate="%{text}<br>r=%{r:.3f}<br>θ=%{theta:.0f}°<extra></extra>"))
        f.update_layout(**PLOT_LAYOUT, title="CERCUL DE FAZĂ (θ, ordine locală r)",
                        polar=dict(bgcolor="rgba(13,6,36,0.65)", radialaxis=dict(range=[0, 1], gridcolor="#2a2050"),
                                   angularaxis=dict(gridcolor="#2a2050")))
        st.plotly_chart(f, width="stretch")

# ---------------------------------------------------------------------------
# Tab 2 — Singularitate hiperbolică & Amplituhedron
# ---------------------------------------------------------------------------
with tabs[1]:
    x, u, amp = R["x"], R["u"], R["amp"]
    anchors = R["anchors"]
    ep = R["ep_gamma"]
    m = st.columns(4)
    m[0].markdown(card("punct excepțional γ_EP (complex)", f"{ep.real:+.4f} {ep.imag:+.4f}i", "mag"), unsafe_allow_html=True)
    m[1].markdown(card("λ_EP coalescent", f"{R['ep_lambda'].real:+.4f} {R['ep_lambda'].imag:+.4f}i"), unsafe_allow_html=True)
    m[2].markdown(card("quasi-EP real γ_q · decalaj", f"{R['gamma_q']:.3f} · {R['gap_q']:.2e}", "amber"), unsafe_allow_html=True)
    m[3].markdown(card("ancore hiperbolice", " · ".join(str(a) for a in anchors), "lime"), unsafe_allow_html=True)
    st.caption(f"Newton complex128: {R['ep_iters']} iterații, reziduu |g|={R['ep_residual']:.2e}, "
               f"convergent={R['ep_converged']}, pereche λ #{R['ep_pair'][0]}–#{R['ep_pair'][1]}. "
               "γ_q este minimul decalajului spectral pe grila reală [0, 2] (protocol QL649-P1).")
    c1, c2 = st.columns(2)
    tp = R["top_pairs"]
    with c1:
        f = fig(title="DISCUL POINCARÉ (curbură negativă) · ancore + perechi încâlcite", height=560)
        t = np.linspace(0, 2 * np.pi, 361)
        f.add_scatter(x=np.cos(t), y=np.sin(t), mode="lines", line=dict(color=NEON["violet"], width=2), hoverinfo="skip", showlegend=False)
        for r0 in (0.5, 0.8, 0.95):
            f.add_scatter(x=r0 * np.cos(t), y=r0 * np.sin(t), mode="lines", line=dict(color="#2a2050", width=1, dash="dot"),
                          hoverinfo="skip", showlegend=False)
        for (a, b), s in tp[:10]:
            f.add_scatter(x=[x[a - 1, 0], x[b - 1, 0]], y=[x[a - 1, 1], x[b - 1, 1]], mode="lines",
                          line=dict(color=NEON["mag"], width=2), opacity=0.7, hoverinfo="skip", showlegend=False)
        f.add_scatter(x=x[:, 0], y=x[:, 1], mode="markers+text", text=[str(i + 1) for i in range(49)],
                      textfont=dict(size=9, color=NEON["text"]), textposition="top center",
                      marker=dict(size=7 + 6 * u / u.max(), color=R["forman"], colorscale="Ice", colorbar=dict(title="Forman"),
                                  line=dict(color=NEON["cyan"], width=0.5)), name="noduri",
                      hovertemplate="#%{text}<br>x=%{x:.3f} y=%{y:.3f}<extra></extra>")
        ai = np.array(anchors) - 1
        f.add_scatter(x=x[ai, 0], y=x[ai, 1], mode="markers", marker=dict(size=22, symbol="star", color=NEON["lime"],
                      line=dict(color="#fff", width=1)), name="ancore")
        f.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.06, xanchor="left", x=0))
        f.update_xaxes(range=[-1.05, 1.05], showgrid=False, zeroline=False)
        f.update_yaxes(range=[-1.05, 1.05], scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False)
        st.plotly_chart(f, width="stretch")
    with c2:
        zz = amp
        f = go.Figure()
        for (a, b), s in tp[:15]:
            f.add_trace(go.Scatter3d(x=[x[a - 1, 0], x[b - 1, 0]], y=[x[a - 1, 1], x[b - 1, 1]], z=[zz[a - 1], zz[b - 1]],
                                     mode="lines", line=dict(color=NEON["mag"], width=4), hoverinfo="skip", showlegend=False))
        f.add_trace(go.Scatter3d(x=x[:, 0], y=x[:, 1], z=zz, mode="markers+text", text=[str(i + 1) for i in range(49)],
                                 marker=dict(size=4 + 4 * u / u.max(), color=zz, colorscale="Plasma", opacity=0.95),
                                 textfont=dict(size=9, color=NEON["text"]), name="noduri"))
        f.update_layout(**PLOT_LAYOUT, title="HOLOGRAMA · disc Poincaré × amplitudine Amplituhedron", height=560,
                        scene=dict(xaxis=dict(title="x", backgroundcolor="rgba(0,0,0,0)", gridcolor="#2a2050"),
                                   yaxis=dict(title="y", backgroundcolor="rgba(0,0,0,0)", gridcolor="#2a2050"),
                                   zaxis=dict(title="amp", backgroundcolor="rgba(0,0,0,0)", gridcolor="#2a2050"),
                                   camera=dict(eye=dict(x=1.5, y=1.4, z=0.9))))
        st.plotly_chart(f, width="stretch")
    c3, c4 = st.columns(2)
    with c3:
        S = R["pair_scatter"].copy()
        np.fill_diagonal(S, np.nan)
        f = fig(title=f"VOLUME DE ÎMPRĂȘTIERE S_ij (Σ volume politop pozitiv) · vol total {R['vol_total']:.1f}", height=520)
        f.add_heatmap(z=S, x=list(range(1, 50)), y=list(range(1, 50)), colorscale="Magma", colorbar=dict(title="S_ij"))
        f.update_yaxes(autorange="reversed")
        st.plotly_chart(f, width="stretch")
    with c4:
        dfp = pd.DataFrame([{"pereche încâlcită": f"{a} ⟷ {b}", "S_ij": s, "exces pereche A_ij": float(R["A"][a - 1, b - 1])}
                            for (a, b), s in tp])
        st.markdown("**Cele mai puternice perechi încâlcite (volume de împrăștiere)**")
        st.dataframe(dfp.style.format(precision=4), width="stretch", hide_index=True, height=480)
    c5, c6 = st.columns(2)
    with c5:
        g, gap = R["gamma_grid"], R["gap_grid"]
        f = fig(title="DECALAJ SPECTRAL min|λa−λb| vs γ (căutare punct excepțional)", xaxis_title="γ", yaxis_title="decalaj minim",
                yaxis_type="log")
        f.add_scatter(x=g, y=gap, mode="lines+markers", line=dict(color=NEON["cyan"]))
        f.add_vline(x=R["gamma_q"], line=dict(color=NEON["mag"], dash="dash"), annotation_text="γ_q")
        st.plotly_chart(f, width="stretch")
    with c6:
        sp = R["spectrum_grid"]
        f = fig(title="TRAIECTORII SPECTRALE λ(γ) ÎN PLANUL COMPLEX", xaxis_title="Re λ", yaxis_title="Im λ")
        gg = np.repeat(g[:, None], sp.shape[1], 1)
        f.add_scatter(x=sp.real.ravel(), y=sp.imag.ravel(), mode="markers",
                      marker=dict(size=3, color=gg.ravel(), colorscale="Viridis", colorbar=dict(title="γ")), name="λ(γ)")
        f.add_scatter(x=[R["ep_lambda"].real], y=[R["ep_lambda"].imag], mode="markers",
                      marker=dict(size=16, symbol="x", color=NEON["mag"]), name="λ_EP")
        st.plotly_chart(f, width="stretch")

# ---------------------------------------------------------------------------
# Tab 3 — Convergența terminală
# ---------------------------------------------------------------------------
def render_variants(variants, energies, cfg_label: str):
    cols = st.columns(3)
    for i, (v, e) in enumerate(zip(variants, energies)):
        crowd = int(E.crowd_penalty(torch.tensor([v])).item())
        balls = "".join(f'<span class="ql-ball">{n}</span>' for n in v)
        cols[i].markdown(f'<div class="ql-variant v{i + 1}"><div class="ql-vlabel">VARIANTA {i + 1} · ECHILIBRU {["α", "β", "γ"][i]}</div>'
                         f'{balls}<div class="ql-meta">energie E = {e:.4f} · penalizare mulțime = {crowd} · {cfg_label}</div></div>',
                         unsafe_allow_html=True)


with tabs[2]:
    st.markdown("### ♾ CONFIGURAȚIILE DE ECHILIBRU TERMODINAMIC (minime de energie MCMC · paralel tempering)")
    render_variants(R["variants"], R["energies"], "protocol QL649-P1" if R["is_protocol"] else "config NON-protocol")
    allnums = sorted({n for v in R["variants"] for n in v})
    m = st.columns(4)
    m[0].markdown(card("numere distincte acoperite", f"{len(allnums)} / 18", "lime"), unsafe_allow_html=True)
    m[1].markdown(card("nucleu determinist (≥50% replici)", " ".join(str(i + 1) for i in np.nonzero(R["core"])[0]) or "—", "mag"),
                  unsafe_allow_html=True)
    m[2].markdown(card("replici Boltzmann · pași MCMC", f"{BASE_CFG.replicas:,} · {BASE_CFG.mcmc_steps:,}".replace(",", " ")),
                  unsafe_allow_html=True)
    m[3].markdown(card("timp motor GPU", f"{R['elapsed_s']:.1f} s", "amber"), unsafe_allow_html=True)
    st.markdown('<div class="ql-warn">Variantele sunt minimele energiei '
                '<code>E(S) = −Σ log π_QL − 0.5·Σ A_ij + 0.25·mulțime(S) + 1.0·suprapunere</code> pentru extragerea următoare '
                '(după ultima zi din arhivă). <b>Exploratoriu, fără avantaj demonstrat.</b> Scutul Anti-Mulțime evită euristic '
                'tiparele populare (poate reduce împărțirea premiului, nu crește șansa). Fără promisiuni de câștig.</div>',
                unsafe_allow_html=True)
    tm = R["timings_s"]
    f = fig(title="PROFIL GPU PE OPERATOR (secunde)", xaxis_title="s", height=300)
    f.add_bar(y=list(tm.keys()), x=list(tm.values()), orientation="h", marker=dict(color=NEON["cyan"]))
    st.plotly_chart(f, width="stretch")

# ---------------------------------------------------------------------------
# Tab 4 — Multiversul Nul
# ---------------------------------------------------------------------------
with tabs[3]:
    st.markdown(f"### 🌌 ISTORIA REALĂ vs {SCI['M']:,} UNIVERSURI PARALELE UNIFORME".replace(",", " "))
    st.caption(f"Sursă: {SCI.get('origin')}. Fiecare univers are aceeași structură de zile și extrageri uniforme fără întoarcere. "
               "SCI = Σ z / 2 peste 4 statistici; p empiric unilateral.")
    c1, c2 = st.columns([1.3, 1])
    with c1:
        f = fig(title="DISTRIBUȚIA SCI ÎN MULTIVERS · linia = istoria reală", xaxis_title="SCI (σ)", yaxis_title="universuri")
        f.add_histogram(x=SCI["sci_null_sample"], nbinsx=60, marker=dict(color=NEON["violet"], line=dict(color=NEON["cyan"], width=0.5)))
        f.add_vline(x=SCI["SCI"], line=dict(color=NEON["mag"], width=3), annotation_text=f"real {SCI['SCI']:+.2f}")
        st.plotly_chart(f, width="stretch")
    with c2:
        z = SCI["z"]
        lbl = {"chi_freq": "χ² frecvențe", "chi_pair": "χ² perechi", "chi_gap": "χ² goluri", "overlap": "suprapunere serială"}
        f = fig(title="z-SCORURI PE STATISTICĂ", yaxis_title="z")
        f.add_bar(x=[lbl[k] for k in z], y=list(z.values()),
                  marker=dict(color=[NEON["mag"] if abs(v) > 2 else NEON["cyan"] for v in z.values()]))
        f.add_hrect(y0=-2, y1=2, fillcolor="rgba(182,255,0,0.07)", line_width=0)
        st.plotly_chart(f, width="stretch")
    c3, c4 = st.columns(2)
    with c3:
        fr = np.array(SCI["freq_real"])
        f = fig(title="FRECVENȚE REALE vs AȘTEPTARE UNIFORMĂ", xaxis_title="număr", yaxis_title="apariții")
        f.add_bar(x=list(range(1, 50)), y=fr, marker=dict(color=NEON["cyan"]))
        f.add_hline(y=6 * R["n_draws_used"] / 49, line=dict(color=NEON["amber"], dash="dot"), annotation_text="6N/49")
        st.plotly_chart(f, width="stretch")
    with c4:
        f = fig(title="HISTOGRAMA GOLURILOR (pași) · real vs medie multivers", xaxis_title="gol (21 = 21+)", yaxis_title="număr")
        f.add_bar(x=list(range(1, 22)), y=SCI["gap_hist_real"], name="real", marker=dict(color=NEON["mag"]))
        f.add_scatter(x=list(range(1, 22)), y=SCI["gap_hist_null_mean"], name="medie nul", mode="lines+markers",
                      line=dict(color=NEON["lime"]))
        st.plotly_chart(f, width="stretch")
    st.dataframe(pd.DataFrame({"statistică": [lbl[k] for k in z], "real": [SCI["stats_real"][k] for k in z],
                               "medie nul": [SCI["null_mean"][k] for k in z], "abatere nul": [SCI["null_std"][k] for k in z],
                               "z": list(z.values())}).style.format(precision=4), width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Tab 5 — Mașina Timpului
# ---------------------------------------------------------------------------
with tabs[4]:
    res = load_json(BT_DIR / "REZULTATE.json")
    ver = load_json(BT_DIR / "VERIFICARE_INDEPENDENTA.json")
    if not res:
        st.info("Backtestul unic preînregistrat nu a fost încă rulat (rezultate/backtest_unic). "
                "Rulare: `.venv/bin/python -B validare.py --real` (o singură dată, protocol QL649-P1).")
    else:
        t = res["total"]
        m = st.columns(5)
        m[0].markdown(card("verdict", res["verdict"].replace("_", " "), "mag" if res["gates_passed"] < 6 else "lime"), unsafe_allow_html=True)
        m[1].markdown(card("porți trecute", f"{res['gates_passed']} / 6", "amber"), unsafe_allow_html=True)
        m[2].markdown(card("ținte (extrageri)", f"{t['targets']:,}".replace(",", " ")), unsafe_allow_html=True)
        m[3].markdown(card("exces QL / U pe țintă", f"{t['excess_QL']:+.6f}"), unsafe_allow_html=True)
        m[4].markdown(card("verificare independentă", (ver or {}).get("status", "—"), "lime" if (ver or {}).get("status") == "PASS" else "mag"),
                      unsafe_allow_html=True)
        pt = res["per_target"]
        n = len(pt["hits_QL"])
        idx = np.arange(1, n + 1)
        f = fig(title="REPLAY CAUZAL: LOVITURI CUMULATE MINUS AȘTEPTAREA UNIFORMĂ (36/49 pe țintă)",
                xaxis_title="țintă (cronologic)", yaxis_title="Σ hits − 36/49·n", height=430)
        for key, name, col in (("hits_QL", "QL (varianta 1)", NEON["cyan"]), ("hits_B", "B frecvență", NEON["amber"]),
                               ("hits_R", "R recență", NEON["lime"])):
            f.add_scatter(x=idx, y=np.cumsum(pt[key]) - idx * 36 / 49, mode="lines", name=name, line=dict(color=col, width=2))
        sd = np.sqrt(idx * float(np.sum(V.hyper_pmf() * (np.arange(7) - 36 / 49) ** 2)))
        f.add_scatter(x=np.r_[idx, idx[::-1]], y=np.r_[2 * sd, -2 * sd[::-1]], fill="toself", fillcolor="rgba(143,91,255,0.12)",
                      line=dict(width=0), name="±2σ sub nul", hoverinfo="skip")
        st.plotly_chart(f, width="stretch")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Cele 6 porți preînregistrate**")
            st.dataframe(pd.DataFrame([{"poartă": g["gate"], "regulă": g["rule"], "rezultat": "PASS" if g["pass"] else "FAIL",
                                        "valoare": json.dumps(_round(g["value"]))} for g in res["gates"]]),
                         width="stretch", hide_index=True)
            tbl = pd.DataFrame([{"parte": p, "hits QL": res[p]["hits_QL"], "hits B": res[p]["hits_B"], "hits R": res[p]["hits_R"],
                                 "log QL−U": res[p]["log_QL"] - res[p]["log_U"], "log QL−B": res[p]["log_QL"] - res[p]["log_B"],
                                 "Brier QL": res[p]["brier_QL"], "Brier U": res[p]["brier_U"]} for p in ("total", "half1", "half2")])
            st.dataframe(tbl.style.format(precision=3), width="stretch", hide_index=True)
        with c2:
            f = fig(title="DISTRIBUȚIA POTRIVIRILOR (varianta 1) vs HIPERGEOMETRIC", xaxis_title="potriviri", yaxis_title="ținte",
                    yaxis_type="log")
            f.add_bar(x=list(range(7)), y=res["match_dist_QL_v1"], name="observat", marker=dict(color=NEON["cyan"]))
            f.add_scatter(x=list(range(7)), y=res["match_expected_U"], name="așteptat uniform", mode="lines+markers",
                          line=dict(color=NEON["mag"]))
            st.plotly_chart(f, width="stretch")
            ue, um = union_expected(res)
            st.caption(f"p exact (hits QL ≥ observat | extrageri uniforme) = {res['p_exact_hits_QL_ge']:.4f} · "
                       f"reuniune 3 variante: {t['hits_union3_QL']} hits vs așteptat uniform "
                       + (f"{ue:.1f} (condiționat de {um:.2f} numere distincte în medie)" if ue else "—")
                       + f" · bilete QL diferite de B: {res['tickets_changed_vs_B']}")
        nsum = load_json(NULL_DIR / "SUMAR.json")
        if nsum:
            ex = [u["excess_QL"] for u in nsum["universes"]]
            f = fig(title=f"PIPELINE COMPLET PE {nsum['M']} UNIVERSURI NULE · exces QL/U", xaxis_title="exces", yaxis_title="universuri")
            f.add_histogram(x=ex, nbinsx=20, marker=dict(color=NEON["violet"]))
            f.add_vline(x=t["excess_QL"], line=dict(color=NEON["mag"], width=3), annotation_text="istoria reală")
            st.plotly_chart(f, width="stretch")

# ---------------------------------------------------------------------------
# Tab 6 — Ablație & Sigiliu temporal
# ---------------------------------------------------------------------------
with tabs[5]:
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown("### 🧪 Panou de ablație (NON-protocol)")
        with st.form("ablation"):
            a_walk = st.checkbox("O1 walk non-hermitic", True, key="abl_walk")
            a_amp = st.checkbox("O2 Amplituhedron", True, key="abl_amp")
            a_poi = st.checkbox("O3 Poincaré", True, key="abl_poi")
            a_kur = st.checkbox("O4 Kuramoto + interferență", True, key="abl_kur")
            a_crowd = st.checkbox("Scutul Anti-Mulțime", True, key="abl_crowd")
            go_btn = st.form_submit_button("⚡ Recalculează pe GPU", key="abl_submit")
        if go_btn:
            cfg2 = replace(BASE_CFG, use_walk=a_walk, use_amplituhedron=a_amp, use_poincare=a_poi, use_kuramoto=a_kur,
                           crowd_shield=a_crowd)
            with st.spinner("Recalculare câmp…"):
                R2 = run_engine(json.dumps(asdict(cfg2), sort_keys=True))
            st.session_state["ablation_result"] = {"variants": R2["variants"], "energies": R2["energies"],
                                            "is_protocol": bool(R2["is_protocol"]), "digest": R2["config_digest"],
                                            "pi": R2["pi"].tolist()}
    with c2:
        ab = st.session_state.get("ablation_result")
        if ab:
            st.markdown(f"**Rezultat ablație** · config `{ab['digest'][:12]}…` · {'protocol' if ab['is_protocol'] else 'NON-protocol'}")
            render_variants(ab["variants"], ab["energies"], "ablație")
            base_pi, abl_pi = R["pi"], np.array(ab["pi"])
            tv = 0.5 * float(np.abs(base_pi - abl_pi).sum())
            st.caption(f"Distanța de variație totală π_QL protocol ↔ ablație: {tv:.4f}")
        else:
            st.info("Debifează operatori și apasă Recalculează pentru a vedea contribuția fiecăruia.")
    st.markdown("---")
    st.markdown("### 🔏 Sigiliul temporal (commit–reveal)")
    st.caption("Scrie local SHA-256 al variantelor protocolului cu marcaj UTC, ÎNAINTE de extragere. Verificarea se face după "
               "extragere, separat de OGLINDA; nu este evaluare prospectivă automată.")
    if st.button("🔏 Sigilează variantele curente", key="seal_btn"):
        SEAL_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"variants": [list(map(int, v)) for v in R["variants"]], "after_last_date": R["last_date"],
                   "config_digest": R["config_digest"], "is_protocol": bool(R["is_protocol"]),
                   "protocol_sha256": R.get("protocol_sha256"), "source_sha256": R["source_sha256"],
                   "sealed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "positive_claims_allowed": False}
        canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(canon).hexdigest()
        path = SEAL_DIR / f"SIGILIU_{payload['sealed_at_utc'][:19].replace(':', '').replace('-', '')}Z.json"
        path.write_text(json.dumps({"payload": payload, "sha256": digest}, indent=2) + "\n")
        st.session_state["seal"] = (str(path), digest)
    if st.session_state.get("seal"):
        p, d = st.session_state["seal"]
        st.success(f"Sigiliu scris: `{p}` · SHA-256 `{d}`")
    seals = sorted(SEAL_DIR.glob("SIGILIU_*.json")) if SEAL_DIR.exists() else []
    if seals:
        st.dataframe(pd.DataFrame([{"fișier": s.name, "sha256": (load_json(s) or {}).get("sha256", "")[:24] + "…",
                                    "variante": json.dumps((load_json(s) or {}).get("payload", {}).get("variants"))}
                                   for s in seals[-10:]]), width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Tab 7 — BO649: rupturi de regim (ipoteză distinctă, protocol BO649-P1; afișare read-only a artefactelor)
# ---------------------------------------------------------------------------
BO_DIR = ROOT / "bo649"
with tabs[6]:
    bres = load_json(BO_DIR / "rezultate" / "backtest_unic" / "REZULTATE.json")
    bver = load_json(BO_DIR / "rezultate" / "backtest_unic" / "VERIFICARE_INDEPENDENTA.json")
    bq = load_json(BO_DIR / "rezultate" / "CALIFICARE.json")
    st.markdown("### 📉 Detecție bayesiană online a rupturilor de regim (Adams & MacKay 2007)")
    st.caption("Ipoteză distinctă de QL649: ratele numerelor sunt constante pe bucăți, iar lungimea regimului curent se "
               "deduce bayesian (BOCPD Beta–Bernoulli exact, h = 1/250, m0 = 12). Protocolul BO649-P1 a fost sigilat "
               "înainte de cod. Backtestul a fost rulat o singură dată. Calculul este clasic: fp64 pe CPU, cu certificate "
               "în Q. Rezultatele sunt exploratorii, fără avantaj demonstrat; positive_claims_allowed=false.")
    if not bres:
        st.info("Backtestul unic BO649 nu a fost încă rulat (bo649/rezultate/backtest_unic).")
    else:
        bt = bres["total"]
        m = st.columns(5)
        m[0].markdown(card("verdict BO649", bres["verdict"].replace("_", " "), "mag" if bres["gates_passed"] < 6 else "lime"),
                      unsafe_allow_html=True)
        m[1].markdown(card("porți trecute", f"{bres['gates_passed']} / 6", "amber"), unsafe_allow_html=True)
        m[2].markdown(card("calificare", (bq or {}).get("status", "—").replace("_", " ")), unsafe_allow_html=True)
        m[3].markdown(card("hits BO / B / R", f"{bt['hits_BO']} / {bt['hits_B']} / {bt['hits_R']}"), unsafe_allow_html=True)
        m[4].markdown(card("verificare independentă", (bver or {}).get("status", "—"),
                           "lime" if (bver or {}).get("status") == "PASS" else "mag"), unsafe_allow_html=True)
        try:
            BP = np.load(BO_DIR / "rezultate" / "backtest_unic" / "PREDICTII.npz")
            c1, c2 = st.columns(2)
            with c1:
                f = fig(title="LUNGIMEA AȘTEPTATĂ A REGIMULUI CURENT E[r] (pași-zi)", xaxis_title="pas", yaxis_title="E[r]",
                        height=380)
                f.add_scatter(x=BP["ks"], y=BP["Er"], mode="lines", name="E[r]", line=dict(color=NEON["cyan"], width=2))
                f.add_scatter(x=BP["ks"], y=BP["ks"], mode="lines", name="fără nicio ruptură (r = k)",
                              line=dict(color=NEON["dim"], dash="dot"))
                st.plotly_chart(f, width="stretch")
            with c2:
                pl = BP["post_last"]
                f = fig(title="POSTERIORUL PE LUNGIMEA REGIMULUI LA ULTIMUL PAS", xaxis_title="r (pași-zi)",
                        yaxis_title="P(r)", height=380)
                f.add_scatter(x=np.arange(pl.shape[0]), y=pl, mode="lines", fill="tozeroy", name="P(r)",
                              line=dict(color=NEON["mag"], width=2))
                st.plotly_chart(f, width="stretch")
        except Exception as exc:  # afișare robustă
            st.caption(f"Predicțiile BO649 nu pot fi afișate: {exc}")
        st.dataframe(pd.DataFrame([{"poartă": g["gate"], "regulă": g["rule"], "rezultat": "PASS" if g["pass"] else "FAIL",
                                    "valoare": json.dumps(_round(g["value"]))} for g in bres["gates"]]),
                     width="stretch", hide_index=True)
        bn = load_json(BO_DIR / "rezultate" / "nule" / "SUMAR.json")
        if bn:
            f = fig(title=f"BO649 PE {bn['M']} UNIVERSURI NULE · logBO − logB", xaxis_title="logBO − logB",
                    yaxis_title="universuri", height=340)
            f.add_histogram(x=[u["logBO_minus_B"] for u in bn["universes"]], nbinsx=20, marker=dict(color=NEON["violet"]))
            f.add_vline(x=bt["log_BO"] - bt["log_B"], line=dict(color=NEON["mag"], width=3), annotation_text="istoria reală")
            st.plotly_chart(f, width="stretch")
        st.caption(f"p exact (hits BO ≥ observat | extrageri uniforme) = {bres['p_exact_hits_BO_ge']:.4f} · "
                   "raport complet: bo649/RAPORT_BO649.md")

# ---------------------------------------------------------------------------
# Tab 8 — WU649: urna ponderată (protocol WU649-P1; afișare read-only a calificării)
# ---------------------------------------------------------------------------
WU_DIR = ROOT / "wu649"
with tabs[7]:
    wq = load_json(WU_DIR / "rezultate" / "CALIFICARE.json")
    wv = load_json(WU_DIR / "rezultate" / "VERIFICARE_NECALIFICARE.json")
    st.markdown("### 🎱 Urna ponderată — cursa exponențială Luce cu ordinea nevăzută marginalizată")
    st.caption("Ipoteză distinctă de QL649 și BO649: fiecare bilă are o propensiune constantă w_j, iar extragerea este "
               "mulțimea primelor 6 sosiri dintr-o cursă de ceasuri exponențiale (Luce/Plackett/Wallenius; Yellott 1977). "
               "Protocolul WU649-P1 a fost sigilat înainte de cod. Calculul este clasic: fp64 pe CPU, cu certificate în Q. "
               "positive_claims_allowed=false.")
    if not wq:
        st.info("Calificarea WU649 nu a fost încă rulată (wu649/rezultate/CALIFICARE.json).")
    else:
        m = st.columns(4)
        m[0].markdown(card("calificare WU649", wq["status"].replace("_", " "),
                           "lime" if wq["status"] == "WU_QUALIFIED" else "mag"), unsafe_allow_html=True)
        m[1].markdown(card("verificări trecute", f"{wq['passed']} / 6", "amber"), unsafe_allow_html=True)
        m[2].markdown(card("backtest pe arhivă", "NERULAT" if wq["status"] != "WU_QUALIFIED" else "—"),
                      unsafe_allow_html=True)
        m[3].markdown(card("verificare necalificare", (wv or {}).get("status", "—"),
                           "lime" if (wv or {}).get("status") == "PASS" else "mag"), unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{"verificare": c["id"], "nume": c["name"], "rezultat": "PASS" if c["pass"] else "FAIL",
                                    "detalii": json.dumps(_round(c["detail"]), ensure_ascii=False)[:220]}
                                   for c in wq["checks"]]), width="stretch", hide_index=True)
        d5 = wq["checks"][4]["detail"]
        f = fig(title="MARTORUL Q5/Q6 · q_WU PENTRU BILELE 6 (COLEGI GREI) ȘI 7 (COLEGI UȘORI), ACELEAȘI NUMĂRĂRI",
                xaxis_title="bilă", yaxis_title="q_WU", height=320)
        f.add_bar(x=["6", "7"], y=d5["q6_q7_Hplus"], marker=dict(color=[NEON["cyan"], NEON["mag"]]))
        st.plotly_chart(f, width="stretch")
        st.caption("Q6 a eșuat: biletul WU coincide cu B și R, deci istoria reală nu a fost atinsă, iar codul rămâne "
                   "condiționat NEVALIDAT · raport complet: wu649/RAPORT_WU649.md")

# ---------------------------------------------------------------------------
# Tab 9 — GL649: masa glifelor (protocol GL649-P1; afișare read-only a artefactelor)
# ---------------------------------------------------------------------------
GL_DIR = ROOT / "gl649"
with tabs[8]:
    gq = load_json(GL_DIR / "rezultate" / "CALIFICARE.json")
    gr = load_json(GL_DIR / "rezultate" / "backtest_unic" / "REZULTATE.json")
    gv = load_json(GL_DIR / "rezultate" / "backtest_unic" / "VERIFICARE_INDEPENDENTA.json")
    st.markdown("### 🔢 Masa glifelor — Bayes liniar exact pe structura cifrelor tipărite")
    st.caption("Ipoteză distinctă de QL649, BO649 și WU649: propensiunea unei bile = p0 + suma contribuțiilor glifelor "
               "zecimale tipărite pe ea + un rest propriu (premisă fizică neverificată). Predictorul este așteptarea "
               "ajustată Bayes liniară (Goldstein–Wooff), calculată EXACT în Q. Protocolul GL649-P1 a fost sigilat "
               "înainte de cod; martorii Q5/Q6 sunt derivați analitic. Calcul clasic. positive_claims_allowed=false.")
    if not gq:
        st.info("Calificarea GL649 nu a fost încă rulată (gl649/rezultate/CALIFICARE.json).")
    else:
        m = st.columns(4)
        m[0].markdown(card("calificare GL649", f"{gq['status'].replace('_', ' ')} {gq['passed']}/6",
                           "lime" if gq["status"] == "GL_QUALIFIED" else "mag"), unsafe_allow_html=True)
        m[1].markdown(card("backtest unic", (gr or {}).get("verdict", "NERULAT").replace("_", " "), "amber"),
                      unsafe_allow_html=True)
        m[2].markdown(card("porți trecute", f"{(gr or {}).get('gates_passed', '—')} / 6", "mag"), unsafe_allow_html=True)
        m[3].markdown(card("verificare independentă", (gv or {}).get("status", "—"),
                           "lime" if (gv or {}).get("status") == "PASS" else "mag"), unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{"verificare": c["id"], "nume": c["name"], "rezultat": "PASS" if c["pass"] else "FAIL",
                                    "detalii": json.dumps(_round(c["detail"]), ensure_ascii=False)[:220]}
                                   for c in gq["checks"]]), width="stretch", hide_index=True)
        if gr:
            t = gr["total"]
            st.dataframe(pd.DataFrame([{"poartă": g["gate"], "cerință": g["rule"], "rezultat": "PASS" if g["pass"] else "FAIL",
                                        "valoare": json.dumps(_round(g["value"]), ensure_ascii=False)}
                                       for g in gr["gates"]]), width="stretch", hide_index=True)
            f = fig(title="BACKTEST UNIC · HITS PE 2495 DE ȚINTE (U AȘTEPTAT ≈ 1833)", xaxis_title="model",
                    yaxis_title="hits", height=320)
            f.add_bar(x=["GL", "B", "R"], y=[t["hits_GL"], t["hits_B"], t["hits_R"]],
                      marker=dict(color=[NEON["cyan"], NEON["mag"], NEON["amber"]]))
            st.plotly_chart(f, width="stretch")
            gl = gr.get("gamma_last_relative") or []
            if gl:
                f2 = fig(title="EFECTE DE GLIFĂ AJUSTATE LA ULTIMUL PAS (RELATIV LA p0, DESCRIPTIV)",
                         xaxis_title="cifră", yaxis_title="γ̂ / p0", height=300)
                f2.add_bar(x=[str(d) for d in range(10)], y=gl, marker=dict(color=NEON["cyan"]))
                st.plotly_chart(f2, width="stretch")
        st.caption("Rezultatul este exploratoriu pe o arhivă deja explorată; nu demonstrează avantaj · raport complet: "
                   "gl649/RAPORT_GL649.md")

# ---------------------------------------------------------------------------
# Tab 10 — SE649: anotimpurile bilelor (protocol SE649-P1; afișare read-only a artefactelor)
# ---------------------------------------------------------------------------
SE_DIR = ROOT / "se649"
with tabs[9]:
    sq = load_json(SE_DIR / "rezultate" / "CALIFICARE.json")
    sr = load_json(SE_DIR / "rezultate" / "backtest_unic" / "REZULTATE.json")
    sv = load_json(SE_DIR / "rezultate" / "backtest_unic" / "VERIFICARE_INDEPENDENTA.json")
    st.markdown("### 🍂 Anotimpurile bilelor — Bayes liniar ierarhic exact, etichetă × anotimp")
    st.caption("Ipoteză distinctă de QL649, BO649, WU649 și GL649: propensiunea unei bile = p0 + efect principal + "
               "interacțiune cu anotimpul meteorologic al datei extragerii (premisă fizică neverificată). Predictorul "
               "este așteptarea ajustată Bayes liniară, cu ponderi în formă închisă, calculată EXACT în Q. Protocolul "
               "SE649-P1 a fost sigilat înainte de cod; martorii Q5/Q6 sunt derivați analitic. Calcul clasic. "
               "positive_claims_allowed=false.")
    if not sq:
        st.info("Calificarea SE649 nu a fost încă rulată (se649/rezultate/CALIFICARE.json).")
    else:
        m = st.columns(4)
        m[0].markdown(card("calificare SE649", f"{sq['status'].replace('_', ' ')} {sq['passed']}/6",
                           "lime" if sq["status"] == "SE_QUALIFIED" else "mag"), unsafe_allow_html=True)
        m[1].markdown(card("backtest unic", (sr or {}).get("verdict", "NERULAT").replace("_", " "), "amber"),
                      unsafe_allow_html=True)
        m[2].markdown(card("porți trecute", f"{(sr or {}).get('gates_passed', '—')} / 6", "mag"), unsafe_allow_html=True)
        m[3].markdown(card("verificare independentă", (sv or {}).get("status", "—"),
                           "lime" if (sv or {}).get("status") == "PASS" else "mag"), unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{"verificare": c["id"], "nume": c["name"], "rezultat": "PASS" if c["pass"] else "FAIL",
                                    "detalii": json.dumps(_round(c["detail"]), ensure_ascii=False)[:220]}
                                   for c in sq["checks"]]), width="stretch", hide_index=True)
        if sr:
            t = sr["total"]
            st.dataframe(pd.DataFrame([{"poartă": g["gate"], "cerință": g["rule"], "rezultat": "PASS" if g["pass"] else "FAIL",
                                        "valoare": json.dumps(_round(g["value"]), ensure_ascii=False)}
                                       for g in sr["gates"]]), width="stretch", hide_index=True)
            f = fig(title="BACKTEST UNIC · HITS PE 2495 DE ȚINTE (U AȘTEPTAT ≈ 1833)", xaxis_title="model",
                    yaxis_title="hits", height=320)
            f.add_bar(x=["SE", "B", "R"], y=[t["hits_SE"], t["hits_B"], t["hits_R"]],
                      marker=dict(color=[NEON["cyan"], NEON["mag"], NEON["amber"]]))
            st.plotly_chart(f, width="stretch")
            bs = sr.get("by_target_season") or {}
            if bs:
                f2 = fig(title="HITS SE − HITS B PE ANOTIMPUL ȚINTEI (DESCRIPTIV)", xaxis_title="anotimp",
                         yaxis_title="hitsSE − hitsB", height=300)
                f2.add_bar(x=list(bs), y=[v["hits_SE"] - v["hits_B"] for v in bs.values()], marker=dict(color=NEON["cyan"]))
                st.plotly_chart(f2, width="stretch")
        st.caption("Rezultatul este exploratoriu pe o arhivă deja explorată; nu demonstrează avantaj · raport complet: "
                   "se649/RAPORT_SE649.md")

# ---------------------------------------------------------------------------
# Tab 11 — CS649: caruselul seturilor (protocol CS649-P1; afișare read-only a artefactelor)
# ---------------------------------------------------------------------------
CS_DIR = ROOT / "cs649"
with tabs[10]:
    cq = load_json(CS_DIR / "rezultate" / "CALIFICARE.json")
    cr = load_json(CS_DIR / "rezultate" / "backtest_unic" / "REZULTATE.json")
    cv = load_json(CS_DIR / "rezultate" / "backtest_unic" / "VERIFICARE_INDEPENDENTA.json")
    st.markdown("### 🎠 Caruselul seturilor — rotație deterministă ipotetică a seturilor de bile/urnelor")
    st.caption("Ipoteză distinctă de QL649, BO649, WU649, GL649 și SE649: propensiunea unei bile = p0 + efect principal + "
               "efecte ale fazei indicelui zilei de extragere modulo 3, 5 și 7 (rotație operațională ipotetică a "
               "seturilor, premisă neverificată; perioadele pare excluse a priori). Predictorul este așteptarea ajustată "
               "Bayes liniară prin ecuațiile Henderson 16×16, calculată EXACT în Q. Protocolul CS649-P1 a fost sigilat "
               "înainte de cod; martorii Q5/Q6 sunt derivați analitic. Calcul clasic. positive_claims_allowed=false.")
    if not cq:
        st.info("Calificarea CS649 nu a fost încă rulată (cs649/rezultate/CALIFICARE.json).")
    else:
        m = st.columns(4)
        m[0].markdown(card("calificare CS649", f"{cq['status'].replace('_', ' ')} {cq['passed']}/6",
                           "lime" if cq["status"] == "CS_QUALIFIED" else "mag"), unsafe_allow_html=True)
        m[1].markdown(card("backtest unic", (cr or {}).get("verdict", "NERULAT").replace("_", " "), "amber"),
                      unsafe_allow_html=True)
        m[2].markdown(card("porți trecute", f"{(cr or {}).get('gates_passed', '—')} / 6", "mag"), unsafe_allow_html=True)
        m[3].markdown(card("verificare independentă", (cv or {}).get("status", "—"),
                           "lime" if (cv or {}).get("status") == "PASS" else "mag"), unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{"verificare": c["id"], "nume": c["name"], "rezultat": "PASS" if c["pass"] else "FAIL",
                                    "detalii": json.dumps(_round(c["detail"]), ensure_ascii=False)[:220]}
                                   for c in cq["checks"]]), width="stretch", hide_index=True)
        if cr:
            t = cr["total"]
            st.dataframe(pd.DataFrame([{"poartă": g["gate"], "cerință": g["rule"], "rezultat": "PASS" if g["pass"] else "FAIL",
                                        "valoare": json.dumps(_round(g["value"]), ensure_ascii=False)}
                                       for g in cr["gates"]]), width="stretch", hide_index=True)
            f = fig(title="BACKTEST UNIC · HITS PE 2495 DE ȚINTE (U AȘTEPTAT ≈ 1833)", xaxis_title="model",
                    yaxis_title="hits", height=320)
            f.add_bar(x=["CS", "B", "R"], y=[t["hits_CS"], t["hits_B"], t["hits_R"]],
                      marker=dict(color=[NEON["cyan"], NEON["mag"], NEON["amber"]]))
            st.plotly_chart(f, width="stretch")
            bp = cr.get("by_target_phase") or {}
            if bp:
                xs, ys = [], []
                for K, d in bp.items():
                    for r, v in d.items():
                        xs.append(f"{K}·r{r}")
                        ys.append(v["hits_CS"] - v["hits_B"])
                f2 = fig(title="HITS CS − HITS B PE FAZA-ȚINTĂ (DESCRIPTIV)", xaxis_title="perioadă · fază",
                         yaxis_title="hitsCS − hitsB", height=300)
                f2.add_bar(x=xs, y=ys, marker=dict(color=NEON["cyan"]))
                st.plotly_chart(f2, width="stretch")
        st.caption("Rezultatul este exploratoriu pe o arhivă deja explorată; nu demonstrează avantaj · raport complet: "
                   "cs649/RAPORT_CS649.md")

# ---------------------------------------------------------------------------
# Tab 12 — PL649: Orizontul evenimentelor (protocol PL649-P1; motorul v2.0 în pl649/pl_core.py)
# ---------------------------------------------------------------------------
with tabs[11]:
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "pl649"))
    import ui_pl649  # noqa: E402
    ui_pl649.render(st, card, fig, NEON, PLOT_LAYOUT, _round)

st.markdown(f'<p class="ql-sub" style="text-align:center;margin-top:30px">QL649 · protocol QL649-P1 · torch {torch.__version__} · '
            f'sursă {R["source_sha256"][:12]}… · calcul clasic · positive_claims_allowed=false</p>', unsafe_allow_html=True)
