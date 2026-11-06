"""TU3 — exportul arhivelor Loto 5/40 și Joker în JSONL (inventar, NU experiment de selecție).

Sursa: baza candidat validată a colectorului existent (`loto_romania/data/automatizare/rulari/<run>/candidat.sqlite`),
descărcată de colector din loto.ro (oficial) + surse secundare, cu dovezi HTTP în `colectare.json`.
Pași: (1) copie înghețată byte-identică în `tu3/date/sursa/` (hash verificat); (2) citire read-only NUMAI pentru
jocurile '540' și 'joker' (6/49 NU se citește: ținta OGLINDA 649/2026-10-25 rămâne PENDING și separată);
(3) validare (540: 6 numere distincte 1..40 — biletul are 5; joker: 5 distincte 1..45 + Joker 1..20), cu motive
explicite de excludere; (4) comparație cu snapshot-ul canonic intern pe cheile comune; (5) manifest.
Refuză suprascrierea fișierelor existente.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DATA = REPO / "loto_romania" / "data"
RUN_ID = "20261026T173008672174"
RUN = DATA / "automatizare" / "rulari" / RUN_ID
EXPECTED_DB_SHA = "2a0b94233538592f9d3723540e7e9cb9e086e79a4381af4462e8cb015efc2415"
OUT = HERE / "date"
RULES = {"540": dict(n=40, r=6, joker=None, name="Loto 5/40", ticket=5),
         "joker": dict(n=45, r=5, joker=20, name="Joker", ticket="5+1")}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rows(db: Path, game: str) -> list[dict]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = con.execute("SELECT draw_key, draw_date, draw_kind, n1, n2, n3, n4, n5, n6, joker, verification, "
                          "source_count, has_source_disagreement FROM draws WHERE game = ? "
                          "ORDER BY draw_date, draw_key", (game,))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()


def validate(game: str, r: dict) -> tuple[dict | None, str | None]:
    rule = RULES[game]
    order = [r[f"n{i}"] for i in range(1, 7) if r[f"n{i}"] is not None]
    try:
        order = [int(x) for x in order]
    except (TypeError, ValueError):
        return None, "numere nenumerice"
    if len(order) != rule["r"]:
        return None, f"{len(order)} numere în loc de {rule['r']}"
    if len(set(order)) != rule["r"]:
        return None, "numere repetate"
    if min(order) < 1 or max(order) > rule["n"]:
        return None, f"numere în afara 1..{rule['n']}"
    jk = r["joker"]
    if rule["joker"] is not None:
        if jk is None or not (1 <= int(jk) <= rule["joker"]):
            return None, f"Joker lipsă sau în afara 1..{rule['joker']}"
        jk = int(jk)
    elif jk is not None:
        return None, "Joker prezent la un joc fără Joker"
    try:
        dt.date.fromisoformat(r["draw_date"])
    except (TypeError, ValueError):
        return None, "dată invalidă"
    rec = {"game": game, "draw_key": r["draw_key"], "draw_date": r["draw_date"], "draw_kind": r["draw_kind"],
           "numbers": sorted(order), "numbers_order_as_stored": order, "joker": jk,
           "verification": r["verification"], "source_count": r["source_count"],
           "has_source_disagreement": bool(r["has_source_disagreement"]),
           "provenance": {"run_id": RUN_ID, "database_sha256": EXPECTED_DB_SHA}}
    return rec, None


def main() -> int:
    targets = [OUT / "extrageri_540.jsonl", OUT / "extrageri_joker.jsonl", OUT / "MANIFEST_DATE.json"]
    if any(p.exists() for p in targets):
        print("REFUZ: exportul există deja; nu se suprascrie.")
        return 2
    src = RUN / "candidat.sqlite"
    assert sha(src) == EXPECTED_DB_SHA, "baza candidat diferă de cea inventariată"
    decision = json.loads((RUN / "decision.json").read_text())
    assert decision["validation"]["database_sha256"] == EXPECTED_DB_SHA
    (OUT / "sursa").mkdir(parents=True, exist_ok=True)
    frozen = OUT / "sursa" / f"candidat_{RUN_ID}.sqlite"
    shutil.copy2(src, frozen)
    assert sha(frozen) == EXPECTED_DB_SHA
    for extra in ("decision.json", "colectare.json"):
        shutil.copy2(RUN / extra, OUT / "sursa" / f"{extra[:-5]}_{RUN_ID}.json")
    frozen.chmod(0o444)

    canon_ptr = json.loads((DATA / "CURRENT.json").read_text())["snapshot"]
    canon = DATA / "snapshots" / canon_ptr / "loto_romania.sqlite"
    manifest = {"created_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": {"run_id": RUN_ID, "database_sha256": EXPECTED_DB_SHA,
                           "frozen_copy": str(frozen.relative_to(HERE)),
                           "collector_official_urls": sorted({a["requested_url"]
                                                              for c in json.loads((RUN / "colectare.json").read_text())
                                                              for a in c.get("http_attempts", [])
                                                              if "loto.ro" in a["requested_url"]})},
                "canonical_snapshot": {"snapshot": canon_ptr, "database_sha256": sha(canon)},
                "games_read": sorted(RULES), "game_649_read": False,
                "note": "Inventar, nu experiment de selecție. 5/40: extragerea are 6 numere, biletul 5.",
                "games": {}}
    for game, rule in RULES.items():
        recs, excluded = [], []
        for r in rows(frozen, game):
            rec, why = validate(game, r)
            if rec is None:
                excluded.append({"draw_key": r["draw_key"], "reason": why})
            else:
                recs.append(rec)
        keys = [x["draw_key"] for x in recs]
        assert len(keys) == len(set(keys)), "chei duplicate"
        canon_rows = {r["draw_key"]: r for r in rows(canon, game)}
        new_rows = {r["draw_key"]: r for r in rows(frozen, game)}
        common = sorted(set(canon_rows) & set(new_rows))
        diffs = [k for k in common if canon_rows[k] != new_rows[k]]
        path = OUT / f"extrageri_{game}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for rec in recs:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        path.chmod(0o444)
        manifest["games"][game] = {
            "name": rule["name"], "file": path.name, "sha256": sha(path), "records": len(recs),
            "excluded": excluded, "first_date": recs[0]["draw_date"], "last_date": recs[-1]["draw_date"],
            "draw_size": rule["r"], "number_range": [1, rule["n"]], "joker_range": [1, rule["joker"]] if rule["joker"] else None,
            "ticket": rule["ticket"], "source_disagreements": sum(x["has_source_disagreement"] for x in recs),
            "vs_canonical": {"canonical_records": len(canon_rows), "common_keys": len(common),
                             "rows_differing_on_common_keys": diffs,
                             "only_in_new": sorted(set(new_rows) - set(canon_rows)),
                             "only_in_canonical": sorted(set(canon_rows) - set(new_rows))}}
    (OUT / "MANIFEST_DATE.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    summary = {g: {k: v for k, v in m.items() if k in ("records", "first_date", "last_date", "source_disagreements")}
               | {"excluded": len(m["excluded"]), "differing": len(m["vs_canonical"]["rows_differing_on_common_keys"]),
                  "only_in_new": m["vs_canonical"]["only_in_new"],
                  "only_in_canonical": len(m["vs_canonical"]["only_in_canonical"])}
               for g, m in manifest["games"].items()}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
