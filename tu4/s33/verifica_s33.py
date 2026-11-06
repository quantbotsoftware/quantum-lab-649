"""Verificatorul S33 (protocol tu4/PROTOCOL_QUANTUM_S33.md §3–§4). Scris DUPĂ sigiliul tu4/SIGILIU_TU4_S33.json.
Scrie numai fișiere NOI în tu4/rezultate/S33/. Nu scrie în tribunal, nu rescrie incidente, verificatoare vechi sau fișe.

Utilizare:
  verifica_s33.py q7s <log>                         Q7S: Q7L cu paritate_completa în locul paritate_587 + K/P/I
  verifica_s33.py rezolutie <Q7S.json> <Q7L.json> <V0L.json>   REZOLUTIE_S31_01 (numai dacă Q7S = PASS)
Calcul clasic; verificări de metadate și integritate; positive_claims_allowed=false.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

QL = Path(".")
REPO = Path(".")
OUT = QL / "tu4/rezultate/S33"
SEAL_PATH = QL / "tu4/SIGILIU_TU4_S33.json"
SEAL_SHA = "5caceda6069e314a3f1f189c59c869620ab3410c20543d1dc434f31a93325ff2"
SEAL = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
BIN = REPO / "rust_core/target/release/rust-singularity-core"
BIN_SHA = "c20fdcd2f7f237578d1f0ea85c05f9bf6b32a888d228e4443b6756dd1d43fd9e"
KERNEL = "7.0.11-76070011-generic"
MAN22 = QL / "tu4/rezultate/S22/MANIFEST_RUST_CORE_20261028T032900Z.json"
SEAL25 = json.loads((QL / "tu4/SIGILIU_TU4_S25.json").read_text(encoding="utf-8"))
I2 = ("tu4/rezultate/S31/INCIDENT_S31_01.json", "tu4/rezultate/S25/Q7L_VERIFICARE_20261029T184906Z.json",
      "tu4/rezultate/S25/V0L_VERIFICARE_20261029T184906Z.json", "tu4/rezultate/S31/NOTA_COMPLETARE_S31.md")
I3 = ("tu4/s25/verifica_s25.py", "tu4/rezultate/S25/primul_pas_S26.sh", "tu4/SIGILIU_TU4_S25.json",
      "tu4/rezultate/S29/FISA_DUMINICA_S29.json", "loto_romania/cohorta.py", "tu4/PROTOCOL_QUANTUM_S32.md")
SERVICE_ENV = {"OPENBLAS_NUM_THREADS": "2", "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def p(rel: str) -> Path:
    if rel.startswith("/"):
        return Path(rel)
    return REPO / rel if rel.startswith(("rust_core/", "loto_romania/")) else QL / rel


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def run(cmd, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


class Report:
    def __init__(self, crit: str):
        self.crit, self.checks = crit, []

    def check(self, name: str, ok, detail=None):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def finish(self, extra: dict | None = None) -> tuple[int, Path]:
        n_pass = sum(c["ok"] for c in self.checks)
        verdict = "PASS" if self.checks and n_pass == len(self.checks) else "FAIL"
        doc = {"criteriu": self.crit, "verdict": verdict, "n_checks": len(self.checks), "n_pass": n_pass,
               "protocol": "TU4-S33", "seal_sha256": SEAL_SHA, "utc": utc_now(), "checks": self.checks,
               **(extra or {}), "positive_claims_allowed": False}
        OUT.mkdir(parents=True, exist_ok=True)
        f = OUT / f"{self.crit}_VERIFICARE_{doc['utc']}.json"
        assert not f.exists()
        f.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "n_checks", "n_pass")}, indent=2))
        for c in self.checks:
            if not c["ok"]:
                print("FAIL", self.crit, c["name"], json.dumps(c["detail"], ensure_ascii=False)[:400])
        print(f, sha(f))
        return (0 if verdict == "PASS" else 1), f


def find_values(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            else:
                yield from find_values(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from find_values(v, key)


def log_parity(lines: list[str]) -> dict:
    """Blocul de paritate din log: linia referinței, apoi max_abs_delta/n_checks/n_pass/verdict, apoi PARITY_RC."""
    idx = [i for i, x in enumerate(lines) if x.startswith("PARITY_RC=")]
    if len(idx) != 1:
        return {"eroare": f"PARITY_RC apare de {len(idx)} ori"}
    i = idx[0]
    block = lines[max(0, i - 6): i]
    d = {"PARITY_RC": lines[i].split("=", 1)[1]}
    for x in block:
        m = re.match(r'^\s+"(n_checks|n_pass|verdict_B2_B7|max_abs_delta_float)": (.+?),?$', x)
        if m:
            d[m.group(1)] = json.loads(m.group(2))
        if re.search(r"/REFERINTA_PARITATE_\d{8}T\d{6}Z\.json$", x.strip()):
            d["referinta"] = x.strip()
    return d


# ----------------------------------------------------------------------------------------------------------- Q7S
def q7s(log: Path) -> int:
    r = Report("Q7S")
    t = log.read_text(encoding="utf-8", errors="replace")
    lines = t.splitlines()
    m = re.search(r"primul_pas_S26_(\d{8}T\d{6}Z)\.log$", log.name)
    log_utc = m.group(1) if m else None

    # K — mediu
    r.check("K1_kernel_7_0_11", platform.release() == KERNEL, platform.release())
    env = {**os.environ, **SERVICE_ENV}
    dg = run(["/usr/bin/python3", "-B", str(QL / "tu4/rezultate/S32/diag_gpu_v1.py")], env=env, timeout=600)
    last = (dg.stdout.strip().splitlines() or [""])[-1]
    r.check("K2_identitate_gpu_v1_egala", dg.returncode == 0 and last == "equal",
            {"rc": dg.returncode, "stdout": dg.stdout.strip().splitlines()[-4:], "stderr": dg.stderr[-400:],
             "env": SERVICE_ENV})
    res = run(["systemctl", "--user", "show", "-p", "Result", "--value", "loto-actualizare.service"]).stdout.strip()
    jr = run(["journalctl", "--user", "-b", "-u", "loto-actualizare.service", "-o", "cat", "--no-pager"]).stdout
    n_guard = jr.count("Model/environment changed")
    r.check("K3_actualizare_fara_garda", res == "success" and n_guard == 0, {"Result": res, "mesaje_garda_boot": n_guard})

    # L — logul primului pas
    sys.path.insert(0, str(QL / "tu4/s25"))
    import verifica_s25 as V25  # noqa: E402  (cod înghețat; numai v0l_checks, fără fișier)
    v = V25.v0l_checks(log)
    allowed = set(SEAL25["incidents_before"])
    fails = [c for c in v if not c["ok"]]
    inc = next((c for c in v if c["name"] == "incidente"), None)
    inc_found = set((inc or {}).get("detail", {}).get("gasite", [])) if inc else set()
    r.check("L1_v0l_numai_incidente_si_paritate",
            len(v) == 29 and {c["name"] for c in fails} <= {"incidente", "paritate"} and inc_found <= allowed,
            {"n": len(v), "fails": [(c["name"], c["detail"]) for c in fails]})
    found = sorted(d.name for d in (QL / "tu4/incidente").iterdir() if d.is_dir())
    r.check("L2_incidente_cunoscute_9", set(found) == allowed and len(found) == 9, found)
    lp = log_parity(lines)
    r.check("L3_paritate_completa_log", lp.get("verdict_B2_B7") == "PASS" and isinstance(lp.get("n_checks"), int)
            and lp.get("n_pass") == lp.get("n_checks") and lp.get("PARITY_RC") == "0", lp)
    for k, pat in (("L4_rust_61", r"test result: ok\. 61 passed"),
                   ("L5_q0_pass", r'"criteriu": "Q0",\s+"verdict": "PASS"'),
                   ("L6_q1_pass", r'"criteriu": "Q1",\s+"verdict": "PASS"'),
                   ("L7_serviciu_reusit", r"^S24_SERVICIU Result=success"),
                   ("L8_decontare_completa", r'"verdict": "DECONTARE_COMPLETA"'),
                   ("L9_b5_sau_b2", r"^(B5_RC=0|B2_RC=0)$")):
        r.check(k, re.search(pat, t, re.M) is not None)
    bad = [x for x in lines if x.startswith(("FAIL Q", "FAIL A"))]
    r.check("L10_fara_fail_q_a", not bad, bad)
    r.check("L11_dl_rc_0", "DL_RC=0" in lines)
    r.check("L12_a0_pass_scut", re.search(r'"criteriu": "A0",\s+"verdict": "PASS"', t) is not None
            and re.search(r"^SCUT_LANT OK linii \d+ \[\]$", t, re.M) is not None)
    q4 = re.search(r'"criteriu": "Q4",\s+"verdict": "(\w+)"', t)
    r.check("L13_q4_pass", q4 is not None and q4.group(1) == "PASS", q4.group(1) if q4 else None)

    # P — reproducerea parității
    r.check("P1_binar_c20fdcd2", sha(BIN) == BIN_SHA, sha(BIN))
    man = json.loads(MAN22.read_text())
    badsrc = {k: (oct(mode(p(k))), sha(p(k)) == d["sha256"]) for k, d in man["sources"].items()
              if mode(p(k)) != 0o444 or sha(p(k)) != d["sha256"]}
    r.check("P2_surse_rust_27_0444_sha", len(man["sources"]) == 27 and not badsrc, badsrc)
    ref = Path(lp.get("referinta", "/nonexistent"))
    cur = json.loads((QL / "tu3/date/live/CURRENT_LIVE.json").read_text())
    info = {"referinta": str(ref), "live_version_dir": cur["version_dir"]}
    ok3 = False
    if ref.exists():
        rd = json.loads(ref.read_text())
        vds = sorted(set(find_values(rd, "version_dir")))
        info.update({"ref_run_utc": rd.get("run_utc"), "ref_version_dirs": vds, "ref_sha256": sha(ref)})
        ref_utc = re.search(r"(\d{8}T\d{6}Z)\.json$", ref.name).group(1)
        ok3 = bool(vds) and vds == [cur["version_dir"]] and log_utc is not None and ref_utc >= log_utc
    r.check("P3_referinta_aceeasi_versiune_live", ok3, info)
    full, ok4, det4 = None, False, {}
    if ref.exists():
        pr = run([str(BIN), "parity", "--ref", str(ref), "--root", str(QL)], timeout=3600)
        try:
            full = json.loads(pr.stdout)
        except json.JSONDecodeError:
            full = None
        det4 = {"rc": pr.returncode, "stderr": pr.stderr[-400:]}
        if full is not None:
            groups = full.get("groups", {})
            det4.update({"n_checks": full.get("n_checks"), "n_pass": full.get("n_pass"),
                         "verdict_B2_B7": full.get("verdict_B2_B7"), "groups": groups,
                         "max_abs_delta_float": full.get("max_abs_delta_float")})
            ok4 = (pr.returncode == 0 and full.get("verdict_B2_B7") == "PASS"
                   and full.get("n_pass") == full.get("n_checks") == lp.get("n_checks")
                   and all(g.get("verdict") == "PASS" for g in groups.values())
                   and sum(g.get("checks", 0) for g in groups.values()) == full.get("n_checks"))
            OUT.mkdir(parents=True, exist_ok=True)
            pf = OUT / f"PARITATE_COMPLETA_{utc_now()}.json"
            pf.write_text(pr.stdout, encoding="utf-8")
            det4["fisier"], det4["sha256"] = str(pf), sha(pf)
    r.check("P4_paritate_reprodusa", ok4, det4)
    n = (full or {}).get("n_checks")
    p5 = {"n_checks": n, "fata_de_587": (n - 587) if isinstance(n, int) else None,
          "fata_de_552": (n - 552) if isinstance(n, int) else None,
          "grupe": {g: d.get("checks") for g, d in (full or {}).get("groups", {}).items()}}

    # I — integritate
    pdoc = "tu4/PROTOCOL_QUANTUM_S33.md"
    r.check("I1_sigiliu_si_protocol", sha(SEAL_PATH) == SEAL_SHA and mode(SEAL_PATH) == 0o444
            and sha(p(pdoc)) == SEAL["documents"][pdoc]["sha256"] and mode(p(pdoc)) == 0o444)
    fz = SEAL["frozen_hashes"]
    d2 = [k for k in I2 if sha(p(k)) != fz[k]]
    r.check("I2_S31_neschimbat", not d2, d2)
    d3 = [k for k in I3 if sha(p(k)) != fz[k]]
    r.check("I3_inghetate_neschimbate", not d3, d3)

    rc, _ = r.finish({"log": str(log), "log_sha256": sha(log), "P5_informativ": p5})
    print(f"Q7S_RC={rc}")
    return rc


# ------------------------------------------------------------------------------------------------------ rezolutie
def rezolutie(q7s_f: Path, q7l_f: Path, v0l_f: Path) -> int:
    q = json.loads(q7s_f.read_text())
    if q.get("criteriu") != "Q7S" or q.get("verdict") != "PASS":
        print("REZOLUTIE_REFUZATA Q7S nu este PASS")
        return 1
    assert sha(p("tu4/rezultate/S31/INCIDENT_S31_01.json")) == SEAL["frozen_hashes"]["tu4/rezultate/S31/INCIDENT_S31_01.json"]
    ql, vl = json.loads(q7l_f.read_text()), json.loads(v0l_f.read_text())
    p5 = q.get("P5_informativ", {})
    doc = {
        "rezolutie": "S31_01", "protocol": "TU4-S33 §4", "seal_sha256": SEAL_SHA, "utc": utc_now(),
        "stare": "REZOLVAT_PROSPECTIV",
        "incident_neschimbat": True,
        "incident_sha256": SEAL["frozen_hashes"]["tu4/rezultate/S31/INCIDENT_S31_01.json"],
        "S31_verdict": "S31_FAIL (neschimbat; rezultatele publicate nu se rescriu)",
        "cauza_mediu": "kernel 7.2.6 în environment/platform ⇒ garda cohortei gpu-v1; înlăturată prin opțiunea A (S32 §3), "
                       "repornire în 7.0.11-76070011-generic (boot 2026-10-29T19:08:31Z)",
        "criteriu_inlocuit_prospectiv": "paritate_587 (Q7L/V0L) → Q7S paritate_completa (S33 §3)",
        "Q7S": {"fisier": str(q7s_f), "sha256": sha(q7s_f), "verdict": q["verdict"],
                "n": f"{q['n_pass']}/{q['n_checks']}"},
        "Q7L_S33": {"fisier": str(q7l_f), "sha256": sha(q7l_f), "verdict": ql.get("verdict"),
                    "n": f"{ql.get('n_pass')}/{ql.get('n_checks')}"},
        "V0L_S33": {"fisier": str(v0l_f), "sha256": sha(v0l_f), "verdict": vl.get("verdict"),
                    "n": f"{vl.get('n_pass')}/{vl.get('n_checks')}"},
        "paritate_informativ": p5,
        "incidente_proiect": "neschimbate; NU zero incidente",
        "positive_claims_allowed": False,
    }
    f = OUT / f"REZOLUTIE_S31_01_{doc['utc']}.json"
    assert not f.exists()
    f.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("REZOLUTIE", doc["stare"], f, sha(f))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["q7s", "rezolutie"])
    ap.add_argument("files", nargs="+", type=Path)
    a = ap.parse_args()
    if a.cmd == "q7s":
        return q7s(a.files[0])
    if len(a.files) != 3:
        ap.error("rezolutie cere Q7S.json Q7L.json V0L.json")
    return rezolutie(*a.files)


if __name__ == "__main__":
    sys.exit(main())
