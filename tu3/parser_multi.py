"""TU3 — modulul P: parser multi-joc (6/49, 5/40, Joker). Protocol: PROTOCOL_TU3_P.md (sigilat în SIGILIU_TU3_P.json).

Ingestie/inventar, NU experiment de selecție: citire, lanț de integritate, validare cu motive explicite, deduplicare,
ordonare stabilă, grupare pe zile calendaristice (ordinea din aceeași zi nu se folosește), tensori PyTorch pe `cuda`
(fallback CPU jurnalizat prin `parser.resolve_device`). Nu calculează operatori, nu produce variante sau prognoze,
nu citește OGLINDA și nu compară nicio extragere cu vreo prognoză. `positive_claims_allowed=false`.

Surse: produsul citește arhiva LIVE (`tu3/date/live/CURRENT_LIVE.json` → manifest → JSONL, hash-uri verificate);
protocoalele sigilate folosesc exporturile înghețate (`tu3/date/extrageri_540.jsonl`, `extrageri_joker.jsonl`,
`MANIFEST_DATE.json`) și, pentru 6/49, fișierul de cercetare sigilat (`parser.DEFAULT_SOURCE`).
6/49 deleagă integral la `parser.build_dataset` (nemodificat) printr-un adaptor de schemă pur, adresat prin conținut.
`engine.py` și `parser.py` NU se modifică; `parser.main` nu se apelează.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import logging
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
if str(QL) not in sys.path:
    sys.path.insert(0, str(QL))
import parser as QP  # noqa: E402  (parser.py al QL649, nemodificat)

LOG = logging.getLogger("tu3.parser_multi")
DATA = HERE / "date"
LIVE = DATA / "live"
DERIV = DATA / "derivat"
OUT = HERE / "rezultate" / "P"
FROZEN_649_SHA256 = "193eaf7a6f4f9948a43e53e053ee8c03b0cd591bed0279d15d312a2857fa707c"


@dataclass(frozen=True)
class GameSpec:
    code: str
    name: str
    n: int            # mărimea urnei principale
    r: int            # numere principale pe extragere
    ticket: object    # numere pe bilet/variantă (5/40: 5; Joker: "5+1")
    joker_m: int | None = None


GAMES: dict[str, GameSpec] = {
    "649": GameSpec("649", "Loto 6/49", 49, 6, 6, None),
    "540": GameSpec("540", "Loto 5/40", 40, 6, 5, None),
    "joker": GameSpec("joker", "Joker", 45, 5, "5+1", 20),
}


class IntegrityError(RuntimeError):
    """Lanțul de integritate (pointer → manifest → JSONL) sau referința înghețată nu se verifică. Refuz complet."""


def spec(game: str) -> GameSpec:
    if game not in GAMES:
        raise ValueError(f"joc necunoscut {game!r}; permise: {sorted(GAMES)}")
    return GAMES[game]


sha256_file = QP.sha256_file


def _count_nonblank(path: Path) -> int:
    return sum(1 for line in Path(path).read_bytes().decode("utf-8").splitlines() if line.strip())


# ---------------------------------------------------------------------------
# Surse (§1)
# ---------------------------------------------------------------------------
def resolve_live(game: str, live_root: Path = LIVE) -> tuple[Path, dict]:
    """Lanțul LIVE, citit o singură dată. Întoarce (cale JSONL, proveniență). Orice abatere ⇒ IntegrityError."""
    g = spec(game)
    live_root = Path(live_root)
    ptr_path = live_root / "CURRENT_LIVE.json"
    if not ptr_path.is_file():
        raise IntegrityError(f"pointer LIVE absent: {ptr_path}")
    ptr_bytes = ptr_path.read_bytes()
    try:
        ptr = json.loads(ptr_bytes)
        vdir_rel = ptr["version_dir"]
        man_sha_ptr = ptr["manifest_sha256"]
        g_ptr = ptr["games"][g.code]
    except (ValueError, KeyError, TypeError) as exc:
        raise IntegrityError(f"pointer LIVE invalid: {type(exc).__name__}: {exc}") from exc
    versions = (live_root / "versiuni").resolve()
    vdir = (live_root / str(vdir_rel)).resolve()
    if vdir == versions or not vdir.is_relative_to(versions):
        raise IntegrityError(f"version_dir în afara versiuni/: {vdir_rel!r}")
    man_path = vdir / "MANIFEST_LIVE.json"
    if not man_path.is_file():
        raise IntegrityError(f"manifest LIVE absent: {man_path}")
    man_bytes = man_path.read_bytes()
    if hashlib.sha256(man_bytes).hexdigest() != man_sha_ptr:
        raise IntegrityError("sha256(MANIFEST_LIVE.json) ≠ manifest_sha256 din pointer")
    try:
        man = json.loads(man_bytes)
        g_man = man["games"][g.code]
        fname = g_man["file"]
    except (ValueError, KeyError, TypeError) as exc:
        raise IntegrityError(f"manifest LIVE invalid: {type(exc).__name__}: {exc}") from exc
    if Path(fname).name != fname or fname != f"extrageri_{g.code}.jsonl":
        raise IntegrityError(f"nume de fișier neașteptat în manifest: {fname!r}")
    if g_man.get("draw_size") != g.r:
        raise IntegrityError(f"draw_size din manifest {g_man.get('draw_size')} ≠ regula jocului {g.r}")
    path = vdir / fname
    if not path.is_file():
        raise IntegrityError(f"JSONL LIVE absent: {path}")
    got = sha256_file(path)
    if got != g_man.get("sha256") or got != g_ptr.get("sha256"):
        raise IntegrityError(f"sha256({fname}) = {got[:12]}… ≠ manifest/pointer")
    if g_man.get("records") != g_ptr.get("records"):
        raise IntegrityError("records din manifest ≠ records din pointer")
    n_lines = _count_nonblank(path)
    if n_lines != g_man.get("records"):
        raise IntegrityError(f"{n_lines} rânduri citite ≠ records {g_man.get('records')} din manifest")
    prov = {"source_kind": "live", "pointer_sha256": hashlib.sha256(ptr_bytes).hexdigest(),
            "run_id": ptr.get("run_id"), "database_sha256": ptr.get("database_sha256"),
            "version_dir": str(vdir_rel), "manifest_sha256": man_sha_ptr, "file_sha256": got,
            "records_manifest": g_man.get("records"), "last_date_manifest": g_man.get("last_date"),
            "excluded_by_archive": len(g_man.get("excluded", []))}
    return path, prov


def resolve_frozen(game: str, data_root: Path = DATA) -> tuple[Path, dict]:
    """Referința înghețată pentru protocoalele sigilate. Hash diferit ⇒ IntegrityError."""
    g = spec(game)
    if g.code == "649":
        path = Path(QP.DEFAULT_SOURCE)
        got = sha256_file(path)
        if got != FROZEN_649_SHA256:
            raise IntegrityError(f"fișierul de cercetare 6/49 are sha {got[:12]}… ≠ {FROZEN_649_SHA256[:12]}…")
        return path, {"source_kind": "frozen", "file_sha256": got, "reference": "parser.DEFAULT_SOURCE (QL649 sigilat)"}
    data_root = Path(data_root)
    man_path = data_root / "MANIFEST_DATE.json"
    try:
        man = json.loads(man_path.read_bytes())
        g_man = man["games"][g.code]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise IntegrityError(f"MANIFEST_DATE invalid: {type(exc).__name__}: {exc}") from exc
    path = data_root / f"extrageri_{g.code}.jsonl"
    got = sha256_file(path)
    if got != g_man.get("sha256"):
        raise IntegrityError(f"sha256({path.name}) = {got[:12]}… ≠ MANIFEST_DATE")
    if _count_nonblank(path) != g_man.get("records"):
        raise IntegrityError("număr de rânduri ≠ MANIFEST_DATE")
    return path, {"source_kind": "frozen", "file_sha256": got, "manifest_sha256": sha256_file(man_path),
                  "records_manifest": g_man.get("records"), "source_run_id": man.get("source", {}).get("run_id")}


# ---------------------------------------------------------------------------
# Validare 5/40 și Joker (§3)
# ---------------------------------------------------------------------------
def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def validate_record(g: GameSpec, rec: dict) -> str | None:
    key = rec.get("draw_key")
    if not isinstance(key, str) or not key:
        return "draw_key_missing"
    if rec.get("game") != g.code:
        return "game_mismatch"
    date = rec.get("draw_date")
    if not isinstance(date, str):
        return "draw_date_missing"
    try:
        _dt.date.fromisoformat(date)
    except ValueError:
        return "draw_date_invalid"
    nums = rec.get("numbers")
    if not isinstance(nums, list) or len(nums) != g.r:
        return "numbers_count_invalid"
    if not all(_is_int(x) for x in nums):
        return "numbers_not_int"
    if any(x < 1 or x > g.n for x in nums):
        return "numbers_out_of_range"
    if len(set(nums)) != g.r:
        return "numbers_duplicate_in_row"
    jk = rec.get("joker")
    if g.joker_m is not None:
        if jk is None:
            return "joker_missing"
        if not _is_int(jk):
            return "joker_not_int"
        if jk < 1 or jk > g.joker_m:
            return "joker_out_of_range"
    elif jk is not None:
        return "joker_unexpected"
    return None


def clean_records(g: GameSpec, records: list[dict]) -> tuple[list[dict], dict]:
    removed, flags, valid = [], [], []
    for rec in records:
        why = validate_record(g, rec)
        if why:
            removed.append({"line": rec.get("_line"), "draw_key": rec.get("draw_key"), "reason": why})
        else:
            valid.append(rec)
    seen_keys, seen_sets, unique = set(), set(), []
    for rec in valid:
        nums = tuple(sorted(rec["numbers"]))
        if rec["draw_key"] in seen_keys:
            removed.append({"line": rec["_line"], "draw_key": rec["draw_key"], "reason": "duplicate_draw_key"})
            continue
        sk = (rec["draw_date"], nums, rec.get("joker"))
        if sk in seen_sets:
            removed.append({"line": rec["_line"], "draw_key": rec["draw_key"], "reason": "duplicate_date_set"})
            continue
        seen_keys.add(rec["draw_key"])
        seen_sets.add(sk)
        stored = rec.get("numbers_order_as_stored")
        if isinstance(stored, list) and sorted(stored) != list(nums):
            flags.append({"draw_key": rec["draw_key"], "flag": "stored_vs_sorted_mismatch"})
        if rec.get("has_source_disagreement"):
            flags.append({"draw_key": rec["draw_key"], "flag": "source_disagreement_kept"})
        if not rec["draw_key"].startswith(f"{g.code}:"):
            flags.append({"draw_key": rec["draw_key"], "flag": "key_prefix_mismatch"})
        unique.append(rec)
    unique.sort(key=lambda r: (r["draw_date"], r["draw_key"]))  # stabil
    reasons: dict[str, int] = {}
    for r in removed:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    kinds: dict[str, int] = {}
    for r in unique:
        k = str(r.get("draw_kind"))
        kinds[k] = kinds.get(k, 0) + 1
    return unique, {"removed": removed, "removed_by_reason": reasons, "flags": flags, "kinds_kept": kinds,
                    "physical_order_used": False, "within_day_order_used": False}


def _steps(dates: list[str]):
    n = len(dates)
    step_dates: list[str] = []
    step_index = torch.empty(n, dtype=torch.int64)
    offsets = [0]
    for i, d in enumerate(dates):
        if not step_dates or step_dates[-1] != d:
            if step_dates:
                offsets.append(i)
            step_dates.append(d)
        step_index[i] = len(step_dates) - 1
    offsets.append(n)
    if n == 0:
        offsets = [0]
    return step_index, torch.tensor(offsets, dtype=torch.int64), step_dates


def build_tensors(g: GameSpec, records: list[dict], device: torch.device) -> dict:
    T = len(records)
    draws = torch.tensor([sorted(r["numbers"]) for r in records], dtype=torch.int64).reshape(T, g.r)
    onehot = torch.zeros(T, g.n, dtype=torch.float32)
    if T:
        onehot.scatter_(1, draws - 1, 1.0)
    dates = [r["draw_date"] for r in records]
    step_index, step_offsets, step_dates = _steps(dates)
    onehot_d = onehot.to(device)
    out = {"draws": draws.to(device), "onehot": onehot_d, "step_index": step_index.to(device),
           "step_offsets": step_offsets.to(device), "pair_counts": onehot_d.T @ onehot_d, "dates": dates,
           "step_dates": step_dates, "joker": None, "joker_onehot": None, "cross_counts": None}
    if g.joker_m is not None:
        jk = torch.tensor([r["joker"] for r in records], dtype=torch.int64).reshape(T)
        jo = torch.zeros(T, g.joker_m, dtype=torch.float32)
        if T:
            jo.scatter_(1, (jk - 1)[:, None], 1.0)
        jo_d = jo.to(device)
        out.update(joker=jk.to(device), joker_onehot=jo_d, cross_counts=onehot_d.T @ jo_d)
    return out


# ---------------------------------------------------------------------------
# 6/49: adaptor de schemă → parser.build_dataset (§4)
# ---------------------------------------------------------------------------
_MAP_649 = (("draw_key", "draw_key"), ("draw_date", "draw_date"), ("game", "game"), ("provenance", "provenance"),
            ("numbers_sorted", "numbers"), ("numbers_as_stored", "numbers_order_as_stored"),
            ("draw_kind_as_stored", "draw_kind"), ("has_source_disagreement_as_stored", "has_source_disagreement"))


def adapt_649_bytes(raw: bytes) -> bytes:
    """Adaptor pur (fără filtrare), 1:1 pe linii: schema LIVE → schema parser.py. Liniile ne-JSON se copiază ca atare."""
    out = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            out.append("")
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        if not isinstance(obj, dict):
            out.append(line)
            continue
        out.append(json.dumps({dst: obj.get(src) for dst, src in _MAP_649}, ensure_ascii=False, sort_keys=True))
    return ("\n".join(out) + "\n").encode("utf-8") if out else b""


def adapt_649(src: Path, deriv_root: Path = DERIV) -> Path:
    src = Path(src)
    data = adapt_649_bytes(src.read_bytes())
    deriv_root = Path(deriv_root)
    deriv_root.mkdir(parents=True, exist_ok=True)
    dst = deriv_root / f"649_{sha256_file(src)[:12]}.jsonl"
    if dst.exists():
        if dst.read_bytes() != data:
            raise IntegrityError(f"fișier adaptat existent cu conținut diferit: {dst}")
        return dst
    fd, tmp = tempfile.mkstemp(prefix=".649_", dir=deriv_root)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(tmp, 0o444)
    os.replace(tmp, dst)
    return dst


# ---------------------------------------------------------------------------
# Ieșire (§5)
# ---------------------------------------------------------------------------
@dataclass
class GameDataset:
    game: GameSpec
    draws: torch.Tensor
    onehot: torch.Tensor
    joker: torch.Tensor | None
    joker_onehot: torch.Tensor | None
    step_index: torch.Tensor
    step_offsets: torch.Tensor
    pair_counts: torch.Tensor
    cross_counts: torch.Tensor | None
    dates: list[str]
    keys: list[str]
    kinds: list[str]
    step_dates: list[str]
    device: torch.device
    source: str
    source_sha256: str
    source_kind: str
    n_raw: int
    provenance: dict = field(default_factory=dict)
    anomalies: dict = field(default_factory=dict)
    json_errors: list = field(default_factory=list)
    base: object = None   # parser.Dataset la 6/49

    @property
    def n_draws(self) -> int:
        return int(self.draws.shape[0])

    @property
    def n_steps(self) -> int:
        return len(self.step_dates)

    def to(self, device) -> "GameDataset":
        d = torch.device(device)
        mv = lambda t: None if t is None else t.to(d)  # noqa: E731
        return GameDataset(self.game, mv(self.draws), mv(self.onehot), mv(self.joker), mv(self.joker_onehot),
                           mv(self.step_index), mv(self.step_offsets), mv(self.pair_counts), mv(self.cross_counts),
                           self.dates, self.keys, self.kinds, self.step_dates, d, self.source, self.source_sha256,
                           self.source_kind, self.n_raw, self.provenance, self.anomalies, self.json_errors,
                           None if self.base is None else self.base.to(d))

    def summary(self) -> dict:
        freq = self.onehot.sum(0)
        double_days = int(((self.step_offsets[1:] - self.step_offsets[:-1]) > 1).sum().item())
        s = {"game": self.game.code, "name": self.game.name, "n": self.game.n, "draw_size": self.game.r,
             "ticket": self.game.ticket, "joker_m": self.game.joker_m, "source_kind": self.source_kind,
             "source": self.source, "source_sha256": self.source_sha256, "n_raw": self.n_raw,
             "n_draws": self.n_draws, "n_steps": self.n_steps, "double_draw_days": double_days,
             "first_date": self.step_dates[0] if self.step_dates else None,
             "last_date": self.step_dates[-1] if self.step_dates else None,
             "removed_by_reason": self.anomalies.get("removed_by_reason", {}),
             "flags": len(self.anomalies.get("flags", [])), "kinds_kept": self.anomalies.get("kinds_kept", {}),
             "json_errors": len(self.json_errors),
             "freq_min": int(freq.min().item()) if self.n_draws else 0,
             "freq_max": int(freq.max().item()) if self.n_draws else 0,
             "device": str(self.device), "device_events": QP.device_events()}
        if self.joker is not None:
            jf = self.joker_onehot.sum(0)
            s.update(joker_freq_min=int(jf.min().item()) if self.n_draws else 0,
                     joker_freq_max=int(jf.max().item()) if self.n_draws else 0)
        return s


def _from_parser(g: GameSpec, base, source: Path, src_sha: str, kind: str, prov: dict) -> GameDataset:
    return GameDataset(g, base.draws, base.onehot, None, None, base.step_index, base.step_offsets, base.pair_counts,
                       None, base.dates, base.keys, base.kinds, base.step_dates, base.device, str(source), src_sha,
                       kind, base.n_raw, prov, base.anomalies, base.json_errors, base)


def build_game_dataset(game: str, source: str | Path = "live", device=None, live_root: Path = LIVE,
                       data_root: Path = DATA, deriv_root: Path = DERIV) -> GameDataset:
    """source: "live" (produs), "frozen" (referința protocoalelor sigilate) sau o cale explicită (schema LIVE)."""
    g = spec(game)
    dev = QP.resolve_device() if device is None else torch.device(device)
    if source == "live":
        path, prov = resolve_live(g.code, live_root)
        kind = "live"
    elif source == "frozen":
        path, prov = resolve_frozen(g.code, data_root)
        kind = "frozen"
    else:
        path, prov, kind = Path(source).resolve(), {"source_kind": "path"}, "path"
    src_sha = sha256_file(path)
    if g.code == "649":
        if kind == "frozen":
            base = QP.build_dataset(path, device=dev)
        else:
            adapted = adapt_649(path, deriv_root)
            prov = dict(prov, adapted_path=str(adapted), adapted_sha256=sha256_file(adapted))
            base = QP.build_dataset(adapted, device=dev)
        return _from_parser(g, base, path, src_sha, kind, prov)
    records, json_errors = QP.load_records(path)
    clean, anomalies = clean_records(g, records)
    t = build_tensors(g, clean, dev)
    return GameDataset(g, t["draws"], t["onehot"], t["joker"], t["joker_onehot"], t["step_index"],
                       t["step_offsets"], t["pair_counts"], t["cross_counts"], t["dates"],
                       [r["draw_key"] for r in clean], [str(r.get("draw_kind")) for r in clean], t["step_dates"],
                       dev, str(path), src_sha, kind, len(records) + len(json_errors), prov, anomalies, json_errors)


# ---------------------------------------------------------------------------
# Raport înghețat ↔ LIVE (P7) și manifest
# ---------------------------------------------------------------------------
def _key_map(ds: GameDataset) -> dict[str, tuple]:
    jk = [None] * ds.n_draws if ds.joker is None else ds.joker.cpu().tolist()
    return {k: (d, tuple(x), j) for k, d, x, j in zip(ds.keys, ds.dates, ds.draws.cpu().tolist(), jk)}


def compare_frozen_live(frozen: GameDataset, live: GameDataset) -> dict:
    """Descriptiv (inventar): chei numai în înghețat, numai în LIVE, și chei comune cu dată/numere/Joker diferite."""
    fm, lm = _key_map(frozen), _key_map(live)
    only_f = sorted(set(fm) - set(lm))
    only_l = sorted(set(lm) - set(fm))
    diff = sorted(k for k in set(fm) & set(lm) if fm[k] != lm[k])
    return {"frozen_records": len(fm), "live_records": len(lm), "common_keys": len(set(fm) & set(lm)),
            "only_in_frozen": only_f, "only_in_live": only_l, "differing_on_common_keys": diff,
            "live_superset_of_frozen": not only_f and not diff}


def write_manifest(out_dir: Path = OUT, device=None) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = out_dir / f"MANIFEST_P_{stamp}.json"
    if dst.exists():
        raise FileExistsError(f"refuz suprascrierea {dst}")
    payload = {"protocol": "TU3-P", "protocol_sha256": sha256_file(HERE / "PROTOCOL_TU3_P.md"),
               "generated_utc": stamp, "code_sha256": sha256_file(Path(__file__)),
               "engine_sha256": sha256_file(QL / "engine.py"), "parser_sha256": sha256_file(QL / "parser.py"),
               "note": "Inventar, nu experiment de selecție. Nicio prognoză, niciun scor; OGLINDA neatinsă. "
                       "positive_claims_allowed=false.", "positive_claims_allowed": False, "games": {}}
    for game in GAMES:
        live = build_game_dataset(game, "live", device=device)
        frozen = build_game_dataset(game, "frozen", device=device)
        payload["games"][game] = {"live": dict(live.summary(), provenance=live.provenance,
                                               removed=live.anomalies["removed"]),
                                  "frozen": dict(frozen.summary(), provenance=frozen.provenance,
                                                 removed=frozen.anomalies["removed"]),
                                  "frozen_vs_live": compare_frozen_live(frozen, live)}
    with open(dst, "x", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    os.chmod(dst, 0o444)
    return dst


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stare", action="store_true", help="rezumatul arhivei LIVE pentru toate 3 jocurile")
    ap.add_argument("--manifest", action="store_true", help="scrie rezultate/P/MANIFEST_P_<UTC>.json (fișier nou)")
    ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args(argv)
    dev = "cpu" if a.cpu else None
    if a.manifest:
        print(write_manifest(device=dev))
        return 0
    for game in GAMES:
        s = build_game_dataset(game, "live", device=dev).summary()
        print(f"{s['game']:>5} {s['name']:<10} extrageri={s['n_draws']} pași={s['n_steps']} "
              f"{s['first_date']}…{s['last_date']} excluse={sum(s['removed_by_reason'].values())} "
              f"device={s['device']} sha={s['source_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
