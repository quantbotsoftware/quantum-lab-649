"""TU4-S16: martorii W0–W4 ai cererii „expansiunea preciziei H1/H3” (Mesajul 59).

Protocol: tu4/PROTOCOL_TU4_S16.md (ae7b1145…), sigiliu tu4/SIGILIU_TU4_S16.json (23:51:34Z), scrise ÎNAINTE de acest
cod. Fișier NOU: nu modifică ip_core.py / judecator.py / emite.py / emisiile. Fixturi sintetice, fără arhiva reală.
Calcul clasic float64 / complex128 (FrFT pe CPU NumPy; enumerarea W4 pe GPU compilat + CPU NumPy).
positive_claims_allowed = false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import itertools
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent            # tu4/
ROOT = HERE.parent                                # quantum_lab_649/
IP_CORE = HERE / "ip_core.py"
IP_SHA = "ab3e1de93d8e5ae537a8c80599905aaa19cc103602f9b18f4b7f7f6f8a48c302"
PROTOCOL = HERE / "PROTOCOL_TU4_S16.md"
SEAL = HERE / "SIGILIU_TU4_S16.json"
OUT_DIR = HERE / "rezultate" / "S16"

N_DRAWS = 2595
NG, KG = 49, 6
D_STAR = 0.001619927375358543
A_GRID = (0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 1.9)
S_GRID = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0)
N_FRFT = (20, 40, 45, 49)
AB_PAIRS = ((0.3, 0.4), (0.5, 0.5), (0.25, 1.5))
BISECT_ITERS = 80
LN_THR = math.log(600.0)
DRAWS_PER_YEAR = 104
COMPILE_MODE = "max-autotune-no-cudagraphs"


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_ip_core():
    """Importă nucleul ÎNGHEȚAT numai după verificarea sha-ului (fără nicio modificare)."""
    got = sha_file(IP_CORE)
    if got != IP_SHA:
        raise RuntimeError(f"ip_core.py sha {got} != {IP_SHA}")
    spec = importlib.util.spec_from_file_location("ip_core_s16_ro", IP_CORE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ FrFT discretă (Candan–Kutay–Ozaktas 2000)
def s_matrix(n: int) -> np.ndarray:
    S = np.zeros((n, n))
    j = np.arange(n)
    S[j, j] = 2.0 * np.cos(2.0 * np.pi * j / n) - 4.0
    S[j, (j + 1) % n] += 1.0
    S[j, (j - 1) % n] += 1.0
    return S


def p_matrix(n: int) -> np.ndarray:
    """Matricea ortogonală simetrică ce separă subspațiul par (x_j = x_{n-j}) de cel impar."""
    r, even = n // 2, (n % 2 == 0)
    P = np.zeros((n, n))
    P[0, 0] = 1.0
    s = 1.0 / math.sqrt(2.0)
    for i in range(1, r - int(even) + 1):
        P[i, i] = s
        P[i, n - i] = s
    if even:
        P[r, r] = 1.0
    for i in range(r + 1, n):
        P[i, i] = -s
        P[i, n - i] = s
    return P


def frft_basis(n: int) -> tuple[np.ndarray, np.ndarray]:
    """V (n, n) real ortonormal și ordinele Hermite r (0..n-2, n-1+[n par])."""
    S, P = s_matrix(n), p_matrix(n)
    CS = P @ S @ P.T
    ne = n // 2 + 1
    ec, vc = np.linalg.eigh(CS[:ne, :ne])
    es, vs = np.linalg.eigh(CS[ne:, ne:])
    ve = P @ np.vstack([vc, np.zeros((n - ne, ne))])
    vo = P @ np.vstack([np.zeros((ne, n - ne)), vs])
    ve = ve[:, np.argsort(-ec, kind="stable")]
    vo = vo[:, np.argsort(-es, kind="stable")]
    cols, orders = [], []
    for j in range(ne):
        cols.append(ve[:, j])
        orders.append(2 * j)
    for j in range(n - ne):
        cols.append(vo[:, j])
        orders.append(2 * j + 1)
    return np.stack(cols, 1), np.array(orders, dtype=float)


def frft_matrix(n: int, a: float, basis=None) -> np.ndarray:
    V, r = basis if basis is not None else frft_basis(n)
    return (V * np.exp(-1j * np.pi * a * r / 2.0)[None, :]) @ V.T


def dft_unitary(n: int) -> np.ndarray:
    m = np.arange(n)
    return np.exp(-2j * np.pi * np.outer(m, m) / n) / math.sqrt(n)


# ------------------------------------------------------------------ fixturi
def profile_v(n: int = NG) -> np.ndarray:
    i = np.arange(1, n + 1)
    return ((5 * i) % n - (n - 1) // 2).astype(float)


def profile_g(n: int = NG) -> np.ndarray:
    i = np.arange(1, n + 1)
    return np.cos(2.0 * np.pi * (i - 0.5) / n)


def counts_for(u: np.ndarray, x2: float, n: int = NG, k: int = KG, N: int = N_DRAWS) -> np.ndarray:
    p = k / n
    gamma = math.sqrt(x2 * N * p * (1 - p) * n / ((n - 1) * float(u @ u)))
    return N * p + gamma * u


def z_of(c: np.ndarray, n: int = NG, k: int = KG, N: int = N_DRAWS) -> np.ndarray:
    p = k / n
    return math.sqrt((n - 1) / n) * (c - N * p) / math.sqrt(N * p * (1 - p))


def fixtures() -> dict:
    v, g = profile_v(), profile_g()
    return {"F1": counts_for(v, 50.0), "I1": counts_for(v, 400.0), "G": counts_for(g, 100.0)}


def top_ticket(lw: np.ndarray, b: int = KG) -> list[int]:
    order = sorted(range(len(lw)), key=lambda i: (-lw[i], i))
    return sorted(i + 1 for i in order[:b])


# ------------------------------------------------------------------ W0–W3
def run_w0_w1() -> list[dict]:
    checks = []
    for n in N_FRFT:
        basis = frft_basis(n)
        I = np.eye(n)
        e0 = float(np.abs(frft_matrix(n, 0.0, basis) - I).max())
        e1 = float(np.abs(frft_matrix(n, 1.0, basis) - dft_unitary(n)).max())
        checks.append(dict(id=f"W0_F0_n{n}", value=e0, threshold=1e-10, ok=e0 <= 1e-10))
        checks.append(dict(id=f"W0_F1_DFT_n{n}", value=e1, threshold=1e-8, ok=e1 <= 1e-8))
        for a, b in AB_PAIRS:
            e = float(np.abs(frft_matrix(n, a, basis) @ frft_matrix(n, b, basis)
                             - frft_matrix(n, a + b, basis)).max())
            checks.append(dict(id=f"W0_add_n{n}_a{a}_b{b}", value=e, threshold=1e-8, ok=e <= 1e-8))
        for a in A_GRID:
            F = frft_matrix(n, a, basis)
            e = float(np.abs(F.conj().T @ F - I).max())
            checks.append(dict(id=f"W1_unit_n{n}_a{a}", value=e, threshold=1e-10, ok=e <= 1e-10))
    return checks


def run_w2_w3(ip) -> list[dict]:
    import torch
    checks = []
    n, k, N = NG, KG, N_DRAWS
    p = k / n
    basis = frft_basis(n)
    B = ip.dct_basis(n)
    Nt = torch.tensor(float(N), dtype=torch.float64)
    for name, c in fixtures().items():
        z = z_of(c)
        for a in A_GRID:
            F = frft_matrix(n, a, basis)
            rel = abs(float(np.sum(np.abs(F @ z) ** 2)) - float(z @ z)) / float(z @ z)
            checks.append(dict(id=f"W2_X2_{name}_a{a}", value=rel, threshold=1e-9, ok=rel <= 1e-9))
            cp = N * p + np.real(F.conj().T @ (F @ (c - N * p)))
            ct, cpt = torch.tensor(c, dtype=torch.float64), torch.tensor(cp, dtype=torch.float64)
            for model in ("H1", "H3"):
                if model == "H1":
                    (lw, lam), (lw2, lam2) = ip.logw_h1(ct, Nt, n, k), ip.logw_h1(cpt, Nt, n, k)
                else:
                    (lw, lam), (lw2, lam2) = ip.logw_h3(ct, Nt, n, k, B), ip.logw_h3(cpt, Nt, n, k, B)
                lw, lw2 = lw.numpy(), lw2.numpy()
                dlw = float(np.abs(lw - lw2).max())
                dlam = abs(float(lam) - float(lam2))
                t1, t2 = top_ticket(lw), top_ticket(lw2)
                checks.append(dict(id=f"W3_{model}_{name}_a{a}", value=dict(max_dlogw=dlw, dlambda=dlam,
                                   lambda_=float(lam), ticket=t1, ticket_rt=t2),
                                   threshold=dict(max_dlogw=1e-9, dlambda=1e-10, ticket="identic"),
                                   ok=(dlw <= 1e-9 and dlam <= 1e-10 and t1 == t2)))
    return checks


# ------------------------------------------------------------------ W4
def calibrate_eps(ip, vhat: np.ndarray, k: int, D: float, iters: int = BISECT_ITERS) -> float:
    import torch
    vt = torch.tensor(vhat, dtype=torch.float64)
    Df = lambda e: float(ip.info_D(e * vt, k))
    hi = 1.0
    while Df(hi) <= D:
        hi *= 2.0
    lo = 0.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if Df(mid) < D:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def closed_form(ip, lnw: np.ndarray, k: int, s_grid=S_GRID) -> dict:
    """G_P(s) = s Σ π_i ln w_i − L(s), G_U(s) = s·(k/n)Σ ln w_i − L(s), L(s) = ln e_k(w_s) − ln C(n,k)."""
    import torch
    n = len(lnw)
    lc = ip.log_comb(n, k)
    lt = torch.tensor(lnw, dtype=torch.float64)
    w = torch.exp(lt)
    e = ip.esp(w, k)
    em = torch.ones_like(w)
    for j in range(1, k):
        em = e[j:j + 1] - w * em
    pi = (w * em / e[k]).numpy()
    EP = float(pi @ lnw)
    meanU = k / n * float(lnw.sum())
    L = [float(torch.log(ip.esp(torch.exp(s * lt), k)[k])) - lc for s in s_grid]
    return dict(sum_pi=float(pi.sum()), EP=EP, meanU=meanU, L=L,
                G_P=[s * EP - l for s, l in zip(s_grid, L)], G_U=[s * meanU - l for s, l in zip(s_grid, L)],
                D_info=float(ip.info_D(lt, k)))


def all_subsets(n: int, k: int) -> np.ndarray:
    M = math.comb(n, k)
    return np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(n), k)),
                       dtype=np.int16, count=M * k).reshape(M, k)


def enum_cpu(lnw: np.ndarray, idx: np.ndarray, s_grid=S_GRID) -> dict:
    sP = np.zeros(idx.shape[0])
    for j in range(idx.shape[1]):
        sP += lnw[idx[:, j]]
    L = []
    for s in s_grid:
        x = s * sP
        m = float(x.max())
        L.append(math.log(float(np.exp(x - m).mean())) + m)
    L1 = L[list(s_grid).index(1.0)]
    wP = np.exp(sP - L1)
    EP, sumP, meanU = float((wP * sP).mean()), float(wP.mean()), float(sP.mean())
    return dict(L=L, EP=EP, sumP=sumP, meanU=meanU,
                G_P=[s * EP - l for s, l in zip(s_grid, L)], G_U=[s * meanU - l for s, l in zip(s_grid, L)])


def _w4_kernel(lnw, idx, svec):
    import torch
    sP = lnw[idx].sum(1)
    x = svec[:, None] * sP[None, :]
    m = x.amax(1, keepdim=True)
    L = torch.log(torch.exp(x - m).mean(1)) + m[:, 0]
    m1 = sP.max()
    L1 = torch.log(torch.exp(sP - m1).mean()) + m1
    wP = torch.exp(sP - L1)
    return L, (wP * sP).mean(), wP.mean(), sP.mean()


def enum_gpu(lnw: np.ndarray, idx: np.ndarray, s_grid=S_GRID, compiled: bool = True) -> dict:
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    status = "eager"
    fn = _w4_kernel
    if compiled:
        try:
            fn = torch.compile(_w4_kernel, mode=COMPILE_MODE, fullgraph=True, dynamic=False)
            status = "compiled:" + COMPILE_MODE
        except Exception as exc:  # declarat
            fn, status = _w4_kernel, "eager_fallback:" + repr(exc)[:200]
    lt = torch.tensor(lnw, dtype=torch.float64, device=dev)
    it = torch.from_numpy(idx.astype(np.int64)).to(dev)
    st = torch.tensor(s_grid, dtype=torch.float64, device=dev)
    t0 = time.time()
    try:
        L, EP, sumP, meanU = fn(lt, it, st)
    except Exception as exc:  # eșec la prima execuție => eager, declarat
        if not compiled:
            raise
        status = "eager_fallback_runtime:" + repr(exc)[:200]
        L, EP, sumP, meanU = _w4_kernel(lt, it, st)
    if dev == "cuda":
        torch.cuda.synchronize()
    t_first = time.time() - t0
    t0 = time.time()
    L, EP, sumP, meanU = fn(lt, it, st) if status.startswith("compiled") else (L, EP, sumP, meanU)
    if dev == "cuda":
        torch.cuda.synchronize()
    t_second = time.time() - t0
    L = [float(x) for x in L.cpu()]
    EP, sumP, meanU = float(EP), float(sumP), float(meanU)
    return dict(device=dev, status=status, t_first_s=t_first, t_second_s=t_second, L=L, EP=EP, sumP=sumP,
                meanU=meanU, G_P=[s * EP - l for s, l in zip(s_grid, L)],
                G_U=[s * meanU - l for s, l in zip(s_grid, L)])


def gpu_temp() -> str:
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,clocks.sm",
                               "--format=csv,noheader"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as exc:
        return "unavailable:" + repr(exc)[:80]


def run_w4(ip) -> tuple[list[dict], dict]:
    import torch
    n, k = NG, KG
    v = profile_v(n)
    vhat = v / np.linalg.norm(v)
    eps = calibrate_eps(ip, vhat, k, D_STAR)
    lnw = eps * vhat
    D_cal = float(ip.info_D(torch.tensor(lnw, dtype=torch.float64), k))
    cf = closed_form(ip, lnw, k)
    t0 = time.time()
    idx = all_subsets(n, k)
    t_idx = time.time() - t0
    t0 = time.time()
    cpu = enum_cpu(lnw, idx)
    t_cpu = time.time() - t0
    temp_before = gpu_temp()
    gpu = enum_gpu(lnw, idx)
    temp_after = gpu_temp()
    i1 = S_GRID.index(1.0)
    checks = [dict(id="W4_calibrare", value=abs(D_cal - D_STAR) / D_STAR, threshold=1e-10,
                   ok=abs(D_cal - D_STAR) / D_STAR <= 1e-10)]
    for j, s in enumerate(S_GRID):
        dgc = max(abs(gpu["G_P"][j] - cpu["G_P"][j]), abs(gpu["G_U"][j] - cpu["G_U"][j]))
        dcf = max(abs(cpu["G_P"][j] - cf["G_P"][j]), abs(cpu["G_U"][j] - cf["G_U"][j]))
        checks.append(dict(id=f"W4a_gpu_cpu_s{s}", value=dgc, threshold=1e-10, ok=dgc <= 1e-10))
        checks.append(dict(id=f"W4a_enum_closed_s{s}", value=dcf, threshold=1e-9, ok=dcf <= 1e-9))
        checks.append(dict(id=f"W4b_GP_le_D_s{s}", value=cpu["G_P"][j], threshold=D_STAR + 1e-12,
                           ok=cpu["G_P"][j] <= D_STAR + 1e-12))
        checks.append(dict(id=f"W4c_GU_le_0_s{s}", value=cpu["G_U"][j], threshold=1e-12,
                           ok=cpu["G_U"][j] <= 1e-12))
    for name, r in (("cpu", cpu), ("gpu", gpu)):
        checks.append(dict(id=f"W4a_sumP_{name}", value=abs(r["sumP"] - 1.0), threshold=1e-12,
                           ok=abs(r["sumP"] - 1.0) <= 1e-12))
    checks.append(dict(id="W4b_GP1_eq_D", value=abs(cpu["G_P"][i1] - D_STAR), threshold=1e-9,
                       ok=abs(cpu["G_P"][i1] - D_STAR) <= 1e-9))
    jmax = int(np.argmax(cpu["G_P"]))
    checks.append(dict(id="W4b_argmax_s1", value=S_GRID[jmax], threshold=1.0, ok=S_GRID[jmax] == 1.0))
    pos = [j for j, s in enumerate(S_GRID) if s > 0]
    dec = all(cpu["G_U"][a] > cpu["G_U"][b] for a, b in zip(pos, pos[1:]))
    checks.append(dict(id="W4c_GU_strict_desc", value=[cpu["G_U"][j] for j in pos], threshold="strict", ok=dec))
    t_star = LN_THR / D_STAR
    info = dict(eps=eps, D_calibrated=D_cal, n_subsets=int(idx.shape[0]), t_index_s=t_idx, t_cpu_s=t_cpu,
                closed_form=cf, cpu=cpu, gpu=gpu, gpu_before=temp_before, gpu_after=temp_after,
                t_star_draws=t_star, t_star_years=t_star / DRAWS_PER_YEAR,
                G_P=dict(zip(map(str, S_GRID), cpu["G_P"])), G_U=dict(zip(map(str, S_GRID), cpu["G_U"])))
    return checks, info


def main() -> int:
    import torch
    seal = json.loads(SEAL.read_text())
    assert sha_file(PROTOCOL) == seal["documents"]["tu4/PROTOCOL_TU4_S16.md"]["sha256"], "protocol drift"
    drift = [f for f, h in seal["frozen_hashes"].items() if sha_file(ROOT / f) != h]
    ip = load_ip_core()
    t0 = time.time()
    checks = [dict(id="S_drift_frozen", value=drift, threshold=[], ok=drift == [])]
    checks += run_w0_w1()
    checks += run_w2_w3(ip)
    w4_checks, w4 = run_w4(ip)
    checks += w4_checks
    n_fail = sum(1 for c in checks if not c["ok"])
    groups = {}
    for c in checks:
        g = c["id"].split("_")[0]
        groups.setdefault(g, [0, 0])
        groups[g][0] += 1
        groups[g][1] += int(c["ok"])
    verdict = "S16_NECALIFICAT_INVARIANTA" if n_fail == 0 else "S16_INCIDENT_TEHNIC"
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = dict(protocol="TU4-S16", protocol_sha256=sha_file(PROTOCOL), seal_sha256=sha_file(SEAL),
               script_sha256=sha_file(Path(__file__)), ip_core_sha256=IP_SHA, utc=utc, verdict=verdict,
               n_checks=len(checks), n_pass=len(checks) - n_fail, n_fail=n_fail, groups=groups,
               runtime_s=time.time() - t0, torch=torch.__version__,
               device=torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
               real_archive_read=False, positive_claims_allowed=False, w4=w4, checks=checks)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"MARTORI_S16_{utc}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    os.chmod(path, 0o444)
    print(path)
    print(json.dumps(dict(verdict=verdict, n_checks=len(checks), n_pass=len(checks) - n_fail, n_fail=n_fail,
                          groups=groups, t_star_draws=round(w4["t_star_draws"], 1),
                          t_star_years=round(w4["t_star_years"], 1), G_P=w4["G_P"], G_U=w4["G_U"],
                          gpu_status=w4["gpu"]["status"], gpu_before=w4["gpu_before"],
                          gpu_after=w4["gpu_after"]), ensure_ascii=False))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
