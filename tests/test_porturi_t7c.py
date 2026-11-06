"""Teste TU3-T7C (PROTOCOL_TU3_T7C.md §7): porturile DESCRIPTIVE CS (tab 11) și PL (tab 12) în 5/40 și Joker, sub
protocolul comun al porturilor (PROTOCOL_TU3_T7A §3, P1–P8).

Testele NU scriu în afara directoarelor temporare, NU rulează codul pistelor închise (cs649/, pl649/ se citesc numai ca
artefacte de referință; formele de referință necesare certificatelor — `cs649.primal_predict`, `pl649.ref_links` /
`ref_curvature` — sunt rescrise aici, nu importate) și NU recalculează scoruri, porți, bilete, variante sau verdicte.
AppTest-ul taburilor este în tests/test_porturi_712.py P8 (o singură rulare pe mod). C8/C9 cer înregistrarea
`tu3/inlocuiri/INLOCUIRE_T7C_*.json` și raportul `tu3/rezultate/T7C/IDENTITATE_T7C_*.json` (§8 pașii 4–5).
Calcul clasic pe CPU (CS: exact în Q + NumPy float64; PL: NumPy complex128). Variantele produsului = minime de energie,
NU predicții. positive_claims_allowed=false.
"""
import ast
import difflib
import hashlib
import itertools
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

SEAL_P = TU3 / "SIGILIU_TU3_T7C.json"
SEAL = json.loads(SEAL_P.read_text())
SEAL_T7A = json.loads((TU3 / "SIGILIU_TU3_T7A.json").read_text())
SEAL_T7B = json.loads((TU3 / "SIGILIU_TU3_T7B.json").read_text())
PROTO = TU3 / "PROTOCOL_TU3_T7C.md"
PORT = TU3 / "porturi_712.py"
BASE_UI = ROOT / "tests" / "baseline" / "ui_tu3_pre_t7c.py"
BASE_PT = ROOT / "tests" / "baseline" / "porturi_712_pre_t7c.py"
REPLACEABLE = {"tu3/ui_tu3.py": "c5a94a44", "tests/test_app_tu3.py": "28156da4", "tu3/porturi_712.py": "3dea1aaa",
               "tests/test_porturi_712.py": "2c83417a", "tests/test_porturi_t7b.py": "7e85184d"}


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _ro(p) -> bool:
    return (os.stat(p).st_mode & 0o222) == 0


def _random_steps(rng, n_steps: int, N: int, kappa: int, p2: float = 0.15) -> list[np.ndarray]:
    out = []
    for _ in range(n_steps):
        a = np.zeros((2 if rng.random() < p2 else 1, N))
        for i in range(a.shape[0]):
            a[i, rng.choice(N, kappa, replace=False)] = 1.0
        out.append(a)
    return out


# ---------------- C1: sigiliul protocolului, scris ÎNAINTE de cod ----------------
def test_C1_seal_before_code():
    assert _sha(PROTO) == SEAL["sha256"] and SEAL["file"] == PROTO.name and SEAL["protocol"] == "TU3-T7C"
    assert SEAL["code_files_present"] == [] and SEAL["results_present"] is False
    assert SEAL["replacement_mechanism"] == INL.MECHANISM and SEAL["positive_claims_allowed"] is False
    assert _ro(SEAL_P) and _ro(PROTO)
    assert set(SEAL["replaceable"]) == set(REPLACEABLE)
    for k, pre in REPLACEABLE.items():
        assert SEAL["replaceable"][k].startswith(pre), k
    assert SEAL["common_protocol"]["sha256"] == _sha(TU3 / "PROTOCOL_TU3_T7A.md") == SEAL_T7A["sha256"]
    assert SEAL["previous_port_seal"]["sha256"] == _sha(TU3 / "SIGILIU_TU3_T7B.json")
    for f in ("tests/test_porturi_t7c.py", "tests/baseline/ui_tu3_pre_t7c.py", "tests/baseline/porturi_712_pre_t7c.py"):
        assert f in SEAL["new_files_planned"] and f not in SEAL["frozen_hashes"]
    assert SEAL["baseline_copies_must_equal"] == {"tests/baseline/ui_tu3_pre_t7c.py": SEAL["replaceable"]["tu3/ui_tu3.py"],
                                                  "tests/baseline/porturi_712_pre_t7c.py":
                                                      SEAL["replaceable"]["tu3/porturi_712.py"]}
    assert _sha(BASE_UI) == SEAL["replaceable"]["tu3/ui_tu3.py"] and _ro(BASE_UI)
    assert _sha(BASE_PT) == SEAL["replaceable"]["tu3/porturi_712.py"] and _ro(BASE_PT)
    assert SEAL_T7B["sealed_utc"] < SEAL["sealed_utc"] < "2026-10-27T15:12:00Z"


