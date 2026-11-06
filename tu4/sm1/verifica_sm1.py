"""Verificatorul SM1 (protocol tu4/PROTOCOL_MONTARE_SSD_SM1.md §5, amendament A01). Fără root; scrie numai
tu4/rezultate/SM1/<CRIT>_VERIFICARE_<UTC>.json. Parola nu apare nicăieri aici.

  verifica_sm1.py m0                 pre-condiții
  verifica_sm1.py m1 <copia .bak>    aplicarea (fstab = copie + exact 2 linii; unitatea generată)
  verifica_sm1.py m2                 montarea de către systemd + scriere-test
  verifica_sm1.py m4                 după repornire: montat înainte de login
  verifica_sm1.py m5                 după repornire: tribunalul a văzut SSD-ul la prima rulare
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

QL = Path("${QL649_ROOT:-.}")
OUT = QL / "tu4/rezultate/SM1"
SEAL = json.loads((QL / "tu4/SIGILIU_TU4_SM1.json").read_text(encoding="utf-8"))
DEV = SEAL["device"]
MP, UNIT = DEV["mountpoint"], DEV["mount_unit"]
PRE = SEAL["pre_hashes"]["/etc/fstab"]
LINES = SEAL["fstab_lines_to_append"]


def sh(*a: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(a), capture_output=True, text=True)


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class R:
    def __init__(self, crit):
        self.crit, self.checks = crit, []

    def c(self, name, ok, detail=None):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def done(self, extra=None) -> int:
        n = sum(x["ok"] for x in self.checks)
        v = "PASS" if self.checks and n == len(self.checks) else "FAIL"
        doc = {"criteriu": self.crit, "verdict": v, "n_checks": len(self.checks), "n_pass": n, "run_utc": utc(),
               "protocol": "TU4-SM1 (+A01)", "checks": self.checks, "positive_claims_allowed": False} | (extra or {})
        out = OUT / f"{self.crit}_VERIFICARE_{doc['run_utc']}.json"
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out.chmod(0o444)
        print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "n_checks", "n_pass")}, ensure_ascii=False))
        for x in self.checks:
            if not x["ok"]:
                print("FAIL", x["name"], x["detail"])
        print(out, sha(out))
        return 0 if v == "PASS" else 1


def m0() -> int:
    r = R("M0")
    r.c("fstab_pre_hash", sha("/etc/fstab") == PRE, sha("/etc/fstab"))
    txt = Path("/etc/fstab").read_text()
    r.c("fara_intrare_ssd", "LOTO_SSD" not in txt and DEV["uuid"] not in txt)
    b = sh("lsblk", "-no", "UUID,FSTYPE,LABEL", f"/dev/disk/by-uuid/{DEV['uuid']}").stdout.split()
    r.c("dispozitiv", b == [DEV["uuid"], DEV["fstype"], DEV["label"]], b)
    fz = SEAL["frozen_hashes"]
    dr = [k for k, v in fz.items() if not (Path(k) if k.startswith("/") else (Path("${LOTO_RO_ROOT:-.}") / k if k.startswith("rust_core/") else QL / k)).exists()
          or sha(Path(k) if k.startswith("/") else (Path("${LOTO_RO_ROOT:-.}") / k if k.startswith("rust_core/") else QL / k)) != v]
    r.c("drift_sm1_gol", not dr, dr)
    d23 = sh("/usr/bin/python3", "-B", str(QL / "tu4/rezultate/S23/verifica_s23.py"), "drift")
    r.c("drift_s23_gol", "tu4/SIGILIU_TU4_S23.json drift []" in d23.stdout, d23.stdout[-300:])
    return r.done()


def m1(bak: str) -> int:
    r = R("M1")
    b, f = Path(bak), Path("/etc/fstab")
    r.c("copie_pre_hash", b.exists() and sha(b) == PRE, str(b))
    expected = b.read_bytes() + ("\n".join(LINES) + "\n").encode() if b.exists() else b""
    r.c("fstab_egal_copie_plus_2_linii", f.read_bytes() == expected, sha(f))
    v = sh("findmnt", "--verify", "--tab-file", "/etc/fstab")
    r.c("findmnt_verify", v.returncode == 0 and "0 parse errors, 0 errors" in (v.stdout + v.stderr), (v.stdout + v.stderr)[-300:])
    c = sh("systemctl", "show", UNIT, "-p", "SourcePath", "-p", "Where", "-p", "What", "-p", "Options")
    r.c("unitate_generata_din_fstab", "SourcePath=/etc/fstab" in c.stdout and f"Where={MP}" in c.stdout, c.stdout)
    return r.done({"backup": str(b), "fstab_sha256": sha(f)})


def m2() -> int:
    r = R("M2")
    fm = sh("findmnt", "-n", "-o", "SOURCE,OPTIONS", MP).stdout.split()
    r.c("sursa_sda1", bool(fm) and fm[0] == "/dev/sda1", fm)
    opts = set(fm[1].split(",")) if len(fm) > 1 else set()
    r.c("optiuni", {"rw", "nosuid", "nodev", "relatime"} <= opts, sorted(opts))
    a = sh("systemctl", "is-active", UNIT).stdout.strip()
    r.c("unitate_activa", a == "active", a)
    j = sh("journalctl", "-b", "-u", UNIT, "--no-pager", "-o", "short-iso").stdout
    r.c("montat_de_systemd_in_boot_curent", "Mounted" in j, j[-400:])
    d = Path(MP) / "QL649_SM1_TEST"
    try:
        d.mkdir(exist_ok=True)
        t = d / f"test_{utc()}.txt"
        t.write_text("SM1\n")
        ok = t.read_text() == "SM1\n"
        t.unlink()
        d.rmdir()
    except OSError as e:
        ok = str(e)
    r.c("scriere_test_tony", ok is True, ok)
    return r.done({"journal": j[-1200:]})


def _session_start() -> str | None:
    s = sh("loginctl", "list-sessions", "--no-legend").stdout.split("\n")
    ts = []
    for line in s:
        f = line.split()
        if len(f) >= 3 and f[2] == "tony":
            t = sh("loginctl", "show-session", f[0], "-p", "Timestamp", "--value").stdout.strip()
            if t:
                ts.append(sh("date", "-u", "-d", t, "+%Y-%m-%dT%H:%M:%S").stdout.strip())
    return min(ts) if ts else None


def m4() -> int:
    r = R("M4")
    boot = sh("date", "-u", "-d", sh("uptime", "-s").stdout.strip(), "+%Y-%m-%dT%H:%M:%S").stdout.strip()
    j = sh("journalctl", "-b", "-u", UNIT, "--no-pager", "-o", "short-iso-precise", "--utc").stdout
    m = re.search(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\S*\s.*Mounted", j, re.M)
    mounted = m.group(1) if m else None
    sess = _session_start()
    r.c("montat_in_boot_curent", mounted is not None, j[-400:])
    r.c("inainte_de_login", bool(mounted and sess and mounted < sess), {"boot": boot, "montat": mounted, "sesiune": sess})
    return r.done({"boot_utc": boot, "montat_utc": mounted, "sesiune_utc": sess})


def m5() -> int:
    r = R("M5")
    rows = []
    for u, tag in (("ql649-tu4-judecator", "[judecator]"), ("ql649-tu4-emitere", "[emitere]")):
        out = sh("journalctl", "--user", "-b", "-u", u, "--no-pager", "-o", "short-iso", "--utc").stdout
        for line in out.splitlines():
            if tag + " SSD" in line:
                rows.append(line)
    rows.sort()
    first = rows[0] if rows else None
    r.c("prima_rulare_ssd_montat", bool(first) and "SSD montat" in first, first)
    r.c("nicio_rulare_indisponibil", not any("SSD indisponibil" in x for x in rows), [x for x in rows if "indisponibil" in x])
    return r.done({"rulari": rows[:10]})


if __name__ == "__main__":
    a = sys.argv[1:]
    fn = {"m0": m0, "m2": m2, "m4": m4, "m5": m5}
    if a and a[0] == "m1" and len(a) == 2:
        sys.exit(m1(a[1]))
    if a and a[0] in fn:
        sys.exit(fn[a[0]]())
    print(__doc__)
    sys.exit(2)
