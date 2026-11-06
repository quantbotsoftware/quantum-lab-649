#!/usr/bin/env python3
"""XI-P2 — cititorul arhivelor străine (reguli declarative din `xi/p2/SURSE_P2.json`, treapta B).

Nu afișează niciodată numere extrase. Erorile de format raportează numai „forma” rândului (cifrele → 9).
Amendamentul de citire XI-P2-01 a adăugat opțiunile declarative `filtru_rand`, `camp_data_poz`, `camp_cheie_poz`
și regula de numere `variante` (structura DE) și numărarea extragerilor pe an.
Normalizare generică (aceeași pentru toate jocurile): spațiile din jurul câmpurilor se elimină, rândurile goale se
ignoră, câmpurile goale de la SFÂRȘITUL unui rând (delimitator final) se elimină înaintea indexării pozționale.
positive_claims_allowed=false.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
import zipfile


class EroareCitire(Exception):
    """Format diferit de cel declarat (se raportează antetul și forma, fără valori)."""


class RandInvalid(Exception):
    """Rând în perioada stabilă care nu respectă formatul k din n ⇒ jocul este exclus (incident)."""


def forma(s: str) -> str:
    return re.sub(r"\d", "9", s)[:300]


def _decode(b: bytes, enc: str) -> str:
    if enc.lower() in ("utf-8", "utf8"):
        return b.decode("utf-8-sig")
    return b.decode(enc)


def _date(s: str, fmts) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    for f in fmts:
        if f == "excel_serial":
            if re.fullmatch(r"\d{4,6}(\.0+)?", s):
                return (dt.date(1899, 12, 30) + dt.timedelta(days=int(float(s)))).isoformat()
            continue
        try:
            return dt.datetime.strptime(s, f).date().isoformat()
        except ValueError:
            pass
    raise EroareCitire(f"data necitibilă, forma: {forma(s)!r}")


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    v = 0
    for ch in letters:
        v = v * 26 + (ord(ch) - 64)
    return v - 1


def _xlsx_tables(name: str, b: bytes, foi: str = "toate"):
    """Foile unui .xlsx (OOXML) citite cu biblioteca standard: valori ca text (numerele în forma stocată)."""
    import xml.etree.ElementTree as ET
    m = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        names = z.namelist()
        ss = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(f"{m}si"):
                ss.append("".join(t.text or "" for t in si.iter(f"{m}t")))
        sheets = sorted((x for x in names if re.match(r"xl/worksheets/sheet\d+\.xml$", x)),
                        key=lambda x: int(re.findall(r"\d+", x)[-1]))
        if foi == "prima":
            sheets = sheets[:1]
        out = []
        for sh in sheets:
            rows = []
            for r in ET.fromstring(z.read(sh)).iter(f"{m}row"):
                cells = {}
                for c in r.findall(f"{m}c"):
                    t, v = c.get("t"), c.find(f"{m}v")
                    if t == "s":
                        val = ss[int(v.text)]
                    elif t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(f"{m}t"))
                    else:
                        val = v.text if v is not None and v.text is not None else ""
                    cells[_col_index(c.get("r"))] = val.strip()
                row = [cells.get(i, "") for i in range(max(cells) + 1)] if cells else []
                while row and row[-1] == "":
                    row.pop()
                if row:
                    rows.append(row)
            out.append((f"{name}:{sh}", rows))
    return out


def _tables(spec_fmt: dict, files: list[tuple[str, bytes]]):
    """Întoarce lista de (nume, rânduri) pentru fișierele/membrii CSV sau foile XLSX."""
    out = []
    tabs = []
    rx = re.compile(spec_fmt.get("membri_regex", r".*"), re.I)
    for name, b in files:
        if spec_fmt["tip"] == "csv":
            out.append((name, b))
        elif spec_fmt["tip"] == "zip_csv":
            with zipfile.ZipFile(io.BytesIO(b)) as z:
                mem = sorted(m for m in z.namelist() if m.lower().endswith((".csv", ".txt")) and rx.search(m))
                if spec_fmt.get("membri", "unul") == "unul" and len(mem) != 1:
                    raise EroareCitire(f"{name}: membri CSV = {mem} (așteptat exact 1)")
                if not mem:
                    raise EroareCitire(f"{name}: niciun membru CSV/TXT")
                for mm in mem:
                    out.append((f"{name}:{mm}", z.read(mm)))
        elif spec_fmt["tip"] == "zip_xlsx":
            with zipfile.ZipFile(io.BytesIO(b)) as z:
                mem = sorted(m for m in z.namelist() if m.lower().endswith(".xlsx") and rx.search(m))
                if not mem:
                    raise EroareCitire(f"{name}: niciun membru XLSX")
                for mm in mem:
                    tabs += _xlsx_tables(f"{name}:{mm}", z.read(mm), spec_fmt.get("foi", "toate"))
        elif spec_fmt["tip"] == "xlsx":
            tabs += _xlsx_tables(name, b, spec_fmt.get("foi", "toate"))
        else:
            raise EroareCitire(f"tip de format fără regulă de citire: {spec_fmt['tip']}")
    for name, b in out:
        txt = _decode(b, spec_fmt.get("encoding", "utf-8"))
        rows = []
        for r in csv.reader(io.StringIO(txt), delimiter=spec_fmt["delim"]):
            r = [x.strip() for x in r]
            while r and r[-1] == "":
                r.pop()
            if r:
                rows.append(r)
        tabs.append((name, rows))
    return tabs


def _nums(fields, hdr, rule):
    if "variante" in rule:  # amendament P2_01: prima variantă potrivită (câmp + regex), ultima fără condiție
        for v in rule["variante"]:
            if "camp" not in v or (v["camp"] < len(fields) and re.fullmatch(v["regex"], fields[v["camp"]])):
                return _nums(fields, hdr, {k_: x for k_, x in v.items() if k_ not in ("camp", "regex")})
        raise ValueError("nicio variantă de poziții nu se potrivește")
    if "pozitii" in rule:
        vals = [fields[i] for i in rule["pozitii"]]
    elif "coloane" in rule:
        vals = [fields[hdr[c]] for c in rule["coloane"]]
    elif "coloana_spatiu" in rule:
        parts = fields[hdr[rule["coloana_spatiu"]]].split()
        vals = [parts[i] for i in rule["indici"]]
    else:
        raise EroareCitire(f"regulă de numere necunoscută: {sorted(rule)}")
    return [_int(v) for v in vals]


def _int(v: str) -> int:
    v = v.strip()
    if re.fullmatch(r"\d+\.0+", v):  # numere stocate ca 12.0 (foi de calcul)
        v = v.split(".")[0]
    return int(v)


def citeste_joc(spec: dict, files: list[tuple[str, bytes]]):
    """spec = intrarea jocului din SURSE_P2.json. files = [(nume, octeți)] în ordinea URL-urilor.

    Întoarce (extrageri, statistici). extragere = {"cheie", "data", "sets": {lab: [numere 1-bazate sortate]}}.
    """
    fmt = spec["format"]
    subs = spec["subjocuri"]
    stats = {"fisiere": [], "randuri_antet": 0, "randuri_inainte_start": 0, "randuri_dupa_sfarsit": 0,
             "randuri_alta_zi": 0, "duplicate_exacte": 0}
    recs = []
    gidx = 0
    for name, rows in _tables(fmt, files):
        hdr = {}
        start_i = 0
        if fmt.get("antet_regex"):  # antetul = primul rând care conține textul dat (rândurile de titlu dinainte se sar)
            hi = next((i for i, r in enumerate(rows) if any(re.search(fmt["antet_regex"], c) for c in r)), None)
            if hi is None:
                raise EroareCitire(f"{name}: antet negăsit; forma primului rând: {forma(';'.join(rows[0]) if rows else '')!r}")
            rows = rows[hi:]
            stats["randuri_titlu_sarite"] = stats.get("randuri_titlu_sarite", 0) + hi
        if fmt["antet"] is True:
            hdr = {c.lstrip("\ufeff"): i for i, c in enumerate(rows[0])}
            start_i = 1
        elif fmt["antet"] == "auto":
            if rows and not rows[0][fmt["camp_an"]].isdigit():
                start_i = 1
        stats["randuri_antet"] += start_i
        need = set()
        for rule in fmt["numere"].values():
            need |= set(rule.get("coloane", []))
            if "coloana_spatiu" in rule:
                need.add(rule["coloana_spatiu"])
        for c in ("col_data", "col_cheie"):
            if c in fmt:
                need.add(fmt[c])
        miss = sorted(c for c in need if c not in hdr) if fmt["antet"] is True else []
        if miss:
            raise EroareCitire(f"{name}: coloane lipsă {miss}; antet (forma): {forma(';'.join(rows[0]))!r}")
        file_recs = []
        flt = fmt.get("filtru_rand")  # amendament P2_01: rândurile de date = câmpul dat potrivește regex-ul
        for ri, f in enumerate(rows[start_i:]):
            if flt and not (flt["camp"] < len(f) and re.fullmatch(flt["regex"], f[flt["camp"]])):
                stats["randuri_nedate_sarite"] = stats.get("randuri_nedate_sarite", 0) + 1
                continue
            try:
                if fmt["ordine"] == "an_saptamana":
                    year, week = int(f[fmt["camp_an"]]), int(f[fmt["camp_sapt"]])
                    date = _date(f[fmt["camp_data"]], fmt["data_fmt"]) if len(f) > fmt["camp_data"] else None
                    key = f"{year}-{week:02d}" + (f"-{date}" if date else "")
                else:
                    year = week = None
                    ci = fmt["camp_data_poz"] if "camp_data_poz" in fmt else hdr[fmt["col_data"]]
                    raw_d = f[ci] if ci < len(f) else ""
                    if not raw_d.strip() and fmt.get("ignora_randuri_fara_data"):
                        stats["randuri_fara_data_ignorate"] = stats.get("randuri_fara_data_ignorate", 0) + 1
                        continue
                    date = _date(raw_d, fmt["data_fmt"])
                    if date is None:
                        raise ValueError("dată goală")
                    key = f[hdr[fmt["col_cheie"]]] if "col_cheie" in fmt else date
                    if "camp_cheie_poz" in fmt:
                        key = f"{date}#{f[fmt['camp_cheie_poz']]}"
                sets = {lab: _nums(f, hdr, fmt["numere"][lab]) for lab, _, _ in subs}
            except (ValueError, IndexError, KeyError) as e:
                raise RandInvalid(f"{name}: rândul {ri + start_i + 1} necitibil ({type(e).__name__}); "
                                  f"forma: {forma(';'.join(f))!r}") from None
            file_recs.append({"cheie": key, "data": date, "an": year, "sapt": week, "sets": sets,
                              "_forma": forma(";".join(f)), "_rand": ri + start_i + 1, "_fis": name})
        if fmt["ordine"] == "an_saptamana":
            dated = [r["data"] for r in file_recs if r["data"]]
            if len(dated) >= 2 and dated[0] > dated[-1]:
                file_recs.reverse()
        for r in file_recs:
            r["_g"] = gidx
            gidx += 1
        stats["fisiere"].append({"nume": name, "randuri_date": len(file_recs)})
        recs += file_recs
    # filtrul perioadei (după dată; rândurile fără dată după an)
    kept = []
    for r in recs:
        d = r["data"] or (f"{r['an']:04d}-12-31" if r["an"] is not None else None)
        d0 = r["data"] or (f"{r['an']:04d}-01-01" if r["an"] is not None else None)
        if d is None or d < spec["start"]:
            stats["randuri_inainte_start"] += 1
            continue
        if spec.get("sfarsit") and d0 > spec["sfarsit"]:
            stats["randuri_dupa_sfarsit"] += 1
            continue
        if spec.get("numai_ziua_saptamanii") is not None:
            if r["data"] is None or dt.date.fromisoformat(r["data"]).weekday() != spec["numai_ziua_saptamanii"]:
                stats["randuri_alta_zi"] += 1
                continue
        kept.append(r)
    # validare k din n
    for r in kept:
        for lab, n, k in subs:
            v = r["sets"][lab]
            if len(v) != k or len(set(v)) != k or not all(1 <= x <= n for x in v):
                raise RandInvalid(f"{r['_fis']}: rândul {r['_rand']} nu este {k} din {n}; forma: {r['_forma']!r}")
    # ordinea
    if spec["format"]["ordine"] == "an_saptamana":
        kept.sort(key=lambda r: (r["an"], r["sapt"], r["data"] or "", r["_g"]))
    else:
        kept.sort(key=lambda r: (r["data"], r["_g"]))
    # duplicate exacte (aceeași cheie și aceleași numere); aceeași cheie cu alte numere ⇒ invalid
    seen = {}
    out = []
    for r in kept:
        sig = tuple(tuple(sorted(r["sets"][lab])) for lab, _, _ in subs)
        k_ = (r["cheie"], r["data"])
        if k_ in seen:
            if seen[k_] == sig:
                stats["duplicate_exacte"] += 1
                continue
            raise RandInvalid(f"cheie repetată cu alte numere: rândul {r['_rand']} din {r['_fis']}")
        seen[k_] = sig
        out.append({"cheie": r["cheie"], "data": r["data"],
                    "sets": {lab: sorted(r["sets"][lab]) for lab, _, _ in subs}})
    per_an = {}
    for r in out:
        y = (r["data"] or r["cheie"])[:4]
        per_an[y] = per_an.get(y, 0) + 1
    stats["extrageri_pe_an"] = per_an
    return out, stats


def separa(extrageri: list):
    """Ultimele ⌊0.2·T⌋ extrageri (în ordinea dată) sunt rezerva."""
    T = len(extrageri)
    R = T // 5
    return extrageri[:T - R], extrageri[T - R:], T, R
