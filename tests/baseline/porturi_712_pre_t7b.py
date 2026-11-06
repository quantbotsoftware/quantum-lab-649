"""TU3-T7A — porturile DESCRIPTIVE ale taburilor 7–12 pentru 5/40 și Joker (S4: BO = tab 7, WU = tab 8).

Protocol: PROTOCOL_TU3_T7A.md, sigilat în SIGILIU_TU3_T7A.json ÎNAINTE de acest cod. Decizia D3 = (b): porturi
DESCRIPTIVE — fără verdict, fără scor, fără bilete, fără clasări; verdictele pistelor 6/49 NU se transferă.

Algoritmii sunt copiați literal din pistele închise `bo649/bo649.py` (BOCPD Beta–Bernoulli exact, Adams & MacKay 2007)
și `wu649/wu649.py` (cursa exponențială Luce cu ordinea nevăzută marginalizată; MAP Newton–Levenberg + Armijo,
Amendamentul 01 WU); se schimbă numai constantele 49/6 în parametri (n, κ). Pistele închise NU se importă, NU se
execută și rămân byte-identice. Parametrii lor rămân neschimbați (fără tuning).

Calcul clasic: NumPy float64 pe CPU (ca pistele originale; necesar pentru testul de identitate). Nimic de aici nu este
predicție sau avantaj. `positive_claims_allowed=false`.

CLI (numai pentru raportul de identitate, P3):
  python -B tu3/porturi_712.py --identitate bo|wu            # JSON pe stdout
  python -B tu3/porturi_712.py --identitate toate --out tu3/rezultate/T7A   # două subprocese, raport 0444
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
QL = HERE.parent
PROTOCOL = HERE / "PROTOCOL_TU3_T7A.md"
OUT_DIR = HERE / "rezultate" / "T7A"
BO_REF = QL / "bo649" / "rezultate" / "backtest_unic"
WU_REF = QL / "wu649" / "rezultate" / "CALIFICARE.json"
TOL = 1e-12
LABEL = "DESCRIPTIV"
FORBIDDEN_KEYS = frozenset({"q", "q_BO", "q_WU", "pi", "piB", "piR", "ticket", "tickets", "ticket_BO", "ticket_B",
                            "ticket_R", "t_WU", "t_B", "t_R", "hits", "verdict", "gates", "gates_passed", "score",
                            "log_score", "brier", "excess", "top", "top6", "p_exact"})

# ---------------------------------------------------------------------------
# BO — parametrii pistei BO649 (neschimbați)
# ---------------------------------------------------------------------------
BO_H = 1.0 / 250.0
BO_M0 = 12.0
BO_WARMUP = 100
RECENT_R = 100


def bocpd(steps: list[np.ndarray], N: int, kappa: int, h: float, m0: float, keep_post: tuple = ()) -> dict:
    """Recursie exactă BOCPD Beta–Bernoulli, fără trunchiere (copiată literal din bo649.bocpd).

    steps[s]: array (n_s, N) cu 0/1 (extragerile pasului s). Returnează predicțiile prior
    (din date < s) pentru fiecare pas: q[K,N], E[r], P(r<=100), plus log-evidența totală.
    keep_post: pași pentru care se păstrează posteriorul prior-predictiv pe lungimi (UI/descriptiv).
    """
    a0, b0 = m0 * kappa / N, m0 * (N - kappa) / N
    K = len(steps)
    q = np.empty((K, N))
    Er = np.empty(K)
    prec = np.empty(K)
    lh, l1h = math.log(h), math.log1p(-h)
    n = np.zeros(0)
    C = np.zeros((0, N))
    logw = np.zeros(0)
    logZ = 0.0
    posts = {}
    for s in range(K):
        if s == 0:
            n = np.zeros(1)
            C = np.zeros((1, N))
            lp = np.zeros(1)
        else:
            lp = np.concatenate(([lh], l1h + logw))
            n = np.concatenate(([0.0], n))
            C = np.vstack((np.zeros((1, N)), C))
        w = np.exp(lp - lp.max())
        w /= w.sum()
        q[s] = w @ ((a0 + C) / (m0 + n)[:, None])
        r = np.arange(n.shape[0])
        Er[s] = float(w @ r)
        prec[s] = float(w[r <= RECENT_R].sum())
        if s in keep_post:
            posts[s] = w.copy()
        ll = np.zeros(n.shape[0])
        for y in steps[s]:
            y = np.asarray(y, dtype=np.float64)
            ll += (y * np.log(a0 + C) + (1.0 - y) * np.log(b0 + n[:, None] - C)).sum(1) - N * np.log(m0 + n)
            C = C + y
            n = n + 1.0
        lpost = lp + ll
        mx = lpost.max()
        lse = mx + math.log(np.exp(lpost - mx).sum())
        logZ += lse
        logw = lpost - lse
    return {"q": q, "Er": Er, "p_recent": prec, "logZ": logZ, "posts": posts}


def steps_from(onehot: np.ndarray, offsets: np.ndarray) -> list[np.ndarray]:
    """Pașii-zi (CSR) dintr-un onehot [T, N] float64 și offset-urile [S+1] (exact ca bo649.load_real)."""
    oh = np.asarray(onehot, dtype=np.float64)
    off = np.asarray(offsets, dtype=np.int64)
    return [oh[off[s]:off[s + 1]] for s in range(len(off) - 1)]


def bo_describe(steps: list[np.ndarray], N: int, kappa: int) -> dict:
    """Portul BO DESCRIPTIV: E[r], P(r ≤ 100), posteriorul la ultimul pas. Fără q, bilete, scoruri sau porți."""
    K = len(steps)
    if K == 0:
        raise ValueError("niciun pas în setul de date")
    warm = BO_WARMUP if K > BO_WARMUP else 0
    bo = bocpd(steps, N, kappa, BO_H, BO_M0, keep_post=(K - 1,))
    ks = np.arange(warm, K, dtype=np.int64)
    Er, pr = bo["Er"][ks], bo["p_recent"][ks]
    return {"N": int(N), "kappa": int(kappa), "h": BO_H, "m0": BO_M0, "warmup": int(warm), "n_steps": int(K),
            "n_draws": int(sum(s.shape[0] for s in steps)), "ks": ks, "Er": Er, "p_recent": pr,
            "post_last": bo["posts"][K - 1], "logZ": float(bo["logZ"]),
            "Er_last": float(Er[-1]), "p_recent_last": float(pr[-1]),
            "steps_p_recent_gt_half": int((pr > 0.5).sum()), "label": LABEL}


# ---------------------------------------------------------------------------
# WU — parametrii pistei WU649 + Amendamentul 01 (neschimbați)
# ---------------------------------------------------------------------------
SIGMA = 0.2
H_Q, K_Q = 1.0 / 16.0, 64          # tanh-sinh, 129 noduri
GTOL, MAXIT = 1e-8, 200
ARM_C, ARM_MAX, TAU = 1e-4, 60, 1e-10
WITNESS_STEPS = 400
WITNESS_SEED = [649, 8, 5]


def ts_nodes(h: float, K: int) -> tuple[np.ndarray, np.ndarray]:
    """(log x_k, log pondere_k) pentru x_k = 1/(1+e^{-π sinh t_k}), t_k = k h, |k| ≤ K."""
    t = np.arange(-K, K + 1, dtype=np.float64) * h
    s = math.pi * np.sinh(t)
    logx = -np.logaddexp(0.0, -s)
    log1mx = -np.logaddexp(0.0, s)
    logw = math.log(h * math.pi) + np.log(np.cosh(t)) + logx + log1mx
    return logx, logw


NODES = ts_nodes(H_Q, K_Q)


def _logsumexp(a: np.ndarray, axis: int) -> np.ndarray:
    m = a.max(axis=axis, keepdims=True)
    return (m + np.log(np.exp(a - m).sum(axis=axis, keepdims=True))).squeeze(axis)


def draw_terms(theta: np.ndarray, mem: np.ndarray, nonmem: np.ndarray, nodes=NODES, deriv: bool = True) -> dict:
    """mem: [n,κ] indici membri; nonmem: [n,N] 1.0 pentru ne-membri. Întoarce log P pe extragere
    și, dacă deriv, gradientul și hessiana totale (fără prior). (Copiat literal din wu649.draw_terms.)"""
    logx, logw = nodes
    w = np.exp(theta)
    N = theta.shape[0]
    wn = nonmem * w[None, :]
    Wc = wn.sum(1)                                   # [n]
    r = w[mem] / Wc[:, None]                         # [n,κ]
    rL = r[:, :, None] * logx[None, None, :]         # [n,κ,M]
    om = -np.expm1(rL)                               # 1 - x^r
    la = np.log(om).sum(1) + logw[None, :]           # [n,M]
    logP = _logsumexp(la, 1)                         # [n]
    out = {"logP": logP}
    if not deriv:
        return out
    rho = np.exp(la - logP[:, None])                 # [n,M], Σ_m = 1
    v = np.exp(rL)
    L = logx[None, None, :]
    b = -L * v / om
    c = -(L * L) * v / (om * om)
    Eb = np.einsum("nm,nim->ni", rho, b)
    Ec = np.einsum("nm,nim->ni", rho, c)
    Ebb = np.einsum("nm,nim,njm->nij", rho, b, b)
    e = r * Eb                                       # ∂logP/∂d_i
    Hd = r[:, :, None] * r[:, None, :] * (Ebb - Eb[:, :, None] * Eb[:, None, :])
    idx = np.arange(mem.shape[1])
    Hd[:, idx, idx] += r * r * Ec + r * Eb
    g7 = -e.sum(1)                                   # ∂logP/∂z7, z7 = log Wc
    h7 = -Hd.sum(2)                                  # H_z[i,7]
    h77 = Hd.sum((1, 2))                             # H_z[7,7]
    rho_l = wn / Wc[:, None]                         # [n,N], softmax pe ne-membri
    n = mem.shape[0]
    grad = np.bincount(mem.ravel(), weights=e.ravel(), minlength=N) + (g7[:, None] * rho_l).sum(0)
    flat = (mem[:, :, None] * N + mem[:, None, :]).ravel()
    H = np.bincount(flat, weights=Hd.ravel(), minlength=N * N).reshape(N, N)
    A = np.zeros((n, N))
    A[np.arange(n)[:, None], mem] = h7
    C = A.T @ rho_l
    H += C + C.T
    H += (rho_l * (h77 - g7)[:, None]).T @ rho_l
    H[np.arange(N), np.arange(N)] += (g7[:, None] * rho_l).sum(0)
    out.update({"grad": grad, "H": H})
    return out


def posterior_eval(theta, mem, nonmem, sigma, nodes=NODES, deriv=True) -> dict:
    d = draw_terms(theta, mem, nonmem, nodes, deriv)
    s2 = sigma * sigma
    d["lp"] = float(d["logP"].sum() - (theta @ theta) / (2 * s2))
    if deriv:
        d["g"] = d["grad"] - theta / s2
        d["Hp"] = d["H"] - np.eye(theta.shape[0]) / s2
    return d


def _chol_ok(A: np.ndarray) -> bool:
    try:
        np.linalg.cholesky(A)
        return True
    except np.linalg.LinAlgError:
        return False


def map_fit(mem, nonmem, N: int, sigma: float = SIGMA, theta0=None, nodes=NODES) -> dict:
    """MAP Newton–Levenberg cu backtracking Armijo (Amendamentul 01 WU). Pornire implicită θ=0."""
    theta = np.zeros(N) if theta0 is None else np.array(theta0, dtype=np.float64)
    s2 = sigma * sigma
    ev = posterior_eval(theta, mem, nonmem, sigma, nodes)
    it, fail = 0, ""
    while True:
        gnorm = float(np.abs(ev["g"]).max())
        if gnorm <= GTOL:
            break
        if it >= MAXIT:
            fail = "maxit"
            break
        A = -ev["Hp"]
        mu = 0.0
        if not _chol_ok(A):
            mu = 1e-6 * float(np.abs(ev["Hp"]).max())
            while not _chol_ok(A + mu * np.eye(N)):
                mu *= 2.0
        delta = np.linalg.solve(A + mu * np.eye(N), ev["g"])
        gd = float(ev["g"] @ delta)
        step, acc = 1.0, False
        for _ in range(ARM_MAX):
            th_n = theta + step * delta
            ev_n = posterior_eval(th_n, mem, nonmem, sigma, nodes)
            diff = float((ev_n["logP"] - ev["logP"]).sum() - (th_n @ th_n - theta @ theta) / (2 * s2))
            if diff >= ARM_C * step * gd - TAU:
                acc = True
                break
            step *= 0.5
        if not acc:
            fail = "armijo"
            break
        theta, ev = th_n, ev_n
        it += 1
    gnorm = float(np.abs(ev["g"]).max())
    nd = _chol_ok(-ev["Hp"])
    return {"theta": theta, "iters": it, "gnorm": gnorm, "nd": nd, "cert": bool(gnorm <= GTOL and nd),
            "lp": ev["lp"], "fail": fail}


def inclusion(theta: np.ndarray, kappa: int, nodes=NODES) -> np.ndarray:
    """π_j(w) (substituția v = u^{w_j}); copiat literal. Folosit NUMAI pe fixture-ul martorului (nu pe date de joc)."""
    logx, logw = nodes
    N = theta.shape[0]
    a = np.exp(theta[None, :] - theta[:, None])      # a[j,l] = w_l / w_j
    aL = a[:, :, None] * logx[None, None, :]         # [N,N,M]
    p = -np.expm1(aL)                                # sosit
    s = np.exp(aL)                                   # nesosit
    j = np.arange(N)
    p[j, j, :] = 0.0
    s[j, j, :] = 1.0
    M = logx.shape[0]
    P = np.zeros((N, M, kappa))
    P[:, :, 0] = 1.0
    for l in range(N):
        pl, sl = p[:, l, :][:, :, None], s[:, l, :][:, :, None]
        newP = P * sl
        newP[:, :, 1:] += P[:, :, :-1] * pl
        P = newP
    G = P.sum(-1)                                    # P(N_{-j} ≤ κ-1)
    return G @ np.exp(logw)


def _prep(steps: list[np.ndarray]):
    D = np.concatenate(steps, 0)
    off = np.concatenate([[0], np.cumsum([s.shape[0] for s in steps])]).astype(np.int64)
    mem = np.sort(np.argsort(-D, axis=1, kind="stable")[:, :int(D[0].sum())], axis=1)
    return D, off, mem


def fit_prefix(D, off, mem, k: int, sigma: float, nodes=NODES) -> dict:
    n = int(off[k])
    m = mem[:n]
    nonmem = 1.0 - D[:n]
    f = map_fit(m, nonmem, D.shape[1], sigma, nodes=nodes)
    f["q"] = inclusion(f["theta"], m.shape[1], nodes)
    return f


def wu_fixture(n: int, kappa: int, steps_n: int = WITNESS_STEPS) -> list[np.ndarray]:
    """Generalizarea literală a wu649.fixture_hplus (PROTOCOL_TU3_T7A §5a); pentru (49, 6) coincide exact."""
    rest = list(range(kappa + 2, n + 1))
    R = len(rest)
    out = []
    for i in range(steps_n):
        beta = [kappa + 1] + [rest[((kappa - 1) * i + m) % R] for m in range(kappa - 1)]
        gamma = [rest[(kappa * i + m + R // 2) % R] for m in range(kappa)]
        alpha = list(range(1, kappa + 1))
        for S in (beta, gamma, alpha):
            a = np.zeros((1, n))
            a[0, np.array(S) - 1] = 1.0
            out.append(a)
    return out


def swap_labels(steps, i: int, j: int):
    out = []
    for s in steps:
        t = s.copy()
        t[:, [i - 1, j - 1]] = t[:, [j - 1, i - 1]]
        out.append(t)
    return out


def _full_fit(steps: list[np.ndarray], sigma: float) -> dict:
    """Ca wu649.next_prediction, fără bilete: θ̂, q (fixture), certificat, numărări și π_B (numai pentru egalitate)."""
    D, off, mem = _prep(steps)
    f = fit_prefix(D, off, mem, len(steps), sigma)
    S = np.stack([s.sum(0) for s in steps])
    c = np.vstack((np.zeros((1, S.shape[1])), np.cumsum(S, 0)))[len(steps)]
    return {"theta": f["theta"], "q_fix": f["q"], "cert": f["cert"], "counts": c,
            "pib": (c + 1.0) / (c + 1.0).sum(-1, keepdims=True)}


def wu_witness(n: int, kappa: int, sigma: float = SIGMA) -> dict:
    """Martorul de informație Q5 (fixture construit pentru (n, κ), NU date de joc). Fără bilete (Q6 exclus)."""
    if kappa < 2 or n < kappa + 3:
        return {"applicable": False, "n": int(n), "kappa": int(kappa), "label": LABEL,
                "reason": "pentru κ = 1 cursa Luce depinde numai de numărări: compoziția colegilor nu există, "
                          "martorul nu se aplică"}
    Hp = wu_fixture(n, kappa)
    Hm = swap_labels(Hp, kappa, kappa + 1)
    a, b = _full_fit(Hp, sigma), _full_fit(Hm, sigma)
    order = np.random.default_rng(WITNESS_SEED).permutation(len(Hp))
    c = _full_fit([Hp[i] for i in order], sigma)
    return {"applicable": True, "n": int(n), "kappa": int(kappa), "label": LABEL,
            "balls": [int(kappa), int(kappa + 1)],
            "q_balls_Hplus": [float(a["q_fix"][kappa - 1]), float(a["q_fix"][kappa])],
            "theta_balls_Hplus": [float(a["theta"][kappa - 1]), float(a["theta"][kappa])],
            "counts_first": a["counts"][:kappa + 2].tolist(),
            "max_abs_dq": float(np.abs(a["q_fix"] - b["q_fix"]).max()),
            "order_invariance_max_dq": float(np.abs(a["q_fix"] - c["q_fix"]).max()),
            "same_counts": bool(np.array_equal(a["pib"], b["pib"])),
            "cert": [bool(a["cert"]), bool(b["cert"]), bool(c["cert"])]}


def wu_describe(draws_onehot: np.ndarray, sigma: float = SIGMA) -> dict:
    """Ajustarea DESCRIPTIVĂ θ̂ (MAP) pe toate extragerile; fără π/q, fără bilete, fără clasare."""
    D = np.asarray(draws_onehot, dtype=np.float64)
    if D.shape[0] == 0:
        raise ValueError("nicio extragere")
    kap = int(D[0].sum())
    if not np.all(D.sum(1) == kap):
        raise ValueError("extrageri cu număr diferit de bile")
    D_, _, mem = _prep([D])
    f = map_fit(mem, 1.0 - D_, D.shape[1], sigma)
    freq = D.sum(0)
    return {"N": int(D.shape[1]), "kappa": kap, "sigma": sigma, "n_draws": int(D.shape[0]),
            "theta": f["theta"], "freq": freq, "freq_rel": freq / D.shape[0], "iters": int(f["iters"]),
            "gnorm": float(f["gnorm"]), "nd": bool(f["nd"]), "cert": bool(f["cert"]), "fail": f["fail"],
            "sum_theta": float(f["theta"].sum()), "theta_min": float(f["theta"].min()),
            "theta_max": float(f["theta"].max()), "label": LABEL}


# ---------------------------------------------------------------------------
# Componentele unui joc (P7) și verificarea „numai descriptiv” (P2)
# ---------------------------------------------------------------------------
def components(onehot: np.ndarray, offsets: np.ndarray, n: int, r: int, joker_onehot=None, m=None) -> list[dict]:
    comps = [{"key": "principal", "label": "numerele principale", "N": int(n), "kappa": int(r),
              "onehot": np.asarray(onehot, dtype=np.float64)}]
    if joker_onehot is not None:
        comps.append({"key": "joker", "label": "bila Joker", "N": int(m), "kappa": 1,
                      "onehot": np.asarray(joker_onehot, dtype=np.float64)})
    for c in comps:
        c["offsets"] = np.asarray(offsets, dtype=np.int64)
    return comps


def describe_bo(comps: list[dict]) -> list[dict]:
    return [dict(bo_describe(steps_from(c["onehot"], c["offsets"]), c["N"], c["kappa"]), key=c["key"],
                 component=c["label"]) for c in comps]


def describe_wu(comps: list[dict]) -> list[dict]:
    out = []
    for c in comps:
        out.append({"key": c["key"], "component": c["label"], "fit": wu_describe(c["onehot"]),
                    "witness": wu_witness(c["N"], c["kappa"])})
    return out


def forbidden_keys(obj) -> list[str]:
    """Cheile interzise de P2 găsite (recursiv) într-o ieșire de port."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS:
                found.append(k)
            found += forbidden_keys(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found += forbidden_keys(v)
    return found


# ---------------------------------------------------------------------------
# Testul de identitate (P3) — artefactele originale citite read-only
# ---------------------------------------------------------------------------
def _cmp(name: str, port, ref) -> dict:
    a, b = np.asarray(port), np.asarray(ref)
    row = {"name": name, "shape": list(a.shape)}
    if a.shape != b.shape:
        return dict(row, status="FAIL", why=f"formă {a.shape} ≠ {b.shape}")
    if a.dtype.kind in "biu" and b.dtype.kind in "biu" or a.dtype == bool or b.dtype == bool:
        return dict(row, status="EXACT" if np.array_equal(a, b) else "FAIL")
    a64, b64 = a.astype(np.float64), b.astype(np.float64)
    if np.array_equal(a64, b64):
        return dict(row, status="EXACT", max_abs_diff=0.0)
    d = np.abs(a64 - b64)
    rel = float((d / np.maximum(1.0, np.abs(b64))).max())
    return dict(row, status="NUMERIC" if rel <= TOL else "FAIL", max_abs_diff=float(d.max()), max_scaled_diff=rel)


def _verdict(rows: list[dict]) -> str:
    st = {r["status"] for r in rows}
    if "FAIL" in st or not rows:
        return "FAIL"
    return "IDENTITATE_EXACTA" if st == {"EXACT"} else "IDENTITATE_NUMERICA"


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def identity_bo() -> dict:
    """Portul BO pe 6/49 înghețat (pașii exact ca bo649.load_real) vs PREDICTII.npz / REZULTATE.json."""
    if str(QL) not in sys.path:
        sys.path.insert(0, str(QL))
    import parser as P  # ingestia QL649 (nu este model)
    ds = P.build_dataset(device="cpu")
    steps = steps_from(ds.onehot.numpy().astype(np.float64), ds.step_offsets.numpy())
    d = bo_describe(steps, 49, 6)
    res = json.loads((BO_REF / "REZULTATE.json").read_text(encoding="utf-8"))
    npz_p = BO_REF / "PREDICTII.npz"
    ref = np.load(npz_p)
    rows = [_cmp("source_sha256", ds.source_sha256 == res["start"]["source_sha256"], True),
            _cmp("predictions_sha256", _sha(npz_p) == res["predictions_sha256"], True),
            _cmp("ks", d["ks"], ref["ks"]), _cmp("Er", d["Er"], ref["Er"]),
            _cmp("p_recent", d["p_recent"], ref["p_recent"]), _cmp("post_last", d["post_last"], ref["post_last"]),
            _cmp("logZ", d["logZ"], ref["logZ"]),
            _cmp("n_steps_predicted", len(d["ks"]), res["n_steps_predicted"]),
            _cmp("Er.min", float(d["Er"].min()), res["Er"]["min"]),
            _cmp("Er.median", float(np.median(d["Er"])), res["Er"]["median"]),
            _cmp("Er.max", float(d["Er"].max()), res["Er"]["max"]), _cmp("Er.last", d["Er_last"], res["Er"]["last"]),
            _cmp("steps_p_recent_gt_half", d["steps_p_recent_gt_half"], res["steps_p_recent_gt_half"])]
    return {"port": "BO", "verdict": _verdict(rows), "rows": rows, "source_sha256": ds.source_sha256,
            "n_steps": d["n_steps"], "n_draws": d["n_draws"],
            "reference": {"REZULTATE.json": _sha(BO_REF / "REZULTATE.json"), "PREDICTII.npz": _sha(npz_p)},
            "env_threads": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
            "scores_recomputed": False}


def identity_wu() -> dict:
    """Martorul portat pe (49, 6) vs wu649/rezultate/CALIFICARE.json Q5 `detail`."""
    q = json.loads(WU_REF.read_text(encoding="utf-8"))
    q5 = next(c for c in q["checks"] if c["id"] == "Q5")["detail"]
    w = wu_witness(49, 6)
    rows = [_cmp("q6_q7_Hplus", w["q_balls_Hplus"], q5["q6_q7_Hplus"]),
            _cmp("theta6_theta7_Hplus", w["theta_balls_Hplus"], q5["theta6_theta7_Hplus"]),
            _cmp("counts_1_8", w["counts_first"], q5["counts_1_8"]),
            _cmp("max_abs_dq_WU", w["max_abs_dq"], q5["max_abs_dq_WU"]),
            _cmp("order_invariance_max_dq", w["order_invariance_max_dq"], q5["order_invariance_max_dq"]),
            _cmp("B_identical", w["same_counts"], q5["B_identical"]), _cmp("cert", w["cert"], q5["cert"])]
    return {"port": "WU", "verdict": _verdict(rows), "rows": rows, "reference": {"CALIFICARE.json": _sha(WU_REF)},
            "env_threads": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
            "tickets_recomputed": False}


def _run_sub(which: str, single_thread: bool) -> dict:
    env = dict(os.environ)
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        if single_thread:
            env[v] = "1"
        else:
            env.pop(v, None)
    p = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--identitate", which], env=env,
                       capture_output=True, text=True, timeout=3600)
    if p.returncode not in (0, 1):
        raise RuntimeError(f"identitate {which}: cod {p.returncode}: {p.stderr[-2000:]}")
    return json.loads(p.stdout)


