#!/usr/bin/env python3
"""TU4-EM (S12): emițătorul prospectiv al tribunalului — H1 „MA” și H3 „AD”, ÎNGHEȚATE (tu4/ip_core.py ab3e1de9…).

Protocol: tu4/PROTOCOL_TU4_EM.md, sigiliu tu4/SIGILIU_TU4_EM.json (2026-10-27T21:37:15Z), scrise ÎNAINTE de acest cod.

    .venv/bin/python -B tu4/emite.py --joc {649,540,joker} [--ssd DIR | --fara-ssd]
    (teste: --radacina-test DIR --acum 2026-10-27T21:40:00Z)

Warm start = arhiva LIVE (tu3/date/live/); ținta = următoarea extragere joi/duminică 18:30 Europe/Bucharest; sigilare
înainte de 16:00 local; lanț append-only SHA-256 (tu4/tribunal/); oglindă asincronă pe SSD (copie + jurnal prin mmap);
oglindă de fază complexă complex64 compilată (torch.compile fullgraph), autoritatea rămâne float64.
Zero popularitate: singura intrare este lista extragerilor. Calcul clasic. positive_claims_allowed=false.
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
import queue
import sys
import threading
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
sys.path.insert(0, str(HERE))
import ip_core as C  # noqa: E402  (nucleul ÎNGHEȚAT, neschimbat)

PROTOCOL = HERE / "PROTOCOL_TU4_EM.md"
SEAL = HERE / "SIGILIU_TU4_EM.json"
CODE_SEAL = HERE / "SIGILIU_TU4_EM_COD.json"
IP_CORE_SHA = "ab3e1de93d8e5ae537a8c80599905aaa19cc103602f9b18f4b7f7f6f8a48c302"
SEAL_SHA = "82459f48458ef2ee248784929ea2c4c18ae60469b0084e4a7345910a7b5c53c7"
TZ = ZoneInfo("Europe/Bucharest")
DRAW_T, CUTOFF_T, FINAL_T = dt.time(18, 30), dt.time(16, 0), dt.time(15, 0)
WEEKDAYS = (3, 6)
M_STREAMS, THRESHOLD = 6, 600
MODELS_EM = ("H1", "H3")
GAMES_EM = {"649": dict(n=49, k=6, b=6, ball=False), "540": dict(n=40, k=6, b=5, ball=False),
            "joker": dict(n=45, k=5, b=5, ball=True)}
NB, K = 20, C.K_AD
GATE = dict(lambda_abs=1e-4, logw_abs=1e-5, logw_rel_of_max=1e-4)
COMPILE_MODE = "max-autotune-no-cudagraphs"
LABEL = "test științific în curs; nu este sfat de joc"
EXIT_OK, EXIT_REFUSED, EXIT_LATE, EXIT_POSTPONED = 0, 3, 4, 75


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
    """Creare exclusivă (O_EXCL), 0444, fsync — o emisie existentă nu se suprascrie niciodată."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_dir(path.parent)


def append_line(path: Path, line: bytes) -> None:
    """Adăugare O_APPEND la un registru 0444 (redeschis 0644 numai pe durata adăugării)."""
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
    """Adăugare prin mmap: extinde fișierul, mapează regiunea nouă, scrie, flush + fsync (jurnalul SSD)."""
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


# ---------------------------------------------------------------- arhiva LIVE (protocol §1)
class Refuz(Exception):
    pass


