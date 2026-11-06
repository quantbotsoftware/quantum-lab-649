"""PL649 — calificare Q1–Q6, backtest unic, descriptiv (PREINREGISTRARE_PL649.md, PL649-P1).

Utilizare (din pl649/, cu ../.venv/bin/python -B):
  pl649.py --qualify            # Q1–Q6 (date construite/sintetice; arhiva reală neatinsă)
  pl649.py --real               # backtestul unic (refuză repetarea: START.json)
  pl649.py --null-marg 1024     # §7 universuri nule masive (legea), GPU
  pl649.py --null-full 32       # §7 universuri nule cu biletul QUBO exact
  pl649.py --power              # §7 putere sub H_PL auto-consistentă
  pl649.py --annealer-cert      # §7 certificatul anealerului la pașii din 97 în 97
  pl649.py --final              # §7/§9 starea finală + produsul (3 variante)
Nu importă și nu rulează modele închise; parser.py este folosit numai pentru ingestie.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
sys.path.insert(0, str(HERE))
import pl_core as C  # noqa: E402

OUT = HERE / "rezultate"
PROTO = HERE / "PREINREGISTRARE_PL649.md"
SEAL = HERE / "SIGILIU_PROTOCOL_PL649.json"
N49, K6 = 49, 6
WARMUP = 100
HALF_LIFE = 26.0
CK_EVERY = 97


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=float))


def code_hashes() -> dict:
    return {"pl_core.py": sha256_file(HERE / "pl_core.py"), "pl649.py": sha256_file(HERE / "pl649.py")}


def check_seal() -> dict:
    seal = json.loads(SEAL.read_text())
    ok = sha256_file(PROTO) == seal["sha256"]
    return {"ok": ok, "sha256": seal["sha256"], "sealed_at_utc": seal["sealed_at_utc"]}


# ---------------------------------------------------------------------------
# Date
# ---------------------------------------------------------------------------
def load_real():
    sys.path.insert(0, str(QL))
    import parser as P  # noqa: E402  (ingestie QL649 §1; nu este model)
    ds = P.build_dataset(device="cpu")
    oh = ds.onehot.numpy().astype(np.float64)
    off = ds.step_offsets.numpy()
    steps = [oh[off[s]:off[s + 1]] for s in range(len(off) - 1)]
    meta = {"source": str(ds.source), "source_sha256": ds.source_sha256, "n_draws": ds.n_draws,
            "n_steps": ds.n_steps, "parser_sha256": sha256_file(QL / "parser.py"),
            "first_date": ds.step_dates[0], "last_date": ds.step_dates[-1]}
    return steps, meta


def real_step_structure() -> np.ndarray:
    sys.path.insert(0, str(QL))
    import parser as P  # noqa: E402
    recs, _ = P.load_records(P.DEFAULT_SOURCE)
    clean, _ = P.clean_records(recs)
    dates = [r["draw_date"] for r in clean]
    sizes = []
    for i, d in enumerate(dates):
        if i == 0 or d != dates[i - 1]:
            sizes.append(1)
        else:
            sizes[-1] += 1
    return np.array(sizes, dtype=np.int64)


def synthetic_steps(sizes: np.ndarray, seed) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    out = []
    for sz in sizes:
        a = np.zeros((int(sz), N49))
        for i in range(int(sz)):
            a[i, rng.choice(N49, K6, replace=False)] = 1.0
        out.append(a)
    return out


def onehot_sets(sets: list[list[int]]) -> list[np.ndarray]:
    out = []
    for s in sets:
        a = np.zeros((1, N49))
        a[0, [t - 1 for t in s]] = 1.0
        out.append(a)
    return out


def relabel(steps: list[np.ndarray], perm: list[int]) -> list[np.ndarray]:
    idx = np.array([perm[j] - 1 for j in range(N49)])
    out = []
    for s in steps:
        b = np.zeros_like(s)
        b[:, idx] = s
        out.append(b)
    return out


def idx_of(step: np.ndarray) -> np.ndarray:
    return np.stack([np.nonzero(r)[0] for r in step])


# ---------------------------------------------------------------------------
# Comparatori, scoruri, porți (definițiile QL649 §5 / CS649 §3)
# ---------------------------------------------------------------------------
def top6(score: np.ndarray) -> np.ndarray:
    order = np.argsort(-score, axis=-1, kind="stable")
    return np.sort(order[..., :K6] + 1, -1)


def comparators(steps: list[np.ndarray], ks: np.ndarray) -> dict:
    S = np.stack([s.sum(0) for s in steps]).astype(np.float64)
    P = np.vstack((np.zeros((1, S.shape[1])), np.cumsum(S, 0)))
    c = P[ks]
    sidx = np.arange(S.shape[0])
    W = np.where(sidx[None, :] < ks[:, None], 2.0 ** (-(ks[:, None] - 1 - sidx[None, :]) / HALF_LIFE), 0.0)
    ew = W @ S
    piB = (c + 1.0) / (c + 1.0).sum(-1, keepdims=True)
    piR = (ew + 0.5) / (ew + 0.5).sum(-1, keepdims=True)
    return {"piB": piB, "piR": piR, "ew": ew, "c": c}


def score_block(q, ticket, y) -> dict:
    out = {"log": (y * np.log(q) + (1 - y) * np.log(1 - q)).sum(-1), "brier": ((q - y) ** 2).sum(-1)}
    if ticket is not None:
        out["hits"] = np.take_along_axis(y, ticket - 1, axis=1).sum(-1)
    return out


def hyper_pmf() -> np.ndarray:
    return np.array([math.comb(6, i) * math.comb(43, 6 - i) / math.comb(49, 6) for i in range(7)])


def exact_tail(total_hits: int, n: int) -> float:
    pmf, dist = hyper_pmf(), np.array([1.0])
    for _ in range(n):
        dist = np.convolve(dist, pmf)
    return float(dist[total_hits:].sum())


def gates(t: dict, h1: dict, h2: dict) -> list[dict]:
    g = [
        ("1", "ExcesPL/U >= 0.20", t["excess_PL"] >= 0.20, t["excess_PL"]),
        ("2", "hitsPL > hitsB și hitsPL > hitsR", t["hits_PL"] > t["hits_B"] and t["hits_PL"] > t["hits_R"],
         [t["hits_PL"], t["hits_B"], t["hits_R"]]),
        ("3", "logPL−logU > 0 și logPL−logB > 0", t["log_PL"] - t["log_U"] > 0 and t["log_PL"] - t["log_B"] > 0,
         [t["log_PL"] - t["log_U"], t["log_PL"] - t["log_B"]]),
        ("4", "BrierPL < BrierU, BrierB, BrierR", t["brier_PL"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
         [t["brier_PL"], t["brier_U"], t["brier_B"], t["brier_R"]]),
        ("5", "ambele jumătăți: exces > 0 și hitsPL−hitsB > 0",
         all(h["excess_PL"] > 0 and h["hits_PL"] - h["hits_B"] > 0 for h in (h1, h2)),
         [[h["excess_PL"], h["hits_PL"] - h["hits_B"]] for h in (h1, h2)]),
        ("6", "ambele jumătăți: logPL−logB > 0", all(h["log_PL"] - h["log_B"] > 0 for h in (h1, h2)),
         [h["log_PL"] - h["log_B"] for h in (h1, h2)]),
    ]
    return [{"gate": a, "rule": b, "pass": bool(c), "value": d} for a, b, c, d in g]


def summarize(sl: slice, S: dict) -> dict:
    n = int(S["y"][sl].shape[0])
    o = {"targets": n}
    for name in ("PL", "B", "R", "PI6"):
        o[f"hits_{name}"] = int(S[f"hits_{name}"][sl].sum())
        o[f"excess_{name}"] = o[f"hits_{name}"] / n - 36.0 / 49.0 if n else 0.0
    for name in ("PL", "B", "R", "U"):
        o[f"log_{name}"] = float(S[f"log_{name}"][sl].sum())
        o[f"brier_{name}"] = float(S[f"brier_{name}"][sl].sum())
    return o


def targets_of(steps, warmup):
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    t_step = np.concatenate([np.full(steps[k].shape[0], k, dtype=np.int64) for k in ks])
    y = np.concatenate([steps[k] for k in ks]).astype(np.float64)
    return ks, t_step, y


def score(steps, pred: dict, warmup: int = WARMUP, verdict_prefix: str = "PL") -> dict:
    ks, t_step, y = targets_of(steps, warmup)
    assert np.array_equal(ks, pred["ks"])
    row = t_step - warmup
    cmp_ = comparators(steps, ks)
    laws = {"PL": C.marginal_q(pred["pi"]), "B": C.marginal_q(cmp_["piB"]), "R": C.marginal_q(cmp_["piR"])}
    tick = {"PL": pred["ticket"], "B": top6(cmp_["piB"]), "R": top6(cmp_["piR"]), "PI6": top6(pred["pi"])}
    S = {"y": y}
    for name in ("PL", "B", "R"):
        sb = score_block(laws[name][row], tick[name][row], y)
        S[f"hits_{name}"], S[f"log_{name}"], S[f"brier_{name}"] = sb["hits"], sb["log"], sb["brier"]
    S["hits_PI6"] = np.take_along_axis(y, tick["PI6"][row] - 1, axis=1).sum(-1)
    sU = score_block(np.full_like(y, 6.0 / N49), None, y)
    S["log_U"], S["brier_U"] = sU["log"], sU["brier"]
    n = y.shape[0]
    half = n // 2
    t, h1, h2 = summarize(slice(0, n), S), summarize(slice(0, half), S), summarize(slice(half, n), S)
    g = gates(t, h1, h2)
    passed = sum(x["pass"] for x in g)
    tP = tick["PL"]
    return {
        "n_targets": int(n), "n_steps_predicted": int(ks.shape[0]), "total": t, "half1": h1, "half2": h2,
        "gates": g, "gates_passed": int(passed),
        "verdict": f"{verdict_prefix}_PROMOVAT_EXPLORATORIU" if passed == 6 else f"{verdict_prefix}_NO_PROMOTION_EXPLORATORY",
        "tickets_changed_vs_B_targets": int((tP[row] != tick["B"][row]).any(-1).sum()),
        "tickets_changed_vs_R_targets": int((tP[row] != tick["R"][row]).any(-1).sum()),
        "tickets_changed_vs_top6pi_targets": int((tP[row] != tick["PI6"][row]).any(-1).sum()),
        "match_dist_PL": np.bincount(S["hits_PL"].astype(int), minlength=7).tolist(),
        "match_expected_U": (hyper_pmf() * n).tolist(),
        "law_PL_in_01": bool(((laws["PL"] > 0) & (laws["PL"] < 1)).all()),
        "per_target": {"step": t_step.tolist(), "hits_PL": S["hits_PL"].astype(int).tolist(),
                       "log_PL": S["log_PL"].tolist()},
    }


# ---------------------------------------------------------------------------
# Rulări ale motorului
# ---------------------------------------------------------------------------
def state_after(steps: list[np.ndarray], device, upto: int | None = None) -> C.LinkState:
    st = C.LinkState(1, device)
    for s, step in enumerate(steps[: (len(steps) if upto is None else upto)]):
        st.add_step(s, torch.as_tensor(idx_of(step), device=device)[None])
    return st


def predict_at(steps, device, enum=None, upto=None) -> dict:
    st = state_after(steps, device, upto)
    r = C.predict_state(st.U, st.n, enum, need_ticket=enum is not None)
    r["state"] = st
    return r


def walk_forward(steps, device, enum, warmup=WARMUP, need_ticket=True, keep_at=(), progress=False) -> dict:
    st = C.LinkState(1, device)
    for s in range(warmup):
        st.add_step(s, torch.as_tensor(idx_of(steps[s]), device=device)[None])
    ks = np.arange(warmup, len(steps), dtype=np.int64)
    pi = np.zeros((len(ks), N49))
    kap = np.zeros((len(ks), N49))
    tick = np.zeros((len(ks), K6), dtype=np.int64)
    emin = np.full(len(ks), np.nan)
    esec = np.full(len(ks), np.nan)
    kept = {}
    t0 = time.time()
    for i, k in enumerate(ks):
        r = C.predict_state(st.U, st.n, enum, need_ticket=need_ticket)
        pi[i] = r["pi"][0].cpu().numpy()
        kap[i] = r["kappa"][0].cpu().numpy()
        if need_ticket:
            q = r["qubo"][0]
            tick[i] = q["ticket"]
            emin[i], esec[i] = q["E_min"], q["E_second"]
        if int(k) in keep_at:
            kept[int(k)] = {"pi": pi[i].copy(), "ticket": tick[i].copy(), "snap": st.snapshot(),
                            "z": r["z"][0].clone(), "eps_edge": r["eps_edge"][0].clone()}
        st.add_step(int(k), torch.as_tensor(idx_of(steps[k]), device=device)[None])
        if progress and (i % 250 == 0):
            print(f"  pas {i}/{len(ks)}  {time.time() - t0:.1f}s", flush=True)
    return {"ks": ks, "pi": pi, "kappa": kap, "ticket": tick, "E_min": emin, "E_second": esec, "kept": kept,
            "final_state": st, "seconds": time.time() - t0}


# ---------------------------------------------------------------------------
# Implementarea de referință CPU (Q1): exponențiale în formă închisă, triunghi cu triunghi
# ---------------------------------------------------------------------------
def _gm_np() -> np.ndarray:
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


def _exp_closed(k: int, eps: float = C.EPS) -> np.ndarray:
    L = _gm_np()[k]
    if k == 7:
        return np.diag(np.exp(1j * eps * np.diag(L).real))
    return np.eye(3) + 1j * math.sin(eps) * L + (math.cos(eps) - 1) * (L @ L)


def ref_links(steps: list[np.ndarray]):
    E = [_exp_closed(k) for k in range(8)]
    U = {}
    n = np.zeros((N49, N49), dtype=np.int64)
    last = np.full(N49, -1, dtype=np.int64)
    for s, step in enumerate(steps):
        ages = last.copy()
        for row in step:
            x = sorted(np.nonzero(row)[0].tolist())
            for a, b in itertools.combinations(x, 2):
                m = n[a, b]
                Ek = E[m % 8]
                u = U.get((a, b), np.eye(3, dtype=complex))
                if ages[a] < ages[b]:
                    u = Ek @ u
                elif ages[b] < ages[a]:
                    u = u @ Ek.conj().T
                U[(a, b)] = u
                n[a, b] += 1
                n[b, a] += 1
        for row in step:
            last[np.nonzero(row)[0]] = s
    return U, n


def ref_curvature(U: dict, n: np.ndarray):
    def link(x, y):
        if x < y:
            return U.get((x, y), np.eye(3, dtype=complex))
        return U.get((y, x), np.eye(3, dtype=complex)).conj().T
    a = np.sqrt((n / 2) * (n / 2 + 1))
    numn, denn = np.zeros(N49), np.zeros(N49)
    nume, dene = np.zeros((N49, N49)), np.zeros((N49, N49))
    for x, y, z in itertools.combinations(range(N49), 3):
        w = math.sqrt(a[x, y] * a[y, z] * a[x, z])
        if w == 0:
            continue
        e = 1 - np.trace(link(x, y) @ link(y, z) @ link(z, x)).real / 3
        for v in (x, y, z):
            numn[v] += w * e
            denn[v] += w
        for p, q in ((x, y), (y, z), (x, z)):
            nume[p, q] += w * e
            dene[p, q] += w
    kap = np.where(denn > 0, numn / np.where(denn > 0, denn, 1), 0.0)
    ee = np.where(dene > 0, nume / np.where(dene > 0, dene, 1), 0.0)
    return kap, ee[C.PA, C.PB]


def random_su3(rng) -> np.ndarray:
    Z = rng.normal(size=(3, 3)) + 1j * rng.normal(size=(3, 3))
    Q, R = np.linalg.qr(Z)
    Q = Q @ np.diag(np.diag(R) / np.abs(np.diag(R)))
    return Q / np.linalg.det(Q) ** (1 / 3)


def cpu_enumerate(h: np.ndarray, J: np.ndarray, tau: float = C.TAU_E) -> dict:
    Cb = C._combos_np(N49, K6).astype(np.int64)
    E = h[Cb].sum(1)
    for i, j in C.P15:
        E += J[Cb[:, i], Cb[:, j]]
    emin = E.min()
    best = int(np.nonzero(E <= emin + tau)[0][0])
    return {"ticket": (Cb[best] + 1).tolist(), "E_min": float(emin)}


# ---------------------------------------------------------------------------
# Calificare Q1–Q6 (§5)
# ---------------------------------------------------------------------------
def q1(device, enum) -> dict:
    rng = np.random.default_rng([649, 12, 1])
    grng = np.random.default_rng([649, 12, 11])
    d_k, d_e, unit, det, gauge = 0.0, 0.0, 0.0, 0.0, 0.0
    enum_rows = []
    for inst in range(40):
        n = int(rng.integers(1, 7)) if inst < 6 else int(rng.integers(1, 41))
        steps = []
        for _ in range(n):
            nd = 2 if rng.random() < 0.15 else 1
            a = np.zeros((nd, N49))
            for i in range(nd):
                a[i, rng.choice(N49, K6, replace=False)] = 1.0
            steps.append(a)
        st = state_after(steps, device)
        g = C.geometry(st.U, st.n)
        L = C.law(g["kappa"])
        Ur, nr = ref_links(steps)
        kr, er = ref_curvature(Ur, nr)
        d_k = max(d_k, float(np.abs(g["kappa"][0].cpu().numpy() - kr).max()))
        d_e = max(d_e, float(np.abs(g["eps_edge"][0].cpu().numpy() - er).max()))
        ue = C.unitarity_error(st.U)
        unit, det = max(unit, ue["max_unitarity"]), max(det, ue["max_det"])
        G = torch.as_tensor(np.stack([random_su3(grng) for _ in range(N49)]), device=device)
        pa, pb = torch.as_tensor(C.PA, device=device), torch.as_tensor(C.PB, device=device)
        Ug = G[pa][None] @ st.U @ G[pb][None].conj().transpose(-1, -2)
        g2 = C.geometry(Ug, st.n)
        L2 = C.law(g2["kappa"])
        gauge = max(gauge, float((g2["kappa"] - g["kappa"]).abs().max()), float((g2["eps_edge"] - g["eps_edge"]).abs().max()),
                    float((L2["pi"] - L["pi"]).abs().max()))
        if inst in (10, 20, 30):
            h, J = C.qubo_terms(L["z"], g["eps_edge"])
            rg = enum.minimize(h[0], J[0])
            rc = cpu_enumerate(h[0].cpu().numpy(), J[0].cpu().numpy())
            enum_rows.append({"inst": inst, "gpu": rg["ticket"], "cpu": rc["ticket"],
                              "dE": abs(rg["E_min"] - rc["E_min"])})
    ok = (d_k <= 1e-12 and d_e <= 1e-12 and unit <= 1e-12 and det <= 1e-12 and gauge <= 1e-10
          and all(r["gpu"] == r["cpu"] and r["dE"] <= 1e-9 for r in enum_rows))
    return {"pass": bool(ok), "max_dkappa": d_k, "max_deps": d_e, "max_unitarity": unit, "max_det": det,
            "max_gauge_dev": gauge, "enumeration": enum_rows}


def q2_q3_q4(device, enum, sizes) -> tuple[dict, dict, dict]:
    steps = synthetic_steps(sizes, [649, 12, 999])
    ks = np.arange(WARMUP, len(steps))
    cks = [int(k) for k in ks if (k - WARMUP) % CK_EVERY == 0]
    wf = walk_forward(steps, device, enum, need_ticket=False, keep_at=set(cks))
    sum_dev = float(np.abs(wf["pi"].sum(-1) - 1).max())
    q = C.marginal_q(wf["pi"])
    q_ok = bool(((q > 0) & (q < 1)).all())
    fin = bool(np.isfinite(wf["kappa"]).all())
    ue = C.unitarity_error(wf["final_state"].U)
    inc_ok, u_dev = True, 0.0
    q3_pi, q3_ticket_ok = 0.0, True
    perm = [int(v) + 1 for v in np.random.default_rng([649, 12, 4]).permutation(N49)]
    steps_p = relabel(steps, perm)
    q4_pi, q4_checked, q4_gap_ok, q4_match = 0.0, 0, 0, True
    for k in cks:
        kp = wf["kept"][k]
        st = state_after(steps, device, upto=k)
        sn = kp["snap"]
        inc_ok &= bool(torch.equal(st.n, sn["n"]) and torch.equal(st.last, sn["last"]) and torch.equal(st.counts, sn["counts"]))
        u_dev = max(u_dev, float((st.U - sn["U"]).abs().max()))
        r_tr = C.predict_state(st.U, st.n, enum)
        r_full = C.predict_state(sn["U"], sn["n"], enum)
        q3_pi = max(q3_pi, float(np.abs(r_tr["pi"][0].cpu().numpy() - kp["pi"]).max()))
        q3_ticket_ok &= r_tr["qubo"][0]["ticket"] == r_full["qubo"][0]["ticket"]
        rp = predict_at(steps_p, device, enum, upto=k)
        pi0, pip = r_full["pi"][0].cpu().numpy(), rp["pi"][0].cpu().numpy()
        q4_pi = max(q4_pi, float(max(abs(pip[perm[j] - 1] - pi0[j]) for j in range(N49))))
        q4_checked += 1
        gap = r_full["qubo"][0]["E_second"] - r_full["qubo"][0]["E_min"]
        if gap > 1e-6:
            q4_gap_ok += 1
            mapped = sorted(perm[t - 1] for t in r_full["qubo"][0]["ticket"])
            q4_match &= mapped == rp["qubo"][0]["ticket"]
    Q2 = {"pass": bool(sum_dev <= 1e-12 and q_ok and fin and ue["max_unitarity"] <= 1e-10 and ue["max_det"] <= 1e-10
                       and inc_ok and u_dev <= 1e-12),
          "max_sum_pi_dev": sum_dev, "q_law_in_01": q_ok, "kappa_finite": fin, "unitarity": ue,
          "incremental_equals_scratch": bool(inc_ok), "max_link_dev": u_dev, "checkpoints": cks,
          "walk_seconds": wf["seconds"]}
    Q3 = {"pass": bool(q3_pi <= 1e-12 and q3_ticket_ok), "max_pi_dev": q3_pi, "tickets_identical": bool(q3_ticket_ok)}
    Q4 = {"pass": bool(q4_pi <= 1e-10 and q4_match and q4_gap_ok >= 0.9 * q4_checked), "max_pi_dev": q4_pi,
          "checked": q4_checked, "gap_gt_1e-6": q4_gap_ok, "tickets_match": bool(q4_match), "perm_seed": [649, 12, 4]}
    return Q2, Q3, Q4


D1, D2, D3 = list(range(1, 7)), list(range(7, 13)), [1, 7, 13, 14, 15, 16]
NFIX = [list(range(1, 7)), [2, 7, 8, 9, 10, 11], [1, 2, 12, 13, 14, 15], [2, 16, 17, 18, 19, 20], [1, 2, 21, 22, 23, 24]]
CONST = json.loads((HERE / "jurnal" / "preprotocol" / "constante_preprotocol.json").read_text())


def rel(a, b):
    return abs(a - b) / abs(b)


def q5(device, enum) -> dict:
    Hp, Hm = onehot_sets([D1, D2, D3]), onehot_sets([D1, D3, D2])
    rp, rm = predict_at(Hp, device, enum), predict_at(Hm, device, enum)
    sp, sm = rp["state"], rm["state"]
    a_ok = (torch.equal(sp.counts, sm.counts) and torch.equal(sp.n, sm.n)
            and float((rp["A"] - rm["A"]).abs().max()) == 0.0 and float((rp["V"] - rm["V"]).abs().max()) == 0.0)
    cp, cm = comparators(Hp, np.array([3])), comparators(Hm, np.array([3]))
    a_ok = bool(a_ok and np.array_equal(cp["piB"], cm["piB"]) and np.array_equal(top6(cp["piB"]), top6(cm["piB"])))
    pim = rm["pi"][0].cpu().numpy()
    b_ok = bool(np.abs(pim - 1 / 49).max() <= 1e-12)
    k = rp["kappa"][0].cpu().numpy()
    c5, c10 = CONST["c_over_5"], CONST["c_over_10"]
    rest = [j for j in range(N49) if j not in (0, 6, 12, 13, 14, 15)]
    c_ok = bool(rel(k[0], c5) <= 1e-9 and rel(k[6], c5) <= 1e-9 and all(rel(k[j], c10) <= 1e-9 for j in (12, 13, 14, 15))
                and np.abs(k[rest]).max() <= 1e-14)
    pi = rp["pi"][0].cpu().numpy()
    q = C.marginal_q(pi[None])[0]
    d_ok = bool(rel(pi[0], CONST["pi_1"]) <= 1e-9 and rel(pi[12], CONST["pi_13"]) <= 1e-9
                and rel(pi[1], CONST["pi_2"]) <= 1e-9 and rel(q[1] - q[0], CONST["q2_minus_q1"]) <= 1e-9
                and q[1] - q[0] >= 1e-3)
    rn = predict_at(onehot_sets(NFIX), device, None)
    k3 = float(rn["kappa"][0, 2])
    e_ok = bool(rel(k3, CONST["N_kappa3_SU3"]) <= 1e-9 and rel(k3, CONST["N_kappa3_abelian"]) >= 0.4)
    return {"pass": bool(a_ok and b_ok and c_ok and d_ok and e_ok), "a_same_counts_pairs_area_volume_B": a_ok,
            "b_Hminus_uniform": b_ok, "max_pi_dev_Hminus": float(np.abs(pim - 1 / 49).max()),
            "c_kappa": c_ok, "kappa_Hplus": {"1": float(k[0]), "7": float(k[6]), "13": float(k[12]),
                                            "max_abs_rest": float(np.abs(k[rest]).max())},
            "d_pi": d_ok, "pi_Hplus": {"1": float(pi[0]), "13": float(pi[12]), "2": float(pi[1])},
            "q2_minus_q1": float(q[1] - q[0]), "e_nonabelian": e_ok, "kappa3_N": k3}


def q6(device, enum) -> dict:
    Hp, Hm = onehot_sets([D1, D2, D3]), onehot_sets([D1, D3, D2])
    rp, rm = predict_at(Hp, device, enum), predict_at(Hm, device, enum)
    cp = comparators(Hp, np.array([3]))
    tB, tR = top6(cp["piB"])[0].tolist(), top6(cp["piR"])[0].tolist()
    ew = cp["ew"][0]
    ew_ok = bool(ew[6] > ew[0] > ew[12] and all(ew[12] == ew[j] for j in (13, 14, 15))
                 and ew[12] > max(ew[j] for j in range(N49) if j not in (0, 6, 12, 13, 14, 15)))
    tPp, tPm = rp["qubo"][0]["ticket"], rm["qubo"][0]["ticket"]
    ok = (tPp == [2, 3, 4, 5, 6, 8] and tB == [1, 2, 3, 4, 5, 7] and tR == [1, 7, 13, 14, 15, 16]
          and tPm == [1, 2, 3, 4, 5, 6] and ew_ok)
    return {"pass": bool(ok), "ticket_PL_Hplus": tPp, "ticket_B": tB, "ticket_R": tR, "ticket_PL_Hminus": tPm,
            "ew_order_ok": ew_ok, "E_gap_Hplus": rp["qubo"][0]["E_second"] - rp["qubo"][0]["E_min"]}


def qualify() -> dict:
    seal = check_seal()
    assert seal["ok"], "protocolul nu corespunde sigiliului"
    dev = C.resolve_device()
    t0 = time.time()
    enum = C.Enumerator(dev)
    sizes = real_step_structure()
    res = {"protocol_sha256": seal["sha256"], "started_utc": utc_now(), "device": str(dev),
           "device_name": torch.cuda.get_device_name(0) if dev.type == "cuda" else "cpu",
           "code_sha256": code_hashes(), "torch": torch.__version__}
    res["Q1"] = q1(dev, enum)
    res["Q2"], res["Q3"], res["Q4"] = q2_q3_q4(dev, enum, sizes)
    res["Q5"] = q5(dev, enum)
    res["Q6"] = q6(dev, enum)
    n_pass = sum(res[f"Q{i}"]["pass"] for i in range(1, 7))
    res["n_pass"] = int(n_pass)
    res["verdict"] = "PL_QUALIFIED" if n_pass == 6 else "PL_NOT_QUALIFIED"
    res["seconds"] = time.time() - t0
    res["finished_utc"] = utc_now()
    res["vram"] = C.vram()
    res["real_archive_touched"] = False
    write_json(OUT / "calificare" / "CALIFICARE.json", res)
    print(json.dumps({k: (v["pass"] if isinstance(v, dict) and "pass" in v else v) for k, v in res.items()
                      if k.startswith("Q") or k in ("verdict", "seconds")}, indent=1))
    return res


# ---------------------------------------------------------------------------
# Backtestul unic (§6)
# ---------------------------------------------------------------------------
def run_real() -> int:
    rdir = OUT / "backtest_unic"
    if (rdir / "START.json").exists():
        print("REFUZ: backtestul unic a fost deja pornit (START.json există).")
        return 2
    seal = check_seal()
    qual = json.loads((OUT / "calificare" / "CALIFICARE.json").read_text())
    assert seal["ok"] and qual["verdict"] == "PL_QUALIFIED", "necalificat sau sigiliu invalid"
    assert qual["code_sha256"] == code_hashes(), "codul diferă de cel calificat"
    dev = C.resolve_device()
    steps, meta = load_real()
    start = {"started_utc": utc_now(), "protocol_sha256": seal["sha256"], "qualification_finished_utc": qual["finished_utc"],
             "code_sha256": code_hashes(), "source_sha256": meta["source_sha256"], "parser_sha256": meta["parser_sha256"],
             "meta": meta, "device": str(dev), "positive_claims_allowed": False}
    write_json(rdir / "START.json", start)
    enum = C.Enumerator(dev)
    wf = walk_forward(steps, dev, enum, progress=True)
    np.savez_compressed(rdir / "PREDICTII.npz", ks=wf["ks"], pi=wf["pi"], kappa=wf["kappa"], ticket=wf["ticket"],
                        E_min=wf["E_min"], E_second=wf["E_second"])
    psha = sha256_file(rdir / "PREDICTII.npz")
    write_json(rdir / "PREDICTII_SIGILIU.json", {"sha256": psha, "sealed_utc": utc_now(), "before_scoring": True})
    S = score(steps, wf)
    cons = {"hits_B": S["total"]["hits_B"], "hits_R": S["total"]["hits_R"], "targets": S["n_targets"],
            "consistent": S["total"]["hits_B"] == 1847 and S["total"]["hits_R"] == 1821 and S["n_targets"] == 2495}
    fin = wf["final_state"]
    res = {"protocol": "PL649-P1", "finished_utc": utc_now(), "predictions_sha256": psha, "consistency_BR": cons,
           "exact_tail_p_hitsPL_ge": exact_tail(S["total"]["hits_PL"], S["n_targets"]), **S,
           "E_gap_min": float(np.nanmin(wf["E_second"] - wf["E_min"])),
           "steps_gap_le_1e-6": int(((wf["E_second"] - wf["E_min"]) <= 1e-6).sum()),
           "final_unitarity": C.unitarity_error(fin.U), "walk_seconds": wf["seconds"], "vram": C.vram(),
           "positive_claims_allowed": False}
    if not cons["consistent"]:
        res["verdict"] = "INVALID_CONSISTENCY_" + res["verdict"]
    write_json(rdir / "REZULTATE.json", res)
    print(json.dumps({k: res[k] for k in ("verdict", "gates_passed", "total", "consistency_BR")}, indent=1, default=float))
    return 0


# ---------------------------------------------------------------------------
# Descriptiv (§7)
# ---------------------------------------------------------------------------
def _batched_steps(universes: list[list[np.ndarray]], s: int, device) -> torch.Tensor:
    return torch.as_tensor(np.stack([idx_of(u[s]) for u in universes]), device=device)


def _null_stats(steps, pi, ticket=None) -> dict:
    pred = {"ks": np.arange(WARMUP, len(steps)), "pi": pi,
            "ticket": ticket if ticket is not None else top6(pi)}
    S = score(steps, pred)
    t, h1, h2 = S["total"], S["half1"], S["half2"]
    return {"logPL_U": t["log_PL"] - t["log_U"], "logPL_B": t["log_PL"] - t["log_B"],
            "brier_ok": t["brier_PL"] < min(t["brier_U"], t["brier_B"], t["brier_R"]),
            "halves_logPL_B": [h1["log_PL"] - h1["log_B"], h2["log_PL"] - h2["log_B"]],
            "hits_PL": t["hits_PL"], "hits_PI6": t["hits_PI6"], "excess_PL": t["excess_PL"],
            "hits_B": t["hits_B"], "hits_R": t["hits_R"], "gates_passed": S["gates_passed"],
            "gates": [g["pass"] for g in S["gates"]]}


def run_null_marg(M: int, batch: int = 256) -> int:
    dev = C.resolve_device()
    sizes = real_step_structure()
    rows, t0 = [], time.time()
    for b0 in range(0, M, batch):
        us = [synthetic_steps(sizes, [649, 12, u]) for u in range(b0, min(M, b0 + batch))]
        B = len(us)
        st = C.LinkState(B, dev)
        K = len(sizes)
        PI = np.zeros((B, K - WARMUP, N49))
        for s in range(K):
            if s >= WARMUP:
                g = C.geometry(st.U, st.n)
                PI[:, s - WARMUP] = C.law(g["kappa"])["pi"].cpu().numpy()
            st.add_step(s, _batched_steps(us, s, dev))
        for i in range(B):
            r = _null_stats(us[i], PI[i])
            r["u"] = b0 + i
            r["law_gates_3_4_6"] = [r["gates"][2], r["gates"][3], r["gates"][5]]
            rows.append(r)
        print(f"  nul {b0 + B}/{M}  {time.time() - t0:.0f}s  vram={C.vram().get('max_allocated_MiB', 0):.0f}MiB", flush=True)
    write_json(OUT / "descriptiv" / "NUL_LEGE_1024.json", {"M": M, "seconds": time.time() - t0, "rows": rows,
                                                           "vram": C.vram(), "note": "hits = top-6 după π (fără QUBO)"})
    return 0


def run_null_full(M: int) -> int:
    dev = C.resolve_device()
    sizes = real_step_structure()
    enum = C.Enumerator(dev)
    rows, t0 = [], time.time()
    for u in range(M):
        steps = synthetic_steps(sizes, [649, 12, u])
        wf = walk_forward(steps, dev, enum)
        r = _null_stats(steps, wf["pi"], wf["ticket"])
        r["u"] = u
        rows.append(r)
        print(f"  nul complet {u + 1}/{M}  {time.time() - t0:.0f}s  porți={r['gates_passed']}", flush=True)
        write_json(OUT / "descriptiv" / "NUL_COMPLET_32.json", {"M": M, "done": u + 1, "rows": rows,
                                                                "seconds": time.time() - t0})
    return 0


def run_power(n_each: int = 8) -> int:
    dev = C.resolve_device()
    sizes = real_step_structure()
    enum = C.Enumerator(dev)
    out, t0 = {}, time.time()
    for gamma, base in ((0.5, 1000), (0.125, 2000)):
        rngs = [np.random.default_rng([649, 12, base + u]) for u in range(n_each)]
        B = n_each
        st = C.LinkState(B, dev)
        K = len(sizes)
        steps = [[None] * K for _ in range(B)]
        PI = np.zeros((B, K - WARMUP, N49))
        TK = np.zeros((B, K - WARMUP, K6), dtype=np.int64)
        for s in range(K):
            g = C.geometry(st.U, st.n)
            L = C.law(g["kappa"])
            z = L["z"].cpu().numpy()
            if s >= WARMUP:
                PI[:, s - WARMUP] = L["pi"].cpu().numpy()
                h, J = C.qubo_terms(L["z"], g["eps_edge"])
                for i in range(B):
                    TK[i, s - WARMUP] = enum.minimize(h[i], J[i])["ticket"]
            for i in range(B):
                w = np.exp(-gamma * z[i])
                a = np.zeros((int(sizes[s]), N49))
                for d in range(int(sizes[s])):
                    a[d, rngs[i].choice(N49, K6, replace=False, p=w / w.sum())] = 1.0
                steps[i][s] = a
            st.add_step(s, torch.as_tensor(np.stack([idx_of(steps[i][s]) for i in range(B)]), device=dev))
            if s % 500 == 0:
                print(f"  putere γ={gamma} pas {s}/{K} {time.time() - t0:.0f}s", flush=True)
        out[str(gamma)] = [dict(_null_stats(steps[i], PI[i], TK[i]), u=base + i) for i in range(B)]
        write_json(OUT / "descriptiv" / "PUTERE.json", {"gamma_results": out, "seconds": time.time() - t0})
    return 0


def run_annealer_cert() -> int:
    dev = C.resolve_device()
    rdir = OUT / "backtest_unic"
    pred = np.load(rdir / "PREDICTII.npz")
    steps, _ = load_real()
    ks = pred["ks"]
    cks = [int(k) for k in ks if (k - WARMUP) % CK_EVERY == 0]
    st = C.LinkState(1, dev)
    rows = []
    for s in range(len(steps)):
        if s in cks:
            g = C.geometry(st.U, st.n)
            L = C.law(g["kappa"])
            h, J = C.qubo_terms(L["z"], g["eps_edge"])
            an = C.higgs_anneal(h[0], J[0])
            exact = pred["ticket"][s - WARMUP].tolist()
            best = an["states"][0]
            rows.append({"step": s, "exact": exact, "annealer_best": best["ticket"], "success": best["ticket"] == exact,
                         "replicas_in_exact": next((x["replicas"] for x in an["states"] if x["ticket"] == exact), 0),
                         "n_distinct": an["n_distinct"], "seconds": an["seconds"]})
            print(f"  anealer pas {s}: succes={rows[-1]['success']} replici={rows[-1]['replicas_in_exact']}", flush=True)
        st.add_step(s, torch.as_tensor(idx_of(steps[s]), device=dev)[None])
    write_json(OUT / "descriptiv" / "CERTIFICAT_ANEALER.json",
               {"rows": rows, "success_rate": sum(r["success"] for r in rows) / len(rows), "vram": C.vram()})
    return 0


def final_product(steps=None, meta=None, device=None, frames: int = 24, save: bool = True) -> dict:
    """Starea finală pe toată arhiva + produsul (3 variante) + telemetrie (§7, §9)."""
    dev = device or C.resolve_device()
    if steps is None:
        steps, meta = load_real()
    t0 = time.time()
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    st = C.LinkState(1, dev)
    K = len(steps)
    layouts = []
    for s in range(K):
        st.add_step(s, torch.as_tensor(idx_of(steps[s]), device=dev)[None])
        if s >= K - frames:
            g = C.geometry(st.U, st.n)
            layouts.append({"step": s, "xyz": C.spectral_layout(g["a"][0]).tolist(),
                            "kappa": g["kappa"][0].cpu().tolist(), "A": g["A"][0].cpu().tolist(),
                            "V_total": float(g["V"][0].sum())})
    t_links = time.time() - t0
    enum = C.Enumerator(dev)
    r = C.predict_state(st.U, st.n, enum)
    h, J = r["h"][0], r["J"][0]
    var = enum.variants(h, J, 3)
    an = C.higgs_anneal(h, J)
    mono = C.xy_monopoles(r["z"][0], r["a"][0])
    n_draws = int(sum(x.shape[0] for x in steps))
    nul = C.null_total_area(n_draws, dev)
    a = r["a"][0]
    A_tot = float(a.sum())
    ue = C.unitarity_error(st.U)
    pa = C.PA
    top_e = torch.argsort(r["eps_edge"][0], descending=True)[:60].cpu().numpy()
    out = {"utc": utc_now(), "meta": meta, "n_draws": n_draws, "n_steps": K,
           "variants": [{"ticket": v["ticket"], "E": v["E_base"], "E_penalized": v["E_min"]} for v in var],
           "ground_state_certified_exhaustive": True, "n_tickets_enumerated": enum.total,
           "annealer": {"best": an["states"][:3], "agrees_with_exact_ground_state": an["states"][0]["ticket"] == var[0]["ticket"],
                        "n_distinct": an["n_distinct"], "R": an["R"], "symmetry_breaking_step": an["symmetry_breaking_step"],
                        "trajectory": an["trajectory"], "seconds": an["seconds"]},
           "monopoles_xy": mono,
           "telemetry": {"planck_area_total": A_tot, "planck_area_null_mean": nul["mean"], "planck_area_null_sd": nul["sd"],
                         "planck_area_deviancy": (A_tot - nul["mean"]) / nul["mean"],
                         "planck_area_z": (A_tot - nul["mean"]) / nul["sd"],
                         "holonomy_error": ue, "vram": C.vram(), "seconds_links": t_links,
                         "seconds_total": time.time() - t0},
           "node": {"kappa": r["kappa"][0].cpu().tolist(), "pi": r["pi"][0].cpu().tolist(), "z": r["z"][0].cpu().tolist(),
                    "A": r["A"][0].cpu().tolist(), "V": r["V"][0].cpu().tolist()},
           "area_spectrum": {str(k): int(v) for k, v in zip(*np.unique(st.n[0].cpu().numpy(), return_counts=True))},
           "top_edges": [{"a": int(pa[i]) + 1, "b": int(C.PB[i]) + 1, "eps": float(r["eps_edge"][0, i]),
                          "j": float(st.n[0, i]) / 2} for i in top_e],
           "frames": layouts, "positive_claims_allowed": False,
           "disclaimer": "Calcul clasic pe GPU; termenii fizici sunt inspirație matematică. Variantele sunt minimele exacte ale "
                         "unei energii definite în PL649-P1, nu predicții cu avantaj demonstrat."}
    if save:
        write_json(OUT / "final" / "FINAL.json", out)
    return out


def main(argv: list[str]) -> int:
    if "--qualify" in argv:
        return 0 if qualify()["verdict"] == "PL_QUALIFIED" else 1
    if "--real" in argv:
        return run_real()
    if "--null-marg" in argv:
        return run_null_marg(int(argv[argv.index("--null-marg") + 1]))
    if "--null-full" in argv:
        return run_null_full(int(argv[argv.index("--null-full") + 1]))
    if "--power" in argv:
        return run_power()
    if "--annealer-cert" in argv:
        return run_annealer_cert()
    if "--final" in argv:
        o = final_product()
        print(json.dumps({"variants": o["variants"], "telemetry": {k: v for k, v in o["telemetry"].items() if k != "vram"}},
                         indent=1, default=float))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
