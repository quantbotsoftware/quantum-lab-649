# PROTOCOL TU3-EJ — modulul E-J: integrarea Joker în motorul polimorf (n = 45, r = 5, variante 5+1)

Sesiunea 2026-10-26 (start ~17:06Z), continuare din checkpoint-ul 20261026T170155Z, la cererea utilizatorului (Mesajul 32).
Scris și sigilat ÎNAINTE de orice cod sau calcul al modulului (`tu3/motor_joker.py`, `tu3/putere_ej.py`,
`tu3/tests/test_motor_joker.py` și `tu3/rezultate/EJ/` nu există la sigilare). Subordonat `PROTOCOL_TU3_P1.md`
(§0 abateri, §1 ordinea modulelor, §2 definițiile J), `PROTOCOL_TU3_P.md` (surse) și `PROTOCOL_TU3_E40.md` (motorul
polimorf); nu modifică nimic din modulele J, P și E40.

## 0. Încadrare onestă

- Calcul CLASIC (PyTorch, CUDA pe RTX 5060 Laptop; fallback CPU jurnalizat). „Distribuție condiționată”, „holonomie”,
  „tensor comun”, „Born”, „QUBO” sunt vocabular matematic aplicat unor tabele de co-apariție; niciun hardware cuantic,
  niciun avantaj cuantic. `positive_claims_allowed=false`.
- Produsul E-J este un motor DESCRIPTIV + generator de 3 variante Joker 5+1 de energie minimă (5 numere distincte din
  1..45 + 1 Joker din 1..20). Variantele NU sunt predicții și NU se compară cu nicio extragere. Orice scor pe istoria
  reală cere protocol separat, sigilat înainte (nu face parte din E-J). Arhiva este deja explorată; nu există set „nevăzut”.
- NEMODIFICATE (hash-uri în sigiliu): `engine.py` (`1da9be4e…2ae`), `parser.py` (`219e5d20…968`),
  `tu3/parser_multi.py` (`4c4b0f34…ef2a`), `tu3/motor_n.py` (`28e8eede…dd17`; nu se schimbă retroactiv fără amendament),
  `tu3/joker_entanglement.py` (`52feb5b5…933e`). E-J nu atinge: colectorul/baza, protocolul prospectiv și gardul lui
  (decizia utilizatorului), OGLINDA, DL, modelele închise, `arhiva_live.py` (deduplicarea rămâne submodul separat, la cerere).
- E-J se implementează ADITIV într-un modul nou `tu3/motor_joker.py`, care IMPORTĂ `motor_n` și `joker_entanglement`.

## 1. Inventar (citire de cod, înainte de orice cod nou)

- `motor_n.Shape`, `Prefix`, `final_state`, `pair_excess`, `op_amplituhedron`, `op_poincare`, `born_state`,
  `boltzmann_filter`, `energy`, `mcmc_variant`, `op_variants`, `score_steps`, `score_states`, `variants_steps`, `run_full`
  sunt generice în (n, r, k) și se folosesc NEMODIFICATE cu forma nouă. Excepții declarate: `motor_n.protocol_config`
  întoarce `PROTOCOL_540` pentru orice formă ≠ 6/49, iar `motor_n.run_full` scrie `is_protocol = (cfg ==
  protocol_config(shape))` și `protocol_sha256` = sha-ul `PROTOCOL_TU3_E40.md`. Pentru Joker, E-J transmite EXPLICIT
  `PROTOCOL_JOKER` și SUPRASCRIE în ieșirea produsului numai aceste două câmpuri de metadate (`is_protocol = (cfg ==
  PROTOCOL_JOKER)`, `protocol_sha256` = sha-ul acestui protocol). Niciun alt câmp al `run_full` nu se modifică.
- `joker_entanglement.joint_counts`, `joint_tensor`, `cross_covariance`, `schmidt`, `mutual_information`, `holonomy`,
  `joker_phases` se folosesc nemodificate (tensorul comun J și holonomia).
- `parser_multi.GameDataset` pentru Joker: `draws` [T,5], `onehot` [T,45] (float32), `joker` [T], `joker_onehot` [T,20]
  (float32), `cross_counts = onehot.T @ joker_onehot` [45,20] (float32) = tensorul comun J ne-normalizat.

