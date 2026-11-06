# PROTOCOL XI-C3 — optimizatorul de portofoliu sub buget (planul V11, faza E)

Scris și sigilat ÎNAINTE de orice cod C3 și de orice calcul C3. Autoritate: Mesajele 107/108/111 și cererea din
2026-10-31 (faza E, cu lecția C2: „EV supraestimat când vânzările prognozate sunt mici față de fonduri; raportează κ”).
`positive_claims_allowed=false`. C3 NU este un predictor de numere: dacă extragerile sunt corecte, fiecare bilet are
aceeași șansă; C3 alege doar CUM se împarte un buget între bilete (valoare așteptată după modelul mulțimii al produsului,
autoîmpărțire, probabilitatea de a câștiga ceva). Calcul clasic (CPU + GPU, CuPy). „Cuantic” = recoacere cuantică
SIMULATĂ (Monte Carlo pe integrala de drum, Suzuki–Trotter), pe hardware clasic; fără avantaj cuantic revendicat.
Inventarul făcut înainte de protocol (sha-uri, formate, API-ul produsului, existența CuPy 14.2 în `/usr/bin/python3`)
nu este experiment de selecție.

## 1. Întrebările

**C3a.** Pentru un buget B pe extragere (K = ⌊B/preț⌋ bilete distincte), care portofoliu S maximizează
F_μ(S) = EV(S) + μ·P_any(S), unde EV(S) este valoarea așteptată EXACTĂ a portofoliului (cu autoîmpărțirea între
propriile bilete) după modelul produsului, iar P_any(S) probabilitatea EXACTĂ ca măcar un bilet să câștige un premiu
(orice categorie)? μ ≥ 0 [lei per unitate de probabilitate] este schimbul declarat între valoare și regularitate
(μ = 1000 ⇔ +1 punct procentual de P_any valorează 10 lei). Se publică frontiera (EV, P_any) pe o grilă fixă de μ.

**C3b.** Găsește optimizatorul (recoacere cuantică simulată + recoacere clasică + tempering paralel, pe GPU) optimul
exact al problemei QUBO pe instanțe mici verificate prin enumerare completă (poarta G4 a planului)?

**C3c.** Cât de mult depind cifrele de lecția C2: κ la starea folosită și o variantă de sensibilitate „fonduri ∝ vânzări”.

## 2. Date și stare (fixate)

- Baza: `${LOTO_RO_ROOT:-.}/loto_romania/data/snapshots/c6bfd021af15d9d6ece6b20d106550e4c8474049e38e9caa3bd1c99d19766adb/loto_romania.sqlite`,
  sha256 `9942abfc25282a715cba70e4f6d17a885a467eaf5fe0440838dc28114003c078` (aceeași ca C2/C4); codul verifică sha-ul.
- Starea: ținta 2026-11-01 (toate 3 jocurile), construită ca în testul K2 al C2: modelul 6/49 estimat pe toate extragerile
  observate (`fit`, ponderi de timp, ridge 1.0), 5/40 și Joker prin transferurile produsului (`estimate_pi` pentru Joker),
  `ceiling.market_state` și `ceiling.ev_all_tickets` neschimbate. Fidelitatea se verifică (T1) față de sigiliile
  `quantum_limit/prospectiv/{649,540,joker}/2026-11-01/sigiliu_20261029T2140{19,41}Z.json` / `…214102Z.json`.
- Designurile C1 (numai ca bilete candidate): `xi/rezultate/C1/designuri/SG324Q.json` (`b8305030…`) și `JS135Q.json`
  (`add35bb7…`). Rezultatele C2 etapa 1 (numai câmpurile ex-ante `state.sales`, `state.funds`): `etapa1_649.jsonl`
  (`d7cd6639…`), `etapa1_540.jsonl` (`209a90ea…`), `etapa1_joker.jsonl` (`72162919…`).
- Prețuri: 6/49 8 lei, 5/40 5 lei, Joker 7 lei. Bugete de producție: B ∈ {40, 100, 500} lei ⇒
  K = 5/12/62 (6/49), 8/20/100 (5/40), 5/14/71 (Joker).
- Portofoliul pentru 2026-11-01 este o ieșire de model, ca biletul-limită al produsului: NU este emis, înregistrat în
  vreun lanț sau decontat (registrul pe hârtie este faza F, separată). Nicio evaluare prospectivă în C3.

