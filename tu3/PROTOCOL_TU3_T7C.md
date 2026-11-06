# PROTOCOL TU3-T7C — porturile DESCRIPTIVE CS (tab 11) și PL (tab 12) (sesiunea S6)

Stare: scris și sigilat (`tu3/SIGILIU_TU3_T7C.json`) ÎNAINTE de orice cod și de orice calcul al acestei sesiuni
(`code_files_present: []`). Decizia utilizatorului: D3 = (b) — porturi DESCRIPTIVE, fără verdict și fără scor;
verdictele 6/49 NU se transferă (`tu3/DECIZII_PLAN_TU3_20261027.json` `b6a5ba05…`; plan `c7b4bfd3…`; cererea sesiunii S6
din 2026-10-27, Mesajul 47). Se aplică protocolul COMUN al porturilor `PROTOCOL_TU3_T7A.md` §3 (P1–P8, `f375bae9…`),
neschimbat, cu precizările declarate la §3.3 (P6). Mecanismul de schimbare a fișierelor înghețate: înlocuirea sigilată
`inlocuiri_tu3/v1` (PROTOCOL_TU3_L649 §4), neschimbat. Calcul clasic. Variantele produsului = minime de energie, NU
predicții. `positive_claims_allowed=false`.

## 1. Inventar read-only (făcut înainte de acest protocol)

### 1.1 CS649 (`cs649/cs649.py`, protocol CS649-P1, `CS_NO_PROMOTION_EXPLORATORY`, închis)
- Model: θ(k) = p0·1 + a + b³(k mod 3) + b⁵(k mod 5) + b⁷(k mod 7); așteptarea ajustată Bayes liniară prin ecuațiile
  Henderson 16 × 16, EXACT în Q (`fractions.Fraction`), float64 numai la conversie și pentru statistica G.
- Generice (depind de N/κ numai prin constantele modulului): `levels_of`, `zstar` (numai indicele pasului k),
  `solve_exact` (Bareiss), `solve_gauss_jordan`, `State` (`NN` 16 × 16, `C` 16 × N49), `state_from`, `henderson_M`
  (`SIGMA0_2`), `cs_predict_state` (`P0`, `N49`), `primal_predict`, `closed_form_balanced`, `g_statistics` (`6.0`, `N49`),
  `level_name`.
- Dependente de N = 49 / 6 bile sau de scor: `P0 = 6/49`, `TA2 = 9/240100`, `T2 = 9/9604`, `SIGMA0_2 = 43/392` (formele
  generale: `(p0/20)²`, `(p0/4)²`, `p0(1−p0)·N/(N−1)`); `ticket_exact`, `marginal_q`, `top6`, `comparators`,
  `score_block`, `hyper_pmf`, `exact_tail`, `gates`, `summarize`, `predict` (bilete), `score`, `cs_predict_float`,
  consistența cu BO649 (`1847/1821/2495`), `load_real`/`real_step_structure` (parserul 6/49), `synthetic_steps`,
  `onehot`, `constant_phase_history`/`fixture_F5`/`q5`/`q6` (etichete 1..49 fixe), `relabel`, `q1`–`q4`, `lam_K`/`lam_0`,
  `run_*`, `SENS`.
- **Decizia P4 pentru CS: PORT (aplicabil).** Motiv: structura modelului este faza indicelui pasului (zi distinctă de
  extragere, numerotată de la 0) modulo 3, 5, 7; ea nu depinde de etichete și nici de 49 — orice șir de zile de extragere
  o definește a priori. Setul LIVE al fiecărui mod are pași (zile) proprii (`step_offsets`). Premisa fizică a pistei
  (rotația operațională a seturilor de bile/urnelor) este la fel de NEVERIFICATĂ pe 5/40 și Joker ca pe 6/49. Ce NU se
  portează: p̂, biletele, scorurile, martorii Q5/Q6 (fixture-uri pe etichetele 1..49), sensibilitatea.
