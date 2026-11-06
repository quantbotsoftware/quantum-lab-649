"""Verificatorul S29 (protocol tu4/PROTOCOL_QUANTUM_S29.md §3). Scris DUPĂ sigiliul S29 (911af09c…); scrie numai fișiere
noi în tu4/rezultate/S29/ (0444): <crit>_VERIFICARE_<UTC>.json, iar P1 încă FISA_DUMINICA_S29.json.
Utilizare:  verifica_s29.py p0 | p1 | p2      (fiecare O SINGURĂ DATĂ; în fereastră: rc 3 fără scrieri)
Nu citește numerele extragerilor, nu rulează binarul Rust, nu atinge garda externă (numai citire/hash). Calcul clasic;
positive_claims_allowed=false.
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
OUT = QL / "tu4/rezultate/S29"
SEAL_PATH = QL / "tu4/SIGILIU_TU4_S29.json"
SEAL_SHA = "911af09ca6fb11b10129655aad04e7f6f477aac517cdefc887e2164be8d8fa37"
SEAL27_SHA = "ce2a9f1816dd5de4a8e22e98e3e4566de7267def2142b23122be2374b9f9bc13"
SEAL28_SHA = "0b4fd79b0323532241504a0b04368d50c8aa754a8bb687d0c5030dc9abb4a138"
A01_SEAL = QL / "tu4/SIGILIU_AMENDAMENT_S28_A01.json"
A01_SHA = "b44ffea37fb7d8b357491648c28a833a97434ff620a88b17f8f290f78fcd1d79"
SEAL = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
MAN22 = QL / "tu4/rezultate/S22/MANIFEST_RUST_CORE_20261028T032900Z.json"
UTC = dt.timezone.utc
TZ = ZoneInfo("Europe/Bucharest")
NY = ZoneInfo("America/New_York")
DRAW = dt.datetime(2026, 10, 29, 16, 30, tzinfo=UTC)
INCID9 = ["EM_01", "FR_01", "S19_01", "S20_01", "S23_01", "S23_02", "S23_03", "S24_01", "SM1_01"]
GUARD163 = "raise ValueError('Model/environment changed after protocol freeze: ' + model)"
QLD = "."

sys.path.insert(0, str(QL / "tu4/s27"))
sys.path.insert(0, str(QL / "tu4/s25"))
sys.path.insert(0, str(QL / "tu4/s24"))
import sonda_s27 as SO  # noqa: E402  (cod S27 înghețat; numai window/path_of/MARGIN)


def utc_now() -> str:
    return dt.datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def z(t: dt.datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ny(t: dt.datetime) -> str:
    return t.astimezone(NY).strftime("%Y-%m-%d %H:%M %Z")


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
               "run_utc": stamp, "protocol": "TU4-S29", "checks": self.checks, "positive_claims_allowed": False}
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


def gate() -> str | None:
    """Fereastra §1 (sonda_s27.window) + minutele [:58,:04) și [:28,:34); None = liber."""
    now = dt.datetime.now(UTC)
    w = SO.window(now, DRAW)
    if w:
        return w
    if now.minute >= 58 or now.minute < 4 or 28 <= now.minute < 34:
        return f"minutul {now.minute} exclus"
    return None


def minute_excluded(t: dt.datetime) -> bool:
    return t.minute >= 58 or t.minute < 4 or 28 <= t.minute < 34


def once(crit: str) -> bool:
    return not list(OUT.glob(f"{crit}_VERIFICARE_*.json"))


# ------------------------------------------------------------------ P0
def p0() -> int:
    r = Report("P0")
    vp = json.loads((QL / "predari/VERIFICARE_PREDARE_20261028T125934Z.json").read_text())
    for f in ("HANDOFF_QL649_20261028T125934Z.md", "PROMPT_QL649_20261028T125934Z.txt"):
        r.check(f"predare_{f}", sha(QL / "predari" / f) == vp[f]["sha256"] and vp[f]["canon_once"] and vp[f]["supl_once"],
                vp[f]["sha256"][:8])
    b0 = SEAL["baseline_B0"]
    r.check("B0_hashes", all(sha(SO.path_of(k)) == v for k, v in b0.items()), list(b0))
    q7l = json.loads((QL / "tu4/rezultate/S25/Q7L_VERIFICARE_20261028T133940Z.json").read_text())
    r.check("B0_Q7L_11_11", q7l["verdict"] == "PASS" and q7l["n_pass"] == q7l["n_checks"] == 11)
    v0l = json.loads((QL / "tu4/rezultate/S25/V0L_VERIFICARE_20261028T133940Z.json").read_text())
    fails = [c.get("name") for c in v0l.get("checks", []) if not c.get("ok")]
    r.check("B0_V0L_28_29_incidente", v0l["n_checks"] == 29 and v0l["n_pass"] == 28 and fails == ["incidente"], fails)
    r.check("sigiliu_S27_ce2a9f18", sha(QL / "tu4/SIGILIU_TU4_S27.json") == SEAL27_SHA)
    r.check("sigiliu_S28_0b4fd79b", sha(QL / "tu4/SIGILIU_TU4_S28.json") == SEAL28_SHA)
    r.check("sigiliu_A01_si_amendament", sha(A01_SEAL) == A01_SHA
            and sha(QL / "tu4/AMENDAMENT_S28_A01.md") == json.loads(A01_SEAL.read_text())["sha256"])
    r.check("sigiliu_S29", sha(SEAL_PATH) == SEAL_SHA)
    d = frozen_drift()
    r.check("frozen_S29", not d, d)
    inc = incidents()
    r.check("incidente_9", inc == INCID9, inc)
    ok, bad = rust_ok()
    r.check("rust_27_0444_sha", ok, bad)
    me = Path(__file__).resolve()
    r.check("verifica_s29_0444", me.stat().st_mode & 0o777 == 0o444, oct(me.stat().st_mode & 0o777))
    return r.finish({"seal_sha256": SEAL_SHA})


# ------------------------------------------------------------------ P1
def at_local(d: dt.date, hm: tuple[int, int]) -> dt.datetime:
    return dt.datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=TZ).astimezone(UTC)


def target_of(t: dt.datetime) -> dict:
    """Replică independentă: prima zi joi/duminică (Europe/Bucharest) cu cutoff 16:00 > t; precedenta joi/duminică."""
    d = t.astimezone(TZ).date()
    while not (d.weekday() in (3, 6) and at_local(d, (16, 0)) > t):
        d += dt.timedelta(days=1)
    p = d - dt.timedelta(days=1)
    while p.weekday() not in (3, 6):
        p -= dt.timedelta(days=1)
    return {"target": d.isoformat(), "prev": p.isoformat(), "cutoff": at_local(d, (16, 0)),
            "final": at_local(d, (15, 0)), "draw": at_local(d, (18, 30))}


def parse_systemd_calendar(text: str) -> list[tuple[str, dt.datetime]]:
    """Perechi (linia locală, momentul UTC) din ieșirea `systemd-analyze calendar`."""
    pairs, local = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("Next elapse:") or s.startswith("Iteration #"):
            local = s.split(": ", 1)[1].strip()
        elif s.startswith("(in UTC):"):
            u = dt.datetime.strptime(s.split(": ", 1)[1].strip(), "%a %Y-%m-%d %H:%M:%S UTC").replace(tzinfo=UTC)
            pairs.append((local, u))
            local = None
    return pairs


def p1() -> int:
    r = Report("P1")
    tz = run(["timedatectl", "show", "-p", "Timezone", "--value"])
    r.check("fus_laptop_America_New_York", tz.returncode == 0 and tz.stdout.strip() == "America/New_York", tz.stdout.strip())
    # (2) zoneinfo
    ny_ok = (T("2026-11-01T05:59:59Z").astimezone(NY).utcoffset() == dt.timedelta(hours=-4)
             and T("2026-11-01T06:00:00Z").astimezone(NY).utcoffset() == dt.timedelta(hours=-5))
    t0 = T("2026-10-26T00:00:00Z")
    buc_bad = [z(t0 + dt.timedelta(hours=k)) for k in range(0, 24 * 7 + 1)
               if (t0 + dt.timedelta(hours=k)).astimezone(TZ).utcoffset() != dt.timedelta(hours=2)]
    r.check("zoneinfo_NY_EDT_EST_si_Bucuresti_EET", ny_ok and not buc_bad, {"ny_ok": ny_ok, "buc_bad": buc_bad[:5]})
    # (3) zdump
    zn = run(["zdump", "-v", "-c", "2026,2027", "America/New_York"])
    zb = run(["zdump", "-v", "-c", "2026,2027", "Europe/Bucharest"])
    want_ny = ["America/New_York  Sun Nov  1 05:59:59 2026 UT = Sun Nov  1 01:59:59 2026 EDT isdst=1 gmtoff=-14400",
               "America/New_York  Sun Nov  1 06:00:00 2026 UT = Sun Nov  1 01:00:00 2026 EST isdst=0 gmtoff=-18000"]
    zn_lines = [x.rstrip() for x in zn.stdout.splitlines()]
    r.check("zdump_NY_tranzitie_2026_11_01_06Z", zn.returncode == 0 and all(w in zn_lines for w in want_ny),
            [x for x in zn_lines if "Nov" in x])
    zb_dated = [x.rstrip() for x in zb.stdout.splitlines() if " UT = " in x]
    want_b = "Europe/Bucharest  Sun Oct 25 01:00:00 2026 UT = Sun Oct 25 03:00:00 2026 EET isdst=0 gmtoff=7200"
    r.check("zdump_Bucuresti_ultima_2026_10_25_EET", zb.returncode == 0 and bool(zb_dated) and zb_dated[-1] == want_b,
            zb_dated[-2:])
    # (4) systemd calendar pe expresiile timerului instalat
    inst = Path("~/.config/systemd/user/ql649-tu4-emitere.timer")
    ref = QL / "tu4/systemd/ql649-tu4-emitere.timer"
    exprs = [ln.split("=", 1)[1].strip() for ln in inst.read_text().splitlines() if ln.startswith("OnCalendar=")]
    r.check("timer_instalat_eq_ref_3_expresii", sha(inst) == sha(ref) and exprs == [
        "*-*-* 08:20:00 Europe/Bucharest", "*-*-* 12:20:00 Europe/Bucharest", "*-*-* 15:20:00 Europe/Bucharest"], exprs)
    pairs, rcs, raw = [], [], {}
    for e in exprs:
        c = run(["systemd-analyze", "calendar", "--iterations=4", "--base-time=2026-10-29 14:00:00 UTC", e])
        rcs.append(c.returncode)
        raw[e] = c.stdout.splitlines()
        pairs += parse_systemd_calendar(c.stdout)
    lo, hi = T("2026-10-29T14:00:00Z"), T("2026-11-01T14:00:00Z")
    inside = sorted((u, loc) for loc, u in pairs if lo < u < hi)
    want9 = [z(dt.datetime(2026, m, d, h, 20, tzinfo=UTC)) for (m, d) in ((10, 30), (10, 31), (11, 1)) for h in (6, 10, 13)]
    got9 = [z(u) for u, _ in inside]
    r.check("systemd_rc0", rcs == [0, 0, 0], rcs)
    r.check("systemd_9_sloturi_A01", got9 == want9, got9)
    locmap = {z(u): loc for u, loc in inside}
    r.check("systemd_local_EST_duminica", locmap.get("2026-11-01T13:20:00Z") == "Sun 2026-11-01 08:20:00 EST"
            and locmap.get("2026-11-01T06:20:00Z") == "Sun 2026-11-01 01:20:00 EST",
            {k: locmap.get(k) for k in ("2026-11-01T06:20:00Z", "2026-11-01T10:20:00Z", "2026-11-01T13:20:00Z")})
    # (5) H_BLOCAT pe cele 9 sloturi systemd
    LAST = "2026-10-25"
    rows = []
    for u, loc in inside:
        sc = target_of(u)
        complete = LAST >= sc["prev"]
        act = "postponed" if (not complete and u < sc["final"]) else ("emisie" if u < sc["cutoff"] else "late")
        rows.append({"slot_utc": z(u), "laptop_systemd": loc, "laptop_zoneinfo": ny(u),
                     "bucuresti": u.astimezone(TZ).strftime("%Y-%m-%d %H:%M %Z"), "tinta": sc["target"], "H_BLOCAT": act})
    r.check("H_BLOCAT_8_postponed_1_emisie", [x["H_BLOCAT"] for x in rows] == ["postponed"] * 8 + ["emisie"]
            and all(x["tinta"] == "2026-11-01" for x in rows), [x["H_BLOCAT"] for x in rows])
    # (6) următoarea declanșare reală a timerului instalat
    ne = run(["systemctl", "--user", "show", "ql649-tu4-emitere.timer", "-p", "NextElapseUSecRealtime", "--value"])
    r.check("timer_next_elapse_joi_06_20Z", ne.returncode == 0 and ne.stdout.strip() == "Thu 2026-10-29 02:20:00 EDT",
            ne.stdout.strip())
    # (7) fereastra de duminică
    forb = {x: SO.window(T(x), DRAW) for x in ("2026-11-01T13:20:00Z", "2026-11-01T13:35:00Z")}
    mins = [T("2026-11-01T13:36:00Z") + dt.timedelta(minutes=k) for k in range(22)]
    free = {z(t): SO.window(t, DRAW) for t in mins}
    r.check("duminica_13_20_si_13_35_interzise", all(forb.values()), forb)
    r.check("duminica_13_36_13_57_libere_22", len(mins) == 22 and z(mins[-1]) == "2026-11-01T13:57:00Z"
            and all(v is None for v in free.values()) and not any(minute_excluded(t) for t in mins),
            {k: v for k, v in free.items() if v})
    r.check("duminica_13_58_minut_exclus", minute_excluded(T("2026-11-01T13:58:00Z")))
    est = [ny(t) for t in mins]
    r.check("duminica_08_36_08_57_EST", est == [f"2026-11-01 08:{m:02d} EST" for m in range(36, 58)], [est[0], est[-1]])
    # (8) fișa formală
    fisa = {
        "fisa": "FISA_DUMINICA_S29", "protocol": "TU4-S29 §2", "cerere": "Mesajul 80 (2026-10-28T13:06:40Z)",
        "data": "2026-11-01",
        "tranzitie_laptop": {"fus": tz.stdout.strip(), "utc": "2026-11-01T06:00:00Z", "din": "EDT (UTC-4)", "in": "EST (UTC-5)",
                             "martori": ["zoneinfo", "zdump", "systemd-analyze calendar"]},
        "fus_timere_QL649": "Europe/Bucharest (EET = UTC+2 din 2026-10-25T01:00Z)",
        "slot_final_emisie": {"utc": "2026-11-01T13:20:00Z", "bucuresti": "15:20 EET", "laptop": "08:20 EST",
                              "interzis_utc": ["2026-11-01T13:05:00Z", "2026-11-01T13:35:00Z"]},
        "verificare_C1_B5": {"utc": ["2026-11-01T13:36:00Z", "2026-11-01T13:57:59Z"], "laptop": ["08:36 EST", "08:57 EST"],
                             "strict": True,
                             "precondite": "date -u în [13:36:00Z, 13:57:59Z]; SSD montat; 8649 activ",
                             "pasi": ["cd " + QLD + " && date -u && /usr/bin/python3 -B tu4/s27/sonda_s27.py; echo SONDA_RC=$?"
                                      " (așteptat FAZA_4)",
                                      "L=$PWD/tu4/rezultate/S25/primul_pas_S26_$(date -u +%Y%m%dT%H%M%SZ).log && bash "
                                      "tu4/rezultate/S25/primul_pas_S26.sh > \"$L\" 2>&1; /usr/bin/python3 -B "
                                      "tu4/s25/verifica_s25.py q7l \"$L\""],
                             "ratare": "C1/B5 rămân PENDING/UNKNOWN; altă fereastră numai cu protocol nou",
                             "late": "dacă emisia dă late, C1/B5 rămân PENDING/UNKNOWN, fără PASS"},
        "nota_coliziuni": "înainte de 13:36Z: fereastra emisiei 13:20Z; 13:58Z–14:04Z: minutele actualizării/judecătorului "
                          "(14:00:30Z) și cutoff 14:00Z; restricția strictă este a utilizatorului (Mesajul 80)",
        "sloturi_H_BLOCAT": rows,
        "garda_externa": "loto_romania/cohorta.py:163 NEATINSĂ (sesiune dedicată separată)",
        "positive_claims_allowed": False,
    }
    fsha = write_ro(OUT / "FISA_DUMINICA_S29.json", json.dumps(fisa, indent=2, ensure_ascii=False) + "\n")
    r.check("fisa_scrisa_0444", (OUT / "FISA_DUMINICA_S29.json").stat().st_mode & 0o777 == 0o444, fsha[:8])
    return r.finish({"fisa_sha256": fsha, "systemd_raw": raw})


# ------------------------------------------------------------------ P2
def p2() -> int:
    r = Report("P2")
    d = frozen_drift()
    r.check("frozen_S29_neschimbate", not d, d)
    r.check("sigilii_S27_S28_A01_S29", sha(SEAL_PATH) == SEAL_SHA and sha(QL / "tu4/SIGILIU_TU4_S28.json") == SEAL28_SHA
            and sha(QL / "tu4/SIGILIU_TU4_S27.json") == SEAL27_SHA and sha(A01_SEAL) == A01_SHA)
    e = external_drift()
    s28 = json.loads((QL / "tu4/SIGILIU_TU4_S28.json").read_text())
    r.check("externe_garda_unitate_timere_neschimbate", not e
            and SEAL["external_nonintervention"] == s28["external_nonintervention"], e)
    lines = (ROOT / "loto_romania/cohorta.py").read_text(encoding="utf-8").splitlines()
    r.check("garda_linia_163_neatinsa", len(lines) >= 163 and lines[162].strip() == GUARD163, lines[162].strip()[:120])
    ok, bad = rust_ok()
    r.check("rust_27_0444_sha", ok, bad)
    inc = incidents()
    r.check("incidente_9", inc == INCID9, inc)
    lb = (QL / "tu4/tribunal/LANT.jsonl").read_bytes()
    snap = SEAL["lant_snapshot_S29"]
    r.check("LANT_eq_instantaneu", hashlib.sha256(lb).hexdigest() == snap["sha256"] and len(lb) == snap["bytes"],
            {"bytes": len(lb), "lines": len(lb.splitlines())})
    s29 = sorted(f.name for f in (QL / "tu4/s29").iterdir())
    r.check("s29_numai_verificator_0444", s29 == ["verifica_s29.py"]
            and (QL / "tu4/s29/verifica_s29.py").stat().st_mode & 0o777 == 0o444, s29)
    act = {u: run(["systemctl", "--user", "is-active", u]).stdout.strip()
           for u in ("loto-actualizare.timer", "ql649-tu4-emitere.timer")}
    r.check("timere_active", all(v == "active" for v in act.values()), act)
    return r.finish()


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("p0", "p1", "p2"):
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
    return {"P0": p0, "P1": p1, "P2": p2}[crit]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
