#!/usr/bin/env python3
"""INCIDENT P2_02 — diagnostic de format al fișierelor brute HU: numărul de câmpuri și forma câmpurilor pe an
(9 = întreg, T = text, _ = gol). NU afișează și NU salvează nicio valoare extrasă. Scrie
xi/incidente/P2_02/DIAGNOSTIC_CAMPURI_HU.json. positive_claims_allowed=false."""
import collections
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
XI = Path(__file__).resolve().parent.parent
out = {}
for joc, f in (("HU_hatos", "00_hatos.csv"), ("HU_otos", "00_otos.csv")):
    txt = (XI / "date_p2" / joc / "sigilat" / f).read_bytes().decode("utf-8-sig")
    per = collections.defaultdict(collections.Counter)
    for line in txt.splitlines():
        if not line.strip():
            continue
        fl = line.split(";")
        while fl and fl[-1].strip() == "":
            fl.pop()
        shape = ";".join("9" if re.fullmatch(r"\d+", x.strip()) else ("T" if x.strip() else "_") for x in fl)
        per[fl[0]][f"{len(fl)}|{shape}"] += 1
    out[joc] = {y: dict(per[y]) for y in sorted(per)}
    tot = collections.Counter()
    for y in per:
        for k, c in per[y].items():
            tot[k.split("|")[0]] += c
    out[joc + "_total_pe_numar_campuri"] = dict(tot)
p = XI / "incidente" / "P2_02" / "DIAGNOSTIC_CAMPURI_HU.json"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(json.dumps({k: v for k, v in out.items() if k.endswith("_total_pe_numar_campuri")}))
print(p)
