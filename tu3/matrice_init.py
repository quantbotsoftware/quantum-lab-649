"""TU3-VS — matricea de inițializare a sistemului (PROTOCOL_TU3_VS §2).

Tipărită de `run_app.sh` la pornirea serverului (și la cerere). NU rulează niciun motor (`engine.run_full`,
`motor_n.run_full*`, `motor_joker.engine_joker` / `run_full_joker`) și NU conține variante: doar starea sistemului,
seturile de date (inventar), protocoalele, verdictele de putere și integritatea fișierelor înghețate.
Calcul clasic; `positive_claims_allowed=false`. Variantele produsului sunt minime de energie, NU predicții.

Utilizare:  .venv/bin/python -B tu3/matrice_init.py [--address 127.0.0.1] [--port 8649] [--out-dir jurnal]
Cod de ieșire 0 dacă toate 3 modurile sunt READY și integritatea este OK, altfel 1.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
for _p in (str(HERE), str(QL)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine as E  # noqa: E402
import inlocuiri_tu3 as INL  # noqa: E402  (TU3-L649 §5.1: înlocuirea sigilată inlocuiri_tu3/v1)
import motor_joker as MJ  # noqa: E402
import motor_n as M  # noqa: E402
import parser_multi as PM  # noqa: E402

SEAL_VS = HERE / "SIGILIU_TU3_VS.json"
LIVE_PTR = PM.LIVE / "CURRENT_LIVE.json"
MODES = (("649", "🌌 Mode: Loto 6/49"), ("540", "🌀 Mode: Loto 5/40"), ("joker", "🃏 Mode: Joker"))
RULES = {"649": "extragere 6 din 1..49 · variantă 6 din 1..49",
         "540": "extragere 6 din 1..40 · variantă 5 din 1..40",
         "joker": "extragere 5 din 1..45 + Joker 1..20 · variantă 5+1"}


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _mode_spec(game: str) -> dict:
    """Specificația fixă a fiecărui mod (PROTOCOL_TU3_VS §2; produsele din PROTOCOL_TU3_UI §3)."""
    if game == "649":
        return {"source": "frozen", "product": "engine.run_full", "protocol": QL / "PREINREGISTRARE_QL649.md",
                "seal": QL / "SIGILIU_PROTOCOL.json", "config_digest": E.PROTOCOL.digest(), "power": None,
                "power_expected": None}
    if game == "540":
        return {"source": "live", "product": "motor_n.run_full_540", "protocol": M.PROTOCOL_FILE, "seal": M.SEAL_FILE,
                "config_digest": M.PROTOCOL_540.digest(), "power": M.POWER_FILE, "power_expected": "E40_PASS"}
    return {"source": "live", "product": "motor_joker.run_full_joker", "protocol": MJ.PROTOCOL_FILE,
            "seal": MJ.SEAL_FILE, "config_digest": MJ.PROTOCOL_JOKER.digest(), "power": MJ.POWER_FILE,
            "power_expected": "EJ_PASS"}


def _power_row(path: Path | None, expected: str | None) -> tuple[str, str | None, bool]:
    """(verdict afișat, motiv de eroare sau None, potrivirea hash-urilor de cod)."""
    if path is None:
        return "n/a (QL649: protocol propriu, fără poartă de putere TU3)", None, True
    if not path.exists():
        return "ABSENT", "fișier de putere absent", False
    d = json.loads(path.read_text())
    verdict = d.get("verdict")
    codes = d.get("code_sha256", {})
    match = bool(codes) and all((HERE / rel).exists() and sha(HERE / rel) == h for rel, h in codes.items())
    err = None
    if verdict != expected:
        err = f"verdict {verdict} ≠ {expected}"
    elif not match:
        err = "hash de cod ≠ fișierul de putere"
    return str(verdict), err, match


def mode_row(game: str, label: str, device=None) -> dict:
    s = _mode_spec(game)
    row = {"mode": game, "label": label, "rule": RULES[game], "source_kind": s["source"], "product": s["product"],
           "config_digest": s["config_digest"][:12], "status": "READY", "errors": []}
    try:
        seal = json.loads(Path(s["seal"]).read_text())
        p_sha = sha(s["protocol"])
        row["protocol"] = Path(s["protocol"]).name
        row["protocol_sha256"] = p_sha[:12]
        row["protocol_seal_ok"] = p_sha == seal.get("sha256")
        if not row["protocol_seal_ok"]:
            row["errors"].append("sha protocol ≠ sigiliul lui")
    except (OSError, ValueError) as exc:
        row["protocol_seal_ok"] = False
        row["errors"].append(f"protocol/sigiliu: {type(exc).__name__}")
    verdict, err, match = _power_row(s["power"], s["power_expected"])
    row["power_verdict"] = verdict
    row["power_code_hashes_match"] = match
    if err:
        row["errors"].append(err)
    try:
        ds = PM.build_game_dataset(game, s["source"], device=device)
        sm = ds.summary()
        row.update(source_sha256=sm["source_sha256"][:12], n_draws=sm["n_draws"], n_steps=sm["n_steps"],
                   first_date=sm["first_date"], last_date=sm["last_date"],
                   excluded=int(sum(sm["removed_by_reason"].values())), device=sm["device"])
        if game == "649":
            row["frozen_sha_verified"] = ds.source_sha256 == PM.FROZEN_649_SHA256
            if not row["frozen_sha_verified"]:
                row["errors"].append("sursa înghețată 6/49 ≠ FROZEN_649_SHA256")
        else:
            row["live_chain_verified"] = True
            row["live_version_dir"] = ds.provenance.get("version_dir")
        del ds
    except PM.IntegrityError as exc:
        row["errors"].append(f"IntegrityError: {exc}")
    except Exception as exc:  # noqa: BLE001 — orice eșec de încărcare apare în matrice, fără a opri serverul
        row["errors"].append(f"{type(exc).__name__}: {exc}")
    if row["errors"]:
        row["status"] = "ERROR"
    return row


def integrity() -> dict:
    try:
        seal = json.loads(SEAL_VS.read_text())
    except (OSError, ValueError) as exc:
        return {"status": "DRIFT", "errors": [f"sigiliu TU3-VS: {type(exc).__name__}"], "checked": 0}
    res = INL.resolve(seal.get("frozen_hashes", {}), QL)   # TU3-L649 §5.1: identic SAU înlocuit sigilat
    drift = res["drift"]
    return {"status": "OK" if not drift else "DRIFT", "drift": drift, "checked": len(seal.get("frozen_hashes", {})),
            "replaced": res["replaced"], "records": res["records"], "seal_sha256": sha(SEAL_VS)[:12]}


def live_info() -> dict:
    try:
        ptr = json.loads(LIVE_PTR.read_text())
    except (OSError, ValueError) as exc:
        return {"error": f"{type(exc).__name__}"}
    vroot = PM.LIVE / "versiuni"
    size = sum(f.stat().st_size for f in vroot.rglob("*") if f.is_file()) if vroot.exists() else 0
    n_ver = sum(1 for d in vroot.iterdir() if d.is_dir()) if vroot.exists() else 0
    return {"updated_utc": ptr.get("updated_utc"), "version_dir": ptr.get("version_dir"),
            "manifest_sha256": str(ptr.get("manifest_sha256", ""))[:12], "versions": n_ver,
            "versions_bytes": size}


def system_info(address: str, port: int) -> dict:
    cuda = torch.cuda.is_available()
    info = {"utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "python": platform.python_version(), "torch": torch.__version__, "cuda": cuda,
            "address": address, "port": int(port), "positive_claims_allowed": False}
    try:
        info["streamlit"] = importlib.metadata.version("streamlit")
    except importlib.metadata.PackageNotFoundError:
        info["streamlit"] = None
    if cuda:
        free, total = torch.cuda.mem_get_info()
        cap = torch.cuda.get_device_capability(0)
        info.update(device=torch.cuda.get_device_name(0), capability=f"{cap[0]}.{cap[1]}",
                    vram_total_mib=round(total / 2 ** 20), vram_free_mib=round(free / 2 ** 20))
    else:
        info["device"] = "CPU (fallback)"
    return info


def build_matrix(address: str = "127.0.0.1", port: int = 8649, device=None) -> dict:
    m = {"matrix": "TU3-VS init", "system": system_info(address, port),
         "modes": [mode_row(g, lab, device) for g, lab in MODES], "live": live_info(), "integrity": integrity(),
         "note": "Fără motoare rulate și fără variante. Variantele produsului = minime de energie, NU predicții. "
                 "Calcul clasic. positive_claims_allowed=false.", "positive_claims_allowed": False}
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    m["ok"] = all(r["status"] == "READY" for r in m["modes"]) and m["integrity"]["status"] == "OK"
    return m


def render(m: dict) -> str:
    s, L = m["system"], []
    bar = "═" * 118
    L.append(bar)
    L.append(" QUANTUM LAB 649 · TRI-UNIVERSE CONVERGENCE v3.0 — MATRICEA DE INIȚIALIZARE (TU3-VS)")
    L.append(bar)
    dev = f"{s.get('device')} (cc {s.get('capability')}, VRAM {s.get('vram_free_mib')}/{s.get('vram_total_mib')} MiB liberă)" \
        if s["cuda"] else s["device"]
    L.append(f" UTC {s['utc']} · Python {s['python']} · torch {s['torch']} · Streamlit {s['streamlit']}")
    L.append(f" CUDA {s['cuda']} · {dev}")
    L.append(f" server http://{s['address']}:{s['port']} · positive_claims_allowed=false")
    L.append("─" * 118)
    hdr = f" {'mod':<22}{'sursă':<8}{'sha':<14}{'extr.':>6}{'pași':>6}  {'interval':<23}{'excl':>5}  {'disp.':<7}" \
          f"{'protocol':<14}{'putere':<11}{'stare'}"
    L.append(hdr)
    for r in m["modes"]:
        interval = f"{r.get('first_date')}…{r.get('last_date')}" if r.get("first_date") else "—"
        pw = r["power_verdict"] if not r["power_verdict"].startswith("n/a") else "n/a"
        proto = f"{r.get('protocol_sha256', '—')}{'✓' if r.get('protocol_seal_ok') else '✗'}"
        L.append(f" {r['label']:<22}{r['source_kind']:<8}{r.get('source_sha256', '—'):<14}{r.get('n_draws', 0):>6}"
                 f"{r.get('n_steps', 0):>6}  {interval:<23}{r.get('excluded', 0):>5}  {r.get('device', '—'):<7}"
                 f"{proto:<14}{pw:<11}{r['status']}")
        L.append(f"   regulă: {r['rule']} · produs {r['product']} · config {r['config_digest']}…")
        for e in r["errors"]:
            L.append(f"   ✗ {e}")
    L.append("─" * 118)
    lv = m["live"]
    if "error" in lv:
        L.append(f" LIVE: pointer ilizibil ({lv['error']})")
    else:
        L.append(f" LIVE: actualizat {lv['updated_utc']} · {lv['version_dir']} · manifest {lv['manifest_sha256']}… · "
                 f"versiuni/ {lv['versions']} directoare, {lv['versions_bytes'] / 2 ** 20:.1f} MiB (descriptiv)")
    it = m["integrity"]
    L.append(f" Integritate (sigiliu TU3-VS {it.get('seal_sha256', '—')}…): {it['status']} pe {it['checked']} fișiere"
             + (f" ({len(it['replaced'])} înlocuite sigilat: {', '.join(it['replaced'])} · "
                f"{', '.join(it.get('records', []))})" if it.get("replaced") else "")
             + (f" · DRIFT: {', '.join(it.get('drift', []))}" if it.get("drift") else ""))
    L.append(f" Verdict matrice: {'TOATE 3 MODURILE READY' if m['ok'] else 'ATENȚIE — vezi erorile'} · "
             "fără motoare rulate, fără variante (variantele = minime de energie, NU predicții)")
    L.append(bar)
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TU3-VS — matricea de inițializare (fără motoare, fără variante)")
    ap.add_argument("--address", default=os.environ.get("QL649_ADDRESS", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("QL649_PORT", "8649")))
    ap.add_argument("--out-dir", default=str(QL / "jurnal"))
    ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args(argv)
    m = build_matrix(a.address, a.port, "cpu" if a.cpu else None)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dst = out / f"MATRICE_INIT_{utc_stamp()}.json"
    with open(dst, "x", encoding="utf-8") as f:
        f.write(json.dumps(m, indent=2, ensure_ascii=False) + "\n")
    print(render(m))
    print(f" json: {dst}")
    return 0 if m["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
