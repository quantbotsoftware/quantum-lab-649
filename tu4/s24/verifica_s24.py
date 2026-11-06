"""Verificatorul S24 (protocol tu4/PROTOCOL_QUANTUM_S24.md §5). Scris DUPĂ sigiliu; scrie numai fișiere noi
Qn_VERIFICARE_<UTC>.json în tu4/rezultate/S24/ (plus, prin Q7, V0_VERIFICARE_<UTC>.json al verifica_s23.py în S23/).

Utilizare:
  verifica_s24.py q0                              Q0: integritatea (sigiliu, înghețate, 0444, append-only, fstab)
  verifica_s24.py q1                              Q1: unitatea (canonic = instalat = textul sigilat; verify; enabled)
  verifica_s24.py q2 [--restart] [--old-pid N]    Q2: pornirea prin systemd (scope izolat, 127.0.0.1, health, READY)
  verifica_s24.py q3                              Q3: așteptarea SSD-ului (montat / absent / jurnalul serviciului)
  verifica_s24.py q4                              Q4: după repornirea laptopului (UNKNOWN dacă nu a avut loc)
  verifica_s24.py q5                              Q5: decontarea read-only (tribunal real + fixture sintetic temporar)
  verifica_s24.py q6                              Q6: B5/B2 pentru 2026-11-01 (ramura corectă, tribunal neatins)
  verifica_s24.py q7 <log> [--incidente-s24 S24_01,...]   Q7: închiderea (V0 S23 27/28 + incidentele + liniile S24)
Calcul clasic; positive_claims_allowed=false.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

QL = Path(".")
RC = Path("./rust_core")
OUT = QL / "tu4/rezultate/S24"
SEAL_PATH = QL / "tu4/SIGILIU_TU4_S24.json"
SEAL_SHA = "c3b5ebb39bf775c20d854c74f046976315a606218fbccb8586de1fd5daa3770c"
SEAL = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
UNIT = SEAL["unit_name"]
UDIR = Path.home() / ".config/systemd/user"
CANON_UNIT = QL / "tu4/systemd" / UNIT
MAN22 = QL / "tu4/rezultate/S22/MANIFEST_RUST_CORE_20261028T032900Z.json"
PORT = 8649
TRIB = QL / "tu4/tribunal"
sys.path.insert(0, str(QL / "tu4/s24"))
import raport_decontare_s24 as RD  # noqa: E402


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


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

    def finish(self, extra: dict | None = None, unknown: str | None = None) -> int:
        n_pass = sum(c["ok"] for c in self.checks)
        if unknown:
            verdict = "UNKNOWN"
        else:
            verdict = "PASS" if self.checks and n_pass == len(self.checks) else "FAIL"
        stamp = utc_now()
        out = OUT / f"{self.crit}_VERIFICARE_{stamp}.json"
        while out.exists():          # lecția S23_02: niciodată două rezultate în același fișier/secundă
            time.sleep(1.0)
            stamp = utc_now()
            out = OUT / f"{self.crit}_VERIFICARE_{stamp}.json"
        doc = {"criteriu": self.crit, "verdict": verdict, "n_checks": len(self.checks), "n_pass": n_pass,
               "run_utc": stamp, "protocol": "TU4-S24", "checks": self.checks, "positive_claims_allowed": False}
        if unknown:
            doc["motiv_unknown"] = unknown
        if extra:
            doc.update(extra)
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out.chmod(0o444)
        print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "n_checks", "n_pass")}, indent=2, ensure_ascii=False))
        if unknown:                  # UNKNOWN nu e FAIL și nu devine PASS: o linie proprie, fără prefixul „FAIL ”
            print("UNKNOWN", self.crit, unknown)
        for c in ([] if unknown else self.checks):
            if not c["ok"]:
                print("FAIL", self.crit, c["name"], c["detail"])
        print(out, sha(out))
        return 0 if verdict in ("PASS", "UNKNOWN") else 1


# ------------------------------------------------------------------------------------------------ utilitare 8649
def listeners(port: int = PORT) -> list[tuple[str, int]]:
    out = run(["ss", "-ltnpH", f"sport = :{port}"]).stdout
    res = []
    for line in out.splitlines():
        parts = line.split()
        local = parts[3] if len(parts) > 3 else ""
        for pid in re.findall(r"pid=(\d+)", line):
            res.append((local, int(pid)))
        if not re.search(r"pid=\d+", line):
            res.append((local, -1))
    return res


def cgroup(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cgroup").read_text().strip().split("::", 1)[-1]
    except OSError:
        return ""


def health() -> str:
    return run(["curl", "-s", "--max-time", "2", f"http://127.0.0.1:{PORT}/_stcore/health"]).stdout.strip()


def unit_show(*props) -> dict:
    out = run(["systemctl", "--user", "show", UNIT, *[f"-p{p}" for p in props]]).stdout
    return dict(x.split("=", 1) for x in out.splitlines() if "=" in x)


def invocation_journal(inv: str) -> str:
    if not inv:
        return ""
    return run(["journalctl", "--user", f"_SYSTEMD_INVOCATION_ID={inv}", "-o", "cat", "--no-pager"]).stdout


def boot_epoch() -> float:
    for line in Path("/proc/stat").read_text().splitlines():
        if line.startswith("btime "):
            return float(line.split()[1])
    raise RuntimeError("btime")


def proc_start_epoch(pid: int) -> float:
    st = Path(f"/proc/{pid}/stat").read_text()
    fields = st[st.rindex(")") + 2:].split()
    return boot_epoch() + int(fields[19]) / os.sysconf("SC_CLK_TCK")


def launcher_logs_since(stamp: str) -> list[Path]:
    return sorted(p for p in (QL / "jurnal").glob("lansator_tu3_*Z.log") if p.name >= f"lansator_tu3_{stamp}")


# ----------------------------------------------------------------------------------------------------------- Q0
def q0() -> int:
    r = Report("Q0")
    r.check("sigiliu_sha", sha(SEAL_PATH) == SEAL_SHA, sha(SEAL_PATH))
    r.check("sigiliu_0444", SEAL_PATH.stat().st_mode & 0o777 == 0o444)
    for rel, d in SEAL["documents"].items():
        r.check(f"protocol_sha:{rel}", sha(path_of(rel)) == d["sha256"])
        r.check(f"protocol_0444:{rel}", path_of(rel).stat().st_mode & 0o777 == 0o444)
    drift = [k for k, v in SEAL["frozen_hashes"].items() if not path_of(k).exists() or sha(path_of(k)) != v]
    r.check("inghetate_fara_drift", not drift, {"n": len(SEAL["frozen_hashes"]), "drift": drift})
    man = json.loads(MAN22.read_text())
    modes = {k: oct(path_of(k).stat().st_mode & 0o777) for k in man["sources"]}
    r.check("surse_rust_27_0444", len(modes) == 27 and all(v == "0o444" for v in modes.values()),
            {k: v for k, v in modes.items() if v != "0o444"})
    for k in ("rust_core/src/models/h1_mass.rs", "rust_core/src/models/h3_aero.rs"):
        r.check(f"{Path(k).name}_0444_sha", modes[k] == "0o444" and sha(path_of(k)) == man["sources"][k]["sha256"])
    for rel, d in SEAL["append_only_prefix"].items():
        b = path_of(rel).read_bytes()
        r.check(f"prefix:{rel}", len(b) >= d["bytes"] and hashlib.sha256(b[:d["bytes"]]).hexdigest() == d["sha256"],
                {"bytes_acum": len(b), "bytes_sigiliu": d["bytes"]})
    r.check("fstab", sha(Path("/etc/fstab")) == SEAL["frozen_hashes"]["/etc/fstab"])
    return r.finish()


# ----------------------------------------------------------------------------------------------------------- Q1
def q1() -> int:
    r = Report("Q1")
    inst = UDIR / UNIT
    text = SEAL["unit_text"]
    r.check("canonic_exista", CANON_UNIT.exists())
    r.check("instalat_exista", inst.exists() and not inst.is_symlink())
    strip = lambda s: "".join(x + "\n" for x in s.splitlines() if not x.lstrip().startswith("#"))
    r.check("canonic_eq_text_sigilat", CANON_UNIT.exists() and strip(CANON_UNIT.read_text()) == text)
    r.check("instalat_eq_canonic", inst.exists() and CANON_UNIT.exists() and inst.read_bytes() == CANON_UNIT.read_bytes())
    r.check("execstart_exact", "ExecStart=/usr/bin/systemd-run --user --scope --collect -q ./porneste_aplicatia_tu3.sh\n" in text)
    v = run(["systemd-analyze", "--user", "verify", str(inst)])
    r.check("systemd_analyze_verify", v.returncode == 0 and not v.stderr.strip(), (v.returncode, v.stderr.strip()[-400:]))
    en = run(["systemctl", "--user", "is-enabled", UNIT]).stdout.strip()
    r.check("is_enabled", en == "enabled", en)
    lk = UDIR / "default.target.wants" / UNIT
    r.check("legatura_default_target", lk.is_symlink() and lk.resolve() == inst.resolve(), str(lk))
    lg = run(["loginctl", "show-user", os.environ.get("USER", "tony"), "-p", "Linger"]).stdout.strip()
    r.check("linger", lg == "Linger=yes", lg)
    pre = Path(QL / "tu4/s24/asteapta_ssd.sh")
    r.check("execstartpre_exista", pre.exists())
    return r.finish({"canonic_sha256": sha(CANON_UNIT) if CANON_UNIT.exists() else None})


# ----------------------------------------------------------------------------------------------------------- Q2
def q2(restart: bool, old_pid: int | None) -> int:
    r = Report("Q2")
    t0 = utc_now()
    t0_epoch = time.time()
    if restart:
        rs = run(["systemctl", "--user", "restart", UNIT], timeout=420)
        r.check("restart_rc0", rs.returncode == 0, rs.stderr.strip()[-400:])
    h, waited = "", 0.0
    while waited <= 150:
        h = health()
        if h == "ok":
            break
        time.sleep(1.0)
        waited = time.time() - t0_epoch
    r.check("health_ok_150s", h == "ok", {"health": h, "secunde": round(time.time() - t0_epoch, 1)})
    sh = unit_show("Result", "ActiveState", "ExecMainStatus", "InvocationID", "ExecMainStartTimestamp")
    r.check("result_success", sh.get("Result") == "success" and sh.get("ExecMainStatus") == "0", sh)
    ls = listeners()
    r.check("asculta_numai_127", bool(ls) and all(l.startswith("127.0.0.1:") for l, _ in ls), ls)
    pids = sorted({p for _, p in ls if p > 0})
    cgs = {p: cgroup(p) for p in pids}
    r.check("in_run_scope", bool(cgs) and all(re.search(r"/run-[^/]+\.scope$", c) for c in cgs.values()), cgs)
    r.check("nu_in_cgroup_serviciu", bool(cgs) and all(UNIT not in c for c in cgs.values()), cgs)
    if restart:
        r.check("pornit_dupa_restart", bool(pids) and all(proc_start_epoch(p) >= t0_epoch - 1 for p in pids),
                {p: proc_start_epoch(p) for p in pids})
    if old_pid:
        r.check("pid_vechi_oprit", not Path(f"/proc/{old_pid}").exists(), old_pid)
    logs = launcher_logs_since(t0) if restart else sorted((QL / "jurnal").glob("lansator_tu3_*Z.log"))[-1:]
    txt = logs[-1].read_text(encoding="utf-8", errors="replace") if logs else ""
    r.check("lansator_health_ok", "[lansator] health ok" in txt, str(logs[-1]) if logs else None)
    r.check("lansator_3_moduri_ready", "TOATE 3 MODURILE READY" in txt)
    j = invocation_journal(sh.get("InvocationID", ""))
    r.check("jurnal_ssd_montat", re.search(r"^SSD_MONTAT /dev/\S+ ./ssd_data", j, re.M) is not None,
            [x for x in j.splitlines() if x.startswith("SSD_")])
    return r.finish({"pids": pids, "cgroups": cgs, "lansator_log": str(logs[-1]) if logs else None,
                     "invocation": sh.get("InvocationID"), "t0": t0})


# ----------------------------------------------------------------------------------------------------------- Q3
def q3() -> int:
    r = Report("Q3")
    sh = QL / "tu4/s24/asteapta_ssd.sh"
    a = run(["/usr/bin/bash", str(sh), "5"])
    r.check("montat_rc0", a.returncode == 0, a.returncode)
    r.check("montat_linie", a.stdout.startswith("SSD_MONTAT /dev/sda1 ./ssd_data"), a.stdout.strip())
    with tempfile.TemporaryDirectory(prefix="ql649_s24_q3_") as d:
        t = time.monotonic()
        b = run(["/usr/bin/bash", str(sh), "2", d])
        dur = time.monotonic() - t
    r.check("absent_rc0", b.returncode == 0, b.returncode)
    r.check("absent_linie", b.stdout.startswith("SSD_ABSENT "), b.stdout.strip())
    r.check("absent_durata_ge_2s", dur >= 2.0, round(dur, 2))
    inv = unit_show("InvocationID").get("InvocationID", "")
    j = invocation_journal(inv)
    r.check("jurnal_serviciu_ssd_montat", re.search(r"^SSD_MONTAT /dev/\S+", j, re.M) is not None,
            [x for x in j.splitlines() if x.startswith("SSD_")])
    return r.finish({"invocation": inv})


# ----------------------------------------------------------------------------------------------------------- Q4
def q4() -> int:
    r = Report("Q4")
    sealed = dt.datetime.strptime(SEAL["sealed_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()
    bt = boot_epoch()
    info = {"boot_utc": dt.datetime.fromtimestamp(bt, dt.timezone.utc).isoformat(), "sealed_utc": SEAL["sealed_utc"]}
    if bt < sealed:
        return r.finish(info, unknown="laptopul nu a fost repornit după activarea S24 (boot anterior sigiliului)")
    js = run(["journalctl", "--user", "-b", "-u", UNIT, "-o", "json", "--no-pager"]).stdout.splitlines()
    ev = [json.loads(x) for x in js if x.strip()]
    starts = [e for e in ev if str(e.get("MESSAGE", "")).startswith("Starting ")]
    first = starts[0] if starts else None
    r.check("pornire_in_boot", first is not None, len(starts))
    if first:
        t_first = int(first["__REALTIME_TIMESTAMP"]) / 1e6
        info["prima_pornire_dupa_boot_s"] = round(t_first - bt, 1)
        r.check("prima_pornire_le_600s_dupa_boot", t_first - bt <= 600, info["prima_pornire_dupa_boot_s"])
        inv = first.get("INVOCATION_ID") or first.get("_SYSTEMD_INVOCATION_ID") or ""
        j = invocation_journal(inv)
        info["jurnal_prima_invocatie"] = [x for x in j.splitlines() if x.startswith("SSD_")]
        r.check("prima_invocatie_ssd_montat", re.search(r"^SSD_MONTAT /dev/\S+", j, re.M) is not None, info["jurnal_prima_invocatie"])
        fin = [e for e in ev if (e.get("INVOCATION_ID") or e.get("_SYSTEMD_INVOCATION_ID")) == inv
               and str(e.get("MESSAGE", "")).startswith("Finished ")]
        r.check("prima_invocatie_finished", bool(fin))
    r.check("health_ok", health() == "ok")
    ls = listeners()
    r.check("asculta_numai_127", bool(ls) and all(l.startswith("127.0.0.1:") for l, _ in ls), ls)
    pids = sorted({p for _, p in ls if p > 0})
    info["cgroups_informativ"] = {p: cgroup(p) for p in pids}
    info["pornire_ascultator_dupa_boot_s"] = {p: round(proc_start_epoch(p) - bt, 1) for p in pids}
    return r.finish(info)


# ----------------------------------------------------------------------------------------------------------- Q5
def _fixture(root: Path, games=("649", "540", "joker"), bad_sha=False, bad_thr=False):
    trib = root / "tribunal"
    (trib / "decontari").mkdir(parents=True)
    seal = RD.ju_seal_sha(QL / "tu4/judecator.py")
    lant, dec_lines, prev = [], [], seal
    for i, g in enumerate(("649", "540", "joker")):
        lant.append({"i": i, "game": g, "target_date": "2099-01-01", "sha256": hashlib.sha256(f"em{g}".encode()).hexdigest()})
    (trib / "LANT.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lant))
    for k, g in enumerate(games):
        thr = dict(RD.THRESHOLDS)
        if bad_thr and k == 0:
            thr["confirm_ln"] = math.log(19.0)
        doc = {"game": g, "target_date": "2099-01-01", "status": "DECONTAT", "reason": "fixture sintetic",
               "decided_utc": "2099-01-02T00:00:00Z", "test_mode": True, "label": "fixture", "positive_claims_allowed": False,
               "emission": {"file": f"emisii/{g}/2099-01-01.json", "sha256": lant[("649", "540", "joker").index(g)]["sha256"],
                            "lant_i": 0}, "draw": {"numbers": [1, 2, 3, 4, 5, 6], "joker": None},
               "models": {m: {"ln_e": 0.0, "ln_e_main": 0.0, "ln_e_ball": None, "counted": True} for m in ("H1", "H3")},
               "streams_before": {}, "streams_after": {}, "thresholds": thr}
        data = (json.dumps(doc, indent=1) + "\n").encode()
        rel = f"decontari/{g}/2099-01-01.json"
        (trib / rel).parent.mkdir(parents=True, exist_ok=True)
        (trib / rel).write_bytes(data)
        line = json.dumps({"i": k, "game": g, "target_date": "2099-01-01", "status": "DECONTAT", "file": rel,
                           "sha256": hashlib.sha256(data).hexdigest(), "prev_line_sha256": prev}, sort_keys=True).encode()
        dec_lines.append(line)
        prev = hashlib.sha256(line).hexdigest()
    (trib / "DECONTARI.jsonl").write_bytes(b"".join(x + b"\n" for x in dec_lines))
    if bad_sha:
        f = trib / "decontari/540/2099-01-01.json"
        f.write_bytes(f.read_bytes().replace(b"fixture sintetic", b"fixture alterat!"))
    return trib


def _rd(trib: Path, target: str, out: Path) -> dict:
    p = run([sys.executable, "-B", str(QL / "tu4/s24/raport_decontare_s24.py"), "--tinta", target, "--trib", str(trib),
             "--out", str(out)])
    try:
        return json.loads(p.stdout.strip().splitlines()[-1]) | {"rc": p.returncode}
    except Exception:
        return {"rc": p.returncode, "stdout": p.stdout[-400:], "stderr": p.stderr[-400:]}


def q5() -> int:
    r = Report("Q5")
    dec = TRIB / "DECONTARI.jsonl"
    n_target = sum(1 for x in (dec.read_text().splitlines() if dec.exists() else []) if json.loads(x).get("target_date") == "2026-10-29")
    exp = "DECONTARE_PENDING" if n_target == 0 else ("DECONTARE_COMPLETA" if n_target == 3 else "DECONTARE_PARTIALA")
    real = _rd(TRIB, "2026-10-29", OUT)
    r.check("real_tribunal_neatins", real.get("tribunal_neatins") is True, real)
    r.check("real_verdict_stare_curenta", real.get("verdict") == exp, {"asteptat": exp, "obtinut": real.get("verdict")})
    with tempfile.TemporaryDirectory(prefix="ql649_s24_q5_") as d:
        D = Path(d)
        for name, kw, want in (("completa", {}, "DECONTARE_COMPLETA"), ("partiala", {"games": ("649",)}, "DECONTARE_PARTIALA"),
                               ("sha_alterat", {"bad_sha": True}, "DECONTARE_FAIL"),
                               ("prag_modificat", {"bad_thr": True}, "DECONTARE_FAIL")):
            trib = _fixture(D / name, **kw)
            res = _rd(trib, "2099-01-01", D / name / "out")
            r.check(f"fixture_{name}", res.get("verdict") == want and res.get("tribunal_neatins") is True,
                    {"asteptat": want, "obtinut": res.get("verdict"), "rc": res.get("rc")})
        pend = _fixture(D / "pending", games=())
        res = _rd(pend, "2099-01-01", D / "pending" / "out")
        r.check("fixture_pending", res.get("verdict") == "DECONTARE_PENDING", res.get("verdict"))
    return r.finish({"raport_real": real.get("json"), "raport_real_sha256": real.get("sha256")})


# ----------------------------------------------------------------------------------------------------------- Q6
def q6() -> int:
    r = Report("Q6")
    before, _ = RD.tree_hash(TRIB)
    has_em = (TRIB / "emisii/649/2026-11-01.json").exists()
    p = run(["/usr/bin/bash", str(QL / "tu4/s24/b5_s24.sh")], timeout=600)
    after, _ = RD.tree_hash(TRIB)
    out = p.stdout
    r.check("tribunal_neatins", before == after)
    r.check("rc0", p.returncode == 0, (p.returncode, out[-400:], p.stderr[-300:]))
    r.check("binar_sigilat", f"BIN_SHA {SEAL['expected']['release_binary_sha256']}" in out)
    if has_em:
        r.check("ramura_b5", "B5_PENDING" not in out and re.search(r'"criteriu": "B5",\s+"verdict": "PASS"', out) is not None)
        m = re.search(r'"fluxuri": (\[.*?\]\s*\])', out, re.S)
        r.check("b5_6_fluxuri", m is not None and len(json.loads(m.group(1))) == 6)
    else:
        r.check("ramura_pending", "B5_PENDING" in out)
        r.check("b2_pass", re.search(r'"criteriu": "B2",\s+"verdict": "PASS"', out) is not None and "B2_RC=0" in out)
    return r.finish({"emisie_20261101": has_em, "stdout": out[-1500:]})


# ----------------------------------------------------------------------------------------------------------- Q7
def q7(log: Path, s24_inc: list[str]) -> int:
    r = Report("Q7")
    t = log.read_text(encoding="utf-8", errors="replace")
    lines = t.splitlines()
    v = run(["/usr/bin/python3", "-B", str(QL / "tu4/rezultate/S23/verifica_s23.py"), "v0", str(log)])
    m = re.search(r"(\S+/V0_VERIFICARE_\d{8}T\d{6}Z\.json) [0-9a-f]{64}", v.stdout)
    v0 = json.loads(Path(m.group(1)).read_text()) if m else {}
    fails = [c for c in v0.get("checks", []) if not c["ok"]]
    allowed = set(SEAL["incidents_before"]) | set(s24_inc)
    v0_inc = set((fails[0]["detail"] or {}).get("gasite", [])) if len(fails) == 1 else set()
    r.check("v0_27_28_numai_incidente", v0.get("n_checks") == 28 and v0.get("n_pass") == 27 and len(fails) == 1
            and fails[0]["name"] == "incidente" and v0_inc <= allowed,
            {"v0": m.group(1) if m else None, "fails": [(c["name"], c["detail"]) for c in fails]})
    found = sorted(d.name for d in (QL / "tu4/incidente").iterdir() if d.is_dir())
    r.check("incidente_cunoscute", set(found) == allowed and all(re.fullmatch(r"S24_\d\d", x) for x in s24_inc),
            {"gasite": found, "permise": sorted(allowed)})
    for k, pat in (("paritate_587", r'"n_pass": 587'), ("rust_61", r"test result: ok\. 61 passed"),
                   ("q0_pass", r'"criteriu": "Q0",\s+"verdict": "PASS"'), ("q1_pass", r'"criteriu": "Q1",\s+"verdict": "PASS"'),
                   ("serviciu_activ_sau_reusit", r"^S24_SERVICIU Result=success"),
                   ("decontare_raport", r'"verdict": "DECONTARE_(PENDING|PARTIALA|COMPLETA)"'),
                   ("b5_sau_b2", r"^(B5_RC=0|B2_RC=0)$")):
        r.check(k, re.search(pat, t, re.M) is not None)
    r.check("fara_fail_s24", not any(x.startswith("FAIL Q") for x in lines), [x for x in lines if x.startswith("FAIL Q")])
    return r.finish({"log": str(log), "log_sha256": sha(log), "v0_file": m.group(1) if m else None,
                     "v0_sha256": sha(Path(m.group(1))) if m else None})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["q0", "q1", "q2", "q3", "q4", "q5", "q6", "q7"])
    ap.add_argument("log", nargs="?", type=Path)
    ap.add_argument("--restart", action="store_true")
    ap.add_argument("--old-pid", type=int)
    ap.add_argument("--incidente-s24", default="")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.cmd == "q2":
        return q2(a.restart, a.old_pid)
    if a.cmd == "q7":
        if not a.log:
            ap.error("q7 cere calea logului")
        return q7(a.log, [x for x in a.incidente_s24.split(",") if x])
    return {"q0": q0, "q1": q1, "q3": q3, "q4": q4, "q5": q5, "q6": q6}[a.cmd]()


if __name__ == "__main__":
    sys.exit(main())
