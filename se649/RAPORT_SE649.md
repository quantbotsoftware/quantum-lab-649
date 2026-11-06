# RAPORT SE649 — „Anotimpurile bilelor” (Bayes liniar ierarhic exact, etichetă × anotimp)

Protocol `SE649-P1` sigilat (sha256 `eaf1fe5089b58b915af1769990d474646a585750cad9851ea95f18caaf396de8`, 2026-10-25T22:50:21.380713+00:00) înainte de orice cod și calcul SE649. Ipoteză nouă și distinctă în pista QL649; nu este o salvare a QL649 (0/6), BO649 (0/6), WU649 (necalificat 5/6), GL649 (2/6) sau DL-649 (înghețat, neatins). Modelele închise nu au fost importate sau rulate; OGLINDA nu a fost atinsă. Precedente: Hartigan (1969), Goldstein & Wooff (2007), Henderson (1975), Robinson (1991), Sherman & Morrison (1950); dependența de temperatură a restituției elastomerilor este fizică clasică. Calcul clasic: predictorul exact în Q (`Fraction`), scorurile în fp64 pe CPU. Fără hardware cuantic, avantaj cuantic sau noutate mondială. `positive_claims_allowed=false`. Arhiva este deja explorată, deci nu este un set nevăzut.

Ipoteza H_SE: `p_j(φ) = p0 + a_j + b_j(φ)`, cu φ anotimpul meteorologic al datei extragerii (DJF/MAM/JJA/SON), efect principal `a ~ (0, (p0/20)² P)` și interacțiune `b(φ) ~ (0, (p0/5)² P)`, independente între anotimpuri. Predicția este așteptarea ajustată Bayes liniară `p̂ = p0·1 + Σ_φ w_φ (c_φ/n_φ − p0·1)`, cu ponderi în formă închisă (Sherman–Morrison); `Σ p̂ = 6` exact și `p̂ ∈ (0,1)`. Motivul a priori: o interacțiune cu medie anuală zero este invizibilă pentru B (numărări totale), deci nu era infirmată de rezultatele negative anterioare. Premisa fizică (climatizare, seturi de bile) nu este verificată pentru Loteria Română.

## Calificare (înainte de istoria reală)

Status **SE_QUALIFIED** (6/6), cod sha256 `c26cffc263f88854…` (arhivat byte-identic în `rezultate/cod_calificare/se649.py`), 2026-10-25T22:53:11.302960+00:00, durată 3 s. Numerele arhivei nu au fost folosite; Q2–Q4 au citit doar structura pașilor și anotimpurile datelor. Martorii Q5/Q6 au fost derivați analitic în protocol (Derivarea B: antisimetrie iarnă–vară, `p̂ − p0 = (τb²/D) u`) și confirmați exact în Q.

| Verificare | Nume | Rezultat | Detalii |
|---|---|---|---|
| Q1 | exactitate în Q (formă închisă = direct, Σ=6, ortogonalitate Bayes liniară, echivarianță) | PASS | `{"instances": 40, "closed_eq_direct": true, "sum6": true, "wsum_lt1": true, "range01": true, "bl_orthogonality": true, "equivariance": true, "cases_phi_absent": 6, "cases_other_absent": 6}` |
| Q2 | identități pe univers nul complet | PASS | `{"steps": 2427, "sum_exact_ok": true, "range_ok": true, "wsum_lt1_ok": true, "law_in_01": true, "closed_eq_direct_sample": true, "sample_steps": 26, "p_min": 0.07913032018598909, "p_max": 0.16554098820025182, "run_seconds": 1.6093618869781494}` |
| Q3 | cauzalitate (trunchiat ≡ complet, exact) | PASS | `{"sample_steps": 26}` |
| Q4 | echivarianță la etichete și invarianță la ordinea din anotimp | PASS | `{"sample_steps": 26, "label_equivariance": true, "within_season_order_invariance": true, "descriptive_cross_season_perm_max_abs_dp": 0.02573021289428499}` |
| Q5 | martor de informație (analitic, Derivarea B) | PASS | `{"N4": [49, 49, 49, 49], "phi_target": 0, "totals_all_equal": true, "c5_eq_c9": true, "B_law_5_eq_9": true, "gap_exact_eq_closed_form": true, "gap_float": 0.025873298695853985, "symmetric_about_p0": true, "others_eq_p0": true, "sign_p5_gt_p9": true, "law_gap": 0.012936649347926987, "law_gap_ge_1e-3"` |
| Q6 | martor de decizie (analitic) | PASS | `{"k": 98, "N4": [49, 0, 49, 0], "phi_target": 0, "totals": [12], "ticket_SE": [44, 45, 46, 47, 48, 49], "ticket_B": [1, 2, 3, 4, 5, 6], "ticket_R": [3, 4, 10, 18, 35, 43], "p_values_exact_as_derived": true, "delta_float": 0.025873298695853985, "ew_1": 3.8810616443112, "ew_1_lower_bound": 3.337594428` |

