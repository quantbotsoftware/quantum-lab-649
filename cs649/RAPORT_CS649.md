# RAPORT CS649 — „Caruselul seturilor” (rotație deterministă ipotetică a seturilor de bile/urnelor)

Protocol `CS649-P1` sigilat (sha256 `d9c453e4228e9ea49f2430f79c76ec31d52ab66d2bf48bc950bd96a066be1fcf`, 2026-10-26T10:35:02.161871+00:00) înainte de orice cod și calcul CS649. Ipoteză nouă și distinctă în pista QL649; nu este o salvare a QL649 (0/6), BO649 (0/6), WU649 (necalificat 5/6), GL649 (2/6), SE649 (1/6) sau DL-649 (înghețat, neatins). Modelele închise nu au fost importate sau rulate; OGLINDA nu a fost atinsă. Precedente: Henderson (1950, 1975), Hartigan (1969), Goldstein & Wooff (2007), Searle, Casella & McCulloch (1992), teorema chineză a resturilor; practica publică a urnelor/seturilor multiple (la loteria citată în surse: selecție ALEATOARE). Calcul clasic: predictorul exact în Q (`Fraction`), scorurile în fp64 pe CPU. Fără hardware cuantic, avantaj cuantic sau noutate mondială. `positive_claims_allowed=false`. Arhiva este deja explorată, deci nu este un set nevăzut.

Ipoteza H_CS: seturi de bile/urne cu defecte diferite, alese printr-o rotație deterministă după indicele zilei de extragere din arhivă; surogat aditiv `θ(k) = p0·1 + a + b³(k mod 3) + b⁵(k mod 5) + b⁷(k mod 7)`, cu `a ~ (0, (p0/20)² P)`, `b^K(r) ~ (0, (p0/4)² P)`. Perioadele pare au fost excluse a priori (alias cu alternanța joi/duminică, familia închisă N1/N2); 3, 5, 7 sunt prime între ele (plan încrucișat complet). Predicția este așteptarea ajustată Bayes liniară prin ecuațiile Henderson 16×16: `p̂_j = p0 + Σ_ℓ v_ℓ (c_{ℓj} − p0 n_ℓ)`, `v = (ZᵀZ + σ0² G⁻¹)⁻¹ z*`; ponderea unei extrageri vechi este periodică în timp (perioadă 105), nu de recență. Premisa (procedura de alegere a setului la Loteria Română) nu este verificată.

## Calificare (înainte de istoria reală)

Status **CS_QUALIFIED** (6/6), cod sha256 `b66c064ac5d0a60f…` (arhivat byte-identic în `rezultate/cod_calificare/cs649.py`), 2026-10-26T10:38:42.690331+00:00, durată 6 s. Numerele arhivei nu au fost folosite; Q2–Q4 au citit doar numărul de extrageri pe zi. Martorii Q5/Q6 au fost derivați analitic în protocol (Derivarea C: plan echilibrat n = 105, contracțiile λ_K și λ0 în formă închisă) și confirmați exact în Q.

