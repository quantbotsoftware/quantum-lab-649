#!/usr/bin/env python3
"""Verificator SEPARAT TU4-EM (protocol tu4/PROTOCOL_TU4_EM.md §7). Numai stdlib + NumPy: fără torch, fără import din tu4/.

    /usr/bin/python3 -B tu4/verifica_em.py                 # lanțul real → tu4/rezultate/EM/VERIFICARE_EM_<UTC>.json
    /usr/bin/python3 -B tu4/verifica_em.py --radacina DIR --test --ssd DIR   # rădăcină de test (fără fișier scris)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

TU4 = Path(__file__).resolve().parent
QL = TU4.parent
TZ = ZoneInfo("Europe/Bucharest")
GAMES = {"649": (49, 6, 6, False), "540": (40, 6, 5, False), "joker": (45, 5, 5, True)}
NB, K = 20, 4
SEAL_SHA = "82459f48458ef2ee248784929ea2c4c18ae60469b0084e4a7345910a7b5c53c7"
IP_CORE_SHA = "ab3e1de93d8e5ae537a8c80599905aaa19cc103602f9b18f4b7f7f6f8a48c302"
UNITS = ("ql649-tu4-emitere.service", "ql649-tu4-emitere.timer")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def shaf(p) -> str:
    return sha(Path(p).read_bytes())


def utc(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


# ------------------------------------------------ recalcul independent (NumPy, alt algoritm pentru π)
def theta_x2(c, N, n, k):
    p = k / n
    th = (n - 1) / n * (c / N - p) / (p * (1 - p))
    x2 = (n - 1) / n * ((c - N * p) ** 2).sum() / (N * p * (1 - p))
    return th, x2


def basis(n):
    i = np.arange(1, n + 1, dtype=float)[:, None]
    m = np.arange(1, K + 1, dtype=float)[None, :]
    return math.sqrt(2.0 / n) * np.cos(math.pi * m * (i - 0.5) / n)


def models(c, N, n, k):
    c = np.asarray(c, float)
    th, x2 = theta_x2(c, N, n, k)
    lam1 = max(0.0, 1.0 - (n - 3) / x2)
    p = k / n
    z = math.sqrt((n - 1) / n) * (c - N * p) / math.sqrt(N * p * (1 - p))
    B = basis(n)
    x2s = float(((z @ B) ** 2).sum())
    lam3 = max(0.0, 1.0 - (K - 2) / x2s)
    return {"H1": (lam1 * th, lam1, x2), "H3": (lam3 * ((th @ B) @ B.T), lam3, x2s)}


def log_esp(lw, k):
    """ln e_0..e_k(w) prin recurență în spațiul logaritmic."""
    L = np.full(k + 1, -np.inf)
    L[0] = 0.0
    for v in lw:
        for j in range(k, 0, -1):
            L[j] = np.logaddexp(L[j], v + L[j - 1])
    return L


def incl_D(lw, k):
    n = len(lw)
    Lk = log_esp(lw, k)[k]
    pi = np.empty(n)
    for i in range(n):
        Lm = log_esp(np.delete(lw, i), k - 1)[k - 1] if k > 1 else 0.0
        pi[i] = math.exp(lw[i] + Lm - Lk)
    D = float((pi * lw).sum() - Lk + math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1))
    return pi, D


def top(lw, b):
    order = np.lexsort((np.arange(len(lw)), -np.asarray(lw)))
    return sorted(int(i) + 1 for i in order[:b])


# ------------------------------------------------ verificarea
class V:
    def __init__(self):
        self.checks = []

    def add(self, name, ok, detail=""):
        self.checks.append({"check": name, "status": ok if isinstance(ok, str) else ("PASS" if ok else "FAIL"),
                            "detail": str(detail)[:400]})


def verify(root: Path, ssd: Path | None, test: bool) -> dict:
    v = V()
    # V1 sigiliile
    v.add("V1_protocol_seal_sha", shaf(TU4 / "SIGILIU_TU4_EM.json") == SEAL_SHA)
    seal = json.loads((TU4 / "SIGILIU_TU4_EM.json").read_text())
    v.add("V1_protocol_sha", shaf(TU4 / "PROTOCOL_TU4_EM.md") == seal["document"]["sha256"])
    drift = [f for f, h in seal["frozen_hashes"].items() if shaf(QL / f) != h]
    v.add("V1_frozen_drift_empty", not drift, drift)
    v.add("V1_ip_core_frozen", shaf(TU4 / "ip_core.py") == IP_CORE_SHA)
    cs_path = TU4 / "SIGILIU_TU4_EM_COD.json"
    cs = json.loads(cs_path.read_text()) if cs_path.exists() else None
    if cs:
        cd = [f for f, h in cs["files"].items() if shaf(QL / f) != h]
        v.add("V1_code_seal_drift_empty", not cd, cd)
    else:
        v.add("V1_code_seal_present", "UNKNOWN" if test else False, "sigiliul codului lipsește")
    trib = root / "tu4" / "tribunal"
    files = sorted((trib / "emisii").glob("*/*.json"))
    v.add("V0_emissions_present", len(files) > 0, len(files))
    lant_lines = (trib / "LANT.jsonl").read_bytes().splitlines() if (trib / "LANT.jsonl").exists() else []
    lant = [json.loads(x) for x in lant_lines]
    summary = []
    for game in GAMES:
        n, k, b, ball = GAMES[game]
        gfiles = sorted((trib / "emisii" / game).glob("*.json"))
        prev = shaf(TU4 / "SIGILIU_TU4_EM.json")
        for idx, f in enumerate(gfiles):
            data = f.read_bytes()
            em = json.loads(data)
            tag = f"{game}/{f.stem}"
            # V2 arhiva
            arch = em["archive"]
            ap = root / arch["file"]
            ok2 = ap.exists() and shaf(ap) == arch["sha256"]
            c = np.zeros(n)
            cb = np.zeros(NB)
            N = 0
            if ok2:
                rows = [json.loads(x) for x in ap.read_text(encoding="utf-8").splitlines() if x.strip()]
                N = len(rows)
                for r in rows:
                    nums = r["numbers"]
                    ok2 &= len(nums) == k and len(set(nums)) == k and all(1 <= x <= n for x in nums)
                    c[np.array(nums) - 1] += 1
                    if ball:
                        ok2 &= isinstance(r["joker"], int) and 1 <= r["joker"] <= NB
                        cb[r["joker"] - 1] += 1
                ok2 &= N == arch["records"] == em["warm_start"]["N"]
                ok2 &= [int(x) for x in c] == em["warm_start"]["counts"]
                if ball:
                    ok2 &= [int(x) for x in cb] == em["warm_start"]["ball_counts"]
            v.add(f"V2_archive_{tag}", bool(ok2), arch["file"])
            # V3 recalcul
            errs = []
            for urn, cc, nn, kk, bb in ((("main", c, n, k, b),) + ((("ball", cb, NB, 1, 1),) if ball else ())):
                ref = models(cc, N, nn, kk)
                for m in ("H1", "H3"):
                    blk = em["models"][m] if urn == "main" else em["models"][m]["ball"]
                    lw, lam, x2 = ref[m]
                    elw = np.array(blk["logw"])
                    if np.max(np.abs(elw - lw)) > 1e-12:
                        errs.append(f"{urn}.{m}.logw {np.max(np.abs(elw - lw)):.2e}")
                    if abs(blk["lambda"] - lam) > 1e-12 or abs(blk["X2"] - x2) > 1e-9 * max(1, x2):
                        errs.append(f"{urn}.{m}.lambda/X2")
                    if blk["bet_active"] != (lam > 0):
                        errs.append(f"{urn}.{m}.bet_active")
                    pi, D = incl_D(elw, kk)
                    if abs(blk["D_nats"] - D) > 1e-10:
                        errs.append(f"{urn}.{m}.D {abs(blk['D_nats'] - D):.2e}")
                    if kk == 1:
                        q = np.exp(elw - elw.max()); q /= q.sum()
                        if np.max(np.abs(np.array(blk["q"]) - q)) > 1e-12 or blk["top_ball"] != top(elw, 1)[0]:
                            errs.append(f"{urn}.{m}.q/top_ball")
                    else:
                        if np.max(np.abs(np.array(blk["pi"]) - pi)) > 1e-10 or abs(sum(blk["pi"]) - kk) > 1e-9:
                            errs.append(f"{urn}.{m}.pi")
                        if blk["top_ticket"] != top(elw, bb):
                            errs.append(f"{urn}.{m}.ticket")
                    # oglinda c64: consistența porții raportate
                    g = em["c64_mirror"]["per_model"][m][urn]
                    tol = 1e-5 + 1e-4 * float(np.max(np.abs(elw)))
                    if g["pass"] != (g["abs_dlambda"] <= 1e-4 and g["max_abs_dlogw"] <= tol) or abs(g["tol_logw"] - tol) > 1e-15:
                        errs.append(f"{urn}.{m}.c64_gate_inconsistent")
            v.add(f"V3_recompute_{tag}", not errs, errs)
            # V4 cronologia
            d = dt.date.fromisoformat(em["target_date"])
            draw = dt.datetime.combine(d, dt.time(18, 30), TZ)
            cut = dt.datetime.combine(d, dt.time(16, 0), TZ)
            ok4 = (d.weekday() in (3, 6) and utc(em["draw_utc"]) == draw and utc(em["cutoff_utc"]) == cut
                   and utc(em["emitted_utc"]) < utc(em["cutoff_utc"]) < utc(em["draw_utc"]) and f.stem == em["target_date"]
                   and em["game"] == game and em["test_mode"] == test)
            v.add(f"V4_chronology_{tag}", ok4, f"emitted {em['emitted_utc']} cutoff {em['cutoff_utc']}")
            # V5 lanțul per joc
            ch = em["chain"]
            v.add(f"V5_chain_{tag}", ch["index"] == idx and ch["prev_sha256"] == prev, ch)
            prev = sha(data)
            # V6 moduri
            v.add(f"V6_mode_{tag}", stat.S_IMODE(f.stat().st_mode) == 0o444)
            # V8 codul
            if cs:
                v.add(f"V8_code_{tag}", em["code"]["emite_sha256"] == cs["files"]["tu4/emite.py"]
                      and em["code"]["ip_core_sha256"] == IP_CORE_SHA and em["code"]["protocol_seal_sha256"] == SEAL_SHA)
            else:
                v.add(f"V8_code_{tag}", "UNKNOWN" if test else False, "fără sigiliu de cod")
            ok_flags = em["positive_claims_allowed"] is False and em["tribunal"]["M"] == 6 and em["tribunal"]["threshold"] == 600
            v.add(f"V3_flags_{tag}", ok_flags)
            # V7 oglinda SSD
            if ssd is not None and ssd.exists():
                sf = ssd / "emisii" / game / f.name
                v.add(f"V7_ssd_copy_{tag}", sf.exists() and sf.read_bytes() == data)
            else:
                v.add(f"V7_ssd_copy_{tag}", "UNKNOWN", "SSD nemontat / neindicat")
            summary.append({"game": game, "target": em["target_date"], "sha256": sha(data),
                            "H1": em["models"]["H1"]["top_ticket"], "H3": em["models"]["H3"]["top_ticket"],
                            "balls": ({m: em["models"][m]["ball"]["top_ball"] for m in ("H1", "H3")} if ball else None),
                            "lambda": {m: em["models"][m]["lambda"] for m in ("H1", "H3")}})
    # V5 registrul global
    ok5 = len(lant) == len(files)
    p = shaf(TU4 / "SIGILIU_TU4_EM.json")
    for i, (raw, rec) in enumerate(zip(lant_lines, lant)):
        fp = trib / rec["file"]
        ok5 &= rec["i"] == i and rec["prev_line_sha256"] == p and fp.exists() and shaf(fp) == rec["sha256"]
        p = sha(raw)
    ok5 &= len({(r["game"], r["target_date"]) for r in lant}) == len(lant)
    v.add("V5_lant_global", ok5, f"{len(lant)} linii / {len(files)} emisii")
    for name in ("LANT.jsonl", "RULARI.jsonl"):
        fp = trib / name
        v.add(f"V6_mode_{name}", fp.exists() and stat.S_IMODE(fp.stat().st_mode) == 0o444)
    # V7 jurnalul mmap
    if ssd is not None and ssd.exists():
        j = ssd / "JURNAL_EMISII.jsonl"
        recs = [json.loads(x) for x in j.read_text(encoding="utf-8").splitlines() if x.strip()] if j.exists() else []
        shas = {r["sha256"] for r in recs}
        v.add("V7_ssd_journal", j.exists() and all(shaf(f) in shas for f in files) and len(recs) == len(shas)
              and j.read_bytes().endswith(b"\n") and b"\x00" not in j.read_bytes(), f"{len(recs)} înregistrări")
        sl = ssd / "LANT.jsonl"
        v.add("V7_ssd_lant", sl.exists() and sl.read_bytes() == (trib / "LANT.jsonl").read_bytes())
    else:
        v.add("V7_ssd_journal", "UNKNOWN", "SSD nemontat / neindicat")
    # V9 unitățile instalate
    if test:
        v.add("V9_units", "UNKNOWN", "mod test")
    else:
        ud = Path.home() / ".config/systemd/user"
        ok9 = all((ud / u).exists() and shaf(ud / u) == shaf(TU4 / "systemd" / u) for u in UNITS)
        if cs:
            ok9 &= all(cs["files"][f"tu4/systemd/{u}"] == shaf(ud / u) for u in UNITS if (ud / u).exists())
        v.add("V9_units", ok9)
    st = [c["status"] for c in v.checks]
    hard_fail = any(s == "FAIL" for s in st)
    unknown_ok = all(c["status"] != "UNKNOWN" or c["check"].startswith(("V7", "V9", "V8", "V1_code")) for c in v.checks)
    verdict = "VERIFICARE_EM_PASS" if (not hard_fail and unknown_ok) else "VERIFICARE_EM_FAIL"
    return {"protocol": "TU4-EM", "verifier": "tu4/verifica_em.py", "verifier_sha256": shaf(Path(__file__)),
            "root": str(root), "test_mode": test, "verified_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_checks": len(st), "n_pass": st.count("PASS"), "n_fail": st.count("FAIL"), "n_unknown": st.count("UNKNOWN"),
            "verdict": verdict, "emissions": summary, "checks": v.checks, "positive_claims_allowed": False}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--radacina", type=Path, default=QL)
    ap.add_argument("--ssd", type=Path, default=None)
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args(argv)
    ssd = a.ssd
    if ssd is None and not a.test and os.path.ismount("./ssd_data"):
        ssd = Path("./ssd_data/QL649_TU4_EM")
    res = verify(a.radacina.resolve(), ssd, a.test)
    if not a.test:
        out = TU4 / "rezultate" / "EM" / f"VERIFICARE_EM_{res['verified_utc'].replace('-', '').replace(':', '')}.json"
        fd = os.open(out, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
        print(out)
    print(json.dumps({k: res[k] for k in ("verdict", "n_checks", "n_pass", "n_fail", "n_unknown")}))
    for c in res["checks"]:
        if c["status"] == "FAIL":
            print("FAIL", c["check"], c["detail"])
    return 0 if res["verdict"] == "VERIFICARE_EM_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
