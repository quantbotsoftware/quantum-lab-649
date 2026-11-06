"""TU3-SR — scorul real 5/40 și Joker (taburile 4–5): ecuațiile generalizate, generatorul MPS „Quantum Shadow”
(complex64), puterea sintetică S7 și rularea reală UNICĂ S8 (blocată până la `SR_P_PASS`).

Protocol: `tu3/PROTOCOL_TU3_SR.md` (`7f38a94b…`, sigilat în `SIGILIU_TU3_SR.json` ÎNAINTE de acest cod) + amendamentul
`AMENDAMENT_TU3_SR_01.md` (`3c16f2e0…`, sigilat tot înainte de cod).

- §2: legea marginală, log/Brier/hits, legea nulă hipergeometrică (n, r, k), excesul cu prag relativ, comparatorii B/R,
  cele 6 porți, urna duală Joker (principal (45,5,5) + bila (20,1,1)), SCI generalizat (Σz/√K). Pe (49,6,6) formulele
  reproduc `validare.py` (martorul W1); `validare.py` NU se importă (reimplementare independentă).
- §3: MPS cu nuclee `torch.complex64` — sit de mod (fizic), n situri binare cu legătura (b, c), sit Joker; eșantionare Born
  exactă din mediile drepte (fără vectorul de stare), entropia Schmidt din matricile Gram, tăietura minimă (Edmonds–Karp)
  ca margine de tip rețea tensorială („Ryu–Takayanagi” numai în sensul §0 al protocolului). Nicio ecuație Wheeler–DeWitt.
- `engine.py`, `motor_n.py`, `motor_joker.py`, `parser*.py` se IMPORTĂ nemodificate (punctele standard de apel).

Calcul CLASIC (PyTorch pe GPU, NumPy pe CPU). Variantele motorului sunt minime de energie, NU predicții.
`positive_claims_allowed=false`.

Utilizare:
  .venv/bin/python -B tu3/scor_real.py --putere          # S7, o singură dată (refuză suprascrierea)
  .venv/bin/python -B tu3/scor_real.py --stare
  .venv/bin/python -B tu3/scor_real.py --real 540 --sesiune S8   # NUMAI în S8, după SR_P_PASS
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
for _p in (str(QL), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import motor_joker as MJ  # noqa: E402  (nemodificat)
import motor_n as M  # noqa: E402  (nemodificat)
import parser_multi as PM  # noqa: E402  (nemodificat)

PROTOCOL_FILE = HERE / "PROTOCOL_TU3_SR.md"
SEAL_FILE = HERE / "SIGILIU_TU3_SR.json"
AMEND_FILE = HERE / "AMENDAMENT_TU3_SR_01.md"
AMEND_SEAL_FILE = HERE / "SIGILIU_AMENDAMENT_TU3_SR_01.json"
OUT_DIR = HERE / "rezultate" / "SR"
POWER_FILE = OUT_DIR / "PUTERE_SR.json"
TEST_FILE = QL / "tests" / "test_scor_real.py"

F64, C64, C128 = torch.float64, torch.complex64, torch.complex128
QEPS, LAM0 = 1e-4, 0.5
GAP_BINS = 21
WARMUP = 100
TAU_649 = 0.20                       # pragul porții 1 pe 6/49; scalat relativ (§2.4)
E_649 = 36.0 / 49.0
VRAM_CAP_BYTES = 6.2e9
T_PAUSE, T_RESUME, T_TARGET = 69, 64, 71
T_O6_PAUSE, T_O6_RESUME = 66, 62     # AMENDAMENT_TU3_SR_01 A2
SUB_O15, SUB_O6 = 16, 64             # AMENDAMENT_TU3_SR_01 A2

# Puterea S7 (§5; copiată în SIGILIU_TU3_SR.json `power_design`)
M_NULL = 8192
B_SCI = {"gamma_1_2": 512, "control": 512, "gamma_1_8": 256}
GAMMA_SCI = {"gamma_1_2": 0.5, "control": 0.0, "gamma_1_8": 0.125}
B_WF_SIGNAL, B_WF_NULL, G_GRID = 20, 6, 192
P1_MIN, P2_MAX, P3_MIN, P4_MAX = 0.90, 0.02, 19, 1
BETA, BETA_J = 1.0, 1.0
H_SIZE = 5
ALPHA = 0.01


@dataclass(frozen=True)
class Urn:
    """O urnă: n numere, r extrase, bilet de k numere."""
    name: str
    n: int
    r: int
    k: int

    @property
    def p0(self) -> float:
        return float(self.r) / self.n

    @property
    def e_u(self) -> float:
        """Media hits-urilor sub nul: k r / n (§2.3)."""
        return float(self.k * self.r) / self.n

    @property
    def tau(self) -> float:
        """Pragul porții 1, relativ (§2.4): 0.20 · E_U / (36/49)."""
        return TAU_649 * (self.e_u / E_649)


URN_649 = Urn("649", 49, 6, 6)
URN_540 = Urn("540", 40, 6, 5)
URN_JMAIN = Urn("joker_principal", 45, 5, 5)
URN_JBALL = Urn("joker_bila", 20, 1, 1)
GAMES = {
    "540": dict(urns=(URN_540,), L=2490, tag=540, shape=M.SHAPE_540, cfg=M.PROTOCOL_540,
                seeds_sci=(5407001, 5407002, 5407003, 5407004), seeds_wf=(5407012, 5407014), seed_real_null=5401101,
                alpha_each=0.01, frozen_sha="e1591b8727c09f2350854540b7437eb271c3f850707502c17ff172b95fe62c5c"),
    "joker": dict(urns=(URN_JMAIN, URN_JBALL), L=2202, tag=452, shape=MJ.SHAPE_JOKER, cfg=MJ.PROTOCOL_JOKER,
                  seeds_sci=(4527001, 4527002, 4527003, 4527004), seeds_wf=(4527012, 4527014), seed_real_null=4521101,
                  alpha_each=0.005, frozen_sha="45713aa2146efb725336ca6d40a92690341133ec98b26046bf7cefdf8cfe22bf"),
}


def sha_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ===========================================================================
# §2 — ecuațiile generalizate (NumPy, float64)
# ===========================================================================
def marginal_q(pi: np.ndarray, urn: Urn) -> np.ndarray:
    """q_j = p0 + λ(r π_j − p0), λ = min(0.5, λ_max), q ∈ [1e-4, 1−1e-4] (§2.1)."""
    base = float(urn.r) / urn.n
    d = float(urn.r) * pi - base
    with np.errstate(divide="ignore", invalid="ignore"):
        up = np.where(d > 0, (1 - QEPS - base) / d, np.inf)
        dn = np.where(d < 0, (base - QEPS) / (-d), np.inf)
    lam = np.minimum(LAM0, np.minimum(up.min(-1), dn.min(-1)))[..., None]
    return base + lam * d


def top_k(pi: np.ndarray, k: int) -> np.ndarray:
    """Biletul top-k după π (sortare stabilă după −π ⇒ egalități → numărul mai mic), numere 1..n sortate."""
    order = np.argsort(-pi, axis=-1, kind="stable")
    return np.sort(order[..., :k] + 1, -1)


def score_block(q: np.ndarray, ticket: np.ndarray | None, y: np.ndarray) -> dict:
    log = (y * np.log(q) + (1 - y) * np.log(1 - q)).sum(-1)
    brier = ((q - y) ** 2).sum(-1)
    out = {"log": log, "brier": brier}
    if ticket is not None:
        out["hits"] = np.take_along_axis(y, ticket - 1, axis=1).sum(-1)
    return out


def hyper_pmf(urn: Urn) -> np.ndarray:
    """P(h) = C(k,h) C(n−k, r−h) / C(n,r), h = 0..min(k,r) (§2.3)."""
    n, r, k = urn.n, urn.r, urn.k
    return np.array([math.comb(k, h) * math.comb(n - k, r - h) / math.comb(n, r) for h in range(min(k, r) + 1)])


def exact_tail(total_hits: int, n_targets: int, urn: Urn) -> float:
    """P(H ≥ total_hits) pentru suma a n_targets hits i.i.d. hipergeometrice (convoluție float64, ca validare)."""
    pmf = hyper_pmf(urn)
    dist = np.array([1.0])
    for _ in range(n_targets):
        dist = np.convolve(dist, pmf)
    return float(dist[total_hits:].sum())


def gates(res: dict, urn: Urn) -> list[dict]:
    t, h1, h2 = res["total"], res["half1"], res["half2"]
    tau = urn.tau
    g = [
        ("1", f"ExcesQL/U >= {tau:.7f}", t["excess_QL"] >= tau, t["excess_QL"]),
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


def summarize(sl: slice, S: dict, urn: Urn) -> dict:
    n = int(S["y"][sl].shape[0])
    o = {"targets": n}
    for name in ("QL", "B", "R"):
        o[f"hits_{name}"] = int(S[f"hits_{name}"][sl].sum())
    o["excess_QL"] = o["hits_QL"] / n - urn.e_u if n else 0.0
    o["excess_B"] = o["hits_B"] / n - urn.e_u if n else 0.0
    o["excess_R"] = o["hits_R"] / n - urn.e_u if n else 0.0
    for name in ("QL", "B", "R", "U"):
        o[f"log_{name}"] = float(S[f"log_{name}"][sl].sum())
        o[f"brier_{name}"] = float(S[f"brier_{name}"][sl].sum())
    o["hits_union3_QL"] = int(S["hits_union"][sl].sum())
    o["expected_union3_U"] = n * float(3 * urn.k * urn.r) / float(urn.n)
    return o


def score_component(urn: Urn, y: np.ndarray, pi_ql: np.ndarray, tickets_ql: np.ndarray, union_tickets: np.ndarray,
                    pi_b: np.ndarray, pi_r: np.ndarray, with_tail: bool = True) -> dict:
    """Scorul unei componente pe ținte deja aliniate (rânduri = ținte). tickets_ql [T,k]; union_tickets [T,V,k]."""
    qQL, qB, qR = marginal_q(pi_ql, urn), marginal_q(pi_b, urn), marginal_q(pi_r, urn)
    qU = np.full_like(y, float(urn.r) / urn.n)
    tB, tR = top_k(pi_b, urn.k), top_k(pi_r, urn.k)
    S = {"y": y}
    for name, q, t in (("QL", qQL, tickets_ql), ("B", qB, tB), ("R", qR, tR), ("U", qU, None)):
        sb = score_block(q, t, y)
        S[f"log_{name}"], S[f"brier_{name}"] = sb["log"], sb["brier"]
        if t is not None:
            S[f"hits_{name}"] = sb["hits"]
    uni = np.zeros_like(y)
    for v in range(union_tickets.shape[1]):
        np.put_along_axis(uni, union_tickets[:, v, :] - 1, 1.0, axis=1)
    S["hits_union"] = (uni * y).sum(-1)
    n = y.shape[0]
    h = n // 2
    res = {"urn": {"name": urn.name, "n": urn.n, "r": urn.r, "k": urn.k, "E_U": urn.e_u, "tau": urn.tau},
           "total": summarize(slice(0, n), S, urn), "half1": summarize(slice(0, h), S, urn),
           "half2": summarize(slice(h, n), S, urn)}
    res["total"]["expected_union3_exact"] = float(uni.sum() * urn.r / urn.n)
    res["gates"] = gates(res, urn)
    res["gates_passed"] = sum(g["pass"] for g in res["gates"])
    mlen = min(urn.k, urn.r) + 1
    res["match_dist_QL_v1"] = np.bincount(S["hits_QL"].astype(int), minlength=mlen)[:mlen].tolist()
    res["match_expected_U"] = (hyper_pmf(urn) * n).tolist()
    if with_tail:
        res["p_exact_hits_QL_ge"] = exact_tail(int(S["hits_QL"].sum()), n, urn)
    res["n_targets"] = int(n)
    res["tickets_changed_vs_B"] = int((tickets_ql != tB).any(-1).sum())
    res["_per_target"] = {k_: S[k_] for k_ in ("hits_QL", "hits_B", "hits_R", "hits_union")}
    return res


def target_rows(step_offsets: np.ndarray, ks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rândurile-țintă (extragerile pașilor ks) și indicele pasului prezis pentru fiecare."""
    rows, kidx = [], []
    for i, k in enumerate(ks):
        for r in range(step_offsets[k], step_offsets[k + 1]):
            rows.append(r)
            kidx.append(i)
    return np.array(rows, dtype=np.int64), np.array(kidx, dtype=np.int64)


