"""Teste de inginerie SE649 (nu sunt teste predictive). Rulare: ../.venv/bin/python -m pytest -q tests/"""
from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import se649 as S  # noqa: E402


def test_season_mapping():
    exp = {1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3, 11: 3, 12: 0}
    for m, f in exp.items():
        assert S.season_of(f"2001-{m:02d}-15") == f


def test_closed_form_equals_direct_and_sum6():
    ns = [37, 0, 52, 11]
    for phi in range(4):
        assert S.se_weights(ns, phi) == S.se_weights_direct(ns, phi)
        assert sum(S.se_weights(ns, phi).values()) < 1
    C4 = [[0] * 49 for _ in range(4)]
    for f in range(4):
        for i in range(ns[f]):
            for t in range(6):
                C4[f][(7 * i + 11 * t + f) % 49] += 1
    r = S.se_predict_counts(C4, ns, 1)
    assert sum(r["p"]) == 6 and all(0 < x < 1 for x in r["p"])


def test_q5_closed_form_gap():
    steps, dates = S.block_history(S.fixture_F5())
    r = S.predict_at(steps, dates, S.TARGET_WINTER)
    D = S.TB2 + S.SIGMA0_2 / 49
    assert r["p"][4] - r["p"][8] == 6 * S.TB2 / (49 * D)
    assert all(r["p"][j] == S.P0 for j in range(49) if j not in (4, 8))


def test_q6_tickets():
    steps, dates = S.block_history(S.fixture_F6())
    r = S.predict_at(steps, dates, S.TARGET_WINTER)
    assert r["ticket_SE"] == [44, 45, 46, 47, 48, 49] and r["ticket_B"] == [1, 2, 3, 4, 5, 6]
    assert r["ticket_R"] != r["ticket_SE"]


def test_ticket_tie_rule():
    p = [Fraction(6, 49)] * 49
    assert S.ticket_exact(p) == [1, 2, 3, 4, 5, 6]


def test_protocol_seal_and_real_refuses_repeat():
    seal = json.loads(S.SEAL.read_text())
    assert S.sha256_file(S.PROTO) == seal["sha256"]
    if (S.OUT / "backtest_unic" / "START.json").exists():
        assert S.run_real() == 2
