#!/usr/bin/env python3
"""XI-P2 — banca P1 înghețată aplicată arhivelor străine (planul V12, faza P2).

Implementează `xi/PROTOCOL_XI_P2.md` (treapta A, 01ff6235…) cu `xi/PROTOCOL_XI_P2_ANEXA_SURSE.md` +
`xi/p2/SURSE_P2.json` (treapta B). Funcțiile modelului vin NESCHIMBATE din `xi/p1/banca.py` (sha d7d1cbb4…,
import fără bytecode); acest modul adaugă numai citirea datelor, garda rezervei, testul global și ieșirile.

  teste        calificarea Q1–Q5 + rezoluția descriptivă (date SINTETICE; nu citește date reale)
  dezvoltare   rularea unică pe partea de dezvoltare (cod sigilat; refuză repetarea)
  confirmare   rularea unică pe rezervă, numai pentru supraviețuitori (cere SIGILIU_CONFIRMARE_P2.json)
Calcul clasic float64 pe CPU. positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import io
import itertools
import json
import math
import os
import shutil
import sys
import time
import zipfile
from multiprocessing import Pool
from pathlib import Path

sys.dont_write_bytecode = True
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):  # un fir BLAS per proces (Pool)
    os.environ.setdefault(_v, "1")
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
XI = HERE.parent
ROOT = XI.parent
DATE = XI / "date_p2"
OUT = XI / "rezultate" / "P2"
CAL = OUT / "calificare"
CONF = HERE / "SIGILIU_CONFIRMARE_P2.json"
BANCA_SHA = "d7d1cbb48553bc61b26285771d7456c53bc554f77ace26fe889756be624a6770"
PROT_A_SHA = "01ff623543ca73b11cd5b66f5b4ed2ae920e38fba66198ff7348452e49957707"
SEED = 20261101
ALPHA = 0.01
PROCS = 24

sys.path.insert(0, str(HERE))
import citire  # noqa: E402


def sha_b(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_f(p) -> str:
    return sha_b(Path(p).read_bytes())


def utcnow():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_banca():
    p = XI / "p1" / "banca.py"
    assert sha_f(p) == BANCA_SHA, "sha banca.py"
    spec = importlib.util.spec_from_file_location("banca_p1_inghetata", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


B = _load_banca()
SEAL_P1 = json.loads((XI / "p1" / "SIGILIU_COD_P1.json").read_text())
QUAL = tuple(SEAL_P1["qualified_families"])
PREDS = [X for X in B.PREDICTORS if X in QUAL or (X == "COMB" and SEAL_P1["COMB_qualified"])]
SURSE = json.loads((HERE / "SURSE_P2.json").read_text())
GAMES = {g["joc"]: [tuple(s) for s in g["subjocuri"]] for g in SURSE["incluse"]}
# Estimări calendaristice ale lui T (pentru lungimile Q2/Q3/rezoluție; protocol A §5: nu se repetă dacă T diferă).
T_EST = {"HU_otos": 3630, "HU_hatos": 2000, "FR_loto": 2460, "DE_6aus49_sambata": 3700,
         "US_powerball": 1430, "US_megamillions": 770}
TDEV_EST = {g: T_EST[g] - T_EST[g] // 5 for g in T_EST}


# ---------------------------------------------------------------- garda rezervei
def citeste_date(path: Path, conf: Path = CONF, dev_rez: Path | None = None) -> bytes:
    """Orice citire de date trece pe aici. Rezerva și fișierele brute: numai cu sigiliul de confirmare valid."""
    p = Path(path).resolve()
    if "sigilat" in p.parts or p.name.startswith("rezerva"):
        if not conf.exists():
            raise PermissionError(f"rezerva este sigilată (lipsește {conf.name}): {p.name}")
        s = json.loads(conf.read_text())
        if not s.get("supravietuitori"):
            raise PermissionError("niciun supraviețuitor: rezerva rămâne sigilată")
        dr = dev_rez if dev_rez is not None else OUT / "P2_DEV_REZULTATE.json"
        if sha_f(dr) != s.get("dev_rezultate_sha256"):
            raise PermissionError("sha-ul rezultatelor de dezvoltare nu corespunde sigiliului de confirmare")
    return p.read_bytes()


def load_dev(joc: str):
    d = json.loads(citeste_date(DATE / joc / "dev.json"))
    assert [tuple(s) for s in d["subjocuri"]] == GAMES[joc]
    return d


def histories(doc, subs):
    return {lab: [np.array([x - 1 for x in e["sets"][lab]], dtype=np.int64) for e in doc["extrageri"]]
            for lab, _, _ in subs}


# ---------------------------------------------------------------- calificare
def _combs(n, k):
    return np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(n), k)),
                       dtype=np.int8, count=math.comb(n, k) * k).reshape(-1, k)


def _q1_case(nk):
    n, k = nk
    rng = np.random.Generator(np.random.PCG64(SEED + 1 + 100 * n + k))
    out = {"n": n, "k": k}
    S = np.sort(rng.choice(n, k, replace=False))
    LP, MG = B.run_components([S], n, k, need_marg=True)
    out["uniform_maxabs"] = max(float(np.max(np.abs(LP[0] + math.log(math.comb(n, k))))),
                                float(np.max(np.abs(MG[0] / (k / n) - 1))))
    w = rng.uniform(0.5, 2.0, n)
    wn = w / w.mean()
    lz = math.log(B.esp(wn, k)[k])
    if k == 1:
        out["cb_sum"] = float(np.exp(np.log(wn) - lz).sum())
        out["fermi_sum"] = None
    else:
        combs = _combs(n, k)
        lw = np.log(wn)
        tot = 0.0
        for a in range(0, len(combs), 2_000_000):
            tot += float(np.exp(lw[combs[a:a + 2_000_000]].sum(axis=1) - lz).sum())
        out["cb_sum"] = tot
        H = B.gen_history("uniform", n, k, 300, SEED + 2 + 100 * n + k)
        c = np.zeros(n)
        C = np.zeros((n, n))
        for s in H:
            c[s] += 1
            C[np.ix_(s, s)] += 1
        mu, U = B.fermi_L(c, C, 300, 200, n, k)
        L = (U * mu) @ U.T
        lz = math.log(B.esp(mu, k)[k])
        tot = 0.0
        for a in range(0, len(combs), 250_000):
            cb = combs[a:a + 250_000].astype(np.int64)
            sub = L[cb[:, :, None], cb[:, None, :]]
            tot += float(np.exp(np.linalg.slogdet(sub)[1] - lz).sum())
        out["fermi_sum"] = tot
        out["fermi_spectru_min_max"] = [float(mu.min()), float(mu.max())]
        del combs
    out["PASS"] = bool(out["uniform_maxabs"] <= 1e-12 and abs(out["cb_sum"] - 1) <= 1e-9
                       and (out["fermi_sum"] is None or abs(out["fermi_sum"] - 1) <= 1e-9))
    return out


def _q2_game(joc):
    subs = GAMES[joc]
    T = TDEV_EST[joc]
    t0 = T // 2
    ok = True
    info = {}
    for si, (lab, n, k) in enumerate(subs):
        H = B.gen_history("uniform", n, k, T, SEED + 300 + 17 * si + 1000 * list(GAMES).index(joc))
        H2 = list(H[:t0 - 1]) + B.gen_history("uniform", n, k, T - t0 + 1, SEED + 301 + 17 * si
                                              + 1000 * list(GAMES).index(joc))
        LP0, MG0 = B.run_components(H, n, k, need_marg=True)
        LP1, MG1 = B.run_components(H2, n, k, need_marg=True)
        same_lp = bool(np.array_equal(LP0[:t0 - 1], LP1[:t0 - 1]))
        same_mg = bool(np.array_equal(MG0[:t0], MG1[:t0]))
        tick = True
        for X in PREDS:
            rho = B.priors(X, k, QUAL)
            _, _, m0 = B.mixture_seq(LP0, rho, n, k, MG0)
            _, _, m1 = B.mixture_seq(LP1, rho, n, k, MG1)
            tick &= all(B.ticket(m0[t], k) == B.ticket(m1[t], k) for t in range(t0))
        info[lab] = {"T": T, "t0": t0, "logp_identice": same_lp, "marg_identice": same_mg, "bilete_identice": bool(tick)}
        ok &= same_lp and same_mg and tick
    return joc, {"sub": info, "PASS": bool(ok)}


def _gen_stat(n, k, T, seed, d):
    rng = np.random.Generator(np.random.PCG64(seed))
    w = np.where(np.arange(n) < n // 2, 1 + d, 1 / (1 + d))
    Es = B.cb_sampler_table(w, k)
    return [B.cb_sample(w, k, rng, Es) for _ in range(T)]


def _hist_task(spec):
    joc, kind, d, seed = spec
    res = {X: 0.0 for X in PREDS}
    minsub = []
    for si, (lab, n, k) in enumerate(GAMES[joc]):
        T = TDEV_EST[joc]
        if kind == "stat" and si == 0:
            H = _gen_stat(n, k, T, seed, d)
        else:
            H = B.gen_history("uniform", n, k, T, seed + 7919 * si)
        LP, _ = B.run_components(H, n, k)
        vals = {X: B.logE_closed(LP, B.priors(X, k, QUAL), n, k) for X in PREDS}
        for X in PREDS:
            res[X] += vals[X]
        minsub.append(min(vals.values()))
    res["_min_sub"] = min(minsub)
    return spec, res


def _q4_synthetic(tmp: Path):
    """Fișiere sintetice în formatele declarate ⇒ cititorul trebuie să reproducă exact extragerile."""
    rng = np.random.Generator(np.random.PCG64(SEED + 500))
    out = {}
    sp = {g["joc"]: g for g in SURSE["incluse"]}

    def draw(n, k):
        return sorted(int(x) + 1 for x in rng.choice(n, k, replace=False))

    def check(joc, files, expected):
        got, st = citire.citeste_joc(sp[joc], files)
        same = [(e["data"], e["sets"]) for e in got] == [(e["data"], e["sets"]) for e in expected]
        dev, rez, T, R = citire.separa(got)
        return {"extrageri_identice": bool(same), "T": T, "R": R, "R_corect": R == T // 5,
                "dev_plus_rez": len(dev) + len(rez) == T, "statistici": st}

    # Ungaria (fără antet, cel mai nou primul, rânduri vechi fără dată, câmpuri cu „Ft”)
    for joc, k in (("HU_otos", 5), ("HU_hatos", 6)):
        n = GAMES[joc][0][1]
        start_year = int(sp[joc]["start"][:4])
        rows, exp = [], []
        day = dt.date(start_year, 1, 4)
        for i in range(1300):
            y, w_ = day.isocalendar()[0], day.isocalendar()[1]
            nums = draw(n, k)
            dstr = "" if i < 200 else day.strftime("%Y.%m.%d.")
            prizes = ";".join(["0", "0 Ft", "12", "1 234 567 Ft", "345", "12 000 Ft"])
            rows.append(f"{y};{w_};{dstr};{prizes};" + ";".join(str(x) for x in nums))
            exp.append({"data": (day.isoformat() if dstr else None), "sets": {"princ": nums}})
            day += dt.timedelta(days=7)
        old = f"{start_year - 1};50;;0;0 Ft;1;2;3;4;5;6;" + ";".join(str(x) for x in draw(n, k))
        rows.append(old)
        txt = "\n".join(reversed(rows)) + "\n"
        out[joc] = check(joc, [("sint.csv", txt.encode("latin-1"))], exp)
        out[joc]["rand_vechi_exclus"] = out[joc]["statistici"]["randuri_inainte_start"] == 1
        bad = txt.replace(";" + ";".join(str(x) for x in exp[700]["sets"]["princ"]), ";" + ";".join(["1"] * k), 1)
        try:
            citire.citeste_joc(sp[joc], [("rau.csv", bad.encode("latin-1"))])
            out[joc]["refuza_rand_invalid"] = False
        except citire.RandInvalid:
            out[joc]["refuza_rand_invalid"] = True

    # Franța (4 arhive zip, două formate de dată, suprapunere = duplicat, rând anterior startului)
    hdr = ("annee_numero_de_tirage;jour_de_tirage;date_de_tirage;date_de_forclusion;boule_1;boule_2;boule_3;"
           "boule_4;boule_5;numero_chance;combinaison_gagnante_en_ordre_croissant;nombre_de_gagnant_au_rang1")
    day = dt.date(2008, 10, 1)
    allr, exp = [], []
    while len(allr) < 1400:
        if day.weekday() in (0, 2, 5):
            nums, ch = draw(49, 5), int(rng.integers(1, 11))
            allr.append((day, nums, ch))
            if day >= dt.date(2008, 10, 6):
                exp.append({"data": day.isoformat(), "sets": {"princ": nums, "bila": [ch]}})
        day += dt.timedelta(days=1)
    cuts = [0, 400, 800, 1000, len(allr)]
    files = []
    for fi in range(4):
        part = allr[max(0, cuts[fi] - (1 if fi else 0)):cuts[fi + 1]]  # un rând suprapus ⇒ duplicat exact
        lines = [hdr]
        for j, (d_, nums, ch) in enumerate(reversed(part)):
            ds = d_.strftime("%Y%m%d") if fi == 0 else d_.strftime("%d/%m/%Y")
            key = f"{d_.year}{d_.timetuple().tm_yday:03d}"
            lines.append(f"{key};LUNDI;{ds};{ds};" + ";".join(map(str, nums)) + f";{ch};x;0")
        bz = io.BytesIO()
        with zipfile.ZipFile(bz, "w") as z:
            z.writestr(f"loto_{fi}.csv", ("\n".join(lines) + "\n").encode("latin-1"))
        files.append((f"f{fi}.zip", bz.getvalue()))
    out["FR_loto"] = check("FR_loto", files, exp)
    out["FR_loto"]["duplicate_3"] = out["FR_loto"]["statistici"]["duplicate_exacte"] == 3

    # SUA (antet, numere cu zero în față, format vechi înainte de start / după sfârșit)
    for joc in ("US_powerball", "US_megamillions"):
        g = sp[joc]
        (_, n1, k1), (_, n2, _) = GAMES[joc]
        lines = ["Draw Date,Winning Numbers,Multiplier" if joc == "US_powerball"
                 else "Draw Date,Winning Numbers,Mega Ball,Multiplier"]
        exp = []
        day = dt.date.fromisoformat(g["start"]) - dt.timedelta(days=60)
        end = dt.date.fromisoformat(g["sfarsit"]) + dt.timedelta(days=40) if g["sfarsit"] else None
        cnt = 0
        while cnt < 1250:
            if day.weekday() in (0, 2, 5) if joc == "US_powerball" else day.weekday() in (1, 4):
                inside = day >= dt.date.fromisoformat(g["start"]) and (not g["sfarsit"] or day <= dt.date.fromisoformat(g["sfarsit"]))
                nn, bb = (n1, n2) if inside else (n1 + 6, n2 + 9)
                nums = sorted(int(x) + 1 for x in rng.choice(nn, k1, replace=False))
                ball = int(rng.integers(1, bb + 1))
                ds = day.strftime("%m/%d/%Y")
                if joc == "US_powerball":
                    lines.append(f"{ds},{' '.join(f'{x:02d}' for x in nums)} {ball:02d},2")
                else:
                    lines.append(f"{ds},{' '.join(f'{x:02d}' for x in nums)},{ball:02d},3")
                if inside:
                    exp.append({"data": day.isoformat(), "sets": {"princ": nums, "bila": [ball]}})
                    cnt += 1
                if end and day > end:
                    break
            day += dt.timedelta(days=1)
            if end and day > end + dt.timedelta(days=30):
                break
        body = "\n".join([lines[0]] + list(reversed(lines[1:]))) + "\n"
        out[joc] = check(joc, [("sint.csv", body.encode())], exp)
    for joc, r in out.items():
        r["PASS"] = bool(r["extrageri_identice"] and r["R_corect"] and r["dev_plus_rez"]
                         and r.get("refuza_rand_invalid", True) and r.get("rand_vechi_exclus", True)
                         and r.get("duplicate_3", True))
    out["GENERIC_zip_xlsx_si_multi_csv"] = _q4_generic(rng)
    out["DE_6aus49_sambata"] = {"PASS": None, "nota": "regula de citire se fixează prin amendament; Q4 DE după amendament"}
    return out


def _xlsx_bytes(rows):
    """XLSX minimal (numai foaia și șirurile partajate) pentru testarea cititorului."""
    ss, idx = [], {}

    def cell(ci, ri, v):
        ref = f"{chr(65 + ci)}{ri}"
        if isinstance(v, str):
            if v not in idx:
                idx[v] = len(ss)
                ss.append(v)
            return f'<c r="{ref}" t="s"><v>{idx[v]}</v></c>'
        return f'<c r="{ref}"><v>{v}</v></c>'
    body = "".join(f'<row r="{ri + 1}">' + "".join(cell(ci, ri + 1, v) for ci, v in enumerate(r) if v is not None)
                   + "</row>" for ri, r in enumerate(rows))
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    sheet = f'<?xml version="1.0" encoding="UTF-8"?><worksheet {ns}><sheetData>{body}</sheetData></worksheet>'
    sst = (f'<?xml version="1.0" encoding="UTF-8"?><sst {ns}>'
           + "".join(f"<si><t>{s}</t></si>" for s in ss) + "</sst>")
    bz = io.BytesIO()
    with zipfile.ZipFile(bz, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/sharedStrings.xml", sst)
    return bz.getvalue()


def _q4_generic(rng):
    """Cititoarele generice pregătite pentru amendamentul DE: zip cu mai multe XLSX/CSV, titluri, serii Excel."""
    res = {}
    spec = {"joc": "TEST", "subjocuri": [["princ", 49, 6]], "start": "1955-10-09", "sfarsit": None,
            "numai_ziua_saptamanii": 5,
            "format": {"tip": "zip_xlsx", "antet": True, "antet_regex": "^Datum$", "ordine": "data",
                       "col_data": "Datum", "data_fmt": ["excel_serial", "%d.%m.%Y"], "ignora_randuri_fara_data": True,
                       "numere": {"princ": {"coloane": [f"Z{i}" for i in range(1, 7)]}}}}
    day, exp, members = dt.date(1955, 9, 28), [], {}
    while day < dt.date(1975, 1, 1):
        if day.weekday() in (2, 5):
            nums = sorted(int(x) + 1 for x in rng.choice(49, 6, replace=False))
            dec = f"{day.year // 10 * 10}"
            serial = (day - dt.date(1899, 12, 30)).days
            dcell = serial if day.day % 2 else day.strftime("%d.%m.%Y")
            members.setdefault(dec, []).append([dcell] + [f"{x}.0" if x % 3 == 0 else x for x in nums] + [7])
            if day.weekday() == 5 and day >= dt.date(1955, 10, 9):
                exp.append({"data": day.isoformat(), "sets": {"princ": nums}})
        day += dt.timedelta(days=1)
    bz = io.BytesIO()
    with zipfile.ZipFile(bz, "w") as z:
        for dec, rows in members.items():
            z.writestr(f"lotto_{dec}.xlsx", _xlsx_bytes([["LOTTO 6aus49 Gewinnzahlen"], ["Datum"] + [f"Z{i}" for i in range(1, 7)] + ["ZZ"]]
                                                        + list(reversed(rows)) + [[None, "Summe"]]))
    got, st = citire.citeste_joc(spec, [("de.zip", bz.getvalue())])
    res["xlsx_identice"] = [(e["data"], e["sets"]) for e in got] == [(e["data"], e["sets"]) for e in exp]
    res["xlsx_statistici"] = st
    # zip cu mai multe CSV (membri pe ani)
    spec2 = {"joc": "TEST2", "subjocuri": [["princ", 45, 6]], "start": "2000-01-01", "sfarsit": None,
             "format": {"tip": "zip_csv", "membri": "toate", "encoding": "latin-1", "delim": ";", "antet": True,
                        "ordine": "data", "col_data": "Datum", "data_fmt": ["%d.%m.%Y"],
                        "numere": {"princ": {"coloane": [f"Z{i}" for i in range(1, 7)]}}}}
    day, exp2 = dt.date(2000, 1, 1), []
    bz = io.BytesIO()
    with zipfile.ZipFile(bz, "w") as z:
        for y in range(2000, 2004):
            lines = ["Datum;" + ";".join(f"Z{i}" for i in range(1, 7))]
            for wk in range(52):
                d_ = dt.date(y, 1, 1) + dt.timedelta(days=7 * wk)
                nums = sorted(int(x) + 1 for x in rng.choice(45, 6, replace=False))
                lines.append(d_.strftime("%d.%m.%Y") + ";" + ";".join(map(str, nums)))
                exp2.append({"data": d_.isoformat(), "sets": {"princ": nums}})
            z.writestr(f"{y}.csv", "\n".join(lines) + "\n")
    got2, _ = citire.citeste_joc(spec2, [("m.zip", bz.getvalue())])
    res["multi_csv_identice"] = [(e["data"], e["sets"]) for e in got2] == [(e["data"], e["sets"]) for e in exp2]
    res["PASS"] = bool(res["xlsx_identice"] and res["multi_csv_identice"])
    return res


def _q5(tmp: Path):
    d = tmp / "q5"
    if d.exists():
        shutil.rmtree(d)
    (d / "joc" / "sigilat").mkdir(parents=True)
    (d / "joc" / "rezerva.json").write_text("{}")
    (d / "joc" / "sigilat" / "brut.csv").write_text("x")
    (d / "dev_rez.json").write_text("{\"a\": 1}")
    conf = d / "SIGILIU_CONFIRMARE_P2.json"
    r = {}

    def tries(p, **kw):
        try:
            citeste_date(p, conf=conf, dev_rez=d / "dev_rez.json")
            return "citit"
        except PermissionError:
            return "refuz"
    r["fara_sigiliu_rezerva"] = tries(d / "joc" / "rezerva.json")
    r["fara_sigiliu_brut"] = tries(d / "joc" / "sigilat" / "brut.csv")
    conf.write_text(json.dumps({"supravietuitori": [], "dev_rezultate_sha256": sha_f(d / "dev_rez.json")}))
    r["sigiliu_gol"] = tries(d / "joc" / "rezerva.json")
    conf.write_text(json.dumps({"supravietuitori": ["x"], "dev_rezultate_sha256": "0" * 64}))
    r["sigiliu_sha_gresit"] = tries(d / "joc" / "rezerva.json")
    conf.write_text(json.dumps({"supravietuitori": ["x"], "dev_rezultate_sha256": sha_f(d / "dev_rez.json")}))
    r["sigiliu_valid"] = tries(d / "joc" / "rezerva.json")
    shutil.rmtree(d)
    r["PASS"] = (r["fara_sigiliu_rezerva"] == r["fara_sigiliu_brut"] == r["sigiliu_gol"] == r["sigiliu_sha_gresit"]
                 == "refuz" and r["sigiliu_valid"] == "citit")
    return r


def cmd_teste():
    CAL.mkdir(parents=True, exist_ok=True)
    utc = utcnow()
    t0 = time.time()
    res = {"utc": utc, "code_sha256": sha_f(__file__), "citire_sha256": sha_f(HERE / "citire.py"),
           "banca_sha256": BANCA_SHA, "protocol_A_sha256": PROT_A_SHA,
           "surse_sha256": sha_f(HERE / "SURSE_P2.json"), "numpy": np.__version__, "seed": SEED,
           "date_reale_citite": False, "predictori": PREDS, "familii_calificate_P1": list(QUAL),
           "T_estimat": T_EST, "T_dev_estimat": TDEV_EST}
    res["Q5"] = _q5(CAL)
    print("Q5", res["Q5"]["PASS"], flush=True)
    res["Q4"] = _q4_synthetic(CAL)
    print("Q4", {g: r["PASS"] for g, r in res["Q4"].items()}, flush=True)
    nks = sorted({(n, k) for subs in GAMES.values() for _, n, k in subs}, key=lambda x: -math.comb(*x))
    specs = []
    gi = {g: i for i, g in enumerate(GAMES)}
    for g in GAMES:
        for r in range(100):
            specs.append((g, "uniform", None, SEED + 1000 + 1000 * gi[g] + r))
        for di, d in enumerate((0.05, 0.10, 0.20)):
            for r in range(20):
                specs.append((g, "stat", d, SEED + 20000 + 1000 * gi[g] + 100 * di + r))
    with Pool(PROCS) as pool:
        q1_async = pool.map_async(_q1_case, nks, chunksize=1)
        q2_async = pool.map_async(_q2_game, list(GAMES), chunksize=1)
        hist = pool.map(_hist_task, specs, chunksize=1)
        q1 = q1_async.get()
        q2 = dict(q2_async.get())
    minsub = min(r["_min_sub"] for _, r in hist)
    res["Q1"] = {"cazuri": q1, "e_min_sub_logE": minsub, "e_PASS": bool(minsub >= -math.log(2) - 1e-12)}
    res["Q1"]["PASS"] = bool(all(c["PASS"] for c in q1) and res["Q1"]["e_PASS"])
    print("Q1", res["Q1"]["PASS"], flush=True)
    res["Q2"] = {"jocuri": q2, "PASS": bool(all(v["PASS"] for v in q2.values()))}
    print("Q2", res["Q2"]["PASS"], flush=True)
    q3 = {}
    per_rep = {}
    for (g, kind, d, seed), r in hist:
        if kind != "uniform":
            continue
        q3.setdefault(g, {X: [] for X in PREDS})
        rep = seed - (SEED + 1000 + 1000 * gi[g])
        for X in PREDS:
            q3[g][X].append(r[X])
            per_rep.setdefault(rep, {}).setdefault(X, {})[g] = r[X]
    summ = {}
    for g in q3:
        summ[g] = {}
        for X in PREDS:
            v = np.array(q3[g][X])
            summ[g][X] = {"frac_E_ge_20": float(np.mean(v >= math.log(20))), "frac_E_ge_1500": float(np.mean(v >= math.log(1500))),
                          "q05_q50_q95_max": [float(np.quantile(v, .05)), float(np.median(v)), float(np.quantile(v, .95)), float(v.max())]}
    glob = {}
    for name, gs in (("toate_6", list(GAMES)), ("fara_MM", [g for g in GAMES if g != "US_megamillions"])):
        glob[name] = {}
        for X in PREDS:
            v = np.array([sum(per_rep[r][X][g] for g in gs) for r in sorted(per_rep)])
            glob[name][X] = {"frac_E_ge_20": float(np.mean(v >= math.log(20))),
                             "q50_max": [float(np.median(v)), float(v.max())]}
    ok3 = (all(summ[g][X]["frac_E_ge_20"] <= 0.10 for g in summ for X in PREDS)
           and all(glob[nm][X]["frac_E_ge_20"] <= 0.10 for nm in glob for X in PREDS))
    res["Q3"] = {"istorii_per_joc": 100, "per_joc": summ, "global": glob, "valori_per_replica": per_rep, "PASS": bool(ok3)}
    print("Q3", ok3, flush=True)
    rez = {}
    for (g, kind, d, seed), r in hist:
        if kind == "stat":
            rez.setdefault(g, {}).setdefault(str(d), []).append(r)
    res["rezolutie"] = {g: {d: {"frac_STAT_E_ge_1500": float(np.mean([x["STAT"] >= math.log(1500) for x in rows])),
                                "mediana_logE_STAT": float(np.median([x["STAT"] for x in rows])),
                                "frac_COMB_E_ge_1500": float(np.mean([x["COMB"] >= math.log(1500) for x in rows])),
                                "n": len(rows)} for d, rows in v.items()} for g, v in rez.items()}
    res["seconds"] = time.time() - t0
    res["PASS_Q1_Q5"] = bool(res["Q1"]["PASS"] and res["Q2"]["PASS"] and res["Q3"]["PASS"]
                             and all(r["PASS"] for g, r in res["Q4"].items() if r["PASS"] is not None)
                             and res["Q5"]["PASS"])
    res["positive_claims_allowed"] = False
    p = CAL / f"CALIFICARE_P2_{utc}.json"
    p.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    os.chmod(p, 0o444)
    print("PASS_Q1_Q5", res["PASS_Q1_Q5"], p, sha_f(p), f"{res['seconds']:.0f}s")
    return 0 if res["PASS_Q1_Q5"] else 1


# ---------------------------------------------------------------- producție
def verifica_cod():
    seal = json.loads((HERE / "SIGILIU_COD_P2.json").read_text())
    for rel, s in seal["files"].items():
        assert sha_f(ROOT / rel) == s, f"sha cod {rel}"
    assert sha_f(XI / "PROTOCOL_XI_P2.md") == PROT_A_SHA
    return seal


def _game_run(args):
    """Rulează banca pe un joc: H = dezvoltare (+ rezervă la confirmare). Întoarce LP/MG/mixturi."""
    joc, docs, need_marg = args
    subs = GAMES[joc]
    out = {"sub": {}}
    for lab, n, k in subs:
        H = [np.array([x - 1 for x in e["sets"][lab]], dtype=np.int64) for d in docs for e in d["extrageri"]]
        LP, MG = B.run_components(H, n, k, need_marg=need_marg)
        o = {"n": n, "k": k, "LP": LP, "H": H, "pred": {}}
        for X in PREDS:
            rho = B.priors(X, k, QUAL)
            lpx, lr, marg = B.mixture_seq(LP, rho, n, k, MG if need_marg else None)
            mask = rho > 0
            cum = np.log(rho[mask]) + (LP[:, mask] + math.log(math.comb(n, k))).sum(axis=0)
            wfin = np.exp(cum - B.lse(cum))
            names = [f"{f}:{p}" for (f, p), m_ in zip(B.components(k), mask) if m_]
            o["pred"][X] = {"lpx": lpx, "lr": lr,
                            "tk": [B.ticket(marg[t], k) for t in range(len(H))] if need_marg else None,
                            "ponderi_finale": {nm: float(v) for nm, v in zip(names, wfin)}}
        out["sub"][lab] = o
    return joc, out


def _jocuri_active():
    act, excl = [], {}
    for joc in GAMES:
        b = DATE / joc
        if (b / "EXCLUS.json").exists():
            excl[joc] = json.loads((b / "EXCLUS.json").read_text())["motiv"]
        elif (b / "dev.json").exists():
            act.append(joc)
        else:
            raise SystemExit(f"{joc}: nici dev.json, nici EXCLUS.json — separarea nu este completă")
    return act, excl


def cmd_dezvoltare():
    seal = verifica_cod()
    OUT.mkdir(parents=True, exist_ok=True)
    names = ("p2_dev_pas.jsonl", "P2_DEV_REZULTATE.json", "RAPORT_P2_DEV_CIFRE.md")
    for f in names:
        if (OUT / f).exists():
            print("REFUZ: producția de dezvoltare a fost deja făcută:", OUT / f)
            return 2
    utc = utcnow()
    t0 = time.time()
    act, excl = _jocuri_active()
    docs = {j: load_dev(j) for j in act}
    with Pool(min(PROCS, len(act))) as pool:
        runs = dict(pool.map(_game_run, [(j, [docs[j]], True) for j in act], chunksize=1))
    res = {"utc": utc, "code_seal_sha256": sha_f(HERE / "SIGILIU_COD_P2.json"), "code_sha256": sha_f(__file__),
           "banca_sha256": BANCA_SHA, "protocol_A_sha256": PROT_A_SHA, "surse_sha256": sha_f(HERE / "SURSE_P2.json"),
           "predictori": PREDS, "alpha": ALPHA, "jocuri_active": act, "jocuri_excluse": excl, "games": {}}
    pvals = {}
    glob = {X: 0.0 for X in PREDS}
    with open(OUT / "p2_dev_pas.jsonl", "w") as pas:
        for joc in act:
            d = docs[joc]
            T = len(d["extrageri"])
            half = T // 2
            g = {"T_dev": T, "T_total": d["T_total"], "R": d["R"], "dev_sha256": sha_f(DATE / joc / "dev.json"),
                 "prima": d["extrageri"][0]["data"] or d["extrageri"][0]["cheie"],
                 "ultima": d["extrageri"][-1]["data"] or d["extrageri"][-1]["cheie"], "sub": {}, "pred": {}}
            run = runs[joc]
            for lab, o in run["sub"].items():
                n, k = o["n"], o["k"]
                g["sub"][lab] = {"n": n, "k": k, "logE_componente":
                                 [float(x) for x in (o["LP"] + math.log(math.comb(n, k))).sum(axis=0)],
                                 "componente": [f"{f}:{p}" for f, p in B.components(k)]}
            for t in range(T):
                row = {"joc": joc, "t": t + 1, "data": d["extrageri"][t]["data"], "cheie": d["extrageri"][t]["cheie"],
                       "S": {lab: d["extrageri"][t]["sets"][lab] for lab in run["sub"]},
                       "logp_comp": {lab: [round(float(x), 12) for x in o["LP"][t]] for lab, o in run["sub"].items()},
                       "logp_pred": {X: {lab: round(float(o["pred"][X]["lpx"][t]), 12) for lab, o in run["sub"].items()} for X in PREDS},
                       "bilet": {X: {lab: [x + 1 for x in o["pred"][X]["tk"][t]] for lab, o in run["sub"].items()} for X in PREDS}}
                row["hits"] = {X: {lab: len(set(row["bilet"][X][lab]) & set(row["S"][lab])) for lab in run["sub"]} for X in PREDS}
                pas.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            for X in PREDS:
                tot = np.zeros(T)
                pr = {"sub": {}}
                for lab, o in run["sub"].items():
                    n, k = o["n"], o["k"]
                    lr = o["pred"][X]["lr"]
                    tot += lr
                    hits = np.array([len(set(o["pred"][X]["tk"][t]) & set(int(x) for x in o["H"][t])) for t in range(T)])
                    pmf = B.hyper_pmf(n, k)
                    dist = B.conv_power(pmf, T)
                    hs = int(hits.sum())
                    p3 = float(pmf[3:].sum()) if k >= 3 else None
                    n3 = int((hits >= 3).sum()) if k >= 3 else None
                    pr["sub"][lab] = {"logE": float(lr.sum()), "hits_sum": hs, "hits_null_mean": T * k * k / n,
                                      "hits_p_one_sided": float(dist[hs:].sum()), "n_hits_ge_3": n3,
                                      "n_hits_ge_3_null_mean": (T * p3 if p3 is not None else None),
                                      "n_hits_ge_3_p_one_sided": (B.binom_sf(n3, T, p3) if p3 is not None else None),
                                      "F_XEB": float(math.comb(n, k) * np.mean(np.exp(o["pred"][X]["lpx"])) - 1),
                                      "ponderi_finale": o["pred"][X]["ponderi_finale"]}
                pr["logE"] = float(tot.sum())
                pr["log10E"] = pr["logE"] / math.log(10)
                pr["logE_prima_jumatate"] = float(tot[:half].sum())
                pr["logE_a_doua_jumatate"] = float(tot[half:].sum())
                pr["p_ville"] = min(1.0, math.exp(-pr["logE"]))
                pvals[f"{joc}:{X}"] = pr["p_ville"]
                glob[X] += pr["logE"]
                g["pred"][X] = pr
            res["games"][joc] = g
    if len(act) >= 2:
        res["global"] = {X: {"logE": glob[X], "log10E": glob[X] / math.log(10), "p_ville": min(1.0, math.exp(-glob[X]))}
                         for X in PREDS}
        for X in PREDS:
            pvals[f"GLOBAL:{X}"] = res["global"][X]["p_ville"]
    rej = B.holm(pvals, ALPHA)
    M = len(pvals)
    res["holm"] = {"M": M, "p": pvals, "respinse": rej, "prag_Bonferroni_E": M / ALPHA}
    surv = sorted(k_ for k_, v in rej.items() if v)
    res["supravietuitori"] = surv
    res["verdict_dezvoltare"] = "P2_SUPRAVIETUITORI" if surv else "P2_NICIUN_SUPRAVIETUITOR"
    res["seconds"] = time.time() - t0
    res["positive_claims_allowed"] = False
    (OUT / "P2_DEV_REZULTATE.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    _cifre_dev(res)
    for f in names:
        os.chmod(OUT / f, 0o444)
    print(res["verdict_dezvoltare"], surv)
    for f in names:
        print(f, sha_f(OUT / f))
    return 0


def _cifre_dev(res):
    L = [f"# RAPORT P2 — dezvoltare, cifre (generat automat, {res['utc']})", "",
         f"Verdict pe dezvoltare: **{res['verdict_dezvoltare']}**; supraviețuitori: {res['supravietuitori'] or 'niciunul'}. "
         f"Holm α = {ALPHA}, M = {res['holm']['M']} (prag Bonferroni E ≥ {res['holm']['prag_Bonferroni_E']:.0f}). "
         "positive_claims_allowed=false.", "",
         "| Joc | Predictor | log10 E | E | p (Ville) | Holm | log E jum. 1 | log E jum. 2 |", "|---|---|---|---|---|---|---|---|"]
    for joc, g in res["games"].items():
        for X, pr in g["pred"].items():
            L.append(f"| {joc} | {X} | {pr['log10E']:.4f} | {math.exp(pr['logE']):.4g} | {pr['p_ville']:.4g} | "
                     f"{'RESPINS' if res['holm']['respinse'][f'{joc}:{X}'] else 'nu'} | "
                     f"{pr['logE_prima_jumatate']:.3f} | {pr['logE_a_doua_jumatate']:.3f} |")
    if "global" in res:
        L += ["", "| GLOBAL (produs pe jocuri) | log10 E | E | p | Holm |", "|---|---|---|---|---|"]
        for X, v in res["global"].items():
            L.append(f"| {X} | {v['log10E']:.4f} | {math.exp(v['logE']):.4g} | {v['p_ville']:.4g} | "
                     f"{'RESPINS' if res['holm']['respinse'][f'GLOBAL:{X}'] else 'nu'} |")
    L += ["", "## Nimeriri ale biletului de vârf (descriptiv)", "",
          "| Joc | Sub | Predictor | nimeriri | nul | p unilateral | ≥3 | nul | p | F_XEB |", "|---|---|---|---|---|---|---|---|---|---|"]
    for joc, g in res["games"].items():
        for X, pr in g["pred"].items():
            for lab, s in pr["sub"].items():
                n3 = "—" if s["n_hits_ge_3"] is None else s["n_hits_ge_3"]
                n3m = "—" if s["n_hits_ge_3_null_mean"] is None else f"{s['n_hits_ge_3_null_mean']:.1f}"
                n3p = "—" if s["n_hits_ge_3_p_one_sided"] is None else f"{s['n_hits_ge_3_p_one_sided']:.3g}"
                L.append(f"| {joc} | {lab} | {X} | {s['hits_sum']} | {s['hits_null_mean']:.1f} | {s['hits_p_one_sided']:.3g} | "
                         f"{n3} | {n3m} | {n3p} | {s['F_XEB']:.5f} |")
    L += [""]
    for joc, g in res["games"].items():
        L.append(f"- {joc}: dezvoltare T = {g['T_dev']} ({g['prima']} … {g['ultima']}), total {g['T_total']}, rezervă {g['R']} (sigilată).")
    for joc, m in res["jocuri_excluse"].items():
        L.append(f"- {joc}: EXCLUS — {m}")
    (OUT / "RAPORT_P2_DEV_CIFRE.md").write_text("\n".join(L) + "\n")


def cmd_confirmare():
    verifica_cod()
    if not CONF.exists():
        print("REFUZ: lipsește SIGILIU_CONFIRMARE_P2.json")
        return 2
    s = json.loads(CONF.read_text())
    surv = s["supravietuitori"]
    if not surv:
        print("REFUZ: niciun supraviețuitor; rezerva rămâne sigilată")
        return 2
    for f in ("P2_REZ_REZULTATE.json", "RAPORT_P2_REZ_CIFRE.md"):
        if (OUT / f).exists():
            print("REFUZ: confirmarea a fost deja făcută")
            return 2
    dev_res = json.loads((OUT / "P2_DEV_REZULTATE.json").read_text())
    act = dev_res["jocuri_active"]
    need = sorted({k_.split(":")[0] for k_ in surv if not k_.startswith("GLOBAL:")} |
                  (set(act) if any(k_.startswith("GLOBAL:") for k_ in surv) else set()))
    docs = {}
    for j in need:
        dev = load_dev(j)
        rb = citeste_date(DATE / j / "rezerva.json")
        assert sha_b(rb) == dev["rezerva_sha256"], f"sha rezerva {j}"
        docs[j] = (dev, json.loads(rb))
    utc = utcnow()
    with Pool(min(PROCS, len(need))) as pool:
        runs = dict(pool.map(_game_run, [(j, list(docs[j]), False) for j in need], chunksize=1))
    res = {"utc": utc, "supravietuitori": surv, "games": {}, "alpha": ALPHA}
    logE_r = {}
    for j in need:
        Td, R = len(docs[j][0]["extrageri"]), len(docs[j][1]["extrageri"])
        res["games"][j] = {"T_dev": Td, "R": R, "pred": {}}
        for X in PREDS:
            lr = sum(o["pred"][X]["lr"] for o in runs[j]["sub"].values())
            logE_r[(j, X)] = float(lr[Td:].sum())
            res["games"][j]["pred"][X] = {"logE_rezerva": logE_r[(j, X)]}
    pv = {}
    for k_ in surv:
        j, X = k_.split(":")
        le = sum(logE_r[(g, X)] for g in act) if j == "GLOBAL" else logE_r[(j, X)]
        pv[k_] = min(1.0, math.exp(-le))
        res.setdefault("logE_rezerva_supravietuitori", {})[k_] = le
    rej = B.holm(pv, ALPHA)
    res["holm"] = {"M": len(pv), "p": pv, "respinse": rej}
    conf = sorted(k_ for k_, v in rej.items() if v)
    res["confirmati"] = conf
    res["verdict"] = "P2_CONFIRMAT_ORB" if conf else "P2_NECONFIRMAT"
    res["positive_claims_allowed"] = False
    (OUT / "P2_REZ_REZULTATE.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    (OUT / "RAPORT_P2_REZ_CIFRE.md").write_text(
        f"# RAPORT P2 — rezervă (generat automat, {utc})\n\nVerdict: **{res['verdict']}**; confirmați: {conf or 'niciunul'}.\n\n"
        + "\n".join(f"- {k_}: log E rezervă = {res['logE_rezerva_supravietuitori'][k_]:.4f}, p = {pv[k_]:.4g}" for k_ in surv) + "\n")
    for f in ("P2_REZ_REZULTATE.json", "RAPORT_P2_REZ_CIFRE.md"):
        os.chmod(OUT / f, 0o444)
    print(res["verdict"], conf)
    return 0


def main(argv):
    cmds = {"teste": cmd_teste, "dezvoltare": cmd_dezvoltare, "confirmare": cmd_confirmare}
    if len(argv) < 2 or argv[1] not in cmds:
        print(__doc__)
        return 2
    return cmds[argv[1]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
