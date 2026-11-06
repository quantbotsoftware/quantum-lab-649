"""TU3-SR-R — verificatorul SEPARAT al rulării reale UNICE S8 (5/40 și Joker).

Protocol: `tu3/PROTOCOL_TU3_SR_R.md` §3 (sigilat în `SIGILIU_TU3_SR_R.json` ÎNAINTE de acest cod), peste
`PROTOCOL_TU3_SR.md` §2/§4 + `AMENDAMENT_TU3_SR_01.md` (neschimbate).

Independență (§3.1): numai biblioteca standard + NumPy. NU importă `scor_real`, `torch`, `motor_n`, `motor_joker`,
`engine`, `parser`, `parser_multi`, `validare` sau vreo pistă închisă. Totul se recalculează din `PREDICTII.npz` (sigilat
înainte de scor) și din arhiva ÎNGHEȚATĂ (JSONL citit direct): integritatea (V1), arhiva (V2), predicțiile (V3),
comparatorii B/R (V4), scorul complet cu porțile și p exact (V5), verdictele D1/promovare (V6), D2 cu o referință nulă
PROPRIE (V7, legea nulă exactă, generator NumPy PCG64), resursele (V8, declarativ).

Calcul CLASIC pe CPU. O detecție pe arhiva deja explorată NU este avantaj predictiv. `positive_claims_allowed=false`.

Utilizare:
  python3 -B tu3/verifica_sr.py --joc 540 [--termic tu3/rezultate/SR/termic_s8_<UTC>Z.csv]   # scrie VERIFICARE_SR.json
  python3 -B tu3/verifica_sr.py --joc joker --verifica-doar [--fara-d2]                          # numai citire
  python3 -B tu3/verifica_sr.py --pre-rulare                                                    # PRE_RULARE_S8.json
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
QL = HERE.parent
SR_DIR = HERE / "rezultate" / "SR"
DATA = HERE / "date"
SEAL_R = HERE / "SIGILIU_TU3_SR_R.json"
PROTO_R = HERE / "PROTOCOL_TU3_SR_R.md"
SEAL_SR = HERE / "SIGILIU_TU3_SR.json"
PROTO_SR = HERE / "PROTOCOL_TU3_SR.md"
AMEND = HERE / "AMENDAMENT_TU3_SR_01.md"
AMEND_SEAL = HERE / "SIGILIU_AMENDAMENT_TU3_SR_01.json"

WARMUP = 100
QEPS, LAM0 = 1e-4, 0.5
GAP_BINS = 21
TAU_649, E_649 = 0.20, 36.0 / 49.0
HALF_LIFE = 26.0
ALPHA_D2 = 0.01
M_NULL = 8192
VRAM_CAP = 6.2e9
T_TARGET = 71
REL, ABS = 1e-9, 1e-12

# (n, r, k) pe componentă; jocul: componente, fișierul înghețat, sha, digest, α D1, semințele D2
URNS = {"540": (("540", 40, 6, 5),),
        "joker": (("joker_principal", 45, 5, 5), ("joker_bila", 20, 1, 1))}
GAMES = {
    "540": dict(code="540", n=40, r=6, joker_m=None, file="extrageri_540.jsonl", n_draws=2490, n_steps=2427,
                frozen_sha="e1591b8727c09f2350854540b7437eb271c3f850707502c17ff172b95fe62c5c",
                digest_prefix="b364fc0cfb6c", alpha_each=0.01, seed_sr=5401101, seed_np=5408101),
    "joker": dict(code="joker", n=45, r=5, joker_m=20, file="extrageri_joker.jsonl", n_draws=2202, n_steps=2139,
                  frozen_sha="45713aa2146efb725336ca6d40a92690341133ec98b26046bf7cefdf8cfe22bf",
                  digest_prefix="61c9445bce19", alpha_each=0.005, seed_sr=4521101, seed_np=4528101),
}
STATS_MAIN = ("chi_freq", "chi_pair", "chi_gap", "overlap")


def sha_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ro(p: Path) -> bool:
    return (os.stat(p).st_mode & 0o222) == 0


# ===========================================================================
# Arhiva înghețată (citire directă; aceleași reguli ca parser.load_records + parser_multi.clean_records/_steps)
# ===========================================================================
def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _invalid(g: dict, rec: dict) -> bool:
    key = rec.get("draw_key")
    if not isinstance(key, str) or not key or rec.get("game") != g["code"]:
        return True
    d = rec.get("draw_date")
    if not isinstance(d, str):
        return True
    try:
        dt.date.fromisoformat(d)
    except ValueError:
        return True
    nums = rec.get("numbers")
    if not isinstance(nums, list) or len(nums) != g["r"] or not all(_is_int(x) for x in nums):
        return True
    if any(x < 1 or x > g["n"] for x in nums) or len(set(nums)) != g["r"]:
        return True
    jk = rec.get("joker")
    if g["joker_m"] is not None:
        return not (_is_int(jk) and 1 <= jk <= g["joker_m"])
    return jk is not None


def load_archive(game: str, path: Path | None = None) -> dict:
    """Extragerile curățate, ordonate (dată, cheie), cu pașii pe dată. Întoarce indicatorii și structura de pași."""
    g = GAMES[game]
    path = Path(path) if path is not None else DATA / g["file"]
    raw = path.read_bytes()
    recs = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            recs.append(obj)
    keys, sets, keep = set(), set(), []
    for rec in recs:
        if _invalid(g, rec):
            continue
        nums = tuple(sorted(rec["numbers"]))
        sk = (rec["draw_date"], nums, rec.get("joker"))
        if rec["draw_key"] in keys or sk in sets:
            continue
        keys.add(rec["draw_key"])
        sets.add(sk)
        keep.append(rec)
    keep.sort(key=lambda r: (r["draw_date"], r["draw_key"]))
    T = len(keep)
    main = np.zeros((T, g["n"]), dtype=np.float64)
    for i, rec in enumerate(keep):
        main[i, np.asarray(rec["numbers"], dtype=np.int64) - 1] = 1.0
    jo = None
    if g["joker_m"] is not None:
        jo = np.zeros((T, g["joker_m"]), dtype=np.float64)
        jo[np.arange(T), np.asarray([r["joker"] for r in keep], dtype=np.int64) - 1] = 1.0
    offsets, step_index, last = [0], np.empty(T, dtype=np.int64), None
    for i, rec in enumerate(keep):
        if last is not None and rec["draw_date"] != last:
            offsets.append(i)
        last = rec["draw_date"]
        step_index[i] = len(offsets) - 1
    offsets.append(T)
    return {"sha256": hashlib.sha256(raw).hexdigest(), "path": str(path), "main": main, "joker": jo,
            "step_offsets": np.asarray(offsets, dtype=np.int64), "step_index": step_index,
            "n_draws": T, "n_steps": len(offsets) - 1}


# ===========================================================================
# §2 — scorul (re-implementare independentă din PROTOCOL_TU3_SR §2)
# ===========================================================================
def e_u(n: int, r: int, k: int) -> float:
    return float(k * r) / n


def tau(n: int, r: int, k: int) -> float:
    return TAU_649 * (e_u(n, r, k) / E_649)


def marginal(pi: np.ndarray, n: int, r: int) -> np.ndarray:
    p0 = float(r) / n
    d = float(r) * pi - p0
    with np.errstate(divide="ignore", invalid="ignore"):
        hi = np.where(d > 0, (1 - QEPS - p0) / d, np.inf).min(-1)
        lo = np.where(d < 0, (p0 - QEPS) / (-d), np.inf).min(-1)
    lam = np.minimum(LAM0, np.minimum(hi, lo))
    return p0 + lam[:, None] * d


def ticket_topk(pi: np.ndarray, k: int) -> np.ndarray:
    return np.sort(np.argsort(-pi, axis=-1, kind="stable")[:, :k] + 1, axis=-1)


def hyper(n: int, r: int, k: int) -> np.ndarray:
    return np.array([math.comb(k, h) * math.comb(n - k, r - h) / math.comb(n, r) for h in range(min(k, r) + 1)])


def tail_exact(H: int, T: int, n: int, r: int, k: int) -> float:
    pmf, dist = hyper(n, r, k), np.array([1.0])
    for _ in range(T):
        dist = np.convolve(dist, pmf)
    return float(dist[H:].sum())


def _block(per: dict, sl: slice, n: int, r: int, k: int) -> dict:
    T = int(per["hits_QL"][sl].shape[0])
    eu = e_u(n, r, k)
    o = {"targets": T}
    for nm in ("QL", "B", "R"):
        o[f"hits_{nm}"] = int(per[f"hits_{nm}"][sl].sum())
    for nm in ("QL", "B", "R"):
        o[f"excess_{nm}"] = o[f"hits_{nm}"] / T - eu if T else 0.0
    for nm in ("QL", "B", "R", "U"):
        o[f"log_{nm}"] = float(per[f"log_{nm}"][sl].sum())
        o[f"brier_{nm}"] = float(per[f"brier_{nm}"][sl].sum())
    o["hits_union3_QL"] = int(per["hits_union"][sl].sum())
    o["expected_union3_U"] = T * float(3 * k * r) / float(n)
    return o


def _gates(tot: dict, h1: dict, h2: dict, t_: float) -> list[dict]:
    g = [
        ("1", tot["excess_QL"] >= t_, tot["excess_QL"]),
        ("2", tot["hits_QL"] > tot["hits_B"] and tot["hits_QL"] > tot["hits_R"],
         [tot["hits_QL"], tot["hits_B"], tot["hits_R"]]),
        ("3", tot["log_QL"] - tot["log_U"] > 0 and tot["log_QL"] - tot["log_B"] > 0,
         [tot["log_QL"] - tot["log_U"], tot["log_QL"] - tot["log_B"]]),
        ("4", tot["brier_QL"] < min(tot["brier_U"], tot["brier_B"], tot["brier_R"]),
         [tot["brier_QL"], tot["brier_U"], tot["brier_B"], tot["brier_R"]]),
        ("5", all(h["excess_QL"] > 0 and h["hits_QL"] - h["hits_B"] > 0 for h in (h1, h2)),
         [[h["excess_QL"], h["hits_QL"] - h["hits_B"]] for h in (h1, h2)]),
        ("6", all(h["log_QL"] - h["log_B"] > 0 for h in (h1, h2)), [h["log_QL"] - h["log_B"] for h in (h1, h2)]),
    ]
    return [{"gate": a, "pass": bool(b), "value": c} for a, b, c in g]


def component(name: str, n: int, r: int, k: int, y: np.ndarray, pi_ql: np.ndarray, t_ql: np.ndarray,
              union: np.ndarray, pi_b: np.ndarray, pi_r: np.ndarray) -> dict:
    """y [T,n]; t_ql [T,k]; union [T,V,k] (numere 1..n)."""
    T = y.shape[0]
    tb, tr = ticket_topk(pi_b, k), ticket_topk(pi_r, k)
    per = {}
    for nm, pi, t in (("QL", pi_ql, t_ql), ("B", pi_b, tb), ("R", pi_r, tr), ("U", None, None)):
        q = np.full_like(y, float(r) / n) if pi is None else marginal(pi, n, r)
        per[f"log_{nm}"] = (y * np.log(q) + (1 - y) * np.log(1 - q)).sum(-1)
        per[f"brier_{nm}"] = ((q - y) ** 2).sum(-1)
        if t is not None:
            per[f"hits_{nm}"] = np.take_along_axis(y, t - 1, axis=1).sum(-1)
    U = np.zeros_like(y)
    for v in range(union.shape[1]):
        U[np.arange(T)[:, None], union[:, v, :] - 1] = 1.0
    per["hits_union"] = (U * y).sum(-1)
    h = T // 2
    tot, h1, h2 = _block(per, slice(0, T), n, r, k), _block(per, slice(0, h), n, r, k), _block(per, slice(h, T), n, r, k)
    tot["expected_union3_exact"] = float(U.sum() * r / n)
    gates = _gates(tot, h1, h2, tau(n, r, k))
    mlen = min(k, r) + 1
    changed_set = int(sum(set(a.tolist()) != set(b.tolist()) for a, b in zip(t_ql, tb)))
    changed_raw = int((t_ql != tb).any(-1).sum())
    return {"urn": {"name": name, "n": n, "r": r, "k": k, "E_U": e_u(n, r, k), "tau": tau(n, r, k)},
            "total": tot, "half1": h1, "half2": h2, "gates": gates, "gates_passed": sum(g["pass"] for g in gates),
            "match_dist_QL_v1": np.bincount(per["hits_QL"].astype(np.int64), minlength=mlen)[:mlen].tolist(),
            "match_expected_U": (hyper(n, r, k) * T).tolist(),
            "p_exact_hits_QL_ge": tail_exact(int(per["hits_QL"].sum()), T, n, r, k),
            "n_targets": int(T), "tickets_changed_vs_B": changed_raw, "_tickets_changed_set": changed_set,
            "per_target": {kk: per[kk].astype(np.int64).tolist() for kk in ("hits_QL", "hits_B", "hits_R", "hits_union")}}


def comparators(counts_steps: np.ndarray, cum_draws: np.ndarray, offsets: np.ndarray, ks: np.ndarray):
    """π_B ∝ c+1 (extragerile pașilor < k), π_R ∝ ew+0.5 (ew(s) = ew(s−1)·2^(−1/26) + cnt(s−1))."""
    S = counts_steps.shape[0]
    decay = 2.0 ** (-1.0 / HALF_LIFE)
    ew = np.zeros((S + 1, counts_steps.shape[1]), dtype=np.float64)
    for s in range(1, S + 1):
        ew[s] = ew[s - 1] * decay + counts_steps[s - 1]
    c = cum_draws[offsets[ks]]
    pb = (c + 1.0) / (c + 1.0).sum(-1, keepdims=True)
    e = ew[ks]
    pr = (e + 0.5) / (e + 0.5).sum(-1, keepdims=True)
    return pb, pr


def _cum(x: np.ndarray) -> np.ndarray:
    out = np.zeros((x.shape[0] + 1, x.shape[1]), dtype=np.float64)
    out[1:] = np.cumsum(x, 0)
    return out


def _step_counts(x: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    return np.add.reduceat(x, offsets[:-1], axis=0)


# ===========================================================================
# §2.9 — SCI (statistici brute, NumPy) + referința nulă proprie (V7)
# ===========================================================================
def raw_stats(oh: np.ndarray, offsets: np.ndarray, r: int, pairs: bool = True) -> dict:
    """oh [M, Nd, n] (0/1). χ²_frecv, χ²_perechi (r ≥ 2), histograma golurilor [M,n,21], suprapunerea serială."""
    M, Nd, n = oh.shape
    c = oh.sum(1, dtype=np.float64)
    e1 = float(r) * Nd / n
    out = {"chi_freq": ((c - e1) ** 2 / e1).sum(-1)}
    if pairs and r >= 2:
        o32 = oh.astype(np.float32)
        C = np.matmul(o32.transpose(0, 2, 1), o32).astype(np.float64)
        iu = np.triu_indices(n, 1)
        e2 = Nd * float(r * (r - 1)) / float(n * (n - 1))
        out["chi_pair"] = ((C[:, iu[0], iu[1]] - e2) ** 2 / e2).sum(-1)
    pres = np.add.reduceat(oh, offsets[:-1], axis=1)                    # [M, S, n]
    S = pres.shape[1]
    s_ar = np.broadcast_to(np.arange(S, dtype=np.int64)[None, :, None], pres.shape)
    marks = np.where(pres > 0, s_ar, -1)
    last = np.maximum.accumulate(marks, axis=1)
    prev = np.concatenate([np.full((M, 1, n), -1, dtype=np.int64), last[:, :-1]], axis=1)
    valid = (pres > 0) & (prev >= 0)
    gap = np.clip(s_ar - prev, 1, GAP_BINS) - 1
    flat = ((np.arange(M, dtype=np.int64)[:, None, None] * n + np.arange(n, dtype=np.int64)[None, None, :]) * GAP_BINS
            + gap)
    out["gap_hist"] = np.bincount(flat[valid], minlength=M * n * GAP_BINS).astype(np.float64).reshape(M, n, GAP_BINS)
    sz = np.diff(offsets).astype(np.float64)
    v = pres.astype(np.float64)
    out["overlap"] = ((v[:, :-1] * v[:, 1:]).sum(-1) / (sz[:-1] * sz[1:])[None]).mean(-1)
    return out


def game_stats(game: str, main: np.ndarray, jo: np.ndarray | None, offsets: np.ndarray) -> dict:
    g = GAMES[game]
    rm = raw_stats(main, offsets, g["r"])
    out = {f"main.{k}": v for k, v in rm.items()}
    if game == "joker":
        rb = raw_stats(jo, offsets, 1, pairs=False)
        out.update({f"ball.{k}": v for k, v in rb.items()})
        N = np.matmul(main.astype(np.float32).transpose(0, 2, 1), jo.astype(np.float32)).astype(np.float64)
        E = main.shape[1] * (float(g["r"]) / g["n"]) * (1.0 / g["joker_m"])
        out["cross.chi"] = ((N - E) ** 2 / E).sum((-1, -2))
    return out


def stat_names(game: str) -> list[str]:
    names = [f"main.{s}" for s in STATS_MAIN]
    return names + (["ball.chi_freq", "ball.chi_gap", "ball.overlap", "cross.chi"] if game == "joker" else [])


def null_universes(game: str, M: int, Nd: int, rng: np.random.Generator, chunk: int):
    """Legea nulă EXACTĂ: submulțimi uniforme de r numere din n, bila uniformă și independentă (= nulul MPS, W2)."""
    g = GAMES[game]
    for s0 in range(0, M, chunk):
        m = min(chunk, M - s0)
        keys = rng.random((m, Nd, g["n"]), dtype=np.float32)
        idx = np.argpartition(keys, g["r"] - 1, axis=-1)[..., :g["r"]]
        oh = np.zeros((m, Nd, g["n"]), dtype=np.float32)
        np.put_along_axis(oh, idx, 1.0, axis=-1)
        jo = None
        if g["joker_m"] is not None:
            jo = np.zeros((m, Nd, g["joker_m"]), dtype=np.float32)
            jo[np.arange(m)[:, None], np.arange(Nd)[None, :], rng.integers(0, g["joker_m"], (m, Nd))] = 1.0
        yield oh, jo


def d2_independent(game: str, arc: dict, M: int = M_NULL, seed: int | None = None, chunk: int = 128) -> dict:
    g = GAMES[game]
    seed = g["seed_np"] if seed is None else seed
    off = arc["step_offsets"]
    real = game_stats(game, arc["main"][None], None if arc["joker"] is None else arc["joker"][None], off)
    parts: dict[str, list] = {}
    rng = np.random.default_rng(seed)
    for oh, jo in null_universes(game, M, arc["n_draws"], rng, chunk):
        st = game_stats(game, oh, jo, off)
        for k, v in st.items():
            parts.setdefault(k, []).append(v)
    nul = {k: np.concatenate(v, 0) for k, v in parts.items()}
    for pre in ("main.", "ball."):
        if f"{pre}gap_hist" in nul:
            eb = np.maximum(nul[f"{pre}gap_hist"].mean(0), 1e-12)
            nul[f"{pre}chi_gap"] = ((nul.pop(f"{pre}gap_hist") - eb) ** 2 / eb).sum((-1, -2))
            real[f"{pre}chi_gap"] = ((real.pop(f"{pre}gap_hist") - eb) ** 2 / eb).sum((-1, -2))
    names = stat_names(game)
    z, zn = {}, np.zeros(M)
    for k in names:
        mu, sd = float(nul[k].mean()), float(nul[k].std(ddof=1))
        z[k] = float((real[k][0] - mu) / sd)
        zn = zn + (nul[k] - mu) / sd
    K = len(names)
    sci = sum(z.values()) / math.sqrt(K)
    sci_null = zn / math.sqrt(K)
    p = (1 + int((sci_null >= sci).sum())) / (M + 1)
    return {"M": M, "seed": seed, "generator": "numpy PCG64", "K": K, "z": z, "SCI": float(sci), "p_empirical": p,
            "stats_real": {k: float(real[k][0]) for k in names}}


# ===========================================================================
# Comparații
# ===========================================================================
def close(a, b, path: str = "", out: list | None = None) -> list:
    """Diferențele (listă de căi) dintre a (recalculat) și b (publicat): întregi/bool exact, reali REL/ABS."""
    out = [] if out is None else out
    if isinstance(a, dict):
        if not isinstance(b, dict):
            out.append(path)
            return out
        for k in a:
            if k.startswith("_"):
                continue
            if k not in b:
                out.append(f"{path}.{k}(lipsă)")
            else:
                close(a[k], b[k], f"{path}.{k}", out)
        return out
    if isinstance(a, (list, tuple)):
        if not isinstance(b, (list, tuple)) or len(a) != len(b):
            out.append(path)
            return out
        for i, (x, y) in enumerate(zip(a, b)):
            close(x, y, f"{path}[{i}]", out)
        return out
    if isinstance(a, (bool, np.bool_)) or isinstance(b, bool):
        if bool(a) != b or not isinstance(b, bool):
            out.append(path)
        return out
    if isinstance(a, (int, np.integer)) and isinstance(b, int):
        if int(a) != b:
            out.append(path)
        return out
    if isinstance(a, str):
        if a != b:
            out.append(path)
        return out
    try:
        if not math.isclose(float(a), float(b), rel_tol=REL, abs_tol=ABS):
            out.append(path)
    except (TypeError, ValueError):
        out.append(path)
    return out


def thermal_csv(path: Path) -> dict:
    temps = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                try:
                    temps.append(int(row[1].strip()))
                except ValueError:
                    continue
    return {"file": str(path), "samples": len(temps), "t_max_c": max(temps) if temps else None,
            "sha256": sha_file(path), "temperature_target_met": bool(temps) and max(temps) < T_TARGET}


# ===========================================================================
# Verificarea unui joc
# ===========================================================================
def verify_game(game: str, sr_dir: Path = SR_DIR, archive: Path | None = None, frozen_sha: str | None = None,
                digest_prefix: str | None = None, M: int = M_NULL, d2: bool = True, seal_utc: str | None = None,
                seal_files: bool = True, termic: Path | None = None, chunk: int = 128) -> dict:
    g = GAMES[game]
    frozen_sha = g["frozen_sha"] if frozen_sha is None else frozen_sha
    digest_prefix = g["digest_prefix"] if digest_prefix is None else digest_prefix
    d = Path(sr_dir) / game
    checks = []

    def chk(cid: str, ok: bool, detail=None):
        checks.append({"id": cid, "pass": bool(ok), "detail": detail})
        return ok

    names = ("START.json", "PREDICTII.npz", "PREDICTII_SIGILIU.json", "REZULTATE.json")
    present = {n_: (d / n_).is_file() for n_ in names}
    if not chk("V1.fisiere_prezente", all(present.values()), present):
        return {"game": game, "verdict": "VERIFICARE_SR_FAIL", "checks": checks}
    start = json.loads((d / "START.json").read_text())
    psig = json.loads((d / "PREDICTII_SIGILIU.json").read_text())
    res = json.loads((d / "REZULTATE.json").read_text())
    psha = sha_file(d / "PREDICTII.npz")
    chk("V1.0444", all(_ro(d / n_) for n_ in names), {n_: _ro(d / n_) for n_ in names})
    chk("V1.sha_predictii", psha == psig.get("sha256") == res.get("predictions_sha256"),
        {"npz": psha, "sigiliu": psig.get("sha256"), "rezultate": res.get("predictions_sha256")})
    chk("V1.predictii_inainte_de_scor", psig.get("before_scoring") is True
        and str(psig.get("written_at_utc")) <= str(res.get("finished_at_utc")),
        [psig.get("written_at_utc"), res.get("finished_at_utc")])
    if seal_utc is None:
        seal_utc = json.loads(SEAL_R.read_text())["sealed_utc"]
    chk("V1.start_dupa_sigiliul_S8", str(start.get("started_at_utc")) > seal_utc, [start.get("started_at_utc"), seal_utc])
    if seal_files:
        exp = {"protocol_sha256": sha_file(PROTO_SR), "seal_sha256": sha_file(SEAL_SR),
               "amendment_sha256": sha_file(AMEND), "amendment_seal_sha256": sha_file(AMEND_SEAL)}
        chk("V1.sigilii_SR_in_START", all(start.get(k) == v for k, v in exp.items()) and
            all(res.get(k) == v for k, v in exp.items()), exp)
    chk("V1.claims_false", start.get("positive_claims_allowed") is False and res.get("positive_claims_allowed") is False
        and res.get("game") == game and res.get("session") == "S8")
    # V2 — arhiva
    arc = load_archive(game, archive)
    chk("V2.sha_arhiva", arc["sha256"] == start.get("source_sha256") == frozen_sha,
        {"fisier": arc["sha256"], "start": start.get("source_sha256"), "sigilat": frozen_sha})
    chk("V2.pasi", arc["n_draws"] == start.get("n_draws") and arc["n_steps"] == start.get("n_steps")
        and start.get("warmup") == WARMUP, [arc["n_draws"], arc["n_steps"], start.get("n_draws"), start.get("n_steps")])
    chk("V2.config_digest", str(start.get("config_digest", "")).startswith(digest_prefix),
        [start.get("config_digest"), digest_prefix])
    # V3 — predicțiile
    P = dict(np.load(d / "PREDICTII.npz"))
    S = arc["n_steps"]
    ks = P["ks"].astype(np.int64)
    urns = URNS[game]
    n0, r0, k0 = urns[0][1:]
    V = P["variants"].astype(np.int64)
    ok3 = (ks.tolist() == list(range(WARMUP, S)) and V.shape == (S - WARMUP, 3, k0) and V.min() >= 1
           and V.max() <= n0 and all(len(set(v)) == k0 for v in V.reshape(-1, k0).tolist())
           and P["pi_QL"].shape == (S - WARMUP, n0) and (P["pi_QL"] >= 0).all()
           and np.abs(P["pi_QL"].sum(-1) - 1).max() <= 1e-6)
    if game == "joker":
        J = P["jokers"].astype(np.int64)
        ok3 = ok3 and J.shape[0] == S - WARMUP and J.min() >= 1 and J.max() <= 20 and (P["pi_J"] >= 0).all() \
            and np.abs(P["pi_J"].sum(-1) - 1).max() <= 1e-6
    chk("V3.predictii_valide", ok3, {"S": S, "shape_variants": list(V.shape)})
    # V4 — comparatorii
    off = arc["step_offsets"]
    pb, pr = comparators(_step_counts(arc["main"], off), _cum(arc["main"]), off, ks)
    dev4 = {"piB": float(np.abs(pb - P["piB"]).max()), "piR": float(np.abs(pr - P["piR"]).max())}
    if game == "joker":
        pbj, prj = comparators(_step_counts(arc["joker"], off), _cum(arc["joker"]), off, ks)
        dev4.update(piB_J=float(np.abs(pbj - P["piB_J"]).max()), piR_J=float(np.abs(prj - P["piR_J"]).max()))
    chk("V4.comparatori", max(dev4.values()) <= 1e-12, dev4)
    # V5 — scorul
    rows = np.concatenate([np.arange(off[k], off[k + 1]) for k in ks]).astype(np.int64)
    kidx = np.concatenate([np.full(off[k + 1] - off[k], i) for i, k in enumerate(ks)]).astype(np.int64)
    y = arc["main"][rows]
    comps = [component(urns[0][0], n0, r0, k0, y, P["pi_QL"][kidx], V[kidx][:, 0, :], V[kidx], pb[kidx], pr[kidx])]
    if game == "joker":
        J = P["jokers"].astype(np.int64)[kidx]
        nm, n1, r1, k1 = urns[1]
        comps.append(component(nm, n1, r1, k1, arc["joker"][rows], P["pi_J"][kidx], J[:, :1], J[:, :, None],
                               pbj[kidx], prj[kidx]))
    pub = res.get("components", [])
    diffs = []
    notes = []
    if len(pub) != len(comps):
        diffs.append("components(număr)")
    for c, pc in zip(comps, pub):
        rec = dict(c)
        if c["tickets_changed_vs_B"] != pc.get("tickets_changed_vs_B") and \
                c["_tickets_changed_set"] == pc.get("tickets_changed_vs_B"):
            rec["tickets_changed_vs_B"] = c["_tickets_changed_set"]
            notes.append(f"{c['urn']['name']}: tickets_changed_vs_B pe mulțimi")
        pcg = [{k: v for k, v in gg.items() if k != "rule"} for gg in pc.get("gates", [])]
        rec_cmp = {k: v for k, v in rec.items() if k != "gates"}
        close(rec_cmp, pc, c["urn"]["name"], diffs)
        close(rec["gates"], pcg, f"{c['urn']['name']}.gates", diffs)
    chk("V5.scor_recalculat", not diffs, {"diferente": diffs[:20], "note": notes})
    # V6 — verdictele
    a = g["alpha_each"]
    ps = [c["p_exact_hits_QL_ge"] for c in comps]
    det = any(p <= a for p in ps)
    d1 = {"alpha_each": a, "p_values": ps, "detected": det,
          "verdict": "SR_DETECTIE_EXPLORATORIE" if det else "SR_FARA_DETECTIE"}
    promo = "SR_PROMOVAT_EXPLORATORIU" if all(c["gates_passed"] == 6 for c in comps) else "SR_NO_PROMOTION_EXPLORATORY"
    dd = close(d1, res.get("D1", {}), "D1")
    chk("V6.verdicte", not dd and promo == res.get("promotion"),
        {"D1": d1["verdict"], "D1_publicat": res.get("D1", {}).get("verdict"), "promovare": promo,
         "promovare_publicata": res.get("promotion"), "diferente": dd})
    # V7 — D2 independent
    d2_out = None
    pd2 = res.get("D2", {})
    chk("V7.parametri_D2", pd2.get("M_null") == M_NULL and pd2.get("seed") == g["seed_sr"],
        [pd2.get("M_null"), pd2.get("seed")])
    if d2:
        ind = d2_independent(game, arc, M=M, chunk=chunk)
        zt = {k: (abs(ind["z"][k] - pd2["z"][k]), 0.10 + 0.03 * abs(pd2["z"][k])) for k in ind["z"]}
        sci_d, sci_t = abs(ind["SCI"] - pd2["SCI"]), 0.10 + 0.03 * abs(pd2["SCI"])
        pbar = 0.5 * (ind["p_empirical"] + pd2["p_empirical"])
        ptol = 4 * math.sqrt(max(pbar * (1 - pbar), 0.0) / M) + 3.0 / M
        p_ok = abs(ind["p_empirical"] - pd2["p_empirical"]) <= ptol
        v_np = "SCI_ABATERE_EXPLORATORIE" if ind["p_empirical"] <= ALPHA_D2 else "SCI_COMPATIBIL_NUL"
        v_pub = "SCI_ABATERE_EXPLORATORIE" if pd2["p_empirical"] <= ALPHA_D2 else "SCI_COMPATIBIL_NUL"
        band = abs(pd2["p_empirical"] - ALPHA_D2) <= ptol
        concord = "D2_CONCORDANT" if v_np == pd2.get("verdict") else ("D2_IN_BANDA_MC" if band else "D2_DISCORDANT")
        ok7 = (all(dz <= t for dz, t in zt.values()) and sci_d <= sci_t and p_ok and concord != "D2_DISCORDANT"
               and v_pub == pd2.get("verdict") and set(ind["z"]) == set(pd2.get("z", {})))
        d2_out = {**ind, "abs_diff_z": {k: v[0] for k, v in zt.items()}, "tol_z": {k: v[1] for k, v in zt.items()},
                  "abs_diff_SCI": sci_d, "tol_SCI": sci_t, "abs_diff_p": abs(ind["p_empirical"] - pd2["p_empirical"]),
                  "tol_p": ptol, "verdict_np": v_np, "verdict_publicat": pd2.get("verdict"), "concordanta": concord}
        chk("V7.D2_independent", ok7, {"concordanta": concord, "SCI": [ind["SCI"], pd2.get("SCI")],
                                       "p": [ind["p_empirical"], pd2.get("p_empirical")]})
    # V8 — resursele (declarativ)
    rs = res.get("resources", {}) or {}
    th = rs.get("thermal") or {}
    resources = {"peak_reserved_bytes": rs.get("peak_reserved_bytes"),
                 "vram_under_cap": (rs.get("peak_reserved_bytes") or 0) < VRAM_CAP, "thermal_guard": th,
                 "external": thermal_csv(Path(termic)) if termic else None}
    verdict = "VERIFICARE_SR_PASS" if all(c["pass"] for c in checks) else "VERIFICARE_SR_FAIL"
    return {"game": game, "verdict": verdict, "checks": checks, "d2_independent": d2_out, "resources": resources,
            "rezultate_sha256": sha_file(d / "REZULTATE.json"), "predictions_sha256": psha,
            "published": {"D1": res.get("D1", {}).get("verdict"), "D2": pd2.get("verdict"),
                          "promotion": res.get("promotion")}}


def write_verification(game: str, rep: dict, sr_dir: Path = SR_DIR) -> Path:
    out = Path(sr_dir) / game / "VERIFICARE_SR.json"
    doc = {"verifier": "TU3-SR-R tu3/verifica_sr.py", "protocol": "tu3/PROTOCOL_TU3_SR_R.md",
           "protocol_sha256": sha_file(PROTO_R), "seal_sha256": sha_file(SEAL_R),
           "verifier_sha256": sha_file(Path(__file__)), "written_utc": utc_now(), **rep,
           "note": ("Recalcul NumPy independent din PREDICTII.npz + arhiva înghețată; D2 cu referință nulă proprie. "
                    "O detecție pe arhiva deja explorată NU este avantaj predictiv. positive_claims_allowed=false."),
           "positive_claims_allowed": False}
    with open(out, "x", encoding="utf-8") as f:
        f.write(json.dumps(doc, indent=1, ensure_ascii=False, default=float) + "\n")
    os.chmod(out, 0o444)
    return out


def write_pre_run(sr_dir: Path = SR_DIR, root: Path = QL) -> Path:
    sr_dir, root = Path(sr_dir), Path(root)
    out = sr_dir / "PRE_RULARE_S8.json"
    if any((sr_dir / g / "START.json").exists() for g in GAMES):
        raise RuntimeError("REFUZ: există deja un START.json (manifestul pre-rulare trebuie scris înainte)")
    recs = sorted((root / "tu3" / "inlocuiri").glob("INLOCUIRE_SR_*.json"))
    if not recs:
        raise RuntimeError("REFUZ: înregistrarea INLOCUIRE_SR_*.json lipsește (se scrie după testele de cod)")
    files = ["tu3/verifica_sr.py", "tests/test_verifica_sr.py", "tu3/ui_tu3.py", "tests/test_app_tu3.py",
             "tests/test_scor_real.py", "tu3/scor_real.py", "tu3/PROTOCOL_TU3_SR_R.md", "tu3/SIGILIU_TU3_SR_R.json",
             "tu3/PROTOCOL_TU3_SR.md", "tu3/SIGILIU_TU3_SR.json", "tu3/AMENDAMENT_TU3_SR_01.md",
             "tu3/SIGILIU_AMENDAMENT_TU3_SR_01.json", "tu3/rezultate/SR/PUTERE_SR.json", "engine.py",
             "tu3/motor_n.py", "tu3/motor_joker.py", "tu3/parser_multi.py", "parser.py"]
    files += [str(p.relative_to(root)) for p in recs]
    doc = {"manifest": "PRE_RULARE_S8", "written_utc": utc_now(), "sha256": {f: sha_file(root / f) for f in files},
           "note": "Tot codul S8 înghețat ÎNAINTE de rularea reală unică. positive_claims_allowed=false.",
           "positive_claims_allowed": False}
    with open(out, "x", encoding="utf-8") as f:
        f.write(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    os.chmod(out, 0o444)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="TU3-SR-R — verificatorul separat al rulării reale S8")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--joc", choices=sorted(GAMES))
    g.add_argument("--pre-rulare", action="store_true")
    ap.add_argument("--verifica-doar", action="store_true", help="fără scriere")
    ap.add_argument("--fara-d2", action="store_true", help="sare peste V7 (numai cu --verifica-doar)")
    ap.add_argument("--termic", default=None, help="jurnalul CSV al monitorului extern nvidia-smi")
    a = ap.parse_args(argv)
    if a.pre_rulare:
        try:
            p = write_pre_run()
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 2
        print(p, sha_file(p))
        return 0
    if a.fara_d2 and not a.verifica_doar:
        print("REFUZ: --fara-d2 numai cu --verifica-doar", file=sys.stderr)
        return 2
    if not a.verifica_doar and (SR_DIR / a.joc / "VERIFICARE_SR.json").exists():
        print(f"REFUZ: {SR_DIR / a.joc / 'VERIFICARE_SR.json'} există deja (fără suprascriere)", file=sys.stderr)
        return 2
    rep = verify_game(a.joc, d2=not a.fara_d2, termic=Path(a.termic) if a.termic else None)
    summary = {"game": a.joc, "verdict": rep["verdict"], "published": rep.get("published"),
               "failed": [c["id"] for c in rep["checks"] if not c["pass"]],
               "D2_independent": None if not rep.get("d2_independent") else
               {k: rep["d2_independent"][k] for k in ("SCI", "p_empirical", "concordanta")}}
    if not a.verifica_doar:
        out = write_verification(a.joc, rep)
        summary["file"] = str(out)
        summary["sha256"] = sha_file(out)
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=float))
    return 0 if rep["verdict"] == "VERIFICARE_SR_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
