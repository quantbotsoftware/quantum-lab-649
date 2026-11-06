# PREINREGISTRARE QL649 — „Quantum Lab 649” (pistă nouă, separată de DL-649)

Versiune protocol: `QL649-P1`. Scris și sigilat (SHA-256 în `SIGILIU_PROTOCOL.json`)
ÎNAINTE de scrierea codului operatorilor și de orice calcul de operator pe
`extrageri_649.jsonl`. Inventarul read-only al datelor (număr rânduri, chei,
tipuri, zile duble) a fost făcut înainte și NU este experiment de selecție.

Pista DL-649 (revizia `20261025T165403Z`) rămâne înghețată; nimic de aici nu
modifică modelele închise, OGLINDA, perechea HANDOFF/PROMPT din rădăcină sau
probele istorice. Calcul clasic (PyTorch pe GPU NVIDIA, fallback CPU numai la
eroare de driver). Inspirația „cuantică” (non-hermitic/EP, Born, Amplituhedron,
Kuramoto, Boltzmann) este strict matematică: fără hardware cuantic, fără avantaj
cuantic, fără noutate mondială revendicată. `positive_claims_allowed=false`.
Arhiva este deja explorată în proiect: valoare confirmatoare 0, nu set nevăzut.

## 1. Date și curățare (parser.py)

- Sursă: `next_candidate/predictie_numere/probe_date/extrageri_649.jsonl`; hash SHA-256 înregistrat în manifest la fiecare rulare.
- Rând valid: `numbers_sorted` = 6 întregi distincți în 1..49, `draw_date` ISO valid, `draw_key` prezent. Rândurile invalide sunt eliminate cu motiv explicit în raportul de anomalii.
- Duplicate: eliminate după `draw_key` și după (`draw_date`, mulțimea sortată); se păstrează prima apariție, motiv înregistrat.
- Toate tipurile (`regular`, `special`, `unknown`) sunt păstrate; tipul și dezacordul de surse rămân metadate (fără selecție după rezultat).
- Ordine: sortare cronologică stabilă după `draw_date`, apoi `draw_key`. Ordinea fizică a bilelor este neverificată și NU este folosită.
- Pași de timp: o zi calendaristică = un pas de timp (`date-step`). Zilele cu 2 extrageri formează un singur pas; ordinea în zi (necunoscută) nu este inventată.
- Tensori: `draws[N,6]` (int64), `onehot[N,49]` (float32), `step_index[N]`, `pair_counts[49,49]`, pe `cuda` când e disponibil.

## 2. Starea la pasul k (strict cauzală)

La pasul k se folosesc NUMAI extragerile din pașii `< k`. Notații: `N` extrageri
anterioare, `c_j` frecvențe, `C_ij` co-apariții, `gap_j` = pași de la ultima
apariție (k dacă niciodată), `ew_j` = numărare cu pondere `2^{-(k-1-s)/26}` pe pas.

- Exces pe perechi: `p2 = 30/2352`, `E = N·p2`, `A_ij = (C_ij − E)/sqrt(E(1−p2)+1e-9)`, diag 0, apoi `A ← A/‖A‖_2` (dacă norma e 0, A=0).
- Disipare: `z_j` = standardizarea transversală a `gap_j` (medie/abatere pe cele 49, +1e-9); `D = diag(tanh z_j)`.

## 3. Operatori (hiperparametri fixați)

O1 Walk non-hermitic + EP. `H(γ) = A + iγD`. Grilă `γ ∈ linspace(0, 2, 48)`;
quasi-EP real `γ_q` = argmin pe grilă al `min_{a≠b}|λ_a−λ_b|` (ties: γ mai mic).
EP exact complex: Newton în `complex128` pe `g(γ) = (λ_a(γ)−λ_b(γ))²` pentru perechea
minimă la `γ_q`, urmărire prin cel mai apropiat vecin, diferență finită `h=1e-6`,
max 40 iterații, convergență `|g| < 1e-10`; neconvergența se raportează, nu oprește.
Walk: `Ψ0 = 1/√49`, `U = exp(−i H(γ_q) Δ)`, `Δ = 0.15`, 24 pași cu renormalizare.
Test de referință: `H = [[iγ, κ], [κ, −iγ]]` are EP exact la `γ = κ`.

