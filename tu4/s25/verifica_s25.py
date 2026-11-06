"""Verificatorul S25 (protocol tu4/PROTOCOL_QUANTUM_S25.md §2–§4). Scris DUPĂ sigiliu; scrie numai fișiere noi
<CRIT>_VERIFICARE_<UTC>.json în tu4/rezultate/S25/. Nu scrie în tribunal, nu rescrie verificatoarele vechi.

Utilizare:
  verifica_s25.py a0                               A0: integritatea (sigiliu, înghețate, 0444, prefixe, scutul LANT)
  verifica_s25.py a1                               A1: fixture-uri sintetice F01–F15 (director temporar)
  verifica_s25.py v0l <log>                        V0L: V0 amendat (drift structural LANT + lant_scut), 29 verificări
  verifica_s25.py q7l <log> [--incidente-s25 S25_01,...]   Q7L: Q7 amendat (V0L în locul V0), 11 verificări
  verifica_s25.py scut                             scutul LANT pe tribunalul real (numai afișare, fără fișier)
V0L refolosește EXACT codul înghețat verifica_s23.py v0 pentru cele 27 de verificări moștenite (captură, fără fișier
V0 nou) și înlocuiește numai drift_14_goale. Calcul clasic; positive_claims_allowed=false.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True        # niciun __pycache__ nou în directoarele S23/S24 la import

QL = Path(".")
RC = Path("./rust_core")
OUT = QL / "tu4/rezultate/S25"
SEAL_PATH = QL / "tu4/SIGILIU_TU4_S25.json"
SEAL_SHA = "195bf91f9c897ee59300b981212db650dbffc110bd9da994a4a9fbd3c284ef1f"
SEAL = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
LS = SEAL["lant"]
TRIB = QL / "tu4/tribunal"
MAN22 = QL / "tu4/rezultate/S22/MANIFEST_RUST_CORE_20261028T032900Z.json"
LANT_REL = "tu4/tribunal/LANT.jsonl"
OLD_VERIFIERS = ("tu4/rezultate/S23/verifica_s23.py", "tu4/s24/verifica_s24.py")
B0_LOG = QL / SEAL["baseline_B0"]["log"]

sys.path.insert(0, str(QL / "tu4/rezultate/S23"))
sys.path.insert(0, str(QL / "tu4/s24"))
import verifica_s23 as V23  # noqa: E402  (cod înghețat, 0444; numai citit)
import raport_decontare_s24 as RD  # noqa: E402


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def shab(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def path_of(rel: str) -> Path:
    if rel.startswith("~"):
        return Path(rel).expanduser()
    if rel.startswith("/"):
        return Path(rel)
    return RC.parent / rel if rel.startswith("rust_core/") else QL / rel


def run(cmd, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


class Report:
    def __init__(self, crit: str):
        self.crit, self.checks = crit, []

    def check(self, name: str, ok, detail=None):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def finish(self, extra: dict | None = None) -> int:
        n_pass = sum(c["ok"] for c in self.checks)
        verdict = "PASS" if self.checks and n_pass == len(self.checks) else "FAIL"
        stamp = utc_now()
        out = OUT / f"{self.crit}_VERIFICARE_{stamp}.json"
        while out.exists():          # lecția S23_02
            time.sleep(1.0)
            stamp = utc_now()
            out = OUT / f"{self.crit}_VERIFICARE_{stamp}.json"
        doc = {"criteriu": self.crit, "verdict": verdict, "n_checks": len(self.checks), "n_pass": n_pass,
               "run_utc": stamp, "protocol": "TU4-S25", "checks": self.checks, "positive_claims_allowed": False}
        if extra:
            doc.update(extra)
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out.chmod(0o444)
        print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "n_checks", "n_pass")}, indent=2, ensure_ascii=False))
        for c in self.checks:
            if not c["ok"]:
                print("FAIL", self.crit, c["name"], json.dumps(c["detail"], ensure_ascii=False)[:600])
        print(out, sha(out))
        return 0 if verdict == "PASS" else 1


# ------------------------------------------------------------------------------------------------- scutul LANT §2
UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def scut_lant(trib: Path, check_mode: bool = True) -> list[str]:
    """Lista abaterilor (goală = PASS). Fiecare abatere începe cu eticheta condiției (S1…S6)."""
    err: list[str] = []
    f = trib / "LANT.jsonl"
    if not f.exists():
        return ["S4_lipsa fișierul LANT.jsonl lipsește"]
    b = f.read_bytes()
    ls = b.splitlines(keepends=True)
    p20 = LS["LANT_PREFIX_S20"]
    pre = b"".join(ls[: p20["lines"]])
    if len(ls) < p20["lines"] or len(pre) != p20["bytes"] or shab(pre) != p20["sha256"]:
        err.append(f"S1 prefixul S20 diferit (linii {len(ls)}, octeți prefix {len(pre)})")
    for sf, d in LS["s16_s19_frozen"].items():
        if shab(b"".join(ls[: d["prefix_lines"]])) != d["sha256"]:
            err.append(f"S2 {sf}: primele {d['prefix_lines']} linii nu au sha-ul înghețat")
    snap = LS["snapshot_S25"]
    if len(b) < snap["bytes"] or shab(b[: snap["bytes"]]) != snap["sha256"]:
        err.append(f"S3 instantaneul S25 nu e prefix (octeți {len(b)} < {snap['bytes']} sau sha diferit)")
    if not b.endswith(b"\n"):
        err.append("S4_newline fișierul nu se termină cu \\n")
    keys = set(LS["keys"])
    prev_line, prev_utc, seen = None, "", set()
    for i, raw in enumerate(b.split(b"\n")[:-1] if b.endswith(b"\n") else b.split(b"\n")):
        if not raw:
            err.append(f"S4_gol linia {i} goală")
            prev_line = raw
            continue
        try:
            o = json.loads(raw.decode("utf-8"))
            assert isinstance(o, dict)
        except Exception as e:  # noqa: BLE001
            err.append(f"S4_json linia {i}: {e}")
            prev_line = raw
            continue
        if set(o) != keys:
            err.append(f"S5_keys linia {i}: {sorted(set(o) ^ keys)}")
        if json.dumps(o, ensure_ascii=False, sort_keys=True).encode() != raw:
            err.append(f"S5_canon linia {i}: serializare necanonică")
        if o.get("i") != i:
            err.append(f"S5_i linia {i}: i={o.get('i')}")
        want_prev = LS["first_prev_line_sha256"] if i == 0 else shab(prev_line or b"")
        if o.get("prev_line_sha256") != want_prev:
            err.append(f"S5_prev linia {i}: lanțul prev_line_sha256 rupt")
        g, td = o.get("game"), o.get("target_date")
        if g not in LS["games"]:
            err.append(f"S5_game linia {i}: {g!r}")
        if not (isinstance(td, str) and DATE_RE.fullmatch(td)):
            err.append(f"S5_date linia {i}: {td!r}")
        if o.get("file") != f"emisii/{g}/{td}.json":
            err.append(f"S5_file linia {i}: {o.get('file')!r}")
        else:
            ef = trib / o["file"]
            if not ef.is_file():
                err.append(f"S5_sha linia {i}: emisia {o['file']} lipsește")
            elif sha(ef) != o.get("sha256"):
                err.append(f"S5_sha linia {i}: sha-ul emisiei {o['file']} diferă")
        u = o.get("emitted_utc")
        if not (isinstance(u, str) and UTC_RE.fullmatch(u)):
            err.append(f"S5_utc linia {i}: {u!r}")
        elif u < prev_utc:
            err.append(f"S5_utc linia {i}: emitted_utc descrescător")
        else:
            prev_utc = u
        if (g, td) in seen:
            err.append(f"S5_unique linia {i}: ({g}, {td}) duplicat")
        seen.add((g, td))
        prev_line = raw
    if check_mode and f.stat().st_mode & 0o777 != 0o444:
        err.append(f"S6 modul {oct(f.stat().st_mode & 0o777)} != 0o444")
    return err


def lant_lines(trib: Path) -> list[bytes]:
    return (trib / "LANT.jsonl").read_bytes().splitlines()


# --------------------------------------------------------------------------------------------- driftul nou §3
DRIFT_RE = re.compile(r"^(\S+) drift (\[.*\])$")
LANT_ONLY = [LANT_REL]


def drift_check(lines: list[str]) -> tuple[bool, dict]:
    raw = [x for x in lines if re.search(r" drift \[", x)]
    det: dict = {"linii": raw}
    order = SEAL["suite14_order"]
    if len(raw) != 14:
        det["motiv"] = f"{len(raw)} linii drift (≠ 14)"
        return False, det
    parsed = []
    for x in raw:
        m = DRIFT_RE.match(x)
        try:
            lst = ast.literal_eval(m.group(2)) if m else None
        except Exception:  # noqa: BLE001
            lst = None
        if not m or not isinstance(lst, list):
            det["motiv"] = f"linie drift neparsabilă: {x}"
            return False, det
        parsed.append((m.group(1), lst))
    if [s for s, _ in parsed] != order:
        det["motiv"] = "ordinea sigiliilor diferă"
        return False, det
    allowed = set(SEAL["drift_allowed_on"])
    bad = [(s, l) for s, l in parsed if s not in allowed and l != []]
    if bad:
        det["motiv"] = f"drift în afara S16–S19: {bad}"
        return False, det
    four = [l for s, l in parsed if s in allowed]
    if any(l not in ([], LANT_ONLY) for l in four):
        det["motiv"] = f"S16–S19: alt fișier decât LANT: {four}"
        return False, det
    if any(l != four[0] for l in four):
        det["motiv"] = f"S16–S19 neidentice: {four}"
        return False, det
    m = [re.fullmatch(r"LANT_PREFIX_S20 OK linii (\d+)", x) for x in lines]
    m = [int(x.group(1)) for x in m if x]
    if len(m) != 1:
        det["motiv"] = f"linia LANT_PREFIX_S20 OK lipsește sau e multiplă: {m}"
        return False, det
    n = m[0]
    det["lant_linii_log"], det["s16_s19"] = n, four[0]
    if four[0] == [] and n != LS["LANT_PREFIX_S20"]["lines"]:
        det["motiv"] = f"S16–S19 fără drift dar LANT are {n} linii"
        return False, det
    if four[0] == LANT_ONLY and n <= LS["LANT_PREFIX_S20"]["lines"]:
        det["motiv"] = f"S16–S19 arată LANT dar logul are numai {n} linii"
        return False, det
    return True, det


def lant_log_check(lines: list[str], trib: Path) -> tuple[bool, dict]:
    errs = scut_lant(trib)
    cur = lant_lines(trib)
    logl = [x for x in lines if re.fullmatch(r"LANT \S+ \S+ [0-9a-f]{8}", x)]
    exp = []
    for raw in cur[: len(logl)]:
        try:
            o = json.loads(raw)
            exp.append(f"LANT {o['game']} {o['target_date']} {o['sha256'][:8]}")
        except Exception:  # noqa: BLE001
            exp.append(None)
    m = [re.fullmatch(r"LANT_PREFIX_S20 OK linii (\d+)", x) for x in lines]
    m = [int(x.group(1)) for x in m if x]
    ok_log = len(m) == 1 and len(logl) == m[0] <= len(cur) and logl == exp
    return (not errs and ok_log), {"scut_abateri": errs, "linii_log": len(logl), "linii_curente": len(cur),
                                   "log_coincide_cu_prefixul_curent": ok_log}


# ---------------------------------------------------------------------------------------------------------- V0L
class _Capture:
    """Înlocuiește Report din verifica_s23 pe durata apelului: păstrează verificările, NU scrie fișier V0."""
    last: list = []

    def __init__(self, crit: str):
        self.crit, self.checks = crit, []

    def check(self, name, ok, detail=None):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def finish(self, extra=None, informative=False):
        _Capture.last = self.checks
        return 0


def v0l_checks(log: Path, trib: Path = TRIB) -> list[dict]:
    orig = V23.Report
    V23.Report = _Capture
    try:
        V23.v0(log)
    finally:
        V23.Report = orig
    inherited = _Capture.last
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    assert [c["name"] for c in inherited].count("drift_14_goale") == 1 and len(inherited) == 28
    ok_d, det_d = drift_check(lines)
    out = []
    for c in inherited:
        if c["name"] == "drift_14_goale":
            out.append({"name": "drift_14_numai_lant_append", "ok": ok_d, "detail": det_d})
        else:
            out.append(c)
    ok_s, det_s = lant_log_check(lines, trib)
    out.append({"name": "lant_scut", "ok": ok_s, "detail": det_s})
    return out


def v0l_ok(checks: list[dict]) -> bool:
    fails = [c for c in checks if not c["ok"]]
    return len(checks) == 29 and len(fails) == 1 and fails[0]["name"] == "incidente"


def v0l(log: Path) -> tuple[int, Path]:
    r = Report("V0L")
    r.checks = v0l_checks(log)
    rc = r.finish({"log": str(log), "log_sha256": sha(log), "asteptat": SEAL["expected"]["v0l"],
                   "conform_asteptarii_28_29_numai_incidente": v0l_ok(r.checks)})
    return rc, sorted(OUT.glob("V0L_VERIFICARE_*.json"))[-1]


# ----------------------------------------------------------------------------------------------------------- A0
def a0() -> int:
    r = Report("A0")
    r.check("sigiliu_sha", sha(SEAL_PATH) == SEAL_SHA, sha(SEAL_PATH))
    r.check("sigiliu_0444", SEAL_PATH.stat().st_mode & 0o777 == 0o444)
    for rel, d in SEAL["documents"].items():
        r.check(f"protocol_sha:{rel}", sha(path_of(rel)) == d["sha256"])
        r.check(f"protocol_0444:{rel}", path_of(rel).stat().st_mode & 0o777 == 0o444)
    fz = SEAL["frozen_hashes"]
    drift = [k for k, v in fz.items() if not path_of(k).exists() or sha(path_of(k)) != v]
    r.check("inghetate_fara_drift", not drift, {"n": len(fz), "drift": drift})
    man = json.loads(MAN22.read_text())
    modes = {k: oct(path_of(k).stat().st_mode & 0o777) for k in man["sources"]}
    r.check("surse_rust_27_0444", len(modes) == 27 and all(v == "0o444" for v in modes.values()),
            {k: v for k, v in modes.items() if v != "0o444"})
    for k in ("rust_core/src/models/h1_mass.rs", "rust_core/src/models/h3_aero.rs"):
        r.check(f"{Path(k).name}_0444_sha", modes[k] == "0o444" and sha(path_of(k)) == man["sources"][k]["sha256"])
    for rel, d in SEAL["append_only_prefix"].items():
        b = path_of(rel).read_bytes()
        r.check(f"prefix:{rel}", len(b) >= d["bytes"] and shab(b[: d["bytes"]]) == d["sha256"],
                {"bytes_acum": len(b), "bytes_sigiliu": d["bytes"]})
    errs = scut_lant(TRIB)
    r.check("scut_lant", not errs, {"abateri": errs, "linii": len(lant_lines(TRIB))})
    for rel in OLD_VERIFIERS:
        r.check(f"neschimbat:{rel}", sha(path_of(rel)) == fz[rel])
    return r.finish()


# ----------------------------------------------------------------------------------------------------------- A1
def _emisie_sintetica(trib: Path, game: str, td: str) -> tuple[str, str]:
    rel = f"emisii/{game}/{td}.json"
    (trib / rel).parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps({"game": game, "target_date": td, "fixture": "S25 sintetic", "positive_claims_allowed": False},
                       indent=1) + "\n").encode()
    (trib / rel).write_bytes(data)
    return rel, shab(data)


def _tribunal_sintetic(root: Path, n_new: int = 3) -> Path:
    trib = root / "tribunal"
    trib.mkdir(parents=True)
    shutil.copytree(TRIB / "emisii", trib / "emisii")
    lant = (TRIB / "LANT.jsonl").read_bytes()
    lines = lant.splitlines()
    for k, g in enumerate(LS["games"][:n_new]):
        rel, s = _emisie_sintetica(trib, g, "2099-01-01")
        rec = {"i": len(lines), "game": g, "target_date": "2099-01-01", "file": rel, "sha256": s,
               "emitted_utc": f"2099-01-01T06:20:0{k}.000000Z", "prev_line_sha256": shab(lines[-1])}
        lines.append(json.dumps(rec, ensure_ascii=False, sort_keys=True).encode())
    (trib / "LANT.jsonl").write_bytes(b"".join(x + b"\n" for x in lines))
    (trib / "LANT.jsonl").chmod(0o444)
    return trib


def _rewrite_lant(trib: Path, fn) -> None:
    f = trib / "LANT.jsonl"
    f.chmod(0o644)
    f.write_bytes(fn(f.read_bytes()))
    f.chmod(0o444)


def _log_post_emisie(base: list[str], trib: Path) -> list[str]:
    cur = lant_lines(trib)
    out = []
    for x in base:
        m = DRIFT_RE.match(x)
        if m and m.group(1) in SEAL["drift_allowed_on"]:
            out.append(f"{m.group(1)} drift {LANT_ONLY!r}")
        elif re.fullmatch(r"LANT_PREFIX_S20 OK linii \d+", x):
            out.append(f"LANT_PREFIX_S20 OK linii {len(cur)}")
        elif re.fullmatch(r"LANT \S+ \S+ [0-9a-f]{8}", x):
            continue
        else:
            out.append(x)
        if x.startswith("LANT_PREFIX_S20 OK"):
            for raw in cur:
                o = json.loads(raw)
                out.append(f"LANT {o['game']} {o['target_date']} {o['sha256'][:8]}")
    return out


def a1() -> int:
    r = Report("A1")
    before, _ = RD.tree_hash(TRIB)
    base = B0_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    res = {}
    with tempfile.TemporaryDirectory(prefix="ql649_s25_a1_") as d:
        D = Path(d)
        # F01: logul B0 real + tribunalul real
        c = v0l_checks(B0_LOG, TRIB)
        res["F01"] = (v0l_ok(c), [x["name"] for x in c if not x["ok"]])
        # F02: 3 linii sintetice valide + log post-emisie
        t2 = _tribunal_sintetic(D / "F02")
        lp = _log_post_emisie(base, t2)
        lf = D / "F02" / "log_post_emisie.log"
        lf.write_text("\n".join(lp) + "\n", encoding="utf-8")
        c = v0l_checks(lf, t2)
        res["F02"] = (v0l_ok(c) and not scut_lant(t2), [x["name"] for x in c if not x["ok"]])

        def scut_case(name, mut, tag):
            t = _tribunal_sintetic(D / name)
            _rewrite_lant(t, mut)
            e = scut_lant(t)
            res[name] = (bool(e) and any(x.startswith(tag) for x in e), e[:4])

        def last_obj(b):
            ls = b.splitlines()
            return ls, json.loads(ls[-1])

        def put_last(ls, o, raw=None):
            ls[-1] = raw if raw is not None else json.dumps(o, ensure_ascii=False, sort_keys=True).encode()
            return b"".join(x + b"\n" for x in ls)

        scut_case("F03", lambda b: b[:10] + bytes([b[10] ^ 0x01]) + b[11:], "S1")   # un octet din linia 0
        scut_case("F04", lambda b: b"".join(x + b"\n" for x in b.splitlines()[:2]), "S1")

        def f05(b):
            ls, o = last_obj(b)
            o["prev_line_sha256"] = "0" * 64
            return put_last(ls, o)
        scut_case("F05", f05, "S5_prev")

        def f06(b):
            ls, o = last_obj(b)
            o["sha256"] = "f" * 64
            return put_last(ls, o)
        scut_case("F06", f06, "S5_sha")

        def f07(b):
            ls, o = last_obj(b)
            o["extra"] = 1
            return put_last(ls, o)
        scut_case("F07", f07, "S5_keys")
        scut_case("F08", lambda b: b.rstrip(b"\n"), "S4_newline")

        def f09(b):
            ls, o = last_obj(b)
            prev = json.loads(ls[-2])
            o["game"], o["file"], o["sha256"] = prev["game"], prev["file"], prev["sha256"]
            return put_last(ls, o)
        scut_case("F09", f09, "S5_unique")

        def f10(b):
            ls, o = last_obj(b)
            return put_last(ls, o, json.dumps(o, ensure_ascii=False, sort_keys=True, indent=None,
                                              separators=(",", ":")).encode())
        scut_case("F10", f10, "S5_canon")

        # F11–F15: mutații ale logului post-emisie (tribunalul F02, altfel valid)
        def drift_case(name, mut):
            ok, det = drift_check(mut(list(lp)))
            res[name] = (not ok, det.get("motiv"))

        def repl(lines, sigiliu, new):
            return [new if DRIFT_RE.match(x) and DRIFT_RE.match(x).group(1) == sigiliu else x for x in lines]

        drift_case("F11", lambda L: repl(L, "tu4/SIGILIU_TU4_S17.json",
                                         "tu4/SIGILIU_TU4_S17.json drift ['tu4/tribunal/LANT.jsonl', 'tu4/emite.py']"))
        drift_case("F12", lambda L: repl(L, "tu4/SIGILIU_TU4_S20.json",
                                         "tu4/SIGILIU_TU4_S20.json drift ['tu4/tribunal/LANT.jsonl']"))
        drift_case("F13", lambda L: [re.sub(r"^LANT_PREFIX_S20 OK linii \d+$", "LANT_PREFIX_S20 OK linii 3", x) for x in L])
        drift_case("F14", lambda L: repl(repl(repl(L, "tu4/SIGILIU_TU4_S17.json", "tu4/SIGILIU_TU4_S17.json drift []"),
                                              "tu4/SIGILIU_TU4_S18.json", "tu4/SIGILIU_TU4_S18.json drift []"),
                                         "tu4/SIGILIU_TU4_S19.json", "tu4/SIGILIU_TU4_S19.json drift []"))
        drift_case("F15", lambda L: [x for x in L if not (DRIFT_RE.match(x) and DRIFT_RE.match(x).group(1)
                                                         == "tu4/SIGILIU_TU4_UI.json")])
    after, _ = RD.tree_hash(TRIB)
    r.check("tribunal_real_neatins", before == after)
    for k in SEAL["expected"]["a1_cases"]:
        ok, det = res.get(k, (False, "caz lipsă"))
        r.check(k, ok, det)
    return r.finish()


# ----------------------------------------------------------------------------------------------------------- Q7L
def q7l(log: Path, s25_inc: list[str]) -> int:
    r = Report("Q7L")
    t = log.read_text(encoding="utf-8", errors="replace")
    lines = t.splitlines()
    _, vf = v0l(log)
    v = json.loads(vf.read_text())
    fails = [c for c in v["checks"] if not c["ok"]]
    allowed = set(SEAL["incidents_before"]) | set(s25_inc)
    v_inc = set((fails[0]["detail"] or {}).get("gasite", [])) if len(fails) == 1 else set()
    r.check("v0l_28_29_numai_incidente", v0l_ok(v["checks"]) and v_inc <= allowed,
            {"v0l": str(vf), "fails": [(c["name"], c["detail"]) for c in fails]})
    found = sorted(d.name for d in (QL / "tu4/incidente").iterdir() if d.is_dir())
    r.check("incidente_cunoscute", set(found) == allowed and all(re.fullmatch(r"S25_\d\d", x) for x in s25_inc),
            {"gasite": found, "permise": sorted(allowed)})
    for k, pat in (("paritate_587", r'"n_pass": 587'), ("rust_61", r"test result: ok\. 61 passed"),
                   ("q0_pass", r'"criteriu": "Q0",\s+"verdict": "PASS"'), ("q1_pass", r'"criteriu": "Q1",\s+"verdict": "PASS"'),
                   ("serviciu_activ_sau_reusit", r"^S24_SERVICIU Result=success"),
                   ("decontare_raport", r'"verdict": "DECONTARE_(PENDING|PARTIALA|COMPLETA)"'),
                   ("b5_sau_b2", r"^(B5_RC=0|B2_RC=0)$")):
        r.check(k, re.search(pat, t, re.M) is not None)
    r.check("fara_fail_q_a", not any(x.startswith(("FAIL Q", "FAIL A")) for x in lines),
            [x for x in lines if x.startswith(("FAIL Q", "FAIL A"))])
    r.check("verificatoare_vechi_neschimbate", all(sha(path_of(x)) == SEAL["frozen_hashes"][x] for x in OLD_VERIFIERS))
    return r.finish({"log": str(log), "log_sha256": sha(log), "v0l_file": str(vf), "v0l_sha256": sha(vf)})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["a0", "a1", "v0l", "q7l", "scut"])
    ap.add_argument("log", nargs="?", type=Path)
    ap.add_argument("--incidente-s25", default="")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.cmd in ("v0l", "q7l") and not a.log:
        ap.error(f"{a.cmd} cere calea logului")
    if a.cmd == "v0l":
        return v0l(a.log)[0]
    if a.cmd == "q7l":
        return q7l(a.log, [x for x in a.incidente_s25.split(",") if x])
    if a.cmd == "scut":
        e = scut_lant(TRIB)
        print("SCUT_LANT", "OK" if not e else "FAIL", "linii", len(lant_lines(TRIB)), e)
        return 0 if not e else 1
    return {"a0": a0, "a1": a1}[a.cmd]()


if __name__ == "__main__":
    sys.exit(main())
