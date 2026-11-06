"""Testele T1–T11 ale submodulului TU3-DD (PROTOCOL_TU3_DD.md §5) pe o arhivă LIVE SINTETICĂ în director temporar,
construită exact în formatul `tu3/arhiva_live.py` (rânduri `json.dumps(..., ensure_ascii=False, sort_keys=True)`,
`provenance = {run_id, database_sha256}`, manifest + pointer). Nu citește și nu modifică arhiva reală."""
from __future__ import annotations

import ast
import gzip
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tu3"))
import dedup_live as DD  # noqa: E402
import parser_multi as PM  # noqa: E402

RULES = {"649": (49, 6, None), "540": (40, 6, None), "joker": (45, 5, 20)}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _records(game: str, n_draws: int, prov: dict) -> list[dict]:
    n, r, jm = RULES[game]
    out = []
    for t in range(n_draws):
        nums = sorted({(t * 7 + k * 11 + len(game)) % n + 1 for k in range(r * 3)})[:r]
        while len(nums) < r:
            nums = sorted(set(nums) | {len(nums) + 1})
        jk = (t % jm) + 1 if jm else None
        d = f"{2001 + t // 100:04d}-{1 + (t // 8) % 12:02d}-{1 + t % 8:02d}"
        key = f"{game}:{d}:{'-'.join(map(str, nums))}" + (f":J{jk}" if jk else "")
        out.append({"game": game, "draw_key": key, "draw_date": d, "draw_kind": "unknown", "numbers": nums,
                    "numbers_order_as_stored": list(reversed(nums)), "joker": jk, "verification": "secondary_only",
                    "source_count": 1, "has_source_disagreement": False, "provenance": prov})
    return out


def _make_version(vers: Path, idx: int, n_draws: int) -> str:
    db_sha = _sha(f"baza-{idx}".encode())
    run_id = f"2026102{idx}T00000{idx}000000"
    name = db_sha[:12]
    v = vers / name
    v.mkdir(parents=True)
    prov = {"run_id": run_id, "database_sha256": db_sha}
    man = {"created_utc": f"2026-10-26T{10 + idx:02d}:00:00Z", "run_id": run_id, "database_sha256": db_sha,
           "archive_changed_by_collector": False, "note": "sintetic", "games": {}}
    for game, (n, r, jm) in RULES.items():
        recs = _records(game, n_draws, prov)
        p = v / f"extrageri_{game}.jsonl"
        p.write_text("".join(DD.dumps(x) for x in recs), encoding="utf-8")
        man["games"][game] = {"name": game, "file": p.name, "sha256": _sha(p.read_bytes()), "records": len(recs),
                              "excluded": [], "first_date": recs[0]["draw_date"], "last_date": recs[-1]["draw_date"],
                              "last_key": recs[-1]["draw_key"], "draw_size": r, "ticket": r,
                              "source_disagreements": 0}
    (v / "decision.json").write_text(json.dumps({"run": run_id, "validation": {"database_sha256": db_sha},
                                                 "pad": ["x" * 40] * 50}, indent=2))
    (v / "colectare.json").write_text(json.dumps({"run": run_id, "idx": idx}, indent=2))
    (v / "MANIFEST_LIVE.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    for p in v.iterdir():
        p.chmod(0o444)
    return name


def _point(live: Path, cur: str, prev: str | None) -> None:
    vers = live / "versiuni"
    mb = (vers / cur / "MANIFEST_LIVE.json").read_bytes()
    m = json.loads(mb)
    ptr = {"updated_utc": "2026-10-26T20:00:00Z", "run_id": m["run_id"], "database_sha256": m["database_sha256"],
           "version_dir": f"versiuni/{cur}", "manifest_sha256": _sha(mb),
           "games": {g: {k: gm[k] for k in ("records", "last_date", "last_key", "sha256")} for g, gm in m["games"].items()},
           "previous": f"versiuni/{prev}" if prev else None}
    (live / "CURRENT_LIVE.json").write_text(json.dumps(ptr, indent=2) + "\n")


class _Live(type(Path())):
    """Calea arhivei sintetice + numele versiunilor (v1..v7)."""
    names: list[str]


@pytest.fixture
def live(tmp_path):
    """v1..v3 = clasa A (40 extrageri), v4..v7 = clasa B (41); v6 = precedentă, v7 = curentă."""
    lv = _Live(tmp_path / "live")
    vers = lv / "versiuni"
    names = [_make_version(vers, i, 40 if i <= 3 else 41) for i in range(1, 8)]
    _point(lv, names[6], names[5])
    (lv / "ISTORIC_LIVE.jsonl").write_text("".join(json.dumps({"version_dir": f"versiuni/{n}"}) + "\n" for n in names))
    lv.names = names
    return lv


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None, p.stat().st_mode)
            for p in sorted(root.rglob("*"))}


