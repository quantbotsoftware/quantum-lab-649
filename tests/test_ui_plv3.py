"""Teste End-to-End UI pentru integrarea motorului PL-V3 (`pl_v3/ui_pl_v3.py` + `tu3/ui_tu3.py`).

Verifică:
1. Sigiliul pre-cod `pl_v3/SIGILIU_PLV3_UI.json`, lanțul `inlocuiri_tu3/v1` și inserțiile pure în `tu3/ui_tu3.py`.
2. Politica implicită a comutatorului `plv3_active` (`True` pe Desktop normal, `False` sub `fast` / `protocol` / `pytest`).
3. Randarea completă `AppTest` cu `PL-V3` activ pe toate cele 3 moduri (`649`, `540`, `joker`):
   - eticheta onestă permanentă (`PLV3_NO_PROMOTION_EXPLORATORY`, `0 / 6 porți`, `positive_claims_allowed=false`),
   - cele 3 carduri `.ql-variant` (`α`, `β`, `γ`) cu `.ql-ball` + `.ql-ball.jk` la Joker, `ln W(σ)`, `P(σ)`, `det G`,
   - cele 6 carduri KPI (`NUMERE DISTINCTE ACOPERITE`, `NUCLEU DETERMINIST`, `EROARE CAUCHY-BINET`,
     `GAP FUNDAMENTAL ΔlnW`, `TIMP MOTOR GPU`, `VRAM`),
   - telemetria `CALIFICARE Q1–Q6` (`6/6 PASS`), `WALK-FORWARD ARHIVĂ LIVE (G1–G6: 0/6)`, curba Plotly `log10(E_s)`,
     vorticitatea `‖J_curl‖²/‖J‖²`, diagrama Argand Ruelle, `S_vN` + distribuția celor 20 bile Joker,
     istoricul decontărilor automate live și `PROFIL GPU PE OPERATOR (secunde)`.
4. Eliberarea memoriei / `release_mode` la comutarea modului în sidebar.
5. Sincronizarea `live_key(mode)` / `get_or_advance_live(mode)` (`< 0.01 s` cache-hit, `< 0.35 s` la avans `CURRENT_LIVE.json`).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TU3 = ROOT / "tu3"
for _p in (str(ROOT), str(TU3)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from streamlit.testing.v1 import AppTest  # noqa: E402

import inlocuiri_tu3 as INL  # noqa: E402
import parser_multi as PM  # noqa: E402
import ui_tu3  # noqa: E402
from pl_v3.ui_pl_v3 import HONEST_LABEL  # noqa: E402
from pl_v3.walkforward import (  # noqa: E402
    _write_temp_live_version,
    get_or_advance_live,
    warmup_realtime_kernels,
)

RULES = {"649": (49, 6, None), "540": (40, 5, None), "joker": (45, 5, 20)}


def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _not_writable(p: Path) -> bool:
    return (os.stat(p).st_mode & 0o222) == 0


def _run_plv3_app(tmp_path: Path, mode: str = "649") -> AppTest:
    os.environ["QL649_SEAL_DIR"] = str(tmp_path / "sigilii")
    os.environ["QL649_CONFIG"] = "fast"
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at.session_state["tu3_mode"] = mode
    at.session_state["plv3_active"] = True
    at.run()
    return at


def _variant_cards(at: AppTest) -> list[str]:
    return [m.value for m in at.main.markdown if 'class="ql-variant' in m.value]


def _kpi_cards(at: AppTest) -> list[str]:
    return [m.value for m in at.main.markdown if 'class="ql-card"' in m.value]


def _all_main_text(at: AppTest) -> str:
    chunks: list[str] = []
    for kind in ("markdown", "caption", "warning", "info", "error"):
        chunks.extend(el.value for el in getattr(at.main, kind))
    return "\n".join(chunks)


def _plot_specs(at: AppTest) -> list[dict]:
    return [json.loads(el.proto.spec) for el in at.main.get("plotly_chart")]


def _plot_titles(specs: list[dict]) -> list[str]:
    titles: list[str] = []
    for sp in specs:
        t = sp.get("layout", {}).get("title", {})
        titles.append(str(t.get("text") if isinstance(t, dict) else t))
    return titles


def test_plv3_ui_seal_and_insertions():
    proto_p = ROOT / "pl_v3" / "PROTOCOL_PLV3_UI.md"
    seal_p = ROOT / "pl_v3" / "SIGILIU_PLV3_UI.json"
    assert proto_p.is_file() and seal_p.is_file()
    assert _not_writable(proto_p) and _not_writable(seal_p)

    seal = json.loads(seal_p.read_text(encoding="utf-8"))
    assert seal["file"] == "PROTOCOL_PLV3_UI.md"
    assert seal["sha256"] == _sha_file(proto_p)
    assert seal["replacement_mechanism"] == "inlocuiri_tu3/v1"
    assert seal["code_files_present"] == []
    assert seal["results_present"] is False
    assert seal["positive_claims_allowed"] is False
    assert set(seal["replaceable"]) == {"tu3/ui_tu3.py", "tests/test_scor_real.py"}

    # Inserții pure în tu3/ui_tu3.py față de copia de referință pre-TU4-UI
    base_ui = (ROOT / "tests" / "baseline" / "ui_tu3_pre_tu4ui.py").read_text(encoding="utf-8").splitlines()
    cur_ui = (TU3 / "ui_tu3.py").read_text(encoding="utf-8").splitlines()
    opcodes = difflib.SequenceMatcher(a=base_ui, b=cur_ui, autojunk=False).get_opcodes()
    assert {tag for tag, *_ in opcodes} <= {"equal", "insert"}

    rep = INL.verify_all(ROOT)
    assert rep["ok"] is True, rep
    plv3_recs = [r for r in INL.load_records(ROOT)[0] if r["seal"] == "pl_v3/SIGILIU_PLV3_UI.json"]
    assert len(plv3_recs) >= 1


def test_plv3_toggle_default_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert ui_tu3.plv3_default_on(env={}, in_pytest=False) is True
    assert ui_tu3.plv3_default_on(env={"QL649_CONFIG": "fast"}, in_pytest=False) is False
    assert ui_tu3.plv3_default_on(env={"QL649_UI_PROTOCOL": "1"}, in_pytest=False) is False
    assert ui_tu3.plv3_default_on(env={}, in_pytest=True) is False

    # Simulare lansare Desktop normală (fără QL649_CONFIG=fast): PL-V3 pornește activ implicit
    monkeypatch.setenv("QL649_SEAL_DIR", str(tmp_path / "sigilii"))
    monkeypatch.delenv("QL649_CONFIG", raising=False)
    monkeypatch.delenv("QL649_UI_PROTOCOL", raising=False)
    monkeypatch.setenv("QL649_PLV3_DESKTOP_SIM", "1")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    tg = [t for t in at.sidebar.toggle if t.key == "plv3_active"]
    assert len(tg) == 1 and tg[0].value is True
    assert HONEST_LABEL in _all_main_text(at)
    assert len(_variant_cards(at)) == 3


@pytest.mark.parametrize("mode", ["649", "540", "joker"])
def test_plv3_apptest_all_modes(tmp_path: Path, mode: str):
    at = _run_plv3_app(tmp_path, mode=mode)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.main.error

    txt = _all_main_text(at)
    assert HONEST_LABEL in txt
    assert "positive_claims_allowed=false" in txt
    assert "0 / 6 porți" in txt

    # Verificăm cele 3 carduri principale (α, β, γ)
    cards = _variant_cards(at)
    assert len(cards) == 3
    expected_titles = (
        "VARIANTA 1 · STARE FUNDAMENTALĂ α",
        "VARIANTA 2 · EXCITATĂ ORTOGONALĂ β",
        "VARIANTA 3 · EXCITATĂ ORTOGONALĂ γ",
    )
    n_max, k_req, m_jok = RULES[mode]
    live_ref = get_or_advance_live(mode)
    for idx, (card_html, title_req) in enumerate(zip(cards, expected_titles)):
        assert f'class="ql-variant v{idx + 1}"' in card_html
        assert title_req in card_html
        assert "ln W(σ) =" in card_html
        assert "P(σ) =" in card_html
        assert "det G =" in card_html

        main_balls = [int(x) for x in re.findall(r'class="ql-ball">(\d+)<', card_html)]
        jk_balls = [int(x) for x in re.findall(r'class="ql-ball jk">(\d+)<', card_html)]
        assert main_balls == [int(x) for x in live_ref["variants"][idx]["ticket"]]
        assert len(main_balls) == k_req and len(set(main_balls)) == k_req
        assert all(1 <= b <= n_max for b in main_balls)
        if m_jok is None:
            assert jk_balls == []
        else:
            assert len(jk_balls) == 1 and 1 <= jk_balls[0] <= m_jok
            assert jk_balls[0] == int(live_ref["variants"][idx]["joker"])

    # Verificăm cele 6 carduri KPI sub variante
    kpis_joined = "\n".join(_kpi_cards(at))
    for kpi_label in (
        "NUMERE DISTINCTE ACOPERITE",
        "NUCLEU DETERMINIST",
        "EROARE CAUCHY-BINET",
        "GAP FUNDAMENTAL ΔlnW",
        "TIMP MOTOR GPU",
        "VRAM",
        "FRACȚIE VORTICITATE ‖J_curl‖²/‖J‖²",
    ):
        assert kpi_label in kpis_joined, f"Lipsește KPI {kpi_label} pe modul {mode}"

    # Verificăm secțiunile Q1-Q6, G1-G6, decontările live și graficele Plotly
    assert "CALIFICARE Q1–Q6 (6/6 PASS" in txt
    assert "WALK-FORWARD ARHIVĂ LIVE (G1–G6: 0/6" in txt
    assert "ISTORICUL DECONTĂRILOR AUTOMATE LIVE" in txt
    assert len(at.main.dataframe) >= 4  # G1-G6, ferestre, Q1-Q6, istoric decontări

    specs = _plot_specs(at)
    titles = _plot_titles(specs)
    assert any("E-PROCESUL DEFENSIV VILLE" in t and "log10(E_s)" in t for t in titles)
    assert any("DIAGRAMA ARGAND RUELLE" in t for t in titles)
    assert any(t == "PROFIL GPU PE OPERATOR (secunde)" for t in titles)

    if mode == "joker":
        assert "ENTROPIE ÎNCURCARE S_vN" in kpis_joined
        jok_charts = [sp for sp, t in zip(specs, titles) if "DISTRIBUȚIA CELOR 20 BILE JOKER" in t]
        assert len(jok_charts) == 1
        assert len(jok_charts[0]["data"][0]["x"]) == 20


def test_plv3_mode_switch_releases_vram(tmp_path: Path):
    os.environ["QL649_SEAL_DIR"] = str(tmp_path / "sigilii")
    os.environ["QL649_CONFIG"] = "fast"
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at.run()
    at.sidebar.toggle(key="plv3_active").set_value(True).run()
    assert not at.exception

    at.sidebar.selectbox(key="tu3_mode").set_value("540").run()
    assert not at.exception
    at.sidebar.selectbox(key="tu3_mode").set_value("joker").run()
    assert not at.exception
    at.sidebar.selectbox(key="tu3_mode").set_value("649").run()
    assert not at.exception

    rel_log = at.session_state["tu3_release_log"]
    transitions = [(ev["from"], ev["to"]) for ev in rel_log]
    assert ("649", "540") in transitions
    assert ("540", "joker") in transitions
    assert ("joker", "649") in transitions


def test_plv3_live_sync_latency_and_incremental_ui(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    warmup_realtime_kernels()
    # 1. Cache-hit sub 0.01 s pe arhiva LIVE reală
    for m in ("649", "540", "joker"):
        _ = get_or_advance_live(m)  # încălzire pagină OS
        t0 = time.perf_counter()
        res_hit = get_or_advance_live(m)
        dt_hit = time.perf_counter() - t0
        assert res_hit["cache_hit"] is True
        assert dt_hit < 0.01, f"Cache-hit {m} a durat {dt_hit:.5f}s >= 0.01s"

    # 2. Avans incremental CURRENT_LIVE.json (ΔS = 1) < 0.35 s + randare istoric decontări live în UI
    raw_full: dict[str, list[str]] = {}
    lines_prev: dict[str, list[str]] = {}
    for m in ("649", "540", "joker"):
        src_p, _ = PM.resolve_live(m)
        lns = [ln for ln in src_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        raw_full[m] = lns
        last_dt = json.loads(lns[-1])["draw_date"]
        lines_prev[m] = [ln for ln in lns if json.loads(ln)["draw_date"] < last_dt]

    live_sbx = tmp_path / "live_sbx"
    deriv_sbx = tmp_path / "deriv_sbx"
    cache_sbx = tmp_path / "cache_sbx"

    _write_temp_live_version(live_sbx, "v_s_minus_1", lines_prev)
    _ = get_or_advance_live("540", live_root=live_sbx, deriv_root=deriv_sbx, cache_dir=cache_sbx, force_rebuild=True)

    _write_temp_live_version(live_sbx, "v_s_now", raw_full)
    t_adv0 = time.perf_counter()
    res_adv = get_or_advance_live("540", live_root=live_sbx, deriv_root=deriv_sbx, cache_dir=cache_sbx)
    dt_adv = time.perf_counter() - t_adv0
    assert res_adv["cache_hit"] is False and res_adv["delta_steps"] == 1
    assert dt_adv < 0.35, f"Avansul ΔS=1 pe 540 a durat {dt_adv:.4f}s >= 0.35s"
    assert len(res_adv["settled_new_draws"]) >= 1

    monkeypatch.setenv("QL649_SEAL_DIR", str(tmp_path / "sigilii"))
    monkeypatch.setenv("QL649_CONFIG", "fast")
    monkeypatch.setenv("QL649_PLV3_LIVE_ROOT", str(live_sbx))
    monkeypatch.setenv("QL649_PLV3_DERIV_ROOT", str(deriv_sbx))
    monkeypatch.setenv("QL649_PLV3_CACHE_DIR", str(cache_sbx))

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at.session_state["tu3_mode"] = "540"
    at.session_state["plv3_active"] = True
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "extrageri decontate automat incremental peste checkpoint" in _all_main_text(at)
