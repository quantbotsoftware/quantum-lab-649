# PROTOCOL TU3-T7B — porturile DESCRIPTIVE GL (tab 9) și SE (tab 10) (sesiunea S5)

Stare: scris și sigilat (`tu3/SIGILIU_TU3_T7B.json`) ÎNAINTE de orice cod al acestei sesiuni (`code_files_present: []`).
Decizia utilizatorului: D3 = (b) — porturi DESCRIPTIVE, fără verdict și fără scor; verdictele 6/49 NU se transferă
(`tu3/DECIZII_PLAN_TU3_20261027.json` `b6a5ba05…`; plan `c7b4bfd3…`; cererea sesiunii S5 din 2026-10-27, Mesajul 46).
Se aplică protocolul COMUN al porturilor `PROTOCOL_TU3_T7A.md` §3 (P1–P8, `f375bae9…`), neschimbat, cu precizarea
declarată la §3.3 (P6). Mecanismul de schimbare a fișierelor înghețate: înlocuirea sigilată `inlocuiri_tu3/v1`
(PROTOCOL_TU3_L649 §4), neschimbat. Calcul clasic. Variantele produsului = minime de energie, NU predicții.
`positive_claims_allowed=false`.

## 1. Inventar read-only (făcut înainte de acest protocol)

### 1.1 GL649 (`gl649/gl649.py`, protocol GL649-P1, `GL_NO_PROMOTION_EXPLORATORY` 2/6, închis)
- Generice (depind de N/κ numai prin constantele modulului): `solve_exact` (Bareiss exact în Q, complet generic),
  `glyph_matrix` (`range(1, N49 + 1)` → `1..N`), `G_COLSUM`, `H_FR`, `HTH`, `gl_core` (Woodbury), `gl_predict_counts`
  (`K6`, `P0`, `SIGMA0_2`), `pkp_matrix`, `gl_predict_direct` (rezolvarea directă N×N).
- Dependente de N = 49 / 6 bile sau de scor: `P0 = 6/49`, `SG2 = 9/60025`, `SE2 = 9/240100`, `SIGMA0_2 = 43/392`
  (formele lor generale: `(p0/10)²`, `(p0/20)²`, `p0(1−p0)·N/(N−1)`); `ticket_exact`, `marginal_q`, `top6`,
  `comparators`, `score_block`, `hyper_pmf`, `exact_tail`, `gates`, `summarize`, `predict` (bilete), `score`,
  consistența cu BO649 (`1847/1821/2495`), `load_real`/`real_step_sizes` (parserul 6/49), `synthetic_steps`,
  `rotation_history`, `relabel`, `digit_perm`/`CYCLE5`/`TRANS59`/`sector_lambdas` (sectorul antisimetric pe cifrele 5..9
  cere etichetele `10t + d` până la 49), fixture-urile F5/F6, `q1`–`q6`, `run_*`.
- **Decizia P4 pentru GL: PORT (aplicabil), nu NEAPLICABIL.** Motiv: structura folosită de model este incidența
  glifelor zecimale `G[j, d]` = numărul de apariții ale cifrei d în scrierea lui j fără zero în față; în cod ea depinde
  de 49 numai prin capătul `range(1, 50)`. Bilele 5/40 (1..40), Joker principal (1..45) și bila Joker (1..20) poartă
  aceleași numere zecimale tipărite, deci `G_N` (N × 10) e definită a priori, fără date, pentru fiecare componentă;
  premisa fizică a pistei (cerneală/vopsea/gravură) este la fel de NEVERIFICATĂ pe orice joc ca pe 6/49. Exemplul din
  PROTOCOL_TU3_T7A §3 P4 („de ex. depinde de glifele 1..49”) era ipotetic; inventarul arată că dependența este de
  scrierea zecimală, nu de 49. Ce NU se portează: sectorul antisimetric/martorii Q5–Q6 (specifici etichetelor
  `10t + d ≤ 49`), biletele și scorurile. Toate cifrele 0..9 apar în fiecare componentă (N = 20: cifra 0 în 10, 20;
  cifrele 3..9 în d și 1d), iar `M = (a/s_g²) I₁₀ + HᵀH` rămâne pozitiv definită pentru orice N.