- Tabul 11 din `app.py` (6/49) afișează numai calificarea Q1–Q6, verdictul backtestului, porțile, verificarea
  independentă, hits CS/B/R și „hits CS − hits B pe faza-țintă” (toate = VERDICT/SCOR — EXCLUSE). Mărimile DESCRIPTIVE ale
  pistei sunt în `cs649/rezultate/backtest_unic/REZULTATE.json`: `final_state.n_per_level` (16 întregi),
  `final_state.v_for_next_index` (ponderile v = M⁻¹ z* ale celor 16 niveluri pentru indicele `next_index`),
  `next_phases`, `G_label_x_phase` (G3, G5, G7, G_sum). `final_step.rel_dev_*` derivă din p̂ ⇒ EXCLUS. Ponderile v exacte
  pe pași sunt în `PREDICTII_EXACTE.json.gz` (`v`, șiruri „num/den”).

### 1.2 PL649 (`pl649/pl649.py` + motorul `pl649/pl_core.py`, protocol PL649-P1, verdict 6/49 închis)
- Motorul: rețeaua de spin pe muchiile grafului complet al etichetelor; conexiunea SU(3) din impulsuri exp(iε λ_k)
  orientate după vechime (`LinkState.add_step`), spinii j = n/2 (n = co-extrageri), spectrul de arie √(j(j+1)), aria
  nodului, volumul-PROXY (S³)_aa/2, buclele Wilson ale tuturor triunghiurilor printr-o înmulțire M·M și curburile pe
  nod κ și pe muchie ε (`geometry`), `unitarity_error`. Original: PyTorch complex128/float64 pe CUDA
  (`START.json` `device: cuda`).
- Generice în (N, κ) prin constantele modulului: `gell_mann`, `kick_matrices`, `LinkState` (`N`, `NP`, `PID`, `P15` =
  perechile de poziții dintr-un bilet de 6), `geometry` (`N`, `PA`, `PB`), `unitarity_error`, `steps_to_tensor`,
  `spectral_layout`; în `pl649.py`: `idx_of`, `state_after`, `walk_forward` (partea κ), `_gm_np`, `_exp_closed` (forma
  închisă a exponențialelor, implementarea de referință CPU a Q1), `ref_links`, `ref_curvature`.
- Dependente de 49 / 6 sau de scor/bilete: `law`/`standardize` (legea π pentru extragerea următoare), `marginal_q`,
  `qubo_terms`, `Enumerator` (C(49,6) bilete), `variants`, `energy_of`, `predict_state` (bilet), `higgs_anneal`
  (bilete), `xy_monopoles` (zgomot `torch.Generator` + clasare de triunghiuri după persistență), `null_total_area`
  (universuri nule pe GPU), `top6`, `comparators`, `score*`, `gates`, `summarize`, `hyper_pmf`, `exact_tail`, `run_*`,
  `NFIX`/`q5`/`q6`, `load_real`.
- **Decizia P4 pentru PL: PORT pentru componentele cu κ ≥ 2 (5/40: n = 40, κ = 5; Joker principal: n = 45, κ = 5);
  NEAPLICABIL pentru bila Joker (n = 20, κ = 1).** Motiv: rețeaua de spin e definită a priori pe perechile de etichete
  co-extrase în aceeași extragere; pentru orice N cu κ ≥ 2 graful complet și impulsurile SU(3) sunt definite (constantele
  ε = π/32 nu depind de N). Pentru κ = 1 nicio pereche nu este co-extrasă niciodată: n ≡ 0, U ≡ I, nicio muchie nu are
  spin, κ ≡ 0 trivial — portul nu are obiect; se scrie motivul. Premisa pistei (inspirație LQG/Yang–Mills, metaforică)
  este la fel de nefizică pe orice joc.
