"""Teste UI TU3 v3.0 (protocol tu3/PROTOCOL_TU3_UI.md §5): selector global, 12 taburi × 3 moduri, EXACT 3 variante
(6 / 5 / 5+1), sigiliul SHA-256, eliberarea tensorilor și identitatea căii 6/49. Mod FAST (AppTest).

Testele NU tipăresc, NU salvează (în afara directorului temporar de sigilii) și NU compară variantele reale: verifică
numai forma (regula jocului, unicitatea), nu valorile."""
import difflib
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from streamlit.testing.v1 import AppTest  # noqa: E402

BASELINE = ROOT / "tests" / "baseline" / "app_v2_649.py"
SEAL = json.loads((ROOT / "tu3" / "SIGILIU_TU3_UI.json").read_text())
MODE_INDEX = {"649": 0, "540": 1, "joker": 2}
RULES = {"649": (49, 6, None), "540": (40, 5, None), "joker": (45, 5, 20)}
VOLATILE = ("timp motor GPU", "VRAM")


def _env(tmp_path):
    os.environ["QL649_SEAL_DIR"] = str(tmp_path / "sigilii")
    os.environ["QL649_CONFIG"] = "fast"


def _app(tmp_path, mode="649"):
    _env(tmp_path)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at.run()
    if mode != "649":
        _select(at, mode)
    return at


def _select(at, mode):
    at.selectbox(key="tu3_mode").set_value(mode).run()      # AppTest aplică format_func pe valoare
    return at


def _cards(at):
    return [m.value for m in at.markdown if 'class="ql-variant' in m.value]


def _parse(card):
    main = tuple(int(x) for x in re.findall(r'class="ql-ball">(\d+)<', card))
    jk = re.findall(r'class="ql-ball jk">(\d+)<', card)
    return main, (int(jk[0]) if jk else None)


def _rule_ok(mode, cards):
    n, k, m = RULES[mode]
    parsed = [_parse(c) for c in cards]
    ok = len(parsed) == 3
    for main, j in parsed:
        ok &= len(main) == k and len(set(main)) == k and all(1 <= x <= n for x in main)
        ok &= (j is None) if m is None else (j is not None and 1 <= j <= m)
    ok &= len({(tuple(sorted(a)), b) for a, b in parsed}) == 3
    return bool(ok)


def _mask(s):
    return re.sub(r"\d", "#", s) if any(v in s for v in VOLATILE) else s


def _plot_titles(at):
    out = []
    for el in at.main.get("plotly_chart"):
        lay = json.loads(el.proto.spec).get("layout", {})
        t = lay.get("title", {})
        out.append(t.get("text") if isinstance(t, dict) else t)
    return out


def _main_snapshot(at):
    return {"tabs": [t.label for t in at.tabs],
            "markdown": [_mask(m.value) for m in at.main.markdown],
            "caption": [c.value for c in at.main.caption],
            "info": [i.value for i in at.main.info],
            "n_dataframe": len(at.main.dataframe),
            "plots": _plot_titles(at),
            "cards": _cards(at)}


# U1 — identitatea căii 6/49 față de copia byte-identică a app.py anterior
def test_u1_identity_649_vs_baseline(tmp_path):
    assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == SEAL["hashes"]["app.py"]
    _env(tmp_path)
    src = BASELINE.read_text()
    needle = "ROOT = Path(__file__).resolve().parent"
    assert src.count(needle) == 1
    base = AppTest.from_string(src.replace(needle, f"ROOT = Path({str(ROOT)!r})"), default_timeout=900)
    base.run()
    assert not base.exception
    new = _app(tmp_path)
    assert not new.exception
    # U1′ (TU3-L649 §5.3): cu „înghețat (sigilat)” selectat, vederea principală = copia de referință, mai puțin EXACT
    # linia sursei („🛰 Sursa 6/49:”); implicit sursa este LIVE.
    assert new.session_state["l649_src"] == "live"
    new.radio(key="l649_src").set_value("frozen").run()
    assert not new.exception, [e.value for e in new.exception]
    a, b = _main_snapshot(base), _main_snapshot(new)
    src_lines = [c for c in b["caption"] if c.startswith("🛰 Sursa 6/49:")]
    assert len(src_lines) == 1 and "înghețat (sigilat)" in src_lines[0]
    b["caption"] = [c for c in b["caption"] if not c.startswith("🛰 Sursa 6/49:")]
    assert len(a["tabs"]) == 12 and len(a["cards"]) == 3
    for key in a:
        assert a[key] == b[key], key
    for x, y in zip(base.main.dataframe, new.main.dataframe):
        assert x.value.equals(y.value)


