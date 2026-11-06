"""Martorii P1–P8 ai modulului P (PROTOCOL_TU3_P.md §6). Fixturi sintetice în directoare temporare + citiri read-only."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joker_entanglement as J  # noqa: E402
import parser_multi as PM  # noqa: E402

QP = PM.QP
HAS_CUDA = torch.cuda.is_available()
ENGINE_SHA = "1da9be4e05bcefe401c299b6e6cd0ca7e4d6057939756057822cb43c951cb2ae"
PARSER_SHA = "219e5d2085a72e960583830a6acd009e376f01079381ad0e09824fd200ee8968"
PARSER_MANIFEST_SHA = "ee8f2c9c41138111d96ae343bf5c62bf9ad99276694f291ddf704e26aa666f4b"


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _rec(game, date, nums, joker=None, key=None, stored=None, kind="regular", dis=False, **extra):
    k = key if key is not None else f"{game}:{date}:{'-'.join(map(str, nums))}" + (f":J{joker}" if joker else "")
    r = {"draw_key": k, "draw_date": date, "game": game, "numbers": sorted(nums) if isinstance(nums, list) and
         all(isinstance(x, int) for x in nums) else nums, "numbers_order_as_stored": stored if stored is not None
         else nums, "joker": joker, "draw_kind": kind, "has_source_disagreement": dis, "verification": "x",
         "source_count": 2, "provenance": {"run_id": "t"}}
    r.update(extra)
    return r


def _write(path: Path, rows) -> Path:
    lines = [r if isinstance(r, str) else json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# P1 — un rând pentru fiecare motiv de excludere
# ---------------------------------------------------------------------------
def _invalid_rows(game):
    g = PM.GAMES[game]
    ok = [1, 2, 3, 4, 5, 6][: g.r]
    jk = 7 if g.joker_m else None
    rows = [
        _rec(game, "2020-01-01", ok, jk, key=""),                                   # draw_key_missing
        _rec("649" if game != "649" else "540", "2020-01-02", ok, jk),               # game_mismatch
        dict(_rec(game, "2020-01-03", ok, jk), draw_date=None),                      # draw_date_missing
        _rec(game, "2020-13-40", ok, jk),                                            # draw_date_invalid
        _rec(game, "2020-01-05", ok[:-1], jk),                                       # numbers_count_invalid
        _rec(game, "2020-01-06", ok[:-1] + [True], jk),                              # numbers_not_int
        _rec(game, "2020-01-07", ok[:-1] + [g.n + 1], jk),                           # numbers_out_of_range
        _rec(game, "2020-01-08", ok[:-1] + [ok[0]], jk),                             # numbers_duplicate_in_row
    ]
    if g.joker_m:
        rows += [_rec(game, "2020-01-09", ok, None, key=f"{game}:a"),                # joker_missing
                 _rec(game, "2020-01-10", ok, "7", key=f"{game}:b"),                 # joker_not_int
                 _rec(game, "2020-01-11", ok, 21, key=f"{game}:c")]                  # joker_out_of_range
    else:
        rows += [_rec(game, "2020-01-12", ok, 3)]                                    # joker_unexpected
    rows += [_rec(game, "2020-02-01", ok, jk, key=f"{game}:dup"),
             _rec(game, "2020-02-02", [x + 1 for x in ok], jk, key=f"{game}:dup"),   # duplicate_draw_key
             _rec(game, "2020-02-01", ok, jk, key=f"{game}:other")]                  # duplicate_date_set
    return rows


@pytest.mark.parametrize("game", ["540", "joker"])
def test_P1_reasons_exact(tmp_path, game):
    src = _write(tmp_path / "x.jsonl", _invalid_rows(game) + ["{not json", "[1,2]"])
    ds = PM.build_game_dataset(game, src, device="cpu")
    want = {"draw_key_missing": 1, "game_mismatch": 1, "draw_date_missing": 1, "draw_date_invalid": 1,
            "numbers_count_invalid": 1, "numbers_not_int": 1, "numbers_out_of_range": 1,
            "numbers_duplicate_in_row": 1, "duplicate_draw_key": 1, "duplicate_date_set": 1}
    want.update({"joker_missing": 1, "joker_not_int": 1, "joker_out_of_range": 1} if game == "joker"
                else {"joker_unexpected": 1})
    assert ds.anomalies["removed_by_reason"] == want
    assert ds.keys == [f"{game}:dup"] and ds.n_draws == 1
    assert [e["reason"].split(":")[0] for e in ds.json_errors] == ["json_invalid", "json_not_object"]
    assert ds.n_raw == len(_invalid_rows(game)) + 2


# ---------------------------------------------------------------------------
# P2 — deduplicare, ordonare stabilă, grupare pe zile
# ---------------------------------------------------------------------------
def test_P2_order_and_steps(tmp_path):
    rows = [_rec("540", "2021-03-04", [1, 2, 3, 4, 5, 6], key="540:2021-03-04:b"),
            _rec("540", "2021-03-01", [7, 8, 9, 10, 11, 12], key="540:2021-03-01:z"),
            _rec("540", "2021-03-04", [13, 14, 15, 16, 17, 40], key="540:2021-03-04:a", kind="special"),
            _rec("540", "2021-03-02", [2, 3, 4, 5, 6, 7], key="540:2021-03-02:q", stored=[7, 6, 5, 4, 3, 2]),
            _rec("540", "2021-03-02", [2, 3, 4, 5, 6, 7], key="540:2021-03-02:r"),          # duplicate_date_set
            _rec("540", "2021-03-09", [1, 3, 5, 7, 9, 11], key="X:2021-03-09", dis=True,
                 stored=[1, 3, 5, 7, 9, 12])]
    ds = PM.build_game_dataset("540", _write(tmp_path / "s.jsonl", rows), device="cpu")
    assert ds.keys == ["540:2021-03-01:z", "540:2021-03-02:q", "540:2021-03-04:a", "540:2021-03-04:b",
                       "X:2021-03-09"]
    assert ds.step_dates == ["2021-03-01", "2021-03-02", "2021-03-04", "2021-03-09"]
    assert ds.step_offsets.tolist() == [0, 1, 2, 4, 5]
    assert ds.step_index.tolist() == [0, 1, 2, 2, 3]
    assert ds.anomalies["removed_by_reason"] == {"duplicate_date_set": 1}
    assert sorted(f["flag"] for f in ds.anomalies["flags"]) == ["key_prefix_mismatch", "source_disagreement_kept",
                                                                 "stored_vs_sorted_mismatch"]
    assert ds.anomalies["kinds_kept"] == {"regular": 4, "special": 1}
    assert ds.summary()["double_draw_days"] == 1
    assert ds.draws[1].tolist() == [2, 3, 4, 5, 6, 7]


# ---------------------------------------------------------------------------
# P3 — tensori; Joker = joker_entanglement.joint_counts; GPU = CPU bit cu bit
# ---------------------------------------------------------------------------
def _synth(game, T, seed):
    g = PM.GAMES[game]
    gen = torch.Generator().manual_seed(seed)
    rows = []
    for t in range(T):
        nums = (torch.randperm(g.n, generator=gen)[: g.r] + 1).tolist()
        jk = int(torch.randint(1, 21, (1,), generator=gen)) if g.joker_m else None
        d = f"{2000 + t // 300:04d}-{1 + (t // 25) % 12:02d}-{1 + t % 25:02d}"
        rows.append(_rec(game, d, nums, jk, key=f"{game}:{t:05d}", stored=nums))
    return rows


@pytest.mark.parametrize("game", ["540", "joker"])
def test_P3_tensors(tmp_path, game):
    g = PM.GAMES[game]
    src = _write(tmp_path / "t.jsonl", _synth(game, 1500, 11))
    ds = PM.build_game_dataset(game, src, device="cpu")
    T = ds.n_draws
    assert T == 1500 and ds.draws.shape == (T, g.r) and ds.onehot.shape == (T, g.n)
    assert bool((ds.onehot.sum(1) == g.r).all())
    assert torch.equal(torch.diagonal(ds.pair_counts), ds.onehot.sum(0))
    assert torch.equal(ds.pair_counts, ds.pair_counts.T)
    if g.joker_m:
        assert ds.joker_onehot.shape == (T, 20) and bool((ds.joker_onehot.sum(1) == 1).all())
        assert float(ds.cross_counts.sum()) == 5 * T
        jc = J.joint_counts(ds.draws - 1, ds.joker - 1)[0]
        assert torch.equal(ds.cross_counts.double(), jc)
        J.validate_draws(ds.draws, ds.joker)
    else:
        assert ds.joker is None and ds.cross_counts is None
    if HAS_CUDA:
        dg = PM.build_game_dataset(game, src, device="cuda")
        assert dg.device.type == "cuda"
        for name in ("draws", "onehot", "step_index", "step_offsets", "pair_counts", "joker", "joker_onehot",
                     "cross_counts"):
            a, b = getattr(ds, name), getattr(dg, name)
            assert (a is None and b is None) or torch.equal(a, b.cpu()), name


# ---------------------------------------------------------------------------
# P4 — 6/49 deleagă exact la parser.build_dataset
# ---------------------------------------------------------------------------
def test_P4_delegation_649(tmp_path):
    rows = _synth("649", 400, 5)
    rows[10]["numbers"] = [1, 2, 3, 4, 5]                      # numbers_count_invalid
    rows[11]["numbers"] = [1, 2, 3, 4, 5, 50]                  # numbers_out_of_range
    rows[12]["draw_date"] = "2001-02-30"                       # draw_date_invalid
    rows.append(dict(rows[20]))                                # duplicate_draw_key
    rows.append(dict(rows[21], draw_key="649:alt"))            # duplicate_date_set
    rows[30]["has_source_disagreement"] = True
    rows[31]["numbers_order_as_stored"] = [1, 2, 3, 4, 5, 6]   # stored_vs_sorted_mismatch (probabil)
    live_src = _write(tmp_path / "live649.jsonl", rows + ["{broken"])
    # echivalentul scris independent în schema parser.py
    prows = [{"draw_key": r["draw_key"], "draw_date": r["draw_date"], "numbers_sorted": r["numbers"],
              "numbers_as_stored": r["numbers_order_as_stored"], "draw_kind_as_stored": r["draw_kind"],
              "has_source_disagreement_as_stored": r["has_source_disagreement"]} for r in rows]
    par_src = _write(tmp_path / "parser649.jsonl", prows + ["{broken"])
    ref = QP.build_dataset(par_src, device="cpu")
    deriv = tmp_path / "derivat"
    ds = PM.build_game_dataset("649", live_src, device="cpu", deriv_root=deriv)
    for name in ("draws", "onehot", "step_index", "step_offsets", "pair_counts"):
        assert torch.equal(getattr(ds, name), getattr(ref, name)), name
    assert (ds.keys, ds.dates, ds.step_dates, ds.kinds) == (ref.keys, ref.dates, ref.step_dates, ref.kinds)
    assert ds.anomalies["removed"] == ref.anomalies["removed"]
    assert ds.anomalies["flags"] == ref.anomalies["flags"]
    assert ds.anomalies["removed_by_reason"] == {"numbers_count_invalid": 1, "numbers_out_of_range": 1,
                                                 "draw_date_invalid": 1, "duplicate_draw_key": 1,
                                                 "duplicate_date_set": 1}
    assert ds.json_errors == ref.json_errors and ds.n_raw == ref.n_raw
    assert isinstance(ds.base, QP.Dataset) and ds.joker is None and ds.game.r == 6
    adapted = Path(ds.provenance["adapted_path"])
    h = _sha(adapted)
    ds2 = PM.build_game_dataset("649", live_src, device="cpu", deriv_root=deriv)
    assert ds2.provenance["adapted_path"] == str(adapted) and _sha(adapted) == h
    adapted.chmod(0o644)
    adapted.write_text("altceva\n")
    with pytest.raises(PM.IntegrityError):
        PM.build_game_dataset("649", live_src, device="cpu", deriv_root=deriv)


# ---------------------------------------------------------------------------
# P5 — lanțul de integritate LIVE
# ---------------------------------------------------------------------------
def _make_live(root: Path) -> Path:
    vdir = root / "versiuni" / "abc123"
    vdir.mkdir(parents=True)
    games = {}
    for game, T in (("649", 30), ("540", 30), ("joker", 30)):
        f = _write(vdir / f"extrageri_{game}.jsonl", _synth(game, T, 3))
        games[game] = {"file": f.name, "sha256": _sha(f), "records": T, "excluded": [], "last_date": None,
                       "draw_size": PM.GAMES[game].r}
    man = vdir / "MANIFEST_LIVE.json"
    man.write_text(json.dumps({"games": games}, indent=2))
    ptr = {"run_id": "r", "database_sha256": "0" * 64, "version_dir": "versiuni/abc123", "manifest_sha256": _sha(man),
           "games": {g: {"records": v["records"], "sha256": v["sha256"]} for g, v in games.items()}}
    (root / "CURRENT_LIVE.json").write_text(json.dumps(ptr))
    return root


@pytest.mark.parametrize("attack", ["byte", "manifest", "pointer_hash", "count", "traversal", "none"])
def test_P5_integrity(tmp_path, attack):
    root = _make_live(tmp_path / "live")
    vdir = root / "versiuni" / "abc123"
    ptr_p = root / "CURRENT_LIVE.json"
    ptr = json.loads(ptr_p.read_text())
    if attack == "byte":
        b = bytearray((vdir / "extrageri_540.jsonl").read_bytes())
        b[5] ^= 1
        (vdir / "extrageri_540.jsonl").write_bytes(bytes(b))
    elif attack == "manifest":
        m = json.loads((vdir / "MANIFEST_LIVE.json").read_text())
        m["games"]["540"]["records"] = 31
        (vdir / "MANIFEST_LIVE.json").write_text(json.dumps(m))
    elif attack == "pointer_hash":
        ptr["games"]["540"]["sha256"] = "f" * 64
        ptr_p.write_text(json.dumps(ptr))
    elif attack == "count":   # manifest + pointer coerente între ele, dar fișierul are alt număr de rânduri
        m = json.loads((vdir / "MANIFEST_LIVE.json").read_text())
        m["games"]["540"]["records"] = 29
        (vdir / "MANIFEST_LIVE.json").write_text(json.dumps(m))
        ptr["games"]["540"]["records"] = 29
        ptr["manifest_sha256"] = _sha(vdir / "MANIFEST_LIVE.json")
        ptr_p.write_text(json.dumps(ptr))
    elif attack == "traversal":
        outside = tmp_path / "evil"
        shutil.copytree(vdir, outside)
        ptr["version_dir"] = "versiuni/../../evil"
        ptr_p.write_text(json.dumps(ptr))
    if attack == "none":
        for game in PM.GAMES:
            ds = PM.build_game_dataset(game, "live", device="cpu", live_root=root, deriv_root=tmp_path / "d")
            assert ds.n_draws == 30 and ds.source_kind == "live"
    else:
        with pytest.raises(PM.IntegrityError):
            PM.build_game_dataset("540", "live", device="cpu", live_root=root)


# ---------------------------------------------------------------------------
# P6 / P7 — date reale (read-only): LIVE și exporturile înghețate
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def real():
    ptr = json.loads((PM.LIVE / "CURRENT_LIVE.json").read_text())
    live = {g: PM.build_game_dataset(g, "live") for g in PM.GAMES}
    frozen = {g: PM.build_game_dataset(g, "frozen") for g in PM.GAMES}
    return ptr, live, frozen


def test_P6_live_real(real):
    ptr, live, _ = real
    for g, ds in live.items():
        assert ds.n_draws == ptr["games"][g]["records"], g
        assert not ds.anomalies["removed"] and not ds.json_errors, g
        assert ds.step_dates[-1] == ptr["games"][g]["last_date"], g
        assert ds.source_sha256 == ptr["games"][g]["sha256"], g
        assert ds.device.type == ("cuda" if HAS_CUDA else "cpu")
    assert live["540"].game.r == 6 and live["540"].game.ticket == 5 and live["540"].draws.shape[1] == 6
    assert int(live["540"].draws.max()) <= 40
    J.validate_draws(live["joker"].draws, live["joker"].joker)
    assert live["joker"].cross_counts.shape == (45, 20)


def test_P7_frozen_real(real):
    _, live, frozen = real
    man = json.loads((PM.DATA / "MANIFEST_DATE.json").read_text())
    for g in ("540", "joker"):
        ds = frozen[g]
        assert ds.n_draws == man["games"][g]["records"] and ds.source_sha256 == man["games"][g]["sha256"]
        assert not ds.anomalies["removed"] and not ds.json_errors
        rep = PM.compare_frozen_live(ds, live[g])
        assert rep["live_superset_of_frozen"], rep
    assert frozen["649"].source_sha256 == PM.FROZEN_649_SHA256
    rep = PM.compare_frozen_live(frozen["649"], live["649"])   # descriptiv; fără aserțiune de egalitate
    assert set(rep) >= {"only_in_frozen", "only_in_live", "differing_on_common_keys"}


# ---------------------------------------------------------------------------
# P8 — fișierele sigilate rămân neatinse
# ---------------------------------------------------------------------------
def test_P8_sealed_untouched():
    assert _sha(PM.QL / "engine.py") == ENGINE_SHA
    assert _sha(PM.QL / "parser.py") == PARSER_SHA
    assert _sha(PM.QL / "rezultate" / "parser_manifest.json") == PARSER_MANIFEST_SHA
