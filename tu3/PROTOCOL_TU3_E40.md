# PROTOCOL TU3-E40 — modulul E40: motorul Loto 5/40 (n = 40, r = 6 la extragere, variante de exact 5)

Sesiunea 2026-10-26 (start ~16:35Z), continuare din checkpoint-ul 20261026T163435Z, la cererea utilizatorului (Mesajul 31).
Scris și sigilat ÎNAINTE de orice cod sau calcul al modulului (`tu3/motor_n.py`, `tu3/putere_e40.py` și
`tu3/tests/test_motor_n.py` nu există la sigilare). Subordonat `PROTOCOL_TU3_P1.md` (§0 abateri, §1 ordinea
modulelor) și `PROTOCOL_TU3_P.md` (surse); nu modifică nimic din modulele J și P.

## 0. Încadrare onestă

- Calcul CLASIC (PyTorch, CUDA pe RTX 5060 Laptop; fallback CPU jurnalizat). Vocabularul „non-hermitic”, „punct
  excepțional”, „Born”, „Kuramoto”, „QUBO” este strict matematic, aplicat unor tabele de co-apariție; niciun hardware
  cuantic, niciun avantaj cuantic. `positive_claims_allowed=false`.
- Produsul E40 este un motor DESCRIPTIV + generator de 3 variante de energie minimă de exact 5 numere din 1..40.
  Variantele NU sunt predicții și NU se compară cu nicio extragere. Orice scor pe istoria reală cere protocol separat,
  sigilat înainte (nu face parte din E40). Arhiva este deja explorată; nu există set „nevăzut”.
- `engine.py` (sha `1da9be4e…2ae`) și `parser.py` (sha `219e5d20…968`) rămân NEMODIFICATE; la fel `tu3/parser_multi.py`
  (`4c4b0f34…ef2a`). E40 nu atinge: colectorul/baza, protocolul prospectiv și gardul lui (decizia utilizatorului),
  OGLINDA, DL, modelele închise, `arhiva_live.py` (deduplicarea versiunilor rămâne submodul separat, la cerere).

## 1. Inventarul genericității în N al `engine.py` (citire de cod, înainte de orice cod nou)

`engine.py` fixează global `N = 49`, `K6 = 6`, `P2 = 30/2352`, `P3 = 120/110544`, `PAIR15`, baza de cod 50.
- **Generice (se IMPORTĂ nemodificate):** RNG-ul pe contor (`_s64`, `splitmix`, `stream`, `uniform`, `TAG_*`),
  `Config`/`PROTOCOL`/`step_seed`, `dissipation`, `_track`, `_hgam`, `op_nonhermitian` (n din formă; ψ inițial
  `1/√n`), `poincare_dist`, `_wrap`, `kuramoto_coupling`, `local_order`, `kuramoto_run`, `op_kuramoto` (40×40 din formă),
  `crowd_penalty` (operează pe orice lungime ≥ 3 a combinației), `FORBID_PENALTY`, `sha256_file`, `_vram`.
- **Dependente de N/K6 (se rescriu PARAMETRIZAT în `tu3/motor_n.py`, cu aceeași ordine a operațiilor):**
  `triples` (N, pozițiile C(6,3) → C(r,3)), `Prefix` (N), `pair_excess` (P2, N), `op_amplituhedron` (P3, N³),
  `op_poincare` (N), `born_state` (rezerva uniformă 1/N), `boltzmann_filter` (N, top-K6), `PAIR15`/`_PI`/`_PJ`,
  `energy`, `_code` (baza 50, K6), `mcmc_variant` (N, K6), `op_variants` (K6), `score_steps` (rezerva ψ 1/√N),
  `variants_steps`, `run_full` (sursa 6/49, `PREINREGISTRARE_QL649.md`).

## 2. Definiții E40 (fixate)

Forma jocului `Shape(n, r, k)`: n = mărimea urnei, r = numere pe extragere, k = numere pe variantă.
`SHAPE_649 = (49, 6, 6)` (martor de echivalență), `SHAPE_540 = (40, 6, 5)` (produsul E40).
1. Constante exacte: `P2 = r(r−1)/(n(n−1))` (5/40: 30/1560 = C(38,4)/C(40,6)), `P3 = r(r−1)(r−2)/(n(n−1)(n−2))`
   (5/40: 120/59280). La 6/49 se obțin exact valorile float din `engine.py`.