## 2. Definiții E-J (fixate)

1. Forma: `SHAPE_JOKER = Shape("joker", 45, 5, 5)`: `P2 = 20/1980 = C(43,3)/C(45,5)`, `P3 = 60/85140 =
   C(42,2)/C(45,5)`; C(45,3) = 14 190 triplete, C(5,3) = 10 poziții pe extragere, C(5,2) = 10 perechi în QUBO; cod
   lexicografic în baza 46. `PROTOCOL_JOKER = replace(engine.PROTOCOL, seed_master=4520)` (TOȚI ceilalți hiperparametri
   QL649-P1, neajustați); sămânța pasului `4520·100003 + k`.
2. Partea principală (5 din 45): motorul polimorf O1–O6 al `motor_n`, neschimbat, pe `GameDataset` Joker (Joker-ul NU
   intră în O1–O6). Rezultă π (45), A (45×45) și 3 variante principale V_1, V_2, V_3 distincte de câte 5 numere
   (O6 cu penalizarea de suprapunere și interdicția de identitate AMENDAMENT_02), energiile E_main(V_v).
3. Tensorul comun la pasul k (cauzal): `N^{(k)}_{ja} = Σ_{t: pas(t) < k} X_tj Y_ta` (numărări întregi), calculat ca
   `onehot[:o_k].T @ joker_onehot[:o_k]` (float32, aceeași operație ca `parser_multi`), `o_k = step_offsets[k]`. La
   k = n_steps: `N^{(k)} = GameDataset.cross_counts` bit cu bit și = `joker_entanglement.joint_counts` (bincount).
4. Distribuția condiționată a Joker-ului dată varianta V (|V| = 5):
   `q_V(a) = Σ_{j∈V} N_{ja} / Σ_{j∈V} Σ_b N_{jb}` (= `Σ_{j∈V} P_ja / Σ_{j∈V} p_j` cu P = N/ΣN), iar dacă numitorul
   este 0, `q_V(a) = 1/20`. Holonomia variantei: `h_V = Σ_a q_V(a) e^{iφ_a}`, `φ_a = 2π(a−1)/20`; identitate:
   `h_V = Σ_{j∈V} p_j h_j / Σ_{j∈V} p_j` (h_j = holonomia nodală J, P1 §2.4). |h_V| și arg h_V sunt descriptive.
5. Energia Joker (exact 1 din 20, enumerare exhaustivă): pentru varianta v,
   `E_J(a | V_v) = −ln max(q_{V_v}(a), 1e-300) + μ_ov·ovJ_v(a)`, `μ_ov = mu_overlap = 1.0` (QL649), `ovJ_v(a)` = numărul
   variantelor anterioare (1..v−1) cu Joker a. `a*_v` = cel mai mic a care minimizează E_J (departajare la egalitate
   exactă după indice). Variantele 5+1 sunt `(V_v, a*_v)`, v = 1..3, secvențial; ele sunt distincte deoarece V_v sunt
   distincte (nu e nevoie de interdicție suplimentară). Energia totală `E_v = E_main(V_v) + E_J(a*_v | V_v)`.
   Minimizarea este în DOUĂ ETAPE (lexicografică: întâi V prin O6, apoi a dat V), NU minimul comun pe (V, a); declarat.
6. Descriptori J ai produsului (din `joker_entanglement`, nemodificat): S_E, K_S, I, Φ ale tensorului N^{(k)}.
7. Intrarea produsului: `parser_multi.build_game_dataset("joker", "live")`; orice protocol sigilat viitor folosește
   exportul înghețat (`"frozen"`). Ieșirea produsului (`run_full_joker`) conține `positive_claims_allowed=False`, sursa,
   hash-ul sursei, digest-ul configurației, `is_protocol`, sha-ul acestui protocol, cele 3 variante 5+1, q_V, h_V,
   E_main, E_J, E_v și descriptorii J. Refuză date reale dacă `rezultate/EJ/PUTERE_EJ.json` nu are `EJ_PASS`.

## 3. Martori (cod de test; trebuie să treacă exact)