- Tabul 9 din `app.py` (6/49) afișează: cardul și tabelul calificării (Q1–Q6), verdictul backtestului, porțile,
  verificarea independentă, graficul hits GL/B/R (= VERDICT/SCOR — EXCLUSE din port) și DESCRIPTIV: „efecte de glifă
  ajustate la ultimul pas (relativ la p0)” (`REZULTATE.json` `gamma_last_relative`).

### 1.2 SE649 (`se649/se649.py`, protocol SE649-P1, `SE_NO_PROMOTION_EXPLORATORY`, închis)
- Generice: `season_of` (luna datei: DJF/MAM/JJA/SON), `solve_exact`, `se_weights` (Sherman–Morrison), `se_weights_direct`,
  `se_predict_counts` (prin `P0`, `TA2`, `TB2`, `SIGMA0_2`, `N49`, `K6`), `season_prefix` (`N49`), `g_statistic`
  (`N49`, `6.0`).
- Dependente de 49 / 6 sau de scor: `P0`, `TA2 = 9/240100`, `TB2 = 36/60025`, `SIGMA0_2 = 43/392` (forme generale
  `(p0/20)²`, `(p0/5)²`, `p0(1−p0)·N/(N−1)`); `ticket_exact`, `marginal_q`, `top6`, `comparators`, `score_block`,
  `hyper_pmf`, `exact_tail`, `gates`, `summarize`, `predict` (bilete), `score` (hits pe anotimpuri), `load_real`,
  `real_step_structure`, `synthetic_steps`, `block_history`, `predict_at` (bilete), fixture-urile, `q1`–`q6`, `run_*`.
- Aplicabil (P4): anotimpurile vin din datele extragerilor, care există în setul LIVE al fiecărui mod (`step_dates`);
  nu depind de etichete. PORT.
- Tabul 10 din `app.py` (6/49) afișează numai calificarea, verdictul, porțile, verificarea, hits SE/B/R și „hits SE −
  hits B pe anotimpul țintei” (toate = VERDICT/SCOR — EXCLUSE). Mărimile DESCRIPTIVE ale pistei sunt în
  `REZULTATE.json` (§6 „Descriptiv” al SE649-P1): `final_state.n_per_season`, `final_state.weights_by_target_season`
  (ponderile w_φ ale modelului pe istoria completă), `G_label_x_season` (statistica G a tabelului etichetă × anotimp).
  Rangul lui G între universurile nule (echivalent unei p-valori față de uniform) este EXCLUS (P2).

### 1.3 Sigiliile care conțin fișierele atinse
- `tu3/ui_tu3.py`: înghețat în VS, DD, LN; `replaceable` în L649 și T7A; curent `1128492b…` prin `INLOCUIRE_T7A_…`.
- `tests/test_app_tu3.py`: înghețat în VS, DD, LN; `replaceable` în L649 și T7A; curent `ca849e6f…`.
- `tu3/porturi_712.py` (`88dd168b…`), `tests/test_porturi_712.py` (`68cb1efc…`): create în T7A (`new_files_planned`),
  în niciun `frozen_hashes`/`replaceable` al vreunui sigiliu TU3 până acum.
- `gl649/`, `se649/` (54 de fișiere): în niciun sigiliu TU3; au sigiliile/manifestele proprii (rămân byte-identice).
  Sigiliul UI nu conține niciunul dintre fișierele atinse.

### 1.4 Cititorii fișierelor atinse
- `tests/test_app_tu3.py` U3/U4: `sum("NEAPLICABIL") == 4` ⇒ se amendează NUMAI `4 → 2` (taburile 11–12 rămân
  NEAPLICABIL până la S6).
