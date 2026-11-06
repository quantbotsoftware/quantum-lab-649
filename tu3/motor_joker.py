"""TU3 — modulul E-J: integrarea Joker în motorul polimorf. Protocol: PROTOCOL_TU3_EJ.md (sigilat în
SIGILIU_TU3_EJ.json ÎNAINTE de acest cod).

Joker = 5 numere distincte din 1..45 + 1 Joker din 1..20. Forma `SHAPE_JOKER = (45, 5, 5)`:
  - partea principală: motorul polimorf O1–O6 din `motor_n` (NEMODIFICAT), cu `PROTOCOL_JOKER` (seed_master = 4520);
  - Joker-ul: tensorul comun J `N_ja` (= `GameDataset.cross_counts` la pasul final), distribuția condiționată
    `q_V(a) = Σ_{j∈V} N_ja / Σ_{j∈V} Σ_b N_jb` și energia `E_J(a|V) = −ln q_V(a) + μ_ov·ovJ(a)`, minimizată exhaustiv
    pe cele 20 de valori (departajare după indice). Holonomia variantei `h_V = Σ_a q_V(a) e^{iφ_a}` este descriptivă.
Minimizarea este în DOUĂ ETAPE (întâi V prin O6, apoi a dat V), nu minimul comun pe (V, a).

`engine.py`, `parser.py`, `parser_multi.py`, `motor_n.py` și `joker_entanglement.py` NU se modifică. Calcul CLASIC
(PyTorch, CUDA implicit; fallback CPU jurnalizat). Variantele sunt minime de energie, NU predicții.
`positive_claims_allowed=false`.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
QL = HERE.parent
for _p in (str(QL), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import joker_entanglement as JE  # noqa: E402  (modulul J, nemodificat)
import motor_n as M  # noqa: E402  (modulul E40, nemodificat)
from engine import PROTOCOL, Config, sha256_file  # noqa: E402

PM = M.PM
F64, C128 = torch.float64, torch.complex128
PROTOCOL_FILE = HERE / "PROTOCOL_TU3_EJ.md"
SEAL_FILE = HERE / "SIGILIU_TU3_EJ.json"
POWER_FILE = HERE / "rezultate" / "EJ" / "PUTERE_EJ.json"

SHAPE_JOKER = M.Shape("joker", 45, 5, 5)
PROTOCOL_JOKER = replace(PROTOCOL, seed_master=4520)
M_JOKER = 20
LOG_FLOOR = 1e-300


# ---------------------------------------------------------------------------
# Tensorul comun cauzal (§2.3)
# ---------------------------------------------------------------------------
def cross_prefix(ds, k: int, device=None) -> torch.Tensor:
    """N^{(k)} [45,20] (float64, numărări întregi) din extragerile pașilor < k; aceeași operație ca `parser_multi`."""
    dev = ds.device if device is None else torch.device(device)
    if ds.joker_onehot is None:
        raise ValueError("setul nu are Joker")
    o = int(ds.step_offsets[int(k)].item())
    oh = ds.onehot.to(dev)
    jo = ds.joker_onehot.to(dev)
    return (oh[:o].T @ jo[:o]).to(F64)


# ---------------------------------------------------------------------------
# Distribuția condiționată, holonomia variantei și alegerea Joker-ului (§2.4–2.5)
# ---------------------------------------------------------------------------
def joker_conditional(N: torch.Tensor, V0: torch.Tensor) -> torch.Tensor:
    """N [B,n,m] numărări; V0 [B,Vn,5] indici 0-based ⇒ q [B,Vn,m]; numitor 0 ⇒ uniform 1/m."""
    B, Vn, k = V0.shape
    m = N.shape[-1]
    rows = N.gather(1, V0.reshape(B, Vn * k, 1).expand(-1, -1, m).to(torch.int64)).reshape(B, Vn, k, m)
    num = rows.sum(-2)
    den = num.sum(-1, keepdim=True)
    return torch.where(den > 0, num / den.clamp(min=LOG_FLOOR), torch.full_like(num, 1.0 / m))


def variant_holonomy(q: torch.Tensor) -> torch.Tensor:
    """h_V = Σ_a q_V(a) e^{iφ_a}, φ_a = 2π(a−1)/m."""
    e = torch.exp(1j * JE.joker_phases(q.shape[-1], q.device)).to(C128)
    return q.to(C128) @ e


def choose_jokers(q: torch.Tensor, cfg: Config = PROTOCOL_JOKER) -> dict:
    """Secvențial pe variante: E_J(a) = −ln max(q,1e-300) + μ_ov·ovJ(a); a* = cel mai mic indice de energie minimă."""
    B, Vn, m = q.shape
    ov = torch.zeros(B, m, dtype=F64, device=q.device)
    ar = torch.arange(m, device=q.device, dtype=torch.int64)
    js, es, Es = [], [], []
    base = -torch.log(q.clamp(min=LOG_FLOOR))
    for v in range(Vn):
        E = base[:, v] + cfg.mu_overlap * ov
        emin = E.amin(-1, keepdim=True)
        a = torch.where(E == emin, ar[None].expand(B, -1), torch.full_like(ar[None].expand(B, -1), m)).amin(-1)
        js.append(a)
        es.append(emin[:, 0])
        Es.append(E)
        ov = ov.clone()
        ov.scatter_add_(1, a[:, None], torch.ones(B, 1, dtype=F64, device=q.device))
    return {"jokers": torch.stack(js, 1) + 1, "E_J": torch.stack(es, 1), "E_J_all": torch.stack(Es, 1)}


def joker_stage(N: torch.Tensor, variants1: torch.Tensor, cfg: Config = PROTOCOL_JOKER) -> dict:
    """N [B,45,20]; variants1 [B,Vn,5] numere 1..45 ⇒ q, h_V, Joker-ii aleși (1..20) și E_J."""
    q = joker_conditional(N, variants1.to(torch.int64) - 1)
    ch = choose_jokers(q, cfg)
    return {"q": q, "h": variant_holonomy(q), **ch}


def j_descriptors(N: torch.Tensor) -> dict:
    """S_E, K_S, I, Φ ale tensorului comun (funcțiile modulului J, nemodificate). N [n,m]."""
    P, p, q = JE.joint_tensor(N[None])
    C, _ = JE.cross_covariance(P, p, q)
    _, S_E, K_S = JE.schmidt(P)
    hol = JE.holonomy(P, p, q, C, N.sum(-1)[None])
    return {"S_E": float(S_E[0]), "K_S": float(K_S[0]), "I": float(JE.mutual_information(P, p, q)[0]),
            "Phi": float(hol["Phi"][0]), "h_nodes": hol["h"][0]}


# ---------------------------------------------------------------------------
# Produsul
# ---------------------------------------------------------------------------
def engine_joker(ds, cfg: Config = PROTOCOL_JOKER, device=None, k: int | None = None) -> dict:
    """Motorul E-J complet (fără poarta de putere; folosit de teste pe date sintetice și de `run_full_joker`)."""
    if getattr(ds, "game", None) is None or ds.game.code != "joker":
        raise ValueError("motorul E-J cere un GameDataset Joker")
    out = M.run_full(ds, SHAPE_JOKER, cfg, device, k)
    dev = torch.device(out["device"])
    kk = out["k"]
    out["is_protocol"] = cfg == PROTOCOL_JOKER
    out["protocol_sha256"] = sha256_file(PROTOCOL_FILE)
    out["motor_n_metadata_overridden"] = ["is_protocol", "protocol_sha256"]
    N = cross_prefix(ds, kk, dev)
    V = torch.tensor(out["variants"], dtype=torch.int64, device=dev)[None]
    js = joker_stage(N[None], V, cfg)
    jokers = js["jokers"][0].tolist()
    e_main = out["energies"]
    e_j = js["E_J"][0].tolist()
    out.update({
        "cross_counts": N, "q_joker": js["q"][0], "h_variant": [complex(z) for z in js["h"][0].tolist()],
        "jokers": jokers, "variants_5plus1": [[v, a] for v, a in zip(out["variants"], jokers)],
        "energies_main": e_main, "energies_joker": e_j, "energies_total": [a + b for a, b in zip(e_main, e_j)],
        "J": {kk2: vv for kk2, vv in j_descriptors(N).items() if kk2 != "h_nodes"},
        "joker_minimization": "două etape: V prin O6 (motor_n), apoi a = argmin E_J(a|V) exhaustiv pe 1..20",
        "positive_claims_allowed": False,
        "note": "Variante 5+1 = minime de energie, NU predicții. Calcul clasic.",
    })
    return out


def power_verdict() -> str | None:
    """Verdictul verificării de putere sintetice (PROTOCOL_TU3_EJ §4), sau None dacă nu a rulat."""
    if not POWER_FILE.exists():
        return None
    return json.loads(POWER_FILE.read_text()).get("verdict")


def run_full_joker(ds=None, cfg: Config = PROTOCOL_JOKER, device=None, k: int | None = None) -> dict:
    """Produsul E-J (Joker 5+1): intrare implicită `parser_multi.build_game_dataset("joker", "live")`.
    Refuză datele reale înainte ca verificarea de putere sintetică să dea `EJ_PASS` (§4)."""
    if power_verdict() != "EJ_PASS":
        raise RuntimeError("E-J: verificarea de putere sintetică nu a dat EJ_PASS; nicio rulare pe date reale (§4)")
    if ds is None:
        ds = PM.build_game_dataset("joker", "live", device=device)
    return engine_joker(ds, cfg, device, k)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="TU3 E-J — motorul Joker 5+1 (variante = minime de energie, NU predicții)")
    ap.add_argument("--sursa", default="live", help="live (produs) sau frozen (protocoale sigilate)")
    a = ap.parse_args(argv)
    ds = PM.build_game_dataset("joker", a.sursa)
    out = run_full_joker(ds)
    show = {kk: vv for kk, vv in out.items() if not torch.is_tensor(vv)}
    print(json.dumps(show, indent=2, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