Martor de informație (F5, 4 blocuri × 49): etichetele 5 și 9 au numărări totale egale (B identic), dar pentru ținta de iarnă `p̂_5 − p̂_9 = 2.587330e-02` = `6τb²/(49D)` exact (τb²/D = 0.211299); diferența în lege = 1.293665e-02 ≥ 1e-3; pentru ținta de vară diferența își schimbă exact semnul: True.
Martor de decizie (F6, iarnă + vară, k = 98): bilet SE [44, 45, 46, 47, 48, 49], bilet B [1, 2, 3, 4, 5, 6] (disjuncte), bilet R [3, 4, 10, 18, 35, 43] (`ew_1` = 3.8811 ≥ marginea 3.3376 > 3.2498 ≥ max ew_44..49 = 2.8185). Anticiparea analitică a fost confirmată exact.

## Backtest walk-forward cauzal unic

START 2026-10-25T22:53:19.912958+00:00. Sursa are sha256 `193eaf7a6f4f9948a43e53e053ee8c03b0cd591bed0279d15d312a2857fa707c`, cu 2595 extrageri și 2527 pași-zi, de la 1993-08-08 la 2026-10-18. Încălzirea are 100 de pași; rămân **2495 ținte**. Predicțiile au fost sigilate înainte de scor: `PREDICTII.npz` sha256 `7f947d193df7e4230c922f931a22f9badf3b41168910015bca3c9bf21c3a555f`, fracțiile exacte și ponderile `PREDICTII_EXACTE.json.gz` sha256 `e461e3e1fe992e4755c3d817a59954dedc8a4a74b57ab8e3b70e6007a836c3f0` (Σ p̂ = 6 exact la toți pașii: True; p̂ ∈ (0,1): True). Durata predicției: 1.5 s. Consecvența comparatorilor cu BO649/GL649 (hitsB = 1847, hitsR = 1821): DA; rulare validă: True.

| Parte | Ținte | hitsSE | hitsB | hitsR | ExcesSE/U | logSE−U | logSE−B | BrierSE | BrierU | BrierB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Total | 2495 | 1845 | 1847 | 1821 | +0.004785 | -12.584676 | +1.633348 | 13139.655934 | 13136.938776 | 13139.967405 |
| Prima jumătate | 1247 | 902 | 902 | 919 | -0.011358 | -12.184244 | +0.242241 | 6568.481167 | 6565.836735 | 6568.490479 |
| A doua jumătate | 1248 | 943 | 945 | 902 | +0.020915 | -0.400431 | +1.391106 | 6571.174767 | 6571.102041 | 6571.476926 |

| Poartă | Cerință | Rezultat | Valoare |
|---|---|---|---|
| 1 | ExcesSE/U >= 0.20 | FAIL | `0.004785080364811178` |
| 2 | hitsSE > hitsB și hitsSE > hitsR | FAIL | `[1845, 1847, 1821]` |
| 3 | logSE−logU > 0 și logSE−logB > 0 | FAIL | `[-12.584675624784722, 1.6333478140368243]` |
| 4 | BrierSE < BrierU, BrierB, BrierR | FAIL | `[13139.655934474984, 13136.9387755102, 13139.967405084508, 13171.643465301917]` |
| 5 | ambele jumătăți: exces > 0 și hitsSE−hitsB > 0 | FAIL | `[[-0.011357871135623476, 0], [0.020915096807953892, -2]]` |
| 6 | ambele jumătăți: logSE−logB > 0 | PASS | `[0.2422413843414688, 1.3911064296989935]` |

**Verdict: `SE_NO_PROMOTION_EXPLORATORY` (1/6 porți).**

Pe anotimpul țintei (descriptiv):

| Anotimp țintă | Ținte | hitsSE | hitsB | hitsR | ExcesSE/U | logSE−B | logSE−U |
|---|---:|---:|---:|---:|---:|---:|---:|
| iarnă | 589 | 466 | 426 | 439 | +0.056478 | +1.618 | +0.689 |
| primăvară | 622 | 448 | 449 | 447 | -0.014437 | +2.651 | -3.594 |
| vară | 637 | 474 | 488 | 459 | +0.009419 | -0.075 | -4.077 |
| toamnă | 647 | 457 | 484 | 476 | -0.028357 | -2.561 | -5.603 |

Date descriptive:
- p exact (hitsSE ≥ observat | extrageri uniforme independente) = 0.380678 (arhivă explorată, fără valoare confirmatoare);
- potriviri SE (0..6): [1090, 1016, 340, 47, 2, 0, 0]; așteptat sub U: [1087.7, 1030.5, 330.3, 44.0, 2.4, 0.0, 0.0];
- biletul SE diferă de B la 2495 ținte și de R la 2495 (din 2495);
- la final: extrageri pe anotimpuri [607, 648, 667, 673]; ponderea anotimpului propriu iarnă 0.7778, primăvară 0.7889, vară 0.7936, toamnă 0.7951; ponderile celorlalte anotimpuri ≈ 0.009 fiecare;
- la ultimul pas (anotimp 3): abaterea relativă a lui p̂ față de p0 are deviația 0.0802, min -0.1598, max +0.1626;
- statistica G a tabelului etichetă × anotimp pe întreaga arhivă: 196.652 (rangul față de universurile nule mai jos).

