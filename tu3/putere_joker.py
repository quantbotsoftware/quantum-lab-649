"""TU3 modul J — verificarea de putere sintetică (PROTOCOL_TU3_P1 §4). Nu citește arhiva reală.

Rulează: martorii W1–W10 (pytest), nulul B0 = 4096 (sămânța 649001) → praguri q0.99 (torch.quantile, liniar),
puterea B1 = 1024 la γ = 1/2 (649002), controlul B2 = 1024 la γ = 0 (649004), descriptiv γ = 1/8 (649003).
Verdict J_PASS numai dacă W1–W10 trec, puterea ≥ 0.90 și FPR ≤ 0.02 pentru FIECARE dintre I, S_E, Φ.
Scrie `rezultate/J/PUTERE_J.json`; refuză suprascrierea (rulare unică).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import joker_entanglement as J  # noqa: E402

OUT = HERE / "rezultate" / "J" / "PUTERE_J.json"
T = 2201
CHUNK = 256
STATS = ("I", "S_E", "Phi")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_universes(B: int, gamma: float, seed: int, dev) -> dict:
    g = torch.Generator(device=dev).manual_seed(seed)
    acc = {k: [] for k in STATS}
    for s0 in range(0, B, CHUNK):
        b = min(CHUNK, B - s0)
        main0, jok0 = J.synth_universes(b, T, gamma, g, dev)
        st = J.batch_stats(J.joint_counts(main0, jok0))
        for k in STATS:
            acc[k].append(st[k])
    return {k: torch.cat(v) for k, v in acc.items()}


def summary(x: torch.Tensor) -> dict:
    return {"mean": float(x.mean()), "std": float(x.std()), "min": float(x.min()), "max": float(x.max())}


def main() -> int:
    if OUT.exists():
        print(f"REFUZ: {OUT} există deja (rulare unică, P1 §4).")
        return 2
    OUT.parent.mkdir(parents=True, exist_ok=True)
    seal = json.loads((HERE / "SIGILIU_TU3_P1.json").read_text())
    assert sha(HERE / "PROTOCOL_TU3_P1.md") == seal["sha256"], "protocol modificat după sigilare"
    for a in ("01", "02"):
        s = json.loads((HERE / f"SIGILIU_AMENDAMENT_TU3_{a}.json").read_text())
        assert sha(HERE / f"AMENDAMENT_TU3_{a}.md") == s["sha256"], f"amendament {a} modificat"
    t0 = time.time()
    start = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
                           cwd=HERE, capture_output=True, text=True)
    w_pass = tests.returncode == 0
    dev = J.resolve_device()
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats(dev)
    null = run_universes(4096, 0.0, 649001, dev)
    thr = {k: float(torch.quantile(null[k], 0.99)) for k in STATS}
    pw = run_universes(1024, 0.5, 649002, dev)
    ctl = run_universes(1024, 0.0, 649004, dev)
    weak = run_universes(1024, 0.125, 649003, dev)
    power = {k: float((pw[k] > thr[k]).to(J.F64).mean()) for k in STATS}
    fpr = {k: float((ctl[k] > thr[k]).to(J.F64).mean()) for k in STATS}
    weak_power = {k: float((weak[k] > thr[k]).to(J.F64).mean()) for k in STATS}
    power_ok = all(power[k] >= 0.90 for k in STATS)
    fpr_ok = all(fpr[k] <= 0.02 for k in STATS)
    verdict = "J_PASS" if (w_pass and power_ok and fpr_ok) else "J_FAIL"
    res = {
        "protocol": "TU3-P1", "protocol_sha256": seal["sha256"], "start_utc": start,
        "end_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seconds": round(time.time() - t0, 2), "device": str(dev), "device_events": J.DEVICE_EVENTS,
        "torch": torch.__version__, "T": T, "chunk": CHUNK, "beta": J.BETA_SYNTH,
        "code_sha256": {"joker_entanglement.py": sha(HERE / "joker_entanglement.py"),
                        "putere_joker.py": sha(Path(__file__)),
                        "tests/test_joker_entanglement.py": sha(HERE / "tests" / "test_joker_entanglement.py")},
        "witnesses_W1_W10": {"pass": w_pass, "pytest_tail": tests.stdout.strip().splitlines()[-1:]},
        "seeds": {"null": 649001, "gamma_1_2": 649002, "gamma_1_8": 649003, "control": 649004},
        "thresholds_q099": thr,
        "null_B0_4096": {k: summary(null[k]) for k in STATS},
        "power_gamma_1_2_B1024": power, "power_gate_pass": power_ok,
        "fpr_control_B1024": fpr, "fpr_gate_pass": fpr_ok,
        "descriptive_gamma_1_8_power": weak_power,
        "gamma_1_2": {k: summary(pw[k]) for k in STATS},
        "gamma_1_8": {k: summary(weak[k]) for k in STATS},
        "verdict": verdict,
        "note": "Putere pe date SINTETICE; nu spune nimic despre arhiva reală. positive_claims_allowed=false.",
        "real_archive_read": False,
    }
    if dev.type == "cuda":
        res["vram_peak_bytes"] = int(torch.cuda.max_memory_allocated(dev))
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: res[k] for k in ("verdict", "thresholds_q099", "power_gamma_1_2_B1024",
                                          "fpr_control_B1024", "descriptive_gamma_1_8_power", "seconds")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
