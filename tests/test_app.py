"""Teste UI QL649 cu streamlit.testing.v1.AppTest (mod FAST pentru viteză + un test pe protocol)."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from streamlit.testing.v1 import AppTest  # noqa: E402


def _app(tmp_path, fast=True):
    os.environ["QL649_SEAL_DIR"] = str(tmp_path / "sigilii")
    if fast:
        os.environ["QL649_CONFIG"] = "fast"
    else:
        os.environ.pop("QL649_CONFIG", None)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=600)
    at.run()
    return at


def _variant_cards(at):
    return [m for m in at.markdown if 'class="ql-variant' in m.value]


def test_app_renders_all_tabs_and_three_variants(tmp_path):
    at = _app(tmp_path)
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.tabs) == 12
    cards = _variant_cards(at)
    assert len(cards) == 3
    import re
    variants = [tuple(int(x) for x in re.findall(r'class="ql-ball">(\d+)<', c.value)) for c in cards]
    assert all(len(v) == 6 and len(set(v)) == 6 and all(1 <= n <= 49 for n in v) for v in variants)
    assert len(set(variants)) == 3
    text = " ".join(m.value for m in at.markdown)
    assert "positive_claims_allowed=false" in text and "QUANTUM LAB 649" in text
    assert any("BO649-P1" in c.value for c in at.caption)                 # tab 7 BO649 (read-only)
    assert any("WU649-P1" in c.value for c in at.caption)                 # tab 8 WU649 (read-only)
    assert any("SE649-P1" in c.value for c in at.caption)                 # tab 10 SE649 (read-only)
    assert any("CS649-P1" in c.value for c in at.caption)                 # tab 11 CS649 (read-only)
    assert any("PL649-P1" in c.value for c in at.caption)                 # tab 12 PL649 (v2.0)
    assert len(at.dataframe) >= 3          # tab1, tab2 (perechi), tab4 (+ tab5/6 când există rezultate)


def test_app_seal_and_ablation(tmp_path):
    at = _app(tmp_path)
    at.button(key="seal_btn").click().run()
    assert not at.exception
    seals = list((tmp_path / "sigilii").glob("SIGILIU_*.json"))
    assert len(seals) == 1
    d = json.loads(seals[0].read_text())
    assert len(d["payload"]["variants"]) == 3 and len(d["sha256"]) == 64
    at.checkbox(key="abl_kur").uncheck()
    at.button(key="abl_submit").click().run()
    assert not at.exception
    assert len(_variant_cards(at)) == 6                    # 3 protocol/fast + 3 ablație


@pytest.mark.skipif(os.environ.get("QL649_UI_PROTOCOL") != "1", reason="setează QL649_UI_PROTOCOL=1 pentru testul pe protocol")
def test_app_protocol_config(tmp_path):
    at = _app(tmp_path, fast=False)
    assert not at.exception
    assert len(_variant_cards(at)) == 3
    assert "MOD FAST" not in " ".join(m.value for m in at.markdown)