Verificarea independentă (`verify_se649.py`, fără import din se649, gl649, wu649, bo649, engine, parser sau validare; anotimpuri printr-un dicționar explicit, rezolvare directă |O|×|O| fără Sherman–Morrison în fp64 la fiecare pas și Gauss–Jordan exact în Q la pașii din 25 în 25, inclusiv ponderile; R prin recursie) a dat **PASS** (33/33), verdict recalculat `SE_NO_PROMOTION_EXPLORATORY` (1/6).

## Universuri nule sintetice (descriptiv, M = 32, seed `[649, 10, u]`)

- Excesul SE: medie +0.002255, abatere 0.015635, min -0.047720, max +0.034044. Valoarea reală +0.004785 are rangul empiric 19/32 (≤).
- hitsSE − hitsB: medie +5.7, abatere 39.3, min -75.0, max +90.0. Valoarea reală -2.0 are rangul empiric 14/32 (≤).
- logSE−B: medie +1.367, abatere 4.907, min -5.568, max +15.432. Valoarea reală +1.633 are rangul empiric 18/32 (≤).
- logSE−U: medie -17.909, abatere 5.066, min -31.425, max -8.692. Valoarea reală -12.585 are rangul empiric 29/32 (≤).
- Statistica G etichetă × anotimp: medie 174.217, abatere 17.522, min 128.375, max 217.348. Valoarea reală 196.652 are rangul empiric 29/32 (≤).
- Porți trecute pe universurile nule: distribuția [20, 9, 3, 0, 0, 0, 0] (0..6); maximum 2/6; pe porți (1..6): [0, 9, 0, 0, 3, 3].
- `logSE−B > 0` apare în 20/32 universuri nule (contracție față de legea B), deci poarta 6 trecută pe arhivă nu indică singură un semnal (lecția GL649 confirmată).

## Putere sintetică sub H_SE, scara priorului (b ~ N(0, 0.2²)) (descriptiv, M = 16, generator: alegere secvențială ponderată p_j(φ) a anotimpului datei)

- Exces SE: medie +0.1623, min +0.1170, max +0.2156; exces B mediu +0.0977; poarta 1 (exces ≥ 0.20) atinsă în 1/16 universuri.
- hitsSE − hitsB: medie +160.9, pozitiv în 16/16 universuri.
- Porți trecute: distribuția [0, 0, 0, 0, 1, 14, 1] (0..6); 6/6 în 1/16.

## Putere sintetică sub H_SE, jumătatea interacțiunii (b ~ N(0, 0.1²)) (descriptiv, M = 8, generator: alegere secvențială ponderată p_j(φ) a anotimpului datei)

- Exces SE: medie +0.0663, min +0.0413, max +0.1022; exces B mediu +0.0597; poarta 1 (exces ≥ 0.20) atinsă în 0/8 universuri.
- hitsSE − hitsB: medie +16.5, pozitiv în 5/8 universuri.
- Porți trecute: distribuția [0, 0, 0, 3, 2, 3, 0] (0..6); 6/6 în 0/8.

Comparație cu estimarea de mână din protocol §2.1 (exces așteptat ≈ 0.19 la scara priorului, ≈ 0.09 la jumătate): valorile sintetice de mai sus sunt măsurătoarea; diferența arată cât de optimistă a fost aproximarea de mână.

## Sensibilitate (strict descriptivă, declarată în §6; nicio configurație nu poate fi promovată sau selectată)

| τa | τb | hitsSE | ExcesSE/U | logSE−U | logSE−B | BrierSE | porți | bilete ≠ B |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| p0/20 | p0/10 | 1837 | +0.001579 | -1.534 | +12.684 | 13137.272 | 1/6 | 2495 |
| p0/20 | p0/4 | 1845 | +0.004785 | -18.680 | -4.462 | 13140.964 | 0/6 | 2495 |
| p0/10 | p0/5 | 1845 | +0.004785 | -14.153 | +0.065 | 13139.995 | 0/6 | 2495 |

## Limite

Rezultatul nu demonstrează avantaj predictiv real și nu infirmă universal alte covariabile ambientale, alte partiții ale anului sau alte modele fizice. Dacă extragerile sunt uniforme și independente, istoricul nu oferă avantaj. Nu au existat evaluări prospective, emisii live sau promisiuni de câștig. Nu s-a făcut tuning după rezultat; sensibilitatea, universurile nule și puterea sintetică au fost declarate înainte și sunt doar descriptive. Zero incidente tehnice în calificare și în backtest, zero amendamente; codul de calificare și cel al backtestului sunt același fișier (sha256 identic). Notă tehnică (fără efect asupra verdictului): prima rulare a verificatorului independent s-a oprit cu `IndexError` în calculul descriptiv al statisticii G, înainte de a scrie vreun rezultat; corecția are o linie, iar încercarea inițială și nota sunt păstrate în `jurnal/incidente_verificator/`. Rulările nule/putere au fost pornite ca sarcini proprii și s-au terminat complet.

