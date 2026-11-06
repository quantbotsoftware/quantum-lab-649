"""TU3 v3.0 — modulul UI: selector global de univers (🌌 6/49 · 🌀 5/40 · 🃏 Joker) și cele 12 taburi ale modurilor
5/40 și Joker. Protocol: PROTOCOL_TU3_UI.md (sigilat în SIGILIU_TU3_UI.json ÎNAINTE de acest cod).

Calea 6/49 NU trece prin acest modul (în afara selectorului și a eliberării la schimbarea modului): `app.py` o execută
neschimbată. Produse: `motor_n.run_full_540` (5/40) și `motor_joker.run_full_joker` (Joker), pe arhiva LIVE rezolvată
prin `parser_multi` (lanț pointer → manifest → JSONL). `engine.py`, `parser.py`, `parser_multi.py`, `motor_n.py`,
`motor_joker.py` NEMODIFICATE. Calcul CLASIC pe GPU; variantele sunt minime de energie, NU predicții.
`positive_claims_allowed=false`.
"""
from __future__ import annotations

import datetime as dt
import gc
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
for _p in (str(QL), str(HERE)):
    if _p not in sys.path:
        sys.path.append(_p)

MODES = {"649": "🌌 Mode: Loto 6/49", "540": "🌀 Mode: Loto 5/40", "joker": "🃏 Mode: Joker"}
FAST_OVERRIDES = dict(mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60, gamma_grid=12)
INFO = {
    "540": dict(title="🌀 QUANTUM LAB 540", game="LOTO 5/40 RO", name="Loto 5/40", n=40, r=6, k=5, m=None,
                rule="5 numere distincte din 1..40", power="E40"),
    "joker": dict(title="🃏 QUANTUM LAB JOKER", game="JOKER RO", name="Joker", n=45, r=5, k=5, m=20,
                  rule="5 numere distincte din 1..45 + 1 Joker din 1..20", power="EJ"),
}
TAB_LABELS = ["⚛ Colapsul funcției de undă", "🌀 Singularitate hiperbolică & Amplituhedron",
              "♾ Convergența terminală — Limita Cuantică", "🌌 Multiversul Nul", "⏳ Mașina Timpului",
              "🧪 Ablație & Sigiliu temporal", "📉 Rupturi de regim (BO649)", "🎱 Urna ponderată (WU649)",
              "🔢 Masa glifelor (GL649)", "🍂 Anotimpurile bilelor (SE649)", "🎠 Caruselul seturilor (CS649)",
              "🌌 Orizontul evenimentelor (PL649)"]
CLOSED_649 = [("BO649", "BO649-P1", "bo649/RAPORT_BO649.md"), ("WU649", "WU649-P1", "wu649/RAPORT_WU649.md"),
              ("GL649", "GL649-P1", "gl649/RAPORT_GL649.md"), ("SE649", "SE649-P1", "se649/RAPORT_SE649.md"),
              ("CS649", "CS649-P1", "cs649/RAPORT_CS649.md"), ("PL649", "PL649-P1", "pl649/RAPORT_PL649.md")]

EXTRA_CSS = """
<style>
.ql-ball.jk { background:radial-gradient(circle at 30% 28%, #ffffff 0%, #ffb000 40%, #6b4a00 100%) !important;
  box-shadow:0 0 18px rgba(255,176,0,0.8) !important; border:2px dashed #fff; }
.ql-plus { display:inline-block; font-size:1.6rem; font-weight:800; color:#ffb000; margin:0 4px;
  text-shadow:0 0 10px rgba(255,176,0,0.7); vertical-align:middle; }
</style>
"""


# ---------------------------------------------------------------------------
# Selector și ciclul de viață al tensorilor (§2)
# ---------------------------------------------------------------------------
def sidebar_selector() -> str:
    with st.sidebar:
        st.markdown("### 🛰 UNIVERS ACTIV")
        mode = st.selectbox("Mod de joc", list(MODES), format_func=MODES.get, key="tu3_mode")
        st.caption("TU3 v3.0 · calcul clasic pe GPU · variantele sunt minime de energie, NU predicții · "
                   "positive_claims_allowed=false")
    return mode


def _vram() -> int:
    return int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else 0