- Ce NU se portează (P2 și P3): legea π și z (probabilitate pentru extragerea următoare), biletul QUBO și cele 3 variante
  (bilete), enumerarea, anealerul Higgs (bilete + zgomot CUDA), monopolii XY (zgomot `torch.Generator` pe CUDA,
  nereproductibil pe CPU ⇒ identitate imposibilă, și clasare de triunghiuri), aria față de universurile nule
  (`planck_area_z`/`deviancy` = comparație cu uniformul + zgomot CUDA), dispunerea spectrală 3D (vectori proprii ai unor
  valori proprii posibil apropiate ⇒ fără identitate fiabilă între dispozitive; nu e necesară), telemetria VRAM.
- Tabul 12 din `app.py` (6/49) importă `pl649/ui_pl649.py` (înghețat în UI, L649, T7A, T7B — NU se atinge) care afișează:
  calificarea, verdictul, porțile, verificarea, butonul GPU, telemetria (aria totală vs nul, eroarea de holonomie,
  anealerul, monopolii), cele 3 variante, spuma de spin 3D, traiectoria anealerului, hits și nulele (= VERDICT/SCOR/
  BILETE/NUL — EXCLUSE). DESCRIPTIVE în artefacte: `rezultate/final/FINAL.json` — `node.kappa`, `node.A`, `node.V`,
  `area_spectrum`, `telemetry.planck_area_total`, `telemetry.holonomy_error`, `top_edges` (ε și j pe muchii), `frames`
  (ultimii 24 de pași: κ, A, V_total), `n_draws`, `n_steps`; `rezultate/backtest_unic/PREDICTII.npz` — `ks`, `kappa`
  (κ pe nod la fiecare pas al mersului înainte, 2427 × 49); `REZULTATE.json` — `final_unitarity`, `predictions_sha256`.

### 1.3 Sigiliile care conțin fișierele atinse
- `tu3/ui_tu3.py`: înghețat în VS, DD, LN; `replaceable` în L649, T7A, T7B; curent `c5a94a44…` prin `INLOCUIRE_T7B_…`.
- `tests/test_app_tu3.py`: înghețat în VS, DD, LN; `replaceable` în L649, T7A, T7B; curent `28156da4…`.
- `tu3/porturi_712.py` (`3dea1aaa…`), `tests/test_porturi_712.py` (`2c83417a…`): `replaceable` în T7B; curente prin
  `INLOCUIRE_T7B_…`. `tests/test_porturi_t7b.py` (`7e85184d…`): creat în T7B (`new_files_planned`), în niciun
  `frozen_hashes`/`replaceable`.
- `cs649/` (28 de fișiere): în niciun sigiliu TU3. `pl649/` (31 de fișiere): numai `pl649/ui_pl649.py` (`72f3843c…`) e în
  sigiliile UI, L649, T7A, T7B (`frozen_hashes`) — rămâne byte-identic (portul nu îl folosește). Ambele directoare au
  sigiliile/manifestele proprii (rămân byte-identice).

### 1.4 Cititorii fișierelor atinse
- `tests/test_app_tu3.py` U3/U4: `sum("NEAPLICABIL" in i.value for i in at.info) == 2` ⇒ se amendează NUMAI `2 → 0`
  (toate taburile 7–12 devin porturi DESCRIPTIVE; bila Joker din tabul 12 nu folosește `st.info` „NEAPLICABIL”, ci o
  explicație în text).
- `tests/test_porturi_712.py`: P8 cere NEAPLICABIL în taburile 11–12 ⇒ se amendează (7–12 DESCRIPTIV; numărul de grafice
  pentru 11–12; cuvintele interzise pe toate cele 6 taburi); P9 cere `== 2` în `test_app_tu3.py` ⇒ `== 0`. P1–P7 și P10
  neschimbate (P2 rămâne valabil: T7C nu atinge `frozen_hashes` ale T7A și nu importă `torch`; P10 urmează deja lanțul).
- `tests/test_porturi_t7b.py`: B7 cere `== 2` ⇒ `== 0`; B8 cere `to` = sha-ul curent ⇒ „lanțul pornit din `from`-ul
  T7B ajunge la sha-ul curent”. B1–B6, B9 neschimbate (B2 rămâne valabil: fără `torch`, `gl649/`, `se649/`, `bo649/`,
  `wu649/` neatinse).
