"""Teste TU3-T7A (PROTOCOL_TU3_T7A.md §7): protocolul comun al porturilor 7–12 și porturile DESCRIPTIVE BO (tab 7) și
WU (tab 8) în 5/40 și Joker.

Testele NU scriu în afara directoarelor temporare, NU rulează codul pistelor închise (bo649/, wu649/ se citesc numai ca
artefacte de referință) și NU recalculează scoruri, porți, bilete sau verdicte. AppTest în mod FAST (QL649_CONFIG=fast).
P10 cere înregistrarea `tu3/inlocuiri/INLOCUIRE_T7A_*.json` (scrisă după testele de cod, §8 pasul 5).
Calcul clasic. Variantele produsului = minime de energie, NU predicții. positive_claims_allowed=false.
TU3-T7B (PROTOCOL_TU3_T7B.md §7): P8 cere acum taburile 7–10 DESCRIPTIVE (9 GL, 10 SE) și 11–12 NEAPLICABIL; P9 cere
`== 2` în U3/U4; P10 cere ca lanțul pornit din `from`-ul T7A să ajungă la sha-ul curent (prin INLOCUIRE_T7B_*).
TU3-T7C (PROTOCOL_TU3_T7C.md §7): P8 cere acum taburile 7–12 DESCRIPTIVE (11 CS, 12 PL), cu graficele 11–12; P9 cere
`== 0` în U3/U4; P10 neschimbat (lanțul trece și prin INLOCUIRE_T7C_*).
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

SEAL_P = TU3 / "SIGILIU_TU3_T7A.json"
SEAL = json.loads(SEAL_P.read_text())
PROTO = TU3 / "PROTOCOL_TU3_T7A.md"
PORT = TU3 / "porturi_712.py"
BASE_UI = ROOT / "tests" / "baseline" / "ui_tu3_pre_t7a.py"
REPLACEABLE = {"tu3/ui_tu3.py", "tests/test_app_tu3.py"}
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _ro(p) -> bool:
    return (os.stat(p).st_mode & 0o222) == 0


# ---------------- P1: sigiliul protocolului, scris ÎNAINTE de cod ----------------
def test_P1_seal_before_code():
    assert _sha(PROTO) == SEAL["sha256"] and SEAL["file"] == PROTO.name
    assert SEAL["code_files_present"] == [] and SEAL["results_present"] is False
    assert SEAL["replacement_mechanism"] == INL.MECHANISM and SEAL["positive_claims_allowed"] is False
    assert _ro(SEAL_P) and _ro(PROTO)
    assert set(SEAL["replaceable"]) == REPLACEABLE
    assert SEAL["replaceable"]["tu3/ui_tu3.py"].startswith("eb0a1a90")
    assert SEAL["replaceable"]["tests/test_app_tu3.py"].startswith("ea06ef9f")
    for f in ("tu3/porturi_712.py", "tests/test_porturi_712.py", "tests/baseline/ui_tu3_pre_t7a.py"):
        assert f in SEAL["new_files_planned"] and f not in SEAL["frozen_hashes"]
    assert SEAL["baseline_copies_must_equal"] == {"tests/baseline/ui_tu3_pre_t7a.py": SEAL["replaceable"]["tu3/ui_tu3.py"]}
    assert _sha(BASE_UI) == SEAL["replaceable"]["tu3/ui_tu3.py"] and _ro(BASE_UI)
    assert SEAL["sealed_utc"] < "2026-10-27T14:17:00Z"


# ---------------- P2: fișierele protejate byte-identice; portul nu importă pistele/modelele ----------------
def test_P2_frozen_identical_and_imports():
    bad = [k for k, h in SEAL["frozen_hashes"].items() if not (ROOT / k).is_file() or _sha(ROOT / k) != h]
    bad += [k for k, h in SEAL["frozen_external"].items() if _sha(k) != h]
    assert bad == []
    fz = SEAL["frozen_hashes"]
    for k in ("engine.py", "parser.py", "tu3/parser_multi.py", "tu3/motor_n.py", "tu3/motor_joker.py", "run_app.sh",
              "run_app_tu3.sh", "porneste_aplicatia.sh", "porneste_aplicatia_tu3.sh", "tu3/arhiva_live.py",
              "tu3/dedup_live.py", "validare.py", "app.py", "tu3/inlocuiri_tu3.py", "tu3/matrice_init.py",
              "tu3/validare_tu3.py", "bo649/bo649.py", "wu649/wu649.py", "bo649/rezultate/backtest_unic/PREDICTII.npz",
              "wu649/rezultate/CALIFICARE.json", "tests/test_l649.py"):
        assert k in fz, k
    for d in ("bo649", "wu649"):          # pistele închise: TOATE fișierele în sigiliu, niciun fișier nou
        cur = {str(p.relative_to(ROOT)) for p in (ROOT / d).rglob("*") if p.is_file()}
        assert cur == {k for k in fz if k.startswith(d + "/")}, d
    mods = set()
    for node in ast.walk(ast.parse(PORT.read_text())):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert not mods & {"bo649", "wu649", "engine", "validare", "motor_n", "motor_joker", "torch", "streamlit"}, mods
    assert mods <= set(sys.stdlib_module_names) | {"__future__", "numpy", "parser"}, mods


# ---------------- P3/P4: identitatea pe 6/49 (subprocese) ----------------
def _identity(which: str, single: bool) -> dict:
    env = dict(os.environ)
    for v in THREAD_VARS:
        env.pop(v, None)
        if single:
            env[v] = "1"
    p = subprocess.run([sys.executable, "-B", str(PORT), "--identitate", which], env=env, capture_output=True,
                       text=True, timeout=1800)
    assert p.returncode == 0, p.stderr[-3000:]
    return json.loads(p.stdout)


def test_P3_identity_bo():
    r = _identity("bo", False)
    assert r["verdict"] in ("IDENTITATE_EXACTA", "IDENTITATE_NUMERICA"), r["rows"]
    names = {x["name"] for x in r["rows"]}
    assert {"ks", "Er", "p_recent", "post_last", "logZ", "steps_p_recent_gt_half", "source_sha256"} <= names
    assert r["source_sha256"].startswith("193eaf7a") and r["scores_recomputed"] is False


def test_P4_identity_wu():
    r = _identity("wu", True)
    assert r["verdict"] in ("IDENTITATE_EXACTA", "IDENTITATE_NUMERICA"), r["rows"]
    assert {x["name"] for x in r["rows"]} == {"q6_q7_Hplus", "theta6_theta7_Hplus", "counts_1_8", "max_abs_dq_WU",
                                             "order_invariance_max_dq", "B_identical", "cert"}
    assert r["tickets_recomputed"] is False


def test_P3b_fixture_generalization_matches_original_formula():
    """Pentru (49, 6), wu_fixture = formula literală wu649.fixture_hplus (rescrisă aici, fără import)."""
    rest = list(range(8, 50))
    ref = []
    for i in range(400):
        for S in ([7] + [rest[(5 * i + m) % 42] for m in range(5)], [rest[(6 * i + m + 21) % 42] for m in range(6)],
                  [1, 2, 3, 4, 5, 6]):
            ref.append(sorted(S))
    got = [sorted((np.flatnonzero(s[0]) + 1).tolist()) for s in PT.wu_fixture(49, 6)]
    assert got == ref
    for n, k in ((40, 6), (45, 5)):
        fx = PT.wu_fixture(n, k)
        assert len(fx) == 1200 and all(s.shape == (1, n) and s.sum() == k for s in fx)
        cnt = np.concatenate(fx).sum(0)
        assert (cnt[:k + 1] == 400).all()                   # bilele 1..κ+1: aceleași numărări (400)


# ---------------- P5: certificat BO — recursia float64 vs recursia exactă în Q ----------------
def _bocpd_q(steps, N, kappa, h, m0):
    a0, b0 = m0 * kappa / N, m0 * (N - kappa) / N
    runs, out = [], []
    evid = Fraction(1)
    for s, ys in enumerate(steps):
        zero = tuple(Fraction(0) for _ in range(N))
        prior = [(Fraction(1), 0, zero)] if s == 0 else [(h, 0, zero)] + [((1 - h) * w, n, C) for w, n, C in runs]
        q = [sum((w * (a0 + C[j]) / (m0 + n) for w, n, C in prior), Fraction(0)) for j in range(N)]
        er = sum((w * i for i, (w, _, _) in enumerate(prior)), Fraction(0))
        post = []
        for w, n, C in prior:
            lik = Fraction(1)
            for y in ys:
                for j in range(N):
                    lik *= (a0 + C[j]) / (m0 + n) if y[j] else (b0 + n - C[j]) / (m0 + n)
                C = tuple(C[j] + int(y[j]) for j in range(N))
                n += 1
            post.append((w * lik, n, C))
        Z = sum((p[0] for p in post), Fraction(0))
        evid *= Z
        runs = [(w / Z, n, C) for w, n, C in post]
        out.append((q, er, [w for w, _, _ in prior]))
    return out, evid


@pytest.mark.parametrize("N,kappa", [(7, 1), (7, 5), (6, 2)])
def test_P5_bo_exact_certificate(N, kappa):
    rng = np.random.default_rng([649, 7, N, kappa])
    steps = []
    for _ in range(6):
        a = np.zeros((int(rng.integers(1, 3)), N))
        for i in range(a.shape[0]):
            a[i, rng.choice(N, kappa, replace=False)] = 1.0
        steps.append(a)
    h, m0 = Fraction(1, 4), Fraction(3)
    fl = PT.bocpd(steps, N, kappa, float(h), float(m0), keep_post=(len(steps) - 1,))
    ex, evid = _bocpd_q([s.astype(int).tolist() for s in steps], N, kappa, h, m0)
    for s, (q, er, prior) in enumerate(ex):
        assert np.max(np.abs(fl["q"][s] - np.array([float(x) for x in q]))) <= 1e-12
        assert abs(fl["Er"][s] - float(er)) <= 1e-12
    assert np.max(np.abs(fl["posts"][len(steps) - 1] - np.array([float(x) for x in ex[-1][2]]))) <= 1e-12
    assert abs(fl["logZ"] - (math.log(evid.numerator) - math.log(evid.denominator))) <= 1e-10
    d = PT.bo_describe(steps, N, kappa)
    assert d["warmup"] == 0 and abs(d["post_last"].sum() - 1) <= 1e-12 and PT.forbidden_keys(d) == []


# ---------------- P6: certificat WU — cuadratura vs enumerarea exactă Luce ----------------
def _luce_set_prob(w, S):
    W = sum(w)
    tot = 0.0
    for perm in itertools.permutations(S):
        p, rem = 1.0, W
        for j in perm:
            p *= w[j] / rem
            rem -= w[j]
        tot += p
    return tot


@pytest.mark.parametrize("kappa", [1, 2, 5])
def test_P6_wu_exact_certificate(kappa):
    N = 7
    theta = np.random.default_rng([649, 9, kappa]).normal(0, 0.4, N)
    w = np.exp(theta).tolist()
    sets = list(itertools.combinations(range(N), kappa))
    probs = {S: _luce_set_prob(w, S) for S in sets}
    assert abs(sum(probs.values()) - 1) <= 1e-12
    incl = np.array([sum(p for S, p in probs.items() if j in S) for j in range(N)])
    assert np.max(np.abs(PT.inclusion(theta, kappa) - incl)) <= 1e-12
    mem = np.array(sets[:12], dtype=np.int64)
    nonmem = np.ones((mem.shape[0], N))
    nonmem[np.arange(mem.shape[0])[:, None], mem] = 0.0
    dt_ = PT.draw_terms(theta, mem, nonmem)
    assert np.max(np.abs(dt_["logP"] - np.log([probs[tuple(S)] for S in mem.tolist()]))) <= 1e-12
    eps, g = 1e-6, np.zeros(N)
    for j in range(N):
        e = np.zeros(N)
        e[j] = eps
        g[j] = (PT.draw_terms(theta + e, mem, nonmem, deriv=False)["logP"].sum()
                - PT.draw_terms(theta - e, mem, nonmem, deriv=False)["logP"].sum()) / (2 * eps)
    assert np.max(np.abs(dt_["grad"] - g)) <= 1e-6
    D = np.zeros((mem.shape[0], N))
    D[np.arange(mem.shape[0])[:, None], mem] = 1.0
    f = PT.wu_describe(D)
    assert f["cert"] and abs(f["sum_theta"]) <= 1e-7 and PT.forbidden_keys(f) == []


# ---------------- P7: rulare generică pe 5/40 și Joker (LIVE) ----------------
@pytest.mark.parametrize("game", ["540", "joker"])
def test_P7_generic_live(game):
    import parser_multi as PM
    ds = PM.build_game_dataset(game, "live", device="cpu")
    jo = None if ds.joker_onehot is None else ds.joker_onehot.numpy()
    comps = PT.components(ds.onehot.numpy(), ds.step_offsets.numpy(), ds.game.n, ds.game.r, jo, ds.game.joker_m)
    assert [c["key"] for c in comps] == (["principal", "joker"] if game == "joker" else ["principal"])
    B, W = PT.describe_bo(comps), PT.describe_wu(comps)
    for c, b, w in zip(comps, B, W):
        assert b["N"] == c["N"] and b["kappa"] == c["kappa"] and b["n_draws"] == ds.n_draws
        assert b["n_steps"] == ds.n_steps and b["warmup"] == 100 and len(b["ks"]) == ds.n_steps - 100
        assert np.isfinite(b["Er"]).all() and (b["Er"] >= 0).all() and (b["Er"] <= b["ks"] + 1e-9).all()
        assert ((b["p_recent"] >= 0) & (b["p_recent"] <= 1 + 1e-12)).all()
        assert abs(b["post_last"].sum() - 1) <= 1e-9 and np.isfinite(b["logZ"])
        f = w["fit"]
        assert f["cert"] and f["fail"] == "" and abs(f["sum_theta"]) <= 1e-7 and np.isfinite(f["theta"]).all()
        assert f["N"] == c["N"] and f["kappa"] == c["kappa"] and f["freq"].sum() == c["kappa"] * ds.n_draws
        if c["kappa"] >= 2:
            wt = w["witness"]
            assert wt["applicable"] and all(wt["cert"]) and wt["same_counts"] and wt["max_abs_dq"] > 0
            assert wt["order_invariance_max_dq"] <= 1e-9
        else:
            assert w["witness"]["applicable"] is False and "κ = 1" in w["witness"]["reason"]
    assert PT.forbidden_keys(B) == [] and PT.forbidden_keys(W) == []


# ---------------- P8: numai descriptiv în aplicație (AppTest FAST) ----------------
def _tab_text(tab) -> str:
    parts = []
    for kind in ("markdown", "caption", "info", "error", "warning"):
        parts += [e.value for e in getattr(tab, kind)]
    return "\n".join(parts)


@pytest.mark.parametrize("mode", ["540", "joker"])
def test_P8_app_tabs_descriptive(tmp_path, mode):
    from streamlit.testing.v1 import AppTest
    os.environ["QL649_SEAL_DIR"] = str(tmp_path / "sigilii")
    os.environ["QL649_CONFIG"] = "fast"
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
    at.run()
    at.selectbox(key="tu3_mode").set_value(mode).run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.tabs) == 12
    for i in range(6, 12):                # TU3-T7C: taburile 7–12 = porturile BO/WU/GL/SE/CS/PL (PROTOCOL_TU3_T7C §7)
        t = _tab_text(at.tabs[i])
        assert "DESCRIPTIV" in t and "NU se transferă" in t and "positive_claims_allowed=false" in t
        assert "NEAPLICABIL" not in t and not at.tabs[i].error, t[:500]
        assert "IDENTITATE_" in t or "raport absent" in t
    low = "".join(_tab_text(at.tabs[i]) for i in range(6, 12)).lower()
    for word in ("bilet recomandat", "câștig", "promovat", "bo_no_promotion", "porți trecute", "hits"):
        assert word not in low, word
    assert len(at.tabs[6].get("plotly_chart")) == (4 if mode == "joker" else 2)
    assert len(at.tabs[7].get("plotly_chart")) == (5 if mode == "joker" else 3)
    assert len(at.tabs[8].get("plotly_chart")) == (4 if mode == "joker" else 2)
    assert len(at.tabs[9].get("plotly_chart")) == (4 if mode == "joker" else 2)
    assert len(at.tabs[10].get("plotly_chart")) == (4 if mode == "joker" else 2)
    assert len(at.tabs[11].get("plotly_chart")) == 3


# ---------------- P9: numai inserții față de copia de referință ----------------
def test_P9_insertions_only():
    a = BASE_UI.read_text().splitlines()
    b = (TU3 / "ui_tu3.py").read_text().splitlines()
    ops = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
    assert {o for o, *_ in ops} <= {"equal", "insert"}
    ins = [ln for o, _, _, j1, j2 in ops if o == "insert" for ln in b[j1:j2]]
    assert any("TU3-T7A" in ln for ln in ins) and any("t7a_port(t_idx, tabs[t_idx]" in ln for ln in ins)
    t = (ROOT / "tests" / "test_app_tu3.py").read_text()
    assert 'sum("NEAPLICABIL" in i.value for i in at.info) == 0' in t and "== 6" not in t.split("def test_u3_u4")[1][:1200]


# ---------------- P10: înregistrarea de înlocuire (după testele de cod) ----------------
def test_P10_replacement_record():
    recs = sorted((TU3 / "inlocuiri").glob("INLOCUIRE_T7A_*.json"))
    assert recs, "înregistrarea INLOCUIRE_T7A_*.json lipsește (se scrie după testele de cod, §8 pasul 5)"
    valid, invalid = INL.load_records(ROOT)
    assert invalid == [] and recs[-1].name in {r["_name"] for r in valid}
    rec = json.loads(recs[-1].read_text())
    assert rec["seal"] == "tu3/SIGILIU_TU3_T7A.json" and set(rec["replacements"]) <= REPLACEABLE
    for rel, ft in rec["replacements"].items():   # TU3-T7B: lanțul pornit din `from`-ul T7A ajunge la sha-ul curent
        st_, chain = INL.resolve_one(rel, ft["from"], ROOT, valid)
        assert st_ == "inlocuit" and chain[0] == recs[-1].name, (rel, st_, chain)
    rep = INL.verify_all(ROOT)
    assert rep["ok"] is True
    vs = rep["seals"]["tu3/SIGILIU_TU3_VS.json"]
    assert REPLACEABLE <= set(vs["replaced"]) and recs[-1].name in vs["records"]
    assert any(n.startswith("INLOCUIRE_L649_") for n in vs["records"])