# ---------------- C2: fișierele protejate byte-identice; portul nu importă pistele/modelele ----------------
def test_C2_frozen_identical_and_imports():
    bad = [k for k, h in SEAL["frozen_hashes"].items() if not (ROOT / k).is_file() or _sha(ROOT / k) != h]
    bad += [k for k, h in SEAL["frozen_external"].items() if _sha(k) != h]
    assert bad == []
    fz = SEAL["frozen_hashes"]
    assert set(SEAL_T7B["frozen_hashes"]) <= set(fz) and SEAL["frozen_external"] == SEAL_T7B["frozen_external"]
    for k in ("engine.py", "parser.py", "tu3/parser_multi.py", "tu3/motor_n.py", "tu3/motor_joker.py", "run_app.sh",
              "run_app_tu3.sh", "porneste_aplicatia.sh", "porneste_aplicatia_tu3.sh", "tu3/arhiva_live.py",
              "tu3/dedup_live.py", "validare.py", "app.py", "tu3/inlocuiri_tu3.py", "tu3/matrice_init.py",
              "tu3/validare_tu3.py", "tests/test_l649.py", "tu3/PROTOCOL_TU3_T7B.md", "tu3/SIGILIU_TU3_T7B.json",
              "tests/baseline/ui_tu3_pre_t7b.py", "tests/baseline/porturi_712_pre_t7b.py", "cs649/cs649.py",
              "pl649/pl649.py", "pl649/pl_core.py", "pl649/ui_pl649.py", "cs649/rezultate/backtest_unic/REZULTATE.json",
              "pl649/rezultate/final/FINAL.json", "pl649/rezultate/backtest_unic/PREDICTII.npz"):
        assert k in fz, k
    assert any(k.startswith("tu3/rezultate/T7B/IDENTITATE_T7B_") for k in fz)
    assert any(k.startswith("tu3/inlocuiri/INLOCUIRE_T7B_") for k in fz)
    for d in ("cs649", "pl649", "gl649", "se649", "bo649", "wu649"):   # pistele închise: TOATE fișierele, niciunul nou
        cur = {str(p.relative_to(ROOT)) for p in (ROOT / d).rglob("*") if p.is_file()}
        assert cur == {k for k in fz if k.startswith(d + "/")}, d
    mods = set()
    for node in ast.walk(ast.parse(PORT.read_text())):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert not mods & {"cs649", "pl649", "pl_core", "ui_pl649", "gl649", "se649", "bo649", "wu649", "engine",
                       "validare", "motor_n", "motor_joker", "torch", "streamlit"}, mods
    assert mods <= set(sys.stdlib_module_names) | {"__future__", "numpy", "parser"}, mods


# ---------------- C3: identitatea pe 6/49 (subprocese) ----------------
def _identity(which: str) -> dict:
    p = subprocess.run([sys.executable, "-B", str(PORT), "--identitate", which], capture_output=True, text=True,
                       timeout=1800)
    assert p.returncode == 0, p.stderr[-3000:]
    return json.loads(p.stdout)


def test_C3_identity_cs():
    r = _identity("cs")
    assert r["verdict"] in ("IDENTITATE_EXACTA", "IDENTITATE_NUMERICA"), r["rows"]
    assert {x["name"] for x in r["rows"]} == {"source_sha256", "predictions_sha256", "exact_predictions_sha256",
                                             "level_names", "n_per_level", "v_for_next_index", "next_index",
                                             "next_phases", "G3", "G5", "G7", "G_sum", "v_exact_sample",
                                             "sum_exact_ok", "hyper_49_6"}
    assert r["source_sha256"].startswith("193eaf7a") and r["scores_recomputed"] is False
    assert len(r["v_exact_sample_steps"]) == 27 and r["v_exact_sample_steps"][-1] == r["n_steps"] - 1


def test_C3_identity_pl():
    r = _identity("pl")
    assert r["verdict"] in ("IDENTITATE_EXACTA", "IDENTITATE_NUMERICA"), r["rows"]
    assert {x["name"] for x in r["rows"]} == {"source_sha256", "predictions_sha256", "n_draws", "n_steps",
                                             "area_spectrum_keys", "area_spectrum_counts", "node_kappa", "node_A",
                                             "node_V", "planck_area_total", "holonomy_max_unitarity",
                                             "holonomy_max_det", "holonomy_frac_err_zero", "top_edges_eps",
                                             "top_edges_j_x2", "frames_steps", "frames_kappa", "frames_A",
                                             "frames_V_total", "walk_ks", "walk_kappa"}
    walk = next(x for x in r["rows"] if x["name"] == "walk_kappa")
    assert walk["shape"] == [2427, 49]
    assert r["source_sha256"].startswith("193eaf7a") and r["scores_recomputed"] is False
    assert r["tickets_recomputed"] is False and r["reference_device"] == "cuda"


