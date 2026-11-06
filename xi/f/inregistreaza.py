"""Registratorul F (protocol xi/PROTOCOL_XI_F.md §2–§4): înregistrează pe hârtie biletele strategiilor, ÎNAINTE de cutoff.

Nu decontează (rolul judecătorului xi/f/deconteaza.py) și nu afișează bilete nicăieri. Registrul este append-only, cu
lanț de hash-uri: xi/rezultate/F/LANT_STRATEGII.jsonl (0444 între scrieri).

    PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B xi/f/inregistreaza.py --data 2026-11-01
    (teste: --radacina DIR --acum 2026-11-01T10:00:00Z --db CALE.sqlite)

positive_claims_allowed=false. Calcul clasic. Nu este o predicție și nici o recomandare.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

QL = Path(__file__).resolve().parents[2]
REPO = QL.parents[1]
PROTO = QL / "xi/PROTOCOL_XI_F.md"
PROTO_SHA = "ba74568f40fa62303bef59bbd7c23d46b527ec53e00297c59f71670a0b7d3220"
TZ = ZoneInfo("Europe/Bucharest")
CUTOFF_T = dt.time(16, 0)
DRAW_WEEKDAYS = (3, 6)  # joi, duminică
GAMES = {"649": (49, 6, False), "540": (40, 5, False), "joker": (45, 5, True)}
PRICE = {"649": 8.0, "540": 5.0, "joker": 7.0}
DESIGNS = {"C1_SG324Q": ("649", "xi/rezultate/C1/designuri/SG324Q.json",
                         "b830503075cb52209497352a40bbd21b4680efcd41a2e27a8454e8aa4f4f86c5"),
           "C1_JS135Q": ("joker", "xi/rezultate/C1/designuri/JS135Q.json",
                         "add35bb780f3983a73623010b6f22d353cb731d521621ac8c13c73cd8feb96fd")}
C1_EVAL = ("xi/rezultate/C1/C1_EVALUARE.json", "5eb6440188d16788e7e7410c44a21512f5830f324324822672eabc5d6803b2e8")
C3_RES = ("xi/rezultate/C3/C3_REZULTATE.json", "01331654bb23b56295e5c23c2b0cf8a72f2ec84f755df2fcefbfcede23c9f9ca")
C3_DATE = "2026-11-01"
BUDGETS = (40, 100, 500)
MUS = (0.0, 1000.0)
ZERO = "0" * 64


class Refuz(Exception):
    pass


def sha_b(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canon(o: dict) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def seal_line(o: dict) -> str:
    body = {k: v for k, v in o.items() if k != "sha256"}
    return canon(dict(body, sha256=sha_b(canon(body).encode("utf-8"))))


def read_chain(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out, prev = [], ZERO
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        o = json.loads(line)
        body = {k: v for k, v in o.items() if k != "sha256"}
        if o.get("seq") != i or o.get("prev_sha256") != prev or o.get("sha256") != sha_b(canon(body).encode("utf-8")):
            raise Refuz(f"lanț invalid la linia {i}")
        if line != canon(o):
            raise Refuz(f"linie necanonică {i}")
        prev = o["sha256"]
        out.append(o)
    return out


def append_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        os.chmod(path, 0o644)
    try:
        with open(path, "a", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln + "\n")
            f.flush()
            os.fsync(f.fileno())
    finally:
        os.chmod(path, 0o444)


def load_src(rel: str, want: str):
    b = (QL / rel).read_bytes()
    if sha_b(b) != want:
        raise Refuz(f"sha diferit pentru {rel}")
    return json.loads(b.decode("utf-8"))


def valid_ticket(game: str, t: list) -> bool:
    n, k, ball = GAMES[game]
    main = t[:k]
    if len(t) != k + (1 if ball else 0) or main != sorted(main) or len(set(main)) != k:
        return False
    if not all(isinstance(x, int) and not isinstance(x, bool) and 1 <= x <= n for x in main):
        return False
    return (not ball) or (isinstance(t[k], int) and not isinstance(t[k], bool) and 1 <= t[k] <= 20)


def rnd_tickets(date: str, game: str, B: int, K: int) -> tuple[list, str]:
    n, k, ball = GAMES[game]
    rule = f"XI-F|RND|{date}|{game}|{B}|{PROTO_SHA}"
    rnd = random.Random(int(sha_b(rule.encode("utf-8")), 16))
    seen, out = set(), []
    while len(out) < K:
        t = sorted(rnd.sample(range(1, n + 1), k))
        if ball:
            t.append(rnd.randint(1, 20))
        if tuple(t) not in seen:
            seen.add(tuple(t))
            out.append(t)
    return out, rule


def strategies(date: str) -> list[dict]:
    out = []
    ev = load_src(*C1_EVAL)
    for sid, (game, rel, want) in DESIGNS.items():
        d = load_src(rel, want)
        if ev["designs"][game]["file_sha256"] != want or d["n_tickets"] != len(d["tickets"]):
            raise Refuz(f"designul {sid} nu corespunde C1_EVALUARE")
        out.append(dict(strategie=sid, joc=game, bilete=d["tickets"], sursa={"fisier": rel, "sha256": want}))
    c3 = load_src(*C3_RES) if date == C3_DATE else None
    for game in GAMES:
        for B in BUDGETS:
            K = None
            for mu in MUS:
                hit = [i for i in (c3 or load_src(*C3_RES))["instances"]
                       if (i["game"], i["variant"], i["B"], i["mu"]) == (game, "P", B, mu)]
                if len(hit) != 1:
                    raise Refuz(f"instanța C3 {game}/{B}/{mu} nu este unică")
                K = hit[0]["K"]
                if c3 is not None:
                    out.append(dict(strategie=f"C3_{game}_B{B}_mu{int(mu)}", joc=game, bilete=hit[0]["tickets"],
                                    sursa={"fisier": C3_RES[0], "sha256": C3_RES[1], "varianta": "P", "B": B,
                                           "mu": mu}))
            t, rule = rnd_tickets(date, game, B, K)
            out.append(dict(strategie=f"RND_{game}_B{B}", joc=game, bilete=t, sursa={"regula_seed": rule}))
    for s in out:
        if not all(valid_ticket(s["joc"], t) for t in s["bilete"]) or len({tuple(t) for t in s["bilete"]}) != len(
                s["bilete"]):
            raise Refuz(f"bilete invalide în {s['strategie']}")
    return out


def database_path(db_arg: str | None) -> Path:
    if db_arg:
        return Path(db_arg)
    cur = json.loads((REPO / "loto_romania/data/CURRENT.json").read_text(encoding="utf-8"))
    return REPO / "loto_romania/data/snapshots" / cur["snapshot"] / "loto_romania.sqlite"


def draw_exists(db: Path, game: str, date: str) -> bool:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute("SELECT COUNT(*) FROM draws WHERE game=? AND draw_date=? AND draw_kind='regular'",
                           (game, date)).fetchone()[0] > 0
    finally:
        con.close()


def register(root: Path, date: str, now: dt.datetime, db: Path) -> dict:
    if sha_b(PROTO.read_bytes()) != PROTO_SHA:
        raise Refuz("protocolul XI-F diferă de sigiliu")
    d = dt.date.fromisoformat(date)
    if d.weekday() not in DRAW_WEEKDAYS:
        raise Refuz(f"{date} nu este zi de extragere (joi/duminică)")
    cutoff = dt.datetime.combine(d, CUTOFF_T, TZ).astimezone(dt.timezone.utc)
    if not now < cutoff:
        raise Refuz(f"după cutoff ({cutoff.isoformat()})")
    for g in GAMES:
        if draw_exists(db, g, date):
            raise Refuz(f"extragerea {g} {date} există deja în baza")
    ledger = root / "LANT_STRATEGII.jsonl"
    chain = read_chain(ledger)
    done = {(o["tinta"]["data"], o["strategie"]) for o in chain if o["tip"] == "INREGISTRARE"}
    strat = strategies(date)
    dup = [s["strategie"] for s in strat if (date, s["strategie"]) in done]
    if dup:
        raise Refuz(f"deja înregistrate: {dup}")
    code_sha = sha_b(Path(__file__).read_bytes())
    prev = chain[-1]["sha256"] if chain else ZERO
    seq0 = len(chain)
    utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = []
    for i, s in enumerate(strat):
        o = {"seq": seq0 + i, "prev_sha256": prev, "tip": "INREGISTRARE", "tinta": {"data": date, "joc": s["joc"]},
             "strategie": s["strategie"], "sursa": s["sursa"], "bilete": s["bilete"], "nr_bilete": len(s["bilete"]),
             "pret_bilet": PRICE[s["joc"]], "miza": len(s["bilete"]) * PRICE[s["joc"]], "utc_inregistrare": utc,
             "cutoff_utc": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"), "protocol_sha256": PROTO_SHA, "cod_sha256": code_sha,
             "baza_sha256_la_inregistrare": sha_b(db.read_bytes()), "extragere_absenta_la_inregistrare": True,
             "positive_claims_allowed": False}
        ln = seal_line(o)
        prev = json.loads(ln)["sha256"]
        lines.append(ln)
    append_lines(ledger, lines)
    read_chain(ledger)
    return {"inregistrate": len(lines), "cap_lant_sha256": prev, "seq": [seq0, seq0 + len(lines) - 1],
            "miza_totala": sum(json.loads(x)["miza"] for x in lines), "utc": utc,
            "cutoff_utc": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--radacina")
    ap.add_argument("--acum")
    ap.add_argument("--db")
    a = ap.parse_args(argv)
    test = a.radacina is not None
    if (a.acum or a.db) and not test:
        print("REFUZ: --acum/--db numai cu --radacina (mod test)")
        return 3
    root = Path(a.radacina) if test else QL / "xi/rezultate/F"
    now = (dt.datetime.fromisoformat(a.acum.replace("Z", "+00:00")) if a.acum
           else dt.datetime.now(dt.timezone.utc))
    try:
        r = register(root, a.data, now, database_path(a.db))
    except Refuz as e:
        print(f"REFUZ: {e}")
        return 3
    print("INREGISTRARE " + json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