def write_identity(out_dir: Path = OUT_DIR) -> Path:
    bo, wu = _run_sub("bo", False), _run_sub("wu", True)
    now = dt.datetime.now(dt.timezone.utc)
    rep = {"protocol": "TU3-T7A", "protocol_sha256": _sha(PROTOCOL), "code_sha256": _sha(Path(__file__)),
           "written_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "tolerance": TOL, "BO": bo, "WU": wu,
           "verdict": "PASS" if "FAIL" not in (bo["verdict"], wu["verdict"]) else "FAIL",
           "note": "Identitatea compară numai mărimi descriptive; scorurile, porțile, biletele și verdictele pistelor "
                   "6/49 nu sunt recalculate și nu se transferă. positive_claims_allowed=false.",
           "positive_claims_allowed": False}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"IDENTITATE_T7A_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(dst, "x", encoding="utf-8") as f:
        f.write(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    os.chmod(dst, 0o444)
    return dst


def latest_identity(out_dir: Path = OUT_DIR) -> dict | None:
    fs = sorted(Path(out_dir).glob("IDENTITATE_T7A_*.json")) if Path(out_dir).is_dir() else []
    if not fs:
        return None
    try:
        d = json.loads(fs[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {"file": fs[-1].name, "verdict": d.get("verdict"), "BO": (d.get("BO") or {}).get("verdict"),
            "WU": (d.get("WU") or {}).get("verdict")}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--identitate"] and len(argv) >= 2:
        if argv[1] == "bo":
            r = identity_bo()
        elif argv[1] == "wu":
            r = identity_wu()
        elif argv[1] == "toate":
            out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else OUT_DIR
            dst = write_identity(out)
            print(dst, _sha(dst))
            return 0 if json.loads(dst.read_text())["verdict"] == "PASS" else 1
        else:
            print(__doc__)
            return 2
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["verdict"] != "FAIL" else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