| Verificare | Nume | Rezultat | Detalii |
|---|---|---|---|
| Q1 | exactitate în Q (Henderson = primal N×N, Σ=6, echivarianță, formă închisă echilibrată) | PASS | `{"instances": 40, "henderson_eq_primal": true, "sum6": true, "equivariance": true, "cases_empty_levels": 10, "cases_two_draw_steps": 35, "max_draws": 48, "balanced_closed_form": [{"n": 105, "kstar": 105, "eq": true}, {"n": 105, "kstar": 106, "eq": true}, {"n": 210, "kstar": 210, "eq": true}, {"n": 2` |
| Q2 | identități pe univers nul complet (incremental = de la zero, Bareiss = Gauss–Jordan) | PASS | `{"steps": 2427, "sum_exact_ok": true, "law_in_01": true, "incremental_eq_scratch_sample": true, "bareiss_eq_gauss_jordan_sample": true, "sample_steps": 26, "steps_p_outside_01": 0, "p_min": 0.01720215590282074, "p_max": 0.22792394206577302, "run_seconds": 3.9852523803710938}` |
| Q3 | cauzalitate (trunchiat ≡ complet, exact) | PASS | `{"sample_steps": 26}` |
| Q4 | echivarianță la etichete și invarianță la ordinea din clasa k mod 105 | PASS | `{"sample_steps": 26, "label_equivariance": true, "within_class_mod105_order_invariance": true, "descriptive_cross_class_perm_max_abs_dp": 0.039821119355110554}` |
| Q5 | martor de informație (analitic, Derivarea C, K = 3, 5, 7) | PASS | `{"K3": {"lambda_K": "90/391", "lambda_K_float": 0.23017902813299232, "c5": 35, "c9": 35, "c5_eq_c9_eq_105_over_K": true, "B_law_5_eq_9": true, "gap_105_exact_eq_lambda": true, "gap_105_float": 0.23017902813299232, "sign_p5_gt_p9": true, "law_gap": 0.1150895140664962, "law_gap_ge_1e-3": true, "gap_10` |
| Q6 | martor de decizie (analitic) | PASS | `{"lambda0": "6768/17303", "lambda3": "90/391", "diff_44_1": "1194264/6765473", "diff_expected": "1194264/6765473", "diff_eq_expected": true, "p44": 0.35838824572945605, "p1": 0.1818648895650016, "p7": 0.0745535456279258, "p_values_exact_as_derived": true, "totals": [0, 35, 70], "ticket_CS": [44, 45,` |

Martor de informație (F5_K, „set constant pe fază”, 105 pași): etichetele 5 și 9 au numărări totale egale (B identic), dar la ținta k* = 105 `p̂_5 − p̂_9 = λ_K` exact: K = 3: 90/391 ≈ 0.230179, lege 0.115090, semn inversat la k* = 106: True, zero la 107: True, R inversează ordinea (ew_9 = 11.8969 > ew_5 = 11.5839); K = 5: 54/355 ≈ 0.152113, lege 0.076056, semn inversat la k* = 106: True, zero la 107: True, R inversează ordinea (ew_9 = 6.9470 > ew_5 = 6.7643); K = 7: 270/2377 ≈ 0.113589, lege 0.056794, semn inversat la k* = 106: True, zero la 107: True, R inversează ordinea (ew_9 = 4.8282 > ew_5 = 4.7012).
Martor de decizie (F6, K = 3): bilet CS [44, 45, 46, 47, 48, 49], bilet B [1, 2, 3, 4, 5, 6] (disjuncte), bilet R [1, 2, 3, 4, 5, 6] (`ew_1` = 24.1151 > 2 · max ew_44..49 = 2 · 11.5839); `p̂_44 − p̂_1 = 1194264/6765473` = `(4λ3 − λ0)/3` exact; p̂ = 0.358388 / 0.181865 / 0.074554 ca în derivare.

## Backtest walk-forward cauzal unic

START 2026-10-26T10:38:57.149389+00:00. Sursa are sha256 `193eaf7a6f4f9948a43e53e053ee8c03b0cd591bed0279d15d312a2857fa707c`, cu 2595 extrageri și 2527 pași-zi, de la 1993-08-08 la 2026-10-18. Încălzirea are 100 de pași; rămân **2495 ținte**. Predicțiile au fost sigilate înainte de scor: `PREDICTII.npz` sha256 `87155567db84087c9954d508fd5d00e3b7cf2d4088b8a213043ecfb45ddaae39`, fracțiile exacte și ponderile v `PREDICTII_EXACTE.json.gz` sha256 `cee7ae7ebac771a8a35ed8db5bfd382ba8a4e0e980adac76907eeb5c42c3d958` (Σ p̂ = 6 exact la toți pașii: True; pași cu p̂ în afara lui (0,1): 0). Durata predicției: 3.6 s. Consecvența comparatorilor cu BO649/GL649/SE649 (hitsB = 1847, hitsR = 1821): DA; rulare validă: True.