- `tests/test_l649.py` L3: `ui_tu3.py` numai inserții față de `ui_tu3_pre_l649.py` (rămâne adevărat). `test_validare_tu3.py`
  T4/T5b (`FAST_OVERRIDES` neschimbat), `matrice_init`/`validare_tu3` (integritatea prin `inlocuiri_tu3.resolve`, lanțul
  VS → L649 → T7A → T7B → T7C) — NEMODIFICATE.
- `inlocuiri_tu3.py`: `OLD_SEALS` = VS/DD/LN/L649 — `--verifica` nu include sigiliile T7A/T7B/T7C; protecția lor e dată de
  P2 (T7A), B2 (T7B), C2 (T7C) și de `plan_record`. Limită declarată; `inlocuiri_tu3.py` rămâne NEMODIFICAT.

### 1.5 Concluzie
Soluția încape în fișierele permise de cererea S6: `tu3/porturi_712.py` (numai inserții), `tu3/ui_tu3.py` (numai
inserții), `tests/test_app_tu3.py` (U3/U4: 2 → 0), `tests/test_porturi_712.py` (P8/P9), `tests/test_porturi_t7b.py`
(B7/B8), test nou `tests/test_porturi_t7c.py`, copiile de referință (0444) și artefactele de proces. Nu e nevoie de alte
fișiere ⇒ fără întrebare către utilizator.

## 2. Domeniu (închis)
- Se pot schimba numai fișierele din `replaceable`: `tu3/ui_tu3.py` (`c5a94a44…`), `tests/test_app_tu3.py`
  (`28156da4…`), `tu3/porturi_712.py` (`3dea1aaa…`), `tests/test_porturi_712.py` (`2c83417a…`),
  `tests/test_porturi_t7b.py` (`7e85184d…`).
- Fișiere noi permise: `tests/test_porturi_t7c.py`; `tests/baseline/ui_tu3_pre_t7c.py` și
  `tests/baseline/porturi_712_pre_t7c.py` (copii byte-identice ale `c5a94a44…`, `3dea1aaa…`, 0444);
  `tu3/rezultate/T7C/IDENTITATE_T7C_<UTC>Z.json` (0444); `tu3/inlocuiri/INLOCUIRE_T7C_<UTC>Z.json` (0444). Efecte
  laterale tolerate și declarate (comportament anterior): `jurnal/MATRICE_INIT_*.json` scrise de suitele existente,
  jurnalele lansatorului/matricei/aplicației la repornire, `jurnal/app.pgid`, fișierele derivate ale aplicației,
  `tu3/__pycache__` scris de lansator.
- Byte-identice (`frozen_hashes`/`frozen_external` ale sigiliului): cele 170 + 5 ale T7B; artefactele T7B
  (`PROTOCOL_TU3_T7B.md`, `SIGILIU_TU3_T7B.json`, `tests/baseline/ui_tu3_pre_t7b.py`,
  `tests/baseline/porturi_712_pre_t7b.py`, `IDENTITATE_T7B_…`, `INLOCUIRE_T7B_…`); TOATE fișierele din `cs649/` și
  `pl649/`. În particular NEMODIFICATE: `engine.py`, `parser.py`, `tu3/parser_multi.py`, `tu3/motor_n.py`,
  `tu3/motor_joker.py`, `run_app.sh`, `run_app_tu3.sh`, `porneste_aplicatia*.sh`, `tu3/arhiva_live.py`,
  `tu3/dedup_live.py`, `validare.py`, `app.py`, `tu3/inlocuiri_tu3.py`, `tu3/matrice_init.py`, `tu3/validare_tu3.py`,
  `tests/test_l649.py`, `pl649/ui_pl649.py`, `gl649/`, `se649/`, `bo649/`, `wu649/`; DL read-only; gardul prognozei neatins.

