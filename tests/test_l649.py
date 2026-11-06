"""Teste TU3-L649 (PROTOCOL_TU3_L649.md §6): 6/49 pe arhiva LIVE în aplicație (LIVE implicit + „înghețat (sigilat)”)
și înlocuirea sigilată `inlocuiri_tu3/v1`.

AppTest în mod FAST (QL649_CONFIG=fast), sigiliile de timp într-un director temporar. Testele NU tipăresc, NU salvează
în afara directoarelor temporare și NU compară variantele (verifică numai forma: 6 numere distincte din 1..49).
L10 cere înregistrarea `tu3/inlocuiri/INLOCUIRE_L649_*.json` (scrisă după testele de cod, §7 O5).
Variantele produsului = minime de energie, NU predicții. Calcul clasic. positive_claims_allowed=false.
"""
import ast
import difflib
import hashlib
import json
import os
import re
import subprocess
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

SEAL_P = TU3 / "SIGILIU_TU3_L649.json"
SEAL = json.loads(SEAL_P.read_text())
PROTO = TU3 / "PROTOCOL_TU3_L649.md"
PREFIX = "🛰 Sursa 6/49:"
REPLACEABLE = {"app.py", "tu3/ui_tu3.py", "tu3/matrice_init.py", "tu3/validare_tu3.py", "tests/test_app_tu3.py",
               "tests/test_validare_tu3.py", "tests/test_dedup_live.py", "tests/test_lansator_tu3.py"}


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _insertions_only(old: str, new: str) -> bool:
    a, b = old.splitlines(), new.splitlines()
    ops = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
    return {o for o, *_ in ops} <= {"equal", "insert"}


def _app(tmp_path):
    os.environ["QL649_SEAL_DIR"] = str(tmp_path / "sigilii")
    os.environ["QL649_CONFIG"] = "fast"
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at.run()
    return at


def _src_line(at) -> str:
    lines = [c.value for c in at.main.caption if c.value.startswith(PREFIX)]
    assert len(lines) == 1, lines
    return lines[0]


def _variants(at):
    cards = [m.value for m in at.markdown if 'class="ql-variant' in m.value]
    return [tuple(int(x) for x in re.findall(r'class="ql-ball">(\d+)<', c)) for c in cards]


def _live_now():
    path, prov = PM.resolve_live("649")
    lv = PM.build_game_dataset("649", "live", device="cpu")
    fr = PM.build_game_dataset("649", "frozen", device="cpu")
    return PM.sha256_file(path), prov, lv, PM.compare_frozen_live(fr, lv)


# ---------------- L1: sigiliul protocolului, scris ÎNAINTE de cod ----------------
def test_L1_seal_before_code():
    assert _sha(PROTO) == SEAL["sha256"] and SEAL["file"] == PROTO.name
    assert SEAL["code_files_present"] == [] and SEAL["results_present"] is False
    assert SEAL["replacement_mechanism"] == INL.MECHANISM and SEAL["positive_claims_allowed"] is False
    assert (os.stat(SEAL_P).st_mode & 0o222) == 0 and (os.stat(PROTO).st_mode & 0o222) == 0
    assert set(SEAL["replaceable"]) == REPLACEABLE
    assert SEAL["replaceable"]["app.py"].startswith("051dd839")
    assert SEAL["replaceable"]["tu3/ui_tu3.py"].startswith("9fe6c4d3")
    assert "tu3/inlocuiri_tu3.py" in SEAL["new_files_planned"] and "tests/test_l649.py" in SEAL["new_files_planned"]


# ---------------- L2: fișierele protejate byte-identice ----------------
def test_L2_frozen_identical():
    bad = [k for k, h in SEAL["frozen_hashes"].items() if _sha(ROOT / k) != h]
    bad += [k for k, h in SEAL["frozen_external"].items() if _sha(k) != h]
    assert bad == []
    for k in ("engine.py", "parser.py", "tu3/parser_multi.py", "tu3/motor_n.py", "tu3/motor_joker.py", "run_app.sh",
              "run_app_tu3.sh", "porneste_aplicatia.sh", "porneste_aplicatia_tu3.sh", "tu3/arhiva_live.py",
              "tu3/dedup_live.py", "validare.py"):
        assert k in SEAL["frozen_hashes"], k
    assert any(p.endswith("predictie_numere/probe_date/extrageri_649.jsonl") for p in SEAL["frozen_external"])


