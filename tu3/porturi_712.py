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

TU3-T7B (PROTOCOL_TU3_T7B.md, sigilat în SIGILIU_TU3_T7B.json ÎNAINTE de codul T7B; numai inserții în acest fișier):
porturile DESCRIPTIVE GL (tab 9, `gl649/gl649.py`) și SE (tab 10, `se649/se649.py`), copiate literal, aritmetica
pistelor păstrată (exact în Q cu fractions.Fraction + NumPy float64 pentru conversie și statistica G), pe CPU.
  python -B tu3/porturi_712.py --identitate gl|se            # JSON pe stdout
  python -B tu3/porturi_712.py --identitate t7b --out tu3/rezultate/T7B    # două subprocese, raport 0444

TU3-T7C (PROTOCOL_TU3_T7C.md, sigilat în SIGILIU_TU3_T7C.json ÎNAINTE de codul T7C; numai inserții în acest fișier):
porturile DESCRIPTIVE CS (tab 11, `cs649/cs649.py`; exact în Q cu fractions.Fraction + NumPy float64) și PL (tab 12,
`pl649/pl_core.py` + `pl649/pl649.py`; NumPy complex128/float64 pe CPU în loc de PyTorch CUDA, impulsurile SU(3) în
forma închisă a pistei), copiate literal; fără p̂, legi, bilete, variante, scoruri.
  python -B tu3/porturi_712.py --identitate cs|pl            # JSON pe stdout
  python -B tu3/porturi_712.py --identitate t7c --out tu3/rezultate/T7C    # două subprocese, raport 0444
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import subprocess
import sys
from fractions import Fraction  # TU3-T7B (inserție): aritmetica exactă a pistelor GL/SE
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
        elif argv[1] in ("gl", "se"):  # TU3-T7B (inserție): identitatea GL / SE pe 6/49
            r = identity_gl() if argv[1] == "gl" else identity_se()
        elif argv[1] == "t7b":  # TU3-T7B (inserție): raportul GL + SE (două subprocese, 0444)
            out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else OUT_DIR_T7B
            dst = write_identity_t7b(out)
            print(dst, _sha(dst))
            return 0 if json.loads(dst.read_text())["verdict"] == "PASS" else 1
        elif argv[1] in ("cs", "pl"):  # TU3-T7C (inserție): identitatea CS / PL pe 6/49
            r = identity_cs() if argv[1] == "cs" else identity_pl()
        elif argv[1] == "t7c":  # TU3-T7C (inserție): raportul CS + PL (două subprocese, 0444)
            out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else OUT_DIR_T7C
            dst = write_identity_t7c(out)
            print(dst, _sha(dst))
            return 0 if json.loads(dst.read_text())["verdict"] == "PASS" else 1
        else:
            print(__doc__)
            return 2
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["verdict"] != "FAIL" else 1
    print(__doc__)
    return 2


# ---------------------------------------------------------------------------
# TU3-T7B — porturile DESCRIPTIVE GL (tab 9) și SE (tab 10) (PROTOCOL_TU3_T7B.md; sigilat în SIGILIU_TU3_T7B.json
# ÎNAINTE de acest cod; protocolul comun PROTOCOL_TU3_T7A §3, P1–P8). Algoritmii sunt copiați literal din
# `gl649/gl649.py` (GL649-P1) și `se649/se649.py` (SE649-P1), care NU se importă și NU se execută; constantele 49/6 devin
# (N, κ) prin formele generale care dau EXACT aceleași fracții pentru (49, 6). Aritmetica pistelor e păstrată: exact în
# Q (fractions.Fraction) + NumPy float64 pentru conversie și statistica G (P6, §3.3 T7B), pe CPU. Ieșirile publice NU
# conțin p̂, legi, bilete, top-k, scoruri, porți, verdicte, p-valori sau ranguri față de universuri nule.
# positive_claims_allowed=false.
# ---------------------------------------------------------------------------
PROTOCOL_T7B = HERE / "PROTOCOL_TU3_T7B.md"
OUT_DIR_T7B = HERE / "rezultate" / "T7B"
GL_REF = QL / "gl649" / "rezultate" / "backtest_unic"
SE_REF = QL / "se649" / "rezultate" / "backtest_unic"
NS = 4
SEASON_NAMES = ["iarnă", "primăvară", "vară", "toamnă"]
FORBIDDEN_KEYS_T7B = FORBIDDEN_KEYS | frozenset({"p", "p_hat", "p_GL", "p_SE", "z", "ticket_GL", "ticket_SE", "q_law",
                                                  "law", "rank", "p_value", "pvalue", "null_rank", "by_target_season",
                                                  "hits_GL", "hits_SE"})


