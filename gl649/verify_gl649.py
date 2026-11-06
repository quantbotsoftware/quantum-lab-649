"""Verificator independent GL649 (PREINREGISTRARE_GL649.md §7).

NU importă gl649.py, wu649.py, bo649.py, engine.py, parser.py sau validare.py. Reparsează JSONL
după QL649 §1, reconstruiește structura glifelor prin aritmetică (divmod, nu șiruri), recalculează
p̂ prin rezolvarea DIRECTĂ 49×49 (fără Woodbury) în float64 la fiecare pas și în Q (Gauss–Jordan
propriu, Fraction) la pașii din 25 în 25, comparatorii (R prin recursie), legile, scorurile,
porțile și verdictul, apoi compară cu artefactele sigilate din rezultate/backtest_unic/.
"""
from __future__ import annotations

import datetime
import gzip
import hashlib
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUN = HERE / "rezultate" / "backtest_unic"
SRC = (HERE.parent.parent / "predictie_numere" / "probe_date" / "extrageri_649.jsonl").resolve()
WARM, HL = 100, 26.0
FP0 = Fraction(6, 49)
FSG2, FSE2, FS02 = FP0 * FP0 / 100, FP0 * FP0 / 400, FP0 * (1 - FP0) * Fraction(49, 48)
FORBIDDEN = ("gl649", "wu649", "bo649", "engine", "parser", "validare")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse() -> tuple[np.ndarray, np.ndarray]:
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


def glyphs() -> np.ndarray:
    G = np.zeros((49, 10), dtype=np.int64)
    for j in range(1, 50):
        t, u = divmod(j, 10)
        G[j - 1, u] += 1
        if t:
            G[j - 1, t] += 1
    return G


G = glyphs()


def pkp_float() -> np.ndarray:
    P = np.eye(49) - 1.0 / 49
    K = float(FSG2) * (G @ G.T) + float(FSE2) * np.eye(49)
    return P @ K @ P


def pkp_frac() -> list[list[Fraction]]:
    Gt = G.tolist()
    K = [[FSG2 * sum(Gt[i][d] * Gt[j][d] for d in range(10)) + (FSE2 if i == j else 0) for j in range(49)]
         for i in range(49)]
    rs = [sum(r) for r in K]
    tot = sum(rs)
    return [[K[i][j] - rs[i] / 49 - rs[j] / 49 + tot / 2401 for j in range(49)] for i in range(49)]


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


