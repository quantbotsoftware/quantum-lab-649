"""TU4-IP (S11): martori (Q5, Q6, fixturile F/I), generarea lumilor sintetice pe SSD (numpy.memmap, scriere
asincronă) și rularea UNICĂ de calificare. Protocol tu4/PROTOCOL_TU4_IP*.md, sigiliu tu4/SIGILIU_TU4_IP.json.

Utilizare:  python -B tu4/ip_run.py martori   |   python -B tu4/ip_run.py califica
Rezultatele sunt 0444 și nu se suprascriu. Arhiva reală NU este citită.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import hashlib
import itertools
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ip_core as C  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tu4/rezultate/IP"
SSD = Path("./ssd_data/QL649_S11")
SEAL = ROOT / "tu4/SIGILIU_TU4_IP.json"
DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
EVAL_CHUNK = 200
GEN_CHUNK = {"U": 100, "A1": 100, "A3": 100, "A2": 20}


def utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 24), b""):
            h.update(blk)
    return h.hexdigest()


def write_result(name: str, obj) -> Path:
    p = OUT / name
    if p.exists():
        raise SystemExit(f"refuz: {p} există deja")
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")
    os.chmod(p, 0o444)
    return p


def check_seal() -> dict:
    seal = json.loads(SEAL.read_text())
    bad = [f for f, v in seal["documents"].items() if sha_file(ROOT / f) != v["sha256"]]
    bad += [f for f, v in seal["frozen_hashes"].items() if sha_file(ROOT / f) != v]
    if bad:
        raise SystemExit(f"drift față de sigiliu: {bad}")
    return seal


def parts_of(game):
    cfg = C.GAMES[game]
    ps = [("main", cfg["n"], cfg["k"], cfg["D"])]
    if cfg["ball"]:
        b = cfg["ball"]
        ps.append(("ball", b["n"], b["k"], b["D"]))
    return ps


# ---------------------------------------------------------------- generarea unei bucăți de lumi
def implant(cell, W, n, k, D, Tn, gen):
    if cell == "U":
        return torch.zeros((W, n), dtype=C.DT, device=DEV), torch.zeros(W, dtype=C.DT, device=DEV)
    if cell == "A1":
        d = C.unit_dirs(W, n, gen, DEV)
        eps = C.calibrate(d, k, D)
        return eps[:, None] * d, eps
    if cell == "A3":
        d = C.smooth_dirs(W, n, gen, DEV)
        eps = C.calibrate(d, k, D)
        return eps[:, None] * d, eps
    x = C.ou_paths(W, Tn, n, gen, DEV)
    eps = C.calibrate(x[:, ::C.OU_GRID].contiguous(), k, D)
    return eps[:, None, None] * x, eps


def simulate(game, cell, W_total, chunk, gen, sink=None):
    """Generează W_total lumi în bucăți fixe; întoarce listele (dacă sink e None) sau scrie prin sink."""
    T = C.GAMES[game]["T"]
    Tn = T + C.H
    acc = {}
    for w0 in range(0, W_total, chunk):
        W = min(chunk, W_total - w0)
        for name, n, k, D in parts_of(game):
            lw, eps = implant(cell, W, n, k, D, Tn, gen)
            X = C.sample_cp(lw, k, Tn, gen)
            item = (X.cpu().numpy(), lw.cpu().numpy(), eps.cpu().numpy())
            if sink is None:
                acc.setdefault(name, []).append(item)
            else:
                sink(name, w0, W, *item)
    return acc


def gen_cell(game, cell, pool):
    T = C.GAMES[game]["T"]
    Tn = T + C.H
    d = SSD / f"{game}_{cell}"
    d.mkdir(parents=True, exist_ok=True)
    mm, eps_all = {}, {}
    for name, n, k, D in parts_of(game):
        if (d / f"X_{name}.npy").exists():
            raise SystemExit(f"refuz: {d}/X_{name}.npy există")
        mm[name] = {"X": np.lib.format.open_memmap(d / f"X_{name}.npy", mode="w+", dtype=np.uint8,
                                                   shape=(C.R, Tn, n))}
        if cell != "U":
            shp = (C.R, Tn, n) if cell == "A2" else (C.R, n)
            mm[name]["LW"] = np.lib.format.open_memmap(d / f"LW_{name}.npy", mode="w+", dtype=np.float64, shape=shp)
        eps_all[name] = np.zeros(C.R)
    futs = []

    def write(name, w0, W, X, lw, eps):
        mm[name]["X"][w0:w0 + W] = X
        if "LW" in mm[name]:
            mm[name]["LW"][w0:w0 + W] = lw
        eps_all[name][w0:w0 + W] = eps

    def sink(name, w0, W, X, lw, eps):
        while len([f for f in futs if not f.done()]) >= 2:
            time.sleep(0.01)
        futs.append(pool.submit(write, name, w0, W, X, lw, eps))
    gen = torch.Generator(device=DEV)
    gen.manual_seed(C.seed_of(game, cell))
    simulate(game, cell, C.R, GEN_CHUNK[cell], gen, sink)
    for f in futs:
        f.result()
    files = {}
    for name in mm:
        for key, arr in mm[name].items():
            arr.flush()
            files[str(d / f"{key}_{name}.npy")] = None
    mm.clear()
    return eps_all, files


def eval_cell(game, cell, B):
    T = C.GAMES[game]["T"]
    d = SSD / f"{game}_{cell}"
    res = {m: {"final": [], "max": [], "first": []} for m in C.MODELS}
    Xs = {name: np.load(d / f"X_{name}.npy", mmap_mode="r") for name, *_ in parts_of(game)}
    for w0 in range(0, C.R, EVAL_CHUNK):
        tot = None
        for name, n, k, D in parts_of(game):
            X = torch.from_numpy(np.ascontiguousarray(Xs[name][w0:w0 + EVAL_CHUNK])).to(DEV).to(C.DT)
            le = C.log_e_all(X[:, :T], X[:, T:], n, k, B[n], compiled=True)
            tot = le if tot is None else {m: tot[m] + le[m] for m in C.MODELS}
        for m in C.MODELS:
            f, mx, fi = C.summarize(tot[m])
            res[m]["final"].append(f.cpu().numpy())
            res[m]["max"].append(mx.cpu().numpy())
            res[m]["first"].append(fi.cpu().numpy())
    return {m: {k2: np.concatenate(v) for k2, v in r.items()} for m, r in res.items()}


# ---------------------------------------------------------------- martori
def enum_check(n, k, lw):
    lw = np.asarray(lw)
    logs = np.array([lw[list(S)].sum() for S in itertools.combinations(range(n), k)])
    lse = float(np.log(np.exp(logs - logs.max()).sum()) + logs.max())
    lek = float(torch.log(C.esp(torch.exp(C._t(lw)), k)[k]))
    q = np.exp(logs - lek)
    lc = C.log_comb(n, k)
    le = C._log_e_factor(C._t(lw)[None].expand(len(logs), n),
                         torch.stack([torch.zeros(n, dtype=C.DT).index_fill_(0, torch.tensor(S), 1.0)
                                      for S in itertools.combinations(range(n), k)]), k, lc).numpy()
    return {"sum_q_minus_1": float(abs(q.sum() - 1)), "lek_vs_enum": abs(lek - lse),
            "kernel_sum_minus_1": float(abs(np.exp(le - lc).sum() - 1))}


def random_states(n, k, rng, cnt=5, N=300):
    p = k / n
    out = []
    for _ in range(cnt):
        z = rng.normal(size=n)
        z -= z.mean()
        c = N * p + 2.0 * math.sqrt(N * p * (1 - p)) * z
        out.append(c)
    return out


def martori() -> dict:
    seal = check_seal()
    rng = np.random.default_rng(2026102799)
    res = {"protocol": "TU4-IP", "seal_sha256": sha_file(SEAL), "code_sha256": {
        "tu4/ip_core.py": sha_file(ROOT / "tu4/ip_core.py"), "tu4/ip_run.py": sha_file(ROOT / "tu4/ip_run.py")},
        "start_utc": utc(), "device": torch.cuda.get_device_name(0) if DEV.type == "cuda" else "cpu",
        "torch": torch.__version__}
    # T1 / T5 enumerare
    t1 = []
    for (n, k) in ((12, 4), (20, 1)):
        Nt, N2t = C.disc_N(300)
        for c in random_states(n, k, rng):
            for m, lw in (("H1", C.lw_h1_np(c, 300, n, k)[0]), ("H2", C.lw_h2_np(c * Nt / 300, Nt, N2t, n, k)[0]),
                          ("H3", C.lw_h3_np(c, 300, n, k)[0])):
                r = enum_check(n, k, lw)
                r.update({"n": n, "k": k, "model": m})
                t1.append(r)
    T1 = all(r["sum_q_minus_1"] <= 1e-12 and r["lek_vs_enum"] <= 1e-12 and r["kernel_sum_minus_1"] <= 1e-12
             for r in t1)
    res["T1_T5_enumerare"] = {"max_sum_q": max(r["sum_q_minus_1"] for r in t1),
                              "max_lek": max(r["lek_vs_enum"] for r in t1),
                              "max_kernel": max(r["kernel_sum_minus_1"] for r in t1), "cases": len(t1), "pass": T1}
    # T2 eșantionatorul
    n, k = 8, 3
    lw = 0.5 * np.linspace(-1, 1, n)
    g = torch.Generator(device=DEV)
    g.manual_seed(2026102798)
    X = C.sample_cp(torch.as_tensor(lw, dtype=C.DT, device=DEV)[None], k, 200_000, g)[0].cpu().numpy()
    subsets = list(itertools.combinations(range(n), k))
    idx = {S: j for j, S in enumerate(subsets)}
    cnt = np.zeros(len(subsets))
    for row in X:
        cnt[idx[tuple(np.flatnonzero(row))]] += 1
    pr = np.array([math.exp(lw[list(S)].sum()) for S in subsets])
    pr /= pr.sum()
    chi = float(((cnt - 200_000 * pr) ** 2 / (200_000 * pr)).sum())
    p_chi = float(stats.chi2.sf(chi, len(subsets) - 1))
    res["T2_esantionare"] = {"chi2": chi, "df": len(subsets) - 1, "p": p_chi, "pass": p_chi > 0.001}
    # T3 / T5 D exact
    t3 = []
    for (n, k) in ((10, 3), (20, 1)):
        for _ in range(5):
            lw = rng.normal(scale=0.4, size=n)
            logs = np.array([lw[list(S)].sum() for S in itertools.combinations(range(n), k)])
            q = np.exp(logs - logs.max())
            q /= q.sum()
            Denum = float((q * np.log(q * math.comb(n, k))).sum())
            t3.append(abs(Denum - C.D_np(lw, k)))
    res["T3_T5_D"] = {"max_abs": max(t3), "pass": max(t3) <= 1e-12}
    # T4 / T5 predictibilitate
    t4 = True
    det = []
    for (n, k) in ((12, 4), (20, 1)):
        g = torch.Generator(device=DEV)
        g.manual_seed(2026102797 + n)
        strong = 1.5 * torch.linspace(-1, 1, n, dtype=C.DT, device=DEV)[None].expand(4, n).contiguous()
        Xa = C.sample_cp(strong, k, 200, g).to(C.DT)
        Xf = C.sample_cp(strong, k, 30, g).to(C.DT)
        Xf2 = Xf.clone()
        t0 = 10
        Xf2[:, t0] = torch.roll(Xf[:, t0], 1, dims=1)
        assert bool((Xf2[:, t0] != Xf[:, t0]).any(1).all())
        B = C.dct_basis(n, C.K_AD, DEV)
        a, b2 = C.model_logw_all(Xa, Xf, n, k, B), C.model_logw_all(Xa, Xf2, n, k, B)
        for m in C.MODELS:
            same = bool(torch.equal(a[m][:, :t0 + 1], b2[m][:, :t0 + 1]))
            diff = bool((a[m][:, t0 + 1] != b2[m][:, t0 + 1]).any())
            det.append({"n": n, "k": k, "model": m, "q_t_unchanged": same, "q_t1_changed": diff})
            t4 = t4 and same and diff
    res["T4_T5_predictibilitate"] = {"cases": det, "pass": t4}
    # T6 compilat == eager (formele exacte ale rulării: W*H = 200*520)
    t6 = {}
    for (n, k) in ((49, 6), (40, 6), (45, 5), (20, 1)):
        g = torch.Generator(device=DEV)
        g.manual_seed(2026102796 + n + k)
        lw = 0.3 * torch.randn((EVAL_CHUNK * C.H, n), dtype=C.DT, device=DEV, generator=g)
        x = C.sample_cp(torch.zeros((1, n), dtype=C.DT, device=DEV), k, lw.shape[0], g)[0].to(C.DT)
        t_0 = time.time()
        a = C.run_kernel(n, k, lw, x, compiled=True)
        torch.cuda.synchronize()
        tc = time.time() - t_0
        e = C.run_kernel(n, k, lw, x, compiled=False)
        t6[f"{n}_{k}"] = {"max_abs": float((a - e).abs().max()), "first_call_s": round(tc, 1),
                          "status": C.COMPILE_STATUS.get(f"{n}_{k}")}
    res["T6_compilat_eager"] = {"cases": t6, "pass": all(v["max_abs"] <= 1e-9 for v in t6.values())}
    # T7 determinism
    t7 = []
    for game, cell in (("joker", "A2"), ("649", "A1")):
        outs = []
        for _ in range(2):
            g = torch.Generator(device=DEV)
            g.manual_seed(C.seed_of(game, cell) + 7_000_000)
            acc = simulate(game, cell, 4, 4, g)
            outs.append(acc)
        same = all(np.array_equal(outs[0][nm][0][0], outs[1][nm][0][0]) and
                   np.array_equal(outs[0][nm][0][1], outs[1][nm][0][1]) for nm in outs[0])
        T = C.GAMES[game]["T"]
        les = []
        for _ in range(2):
            tot = None
            for name, n, k, D in parts_of(game):
                X = torch.from_numpy(outs[0][name][0][0]).to(DEV).to(C.DT)
                le = C.log_e_all(X[:, :T], X[:, T:], n, k, C.dct_basis(n, C.K_AD, DEV), compiled=False)
                tot = le if tot is None else {m: tot[m] + le[m] for m in C.MODELS}
            les.append(tot)
        same_le = all(torch.equal(les[0][m], les[1][m]) for m in C.MODELS)
        t7.append({"game": game, "cell": cell, "bytes_identical": bool(same), "logE_identical": bool(same_le)})
    res["T7_determinism"] = {"cases": t7, "pass": all(r["bytes_identical"] and r["logE_identical"] for r in t7)}
    # fixturile
    fx = C.fixtures()
    res["fixtures"] = fx
    res["Q5_pass"] = bool(T1 and res["T2_esantionare"]["pass"] and res["T3_T5_D"]["pass"] and t4)
    res["Q6_pass"] = bool(res["T6_compilat_eager"]["pass"] and res["T7_determinism"]["pass"])
    res["verdict"] = "MARTORI_PASS" if res["Q5_pass"] and res["Q6_pass"] else "IP_NECALIFICAT_TEHNIC"
    res["end_utc"] = utc()
    res["positive_claims_allowed"] = False
    write_result("MARTORI_IP.json", res)
    return res


# ---------------------------------------------------------------- calificarea
def cp_lower(s, n, a=0.05):
    return 0.0 if s == 0 else float(stats.beta.ppf(a, s, n - s + 1))


def cp_upper(f, n, a=0.05):
    return 1.0 if f == n else float(stats.beta.ppf(1 - a, f + 1, n - f))


def califica() -> dict:
    seal = check_seal()
    mart = json.loads((OUT / "MARTORI_IP.json").read_text())
    if mart["verdict"] != "MARTORI_PASS":
        raise SystemExit("martorii nu au trecut: fără rulare mare")
    t0 = time.time()
    res = {"protocol": "TU4-IP", "seal_sha256": sha_file(SEAL), "martori_sha256": sha_file(OUT / "MARTORI_IP.json"),
           "code_sha256": {"tu4/ip_core.py": sha_file(ROOT / "tu4/ip_core.py"),
                           "tu4/ip_run.py": sha_file(ROOT / "tu4/ip_run.py")},
           "start_utc": utc(), "device": torch.cuda.get_device_name(0), "torch": torch.__version__,
           "R": C.R, "H": C.H, "ln_threshold": C.LN_THR, "ssd_root": str(SSD)}
    SSD.mkdir(parents=True, exist_ok=True)
    per = {}
    manifest = {}
    pool = cf.ThreadPoolExecutor(max_workers=1)
    cells = ("U", "A1", "A2", "A3")
    for game in C.GAMES:
        for cell in cells:
            ts = time.time()
            eps, files = gen_cell(game, cell, pool)
            for name, e in eps.items():
                per[f"{game}_{cell}_{name}_eps"] = e
            print(f"[gen] {game} {cell} {time.time() - ts:.1f}s", flush=True)
    pool.shutdown()
    for game in C.GAMES:
        Bs = {n: C.dct_basis(n, C.K_AD, DEV) for _, n, _, _ in parts_of(game)}
        for cell in cells:
            ts = time.time()
            r = eval_cell(game, cell, Bs)
            for m in C.MODELS:
                for key, arr in r[m].items():
                    per[f"{game}_{cell}_{m}_{key}"] = arr
            print(f"[eval] {game} {cell} {time.time() - ts:.1f}s", flush=True)
    for p in sorted(SSD.rglob("*.npy")):
        manifest[str(p.relative_to(SSD))] = {"sha256": sha_file(p), "bytes": p.stat().st_size}
    res["compile_status"] = dict(C.COMPILE_STATUS)
    gates = {}
    cross = {}
    for game in C.GAMES:
        cross[game] = {}
        for cell in cells:
            cross[game][cell] = {m: {"power_or_fpr": float((per[f"{game}_{cell}_{m}_max"] >= C.LN_THR).mean()),
                                     "mean_final_logE": float(per[f"{game}_{cell}_{m}_final"].mean()),
                                     "median_final_logE": float(np.median(per[f"{game}_{cell}_{m}_final"])),
                                     "median_first_crossing": (float(np.median(
                                         per[f"{game}_{cell}_{m}_first"][per[f"{game}_{cell}_{m}_first"] > 0]))
                                         if (per[f"{game}_{cell}_{m}_first"] > 0).any() else None)}
                                 for m in C.MODELS}
        for kk, m in enumerate(C.MODELS, start=1):
            alt = f"A{kk}"
            s = int((per[f"{game}_{alt}_{m}_max"] >= C.LN_THR).sum())
            f = int((per[f"{game}_U_{m}_max"] >= C.LN_THR).sum())
            means = {mm: float(per[f"{game}_{alt}_{mm}_final"].mean()) for mm in C.MODELS}
            q3a = all(means[m] > means[o] for o in C.MODELS if o != m) and means[m] > 0
            fx = mart["fixtures"]
            q3b = fx[f"I{kk}"]["pass"]
            q4 = fx[f"F{kk}"]["pass"]
            g = {"successes": s, "power": s / C.R, "power_LCB95": cp_lower(s, C.R), "Q1": cp_lower(s, C.R) >= 0.80,
                 "false_positives": f, "fpr": f / C.R, "fpr_UCB95": cp_upper(f, C.R), "Q2": cp_upper(f, C.R) <= 0.01,
                 "mean_final_logE_in_alt": means, "Q3a": bool(q3a), "Q3b": bool(q3b), "Q3": bool(q3a and q3b),
                 "Q4": bool(q4), "Q5": mart["Q5_pass"], "Q6": mart["Q6_pass"]}
            g["qualified"] = bool(g["Q1"] and g["Q2"] and g["Q3"] and g["Q4"] and g["Q5"] and g["Q6"])
            g["verdict"] = "IP_CALIFICAT" if g["qualified"] else "IP_NECALIFICAT"
            gates[f"{m}_{game}"] = g
    res["cross_matrix"] = cross
    res["gates"] = gates
    res["qualified"] = sorted(k for k, v in gates.items() if v["qualified"])
    res["eps_summary"] = {k: [float(v.min()), float(v.max())] for k, v in per.items() if k.endswith("_eps")}
    res["seconds"] = round(time.time() - t0, 1)
    res["end_utc"] = utc()
    res["positive_claims_allowed"] = False
    npz = OUT / "PER_LUME_IP.npz"
    if npz.exists():
        raise SystemExit("refuz: PER_LUME_IP.npz există")
    np.savez_compressed(npz, **per)
    os.chmod(npz, 0o444)
    res["per_world_sha256"] = sha_file(npz)
    write_result("MANIFEST_SSD_IP.json", {"ssd_root": str(SSD), "files": manifest, "utc": utc()})
    res["manifest_sha256"] = sha_file(OUT / "MANIFEST_SSD_IP.json")
    write_result("CALIFICARE_IP.json", res)
    return res


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "martori":
        r = martori()
        print(json.dumps({k: v for k, v in r.items() if k != "fixtures"}, indent=1, default=str)[:6000])
        print(json.dumps(r["fixtures"], indent=1))
    elif cmd == "califica":
        r = califica()
        print(json.dumps(r["gates"], indent=1))
        print("qualified:", r["qualified"])
    else:
        raise SystemExit(__doc__)
