"""Tabul 12 „🌌 Orizontul evenimentelor (PL649)” — produsul UI v2.0 (PREINREGISTRARE_PL649.md §9).

Read-only față de cercetare: afișează artefactele PL649 (calificare, backtest unic, verificare, descriptiv) și
starea finală precalculată (`pl649.py --final` → rezultate/final/FINAL.json); butonul de recalculare rulează
motorul pl_core pe GPU în sesiune (fără a scrie artefacte de cercetare). Calcul clasic; positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import torch

PL_DIR = Path(__file__).resolve().parent
RES = PL_DIR / "rezultate"


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _spinfoam_figure(final: dict, NEON: dict, layout: dict) -> go.Figure:
    frames_src = final["frames"]
    top = final["top_edges"][:40]
    vt0 = frames_src[0]["V_total"] or 1.0

    def traces(fr, k):
        X = np.asarray(fr["xyz"])
        scale = (fr["V_total"] / vt0) ** (1 / 3)                       # dilatare/contracție cu volumul-proxy
        X = X * scale
        A = np.asarray(fr["A"])
        kap = np.asarray(fr["kappa"])
        size = 6 + 16 * (A - A.min()) / max(1e-12, A.max() - A.min())
        ex, ey, ez = [], [], []
        for e in top:
            a, b = e["a"] - 1, e["b"] - 1
            ex += [X[a, 0], X[b, 0], None]
            ey += [X[a, 1], X[b, 1], None]
            ez += [X[a, 2], X[b, 2], None]
        return [go.Scatter3d(x=ex, y=ey, z=ez, mode="lines", line=dict(color=NEON["mag"], width=2), opacity=0.45,
                             hoverinfo="skip", name="muchii cu curbură ε maximă"),
                go.Scatter3d(x=X[:, 0], y=X[:, 1], z=X[:, 2], mode="markers+text", text=[str(i + 1) for i in range(49)],
                             textfont=dict(color=NEON["text"], size=9),
                             marker=dict(size=size, color=kap, colorscale="Plasma", cmin=float(kap.min()),
                                         cmax=float(kap.max()), colorbar=dict(title="κ", thickness=10),
                                         line=dict(color=NEON["cyan"], width=0.5)),
                             hovertemplate="bila %{text}<br>κ=%{marker.color:.5f}<extra></extra>", name="noduri (arie A)")]
    n = len(frames_src)
    cams = [dict(eye=dict(x=1.8 * math.cos(2 * math.pi * i / n), y=1.8 * math.sin(2 * math.pi * i / n), z=0.7))
            for i in range(n)]
    f = go.Figure(data=traces(frames_src[-1], n - 1),
                  frames=[go.Frame(data=traces(fr, i), name=str(fr["step"]), layout=dict(scene_camera=cams[i]))
                          for i, fr in enumerate(frames_src)])
    f.update_layout(**{k: v for k, v in layout.items() if k not in ("xaxis", "yaxis")}, height=620,
                    title="SPUMA DE SPIN · ultimele tranziții (extrageri) · poziții = vectori proprii 2–4 ai Laplacianului (GPU)",
                    scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
                               bgcolor="rgba(4,1,11,1)", camera=cams[-1]),
                    showlegend=False,
                    updatemenus=[dict(type="buttons", showactive=False, x=0.02, y=0.02,
                                      buttons=[dict(label="▶ rotație + tranziții", method="animate",
                                                    args=[None, dict(frame=dict(duration=350, redraw=True), fromcurrent=True,
                                                                     transition=dict(duration=200), mode="immediate")]),
                                               dict(label="⏸", method="animate",
                                                    args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])])
    return f


def _singularity_html(variants: list[dict], NEON: dict) -> str:
    cards = []
    for i, v in enumerate(variants):
        balls = "".join(f'<span class="pl-ball">{b}</span>' for b in v["ticket"])
        cards.append(f'<div class="pl-sing"><div class="pl-sing-k">VARIANTA {i + 1} · E = {v["E"]:+.4f}</div>'
                     f'<div>{balls}</div></div>')
    css = (f"<style>.pl-sing{{background:#000;border:2px solid {NEON['lime']};border-radius:10px;padding:14px 18px;"
           f"margin:8px 0;box-shadow:0 0 22px {NEON['lime']}55}}"
           f".pl-sing-k{{color:{NEON['lime']};font-weight:700;letter-spacing:2px;font-size:13px;margin-bottom:8px}}"
           f".pl-ball{{display:inline-block;width:52px;height:52px;line-height:52px;margin:4px;border-radius:50%;"
           f"background:#fff;color:#000;font-weight:900;font-size:22px;text-align:center;"
           f"box-shadow:0 0 14px #fff}}</style>")
    return css + "".join(cards)


def render(st, card, fig, NEON, PLOT_LAYOUT, _round):
    st.markdown("### 🌌 Orizontul evenimentelor — rețea de spin · holonomii SU(3) · vid Higgs (PL649)")
    st.caption("Protocol PL649-P1 sigilat înainte de cod. Rețeaua de spin pe 49 de noduri (spini j = n/2, spectrul de arie "
               "√(j(j+1)), volum-PROXY), conexiune SU(3) din impulsuri exp(iελ) orientate după vechime, bucle Wilson ale "
               "tuturor celor 18.424 de triunghiuri printr-o înmulțire M·M pe GPU, curbură → lege; biletul = vidul QUBO "
               "certificat prin enumerarea COMPLETĂ a 13.983.816 bilete. Calcul CLASIC pe GPU; termenii LQG / Yang–Mills / "
               "Higgs sunt inspirație matematică, fără hardware cuantic sau avantaj cuantic. positive_claims_allowed=false.")
    q = _load(RES / "calificare" / "CALIFICARE.json")
    r = _load(RES / "backtest_unic" / "REZULTATE.json")
    v = _load(RES / "backtest_unic" / "VERIFICARE_INDEPENDENTA.json")
    final = st.session_state.get("pl_final_live") or _load(RES / "final" / "FINAL.json")

    m = st.columns(4)
    m[0].markdown(card("calificare PL649", f"{(q or {}).get('verdict', 'NERULATĂ').replace('_', ' ')} "
                                           f"{(q or {}).get('n_pass', '—')}/6",
                       "lime" if (q or {}).get("verdict") == "PL_QUALIFIED" else "mag"), unsafe_allow_html=True)
    m[1].markdown(card("backtest unic", (r or {}).get("verdict", "NERULAT").replace("_", " "), "amber"), unsafe_allow_html=True)
    m[2].markdown(card("porți trecute", f"{(r or {}).get('gates_passed', '—')} / 6", "mag"), unsafe_allow_html=True)
    m[3].markdown(card("verificare independentă", (v or {}).get("status", "—"),
                       "lime" if (v or {}).get("status") == "PASS" else "mag"), unsafe_allow_html=True)

    if st.button("⚡ Recalculează starea finală pe GPU acum (≈ 10–20 s)", key="pl_recompute"):
        sys.path.insert(0, str(PL_DIR))
        import pl649 as PLM  # noqa: E402
        with st.spinner("Rețea de spin → bucle Wilson → enumerare 13,98 M bilete → anealer Higgs 50.000 replici → Kuramoto…"):
            st.session_state["pl_final_live"] = PLM.final_product(save=False)
        final = st.session_state["pl_final_live"]

    if not final:
        st.info("Starea finală nu este încă precalculată (rulați `pl649.py --final` sau butonul de mai sus).")
    else:
        tl = final["telemetry"]
        st.markdown("#### 📡 Telemetrie gauge")
        t = st.columns(5)
        t[0].markdown(card("Planck Area Deviancy", f"{tl['planck_area_deviancy']:+.3e}",
                           "lime" if abs(tl["planck_area_z"]) < 2 else "mag"), unsafe_allow_html=True)
        t[1].markdown(card("arie totală / nul (z)", f"{tl['planck_area_z']:+.2f}σ", "amber"), unsafe_allow_html=True)
        he = tl["holonomy_error"]
        t[2].markdown(card("SU(3) holonomy error rate", f"{he['frac_links_err_gt_1e-12']:.2%} · max {he['max_unitarity']:.1e}",
                           "lime" if he["frac_links_err_gt_1e-12"] == 0 else "mag"), unsafe_allow_html=True)
        an = final["annealer"]
        t[3].markdown(card("anealer Higgs = vid exact", "DA" if an["agrees_with_exact_ground_state"] else "NU",
                           "lime" if an["agrees_with_exact_ground_state"] else "mag"), unsafe_allow_html=True)
        mo = final["monopoles_xy"]
        t[4].markdown(card("monopoli XY persistenți", f"{mo['persistent_monopoles']} / {mo['n_triangles']}", "cyan"),
                      unsafe_allow_html=True)
        vr = tl.get("vram") or {}
        if vr.get("cuda"):
            st.caption(f"VRAM la calcul: alocat {vr['allocated_MiB']:.0f} MiB · rezervat {vr['reserved_MiB']:.0f} MiB · vârf "
                       f"{vr['max_allocated_MiB']:.0f} MiB · liber {vr['free_MiB']:.0f}/{vr['total_MiB']:.0f} MiB · "
                       f"{vr['device']} ({vr['sm_count']} SM) · timp total {tl['seconds_total']:.1f} s · "
                       f"calculat {final['utc'][:19]}Z")
        if torch.cuda.is_available():
            alloc = torch.cuda.memory_allocated() / 2 ** 20
            st.progress(min(1.0, alloc / (torch.cuda.get_device_properties(0).total_memory / 2 ** 20)),
                        text=f"VRAM acum (proces UI): {alloc:,.0f} MiB · rezervat {torch.cuda.memory_reserved() / 2 ** 20:,.0f} MiB")

        st.markdown("#### 🕳 Singularitatea — EXACT 3 variante unice (minimele exacte ale energiei PL)")
        st.markdown(_singularity_html(final["variants"], NEON), unsafe_allow_html=True)
        st.caption("Varianta 1 = vidul QUBO certificat prin enumerarea completă; variantele 2–3 minimizează E + ρ·suprapunere "
                   "(ρ = 1/2) peste bilete noi. Sunt minimele unei energii definite în protocol, NU „puncte de colaps” cu "
                   "șanse mai mari: backtestul unic de mai jos nu a demonstrat niciun avantaj; dacă extragerile sunt uniforme "
                   "și independente, nicio funcție a istoricului nu ajută.")

        st.plotly_chart(_spinfoam_figure(final, NEON, PLOT_LAYOUT), width="stretch")

        tr = an["trajectory"]
        f = fig(title="ANEALER HIGGS · 50.000 REPLICI · RUPEREA SPONTANĂ A SIMETRIEI (μ² < 0)", xaxis_title="pas Langevin",
                yaxis_title="⟨|φ|⟩", height=300)
        f.add_scatter(x=[p["t"] for p in tr], y=[p["order_param"] for p in tr], mode="lines", name="⟨|φ|⟩",
                      line=dict(color=NEON["lime"], width=3))
        f.add_scatter(x=[p["t"] for p in tr], y=[p["mu2"] for p in tr], mode="lines", name="μ²",
                      line=dict(color=NEON["mag"], dash="dot"))
        st.plotly_chart(f, width="stretch")
        st.dataframe(pd.DataFrame([{"triunghi": "–".join(map(str, x["triangle"])), "sarcină": x["charge"],
                                    "persistență": round(x["persistence"], 3)} for x in mo["top"][:6]]),
                     width="stretch", hide_index=True)
        st.caption("„Monopolii cromodinamici” sunt vortexuri XY ale unui model Kuramoto pe rețeaua de spin (4096 replici, "
                   "zgomot termic); denumirea este metaforică, nu monopoli QCD.")

    if q:
        st.markdown("#### 🔬 Cercetare (read-only)")
        st.dataframe(pd.DataFrame([{"calificare": k, "rezultat": "PASS" if q[k]["pass"] else "FAIL",
                                    "detalii": json.dumps(_round({kk: vv for kk, vv in q[k].items()
                                                                  if kk not in ("pass", "checkpoints", "enumeration")}),
                                                          ensure_ascii=False)[:220]}
                                   for k in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6")]), width="stretch", hide_index=True)
    if r:
        tt = r["total"]
        st.dataframe(pd.DataFrame([{"poartă": g["gate"], "cerință": g["rule"], "rezultat": "PASS" if g["pass"] else "FAIL",
                                    "valoare": json.dumps(_round(g["value"]), ensure_ascii=False)} for g in r["gates"]]),
                     width="stretch", hide_index=True)
        f = fig(title="BACKTEST UNIC · HITS PE 2495 DE ȚINTE (U AȘTEPTAT ≈ 1833)", xaxis_title="model", yaxis_title="hits",
                height=300)
        f.add_bar(x=["PL (vid QUBO)", "top-6 π", "B", "R"], y=[tt["hits_PL"], tt["hits_PI6"], tt["hits_B"], tt["hits_R"]],
                  marker=dict(color=[NEON["lime"], NEON["cyan"], NEON["mag"], NEON["amber"]]))
        st.plotly_chart(f, width="stretch")
    nul = _load(RES / "descriptiv" / "NUL_LEGE_1024.json")
    if nul and r:
        lu = np.array([x["logPL_U"] for x in nul["rows"]])
        f = fig(title=f"{len(lu)} UNIVERSURI NULE PE GPU · logPL − logU (linia = valoarea reală)", xaxis_title="logPL − logU",
                yaxis_title="universuri", height=280)
        f.add_histogram(x=lu, marker=dict(color=NEON["violet"]))
        f.add_vline(x=r["total"]["log_PL"] - r["total"]["log_U"], line=dict(color=NEON["lime"], width=3))
        st.plotly_chart(f, width="stretch")
    st.caption("PL649-P1 · rezultat exploratoriu pe o arhivă deja explorată; nu demonstrează avantaj · raport: "
               "pl649/RAPORT_PL649.md")
