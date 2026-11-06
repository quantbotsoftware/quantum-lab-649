# PROTOCOL TU3-SR — scorul real 5/40 și Joker (taburile 4–5), sesiunea S7 „SR-P”, cu extensia „Quantum Shadow” (MPS)

Stare: scris și sigilat (`tu3/SIGILIU_TU3_SR.json`) ÎNAINTE de orice cod și de orice calcul al acestei sesiuni
(`code_files_present: []`, `results_present: false`). Decizia utilizatorului: D4 = DA — scorul pe istoria reală 5/40 și
Joker, S7 = protocol + putere sintetică, S8 = rularea reală UNICĂ (`tu3/DECIZII_PLAN_TU3_20261027.json` `b6a5ba05…`; plan
`c7b4bfd3…` §4 S7–S8); cererea sesiunii S7 din 2026-10-27 (Mesajul 48 din supliment), care adaugă extensia „Quantum
Shadow”: universurile virtuale generate din tensori `torch.complex64` asamblați într-un MPS, entanglement-ul dintre cele
două urne Joker, marginea de tip Ryu–Takayanagi, „fluxul minim” fără matrici redundante, VRAM < 6.2 GB și temperatura
GPU < 71 °C. Calcul CLASIC (PyTorch pe GPU-ul RTX 5060 Laptop, NumPy pe CPU). `positive_claims_allowed=false`.

## 0. Ce înseamnă (și ce NU înseamnă) vocabularul acestui protocol

- **MPS / complex64.** Un MPS este aici o reprezentare matematică EXACTĂ a unei legi de probabilitate P prin amplitudini
  ψ = √P · e^{iφ}; extragerea se face prin eșantionare Born exactă (|ψ|²). Fazele φ sunt unitare locale diagonale: NU
  schimbă nici legea extragerilor, nici spectrul Schmidt (martorul W4 o verifică). Nimic nu rulează pe hardware cuantic;
  nu se revendică avantaj cuantic sau noutate.
- **„Entanglement-ul dintre urne”** = entropia von Neumann a spectrului Schmidt al stării √P(S, a) la tăietura
  „urna principală | urna Joker”. Pentru o lege CLASICĂ aceasta este o măsură de corelație a legii comune, nu o proprietate
  fizică a bilelor. Sub nul (urne independente, regula oficială a jocului) legea este produs ⇒ rang Schmidt 1 ⇒ entropia
  este EXACT 0.
- **„Ryu–Takayanagi”** = numai analogul discret din rețelele tensoriale: pentru o regiune A, S(A) ≤ |γ_A| · ln χ, unde γ_A
  este tăietura minimă a grafului rețelei și χ dimensiunea legăturilor tăiate (Swingle 2012; Pastawski–Yoshida–Harlow–
  Preskill 2015). „Fluxul minim” = valoarea tăieturii minime (max-flow = min-cut) pe graful MPS cu capacitățile
  ln χ_eff ale legăturilor efective (blocurile nule eliminate). NU este formula holografică AdS/CFT.
- **„Stări de vacuum energetic stabil din ecuația Wheeler–DeWitt”**: nicio ecuație Wheeler–DeWitt nu se scrie sau se
  rezolvă; termenul nu se aplică acestui calcul. Ieșirile sunt scoruri statistice (hits, log, Brier, SCI) și verdicte
  preînregistrate. Variantele produsului rămân minime de energie ale modelului, NU predicții.
- Dacă extragerile sunt uniforme și independente, istoricul nu oferă avantaj predictiv; un rezultat pozitiv exploratoriu
  pe o arhivă deja explorată NU ar demonstra avantaj (cere confirmare prospectivă separată).

## 1. Inventar read-only (făcut înainte de acest protocol)

### 1.1 Ce afișează azi taburile 4–5 în 5/40 și Joker (`tu3/ui_tu3.py` `9920b9dd…`, `render`)
- **Tab 4 „🌌 Multiversul Nul”**: verificarea de putere SINTETICĂ a motorului (`PUTERE_E40.json` / `PUTERE_EJ.json`,
  read-only): verdict, porțile G1/G2 (+ GJ1/GJ2 la Joker), tabelul și graficul ratelor pe seturi; mesajul „SCI pe istoria
  reală: NERULAT — `validare.py` este definit pe 6/49”; frecvențele reale LIVE față de rN/n (descriptiv) și, la Joker,
  frecvențele Joker față de N/20.