- EJ1 constante: P2, P3 = rapoartele `math.comb`; 14 190 triplete / 10 poziții / 10 perechi;
  `PROTOCOL_JOKER == replace(engine.PROTOCOL, seed_master=4520)`; `step_seed(PROTOCOL_JOKER, 7) = 4520·100003 + 7`.
- EJ2 forma 5/45 (set sintetic Joker construit prin `parser_multi.build_game_dataset("joker", <cale>)`): π în simplexul
  45; A 45×45 simetrică, diagonală zero, normă spectrală 1; W Kuramoto 45×45 ≥ 0 cu suma maximă pe rând 1;
  `topk_frac` cu suma 5; 3 variante 5+1 distincte, 5 numere distincte sortate din 1..45 + Joker din 1..20; E_main < 10⁵;
  q_V în simplexul 20.
- EJ3 tensor comun: N^{(n_steps)} = `cross_counts` bit cu bit (`torch.equal`) și = `joint_counts` ca întregi; sumele pe
  rânduri = frecvențele principale; Σ_j N_ja = 5·#{t: Joker_t = a}.
- EJ4 condiționată + holonomie: q_V = Σ_{j∈V} P_ja / Σ_{j∈V} p_j (1e-12); Σ_a q_V(a) = 1 (1e-12); h_V = Σ_{j∈V} p_j h_j /
  Σ_{j∈V} p_j cu h_j din `joker_entanglement.holonomy` (1e-12).
- EJ5 alegerea Joker-ului: = buclă Python exhaustivă peste 20 de valori (cu penalizarea de suprapunere și departajarea
  după indice) pe tabele aleatoare; tabel construit în care modul marginal al Joker-ului ≠ modul condiționat dat V ⇒
  a*_1 = modul condiționat; numitor 0 (V neextras) ⇒ q uniform ⇒ Joker-ii 1, 2, 3 pentru v = 1, 2, 3.
- EJ6 covarianță Z_20: deplasarea etichetelor Joker a → a+s (mod 20) în date ⇒ q_V deplasat exact (`torch.roll`),
  Joker-ii aleși deplasați cu s (fixtură cu minim unic, verificat), variantele principale și π identice bit cu bit.
- EJ7 cauzalitate: set trunchiat la pașii < k ⇒ π identic (1e-12), aceleași variante principale, același N, q_V, Joker-i.
- EJ8 echivarianță la permutarea etichetelor principale: N permutat pe rânduri exact; q_{σ(V)} pe datele permutate = q_V.
- EJ9 GPU = CPU (π la 2e-5, N și q_V exact); `final_state` vectorizat (r = 5, zile duble) = `Prefix.state(n_steps)` bit
  cu bit; universuri în lot = unul câte unul (π la 1e-9); Joker-ii în lot = unul câte unul.
- EJ10 QUBO exact-5 la n = 45: MCMC cu configurația protocolului = minimul exhaustiv pe toate C(45,5) = 1 221 759
  combinații (GPU), aceeași combinație și energie la 1e-9; energia = formula explicită (buclă Python).
- EJ11 integritate: `engine.py`, `parser.py`, `parser_multi.py`, `motor_n.py`, `joker_entanglement.py` și acest
  protocol au hash-urile sigilate; sigiliul are `code_files_present: []`, `results_present: false`.
- EJ12 (numai DUPĂ verdictul `EJ_PASS` din §4, altfel `skip`): fumul produsului pe LIVE Joker —
  `run_full_joker(build_game_dataset("joker", "live"))` cu `PROTOCOL_JOKER`: structură validă (EJ2), `is_protocol=True`,
  `source_kind="live"`, `positive_claims_allowed=False`, `cross_counts` = N^{(n_steps)}. Variantele NU se tipăresc,
  NU se salvează, NU se compară.

## 4. Putere sintetică (γ = 1/2) — praguri fixate înainte de orice rulare; nicio rulare pe date reale înainte

