#!/usr/bin/env python3
"""Q7S v2 (protocol tu4/PROTOCOL_QUANTUM_S35.md, sigilat înainte de cod: tu4/SIGILIU_TU4_S35.json).

Rulează funcția înghețată `verifica_s33.q7s(log)` NEMODIFICATĂ (Report captat, OUT → tu4/rezultate/S35), păstrează
identic 19 verificări, înlocuiește exact L1/L10/L11/L13 cu L1v2/L10v2/L11v2a/L11v2b/L13v2a/L13v2b (DL v2, Q4 v2 rulate
în aceeași rulare) și adaugă I4/I5 (+ W1/W2 în modul c1).

Utilizare:  verifica_q7s_v2.py --mod {c1,repetitie} <cale absolută primul_pas_S26_<UTC>.log>
Calcul clasic; verificări de metadate și integritate; positive_claims_allowed=false.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

QL = Path(".")
REPO = Path(".")
OUT = QL / "tu4/rezultate/S35"
SEAL_PATH = QL / "tu4/SIGILIU_TU4_S35.json"
SEAL_SHA = "7a74d65c602518797724ccb96698bda0f83ef504a29b07443c2476c79a6b799d"
PROTO = "tu4/PROTOCOL_QUANTUM_S35.md"
DL_V2 = QL / "tu4/s34/verifica_publicarea_v2.py"
DL_V2_SHA = "7893db937b3ad882a2e450b211a244daa495cee7fffa84c473c10e5c20ee5b69"
Q4_V2 = QL / "tu4/s34/verifica_q4_v2.py"
Q4_V2_SHA = "c958bad76815a9c1be73fb4caf11ea76e1b510ac837b6ddc6688e3a1b453d519"
WIN = ("20261101T133600Z", "20261101T135759Z")
KEEP = ["K1_kernel_7_0_11", "K2_identitate_gpu_v1_egala", "K3_actualizare_fara_garda", "L2_incidente_cunoscute_9",
        "L3_paritate_completa_log", "L4_rust_61", "L5_q0_pass", "L6_q1_pass", "L7_serviciu_reusit",
        "L8_decontare_completa", "L9_b5_sau_b2", "L12_a0_pass_scut", "P1_binar_c20fdcd2", "P2_surse_rust_27_0444_sha",
        "P3_referinta_aceeasi_versiune_live", "P4_paritate_reprodusa", "I1_sigiliu_si_protocol", "I2_S31_neschimbat",
        "I3_inghetate_neschimbate"]
REPLACED = ["L1_v0l_numai_incidente_si_paritate", "L10_fara_fail_q_a", "L11_dl_rc_0", "L13_q4_pass"]
Q4_CUNOSCUT = re.compile(r"^FAIL Q4 (prima_invocatie_ssd_montat|prima_invocatie_finished)( |$)")
LIVE6 = {f"next_candidate/quantum_limit/prospectiv/{g}/{f}" for g in ("649", "540", "joker")
         for f in ("registru.json", "REZULTATE_PROSPECTIVE.md")}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def p(rel: str) -> Path:
    if rel.startswith("/"):
        return Path(rel)
    if rel.startswith(("rust_core/", "loto_romania/", "documentatie/", "next_candidate/")):
        return REPO / rel
    return QL / rel


class _Capture:
    """Înlocuiește verifica_s33.Report: colectează verificările, nu scrie fișiere."""
    last: tuple | None = None

    def __init__(self, crit: str):
        self.crit, self.checks = crit, []

    def check(self, name: str, ok, detail=None):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def finish(self, extra: dict | None = None):
        _Capture.last = (self.checks, extra or {})
        n_pass = sum(c["ok"] for c in self.checks)
        return (0 if self.checks and n_pass == len(self.checks) else 1), None


def frozen_q7s(log: Path) -> tuple[list[dict], dict, str]:
    sys.path.insert(0, str(QL / "tu4/s33"))
    import verifica_s33 as V33  # noqa: E402  (cod înghețat, numai importat)
    V33.Report = _Capture
    V33.OUT = OUT
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        V33.q7s(log)
    checks, extra = _Capture.last
    return checks, extra, buf.getvalue()


def semn_dl(lines: list[str]) -> tuple[bool, dict]:
    idx = [i for i, x in enumerate(lines) if x.startswith("DL_RC=")]
    if len(idx) != 1:
        return False, {"linii_DL_RC": len(idx)}
    i = idx[0]
    k = lines[i].split("=", 1)[1]
    prev = lines[i - 1] if i > 0 else ""
    if k == "0":
        return True, {"DL_RC": k}
    m = re.match(r"^AssertionError: Immutable: (\S+)$", prev)
    ok = k == "1" and m is not None and m.group(1) in LIVE6
    return ok, {"DL_RC": k, "linia_anterioara": prev[:200], "fisier_in_LIVE6": bool(m and m.group(1) in LIVE6)}


def run_sub(script: Path, want_sha: str, pat: str, crit: str, n_exp: int, start: str) -> tuple[bool, dict]:
    det = {"script": str(script), "script_sha256_inainte": sha(script)}
    if det["script_sha256_inainte"] != want_sha:
        det["eroare"] = "sha script diferit; nu se rulează"
        return False, det
    pr = subprocess.run(["/usr/bin/python3", "-B", str(script)], capture_output=True, text=True, timeout=3600)
    det.update(rc=pr.returncode, stdout_coada=pr.stdout.strip().splitlines()[-6:], stderr_coada=pr.stderr[-600:])
    m = None
    for x in pr.stdout.splitlines():
        m = re.match(r"^(/\S+/" + pat + r"_\d{8}T\d{6}Z\.json) ([0-9a-f]{64})$", x.strip()) or m
    if not m:
        det["eroare"] = "fișierul rezultat nu apare în ieșire"
        return False, det
    f = Path(m.group(1))
    det.update(fisier=str(f), sha256=sha(f), sha256_afisat=m.group(2))
    d = json.loads(f.read_text(encoding="utf-8"))
    det.update({k: d.get(k) for k in ("criteriu", "verdict", "n_checks", "n_pass", "run_utc", "script_sha256")})
    ok = (pr.returncode == 0 and det["sha256"] == m.group(2) and d.get("criteriu") == crit
          and d.get("verdict") == "PASS" and d.get("n_pass") == d.get("n_checks") == n_exp
          and d.get("script_sha256") == want_sha and str(d.get("run_utc", "")) >= start)
    return ok, det


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mod", choices=["c1", "repetitie"], required=True)
    ap.add_argument("log", type=Path)
    a = ap.parse_args()
    log = a.log
    start = utc_now()
    m = re.search(r"primul_pas_S26_(\d{8}T\d{6}Z)\.log$", log.name)
    log_utc = m.group(1) if m else None
    in_win = WIN[0] <= start <= WIN[1]
    if a.mod == "c1" and not in_win:
        print(f"Q7S2_REFUZ start {start} în afara ferestrei {WIN} ⇒ C1 PENDING (fără fișier)")
        return 3
    if not log.is_absolute() or not log.is_file():
        print("Q7S2_REFUZ logul trebuie dat cu cale absolută și să existe")
        return 2

    checks: list[dict] = []

    def ck(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    # 1) funcția înghețată, captată
    fz, fz_extra, fz_out = frozen_q7s(log)
    names = [c["name"] for c in fz]
    assert names == KEEP[:3] + ["L1_v0l_numai_incidente_si_paritate"] + KEEP[3:11] + \
        ["L10_fara_fail_q_a", "L11_dl_rc_0"] + [KEEP[11]] + ["L13_q4_pass"] + KEEP[12:], names
    by = {c["name"]: c for c in fz}
    for n in KEEP:
        checks.append(by[n])

    t = log.read_text(encoding="utf-8", errors="replace")
    lines = t.splitlines()
    fail_lines = [x for x in lines if x.startswith("FAIL ")]
    q4_lines = [x for x in lines if x.startswith("FAIL Q4")]
    ok_dl, det_dl = semn_dl(lines)

    # L1v2
    d1 = by["L1_v0l_numai_incidente_si_paritate"]["detail"] or {}
    fails = {f[0]: f[1] for f in d1.get("fails", [])}
    seal25 = json.loads((QL / "tu4/SIGILIU_TU4_S25.json").read_text(encoding="utf-8"))
    inc_found = set((fails.get("incidente") or {}).get("gasite", [])) if "incidente" in fails else set()
    ok1 = (d1.get("n") == 29 and set(fails) <= {"incidente", "paritate", "dl", "fara_fail"}
           and inc_found <= set(seal25["incidents_before"])
           and ("dl" not in fails or ok_dl)
           and ("fara_fail" not in fails or all(Q4_CUNOSCUT.match(x) for x in fail_lines)))
    ck("L1v2_v0l_numai_incidente_paritate_dl_q4", ok1,
       {"n": d1.get("n"), "picate": sorted(fails), "incidente_gasite": sorted(inc_found), "linii_FAIL": fail_lines})
    # L10v2
    bad = [x for x in lines if x.startswith(("FAIL Q", "FAIL A")) and not Q4_CUNOSCUT.match(x)]
    ck("L10v2_fara_fail_q_a_in_afara_S33_02", not bad, bad)
    # L11v2a / L11v2b
    ck("L11v2a_semnatura_dl_S33_01", ok_dl, det_dl)
    ok, det = run_sub(DL_V2, DL_V2_SHA, "DL_V2_VERIFICARE", "DL_V2", 19, start)
    ck("L11v2b_dl_v2_pass", ok, det)
    # L13v2a / L13v2b
    q4 = re.search(r'"criteriu": "Q4",\s+"verdict": "(\w+)"', t)
    v = q4.group(1) if q4 else None
    ok13 = v == "PASS" or (v == "FAIL" and bool(q4_lines) and all(Q4_CUNOSCUT.match(x) for x in q4_lines))
    ck("L13v2a_semnatura_q4_S33_02", ok13, {"q4_log": v, "linii_FAIL_Q4": q4_lines})
    ok, det = run_sub(Q4_V2, Q4_V2_SHA, "Q4V2_VERIFICARE", "Q4V2", 6, start)
    ck("L13v2b_q4_v2_pass", ok, det)
    # I4 / I5
    seal = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
    ck("I4_sigiliu_si_protocol_S35", sha(SEAL_PATH) == SEAL_SHA and SEAL_PATH.stat().st_mode & 0o777 == 0o444
       and sha(p(PROTO)) == seal["documents"][PROTO]["sha256"] and p(PROTO).stat().st_mode & 0o777 == 0o444,
       {"seal_sha256": sha(SEAL_PATH)})
    drift = [k for k, h in seal["frozen_hashes"].items() if not p(k).exists() or sha(p(k)) != h]
    ck("I5_inghetate_S35_neschimbate", not drift, {"n": len(seal["frozen_hashes"]), "drift": drift})

    end = utc_now()
    win_info = {"start_utc": start, "end_utc": end, "log_utc": log_utc, "fereastra": WIN}
    if a.mod == "c1":
        ck("W1_start_si_log_in_fereastra", in_win and log_utc is not None and WIN[0] <= log_utc <= WIN[1], win_info)
        ck("W2_sfarsit_in_fereastra", end <= WIN[1], win_info)

    n_pass = sum(c["ok"] for c in checks)
    n_exp = 29 if a.mod == "c1" else 27
    verdict = "PASS" if len(checks) == n_exp and n_pass == n_exp else "FAIL"
    if a.mod == "c1":
        other_fail = [c["name"] for c in checks if not c["ok"] and not c["name"].startswith("W")]
        c1 = "PASS" if verdict == "PASS" else ("UNKNOWN" if not other_fail else "FAIL")
    else:
        c1 = "NEAPLICABIL_REPETITIE"
    fz_n = sum(c["ok"] for c in fz)
    doc = {
        "criteriu": "Q7S2" if a.mod == "c1" else "Q7S2_REPETITIE", "verdict": verdict, "C1": c1,
        "n_checks": len(checks), "n_pass": n_pass, "mod": a.mod, "protocol": "TU4-S35", "seal_sha256": SEAL_SHA,
        "script_sha256": sha(Path(__file__)), "utc": end, **win_info,
        "log": str(log), "log_sha256": sha(log), "checks": checks,
        "Q7S_inghetat_informativ": {"verdict": "PASS" if fz_n == len(fz) else "FAIL", "n_pass": fz_n,
                                    "n_checks": len(fz), "picate": [c["name"] for c in fz if not c["ok"]],
                                    "inlocuite": REPLACED, "stdout_captat": fz_out[-3000:],
                                    "P5_informativ": fz_extra.get("P5_informativ")},
        "positive_claims_allowed": False,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / (f"Q7S2_VERIFICARE_{end}.json" if a.mod == "c1" else f"Q7S2_REPETITIE_{end}.json")
    assert not f.exists()
    f.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    f.chmod(0o444)
    print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "C1", "n_checks", "n_pass", "start_utc", "end_utc")},
                     ensure_ascii=False))
    for c in checks:
        if not c["ok"]:
            print("FAIL", doc["criteriu"], c["name"], json.dumps(c["detail"], ensure_ascii=False)[:500])
    print("Q7S_INGHETAT_INFORMATIV", doc["Q7S_inghetat_informativ"]["verdict"],
          f"{fz_n}/{len(fz)}", doc["Q7S_inghetat_informativ"]["picate"])
    print(f, sha(f))
    rc = 0 if verdict == "PASS" else 1
    print(f"Q7S2_RC={rc} C1={c1}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