| Parte | Ținte | hitsCS | hitsB | hitsR | ExcesCS/U | logCS−U | logCS−B | BrierCS | BrierU | BrierB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Total | 2495 | 1839 | 1847 | 1821 | +0.002380 | -84.051661 | -69.833637 | 13154.832527 | 13136.938776 | 13139.967405 |
| Prima jumătate | 1247 | 915 | 902 | 919 | -0.000933 | -50.737878 | -38.311393 | 6576.693850 | 6565.836735 | 6568.490479 |
| A doua jumătate | 1248 | 924 | 945 | 902 | +0.005691 | -33.313782 | -31.522245 | 6578.138676 | 6571.102041 | 6571.476926 |

| Poartă | Cerință | Rezultat | Valoare |
|---|---|---|---|
| 1 | ExcesCS/U >= 0.20 | FAIL | `0.002380270745572788` |
| 2 | hitsCS > hitsB și hitsCS > hitsR | FAIL | `[1839, 1847, 1821]` |
| 3 | logCS−logU > 0 și logCS−logB > 0 | FAIL | `[-84.05166057995666, -69.83363714113511]` |
| 4 | BrierCS < BrierU, BrierB, BrierR | FAIL | `[13154.832526787044, 13136.9387755102, 13139.967405084508, 13171.643465301917]` |
| 5 | ambele jumătăți: exces > 0 și hitsCS−hitsB > 0 | FAIL | `[[-0.0009328510875080687, 13], [0.005690737833594972, -21]]` |
| 6 | ambele jumătăți: logCS−logB > 0 | FAIL | `[-38.31139260762575, -31.522244533505727]` |

**Verdict: `CS_NO_PROMOTION_EXPLORATORY` (0/6 porți).**

Pe faza-țintă a fiecărei perioade (descriptiv):

| Perioadă | Fază | Ținte | hitsCS | hitsB | hitsR | ExcesCS/U | logCS−B |
|---|---:|---:|---:|---:|---:|---:|---:|
| K3 | 0 | 830 | 607 | 589 | 616 | -0.003369 | -28.826 |
| K3 | 1 | 832 | 613 | 632 | 591 | +0.002085 | -20.058 |
| K3 | 2 | 833 | 619 | 626 | 614 | +0.008403 | -20.950 |
| K5 | 0 | 500 | 357 | 354 | 382 | -0.020694 | -13.037 |
| K5 | 1 | 501 | 362 | 390 | 386 | -0.012139 | -13.965 |
| K5 | 2 | 495 | 361 | 330 | 343 | -0.005401 | -11.879 |
| K5 | 3 | 499 | 355 | 377 | 336 | -0.023271 | -15.940 |
| K5 | 4 | 500 | 404 | 396 | 374 | +0.073306 | -15.014 |
| K7 | 0 | 357 | 258 | 261 | 268 | -0.012005 | -12.689 |
| K7 | 1 | 362 | 278 | 274 | 270 | +0.033262 | -10.178 |
| K7 | 2 | 355 | 258 | 263 | 270 | -0.007933 | -11.255 |
| K7 | 3 | 353 | 253 | 257 | 265 | -0.017980 | -12.704 |
| K7 | 4 | 354 | 272 | 281 | 233 | +0.033668 | -6.167 |
| K7 | 5 | 356 | 255 | 252 | 232 | -0.018402 | -9.392 |
| K7 | 6 | 358 | 265 | 259 | 283 | +0.005530 | -7.448 |

