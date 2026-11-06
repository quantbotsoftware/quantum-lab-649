"""Generează RAPORT_GL649.md și MANIFEST_GL649.json direct din artefactele sigilate (fără cifre editate manual)."""
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
    seal, qual = j(HERE / "SIGILIU_PROTOCOL_GL649.json"), j(R / "CALIFICARE.json")
    res, ver = j(RUN / "REZULTATE.json"), j(RUN / "VERIFICARE_INDEPENDENTA.json")
    sens, nul, pw = j(R / "SENSIBILITATE.json"), j(R / "nule" / "SUMAR.json"), j(R / "putere" / "SUMAR.json")
    psig = j(RUN / "PREDICTII_SIGILIU.json")
    L = []
    a = L.append
    a("# RAPORT GL649 — „Masa glifelor” (Bayes liniar exact pe structura cifrelor tipărite)\n")
    a(f"Protocol `GL649-P1` sigilat (sha256 `{seal['sha256']}`, {seal['sealed_at_utc']}) înainte de orice cod și calcul "
      "GL649. Ipoteză nouă și distinctă în pista QL649; nu este o salvare a QL649 (0/6), BO649 (0/6), WU649 (necalificat "
      "5/6) sau DL-649 (înghețat, neatins). Modelele închise nu au fost importate sau rulate; OGLINDA nu a fost atinsă. "
      "Precedente: Hartigan (1969), Goldstein & Wooff (2007), Henderson (1950, 1975), Robinson (1991), Woodbury (1950), "
      "Fienberg (1971); ideea „cernelii mai grele” este folclor. Calcul clasic: predictorul exact în Q (`Fraction`), "
      "scorurile în fp64 pe CPU. Fără hardware cuantic, avantaj cuantic sau noutate mondială. "
      "`positive_claims_allowed=false`. Arhiva este deja explorată, deci nu este un set nevăzut.\n")
    a("Ipoteza H_GL: propensiunea bilei j = `p0 + [P(Gγ + ε)]_j`, cu `G` incidența glifelor zecimale (fixă, a priori), "
      "`γ_d ~ (0, (p0/10)²)`, `ε_j ~ (0, (p0/20)²)`; predicția este așteptarea ajustată Bayes liniară cu covarianța exactă "
      "a eșantionării 6-din-49 la p0, `p̂ = x − ν z` (Woodbury), cu `Σ p̂ = 6` exact. Premisa fizică (cerneală, vopsea, "
      "gravură) nu este verificată pentru bilele Loteriei Române.\n")
    a("## Calificare (înainte de istoria reală)\n")
    a(f"Status **{qual['status']}** ({qual['passed']}/6), cod sha256 `{qual['code_sha256'][:16]}…` (arhivat byte-identic "
      f"în `rezultate/cod_calificare/gl649.py`), {qual['utc']}, durată {qual['seconds']:.0f} s. Numerele arhivei nu au "
      "fost folosite; Q2 a citit doar structura pașilor. Martorii Q5/Q6 au fost derivați analitic în protocol "
      "(Derivarea A: sectorul antisimetric 7↔8, valori proprii λ0, λ1 în formă închisă) și confirmați exact în Q.\n")
    a("| Verificare | Nume | Rezultat | Detalii |")
    a("|---|---|---|---|")
    for c in qual["checks"]:
        a(f"| {c['id']} | {c['name']} | {'PASS' if c['pass'] else 'FAIL'} | "
          f"`{json.dumps(c['detail'], ensure_ascii=False)[:300]}` |")
    a("")
    d5, d6 = qual["checks"][4]["detail"], qual["checks"][5]["detail"]
    a(f"Martor de informație (F5, n = {d5['n']}): etichetele 17 și 19 au numărări egale (B identic), dar "
      f"`p̂_17 − p̂_19 = {d5['gap_float']:.6e}` = forma închisă `12(λ1−λ0)/(5n)` exact, cu λ0 = {d5['lambda0']:.6f}, "
      f"λ1 = {d5['lambda1']:.6f}; diferența în lege = {d5['law_gap']:.6e} ≥ 1e-3.")
    a(f"Martor de decizie (F6): bilet GL {d6['ticket_GL']}, bilet B {d6['ticket_B']}, bilet R {d6['ticket_R']} "
      f"(`ew_1` = {d6['ew_1']:.4f} ≤ marginea {d6['ew_1_bound']:.4f} < 1 ≤ min ew pe ultima extragere = "
      f"{d6['min_ew_last_draw']:.4f}). Anticiparea analitică a fost confirmată exact.\n")
    if res:
        t, h1, h2 = res["total"], res["half1"], res["half2"]
        st = res["start"]
        a("## Backtest walk-forward cauzal unic\n")
        a(f"START {st['utc']}. Sursa are sha256 `{st['source_sha256']}`, cu {st['n_draws']} extrageri și {st['n_steps']} "
          f"pași-zi, de la {st['first_date']} la {st['last_date']}. Încălzirea are 100 de pași; rămân "
          f"**{res['n_targets']} ținte**. Predicțiile au fost sigilate înainte de scor: `PREDICTII.npz` sha256 "
          f"`{psig['npz_sha256']}`, fracțiile exacte `PREDICTII_EXACTE.json.gz` sha256 `{psig['exact_sha256']}` "
          f"(Σ p̂ = 6 exact la toți pașii: {psig['sum_exact_ok']}). Durata predicției: {res['predict_seconds']:.1f} s. "
          f"Consecvența comparatorilor cu BO649 (hitsB = 1847, hitsR = 1821): "
          f"{'DA' if res['consistency_with_BO649']['ok'] else 'NU'}; rulare validă: {res['valid_run']}.\n")
        a("| Parte | Ținte | hitsGL | hitsB | hitsR | ExcesGL/U | logGL−U | logGL−B | BrierGL | BrierU | BrierB |")
        a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for name, x in (("Total", t), ("Prima jumătate", h1), ("A doua jumătate", h2)):
            a(f"| {name} | {x['targets']} | {x['hits_GL']} | {x['hits_B']} | {x['hits_R']} | {x['excess_GL']:+.6f} | "
              f"{x['log_GL'] - x['log_U']:+.6f} | {x['log_GL'] - x['log_B']:+.6f} | {x['brier_GL']:.6f} | "
              f"{x['brier_U']:.6f} | {x['brier_B']:.6f} |")
        a("")
        a("| Poartă | Cerință | Rezultat | Valoare |")
        a("|---|---|---|---|")
        for g in res["gates"]:
            a(f"| {g['gate']} | {g['rule']} | {'PASS' if g['pass'] else 'FAIL'} | `{json.dumps(g['value'])}` |")
        a("")
        a(f"**Verdict: `{res['verdict']}` ({res['gates_passed']}/6 porți).**\n")
        fs = res["final_step"]
        a("Date descriptive:")
        a(f"- p exact (hitsGL ≥ observat | extrageri uniforme independente) = {res['p_exact_hits_GL_ge']:.6f} "
          "(arhivă explorată, fără valoare confirmatoare);")
        a(f"- potriviri GL (0..6): {res['match_dist_GL']}; așteptat sub U: {[round(v, 1) for v in res['match_expected_U']]};")
        a(f"- biletul GL diferă de B la {res['tickets_changed_vs_B_targets']} ținte și de R la "
          f"{res['tickets_changed_vs_R_targets']} (din {res['n_targets']});")
        a(f"- la ultimul pas: abaterea relativă a lui p̂ față de p0 are deviația {fs['rel_dev_std']:.4f}, min "
          f"{fs['rel_dev_min']:+.4f}, max {fs['rel_dev_max']:+.4f}; Spearman(p̂, numărări) = "
          f"{fs['spearman_p_vs_counts_prefix']:.4f};")
        a(f"- efecte de glifă ajustate γ̂/p0 (cifrele 0..9): {[round(g, 4) for g in res['gamma_last_relative']]} "
          "(descriptiv; nivelul comun este identificat numai prin contrastul etichete cu o glifă / cu două glife).")
        a("")
    if ver:
        a(f"Verificarea independentă (`verify_gl649.py`, fără import din gl649, wu649, bo649, engine, parser sau "
          f"validare; rezolvare directă 49×49 fără Woodbury în fp64 la fiecare pas și Gauss–Jordan exact în Q la pașii "
          f"din 25 în 25; R prin recursie) a dat **{ver['status']}** ({ver['n_checks'] - ver['n_fail']}/{ver['n_checks']}), "
          f"verdict recalculat `{ver['verdict_recomputed']}` ({ver['gates_passed_recomputed']}/6).\n")
    if nul and res:
        u = nul["universes"]
        ex = np.array([x["excess_GL"] for x in u])
        lb = np.array([x["logGL_minus_B"] for x in u])
        lu = np.array([x["logGL_minus_U"] for x in u])
        dh = np.array([x["hits_GL"] - x["hits_B"] for x in u])
        gp = np.array([x["gates_passed"] for x in u])
        T = res["total"]
        a(f"## Universuri nule sintetice (descriptiv, M = {nul['M']}, seed `{nul['seed']}`)\n")
        a(rank_line("Excesul GL", ex, T["excess_GL"], "+.6f"))
        a(rank_line("hitsGL − hitsB", dh.astype(float), float(T["hits_GL"] - T["hits_B"]), "+.1f"))
        a(rank_line("logGL−B", lb, T["log_GL"] - T["log_B"], "+.3f"))
        a(rank_line("logGL−U", lu, T["log_GL"] - T["log_U"], "+.3f"))
        a(f"- Porți trecute pe universurile nule: distribuția {np.bincount(gp, minlength=7).tolist()} (0..6); maximum "
          f"{gp.max()}/6.")
        a("- Observație: `logGL−B > 0` apare și sub nul (contracția Bayes liniară față de legea B), deci poarta 6 "
          "trecută pe arhivă nu indică singură un semnal.\n")
    if pw:
        u = pw["universes"]
        ex = np.array([x["excess_GL"] for x in u])
        dh = np.array([x["hits_GL"] - x["hits_B"] for x in u])
        gp = np.array([x["gates_passed"] for x in u])
        a(f"## Putere sintetică sub H_GL (descriptiv, M = {pw['M']}, seed `{pw['seed']}`, generator: {pw['generator']})\n")
        a(f"- Exces GL: medie {ex.mean():+.4f}, min {ex.min():+.4f}, max {ex.max():+.4f}; universuri cu exces ≥ 0.20: "
          f"{int((ex >= 0.20).sum())}/{len(ex)}.")
        a(f"- hitsGL − hitsB: medie {dh.mean():+.1f}, pozitiv în {int((dh > 0).sum())}/{len(dh)} universuri.")
        a(f"- Porți trecute: distribuția {np.bincount(gp, minlength=7).tolist()} (0..6); 6/6 în "
          f"{int((gp == 6).sum())}/{len(gp)}.")
        a(f"- Sub H_GL la scara priorului, poarta 1 (exces ≥ 0.20) a fost atinsă în {int((ex >= 0.20).sum())}/{len(ex)} "
          "universuri: porțile, fixate înainte, sunt foarte exigente pentru efecte de această mărime.\n")
    if sens:
        a("## Sensibilitate (strict descriptivă, declarată în §6; nicio configurație nu poate fi promovată sau selectată)\n")
        a("| s_g | s_e | hitsGL | ExcesGL/U | logGL−U | logGL−B | BrierGL | porți | bilete ≠ B |")
        a("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        for r in sens["rows"]:
            a(f"| {r['s_g']} | {r['s_e']} | {r['hits_GL']} | {r['excess_GL']:+.6f} | {r['logGL_minus_U']:+.3f} | "
              f"{r['logGL_minus_B']:+.3f} | {r['brier_GL']:.3f} | {r['gates_passed']}/6 | {r['tickets_changed_vs_B_targets']} |")
        a("")
    a("## Limite\n")
    a("Rezultatul nu demonstrează avantaj predictiv real și nu infirmă universal alte structuri pe etichete sau alte "
      "modele fizice. Dacă extragerile sunt uniforme și independente, istoricul nu oferă avantaj. Nu au existat evaluări "
      "prospective, emisii live sau promisiuni de câștig. Nu s-a făcut tuning după rezultat; sensibilitatea, universurile "
      "nule și puterea sintetică au fost declarate înainte și sunt doar descriptive. Zero incidente tehnice în calificare "
      "și în backtest, zero amendamente; codul de calificare și cel al backtestului sunt același fișier (sha256 identic). "
      "Notă de proces (descriptiv, fără efect asupra verdictului): prima pornire a rulărilor nule/putere a fost lansată în "
      "fundal dintr-o sesiune shell care s-a închis, iar procesele au fost oprite după 3 universuri fiecare; jurnalele "
      "parțiale sunt păstrate (`jurnal/*_intrerupt_01.log`), iar rulările au fost repornite identic (aceleași seed-uri). "
      "Testul de inginerie al UI (`tests/test_app.py`) a fost actualizat de la 8 la 9 taburi.\n")
    (HERE / "RAPORT_GL649.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    files = ["PREINREGISTRARE_GL649.md", "SIGILIU_PROTOCOL_GL649.json", "gl649.py", "verify_gl649.py", "raport_gl649.py",
             "tests/test_gl649.py", "rezultate/cod_calificare/gl649.py", "rezultate/CALIFICARE.json",
             "rezultate/backtest_unic/START.json", "rezultate/backtest_unic/PREDICTII.npz",
             "rezultate/backtest_unic/PREDICTII_EXACTE.json.gz", "rezultate/backtest_unic/PREDICTII_SIGILIU.json",
             "rezultate/backtest_unic/REZULTATE.json", "rezultate/backtest_unic/VERIFICARE_INDEPENDENTA.json",
             "rezultate/nule/SUMAR.json", "rezultate/putere/SUMAR.json", "rezultate/SENSIBILITATE.json",
             "jurnal/calificare.log", "jurnal/calificare_stdout.log", "jurnal/backtest_unic.log", "jurnal/sens.log",
             "jurnal/null32.log", "jurnal/power16.log", "jurnal/null32_intrerupt_01.log",
             "jurnal/power16_intrerupt_01.log", "RAPORT_GL649.md"]
    man = {"generated_from_artifacts": True, "files": {}}
    for f in files:
        p = HERE / f
        if p.exists():
            man["files"][f] = {"sha256": sha(p), "bytes": p.stat().st_size}
    (HERE / "MANIFEST_GL649.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print("RAPORT_GL649.md + MANIFEST_GL649.json generate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
