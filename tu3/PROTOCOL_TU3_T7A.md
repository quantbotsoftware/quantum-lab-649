# PROTOCOL TU3-T7A — protocolul comun al porturilor 7–12 + porturile DESCRIPTIVE BO (tab 7) și WU (tab 8) (sesiunea S4)

Stare: scris și sigilat (`tu3/SIGILIU_TU3_T7A.json`) ÎNAINTE de orice cod al acestei sesiuni (`code_files_present: []`).
Decizia utilizatorului: D3 = (b) — porturi DESCRIPTIVE, fără verdict și fără scor; verdictele 6/49 NU se transferă
(`tu3/DECIZII_PLAN_TU3_20261027.json` `b6a5ba05…`; plan `c7b4bfd3…`; cererea sesiunii S4 din 2026-10-27). Mecanismul de
schimbare a fișierelor înghețate: înlocuirea sigilată `inlocuiri_tu3/v1` (PROTOCOL_TU3_L649 §4), neschimbată.
Calcul clasic. Variantele produsului = minime de energie, NU predicții. `positive_claims_allowed=false`.

## 1. Inventar read-only (făcut înainte de acest protocol)

### 1.1 BO649 (`bo649/bo649.py`, protocol BO649-P1, verdict 6/49 închis)
- Generice în (N, κ): `bocpd` (recursia exactă BOCPD Beta–Bernoulli float64), `bocpd_exact`, `bocpd_brute`, `_pred_lik`,
  `_segment_lik`, `step_counts`, `targets_of`, `score_block`.
- Dependente de N = 49 / 6 bile: constantele `N49, K6`; `marginal_q` (baza 6/49), `top6`, `hyper_pmf`/`exact_tail`
  (C(49,6)), `summarize` (36/49), `predict`/`score`/`gates` (scor + verdict), `synthetic_steps`, `weighted_draw`,
  `regime_fixture`, `final_tickets`, `qualify`, `load_real`/`real_step_sizes` (parserul 6/49).
- Tabul 7 din `app.py` (6/49) afișează: verdictul, porțile, hits BO/B/R, verificarea independentă, p exact, nulele
  (= SCOR/VERDICT — EXCLUSE din port) și DESCRIPTIV: curba E[r] pe pași (`PREDICTII.npz` `ks`, `Er`) și posteriorul pe
  lungimea regimului la ultimul pas (`post_last`).

### 1.2 WU649 (`wu649/wu649.py`, protocol WU649-P1 + Amendamentul 01, `WU_NOT_QUALIFIED` 5/6, Q6 eșuat)
- Generice în (N, κ): `ts_nodes`, `_logsumexp`, `draw_terms`, `posterior_eval`, `_chol_ok`, `map_fit`, `inclusion`,
  `_prep`, `fit_prefix`, `run_steps`, `q1_exact` și ajutătoarele exacte.
- Dependente de 49 / 6: `N49, K6`; `marginal_q`, `top6`, `hyper_pmf`, `exact_tail`, `gates`, `summarize`, `predict`,
  `score`, `synthetic_steps`, `fixture_hplus` (indici 1..49, 42 bile „rest”), `next_prediction` (bilete), `qualify`.
- Tabul 8 din `app.py` (6/49) afișează numai calificarea (Q1–Q6, date construite/sintetice; `real_archive_read: false`)
  și graficul martorului Q5 (q pentru bilele 6 și 7 pe fixture-ul H+). Backtestul nu a existat.

### 1.3 Sigiliile care conțin fișierele atinse
- `tu3/ui_tu3.py`: înghețat în VS (21), DD (30), LN (55); în L649 `replaceable` (`9fe6c4d3…`) → `INLOCUIRE_L649_…`
  → `eb0a1a90…` (curent). Nu apare în sigiliul UI (`hashes` fără `ui_tu3.py`).
