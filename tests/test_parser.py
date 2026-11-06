"""Teste parser QL649 (PREINREGISTRARE §1, §6)."""
import json
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import parser as qp  # noqa: E402


def _row(date, nums, key=None, **extra):
    r = {"draw_date": date, "numbers_sorted": sorted(nums) if all(isinstance(x, int) for x in nums) else nums,
         "numbers_as_stored": list(nums), "draw_key": key or f"649:{date}:{'-'.join(map(str, nums))}",
         "draw_kind_as_stored": "regular", "has_source_disagreement_as_stored": False}
    r.update(extra)
    return r


def _write(tmp_path, rows, extra_lines=()):
    p = tmp_path / "x.jsonl"
    lines = [json.dumps(r) for r in rows] + list(extra_lines)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_invalid_rows_refused(tmp_path):
    rows = [
        _row("2020-01-02", [1, 2, 3, 4, 5, 6]),
        _row("2020-01-03", [0, 2, 3, 4, 5, 6]),
        _row("2020-01-04", [1, 2, 3, 4, 5, 50]),
        {"draw_date": "2020-01-05", "numbers_sorted": [1, 1, 3, 4, 5, 6], "draw_key": "k5"},
        {"numbers_sorted": [1, 2, 3, 4, 5, 6], "draw_key": "k6"},
        {"draw_date": "2020-13-40", "numbers_sorted": [1, 2, 3, 4, 5, 6], "draw_key": "k7"},
        {"draw_date": "2020-01-08", "numbers_sorted": [1, 2, 3, 4, 5], "draw_key": "k8"},
        {"draw_date": "2020-01-09", "numbers_sorted": [1, 2, 3, 4, 5, 6.0], "draw_key": "k9"},
        {"draw_date": "2020-01-10", "numbers_sorted": [True, 2, 3, 4, 5, 6], "draw_key": "k10"},
        {"draw_date": "2020-01-11", "numbers_sorted": [1, 2, 3, 4, 5, 6]},
    ]
    ds = qp.build_dataset(_write(tmp_path, rows, ["{not json", "[1,2]"]), device="cpu")
    assert ds.n_draws == 1
    assert ds.n_raw == 12
    r = ds.anomalies["removed_by_reason"]
    assert r == {"numbers_out_of_range": 2, "numbers_duplicate_in_row": 1, "draw_date_missing": 1,
                 "draw_date_invalid": 1, "numbers_count_invalid": 1, "numbers_not_int": 2, "draw_key_missing": 1}
    assert len(ds.json_errors) == 2


def test_dedup_sort_and_steps(tmp_path):
    rows = [
        _row("2020-01-05", [7, 8, 9, 10, 11, 12]),
        _row("2020-01-02", [1, 2, 3, 4, 5, 6]),
        _row("2020-01-05", [13, 14, 15, 16, 17, 18]),
        _row("2020-01-02", [1, 2, 3, 4, 5, 6]),                       # duplicate key
        _row("2020-01-05", [12, 11, 10, 9, 8, 7], key="other"),        # duplicate (date,set)
        _row("2020-01-03", [44, 45, 46, 47, 48, 49], has_source_disagreement_as_stored=True),
    ]
    ds = qp.build_dataset(_write(tmp_path, rows), device="cpu")
    assert ds.n_draws == 4
    assert ds.anomalies["removed_by_reason"] == {"duplicate_draw_key": 1, "duplicate_date_set": 1}
    assert ds.dates == sorted(ds.dates)
    assert ds.step_dates == ["2020-01-02", "2020-01-03", "2020-01-05"]
    assert ds.step_index.tolist() == [0, 1, 2, 2]
    assert ds.step_offsets.tolist() == [0, 1, 2, 4]
    assert ds.summary()["double_draw_days"] == 1
    assert any(f["flag"] == "source_disagreement_kept" for f in ds.anomalies["flags"])
    assert torch.equal(ds.onehot.sum(1), torch.full((4,), 6.0))
    assert torch.equal(torch.diagonal(ds.pair_counts), ds.onehot.sum(0))


def test_real_dataset_invariants():
    ds = qp.build_dataset(device="cpu")
    s = ds.summary()
    assert s["n_raw"] == 2595
    assert s["n_draws"] == s["n_raw"] - sum(s["removed_by_reason"].values())
    assert s["json_errors"] == 0
    assert ds.draws.min() >= 1 and ds.draws.max() <= 49
    assert (ds.draws[:, 1:] > ds.draws[:, :-1]).all()
    assert ds.dates == sorted(ds.dates)
    assert len(set(ds.keys)) == ds.n_draws
    assert int(ds.step_offsets[-1]) == ds.n_draws and ds.n_steps == len(set(ds.dates))
    assert int(ds.onehot.sum()) == 6 * ds.n_draws
    pc = ds.pair_counts
    assert torch.equal(pc, pc.T)
    assert float((pc.sum() - torch.diagonal(pc).sum()) / 2) == 15 * ds.n_draws
    assert not s["kinds_kept"] == {}
    assert ds.anomalies["physical_order_used"] is False


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA absent")
def test_cpu_gpu_parity_exact():
    cpu = qp.build_dataset(device="cpu")
    gpu = qp.build_dataset(device="cuda")
    assert gpu.draws.is_cuda and gpu.onehot.is_cuda and gpu.pair_counts.is_cuda
    for a, b in [(cpu.draws, gpu.draws), (cpu.onehot, gpu.onehot), (cpu.step_index, gpu.step_index),
                 (cpu.step_offsets, gpu.step_offsets), (cpu.pair_counts, gpu.pair_counts)]:
        assert torch.equal(a, b.cpu())
    assert cpu.source_sha256 == gpu.source_sha256


def test_resolve_device_default_and_cpu():
    assert qp.resolve_device("cpu").type == "cpu"
    d = qp.resolve_device()
    assert d.type == ("cuda" if torch.cuda.is_available() else "cpu")