## 3. Aplicarea protocolului comun (P1–P8) în T7C
### 3.1 P1/P2
Porturile sunt funcții NOI în `tu3/porturi_712.py`, într-o secțiune „TU3-T7C” inserată înaintea gărzii
`if __name__ == "__main__"` + ramurile CLI `cs`/`pl`/`t7c` în `main` + docstring; liniile existente rămân neschimbate
(numai inserții, verificat față de copia de referință). `cs649`/`pl649` nu se importă și nu se execută; `torch` nu se
importă (P2 al T7A/B2 al T7B rămân valabile: importuri ⊆ stdlib ∪ {numpy, parser}). Algoritmii se copiază literal; se
schimbă numai constantele 49/6 în parametri (N, κ), cu formele generale de la §1.1–1.2, care dau EXACT aceleași valori
pentru (49, 6). Fără tuning, fără grile, fără alegeri după date. Ieșirile nu conțin p̂, legi π/q, z, bilete, variante,
energii QUBO, top-k, hits, log-score, Brier, exces, porți, verdicte, p-valori, comparații cu universuri nule sau clasări.
### 3.2 P3 identitate (6/49, sursa înghețată `193eaf7a…`, pașii exact ca `load_real`: `parser.build_dataset(device="cpu")`)
- **CS:** `cs_describe` pe TOȚI pașii → `n_per_level` (16 întregi, EXACT), `v_next` (16 reale = `float(v_ℓ)`, bit cu bit)
  față de `final_state.v_for_next_index`, `next_index`/`next_phases` (EXACT), `G3`, `G5`, `G7`, `G_sum` față de
  `G_label_x_phase`; ponderile v EXACTE în Q (șirurile „num/den”) la pașii k = 100 + 97 i (i = 0..25) și k = K − 1, din
  starea pașilor < k, față de `PREDICTII_EXACTE.json.gz` `v` (egalitate de șiruri ⇒ EXACT); `start.source_sha256`;
  sha `PREDICTII.npz` = `predictions_sha256`, sha gz = `exact_predictions_sha256`; hiperparametrii (49, 6) =
  `start.config`; controlul exact Σ p̂ = κ la indicele următor (boolean `True`; p̂ intern, neexpus).
- **PL:** `pl_describe` pe TOȚI pașii (starea finală) → `curvature_node`, `area_node`, `volume_node` față de `FINAL.json`
  `node.kappa`/`node.A`/`node.V`; `area_spectrum` (EXACT); `area_total` față de `telemetry.planck_area_total`;
  `holonomy` față de `telemetry.holonomy_error` și `REZULTATE.json` `final_unitarity` (fracția EXACTĂ, maximele
  numeric); ε pe muchiile `top_edges` (căutate după perechea (a, b) din referință, nu după clasare) și j (EXACT);
  `frames` — pașii (EXACT), κ, A, V_total la ultimii 24 de pași; mersul înainte: κ pe nod la fiecare pas k ∈ `ks`
  (starea pașilor < k) față de `PREDICTII.npz` `kappa` și `ks` (EXACT); `n_draws`, `n_steps` (EXACT); sursa (`FINAL.json`
  `meta.source_sha256` și `START.json`); sha `PREDICTII.npz` = `predictions_sha256`.
- Criteriile: P3 din T7A (EXACT; `IDENTITATE_NUMERICA` dacă |Δ| ≤ 1e-12·max(1, |x|) pe fiecare valoare; altfel FAIL ⇒
  portul NU se afișează, sesiunea se oprește și se raportează). Nu se recalculează scoruri, porți, bilete, variante sau
  verdicte.
### 3.3 P6 calcul (precizări declarate dinainte)
- CS: pista originală e EXACTĂ în Q (`fractions.Fraction`, Bareiss) cu float64 la conversie și NumPy float64 pentru G;
  portul literal păstrează exact aceeași aritmetică (necesar pentru identitate), pe CPU ⇒ `IDENTITATE_EXACTA` așteptată.
