#!/usr/bin/env python3
"""XI-P2 §3 — descărcarea unică, proveniența și separarea dezvoltare/rezervă.

  descarca            descarcă o dată fișierele jocurilor incluse (SURSE_P2.json), scrie PROVENIENTA.json și
                      STRUCTURA.json (membrii arhivelor, numărul de rânduri, FORMA primului/ultimului rând: cifrele → 9)
  separa [joc ...]    citește după regulile declarate, validează, ordonează, separă ultimele ⌊0.2·T⌋ în rezerva.json
                      (0400) și scrie dev.json (0444); sub 1 000 de extrageri ⇒ EXCLUS.json. Refuză repetarea.

Niciun număr extras nu se afișează. Cod sigilat (xi/p2/SIGILIU_COD_P2.json) înainte de rulare.
positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
XI = HERE.parent
DATE = XI / "date_p2"
SURSE = HERE / "SURSE_P2.json"
AMEND = HERE / "AMENDAMENTE_CITIRE_P2.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) QL649-XI-P2 (cercetare statistica)"
T_MIN = 1000

sys.path.insert(0, str(HERE))
import citire  # noqa: E402


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def verifica_sigiliu_cod():
    seal = json.loads((HERE / "SIGILIU_COD_P2.json").read_text())
    for rel, s in seal["files"].items():
        assert sha((XI.parent / rel).read_bytes()) == s, f"sha cod {rel}"
    return seal


def specs():
    d = json.loads(SURSE.read_text())
    games = {g["joc"]: g for g in d["incluse"]}
    if AMEND.exists():  # amendamente de citire sigilate (numai câmpul "format" al unui joc)
        am = json.loads(AMEND.read_text())
        for joc, fmt in am["format"].items():
            games[joc] = dict(games[joc], format=fmt)
    return games


def structura(name: str, b: bytes):
    info = {"nume": name, "octeti": len(b), "sha256": sha(b)}
    def txt_info(bb):
        lines = [x for x in bb.decode("latin-1").splitlines() if x.strip()]
        return {"linii_nevide": len(lines), "forma_prima": citire.forma(lines[0]) if lines else None,
                "forma_a_doua": citire.forma(lines[1]) if len(lines) > 1 else None,
                "forma_ultima": citire.forma(lines[-1]) if lines else None}
    if b[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            info["membri"] = []
            for m in z.infolist():
                e = {"nume": m.filename, "marime": m.file_size}
                if m.filename.lower().endswith((".csv", ".txt")):
                    e.update(txt_info(z.read(m.filename)))
                info["membri"].append(e)
    else:
        info.update(txt_info(b))
    return info


def cmd_descarca():
    verifica_sigiliu_cod()
    for joc, g in specs().items():
        d = DATE / joc / "sigilat"
        if d.exists():
            print(f"{joc}: REFUZ, deja descărcat")
            continue
        d.mkdir(parents=True)
        prov = {"joc": joc, "utc_start": now(), "fisiere": []}
        for i, url in enumerate(g["urls"]):
            rec = {"url": url, "incercari": []}
            body = None
            for att in range(3):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
                    with urllib.request.urlopen(req, timeout=180) as r:
                        body = r.read()
                        rec.update({"status": r.status, "url_final": r.geturl(), "utc": now(),
                                    "headers": {k: r.headers.get(k) for k in
                                                ("Date", "Last-Modified", "ETag", "Content-Length",
                                                 "Content-Type", "Content-Disposition") if r.headers.get(k)}})
                    rec["incercari"].append({"utc": now(), "ok": True})
                    break
                except (urllib.error.URLError, TimeoutError, OSError) as e:
                    rec["incercari"].append({"utc": now(), "ok": False, "eroare": f"{type(e).__name__}: {e}"})
                    time.sleep(5)
            if body is None:
                rec["esec"] = True
                prov["fisiere"].append(rec)
                continue
            base = url.split("?")[0].rstrip("/").split("/")[-1] or "fisier"
            if base == "rows.csv":
                base = f"{joc}_rows.csv"
            p = d / f"{i:02d}_{base}"
            p.write_bytes(body)
            os.chmod(p, 0o400)
            rec.update({"fisier": str(p.relative_to(XI)), "octeti": len(body), "sha256": sha(body),
                        "structura": structura(p.name, body)})
            prov["fisiere"].append(rec)
        prov["utc_sfarsit"] = now()
        pp = DATE / joc / "PROVENIENTA.json"
        pp.write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n")
        os.chmod(pp, 0o444)
        print(json.dumps({"joc": joc, "fisiere": [{k: f.get(k) for k in ("url", "status", "octeti", "sha256", "esec")}
                                                  | {"structura": f.get("structura")} for f in prov["fisiere"]]},
                         ensure_ascii=False, indent=1))
    return 0


def cmd_separa(jocuri):
    verifica_sigiliu_cod()
    sp = specs()
    rc = 0
    for joc in (jocuri or list(sp)):
        g = sp[joc]
        base = DATE / joc
        if (base / "dev.json").exists() or (base / "EXCLUS.json").exists():
            print(f"{joc}: REFUZ, separarea a fost deja făcută")
            continue
        prov = json.loads((base / "PROVENIENTA.json").read_text())
        files = []
        ok = True
        for f in prov["fisiere"]:
            if f.get("esec"):
                ok = False
                break
            b = (XI / f["fisier"]).read_bytes()
            assert sha(b) == f["sha256"], f"sha brut {f['fisier']}"
            files.append((Path(f["fisier"]).name, b))
        res = {"joc": joc, "utc": now(), "surse_sha256": sha(SURSE.read_bytes()),
               "amendament_citire_sha256": sha(AMEND.read_bytes()) if AMEND.exists() else None,
               "brut_sha256": [f.get("sha256") for f in prov["fisiere"]]}
        if not ok:
            res.update({"exclus": True, "motiv": "descărcare eșuată după 3 încercări"})
            _scrie(base / "EXCLUS.json", res, 0o444)
            print(json.dumps(res, ensure_ascii=False))
            continue
        try:
            ex, st = citire.citeste_joc(g, files)
        except citire.EroareCitire as e:
            print(f"{joc}: EROARE_CITIRE (format diferit; amendament de citire posibil): {e}")
            rc = 3
            continue
        except citire.RandInvalid as e:
            res.update({"exclus": True, "motiv": f"rând invalid în perioada stabilă: {e}"})
            _scrie(base / "EXCLUS.json", res, 0o444)
            print(json.dumps(res, ensure_ascii=False))
            continue
        dev, rez, T, R = citire.separa(ex)
        res.update({"statistici_citire": st, "T": T, "R": R, "T_dev": T - R})
        if T < T_MIN:
            res.update({"exclus": True, "motiv": f"T = {T} < {T_MIN} în perioada stabilă"})
            _scrie(base / "EXCLUS.json", res, 0o444)
            print(json.dumps({k: res[k] for k in ("joc", "T", "exclus", "motiv")}, ensure_ascii=False))
            continue
        subs = g["subjocuri"]
        rez_doc = {"joc": joc, "subjocuri": subs, "R": R, "extrageri": rez}
        rb = (json.dumps(rez_doc, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        (base / "rezerva.json").write_bytes(rb)
        os.chmod(base / "rezerva.json", 0o400)
        (base / "REZERVA_SHA256.txt").write_text(sha(rb) + "  rezerva.json\n")
        os.chmod(base / "REZERVA_SHA256.txt", 0o444)
        dev_doc = {"joc": joc, "subjocuri": subs, "T_total": T, "R": R, "T_dev": T - R,
                   "rezerva_sha256": sha(rb), "brut_sha256": res["brut_sha256"], "extrageri": dev}
        _scrie(base / "dev.json", dev_doc, 0o444, compact=True)
        res.update({"dev_sha256": sha((base / "dev.json").read_bytes()), "rezerva_sha256": sha(rb),
                    "dev_prima_data": dev[0]["data"] or dev[0]["cheie"], "dev_ultima_data": dev[-1]["data"] or dev[-1]["cheie"],
                    "rez_prima_data": rez[0]["data"] or rez[0]["cheie"], "rez_ultima_data": rez[-1]["data"] or rez[-1]["cheie"]})
        _scrie(base / "SEPARARE.json", res, 0o444)
        print(json.dumps({k: res[k] for k in ("joc", "T", "R", "T_dev", "dev_prima_data", "dev_ultima_data",
                                              "rez_prima_data", "rez_ultima_data", "dev_sha256", "rezerva_sha256")}
                         | {"statistici": st}, ensure_ascii=False))
    return rc


def _scrie(p: Path, obj, mode, compact=False):
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(obj, indent=2, ensure_ascii=False)
    p.write_text(txt + "\n")
    os.chmod(p, mode)


def main(argv):
    if len(argv) >= 2 and argv[1] == "descarca":
        return cmd_descarca()
    if len(argv) >= 2 and argv[1] == "separa":
        return cmd_separa(argv[2:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
