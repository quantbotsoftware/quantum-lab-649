#!/usr/bin/env python3
"""DL v2 (S33_01 opțiunea A) — protocol tu4/PROTOCOL_QUANTUM_S34.md, sigilat înainte de cod.

Reutilizează verificatorul DL original NEMODIFICAT pe o vedere în care numai cele 6 registre prospective vii sunt
înlocuite de preimaginile lor păstrate, apoi verifică faptul că registrele vii sunt extensii append-only ale
preimaginilor. Read-only față de proiect; scrie numai rezultatul în tu4/rezultate/S34/. positive_claims_allowed=false.
"""
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(".")
DL_DIR = ROOT / "documentatie/continuitate_20261025T165403Z"
OUT = ROOT / "next_candidate/quantum_lab_649/tu4/rezultate/S34"
PRE_PREFIX = "next_candidate/predictie_numere/vechime_conditionata_20261023/external_state_at_entry/"
GAMES = ("649", "540", "joker")
LIVE = [f"next_candidate/quantum_limit/prospectiv/{g}/{f}" for g in GAMES
        for f in ("registru.json", "REZULTATE_PROSPECTIVE.md")]
sys.path.insert(0, str(ROOT / "next_candidate"))
import quantum_limit.prospectiv as PROSPECTIV  # noqa: E402  (_digest importat nemodificat; AMENDAMENT_S34_01)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_original():
    spec = importlib.util.spec_from_file_location("dl_original", DL_DIR / "verifica_publicarea.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build_overlay(view: Path, base: Path, overrides: dict):
    """Vedere cu legături simbolice spre `base`; căile din `overrides` (relative) indică spre alte fișiere."""
    dirs = set()
    for rel in overrides:
        parts = Path(rel).parts
        for i in range(1, len(parts)):
            dirs.add(Path(*parts[:i]))

    def fill(rel_dir: Path):
        src, dst = base / rel_dir, view / rel_dir
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            rel = rel_dir / child.name
            if rel in dirs:
                fill(rel)
            elif str(rel) in overrides:
                (dst / child.name).symlink_to(overrides[str(rel)])
            else:
                (dst / child.name).symlink_to(child.resolve() if child.is_symlink() else child,
                                              target_is_directory=child.is_dir())

    fill(Path("."))


def check_registry(old: dict, new: dict, game_dir: Path):
    probs = []
    for k in ("schema", "protocol", "game"):
        if old.get(k) != new.get(k):
            probs.append(f"{k} diferit")
    oe, ne = old.get("entries", []), new.get("entries", [])
    if len(ne) < len(oe):
        probs.append("intrări eliminate")
    for i, o in enumerate(oe):
        if i >= len(ne):
            break
        n = ne[i]
        if o.get("target_draw") != n.get("target_draw"):
            probs.append(f"intrarea {i}: target_draw diferit")
        for k, v in o.items():
            if v is not None and n.get(k) != v:
                probs.append(f"intrarea {i} ({o.get('target_draw')}): cheia {k} modificată")
    new_seals = []
    for n in ne[len(oe):]:
        p = game_dir / str(n.get("target_draw")) / str(n.get("seal"))
        ok = False
        if p.is_file():  # AMENDAMENT_S34_01: seal_sha256 = câmpul sha256 canonic din sigiliu
            rec = json.loads(p.read_text())
            ok = rec.get("sha256") == n.get("seal_sha256") == PROSPECTIV._digest(rec)
        new_seals.append({"target_draw": n.get("target_draw"), "seal": n.get("seal"), "ok": ok})
        if not ok:
            probs.append(f"sigiliu invalid pentru intrarea nouă {n.get('target_draw')}")
    return probs, {"old_entries": len(oe), "new_entries": len(ne), "new_seals": new_seals}


def check_report(old: str, new: str):
    probs = []
    ol, nl = old.splitlines(), new.splitlines()
    derived = "Numărul Joker ("  # AMENDAMENT_S34_01: linie cumulativă derivată, tratată ca titlul
    keep = [x for i, x in enumerate(ol) if i not in (0, 2) and not x.startswith(derived)]
    j = 0
    for line in nl:
        if j < len(keep) and line == keep[j]:
            j += 1
    if j != len(keep):
        probs.append(f"linie veche lipsă sau reordonată: {keep[j][:80]!r}")
    rk = re.compile(r"\((\d+)/52")
    ko, kn = rk.search(ol[0] if ol else ""), rk.search(nl[0] if nl else "")
    if not (ko and kn) or int(kn.group(1)) < int(ko.group(1)):
        probs.append("numărul de extrageri punctate a scăzut sau lipsește")
    rj = re.compile(r"^" + re.escape(derived) + r"(\d+) ")
    jo = [int(m.group(1)) for x in ol if (m := rj.match(x))]
    jn = [int(m.group(1)) for x in nl if (m := rj.match(x))]
    if jo and (len(jn) != len(jo) or any(b < a for a, b in zip(jo, jn))):
        probs.append("linia derivată Joker lipsește sau contorul a scăzut")
    return probs, {"old_k": int(ko.group(1)) if ko else None, "new_k": int(kn.group(1)) if kn else None,
                   "old_lines_kept": j, "old_lines_required": len(keep)}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((DL_DIR / "manifest.json").read_text())
    imm = manifest["immutable_checks"]
    checks, info = [], {}

    def ck(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    # D1
    for rel in LIVE:
        pre = ROOT / (PRE_PREFIX + rel)
        ck(f"D1_preimagine {rel}", pre.is_file() and sha(pre) == imm.get(rel) == imm.get(PRE_PREFIX + rel),
           {"pre_sha": sha(pre) if pre.is_file() else None, "manifest": imm.get(rel)})
        ck(f"informativ_viu_diferit {rel}", True, {"live_sha": sha(ROOT / rel), "changed": sha(ROOT / rel) != imm.get(rel)})

    original = load_original()
    # informativ: verificatorul original pe rădăcina vie
    try:
        res = original.verify(ROOT, ROOT)
        info["original_pe_radacina_vie"] = {"status": res.get("status")}
    except AssertionError as e:
        info["original_pe_radacina_vie"] = {"status": "FAIL", "assertion": str(e)}
    except Exception as e:  # noqa: BLE001
        info["original_pe_radacina_vie"] = {"status": "ERROR", "error": repr(e)}

    # D2
    with tempfile.TemporaryDirectory(prefix="dl_v2_view_") as tmp:
        view = Path(tmp) / "LOTO_RO"
        build_overlay(view, ROOT, {rel: str(ROOT / (PRE_PREFIX + rel)) for rel in LIVE})
        try:
            res = original.verify(view, view)
            ck("D2_original_nemodificat_pe_vedere", res.get("status") == "PASS",
               {k: res.get(k) for k in ("status", "DL", "immutable_files", "installed_files", "previous_context")})
        except Exception as e:  # noqa: BLE001
            ck("D2_original_nemodificat_pe_vedere", False, {"error": repr(e), "tb": traceback.format_exc()[-1500:]})

    # D3, D4
    for g in GAMES:
        live_dir = ROOT / f"next_candidate/quantum_limit/prospectiv/{g}"
        pre_dir = ROOT / (PRE_PREFIX + f"next_candidate/quantum_limit/prospectiv/{g}")
        probs, det = check_registry(json.loads((pre_dir / "registru.json").read_text()),
                                    json.loads((live_dir / "registru.json").read_text()), live_dir)
        ck(f"D3_registru_append_only {g}", not probs, {"probleme": probs, **det})
        probs, det = check_report((pre_dir / "REZULTATE_PROSPECTIVE.md").read_text(),
                                  (live_dir / "REZULTATE_PROSPECTIVE.md").read_text())
        ck(f"D4_raport_append_only {g}", not probs, {"probleme": probs, **det})

    n_pass = sum(c["ok"] for c in checks)
    verdict = "PASS" if n_pass == len(checks) else "FAIL"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT / f"DL_V2_VERIFICARE_{stamp}.json"
    while out.exists():
        time.sleep(1)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = OUT / f"DL_V2_VERIFICARE_{stamp}.json"
    doc = {"criteriu": "DL_V2", "verdict": verdict, "n_checks": len(checks), "n_pass": n_pass, "run_utc": stamp,
           "protocol": "TU4-S34", "script_sha256": sha(Path(__file__)), "checks": checks, **info,
           "positive_claims_allowed": False}
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out.chmod(0o444)
    print(json.dumps({k: doc[k] for k in ("criteriu", "verdict", "n_checks", "n_pass")}, ensure_ascii=False))
    for c in checks:
        if not c["ok"]:
            print("FAIL", c["name"], json.dumps(c["detail"], ensure_ascii=False)[:600])
    print("ORIGINAL_PE_VIU", json.dumps(info.get("original_pe_radacina_vie"), ensure_ascii=False))
    print(out, sha(out))
    print(f"DL_RC_V2={0 if verdict == 'PASS' else 1}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