## 3. Obiectivul exact

Pentru jocul g: stările extragerii ω ∈ Ω_g cu ponderi uniforme w_ω (6/49: cele C(49,6) mulțimi; Joker: C(45,5)×20
perechi (D, J*); 5/40: C(40,6) mulțimi × 6 poziții ale bilei a șasea), categoria cat(s, ω) a biletului s (regulile
produsului/C2 §6), fondurile A_c ale categoriilor cu împărțire, premiul fix v_c (6/49 IV) și intensitatea mulțimii
λ_c(ω) = N × masa mulțimii care ar împărți categoria c la ω (exact ca în produs: 6/49 N·q_k(D); Joker N·π_{J*}·Q_h(D)
pentru categoriile cu Joker potrivit și N·(1−π_{J*})·Q_h(D) altfel; 5/40 I N·p(D∖y), II N·(q_5(D) − p(D∖y)), III N·q_4(D)).
Ipoteza produsului se păstrează: biletele mele se adaugă celor N ale mulțimii, co-câștigătorii mulțimii ~ Poisson(λ).

- m_c(ω, S) = #{s ∈ S : cat(s, ω) = c}.
- **EV(S) = Σ_ω w_ω [ Σ_{c cu împărțire} A_c · G(m_c, λ_c(ω)) + Σ_{c fix} v_c · m_c ]**, cu
  G(m, λ) = E[m/(m+W)], W ~ Poisson(λ) = m ∫₀¹ t^{m−1} e^{−λ(1−t)} dt, G(0, ·) = 0, G(1, λ) = `expected_share(λ)`.
  Calcul: recurența I_{m+1} = (1 − m·I_m)/λ din I_1 = −expm1(−λ)/λ pentru λ ≥ m; cuadratură Gauss–Legendre cu 64 de
  noduri pe ∫₀¹ (1−u)^{m−1} e^{−λu} du pentru λ < m.
- **P_any(S) = Σ_ω w_ω · 1[∃ s ∈ S : cat(s, ω) definită]** — nu depinde de modelul mulțimii (numai de corectitudinea
  extragerii). Se raportează și P(≥ 1 bilet în categoria c) și E[număr de bilete câștigătoare] = K·p_any.
- F_μ(S) = EV(S) + μ·P_any(S). ρ(S) = EV(S)/(K·preț).
- Evaluatorul exact enumeră TOATE stările pe GPU (biletele ca măști de biți, `popcount`).

## 4. Problema QUBO (surogatul de ordinul 2)

