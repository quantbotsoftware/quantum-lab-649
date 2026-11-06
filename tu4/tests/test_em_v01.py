"""Teste TU4-EM-V01 (tu4/AMENDAMENT_TU4_EM_V01.md §5, A1–A7). Citire numai pe rădăcina reală; scrieri numai în tmp_path.
positive_claims_allowed=false."""
from __future__ import annotations

import ast
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

TU4 = Path(__file__).resolve().parents[1]
QL = TU4.parent
SSD = Path("./ssd_data/QL649_TU4_EM")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V1 = _load("verifica_em_v01_t", TU4 / "verifica_em_v01.py")
VE = _load("verifica_em_t", TU4 / "verifica_em.py")
DD = _load("dedup_live_t", QL / "tu3" / "dedup_live.py")
sha = lambda b: hashlib.sha256(b).hexdigest()


def _ssd():
    return SSD if SSD.is_dir() else None


def _emissions():
    return sorted((TU4 / "tribunal" / "emisii").glob("*/*.json"))


@pytest.fixture(scope="module")
def real_new():
    return V1.verify(QL, _ssd(), False)


# A1
def test_a1_real_root_pass(real_new):
    assert real_new["verdict"] == "VERIFICARE_EM_PASS", [c for c in real_new["checks"] if c["status"] != "PASS"]
    v23 = [c for c in real_new["checks"] if c["check"].startswith(("V2_", "V3_"))]
    assert v23 and all(c["status"] == "PASS" for c in v23)
    for e in real_new["emissions"]:
        assert e["archive_resolution"] in ("raw", "gzip") or e["archive_resolution"].startswith("ref:")


# A2
def test_a2_equivalence_with_sealed_verifier(real_new):
    old = VE.verify(QL, _ssd(), False)
    on = {c["check"]: c["status"] for c in old["checks"]}
    nn = {c["check"]: c["status"] for c in real_new["checks"]}
    assert set(on) <= set(nn)
    for k, s in on.items():
        if not k.startswith(("V2_", "V3_recompute_")):
            assert nn[k] == s, (k, s, nn[k])
    extra = set(nn) - set(on)
    assert all(x.startswith(("V1_amendment_", "V2_fingerprint_")) for x in extra), extra


# A3
def test_a3_reconstruction_equals_dedup_live():
    vers = QL / "tu3" / "date" / "live" / "versiuni"
    seen = set()
    for p in _emissions():
        arch = json.loads(p.read_bytes())["archive"]
        vd = QL / "tu3" / "date" / "live" / arch["version_dir"]
        ref = DD.materialize(vers, vd)
        for name in sorted(n for n in ref if n.endswith(".jsonl")):
            if (vd.name, name) in seen:
                continue
            seen.add((vd.name, name))
            data, _res = V1.read_version_file(vers, vd, name)
            assert data == ref[name], (vd.name, name)
    assert seen


# A4 — arbore sintetic
def _dumps(rec):
    return json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"


def _build(tmp: Path):
    vers = tmp / "tu3" / "date" / "live" / "versiuni"
    a, b = vers / "aaaaaaaaaaaa", vers / "bbbbbbbbbbbb"
    a.mkdir(parents=True)
    b.mkdir()
    rows = [{"date": f"2020-01-{i + 1:02d}", "numbers": sorted({(i * 7 + j * 11) % 49 + 1 for j in range(6)} | set())[:6]}
            for i in range(9)]
    rows = [r for r in rows if len(r["numbers"]) == 6]
    man_a = {"run_id": "RA", "database_sha256": "a" * 64, "games": {}}
    man_b = {"run_id": "RB", "database_sha256": "b" * 64, "games": {}}
    pa = "".join(_dumps(dict(r, provenance={"database_sha256": man_a["database_sha256"], "run_id": "RA"})) for r in rows)
    pb = "".join(_dumps(dict(r, provenance={"database_sha256": man_b["database_sha256"], "run_id": "RB"})) for r in rows)
    pa, pb = pa.encode(), pb.encode()
    col = b'{"x": 1}\n'
    man_a["games"]["649"] = {"file": "extrageri_649.jsonl", "sha256": sha(pa)}
    man_b["games"]["649"] = {"file": "extrageri_649.jsonl", "sha256": sha(pb)}
    (a / "MANIFEST_LIVE.json").write_text(json.dumps(man_a))
    (a / "extrageri_649.jsonl").write_bytes(pa)
    (b / "MANIFEST_LIVE.json").write_text(json.dumps(man_b))
    gzc = gzip.compress(col, compresslevel=9, mtime=0)
    (b / "colectare.json.gz").write_bytes(gzc)
    meta = {"schema": "tu3-dedup-live/1", "version": b.name, "manifest_sha256": sha((b / "MANIFEST_LIVE.json").read_bytes()),
            "files": {"colectare.json": {"sha256": sha(col), "bytes": len(col), "method": "gzip",
                                         "stored": "colectare.json.gz", "stored_sha256": sha(gzc)},
                      "extrageri_649.jsonl": {"sha256": sha(pb), "bytes": len(pb), "method": "ref", "ref": a.name,
                                              "ref_manifest_sha256": sha((a / "MANIFEST_LIVE.json").read_bytes())}}}
    (b / "DEDUP_LIVE.json").write_text(json.dumps(meta))
    return vers, a, b, pa, pb, col, meta


