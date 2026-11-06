#!/usr/bin/env python3
"""TU4-JU (S13): verificator SEPARAT al judecătorului (protocol tu4/PROTOCOL_TU4_JU.md §9).

Numai biblioteca standard + NumPy; fără torch și fără niciun import din tu4/. Recalculează independent lanțul
emisiilor, admisibilitatea, regula de potrivire, factorii e (identitățile lui Newton), procesele E și stările,
lanțul decontărilor, oglinda SSD (matricea MMAP), unitățile instalate și calibrarea nulă.

    /usr/bin/python3 -B tu4/verifica_ju.py                      (scrie tu4/rezultate/JU/VERIFICARE_JU_<UTC>.json)
    /usr/bin/python3 -B tu4/verifica_ju.py --radacina DIR --acum T --fara-scriere [--ssd DIR] [--calibrare F]
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import math
import os
import stat
import struct
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

TU4 = Path(__file__).resolve().parent
QLR = TU4.parent
TZ = ZoneInfo("Europe/Bucharest")
GAMES = {"649": (49, 6, False), "540": (40, 6, False), "joker": (45, 5, True)}
GIDX = {"649": 0, "540": 1, "joker": 2}
MODELS = ("H1", "H3")
STREAMS = [f"{m}_{g}" for m in MODELS for g in GAMES]
LN600, LN20, RET = math.log(600.0), math.log(20.0), -10.0
UNITS = {"ql649-tu4-judecator.service": "tu4/systemd/ql649-tu4-judecator.service",
         "loto-actualizare.service.d/tu4-judecator.conf": "tu4/systemd/tu4-judecator.conf"}
FORBIDDEN_IMPORTS = ("ip_core", "emite", "ip_run", "frontiera")


def H(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def HF(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def T(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def local_utc(d: str, hh: int, mm: int) -> dt.datetime:
    y, m, dd = map(int, d.split("-"))
    return dt.datetime(y, m, dd, hh, mm, tzinfo=TZ).astimezone(dt.timezone.utc)


class Rep:
    def __init__(self):
        self.checks = []

    def add(self, cid, status, detail=""):
        self.checks.append({"id": cid, "status": status, "detail": str(detail)[:500]})

    def ok(self, cid, cond, detail=""):
        self.add(cid, "PASS" if cond else "FAIL", detail)


# ---------------------------------------------------------------- factorul e: identitățile lui Newton (independent)
def ln_e_newton(logw, chosen, k, active) -> float:
    if not active:
        return 0.0
    n = len(logw)
    w = [math.exp(x) for x in logw]
    p = [None] + [math.fsum(x ** j for x in w) for j in range(1, k + 1)]
    e = [1.0]
    for m in range(1, k + 1):
        e.append(math.fsum(((-1) ** (j - 1)) * e[m - j] * p[j] for j in range(1, m + 1)) / m)
    lc = math.log(math.comb(n, k))
    return math.fsum(logw[i - 1] for i in chosen) - math.log(e[k]) + lc


# ---------------------------------------------------------------- mașina de stări (reimplementare)
def step(st, status, le, D, emitted, decided):
    st = dict(st)
    cnt = False
    if st["state"] == "EXPLORARE" and status == "DECONTAT":
        st["lnE"] += le
        cnt = True
        if st["lnE"] >= LN600:
            st.update(state="CONFIRMARE", lnE_conf=0.0, conf_start_utc=decided, conf_start_date=D)
        elif st["lnE"] < RET:
            st["state"] = "RETRAS"
    elif st["state"] == "CONFIRMARE" and status == "DECONTAT" and D > st["conf_start_date"] \
            and T(emitted) > T(st["conf_start_utc"]):
        st["lnE_conf"] += le
        cnt = True
        if st["lnE_conf"] >= LN20:
            st["state"] = "CONFIRMAT"
        elif st["lnE_conf"] < RET:
            st["state"] = "RETRAS"
    return st, cnt


def st0():
    return {"state": "EXPLORARE", "lnE": 0.0, "lnE_conf": 0.0, "conf_start_utc": None, "conf_start_date": None}


def adm(em, test_mode, em_code_seal_bytes):
    r = {}
    try:
        e, c, d = T(em["emitted_utc"]), T(em["cutoff_utc"]), T(em["draw_utc"])
        r["A1_cronologie"] = e < c < d
        D = em["target_date"]
        r["A2_calendar"] = (dt.date.fromisoformat(D).weekday() in (3, 6) and d == local_utc(D, 18, 30)
                            and c == local_utc(D, 16, 0))
    except Exception:
        r["A1_cronologie"] = r["A2_calendar"] = False
    r["A3_metadate"] = (em.get("protocol") == "TU4-EM" and em.get("target_kind") == "regular"
                        and em.get("positive_claims_allowed") is False and em.get("test_mode") is bool(test_mode))
    cs = json.loads(em_code_seal_bytes)
    code = em.get("code", {})
    r["A4_cod"] = (code.get("emite_sha256") == cs["files"]["tu4/emite.py"]
                   and code.get("ip_core_sha256") == "ab3e1de93d8e5ae537a8c80599905aaa19cc103602f9b18f4b7f7f6f8a48c302"
                   and code.get("code_seal_sha256") == H(em_code_seal_bytes)
                   and code.get("protocol_seal_sha256") == H((TU4 / "SIGILIU_TU4_EM.json").read_bytes()))
    r["A5_arhiva_anterioara"] = str(em.get("archive", {}).get("last_date", "9999")) < str(em.get("target_date", ""))
    n, k, ball = GAMES.get(em.get("game"), (None, None, None))
    ok = n is not None

    def fin(v, L):
        return isinstance(v, list) and len(v) == L and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                         and math.isfinite(x) for x in v)
    if ok:
        for m in MODELS:
            b = em.get("models", {}).get(m, {})
            ok = ok and fin(b.get("logw"), n) and isinstance(b.get("bet_active"), bool)
            if ball:
                bb = b.get("ball") or {}
                ok = ok and fin(bb.get("logw"), 20) and isinstance(bb.get("bet_active"), bool)
    r["A6_blocuri"] = bool(ok)
    return r


def live_current(root: Path):
    live = root / "tu3" / "date" / "live"
    cur = json.loads((live / "CURRENT_LIVE.json").read_bytes())
    vdir = live / cur["version_dir"]
    man = json.loads((vdir / "MANIFEST_LIVE.json").read_bytes())
    out = {}
    for g in GAMES:
        b = (vdir / man["games"][g]["file"]).read_bytes()
        assert H(b) == man["games"][g]["sha256"] == cur["games"][g]["sha256"], f"sha LIVE {g}"
        out[g] = [json.loads(x) for x in b.decode().splitlines() if x.strip()]
    return out


def canon(r):
    return {k: r.get(k) for k in ("game", "draw_date", "draw_kind", "numbers", "joker")}


def rows_bytes(docs_in_order):
    st = {s: st0() for s in STREAMS}
    out = []
    for i, doc in docs_in_order:
        st.update(doc["streams_after"])
        b = struct.pack("<qqqq", i, int(doc["target_date"].replace("-", "")), GIDX[doc["game"]],
                        {"DECONTAT": 0, "VOID": 1, "RESPINS": 2}[doc["status"]])
        b += struct.pack("<2d", *[doc["models"][m]["ln_e"] for m in MODELS])
        b += struct.pack("<6d", *[st[s]["lnE"] for s in STREAMS]) + struct.pack("<6d", *[st[s]["lnE_conf"] for s in STREAMS])
        b += bytes(struct.pack("<6b", *[{"EXPLORARE": 0, "CONFIRMARE": 1, "CONFIRMAT": 2, "RETRAS": 3}[st[s]["state"]]
                                         for s in STREAMS]))
        out.append(b.ljust(160, b"\0"))
    hdr = (b"QL649JU1" + struct.pack("<IIQ", 1, 160, len(out)) + ",".join(STREAMS).encode()).ljust(512, b"\0")
    return hdr + b"".join(out)


def q999_ratio(R, p):
    """Cuantila 0.999 binomială prin recurența raportului pmf (metodă diferită de calibrare)."""
    pmf = (1 - p) ** R
    cdf = pmf
    x = 0
    while cdf < 0.999 and x < R:
        pmf *= (R - x) / (x + 1) * p / (1 - p)
        x += 1
        cdf += pmf
    return x


def first_idx(mask):
    return np.where(mask.any(1), mask.argmax(1), mask.shape[1])


def verify(root: Path, now: dt.datetime, test_mode: bool, ssd: Path | None, calib: Path | None) -> dict:
    rep = Rep()
    trib = root / "tu4" / "tribunal"
    em_seal_sha = H((TU4 / "SIGILIU_TU4_EM.json").read_bytes())
    em_cs = (TU4 / "SIGILIU_TU4_EM_COD.json").read_bytes()
    # V1 sigiliile
    seal = json.loads((TU4 / "SIGILIU_TU4_JU.json").read_bytes())
    ju_seal_sha = H((TU4 / "SIGILIU_TU4_JU.json").read_bytes())
    rep.ok("V1_protocol", HF(TU4 / "PROTOCOL_TU4_JU.md") == seal["document"]["sha256"]
           and ju_seal_sha == "5dcc0a4252acf9d504b5bbc11e13816595638839628d53349fd9c08082533093")
    drift = [f for f, h in seal["frozen_hashes"].items() if HF(QLR / f) != h]
    rep.ok("V1_frozen", not drift, drift)
    cs_p = TU4 / "SIGILIU_TU4_JU_COD.json"
    if cs_p.exists():
        cs = json.loads(cs_p.read_bytes())
        d2 = [f for f, h in cs["files"].items() if HF(QLR / f) != h]
        rep.ok("V1_code_seal", not d2 and cs["protocol_seal"]["sha256"] == ju_seal_sha, d2)
    else:
        rep.add("V1_code_seal", "UNKNOWN" if test_mode else "FAIL", "SIGILIU_TU4_JU_COD.json lipsește")
    # V2 lanțul emisiilor
    ems = {}
    try:
        lines = (trib / "LANT.jsonl").read_bytes().splitlines() if (trib / "LANT.jsonl").exists() else []
        prev, seen = em_seal_sha, set()
        for i, ln in enumerate(lines):
            r = json.loads(ln)
            assert r["i"] == i and r["prev_line_sha256"] == prev, f"linia {i}"
            prev = H(ln)
            b = (trib / r["file"]).read_bytes()
            assert H(b) == r["sha256"], f"sha {r['file']}"
            em = json.loads(b)
            assert em["emitted_utc"] == r["emitted_utc"] and em["game"] == r["game"] and em["target_date"] == r["target_date"]
            assert (r["game"], r["target_date"]) not in seen
            seen.add((r["game"], r["target_date"]))
            ems[(r["game"], r["target_date"])] = {"em": em, "sha": r["sha256"], "i": i, "file": r["file"]}
        for g in GAMES:
            pv = em_seal_sha
            lst = sorted((k for k in ems if k[0] == g), key=lambda k: k[1])
            for j, key in enumerate(lst):
                ch = ems[key]["em"]["chain"]
                assert ch["index"] == j and ch["prev_sha256"] == pv, f"lanț {key}"
                pv = ems[key]["sha"]
            d = trib / "emisii" / g
            files = {str(p.relative_to(trib)) for p in d.glob("*.json")} if d.exists() else set()
            assert files == {ems[k]["file"] for k in lst}, f"orfani {g}"
        rep.ok("V2_lant_emisii", True, f"{len(lines)} emisii")
    except Exception as exc:
        rep.ok("V2_lant_emisii", False, repr(exc))
    # V5 lanțul decontărilor
    decs = []
    try:
        dl = (trib / "DECONTARI.jsonl").read_bytes().splitlines() if (trib / "DECONTARI.jsonl").exists() else []
        prev, seen = ju_seal_sha, set()
        for i, ln in enumerate(dl):
            r = json.loads(ln)
            assert r["i"] == i and r["prev_line_sha256"] == prev, f"linia {i}"
            prev = H(ln)
            b = (trib / r["file"]).read_bytes()
            assert H(b) == r["sha256"]
            assert (r["game"], r["target_date"]) not in seen
            seen.add((r["game"], r["target_date"]))
            doc = json.loads(b)
            assert doc["game"] == r["game"] and doc["target_date"] == r["target_date"] and doc["status"] == r["status"]
            decs.append((i, r, doc))
        files = {str(p.relative_to(trib)) for p in (trib / "decontari").glob("*/*.json")} if (trib / "decontari").exists() else set()
        assert files == {r["file"] for _, r, _ in decs}, "decontări fără linie"
        rep.ok("V5_lant_decontari", True, f"{len(decs)} decontări")
    except Exception as exc:
        rep.ok("V5_lant_decontari", False, repr(exc))
    # V3 + V4
    v3, v4 = [], []
    try:
        live = live_current(root)
    except Exception as exc:
        live = None
        v3.append("LIVE invalid: " + repr(exc))
    st = {s: st0() for s in STREAMS}
    last_date = {g: "" for g in GAMES}
    for i, r, doc in decs:
        key = (doc["game"], doc["target_date"])
        g = doc["game"]
        n, k, ball = GAMES[g]
        e = ems.get(key)
        if e is None or doc["emission"]["sha256"] != e["sha"]:
            v3.append(f"{key}: emisie necorespunzătoare")
            continue
        em = e["em"]
        if doc["target_date"] <= last_date[g]:
            v4.append(f"{key}: ordine necronologică")
        last_date[g] = doc["target_date"]
        if T(doc["decided_utc"]) < T(em["draw_utc"]):
            v3.append(f"{key}: decis înainte de extragere")
        a = adm(em, test_mode, em_cs)
        if a != doc["admissibility"]:
            v3.append(f"{key}: admisibilitate diferită")
        if doc["status"] == "RESPINS":
            if all(a.values()):
                v3.append(f"{key}: RESPINS fără motiv")
        elif not all(a.values()):
            v3.append(f"{key}: emisie inadmisibilă decontată")
        if live is not None:
            R = [x for x in live[g] if x.get("draw_date") == doc["target_date"] and x.get("draw_kind") == "regular"]
            if doc["status"] == "DECONTAT":
                rev = (root / "tu4" / "incidente" / f"JU_REVIZIE_{g}_{doc['target_date']}.json").exists()
                if not ((len(R) == 1 and canon(R[0]) == doc["record"]["canonical"]) or rev):
                    v3.append(f"{key}: înregistrarea nu corespunde arhivei curente")
                c = doc["record"]["canonical"]
                if doc["draw"]["numbers"] != c["numbers"] or (ball and doc["draw"]["joker"] != c["joker"]):
                    v3.append(f"{key}: numerele diferă de înregistrare")
            elif doc["status"] == "VOID":
                if not ((doc["n_regular_records"] or 0) >= 2
                        or T(doc["decided_utc"]) >= T(em["draw_utc"]) + dt.timedelta(days=14)):
                    v3.append(f"{key}: VOID nejustificat")
        for m in MODELS:
            mb = doc["models"][m]
            blk = em["models"][m]
            if doc["status"] == "DECONTAT":
                lm = ln_e_newton(blk["logw"], doc["draw"]["numbers"], k, blk["bet_active"])
                lb = ln_e_newton(blk["ball"]["logw"], [doc["draw"]["joker"]], 1, blk["ball"]["bet_active"]) if ball else 0.0
            else:
                lm, lb = 0.0, 0.0
            if abs(lm - mb["ln_e_main"]) > 1e-10 or abs(lb - (mb["ln_e_ball"] or 0.0)) > 1e-10 \
                    or abs(mb["ln_e"] - (mb["ln_e_main"] + (mb["ln_e_ball"] or 0.0))) > 1e-15:
                v3.append(f"{key} {m}: ln e diferit")
            if not blk["bet_active"] and mb["ln_e_main"] != 0.0:
                v3.append(f"{key} {m}: λ=0 dar ln e ≠ 0")
            s = f"{m}_{g}"
            if doc["streams_before"][s] != st[s]:
                v4.append(f"{key} {s}: stare anterioară diferită")
            new, cnt = step(st[s], doc["status"], mb["ln_e"], doc["target_date"], em["emitted_utc"], doc["decided_utc"])
            if new["state"] != doc["streams_after"][s]["state"] or abs(new["lnE"] - doc["streams_after"][s]["lnE"]) > 1e-12 \
                    or abs(new["lnE_conf"] - doc["streams_after"][s]["lnE_conf"]) > 1e-12 or cnt != mb["counted"]:
                v4.append(f"{key} {s}: stare ulterioară diferită")
            st[s] = doc["streams_after"][s]
        if doc.get("positive_claims_allowed") is not False:
            v3.append(f"{key}: positive_claims_allowed")
    rep.ok("V3_decontari", not v3, v3 or f"{len(decs)} verificate")
    rep.ok("V4_stari", not v4, v4 or {s: (st[s]["state"], round(st[s]["lnE"], 6)) for s in STREAMS})
    # V6 modurile
    bad = []
    for p in [trib / "DECONTARI.jsonl", trib / "JUDECATOR_RULARI.jsonl"] + [trib / r["file"] for _, r, _ in decs]:
        if p.exists() and stat.S_IMODE(p.stat().st_mode) != 0o444:
            bad.append(str(p))
    if not test_mode:
        for f in ("tu4/judecator.py", "tu4/calibrare_ju.py", "tu4/verifica_ju.py", "tu4/PROTOCOL_TU4_JU.md",
                  "tu4/SIGILIU_TU4_JU.json", "tu4/SIGILIU_TU4_JU_COD.json"):
            if stat.S_IMODE((QLR / f).stat().st_mode) & 0o222:
                bad.append(f)
    rep.ok("V6_moduri", not bad, bad)
    # V7 nicio emisie restantă
    done = {(r["game"], r["target_date"]) for _, r, _ in decs}
    late = [k for k, e in ems.items() if k not in done and now >= T(e["em"]["draw_utc"]) + dt.timedelta(days=14)]
    rep.ok("V7_restante", not late, late or [f"{k[0]} {k[1]}" for k in ems if k not in done])
    # V8 oglinda SSD
    if ssd is None or not ssd.parent.exists():
        rep.add("V8_ssd", "UNKNOWN", "SSD nemontat / neindicat")
    else:
        prob = []
        jp = ssd / "JURNAL_DECONTARI.jsonl"
        jsh = {json.loads(x)["sha256"] for x in jp.read_text().splitlines() if x.strip()} if jp.exists() else set()
        for _, r, _ in decs:
            c = ssd / r["file"]
            if not c.exists() or c.read_bytes() != (trib / r["file"]).read_bytes():
                prob.append("copie " + r["file"])
            if r["sha256"] not in jsh:
                prob.append("jurnal " + r["file"])
        mp = ssd / "SCORURI_JU.mmap"
        want = rows_bytes([(i, doc) for i, _, doc in decs])
        if mp.exists():
            if mp.read_bytes() != want:
                prob.append("matricea SCORURI_JU.mmap diferă de recalculare")
        elif decs:
            prob.append("matricea SCORURI_JU.mmap lipsește deși există decontări")
        em_ssd = ssd.parent / "QL649_TU4_EM"
        if em_ssd.exists():
            for key, e in ems.items():
                c = em_ssd / e["file"]
                if c.exists() and H(c.read_bytes()) != e["sha"]:
                    prob.append("emisie SSD alterată " + e["file"])
        rep.ok("V8_ssd", not prob, prob or f"matrice {len(decs)} rânduri; emisii SSD neatinse")
    # V9 unitățile
    if test_mode:
        rep.add("V9_unitati", "UNKNOWN", "mod test")
    else:
        ud = Path.home() / ".config" / "systemd" / "user"
        cs = json.loads(cs_p.read_bytes()) if cs_p.exists() else {"files": {}}
        prob = [u for u, src in UNITS.items() if not (ud / u).exists()
                or (ud / u).read_bytes() != (QLR / src).read_bytes() or cs["files"].get(src) != HF(QLR / src)]
        rep.ok("V9_unitati", not prob, prob)
    # V10 calibrarea
    if calib is None or not calib.exists():
        rep.add("V10_calibrare", "UNKNOWN" if test_mode else "FAIL", "CALIBRARE_JU.json lipsește")
    else:
        c = json.loads(calib.read_bytes())
        R = c["R"]
        qs, qf, qc = q999_ratio(R, 1 / 600), q999_ratio(R, 0.01), q999_ratio(R, 0.05)
        prob = []
        if [qs, qf, qc] != [c["binomial_q999"]["p_1_600"], c["binomial_q999"]["p_0.01"], c["binomial_q999"]["p_0.05"]]:
            prob.append(f"cuantile {qs},{qf},{qc}")
        g = c["gates"]
        okc = (all(v["hits"] <= qs for v in g["C1_per_stream_ln600"].values()) and g["C2_family_ln600"]["hits"] <= qf
               and all(v["hits"] <= qc for v in g["C3_per_stream_ln20"].values())
               and all(abs(v["mean_e"] - 1) <= v["tol"] for v in g["C4_martingale"].values())
               and all(v["max_abs_diff"] <= 1e-9 for v in g["C5_gpu_eq_cpu"].values()))
        if okc != (c["verdict"] == "CALIBRARE_JU_PASS"):
            prob.append("verdict inconsistent")
        if R != 10000 or c["seed"] != 2026102713 or c["H"] != 520:
            prob.append("parametri diferiți de protocol")
        mm = c.get("memmap")
        if mm and Path(mm["path"]).exists():
            if HF(mm["path"]) != mm["sha256"]:
                prob.append("sha memmap")
            else:
                L = np.memmap(mm["path"], dtype=np.float32, mode="r", shape=tuple(mm["shape"]))
                fam = np.zeros(R, bool)
                for si, s in enumerate(STREAMS):
                    Ls = np.asarray(L[si], dtype=np.float64)
                    fr = first_idx(Ls < RET)
                    h6 = first_idx(Ls >= LN600) < fr
                    h2 = first_idx(Ls >= LN20) < fr
                    fam |= h6
                    s_ = c["streams"][s]
                    if abs(int(h6.sum()) - s_["hits_ln600"]) > 2 or abs(int(h2.sum()) - s_["hits_ln20"]) > max(2, s_["hits_ln20"] // 100) \
                            or abs(int((fr < Ls.shape[1]).sum()) - s_["retired_by_H"]) > max(2, s_["retired_by_H"] // 100):
                        prob.append(f"rezumat memmap {s}")
                if abs(int(fam.sum()) - c["family_hits_ln600"]) > 2:
                    prob.append("familie memmap")
                del L
        rep.ok("V10_calibrare", not prob and c["verdict"] == "CALIBRARE_JU_PASS", prob or c["verdict"])
    # V11 AST
    src = (TU4 / "judecator.py").read_text()
    tree = ast.parse(src)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    badn = [x for x in names if x.split(".")[0] in FORBIDDEN_IMPORTS or "popular" in x.lower()]
    badid = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and "popular" in n.id.lower()})
    rep.ok("V11_ast", not badn and not badid, badn + badid)
    # verdict
    allow_unknown = {"V8_ssd"} | ({"V1_code_seal", "V9_unitati", "V10_calibrare"} if test_mode else set())
    fails = [c for c in rep.checks if c["status"] == "FAIL" or (c["status"] == "UNKNOWN" and c["id"] not in allow_unknown)]
    return {"protocol": "TU4-JU", "kind": "verification", "verifier_sha256": HF(__file__), "root": str(root),
            "test_mode": test_mode, "now": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "verdict": "VERIFICARE_JU_PASS" if not fails else "VERIFICARE_JU_FAIL",
            "n_checks": len(rep.checks), "n_pass": sum(c["status"] == "PASS" for c in rep.checks),
            "n_fail": sum(c["status"] == "FAIL" for c in rep.checks),
            "n_unknown": sum(c["status"] == "UNKNOWN" for c in rep.checks),
            "checks": rep.checks, "positive_claims_allowed": False}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--radacina", type=Path, default=None)
    ap.add_argument("--acum", default=None)
    ap.add_argument("--ssd", type=Path, default=None)
    ap.add_argument("--calibrare", type=Path, default=None)
    ap.add_argument("--fara-scriere", action="store_true")
    a = ap.parse_args(argv)
    test_mode = a.radacina is not None
    root = a.radacina.resolve() if test_mode else QLR
    now = T(a.acum) if a.acum else dt.datetime.now(dt.timezone.utc)
    ssd = a.ssd if a.ssd is not None else (None if test_mode else Path("./ssd_data/QL649_TU4_JU"))
    calib = a.calibrare if a.calibrare is not None else (None if test_mode else TU4 / "rezultate" / "JU" / "CALIBRARE_JU.json")
    res = verify(root, now, test_mode, ssd, calib)
    if not a.fara_scriere and not test_mode:
        out = TU4 / "rezultate" / "JU" / f"VERIFICARE_JU_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        fd = os.open(out, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
        os.write(fd, (json.dumps(res, indent=1, ensure_ascii=False) + "\n").encode())
        os.fsync(fd)
        os.close(fd)
        print(out)
    print(json.dumps({k: res[k] for k in ("verdict", "n_checks", "n_pass", "n_fail", "n_unknown")}))
    if res["verdict"] != "VERIFICARE_JU_PASS":
        print(json.dumps([c for c in res["checks"] if c["status"] != "PASS"], ensure_ascii=False, indent=1))
    return 0 if res["verdict"] == "VERIFICARE_JU_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