# ---------------- L3: copiile de referință și „numai inserții” ----------------
def test_L3_baselines_and_insertions_only():
    for k, h in SEAL["baseline_copies_must_equal"].items():
        assert _sha(ROOT / k) == h, k
    app_new = (ROOT / "app.py").read_text()
    assert _insertions_only((ROOT / "tests/baseline/app_tu3_pre_l649.py").read_text(), app_new)
    assert _insertions_only((ROOT / "tests/baseline/app_v2_649.py").read_text(), app_new)
    assert _insertions_only((ROOT / "tests/baseline/ui_tu3_pre_l649.py").read_text(), (TU3 / "ui_tu3.py").read_text())
    assert app_new.count("ui_tu3.l649_") >= 5 and "TU3-L649" in app_new


# ---------------- L4: helperul inlocuiri_tu3 pe directoare temporare ----------------
def _fake_root(tmp_path):
    root = tmp_path / "r"
    (root / "tu3").mkdir(parents=True)
    (root / "a.txt").write_text("vechi\n")
    (root / "b.txt").write_text("b\n")
    proto = root / "tu3" / "P.md"
    proto.write_text("protocol\n")
    seal = {"file": "P.md", "sha256": _sha(proto), "sealed_utc": "2000-01-01T00:00:00Z", "code_files_present": [],
            "results_present": False, "replacement_mechanism": INL.MECHANISM, "replaceable": {"a.txt": _sha(root / "a.txt")},
            "frozen_hashes": {}, "frozen_external": {}}
    sp = root / "tu3" / "S.json"
    sp.write_text(json.dumps(seal))
    os.chmod(sp, 0o444)
    old = {"a.txt": _sha(root / "a.txt"), "b.txt": _sha(root / "b.txt")}
    return root, old


def _craft(root, name, repl, written="2099-01-01T00:00:00Z", mode=0o444):
    d = root / "tu3" / "inlocuiri"
    d.mkdir(exist_ok=True)
    sp = root / "tu3" / "S.json"
    rec = {"record": "INLOCUIRE_X", "mechanism": INL.MECHANISM, "seal": "tu3/S.json", "seal_sha256": _sha(sp),
           "protocol": "tu3/P.md", "protocol_sha256": _sha(root / "tu3" / "P.md"), "written_utc": written,
           "replacements": repl, "positive_claims_allowed": False}
    p = d / name
    p.write_text(json.dumps(rec))
    os.chmod(p, mode)
    return p