# ---------------- C4: certificat CS exact în Q ----------------
def _cs_primal(hist, kstar: int, N: int, kappa: int) -> list[Fraction]:
    """Forma primală N_d × N_d (rescrisă după cs649.primal_predict, parametrizată în (N, κ))."""
    K = PT.cs_constants(N, kappa)
    rows = [(k, d[i]) for k, d in hist for i in range(d.shape[0])]
    n = len(rows)
    ph = [[k % P for P in (3, 5, 7)] for k, _ in rows]
    phs = [kstar % P for P in (3, 5, 7)]
    A = [[K["ta2"] + sum(K["t2"] for a, b in zip(ph[i], ph[j]) if a == b) + (K["sigma0_2"] if i == j else 0)
          for j in range(n)] for i in range(n)]
    rhs = [[K["ta2"] + sum(K["t2"] for a, b in zip(ph[i], phs) if a == b)] for i in range(n)]
    alpha = [x[0] for x in PT.solve_exact(A, rhs)]
    return [K["p0"] + sum(alpha[i] * (int(rows[i][1][j]) - K["p0"]) for i in range(n)) for j in range(N)]


def test_C4_cs_constants():
    K = PT.cs_constants(49, 6)
    assert (K["ta2"], K["t2"], K["sigma0_2"]) == (Fraction(9, 240100), Fraction(9, 9604), Fraction(43, 392))
    assert [PT.cs_level_name(lv) for lv in range(16)] == (["a"] + [f"K3r{r}" for r in range(3)] +
                                                          [f"K5r{r}" for r in range(5)] + [f"K7r{r}" for r in range(7)])
    assert PT.cs_levels_of(104) == [0, 1 + 2, 4 + 4, 9 + 6]


@pytest.mark.parametrize("N,kappa", [(49, 6), (40, 5), (45, 5), (20, 1)])
def test_C4_cs_henderson_equals_primal(N, kappa):
    rng = np.random.default_rng([649, 11, 7, N, kappa])
    for _ in range(3):
        k0 = int(rng.integers(0, 105))
        steps = _random_steps(rng, int(rng.integers(1, 9)), N, kappa)
        hist = [(k0 + t, s) for t, s in enumerate(steps)]
        kstar = k0 + len(steps)
        st = PT.cs_new_state(N)
        for k, d in hist:
            PT.cs_add_step(st, k, d)
        r = PT.cs_v(st, kstar, N, kappa)
        assert r["p"] == _cs_primal(hist, kstar, N, kappa)                          # egalitate EXACTĂ în Q
        assert r["p"] == PT.cs_v(st, kstar, N, kappa, method="gauss_jordan")["p"]
        assert sum(r["p"]) == kappa
    d = PT.cs_describe(_random_steps(rng, 60, N, kappa), N, kappa)
    assert d["sum_exact_ok"] and len(d["v_next"]) == 16 and np.isfinite(d["v_next"]).all()
    assert np.asarray(d["freq_rel_phase"]).shape == (15, N) and PT.forbidden_keys_t7c(d) == []


# ---------------- C5: certificat PL — forma închisă, M·M vs triunghi cu triunghi ----------------
def test_C5_pl_kicks_closed_form():
    L = PT.pl_gell_mann()
    E, Ed = PT.pl_kicks()
    for k in range(8):
        X = 1j * PT.PL_EPS * L[k]
        ser, term = np.eye(3, dtype=complex), np.eye(3, dtype=complex)
        for m in range(1, 30):
            term = term @ X / m
            ser = ser + term
        assert np.abs(E[k] - ser).max() <= 1e-14
        assert np.abs(Ed[k] @ E[k] - np.eye(3)).max() <= 1e-15 and abs(np.linalg.det(E[k]) - 1) <= 1e-15