def load_live(root: Path, game: str) -> dict:
    g = GAMES_EM[game]
    live = root / "tu3" / "date" / "live"
    cur_b = (live / "CURRENT_LIVE.json").read_bytes()
    cur = json.loads(cur_b)
    vdir = live / cur["version_dir"]
    man_b = (vdir / "MANIFEST_LIVE.json").read_bytes()
    man = json.loads(man_b)
    gm, gc = man["games"][game], cur["games"][game]
    fpath = vdir / gm["file"]
    fb = fpath.read_bytes()
    fsha = sha_bytes(fb)
    if not (fsha == gm["sha256"] == gc["sha256"]):
        raise Refuz(f"sha arhivă {game}: fișier {fsha[:12]} manifest {gm['sha256'][:12]} curent {gc['sha256'][:12]}")
    if man.get("database_sha256") != cur.get("database_sha256"):
        raise Refuz("database_sha256 diferit între CURRENT_LIVE și manifest")
    rows = [json.loads(x) for x in fb.decode("utf-8").splitlines() if x.strip()]
    if len(rows) != gm["records"] or len(rows) != gc["records"]:
        raise Refuz(f"număr de înregistrări {len(rows)} ≠ manifest {gm['records']} / curent {gc['records']}")
    n, k = g["n"], g["k"]
    c = np.zeros(n, np.int64)
    cb = np.zeros(NB, np.int64)
    last = ""
    for r in rows:
        nums = r.get("numbers")
        if (not isinstance(nums, list) or len(nums) != k or len(set(nums)) != k
                or not all(isinstance(x, int) and not isinstance(x, bool) and 1 <= x <= n for x in nums)):
            raise Refuz(f"extragere invalidă {r.get('draw_key')}")
        c[np.array(nums) - 1] += 1
        if g["ball"]:
            j = r.get("joker")
            if not (isinstance(j, int) and not isinstance(j, bool) and 1 <= j <= NB):
                raise Refuz(f"bilă invalidă {r.get('draw_key')}")
            cb[j - 1] += 1
        last = max(last, r["draw_date"])
    if last != gm["last_date"]:
        raise Refuz(f"last_date {last} ≠ manifest {gm['last_date']}")
    return {"c": c, "cb": cb if g["ball"] else None, "N": len(rows),
            "meta": {"database_sha256": cur["database_sha256"], "version_dir": cur["version_dir"],
                     "manifest_sha256": sha_bytes(man_b), "current_live_sha256": sha_bytes(cur_b),
                     "file": f"tu3/date/live/{cur['version_dir']}/{gm['file']}", "sha256": fsha,
                     "records": len(rows), "last_date": last, "last_key": gm["last_key"], "run_id": cur.get("run_id")}}


# ---------------------------------------------------------------- ținta (protocol §2)
def at_local(d: dt.date, t: dt.time) -> dt.datetime:
    return dt.datetime.combine(d, t, TZ).astimezone(dt.timezone.utc)


def schedule(now: dt.datetime) -> dict:
    d = now.astimezone(TZ).date()
    while not (d.weekday() in WEEKDAYS and at_local(d, CUTOFF_T) > now):
        d += dt.timedelta(days=1)
    p = d - dt.timedelta(days=1)
    while p.weekday() not in WEEKDAYS:
        p -= dt.timedelta(days=1)
    return {"target_date": d.isoformat(), "previous_draw_date": p.isoformat(), "draw_utc": at_local(d, DRAW_T),
            "cutoff_utc": at_local(d, CUTOFF_T), "final_window_utc": at_local(d, FINAL_T)}


# ---------------------------------------------------------------- modelele float64 (autoritatea, protocol §3)
def inclusion(logw: np.ndarray, k: int) -> np.ndarray:
    lw = torch.as_tensor(logw, dtype=C.DT)[None]
    w = torch.exp(lw)
    e = C.esp(w, k)
    em = torch.ones_like(w)
    for j in range(1, k):
        em = e[..., j:j + 1] - w * em
    return (w * em / e[..., k:k + 1])[0].numpy()


def x2_smooth(c: np.ndarray, N: int, n: int, k: int) -> float:
    p = k / n
    z = math.sqrt((n - 1) / n) * (c - N * p) / math.sqrt(N * p * (1 - p))
    return float(((z @ C.dct_basis(n).numpy()) ** 2).sum())


def model_block(m: str, c: np.ndarray, N: int, n: int, k: int, b: int) -> dict:
    cf = c.astype(float)
    if m == "H1":
        lw, lam = C.lw_h1_np(cf, N, n, k)
        _, x2 = C.theta_x2(torch.as_tensor(cf, dtype=C.DT)[None], torch.as_tensor([float(N)], dtype=C.DT),
                           torch.as_tensor([float(N)], dtype=C.DT), n, k)
        x2, df = float(x2[0]), n - 1
    else:
        lw, lam = C.lw_h3_np(cf, N, n, k)
        x2, df = x2_smooth(cf, N, n, k), K
    lw = np.asarray(lw, float)
    pi = inclusion(lw, k)
    out = {"lambda": float(lam), "X2": x2, "df": df, "bet_active": bool(lam > 0), "logw": [float(v) for v in lw],
           "D_nats": C.D_np(lw, k)}
    if k == 1:
        q = np.exp(lw - lw.max())
        q = q / q.sum()
        out["q"] = [float(v) for v in q]
        out["top_ball"] = C.ticket(lw, 1)[0]
    else:
        out["pi"] = [float(v) for v in pi]
        out["pi_sum"] = float(pi.sum())
        out["top_ticket"] = C.ticket(lw, b)
    if not out["bet_active"]:
        out["ticket_note"] = ("lambda = 0: modelul NU pariază (q = uniform, e-factor exact 1); biletul/bila top este "
                              "numai artefactul regulii de egalitate (etichetele cele mai mici)")
    return out