def score_649_from_file(onehot: np.ndarray, step_offsets: np.ndarray, pred_path: Path) -> dict:
    """Martorul W1: scorul generalizat pe PREDICTII.npz al QL649 (aceleași câmpuri ca validare.score_from_file)."""
    P = np.load(pred_path)
    ks = P["ks"]
    rows, kidx = target_rows(step_offsets, ks)
    y = onehot[rows].astype(np.float64)
    tQL = P["variants"][:, 0, :][kidx]
    res = score_component(URN_649, y, P["pi_QL"][kidx], tQL, P["variants"][kidx], P["piB"][kidx], P["piR"][kidx])
    res["verdict"] = "QL_PROMOVAT_EXPLORATORIU" if res["gates_passed"] == 6 else "QL_NO_PROMOTION_EXPLORATORY"
    res["n_steps_predicted"] = int(len(ks))
    pt = res.pop("_per_target")
    res["per_target"] = {k_: v.astype(int).tolist() for k_, v in pt.items()}
    res["per_target"]["step"] = ks[kidx].astype(int).tolist()
    return res


def detection_d1(game: str, comps: list[dict]) -> dict:
    """D1 (§4.3): 5/40 p ≤ 0.01; Joker min(p_principal, p_bilă) ≤ 0.005 (Bonferroni)."""
    a = GAMES[game]["alpha_each"]
    ps = [c["p_exact_hits_QL_ge"] for c in comps]
    det = any(p <= a for p in ps)
    return {"alpha_each": a, "p_values": ps, "detected": bool(det),
            "verdict": "SR_DETECTIE_EXPLORATORIE" if det else "SR_FARA_DETECTIE"}


# ===========================================================================
# §2.9 — SCI generalizat (PyTorch)
# ===========================================================================
def step_presence(onehot: torch.Tensor, step_index: torch.Tensor, n_steps: int) -> torch.Tensor:
    Mu, _, n = onehot.shape
    out = torch.zeros(Mu, n_steps, n, device=onehot.device, dtype=onehot.dtype)
    out.index_add_(1, step_index, onehot)
    return out


def sci_raw(onehot: torch.Tensor, step_index: torch.Tensor, step_sizes: torch.Tensor, n_steps: int, r: int) -> dict:
    """Statisticile brute ale unei urne (n, r) pe M universuri: χ² frecvențe, χ² perechi (r ≥ 2), histograme de goluri,
    suprapunere serială. Pe (49, 6) aceeași ordine a operațiilor ca `validare.sci_raw`."""
    Mu, Nd, n = onehot.shape
    oh = onehot.to(torch.float32)
    c = oh.sum(1).to(F64)
    e1 = float(r) * Nd / n
    out = {"chi_freq": ((c - e1) ** 2 / e1).sum(-1)}
    if r >= 2:
        C = torch.bmm(oh.transpose(1, 2), oh).to(F64)
        iu = torch.triu_indices(n, n, 1, device=oh.device)
        pc = C[:, iu[0], iu[1]]
        e2 = Nd * float(r * (r - 1)) / float(n * (n - 1))
        out["chi_pair"] = ((pc - e2) ** 2 / e2).sum(-1)
        del C, pc
    pres = step_presence(oh, step_index, n_steps)
    s_ar = torch.arange(n_steps, device=oh.device)[None, :, None].expand(Mu, -1, n)
    marks = torch.where(pres > 0, s_ar, torch.full_like(s_ar, -1))
    last = torch.cummax(marks, 1).values
    prev = torch.cat([torch.full_like(last[:, :1], -1), last[:, :-1]], 1)
    valid = (pres > 0) & (prev >= 0)
    gap = (s_ar - prev).clamp(min=1, max=GAP_BINS) - 1
    num_ar = torch.arange(n, device=oh.device)[None, None, :].expand(Mu, n_steps, -1)
    uni_ar = torch.arange(Mu, device=oh.device)[:, None, None].expand(-1, n_steps, n)
    flat = (uni_ar * n + num_ar) * GAP_BINS + gap
    hist = torch.zeros(Mu * n * GAP_BINS, device=oh.device, dtype=F64)
    hist.index_add_(0, flat[valid], torch.ones(int(valid.sum()), device=oh.device, dtype=F64))
    out["gap_hist"] = hist.view(Mu, n, GAP_BINS)
    del marks, last, prev, valid, gap, num_ar, uni_ar, flat
    sz = step_sizes.to(F64)
    v = pres.to(F64)
    ov = (v[:, :-1] * v[:, 1:]).sum(-1) / (sz[:-1] * sz[1:])[None]
    out["overlap"] = ov.mean(-1)
    return out


