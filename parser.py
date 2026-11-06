"""QL649 — STEP 1: ingestia semnalului topologic (parser.py).

Încarcă `extrageri_649.jsonl` integral în RAM, validează schema, elimină
anomaliile și duplicatele (cu motiv explicit), ordonează cronologic, grupează
extragerile pe pași de timp (o zi calendaristică = un pas; ordinea din aceeași zi
este necunoscută și nu se inventează) și construiește tensori PyTorch pe `cuda`
(fallback silențios pe CPU numai la eroare de driver/CUDA).

Protocol: PREINREGISTRARE_QL649.md §1 (sigilat în SIGILIU_PROTOCOL.json).
Inventarul datelor nu este experiment de selecție; parserul nu calculează operatori.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import torch

LOG = logging.getLogger("ql649.parser")
ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = Path(os.environ.get("QL649_DATA_649", str(ROOT / "data" / "extrageri_649.jsonl"))).resolve()
N_NUMBERS = 49
K_DRAWN = 6

_DEVICE_EVENTS: list[str] = []


def resolve_device(prefer: str = "cuda") -> torch.device:
    """GPU implicit; CPU numai dacă CUDA lipsește sau driverul eșuează (eveniment jurnalizat)."""
    if prefer == "cpu":
        return torch.device("cpu")
    try:
        if not torch.cuda.is_available():
            raise RuntimeError("torch.cuda.is_available() == False")
        dev = torch.device("cuda")
        probe = torch.ones(8, device=dev)
        torch.cuda.synchronize()
        if float(probe.sum().item()) != 8.0:
            raise RuntimeError("CUDA probe mismatch")
        return dev
    except Exception as exc:  # fallback silențios, dar jurnalizat
        msg = f"CUDA indisponibil, fallback CPU: {type(exc).__name__}: {exc}"
        _DEVICE_EVENTS.append(msg)
        LOG.warning(msg)
        return torch.device("cpu")


def device_events() -> list[str]:
    return list(_DEVICE_EVENTS)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_records(path: Path) -> tuple[list[dict], list[dict]]:
    """Citește tot fișierul în RAM. Întoarce (înregistrări, erori de parsare JSON)."""
    raw = Path(path).read_bytes().decode("utf-8")
    records, errors = [], []
    for lineno, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({"line": lineno, "reason": f"json_invalid: {exc.msg}"})
            continue
        if not isinstance(obj, dict):
            errors.append({"line": lineno, "reason": "json_not_object"})
            continue
        obj["_line"] = lineno
        records.append(obj)
    return records, errors


def _validate(rec: dict) -> str | None:
    """Motivul invalidității sau None dacă rândul este valid (PREINREGISTRARE §1)."""
    key = rec.get("draw_key")
    if not isinstance(key, str) or not key:
        return "draw_key_missing"
    date = rec.get("draw_date")
    if not isinstance(date, str):
        return "draw_date_missing"
    try:
        _dt.date.fromisoformat(date)
    except ValueError:
        return "draw_date_invalid"
    nums = rec.get("numbers_sorted")
    if not isinstance(nums, list) or len(nums) != K_DRAWN:
        return "numbers_count_invalid"
    if any(isinstance(x, bool) or not isinstance(x, int) for x in nums):
        return "numbers_not_int"
    if any(x < 1 or x > N_NUMBERS for x in nums):
        return "numbers_out_of_range"
    if len(set(nums)) != K_DRAWN:
        return "numbers_duplicate_in_row"
    return None


def clean_records(records: list[dict]) -> tuple[list[dict], dict]:
    """Validare, deduplicare, sortare cronologică stabilă. Fiecare eliminare are motiv."""
    removed, flags = [], []
    valid = []
    for rec in records:
        reason = _validate(rec)
        if reason:
            removed.append({"line": rec.get("_line"), "draw_key": rec.get("draw_key"), "reason": reason})
            continue
        valid.append(rec)
    seen_keys, seen_sets, unique = set(), set(), []
    for rec in valid:
        nums = tuple(sorted(rec["numbers_sorted"]))
        if rec["draw_key"] in seen_keys:
            removed.append({"line": rec["_line"], "draw_key": rec["draw_key"], "reason": "duplicate_draw_key"})
            continue
        sk = (rec["draw_date"], nums)
        if sk in seen_sets:
            removed.append({"line": rec["_line"], "draw_key": rec["draw_key"], "reason": "duplicate_date_set"})
            continue
        seen_keys.add(rec["draw_key"])
        seen_sets.add(sk)
        stored = rec.get("numbers_as_stored")
        if isinstance(stored, list) and sorted(stored) != list(nums):
            flags.append({"draw_key": rec["draw_key"], "flag": "stored_vs_sorted_mismatch"})
        if rec.get("has_source_disagreement_as_stored"):
            flags.append({"draw_key": rec["draw_key"], "flag": "source_disagreement_kept"})
        unique.append(rec)
    unique.sort(key=lambda r: (r["draw_date"], r["draw_key"]))  # stabil
    reasons: dict[str, int] = {}
    for r in removed:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    kinds: dict[str, int] = {}
    for r in unique:
        k = str(r.get("draw_kind_as_stored"))
        kinds[k] = kinds.get(k, 0) + 1
    anomalies = {
        "removed": removed,
        "removed_by_reason": reasons,
        "flags": flags,
        "kinds_kept": kinds,
        "physical_order_used": False,
        "within_day_order_used": False,
    }
    return unique, anomalies


@dataclass
class Dataset:
    draws: torch.Tensor          # [N,6] int64, numere 1..49 sortate
    onehot: torch.Tensor         # [N,49] float32
    step_index: torch.Tensor     # [N] int64, pasul de timp (zi) al fiecărei extrageri
    step_offsets: torch.Tensor   # [S+1] int64, CSR: extragerile pasului s sunt [off[s], off[s+1])
    pair_counts: torch.Tensor    # [49,49] float32, co-apariții pe toată istoria, diag = frecvențe
    dates: list[str]
    keys: list[str]
    kinds: list[str]
    step_dates: list[str]
    device: torch.device
    source: str
    source_sha256: str
    n_raw: int
    anomalies: dict = field(default_factory=dict)
    json_errors: list = field(default_factory=list)

    @property
    def n_draws(self) -> int:
        return int(self.draws.shape[0])

    @property
    def n_steps(self) -> int:
        return len(self.step_dates)

    def to(self, device: torch.device) -> "Dataset":
        d = torch.device(device)
        return Dataset(self.draws.to(d), self.onehot.to(d), self.step_index.to(d), self.step_offsets.to(d),
                       self.pair_counts.to(d), self.dates, self.keys, self.kinds, self.step_dates, d,
                       self.source, self.source_sha256, self.n_raw, self.anomalies, self.json_errors)

    def summary(self) -> dict:
        freq = self.onehot.sum(0)
        double_days = int(((self.step_offsets[1:] - self.step_offsets[:-1]) > 1).sum().item())
        return {
            "source": self.source,
            "source_sha256": self.source_sha256,
            "n_raw": self.n_raw,
            "n_draws": self.n_draws,
            "n_steps": self.n_steps,
            "double_draw_days": double_days,
            "first_date": self.step_dates[0] if self.step_dates else None,
            "last_date": self.step_dates[-1] if self.step_dates else None,
            "removed_by_reason": self.anomalies.get("removed_by_reason", {}),
            "flags": len(self.anomalies.get("flags", [])),
            "kinds_kept": self.anomalies.get("kinds_kept", {}),
            "json_errors": len(self.json_errors),
            "freq_min": int(freq.min().item()) if self.n_draws else 0,
            "freq_max": int(freq.max().item()) if self.n_draws else 0,
            "device": str(self.device),
            "device_events": device_events(),
        }


def build_tensors(records: list[dict], device: torch.device):
    n = len(records)
    draws = torch.tensor([sorted(r["numbers_sorted"]) for r in records], dtype=torch.int64).reshape(n, K_DRAWN)
    onehot = torch.zeros(n, N_NUMBERS, dtype=torch.float32)
    if n:
        onehot.scatter_(1, draws - 1, 1.0)
    dates = [r["draw_date"] for r in records]
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
    step_offsets = torch.tensor(offsets, dtype=torch.int64)
    onehot_d = onehot.to(device)
    pair_counts = onehot_d.T @ onehot_d
    return (draws.to(device), onehot_d, step_index.to(device), step_offsets.to(device), pair_counts,
            dates, step_dates)


def build_dataset(path: Path | str = DEFAULT_SOURCE, device: torch.device | str | None = None) -> Dataset:
    path = Path(path).resolve()
    dev = resolve_device() if device is None else torch.device(device)
    records, json_errors = load_records(path)
    clean, anomalies = clean_records(records)
    draws, onehot, step_index, step_offsets, pair_counts, dates, step_dates = build_tensors(clean, dev)
    return Dataset(
        draws=draws, onehot=onehot, step_index=step_index, step_offsets=step_offsets, pair_counts=pair_counts,
        dates=dates, keys=[r["draw_key"] for r in clean], kinds=[str(r.get("draw_kind_as_stored")) for r in clean],
        step_dates=step_dates, device=dev, source=str(path), source_sha256=sha256_file(path), n_raw=len(records) + len(json_errors),
        anomalies=anomalies, json_errors=json_errors,
    )


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    src = Path(argv[1]) if len(argv) > 1 else DEFAULT_SOURCE
    ds = build_dataset(src)
    summ = ds.summary()
    out = ROOT / "rezultate" / "parser_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(summ, generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
                   removed=ds.anomalies["removed"], flag_list=ds.anomalies["flags"])
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summ, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
