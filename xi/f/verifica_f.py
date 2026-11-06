"""Verificatorul independent al fazei F (protocol xi/PROTOCOL_XI_F.md §6). NU importă registratorul sau judecătorul.

    PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B xi/f/verifica_f.py registru [--radacina DIR] [--data 2026-11-01]
    PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B xi/f/verifica_f.py decontare [--radacina DIR] [--db CALE]

Scrie VERIFICARE_F_<mod>_<UTC>.json în rădăcina registrului. positive_claims_allowed=false.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

QL = Path(__file__).resolve().parents[2]
REPO = QL.parents[1]
SNAP = REPO / "loto_romania/data/snapshots"
PROTO = QL / "xi/PROTOCOL_XI_F.md"
SIG = QL / "xi/SIGILIU_XI_F.json"
SIG_COD = QL / "xi/f/SIGILIU_COD_F.json"
SPEC = {"649": {"n": 49, "k": 6, "ball": False, "price": 8.0, "cats": ["I", "II", "III", "IV"]},
        "540": {"n": 40, "k": 5, "ball": False, "price": 5.0, "cats": ["I", "II", "III"]},
        "joker": {"n": 45, "k": 5, "ball": True, "price": 7.0, "cats": ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]}}
REQUIRED = {"seq", "prev_sha256", "tip", "tinta", "strategie", "sursa", "bilete", "nr_bilete", "pret_bilet", "miza",
            "utc_inregistrare", "cutoff_utc", "protocol_sha256", "cod_sha256", "sha256"}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_chain(p: Path) -> tuple[list, list]:
    errs, rows = [], []
    if not p.exists():
        return [], [f"{p.name} lipsește"]
    prev = "0" * 64
    for i, raw in enumerate(p.read_bytes().split(b"\n")[:-1]):
        o = json.loads(raw)
        rest = dict(o)
        s = rest.pop("sha256", None)
        if o.get("seq") != i:
            errs.append(f"seq {i}")
        if o.get("prev_sha256") != prev:
            errs.append(f"prev {i}")
        if s != sha(canonical(rest)) or raw != canonical(o):
            errs.append(f"sha/canonic {i}")
        prev = s
        rows.append(o)
    return rows, errs


def find_snapshot(want: str) -> Path | None:
    for d in sorted(SNAP.iterdir()):
        f = d / "loto_romania.sqlite"
        if f.exists() and sha(f.read_bytes()) == want:
            return f
    return None


def expected_ids(date: str) -> set:
    ids = {"C1_SG324Q", "C1_JS135Q"} | {f"RND_{g}_B{b}" for g in SPEC for b in (40, 100, 500)}
    if date == "2026-11-01":
        ids |= {f"C3_{g}_B{b}_mu{m}" for g in SPEC for b in (40, 100, 500) for m in (0, 1000)}
    return ids


def reproduce_rnd(rule: str, game: str, count: int) -> list:
    s = SPEC[game]
    gen = random.Random(int(sha(rule.encode("utf-8")), 16))
    res, have = [], set()
    while len(res) < count:
        t = sorted(gen.sample(range(1, s["n"] + 1), s["k"]))
        if s["ball"]:
            t.append(gen.randint(1, 20))
        if tuple(t) not in have:
            have.add(tuple(t))
            res.append(t)
    return res


def check_registry(root: Path, date: str, db_arg: str | None = None) -> list[dict]:
    out = []

    def ck(i, ok, det=None):
        out.append({"id": i, "ok": bool(ok), "det": det})

    proto_sha = sha(PROTO.read_bytes())
    sig = json.loads(SIG.read_text(encoding="utf-8"))
    ck("R0_protocol_sigilat", proto_sha == sig["protocol_sha256"] and PROTO.stat().st_mode & 0o777 == 0o444)
    p = root / "LANT_STRATEGII.jsonl"
    rows, errs = verify_chain(p)
    ck("R1_lant", not errs and rows, errs[:10])
    ck("R7_mod_0444", p.exists() and p.stat().st_mode & 0o777 == 0o444)
    cod = json.loads(SIG_COD.read_text(encoding="utf-8"))["cod"]["xi/f/inregistreaza.py"] if SIG_COD.exists() else None
    tgt = [r for r in rows if r.get("tip") == "INREGISTRARE" and r["tinta"]["data"] == date]
    ck("R2_campuri", all(REQUIRED <= set(r) for r in tgt), [r["seq"] for r in tgt if not REQUIRED <= set(r)])
    ck("R5_strategii", {r["strategie"] for r in tgt} == expected_ids(date) and len(tgt) == len(expected_ids(date)),
       sorted({r["strategie"] for r in tgt} ^ expected_ids(date)))
    ck("R8_protocol_cod", all(r["protocol_sha256"] == proto_sha and (cod is None or r["cod_sha256"] == cod)
                              for r in tgt), {"cod_sigilat": cod})
    cut = dt.datetime.combine(dt.date.fromisoformat(date), dt.time(16, 0), ZoneInfo("Europe/Bucharest")).astimezone(
        dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ck("R4_cutoff", all(r["cutoff_utc"] == cut and r["utc_inregistrare"] < cut for r in tgt), cut)
    bad6 = []
    for r in tgt:
        g = r["tinta"]["joc"]
        if r["nr_bilete"] != len(r["bilete"]) or r["pret_bilet"] != SPEC[g]["price"] or abs(
                r["miza"] - len(r["bilete"]) * SPEC[g]["price"]) > 1e-9:
            bad6.append(r["strategie"])
    ck("R6_miza", not bad6, bad6)
    bad3 = []
    c3_cache = {}
    for r in tgt:
        g, s = r["tinta"]["joc"], r["sursa"]
        if r["strategie"].startswith("C1_"):
            f = QL / s["fisier"]
            d = json.loads(f.read_bytes())
            ok = sha(f.read_bytes()) == s["sha256"] and d["tickets"] == r["bilete"] and d["game"] == g
        elif r["strategie"].startswith("C3_"):
            f = QL / s["fisier"]
            if f not in c3_cache:
                c3_cache[f] = (sha(f.read_bytes()), json.loads(f.read_bytes()))
            hs, d = c3_cache[f]
            inst = [i for i in d["instances"] if i["game"] == g and i["variant"] == "P" and i["B"] == s["B"]
                    and float(i["mu"]) == float(s["mu"])]
            ok = hs == s["sha256"] and len(inst) == 1 and inst[0]["tickets"] == r["bilete"]
        else:
            b = int(r["strategie"].split("_B")[1])
            rule = f"XI-F|RND|{date}|{g}|{b}|{proto_sha}"
            ok = s.get("regula_seed") == rule and reproduce_rnd(rule, g, r["nr_bilete"]) == r["bilete"]
        if not ok:
            bad3.append(r["strategie"])
    ck("R3_bilete_reproduse", not bad3, bad3)
    # extragerea absentă în baza folosită la înregistrare
    snaps = {r.get("baza_sha256_la_inregistrare") for r in tgt}
    absent = True
    det = {}
    for sh in snaps:
        f = (Path(db_arg) if db_arg and sha(Path(db_arg).read_bytes()) == sh else find_snapshot(sh)) if sh else None
        if f is None:
            absent, det[str(sh)] = False, "snapshot negăsit"
            continue
        con = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
        n = con.execute("SELECT COUNT(*) FROM draws WHERE draw_date=? AND draw_kind='regular'", (date,)).fetchone()[0]
        con.close()
        det[sh[:12]] = n
        absent = absent and n == 0
    ck("R9_extragere_absenta_la_inregistrare", absent, det)
    return out


def classify(game: str, t: list, drawn: list, jb) -> str | None:
    s = SPEC[game]
    hit = sum(1 for x in t[:s["k"]] if x in drawn)
    if game == "649":
        return ["IV", "III", "II", "I"][hit - 3] if hit >= 3 else None
    if game == "540":
        if hit == 5:
            return "I" if all(x in drawn[:5] for x in t) else "II"
        return "III" if hit == 4 else None
    j = t[5] == jb
    if j:
        return {5: "I", 4: "III", 3: "V", 2: "VII", 1: "VIII"}.get(hit)
    return {5: "II", 4: "IV", 3: "VI"}.get(hit)


def check_settlements(root: Path, db_arg: str | None) -> list[dict]:
    out = []

    def ck(i, ok, det=None):
        out.append({"id": i, "ok": bool(ok), "det": det})

    reg, e1 = verify_chain(root / "LANT_STRATEGII.jsonl")
    dec, e2 = verify_chain(root / "DECONTARI_STRATEGII.jsonl")
    ck("D1_lanturi", not e1 and not e2 and dec, (e1 + e2)[:10])
    by_seq = {r["seq"]: r for r in reg}
    refs = [d["ref_seq"] for d in dec]
    ck("D2_referinte", len(refs) == len(set(refs)) and all(
        d["ref_seq"] in by_seq and by_seq[d["ref_seq"]]["sha256"] == d["ref_sha256"] for d in dec))
    bad = []
    for d in dec:
        if d["status"] != "DECONTAT":
            continue
        r = by_seq[d["ref_seq"]]
        g, date = r["tinta"]["joc"], r["tinta"]["data"]
        f = Path(db_arg) if db_arg else find_snapshot(d["baza_sha256"])
        if f is None or sha(f.read_bytes()) != d["baza_sha256"]:
            bad.append((d["seq"], "baza"))
            continue
        con = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
        row = con.execute("SELECT n1,n2,n3,n4,n5,n6,joker,selected_observation FROM draws WHERE game=? AND "
                          "draw_date=? AND draw_kind='regular'", (g, date)).fetchone()
        pr = {c: (st, w, p, cv) for c, st, w, p, cv in con.execute(
            "SELECT category,status,winning_variants,payout_per_win,carryover FROM prizes WHERE observation_id=?",
            (row[7],))}
        con.close()
        drawn = [x for x in row[:6] if x is not None]
        cnt = {c: 0 for c in SPEC[g]["cats"]}
        for t in r["bilete"]:
            c = classify(g, t, drawn, row[6])
            if c:
                cnt[c] += 1
        total = 0.0
        for c, m in cnt.items():
            if not m:
                continue
            st, w, p, cv = pr[c]
            fl = lambda x: float(str(x).replace(",", "")) if x is not None else None  # noqa: E731
            if g == "649" and c == "IV":
                total += m * fl(p)
            elif st == "paid":
                total += m * fl(p) * int(w) / (int(w) + m)
            else:
                total += fl(cv)
        res = d["rezultat"]
        if (res["bilete_pe_categorie"] != cnt or abs(res["plata"] - total) > 1e-9 * max(1.0, total)
                or abs(res["net"] - (total - r["miza"])) > 1e-9 * max(1.0, abs(total - r["miza"]))
                or res["numere_extrase"] != drawn):
            bad.append((d["seq"], r["strategie"], cnt, total))
    ck("D3_recalcul_independent", not bad, bad[:10])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mod", choices=["registru", "decontare"])
    ap.add_argument("--radacina")
    ap.add_argument("--data", default="2026-11-01")
    ap.add_argument("--db")
    a = ap.parse_args(argv)
    root = Path(a.radacina) if a.radacina else QL / "xi/rezultate/F"
    checks = check_registry(root, a.data, a.db) if a.mod == "registru" else check_settlements(root, a.db)
    n = sum(c["ok"] for c in checks)
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rep = {"utc": utc, "mod": a.mod, "data": a.data, "verifier_sha256": sha(Path(__file__).read_bytes()),
           "n_checks": len(checks), "n_pass": n, "VERDICT": "PASS" if n == len(checks) else "FAIL",
           "poarta": "G5a" if a.mod == "registru" else "G5", "checks": checks, "positive_claims_allowed": False}
    f = root / f"VERIFICARE_F_{a.mod}_{utc}.json"
    f.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["id"] + ("" if c["ok"] else f"  {json.dumps(c['det'], ensure_ascii=False)[:500]}"))
    print(f"VERIFICARE_F {a.mod} {rep['VERDICT']} {n}/{len(checks)} {f} {sha(f.read_bytes())}")
    return 0 if rep["VERDICT"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
