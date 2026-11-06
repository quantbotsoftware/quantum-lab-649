# PROTOCOL XI-P1 — banca de predictoare și backtestul „ca în ajun” pe arhiva RO (planul V12, faza P1)

Scris și sigilat ÎNAINTE de orice cod P1 și de orice calcul P1, împreună cu `xi/PLAN_V12_PREDICTIE.md`.
Autoritate: Mesajele 107/108 și 117–122. `positive_claims_allowed=false`. Calcul clasic exact în virgulă mobilă
dublă (float64) pe CPU (`/usr/bin/python3 -B`, NumPy 2.5.3, `multiprocessing` pe 24 de fire); GPU nefolosit (calculul
are ordinul minutelor pe CPU). Inventarul făcut înainte de protocol (sha-ul bazei, schema, numărul de extrageri pe
joc, versiunile bibliotecilor) nu este experiment de selecție; nicio statistică a numerelor extrase nu a fost calculată.

## 1. Întrebările

- **P1a (primară).** Pentru fiecare joc g ∈ {6/49, 5/40, Joker} și predictor X ∈ {STAT, DRIFT, GAP, FERMI, COMB},
  respinge e-valoarea E_{g,X} ipoteza „extragerile sunt uniforme și independente”, cu corecția Holm la α = 0.01 pe
  cele 15 teste (sau pe câte rămân după §5 Q4)?
- **P1b (descriptivă).** Rezoluția: cea mai mică abatere statică a bilelor detectabilă cu putere ≥ 0.8 pe lungimea
  arhivei 6/49.
- **P1c (descriptivă).** Nimeririle biletului de vârf al fiecărui predictor față de hipergeometric, inclusiv
  frecvența extragerilor cu ≥ 3 numere nimerite (Mesajul 106: „categorii mai mici dar constante”).

## 2. Date (fixate)

- Baza: `${LOTO_RO_ROOT:-.}/loto_romania/data/snapshots/c6bfd021af15d9d6ece6b20d106550e4c8474049e38e9caa3bd1c99d19766adb/loto_romania.sqlite`,
  sha256 `9942abfc25282a715cba70e4f6d17a885a467eaf5fe0440838dc28114003c078` (aceeași ca C2/C3/C4; `as_of` 2026-10-29);
  deschisă numai citire; codul verifică sha-ul și se oprește la nepotrivire.
- Tabelul `draws`, `game` = joc, `draw_kind` ∈ {`regular`, `special`} (rândurile `unknown` dinainte de 1998 sunt
  excluse: format și proveniență neconfirmate). Ordinea: (`draw_date`, regular înaintea special, `draw_key`). Toate
  rândurile selectate se păstrează, inclusiv cele cu `has_source_disagreement=1` (numărul lor se raportează).
- Subjocuri: **6/49** = mulțimea {n1..n6} ⊂ {1..49} (n=49, k=6); **5/40** = mulțimea celor 6 bile {n1..n6} ⊂ {1..40}
  (n=40, k=6; a șasea bilă intră în mulțime, poziția ei nu este modelată); **Joker** = principal {n1..n5} ⊂ {1..45}
  (n=45, k=5) + bila Joker ∈ {1..20} (n=20, k=1).
- Lungimi din inventar: T = 2384 (6/49), 2341 (5/40), 2203 (Joker). Orice abatere (număr, valori în afara
  domeniului, repetiții într-o extragere) oprește producția ⇒ incident, fără reparare improvizată.
- Extragerile se indexează t = 1..T; predicția pentru t folosește NUMAI S_1..S_{t−1} („ca în ajun”).

## 3. Modelele (complet specificate)

Notații pentru un subjoc (n, k): p = k/n; T' = t − 1; c_i = #{s < t : i ∈ S_s}; C_ij = #{s < t : i, j ∈ S_s}.

**Modelul de mulțime CB(w)** (Poisson condiționat): P(S) = ∏_{i∈S} w_i / e_k(w), cu e_k polinomul simetric elementar
de grad k (recurență DP în float64); marginala π_i = w_i·e_{k−1}(w_{−i}) / e_k(w). Pentru k = 1: P({i}) = w_i/Σw.
Toate componentele de mai jos se reduc exact la uniform când ponderile sunt egale.

