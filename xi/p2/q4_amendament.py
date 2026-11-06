#!/usr/bin/env python3
"""XI-P2 — calificarea Q4 a amendamentului de citire XI-P2-01 (date SINTETICE) + echivalența cititorului nou pe
jocurile deja separate (FR_loto, US_powerball, US_megamillions): re-citirea brută cu `citire.py` amendat trebuie să
dea exact aceleași sha-uri dev/rezervă (se afișează numai booleeni și numere de rânduri, nicio valoare extrasă).
Scrie xi/rezultate/P2/calificare/Q4_AMENDAMENT_P2_01_<utc>.json. positive_claims_allowed=false."""
import datetime as dt
import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
HERE = Path(__file__).resolve().parent
XI = HERE.parent
sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402
import citire  # noqa: E402


def h(b):
    return hashlib.sha256(b).hexdigest()


rng = np.random.Generator(np.random.PCG64(20261101 + 900))
AM = json.loads((HERE / "AMENDAMENTE_CITIRE_P2.json").read_text())["format"]
SUR = {g["joc"]: g for g in json.loads((HERE / "SURSE_P2.json").read_text())["incluse"]}
res = {}


def spec(joc):
    return dict(SUR[joc], format=AM[joc])


def draw(n, k):
    return sorted(int(x) + 1 for x in rng.choice(n, k, replace=False))


# HU cu BOM UTF-8; Hatoslottó cu coloana zilei și două extrageri pe săptămână
for joc, k, zi in (("HU_otos", 5, False), ("HU_hatos", 6, True)):
    n = SUR[joc]["subjocuri"][0][1]
    y0 = int(SUR[joc]["start"][:4])
    rows, exp = [], []
    day = dt.date(y0, 1, 7)
    i = 0
    while len(exp) < 1500:
        for off in ((0, 3) if zi and i > 300 else (0,)):
            d_ = day + dt.timedelta(days=off)
            nums = draw(n, k)
            dstr = "" if i < 150 else d_.strftime("%Y.%m.%d.")
            iso = day.isocalendar()
            cells = [str(iso[0]), str(iso[1])] + (["Csütörtök" if off else "Vasárnap"] if zi else []) + [dstr]
            cells += ["0", "0 Ft", "12", "1 234 567 Ft"] + [str(x) for x in nums]
            rows.append(";".join(cells))
            exp.append({"data": d_.isoformat() if dstr else None, "sets": {"princ": nums}})
        day += dt.timedelta(days=7)
        i += 1
    txt = "\ufeff" + "\n".join(reversed(rows)) + "\n"
    got, st = citire.citeste_joc(spec(joc), [("s.csv", txt.encode("utf-8"))])
    res[joc] = {"identice": [(e["data"], e["sets"]) for e in got] == [(e["data"], e["sets"]) for e in exp],
                "T": len(got), "T_asteptat": len(exp), "antet_sarit": st["randuri_antet"]}

# DE: foi pe ani, două aranjamente (VA | dată | 6 numere) și (KW | dată | MI/SA | 6 numere), titluri, note,
# extrageri de duminică timpurii (excluse de filtrul de zi), miercuri (excluse), serii Excel și date text
exp = []
by_year = {}
day = dt.date(1955, 10, 9)
while day.year < 2006:
    wds = (6,) if day.year < 1965 else ((5,) if day.year < 2000 else (2, 5))
    if day.weekday() in wds:
        nums = draw(49, 6)
        serial = (day - dt.date(1899, 12, 30)).days
        dcell = serial if day.day % 5 else day.strftime("%d.%m.%Y")
        if day.year < 2000:
            row = [str(len(by_year.get(day.year, [])) + 1), dcell] + list(nums) + [7, "1000.5", "unbesetzt"]
        else:
            row = ["40" if day.weekday() == 2 else "", dcell, "MI" if day.weekday() == 2 else "SA"] + list(nums) + [3, 9]
        by_year.setdefault(day.year, []).append(row)
        if day.weekday() == 5:
            exp.append({"data": day.isoformat(), "sets": {"princ": sorted(nums)}})
    day += dt.timedelta(days=1)
bz = io.BytesIO()
book = io.BytesIO()
ss, idx = [], {}


