"""Teste TU4-UI (S14; protocol tu4/PROTOCOL_TU4_UI.md §5, sigilat înainte de cod): tabul „🔮 Predicție prospectivă”.

AppTest pe app.py (calea reală a produsului). Comutatorul pornit ⇒ tabul citește NUMAI tu4/tribunal/ (sau un tribunal de
test indicat prin QL649_TU4_TRIBUNAL) și se oprește înaintea oricărui motor. Testele nu scriu în tribunalul real.
positive_claims_allowed=false.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from streamlit.testing.v1 import AppTest  # noqa: E402

TRIB = ROOT / "tu4" / "tribunal"
UI = ROOT / "tu3" / "ui_tu3.py"
BASE_UI = ROOT / "tests" / "baseline" / "ui_tu3_pre_tu4ui.py"
LABEL = "Test științific în curs; nu este sfat de joc"
TAB = "🔮 Predicție prospectivă"
JU_GENESIS = "5dcc0a4252acf9d504b5bbc11e13816595638839628d53349fd9c08082533093"
LN600, LN20 = 6.396929655216146, 2.995732273553991


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _tree(d: Path) -> dict:
    return {str(p.relative_to(d)): (_sha(p.read_bytes()), p.stat().st_mtime_ns) for p in sorted(d.rglob("*")) if p.is_file()}


def _run(tmp_path, mode: str, trib: Path | None = None, on: bool = True) -> AppTest:
    os.environ["QL649_SEAL_DIR"] = str(tmp_path / "sigilii")
    os.environ["QL649_CONFIG"] = "fast"
    if trib is None:
        os.environ.pop("QL649_TU4_TRIBUNAL", None)
    else:
        os.environ["QL649_TU4_TRIBUNAL"] = str(trib)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at.session_state["tu3_mode"] = mode
    if on:
        at.session_state["tu4_prosp"] = True
    try:
        at.run()
    finally:
        os.environ.pop("QL649_TU4_TRIBUNAL", None)
    return at


def _emission(game: str) -> dict:
    lant = [json.loads(x) for x in (TRIB / "LANT.jsonl").read_bytes().splitlines() if x.strip()]
    rec = max((r for r in lant if r["game"] == game), key=lambda r: r["target_date"])
    return json.loads((TRIB / rec["file"]).read_bytes())


def _tickets(at) -> dict:
    out = {}
    for m in at.main.markdown:
        if 'class="tu4-ticket"' in m.value:
            model = re.search(r'data-model="(H\d)"', m.value).group(1)
            main = [int(x) for x in re.findall(r'class="ql-ball">(\d+)<', m.value)]
            jk = re.findall(r'class="ql-ball jk">(\d+)<', m.value)
            out[model] = (main, int(jk[0]) if jk else None, m.value)
    return out


def _plots(at) -> list[dict]:
    return [json.loads(el.proto.spec) for el in at.main.get("plotly_chart")]


def _texts(at) -> str:
    parts = []
    for kind in ("markdown", "caption", "warning", "info", "error"):
        parts += [e.value for e in getattr(at.main, kind)]
    return "\n".join(parts)


@pytest.fixture(scope="module")
def real_tree():
    return _tree(TRIB)


# UT1 — comutatorul (implicit oprit) și eticheta permanentă în bara laterală; vederea implicită = 12 taburi, fără TU4
def test_ut1_switch_default_off(tmp_path):
    at = _run(tmp_path, "540", on=False)
    assert not at.exception, [e.value for e in at.exception]
    tg = [t for t in at.sidebar.toggle if t.key == "tu4_prosp"]
    assert len(tg) == 1 and tg[0].value is False
    assert any(LABEL in c.value for c in at.sidebar.caption)
    assert len(at.tabs) == 12 and TAB not in [t.label for t in at.tabs]
    assert not _tickets(at)


# UT2 — tribunalul REAL, cele 3 moduri
@pytest.mark.parametrize("mode", ["649", "540", "joker"])
def test_ut2_real_tribunal(tmp_path, mode, real_tree):
    at = _run(tmp_path, mode)
    assert not at.exception, [e.value for e in at.exception]
    assert [t.label for t in at.tabs] == [TAB]
    assert not [m for m in at.main.markdown if 'class="ql-variant' in m.value]        # niciun motor rulat
    txt = _texts(at)
    assert LABEL in txt and "positive_claims_allowed=false" in txt
    assert not at.main.error
    em = _emission(mode)
    assert em["emitted_utc"] in txt                                                     # ora exactă a sigiliului
    tk = _tickets(at)
    assert set(tk) == {"H1", "H3"}
    for m in ("H1", "H3"):
        main, jk, html = tk[m]
        assert main == [int(x) for x in em["models"][m]["top_ticket"]]
        assert jk == (em["models"][m]["ball"]["top_ball"] if mode == "joker" else None)
        assert f"λ = {em['models'][m]['lambda']:.6f}" in html
        assert f"bet_active = <b>{str(em['models'][m]['bet_active']).lower()}</b>" in html
    if mode == "649":
        assert tk["H3"][0] == [1, 2, 3, 4, 5, 6]
    specs = _plots(at)
    heat = [s for s in specs if s["data"] and s["data"][0].get("type") == "heatmap"]
    assert len(heat) == 2
    bars = [s for s in specs if s["data"] and all(d.get("type") == "bar" for d in s["data"])]
    assert len(bars) == (1 if mode == "joker" else 0)
    traj = [s for s in specs if "ln E_t" in str(s["layout"].get("title", ""))]
    assert len(traj) == 1
    ys = sorted(round(sh["y0"], 4) for sh in traj[0]["layout"]["shapes"])
    assert ys == [-10.0, 0.0, round(LN20, 4), round(LN600, 4)]
    assert "MOD TEST" not in txt
    assert any("EXPLORARE" in str(v) for df in at.main.dataframe for v in df.value.get("stare", []))


def _mk_dec(trib: Path, docs: list[dict]) -> None:
    lines, prev = [], JU_GENESIS
    for i, doc in enumerate(docs):
        rel = f"decontari/{doc['game']}/{doc['target_date']}.json"
        data = (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode()
        (trib / rel).parent.mkdir(parents=True, exist_ok=True)
        (trib / rel).write_bytes(data)
        line = json.dumps({"i": i, "game": doc["game"], "target_date": doc["target_date"], "status": doc["status"],
                           "file": rel, "sha256": _sha(data), "prev_line_sha256": prev},
                          ensure_ascii=False, sort_keys=True).encode()
        prev = _sha(line)
        lines.append(line)
    (trib / "DECONTARI.jsonl").write_bytes(b"\n".join(lines) + b"\n")


def _st(lnE=0.0, state="EXPLORARE", conf=None, lnc=0.0):
    return {"state": state, "lnE": lnE, "lnE_conf": lnc, "conf_start_utc": conf and f"{conf}T17:00:00.000000Z",
            "conf_start_date": conf}


def _synthetic(tmp_path) -> Path:
    trib = tmp_path / "tribunal"
    shutil.copytree(TRIB, trib, ignore=shutil.ignore_patterns(".lock", "DECONTARI.jsonl", "decontari"))
    for p in trib.rglob("*"):
        if p.is_file():
            os.chmod(p, 0o644)
    th = {"explore_ln": LN600, "confirm_ln": LN20, "retire_ln": -10.0, "M": 6}
    e649, ej = _emission("649"), _emission("joker")
    base = {"protocol": "TU4-JU", "label": LABEL, "positive_claims_allowed": False, "thresholds": th}
    docs = [
        {**base, "game": "649", "target_date": "2026-10-29", "status": "DECONTAT", "reason": "înregistrarea regulată unică",
         "decided_utc": "2026-10-29T17:10:00.000000Z", "emission": {"file": "emisii/649/2026-10-29.json"},
         "draw": {"numbers": [4, 5, 6, 12, 40, 41], "joker": None},
         "models": {"H1": {"ln_e": 6.5, "counted": True}, "H3": {"ln_e": -0.4, "counted": True}},
         "streams_after": {"H1_649": _st(6.5, "CONFIRMARE", "2026-10-29"), "H3_649": _st(-0.4)}},
        {**base, "game": "joker", "target_date": "2026-10-29", "status": "DECONTAT", "reason": "înregistrarea regulată unică",
         "decided_utc": "2026-10-29T17:10:01.000000Z", "emission": {"file": "emisii/joker/2026-10-29.json"},
         "draw": {"numbers": ej["models"]["H1"]["top_ticket"], "joker": ej["models"]["H1"]["ball"]["top_ball"]},
         "models": {"H1": {"ln_e": 0.2, "counted": True}, "H3": {"ln_e": 0.1, "counted": True}},
         "streams_after": {"H1_joker": _st(0.2), "H3_joker": _st(0.1)}},
        {**base, "game": "649", "target_date": "2026-11-01", "status": "VOID", "reason": "ambiguu: 2 înregistrări regulate",
         "decided_utc": "2026-11-01T17:10:00.000000Z", "emission": {"file": "emisii/649/2026-11-01.json"}, "draw": None,
         "models": {"H1": {"ln_e": 0.0, "counted": False}, "H3": {"ln_e": 0.0, "counted": False}},
         "streams_after": {"H1_649": _st(6.5, "CONFIRMARE", "2026-10-29"), "H3_649": _st(-0.4)}},
        {**base, "game": "649", "target_date": "2026-11-05", "status": "RESPINS", "reason": "admisibilitate: A1_cronologie",
         "decided_utc": "2026-11-05T17:10:00.000000Z", "emission": {"file": "emisii/649/2026-11-05.json"}, "draw": None,
         "models": {"H1": {"ln_e": 0.0, "counted": False}, "H3": {"ln_e": 0.0, "counted": False}},
         "streams_after": {"H1_649": _st(6.5, "CONFIRMARE", "2026-10-29"), "H3_649": _st(-0.4)}},
    ]
    assert e649["models"]["H1"]["top_ticket"] == [4, 5, 6, 12, 25, 36]
    _mk_dec(trib, docs)
    run = {"utc": "2026-11-05T17:10:02.000000Z", "action": "decided", "rc": 0, "decided": [1], "pending": []}
    with open(trib / "JUDECATOR_RULARI.jsonl", "ab") as fh:
        fh.write(json.dumps(run).encode() + b"\n")
    return trib


# UT3 + UT8 — tribunal sintetic: DECONTAT / VOID / RESPINS, potriviri, traiectorie, stări, MOD TEST
def test_ut3_ut8_synthetic_history(tmp_path):
    trib = _synthetic(tmp_path)
    at = _run(tmp_path, "649", trib)
    assert not at.exception, [e.value for e in at.exception]
    txt = _texts(at)
    assert "MOD TEST" in txt and not at.main.error
    hist = [df.value for df in at.main.dataframe if "potriviri H1" in df.value.columns]
    assert len(hist) == 1
    h = hist[0]
    assert list(h["data"]) == ["2026-10-29", "2026-11-01", "2026-11-05"]
    assert [s.split()[-1] for s in h["stare"]] == ["DECONTAT", "VOID", "RESPINS"]
    assert list(h["potriviri H1"]) == ["4", "—", "—"] and list(h["potriviri H3"]) == ["3", "—", "—"]
    assert list(h["numărat H1"]) == ["da", "nu", "nu"]
    states = [df.value for df in at.main.dataframe if "flux" in df.value.columns][0].set_index("flux")
    assert "CONFIRMARE" in states.loc["H1_649", "stare"] and states.loc["H1_649", "decontări numărate"] == 1
    assert abs(states.loc["H3_649", "ln E"] + 0.4) < 1e-12 and "EXPLORARE" in states.loc["H3_joker", "stare"]
    traj = [s for s in _plots(at) if "ln E_t" in str(s["layout"].get("title", ""))][0]
    names = [d.get("name") for d in traj["data"]]
    assert "H1_649 ln E_conf" in names
    h1 = traj["data"][names.index("H1_649 ln E")]
    assert h1["y"][0] == 0.0 and h1["y"][-1] == 6.5 and len(h1["y"]) == 4
    assert "ultima rulare" in txt.lower() or any("Ultima rulare" in c.value for c in at.main.caption)
    at_j = _run(tmp_path, "joker", trib)
    hj = [df.value for df in at_j.main.dataframe if "potriviri H1" in df.value.columns][0]
    assert list(hj["potriviri H1"]) == ["5 + J✓"]


# UT4 — emisie alterată ⇒ refuz (nicio emisie afișată)
def test_ut4_tampered_emission(tmp_path):
    trib = _synthetic(tmp_path)
    p = trib / "emisii" / "649" / "2026-10-29.json"
    p.write_bytes(p.read_bytes() + b" ")
    at = _run(tmp_path, "649", trib)
    assert not at.exception
    assert any("LANT" in e.value for e in at.main.error)
    assert not _tickets(at)


# UT5 — lanț DECONTARI rupt ⇒ eroare în secțiunea decontărilor; emisia curentă rămâne
def test_ut5_broken_settlement_chain(tmp_path):
    trib = _synthetic(tmp_path)
    lines = (trib / "DECONTARI.jsonl").read_bytes().splitlines()
    rec = json.loads(lines[1])
    rec["prev_line_sha256"] = "0" * 64
    lines[1] = json.dumps(rec, ensure_ascii=False, sort_keys=True).encode()
    (trib / "DECONTARI.jsonl").write_bytes(b"\n".join(lines) + b"\n")
    at = _run(tmp_path, "649", trib)
    assert not at.exception
    assert any("DECONTARI" in e.value for e in at.main.error)
    assert set(_tickets(at)) == {"H1", "H3"}
    assert not [s for s in _plots(at) if "ln E_t" in str(s["layout"].get("title", ""))]


# UT6 — citire exclusivă: tribunalul real neschimbat; blocul TU4-UI fără importuri tu4/scrieri/popularitate
def test_ut6_read_only(real_tree):
    assert _tree(TRIB) == real_tree
    src = UI.read_text()
    block = src[src.index("# TU4-UI (S14;"):]
    tree = ast.parse(block)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            assert name not in {"open", "write_text", "write_bytes", "chmod", "unlink", "mkdir", "rmtree", "touch",
                                "crowd_penalty", "system", "Popen", "write"}, name
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in ("os", "_tu4_os",
                                                                                                     "shutil"):
                assert fn.attr in {"get"} or fn.value.id == "_tu4_os" and fn.attr == "environ", fn.attr
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Attribute) and fn.value.attr == "environ":
                assert fn.attr == "get", fn.attr
    assert mods <= {"os", "zoneinfo"}, mods
    assert "crowd_penalty" not in block and "judecator" not in block.replace("judecătorul", "")


# UT7 — numai inserții față de copia de referință; P1, P2, P3 prezente
def test_ut7_insertions_only():
    seal = json.loads((ROOT / "tu4" / "SIGILIU_TU4_UI.json").read_text())
    assert _sha(BASE_UI.read_bytes()) == seal["replaceable"]["tu3/ui_tu3.py"]
    assert (os.stat(BASE_UI).st_mode & 0o222) == 0
    a, b = BASE_UI.read_text().splitlines(), UI.read_text().splitlines()
    ops = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
    assert {o for o, *_ in ops} <= {"equal", "insert"}
    ins = [ln for o, _, _, j1, j2 in ops if o == "insert" for ln in b[j1:j2]]
    assert any("tu4_on = tu4_sidebar_switch()" in ln and "P1" in ln for ln in ins)
    assert any("tu4_render_prospectiv(mode)" in ln and "P2" in ln for ln in ins)
    assert any("st.stop()" in ln and "P2" in ln for ln in ins)
    assert any(ln.startswith("# TU4-UI (S14;") for ln in ins) and any("def tu4_render_prospectiv(" in ln for ln in ins)
    assert seal["code_files_present"] == [] and seal["results_present"] is False