def cross_chi(main_oh: torch.Tensor, joker_oh: torch.Tensor, r: int, n: int, m: int) -> torch.Tensor:
    """χ² al tabelului N_ja (n × m) față de E = N·(r/n)·(1/m) (§2.9)."""
    Nd = main_oh.shape[1]
    N = torch.bmm(main_oh.to(torch.float32).transpose(1, 2), joker_oh.to(torch.float32)).to(F64)
    E = Nd * (float(r) / n) * (1.0 / m)
    return ((N - E) ** 2 / E).sum((-1, -2))


STAT_ORDER = ("chi_freq", "chi_pair", "chi_gap", "overlap")


def stat_names(game: str) -> list[str]:
    if game == "649":
        return list(STAT_ORDER)
    if game == "540":
        return [f"main.{s}" for s in STAT_ORDER]
    return [f"main.{s}" for s in STAT_ORDER] + ["ball.chi_freq", "ball.chi_gap", "ball.overlap", "cross.chi"]


def raw_stats_game(game: str, main_oh, joker_oh, step_index, sizes, n_steps) -> dict:
    """Statisticile brute (fără χ²_goluri, care cere media nulului) pentru un lot de universuri."""
    urn = URN_649 if game == "649" else GAMES[game]["urns"][0]
    rm = sci_raw(main_oh, step_index, sizes, n_steps, urn.r)
    pre = "" if game == "649" else "main."
    out = {f"{pre}chi_freq": rm["chi_freq"], f"{pre}chi_pair": rm["chi_pair"], f"{pre}overlap": rm["overlap"],
           f"{pre}gap_hist": rm["gap_hist"]}
    if game == "joker":
        rb = sci_raw(joker_oh, step_index, sizes, n_steps, 1)
        out.update({"ball.chi_freq": rb["chi_freq"], "ball.overlap": rb["overlap"], "ball.gap_hist": rb["gap_hist"],
                    "cross.chi": cross_chi(main_oh, joker_oh, URN_JMAIN.r, URN_JMAIN.n, URN_JBALL.n)})
    return out


def _gchi(h: torch.Tensor, ebar: torch.Tensor) -> torch.Tensor:
    return ((h - ebar) ** 2 / ebar).sum((-1, -2))


def sci_reference(game: str, null_batches, M_total: int) -> dict:
    """Referința nulă: statisticile pe M universuri (generate de `null_batches`, iterator de (main_oh, joker_oh)),
    media golurilor, mediile/abaterile, distribuția SCI nulă. Aceeași aritmetică ca `validare.compute_sci`."""
    parts: dict[str, list] = {}
    for main_oh, joker_oh, step_index, sizes, n_steps in null_batches:
        r = raw_stats_game(game, main_oh, joker_oh, step_index, sizes, n_steps)
        for k_, v in r.items():
            parts.setdefault(k_, []).append(v)
        del r
    nul = {k_: torch.cat(v, 0) for k_, v in parts.items()}
    assert next(iter(nul.values())).shape[0] == M_total
    ebar = {}
    for pre in ("", "main.", "ball."):
        if f"{pre}gap_hist" in nul:
            ebar[pre] = nul[f"{pre}gap_hist"].mean(0).clamp(min=1e-12)
            nul[f"{pre}chi_gap"] = _gchi(nul.pop(f"{pre}gap_hist"), ebar[pre])
    names = stat_names(game)
    mu, sd = {}, {}
    zn = torch.zeros(M_total, dtype=F64, device=nul[names[0]].device)
    for k_ in names:
        v = nul[k_]
        mu[k_], sd[k_] = float(v.mean()), float(v.std())
        zn = zn + (v - mu[k_]) / sd[k_]
    K = len(names)
    sci_null = zn / math.sqrt(K)
    return {"names": names, "K": K, "M": M_total, "mu": mu, "sd": sd, "ebar": ebar, "sci_null": sci_null,
            "null_stats": nul}


def sci_evaluate(game: str, raw: dict, ref: dict) -> dict:
    """z, SCI, p empiric pentru un lot de universuri față de referința nulă."""
    st = dict(raw)
    for pre, eb in ref["ebar"].items():
        st[f"{pre}chi_gap"] = _gchi(st.pop(f"{pre}gap_hist"), eb)
    z = {}
    tot = None
    for k_ in ref["names"]:
        z[k_] = (st[k_] - ref["mu"][k_]) / ref["sd"][k_]
        tot = z[k_] if tot is None else tot + z[k_]
    sci = tot / math.sqrt(ref["K"])
    sn = ref["sci_null"]
    p = (1 + (sn[None, :] >= sci[:, None]).sum(-1)).to(F64) / (ref["M"] + 1)
    return {"stats": st, "z": z, "SCI": sci, "p": p}


def legacy_topk_null(M_total: int, n_draws: int, n: int, r: int, seed: int, device, chunk: int = 256):
    """Eșantionatorul „legacy” al lui validare (rand + topk), numai pentru martorul W1 pe 6/49."""
    gen = torch.Generator(device=device).manual_seed(seed)
    for s0 in range(0, M_total, chunk):
        m = min(chunk, M_total - s0)
        keys = torch.rand(m, n_draws, n, generator=gen, device=device)
        idx = keys.topk(r, dim=-1).indices
        oh = torch.zeros(m, n_draws, n, device=device, dtype=torch.float32)
        oh.scatter_(2, idx, 1.0)
        yield oh


def sci_649_identity(ds, M_total: int = 8192, seed: int = 649) -> dict:
    """W1: SCI generalizat pe 6/49 cu eșantionatorul legacy (aceleași apeluri RNG ca validare.compute_sci)."""
    dev = ds.device
    sidx = ds.step_index.to(dev)
    sizes = (ds.step_offsets[1:] - ds.step_offsets[:-1]).to(dev)
    real = raw_stats_game("649", ds.onehot.to(dev)[None], None, sidx, sizes, ds.n_steps)
    batches = ((oh, None, sidx, sizes, ds.n_steps) for oh in legacy_topk_null(M_total, ds.n_draws, 49, 6, seed, dev))
    ref = sci_reference("649", batches, M_total)
    ev = sci_evaluate("649", real, ref)
    return {"stats_real": {k_: float(ev["stats"][k_][0]) for k_ in STAT_ORDER},
            "null_mean": ref["mu"], "null_std": ref["sd"], "z": {k_: float(v[0]) for k_, v in ev["z"].items()},
            "SCI": float(ev["SCI"][0]), "p_empirical": float(ev["p"][0])}


