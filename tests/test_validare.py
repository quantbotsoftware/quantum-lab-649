"""Teste validare QL649 — numai date sintetice (nu ating istoria reală)."""
import json
import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine as E  # noqa: E402
import validare as V  # noqa: E402

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
FAST = replace(E.PROTOCOL, mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60, gamma_grid=12)


def test_marginal_q_bounds_and_uniform():
    rng = np.random.default_rng(0)
    pi = rng.dirichlet(np.ones(49) * 0.05, size=200)
    q = V.marginal_q(pi)
    assert np.allclose(q.sum(-1), 6.0)
    assert (q >= 1e-4 - 1e-12).all() and (q <= 1 - 1e-4 + 1e-12).all()
    qu = V.marginal_q(np.full((1, 49), 1 / 49))
    assert np.allclose(qu, 6 / 49)


def test_uniform_brier_and_log_reference():
    y = np.zeros((1, 49))
    y[0, :6] = 1
    s = V.score_block(np.full((1, 49), 6 / 49), np.array([[1, 2, 3, 4, 5, 6]]), y)
    assert abs(s["brier"][0] - 6 * 43 / 49) < 1e-12
    assert abs(s["log"][0] - (6 * math.log(6 / 49) + 43 * math.log(43 / 49))) < 1e-12
    assert s["hits"][0] == 6


def test_top6_ties_smaller_number():
    pi = np.full((1, 49), 1 / 49)
    assert V.top6(pi).tolist() == [[1, 2, 3, 4, 5, 6]]
    pi2 = pi.copy()
    pi2[0, 40] += 0.1
    assert V.top6(pi2).tolist() == [[1, 2, 3, 4, 5, 41]]


def test_exact_tail():
    assert abs(V.exact_tail(0, 3) - 1.0) < 1e-12
    assert abs(V.exact_tail(6, 1) - 1 / math.comb(49, 6)) < 1e-18
    pmf = V.hyper_pmf()
    assert abs(pmf.sum() - 1) < 1e-12 and abs((pmf * np.arange(7)).sum() - 36 / 49) < 1e-12


def test_gates_logic():
    base = {"hits_QL": 10, "hits_B": 5, "hits_R": 5, "excess_QL": 0.3, "log_QL": 0, "log_U": -1, "log_B": -1,
            "brier_QL": 1, "brier_U": 2, "brier_B": 2, "brier_R": 2}
    res = {"total": dict(base), "half1": dict(base), "half2": dict(base)}
    assert all(g["pass"] for g in V.gates(res))
    res["half2"] = dict(base, log_QL=-5)
    gs = V.gates(res)
    assert [g["pass"] for g in gs] == [True, True, True, True, True, False]


def test_sci_raw_small_known():
    # 3 pași: {1..6}, {1..6}+{7..12} (zi dublă), {1,7,13..16}
    draws = [[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12], [1, 7, 13, 14, 15, 16]]
    oh = torch.zeros(1, 4, 49)
    for i, d in enumerate(draws):
        oh[0, i, torch.tensor(d) - 1] = 1
    sidx = torch.tensor([0, 1, 1, 2])
    sizes = torch.tensor([1, 2, 1])
    r = V.sci_raw(oh, sidx, sizes, 3)
    # suprapunere: pas0→pas1: (6 + 0)/(1·2) = 3 ; pas1→pas2: (1·1 [nr 1] + 1·1 [nr 7])/(2·1) = 1 → medie 2
    assert abs(float(r["overlap"][0]) - 2.0) < 1e-12
    h = r["gap_hist"][0]
    assert float(h[0, 0]) == 2 and float(h[0, 1]) == 0          # nr 1: pașii 0,1,2 → două goluri de 1 pas
    assert float(h[6, 0]) == 1                                   # nr 7: pașii 1,2 → un gol de 1 pas
    assert float(h.sum()) == 6 + 1 + 1                           # 1..6 la pas1 (gol 1), 1 la pas2, 7 la pas2


def test_synthetic_pipeline_end_to_end(tmp_path):
    ds = V.synthetic_dataset(tmp_path / "s.jsonl", n=160, device=DEV)
    out = tmp_path / "run"
    r = V.run_backtest(ds, out, FAST, warmup=40, m_null=256, log=lambda *_: None)
    res = r["res"]
    files = {p.name for p in out.iterdir()}
    assert {"START.json", "PREDICTII.npz", "PREDICTII_SIGILIU.json", "REZULTATE.json", "SCI.json", "MANIFEST.json"} <= files
    man = json.loads((out / "MANIFEST.json").read_text())
    assert man["PREDICTII.npz"] == res["predictions_sha256"]
    assert res["verdict"] in ("QL_PROMOVAT_EXPLORATORIU", "QL_NO_PROMOTION_EXPLORATORY")
    assert res["gates_passed"] == sum(g["pass"] for g in res["gates"])
    t = res["total"]
    assert t["targets"] == res["half1"]["targets"] + res["half2"]["targets"]
    assert t["hits_QL"] == sum(res["per_target"]["hits_QL"])
    assert res["start"]["is_protocol"] is False
    assert 0 < r["sci"]["p_empirical"] <= 1
    P = np.load(out / "PREDICTII.npz")
    v = P["variants"]
    assert v.shape[1:] == (3, 6) and (np.diff(v, axis=-1) > 0).all() and v.min() >= 1 and v.max() <= 49


def test_predictions_causal_under_future_tampering(tmp_path):
    p1 = tmp_path / "a.jsonl"
    ds1 = V.synthetic_dataset(p1, n=120, seed=5, device=DEV)
    rows = [json.loads(l) for l in p1.read_text().splitlines()]
    k = 70
    cut = ds1.step_dates[k]
    rng = np.random.default_rng(99)
    for r in rows:
        if r["draw_date"] >= cut:
            nums = sorted(int(x) + 1 for x in rng.choice(49, 6, replace=False))
            r["numbers_sorted"] = r["numbers_as_stored"] = nums
            r["draw_key"] = f"t:{r['draw_date']}:{'-'.join(map(str, nums))}"
    p2 = tmp_path / "b.jsonl"
    p2.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    ds2 = V.build_dataset(p2, DEV)
    a = V.predict_all(ds1, FAST, warmup=60, log=lambda *_: None)
    b = V.predict_all(ds2, FAST, warmup=60, log=lambda *_: None)
    i = k - 60
    assert np.allclose(a["pi_QL"][: i + 1], b["pi_QL"][: i + 1], atol=1e-12, rtol=0)
    assert (a["variants"][: i + 1] == b["variants"][: i + 1]).all()
    assert np.allclose(a["piB"][: i + 1], b["piB"][: i + 1])
