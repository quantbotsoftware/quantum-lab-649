"""QL649 — validare backend (PREINREGISTRARE_QL649.md §4–§5).

- Indicele de Coerență Structurală (SCI) față de Multiversul Nul (8192 istorii uniforme pe GPU).
- Backtest walk-forward cauzal UNIC („Mașina Timpului”): predicțiile tuturor pașilor sunt
  scrise și hash-uite ÎNAINTE de scor; scorul se calculează din fișierul scris.
- Comparatori U/B/R, cele 6 porți, verdict, statistici descriptive (reuniune 3 variante,
  distribuția potrivirilor vs hipergeometric, p exact sub nul).

Rulare reală (o singură dată, protocolul interzice repetarea pentru tuning):
    .venv/bin/python -B validare.py --real
Mod sintetic (teste/inginerie, NU atinge istoria reală):
    .venv/bin/python -B validare.py --synthetic OUT_DIR
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import torch

import engine as E
from parser import DEFAULT_SOURCE, Dataset, build_dataset, resolve_device

ROOT = Path(__file__).resolve().parent
N, K6 = 49, 6
F64 = torch.float64
WARMUP = 100
LAM0, QEPS = 0.5, 1e-4
GAP_BINS = 21                   # 1..20, 21+
M_NULL = 8192
M_PIPE_NULL = 4                 # AMENDAMENT_01: 64 → 4 (descriptiv, cost de calcul)
SEED_NULL = 649


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Statistici SCI (vectorizate pe universuri)
# ---------------------------------------------------------------------------
def step_presence(onehot: torch.Tensor, step_index: torch.Tensor, n_steps: int) -> torch.Tensor:
    """onehot [M,Nd,49] → numărări pe pas [M,S,49] (0..2)."""
    M = onehot.shape[0]
    out = torch.zeros(M, n_steps, N, device=onehot.device, dtype=onehot.dtype)
    out.index_add_(1, step_index, onehot)
    return out


def sci_raw(onehot: torch.Tensor, step_index: torch.Tensor, step_sizes: torch.Tensor, n_steps: int) -> dict:
    """Statisticile brute pe M universuri: χ² frecvențe, χ² perechi, histograme goluri, suprapunere serială."""
    M, Nd, _ = onehot.shape
    oh = onehot.to(torch.float32)
    c = oh.sum(1).to(F64)
    e1 = 6.0 * Nd / N
    chi_f = ((c - e1) ** 2 / e1).sum(-1)
    C = torch.bmm(oh.transpose(1, 2), oh).to(F64)
    iu = torch.triu_indices(N, N, 1, device=oh.device)
    pc = C[:, iu[0], iu[1]]
    e2 = Nd * 30.0 / 2352.0
    chi_p = ((pc - e2) ** 2 / e2).sum(-1)
    pres = step_presence(oh, step_index, n_steps)                     # [M,S,49]
    s_ar = torch.arange(n_steps, device=oh.device)[None, :, None].expand(M, -1, N)
    marks = torch.where(pres > 0, s_ar, torch.full_like(s_ar, -1))
    last = torch.cummax(marks, 1).values
    prev = torch.cat([torch.full_like(last[:, :1], -1), last[:, :-1]], 1)
    valid = (pres > 0) & (prev >= 0)
    gap = (s_ar - prev).clamp(min=1, max=GAP_BINS) - 1                # bin 0..20
    num_ar = torch.arange(N, device=oh.device)[None, None, :].expand(M, n_steps, -1)
    uni_ar = torch.arange(M, device=oh.device)[:, None, None].expand(-1, n_steps, N)
    flat = (uni_ar * N + num_ar) * GAP_BINS + gap
    hist = torch.zeros(M * N * GAP_BINS, device=oh.device, dtype=F64)
    hist.index_add_(0, flat[valid], torch.ones(int(valid.sum()), device=oh.device, dtype=F64))
    hist = hist.view(M, N, GAP_BINS)
    sz = step_sizes.to(F64)
    v = pres.to(F64)
    ov = (v[:, :-1] * v[:, 1:]).sum(-1) / (sz[:-1] * sz[1:])[None]
    overlap = ov.mean(-1)
    return {"chi_freq": chi_f, "chi_pair": chi_p, "gap_hist": hist, "overlap": overlap}


def null_onehot(M: int, n_draws: int, gen: torch.Generator, device) -> torch.Tensor:
    keys = torch.rand(M, n_draws, N, generator=gen, device=device)
    idx = keys.topk(K6, dim=-1).indices
    oh = torch.zeros(M, n_draws, N, device=device, dtype=torch.float32)
    oh.scatter_(2, idx, 1.0)
    return oh


def null_draws(n_draws: int, gen: torch.Generator, device) -> torch.Tensor:
    keys = torch.rand(n_draws, N, generator=gen, device=device)
    return torch.sort(keys.topk(K6, dim=-1).indices + 1, -1).values


def compute_sci(ds: Dataset, M: int = M_NULL, chunk: int = 256, seed: int = SEED_NULL) -> dict:
    dev = ds.device
    sidx = ds.step_index.to(dev)
    sizes = (ds.step_offsets[1:] - ds.step_offsets[:-1]).to(dev)
    real = sci_raw(ds.onehot.to(dev)[None], sidx, sizes, ds.n_steps)
    gen = torch.Generator(device=dev).manual_seed(seed)
    parts = {"chi_freq": [], "chi_pair": [], "gap_hist": [], "overlap": []}
    for s0 in range(0, M, chunk):
        m = min(chunk, M - s0)
        r = sci_raw(null_onehot(m, ds.n_draws, gen, dev), sidx, sizes, ds.n_steps)
        for k in parts:
            parts[k].append(r[k])
    nul = {k: torch.cat(v, 0) for k, v in parts.items()}
    ebar = nul["gap_hist"].mean(0).clamp(min=1e-12)                   # [49,21] așteptat per număr
    def gchi(h):
        return ((h - ebar) ** 2 / ebar).sum((-1, -2))
    stats_real = {"chi_freq": float(real["chi_freq"][0]), "chi_pair": float(real["chi_pair"][0]),
                  "chi_gap": float(gchi(real["gap_hist"])[0]), "overlap": float(real["overlap"][0])}
    stats_null = {"chi_freq": nul["chi_freq"], "chi_pair": nul["chi_pair"], "chi_gap": gchi(nul["gap_hist"]),
                  "overlap": nul["overlap"]}
    z, mu, sd = {}, {}, {}
    zn = torch.zeros(M, dtype=F64, device=dev)
    for k, v in stats_null.items():
        mu[k], sd[k] = float(v.mean()), float(v.std())
        z[k] = (stats_real[k] - mu[k]) / sd[k]
        zn = zn + (v - mu[k]) / sd[k]
    sci = sum(z.values()) / 2.0
    sci_null = zn / 2.0
    p = (1 + int((sci_null >= sci).sum())) / (M + 1)
    q = torch.quantile(sci_null.float(), torch.tensor([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99], device=dev))
    return {"M": M, "seed": seed, "stats_real": stats_real, "null_mean": mu, "null_std": sd, "z": z,
            "SCI": sci, "p_empirical": p, "sci_null_quantiles": [float(x) for x in q],
            "sci_null_sample": [float(x) for x in sci_null[:2048].cpu()],
            "freq_real": [int(x) for x in ds.onehot.sum(0).cpu()],
            "gap_hist_real": real["gap_hist"][0].sum(0).cpu().tolist(), "gap_hist_null_mean": ebar.sum(0).cpu().tolist()}


# ---------------------------------------------------------------------------
# Legi marginale, comparatori, scoruri
# ---------------------------------------------------------------------------
def marginal_q(pi: np.ndarray) -> np.ndarray:
    """q_j = 6/49 + λ(6π_j − 6/49), λ = min(0.5, λ_max) cu q ∈ [1e-4, 1−1e-4]."""
    base = 6.0 / N
    d = 6.0 * pi - base
    with np.errstate(divide="ignore", invalid="ignore"):
        up = np.where(d > 0, (1 - QEPS - base) / d, np.inf)
        dn = np.where(d < 0, (base - QEPS) / (-d), np.inf)
    lam = np.minimum(LAM0, np.minimum(up.min(-1), dn.min(-1)))[..., None]
    return base + lam * d


def top6(pi: np.ndarray) -> np.ndarray:
    order = np.argsort(-pi, axis=-1, kind="stable")
    return np.sort(order[..., :K6] + 1, -1)


def comparators(ds: Dataset, ks: np.ndarray, cfg: E.Config = E.PROTOCOL) -> dict:
    pre = E.Prefix(ds, cfg, ds.device)
    st = pre.state(torch.as_tensor(ks, device=ds.device))
    c = st["c"].cpu().numpy()
    ew = st["ew"].cpu().numpy()
    piB = (c + 1.0) / (c + 1.0).sum(-1, keepdims=True)
    piR = (ew + 0.5) / (ew + 0.5).sum(-1, keepdims=True)
    return {"piB": piB, "piR": piR}


def score_block(q: np.ndarray, ticket: np.ndarray | None, y: np.ndarray) -> dict:
    """q [T,49], ticket [T,6] (1..49) sau None, y [T,49] 0/1."""
    log = (y * np.log(q) + (1 - y) * np.log(1 - q)).sum(-1)
    brier = ((q - y) ** 2).sum(-1)
    out = {"log": log, "brier": brier}
    if ticket is not None:
        out["hits"] = np.take_along_axis(y, ticket - 1, axis=1).sum(-1)
    return out


def hyper_pmf() -> np.ndarray:
    return np.array([math.comb(6, i) * math.comb(43, 6 - i) / math.comb(49, 6) for i in range(7)])


def exact_tail(total_hits: int, n: int, m_tickets: int = 1) -> float:
    """P(H ≥ total_hits) pentru suma a n variabile i.i.d. (hipergeometrice; m bilete fixe → convoluție)."""
    pmf = hyper_pmf()
    base = pmf.copy()
    for _ in range(m_tickets - 1):
        base = np.convolve(base, pmf)
    dist = np.array([1.0])
    for _ in range(n):
        dist = np.convolve(dist, base)
    return float(dist[total_hits:].sum())


def gates(res: dict) -> list[dict]:
    t, h1, h2 = res["total"], res["half1"], res["half2"]
    g = [
        ("1", "ExcesQL/U >= 0.20", t["excess_QL"] >= 0.20, t["excess_QL"]),
        ("2", "hitsQL > hitsB și hitsQL > hitsR", t["hits_QL"] > t["hits_B"] and t["hits_QL"] > t["hits_R"],
         [t["hits_QL"], t["hits_B"], t["hits_R"]]),
        ("3", "logQL−logU > 0 și logQL−logB > 0", t["log_QL"] - t["log_U"] > 0 and t["log_QL"] - t["log_B"] > 0,
         [t["log_QL"] - t["log_U"], t["log_QL"] - t["log_B"]]),
        ("4", "BrierQL < BrierU, BrierB, BrierR", t["brier_QL"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
         [t["brier_QL"], t["brier_U"], t["brier_B"], t["brier_R"]]),
        ("5", "ambele jumătăți: exces > 0 și hitsQL−hitsB > 0",
         all(h["excess_QL"] > 0 and h["hits_QL"] - h["hits_B"] > 0 for h in (h1, h2)),
         [[h["excess_QL"], h["hits_QL"] - h["hits_B"]] for h in (h1, h2)]),
        ("6", "ambele jumătăți: logQL−logB > 0", all(h["log_QL"] - h["log_B"] > 0 for h in (h1, h2)),
         [h["log_QL"] - h["log_B"] for h in (h1, h2)]),
    ]
    return [{"gate": a, "rule": b, "pass": bool(c), "value": d} for a, b, c, d in g]


def summarize(sl: slice, S: dict) -> dict:
    n = int(S["y"][sl].shape[0])
    o = {"targets": n}
    for name in ("QL", "B", "R"):
        o[f"hits_{name}"] = int(S[f"hits_{name}"][sl].sum())
    o["excess_QL"] = o["hits_QL"] / n - 36.0 / 49.0 if n else 0.0
    o["excess_B"] = o["hits_B"] / n - 36.0 / 49.0 if n else 0.0
    o["excess_R"] = o["hits_R"] / n - 36.0 / 49.0 if n else 0.0
    for name in ("QL", "B", "R", "U"):
        o[f"log_{name}"] = float(S[f"log_{name}"][sl].sum())
        o[f"brier_{name}"] = float(S[f"brier_{name}"][sl].sum())
    o["hits_union3_QL"] = int(S["hits_union"][sl].sum())
    o["expected_union3_U"] = n * 108.0 / 49.0
    return o


# ---------------------------------------------------------------------------
# Predicții (scrise înainte de scor) și scor
# ---------------------------------------------------------------------------
def predict_all(ds: Dataset, cfg: E.Config, warmup: int, chunk: int = 64, log=print) -> dict:
    dev = ds.device
    ks = np.arange(warmup, ds.n_steps, dtype=np.int64)
    kt = torch.as_tensor(ks, device=dev)
    pre = E.Prefix(ds, cfg, dev)
    timings: dict = {}
    t0 = time.perf_counter()
    sc = E.score_steps(pre, kt, cfg, chunk=chunk, timings=timings)
    log(f"[QL649] O1–O5 pe {len(ks)} pași: {time.perf_counter() - t0:.1f}s {json.dumps({k: round(v, 1) for k, v in timings.items()})}")
    t1 = time.perf_counter()
    vv = E.variants_steps(sc["pi"], sc["A"], kt, cfg)
    if dev.type == "cuda":
        torch.cuda.synchronize()
    timings["O6_mcmc_qubo"] = time.perf_counter() - t1
    log(f"[QL649] O6 MCMC/QUBO: {timings['O6_mcmc_qubo']:.1f}s")
    comp = comparators(ds, ks, cfg)
    return {"ks": ks, "pi_QL": sc["pi"].cpu().numpy(), "variants": vv["variants"].cpu().numpy(),
            "energies": vv["energies"].cpu().numpy(), "gamma_q": sc["gamma_q"].cpu().numpy(),
            "ep_converged": sc["ep_converged"].cpu().numpy(), "anchors": sc["anchors"].cpu().numpy(),
            "piB": comp["piB"], "piR": comp["piR"], "timings": timings}


def write_predictions(pred: dict, out: Path) -> str:
    path = out / "PREDICTII.npz"
    np.savez_compressed(path, **{k: v for k, v in pred.items() if isinstance(v, np.ndarray)})
    return sha256_bytes(path.read_bytes())


def score_from_file(ds: Dataset, pred_path: Path) -> dict:
    P = np.load(pred_path)
    ks = P["ks"]
    off = ds.step_offsets.cpu().numpy()
    oh = ds.onehot.cpu().numpy().astype(np.float64)
    rows, kidx = [], []
    for i, k in enumerate(ks):
        for r in range(off[k], off[k + 1]):
            rows.append(r)
            kidx.append(i)
    rows, kidx = np.array(rows), np.array(kidx)
    y = oh[rows]
    qQL, qB, qR = marginal_q(P["pi_QL"])[kidx], marginal_q(P["piB"])[kidx], marginal_q(P["piR"])[kidx]
    qU = np.full_like(y, 6.0 / N)
    tQL = P["variants"][:, 0, :][kidx]
    tB, tR = top6(P["piB"])[kidx], top6(P["piR"])[kidx]
    S = {"y": y}
    for name, q, t in (("QL", qQL, tQL), ("B", qB, tB), ("R", qR, tR), ("U", qU, None)):
        sb = score_block(q, t, y)
        S[f"log_{name}"], S[f"brier_{name}"] = sb["log"], sb["brier"]
        if t is not None:
            S[f"hits_{name}"] = sb["hits"]
    V = P["variants"][kidx]                                           # [T,3,6]
    uni = np.zeros_like(y)
    for v in range(V.shape[1]):
        np.put_along_axis(uni, V[:, v, :] - 1, 1.0, axis=1)
    S["hits_union"] = (uni * y).sum(-1)
    n = y.shape[0]
    h = n // 2
    res = {"total": summarize(slice(0, n), S), "half1": summarize(slice(0, h), S), "half2": summarize(slice(h, n), S)}
    res["gates"] = gates(res)
    res["gates_passed"] = sum(g["pass"] for g in res["gates"])
    res["verdict"] = "QL_PROMOVAT_EXPLORATORIU" if res["gates_passed"] == 6 else "QL_NO_PROMOTION_EXPLORATORY"
    match = np.bincount(S["hits_QL"].astype(int), minlength=7)[:7]
    res["match_dist_QL_v1"] = match.tolist()
    res["match_expected_U"] = (hyper_pmf() * n).tolist()
    res["p_exact_hits_QL_ge"] = exact_tail(int(S["hits_QL"].sum()), n)
    res["n_targets"] = int(n)
    res["n_steps_predicted"] = int(len(ks))
    res["tickets_changed_vs_B"] = int((tQL != tB).any(-1).sum())
    res["per_target"] = {"hits_QL": S["hits_QL"].astype(int).tolist(), "hits_B": S["hits_B"].astype(int).tolist(),
                         "hits_R": S["hits_R"].astype(int).tolist(), "hits_union": S["hits_union"].astype(int).tolist(),
                         "step": ks[kidx].astype(int).tolist()}
    return res


def run_backtest(ds: Dataset, out: Path, cfg: E.Config = E.PROTOCOL, warmup: int = WARMUP,
                 m_null: int = M_NULL, log=print) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    proto = ROOT / "PREINREGISTRARE_QL649.md"
    start = {"started_at_utc": utc_now(), "protocol_sha256": sha256_bytes(proto.read_bytes()),
             "code_sha256": {f: sha256_bytes((ROOT / f).read_bytes()) for f in ("parser.py", "engine.py", "validare.py")},
             "amendments_sha256": {p.name: sha256_bytes(p.read_bytes()) for p in sorted(ROOT.glob("AMENDAMENT_*.md"))},
             "config_digest": cfg.digest(), "is_protocol": cfg.is_protocol(), "source": ds.source,
             "source_sha256": ds.source_sha256, "n_draws": ds.n_draws, "n_steps": ds.n_steps, "warmup": warmup,
             "device": str(ds.device), "torch": torch.__version__, "positive_claims_allowed": False}
    (out / "START.json").write_text(json.dumps(start, indent=2) + "\n")
    t0 = time.perf_counter()
    pred = predict_all(ds, cfg, warmup, log=log)
    pred_sha = write_predictions(pred, out)
    (out / "PREDICTII_SIGILIU.json").write_text(json.dumps({"sha256": pred_sha, "written_at_utc": utc_now(),
                                                             "before_scoring": True}, indent=2) + "\n")
    res = score_from_file(ds, out / "PREDICTII.npz")
    res["predictions_sha256"] = pred_sha
    res["timings_s"] = pred["timings"]
    res["ep_converged_frac"] = float(pred["ep_converged"].mean())
    res["gamma_q_zero_frac"] = float((pred["gamma_q"] == 0).mean())
    t1 = time.perf_counter()
    sci = compute_sci(ds, M=m_null)
    res["sci_seconds"] = time.perf_counter() - t1
    res["backtest_seconds"] = time.perf_counter() - t0
    res["vram_peak_mib"] = torch.cuda.max_memory_allocated() / 2 ** 20 if ds.device.type == "cuda" else 0.0
    res["start"] = start
    res["finished_at_utc"] = utc_now()
    res["positive_claims_allowed"] = False
    (out / "SCI.json").write_text(json.dumps(sci, indent=2) + "\n")
    (out / "REZULTATE.json").write_text(json.dumps(res, indent=2) + "\n")
    manifest = {p.name: sha256_bytes(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file() and p.name != "MANIFEST.json"}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"res": res, "sci": sci}


def synthetic_dataset(path: Path, n: int = 260, seed: int = 3, device=None) -> Dataset:
    rng = np.random.default_rng(seed)
    rows, day = [], 0
    for i in range(n):
        if i % 11 != 5:
            day += 1
        nums = sorted(int(x) + 1 for x in rng.choice(49, 6, replace=False))
        d = (dt.date(2001, 1, 1) + dt.timedelta(days=day)).isoformat()
        rows.append({"draw_date": d, "numbers_sorted": nums, "numbers_as_stored": nums,
                     "draw_key": f"syn:{d}:{'-'.join(map(str, nums))}", "draw_kind_as_stored": "synthetic"})
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return build_dataset(path, device)


def null_universe_file(ds_real: Dataset, path: Path, seed: int) -> Path:
    """Univers nul: ACEEAȘI structură de pași (datele/zilele reale) dar extrageri uniforme fără întoarcere."""
    rng = np.random.default_rng([SEED_NULL, seed])
    rows = []
    for i, d in enumerate(ds_real.dates):
        nums = sorted(int(x) + 1 for x in rng.choice(49, 6, replace=False))
        rows.append({"draw_date": d, "numbers_sorted": nums, "numbers_as_stored": nums,
                     "draw_key": f"null{seed}:{d}:{i}:{'-'.join(map(str, nums))}", "draw_kind_as_stored": "synthetic_null"})
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def run_null_pipeline(M: int, out_root: Path, log=print, start_u: int = 0) -> dict:
    """Pipeline COMPLET (configurația protocolului) pe M universuri nule — descriptiv (§5)."""
    dev = resolve_device()
    real = build_dataset(DEFAULT_SOURCE, dev)
    out_root.mkdir(parents=True, exist_ok=True)
    summ = []
    for u in range(start_u, start_u + M):
        ud = out_root / f"u{u:03d}"
        if (ud / "run" / "REZULTATE.json").exists():
            res = json.loads((ud / "run" / "REZULTATE.json").read_text())
        else:
            ud.mkdir(exist_ok=True)
            ds = build_dataset(null_universe_file(real, ud / f"synthetic_null_u{u:03d}.jsonl", u), dev)
            res = run_backtest(ds, ud / "run", E.PROTOCOL, WARMUP, m_null=256, log=log)["res"]
        t = res["total"]
        summ.append({"u": u, "excess_QL": t["excess_QL"], "hits_QL": t["hits_QL"], "hits_B": t["hits_B"],
                     "hits_R": t["hits_R"], "logQL_minus_U": t["log_QL"] - t["log_U"],
                     "logQL_minus_B": t["log_QL"] - t["log_B"], "gates_passed": res["gates_passed"],
                     "seconds": res.get("backtest_seconds")})
        log(f"[QL649] univers nul {u}: exces={t['excess_QL']:+.4f} porți={res['gates_passed']}/6")
    agg = {"M": len(summ), "universes": summ, "generated_at_utc": utc_now(),
           "mean_excess_QL": float(np.mean([s["excess_QL"] for s in summ])) if summ else None,
           "max_gates_passed": max((s["gates_passed"] for s in summ), default=None)}
    (out_root / "SUMAR.json").write_text(json.dumps(agg, indent=2) + "\n")
    return agg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--real", action="store_true", help="rularea unică preînregistrată pe istoria reală")
    g.add_argument("--synthetic", metavar="OUT", help="pipeline pe date sintetice (inginerie)")
    g.add_argument("--null-pipeline", type=int, metavar="M", help="pipeline complet pe M universuri nule")
    ap.add_argument("--start-u", type=int, default=0)
    a = ap.parse_args(argv)
    dev = resolve_device()
    if a.null_pipeline:
        agg = run_null_pipeline(a.null_pipeline, ROOT / "rezultate" / "multivers_pipeline", start_u=a.start_u)
        print(json.dumps({k: v for k, v in agg.items() if k != "universes"}, indent=2))
        return 0
    if a.real:
        out = ROOT / "rezultate" / "backtest_unic"
        if (out / "START.json").exists():
            print("REFUZ: backtestul unic a fost deja pornit (rezultate/backtest_unic/START.json există).")
            return 2
        ds = build_dataset(DEFAULT_SOURCE, dev)
        r = run_backtest(ds, out)
    else:
        out = Path(a.synthetic)
        out.mkdir(parents=True, exist_ok=True)
        ds = synthetic_dataset(out / "synthetic.jsonl", device=dev)
        fast = replace(E.PROTOCOL, mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60, gamma_grid=12)
        r = run_backtest(ds, out / "run", fast, warmup=40, m_null=512)
    show = {k: v for k, v in r["res"].items() if k not in ("per_target",)}
    print(json.dumps(show, indent=2, default=str))
    print(json.dumps({"SCI": r["sci"]["SCI"], "p": r["sci"]["p_empirical"], "z": r["sci"]["z"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
