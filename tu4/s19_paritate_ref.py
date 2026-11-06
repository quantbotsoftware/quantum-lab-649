"""TU4-S19: referința de paritate Rust ↔ Python ÎNGHEȚAT (protocol tu4/PROTOCOL_SUPERQUANTUM_S19.md §2).

Protocol: tu4/PROTOCOL_SUPERQUANTUM_S19.md (8c27d81f…), sigiliu tu4/SIGILIU_TU4_S19.json (01:10:47Z), scrise ÎNAINTE de
acest cod. Fișier NOU: nu modifică ip_core.py / emite.py / s16_martori.py / emisiile / arhiva. Importă `ip_core` și
`s16_martori` numai după verificarea sha-urilor. Calcul clasic pe CPU, torch.float64 / NumPy (fără compilare, fără GPU).
Fiecare float este scris în zecimal ȘI în hex (`float.hex()`), pentru comparația bit-cu-bit în Rust.
Nu emite, nu decontează, nu produce bilete. positive_claims_allowed = false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import random
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent            # tu4/
ROOT = HERE.parent                                # quantum_lab_649/
OUT_DIR = HERE / "rezultate" / "S19"
IP_SHA = "ab3e1de93d8e5ae537a8c80599905aaa19cc103602f9b18f4b7f7f6f8a48c302"
S16_SHA = "298d3ec69af61361664b760a05af95c065d20a1248272fb1ea640c9ef5ce9df8"
S17_FILE = HERE / "rezultate" / "S17" / "BILETE_ADMISIBILE_20261028T001924Z.json"
S17_SHA = "6e9afe943dd93a4cfb53cdefaf28ceec22def7be8b6b876cf2d3c969614b2ad0"
EM_SHA = {"649": "e2fe385ecad12ac85cb870f9301ee64eee4ac1f78696656c32dd4278ddcb1947",
          "540": "a15dc8fdbad6c165cf45ce5290790120ecdd0a2e752a370bcbf45869e2e06098",
          "joker": "092e3f5c610a7b000e47467d572558d8b6bb45cf94b6b6315333312e64990a74"}
TARGET = "2026-10-29"
A_GRID = (0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 1.9)
N_FRFT = (20, 40, 45, 49)
GAMES = {"649": (49, 6), "540": (40, 6), "joker": (45, 5)}
NB = 20


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_frozen(path: Path, sha: str, name: str):
    got = sha_file(path)
    if got != sha:
        raise RuntimeError(f"{path.name} sha {got} != {sha}")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arr(a) -> dict:
    v = np.asarray(a, dtype=np.float64).ravel()
    return {"dec": [float(x) for x in v], "hex": [float(x).hex() for x in v]}


# ------------------------------------------------------------------ fixturile (protocol §2)
def fx_uniform(seed: int, n: int, k: int, T: int, ball: bool = False):
    rng = random.Random(seed)
    main, balls = [], []
    for _ in range(T):
        main.append(sorted(rng.sample(range(1, n + 1), k)))
        if ball:
            balls.append([rng.randint(1, NB)])
    return main, balls


def fx_weighted(seed: int, n: int, k: int, T: int):
    rng = random.Random(seed)
    w = [1.0 + 0.35 * math.cos(2.0 * math.pi * (i - 0.5) / n) for i in range(1, n + 1)]
    draws = []
    for _ in range(T):
        avail = list(range(1, n + 1))
        d = []
        for _ in range(k):
            tot = sum(w[i - 1] for i in avail)
            u = rng.random() * tot
            acc = 0.0
            pick = avail[-1]
            for i in avail:
                acc += w[i - 1]
                if u < acc:
                    pick = i
                    break
            d.append(pick)
            avail.remove(pick)
        draws.append(sorted(d))
    return draws


def fixtures() -> list[dict]:
    out = []
    m, _ = fx_uniform(20261028, 49, 6, 2595)
    out.append(dict(name="FX1", n=49, k=6, draws=m))
    m, _ = fx_uniform(20261029, 40, 6, 2490)
    out.append(dict(name="FX2", n=40, k=6, draws=m))
    m, b = fx_uniform(20261030, 45, 5, 2202, ball=True)
    out.append(dict(name="FX3", n=45, k=5, draws=m))
    out.append(dict(name="FX3_BILA", n=NB, k=1, draws=b))
    out.append(dict(name="FX4", n=49, k=6, draws=fx_weighted(20261031, 49, 6, 3000)))
    out.append(dict(name="FX5", n=5, k=2, draws=[[1, 2], [1, 3], [1, 4], [2, 3]]))
    full = []

    def rec(start, cur):
        if len(cur) == 3:
            full.append(list(cur))
            return
        for x in range(start, 7):
            rec(x + 1, cur + [x])
    rec(1, [])
    out.append(dict(name="FX6", n=6, k=3, draws=full))
    out.append(dict(name="FX7", n=20, k=1, draws=[[l] for l in range(1, 21) for _ in range(60 - 2 * l)]))
    return out


# ------------------------------------------------------------------ arhiva reală (ca emite.load_live, read-only)
def real_cases() -> list[dict]:
    live = ROOT / "tu3" / "date" / "live"
    cur_b = (live / "CURRENT_LIVE.json").read_bytes()
    cur = json.loads(cur_b)
    vdir = live / cur["version_dir"]
    man = json.loads((vdir / "MANIFEST_LIVE.json").read_bytes())
    if man.get("database_sha256") != cur.get("database_sha256"):
        raise RuntimeError("database_sha256 diferit între CURRENT_LIVE și manifest")
    out = []
    for g, (n, k) in GAMES.items():
        gm, gc = man["games"][g], cur["games"][g]
        fpath = vdir / gm["file"]
        fb = fpath.read_bytes()
        fsha = hashlib.sha256(fb).hexdigest()
        if not (fsha == gm["sha256"] == gc["sha256"]):
            raise RuntimeError(f"sha arhivă {g}")
        rows = [json.loads(x) for x in fb.decode("utf-8").splitlines() if x.strip()]
        if len(rows) != gm["records"] or len(rows) != gc["records"]:
            raise RuntimeError(f"număr de înregistrări {g}")
        main, balls = [], []
        for r in rows:
            nums = r["numbers"]
            if len(nums) != k or len(set(nums)) != k or not all(1 <= x <= n for x in nums):
                raise RuntimeError(f"extragere invalidă {r.get('draw_key')}")
            main.append(sorted(int(x) for x in nums))
            if g == "joker":
                j = int(r["joker"])
                if not 1 <= j <= NB:
                    raise RuntimeError("bilă invalidă")
                balls.append([j])
        src = {"file": str(fpath.relative_to(ROOT)), "sha256": fsha, "records": len(rows),
               "last_key": gm["last_key"], "last_date": gm["last_date"], "version_dir": cur["version_dir"],
               "current_live_sha256": hashlib.sha256(cur_b).hexdigest()}
        out.append(dict(name=f"REAL_{g.upper()}", n=n, k=k, draws=main, game=g, urn="main", source=src))
        if g == "joker":
            out.append(dict(name="REAL_JOKER_BILA", n=NB, k=1, draws=balls, game=g, urn="ball", source=src))
    return out


# ------------------------------------------------------------------ mărimile de referință
def inclusion(C, logw: np.ndarray, k: int) -> np.ndarray:
    """Copiată literal din `emite.inclusion` (folosește `ip_core.esp` înghețat)."""
    lw = torch.as_tensor(logw, dtype=C.DT)[None]
    w = torch.exp(lw)
    e = C.esp(w, k)
    em = torch.ones_like(w)
    for j in range(1, k):
        em = e[..., j:j + 1] - w * em
    return (w * em / e[..., k:k + 1])[0].numpy()


def pair_inclusion(C, logw: np.ndarray, k: int, pi: np.ndarray) -> np.ndarray:
    """Π_ij = w_i w_j e_{k−2}(w_{−i,−j}) / e_k(w), Π_ii = π_i — direct cu `ip_core.esp` pe w fără i, j (fără scădere)."""
    n = len(logw)
    w = np.exp(np.asarray(logw, float))
    P = np.zeros((n, n))
    P[np.arange(n), np.arange(n)] = pi
    if k < 2:
        return P
    ek = float(C.esp(torch.as_tensor(w, dtype=C.DT)[None], k)[0, k])
    ii, jj = np.nonzero(~np.eye(n, dtype=bool))
    keep = np.ones((len(ii), n), bool)
    keep[np.arange(len(ii)), ii] = False
    keep[np.arange(len(ii)), jj] = False
    W = np.broadcast_to(w, (len(ii), n))[keep].reshape(len(ii), n - 2)
    e = C.esp(torch.as_tensor(W, dtype=C.DT), k - 2)[:, k - 2].numpy()
    P[ii, jj] = w[ii] * w[jj] * e / ek
    return P


def case_record(C, cs: dict) -> dict:
    n, k = cs["n"], cs["k"]
    draws = cs["draws"]
    N = len(draws)
    c = np.zeros(n, np.int64)
    P = np.zeros((n, n), np.int64)
    for d in draws:
        idx = np.array(d) - 1
        c[idx] += 1
        P[np.ix_(idx, idx)] += 1
    cf = torch.as_tensor(c.astype(float), dtype=C.DT)[None]
    Nt = torch.as_tensor([float(N)], dtype=C.DT)
    th, x2 = C.theta_x2(cf, Nt, Nt, n, k)
    B = C.dct_basis(n)
    rec = {"name": cs["name"], "kind": "real" if "source" in cs else "fixture", "n": n, "k": k, "N": N,
           "game": cs.get("game"), "urn": cs.get("urn", "main"), "source": cs.get("source"),
           "draws": None if "source" in cs else draws,
           "counts": [int(x) for x in c], "pairs": [int(x) for x in P.ravel()],
           "theta": arr(th[0].numpy()), "x2": arr([float(x2[0])]), "basis": arr(B.numpy())}
    for m in ("h1", "h3"):
        if m == "h1":
            lw, lam = C.logw_h1(cf, Nt, n, k)
        else:
            lw, lam = C.logw_h3(cf, Nt, n, k, B)
        lw = lw[0].numpy()
        pi = inclusion(C, lw, k)
        blk = {"logw": arr(lw), "lambda": arr([float(lam[0])]),
               "D": arr([float(C.info_D(torch.as_tensor(lw, dtype=C.DT)[None], k)[0])]),
               "pi": arr(pi), "Pi": arr(pair_inclusion(C, lw, k, pi))}
        if k == 1:
            q = np.exp(lw - lw.max())
            blk["q"] = arr(q / q.sum())
        rec[m] = blk
    p = k / n
    f = c / N
    R = (P / N - np.outer(f, f)) / (p * (1 - p))
    z = math.sqrt((n - 1) / n) * (c - N * p) / math.sqrt(N * p * (1 - p))
    Z = np.fft.fft(z) / math.sqrt(n)
    rec.update({"R": arr(R), "z": arr(z), "dft_re": arr(Z.real), "dft_im": arr(Z.imag)})
    return rec


def main() -> int:
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    C = load_frozen(HERE / "ip_core.py", IP_SHA, "ip_core_s19_ro")
    S16 = load_frozen(HERE / "s16_martori.py", S16_SHA, "s16_martori_s19_ro")
    if sha_file(S17_FILE) != S17_SHA:
        raise RuntimeError("fișierul S17 a fost modificat")
    lant = [json.loads(x) for x in (HERE / "tribunal" / "LANT.jsonl").read_text().splitlines() if x.strip()]
    em_ok = {}
    for r in lant:
        if r["target_date"] == TARGET:
            p = HERE / "tribunal" / r["file"]
            em_ok[r["game"]] = sha_file(p) == r["sha256"] == EM_SHA[r["game"]]
    if sorted(em_ok) != ["540", "649", "joker"] or not all(em_ok.values()):
        raise RuntimeError(f"emisii: {em_ok}")
    cases = [case_record(C, cs) for cs in fixtures() + real_cases()]
    frft = []
    for n in N_FRFT:
        basis = S16.frft_basis(n)
        for a in A_GRID:
            F = S16.frft_matrix(n, a, basis)
            frft.append({"n": n, "a": a, "re": arr(F.real), "im": arr(F.imag)})
    doc = {"schema": "ql649-s19-paritate-ref/1", "protocol": "TU4-S19", "run_utc": utc,
           "protocol_sha256": sha_file(HERE / "PROTOCOL_SUPERQUANTUM_S19.md"),
           "seal_sha256": sha_file(HERE / "SIGILIU_TU4_S19.json"), "code_sha256": sha_file(Path(__file__)),
           "frozen": {"tu4/ip_core.py": IP_SHA, "tu4/s16_martori.py": S16_SHA,
                      "tu4/rezultate/S17/BILETE_ADMISIBILE_20261028T001924Z.json": S17_SHA,
                      **{f"tu4/tribunal/emisii/{g}/{TARGET}.json": s for g, s in EM_SHA.items()}},
           "versions": {"python": sys.version.split()[0], "torch": torch.__version__, "numpy": np.__version__},
           "device": "cpu", "dtype": "float64", "k_ad": int(C.K_AD), "a_grid": list(A_GRID),
           "cases": cases, "frft": frft, "positive_claims_allowed": False}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"REFERINTA_PARITATE_{utc}.json"
    out.write_text(json.dumps(doc, ensure_ascii=False) + "\n")
    os.chmod(out, 0o444)
    print(out)
    print(json.dumps({"cases": [c["name"] for c in cases], "frft": len(frft), "bytes": out.stat().st_size,
                      "sha256": sha_file(out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
