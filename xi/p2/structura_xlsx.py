#!/usr/bin/env python3
"""XI-P2 §3 — structura unei arhive XLSX descărcate, pentru amendamentul de citire: pentru fiecare foaie numărul de
rânduri și FORMA (cifrele → 9) primelor 6 și ultimelor 2 rânduri. Nu afișează valori numerice.
Utilizare: structura_xlsx.py <fișier.zip|.xlsx>"""
import io
import json
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import citire  # noqa: E402

p = Path(sys.argv[1])
b = p.read_bytes()
tabs = []
if p.suffix.lower() == ".zip":
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        for m in z.namelist():
            if m.lower().endswith(".xlsx"):
                tabs += citire._xlsx_tables(m, z.read(m))
else:
    tabs = citire._xlsx_tables(p.name, b)
out = []
for name, rows in tabs:
    out.append({"foaie": name, "randuri": len(rows),
                "forme_inceput": [citire.forma(" | ".join(r)) for r in rows[:6]],
                "forme_sfarsit": [citire.forma(" | ".join(r)) for r in rows[-2:]],
                "lungimi_randuri_distincte": sorted({len(r) for r in rows})[:20]})
print(json.dumps(out, ensure_ascii=False, indent=1))