def _pl_ref(steps, N: int):
    """Referința triunghi cu triunghi (rescrisă după pl649.ref_links + ref_curvature, parametrizată în N)."""
    E = [PT.pl_exp_closed(k) for k in range(8)]
    U, n, last = {}, np.zeros((N, N), dtype=np.int64), np.full(N, -1, dtype=np.int64)
    for s, step in enumerate(steps):
        ages = last.copy()
        for row in step:
            x = sorted(np.nonzero(row)[0].tolist())
            for a, b in itertools.combinations(x, 2):
                Ek = E[n[a, b] % 8]
                u = U.get((a, b), np.eye(3, dtype=complex))
                if ages[a] < ages[b]:
                    u = Ek @ u
                elif ages[b] < ages[a]:
                    u = u @ Ek.conj().T
                U[(a, b)] = u
                n[a, b] += 1
                n[b, a] += 1
        for row in step:
            last[np.nonzero(row)[0]] = s

    def link(x, y):
        return U.get((x, y), np.eye(3, dtype=complex)) if x < y else U.get((y, x), np.eye(3, dtype=complex)).conj().T
    aa = np.sqrt((n / 2) * (n / 2 + 1))
    numn, denn = np.zeros(N), np.zeros(N)
    nume, dene = np.zeros((N, N)), np.zeros((N, N))
    for x, y, z in itertools.combinations(range(N), 3):
        w = math.sqrt(aa[x, y] * aa[y, z] * aa[x, z])
        if w == 0:
            continue
        e = 1 - np.trace(link(x, y) @ link(y, z) @ link(z, x)).real / 3
        for v in (x, y, z):
            numn[v] += w * e
            denn[v] += w
        for p, q in ((x, y), (y, z), (x, z)):
            nume[p, q] += w * e
            dene[p, q] += w
    kap = np.where(denn > 0, numn / np.where(denn > 0, denn, 1), 0.0)
    ee = np.where(dene > 0, nume / np.where(dene > 0, dene, 1), 0.0)
    pa, pb = np.triu_indices(N, 1)
    return kap, ee[pa, pb], n[pa, pb]


@pytest.mark.parametrize("N,kappa", [(9, 3), (12, 5), (8, 2)])
def test_C5_pl_geometry_equals_triangle_reference(N, kappa):
    rng = np.random.default_rng([649, 12, 7, N, kappa])
    steps = _random_steps(rng, 40, N, kappa, p2=0.25)
    run = PT.pl_run(steps, N, kappa)
    g = PT.pl_geometry(run["state"]["U"], run["state"]["n"], N)
    kap, ee, nn = _pl_ref(steps, N)
    assert np.array_equal(run["state"]["n"], nn)
    assert np.abs(g["curvature"] - kap).max() <= 1e-12 and np.abs(g["eps_edge"] - ee).max() <= 1e-12
    h = PT.pl_unitarity(run["state"]["U"])
    assert h["max_unitarity"] <= 1e-13 and h["frac_links_err_gt_1e-12"] == 0.0
    d = PT.pl_describe(steps, N, kappa)
    assert d["applicable"] and sum(d["area_spectrum"].values()) == N * (N - 1) // 2
    assert np.allclose(d["curvature_node"], kap, atol=1e-12, rtol=0) and PT.forbidden_keys_t7c(d) == []
    one = PT.pl_describe(_random_steps(rng, 10, N, 1), N, 1)
    assert one["applicable"] is False and "κ = 1" in one["reason"] and PT.forbidden_keys_t7c(one) == []


# ---------------- C6: rulare generică pe 5/40 și Joker (LIVE) ----------------
@pytest.mark.parametrize("game", ["540", "joker"])
def test_C6_generic_live(game):
    import parser_multi as PM
    ds = PM.build_game_dataset(game, "live", device="cpu")
    jo = None if ds.joker_onehot is None else ds.joker_onehot.numpy()
    comps = PT.components(ds.onehot.numpy(), ds.step_offsets.numpy(), ds.game.n, ds.game.r, jo, ds.game.joker_m)
    Cs, Pl = PT.describe_cs(comps), PT.describe_pl(comps)
    assert [c["key"] for c in Cs] == [p["key"] for p in Pl] == [c["key"] for c in comps]
    for c, s, p in zip(comps, Cs, Pl):
        assert s["N"] == p["N"] == c["N"] and s["kappa"] == p["kappa"] == c["kappa"]
        assert s["n_draws"] == p["n_draws"] == ds.n_draws and s["n_steps"] == p["n_steps"] == ds.n_steps
        nl = s["n_per_level"]
        assert sum(nl[1:4]) == sum(nl[4:9]) == sum(nl[9:16]) == nl[0] == ds.n_draws and min(nl) > 0
        assert s["sum_exact_ok"] and np.isfinite(s["v_next"]).all() and len(s["v_next_exact"]) == 16
        assert all(math.isfinite(s[g]) and s[g] >= 0 for g in ("G3", "G5", "G7", "G_sum"))
        fr = np.asarray(s["freq_rel_phase"])
        assert fr.shape == (15, c["N"]) and np.isfinite(fr).all()
        if c["kappa"] >= 2:
            NP = c["N"] * (c["N"] - 1) // 2
            assert p["applicable"] and len(p["curvature_node"]) == c["N"] and len(p["eps_edge"]) == NP
            assert np.isfinite(p["curvature_node"]).all() and np.isfinite(p["eps_edge"]).all()
            assert sum(p["area_spectrum"].values()) == NP and 0 < p["links_spun"] <= NP
            assert p["holonomy"]["frac_links_err_gt_1e-12"] == 0.0 and p["area_total"] > 0
        else:
            assert p["applicable"] is False and "κ = 1" in p["reason"]
    assert PT.forbidden_keys_t7c(Cs) == [] and PT.forbidden_keys_t7c(Pl) == []


