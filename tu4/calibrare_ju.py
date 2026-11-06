#!/usr/bin/env python3
"""TU4-JU (S13): calibrarea nulă de control — 10⁴ istorii sub H0 (urna uniformă), protocol tu4/PROTOCOL_TU4_JU.md §6.

    .venv/bin/python -B tu4/calibrare_ju.py [--ssd ./ssd_data/QL649_TU4_JU] [--R 10000] [--iesire FIȘIER]

Eticheta din cerere („zgomot de fond Wheeler–DeWitt / martor gauge”) = calibrare Monte Carlo sub H0; nu este fizică.
Modelele: funcțiile ÎNGHEȚATE din tu4/ip_core.py (ab3e1de9…), neschimbate. Factorii e: nucleul compilat al judecătorului
(judecator.ln_e_torch, torch.compile max-autotune-no-cudagraphs, fullgraph). Calcul clasic. positive_claims_allowed=false.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ip_core as C  # noqa: E402  (nucleul ÎNGHEȚAT, neschimbat)
import judecator as J  # noqa: E402

SEED, H = 2026102713, 520
NW = {"649": 2597, "540": 2490, "joker": 2202}
BATCH = 1000
WARM_CHUNK = 500


def sha_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def q999(R: int, p: float) -> int:
    """Cea mai mică x cu P(Bin(R, p) ≤ x) ≥ 0.999 (exact, în spațiul logaritmic)."""
    cdf = 0.0
    for x in range(R + 1):
        cdf += math.exp(math.lgamma(R + 1) - math.lgamma(x + 1) - math.lgamma(R - x + 1)
                        + x * math.log(p) + (R - x) * math.log1p(-p))
        if cdf >= 0.999:
            return x
    return R


def uniform_counts(B: int, N: int, n: int, k: int, gen, dev) -> torch.Tensor:
    c = torch.zeros((B, n), dtype=C.DT, device=dev)
    left = N
    while left > 0:
        m = min(WARM_CHUNK, left)
        if k == 1:
            idx = torch.randint(0, n, (B, m), generator=gen, device=dev)
        else:
            idx = torch.rand((B, m, n), generator=gen, device=dev).topk(k, dim=2).indices.reshape(B, -1)
        c.scatter_add_(1, idx, torch.ones(idx.shape, dtype=C.DT, device=dev))
        left -= m
    return c


def uniform_draws(B: int, n: int, k: int, gen, dev) -> torch.Tensor:
    X = torch.zeros((B, H, n), dtype=C.DT, device=dev)
    if k == 1:
        idx = torch.randint(0, n, (B, H, 1), generator=gen, device=dev)
    else:
        idx = torch.rand((B, H, n), generator=gen, device=dev).topk(k, dim=2).indices
    X.scatter_(2, idx, 1.0)
    return X


def block_le(c0: torch.Tensor, X: torch.Tensor, Nw: int, n: int, k: int) -> dict:
    """ln e (B, H) pentru H1 și H3, cu modelele înghețate actualizate înaintea fiecărei extrageri."""
    B = X.shape[0]
    dev = X.device
    cum = torch.cumsum(X, 1)
    prev = torch.cat([torch.zeros_like(cum[:, :1]), cum[:, :-1]], 1)
    Cc = c0[:, None, :] + prev
    N = (Nw + torch.arange(H, dtype=C.DT, device=dev))[None, :].expand(B, H)
    lw1, lam1 = C.logw_h1(Cc, N, n, k)
    lw3, lam3 = C.logw_h3(Cc, N, n, k, C.dct_basis(n, C.K_AD, dev))
    xf = X.reshape(B * H, n).contiguous()
    out = {}
    for m, lw, lam in (("H1", lw1, lam1), ("H3", lw3, lam3)):
        le = J.ln_e_torch(n, k, lw.reshape(B * H, n).contiguous(), xf, (lam > 0).reshape(B * H).contiguous())
        out[m] = le.reshape(B, H)
        out[m + "_active"] = (lam > 0).float().mean().item()
    return out


def simulate(R: int, dev: str) -> tuple[dict, dict]:
    LE = {s: np.zeros((R, H), np.float64) for s in J.STREAMS}
    active = {s: [] for s in J.STREAMS}
    for gi, (game, g) in enumerate(J.GAMES.items()):
        gen = torch.Generator(device=dev).manual_seed(SEED + gi)
        n, k = g["n"], g["k"]
        for b0 in range(0, R, BATCH):
            B = min(BATCH, R - b0)
            c0 = uniform_counts(B, NW[game], n, k, gen, dev)
            X = uniform_draws(B, n, k, gen, dev)
            res = block_le(c0, X, NW[game], n, k)
            if g["ball"]:
                cb = uniform_counts(B, NW[game], J.NB, 1, gen, dev)
                Xb = uniform_draws(B, J.NB, 1, gen, dev)
                rb = block_le(cb, Xb, NW[game], J.NB, 1)
            for m in J.MODELS:
                le = res[m] + (rb[m] if g["ball"] else 0.0)
                LE[f"{m}_{game}"][b0:b0 + B] = le.double().cpu().numpy()
                active[f"{m}_{game}"].append(res[m + "_active"])
            del c0, X, res
        if dev == "cuda":
            torch.cuda.synchronize()
    return LE, {s: float(np.mean(v)) for s, v in active.items()}


def first_idx(mask: np.ndarray) -> np.ndarray:
    """Primul indice True pe axa 1, sau H dacă nu există."""
    any_ = mask.any(1)
    return np.where(any_, mask.argmax(1), mask.shape[1])


def stream_stats(le: np.ndarray) -> dict:
    R = le.shape[0]
    L = np.cumsum(le, 1)
    fr = first_idx(L < J.LN_RETIRE)
    f600 = first_idx(L >= J.LN_EXPLORE)
    f20 = first_idx(L >= J.LN_CONFIRM)
    hit600 = f600 < fr
    hit20 = f20 < fr
    conf = 0
    for r in np.nonzero(hit600)[0]:
        t0 = int(f600[r]) + 1
        if t0 < H:
            Lc = np.cumsum(le[r, t0:])
            a, b = first_idx((Lc >= J.LN_CONFIRM)[None])[0], first_idx((Lc < J.LN_RETIRE)[None])[0]
            conf += int(a < b and a < len(Lc))
    Lfroz = np.array([L[r, :min(int(fr[r]), H - 1) + 1].max() for r in range(R)])
    pm = np.exp(le).mean(1)
    qs = [1, 5, 50, 95, 99]
    return {"hits_ln600": int(hit600.sum()), "hits_ln20": int(hit20.sum()), "retired_by_H": int((fr < H).sum()),
            "confirmed_after_hit": conf, "mean_e": float(pm.mean()), "sd_e_hist": float(pm.std(ddof=1)),
            "mean_ln_e": float(le.mean()), "lnE_H_quantiles": dict(zip(map(str, qs), map(float, np.percentile(L[:, -1], qs)))),
            "sup_lnE_max": float(Lfroz.max()), "sup_lnE_q99": float(np.percentile(Lfroz, 99)),
            "_hit600_mask": hit600}


def c5_check(dev: str) -> dict:
    rng = np.random.default_rng(SEED)
    out = {}
    for n, k in ((49, 6), (40, 6), (45, 5), (20, 1)):
        lw = rng.normal(0.0, 0.05, (1000, n))
        x = np.zeros((1000, n))
        sets = [sorted(rng.choice(n, k, replace=False) + 1) for _ in range(1000)]
        for r, s in enumerate(sets):
            x[r, np.array(s) - 1] = 1.0
        act = rng.random(1000) < 0.9
        g = J.ln_e_torch(n, k, torch.tensor(lw, dtype=torch.float64, device=dev),
                         torch.tensor(x, dtype=torch.float64, device=dev), torch.tensor(act, device=dev)).cpu().numpy()
        cpu = np.array([J.ln_e_block(list(lw[r]), sets[r], k, bool(act[r])) for r in range(1000)])
        d = float(np.max(np.abs(g - cpu)))
        out[f"{n}_{k}"] = {"max_abs_diff": d, "pass": d <= J.GPU_GATE}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ssd", type=Path, default=None)
    ap.add_argument("--R", type=int, default=10000)
    ap.add_argument("--iesire", type=Path, default=HERE / "rezultate" / "JU" / "CALIBRARE_JU.json")
    a = ap.parse_args(argv)
    if a.iesire.exists():
        print(json.dumps({"action": "refused", "reason": f"{a.iesire} există deja (O_EXCL)"}))
        return 3
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.perf_counter()
    LE, act = simulate(a.R, dev)
    t_sim = time.perf_counter() - t0
    R = a.R
    st = {s: stream_stats(LE[s]) for s in J.STREAMS}
    fam = int(np.any(np.stack([st[s]["_hit600_mask"] for s in J.STREAMS]), 0).sum())
    q_s, q_f, q_c = q999(R, 1 / 600), q999(R, 0.01), q999(R, 0.05)
    c5 = c5_check(dev)
    gates = {
        "C1_per_stream_ln600": {s: {"hits": st[s]["hits_ln600"], "max": q_s, "pass": st[s]["hits_ln600"] <= q_s} for s in J.STREAMS},
        "C2_family_ln600": {"hits": fam, "max": q_f, "pass": fam <= q_f},
        "C3_per_stream_ln20": {s: {"hits": st[s]["hits_ln20"], "max": q_c, "pass": st[s]["hits_ln20"] <= q_c} for s in J.STREAMS},
        "C4_martingale": {s: {"mean_e": st[s]["mean_e"], "tol": 5 * st[s]["sd_e_hist"] / math.sqrt(R),
                              "pass": abs(st[s]["mean_e"] - 1) <= 5 * st[s]["sd_e_hist"] / math.sqrt(R)} for s in J.STREAMS},
        "C5_gpu_eq_cpu": c5,
    }
    ok = (all(v["pass"] for v in gates["C1_per_stream_ln600"].values()) and gates["C2_family_ln600"]["pass"]
          and all(v["pass"] for v in gates["C3_per_stream_ln20"].values())
          and all(v["pass"] for v in gates["C4_martingale"].values()) and all(v["pass"] for v in c5.values()))
    mm = None
    if a.ssd is not None:
        p = a.ssd / "calibrare" / "lnE_null_f32.mmap"
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(fd)
        arr = np.memmap(p, dtype=np.float32, mode="r+", shape=(len(J.STREAMS), R, H))
        for i, s in enumerate(J.STREAMS):
            arr[i] = np.cumsum(LE[s], 1).astype(np.float32)
        arr.flush()
        del arr
        os.chmod(p, 0o444)
        mm = {"path": str(p), "dtype": "float32", "shape": [len(J.STREAMS), R, H], "content": "ln E_t cumulat (brut)",
              "sha256": sha_file(p)}
    for s in J.STREAMS:
        st[s].pop("_hit600_mask")
    out = {
        "protocol": "TU4-JU", "session": "S13", "kind": "null_calibration",
        "label_user": "zgomot de fond Wheeler–DeWitt / martor gauge = etichetă; matematic: Monte Carlo sub H0",
        "R": R, "H": H, "seed": SEED, "N_warm": NW, "device": dev, "torch": torch.__version__,
        "compile_status": dict(J.COMPILE_STATUS), "bet_active_fraction": act,
        "binomial_q999": {"p_1_600": q_s, "p_0.01": q_f, "p_0.05": q_c},
        "streams": st, "gates": gates, "family_hits_ln600": fam, "memmap": mm,
        "seconds_simulation": round(t_sim, 1), "seconds_total": round(time.perf_counter() - t0, 1),
        "code": {"calibrare_ju_sha256": sha_file(__file__), "judecator_sha256": sha_file(HERE / "judecator.py"),
                 "ip_core_sha256": sha_file(HERE / "ip_core.py")},
        "verdict": "CALIBRARE_JU_PASS" if ok else "CALIBRARE_JU_FAIL",
        "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "positive_claims_allowed": False,
    }
    a.iesire.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(a.iesire, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    os.write(fd, (json.dumps(out, indent=1, ensure_ascii=False) + "\n").encode())
    os.fsync(fd)
    os.close(fd)
    print(json.dumps({"verdict": out["verdict"], "family_hits": fam, "seconds": out["seconds_total"],
                      "compile": out["compile_status"]}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