# ===========================================================================
# §3 — MPS „Quantum Shadow” (complex64)
# ===========================================================================
class UrnMPS:
    """MPS al purificării |Ψ⟩ = Σ_b √p_b |b⟩ ⊗ |ψ_b⟩_principal (⊗ |χ_b⟩_Joker) (AMENDAMENT_TU3_SR_01 A1).

    Situri: [mod b] + n situri binare (legătura (b, c), c = 0..r) [+ sit Joker a ∈ 1..m]. Nucleele au forma
    [Bc, D_stânga, d, D_dreapta] (Bc = 1 dacă toate universurile au aceleași nuclee — fără copii redundante).
    """

    def __init__(self, n: int, r: int, gamma: float = 0.0, H: torch.Tensor | None = None, beta: float = BETA,
                 m: int | None = None, a_star: torch.Tensor | None = None, beta_j: float = BETA_J,
                 phases: bool = True, device=None, n_univ: int = 1):
        dev = torch.device(device) if device is not None else torch.device("cpu")
        self.n, self.r, self.m, self.device = n, r, m, dev
        self.gamma = float(gamma)
        modes = [0] if self.gamma == 0.0 else [0, 1]     # blocul b = 1 eliminat sub nul (§3.2)
        self.modes = modes
        nm, R1 = len(modes), r + 1
        D = nm * R1
        self.D = D
        Bc = n_univ if (self.gamma > 0 and (H is not None or a_star is not None)) else 1
        self.Bc, self.n_univ = Bc, n_univ
        # ponderile siturilor binare pe mod: w[b] [Bc, n]
        w = torch.ones(Bc, nm, n, dtype=torch.float32, device=dev)
        if nm == 2 and H is not None:
            inH = torch.zeros(Bc, n, dtype=torch.float32, device=dev)
            inH.scatter_(1, H.to(dev, torch.int64), 1.0)
            w[:, 1] = torch.exp(beta * inH)
        phi = (2 * math.pi * torch.arange(n, device=dev, dtype=torch.float32) / n) if phases else \
            torch.zeros(n, device=dev)
        cores = []
        # situl de mod: [Bc, 1, nm, D]; amplitudinile se normalizează după mediile drepte
        mode_core = torch.zeros(Bc, 1, nm, D, dtype=C64, device=dev)
        for bi in range(nm):
            mode_core[:, 0, bi, bi * R1 + 0] = 1.0
        cores.append(mode_core)
        for j in range(n):
            A = torch.zeros(Bc, D, 2, D, dtype=C64, device=dev)
            e = torch.exp(1j * phi[j].to(C64)) if phases else torch.ones((), dtype=C64, device=dev)
            for bi in range(nm):
                for c in range(R1):
                    A[:, bi * R1 + c, 0, bi * R1 + c] = 1.0
                    if c < r:
                        A[:, bi * R1 + c, 1, bi * R1 + c + 1] = torch.sqrt(w[:, bi, j]).to(C64) * e
            cores.append(A)
        if m is not None:
            v = torch.ones(Bc, nm, m, dtype=torch.float64, device=dev)
            phj = 2 * math.pi * torch.arange(m, device=dev, dtype=torch.float64) / m
            if nm == 2 and a_star is not None:
                v[:, 1] = torch.exp(beta_j * torch.cos(phj[None, :] - phj[a_star.to(dev, torch.int64)][:, None]))
            v = v / v.sum(-1, keepdim=True)
            Aj = torch.zeros(Bc, D, m, 1, dtype=C64, device=dev)
            ej = torch.exp(1j * phj).to(C64) if phases else torch.ones(m, dtype=C64, device=dev)
            for bi in range(nm):
                Aj[:, bi * R1 + r, :, 0] = torch.sqrt(v[:, bi]).to(C64) * ej[None]
            cores.append(Aj)
            rb = torch.ones(1, dtype=C64, device=dev)
        else:
            rb = torch.zeros(D, dtype=C64, device=dev)
            for bi in range(nm):
                rb[bi * R1 + r] = 1.0
        self.cores, self.rb = cores, rb
        self._environments()
        # normalizarea amplitudinilor de mod: P(b) = p_b exact (A1)
        pb = [1.0 - self.gamma, self.gamma] if nm == 2 else [1.0]
        R1env = self.R[1]                                                   # [Bc, D, D]
        for bi in range(nm):
            Zb = R1env[:, bi * R1, bi * R1].real.clamp(min=1e-30)          # Σ_S ∏ w = e_r(w^{(b)})
            self.cores[0][:, 0, bi, bi * R1] = torch.sqrt(pb[bi] / Zb).to(C64)
        self.R[0] = self._env_step(self.cores[0], self.R[1])
        self.Z = {bi: float(R1env[0, bi * R1, bi * R1].real) for bi in range(nm)}

    @staticmethod
    def _env_step(A: torch.Tensor, Rn: torch.Tensor) -> torch.Tensor:
        # R_j = Σ_s A^s R_{j+1} A^{s†}
        T = torch.einsum("bdse,bef->bdsf", A, Rn)
        return torch.einsum("bdsf,bgsf->bdg", T, A.conj())

    def _environments(self):
        rb = self.rb
        Rn = (rb[:, None] * rb.conj()[None, :])[None].expand(self.Bc, -1, -1).contiguous()
        R = [None] * (len(self.cores) + 1)
        R[len(self.cores)] = Rn
        for j in range(len(self.cores) - 1, -1, -1):
            R[j] = self._env_step(self.cores[j], R[j + 1])
        self.R = R

    def left_grams(self) -> list[torch.Tensor]:
        """L_0 = [[1]], L_{j+1} = Σ_s A^{s†} L_j A^s."""
        L = [torch.ones(self.Bc, 1, 1, dtype=C64, device=self.device)]
        for A in self.cores:
            T = torch.einsum("bde,bdsf->besf", L[-1], A)
            L.append(torch.einsum("besf,besg->bfg", A.conj(), T))
        return L

    def sample(self, n_draws: int, gen: torch.Generator, n_univ: int | None = None) -> dict:
        """Eșantionare Born exactă (perfectă), stânga → dreapta, fără vectorul de stare. Întoarce indicatorii
        principali [B,T,n] (float32), bila Joker [B,T] (0..m−1) și modul [B,T]."""
        B = self.n_univ if n_univ is None else n_univ
        dev = self.device
        l = torch.ones(B, n_draws, 1, dtype=C64, device=dev)
        out_bits = torch.zeros(B, n_draws, self.n, dtype=torch.float32, device=dev)
        mode = joker = None
        for j, A in enumerate(self.cores):
            Ab = A.expand(B, -1, -1, -1) if A.shape[0] != B else A
            Rn = self.R[j + 1]
            Rb = Rn.expand(B, -1, -1) if Rn.shape[0] != B else Rn
            v = torch.einsum("btd,bdse->btse", l, Ab)
            w = torch.einsum("btse,bef->btsf", v, Rb)
            p = (w * v.conj()).sum(-1).real.clamp(min=0.0)                    # [B,T,d]
            del w
            cum = torch.cumsum(p, -1)
            u = torch.rand(B, n_draws, generator=gen, device=dev) * cum[..., -1]
            s = (cum < u[..., None]).sum(-1).clamp(max=p.shape[-1] - 1)      # [B,T]
            ps = p.gather(-1, s[..., None])[..., 0].clamp(min=1e-30)
            l = v.gather(2, s[..., None, None].expand(-1, -1, 1, v.shape[-1]))[:, :, 0, :] / torch.sqrt(ps)[..., None]
            del v, p, cum, u
            if j == 0:
                mode = s
            elif j <= self.n:
                out_bits[:, :, j - 1] = s.to(torch.float32)
            else:
                joker = s
        return {"main": out_bits, "joker": joker, "mode": mode}

    def schmidt(self, bond: int, L: list | None = None) -> dict:
        """Spectrul Schmidt la legătura `bond` (între situl bond−1 și situl bond): eig(L^{1/2} R L^{1/2})."""
        L = self.left_grams() if L is None else L
        Lb = L[bond].to(C128)
        Rb = self.R[bond].to(C128)
        ev, U = torch.linalg.eigh(Lb)
        sq = U @ torch.diag_embed(ev.clamp(min=0).sqrt().to(C128)) @ U.conj().transpose(-1, -2)
        Mx = sq @ Rb @ sq
        lam = torch.linalg.eigvalsh(Mx).clamp(min=0)
        lam = lam / lam.sum(-1, keepdim=True)
        S = -(torch.where(lam > 0, lam * torch.log(lam), torch.zeros_like(lam))).sum(-1)
        dl, dr = Lb.diagonal(dim1=-2, dim2=-1).real, Rb.diagonal(dim1=-2, dim2=-1).real
        tol_l = 1e-12 * dl.amax(-1, keepdim=True)
        tol_r = 1e-12 * dr.amax(-1, keepdim=True)
        chi_eff = ((dl > tol_l) & (dr > tol_r)).sum(-1)
        return {"lambda": lam, "S": S, "chi_eff": chi_eff}

    def joker_cut(self) -> dict:
        """Tăietura (mod + urna principală | urna Joker): S, χ_eff și min-cut-ul (Edmonds–Karp) pe lanț."""
        if self.m is None:
            raise ValueError("fără urna Joker")
        L = self.left_grams()
        n_sites = len(self.cores)
        caps = []
        chis = []
        for bond in range(1, n_sites):
            sc = self.schmidt(bond, L)
            chis.append(sc["chi_eff"])
            if bond == n_sites - 1:
                cut = sc
        S = cut["S"].real
        mincuts = []
        for u in range(S.shape[0]):
            caps = [math.log(max(int(c[u].item()), 1)) for c in chis]
            mincuts.append(min_cut_chain(caps, n_sites, region_a=range(0, n_sites - 1)))
        return {"S": S, "chi_eff": cut["chi_eff"], "min_cut": torch.tensor(mincuts, dtype=F64)}