def exact_direct(args) -> tuple[int, list[str]]:
    idx, counts, n = args
    PKPf = pkp_frac()
    nu = FS02 / n
    v = [Fraction(int(c), n) - FP0 for c in counts]
    A = [[PKPf[i][j] + nu * ((1 if i == j else 0) - Fraction(1, 49)) + FSE2 for j in range(49)] for i in range(49)]
    w = gj_solve(A, v)
    p = [Fraction(int(counts[j]), n) - nu * w[j] for j in range(49)]
    return idx, [f"{t.numerator}/{t.denominator}" for t in p]


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
    ck("source_sha256", sha(SRC) == start["source_sha256"], sha(SRC))
    proto_seal = json.loads((HERE / "SIGILIU_PROTOCOL_GL649.json").read_text())
    ck("protocol_sha256", sha(HERE / "PREINREGISTRARE_GL649.md") == proto_seal["sha256"] == start["protocol_sha256"])
    ck("qualification_sha256", sha(HERE / "rezultate" / "CALIFICARE.json") == start["qualification_sha256"])
    ck("qualified", json.loads((HERE / "rezultate" / "CALIFICARE.json").read_text())["status"] == "GL_QUALIFIED")
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
    ck("ks", np.array_equal(P["ks"], ks) and EX["ks"] == ks.tolist())

    # numărări pe prefix (pe extrageri) și comparatori
    D = np.vstack((np.zeros((1, 49)), np.cumsum(Y, 0)))
    counts = D[off[ks]].astype(np.int64)
    nds = off[ks].astype(np.int64)
    ck("n_draws_saved", np.array_equal(P["n_draws"], nds))
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

    # GL: rezolvare directă float64 la fiecare pas
    PKP = pkp_float()
    Pm = np.eye(49) - 1.0 / 49
    J = np.ones((49, 49))
    se2, s02 = float(FSE2), float(FS02)
    pind = np.empty((len(ks), 49))
    for i, k in enumerate(ks):
        n = nds[i]
        x = counts[i] / n
        v = x - 6 / 49
        nu = s02 / n
        w = np.linalg.solve(PKP + nu * Pm + se2 * J, v)
        pind[i] = x - nu * w
    dmax = float(np.abs(pind - P["p_GL"]).max())
    ck("p_direct_float_vs_saved_le_1e-12", dmax <= 1e-12, dmax)

    # fracțiile salvate: sumă exactă 6, conversie float, bilete
    sum_ok, conv_max, tick_rule_ok, tick_valid_ok = True, 0.0, True, True
    for i in range(len(ks)):
        fr = [Fraction(s) for s in EX["p_hat"][i]]
        sum_ok &= (sum(fr) == 6)
        conv_max = max(conv_max, max(abs(float(fr[j]) - P["p_GL"][i, j]) for j in range(49)))
        t = top6_rule(fr)
        tick_rule_ok &= (t == P["ticket_GL"][i].tolist())
        inn = set(t)
        tick_valid_ok &= (min(pind[i, j - 1] for j in inn) >= max(pind[i, j] for j in range(49) if j + 1 not in inn) - 1e-12)
    ck("exact_sum_6_all_steps", sum_ok)
    ck("exact_to_float_conversion", conv_max <= 1e-15, conv_max)
    ck("ticket_GL_exact_top6_rule", tick_rule_ok)
    ck("ticket_GL_valid_under_independent_p", tick_valid_ok)

    # rezolvare directă EXACTĂ (Gauss–Jordan, Fraction) la pașii din 25 în 25
    sample = [i for i in range(len(ks)) if i % 25 == 0]
    jobs = [(i, counts[i].tolist(), int(nds[i])) for i in sample]
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1)) as ex:
        out = dict(ex.map(exact_direct, jobs))
    exact_ok = all(out[i] == EX["p_hat"][i] for i in sample)
    ck("exact_direct_gauss_jordan_every_25", exact_ok, len(sample))

    # legi, scoruri, porți, verdict
    rows = np.concatenate([np.full(off[k + 1] - off[k], k - WARM) for k in ks])
    y = np.concatenate([Y[off[k]:off[k + 1]] for k in ks])
    laws = {"GL": law(pind / 6), "B": law(piB), "R": law(piR)}
    ticks = {"GL": P["ticket_GL"], "B": tB, "R": tR}
    tot = {}
    n = y.shape[0]
    half = n // 2
    per = {}
    for nm in ("GL", "B", "R"):
        q = laws[nm][rows]
        per[f"log_{nm}"] = (y * np.log(q) + (1 - y) * np.log(1 - q)).sum(1)
        per[f"brier_{nm}"] = ((q - y) ** 2).sum(1)
        per[f"hits_{nm}"] = np.array([int(y[r, ticks[nm][rows[r]] - 1].sum()) for r in range(n)])
    qU = np.full_like(y, 6 / 49)
    per["log_U"] = (y * np.log(qU) + (1 - y) * np.log(1 - qU)).sum(1)
    per["brier_U"] = ((qU - y) ** 2).sum(1)

    def summ(sl):
        o = {"targets": int(len(range(n)[sl]))}
        for nm in ("GL", "B", "R"):
            o[f"hits_{nm}"] = int(per[f"hits_{nm}"][sl].sum())
            o[f"excess_{nm}"] = o[f"hits_{nm}"] / o["targets"] - 36 / 49
        for nm in ("GL", "B", "R", "U"):
            o[f"log_{nm}"] = float(per[f"log_{nm}"][sl].sum())
            o[f"brier_{nm}"] = float(per[f"brier_{nm}"][sl].sum())
        return o

    T, H1, H2 = summ(slice(0, n)), summ(slice(0, half)), summ(slice(half, n))
    ck("n_targets", n == res["n_targets"] == 2495, n)
    ck("consistency_BO649_hitsB_hitsR", (T["hits_B"], T["hits_R"]) == (1847, 1821), [T["hits_B"], T["hits_R"]])
    for blk, mine in (("total", T), ("half1", H1), ("half2", H2)):
        for key, val in mine.items():
            ref = res[blk][key]
            ok = (val == ref) if key.startswith(("hits", "targets")) else abs(val - ref) <= 1e-6
            if not ok:
                ck(f"{blk}.{key}", False, [val, ref])
    ck("scores_match_all_blocks", all(c["pass"] for c in checks if "." in c["check"]) or
       not any("." in c["check"] for c in checks))
    g = [T["excess_GL"] >= 0.20,
         T["hits_GL"] > T["hits_B"] and T["hits_GL"] > T["hits_R"],
         T["log_GL"] - T["log_U"] > 0 and T["log_GL"] - T["log_B"] > 0,
         T["brier_GL"] < min(T["brier_U"], T["brier_B"], T["brier_R"]),
         all(h["excess_GL"] > 0 and h["hits_GL"] - h["hits_B"] > 0 for h in (H1, H2)),
         all(h["log_GL"] - h["log_B"] > 0 for h in (H1, H2))]
    verdict = "GL_PROMOVAT_EXPLORATORIU" if all(g) else "GL_NO_PROMOTION_EXPLORATORY"
    ck("gates_recomputed", [bool(x) for x in g] == [x["pass"] for x in res["gates"]], [bool(x) for x in g])
    ck("verdict_recomputed", verdict == res["verdict"], verdict)
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
