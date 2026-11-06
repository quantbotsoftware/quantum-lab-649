# RAPORT BO649 — „Rupturi de regim” (detecție bayesiană online a schimbărilor)

Protocol `BO649-P1` sigilat (sha256 `983707bdcb8bb68c44e56c9caa23854b3f3a230676a6a20ac98fca40b154ca85`, 2026-10-25T19:21:57.111799+00:00) înainte de orice cod și calcul BO649. Ipoteză nouă și distinctă în pista QL649. Nu este o salvare a QL649 (închis 0/6) sau a DL-649 (înghețat, neatins). Modelele închise nu au fost importate sau rulate. OGLINDA nu a fost atinsă. Precedente: Adams & MacKay (2007), Fearnhead & Liu (2007). Calculul este clasic exact, NumPy fp64 pe CPU, cu certificate în Q (`Fraction`). Nu se revendică hardware cuantic, avantaj cuantic sau noutate mondială. `positive_claims_allowed=false`. Arhiva este deja explorată, deci nu este un set nevăzut.

## Calificare (înainte de istoria reală)

Status **BO_QUALIFIED** (6/6), cod sha256 `6c82533048d8e338…`, 2026-10-25T19:25:54.637569+00:00. Numerele din arhivă nu au fost folosite; s-a folosit doar structura pașilor.

| Verificare | Rezultat | Detalii |
|---|---|---|
| Q1 | PASS | `{"instances": 48, "certificates_in_Q": 48, "segmentations_total": 5632, "float_max_dq": 3.3306690738754696e-16}` |
| Q2 | PASS | `{"sum_q_max_abs_err": 2.6645352591003757e-15, "q_in_open_unit": true, "n_steps": 2527, "logZ": -47393.03032995504}` |
| Q3 | PASS | `{"k_sampled": 26, "max_abs_diff": 0.0}` |
| Q4 | PASS | `{"max_abs_diff": 7.105427357601002e-15, "steps": 600}` |
| Q5 | PASS | `{"same_multiset": true, "B_law_and_ticket_identical": true, "max_abs_dq_BO": 0.11269161137953652, "ticket_BO_plus": [7, 8, 9, 10, 12, 17], "ticket_BO_minus": [1, 2, 3, 4, 5, 6], "ticket_B": [1, 2, 3, 4, 5, 6], "Er_plus": 333.7899319308923, "Er_minus": 928.5698` |
| Q6 | PASS | `{"fixture_seed": 0, "seeds_tried": 1, "ticket_BO": [7, 8, 9, 10, 12, 17], "ticket_B": [1, 2, 3, 4, 5, 6], "ticket_R": [7, 12, 13, 14, 17, 18], "Er_BO": 333.7899319308923, "F1": [1, 2, 3, 4, 5, 6], "F2": [7, 8, 9, 10, 11, 12], "F3": [13, 14, 15, 16, 17, 18]}` |

## Backtest walk-forward cauzal unic

Sursa are sha256 `193eaf7a6f4f9948a43e53e053ee8c03b0cd591bed0279d15d312a2857fa707c`, cu 2595 extrageri și 2527 pași-zi, de la 1993-08-08 la 2026-10-18. Încălzirea are 100 de pași; rămân **2495 ținte**. Configurația este `h = 1/250` și `m0 = 12`. Predicțiile au fost sigilate înainte de scor: `PREDICTII.npz` are sha256 `19277671320e56eab1474d3b7233885f625639f3dc9a8c55e407a43896addc3a`. Durata calculului a fost 1.7 s.

| Parte | Ținte | hitsBO | hitsB | hitsR | ExcesBO/U | logBO−U | logBO−B | BrierBO | BrierU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Total | 2495 | 1807 | 1847 | 1821 | -0.010445 | -19.473653 | -5.255630 | 13141.146773 | 13136.938776 |
| Prima jumătate | 1247 | 880 | 902 | 919 | -0.029000 | -17.359788 | -4.933302 | 6569.540756 | 6565.836735 |
| A doua jumătate | 1248 | 927 | 945 | 902 | +0.008095 | -2.113866 | -0.322328 | 6571.606017 | 6571.102041 |

