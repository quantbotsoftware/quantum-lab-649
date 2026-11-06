"""TU4-FR-01: reclasificarea familiilor S10 după orizontul cu pornire de la arhivă (numai biblioteca standard).

Regula (AMENDAMENT_TU4_FR_01.md §2): N_cald = min N >= 1 cu N*D_max - (df/2)*ln(1 + N/T) >= ln(300).
Intrări: numai D_max, df, T din FR_REZULTATE.json (nicio extragere recitită). Ieșire 0444, refuză suprascrierea.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FR = ROOT / "tu4/rezultate/FR/FR_REZULTATE.json"
SEAL = ROOT / "tu4/SIGILIU_AMENDAMENT_TU4_FR_01.json"
OUT = ROOT / "tu4/rezultate/FR/RECLASIFICARE_FR01.json"
TARGET = math.log(300.0)
NMAX = 10_000_000


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def n_cald(D: float, df: int, T: int) -> int:
    for N in range(1, NMAX):
        if N * D - 0.5 * df * math.log1p(N / T) >= TARGET:
            return N
    raise RuntimeError("N_cald > NMAX")


def clasa(N: int) -> str:
    return "FR_FEZABIL" if N <= 520 else ("FR_LENT" if N <= 2080 else "FR_NEFEZABIL")


def main() -> int:
    if OUT.exists():
        print("refuz: rezultatul există deja", file=sys.stderr)
        return 2
    seal = json.loads(SEAL.read_text())
    amd = ROOT / seal["file"]
    assert sha(amd) == seal["sha256"], "amendamentul nu corespunde sigiliului"
    assert sha(FR) == seal["inputs"]["tu4/rezultate/FR/FR_REZULTATE.json"], "FR_REZULTATE schimbat"
    fr = json.loads(FR.read_text())
    fam = []
    for g, rec in fr["games"].items():
        for c, v in rec["frontier"].items():
            N = n_cald(v["D_max"], v["df"], rec["T"])
            fam.append({"game": g, "family": c, "T": rec["T"], "df": v["df"], "D_max": v["D_max"],
                        "N_learner_M3_sealed": v["N_learner_M3"], "feasibility_sealed": v["feasibility"],
                        "N_cald": N, "years_cald": round(N / 104, 2), "feasibility_amended": clasa(N)})
    out = {"amendment": "TU4-FR-01", "seal_sha256": sha(SEAL), "fr_results_sha256": sha(FR),
           "code_sha256": sha(Path(__file__)), "rule": seal["rule"], "target_ln": TARGET,
           "computed_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "families": fam,
           "note": "Verdictul oficial S10 ramane cel sigilat (FR_NEFEZABIL); reclasificarea este publicata ALATURI, "
                   "margine superioara optimista; nu afirma ca vreo abatere exista.",
           "positive_claims_allowed": False}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    os.chmod(OUT, 0o444)
    for f in fam:
        print(f["game"], f["family"], f["N_learner_M3_sealed"], f["feasibility_sealed"], "->", f["N_cald"],
              f["years_cald"], f["feasibility_amended"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