O2 Volum „Amplituhedron” (inspirat; nu este teoria N=4). `z_j = [1, c_j/max c, ew_j/max ew]`
(pozitivi). Pentru toate cele 18424 triplete: `vol = |det[z_i z_j z_l]|`, pondere
`w = (T_ijl+1)/(E_T+1)`, `E_T = N·120/110544`. Amplitudine `a_j = Σ_{triplete∋j} vol·w`,
normalizată la medie 1. Amplitudine de împrăștiere pe perechi `S_ij = Σ_l vol_ijl·w_ijl` (UI).

O3 Poincaré. Disimilaritate `δ_ij = log((E+1)/(C_ij+1))`, deplasată la minim 0.1 și
scalată la medie 2.0. Încorporare 2D în discul unitate, inițializare deterministă
`x_j = 0.5·(cos 2πj/49, sin 2πj/49)`, Adam `lr=0.02`, 400 iterații, stres
`Σ_{i<j}(d_H(x_i,x_j) − δ_ij)²`, proiecție la `‖x‖ ≤ 1−1e-5`.
`d_H(x,y) = arcosh(1 + 2‖x−y‖²/((1−‖x‖²)(1−‖y‖²)))`. Centralitate
`u_j = exp(−d_H(x_j,0))` normalizată la medie 1. Ancore = top-3 după `u_j`
(ties: număr mai mic). Curbură Forman descriptivă pe graful top-6 vecini pozitivi
din A (simetrizat): `F(e) = 4 − deg i − deg j`, nod = media pe muchii.

O4 Kuramoto. `ν_j = k/(c_j+1)` (perioadă medie), `θ_j(0) = 2π·gap_j/ν_j mod 2π`,
`ω_j = 2π/ν_j`, `W = max(A,0)` scalat la suma maximă pe rând 1. RK4 cu `K=2.0`,
`dt=0.05`, 200 pași, `θ̇_i = ω_i + K Σ_j W_ij sin(θ_j−θ_i)`. Ordine locală
`r_i = |Σ_j W_ij e^{iθ_j}| / Σ_j W_ij` (0 dacă rândul e nul). Salt de interferență:
la trecerea ascendentă `r_i > 0.8`, partenerii primesc instantaneu
`θ_j ← θ_j + 0.35·W_ij·wrap(θ_i − θ_j)`.

O5 Colaps Born + filtru Boltzmann. `m_j ∝ |Ψ_walk,j|²·a_j·u_j` (normalizat),
`ψ_j = sqrt(m_j)·e^{i(arg Ψ_walk,j + θ_j)}`, interferență
`Ψ_f = ψ + 0.5·Kφ ψ`, `Kφ_ij = W_ij e^{i(θ_i−θ_j)}`, `P = |Ψ_f|²/Σ`.
Filtru: `R = 50000` replici, `β_r = 10^{linspace(−1,1,R)}`, zgomot alb gaussian
`σ = 0.5`: `π_r = softmax(β_r·(log P + σ ε_r))`; `π_QL = media_r π_r`.
Nucleu descriptiv = numerele aflate în top-6 la ≥ 50% din replici.

O6 MCMC geometric + QUBO pentru 3 variante. Energie
`E(S) = −Σ_{j∈S} log π_QL,j − 0.5·Σ_{i<j∈S} A_ij + 0.25·crowd(S) + 1.0·Σ_{w<v}|S ∩ S_w|`
(variantele se calculează secvențial v=1,2,3). `crowd(S)` (Scutul Anti-Mulțime,
activ implicit, euristic) = [toate ≤31] + [rulaj consecutiv ≥3] + [progresie
aritmetică pe toate 6] + [≥4 cu aceeași ultimă cifră]. MCMC: 256 lanțuri
(8 temperaturi geometrice în [0.05, 2.0] × 32), 10000 pași, propunere = schimbă un
număr din S cu unul din afară (uniform), Metropolis; schimburi între temperaturi
adiacente la fiecare 10 pași. Rezultat = cea mai mică energie văzută
(ties: lexicografic minim). Exact aceeași configurație în produs și în backtest.

