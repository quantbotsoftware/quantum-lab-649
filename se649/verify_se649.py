"""Verificator independent SE649 (PREINREGISTRARE_SE649.md §7).

NU importă se649.py, gl649.py, wu649.py, bo649.py, engine.py, parser.py sau validare.py. Reparsează
JSONL după QL649 §1, recalculează anotimpurile prin datetime.date și un dicționar explicit lună →
anotimp (nu prin formula din model), numărările pe anotimpuri, p̂ prin rezolvarea DIRECTĂ a
sistemului |O|×|O| (numpy.linalg.solve, fără Sherman–Morrison) la fiecare pas și în Q (Gauss–Jordan
propriu, Fraction) la pașii din 25 în 25, comparatorii (R prin recursie), legile, scorurile, porțile
și verdictul, apoi compară cu artefactele sigilate din rezultate/backtest_unic/.
"""
from __future__ import annotations

import datetime
import gzip
import hashlib
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUN = HERE / "rezultate" / "backtest_unic"
SRC = (HERE.parent.parent / "predictie_numere" / "probe_date" / "extrageri_649.jsonl").resolve()
WARM, HL = 100, 26.0
FP0 = Fraction(6, 49)
FTA2, FTB2, FS02 = FP0 * FP0 / 400, FP0 * FP0 / 25, FP0 * (1 - FP0) * Fraction(49, 48)
MONTH_TO_SEASON = {12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3, 11: 3}
FORBIDDEN = ("se649", "gl649", "wu649", "bo649", "engine", "parser", "validare")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse():
    rows = []
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(o, dict):
            continue
        k, d, ns = o.get("draw_key"), o.get("draw_date"), o.get("numbers_sorted")
        if not (isinstance(k, str) and k and isinstance(d, str)):
            continue
        try:
            datetime.date.fromisoformat(d)
        except ValueError:
            continue
        if not (isinstance(ns, list) and len(ns) == 6 and all(type(x) is int and 1 <= x <= 49 for x in ns)
                and len(set(ns)) == 6):
            continue
        rows.append((d, k, tuple(sorted(ns))))
    keys, sets, uniq = set(), set(), []
    for d, k, ns in rows:
        if k in keys or (d, ns) in sets:
            continue
        keys.add(k)
        sets.add((d, ns))
        uniq.append((d, k, ns))
    uniq.sort(key=lambda r: (r[0], r[1]))
    Y = np.zeros((len(uniq), 49))
    for i, (_, _, ns) in enumerate(uniq):
        Y[i, [x - 1 for x in ns]] = 1.0
    off, sdates = [0], [uniq[0][0]]
    for i in range(1, len(uniq)):
        if uniq[i][0] != uniq[i - 1][0]:
            off.append(i)
            sdates.append(uniq[i][0])
    off.append(len(uniq))
    seasons = np.array([MONTH_TO_SEASON[datetime.date.fromisoformat(d).month] for d in sdates])
    return Y, np.array(off), seasons


def gj_solve(A: list[list[Fraction]], b: list[Fraction]) -> list[Fraction]:
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        p = next(i for i in range(c, n) if M[i][c] != 0)
        M[c], M[p] = M[p], M[c]
        inv = 1 / M[c][c]
        M[c] = [x * inv for x in M[c]]
        for i in range(n):
            if i != c and M[i][c] != 0:
                f = M[i][c]
                M[i] = [M[i][j] - f * M[c][j] for j in range(n + 1)]
    return [M[i][n] for i in range(n)]


def system(n4, phi, exact: bool):
    O = [f for f in range(4) if n4[f] > 0]
    if exact:
        A = [[FTA2 + ((FTB2 + FS02 / int(n4[f])) if f == g else 0) for g in O] for f in O]
        s = [FTA2 + (FTB2 if f == phi else 0) for f in O]
    else:
        ta2, tb2, s02 = float(FTA2), float(FTB2), float(FS02)
        A = np.full((len(O), len(O)), ta2) + np.diag([tb2 + s02 / n4[f] for f in O])
        s = np.array([ta2 + (tb2 if f == phi else 0.0) for f in O])
    return O, A, s