# ---------------------------------------------------------------- oglinda de fază complexă complex64 (protocol §4)
_MIRRORS: dict = {}
MIRROR_STATUS: dict = {}


def _mirror_fn(n: int, k: int):
    p = k / n
    s2n = math.sqrt(2.0 / n)

    def f(c, N, ph):
        z = (math.sqrt((n - 1) / n) * (c - N * p) / torch.sqrt(N * p * (1 - p))).to(torch.complex64)
        kappa = (math.sqrt((n - 1) / n) / torch.sqrt(N * p * (1 - p))).to(torch.complex64)
        thc = z * kappa                                               # θ̂ în reprezentare complexă
        x2 = (torch.abs(torch.fft.fft(z)) ** 2).sum() / n             # Parseval: energia spectrală = X²
        lam1 = torch.clamp(1.0 - (n - 3) / x2, min=0.0)
        lw1 = lam1 * torch.real(thc)
        a = s2n * torch.real(ph @ z)                                  # coeficienți cosinus prin faze e^{-iπm(i-½)/n}
        x2s = (a * a).sum()
        ath = (s2n * torch.real(ph @ thc)).to(torch.complex64)
        rec = s2n * torch.real(ph.conj().transpose(0, 1) @ ath)       # Σ_m b_m(i) a_m(θ̂)
        lam3 = torch.clamp(1.0 - (K - 2) / x2s, min=0.0)
        lw3 = lam3 * rec
        return lam1, lw1, x2, lam3, lw3, x2s
    return f


def mirror(c: np.ndarray, N: int, n: int, k: int) -> dict:
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    key = (n, k)
    if key not in _MIRRORS:
        f = _mirror_fn(n, k)
        try:
            _MIRRORS[key] = torch.compile(f, mode=COMPILE_MODE, fullgraph=True, dynamic=False)
            MIRROR_STATUS[f"{n}_{k}"] = f"compiled:{COMPILE_MODE}:fullgraph:{dev}"
        except Exception as exc:  # declarat (protocol §4)
            _MIRRORS[key] = f
            MIRROR_STATUS[f"{n}_{k}"] = "eager_fallback:" + repr(exc)[:200]
    i = torch.arange(1, n + 1, dtype=torch.float32, device=dev)
    m = torch.arange(1, K + 1, dtype=torch.float32, device=dev)
    ph = torch.polar(torch.ones(K, n, device=dev), -math.pi * m[:, None] * (i[None, :] - 0.5) / n)
    ct = torch.as_tensor(c.astype(float), dtype=torch.float64, device=dev)
    Nt = torch.as_tensor(float(N), dtype=torch.float64, device=dev)
    t0 = time.perf_counter()
    try:
        res = _MIRRORS[key](ct, Nt, ph)
    except Exception as exc:  # eșec la prima execuție ⇒ eager, declarat
        MIRROR_STATUS[f"{n}_{k}"] = "eager_fallback_runtime:" + repr(exc)[:200]
        _MIRRORS[key] = _mirror_fn(n, k)
        res = _MIRRORS[key](ct, Nt, ph)
    if dev == "cuda":
        torch.cuda.synchronize()
    lam1, lw1, x2, lam3, lw3, x2s = (r.detach().cpu() for r in res)
    return {"device": dev, "dtype": "complex64", "seconds": round(time.perf_counter() - t0, 3),
            "H1": {"lambda": float(lam1), "logw": lw1.double().numpy(), "X2": float(x2)},
            "H3": {"lambda": float(lam3), "logw": lw3.double().numpy(), "X2": float(x2s)}}


