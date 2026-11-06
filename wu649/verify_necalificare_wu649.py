"""Verificare independentă a NECALIFICĂRII WU649 (WU_NOT_QUALIFIED, 5/6).

NU importă wu649.py, bo649.py, engine.py, parser.py sau validare.py și NU citește arhiva
reală. Reutilizează doar funcțiile de formulare independentă din verify_wu649.py
(Gauss–Legendre pe u, derivate în (w_S, W_c), Newton propriu, π_j prin programare dinamică
proprie). Reconstruiește fixture-ul Q5/Q6 direct din textul protocolului §4 și confirmă:
martorul de informație trece, martorul de decizie eșuează, verdictul este WU_NOT_QUALIFIED,
iar istoria reală nu a fost atinsă.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

import verify_wu649 as V  # formulare independentă (nu modelul)

HERE = Path(__file__).resolve().parent
OUT = HERE / "rezultate"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fixture_from_protocol() -> np.ndarray:
    """§4 Q5: rest=(8..49); ciclul i = β_i, γ_i, α; 400 de cicluri; o extragere pe pas."""
    rest = list(range(8, 50))
    rows = []
    for i in range(400):
        for S in ([7] + [rest[(5 * i + m) % 42] for m in range(5)],
                  [rest[(6 * i + m + 21) % 42] for m in range(6)],
                  [1, 2, 3, 4, 5, 6]):
            y = np.zeros(49)
            y[np.array(S) - 1] = 1.0
            rows.append(y)
    return np.array(rows)


def ticket(score: np.ndarray) -> list[int]:
    return sorted(j + 1 for j in sorted(range(49), key=lambda j: (-score[j], j))[:6])


def b_and_r(Y: np.ndarray):
    c = Y.sum(0)
    ew = np.zeros(49)
    g = 2.0 ** (-1.0 / 26.0)
    for y in Y:
        ew = ew * g + y
    return (c + 1) / (c + 1).sum(), (ew + 0.5) / (ew + 0.5).sum(), c


def race_identity_exact(n_inst: int = 12) -> bool:
    rng = np.random.default_rng([649, 8, 77])
    ok = True
    for _ in range(n_inst):
        N = int(rng.integers(4, 7))
        k = int(rng.integers(2, min(4, N)))
        w = [Fraction(int(a), int(b)) for a, b in zip(rng.integers(1, 10, N), rng.integers(1, 5, N))]
        W = sum(w)
        tot = Fraction(0)
        for S in itertools.combinations(range(N), k):
            po = Fraction(0)
            for perm in itertools.permutations(S):
                pr, rem = Fraction(1), W
                for i in perm:
                    pr *= w[i] / rem
                    rem -= w[i]
                po += pr
            Wc = W - sum(w[i] for i in S)
            ie = sum(((-1) ** len(A)) * Wc / (Wc + sum((w[i] for i in A), Fraction(0)))
                     for r in range(k + 1) for A in itertools.combinations(S, r))
            ok &= (po == ie)
            tot += po
        ok &= (tot == 1)
    return bool(ok)


def main() -> int:
    checks = []

    def chk(name, ok, val=None):
        checks.append({"check": name, "pass": bool(ok), "value": val})

    seal = json.loads((HERE / "SIGILIU_PROTOCOL_WU649.json").read_text())
    aseal = json.loads((HERE / "SIGILIU_AMENDAMENT_01.json").read_text())
    qual = json.loads((OUT / "CALIFICARE.json").read_text())
    chk("protocol_sha_eq_seal_eq_qualification", sha(HERE / "PREINREGISTRARE_WU649.md") == seal["sha256"]
        == qual["protocol_sha256"])
    chk("amendment01_sha_eq_seal_eq_qualification", sha(HERE / "AMENDAMENT_01.md") == aseal["sha256"]
        == qual["amendment01_sha256"])
    chk("seal_order_protocol_lt_amendment_lt_qualification",
        seal["sealed_at_utc"] < aseal["sealed_at_utc"] < qual["utc"],
        [seal["sealed_at_utc"], aseal["sealed_at_utc"], qual["utc"]])
    chk("dir_at_seal_only_protocol", seal["dir_listing_at_seal"] == ["PREINREGISTRARE_WU649.md"])
    chk("dir_at_amendment_no_code", not any(f.endswith(".py") for f in aseal["dir_listing_at_seal"]),
        aseal["dir_listing_at_seal"])
    chk("qualification_code_archived_byte_identical",
        sha(OUT / "cod_calificare" / "wu649.py") == qual["code_sha256"], qual["code_sha256"])
    chk("status_not_qualified_5_of_6", qual["status"] == "WU_NOT_QUALIFIED" and qual["passed"] == 5)
    chk("only_Q6_failed", [c["id"] for c in qual["checks"] if not c["pass"]] == ["Q6"])
    chk("real_archive_not_read", qual.get("real_archive_read") is False)
    chk("no_backtest_artifacts", not (OUT / "backtest_unic").exists())
    chk("race_identity_exact_in_Q_independent", race_identity_exact())

    Yp = fixture_from_protocol()
    Ym = Yp.copy()
    Ym[:, [5, 6]] = Ym[:, [6, 5]]
    piBp, piRp, cp = b_and_r(Yp)
    piBm, _, cm = b_and_r(Ym)
    chk("fixture_counts_1_to_7_eq_400", bool(np.all(cp[:7] == 400)), cp[:8].tolist())
    chk("B_identical_Hplus_Hminus", bool(np.array_equal(piBp, piBm) and np.array_equal(cp, cm)))
    thp, thm = V.newton(Yp), V.newton(Ym)
    gp = float(np.abs(V.post(thp, Yp, False)[1]).max())
    gm = float(np.abs(V.post(thm, Ym, False)[1]).max())
    chk("indep_newton_converged", max(gp, gm) <= 1e-8, [gp, gm])
    qp, qm = V.incl(thp), V.incl(thm)
    dq = float(np.abs(qp - qm).max())
    chk("Q5_info_witness_reconfirmed_dq_ge_1e-3", dq >= 1e-3, dq)
    det = qual["checks"][4]["detail"]
    chk("q6_q7_match_qualification_1e-8",
        abs(qp[5] - det["q6_q7_Hplus"][0]) <= 1e-8 and abs(qp[6] - det["q6_q7_Hplus"][1]) <= 1e-8,
        [float(qp[5]), float(qp[6])])
    chk("anticipation_q7_gt_q6_false", bool(qp[5] > qp[6]), [float(qp[5]), float(qp[6])])
    tW, tB, tR = ticket(qp), ticket(piBp), ticket(piRp)
    chk("Q6_decision_witness_fails_WU_eq_B_eq_R", tW == tB == tR == [1, 2, 3, 4, 5, 6], [tW, tB, tR])
    passed_recomputed = 4 + int(dq >= 1e-3) + int(set(tW) != set(tB) and set(tW) != set(tR))
    chk("verdict_recomputed_not_qualified", passed_recomputed == 5, passed_recomputed)
    banned = [m for m in ("wu649", "bo649", "parser", "engine", "validare", "torch") if m in sys.modules]
    chk("no_forbidden_imports", not banned, banned)
    nf = sum(not c["pass"] for c in checks)
    out = {"status": "PASS" if nf == 0 else "FAIL", "n_checks": len(checks), "n_fail": nf,
           "verdict_confirmed": "WU_NOT_QUALIFIED", "note": "Q1–Q4 sunt reconfirmate doar prin artefact și "
           "identitatea exactă independentă; Q5/Q6 sunt recalculate independent.", "checks": checks}
    (OUT / "VERIFICARE_NECALIFICARE.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "checks"}, indent=2, ensure_ascii=False))
    return 0 if nf == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
