# PROTOCOL TU3-P1 — TRI-UNIVERSE CONVERGENCE v3.0, modulul J (Joker, sistem bipartit)

Sesiunea 2026-10-26 (start ~15:36Z), cererea utilizatorului „Mesajul 25” (supliment QL649).
Scris și sigilat ÎNAINTE de orice cod sau calcul al modulului. Nu atinge arhiva reală în această sesiune.

## 0. Încadrare onestă și abateri declarate

- Calcul CLASIC (PyTorch float64, CUDA pe RTX 5060 Laptop; fallback CPU jurnalizat). „Stare”, „spațiu Hilbert”,
  „entanglement”, „holonomie”, „rupere spontană de simetrie” sunt vocabular matematic aplicat unor tabele de
  co-apariție; nicio pretenție fizică, niciun avantaj cuantic. `positive_claims_allowed=false`.
- Produsul TU3 este un motor DESCRIPTIV + generator de variante de energie minimă. Variantele NU sunt predicții.
  Orice scor pe istoria reală cere un protocol de backtest separat, sigilat înaintea rulării (nu face parte din P1).
- `engine.py` și `parser.py` sunt codul sigilat al backtestului QL649 (handoff 150232Z: „NEMODIFICATE”). Ele NU se
  rescriu. Polimorfismul se implementează ADITIV în `tu3/` (module noi care pot importa funcții generice din
  `engine.py`), iar `app.py` primește aditiv selectorul de mod. Calea 6/49 rămâne byte-identică.
- Abatere de date (verificată 15:37Z, inventar, nu selecție): `extrageri_540.jsonl` și `extrageri_joker.jsonl` NU
  există nici intern, nici pe SSD-ul `LOTO_SSD` (montat 15:40Z; acolo doar copii mai vechi, până la 2026-10-01).
  Sursa reală este snapshot-ul read-only `loto_romania/data/snapshots/5843ccc6…/loto_romania.sqlite`
  (sha256 `87ec292e…8e05`): 540 = 2489 extrageri, joker = 2201 extrageri (până la 2026-10-22). Sesiunea de parser
  (modulul P) va EXPORTA cele două JSONL în `tu3/date/` cu proveniență (hash DB, interogare), fără a scrie în DB.
- Abatere de regulă de joc: în arhivă, TOATE cele 2489 extrageri Loto 5/40 au **6 numere distincte din 1..40**
  (biletul are 5 numere; categoria I = primele cinci, II = cinci din șase — `quantum_limit_data.py`). Validarea
  „exact 5 numere” din cerere ar respinge 100% din arhivă; modulul P va valida 6 numere distincte 1..40 la extragere și
  5 numere la variantă/bilet. Joker: 5 distincte din 1..45 + 1 Joker din 1..20 (conform cererii și arhivei).

## 1. Ordinea modulelor (fiecare = checkpoint separat, predare la final)

J (acest protocol) → P (parser multi-joc + export JSONL) → E40 (motor 5/40, n = 40, variante de 5) →
E-J integrare (Joker în motorul polimorfic, variante 5+1) → UI (selector global, 12 taburi × 3 moduri) →
validare (sintetic, γ = 1/2) → server 127.0.0.1:8649. Fiecare modul nou primește amendament/protocol propriu înainte de cod.

## 2. Modulul J — definiții (fixate)

Notații: n = 45, m = 20, k = 5, T extrageri. X ∈ {0,1}^{T×n} (k unități pe rând), Y ∈ {0,1}^{T×m} (o unitate).
Toate statisticile sunt NEPONDERATE (fără timp de înjumătățire, niciun parametru liber de recență).

1. Tensor comun: `P_ja = Σ_t X_tj Y_ta / (kT)`; marginale `p = P·1`, `q = Pᵀ·1` (Σp = Σq = 1).
   Construit pe GPU prin `index_add`/`bincount` pe indicii plați (b, j, a), lot B de universuri.
2. Cross-covarianță: `C = P − p qᵀ`; reziduul normalizat `K̃_ja = C_ja / √(p_j q_a)` (0 unde p_j q_a = 0).
3. Stare bipartită `|Ψ⟩ = Σ_ja √P_ja |j⟩⊗|a⟩` în `H_Main ⊗ H_Joker` (C^45 ⊗ C^20). Coeficienți Schmidt `s` =
   valorile singulare ale matricei 45×20 `√P` (SVD batch CUDA), Σs² = 1. Entropia de entanglement
   `S_E = −Σ s² ln s²`; numărul Schmidt `K_S = 1/Σ s⁴`. Informația mutuală `I = Σ P ln(P/(p q))` (termen neliniar).
4. Holonomia Joker: fazele Z_20 `φ_a = 2π(a−1)/m`. Pentru nodul principal j: `h_j = Σ_a P_ja e^{iφ_a} / p_j`
   (faza `θ_j = arg h_j`, modulul `r_j = |h_j|`); deplasarea de simetrie `Δ_j = Σ_a C_ja e^{iφ_a} / p_j`
   (= h_j − Σ_a q_a e^{iφ_a}). Parametrul de ordine SSB `Φ = Σ_j p_j |Δ_j|²`. Statistica Rayleigh nodală
   `Z_j = n_j |Δ_j|²`, `n_j = Σ_t X_tj`. Faza de rotație a nodului j: `ϑ_j = arg Δ_j` (0 dacă Δ_j = 0).