def law(pi: np.ndarray) -> np.ndarray:
    base = 6 / 49
    d = 6 * pi - base
    lam = np.full(pi.shape[0], 0.5)
    for t in range(pi.shape[0]):
        for x in d[t]:
            if x > 0:
                lam[t] = min(lam[t], (1 - 1e-4 - base) / x)
            elif x < 0:
                lam[t] = min(lam[t], (base - 1e-4) / (-x))
    return base + lam[:, None] * d


def top6_rule(vals) -> list[int]:
    return sorted(j + 1 for j in sorted(range(49), key=lambda j: (-vals[j], j))[:6])


def main() -> int:
    checks = []

    def ck(name, ok, val=None):
        checks.append({"check": name, "pass": bool(ok), "value": val})

    start = json.loads((RUN / "START.json").read_text())
    seal = json.loads((RUN / "PREDICTII_SIGILIU.json").read_text())
    res = json.loads((RUN / "REZULTATE.json").read_text())
    qual = json.loads((HERE / "rezultate" / "CALIFICARE.json").read_text())
    ck("source_sha256", sha(SRC) == start["source_sha256"], sha(SRC))
    proto_seal = json.loads((HERE / "SIGILIU_PROTOCOL_SE649.json").read_text())
    ck("protocol_sha256", sha(HERE / "PREINREGISTRARE_SE649.md") == proto_seal["sha256"] == start["protocol_sha256"]
       == qual["protocol_sha256"])
    ck("protocol_sealed_before_code", proto_seal["dir_listing_at_seal"] == ["PREINREGISTRARE_SE649.md"])
    ck("qualification_sha256", sha(HERE / "rezultate" / "CALIFICARE.json") == start["qualification_sha256"])
    ck("qualified_6_of_6", qual["status"] == "SE_QUALIFIED" and qual["passed"] == 6)
    code_hashes = {sha(HERE / "se649.py"), sha(HERE / "rezultate" / "cod_calificare" / "se649.py"),
                   qual["code_sha256"], start["code_sha256"]}
    ck("same_code_qualification_and_backtest", len(code_hashes) == 1, sorted(code_hashes))
    Y, off, seasons = parse()
    K = off.shape[0] - 1
    ck("n_draws", Y.shape[0] == start["n_draws"] == 2595, int(Y.shape[0]))
    ck("n_steps", K == start["n_steps"] == 2527, int(K))
    ck("npz_sha256", sha(RUN / seal["npz"]) == seal["npz_sha256"] == res["predictions_sha256"])
    ck("exact_sha256", sha(RUN / seal["exact"]) == seal["exact_sha256"] == res["exact_predictions_sha256"])
    P = dict(np.load(RUN / seal["npz"]))
    with gzip.open(RUN / seal["exact"], "rb") as fh:
        EX = json.loads(fh.read().decode())
    ks = np.arange(WARM, K)
    ck("ks", np.array_equal(P["ks"], ks) and EX["ks"] == ks.tolist())
    ck("phi_saved", np.array_equal(P["phi"], seasons[ks]) and EX["phi"] == seasons[ks].tolist())

    # numărări pe anotimpuri (pe extrageri), prin acumulare proprie
    C4 = np.zeros((K + 1, 4, 49), dtype=np.int64)
    N4 = np.zeros((K + 1, 4), dtype=np.int64)
    for k in range(K):
        C4[k + 1] = C4[k]
        N4[k + 1] = N4[k]
        blk = Y[off[k]:off[k + 1]]
        C4[k + 1, seasons[k]] += blk.sum(0).astype(np.int64)
        N4[k + 1, seasons[k]] += blk.shape[0]
    ck("n4_saved", np.array_equal(P["n4"], N4[ks]))

    # comparatori
    D = np.vstack((np.zeros((1, 49)), np.cumsum(Y, 0)))
    counts = D[off[ks]].astype(np.int64)
    ew = np.zeros(49)
    EW = np.zeros((K, 49))
    dec = 2.0 ** (-1.0 / HL)
    for k in range(K):
        if k > 0:
            ew = dec * ew + Y[off[k - 1]:off[k]].sum(0)
        EW[k] = ew
    piB = (counts + 1.0) / (counts + 1.0).sum(1, keepdims=True)
    piR = (EW[ks] + 0.5) / (EW[ks] + 0.5).sum(1, keepdims=True)
    ck("piB", np.abs(piB - P["piB"]).max() <= 1e-12, float(np.abs(piB - P["piB"]).max()))
    ck("piR", np.abs(piR - P["piR"]).max() <= 1e-9, float(np.abs(piR - P["piR"]).max()))
    tB = np.array([top6_rule(r) for r in piB])
    tR = np.array([top6_rule(r) for r in piR])
    ck("ticket_B", np.array_equal(tB, P["ticket_B"]))
    ck("ticket_R", np.array_equal(tR, P["ticket_R"]))

    # SE: rezolvare directă float64 la fiecare pas
    pind = np.empty((len(ks), 49))
    for i, k in enumerate(ks):
        O, A, s = system(N4[k], int(seasons[k]), exact=False)
        w = np.linalg.solve(A, s)
        v = np.full(49, 6 / 49)
        for t, f in enumerate(O):
            v += w[t] * (C4[k, f] / N4[k, f] - 6 / 49)
        pind[i] = v
    dmax = float(np.abs(pind - P["p_SE"]).max())
    ck("p_direct_float_vs_saved_le_1e-12", dmax <= 1e-12, dmax)

    # fracțiile salvate: sumă exactă 6, interval, conversie float, bilete
    sum_ok, rng_ok, conv_max, tick_rule_ok, tick_valid_ok = True, True, 0.0, True, True
    for i in range(len(ks)):
        fr = [Fraction(s) for s in EX["p_hat"][i]]
        sum_ok &= (sum(fr) == 6)
        rng_ok &= all(0 < t < 1 for t in fr)
        conv_max = max(conv_max, max(abs(float(fr[j]) - P["p_SE"][i, j]) for j in range(49)))
        t = top6_rule(fr)
        tick_rule_ok &= (t == P["ticket_SE"][i].tolist())
        inn = set(t)
        tick_valid_ok &= (min(pind[i, j - 1] for j in inn) >= max(pind[i, j] for j in range(49) if j + 1 not in inn) - 1e-12)
    ck("exact_sum_6_all_steps", sum_ok)
    ck("exact_in_open_unit_interval", rng_ok)
    ck("exact_to_float_conversion", conv_max <= 1e-15, conv_max)
    ck("ticket_SE_exact_top6_rule", tick_rule_ok)
    ck("ticket_SE_valid_under_independent_p", tick_valid_ok)

    # rezolvare directă EXACTĂ (Gauss–Jordan, Fraction) la pașii din 25 în 25: ponderi și p̂
    sample = [i for i in range(len(ks)) if i % 25 == 0]
    exact_ok, w_ok = True, True
    for i in sample:
        k = int(ks[i])
        O, A, s = system(N4[k], int(seasons[k]), exact=True)
        w = gj_solve(A, s)
        p = []
        for j in range(49):
            v = FP0
            for t, f in enumerate(O):
                v += w[t] * (Fraction(int(C4[k, f, j]), int(N4[k, f])) - FP0)
            p.append(f"{v.numerator}/{v.denominator}")
        exact_ok &= (p == EX["p_hat"][i])
        w_ok &= ({str(f): f"{w[t].numerator}/{w[t].denominator}" for t, f in enumerate(O)} == EX["w"][i])
    ck("exact_direct_gauss_jordan_every_25", exact_ok, len(sample))
    ck("weights_exact_every_25", w_ok, len(sample))

    # legi, scoruri, porți, verdict
    rows = np.concatenate([np.full(off[k + 1] - off[k], k - WARM) for k in ks])
    y = np.concatenate([Y[off[k]:off[k + 1]] for k in ks])
    laws = {"SE": law(pind / 6), "B": law(piB), "R": law(piR)}
    ticks = {"SE": P["ticket_SE"], "B": tB, "R": tR}
    n = y.shape[0]
    half = n // 2
    per = {}
    for nm in ("SE", "B", "R"):
        q = laws[nm][rows]
        per[f"log_{nm}"] = (y * np.log(q) + (1 - y) * np.log(1 - q)).sum(1)
        per[f"brier_{nm}"] = ((q - y) ** 2).sum(1)
        per[f"hits_{nm}"] = np.array([int(y[r, ticks[nm][rows[r]] - 1].sum()) for r in range(n)])
    qU = np.full_like(y, 6 / 49)
    per["log_U"] = (y * np.log(qU) + (1 - y) * np.log(1 - qU)).sum(1)
    per["brier_U"] = ((qU - y) ** 2).sum(1)

    def summ(sl):
        o = {"targets": int(len(range(n)[sl]))}
        for nm in ("SE", "B", "R"):
            o[f"hits_{nm}"] = int(per[f"hits_{nm}"][sl].sum())
            o[f"excess_{nm}"] = o[f"hits_{nm}"] / o["targets"] - 36 / 49
        for nm in ("SE", "B", "R", "U"):
            o[f"log_{nm}"] = float(per[f"log_{nm}"][sl].sum())
            o[f"brier_{nm}"] = float(per[f"brier_{nm}"][sl].sum())
        return o

    T, H1, H2 = summ(slice(0, n)), summ(slice(0, half)), summ(slice(half, n))
    ck("n_targets", n == res["n_targets"] == 2495, n)
    ck("consistency_BO649_GL649_hitsB_hitsR", (T["hits_B"], T["hits_R"]) == (1847, 1821), [T["hits_B"], T["hits_R"]])
    mism = []
    for blk, mine in (("total", T), ("half1", H1), ("half2", H2)):
        for key, val in mine.items():
            ref = res[blk][key]
            ok = (val == ref) if key.startswith(("hits", "targets")) else abs(val - ref) <= 1e-6
            if not ok:
                mism.append([blk, key, val, ref])
    ck("scores_match_all_blocks", not mism, mism)
    g = [T["excess_SE"] >= 0.20,
         T["hits_SE"] > T["hits_B"] and T["hits_SE"] > T["hits_R"],
         T["log_SE"] - T["log_U"] > 0 and T["log_SE"] - T["log_B"] > 0,
         T["brier_SE"] < min(T["brier_U"], T["brier_B"], T["brier_R"]),
         all(h["excess_SE"] > 0 and h["hits_SE"] - h["hits_B"] > 0 for h in (H1, H2)),
         all(h["log_SE"] - h["log_B"] > 0 for h in (H1, H2))]
    verdict = "SE_PROMOVAT_EXPLORATORIU" if all(g) else "SE_NO_PROMOTION_EXPLORATORY"
    ck("gates_recomputed", [bool(x) for x in g] == [x["pass"] for x in res["gates"]], [bool(x) for x in g])
    ck("verdict_recomputed", verdict == res["verdict"], verdict)
    # statistica G descriptivă
    c, nn = C4[K].astype(float), N4[K].astype(float)
    e = 6.0 * nn[:, None] / 49
    Gs = float(2.0 * sum(c[f, j] * math.log(c[f, j] / e[f, 0]) for f in range(4) for j in range(49) if c[f, j] > 0))
    ck("G_statistic", abs(Gs - res["G_label_x_season"]) <= 1e-6, Gs)
    ck("positive_claims_allowed_false", res["positive_claims_allowed"] is False)
    imported = sorted(m for m in sys.modules if m.split(".")[0] in FORBIDDEN)
    ck("no_model_imports", not imported, imported)

    n_fail = sum(not c["pass"] for c in checks)
    rep = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "status": "PASS" if n_fail == 0 else "FAIL",
           "n_checks": len(checks), "n_fail": n_fail, "checks": checks, "verdict_recomputed": verdict,
           "gates_passed_recomputed": int(sum(g)), "imports_model": bool(imported), "verifier_sha256": sha(Path(__file__))}
    (RUN / "VERIFICARE_INDEPENDENTA.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n",
                                                      encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("status", "n_checks", "n_fail", "verdict_recomputed",
                                          "gates_passed_recomputed", "imports_model")}, indent=2))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
