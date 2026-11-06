"""Teste pentru verificatorul SEPARAT `tu3/verifica_sr.py` (PROTOCOL_TU3_SR_R.md §3.4).

T1 importurile (numai stdlib + numpy) · T2 identitatea verificator ↔ `scor_real` pe un set SINTETIC cu pași dubli
(config FAST numai în test) · T3 calea reală `run_real` cap-coadă pe o arhivă SINTETICĂ (director temporar), apoi
verificatorul ⇒ PASS și refuzul unei a doua rulări · T4 falsificări ⇒ FAIL; manifestul pre-rulare refuză · T5 (după
rulare) fișierele reale VERIFICARE_SR.json / PRE_RULARE_S8.json. T1–T4 NU citesc arhivele reale: `resolve_frozen`,
`resolve_live` și `parser.build_dataset` aruncă excepție, iar `build_game_dataset` e redirecționat spre fișierul sintetic.
`positive_claims_allowed=false`.
"""
from __future__ import annotations

import ast
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
TU3 = ROOT / "tu3"
for _p in (str(ROOT), str(TU3)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import parser as QP  # noqa: E402
import parser_multi as PM  # noqa: E402
import scor_real as SR  # noqa: E402
import verifica_sr as VS  # noqa: E402

FAST = dict(mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60, gamma_grid=12)
SIZES = {"540": 220, "joker": 200}
DEV = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _ro(p) -> bool:
    return (os.stat(p).st_mode & 0o222) == 0


def _forbidden(*a, **k):
    raise RuntimeError("test: citirea arhivei reale este interzisă")


def _synthetic_archive(path: Path, game: str, L: int, seed: int) -> Path:
    """L extrageri uniforme cu ~1 zi din 8 dublă (pași dubli), schema LIVE/înghețată."""
    g = VS.GAMES[game]
    rng = np.random.default_rng(seed)
    day = dt.date(2001, 1, 1)
    lines = []
    for i in range(L):
        if not (i > 0 and rng.random() < 0.125):
            day = day + dt.timedelta(days=int(rng.integers(1, 4)))
        nums = sorted((rng.choice(g["n"], g["r"], replace=False) + 1).tolist())
        jk = int(rng.integers(1, 21)) if game == "joker" else None
        key = f"{g['code']}:{day.isoformat()}:{'-'.join(map(str, nums))}" + (f":J{jk}" if jk else "")
        lines.append(json.dumps({"draw_date": day.isoformat(), "draw_key": key, "draw_kind": "regular",
                                 "game": g["code"], "joker": jk, "numbers": nums}))
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture
def no_real_archive(monkeypatch):
    for mod, name in ((PM, "resolve_frozen"), (PM, "resolve_live"), (QP, "build_dataset")):
        monkeypatch.setattr(mod, name, _forbidden)
    return monkeypatch


# ---------------- T1: importurile ----------------
def test_T1_imports_independent():
    mods = set()
    for node in ast.walk(ast.parse((TU3 / "verifica_sr.py").read_text())):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert mods <= set(sys.stdlib_module_names) | {"__future__", "numpy"}, mods
    assert not mods & {"scor_real", "torch", "motor_n", "motor_joker", "engine", "parser", "parser_multi", "validare"}


# ---------------- T2: identitatea verificator ↔ scor_real (sintetic, pași dubli) ----------------
@pytest.mark.parametrize("game", ["540", "joker"])
def test_T2_identity_vs_scor_real(tmp_path, no_real_archive, game):
    path = _synthetic_archive(tmp_path / f"s_{game}.jsonl", game, SIZES[game], 11 if game == "540" else 12)
    ds = PM.build_game_dataset(game, str(path), device=DEV)
    arc = VS.load_archive(game, path)
    assert arc["n_draws"] == ds.n_draws and arc["n_steps"] == ds.n_steps and arc["n_steps"] < arc["n_draws"]
    assert np.array_equal(arc["main"], ds.onehot.cpu().numpy())
    assert np.array_equal(arc["step_offsets"], ds.step_offsets.cpu().numpy())
    if game == "joker":
        assert np.array_equal(arc["joker"], ds.joker_onehot.cpu().numpy())
    cfg = replace(SR.GAMES[game]["cfg"], **FAST)
    ks = torch.arange(SR.WARMUP, ds.n_steps)
    pred = SR.wf_predict(ds, game, ks, cfg=cfg)                                  # semințele step_seed (calea S8)
    off = arc["step_offsets"]
    pb, pr = VS.comparators(VS._step_counts(arc["main"], off), VS._cum(arc["main"]), off, pred["ks"])
    assert np.abs(pb - pred["piB"]).max() <= 1e-12 and np.abs(pr - pred["piR"]).max() <= 1e-12
    comps = SR.score_predictions(game, pred, ds.onehot.cpu().numpy(),
                                 ds.joker_onehot.cpu().numpy() if game == "joker" else None, off)
    rows = np.concatenate([np.arange(off[k], off[k + 1]) for k in pred["ks"]])
    kidx = np.concatenate([np.full(off[k + 1] - off[k], i) for i, k in enumerate(pred["ks"])])
    V = pred["variants"][kidx]
    mine = [VS.component(*VS.URNS[game][0], arc["main"][rows], pred["pi_QL"][kidx], V[:, 0, :], V, pb[kidx], pr[kidx])]
    if game == "joker":
        pbj, prj = VS.comparators(VS._step_counts(arc["joker"], off), VS._cum(arc["joker"]), off, pred["ks"])
        J = pred["jokers"][kidx]
        mine.append(VS.component(*VS.URNS[game][1], arc["joker"][rows], pred["pi_J"][kidx], J[:, :1], J[:, :, None],
                                 pbj[kidx], prj[kidx]))
    for a, b in zip(mine, comps):
        b = dict(b)
        b["per_target"] = {k: v.astype(int).tolist() for k, v in b.pop("_per_target").items()}
        b["gates"] = [{k: v for k, v in g.items() if k != "rule"} for g in b["gates"]]
        assert VS.close(a, b) == []
    # D2: statisticile reale identice; z/SCI/p în toleranțele V7 (M redus numai în test)
    sidx, sizes = ds.step_index.to(DEV), (ds.step_offsets[1:] - ds.step_offsets[:-1]).to(DEV)
    jo = ds.joker_onehot.to(DEV)[None] if game == "joker" else None
    raw = SR.raw_stats_game(game, ds.onehot.to(DEV)[None], jo, sidx, sizes, ds.n_steps)
    Mt = 2048
    gen = torch.Generator(device=DEV).manual_seed(777)

    def batches():
        for s0 in range(0, Mt, 256):
            U = SR.mps_universes(game, 256, ds.n_draws, 0.0, gen, DEV)
            yield U["main"], U["joker_oh"], sidx, sizes, ds.n_steps

    ref = SR.sci_reference(game, batches(), Mt)
    ev = SR.sci_evaluate(game, raw, ref)
    ind = VS.d2_independent(game, arc, M=Mt, seed=778, chunk=256)
    for k in ("main.chi_freq", "main.chi_pair", "main.overlap") + (("ball.chi_freq", "ball.overlap", "cross.chi")
                                                                     if game == "joker" else ()):
        assert math.isclose(ind["stats_real"][k], float(ev["stats"][k][0]), rel_tol=1e-9), k
    for k, z in ev["z"].items():
        assert abs(ind["z"][k] - float(z[0])) <= 0.10 + 0.03 * abs(float(z[0])), k
    sci = float(ev["SCI"][0])
    assert abs(ind["SCI"] - sci) <= 0.10 + 0.03 * abs(sci)
    p, q = ind["p_empirical"], float(ev["p"][0])
    pbar = 0.5 * (p + q)
    assert abs(p - q) <= 4 * math.sqrt(pbar * (1 - pbar) / Mt) + 3 / Mt


# ---------------- T3: run_real cap-coadă pe arhiva sintetică + verificatorul ----------------
@pytest.fixture(scope="module")
def synthetic_runs(tmp_path_factory):
    base = tmp_path_factory.mktemp("sr_synth")
    out = {}
    with pytest.MonkeyPatch.context() as mp:
        for mod, name in ((PM, "resolve_frozen"), (PM, "resolve_live"), (QP, "build_dataset")):
            mp.setattr(mod, name, _forbidden)
        orig = PM.build_game_dataset
        paths = {g: _synthetic_archive(base / f"arhiva_{g}.jsonl", g, SIZES[g], 21 if g == "540" else 22)
                 for g in ("540", "joker")}
        calls = []

        def redirected(game, source="live", device=None, **k):
            calls.append((game, source))
            assert source == "frozen"
            return orig(game, str(paths[game]), device=device)

        mp.setattr(PM, "build_game_dataset", redirected)
        pw = base / "PUTERE_SR.json"
        pw.write_text(json.dumps({"games": {"540": {"verdict": "SR_P_PASS"}, "joker": {"verdict": "SR_P_PASS"}}}))
        sr_dir = base / "SR"
        for g in ("540", "joker"):
            mp.setitem(SR.GAMES[g], "frozen_sha", _sha(paths[g]))
            mp.setitem(SR.GAMES[g], "cfg", replace(SR.GAMES[g]["cfg"], **FAST))
            rc = SR.run_real(g, "S8", sr_dir, pw, log=lambda *_: None)
            rc2 = SR.run_real(g, "S8", sr_dir, pw, log=lambda *_: None)
            out[g] = {"rc": rc, "rc2": rc2, "path": paths[g], "digest": SR.GAMES[g]["cfg"].digest()}
        out["calls"] = calls
    out["sr_dir"] = sr_dir
    return out


@pytest.mark.parametrize("game", ["540", "joker"])
def test_T3_run_real_end_to_end_and_verifier(synthetic_runs, game):
    r = synthetic_runs[game]
    assert r["rc"] == 0 and r["rc2"] == 2                           # a doua rulare refuzată (START există)
    assert synthetic_runs["calls"].count((game, "frozen")) == 1
    d = synthetic_runs["sr_dir"] / game
    for f in ("START.json", "PREDICTII.npz", "PREDICTII_SIGILIU.json", "REZULTATE.json"):
        assert _ro(d / f), f
    rep = VS.verify_game(game, synthetic_runs["sr_dir"], archive=r["path"], frozen_sha=_sha(r["path"]),
                         digest_prefix=r["digest"][:12], chunk=256)
    failed = [c for c in rep["checks"] if not c["pass"]]
    assert rep["verdict"] == "VERIFICARE_SR_PASS", failed
    assert rep["d2_independent"]["concordanta"] in ("D2_CONCORDANT", "D2_IN_BANDA_MC")
    res = json.loads((d / "REZULTATE.json").read_text())
    assert res["positive_claims_allowed"] is False and res["D1"]["verdict"] in ("SR_DETECTIE_EXPLORATORIE",
                                                                                 "SR_FARA_DETECTIE")
    out = VS.write_verification(game, rep, synthetic_runs["sr_dir"])
    assert _ro(out) and json.loads(out.read_text())["rezultate_sha256"] == _sha(d / "REZULTATE.json")
    with pytest.raises(FileExistsError):
        VS.write_verification(game, rep, synthetic_runs["sr_dir"])


# ---------------- T4: falsificări ⇒ FAIL; manifestul pre-rulare refuză ----------------
def test_T4_tampering_detected(synthetic_runs, tmp_path):
    r = synthetic_runs["540"]
    src = synthetic_runs["sr_dir"] / "540"
    for case in ("hits", "sha"):
        dst = tmp_path / case / "540"
        shutil.copytree(src, dst)
        for f in dst.iterdir():
            os.chmod(f, 0o644)
        if case == "hits":
            res = json.loads((dst / "REZULTATE.json").read_text())
            res["components"][0]["total"]["hits_QL"] += 1
            (dst / "REZULTATE.json").write_text(json.dumps(res))
        else:
            sig = json.loads((dst / "PREDICTII_SIGILIU.json").read_text())
            sig["sha256"] = "0" * 64
            (dst / "PREDICTII_SIGILIU.json").write_text(json.dumps(sig))
        for f in dst.iterdir():
            os.chmod(f, 0o444)
        rep = VS.verify_game("540", tmp_path / case, archive=r["path"], frozen_sha=_sha(r["path"]),
                             digest_prefix=r["digest"][:12], d2=False)
        failed = {c["id"] for c in rep["checks"] if not c["pass"]}
        assert rep["verdict"] == "VERIFICARE_SR_FAIL"
        assert ("V5.scor_recalculat" in failed) if case == "hits" else ("V1.sha_predictii" in failed)
    root = tmp_path / "root"
    (root / "tu3" / "inlocuiri").mkdir(parents=True)
    with pytest.raises(RuntimeError):
        VS.write_pre_run(synthetic_runs["sr_dir"], root)               # START există
    with pytest.raises(RuntimeError):
        VS.write_pre_run(tmp_path / "gol", root)                         # fără INLOCUIRE_SR_*


# ---------------- T5: fișierele reale (după rulare) ----------------
@pytest.mark.parametrize("game", ["540", "joker"])
def test_T5_real_verification_files(game):
    d = TU3 / "rezultate" / "SR" / game
    if not (d / "REZULTATE.json").is_file():
        pytest.skip(f"rularea reală {game} nu există încă")
    vf = d / "VERIFICARE_SR.json"
    assert vf.is_file() and _ro(vf), "VERIFICARE_SR.json lipsește (pasul 6 din PROTOCOL_TU3_SR_R §5)"
    v = json.loads(vf.read_text())
    assert v["rezultate_sha256"] == _sha(d / "REZULTATE.json") and v["positive_claims_allowed"] is False
    assert v["predictions_sha256"] == _sha(d / "PREDICTII.npz")
    assert v["verdict"] == ("VERIFICARE_SR_PASS" if all(c["pass"] for c in v["checks"]) else "VERIFICARE_SR_FAIL")
    pre = TU3 / "rezultate" / "SR" / "PRE_RULARE_S8.json"
    assert pre.is_file() and _ro(pre)
    start = json.loads((d / "START.json").read_text())
    assert json.loads(pre.read_text())["written_utc"] < start["started_at_utc"]
    seal_r = json.loads((TU3 / "SIGILIU_TU3_SR_R.json").read_text())
    assert start["started_at_utc"] > seal_r["sealed_utc"]
