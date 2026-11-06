"""Generează RAPORT_QL649.md direct din artefactele sigilate (fără editare manuală a cifrelor)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BT = ROOT / "rezultate" / "backtest_unic"
NUL = ROOT / "rezultate" / "multivers_pipeline"
PRE = ROOT / "rezultate" / "multivers_pipeline_preA02"


def j(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def main() -> int:
    res, sci, ver = j(BT / "REZULTATE.json"), j(BT / "SCI.json"), j(BT / "VERIFICARE_INDEPENDENTA.json")
    if not res:
        print("lipsește rezultate/backtest_unic/REZULTATE.json")
        return 1
    seal = j(ROOT / "SIGILIU_PROTOCOL.json")
    nsum, pre = j(NUL / "SUMAR.json"), j(PRE / "SUMAR.json")
    t, h1, h2 = res["total"], res["half1"], res["half2"]
    L = []
    a = L.append
    a("# RAPORT QL649 — „Quantum Lab 649” (pistă nouă, separată de DL-649)\n")
    a(f"Protocol `QL649-P1` sigilat (sha256 `{seal['sha256']}`, {seal['sealed_at_utc']}), "
      "amendamente [AMENDAMENT_01.md](AMENDAMENT_01.md) (4 universuri nule descriptive în loc de 64, cost de calcul) și "
      "[AMENDAMENT_02.md](AMENDAMENT_02.md) (interdicție tare pentru variante identice), ambele sigilate înainte de backtest. "
      "Pista DL-649 (revizia 20261025T165403Z) rămâne înghețată și neatinsă.\n")
    a("Calcul clasic (PyTorch pe GPU NVIDIA RTX 5060 Laptop). Inspirația cuantică (non-hermitic/EP, Amplituhedron, Poincaré, "
      "Kuramoto, Born–Boltzmann, MCMC) este strict matematică: fără hardware cuantic, fără avantaj cuantic, fără noutate "
      "mondială revendicată. Arhivă deja explorată: valoare confirmatoare 0, nu set nevăzut. `positive_claims_allowed=false`.\n")
    a("## Backtest walk-forward cauzal unic (Mașina Timpului)\n")
    st = res["start"]
    a(f"Sursa sha256 `{st['source_sha256']}`, {st['n_draws']} extrageri, {st['n_steps']} pași (zile), încălzire {st['warmup']} pași, "
      f"{res['n_steps_predicted']} pași prezisi, **{res['n_targets']} ținte**. Predicții scrise și sigilate înainte de scor "
      f"(`PREDICTII.npz` sha256 `{res['predictions_sha256']}`). Config digest `{st['config_digest']}`, protocol={st['is_protocol']}.\n")
    a("| Parte | Ținte | hitsQL | hitsB | hitsR | ExcesQL/U | logQL−U | logQL−B | BrierQL | BrierU |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, x in (("Total", t), ("Prima jumătate", h1), ("A doua jumătate", h2)):
        a(f"| {name} | {x['targets']} | {x['hits_QL']} | {x['hits_B']} | {x['hits_R']} | {x['excess_QL']:.9f} | "
          f"{x['log_QL'] - x['log_U']:.6f} | {x['log_QL'] - x['log_B']:.6f} | {x['brier_QL']:.6f} | {x['brier_U']:.6f} |")
    a("")
    a("| Poartă | Cerință | Rezultat | Valoare |")
    a("|---|---|---|---|")
    for g in res["gates"]:
        a(f"| {g['gate']} | {g['rule']} | {'PASS' if g['pass'] else 'FAIL'} | `{json.dumps(g['value'])}` |")
    a("")
    a(f"**Verdict: `{res['verdict']}` ({res['gates_passed']}/6 porți).** Descriptiv: p exact (hitsQL ≥ observat | extrageri "
      f"uniforme independente) = {res['p_exact_hits_QL_ge']:.6f}; potriviri varianta 1 (0..6) = {res['match_dist_QL_v1']} vs "
      f"așteptat {[round(v, 1) for v in res['match_expected_U']]}; reuniunea celor 3 variante: {t['hits_union3_QL']} hits vs "
      f"{t['expected_union3_U']:.1f} așteptat uniform; bilete QL diferite de B la {res['tickets_changed_vs_B']} pași-țintă; "
      f"EP convergent la {100 * res['ep_converged_frac']:.1f}% din pași; γ_q = 0 (punctul hermitic pe grilă) la "
      f"{100 * res['gamma_q_zero_frac']:.1f}% din pași.\n")
    tm = res.get("timings_s", {})
    try:
        import numpy as np
        P = np.load(BT / "PREDICTII.npz")
        V = P["variants"]
        usz = np.array([len(set(V[i].ravel().tolist())) for i in range(V.shape[0])])
        steps = np.array(res["per_target"]["step"])
        exp_u = float(sum(usz[s - int(P["ks"][0])] * 6 / 49 for s in steps))
        a(f"Notă corectă pentru reuniune: variantele se suprapun (în medie {usz.mean():.2f} numere distincte din 18), deci "
          f"așteptarea uniformă condiționată de mărimea reală a reuniunii este {exp_u:.1f} hits (observat {t['hits_union3_QL']}); "
          f"cifra {t['expected_union3_U']:.1f} din protocol presupune 18 numere distincte și nu este comparabilă direct.\n")
    except Exception as exc:  # raport robust
        a(f"(nota despre reuniune indisponibilă: {exc})\n")
    a(f"Timp: backtest {res['backtest_seconds']:.0f} s ({', '.join(f'{k} {v:.0f}s' for k, v in tm.items())}), SCI {res['sci_seconds']:.0f} s, "
      f"vârf VRAM {res['vram_peak_mib']:.0f} MiB.\n")
    if ver:
        a(f"Verificare independentă (NumPy fp64, fără import din engine/parser/validare): **{ver['status']}** "
          f"({ver['n_checks'] - ver['n_fail']}/{ver['n_checks']}).\n")
    a("## Indicele de Coerență Structurală (Multiversul Nul)\n")
    a(f"M = {sci['M']} istorii uniforme (aceeași structură de zile). SCI = **{sci['SCI']:+.4f}σ**, p empiric = **{sci['p_empirical']:.4f}**.\n")
    a("| Statistică | Real | Medie nul | Abatere nul | z |")
    a("|---|---:|---:|---:|---:|")
    for k, v in sci["z"].items():
        a(f"| {k} | {sci['stats_real'][k]:.4f} | {sci['null_mean'][k]:.4f} | {sci['null_std'][k]:.4f} | {v:+.4f} |")
    a("")
    a("Interpretare `chi_gap`: suma pe cele 49 de numere a χ² histogramelor de goluri (binuri 1..20, 21+) față de media "
      "universurilor nule (lectura „per număr” din §4).\n")
    a("## Pipeline complet pe universuri nule (descriptiv)\n")
    if nsum:
        for u in nsum["universes"]:
            a(f"- u{u['u']:03d}: exces {u['excess_QL']:+.6f}, hits QL/B/R {u['hits_QL']}/{u['hits_B']}/{u['hits_R']}, "
              f"logQL−B {u['logQL_minus_B']:+.3f}, porți {u['gates_passed']}/6")
        exs = [u["excess_QL"] for u in nsum["universes"]]
        lus = [u["logQL_minus_U"] for u in nsum["universes"]]
        ver_ok = sum(1 for u in nsum["universes"]
                     if (j(NUL / f"u{u['u']:03d}" / "run" / "VERIFICARE_INDEPENDENTA.json") or {}).get("status") == "PASS")
        a(f"- Comparație descriptivă (M = {nsum['M']}, nu poartă): excesul real {t['excess_QL']:+.6f} se află în intervalul "
          f"nul [{min(exs):+.6f}, {max(exs):+.6f}]; logQL−U real {t['log_QL'] - t['log_U']:+.1f} față de intervalul nul "
          f"[{min(lus):+.1f}, {max(lus):+.1f}]. Supra-concentrarea legii marginale QL costă mii de nați și sub nul. "
          f"Verificare independentă pe universuri: {ver_ok}/{nsum['M']} PASS.")
    else:
        a("- universurile u000–u003 (cod final) nu sunt încă rulate.")
    if pre:
        u = pre["universes"][0]
        a(f"- pre-A02 u000 (păstrat, dovada defectului de unicitate): exces {u['excess_QL']:+.6f}, porți {u['gates_passed']}/6.")
    a("")
    a("## Limite\n")
    a("Rezultatul nu demonstrează avantaj predictiv real și nu infirmă universal alte idei. Dacă extragerile sunt uniforme "
      "și independente, istoricul nu oferă avantaj. Variantele din UI sunt minimele energiei modelului, etichetate "
      "„exploratoriu, fără avantaj demonstrat”. Nicio evaluare prospectivă, emisie live sau promisiune de câștig.\n")
    (ROOT / "RAPORT_QL649.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("RAPORT_QL649.md scris")
    return 0


if __name__ == "__main__":
    sys.exit(main())