def forbidden_keys_t7b(obj) -> list[str]:
    """Cheile interzise (P2, lista extinsă T7B) găsite recursiv într-o ieșire de port."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS_T7B:
                found.append(k)
            found += forbidden_keys_t7b(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found += forbidden_keys_t7b(v)
    return found


def solve_exact(A: list[list[Fraction]], B: list[list[Fraction]]) -> list[list[Fraction]]:
    """Rezolvă A X = B exact (A pătrată nesingulară), eliminare Bareiss (copiată literal din gl649.solve_exact)."""
    n = len(A)
    m = len(B[0])
    rows = []
    for i in range(n):
        r = [Fraction(x) for x in A[i]] + [Fraction(x) for x in B[i]]
        L = 1
        for x in r:
            L = L * x.denominator // math.gcd(L, x.denominator)
        rows.append([int(x * L) for x in r])
    prev = 1
    for k in range(n):
        piv = next((i for i in range(k, n) if rows[i][k] != 0), None)
        if piv is None:
            raise ZeroDivisionError("matrice singulară")
        if piv != k:
            rows[k], rows[piv] = rows[piv], rows[k]
        rk = rows[k]
        akk = rk[k]
        for i in range(k + 1, n):
            ri = rows[i]
            aik = ri[k]
            rows[i] = [(akk * ri[j] - aik * rk[j]) // prev if j > k else 0 for j in range(n + m)]
        prev = akk
    X = [[Fraction(0)] * m for _ in range(n)]
    for c in range(m):
        for i in range(n - 1, -1, -1):
            s = Fraction(rows[i][n + c])
            for j in range(i + 1, n):
                if rows[i][j]:
                    s -= rows[i][j] * X[j][c]
            X[i][c] = s / rows[i][i]
    return X


def _counts_upto(steps: list[np.ndarray], N: int, upto: int | None = None) -> tuple[list[int], int]:
    """Numărările și numărul de extrageri din pașii < upto (toți pașii dacă upto este None)."""
    sel = steps if upto is None else steps[:upto]
    c = np.zeros(N, dtype=np.int64)
    nd = 0
    for s in sel:
        c += s.sum(0).astype(np.int64)
        nd += int(s.shape[0])
    return [int(t) for t in c], nd


# ---------------- GL (tab 9) — parametrii relativi ai pistei GL649 (neschimbați) ----------------
def gl_constants(N: int, kappa: int) -> dict:
    """p0 = κ/N, s_g² = (p0/10)², s_e² = (p0/20)², σ0² = p0(1−p0)·N/(N−1) — pentru (49, 6): 9/60025, 9/240100, 43/392."""
    p0 = Fraction(int(kappa), int(N))
    return {"p0": p0, "sg2": p0 * p0 / 100, "se2": p0 * p0 / 400, "sigma0_2": p0 * (1 - p0) * Fraction(N, N - 1)}


_GL_STRUCT: dict = {}


def gl_structure(N: int) -> dict:
    """Incidența glifelor G (N×10) din scrierea zecimală a etichetelor 1..N (a priori), H = PG și HᵀH, exact în Q."""
    N = int(N)
    if N not in _GL_STRUCT:
        G = [[0] * 10 for _ in range(N)]
        for j in range(1, N + 1):
            for ch in str(j):
                G[j - 1][int(ch)] += 1
        colsum = [sum(G[j][d] for j in range(N)) for d in range(10)]
        H = [[Fraction(G[j][d]) - Fraction(colsum[d], N) for d in range(10)] for j in range(N)]
        HTH = [[sum(Fraction(G[j][d] * G[j][e]) for j in range(N)) - Fraction(colsum[d] * colsum[e], N)
                for e in range(10)] for d in range(10)]
        _GL_STRUCT[N] = {"G": G, "colsum": colsum, "H": H, "HTH": HTH}
    return _GL_STRUCT[N]


def gl_core(v: list[Fraction], nu: Fraction, N: int, sg2: Fraction, se2: Fraction) -> list[Fraction]:
    """z = (PKP + νP)^+ v pentru v ⟂ 1, prin Woodbury (literal gl649.gl_core)."""
    S = gl_structure(N)
    G, H, HTH = S["G"], S["H"], S["HTH"]
    a = se2 + nu
    Htv = [sum(G[j][d] * v[j] for j in range(N) if G[j][d]) for d in range(10)]
    M = [[HTH[d][e] + (a / sg2 if d == e else 0) for e in range(10)] for d in range(10)]
    y = [r[0] for r in solve_exact(M, [[t] for t in Htv])]
    return [(v[j] - sum(H[j][d] * y[d] for d in range(10))) / a for j in range(N)]


def gl_predict_counts(c, n: int, N: int, kappa: int) -> dict:
    """Literal gl649.gl_predict_counts în (N, κ). INTERN (certificate): p̂ și z NU se expun în ieșirile publice."""
    K = gl_constants(N, kappa)
    H = gl_structure(N)["H"]
    c = [int(x) for x in c]
    assert sum(c) == kappa * n and n > 0
    x = [Fraction(cj, n) for cj in c]
    v = [xj - K["p0"] for xj in x]
    nu = K["sigma0_2"] / n
    z = gl_core(v, nu, N, K["sg2"], K["se2"])
    p = [x[j] - nu * z[j] for j in range(N)]
    gamma = [K["sg2"] * sum(H[j][d] * z[j] for j in range(N)) for d in range(10)]
    return {"p": p, "z": z, "gamma": gamma, "nu": nu}


def gl_predict_direct(c, n: int, N: int, kappa: int) -> list[Fraction]:
    """Rezolvarea directă exactă N×N (PKP + νP + J) w = v; p̂ = p0 + PKP w (literal gl649, Q1.1). INTERN (certificat)."""
    K = gl_constants(N, kappa)
    H = gl_structure(N)["H"]
    PKP = [[K["se2"] * ((1 if i == j else 0) - Fraction(1, N)) + K["sg2"] * sum(H[i][d] * H[j][d] for d in range(10))
            for j in range(N)] for i in range(N)]
    nu = K["sigma0_2"] / n
    v = [Fraction(int(cj), n) - K["p0"] for cj in c]
    A = [[PKP[i][j] + nu * ((1 if i == j else 0) - Fraction(1, N)) + 1 for j in range(N)] for i in range(N)]
    w = [r[0] for r in solve_exact(A, [[t] for t in v])]
    return [K["p0"] + sum(PKP[i][j] * w[j] for j in range(N)) for i in range(N)]


def gl_describe(counts, n: int, N: int, kappa: int) -> dict:
    """Portul GL DESCRIPTIV: efectele de glifă ajustate γ̂/p0 și frecvența observată a glifelor. Fără p̂, bilete, scor."""
    K = gl_constants(N, kappa)
    S = gl_structure(N)
    r = gl_predict_counts(counts, n, N, kappa)
    c = [int(x) for x in counts]
    gc = [sum(S["G"][j][d] * c[j] for j in range(N)) for d in range(10)]
    exp_ = [Fraction(int(kappa) * int(n) * S["colsum"][d], N) for d in range(10)]
    gamma_rel = [float(g) / float(K["p0"]) for g in r["gamma"]]
    return {"N": int(N), "kappa": int(kappa), "n_draws": int(n), "gamma_rel": gamma_rel,
            "gamma_rel_min": min(gamma_rel), "gamma_rel_max": max(gamma_rel),
            "glyph_labels": [sum(1 for j in range(N) if S["G"][j][d]) for d in range(10)],
            "glyph_freq_rel": [float(Fraction(gc[d]) / exp_[d] - 1) if exp_[d] else float("nan") for d in range(10)],
            "sum_exact_ok": bool(sum(r["p"]) == kappa), "z_perp_ok": bool(sum(r["z"]) == 0),
            "hyper": {"s_g2": str(K["sg2"]), "s_e2": str(K["se2"]), "sigma0_2": str(K["sigma0_2"])}, "label": LABEL}


def gl_describe_steps(steps: list[np.ndarray], N: int, kappa: int, upto: int | None = None) -> dict:
    c, nd = _counts_upto(steps, N, upto)
    if nd == 0:
        raise ValueError("nicio extragere în istorie")
    return dict(gl_describe(c, nd, N, kappa), n_steps_used=len(steps) if upto is None else int(upto))


def describe_gl(comps: list[dict]) -> list[dict]:
    return [dict(gl_describe_steps(steps_from(c["onehot"], c["offsets"]), c["N"], c["kappa"]), key=c["key"],
                 component=c["label"]) for c in comps]


# ---------------- SE (tab 10) — parametrii relativi ai pistei SE649 (neschimbați) ----------------
def se_constants(N: int, kappa: int) -> dict:
    """p0 = κ/N, τa² = (p0/20)², τb² = (p0/5)², σ0² = p0(1−p0)·N/(N−1) — pentru (49, 6): 9/240100, 36/60025, 43/392."""
    p0 = Fraction(int(kappa), int(N))
    return {"p0": p0, "ta2": p0 * p0 / 400, "tb2": p0 * p0 / 25, "sigma0_2": p0 * (1 - p0) * Fraction(N, N - 1)}


def season_of(date_str: str) -> int:
    """Anotimp meteorologic (SE649 §0): 0 iarnă (dec–feb), 1 primăvară, 2 vară, 3 toamnă (literal)."""
    m = dt.date.fromisoformat(date_str).month
    return (m % 12) // 3


def se_weights(ns, phi: int, ta2: Fraction, tb2: Fraction, sigma0_2: Fraction) -> dict[int, Fraction]:
    """Ponderile w_φ în formă închisă (Sherman–Morrison), pentru anotimpurile observate O (literal se649.se_weights)."""
    O = [f for f in range(NS) if ns[f] > 0]
    assert O, "nicio extragere în istorie"
    nu = {f: sigma0_2 / int(ns[f]) for f in O}
    D = {f: tb2 + nu[f] for f in O}
    S = sum(1 / D[f] for f in O)
    kappa = ta2 / (1 + ta2 * S)
    if phi in O:
        fac = nu[phi] / D[phi]
        return {f: kappa * fac / D[f] + (tb2 / D[phi] if f == phi else 0) for f in O}
    return {f: kappa / D[f] for f in O}


def se_weights_direct(ns, phi: int, ta2: Fraction, tb2: Fraction, sigma0_2: Fraction) -> dict[int, Fraction]:
    """Rezolvarea directă exactă a sistemului |O|×|O| Σ_d w = s (literal se649, Q1.1). INTERN (certificat)."""
    O = [f for f in range(NS) if ns[f] > 0]
    A = [[ta2 + ((tb2 + sigma0_2 / int(ns[f])) if f == g else 0) for g in O] for f in O]
    s = [[ta2 + (tb2 if f == phi else 0)] for f in O]
    w = solve_exact(A, s)
    return {f: w[i][0] for i, f in enumerate(O)}


def se_predict_counts(C4, ns, phi: int, N: int, kappa: int, direct: bool = False) -> dict:
    """Literal se649.se_predict_counts în (N, κ). INTERN (certificate): p̂ NU se expune în ieșirile publice."""
    K = se_constants(N, kappa)
    ns = [int(x) for x in ns]
    for f in range(NS):
        assert sum(int(t) for t in C4[f]) == kappa * ns[f]
    w = (se_weights_direct if direct else se_weights)(ns, phi, K["ta2"], K["tb2"], K["sigma0_2"])
    p = []
    for j in range(N):
        v = K["p0"]
        for f, wf in w.items():
            v += wf * (Fraction(int(C4[f][j]), ns[f]) - K["p0"])
        p.append(v)
    return {"p": p, "w": w}


def season_prefix(steps: list[np.ndarray], seasons: np.ndarray, N: int) -> tuple[np.ndarray, np.ndarray]:
    """C4[k] (4×N), N4[k] (4): numărări / extrageri pe anotimpuri din pașii < k (literal se649.season_prefix)."""
    K = len(steps)
    C4 = np.zeros((K + 1, NS, N), dtype=np.int64)
    N4 = np.zeros((K + 1, NS), dtype=np.int64)
    for s in range(K):
        C4[s + 1] = C4[s]
        N4[s + 1] = N4[s]
        C4[s + 1, seasons[s]] += steps[s].sum(0).astype(np.int64)
        N4[s + 1, seasons[s]] += steps[s].shape[0]
    return C4, N4


def g_statistic(steps: list[np.ndarray], seasons: np.ndarray, N: int, kappa: int) -> float:
    """G = 2 Σ c_{jφ} ln(c_{jφ} / (κ n_φ / N)) pe întreaga istorie (literal se649.g_statistic). Fără p-valoare."""
    C4, N4 = season_prefix(steps, seasons, N)
    c, n = C4[-1].astype(float), N4[-1].astype(float)
    e = float(kappa) * n[:, None] / N
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(c > 0, c * np.log(c / e), 0.0)
    return float(2.0 * t.sum())


def se_describe(steps: list[np.ndarray], dates: list[str], N: int, kappa: int) -> dict:
    """Portul SE DESCRIPTIV: n_φ, ponderile w_φ ale modelului (istoria completă), statistica G, frecvențele pe anotimp."""
    if len(dates) != len(steps):
        raise ValueError(f"{len(dates)} date ≠ {len(steps)} pași")
    if not steps:
        raise ValueError("niciun pas în setul de date")
    K = se_constants(N, kappa)
    seasons = np.array([season_of(d) for d in dates], dtype=np.int64)
    C4, N4 = season_prefix(steps, seasons, N)
    kf = len(steps)
    n4 = N4[kf]
    W = {f: se_weights(n4, f, K["ta2"], K["tb2"], K["sigma0_2"]) for f in range(NS)}
    p0f = float(K["p0"])
    c = C4[kf].astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        fr = np.where(n4[:, None] > 0, c / (n4[:, None].astype(float) * p0f) - 1.0, np.nan)
    return {"N": int(N), "kappa": int(kappa), "n_steps": int(kf), "n_draws": int(n4.sum()),
            "n_per_season": n4.tolist(), "season_names": SEASON_NAMES,
            "weights_by_target_season": {SEASON_NAMES[f]: {SEASON_NAMES[g]: float(w) for g, w in W[f].items()}
                                         for f in range(NS)},
            "wsum_lt1_ok": bool(all(sum(W[f].values()) < 1 for f in range(NS))),
            "weights_sum": {SEASON_NAMES[f]: float(sum(W[f].values())) for f in range(NS)},
            "G": g_statistic(steps, seasons, N, kappa), "freq_rel_season": fr.T.tolist(),
            "hyper": {"tau_a2": str(K["ta2"]), "tau_b2": str(K["tb2"]), "sigma0_2": str(K["sigma0_2"])},
            "label": LABEL}


def describe_se(comps: list[dict], dates: list[str]) -> list[dict]:
    return [dict(se_describe(steps_from(c["onehot"], c["offsets"]), list(dates), c["N"], c["kappa"]), key=c["key"],
                 component=c["label"]) for c in comps]


# ---------------- Identitatea T7B (P3) — artefactele originale citite read-only ----------------
def _frozen_649():
    if str(QL) not in sys.path:
        sys.path.insert(0, str(QL))
    import parser as P  # ingestia QL649 (nu este model)
    ds = P.build_dataset(device="cpu")
    return ds, steps_from(ds.onehot.numpy().astype(np.float64), ds.step_offsets.numpy())


def identity_gl() -> dict:
    """Portul GL pe 6/49 înghețat, la ultimul pas prezis de pistă (pașii < K−1) vs REZULTATE.json / PREDICTII.npz."""
    ds, steps = _frozen_649()
    K = len(steps)
    d = gl_describe_steps(steps, 49, 6, upto=K - 1)
    res = json.loads((GL_REF / "REZULTATE.json").read_text(encoding="utf-8"))
    npz_p = GL_REF / "PREDICTII.npz"
    ref = np.load(npz_p)
    rows = [_cmp("source_sha256", ds.source_sha256 == res["start"]["source_sha256"], True),
            _cmp("predictions_sha256", _sha(npz_p) == res["predictions_sha256"], True),
            _cmp("gamma_last_relative", d["gamma_rel"], res["gamma_last_relative"]),
            _cmp("step_last", K - 1, int(ref["ks"][-1])),
            _cmp("n_draws_last", d["n_draws"], int(ref["n_draws"][-1])),
            _cmp("sum_exact_ok", d["sum_exact_ok"], True), _cmp("z_perp_ok", d["z_perp_ok"], True),
            _cmp("hyper_49_6", [d["hyper"]["s_g2"], d["hyper"]["s_e2"], d["hyper"]["sigma0_2"]] ==
                 [res["start"]["config"]["s_g2"], res["start"]["config"]["s_e2"], res["start"]["config"]["sigma0_2"]],
                 True)]
    return {"port": "GL", "verdict": _verdict(rows), "rows": rows, "source_sha256": ds.source_sha256,
            "n_steps": K, "step_compared": K - 1, "n_draws_compared": d["n_draws"],
            "reference": {"REZULTATE.json": _sha(GL_REF / "REZULTATE.json"), "PREDICTII.npz": _sha(npz_p)},
            "scores_recomputed": False}


def identity_se() -> dict:
    """Portul SE pe 6/49 înghețat (istoria completă) vs REZULTATE.json `final_state` și `G_label_x_season`."""
    ds, steps = _frozen_649()
    d = se_describe(steps, list(ds.step_dates), 49, 6)
    res = json.loads((SE_REF / "REZULTATE.json").read_text(encoding="utf-8"))
    fs = res["final_state"]
    rw, pw = fs["weights_by_target_season"], d["weights_by_target_season"]
    same_keys = list(rw) == list(pw) and all(list(rw[f]) == list(pw[f]) for f in rw)
    rows = [_cmp("source_sha256", ds.source_sha256 == res["start"]["source_sha256"], True),
            _cmp("predictions_sha256", _sha(SE_REF / "PREDICTII.npz") == res["predictions_sha256"], True),
            _cmp("n_per_season", d["n_per_season"], fs["n_per_season"]),
            _cmp("weights_keys", same_keys, True)]
    if same_keys:
        rows.append(_cmp("weights_by_target_season", [pw[f][g] for f in rw for g in rw[f]],
                         [rw[f][g] for f in rw for g in rw[f]]))
    rows += [_cmp("G_label_x_season", d["G"], res["G_label_x_season"]),
             _cmp("wsum_lt1_ok", d["wsum_lt1_ok"], True),
             _cmp("hyper_49_6", [d["hyper"]["tau_a2"], d["hyper"]["tau_b2"], d["hyper"]["sigma0_2"]] ==
                  [res["start"]["config"]["tau_a2"], res["start"]["config"]["tau_b2"],
                   res["start"]["config"]["sigma0_2"]], True)]
    return {"port": "SE", "verdict": _verdict(rows), "rows": rows, "source_sha256": ds.source_sha256,
            "n_steps": d["n_steps"], "n_draws": d["n_draws"],
            "reference": {"REZULTATE.json": _sha(SE_REF / "REZULTATE.json"),
                          "PREDICTII.npz": _sha(SE_REF / "PREDICTII.npz")},
            "scores_recomputed": False}


def write_identity_t7b(out_dir: Path = OUT_DIR_T7B) -> Path:
    gl, se = _run_sub("gl", False), _run_sub("se", False)
    now = dt.datetime.now(dt.timezone.utc)
    rep = {"protocol": "TU3-T7B", "protocol_sha256": _sha(PROTOCOL_T7B), "code_sha256": _sha(Path(__file__)),
           "written_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "tolerance": TOL, "GL": gl, "SE": se,
           "verdict": "PASS" if "FAIL" not in (gl["verdict"], se["verdict"]) else "FAIL",
           "note": "Identitatea compară numai mărimi descriptive (γ̂/p0 la ultimul pas; n_φ, ponderile w_φ, statistica "
                   "G); p̂, scorurile, porțile, biletele și verdictele pistelor 6/49 nu sunt recalculate și nu se "
                   "transferă. positive_claims_allowed=false.",
           "positive_claims_allowed": False}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"IDENTITATE_T7B_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(dst, "x", encoding="utf-8") as f:
        f.write(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    os.chmod(dst, 0o444)
    return dst


def latest_identity_t7b(out_dir: Path = OUT_DIR_T7B) -> dict | None:
    fs = sorted(Path(out_dir).glob("IDENTITATE_T7B_*.json")) if Path(out_dir).is_dir() else []
    if not fs:
        return None
    try:
        d = json.loads(fs[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {"file": fs[-1].name, "verdict": d.get("verdict"), "GL": (d.get("GL") or {}).get("verdict"),
            "SE": (d.get("SE") or {}).get("verdict")}


# ---------------------------------------------------------------------------
# TU3-T7C — porturile DESCRIPTIVE CS (tab 11) și PL (tab 12) (PROTOCOL_TU3_T7C.md; sigilat în SIGILIU_TU3_T7C.json
# ÎNAINTE de acest cod; protocolul comun PROTOCOL_TU3_T7A §3, P1–P8). Algoritmii sunt copiați literal din
# `cs649/cs649.py` (CS649-P1) și `pl649/pl_core.py` + `pl649/pl649.py` (PL649-P1), care NU se importă și NU se execută;
# constantele 49/6 devin (N, κ) prin formele generale care dau EXACT aceleași valori pentru (49, 6). CS: exact în Q
# (fractions.Fraction) + NumPy float64 (aritmetica pistei). PL: NumPy complex128/float64 pe CPU (pista: PyTorch CUDA),
# impulsurile exp(iελ) în forma închisă a pistei (`pl649._exp_closed`, referința Q1) — §3.3 T7C. Ieșirile publice NU
# conțin p̂, legi π/q, z, bilete, variante, energii QUBO, scoruri, porți, verdicte, p-valori, comparații cu universuri
# nule sau clasări. positive_claims_allowed=false.
# ---------------------------------------------------------------------------
PROTOCOL_T7C = HERE / "PROTOCOL_TU3_T7C.md"
OUT_DIR_T7C = HERE / "rezultate" / "T7C"
CS_REF = QL / "cs649" / "rezultate" / "backtest_unic"
PL_RES = QL / "pl649" / "rezultate"
FORBIDDEN_KEYS_T7C = FORBIDDEN_KEYS_T7B | frozenset({"p_CS", "p_PL", "ticket_CS", "ticket_PL", "variants", "E_min",
                                                     "E_second", "E_base", "qubo", "annealer", "monopoles_xy",
                                                     "planck_area_z", "planck_area_deviancy", "planck_area_null_mean",
                                                     "planck_area_null_sd", "rel_dev_std", "rel_dev_min", "rel_dev_max",
                                                     "by_target_phase", "hits_CS", "hits_PL", "hits_PI6", "xyz",
                                                     "spectral_layout"})


def forbidden_keys_t7c(obj) -> list[str]:
    """Cheile interzise (P2, lista extinsă T7C) găsite recursiv într-o ieșire de port."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS_T7C:
                found.append(k)
            found += forbidden_keys_t7c(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found += forbidden_keys_t7c(v)
    return found


# ---------------- CS (tab 11) — parametrii relativi ai pistei CS649 (neschimbați) ----------------
CS_PERIODS = (3, 5, 7)
CS_OFFS = {3: 1, 5: 4, 7: 9}          # nivelul 0 = a; (K, r) -> CS_OFFS[K] + r (literal cs649.OFFS)
CS_NL = 16


def cs_constants(N: int, kappa: int) -> dict:
    """p0 = κ/N, τa² = (p0/20)², τ² = (p0/4)², σ0² = p0(1−p0)·N/(N−1) — pentru (49, 6): 9/240100, 9/9604, 43/392."""
    p0 = Fraction(int(kappa), int(N))
    return {"p0": p0, "ta2": p0 * p0 / 400, "t2": p0 * p0 / 16, "sigma0_2": p0 * (1 - p0) * Fraction(N, N - 1)}


def cs_levels_of(k: int) -> list[int]:
    """Nivelurile de incidență ale pasului k: a și (K, k mod K) pentru K ∈ {3, 5, 7} (literal cs649.levels_of)."""
    return [0] + [CS_OFFS[K] + (k % K) for K in CS_PERIODS]


def cs_zstar(k: int) -> list[int]:
    z = [0] * CS_NL
    for lv in cs_levels_of(k):
        z[lv] = 1
    return z


def cs_level_name(lv: int) -> str:
    if lv == 0:
        return "a"
    for K in CS_PERIODS:
        if CS_OFFS[K] <= lv < CS_OFFS[K] + K:
            return f"K{K}r{lv - CS_OFFS[K]}"
    raise ValueError(lv)


def cs_new_state(N: int) -> dict:
    return {"NN": np.zeros((CS_NL, CS_NL), dtype=np.int64), "C": np.zeros((CS_NL, int(N)), dtype=np.int64)}


def cs_add_step(st: dict, k: int, draws: np.ndarray) -> None:
    """Literal cs649.State.add_step: NN = ZᵀZ, C = numărări pe niveluri (întregi)."""
    lv = cs_levels_of(k)
    nd = int(draws.shape[0])
    cnt = draws.sum(0).astype(np.int64)
    for l1 in lv:
        st["C"][l1] += cnt
        for l2 in lv:
            st["NN"][l1, l2] += nd


def cs_state(steps: list[np.ndarray], N: int, upto: int | None = None) -> dict:
    st = cs_new_state(N)
    for k, d in enumerate(steps if upto is None else steps[:upto]):
        cs_add_step(st, k, d)
    return st


def cs_solve_gauss_jordan(A: list[list[Fraction]], b: list[Fraction]) -> list[Fraction]:
    """A doua implementare exactă (literal cs649.solve_gauss_jordan; folosită de certificatul C4)."""
    n = len(A)
    M = [[Fraction(x) for x in A[i]] + [Fraction(b[i])] for i in range(n)]
    for c in range(n):
        piv = next(i for i in range(c, n) if M[i][c] != 0)
        M[c], M[piv] = M[piv], M[c]
        inv = 1 / M[c][c]
        M[c] = [x * inv for x in M[c]]
        for i in range(n):
            if i != c and M[i][c] != 0:
                f = M[i][c]
                M[i] = [x - f * y for x, y in zip(M[i], M[c])]
    return [M[i][n] for i in range(n)]


def cs_v(st: dict, kstar: int, N: int, kappa: int, method: str = "bareiss") -> dict:
    """Literal cs649.henderson_M + cs_predict_state în (N, κ): v = M⁻¹ z*, exact în Q. p̂ INTERN (control Σ p̂ = κ)."""
    K = cs_constants(N, kappa)
    ginv = [K["sigma0_2"] / K["ta2"]] + [K["sigma0_2"] / K["t2"]] * (CS_NL - 1)
    NN = st["NN"]
    M = [[Fraction(int(NN[i, j])) + (ginv[i] if i == j else 0) for j in range(CS_NL)] for i in range(CS_NL)]
    z = cs_zstar(kstar)
    if method == "bareiss":
        v = [x[0] for x in solve_exact(M, [[Fraction(t)] for t in z])]
    else:
        v = cs_solve_gauss_jordan(M, [Fraction(t) for t in z])
    den = 1
    for x in v:
        den = den * x.denominator // math.gcd(den, x.denominator)
    V = [int(x * den) for x in v]
    nl = [int(NN[lv, lv]) for lv in range(CS_NL)]
    T = Fraction(sum(V[lv] * nl[lv] for lv in range(CS_NL)), den)
    base = K["p0"] * (1 - T)
    p = [base + Fraction(sum(V[lv] * int(st["C"][lv, j]) for lv in range(CS_NL)), den) for j in range(int(N))]
    return {"v": v, "p": p}


def cs_g(st: dict, N: int, kappa: int) -> dict:
    """G_K = 2 Σ c ln(c / (κ n_{Kr}/N)) pe tabelele etichetă × fază (literal cs649.g_statistics). Fără p-valoare."""
    out = {}
    for K in CS_PERIODS:
        lv = [CS_OFFS[K] + r for r in range(K)]
        c = st["C"][lv].astype(float)
        n = np.array([st["NN"][q, q] for q in lv], dtype=float)
        e = float(kappa) * n[:, None] / N
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(c > 0, c * np.log(c / e), 0.0)
        out[f"G{K}"] = float(2.0 * t.sum())
    out["G_sum"] = out["G3"] + out["G5"] + out["G7"]
    return out


def cs_describe(steps: list[np.ndarray], N: int, kappa: int) -> dict:
    """Portul CS DESCRIPTIV: n pe niveluri, ponderile v (indicele K), statisticile G, frecvențele pe fază. Fără p̂."""
    if not steps:
        raise ValueError("niciun pas în setul de date")
    K = cs_constants(N, kappa)
    st = cs_state(steps, N)
    kf = len(steps)
    r = cs_v(st, kf, N, kappa)
    g = cs_g(st, N, kappa)
    n_lv = [int(st["NN"][lv, lv]) for lv in range(CS_NL)]
    p0f = float(K["p0"])
    fr = []
    for lv in range(1, CS_NL):
        c = st["C"][lv].astype(float)
        fr.append((c / (n_lv[lv] * p0f) - 1.0).tolist() if n_lv[lv] > 0 else [float("nan")] * int(N))
    return {"N": int(N), "kappa": int(kappa), "n_steps": int(kf), "n_draws": n_lv[0],
            "level_names": [cs_level_name(lv) for lv in range(CS_NL)], "n_per_level": n_lv,
            "next_index": int(kf), "next_phases": [kf % P for P in CS_PERIODS],
            "v_next": [float(x) for x in r["v"]], "v_next_exact": [f"{x.numerator}/{x.denominator}" for x in r["v"]],
            "G3": g["G3"], "G5": g["G5"], "G7": g["G7"], "G_sum": g["G_sum"],
            "phase_level_names": [cs_level_name(lv) for lv in range(1, CS_NL)], "freq_rel_phase": fr,
            "sum_exact_ok": bool(sum(r["p"]) == kappa),
            "hyper": {"tau_a2": str(K["ta2"]), "tau2": str(K["t2"]), "sigma0_2": str(K["sigma0_2"])}, "label": LABEL}


def describe_cs(comps: list[dict]) -> list[dict]:
    return [dict(cs_describe(steps_from(c["onehot"], c["offsets"]), c["N"], c["kappa"]), key=c["key"],
                 component=c["label"]) for c in comps]


# ---------------- PL (tab 12) — parametrii pistei PL649 (neschimbați) ----------------
PL_EPS = math.pi / 32
PL_WARMUP = 100
PL_FRAMES = 24
_PL_STRUCT: dict = {}


def pl_structure(N: int, kappa: int) -> dict:
    """PA, PB (perechile a < b, ordinea canonică), PID (N × N), perechile de poziții dintr-o extragere de κ (P15)."""
    key = (int(N), int(kappa))
    if key not in _PL_STRUCT:
        N, kappa = key
        PA, PB = np.triu_indices(N, 1)
        NP = N * (N - 1) // 2
        PID = np.full((N, N), -1, dtype=np.int64)
        PID[PA, PB] = np.arange(NP)
        PID[PB, PA] = np.arange(NP)
        PK = np.array([(i, j) for i in range(kappa) for j in range(i + 1, kappa)], dtype=np.int64).reshape(-1, 2)
        _PL_STRUCT[key] = {"N": N, "kappa": kappa, "NP": NP, "PA": PA, "PB": PB, "PID": PID, "PK": PK}
    return _PL_STRUCT[key]


def pl_gell_mann() -> np.ndarray:
    """Matricele Gell-Mann λ₁..λ₈ (literal pl649._gm_np)."""
    L = np.zeros((8, 3, 3), dtype=complex)
    L[0, 0, 1] = L[0, 1, 0] = 1
    L[1, 0, 1], L[1, 1, 0] = -1j, 1j
    L[2, 0, 0], L[2, 1, 1] = 1, -1
    L[3, 0, 2] = L[3, 2, 0] = 1
    L[4, 0, 2], L[4, 2, 0] = -1j, 1j
    L[5, 1, 2] = L[5, 2, 1] = 1
    L[6, 1, 2], L[6, 2, 1] = -1j, 1j
    L[7] = np.diag([1, 1, -2]) / math.sqrt(3)
    return L


def pl_exp_closed(k: int, eps: float = PL_EPS) -> np.ndarray:
    """exp(iε λ_{k+1}) în formă închisă (literal pl649._exp_closed, referința CPU a Q1)."""
    L = pl_gell_mann()[k]
    if k == 7:
        return np.diag(np.exp(1j * eps * np.diag(L).real))
    return np.eye(3) + 1j * math.sin(eps) * L + (math.cos(eps) - 1) * (L @ L)


def pl_kicks(eps: float = PL_EPS) -> tuple[np.ndarray, np.ndarray]:
    E = np.stack([pl_exp_closed(k, eps) for k in range(8)]).astype(np.complex128)
    return E, np.ascontiguousarray(E.conj().transpose(0, 2, 1))


def pl_new_state(N: int, kappa: int) -> dict:
    S = pl_structure(N, kappa)
    return {"U": np.tile(np.eye(3, dtype=np.complex128), (S["NP"], 1, 1)), "n": np.zeros(S["NP"], dtype=np.int64),
            "last": np.full(S["N"], -1, dtype=np.int64), "counts": np.zeros(S["N"], dtype=np.int64), "steps_done": 0}


def pl_idx(step: np.ndarray) -> np.ndarray:
    return np.stack([np.nonzero(r)[0] for r in step])


def pl_add_step(st: dict, s: int, draws: np.ndarray, S: dict, E: np.ndarray, Ed: np.ndarray) -> None:
    """Literal pl_core.LinkState.add_step (un univers): draws (nd, κ) indici 0-based; vechimile din pașii anteriori."""
    draws = np.sort(draws, -1)
    ages = st["last"].copy()
    PK, PID = S["PK"], S["PID"]
    for d in range(draws.shape[0]):
        x = draws[d]
        a, b = x[PK[:, 0]], x[PK[:, 1]]                       # a < b
        pid = PID[a, b]
        ga, gb = ages[a], ages[b]
        gen = st["n"][pid] % 8
        Ek = E[gen]
        Uc = st["U"][pid]
        left = Ek @ Uc                                        # a mai vechi: U_{a→b} ← E U_{a→b}
        right = Uc @ Ed[gen]                                  # b mai vechi: U_ab ← U_ab E†
        new = np.where((ga < gb)[:, None, None], left, np.where((gb < ga)[:, None, None], right, Uc))
        st["U"][pid] = new
        st["n"][pid] += 1
        st["counts"][x] += 1
    mem = np.zeros(S["N"], dtype=bool)
    mem[draws.reshape(-1)] = True
    st["last"] = np.where(mem, s, st["last"])
    st["steps_done"] += 1


def pl_geometry(U: np.ndarray, n: np.ndarray, N: int) -> dict:
    """Literal pl_core.geometry (un univers): arii, volum-proxy, toate buclele Wilson prin M·M, curburile κ și ε."""
    S_ = pl_structure(N, 2)
    pa, pb = S_["PA"], S_["PB"]
    N = int(N)
    nc = n.astype(np.float64)
    j = nc / 2
    a = np.sqrt(j * (j + 1))                                  # spectrul de arie
    sa = np.sqrt(a)
    S = np.zeros((N, N), dtype=np.float64)
    S[pa, pb] = sa
    S[pb, pa] = sa
    M5 = np.zeros((N, N, 3, 3), dtype=np.complex128)
    M5[pa, pb] = sa.astype(np.complex128)[..., None, None] * U
    M5[pb, pa] = sa.astype(np.complex128)[..., None, None] * U.conj().transpose(0, 2, 1)
    M = M5.transpose(0, 2, 1, 3).reshape(3 * N, 3 * N)        # bloc (a,b) = √a_ab U_{a→b}
    del M5
    M2 = M @ M                                                # toate buclele Wilson
    T = (M * M2.T).reshape(N, 3, N, 3).sum((1, 3)).real      # tr(M_ab (M²)_ba)
    S2 = S @ S
    den_e = 3 * S * S2                                        # 3 √a_ab (S²)_ab
    num_e = T
    ee = np.where(den_e > 0, 1 - num_e / np.where(den_e > 0, den_e, np.ones_like(den_e)), np.zeros_like(den_e))
    den_n = (S * S2).sum(-1)                                  # (S³)_aa
    num_n = T.sum(-1)
    kk = np.where(den_n > 0, 1 - num_n / (3 * np.where(den_n > 0, den_n, np.ones_like(den_n))), np.zeros_like(den_n))
    return {"curvature": kk, "eps_edge": ee[pa, pb], "A": (S ** 2).sum(-1), "V": den_n / 2, "a": a}


def pl_unitarity(U: np.ndarray) -> dict:
    """Literal pl_core.unitarity_error."""
    I = np.eye(3, dtype=U.dtype)
    e = np.abs(U.conj().transpose(0, 2, 1) @ U - I).max((-1, -2))
    d = np.abs(np.linalg.det(U) - 1)
    return {"max_unitarity": float(e.max()), "max_det": float(d.max()),
            "frac_links_err_gt_1e-12": float((e > 1e-12).astype(np.float64).mean())}


def pl_run(steps: list[np.ndarray], N: int, kappa: int, frames: int = 0, walk_from: int | None = None) -> dict:
    """Starea rețelei pe toți pașii (literal pl649.final_product / walk_forward, partea geometrică, un univers).
    frames: geometria după ultimii `frames` pași; walk_from: κ pe nod înaintea fiecărui pas k ≥ walk_from."""
    S = pl_structure(N, kappa)
    E, Ed = pl_kicks()
    st = pl_new_state(N, kappa)
    K = len(steps)
    fr, walk_ks, walk_kappa = [], [], []
    for s in range(K):
        if walk_from is not None and s >= walk_from:
            walk_ks.append(s)
            walk_kappa.append(pl_geometry(st["U"], st["n"], N)["curvature"])
        pl_add_step(st, s, pl_idx(steps[s]), S, E, Ed)
        if frames and s >= K - frames:
            g = pl_geometry(st["U"], st["n"], N)
            fr.append({"step": s, "curvature": g["curvature"].tolist(), "A": g["A"].tolist(),
                       "V_total": float(g["V"].sum())})
    out = {"state": st, "frames": fr}
    if walk_from is not None:
        out["walk_ks"] = np.array(walk_ks, dtype=np.int64)
        out["walk_curvature"] = np.array(walk_kappa) if walk_kappa else np.zeros((0, int(N)))
    return out


def pl_describe(steps: list[np.ndarray], N: int, kappa: int) -> dict:
    """Portul PL DESCRIPTIV (starea finală a rețelei de spin): κ, A, V pe nod, ε pe muchie, spectrul de arie, holonomia.
    Pentru κ < 2 rețeaua nu are muchii (nicio pereche co-extrasă) ⇒ applicable = False, cu motivul scris (P4)."""
    if not steps:
        raise ValueError("niciun pas în setul de date")
    n_draws = int(sum(int(s.shape[0]) for s in steps))
    base = {"N": int(N), "kappa": int(kappa), "n_steps": len(steps), "n_draws": n_draws, "label": LABEL}
    if int(kappa) < 2:
        return dict(base, applicable=False,
                    reason=(f"κ = {int(kappa)}: nicio pereche de bile nu este co-extrasă în aceeași extragere, deci "
                            "rețeaua de spin nu are nicio muchie (n ≡ 0, U ≡ I, curbura ≡ 0 trivial) — portul PL nu "
                            "are obiect pentru această componentă"))
    r = pl_run(steps, N, kappa)
    st = r["state"]
    g = pl_geometry(st["U"], st["n"], N)
    vals, cnts = np.unique(st["n"], return_counts=True)
    kap = g["curvature"]
    return dict(base, applicable=True, curvature_node=kap.tolist(), area_node=g["A"].tolist(),
                volume_node=g["V"].tolist(), eps_edge=g["eps_edge"].tolist(),
                area_spectrum={str(int(k)): int(v) for k, v in zip(vals, cnts)}, area_total=float(g["a"].sum()),
                volume_total=float(g["V"].sum()), links_spun=int((st["n"] > 0).sum()),
                links_total=int(pl_structure(N, kappa)["NP"]), holonomy=pl_unitarity(st["U"]),
                curvature_min=float(kap.min()), curvature_max=float(kap.max()), eps_unit=f"π/32 = {PL_EPS!r}")


def describe_pl(comps: list[dict]) -> list[dict]:
    return [dict(pl_describe(steps_from(c["onehot"], c["offsets"]), c["N"], c["kappa"]), key=c["key"],
                 component=c["label"]) for c in comps]


# ---------------- Identitatea T7C (P3) — artefactele originale citite read-only ----------------
def identity_cs() -> dict:
    """Portul CS pe 6/49 înghețat vs REZULTATE.json (`final_state`, `G_label_x_phase`) și PREDICTII_EXACTE.json.gz (v)."""
    import gzip
    ds, steps = _frozen_649()
    K = len(steps)
    d = cs_describe(steps, 49, 6)
    res = json.loads((CS_REF / "REZULTATE.json").read_text(encoding="utf-8"))
    fs, G = res["final_state"], res["G_label_x_phase"]
    names = list(fs["n_per_level"])
    npz_p, gz_p = CS_REF / "PREDICTII.npz", CS_REF / "PREDICTII_EXACTE.json.gz"
    rows = [_cmp("source_sha256", ds.source_sha256 == res["start"]["source_sha256"], True),
            _cmp("predictions_sha256", _sha(npz_p) == res["predictions_sha256"], True),
            _cmp("exact_predictions_sha256", _sha(gz_p) == res["exact_predictions_sha256"], True),
            _cmp("level_names", names == d["level_names"] == list(fs["v_for_next_index"]), True),
            _cmp("n_per_level", d["n_per_level"], [fs["n_per_level"][x] for x in names]),
            _cmp("v_for_next_index", d["v_next"], [fs["v_for_next_index"][x] for x in names]),
            _cmp("next_index", d["next_index"], fs["next_index"]),
            _cmp("next_phases", d["next_phases"], fs["next_phases"]),
            _cmp("G3", d["G3"], G["G3"]), _cmp("G5", d["G5"], G["G5"]), _cmp("G7", d["G7"], G["G7"]),
            _cmp("G_sum", d["G_sum"], G["G_sum"])]
    with gzip.open(gz_p, "rb") as fh:
        ex = json.loads(fh.read())
    ks = [int(k) for k in ex["ks"]]
    sample = sorted({k for k in ks if (k - ks[0]) % 97 == 0} | {ks[-1]})
    st = cs_new_state(49)
    eq = []
    for s in range(K):
        if s in sample:
            v = cs_v(st, s, 49, 6)["v"]
            eq.append([f"{x.numerator}/{x.denominator}" for x in v] == ex["v"][s - ks[0]])
        cs_add_step(st, s, steps[s])
    rows += [_cmp("v_exact_sample", len(eq) == len(sample) and all(eq), True),
             _cmp("sum_exact_ok", d["sum_exact_ok"], True),
             _cmp("hyper_49_6", [d["hyper"]["tau_a2"], d["hyper"]["tau2"], d["hyper"]["sigma0_2"]] ==
                  [res["start"]["config"]["tau_a2"], res["start"]["config"]["tau2"],
                   res["start"]["config"]["sigma0_2"]], True)]
    return {"port": "CS", "verdict": _verdict(rows), "rows": rows, "source_sha256": ds.source_sha256,
            "n_steps": K, "n_draws": d["n_draws"], "v_exact_sample_steps": sample,
            "reference": {"REZULTATE.json": _sha(CS_REF / "REZULTATE.json"), "PREDICTII.npz": _sha(npz_p),
                          "PREDICTII_EXACTE.json.gz": _sha(gz_p)},
            "scores_recomputed": False}


def identity_pl() -> dict:
    """Portul PL pe 6/49 înghețat vs FINAL.json (nod, spectru, arie, holonomie, muchii, cadre) și PREDICTII.npz (κ)."""
    ds, steps = _frozen_649()
    K = len(steps)
    F = json.loads((PL_RES / "final" / "FINAL.json").read_text(encoding="utf-8"))
    R = json.loads((PL_RES / "backtest_unic" / "REZULTATE.json").read_text(encoding="utf-8"))
    S0 = json.loads((PL_RES / "backtest_unic" / "START.json").read_text(encoding="utf-8"))
    npz_p = PL_RES / "backtest_unic" / "PREDICTII.npz"
    ref = np.load(npz_p)
    run = pl_run(steps, 49, 6, frames=len(F["frames"]), walk_from=PL_WARMUP)
    st = run["state"]
    g = pl_geometry(st["U"], st["n"], 49)
    vals, cnts = np.unique(st["n"], return_counts=True)
    spec = {str(int(k)): int(v) for k, v in zip(vals, cnts)}
    ho = pl_unitarity(st["U"])
    th, fu = F["telemetry"]["holonomy_error"], R["final_unitarity"]
    PID = pl_structure(49, 6)["PID"]
    te = F["top_edges"]
    tidx = [int(PID[e["a"] - 1, e["b"] - 1]) for e in te]
    fr = run["frames"]
    rows = [_cmp("source_sha256", ds.source_sha256 == F["meta"]["source_sha256"] == S0["source_sha256"], True),
            _cmp("predictions_sha256", _sha(npz_p) == R["predictions_sha256"], True),
            _cmp("n_draws", int(sum(int(s.shape[0]) for s in steps)), F["n_draws"]),
            _cmp("n_steps", K, F["n_steps"]),
            _cmp("area_spectrum_keys", list(spec) == list(F["area_spectrum"]), True),
            _cmp("area_spectrum_counts", [spec.get(k, -1) for k in F["area_spectrum"]], list(F["area_spectrum"].values())),
            _cmp("node_kappa", g["curvature"], F["node"]["kappa"]), _cmp("node_A", g["A"], F["node"]["A"]),
            _cmp("node_V", g["V"], F["node"]["V"]),
            _cmp("planck_area_total", float(g["a"].sum()), F["telemetry"]["planck_area_total"]),
            _cmp("holonomy_max_unitarity", [ho["max_unitarity"]] * 2, [th["max_unitarity"], fu["max_unitarity"]]),
            _cmp("holonomy_max_det", [ho["max_det"]] * 2, [th["max_det"], fu["max_det"]]),
            _cmp("holonomy_frac_err_zero", [ho["frac_links_err_gt_1e-12"] == 0.0] * 2,
                 [th["frac_links_err_gt_1e-12"] == 0.0, fu["frac_links_err_gt_1e-12"] == 0.0]),
            _cmp("top_edges_eps", [float(g["eps_edge"][i]) for i in tidx], [e["eps"] for e in te]),
            _cmp("top_edges_j_x2", [int(st["n"][i]) for i in tidx], [int(round(2 * e["j"])) for e in te]),
            _cmp("frames_steps", [f["step"] for f in fr], [f["step"] for f in F["frames"]]),
            _cmp("frames_kappa", [f["curvature"] for f in fr], [f["kappa"] for f in F["frames"]]),
            _cmp("frames_A", [f["A"] for f in fr], [f["A"] for f in F["frames"]]),
            _cmp("frames_V_total", [f["V_total"] for f in fr], [f["V_total"] for f in F["frames"]]),
            _cmp("walk_ks", run["walk_ks"], ref["ks"]),
            _cmp("walk_kappa", run["walk_curvature"], ref["kappa"])]
    return {"port": "PL", "verdict": _verdict(rows), "rows": rows, "source_sha256": ds.source_sha256,
            "n_steps": K, "n_draws": int(sum(int(s.shape[0]) for s in steps)), "device": "cpu (NumPy complex128)",
            "reference_device": S0.get("device"),
            "reference": {"FINAL.json": _sha(PL_RES / "final" / "FINAL.json"),
                          "REZULTATE.json": _sha(PL_RES / "backtest_unic" / "REZULTATE.json"),
                          "PREDICTII.npz": _sha(npz_p)},
            "scores_recomputed": False, "tickets_recomputed": False}


def write_identity_t7c(out_dir: Path = OUT_DIR_T7C) -> Path:
    cs, pl = _run_sub("cs", False), _run_sub("pl", False)
    now = dt.datetime.now(dt.timezone.utc)
    rep = {"protocol": "TU3-T7C", "protocol_sha256": _sha(PROTOCOL_T7C), "code_sha256": _sha(Path(__file__)),
           "written_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "tolerance": TOL, "CS": cs, "PL": pl,
           "verdict": "PASS" if "FAIL" not in (cs["verdict"], pl["verdict"]) else "FAIL",
           "note": "Identitatea compară numai mărimi descriptive (CS: n pe niveluri, ponderile v, statisticile G; PL: "
                   "curburile, ariile, volumele, spectrul de arie, holonomia, κ pe pași); p̂, legile, biletele, "
                   "variantele, scorurile, porțile și verdictele pistelor 6/49 nu sunt recalculate și nu se transferă. "
                   "PL: CPU NumPy complex128 vs referința PyTorch CUDA (PROTOCOL_TU3_T7C §3.3). "
                   "positive_claims_allowed=false.",
           "positive_claims_allowed": False}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"IDENTITATE_T7C_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(dst, "x", encoding="utf-8") as f:
        f.write(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    os.chmod(dst, 0o444)
    return dst


def latest_identity_t7c(out_dir: Path = OUT_DIR_T7C) -> dict | None:
    fs = sorted(Path(out_dir).glob("IDENTITATE_T7C_*.json")) if Path(out_dir).is_dir() else []
    if not fs:
        return None
    try:
        d = json.loads(fs[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {"file": fs[-1].name, "verdict": d.get("verdict"), "CS": (d.get("CS") or {}).get("verdict"),
            "PL": (d.get("PL") or {}).get("verdict")}


if __name__ == "__main__":
    raise SystemExit(main())