5. Câmpul urnei principale (45-dim): `ψ_j = √p_j e^{iϑ_j}`; interferența `I_jl = 2 Re(ψ_j ψ̄_l)`;
   cuplajul indus de entanglement `G = K̃ K̃ᵀ` (45×45, diagonala zero); starea Born
   `P_B ∝ |ψ + η Ĝ ψ|²`, `Ĝ = G / max_j Σ_l |G_jl|`, η = 0.5 (aceeași valoare ca `interference_eta` QL649).
6. Disc Poincaré: `ρ_j = ln(1 + Z_j)`, `z_j = tanh(ρ_j/2) e^{iϑ_j}` (centru = simetric, margine = rupt);
   distanțe hiperbolice d_H; δ-Gromov pe TOATE cele C(45,4) = 148.995 cvadruple (GPU), `δ_rel = 2δ/diam`;
   curbura Forman pe graful top-k (k = 6, ca `forman_k` QL649) al lui G pozitiv: `F_e = 4 − deg_u − deg_v`, medie nodală.
7. Kuramoto condus de holonomie (Adler + câmp mediu), integrat RK4 pe GPU în lot peste κ:
   `dθ_j/dt = ω_j + κ |Δ_j| sin(ϑ_j − θ_j) + (K_m/n) Σ_l sin(θ_l − θ_j)`, `ω_j = n p_j − 1`,
   K_m = 0 (martor analitic) și K_m = 2.0 (= `kur_K` QL649), dt = 0.05, 400 pași, θ(0) = 0,
   κ = κ̃ · std(ω)/mean|Δ|, κ̃ ∈ logspace(−1, 2, 31). Ieșiri: R(t) = |⟨e^{iθ}⟩|, fracția blocată
   `L(κ)` = noduri cu |dθ/dt| < 1e-3 la final, aliniere `A = |Σ_j p_j e^{i(θ_j − ϑ_j)}|`.

## 3. Martori analitici (cod de test, trebuie să treacă exact; toleranță 1e-10 în float64)

- W1 produs: `P = p⊗q` arbitrar → C = 0, S_E = 0, rang Schmidt 1, I = 0, Δ = 0, Φ = 0.
- W2 corelare maximă: `P_ja = 1/20·[j = a]` (a = 1..20) → s² = 1/20 fiecare, S_E = I = ln 20, K_S = 20.
- W3 holonomie pură: nodul j apare numai cu Joker a(j) → θ_j = φ_{a(j)}, r_j = 1.
- W4 covarianță Z_20: deplasarea etichetelor Joker a → a+s (mod 20) rotește toate θ_j, ϑ_j cu 2πs/20; S_E, I, Φ, Z,
  r invariante.
- W5 echivarianță la permutarea etichetelor principale: S_E, I, Φ invariante; Z, r permutate.
- W6 GPU = CPU (float64) la 1e-10 pe același input.
- W7 one-hot: rânduri X sumă 5, Y sumă 1; tensorul din `index_add` = tensorul din einsum.
- W8 δ-Gromov: metrică de arbore (stea) → δ = 0; ciclul C4 (laturi 1, diagonale 2) → δ = 1.
- W9 Adler (K_m = 0): fracția blocată numerică = numărul analitic `#{j: |ω_j| ≤ κ|Δ_j|}/n` (fără cazuri la frontieră
  ±2%), iar nodurile blocate converg la `ϑ_j + arcsin(ω_j/(κ|Δ_j|))` (1e-4).
- W10 lot: universurile calculate în lot = calculate unul câte unul.

## 4. Verificare de putere sintetică (γ = 1/2) — praguri fixate înainte de rulare

Generator GPU: Joker uniform 1..20; cu probabilitatea γ extragerea principală e eșantionată Gumbel-top-5 din logiții
`β cos(ψ_j − φ_a)`, `ψ_j = 2π(j−1)/45`, β = 1; altfel 5-submulțime uniformă. T = 2201 (lungimea arhivei Joker).
Semințe fixe: null 649001, γ = 1/2 649002, γ = 1/8 649003.
- Nul: B0 = 4096 universuri (γ = 0) → praguri la cuantila 0.99 pentru I, S_E, Φ (fiecare separat).
- Putere: B1 = 1024 universuri la γ = 1/2 → **PASS dacă puterea ≥ 0.90 pentru FIECARE dintre I, S_E, Φ**.
- Control: B2 = 1024 universuri noi γ = 0 (sămânța 649004) → **PASS dacă rata fals-pozitivă ≤ 0.02 pentru fiecare**.
- Descriptiv (fără prag): γ = 1/8, B = 1024.
Verdict J: `J_PASS` numai dacă W1–W10 trec și ambele porți de putere/control trec; altfel `J_FAIL`, publicat ca atare,
fără retuning (β, γ, T, praguri nu se schimbă după rezultat). Puterea pe sintetic NU spune nimic despre arhiva reală.

## 5. Artefacte

`tu3/joker_entanglement.py`, `tu3/tests/test_joker_entanglement.py`, `tu3/putere_joker.py`,
`tu3/rezultate/J/PUTERE_J.json` (+ hash cod), apoi predare QL649 (pereche nouă, același UTC).
