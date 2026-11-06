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
        st.info(f"SCI (indicele de coerență structurală) pe istoria reală {info['name']}: NERULAT — `validare.py` este "
                "definit pe 6/49; orice statistică nouă pe istoria reală cere protocol separat, sigilat înainte.")
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
        st.info(f"Backtestul cauzal pe istoria reală {info['name']} este NERULAT: cere un protocol separat, sigilat înainte "
                "(TU3-P1 §0). Arhiva este deja explorată; nu există set „nevăzut”.")
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
        with tabs[t_idx]:
            st.markdown(f"### {TAB_LABELS[t_idx]}")
            st.info(f"NEAPLICABIL în modul {info['name']}: pista {track} (protocol {proto}) a fost definită, calificată sau "
                    f"rulată numai pe Loto 6/49 și este închisă. În acest mod nu există protocol propriu — fără calcul. "
                    "Orice transpunere cere un protocol nou, sigilat înainte.")
            st.caption(f"Raportul pistei (6/49): {report} · comută pe 🌌 6/49 din sidebar pentru afișarea ei.")

    st.markdown(f'<p class="ql-sub" style="text-align:center;margin-top:30px">TU3 v3.0 · {info["name"]} · protocol '
                f'TU3-{info["power"]} · torch {torch.__version__} · sursă LIVE {R["source_sha256"][:12]}… · calcul clasic · '
                'positive_claims_allowed=false</p>', unsafe_allow_html=True)
