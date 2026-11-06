"""TU4-S17: filtrul de admisibilitate pentru AFIȘARE (biletele „pur liniare” = progresii aritmetice) și martorii A0–A4.

Protocol: tu4/PROTOCOL_TU4_S17.md (6603b362…), sigiliu tu4/SIGILIU_TU4_S17.json (00:17:46Z), scrise ÎNAINTE de acest
cod. Fișier NOU: nu modifică ip_core.py / judecator.py / emite.py / emisiile / UI. Citește numai cele 3 emisii sigilate
(read-only); nu citește arhiva. Filtrul NU schimbă nicio probabilitate și NU intră în judecător.
Calcul clasic: aritmetică rațională exactă (Fraction) pentru ordine, float64 pe RTX 5060 + NumPy CPU pentru enumerare.
positive_claims_allowed = false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import heapq
import itertools
import json
import math
import os
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent            # tu4/
ROOT = HERE.parent                                # quantum_lab_649/
TRIB = HERE / "tribunal"
OUT_DIR = HERE / "rezultate" / "S17"
IP_SHA = "ab3e1de93d8e5ae537a8c80599905aaa19cc103602f9b18f4b7f7f6f8a48c302"
EM_SHA = {"649": "e2fe385ecad12ac85cb870f9301ee64eee4ac1f78696656c32dd4278ddcb1947",
          "540": "a15dc8fdbad6c165cf45ce5290790120ecdd0a2e752a370bcbf45869e2e06098",
          "joker": "092e3f5c610a7b000e47467d572558d8b6bb45cf94b6b6315333312e64990a74"}
TARGET = "2026-10-29"
MODELS = ("H1", "H3")
WINDOW = 1e-9
TOL_GPU_CPU = 1e-12


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ definiția (protocol §1 C4)
def is_linear(ticket) -> bool:
    """Pur liniar ⇔ progresie aritmetică cu pas constant d ≥ 1 (b ≥ 3), pe numerele sortate."""
    t = sorted(int(x) for x in ticket)
    if len(t) < 3 or len(set(t)) != len(t):
        raise ValueError("biletul trebuie să aibă cel puțin 3 numere distincte")
    d = t[1] - t[0]
    return d >= 1 and all(t[j + 1] - t[j] == d for j in range(len(t) - 1))


def ap_count(n: int, b: int) -> int:
    """Forma închisă: Σ_{d≥1} max(0, n − (b−1)d)."""
    return sum(max(0, n - (b - 1) * d) for d in range(1, n))


def label_order(logw) -> list[int]:
    """Etichetele 1..n ordonate după (−ln w, etichetă), ca np.argsort(-lw, stable)."""
    return sorted(range(1, len(logw) + 1), key=lambda i: (-Fraction(float(logw[i - 1])), i))


def exact_key(ticket, F) -> tuple:
    t = tuple(sorted(ticket))
    return (-sum(F[i - 1] for i in t), t)


def heap_order(logw, b: int, stop=None, limit: int | None = None):
    """Enumerare best-first exactă în ordinea totală (s exact descrescător, tuplu crescător).

    Generează (rang, bilet, s_exact). Se oprește când stop(bilet) e adevărat sau după `limit` bilete.
    """
    F = [Fraction(float(x)) for x in logw]
    n = len(F)
    top = tuple(sorted(label_order(logw)[:b]))
    heap = [exact_key(top, F)]
    seen = {top}
    rank = 0
    nodes = 1
    while heap:
        negs, t = heapq.heappop(heap)
        rank += 1
        yield rank, t, -negs, nodes
        if (stop is not None and stop(t)) or (limit is not None and rank >= limit):
            return
        ts = set(t)
        for a in t:
            for c in range(1, n + 1):
                if c in ts:
                    continue
                u = tuple(sorted((ts - {a}) | {c}))
                if u not in seen:
                    seen.add(u)
                    nodes += 1
                    heapq.heappush(heap, exact_key(u, F))


def admissible_heap(logw, b: int) -> dict:
    top = None
    for rank, t, s, nodes in heap_order(logw, b, stop=lambda t: not is_linear(t)):
        if top is None:
            top = (t, s)
        last = (rank, t, s, nodes)
    rank, t, s, nodes = last
    return {"top": list(top[0]), "s_top": top[1], "admissible": list(t), "s_adm": s, "rank": rank, "nodes": nodes}


def log_esp(logw, b: int) -> float:
    w = [math.exp(float(x)) for x in logw]
    e = [1.0] + [0.0] * b
    for wi in w:
        for j in range(b, 0, -1):
            e[j] += wi * e[j - 1]
    return math.log(e[b])


def log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


# ------------------------------------------------------------------ enumerarea completă (GPU + CPU)
def all_combos(n: int, b: int) -> np.ndarray:
    tot = math.comb(n, b)
    flat = np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(1, n + 1), b)),
                       dtype=np.int8, count=tot * b)
    return flat.reshape(tot, b)


def enumerate_check(logw, b: int, combos: np.ndarray, adm_heap: dict) -> dict:
    import torch
    lw = np.asarray(logw, dtype=np.float64)
    idx = combos.astype(np.int64) - 1
    t0 = time.time()
    s_cpu = lw[idx].sum(1)
    t_cpu = time.time() - t0
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    it = torch.from_numpy(idx).to(dev)
    s_gpu_t = torch.as_tensor(lw, dtype=torch.float64, device=dev)[it].sum(1)
    if dev == "cuda":
        torch.cuda.synchronize()
    t_gpu = time.time() - t0
    s_gpu = s_gpu_t.cpu().numpy()
    del it, s_gpu_t
    d = np.diff(combos.astype(np.int16), axis=1)
    lin = (d == d[:, :1]).all(1)
    F = [Fraction(float(x)) for x in logw]

    def exact_best(mask):
        smax = s_gpu[mask].max()
        cand = np.nonzero(mask & (s_gpu >= smax - WINDOW))[0]
        best = min((exact_key(combos[i].tolist(), F) for i in cand))
        return list(best[1]), -best[0], int(cand.size)

    top, s_top, w_top = exact_best(np.ones(len(combos), bool))
    adm, s_adm, w_adm = exact_best(~lin)
    sa = float(s_adm)
    above = int((s_gpu > sa + WINDOW).sum())
    win = np.nonzero(np.abs(s_gpu - sa) <= WINDOW)[0]
    kadm = exact_key(adm, F)
    before = sum(1 for i in win if exact_key(combos[i].tolist(), F) < kadm)
    return {"device": dev, "n_combos": int(len(combos)), "n_linear": int(lin.sum()),
            "max_abs_gpu_cpu": float(np.abs(s_gpu - s_cpu).max()), "seconds_gpu": round(t_gpu, 3),
            "seconds_cpu": round(t_cpu, 3), "top": top, "admissible": adm, "rank": above + before + 1,
            "window_top": w_top, "window_adm": w_adm, "window_rank": int(win.size),
            "s_adm_exact_equal_heap": s_adm == adm_heap["s_adm"], "s_top_exact_equal_heap": s_top == adm_heap["s_top"]}


def gpu_temp() -> str:
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as exc:  # informativ
        return repr(exc)


def chi2_p(x2: float, df: int):
    try:
        from scipy.stats import chi2
        return float(chi2.sf(x2, df))
    except Exception:
        return None


# ------------------------------------------------------------------ rularea reală (o singură dată)
def load_emissions() -> dict:
    lant = [json.loads(ln) for ln in (TRIB / "LANT.jsonl").read_text().splitlines()]
    out = {}
    for rec in lant:
        if rec["target_date"] != TARGET:
            continue
        p = TRIB / rec["file"]
        out[rec["game"]] = {"path": p, "lant_sha": rec["sha256"], "sha": sha_file(p),
                            "mode": oct(os.stat(p).st_mode & 0o777), "em": json.loads(p.read_text())}
    return out


def main() -> int:
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    temp0 = gpu_temp()
    add("A0_ip_core_sha", sha_file(HERE / "ip_core.py") == IP_SHA, sha_file(HERE / "ip_core.py"))
    ems = load_emissions()
    for g, e in ems.items():
        add(f"A0_emisie_{g}", e["sha"] == e["lant_sha"] == EM_SHA[g] and e["mode"] == "0o444",
            {"sha": e["sha"], "mode": e["mode"]})
    add("A0_trei_emisii", sorted(ems) == ["540", "649", "joker"], sorted(ems))

    # A1: numărarea progresiilor pe enumerarea completă
    combos = {}
    for n, b in ((49, 6), (40, 5), (45, 5)):
        c = all_combos(n, b)
        combos[(n, b)] = c
        d = np.diff(c.astype(np.int16), axis=1)
        nl = int((d == d[:, :1]).all(1).sum())
        add(f"A1_progresii_{n}_{b}", nl == ap_count(n, b) and len(c) == math.comb(n, b),
            {"enumerat": nl, "forma_inchisa": ap_count(n, b), "total": len(c)})

    streams = {}
    for g in ("649", "540", "joker"):
        em = ems[g]["em"]
        n, k, b = int(em["n"]), int(em["k"]), int(em["ticket_size"])
        p_unif = math.comb(n - b, k - b) / math.comb(n, k)
        if em.get("ball_n"):
            p_unif /= int(em["ball_n"])
        for m in MODELS:
            blk = em["models"][m]
            lw = [float(x) for x in blk["logw"]]
            key = f"{g}/{m}"
            rec = {"game": g, "model": m, "n": n, "k": k, "b": b, "lambda": blk["lambda"], "X2": blk["X2"],
                   "df": blk["df"], "chi2_p_informativ": chi2_p(blk["X2"], blk["df"]),
                   "top_ticket_emis": blk["top_ticket"], "top_emis_liniar": is_linear(blk["top_ticket"]),
                   "p_uniform_orice_bilet": p_unif}
            if max(abs(x) for x in lw) == 0.0:
                rec["stare"] = "NU_PARIAZA"
                rec["bilet_afisare"] = None
                add(f"A4_{key}_nu_pariaza", blk["lambda"] == 0.0 and not blk["bet_active"], blk["lambda"])
            else:
                t0 = time.time()
                ah = admissible_heap(lw, b)
                rec["seconds_heap"] = round(time.time() - t0, 3)
                ev = enumerate_check(lw, b, combos[(n, b)], ah)
                le, lc = log_esp(lw, b), log_comb(n, b)
                rec.update({"stare": "ADMISIBIL_IDENTIC" if ah["admissible"] == ah["top"] else "ADMISIBIL_INLOCUIT",
                            "bilet_afisare": ah["admissible"], "rang": ah["rank"], "noduri_heap": ah["nodes"],
                            "ln_q_u_top": float(ah["s_top"]) - le + lc, "ln_q_u_admisibil": float(ah["s_adm"]) - le + lc,
                            "q_adm_pe_q_top": math.exp(float(ah["s_adm"] - ah["s_top"])), "enumerare": ev})
                ok = (ah["top"] == [int(x) for x in blk["top_ticket"]] and ev["top"] == ah["top"]
                      and ev["admissible"] == ah["admissible"] and ev["rank"] == ah["rank"]
                      and ev["max_abs_gpu_cpu"] <= TOL_GPU_CPU and not is_linear(ah["admissible"])
                      and ah["s_adm"] <= ah["s_top"] and ev["s_adm_exact_equal_heap"] and ev["s_top_exact_equal_heap"]
                      and (is_linear(ah["top"]) or ah["admissible"] == ah["top"]))
                add(f"A3_{key}", ok, {"top": ah["top"], "admisibil": ah["admissible"], "rang": ah["rank"],
                                      "gpu": ev["admissible"], "rang_gpu": ev["rank"],
                                      "max_abs_gpu_cpu": ev["max_abs_gpu_cpu"]})
            jb = blk.get("ball") if em.get("ball_n") else None
            if jb is not None:
                blw = [float(x) for x in jb["logw"]]
                if max(abs(x) for x in blw) == 0.0:
                    rec["bila_afisare"] = None
                    rec["bila_stare"] = "NU_PARIAZA"
                    add(f"A4_{key}_bila_nu_pariaza", jb["lambda"] == 0.0 and not jb["bet_active"], jb["lambda"])
                else:
                    rec["bila_afisare"] = int(jb["top_ball"])
                    rec["bila_stare"] = "ACTIVA"
            streams[key] = rec

    after = {g: (sha_file(e["path"]), oct(os.stat(e["path"]).st_mode & 0o777)) for g, e in ems.items()}
    add("A0_emisii_neschimbate_dupa", all(after[g] == (EM_SHA[g], "0o444") for g in after), after)
    st = [c["status"] for c in checks]
    verdict = "S17_FILTRU_AFISARE_PASS" if all(s == "PASS" for s in st) else "S17_FAIL"
    doc = {"protocol": "TU4-S17", "session": "S17", "run_utc": utc, "verdict": verdict, "n_checks": len(st),
           "n_pass": st.count("PASS"), "n_fail": st.count("FAIL"),
           "protocol_sha256": sha_file(HERE / "PROTOCOL_TU4_S17.md"), "seal_sha256": sha_file(HERE / "SIGILIU_TU4_S17.json"),
           "code_sha256": sha_file(Path(__file__)), "definitie": "pur liniar = progresie aritmetica (d>=1 constant)",
           "nota": ("strat de AFISARE: nu schimba nicio probabilitate, nu intra in judecator, nu modifica emisiile; "
                    "sub urna uniforma toate biletele au aceeasi sansa; nu este sfat de joc"),
           "gpu_temp_inainte": temp0, "gpu_temp_dupa": gpu_temp(), "streams": streams, "checks": checks,
           "positive_claims_allowed": False}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"BILETE_ADMISIBILE_{utc}.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    os.chmod(out, 0o444)
    print(out)
    print(json.dumps({k: doc[k] for k in ("verdict", "n_checks", "n_pass", "n_fail")}))
    for key, r in streams.items():
        print(key, r["stare"], r.get("bilet_afisare"), r.get("bila_afisare", ""), "rang", r.get("rang"))
    return 0 if verdict.endswith("PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