2. Starea cauzală `Prefix` pe `GameDataset` (câmpurile `draws`, `onehot`, `step_index`, `step_offsets`, `n_steps`):
   la pasul k numai extragerile din pașii < k. Triplete: toate C(n,3) (5/40: 9880), C(r,3) = 20 poziții pe extragere.
3. O1–O5 identice formal cu QL649 (aceleași formule și hiperparametri), cu N → n: H(γ) = A + iγD (40×40),
   ψ₀ = 1/√40, puncte excepționale prin grilă + Newton complex128; volume de politop pe 9880 triplete; disc Poincaré
   pe 40 de noduri; Kuramoto RK4 40×40; colaps Born + filtru Boltzmann pe 50 000 replici; fracția „core” = frecvența în
   top-k (k = 5) a replicilor (descriptiv).
4. O6 — anealer QUBO (paralel tempering Metropolis) pe combinații de EXACT k = 5 noduri distincte (mutare = schimbul
   unui membru cu un ne-membru, deci constrângerea „exact 5” e păstrată prin construcție). Energia:
   `E(S) = −Σ_{j∈S} ln π_j − λ Σ_{i<j∈S} A_ij + μ_crowd·crowd(S) + μ_ov·Σ_{j∈S} ov_j + 10⁶·[S ∈ variante anterioare]`,
   cu cele C(5,2) = 10 perechi; `crowd` = funcția QL649 aplicată celor 5 numere (max ≤ 31; trei consecutive;
   progresie aritmetică completă; ≥ 4 cu aceeași ultimă cifră). Cod lexicografic în baza n+1 (departajare la egalitate).
   3 variante secvențiale cu penalizarea de suprapunere și interdicția de identitate (AMENDAMENT_02 QL649).
5. Configurația protocolului E40: `PROTOCOL_540 = replace(engine.PROTOCOL, seed_master=540)` — TOȚI ceilalți
   hiperparametri sunt cei QL649-P1, preluați fără ajustare pentru 5/40. Sămânța pasului: `540·100003 + k`.
6. Intrarea produsului: `parser_multi.build_game_dataset("540", "live")`; orice protocol sigilat viitor folosește
   exportul înghețat (`"frozen"`). Ieșirea produsului (`run_full_540`) conține `positive_claims_allowed=False`, sursa,
   hash-ul sursei, digest-ul configurației, `is_protocol`, sha-ul acestui protocol și cele 3 variante de 5.

## 3. Martori (cod de test; trebuie să treacă exact)

- E1 echivalență: `motor_n` cu `SHAPE_649` = `engine.py` BIT CU BIT (`torch.equal`, același dispozitiv) pe un set
  sintetic 6/49, configurație redusă: `Prefix.state`, `pair_excess`, `op_amplituhedron`, `op_poincare`, `born_state`,
  `boltzmann_filter`, `score_steps` (π, A, P, ancore, core) și `variants_steps` (variante, energii).
- E2 forma 5/40 (sintetic): π în simplexul de dimensiune 40; A 40×40 simetrică, diagonală zero, normă spectrală 1;
  ψ după 0 pași de walk = 1/√40 exact; W Kuramoto 40×40 ≥ 0 cu suma maximă pe rând 1; 9880 triplete / 20 poziții;
  `top5_frac` cu suma 5; 3 variante distincte, sortate, de câte 5 numere distincte din 1..40, energii < 10⁵.
- E3 constante: P2, P3 egale cu rapoartele combinatoriale exacte (`math.comb`), iar la 6/49 egale cu cele din `engine.py`.
- E4 cauzalitate (set trunchiat la pașii < k ⇒ π identic la 1e-12, ancore identice) și invarianță la lot (1e-9).
- E5 echivarianță la permutarea etichetelor: A și amp permutate corespunzător (1e-12 / 1e-9).
- E6 QUBO exact-5: MCMC cu configurația protocolului = minimul exhaustiv pe toate C(40,5) = 658 008 combinații (GPU),
  aceeași combinație și energie la 1e-9; funcția de energie = formula explicită (buclă Python) pe combinații aleatoare.
