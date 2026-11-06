#!/usr/bin/env python3
"""Verificator SEPARAT TU4-EM, amendamentul TU4-EM-V01 (tu4/AMENDAMENT_TU4_EM_V01.md, sigilat ÎNAINTE de acest cod).

Remediază incidentul TU4-EM-01: arhiva citată de o emisie se identifică prin AMPRENTA DE CONȚINUT (sha256 al octeților
exacți, înregistrat în emisie, în MANIFEST_LIVE.json și în DEDUP_LIVE.json), nu prin cale. Versiunile compactate de
TU3-DD se reconstruiesc INDEPENDENT (stdlib; fără import din tu3/dedup_live.py). V0, V1, V3–V9 = cele din
`tu4/verifica_em.py` (sigilat, NEMODIFICAT, încărcat prin cale după verificarea sha-ului; funcțiile de recalcul refolosite
literal). Numai stdlib + NumPy: fără torch, fără emițător, fără ip_core. positive_claims_allowed=false.

    /usr/bin/python3 -B tu4/verifica_em_v01.py                   # lanțul real → tu4/rezultate/EM/VERIFICARE_EM_V01_<UTC>.json
    /usr/bin/python3 -B tu4/verifica_em_v01.py --radacina DIR --test --ssd DIR   # rădăcină de test (fără fișier scris)
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import numpy as np

TU4 = Path(__file__).resolve().parent
QL = TU4.parent
ORIG_VERIFIER = TU4 / "verifica_em.py"
ORIG_VERIFIER_SHA = "1bada90e6e852fed2569cef12caa6b53ca38c98809b09551fe2f6b962426dc52"
AMEND_DOC = TU4 / "AMENDAMENT_TU4_EM_V01.md"
AMEND_DOC_SHA = "f2e55d46ac15cbe35a646c6f5d6eafe01a0cb9ded819599f0a2f0debceeafa81"
AMEND_SEAL = TU4 / "SIGILIU_AMENDAMENT_TU4_EM_V01.json"
AMEND_SEAL_SHA = "9e05c4a207853f52c2cd59bb9d046e4382ed9967389006966813cb9b5674355b"
MANIFEST, DEDUP, SCHEMA = "MANIFEST_LIVE.json", "DEDUP_LIVE.json", "tu3-dedup-live/1"
JSONL = {f"extrageri_{g}.jsonl" for g in ("649", "540", "joker")}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def shaf(p) -> str:
    return sha(Path(p).read_bytes())


def load_original():
    """`tu4/verifica_em.py` sigilat, ca bibliotecă; refuz dacă sha-ul diferă."""
    if shaf(ORIG_VERIFIER) != ORIG_VERIFIER_SHA:
        raise RuntimeError("tu4/verifica_em.py ≠ sha-ul sigilat 1bada90e…")
    spec = importlib.util.spec_from_file_location("verifica_em_sigilat", ORIG_VERIFIER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VE = load_original()


# ------------------------------------------------ reconstrucția independentă a versiunilor compactate (§3.2)
class ArchiveError(Exception):
    """Orice abatere de la regula V2′; verificarea respectivă devine FAIL."""


def _simple(name: str) -> bool:
    return bool(name) and Path(name).name == name and not name.startswith(".")


def _dedup_meta(vd: Path) -> dict | None:
    p = vd / DEDUP
    if not p.is_file():
        return None
    meta = json.loads(p.read_bytes())
    if meta.get("schema") != SCHEMA:
        raise ArchiveError(f"{vd.name}: schema {meta.get('schema')!r}")
    if sha((vd / MANIFEST).read_bytes()) != meta.get("manifest_sha256"):
        raise ArchiveError(f"{vd.name}: sha256({MANIFEST}) ≠ {DEDUP}")
    return meta


def _stored_gzip(vd: Path, name: str, ent: dict) -> bytes:
    stored = ent.get("stored")
    if stored != name + ".gz" or not _simple(stored):
        raise ArchiveError(f"{vd.name}: fișier stocat neașteptat {stored!r}")
    b = (vd / stored).read_bytes()
    if sha(b) != ent.get("stored_sha256"):
        raise ArchiveError(f"{vd.name}: sha256({stored}) ≠ stored_sha256")
    return gzip.decompress(b)


def _provenance(data: bytes, man: dict) -> bytes:
    prov = {"database_sha256": man["database_sha256"], "run_id": man["run_id"]}
    out = []
    for line in data.decode("utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            rec["provenance"] = prov
            out.append(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    return "".join(out).encode("utf-8")


def _leaf_bytes(vd: Path, name: str) -> tuple[bytes, str]:
    """Octeții unui fișier la un reprezentant (adâncime 1: numai raw sau gzip, niciodată ref)."""
    meta = _dedup_meta(vd)
    if meta is None:
        p = vd / name
        if not p.is_file():
            raise ArchiveError(f"{vd.name}: {name} absent")
        return p.read_bytes(), "raw"
    ent = meta.get("files", {}).get(name)
    if not isinstance(ent, dict):
        raise ArchiveError(f"{vd.name}: {name} absent din {DEDUP}")
    if ent.get("method") != "gzip":
        raise ArchiveError(f"{vd.name}: reprezentantul are metoda {ent.get('method')!r} (adâncime > 1 interzisă)")
    data = _stored_gzip(vd, name, ent)
    if sha(data) != ent.get("sha256") or len(data) != ent.get("bytes"):
        raise ArchiveError(f"{vd.name}: {name} decomprimat ≠ sha256/bytes")
    return data, "gzip"


def read_version_file(vers: Path, vd: Path, name: str) -> tuple[bytes, str]:
    """(octeții originali, rezoluția) ai fișierului `name` din versiunea `vd` (brută sau compactă)."""
    if not _simple(name) or name in (MANIFEST, DEDUP):
        raise ArchiveError(f"nume interzis {name!r}")
    if not (vd / MANIFEST).is_file():
        raise ArchiveError(f"{vd.name}: {MANIFEST} absent")
    meta = _dedup_meta(vd)
    if meta is None:
        p = vd / name
        if not p.is_file():
            raise ArchiveError(f"{vd.name}: {name} absent (versiune necompactă)")
        return p.read_bytes(), "raw"
    ent = meta.get("files", {}).get(name)
    if not isinstance(ent, dict):
        raise ArchiveError(f"{vd.name}: {name} absent din {DEDUP}")
    method = ent.get("method")
    if method == "gzip":
        data, res = _stored_gzip(vd, name, ent), "gzip"
    elif method == "ref":
        if name not in JSONL:
            raise ArchiveError(f"{vd.name}: `ref` permis numai pentru JSONL")
        ref = ent.get("ref")
        if not isinstance(ref, str) or not _simple(ref):
            raise ArchiveError(f"{vd.name}: referință invalidă {ref!r}")
        rv = vers / ref
        if not (rv / MANIFEST).is_file() or sha((rv / MANIFEST).read_bytes()) != ent.get("ref_manifest_sha256"):
            raise ArchiveError(f"{vd.name}: manifestul reprezentantului {ref} ≠ ref_manifest_sha256")
        base, _ = _leaf_bytes(rv, name)
        data, res = _provenance(base, json.loads((vd / MANIFEST).read_bytes())), f"ref:{ref}"
    else:
        raise ArchiveError(f"{vd.name}: metodă necunoscută {method!r}")
    if sha(data) != ent.get("sha256") or len(data) != ent.get("bytes"):
        raise ArchiveError(f"{vd.name}: {name} reconstruit ≠ sha256/bytes din {DEDUP}")
    return data, res


def fingerprint(root: Path, game: str, arch: dict) -> tuple[bool, str]:
    """V2_fingerprint: emisie → manifest → intrarea de compactare, fără a citi octeți de date."""
    try:
        vd = root / "tu3" / "date" / "live" / arch["version_dir"]
        name = Path(arch["file"]).name
        if Path(arch["file"]).parent != Path("tu3/date/live") / arch["version_dir"]:
            return False, "archive.file nu e în version_dir"
        mb = (vd / MANIFEST).read_bytes()
        man = json.loads(mb)
        gm = man["games"][game]
        ok = sha(mb) == arch["manifest_sha256"] and gm["file"] == name and gm["sha256"] == arch["sha256"]
        meta = _dedup_meta(vd)
        if meta is not None:
            ent = meta["files"].get(name) or {}
            ok &= meta["manifest_sha256"] == arch["manifest_sha256"] and ent.get("sha256") == arch["sha256"]
        return bool(ok), f"{'compact' if meta is not None else 'brut'} {arch['sha256'][:12]}"
    except (OSError, ValueError, KeyError, TypeError, ArchiveError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def archive_bytes(root: Path, arch: dict) -> tuple[bytes | None, str]:
    vers = root / "tu3" / "date" / "live" / "versiuni"
    vd = root / "tu3" / "date" / "live" / arch["version_dir"]
    try:
        if vd.parent.resolve() != vers.resolve():
            raise ArchiveError("version_dir în afara versiuni/")
        data, res = read_version_file(vers, vd, Path(arch["file"]).name)
    except (OSError, ValueError, KeyError, TypeError, ArchiveError, EOFError, gzip.BadGzipFile) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if sha(data) != arch["sha256"]:
        return None, f"{res}: sha256 ≠ archive.sha256"
    return data, res


# ------------------------------------------------ verificarea (V0, V1, V3–V9 identice cu verifica_em.verify)
def verify(root: Path, ssd: Path | None, test: bool) -> dict:
    v = VE.V()
    TU4E = VE.TU4  # = TU4 (același director)
    # V1′ amendamentul
    v.add("V1_amendment_doc_sha", shaf(AMEND_DOC) == AMEND_DOC_SHA)
    v.add("V1_amendment_seal_sha", shaf(AMEND_SEAL) == AMEND_SEAL_SHA)
    aseal = json.loads(AMEND_SEAL.read_text())
    v.add("V1_amendment_consistent", aseal["sha256"] == AMEND_DOC_SHA and aseal["original_verifier_sha256"]
          == ORIG_VERIFIER_SHA == shaf(ORIG_VERIFIER) and aseal["code_files_present"] == []
          and aseal["positive_claims_allowed"] is False)
    # V1 sigiliile (identic)
    v.add("V1_protocol_seal_sha", shaf(TU4E / "SIGILIU_TU4_EM.json") == VE.SEAL_SHA)
    seal = json.loads((TU4E / "SIGILIU_TU4_EM.json").read_text())
    v.add("V1_protocol_sha", shaf(TU4E / "PROTOCOL_TU4_EM.md") == seal["document"]["sha256"])
    drift = [f for f, h in seal["frozen_hashes"].items() if shaf(QL / f) != h]
    v.add("V1_frozen_drift_empty", not drift, drift)
    v.add("V1_ip_core_frozen", shaf(TU4E / "ip_core.py") == VE.IP_CORE_SHA)
    cs_path = TU4E / "SIGILIU_TU4_EM_COD.json"
    cs = json.loads(cs_path.read_text()) if cs_path.exists() else None
    if cs:
        cd = [f for f, h in cs["files"].items() if shaf(QL / f) != h]
        v.add("V1_code_seal_drift_empty", not cd, cd)
    else:
        v.add("V1_code_seal_present", "UNKNOWN" if test else False, "sigiliul codului lipsește")
    trib = root / "tu4" / "tribunal"
    files = sorted((trib / "emisii").glob("*/*.json"))
    v.add("V0_emissions_present", len(files) > 0, len(files))
    lant_lines = (trib / "LANT.jsonl").read_bytes().splitlines() if (trib / "LANT.jsonl").exists() else []
    lant = [json.loads(x) for x in lant_lines]
    summary = []
    for game in VE.GAMES:
        n, k, b, ball = VE.GAMES[game]
        gfiles = sorted((trib / "emisii" / game).glob("*.json"))
        prev = shaf(TU4E / "SIGILIU_TU4_EM.json")
        for idx, f in enumerate(gfiles):
            data = f.read_bytes()
            em = json.loads(data)
            tag = f"{game}/{f.stem}"
            arch = em["archive"]
            # V2′ amprenta
            okf, detf = fingerprint(root, game, arch)
            v.add(f"V2_fingerprint_{tag}", okf, detf)
            # V2′ octeții prin amprentă + validarea V2 originală
            raw, res = archive_bytes(root, arch)
            ok2 = raw is not None
            c = np.zeros(n)
            cb = np.zeros(VE.NB)
            N = 0
            if ok2:
                rows = [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
                N = len(rows)
                for r in rows:
                    nums = r["numbers"]
                    ok2 &= len(nums) == k and len(set(nums)) == k and all(1 <= x <= n for x in nums)
                    c[np.array(nums) - 1] += 1
                    if ball:
                        ok2 &= isinstance(r["joker"], int) and 1 <= r["joker"] <= VE.NB
                        cb[r["joker"] - 1] += 1
                ok2 &= N == arch["records"] == em["warm_start"]["N"]
                ok2 &= [int(x) for x in c] == em["warm_start"]["counts"]
                if ball:
                    ok2 &= [int(x) for x in cb] == em["warm_start"]["ball_counts"]
            v.add(f"V2_archive_{tag}", bool(ok2), f"{arch['file']} [{res}]")
            # V3 recalcul (identic)
            errs = []
            for urn, cc, nn, kk, bb in ((("main", c, n, k, b),) + ((("ball", cb, VE.NB, 1, 1),) if ball else ())):
                if not ok2:
                    errs.append(f"{urn}: arhivă neverificată")
                    continue
                ref = VE.models(cc, N, nn, kk)
                for m in ("H1", "H3"):
                    blk = em["models"][m] if urn == "main" else em["models"][m]["ball"]
                    lw, lam, x2 = ref[m]
                    elw = np.array(blk["logw"])
                    if np.max(np.abs(elw - lw)) > 1e-12:
                        errs.append(f"{urn}.{m}.logw {np.max(np.abs(elw - lw)):.2e}")
                    if abs(blk["lambda"] - lam) > 1e-12 or abs(blk["X2"] - x2) > 1e-9 * max(1, x2):
                        errs.append(f"{urn}.{m}.lambda/X2")
                    if blk["bet_active"] != (lam > 0):
                        errs.append(f"{urn}.{m}.bet_active")
                    pi, D = VE.incl_D(elw, kk)
                    if abs(blk["D_nats"] - D) > 1e-10:
                        errs.append(f"{urn}.{m}.D {abs(blk['D_nats'] - D):.2e}")
                    if kk == 1:
                        q = np.exp(elw - elw.max()); q /= q.sum()
                        if np.max(np.abs(np.array(blk["q"]) - q)) > 1e-12 or blk["top_ball"] != VE.top(elw, 1)[0]:
                            errs.append(f"{urn}.{m}.q/top_ball")
                    else:
                        if np.max(np.abs(np.array(blk["pi"]) - pi)) > 1e-10 or abs(sum(blk["pi"]) - kk) > 1e-9:
                            errs.append(f"{urn}.{m}.pi")
                        if blk["top_ticket"] != VE.top(elw, bb):
                            errs.append(f"{urn}.{m}.ticket")
                    g = em["c64_mirror"]["per_model"][m][urn]
                    tol = 1e-5 + 1e-4 * float(np.max(np.abs(elw)))
                    if g["pass"] != (g["abs_dlambda"] <= 1e-4 and g["max_abs_dlogw"] <= tol) or abs(g["tol_logw"] - tol) > 1e-15:
                        errs.append(f"{urn}.{m}.c64_gate_inconsistent")
            v.add(f"V3_recompute_{tag}", not errs, errs)
            # V4 cronologia (identic)
            d = dt.date.fromisoformat(em["target_date"])
            draw = dt.datetime.combine(d, dt.time(18, 30), VE.TZ)
            cut = dt.datetime.combine(d, dt.time(16, 0), VE.TZ)
            ok4 = (d.weekday() in (3, 6) and VE.utc(em["draw_utc"]) == draw and VE.utc(em["cutoff_utc"]) == cut
                   and VE.utc(em["emitted_utc"]) < VE.utc(em["cutoff_utc"]) < VE.utc(em["draw_utc"])
                   and f.stem == em["target_date"] and em["game"] == game and em["test_mode"] == test)
            v.add(f"V4_chronology_{tag}", ok4, f"emitted {em['emitted_utc']} cutoff {em['cutoff_utc']}")
            ch = em["chain"]
            v.add(f"V5_chain_{tag}", ch["index"] == idx and ch["prev_sha256"] == prev, ch)
            prev = sha(data)
            v.add(f"V6_mode_{tag}", stat.S_IMODE(f.stat().st_mode) == 0o444)
            if cs:
                v.add(f"V8_code_{tag}", em["code"]["emite_sha256"] == cs["files"]["tu4/emite.py"]
                      and em["code"]["ip_core_sha256"] == VE.IP_CORE_SHA and em["code"]["protocol_seal_sha256"] == VE.SEAL_SHA)
            else:
                v.add(f"V8_code_{tag}", "UNKNOWN" if test else False, "fără sigiliu de cod")
            ok_flags = em["positive_claims_allowed"] is False and em["tribunal"]["M"] == 6 and em["tribunal"]["threshold"] == 600
            v.add(f"V3_flags_{tag}", ok_flags)
            if ssd is not None and ssd.exists():
                sf = ssd / "emisii" / game / f.name
                v.add(f"V7_ssd_copy_{tag}", sf.exists() and sf.read_bytes() == data)
            else:
                v.add(f"V7_ssd_copy_{tag}", "UNKNOWN", "SSD nemontat / neindicat")
            summary.append({"game": game, "target": em["target_date"], "sha256": sha(data), "archive_resolution": res,
                            "H1": em["models"]["H1"]["top_ticket"], "H3": em["models"]["H3"]["top_ticket"],
                            "balls": ({m: em["models"][m]["ball"]["top_ball"] for m in ("H1", "H3")} if ball else None),
                            "lambda": {m: em["models"][m]["lambda"] for m in ("H1", "H3")}})
    ok5 = len(lant) == len(files)
    p = shaf(TU4E / "SIGILIU_TU4_EM.json")
    for i, (rawl, rec) in enumerate(zip(lant_lines, lant)):
        fp = trib / rec["file"]
        ok5 &= rec["i"] == i and rec["prev_line_sha256"] == p and fp.exists() and shaf(fp) == rec["sha256"]
        p = sha(rawl)
    ok5 &= len({(r["game"], r["target_date"]) for r in lant}) == len(lant)
    v.add("V5_lant_global", ok5, f"{len(lant)} linii / {len(files)} emisii")
    for name in ("LANT.jsonl", "RULARI.jsonl"):
        fp = trib / name
        v.add(f"V6_mode_{name}", fp.exists() and stat.S_IMODE(fp.stat().st_mode) == 0o444)
    if ssd is not None and ssd.exists():
        j = ssd / "JURNAL_EMISII.jsonl"
        recs = [json.loads(x) for x in j.read_text(encoding="utf-8").splitlines() if x.strip()] if j.exists() else []
        shas = {r["sha256"] for r in recs}
        v.add("V7_ssd_journal", j.exists() and all(shaf(f) in shas for f in files) and len(recs) == len(shas)
              and j.read_bytes().endswith(b"\n") and b"\x00" not in j.read_bytes(), f"{len(recs)} înregistrări")
        sl = ssd / "LANT.jsonl"
        v.add("V7_ssd_lant", sl.exists() and sl.read_bytes() == (trib / "LANT.jsonl").read_bytes())
    else:
        v.add("V7_ssd_journal", "UNKNOWN", "SSD nemontat / neindicat")
    if test:
        v.add("V9_units", "UNKNOWN", "mod test")
    else:
        ud = Path.home() / ".config/systemd/user"
        ok9 = all((ud / u).exists() and shaf(ud / u) == shaf(TU4E / "systemd" / u) for u in VE.UNITS)
        if cs:
            ok9 &= all(cs["files"][f"tu4/systemd/{u}"] == shaf(ud / u) for u in VE.UNITS if (ud / u).exists())
        v.add("V9_units", ok9)
    st = [c["status"] for c in v.checks]
    hard_fail = any(s == "FAIL" for s in st)
    unknown_ok = all(c["status"] != "UNKNOWN" or c["check"].startswith(("V7", "V9", "V8", "V1_code")) for c in v.checks)
    verdict = "VERIFICARE_EM_PASS" if (not hard_fail and unknown_ok) else "VERIFICARE_EM_FAIL"
    return {"protocol": "TU4-EM", "amendment": "TU4-EM-V01", "verifier": "tu4/verifica_em_v01.py",
            "verifier_sha256": shaf(Path(__file__)), "base_verifier_sha256": ORIG_VERIFIER_SHA,
            "amendment_seal_sha256": AMEND_SEAL_SHA, "root": str(root), "test_mode": test,
            "verified_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_checks": len(st), "n_pass": st.count("PASS"), "n_fail": st.count("FAIL"), "n_unknown": st.count("UNKNOWN"),
            "verdict": verdict, "emissions": summary, "checks": v.checks, "positive_claims_allowed": False}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--radacina", type=Path, default=QL)
    ap.add_argument("--ssd", type=Path, default=None)
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args(argv)
    ssd = a.ssd
    if ssd is None and not a.test and os.path.ismount("./ssd_data"):
        ssd = Path("./ssd_data/QL649_TU4_EM")
    res = verify(a.radacina.resolve(), ssd, a.test)
    if not a.test:
        stamp = res["verified_utc"].replace("-", "").replace(":", "")
        out = TU4 / "rezultate" / "EM" / f"VERIFICARE_EM_V01_{stamp}.json"
        fd = os.open(out, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
        print(out)
    print(json.dumps({k: res[k] for k in ("verdict", "n_checks", "n_pass", "n_fail", "n_unknown")}))
    for c in res["checks"]:
        if c["status"] == "FAIL":
            print("FAIL", c["check"], c["detail"])
    return 0 if res["verdict"] == "VERIFICARE_EM_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
