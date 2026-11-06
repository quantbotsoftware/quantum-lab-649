"""Teste TU4-EM (S12): arhive LIVE SINTETICE într-o rădăcină de test; nu ating lanțul real și nu citesc arhiva reală."""
import datetime as dt
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

TU4 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TU4))
import emite as E  # noqa: E402
import ip_core as C  # noqa: E402
import verifica_em as VE  # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest()


def make_live(root: Path, last_date="2026-10-25", n_rec=300, seed=7, tilt=0.0, version="aaaa00000001"):
    """Arhivă LIVE sintetică cu structura reală (CURRENT_LIVE.json → versiuni/<v>/MANIFEST_LIVE.json + jsonl)."""
    rng = np.random.default_rng(seed)
    live = root / "tu3" / "date" / "live"
    vdir = live / "versiuni" / version
    vdir.mkdir(parents=True, exist_ok=True)
    games = {}
    start = dt.date.fromisoformat(last_date) - dt.timedelta(days=7 * n_rec)
    for game, (n, k, _b, ball) in {"649": (49, 6, 6, False), "540": (40, 6, 5, False),
                                   "joker": (45, 5, 5, True)}.items():
        w = np.exp(tilt * np.cos(np.pi * (np.arange(1, n + 1) - 0.5) / n))
        lines = []
        for t in range(n_rec):
            d = (start + dt.timedelta(days=7 * t)).isoformat() if t < n_rec - 1 else last_date
            nums = sorted(int(x) + 1 for x in rng.choice(n, k, replace=False, p=w / w.sum()))
            rec = {"draw_date": d, "draw_key": f"{game}:{d}:{'-'.join(map(str, nums))}", "draw_kind": "regular",
                   "game": game, "numbers": nums, "joker": int(rng.integers(1, 21)) if ball else None}
            lines.append(json.dumps(rec))
        data = ("\n".join(lines) + "\n").encode()
        (vdir / f"extrageri_{game}.jsonl").write_bytes(data)
        games[game] = {"file": f"extrageri_{game}.jsonl", "sha256": sha(data), "records": n_rec,
                       "last_date": last_date, "last_key": json.loads(lines[-1])["draw_key"]}
    man = {"database_sha256": "d" * 64, "games": games}
    (vdir / "MANIFEST_LIVE.json").write_text(json.dumps(man))
    cur = {"database_sha256": "d" * 64, "version_dir": f"versiuni/{version}", "run_id": "test",
           "games": {g: {k2: v[k2] for k2 in ("records", "last_date", "last_key", "sha256")} for g, v in games.items()}}
    (live / "CURRENT_LIVE.json").write_text(json.dumps(cur))
    return live


def run(root, game, now, ssd=None):
    args = ["--joc", game, "--radacina-test", str(root), "--acum", now]
    args += ["--ssd", str(ssd)] if ssd else ["--fara-ssd"]
    return E.main(args)


def test_calendar_tinta_si_ora():
    s = E.schedule(E.parse_utc("2026-10-27T21:40:00Z"))           # marți
    assert s["target_date"] == "2026-10-29" and s["previous_draw_date"] == "2026-10-25"
    assert E.iso(s["draw_utc"]).startswith("2026-10-29T16:30:00") and E.iso(s["cutoff_utc"]).startswith("2026-10-29T14:00:00")
    assert E.schedule(E.parse_utc("2026-10-29T13:59:59Z"))["target_date"] == "2026-10-29"
    assert E.schedule(E.parse_utc("2026-10-29T14:00:00Z"))["target_date"] == "2026-11-01"
    s2 = E.schedule(E.parse_utc("2027-03-27T10:00:00Z"))           # duminică 28 mar 2027, ora de vară (EEST)
    assert s2["target_date"] == "2027-03-28" and E.iso(s2["draw_utc"]).startswith("2027-03-28T15:30:00")


def test_float64_egal_nucleul_inghetat():
    rng = np.random.default_rng(3)
    for n, k, b in ((49, 6, 6), (40, 6, 5), (45, 5, 5), (20, 1, 1)):
        N = 2500
        c = rng.multinomial(N * k, np.ones(n) / n).astype(float)
        for m, f in (("H1", C.lw_h1_np), ("H3", C.lw_h3_np)):
            blk = E.model_block(m, c, N, n, k, b)
            lw, lam = f(c, N, n, k)
            assert blk["logw"] == [float(x) for x in lw] and blk["lambda"] == lam
            if k > 1:
                assert abs(blk["pi_sum"] - k) < 1e-10 and blk["top_ticket"] == C.ticket(lw, b)
            else:
                assert abs(sum(blk["q"]) - 1) < 1e-12


def test_lambda_zero_nu_pariaza():
    n, k, N = 49, 6, 2401
    c = np.full(n, N * k / n)
    blk = E.model_block("H1", c, N, n, k, 6)
    assert blk["lambda"] == 0.0 and not blk["bet_active"] and "ticket_note" in blk
    assert blk["top_ticket"] == [1, 2, 3, 4, 5, 6] and abs(blk["D_nats"]) < 1e-12


def test_oglinda_c64_compilata_trece_poarta():
    rng = np.random.default_rng(5)
    for n, k, b in ((49, 6, 6), (20, 1, 1)):
        N = 2600
        w = np.exp(0.15 * np.cos(np.pi * (np.arange(1, n + 1) - 0.5) / n))
        c = rng.multinomial(N * k, w / w.sum()).astype(float)
        mm = E.mirror(c, N, n, k)
        for m in ("H1", "H3"):
            g = E.gate(E.model_block(m, c, N, n, k, b), mm[m], b, k)
            assert g["pass"], g
    assert all(s.startswith(("compiled", "eager")) for s in E.MIRROR_STATUS.values())


