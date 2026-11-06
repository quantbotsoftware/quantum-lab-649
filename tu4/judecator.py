#!/usr/bin/env python3
"""TU4-JU (S13): judecătorul e-proces — decontarea automată a emisiilor prospective H1/H3 (6 fluxuri).

Protocol: tu4/PROTOCOL_TU4_JU.md, sigiliu tu4/SIGILIU_TU4_JU.json (2026-10-27T21:57:49Z), scrise ÎNAINTE de acest cod.

    .venv/bin/python -B tu4/judecator.py [--ssd DIR | --fara-ssd] [--fara-gpu]
    (teste: --radacina-test DIR --acum 2026-10-29T20:00:00Z)

Judecătorul NU prezice și NU recalculează modelele: folosește numai ln ŵ din emisiile sigilate (lanțul append-only
tu4/tribunal/), pe care le deschide exclusiv pentru citire. Factorul e: ln e = Σ_{i∈S} ln ŵ_i − ln e_k(ŵ) + ln C(n,k)
(+ termenul bilei la Joker); autoritatea = CPU float64; oglinda = nucleu torch compilat fullgraph (GPU), importat leneș.
Calcul clasic. positive_claims_allowed=false.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import mmap
import os
import struct
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
QL = HERE.parent
EM_SEAL = HERE / "SIGILIU_TU4_EM.json"
EM_CODE_SEAL = HERE / "SIGILIU_TU4_EM_COD.json"
JU_PROTOCOL = HERE / "PROTOCOL_TU4_JU.md"
JU_SEAL = HERE / "SIGILIU_TU4_JU.json"
JU_CODE_SEAL = HERE / "SIGILIU_TU4_JU_COD.json"
EM_SEAL_SHA = "82459f48458ef2ee248784929ea2c4c18ae60469b0084e4a7345910a7b5c53c7"
JU_SEAL_SHA = "5dcc0a4252acf9d504b5bbc11e13816595638839628d53349fd9c08082533093"
IP_CORE_SHA = "ab3e1de93d8e5ae537a8c80599905aaa19cc103602f9b18f4b7f7f6f8a48c302"
TZ = ZoneInfo("Europe/Bucharest")
DRAW_T, CUTOFF_T = dt.time(18, 30), dt.time(16, 0)
WEEKDAYS = (3, 6)
GAMES = {"649": dict(n=49, k=6, ball=False), "540": dict(n=40, k=6, ball=False), "joker": dict(n=45, k=5, ball=True)}
GAME_IDX = {"649": 0, "540": 1, "joker": 2}
NB = 20
MODELS = ("H1", "H3")
STREAMS = tuple(f"{m}_{g}" for m in MODELS for g in GAMES)
LN_EXPLORE, LN_CONFIRM, LN_RETIRE = math.log(600.0), math.log(20.0), -10.0
GRACE = dt.timedelta(days=14)
GPU_GATE = 1e-9
COMPILE_MODE = "max-autotune-no-cudagraphs"
STATES = {"EXPLORARE": 0, "CONFIRMARE": 1, "CONFIRMAT": 2, "RETRAS": 3}
STATUS_CODE = {"DECONTAT": 0, "VOID": 1, "RESPINS": 2}
LABEL = "test științific în curs; nu este sfat de joc"
EXIT_OK, EXIT_REFUSED = 0, 3
MAGIC, HDR, ROW = b"QL649JU1", 512, 160
ROW_FMT = "<qqqq2d6d6d6b"          # 150 octeți + 10 octeți de completare = 160
CANON_KEYS = ("game", "draw_date", "draw_kind", "numbers", "joker")


# ---------------------------------------------------------------- utilitare
def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p) -> str:
    return sha_bytes(Path(p).read_bytes())


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_utc(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def fsync_dir(d: Path) -> None:
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_exclusive(path: Path, data: bytes) -> None:
    """Creare exclusivă (O_EXCL), 0444, fsync — o decontare existentă nu se suprascrie niciodată."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_dir(path.parent)