# ---------------- C7: numai inserții față de copiile de referință ----------------
def _insert_only(a: str, b: str) -> list[str]:
    a, b = a.splitlines(), b.splitlines()
    ops = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
    assert {o for o, *_ in ops} <= {"equal", "insert"}, [o for o in ops if o[0] not in ("equal", "insert")][:3]
    return [ln for o, _, _, j1, j2 in ops if o == "insert" for ln in b[j1:j2]]


def test_C7_insertions_only():
    ins = _insert_only(BASE_UI.read_text(), (TU3 / "ui_tu3.py").read_text())
    assert any("TU3-T7C" in ln for ln in ins) and any("t7c_port(t_idx, tabs[t_idx]" in ln for ln in ins)
    ins = _insert_only(BASE_PT.read_text(), PORT.read_text())
    assert any("TU3-T7C" in ln for ln in ins) and any("def cs_describe(" in ln for ln in ins)
    assert any("def pl_describe(" in ln for ln in ins)
    t = (ROOT / "tests" / "test_app_tu3.py").read_text()
    seg = t.split("def test_u3_u4")[1][:1200]
    assert 'sum("NEAPLICABIL" in i.value for i in at.info) == 0' in seg
    assert all(f"== {k}" not in seg for k in (2, 4, 6))


# ---------------- C8: înregistrarea de înlocuire (după testele de cod) ----------------
def test_C8_replacement_record():
    recs = sorted((TU3 / "inlocuiri").glob("INLOCUIRE_T7C_*.json"))
    assert recs, "înregistrarea INLOCUIRE_T7C_*.json lipsește (se scrie după testele de cod, §8 pasul 5)"
    valid, invalid = INL.load_records(ROOT)
    assert invalid == [] and recs[-1].name in {r["_name"] for r in valid}
    rec = json.loads(recs[-1].read_text())
    assert rec["seal"] == "tu3/SIGILIU_TU3_T7C.json" and set(rec["replacements"]) == set(REPLACEABLE)
    for rel, ft in rec["replacements"].items():
        assert ft["from"] == SEAL["replaceable"][rel]
        st_, chain = INL.resolve_one(rel, ft["from"], ROOT, valid)
        assert st_ == "inlocuit" and chain[0] == recs[-1].name, (rel, st_, chain)
    rep = INL.verify_all(ROOT)
    assert rep["ok"] is True
    vs = rep["seals"]["tu3/SIGILIU_TU3_VS.json"]
    assert {"tu3/ui_tu3.py", "tests/test_app_tu3.py"} <= set(vs["replaced"]) and recs[-1].name in vs["records"]


# ---------------- C9: raportul de identitate T7C (P3, 0444) ----------------
def test_C9_identity_report():
    fs = sorted((TU3 / "rezultate" / "T7C").glob("IDENTITATE_T7C_*.json"))
    assert fs, "raportul IDENTITATE_T7C_*.json lipsește (§8 pasul 4)"
    d = json.loads(fs[-1].read_text())
    assert _ro(fs[-1]) and d["verdict"] == "PASS" and d["protocol"] == "TU3-T7C"
    assert d["protocol_sha256"] == SEAL["sha256"] and d["written_utc"] > SEAL["sealed_utc"]
    assert d["CS"]["verdict"] in ("IDENTITATE_EXACTA", "IDENTITATE_NUMERICA")
    assert d["PL"]["verdict"] in ("IDENTITATE_EXACTA", "IDENTITATE_NUMERICA")
    assert d["positive_claims_allowed"] is False
    li = PT.latest_identity_t7c()
    assert li["file"] == fs[-1].name and li["verdict"] == "PASS"
