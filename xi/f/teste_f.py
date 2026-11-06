"""Calificarea fazei F (protocol xi/PROTOCOL_XI_F.md §6), numai în directoare temporare (registrul real neatins).

T1 categoriile pe extrageri sintetice (judecător + verificator); T2 regula de plată; T3 refuzurile registratorului
(după cutoff, extragere existentă, zi fără extragere, dublură) + înregistrare de probă 2026-11-01 verificată (R*);
T4 alterarea lanțului detectată de toate cele trei cititoare; T5 reluare istorică pe 2026-10-29 (bază temporară fără
acea extragere la înregistrare, baza reală la decontare): designurile C1 câștigă ceva, plata ≥ premiul minim C1,
verificatorul independent dă același rezultat (D*).
Rulare: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B xi/f/teste_f.py
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
QL = HERE.parents[1]
PY = [sys.executable, "-B"]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(script, *args):
    r = subprocess.run(PY + [str(HERE / script), *args], capture_output=True, text=True,
                       env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    I, J, V = load("inregistreaza"), load("deconteaza"), load("verifica_f")
    res = {}
    # T1
    cases = [("649", [1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6], None, "I"), ("649", [1, 2, 3, 4, 5, 7], [6, 5, 4, 3, 2, 1], None, "II"),
             ("649", [1, 2, 3, 4, 8, 9], [1, 2, 3, 4, 5, 6], None, "III"), ("649", [1, 2, 3, 7, 8, 9], [1, 2, 3, 4, 5, 6], None, "IV"),
             ("649", [1, 2, 7, 8, 9, 10], [1, 2, 3, 4, 5, 6], None, None),
             ("540", [1, 2, 3, 4, 5], [5, 4, 3, 2, 1, 6], None, "I"), ("540", [1, 2, 3, 4, 6], [1, 2, 3, 4, 5, 6], None, "II"),
             ("540", [1, 2, 3, 4, 9], [1, 2, 3, 4, 5, 6], None, "III"), ("540", [1, 2, 3, 8, 9], [1, 2, 3, 4, 5, 6], None, None),
             ("joker", [1, 2, 3, 4, 5, 7], [1, 2, 3, 4, 5], 7, "I"), ("joker", [1, 2, 3, 4, 5, 8], [1, 2, 3, 4, 5], 7, "II"),
             ("joker", [1, 2, 3, 4, 9, 7], [1, 2, 3, 4, 5], 7, "III"), ("joker", [1, 2, 3, 4, 9, 8], [1, 2, 3, 4, 5], 7, "IV"),
             ("joker", [1, 2, 3, 9, 10, 7], [1, 2, 3, 4, 5], 7, "V"), ("joker", [1, 2, 3, 9, 10, 8], [1, 2, 3, 4, 5], 7, "VI"),
             ("joker", [1, 2, 9, 10, 11, 7], [1, 2, 3, 4, 5], 7, "VII"), ("joker", [1, 9, 10, 11, 12, 7], [1, 2, 3, 4, 5], 7, "VIII"),
             ("joker", [1, 2, 9, 10, 11, 8], [1, 2, 3, 4, 5], 7, None), ("joker", [9, 10, 11, 12, 13, 7], [1, 2, 3, 4, 5], 7, None)]
    bad = [(g, t, d, e, J.category(g, t, d, jb), V.classify(g, t, d, jb)) for g, t, d, jb, e in cases
           if not (J.category(g, t, d, jb) == V.classify(g, t, d, jb) == e)]
    res["T1_categorii"] = (not bad, bad)
    # T2
    P = lambda s, w, p, c: {"status": s, "w": w, "ppw": p, "carry": c}  # noqa: E731
    t2 = [J.payout("649", "IV", 2, P("paid", 5000, 50.0, None)) == 100.0,
          abs(J.payout("649", "III", 1, P("paid", 10, 1000.0, None)) - 1000.0 * 10 / 11) < 1e-12,
          abs(J.payout("649", "III", 2, P("paid", 10, 1000.0, None)) - 2000.0 * 10 / 12) < 1e-12,
          J.payout("joker", "I", 1, P("rollover", 0, None, 5000.0)) == 5000.0,
          J.payout("joker", "III", 1, P("paid", None, 10.0, None)) is None,
          J.payout("joker", "III", 1, P("paid", 3, None, None)) is None]
    res["T2_plata"] = (all(t2), t2)
    with tempfile.TemporaryDirectory(prefix="ql649_f_") as td:
        T = Path(td)
        # T3
        r1 = run("inregistreaza.py", "--data", "2026-11-01", "--radacina", str(T / "a"), "--acum", "2026-11-01T14:00:00Z")
        r2 = run("inregistreaza.py", "--data", "2026-10-29", "--radacina", str(T / "a"), "--acum", "2026-10-29T10:00:00Z")
        r3 = run("inregistreaza.py", "--data", "2026-11-02", "--radacina", str(T / "a"), "--acum", "2026-11-01T10:00:00Z")
        r4 = run("inregistreaza.py", "--data", "2026-11-01", "--radacina", str(T / "a"), "--acum", "2026-11-01T10:00:00Z")
        r5 = run("inregistreaza.py", "--data", "2026-11-01", "--radacina", str(T / "a"), "--acum", "2026-11-01T11:00:00Z")
        rv = run("verifica_f.py", "registru", "--radacina", str(T / "a"), "--data", "2026-11-01")
        ok3 = (r1[0] == 3 and "după cutoff" in r1[1] and r2[0] == 3 and "există deja" in r2[1] and r3[0] == 3
               and r4[0] == 0 and '"inregistrate": 29' in r4[1] and r5[0] == 3 and "deja înregistrate" in r5[1]
               and rv[0] == 0)
        res["T3_refuzuri_si_proba"] = (ok3, [x[1][-300:] for x in (r1, r2, r3, r4, r5, rv)])
        # T4
        b = (T / "a/LANT_STRATEGII.jsonl").read_bytes()
        (T / "b").mkdir()
        alt = b.replace(b'"bilete":[[', b'"bilete":[[9', 1) if b'"bilete":[[1,' in b else b[:-2] + b"0\n"
        (T / "b/LANT_STRATEGII.jsonl").write_bytes(alt)
        det = []
        try:
            I.read_chain(T / "b/LANT_STRATEGII.jsonl")
        except I.Refuz:
            det.append("I")
        try:
            J.chain(T / "b/LANT_STRATEGII.jsonl")
        except RuntimeError:
            det.append("J")
        if V.verify_chain(T / "b/LANT_STRATEGII.jsonl")[1]:
            det.append("V")
        res["T4_alterare"] = (det == ["I", "J", "V"] and alt != b, det)
        # T5
        real = I.database_path(None)
        tmpdb = T / "fara_1029.sqlite"
        shutil.copy(real, tmpdb)
        tmpdb.chmod(0o644)
        con = sqlite3.connect(tmpdb)
        con.execute("DELETE FROM draws WHERE draw_date='2026-10-29'")
        con.commit()
        con.close()
        q1 = run("inregistreaza.py", "--data", "2026-10-29", "--radacina", str(T / "c"), "--acum", "2026-10-29T10:00:00Z",
                 "--db", str(tmpdb))
        q2 = run("deconteaza.py", "--radacina", str(T / "c"), "--acum", "2026-10-30T12:00:00Z", "--db", str(real))
        q3 = run("verifica_f.py", "decontare", "--radacina", str(T / "c"), "--db", str(real))
        decs = [json.loads(x) for x in (T / "c/DECONTARI_STRATEGII.jsonl").read_text().splitlines()] \
            if (T / "c/DECONTARI_STRATEGII.jsonl").exists() else []
        ev = json.loads((QL / "xi/rezultate/C1/C1_EVALUARE.json").read_text())["designs"]
        c1 = {d["strategie"]: d["rezultat"] for d in decs if d["strategie"].startswith("C1_")}
        ok5 = (q1[0] == 0 and '"inregistrate": 11' in q1[1] and q2[0] == 0 and len(decs) == 11
               and all(d["status"] == "DECONTAT" for d in decs) and q3[0] == 0
               and c1.get("C1_SG324Q", {}).get("plata", -1) >= ev["649"]["min_prize_per_date"] - 1e-9
               and c1.get("C1_JS135Q", {}).get("plata", -1) >= ev["joker"]["min_prize_per_date"] - 1e-9
               and all(sum(v["bilete_pe_categorie"].values()) >= 1 for v in c1.values()))
        res["T5_reluare_istorica"] = (ok5, {"q": [x[1][-300:] for x in (q1, q2, q3)],
                                            "c1": {k: (v["plata"], v["bilete_pe_categorie"]) for k, v in c1.items()}})
    ok = all(v[0] for v in res.values())
    for k, v in res.items():
        print(("PASS " if v[0] else "FAIL ") + k + ("" if v[0] else f"  {v[1]}"))
    if res["T5_reluare_istorica"][0]:
        print("T5 (descriptiv) C1 pe 2026-10-29:", json.dumps(res["T5_reluare_istorica"][1]["c1"], ensure_ascii=False))
    print("TESTE_F", "PASS" if ok else "FAIL", f"{sum(v[0] for v in res.values())}/{len(res)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
