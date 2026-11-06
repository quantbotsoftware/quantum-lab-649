#!/usr/bin/env python3
"""XI-P2 §2 — inventarul de disponibilitate (după treapta A, înainte de treapta B).

Pentru fiecare țintă: HEAD (fișiere de date) sau GET (numai pagini HTML), cu înregistrarea stării HTTP, a antetelor
și a legăturilor spre fișiere de date. NU afișează și NU salvează textul paginilor; NU face GET pe fișiere de date.
Utilizare: inventar.py <tinte.json>  (listă de {"joc","tip":"HEAD"|"HTML","url"}); adaugă în xi/p2/INVENTAR_P2.json.
positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "INVENTAR_P2.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) QL649-XI-P2-inventar (cercetare; contact: utilizator local)"
DATA_RE = re.compile(r"""href\s*=\s*["']([^"']+?\.(?:csv|zip|xls|xlsx|txt|json)(?:\?[^"']*)?)["']""", re.I)
# v2 (după runda 1): și URL-uri spre fișiere de date din JSON-ul încorporat în pagină (nu numai href)
ANY_RE = re.compile(r"""(https?://[^\s"'<>]+?\.(?:csv|zip|xls|xlsx)(?:\?[^\s"'<>]*)?)(?=["'\s<>])""", re.I)
KEEP = ("Content-Type", "Content-Length", "Last-Modified", "ETag", "Date", "Content-Disposition", "Location")


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def probe(t):
    rec = {"joc": t["joc"], "tip": t["tip"], "url": t["url"], "utc": now()}
    req = urllib.request.Request(t["url"], method="HEAD" if t["tip"] == "HEAD" else "GET",
                                 headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            rec["status"] = r.status
            rec["url_final"] = r.geturl()
            rec["headers"] = {k: r.headers.get(k) for k in KEEP if r.headers.get(k) is not None}
            if t["tip"] == "HTML":
                ctype = (r.headers.get("Content-Type") or "").lower()
                if "html" not in ctype:
                    rec["nota"] = "nu este HTML: corpul NU a fost citit"
                else:
                    body = r.read(3_000_000).decode("utf-8", "replace")
                    rec["bytes_citite_neafisate"] = len(body)
                    links = set(DATA_RE.findall(body)) | set(ANY_RE.findall(body.replace("\\/", "/")))
                    rec["legaturi_date"] = sorted(links)[:200]
    except urllib.error.HTTPError as e:
        rec["status"] = e.code
        rec["headers"] = {k: e.headers.get(k) for k in KEEP if e.headers and e.headers.get(k) is not None}
    except Exception as e:  # noqa: BLE001 — se înregistrează orice eroare de rețea
        rec["eroare"] = f"{type(e).__name__}: {e}"
    return rec


def main(argv):
    tinte = json.loads(Path(argv[1]).read_text())
    inv = json.loads(OUT.read_text()) if OUT.exists() else []
    for t in tinte:
        rec = probe(t)
        inv.append(rec)
        short = {k: rec.get(k) for k in ("joc", "tip", "status", "url_final", "eroare")}
        short["headers"] = rec.get("headers")
        if "legaturi_date" in rec:
            short["legaturi_date"] = rec["legaturi_date"]
        print(json.dumps(short, ensure_ascii=False))
    OUT.write_text(json.dumps(inv, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
