"""Judecătorul F (protocol xi/PROTOCOL_XI_F.md §5): decontează pe hârtie înregistrările din LANT_STRATEGII.jsonl.

Nu înregistrează și nu modifică registrul (îl citește numai). Cod separat de registrator (fără module comune).
Date: snapshot-ul din loto_romania/data/CURRENT.json (sqlite, mode=ro). Ieșire append-only, cu lanț de hash-uri:
xi/rezultate/F/DECONTARI_STRATEGII.jsonl (0444 între scrieri).

    PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B xi/f/deconteaza.py
    (teste: --radacina DIR --acum 2026-11-02T10:00:00Z --db CALE.sqlite)

positive_claims_allowed=false. Calcul clasic.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

QL = Path(__file__).resolve().parents[2]
REPO = QL.parents[1]
PROTO = QL / "xi/PROTOCOL_XI_F.md"
PROTO_SHA = "ba74568f40fa62303bef59bbd7c23d46b527ec53e00297c59f71670a0b7d3220"
TZ = ZoneInfo("Europe/Bucharest")
DRAW_T = dt.time(18, 30)
GRACE = dt.timedelta(days=14)
CATEGORIES = {"649": ["I", "II", "III", "IV"], "540": ["I", "II", "III"],
              "joker": ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]}
FIXED = {("649", "IV")}
NULL = "0" * 64


def h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def cj(o: dict) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def chain(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows, prev = [], NULL
    for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines()):
        o = json.loads(ln)
        core = {k: v for k, v in o.items() if k != "sha256"}
        ok = o.get("seq") == i and o.get("prev_sha256") == prev and o.get("sha256") == h(cj(core).encode("utf-8"))
        if not ok or ln != cj(o):
            raise RuntimeError(f"lanț invalid în {path.name} la linia {i}")
        prev = o["sha256"]
        rows.append(o)
    return rows


def category(game: str, ticket: list, nums: list, jk: int | None) -> str | None:
    """Cea mai înaltă categorie a biletului (protocol §5); nums în ordinea extragerii."""
    if game == "649":
        return {6: "I", 5: "II", 4: "III", 3: "IV"}.get(len(set(ticket) & set(nums)))
    if game == "540":
        m = len(set(ticket) & set(nums))
        if m == 5:
            return "I" if set(ticket) == set(nums[:5]) else "II"
        return "III" if m == 4 else None
    m, ball = len(set(ticket[:5]) & set(nums)), ticket[5] == jk
    table = {(5, True): "I", (5, False): "II", (4, True): "III", (4, False): "IV", (3, True): "V", (3, False): "VI",
             (2, True): "VII", (1, True): "VIII"}
    return table.get((m, ball))


def payout(game: str, cat: str, m: int, prize: dict) -> float | None:
    status, w, ppw, carry = prize["status"], prize["w"], prize["ppw"], prize["carry"]
    if (game, cat) in FIXED:
        return None if ppw is None else m * ppw
    if status == "paid":
        if ppw is None or w is None:
            return None
        return m * ppw * w / (w + m)
    if status == "rollover":
        return carry
    return None


def num(x):
    if x is None:
        return None
    try:
        return float(str(x).replace(",", "").strip())
    except ValueError:
        return None


def fetch(db: Path, game: str, date: str) -> dict | None:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT n1,n2,n3,n4,n5,n6,joker,selected_observation,has_source_disagreement,draw_key "
                           "FROM draws WHERE game=? AND draw_date=? AND draw_kind='regular'", (game, date)).fetchall()
        if len(rows) != 1:
            return None
        r = rows[0]
        prizes = {c: {"status": s, "w": (None if w is None else int(w)), "ppw": num(p), "carry": num(cv)}
                  for c, s, w, p, cv in con.execute(
                      "SELECT category,status,winning_variants,payout_per_win,carryover FROM prizes "
                      "WHERE observation_id=?", (r[7],))}
        return {"nums": [x for x in r[:6] if x is not None], "joker": r[6], "disagreement": int(r[8]),
                "draw_key": r[9], "prizes": prizes}
    finally:
        con.close()


def settle_entry(ent: dict, rec: dict) -> dict | None:
    game = ent["tinta"]["joc"]
    if rec["disagreement"] or any(c not in rec["prizes"] or rec["prizes"][c]["status"] not in ("paid", "rollover")
                                  for c in CATEGORIES[game]):
        return None
    counts = {c: 0 for c in CATEGORIES[game]}
    for t in ent["bilete"]:
        c = category(game, t, rec["nums"], rec["joker"])
        if c:
            counts[c] += 1
    plata = 0.0
    per_cat = {}
    for c, m in counts.items():
        if m:
            v = payout(game, c, m, rec["prizes"][c])
            if v is None:
                return None
            per_cat[c] = v
            plata += v
    return {"numere_extrase": rec["nums"], "joker_extras": rec["joker"], "draw_key": rec["draw_key"],
            "bilete_pe_categorie": counts, "plata_pe_categorie": per_cat, "plata": plata,
            "miza": ent["miza"], "net": plata - ent["miza"]}


def database_path(db_arg: str | None) -> Path:
    if db_arg:
        return Path(db_arg)
    cur = json.loads((REPO / "loto_romania/data/CURRENT.json").read_text(encoding="utf-8"))
    return REPO / "loto_romania/data/snapshots" / cur["snapshot"] / "loto_romania.sqlite"


def judge(root: Path, now: dt.datetime, db: Path) -> dict:
    if h(PROTO.read_bytes()) != PROTO_SHA:
        raise RuntimeError("protocolul XI-F diferă de sigiliu")
    reg = chain(root / "LANT_STRATEGII.jsonl")
    out_path = root / "DECONTARI_STRATEGII.jsonl"
    decs = chain(out_path)
    settled = {d["ref_seq"] for d in decs}
    prev = decs[-1]["sha256"] if decs else NULL
    db_sha = h(db.read_bytes())
    code_sha = h(Path(__file__).read_bytes())
    utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    new, pending = [], []
    cache: dict = {}
    for ent in reg:
        if ent["tip"] != "INREGISTRARE" or ent["seq"] in settled:
            continue
        date, game = ent["tinta"]["data"], ent["tinta"]["joc"]
        draw_utc = dt.datetime.combine(dt.date.fromisoformat(date), DRAW_T, TZ).astimezone(dt.timezone.utc)
        if now <= draw_utc:
            pending.append((ent["seq"], "extragerea nu a avut loc"))
            continue
        key = (game, date)
        if key not in cache:
            cache[key] = fetch(db, game, date)
        rec = cache[key]
        res = settle_entry(ent, rec) if rec else None
        if res is None:
            if now > draw_utc + GRACE:
                res, status = {"motiv": "fără date valide după 14 zile"}, "VOID"
            else:
                pending.append((ent["seq"], "date/plăți incomplete sau dezacord între surse"))
                continue
        else:
            status = "DECONTAT"
        o = {"seq": len(decs) + len(new), "prev_sha256": prev, "tip": "DECONTARE", "status": status,
             "ref_seq": ent["seq"], "ref_sha256": ent["sha256"], "strategie": ent["strategie"], "tinta": ent["tinta"],
             "rezultat": res, "baza_sha256": db_sha, "utc_decontare": utc, "protocol_sha256": PROTO_SHA,
             "cod_sha256": code_sha, "positive_claims_allowed": False}
        core = dict(o)
        o["sha256"] = h(cj(core).encode("utf-8"))
        prev = o["sha256"]
        new.append(cj(o))
    if new:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            os.chmod(out_path, 0o644)
        try:
            with open(out_path, "a", encoding="utf-8") as f:
                for ln in new:
                    f.write(ln + "\n")
                f.flush()
                os.fsync(f.fileno())
        finally:
            os.chmod(out_path, 0o444)
        chain(out_path)
    return {"decontari_noi": len(new), "in_asteptare": len(pending), "motive": sorted({m for _, m in pending}),
            "cap_decontari_sha256": prev, "utc": utc}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--radacina")
    ap.add_argument("--acum")
    ap.add_argument("--db")
    a = ap.parse_args(argv)
    test = a.radacina is not None
    if (a.acum or a.db) and not test:
        print("REFUZ: --acum/--db numai cu --radacina (mod test)")
        return 3
    root = Path(a.radacina) if test else QL / "xi/rezultate/F"
    now = dt.datetime.fromisoformat(a.acum.replace("Z", "+00:00")) if a.acum else dt.datetime.now(dt.timezone.utc)
    r = judge(root, now, database_path(a.db))
    print("DECONTARE " + json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
