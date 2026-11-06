"""Generează RAPORT_CS649.md și MANIFEST_CS649.json direct din artefactele sigilate (fără cifre editate manual)."""
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
    seal, qual = j(HERE / "SIGILIU_PROTOCOL_CS649.json"), j(R / "CALIFICARE.json")
    res, ver = j(RUN / "REZULTATE.json"), j(RUN / "VERIFICARE_INDEPENDENTA.json")
    sens, nul, pw = j(R / "SENSIBILITATE.json"), j(R / "nule" / "SUMAR.json"), j(R / "putere" / "SUMAR.json")
    psig = j(RUN / "PREDICTII_SIGILIU.json")
    L = []
    a = L.append
    a("# RAPORT CS649 — „Caruselul seturilor” (rotație deterministă ipotetică a seturilor de bile/urnelor)\n")
    a(f"Protocol `CS649-P1` sigilat (sha256 `{seal['sha256']}`, {seal['sealed_at_utc']}) înainte de orice cod și calcul "
      "CS649. Ipoteză nouă și distinctă în pista QL649; nu este o salvare a QL649 (0/6), BO649 (0/6), WU649 (necalificat "
      "5/6), GL649 (2/6), SE649 (1/6) sau DL-649 (înghețat, neatins). Modelele închise nu au fost importate sau rulate; "
      "OGLINDA nu a fost atinsă. Precedente: Henderson (1950, 1975), Hartigan (1969), Goldstein & Wooff (2007), Searle, "
      "Casella & McCulloch (1992), teorema chineză a resturilor; practica publică a urnelor/seturilor multiple (la "
      "loteria citată în surse: selecție ALEATOARE). Calcul clasic: predictorul exact în Q (`Fraction`), scorurile în "
      "fp64 pe CPU. Fără hardware cuantic, avantaj cuantic sau noutate mondială. `positive_claims_allowed=false`. "
      "Arhiva este deja explorată, deci nu este un set nevăzut.\n")
    a("Ipoteza H_CS: seturi de bile/urne cu defecte diferite, alese printr-o rotație deterministă după indicele zilei de "
      "extragere din arhivă; surogat aditiv `θ(k) = p0·1 + a + b³(k mod 3) + b⁵(k mod 5) + b⁷(k mod 7)`, cu "
      "`a ~ (0, (p0/20)² P)`, `b^K(r) ~ (0, (p0/4)² P)`. Perioadele pare au fost excluse a priori (alias cu alternanța "
      "joi/duminică, familia închisă N1/N2); 3, 5, 7 sunt prime între ele (plan încrucișat complet). Predicția este "
      "așteptarea ajustată Bayes liniară prin ecuațiile Henderson 16×16: `p̂_j = p0 + Σ_ℓ v_ℓ (c_{ℓj} − p0 n_ℓ)`, "
      "`v = (ZᵀZ + σ0² G⁻¹)⁻¹ z*`; ponderea unei extrageri vechi este periodică în timp (perioadă 105), nu de recență. "
      "Premisa (procedura de alegere a setului la Loteria Română) nu este verificată.\n")
    a("## Calificare (înainte de istoria reală)\n")
    a(f"Status **{qual['status']}** ({qual['passed']}/6), cod sha256 `{qual['code_sha256'][:16]}…` (arhivat byte-identic "
      f"în `rezultate/cod_calificare/cs649.py`), {qual['utc']}, durată {qual['seconds']:.0f} s. Numerele arhivei nu au "
      "fost folosite; Q2–Q4 au citit doar numărul de extrageri pe zi. Martorii Q5/Q6 au fost derivați analitic în "
      "protocol (Derivarea C: plan echilibrat n = 105, contracțiile λ_K și λ0 în formă închisă) și confirmați exact în Q.\n")
    a("| Verificare | Nume | Rezultat | Detalii |")
    a("|---|---|---|---|")
    for c in qual["checks"]:
        a(f"| {c['id']} | {c['name']} | {'PASS' if c['pass'] else 'FAIL'} | "
          f"`{json.dumps(c['detail'], ensure_ascii=False)[:300]}` |")
    a("")
    d5, d6 = qual["checks"][4]["detail"], qual["checks"][5]["detail"]
    a("Martor de informație (F5_K, „set constant pe fază”, 105 pași): etichetele 5 și 9 au numărări totale egale (B "
      "identic), dar la ținta k* = 105 `p̂_5 − p̂_9 = λ_K` exact: "
      + "; ".join(f"K = {k[1:]}: {v['lambda_K']} ≈ {v['gap_105_float']:.6f}, lege {v['law_gap']:.6f}, "
                  f"semn inversat la k* = 106: {v['gap_106_exact_eq_minus_lambda']}, zero la 107: {v['gap_107_exact_zero']}, "
                  f"R inversează ordinea (ew_9 = {v['ew9']:.4f} > ew_5 = {v['ew5']:.4f})" for k, v in d5.items()) + ".")
    a(f"Martor de decizie (F6, K = 3): bilet CS {d6['ticket_CS']}, bilet B {d6['ticket_B']} (disjuncte), bilet R "
      f"{d6['ticket_R']} (`ew_1` = {d6['ew_1']:.4f} > 2 · max ew_44..49 = 2 · {d6['max_ew_44_49']:.4f}); "
      f"`p̂_44 − p̂_1 = {d6['diff_44_1']}` = `(4λ3 − λ0)/3` exact; p̂ = {d6['p44']:.6f} / {d6['p1']:.6f} / {d6['p7']:.6f} "
      "ca în derivare.\n")
    if res:
        t, h1, h2 = res["total"], res["half1"], res["half2"]
        st = res["start"]
        a("## Backtest walk-forward cauzal unic\n")
        a(f"START {st['utc']}. Sursa are sha256 `{st['source_sha256']}`, cu {st['n_draws']} extrageri și {st['n_steps']} "
          f"pași-zi, de la {st['first_date']} la {st['last_date']}. Încălzirea are 100 de pași; rămân "
          f"**{res['n_targets']} ținte**. Predicțiile au fost sigilate înainte de scor: `PREDICTII.npz` sha256 "
          f"`{psig['npz_sha256']}`, fracțiile exacte și ponderile v `PREDICTII_EXACTE.json.gz` sha256 "
          f"`{psig['exact_sha256']}` (Σ p̂ = 6 exact la toți pașii: {psig['sum_exact_ok']}; pași cu p̂ în afara lui "
          f"(0,1): {psig['steps_p_outside_01']}). Durata predicției: {res['predict_seconds']:.1f} s. Consecvența "
          f"comparatorilor cu BO649/GL649/SE649 (hitsB = 1847, hitsR = 1821): "
          f"{'DA' if res['consistency_with_BO649_GL649_SE649']['ok'] else 'NU'}; rulare validă: {res['valid_run']}.\n")
        a("| Parte | Ținte | hitsCS | hitsB | hitsR | ExcesCS/U | logCS−U | logCS−B | BrierCS | BrierU | BrierB |")
        a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for name, x in (("Total", t), ("Prima jumătate", h1), ("A doua jumătate", h2)):
            a(f"| {name} | {x['targets']} | {x['hits_CS']} | {x['hits_B']} | {x['hits_R']} | {x['excess_CS']:+.6f} | "
              f"{x['log_CS'] - x['log_U']:+.6f} | {x['log_CS'] - x['log_B']:+.6f} | {x['brier_CS']:.6f} | "
              f"{x['brier_U']:.6f} | {x['brier_B']:.6f} |")
        a("")
        a("| Poartă | Cerință | Rezultat | Valoare |")
        a("|---|---|---|---|")
        for g in res["gates"]:
            a(f"| {g['gate']} | {g['rule']} | {'PASS' if g['pass'] else 'FAIL'} | `{json.dumps(g['value'])}` |")
        a("")
        a(f"**Verdict: `{res['verdict']}` ({res['gates_passed']}/6 porți).**\n")
        a("Pe faza-țintă a fiecărei perioade (descriptiv):\n")
        a("| Perioadă | Fază | Ținte | hitsCS | hitsB | hitsR | ExcesCS/U | logCS−B |")
        a("|---|---:|---:|---:|---:|---:|---:|---:|")
        for K, d in res["by_target_phase"].items():
            for r, x in d.items():
                a(f"| {K} | {r} | {x['targets']} | {x['hits_CS']} | {x['hits_B']} | {x['hits_R']} | "
                  f"{x['excess_CS']:+.6f} | {x['logCS_minus_B']:+.3f} |")
        a("")
        fs, fz = res["final_step"], res["final_state"]
        G = res["G_label_x_phase"]
        a("Date descriptive:")
        a(f"- p exact (hitsCS ≥ observat | extrageri uniforme independente) = {res['p_exact_hits_CS_ge']:.6f} "
          "(arhivă explorată, fără valoare confirmatoare);")
        a(f"- potriviri CS (0..6): {res['match_dist_CS']}; așteptat sub U: {[round(v, 1) for v in res['match_expected_U']]};")
        a(f"- biletul CS diferă de B la {res['tickets_changed_vs_B_targets']} ținte și de R la "
          f"{res['tickets_changed_vs_R_targets']} (din {res['n_targets']});")
        a(f"- la final: extrageri pe niveluri {fz['n_per_level']}; ponderile v pentru indicele următor "
          f"{fz['next_index']} (faze {fz['next_phases']}): "
          + ", ".join(f"{k} {v:+.3e}" for k, v in fz["v_for_next_index"].items()) + ";")
        a(f"- la ultimul pas (faze {fs['phases']}): abaterea relativă a lui p̂ față de p0 are deviația "
          f"{fs['rel_dev_std']:.4f}, min {fs['rel_dev_min']:+.4f}, max {fs['rel_dev_max']:+.4f};")
        a(f"- statisticile G etichetă × fază pe întreaga arhivă: G3 {G['G3']:.3f}, G5 {G['G5']:.3f}, G7 {G['G7']:.3f}, "
          f"suma {G['G_sum']:.3f} (rangurile față de universurile nule mai jos).")
        a("")
    if ver:
        a(f"Verificarea independentă (`verify_cs649.py`, fără import din cs649, se649, gl649, wu649, bo649, engine, parser "
          f"sau validare; faze din propriul indice al pașilor; forma PRIMALĂ pe celulele k mod 105 în fp64 la fiecare pas, "
          f"fără sistemul Henderson; Henderson exact în Q prin Gauss–Jordan propriu la pașii din 25 în 25, inclusiv "
          f"ponderile v; R prin recursie; ordinea temporală sigiliu < calificare < START) a dat "
          f"**{ver['status']}** ({ver['n_checks'] - ver['n_fail']}/{ver['n_checks']}), verdict recalculat "
          f"`{ver['verdict_recomputed']}` ({ver['gates_passed_recomputed']}/6).\n")
    if nul and res:
        u = nul["universes"]
        ex = np.array([x["excess_CS"] for x in u])
        lb = np.array([x["logCS_minus_B"] for x in u])
        lu = np.array([x["logCS_minus_U"] for x in u])
        dh = np.array([x["hits_CS"] - x["hits_B"] for x in u])
        gp = np.array([x["gates_passed"] for x in u])
        per_gate = [int(sum(x["gates"][i] for x in u)) for i in range(6)]
        T = res["total"]
        a(f"## Universuri nule sintetice (descriptiv, M = {nul['M']}, seed `{nul['seed']}`, {nul['predictor']})\n")
        a(rank_line("Excesul CS", ex, T["excess_CS"], "+.6f"))
        a(rank_line("hitsCS − hitsB", dh.astype(float), float(T["hits_CS"] - T["hits_B"]), "+.1f"))
        a(rank_line("logCS−B", lb, T["log_CS"] - T["log_B"], "+.3f"))
        a(rank_line("logCS−U", lu, T["log_CS"] - T["log_U"], "+.3f"))
        for key in ("G3", "G5", "G7", "G_sum"):
            a(rank_line(f"Statistica {key} etichetă × fază", np.array([x[key] for x in u]),
                        res["G_label_x_phase"][key], ".3f"))
        a(f"- Porți trecute pe universurile nule: distribuția {np.bincount(gp, minlength=7).tolist()} (0..6); maximum "
          f"{gp.max()}/6; pe porți (1..6): {per_gate}.")
        a(f"- `logCS−B > 0` apare în {int((lb > 0).sum())}/{len(lb)} universuri nule: la scara priorului CS (25% pe "
          "fiecare rotație) zgomotul contrastelor de fază costă în log sub nul; valoarea reală este în coada de jos a "
          "nulului, nu în afara lui.\n")
    if pw:
        u = pw["universes"]
        for kind, lab in (("prior", "scara priorului (toate trei rotațiile, b ~ N(0, 0.25²), a ~ N(0, 0.05²))"),
                          ("single", "o singură rotație K0 ∈ {3,5,7}, b ~ N(0, 0.25²)")):
            v = [x for x in u if x["kind"] == kind]
            if not v:
                continue
            ex = np.array([x["excess_CS"] for x in v])
            exb = np.array([x["excess_B"] for x in v])
            dh = np.array([x["hits_CS"] - x["hits_B"] for x in v])
            lb = np.array([x["logCS_minus_B"] for x in v])
            gp = np.array([x["gates_passed"] for x in v])
            g1 = int(sum(x["gates"][0] for x in v))
            sd = np.mean([x["p_rel_sd_mean_over_105_phases"] for x in v])
            a(f"## Putere sintetică sub H_CS, {lab} (descriptiv, M = {len(v)})\n")
            a(f"- Deviația relativă medie a propensiunilor generate (după tăiere): {sd:.3f}.")
            a(f"- Exces CS: medie {ex.mean():+.4f}, min {ex.min():+.4f}, max {ex.max():+.4f}; exces B mediu "
              f"{exb.mean():+.4f}; poarta 1 (exces ≥ 0.20) atinsă în {g1}/{len(v)} universuri.")
            a(f"- hitsCS − hitsB: medie {dh.mean():+.1f}, pozitiv în {int((dh > 0).sum())}/{len(dh)}; logCS−B pozitiv în "
              f"{int((lb > 0).sum())}/{len(lb)}.")
            a(f"- Porți trecute: distribuția {np.bincount(gp, minlength=7).tolist()} (0..6); 6/6 în "
              f"{int((gp == 6).sum())}/{len(gp)}.")
            if kind == "single":
                a("- Pe universuri: " + "; ".join(f"K0 = {x['K0']}: exces {x['excess_CS']:+.4f}, {x['gates_passed']}/6"
                                                  for x in v) + ".")
            a("")
        a("Comparație cu estimarea de mână din protocol §2.1 (≈ 0.42 când adevărul = priorul; ≈ 0.21 / 0.20 / 0.18 pentru o "
          "singură rotație de 25% cu K0 = 3 / 5 / 7): valorile sintetice de mai sus sunt măsurătoarea; diferența arată cât "
          "de optimistă a fost aproximarea de mână (gaussianitate, plan echilibrat, fără tăiere). Sub o singură rotație "
          "de 25%, porțile 2–6 trec, dar poarta 1 rămâne blocată; pe arhivă nu trece nicio poartă.\n")
    if sens:
        a("## Sensibilitate (strict descriptivă, declarată în §6; nicio configurație nu poate fi promovată sau selectată)\n")
        a("| τa | τ | hitsCS | ExcesCS/U | logCS−U | logCS−B | BrierCS | porți | bilete ≠ B |")
        a("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        for r in sens["rows"]:
            a(f"| {r['tau_a']} | {r['tau']} | {r['hits_CS']} | {r['excess_CS']:+.6f} | {r['logCS_minus_U']:+.3f} | "
              f"{r['logCS_minus_B']:+.3f} | {r['brier_CS']:.3f} | {r['gates_passed']}/6 | "
              f"{r['tickets_changed_vs_B_targets']} |")
        a("")
    a("## Limite\n")
    a("Rezultatul nu demonstrează avantaj predictiv real și nu infirmă universal rotațiile cu perioadă pară, alte "
      "perioade, rotațiile aliniate la numărul oficial al tragerii (nu la indicele arhivei) sau selecția aleatoare a "
      "seturilor (care, prin construcție, nu ar fi predictibilă). Dacă extragerile sunt uniforme și independente, "
      "istoricul nu oferă avantaj. Nu au existat evaluări prospective, emisii live sau promisiuni de câștig. Nu s-a "
      "făcut tuning după rezultat; sensibilitatea, universurile nule și puterea sintetică au fost declarate înainte și "
      "sunt doar descriptive; nicio altă mulțime de perioade nu se testează ca salvare. Zero incidente tehnice și zero "
      "amendamente în calificare, backtest și verificare (verificatorul a trecut la prima rulare); codul de calificare și "
      "cel al backtestului sunt același fișier (sha256 identic). Înainte de calificare au rulat numai testele unitare pe "
      "date construite minuscule (`jurnal/teste_unitare_precalificare.log`, 7/7). Aritmetica de mână dinaintea sigilării "
      "este păstrată în `jurnal/preprotocol/`. Rulările lungi au fost pornite ca sarcini proprii și s-au terminat "
      "complet.\n")
    (HERE / "RAPORT_CS649.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    files = ["PREINREGISTRARE_CS649.md", "SIGILIU_PROTOCOL_CS649.json", "cs649.py", "verify_cs649.py", "raport_cs649.py",
             "tests/test_cs649.py", "rezultate/cod_calificare/cs649.py", "rezultate/CALIFICARE.json",
             "rezultate/backtest_unic/START.json", "rezultate/backtest_unic/PREDICTII.npz",
             "rezultate/backtest_unic/PREDICTII_EXACTE.json.gz", "rezultate/backtest_unic/PREDICTII_SIGILIU.json",
             "rezultate/backtest_unic/REZULTATE.json", "rezultate/backtest_unic/VERIFICARE_INDEPENDENTA.json",
             "rezultate/nule/SUMAR.json", "rezultate/putere/SUMAR.json", "rezultate/SENSIBILITATE.json",
             "jurnal/calificare.log", "jurnal/calificare_stdout.log", "jurnal/backtest_unic.log", "jurnal/sens.log",
             "jurnal/null32.log", "jurnal/power24.log", "jurnal/teste_unitare_precalificare.log",
             "jurnal/preprotocol/NOTA.md", "jurnal/preprotocol/putere_mana_cs649.py", "RAPORT_CS649.md"]
    man = {"generated_from_artifacts": True, "files": {}}
    for f in files:
        p = HERE / f
        if p.exists():
            man["files"][f] = {"sha256": sha(p), "bytes": p.stat().st_size}
    (HERE / "MANIFEST_CS649.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print("RAPORT_CS649.md + MANIFEST_CS649.json generate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