def gate(ref: dict, mir: dict, b: int, k: int) -> dict:
    lw = np.asarray(ref["logw"])
    lwc = mir["logw"]
    dl = abs(mir["lambda"] - ref["lambda"])
    dw = float(np.max(np.abs(lwc - lw)))
    tol = GATE["logw_abs"] + GATE["logw_rel_of_max"] * float(np.max(np.abs(lw)))
    rec = {"lambda": mir["lambda"], "X2": mir["X2"], "abs_dlambda": dl, "max_abs_dlogw": dw, "tol_logw": tol,
           "pass": bool(dl <= GATE["lambda_abs"] and dw <= tol)}
    if k == 1:
        rec["top_ball_match"] = C.ticket(lwc, 1)[0] == ref["top_ball"]
    else:
        rec["top_ticket_match"] = C.ticket(lwc, b) == ref["top_ticket"]
    return rec


# ---------------------------------------------------------------- oglinda SSD asincronă (protocol §0, §5)
class SSDMirror(threading.Thread):
    def __init__(self, ssd: Path | None, trib: Path):
        super().__init__(daemon=True)
        self.ssd, self.trib = ssd, trib
        self.q: queue.Queue = queue.Queue()
        self.log: list = []
        self.ok = ssd is not None

    def run(self):
        if self.ssd is None:
            return
        try:
            self.ssd.mkdir(parents=True, exist_ok=True)
            self.backfill()
        except Exception as exc:
            self.ok = False
            self.log.append("backfill_error:" + repr(exc)[:200])
        while True:
            item = self.q.get()
            if item is None:
                break
            try:
                if item == "__lant__":
                    self.sync_lant()
                else:
                    self.store(*item)
            except Exception as exc:
                self.ok = False
                self.log.append("store_error:" + repr(exc)[:200])

    def journal_shas(self) -> set:
        j = self.ssd / "JURNAL_EMISII.jsonl"
        if not j.exists():
            return set()
        return {json.loads(x)["sha256"] for x in j.read_text(encoding="utf-8").splitlines() if x.strip()}

    def store(self, rel: str, data: bytes):
        dst = self.ssd / rel
        if dst.exists():
            if dst.read_bytes() != data:
                raise RuntimeError(f"oglinda SSD diferă: {rel}")
        else:
            write_exclusive(dst, data)
            self.log.append("copied:" + rel)
        s = sha_bytes(data)
        if s not in self.journal_shas():
            em = json.loads(data)
            line = json.dumps({"file": rel, "sha256": s, "game": em["game"], "target_date": em["target_date"],
                               "emitted_utc": em["emitted_utc"], "mirrored_utc": iso(dt.datetime.now(dt.timezone.utc))},
                              ensure_ascii=False).encode() + b"\n"
            mmap_append(self.ssd / "JURNAL_EMISII.jsonl", line)
            self.log.append("journal:" + rel)

    def backfill(self):
        for f in sorted((self.trib / "emisii").glob("*/*.json")):
            self.store(str(f.relative_to(self.trib)), f.read_bytes())
        self.sync_lant()

    def sync_lant(self):
        """Copia SSD a registrului LANT.jsonl: numai extindere (prefixul vechi trebuie să se păstreze)."""
        lant = self.trib / "LANT.jsonl"
        if lant.exists():
            data = lant.read_bytes()
            dst = self.ssd / "LANT.jsonl"
            if not dst.exists() or dst.read_bytes() != data:
                if dst.exists():
                    if not data.startswith(dst.read_bytes()):
                        raise RuntimeError("LANT SSD nu este prefix al lanțului canonic")
                    os.chmod(dst, 0o644)
                tmp = dst.with_suffix(".tmp")
                tmp.write_bytes(data)
                os.replace(tmp, dst)
                os.chmod(dst, 0o444)
                self.log.append("lant_synced")

    def finish(self, timeout: float = 120.0) -> dict:
        if self.ssd is None:
            return {"status": "none", "reason": "SSD absent / --fara-ssd"}
        self.q.put(None)
        self.join(timeout)
        if self.is_alive():
            return {"status": "timeout", "log": self.log}
        return {"status": "ok" if self.ok else "error", "dir": str(self.ssd), "log": self.log}


