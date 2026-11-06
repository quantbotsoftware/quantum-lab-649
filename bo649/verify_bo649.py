"""Verificator independent BO649 (PREINREGISTRARE_BO649.md §7).

NU importă bo649.py, engine.py, parser.py sau validare.py. Reparsează JSONL după QL649 §1,
recalculează BOCPD într-o formulare diferită (log-domeniu, statistici din sume de prefix pe
extrageri, fără tablouri purtate), comparatorii (R prin recursie), scorurile, porțile și
verdictul, apoi compară cu artefactele sigilate din rezultate/backtest_unic/.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUN = HERE / "rezultate" / "backtest_unic"
SRC = (HERE.parent.parent / "predictie_numere" / "probe_date" / "extrageri_649.jsonl").resolve()
H, M0, WARM, HL = 1.0 / 250.0, 12.0, 100, 26.0


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


def bocpd_prefix(Y: np.ndarray, off: np.ndarray):
    """Log-domeniu; statistici pentru lungimea r la pasul s din sumele de prefix pe extrageri."""
    N = 49
    a0, b0 = M0 * 6 / N, M0 * 43 / N
    D = np.vstack((np.zeros((1, N)), np.cumsum(Y, 0)))
    K = off.shape[0] - 1
    Q = np.empty((K, N))
    Er = np.empty(K)
    logpost = None
    for s in range(K):
        if s == 0:
            logprior = np.array([0.0])
        else:
            lw = logpost  # indexat după r = 0..s-1 la pasul s-1
            logprior = np.empty(s + 1)
            logprior[0] = math.log(H)
            logprior[1:] = math.log(1 - H) + lw
        r = np.arange(s + 1)
        start = off[s - r]  # prima extragere a regimului
        n = (off[s] - start).astype(np.float64)
        C = D[off[s]][None, :] - D[start]
        m = logprior.max()
        w = np.exp(logprior - m)
        w /= w.sum()
        Q[s] = (w[:, None] * (a0 + C) / (M0 + n)[:, None]).sum(0)
        Er[s] = (w * r).sum()
        ll = np.zeros(s + 1)
        for i in range(off[s], off[s + 1]):
            nn = n + (i - off[s])
            CC = C + (D[i] - D[off[s]])[None, :]
            y = Y[i]
            ll += np.log(np.where(y[None, :] > 0, a0 + CC, b0 + nn[:, None] - CC)).sum(1) - N * np.log(M0 + nn)
        lp = logprior + ll
        mm = lp.max()
        logpost = lp - (mm + np.log(np.exp(lp - mm).sum()))
    return Q, Er


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


def tick(score: np.ndarray) -> np.ndarray:
    out = np.empty((score.shape[0], 6), dtype=np.int64)
    for t in range(score.shape[0]):
        idx = sorted(range(49), key=lambda j: (-score[t, j], j))[:6]
        out[t] = sorted(j + 1 for j in idx)
    return out


def main() -> int:
    checks = []

    def chk(name, ok, val=None):
        checks.append({"check": name, "pass": bool(ok), "value": val})

    start = json.loads((RUN / "START.json").read_text())
    res = json.loads((RUN / "REZULTATE.json").read_text())
    seal = json.loads((HERE / "SIGILIU_PROTOCOL_BO649.json").read_text())
    psig = json.loads((RUN / "PREDICTII_SIGILIU.json").read_text())
    chk("protocol_sha_file_eq_seal", sha(HERE / "PREINREGISTRARE_BO649.md") == seal["sha256"])
    chk("start_protocol_sha_eq_seal", start["protocol_sha256"] == seal["sha256"])
    chk("seal_before_start", seal["sealed_at_utc"] < start["utc"], [seal["sealed_at_utc"], start["utc"]])
    qual = json.loads((HERE / "rezultate" / "CALIFICARE.json").read_text())
    chk("qualified_before_start", qual["status"] == "BO_QUALIFIED" and qual["utc"] < start["utc"])
    chk("qualification_sha_eq_start", sha(HERE / "rezultate" / "CALIFICARE.json") == start["qualification_sha256"])
    chk("predictions_sha_eq_seal", sha(RUN / "PREDICTII.npz") == psig["sha256"] == res["predictions_sha256"])
    chk("source_sha", sha(SRC) == start["source_sha256"], start["source_sha256"])
    Y, off = parse()
    K = off.shape[0] - 1
    chk("n_draws", Y.shape[0] == start["n_draws"] == 2595, Y.shape[0])
    chk("n_steps", K == start["n_steps"] == 2527, K)
    chk("config", start["config"]["h"] == H and start["config"]["m0"] == M0 and start["config"]["warmup"] == WARM)

    P = np.load(RUN / "PREDICTII.npz")
    Q, Er = bocpd_prefix(Y, off)
    ks = np.arange(WARM, K)
    chk("ks", np.array_equal(P["ks"], ks))
    dq = float(np.abs(Q[ks] - P["q_BO"]).max())
    chk("q_BO_max_abs_diff_lt_1e-9", dq < 1e-9, dq)
    chk("sum_q_eq_6", float(np.abs(Q[ks].sum(1) - 6).max()) < 1e-9)
    chk("Er_max_abs_diff_lt_1e-6", float(np.abs(Er[ks] - P["Er"]).max()) < 1e-6)

    # comparatori: B din prefix, R prin recursie
    S = np.stack([Y[off[s]:off[s + 1]].sum(0) for s in range(K)])
    c = np.cumsum(np.vstack((np.zeros((1, 49)), S)), 0)
    ew = np.zeros((K + 1, 49))
    g = 2.0 ** (-1.0 / HL)
    for k in range(1, K + 1):
        ew[k] = ew[k - 1] * g + S[k - 1]
    piB = (c[ks] + 1) / (c[ks] + 1).sum(1, keepdims=True)
    piR = (ew[ks] + 0.5) / (ew[ks] + 0.5).sum(1, keepdims=True)
    chk("piB_diff", float(np.abs(piB - P["piB"]).max()) < 1e-12)
    chk("piR_diff", float(np.abs(piR - P["piR"]).max()) < 1e-9)
    tBO, tB, tR = tick(Q[ks]), tick(piB), tick(piR)
    chk("ticket_BO_exact", np.array_equal(tBO, P["ticket_BO"]))
    chk("ticket_B_exact", np.array_equal(tB, P["ticket_B"]))
    chk("ticket_R_exact", np.array_equal(tR, P["ticket_R"]))

    # ținte și scoruri
    rows, ys = [], []
    for k in ks:
        for i in range(off[k], off[k + 1]):
            rows.append(k - WARM)
            ys.append(Y[i])
    rows, y = np.array(rows), np.array(ys)
    n = y.shape[0]
    chk("n_targets", n == res["n_targets"] == 2495, n)
    laws = {"BO": law(Q[ks] / 6), "B": law(piB), "R": law(piR)}
    tk = {"BO": tBO, "B": tB, "R": tR}
    sc = {}
    for m in ("BO", "B", "R"):
        qq = laws[m][rows]
        sc[f"log_{m}"] = np.array([sum(math.log(qq[t, j]) if y[t, j] else math.log(1 - qq[t, j]) for j in range(49))
                                   for t in range(n)])
        sc[f"brier_{m}"] = ((qq - y) ** 2).sum(1)
        sc[f"hits_{m}"] = np.array([int(y[t, tk[m][rows[t]] - 1].sum()) for t in range(n)])
    sc["log_U"] = y.sum(1) * math.log(6 / 49) + (49 - y.sum(1)) * math.log(43 / 49)
    sc["brier_U"] = ((6 / 49 - y) ** 2).sum(1)
    chk("per_target_hits_BO", sc["hits_BO"].tolist() == res["per_target"]["hits_BO"])
    half = n // 2
    parts = {"total": slice(0, n), "half1": slice(0, half), "half2": slice(half, n)}
    agg = {}
    for pname, sl in parts.items():
        a = {}
        for m in ("BO", "B", "R"):
            a[f"hits_{m}"] = int(sc[f"hits_{m}"][sl].sum())
            a[f"excess_{m}"] = a[f"hits_{m}"] / (sl.stop - sl.start) - 36 / 49
        for m in ("BO", "B", "R", "U"):
            a[f"log_{m}"] = float(sc[f"log_{m}"][sl].sum())
            a[f"brier_{m}"] = float(sc[f"brier_{m}"][sl].sum())
        agg[pname] = a
        for kk, v in a.items():
            ok = (v == res[pname][kk]) if kk.startswith("hits") else abs(v - res[pname][kk]) < 1e-6
            chk(f"{pname}.{kk}", ok, [v, res[pname][kk]])
    t, h1, h2 = agg["total"], agg["half1"], agg["half2"]
    gp = [t["excess_BO"] >= 0.20,
          t["hits_BO"] > t["hits_B"] and t["hits_BO"] > t["hits_R"],
          t["log_BO"] > t["log_U"] and t["log_BO"] > t["log_B"],
          t["brier_BO"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
          all(h["excess_BO"] > 0 and h["hits_BO"] > h["hits_B"] for h in (h1, h2)),
          all(h["log_BO"] > h["log_B"] for h in (h1, h2))]
    for i, ok in enumerate(gp):
        chk(f"gate_{i + 1}_eq", ok == res["gates"][i]["pass"], ok)
    verdict = "BO_PROMOVAT_EXPLORATORIU" if all(gp) else "BO_NO_PROMOTION_EXPLORATORY"
    chk("verdict", verdict == res["verdict"] and sum(gp) == res["gates_passed"], [verdict, sum(gp)])
    chk("positive_claims_allowed_false", res.get("positive_claims_allowed") is False)
    banned = [m for m in ("bo649", "parser", "engine", "validare", "torch") if m in sys.modules]
    chk("no_forbidden_imports", not banned, banned)
    nf = sum(not c_["pass"] for c_ in checks)
    out = {"status": "PASS" if nf == 0 else "FAIL", "n_checks": len(checks), "n_fail": nf,
           "imports_bo649_or_ql": bool(banned), "verdict_recomputed": verdict, "checks": checks}
    (RUN / "VERIFICARE_INDEPENDENTA.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "checks"}, indent=2))
    return 0 if nf == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