Date descriptive:
- p exact (hitsCS ≥ observat | extrageri uniforme independente) = 0.442029 (arhivă explorată, fără valoare confirmatoare);
- potriviri CS (0..6): [1121, 977, 335, 57, 4, 1, 0]; așteptat sub U: [1087.7, 1030.5, 330.3, 44.0, 2.4, 0.0, 0.0];
- biletul CS diferă de B la 2495 ținte și de R la 2495 (din 2495);
- la final: extrageri pe niveluri {'a': 2595, 'K3r0': 864, 'K3r1': 865, 'K3r2': 866, 'K5r0': 520, 'K5r1': 521, 'K5r2': 515, 'K5r3': 519, 'K5r4': 520, 'K7r0': 372, 'K7r1': 377, 'K7r2': 369, 'K7r3': 367, 'K7r4': 368, 'K7r5': 370, 'K7r6': 372}; ponderile v pentru indicele următor 2527 (faze [1, 2, 0]): a +2.032e-05, K3r0 -1.726e-04, K3r1 +8.466e-04, K3r2 -1.659e-04, K5r0 -2.159e-04, K5r1 -2.117e-04, K5r2 +1.363e-03, K5r3 -2.151e-04, K5r4 -2.126e-04, K7r0 +1.827e-03, K7r1 -2.217e-04, K7r2 -2.176e-04, K7r3 -2.242e-04, K7r4 -2.165e-04, K7r5 -2.141e-04, K7r6 -2.244e-04;
- la ultimul pas (faze [0, 1, 6]): abaterea relativă a lui p̂ față de p0 are deviația 0.1535, min -0.2841, max +0.4810;
- statisticile G etichetă × fază pe întreaga arhivă: G3 134.961, G5 188.997, G7 294.753, suma 618.711 (rangurile față de universurile nule mai jos).

Verificarea independentă (`verify_cs649.py`, fără import din cs649, se649, gl649, wu649, bo649, engine, parser sau validare; faze din propriul indice al pașilor; forma PRIMALĂ pe celulele k mod 105 în fp64 la fiecare pas, fără sistemul Henderson; Henderson exact în Q prin Gauss–Jordan propriu la pașii din 25 în 25, inclusiv ponderile v; R prin recursie; ordinea temporală sigiliu < calificare < START) a dat **PASS** (33/33), verdict recalculat `CS_NO_PROMOTION_EXPLORATORY` (0/6).

## Universuri nule sintetice (descriptiv, M = 32, seed `[649, 11, u]`, aceleași ecuații Henderson în float64 (§6))

- Excesul CS: medie -0.000112, abatere 0.016644, min -0.031287, max +0.041258. Valoarea reală +0.002380 are rangul empiric 17/32 (≤).
- hitsCS − hitsB: medie +7.1, abatere 42.9, min -76.0, max +87.0. Valoarea reală -8.0 are rangul empiric 10/32 (≤).
- logCS−B: medie -53.334, abatere 8.672, min -72.933, max -36.795. Valoarea reală -69.834 are rangul empiric 2/32 (≤).
- logCS−U: medie -72.663, abatere 10.961, min -94.351, max -49.359. Valoarea reală -84.052 are rangul empiric 5/32 (≤).
- Statistica G3 etichetă × fază: medie 128.182, abatere 19.965, min 93.979, max 162.720. Valoarea reală 134.961 are rangul empiric 22/32 (≤).
- Statistica G5 etichetă × fază: medie 214.167, abatere 24.798, min 171.227, max 258.173. Valoarea reală 188.997 are rangul empiric 7/32 (≤).
- Statistica G7 etichetă × fază: medie 300.238, abatere 20.801, min 261.136, max 339.421. Valoarea reală 294.753 are rangul empiric 13/32 (≤).
- Statistica G_sum etichetă × fază: medie 642.586, abatere 50.401, min 547.562, max 746.488. Valoarea reală 618.711 are rangul empiric 10/32 (≤).
- Porți trecute pe universurile nule: distribuția [17, 10, 5, 0, 0, 0, 0] (0..6); maximum 2/6; pe porți (1..6): [0, 15, 0, 0, 5, 0].
- `logCS−B > 0` apare în 0/32 universuri nule: la scara priorului CS (25% pe fiecare rotație) zgomotul contrastelor de fază costă în log sub nul; valoarea reală este în coada de jos a nulului, nu în afara lui.

## Putere sintetică sub H_CS, scara priorului (toate trei rotațiile, b ~ N(0, 0.25²), a ~ N(0, 0.05²)) (descriptiv, M = 16)

