"""Generează RAPORT_BO649.md direct din artefactele sigilate (fără editare manuală a cifrelor)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R = HERE / "rezultate"
RUN = R / "backtest_unic"


def j(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def main() -> int:
    seal, qual = j(HERE / "SIGILIU_PROTOCOL_BO649.json"), j(R / "CALIFICARE.json")
    res, ver = j(RUN / "REZULTATE.json"), j(RUN / "VERIFICARE_INDEPENDENTA.json")
    sens, nul = j(R / "SENSIBILITATE.json"), j(R / "nule" / "SUMAR.json")
    L = []
    a = L.append
    a("# RAPORT BO649 — „Rupturi de regim” (detecție bayesiană online a schimbărilor)\n")
    a(f"Protocol `BO649-P1` sigilat (sha256 `{seal['sha256']}`, {seal['sealed_at_utc']}) înainte de orice cod și calcul BO649. "
      "Ipoteză nouă și distinctă în pista QL649. Nu este o salvare a QL649 (închis 0/6) sau a DL-649 (înghețat, neatins). "
      "Modelele închise nu au fost importate sau rulate. OGLINDA nu a fost atinsă. Precedente: Adams & MacKay (2007), "
      "Fearnhead & Liu (2007). Calculul este clasic exact, NumPy fp64 pe CPU, cu certificate în Q (`Fraction`). Nu se "
      "revendică hardware cuantic, avantaj cuantic sau noutate mondială. `positive_claims_allowed=false`. Arhiva este "
      "deja explorată, deci nu este un set nevăzut.\n")
    a("## Calificare (înainte de istoria reală)\n")
    a(f"Status **{qual['status']}** ({qual['passed']}/6), cod sha256 `{qual['code_sha256'][:16]}…`, {qual['utc']}. "
      "Numerele din arhivă nu au fost folosite; s-a folosit doar structura pașilor.\n")
    a("| Verificare | Rezultat | Detalii |")
    a("|---|---|---|")
    for c in qual["checks"]:
        d = {k: v for k, v in c.items() if k not in ("id", "pass", "detail")}
        a(f"| {c['id']} | {'PASS' if c['pass'] else 'FAIL'} | `{json.dumps(d, ensure_ascii=False)[:260]}` |")
    a("")
    if res:
        t, h1, h2 = res["total"], res["half1"], res["half2"]
        st = res["start"]
        a("## Backtest walk-forward cauzal unic\n")
        a(f"Sursa are sha256 `{st['source_sha256']}`, cu {st['n_draws']} extrageri și {st['n_steps']} pași-zi, de la "
          f"{st['first_date']} la {st['last_date']}. Încălzirea are 100 de pași; rămân **{res['n_targets']} ținte**. "
          f"Configurația este `h = 1/250` și `m0 = 12`. Predicțiile au fost sigilate înainte de scor: `PREDICTII.npz` "
          f"are sha256 `{res['predictions_sha256']}`. Durata calculului a fost {res['predict_seconds']:.1f} s.\n")
        a("| Parte | Ținte | hitsBO | hitsB | hitsR | ExcesBO/U | logBO−U | logBO−B | BrierBO | BrierU |")
        a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for name, x in (("Total", t), ("Prima jumătate", h1), ("A doua jumătate", h2)):
            a(f"| {name} | {x['targets']} | {x['hits_BO']} | {x['hits_B']} | {x['hits_R']} | {x['excess_BO']:+.6f} | "
              f"{x['log_BO'] - x['log_U']:+.6f} | {x['log_BO'] - x['log_B']:+.6f} | {x['brier_BO']:.6f} | {x['brier_U']:.6f} |")
        a("")
        a("| Poartă | Cerință | Rezultat | Valoare |")
        a("|---|---|---|---|")
        for g in res["gates"]:
            a(f"| {g['gate']} | {g['rule']} | {'PASS' if g['pass'] else 'FAIL'} | `{json.dumps(g['value'])}` |")
        a("")
        P = np.load(RUN / "PREDICTII.npz")
        pl = P["post_last"]
        a(f"**Verdict: `{res['verdict']}` ({res['gates_passed']}/6 porți).**\n")
        a("Date descriptive:")
        a(f"- p exact (hitsBO ≥ observat | extrageri uniforme independente) = {res['p_exact_hits_BO_ge']:.6f};")
        a(f"- potriviri BO (0..6): {res['match_dist_BO']}; așteptat sub U: "
          f"{[round(v, 1) for v in res['match_expected_U']]};")
        a(f"- biletul BO diferă de B la {res['tickets_changed_vs_B_steps']} pași-țintă și de R la "
          f"{res['tickets_changed_vs_R_steps']};")
        a(f"- E[r] pe pașii-țintă: min {res['Er']['min']:.1f}, median {res['Er']['median']:.1f}, max "
          f"{res['Er']['max']:.1f}, ultimul {res['Er']['last']:.1f};")
        a(f"- pași cu P(r ≤ 100) > 0.5: {res['steps_p_recent_gt_half']};")
        a(f"- la ultimul pas, P(r ≥ 2000) = {pl[2000:].sum():.4f}.")
        a("")
        a("Interpretare: posteriorul BO revine în cea mai mare parte la ipoteza „un singur regim lung”. În acest caz "
          "BO se apropie de B, cu netezirea priorului și cu fluctuații suplimentare. Pierderea log față de B și U este "
          "costul flexibilității fără semnal, așa cum se așteaptă sub uniformitate.\n")
    if ver:
        a(f"Verificarea independentă (`verify_bo649.py`, fără import din bo649, engine, parser, validare sau torch; "
          f"log-domeniu și sume de prefix) a dat **{ver['status']}** ({ver['n_checks'] - ver['n_fail']}/{ver['n_checks']}).\n")
    if sens:
        a("## Sensibilitate (strict descriptivă, declarată în §6; nicio configurație nu poate fi promovată sau selectată)\n")
        a("| h | m0 | hitsBO | ExcesBO/U | logBO−U | logBO−B | porți |")
        a("|---:|---:|---:|---:|---:|---:|---:|")
        for r in sens["rows"]:
            a(f"| 1/{round(1 / r['h'])} | {r['m0']:g} | {r['hits_BO']} | {r['excess_BO']:+.6f} | {r['logBO_minus_U']:+.3f} | "
              f"{r['logBO_minus_B']:+.3f} | {r['gates_passed']}/6 |")
        a("")
    if nul and res:
        u = nul["universes"]
        ex = np.array([x["excess_BO"] for x in u])
        lb = np.array([x["logBO_minus_B"] for x in u])
        gp = np.array([x["gates_passed"] for x in u])
        rex = res["total"]["excess_BO"]
        rlb = res["total"]["log_BO"] - res["total"]["log_B"]
        a(f"## Universuri nule sintetice (descriptiv, M = {nul['M']}, seed `{nul['seed']}`)\n")
        a(f"- Excesul BO: medie {ex.mean():+.6f}, abatere {ex.std(ddof=1):.6f}. Valoarea reală {rex:+.6f} are rangul "
          f"empiric {int((ex <= rex).sum())}/{len(ex)} (≤).")
        a(f"- logBO−B: medie {lb.mean():+.3f}, abatere {lb.std(ddof=1):.3f}. Valoarea reală {rlb:+.3f} are rangul "
          f"empiric {int((lb <= rlb).sum())}/{len(lb)} (≤).")
        a(f"- Porți trecute pe universurile nule: distribuția {np.bincount(gp, minlength=7).tolist()} (0..6); maximum "
          f"{gp.max()}/6.")
        a("")
    a("## Limite\n")
    a("Rezultatul nu demonstrează avantaj predictiv real și nu infirmă universal alte idei sau alte modele de "
      "regim, de exemplu cu hazard variabil sau cu rate corelate. Dacă extragerile sunt uniforme și independente, "
      "istoricul nu oferă avantaj. Nu au existat evaluări prospective, emisii live sau promisiuni de câștig. Nu s-a "
      "făcut tuning după rezultat; grila de sensibilitate a fost declarată înainte și este doar descriptivă. O singură "
      "corectură a fost făcută într-un test de inginerie (`tests/test_bo649.py`): așteptarea greșită a testului pentru "
      "biletul cu egalități a fost reparată după prima rulare a testelor. Modelul, protocolul și pragurile nu au fost "
      "atinse, iar testul nu este o poartă.\n")
    (HERE / "RAPORT_BO649.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("RAPORT_BO649.md scris")
    return 0


if __name__ == "__main__":
    sys.exit(main())