- `tests/test_porturi_712.py`: P8 cere NEAPLICABIL în taburile 9–12 ⇒ se amendează (9–10 = porturi DESCRIPTIVE, 11–12
  NEAPLICABIL; numărul de grafice pentru 9–10); P9 cere `== 4` în `test_app_tu3.py` ⇒ `== 2`; P10 cere ca `to` din
  `INLOCUIRE_T7A_…` să fie sha-ul curent ⇒ după T7B devine „lanțul pornit din `from` al T7A ajunge la sha-ul curent”.
  P1–P7 neschimbate (P2 rămâne valabil: T7B nu atinge `frozen_hashes` ale T7A).
- `tests/test_l649.py` L3: `ui_tu3.py` numai inserții față de `ui_tu3_pre_l649.py` (rămâne adevărat: T7B face numai
  inserții). `test_validare_tu3.py` T4/T5b: `replaced ⊆ L649.replaceable` pe sigiliile vechi (porturile nu sunt în
  ele) și `FAST_OVERRIDES` neschimbat. `matrice_init`/`validare_tu3`: integritatea prin `inlocuiri_tu3.resolve`, care
  urmează lanțul VS → L649 → T7A → T7B (NEMODIFICATE).
- `inlocuiri_tu3.py`: `OLD_SEALS` = VS/DD/LN/L649 — `--verifica` nu include sigiliile T7A/T7B; protecția lor e dată de
  testele P2 (T7A) și B2 (T7B) și de `plan_record`. Limită declarată; `inlocuiri_tu3.py` rămâne NEMODIFICAT.

### 1.5 Concluzie
Soluția încape în fișierele permise de cererea S5: `tu3/porturi_712.py` (extins, numai inserții), `tu3/ui_tu3.py`
(numai inserții), `tests/test_app_tu3.py` (U3/U4: 4 → 2), `tests/test_porturi_712.py` (P8/P9/P10 amendate), test nou
`tests/test_porturi_t7b.py`, copiile de referință (0444) și artefactele de proces. Nu este nevoie de alte fișiere.

## 2. Domeniu (închis)
- Se pot schimba numai fișierele din `replaceable`: `tu3/ui_tu3.py` (`1128492b…`), `tests/test_app_tu3.py`
  (`ca849e6f…`), `tu3/porturi_712.py` (`88dd168b…`), `tests/test_porturi_712.py` (`68cb1efc…`).
- Fișiere noi permise: `tests/test_porturi_t7b.py`; `tests/baseline/ui_tu3_pre_t7b.py` și
  `tests/baseline/porturi_712_pre_t7b.py` (copii byte-identice ale `1128492b…`, `88dd168b…`, 0444);
  `tu3/rezultate/T7B/IDENTITATE_T7B_<UTC>Z.json` (0444); `tu3/inlocuiri/INLOCUIRE_T7B_<UTC>Z.json` (0444). Efecte
  laterale tolerate și declarate (comportament anterior): `jurnal/MATRICE_INIT_*.json` scrise de suitele existente,
  jurnalele lansatorului/matricei/aplicației la repornire, fișierele derivate ale aplicației, `tu3/__pycache__` scris de
  lansator.
- Byte-identice (`frozen_hashes`/`frozen_external` ale sigiliului): cele 111 + 5 ale T7A; artefactele T7A
  (`PROTOCOL_TU3_T7A.md`, `SIGILIU_TU3_T7A.json`, `tests/baseline/ui_tu3_pre_t7a.py`, `IDENTITATE_T7A_…`,
  `INLOCUIRE_T7A_…`); TOATE fișierele din `gl649/` și `se649/`. În particular NEMODIFICATE: `engine.py`, `parser.py`,
  `tu3/parser_multi.py`, `tu3/motor_n.py`, `tu3/motor_joker.py`, `run_app.sh`, `run_app_tu3.sh`, `porneste_aplicatia*.sh`,
  `tu3/arhiva_live.py`, `tu3/dedup_live.py`, `validare.py`, `app.py`, `tu3/inlocuiri_tu3.py`, `tu3/matrice_init.py`,
  `tu3/validare_tu3.py`, `tests/test_l649.py`; DL read-only; gardul prognozei neatins.