- `tests/test_app_tu3.py`: înghețat în VS, DD, LN; în L649 `replaceable` → `ea06ef9f…` (curent).
- `bo649/`, `wu649/`: în niciun sigiliu TU3; au sigiliile/manifestele proprii (rămân byte-identice).
- `tu3/porturi_712.py`, `tests/test_porturi_712.py`: fișiere noi, în niciun sigiliu.

### 1.4 Cititorii fișierelor atinse
- `tests/test_app_tu3.py` U3/U4: 12 taburi, `sum("NEAPLICABIL") == 6` în 5/40 și Joker, niciun „BO649-P1” în
  captions ⇒ se amendează NUMAI numărul 6 → 4 (taburile 9–12 rămân NEAPLICABIL până la S5/S6).
- `tests/test_l649.py` L3: `ui_tu3.py` = numai inserții față de `ui_tu3_pre_l649.py` ⇒ modificarea T7A trebuie să fie
  tot numai inserții (rămâne adevărat și față de baza L649). `test_validare_tu3.py` T5b: șirul `FAST_OVERRIDES` din
  `ui_tu3.py` neschimbat. T4 / L-teste: `replaced ⊆ L649.replaceable` (rămâne adevărat: T7A înlocuiește un subset).
- `tu3/matrice_init.py`, `tu3/validare_tu3.py`: integritatea prin `inlocuiri_tu3.resolve` (preia automat orice
  înregistrare validă nouă); NEMODIFICATE.
- `tu3/inlocuiri_tu3.py`: `OLD_SEALS` = VS/DD/LN/L649 — `--verifica` NU include sigiliul T7A; fișierele protejate de
  T7A sunt verificate de `tests/test_porturi_712.py` (P2) și de `plan_record` la scrierea înregistrării. Limită declarată;
  `inlocuiri_tu3.py` rămâne NEMODIFICAT.

### 1.5 Concluzie
Soluția încape în fișierele permise de cererea S4: `tu3/porturi_712.py` (nou), `tu3/ui_tu3.py` (numai inserții),
`tests/test_app_tu3.py` (U3/U4: 6 → 4), `tests/test_porturi_712.py` (nou), copia de referință
`tests/baseline/ui_tu3_pre_t7a.py` (0444) și artefactele de proces (acest protocol, sigiliul, înregistrarea,
raportul de identitate). Nu este nevoie de alte fișiere.

## 2. Domeniu (închis)
- Se pot schimba numai fișierele din `replaceable`: `tu3/ui_tu3.py` (`eb0a1a90…`), `tests/test_app_tu3.py`
  (`ea06ef9f…`).
- Fișiere noi permise: `tu3/porturi_712.py`, `tests/test_porturi_712.py`, `tests/baseline/ui_tu3_pre_t7a.py` (copie
  byte-identică a `ui_tu3.py` `eb0a1a90…`, 0444), `tu3/rezultate/T7A/IDENTITATE_T7A_<UTC>Z.json` (0444),
  `tu3/inlocuiri/INLOCUIRE_T7A_<UTC>Z.json` (0444). Efecte laterale tolerate și declarate: `__pycache__` nu se scrie
  (`-B`); fișierele derivate S9 ale aplicației (`tu3/date/derivat/…`) la repornire.
- Byte-identice (în `frozen_hashes`/`frozen_external` ale sigiliului): toate fișierele protejate de L649 (63 + 5
  externe), artefactele L649 (protocol, sigiliu, `inlocuiri_tu3.py`, `test_l649.py`, copiile `*_pre_l649.py`,
  `acceptare_l649.py`, `ACCEPTARE_L649_…`, `INLOCUIRE_L649_…`), fișierele L649 ajunse la capăt (`app.py` `7c5da1e6…`,
  `tu3/matrice_init.py`, `tu3/validare_tu3.py`, `tests/test_validare_tu3.py`, `tests/test_dedup_live.py`,
  `tests/test_lansator_tu3.py`) și TOATE fișierele din `bo649/` și `wu649/`. În particular NEMODIFICATE: `engine.py`,
  `parser.py`, `tu3/parser_multi.py`, `tu3/motor_n.py`, `tu3/motor_joker.py`, `run_app.sh`, `run_app_tu3.sh`,
  `porneste_aplicatia*.sh`, `tu3/arhiva_live.py`, `tu3/dedup_live.py`, `validare.py`, `app.py`; DL read-only;
  gardul prognozei neatins.