def min_cut_chain(caps: list[float], n_sites: int, region_a) -> float:
    """Tăietura minimă (max-flow, Edmonds–Karp) între regiunea A și restul, pe graful lanțului cu muchiile
    (i−1, i) de capacitate caps[i−1] (= ln χ_eff al legăturii). Sursă/destinație virtuale cu capacitate infinită."""
    A = set(region_a)
    src, snk = n_sites, n_sites + 1
    INF = float("inf")
    cap: dict[tuple[int, int], float] = {}

    def add(u, v, c):
        cap[(u, v)] = cap.get((u, v), 0.0) + c
        cap.setdefault((v, u), 0.0)

    for i in range(1, n_sites):
        add(i - 1, i, caps[i - 1])
        add(i, i - 1, caps[i - 1])
    for i in range(n_sites):
        add(src, i, INF) if i in A else add(i, snk, INF)
    adj: dict[int, list[int]] = {}
    for (u, v) in cap:
        adj.setdefault(u, []).append(v)
    flow = 0.0
    while True:
        par = {src: None}
        q = [src]
        while q and snk not in par:
            u = q.pop(0)
            for v in adj.get(u, []):
                if v not in par and cap[(u, v)] > 1e-15:
                    par[v] = u
                    q.append(v)
        if snk not in par:
            return flow
        f, v = INF, snk
        while par[v] is not None:
            f = min(f, cap[(par[v], v)])
            v = par[v]
        if f == INF:
            return INF
        v = snk
        while par[v] is not None:
            cap[(par[v], v)] -= f
            cap[(v, par[v])] += f
            v = par[v]
        flow += f


def dicke_profile(n: int, r: int, device=None) -> dict:
    """Profilul de entanglement intra-urnă al stării Dicke |D^n_r⟩ (nul): S după j situri vs entropia hipergeometrică."""
    mps = UrnMPS(n, r, 0.0, device=device)
    L = mps.left_grams()
    S_mps, S_exact, bound = [], [], []
    for j in range(1, n):
        sc = mps.schmidt(1 + j, L)
        S_mps.append(float(sc["S"][0]))
        lam = [math.comb(j, c) * math.comb(n - j, r - c) / math.comb(n, r) for c in range(0, r + 1)]
        S_exact.append(-sum(x * math.log(x) for x in lam if x > 0))
        bound.append(math.log(min(j, r, n - j) + 1))
    return {"S_mps": S_mps, "S_exact": S_exact, "bound": bound,
            "max_abs_err": max(abs(a - b) for a, b in zip(S_mps, S_exact))}


def mps_universes(game: str, B: int, L: int, gamma: float, gen: torch.Generator, device) -> dict:
    """B universuri × L extrageri ale jocului din MPS (§3); H și a* uniform (din `gen`)."""
    urn = GAMES[game]["urns"][0]
    H = a_star = None
    if gamma > 0:
        H = torch.rand(B, urn.n, generator=gen, device=device).argsort(-1)[:, :H_SIZE]
        if game == "joker":
            a_star = torch.randint(0, URN_JBALL.n, (B,), generator=gen, device=device)
    mps = UrnMPS(urn.n, urn.r, gamma, H=H, m=(URN_JBALL.n if game == "joker" else None), a_star=a_star,
                 device=device, n_univ=B)
    smp = mps.sample(L, gen, n_univ=B)
    jo = None
    if game == "joker":
        jo = torch.zeros(B, L, URN_JBALL.n, dtype=torch.float32, device=device)
        jo.scatter_(2, smp["joker"][..., None], 1.0)
    return {"main": smp["main"], "joker_oh": jo, "joker": smp["joker"], "mode": smp["mode"], "H": H,
            "a_star": a_star, "mps": mps}


# ===========================================================================
# §3.7 — resurse: plafonul VRAM și monitorul termic
# ===========================================================================
def apply_vram_cap(device) -> dict:
    dev = torch.device(device)
    if dev.type != "cuda":
        return {"applied": False}
    idx = dev.index if dev.index is not None else torch.cuda.current_device()
    total = torch.cuda.get_device_properties(idx).total_memory
    frac = VRAM_CAP_BYTES / total
    torch.cuda.set_per_process_memory_fraction(frac, idx)
    return {"applied": True, "cap_bytes": VRAM_CAP_BYTES, "total_bytes": int(total), "fraction": frac}


def nvidia_smi_temp() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10)
        return int(out.stdout.strip().splitlines()[0])
    except Exception:  # noqa: BLE001
        return None


class ThermalGuard:
    """Citește temperatura GPU la fiecare `period` s (fir separat) și face pauză între loturi (§3.7, A2)."""

    def __init__(self, reader=nvidia_smi_temp, period: float = 1.0, sleep=time.sleep, start: bool = True, log=print):
        self.reader, self.period, self.sleep, self.log = reader, period, sleep, log
        self.current = reader()
        self.t_max = self.current if self.current is not None else -1
        self.samples = 1
        self.pauses, self.pause_s = 0, 0.0
        self._stop = threading.Event()
        self._th = None
        if start:
            self._th = threading.Thread(target=self._run, daemon=True)
            self._th.start()

    def _poll(self):
        t = self.reader()
        if t is not None:
            self.current = t
            self.t_max = max(self.t_max, t)
            self.samples += 1
        return t

    def _run(self):
        while not self._stop.is_set():
            self._poll()
            self._stop.wait(self.period)

    def wait(self, kind: str = "general"):
        pause_at, resume_at = (T_O6_PAUSE, T_O6_RESUME) if kind == "o6" else (T_PAUSE, T_RESUME)
        if self._th is None:
            self._poll()
        if self.current is None or self.current < pause_at:
            return False
        self.pauses += 1
        t0 = time.perf_counter()
        self.log(f"[termic] {self.current} °C ≥ {pause_at} ({kind}) ⇒ pauză până la ≤ {resume_at} °C")
        while self.current is not None and self.current > resume_at:
            self.sleep(self.period)
            if self._th is None:
                self._poll()
        self.pause_s += time.perf_counter() - t0
        return True

    def stop(self) -> dict:
        self._stop.set()
        if self._th is not None:
            self._th.join(timeout=5)
        return {"t_max_c": self.t_max, "samples": self.samples, "pauses": self.pauses,
                "pause_seconds": round(self.pause_s, 1), "temperature_target_met": bool(self.t_max < T_TARGET),
                "rule": {"general": [T_PAUSE, T_RESUME], "o6": [T_O6_PAUSE, T_O6_RESUME], "target_lt": T_TARGET}}


class _NoGuard:
    def wait(self, kind="general"):
        return False


@contextlib.contextmanager
def forbid_real_archive():
    """Garda S7 (§5): orice încercare de a citi arhiva reală 5/40/Joker/6-49 aruncă excepție."""
    import parser as QP

    def _forbidden(*a, **k):
        raise RuntimeError("TU3-SR S7: citirea arhivei reale este interzisă în calea de putere sintetică")

    saved = {(PM, n_): getattr(PM, n_) for n_ in ("build_game_dataset", "resolve_frozen", "resolve_live")}
    saved[(QP, "build_dataset")] = QP.build_dataset
    try:
        for (mod, n_) in saved:
            setattr(mod, n_, _forbidden)
        yield
    finally:
        for (mod, n_), f in saved.items():
            setattr(mod, n_, f)


# ===========================================================================
# Mersul înainte cu motorul (S7 pe sintetic, S8 pe real)
# ===========================================================================
def synth_dataset(game: str, main_oh: torch.Tensor, joker_oh: torch.Tensor | None):
    """Set sintetic minimal pentru `motor_n.Prefix`: o extragere pe pas."""
    urn = GAMES[game]["urns"][0]
    L = main_oh.shape[0]
    dev = main_oh.device
    draws = torch.sort(main_oh.topk(urn.r, dim=-1).indices, dim=-1).values + 1
    return SimpleNamespace(onehot=main_oh.to(torch.float32), draws=draws.to(torch.int64),
                           step_index=torch.arange(L, device=dev), step_offsets=torch.arange(L + 1, device=dev),
                           n_steps=L, n_draws=L, device=dev, joker_onehot=joker_oh,
                           game=SimpleNamespace(code=game), source_sha256="synthetic")