- **Tab 5 „⏳ Mașina Timpului”**: „Backtestul cauzal pe istoria reală … este NERULAT: cere un protocol separat” +
  inventarul setului LIVE (`ds.summary()`).
- Motoarele: `motor_n.run_full_540` (formă (40, 6, 5), `PROTOCOL_540`, digest `b364fc0cfb6c`) și
  `motor_joker.run_full_joker` (formă (45, 5, 5) + Joker 1..20, `PROTOCOL_JOKER`, digest `61c9445bce19`); ambele refuză
  datele reale fără `E40_PASS`/`EJ_PASS` (ambele PASS). Configul FAST (`FAST_OVERRIDES`) este numai pentru teste.
  `motor_n.score_steps` / `score_states` / `variants_steps` / `Prefix` dau mersul înainte cauzal pe orice pas k.
- Surse: LIVE (produsul) și ÎNGHEȚAT (`tu3/date/extrageri_540.jsonl` `e1591b87…`, 2490 extrageri, 2427 de pași, până la
  2026-10-25; `tu3/date/extrageri_joker.jsonl` `45713aa2…`, 2202 extrageri, 2139 de pași, până la 2026-10-25;
  `MANIFEST_DATE.json` `ea50bdcf…`). Arhivele au fost deja citite de produs (stare finală), de porturile 7–12 și de
  graficele de frecvență: NU sunt set „nevăzut”.

### 1.2 Scorul 6/49 (`validare.py` `01085209…`, `PREINREGISTRARE_QL649.md` §4–§5)
- SCI: χ² frecvențe (E = 6N/49), χ² perechi (E = N·30/2352), χ² histograma golurilor per număr (binuri 1..20, 21+) față de
  media nulului, suprapunerea serială medie; `z_k` față de M = 8192 istorii nule (aceeași structură de pași, sămânța 649);
  `SCI = Σz/2`; p empiric `(1 + #{SCI_nul ≥ SCI})/(M + 1)`. Descriptiv pe 6/49.
- Backtest: încălzire 100 de pași; ținte = toate extragerile pașilor k ≥ 100, prezise din pașii < k; comparatori U
  (q = 6/49), B (π ∝ c+1, bilet top-6), R (π ∝ ew+0.5, timp de înjumătățire 26 de pași, bilet top-6; egalități → numărul
  mai mic); legea marginală `q = 6/49 + λ(6π − 6/49)`, `λ = min(0.5, λ_max)`, q ∈ [1e-4, 1−1e-4]; hits = |bilet ∩
  extragere| (QL: varianta 1); log = Σ y log q + (1−y) log(1−q); Brier = Σ (q−y)²; exces = hits/ținte − 36/49; jumătăți
  `floor(n/2)`; 6 porți (§2.6); p exact al hits-urilor sub nul (convoluția hipergeometricelor; `exact_tail`). Rezultatul
  publicat: `QL_NO_PROMOTION_EXPLORATORY`, 0/6 (`rezultate/backtest_unic/REZULTATE.json`).
- Dependente de 49/6: `N, K6`, `6/49`, `36/49`, `30/2352`, `108/49`, `hyper_pmf` (6 din 49), `top6`, `null_onehot` (6
  din 49), `GAP_BINS` (generic). Generice: structura scorului, regula λ, porțile, jumătățile, convoluția exactă.

## 2. Ecuațiile generalizate pentru o urnă (n, r) cu bilet de k numere

Notații: urna are n numere, extragerea are r numere distincte, biletul k numere distincte; T = numărul de ținte.
Componente: **5/40** = (n, r, k) = (40, 6, 5); **Joker principal** = (45, 5, 5); **bila Joker** = (20, 1, 1). Pentru
(49, 6, 6) toate formulele de mai jos reproduc EXACT pe cele din `validare.py` (martorul W1).

2.1 **Legea marginală**: p0 = r/n; `q_j(π) = p0 + λ (r π_j − p0)`, `λ = min(1/2, λ_max)`, λ_max = cel mai mare λ cu
    q_j ∈ [1e-4, 1 − 1e-4] pentru toți j. Aceeași regulă pentru QL, B, R; U: q_j = p0.
2.2 **Scoruri pe țintă**: `log = Σ_j y_j ln q_j + (1 − y_j) ln(1 − q_j)`; `Brier = Σ_j (q_j − y_j)²`; hits = |bilet ∩
    extragere|.
