"""Generează RAPORT_PL649.md + MANIFEST_PL649.json numai din artefactele PL649 (fără recalcul de model)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R = HERE / "rezultate"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def rank_low(vals, x):
    v = np.asarray(vals, float)
    return int((v <= x).sum()), len(v)


def main() -> int:
    seal = load(HERE / "SIGILIU_PROTOCOL_PL649.json")
    q = load(R / "calificare" / "CALIFICARE.json")
    st = load(R / "backtest_unic" / "START.json")
    r = load(R / "backtest_unic" / "REZULTATE.json")
    v = load(R / "backtest_unic" / "VERIFICARE_INDEPENDENTA.json")
    nm = load(R / "descriptiv" / "NUL_LEGE_1024.json")
    nf = load(R / "descriptiv" / "NUL_COMPLET_32.json")
    pw = load(R / "descriptiv" / "PUTERE.json")
    ac = load(R / "descriptiv" / "CERTIFICAT_ANEALER.json")
    fi = load(R / "final" / "FINAL.json")
    t = r["total"]
    L = []
    w = L.append
    w("# RAPORT PL649 — „Singularitatea Planck” (rețea de spin + holonomii SU(3) + vid Higgs)\n")
    w(f"Generat {dt.datetime.now(dt.timezone.utc).isoformat()[:19]}Z din artefacte. Protocol `PL649-P1`, "
      f"sha256 `{seal['sha256']}`, sigilat {seal['sealed_at_utc'][:19]}Z înainte de cod. Calcul CLASIC pe GPU "
      f"(NVIDIA RTX 5060 Laptop, PyTorch CUDA); termenii LQG / Yang–Mills / Higgs sunt inspirație matematică. "
      "`positive_claims_allowed=false`. Arhiva este deja explorată (nu set nevăzut).\n")
    w("## Verdict\n")
    w(f"- Calificare: **{q['verdict']} {q['n_pass']}/6** ({q['finished_utc'][:19]}Z, {q['seconds']:.0f} s, arhiva reală neatinsă).")
    w(f"- Backtest unic (START {st['started_utc'][:19]}Z, {r['n_targets']} ținte): **{r['verdict']} {r['gates_passed']}/6**.")
    w(f"- Verificare independentă: **{(v or {}).get('status', 'NERULATĂ')} {(v or {}).get('n_checks', 0) - (v or {}).get('n_fail', 0)}/"
      f"{(v or {}).get('n_checks', 0)}**.\n")
    w("## Backtest unic\n")
    w("| model | hits | exces | log | Brier |\n|---|---|---|---|---|")
    for k in ("PL", "B", "R"):
        w(f"| {k} | {t['hits_' + k]} | {t['excess_' + k]:+.4f} | {t['log_' + k]:.2f} | {t['brier_' + k]:.2f} |")
    w(f"| U | — | 0 | {t['log_U']:.2f} | {t['brier_U']:.2f} |")
    w(f"| top-6 după π (descriptiv) | {t['hits_PI6']} | {t['excess_PI6']:+.4f} | — | — |\n")
    w(f"- logPL−U = {t['log_PL'] - t['log_U']:.2f} (estimarea de mână sub nul ≈ −530, §3.6); logPL−B = {t['log_PL'] - t['log_B']:.2f}.")
    w(f"- Jumătăți: hitsPL−B = {r['half1']['hits_PL'] - r['half1']['hits_B']} / {r['half2']['hits_PL'] - r['half2']['hits_B']}; "
      f"logPL−B = {r['half1']['log_PL'] - r['half1']['log_B']:.2f} / {r['half2']['log_PL'] - r['half2']['log_B']:.2f}.")
    w(f"- p exact (hits ≥ {t['hits_PL']} | U) = {r['exact_tail_p_hitsPL_ge']:.3f}; distribuția potrivirilor {r['match_dist_PL']}.")
    w(f"- Bilet PL ≠ B la {r['tickets_changed_vs_B_targets']}/{r['n_targets']}, ≠ R la {r['tickets_changed_vs_R_targets']}, "
      f"≠ top-6 după π la {r['tickets_changed_vs_top6pi_targets']} (efectul termenului de pereche).")
    w(f"- Decalaj energetic minim al vidului {r['E_gap_min']:.2e} (pași cu decalaj ≤ 1e-6: {r['steps_gap_le_1e-6']}); "
      f"eroarea de unitaritate finală {r['final_unitarity']['max_unitarity']:.1e}; walk-forward {r['walk_seconds']:.0f} s "
      f"cu enumerarea completă a 13.983.816 bilete la fiecare pas.")
    w(f"- Consecvență B/R: {r['consistency_BR']}.\n")
    w("| poartă | cerință | rezultat |\n|---|---|---|")
    for g in r["gates"]:
        w(f"| {g['gate']} | {g['rule']} | {'PASS' if g['pass'] else 'FAIL'} |")
    w("\n## Calificare (martori analitici)\n")
    for k in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6"):
        d = {kk: vv for kk, vv in q[k].items() if kk not in ("checkpoints", "enumeration", "unitarity")}
        w(f"- **{k}** {'PASS' if q[k]['pass'] else 'FAIL'}: `{json.dumps(d, ensure_ascii=False, default=float)[:400]}`")
    w("\n## Descriptiv (nu schimbă verdictul)\n")
    if nm:
        lu = [x["logPL_U"] for x in nm["rows"]]
        lb = [x["logPL_B"] for x in nm["rows"]]
        h6 = [x["hits_PI6"] for x in nm["rows"]]
        a, n = rank_low(lu, t["log_PL"] - t["log_U"])
        b, _ = rank_low(lb, t["log_PL"] - t["log_B"])
        c, _ = rank_low(h6, t["hits_PI6"])
        w(f"- **{n} universuri nule pe GPU** (legea; {nm['seconds']:.0f} s): logPL−U medie {np.mean(lu):.1f} "
          f"(sd {np.std(lu):.1f}); valoarea reală are rangul {a}/{n} (≤). logPL−B: rang {b}/{n}; logPL−B > 0 în "
          f"{sum(x > 0 for x in lb)}/{n}. hits top-6 π: medie {np.mean(h6):.1f}, rang real {c}/{n}. Porțile legii 3/4/6 "
          f"trecute în {sum(all(x['law_gates_3_4_6']) for x in nm['rows'])}/{n}.")
    if nf:
        gp = [x["gates_passed"] for x in nf["rows"]]
        hp = [x["hits_PL"] for x in nf["rows"]]
        a, n = rank_low(hp, t["hits_PL"])
        w(f"- **{n} universuri nule complete** (bilet QUBO exact): porți trecute {np.bincount(gp, minlength=7).tolist()} "
          f"(max {max(gp)}/6); hitsPL medie {np.mean(hp):.1f}, rang real {a}/{n}.")
    w("- Interpretare: valorile reale stau în coada de JOS a nulului (log, hits), deci nicio indicație de semnal pozitiv; "
      "coada de jos NU se tratează ca anti-semnal exploatabil (nicio inversare post-hoc a modelului). Aria totală are "
      "dispersie nulă foarte mică deoarece numărul total de co-extrageri este fix (2595·15).")
    if pw:
        for gname, rows in pw["gamma_results"].items():
            ex = [x["excess_PL"] for x in rows]
            gp = [x["gates_passed"] for x in rows]
            w(f"- **Putere H_PL γ = {gname}** ({len(rows)} universuri): exces mediu {np.mean(ex):+.3f}; porți "
              f"{np.bincount(gp, minlength=7).tolist()}; poarta 1 în {sum(x['gates'][0] for x in rows)}/{len(rows)}.")
    if ac:
        w(f"- **Certificatul anealerului Higgs** (50.000 replici, pașii din 97 în 97): succes {ac['success_rate']:.0%} "
          f"({sum(x['success'] for x in ac['rows'])}/{len(ac['rows'])}).")
    if fi:
        tl = fi["telemetry"]
        w(f"- **Starea finală** ({fi['n_draws']} extrageri): arie Planck totală {tl['planck_area_total']:.1f} vs nul "
          f"{tl['planck_area_null_mean']:.3f} ± {tl['planck_area_null_sd']:.3f} (PAD {tl['planck_area_deviancy']:+.2e}, "
          f"z {tl['planck_area_z']:+.2f}); erori de holonomie {tl['holonomy_error']['frac_links_err_gt_1e-12']:.0%} "
          f"(max {tl['holonomy_error']['max_unitarity']:.1e}); monopoli XY persistenți "
          f"{fi['monopoles_xy']['persistent_monopoles']}/{fi['monopoles_xy']['n_triangles']}; anealerul = vidul exact: "
          f"{fi['annealer']['agrees_with_exact_ground_state']}.")
        w(f"- Produs (UI, tabul 12): cele 3 variante = {[x['ticket'] for x in fi['variants']]} — minimele exacte ale energiei "
          "PL, NU predicții; backtestul nu a arătat niciun avantaj.")
    w("\n## Abateri, incidente, limite\n")
    w("- `engine.py`/`parser.py` NEMODIFICATE (QL649 sigilat); motorul v2.0 este `pl649/pl_core.py`; `app.py` primește aditiv tabul 12.")
    w("- Test de dezvoltare (fum) pe date ALEATOARE înainte de calificare, păstrat în `jurnal/dezvoltare/` (nu pe fixture-le "
      "Q5/Q6, nu pe arhivă). Zero amendamente, zero incidente tehnice la calificare/backtest.")
    w("- Nicio pretenție fizică: separarea de scară Planck–urnă ~33 ordine de mărime; volumul este un proxy; „monopolii” sunt "
      "vortexuri XY. Rezultatul negativ nu infirmă alte idei; nu se salvează PL (fără alt ε, β, η, generatori, orientări).")
    (HERE / "RAPORT_PL649.md").write_text("\n".join(L) + "\n")
    files = [p for p in sorted(HERE.rglob("*")) if p.is_file() and "__pycache__" not in p.parts
             and p.name not in ("MANIFEST_PL649.json",) and ".pytest_cache" not in p.parts]
    (HERE / "MANIFEST_PL649.json").write_text(json.dumps({str(p.relative_to(HERE)): sha(p) for p in files}, indent=1))
    print("RAPORT_PL649.md + MANIFEST_PL649.json generate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