def _originals(lv: Path) -> dict:
    vers = lv / "versiuni"
    return {n: {**DD.materialize(vers, vers / n), "MANIFEST_LIVE.json": (vers / n / "MANIFEST_LIVE.json").read_bytes()}
            for n in lv.names}


def _materialized(lv: Path) -> dict:
    vers = lv / "versiuni"
    return {n: {**DD.materialize(vers, vers / n), "MANIFEST_LIVE.json": (vers / n / "MANIFEST_LIVE.json").read_bytes()}
            for n in lv.names}


def _meta(lv: Path, n: str) -> dict:
    return json.loads((lv / "versiuni" / n / "DEDUP_LIVE.json").read_bytes())


def test_T1_lossless(live):
    before = _originals(live)
    size0 = DD.tree_bytes(live / "versiuni")
    r = DD.run(live)
    assert not r["errors"] and len(r["done"]) == 5
    assert _materialized(live) == before
    assert DD.verify_all(live)["ok"]
    assert DD.tree_bytes(live / "versiuni") < size0


def test_T2_protected_untouched(live):
    vers = live / "versiuni"
    prot = live.names[5:]
    snap = {n: {p.name: (p.read_bytes(), p.stat().st_ino) for p in (vers / n).iterdir()} for n in prot}
    ptr, ist = (live / "CURRENT_LIVE.json").read_bytes(), (live / "ISTORIC_LIVE.jsonl").read_bytes()
    DD.run(live)
    for n in prot:
        assert not (vers / n / "DEDUP_LIVE.json").exists()
        assert {p.name: (p.read_bytes(), p.stat().st_ino) for p in (vers / n).iterdir()} == snap[n]
    assert (live / "CURRENT_LIVE.json").read_bytes() == ptr and (live / "ISTORIC_LIVE.jsonl").read_bytes() == ist


def test_T3_representatives_and_classes(live):
    n = live.names
    DD.run(live)
    methods = {v: {f: e["method"] for f, e in _meta(live, v)["files"].items()} for v in n[:5]}
    for rep in (n[0], n[3]):
        assert set(methods[rep].values()) == {"gzip"}
    for v, rep in ((n[1], n[0]), (n[2], n[0]), (n[4], n[3])):
        files = _meta(live, v)["files"]
        for g in DD.GAMES:
            assert files[f"extrageri_{g}.jsonl"]["method"] == "ref" and files[f"extrageri_{g}.jsonl"]["ref"] == rep
        assert files["decision.json"]["method"] == "gzip"
        assert not list((live / "versiuni" / v).glob("*.jsonl*"))
    assert _meta(live, n[0])["content_key"] != _meta(live, n[3])["content_key"]
    assert _meta(live, n[1])["content_key"] == _meta(live, n[0])["content_key"]


def test_T4_tamper_refused(live):
    vers = live / "versiuni"
    rep = vers / live.names[0]
    p = rep / "extrageri_540.jsonl"
    p.chmod(0o644)
    p.write_bytes(p.read_bytes().replace(b'"run_id": "2026102', b'"run_id": "2026103', 1))  # cheie de conținut egală
    r = DD.run(live)
    bad = {e["version"] for e in r["errors"]}
    assert {live.names[0], live.names[1], live.names[2]} <= bad
    for v in live.names[:3]:
        assert not (vers / v / "DEDUP_LIVE.json").exists() and (vers / v / "extrageri_649.jsonl").exists()
    assert not DD.verify_all(live)["ok"]
    # a doua parte: o versiune compactă falsificată ⇒ --verifica = 1
    p.write_bytes(p.read_bytes().replace(b'"run_id": "2026103', b'"run_id": "2026102', 1))
    DD.run(live)
    assert DD.main(["--verifica", "--live-root", str(live)]) == 0
    g = vers / live.names[3] / "decision.json.gz"
    g.chmod(0o644)
    g.write_bytes(gzip.compress(b"altceva", mtime=0))
    assert DD.main(["--verifica", "--live-root", str(live)]) == 1


def test_T5_idempotent(live):
    DD.run(live)
    t = _tree(live / "versiuni")
    r = DD.run(live)
    assert r["done"] == [] and r["errors"] == [] and r["recovery"] == []
    assert _tree(live / "versiuni") == t