2.3 **Legea nulă a hits-urilor** (orice bilet fixat cauzal, extrageri uniforme independente):
    `P(h) = C(k, h) C(n − k, r − h) / C(n, r)`, h = 0..min(k, r); media `E_U = k r / n` (5/40: 3/4; Joker principal: 5/9;
    bila: 1/20); varianța `k (r/n)(1 − r/n)(n − k)/(n − 1)`. Totalul pe T ținte are legea convoluției de ordin T (exactă,
    calculată ca în `validare.exact_tail`, float64); p exact = P(H ≥ H_obs).
2.4 **Exces**: `exces = hits/T − E_U`; pragul porții 1 se scalează RELATIV: `τ = 0.20 · E_U / (36/49)` (= exces relativ
    49/180 ≈ 27.2 %): 6/49 → 0.20 (identic), 5/40 → 0.2041667, Joker principal → 0.1512346, bila → 0.0136111.
2.5 **Comparatori**: B: `π_B ∝ c_j + 1` (numărări pe pașii < k); R: `π_R ∝ ew_j + 0.5`, `ew(s) = ew(s−1)·2^{−1/26} +
    cnt(s−1)`; biletele B/R = top-k după π (sortare stabilă după −π ⇒ egalități → numărul mai mic). QL: π al motorului
    (`motor_n.score_steps`, configurația protocolului jocului), biletul = varianta 1 a `variants_steps`.
2.6 **Porțile de promovare** (pe componentă; toate 6): (1) exces_QL ≥ τ; (2) hits_QL > hits_B și > hits_R; (3) log_QL −
    log_U > 0 și log_QL − log_B > 0; (4) Brier_QL < Brier_U, Brier_B, Brier_R; (5) în ambele jumătăți exces > 0 și hits_QL
    − hits_B > 0; (6) în ambele jumătăți log_QL − log_B > 0. Jumătăți: ținte cronologice, prima = floor(T/2).
2.7 **Descriptiv**: distribuția potrivirilor 0..min(k, r) față de T·P(h); reuniunea celor 3 variante cu așteptarea
    „legacy” `T·3kr/n` (6/49: 108/49, identic) și cea exactă `Σ_t |U_t| r/n`; biletele schimbate față de B.
2.8 **Urna duală Joker (defectul (20, 1))**: două componente scorate separat, pe aceleași ținte: principal (45, 5, 5) și
    bila (20, 1, 1). QL-bila: `π_J = q_{V1}` (distribuția condiționată a lui `motor_joker.joker_conditional` pentru
    varianta 1, din tensorul cauzal N^{(k)} al pașilor < k), biletul = `jokers[0]` din `motor_joker.choose_jokers`.
    B_J/R_J pe numărările bilei. Pentru r = 1 nu există perechi (χ²_perechi nedefinit). Sub nul, extragerea principală și
    bila sunt independente și, condiționat de trecut, hits_principal și hits_bilă sunt independente cu legile 2.3 ⇒
    totalurile sunt independente; testul combinat Bonferroni (§4.3) are rata de fals-pozitive ≤ α exact.
2.9 **SCI generalizat**: χ²_frecv cu E = rN/n; χ²_perechi cu E = N·r(r−1)/(n(n−1)) (numai r ≥ 2; 6/49: 30/2352);
    χ²_goluri (binuri 1..20, 21+) față de media nulului; suprapunerea serială (aceeași formulă); `SCI = Σ_k z_k / √K`, K =
    numărul statisticilor (6/49: K = 4 ⇒ /2, identic). **Joker**: K = 8 = principal (4) + bilă (3: frecv, goluri,
    suprapunere) + χ²_cross al tabelului N_ja (45 × 20) cu E_ja = N·(5/45)·(1/20). p empiric ca la 6/49.

## 3. Extensia „Quantum Shadow”: generatorul MPS al universurilor (complex64)

3.1 **Situri**: un sit de mod b ∈ {0, 1} (amplitudini √(1−γ), √γ); n situri binare s_j (bila j extrasă sau nu), legătura
    purtând (b, c), c = numărul de bile alese până la j (0..r); la Joker încă un sit a ∈ 1..20. Nucleele (complex64):
    `A_j[(b,c), s, (b,c+s)] = (w_j^{(b)})^{s/2} e^{i s φ_j}`, φ_j = 2π(j−1)/n; nucleul Joker
    `[(b, r), a] = (v_a^{(b)} / Z_b)^{1/2} e^{i φ^J_a}`, φ^J_a = 2π(a−1)/20; condițiile la margini impun c = r la final.