## 3. Protocolul COMUN al porturilor 7–12 (se aplică în S4, S5, S6)
- **P1 Port = funcție nouă** în `tu3/porturi_712.py`, parametrizată în (n, κ[, m]). Fișierele pistei închise NU se
  importă, NU se execută și rămân byte-identice. Algoritmul se copiază literal; se schimbă numai constantele 49/6 în
  parametri. Parametrii protocolului original rămân neschimbați (fără tuning, fără grile, fără alegeri după date).
- **P2 Numai DESCRIPTIV.** Permise: statisticile/graficele care descriu istoria jocului, ca în tabul original.
  Interzise: verdict, porți, scoruri (hits, log-score, Brier, exces, p-valori față de uniform), comparatori B/R folosiți
  ca scor, bilete/top-k, clasări ale numerelor, probabilități „pentru extragerea următoare”. Fiecare tab portat poartă
  eticheta „DESCRIPTIV” și textul „verdictul pistei 6/49 NU se transferă”.
- **P3 Test de identitate.** Portul rulat pe 6/49 (sursa înghețată `193eaf7a…`, aceeași ca pista originală) sau pe
  fixture-ul original reproduce cifrele artefactelor originale (citite read-only): întregi/booleeni EXACT; reale:
  egalitate bit cu bit (`IDENTITATE_EXACTA`); acceptat și `IDENTITATE_NUMERICA` dacă |Δ| ≤ 1e-12·max(1, |x|) pe fiecare
  valoare; altfel `FAIL` ⇒ portul NU se afișează (tabul rămâne NEAPLICABIL), sesiunea se oprește și se raportează.
  Identitatea compară numai mărimi descriptive; nu se recalculează scoruri, porți sau verdicte.
- **P4 Aplicabilitate.** Dacă o pistă nu are sens pentru un joc (de ex. depinde de glifele 1..49), tabul rămâne
  „NEAPLICABIL”, cu motivul scris.
- **P5 Date.** 5/40 și Joker: setul LIVE al modului (același `get_game_dataset`, sha afișat). Vederea 6/49 (`app.py`,
  înghețat) rămâne neschimbată: taburile 7–12 din 6/49 afișează în continuare artefactele originale.
- **P6 Calcul.** NumPy float64 pe CPU (ca pistele originale; necesar pentru identitate), rezultate în cache pe
  (mod, sha LIVE). Clasic; fără afirmații GPU/cuantice pentru aceste taburi.
- **P7 Joker.** Componenta principală (n = 45, κ = 5) și bila Joker (m = 20, κ = 1) ca serii separate; fără model
  încrucișat.
- **P8 Fără scrieri din UI.** Porturile nu scriu fișiere. Excepție: CLI `--identitate … --out` scrie raportul de
  identitate în `tu3/rezultate/T7A/` (creare exclusivă, 0444).

## 4. Portul BO (tab 7)
- `bo_describe(steps, N, kappa)`: `bocpd` literal (h = 1/250, m0 = 12, `RECENT_R` = 100), `keep_post` = ultimul pas;
  `ks` = pașii de la `WARMUP` = 100 (dacă sunt ≥ 101 pași). Ieșiri: `ks`, `Er` (lungimea așteptată a regimului curent),
  `p_recent` = P(r ≤ 100), `post_last`, `logZ` (numai în raportul de identitate; NU se afișează și nu se compară cu
  uniformul), `n_steps`, `n_draws`. NU se calculează/expun `q`, bilete, hits, scoruri, porți.