- PL: pista originală a rulat motorul în PyTorch complex128/float64 pe CUDA, cu impulsurile `torch.linalg.matrix_exp`.
  Portul rulează pe CPU în NumPy complex128/float64 (același tip aritmetic; `torch` nu se importă — cerința P2/B2), cu
  algoritmul motorului copiat literal (actualizarea vectorizată pe perechile unei extrageri, `geometry` prin M·M) și cu
  impulsurile în forma închisă exactă a pistei (`pl649._exp_closed`, implementarea de referință CPU din Q1: pentru
  λ₁..λ₇, λ³ = λ ⇒ exp(iελ) = I + i sin ε λ + (cos ε − 1) λ²; λ₈ diagonal). Rotunjirile diferă de GPU la nivelul
  ~1e-16 pe operație ⇒ se așteaptă `IDENTITATE_NUMERICA` (acceptată de P3); nicio ramificare a stării nu depinde de
  valori reale (generatorul = n mod 8 întreg; vechimile întregi), deci diferențele nu se pot amplifica discontinuu.
  Clasic; fără afirmații GPU/cuantice.
### 3.4 P5/P7/P8
Setul LIVE al modului (același `get_game_dataset`, sha afișat; cache `st.cache_data` pe (mod, sha LIVE)); vederea 6/49
din `app.py` neschimbată (tabul 12 din 6/49 rămâne `ui_pl649`). Joker: componenta principală (45, 5) și bila Joker
(20, 1) ca serii separate; PL: bila Joker NEAPLICABIL (§1.2), explicat în text. Porturile nu scriu fișiere; excepție:
CLI `--identitate t7c --out` scrie raportul în `tu3/rezultate/T7C/` (creare exclusivă, 0444).

## 4. Portul CS (tab 11)
- `cs_constants(N, κ)`: `p0 = κ/N`, `τa² = (p0/20)²`, `τ² = (p0/4)²`, `σ0² = p0(1−p0)·N/(N−1)` (pentru (49, 6):
  9/240100, 9/9604, 43/392).
- `cs_state(steps, N, upto)`: literal `State`/`add_step` (NN 16 × 16, C 16 × N, întregi), pașii < upto.
- `cs_v(state, k*, N, κ)`: literal `henderson_M` + `cs_predict_state` (Bareiss) ⇒ v (16 fracții) și, INTERN, Σ p̂.
- `cs_g(state, N, κ)`: literal `g_statistics` (`G_K = 2 Σ c ln(c / (κ n_{Kr}/N))`). Fără p-valoare.
- `cs_describe(steps, N, κ)`: `n_steps`, `n_draws`, `n_per_level` (nume `a`, `K3r0`, …, `K7r6`), `next_index` = K,
  `next_phases`, `v_next` (16 reale), `v_next_exact` (șiruri), `G3`, `G5`, `G7`, `G_sum`, `freq_rel_phase[ℓ][j]` =
  `c_{ℓj}/(n_ℓ p0) − 1` pentru cele 15 niveluri de fază (etichetele în ordine naturală), `sum_exact_ok`, `hyper`.
- UI 5/40 și Joker: carduri (extrageri, pași, G3 · G5 · G7, controlul exact Σ p̂ = κ în Q) și graficele „ponderile v ale
  celor 16 niveluri pentru indicele K (fazele …)” și „frecvența relativă pe fază față de p0 (nivel de fază × bilă)”; la
  Joker, aceleași pentru bila Joker (2 + 2 grafice; 5/40: 2).

## 5. Portul PL (tab 12)
- `pl_structure(N, κ)`: `NP`, `PA`, `PB`, `PID`, perechile de poziții dintr-o extragere de κ (`P15` pentru κ = 6).
- `pl_kicks()`: literal `_gm_np` + `_exp_closed` (k = 0..7) și conjugatele.
- `pl_state(steps, N, κ, upto, frames)`: literal `LinkState.add_step` pentru un univers (vechimile din pașii strict
  anteriori; pentru fiecare extragere, perechile ordonate, `gen = n mod 8`, `U ← E U` dacă a e mai vechi, `U ← U E†` dacă
  b e mai vechi, altfel neschimbat; `n += 1`; apoi `last`); opțional geometria la ultimii `frames` pași.