## 3. Aplicarea protocolului comun (P1–P8) în T7B
### 3.1 P1/P2
Porturile sunt funcții NOI în `tu3/porturi_712.py`, într-o secțiune „TU3-T7B” inserată înaintea gărzii
`if __name__ == "__main__"`; liniile existente (T7A) rămân neschimbate (numai inserții, verificat față de copia de
referință). `gl649`/`se649` nu se importă și nu se execută. Algoritmii se copiază literal; se schimbă numai constantele
49/6 în parametri (N, κ), cu formele generale de la §1.1–1.2, care dau EXACT aceleași fracții pentru (49, 6). Fără
tuning, fără grile, fără alegeri după date. Ieșirile nu conțin p̂, legi q, bilete, top-k, hits, log-score, Brier,
exces, porți, verdicte, p-valori sau ranguri față de nule.
### 3.2 P3 identitate (6/49, sursa înghețată `193eaf7a…`, pașii exact ca `load_real`)
- **GL:** `gl_describe` pe numărările pașilor `< K−1` (ultimul pas prezis de pistă, K = 2527) → `gamma_rel` =
  `float(γ̂_d)/float(p0)` față de `gl649/rezultate/backtest_unic/REZULTATE.json` `gamma_last_relative` (10 reale, bit cu
  bit); `ks[-1]` și `n_draws[-1]` din `PREDICTII.npz` (întregi, exact); `start.source_sha256`; sha `PREDICTII.npz` =
  `predictions_sha256`; controalele exacte `Σ p̂ = κ`, `1ᵀz = 0` la acel pas (booleene, `True`).
- **SE:** `se_describe` pe TOATE pașii → `n_per_season` (întregi, exact), `weights` 4 × 4 (= `float(w_φ)` pentru
  fiecare anotimp-țintă; 16 reale, bit cu bit) față de `REZULTATE.json` `final_state`; `G` față de
  `G_label_x_season`; `start.source_sha256`; sha `PREDICTII.npz` = `predictions_sha256`.
- Criteriile: P3 din T7A (EXACT; `IDENTITATE_NUMERICA` dacă |Δ| ≤ 1e-12·max(1, |x|); altfel FAIL ⇒ portul NU se
  afișează, sesiunea se oprește și se raportează). Nu se recalculează scoruri, porți, bilete sau verdicte.
### 3.3 P6 calcul (precizare declarată)
GL și SE sunt, în pistele originale, EXACTE în Q (`fractions.Fraction`) pentru γ̂/p̂/w, cu `float64` numai la
conversie și pentru statistica G (NumPy). Portul literal păstrează exact aceeași aritmetică (necesar pentru identitate,
cum cere P6): Fraction exact + NumPy float64, pe CPU. Clasic; fără afirmații GPU/cuantice.
### 3.4 P5/P7/P8
Setul LIVE al modului (același `get_game_dataset`, sha afișat; cache `st.cache_data` pe (mod, sha LIVE)); vederea 6/49
din `app.py` neschimbată. Joker: componenta principală (45, 5) și bila Joker (20, 1) ca serii separate. Porturile nu
scriu fișiere; excepție: CLI `--identitate t7b --out` scrie raportul în `tu3/rezultate/T7B/` (creare exclusivă, 0444).

## 4. Portul GL (tab 9)
- `gl_structure(N)`: `G` (N × 10), sumele pe coloane, `H = P G` (exact), `HᵀH` (exact); cache pe N.
- `gl_describe(counts, n, N, κ)`: literal `gl_predict_counts` cu `p0 = κ/N`, `s_g² = (p0/10)²`, `s_e² = (p0/20)²`,
  `σ0² = p0(1−p0)·N/(N−1)`, `ν = σ0²/n`; ieșiri: `gamma_rel` (γ̂_d / p0, d = 0..9), `glyph_labels` (numărul de etichete
  care conțin cifra d), `glyph_freq_rel` (frecvența observată a glifei d față de așteptarea uniformă:
  `(Gᵀc)_d / (κ n (Gᵀ1)_d / N) − 1`), `n_draws`, `N`, `kappa`, `sum_exact_ok`, `z_perp_ok`. p̂ și z NU se expun.
