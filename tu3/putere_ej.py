"""TU3 modul E-J — verificarea de putere sintetică (PROTOCOL_TU3_EJ §4). NU citește arhiva reală.

Rulează: martorii EJ1–EJ11 (pytest pe `tests/test_motor_joker.py`; EJ12 este `skip` până la verdict), apoi motorul E-J
complet (O1–O6 pe 5/45 + Joker din tensorul comun J, `PROTOCOL_JOKER`) pe universuri sintetice cu o mulțime plantată
H de 5 numere și un Joker plantat a_H, purtate simultan de extragerile înclinate (Bernoulli comun γ):
  G1  putere principală — B1 = 512 la γ = 1/2 (sămânța 452002): fracția cu p ≤ 0.01 ≥ 0.90;
  G2  control principal — B2 = 512 la γ = 0   (sămânța 452004): rata fals-pozitivă ≤ 0.02;
  GJ1 putere Joker      — aceleași B1: rata-fereastră d(a*_1, a_H) ≤ 1 ≥ 0.50;
  GJ2 control Joker     — aceleași B2: rata-fereastră ≤ 0.20 (nul exact 3/20);
  descriptiv — B = 256 la γ = 1/8 (sămânța 452003).
Verdict `EJ_PASS` numai dacă EJ1–EJ11 trec și G1, G2, GJ1, GJ2 trec; altfel `EJ_FAIL`. Scrie
`rezultate/EJ/PUTERE_EJ.json` (0444); refuză suprascrierea (rulare unică, fără retuning).
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
import motor_joker as MJ  # noqa: E402

M, JE = MJ.M, MJ.JE
OUT = MJ.POWER_FILE
T = 2202
CHUNK = 128
BETA = 1.0
BETA_J = 1.0
SHAPE = MJ.SHAPE_JOKER
CFG = MJ.PROTOCOL_JOKER
ALPHA = 0.01
N_SUBSETS = math.comb(45, 5)
SETS = {"gamma_1_2": (2, 0.5, 512, 452002), "gamma_1_8": (3, 0.125, 256, 452003), "control": (4, 0.0, 512, 452004)}


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def synth_chunk(b: int, gamma: float, g: torch.Generator, dev):
    """b universuri × T extrageri Joker (5 din 45 + 1 din 20). Ordinea apelurilor fixată în §4."""
    H = torch.rand(b, 45, generator=g, device=dev).argsort(-1)[:, :5]
    aH = torch.randint(0, 20, (b,), generator=g, device=dev)
    mix = (torch.rand(b, T, generator=g, device=dev) < gamma).to(torch.float32)
    inH = torch.zeros(b, 45, dtype=torch.float32, device=dev)
    inH.scatter_(1, H, 1.0)
    U = torch.rand(b, T, 45, generator=g, device=dev).clamp(min=1e-12, max=1 - 1e-7)
    logits = BETA * inH[:, None, :] * mix[..., None] - torch.log(-torch.log(U))
    del U
    draws = torch.sort(logits.topk(5, dim=-1).indices, dim=-1).values + 1
    del logits
    UJ = torch.rand(b, T, 20, generator=g, device=dev).clamp(min=1e-12, max=1 - 1e-7)
    phi = JE.joker_phases(20, dev)
    tilt = torch.cos(phi[None, :] - phi[aH][:, None]).to(torch.float32)          # [b,20]
    joker0 = (BETA_J * tilt[:, None, :] * mix[..., None] - torch.log(-torch.log(UJ))).argmax(-1)
    return draws, torch.sort(H, dim=-1).values, aH, joker0


def exact_pvalue(m: list[int], s_obs: int) -> float:
    """P_{H' uniform, |H'|=5 din 45}(Σ_{j∈H'} m_j ≥ s_obs), exact pe întregi (m_j ∈ {0..3})."""
    cnt = [m.count(v) for v in range(4)]
    tot = 0
    for a1 in range(6):
        for a2 in range(6 - a1):
            for a3 in range(6 - a1 - a2):
                a0 = 5 - a1 - a2 - a3
                if a1 + 2 * a2 + 3 * a3 >= s_obs:
                    tot += math.comb(cnt[0], a0) * math.comb(cnt[1], a1) * math.comb(cnt[2], a2) * math.comb(cnt[3], a3)
    return tot / N_SUBSETS


def circ(a: int, b: int) -> int:
    d = abs(a - b) % 20
    return min(d, 20 - d)


def first_argmax(x: torch.Tensor) -> torch.Tensor:
    ar = torch.arange(x.shape[-1], device=x.device)
    return torch.where(x == x.amax(-1, keepdim=True), ar, torch.full_like(ar, x.shape[-1])).amin(-1)


def run_set(set_id: int, gamma: float, B: int, seed: int, dev, timings: dict) -> dict:
    g = torch.Generator(device=dev).manual_seed(seed)
    step_index = torch.arange(T, device=dev)
    phi = [2 * math.pi * a / 20 for a in range(20)]
    S, P, H1, rank = [], [], [], []
    jw, jx, jd, jrank, ow, ox, mw, sj = [], [], [], [], [], [], [], []
    for s0 in range(0, B, CHUNK):
        b = min(CHUNK, B - s0)
        draws, H, aH, joker0 = synth_chunk(b, gamma, g, dev)
        st = M.final_state(draws, step_index, T, SHAPE, CFG)
        N = JE.joint_counts(draws - 1, joker0)
        del draws, joker0
        seeds = torch.tensor([4520 * 10**6 + set_id * 10**5 + u for u in range(s0, s0 + b)], dtype=torch.int64)
        sc = M.score_states(st, seeds, SHAPE, CFG, timings=timings)
        t0 = time.perf_counter()
        vv = M.variants_steps(sc["pi"], sc["A"], st["k"], SHAPE, CFG, seeds=seeds)
        if dev.type == "cuda":
            torch.cuda.synchronize()
        timings["O6_mcmc_qubo"] = timings.get("O6_mcmc_qubo", 0.0) + time.perf_counter() - t0
        t0 = time.perf_counter()
        js = MJ.joker_stage(N, vv["variants"], CFG)
        orc = MJ.joker_stage(N, (H + 1)[:, None, :], CFG)["jokers"][:, 0] - 1
        marg = first_argmax(N.sum(1))
        timings["J_joker_stage"] = timings.get("J_joker_stage", 0.0) + time.perf_counter() - t0
        V = (vv["variants"] - 1).cpu()
        Hc, aHc = H.cpu(), aH.cpu().tolist()
        jok = (js["jokers"] - 1).cpu().tolist()
        q1 = js["q"][:, 0].cpu()
        orc, marg = orc.cpu().tolist(), marg.cpu().tolist()
        order = torch.argsort(torch.argsort(-sc["pi"].cpu(), dim=-1, stable=True), dim=-1) + 1   # rang 1 = cel mai mare π
        qorder = torch.argsort(torch.argsort(-q1, dim=-1, stable=True), dim=-1) + 1
        for i in range(b):
            hs = set(Hc[i].tolist())
            m = [0] * 45
            for v in V[i].tolist():
                for j in v:
                    m[j] += 1
            s_obs = sum(m[j] for j in hs)
            S.append(s_obs)
            P.append(exact_pvalue(m, s_obs))
            H1.append(len(hs & set(V[i, 0].tolist())))
            rank.append(float(order[i, Hc[i]].to(torch.float64).mean()))
            a = aHc[i]
            d1 = circ(jok[i][0], a)
            jd.append(d1)
            jw.append(d1 <= 1)
            jx.append(d1 == 0)
            jrank.append(int(qorder[i, a]))
            ow.append(circ(orc[i], a) <= 1)
            ox.append(orc[i] == a)
            mw.append(circ(marg[i], a) <= 1)
            sj.append(sum(math.cos(phi[x] - phi[a]) for x in jok[i]))
        print(f"  set {set_id} γ={gamma}: {s0 + b}/{B}", flush=True)
    n_sig = sum(p <= ALPHA for p in P)
    return {"gamma": gamma, "B": B, "seed": seed, "significant": n_sig, "rate": n_sig / B,
            "S_mean": sum(S) / B, "S_hist": {str(v): S.count(v) for v in sorted(set(S))},
            "V1_hits_mean": sum(H1) / B, "H_rank_in_pi_mean": sum(rank) / B,
            "p_min": min(P), "p_median": sorted(P)[B // 2],
            "joker_window_hits": sum(jw), "joker_window_rate": sum(jw) / B,
            "joker_exact_rate": sum(jx) / B, "joker_circ_dist_mean": sum(jd) / B,
            "joker_circ_dist_hist": {str(v): jd.count(v) for v in sorted(set(jd))},
            "aH_rank_in_qV1_mean": sum(jrank) / B, "S_J_mean": sum(sj) / B,
            "oracle_V_eq_H_window_rate": sum(ow) / B, "oracle_V_eq_H_exact_rate": sum(ox) / B,
            "marginal_selector_window_rate": sum(mw) / B}


def main() -> int:
    if OUT.exists():
        print(f"REFUZ: {OUT} există deja (rulare unică, E-J §4).")
        return 2
    seal = json.loads(MJ.SEAL_FILE.read_text())
    assert sha(MJ.PROTOCOL_FILE) == seal["sha256"], "protocol modificat după sigilare"
    assert sha(HERE.parent / "engine.py") == seal["engine_sha256"], "engine.py modificat"
    assert sha(HERE / "motor_n.py") == seal["motor_n_sha256"], "motor_n.py modificat"
    assert sha(HERE / "joker_entanglement.py") == seal["joker_entanglement_sha256"], "joker_entanglement.py modificat"
    t0 = time.time()
    start = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            "tests/test_motor_joker.py"], cwd=HERE, capture_output=True, text=True)
    w_pass = tests.returncode == 0
    print("martori EJ1–EJ11:", tests.stdout.strip().splitlines()[-1:], flush=True)
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
    jpow = res_sets["gamma_1_2"]["joker_window_rate"]
    jfpr = res_sets["control"]["joker_window_rate"]
    g1, g2, gj1, gj2 = power >= 0.90, fpr <= 0.02, jpow >= 0.50, jfpr <= 0.20
    verdict = "EJ_PASS" if (w_pass and g1 and g2 and gj1 and gj2) else "EJ_FAIL"
    res = {
        "protocol": "TU3-EJ", "protocol_sha256": seal["sha256"], "start_utc": start,
        "end_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seconds": round(time.time() - t0, 2), "device": str(dev), "device_events": M.PM.QP.device_events(),
        "torch": torch.__version__, "T": T, "chunk": CHUNK, "beta": BETA, "beta_J": BETA_J, "alpha": ALPHA,
        "config_digest": CFG.digest(), "shape": {"n": SHAPE.n, "r": SHAPE.r, "k": SHAPE.k, "joker_m": 20},
        "code_sha256": {"motor_joker.py": sha(HERE / "motor_joker.py"), "putere_ej.py": sha(Path(__file__)),
                        "tests/test_motor_joker.py": sha(HERE / "tests" / "test_motor_joker.py"),
                        "motor_n.py": sha(HERE / "motor_n.py"),
                        "joker_entanglement.py": sha(HERE / "joker_entanglement.py")},
        "witnesses_EJ1_EJ11": {"pass": w_pass, "pytest_tail": tests.stdout.strip().splitlines()[-1:]},
        "sets": res_sets,
        "G1_power_gamma_1_2_B512": power, "G1_pass": g1,
        "G2_fpr_control_B512": fpr, "G2_pass": g2,
        "GJ1_joker_window_gamma_1_2_B512": jpow, "GJ1_pass": gj1,
        "GJ2_joker_window_control_B512": jfpr, "GJ2_pass": gj2,
        "descriptive_gamma_1_8": {"rate": res_sets["gamma_1_8"]["rate"],
                                  "joker_window_rate": res_sets["gamma_1_8"]["joker_window_rate"]},
        "timings_s": timings, "verdict": verdict,
        "note": "Putere pe date SINTETICE; nu spune nimic despre arhiva reală. Variante 5+1 = minime de energie, NU "
                "predicții. positive_claims_allowed=false.",
        "real_archive_read": False, "positive_claims_allowed": False,
    }
    if dev.type == "cuda":
        res["vram_peak_bytes"] = int(torch.cuda.max_memory_allocated(dev))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    os.chmod(OUT, 0o444)
    print(json.dumps({k: res[k] for k in ("verdict", "G1_power_gamma_1_2_B512", "G2_fpr_control_B512",
                                          "GJ1_joker_window_gamma_1_2_B512", "GJ2_joker_window_control_B512",
                                          "descriptive_gamma_1_8", "seconds")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
