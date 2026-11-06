"""QL649 TU4-S24 (tu4/PROTOCOL_QUANTUM_S24.md §2): raportul de decontare FĂRĂ reglaje, strict read-only.

Decontarea o face numai judecătorul sigilat (tu4/judecator.py, TU4-JU). Acest script:
  1. hash-uiește arborele tribunalului înainte și după (sub flock PARTAJAT pe .lock, deschis read-only);
  2. verifică lanțul DECONTARI.jsonl (i consecutiv, prev_line_sha256, sha256 al fișierului de decontare);
  3. copiază VERBATIM câmpurile documentelor judecătorului pentru ținta cerută (nu recalculează, nu ajustează);
  4. compară pragurile cu constantele sigilate (ln 600, ln 20, -10, M=6) și verifică emisia în LANT.jsonl;
  5. scrie DECONTARE_<data>_<UTC>.json + .md în --out.
Verdicte: DECONTARE_COMPLETA / DECONTARE_PARTIALA / DECONTARE_PENDING / DECONTARE_FAIL. PENDING nu devine PASS.
positive_claims_allowed=false: decontarea e o înregistrare de test științific, nu sfat de joc.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

QL = Path("${QL649_ROOT:-.}")
GAMES = ("649", "540", "joker")
MODELS = ("H1", "H3")
THRESHOLDS = {"explore_ln": math.log(600.0), "confirm_ln": math.log(20.0), "retire_ln": -10.0, "M": 6}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tree_hash(trib: Path) -> tuple[str, int]:
    h, n = hashlib.sha256(), 0
    for f in sorted(trib.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(trib)).encode() + b"\0" + f.read_bytes() + b"\0")
            n += 1
    return h.hexdigest(), n


def ju_seal_sha(judecator: Path) -> str:
    m = re.search(r'^JU_SEAL_SHA = "([0-9a-f]{64})"$', judecator.read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit("JU_SEAL_SHA lipsește din judecator.py")
    return m.group(1)


def shared_lock(trib: Path, timeout: float = 120.0):
    lf = trib / ".lock"
    if not lf.exists():
        return None
    fh = open(lf, "rb")
    t0 = time.monotonic()
    while True:
        try:
            fcntl.flock(fh, fcntl.LOCK_SH | fcntl.LOCK_NB)
            return fh
        except BlockingIOError:
            if time.monotonic() - t0 > timeout:
                raise SystemExit("tribunalul e ocupat (flock) de peste 120 s; reîncearcă")
            time.sleep(0.5)


def analyze(trib: Path, target: str, seal: str) -> dict:
    checks, games = [], {}

    def c(name, ok, detail=None):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    lant = [json.loads(x) for x in (trib / "LANT.jsonl").read_text(encoding="utf-8").splitlines()] \
        if (trib / "LANT.jsonl").exists() else []
    lant_sha = {r.get("sha256") for r in lant}
    p = trib / "DECONTARI.jsonl"
    raw = p.read_bytes().splitlines() if p.exists() else []
    prev = seal
    for k, b in enumerate(raw):
        r = json.loads(b)
        c(f"lant_i_{k}", r.get("i") == k, r.get("i"))
        c(f"lant_prev_{k}", r.get("prev_line_sha256") == prev, r.get("prev_line_sha256"))
        f = trib / r["file"]
        c(f"lant_fisier_{k}", f.exists() and sha(f.read_bytes()) == r.get("sha256"), r["file"])
        prev = sha(b)
        if r.get("target_date") != target or r.get("game") not in GAMES:
            continue
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        g = r["game"]
        c(f"{g}_consistenta_linie_doc", d.get("game") == g and d.get("target_date") == target
          and d.get("status") == r.get("status"))
        c(f"{g}_praguri_sigilate", d.get("thresholds") == THRESHOLDS, d.get("thresholds"))
        c(f"{g}_emisie_in_LANT", (d.get("emission") or {}).get("sha256") in lant_sha, (d.get("emission") or {}).get("sha256"))
        c(f"{g}_pca_false", d.get("positive_claims_allowed") is False)
        if g in games:
            c(f"{g}_decontare_unica", False, "a doua decontare pentru aceeași țintă")
        games[g] = {
            "linie_i": r["i"], "fisier": r["file"], "sha256": r["sha256"],
            "status": d.get("status"), "reason": d.get("reason"), "decided_utc": d.get("decided_utc"),
            "test_mode": d.get("test_mode"), "label": d.get("label"),
            "emisie": {k2: (d.get("emission") or {}).get(k2) for k2 in ("file", "sha256", "lant_i", "emitted_utc", "draw_utc")},
            "draw": d.get("draw"),
            "modele": {m: {k2: ((d.get("models") or {}).get(m) or {}).get(k2)
                           for k2 in ("ln_e", "ln_e_main", "ln_e_ball", "counted")} for m in MODELS},
            "streams_before": d.get("streams_before"), "streams_after": d.get("streams_after"),
            "thresholds": d.get("thresholds"),
        }
    c("lant_lungime_cunoscuta", True, len(raw))
    n = len(games)
    if not all(x["pass"] for x in checks):
        verdict = "DECONTARE_FAIL"
    elif n == len(GAMES):
        verdict = "DECONTARE_COMPLETA"
    elif n:
        verdict = "DECONTARE_PARTIALA"
    else:
        verdict = "DECONTARE_PENDING"
    return {"verdict": verdict, "n_decontate": n, "n_linii_DECONTARI": len(raw), "jocuri": games,
            "lipsa": [g for g in GAMES if g not in games], "checks": checks}


def to_md(rep: dict) -> str:
    L = [f"# Decontarea țintei {rep['tinta']} — raport read-only S24 (fără reglaje)", "",
         f"- Generat: {rep['utc']}; tribunal: `{rep['tribunal']}`",
         f"- **Verdict: `{rep['verdict']}`** ({rep['n_decontate']}/3 jocuri; linii DECONTARI: {rep['n_linii_DECONTARI']})",
         f"- Tribunal neatins: {rep['tribunal_neatins']} (arbore `{rep['arbore_inainte'][:12]}…`, {rep['fisiere_tribunal']} fișiere)",
         "- Valorile sunt copiate VERBATIM din documentele judecătorului TU4-JU; nimic nu e recalculat sau ajustat.",
         "- `positive_claims_allowed=false`: o decontare nu arată și nu implică vreun avantaj predictiv.", ""]
    for g, x in rep["jocuri"].items():
        L += [f"## {g}", "", f"- status `{x['status']}` ({x['reason']}), decis {x['decided_utc']}, fișier `{x['fisier']}` `{x['sha256'][:12]}…`",
              f"- extragerea: `{json.dumps(x['draw'], ensure_ascii=False)}`"]
        for m, v in x["modele"].items():
            L.append(f"- {m}: ln_e={v['ln_e']} (main {v['ln_e_main']}, bilă {v['ln_e_ball']}), counted={v['counted']}")
        L.append("")
    if rep["lipsa"]:
        L += [f"Nedecontate încă: {', '.join(rep['lipsa'])}.", ""]
    bad = [x for x in rep["checks"] if not x["pass"]]
    L += [f"Verificări: {len(rep['checks']) - len(bad)}/{len(rep['checks'])} PASS."]
    L += [f"- FAIL `{x['check']}`: {x['detail']}" for x in bad]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tinta", default="2026-10-29")
    ap.add_argument("--trib", type=Path, default=QL / "tu4/tribunal")
    ap.add_argument("--judecator", type=Path, default=QL / "tu4/judecator.py")
    ap.add_argument("--out", type=Path, default=QL / "tu4/rezultate/S24")
    a = ap.parse_args(argv)
    seal = ju_seal_sha(a.judecator)
    lock = shared_lock(a.trib)
    try:
        before, nfiles = tree_hash(a.trib)
        res = analyze(a.trib, a.tinta, seal)
        after, _ = tree_hash(a.trib)
    finally:
        if lock:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
    untouched = before == after
    res["checks"].append({"check": "tribunal_neatins", "pass": untouched, "detail": [before, after]})
    if not untouched:
        res["verdict"] = "DECONTARE_FAIL"
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rep = {"protocol": "TU4-S24 §2", "utc": utc, "tinta": a.tinta, "tribunal": str(a.trib), "ju_seal_sha": seal,
           "arbore_inainte": before, "arbore_dupa": after, "fisiere_tribunal": nfiles, "tribunal_neatins": untouched,
           "praguri_sigilate": THRESHOLDS, **res, "positive_claims_allowed": False}
    a.out.mkdir(parents=True, exist_ok=True)
    stem = f"DECONTARE_{a.tinta.replace('-', '')}_{utc}"
    pj, pm = a.out / f"{stem}.json", a.out / f"{stem}.md"
    pj.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    pm.write_text(to_md(rep), encoding="utf-8")
    print(json.dumps({"verdict": rep["verdict"], "n_decontate": rep["n_decontate"], "tribunal_neatins": untouched,
                      "n_checks": len(rep["checks"]), "n_pass": sum(x["pass"] for x in rep["checks"]),
                      "json": str(pj), "sha256": sha(pj.read_bytes())}, ensure_ascii=False))
    return 1 if rep["verdict"] == "DECONTARE_FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