| Poartă | Cerință | Rezultat | Valoare |
|---|---|---|---|
| 1 | ExcesBO/U >= 0.20 | FAIL | `-0.01044538055703248` |
| 2 | hitsBO > hitsB și hitsBO > hitsR | FAIL | `[1807, 1847, 1821]` |
| 3 | logBO−logU > 0 și logBO−logB > 0 | FAIL | `[-19.47365332229674, -5.255629883475194]` |
| 4 | BrierBO < BrierU, BrierB, BrierR | FAIL | `[13141.146773133052, 13136.9387755102, 13139.967405084508, 13171.643465301917]` |
| 5 | ambele jumătăți: exces > 0 și hitsBO−hitsB > 0 | FAIL | `[[-0.029000212755511234, -22], [0.008094583987441117, -18]]` |
| 6 | ambele jumătăți: logBO−logB > 0 | FAIL | `[-4.933301776291046, -0.3223281071841484]` |

**Verdict: `BO_NO_PROMOTION_EXPLORATORY` (0/6 porți).**

Date descriptive:
- p exact (hitsBO ≥ observat | extrageri uniforme independente) = 0.757525;
- potriviri BO (0..6): [1090, 1042, 325, 37, 1, 0, 0]; așteptat sub U: [1087.7, 1030.5, 330.3, 44.0, 2.4, 0.0, 0.0];
- biletul BO diferă de B la 1372 pași-țintă și de R la 2427;
- E[r] pe pașii-țintă: min 7.6, median 1232.5, max 2486.7, ultimul 2484.5;
- pași cu P(r ≤ 100) > 0.5: 62;
- la ultimul pas, P(r ≥ 2000) = 0.9838.

Interpretare: posteriorul BO revine în cea mai mare parte la ipoteza „un singur regim lung”. În acest caz BO se apropie de B, cu netezirea priorului și cu fluctuații suplimentare. Pierderea log față de B și U este costul flexibilității fără semnal, așa cum se așteaptă sub uniformitate.

Verificarea independentă (`verify_bo649.py`, fără import din bo649, engine, parser, validare sau torch; log-domeniu și sume de prefix) a dat **PASS** (72/72).

## Sensibilitate (strict descriptivă, declarată în §6; nicio configurație nu poate fi promovată sau selectată)

| h | m0 | hitsBO | ExcesBO/U | logBO−U | logBO−B | porți |
|---:|---:|---:|---:|---:|---:|---:|
| 1/100 | 6 | 1804 | -0.011648 | -20.571 | -6.353 | 0/6 |
| 1/100 | 12 | 1792 | -0.016457 | -26.562 | -12.344 | 0/6 |
| 1/100 | 48 | 1824 | -0.003632 | -24.703 | -10.485 | 0/6 |
| 1/250 | 6 | 1812 | -0.008441 | -15.951 | -1.733 | 0/6 |
| 1/250 | 12 | 1807 | -0.010445 | -19.474 | -5.256 | 0/6 |
| 1/250 | 48 | 1837 | +0.001579 | -18.605 | -4.387 | 0/6 |
| 1/1000 | 6 | 1832 | -0.000425 | -14.073 | +0.145 | 0/6 |
| 1/1000 | 12 | 1824 | -0.003632 | -15.914 | -1.696 | 0/6 |
| 1/1000 | 48 | 1832 | -0.000425 | -15.170 | -0.952 | 0/6 |

## Universuri nule sintetice (descriptiv, M = 64, seed `[649, 2, u]`)

- Excesul BO: medie +0.004641, abatere 0.013988. Valoarea reală -0.010445 are rangul empiric 10/64 (≤).
- logBO−B: medie -2.585, abatere 1.945. Valoarea reală -5.256 are rangul empiric 7/64 (≤).
- Porți trecute pe universurile nule: distribuția [41, 19, 4, 0, 0, 0, 0] (0..6); maximum 2/6.

## Limite

Rezultatul nu demonstrează avantaj predictiv real și nu infirmă universal alte idei sau alte modele de regim, de exemplu cu hazard variabil sau cu rate corelate. Dacă extragerile sunt uniforme și independente, istoricul nu oferă avantaj. Nu au existat evaluări prospective, emisii live sau promisiuni de câștig. Nu s-a făcut tuning după rezultat; grila de sensibilitate a fost declarată înainte și este doar descriptivă. O singură corectură a fost făcută într-un test de inginerie (`tests/test_bo649.py`): așteptarea greșită a testului pentru biletul cu egalități a fost reparată după prima rulare a testelor. Modelul, protocolul și pragurile nu au fost atinse, iar testul nu este o poartă.

