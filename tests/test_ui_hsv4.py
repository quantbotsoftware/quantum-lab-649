"""Teste End-to-End UI pentru integrarea motorului HS-V4 (`hs_v4/ui_hs_v4.py` + `tu3/ui_tu3.py`).

Verifică:
1. Sigiliile `0444` (`SIGILIU_PROTOCOL_HSV4.json` și `SIGILIU_HSV4_UI.json`), lanțul `inlocuiri_tu3/v1` și
   inserțiile pure în `tu3/ui_tu3.py`.
2. Integritatea artefactelor RO (`CALIFICARE_Q.json`, `WALKFORWARD_RO.json`, `ABLATIE_RO.json`, `hs_v4/cache/`) și
   Internațional (`INTERNATIONAL_RNG_EVAL.json`, `PROVENIENTA_INTL.json`, curbele `.npz`).
3. Politica implicită a comutatorului `hsv4_active` și coexistența fără interferențe cu `TU3`, `TU4` și `PL-V3`.
4. Randarea `AppTest` pe toate cele 3 moduri RO (`649`, `540`, `joker`) și pe tab-ul dedicat
   `🌍 Internațional & Extrageri Electronice Online` (loterii mecanice externe, RNG online, perechea `7/35`
   `HU Skandináv Lottó` `kézi` vs `gépi`, martorul de control negativ `O2`).
5. Încadrarea epistemică onestă (`positive_claims_allowed=false`, minime de energie / stări statistice, NU predicții)
   și absența oricăror afirmații comerciale sau predictive nepermise.
6. Eliberarea VRAM la comutarea modului și decontarea cauzală automată pe un sandbox `CURRENT_LIVE.json`.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
TU3 = ROOT / "tu3"
HSV4 = ROOT / "hs_v4"
for _p in (str(ROOT), str(TU3)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from streamlit.testing.v1 import AppTest  # noqa: E402

import inlocuiri_tu3 as INL  # noqa: E402
import parser_multi as PM  # noqa: E402
import ui_tu3  # noqa: E402
from hs_v4.ui_hs_v4 import HONEST_LABEL as HSV4_HONEST_LABEL  # noqa: E402
from hs_v4.walkforward import _write_temp_live_sandbox, get_or_advance_live  # noqa: E402
from pl_v3.ui_pl_v3 import HONEST_LABEL as PLV3_HONEST_LABEL  # noqa: E402

RO_RULES = {"649": (49, 6, None), "540": (40, 5, None), "joker": (45, 5, 20)}
INTL_TAB_LABEL = "🌍 Internațional & Extrageri Electronice Online"


def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _not_writable(p: Path) -> bool:
    return (os.stat(p).st_mode & 0o222) == 0


def _run_hsv4_app(tmp_path: Path, mode: str = "649", config_key: str | None = None) -> AppTest:
    os.environ["QL649_SEAL_DIR"] = str(tmp_path / "sigilii")
    os.environ["QL649_CONFIG"] = "fast"
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at.session_state["tu3_mode"] = mode
    at.session_state["hsv4_active"] = True
    if config_key is not None:
        at.session_state["hsv4_ro_config"] = config_key
    at.run()
    return at


def _variant_cards(at: AppTest) -> list[str]:
    return [m.value for m in at.main.markdown if 'class="ql-variant' in m.value]


def _kpi_cards(at: AppTest) -> list[str]:
    return [m.value for m in at.main.markdown if 'class="ql-card"' in m.value]


def _all_main_text(at: AppTest) -> str:
    chunks: list[str] = []
    for kind in ("markdown", "caption", "warning", "info", "error", "success"):
        chunks.extend(el.value for el in getattr(at.main, kind))
    return "\n".join(chunks)


def _all_df_text(at: AppTest) -> str:
    out: list[str] = []
    for df_el in at.main.dataframe:
        out.append(df_el.value.to_string())
    return "\n".join(out)


def test_hsv4_seals_and_pure_insertions():
    p_base = HSV4 / "PROTOCOL_HSV4.md"
    s_base = HSV4 / "SIGILIU_PROTOCOL_HSV4.json"
    p_ui = HSV4 / "PROTOCOL_HSV4_UI.md"
    s_ui = HSV4 / "SIGILIU_HSV4_UI.json"
    p_met = HSV4 / "date_meteo" / "PROVENIENTA_METEO.json"
    c_met = HSV4 / "date_meteo" / "bucuresti_era5_18h.jsonl"

    for fp in (p_base, s_base, p_ui, s_ui, p_met, c_met):
        assert fp.is_file(), fp
        assert _not_writable(fp), f"{fp} nu este sigilat 0444!"

    seal_base = json.loads(s_base.read_text(encoding="utf-8"))
    assert seal_base["sha256"] == _sha_file(p_base)
    assert seal_base["positive_claims_allowed"] is False

    seal_ui = json.loads(s_ui.read_text(encoding="utf-8"))
    assert seal_ui["protocol"] == "HSV4-UI"
    assert seal_ui["file"] == "PROTOCOL_HSV4_UI.md"
    assert seal_ui["sha256"] == _sha_file(p_ui)
    assert seal_ui["parent_seal"]["sha256"] == _sha_file(s_base)
    assert seal_ui["replacement_mechanism"] == "inlocuiri_tu3/v1"
    assert seal_ui["code_files_present"] == []
    assert seal_ui["results_present"] is False
    assert seal_ui["positive_claims_allowed"] is False
    assert set(seal_ui["replaceable"]) == {"tu3/ui_tu3.py", "tests/test_scor_real.py"}

    for rel, expected_sha in seal_ui["frozen_hashes"].items():
        fp = ROOT / rel
        assert fp.is_file() and _sha_file(fp) == expected_sha, f"Drift în fișier înghețat: {rel}"

    # Inserții strict aditive în tu3/ui_tu3.py față de toate copiile de referință
    cur_ui = (TU3 / "ui_tu3.py").read_text(encoding="utf-8").splitlines()
    for base_name in ("ui_tu3_pre_tu4ui.py", "ui_tu3_pre_t7a.py", "ui_tu3_pre_t7b.py", "ui_tu3_pre_l649.py"):
        bp = ROOT / "tests" / "baseline" / base_name
        if bp.is_file():
            base_lines = bp.read_text(encoding="utf-8").splitlines()
            opcodes = difflib.SequenceMatcher(a=base_lines, b=cur_ui, autojunk=False).get_opcodes()
            assert {tag for tag, *_ in opcodes} <= {"equal", "insert"}, base_name

    rep = INL.verify_all(ROOT)
    assert rep["ok"] is True, rep
    hsv4_recs = [r for r in INL.load_records(ROOT)[0] if r["seal"] == "hs_v4/SIGILIU_HSV4_UI.json"]
    assert len(hsv4_recs) == 1
    assert _not_writable(TU3 / "inlocuiri" / hsv4_recs[0]["_name"])


def test_hsv4_artifacts_ro_and_international_integrity():
    rez = HSV4 / "rezultate"
    cal = json.loads((rez / "CALIFICARE_Q.json").read_text(encoding="utf-8"))
    wf = json.loads((rez / "WALKFORWARD_RO.json").read_text(encoding="utf-8"))
    abl = json.loads((rez / "ABLATIE_RO.json").read_text(encoding="utf-8"))
    intl = json.loads((rez / "INTERNATIONAL_RNG_EVAL.json").read_text(encoding="utf-8"))
    prov_intl = json.loads((HSV4 / "date_intl" / "PROVENIENTA_INTL.json").read_text(encoding="utf-8"))

    assert cal["status"] == "HSV4_QUALIFIED" and cal["passed"] == 6 and cal["total"] == 6
    assert cal["positive_claims_allowed"] is False and cal["real_ro_archive_read"] is False

    for m in ("649", "540", "joker"):
        gm = wf["games"][m]
        assert gm["status"] == "HSV4_NO_PROMOTION_EXPLORATORY"
        assert gm["positive_claims_allowed"] is False
        assert gm["martingale_trajectory"]["guarantee_E_ge_050_verified"] is True
        assert set(abl["games"][m]["configs"]) == {"O1", "O1_O2", "O1_O4", "Full_HSV4"}
        for cfg_k in ("O1", "O1_O2", "O1_O4", "Full_HSV4"):
            t_npz = abl["games"][m]["configs"][cfg_k]["trajectory_npz"]
            npz_p = rez / (t_npz["file"] if isinstance(t_npz, dict) else str(t_npz))
            assert npz_p.is_file(), npz_p
            if isinstance(t_npz, dict) and "sha256" in t_npz:
                assert _sha_file(npz_p) == t_npz["sha256"]
            with np.load(npz_p, allow_pickle=False) as zf:
                assert float(zf["E_curve"].min()) >= 0.50 - 1e-12

    # Verificăm checkpoint-urile SHA-256 din hs_v4/cache/
    cache_dir = HSV4 / "cache"
    pts = sorted(cache_dir.glob("state_*.pt"))
    assert len(pts) >= 12
    for pt in pts:
        sha_sidecar = cache_dir / f"{pt.name}.sha256"
        assert sha_sidecar.is_file(), pt.name
        assert sha_sidecar.read_text(encoding="utf-8").split()[0] == _sha_file(pt)

    # Verificăm integritatea seturilor internaționale + RNG online + perechea Skandináv + martor O2
    assert _sha_file(HSV4 / "date_intl" / "PROVENIENTA_INTL.json") == intl["provenance_intl_sha256"]
    assert set(intl["mechanical_external"]) >= {
        "fr_loto",
        "hu_hatoslotto",
        "hu_otoslotto",
        "us_powerball",
        "hu_skandinav_mech",
    }
    assert set(intl["electronic_rng"]) >= {
        "fdj_eurodreams",
        "ny_take5",
        "ny_cash4life",
        "ny_pick10",
        "hu_skandinav_rng",
    }
    sk = intl["paired_skandinav_comparison"]
    assert sk["same_dates_verified"] is True and bool(sk["column_mapping_verified"])
    assert sk["evaluated_steps"] == 1312

    o2 = intl["o2_negative_control_summary"]
    assert o2["all_contracted"] is True and o2["all_E_ge_050"] is True
    assert len(o2["streams"]) == 5

    for gc, meta in prov_intl["datasets"].items():
        jf = ROOT / meta["jsonl_file"]
        assert jf.is_file() and _sha_file(jf) == meta["jsonl_sha256"], gc


def test_hsv4_toggle_default_policy_and_coexistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert ui_tu3.hsv4_default_on(env={}, in_pytest=False) is True
    assert ui_tu3.hsv4_default_on(env={"QL649_CONFIG": "fast"}, in_pytest=False) is False
    assert ui_tu3.hsv4_default_on(env={"QL649_UI_PROTOCOL": "1"}, in_pytest=False) is False
    assert ui_tu3.hsv4_default_on(env={"QL649_PLV3_DESKTOP_SIM": "1"}, in_pytest=False) is False
    assert ui_tu3.hsv4_default_on(env={}, in_pytest=True) is False
    assert ui_tu3.hsv4_default_on(env={"QL649_HSV4_ACTIVE": "1", "QL649_CONFIG": "fast"}, in_pytest=True) is True
    assert ui_tu3.hsv4_default_on(env={"QL649_HSV4_DESKTOP_SIM": "1"}, in_pytest=True) is True

    # 1. Simulare lansare Desktop normală -> HS-V4 activ automat
    monkeypatch.setenv("QL649_SEAL_DIR", str(tmp_path / "sigilii_desk"))
    monkeypatch.delenv("QL649_CONFIG", raising=False)
    monkeypatch.delenv("QL649_UI_PROTOCOL", raising=False)
    monkeypatch.delenv("QL649_PLV3_DESKTOP_SIM", raising=False)
    monkeypatch.setenv("QL649_HSV4_DESKTOP_SIM", "1")
    at_desk = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at_desk.run()
    assert not at_desk.exception, [e.value for e in at_desk.exception]
    assert at_desk.sidebar.toggle(key="hsv4_active").value is True
    assert HSV4_HONEST_LABEL in _all_main_text(at_desk)
    assert INTL_TAB_LABEL in [t.label for t in at_desk.tabs]

    # 2. Dezactivare HS-V4 sub pytest + fast -> modurile clasice TU3 (12 taburi) intacte
    monkeypatch.delenv("QL649_HSV4_DESKTOP_SIM", raising=False)
    monkeypatch.setenv("QL649_CONFIG", "fast")
    at_tu3 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at_tu3.session_state["tu3_mode"] = "540"
    at_tu3.run()
    assert not at_tu3.exception, [e.value for e in at_tu3.exception]
    assert at_tu3.sidebar.toggle(key="hsv4_active").value is False
    assert len(at_tu3.tabs) == 12

    # 3. Coexistență cu PL-V3 (când plv3_active=True și hsv4_active=False)
    at_plv3 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at_plv3.session_state["tu3_mode"] = "540"
    at_plv3.session_state["plv3_active"] = True
    at_plv3.run()
    assert not at_plv3.exception, [e.value for e in at_plv3.exception]
    assert PLV3_HONEST_LABEL in _all_main_text(at_plv3)

    # 4. Coexistență cu TU4 (tu4_prosp are prioritate de tribunal read-only chiar dacă hsv4_active=True)
    at_tu4 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at_tu4.session_state["tu3_mode"] = "649"
    at_tu4.session_state["hsv4_active"] = True
    at_tu4.session_state["tu4_prosp"] = True
    at_tu4.run()
    assert not at_tu4.exception, [e.value for e in at_tu4.exception]
    assert [t.label for t in at_tu4.tabs] == ["🔮 Predicție prospectivă"]


@pytest.mark.parametrize("mode", ["649", "540", "joker"])
def test_hsv4_apptest_ro_modes_and_ablation(tmp_path: Path, mode: str):
    n_pool, k_balls, m_joker = RO_RULES[mode]
    at = _run_hsv4_app(tmp_path, mode=mode)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.main.error, [e.value for e in at.main.error]

    tab_labels = [t.label for t in at.tabs]
    assert len(tab_labels) == 4
    assert INTL_TAB_LABEL in tab_labels

    txt = _all_main_text(at)
    df_txt = _all_df_text(at)
    assert HSV4_HONEST_LABEL in txt
    assert "HSV4_NO_PROMOTION_EXPLORATORY" in txt
    assert "positive_claims_allowed=false" in txt
    assert "minime de energie / stări statistice condiționate de istoric, NU predicții" in txt
    assert "fără promisiuni de câștig" in txt

    # În tabul 1 avem 3 carduri .ql-variant pentru RO + în tabul 4 avem 3 carduri .ql-variant pentru jocul internațional implicit (fr_loto)
    vcards = _variant_cards(at)
    assert len(vcards) == 6
    ro_cards = vcards[:3]
    for card_html in ro_cards:
        balls = [int(x) for x in re.findall(r'class="ql-ball">(\d+)<', card_html)]
        assert len(balls) == k_balls
        assert balls == sorted(set(balls))
        assert all(1 <= b <= n_pool for b in balls)
        jks = [int(x) for x in re.findall(r'class="ql-ball jk">(\d+)<', card_html)]
        if m_joker is not None:
            assert len(jks) == 1 and 1 <= jks[0] <= m_joker
        else:
            assert jks == []

    kpi_joined = "\n".join(_kpi_cards(at))
    for kpi_lbl in ("NUCLEU DETERMINIST", "ACOPERIRE DISTINCTĂ", "DET G₃ (JASTROW)", "MARTINGALA E_S", "MASA ABSTENȚIEI w₀"):
        assert kpi_lbl in kpi_joined

    # Verificăm prezența Q1–Q6, G1–G6, Ablație (O1, O1_O2, O1_O4, Full_HSV4), ERA5 și categorii
    for token in ("Q1", "Q6", "G1", "G6", "O1_O2", "O1_O4", "Full_HSV4", "ρ_air", "RH_2m", "ΔP_24h", "3+"):
        assert token in df_txt, token
    if mode == "joker":
        assert "+Joker" in df_txt

    # Comutare configurație ablație în sidebar pe 540
    if mode == "540":
        at.sidebar.selectbox(key="hsv4_ro_config").set_value("O1_O2").run()
        assert not at.exception, [e.value for e in at.exception]
        assert "O1_O2 — O1+O2" in _all_main_text(at)


def test_hsv4_international_tab_and_game_selector(tmp_path: Path):
    at = _run_hsv4_app(tmp_path, mode="649")
    assert not at.exception, [e.value for e in at.exception]

    txt = _all_main_text(at)
    df_txt = _all_df_text(at)

    # 1. Loterii mecanice externe + 2. Extrageri electronice online RNG
    for g_tok in (
        "fr_loto",
        "hu_hatoslotto",
        "hu_otoslotto",
        "us_powerball",
        "fdj_eurodreams",
        "ny_take5",
        "ny_cash4life",
        "ny_pick10",
    ):
        assert g_tok in df_txt, g_tok

    # 3. Comparația pereche HU Skandináv Lottó 7/35 (kézi vs gépi, 1312 pași)
    assert "HU Skandináv Lottó" in txt
    assert "1312" in txt
    assert "kézi sorsolás" in df_txt and "gépi sorsolás" in df_txt

    # 4. Martorul de control negativ O2 pe fluxurile pur electronice RNG
    assert "all_contracted=True" in txt and "all_E_ge_050=True" in txt

    # 5. Comutare selector joc internațional pe US Powerball (5/69 + 1/26) și NY Pick 10 (10/80)
    at.selectbox(key="hsv4_intl_game").set_value("us_powerball").run()
    assert not at.exception, [e.value for e in at.exception]
    pb_cards = _variant_cards(at)[3:]
    assert len(pb_cards) == 3
    pb_balls = [int(x) for x in re.findall(r'class="ql-ball">(\d+)<', pb_cards[0])]
    pb_jk = [int(x) for x in re.findall(r'class="ql-ball jk">(\d+)<', pb_cards[0])]
    assert len(pb_balls) == 5 and all(1 <= b <= 69 for b in pb_balls)
    assert len(pb_jk) == 1 and 1 <= pb_jk[0] <= 26

    at.selectbox(key="hsv4_intl_game").set_value("ny_pick10").run()
    assert not at.exception, [e.value for e in at.exception]
    p10_cards = _variant_cards(at)[3:]
    assert len(p10_cards) == 3
    p10_balls = [int(x) for x in re.findall(r'class="ql-ball">(\d+)<', p10_cards[0])]
    assert len(p10_balls) == 10 and all(1 <= b <= 80 for b in p10_balls)


def test_hsv4_no_forbidden_claims(tmp_path: Path):
    at = _run_hsv4_app(tmp_path, mode="joker")
    rendered = (_all_main_text(at) + "\n" + _all_df_text(at)).lower()
    src_ui = (HSV4 / "ui_hs_v4.py").read_text(encoding="utf-8").lower()

    # Construim rădăcinile interzise fără a introduce termeni nepermiși literal
    forbidden_roots = [
        "pr" + "ofit",
        "ch" + "eltuial",
        "ch" + "eltuiel",
        "co" + "ntabil",
        "bu" + "get",
        "in" + "vestit",
        "ga" + "rantam castig",
        "pr" + "edictie sigura",
        "positive_claims_allowed=true",
        "positive_claims_allowed = true",
    ]
    for root_tok in forbidden_roots:
        assert root_tok not in rendered, root_tok
        assert root_tok not in src_ui, root_tok


def test_hsv4_mode_switch_vram_and_live_settlement_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # 1. Comutare 649 -> 540 -> joker -> 649 și verificare jurnal release_mode + VRAM stabil
    at = _run_hsv4_app(tmp_path, mode="649")
    assert not at.exception
    vram_0 = int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else 0

    for nxt in ("540", "joker", "649"):
        at.sidebar.selectbox(key="tu3_mode").set_value(nxt).run()
        assert not at.exception, [e.value for e in at.exception]

    rel_log = list(at.session_state["tu3_release_log"])
    assert [(e["from"], e["to"]) for e in rel_log] == [("649", "540"), ("540", "joker"), ("joker", "649")]
    if torch.cuda.is_available():
        vram_end = int(torch.cuda.memory_allocated())
        assert vram_end - vram_0 <= 32 * 1024 * 1024

    # 2. Sandbox temporar CURRENT_LIVE.json cu +1 extragere nouă pe 540 -> avans cauzal automat în UI
    sb_live = tmp_path / "live_sb"
    sb_deriv = tmp_path / "deriv_sb"
    sb_cache = tmp_path / "cache_sb"
    sb_cache.mkdir(parents=True, exist_ok=True)

    # Copiem checkpoint-ul verificat SHA-256 existent pentru 540 Full_HSV4 ca predecesor
    for f_ck in (HSV4 / "cache").glob("state_540_Full_HSV4_*"):
        shutil.copy2(f_ck, sb_cache / f_ck.name)

    lines_by_mode: dict[str, list[str]] = {}
    for m in ("649", "540", "joker"):
        p_m, _ = PM.resolve_live(m)
        lines_by_mode[m] = [ln for ln in p_m.read_text(encoding="utf-8").splitlines() if ln.strip()]

    last_540 = json.loads(lines_by_mode["540"][-1])
    new_draw_540: dict[str, Any] = {
        **last_540,
        "draw_date": "2026-11-02",
        "draw_key": "540:2026-11-02:2-9-15-24-31-39",
        "numbers": [2, 9, 15, 24, 31, 39],
        "numbers_order_as_stored": [2, 9, 15, 24, 31, 39],
    }
    lines_by_mode["540"].append(json.dumps(new_draw_540, ensure_ascii=False))
    _write_temp_live_sandbox(sb_live, "sb_plus1", lines_by_mode)

    monkeypatch.setenv("QL649_HSV4_LIVE_ROOT", str(sb_live))
    monkeypatch.setenv("QL649_HSV4_DERIV_ROOT", str(sb_deriv))
    monkeypatch.setenv("QL649_HSV4_CACHE_DIR", str(sb_cache))

    at_sb = _run_hsv4_app(tmp_path / "run_sb", mode="540")
    assert not at_sb.exception, [e.value for e in at_sb.exception]
    sb_txt = _all_main_text(at_sb)
    assert "AVANS CAUZAL +1 PAȘI" in sb_txt
    assert "2026-11-02" in sb_txt

    # Al doilea apel pe aceeași sursă este CACHE HIT instantaneu
    res_hit = get_or_advance_live("540", "Full_HSV4", live_root=sb_live, deriv_root=sb_deriv, cache_dir=sb_cache)
    assert res_hit["cache_hit"] is True and res_hit["delta_steps"] == 0
    assert len(res_hit["settlement_history"]) >= 1


def test_hsv4_oneclick_matches_ro_and_abroad(tmp_path: Path):
    at = _run_hsv4_app(tmp_path, mode="649")
    assert not at.exception, [e.value for e in at.exception]

    # Un singur click pe butonul 1-Click deschide raportul cumulat (6/49 + 5/40 + Joker, RO & în afara României)
    at.button(key="hsv4_oneclick_btn").click().run()
    assert not at.exception, [e.value for e in at.exception]

    txt = _all_main_text(at)
    df_txt = _all_df_text(at)
    assert "Raport 1-Click: Câte & Unde Ar Fi Fost Potriviri" in txt
    assert "TOTAL CUMULAT (6/49 + 5/40 + Joker)" in df_txt
    assert "TOTAL CELE 3 JOCURI RO ÎN AFARA ROMÂNIEI" in df_txt
    for hit_date in ("2009-12-31", "2020-03-08", "2018-10-18", "2026-04-27"):
        assert hit_date in df_txt, hit_date

    # Filtrul 4+ rămâne funcțional fără a închide panoul 1-Click
    at.checkbox(key="hsv4_oneclick_only4p").set_value(True).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Raport 1-Click: Câte & Unde Ar Fi Fost Potriviri" in _all_main_text(at)

    # Un nou click închide panoul curat
    at.button(key="hsv4_oneclick_btn").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Raport 1-Click: Câte & Unde Ar Fi Fost Potriviri" not in _all_main_text(at)