# U2 — selectorul global din sidebar
def test_u2_selector(tmp_path):
    at = _app(tmp_path)
    sb = at.sidebar.selectbox
    assert len(sb) == 1 and sb[0].key == "tu3_mode"
    assert list(sb[0].options) == ["🌌 Mode: Loto 6/49", "🌀 Mode: Loto 5/40", "🃏 Mode: Joker"]
    assert at.session_state["tu3_mode"] == "649"


# U3/U4 — 12 taburi și EXACT 3 variante după regula activă (5/40: 5 din 40; Joker: 5 din 45 + 1 din 20)
@pytest.mark.parametrize("mode", ["540", "joker"])
def test_u3_u4_modes_tabs_and_variants(tmp_path, mode):
    at = _app(tmp_path, mode)
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["tu3_mode"] == mode
    assert len(at.tabs) == 12
    assert [t.label for t in at.tabs] == [t.label for t in _app(tmp_path).tabs]
    ok = _rule_ok(mode, _cards(at))
    assert ok
    text = " ".join(m.value for m in at.markdown)
    assert "positive_claims_allowed=false" in text and "MOD FAST (test)" in text
    assert "QUANTUM LAB 540" in text if mode == "540" else "QUANTUM LAB JOKER" in text
    assert sum("NEAPLICABIL" in i.value for i in at.info) == 0          # TU3-T7C: taburile 7–12 = porturi DESCRIPTIVE
    assert not any("BO649-P1" in c.value for c in at.caption)           # artefactele 6/49 nu se citesc


# U5 — sigiliul SHA-256 de timp în subdirectorul modului
@pytest.mark.parametrize("mode", ["540", "joker"])
def test_u5_seal(tmp_path, mode):
    at = _app(tmp_path, mode)
    at.button(key=f"seal_btn_{mode}").click().run()
    assert not at.exception
    seals = list((tmp_path / "sigilii" / mode).glob(f"SIGILIU_{mode}_*.json"))
    assert len(seals) == 1
    assert not list((tmp_path / "sigilii").glob("SIGILIU_*.json"))      # rădăcina 6/49 neatinsă
    d = json.loads(seals[0].read_text())
    p = d["payload"]
    canon = json.dumps(p, sort_keys=True, separators=(",", ":")).encode()
    assert d["sha256"] == hashlib.sha256(canon).hexdigest()
    assert p["game"] == mode and p["positive_claims_allowed"] is False and p["source_kind"] == "live"
    n, k, m = RULES[mode]
    vs = p["variants"]
    if m is None:
        ok = len(vs) == 3 and all(len(set(v)) == k and all(1 <= x <= n for x in v) for v in vs)
    else:
        ok = len(vs) == 3 and all(len(set(v[0])) == k and all(1 <= x <= n for x in v[0]) and 1 <= v[1] <= m for v in vs)
    assert ok


# U6 — schimbarea modului eliberează tensorii, fără scurgeri de VRAM
def test_u6_switch_release_no_leak(tmp_path):
    torch = pytest.importorskip("torch")
    at = _app(tmp_path)
    mem = []
    for mode in ["540", "joker", "649", "540", "joker"]:
        _select(at, mode)
        assert not at.exception, [e.value for e in at.exception]
        assert len(at.tabs) == 12
        mem.append(torch.cuda.memory_allocated() if torch.cuda.is_available() else 0)
    log = at.session_state["tu3_release_log"]
    assert [(e["from"], e["to"]) for e in log] == [("649", "540"), ("540", "joker"), ("joker", "649"),
                                                   ("649", "540"), ("540", "joker")]
    assert mem[4] <= mem[1] + 8 * 2 ** 20


# U7 — ablația NON-protocol în modul 5/40
def test_u7_ablation_540(tmp_path):
    at = _app(tmp_path, "540")
    at.checkbox(key="abl_kur_540").uncheck()
    at.button(key="abl_submit_540").click().run()
    assert not at.exception
    assert len(_cards(at)) == 6


