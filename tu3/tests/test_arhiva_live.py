"""Teste pentru arhiva LIVE (baze temporare; nu atinge datele reale)."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import arhiva_live as AL  # noqa: E402

PROV = {"run_id": "t", "database_sha256": "0" * 64}


def _row(key, date, nums, joker=None):
    r = {"draw_key": key, "draw_date": date, "draw_kind": "regular", "joker": joker, "verification": "x",
         "source_count": 2, "has_source_disagreement": 0}
    for i in range(6):
        r[f"n{i + 1}"] = nums[i] if i < len(nums) else None
    return r


def test_rules_three_games():
    assert AL.validate("649", _row("a", "2026-10-25", [1, 2, 3, 4, 5, 49]), PROV)[0]
    assert AL.validate("540", _row("b", "2026-10-25", [1, 8, 12, 21, 22, 16]), PROV)[0]
    assert AL.validate("joker", _row("c", "2026-10-25", [1, 10, 16, 20, 39], 8), PROV)[0]
    assert AL.validate("540", _row("d", "2026-10-25", [1, 2, 3, 4, 5]), PROV)[1] == "5 numere în loc de 6"
    assert "afara" in AL.validate("540", _row("e", "2026-10-25", [1, 2, 3, 4, 5, 41]), PROV)[1]
    assert AL.validate("649", _row("f", "2026-10-25", [1, 1, 3, 4, 5, 6]), PROV)[1] == "numere repetate"
    assert "Joker" in AL.validate("joker", _row("g", "2026-10-25", [1, 2, 3, 4, 5], 21), PROV)[1]
    assert "Joker" in AL.validate("joker", _row("h", "2026-10-25", [1, 2, 3, 4, 5]), PROV)[1]
    assert AL.validate("649", _row("i", "2026-10-25", [1, 2, 3, 4, 5, 6], 3), PROV)[1]


def _db(path: Path, rows: list[tuple[str, dict]]):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE draws (draw_key, draw_date, draw_kind, n1, n2, n3, n4, n5, n6, joker, verification, "
                "source_count, has_source_disagreement, game)")
    for game, r in rows:
        con.execute("INSERT INTO draws VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*[r[c.strip()] for c in AL.COLS.split(",")], game))
    con.commit()
    con.close()


def test_regression_detection(tmp_path):
    base = [("649", _row("649:k1", "2026-10-22", [1, 2, 3, 4, 5, 6])),
            ("540", _row("540:k1", "2026-10-22", [1, 2, 3, 4, 5, 6])),
            ("joker", _row("joker:k1", "2026-10-22", [1, 2, 3, 4, 5], 7))]
    _db(tmp_path / "old.sqlite", base)
    _db(tmp_path / "grow.sqlite", base + [("540", _row("540:k2", "2026-10-25", [7, 8, 9, 10, 11, 12]))])
    _db(tmp_path / "lost.sqlite", base[:2])
    changed = [base[0], base[1], ("joker", _row("joker:k1", "2026-10-22", [1, 2, 3, 4, 5], 8))]
    _db(tmp_path / "changed.sqlite", changed)
    assert AL.no_regression(tmp_path / "grow.sqlite", tmp_path / "old.sqlite", "t") == []
    assert any("lipsește" in p for p in AL.no_regression(tmp_path / "lost.sqlite", tmp_path / "old.sqlite", "t"))
    assert any("diferă" in p for p in AL.no_regression(tmp_path / "changed.sqlite", tmp_path / "old.sqlite", "t"))
    prev = tmp_path / "prev"
    prev.mkdir()
    rec = AL.validate("joker", base[2][1], PROV)[0]
    (prev / "extrageri_joker.jsonl").write_text(json.dumps(rec) + "\n")
    assert AL.no_regression_live(tmp_path / "grow.sqlite", prev) == []
    assert AL.no_regression_live(tmp_path / "changed.sqlite", prev)
