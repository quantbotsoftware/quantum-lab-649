"""TU3-DD — deduplicarea versiunilor arhivei LIVE: compactare FĂRĂ PIERDERI, verificabilă octet cu octet.

Protocol: `tu3/PROTOCOL_TU3_DD.md` (sigilat înainte de cod în `tu3/SIGILIU_TU3_DD.json`).

Fiecare ciclu al colectorului publică `tu3/date/live/versiuni/<sha12>/` complet (~3.3 MB), deși extragerile sunt de
obicei identice: baza se reconstruiește la fiecare rulare, iar fiecare rând JSONL poartă `provenance` (run_id, sha bază).
Acest script, rulat DUPĂ `arhiva_live.py` (drop-in `ExecStopPost` separat) sau manual:

- nu atinge versiunea curentă și pe cea precedentă (PROTEJATE; dacă le găsește compacte, le rehidratează byte-exact);
- grupează versiunile după cheia de conținut (rândurile fără `provenance`); reprezentantul clasei = cea mai veche;
- compactează celelalte: `MANIFEST_LIVE.json` neschimbat; `decision.json`/`colectare.json` → gzip determinist;
  JSONL → gzip la reprezentant, iar la restul o referință (`ref`) la reprezentant + `provenance` din manifest;
- compactează NUMAI dacă materializarea formei compacte dă exact octeții originali (altfel lasă versiunea completă);
- înlocuire atomică (`.dedup_tmp_*` → `.dedup_old_*`) cu recuperare la pornire; același lacăt ca `arhiva_live.py`.

Nimic nu se pierde: `--reconstruieste <sha12> --out <dir>` scrie fișierele originale byte-exact.
Nu atinge `CURRENT_LIVE.json`, `ISTORIC_LIVE.jsonl`, colectorul, prognoza sau gardul ei. Doar biblioteca standard.
Stocare, nu model: nu rulează niciun motor, nu produce variante; positive_claims_allowed=false.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE_DEFAULT = HERE / "date" / "live"
GAMES = ("649", "540", "joker")
MANIFEST = "MANIFEST_LIVE.json"
DEDUP = "DEDUP_LIVE.json"
SCHEMA = "tu3-dedup-live/1"
TMP_PREFIX, OLD_PREFIX, BAD_PREFIX = ".dedup_tmp_", ".dedup_old_", ".dedup_bad_"


class DedupError(Exception):
    """Orice abatere de integritate; versiunea în cauză nu se atinge."""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_b(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def log(msg: str) -> None:
    print(f"[tu3-dedup-live {now()}] {msg}", flush=True)


def dumps(rec: dict) -> str:
    """Serializarea EXACTĂ din `arhiva_live.py`."""
    return json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"


def gz(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9, mtime=0)


def jsonl_name(game: str) -> str:
    return f"extrageri_{game}.jsonl"


def is_jsonl(name: str) -> bool:
    return name in {jsonl_name(g) for g in GAMES}


# ── citire / materializare ───────────────────────────────────────────────────────────────────────────────────────────
def manifest_bytes(v: Path) -> bytes:
    p = v / MANIFEST
    if not p.is_file():
        raise DedupError(f"{v.name}: {MANIFEST} absent")
    return p.read_bytes()


def manifest(v: Path) -> dict:
    return json.loads(manifest_bytes(v))


def is_compact(v: Path) -> bool:
    return (v / DEDUP).is_file()


def list_versions(vers: Path) -> list[Path]:
    """Versiunile publicate (cu manifest), ordonate după created_utc din manifest, apoi după nume."""
    out = []
    if not vers.is_dir():
        return out
    for d in vers.iterdir():
        if d.is_dir() and not d.name.startswith(".") and (d / MANIFEST).is_file():
            out.append(d)
    def key(d: Path):
        try:
            return (str(manifest(d).get("created_utc", "")), d.name)
        except (ValueError, OSError):
            return ("", d.name)
    return sorted(out, key=key)


def reprovenance(data: bytes, man: dict) -> bytes:
    prov = {"database_sha256": man["database_sha256"], "run_id": man["run_id"]}
    out = []
    for line in data.decode("utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            rec["provenance"] = prov
            out.append(dumps(rec))
    return "".join(out).encode("utf-8")


def materialize(vers: Path, v: Path, cache: dict | None = None, depth: int = 0) -> dict[str, bytes]:
    """Octeții ORIGINALI ai tuturor fișierelor versiunii, în afară de manifest (care nu se schimbă niciodată)."""
    cache = {} if cache is None else cache
    ck = (str(v), depth)
    if ck in cache:
        return cache[ck]
    if not is_compact(v):
        files = {p.name: p.read_bytes() for p in sorted(v.iterdir()) if p.is_file() and p.name != MANIFEST}
        cache[ck] = files
        return files
    meta = json.loads((v / DEDUP).read_bytes())
    if meta.get("schema") != SCHEMA:
        raise DedupError(f"{v.name}: schema {meta.get('schema')!r} necunoscută")
    man_b = manifest_bytes(v)
    if sha_b(man_b) != meta.get("manifest_sha256"):
        raise DedupError(f"{v.name}: sha256({MANIFEST}) ≠ DEDUP_LIVE.json")
    man = json.loads(man_b)
    files = {}
    for name, ent in sorted(meta["files"].items()):
        if Path(name).name != name or name in (MANIFEST, DEDUP):
            raise DedupError(f"{v.name}: nume de fișier interzis {name!r}")
        method = ent.get("method")
        if method == "gzip":
            stored = ent["stored"]
            if Path(stored).name != stored or stored != name + ".gz":
                raise DedupError(f"{v.name}: fișier stocat neașteptat {stored!r}")
            b = (v / stored).read_bytes()
            if sha_b(b) != ent["stored_sha256"]:
                raise DedupError(f"{v.name}: sha256({stored}) ≠ DEDUP_LIVE.json")
            data = gzip.decompress(b)
        elif method == "ref":
            if depth > 0:
                raise DedupError(f"{v.name}: referință în lanț (adâncime > 1) interzisă")
            if not is_jsonl(name):
                raise DedupError(f"{v.name}: `ref` permis numai pentru JSONL, nu {name!r}")
            ref = ent["ref"]
            if Path(ref).name != ref or ref.startswith("."):
                raise DedupError(f"{v.name}: referință invalidă {ref!r}")
            rv = vers / ref
            if sha_b(manifest_bytes(rv)) != ent["ref_manifest_sha256"]:
                raise DedupError(f"{v.name}: manifestul reprezentantului {ref} ≠ DEDUP_LIVE.json")
            rfiles = materialize(vers, rv, cache, depth + 1)
            if name not in rfiles:
                raise DedupError(f"{v.name}: {name} absent la reprezentantul {ref}")
            data = reprovenance(rfiles[name], man)
        else:
            raise DedupError(f"{v.name}: metodă necunoscută {method!r} pentru {name}")
        if sha_b(data) != ent["sha256"] or len(data) != ent["bytes"]:
            raise DedupError(f"{v.name}: {name} materializat ≠ sha256/bytes originale")
        files[name] = data
    cache[ck] = files
    return files


def check_against_manifest(v: Path, files: dict[str, bytes]) -> list[str]:
    problems = []
    try:
        man = manifest(v)
        for g, gm in man["games"].items():
            name = gm["file"]
            if name not in files:
                problems.append(f"{v.name}: {name} lipsește")
            elif sha_b(files[name]) != gm["sha256"]:
                problems.append(f"{v.name}: sha256({name}) ≠ manifest")
    except (ValueError, KeyError, TypeError, OSError, DedupError) as exc:
        problems.append(f"{v.name}: manifest invalid: {type(exc).__name__}: {exc}")
    return problems


def verify_version(vers: Path, v: Path, cache: dict | None = None) -> list[str]:
    try:
        files = materialize(vers, v, cache)
    except (DedupError, OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile, EOFError) as exc:
        return [f"{v.name}: {type(exc).__name__}: {exc}"]
    problems = check_against_manifest(v, files)
    if is_compact(v) and not problems:
        meta = json.loads((v / DEDUP).read_bytes())
        if content_key(files) != meta.get("content_key"):
            problems.append(f"{v.name}: cheia de conținut ≠ DEDUP_LIVE.json")
    return problems


def content_key(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for g in GAMES:
        h.update(f"#{g}\n".encode())
        for line in files.get(jsonl_name(g), b"").decode("utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                rec.pop("provenance", None)
                h.update(dumps(rec).encode("utf-8"))
    return h.hexdigest()


# ── plan ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
def protected_names(live: Path) -> set[str] | None:
    ptr_path = live / "CURRENT_LIVE.json"
    if not ptr_path.is_file():
        return None
    ptr = json.loads(ptr_path.read_text())
    names = {Path(ptr["version_dir"]).name}
    if ptr.get("previous"):
        names.add(Path(ptr["previous"]).name)
    return names


def plan(live: Path, cache: dict | None = None) -> dict:
    vers = live / "versiuni"
    cache = {} if cache is None else cache
    prot = protected_names(live)
    if prot is None:
        return {"protected": None, "actions": [], "skipped": [{"why": "CURRENT_LIVE.json absent; nimic de făcut"}]}
    actions, skipped, keys, reps = [], [], {}, {}
    for v in list_versions(vers):
        try:
            if is_compact(v):
                k = json.loads((v / DEDUP).read_bytes())["content_key"]
            else:
                k = content_key(materialize(vers, v, cache))
        except (DedupError, OSError, ValueError, KeyError) as exc:
            skipped.append({"version": v.name, "why": f"{type(exc).__name__}: {exc}"})
            continue
        keys[v.name] = k
        reps.setdefault(k, v.name)  # cea mai veche din clasă (list_versions e ordonat)
    for v in list_versions(vers):
        if v.name not in keys:
            continue
        if v.name in prot:
            if is_compact(v):
                actions.append({"op": "rehydrate", "version": v.name})
            continue
        if is_compact(v):
            continue
        rep = reps[keys[v.name]]
        if rep == v.name:
            actions.append({"op": "gzip", "version": v.name, "content_key": keys[v.name]})
        else:
            rv = vers / rep
            if is_compact(rv) and any(e.get("method") == "ref" for e in
                                      json.loads((rv / DEDUP).read_bytes())["files"].values()):
                skipped.append({"version": v.name, "why": f"reprezentantul {rep} este el însuși `ref` (inconsistent)"})
                continue
            actions.append({"op": "ref", "version": v.name, "ref": rep, "content_key": keys[v.name]})
    return {"protected": sorted(prot), "actions": actions, "skipped": skipped,
            "classes": len(reps), "versions": len(keys)}


# ── construire / înlocuire ───────────────────────────────────────────────────────────────────────────────────────────
def compact_payload(vers: Path, v: Path, action: dict, cache: dict) -> dict[str, bytes]:
    """Fișierele formei compacte (inclusiv manifestul neschimbat și DEDUP_LIVE.json), în memorie."""
    if is_compact(v):
        raise DedupError(f"{v.name}: deja compactă")
    original = materialize(vers, v, cache)
    problems = check_against_manifest(v, original)
    if problems:
        raise DedupError("; ".join(problems))
    man_b = manifest_bytes(v)
    payload: dict[str, bytes] = {MANIFEST: man_b}
    meta = {"schema": SCHEMA, "version": v.name, "manifest_sha256": sha_b(man_b),
            "content_key": action["content_key"], "compacted_utc": now(),
            "protocol": "TU3-DD (tu3/PROTOCOL_TU3_DD.md)", "positive_claims_allowed": False, "files": {}}
    if action["op"] == "ref":
        rv = vers / action["ref"]
        rp = verify_version(vers, rv, cache)
        if rp:
            raise DedupError(f"reprezentantul {action['ref']} nu se verifică: {rp}")
        ref_man_sha = sha_b(manifest_bytes(rv))
    for name, data in sorted(original.items()):
        if name in (DEDUP,) or name.endswith(".gz") or (name + ".gz") in original:
            raise DedupError(f"{v.name}: fișier neașteptat {name!r}")
        ent = {"sha256": sha_b(data), "bytes": len(data)}
        if action["op"] == "ref" and is_jsonl(name):
            ent.update(method="ref", ref=action["ref"], ref_manifest_sha256=ref_man_sha)
        else:
            b = gz(data)
            payload[name + ".gz"] = b
            ent.update(method="gzip", stored=name + ".gz", stored_sha256=sha_b(b))
        meta["files"][name] = ent
    payload[DEDUP] = (json.dumps(meta, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    return payload


def write_dir(vers: Path, name: str, payload: dict[str, bytes]) -> Path:
    tmp = vers / f"{TMP_PREFIX}{name}_{os.getpid()}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        for fname, b in payload.items():
            p = tmp / fname
            with open(p, "wb") as f:
                f.write(b)
                f.flush()
                os.fsync(f.fileno())
            p.chmod(0o444)
        tmp.chmod(0o755)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return tmp


def swap(vers: Path, v: Path, tmp: Path) -> None:
    old = vers / f"{OLD_PREFIX}{v.name}"
    if old.exists():
        raise DedupError(f"{old.name} există deja (recuperare necesară)")
    os.rename(v, old)
    os.rename(tmp, v)
    shutil.rmtree(old)


def dir_bytes(d: Path) -> int:
    return sum(p.stat().st_size for p in d.iterdir() if p.is_file())


def apply_action(vers: Path, action: dict, cache: dict, dry: bool) -> dict:
    v = vers / action["version"]
    before = dir_bytes(v)
    if action["op"] == "rehydrate":
        files = materialize(vers, v, cache)
        problems = check_against_manifest(v, files)
        if problems:
            raise DedupError("; ".join(problems))
        payload = {MANIFEST: manifest_bytes(v), **files}
    else:
        payload = compact_payload(vers, v, action, cache)
    after = sum(len(b) for b in payload.values())
    rec = dict(action, bytes_before=before, bytes_after=after)
    if dry:
        return rec
    original = materialize(vers, v, cache)
    tmp = write_dir(vers, v.name, payload)
    try:
        check = materialize(vers, tmp, {})  # poarta de siguranță: octeții originali, exact
        if set(check) != set(original) or any(check[k] != original[k] for k in original):
            raise DedupError(f"{v.name}: forma nouă NU reproduce exact octeții originali; versiunea rămâne neatinsă")
        if check_against_manifest(tmp, check):
            raise DedupError(f"{v.name}: forma nouă nu se verifică față de manifest")
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    swap(vers, v, tmp)
    cache.clear()
    return rec


def recover(vers: Path) -> list[dict]:
    events = []
    if not vers.is_dir():
        return events
    for old in sorted(vers.glob(f"{OLD_PREFIX}*")):
        name = old.name[len(OLD_PREFIX):]
        target = vers / name
        if not target.exists():
            os.rename(old, target)
            events.append({"op": "recover_restore", "version": name})
        elif not verify_version(vers, target):
            shutil.rmtree(old)
            events.append({"op": "recover_drop_old", "version": name})
        else:
            bad = vers / f"{BAD_PREFIX}{name}_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            os.rename(target, bad)
            os.rename(old, target)
            events.append({"op": "recover_restore_bad_new", "version": name, "moved_to": bad.name})
    for tmp in sorted(vers.glob(f"{TMP_PREFIX}*")):
        shutil.rmtree(tmp, ignore_errors=True)
        events.append({"op": "recover_drop_tmp", "dir": tmp.name})
    return events


def tree_bytes(vers: Path) -> int:
    return sum(p.stat().st_size for p in vers.rglob("*") if p.is_file()) if vers.is_dir() else 0


def run(live: Path, dry: bool = False) -> dict:
    """O trecere completă (apelantul ține lacătul). Erorile pe o versiune nu opresc celelalte."""
    vers = live / "versiuni"
    report = {"utc": now(), "dry_run": dry, "bytes_before": tree_bytes(vers), "recovery": [], "done": [],
              "errors": [], "positive_claims_allowed": False}
    if not dry:
        report["recovery"] = recover(vers)
    cache: dict = {}
    p = plan(live, cache)
    report.update(protected=p["protected"], skipped=p["skipped"], classes=p.get("classes"),
                  versions=p.get("versions"))
    for action in p["actions"]:
        try:
            report["done"].append(apply_action(vers, action, cache, dry))
        except (DedupError, OSError, ValueError, KeyError, gzip.BadGzipFile, EOFError) as exc:
            report["errors"].append({"version": action["version"], "op": action["op"],
                                     "error": f"{type(exc).__name__}: {exc}"})
            cache.clear()
    if dry:
        report["bytes_after_estimate"] = report["bytes_before"] - sum(
            d["bytes_before"] - d["bytes_after"] for d in report["done"])
    else:
        report["bytes_after"] = tree_bytes(vers)
        if report["done"] or report["recovery"] or report["errors"]:
            with open(live / "DEDUP_LIVE.jsonl", "a", encoding="utf-8") as f:
                for d in report["done"]:
                    f.write(json.dumps({"utc": report["utc"], **d}, ensure_ascii=False) + "\n")
                for e in report["recovery"] + report["errors"]:
                    f.write(json.dumps({"utc": report["utc"], **e}, ensure_ascii=False) + "\n")
    return report


def verify_all(live: Path) -> dict:
    vers = live / "versiuni"
    cache: dict = {}
    res = {}
    for v in list_versions(vers):
        res[v.name] = {"compact": is_compact(v), "problems": verify_version(vers, v, cache)}
    leftovers = [d.name for d in vers.iterdir() if d.name.startswith((TMP_PREFIX, OLD_PREFIX))] if vers.is_dir() else []
    return {"versions": res, "leftovers": leftovers,
            "ok": all(not r["problems"] for r in res.values()) and not leftovers}


def reconstruct(live: Path, name: str, out: Path) -> dict:
    vers = live / "versiuni"
    v = vers / name
    if Path(name).name != name or not (v / MANIFEST).is_file():
        raise DedupError(f"versiune necunoscută: {name!r}")
    out = out.resolve()
    if out.is_relative_to(live.resolve()):
        raise DedupError("--out trebuie să fie în afara arhivei LIVE")
    files = materialize(vers, v)
    problems = check_against_manifest(v, files)
    if problems:
        raise DedupError("; ".join(problems))
    out.mkdir(parents=True, exist_ok=True)
    allf = {MANIFEST: manifest_bytes(v), **files}
    for fname in allf:
        if (out / fname).exists():
            raise DedupError(f"{out / fname} există; refuz de suprascriere")
    for fname, b in allf.items():
        (out / fname).write_bytes(b)
    return {fname: sha_b(b) for fname, b in allf.items()}


def _summary(r: dict) -> str:
    n = {op: sum(1 for d in r["done"] if d["op"] == op) for op in ("gzip", "ref", "rehydrate")}
    after = r.get("bytes_after", r.get("bytes_after_estimate", 0))
    pre = "SIMULARE: " if r["dry_run"] else ""
    if not any(n.values()) and not r["errors"] and not r["recovery"]:
        return f"{pre}nimic de compactat ({r.get('versions')} versiuni, {r.get('classes')} clase de conținut)"
    return (f"{pre}compactate {n['gzip'] + n['ref']} (gzip {n['gzip']}, ref {n['ref']}), rehidratate {n['rehydrate']}, "
            f"recuperări {len(r['recovery'])}, erori {len(r['errors'])}; versiuni/ "
            f"{r['bytes_before'] / 2 ** 20:.1f} MiB → {after / 2 ** 20:.1f} MiB")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--automat", action="store_true", help="trecere reală (systemd ExecStopPost); ieșire mereu 0")
    g.add_argument("--simulare", action="store_true", help="numai raportează; nu scrie nimic")
    g.add_argument("--verifica", action="store_true", help="materializează și verifică toate versiunile; ieșire 0/1")
    g.add_argument("--reconstruieste", metavar="SHA12", help="scrie fișierele originale ale versiunii în --out")
    ap.add_argument("--out", type=Path, help="director țintă pentru --reconstruieste (în afara arhivei)")
    ap.add_argument("--live-root", type=Path, default=LIVE_DEFAULT)
    ap.add_argument("--json", action="store_true", help="tipărește raportul complet JSON")
    a = ap.parse_args(argv)
    live = a.live_root
    if a.verifica:
        res = verify_all(live)
        bad = {k: v["problems"] for k, v in res["versions"].items() if v["problems"]}
        if a.json:
            print(json.dumps(res, indent=1, ensure_ascii=False))
        log(f"verificare: {len(res['versions'])} versiuni "
            f"({sum(v['compact'] for v in res['versions'].values())} compacte), "
            f"probleme {len(bad)}, resturi {res['leftovers']} → {'OK' if res['ok'] else 'EȘEC'}")
        for k, v in bad.items():
            log(f"  {k}: {v}")
        return 0 if res["ok"] else 1
    if a.reconstruieste:
        if a.out is None:
            ap.error("--reconstruieste cere --out")
        hashes = reconstruct(live, a.reconstruieste, a.out)
        print(json.dumps(hashes, indent=1))
        return 0
    if a.simulare:
        r = run(live, dry=True)
        if a.json:
            print(json.dumps(r, indent=1, ensure_ascii=False))
        log(_summary(r))
        return 0
    live.mkdir(parents=True, exist_ok=True)
    try:
        with open(live / ".lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            r = run(live, dry=False)
        if a.json:
            print(json.dumps(r, indent=1, ensure_ascii=False))
        log(_summary(r))
        for e in r["errors"]:
            log(f"  eroare {e['version']} ({e['op']}): {e['error']}")
    except Exception as exc:  # în modul automat nu stricăm serviciul colectorului
        log(f"EROARE {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
