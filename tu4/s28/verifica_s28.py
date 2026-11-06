"""Verificatorul S28 (protocol tu4/PROTOCOL_QUANTUM_S28.md §3 + AMENDAMENT_S28_A01). Scris DUPĂ sigiliul S28 și după
sigiliul amendamentului A01; scrie numai fișiere noi în tu4/rezultate/S28/ (0444): <crit>_VERIFICARE_<UTC>.json, iar P1
și P2 încă AVERTISMENT_EXTERN_S28.json + JURNAL_GPU_V1_S28.txt, respectiv CALENDAR_S28.json.
Utilizare:  verifica_s28.py p0 | p1 | p2 | p3      (fiecare O SINGURĂ DATĂ; în fereastră: rc 3 fără scrieri)
Nu citește numerele extragerilor, nu rulează binarul Rust, nu atinge garda externă. Calcul clasic;
positive_claims_allowed=false.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import datetime as dt  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

QL = Path("${QL649_ROOT:-.}")
ROOT = Path("${LOTO_RO_ROOT:-.}")
OUT = QL / "tu4/rezultate/S28"
SEAL_PATH = QL / "tu4/SIGILIU_TU4_S28.json"
SEAL_SHA = "0b4fd79b0323532241504a0b04368d50c8aa754a8bb687d0c5030dc9abb4a138"
AMEND_SEAL = QL / "tu4/SIGILIU_AMENDAMENT_S28_A01.json"
AMEND_SEAL_SHA = "b44ffea37fb7d8b357491648c28a833a97434ff620a88b17f8f290f78fcd1d79"
SEAL27_SHA = "ce2a9f1816dd5de4a8e22e98e3e4566de7267def2142b23122be2374b9f9bc13"
SEAL = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
MAN22 = QL / "tu4/rezultate/S22/MANIFEST_RUST_CORE_20261028T032900Z.json"
UTC = dt.timezone.utc
TZ = ZoneInfo("Europe/Bucharest")
NY = ZoneInfo("America/New_York")
DRAW = dt.datetime(2026, 10, 29, 16, 30, tzinfo=UTC)
INCID9 = ["EM_01", "FR_01", "S19_01", "S20_01", "S23_01", "S23_02", "S23_03", "S24_01", "SM1_01"]

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


def ny(t: dt.datetime) -> str:
    return t.astimezone(NY).strftime("%Y-%m-%d %H:%M %Z")


def write_ro(path: Path, text: str) -> str:
    assert not path.exists(), path
    path.write_text(text, encoding="utf-8")
    path.chmod(0o444)
    return sha(path)


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
               "run_utc": stamp, "protocol": "TU4-S28 (+A01)", "checks": self.checks, "positive_claims_allowed": False}
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


def once(crit: str) -> bool:
    return not list(OUT.glob(f"{crit}_VERIFICARE_*.json"))


# ------------------------------------------------------------------ P0
def p0() -> int:
    r = Report("P0")
    vp = json.loads((QL / "predari/VERIFICARE_PREDARE_20261028T124151Z.json").read_text())
    for f in ("HANDOFF_QL649_20261028T124151Z.md", "PROMPT_QL649_20261028T124151Z.txt"):
        r.check(f"predare_{f}", sha(QL / "predari" / f) == vp[f]["sha256"] and vp[f]["canon_once"] and vp[f]["supl_once"],
                vp[f]["sha256"][:8])
    b0 = SEAL["baseline_B0"]
    r.check("B0_hashes", all(sha(SO.path_of(k)) == v for k, v in b0.items()), list(b0))
    q7l = json.loads((QL / "tu4/rezultate/S25/Q7L_VERIFICARE_20261028T124747Z.json").read_text())
    r.check("B0_Q7L_11_11", q7l["verdict"] == "PASS" and q7l["n_pass"] == q7l["n_checks"] == 11)
    v0l = json.loads((QL / "tu4/rezultate/S25/V0L_VERIFICARE_20261028T124747Z.json").read_text())
    fails = [c.get("name") for c in v0l.get("checks", []) if not c.get("ok")]
    r.check("B0_V0L_28_29_incidente", v0l["n_checks"] == 29 and v0l["n_pass"] == 28 and fails == ["incidente"], fails)
    r.check("sigiliu_S27_ce2a9f18", sha(QL / "tu4/SIGILIU_TU4_S27.json") == SEAL27_SHA)
    r.check("sigiliu_S28", sha(SEAL_PATH) == SEAL_SHA)
    r.check("sigiliu_A01", sha(AMEND_SEAL) == AMEND_SEAL_SHA
            and sha(QL / "tu4/AMENDAMENT_S28_A01.md") == json.loads(AMEND_SEAL.read_text())["sha256"])
    d = frozen_drift()
    r.check("frozen_S28", not d, d)
    inc = incidents()
    r.check("incidente_9", inc == INCID9, inc)
    ok, bad = rust_ok()
    r.check("rust_27_0444_sha", ok, bad)
    me = Path(__file__).resolve()
    r.check("verifica_s28_0444", me.stat().st_mode & 0o777 == 0o444, oct(me.stat().st_mode & 0o777))
    return r.finish({"seal_sha256": SEAL_SHA})


# ------------------------------------------------------------------ P1
def p1() -> int:
    r = Report("P1")
    now = dt.datetime.now(UTC)
    cmd = ["journalctl", "--user", "-u", "loto-actualizare.service", "--since", "2026-10-25 19:00:00 UTC",
           "--until", now.strftime("%Y-%m-%d %H:%M:%S UTC"), "--no-pager", "-o", "short-iso-precise"]
    j = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    r.check("journalctl_rc0", j.returncode == 0, j.stderr[-300:])
    lines = j.stdout.splitlines()
    unit = "loto-actualizare.service"
    st = [x for x in lines if f"Starting {unit}" in x]
    fa = [x for x in lines if f"{unit}: Failed with result" in x]
    gp = [x for x in lines if "Model/environment changed after protocol freeze: gpu-v1" in x]
    ok_ = [x for x in lines if f"Finished {unit}" in x]
    r.check("n_porniri_ge_1", len(st) >= 1, len(st))
    r.check("consistenta_gpu_le_esec_le_porniri", len(gp) <= len(fa) <= len(st), [len(gp), len(fa), len(st)])
    excerpt = [x for x in lines if ("systemd[" in x and unit in x) or "gpu-v1" in x]
    last_start = max((i for i, x in enumerate(lines) if f"Starting {unit}" in x), default=None)
    tail = lines[last_start:] if last_start is not None else []
    garda = "GARDA_ACTIVA" if (any("gpu-v1" in x for x in tail) and any("Failed with result" in x for x in tail)) \
        else "GARDA_NEOBSERVATA"
    live = json.loads((QL / "tu3/date/live/CURRENT_LIVE.json").read_text())
    last_date = {g: v["last_date"] for g, v in live["games"].items()}
    r.check("live_citit", set(last_date) == {"649", "540", "joker"}, last_date)
    show = subprocess.run(["systemctl", "--user", "show", unit, "-p", "Result,ExecMainExitTimestamp"],
                          capture_output=True, text=True, timeout=30)
    r.check("systemctl_show_rc0", show.returncode == 0, show.stdout.strip())
    jtxt = "\n".join(excerpt) + "\n"
    jsha = write_ro(OUT / "JURNAL_GPU_V1_S28.txt", jtxt)
    av = {
        "avertisment": "AVERTISMENT_EXTERN_S28",
        "sursa": "loto-actualizare.service (produsul principal, în afara QL649)",
        "mesaj": "Actualizarea a eșuat; snapshotul anterior rămâne activ. Model/environment changed after protocol "
                 "freeze: gpu-v1",
        "garda_localizare": "loto_romania/cohorta.py:163 context(): prognoze.model_identity(model) != identitatea "
                            "înghețată în cohortă ⇒ ValueError (constatat read-only; cauza NEinvestigată)",
        "interval": [ "2026-10-25T19:00:00Z", z(now)],
        "n_porniri": len(st), "n_esecuri": len(fa), "n_gpu_v1": len(gp), "n_reusite": len(ok_),
        "prima_gpu_v1": gp[0].split()[0] if gp else None, "ultima_gpu_v1": gp[-1].split()[0] if gp else None,
        "stare_ultima_rulare": garda,
        "systemctl_show": show.stdout.strip().splitlines(),
        "arhiva_LIVE": {"updated_utc": live.get("updated_utc"), "last_date": last_date},
        "consecinta": "DECONTARE_PENDING_CONDITIONAT: dacă arhiva LIVE nu conține 2026-10-29, decontarea rămâne "
                      "PENDING; emisia 2026-11-01 e amânată până la slotul final 2026-11-01T13:20Z; C1/B5 se verifică "
                      "duminică 13:36Z–13:57Z (protocol S28 §2)",
        "decizie": "NEREPARAT, NELEGITIMAT în S28; remediere numai într-o sesiune dedicată separată, cu protocol propriu",
        "jurnal_extras": {"file": "tu4/rezultate/S28/JURNAL_GPU_V1_S28.txt", "sha256": jsha, "lines": len(excerpt)},
        "positive_claims_allowed": False,
    }
    asha = write_ro(OUT / "AVERTISMENT_EXTERN_S28.json", json.dumps(av, indent=2, ensure_ascii=False) + "\n")
    r.check("fisiere_scrise_0444", all((OUT / f).stat().st_mode & 0o777 == 0o444
                                       for f in ("JURNAL_GPU_V1_S28.txt", "AVERTISMENT_EXTERN_S28.json")))
    return r.finish({"avertisment_sha256": asha, "jurnal_sha256": jsha, "stare": garda,
                     "n": [len(st), len(fa), len(gp), len(ok_)]})


# ------------------------------------------------------------------ P2
def at_local(d: dt.date, hm: tuple[int, int]) -> dt.datetime:
    return dt.datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=TZ).astimezone(UTC)


def schedule(now: dt.datetime) -> dict:
    """Replică independentă a emite.schedule (WEEKDAYS (3, 6), CUTOFF 16:00, FINAL 15:00, DRAW 18:30 Europe/Bucharest)."""
    d = now.astimezone(TZ).date()
    while not (d.weekday() in (3, 6) and at_local(d, (16, 0)) > now):
        d += dt.timedelta(days=1)
    p = d - dt.timedelta(days=1)
    while p.weekday() not in (3, 6):
        p -= dt.timedelta(days=1)
    return {"target": d.isoformat(), "prev": p.isoformat(), "cutoff": at_local(d, (16, 0)),
            "final": at_local(d, (15, 0)), "draw": at_local(d, (18, 30))}


def p2() -> int:
    r = Report("P2")
    em = (QL / "tu4/emite.py").read_text(encoding="utf-8").splitlines()
    ju = (QL / "tu4/judecator.py").read_text(encoding="utf-8").splitlines()
    r.check("emite_constante", "DRAW_T, CUTOFF_T, FINAL_T = dt.time(18, 30), dt.time(16, 0), dt.time(15, 0)" in em
            and "WEEKDAYS = (3, 6)" in em)
    r.check("judecator_grace", "GRACE = dt.timedelta(days=14)" in ju)
    inst = Path("$HOME/.config/systemd/user/ql649-tu4-emitere.timer")
    ref = QL / "tu4/systemd/ql649-tu4-emitere.timer"
    tl = inst.read_text().splitlines()
    r.check("timer_instalat_eq_ref", sha(inst) == sha(ref), sha(inst)[:8])
    r.check("timer_3_oncalendar", all(f"OnCalendar=*-*-* {hm}:00 Europe/Bucharest" in tl
                                      for hm in ("08:20", "12:20", "15:20")))
    s = schedule(dt.datetime(2026, 10, 29, 14, 5, tzinfo=UTC))
    r.check("schedule_tinta", s["target"] == "2026-11-01" and s["prev"] == "2026-10-29"
            and z(s["cutoff"]) == "2026-11-01T14:00:00Z" and z(s["final"]) == "2026-11-01T13:00:00Z"
            and z(s["draw"]) == "2026-11-01T16:30:00Z", {k: (z(v) if isinstance(v, dt.datetime) else v) for k, v in s.items()})
    lo, hi = dt.datetime(2026, 10, 29, 14, 0, tzinfo=UTC), dt.datetime(2026, 11, 1, 14, 0, tzinfo=UTC)
    slots = sorted(t for k in range(4) for hm in ((8, 20), (12, 20), (15, 20))
                   for t in [at_local(dt.date(2026, 10, 29) + dt.timedelta(days=k), hm)] if lo < t < hi)
    rows = []
    for t in slots:
        sc = schedule(t)
        complete = "2026-10-25" >= sc["prev"]
        act = "postponed" if (not complete and t < sc["final"]) else ("emisie" if t < sc["cutoff"] < sc["draw"] else "late")
        rows.append({"slot_utc": z(t), "laptop": ny(t), "bucuresti": t.astimezone(TZ).strftime("%Y-%m-%d %H:%M %Z"),
                     "tinta": sc["target"], "H_BLOCAT": act, "fereastra_interzisa": [z(t - SO.MARGIN), z(t + SO.MARGIN)]})
    want = [z(dt.datetime(2026, m, d, h, 20, tzinfo=UTC)) for (m, d) in ((10, 30), (10, 31), (11, 1)) for h in (6, 10, 13)]
    r.check("sloturi_9_A01", [x["slot_utc"] for x in rows] == want, [x["slot_utc"] for x in rows])
    r.check("H_BLOCAT_8_postponed_1_emisie", [x["H_BLOCAT"] for x in rows] == ["postponed"] * 8 + ["emisie"]
            and all(x["tinta"] == "2026-11-01" for x in rows), [x["H_BLOCAT"] for x in rows])
    T = lambda s_: dt.datetime.fromisoformat(s_.replace("Z", "+00:00"))  # noqa: E731
    forb = ["2026-11-01T13:20:00Z", "2026-11-01T13:35:00Z", "2026-10-29T16:15:00Z", "2026-10-29T16:45:00Z"]
    free = ["2026-11-01T13:36:00Z", "2026-11-01T13:57:00Z", "2026-10-29T16:46:00Z"]
    wres = {x: SO.window(T(x), DRAW) for x in forb + free}
    r.check("ferestre_interzise", all(wres[x] for x in forb), {x: wres[x] for x in forb})
    r.check("ferestre_libere", all(wres[x] is None for x in free), {x: wres[x] for x in free})
    dst_ok = (T("2026-11-01T05:59:00Z").astimezone(NY).utcoffset() == dt.timedelta(hours=-4)
              and T("2026-11-01T06:00:00Z").astimezone(NY).utcoffset() == dt.timedelta(hours=-5))
    conv = {"2026-10-29T16:30:00Z": "2026-10-29 12:30 EDT", "2026-10-30T06:20:00Z": "2026-10-30 02:20 EDT",
            "2026-10-30T10:20:00Z": "2026-10-30 06:20 EDT", "2026-10-30T13:20:00Z": "2026-10-30 09:20 EDT",
            "2026-11-01T06:20:00Z": "2026-11-01 01:20 EST", "2026-11-01T10:20:00Z": "2026-11-01 05:20 EST",
            "2026-11-01T13:20:00Z": "2026-11-01 08:20 EST", "2026-11-01T13:36:00Z": "2026-11-01 08:36 EST",
            "2026-11-01T13:57:00Z": "2026-11-01 08:57 EST"}
    got = {k: ny(T(k)) for k in conv}
    r.check("ny_dst_si_conversii", dst_ok and got == conv, got)
    tzs = subprocess.run(["timedatectl", "show", "-p", "Timezone", "--value"], capture_output=True, text=True, timeout=30)
    cal = {
        "calendar": "CALENDAR_S28", "protocol": "TU4-S28 §2 + A01",
        "extragere": {"utc": z(DRAW), "laptop": ny(DRAW), "interzis": [z(DRAW - SO.MARGIN), z(DRAW + SO.MARGIN)]},
        "decontare_2026_10_29": {"H_BLOCAT": "DECONTARE_PENDING; AVERTISMENT_DECONTARE_BLOCATA de la "
                                             + z(DRAW + dt.timedelta(hours=2)) + "; VOID după 14 zile (GRACE)",
                                 "H_ACTUALIZAT": "prima rulare a judecătorului (:00:30/:30:30) după ce arhiva LIVE "
                                                 "conține 2026-10-29 ⇒ DECONTARE_COMPLETA 3/3 (primul pas)"},
        "emisie_2026_11_01": {"schedule": {k: (z(v) if isinstance(v, dt.datetime) else v) for k, v in s.items()},
                              "sloturi": rows,
                              "risc_late": "dacă emisia de la 13:20Z nu se termină înainte de cutoff 14:00Z ⇒ late"},
        "verificare_finala_C1_B5": {"utc": ["2026-11-01T13:36:00Z", "2026-11-01T13:57:00Z"],
                                    "laptop": [ny(T("2026-11-01T13:36:00Z")), ny(T("2026-11-01T13:57:00Z"))],
                                    "pasi": "sonda_s27.py ⇒ FAZA_4; apoi primul pas neschimbat + verifica_s25.py q7l"},
        "fus_laptop": tzs.stdout.strip(), "tranzitie_EDT_EST_utc": "2026-11-01T06:00:00Z",
        "positive_claims_allowed": False,
    }
    csha = write_ro(OUT / "CALENDAR_S28.json", json.dumps(cal, indent=2, ensure_ascii=False) + "\n")
    r.check("calendar_scris_0444", (OUT / "CALENDAR_S28.json").stat().st_mode & 0o777 == 0o444, csha[:8])
    return r.finish({"calendar_sha256": csha})


# ------------------------------------------------------------------ P3
def p3() -> int:
    r = Report("P3")
    d = frozen_drift()
    r.check("frozen_S28_neschimbate", not d, d)
    r.check("sigilii_S28_A01", sha(SEAL_PATH) == SEAL_SHA and sha(AMEND_SEAL) == AMEND_SEAL_SHA)
    e = external_drift()
    r.check("externe_garda_unitate_timere_neschimbate", not e, e)
    ok, bad = rust_ok()
    r.check("rust_27_0444_sha", ok, bad)
    inc = incidents()
    r.check("incidente_9", inc == INCID9, inc)
    lb = (QL / "tu4/tribunal/LANT.jsonl").read_bytes()
    snap = SEAL["lant_snapshot_S28"]
    r.check("LANT_eq_instantaneu", hashlib.sha256(lb).hexdigest() == snap["sha256"] and len(lb) == snap["bytes"],
            {"bytes": len(lb), "lines": len(lb.splitlines())})
    s28 = sorted(f.name for f in (QL / "tu4/s28").iterdir())
    r.check("s28_numai_verificator_0444", s28 == ["verifica_s28.py"]
            and (QL / "tu4/s28/verifica_s28.py").stat().st_mode & 0o777 == 0o444, s28)
    act = {u: subprocess.run(["systemctl", "--user", "is-active", u], capture_output=True, text=True, timeout=30).stdout.strip()
           for u in ("loto-actualizare.timer", "ql649-tu4-emitere.timer")}
    r.check("timere_active", all(v == "active" for v in act.values()), act)
    return r.finish()


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("p0", "p1", "p2", "p3"):
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
    return {"P0": p0, "P1": p1, "P2": p2, "P3": p3}[crit]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
