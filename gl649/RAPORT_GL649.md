# RAPORT GL649 — „Masa glifelor” (Bayes liniar exact pe structura cifrelor tipărite)

Protocol `GL649-P1` sigilat (sha256 `20384825d950c47ff284bacfb234199e0b0d2881d3820010619e7ce6d3ef10ae`, 2026-10-25T21:56:02.749481+00:00) înainte de orice cod și calcul GL649. Ipoteză nouă și distinctă în pista QL649; nu este o salvare a QL649 (0/6), BO649 (0/6), WU649 (necalificat 5/6) sau DL-649 (înghețat, neatins). Modelele închise nu au fost importate sau rulate; OGLINDA nu a fost atinsă. Precedente: Hartigan (1969), Goldstein & Wooff (2007), Henderson (1950, 1975), Robinson (1991), Woodbury (1950), Fienberg (1971); ideea „cernelii mai grele” este folclor. Calcul clasic: predictorul exact în Q (`Fraction`), scorurile în fp64 pe CPU. Fără hardware cuantic, avantaj cuantic sau noutate mondială. `positive_claims_allowed=false`. Arhiva este deja explorată, deci nu este un set nevăzut.

Ipoteza H_GL: propensiunea bilei j = `p0 + [P(Gγ + ε)]_j`, cu `G` incidența glifelor zecimale (fixă, a priori), `γ_d ~ (0, (p0/10)²)`, `ε_j ~ (0, (p0/20)²)`; predicția este așteptarea ajustată Bayes liniară cu covarianța exactă a eșantionării 6-din-49 la p0, `p̂ = x − ν z` (Woodbury), cu `Σ p̂ = 6` exact. Premisa fizică (cerneală, vopsea, gravură) nu este verificată pentru bilele Loteriei Române.

## Calificare (înainte de istoria reală)

Status **GL_QUALIFIED** (6/6), cod sha256 `ff5ce039cb529d34…` (arhivat byte-identic în `rezultate/cod_calificare/gl649.py`), 2026-10-25T21:59:37.619438+00:00, durată 11 s. Numerele arhivei nu au fost folosite; Q2 a citit doar structura pașilor. Martorii Q5/Q6 au fost derivați analitic în protocol (Derivarea A: sectorul antisimetric 7↔8, valori proprii λ0, λ1 în formă închisă) și confirmați exact în Q.

| Verificare | Nume | Rezultat | Detalii |
|---|---|---|---|
| Q1 | exactitate în Q (Woodbury = direct, Bayes liniar, echivarianță, sector) | PASS | `{"instances": 40, "woodbury_eq_direct": true, "sum6": true, "z_perp": true, "bl_identity": true, "equivariance": true, "sector_formula": true}` |
| Q2 | identități pe univers nul complet | PASS | `{"steps": 2427, "sum_exact_ok": true, "z_perp_ok": true, "law_in_01": true, "direct_eq_woodbury_sample": true, "sample_steps": 26, "p_min": 0.09751771667766485, "p_max": 0.14433738920488962, "run_seconds": 6.504241943359375}` |
| Q3 | cauzalitate (trunchiat ≡ complet, exact) | PASS | `{"sample_steps": 26}` |
| Q4 | echivarianță la automorfismul cifrelor (5 6 7 8 9) | PASS | `{"sample_steps": 26, "descriptive_non_automorphism_17_19_max_abs_dp": 0.010771871834417348}` |
| Q5 | martor de informație (analitic) | PASS | `{"n": 196, "counts_ok": true, "c17_eq_c19": true, "B_law_17_eq_19": true, "p19_eq_p0": true, "gap_exact_eq_closed_form": true, "gap_float": 0.006388020189747721, "sign_p17_gt_p19": true, "law_gap": 0.003194010094873856, "law_gap_ge_1e-3": true, "order_invariance_exact": true, "lambda0": 0.0627724498` |
| Q6 | martor de decizie (analitic) | PASS | `{"n": 196, "counts_ok": true, "ticket_GL": [1, 7, 17, 27, 37, 47], "ticket_B": [1, 8, 17, 27, 37, 47], "ticket_R": [8, 16, 24, 33, 41, 49], "above_p0": [7, 17, 27, 37, 47], "below_p0": [8, 18, 28, 38, 48], "three_l1_gt_eight_l0": true, "lambda0": 0.06277244986922406, "lambda1": 0.584460765365288, "e` |