def test_a4_synthetic_roundtrip(tmp_path):
    vers, a, b, pa, pb, col, _ = _build(tmp_path)
    assert V1.read_version_file(vers, a, "extrageri_649.jsonl") == (pa, "raw")
    assert V1.read_version_file(vers, b, "extrageri_649.jsonl") == (pb, f"ref:{a.name}")
    assert V1.read_version_file(vers, b, "colectare.json") == (col, "gzip")
    ref = DD.materialize(vers, b)
    assert ref["extrageri_649.jsonl"] == pb and ref["colectare.json"] == col


@pytest.mark.parametrize("tamper", ["rep_byte", "stored_sha", "manifest", "depth2", "method", "slash_ref"])
def test_a4_synthetic_tamper_refused(tmp_path, tamper):
    vers, a, b, pa, pb, col, meta = _build(tmp_path)
    name = "extrageri_649.jsonl"
    if tamper == "rep_byte":
        (a / name).write_bytes(pa.replace(b'"numbers"', b'"numberz"', 1))
    elif tamper == "stored_sha":
        meta["files"]["colectare.json"]["stored_sha256"] = "0" * 64
        name = "colectare.json"
    elif tamper == "manifest":
        (b / "MANIFEST_LIVE.json").write_text(json.dumps({"run_id": "RX", "database_sha256": "c" * 64, "games": {}}))
    elif tamper == "depth2":
        c = vers / "cccccccccccc"
        c.mkdir()
        (c / "MANIFEST_LIVE.json").write_text(json.dumps({"run_id": "RC", "database_sha256": "c" * 64, "games": {}}))
        (c / "DEDUP_LIVE.json").write_text(json.dumps({"schema": "tu3-dedup-live/1",
            "manifest_sha256": sha((c / "MANIFEST_LIVE.json").read_bytes()),
            "files": {name: {"method": "ref", "ref": a.name, "sha256": "0" * 64, "bytes": 0}}}))
        meta["files"][name]["ref"] = c.name
        meta["files"][name]["ref_manifest_sha256"] = sha((c / "MANIFEST_LIVE.json").read_bytes())
    elif tamper == "method":
        meta["files"][name]["method"] = "xz"
    elif tamper == "slash_ref":
        meta["files"][name]["ref"] = "../" + a.name
    if tamper not in ("rep_byte", "manifest"):
        (b / "DEDUP_LIVE.json").write_text(json.dumps(meta))
    with pytest.raises((V1.ArchiveError, OSError, ValueError)):
        V1.read_version_file(vers, b, name)
    with pytest.raises(V1.ArchiveError):
        V1.read_version_file(vers, b, "../x")


# A5
def test_a5_fingerprint_detects_altered_sha():
    p = _emissions()[0]
    em = json.loads(p.read_bytes())
    arch = dict(em["archive"])
    assert V1.fingerprint(QL, em["game"], arch)[0] is True
    assert V1.archive_bytes(QL, arch)[0] is not None
    arch["sha256"] = "f" * 64
    assert V1.fingerprint(QL, em["game"], arch)[0] is False
    data, res = V1.archive_bytes(QL, arch)
    assert data is None and "sha256" in res
    arch2 = dict(em["archive"], version_dir="../../x")
    assert V1.archive_bytes(QL, arch2)[0] is None


# A6
def test_a6_independence():
    src = (TU4 / "verifica_em_v01.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = {(a.name if isinstance(n, ast.Import) else n.module).split(".")[0]
            for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    assert mods <= {"__future__", "argparse", "datetime", "gzip", "hashlib", "importlib", "json", "os", "stat", "sys",
                    "pathlib", "numpy"}, mods
    for bad in ("torch", "ip_core", "emite", "dedup_live", "judecator"):
        assert bad not in mods
    assert sha((TU4 / "verifica_em.py").read_bytes()) == V1.ORIG_VERIFIER_SHA


# A7
def test_a7_amendment_seal():
    seal = json.loads((TU4 / "SIGILIU_AMENDAMENT_TU4_EM_V01.json").read_bytes())
    assert sha((TU4 / "AMENDAMENT_TU4_EM_V01.md").read_bytes()) == seal["sha256"] == V1.AMEND_DOC_SHA
    assert sha((TU4 / "SIGILIU_AMENDAMENT_TU4_EM_V01.json").read_bytes()) == V1.AMEND_SEAL_SHA
    assert seal["code_files_present"] == [] and seal["results_present"] is False
    assert seal["new_files_planned"] == ["tu4/verifica_em_v01.py", "tu4/tests/test_em_v01.py"]
    assert seal["positive_claims_allowed"] is False
    for f in ("tu4/verifica_em.py", "tu4/judecator.py", "tu4/emite.py", "tu3/dedup_live.py"):
        assert sha((QL / f).read_bytes()) == seal["frozen_hashes"][f], f
    assert all((os.stat(TU4 / x).st_mode & 0o222) == 0 for x in ("AMENDAMENT_TU4_EM_V01.md",
                                                               "SIGILIU_AMENDAMENT_TU4_EM_V01.json"))