3.2 **Nul**: γ = 0 (blocul b = 1 eliminat), w ≡ 1, v ≡ 1 ⇒ |ψ|² uniform pe cele C(n, r) mulțimi × uniform pe 1..20 (starea
    Dicke |D^n_r⟩ ⊗ uniform); legea oficială a jocului, EXACT produs ⇒ entropia la tăietura urnelor = 0.
3.3 **Semnal**: per univers, H = 5 numere uniform alese (5/40 și Joker principal) și a* uniform în 1..20 (Joker);
    `w_j^{(1)} = e^{β·1[j∈H]}`, β = 1 ⇒ P(S | b = 1) ∝ e^{β|S∩H|} (Poisson condiționat; DIFERIT de legea Gumbel top-k a
    verificărilor E40/EJ — declarat); `v_a^{(1)} = exp(β_J cos(φ^J_a − φ^J_{a*}))`, β_J = 1 (= legea Joker EJ, exact);
    modul b este COMUN celor două urne ⇒ corelație principal–bilă (rang Schmidt ≤ 2, marginea ln 2).
3.4 **Eșantionare exactă fără vectorul de stare**: mediile drepte `R_j = Σ_s A_j^s R_{j+1} (A_j^s)^†` (D × D, D ≤ 2(r+1))
    se calculează o dată pe univers; extragerea merge stânga → dreapta cu vectorul stâng l: `P(s | trecut) ∝ (l A_j^s) R_{j+1}
    (l A_j^s)^†`. Nu se stochează niciodată vectorul de stare (C(45,5)·20 = 24 435 180 amplitudini) și nici matrici
    densitate mari; memoria este O(B·T·D). Rezultă extragerile (indicatori și numere sortate) pe GPU.
3.5 **Entanglement și tăietura minimă** (Joker, descriptiv, per univers): spectrul Schmidt la orice legătură din matricile
    Gram stânga/dreapta (contracții de transfer în complex64, diagonalizarea D × D în complex128 pentru stabilitate):
    `λ = eig(L^{1/2} R L^{1/2})/tr`, `S = −Σ λ ln λ`. „Fluxul minim” = tăietura minimă (max-flow, Edmonds–Karp) pe graful
    lanțului MPS cu capacitățile `ln χ_eff`; marginea verificată: `S_urne ≤ min-cut` (nul: 0 ≤ 0; semnal: ≤ ln 2).
    Descriptiv suplimentar: profilul intra-urnă al stării Dicke (tăietura după j situri), unde λ_c sunt EXACT ponderile
    hipergeometrice C(j,c)C(n−j,r−c)/C(n,r) — constrângerea „fără întoarcere” este cea care încâlcește siturile; marginea
    ln(min(j, r)+1).
3.6 **Precizie**: complex64 ⇒ probabilități float32; abaterea față de legea exactă se măsoară în martori (W2–W5) pe
    instanțe mici, cu toleranța 2e-5 absolută pe probabilitățile condiționate; nulul are P(s_j = 1 | c) = (r − c)/(n − j + 1).
    Această abatere nu intră în niciun test exact (testele 2.3 sunt analitice).
3.7 **Resurse** (cererea utilizatorului): VRAM plafonat rigid cu `torch.cuda.set_per_process_memory_fraction(6.2e9 /
    memoria totală)` (6.2 GB = 6.2·10⁹ octeți); vârfurile `max_memory_allocated/reserved` se scriu în rezultate și trebuie
    să fie < 6.2·10⁹. Temperatura GPU: un fir citește `nvidia-smi` la fiecare secundă; calculul face pauză între loturi
    când T ≥ 69 °C și reia la T ≤ 64 °C; loturile sunt mici (≤ 16 pași de motor sau ≤ 256 de universuri); se scriu T_max,
    numărul și durata pauzelor și `temperature_target_met = (T_max < 71)`. Software-ul NU poate garanta fizic plafonul
    termic (protecțiile hardware/OS rămân); o depășire se declară, nu invalidează matematica (RNG pe contor ⇒ rezultatele
    nu depind de pauze sau de loturi). Fără CUDA ⇒ refuz (nu se rulează puterea pe CPU).

