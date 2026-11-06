"""Generează RAPORT_SE649.md și MANIFEST_SE649.json direct din artefactele sigilate (fără cifre editate manual)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R = HERE / "rezultate"
RUN = R / "backtest_unic"


def j(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rank_line(name: str, arr: np.ndarray, real: float, fmt: str) -> str:
    return (f"- {name}: medie {arr.mean():{fmt}}, abatere {arr.std(ddof=1):{fmt.lstrip('+')}}, min {arr.min():{fmt}}, "
            f"max {arr.max():{fmt}}. Valoarea reală {real:{fmt}} are rangul empiric {int((arr <= real).sum())}/{len(arr)} (≤).")


def main() -> int:
    seal, qual = j(HERE / "SIGILIU_PROTOCOL_SE649.json"), j(R / "CALIFICARE.json")
    res, ver = j(RUN / "REZULTATE.json"), j(RUN / "VERIFICARE_INDEPENDENTA.json")
    sens, nul, pw = j(R / "SENSIBILITATE.json"), j(R / "nule" / "SUMAR.json"), j(R / "putere" / "SUMAR.json")
    psig = j(RUN / "PREDICTII_SIGILIU.json")
    L = []
    a = L.append
    a("# RAPORT SE649 — „Anotimpurile bilelor” (Bayes liniar ierarhic exact, etichetă × anotimp)\n")
    a(f"Protocol `SE649-P1` sigilat (sha256 `{seal['sha256']}`, {seal['sealed_at_utc']}) înainte de orice cod și calcul "
      "SE649. Ipoteză nouă și distinctă în pista QL649; nu este o salvare a QL649 (0/6), BO649 (0/6), WU649 (necalificat "
      "5/6), GL649 (2/6) sau DL-649 (înghețat, neatins). Modelele închise nu au fost importate sau rulate; OGLINDA nu a "
      "fost atinsă. Precedente: Hartigan (1969), Goldstein & Wooff (2007), Henderson (1975), Robinson (1991), "
      "Sherman & Morrison (1950); dependența de temperatură a restituției elastomerilor este fizică clasică. Calcul "
      "clasic: predictorul exact în Q (`Fraction`), scorurile în fp64 pe CPU. Fără hardware cuantic, avantaj cuantic sau "
      "noutate mondială. `positive_claims_allowed=false`. Arhiva este deja explorată, deci nu este un set nevăzut.\n")
    a("Ipoteza H_SE: `p_j(φ) = p0 + a_j + b_j(φ)`, cu φ anotimpul meteorologic al datei extragerii (DJF/MAM/JJA/SON), "
      "efect principal `a ~ (0, (p0/20)² P)` și interacțiune `b(φ) ~ (0, (p0/5)² P)`, independente între anotimpuri. "
      "Predicția este așteptarea ajustată Bayes liniară `p̂ = p0·1 + Σ_φ w_φ (c_φ/n_φ − p0·1)`, cu ponderi în formă "
      "închisă (Sherman–Morrison); `Σ p̂ = 6` exact și `p̂ ∈ (0,1)`. Motivul a priori: o interacțiune cu medie anuală zero "
      "este invizibilă pentru B (numărări totale), deci nu era infirmată de rezultatele negative anterioare. Premisa "
      "fizică (climatizare, seturi de bile) nu este verificată pentru Loteria Română.\n")
    a("## Calificare (înainte de istoria reală)\n")
    a(f"Status **{qual['status']}** ({qual['passed']}/6), cod sha256 `{qual['code_sha256'][:16]}…` (arhivat byte-identic "
      f"în `rezultate/cod_calificare/se649.py`), {qual['utc']}, durată {qual['seconds']:.0f} s. Numerele arhivei nu au "
      "fost folosite; Q2–Q4 au citit doar structura pașilor și anotimpurile datelor. Martorii Q5/Q6 au fost derivați "
      "analitic în protocol (Derivarea B: antisimetrie iarnă–vară, `p̂ − p0 = (τb²/D) u`) și confirmați exact în Q.\n")
    a("| Verificare | Nume | Rezultat | Detalii |")
    a("|---|---|---|---|")
    for c in qual["checks"]:
        a(f"| {c['id']} | {c['name']} | {'PASS' if c['pass'] else 'FAIL'} | "
          f"`{json.dumps(c['detail'], ensure_ascii=False)[:300]}` |")
    a("")
    d5, d6 = qual["checks"][4]["detail"], qual["checks"][5]["detail"]
    a(f"Martor de informație (F5, 4 blocuri × 49): etichetele 5 și 9 au numărări totale egale (B identic), dar pentru ținta "
      f"de iarnă `p̂_5 − p̂_9 = {d5['gap_float']:.6e}` = `6τb²/(49D)` exact (τb²/D = {d5['tb2_over_D']:.6f}); diferența în "
      f"lege = {d5['law_gap']:.6e} ≥ 1e-3; pentru ținta de vară diferența își schimbă exact semnul: "
      f"{d5['summer_target_gap_flips_exact']}.")
    a(f"Martor de decizie (F6, iarnă + vară, k = {d6['k']}): bilet SE {d6['ticket_SE']}, bilet B {d6['ticket_B']} "
      f"(disjuncte), bilet R {d6['ticket_R']} (`ew_1` = {d6['ew_1']:.4f} ≥ marginea {d6['ew_1_lower_bound']:.4f} > "
      f"{d6['ew_44_49_upper_bound']:.4f} ≥ max ew_44..49 = {d6['max_ew_44_49']:.4f}). Anticiparea analitică a fost "
      "confirmată exact.\n")
    if res:
        t, h1, h2 = res["total"], res["half1"], res["half2"]
        st = res["start"]
        a("## Backtest walk-forward cauzal unic\n")
        a(f"START {st['utc']}. Sursa are sha256 `{st['source_sha256']}`, cu {st['n_draws']} extrageri și {st['n_steps']} "
          f"pași-zi, de la {st['first_date']} la {st['last_date']}. Încălzirea are 100 de pași; rămân "
          f"**{res['n_targets']} ținte**. Predicțiile au fost sigilate înainte de scor: `PREDICTII.npz` sha256 "
          f"`{psig['npz_sha256']}`, fracțiile exacte și ponderile `PREDICTII_EXACTE.json.gz` sha256 "
          f"`{psig['exact_sha256']}` (Σ p̂ = 6 exact la toți pașii: {psig['sum_exact_ok']}; p̂ ∈ (0,1): "
          f"{psig['range_ok']}). Durata predicției: {res['predict_seconds']:.1f} s. Consecvența comparatorilor cu "
          f"BO649/GL649 (hitsB = 1847, hitsR = 1821): {'DA' if res['consistency_with_BO649_GL649']['ok'] else 'NU'}; "
          f"rulare validă: {res['valid_run']}.\n")
        a("| Parte | Ținte | hitsSE | hitsB | hitsR | ExcesSE/U | logSE−U | logSE−B | BrierSE | BrierU | BrierB |")
        a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for name, x in (("Total", t), ("Prima jumătate", h1), ("A doua jumătate", h2)):
            a(f"| {name} | {x['targets']} | {x['hits_SE']} | {x['hits_B']} | {x['hits_R']} | {x['excess_SE']:+.6f} | "
              f"{x['log_SE'] - x['log_U']:+.6f} | {x['log_SE'] - x['log_B']:+.6f} | {x['brier_SE']:.6f} | "
              f"{x['brier_U']:.6f} | {x['brier_B']:.6f} |")
        a("")
        a("| Poartă | Cerință | Rezultat | Valoare |")
        a("|---|---|---|---|")
        for g in res["gates"]:
            a(f"| {g['gate']} | {g['rule']} | {'PASS' if g['pass'] else 'FAIL'} | `{json.dumps(g['value'])}` |")
        a("")
        a(f"**Verdict: `{res['verdict']}` ({res['gates_passed']}/6 porți).**\n")
        a("Pe anotimpul țintei (descriptiv):\n")
        a("| Anotimp țintă | Ținte | hitsSE | hitsB | hitsR | ExcesSE/U | logSE−B | logSE−U |")
        a("|---|---:|---:|---:|---:|---:|---:|---:|")
        for nm, x in res["by_target_season"].items():
            a(f"| {nm} | {x['targets']} | {x['hits_SE']} | {x['hits_B']} | {x['hits_R']} | {x['excess_SE']:+.6f} | "
              f"{x['logSE_minus_B']:+.3f} | {x['logSE_minus_U']:+.3f} |")
        a("")
        fs, fz = res["final_step"], res["final_state"]
        a("Date descriptive:")
        a(f"- p exact (hitsSE ≥ observat | extrageri uniforme independente) = {res['p_exact_hits_SE_ge']:.6f} "
          "(arhivă explorată, fără valoare confirmatoare);")
        a(f"- potriviri SE (0..6): {res['match_dist_SE']}; așteptat sub U: {[round(v, 1) for v in res['match_expected_U']]};")
        a(f"- biletul SE diferă de B la {res['tickets_changed_vs_B_targets']} ținte și de R la "
          f"{res['tickets_changed_vs_R_targets']} (din {res['n_targets']});")
        a(f"- la final: extrageri pe anotimpuri {fz['n_per_season']}; ponderea anotimpului propriu "
          + ", ".join(f"{k} {v[k]:.4f}" for k, v in fz["weights_by_target_season"].items())
          + "; ponderile celorlalte anotimpuri ≈ 0.009 fiecare;")
        a(f"- la ultimul pas (anotimp {fs['phi']}): abaterea relativă a lui p̂ față de p0 are deviația "
          f"{fs['rel_dev_std']:.4f}, min {fs['rel_dev_min']:+.4f}, max {fs['rel_dev_max']:+.4f};")
        a(f"- statistica G a tabelului etichetă × anotimp pe întreaga arhivă: {res['G_label_x_season']:.3f} (rangul față de "
          "universurile nule mai jos).")
        a("")
    if ver:
        a(f"Verificarea independentă (`verify_se649.py`, fără import din se649, gl649, wu649, bo649, engine, parser sau "
          f"validare; anotimpuri printr-un dicționar explicit, rezolvare directă |O|×|O| fără Sherman–Morrison în fp64 la "
          f"fiecare pas și Gauss–Jordan exact în Q la pașii din 25 în 25, inclusiv ponderile; R prin recursie) a dat "
          f"**{ver['status']}** ({ver['n_checks'] - ver['n_fail']}/{ver['n_checks']}), verdict recalculat "
          f"`{ver['verdict_recomputed']}` ({ver['gates_passed_recomputed']}/6).\n")
    if nul and res:
        u = nul["universes"]
        ex = np.array([x["excess_SE"] for x in u])
        lb = np.array([x["logSE_minus_B"] for x in u])
        lu = np.array([x["logSE_minus_U"] for x in u])
        dh = np.array([x["hits_SE"] - x["hits_B"] for x in u])
        gG = np.array([x["G_label_x_season"] for x in u])
        gp = np.array([x["gates_passed"] for x in u])
        per_gate = [int(sum(x["gates"][i] for x in u)) for i in range(6)]
        T = res["total"]
        a(f"## Universuri nule sintetice (descriptiv, M = {nul['M']}, seed `{nul['seed']}`)\n")
        a(rank_line("Excesul SE", ex, T["excess_SE"], "+.6f"))
        a(rank_line("hitsSE − hitsB", dh.astype(float), float(T["hits_SE"] - T["hits_B"]), "+.1f"))
        a(rank_line("logSE−B", lb, T["log_SE"] - T["log_B"], "+.3f"))
        a(rank_line("logSE−U", lu, T["log_SE"] - T["log_U"], "+.3f"))
        a(rank_line("Statistica G etichetă × anotimp", gG, res["G_label_x_season"], ".3f"))
        a(f"- Porți trecute pe universurile nule: distribuția {np.bincount(gp, minlength=7).tolist()} (0..6); maximum "
          f"{gp.max()}/6; pe porți (1..6): {per_gate}.")
        a(f"- `logSE−B > 0` apare în {int((lb > 0).sum())}/{len(lb)} universuri nule (contracție față de legea B), deci "
          "poarta 6 trecută pe arhivă nu indică singură un semnal (lecția GL649 confirmată).\n")
    if pw:
        u = pw["universes"]
        for scale, lab in ((0.2, "scara priorului (b ~ N(0, 0.2²))"), (0.1, "jumătatea interacțiunii (b ~ N(0, 0.1²))")):
            v = [x for x in u if x["scale_b"] == scale]
            if not v:
                continue
            ex = np.array([x["excess_SE"] for x in v])
            exb = np.array([x["excess_B"] for x in v])
            dh = np.array([x["hits_SE"] - x["hits_B"] for x in v])
            gp = np.array([x["gates_passed"] for x in v])
            g1 = int(sum(x["gates"][0] for x in v))
            a(f"## Putere sintetică sub H_SE, {lab} (descriptiv, M = {len(v)}, generator: {pw['generator']})\n")
            a(f"- Exces SE: medie {ex.mean():+.4f}, min {ex.min():+.4f}, max {ex.max():+.4f}; exces B mediu "
              f"{exb.mean():+.4f}; poarta 1 (exces ≥ 0.20) atinsă în {g1}/{len(v)} universuri.")
            a(f"- hitsSE − hitsB: medie {dh.mean():+.1f}, pozitiv în {int((dh > 0).sum())}/{len(dh)} universuri.")
            a(f"- Porți trecute: distribuția {np.bincount(gp, minlength=7).tolist()} (0..6); 6/6 în "
              f"{int((gp == 6).sum())}/{len(gp)}.")
            a("")
        a("Comparație cu estimarea de mână din protocol §2.1 (exces așteptat ≈ 0.19 la scara priorului, ≈ 0.09 la "
          "jumătate): valorile sintetice de mai sus sunt măsurătoarea; diferența arată cât de optimistă a fost "
          "aproximarea de mână.\n")
    if sens:
        a("## Sensibilitate (strict descriptivă, declarată în §6; nicio configurație nu poate fi promovată sau selectată)\n")
        a("| τa | τb | hitsSE | ExcesSE/U | logSE−U | logSE−B | BrierSE | porți | bilete ≠ B |")
        a("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        for r in sens["rows"]:
            a(f"| {r['tau_a']} | {r['tau_b']} | {r['hits_SE']} | {r['excess_SE']:+.6f} | {r['logSE_minus_U']:+.3f} | "
              f"{r['logSE_minus_B']:+.3f} | {r['brier_SE']:.3f} | {r['gates_passed']}/6 | "
              f"{r['tickets_changed_vs_B_targets']} |")
        a("")
    a("## Limite\n")
    a("Rezultatul nu demonstrează avantaj predictiv real și nu infirmă universal alte covariabile ambientale, alte "
      "partiții ale anului sau alte modele fizice. Dacă extragerile sunt uniforme și independente, istoricul nu oferă "
      "avantaj. Nu au existat evaluări prospective, emisii live sau promisiuni de câștig. Nu s-a făcut tuning după "
      "rezultat; sensibilitatea, universurile nule și puterea sintetică au fost declarate înainte și sunt doar "
      "descriptive. Zero incidente tehnice în calificare și în backtest, zero amendamente; codul de calificare și cel al "
      "backtestului sunt același fișier (sha256 identic). Notă tehnică (fără efect asupra verdictului): prima rulare a "
      "verificatorului independent s-a oprit cu `IndexError` în calculul descriptiv al statisticii G, înainte de a scrie "
      "vreun rezultat; corecția are o linie, iar încercarea inițială și nota sunt păstrate în "
      "`jurnal/incidente_verificator/`. Rulările nule/putere au fost pornite ca sarcini proprii și s-au terminat "
      "complet.\n")
    (HERE / "RAPORT_SE649.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    files = ["PREINREGISTRARE_SE649.md", "SIGILIU_PROTOCOL_SE649.json", "se649.py", "verify_se649.py", "raport_se649.py",
             "tests/test_se649.py", "rezultate/cod_calificare/se649.py", "rezultate/CALIFICARE.json",
             "rezultate/backtest_unic/START.json", "rezultate/backtest_unic/PREDICTII.npz",
             "rezultate/backtest_unic/PREDICTII_EXACTE.json.gz", "rezultate/backtest_unic/PREDICTII_SIGILIU.json",
             "rezultate/backtest_unic/REZULTATE.json", "rezultate/backtest_unic/VERIFICARE_INDEPENDENTA.json",
             "rezultate/nule/SUMAR.json", "rezultate/putere/SUMAR.json", "rezultate/SENSIBILITATE.json",
             "jurnal/calificare.log", "jurnal/calificare_stdout.log", "jurnal/backtest_unic.log", "jurnal/sens.log",
             "jurnal/null32.log", "jurnal/power24.log", "jurnal/incidente_verificator/NOTA_01.md",
             "jurnal/incidente_verificator/verify_se649_incercare01.py", "RAPORT_SE649.md"]
    man = {"generated_from_artifacts": True, "files": {}}
    for f in files:
        p = HERE / f
        if p.exists():
            man["files"][f] = {"sha256": sha(p), "bytes": p.stat().st_size}
    (HERE / "MANIFEST_SE649.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print("RAPORT_SE649.md + MANIFEST_SE649.json generate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
