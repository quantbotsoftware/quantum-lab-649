"""TU3-VS — teste pentru matricea de inițializare, suita de validare și `run_app.sh` (PROTOCOL_TU3_VS §5).

Nu tipăresc, nu salvează și nu compară variante (nici reale, nici sintetice).
"""
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import torch

QL = Path(__file__).resolve().parents[1]
TU3 = QL / "tu3"
for _p in (str(TU3), str(QL)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import matrice_init as MI  # noqa: E402
import validare_tu3 as VS  # noqa: E402

SEAL = json.loads((TU3 / "SIGILIU_TU3_VS.json").read_text())


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------- T1: matricea nu rulează motoare și nu conține variante ----------------
def test_T1_matrix_no_engine_no_variants(monkeypatch, tmp_path, capsys):
    import engine as E
    import motor_joker as MJ
    import motor_n as M

    def boom(*a, **k):
        raise AssertionError("matricea a apelat un motor")

    for mod, name in ((E, "run_full"), (M, "run_full"), (M, "run_full_540"), (M, "score_steps"),
                      (M, "variants_steps"), (MJ, "engine_joker"), (MJ, "run_full_joker"), (E, "score_steps")):
        monkeypatch.setattr(mod, name, boom)
    rc = MI.main(["--out-dir", str(tmp_path)])
    out = capsys.readouterr().out
    files = list(tmp_path.glob("MATRICE_INIT_*.json"))
    assert rc == 0 and len(files) == 1
    m = json.loads(files[0].read_text())
    assert [r["mode"] for r in m["modes"]] == ["649", "540", "joker"]
    assert all(r["status"] == "READY" for r in m["modes"]) and m["integrity"]["status"] == "OK" and m["ok"] is True
    assert m["positive_claims_allowed"] is False and "positive_claims_allowed=false" in out
    assert "variants" not in json.dumps(m) and "last_key" not in json.dumps(m)
    r649, r540, rj = m["modes"]
    assert r649["source_kind"] == "frozen" and r649["frozen_sha_verified"] is True
    assert r540["source_kind"] == "live" and r540["power_verdict"] == "E40_PASS" and r540["power_code_hashes_match"]
    assert rj["source_kind"] == "live" and rj["power_verdict"] == "EJ_PASS" and rj["power_code_hashes_match"]
    assert m["system"]["address"] == "127.0.0.1" and m["system"]["port"] == 8649
    assert "TOATE 3 MODURILE READY" in out


# ---------------- T2: reverificarea puterii detectează falsificarea ----------------
@pytest.mark.parametrize("key", ["J", "E40", "EJ"])
def test_T2_power_reverify_real_and_tampered(tmp_path, key):
    assert VS.reverify_power(key)["pass"] is True
    sp = VS.POWER_SPECS[key]
    orig = json.loads(sp["file"].read_text())
    first_gate, op, thr, flag = sp["gates"][0]

    def bad_gate(d):
        v = d[first_gate]
        worse = 0.0 if op == ">=" else 1.0
        d[first_gate] = {k: worse for k in v} if isinstance(v, dict) else worse

    tampers = {
        "verdict": lambda d: d.__setitem__("verdict", sp["verdict"].replace("PASS", "FAIL")),
        "code": lambda d: d["code_sha256"].__setitem__(next(iter(d["code_sha256"])), "0" * 64),
        "protocol": lambda d: d.__setitem__("protocol_sha256", "f" * 64),
        "gate_value": bad_gate,
        "gate_flag": lambda d: d.__setitem__(flag, False),
        "real_archive": lambda d: d.__setitem__("real_archive_read", True),
        "witness": lambda d: d[sp["witnesses"]].__setitem__("pass", False),
    }
    for name, f in tampers.items():
        d = copy.deepcopy(orig)
        f(d)
        p = tmp_path / f"{key}_{name}.json"
        p.write_text(json.dumps(d))
        assert VS.reverify_power(key, p)["pass"] is False, name
    ok = tmp_path / f"{key}_copy.json"
    ok.write_text(json.dumps(orig))
    assert VS.reverify_power(key, ok)["pass"] is True


# ---------------- T3: run_app.sh byte-identic; inserțiile în run_app_tu3.sh (AMENDAMENT_TU3_VS_01) ----------------
def test_T3_run_app_identical_and_launcher():
    base = QL / "tests" / "baseline" / "run_app_v2.sh"
    assert sha(base) == SEAL["run_app_sh_before"] == "a8f38cea330a803e55ecaa3fb74fe2886e502bd420575f3a7a72f41b4e1037e5"
    assert sha(QL / "run_app.sh") == SEAL["run_app_sh_before"]
    new = (QL / "run_app.sh").read_text()
    assert VS.insertions_only(base.read_text(), new)
    assert not VS.insertions_only(base.read_text(), new.replace("127.0.0.1", "0.0.0.0"))   # martor negativ
    launcher = QL / "run_app_tu3.sh"
    lt = launcher.read_text()
    for p in (QL / "run_app.sh", launcher):
        assert subprocess.run(["bash", "-n", str(p)]).returncode == 0
    assert "tu3/matrice_init.py" in lt and 'MATRIX="jurnal/matrice_$(date -u +%Y%m%dT%H%M%SZ).txt"' in lt
    assert lt.rstrip().endswith("exec ./run_app.sh") and "0.0.0.0" not in lt
    assert '--server.address "127.0.0.1"' in new
    inc = json.loads((TU3 / "incidente" / "VS_01" / "INCIDENT_TEHNIC_VS_01.json").read_text())
    assert sha(TU3 / "incidente" / "VS_01" / "run_app.sh") == inc["modified_run_app_sha256"]
    am = json.loads((TU3 / "SIGILIU_AMENDAMENT_TU3_VS_01.json").read_text())
    assert sha(TU3 / "AMENDAMENT_TU3_VS_01.md") == am["sha256"] and am["run_app_tu3_present"] is False


# ---------------- T4: fișierele NEMODIFICATE ----------------
def test_T4_frozen_hashes():
    import inlocuiri_tu3 as INL   # TU3-L649 §5.4: fișier înghețat = identic SAU înlocuit sigilat (inlocuiri_tu3/v1)
    res = INL.resolve(SEAL["frozen_hashes"], QL)
    assert res["drift"] == [], res["drift"]
    l649 = json.loads((TU3 / "SIGILIU_TU3_L649.json").read_text())
    assert set(res["replaced"]) <= set(l649["replaceable"]), res["replaced"]
    fh = SEAL["frozen_hashes"]
    assert fh["engine.py"].startswith("1da9be4e") and fh["parser.py"].startswith("219e5d20")
    assert fh["tu3/parser_multi.py"].startswith("4c4b0f34") and fh["tu3/motor_n.py"].startswith("28e8eede")
    assert fh["tu3/motor_joker.py"].startswith("95960c26") and fh["app.py"].startswith("051dd839")
    assert SEAL["code_files_present"] == [] and SEAL["results_present"] is False
    assert sha(TU3 / "PROTOCOL_TU3_VS.md") == SEAL["sha256"]
    assert VS.integrity_check()["pass"] is True


# ---------------- T5: produsul pe toate 3 căile sintetice (FAST) ----------------
@pytest.mark.parametrize("game", ["649", "540", "joker"])
def test_T5_synthetic_product(tmp_path, game):
    r = VS.synthetic_product(game, tmp_path)
    assert r["pass"] is True, r["checks"]
    assert r["rows"] == 200 and r["n_draws"] == 200
    assert not re.search(r'"variants[^"]*"\s*:', json.dumps(r))      # nicio cheie de variante (numai booleene)
    if torch.cuda.is_available():
        assert r["device"].startswith("cuda")


def test_T5b_fast_overrides_match_ui():
    src = (TU3 / "ui_tu3.py").read_text()
    assert "FAST_OVERRIDES = dict(mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60, gamma_grid=12)" in src
    assert VS.FAST_OVERRIDES == dict(mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60, gamma_grid=12)


# ---------------- T6: parserul numărătorilor pytest ----------------
def test_T6_parse_pytest_counts():
    c = VS.parse_pytest_counts("..s.........ss   [100%]\n11 passed, 3 skipped in 15.87s\n")
    assert (c["passed"], c["skipped"], c["failed"], c["errors"]) == (11, 3, 0, 0)
    c = VS.parse_pytest_counts("....\n53 passed in 99.70s (0:01:39)\n")
    assert c["passed"] == 53 and c["skipped"] == 0
    c = VS.parse_pytest_counts("F.E\n1 failed, 1 passed, 1 error in 2.00s\n")
    assert (c["passed"], c["failed"], c["errors"]) == (1, 1, 1)
    c = VS.parse_pytest_counts("=== 2 failed, 30 passed, 2 warnings in 10.1s ===")
    assert (c["passed"], c["failed"], c["warnings"]) == (30, 2, 2)
    assert VS.parse_pytest_counts("nimic")["passed"] == 0
