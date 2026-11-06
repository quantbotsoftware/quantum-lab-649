"""Verificatorul S31 (protocol tu4/PROTOCOL_QUANTUM_S31.md §3). Scris DUPĂ sigiliul S31 (d8e8cfe0…); scrie numai fișiere
noi în tu4/rezultate/S31/ (0444): <crit>_VERIFICARE_<UTC>.json, iar M2 încă SONDA_M2_<UTC>.txt (ieșirea sondei).
Utilizare:  verifica_s31.py m0 | m1 | m2 | m3      (fiecare O SINGURĂ DATĂ; în fereastră: rc 3 fără scrieri)
Nu citește numerele extragerilor, nu rulează binarul Rust, judecătorul, emițătorul sau actualizarea, nu atinge garda externă
(numai citire/hash), nu rescrie fișele S29/S30. Calcul clasic; positive_claims_allowed=false.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import datetime as dt  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

QL = Path(".")
ROOT = Path(".")
OUT = QL / "tu4/rezultate/S31"
SEAL_PATH = QL / "tu4/SIGILIU_TU4_S31.json"
SEAL_SHA = "d8e8cfe06b5e0398e617170e7d183e648ce592714bbd85122a671a256a3f73b7"
SEAL27_SHA = "ce2a9f1816dd5de4a8e22e98e3e4566de7267def2142b23122be2374b9f9bc13"
SEAL28_SHA = "0b4fd79b0323532241504a0b04368d50c8aa754a8bb687d0c5030dc9abb4a138"
SEAL29_SHA = "911af09ca6fb11b10129655aad04e7f6f477aac517cdefc887e2164be8d8fa37"
SEAL30_SHA = "4cbdb516e600185f541b779a5a43fd9b457ea487d3f2888450235f25ff215169"
A01_SEAL = QL / "tu4/SIGILIU_AMENDAMENT_S28_A01.json"
A01_SHA = "b44ffea37fb7d8b357491648c28a833a97434ff620a88b17f8f290f78fcd1d79"
FISA29 = QL / "tu4/rezultate/S29/FISA_DUMINICA_S29.json"
FISA29_SHA = "2b597a222d50189064397bbb0a1e035fe01d7c57f945b7a2887c2e315376b10f"
FISAJ30 = QL / "tu4/rezultate/S30/FISA_JOI_S30.json"
FISAJ30_SHA = "0deeb89e502a46926312ef46e29d3bcfce2a46a91ed243d7bc0de4dfcfe9a06d"
P1_S29 = QL / "tu4/rezultate/S29/P1_VERIFICARE_20261028T134355Z.json"
K1_S30 = QL / "tu4/rezultate/S30/K1_VERIFICARE_20261028T140453Z.json"
K1_S30_SHA = "1a18f05a4907353816d01886f96873df0e0d6c8e09918aa477a7a5e6b8e313b9"
ALIN30 = QL / "tu4/rezultate/S30/ALINIERE_FISE_S30.json"
ALIN30_SHA = "65ef123ca16c72a05a4193f1a3a0ecda36545a8a2c3adfdf9b04e78fb8674ac0"
DEC_B0 = QL / "tu4/rezultate/S24/DECONTARE_20261029_20261029T171753Z.json"
DEC_B0_SHA = "21afe07ae8c27e89acce382c7b5158a23f8761911417fe6c0aa0043f0f5f22a7"
LIVE = QL / "tu3/date/live/CURRENT_LIVE.json"
SEAL = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
MAN22 = QL / "tu4/rezultate/S22/MANIFEST_RUST_CORE_20261028T032900Z.json"
UTC = dt.timezone.utc
TZ = ZoneInfo("Europe/Bucharest")
NY = ZoneInfo("America/New_York")
DRAW = dt.datetime(2026, 10, 29, 16, 30, tzinfo=UTC)
M2_NOT_BEFORE = DRAW + dt.timedelta(hours=2)
INCID9 = ["EM_01", "FR_01", "S19_01", "S20_01", "S23_01", "S23_02", "S23_03", "S24_01", "SM1_01"]
GUARD163 = "raise ValueError('Model/environment changed after protocol freeze: ' + model)"
TD_DEC = "2026-10-29"

sys.path.insert(0, str(QL / "tu4/s27"))
import sonda_s27 as SO  # noqa: E402  (cod S27 înghețat; numai window/path_of)


def utc_now() -> str:
    return dt.datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def z(t: dt.datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ny(t: dt.datetime, fmt: str = "%Y-%m-%d %H:%M %Z") -> str:
    return t.astimezone(NY).strftime(fmt)


def T(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def write_ro(path: Path, text: str) -> str:
    assert not path.exists(), path
    path.write_text(text, encoding="utf-8")
    path.chmod(0o444)
    return sha(path)


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "TZ"}
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env, cwd=cwd)


class Report:
    def __init__(self, crit: str):
        self.crit, self.checks = crit, []

    def check(self, name, ok, detail=None):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def finish(self, extra=None, verdict: str | None = None) -> int:
        n_pass = sum(c["ok"] for c in self.checks)
        if verdict is None:
            verdict = "PASS" if self.checks and n_pass == len(self.checks) else "FAIL"
        stamp = utc_now()
        out = OUT / f"{self.crit}_VERIFICARE_{stamp}.json"
        while out.exists():          # lecția S23_02
            time.sleep(1.0)
            stamp = utc_now()
            out = OUT / f"{self.crit}_VERIFICARE_{stamp}.json"
        doc = {"criteriu": self.crit, "verdict": verdict, "n_checks": len(self.checks), "n_pass": n_pass,
               "run_utc": stamp, "protocol": "TU4-S31", "checks": self.checks, "positive_claims_allowed": False}
        if extra:
            doc.update(extra)
        write_ro(out, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "n_checks", "n_pass")}, ensure_ascii=False))
        for c in self.checks:
            if not c["ok"]:
                print("FAIL", self.crit, c["name"], json.dumps(c["detail"], ensure_ascii=False)[:800])
        print(out, sha(out))
        return {"PASS": 0, "FAIL": 1}.get(verdict, 3)


def incidents() -> list[str]:
    return sorted(d.name for d in (QL / "tu4/incidente").iterdir() if d.is_dir())


def rust_ok() -> tuple[bool, list]:
    man = json.loads(MAN22.read_text(encoding="utf-8"))["sources"]
    bad = [f for f, d in man.items() if SO.path_of(f).stat().st_mode & 0o777 != 0o444 or sha(SO.path_of(f)) != d["sha256"]]
    return len(man) == 27 and not bad, bad


def frozen_drift() -> list[str]:
    return [k for k, v in SEAL["frozen_hashes"].items() if not SO.path_of(k).is_file() or sha(SO.path_of(k)) != v]


def external_drift() -> list[str]:
    return [k for k, v in SEAL["external_nonintervention"].items() if not Path(k).is_file() or sha(Path(k)) != v]


def minute_excluded(t: dt.datetime) -> bool:
    return t.minute >= 58 or t.minute < 4 or 28 <= t.minute < 34


def gate() -> str | None:
    """Fereastra §1 (sonda_s27.window) + minutele [:58,:04) și [:28,:34); None = liber."""
    now = dt.datetime.now(UTC)
    w = SO.window(now, DRAW)
    if w:
        return w
    if minute_excluded(now):
        return f"minutul {now.minute} exclus"
    return None


def prior_verdicts(crit: str) -> list[str]:
    return [json.loads(f.read_text()).get("verdict") for f in sorted(OUT.glob(f"{crit}_VERIFICARE_*.json"))]


def allowed(crit: str) -> bool:
    v = prior_verdicts(crit)
    if any(x in ("PASS", "FAIL") for x in v):
        return False
    # excepția §2: o singură reluare după UNKNOWN_TRANZITIE (numai M2)
    return len(v) == 0 or (crit == "M2" and len(v) == 1)


# ------------------------------------------------------------------ M0
def m0() -> int:
    r = Report("M0")
    vp = json.loads((QL / "predari/VERIFICARE_PREDARE_20261028T140923Z.json").read_text())
    for f in ("HANDOFF_QL649_20261028T140923Z.md", "PROMPT_QL649_20261028T140923Z.txt"):
        r.check(f"predare_{f}", sha(QL / "predari" / f) == vp[f]["sha256"] and vp[f]["canon_once"] and vp[f]["supl_once"],
                vp[f]["sha256"][:8])
    b0 = SEAL["baseline_B0"]
    r.check("B0_hashes", all(sha(SO.path_of(k)) == v for k, v in b0.items()), list(b0))
    q7l = json.loads((QL / "tu4/rezultate/S25/Q7L_VERIFICARE_20261029T171753Z.json").read_text())
    r.check("B0_Q7L_11_11", q7l["verdict"] == "PASS" and q7l["n_pass"] == q7l["n_checks"] == 11)
    v0l = json.loads((QL / "tu4/rezultate/S25/V0L_VERIFICARE_20261029T171753Z.json").read_text())
    fails = [c.get("name") for c in v0l.get("checks", []) if not c.get("ok")]
    r.check("B0_V0L_28_29_incidente", v0l["n_checks"] == 29 and v0l["n_pass"] == 28 and fails == ["incidente"], fails)
    dec = json.loads(DEC_B0.read_text())
    r.check("B0_DECONTARE_PENDING_0", sha(DEC_B0) == DEC_B0_SHA and dec.get("verdict") == "DECONTARE_PENDING"
            and dec.get("n_decontate") == 0, dec.get("verdict"))
    r.check("sigiliu_S27_ce2a9f18", sha(QL / "tu4/SIGILIU_TU4_S27.json") == SEAL27_SHA)
    r.check("sigiliu_S28_0b4fd79b", sha(QL / "tu4/SIGILIU_TU4_S28.json") == SEAL28_SHA)
    r.check("sigiliu_A01_si_amendament", sha(A01_SEAL) == A01_SHA
            and sha(QL / "tu4/AMENDAMENT_S28_A01.md") == json.loads(A01_SEAL.read_text())["sha256"])
    r.check("sigiliu_S29_911af09c", sha(QL / "tu4/SIGILIU_TU4_S29.json") == SEAL29_SHA)
    r.check("sigiliu_S30_4cbdb516", sha(QL / "tu4/SIGILIU_TU4_S30.json") == SEAL30_SHA)
    d = frozen_drift()
    r.check("frozen_S31", not d, d)
    inc = incidents()
    r.check("incidente_9", inc == INCID9, inc)
    ok, bad = rust_ok()
    r.check("rust_27_0444_sha", ok, bad)
    me = Path(__file__).resolve()
    r.check("sigiliu_S31_si_verifica_s31_0444", sha(SEAL_PATH) == SEAL_SHA and me.stat().st_mode & 0o777 == 0o444,
            oct(me.stat().st_mode & 0o777))
    return r.finish({"seal_sha256": SEAL_SHA})


# ------------------------------------------------------------------ M1
def m1() -> int:
    r = Report("M1")
    p1 = json.loads(P1_S29.read_text())
    k1 = json.loads(K1_S30.read_text())
    alin = json.loads(ALIN30.read_text(encoding="utf-8"))
    mode = FISA29.stat().st_mode & 0o777
    r.check("fisa_S29_sha_mod_P1_K1_aliniere", sha(FISA29) == FISA29_SHA == p1.get("fisa_sha256") and mode == 0o444
            and p1["verdict"] == "PASS" and p1["n_pass"] == p1["n_checks"] == 15
            and sha(K1_S30) == K1_S30_SHA and k1["verdict"] == "PASS" and k1["n_pass"] == k1["n_checks"] == 8
            and sha(ALIN30) == ALIN30_SHA and alin.get("fisa_S29_rescrisa") is False, {"mode": oct(mode)})
    f = json.loads(FISA29.read_text(encoding="utf-8"))
    v, s = f["verificare_C1_B5"], f["slot_final_emisie"]
    fields_ok = (v["utc"] == ["2026-11-01T13:36:00Z", "2026-11-01T13:57:59Z"] and v["laptop"] == ["08:36 EST", "08:57 EST"]
                 and v["strict"] is True
                 and s["utc"] == "2026-11-01T13:20:00Z" and s["bucuresti"] == "15:20 EET" and s["laptop"] == "08:20 EST"
                 and s["interzis_utc"] == ["2026-11-01T13:05:00Z", "2026-11-01T13:35:00Z"]
                 and f["tranzitie_laptop"]["utc"] == "2026-11-01T06:00:00Z" and f["positive_claims_allowed"] is False)
    r.check("fisa_S29_campuri", fields_ok, {"utc": v["utc"], "laptop": v["laptop"], "slot": s})
    a, b = T(v["utc"][0]), T(v["utc"][1])
    mins = [T("2026-11-01T13:36:00Z") + dt.timedelta(minutes=k) for k in range(22)]
    zi_ok = (ny(a, "%H:%M:%S %Z") == "08:36:00 EST" and ny(b, "%H:%M:%S %Z") == "08:57:59 EST"
             and [ny(t) for t in mins] == [f"2026-11-01 08:{m:02d} EST" for m in range(36, 58)]
             and ny(T(s["utc"]), "%H:%M %Z") == "08:20 EST" and T(s["utc"]).astimezone(TZ).strftime("%H:%M %Z") == "15:20 EET")
    r.check("zoneinfo_capete_08_36_00_08_57_59_EST", zi_ok, [ny(a, "%H:%M:%S %Z"), ny(b, "%H:%M:%S %Z")])
    zn = run(["zdump", "-v", "-c", "2026,2027", "America/New_York"])
    zb = run(["zdump", "-v", "-c", "2026,2027", "Europe/Bucharest"])
    want_ny = ["America/New_York  Sun Nov  1 05:59:59 2026 UT = Sun Nov  1 01:59:59 2026 EDT isdst=1 gmtoff=-14400",
               "America/New_York  Sun Nov  1 06:00:00 2026 UT = Sun Nov  1 01:00:00 2026 EST isdst=0 gmtoff=-18000"]
    zn_lines = [x.rstrip() for x in zn.stdout.splitlines()]
    zb_dated = [x.rstrip() for x in zb.stdout.splitlines() if " UT = " in x]
    want_b = "Europe/Bucharest  Sun Oct 25 01:00:00 2026 UT = Sun Oct 25 03:00:00 2026 EET isdst=0 gmtoff=7200"
    r.check("zdump_NY_si_Bucuresti", zn.returncode == 0 and all(w in zn_lines for w in want_ny)
            and zb.returncode == 0 and bool(zb_dated) and zb_dated[-1] == want_b,
            {"ny": [x for x in zn_lines if "Nov  1" in x], "buc": zb_dated[-1:]})
    forb = {x: SO.window(T(x), DRAW) for x in ("2026-11-01T13:20:00Z", "2026-11-01T13:35:00Z")}
    free = {z(t): SO.window(t, DRAW) for t in mins}
    r.check("fereastra_13_36_13_57_libera_13_35_interzis_13_58_exclus",
            all(forb.values()) and all(x is None for x in free.values()) and not any(minute_excluded(t) for t in mins)
            and minute_excluded(T("2026-11-01T13:58:00Z")), {"forb": forb, "nelibere": {k: x for k, x in free.items() if x}})
    slots = [T(x["slot_utc"]) for x in f["sloturi_H_BLOCAT"]]
    robust = (len(slots) == 9 and z(slots[0]) == "2026-10-30T06:20:00Z" and z(slots[-1]) == "2026-11-01T13:20:00Z"
              and all(t + dt.timedelta(minutes=15) < a for t in slots)
              and T(s["interzis_utc"][1]) < a)
    r.check("fereastra_valabila_in_ambele_ramuri_H_BLOCAT_H_ACTUALIZAT", robust,
            {"prima_emisie_posibila": z(slots[0]) if slots else None, "slot_final": z(slots[-1]) if slots else None,
             "inceput_C1_B5": z(a)})
    now = dt.datetime.now(UTC)
    off = now.astimezone(NY).utcoffset()
    r.check("laptop_inca_EDT_tranzitie_programata_06_00Z", off == dt.timedelta(hours=-4) and now < T("2026-11-01T06:00:00Z"),
            {"acum_utc": z(now), "acum_NY": ny(now, "%Y-%m-%d %H:%M:%S %Z"), "offset_h": off.total_seconds() / 3600})
    return r.finish({"fisa_S29_rescrisa": False})


# ------------------------------------------------------------------ M2
def tree(paths: list[Path]) -> dict:
    out = {}
    for base in paths:
        files = [base] if base.is_file() else sorted(x for x in base.rglob("*") if x.is_file())
        for x in files:
            out[str(x.relative_to(QL))] = [x.stat().st_size, sha(x)]
    return out


def live_last() -> dict:
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    return {g: x["last_date"] for g, x in live["games"].items()}


def m2() -> int:
    now = dt.datetime.now(UTC)
    if now < M2_NOT_BEFORE:
        print(f"UNKNOWN_PREMATUR M2: {z(now)} < {z(M2_NOT_BEFORE)} (fără scrieri)")
        return 3
    r = Report("M2")
    watched = [QL / "tu4/tribunal", QL / "tu4/rezultate/S24", LIVE]
    ld0, t0 = live_last(), tree(watched)
    so = run(["/usr/bin/python3", "-B", "tu4/s27/sonda_s27.py"], cwd=QL)
    t1, ld1 = tree(watched), live_last()
    stamp = utc_now()
    txt = OUT / f"SONDA_M2_{stamp}.txt"
    tsh = write_ro(txt, f"$ /usr/bin/python3 -B tu4/s27/sonda_s27.py   (rc={so.returncode})\n" + so.stdout
                   + ("\n--- stderr ---\n" + so.stderr if so.stderr else ""))
    lines = so.stdout.splitlines()
    changed = sorted(k for k in set(t0) | set(t1) if t0.get(k) != t1.get(k))
    r.check("sonda_zero_scrieri_tribunal_S24_LIVE", not changed, changed)
    r.check("sonda_inghetata_rc0_fara_abateri", sha(QL / "tu4/s27/sonda_s27.py") == SEAL["frozen_hashes"]["tu4/s27/sonda_s27.py"]
            and so.returncode == 0 and not any(x.startswith("ABATERE") for x in lines) and "ANOMALIE" not in so.stdout,
            {"rc": so.returncode, "abateri": [x for x in lines if x.startswith("ABATERE")]})
    if ld0 != ld1:
        r.check("LIVE_stabil_in_timpul_sondei", False, {"inainte": ld0, "dupa": ld1})
        return r.finish({"sonda_txt": txt.name, "sonda_txt_sha256": tsh, "ramura": "UNKNOWN_TRANZITIE"},
                        verdict="UNKNOWN")
    r.check("LIVE_stabil_in_timpul_sondei", True, ld0)
    branch = "H_BLOCAT" if min(ld0.values()) < TD_DEC else "H_ACTUALIZAT"
    faza = next((x.split("=", 1)[1].split()[0] for x in lines if x.startswith("SONDA_S27_FAZA=")), None)
    avert = any(x.startswith("AVERTISMENT_DECONTARE_BLOCATA") for x in lines)
    get = lambda pre: next((x for x in lines if x.startswith(pre)), "")  # noqa: E731
    t1l, t2l, t3l, t5l, jul = get("T1 "), get("T2 "), get("T3 "), get("T5 "), get("T4 judecator")
    if branch == "H_BLOCAT":
        r.check("faza_si_avertisment_H_BLOCAT", faza == "FAZA_0_ASTEAPTA_DECONTAREA" and avert,
                {"faza": faza, "AVERTISMENT_DECONTARE_BLOCATA": avert})
        r.check("T1_T2_T3_T5_judecator_H_BLOCAT", "DECONTARE_PENDING 0/3" in t2l and " 0/3 " in t3l + " "
                and "OK linii=3" in t1l and "tribunal_neatins OK" in t5l and "action=nothing_to_settle" in jul,
                {"T1": t1l, "T2": t2l, "T3": t3l, "T5": t5l, "judecator": jul[:200]})
        rezultat = "CONFIRMAT_PENDING_CU_AVERTISMENT"
    else:
        r.check("faza_si_avertisment_H_ACTUALIZAT", faza in ("FAZA_0_ASTEAPTA_DECONTAREA", "FAZA_1_DECONTARE_PARTIALA",
                                                             "FAZA_2_DECONTARE_COMPLETA") and not avert,
                {"faza": faza, "AVERTISMENT_DECONTARE_BLOCATA": avert})
        r.check("T3_T5_H_ACTUALIZAT", " 0/3 " in t3l + " " and "tribunal_neatins OK" in t5l, {"T3": t3l, "T5": t5l})
        rezultat = "NECONFIRMAT_H_ACTUALIZAT"
    decs = sorted((QL / "tu4/rezultate/S24").glob("DECONTARE_20261029_*.json"))
    r.check("ultimul_raport_decontare_este_B0", bool(decs) and decs[-1] == DEC_B0 and sha(DEC_B0) == DEC_B0_SHA,
            decs[-1].name if decs else None)
    res = run(["systemctl", "--user", "show", "-p", "Result", "-p", "ExecMainExitTimestamp", "loto-actualizare.service"])
    jr = run(["journalctl", "--user", "-u", "loto-actualizare.service", "-n", "40", "--no-pager", "-o", "short-iso"])
    obs = {"systemctl": " ".join(res.stdout.split()),
           "jurnal_ultimele_40_contin_gpu_v1": "gpu-v1" in jr.stdout,
           "nota": "observație de stare, fără prag; cauza neinvestigată"}
    return r.finish({"sonda_txt": txt.name, "sonda_txt_sha256": tsh, "ramura": branch, "rezultat_M2": rezultat,
                     "faza": faza, "AVERTISMENT_DECONTARE_BLOCATA": avert, "live_last_date": ld0,
                     "observatie_loto_actualizare": obs})


# ------------------------------------------------------------------ M3
def m3() -> int:
    r = Report("M3")
    d = frozen_drift()
    r.check("frozen_S31_neschimbate", not d, d)
    r.check("sigilii_S27_S28_A01_S29_S30_S31", sha(SEAL_PATH) == SEAL_SHA and sha(QL / "tu4/SIGILIU_TU4_S30.json") == SEAL30_SHA
            and sha(QL / "tu4/SIGILIU_TU4_S29.json") == SEAL29_SHA and sha(QL / "tu4/SIGILIU_TU4_S28.json") == SEAL28_SHA
            and sha(QL / "tu4/SIGILIU_TU4_S27.json") == SEAL27_SHA and sha(A01_SEAL) == A01_SHA)
    e = external_drift()
    s30 = json.loads((QL / "tu4/SIGILIU_TU4_S30.json").read_text())
    r.check("externe_garda_unitate_timere_neschimbate", not e
            and SEAL["external_nonintervention"] == s30["external_nonintervention"], e)
    lines = (ROOT / "loto_romania/cohorta.py").read_text(encoding="utf-8").splitlines()
    r.check("garda_linia_163_neatinsa", len(lines) >= 163 and lines[162].strip() == GUARD163, lines[162].strip()[:120])
    ok, bad = rust_ok()
    r.check("rust_27_0444_sha", ok, bad)
    inc = incidents()
    r.check("incidente_9", inc == INCID9, inc)
    lb = (QL / "tu4/tribunal/LANT.jsonl").read_bytes()
    snap = SEAL["lant_snapshot_S31"]
    r.check("LANT_eq_instantaneu", hashlib.sha256(lb).hexdigest() == snap["sha256"] and len(lb) == snap["bytes"],
            {"bytes": len(lb), "lines": len(lb.splitlines())})
    s31 = sorted(f.name for f in (QL / "tu4/s31").iterdir())
    r.check("s31_numai_verificator_0444", s31 == ["verifica_s31.py"]
            and (QL / "tu4/s31/verifica_s31.py").stat().st_mode & 0o777 == 0o444, s31)
    act = {u: run(["systemctl", "--user", "is-active", u]).stdout.strip()
           for u in ("loto-actualizare.timer", "ql649-tu4-emitere.timer")}
    r.check("timere_active", all(x == "active" for x in act.values()), act)
    r.check("fise_S29_S30_neschimbate", sha(FISA29) == FISA29_SHA and FISA29.stat().st_mode & 0o777 == 0o444
            and sha(FISAJ30) == FISAJ30_SHA and FISAJ30.stat().st_mode & 0o777 == 0o444)
    return r.finish()


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("m0", "m1", "m2", "m3"):
        print(__doc__)
        return 2
    crit = argv[0].upper()
    if not allowed(crit):
        print(f"REFUZ {crit}: rulat deja (o singură rulare per criteriu; §2)")
        return 2
    w = gate()
    if w:
        print(f"UNKNOWN_FEREASTRA {crit}: {w} (fără scrieri)")
        return 3
    return {"M0": m0, "M1": m1, "M2": m2, "M3": m3}[crit]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
