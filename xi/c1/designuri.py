#!/usr/bin/env python3
"""XI-C1 §3 — designurile constructive J180 și J140 (Joker) și scrierea fișierelor de design.

Format design (JSON): {"game": "joker"|"649", "name": ..., "n_tickets": N, "tickets": [[...], ...], "sha256_tickets"}
Joker: fiecare bilet = 5 numere 1..45 crescătoare + Joker 1..20 (ultimul element). 6/49: 6 numere 1..49 crescătoare.
positive_claims_allowed=false. Calcul clasic.
"""
from __future__ import annotations

import hashlib
import json
import os
from itertools import combinations
from pathlib import Path

XI = Path(__file__).resolve().parents[1]
DESIGNS = XI / "rezultate" / "C1" / "designuri"


def blocks():
    return [list(range(5 * i - 4, 5 * i + 1)) for i in range(1, 10)]


def j180():
    return [b + [j] for j in range(1, 21) for b in blocks()]


def j140_pairs():
    return list(combinations(range(1, 10), 2))[:20]


def j140():
    B = blocks()
    out = []
    for j, (a, b) in enumerate(j140_pairs(), start=1):
        out += [B[i - 1] + [j] for i in range(1, 10) if i not in (a, b)]
    return out


def canon(game: str, tickets) -> list[list[int]]:
    if game == "joker":
        t = [sorted(int(x) for x in tk[:5]) + [int(tk[5])] for tk in tickets]
    else:
        t = [sorted(int(x) for x in tk) for tk in tickets]
    return sorted(t)


def tickets_sha(tickets) -> str:
    return hashlib.sha256(json.dumps(tickets, separators=(",", ":")).encode()).hexdigest()


def write_design(game: str, name: str, tickets, meta: dict | None = None) -> Path:
    t = canon(game, tickets)
    doc = {"game": game, "name": name, "n_tickets": len(t), "tickets": t, "sha256_tickets": tickets_sha(t),
           **(meta or {}), "positive_claims_allowed": False}
    DESIGNS.mkdir(parents=True, exist_ok=True)
    f = DESIGNS / f"{name}.json"
    if f.exists():
        old = json.loads(f.read_text())
        assert old["sha256_tickets"] == doc["sha256_tickets"], f"refuz suprascrierea diferită: {f}"
        return f
    f.write_text(json.dumps(doc, indent=1) + "\n")
    os.chmod(f, 0o444)
    return f


if __name__ == "__main__":
    for name, t in (("J180", j180()), ("J140", j140())):
        f = write_design("joker", name, t, {"constructie": "XI-C1 §3"})
        print(name, len(t), f, hashlib.sha256(f.read_bytes()).hexdigest())