def _ew_steps(step_counts: torch.Tensor, n_steps: int, half_life: float) -> torch.Tensor:
    decay = 2.0 ** (-1.0 / half_life)
    ew = torch.zeros(n_steps + 1, step_counts.shape[1], device=step_counts.device, dtype=F64)
    for s in range(1, n_steps + 1):
        ew[s] = ew[s - 1] * decay + step_counts[s - 1]
    return ew


def wf_predict(ds, game: str, ks: torch.Tensor, cfg=None, seeds: torch.Tensor | None = None, guard=None,
               log=print) -> dict:
    """Predicțiile cauzale la pașii ks: π_QL, variantele, π_B, π_R; la Joker și π_J = q_{V1}, Joker-ii, π_B/π_R ai bilei.
    `seeds is None` ⇒ semințele `step_seed(cfg, k)` (S8, `score_steps`); altfel semințele date (S7, `score_states`)."""
    G = GAMES[game]
    shape = G["shape"]
    cfg = G["cfg"] if cfg is None else cfg
    guard = _NoGuard() if guard is None else guard
    dev = ds.device
    ks = ks.to(dev, torch.int64)
    pre = M.Prefix(ds, shape, cfg, dev)
    pis, As, cs, ews = [], [], [], []
    for s0 in range(0, ks.shape[0], SUB_O15):
        kb = ks[s0:s0 + SUB_O15]
        guard.wait("general")
        if seeds is None:
            sc = M.score_steps(pre, kb, cfg, chunk=SUB_O15)
        else:
            st = pre.state(kb)
            sc = M.score_states(st, seeds[s0:s0 + SUB_O15].to(dev), shape, cfg, chunk=SUB_O15)
        pis.append(sc["pi"])
        As.append(sc["A"])
        st2 = pre.state(kb)
        cs.append(st2["c"])
        ews.append(st2["ew"])
        del sc
    pi, A = torch.cat(pis, 0), torch.cat(As, 0)
    vs = []
    for s0 in range(0, ks.shape[0], SUB_O6):
        guard.wait("general")
        guard.wait("o6")
        sl = slice(s0, s0 + SUB_O6)
        vv = M.variants_steps(pi[sl], A[sl], ks[sl], shape, cfg, seeds=None if seeds is None else seeds[sl].to(dev))
        vs.append(vv["variants"])
    variants = torch.cat(vs, 0)
    c, ew = torch.cat(cs, 0).cpu().numpy(), torch.cat(ews, 0).cpu().numpy()
    out = {"ks": ks.cpu().numpy(), "pi_QL": pi.cpu().numpy(), "variants": variants.cpu().numpy().astype(np.int64),
           "piB": (c + 1.0) / (c + 1.0).sum(-1, keepdims=True), "piR": (ew + 0.5) / (ew + 0.5).sum(-1, keepdims=True)}
    if game == "joker":
        oh = ds.onehot.to(dev, F64)
        jo = ds.joker_onehot.to(dev, F64)
        off = ds.step_offsets.to(dev)
        cumX = torch.zeros(oh.shape[0] + 1, oh.shape[1], jo.shape[1], dtype=F64, device=dev)
        cumX[1:] = torch.cumsum(oh[:, :, None] * jo[:, None, :], 0)
        cumJ = torch.zeros(oh.shape[0] + 1, jo.shape[1], dtype=F64, device=dev)
        cumJ[1:] = torch.cumsum(jo, 0)
        Nk = cumX[off[ks]]                                                  # [S,45,20], pașii < k
        js = MJ.joker_stage(Nk, variants, cfg)
        cntJ = torch.zeros(ds.n_steps, jo.shape[1], dtype=F64, device=dev)
        cntJ.index_add_(0, ds.step_index.to(dev), jo)
        ewJ = _ew_steps(cntJ, ds.n_steps, cfg.ew_half_life)[ks].cpu().numpy()
        cJ = cumJ[off[ks]].cpu().numpy()
        out.update({"pi_J": js["q"][:, 0, :].cpu().numpy(), "jokers": js["jokers"].cpu().numpy().astype(np.int64),
                    "piB_J": (cJ + 1.0) / (cJ + 1.0).sum(-1, keepdims=True),
                    "piR_J": (ewJ + 0.5) / (ewJ + 0.5).sum(-1, keepdims=True)})
        del cumX, Nk
    return out


def score_predictions(game: str, pred: dict, main_oh: np.ndarray, joker_oh: np.ndarray | None,
                      step_offsets: np.ndarray, with_tail: bool = True) -> list[dict]:
    """Componentele scorate (5/40: una; Joker: principal + bilă) pe țintele pașilor `pred['ks']`."""
    rows, kidx = target_rows(step_offsets, pred["ks"])
    urns = GAMES[game]["urns"]
    y = main_oh[rows].astype(np.float64)
    V = pred["variants"][kidx]
    comps = [score_component(urns[0], y, pred["pi_QL"][kidx], V[:, 0, :], V, pred["piB"][kidx], pred["piR"][kidx],
                             with_tail)]
    if game == "joker":
        yj = joker_oh[rows].astype(np.float64)
        J = pred["jokers"][kidx]
        comps.append(score_component(urns[1], yj, pred["pi_J"][kidx], J[:, :1], J[:, :, None], pred["piB_J"][kidx],
                                     pred["piR_J"][kidx], with_tail))
    return comps


def promotion(comps: list[dict]) -> str:
    return "SR_PROMOVAT_EXPLORATORIU" if all(c["gates_passed"] == 6 for c in comps) else "SR_NO_PROMOTION_EXPLORATORY"