Pentru orice pereche de bilete distincte EV({s, s'}) = EV(s) + EV(s') − Σ_c A_c Σ_ω w_ω 1[ambele în c] δ(λ_c(ω)), cu
δ(λ) = 2g(λ) − G(2, λ) (exact, deoarece m_c ≤ 2), iar P_any({s, s'}) = 2p_any − P2(s, s'). Surogatul:

F̃_μ(S) = Σ_{s∈S} [EV(s) + μ·p_any] − Σ_{s<s'∈S} [ Σ_c D̃_c(s, s') + μ·P2(s, s') ],

- EV(s) = EV-ul exact al produsului (`ev_all_tickets`); p_any este același pentru toate biletele unui joc.
- P2(s, s') = P(ambele câștigă ceva) și P2_c(s, s') = P(ambele în categoria c): EXACTE, prin numărare combinatorică pe
  structura perechii (suprapunerea t = |s ∩ s'| și, la Joker, egalitatea numerelor Joker); 5/40 II: nenul numai la t = 4,
  egal cu 4/(6·C(40,6)).
- D̃_c(s, s') = A_c · P2_c(s, s') · δ(λ̄_c), λ̄_c = (λ_c^eff(s) + λ_c^eff(s'))/2, unde λ_c^eff(s) = g⁻¹(comp_c(s)/(A_c·P_c))
  este intensitatea efectivă a biletului s în categoria c, obținută din componenta produsului comp_c(s) (P_c =
  probabilitatea categoriei pentru un bilet). **Aproximare declarată:** δ la starea ω este înlocuit cu δ la intensitatea
  efectivă; eroarea pe perechi se măsoară (T4c) și eroarea pe portofoliile finale se raportează (F − F̃).
- Energia QUBO (minimizată, cu Σ x_i = K): E(x) = −Σ_i a_i x_i + Σ_{i<j} Q_ij x_i x_j, a_i = EV(s_i),
  Q_ij = Σ_c D̃_c + μ·P2 (constanta μ·K·p_any omisă).
- **Mulțimea candidată (pool)**, M = 4096 bilete distincte, fără bilete marcate `patterned`: biletele designului C1 al
  jocului (6/49 SG324Q, 324; Joker JS135Q, 135; 5/40 niciunul), apoi biletele cu cel mai mare EV (în varianta de fonduri
  respectivă), în ordinea EV descrescătoare (egalitate: indicele de enumerare mai mic), până la M. La Joker, biletul
  este perechea (numere, Joker). Optimul este relativ la pool (limită declarată).

## 5. Optimizatoarele (GPU, CuPy) și comparatorii

Toate folosesc aceeași mutare care păstrează cardinalul: un bilet din S iese, un bilet din pool \ S intră (alegeri
uniforme, propunere simetrică), ΔE = a_i − a_j + h_j − Q_ij − h_i cu câmpul h_x = Σ_{l∈S} Q_xl actualizat incremental.
Scala energiei: s_E = std(a pe pool) + μ·mediana(P2 pe 20 000 de perechi aleatoare din pool, seed fix).

1. **SQA** — Monte Carlo pe integrala de drum pentru H = −Γ Σ_i σ_i^x + E(σ^z) (Kadowaki–Nishimori 1998; Santoro,
   Martoňák, Tosatti, Car 2002; Martoňák, Santoro, Tosatti 2002), adaptat la restricția de cardinal prin mutările de
   schimb în fiecare felie: P felii Trotter, temperatura T, cuplajul între felii J⊥ = −½·ln tanh(Γ/(P·T)), Γ liniar de la
   Γ₀ la Γ₁; acceptare Metropolis cu −ΔE/(P·T) + J⊥·Δ(Σ σ^k σ^{k+1}); feliile pare/impare actualizate alternativ (fără
   cursă între felii vecine). 32 de lanțuri independente.
2. **SA** — recoacere clasică (Kirkpatrick et al. 1983), 1024 de lanțuri, T geometric de la T₀ la T₁.
3. **PT** — tempering paralel (Swendsen–Wang 1986; Geyer 1991; Hukushima–Nemoto 1996), 32 de lanțuri × 32 de
   temperaturi geometrice între T_min și T_max, schimburi între temperaturi vecine la fiecare 10 pași.
4. **Greedy** — adăugare succesivă a biletului cu cel mai bun câștig marginal al surogatului.
5. **Exact** (numai instanțe mici) — enumerarea completă a celor C(M_s, K) submulțimi pe GPU.

Pași: n = 20 000 + 200·K pentru SQA, SA și PT. Fiecare lanț ține cea mai bună stare văzută. **Selecția finală:** cele
L = 32 de stări distincte cu cea mai mică energie a surogatului (din SQA ∪ SA ∪ PT ∪ greedy ∪ comparatorul C_EV) se
evaluează EXACT; portofoliul raportat este cel cu F_μ exact maxim (egalitate: energia surogatului mai mică).

**Comparatori** (pe fiecare joc × buget × variantă): C_EV — cele K bilete cu EV maxim din pool (ce ar face un utilizator
cu lista „best” a produsului); C_RND — 64 de portofolii aleatoare de K bilete nemarcate din toată enumerarea (seed fix),
media și cuantilele lui EV și P_any; C_DES — primele K bilete ale designului C1 ordonate după EV (6/49, Joker); marginea
de reuniune K·p_any pentru P_any și Σ EV(s) pentru EV.

**Calibrarea parametrilor** (înainte de sigilarea codului; publicată; instanțe separate de G4 și de producție):
SQA (P, P·T/s_E) ∈ {16, 32} × {0.5, 1.0}, Γ₀ = 2·s_E, Γ₁ = 10⁻³·s_E; SA T₀/s_E ∈ {1, 3} × T₁/s_E ∈ {10⁻², 10⁻³};
PT T_max/s_E ∈ {1, 3}, T_min = 10⁻³·s_E. Instanțe de calibrare: (a) mici: 3 jocuri × μ ∈ {50, 3000} × (M_s, K) ∈
{(40, 5), (64, 5)}, sub-pooluri cu seed 77 000 + indice; (b) de producție: 3 jocuri × B ∈ {100, 500} × μ ∈ {50, 3000}.
Regula de alegere, separat pentru SQA/SA/PT: (1) numărul maxim de optime exacte pe (a); (2) apoi media minimă a energiei
normalizate pe (b), (E − E_best,b)/s_E, cu E_best,b cea mai bună energie găsită de oricare configurație; (3) apoi
configurația listată prima. Parametrii aleși intră în codul sigilat (`xi/c3/SIGILIU_COD_C3.json`).

## 6. Varianta de sensibilitate (lecția C2) și κ

- **κ (definiția C2):** κ = (vânzări prognozate / alocarea mediană a categoriei de referință: 6/49 III, 5/40 III,
  Joker VIII), normalizat la mediana aceluiași raport pe rândurile C2 `etapa1_<joc>.jsonl` evaluate. Se raportează κ
  la starea 2026-11-01, cuantila lui în distribuția C2 și intervalul C2 (bins din `DIAGNOSTIC_POSTHOC_C2.json`) în care cade,
  cu raportul ex-ante/realizat observat acolo (descriptiv).
- **Varianta S („fonduri ∝ vânzări”), numai ca analiză de sensibilitate, NU schimbare a produsului:** pentru fiecare
  categorie cu împărțire, fără jackpot, alocarea nouă devine alloc_c · κ_c^rec, cu κ_c^rec = (vânzări / alloc_c) împărțit
  la mediana aceluiași raport pe ultimele 104 rânduri C2 evaluate ale jocului; reportul (carried) rămâne; jackpotul și
  premiile fixe rămân. EV-urile se recalculează cu `ev_all_tickets` pe starea modificată; pool-ul se reconstruiește.
  Varianta P = produsul neschimbat.

## 7. Porți de corectitudine (înainte de calibrare, G4 și producție)

- **T1** (fidelitate): starea 2026-11-01 reproduce sigiliile produsului (EV mediu și EV-ul limitei, rel ≤ 1e-9; același
  bilet-limită; aceeași dată țintă) la toate 3 jocurile.
- **T2** (G exact): G(m, λ) față de seria Poisson calculată cu `decimal` (50 de cifre) pe grila m ∈ {1..8, 16, 64},
  λ ∈ {0, 1e-8, 1e-3, 0.1, 0.5, 1, 2, 5, 10, 50, 100, 1e3, 1e4, 1e5}: rel ≤ 1e-12; G(1, ·) = `expected_share` (rel ≤ 1e-14).
- **T3** (jocuri mici, implementare naivă independentă în Python pur, cu sume Poisson): 6/49-mic (n = 10, m = 6),
  5/40-mic (n = 9, m = 5, r = 6), Joker-mic (n = 8, m = 5, J = 3), modele ale mulțimii cu θ aleator (seed fix):
  (a) evaluatorul pe bilete singure = `ev_all_tickets` al produsului pe aceeași formă, toate biletele, rel ≤ 1e-10;
  (b) EV și P_any pe 200 de portofolii aleatoare (K = 2..6) = implementarea naivă, rel ≤ 1e-10;
  (c) P2 și P2_c prin numărare = enumerarea naivă, egalitate exactă (fracții), pe toate perechile.
- **T4** (jocuri reale): (a) evaluatorul pe biletul-limită + 50 de bilete aleatoare/joc = `ev_all_tickets`, rel ≤ 1e-9;
  (b) P2 și P2_c prin numărare = numărarea directă a stărilor pe GPU, pe 200 de perechi din pool/joc, egalitate exactă;
  (c) descriptiv: eroarea surogatului pe 200 de perechi/joc, D̃ − [EV(s) + EV(s') − EV({s, s'})].
- **T5** (contabilitatea optimizatoarelor): la finalul fiecărei rulări, energia incrementală a fiecărui lanț = energia
  recalculată complet, |Δ| ≤ 1e-9·max(1, s_E·K); aserție în cod la fiecare rulare (calibrare, G4, producție).
- **T6** (enumeratorul exact): pe o instanță minusculă (M_s = 10, K = 3) = enumerarea cu `itertools` în Python.

Orice eșec: incident publicat, corecție tehnică, testele reluate; fără ajustări după rezultat.

## 8. Poarta G4 (optim exact pe instanțe mici) — după sigilarea codului

36 de instanțe: 3 jocuri × μ ∈ {0, 1000, 100 000} × (M_s, K) ∈ {(24, 4), (40, 5), (48, 6), (64, 5)}; sub-pooluri de M_s
bilete extrase uniform din pool-ul de producție al variantei P, seed 20 261 031 + indice. Optimul exact al surogatului
prin enumerare completă. „Găsit” dacă energia celei mai bune stări a ansamblului (SQA ∪ SA ∪ PT ∪ greedy) ≤
E_opt + 1e-9·max(1, |E_opt|). **G4 PASS ⇔ 36/36.** Se raportează separat ratele SQA, SA, PT și greedy (descriptiv; nu
se afirmă superioritatea vreunei metode, nici avantaj cuantic). Dacă G4 pică, producția rulează totuși, iar rezultatele
poartă eticheta „optim neconfirmat”, fără reglaje de salvare.

## 9. Producția (unică)

3 jocuri × 3 bugete × μ ∈ {0, 100, 1000, 10 000, 100 000, 10⁸} în varianta P (10⁸ ≈ „numai regularitate”, EV doar ca
departajare) + μ ∈ {0, 1000, 10⁸} în varianta S = 81 de instanțe, seed 20 261 031 + 1000·cod_joc + 100·i_buget + i_μ
(+ 50 pentru S). Fiecare instanță se scrie incremental (JSONL) și se calculează o singură dată; o întrerupere tehnică se
reia de la ultima instanță terminată. GPU cedat (pauză internă, fără timere de sistem) în ±15 min de 06:20, 10:20, 13:20
și 21:40 UTC; producția nu rulează în 2026-11-01 între 13:00 și 14:00 UTC (C1).

Ieșiri (`xi/rezultate/C3/`, 0444 la final): `teste/`, `calibrare/`, `G4.jsonl`, `productie.jsonl`, `C3_REZULTATE.json`,
`RAPORT_C3_CIFRE.md` (automat), `RAPORT_C3.md` (redactat). Pe instanță: biletele, EV exact, ρ, P_any, P pe categorii,
F_μ exact și surogat (și diferența), metoda care a găsit portofoliul, timpi, comparatorii, κ.

## 10. Interpretări fixate acum

- ρ < 1 este așteptat peste tot. Dacă ρ ≥ 1 apare la vreo instanță, se raportează ca „suspect de artefact al modelului
  de fonduri (κ mic, lecția C2)” și se compară cu varianta S; nicio afirmație de valoare pozitivă.
- P_any este exact dacă extragerea e corectă și nu depinde de modelul mulțimii; frontiera arată prețul regularității
  (cât EV se cedează pentru +P_any). Ea nu schimbă pierderea pe termen lung și nu face jocul profitabil.
- Garanția „câștig la fiecare extragere” cere un design complet (C1: 135 de bilete Joker, 324 la 6/49); sub buget,
  P_any < 1 și se raportează exact.
- Comparația SQA ↔ SA ↔ PT este descriptivă, pe acest problem și acest buget de pași; nu se generalizează.

## 11. Abatere declarată de la plan și igienă

- Planul spune „optimizatorul de portofoliu în produs”. C3 se livrează ca modul separat `xi/c3/` cu linie de comandă
  (`portofoliu.py`, buget și μ arbitrare, ieșire JSON), care importă `quantum_limit` numai pentru citire. Produsul
  `quantum_limit` NU se modifică acum (fișiere înghețate în DL v2 și C1 de duminică); integrarea în interfață intră în
  faza H (ecranul „Strategii”), cu protocol separat.
- Rulare: `/usr/bin/python3 -B` cu `PYTHONDONTWRITEBYTECODE=1` (INCIDENT_S35_02); DL v2 reverificat la închidere.
- Cod: `xi/c3/portofoliu.py` (evaluator, surogat, optimizatoare, comenzi `teste`, `calibrare`, `g4`, `productie`,
  `raport`, `optimizeaza`). Scris după sigilarea acestui protocol.