Seed master `649`; seed per pas `= 649·100003 + k` (și + v pentru variante).
Produsul pentru extragerea următoare = aceeași procedură la `k = K` (toată istoria).

## 4. Indicele de Coerență Structurală (SCI) și Multiversul Nul

Statistici reale: (1) χ² frecvențe pe 49 (`E = 6N/49`); (2) χ² perechi pe 1176
(`E = N·30/2352`); (3) χ² histogramă goluri per număr (binuri 1,2,…,20,21+) față de
media universurilor nule; (4) suprapunere serială medie între pași consecutivi.
Multivers Nul: `M = 8192` istorii uniforme fără întoarcere, aceeași structură de
pași (aceleași numere de extrageri pe zi), seed 649. `z_k` = (real − medie nul)/abatere nul;
`SCI = Σ z_k / 2`; p empiric = `(1 + #{SCI_nul ≥ SCI_real})/(M+1)`. Descriptiv.

## 5. Backtest walk-forward unic (Mașina Timpului)

- Încălzire: primii 100 de pași. Ținte = toate extragerile din pașii `k ≥ 100`; fiecare țintă e prezisă din pașii `< k` (extragerile din aceeași zi primesc aceeași predicție).
- Comparatori: U (`q = 6/49`), B (`π_B ∝ c_j+1`, bilet top-6, ties număr mai mic), R (`π_R ∝ ew_j+0.5`, bilet top-6, ties număr mai mic).
- Legi marginale: `q_j(π) = 6/49 + λ(6π_j − 6/49)`, `λ = min(0.5, λ_max)` unde `λ_max` menține `q_j ∈ [1e-4, 1−1e-4]`. Aceeași regulă pentru QL, B, R.
- Scoruri pe țintă: hits = |bilet ∩ extragere| (QL: varianta 1); log = `Σ_j y_j log q_j + (1−y_j) log(1−q_j)`; Brier = `Σ_j (q_j − y_j)²`. Exces = hits/ținte − 36/49.
- Jumătăți: ținte în ordine cronologică, prima jumătate = `floor(n/2)`.
- Porți de promovare (toate 6 necesare):
  1. `ExcesQL/U ≥ 0.20`;
  2. `hitsQL > hitsB` și `hitsQL > hitsR`;
  3. `logQL − logU > 0` și `logQL − logB > 0`;
  4. `BrierQL < BrierU, BrierB, BrierR`;
  5. în ambele jumătăți: exces > 0 și `hitsQL − hitsB > 0`;
  6. în ambele jumătăți: `logQL − logB > 0`.
- Verdict: `QL_PROMOVAT_EXPLORATORIU` (6/6; tot `positive_claims_allowed=false`, cere confirmare prospectivă separată) altfel `QL_NO_PROMOTION_EXPLORATORY`.
- Descriptiv: hits pe reuniunea celor 3 variante (U așteptat 108/49 pe țintă), distribuția potrivirilor 0..6 față de hipergeometric, p exact sub nul pentru exces (sub extrageri uniforme independente hits-urile oricărui predictor sunt hipergeometrice), pipeline complet pe 64 universuri nule.
- O singură rulare; rezultatul se publică indiferent de verdict; fără tuning după vizualizare. Orice defect tehnic se tratează prin amendament scris și păstrarea încercării inițiale.

## 6. Teste de inginerie (nu sunt porți predictive)

Parser (schemă, refuzuri, paritate CPU/GPU), EP 2×2 (eroare < 1e-8), invarianțe,
distanța hiperbolică, Kuramoto (r→1 la cuplaj mare, nemișcat relativ la K=0),
normalizare Born, MCMC pe instanță mică vs Boltzmann exact (χ², p > 0.001),
invariante variante (exact 3, câte 6 distincte în 1..49, unice), verificator
independent NumPy fp64 fără import din `engine.py`, AppTest Streamlit.

## 7. Produs

UI Streamlit; variantele din Tab 3 sunt minimele energiei modelului, etichetate
permanent „exploratoriu, fără avantaj demonstrat”. Sigiliul temporal SHA-256 al
variantelor se scrie local înainte de extragere; evaluare prospectivă separată,
neconfundată cu OGLINDA. Fără promisiuni de câștig.