def test_L4_helper_rules(tmp_path):
    root, old = _fake_root(tmp_path)
    assert INL.resolve(old, root)["identical"] == 2
    (root / "a.txt").write_text("nou\n")
    assert INL.resolve(old, root)["drift"] == ["a.txt"]                       # fără înregistrare ⇒ DRIFT
    h1 = _sha(root / "a.txt")
    # înregistrări invalide ⇒ ignorate ⇒ DRIFT
    _craft(root, "INLOCUIRE_X_1.json", {"a.txt": {"from": old["a.txt"], "to": h1}}, mode=0o644)          # R2
    _craft(root, "INLOCUIRE_X_2.json", {"a.txt": {"from": old["a.txt"], "to": h1}}, written="1999-01-01T00:00:00Z")  # R6
    _craft(root, "INLOCUIRE_X_3.json", {"a.txt": {"from": "0" * 64, "to": h1}})                          # R8
    (root / "b.txt").write_text("b2\n")
    _craft(root, "INLOCUIRE_X_4.json", {"b.txt": {"from": old["b.txt"], "to": _sha(root / "b.txt")}})    # R7
    r = INL.resolve(old, root)
    assert sorted(r["drift"]) == ["a.txt", "b.txt"] and len(r["invalid_records"]) == 4
    for p in (root / "tu3" / "inlocuiri").glob("*.json"):
        os.chmod(p, 0o644)
        p.unlink()
    (root / "b.txt").write_text("b\n")
    # înregistrare validă prin write_record ⇒ înlocuit
    rec = INL.write_record("tu3/S.json", "T", root)
    r = INL.resolve(old, root)
    assert r["drift"] == [] and r["replaced"] == ["a.txt"] and r["records"] == [rec.name]
    # lanț în două trepte
    (root / "a.txt").write_text("mai nou\n")
    h2 = _sha(root / "a.txt")
    _craft(root, "INLOCUIRE_T_29990101T000000Z.json", {"a.txt": {"from": h1, "to": h2}})
    r = INL.resolve(old, root)
    assert r["replaced"] == ["a.txt"] and len(r["records"]) == 2
    # ciclu (h2 → h1) cu fișier curent h3: fără buclă infinită ⇒ DRIFT
    _craft(root, "INLOCUIRE_T_29990102T000000Z.json", {"a.txt": {"from": h2, "to": h1}})
    (root / "a.txt").write_text("altceva\n")
    assert INL.resolve(old, root)["drift"] == ["a.txt"]
    # sigiliu modificat ⇒ toate înregistrările lui invalide
    sp = root / "tu3" / "S.json"
    os.chmod(sp, 0o644)
    sp.write_text(sp.read_text() + " ")
    os.chmod(sp, 0o444)
    (root / "a.txt").write_text("nou\n")
    r = INL.resolve(old, root)
    assert r["drift"] == ["a.txt"] and r["invalid_records"]