# ===========================================================================
# §5 — puterea sintetică S7
# ===========================================================================
def grid_steps(L: int, G: int | None = None, warmup: int = WARMUP) -> np.ndarray:
    G = G_GRID if G is None else G
    return np.array([warmup + (i * (L - warmup)) // G for i in range(G)], dtype=np.int64)


def wf_seeds(game: str, set_id: int, u: int, ks: np.ndarray) -> torch.Tensor:
    tag = GAMES[game]["tag"]
    return torch.tensor([7 * 10**12 + tag * 10**9 + set_id * 10**7 + u * 10**4 + int(k) for k in ks],
                        dtype=torch.int64)


def _sci_batches(game: str, total: int, L: int, gamma: float, gen, dev, guard, chunk: int = 256, keep=None):
    sidx = torch.arange(L, device=dev)
    sizes = torch.ones(L, dtype=torch.int64, device=dev)
    for s0 in range(0, total, chunk):
        b = min(chunk, total - s0)
        guard.wait("general")
        U = mps_universes(game, b, L, gamma, gen, dev)
        if keep is not None:
            keep.append(U["mps"])
        yield U["main"], U["joker_oh"], sidx, sizes, L
        del U


def power_sci(game: str, dev, guard, log=print) -> dict:
    G = GAMES[game]
    L = G["L"]
    s_null, s_12, s_18, s_ctrl = G["seeds_sci"]
    t0 = time.perf_counter()
    gen = torch.Generator(device=dev).manual_seed(s_null)
    ref = sci_reference(game, _sci_batches(game, M_NULL, L, 0.0, gen, dev, guard), M_NULL)
    log(f"[SR {game}] referința nulă SCI M={M_NULL}: {time.perf_counter() - t0:.1f}s")
    sets = {}
    for name, seed in (("gamma_1_2", s_12), ("control", s_ctrl), ("gamma_1_8", s_18)):
        gen = torch.Generator(device=dev).manual_seed(seed)
        Bn, gamma = B_SCI[name], GAMMA_SCI[name]
        ps, scis, ents = [], [], []
        for main_oh, joker_oh, sidx, sizes, n_steps in _sci_batches(game, Bn, L, gamma, gen, dev, guard):
            raw = raw_stats_game(game, main_oh, joker_oh, sidx, sizes, n_steps)
            ev = sci_evaluate(game, raw, ref)
            ps.append(ev["p"].cpu())
            scis.append(ev["SCI"].cpu())
        p = torch.cat(ps)
        sci = torch.cat(scis)
        det = int((p <= ALPHA).sum())
        sets[name] = {"gamma": gamma, "B": Bn, "seed": seed, "detected": det, "rate": det / Bn,
                      "p_median": float(p.median()), "p_min": float(p.min()), "SCI_mean": float(sci.mean()),
                      "SCI_median": float(sci.median())}
        log(f"[SR {game}] SCI {name}: {det}/{Bn} detectate")
    return {"M_null": M_NULL, "seed_null": s_null, "K": ref["K"], "names": ref["names"], "null_mean": ref["mu"],
            "null_std": ref["sd"], "sets": sets,
            "P1_rate_gamma_1_2": sets["gamma_1_2"]["rate"], "P1_pass": sets["gamma_1_2"]["rate"] >= P1_MIN,
            "P2_fpr_control": sets["control"]["rate"], "P2_pass": sets["control"]["rate"] <= P2_MAX,
            "seconds": round(time.perf_counter() - t0, 1)}


def power_wf_universe(game: str, set_id: int, u: int, gamma: float, gen, dev, guard, log=print) -> dict:
    G = GAMES[game]
    L = G["L"]
    U = mps_universes(game, 1, L, gamma, gen, dev)
    ent = None
    if game == "joker":
        jc = U["mps"].joker_cut()
        ent = {"S_urns": float(jc["S"][0]), "chi_eff": int(jc["chi_eff"][0]), "min_cut": float(jc["min_cut"][0])}
    main_oh = U["main"][0]
    joker_oh = U["joker_oh"][0] if game == "joker" else None
    ds = synth_dataset(game, main_oh, joker_oh)
    ks = grid_steps(L)
    seeds = wf_seeds(game, set_id, u, ks)
    pred = wf_predict(ds, game, torch.as_tensor(ks), seeds=seeds, guard=guard, log=log)
    off = np.arange(L + 1)
    comps = score_predictions(game, pred, main_oh.cpu().numpy(), None if joker_oh is None else joker_oh.cpu().numpy(),
                              off)
    d1 = detection_d1(game, comps)
    rec = {"u": u, "detected": d1["detected"], "p_values": d1["p_values"],
           "hits_QL": [c["total"]["hits_QL"] for c in comps], "hits_B": [c["total"]["hits_B"] for c in comps],
           "hits_R": [c["total"]["hits_R"] for c in comps], "gates_passed": [c["gates_passed"] for c in comps],
           "promotion": promotion(comps), "targets": comps[0]["n_targets"]}
    if U["H"] is not None:
        H = set((U["H"][0].cpu().numpy() + 1).tolist())
        rec["V1_cap_H_mean"] = float(np.mean([len(H & set(v.tolist())) for v in pred["variants"][:, 0, :]]))
        if game == "joker":
            rec["ball_ticket_eq_astar_frac"] = float(np.mean(pred["jokers"][:, 0] == int(U["a_star"][0]) + 1))
    if ent is not None:
        rec["entanglement"] = ent
    return rec


def power_wf(game: str, dev, guard, log=print) -> dict:
    G = GAMES[game]
    out = {}
    t0 = time.perf_counter()
    for name, set_id, seed, Bn, gamma in (("signal", 12, G["seeds_wf"][0], B_WF_SIGNAL, 0.5),
                                          ("null", 14, G["seeds_wf"][1], B_WF_NULL, 0.0)):
        gen = torch.Generator(device=dev).manual_seed(seed)
        recs = []
        for u in range(Bn):
            t1 = time.perf_counter()
            recs.append(power_wf_universe(game, set_id, u, gamma, gen, dev, guard, log))
            log(f"[SR {game}] WF {name} u={u}: detectat={recs[-1]['detected']} p={recs[-1]['p_values']} "
                f"porți={recs[-1]['gates_passed']} ({time.perf_counter() - t1:.0f}s)")
        det = sum(r["detected"] for r in recs)
        s = {"gamma": gamma, "B": Bn, "seed": seed, "set_id": set_id, "detected": det, "universes": recs,
             "promoted": sum(r["promotion"] == "SR_PROMOVAT_EXPLORATORIU" for r in recs)}
        if game == "joker":
            s["ball_only_detected"] = sum(r["p_values"][1] <= GAMES[game]["alpha_each"] for r in recs)
            s["S_urns_max"] = max(r["entanglement"]["S_urns"] for r in recs)
            s["min_cut_ok"] = all(r["entanglement"]["S_urns"] <= r["entanglement"]["min_cut"] + 1e-6 for r in recs)
        out[name] = s
    out["G"] = G_GRID
    out["grid"] = grid_steps(G["L"]).tolist()
    out["P3_detected_signal"] = out["signal"]["detected"]
    out["P3_pass"] = out["signal"]["detected"] >= P3_MIN
    out["P4_detected_null"] = out["null"]["detected"]
    out["P4_pass"] = out["null"]["detected"] <= P4_MAX
    out["seconds"] = round(time.perf_counter() - t0, 1)
    return out


def run_witnesses() -> dict:
    p = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", str(TEST_FILE),
                        "-k", "not W12"], cwd=QL, capture_output=True, text=True)
    tail = p.stdout.strip().splitlines()[-1:] if p.stdout.strip() else []
    return {"pass": p.returncode == 0, "pytest_tail": tail}


def check_seals() -> dict:
    seal = json.loads(SEAL_FILE.read_text())
    aseal = json.loads(AMEND_SEAL_FILE.read_text())
    assert sha_file(PROTOCOL_FILE) == seal["sha256"], "protocolul modificat după sigilare"
    assert sha_file(AMEND_FILE) == aseal["sha256"], "amendamentul modificat după sigilare"
    assert aseal["protocol_seal"]["sha256"] == sha_file(SEAL_FILE)
    for f in ("engine.py", "parser.py", "tu3/parser_multi.py", "tu3/motor_n.py", "tu3/motor_joker.py",
              "tu3/joker_entanglement.py", "validare.py"):
        assert sha_file(QL / f) == seal["frozen_hashes"][f], f"{f} modificat"
    return {"protocol_sha256": seal["sha256"], "seal_sha256": sha_file(SEAL_FILE),
            "amendment_sha256": aseal["sha256"], "amendment_seal_sha256": sha_file(AMEND_SEAL_FILE)}


def run_power(out: Path = POWER_FILE, log=print) -> int:
    if out.exists():
        log(f"REFUZ: {out} există deja (rulare unică, PROTOCOL_TU3_SR §5.4).")
        return 2
    seals = check_seals()
    if not torch.cuda.is_available():
        log("REFUZ: puterea S7 cere CUDA (§3.7).")
        return 3
    dev = torch.device("cuda")
    start = utc_now()
    t0 = time.time()
    wit = run_witnesses()
    log(f"martori W1–W11: {wit}")
    vram = apply_vram_cap(dev)
    torch.cuda.reset_peak_memory_stats(dev)
    guard = ThermalGuard(log=log)
    games = {}
    try:
        with forbid_real_archive():
            for game in ("540", "joker"):
                sci = power_sci(game, dev, guard, log)
                wf = power_wf(game, dev, guard, log)
                p5 = wit["pass"]
                ok = sci["P1_pass"] and sci["P2_pass"] and wf["P3_pass"] and wf["P4_pass"] and p5
                games[game] = {"SCI": sci, "walk_forward": wf, "P5_witnesses_pass": p5,
                               "verdict": "SR_P_PASS" if ok else "SR_P_FAIL"}
                log(f"[SR {game}] verdict {games[game]['verdict']}")
    finally:
        thermal = guard.stop()
    peak_alloc = int(torch.cuda.max_memory_allocated(dev))
    peak_res = int(torch.cuda.max_memory_reserved(dev))
    s7 = all(g["verdict"] == "SR_P_PASS" for g in games.values())
    res = {
        "protocol": "TU3-SR", "session": "S7", **seals, "start_utc": start, "end_utc": utc_now(),
        "seconds": round(time.time() - t0, 1), "device": torch.cuda.get_device_name(dev), "torch": torch.__version__,
        "code_sha256": {"tu3/scor_real.py": sha_file(Path(__file__)), "tests/test_scor_real.py": sha_file(TEST_FILE),
                        "tu3/motor_n.py": sha_file(HERE / "motor_n.py"),
                        "tu3/motor_joker.py": sha_file(HERE / "motor_joker.py"), "engine.py": sha_file(QL / "engine.py")},
        "witnesses_W1_W11": wit, "games": games,
        "S7_verdict": "S7_PASS" if s7 else "S7_FAIL",
        "S8_allowed_games": [g for g, v in games.items() if v["verdict"] == "SR_P_PASS"],
        "resources": {"vram": vram, "peak_allocated_bytes": peak_alloc, "peak_reserved_bytes": peak_res,
                      "vram_under_cap": bool(peak_res < VRAM_CAP_BYTES), "thermal": thermal},
        "design": {"M_null": M_NULL, "B_SCI": B_SCI, "B_wf_signal": B_WF_SIGNAL, "B_wf_null": B_WF_NULL, "G": G_GRID,
                   "beta": BETA, "beta_J": BETA_J, "alpha": ALPHA, "P1": P1_MIN, "P2": P2_MAX, "P3": P3_MIN,
                   "P4": P4_MAX, "sub_o15": SUB_O15, "sub_o6": SUB_O6},
        "real_archive_read": False,
        "note": ("Putere pe date SINTETICE (MPS complex64, purificarea modelului cu mod latent); nu spune nimic despre "
                 "arhiva reală. Entropia urnelor și min-cut-ul sunt descriptive (margine de tip rețea tensorială, nu "
                 "AdS/CFT); nicio ecuație Wheeler–DeWitt. Variante = minime de energie, NU predicții. "
                 "positive_claims_allowed=false."),
        "positive_claims_allowed": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float) + "\n")
    os.chmod(out, 0o444)
    log(json.dumps({"S7_verdict": res["S7_verdict"], "games": {g: v["verdict"] for g, v in games.items()},
                    "seconds": res["seconds"], "thermal": thermal, "peak_reserved_bytes": peak_res}, ensure_ascii=False))
    return 0