- UI 5/40 și Joker: carduri (extrageri, pași, E[r] la ultimul pas, P(r ≤ 100) la ultimul pas, pași cu P(r ≤ 100) > ½),
  graficele „E[r] pe pași” (+ linia r = k) și „posteriorul la ultimul pas”; la Joker, aceleași pentru bila Joker.
- Identitate (6/49, înghețat, pașii exact ca `load_real`: `parser.build_dataset(device="cpu")`, onehot → float64,
  `step_offsets`): față de `bo649/rezultate/backtest_unic/PREDICTII.npz` — `ks`, `Er`, `p_recent`, `post_last`, `logZ`;
  față de `REZULTATE.json` — `Er.{min, median, max, last}`, `steps_p_recent_gt_half` (= 62), `n_steps_predicted`
  (= 2427), `start.source_sha256`; sha-ul `PREDICTII.npz` = `predictions_sha256`. Mediu: implicit (ca rularea originală).

## 5. Portul WU (tab 8)
- **5a Martorul de informație (fixture construit, nu date de joc)** — generalizarea literală a `fixture_hplus`:
  `rest = κ+2..n`, R = n − κ − 1; pentru i = 0..399: β = [κ+1] + [rest[((κ−1)i + m) mod R], m < κ−1],
  γ = [rest[(κ i + m + ⌊R/2⌋) mod R], m < κ], α = [1..κ]; pașii (β, γ, α). H− = H+ cu etichetele κ ↔ κ+1 schimbate;
  ordinea permutată cu `default_rng([649, 8, 5])`. Ieșiri: q și θ pentru bilele κ și κ+1 pe H+, numărările bilelor
  1..κ+2, max|Δq| (H+ vs H−), invarianța la ordine, „aceleași numărări” (π_B identic), cele 3 certificate. FĂRĂ bilete
  (Q6 exclus). Pentru (49, 6) formula = `fixture_hplus` exact. Pentru κ = 1 martorul nu se aplică (cursa Luce cu o
  singură bilă depinde numai de numărări) — se scrie motivul.
- Identitate (49, 6): egal cu `wu649/rezultate/CALIFICARE.json` Q5 `detail` — `q6_q7_Hplus`, `theta6_theta7_Hplus`,
  `counts_1_8`, `max_abs_dq_WU`, `order_invariance_max_dq`, `B_identical`, `cert`. Mediu: subproces cu
  `OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1` (ca Amendamentul 01 WU).
- **5b Ajustarea descriptivă pe istoria jocului:** θ̂ = MAP literal (σ = 0.2, Newton–Levenberg + Armijo, θ0 = 0,
  GTOL 1e-8, MAXIT 200) pe TOATE extragerile setului LIVE al modului. Afișate: θ̂_j în ordinea naturală a bilelor (fără
  sortare), frecvența observată vs θ̂ (punct pe bilă), certificatul (‖g‖∞, hessiană negativ definită), iterațiile,
  Σθ̂. NU se afișează: π/q (includere), top-k, bilete, clasări. Joker: componenta principală + bila Joker (κ = 1).
- Declarat: WU nu a citit niciodată arhiva 6/49 reală; portul NU rulează pe 6/49 reală (tabul 8 din 6/49 rămâne cel
  din `app.py`). Pe 5/40/Joker este primul contact al modelului cu o istorie reală, strict descriptiv; pista rămâne
  `WU_NOT_QUALIFIED` și nimic de aici nu o califică.

## 6. `tu3/ui_tu3.py` — numai inserții (față de `tests/baseline/ui_tu3_pre_t7a.py` și, implicit, față de baza L649)
1. În bucla taburilor 7–12, imediat după antetul `for`: o linie
   `if t7a_port(t_idx, tabs[t_idx], mode, ds, key, ctx):` + `continue` (portul tratează tabul; altfel NEAPLICABIL ca acum).
