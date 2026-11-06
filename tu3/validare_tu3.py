"""TU3-VS — suita de validare pe toate 3 căile (sintetic) și verificarea serverului (PROTOCOL_TU3_VS §1, §4).

    .venv/bin/python -B tu3/validare_tu3.py --suita     # V1–V6 → rezultate/VS/VALIDARE_TU3_<UTC>Z.json (0444)
    .venv/bin/python -B tu3/validare_tu3.py --server    # după ./run_app.sh → rezultate/VS/SERVER_TU3_<UTC>Z.json (0444)

Niciun pas nu tipărește, nu salvează și nu compară variante (nici reale, nici sintetice); din pytest se păstrează numai
numărătorile. Verificările de putere γ = 1/2 NU se rerulează: se recitesc și porțile se recalculează din valorile stocate
față de pragurile sigilate. Calcul clasic; `positive_claims_allowed=false`; variantele = minime de energie, NU predicții.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
for _p in (str(HERE), str(QL)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = QL / ".venv" / "bin" / "python"
SEAL_VS = HERE / "SIGILIU_TU3_VS.json"
OUT = HERE / "rezultate" / "VS"
BASELINE_RUN_APP = QL / "tests" / "baseline" / "run_app_v2.sh"
FAST_OVERRIDES = dict(mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60, gamma_grid=12)
SYNTH_SEEDS = {"649": 64905, "540": 54005, "joker": 45205}
SYNTH_ROWS = 200

# V1–V3: așteptările fixate în protocol (§1)
PYTEST_STEPS = {
    "V1_649_sintetic": {"cwd": QL, "args": ["tests/test_parser.py", "tests/test_engine.py", "tests/test_validare.py"],
                        "expect": {"passed": 32, "failed": 0, "errors": 0, "skipped": 0}},
    "V2_tu3_540_joker": {"cwd": HERE, "args": ["tests"],
                         "expect": {"passed": 53, "failed": 0, "errors": 0, "skipped": 0}},
    "V3_ui_3_moduri": {"cwd": QL, "args": ["tests/test_app.py", "tests/test_app_tu3.py"],
                       "expect": {"passed": 11, "failed": 0, "errors": 0, "skipped": 3}},
}

# V4: fișierele de putere și pragurile sigilate (P1 §4, E40 §4, EJ §4)
POWER_SPECS = {
    "J": {"file": HERE / "rezultate" / "J" / "PUTERE_J.json", "verdict": "J_PASS",
          "protocol": HERE / "PROTOCOL_TU3_P1.md", "witnesses": "witnesses_W1_W10", "mode_0444": False,
          "gates": [("power_gamma_1_2_B1024", ">=", 0.90, "power_gate_pass"),
                    ("fpr_control_B1024", "<=", 0.02, "fpr_gate_pass")]},
    "E40": {"file": HERE / "rezultate" / "E40" / "PUTERE_E40.json", "verdict": "E40_PASS",
            "protocol": HERE / "PROTOCOL_TU3_E40.md", "witnesses": "witnesses_E1_E10", "mode_0444": True,
            "gates": [("G1_power_gamma_1_2_B512", ">=", 0.90, "G1_pass"),
                      ("G2_fpr_control_B512", "<=", 0.02, "G2_pass")]},
    "EJ": {"file": HERE / "rezultate" / "EJ" / "PUTERE_EJ.json", "verdict": "EJ_PASS",
           "protocol": HERE / "PROTOCOL_TU3_EJ.md", "witnesses": "witnesses_EJ1_EJ11", "mode_0444": True,
           "gates": [("G1_power_gamma_1_2_B512", ">=", 0.90, "G1_pass"),
                     ("G2_fpr_control_B512", "<=", 0.02, "G2_pass"),
                     ("GJ1_joker_window_gamma_1_2_B512", ">=", 0.50, "GJ1_pass"),
                     ("GJ2_joker_window_control_B512", "<=", 0.20, "GJ2_pass")]},
}


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# V1–V3: pytest (numai numărătorile)
# ---------------------------------------------------------------------------
_COUNT_RE = re.compile(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed|deselected|warnings?)")


def parse_pytest_counts(text: str) -> dict:
    """Numărătorile din linia de rezumat pytest (ultima linie care conține „ in <timp>s”)."""
    summary = ""
    for line in text.splitlines():
        if re.search(r"\bin [\d.]+s\b", line) and _COUNT_RE.search(line):
            summary = line
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for n, kind in _COUNT_RE.findall(summary):
        key = {"error": "errors", "warning": "warnings"}.get(kind, kind)
        counts[key] = counts.get(key, 0) + int(n)
    counts["summary"] = summary.strip().strip("=").strip()
    return counts


def run_pytest(name: str, step: dict) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("QL649_UI_PROTOCOL", None)          # cele 3 teste de protocol rămân skip (§1 V3)
    t0 = time.perf_counter()
    p = subprocess.run([str(PY), "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *step["args"]],
                       cwd=step["cwd"], env=env, capture_output=True, text=True)
    c = parse_pytest_counts(p.stdout + "\n" + p.stderr)
    ok = p.returncode == 0 and all(c.get(k, 0) == v for k, v in step["expect"].items())
    return {"step": name, "pass": ok, "returncode": p.returncode, "counts": c, "expect": step["expect"],
            "args": step["args"], "seconds": round(time.perf_counter() - t0, 1)}


# ---------------------------------------------------------------------------
# V4: reverificarea puterii (fără rerulare)
# ---------------------------------------------------------------------------
def _cmp(v: float, op: str, thr: float) -> bool:
    return v >= thr if op == ">=" else v <= thr


def reverify_power(key: str, power_path: Path | None = None) -> dict:
    sp = POWER_SPECS[key]
    path = Path(power_path) if power_path is not None else sp["file"]
    checks: dict[str, bool] = {}
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return {"key": key, "pass": False, "error": f"{type(exc).__name__}: {exc}", "checks": {}}
    checks["verdict"] = d.get("verdict") == sp["verdict"]
    checks["protocol_sha256"] = d.get("protocol_sha256") == sha(sp["protocol"])
    codes = d.get("code_sha256") or {}
    checks["code_sha256"] = bool(codes) and all((HERE / rel).exists() and sha(HERE / rel) == h
                                                for rel, h in codes.items())
    w = d.get(sp["witnesses"])
    checks["witnesses"] = isinstance(w, dict) and w.get("pass") is True
    checks["real_archive_read_false"] = d.get("real_archive_read") is False
    if "positive_claims_allowed" in d:
        checks["positive_claims_allowed_false"] = d["positive_claims_allowed"] is False
    gates = []
    for field, op, thr, flag in sp["gates"]:
        v = d.get(field)
        vals = list(v.values()) if isinstance(v, dict) else [v]
        ok_vals = all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in vals)
        recomputed = ok_vals and len(vals) > 0 and all(_cmp(float(x), op, thr) for x in vals)
        stored = d.get(flag)
        gates.append({"field": field, "rule": f"{op} {thr}", "value": v, "recomputed": recomputed,
                      "stored_flag": stored, "consistent": stored is recomputed})
        checks[f"gate_{field}"] = recomputed and stored is recomputed
    mode = stat.S_IMODE(path.stat().st_mode)
    return {"key": key, "file": str(path.relative_to(QL)) if path.is_relative_to(QL) else str(path),
            "file_sha256": sha(path), "mode": oct(mode), "mode_0444_expected": sp["mode_0444"],
            "mode_note": None if not sp["mode_0444"] or mode == 0o444 else "mod diferit de 0444 (descriptiv)",
            "checks": checks, "gates": gates, "pass": all(checks.values())}


# ---------------------------------------------------------------------------
# V5: produsul cap-coadă pe date sintetice (config FAST)
# ---------------------------------------------------------------------------
def synth_rows(game: str, n_rows: int, seed: int) -> list[dict]:
    """Rânduri uniforme în schema LIVE (zile duble ocazionale). Numai sintetic."""
    import parser_multi as PM
    g = PM.spec(game)
    rng = np.random.default_rng(seed)
    rows, day = [], 0
    for i in range(n_rows):
        if i % 9 != 4:
            day += 1
        nums = sorted(int(x) + 1 for x in rng.choice(g.n, g.r, replace=False))
        d = (dt.date(2000, 1, 1) + dt.timedelta(days=day)).isoformat()
        rec = {"draw_key": f"{game}:{d}:{i:05d}", "draw_date": d, "game": game, "numbers": nums,
               "numbers_order_as_stored": nums, "draw_kind": "synthetic", "has_source_disagreement": False}
        if g.joker_m:
            rec["joker"] = int(rng.integers(1, g.joker_m + 1))
            rec["draw_key"] += f":J{rec['joker']}"
        rows.append(rec)
    return rows


def _variant_rule_ok(game: str, out: dict) -> dict:
    if game == "joker":
        V = out["variants_5plus1"]
        mains = [list(v) for v, _ in V]
        jk = [a for _, a in V]
        n, k = 45, 5
        uniq = len({(tuple(v), a) for v, a in V}) == 3
        jok_ok = all(isinstance(a, int) and 1 <= a <= 20 for a in jk)
        energies = out["energies_total"]
    else:
        mains = [list(v) for v in out["variants"]]
        n, k = (49, 6) if game == "649" else (40, 5)
        uniq = len({tuple(v) for v in mains}) == 3
        jok_ok = True
        energies = out["energies"]
    rule = len(mains) == 3 and all(len(v) == k and len(set(v)) == k and v == sorted(v) and
                                   all(1 <= x <= n for x in v) for v in mains)
    return {"three_variants": len(mains) == 3, "unique": uniq, "rule": rule and jok_ok,
            "energies_finite": len(energies) == 3 and all(math.isfinite(float(e)) for e in energies)}


def synthetic_product(game: str, workdir: Path, device=None) -> dict:
    import engine as E
    import motor_joker as MJ
    import motor_n as M
    import parser_multi as PM
    import validare as VQ
    dev = torch.device(device) if device is not None else torch.device("cuda" if torch.cuda.is_available() else "cpu")
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    if game == "649":
        ds = VQ.synthetic_dataset(workdir / "sintetic_649.jsonl", n=SYNTH_ROWS, seed=SYNTH_SEEDS["649"], device=dev)
        out = E.run_full(ds, replace(E.PROTOCOL, **FAST_OVERRIDES), dev)
    else:
        p = workdir / f"sintetic_{game}.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in synth_rows(game, SYNTH_ROWS, SYNTH_SEEDS[game])) + "\n")
        ds = PM.build_game_dataset(game, p, device=dev)
        if game == "540":
            out = M.run_full(ds, M.SHAPE_540, replace(M.PROTOCOL_540, **FAST_OVERRIDES), dev)
        else:
            out = MJ.engine_joker(ds, replace(MJ.PROTOCOL_JOKER, **FAST_OVERRIDES), dev)
    checks = _variant_rule_ok(game, out)
    checks["is_protocol_false"] = out.get("is_protocol") is False
    checks["positive_claims_allowed_false"] = out.get("positive_claims_allowed") is False
    checks["device_cuda_when_available"] = (not torch.cuda.is_available()) or str(out.get("device", "")).startswith("cuda")
    res = {"game": game, "seed": SYNTH_SEEDS[game], "rows": SYNTH_ROWS, "n_draws": int(ds.n_draws),
           "n_steps": int(ds.n_steps), "device": str(out.get("device")), "config_digest": out.get("config_digest"),
           "seconds": round(time.perf_counter() - t0, 1), "checks": checks, "pass": all(checks.values())}
    del out, ds
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return res


# ---------------------------------------------------------------------------
# V6: integritate
# ---------------------------------------------------------------------------
def insertions_only(base_text: str, new_text: str) -> bool:
    a, b = base_text.splitlines(keepends=True), new_text.splitlines(keepends=True)
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    return all(tag in ("equal", "insert") for tag, *_ in ops) and \
        sum(i2 - i1 for tag, i1, i2, _, _ in ops if tag == "equal") == len(a)


def integrity_check() -> dict:
    """V6 (cu AMENDAMENT_TU3_VS_01 §2): run_app.sh byte-identic cu copia; inserțiile (a)/(b) în run_app_tu3.sh."""
    seal = json.loads(SEAL_VS.read_text())
    import inlocuiri_tu3 as INL   # TU3-L649 §5.2: fișier înghețat = identic SAU înlocuit sigilat (inlocuiri_tu3/v1)
    res = INL.resolve(seal["frozen_hashes"], QL)
    drift = res["drift"]
    base_ok = BASELINE_RUN_APP.exists() and sha(BASELINE_RUN_APP) == seal["run_app_sh_before"]
    run_app_same = sha(QL / "run_app.sh") == seal["run_app_sh_before"]
    launcher = QL / "run_app_tu3.sh"
    lt = launcher.read_text() if launcher.exists() else ""
    launcher_ok = ("tu3/matrice_init.py" in lt and "-m py_compile tu3/ui_tu3.py" in lt and
                   lt.rstrip().endswith("exec ./run_app.sh") and 'jurnal/matrice_' in lt)
    bash_n = all(subprocess.run(["bash", "-n", str(p)], capture_output=True).returncode == 0
                 for p in (QL / "run_app.sh", launcher)) if launcher.exists() else False
    checks = {"frozen_hashes": not drift, "baseline_run_app_sha": base_ok, "run_app_byte_identical": run_app_same,
              "launcher_run_app_tu3": launcher_ok, "bash_n": bash_n}
    return {"step": "V6_integritate", "checks": checks, "drift": drift, "checked": len(seal["frozen_hashes"]),
            "replaced": res["replaced"], "replacement_records": res["records"],
            "run_app_sha256": sha(QL / "run_app.sh"),
            "run_app_tu3_sha256": sha(launcher) if launcher.exists() else None,
            "amendment": "AMENDAMENT_TU3_VS_01", "seal_sha256": sha(SEAL_VS), "pass": all(checks.values())}


# ---------------------------------------------------------------------------
# Rapoarte
# ---------------------------------------------------------------------------
def write_report(prefix: str, payload: dict, out_dir: Path = OUT) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{prefix}_{utc_stamp()}.json"
    with open(dst, "x", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")
    os.chmod(dst, 0o444)
    return dst


def run_suite(log=print) -> dict:
    t0 = time.perf_counter()
    rep = {"protocol": "TU3-VS", "protocol_sha256": sha(HERE / "PROTOCOL_TU3_VS.md"), "seal_sha256": sha(SEAL_VS),
           "amendments_sha256": {p.name: sha(p) for p in sorted(HERE.glob("AMENDAMENT_TU3_VS_*.md"))},
           "start_utc": utc_iso(), "torch": torch.__version__, "cuda": torch.cuda.is_available(),
           "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
           "code_sha256": {"tu3/validare_tu3.py": sha(Path(__file__)), "tu3/matrice_init.py": sha(HERE / "matrice_init.py")},
           "steps": {}}
    for name, step in PYTEST_STEPS.items():
        log(f"[TU3-VS] {name}: pytest {' '.join(step['args'])} …")
        r = run_pytest(name, step)
        rep["steps"][name] = r
        log(f"[TU3-VS] {name}: {r['counts']['summary']} → {'PASS' if r['pass'] else 'FAIL'}")
    v4 = {k: reverify_power(k) for k in POWER_SPECS}
    rep["steps"]["V4_putere_reverificare"] = {"pass": all(r["pass"] for r in v4.values()), "files": v4,
                                              "rerun": False}
    log(f"[TU3-VS] V4 reverificare putere: " + ", ".join(f"{k} {'PASS' if r['pass'] else 'FAIL'}" for k, r in v4.items()))
    with tempfile.TemporaryDirectory(prefix="tu3vs_") as td:
        v5 = {g: synthetic_product(g, Path(td) / g) for g in ("649", "540", "joker")}
    rep["steps"]["V5_produs_sintetic_FAST"] = {"pass": all(r["pass"] for r in v5.values()), "paths": v5,
                                               "fast_overrides": FAST_OVERRIDES}
    log(f"[TU3-VS] V5 produs sintetic: " + ", ".join(f"{g} {'PASS' if r['pass'] else 'FAIL'} ({r['seconds']}s)"
                                                    for g, r in v5.items()))
    v6 = integrity_check()
    rep["steps"]["V6_integritate"] = v6
    log(f"[TU3-VS] V6 integritate: {'PASS' if v6['pass'] else 'FAIL'} ({v6['checked']} fișiere înghețate)")
    rep["pass"] = all(s["pass"] for s in rep["steps"].values())
    rep["verdict"] = "VS_SUITE_PASS" if rep["pass"] else "VS_SUITE_FAIL"
    rep["end_utc"] = utc_iso()
    rep["seconds"] = round(time.perf_counter() - t0, 1)
    rep["variants_printed_or_saved"] = False
    rep["real_history_scored"] = False
    rep["positive_claims_allowed"] = False
    rep["note"] = ("Validare de inginerie pe date sintetice + reverificarea puterii fără rerulare. Nu spune nimic despre "
                   "arhiva reală. Variante = minime de energie, NU predicții. Calcul clasic.")
    return rep


# ---------------------------------------------------------------------------
# §4 serverul
# ---------------------------------------------------------------------------
def _http(url: str, timeout: float = 3.0) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 — numai 127.0.0.1
        return r.status, r.read(4096).decode("utf-8", "replace")


def listen_sockets(port: int) -> list[str]:
    p = subprocess.run(["ss", "-ltnH", f"sport = :{port}"], capture_output=True, text=True)
    return [ln.split()[3] for ln in p.stdout.splitlines() if len(ln.split()) >= 4]


def check_server(address: str = "127.0.0.1", port: int = 8649, wait_s: float = 120.0, log=print) -> dict:
    base = f"http://{address}:{port}"
    t0, health = time.perf_counter(), None
    while time.perf_counter() - t0 < wait_s:
        try:
            health = _http(base + "/_stcore/health")[1].strip()
            if health == "ok":
                break
        except OSError:
            pass
        time.sleep(1.0)
    checks: dict[str, bool] = {"health_ok": health == "ok"}
    try:
        checks["root_200"] = _http(base + "/")[0] == 200
    except OSError:
        checks["root_200"] = False
    socks = listen_sockets(port)
    checks["listen_loopback_only"] = bool(socks) and all(s.startswith("127.0.0.1:") for s in socks)
    jur = QL / "jurnal"
    mats = sorted(jur.glob("matrice_*Z.txt"), key=lambda p: p.stat().st_mtime)   # AMENDAMENT_TU3_VS_01 §2
    logs = sorted(jur.glob("app_*Z.log"), key=lambda p: p.stat().st_mtime)
    matrix_json, mat_txt = None, mats[-1] if mats else None
    if mat_txt is not None:
        m = re.search(r"json: (\S+)", mat_txt.read_text())
        if m and Path(m.group(1)).exists():
            matrix_json = json.loads(Path(m.group(1)).read_text())
    checks["matrix_printed"] = mat_txt is not None and matrix_json is not None
    checks["matrix_3_ready"] = bool(matrix_json) and len(matrix_json["modes"]) == 3 and \
        all(r["status"] == "READY" for r in matrix_json["modes"])
    checks["matrix_integrity_ok"] = bool(matrix_json) and matrix_json["integrity"]["status"] == "OK"
    checks["matrix_no_variants"] = bool(matrix_json) and not re.search(r'"variants[^"]*"\s*:', json.dumps(matrix_json))
    log_txt = logs[-1].read_text(errors="replace") if logs else ""
    checks["server_log_present"] = bool(logs)
    checks["server_log_no_traceback"] = bool(logs) and "Traceback" not in log_txt
    rep = {"protocol": "TU3-VS", "check_utc": utc_iso(), "url": base, "health": health, "listen": socks,
           "matrix_txt": str(mat_txt.relative_to(QL)) if mat_txt else None,
           "matrix_json_modes": [{k: r.get(k) for k in ("mode", "source_kind", "source_sha256", "n_draws",
                                                         "last_date", "power_verdict", "status")}
                                 for r in (matrix_json or {}).get("modes", [])],
           "server_log": str(logs[-1].relative_to(QL)) if logs else None, "checks": checks,
           "pass": all(checks.values()), "positive_claims_allowed": False,
           "note": "Serverul servește produsul existent; variantele = minime de energie, NU predicții."}
    rep["verdict"] = "VS_SERVER_PASS" if rep["pass"] else "VS_SERVER_FAIL"
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TU3-VS — validare pe 3 căi (sintetic) + verificarea serverului")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--suita", action="store_true")
    g.add_argument("--server", action="store_true")
    ap.add_argument("--address", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8649)
    a = ap.parse_args(argv)
    if a.suita:
        rep = run_suite()
        dst = write_report("VALIDARE_TU3", rep)
    else:
        rep = check_server(a.address, a.port)
        dst = write_report("SERVER_TU3", rep)
        for k, v in rep["checks"].items():
            print(f"[TU3-VS] server {k}: {'OK' if v else 'FAIL'}")
    print(f"[TU3-VS] verdict {rep['verdict']} → {dst.relative_to(QL)} (sha {sha(dst)[:12]}…)")
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