# ===========================================================================
# §4 — rularea reală UNICĂ (S8). NU se execută în S7.
# ===========================================================================
def real_gate(game: str, session: str | None, out_root: Path = OUT_DIR, power_file: Path = POWER_FILE) -> str | None:
    """Motivul refuzului (sau None). Verificările se fac ÎNAINTE de orice citire a arhivei."""
    if game not in GAMES:
        return f"joc necunoscut {game!r}"
    if session != "S8":
        return "rularea reală cere explicit --sesiune S8 (§4.1)"
    if (out_root / game / "START.json").exists():
        return f"rularea reală {game} a fost deja pornită (START.json există; rulare unică)"
    if not power_file.exists():
        return "PUTERE_SR.json lipsește (S7 nu a rulat)"
    pw = json.loads(power_file.read_text())
    if pw.get("games", {}).get(game, {}).get("verdict") != "SR_P_PASS":
        return f"puterea S7 nu dă SR_P_PASS pentru {game}"
    return None


def run_real(game: str, session: str | None, out_root: Path = OUT_DIR, power_file: Path = POWER_FILE,
             log=print) -> int:
    why = real_gate(game, session, out_root, power_file)
    if why:
        log(f"REFUZ: {why}")
        return 2
    seals = check_seals()
    dev = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    vram = apply_vram_cap(dev)
    G = GAMES[game]
    out = out_root / game
    out.mkdir(parents=True, exist_ok=True)
    ds = PM.build_game_dataset(game, "frozen", device=dev)
    assert ds.source_sha256 == G["frozen_sha"], "arhiva înghețată diferă de sigiliu"
    start = {"started_at_utc": utc_now(), **seals, "game": game, "source_sha256": ds.source_sha256,
             "n_draws": ds.n_draws, "n_steps": ds.n_steps, "warmup": WARMUP, "config_digest": G["cfg"].digest(),
             "code_sha256": sha_file(Path(__file__)), "device": str(dev), "positive_claims_allowed": False}
    (out / "START.json").write_text(json.dumps(start, indent=1, ensure_ascii=False) + "\n")
    os.chmod(out / "START.json", 0o444)
    guard = ThermalGuard(log=log) if dev.type == "cuda" else _NoGuard()
    t0 = time.perf_counter()
    try:
        ks = torch.arange(WARMUP, ds.n_steps, dtype=torch.int64)
        pred = wf_predict(ds, game, ks, guard=guard, log=log)
    finally:
        thermal = guard.stop() if isinstance(guard, ThermalGuard) else None
    pp = out / "PREDICTII.npz"
    np.savez_compressed(pp, **pred)
    psha = sha_file(pp)
    (out / "PREDICTII_SIGILIU.json").write_text(json.dumps({"sha256": psha, "written_at_utc": utc_now(),
                                                           "before_scoring": True}, indent=1) + "\n")
    os.chmod(pp, 0o444)
    os.chmod(out / "PREDICTII_SIGILIU.json", 0o444)
    P = dict(np.load(pp))
    main_oh = ds.onehot.cpu().numpy()
    joker_oh = ds.joker_onehot.cpu().numpy() if game == "joker" else None
    comps = score_predictions(game, P, main_oh, joker_oh, ds.step_offsets.cpu().numpy())
    for c in comps:
        pt = c.pop("_per_target")
        c["per_target"] = {k_: v.astype(int).tolist() for k_, v in pt.items()}
    d1 = detection_d1(game, comps)
    # SCI real (D2) cu structura reală de pași, nul MPS
    sidx = ds.step_index.to(dev)
    sizes = (ds.step_offsets[1:] - ds.step_offsets[:-1]).to(dev)
    jo_t = ds.joker_onehot.to(dev)[None] if game == "joker" else None
    real_raw = raw_stats_game(game, ds.onehot.to(dev)[None], jo_t, sidx, sizes, ds.n_steps)
    gen = torch.Generator(device=dev).manual_seed(G["seed_real_null"])

    def batches():
        for s0 in range(0, M_NULL, 256):
            b = min(256, M_NULL - s0)
            U = mps_universes(game, b, ds.n_draws, 0.0, gen, dev)
            yield U["main"], U["joker_oh"], sidx, sizes, ds.n_steps

    ref = sci_reference(game, batches(), M_NULL)
    ev = sci_evaluate(game, real_raw, ref)
    sci_p = float(ev["p"][0])
    res = {"protocol": "TU3-SR", "session": "S8", "game": game, **seals, "start": start,
           "predictions_sha256": psha, "components": comps, "D1": d1,
           "D2": {"SCI": float(ev["SCI"][0]), "p_empirical": sci_p, "M_null": M_NULL, "seed": G["seed_real_null"],
                  "z": {k_: float(v[0]) for k_, v in ev["z"].items()},
                  "verdict": "SCI_ABATERE_EXPLORATORIE" if sci_p <= ALPHA else "SCI_COMPATIBIL_NUL"},
           "promotion": promotion(comps), "seconds": round(time.perf_counter() - t0, 1),
           "resources": {"vram": vram, "thermal": thermal,
                         "peak_reserved_bytes": int(torch.cuda.max_memory_reserved(dev)) if dev.type == "cuda" else 0},
           "finished_at_utc": utc_now(), "positive_claims_allowed": False}
    (out / "REZULTATE.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float) + "\n")
    os.chmod(out / "REZULTATE.json", 0o444)
    log(json.dumps({"D1": d1["verdict"], "D2": res["D2"]["verdict"], "promotion": res["promotion"]}, ensure_ascii=False))
    return 0


def status() -> dict:
    pw = json.loads(POWER_FILE.read_text()) if POWER_FILE.exists() else None
    return {"power_file": str(POWER_FILE), "power_present": pw is not None,
            "S7_verdict": pw.get("S7_verdict") if pw else None,
            "games": {g: v["verdict"] for g, v in pw["games"].items()} if pw else None,
            "real_started": {g: (OUT_DIR / g / "START.json").exists() for g in GAMES},
            "positive_claims_allowed": False}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="TU3-SR — scorul real 5/40/Joker (S7 putere, S8 rulare unică)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--putere", action="store_true", help="puterea sintetică S7 (o singură dată)")
    g.add_argument("--real", metavar="JOC", help="rularea reală UNICĂ (numai în S8, după SR_P_PASS)")
    g.add_argument("--stare", action="store_true")
    ap.add_argument("--sesiune", default=None)
    a = ap.parse_args(argv)
    if a.stare:
        print(json.dumps(status(), indent=1, ensure_ascii=False))
        return 0
    if a.putere:
        return run_power()
    return run_real(a.real, a.sesiune)


if __name__ == "__main__":
    raise SystemExit(main())