## 4. Rularea reală UNICĂ (S8 — fixată ACUM, executată NUMAI în S8, după S7 PASS pentru jocul respectiv)

4.1 **Sursa**: arhiva ÎNGHEȚATĂ (`parser_multi.build_game_dataset(game, "frozen")`, sha-urile §1.1, verificate la start);
    structura reală de pași. Refuz dacă `tu3/rezultate/SR/<joc>/START.json` există (rulare unică), dacă sigiliul/protocolul
    sau `engine.py`/`motor_n.py`/`motor_joker.py`/`parser*.py` diferă de sigiliu, sau dacă `PUTERE_SR.json` nu dă
    `SR_P_PASS` pentru jocul respectiv. Comanda va cere explicit `--real --sesiune S8`.
4.2 **Predictorul QL**: încălzire 100 de pași; ks = 100..S−1; `motor_n.Prefix` + `motor_n.score_steps(cfg = PROTOCOL_540 /
    PROTOCOL_JOKER, chunk = 64)` și `variants_steps` (semințele `step_seed(cfg, k)`); Joker: `cross` cauzal la k +
    `motor_joker.joker_stage`. Motoarele se IMPORTĂ nemodificate (punctele standard de apel). Predicțiile (π, variantele,
    biletele B/R, π_J) se scriu în `PREDICTII.npz` și se sigilează (sha + UTC) ÎNAINTE de scor; scorul se calculează din
    fișierul scris.
4.3 **Verdicte** (pe joc; α fixate):
    - **D1 (primar, mersul înainte)**: 5/40: p_exact(hits_QL) ≤ 0.01; Joker: min(p_principal, p_bilă) ≤ 0.005
      (Bonferroni, α total 0.01) ⇒ `SR_DETECTIE_EXPLORATORIE`, altfel `SR_FARA_DETECTIE`.
    - **D2 (SCI)**: p empiric ≤ 0.01 față de M = 8192 universuri nule MPS cu structura reală de pași (semințele 5401101 /
      4521101) ⇒ `SCI_ABATERE_EXPLORATORIE`, altfel `SCI_COMPATIBIL_NUL`. D1 și D2 sunt întrebări separate, raportate
      separat; nicio combinare, nicio selecție după rezultat.
    - **Promovare**: 6/6 porți 2.6 ⇒ `SR_PROMOVAT_EXPLORATORIU` (Joker: 6/6 pe AMBELE componente), altfel
      `SR_NO_PROMOTION_EXPLORATORY`.
    - Orice verdict păstrează `positive_claims_allowed=false`; o detecție NU este avantaj predictiv (arhivă explorată,
      multiple analize anterioare pe aceleași date).
4.4 Rezultatele (0444) se publică indiferent de verdict, fără tuning după vizualizare; verificare SEPARATĂ (recalcul NumPy
    din `PREDICTII.npz` fără import din `scor_real.py`) în S8; UI-ul taburilor 4–5 afișează verdictul în S8 (înlocuire
    sigilată `inlocuiri_tu3/v1`, protocol/amendament S8 propriu). Orice defect tehnic ⇒ amendament scris + păstrarea
    încercării inițiale.

## 5. Puterea sintetică S7 (executată ACUM; nu citește nicio arhivă reală 5/40/Joker)

Universuri de lungime L = 2490 (5/40) și L = 2202 (Joker), o extragere pe pas (structura reală de pași NU se citește în
S7; cei 63 de pași dubli se tratează în S8). Toate universurile vin din generatorul MPS §3. În timpul rulării,
`parser_multi.build_game_dataset`, `resolve_frozen` și `resolve_live` sunt înlocuite în proces cu o funcție care aruncă
excepție (garda „fără arhivă reală”).

5.1 **A — SCI** (per joc): referința nulă M = 8192 (sămânța 5407001 / 4527001); semnal γ = 1/2, B = 512 (5407002 /
    4527002); control γ = 0, B = 512 (5407004 / 4527004); descriptiv γ = 1/8, B = 256 (5407003 / 4527003). Detecție =
    p empiric ≤ 0.01 față de referința nulă. **P1**: rata la γ = 1/2 ≥ 0.90. **P2**: rata la control ≤ 0.02.