def append_line(path: Path, line: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        os.chmod(path, 0o644)
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
    try:
        os.write(fd, line.rstrip(b"\n") + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)
        os.chmod(path, 0o444)


def mmap_append(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        os.chmod(path, 0o644)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        old = os.fstat(fd).st_size
        os.ftruncate(fd, old + len(data))
        off = (old // mmap.ALLOCATIONGRANULARITY) * mmap.ALLOCATIONGRANULARITY
        with mmap.mmap(fd, old + len(data) - off, offset=off) as mm:
            mm[old - off:old - off + len(data)] = data
            mm.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
        os.chmod(path, 0o444)


def incident(root: Path, name: str, payload: dict) -> str | None:
    p = root / "tu4" / "incidente" / f"{name}.json"
    try:
        write_exclusive(p, (json.dumps(payload, indent=1, ensure_ascii=False, default=str) + "\n").encode())
        return str(p.relative_to(root))
    except FileExistsError:
        return None


class Integritate(Exception):
    pass


class ArhivaInvalida(Exception):
    pass


# ---------------------------------------------------------------- factorul e (autoritate CPU float64, protocol §1)
def log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def ln_e_block(logw: list, chosen: list, k: int, active: bool) -> float:
    """ln e = Σ_{i∈S} ln ŵ_i − ln e_k(ŵ) + ln C(n,k); exact 0.0 dacă blocul nu pariază (λ = 0)."""
    if not active:
        return 0.0
    n = len(logw)
    w = [math.exp(x) for x in logw]
    e = [1.0] + [0.0] * k
    for wi in w:
        for j in range(k, 0, -1):
            e[j] = e[j] + wi * e[j - 1]
    return math.fsum(logw[i - 1] for i in chosen) - math.log(e[k]) + log_comb(n, k)


# ---------------------------------------------------------------- nucleul torch compilat (oglindă + calibrare, §6)
_KERNELS: dict = {}
COMPILE_STATUS: dict = {}


def _kernel_fn(n: int, k: int):
    import torch
    lc = log_comb(n, k)

    def f(logw, x, active):
        w = torch.exp(logw)
        e = [torch.ones_like(w[:, 0])] + [torch.zeros_like(w[:, 0]) for _ in range(k)]
        for i in range(n):
            wi = w[:, i]
            for j in range(k, 0, -1):
                e[j] = e[j] + wi * e[j - 1]
        val = (x * logw).sum(1) - torch.log(e[k]) + lc
        return torch.where(active, val, torch.zeros_like(val))
    return f


def kernel(n: int, k: int, compiled: bool = True):
    key = (n, k, compiled)
    if key not in _KERNELS:
        import torch
        f = _kernel_fn(n, k)
        if compiled:
            try:
                _KERNELS[key] = torch.compile(f, mode=COMPILE_MODE, fullgraph=True, dynamic=False)
                COMPILE_STATUS[f"{n}_{k}"] = f"compiled:{COMPILE_MODE}:fullgraph"
            except Exception as exc:  # declarat (protocol §0)
                _KERNELS[key] = f
                COMPILE_STATUS[f"{n}_{k}"] = "eager_fallback:" + repr(exc)[:200]
        else:
            _KERNELS[key] = f
            COMPILE_STATUS.setdefault(f"{n}_{k}", "eager")
    return _KERNELS[key]


def ln_e_torch(n: int, k: int, logw, x, active, compiled: bool = True):
    """logw (B,n) float64, x (B,n) float64 {0,1}, active (B,) bool -> ln e (B,) pe dispozitivul intrărilor."""
    fn = kernel(n, k, compiled)
    try:
        return fn(logw, x, active)
    except Exception as exc:  # eșec la prima execuție a nucleului compilat ⇒ eager, declarat
        if not compiled:
            raise
        COMPILE_STATUS[f"{n}_{k}"] = "eager_fallback_runtime:" + repr(exc)[:200]
        _KERNELS[(n, k, True)] = kernel(n, k, False)
        return _KERNELS[(n, k, True)](logw, x, active)


def gpu_mirror(blocks: list) -> dict:
    """blocks: [(eticheta, logw, chosen, k, active, ln_e_cpu)] -> poarta |Δ| ≤ 1e-9."""
    t0 = time.perf_counter()
    try:
        import torch
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        out = {}
        for lab, logw, chosen, k, active, ref in blocks:
            n = len(logw)
            lw = torch.tensor([logw], dtype=torch.float64, device=dev)
            x = torch.zeros((1, n), dtype=torch.float64, device=dev)
            x[0, [i - 1 for i in chosen]] = 1.0
            act = torch.tensor([bool(active)], device=dev)
            v = float(ln_e_torch(n, k, lw, x, act)[0].cpu())
            out[lab] = {"ln_e_gpu": v, "abs_diff": abs(v - ref), "pass": abs(v - ref) <= GPU_GATE}
        return {"device": dev, "compile_status": dict(COMPILE_STATUS), "per_block": out,
                "pass": all(r["pass"] for r in out.values()), "seconds": round(time.perf_counter() - t0, 3)}
    except Exception as exc:
        return {"device": None, "error": repr(exc)[:300], "pass": False, "seconds": round(time.perf_counter() - t0, 3)}


# ---------------------------------------------------------------- mașina de stări (protocol §4)
def init_state() -> dict:
    return {"state": "EXPLORARE", "lnE": 0.0, "lnE_conf": 0.0, "conf_start_utc": None, "conf_start_date": None}


def advance(st: dict, status: str, ln_e: float, target_date: str, emitted_utc: str, decided_utc: str):
    st = dict(st)
    counted = False
    if st["state"] == "EXPLORARE":
        if status == "DECONTAT":
            st["lnE"] = st["lnE"] + ln_e
            counted = True
            if st["lnE"] >= LN_EXPLORE:
                st.update(state="CONFIRMARE", lnE_conf=0.0, conf_start_utc=decided_utc, conf_start_date=target_date)
            elif st["lnE"] < LN_RETIRE:
                st["state"] = "RETRAS"
    elif st["state"] == "CONFIRMARE":
        if (status == "DECONTAT" and target_date > st["conf_start_date"]
                and parse_utc(emitted_utc) > parse_utc(st["conf_start_utc"])):
            st["lnE_conf"] = st["lnE_conf"] + ln_e
            counted = True
            if st["lnE_conf"] >= LN_CONFIRM:
                st["state"] = "CONFIRMAT"
            elif st["lnE_conf"] < LN_RETIRE:
                st["state"] = "RETRAS"
    return st, counted


# ---------------------------------------------------------------- lanțul emisiilor (integritate, protocol §2 I1–I3)
def load_chain(trib: Path) -> tuple[list, bytes]:
    lant_p = trib / "LANT.jsonl"
    lant_b = lant_p.read_bytes() if lant_p.exists() else b""
    lines = lant_b.splitlines()
    prev = EM_SEAL_SHA
    seen, entries = set(), []
    per_game: dict = {g: [] for g in GAMES}
    for idx, ln in enumerate(lines):
        rec = json.loads(ln)
        if rec.get("i") != idx:
            raise Integritate(f"LANT: indice {rec.get('i')} ≠ {idx}")
        if rec.get("prev_line_sha256") != prev:
            raise Integritate(f"LANT: prev_line_sha256 rupt la linia {idx}")
        prev = sha_bytes(ln)
        key = (rec["game"], rec["target_date"])
        if key in seen:
            raise Integritate(f"LANT: emisie dublată {key}")
        seen.add(key)
        f = trib / rec["file"]
        b = f.read_bytes()
        if sha_bytes(b) != rec["sha256"]:
            raise Integritate(f"LANT: sha256 diferit pentru {rec['file']}")
        em = json.loads(b)
        if em.get("emitted_utc") != rec.get("emitted_utc") or em.get("game") != rec["game"] \
                or em.get("target_date") != rec["target_date"]:
            raise Integritate(f"LANT: metadate diferite pentru {rec['file']}")
        ent = {"lant_i": idx, "file": rec["file"], "sha256": rec["sha256"], "em": em, "game": rec["game"],
               "target_date": rec["target_date"]}
        per_game.setdefault(rec["game"], []).append(ent)
        entries.append(ent)
    for g, lst in per_game.items():
        pv = EM_SEAL_SHA
        for j, ent in enumerate(sorted(lst, key=lambda e: e["target_date"])):
            ch = ent["em"].get("chain", {})
            if ch.get("index") != j or ch.get("prev_sha256") != pv:
                raise Integritate(f"lanț per joc rupt: {g} {ent['target_date']}")
            pv = ent["sha256"]
        files = {str(p.relative_to(trib)) for p in (trib / "emisii" / g).glob("*.json")} if (trib / "emisii" / g).exists() else set()
        orphans = files - {e["file"] for e in lst}
        if orphans:
            raise Integritate(f"fișiere în emisii/ fără linie în LANT: {sorted(orphans)}")
    return entries, lant_b


def check_frozen_29(trib: Path, root: Path, test_mode: bool) -> None:
    if test_mode:
        return
    fz = json.loads(JU_SEAL.read_text())["frozen_hashes"]
    for g in GAMES:
        rel = f"tu4/tribunal/emisii/{g}/2026-10-29.json"
        if sha_file(root / rel) != fz[rel]:
            raise Integritate(f"emisia înghețată {rel} diferă de sigiliul JU")


def check_code(test_mode: bool) -> dict:
    code = {"judecator_sha256": sha_file(Path(__file__)), "ju_protocol_sha256": sha_file(JU_PROTOCOL),
            "ju_seal_sha256": sha_file(JU_SEAL)}
    if code["ju_seal_sha256"] != JU_SEAL_SHA:
        raise Integritate("sigiliul protocolului JU diferă")
    if json.loads(JU_SEAL.read_text())["document"]["sha256"] != code["ju_protocol_sha256"]:
        raise Integritate("protocolul JU diferă de cel sigilat")
    if sha_file(EM_SEAL) != EM_SEAL_SHA:
        raise Integritate("sigiliul EM diferă")
    if JU_CODE_SEAL.exists():
        cs = json.loads(JU_CODE_SEAL.read_text())
        code["ju_code_seal_sha256"] = sha_file(JU_CODE_SEAL)
        if cs["files"]["tu4/judecator.py"] != code["judecator_sha256"]:
            raise Integritate("judecator.py diferă de codul sigilat")
    elif not test_mode:
        raise Integritate("lipsește SIGILIU_TU4_JU_COD.json: decontarea reală nu este permisă")
    else:
        code["ju_code_seal_sha256"] = None
    return code


# ---------------------------------------------------------------- admisibilitatea (protocol §2 A1–A6)
def at_local(d: dt.date, t: dt.time) -> dt.datetime:
    return dt.datetime.combine(d, t, TZ).astimezone(dt.timezone.utc)


def _finite_list(v, n) -> bool:
    return (isinstance(v, list) and len(v) == n
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v))


def admissibility(em: dict, test_mode: bool) -> dict:
    g = GAMES.get(em.get("game"))
    res = {}
    try:
        e, c, d = parse_utc(em["emitted_utc"]), parse_utc(em["cutoff_utc"]), parse_utc(em["draw_utc"])
        res["A1_cronologie"] = e < c < d
        D = dt.date.fromisoformat(em["target_date"])
        res["A2_calendar"] = D.weekday() in WEEKDAYS and d == at_local(D, DRAW_T) and c == at_local(D, CUTOFF_T)
    except Exception:
        res["A1_cronologie"] = res["A2_calendar"] = False
    res["A3_metadate"] = (em.get("protocol") == "TU4-EM" and em.get("target_kind") == "regular"
                          and em.get("positive_claims_allowed") is False and em.get("test_mode") is bool(test_mode))
    cs = json.loads(EM_CODE_SEAL.read_text())
    code = em.get("code", {})
    res["A4_cod"] = (code.get("emite_sha256") == cs["files"]["tu4/emite.py"] and code.get("ip_core_sha256") == IP_CORE_SHA
                     and code.get("code_seal_sha256") == sha_file(EM_CODE_SEAL)
                     and code.get("protocol_seal_sha256") == EM_SEAL_SHA)
    res["A5_arhiva_anterioara"] = str(em.get("archive", {}).get("last_date", "9999")) < str(em.get("target_date", ""))
    ok6 = g is not None
    if ok6:
        for m in MODELS:
            blk = em.get("models", {}).get(m, {})
            ok6 = ok6 and _finite_list(blk.get("logw"), g["n"]) and isinstance(blk.get("bet_active"), bool)
            if g["ball"]:
                bb = blk.get("ball", {}) or {}
                ok6 = ok6 and _finite_list(bb.get("logw"), NB) and isinstance(bb.get("bet_active"), bool)
    res["A6_blocuri"] = bool(ok6)
    return res


# ---------------------------------------------------------------- arhiva LIVE (protocol §3)
def load_live(root: Path) -> dict:
    live = root / "tu3" / "date" / "live"
    cur_b = (live / "CURRENT_LIVE.json").read_bytes()
    cur = json.loads(cur_b)
    vdir = live / cur["version_dir"]
    man_b = (vdir / "MANIFEST_LIVE.json").read_bytes()
    man = json.loads(man_b)
    if man.get("database_sha256") != cur.get("database_sha256"):
        raise ArhivaInvalida("database_sha256 diferit între CURRENT_LIVE și manifest")
    out = {"meta": {"version_dir": cur["version_dir"], "database_sha256": cur["database_sha256"],
                    "current_live_sha256": sha_bytes(cur_b), "manifest_sha256": sha_bytes(man_b)}, "games": {}}
    for game, g in GAMES.items():
        gm, gc = man["games"][game], cur["games"][game]
        fb = (vdir / gm["file"]).read_bytes()
        fsha = sha_bytes(fb)
        if not (fsha == gm["sha256"] == gc["sha256"]):
            raise ArhivaInvalida(f"sha arhivă {game}")
        rows = [json.loads(x) for x in fb.decode("utf-8").splitlines() if x.strip()]
        if len(rows) != gm["records"] or len(rows) != gc["records"]:
            raise ArhivaInvalida(f"număr de înregistrări {game}")
        for r in rows:
            nums = r.get("numbers")
            if (not isinstance(nums, list) or len(nums) != g["k"] or len(set(nums)) != g["k"]
                    or not all(isinstance(x, int) and not isinstance(x, bool) and 1 <= x <= g["n"] for x in nums)):
                raise ArhivaInvalida(f"extragere invalidă {r.get('draw_key')}")
            if g["ball"]:
                j = r.get("joker")
                if not (isinstance(j, int) and not isinstance(j, bool) and 1 <= j <= NB):
                    raise ArhivaInvalida(f"bilă invalidă {r.get('draw_key')}")
        out["games"][game] = {"rows": rows, "file": f"tu3/date/live/{cur['version_dir']}/{gm['file']}", "sha256": fsha,
                              "records": len(rows)}
    return out


def canon(r: dict) -> dict:
    return {k: r.get(k) for k in CANON_KEYS}


def regular_records(live: dict, game: str, D: str) -> list:
    return [r for r in live["games"][game]["rows"] if r.get("draw_date") == D and r.get("draw_kind") == "regular"]


def decide(ent: dict, live: dict, now: dt.datetime, test_mode: bool) -> dict:
    """Întoarce {'pending': motiv} sau {'status', 'reason', 'record', 'adm'} (protocol §3)."""
    em, game, D = ent["em"], ent["game"], ent["target_date"]
    draw = parse_utc(em["draw_utc"])
    R = regular_records(live, game, D)
    if now < draw:
        return {"pending": "înainte de ora extragerii", "early_record": bool(R)}
    adm = admissibility(em, test_mode)
    if not all(adm.values()):
        return {"status": "RESPINS", "reason": "admisibilitate: " + ",".join(k for k, v in adm.items() if not v),
                "record": None, "adm": adm, "n_regular": None}
    if len(R) >= 2:
        return {"status": "VOID", "reason": f"ambiguu: {len(R)} înregistrări regulate în {D}", "record": None,
                "adm": adm, "n_regular": len(R)}
    if len(R) == 1 and R[0].get("has_source_disagreement") is not True:
        return {"status": "DECONTAT", "reason": "înregistrarea regulată unică", "record": R[0], "adm": adm,
                "n_regular": 1}
    if now >= draw + GRACE:
        why = "dezacord persistent între surse" if R else "extragere absentă"
        return {"status": "VOID", "reason": f"{why} după 14 zile", "record": None, "adm": adm, "n_regular": len(R)}
    return {"pending": "dezacord între surse (în așteptare)" if R else "extragerea nu este încă în arhiva LIVE"}


# ---------------------------------------------------------------- decontarea
def model_factors(em: dict, rec: dict | None) -> tuple[dict, list]:
    g = GAMES[em["game"]]
    out, blocks = {}, []
    for m in MODELS:
        blk = em["models"][m]
        act_main = bool(blk["bet_active"])
        act_ball = bool(blk["ball"]["bet_active"]) if g["ball"] else False
        if rec is None:
            out[m] = {"bet_active_main": act_main, "bet_active_ball": act_ball if g["ball"] else None,
                      "ln_e_main": 0.0, "ln_e_ball": 0.0 if g["ball"] else None, "ln_e": 0.0}
            continue
        lm = ln_e_block(blk["logw"], rec["numbers"], g["k"], act_main)
        blocks.append((f"{m}_main", blk["logw"], rec["numbers"], g["k"], act_main, lm))
        lb = None
        if g["ball"]:
            lb = ln_e_block(blk["ball"]["logw"], [rec["joker"]], 1, act_ball)
            blocks.append((f"{m}_ball", blk["ball"]["logw"], [rec["joker"]], 1, act_ball, lb))
        out[m] = {"bet_active_main": act_main, "bet_active_ball": act_ball if g["ball"] else None,
                  "ln_e_main": lm, "ln_e_ball": lb, "ln_e": lm + (lb if lb is not None else 0.0)}
    return out, blocks


def read_decontari(trib: Path) -> list:
    p = trib / "DECONTARI.jsonl"
    if not p.exists():
        return []
    out = []
    for ln in p.read_bytes().splitlines():
        rec = json.loads(ln)
        rec["_doc"] = json.loads((trib / rec["file"]).read_bytes())
        out.append(rec)
    return out


def current_states(decs: list) -> dict:
    st = {s: init_state() for s in STREAMS}
    for d in decs:
        st.update(d["_doc"]["streams_after"])
    return st


def ssd_journal_time(ssd_em: Path | None, sha: str) -> str | None:
    if ssd_em is None:
        return None
    j = ssd_em / "JURNAL_EMISII.jsonl"
    if not j.exists():
        return None
    for x in j.read_text(encoding="utf-8").splitlines():
        if x.strip():
            r = json.loads(x)
            if r.get("sha256") == sha:
                return r.get("mirrored_utc")
    return None


def observed_before(trib: Path, sha: str, draw_utc: str) -> bool:
    p = trib / "JUDECATOR_RULARI.jsonl"
    if not p.exists():
        return False
    d = parse_utc(draw_utc)
    for x in p.read_text(encoding="utf-8").splitlines():
        if not x.strip():
            continue
        r = json.loads(x)
        if parse_utc(r["utc"]) < d and any(o.get("sha256") == sha for o in r.get("observed", [])):
            return True
    return False


# ---------------------------------------------------------------- oglinda SSD: copii, jurnal mmap, matricea (§8)
def matrix_rows(decs: list) -> list:
    st = {s: init_state() for s in STREAMS}
    rows = []
    for d in decs:
        doc = d["_doc"]
        st.update(doc["streams_after"])
        g = doc["game"]
        lne = [doc["models"][m]["ln_e"] for m in MODELS]
        row = struct.pack(ROW_FMT, d["i"], int(doc["target_date"].replace("-", "")), GAME_IDX[g],
                          STATUS_CODE[doc["status"]], *lne, *[st[s]["lnE"] for s in STREAMS],
                          *[st[s]["lnE_conf"] for s in STREAMS], *[STATES[st[s]["state"]] for s in STREAMS])
        rows.append(row + b"\0" * (ROW - len(row)))
    return rows


def matrix_header(nrows: int) -> bytes:
    h = MAGIC + struct.pack("<IIQ", 1, ROW, nrows) + ",".join(STREAMS).encode()
    return h + b"\0" * (HDR - len(h))


def matrix_sync(path: Path, rows: list) -> str:
    want = matrix_header(len(rows)) + b"".join(rows)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            os.ftruncate(fd, len(want))
            with mmap.mmap(fd, len(want)) as mm:
                mm[:] = want
                mm.flush()
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(path, 0o444)
        return f"created:{len(rows)}"
    old = path.read_bytes()
    if old[:8] != MAGIC:
        raise RuntimeError("matrice SSD: magic invalid")
    nold = struct.unpack("<Q", old[16:24])[0]
    if nold > len(rows) or old[HDR:HDR + nold * ROW] != b"".join(rows[:nold]) or len(old) != HDR + nold * ROW:
        raise RuntimeError("matrice SSD: prefixul diferă de recalculare")
    if nold == len(rows):
        return f"unchanged:{nold}"
    os.chmod(path, 0o644)
    fd = os.open(path, os.O_RDWR)
    try:
        os.ftruncate(fd, len(want))
        with mmap.mmap(fd, len(want)) as mm:
            mm[HDR + nold * ROW:] = b"".join(rows[nold:])
            mm[:HDR] = matrix_header(len(rows))
            mm.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
        os.chmod(path, 0o444)
    return f"appended:{len(rows) - nold}"


def ssd_sync(ssd: Path, trib: Path, decs: list) -> dict:
    log = []
    try:
        ssd.mkdir(parents=True, exist_ok=True)
        jp = ssd / "JURNAL_DECONTARI.jsonl"
        have = {json.loads(x)["sha256"] for x in jp.read_text(encoding="utf-8").splitlines() if x.strip()} if jp.exists() else set()
        for d in decs:
            data = (trib / d["file"]).read_bytes()
            dst = ssd / d["file"]
            if dst.exists():
                if dst.read_bytes() != data:
                    raise RuntimeError(f"copia SSD diferă: {d['file']}")
            else:
                write_exclusive(dst, data)
                log.append("copied:" + d["file"])
            if d["sha256"] not in have:
                line = json.dumps({"i": d["i"], "file": d["file"], "sha256": d["sha256"], "game": d["game"],
                                   "target_date": d["target_date"], "status": d["status"],
                                   "mirrored_utc": iso(dt.datetime.now(dt.timezone.utc))}, ensure_ascii=False)
                mmap_append(jp, line.encode() + b"\n")
                log.append("journal:" + d["file"])
        log.append("matrix:" + matrix_sync(ssd / "SCORURI_JU.mmap", matrix_rows(decs)))
        return {"status": "ok", "dir": str(ssd), "log": log}
    except Exception as exc:
        return {"status": "error", "dir": str(ssd), "error": repr(exc)[:300], "log": log}


# ---------------------------------------------------------------- rularea judecătorului
def judge(root: Path, now: dt.datetime, ssd: Path | None, test_mode: bool, use_gpu: bool = True,
          ssd_em: Path | None = None) -> tuple[int, dict]:
    trib = root / "tu4" / "tribunal"
    trib.mkdir(parents=True, exist_ok=True)
    lockf = open(trib / ".lock", "a+")
    fcntl.flock(lockf, fcntl.LOCK_EX)
    run = {"utc": iso(now), "test_mode": test_mode, "decided": [], "pending": [], "observed": [], "incidents": []}
    rc = EXIT_OK
    try:
        code = check_code(test_mode)
        entries, lant_b = load_chain(trib)
        check_frozen_29(trib, root, test_mode)
        run["lant_sha256"] = sha_bytes(lant_b)
        run["emissions"] = len(entries)
        decs = read_decontari(trib)
        done = {(d["game"], d["target_date"]) for d in decs}
        run["observed"] = [{"game": e["game"], "target_date": e["target_date"], "sha256": e["sha256"]}
                           for e in entries if (e["game"], e["target_date"]) not in done]
        try:
            live = load_live(root)
        except (ArhivaInvalida, OSError, KeyError, ValueError) as exc:
            run["archive_error"] = str(exc)[:300]
            rc = EXIT_REFUSED
            live = None
        if live is not None:
            run["archive"] = live["meta"]
            for d in decs:                                           # revizii ale sursei după decontare
                doc = d["_doc"]
                if doc["status"] == "DECONTAT":
                    R = regular_records(live, doc["game"], doc["target_date"])
                    if len(R) != 1 or canon(R[0]) != doc["record"]["canonical"]:
                        inc = incident(root, f"JU_REVIZIE_{doc['game']}_{doc['target_date']}",
                                       {"incident": "revizie_sursa", "decontare": d["file"], "now": iso(now),
                                        "records_now": [canon(r) for r in R]})
                        if inc:
                            run["incidents"].append(inc)
            states = current_states(decs)
            for game in GAMES:
                for ent in sorted((e for e in entries if e["game"] == game), key=lambda e: e["target_date"]):
                    if (game, ent["target_date"]) in done:
                        continue
                    dec = decide(ent, live, now, test_mode)
                    if "pending" in dec:
                        run["pending"].append({"game": game, "target_date": ent["target_date"], "reason": dec["pending"]})
                        if dec.get("early_record"):
                            inc = incident(root, f"JU_CEAS_{game}_{ent['target_date']}",
                                           {"incident": "inregistrare_inainte_de_extragere", "now": iso(now),
                                            "emission": ent["file"]})
                            if inc:
                                run["incidents"].append(inc)
                        break                                        # ordinea cronologică pe flux (§4)
                    doc = settle(root, trib, ent, dec, live, states, decs, code, now, test_mode, use_gpu, ssd_em)
                    states.update(doc["streams_after"])
                    decs = read_decontari(trib)
                    run["decided"].append({"game": game, "target_date": ent["target_date"], "status": doc["status"],
                                           "ln_e": {m: doc["models"][m]["ln_e"] for m in MODELS}})
        run["streams"] = {s: {"state": v["state"], "lnE": v["lnE"], "lnE_conf": v["lnE_conf"]}
                          for s, v in current_states(read_decontari(trib)).items()}
        run["ssd"] = ssd_sync(ssd, trib, read_decontari(trib)) if ssd is not None else {"status": "none"}
        run["action"] = "decided" if run["decided"] else ("refused_archive" if rc else "nothing_to_settle")
    except Integritate as exc:
        rc = EXIT_REFUSED
        run.update(action="refused_integrity", reason=str(exc))
        run["incidents"].append(incident(root, f"JU_INTEGRITATE_{iso(now).replace(':', '').replace('.', '_')}",
                                         {"incident": "integritate", "reason": str(exc), "now": iso(now)}))
    finally:
        run["rc"] = rc
        run["positive_claims_allowed"] = False
        try:
            append_line(trib / "JUDECATOR_RULARI.jsonl", json.dumps(run, ensure_ascii=False, default=str).encode())
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)
            lockf.close()
    return rc, run


def settle(root, trib, ent, dec, live, states, decs, code, now, test_mode, use_gpu, ssd_em) -> dict:
    em, game, D = ent["em"], ent["game"], ent["target_date"]
    rec = dec["record"]
    models, blocks = model_factors(em, rec)
    decided = dt.datetime.now(dt.timezone.utc) if not test_mode else now
    before = {f"{m}_{game}": states[f"{m}_{game}"] for m in MODELS}
    after = {}
    for m in MODELS:
        s = f"{m}_{game}"
        after[s], cnt = advance(states[s], dec["status"], models[m]["ln_e"], D, em["emitted_utc"], iso(decided))
        models[m]["counted"] = cnt
    gm = None
    if blocks and any(b[4] for b in blocks):
        gm = gpu_mirror(blocks) if use_gpu else {"status": "disabled (--fara-gpu)", "pass": None}
    gl = live["games"][game]
    doc = {
        "protocol": "TU4-JU", "session": "S13", "label": LABEL, "positive_claims_allowed": False,
        "game": game, "target_date": D, "status": dec["status"], "reason": dec["reason"],
        "decided_utc": iso(decided), "test_mode": test_mode,
        "emission": {"file": ent["file"], "sha256": ent["sha256"], "lant_i": ent["lant_i"],
                     "chain_index": em["chain"]["index"], "emitted_utc": em["emitted_utc"],
                     "cutoff_utc": em["cutoff_utc"], "draw_utc": em["draw_utc"]},
        "admissibility": dec["adm"], "n_regular_records": dec["n_regular"],
        "archive": {**live["meta"], "file": gl["file"], "sha256": gl["sha256"], "records": gl["records"]},
        "record": ({"draw_key": rec.get("draw_key"), "canonical": canon(rec),
                    "has_source_disagreement": rec.get("has_source_disagreement"),
                    "verification": rec.get("verification")} if rec else None),
        "draw": {"numbers": rec["numbers"], "joker": rec.get("joker") if GAMES[game]["ball"] else None} if rec else None,
        "models": models, "streams_before": before, "streams_after": after,
        "thresholds": {"explore_ln": LN_EXPLORE, "confirm_ln": LN_CONFIRM, "retire_ln": LN_RETIRE, "M": 6},
        "gpu_mirror": gm,
        "corroboration": {"ssd_journal_mirrored_utc": ssd_journal_time(ssd_em, ent["sha256"]),
                          "observed_by_judge_before_draw": observed_before(trib, ent["sha256"], em["draw_utc"])},
        "code": code,
    }
    data = (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    rel = f"decontari/{game}/{D}.json"
    write_exclusive(trib / rel, data)
    lines = (trib / "DECONTARI.jsonl").read_bytes().splitlines() if (trib / "DECONTARI.jsonl").exists() else []
    line = {"i": len(lines), "game": game, "target_date": D, "status": dec["status"], "file": rel,
            "sha256": sha_bytes(data), "prev_line_sha256": sha_bytes(lines[-1]) if lines else JU_SEAL_SHA}
    append_line(trib / "DECONTARI.jsonl", json.dumps(line, ensure_ascii=False, sort_keys=True).encode())
    if dec["status"] == "RESPINS":
        incident(root, f"JU_RESPINS_{game}_{D}", {"incident": "emisie_respinsa", "emission": ent["file"],
                                                  "admissibility": dec["adm"]})
    if gm is not None and gm.get("pass") is False:
        incident(root, f"JU_GPU_{game}_{D}", {"incident": "oglinda_gpu", "gpu_mirror": gm})
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="TU4-JU: decontarea e-proces (protocol tu4/PROTOCOL_TU4_JU.md)")
    ap.add_argument("--ssd", type=Path, default=None, help="oglinda SSD, ex. ./ssd_data/QL649_TU4_JU")
    ap.add_argument("--fara-ssd", action="store_true")
    ap.add_argument("--fara-gpu", action="store_true", help="fără oglinda GPU (numai teste rapide)")
    ap.add_argument("--radacina-test", type=Path, default=None)
    ap.add_argument("--acum", default=None, help="ceas fals ISO UTC — NUMAI cu --radacina-test")
    a = ap.parse_args(argv)
    test_mode = a.radacina_test is not None
    if a.acum and not test_mode:
        print(json.dumps({"action": "refused", "reason": "--acum este permis numai cu --radacina-test"}))
        return EXIT_REFUSED
    if test_mode and a.radacina_test.resolve() == QL:
        print(json.dumps({"action": "refused", "reason": "rădăcina de test nu poate fi depozitul real"}))
        return EXIT_REFUSED
    if a.fara_gpu and not test_mode:
        print(json.dumps({"action": "refused", "reason": "--fara-gpu este permis numai cu --radacina-test"}))
        return EXIT_REFUSED
    root = a.radacina_test.resolve() if test_mode else QL
    now = parse_utc(a.acum) if a.acum else dt.datetime.now(dt.timezone.utc)
    ssd = None if a.fara_ssd else a.ssd
    ssd_em = (ssd.parent / "QL649_TU4_EM") if ssd is not None else None
    rc, run = judge(root, now, ssd, test_mode, use_gpu=not a.fara_gpu, ssd_em=ssd_em)
    print(json.dumps({k: run.get(k) for k in ("utc", "action", "rc", "decided", "pending", "incidents", "streams")},
                     ensure_ascii=False, default=str))
    return rc


if __name__ == "__main__":
    sys.exit(main())