def test_L4b_helper_stdlib_only():
    tree = ast.parse((TU3 / "inlocuiri_tu3.py").read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert mods <= set(sys.stdlib_module_names) | {"__future__"}, mods


# ---------------- L5 + L6: LIVE implicit, linia sursei, martorul ----------------
def test_L5_L6_live_default_and_witness(tmp_path):
    at = _app(tmp_path)
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["l649_src"] == "live"
    key, prov, lv, cmp = _live_now()
    line = _src_line(at)
    live_last = lv.step_dates[-1]
    assert "LIVE (implicit)" in line and key[:12] in line and live_last in line
    assert any("ultima extragere" in m.value and live_last in m.value for m in at.markdown)
    assert (f"{cmp['common_keys']} chei comune, {len(cmp['differing_on_common_keys'])} diferențe pe chei comune, "
            f"{len(cmp['only_in_live'])} numai în LIVE, {len(cmp['only_in_frozen'])} numai în înghețat") in line
    assert ("LIVE ⊇ înghețat: DA" if cmp["live_superset_of_frozen"] else "LIVE ⊇ înghețat: NU") in line
    assert len(at.tabs) == 12
    vs = _variants(at)
    assert len(vs) == 3 and len(set(vs)) == 3
    assert all(len(v) == 6 and len(set(v)) == 6 and all(1 <= x <= 49 for x in v) for v in vs)
    assert len(at.warning) == len(ui_tu3.l649_warnings(cmp))


def test_L6b_witness_rendering_synthetic():
    m = {"differing_on_common_keys": ["k1", "k2"], "only_in_frozen": []}
    w = ui_tu3.l649_warnings(m)
    assert len(w) == 1 and "k1, k2" in w[0] and "NEreparate" in w[0]
    m = {"differing_on_common_keys": [], "only_in_frozen": [f"x{i}" for i in range(25)]}
    w = ui_tu3.l649_warnings(m)
    assert len(w) == 1 and w[0].endswith(" …") and "x19" in w[0] and "x20" not in w[0]
    assert ui_tu3.l649_warnings(None) == [] and ui_tu3.l649_warnings({"differing_on_common_keys": []}) == []
    line = ui_tu3.l649_source_line("frozen", {"live_error": "IntegrityError: test"})
    assert line.startswith(PREFIX) and "LIVE indisponibil: IntegrityError: test" in line and "193eaf7a6f4f" in line


# ---------------- L7: LIVE → înghețat → LIVE (eliberare + VRAM) ----------------
def test_L7_switch_source_release(tmp_path):
    torch = pytest.importorskip("torch")
    at = _app(tmp_path)
    assert not at.exception
    mem0 = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
    at.radio(key="l649_src").set_value("frozen").run()
    assert not at.exception, [e.value for e in at.exception]
    assert "înghețat (sigilat)" in _src_line(at) and "193eaf7a6f4f" in _src_line(at)
    at.radio(key="l649_src").set_value("live").run()
    assert not at.exception
    assert "LIVE (implicit)" in _src_line(at)
    mem2 = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
    log = at.session_state["l649_release_log"]
    assert [(e["from"], e["to"]) for e in log] == [("live", "frozen"), ("frozen", "live")]
    assert mem2 <= mem0 + 8 * 2 ** 20


# ---------------- L8: sigiliul de timp conține sursa activă ----------------
def test_L8_time_seal_source_fields(tmp_path):
    at = _app(tmp_path)
    at.button(key="seal_btn").click().run()
    assert not at.exception
    key, prov, _, _ = _live_now()
    at.radio(key="l649_src").set_value("frozen").run()
    time.sleep(1.2)                                                 # numele sigiliului are rezoluție de 1 s
    at.button(key="seal_btn").click().run()
    assert not at.exception
    seals = sorted((tmp_path / "sigilii").glob("SIGILIU_*.json"))
    assert len(seals) == 2
    got = {}
    for s in seals:
        d = json.loads(s.read_text())
        p = d["payload"]
        assert d["sha256"] == hashlib.sha256(json.dumps(p, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert p["positive_claims_allowed"] is False and p["l649_protocol_sha256"] == SEAL["sha256"]
        got[p["l649_source_kind"]] = p
    lv, fr = got["live"], got["frozen"]
    assert lv["l649_source_file_sha256"] == key and lv["l649_live_version_dir"].startswith("versiuni/")
    assert lv["l649_adapted_sha256"] == lv["source_sha256"]
    assert fr["l649_source_file_sha256"] == PM.FROZEN_649_SHA256 == fr["source_sha256"]
    assert fr["l649_live_version_dir"] is None and fr["l649_adapted_sha256"] is None


# ---------------- L9: schimbarea modului din 6/49 (LIVE) golește și setul LIVE ----------------
def test_L9_mode_switch_clears_live(tmp_path, monkeypatch):
    calls = []
    real = PM.build_game_dataset

    def counting(game, source="live", device=None, *a, **k):
        if game == "649" and source == "live" and device is None:
            calls.append(1)
        return real(game, source, device, *a, **k)

    monkeypatch.setattr(PM, "build_game_dataset", counting)
    ui_tu3.l649_live_dataset.clear()
    at = _app(tmp_path)
    assert not at.exception
    c1 = len(calls)
    assert c1 >= 1
    at.run()
    assert len(calls) == c1                                         # fără schimbare ⇒ din cache
    at.selectbox(key="tu3_mode").set_value("540").run()
    assert not at.exception
    at.selectbox(key="tu3_mode").set_value("649").run()
    assert not at.exception
    assert len(calls) == c1 + 1                                     # setul LIVE a fost eliberat la comutare
    assert [(e["from"], e["to"]) for e in at.session_state["tu3_release_log"]] == [("649", "540"), ("540", "649")]


# ---------------- L10: helperul --verifica (cere înregistrarea L649) ----------------
def test_L10_verify_all_seals():
    out = subprocess.run([sys.executable, "-B", str(TU3 / "inlocuiri_tu3.py"), "--verifica"], capture_output=True,
                         text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    rep = json.loads(out.stdout)
    assert rep["ok"] is True and rep["invalid_records"] == []
    assert any(n.startswith("INLOCUIRE_L649_") for n in rep["valid_records"])
    for s, v in rep["seals"].items():
        assert v["drift"] == [], (s, v["drift"])
        assert set(v["replaced"]) <= REPLACEABLE
    assert {"app.py", "tu3/ui_tu3.py"} <= set(rep["seals"]["tu3/SIGILIU_TU3_VS.json"]["replaced"])