5.2 **B — mersul înainte cu motorul complet** (configurația protocolului jocului, fără FAST): semnal γ = 1/2, B = 20
    universuri (5407012 / 4527012); nul, B = 6 universuri (5407014 / 4527014). Grila: G = 192 de pași
    `k_i = 100 + floor(i (L − 100)/192)`, i = 0..191; ținta pasului k = extragerea k, prezisă din pașii < k. Semințele
    motorului pe stare: `7·10¹² + joc·10⁹ + set·10⁷ + u·10⁴ + k` (joc = 540 / 452; set = 12 / 14). Detecția = testul D1
    (§4.3) restrâns la cele 192 de ținte. **P3**: ≥ 19/20 universuri cu semnal detectate (rata ≥ 0.95; limita inferioară
    Clopper–Pearson unilaterală 95 % pentru 19/20 ≈ 0.78). **P4**: ≤ 1/6 universuri nule detectate (testul exact are FPR
    ≤ α prin construcție; P(≥ 2/6 | α = 0.01) ≈ 0.15 %).
    Descriptiv: porțile 2.6 pe grilă (rate), hits QL/B/R, |V1 ∩ H| mediu, la Joker detecția numai pe bilă (puterea bilei
    pe 192 de ținte este așteptat SUB cea pe ~2040 de ținte reale), entropia urnelor și min-cut-ul MPS per univers.
    Notă de proiect (calcul analitic pe legea sintetică, nu pe date): la γ = 1/2 o bilă din H apare cu probabilitatea
    0.2223 față de 0.15 (5/40) și 0.1705 față de 0.1111 (Joker principal); dacă biletul conține H, z ≈ 6.6 / 6.1 pe 192 de
    ținte. Puterea pe ~2330 / ~2040 de ținte reale este așteptată ≥ cea pe grilă (nedemonstrat formal; grila este un
    proxy conservator declarat). γ = 1/8 NU se rulează la mersul înainte (cost: ~0.47 s/stare).
5.3 **P5 — martori** (`tests/test_scor_real.py`, toate trebuie să treacă înainte de rularea puterii):
    - W1 identitatea pe 6/49: scorul generalizat aplicat pe `rezultate/backtest_unic/PREDICTII.npz` + arhiva 6/49
      înghețată reproduce `REZULTATE.json` (ținte, hits, log, Brier, porți, verdict, distribuția potrivirilor, p exact)
      EXACT (numere întregi bit cu bit; real ≤ 1e-9 relativ); SCI generalizat cu eșantionatorul „legacy” top-k (sămânța 649)
      reproduce `SCI.json` (χ²_frecv, χ²_perechi și suprapunerea reale exact ≤ 1e-12 relativ; χ²_goluri — dependent de
      media nulului —, mediile/abaterile nulului, z, SCI și p ≤ 1e-6 relativ — `index_add_` pe CUDA nu e determinist).
      Fișierele 6/49 sunt rezultate deja publicate ale unei piste închise; nu se recalculează nimic pe 6/49 în afara
      acestui martor.
    - W2 nucleele MPS: |ψ|² pe (8, 3) (enumerare completă) = legea exactă (nul uniform; semnal Poisson condiționat), abatere
      ≤ 2e-5; probabilitățile condiționate nule = (r − c)/(n − j + 1).
    - W3 eșantionatorul: frecvențele empirice pe (8, 3) și pe Joker mic (8, 3) + (5, 1), 2·10⁵ extrageri, χ² față de legea
      exactă (p > 1e-3); fiecare extragere are exact r bile distincte în 1..n și o bilă Joker în 1..m.
    - W4 fazele: legea și spectrul Schmidt identice cu φ ≡ 0 (≤ 1e-5).
    - W5 entanglement: nul ⇒ S_urne ≤ 1e-6 și χ_eff = 1; semnal ⇒ 0 < S_urne ≤ ln 2 + 1e-6; profilul Dicke = entropia
      hipergeometrică (≤ 1e-4); min-cut (Edmonds–Karp) = ln χ_eff al tăieturii; S ≤ min-cut + 1e-6.
    - W6 formulele 2.1–2.4 pentru (40,6,5), (45,5,5), (20,1,1): pmf hipergeometrică = enumerare, Σ = 1, media k r/n,
      convoluția exactă = enumerare pe T mic, regula λ, τ.
    - W7 SCI generalizat pe un set mic: E-urile 2.9, K și normalizarea; Joker cu 8 statistici.
    - W8 mersul înainte pe un univers mic cu config FAST (numai test): cauzalitate (predicția la k nu se schimbă când se
      modifică extragerile ≥ k), forma biletelor (k distincte), bila în 1..20.
    - W9 garda „fără arhivă reală” activă în calea de putere; `--real` refuză fără `SR_P_PASS`, fără `--sesiune S8` și dacă
      START există (testat pe director temporar, fără a citi arhiva).
    - W10 plafonul VRAM aplicat (fracția = 6.2e9/total) și monitorul termic (pauză/reluare pe un senzor simulat).
    - W11 sigiliul: protocolul = sha-ul sigilat, `code_files_present: []`, 0444; fișierele înghețate byte-identice;
      importurile `scor_real.py` ⊆ stdlib ∪ {numpy, torch, engine, motor_n, motor_joker, parser_multi, parser}; nu importă
      `validare` și nicio pistă închisă.
    - W12 (după rulare) `PUTERE_SR.json` 0444, `real_archive_read: false`, verdictele recalculate din câmpuri, VRAM < 6.2e9.