- `pl_geometry(U, n, N)`: literal `geometry` (S, M bloc 3N × 3N, M², T = tr(M_ab (M²)_ba), ε, κ, A, V) în NumPy.
- `pl_unitarity(U)`: literal `unitarity_error`.
- `pl_describe(steps, N, κ)`: dacă κ < 2 ⇒ `{"applicable": False, "reason": …}`; altfel `curvature_node` (N),
  `area_node`, `volume_node`, `eps_edge` (NP, ordinea canonică a perechilor a < b), `area_spectrum`, `area_total`,
  `volume_total`, `links_spun`, `holonomy`, `curvature_min`/`max`, `n_draws`, `n_steps`.
- `pl_kappa_walk(steps, N, κ, warmup = 100)`: κ pe nod la fiecare k ≥ 100 din starea pașilor < k (numai identitate).
- UI 5/40 și Joker (componenta principală): carduri (extrageri, muchii cu spin / total, aria totală Σ√(j(j+1)),
  κ minim–maxim, eroarea de holonomie) și graficele „curbura κ pe nod (ordine naturală)”, „curbura ε pe muchie (N × N,
  ordine naturală)”, „spectrul de arie (muchii pe spin j = n/2)” (3 grafice, ambele moduri); la Joker, textul explică de
  ce rețeaua nu se aplică bilei Joker (κ = 1).

## 6. `tu3/ui_tu3.py` — numai inserții (față de `tests/baseline/ui_tu3_pre_t7c.py`, deci și față de bazele T7B/T7A/L649)
1. În bucla taburilor 7–12, imediat după `continue`-ul T7B: o linie `if t7c_port(t_idx, tabs[t_idx], mode, ds, key,
   ctx):` + `continue` (portul T7C tratează taburile 11–12).
2. La sfârșitul fișierului: secțiunea „TU3-T7C” (cache-urile pe (mod, sha LIVE), randarea CS/PL, linia de identitate din
   ultimul `IDENTITATE_T7C_*`). Orice excepție ⇒ `st.error` explicit în tab, fără comutare tăcută.
Niciun rând existent șters sau schimbat. Fiecare tab portat poartă „DESCRIPTIV”, „verdictul pistei 6/49 NU se
transferă”, „positive_claims_allowed=false”.

## 7. Teste
- `tests/test_app_tu3.py` — U3/U4: NUMAI `== 2` → `== 0` (comentariul actualizat). Restul neschimbat.
- `tests/test_porturi_712.py` — P8: taburile 7–12 „DESCRIPTIV”, fără „NEAPLICABIL”, fără erori; graficele taburilor 11–12
  (5/40: 2 și 3; Joker: 4 și 3); cuvintele interzise verificate pe toate cele 6 taburi; P9: `== 0`. Restul neschimbat.
- `tests/test_porturi_t7b.py` — B7: `== 0`; B8: lanțul pornit din `from`-ul T7B ajunge la sha-ul curent. Restul
  neschimbat.
- `tests/test_porturi_t7c.py` (nou): C1 sigiliul înainte de cod (sha, `code_files_present: []`, `replaceable` = cele 5,
  copiile de referință, 0444, sigilat după T7B); C2 fișierele protejate byte-identice (inclusiv TOATE fișierele `cs649/`,
  `pl649/`, niciun fișier nou acolo și în `gl649/`, `se649/`, `bo649/`, `wu649/`) + importurile `porturi_712.py`
  (fără `cs649`/`pl649`/`pl_core`/`torch`/modele; ⊆ stdlib ∪ {numpy, parser}); C3 identitatea CS și PL (subprocese);
  C4 certificat CS exact în Q: constantele = ale pistei pentru (49, 6); Henderson (Bareiss) = Gauss–Jordan = forma primală
  N_d × N_d (rescrisă în test după `cs649.primal_predict`) pentru (49, 6), (40, 5), (45, 5), (20, 1) pe istorii aleatoare
  mici, Σ p̂ = κ; C5 certificat PL: impulsurile în formă închisă = seria exponențială (în test) la 1e-14 și unitare;
  κ și ε prin M·M = referința triunghi cu triunghi (rescrisă în test după `pl649.ref_links`/`ref_curvature`) pentru
  (N, κ) ∈ {(9, 3), (12, 5), (8, 2)} la 1e-12; κ = 1 ⇒ `applicable` fals; C6 rulare generică pe 5/40 și Joker LIVE
  (forme, finite, controale, nicio cheie interzisă); C7 numai inserții: `ui_tu3.py` și `porturi_712.py` față de copiile
  `*_pre_t7c.py`, `test_app_tu3.py` cu `== 0`; C8 (după înregistrare) `INLOCUIRE_T7C_*` validă, lanțul pentru toate cele
  5 fișiere, `inlocuiri_tu3 --verifica` ok; C9 raportul de identitate (0444, PASS).