- **STAT(m)**, m ∈ {100, 400, 1600, 6400} pseudo-extrageri: f_i = (c_i + m·p)/(T' + m), w_i = f_i/(1 − f_i).
- **DRIFT(H, r)**, H ∈ {25, 100, 400} extrageri (timp de înjumătățire), r ∈ {1, 4}: λ = 2^(−1/H);
  c_i^H = Σ_{s<t} λ^(t−1−s)·1[i ∈ S_s]; T^H = Σ_{s<t} λ^(t−1−s); m = r·H; f_i = (c_i^H + m·p)/(T^H + m);
  w_i = f_i/(1 − f_i).
- **GAP(γ)**, γ ∈ {−0.3, −0.1, +0.1, +0.3}: ℓ_i = ultimul s < t cu i ∈ S_s (0 dacă nu există); g_i = (t − 1) − ℓ_i;
  x_i = min(g_i·p/(1 − p), 5) − 1; w_i = exp(γ·x_i). (γ > 0: „restanța”; γ < 0: „repetarea”.)
- **FERMI(m)**, m ∈ {200, 800, 3200}, numai pentru k ≥ 2 (pentru bila Joker FERMI folosește U):
  q = k(k−1)/(n(n−1)); π̂_i = (c_i + m·p)/(T' + m); π̂_ij = (C_ij + m·q)/(T' + m);
  K_ii = π̂_i, K_ij = sqrt(max(π̂_i·π̂_j − π̂_ij, 0)) pentru i ≠ j; K = V·diag(κ)·Vᵀ (descompunere simetrică),
  κ tăiat în [10⁻⁹, 1 − 10⁻⁹]; L = V·diag(ℓ)·Vᵀ cu ℓ_j = κ_j/(1 − κ_j). k-DPP: P(S) = det(L_S)/e_k(ℓ);
  marginala π_i = Σ_j V_ij²·ℓ_j·e_{k−1}(ℓ_{−j})/e_k(ℓ). Interpretare: stare fermionică liberă (determinant Slater)
  cu marginalele de perechi potrivite contractat; poate reprezenta numai respingerea (excesul de atracție → 0).
- **U**: P(S) = 1/C(n, k).

**Mediile bayesiene (predictorii băncii).** Fiecare predictor X este o mixtură cu ponderi a priori ρ_j și ponderi
a posteriori ρ_j(t) ∝ ρ_j·∏_{s<t} P_j(S_s); predicția P_X(S) = Σ_j ρ_j(t)·P_j(S). În fiecare predictor ρ_U = 1/2,
iar 1/2 se împarte în mod egal între familiile aplicabile ale predictorului și apoi în mod egal între componentele
fiecărei familii:
STAT: 4 × 1/8; DRIFT: 6 × 1/12; GAP: 4 × 1/8; FERMI: 3 × 1/6; COMB (toate 17 componente): familia STAT 1/8 (4 × 1/32),
DRIFT 1/8 (6 × 1/48), GAP 1/8 (4 × 1/32), FERMI 1/8 (3 × 1/24). Pentru bila Joker (k = 1) FERMI nu se aplică: FERMI
folosește U pentru bilă (E_bilă = 1), iar COMB împarte 1/2 între STAT, DRIFT, GAP (1/6 fiecare).
Joker: P_X(D, J) = P_X^{princ}(D)·P_X^{bilă}(J), cu mixturi separate pe cele două subjocuri.
Totul în spațiul logaritmic (log-sum-exp), float64.

## 4. Scorurile

- **Primar:** log E_{g,X} = Σ_t [log P_X(S_t) + log C(n, k)] (+ partea bilei la Joker). Identitatea de telescopare
  E_X = Σ_j ρ_j·∏_t [P_j(S_t)/P_U(S_t)] se verifică numeric (Q1d). Consecință exactă: E ≥ 1/2 pe fiecare subjoc.
  p_{g,X} = min(1, 1/E_{g,X}) este p-valoare validă (Ville); corecția Holm la α = 0.01 pe toate testele calificate.
  Pragul celui mai mic p (Bonferroni pe 15 teste): E ≥ 1500.
- **Secundare (descriptive, nu schimbă verdictul):** biletul de vârf la t = cele k numere cu cel mai mare π_i sub P_X
  (egalități: numărul mai mic); la Joker și bila cu cea mai mare probabilitate. Nimeriri h_t = |bilet ∩ S_t|; suma,
  media, media nulă T·k²/n, p-valoarea unilaterală EXACTĂ prin convoluția hipergeometricelor; numărul de extrageri cu
  h_t ≥ 3, așteptarea nulă și p binomial exact; F_XEB = C(n, k)·media_t P_X(S_t) − 1; log E pe cele două jumătăți
  (⌊T/2⌋, rest) și pe sufixul de la 2010-01-01 (un produs de rapoarte condiționate începând la un moment fixat este tot
  e-valoare); ponderile finale ale componentelor; biletul fiecărui predictor pentru extragerea următoare (după
  2026-10-29) — afișat ca ieșire de model, NU emis, NU recomandat.

## 5. Calificarea tehnică (pe date sintetice, înainte de orice citire a extragerilor reale)

Seminții fixe (NumPy PCG64): 20261031 + deplasare declarată în cod. Eșantionare CB exactă (secvențială, prin e_k);
eșantionare k-DPP exactă (algoritmul spectral Kulesza–Taskar).

- **Q1 exactitate:** (a) CB: n=10, k=3, ponderi raționale ⇒ probabilități prin enumerare în `Fraction` față de cod,
  eroare relativă ≤ 10⁻¹²; n=12, k=4: marginale față de enumerare ≤ 10⁻¹²; n=49, k=6, ponderi aleatoare: suma pe
  toate cele 13 983 816 mulțimi = 1 ± 10⁻⁹. (b) k-DPP: n=12, k=4, K aleator cu spectrul în (0,1): Σ det(L_S) = e_k(ℓ)
  relativ ≤ 10⁻¹⁰, marginale ≤ 10⁻¹⁰; n=40, k=6: suma pe toate cele 3 838 380 de mulțimi = 1 ± 10⁻⁸. (c) limita
  uniformă: fiecare componentă la t = 1 dă 1/C(n,k) (relativ ≤ 10⁻¹²) pe fiecare subjoc. (d) telescoparea BMA pe o
  istorie sintetică: |log E secvențial − log Σ_j ρ_j e^{Σ_t log LR_jt}| ≤ 10⁻⁹. (e) log E ≥ −ln 2 − 10⁻¹² pe fiecare
  subjoc, pe toate istoriile sintetice Q3/Q4. (f) DPP pe blocuri: forma închisă P(S) ∝ ∏_b (1 + s·m_b) față de
  det(L_S), n=14, k=4, blocuri de 7, ≤ 10⁻¹²; eșantionatorul k-DPP (n=8, k=3) și eșantionatorul CB (n=8, k=3):
  200 000 de eșantioane fiecare, χ² față de exact, p > 0.001.
- **Q2 predictibilitate:** pe o istorie sintetică 6/49, la t₀ ∈ {500, 1200, 2000}, înlocuirea extragerilor ≥ t₀ cu
  altele aleatoare lasă bit-identice toate log-probabilitățile componentelor și biletele pentru t ≤ t₀.
- **Q3 nul:** 100 de istorii uniforme per joc (lungimile T de mai sus): pentru fiecare predictor, fracția cu E ≥ 20
  trebuie să fie ≤ 0.10 (Ville dă ≤ 0.05; depășirea ⇒ defect de cod). Se raportează cuantilele lui log E și fracția
  cu E ≥ 1500.
- **Q4 detectarea unui semnal grosier propriu** (6/49, T = 2384, 20 de istorii per semnal):
  Σ_STAT: CB cu cote 1.25 pentru i ≤ 24 și 0.8 pentru i ≥ 25; Σ_DRIFT: epoci de 150 de extrageri, în fiecare epocă
  o submulțime aleatoare de 24 de numere are cota 1.5, restul 1/1.5; Σ_GAP: CB secvențial cu w_i = exp(0.6·x_i(t))
  (trăsătura GAP pe istoria generată); Σ_FERMI: k-DPP cu L = I + s·B, B bloc-diagonală de unu pe blocurile de 7 numere
  consecutive (1–7, …, 43–49), s = cel mai mic din {0.5, 1, 2, 4, 8, 16} cu KL(P_s ‖ U) ≥ 0.05 nați pe extragere
  (calcul exact prin ocupările blocurilor). **Poarta:** familia X atinge E_X ≥ 1500 în ≥ 16 din 20 de istorii sub Σ_X;
  COMB trebuie să atingă E ≥ 1500 în ≥ 16/20 sub Σ_STAT. O familie care pică este `NOT_QUALIFIED`: exclusă din rularea
  reală și din COMB (partea ei se redistribuie egal între familiile calificate; ρ_U rămâne 1/2), iar numărul de
  teste Holm scade corespunzător. Fără salvare prin alți parametri.
  Descriptiv: matricea predictor × semnal (mediana log E) și curba de putere STAT pentru cote 1+δ / 1/(1+δ),
  δ ∈ {0.03, 0.05, 0.10, 0.15} (20 de istorii fiecare): fracția cu E ≥ 1500 ⇒ rezoluția (P1b).
- Un eșec Q1–Q3 este defect tehnic: se corectează codul, se consemnează incidentul (fișierele încercării păstrate),
  se reiau testele; extragerile reale nu au fost citite, deci nu există efect de selecție. După PASS Q1–Q4 codul se
  sigilează (`xi/p1/SIGILIU_COD_P1.json`, fișiere 0444) ÎNAINTE de citirea extragerilor reale.

## 6. Producția (o singură rulare)

`xi/p1/banca.py productie` (cod sigilat): verifică sha-ul bazei și al codului, citește extragerile, calculează tot și
scrie în `xi/rezultate/P1/`: `p1_pas.jsonl` (per joc și t: log-probabilitățile componentelor și predictorilor,
biletele, nimeririle), `P1_REZULTATE.json`, `RAPORT_P1_CIFRE.md`; toate 0444. Refuză repetarea dacă ieșirile există.

## 7. Verificarea independentă

`xi/p1/verifica_p1.py`, fără niciun import din `banca.py`: recitește baza, recalculează numărările, e_k prin
înmulțire de polinoame (convoluții iterate), k-DPP prin construcția proprie, mixturile, log E, Holm, biletele,
nimeririle și p-valorile exacte; toleranțe 10⁻⁸ pe log-probabilitățile pe pas și 10⁻⁶ pe log E agregat. Scrie
`VERIFICARE_P1.json` (PASS/FAIL). Raportul final `RAPORT_P1.md` se scrie din artefacte.

## 8. Interpretări fixate

- Nicio respingere Holm ⇒ **`P1_NICIUN_CANDIDAT`**: „pe arhiva RO, niciun predictor din bancă nu bate uniformul”;
  se raportează rezoluția (P1b). P2 continuă (alte urne, alte aparate).
- Respingeri ⇒ **`P1_CANDIDATI`** (lista): numai candidați, arhiva RO fiind explorată de proiect; urmează P2 și P3.
- Nimeririle (P1c) nu schimbă verdictul. Niciun rezultat nu autorizează afirmații de avantaj sau profit;
  `positive_claims_allowed=false`.

## 9. Distinctivitate și precedente atribuite

Banca folosește ipoteze generice (abatere statică, derivă, memorie de tip restanță/repetare, respingere de perechi),
nu modelele închise ale proiectului (QL649, BO649, WU649, GL649 și familiile din `next_candidate/predictie_numere/`),
pe care nu le rerulează. STAT este înrudit cu reperele B/I folosite anterior ca comparatori (frecvențe contractate);
GAP este înrudit conceptual cu pistele de reapariție închise (cursa de reapariție, accesibilitatea temporală), dar
este trăsătura standard simplă a „restanței”, cu parametri fixați acum, fără statisticile acelor piste. FERMI este
P-F din planul v10 (Ψ-PRED), nerulat până acum. Precedente: Poisson condiționat (Hájek 1964; Chen, Dempster & Liu
1994), Dirichlet–multinomial, uitarea exponențială, procesele punctuale determinantale (Macchi 1975; Kulesza & Taskar
2012), evaluarea prequențială și mixturile bayesiene (Dawid 1984), inegalitatea lui Ville (1939) și e-valorile
(Shafer & Vovk; Grünwald, de Heide & Koolen; Vovk & Wang 2021). Contribuția locală: banca exactă, cu normalizare
exactă, pierdere mărginită (E ≥ 1/2) și test valid oricând, aplicată celor trei jocuri RO, plus rezoluția publicată.