- E7 Boltzmann exact: 8 noduri cu energie finită ⇒ C(8,5) = 56 de stări; 4096 de lanțuri la T = 1, χ² cu p > 0.001.
- E8 π concentrat pe 5 numere ⇒ varianta 1 = cele 5, 3 variante distincte, energii < 10⁵.
- E9 GPU = CPU (π la 2e-5); `final_state` vectorizat pe universuri = `Prefix.state(k = n_steps)` bit cu bit;
  universuri în lot = unul câte unul (π la 1e-9).
- E10 integritate: `engine.py`, `parser.py`, `parser_multi.py` și acest protocol au hash-urile sigilate.
- E11 (numai DUPĂ verdictul de putere `PASS` din §4, altfel `skip`): fumul produsului pe LIVE 5/40 —
  `run_full_540(build_game_dataset("540", "live"))` cu `PROTOCOL_540`: structură validă (E2), `is_protocol=True`,
  `source_kind="live"`, `positive_claims_allowed=False`. Variantele NU se tipăresc, NU se salvează, NU se compară.

## 4. Putere sintetică (γ = 1/2) — praguri fixate înainte de orice rulare; nicio rulare pe date reale înainte

Generator GPU (`torch.Generator("cuda")`, loturi de 128 de universuri, ordinea fixă): T = 2490 extrageri (lungimea
arhivei LIVE 5/40), o extragere pe pas. Per univers, o mulțime plantată H de 5 numere uniformă (argsort de uniforme).
Cu probabilitatea γ (Bernoulli independent pe extragere) extragerea = Gumbel-top-6 din logiții `β·[j ∈ H]`, β = 1;
altfel 6-submulțime uniformă (Gumbel-top-6 din logiți nuli). Motorul E40 complet (O1–O6, `PROTOCOL_540`) rulează la
pasul final k = T pe starea `final_state`; sămânța motorului pentru universul u din setul s: `540·10⁶ + s·10⁵ + u`.
Statistica: `S = Σ_{v=1..3} |V_v ∩ H|`. Valoare p EXACTĂ condiționată de variante: cu `m_j` = numărul de variante care
conțin j, `p = #{H' ⊂ [40], |H'| = 5 : Σ_{j∈H'} m_j ≥ S} / 658 008` (funcție generatoare exactă, întregi).
Sub nul (γ = 0), H este independentă de date, deci testul are mărimea ≤ 0.01 fără calibrare.
- Semințe ale generatorului: γ = 1/2 → 540002, γ = 1/8 → 540003, control γ = 0 → 540004 (s = 2, 3, 4).
- **G1 putere:** B1 = 512 universuri la γ = 1/2 → PASS dacă fracția cu p ≤ 0.01 este ≥ 0.90.
- **G2 control:** B2 = 512 universuri γ = 0 → PASS dacă rata fals-pozitivă (p ≤ 0.01) este ≤ 0.02.
- Descriptiv (fără prag): γ = 1/8, B = 256; media S, media |V_1 ∩ H|, rangul mediu al lui H în π.
Verdict: `E40_PASS` numai dacă E1–E10 trec și G1, G2 trec; altfel `E40_FAIL`, publicat ca atare, fără retuning
(β, γ, T, hiperparametri, statistica și pragurile nu se schimbă după rezultat; E11 nu rulează). Puterea pe sintetic
NU spune nimic despre arhiva reală și NU este un avantaj predictiv.

## 5. Artefacte

`tu3/motor_n.py`, `tu3/tests/test_motor_n.py`, `tu3/putere_e40.py`, `tu3/rezultate/E40/PUTERE_E40.json` (0444, fără
suprascriere, cu hash-urile codului și ale protocolului), apoi `predari/OPERATIV.md`, mesajele utilizatorului și
predarea QL649 (pereche nouă, același UTC, prin `predari/genereaza_predare.py`).
