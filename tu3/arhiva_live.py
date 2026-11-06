"""TU3 — arhiva LIVE pentru toate cele trei jocuri (6/49, 5/40, Joker), mereu la zi.

Rulează după fiecare execuție a `loto-actualizare.service` (drop-in systemd `ExecStopPost`, deci și când serviciul
eșuează la pasul de prognoză) sau manual. Nu descarcă nimic: colectorul existent descarcă oficial de pe loto.ro la
fiecare 30 de minute și validează o bază candidat completă. Acest script:

1. alege cea mai nouă rulare `loto_romania/data/automatizare/rulari/<run>/` a cărei bază `candidat.sqlite` are
   EXACT hash-ul validat din `decision.json` (`validation.database_sha256`);
2. refuză orice regres: fiecare extragere din snapshot-ul canonic (`CURRENT.json`) și din versiunea live precedentă
   trebuie să existe identic în baza nouă (altfel păstrează versiunea precedentă și iese cu cod 3);
3. validează (6/49: 6 distincte 1..49; 5/40: 6 distincte 1..40 — biletul are 5; Joker: 5 distincte 1..45 + Joker
   1..20), cu motive explicite de excludere;
4. scrie o versiune NOUĂ, imutabilă, `tu3/date/live/versiuni/<sha12>/` (JSONL × 3 + manifest + dovezile colectării)
   și mută atomic pointerul `tu3/date/live/CURRENT_LIVE.json`; dacă baza nu s-a schimbat, nu face nimic.

Nu atinge: baza/snapshot-urile colectorului (numai citire), protocolul prospectiv înghețat, fișierele de cercetare
sigilate (`predictie_numere/probe_date/extrageri_649.jsonl`), exportul înghețat `tu3/date/extrageri_*.jsonl`,
OGLINDA. Doar biblioteca standard (rulează cu /usr/bin/python3).
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DATA = REPO / "loto_romania" / "data"
RUNS = DATA / "automatizare" / "rulari"
LIVE = HERE / "date" / "live"
VERS = LIVE / "versiuni"
POINTER = LIVE / "CURRENT_LIVE.json"
GAMES = {"649": dict(n=49, r=6, joker=None, name="Loto 6/49", ticket=6),
         "540": dict(n=40, r=6, joker=None, name="Loto 5/40", ticket=5),
         "joker": dict(n=45, r=5, joker=20, name="Joker", ticket="5+1")}
COLS = ("draw_key, draw_date, draw_kind, n1, n2, n3, n4, n5, n6, joker, verification, source_count, "
        "has_source_disagreement")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def log(msg: str) -> None:
    print(f"[tu3-arhiva-live {now()}] {msg}", flush=True)


def read_rows(db: Path, game: str) -> list[dict]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = con.execute(f"SELECT {COLS} FROM draws WHERE game = ? ORDER BY draw_date, draw_key", (game,))
        names = [c[0] for c in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]
    finally:
        con.close()


def validate(game: str, r: dict, prov: dict) -> tuple[dict | None, str | None]:
    rule = GAMES[game]
    raw = [r[f"n{i}"] for i in range(1, 7) if r[f"n{i}"] is not None]
    try:
        order = [int(x) for x in raw]
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
        try:
            jk = int(jk)
        except (TypeError, ValueError):
            return None, "Joker lipsă"
        if not 1 <= jk <= rule["joker"]:
            return None, f"Joker în afara 1..{rule['joker']}"
    elif jk is not None:
        return None, "Joker prezent la un joc fără Joker"
    try:
        dt.date.fromisoformat(r["draw_date"])
    except (TypeError, ValueError):
        return None, "dată invalidă"
    return {"game": game, "draw_key": r["draw_key"], "draw_date": r["draw_date"], "draw_kind": r["draw_kind"],
            "numbers": sorted(order), "numbers_order_as_stored": order, "joker": jk,
            "verification": r["verification"], "source_count": r["source_count"],
            "has_source_disagreement": bool(r["has_source_disagreement"]), "provenance": prov}, None


def latest_validated_run() -> tuple[Path, dict] | None:
    for run in sorted((p for p in RUNS.iterdir() if p.is_dir()), reverse=True):
        db, dec = run / "candidat.sqlite", run / "decision.json"
        if not (db.is_file() and dec.is_file()):
            continue
        try:
            decision = json.loads(dec.read_text())
            want = decision["validation"]["database_sha256"]
        except (KeyError, TypeError, ValueError):
            continue
        if sha(db) == want:
            return run, decision
        log(f"rularea {run.name}: hash bază ≠ validare; ignorată")
    return None


def no_regression(new_db: Path, ref_db: Path, label: str) -> list[str]:
    problems = []
    for game in GAMES:
        new = {r["draw_key"]: r for r in read_rows(new_db, game)}
        for r in read_rows(ref_db, game):
            if r["draw_key"] not in new:
                problems.append(f"{label}: {r['draw_key']} lipsește în baza nouă")
            elif new[r["draw_key"]] != r:
                problems.append(f"{label}: {r['draw_key']} diferă în baza nouă")
    return problems


def no_regression_live(new_db: Path, prev_dir: Path) -> list[str]:
    problems = []
    for game in GAMES:
        new = {r["draw_key"]: r for r in read_rows(new_db, game)}
        path = prev_dir / f"extrageri_{game}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            old = json.loads(line)
            row = new.get(old["draw_key"])
            if row is None:
                problems.append(f"live precedent: {old['draw_key']} lipsește în baza nouă")
                continue
            rec, _ = validate(game, row, old["provenance"])
            if rec is None or any(rec[k] != old[k] for k in ("numbers", "joker", "draw_date", "numbers_order_as_stored")):
                problems.append(f"live precedent: {old['draw_key']} diferă în baza nouă")
    return problems


def publish(run: Path, decision: dict) -> int:
    db = run / "candidat.sqlite"
    db_sha = decision["validation"]["database_sha256"]
    current = json.loads(POINTER.read_text()) if POINTER.exists() else None
    if current and current["database_sha256"] == db_sha:
        log(f"la zi (baza {db_sha[:12]} din {current['run_id']}); nimic de făcut")
        return 0
    problems = []
    ptr = DATA / "CURRENT.json"
    if ptr.exists():
        snap = DATA / "snapshots" / json.loads(ptr.read_text())["snapshot"] / "loto_romania.sqlite"
        if snap.exists():
            problems += no_regression(db, snap, "snapshot canonic")
    if current:
        problems += no_regression_live(db, LIVE / current["version_dir"])
    if problems:
        log(f"REFUZ (regres, {len(problems)} probleme; versiunea precedentă rămâne): {problems[:5]}")
        return 3
    VERS.mkdir(parents=True, exist_ok=True)
    final = VERS / db_sha[:12]
    if final.exists():
        shutil.rmtree(final) if not (final / "MANIFEST_LIVE.json").exists() else None
    if not final.exists():
        tmp = Path(tempfile.mkdtemp(prefix=".tmp_", dir=VERS))
        prov = {"run_id": run.name, "database_sha256": db_sha}
        manifest = {"created_utc": now(), "run_id": run.name, "database_sha256": db_sha,
                    "archive_changed_by_collector": decision.get("archive_changed"),
                    "note": "Arhivă LIVE (produs). Cercetarea sigilată folosește exporturile înghețate, nu acest director.",
                    "games": {}}
        for game, rule in GAMES.items():
            recs, excluded = [], []
            for r in read_rows(db, game):
                rec, why = validate(game, r, prov)
                (recs.append(rec) if rec else excluded.append({"draw_key": r["draw_key"], "reason": why}))
            keys = [x["draw_key"] for x in recs]
            if len(keys) != len(set(keys)):
                shutil.rmtree(tmp)
                log(f"REFUZ: chei duplicate la {game}")
                return 4
            out = tmp / f"extrageri_{game}.jsonl"
            with open(out, "w", encoding="utf-8") as f:
                for rec in recs:
                    f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            manifest["games"][game] = {"name": rule["name"], "file": out.name, "sha256": sha(out),
                                       "records": len(recs), "excluded": excluded,
                                       "first_date": recs[0]["draw_date"] if recs else None,
                                       "last_date": recs[-1]["draw_date"] if recs else None,
                                       "last_key": recs[-1]["draw_key"] if recs else None,
                                       "draw_size": rule["r"], "ticket": rule["ticket"],
                                       "source_disagreements": sum(x["has_source_disagreement"] for x in recs)}
        for extra in ("decision.json", "colectare.json"):
            if (run / extra).exists():
                shutil.copy2(run / extra, tmp / extra)
        (tmp / "MANIFEST_LIVE.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        for p in tmp.iterdir():
            p.chmod(0o444)
        tmp.chmod(0o755)
        os.replace(tmp, final)
    manifest = json.loads((final / "MANIFEST_LIVE.json").read_text())
    pointer = {"updated_utc": now(), "run_id": run.name, "database_sha256": db_sha,
               "version_dir": str(final.relative_to(LIVE)),
               "manifest_sha256": sha(final / "MANIFEST_LIVE.json"),
               "games": {g: {k: m[k] for k in ("records", "last_date", "last_key", "sha256")}
                         for g, m in manifest["games"].items()},
               "previous": current["version_dir"] if current else None}
    fd, tmpname = tempfile.mkstemp(prefix=".CURRENT_LIVE.", dir=LIVE)
    os.chmod(tmpname, 0o644)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(pointer, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmpname, POINTER)
    with open(LIVE / "ISTORIC_LIVE.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({k: pointer[k] for k in ("updated_utc", "run_id", "database_sha256", "version_dir")}) + "\n")
    log("PUBLICAT " + pointer["version_dir"] + " — " +
        ", ".join(f"{g}: {v['records']} până la {v['last_date']}" for g, v in pointer["games"].items()))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--automat", action="store_true", help="apel din systemd (ExecStopPost); erorile nu blochează")
    ap.add_argument("--stare", action="store_true", help="afișează pointerul curent și iese")
    a = ap.parse_args(argv)
    LIVE.mkdir(parents=True, exist_ok=True)
    if a.stare:
        print(POINTER.read_text() if POINTER.exists() else "nicio versiune live publicată")
        return 0
    with open(LIVE / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            found = latest_validated_run()
            if found is None:
                log("nicio rulare validată disponibilă; nimic publicat")
                return 0 if a.automat else 1
            rc = publish(*found)
        except Exception as exc:  # în modul automat nu stricăm serviciul colectorului
            log(f"EROARE {type(exc).__name__}: {exc}")
            rc = 5
    return 0 if a.automat else rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
