"""QL649 — verificator INDEPENDENT al backtestului unic (NumPy fp64).

NU importă engine.py, parser.py sau validare.py. Reface din fișierul sursă brut:
sigiliile (protocol, sursă, predicții, manifest), comparatorii B/R, legile marginale,
biletele, hits/log/Brier pentru QL/B/R/U pe total și jumătăți, porțile și verdictul,
validitatea variantelor, statisticile reale SCI și p-ul exact sub nul.

    .venv/bin/python -B verify_ql649.py [DIR_REZULTATE]
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SRC = (HERE.parent / "predictie_numere" / "probe_date" / "extrageri_649.jsonl").resolve()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_raw(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        nums = r.get("numbers_sorted")
        if not (isinstance(nums, list) and len(nums) == 6 and len(set(nums)) == 6
                and all(type(x) is int and 1 <= x <= 49 for x in nums)):
            continue
        rows.append((r["draw_date"], r["draw_key"], sorted(nums)))
    seen, seen2, out = set(), set(), []
    for d, k, n in rows:
        if k in seen or (d, tuple(n)) in seen2:
            continue
        seen.add(k)
        seen2.add((d, tuple(n)))
        out.append((d, k, n))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def main(argv) -> int:
    rdir = Path(argv[1]) if len(argv) > 1 else HERE / "rezultate" / "backtest_unic"
    checks = []

    def ck(name, ok, detail=None):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    start = json.loads((rdir / "START.json").read_text())
    res = json.loads((rdir / "REZULTATE.json").read_text())
    sci = json.loads((rdir / "SCI.json").read_text())
    seal = json.loads((HERE / "SIGILIU_PROTOCOL.json").read_text())
    ck("protocol_sha_sealed", sha(HERE / "PREINREGISTRARE_QL649.md") == seal["sha256"] == start["protocol_sha256"])
    src = Path(start["source"])
    if not src.exists() and (rdir.parent / src.name).exists():     # director mutat (arhivare)
        src = rdir.parent / src.name
    ck("source_sha", sha(src) == start["source_sha256"], start["source_sha256"])
    psha = sha(rdir / "PREDICTII.npz")
    ps = json.loads((rdir / "PREDICTII_SIGILIU.json").read_text())
    man = json.loads((rdir / "MANIFEST.json").read_text())
    ck("predictions_sealed_before_scoring", psha == ps["sha256"] == res["predictions_sha256"] == man["PREDICTII.npz"]
       and ps["before_scoring"] is True)
    ck("manifest_files", all(sha(rdir / f) == h for f, h in man.items()))
    ck("is_protocol_config", start["is_protocol"] is True or "synthetic" in str(src))

    draws = load_raw(src)
    nd = len(draws)
    ck("n_draws", nd == start["n_draws"], nd)
    dates = [d for d, _, _ in draws]
    step_dates = sorted(set(dates))
    sidx = np.array([step_dates.index(d) for d in dates]) if nd < 400 else np.searchsorted(np.array(step_dates), np.array(dates))
    S = len(step_dates)
    ck("n_steps", S == start["n_steps"], S)
    Y = np.zeros((nd, 49))
    for i, (_, _, n) in enumerate(draws):
        Y[i, np.array(n) - 1] = 1
    cnt = np.zeros((S, 49))
    np.add.at(cnt, sidx, Y)
    P = np.load(rdir / "PREDICTII.npz")
    ks = P["ks"]
    ck("steps_predicted", (ks == np.arange(start["warmup"], S)).all())
    # comparatori B/R refăcuți
    cum = np.vstack([np.zeros((1, 49)), np.cumsum(cnt, 0)])
    decay = 2.0 ** (-1.0 / 26.0)
    ew = np.zeros((S + 1, 49))
    for s in range(1, S + 1):
        ew[s] = ew[s - 1] * decay + cnt[s - 1]
    c = cum[ks]
    piB = (c + 1) / (c + 1).sum(-1, keepdims=True)
    piR = (ew[ks] + 0.5) / (ew[ks] + 0.5).sum(-1, keepdims=True)
    ck("comparator_B", np.allclose(piB, P["piB"], atol=1e-12, rtol=0))
    ck("comparator_R", np.allclose(piR, P["piR"], atol=1e-10, rtol=0))
    # variante
    V = P["variants"]
    okv = V.shape[1:] == (3, 6) and V.min() >= 1 and V.max() <= 49 and (np.diff(V, axis=-1) > 0).all()
    uniq = all(len({tuple(V[i, v]) for v in range(3)}) == 3 for i in range(V.shape[0]))
    ck("variants_valid", okv, list(V.shape))
    ck("variants_unique_per_step", uniq)
    pq = P["pi_QL"]
    ck("pi_QL_normalized", np.allclose(pq.sum(-1), 1, atol=1e-9) and (pq > 0).all())

    def qmap(pi):
        base = 6 / 49
        d = 6 * pi - base
        with np.errstate(divide="ignore", invalid="ignore"):
            up = np.where(d > 0, (1 - 1e-4 - base) / d, np.inf).min(-1)
            dn = np.where(d < 0, (base - 1e-4) / (-d), np.inf).min(-1)
        lam = np.minimum(0.5, np.minimum(up, dn))[:, None]
        return base + lam * d

    def tick(pi):
        return np.sort(np.argsort(-pi, axis=-1, kind="stable")[:, :6] + 1, -1)

    off = np.searchsorted(sidx, np.arange(S + 1))
    rows = np.concatenate([np.arange(off[k], off[k + 1]) for k in ks])
    kidx = np.concatenate([np.full(off[k + 1] - off[k], i) for i, k in enumerate(ks)])
    y = Y[rows]
    n = len(rows)
    ck("n_targets", n == res["n_targets"], n)
    q = {"QL": qmap(pq)[kidx], "B": qmap(piB)[kidx], "R": qmap(piR)[kidx], "U": np.full((n, 49), 6 / 49)}
    t = {"QL": V[:, 0, :][kidx], "B": tick(piB)[kidx], "R": tick(piR)[kidx]}
    hits = {k: np.take_along_axis(y, v - 1, 1).sum(-1) for k, v in t.items()}
    logs = {k: (y * np.log(v) + (1 - y) * np.log(1 - v)).sum(-1) for k, v in q.items()}
    bri = {k: ((v - y) ** 2).sum(-1) for k, v in q.items()}
    h = n // 2
    parts = {"total": slice(0, n), "half1": slice(0, h), "half2": slice(h, n)}
    for pn, sl in parts.items():
        R = res[pn]
        for k in ("QL", "B", "R"):
            ck(f"{pn}_hits_{k}", int(hits[k][sl].sum()) == R[f"hits_{k}"], [int(hits[k][sl].sum()), R[f"hits_{k}"]])
        for k in ("QL", "B", "R", "U"):
            ck(f"{pn}_log_{k}", abs(float(logs[k][sl].sum()) - R[f"log_{k}"]) < 1e-6)
            ck(f"{pn}_brier_{k}", abs(float(bri[k][sl].sum()) - R[f"brier_{k}"]) < 1e-6)
        m = sl.stop - sl.start
        ck(f"{pn}_excess", abs((hits["QL"][sl].sum() / m - 36 / 49) - R["excess_QL"]) < 1e-12)
    if "synthetic" not in str(src):
        ck("U_brier_reference", abs(float(bri["U"].sum()) - n * 6 * 43 / 49) < 1e-6)
    # porți
    T, H1, H2 = res["total"], res["half1"], res["half2"]
    g = [T["excess_QL"] >= 0.20, T["hits_QL"] > T["hits_B"] and T["hits_QL"] > T["hits_R"],
         T["log_QL"] - T["log_U"] > 0 and T["log_QL"] - T["log_B"] > 0,
         T["brier_QL"] < min(T["brier_U"], T["brier_B"], T["brier_R"]),
         all(x["excess_QL"] > 0 and x["hits_QL"] - x["hits_B"] > 0 for x in (H1, H2)),
         all(x["log_QL"] - x["log_B"] > 0 for x in (H1, H2))]
    ck("gates_recomputed", [gg["pass"] for gg in res["gates"]] == g, g)
    verdict = "QL_PROMOVAT_EXPLORATORIU" if all(g) else "QL_NO_PROMOTION_EXPLORATORY"
    ck("verdict", verdict == res["verdict"], verdict)
    # reuniune 3 variante
    uni = np.zeros_like(y)
    for v in range(3):
        np.put_along_axis(uni, V[kidx, v, :] - 1, 1.0, 1)
    ck("union3_hits", int((uni * y).sum()) == T["hits_union3_QL"])
    # p exact
    pmf = np.array([math.comb(6, i) * math.comb(43, 6 - i) / math.comb(49, 6) for i in range(7)])
    dist = np.array([1.0])
    for _ in range(n):
        dist = np.convolve(dist, pmf)
    ck("p_exact", abs(float(dist[int(hits["QL"].sum()):].sum()) - res["p_exact_hits_QL_ge"]) < 1e-9)
    # SCI: statistici reale refăcute
    e1 = 6 * nd / 49
    chi_f = float((((Y.sum(0)) - e1) ** 2 / e1).sum())
    C = Y.T @ Y
    iu = np.triu_indices(49, 1)
    e2 = nd * 30 / 2352
    chi_p = float(((C[iu] - e2) ** 2 / e2).sum())
    sizes = np.diff(off)
    ov = float(((cnt[:-1] * cnt[1:]).sum(-1) / (sizes[:-1] * sizes[1:])).mean())
    sr = sci["stats_real"]
    ck("sci_chi_freq", abs(chi_f - sr["chi_freq"]) < 1e-6 * max(1, chi_f), [chi_f, sr["chi_freq"]])
    ck("sci_chi_pair", abs(chi_p - sr["chi_pair"]) < 1e-6 * max(1, chi_p), [chi_p, sr["chi_pair"]])
    ck("sci_overlap", abs(ov - sr["overlap"]) < 1e-9, [ov, sr["overlap"]])
    z = {k: (sr[k] - sci["null_mean"][k]) / sci["null_std"][k] for k in sr}
    ck("sci_index", abs(sum(z.values()) / 2 - sci["SCI"]) < 1e-9)
    ck("positive_claims_false", res["positive_claims_allowed"] is False)
    out = {"status": "PASS" if all(c["pass"] for c in checks) else "FAIL", "n_checks": len(checks),
           "n_fail": sum(not c["pass"] for c in checks), "dir": str(rdir), "imports_engine": False,
           "checks": checks}
    (rdir / "VERIFICARE_INDEPENDENTA.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "checks"}, indent=2))
    for cc in checks:
        if not cc["pass"]:
            print("FAIL", cc)
    return 0 if out["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
