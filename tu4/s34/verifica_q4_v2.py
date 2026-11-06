#!/usr/bin/env python3
"""Q4 v2 (S33_02) — protocol tu4/PROTOCOL_QUANTUM_S34.md, sigilat înainte de cod.

Identic cu Q4 din tu4/s24/verifica_s24.py, cu o singură diferență: ID-ul invocației se citește și din
USER_INVOCATION_ID (serviciu systemd --user). Read-only; scrie numai rezultatul în tu4/rezultate/S34/.
"""
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path

QL = Path("${QL649_ROOT:-.}")
sys.path.insert(0, str(QL / "tu4/s24"))
import verifica_s24 as V  # noqa: E402  (funcții reutilizate nemodificat)

OUT = QL / "tu4/rezultate/S34"
FIELDS = ("INVOCATION_ID", "_SYSTEMD_INVOCATION_ID", "USER_INVOCATION_ID")


def inv_of(e: dict) -> str:
    for f in FIELDS:
        if e.get(f):
            return e[f]
    return ""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    checks, info = [], {}

    def ck(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    sealed = dt.datetime.strptime(V.SEAL["sealed_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()
    bt = V.boot_epoch()
    info.update(boot_utc=dt.datetime.fromtimestamp(bt, dt.timezone.utc).isoformat(), sealed_utc=V.SEAL["sealed_utc"],
                unit=V.UNIT)
    unknown = None
    if bt < sealed:
        unknown = "boot anterior sigiliului S24"
    else:
        js = V.run(["journalctl", "--user", "-b", "-u", V.UNIT, "-o", "json", "--no-pager"]).stdout.splitlines()
        ev = [json.loads(x) for x in js if x.strip()]
        starts = [e for e in ev if str(e.get("MESSAGE", "")).startswith("Starting ")]
        first = starts[0] if starts else None
        ck("pornire_in_boot", first is not None, len(starts))
        if first:
            t_first = int(first["__REALTIME_TIMESTAMP"]) / 1e6
            info["prima_pornire_dupa_boot_s"] = round(t_first - bt, 1)
            ck("prima_pornire_le_600s_dupa_boot", t_first - bt <= 600, info["prima_pornire_dupa_boot_s"])
            inv = inv_of(first)
            info["invocatie"] = inv
            info["camp_invocatie"] = next((f for f in FIELDS if first.get(f)), None)
            j = V.invocation_journal(inv)
            info["jurnal_prima_invocatie"] = [x for x in j.splitlines() if x.startswith("SSD_")]
            ck("prima_invocatie_ssd_montat", re.search(r"^SSD_MONTAT /dev/\S+", j, re.M) is not None,
               info["jurnal_prima_invocatie"])
            fin = [e for e in ev if inv and inv_of(e) == inv and str(e.get("MESSAGE", "")).startswith("Finished ")]
            ck("prima_invocatie_finished", bool(fin), len(fin))
        ck("health_ok", V.health() == "ok")
        ls = V.listeners()
        ck("asculta_numai_127", bool(ls) and all(l.startswith("127.0.0.1:") for l, _ in ls), ls)
        pids = sorted({p for _, p in ls if p > 0})
        info["cgroups_informativ"] = {p: V.cgroup(p) for p in pids}

    n_pass = sum(c["ok"] for c in checks)
    verdict = "UNKNOWN" if unknown else ("PASS" if checks and n_pass == len(checks) else "FAIL")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT / f"Q4V2_VERIFICARE_{stamp}.json"
    while out.exists():
        time.sleep(1)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = OUT / f"Q4V2_VERIFICARE_{stamp}.json"
    doc = {"criteriu": "Q4V2", "verdict": verdict, "n_checks": len(checks), "n_pass": n_pass, "run_utc": stamp,
           "protocol": "TU4-S34", "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "checks": checks, **info, "positive_claims_allowed": False}
    if unknown:
        doc["motiv_unknown"] = unknown
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out.chmod(0o444)
    print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "n_checks", "n_pass")}, ensure_ascii=False))
    for c in checks:
        if not c["ok"]:
            print("FAIL", c["name"], c["detail"])
    print(out, hashlib.sha256(out.read_bytes()).hexdigest())
    return 0 if verdict in ("PASS", "UNKNOWN") else 1


if __name__ == "__main__":
    sys.exit(main())