5.4 **Verdict pe joc**: `SR_P_PASS` dacă P1–P5 trec, altfel `SR_P_FAIL`. **S7 PASS** = ambele jocuri `SR_P_PASS`. Dacă un
    singur joc trece, S8 rulează numai pentru el; un `SR_P_FAIL` se publică și NU se repetă cu alți parametri.
    `tu3/rezultate/SR/PUTERE_SR.json` (0444) refuză suprascrierea.

## 6. Fișiere

- NOI: `tu3/PROTOCOL_TU3_SR.md`, `tu3/SIGILIU_TU3_SR.json`, `tu3/scor_real.py`, `tests/test_scor_real.py`,
  `tu3/rezultate/SR/PUTERE_SR.json`, `tu3/rezultate/SR/putere_sr_<UTC>Z.log`.
- NICIO înlocuire în S7: `ui_tu3.py`, `test_app_tu3.py`, `porturi_712.py` și testele existente rămân byte-identice ⇒ nu se
  scrie nicio înregistrare de înlocuire în S7. În S8, afișarea verdictului în taburile 4–5 va trece prin `inlocuiri_tu3/v1`
  cu înregistrarea `tu3/inlocuiri/INLOCUIRE_SR_<UTC>Z.json` (prefixul `INLOCUIRE_T7C_` aparține sesiunii S6: testul C8
  citește ultima înregistrare `INLOCUIRE_T7C_*`, deci o a doua cu acest prefix l-ar rupe — declarat aici).
- NEMODIFICATE (importate numai în punctele standard de apel): `engine.py`, `parser.py`, `tu3/parser_multi.py`,
  `tu3/motor_n.py`, `tu3/motor_joker.py`, `tu3/joker_entanglement.py`, `validare.py`, `app.py`, `tu3/ui_tu3.py`, toate
  pistele închise, protocoalele/sigiliile anterioare, rezultatele publicate, arhivele înghețate.

## 7. Ordinea S7

(1) acest protocol + sigiliul (`code_files_present: []`); (2) `tu3/scor_real.py` + `tests/test_scor_real.py`; (3) martorii
W1–W11 verzi; (4) rularea puterii (`scor_real.py --putere`), o singură dată; (5) W12 + suitele existente (33 passed + 3
skipped; 71 passed) + `inlocuiri_tu3 --verifica` + matricea; (6) repornirea serverului din pictogramă; (7) predarea.

## 8. Acceptare S7

S7 complet = §7 parcurs, `PUTERE_SR.json` scris cu verdictele pe joc, toate suitele verzi, 0 drift al fișierelor înghețate
(sigiliul SR). Verdictul de putere (PASS sau FAIL) se publică așa cum iese.

## 9. Declarații

Arhivele 5/40/Joker sunt deja explorate; nu există set „nevăzut”. Puterea este pe date SINTETICE și nu spune nimic despre
arhiva reală. Legea semnalului (Poisson condiționat) diferă de E40/EJ (Gumbel top-k). Grila de 192 de ținte este un proxy
conservator, nu o teoremă. Inspirația cuantică este strict matematică; termenii „Ryu–Takayanagi” și „Wheeler–DeWitt” sunt
folosiți numai în sensul §0. Sigilii locale, fără atestare externă. `positive_claims_allowed=false`.
