#!/usr/bin/env python3
"""Sigilează codul P2 după calificarea PASS (protocol A §5–§6), ÎNAINTE de orice descărcare de date.
Utilizare: sigileaza_cod.py <CALIFICARE_P2_*.json>"""
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
XI = HERE.parent
ROOT = XI.parent
FILES = ["xi/p2/citire.py", "xi/p2/descarca.py", "xi/p2/p2.py", "xi/p2/verifica_p2.py"]


def h(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


cal = Path(sys.argv[1]).resolve()
c = json.loads(cal.read_text())
assert c["PASS_Q1_Q5"] is True and c["date_reale_citite"] is False
assert c["code_sha256"] == h(HERE / "p2.py") and c["citire_sha256"] == h(HERE / "citire.py"), "calificarea nu e pe codul curent"
assert not (XI / "date_p2").exists(), "date deja prezente"
seal_p = HERE / "SIGILIU_COD_P2.json"
assert not seal_p.exists()
seal = {"utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": {f: h(ROOT / f) for f in FILES},
        "calificare": str(cal.relative_to(ROOT)), "calificare_sha256": h(cal),
        "protocol_A_sha256": h(XI / "PROTOCOL_XI_P2.md"), "sigiliu_A_sha256": h(XI / "SIGILIU_XI_P2.json"),
        "sigiliu_B_sha256": h(XI / "SIGILIU_XI_P2_SURSE.json"), "banca_sha256": h(XI / "p1" / "banca.py"),
        "verifica_p1_sha256": h(XI / "p1" / "verifica_p1.py"),
        "date_descarcate_inainte": False,
        "note": "cod sigilat dupa calificarea pe date sintetice, INAINTE de orice descarcare de date",
        "positive_claims_allowed": False}
seal_p.write_text(json.dumps(seal, indent=2, ensure_ascii=False) + "\n")
for f in FILES:
    os.chmod(ROOT / f, 0o444)
os.chmod(seal_p, 0o444)
print(json.dumps(seal, indent=1))
print("SIGILIU_COD_P2", h(seal_p))