- UI 5/40 și Joker (pe TOATE extragerile setului LIVE; identitatea folosește pașii `< K−1`, ca pista): carduri
  (extrageri, n, κ, γ̂/p0 minim/maxim, controalele exacte) și graficele „efecte de glifă ajustate (γ̂/p0) pe cifră” și
  „frecvența observată a glifei față de uniform” (cifrele 0..9 în ordine naturală, fără sortare); la Joker, aceleași
  pentru bila Joker (2 + 2 grafice; 5/40: 2).

## 5. Portul SE (tab 10)
- `se_describe(steps, dates, N, κ)`: `season_of` literal pe datele pașilor; `season_prefix` literal (N); `n_per_season`;
  `weights[φ*][φ]` = `float(se_weights(n, φ*))` cu `p0 = κ/N`, `τa² = (p0/20)²`, `τb² = (p0/5)²`,
  `σ0² = p0(1−p0)·N/(N−1)`; `G` = `g_statistic` literal (`2 Σ c ln(c/(κ n_φ/N))`); `freq_rel_season[j][φ]` =
  `c_{jφ}/(n_φ p0) − 1` (descriptiv, etichetele în ordine naturală); controalele exacte `Σ_φ w_φ < 1` pentru fiecare φ*.
  FĂRĂ p̂, bilete, hits pe anotimpuri, rang/p-valoare a lui G.
- UI 5/40 și Joker: carduri (extrageri, n_φ pe cele 4 anotimpuri, G, controlul Σw < 1) și graficele „ponderile w_φ ale
  modelului (anotimp-țintă × anotimp observat)” și „frecvența relativă pe anotimp față de p0 (bilă × anotimp)”; la
  Joker, aceleași pentru bila Joker (2 + 2; 5/40: 2). G se afișează fără grade de libertate, fără p-valoare și fără
  comparație cu universuri nule.

## 6. `tu3/ui_tu3.py` — numai inserții (față de `tests/baseline/ui_tu3_pre_t7b.py`, deci și față de bazele T7A/L649)
1. În bucla taburilor 7–12, imediat după `continue`-ul T7A: o linie `if t7b_port(t_idx, tabs[t_idx], mode, ds, key,
   ctx):` + `continue` (portul T7B tratează taburile 9–10; altfel NEAPLICABIL ca acum).
2. La sfârșitul fișierului: secțiunea „TU3-T7B” (cache-urile pe (mod, sha LIVE), randarea GL/SE, linia de identitate
   din ultimul `IDENTITATE_T7B_*`). Orice excepție ⇒ `st.error` explicit în tab, fără comutare tăcută.
Niciun rând existent șters sau schimbat. Fiecare tab portat poartă „DESCRIPTIV”, „verdictul pistei 6/49 NU se
transferă”, „positive_claims_allowed=false”.

## 7. Teste
- `tests/test_app_tu3.py` — U3/U4: NUMAI `== 4` → `== 2` (comentariul actualizat). Restul neschimbat.
- `tests/test_porturi_712.py` — P8: taburile 7–10 „DESCRIPTIV”, fără „NEAPLICABIL”, 11–12 „NEAPLICABIL”; graficele
  taburilor 9–10 (5/40: 2 și 2; Joker: 4 și 4); P9: `== 2`; P10: lanțul din `from`-ul T7A ajunge la sha-ul curent.
  Restul neschimbat.
