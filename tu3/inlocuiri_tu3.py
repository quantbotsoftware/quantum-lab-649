"""TU3 — înlocuirea sigilată `inlocuiri_tu3/v1` (PROTOCOL_TU3_L649 §4; sigilat în SIGILIU_TU3_L649.json ÎNAINTE de cod).

Un fișier înghețat într-un sigiliu vechi (VS, DD, LN, …) e acceptat ca „înlocuit sigilat” numai dacă sha-ul lui curent
se obține din sha-ul sigilat printr-un lanț de înregistrări `tu3/inlocuiri/INLOCUIRE_<ETICHETĂ>_<UTC>Z.json` VALIDE:
fiecare înregistrare (0444) trimite la sigiliul unui protocol scris ÎNAINTE de cod (`code_files_present: []`), care
fixează lista închisă `replaceable` a fișierelor care pot fi înlocuite și sha-ul lor de dinainte. Sigiliile vechi nu se
rescriu; matricea și testele spun explicit ce fișiere sunt înlocuite și prin ce înregistrare.

Numai biblioteca standard. Sigilii locale, fără atestare externă. `positive_claims_allowed=false`.

Utilizare:
  python3 -B tu3/inlocuiri_tu3.py --verifica
  python3 -B tu3/inlocuiri_tu3.py --simuleaza tu3/SIGILIU_TU3_L649.json L649
  python3 -B tu3/inlocuiri_tu3.py --inregistreaza tu3/SIGILIU_TU3_L649.json L649
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

MECHANISM = "inlocuiri_tu3/v1"
HERE = Path(__file__).resolve().parent
QL = HERE.parent
REC_DIR_REL = Path("tu3") / "inlocuiri"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REC_KEYS = ("record", "mechanism", "seal", "seal_sha256", "protocol", "protocol_sha256", "written_utc",
            "replacements", "positive_claims_allowed")
OLD_SEALS = ("tu3/SIGILIU_TU3_VS.json", "tu3/SIGILIU_TU3_DD.json", "tu3/SIGILIU_TU3_LN.json",
             "tu3/SIGILIU_TU3_L649.json")


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha_bytes(Path(p).read_bytes())


def _not_writable(p: Path) -> bool:
    return (os.stat(p).st_mode & 0o222) == 0


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# ---------------------------------------------------------------------------
# Validarea înregistrărilor (§4.3, R1–R8)
# ---------------------------------------------------------------------------
def _validate_one(path: Path, root: Path) -> tuple[dict | None, list[str]]:
    """R1–R7 pentru o singură înregistrare. Întoarce (înregistrarea, erori)."""
    errs: list[str] = []
    try:
        rec = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        return None, [f"R1 JSON ilizibil: {type(exc).__name__}"]
    if not isinstance(rec, dict) or any(k not in rec for k in REC_KEYS):
        return None, ["R1 câmpuri lipsă"]
    if rec["mechanism"] != MECHANISM or rec["positive_claims_allowed"] is not False:
        errs.append("R1 mecanism/positive_claims_allowed")
    if not _not_writable(path):
        errs.append("R2 înregistrarea are bit de scriere")
    seal_p = root / str(rec["seal"])
    try:
        seal_b = seal_p.read_bytes()
        seal = json.loads(seal_b)
    except (OSError, ValueError) as exc:
        return rec, errs + [f"R3 sigiliu ilizibil: {type(exc).__name__}"]
    if sha_bytes(seal_b) != rec["seal_sha256"]:
        errs.append("R3 sha sigiliu ≠ seal_sha256")
    if not _not_writable(seal_p):
        errs.append("R3 sigiliul are bit de scriere")
    proto_p = root / str(rec["protocol"])
    try:
        proto_sha = sha_file(proto_p)
    except OSError:
        proto_sha = None
    if not (proto_sha and seal.get("sha256") == proto_sha == rec["protocol_sha256"]
            and seal.get("file") == proto_p.name):
        errs.append("R4 protocol ≠ sigiliu ≠ înregistrare")
    if seal.get("code_files_present") != [] or seal.get("results_present") is not False \
            or seal.get("replacement_mechanism") != MECHANISM:
        errs.append("R5 sigiliul nu e un sigiliu de protocol pre-cod v1")
    if not (isinstance(rec["written_utc"], str) and isinstance(seal.get("sealed_utc"), str)
            and rec["written_utc"] > seal["sealed_utc"]):
        errs.append("R6 written_utc nu e ulterior sigilării")
    repl = rec["replacements"]
    allowed = seal.get("replaceable") or {}
    if not isinstance(repl, dict) or not repl:
        errs.append("R7 replacements gol")
    else:
        for rel, ft in repl.items():
            if rel not in allowed:
                errs.append(f"R7 {rel} nu e în replaceable")
            elif not (isinstance(ft, dict) and HEX64.match(str(ft.get("from", ""))) and HEX64.match(str(ft.get("to", "")))
                      and ft["from"] != ft["to"]):
                errs.append(f"R7 {rel}: from/to invalide")
    rec["_seal_replaceable"] = allowed
    return rec, errs


def load_records(root: Path = QL) -> tuple[list[dict], list[dict]]:
    """Toate înregistrările din tu3/inlocuiri/, în ordinea numelor; (valide, invalide). R8 aplicat în ordine."""
    root = Path(root)
    d = root / REC_DIR_REL
    valid: list[dict] = []
    invalid: list[dict] = []
    if not d.is_dir():
        return valid, invalid
    for p in sorted(d.glob("INLOCUIRE_*.json")):
        rec, errs = _validate_one(p, root)
        if rec is not None and not errs:
            for rel, ft in rec["replacements"].items():
                tips = {rec["_seal_replaceable"][rel]} | {v["replacements"][rel]["to"] for v in valid
                                                         if v["seal"] == rec["seal"] and rel in v["replacements"]}
                if ft["from"] not in tips:
                    errs.append(f"R8 {rel}: from nu e nici sha-ul din replaceable, nici capătul unui lanț anterior")
        if rec is None or errs:
            invalid.append({"record": p.name, "errors": errs})
        else:
            rec["_name"] = p.name
            valid.append(rec)
    return valid, invalid


# ---------------------------------------------------------------------------
# Rezolvarea (§4.4)
# ---------------------------------------------------------------------------
def resolve_one(rel: str, sealed: str, root: Path, valid: list[dict]) -> tuple[str, list[str]]:
    """('identic' | 'inlocuit' | 'drift', lanțul de înregistrări)."""
    p = Path(root) / rel
    if not p.is_file():
        return "drift", []
    cur = sha_file(p)
    if cur == sealed:
        return "identic", []
    h, chain, seen = sealed, [], {sealed}
    while True:
        nxt = next((r for r in valid if rel in r["replacements"] and r["replacements"][rel]["from"] == h
                    and r["replacements"][rel]["to"] not in seen), None)
        if nxt is None:
            return "drift", []
        h = nxt["replacements"][rel]["to"]
        seen.add(h)
        chain.append(nxt["_name"])
        if h == cur:
            return "inlocuit", chain


def resolve(frozen_hashes: dict, root: Path = QL) -> dict:
    root = Path(root)
    valid, invalid = load_records(root)
    out = {"drift": [], "replaced": [], "identical": 0, "records": [], "invalid_records": invalid}
    used: set[str] = set()
    for rel, h in frozen_hashes.items():
        st, chain = resolve_one(rel, h, root, valid)
        if st == "identic":
            out["identical"] += 1
        elif st == "inlocuit":
            out["replaced"].append(rel)
            used.update(chain)
        else:
            out["drift"].append(rel)
    out["records"] = sorted(used)
    return out


# ---------------------------------------------------------------------------
# Scrierea înregistrării (§4.2) — după teste
# ---------------------------------------------------------------------------
def plan_record(seal_rel: str, label: str, root: Path = QL) -> dict:
    """Calculează înregistrarea; ridică ValueError la orice refuz (§4.4)."""
    root = Path(root)
    seal_p = root / seal_rel
    seal = json.loads(seal_p.read_bytes())
    if seal.get("replacement_mechanism") != MECHANISM or seal.get("code_files_present") != [] \
            or seal.get("results_present") is not False or not _not_writable(seal_p):
        raise ValueError("sigiliul nu e un sigiliu de protocol pre-cod v1 (0444)")
    proto_p = seal_p.parent / seal["file"]
    if sha_file(proto_p) != seal["sha256"]:
        raise ValueError("sha protocol ≠ sigiliu")
    bad = [k for k, h in seal.get("frozen_hashes", {}).items() if not (root / k).is_file() or sha_file(root / k) != h]
    bad += [k for k, h in seal.get("frozen_external", {}).items() if not Path(k).is_file() or sha_file(Path(k)) != h]
    if bad:
        raise ValueError(f"DRIFT în fișierele protejate ale sigiliului: {bad}")
    for k, h in (seal.get("baseline_copies_must_equal") or {}).items():
        if not (root / k).is_file() or sha_file(root / k) != h:
            raise ValueError(f"copia de referință {k} are sha greșit")
    valid, _ = load_records(root)
    repl = {}
    for rel, before in seal["replaceable"].items():
        tip = before
        for r in valid:
            if r["seal"] == seal_rel and rel in r["replacements"] and r["replacements"][rel]["from"] == tip:
                tip = r["replacements"][rel]["to"]
        cur = sha_file(root / rel)
        if cur != tip:
            repl[rel] = {"from": tip, "to": cur}
    if not repl:
        raise ValueError("nicio schimbare față de replaceable / lanțul existent")
    now = _utc_now()
    return {"record": f"INLOCUIRE_{label}", "mechanism": MECHANISM, "seal": seal_rel,
            "seal_sha256": sha_file(seal_p), "protocol": str(proto_p.relative_to(root)),
            "protocol_sha256": seal["sha256"], "written_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "replacements": repl,
            "note": "Înlocuire sigilată (PROTOCOL_TU3_L649 §4). Fișierele vechi rămân în sigiliile lor; această "
                    "înregistrare fixează sha-urile noi. positive_claims_allowed=false.",
            "positive_claims_allowed": False}


def write_record(seal_rel: str, label: str, root: Path = QL) -> Path:
    rec = plan_record(seal_rel, label, root)
    d = Path(root) / REC_DIR_REL
    d.mkdir(parents=True, exist_ok=True)
    stamp = rec["written_utc"].replace("-", "").replace(":", "")
    dst = d / f"INLOCUIRE_{label}_{stamp}.json"
    with open(dst, "x", encoding="utf-8") as f:
        f.write(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
    os.chmod(dst, 0o444)
    valid, invalid = load_records(root)
    if dst.name not in {r["_name"] for r in valid}:
        raise RuntimeError(f"înregistrarea scrisă nu trece validarea: {invalid}")
    return dst


def verify_all(root: Path = QL) -> dict:
    root = Path(root)
    rep = {}
    for s in OLD_SEALS:
        p = root / s
        if p.is_file():
            seal = json.loads(p.read_bytes())
            r = resolve(seal.get("frozen_hashes", {}), root)
            rep[s] = {k: r[k] for k in ("drift", "replaced", "identical", "records")}
    valid, invalid = load_records(root)
    return {"seals": rep, "valid_records": [r["_name"] for r in valid], "invalid_records": invalid,
            "ok": all(not v["drift"] for v in rep.values())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TU3 — înlocuirea sigilată inlocuiri_tu3/v1")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--verifica", action="store_true")
    g.add_argument("--simuleaza", nargs=2, metavar=("SIGILIU", "ETICHETA"))
    g.add_argument("--inregistreaza", nargs=2, metavar=("SIGILIU", "ETICHETA"))
    a = ap.parse_args(argv)
    try:
        if a.verifica:
            rep = verify_all()
            print(json.dumps(rep, indent=2, ensure_ascii=False))
            return 0 if rep["ok"] else 1
        if a.simuleaza:
            print(json.dumps(plan_record(*a.simuleaza), indent=2, ensure_ascii=False))
            return 0
        dst = write_record(*a.inregistreaza)
        print(dst, sha_file(dst))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"REFUZ: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
