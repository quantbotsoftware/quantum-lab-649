"""TU3 modul E40 — verificarea de putere sintetică (PROTOCOL_TU3_E40 §4). NU citește arhiva reală.

Rulează: martorii E1–E10 (pytest pe `tests/test_motor_n.py`; E11 este `skip` până la verdict), apoi motorul E40
complet (O1–O6, `PROTOCOL_540`) pe universuri sintetice cu o mulțime plantată H de 5 numere:
  G1 putere  — B1 = 512 universuri la γ = 1/2 (sămânța 540002): PASS dacă fracția cu p ≤ 0.01 este ≥ 0.90;
  G2 control — B2 = 512 universuri la γ = 0   (sămânța 540004): PASS dacă rata fals-pozitivă este ≤ 0.02;
  descriptiv — B = 256 la γ = 1/8 (sămânța 540003).
Statistica S = Σ_v |V_v ∩ H|, cu valoarea p EXACTĂ condiționată de variante (funcție generatoare pe întregi).
Verdict `E40_PASS` numai dacă E1–E10 trec și G1, G2 trec; altfel `E40_FAIL`. Scrie `rezultate/E40/PUTERE_E40.json`
(0444); refuză suprascrierea (rulare unică, fără retuning).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import motor_n as M  # noqa: E402

OUT = M.POWER_FILE
T = 2490
CHUNK = 128
BETA = 1.0
SHAPE = M.SHAPE_540
CFG = M.PROTOCOL_540
ALPHA = 0.01
N_SUBSETS = math.comb(40, 5)
SETS = {"gamma_1_2": (2, 0.5, 512, 540002), "gamma_1_8": (3, 0.125, 256, 540003), "control": (4, 0.0, 512, 540004)}


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def synth_chunk(b: int, gamma: float, g: torch.Generator, dev) -> tuple[torch.Tensor, torch.Tensor]:
    """b universuri × T extrageri de 6 din 40; H = 5 numere plantate per univers (indici 0..39)."""
    H = torch.rand(b, 40, generator=g, device=dev).argsort(-1)[:, :5]
    inH = torch.zeros(b, 40, dtype=torch.float32, device=dev)
    inH.scatter_(1, H, 1.0)
    mix = (torch.rand(b, T, generator=g, device=dev) < gamma).to(torch.float32)
    U = torch.rand(b, T, 40, generator=g, device=dev).clamp(min=1e-12, max=1 - 1e-7)
    gum = -torch.log(-torch.log(U))
    logits = BETA * inH[:, None, :] * mix[..., None] + gum
    draws = torch.sort(logits.topk(6, dim=-1).indices, dim=-1).values + 1
    return draws, torch.sort(H, dim=-1).values


def exact_pvalue(m: list[int], s_obs: int) -> float:
    """P_{H' uniform, |H'|=5}(Σ_{j∈H'} m_j ≥ s_obs), exact pe întregi (m_j ∈ {0..3})."""
    cnt = [m.count(v) for v in range(4)]
    tot = 0
    for a1 in range(6):
        for a2 in range(6 - a1):
            for a3 in range(6 - a1 - a2):
                a0 = 5 - a1 - a2 - a3
                if a1 + 2 * a2 + 3 * a3 >= s_obs:
                    tot += math.comb(cnt[0], a0) * math.comb(cnt[1], a1) * math.comb(cnt[2], a2) * math.comb(cnt[3], a3)
    return tot / N_SUBSETS


def run_set(set_id: int, gamma: float, B: int, seed: int, dev, timings: dict) -> dict:
    g = torch.Generator(device=dev).manual_seed(seed)
    step_index = torch.arange(T, device=dev)
    S, P, H1, rank = [], [], [], []
    for s0 in range(0, B, CHUNK):
        b = min(CHUNK, B - s0)
        draws, H = synth_chunk(b, gamma, g, dev)
        st = M.final_state(draws, step_index, T, SHAPE, CFG)
        del draws
        seeds = torch.tensor([540 * 10**6 + set_id * 10**5 + u for u in range(s0, s0 + b)], dtype=torch.int64)
        sc = M.score_states(st, seeds, SHAPE, CFG, timings=timings)
        t0 = time.perf_counter()
        vv = M.variants_steps(sc["pi"], sc["A"], st["k"], SHAPE, CFG, seeds=seeds)
        if dev.type == "cuda":
            torch.cuda.synchronize()
        timings["O6_mcmc_qubo"] = timings.get("O6_mcmc_qubo", 0.0) + time.perf_counter() - t0
        V = (vv["variants"] - 1).cpu()
        Hc = H.cpu()
        order = torch.argsort(torch.argsort(-sc["pi"].cpu(), dim=-1, stable=True), dim=-1) + 1   # rang 1 = cel mai mare π
        for i in range(b):
            hs = set(Hc[i].tolist())
            m = [0] * 40
            for v in V[i].tolist():
                for j in v:
                    m[j] += 1
            s_obs = sum(m[j] for j in hs)
            S.append(s_obs)
            P.append(exact_pvalue(m, s_obs))
            H1.append(len(hs & set(V[i, 0].tolist())))
            rank.append(float(order[i, Hc[i]].to(torch.float64).mean()))
        print(f"  set {set_id} γ={gamma}: {s0 + b}/{B}", flush=True)
    n_sig = sum(p <= ALPHA for p in P)
    return {"gamma": gamma, "B": B, "seed": seed, "significant": n_sig, "rate": n_sig / B,
            "S_mean": sum(S) / B, "S_hist": {str(v): S.count(v) for v in sorted(set(S))},
            "V1_hits_mean": sum(H1) / B, "H_rank_in_pi_mean": sum(rank) / B,
            "p_min": min(P), "p_median": sorted(P)[B // 2]}


def main() -> int:
    if OUT.exists():
        print(f"REFUZ: {OUT} există deja (rulare unică, E40 §4).")
        return 2
    seal = json.loads((HERE / "SIGILIU_TU3_E40.json").read_text())
    assert sha(HERE / "PROTOCOL_TU3_E40.md") == seal["sha256"], "protocol modificat după sigilare"
    assert sha(HERE.parent / "engine.py") == seal["engine_sha256"], "engine.py modificat"
    t0 = time.time()
    start = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            "tests/test_motor_n.py"], cwd=HERE, capture_output=True, text=True)
    w_pass = tests.returncode == 0
    print("martori E1–E10:", tests.stdout.strip().splitlines()[-1:], flush=True)
    dev = M.PM.QP.resolve_device()
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats(dev)
    timings: dict = {}
    res_sets = {}
    for name in ("gamma_1_2", "control", "gamma_1_8"):
        sid, gamma, B, seed = SETS[name]
        res_sets[name] = run_set(sid, gamma, B, seed, dev, timings)
    power = res_sets["gamma_1_2"]["rate"]
    fpr = res_sets["control"]["rate"]
    g1, g2 = power >= 0.90, fpr <= 0.02
    verdict = "E40_PASS" if (w_pass and g1 and g2) else "E40_FAIL"
    res = {
        "protocol": "TU3-E40", "protocol_sha256": seal["sha256"], "start_utc": start,
        "end_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seconds": round(time.time() - t0, 2), "device": str(dev), "device_events": M.PM.QP.device_events(),
        "torch": torch.__version__, "T": T, "chunk": CHUNK, "beta": BETA, "alpha": ALPHA,
        "config_digest": CFG.digest(), "shape": {"n": SHAPE.n, "r": SHAPE.r, "k": SHAPE.k},
        "code_sha256": {"motor_n.py": sha(HERE / "motor_n.py"), "putere_e40.py": sha(Path(__file__)),
                        "tests/test_motor_n.py": sha(HERE / "tests" / "test_motor_n.py")},
        "witnesses_E1_E10": {"pass": w_pass, "pytest_tail": tests.stdout.strip().splitlines()[-1:]},
        "sets": res_sets,
        "G1_power_gamma_1_2_B512": power, "G1_pass": g1,
        "G2_fpr_control_B512": fpr, "G2_pass": g2,
        "descriptive_gamma_1_8_rate": res_sets["gamma_1_8"]["rate"],
        "timings_s": timings, "verdict": verdict,
        "note": "Putere pe date SINTETICE; nu spune nimic despre arhiva reală. Variante = minime de energie, NU "
                "predicții. positive_claims_allowed=false.",
        "real_archive_read": False, "positive_claims_allowed": False,
    }
    if dev.type == "cuda":
        res["vram_peak_bytes"] = int(torch.cuda.max_memory_allocated(dev))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    os.chmod(OUT, 0o444)
    print(json.dumps({k: res[k] for k in ("verdict", "G1_power_gamma_1_2_B512", "G2_fpr_control_B512",
                                          "descriptive_gamma_1_8_rate", "seconds")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