2. La sfârșitul fișierului: secțiunea „TU3-T7A” (cache-urile `st.cache_data` pe (mod, sha LIVE), randarea BO/WU).
   Orice excepție a portului ⇒ `st.error` explicit în tab, fără comutare tăcută pe NEAPLICABIL.
Niciun rând existent șters sau schimbat.

## 7. Teste
- `tests/test_app_tu3.py` — U3/U4: NUMAI `== 6` → `== 4` (comentariul actualizat). Restul neschimbat.
- `tests/test_porturi_712.py` (nou): P1 sigiliul înainte de cod (sha, `code_files_present: []`, `replaceable`, 0444);
  P2 fișierele protejate byte-identice + `porturi_712.py` nu importă `bo649`/`wu649`/`engine`/`validare`/`motor_*`;
  P3 identitatea BO (subproces, mediu implicit); P4 identitatea WU (subproces, un fir); P5 certificat BO: `bocpd` vs
  recursia exactă în Q pe instanțe mici (κ = 1 și κ = 5); P6 certificat WU: `inclusion` și log P vs enumerarea exactă
  Luce pe instanțe mici (κ ∈ {1, 2, 5}); P7 rulare generică pe 5/40 și Joker LIVE (forme, finite, Σ post = 1,
  E[r] ≤ k, |Σθ̂| ≤ 1e-7, certificat); P8 numai descriptiv: nicio cheie interzisă în ieșirile porturilor; AppTest 5/40 și
  Joker: taburile 7–8 conțin „DESCRIPTIV” și nu „NEAPLICABIL”, taburile 9–12 „NEAPLICABIL”; P9 numai inserții față de
  copia de referință; P10 (după înregistrare) `INLOCUIRE_T7A_*` validă, `inlocuiri_tu3 --verifica` ok.

## 8. Ordinea lucrului
1. Sigiliul (0444). 2. Copia de referință (0444). 3. `porturi_712.py`, inserțiile `ui_tu3.py`, testele. 4. Teste +
raportul de identitate (`--identitate toate --out`). 5. Înregistrarea `INLOCUIRE_T7A_<UTC>Z.json` (`--inregistreaza`).
6. Suitele complete, matricea, `--verifica`, DL. 7. Repornirea aplicației din pictogramă (buclă health ok); AppTest în
configurația de PROTOCOL pe 5/40 și Joker fără excepții.

## 9. Criterii de acceptare — verdict `T7A_PASS` (consemnat în predare)
- C1 suitele existente **33 passed, 3 skipped**; `test_lansator_tu3.py` + `test_l649.py` **16 passed**;
  `tests/test_porturi_712.py` toate trecute.
- C2 identitatea BO și WU: `IDENTITATE_EXACTA` sau `IDENTITATE_NUMERICA` (P3), raport 0444.
- C3 0 drift pe fișierele protejate ale T7A (+ externe); `inlocuiri_tu3 --verifica` → `"ok": true`; `dedup_live
  --verifica` OK; DL exit 0.
- C4 fișierele schimbate/noi = numai cele din §2 (git read-only prin `./dev-git`).
- C5 aplicația repornită din pictogramă: matricea „TOATE 3 MODURILE READY”, health ok, numai 127.0.0.1; AppTest
  PROTOCOL pe 5/40 și Joker fără excepții, taburile 7–8 cu porturile.

## 10. Abateri și limite declarate dinainte
Porturile rulează pe CPU (float64), nu pe GPU. Toleranța `IDENTITATE_NUMERICA` (1e-12) e fixată aici, înainte de cod.
`--verifica` nu acoperă sigiliul T7A (§1.4). Arhiva este deja explorată; porturile nu creează set „nevăzut” și nu
evaluează nimic prospectiv. Sigilii locale, fără atestare externă. Nicio afirmație de avantaj predictiv.

## 11. În afara domeniului
Taburile 9–12 (S5–S6), scorul real 5/40/Joker (S7–S8), vederea 6/49, gardul prognozei, `inlocuiri_tu3.py`, orice
rulare a codului pistelor închise.