Generator GPU (`torch.Generator("cuda")`, loturi de 128 de universuri, ordinea fixă a apelurilor): T = 2202 (lungimea
arhivei LIVE Joker), o extragere pe pas. Per lot de b universuri, în această ordine: (1) H = primele 5 din
`argsort(rand(b,45))` (mulțimea plantată); (2) `a_H = randint(0, 20, (b,))` (Joker-ul plantat); (3) `mix = rand(b,T) < γ`
(Bernoulli comun pentru partea principală și Joker); (4) principal = Gumbel-top-5 din `β·[j∈H]·mix + G`, G Gumbel din
`rand(b,T,45)` limitat la [1e-12, 1−1e-7]; (5) Joker = argmax din `β_J·cos(φ_a − φ_{a_H})·mix + G_J`, G_J Gumbel din
`rand(b,T,20)` limitat la fel. β = β_J = 1. Extragerile înclinate poartă simultan H și Joker-ul înclinat spre a_H, deci
dependența Joker ↔ principal este cea pe care o măsoară tensorul comun J. Motorul E-J complet (O1–O6 + Joker,
`PROTOCOL_JOKER`) rulează la pasul final k = T pe `final_state` și pe N din `joint_counts`; sămânța motorului pentru
universul u din setul s: `4520·10⁶ + s·10⁵ + u`.

Statistici:
- Principal: `S = Σ_{v=1..3} |V_v ∩ H|`, p EXACT condiționat de variante:
  `p = #{H' ⊂ [45], |H'| = 5 : Σ_{j∈H'} m_j ≥ S} / 1 221 759` (m_j = numărul de variante care conțin j; întregi).
- Joker: distanța circulară `d(a, b) = min(|a−b|, 20−|a−b|)`; lovitură-fereastră dacă `d(a*_1, a_H) ≤ 1`. Când a_H e
  independentă de date (control), rata-fereastră este EXACT 3/20 = 0.15 (a_H uniformă pe Z_20).

Semințe: γ = 1/2 → 452002 (s = 2), γ = 1/8 → 452003 (s = 3), control γ = 0 → 452004 (s = 4).
- **G1 putere principală:** B1 = 512 la γ = 1/2 → PASS dacă fracția cu p ≤ 0.01 este ≥ 0.90.
- **G2 control principal:** B2 = 512 la γ = 0 → PASS dacă rata fals-pozitivă (p ≤ 0.01) este ≤ 0.02.
- **GJ1 putere Joker:** aceleași B1 = 512 la γ = 1/2 → PASS dacă rata-fereastră este ≥ 0.50.
  Justificare analitică (înainte de calcul, aproximativă): la V_1 ≈ H, ~68% din greutatea q_H vine din extrageri
  înclinate; q_H(a_H) ≈ 0.089, q_H(a_H±1) ≈ 0.086, q_H(a_H±2) ≈ 0.077, q_H(a_H±3) ≈ 0.064 pe ~1900 de observații
  ponderate ⇒ rata-fereastră așteptată ≈ 0.75; pragul 0.50 lasă marjă pentru erorile părții principale.
- **GJ2 control Joker:** aceleași B2 = 512 la γ = 0 → PASS dacă rata-fereastră este ≤ 0.20 (nul exact 0.15,
  abatere standard binomială 0.016).
- Descriptiv (fără prag): γ = 1/8, B = 256; media S, media |V_1 ∩ H|, rangul mediu al lui H în π; rata Joker exactă
  `a*_1 = a_H`, distanța circulară medie, rangul lui a_H în q_{V_1}; „oracolul” argmin E_J cu V = H adevărat (separă
  erorile părții principale de cele ale Joker-ului); selectorul marginal argmax_a Σ_j N_ja (numai comparație descriptivă).
Verdict: `EJ_PASS` numai dacă EJ1–EJ11 trec și G1, G2, GJ1, GJ2 trec; altfel `EJ_FAIL`, publicat ca atare, fără retuning
(β, β_J, γ, T, hiperparametri, statisticile și pragurile nu se schimbă după rezultat; EJ12 nu rulează). Puterea pe
sintetic NU spune nimic despre arhiva reală și NU este un avantaj predictiv.

## 5. Artefacte

`tu3/motor_joker.py`, `tu3/tests/test_motor_joker.py`, `tu3/putere_ej.py`, `tu3/rezultate/EJ/PUTERE_EJ.json` (0444,
fără suprascriere, cu hash-urile codului și ale protocolului), apoi `predari/OPERATIV.md`, mesajele utilizatorului și
predarea QL649 (pereche nouă, același UTC, prin `predari/genereaza_predare.py`).