Martor de informație (F5, n = 196): etichetele 17 și 19 au numărări egale (B identic), dar `p̂_17 − p̂_19 = 6.388020e-03` = forma închisă `12(λ1−λ0)/(5n)` exact, cu λ0 = 0.062772, λ1 = 0.584461; diferența în lege = 3.194010e-03 ≥ 1e-3.
Martor de decizie (F6): bilet GL [1, 7, 17, 27, 37, 47], bilet B [1, 8, 17, 27, 37, 47], bilet R [8, 16, 24, 33, 41, 49] (`ew_1` = 0.1832 ≤ marginea 0.3877 < 1 ≤ min ew pe ultima extragere = 3.9889). Anticiparea analitică a fost confirmată exact.

## Backtest walk-forward cauzal unic

START 2026-10-25T22:01:03.625162+00:00. Sursa are sha256 `193eaf7a6f4f9948a43e53e053ee8c03b0cd591bed0279d15d312a2857fa707c`, cu 2595 extrageri și 2527 pași-zi, de la 1993-08-08 la 2026-10-18. Încălzirea are 100 de pași; rămân **2495 ținte**. Predicțiile au fost sigilate înainte de scor: `PREDICTII.npz` sha256 `7ba69e142f0484bb25154849455fda5bc5cea7b5cf7a6792a8853460e0e4671d`, fracțiile exacte `PREDICTII_EXACTE.json.gz` sha256 `c32e647da77aa6317e239f74ff8b9bb6bc16df8ed537795dc992e248b75292be` (Σ p̂ = 6 exact la toți pașii: True). Durata predicției: 5.2 s. Consecvența comparatorilor cu BO649 (hitsB = 1847, hitsR = 1821): DA; rulare validă: True.

| Parte | Ținte | hitsGL | hitsB | hitsR | ExcesGL/U | logGL−U | logGL−B | BrierGL | BrierU | BrierB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Total | 2495 | 1892 | 1847 | 1821 | +0.023623 | -1.825135 | +12.392888 | 13137.322713 | 13136.938776 | 13139.967405 |
| Prima jumătate | 1247 | 916 | 902 | 919 | -0.000131 | -2.489865 | +9.936621 | 6566.372184 | 6565.836735 | 6568.490479 |
| A doua jumătate | 1248 | 976 | 945 | 902 | +0.047357 | +0.664730 | +2.456267 | 6570.950529 | 6571.102041 | 6571.476926 |

| Poartă | Cerință | Rezultat | Valoare |
|---|---|---|---|
| 1 | ExcesGL/U >= 0.20 | FAIL | `0.023622755715512644` |
| 2 | hitsGL > hitsB și hitsGL > hitsR | PASS | `[1892, 1847, 1821]` |
| 3 | logGL−logU > 0 și logGL−logB > 0 | FAIL | `[-1.82513546798873, 12.392887970832817]` |
| 4 | BrierGL < BrierU, BrierB, BrierR | FAIL | `[13137.322713445566, 13136.9387755102, 13139.967405084508, 13171.643465301917]` |
| 5 | ambele jumătăți: exces > 0 și hitsGL−hitsB > 0 | FAIL | `[[-0.0001309264684221656, 14], [0.0473574045002616, 31]]` |
| 6 | ambele jumătăți: logGL−logB > 0 | PASS | `[9.936620550433872, 2.4562674204025825]` |

**Verdict: `GL_NO_PROMOTION_EXPLORATORY` (2/6 porți).**

Date descriptive:
- p exact (hitsGL ≥ observat | extrageri uniforme independente) = 0.062277 (arhivă explorată, fără valoare confirmatoare);
- potriviri GL (0..6): [1045, 1055, 350, 43, 2, 0, 0]; așteptat sub U: [1087.7, 1030.5, 330.3, 44.0, 2.4, 0.0, 0.0];
- biletul GL diferă de B la 2494 ținte și de R la 2495 (din 2495);
- la ultimul pas: abaterea relativă a lui p̂ față de p0 are deviația 0.0363, min -0.0740, max +0.1011; Spearman(p̂, numărări) = 0.9224;
- efecte de glifă ajustate γ̂/p0 (cifrele 0..9): [-0.0288, -0.0351, -0.0284, -0.0307, -0.0503, 0.0009, 0.0236, -0.0293, -0.0322, -0.0447] (descriptiv; nivelul comun este identificat numai prin contrastul etichete cu o glifă / cu două glife).