# U8 — fișierele NEMODIFICATE și app.py = copia anterioară + numai inserții
def test_u8_unchanged_files_and_additive_app():
    for f, h in SEAL["hashes"].items():
        if f == "app.py":
            continue
        assert hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h, f
    old = BASELINE.read_text().splitlines()
    new = (ROOT / "app.py").read_text().splitlines()
    ops = {op for op, *_ in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes()}
    assert ops <= {"equal", "insert"}


# U9 (opțional, ca în test_app.py) — modurile 5/40 și Joker în configurația de PROTOCOL, pe LIVE
@pytest.mark.skipif(os.environ.get("QL649_UI_PROTOCOL") != "1", reason="setează QL649_UI_PROTOCOL=1 pentru protocol")
@pytest.mark.parametrize("mode", ["540", "joker"])
def test_u9_protocol_modes(tmp_path, mode):
    os.environ["QL649_SEAL_DIR"] = str(tmp_path / "sigilii")
    os.environ.pop("QL649_CONFIG", None)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=1800)
    at.run()
    _select(at, mode)
    assert not at.exception
    cards = _cards(at)
    ok = _rule_ok(mode, cards) and all(("protocol TU3-E40" if mode == "540" else "protocol TU3-EJ") in c for c in cards)
    assert ok
    assert "MOD FAST" not in " ".join(m.value for m in at.markdown)


# ---------------------------------------------------------------------------
# TU3-SR-R (S8; PROTOCOL_TU3_SR_R.md §4.2) — taburile 4–5 afișează verdictele rulării reale UNICE (inserții).
# U10 pe rezultate de TEST într-un director temporar (QL649_SR_DIR); U11 pe rezultatele reale (skip dacă lipsesc).
# ---------------------------------------------------------------------------
SR_REAL = ROOT / "tu3" / "rezultate" / "SR"


def _tab_all_text(tab):
    parts = []
    for kind in ("markdown", "caption", "info", "error", "warning", "success"):
        parts += [e.value for e in getattr(tab, kind, [])]
    return "\n".join(parts)


def _sr_fixture(root, mode, ver="pass"):
    d = root / mode
    d.mkdir(parents=True)
    (d / "START.json").write_text(json.dumps({"started_at_utc": "2099-01-01T00:00:00Z", "game": mode}))
    names = ["main.chi_freq", "main.chi_pair", "main.chi_gap", "main.overlap"]
    if mode == "joker":
        names += ["ball.chi_freq", "ball.chi_gap", "ball.overlap", "cross.chi"]
    urns = [("540", 40, 6, 5)] if mode == "540" else [("joker_principal", 45, 5, 5), ("joker_bila", 20, 1, 1)]
    comps = []
    for nm, n, r, k in urns:
        comps.append({"urn": {"name": nm, "n": n, "r": r, "k": k, "E_U": k * r / n, "tau": 0.2},
                      "total": {"hits_QL": 7, "hits_B": 6, "hits_R": 5, "excess_QL": 0.1, "log_QL": -1.0,
                                "log_U": -1.1, "log_B": -1.2, "brier_QL": 0.5, "brier_U": 0.6},
                      "gates": [{"gate": str(i), "rule": f"regula {i}", "pass": i == 2, "value": 0} for i in range(1, 7)],
                      "gates_passed": 1, "n_targets": 4, "p_exact_hits_QL_ge": 0.3,
                      "per_target": {"hits_QL": [2, 1, 2, 2], "hits_B": [1, 2, 1, 2], "hits_R": [1, 1, 1, 2],
                                     "hits_union": [3, 3, 3, 3]}})
    res = {"game": mode, "session": "S8", "D1": {"alpha_each": 0.01, "p_values": [0.3] * len(comps), "detected": False,
                                                 "verdict": "SR_FARA_DETECTIE_TEST"},
           "D2": {"SCI": 0.25, "p_empirical": 0.4, "M_null": 8192, "seed": 1, "z": {k_: 0.1 for k_ in names},
                  "verdict": "SCI_COMPATIBIL_NUL_TEST"},
           "promotion": "SR_NO_PROMOTION_TEST", "components": comps, "predictions_sha256": "ab" * 32,
           "start": {"started_at_utc": "2099-01-01T00:00:00Z", "source_sha256": "cd" * 32}, "seconds": 1.0,
           "resources": {"peak_reserved_bytes": 1e9, "thermal": {"t_max_c": 60, "pauses": 0,
                                                                 "temperature_target_met": True}},
           "finished_at_utc": "2099-01-01T00:01:00Z", "positive_claims_allowed": False}
    raw = json.dumps(res).encode()
    (d / "REZULTATE.json").write_bytes(raw)
    if ver:
        rsha = hashlib.sha256(raw).hexdigest() if ver != "mismatch" else "0" * 64
        (d / "VERIFICARE_SR.json").write_text(json.dumps({
            "verdict": "VERIFICARE_SR_PASS", "rezultate_sha256": rsha, "predictions_sha256": "ab" * 32,
            "written_utc": "2099-01-01T00:02:00Z", "checks": [],
            "d2_independent": {"SCI": 0.26, "p_empirical": 0.41, "z": {k_: 0.11 for k_ in names},
                               "concordanta": "D2_CONCORDANT"}}))
    return res


