# RAPORT WU649 — „Urna ponderată” (cursa exponențială Luce, ordinea nevăzută marginalizată)

Protocol `WU649-P1` sigilat (sha256 `e46db3cf550ab912580b87d37b24bb883ea29f37caabcc5019e17fd7f851f961`, 2026-10-25T21:18:33.356842+00:00) înainte de orice cod și calcul WU649. Amendamentul 01 (toleranța de zgomot Armijo, τ = 1e-10) a fost sigilat tot înainte de cod (sha256 `a5b89c1c2c2ed69342894d964bc7c01a0b49b570accbe0ee0dcb08c5f30a48aa`, 2026-10-25T21:19:57.423035+00:00). Ipoteza este nouă și distinctă în pista QL649. Nu este o salvare a QL649 (0/6), a BO649 (0/6) sau a DL-649 (înghețat, neatins). Modelele închise nu au fost importate sau rulate. OGLINDA nu a fost atinsă. Precedente: Luce (1959), Plackett (1975), Wallenius (1963), Yellott (1977), Hunter (2004), Caron & Doucet (2012), Takahasi & Mori (1974). Calculul este clasic, NumPy fp64 pe CPU, cu certificate în Q (`Fraction`). Nu se revendică hardware cuantic, avantaj cuantic sau noutate mondială. `positive_claims_allowed=false`.

## Ipoteza

Fiecare bilă are o propensiune constantă `w_j`. Extragerea este mulțimea primelor 6 sosiri dintr-o cursă de ceasuri exponențiale independente (echivalent: extragere Luce secvențială fără întoarcere). Ordinea nu este observată și se marginalizează exact. Sub această ipoteză numărările nu sunt statistici suficiente, deci compoziția extragerilor poate schimba ordinea propensiunilor față de B. Estimatorul este MAP, cu prior `N(0, 0.2²)` pe `log w`; legea este probabilitatea exactă de includere.

## Calificare (înainte de istoria reală)

Status **WU_NOT_QUALIFIED** (5/6), cod sha256 `afc6789db7f41234…` (arhivat byte-identic în `rezultate/cod_calificare/wu649.py`), 2026-10-25T21:25:07.023021+00:00, 77 s. Numerele extrase din arhivă NU au fost folosite. Q2 a citit doar structura pașilor (numărul de extrageri pe zi), conform §4.

| Verificare | Rezultat | Detalii |
|---|---|---|
| Q1 exactitate în Q + multi-start | PASS | `{"instances": 42, "sets": 455, "order_eq_ie": true, "sum_one": true, "sum_pi_kappa": true, "multistart_cert": true, "rel_P": 1.1365420394772678e-15, "abs_pi": 2.220446049250313e-16, "grad": 9.992007221626409e-16, "hess": 2.1094237467877974e-15, "multistart_dtheta": 3.5091961281263906e-10}` |
| Q2 identități pe univers nul complet | PASS | `{"steps": 2427, "sum_q_max_err": 1.7763568394002505e-15, "q_in_01": true, "all_cert": true, "n_uncert": 0, "gnorm_max": 9.986477866874566e-09, "iters_max": 4, "iters_mean": 3.9406674907292953, "sum_theta_max": 3.615024946057588e-13, "fine_nodes_max_dq_same_theta": 8.326672684688674e-17, "fine_nodes_` |
| Q3 cauzalitate (trunchiat ≡ complet, bit cu bit) | PASS | `{"sampled_steps": 26}` |
| Q4 echivarianță la permutări | PASS | `{"max_abs_dq": 1.6653345369377348e-16, "sampled_steps": 26}` |
| Q5 martor de informație (aceleași numărări, altă compoziție) | PASS | `{"B_identical": true, "max_abs_dq_WU": 0.00404224961471511, "order_invariance_max_dq": 5.551115123125783e-16, "q6_q7_Hplus": [0.31381692160931435, 0.3097746719945993], "theta6_theta7_Hplus": [1.1651501303922365, 1.1497009650583867], "counts_1_8": [400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 105` |
| Q6 martor de decizie (WU≠B, WU≠R) | FAIL | `{"ticket_WU": [1, 2, 3, 4, 5, 6], "ticket_B": [1, 2, 3, 4, 5, 6], "ticket_R": [1, 2, 3, 4, 5, 6], "anticipation_q7_gt_q6": false}` |

### Ce a eșuat și de ce (descriptiv, fără reparare)