- `tests/test_porturi_t7b.py` (nou): B1 sigiliul înainte de cod (sha, `code_files_present: []`, `replaceable`, copiile
  de referință, 0444); B2 fișierele protejate byte-identice (inclusiv TOATE fișierele `gl649/`, `se649/`, niciun fișier
  nou acolo) + `porturi_712.py` nu importă `gl649`/`se649`/`bo649`/`wu649`/modelele; B3 identitatea GL și SE
  (subprocese); B4 certificat GL exact în Q: Woodbury = rezolvarea directă N × N `(PKP + νP + J) w = v` pentru
  (49, 6), (40, 6), (45, 5), (20, 1) pe numărări aleatoare, `Σ p̂ = κ`, `1ᵀz = 0`, și formele generale = constantele
  pistei pentru (49, 6); B5 certificat SE exact: formă închisă = rezolvarea directă, `Σ w < 1`, `Σ p̂ = κ`, constantele
  pentru (49, 6); B6 rulare generică pe 5/40 și Joker LIVE (forme, finite, controale, nicio cheie interzisă); B7 numai
  inserții: `ui_tu3.py` și `porturi_712.py` față de copiile `*_pre_t7b.py`, `test_app_tu3.py` cu `== 2`; B8 (după
  înregistrare) `INLOCUIRE_T7B_*` validă, lanțul pentru toate cele 4 fișiere, `inlocuiri_tu3 --verifica` ok.
- AppTest-ul taburilor (FAST) rămâne în P8 (o singură rulare pe mod).

## 8. Ordinea lucrului
1. Sigiliul (0444). 2. Copiile de referință (0444). 3. Codul (`porturi_712.py`, inserțiile `ui_tu3.py`), testele.
4. Teste + raportul de identitate (`--identitate t7b --out tu3/rezultate/T7B`). 5. Înregistrarea
`INLOCUIRE_T7B_<UTC>Z.json` (`--inregistreaza tu3/SIGILIU_TU3_T7B.json T7B`). 6. Suitele complete, matricea,
`--verifica`, dedup, DL. 7. Repornirea aplicației din pictogramă (buclă health ok); AppTest în configurația de PROTOCOL
pe 5/40 și Joker fără excepții.

## 9. Criterii de acceptare — verdict `T7B_PASS` (consemnat în predare)
- C1 suitele existente **33 passed, 3 skipped**; `test_lansator_tu3.py` + `test_l649.py` **16 passed**;
  `tests/test_porturi_712.py` (17) și `tests/test_porturi_t7b.py` toate trecute.
- C2 identitatea GL și SE: `IDENTITATE_EXACTA` sau `IDENTITATE_NUMERICA`, raport 0444.
- C3 0 drift pe fișierele protejate ale T7B (+ externe) și ale T7A; `inlocuiri_tu3 --verifica` → `"ok": true`;
  `dedup_live --verifica` OK; DL exit 0.
- C4 fișierele schimbate/noi = numai cele din §2 (+ efectele laterale declarate), verificat cu `find -newer` față de
  sigiliu.
- C5 aplicația repornită din pictogramă: matricea „TOATE 3 MODURILE READY”, health ok, numai 127.0.0.1; AppTest
  PROTOCOL pe 5/40 și Joker fără excepții, taburile 9–10 cu porturile.

## 10. Abateri și limite declarate dinainte
Porturile rulează pe CPU (Fraction exact + NumPy float64), nu pe GPU. Toleranța (1e-12) e cea din T7A. `--verifica` nu
acoperă sigiliile T7A/T7B (§1.4). GL pe 5/40/Joker și SE pe 5/40/Joker sunt primul contact al acestor modele cu
istoriile respective, strict descriptiv; nimic de aici nu califică sau promovează pistele (rămân închise pe 6/49).
Arhiva este deja explorată; porturile nu creează set „nevăzut” și nu evaluează nimic prospectiv. Sigilii locale, fără
atestare externă. Nicio afirmație de avantaj predictiv.

## 11. În afara domeniului
Taburile 11–12 (S6), scorul real 5/40/Joker (S7–S8), vederea 6/49, gardul prognozei, `inlocuiri_tu3.py`, orice rulare
a codului pistelor închise.