def test_emisie_lant_noop_si_verificator(tmp_path):
    root, ssd = tmp_path / "r", tmp_path / "ssd"
    make_live(root, tilt=0.2)
    now = "2026-10-27T21:40:00Z"
    for g in ("649", "540", "joker"):
        assert run(root, g, now, ssd) == 0
    trib = root / "tu4" / "tribunal"
    f = trib / "emisii" / "joker" / "2026-10-29.json"
    em = json.loads(f.read_bytes())
    assert stat.S_IMODE(f.stat().st_mode) == 0o444
    assert em["chain"]["prev_sha256"] == sha((TU4 / "SIGILIU_TU4_EM.json").read_bytes())
    assert em["tribunal"]["M"] == 6 and em["tribunal"]["threshold"] == 600 and em["positive_claims_allowed"] is False
    assert len(em["models"]["H3"]["top_ticket"]) == 5 and 1 <= em["models"]["H1"]["ball"]["top_ball"] <= 20
    assert em["c64_mirror"]["pass"] and em["warm_start_complete"]
    before = f.read_bytes()
    assert run(root, "joker", now, ssd) == 0                         # no-op
    assert f.read_bytes() == before
    with pytest.raises(FileExistsError):
        E.write_exclusive(f, b"x")
    # ținta următoare: lanțul continuă
    make_live(root, last_date="2026-10-29", seed=8, version="aaaa00000002")
    assert run(root, "joker", "2026-10-30T08:00:00Z", ssd) == 0
    em2 = json.loads((trib / "emisii" / "joker" / "2026-11-01.json").read_bytes())
    assert em2["chain"]["index"] == 1 and em2["chain"]["prev_sha256"] == sha(before)
    lines = (trib / "LANT.jsonl").read_bytes().splitlines()
    assert len(lines) == 4 and json.loads(lines[3])["prev_line_sha256"] == sha(lines[2])
    assert (ssd / "emisii" / "joker" / "2026-11-01.json").read_bytes() == (trib / "emisii" / "joker" / "2026-11-01.json").read_bytes()
    assert (ssd / "LANT.jsonl").read_bytes() == (trib / "LANT.jsonl").read_bytes()
    res = VE.verify(root, ssd, test=True)
    assert res["verdict"] == "VERIFICARE_EM_PASS", [c for c in res["checks"] if c["status"] == "FAIL"]
    # falsificare detectată
    os.chmod(f, 0o644)
    f.write_bytes(before.replace(b'"warm_start_complete": true', b'"warm_start_complete": false'))
    os.chmod(f, 0o444)
    assert VE.verify(root, ssd, test=True)["verdict"] == "VERIFICARE_EM_FAIL"


def test_refuzuri_amanare_tarziu(tmp_path):
    root = tmp_path / "r"
    live = make_live(root, last_date="2026-10-22")                   # lipsește extragerea din 25
    assert run(root, "649", "2026-10-27T21:40:00Z") == E.EXIT_POSTPONED
    assert not (root / "tu4/tribunal/emisii/649/2026-10-29.json").exists()
    assert run(root, "649", "2026-10-29T13:10:00Z") == 0           # fereastra finală (15:10 local)
    em = json.loads((root / "tu4/tribunal/emisii/649/2026-10-29.json").read_bytes())
    assert em["warm_start_complete"] is False
    # după termen: ținta devine duminica, deci nu există emisie întârziată pentru joi
    assert E.schedule(E.parse_utc("2026-10-29T14:30:00Z"))["target_date"] == "2026-11-01"
    # arhivă falsificată ⇒ refuz
    f = live / "versiuni" / "aaaa00000001" / "extrageri_540.jsonl"
    f.write_bytes(f.read_bytes().replace(b'"numbers": [', b'"numbers": [ ', 1))
    assert run(root, "540", "2026-10-27T21:40:00Z") == E.EXIT_REFUSED
    runs = [json.loads(x) for x in (root / "tu4/tribunal/RULARI.jsonl").read_text().splitlines()]
    assert [r["action"] for r in runs] == ["postponed", "emitted", "refused"]


def test_ceas_fals_interzis_pe_lantul_real(capsys):
    assert E.main(["--joc", "649", "--acum", "2026-10-27T21:40:00Z", "--fara-ssd"]) == E.EXIT_REFUSED
    assert E.main(["--joc", "649", "--radacina-test", str(E.QL), "--fara-ssd"]) == E.EXIT_REFUSED


def test_fara_popularitate_si_fara_produsul_vechi():
    import ast
    allowed = {"__future__", "argparse", "datetime", "fcntl", "hashlib", "json", "math", "mmap", "os", "queue", "sys",
               "threading", "time", "pathlib", "zoneinfo", "numpy", "torch", "ip_core"}
    tree = ast.parse((TU4 / "emite.py").read_text(encoding="utf-8"))
    mods = {(a.name if isinstance(n, ast.Import) else n.module).split(".")[0]
            for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    assert mods <= allowed, mods - allowed
    names = {n.id.lower() for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr.lower() for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not any("popular" in x or "crowd" in x or "vanzari" in x for x in names)
    vsrc = (TU4 / "verifica_em.py").read_text(encoding="utf-8")
    assert "import torch" not in vsrc and "import ip_core" not in vsrc and "import emite" not in vsrc


def test_mmap_append(tmp_path):
    p = tmp_path / "j.jsonl"
    chunks = [(json.dumps({"i": i, "x": "a" * (i * 997 % 5000)}) + "\n").encode() for i in range(40)]
    for ch in chunks:
        E.mmap_append(p, ch)
    assert p.read_bytes() == b"".join(chunks) and stat.S_IMODE(p.stat().st_mode) == 0o444
