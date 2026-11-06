"""Verificator independent CS649 (PREINREGISTRARE_CS649.md §7).

NU importă cs649.py, se649.py, gl649.py, wu649.py, bo649.py, engine.py, parser.py sau validare.py.
Reparsează JSONL după QL649 §1, recalculează indicele pașilor și fazele k mod 3, 5, 7, numărările pe
CELULELE k mod 105, p̂ prin forma PRIMALĂ pe celule (numpy.linalg.solve, fără sistemul Henderson) la
fiecare pas și sistemul Henderson în Q (Gauss–Jordan propriu, Fraction) la pașii din 25 în 25,
comparatorii (R prin recursie), legile, scorurile, porțile și verdictul, apoi compară cu artefactele
sigilate din rezultate/backtest_unic/.
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
FTA2, FT2, FS02 = FP0 * FP0 / 400, FP0 * FP0 / 16, FP0 * (1 - FP0) * Fraction(49, 48)
PER = (3, 5, 7)
FORBIDDEN = ("cs649", "se649", "gl649", "wu649", "bo649", "engine", "parser", "validare")


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
    off = [0]
    for i in range(1, len(uniq)):
        if uniq[i][0] != uniq[i - 1][0]:
            off.append(i)
    off.append(len(uniq))
    return Y, np.array(off)


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


def cell_levels(c: int) -> list[int]:
    """Nivelurile celulei c = k mod 105: a (0), (3, c mod 3), (5, c mod 5), (7, c mod 7)."""
    return [0, 1 + c % 3, 4 + c % 5, 9 + c % 7]


def matches(c1: int, c2: int) -> int:
    return sum(1 for K in PER if c1 % K == c2 % K)


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
    proto_seal = json.loads((HERE / "SIGILIU_PROTOCOL_CS649.json").read_text())
    ck("protocol_sha256", sha(HERE / "PREINREGISTRARE_CS649.md") == proto_seal["sha256"] == start["protocol_sha256"]
       == qual["protocol_sha256"])
    ck("protocol_sealed_before_code", proto_seal["dir_listing_at_seal"] == ["PREINREGISTRARE_CS649.md"])
    t_seal = datetime.datetime.fromisoformat(proto_seal["sealed_at_utc"])
    t_qual = datetime.datetime.fromisoformat(qual["utc"])
    t_start = datetime.datetime.fromisoformat(start["utc"])
    ck("time_order_seal_qualification_backtest", t_seal < t_qual < t_start,
       [proto_seal["sealed_at_utc"], qual["utc"], start["utc"]])
    ck("qualification_sha256", sha(HERE / "rezultate" / "CALIFICARE.json") == start["qualification_sha256"])
    ck("qualified_6_of_6", qual["status"] == "CS_QUALIFIED" and qual["passed"] == 6)
    code_hashes = {sha(HERE / "cs649.py"), sha(HERE / "rezultate" / "cod_calificare" / "cs649.py"),
                   qual["code_sha256"], start["code_sha256"]}
    ck("same_code_qualification_and_backtest", len(code_hashes) == 1, sorted(code_hashes))
    Y, off = parse()
    K = off.shape[0] - 1
    ck("n_draws", Y.shape[0] == start["n_draws"] == 2595, int(Y.shape[0]))
    ck("n_steps", K == start["n_steps"] == 2527, int(K))
    ck("npz_sha256", sha(RUN / seal["npz"]) == seal["npz_sha256"] == res["predictions_sha256"])
    ck("exact_sha256", sha(RUN / seal["exact"]) == seal["exact_sha256"] == res["exact_predictions_sha256"])
    P = dict(np.load(RUN / seal["npz"]))
    with gzip.open(RUN / seal["exact"], "rb") as fh:
        EX = json.loads(fh.read().decode())
    ks = np.arange(WARM, K)
    ph = np.array([[int(k) % 3, int(k) % 5, int(k) % 7] for k in ks])
    ck("ks", np.array_equal(P["ks"], ks) and EX["ks"] == ks.tolist())
    ck("phases_saved", np.array_equal(P["phases"], ph) and EX["phases"] == ph.tolist())

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

    # CS: forma primală pe celule k mod 105, float64, la fiecare pas
    ta2, t2, s02 = float(FTA2), float(FT2), float(FS02)
    MATCH = np.array([[matches(a, b) for b in range(105)] for a in range(105)], dtype=np.float64)
    cc = np.zeros((105, 49))
    nc = np.zeros(105)
    snaps = {}
    sample = [i for i in range(len(ks)) if i % 25 == 0]
    pind = np.empty((len(ks), 49))
    for k in range(K):
        if k >= WARM:
            i = k - WARM
            O = np.nonzero(nc)[0]
            V = ta2 + t2 * MATCH[np.ix_(O, O)] + np.diag(s02 / nc[O])
            s = ta2 + t2 * MATCH[O, k % 105]
            alpha = np.linalg.solve(V, s)
            xbar = cc[O] / nc[O, None]
            pind[i] = 6 / 49 + alpha @ (xbar - 6 / 49)
            if i in sample:
                snaps[i] = (cc.astype(np.int64).copy(), nc.astype(np.int64).copy())
        blk = Y[off[k]:off[k + 1]]
        cc[k % 105] += blk.sum(0)
        nc[k % 105] += blk.shape[0]
    dmax = float(np.abs(pind - P["p_CS"]).max())
    ck("p_primal_cells_float_vs_saved_le_1e-10", dmax <= 1e-10, dmax)

    # fracțiile salvate: sumă exactă 6, interval raportat, conversie float, bilete
    sum_ok, out01, conv_max, tick_rule_ok, tick_valid_ok = True, 0, 0.0, True, True
    for i in range(len(ks)):
        fr = [Fraction(s) for s in EX["p_hat"][i]]
        sum_ok &= (sum(fr) == 6)
        out01 += int(not all(0 < t < 1 for t in fr))
        conv_max = max(conv_max, max(abs(float(fr[j]) - P["p_CS"][i, j]) for j in range(49)))
        t = top6_rule(fr)
        tick_rule_ok &= (t == P["ticket_CS"][i].tolist())
        inn = set(t)
        tick_valid_ok &= (min(pind[i, j - 1] for j in inn) >= max(pind[i, j] for j in range(49) if j + 1 not in inn) - 1e-10)
    ck("exact_sum_6_all_steps", sum_ok)
    ck("steps_p_outside_01_matches_saved", out01 == seal["steps_p_outside_01"] == res["steps_p_outside_01"], out01)
    ck("exact_to_float_conversion", conv_max <= 1e-15, conv_max)
    ck("ticket_CS_exact_top6_rule", tick_rule_ok)
    ck("ticket_CS_valid_under_independent_p", tick_valid_ok)

    # sistemul Henderson EXACT (Gauss–Jordan propriu) la pașii din 25 în 25, din numărările pe celule
    ginv = [FS02 / FTA2] + [FS02 / FT2] * 15
    exact_ok, v_ok = True, True
    for i in sample:
        k = int(ks[i])
        ccs, ncs = snaps[i]
        NN = [[0] * 16 for _ in range(16)]
        CL = [[0] * 49 for _ in range(16)]
        for c in range(105):
            if ncs[c] == 0:
                continue
            lv = cell_levels(c)
            for l1 in lv:
                for j in range(49):
                    CL[l1][j] += int(ccs[c, j])
                for l2 in lv:
                    NN[l1][l2] += int(ncs[c])
        M = [[Fraction(NN[a][b]) + (ginv[a] if a == b else 0) for b in range(16)] for a in range(16)]
        z = [Fraction(0)] * 16
        for l in cell_levels(k % 105):
            z[l] = Fraction(1)
        v = gj_solve(M, z)
        p = []
        for j in range(49):
            val = FP0 + sum(v[l] * (CL[l][j] - FP0 * NN[l][l]) for l in range(16))
            p.append(f"{val.numerator}/{val.denominator}")
        exact_ok &= (p == EX["p_hat"][i])
        v_ok &= ([f"{x.numerator}/{x.denominator}" for x in v] == EX["v"][i])
    ck("exact_henderson_gauss_jordan_every_25", exact_ok, len(sample))
    ck("weights_v_exact_every_25", v_ok, len(sample))

    # legi, scoruri, porți, verdict
    rows = np.concatenate([np.full(off[k + 1] - off[k], k - WARM) for k in ks])
    y = np.concatenate([Y[off[k]:off[k + 1]] for k in ks])
    laws = {"CS": law(pind / 6), "B": law(piB), "R": law(piR)}
    ticks = {"CS": P["ticket_CS"], "B": tB, "R": tR}
    n = y.shape[0]
    half = n // 2
    per = {}
    for nm in ("CS", "B", "R"):
        q = laws[nm][rows]
        per[f"log_{nm}"] = (y * np.log(q) + (1 - y) * np.log(1 - q)).sum(1)
        per[f"brier_{nm}"] = ((q - y) ** 2).sum(1)
        per[f"hits_{nm}"] = np.array([int(y[r, ticks[nm][rows[r]] - 1].sum()) for r in range(n)])
    qU = np.full_like(y, 6 / 49)
    per["log_U"] = (y * np.log(qU) + (1 - y) * np.log(1 - qU)).sum(1)
    per["brier_U"] = ((qU - y) ** 2).sum(1)

    def summ(sl):
        o = {"targets": int(len(range(n)[sl]))}
        for nm in ("CS", "B", "R"):
            o[f"hits_{nm}"] = int(per[f"hits_{nm}"][sl].sum())
            o[f"excess_{nm}"] = o[f"hits_{nm}"] / o["targets"] - 36 / 49
        for nm in ("CS", "B", "R", "U"):
            o[f"log_{nm}"] = float(per[f"log_{nm}"][sl].sum())
            o[f"brier_{nm}"] = float(per[f"brier_{nm}"][sl].sum())
        return o

    T, H1, H2 = summ(slice(0, n)), summ(slice(0, half)), summ(slice(half, n))
    ck("n_targets", n == res["n_targets"] == 2495, n)
    ck("consistency_BO649_GL649_SE649_hitsB_hitsR", (T["hits_B"], T["hits_R"]) == (1847, 1821),
       [T["hits_B"], T["hits_R"]])
    mism = []
    for blk, mine in (("total", T), ("half1", H1), ("half2", H2)):
        for key, val in mine.items():
            ref = res[blk][key]
            ok = (val == ref) if key.startswith(("hits", "targets")) else abs(val - ref) <= 1e-6
            if not ok:
                mism.append([blk, key, val, ref])
    ck("scores_match_all_blocks", not mism, mism)
    g = [T["excess_CS"] >= 0.20,
         T["hits_CS"] > T["hits_B"] and T["hits_CS"] > T["hits_R"],
         T["log_CS"] - T["log_U"] > 0 and T["log_CS"] - T["log_B"] > 0,
         T["brier_CS"] < min(T["brier_U"], T["brier_B"], T["brier_R"]),
         all(h["excess_CS"] > 0 and h["hits_CS"] - h["hits_B"] > 0 for h in (H1, H2)),
         all(h["log_CS"] - h["log_B"] > 0 for h in (H1, H2))]
    verdict = "CS_PROMOVAT_EXPLORATORIU" if all(g) else "CS_NO_PROMOTION_EXPLORATORY"
    ck("gates_recomputed", [bool(x) for x in g] == [x["pass"] for x in res["gates"]], [bool(x) for x in g])
    ck("verdict_recomputed", verdict == res["verdict"], verdict)
    # statistici G descriptive (etichetă × fază), din numărările pe celule
    Gs = {}
    for Kp in PER:
        c = np.zeros((Kp, 49))
        nn = np.zeros(Kp)
        for cell in range(105):
            c[cell % Kp] += cc[cell]
            nn[cell % Kp] += nc[cell]
        e = 6.0 * nn / 49
        Gs[f"G{Kp}"] = float(2.0 * sum(c[r, j] * math.log(c[r, j] / e[r]) for r in range(Kp) for j in range(49)
                                       if c[r, j] > 0))
    gdev = max(abs(Gs[f"G{Kp}"] - res["G_label_x_phase"][f"G{Kp}"]) for Kp in PER)
    ck("G_statistics", gdev <= 1e-6, Gs)
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