Verificarea independentă (`verify_gl649.py`, fără import din gl649, wu649, bo649, engine, parser sau validare; rezolvare directă 49×49 fără Woodbury în fp64 la fiecare pas și Gauss–Jordan exact în Q la pașii din 25 în 25; R prin recursie) a dat **PASS** (26/26), verdict recalculat `GL_NO_PROMOTION_EXPLORATORY` (2/6).

## Universuri nule sintetice (descriptiv, M = 32, seed `[649, 9, u]`)

- Excesul GL: medie +0.002280, abatere 0.015631, min -0.024073, max +0.050476. Valoarea reală +0.023623 are rangul empiric 31/32 (≤).
- hitsGL − hitsB: medie +1.6, abatere 31.4, min -77.0, max +56.0. Valoarea reală +45.0 are rangul empiric 30/32 (≤).
- logGL−B: medie +16.003, abatere 2.742, min +10.475, max +21.133. Valoarea reală +12.393 are rangul empiric 3/32 (≤).
- logGL−U: medie -3.194, abatere 2.224, min -6.541, max +1.208. Valoarea reală -1.825 are rangul empiric 24/32 (≤).
- Porți trecute pe universurile nule: distribuția [0, 17, 9, 6, 0, 0, 0] (0..6); maximum 3/6.
- Observație: `logGL−B > 0` apare și sub nul (contracția Bayes liniară față de legea B), deci poarta 6 trecută pe arhivă nu indică singură un semnal.

## Putere sintetică sub H_GL (descriptiv, M = 16, seed `[649, 9, 1000+u]`, generator: alegere secvențială ponderată p_j)

- Exces GL: medie +0.1339, min +0.0926, max +0.1711; universuri cu exces ≥ 0.20: 0/16.
- hitsGL − hitsB: medie +36.3, pozitiv în 15/16 universuri.
- Porți trecute: distribuția [0, 0, 4, 4, 8, 0, 0] (0..6); 6/6 în 0/16.
- Sub H_GL la scara priorului, poarta 1 (exces ≥ 0.20) a fost atinsă în 0/16 universuri: porțile, fixate înainte, sunt foarte exigente pentru efecte de această mărime.

## Sensibilitate (strict descriptivă, declarată în §6; nicio configurație nu poate fi promovată sau selectată)

| s_g | s_e | hitsGL | ExcesGL/U | logGL−U | logGL−B | BrierGL | porți | bilete ≠ B |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| p0/20 | p0/20 | 1868 | +0.014004 | -0.892 | +13.326 | 13137.125 | 2/6 | 2404 |
| p0/5 | p0/20 | 1879 | +0.018412 | -2.544 | +11.674 | 13137.475 | 2/6 | 2490 |
| p0/10 | p0/5 | 1854 | +0.008392 | -8.010 | +6.208 | 13138.657 | 2/6 | 930 |

## Limite

Rezultatul nu demonstrează avantaj predictiv real și nu infirmă universal alte structuri pe etichete sau alte modele fizice. Dacă extragerile sunt uniforme și independente, istoricul nu oferă avantaj. Nu au existat evaluări prospective, emisii live sau promisiuni de câștig. Nu s-a făcut tuning după rezultat; sensibilitatea, universurile nule și puterea sintetică au fost declarate înainte și sunt doar descriptive. Zero incidente tehnice în calificare și în backtest, zero amendamente; codul de calificare și cel al backtestului sunt același fișier (sha256 identic). Notă de proces (descriptiv, fără efect asupra verdictului): prima pornire a rulărilor nule/putere a fost lansată în fundal dintr-o sesiune shell care s-a închis, iar procesele au fost oprite după 3 universuri fiecare; jurnalele parțiale sunt păstrate (`jurnal/*_intrerupt_01.log`), iar rulările au fost repornite identic (aceleași seed-uri). Testul de inginerie al UI (`tests/test_app.py`) a fost actualizat de la 8 la 9 taburi.

