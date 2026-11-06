"""Verificatorul S26 (protocol tu4/PROTOCOL_QUANTUM_S26.md, sigiliul tu4/SIGILIU_TU4_S26.json).

  verifica_s26.py t0          T0: starea înainte (predare, B0, binare, gazdă, serviciu, WebKit, SSD, surse, ferestre)
  verifica_s26.py t1          T1: sesiunea mărginită `monitor --pid P --interval-ms 1000 --samples 600` (O SINGURĂ dată)
  verifica_s26.py t2          T2: neintervenția după sesiune (hash-uri, scutul LANT, tribunal append-only, timere)

Scrieri: tu4/rezultate/S26/{T0,T1,T2}_VERIFICARE_<UTC>.json, MONITOR_<UTC>.{json,stderr} și directorul sesiunii pe SSD
(scris de binarul înghețat). Fără sudo, fără scrieri în tribunal/systemd/surse. positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

QL = Path("${QL649_ROOT:-.}")
OUT = QL / "tu4/rezultate/S26"
SEAL = json.loads((QL / "tu4/SIGILIU_TU4_S26.json").read_text(encoding="utf-8"))
TEL_ROOT = Path("./telemetry")
BIN = Path("./rust_core/target/release/rust-singularity-core")
SHA_BIN = "c20fdcd2f7f237578d1f0ea85c05f9bf6b32a888d228e4443b6756dd1d43fd9e"
SHA_BIN21 = "f25aad0c9f197b3fde566a9672c68397be8e0d1fb5ed457b0be42551f9eb5871"
SCOPE = "run-u194.scope"
INCID = ["EM_01", "FR_01", "S19_01", "S20_01", "S23_01", "S23_02", "S23_03", "S24_01", "SM1_01"]
N_SAMPLES, INTERVAL_MS = 600, 1000


def p(rel: str) -> Path:
    return Path(rel) if rel.startswith("/") else (Path("${LOTO_RO_ROOT:-.}") / rel if rel.startswith("rust_core/") else QL / rel)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class Report:
    def __init__(self, name: str):
        self.name, self.checks, self.t0 = name, [], utc()

    def check(self, nume: str, ok: bool, detalii=None):
        self.checks.append({"nume": nume, "ok": bool(ok), "detalii": detalii})
        print(("PASS" if ok else "FAIL"), self.name, nume, "" if ok else json.dumps(detalii, ensure_ascii=False)[:400])

    def finish(self, extra: dict | None = None) -> int:
        n_pass = sum(c["ok"] for c in self.checks)
        verdict = "PASS" if self.checks and n_pass == len(self.checks) else "FAIL"
        doc = {"criteriu": self.name, "verdict": verdict, "n_checks": len(self.checks), "n_pass": n_pass,
               "pornit_utc": self.t0, "terminat_utc": utc(), "checks": self.checks, "extra": extra or {},
               "sigiliu_s26_sha256": sha(QL / "tu4/SIGILIU_TU4_S26.json"), "positive_claims_allowed": False}
        OUT.mkdir(exist_ok=True)
        f = OUT / f"{self.name}_VERIFICARE_{utc()}.json"
        f.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "n_checks", "n_pass")}, indent=2))
        print(f, sha(f))
        return 0 if verdict == "PASS" else 1


# ------------------------------------------------------------------------------------------------------ utilitare
def forbidden_hit(start: dt.datetime, end: dt.datetime) -> list[str]:
    tz, m = ZoneInfo("Europe/Bucharest"), dt.timedelta(minutes=15)
    hits = []
    for dd in (-1, 0, 1):
        d = (start + dt.timedelta(days=dd)).astimezone(tz).date()
        ev = [dt.datetime.combine(d, dt.time(hh, mm), tz) for hh, mm in ((8, 20), (12, 20), (15, 20))]
        dutc = (start + dt.timedelta(days=dd)).date()
        if dutc.weekday() == 3:
            ev.append(dt.datetime.combine(dutc, dt.time(16, 30), dt.timezone.utc))
        for e in ev:
            if start < e + m and end > e - m:
                hits.append(e.astimezone(dt.timezone.utc).isoformat())
    return sorted(set(hits))


def sh(*args: str) -> str:
    return subprocess.run(list(args), capture_output=True, text=True).stdout.strip()


def systemd_props(unit: str, *props: str) -> dict:
    out = sh("systemctl", "--user", "show", unit, "-p", ",".join(props))
    return dict(ln.split("=", 1) for ln in out.splitlines() if "=" in ln)


def scope_procs() -> dict[int, tuple[int, str]]:
    cg = systemd_props(SCOPE, "ControlGroup").get("ControlGroup", "")
    f = Path("/sys/fs/cgroup") / cg.lstrip("/") / "cgroup.procs"
    out = {}
    for x in (f.read_text().split() if cg and f.exists() else []):
        st = Path(f"/proc/{x}/stat").read_text()
        rp = st.rfind(")")
        out[int(x)] = (int(st[rp + 2:].split()[1]), st[st.find("(") + 1: rp])
    return out


def main_pid() -> int | None:
    procs = scope_procs()
    roots = [pid for pid, (pp, comm) in procs.items() if pp not in procs]
    return roots[0] if len(roots) == 1 else None


def listen_pid() -> tuple[int | None, str]:
    out = sh("ss", "-ltnpH", "sport = :8649")
    m = re.search(r'127\.0\.0\.1:8649 .*users:\(\("([^"]+)",pid=(\d+)', out)
    return (int(m.group(2)), m.group(1)) if m else (None, out)


def health() -> str:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8649/_stcore/health", timeout=5) as r:
            return r.read().decode().strip()
    except Exception as e:   # noqa: BLE001
        return f"EROARE {e}"


def webkit_and_gui() -> tuple[list, list]:
    wk, gui, me = [], [], os.getpid()
    for d in Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == me:
            continue
        try:
            comm = (d / "comm").read_text().strip()
            argv = [a for a in (d / "cmdline").read_bytes().split(b"\0") if a]
        except OSError:
            continue
        if comm.startswith("WebKit") or (argv and b"WebKit" in Path(argv[0].decode(errors="replace")).name.encode()):
            wk.append((int(d.name), comm))
        if len(argv) >= 2 and Path(argv[0].decode(errors="replace")).name == "rust-singularity-core" and argv[1] == b"gui":
            gui.append(int(d.name))
    return wk, gui


def rust_sources() -> tuple[bool, dict]:
    man = json.loads((QL / "tu4/rezultate/S22/MANIFEST_RUST_CORE_20261028T032900Z.json").read_text())
    bad = {}
    for f, v in man["sources"].items():
        m = p(f).stat().st_mode & 0o777
        if m != 0o444 or sha(p(f)) != v["sha256"]:
            bad[f] = oct(m)
    return len(man["sources"]) == 27 and not bad, bad


def frozen_drift() -> list[str]:
    return [k for k, v in SEAL["frozen_hashes"].items() if not p(k).exists() or sha(p(k)) != v]


def incidents() -> list[str]:
    return sorted(d.name for d in (QL / "tu4/incidente").iterdir() if d.is_dir())


# ------------------------------------------------------------------------------------------------------------- T0
def t0() -> int:
    r = Report("T0")
    b0 = SEAL["baseline_B0"]
    ver = json.loads((QL / "predari/VERIFICARE_PREDARE_20261028T113522Z.json").read_text())
    hs, ps = sha(QL / "predari/HANDOFF_QL649_20261028T113522Z.md"), sha(QL / "predari/PROMPT_QL649_20261028T113522Z.txt")
    r.check("predare_113522Z", hs == b0["handoff_sha256"] == ver["HANDOFF_QL649_20261028T113522Z.md"]["sha256"]
            and ps == b0["prompt_sha256"] == ver["PROMPT_QL649_20261028T113522Z.txt"]["sha256"], [hs, ps])
    q7l = QL / "tu4/rezultate/S25/Q7L_VERIFICARE_20261028T114548Z.json"
    v0l = QL / "tu4/rezultate/S25/V0L_VERIFICARE_20261028T114548Z.json"
    qd, vd = json.loads(q7l.read_text()), json.loads(v0l.read_text())
    vfail = [c["name"] for c in vd["checks"] if not c["ok"]]
    r.check("B0_log_q7l_v0l", sha(QL / b0["log"]) == b0["log_sha256"] and sha(q7l) == b0["q7l_sha256"]
            and sha(v0l) == b0["v0l_sha256"] and qd["verdict"] == "PASS" and qd["n_pass"] == 11 == qd["n_checks"]
            and vd["n_pass"] == 28 and vd["n_checks"] == 29 and vfail == ["incidente"], {"q7l": qd["n_pass"], "v0l_fail": vfail})
    b21 = Path("./ssd_data/RUST_CORE_S21/bin/rust-singularity-core")
    r.check("binare_c20fdcd2_f25aad0c", sha(BIN) == SHA_BIN and sha(b21) == SHA_BIN21
            and os.access(BIN, os.X_OK) and os.access(b21, os.X_OK), [sha(BIN)[:8], sha(b21)[:8]])
    blocks = [b for b in Path("/proc/cpuinfo").read_text().split("\n\n") if b.strip().startswith("processor")]
    flags = [set(next(ln for ln in b.splitlines() if ln.startswith("flags")).split(":", 1)[1].split()) for b in blocks]
    n_avx2, n_fma = sum("avx2" in f for f in flags), sum("fma" in f for f in flags)
    cfg = p("rust_core/.cargo/config.toml")
    r.check("gazda_avx2_fma_toate", len(flags) == os.cpu_count() == n_avx2 == n_fma,
            {"cpu": len(flags), "avx2": n_avx2, "fma": n_fma})
    r.check("cargo_target_cpu_native", sha(cfg) == SEAL["frozen_hashes"]["rust_core/.cargo/config.toml"]
            and 'rustflags = ["-C", "target-cpu=native"]' in cfg.read_text())
    sp = systemd_props("ql649-tu3-8649.service", "Type", "Result", "UnitFileState")
    unit_ok = (sha(Path("$HOME/.config/systemd/user/ql649-tu3-8649.service")) == SEAL["service"]["unit_sha256"]
               == sha(QL / "tu4/systemd/ql649-tu3-8649.service"))
    r.check("serviciu_oneshot_success_enabled", sp == {"Type": "oneshot", "Result": "success", "UnitFileState": "enabled"}
            and unit_ok, sp)
    procs, mp = scope_procs(), main_pid()
    lp, lname = listen_pid()
    sc = systemd_props(SCOPE, "ActiveState", "SubState")
    r.check("scope_activ_P_streamlit", sc == {"ActiveState": "active", "SubState": "running"} and mp is not None
            and procs.get(mp, (0, ""))[1] == "bash" and lp in procs and lname == "streamlit" and procs[lp][0] == mp,
            {"scope": sc, "P": mp, "listen": [lp, lname], "procs": {k: v[1] for k, v in procs.items()}})
    hc = health()
    r.check("health_ok", hc == "ok", hc)
    wk, gui = webkit_and_gui()
    r.check("fara_webkit_fara_gui", not wk and not gui, {"webkit": wk, "gui": gui})
    fm = sh("findmnt", "-n", "-o", "SOURCE", "./ssd_data")
    r.check("ssd_sda1_tel_root", fm == "/dev/sda1" and TEL_ROOT.is_dir() and os.access(TEL_ROOT, os.W_OK), fm)
    ok, bad = rust_sources()
    r.check("surse_rust_27_0444", ok, bad)
    now = dt.datetime.now(dt.timezone.utc)
    hits = forbidden_hit(now, now + dt.timedelta(seconds=SEAL["forbidden_windows"]["session_plus_margin_s"]))
    r.check("fereastra_libera", not hits, hits)
    r.check("incidente_9", incidents() == INCID, incidents())
    dr = frozen_drift()
    r.check("frozen_hashes_s26", not dr, dr)
    return r.finish({"P": mp, "streamlit": lp})


# ------------------------------------------------------------------------------------------------------------- T1
def t1() -> int:
    r = Report("T1")
    stamp = utc()
    if list(OUT.glob("MONITOR_*.json")):
        r.check("o_singura_sesiune", False, "MONITOR_* există deja: sesiunea nu se repetă (protocol §2)")
        return r.finish()
    now = dt.datetime.now(dt.timezone.utc)
    hits = forbidden_hit(now, now + dt.timedelta(seconds=SEAL["forbidden_windows"]["session_plus_margin_s"]))
    if hits:
        print("UNKNOWN T1 fereastră interzisă", hits)
        return 2
    P = main_pid()
    lp0, _ = listen_pid()
    mon_json, mon_err = OUT / f"MONITOR_{stamp}.json", OUT / f"MONITOR_{stamp}.stderr"
    cmd = [str(BIN), "monitor", "--pid", str(P), "--interval-ms", str(INTERVAL_MS), "--samples", str(N_SAMPLES)]
    print("CMD", " ".join(cmd), flush=True)
    with mon_json.open("wb") as fo, mon_err.open("wb") as fe:
        rc = subprocess.run(cmd, stdout=fo, stderr=fe, timeout=N_SAMPLES * INTERVAL_MS / 1000 + 300).returncode
    try:
        agg = json.loads(mon_json.read_text(encoding="utf-8"))
    except Exception as e:   # noqa: BLE001
        agg = {"_eroare": str(e)}
    r.check("exit0_complet_rezumat", rc == 0 and agg.get("stare") == "COMPLET" and bool(agg.get("rezumat")),
            {"rc": rc, "stare": agg.get("stare"), "motiv": agg.get("motiv")})
    d = Path(agg.get("director") or "/nonexistent")
    r.check("director_ssd_pid", d.parent == TEL_ROOT and d.is_dir() and d.name.endswith(f"_pid{P}"), str(d))
    rows, bad = [], []
    for seg in sorted(d.glob("telemetrie_*.jsonl")) if d.is_dir() else []:
        raw = seg.read_bytes()
        for i, ln in enumerate(raw[: raw.rfind(b"\n") + 1].splitlines()):
            try:
                o = json.loads(ln)
                assert isinstance(o, dict)
                rows.append(o)
            except Exception as e:   # noqa: BLE001
                bad.append({"segment": seg.name, "linia": i + 1, "eroare": str(e)})
    r.check("600_json_seq_pid_citiri0", len(rows) == N_SAMPLES and not bad
            and all(o.get("seq") == i + 1 and o.get("pid") == P and o.get("citiri_esuate") == 0 for i, o in enumerate(rows)),
            {"n": len(rows), "bad": bad[:3], "citiri_esuate_max": max((o.get("citiri_esuate") or 0 for o in rows), default=None)})
    r.check("arbore_viu", bool(rows) and all((o.get("n_procese") or 0) >= 2 and o.get("rss_principal") is not None for o in rows),
            {"n_procese_min": min((o.get("n_procese") or 0 for o in rows), default=None)})
    wk, gui = webkit_and_gui()
    r.check("zero_webview", bool(rows) and all(o.get("n_webview") == 0 and o.get("webview_rss") == 0 for o in rows)
            and not wk and not gui, {"webkit": wk, "gui": gui})
    lp1, ln1 = listen_pid()
    hc = health()
    r.check("streamlit_acelasi_pid_health", lp1 == lp0 and ln1 == "streamlit" and hc == "ok", [lp0, lp1, hc])
    mx = max((o["rss_total"] for o in rows), default=None)
    r.check("agregat_varf_eq_jsonl", agg.get("rss_total_varf") == mx, [agg.get("rss_total_varf"), mx])
    # ---- descriptiv (fără prag)
    desc = {}
    if rows:
        def stats(k):
            v = [o[k] for o in rows if o.get(k) is not None]
            return {"min": min(v), "max": max(v), "prima": v[0], "ultima": v[-1]} if v else None
        xs = [o["t_ms"] / 60000 for o in rows]
        ys = [o["rss_total"] for o in rows]
        mx_, my_ = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - mx_) ** 2 for x in xs)
        desc = {"rss_total": stats("rss_total"), "pss_total": stats("pss_total"), "hwm_total": stats("hwm_total"),
                "rss_principal": stats("rss_principal"),
                "panta_ols_rss_total_octeti_pe_min": (sum((x - mx_) * (y - my_) for x, y in zip(xs, ys)) / sxx) if sxx else None,
                "utc_prima": rows[0]["utc"], "utc_ultima": rows[-1]["utc"], "n_procese_set": sorted({o["n_procese"] for o in rows})}
    od = subprocess.run(["objdump", "-d", "--no-show-raw-insn", str(BIN)], capture_output=True, text=True).stdout
    desc["objdump_static"] = {"instr_ymm": len(re.findall(r"%ymm\d+", od)), "instr_vfmadd": len(re.findall(r"\bvfn?m(?:add|sub)\w*", od)),
                              "nota": "număr static de apariții; NU dovedește execuția pe vreun drum și nici câștig de viteză"}
    return r.finish({"P": P, "cmd": cmd, "rc": rc, "monitor_json": str(mon_json), "monitor_json_sha256": sha(mon_json),
                     "monitor_stderr_sha256": sha(mon_err), "director": str(d),
                     "segmente_sha256": {s.name: sha(s) for s in sorted(d.glob("*"))} if d.is_dir() else {},
                     "agregat": agg, "descriptiv": desc})


# ------------------------------------------------------------------------------------------------------------- T2
def t2() -> int:
    r = Report("T2")
    now = dt.datetime.now(dt.timezone.utc)
    hits = forbidden_hit(now, now + dt.timedelta(seconds=60))
    if hits:
        print("UNKNOWN T2 fereastră interzisă", hits)
        return 2
    dr = frozen_drift()
    r.check("frozen_hashes_s26", not dr, dr)
    sc = subprocess.run(["/usr/bin/python3", "-B", str(QL / "tu4/s25/verifica_s25.py"), "scut"], capture_output=True, text=True)
    r.check("scut_lant", any(ln.startswith("SCUT_LANT OK") for ln in sc.stdout.splitlines()), sc.stdout.strip()[-300:])
    ao = {}
    for rel, v in SEAL["append_only_prefix"].items():
        b = p(rel).read_bytes()
        ao[rel] = len(b) >= v["bytes"] and hashlib.sha256(b[: v["bytes"]]).hexdigest() == v["sha256"]
    r.check("tribunal_append_only", all(ao.values()), ao)
    tm = {t: systemd_props(t, "ActiveState", "UnitFileState") for t in ("ql649-tu4-emitere.timer", "loto-actualizare.timer")}
    r.check("timere_active_enabled", all(v == {"ActiveState": "active", "UnitFileState": "enabled"} for v in tm.values()), tm)
    ok, bad = rust_sources()
    r.check("surse_rust_27_0444", ok, bad)
    r.check("binar_c20fdcd2", sha(BIN) == SHA_BIN)
    inc = incidents()
    extra = sorted(set(inc) - set(INCID))
    r.check("incidente", set(INCID) <= set(inc) and all(x.startswith("S26_") for x in extra), {"toate": inc, "noi": extra})
    return r.finish({"incidente": inc})


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"t0": t0, "t1": t1, "t2": t2}.get(mode)
    if fn is None:
        print(__doc__)
        sys.exit(2)
    sys.exit(fn())