def test_T6_recovery(live):
    vers = live / "versiuni"
    a, b, c = live.names[0], live.names[1], live.names[3]
    orig = _originals(live)
    os.rename(vers / a, vers / f"{DD.OLD_PREFIX}{a}")                       # (1) X absent
    shutil.copytree(vers / b, vers / f"{DD.OLD_PREFIX}{b}")                 # (2) X prezent și valid
    shutil.copytree(vers / c, vers / f"{DD.OLD_PREFIX}{c}")                 # (3) X prezent și invalid
    q = vers / c / "extrageri_649.jsonl"
    q.chmod(0o644)
    q.write_bytes(b"{}\n")
    (vers / f"{DD.TMP_PREFIX}zzz_1").mkdir()
    ev = DD.recover(vers)
    ops = {(e["op"], e.get("version")) for e in ev}
    assert ("recover_restore", a) in ops and ("recover_drop_old", b) in ops and ("recover_restore_bad_new", c) in ops
    assert ("recover_drop_tmp", None) in ops
    assert not list(vers.glob(f"{DD.OLD_PREFIX}*")) and not list(vers.glob(f"{DD.TMP_PREFIX}*"))
    assert len(list(vers.glob(f"{DD.BAD_PREFIX}{c}_*"))) == 1
    assert _originals(live) == orig


def test_T7_rehydrate_protected(live, tmp_path):
    vers = live / "versiuni"
    orig = _originals(live)
    DD.run(live)
    n = live.names
    assert (vers / n[1] / "DEDUP_LIVE.json").exists() and (vers / n[2] / "DEDUP_LIVE.json").exists()
    _point(live, n[2], n[1])                       # pointerul ajunge (ipotetic) pe o versiune compactă
    with pytest.raises(PM.IntegrityError):
        PM.resolve_live("540", live)               # fail-closed înainte de rehidratare
    r = DD.run(live)
    assert {(d["op"], d["version"]) for d in r["done"]} >= {("rehydrate", n[2]), ("rehydrate", n[1])}
    for v in (n[1], n[2]):
        assert not (vers / v / "DEDUP_LIVE.json").exists()
        files = {p.name: p.read_bytes() for p in (vers / v).iterdir()}
        assert files == orig[v]
    for g in ("540", "joker"):
        path, prov = PM.resolve_live(g, live)
        assert prov["version_dir"] == f"versiuni/{n[2]}"
    assert _materialized(live) == orig


def test_T8_reconstruct(live, tmp_path):
    orig = _originals(live)
    DD.run(live)
    v = live.names[2]
    out = tmp_path / "rec"
    assert DD.main(["--reconstruieste", v, "--out", str(out), "--live-root", str(live)]) == 0
    assert {p.name: p.read_bytes() for p in out.iterdir()} == orig[v]
    with pytest.raises(DD.DedupError):
        DD.reconstruct(live, v, live / "inauntru")
    with pytest.raises(DD.DedupError):
        DD.reconstruct(live, v, out)               # refuz de suprascriere


def test_T9_dry_run_writes_nothing(live):
    t = _tree(live)
    assert DD.main(["--simulare", "--live-root", str(live)]) == 0
    r = DD.run(live, dry=True)
    assert len(r["done"]) == 5 and r["bytes_after_estimate"] < r["bytes_before"]
    assert _tree(live) == t


def test_T10_parser_multi_after_compaction(live):
    DD.run(live)
    for g in ("540", "joker"):
        path, prov = PM.resolve_live(g, live)
        assert prov["version_dir"] == f"versiuni/{live.names[6]}" and path.is_file()
    for v in live.names[:5]:
        for e in _meta(live, v)["files"].values():
            if e["method"] == "ref":
                assert all(x["method"] == "gzip" for x in _meta(live, e["ref"])["files"].values())


def test_T11_frozen_and_stdlib_only():
    seal = json.loads((ROOT / "tu3" / "SIGILIU_TU3_DD.json").read_text())
    import inlocuiri_tu3 as INL   # TU3-L649 §5.4: fișier înghețat = identic SAU înlocuit sigilat (inlocuiri_tu3/v1)
    res = INL.resolve(seal["frozen_hashes"], ROOT)
    assert res["drift"] == [], res["drift"]
    for path, h in seal["frozen_external"].items():
        assert _sha(Path(path).read_bytes()) == h, path
    assert _sha((ROOT / "tu3" / "PROTOCOL_TU3_DD.md").read_bytes()) == seal["sha256"]
    tree = ast.parse((ROOT / "tu3" / "dedup_live.py").read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert mods <= set(sys.stdlib_module_names), mods - set(sys.stdlib_module_names)
