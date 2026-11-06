"""Verificatorul S30 (protocol tu4/PROTOCOL_QUANTUM_S30.md §3). Scris DUPĂ sigiliul S30 (4cbdb516…); scrie numai fișiere
noi în tu4/rezultate/S30/ (0444): <crit>_VERIFICARE_<UTC>.json, iar K1 încă ALINIERE_FISE_S30.json, K2 FISA_JOI_S30.json.
Utilizare:  verifica_s30.py k0 | k1 | k2 | k3      (fiecare O SINGURĂ DATĂ; în fereastră: rc 3 fără scrieri)
Nu citește numerele extragerilor, nu rulează binarul Rust, nu atinge garda externă (numai citire/hash), nu rescrie fișa
de duminică S29. Calcul clasic; positive_claims_allowed=false.
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

QL = Path("${QL649_ROOT:-.}")
ROOT = Path("${LOTO_RO_ROOT:-.}")
OUT = QL / "tu4/rezultate/S30"
SEAL_PATH = QL / "tu4/SIGILIU_TU4_S30.json"
SEAL_SHA = "4cbdb516e600185f541b779a5a43fd9b457ea487d3f2888450235f25ff215169"
SEAL27_SHA = "ce2a9f1816dd5de4a8e22e98e3e4566de7267def2142b23122be2374b9f9bc13"
SEAL28_SHA = "0b4fd79b0323532241504a0b04368d50c8aa754a8bb687d0c5030dc9abb4a138"
SEAL29_SHA = "911af09ca6fb11b10129655aad04e7f6f477aac517cdefc887e2164be8d8fa37"
A01_SEAL = QL / "tu4/SIGILIU_AMENDAMENT_S28_A01.json"
A01_SHA = "b44ffea37fb7d8b357491648c28a833a97434ff620a88b17f8f290f78fcd1d79"
FISA29 = QL / "tu4/rezultate/S29/FISA_DUMINICA_S29.json"
FISA29_SHA = "2b597a222d50189064397bbb0a1e035fe01d7c57f945b7a2887c2e315376b10f"
P1_S29 = QL / "tu4/rezultate/S29/P1_VERIFICARE_20261028T134355Z.json"
CAL28 = QL / "tu4/rezultate/S28/CALENDAR_S28.json"
DEC_B0 = QL / "tu4/rezultate/S24/DECONTARE_20261029_20261028T135343Z.json"
SEAL = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
MAN22 = QL / "tu4/rezultate/S22/MANIFEST_RUST_CORE_20261028T032900Z.json"
UTC = dt.timezone.utc
TZ = ZoneInfo("Europe/Bucharest")
NY = ZoneInfo("America/New_York")
DRAW = dt.datetime(2026, 10, 29, 16, 30, tzinfo=UTC)
INCID9 = ["EM_01", "FR_01", "S19_01", "S20_01", "S23_01", "S23_02", "S23_03", "S24_01", "SM1_01"]
GUARD163 = "raise ValueError('Model/environment changed after protocol freeze: ' + model)"
QLD = "${QL649_ROOT:-.}"
LAST_BLOCAT = "2026-10-25"

sys.path.insert(0, str(QL / "tu4/s27"))
sys.path.insert(0, str(QL / "tu4/s25"))
sys.path.insert(0, str(QL / "tu4/s24"))
import sonda_s27 as SO  # noqa: E402  (cod S27 înghețat; numai window/path_of)


def utc_now() -> str:
    return dt.datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def z(t: dt.datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ny(t: dt.datetime, fmt: str = "%Y-%m-%d %H:%M %Z") -> str:
    return t.astimezone(NY).strftime(fmt)


def buc(t: dt.datetime) -> str:
    return t.astimezone(TZ).strftime("%Y-%m-%d %H:%M %Z")


def T(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def write_ro(path: Path, text: str) -> str:
    assert not path.exists(), path
    path.write_text(text, encoding="utf-8")
    path.chmod(0o444)
    return sha(path)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "TZ"}
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)


class Report:
    def __init__(self, crit: str):
        self.crit, self.checks = crit, []

    def check(self, name, ok, detail=None):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def finish(self, extra=None) -> int:
        n_pass = sum(c["ok"] for c in self.checks)
        verdict = "PASS" if self.checks and n_pass == len(self.checks) else "FAIL"
        stamp = utc_now()
        out = OUT / f"{self.crit}_VERIFICARE_{stamp}.json"
        while out.exists():          # lecția S23_02
            time.sleep(1.0)
            stamp = utc_now()
            out = OUT / f"{self.crit}_VERIFICARE_{stamp}.json"
        doc = {"criteriu": self.crit, "verdict": verdict, "n_checks": len(self.checks), "n_pass": n_pass,
               "run_utc": stamp, "protocol": "TU4-S30", "checks": self.checks, "positive_claims_allowed": False}
        if extra:
            doc.update(extra)
        write_ro(out, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "n_checks", "n_pass")}, ensure_ascii=False))
        for c in self.checks:
            if not c["ok"]:
                print("FAIL", self.crit, c["name"], json.dumps(c["detail"], ensure_ascii=False)[:800])
        print(out, sha(out))
        return 0 if verdict == "PASS" else 1


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


def once(crit: str) -> bool:
    return not list(OUT.glob(f"{crit}_VERIFICARE_*.json"))


# ------------------------------------------------------------------ K0
def k0() -> int:
    r = Report("K0")
    vp = json.loads((QL / "predari/VERIFICARE_PREDARE_20261028T134819Z.json").read_text())
    for f in ("HANDOFF_QL649_20261028T134819Z.md", "PROMPT_QL649_20261028T134819Z.txt"):
        r.check(f"predare_{f}", sha(QL / "predari" / f) == vp[f]["sha256"] and vp[f]["canon_once"] and vp[f]["supl_once"],
                vp[f]["sha256"][:8])
    b0 = SEAL["baseline_B0"]
    r.check("B0_hashes", all(sha(SO.path_of(k)) == v for k, v in b0.items()), list(b0))
    q7l = json.loads((QL / "tu4/rezultate/S25/Q7L_VERIFICARE_20261028T135344Z.json").read_text())
    r.check("B0_Q7L_11_11", q7l["verdict"] == "PASS" and q7l["n_pass"] == q7l["n_checks"] == 11)
    v0l = json.loads((QL / "tu4/rezultate/S25/V0L_VERIFICARE_20261028T135344Z.json").read_text())
    fails = [c.get("name") for c in v0l.get("checks", []) if not c.get("ok")]
    r.check("B0_V0L_28_29_incidente", v0l["n_checks"] == 29 and v0l["n_pass"] == 28 and fails == ["incidente"], fails)
    dec = json.loads(DEC_B0.read_text())
    r.check("B0_DECONTARE_PENDING", dec.get("verdict") == "DECONTARE_PENDING", dec.get("verdict"))
    r.check("sigiliu_S27_ce2a9f18", sha(QL / "tu4/SIGILIU_TU4_S27.json") == SEAL27_SHA)
    r.check("sigiliu_S28_0b4fd79b", sha(QL / "tu4/SIGILIU_TU4_S28.json") == SEAL28_SHA)
    r.check("sigiliu_A01_si_amendament", sha(A01_SEAL) == A01_SHA
            and sha(QL / "tu4/AMENDAMENT_S28_A01.md") == json.loads(A01_SEAL.read_text())["sha256"])
    r.check("sigiliu_S29_911af09c", sha(QL / "tu4/SIGILIU_TU4_S29.json") == SEAL29_SHA)
    d = frozen_drift()
    r.check("frozen_S30", not d, d)
    inc = incidents()
    r.check("incidente_9", inc == INCID9, inc)
    ok, bad = rust_ok()
    r.check("rust_27_0444_sha", ok, bad)
    me = Path(__file__).resolve()
    r.check("sigiliu_S30_si_verifica_s30_0444", sha(SEAL_PATH) == SEAL_SHA and me.stat().st_mode & 0o777 == 0o444,
            oct(me.stat().st_mode & 0o777))
    return r.finish({"seal_sha256": SEAL_SHA})


# ------------------------------------------------------------------ K1
def at_local(d: dt.date, hm: tuple[int, int]) -> dt.datetime:
    return dt.datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=TZ).astimezone(UTC)


def target_of(t: dt.datetime) -> dict:
    """Replică (S30): prima zi joi/duminică (Europe/Bucharest) cu cutoff 16:00 local > t; precedenta joi/duminică."""
    d = t.astimezone(TZ).date()
    while not (d.weekday() in (3, 6) and at_local(d, (16, 0)) > t):
        d += dt.timedelta(days=1)
    p = d - dt.timedelta(days=1)
    while p.weekday() not in (3, 6):
        p -= dt.timedelta(days=1)
    return {"target": d.isoformat(), "prev": p.isoformat(), "cutoff": at_local(d, (16, 0)), "final": at_local(d, (15, 0))}


def h_blocat(u: dt.datetime, last: str) -> tuple[str, str]:
    sc = target_of(u)
    complete = last >= sc["prev"]
    act = "postponed" if (not complete and u < sc["final"]) else ("emisie" if u < sc["cutoff"] else "late")
    return sc["target"], act


def systemd_to_zoneinfo_fmt(s: str) -> tuple[str, str]:
    """'Fri 2026-10-30 02:20:00 EDT' -> ('Fri', '2026-10-30 02:20 EDT')."""
    wd, date, hms, abbr = s.split()
    return wd, f"{date} {hms[:5]} {abbr}"


def k1() -> int:
    r = Report("K1")
    p1 = json.loads(P1_S29.read_text())
    mode = FISA29.stat().st_mode & 0o777
    r.check("fisa_S29_sha_mod_P1", sha(FISA29) == FISA29_SHA == p1.get("fisa_sha256") and mode == 0o444
            and p1["verdict"] == "PASS" and p1["n_pass"] == p1["n_checks"] == 15, {"mode": oct(mode)})
    f = json.loads(FISA29.read_text(encoding="utf-8"))
    v, s = f["verificare_C1_B5"], f["slot_final_emisie"]
    fields_ok = (v["utc"] == ["2026-11-01T13:36:00Z", "2026-11-01T13:57:59Z"] and v["laptop"] == ["08:36 EST", "08:57 EST"]
                 and v["strict"] is True and "PENDING/UNKNOWN" in v["ratare"] and "PENDING/UNKNOWN" in v["late"]
                 and s["utc"] == "2026-11-01T13:20:00Z" and s["bucuresti"] == "15:20 EET" and s["laptop"] == "08:20 EST"
                 and s["interzis_utc"] == ["2026-11-01T13:05:00Z", "2026-11-01T13:35:00Z"]
                 and f["tranzitie_laptop"]["utc"] == "2026-11-01T06:00:00Z" and f["positive_claims_allowed"] is False)
    r.check("fisa_S29_campuri", fields_ok, {"utc": v["utc"], "laptop": v["laptop"], "slot": s})
    # (3) zoneinfo
    a, b = T(v["utc"][0]), T(v["utc"][1])
    mins = [T("2026-11-01T13:36:00Z") + dt.timedelta(minutes=k) for k in range(22)]
    zi_ok = (ny(a, "%H:%M:%S %Z") == "08:36:00 EST" and ny(b, "%H:%M:%S %Z") == "08:57:59 EST"
             and [ny(t) for t in mins] == [f"2026-11-01 08:{m:02d} EST" for m in range(36, 58)]
             and ny(T(s["utc"]), "%H:%M %Z") == "08:20 EST" and T(s["utc"]).astimezone(TZ).strftime("%H:%M %Z") == "15:20 EET")
    r.check("zoneinfo_capete_08_36_00_08_57_59_EST", zi_ok, [ny(a, "%H:%M:%S %Z"), ny(b, "%H:%M:%S %Z")])
    # (4) cele 9 sloturi
    rows, bad = f["sloturi_H_BLOCAT"], []
    for x in rows:
        u = T(x["slot_utc"])
        wd, sysd = systemd_to_zoneinfo_fmt(x["laptop_systemd"])
        tgt, act = h_blocat(u, LAST_BLOCAT)
        if not (x["laptop_zoneinfo"] == ny(u) == sysd and wd == u.astimezone(NY).strftime("%a")
                and x["bucuresti"] == buc(u) and x["tinta"] == tgt == "2026-11-01" and x["H_BLOCAT"] == act):
            bad.append({"slot": x["slot_utc"], "ny": ny(u), "buc": buc(u), "act": act})
    r.check("sloturi_9_rederivate_8_postponed_1_emisie", len(rows) == 9 and not bad
            and [x["H_BLOCAT"] for x in rows] == ["postponed"] * 8 + ["emisie"], bad)
    # (5) zdump
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
    # (6) fereastra
    forb = {x: SO.window(T(x), DRAW) for x in ("2026-11-01T13:20:00Z", "2026-11-01T13:35:00Z")}
    free = {z(t): SO.window(t, DRAW) for t in mins}
    r.check("fereastra_13_36_13_57_libera_13_35_interzis_13_58_exclus",
            all(forb.values()) and all(x is None for x in free.values()) and not any(minute_excluded(t) for t in mins)
            and minute_excluded(T("2026-11-01T13:58:00Z")), {"forb": forb, "nelibere": {k: x for k, x in free.items() if x}})
    # (7) alinierea cu CALENDAR_S28 și sigiliul S29
    cal = json.loads(CAL28.read_text(encoding="utf-8"))
    s29 = json.loads((QL / "tu4/SIGILIU_TU4_S29.json").read_text(encoding="utf-8"))
    cal_sha_ok = sha(CAL28) == s29["frozen_hashes"]["tu4/rezultate/S28/CALENDAR_S28.json"]
    cal_rows = [(x["slot_utc"], x["H_BLOCAT"]) for x in cal["emisie_2026_11_01"]["sloturi"]]
    fisa_rows = [(x["slot_utc"], x["H_BLOCAT"]) for x in rows]
    cvf = cal["verificare_finala_C1_B5"]
    sr = s29["sunday_rule"]
    align_ok = (cal_sha_ok and cal_rows == fisa_rows
                and cvf["utc"] == ["2026-11-01T13:36:00Z", "2026-11-01T13:57:00Z"]
                and T(cvf["utc"][1]).replace(second=0) == T(v["utc"][1]).replace(second=0)
                and sr["verificare_C1_B5_utc"] == v["utc"] and sr["verificare_C1_B5_laptop"] == v["laptop"]
                and sr["strict"] is True and sr["slot_final_utc"] == s["utc"] and sr["slot_final_laptop"] == s["laptop"])
    r.check("aliniere_CALENDAR_S28_si_sigiliu_S29", align_ok,
            {"cal_sha_ok": cal_sha_ok, "rows_eq": cal_rows == fisa_rows, "cal_C1B5": cvf["utc"]})
    # (8) tabelul alinierii
    alin = {
        "fisa": "ALINIERE_FISE_S30", "protocol": "TU4-S30 §2, §3 K1", "cerere": "Mesajul 81 (2026-10-28T13:50:35Z)",
        "surse": {"FISA_DUMINICA_S29.json": FISA29_SHA, "CALENDAR_S28.json": sha(CAL28),
                  "SIGILIU_TU4_S29.json#sunday_rule": SEAL29_SHA},
        "verificare_C1_B5": {
            "FISA_DUMINICA_S29": {"utc": v["utc"], "laptop": v["laptop"], "strict": v["strict"]},
            "CALENDAR_S28": {"utc": cvf["utc"], "laptop": cvf["laptop"], "nota": "capătul 13:57:00Z = începutul ultimului minut"},
            "SIGILIU_S29": {"utc": sr["verificare_C1_B5_utc"], "laptop": sr["verificare_C1_B5_laptop"], "strict": sr["strict"]},
            "zoneinfo_S30": [ny(a, "%Y-%m-%d %H:%M:%S %Z"), ny(b, "%Y-%m-%d %H:%M:%S %Z")],
        },
        "slot_final_emisie": {"utc": s["utc"], "bucuresti": buc(T(s["utc"])), "laptop": ny(T(s["utc"]))},
        "sloturi": [{"slot_utc": x["slot_utc"], "fisa_S29": x["H_BLOCAT"], "calendar_S28": dict(cal_rows).get(x["slot_utc"]),
                     "replica_S30": h_blocat(T(x["slot_utc"]), LAST_BLOCAT)[1], "laptop": ny(T(x["slot_utc"])),
                     "bucuresti": buc(T(x["slot_utc"]))} for x in rows],
        "martori": ["zoneinfo", "zdump", "sonda_s27.window (înghețat)"],
        "limita": "zoneinfo și zdump pot citi aceeași bază tzdata; independenți de codul QL649, nu de tzdata",
        "fisa_S29_rescrisa": False,
        "positive_claims_allowed": False,
    }
    ash = write_ro(OUT / "ALINIERE_FISE_S30.json", json.dumps(alin, indent=2, ensure_ascii=False) + "\n")
    r.check("aliniere_scrisa_0444", (OUT / "ALINIERE_FISE_S30.json").stat().st_mode & 0o777 == 0o444, ash[:8])
    return r.finish({"aliniere_sha256": ash})


# ------------------------------------------------------------------ K2
def k2() -> int:
    r = Report("K2")
    live = json.loads((QL / "tu3/date/live/CURRENT_LIVE.json").read_text(encoding="utf-8"))
    ld = {g: x["last_date"] for g, x in live["games"].items()}
    r.check("LIVE_last_date_2026_10_25_x3", ld == {"649": LAST_BLOCAT, "540": LAST_BLOCAT, "joker": LAST_BLOCAT}, ld)
    win = {x: SO.window(T(x), DRAW) for x in ("2026-10-29T16:15:00Z", "2026-10-29T16:30:00Z", "2026-10-29T16:45:00Z",
                                              "2026-10-29T16:46:00Z", "2026-10-29T18:35:00Z")}
    ok_win = (all(win[x] for x in ("2026-10-29T16:15:00Z", "2026-10-29T16:30:00Z", "2026-10-29T16:45:00Z"))
              and win["2026-10-29T16:46:00Z"] is None and win["2026-10-29T18:35:00Z"] is None
              and not minute_excluded(T("2026-10-29T16:46:00Z")) and not minute_excluded(T("2026-10-29T18:35:00Z")))
    r.check("extragere_16_30Z_18_30_EET_12_30_EDT_ferestre", ok_win and buc(DRAW) == "2026-10-29 18:30 EET"
            and ny(DRAW) == "2026-10-29 12:30 EDT", win)
    decs = sorted((QL / "tu4/rezultate/S24").glob("DECONTARE_20261029_*.json"))
    last = json.loads(decs[-1].read_text()) if decs else {}
    cal = json.loads(CAL28.read_text(encoding="utf-8"))
    hb = cal["decontare_2026_10_29"]["H_BLOCAT"]
    r.check("decontare_curenta_PENDING_si_CALENDAR_S28", bool(decs) and decs[-1] == DEC_B0
            and last.get("verdict") == "DECONTARE_PENDING" and last.get("n_decontate") == 0
            and all(k in hb for k in ("DECONTARE_PENDING", "2026-10-29T18:30:00Z", "VOID")),
            {"ultima": decs[-1].name if decs else None, "verdict": last.get("verdict"), "H_BLOCAT": hb})
    so_src = (QL / "tu4/s27/sonda_s27.py").read_text(encoding="utf-8")
    fz = SEAL["frozen_hashes"]
    r.check("sonda_si_judecator_inghetate", sha(QL / "tu4/s27/sonda_s27.py") == fz["tu4/s27/sonda_s27.py"]
            and sha(QL / "tu4/judecator.py") == fz["tu4/judecator.py"]
            and "AVERTISMENT_DECONTARE_BLOCATA" in so_src and "FAZA_0_ASTEAPTA_DECONTAREA" in so_src)
    moments = ["2026-10-29T16:46:00Z", "2026-10-29T17:00:00Z", "2026-10-29T18:00:00Z", "2026-10-29T18:30:00Z",
               "2026-10-29T19:00:00Z"]
    table = []
    for m in moments:
        t = T(m)
        state = "DECONTARE_PENDING" if min(ld.values()) < "2026-10-29" else "DECONTABILA"
        table.append({"utc": m, "laptop": ny(t), "bucuresti": buc(t), "stare": state,
                      "AVERTISMENT_DECONTARE_BLOCATA": t >= DRAW + dt.timedelta(hours=2)})
    r.check("replica_joi_PENDING_avertisment_de_la_18_30Z",
            all(x["stare"] == "DECONTARE_PENDING" for x in table)
            and [x["AVERTISMENT_DECONTARE_BLOCATA"] for x in table] == [False, False, False, True, True], table)
    fisa = {
        "fisa": "FISA_JOI_S30", "protocol": "TU4-S30 §2 (joi)", "cerere": "Mesajul 81 (2026-10-28T13:50:35Z)",
        "data": "2026-10-29",
        "extragere": {"utc": z(DRAW), "bucuresti": buc(DRAW), "laptop": ny(DRAW),
                      "interzis_utc": ["2026-10-29T16:15:00Z", "2026-10-29T16:45:00Z"]},
        "H_BLOCAT": {"live_last_date": ld, "garda": "loto_romania/cohorta.py:163 NEATINSĂ (gpu-v1)",
                     "stare_acceptata": "DECONTARE_PENDING după 16:45Z, cât timp arhiva LIVE nu conține 2026-10-29",
                     "avertisment": "AVERTISMENT_DECONTARE_BLOCATA în sondă de la 2026-10-29T18:30:00Z",
                     "void": cal["decontare_2026_10_29"]["H_BLOCAT"],
                     "tabel": table},
        "H_ACTUALIZAT": cal["decontare_2026_10_29"]["H_ACTUALIZAT"] + " (numai după sesiunea dedicată; nu în S30)",
        "interventii_interzise": ["repararea/legitimarea/investigarea gărzii gpu-v1", "forțarea actualizării arhivei LIVE",
                                  "decontare manuală", "editarea LANT.jsonl/tribunalului", "modificarea timerelor/unităților",
                                  "sudo", "chmod pe fișiere înghețate"],
        "sonda": "cd " + QLD + " && date -u && /usr/bin/python3 -B tu4/s27/sonda_s27.py; echo SONDA_RC=$?  "
                 "(oricând în afara ferestrelor; zero scrieri; așteptat FAZA_0_ASTEAPTA_DECONTAREA)",
        "sesiune_dedicata": "cere decizia utilizatorului și protocol propriu; S30 nu o planifică și nu o pornește",
        "positive_claims_allowed": False,
    }
    fsh = write_ro(OUT / "FISA_JOI_S30.json", json.dumps(fisa, indent=2, ensure_ascii=False) + "\n")
    r.check("fisa_joi_scrisa_0444", (OUT / "FISA_JOI_S30.json").stat().st_mode & 0o777 == 0o444, fsh[:8])
    return r.finish({"fisa_joi_sha256": fsh})


# ------------------------------------------------------------------ K3
def k3() -> int:
    r = Report("K3")
    d = frozen_drift()
    r.check("frozen_S30_neschimbate", not d, d)
    r.check("sigilii_S27_S28_A01_S29_S30", sha(SEAL_PATH) == SEAL_SHA and sha(QL / "tu4/SIGILIU_TU4_S29.json") == SEAL29_SHA
            and sha(QL / "tu4/SIGILIU_TU4_S28.json") == SEAL28_SHA and sha(QL / "tu4/SIGILIU_TU4_S27.json") == SEAL27_SHA
            and sha(A01_SEAL) == A01_SHA)
    e = external_drift()
    s29 = json.loads((QL / "tu4/SIGILIU_TU4_S29.json").read_text())
    r.check("externe_garda_unitate_timere_neschimbate", not e
            and SEAL["external_nonintervention"] == s29["external_nonintervention"], e)
    lines = (ROOT / "loto_romania/cohorta.py").read_text(encoding="utf-8").splitlines()
    r.check("garda_linia_163_neatinsa", len(lines) >= 163 and lines[162].strip() == GUARD163, lines[162].strip()[:120])
    ok, bad = rust_ok()
    r.check("rust_27_0444_sha", ok, bad)
    inc = incidents()
    r.check("incidente_9", inc == INCID9, inc)
    lb = (QL / "tu4/tribunal/LANT.jsonl").read_bytes()
    snap = SEAL["lant_snapshot_S30"]
    r.check("LANT_eq_instantaneu", hashlib.sha256(lb).hexdigest() == snap["sha256"] and len(lb) == snap["bytes"],
            {"bytes": len(lb), "lines": len(lb.splitlines())})
    s30 = sorted(f.name for f in (QL / "tu4/s30").iterdir())
    r.check("s30_numai_verificator_0444", s30 == ["verifica_s30.py"]
            and (QL / "tu4/s30/verifica_s30.py").stat().st_mode & 0o777 == 0o444, s30)
    act = {u: run(["systemctl", "--user", "is-active", u]).stdout.strip()
           for u in ("loto-actualizare.timer", "ql649-tu4-emitere.timer")}
    r.check("timere_active", all(x == "active" for x in act.values()), act)
    r.check("fisa_duminica_S29_neschimbata", sha(FISA29) == FISA29_SHA and FISA29.stat().st_mode & 0o777 == 0o444)
    return r.finish()


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("k0", "k1", "k2", "k3"):
        print(__doc__)
        return 2
    crit = argv[0].upper()
    if not once(crit):
        print(f"REFUZ {crit}: rulat deja (o singură rulare per criteriu)")
        return 2
    w = gate()
    if w:
        print(f"UNKNOWN_FEREASTRA {crit}: {w} (fără scrieri)")
        return 3
    return {"K0": k0, "K1": k1, "K2": k2, "K3": k3}[crit]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