# U10 — fără rulare reală casetele „NERULAT” rămân; cu rezultate (test) ele sunt înlocuite de verdictele D2 / D1
@pytest.mark.parametrize("mode", ["540", "joker"])
def test_u10_sr_tabs_4_5(tmp_path, monkeypatch, mode):
    sr = tmp_path / "sr"
    sr.mkdir()
    monkeypatch.setenv("QL649_SR_DIR", str(sr))
    at = _app(tmp_path, mode)
    assert not at.exception, [e.value for e in at.exception]
    assert "NERULAT" in _tab_all_text(at.tabs[3]) and "NERULAT" in _tab_all_text(at.tabs[4])
    res = _sr_fixture(sr, mode)
    at = _app(tmp_path, mode)
    assert not at.exception, [e.value for e in at.exception]
    t4, t5 = _tab_all_text(at.tabs[3]), _tab_all_text(at.tabs[4])
    assert "NERULAT" not in t4 and "NERULAT" not in t5
    assert res["D2"]["verdict"] in t4 and "VERIFICARE_SR_PASS" in t4 and "positive_claims_allowed=false" in t4
    assert res["D1"]["verdict"] in t5 and res["promotion"] in t5 and "VERIFICARE_SR_PASS" in t5
    assert "positive_claims_allowed=false" in t5 and "NU este avantaj" in t5
    assert len(at.tabs[4].get("plotly_chart")) == len(res["components"])
    assert sum("NEAPLICABIL" in i.value for i in at.info) == 0
    assert len(at.tabs) == 12


# U10′ — verificare nepotrivită ⇒ avertisment; START fără REZULTATE ⇒ eroare de incident
def test_u10_sr_mismatch_and_incident(tmp_path, monkeypatch):
    sr = tmp_path / "sr"
    sr.mkdir()
    monkeypatch.setenv("QL649_SR_DIR", str(sr))
    _sr_fixture(sr, "540", ver="mismatch")
    (sr / "joker").mkdir()
    (sr / "joker" / "START.json").write_text("{}")
    at = _app(tmp_path, "540")
    assert not at.exception, [e.value for e in at.exception]
    assert any("nepotrivită" in w.value for w in at.tabs[3].warning)
    _select(at, "joker")
    assert not at.exception, [e.value for e in at.exception]
    assert any("incident" in e.value for e in at.tabs[3].error) and any("incident" in e.value for e in at.tabs[4].error)


# U11 — după rularea reală: taburile 4–5 arată exact verdictele publicate și starea verificării separate
@pytest.mark.parametrize("mode", ["540", "joker"])
def test_u11_sr_real_results(tmp_path, monkeypatch, mode):
    rz = SR_REAL / mode / "REZULTATE.json"
    if not rz.is_file():
        pytest.skip(f"rularea reală {mode} nu există încă (S8)")
    monkeypatch.delenv("QL649_SR_DIR", raising=False)
    res = json.loads(rz.read_text())
    at = _app(tmp_path, mode)
    assert not at.exception, [e.value for e in at.exception]
    t4, t5 = _tab_all_text(at.tabs[3]), _tab_all_text(at.tabs[4])
    assert res["D2"]["verdict"] in t4 and res["D1"]["verdict"] in t5 and res["promotion"] in t5
    assert "NERULAT" not in t4 and "NERULAT" not in t5
    vf = SR_REAL / mode / "VERIFICARE_SR.json"
    if vf.is_file() and json.loads(vf.read_text()).get("verdict") == "VERIFICARE_SR_PASS":
        assert "VERIFICARE_SR_PASS" in t4 and "VERIFICARE_SR_PASS" in t5
    else:
        assert "VERIFICARE_SR_PASS" not in t4
