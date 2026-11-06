# RAPORT PL649 — „Singularitatea Planck” (rețea de spin + holonomii SU(3) + vid Higgs)

Generat 2026-10-26T15:01:04Z din artefacte. Protocol `PL649-P1`, sha256 `779a108ed9cab8946110e5f048dedd4535cc5e40bdcaae9ea40df0abbfc8c617`, sigilat 2026-10-26T12:50:47Z înainte de cod. Calcul CLASIC pe GPU (NVIDIA RTX 5060 Laptop, PyTorch CUDA); termenii LQG / Yang–Mills / Higgs sunt inspirație matematică. `positive_claims_allowed=false`. Arhiva este deja explorată (nu set nevăzut).

## Verdict

- Calificare: **PL_QUALIFIED 6/6** (2026-10-26T12:57:11Z, 31 s, arhiva reală neatinsă).
- Backtest unic (START 2026-10-26T12:58:21Z, 2495 ținte): **PL_NO_PROMOTION_EXPLORATORY 0/6**.
- Verificare independentă: **PASS 20/20**.

## Backtest unic

| model | hits | exces | log | Brier |
|---|---|---|---|---|
| PL | 1772 | -0.0245 | -46070.16 | 13293.00 |
| B | 1847 | +0.0056 | -45465.71 | 13139.97 |
| R | 1821 | -0.0048 | -45611.60 | 13171.64 |
| U | — | 0 | -45451.50 | 13136.94 |
| top-6 după π (descriptiv) | 1805 | -0.0112 | — | — |

- logPL−U = -618.66 (estimarea de mână sub nul ≈ −530, §3.6); logPL−B = -604.44.
- Jumătăți: hitsPL−B = -30 / -45; logPL−B = -304.88 / -299.56.
- p exact (hits ≥ 1772 | U) = 0.948; distribuția potrivirilor [1123, 1019, 307, 45, 1, 0, 0].
- Bilet PL ≠ B la 2495/2495, ≠ R la 2495, ≠ top-6 după π la 1994 (efectul termenului de pereche).
- Decalaj energetic minim al vidului 9.37e-06 (pași cu decalaj ≤ 1e-6: 0); eroarea de unitaritate finală 1.3e-14; walk-forward 154 s cu enumerarea completă a 13.983.816 bilete la fiecare pas.
- Consecvență B/R: {'hits_B': 1847, 'hits_R': 1821, 'targets': 2495, 'consistent': True}.

| poartă | cerință | rezultat |
|---|---|---|
| 1 | ExcesPL/U >= 0.20 | FAIL |
| 2 | hitsPL > hitsB și hitsPL > hitsR | FAIL |
| 3 | logPL−logU > 0 și logPL−logB > 0 | FAIL |
| 4 | BrierPL < BrierU, BrierB, BrierR | FAIL |
| 5 | ambele jumătăți: exces > 0 și hitsPL−hitsB > 0 | FAIL |
| 6 | ambele jumătăți: logPL−logB > 0 | FAIL |

## Calificare (martori analitici)

- **Q1** PASS: `{"pass": true, "max_dkappa": 9.332812300755222e-16, "max_deps": 1.2698175844150228e-15, "max_unitarity": 1.4432901989173413e-15, "max_det": 1.5543741876503828e-15, "max_gauge_dev": 4.410014020628239e-14}`
- **Q2** PASS: `{"pass": true, "max_sum_pi_dev": 3.3306690738754696e-16, "q_law_in_01": true, "kappa_finite": true, "incremental_equals_scratch": true, "max_link_dev": 0.0, "walk_seconds": 1.8293659687042236}`
- **Q3** PASS: `{"pass": true, "max_pi_dev": 0.0, "tickets_identical": true}`
- **Q4** PASS: `{"pass": true, "max_pi_dev": 4.884981308350689e-15, "checked": 26, "gap_gt_1e-6": 26, "tickets_match": true, "perm_seed": [649, 12, 4]}`
- **Q5** PASS: `{"pass": true, "a_same_counts_pairs_area_volume_B": true, "b_Hminus_uniform": true, "max_pi_dev_Hminus": 0.0, "c_kappa": true, "kappa_Hplus": {"1": 0.0006420364437070836, "7": 0.0006420364437070836, "13": 0.0003210182218535973, "max_abs_rest": 2.220446049250313e-16}, "d_pi": true, "pi_Hplus": {"1": 0.0026360819615030904, "13": 0.007687388882359446, "2": 0.02241809954763045}, "q2_minus_q1": 0.05934`
- **Q6** PASS: `{"pass": true, "ticket_PL_Hplus": [2, 3, 4, 5, 6, 8], "ticket_B": [1, 2, 3, 4, 5, 7], "ticket_R": [1, 7, 13, 14, 15, 16], "ticket_PL_Hminus": [1, 2, 3, 4, 5, 6], "ew_order_ok": true, "E_gap_Hplus": 0.0}`

## Descriptiv (nu schimbă verdictul)

- **1024 universuri nule pe GPU** (legea; 820 s): logPL−U medie -514.4 (sd 47.7); valoarea reală are rangul 24/1024 (≤). logPL−B: rang 25/1024; logPL−B > 0 în 0/1024. hits top-6 π: medie 1832.0, rang real 250/1024. Porțile legii 3/4/6 trecute în 0/1024.
- **32 universuri nule complete** (bilet QUBO exact): porți trecute [17, 10, 5, 0, 0, 0, 0] (max 2/6); hitsPL medie 1835.7, rang real 3/32.
- Interpretare: valorile reale stau în coada de JOS a nulului (log, hits), deci nicio indicație de semnal pozitiv; coada de jos NU se tratează ca anti-semnal exploatabil (nicio inversare post-hoc a modelului). Aria totală are dispersie nulă foarte mică deoarece numărul total de co-extrageri este fix (2595·15).
- **Putere H_PL γ = 0.5** (8 universuri): exces mediu +0.622; porți [0, 0, 0, 0, 0, 0, 8]; poarta 1 în 8/8.
- **Putere H_PL γ = 0.125** (8 universuri): exces mediu +0.143; porți [0, 0, 8, 0, 0, 0, 0]; poarta 1 în 0/8.
- **Certificatul anealerului Higgs** (50.000 replici, pașii din 97 în 97): succes 100% (26/26).
- **Starea finală** (2595 extrageri): arie Planck totală 20041.6 vs nul 20041.618 ± 0.014 (PAD +1.44e-07, z +0.20); erori de holonomie 0% (max 1.3e-14); monopoli XY persistenți 0/18424; anealerul = vidul exact: True.
- Produs (UI, tabul 12): cele 3 variante = [[14, 15, 31, 35, 42, 43], [30, 35, 37, 42, 44, 49], [8, 9, 19, 22, 31, 45]] — minimele exacte ale energiei PL, NU predicții; backtestul nu a arătat niciun avantaj.

## Abateri, incidente, limite

- `engine.py`/`parser.py` NEMODIFICATE (QL649 sigilat); motorul v2.0 este `pl649/pl_core.py`; `app.py` primește aditiv tabul 12.
- Test de dezvoltare (fum) pe date ALEATOARE înainte de calificare, păstrat în `jurnal/dezvoltare/` (nu pe fixture-le Q5/Q6, nu pe arhivă). Zero amendamente, zero incidente tehnice la calificare/backtest.
- Nicio pretenție fizică: separarea de scară Planck–urnă ~33 ordine de mărime; volumul este un proxy; „monopolii” sunt vortexuri XY. Rezultatul negativ nu infirmă alte idei; nu se salvează PL (fără alt ε, β, η, generatori, orientări).
