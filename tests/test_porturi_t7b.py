"""Teste TU3-T7B (PROTOCOL_TU3_T7B.md §7): porturile DESCRIPTIVE GL (tab 9) și SE (tab 10) în 5/40 și Joker, sub
protocolul comun al porturilor (PROTOCOL_TU3_T7A §3, P1–P8).

Testele NU scriu în afara directoarelor temporare, NU rulează codul pistelor închise (gl649/, se649/ se citesc numai ca
artefacte de referință) și NU recalculează scoruri, porți, bilete sau verdicte. AppTest-ul taburilor este în
tests/test_porturi_712.py P8 (o singură rulare pe mod). B8/B9 cer raportul `tu3/rezultate/T7B/IDENTITATE_T7B_*.json` și
înregistrarea `tu3/inlocuiri/INLOCUIRE_T7B_*.json` (scrise după testele de cod, §8 pașii 4–5).
Calcul clasic (exact în Q + NumPy float64, CPU). Variantele produsului = minime de energie, NU predicții.
positive_claims_allowed=false.
TU3-T7C (PROTOCOL_TU3_T7C.md §7): B7 cere acum `== 0` în U3/U4; B8 cere ca lanțul pornit din `from`-ul T7B să ajungă la
sha-ul curent (prin INLOCUIRE_T7C_*).
"""
import ast
import difflib
import hashlib
import json
import math
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
TU3 = ROOT / "tu3"
for _p in (str(ROOT), str(TU3)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import inlocuiri_tu3 as INL  # noqa: E402
import porturi_712 as PT  # noqa: E402

SEAL_P = TU3 / "SIGILIU_TU3_T7B.json"
SEAL = json.loads(SEAL_P.read_text())
SEAL_T7A = json.loads((TU3 / "SIGILIU_TU3_T7A.json").read_text())
PROTO = TU3 / "PROTOCOL_TU3_T7B.md"
PORT = TU3 / "porturi_712.py"
BASE_UI = ROOT / "tests" / "baseline" / "ui_tu3_pre_t7b.py"
BASE_PT = ROOT / "tests" / "baseline" / "porturi_712_pre_t7b.py"
REPLACEABLE = {"tu3/ui_tu3.py": "1128492b", "tests/test_app_tu3.py": "ca849e6f", "tu3/porturi_712.py": "88dd168b",
               "tests/test_porturi_712.py": "68cb1efc"}


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _ro(p) -> bool:
    return (os.stat(p).st_mode & 0o222) == 0


def _random_counts(rng, n_draws: int, N: int, kappa: int) -> list[int]:
    c = np.zeros(N, dtype=np.int64)
    for _ in range(n_draws):
        c[rng.choice(N, kappa, replace=False)] += 1
    return [int(t) for t in c]


# ---------------- B1: sigiliul protocolului, scris ÎNAINTE de cod ----------------
def test_B1_seal_before_code():
    assert _sha(PROTO) == SEAL["sha256"] and SEAL["file"] == PROTO.name and SEAL["protocol"] == "TU3-T7B"
    assert SEAL["code_files_present"] == [] and SEAL["results_present"] is False
    assert SEAL["replacement_mechanism"] == INL.MECHANISM and SEAL["positive_claims_allowed"] is False
    assert _ro(SEAL_P) and _ro(PROTO)
    assert set(SEAL["replaceable"]) == set(REPLACEABLE)
    for k, pre in REPLACEABLE.items():
        assert SEAL["replaceable"][k].startswith(pre), k
    assert SEAL["common_protocol"]["sha256"] == _sha(TU3 / "PROTOCOL_TU3_T7A.md") == SEAL_T7A["sha256"]
    for f in ("tests/test_porturi_t7b.py", "tests/baseline/ui_tu3_pre_t7b.py", "tests/baseline/porturi_712_pre_t7b.py"):
        assert f in SEAL["new_files_planned"] and f not in SEAL["frozen_hashes"]
    assert SEAL["baseline_copies_must_equal"] == {"tests/baseline/ui_tu3_pre_t7b.py": SEAL["replaceable"]["tu3/ui_tu3.py"],
                                                  "tests/baseline/porturi_712_pre_t7b.py":
                                                      SEAL["replaceable"]["tu3/porturi_712.py"]}
    assert _sha(BASE_UI) == SEAL["replaceable"]["tu3/ui_tu3.py"] and _ro(BASE_UI)
    assert _sha(BASE_PT) == SEAL["replaceable"]["tu3/porturi_712.py"] and _ro(BASE_PT)
    assert SEAL["sealed_utc"] < "2026-10-27T14:40:00Z" and SEAL["sealed_utc"] > SEAL_T7A["sealed_utc"]


# ---------------- B2: fișierele protejate byte-identice; portul nu importă pistele/modelele ----------------
def test_B2_frozen_identical_and_imports():
    bad = [k for k, h in SEAL["frozen_hashes"].items() if not (ROOT / k).is_file() or _sha(ROOT / k) != h]
    bad += [k for k, h in SEAL["frozen_external"].items() if _sha(k) != h]
    assert bad == []
    fz = SEAL["frozen_hashes"]
    assert set(SEAL_T7A["frozen_hashes"]) <= set(fz) and SEAL["frozen_external"] == SEAL_T7A["frozen_external"]
    for k in ("engine.py", "parser.py", "tu3/parser_multi.py", "tu3/motor_n.py", "tu3/motor_joker.py", "run_app.sh",
              "run_app_tu3.sh", "porneste_aplicatia.sh", "porneste_aplicatia_tu3.sh", "tu3/arhiva_live.py",
              "tu3/dedup_live.py", "validare.py", "app.py", "tu3/inlocuiri_tu3.py", "tu3/matrice_init.py",
              "tu3/validare_tu3.py", "tests/test_l649.py", "tu3/PROTOCOL_TU3_T7A.md", "tu3/SIGILIU_TU3_T7A.json",
              "tests/baseline/ui_tu3_pre_t7a.py", "gl649/gl649.py", "se649/se649.py",
              "gl649/rezultate/backtest_unic/REZULTATE.json", "se649/rezultate/backtest_unic/REZULTATE.json"):
        assert k in fz, k
    assert any(k.startswith("tu3/rezultate/T7A/IDENTITATE_T7A_") for k in fz)
    assert any(k.startswith("tu3/inlocuiri/INLOCUIRE_T7A_") for k in fz)
    for d in ("gl649", "se649", "bo649", "wu649"):    # pistele închise: TOATE fișierele în sigiliu, niciun fișier nou
        cur = {str(p.relative_to(ROOT)) for p in (ROOT / d).rglob("*") if p.is_file()}
        assert cur == {k for k in fz if k.startswith(d + "/")}, d
    mods = set()
    for node in ast.walk(ast.parse(PORT.read_text())):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert not mods & {"gl649", "se649", "bo649", "wu649", "engine", "validare", "motor_n", "motor_joker", "torch",
                       "streamlit"}, mods
    assert mods <= set(sys.stdlib_module_names) | {"__future__", "numpy", "parser"}, mods


# ---------------- B3: identitatea pe 6/49 (subprocese) ----------------
def _identity(which: str) -> dict:
    p = subprocess.run([sys.executable, "-B", str(PORT), "--identitate", which], capture_output=True, text=True,
                       timeout=1800)
    assert p.returncode == 0, p.stderr[-3000:]
    return json.loads(p.stdout)


def test_B3_identity_gl():
    r = _identity("gl")
    assert r["verdict"] in ("IDENTITATE_EXACTA", "IDENTITATE_NUMERICA"), r["rows"]
    assert {x["name"] for x in r["rows"]} == {"source_sha256", "predictions_sha256", "gamma_last_relative", "step_last",
                                             "n_draws_last", "sum_exact_ok", "z_perp_ok", "hyper_49_6"}
    assert r["source_sha256"].startswith("193eaf7a") and r["scores_recomputed"] is False
    assert r["step_compared"] == r["n_steps"] - 1


def test_B3_identity_se():
    r = _identity("se")
    assert r["verdict"] in ("IDENTITATE_EXACTA", "IDENTITATE_NUMERICA"), r["rows"]
    assert {x["name"] for x in r["rows"]} == {"source_sha256", "predictions_sha256", "n_per_season", "weights_keys",
                                             "weights_by_target_season", "G_label_x_season", "wsum_lt1_ok",
                                             "hyper_49_6"}
    assert r["source_sha256"].startswith("193eaf7a") and r["scores_recomputed"] is False


# ---------------- B4: certificat GL exact în Q ----------------
def test_B4_gl_constants_and_glyphs():
    K = PT.gl_constants(49, 6)
    assert (K["sg2"], K["se2"], K["sigma0_2"]) == (Fraction(9, 60025), Fraction(9, 240100), Fraction(43, 392))
    G = PT.gl_structure(49)["G"]
    assert G[10][1] == 2 and G[21][2] == 2 and G[32][3] == 2 and G[43][4] == 2          # 11, 22, 33, 44
    assert [j + 1 for j in range(49) if G[j][0]] == [10, 20, 30, 40]
    assert all(sum(G[j]) == len(str(j + 1)) for j in range(49))
    for N in (20, 40, 45):
        assert all(c > 0 for c in PT.gl_structure(N)["colsum"]), N                     # toate cifrele 0..9 apar


@pytest.mark.parametrize("N,kappa", [(49, 6), (40, 6), (45, 5), (20, 1)])
def test_B4_gl_woodbury_equals_direct(N, kappa):
    rng = np.random.default_rng([649, 9, 7, N, kappa])
    for _ in range(2):
        n = int(rng.integers(30, 200))
        c = _random_counts(rng, n, N, kappa)
        r = PT.gl_predict_counts(c, n, N, kappa)
        assert r["p"] == PT.gl_predict_direct(c, n, N, kappa)                          # egalitate EXACTĂ în Q
        assert sum(r["p"]) == kappa and sum(r["z"]) == 0
        d = PT.gl_describe(c, n, N, kappa)
        assert d["sum_exact_ok"] and d["z_perp_ok"] and len(d["gamma_rel"]) == 10
        assert PT.forbidden_keys_t7b(d) == []


# ---------------- B5: certificat SE exact în Q ----------------
def test_B5_se_constants_and_seasons():
    K = PT.se_constants(49, 6)
    assert (K["ta2"], K["tb2"], K["sigma0_2"]) == (Fraction(9, 240100), Fraction(36, 60025), Fraction(43, 392))
    assert [PT.season_of(f"2020-{m:02d}-15") for m in range(1, 13)] == [0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 0]


@pytest.mark.parametrize("N,kappa", [(49, 6), (40, 6), (45, 5), (20, 1)])
def test_B5_se_closed_form_equals_direct(N, kappa):
    rng = np.random.default_rng([649, 10, 7, N, kappa])
    K = PT.se_constants(N, kappa)
    for trial in range(6):
        ns = [int(rng.integers(0 if trial % 2 else 1, 60)) for _ in range(4)]
        if sum(ns) == 0:
            ns[0] = 5
        C4 = [_random_counts(rng, ns[f], N, kappa) for f in range(4)]
        for phi in range(4):
            w = PT.se_weights(ns, phi, K["ta2"], K["tb2"], K["sigma0_2"])
            assert w == PT.se_weights_direct(ns, phi, K["ta2"], K["tb2"], K["sigma0_2"])      # EXACT în Q
            assert sum(w.values()) < 1
            r = PT.se_predict_counts(C4, ns, phi, N, kappa)
            assert sum(r["p"]) == kappa and all(0 < t < 1 for t in r["p"])
            assert r["p"] == PT.se_predict_counts(C4, ns, phi, N, kappa, direct=True)["p"]


def test_B5_g_statistic_by_hand():
    rng = np.random.default_rng([649, 10, 8])
    N, kappa = 12, 3
    steps, dates = [], []
    for i in range(40):
        a = np.zeros((1, N))
        a[0, rng.choice(N, kappa, replace=False)] = 1.0
        steps.append(a)
        dates.append(f"2021-{1 + (i % 12):02d}-0{1 + i // 12}")
    d = PT.se_describe(steps, dates, N, kappa)
    seasons = [PT.season_of(x) for x in dates]
    G = 0.0
    for f in range(4):
        nf = sum(1 for s in seasons if s == f)
        for j in range(N):
            c = sum(steps[i][0, j] for i in range(40) if seasons[i] == f)
            if c > 0:
                G += 2.0 * c * math.log(c / (kappa * nf / N))
    assert abs(d["G"] - G) <= 1e-9 and sum(d["n_per_season"]) == 40 and d["wsum_lt1_ok"]
    assert PT.forbidden_keys_t7b(d) == []


# ---------------- B6: rulare generică pe 5/40 și Joker (LIVE) ----------------
@pytest.mark.parametrize("game", ["540", "joker"])
def test_B6_generic_live(game):
    import parser_multi as PM
    ds = PM.build_game_dataset(game, "live", device="cpu")
    jo = None if ds.joker_onehot is None else ds.joker_onehot.numpy()
    comps = PT.components(ds.onehot.numpy(), ds.step_offsets.numpy(), ds.game.n, ds.game.r, jo, ds.game.joker_m)
    Gl, Se = PT.describe_gl(comps), PT.describe_se(comps, ds.step_dates)
    assert [g["key"] for g in Gl] == [s["key"] for s in Se] == [c["key"] for c in comps]
    for c, g, s in zip(comps, Gl, Se):
        assert g["N"] == s["N"] == c["N"] and g["kappa"] == s["kappa"] == c["kappa"]
        assert g["n_draws"] == s["n_draws"] == ds.n_draws and s["n_steps"] == ds.n_steps
        assert g["sum_exact_ok"] and g["z_perp_ok"] and np.isfinite(g["gamma_rel"]).all()
        assert np.isfinite(g["glyph_freq_rel"]).all() and sum(g["glyph_labels"]) >= c["N"]
        assert sum(s["n_per_season"]) == ds.n_draws and min(s["n_per_season"]) > 0 and s["wsum_lt1_ok"]
        assert math.isfinite(s["G"]) and s["G"] >= 0
        assert list(s["weights_by_target_season"]) == PT.SEASON_NAMES
        fr = np.asarray(s["freq_rel_season"])
        assert fr.shape == (c["N"], 4) and np.isfinite(fr).all()
    assert PT.forbidden_keys_t7b(Gl) == [] and PT.forbidden_keys_t7b(Se) == []


# ---------------- B7: numai inserții față de copiile de referință ----------------
def _insert_only(a: str, b: str) -> list[str]:
    a, b = a.splitlines(), b.splitlines()
    ops = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
    assert {o for o, *_ in ops} <= {"equal", "insert"}, [o for o in ops if o[0] not in ("equal", "insert")][:3]
    return [ln for o, _, _, j1, j2 in ops if o == "insert" for ln in b[j1:j2]]


def test_B7_insertions_only():
    ins = _insert_only(BASE_UI.read_text(), (TU3 / "ui_tu3.py").read_text())
    assert any("TU3-T7B" in ln for ln in ins) and any("t7b_port(t_idx, tabs[t_idx]" in ln for ln in ins)
    ins = _insert_only(BASE_PT.read_text(), PORT.read_text())
    assert any("TU3-T7B" in ln for ln in ins) and any("def gl_describe(" in ln for ln in ins)
    assert any("def se_describe(" in ln for ln in ins)
    t = (ROOT / "tests" / "test_app_tu3.py").read_text()
    seg = t.split("def test_u3_u4")[1][:1200]
    # TU3-T7C (PROTOCOL_TU3_T7C §7): după S6 toate taburile 7–12 sunt porturi ⇒ U3/U4 cer `== 0`
    assert 'sum("NEAPLICABIL" in i.value for i in at.info) == 0' in seg and "== 4" not in seg and "== 6" not in seg


# ---------------- B8: înregistrarea de înlocuire (după testele de cod) ----------------
def test_B8_replacement_record():
    recs = sorted((TU3 / "inlocuiri").glob("INLOCUIRE_T7B_*.json"))
    assert recs, "înregistrarea INLOCUIRE_T7B_*.json lipsește (se scrie după testele de cod, §8 pasul 5)"
    valid, invalid = INL.load_records(ROOT)
    assert invalid == [] and recs[-1].name in {r["_name"] for r in valid}
    rec = json.loads(recs[-1].read_text())
    assert rec["seal"] == "tu3/SIGILIU_TU3_T7B.json" and set(rec["replacements"]) == set(REPLACEABLE)
    for rel, ft in rec["replacements"].items():   # TU3-T7C: lanțul pornit din `from`-ul T7B ajunge la sha-ul curent
        assert ft["from"] == SEAL["replaceable"][rel]
        st_, chain = INL.resolve_one(rel, ft["from"], ROOT, valid)
        assert st_ == "inlocuit" and chain[0] == recs[-1].name, (rel, st_, chain)
    rep = INL.verify_all(ROOT)
    assert rep["ok"] is True
    vs = rep["seals"]["tu3/SIGILIU_TU3_VS.json"]
    assert {"tu3/ui_tu3.py", "tests/test_app_tu3.py"} <= set(vs["replaced"]) and recs[-1].name in vs["records"]
    l649 = json.loads((TU3 / "SIGILIU_TU3_L649.json").read_text())
    for s in ("tu3/SIGILIU_TU3_VS.json", "tu3/SIGILIU_TU3_DD.json", "tu3/SIGILIU_TU3_LN.json"):
        assert set(rep["seals"][s]["replaced"]) <= set(l649["replaceable"]), s


# ---------------- B9: raportul de identitate T7B (P3, 0444) ----------------
def test_B9_identity_report():
    fs = sorted((TU3 / "rezultate" / "T7B").glob("IDENTITATE_T7B_*.json"))
    assert fs, "raportul IDENTITATE_T7B_*.json lipsește (§8 pasul 4)"
    d = json.loads(fs[-1].read_text())
    assert _ro(fs[-1]) and d["verdict"] == "PASS" and d["protocol"] == "TU3-T7B"
    assert d["protocol_sha256"] == SEAL["sha256"] and d["written_utc"] > SEAL["sealed_utc"]
    assert d["GL"]["verdict"] in ("IDENTITATE_EXACTA", "IDENTITATE_NUMERICA")
    assert d["SE"]["verdict"] in ("IDENTITATE_EXACTA", "IDENTITATE_NUMERICA")
    assert d["positive_claims_allowed"] is False
    li = PT.latest_identity_t7b()
    assert li["file"] == fs[-1].name and li["verdict"] == "PASS"