def cell(ci, ri, v):
    ref = f"{chr(65 + ci)}{ri}"
    if isinstance(v, str):
        if v not in idx:
            idx[v] = len(ss)
            ss.append(v)
        return f'<c r="{ref}" t="s"><v>{idx[v]}</v></c>'
    return f'<c r="{ref}"><v>{v}</v></c>'


ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
with zipfile.ZipFile(book, "w") as z:
    for si, (y, rows) in enumerate(sorted(by_year.items(), key=lambda kv: -kv[0])):
        hdr = [["Zahlenlotto \"6 aus 49\"", None, "Gewinnzahlen"], ["Alle Zahlenangaben ohne Gewähr"],
               ["VA" if y < 2000 else "KW", str(y), "gezogener Reihenfolge"]]
        allr = hdr + rows + [["* Fußnote"]]
        body = "".join(f'<row r="{ri + 1}">' + "".join(cell(ci, ri + 1, v) for ci, v in enumerate(r) if v is not None)
                       + "</row>" for ri, r in enumerate(allr))
        z.writestr(f"xl/worksheets/sheet{si + 1}.xml",
                   f'<?xml version="1.0" encoding="UTF-8"?><worksheet {ns}><sheetData>{body}</sheetData></worksheet>')
    z.writestr("xl/sharedStrings.xml", f'<?xml version="1.0" encoding="UTF-8"?><sst {ns}>'
               + "".join(f"<si><t>{s.replace('&', '&amp;').replace('<', '&lt;')}</t></si>" for s in ss) + "</sst>")
with zipfile.ZipFile(bz, "w") as z:
    z.writestr("LOTTO6aus49_test.xlsx", book.getvalue())
got, st = citire.citeste_joc(spec("DE_6aus49_sambata"), [("de.zip", bz.getvalue())])
res["DE_6aus49_sambata"] = {"identice": [(e["data"], e["sets"]) for e in got] == [(e["data"], e["sets"]) for e in exp],
                            "T": len(got), "T_asteptat": len(exp), "randuri_alta_zi": st["randuri_alta_zi"],
                            "randuri_nedate_sarite": st.get("randuri_nedate_sarite")}

# echivalența pe jocurile deja separate (cititorul nou, aceleași reguli din SURSE_P2.json)
eqv = {}
for joc in ("FR_loto", "US_powerball", "US_megamillions"):
    base = XI / "date_p2" / joc
    prov = json.loads((base / "PROVENIENTA.json").read_text())
    files = [(Path(f["fisier"]).name, (XI / f["fisier"]).read_bytes()) for f in prov["fisiere"]]
    ex, _ = citire.citeste_joc(SUR[joc], files)
    dev, rez, T, R = citire.separa(ex)
    if (base / "EXCLUS.json").exists():
        eqv[joc] = {"T_identic": T == json.loads((base / "EXCLUS.json").read_text())["T"]}
        continue
    sep = json.loads((base / "SEPARARE.json").read_text())
    rb = (json.dumps({"joc": joc, "subjocuri": SUR[joc]["subjocuri"], "R": R, "extrageri": rez},
                     ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    d = json.loads((base / "dev.json").read_text())
    eqv[joc] = {"T_identic": T == sep["T"], "rezerva_sha_identic": h(rb) == sep["rezerva_sha256"],
                "dev_extrageri_identice": d["extrageri"] == dev}
res["echivalenta_cititor_nou"] = eqv
ok = (all(res[j]["identice"] for j in ("HU_otos", "HU_hatos", "DE_6aus49_sambata"))
      and all(all(v.values()) for v in eqv.values()))
res["citire_sha256"] = h((HERE / "citire.py").read_bytes())
res["amendament_sha256"] = h((HERE / "AMENDAMENTE_CITIRE_P2.json").read_bytes())
res["PASS"] = bool(ok)
res["positive_claims_allowed"] = False
utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
p = XI / "rezultate" / "P2" / "calificare" / f"Q4_AMENDAMENT_P2_01_{utc}.json"
p.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
os.chmod(p, 0o444)
print(json.dumps(res, ensure_ascii=False))
print(p, h(p.read_bytes()))