- Martorul de informație Q5 a trecut. La numărări identice, WU distinge compoziția: `max|Δq| = 0.004042`. Este invariant la ordinea temporală (`5.6e-16`).
- Martorul de decizie Q6 a eșuat. Anticiparea scrisă în protocol (`q_7 > q_6`) a fost greșită: `q_6 = 0.313817`, `q_7 = 0.309775`. Biletul WU `[1, 2, 3, 4, 5, 6]` coincide cu B `[1, 2, 3, 4, 5, 6]` și cu R `[1, 2, 3, 4, 5, 6]`.
- Interpretare propusă post-hoc, necertificată și netestată separat: într-o cursă pe mulțimi, `P(S)` este dominată de membrul cel mai lent al lui S. O bilă extrasă împreună cu bile slabe ar primi puțină informație despre propria pondere, pentru că blocajul este la colegii slabi. Una extrasă împreună cu bile tari ar primi mai multă. Ar fi un semn opus intuiției Bradley–Terry pe perechi („tăria calendarului”). Efectul observat este de ordinul doi și mic: Δθ ≈ 0.0154. În fixture-ul fixat, el a întărit alegerea lui B în loc să o schimbe.
- Conform §4, rezultatul se publică. Codul rămâne condiționat NEVALIDAT, iar istoria reală NU se atinge. Nu se face fixture „oglindit”, nu se schimbă anticiparea și nu se re-rulează. Eșecul este al martorului de decizie preînregistrat, nu un defect tehnic.

## Verificare independentă a necalificării

`verify_necalificare_wu649.py` (fără importuri din model și fără arhiva reală): **PASS** 20/20. Verificarea reconstruiește fixture-ul din textul protocolului, folosește o altă cuadratură (Gauss–Legendre, forma 3) și un Newton propriu, apoi reconfirmă: Q5 trece, Q6 eșuează și verdictul este `WU_NOT_QUALIFIED`. Verifică și identitatea exactă a cursei în Q, ordinea sigiliilor, arhivarea byte-identică a codului și absența artefactelor de backtest.

| Verificare | Rezultat | Valoare |
|---|---|---|
| protocol_sha_eq_seal_eq_qualification | PASS | `None` |
| amendment01_sha_eq_seal_eq_qualification | PASS | `None` |
| seal_order_protocol_lt_amendment_lt_qualification | PASS | `['2026-10-25T21:18:33.356842+00:00', '2026-10-25T21:19:57.423035+00:00', '2026-10-25T21:25:07.023021+00:00']` |
| dir_at_seal_only_protocol | PASS | `None` |
| dir_at_amendment_no_code | PASS | `['AMENDAMENT_01.md', 'PREINREGISTRARE_WU649.md', 'SIGILIU_PROTOCOL_WU649.json']` |
| qualification_code_archived_byte_identical | PASS | `afc6789db7f412346bf108949e08fac06e647c957a3a79d4f0c1c5405466ad87` |
| status_not_qualified_5_of_6 | PASS | `None` |
| only_Q6_failed | PASS | `None` |
| real_archive_not_read | PASS | `None` |
| no_backtest_artifacts | PASS | `None` |
| race_identity_exact_in_Q_independent | PASS | `None` |
| fixture_counts_1_to_7_eq_400 | PASS | `[400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 105.0]` |
| B_identical_Hplus_Hminus | PASS | `None` |
| indep_newton_converged | PASS | `[4.401812248033821e-12, 4.366285111245816e-12]` |
| Q5_info_witness_reconfirmed_dq_ge_1e-3 | PASS | `0.004042249614714277` |
| q6_q7_match_qualification_1e-8 | PASS | `[0.31381692160930685, 0.3097746719945926]` |
| anticipation_q7_gt_q6_false | PASS | `[0.31381692160930685, 0.3097746719945926]` |
| Q6_decision_witness_fails_WU_eq_B_eq_R | PASS | `[[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]]` |
| verdict_recomputed_not_qualified | PASS | `5` |
| no_forbidden_imports | PASS | `[]` |

## Consecințe

- **Niciun backtest WU649 pe arhivă**: zero ținte, zero predicții reale, zero porți evaluate.
- `wu649.py --real` și `--null` refuză (calificare absentă). `verify_wu649.py` (§7) rămâne cod condiționat nerulat.
- Rezultatul nu infirmă modelele Luce/Wallenius în general și nu spune nimic despre arhivă. Arată doar că familia WU-P1 nu a demonstrat, pe martorul preînregistrat, o decizie diferită de B și R.
- Orice idee nouă cere un protocol nou, sigilat înainte de cod. Nu este o variantă „reparată” a WU649.

## Fișiere

- `PREINREGISTRARE_WU649.md` — sha256 `e46db3cf550ab912…`
- `SIGILIU_PROTOCOL_WU649.json` — sha256 `55706d8faf26cc41…`
- `AMENDAMENT_01.md` — sha256 `a5b89c1c2c2ed693…`
- `SIGILIU_AMENDAMENT_01.json` — sha256 `5ef3ca2d84a8c0f9…`
- `wu649.py` — sha256 `1f0a9bc99dbc74cc…`
- `verify_wu649.py` — sha256 `a0fba731b997f5ff…`
- `verify_necalificare_wu649.py` — sha256 `32ddee67bcb9a6b8…`
- `raport_wu649.py` — sha256 `6a148379fdfb2b99…`
- `tests/test_wu649.py` — sha256 `f98188a64a367f38…`
- `rezultate/CALIFICARE.json` — sha256 `324f73487c56a2e2…`
- `rezultate/VERIFICARE_NECALIFICARE.json` — sha256 `54c89742274ef574…`
- `rezultate/cod_calificare/wu649.py` — sha256 `afc6789db7f41234…`
- `jurnal/calificare.log` — sha256 `bcaac9487b0f6216…`