- Deviația relativă medie a propensiunilor generate (după tăiere): 0.407.
- Exces CS: medie +0.3510, min +0.3170, max +0.4160; exces B mediu +0.2023; poarta 1 (exces ≥ 0.20) atinsă în 16/16 universuri.
- hitsCS − hitsB: medie +371.1, pozitiv în 16/16; logCS−B pozitiv în 16/16.
- Porți trecute: distribuția [0, 0, 0, 0, 0, 0, 16] (0..6); 6/6 în 16/16.

## Putere sintetică sub H_CS, o singură rotație K0 ∈ {3,5,7}, b ~ N(0, 0.25²) (descriptiv, M = 8)

- Deviația relativă medie a propensiunilor generate (după tăiere): 0.257.
- Exces CS: medie +0.1741, min +0.1555, max +0.1884; exces B mediu +0.1069; poarta 1 (exces ≥ 0.20) atinsă în 0/8 universuri.
- hitsCS − hitsB: medie +167.8, pozitiv în 8/8; logCS−B pozitiv în 8/8.
- Porți trecute: distribuția [0, 0, 0, 0, 0, 8, 0] (0..6); 6/6 în 0/8.
- Pe universuri: K0 = 3: exces +0.1863, 5/6; K0 = 5: exces +0.1884, 5/6; K0 = 7: exces +0.1555, 5/6; K0 = 3: exces +0.1735, 5/6; K0 = 5: exces +0.1571, 5/6; K0 = 7: exces +0.1755, 5/6; K0 = 3: exces +0.1831, 5/6; K0 = 5: exces +0.1735, 5/6.

Comparație cu estimarea de mână din protocol §2.1 (≈ 0.42 când adevărul = priorul; ≈ 0.21 / 0.20 / 0.18 pentru o singură rotație de 25% cu K0 = 3 / 5 / 7): valorile sintetice de mai sus sunt măsurătoarea; diferența arată cât de optimistă a fost aproximarea de mână (gaussianitate, plan echilibrat, fără tăiere). Sub o singură rotație de 25%, porțile 2–6 trec, dar poarta 1 rămâne blocată; pe arhivă nu trece nicio poartă.

## Sensibilitate (strict descriptivă, declarată în §6; nicio configurație nu poate fi promovată sau selectată)

| τa | τ | hitsCS | ExcesCS/U | logCS−U | logCS−B | BrierCS | porți | bilete ≠ B |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| p0/20 | p0/8 | 1828 | -0.002029 | -26.456 | -12.238 | 13142.590 | 0/6 | 2495 |
| p0/20 | p0/2 | 1836 | +0.001178 | -170.027 | -155.809 | 13172.761 | 0/6 | 2495 |
| p0/10 | p0/4 | 1838 | +0.001979 | -84.647 | -70.429 | 13154.957 | 0/6 | 2495 |

## Limite

Rezultatul nu demonstrează avantaj predictiv real și nu infirmă universal rotațiile cu perioadă pară, alte perioade, rotațiile aliniate la numărul oficial al tragerii (nu la indicele arhivei) sau selecția aleatoare a seturilor (care, prin construcție, nu ar fi predictibilă). Dacă extragerile sunt uniforme și independente, istoricul nu oferă avantaj. Nu au existat evaluări prospective, emisii live sau promisiuni de câștig. Nu s-a făcut tuning după rezultat; sensibilitatea, universurile nule și puterea sintetică au fost declarate înainte și sunt doar descriptive; nicio altă mulțime de perioade nu se testează ca salvare. Zero incidente tehnice și zero amendamente în calificare, backtest și verificare (verificatorul a trecut la prima rulare); codul de calificare și cel al backtestului sunt același fișier (sha256 identic). Înainte de calificare au rulat numai testele unitare pe date construite minuscule (`jurnal/teste_unitare_precalificare.log`, 7/7). Aritmetica de mână dinaintea sigilării este păstrată în `jurnal/preprotocol/`. Rulările lungi au fost pornite ca sarcini proprii și s-au terminat complet.