# ---------------------------------------------------------------- emisia
def chain_state(trib: Path, game: str, target: str) -> dict:
    files = sorted((trib / "emisii" / game).glob("*.json"))
    if files and files[-1].stem >= target:
        raise Refuz(f"lanț: ultima emisie {files[-1].stem} nu este anterioară țintei {target}")
    prev = sha_file(files[-1]) if files else sha_file(SEAL)
    return {"index": len(files), "prev_sha256": prev, "prev_file": files[-1].name if files else "GENESIS:SIGILIU_TU4_EM.json"}


def lant_append(trib: Path, rec: dict) -> None:
    lant = trib / "LANT.jsonl"
    lines = lant.read_bytes().splitlines() if lant.exists() else []
    rec = {"i": len(lines), **rec, "prev_line_sha256": sha_bytes(lines[-1]) if lines else sha_file(SEAL)}
    append_line(lant, json.dumps(rec, ensure_ascii=False, sort_keys=True).encode())


def check_code(test_mode: bool) -> dict:
    code = {"emite_sha256": sha_file(Path(__file__)), "ip_core_sha256": sha_file(HERE / "ip_core.py"),
            "protocol_sha256": sha_file(PROTOCOL), "protocol_seal_sha256": sha_file(SEAL)}
    if code["ip_core_sha256"] != IP_CORE_SHA:
        raise Refuz("ip_core.py diferă de nucleul ÎNGHEȚAT")
    if code["protocol_seal_sha256"] != SEAL_SHA:
        raise Refuz("sigiliul protocolului EM diferă")
    if json.loads(SEAL.read_text())["document"]["sha256"] != code["protocol_sha256"]:
        raise Refuz("protocolul EM diferă de cel sigilat")
    if CODE_SEAL.exists():
        cs = json.loads(CODE_SEAL.read_text())
        code["code_seal_sha256"] = sha_file(CODE_SEAL)
        if cs["files"]["tu4/emite.py"] != code["emite_sha256"]:
            raise Refuz("emite.py diferă de codul sigilat")
    elif not test_mode:
        raise Refuz("lipsește sigiliul codului (SIGILIU_TU4_EM_COD.json): emisia reală nu este permisă")
    else:
        code["code_seal_sha256"] = None
    return code