def release_mode(old: str, new: str, get_dataset_649) -> dict:
    """Golește cache-ul de set al modului părăsit, apoi gc + torch.cuda.empty_cache(); jurnalizează evenimentul."""
    before = _vram()
    if old == "649":
        get_dataset_649.clear()
        l649_live_dataset.clear()  # TU3-L649 (inserție): schimbarea modului eliberează și setul LIVE 6/49
    else:
        get_game_dataset.clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    ev = {"from": old, "to": new, "vram_before": before, "vram_after": _vram(),
          "utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    st.session_state.setdefault("tu3_release_log", []).append(ev)
    return ev


def base_cfg(mode: str, fast: bool):
    import motor_joker as MJ
    import motor_n as M
    c = M.PROTOCOL_540 if mode == "540" else MJ.PROTOCOL_JOKER
    return replace(c, **FAST_OVERRIDES) if fast else c


def live_key(mode: str) -> str:
    """sha256 al JSONL-ului LIVE rezolvat (lanțul pointer → manifest → JSONL verificat de parser_multi)."""
    import parser_multi as PM
    path, _ = PM.resolve_live(mode)
    return PM.sha256_file(path)


@st.cache_resource(show_spinner=False, max_entries=1)
def get_game_dataset(mode: str, src_key: str):
    import parser_multi as PM
    return PM.build_game_dataset(mode, "live")


def _to_np(v):
    if torch.is_tensor(v):
        return v.detach().cpu().numpy()
    if isinstance(v, dict):
        return {k: _to_np(x) for k, x in v.items()}
    return v


@st.cache_resource(show_spinner=False, max_entries=8)
def run_engine_mode(mode: str, cfg_json: str, src_key: str) -> dict:
    """Produsul modului (5/40: run_full_540; Joker: run_full_joker); rezultatul în NumPy pe CPU."""
    import motor_joker as MJ
    import motor_n as M
    from engine import Config
    cfg = Config(**json.loads(cfg_json))
    ds = get_game_dataset(mode, src_key)
    out = M.run_full_540(ds, cfg) if mode == "540" else MJ.run_full_joker(ds, cfg)
    res = {k: _to_np(v) for k, v in out.items()}
    del out
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return res


# ---------------------------------------------------------------------------
# Variante și sigiliu (§4.3)
# ---------------------------------------------------------------------------
def variants_of(mode: str, R: dict) -> list:
    if mode == "540":
        return [[int(x) for x in v] for v in R["variants"]]
    return [[[int(x) for x in v], int(a)] for v, a in R["variants_5plus1"]]


def check_variants(mode: str, variants: list) -> bool:
    info = INFO[mode]
    if len(variants) != 3:
        return False
    keys = []
    for v in variants:
        main, j = (v, None) if mode == "540" else (v[0], v[1])
        if len(main) != info["k"] or len(set(main)) != info["k"] or not all(1 <= x <= info["n"] for x in main):
            return False
        if mode == "joker" and not (1 <= j <= info["m"]):
            return False
        keys.append((tuple(sorted(main)), j))
    return len(set(keys)) == 3


def seal_payload(mode: str, R: dict) -> dict:
    return {"game": mode, "variants": variants_of(mode, R), "after_last_date": R["last_date"],
            "config_digest": R["config_digest"], "is_protocol": bool(R["is_protocol"]),
            "protocol_sha256": R.get("protocol_sha256"), "source_sha256": R["source_sha256"],
            "source_kind": R.get("source_kind"), "sealed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "positive_claims_allowed": False}


def canonical_sha256(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_seal(seal_dir: Path, mode: str, payload: dict) -> tuple[Path, str]:
    seal_dir.mkdir(parents=True, exist_ok=True)
    digest = canonical_sha256(payload)
    ts = payload["sealed_at_utc"][:26].replace(":", "").replace("-", "").replace(".", "")
    path = seal_dir / f"SIGILIU_{mode}_{ts}Z.json"
    path.write_text(json.dumps({"payload": payload, "sha256": digest}, indent=2, ensure_ascii=False) + "\n")
    return path, digest


def render_variants(mode: str, R: dict, label: str, crowd_penalty) -> bool:
    vs = variants_of(mode, R)
    if not check_variants(mode, vs):
        st.error(f"Regula activă ({INFO[mode]['rule']}) sau unicitatea celor 3 variante nu se verifică; nicio carte afișată.")
        return False
    cols = st.columns(3)
    for i, v in enumerate(vs):
        main = v if mode == "540" else v[0]
        crowd = int(crowd_penalty(torch.tensor([main])).item())
        balls = "".join(f'<span class="ql-ball">{x}</span>' for x in main)
        if mode == "540":
            meta = f"energie E = {R['energies'][i]:.4f} · penalizare mulțime = {crowd} · {label}"
        else:
            a = v[1]
            balls += f'<span class="ql-plus">+</span><span class="ql-ball jk">{a}</span>'
            q = float(np.asarray(R["q_joker"])[i, a - 1])
            hv = abs(complex(R["h_variant"][i]))
            meta = (f"E principal = {R['energies_main'][i]:.4f} · E_J = {R['energies_joker'][i]:.4f} · "
                    f"E total = {R['energies_total'][i]:.4f}<br>q_V(Joker) = {q:.4f} · |h_V| = {hv:.4f} · "
                    f"penalizare mulțime = {crowd} · {label}")
        cols[i].markdown(f'<div class="ql-variant v{i + 1}"><div class="ql-vlabel">VARIANTA {i + 1} · ECHILIBRU '
                         f'{["α", "β", "γ"][i]}</div>{balls}<div class="ql-meta">{meta}</div></div>',
                         unsafe_allow_html=True)
    return True


# ---------------------------------------------------------------------------
# Pagina modului 5/40 / Joker (§4)
# ---------------------------------------------------------------------------
def render(mode: str, ctx: dict) -> None:
    import motor_joker as MJ
    import motor_n as M
    from engine import crowd_penalty
    from parser import device_events
    card, fig, NEON, PL = ctx["card"], ctx["fig"], ctx["NEON"], ctx["PLOT_LAYOUT"]
    load_json, round_ = ctx["load_json"], ctx["round_"]
    fast = bool(ctx["FAST_MODE"])
    info = INFO[mode]
    n = info["n"]
    seal_dir = Path(ctx["SEAL_DIR"]) / mode
    st.markdown(EXTRA_CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="ql-title">{info["title"]}</div>'
                f'<p class="ql-sub">NON-HERMITIAN · AMPLITUHEDRON · POINCARÉ · KURAMOTO · BORN–BOLTZMANN · MCMC — '
                f'{info["game"]}</p>', unsafe_allow_html=True)
    try:
        key = live_key(mode)
    except Exception as exc:  # lanț de integritate rupt ⇒ refuz complet
        st.error(f"Arhiva LIVE {info['name']} nu trece lanțul de integritate (pointer → manifest → JSONL): {exc}. "
                 "Nicio dată încărcată.")
        return
    cfg = base_cfg(mode, fast)
    with st.spinner(f"Inițializare câmp {info['name']} pe GPU… (prima rulare durează)"):
        try:
            ds = get_game_dataset(mode, key)
            R = run_engine_mode(mode, json.dumps(asdict(cfg), sort_keys=True), key)
        except Exception as exc:
            st.error(f"Produsul {info['name']} a refuzat rularea: {exc}")
            return

    h = st.columns([1.1, 1, 1, 1.2, 1.3])
    h[0].markdown(card("extrageri analizate", f"{R['n_draws_used']:,}".replace(",", " ")), unsafe_allow_html=True)
    h[1].markdown(card("pași (zile)", f"{R['n_steps']:,}".replace(",", " "), "mag"), unsafe_allow_html=True)
    h[2].markdown(card("ultima extragere", f"{R['last_date']}", "amber"), unsafe_allow_html=True)
    if mode == "540":
        h[3].markdown(card("telemetrie · sincronizare Kuramoto R", f"{R['R_global']:.3f}", "lime"), unsafe_allow_html=True)
    else:
        h[3].markdown(card("telemetrie · I(principal; Joker)", f"{R['J']['I']:.4f} nats", "lime"), unsafe_allow_html=True)

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
        f'<div class="ql-warn">⚠ Calcul <b>clasic</b> pe {R["device"].upper()} (PyTorch). Inspirația cuantică este strict '
        f'matematică — fără hardware cuantic, fără avantaj cuantic. Dacă extragerile sunt uniforme și independente, niciun '
        f'operator nu poate prezice extragerea următoare. Variantele sunt <b>minimele energiei modelului</b>, nu combinații '
        f'cu șanse mai mari. <code>positive_claims_allowed=false</code> · protocol '
        f'<code>{(R.get("protocol_sha256") or "")[:12]}…</code> · config <code>{R["config_digest"][:12]}…</code> · '
        f'sursă LIVE <code>{R["source_sha256"][:12]}…</code>{" · <b>MOD FAST (test)</b>" if fast else ""}</div>',
        unsafe_allow_html=True)
    if device_events():
        st.caption("Evenimente dispozitiv: " + " | ".join(device_events()))

    tabs = st.tabs(TAB_LABELS)
    P, psi, pi = np.asarray(R["P"]), np.asarray(R["psi_f"]), np.asarray(R["pi"])

    # Tab 1 — Colaps
    with tabs[0]:
        top = np.argsort(-P, kind="stable")[:10]
        nums = top + 1
        phase = np.angle(psi[top])
        c1, c2 = st.columns([1.15, 1])
        with c1:
            f = fig(title="TOP-10 AMPLITUDINI POST-COLAPS  P = |Ψ|²", xaxis_title="număr", yaxis_title="P (Born)")
            f.add_bar(x=[f"#{x}" for x in nums], y=P[top],
                      marker=dict(color=phase, colorscale="Twilight", cmin=-math.pi, cmax=math.pi,
                                  colorbar=dict(title="arg Ψ"), line=dict(color=NEON["cyan"], width=1)),
                      hovertemplate="număr %{x}<br>P=%{y:.4f}<extra></extra>")
            f.update_xaxes(type="category", categoryorder="array", categoryarray=[f"#{x}" for x in nums])
            f.add_hline(y=1 / n, line=dict(color=NEON["amber"], dash="dot"), annotation_text=f"uniform 1/{n}")
            st.plotly_chart(f, width="stretch")
        with c2:
            f = fig(title="COORDONATE DE FAZĂ ÎN PLANUL COMPLEX", xaxis_title="Re Ψ", yaxis_title="Im Ψ")
            f.add_scatter(x=psi.real, y=psi.imag, mode="markers", marker=dict(size=6, color=NEON["dim"], opacity=0.5),
                          text=[f"#{i + 1}" for i in range(n)], hoverinfo="text", name=f"toate {n}")
            for i in top:
                f.add_scatter(x=[0, psi[i].real], y=[0, psi[i].imag], mode="lines",
                              line=dict(color=NEON["cyan"], width=1), showlegend=False, hoverinfo="skip")
            f.add_scatter(x=psi[top].real, y=psi[top].imag, mode="markers+text", text=[str(x) for x in nums],
                          textposition="top center", marker=dict(size=13, color=phase, colorscale="Twilight",
                                                                  line=dict(color="#fff", width=1)), name="top-10")
            f.update_yaxes(scaleanchor="x", scaleratio=1)
            st.plotly_chart(f, width="stretch")
        df = pd.DataFrame({"număr": nums, "P Born": P[top], "|Ψ|": np.abs(psi[top]), "arg Ψ (rad)": phase,
                           "π (după Boltzmann)": pi[top], f"în top-{info['k']} la % replici": 100 * np.asarray(R["topk_frac"])[top],
                           "nucleu ≥50%": np.asarray(R["core"])[top], "fază Kuramoto θ": np.asarray(R["theta"])[top],
                           "ordine locală r": np.asarray(R["r_local"])[top]})
        st.dataframe(df.style.format(precision=4), width="stretch", hide_index=True)
        c3, c4 = st.columns(2)
        with c3:
            f = fig(title=f"SINCRONIZARE KURAMOTO  R(t) · salturi de interferență: {int(np.asarray(R['spikes']).sum())}",
                    xaxis_title="eșantion RK4 (×4 pași)", yaxis_title="R global")
            f.add_scatter(y=np.asarray(R["R_series"]), mode="lines", line=dict(color=NEON["mag"], width=2),
                          fill="tozeroy", fillcolor="rgba(255,43,214,0.12)")
            st.plotly_chart(f, width="stretch")
        with c4:
            f = go.Figure(go.Barpolar(r=np.asarray(R["r_local"]), theta=np.degrees(np.asarray(R["theta"])), width=[6] * n,
                                      marker=dict(color=np.asarray(R["spikes"]), colorscale="Plasma",
                                                  line=dict(color="#000", width=0.5)),
                                      text=[f"#{i + 1}" for i in range(n)],
                                      hovertemplate="%{text}<br>r=%{r:.3f}<br>θ=%{theta:.0f}°<extra></extra>"))
            f.update_layout(**PL, title="CERCUL DE FAZĂ (θ, ordine locală r)",
                            polar=dict(bgcolor="rgba(13,6,36,0.65)", radialaxis=dict(range=[0, 1], gridcolor="#2a2050"),
                                       angularaxis=dict(gridcolor="#2a2050")))
            st.plotly_chart(f, width="stretch")

    # Tab 2 — Singularitate hiperbolică & Amplituhedron (+ tensorul comun J la Joker)
    with tabs[1]:
        x, u, amp = np.asarray(R["x"]), np.asarray(R["u"]), np.asarray(R["amp"])
        anchors = list(R["anchors"])
        ep = R["ep_gamma"]
        m = st.columns(4)
        m[0].markdown(card("punct excepțional γ_EP (complex)", f"{ep.real:+.4f} {ep.imag:+.4f}i", "mag"), unsafe_allow_html=True)
        m[1].markdown(card("λ_EP coalescent", f"{R['ep_lambda'].real:+.4f} {R['ep_lambda'].imag:+.4f}i"), unsafe_allow_html=True)
        m[2].markdown(card("quasi-EP real γ_q · decalaj", f"{R['gamma_q']:.3f} · {R['gap_q']:.2e}", "amber"), unsafe_allow_html=True)
        m[3].markdown(card("ancore hiperbolice", " · ".join(str(a) for a in anchors), "lime"), unsafe_allow_html=True)
        st.caption(f"Newton complex128: {R['ep_iters']} iterații, reziduu |g|={R['ep_residual']:.2e}, "
                   f"convergent={R['ep_converged']}, pereche λ #{R['ep_pair'][0]}–#{R['ep_pair'][1]}. "
                   f"Topologie {n}×{n} (motor polimorf TU3-E40{'/EJ' if mode == 'joker' else ''}).")
        tp = R["top_pairs"]
        c1, c2 = st.columns(2)
        with c1:
            f = fig(title="DISCUL POINCARÉ (curbură negativă) · ancore + perechi încâlcite", height=560)
            t = np.linspace(0, 2 * np.pi, 361)
            f.add_scatter(x=np.cos(t), y=np.sin(t), mode="lines", line=dict(color=NEON["violet"], width=2),
                          hoverinfo="skip", showlegend=False)
            for r0 in (0.5, 0.8, 0.95):
                f.add_scatter(x=r0 * np.cos(t), y=r0 * np.sin(t), mode="lines",
                              line=dict(color="#2a2050", width=1, dash="dot"), hoverinfo="skip", showlegend=False)
            for (a, b), _s in tp[:10]:
                f.add_scatter(x=[x[a - 1, 0], x[b - 1, 0]], y=[x[a - 1, 1], x[b - 1, 1]], mode="lines",
                              line=dict(color=NEON["mag"], width=2), opacity=0.7, hoverinfo="skip", showlegend=False)
            f.add_scatter(x=x[:, 0], y=x[:, 1], mode="markers+text", text=[str(i + 1) for i in range(n)],
                          textfont=dict(size=9, color=NEON["text"]), textposition="top center",
                          marker=dict(size=7 + 6 * u / u.max(), color=np.asarray(R["forman"]), colorscale="Ice",
                                      colorbar=dict(title="Forman"), line=dict(color=NEON["cyan"], width=0.5)),
                          name="noduri", hovertemplate="#%{text}<br>x=%{x:.3f} y=%{y:.3f}<extra></extra>")
            ai = np.array(anchors) - 1
            f.add_scatter(x=x[ai, 0], y=x[ai, 1], mode="markers", marker=dict(size=22, symbol="star", color=NEON["lime"],
                          line=dict(color="#fff", width=1)), name="ancore")
            f.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.06, xanchor="left", x=0))
            f.update_xaxes(range=[-1.05, 1.05], showgrid=False, zeroline=False)
            f.update_yaxes(range=[-1.05, 1.05], scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False)
            st.plotly_chart(f, width="stretch")
        with c2:
            f = go.Figure()
            for (a, b), _s in tp[:15]:
                f.add_trace(go.Scatter3d(x=[x[a - 1, 0], x[b - 1, 0]], y=[x[a - 1, 1], x[b - 1, 1]], z=[amp[a - 1], amp[b - 1]],
                                         mode="lines", line=dict(color=NEON["mag"], width=4), hoverinfo="skip",
                                         showlegend=False))
            f.add_trace(go.Scatter3d(x=x[:, 0], y=x[:, 1], z=amp, mode="markers+text", text=[str(i + 1) for i in range(n)],
                                     marker=dict(size=4 + 4 * u / u.max(), color=amp, colorscale="Plasma", opacity=0.95),
                                     textfont=dict(size=9, color=NEON["text"]), name="noduri"))
            f.update_layout(**PL, title="HOLOGRAMA · disc Poincaré × amplitudine Amplituhedron", height=560,
                            scene=dict(xaxis=dict(title="x", backgroundcolor="rgba(0,0,0,0)", gridcolor="#2a2050"),
                                       yaxis=dict(title="y", backgroundcolor="rgba(0,0,0,0)", gridcolor="#2a2050"),
                                       zaxis=dict(title="amp", backgroundcolor="rgba(0,0,0,0)", gridcolor="#2a2050"),
                                       camera=dict(eye=dict(x=1.5, y=1.4, z=0.9))))
            st.plotly_chart(f, width="stretch")
        c3, c4 = st.columns(2)
        with c3:
            S = np.array(R["pair_scatter"], dtype=float, copy=True)
            np.fill_diagonal(S, np.nan)
            f = fig(title=f"VOLUME DE ÎMPRĂȘTIERE S_ij · vol total {R['vol_total']:.1f}", height=520)
            f.add_heatmap(z=S, x=list(range(1, n + 1)), y=list(range(1, n + 1)), colorscale="Magma",
                          colorbar=dict(title="S_ij"))
            f.update_yaxes(autorange="reversed")
            st.plotly_chart(f, width="stretch")
        with c4:
            A = np.asarray(R["A"])
            dfp = pd.DataFrame([{"pereche încâlcită": f"{a} ⟷ {b}", "S_ij": s, "exces pereche A_ij": float(A[a - 1, b - 1])}
                                for (a, b), s in tp])
            st.markdown("**Cele mai puternice perechi încâlcite (volume de împrăștiere)**")
            st.dataframe(dfp.style.format(precision=4), width="stretch", hide_index=True, height=480)
        c5, c6 = st.columns(2)
        g, gap = np.asarray(R["gamma_grid"]), np.asarray(R["gap_grid"])
        with c5:
            f = fig(title="DECALAJ SPECTRAL min|λa−λb| vs γ (căutare punct excepțional)", xaxis_title="γ",
                    yaxis_title="decalaj minim", yaxis_type="log")
            f.add_scatter(x=g, y=gap, mode="lines+markers", line=dict(color=NEON["cyan"]))
            f.add_vline(x=R["gamma_q"], line=dict(color=NEON["mag"], dash="dash"), annotation_text="γ_q")
            st.plotly_chart(f, width="stretch")
        with c6:
            sp = np.asarray(R["spectrum_grid"])
            f = fig(title="TRAIECTORII SPECTRALE λ(γ) ÎN PLANUL COMPLEX", xaxis_title="Re λ", yaxis_title="Im λ")
            gg = np.repeat(g[:, None], sp.shape[1], 1)
            f.add_scatter(x=sp.real.ravel(), y=sp.imag.ravel(), mode="markers",
                          marker=dict(size=3, color=gg.ravel(), colorscale="Viridis", colorbar=dict(title="γ")), name="λ(γ)")
            f.add_scatter(x=[R["ep_lambda"].real], y=[R["ep_lambda"].imag], mode="markers",
                          marker=dict(size=16, symbol="x", color=NEON["mag"]), name="λ_EP")
            st.plotly_chart(f, width="stretch")
        if mode == "joker":
            st.markdown("### 🃏 Tensorul comun J — sistem bipartit H_Main ⊗ H_Joker (C⁴⁵ ⊗ C²⁰, descriptiv)")
            J = R["J"]
            mj = st.columns(4)
            mj[0].markdown(card("entropie de entanglement S_E", f"{J['S_E']:.4f}", "mag"), unsafe_allow_html=True)
            mj[1].markdown(card("număr Schmidt K_S", f"{J['K_S']:.3f}"), unsafe_allow_html=True)
            mj[2].markdown(card("informație mutuală I", f"{J['I']:.5f}", "lime"), unsafe_allow_html=True)
            mj[3].markdown(card("parametru de ordine SSB Φ", f"{J['Phi']:.3e}", "amber"), unsafe_allow_html=True)
            f = fig(title="CO-APARIȚII N_ja (număr principal j × Joker a) · tensorul comun cauzal", height=560,
                    xaxis_title="Joker a", yaxis_title="număr principal j")
            f.add_heatmap(z=np.asarray(R["cross_counts"]), x=list(range(1, 21)), y=list(range(1, n + 1)),
                          colorscale="Viridis", colorbar=dict(title="N_ja"))
            f.update_yaxes(autorange="reversed")
            st.plotly_chart(f, width="stretch")
            st.caption("Descriptori din modulul J (nemodificat), calculați de run_full_joker pe tensorul comun la pasul "
                       "final. Vocabular matematic aplicat unei tabele de co-apariție; fără pretenție fizică.")

    # Tab 3 — Convergența terminală: EXACT 3 variante după regula activă + sigiliul SHA-256 de timp
    with tabs[2]:
        st.markdown(f"### ♾ CONFIGURAȚIILE DE ECHILIBRU TERMODINAMIC · {info['name']} ({info['rule']})")
        label = (f"protocol TU3-{info['power']}" if R["is_protocol"] else "config NON-protocol")
        ok = render_variants(mode, R, label, crowd_penalty)
        if ok:
            vs = variants_of(mode, R)
            allnums = sorted({x for v in vs for x in (v if mode == "540" else v[0])})
            m = st.columns(4)
            m[0].markdown(card("numere distincte acoperite", f"{len(allnums)} / {3 * info['k']}", "lime"),
                          unsafe_allow_html=True)
            m[1].markdown(card("nucleu determinist (≥50% replici)",
                               " ".join(str(i + 1) for i in np.nonzero(np.asarray(R["core"]))[0]) or "—", "mag"),
                          unsafe_allow_html=True)
            m[2].markdown(card("replici Boltzmann · pași MCMC", f"{cfg.replicas:,} · {cfg.mcmc_steps:,}".replace(",", " ")),
                          unsafe_allow_html=True)
            m[3].markdown(card("timp motor GPU", f"{R['elapsed_s']:.1f} s", "amber"), unsafe_allow_html=True)
        joker_txt = ("; Joker: <code>E_J(a|V) = −ln q_V(a) + "
                     f"{cfg.mu_overlap:g}·ovJ(a)</code>, minim exhaustiv pe 1..20, în două etape (întâi V, apoi a)"
                     if mode == "joker" else "")
        st.markdown(f'<div class="ql-warn">Variantele sunt minimele energiei <code>E(S) = −Σ log π − {cfg.lam_pair:g}·Σ A_ij + '
                    f'{cfg.mu_crowd:g}·mulțime(S) + {cfg.mu_overlap:g}·suprapunere</code> pe {info["k"]} noduri din {n}'
                    f'{joker_txt}. <b>Exploratoriu, fără avantaj demonstrat; NU sunt predicții.</b> Nicio comparație cu '
                    'extrageri. Fără promisiuni de câștig.</div>', unsafe_allow_html=True)
        if mode == "joker" and ok:
            q = np.asarray(R["q_joker"])
            f = fig(title="DISTRIBUȚIA CONDIȚIONATĂ q_V(a) A JOKER-ULUI PE VARIANTĂ", xaxis_title="Joker a",
                    yaxis_title="q_V(a)", height=320, barmode="group")
            for i, col in enumerate((NEON["cyan"], NEON["mag"], NEON["lime"])):
                f.add_bar(x=list(range(1, 21)), y=q[i], name=f"varianta {i + 1}", marker=dict(color=col))
            f.add_hline(y=1 / 20, line=dict(color=NEON["amber"], dash="dot"), annotation_text="uniform 1/20")
            st.plotly_chart(f, width="stretch")
        tm = R["timings_s"]
        f = fig(title="PROFIL GPU PE OPERATOR (secunde)", xaxis_title="s", height=300)
        f.add_bar(y=list(tm.keys()), x=list(tm.values()), orientation="h", marker=dict(color=NEON["cyan"]))
        st.plotly_chart(f, width="stretch")
        st.markdown("### 🔏 Sigiliul temporal SHA-256 (commit–reveal local)")
        st.caption(f"Scrie local SHA-256 al celor 3 variante {info['name']} cu marcaj UTC, în "
                   f"{seal_dir.name}/ (separat de sigiliile 6/49). Nu este evaluare prospectivă și nu se verifică automat.")
        if ok and st.button(f"🔏 Sigilează variantele curente ({info['name']})", key=f"seal_btn_{mode}"):
            path, digest = write_seal(seal_dir, mode, seal_payload(mode, R))
            st.session_state[f"seal_{mode}"] = (str(path), digest)
        if st.session_state.get(f"seal_{mode}"):
            p, d = st.session_state[f"seal_{mode}"]
            st.success(f"Sigiliu scris: `{p}` · SHA-256 `{d}`")

    # Tab 4 — Multiversul Nul: universurile sintetice ale verificării de putere (read-only)
    with tabs[3]:
        pw = load_json(M.POWER_FILE if mode == "540" else MJ.POWER_FILE)
        st.markdown(f"### 🌌 MULTIVERSUL SINTETIC AL VERIFICĂRII DE PUTERE TU3-{info['power']} (read-only)")
        st.caption("Universuri SINTETICE generate după protocolul sigilat (nul exact și semnal plantat γ = 1/2, 1/8). "
                   "Puterea pe sintetic NU spune nimic despre arhiva reală și NU este avantaj predictiv.")
        if not pw:
            st.info("Verificarea de putere nu a rulat; produsul refuză datele reale.")
        else:
            gates = [("G1 putere γ=1/2", pw.get("G1_power_gamma_1_2_B512"), pw.get("G1_pass")),
                     ("G2 fals-pozitive control", pw.get("G2_fpr_control_B512"), pw.get("G2_pass"))]
            if mode == "joker":
                gates += [("GJ1 fereastră Joker γ=1/2", pw.get("GJ1_joker_window_gamma_1_2_B512"), pw.get("GJ1_pass")),
                          ("GJ2 fereastră Joker control", pw.get("GJ2_joker_window_control_B512"), pw.get("GJ2_pass"))]
            m = st.columns(1 + len(gates))
            m[0].markdown(card("verdict", str(pw.get("verdict")), "lime" if str(pw.get("verdict", "")).endswith("PASS") else "mag"),
                          unsafe_allow_html=True)
            for i, (nm, val, ps) in enumerate(gates):
                m[i + 1].markdown(card(nm, f"{val:.3f} · {'PASS' if ps else 'FAIL'}" if isinstance(val, float) else "—",
                                       "lime" if ps else "mag"), unsafe_allow_html=True)
            rows = [{"set": k, **{kk: vv for kk, vv in v.items() if not isinstance(vv, (dict, list))}}
                    for k, v in (pw.get("sets") or {}).items()]
            if rows:
                st.dataframe(pd.DataFrame(rows).style.format(precision=4), width="stretch", hide_index=True)
                f = fig(title="RATA DE DETECȚIE PE SET (sintetic)", xaxis_title="set", yaxis_title="rată", height=300)
                f.add_bar(x=[r["set"] for r in rows], y=[r.get("rate", 0.0) for r in rows],
                          marker=dict(color=[NEON["cyan"], NEON["mag"], NEON["lime"]][:len(rows)]))
                st.plotly_chart(f, width="stretch")
        _sr_d2 = sr_slot_open()  # TU3-SR-R (S8, inserție): caseta „NERULAT” de mai jos se scrie într-un placeholder…
        st.info(f"SCI (indicele de coerență structurală) pe istoria reală {info['name']}: NERULAT — `validare.py` este "
                "definit pe 6/49; orice statistică nouă pe istoria reală cere protocol separat, sigilat înainte.")
        sr_slot_close(_sr_d2, mode, "D2", ctx)  # TU3-SR-R: …înlocuită pe loc de verdictul D2 dacă rularea reală există
        fr = ds.onehot.sum(0).detach().cpu().numpy()
        f = fig(title=f"FRECVENȚE REALE vs AȘTEPTARE UNIFORMĂ (descriptiv, LIVE {info['name']})", xaxis_title="număr",
                yaxis_title="apariții")
        f.add_bar(x=list(range(1, n + 1)), y=fr, marker=dict(color=NEON["cyan"]))
        f.add_hline(y=info["r"] * ds.n_draws / n, line=dict(color=NEON["amber"], dash="dot"), annotation_text=f"{info['r']}N/{n}")
        st.plotly_chart(f, width="stretch")
        if mode == "joker" and ds.joker_onehot is not None:
            jf = ds.joker_onehot.sum(0).detach().cpu().numpy()
            f = fig(title="FRECVENȚE JOKER vs AȘTEPTARE UNIFORMĂ (descriptiv)", xaxis_title="Joker", yaxis_title="apariții",
                    height=300)
            f.add_bar(x=list(range(1, 21)), y=jf, marker=dict(color=NEON["amber"]))
            f.add_hline(y=ds.n_draws / 20, line=dict(color=NEON["lime"], dash="dot"), annotation_text="N/20")
            st.plotly_chart(f, width="stretch")

    # Tab 5 — Mașina Timpului: NERULAT + inventarul setului LIVE
    with tabs[4]:
        st.markdown(f"### ⏳ Mașina Timpului · {info['name']}")
        _sr_d1 = sr_slot_open()  # TU3-SR-R (S8, inserție): caseta „NERULAT” de mai jos se scrie într-un placeholder…
        st.info(f"Backtestul cauzal pe istoria reală {info['name']} este NERULAT: cere un protocol separat, sigilat înainte "
                "(TU3-P1 §0). Arhiva este deja explorată; nu există set „nevăzut”.")
        sr_slot_close(_sr_d1, mode, "D1", ctx)  # TU3-SR-R: …înlocuită pe loc de verdictele D1 + promovare (rulare reală)
        s = ds.summary()
        st.markdown("**Inventarul setului LIVE (descriptiv, nu experiment)**")
        st.dataframe(pd.DataFrame([{"câmp": k, "valoare": json.dumps(v, ensure_ascii=False, default=str)}
                                   for k, v in s.items()]), width="stretch", hide_index=True)

    # Tab 6 — Ablație (NON-protocol) & registrul sigiliilor modului
    with tabs[5]:
        c1, c2 = st.columns([1, 1.4])
        with c1:
            st.markdown("### 🧪 Panou de ablație (NON-protocol)")
            with st.form(f"ablation_{mode}"):
                a_walk = st.checkbox("O1 walk non-hermitic", True, key=f"abl_walk_{mode}")
                a_amp = st.checkbox("O2 Amplituhedron", True, key=f"abl_amp_{mode}")
                a_poi = st.checkbox("O3 Poincaré", True, key=f"abl_poi_{mode}")
                a_kur = st.checkbox("O4 Kuramoto + interferență", True, key=f"abl_kur_{mode}")
                a_crowd = st.checkbox("Scutul Anti-Mulțime", True, key=f"abl_crowd_{mode}")
                go_btn = st.form_submit_button("⚡ Recalculează pe GPU", key=f"abl_submit_{mode}")
            if go_btn:
                cfg2 = replace(cfg, use_walk=a_walk, use_amplituhedron=a_amp, use_poincare=a_poi, use_kuramoto=a_kur,
                               crowd_shield=a_crowd)
                with st.spinner("Recalculare câmp…"):
                    st.session_state[f"ablation_result_{mode}"] = run_engine_mode(
                        mode, json.dumps(asdict(cfg2), sort_keys=True), key)
        with c2:
            ab = st.session_state.get(f"ablation_result_{mode}")
            if ab:
                st.markdown(f"**Rezultat ablație** · config `{ab['config_digest'][:12]}…` · "
                            f"{'protocol' if ab['is_protocol'] else 'NON-protocol'}")
                render_variants(mode, ab, "ablație", crowd_penalty)
                tv = 0.5 * float(np.abs(pi - np.asarray(ab["pi"])).sum())
                st.caption(f"Distanța de variație totală π protocol ↔ ablație: {tv:.4f}")
            else:
                st.info("Debifează operatori și apasă Recalculează pentru a vedea contribuția fiecăruia.")
        st.markdown("---")
        st.markdown(f"### 🔏 Registrul sigiliilor {info['name']}")
        seals = sorted(seal_dir.glob(f"SIGILIU_{mode}_*.json")) if seal_dir.exists() else []
        if seals:
            st.dataframe(pd.DataFrame([{"fișier": s_.name, "sha256": (load_json(s_) or {}).get("sha256", "")[:24] + "…",
                                        "variante": json.dumps((load_json(s_) or {}).get("payload", {}).get("variants"))}
                                       for s_ in seals[-10:]]), width="stretch", hide_index=True)
        else:
            st.caption("Niciun sigiliu în acest mod (butonul de sigilare este în tabul Convergența terminală).")

    # Taburile 7–12 — piste definite și închise NUMAI pe 6/49
    for t_idx, (track, proto, report) in zip(range(6, 12), CLOSED_649):
        if t7a_port(t_idx, tabs[t_idx], mode, ds, key, ctx):  # TU3-T7A (inserție): porturi DESCRIPTIVE (7 BO, 8 WU)
            continue
        if t7b_port(t_idx, tabs[t_idx], mode, ds, key, ctx):  # TU3-T7B (inserție): porturi DESCRIPTIVE (9 GL, 10 SE)
            continue
        if t7c_port(t_idx, tabs[t_idx], mode, ds, key, ctx):  # TU3-T7C (inserție): porturi DESCRIPTIVE (11 CS, 12 PL)
            continue
        with tabs[t_idx]:
            st.markdown(f"### {TAB_LABELS[t_idx]}")
            st.info(f"NEAPLICABIL în modul {info['name']}: pista {track} (protocol {proto}) a fost definită, calificată sau "
                    f"rulată numai pe Loto 6/49 și este închisă. În acest mod nu există protocol propriu — fără calcul. "
                    "Orice transpunere cere un protocol nou, sigilat înainte.")
            st.caption(f"Raportul pistei (6/49): {report} · comută pe 🌌 6/49 din sidebar pentru afișarea ei.")

    st.markdown(f'<p class="ql-sub" style="text-align:center;margin-top:30px">TU3 v3.0 · {info["name"]} · protocol '
                f'TU3-{info["power"]} · torch {torch.__version__} · sursă LIVE {R["source_sha256"][:12]}… · calcul clasic · '
                'positive_claims_allowed=false</p>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# TU3-L649 — sursa datelor 6/49 în aplicație (PROTOCOL_TU3_L649.md §3.2; sigilat în SIGILIU_TU3_L649.json ÎNAINTE de
# cod). LIVE implicit; „înghețat (sigilat)” = calea anterioară din app.py, neatinsă. Setul LIVE = același
# parser.build_dataset, prin adaptorul parser_multi.adapt_649 (ambele nemodificate). Variantele = minime de energie,
# NU predicții. Calcul clasic. positive_claims_allowed=false.
# ---------------------------------------------------------------------------
L649_SOURCES = {"live": "LIVE — arhiva actualizată automat", "frozen": "înghețat (sigilat)"}
L649_PROTOCOL = HERE / "PROTOCOL_TU3_L649.md"
L649_MAX_KEYS = 20
L649_LINE_PREFIX = "🛰 Sursa 6/49:"


def l649_source_selector() -> str:
    """Comutatorul sursei 6/49 (bara laterală); implicit LIVE; alegerea se păstrează la revenirea din alt mod."""
    opts = list(L649_SOURCES)
    saved = st.session_state.get("l649_src_saved", "live")
    with st.sidebar:
        src = st.radio("Sursa datelor 6/49", opts, index=opts.index(saved if saved in opts else "live"),
                       format_func=L649_SOURCES.get, key="l649_src")
        st.caption("LIVE = arhiva actualizată automat (lanț pointer → manifest → JSONL verificat). Înghețat (sigilat) = "
                   "fișierul protocolului QL649-P1. Protocoalele, backtestul, SCI și pistele închise rămân pe înghețat.")
    st.session_state["l649_src_saved"] = src
    return src


def l649_live_key() -> str:
    """sha256 al JSONL-ului LIVE 6/49 rezolvat (lanțul pointer → manifest → JSONL verificat de parser_multi)."""
    return live_key("649")


@st.cache_resource(show_spinner=False, max_entries=1)
def l649_live_dataset(src_key: str):
    import parser_multi as PM
    ds = PM.build_game_dataset("649", "live")
    if ds.source_sha256 != src_key:
        raise RuntimeError("arhiva LIVE s-a schimbat în timpul încărcării; reîncarcă pagina")
    return ds


@st.cache_resource(show_spinner=False, max_entries=4)
def l649_run_engine(cfg_json: str, src_key: str) -> dict:
    """Același produs ca app.run_engine (engine.run_full), pe setul LIVE; aceeași conversie tensor → NumPy."""
    import engine as E
    cfg = E.Config(**json.loads(cfg_json))
    base = l649_live_dataset(src_key).base
    res = E.run_full(base, cfg, base.device)
    out = {}
    for k, v in res.items():
        out[k] = v.detach().cpu().numpy() if torch.is_tensor(v) else v
    return out


@st.cache_data(show_spinner=False, max_entries=2)
def l649_martor(src_key: str) -> dict:
    """Martorul §3.3-S3 (pe CPU): parser_multi.compare_frozen_live(înghețat, LIVE) + sha-uri și intervale. Descriptiv."""
    import parser_multi as PM
    fr = PM.build_game_dataset("649", "frozen", device="cpu")
    lv = PM.build_game_dataset("649", "live", device="cpu")
    cmp = PM.compare_frozen_live(fr, lv)
    return dict(cmp, frozen_sha256=fr.source_sha256, live_sha256=lv.source_sha256,
                live_adapted_sha256=lv.provenance.get("adapted_sha256"), frozen_n=fr.n_draws, live_n=lv.n_draws,
                frozen_last=fr.step_dates[-1] if fr.step_dates else None,
                live_last=lv.step_dates[-1] if lv.step_dates else None, live_matches_key=lv.source_sha256 == src_key)


def l649_info(src: str) -> dict:
    """Cheia LIVE, proveniența curentă și martorul. LIVE indisponibil în modul LIVE ⇒ eroare explicită + oprire."""
    import parser_multi as PM
    info = {"src": src}
    try:
        path, prov = PM.resolve_live("649")
        info["live_key"] = PM.sha256_file(path)
        info["live_prov"] = prov
        info["martor"] = l649_martor(info["live_key"])
    except Exception as exc:  # noqa: BLE001 — orice eșec LIVE se afișează, fără comutare tăcută
        info["live_error"] = f"{type(exc).__name__}: {exc}"
        info.pop("martor", None)
        if src == "live":
            st.error(f"{L649_LINE_PREFIX} LIVE indisponibilă ({info['live_error']}). Nu comut tăcut pe altă sursă: "
                     "alege «înghețat (sigilat)» din bara laterală.")
            st.stop()
    return info


def l649_release(old: str, new: str, get_dataset_649) -> dict:
    """Schimbarea sursei: golește setul sursei părăsite, apoi gc + torch.cuda.empty_cache(); jurnalizează."""
    before = _vram()
    if old == "live":
        l649_live_dataset.clear()
    else:
        get_dataset_649.clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    ev = {"from": old, "to": new, "vram_before": before, "vram_after": _vram(),
          "utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    st.session_state.setdefault("l649_release_log", []).append(ev)
    return ev


def l649_source_line(src: str, info: dict) -> str:
    import parser_multi as PM
    m = info.get("martor")
    if src == "live":
        prov = info.get("live_prov", {})
        line = (f"{L649_LINE_PREFIX} LIVE (implicit) · JSONL sha {info['live_key'][:12]}… · {prov.get('version_dir')} · "
                f"{m['live_n']} extrageri până la {m['live_last']} · configurația QL649-P1 pe date LIVE ≠ rezultatul "
                "protocolului științific (închis pe sursa înghețată)")
    else:
        fsha = m["frozen_sha256"] if m else PM.FROZEN_649_SHA256
        line = f"{L649_LINE_PREFIX} înghețat (sigilat) · sha {fsha[:12]}… = referința protocolului QL649-P1"
        if m:
            line += f" · {m['frozen_n']} extrageri până la {m['frozen_last']}"
    if m:
        line += (f" · martor față de înghețat: {m['common_keys']} chei comune, "
                 f"{len(m['differing_on_common_keys'])} diferențe pe chei comune, {len(m['only_in_live'])} numai în "
                 f"LIVE, {len(m['only_in_frozen'])} numai în înghețat · LIVE ⊇ înghețat: "
                 f"{'DA' if m['live_superset_of_frozen'] else 'NU'}")
    else:
        line += f" · LIVE indisponibil: {info.get('live_error')}"
    return line + (" · taburile 4–5 și 7–12 = rezultate sigilate pe sursa înghețată (SCI, backtest, piste închise; "
                   "linia 6N/49 din tabul 4 folosește N al sursei active) · variantele = minime de energie, NU predicții")


def l649_warnings(m: dict | None) -> list[str]:
    """Diferențele martorului: se AFIȘEAZĂ, nu se repară (§3.3-S3)."""
    out = []
    if not m:
        return out
    for key, what in (("differing_on_common_keys", "chei comune cu dată/numere diferite între LIVE și înghețat"),
                      ("only_in_frozen", "chei din sursa înghețată care lipsesc din LIVE")):
        ks = list(m.get(key) or [])
        if ks:
            out.append(f"Martor L649: {len(ks)} {what} (afișate, NEreparate): " + ", ".join(ks[:L649_MAX_KEYS])
                       + (" …" if len(ks) > L649_MAX_KEYS else ""))
    return out


def l649_render_source(src: str, info: dict) -> None:
    st.caption(l649_source_line(src, info))
    for w in l649_warnings(info.get("martor")):
        st.warning(w)


def l649_seal_fields(src: str, info: dict) -> dict:
    """Câmpurile sursei active în sigiliul de timp 6/49 (incluse în sha256 canonic)."""
    import parser_multi as PM
    m = info.get("martor") or {}
    live = src == "live"
    return {"l649_source_kind": src,
            "l649_source_file_sha256": info.get("live_key") if live else PM.FROZEN_649_SHA256,
            "l649_live_version_dir": info.get("live_prov", {}).get("version_dir") if live else None,
            "l649_adapted_sha256": m.get("live_adapted_sha256") if live else None,
            "l649_protocol_sha256": hashlib.sha256(L649_PROTOCOL.read_bytes()).hexdigest()}


# ---------------------------------------------------------------------------
# TU3-T7A — porturile DESCRIPTIVE ale taburilor 7–12 în 5/40 și Joker (PROTOCOL_TU3_T7A.md; sigilat în
# SIGILIU_TU3_T7A.json ÎNAINTE de cod). D3 = (b): fără verdict, fără scor, fără bilete, fără clasări; verdictele pistelor
# 6/49 NU se transferă. S4: tab 7 = BO, tab 8 = WU; taburile 9–12 rămân NEAPLICABIL până la S5/S6. Algoritmii: modulul
# tu3/porturi_712.py (copiați literal din pistele închise, care NU se importă). Calcul clasic NumPy float64 pe CPU.
# Variantele produsului = minime de energie, NU predicții. positive_claims_allowed=false.
# ---------------------------------------------------------------------------
T7A_PORTED = {6: "bo", 7: "wu"}
T7A_NOTE = ("DESCRIPTIV · fără verdict · fără scor · fără bilete · fără clasări · verdictul pistei 6/49 NU se "
            "transferă · calcul clasic NumPy float64 pe CPU · positive_claims_allowed=false")


def _t7a_components(ds) -> list:
    import porturi_712 as PT
    jo = None if ds.joker_onehot is None else ds.joker_onehot.detach().cpu().numpy()
    return PT.components(ds.onehot.detach().cpu().numpy(), ds.step_offsets.detach().cpu().numpy(), ds.game.n,
                         ds.game.r, jo, ds.game.joker_m)


@st.cache_data(show_spinner=False, max_entries=4)
def t7a_bo(mode: str, src_key: str, _ds) -> list:
    """Portul BO pe setul LIVE al modului; cheia cache-ului = (mod, sha JSONL LIVE)."""
    import porturi_712 as PT
    return PT.describe_bo(_t7a_components(_ds))


@st.cache_data(show_spinner=False, max_entries=4)
def t7a_wu(mode: str, src_key: str, _ds) -> list:
    """Portul WU pe setul LIVE al modului (θ̂ descriptiv + martorul pe fixture); cheia = (mod, sha JSONL LIVE)."""
    import porturi_712 as PT
    return PT.describe_wu(_t7a_components(_ds))


def _t7a_identity_line(kind: str) -> str:
    import porturi_712 as PT
    li = PT.latest_identity()
    if not li:
        return "Testul de identitate pe 6/49: raport absent (tu3/rezultate/T7A/)."
    return (f"Testul de identitate pe 6/49 (portul reproduce cifrele pistei originale): {li.get(kind.upper())} · "
            f"{li['file']}.")


def t7a_port(t_idx: int, tab, mode: str, ds, key: str, ctx: dict) -> bool:
    """True dacă tabul are port (S4: 7 = BO, 8 = WU) și a fost randat; False ⇒ tabul rămâne NEAPLICABIL, ca înainte."""
    kind = T7A_PORTED.get(t_idx)
    if kind is None:
        return False
    with tab:
        st.markdown(f"### {TAB_LABELS[t_idx]} · port DESCRIPTIV · {INFO[mode]['name']}")
        st.caption(T7A_NOTE)
        try:
            (t7a_render_bo if kind == "bo" else t7a_render_wu)(mode, ds, key, ctx)
        except Exception as exc:  # noqa: BLE001 — eroare explicită, fără comutare tăcută
            st.error(f"Portul {kind.upper()} a refuzat rularea: {type(exc).__name__}: {exc}")
    return True


def t7a_render_bo(mode: str, ds, key: str, ctx: dict) -> None:
    card, fig, NEON = ctx["card"], ctx["fig"], ctx["NEON"]
    st.caption("Recursia BOCPD Beta–Bernoulli exactă (Adams & MacKay 2007) a pistei BO649, copiată literal și "
               "parametrizată în (n, κ), cu parametrii pistei neschimbați (h = 1/250, m0 = 12, fereastra r ≤ 100), pe "
               f"setul LIVE {INFO[mode]['name']} (sha {key[:12]}…). Descrie cât de lung pare regimul curent al "
               "frecvențelor; NU prezice extragerea următoare. " + _t7a_identity_line("bo"))
    with st.spinner("Port BO pe CPU…"):
        comps = t7a_bo(mode, key, ds)
    for c in comps:
        st.markdown(f"**{c['component']}** · n = {c['N']} · κ = {c['kappa']} bile pe extragere")
        m = st.columns(5)
        m[0].markdown(card("extrageri", f"{c['n_draws']:,}".replace(",", " ")), unsafe_allow_html=True)
        m[1].markdown(card("pași (zile)", f"{c['n_steps']:,}".replace(",", " "), "mag"), unsafe_allow_html=True)
        m[2].markdown(card("E[r] la ultimul pas", f"{c['Er_last']:.1f}", "amber"), unsafe_allow_html=True)
        m[3].markdown(card("P(r ≤ 100) la ultimul pas", f"{c['p_recent_last']:.4f}", "lime"), unsafe_allow_html=True)
        m[4].markdown(card("pași cu P(r ≤ 100) > ½", f"{c['steps_p_recent_gt_half']}"), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            f = fig(title=f"E[r] PE PAȘI · {c['component'].upper()} · DESCRIPTIV", xaxis_title="pas",
                    yaxis_title="E[r] (pași-zi)", height=360)
            f.add_scatter(x=c["ks"], y=c["Er"], mode="lines", name="E[r]", line=dict(color=NEON["cyan"], width=2))
            f.add_scatter(x=c["ks"], y=c["ks"], mode="lines", name="fără nicio ruptură (r = k)",
                          line=dict(color=NEON["dim"], dash="dot"))
            st.plotly_chart(f, width="stretch", key=f"t7a_bo_er_{mode}_{c['key']}")
        with c2:
            pl = c["post_last"]
            f = fig(title=f"POSTERIORUL LUNGIMII REGIMULUI LA ULTIMUL PAS · {c['component'].upper()}",
                    xaxis_title="r (pași-zi)", yaxis_title="P(r)", height=360)
            f.add_scatter(x=np.arange(pl.shape[0]), y=pl, mode="lines", fill="tozeroy", name="P(r)",
                          line=dict(color=NEON["mag"], width=2))
            st.plotly_chart(f, width="stretch", key=f"t7a_bo_post_{mode}_{c['key']}")


def t7a_render_wu(mode: str, ds, key: str, ctx: dict) -> None:
    card, fig, NEON = ctx["card"], ctx["fig"], ctx["NEON"]
    st.caption("Modelul pistei WU649 (cursa exponențială Luce/Plackett/Wallenius cu ordinea nevăzută marginalizată; "
               "Yellott 1977), copiat literal și parametrizat în (n, κ). Pista WU649 a rămas necalificată pe 6/49 "
               "(martorul de decizie a eșuat) și nu a avut backtest. Aici: (a) ajustarea MAP a propensiunilor θ̂ "
               f"(σ = 0.2) pe toate extragerile setului LIVE {INFO[mode]['name']} (sha {key[:12]}…) — o descriere a "
               "istoriei, nu o prognoză; θ̂ în ordinea naturală a bilelor, fără probabilități de includere, fără "
               "bilete; (b) martorul de informație pe un fixture CONSTRUIT pentru (n, κ), nu pe date de joc. "
               + _t7a_identity_line("wu"))
    with st.spinner("Port WU pe CPU…"):
        comps = t7a_wu(mode, key, ds)
    for c in comps:
        fw, w = c["fit"], c["witness"]
        st.markdown(f"**{c['component']}** · n = {fw['N']} · κ = {fw['kappa']} · {fw['n_draws']} extrageri")
        m = st.columns(5)
        m[0].markdown(card("θ̂ minim", f"{fw['theta_min']:+.4f}", "mag"), unsafe_allow_html=True)
        m[1].markdown(card("θ̂ maxim", f"{fw['theta_max']:+.4f}", "amber"), unsafe_allow_html=True)
        m[2].markdown(card("Σ θ̂", f"{fw['sum_theta']:.1e}"), unsafe_allow_html=True)
        m[3].markdown(card("certificat MAP", f"{'DA' if fw['cert'] else 'NU'} · ‖g‖∞ {fw['gnorm']:.1e}",
                           "lime" if fw["cert"] else "mag"), unsafe_allow_html=True)
        m[4].markdown(card("iterații Newton", f"{fw['iters']}"), unsafe_allow_html=True)
        balls = np.arange(1, fw["N"] + 1)
        c1, c2 = st.columns(2)
        with c1:
            f = fig(title=f"θ̂ PE BILĂ (ORDINE NATURALĂ) · {c['component'].upper()} · DESCRIPTIV", xaxis_title="bilă",
                    yaxis_title="θ̂ = log w (MAP, σ = 0.2)", height=340)
            f.add_bar(x=balls, y=fw["theta"], marker=dict(color=NEON["violet"]), name="θ̂")
            st.plotly_chart(f, width="stretch", key=f"t7a_wu_theta_{mode}_{c['key']}")
        with c2:
            f = fig(title=f"FRECVENȚA OBSERVATĂ ↔ θ̂ · {c['component'].upper()}", xaxis_title="frecvență relativă",
                    yaxis_title="θ̂", height=340)
            f.add_scatter(x=fw["freq_rel"], y=fw["theta"], mode="markers", text=[str(b) for b in balls],
                          marker=dict(color=NEON["cyan"], size=8), name="bile")
            st.plotly_chart(f, width="stretch", key=f"t7a_wu_freq_{mode}_{c['key']}")
        if w["applicable"]:
            st.markdown(f"Martorul de informație (fixture construit pentru n = {w['n']}, κ = {w['kappa']}; aceleași "
                        f"numărări, altă compoziție a colegilor bilelor {w['balls'][0]} și {w['balls'][1]})")
            m2 = st.columns(4)
            m2[0].markdown(card("max |Δq| H+ ↔ H−", f"{w['max_abs_dq']:.2e}"), unsafe_allow_html=True)
            m2[1].markdown(card("invarianța la ordine", f"{w['order_invariance_max_dq']:.1e}"), unsafe_allow_html=True)
            m2[2].markdown(card("aceleași numărări", "DA" if w["same_counts"] else "NU"), unsafe_allow_html=True)
            m2[3].markdown(card("certificate", f"{sum(w['cert'])} / 3"), unsafe_allow_html=True)
            f = fig(title=f"MARTORUL (FIXTURE) · q PENTRU BILELE {w['balls'][0]} (COLEGI GREI) ȘI {w['balls'][1]} "
                          "(COLEGI UȘORI)", xaxis_title="bilă (fixture)", yaxis_title="q", height=300)
            f.add_bar(x=[str(b) for b in w["balls"]], y=w["q_balls_Hplus"],
                      marker=dict(color=[NEON["cyan"], NEON["mag"]]))
            st.plotly_chart(f, width="stretch", key=f"t7a_wu_wit_{mode}_{c['key']}")
        else:
            st.caption(f"Martorul de informație: {w['reason']}.")


# ---------------------------------------------------------------------------
# TU3-T7B — porturile DESCRIPTIVE GL (tab 9) și SE (tab 10) în 5/40 și Joker (PROTOCOL_TU3_T7B.md; sigilat în
# SIGILIU_TU3_T7B.json ÎNAINTE de cod; protocolul comun PROTOCOL_TU3_T7A §3). D3 = (b): fără verdict, fără scor, fără
# bilete, fără clasări; verdictele pistelor 6/49 NU se transferă. S5: tab 9 = GL, tab 10 = SE; taburile 11–12 rămân
# NEAPLICABIL până la S6. Algoritmii: tu3/porturi_712.py (secțiunea TU3-T7B, copiați literal din gl649/se649, care NU
# se importă). Calcul clasic pe CPU: exact în Q (fractions) + NumPy float64. positive_claims_allowed=false.
# ---------------------------------------------------------------------------
T7B_PORTED = {8: "gl", 9: "se"}
T7B_NOTE = ("DESCRIPTIV · fără verdict · fără scor · fără bilete · fără clasări · verdictul pistei 6/49 NU se "
            "transferă · calcul clasic pe CPU: exact în Q (fractions) + NumPy float64 · positive_claims_allowed=false")


@st.cache_data(show_spinner=False, max_entries=4)
def t7b_gl(mode: str, src_key: str, _ds) -> list:
    """Portul GL pe setul LIVE al modului (toate extragerile); cheia cache-ului = (mod, sha JSONL LIVE)."""
    import porturi_712 as PT
    return PT.describe_gl(_t7a_components(_ds))


@st.cache_data(show_spinner=False, max_entries=4)
def t7b_se(mode: str, src_key: str, _ds) -> list:
    """Portul SE pe setul LIVE al modului (datele pașilor → anotimpuri); cheia cache-ului = (mod, sha JSONL LIVE)."""
    import porturi_712 as PT
    return PT.describe_se(_t7a_components(_ds), list(_ds.step_dates))


def _t7b_identity_line(kind: str) -> str:
    import porturi_712 as PT
    li = PT.latest_identity_t7b()
    if not li:
        return "Testul de identitate pe 6/49: raport absent (tu3/rezultate/T7B/)."
    return (f"Testul de identitate pe 6/49 (portul reproduce cifrele pistei originale): {li.get(kind.upper())} · "
            f"{li['file']}.")


def t7b_port(t_idx: int, tab, mode: str, ds, key: str, ctx: dict) -> bool:
    """True dacă tabul are port T7B (9 = GL, 10 = SE) și a fost randat; False ⇒ tabul rămâne NEAPLICABIL, ca înainte."""
    kind = T7B_PORTED.get(t_idx)
    if kind is None:
        return False
    with tab:
        st.markdown(f"### {TAB_LABELS[t_idx]} · port DESCRIPTIV · {INFO[mode]['name']}")
        st.caption(T7B_NOTE)
        try:
            (t7b_render_gl if kind == "gl" else t7b_render_se)(mode, ds, key, ctx)
        except Exception as exc:  # noqa: BLE001 — eroare explicită, fără comutare tăcută
            st.error(f"Portul {kind.upper()} a refuzat rularea: {type(exc).__name__}: {exc}")
    return True


def t7b_render_gl(mode: str, ds, key: str, ctx: dict) -> None:
    card, fig, NEON = ctx["card"], ctx["fig"], ctx["NEON"]
    st.caption("Modelul pistei GL649 (așteptarea ajustată Bayes liniară Goldstein–Wooff pe incidența glifelor zecimale "
               "tipărite pe bile, Woodbury exact în Q), copiat literal și parametrizat în (n, κ), cu hiperparametrii "
               "relativi ai pistei neschimbați (s_g = p0/10, s_e = p0/20, p0 = κ/n). Structura glifelor G (n × 10) e "
               "definită a priori din scrierea zecimală a numerelor 1..n; premisa fizică (cerneală, vopsea, gravură) "
               "rămâne NEVERIFICATĂ. Aici: efectele de glifă ajustate γ̂ pe toate extragerile setului LIVE "
               f"{INFO[mode]['name']} (sha {key[:12]}…) și frecvența observată a fiecărei glife — o descriere a "
               "istoriei, nu o prognoză; fără propensiuni pe bile, fără bilete. " + _t7b_identity_line("gl"))
    with st.spinner("Port GL pe CPU…"):
        comps = t7b_gl(mode, key, ds)
    digits = [str(d) for d in range(10)]
    for c in comps:
        st.markdown(f"**{c['component']}** · n = {c['N']} · κ = {c['kappa']} · {c['n_draws']} extrageri")
        m = st.columns(4)
        m[0].markdown(card("extrageri", f"{c['n_draws']:,}".replace(",", " ")), unsafe_allow_html=True)
        m[1].markdown(card("γ̂ / p0 minim", f"{c['gamma_rel_min']:+.4f}", "mag"), unsafe_allow_html=True)
        m[2].markdown(card("γ̂ / p0 maxim", f"{c['gamma_rel_max']:+.4f}", "amber"), unsafe_allow_html=True)
        ok = c["sum_exact_ok"] and c["z_perp_ok"]
        m[3].markdown(card("controale exacte în Q", "DA" if ok else "NU", "lime" if ok else "mag"),
                      unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            f = fig(title=f"EFECTE DE GLIFĂ AJUSTATE (γ̂ / p0) · {c['component'].upper()} · DESCRIPTIV",
                    xaxis_title="cifră", yaxis_title="γ̂ / p0", height=320)
            f.add_bar(x=digits, y=c["gamma_rel"], marker=dict(color=NEON["cyan"]), name="γ̂ / p0")
            st.plotly_chart(f, width="stretch", key=f"t7b_gl_gamma_{mode}_{c['key']}")
        with c2:
            f = fig(title=f"FRECVENȚA OBSERVATĂ A GLIFEI FAȚĂ DE UNIFORM · {c['component'].upper()}",
                    xaxis_title="cifră", yaxis_title="observat / așteptat − 1", height=320)
            f.add_bar(x=digits, y=c["glyph_freq_rel"], marker=dict(color=NEON["violet"]),
                      text=[f"{k} etichete" for k in c["glyph_labels"]], name="glife")
            st.plotly_chart(f, width="stretch", key=f"t7b_gl_freq_{mode}_{c['key']}")
    st.caption("Sectorul antisimetric și martorii de informație/decizie ai pistei (Q5–Q6) sunt specifici etichetelor "
               "10t + d ≤ 49 și nu se portează; nici biletele, nici scorurile. Pista GL649 rămâne închisă pe 6/49.")


def t7b_render_se(mode: str, ds, key: str, ctx: dict) -> None:
    card, fig, NEON = ctx["card"], ctx["fig"], ctx["NEON"]
    st.caption("Modelul pistei SE649 (Bayes liniar ierarhic etichetă × anotimp meteorologic al datei extragerii, "
               "ponderi Sherman–Morrison exacte în Q), copiat literal și parametrizat în (n, κ), cu hiperparametrii "
               "relativi ai pistei neschimbați (τa = p0/20, τb = p0/5, p0 = κ/n); premisa fizică rămâne NEVERIFICATĂ. "
               f"Aici, pe toate extragerile setului LIVE {INFO[mode]['name']} (sha {key[:12]}…): numărul de extrageri "
               "pe anotimp, ponderile w_φ ale modelului (cât cântărește fiecare anotimp observat pentru un anotimp-"
               "țintă), statistica G a tabelului bilă × anotimp (fără p-valoare, fără comparație cu universuri nule) "
               "și frecvențele relative pe anotimp — o descriere a istoriei, nu o prognoză; fără propensiuni, fără "
               "bilete. " + _t7b_identity_line("se"))
    with st.spinner("Port SE pe CPU…"):
        comps = t7b_se(mode, key, ds)
    for c in comps:
        names = c["season_names"]
        st.markdown(f"**{c['component']}** · n = {c['N']} · κ = {c['kappa']} · {c['n_draws']} extrageri")
        m = st.columns(4)
        m[0].markdown(card("extrageri pe anotimp", " · ".join(str(x) for x in c["n_per_season"])),
                      unsafe_allow_html=True)
        m[1].markdown(card("statistica G (bilă × anotimp)", f"{c['G']:.2f}", "amber"), unsafe_allow_html=True)
        m[2].markdown(card("Σ w_φ (min–max)", f"{min(c['weights_sum'].values()):.4f}–"
                                              f"{max(c['weights_sum'].values()):.4f}", "mag"), unsafe_allow_html=True)
        m[3].markdown(card("control exact Σ w_φ < 1", "DA" if c["wsum_lt1_ok"] else "NU",
                           "lime" if c["wsum_lt1_ok"] else "mag"), unsafe_allow_html=True)
        W = c["weights_by_target_season"]
        z = [[W[t].get(o) for o in names] for t in names]
        c1, c2 = st.columns(2)
        with c1:
            f = fig(title=f"PONDERILE w_φ ALE MODELULUI · {c['component'].upper()} · DESCRIPTIV",
                    xaxis_title="anotimp observat", yaxis_title="anotimp-țintă", height=340)
            f.add_heatmap(z=z, x=names, y=names, colorscale="Viridis", text=[[f"{v:.3f}" for v in r] for r in z],
                          texttemplate="%{text}", name="w")
            st.plotly_chart(f, width="stretch", key=f"t7b_se_w_{mode}_{c['key']}")
        with c2:
            fr = np.asarray(c["freq_rel_season"], dtype=float)
            f = fig(title=f"FRECVENȚA RELATIVĂ PE ANOTIMP (c / (n_φ p0) − 1) · {c['component'].upper()}",
                    xaxis_title="bilă (ordine naturală)", yaxis_title="anotimp", height=340)
            f.add_heatmap(z=fr.T.tolist(), x=list(range(1, c["N"] + 1)), y=names, colorscale="RdBu", zmid=0.0,
                          name="frecvență relativă")
            st.plotly_chart(f, width="stretch", key=f"t7b_se_fr_{mode}_{c['key']}")
    st.caption("Martorii pistei (Q5–Q6), biletele, scorurile pe anotimpuri și rangul lui G între universurile nule nu "
               "se portează. Pista SE649 rămâne închisă pe 6/49.")


# ---------------------------------------------------------------------------
# TU3-T7C — porturile DESCRIPTIVE CS (tab 11) și PL (tab 12) în 5/40 și Joker (PROTOCOL_TU3_T7C.md; sigilat în
# SIGILIU_TU3_T7C.json ÎNAINTE de cod; protocolul comun PROTOCOL_TU3_T7A §3). D3 = (b): fără verdict, fără scor, fără
# bilete, fără variante, fără clasări; verdictele pistelor 6/49 NU se transferă. S6: tab 11 = CS, tab 12 = PL (bila
# Joker: rețeaua de spin nu are obiect pentru κ = 1). Algoritmii: tu3/porturi_712.py (secțiunea TU3-T7C, copiați literal
# din cs649/pl649, care NU se importă). Calcul clasic pe CPU: CS exact în Q (fractions) + NumPy float64; PL NumPy
# complex128. Vederea 6/49 (app.py + pl649/ui_pl649.py) neschimbată. positive_claims_allowed=false.
# ---------------------------------------------------------------------------
T7C_PORTED = {10: "cs", 11: "pl"}
T7C_NOTE = ("DESCRIPTIV · fără verdict · fără scor · fără bilete · fără variante · fără clasări · verdictul pistei 6/49 "
            "NU se transferă · calcul clasic pe CPU (CS: exact în Q + NumPy float64; PL: NumPy complex128) · "
            "positive_claims_allowed=false")


@st.cache_data(show_spinner=False, max_entries=4)
def t7c_cs(mode: str, src_key: str, _ds) -> list:
    """Portul CS pe setul LIVE al modului (fazele indicelui zilei mod 3, 5, 7); cheia cache-ului = (mod, sha LIVE)."""
    import porturi_712 as PT
    return PT.describe_cs(_t7a_components(_ds))


@st.cache_data(show_spinner=False, max_entries=4)
def t7c_pl(mode: str, src_key: str, _ds) -> list:
    """Portul PL pe setul LIVE al modului (starea finală a rețelei de spin); cheia cache-ului = (mod, sha LIVE)."""
    import porturi_712 as PT
    return PT.describe_pl(_t7a_components(_ds))


def _t7c_identity_line(kind: str) -> str:
    import porturi_712 as PT
    li = PT.latest_identity_t7c()
    if not li:
        return "Testul de identitate pe 6/49: raport absent (tu3/rezultate/T7C/)."
    return (f"Testul de identitate pe 6/49 (portul reproduce cifrele pistei originale): {li.get(kind.upper())} · "
            f"{li['file']}.")


def t7c_port(t_idx: int, tab, mode: str, ds, key: str, ctx: dict) -> bool:
    """True dacă tabul are port T7C (11 = CS, 12 = PL) și a fost randat; False ⇒ tabul rămâne NEAPLICABIL, ca înainte."""
    kind = T7C_PORTED.get(t_idx)
    if kind is None:
        return False
    with tab:
        st.markdown(f"### {TAB_LABELS[t_idx]} · port DESCRIPTIV · {INFO[mode]['name']}")
        st.caption(T7C_NOTE)
        try:
            (t7c_render_cs if kind == "cs" else t7c_render_pl)(mode, ds, key, ctx)
        except Exception as exc:  # noqa: BLE001 — eroare explicită, fără comutare tăcută
            st.error(f"Portul {kind.upper()} a refuzat rularea: {type(exc).__name__}: {exc}")
    return True


def t7c_render_cs(mode: str, ds, key: str, ctx: dict) -> None:
    card, fig, NEON = ctx["card"], ctx["fig"], ctx["NEON"]
    st.caption("Modelul pistei CS649 (propensiune = p0 + efect principal + efectele fazei indicelui zilei de extragere "
               "modulo 3, 5 și 7; așteptarea ajustată Bayes liniară prin ecuațiile Henderson 16 × 16, exact în Q), "
               "copiat literal și parametrizat în (n, κ), cu hiperparametrii relativi ai pistei neschimbați (τa = p0/20, "
               "τ = p0/4, p0 = κ/n). Fazele vin numai din indicele zilei, nu din etichete; premisa fizică (rotația "
               "seturilor de bile/urnelor) rămâne NEVERIFICATĂ. Aici, pe toate extragerile setului LIVE "
               f"{INFO[mode]['name']} (sha {key[:12]}…): extragerile pe nivel, ponderile v ale modelului pentru indicele "
               "zilei care urmează (cât cântărește fiecare nivel), statisticile G ale tabelelor bilă × fază (fără "
               "p-valoare, fără universuri nule) și frecvențele relative pe fază — o descriere a istoriei, nu o "
               "prognoză; fără propensiuni pe bile, fără bilete. " + _t7c_identity_line("cs"))
    with st.spinner("Port CS pe CPU…"):
        comps = t7c_cs(mode, key, ds)
    for c in comps:
        st.markdown(f"**{c['component']}** · n = {c['N']} · κ = {c['kappa']} · {c['n_draws']} extrageri · "
                    f"{c['n_steps']} zile")
        m = st.columns(4)
        m[0].markdown(card("extrageri · zile", f"{c['n_draws']} · {c['n_steps']}"), unsafe_allow_html=True)
        m[1].markdown(card("G3 · G5 · G7 (bilă × fază)", f"{c['G3']:.1f} · {c['G5']:.1f} · {c['G7']:.1f}", "amber"),
                      unsafe_allow_html=True)
        m[2].markdown(card("fazele indicelui K (mod 3, 5, 7)", " · ".join(str(x) for x in c["next_phases"]), "mag"),
                      unsafe_allow_html=True)
        m[3].markdown(card("control exact Σ p̂ = κ în Q", "DA" if c["sum_exact_ok"] else "NU",
                           "lime" if c["sum_exact_ok"] else "mag"), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            f = fig(title=f"PONDERILE v ALE CELOR 16 NIVELURI (INDICELE {c['next_index']}) · {c['component'].upper()} · "
                          "DESCRIPTIV", xaxis_title="nivel (a = efect principal; KPrR = perioada P, faza R)",
                    yaxis_title="v = M⁻¹ z*", height=340)
            f.add_bar(x=c["level_names"], y=c["v_next"], marker=dict(color=NEON["cyan"]), name="v",
                      text=[str(x) for x in c["n_per_level"]], hovertemplate="%{x}: v = %{y:.3e} · n = %{text}")
            st.plotly_chart(f, width="stretch", key=f"t7c_cs_v_{mode}_{c['key']}")
        with c2:
            f = fig(title=f"FRECVENȚA RELATIVĂ PE FAZĂ (c / (n_faza p0) − 1) · {c['component'].upper()}",
                    xaxis_title="bilă (ordine naturală)", yaxis_title="perioadă · fază", height=340)
            f.add_heatmap(z=c["freq_rel_phase"], x=list(range(1, c["N"] + 1)), y=c["phase_level_names"],
                          colorscale="RdBu", zmid=0.0, name="frecvență relativă")
            st.plotly_chart(f, width="stretch", key=f"t7c_cs_fr_{mode}_{c['key']}")
    st.caption("Martorii pistei (Q5–Q6, fixture-uri pe etichetele 1..49), biletele, scorurile pe faze și sensibilitatea "
               "nu se portează. Pista CS649 rămâne închisă pe 6/49.")


def t7c_render_pl(mode: str, ds, key: str, ctx: dict) -> None:
    card, fig, NEON = ctx["card"], ctx["fig"], ctx["NEON"]
    st.caption("Motorul pistei PL649 (rețea de spin pe perechile de bile co-extrase: spini j = n/2, spectrul de arie "
               "√(j(j+1)), conexiune SU(3) din impulsuri exp(iελ) orientate după vechime, buclele Wilson ale tuturor "
               "triunghiurilor printr-o înmulțire M·M, curbura pe nod κ și pe muchie ε), copiat literal și "
               "parametrizat în (n, κ), cu ε = π/32 neschimbat. Pista a rulat pe GPU în PyTorch; portul rulează pe CPU în "
               "NumPy complex128, cu impulsurile în forma închisă a pistei. Termenii LQG / Yang–Mills sunt inspirație "
               f"matematică. Aici, starea finală pe toate extragerile setului LIVE {INFO[mode]['name']} (sha "
               f"{key[:12]}…) — o descriere a istoriei co-extragerilor, nu o prognoză; fără legea π, fără bilete, fără "
               "variante energetice, fără anealer, fără comparații cu universuri nule. " + _t7c_identity_line("pl"))
    with st.spinner("Port PL pe CPU…"):
        comps = t7c_pl(mode, key, ds)
    for c in comps:
        st.markdown(f"**{c['component']}** · n = {c['N']} · κ = {c['kappa']} · {c['n_draws']} extrageri")
        if not c["applicable"]:
            st.markdown(f"Rețeaua de spin nu se aplică acestei componente: {c['reason']}.")
            continue
        h = c["holonomy"]
        m = st.columns(4)
        m[0].markdown(card("muchii cu spin", f"{c['links_spun']} / {c['links_total']}"), unsafe_allow_html=True)
        m[1].markdown(card("aria totală Σ√(j(j+1))", f"{c['area_total']:.2f}", "amber"), unsafe_allow_html=True)
        m[2].markdown(card("curbura κ (min–max)", f"{c['curvature_min']:.5f}–{c['curvature_max']:.5f}", "mag"),
                      unsafe_allow_html=True)
        m[3].markdown(card("eroarea de holonomie SU(3)", f"max {h['max_unitarity']:.1e} · "
                                                          f"{h['frac_links_err_gt_1e-12']:.0%} > 1e-12",
                           "lime" if h["frac_links_err_gt_1e-12"] == 0 else "mag"), unsafe_allow_html=True)
        N = c["N"]
        balls = list(range(1, N + 1))
        c1, c2 = st.columns(2)
        with c1:
            f = fig(title=f"CURBURA κ PE NOD (ORDINE NATURALĂ) · {c['component'].upper()} · DESCRIPTIV",
                    xaxis_title="bilă", yaxis_title="κ = 1 − Re tr(holonomie)/3 (medie ponderată)", height=340)
            f.add_bar(x=balls, y=c["curvature_node"], marker=dict(color=NEON["violet"]), name="κ")
            st.plotly_chart(f, width="stretch", key=f"t7c_pl_kappa_{mode}_{c['key']}")
        with c2:
            E = np.zeros((N, N))
            iu = np.triu_indices(N, 1)
            E[iu] = c["eps_edge"]
            E = E + E.T
            f = fig(title=f"CURBURA ε PE MUCHIE (N × N, ORDINE NATURALĂ) · {c['component'].upper()}",
                    xaxis_title="bilă", yaxis_title="bilă", height=340)
            f.add_heatmap(z=E.tolist(), x=balls, y=balls, colorscale="Plasma", name="ε")
            st.plotly_chart(f, width="stretch", key=f"t7c_pl_eps_{mode}_{c['key']}")
        spec = c["area_spectrum"]
        f = fig(title=f"SPECTRUL DE ARIE · MUCHII PE SPIN j = n/2 · {c['component'].upper()}",
                xaxis_title="spin j", yaxis_title="muchii", height=280)
        f.add_bar(x=[int(k) / 2 for k in spec], y=list(spec.values()), marker=dict(color=NEON["cyan"]), name="muchii")
        st.plotly_chart(f, width="stretch", key=f"t7c_pl_spec_{mode}_{c['key']}")
    st.caption("Legea π, biletul QUBO și cele 3 variante energetice, enumerarea, anealerul Higgs, monopolii XY, aria față "
               "de universurile nule și spuma 3D nu se portează (bilete, zgomot GPU nereproductibil pe CPU sau "
               "comparații cu uniformul). Pista PL649 rămâne închisă pe 6/49.")


# ---------------------------------------------------------------------------
# TU3-SR-R (S8) — verdictele rulării reale UNICE în taburile 4–5 (PROTOCOL_TU3_SR_R.md §4.1; sigilat în
# SIGILIU_TU3_SR_R.json ÎNAINTE de cod). NUMAI inserții: casetele „NERULAT” rămân în cod, se scriu într-un `st.empty()`
# și sunt înlocuite pe loc de blocul de verdict când `tu3/rezultate/SR/<joc>/START.json` există. Citire read-only a
# REZULTATE.json și VERIFICARE_SR.json (verificatorul separat). O detecție pe arhiva deja explorată NU este avantaj
# predictiv. Calcul clasic. positive_claims_allowed=false.
# ---------------------------------------------------------------------------
SR_RESULTS_DIR = HERE / "rezultate" / "SR"
SR_DISCLAIMER = ("Arhiva ÎNGHEȚATĂ este deja explorată (produs, porturi, grafice de frecvență): nu există set „nevăzut”. "
                 "D1 și D2 sunt teste EXPLORATORII, preînregistrate în PROTOCOL_TU3_SR §4; o detecție NU este avantaj "
                 "predictiv și nu se folosește pentru bilete; o confirmare ar cere date prospective separate și un "
                 "protocol nou. Dacă extragerile sunt uniforme și independente, istoricul nu oferă avantaj predictiv. "
                 "Calcul clasic. positive_claims_allowed=false.")


def sr_results_dir() -> Path:
    import os
    return Path(os.environ.get("QL649_SR_DIR") or SR_RESULTS_DIR)   # QL649_SR_DIR numai în teste (§4.1)


def sr_slot_open():
    """Deschide un `st.empty()` ca context activ: elementul următor (caseta „NERULAT”) se scrie în el."""
    import contextlib
    ph = st.empty()
    stack = contextlib.ExitStack()
    stack.enter_context(ph)
    return ph, stack


def sr_state(mode: str) -> dict:
    """Starea rulării reale a jocului: absentă / pornită fără rezultate / rezultate + starea verificării separate."""
    d = sr_results_dir() / mode
    s = {"dir": d, "start": (d / "START.json").is_file()}
    if not s["start"]:
        return s
    rz = d / "REZULTATE.json"
    if not rz.is_file():
        s["error"] = (f"Rularea reală {INFO[mode]['name']} a fost pornită (START.json există), dar REZULTATE.json "
                      "lipsește: incident (PROTOCOL_TU3_SR_R §6). Nicio rulare nouă fără decizia utilizatorului.")
        return s
    raw = rz.read_bytes()
    res = json.loads(raw)
    s["res"] = res
    s["rezultate_sha256"] = hashlib.sha256(raw).hexdigest()
    vf = d / "VERIFICARE_SR.json"
    if not vf.is_file():
        s["ver_state"] = "absent"
        return s
    v = json.loads(vf.read_text())
    s["ver"] = v
    if v.get("rezultate_sha256") != s["rezultate_sha256"] or v.get("predictions_sha256") != res.get("predictions_sha256"):
        s["ver_state"] = "mismatch"
    else:
        s["ver_state"] = "pass" if v.get("verdict") == "VERIFICARE_SR_PASS" else "fail"
    return s


def sr_render_status(s: dict) -> None:
    vs = s.get("ver_state")
    v = s.get("ver") or {}
    if vs == "pass":
        st.success(f"Verificat separat: VERIFICARE_SR_PASS (tu3/verifica_sr.py, recalcul NumPy independent; "
                   f"VERIFICARE_SR.json scris {v.get('written_utc')}; REZULTATE sha {s['rezultate_sha256'][:12]}…).")
    elif vs == "fail":
        bad = [c.get("id") for c in v.get("checks", []) if not c.get("pass")]
        st.error(f"Verificarea separată a dat VERIFICARE_SR_FAIL (verificări picate: {', '.join(bad) or '—'}). "
                 "Verdictele de mai jos sunt cele publicate de rularea unică și NU se modifică (PROTOCOL_TU3_SR_R §6).")
    elif vs == "mismatch":
        st.warning("Verificare separată nepotrivită: sha-ul REZULTATE/PREDICTII din VERIFICARE_SR.json diferă de "
                   "fișierele curente. Verdictele de mai jos NU sunt confirmate.")
    else:
        st.warning("Verificare separată absentă (VERIFICARE_SR.json lipsește): verdictele de mai jos nu sunt încă "
                   "confirmate de tu3/verifica_sr.py.")


def sr_render_d2(mode: str, s: dict, ctx: dict) -> None:
    card = ctx["card"]
    res = s["res"]
    d2 = res.get("D2", {})
    st.markdown(f"### 🌌 D2 — SCI pe istoria reală {INFO[mode]['name']} (rulare reală UNICĂ S8, arhiva ÎNGHEȚATĂ)")
    m = st.columns(4)
    m[0].markdown(card("verdict D2", str(d2.get("verdict")), "amber"), unsafe_allow_html=True)
    m[1].markdown(card("SCI = Σz/√K", f"{d2.get('SCI', float('nan')):+.4f}"), unsafe_allow_html=True)
    m[2].markdown(card("p empiric (α = 0.01)", f"{d2.get('p_empirical', float('nan')):.4f}", "mag"),
                  unsafe_allow_html=True)
    m[3].markdown(card("universuri nule MPS · K", f"{d2.get('M_null')} · {len(d2.get('z', {}))}", "lime"),
                  unsafe_allow_html=True)
    ind = (s.get("ver") or {}).get("d2_independent") or {}
    zi = ind.get("z", {})
    st.dataframe(pd.DataFrame([{"statistică": k, "z (S8)": float(z), "z (verificator, nul NumPy propriu)": zi.get(k)}
                               for k, z in (d2.get("z") or {}).items()]).style.format(precision=4),
                 width="stretch", hide_index=True)
    st.caption(f"Nulul S8: M = {d2.get('M_null')} universuri MPS (legea oficială: submulțimi uniforme"
               f"{' + bila uniformă independentă' if mode == 'joker' else ''}), sămânța {d2.get('seed')}, structura "
               f"reală de pași. Verificatorul: SCI {ind.get('SCI', float('nan')):+.4f}, p "
               f"{ind.get('p_empirical', float('nan')):.4f} ({ind.get('concordanta', '—')}). Descriptiv-statistic, "
               "nu o proprietate fizică a bilelor.")
    st.markdown(f'<div class="ql-warn">{SR_DISCLAIMER}</div>', unsafe_allow_html=True)


def sr_render_d1(mode: str, s: dict, ctx: dict) -> None:
    card, fig, NEON = ctx["card"], ctx["fig"], ctx["NEON"]
    res = s["res"]
    d1 = res.get("D1", {})
    comps = res.get("components", [])
    st.markdown(f"### ⏳ D1 — mersul înainte cauzal pe istoria reală {INFO[mode]['name']} + promovarea (6 porți)")
    m = st.columns(4)
    m[0].markdown(card("verdict D1", str(d1.get("verdict")), "amber"), unsafe_allow_html=True)
    m[1].markdown(card(f"p exact (α = {d1.get('alpha_each')} pe componentă)",
                       " · ".join(f"{p:.3g}" for p in d1.get("p_values", []))), unsafe_allow_html=True)
    m[2].markdown(card("verdict promovare", str(res.get("promotion")), "mag"), unsafe_allow_html=True)
    m[3].markdown(card("ținte (pași ≥ 100)", f"{comps[0].get('n_targets') if comps else '—'}", "lime"),
                  unsafe_allow_html=True)
    rows, grows = [], []
    for c in comps:
        u, t = c.get("urn", {}), c.get("total", {})
        T = int(c.get("n_targets", 0))
        rows.append({"componentă": u.get("name"), "ținte": T, "hits QL": t.get("hits_QL"), "hits B": t.get("hits_B"),
                     "hits R": t.get("hits_R"), "E_U·T": float(u.get("E_U", 0.0)) * T, "exces QL": t.get("excess_QL"),
                     "τ": u.get("tau"), "log QL−U": t.get("log_QL", 0.0) - t.get("log_U", 0.0),
                     "log QL−B": t.get("log_QL", 0.0) - t.get("log_B", 0.0), "Brier QL": t.get("brier_QL"),
                     "Brier U": t.get("brier_U"), "porți trecute": f"{c.get('gates_passed')}/6",
                     "p exact": c.get("p_exact_hits_QL_ge")})
        for gg in c.get("gates", []):
            grows.append({"componentă": u.get("name"), "poarta": gg.get("gate"), "regula": gg.get("rule"),
                          "trecută": "DA" if gg.get("pass") else "nu"})
    if rows:
        st.dataframe(pd.DataFrame(rows).style.format(precision=4), width="stretch", hide_index=True)
        st.dataframe(pd.DataFrame(grows), width="stretch", hide_index=True)
    for c in comps:
        pt = c.get("per_target") or {}
        if not pt.get("hits_QL"):
            continue
        eu = float(c.get("urn", {}).get("E_U", 0.0))
        tt = np.arange(1, len(pt["hits_QL"]) + 1)
        f = fig(title=f"HITS CUMULATE MINUS E_U·t · {str(c.get('urn', {}).get('name')).upper()} (descriptiv, S8)",
                xaxis_title="țintă (cronologic)", yaxis_title="Σ hits − E_U·t", height=320)
        for nm, col in (("QL", NEON["cyan"]), ("B", NEON["amber"]), ("R", NEON["mag"])):
            f.add_scatter(x=tt, y=np.cumsum(np.asarray(pt[f"hits_{nm}"], dtype=float)) - eu * tt, mode="lines",
                          line=dict(color=col, width=2), name=nm)
        f.add_hline(y=0.0, line=dict(color=NEON["dim"], dash="dot"))
        st.plotly_chart(f, width="stretch", key=f"sr_cum_{mode}_{c.get('urn', {}).get('name')}")
    rs = res.get("resources") or {}
    th = rs.get("thermal") or {}
    st.caption(f"Rulare unică S8: start {res.get('start', {}).get('started_at_utc')} · final {res.get('finished_at_utc')} "
               f"· {res.get('seconds')} s · sursa înghețată sha {str(res.get('start', {}).get('source_sha256'))[:12]}… · "
               f"predicții sigilate înainte de scor sha {str(res.get('predictions_sha256'))[:12]}… · VRAM vârf rezervat "
               f"{(rs.get('peak_reserved_bytes') or 0) / 1e9:.2f} GB (plafon 6.2 GB) · T_max gardă {th.get('t_max_c')} °C "
               f"(țintă < 71: {th.get('temperature_target_met')}) · pauze {th.get('pauses')}.")
    st.markdown(f'<div class="ql-warn">{SR_DISCLAIMER}</div>', unsafe_allow_html=True)


def sr_slot_close(slot, mode: str, kind: str, ctx: dict) -> None:
    """Închide placeholder-ul; dacă rularea reală a jocului există, înlocuiește caseta cu blocul D2 / D1 + promovare."""
    ph, stack = slot
    stack.close()
    try:
        s = sr_state(mode)
    except Exception as exc:  # noqa: BLE001 — fișiere ilizibile ⇒ eroare afișată, fără calcul
        with ph.container():
            st.error(f"Rezultatele S8 {INFO[mode]['name']} nu pot fi citite: {type(exc).__name__}: {exc}")
        return
    if not s["start"]:
        return
    with ph.container():
        if "error" in s:
            st.error(s["error"])
            return
        sr_render_status(s)
        if kind == "D2":
            sr_render_d2(mode, s, ctx)
        else:
            sr_render_d1(mode, s, ctx)
