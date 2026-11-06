"""Verificatorul S27 (protocol tu4/PROTOCOL_QUANTUM_S27.md §3). Scris DUPĂ sigiliu; scrie numai fișiere noi
<crit>_VERIFICARE_<UTC>.json (0444) în tu4/rezultate/S27/. Fixture-urile P1 trăiesc în directoare temporare din afara pistei.
Utilizare:  verifica_s27.py p0 | p1 | p2 | p3
Calcul clasic; positive_claims_allowed=false.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import datetime as dt  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

QL = Path("${QL649_ROOT:-.}")
ROOT = Path("${LOTO_RO_ROOT:-.}")
OUT = QL / "tu4/rezultate/S27"
SEAL_PATH = QL / "tu4/SIGILIU_TU4_S27.json"
SEAL_SHA = "ce2a9f1816dd5de4a8e22e98e3e4566de7267def2142b23122be2374b9f9bc13"
SEAL = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
SONDA = QL / "tu4/s27/sonda_s27.py"
TRIB = QL / "tu4/tribunal"
MAN22 = QL / "tu4/rezultate/S22/MANIFEST_RUST_CORE_20261028T032900Z.json"
PY = "/usr/bin/python3"
ACUM_LIBER = "2026-10-28T12:45:00Z"

sys.path.insert(0, str(QL / "tu4/s27"))
sys.path.insert(0, str(QL / "tu4/s25"))
sys.path.insert(0, str(QL / "tu4/s24"))
import raport_decontare_s24 as RD  # noqa: E402
import sonda_s27 as SO  # noqa: E402
import verifica_s25 as V25  # noqa: E402


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def shab(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha(p: Path) -> str:
    return shab(p.read_bytes())


class Report:
    def __init__(self, crit: str):
        self.crit, self.checks = crit, []

    def check(self, name, ok, detail=None):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def finish(self, extra=None, verdict=None) -> int:
        n_pass = sum(c["ok"] for c in self.checks)
        verdict = verdict or ("PASS" if self.checks and n_pass == len(self.checks) else "FAIL")
        stamp = utc_now()
        out = OUT / f"{self.crit}_VERIFICARE_{stamp}.json"
        while out.exists():          # lecția S23_02
            time.sleep(1.0)
            stamp = utc_now()
            out = OUT / f"{self.crit}_VERIFICARE_{stamp}.json"
        doc = {"criteriu": self.crit, "verdict": verdict, "n_checks": len(self.checks), "n_pass": n_pass,
               "run_utc": stamp, "protocol": "TU4-S27", "checks": self.checks, "positive_claims_allowed": False}
        if extra:
            doc.update(extra)
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out.chmod(0o444)
        print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "n_checks", "n_pass")}, ensure_ascii=False))
        for c in self.checks:
            if not c["ok"]:
                print("FAIL", self.crit, c["name"], json.dumps(c["detail"], ensure_ascii=False)[:800])
        print(out, sha(out))
        return 0 if verdict == "PASS" else (3 if verdict == "UNKNOWN" else 1)


def incidents() -> list[str]:
    return sorted(d.name for d in (QL / "tu4/incidente").iterdir() if d.is_dir())


def rust_ok() -> tuple[bool, list]:
    man = json.loads(MAN22.read_text(encoding="utf-8"))["sources"]
    bad = [f for f, d in man.items() if SO.path_of(f).stat().st_mode & 0o777 != 0o444 or sha(SO.path_of(f)) != d["sha256"]]
    return len(man) == 27 and not bad, bad


def frozen_drift() -> list[str]:
    return [k for k, v in SEAL["frozen_hashes"].items() if not SO.path_of(k).is_file() or sha(SO.path_of(k)) != v]


def tree(root: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(root.rglob("*")):
        st = f.lstat()
        h.update(str(f.relative_to(root)).encode() + b"\0" + oct(st.st_mode).encode() + b"\0")
        if f.is_file():
            h.update(f.read_bytes() + b"\0")
    return h.hexdigest()


def sonda(*args) -> tuple[int, str, str]:
    p = subprocess.run([PY, "-B", str(SONDA), *args], capture_output=True, text=True, timeout=300)
    m = re.search(r"^SONDA_S27_FAZA=(\S+) RC=(\d+)", p.stdout, re.M)
    return p.returncode, (m.group(1) if m else None), p.stdout + p.stderr


# ----------------------------------------------------------------------------------------------------------- P0
def p0() -> int:
    r = Report("P0")
    ver = json.loads((QL / "predari/VERIFICARE_PREDARE_20261028T120625Z.json").read_text())
    for f in ("HANDOFF_QL649_20261028T120625Z.md", "PROMPT_QL649_20261028T120625Z.txt"):
        r.check(f"predare:{f}", sha(QL / "predari" / f) == ver[f]["sha256"])
    for k, v in SEAL["baseline_B0"].items():
        r.check(f"B0:{k}", sha(QL / k) == v)
    q7l = json.loads((QL / "tu4/rezultate/S25/Q7L_VERIFICARE_20261028T123028Z.json").read_text())
    r.check("B0_q7l_11_11", q7l["verdict"] == "PASS" and q7l["n_pass"] == q7l["n_checks"] == 11)
    v0l = json.loads((QL / "tu4/rezultate/S25/V0L_VERIFICARE_20261028T123028Z.json").read_text())
    failed = [c["name"] for c in v0l["checks"] if not c["ok"]]
    r.check("B0_v0l_28_29_numai_incidente", v0l["n_checks"] == 29 and v0l["n_pass"] == 28 and failed == ["incidente"], failed)
    r.check("frozen_hashes_S27", not frozen_drift(), frozen_drift())
    r.check("incidente_9_fara_S26_S27", incidents() == SEAL["incidents_before"], incidents())
    ok, bad = rust_ok()
    r.check("surse_rust_27_0444_sha", ok, bad)
    r.check("sigiliu_S27_sha", sha(SEAL_PATH) == SEAL_SHA)
    r.check("sonda_0444", SONDA.stat().st_mode & 0o777 == 0o444, oct(SONDA.stat().st_mode & 0o777))
    return r.finish()


# ----------------------------------------------------------------------------------------------------------- P1
def base(root: Path, extra_inc=()) -> tuple[Path, Path, Path]:
    trib = root / "tribunal"
    trib.mkdir(parents=True)
    shutil.copytree(TRIB / "emisii", trib / "emisii")
    for f in ("LANT.jsonl", "RULARI.jsonl", "JUDECATOR_RULARI.jsonl"):
        shutil.copyfile(TRIB / f, trib / f)
        (trib / f).chmod(0o444)
    inc = root / "incidente"
    for n in [*SEAL["incidents_before"], *extra_inc]:
        (inc / n).mkdir(parents=True)
    live = root / "live"
    live.mkdir()
    write_live(live, "2026-10-25")
    return trib, inc, live


def write_live(live: Path, last: str) -> None:
    doc = {"updated_utc": "2026-10-28T12:30:29Z", "games": {g: {"last_date": last} for g in SO.GAMES}, "fixture": "S27"}
    (live / "CURRENT_LIVE.json").write_text(json.dumps(doc, indent=1) + "\n")


def add_decontari(trib: Path, games, bad_sha=False) -> None:
    """Decontări sintetice pentru 2026-10-29, cu lanțul din JU_SEAL_SHA și sha-urile emisiilor reale din LANT."""
    seal = RD.ju_seal_sha(QL / "tu4/judecator.py")
    lant = {json.loads(x)["game"]: json.loads(x) for x in (trib / "LANT.jsonl").read_bytes().splitlines()}
    prev, lines = seal, []
    for k, g in enumerate(games):
        e = lant[g]
        doc = {"game": g, "target_date": "2026-10-29", "status": "DECONTAT", "reason": "fixture sintetic S27",
               "decided_utc": "2026-10-29T17:00:30Z", "test_mode": True, "label": "fixture", "positive_claims_allowed": False,
               "emission": {"file": e["file"], "sha256": e["sha256"], "lant_i": e["i"]}, "draw": None,
               "models": {}, "streams_before": {}, "streams_after": {}, "thresholds": dict(RD.THRESHOLDS)}
        data = (json.dumps(doc, indent=1) + "\n").encode()
        rel = f"decontari/{g}/2026-10-29.json"
        (trib / rel).parent.mkdir(parents=True, exist_ok=True)
        (trib / rel).write_bytes(data)
        line = json.dumps({"i": k, "game": g, "target_date": "2026-10-29", "status": "DECONTAT", "file": rel,
                           "sha256": shab(data), "prev_line_sha256": prev}, sort_keys=True).encode()
        lines.append(line)
        prev = shab(line)
    (trib / "DECONTARI.jsonl").write_bytes(b"".join(x + b"\n" for x in lines))
    if bad_sha:
        f = trib / f"decontari/{games[0]}/2026-10-29.json"
        f.write_bytes(f.read_bytes().replace(b"fixture sintetic S27", b"fixture alterat! S27"))


def p1() -> int:
    r = Report("P1")
    res = {}
    with tempfile.TemporaryDirectory(prefix="ql649_s27_p1_") as d:
        D = Path(d)

        def case(name, root, args, want_rc, want_faza, must=(), must_not=()):
            t0 = tree(root)
            rc, faza, out = sonda(*args, "--fara-systemd")
            t1 = tree(root)
            ok = rc == want_rc and faza == want_faza and all(m in out for m in must) and not any(m in out for m in must_not)
            res[name] = {"rc": rc, "faza": faza, "ok": ok}
            r.check(name, ok, {"asteptat": [want_rc, want_faza, list(must), list(must_not)], "obtinut": [rc, faza],
                               "iesire": out[-1500:] if not ok else None})
            r.check(f"F8_arbore_neatins:{name}", t0 == t1)

        def std(root, trib, inc, live, *more):
            return ["--trib", str(trib), "--incidente", str(inc), "--live", str(live), *more]

        # F1
        R = D / "F1"; trib, inc, live = base(R)
        case("F1_copie_reala_FAZA_0", R, std(R, trib, inc, live, "--acum", ACUM_LIBER), 0, "FAZA_0_ASTEAPTA_DECONTAREA")
        # F2
        nx = str(D / "inexistent")
        case("F2_fereastra_extragere", D, ["--trib", nx, "--incidente", nx, "--live", nx, "--acum", "2026-10-29T16:40:00Z"],
             3, "UNKNOWN_FEREASTRA")
        case("F2_fereastra_slot_1101_1520", D, ["--trib", nx, "--incidente", nx, "--live", nx, "--acum", "2026-11-01T13:25:00Z"],
             3, "UNKNOWN_FEREASTRA")
        case("F2_in_afara_1650", R, std(R, trib, inc, live, "--acum", "2026-10-29T16:50:00Z"), 0, "FAZA_0_ASTEAPTA_DECONTAREA")
        # F3
        R = D / "F3"; trib, inc, live = base(R, extra_inc=("S26_01",))
        case("F3_incident_S26_ANOMALIE", R, std(R, trib, inc, live, "--acum", ACUM_LIBER), 1, "ANOMALIE", must=("G1 incidente FAIL",))
        # F4
        R = D / "F4"; trib, inc, live = base(R)
        f = trib / "LANT.jsonl"; f.chmod(0o644)
        b = f.read_bytes(); first = b.splitlines(keepends=True)[0]
        f.write_bytes(first.replace(b"e2fe385e", b"e2fe385f", 1) + b[len(first):]); f.chmod(0o444)
        case("F4_prefix_LANT_ANOMALIE", R, std(R, trib, inc, live, "--acum", ACUM_LIBER), 1, "ANOMALIE", must=("T1 scut_lant FAIL",))
        # F5
        for name, games, bad, want_rc, want in (("F5_decontare_1_FAZA_1", ("649",), False, 0, "FAZA_1_DECONTARE_PARTIALA"),
                                                ("F5_decontare_3_FAZA_2", ("649", "540", "joker"), False, 0, "FAZA_2_DECONTARE_COMPLETA"),
                                                ("F5_sha_alterat_ANOMALIE", ("649", "540", "joker"), True, 1, "ANOMALIE")):
            R = D / name; trib, inc, live = base(R)
            add_decontari(trib, games, bad)
            case(name, R, std(R, trib, inc, live, "--acum", ACUM_LIBER), want_rc, want)
        # F6
        for name, n_new, want in (("F6_emisie_1_FAZA_3", 1, "FAZA_3_EMISIE_PARTIALA"), ("F6_emisie_3_FAZA_4", 3, "FAZA_4_EMISIE_COMPLETA")):
            R = D / name
            trib = V25._tribunal_sintetic(R, n_new)
            _, inc, live = base(D / (name + "_aux"))
            case(name, R, std(R, trib, inc, live, "--acum", ACUM_LIBER, "--tinta-emisie", "2099-01-01"), 0, want)
        # F7
        R = D / "F7"; trib, inc, live = base(R)
        case("F7_avertismente_prezente", R, std(R, trib, inc, live, "--acum", "2026-10-29T19:00:00Z"), 0,
             "FAZA_0_ASTEAPTA_DECONTAREA", must=("AVERTISMENT_DECONTARE_BLOCATA", "AVERTISMENT_EMISIE_AMANATA"))
        write_live(live, "2026-10-29")
        case("F7_avertismente_absente", R, std(R, trib, inc, live, "--acum", "2026-10-29T19:00:00Z"), 0,
             "FAZA_0_ASTEAPTA_DECONTAREA", must_not=("AVERTISMENT_DECONTARE_BLOCATA", "AVERTISMENT_EMISIE_AMANATA"))
    return r.finish({"rezumat": res})


# ----------------------------------------------------------------------------------------------------------- P2
def snapshot() -> dict:
    snap = {}
    for base_dir, skip in ((QL / "tu4", QL / "tu4/tribunal"), (QL / "predari", None), (ROOT / "rust_core/src", None)):
        for f in sorted(base_dir.rglob("*")):
            if skip and (f == skip or skip in f.parents):
                continue
            st = f.lstat()
            snap[str(f)] = [st.st_size, st.st_mtime_ns, oct(st.st_mode), sha(f) if f.is_file() else None]
    return snap


def p2() -> int:
    r = Report("P2")
    now = dt.datetime.now(dt.timezone.utc)
    w = SO.window(now, SO.at_local(dt.date(2026, 10, 29), SO.DRAW_LOCAL))
    if w or now.minute >= 58 or now.minute < 4 or 28 <= now.minute < 34:
        r.check("fereastra_libera", False, w or f"minutul {now.minute} exclus")
        return r.finish(verdict="UNKNOWN")
    if any(OUT.glob("P2_VERIFICARE_*.json")):
        r.check("o_singura_rulare", False, "P2 a mai rulat")
        return r.finish()
    s0, t0 = snapshot(), RD.tree_hash(TRIB)[0]
    rc, faza, out = sonda()
    s1, t1 = snapshot(), RD.tree_hash(TRIB)[0]
    dec = TRIB / "DECONTARI.jsonl"
    n_dec = len({json.loads(x).get("game") for x in (dec.read_text().splitlines() if dec.exists() else [])
                 if json.loads(x).get("target_date") == "2026-10-29"})
    n_em = sum((TRIB / "emisii" / g / "2026-11-01.json").is_file() for g in SO.GAMES)
    exp = ("FAZA_4_EMISIE_COMPLETA" if n_em == 3 else "FAZA_3_EMISIE_PARTIALA" if n_em else
           "FAZA_2_DECONTARE_COMPLETA" if n_dec == 3 else "FAZA_1_DECONTARE_PARTIALA" if n_dec else "FAZA_0_ASTEAPTA_DECONTAREA")
    r.check("rc_0", rc == 0, rc)
    r.check("faza_independenta", faza == exp, {"asteptat": exp, "obtinut": faza, "n_dec": n_dec, "n_em": n_em})
    r.check("tribunal_neatins_intern", "T5 tribunal_neatins OK" in out)
    r.check("tribunal_neatins_extern", t0 == t1, [t0, t1])
    diff = sorted(set(s0) ^ set(s1)) + sorted(k for k in set(s0) & set(s1) if s0[k] != s1[k])
    r.check("zero_scrieri_tu4_predari_rust_src", not diff, diff[:20])
    r.check("pca_false", "positive_claims_allowed=false" in out)
    for tag in ("G1 ", "G2 ", "G3 ", "G4 ", "T1 ", "T2 ", "T3 ", "T4 ", "T5 "):
        r.check(f"linie:{tag.strip()}", re.search(rf"^{tag}", out, re.M) is not None)
    return r.finish({"iesire_sonda": out.splitlines(), "n_fisiere_instantaneu": len(s0)})


# ----------------------------------------------------------------------------------------------------------- P3
def p3() -> int:
    r = Report("P3")
    r.check("frozen_hashes_S27", not frozen_drift(), frozen_drift())
    r.check("incidente_9", incidents() == SEAL["incidents_before"], incidents())
    ok, bad = rust_ok()
    r.check("surse_rust_27_0444", ok, bad)
    for t in ("ql649-tu4-emitere.timer", "loto-actualizare.timer"):
        a = subprocess.run(["systemctl", "--user", "is-active", t], capture_output=True, text=True).stdout.strip()
        r.check(f"timer_activ:{t}", a == "active", a)
    files = sorted((f.name, oct(f.stat().st_mode & 0o777)) for f in (QL / "tu4/s27").iterdir())
    r.check("s27_numai_doua_fisiere_0444", files == [("sonda_s27.py", "0o444"), ("verifica_s27.py", "0o444")], files)
    return r.finish()


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("p0", "p1", "p2", "p3"):
        print(__doc__)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    return {"p0": p0, "p1": p1, "p2": p2, "p3": p3}[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