def emit(game: str, root: Path, now: dt.datetime, ssd: Path | None, test_mode: bool) -> tuple[int, dict]:
    trib = root / "tu4" / "tribunal"
    trib.mkdir(parents=True, exist_ok=True)
    g = GAMES_EM[game]
    lockf = open(trib / ".lock", "a+")
    fcntl.flock(lockf, fcntl.LOCK_EX)
    mir = SSDMirror(ssd, trib)
    mir.start()                                                       # backfill asincron în timp ce se calculează
    run = {"utc": iso(now), "game": game, "test_mode": test_mode}
    try:
        code = check_code(test_mode)
        sch = schedule(now)
        run["target_date"] = sch["target_date"]
        dst = trib / "emisii" / game / f"{sch['target_date']}.json"
        if dst.exists():
            run.update(action="already_emitted", file=str(dst.relative_to(root)), sha256=sha_file(dst))
            return EXIT_OK, run
        if not (now < sch["cutoff_utc"] < sch["draw_utc"]):
            run.update(action="late", reason="după termenul de sigilare")
            return EXIT_LATE, run
        live = load_live(root, game)
        complete = live["meta"]["last_date"] >= sch["previous_draw_date"]
        if not complete and now < sch["final_window_utc"]:
            run.update(action="postponed", reason=f"arhiva LIVE se oprește la {live['meta']['last_date']} < "
                                                  f"{sch['previous_draw_date']}; se așteaptă până la fereastra finală")
            return EXIT_POSTPONED, run
        n, k, b = g["n"], g["k"], g["b"]
        models, c64 = {}, {}
        mm = mirror(live["c"], live["N"], n, k)
        mb = mirror(live["cb"], live["N"], NB, 1) if g["ball"] else None
        for m in MODELS_EM:
            blk = model_block(m, live["c"], live["N"], n, k, b)
            rec = {"main": gate(blk, mm[m], b, k)}
            if g["ball"]:
                blk["ball"] = model_block(m, live["cb"], live["N"], NB, 1, 1)
                rec["ball"] = gate(blk["ball"], mb[m], 1, 1)
            models[m] = blk
            c64[m] = rec
        c64_pass = all(r["pass"] for v in c64.values() for r in v.values())
        chain = chain_state(trib, game, sch["target_date"])
        emitted = dt.datetime.now(dt.timezone.utc) if not test_mode else now
        if not emitted < sch["cutoff_utc"]:
            run.update(action="late", reason="termenul a trecut în timpul calculului")
            return EXIT_LATE, run
        em = {
            "protocol": "TU4-EM", "session": "S12", "label": LABEL, "positive_claims_allowed": False,
            "game": game, "n": n, "k": k, "ticket_size": b, "ball_n": NB if g["ball"] else None,
            "target_date": sch["target_date"], "target_kind": "regular",
            "draw_utc": iso(sch["draw_utc"]), "cutoff_utc": iso(sch["cutoff_utc"]), "emitted_utc": iso(emitted),
            "previous_draw_date": sch["previous_draw_date"], "warm_start_complete": bool(complete),
            "warm_start": {"N": live["N"], "counts": [int(x) for x in live["c"]],
                           "ball_counts": [int(x) for x in live["cb"]] if g["ball"] else None},
            "archive": live["meta"], "code": code,
            "tribunal": {"M": M_STREAMS, "threshold": THRESHOLD, "threshold_ln": math.log(THRESHOLD),
                         "retire_ln": -10.0, "streams": [f"{m}_{gg}" for m in MODELS_EM for gg in GAMES_EM],
                         "streams_this_emission": [f"{m}_{game}" for m in MODELS_EM]},
            "models": models,
            "c64_mirror": {"pass": c64_pass, "gate": GATE, "compile_status": dict(MIRROR_STATUS),
                           "device": mm["device"], "seconds_main": mm["seconds"],
                           "seconds_ball": mb["seconds"] if mb else None, "per_model": c64,
                           "note": "oglindă de algoritm (complex64, faze/FFT); autoritatea = float64 ip_core"},
            "chain": chain, "test_mode": test_mode,
        }
        data = (json.dumps(em, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
        write_exclusive(dst, data)
        s = sha_bytes(data)
        rel = str(dst.relative_to(trib))
        lant_append(trib, {"game": game, "target_date": sch["target_date"], "file": rel,
                           "sha256": s, "emitted_utc": em["emitted_utc"]})
        mir.q.put((rel, data))
        mir.q.put("__lant__")
        run.update(action="emitted", file=str(dst.relative_to(root)), sha256=s, c64_pass=c64_pass,
                   warm_start_complete=bool(complete),
                   tickets={m: models[m]["top_ticket"] for m in MODELS_EM},
                   balls={m: models[m]["ball"]["top_ball"] for m in MODELS_EM} if g["ball"] else None)
        if not c64_pass and not test_mode:
            inc = HERE / "incidente" / f"EM_C64_{game}_{sch['target_date']}.json"
            write_exclusive(inc, (json.dumps({"incident": "c64_gate_fail", "emission_sha256": s, "per_model": c64},
                                             indent=1, default=str) + "\n").encode())
        return EXIT_OK, run
    except Refuz as exc:
        run.update(action="refused", reason=str(exc))
        return EXIT_REFUSED, run
    finally:
        run["ssd_mirror"] = mir.finish()
        try:
            append_line(trib / "RULARI.jsonl", json.dumps(run, ensure_ascii=False, default=str).encode())
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)
            lockf.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="TU4-EM: emisia prospectivă H1/H3 (protocol tu4/PROTOCOL_TU4_EM.md)")
    ap.add_argument("--joc", required=True, choices=sorted(GAMES_EM))
    ap.add_argument("--ssd", type=Path, default=None, help="directorul oglinzii pe SSD (ex. ./ssd_data/QL649_TU4_EM)")
    ap.add_argument("--fara-ssd", action="store_true")
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
    root = a.radacina_test.resolve() if test_mode else QL
    now = parse_utc(a.acum) if a.acum else dt.datetime.now(dt.timezone.utc)
    ssd = None if a.fara_ssd else a.ssd
    rc, run = emit(a.joc, root, now, ssd, test_mode)
    print(json.dumps(run, ensure_ascii=False, default=str))
    return rc


if __name__ == "__main__":
    sys.exit(main())