- AppTest-ul taburilor (FAST) rămâne în P8 (o singură rulare pe mod).

## 8. Ordinea lucrului
1. Sigiliul (0444). 2. Copiile de referință (0444). 3. Codul (`porturi_712.py`, inserțiile `ui_tu3.py`), testele.
4. Teste + raportul de identitate (`--identitate t7c --out tu3/rezultate/T7C`). 5. Înregistrarea
`INLOCUIRE_T7C_<UTC>Z.json` (`--inregistreaza tu3/SIGILIU_TU3_T7C.json T7C`). 6. Suitele complete, matricea,
`--verifica`, dedup, DL. 7. Repornirea aplicației din pictogramă (buclă pe linia `[lansator] health ok` din jurnalul
NOU); AppTest în configurația de PROTOCOL pe 5/40 și Joker fără excepții.

## 9. Criterii de acceptare — verdict `T7C_PASS` (consemnat în predare)
- C1 suitele existente **33 passed, 3 skipped**; `test_lansator_tu3.py` + `test_l649.py` **16 passed**;
  `tests/test_porturi_712.py` (17), `tests/test_porturi_t7b.py` (20) și `tests/test_porturi_t7c.py` toate trecute.
- C2 identitatea CS și PL: `IDENTITATE_EXACTA` sau `IDENTITATE_NUMERICA`, raport 0444.
- C3 0 drift pe fișierele protejate ale T7C (+ externe), ale T7B și ale T7A; `inlocuiri_tu3 --verifica` → `"ok": true`;
  `dedup_live --verifica` OK; DL exit 0.
- C4 fișierele schimbate/noi = numai cele din §2 (+ efectele laterale declarate), verificat cu `find -newer` față de
  sigiliu.
- C5 aplicația repornită din pictogramă: matricea „TOATE 3 MODURILE READY”, health ok, numai 127.0.0.1; AppTest PROTOCOL
  pe 5/40 și Joker fără excepții, taburile 11–12 cu porturile.

## 10. Abateri și limite declarate dinainte
CS pe CPU, exact în Q + NumPy float64 (identic pistei). PL pe CPU în NumPy complex128 în loc de PyTorch CUDA (§3.3),
impulsurile în forma închisă a pistei; identitate numerică așteptată. Toleranța (1e-12) e cea din T7A. `--verifica` nu
acoperă sigiliile T7A/T7B/T7C (§1.4). CS și PL pe 5/40/Joker sunt primul contact al acestor modele cu istoriile
respective, strict descriptiv; nimic de aici nu califică sau promovează pistele (rămân închise pe 6/49). Variantele
energetice ale PL (bilete) NU se calculează în porturi. Arhiva este deja explorată; porturile nu creează set „nevăzut”
și nu evaluează nimic prospectiv. Sigilii locale, fără atestare externă. Nicio afirmație de avantaj predictiv.

## 11. În afara domeniului
Scorul real 5/40/Joker (S7–S8), vederea 6/49 (inclusiv `pl649/ui_pl649.py`), gardul prognozei, `inlocuiri_tu3.py`,
orice rulare a codului pistelor închise, GPU.
