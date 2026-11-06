# PREINREGISTRARE CS649 — „Caruselul seturilor” (rotație deterministă ipotetică a seturilor de bile/urnelor)

Versiune protocol: `CS649-P1`. Scris și sigilat (SHA-256 în `SIGILIU_PROTOCOL_CS649.json`)
ÎNAINTE de scrierea oricărui cod CS649 și înainte de orice calcul CS649 pe date reale, sintetice
sau construite (singurele calcule anterioare sunt aritmetica de mână a formulelor din §2.1 și
constantele exacte ale martorilor din §4, obținute din formulele închise, fără model și fără date).
Ipoteză NOUĂ și DISTINCTĂ în pista QL649. Nu salvează, nu repară și nu re-parametrizează QL649
(închis `QL_NO_PROMOTION_EXPLORATORY`, 0/6), BO649 (închis 0/6), WU649 (`WU_NOT_QUALIFIED`, cod
NEVALIDAT, neexecutat aici), GL649 (închis 2/6; nicio structură de etichete nu este folosită aici),
SE649 (închis 1/6; nicio partiție calendaristică nu este folosită aici) sau DL-649 (înghețat, revizia
`20261025T165403Z`, neatins). Modelele închise nu se importă și nu se rulează. OGLINDA nu este atinsă.

Calcul clasic, EXACT în Q (`fractions.Fraction`) pentru predictor, calificare și backtest; `float64`
numai pentru scoruri (log, Brier), pentru rulările descriptive din §6 (aceleași ecuații) și pentru
verificarea independentă. Fără hardware cuantic, fără avantaj cuantic, fără noutate mondială
revendicată. `positive_claims_allowed=false`. Arhiva este deja explorată în proiect: valoare
confirmatoare 0, nu set nevăzut.

Precedente atribuite: C. R. Henderson (1950, 1975) — ecuațiile modelului mixt și BLUP;
J. A. Hartigan (1969), M. Goldstein și D. Wooff, *Bayes Linear Statistics* (2007) — așteptarea
ajustată; S. R. Searle, G. Casella, C. E. McCulloch, *Variance Components* (1992) — planuri încrucișate
echilibrate și descompunerea ortogonală; teorema chineză a resturilor (clasică) pentru planul
încrucișat al fazelor 3 × 5 × 7. Practica loteriilor de a folosi mai multe urne și seturi de bile este
documentată public (de ex. descrierea Florida Lottery din sursele proiectului: „three draw machines and
six ball sets … selected at random just prior to the drawing”) — sursa descrie selecție ALEATOARE, nu
rotație deterministă, deci H_CS este a priori puțin probabilă. Pentru Loteria Română, sursele
proiectului menționează cântărirea bilelor, seturile furnizate de producătorul urnelor și certificatele
de greutate, dar NU procedura de alegere a setului. Contribuția proprie este numai formularea pe 6/49
(efect principal + trei rotații aditive încrucișate, sistem Henderson 16×16 exact), protocolul,
martorii analitici și porțile.

## 0. Ipoteza, informația pre-țintă, motivul unei decizii diferite, distinctitate

- **Ipoteză H_CS:** extragerile folosesc mai multe seturi de bile (și/sau urne) cu defecte individuale
  diferite, alese printr-o ROTAȚIE DETERMINISTĂ după ordinea zilelor de extragere. Dacă perioada de
  rotație este K, propensiunea bilei j în ziua de extragere cu indicele k este
  `p_j(k) = p0 + a_j + b^K_j(k mod K)`. Perioada nu este cunoscută; folosim un surogat aditiv pentru
  K ∈ {3, 5, 7}: `θ(k) = p0·1 + a + b³(k mod 3) + b⁵(k mod 5) + b⁷(k mod 7)`. Premisa NU este verificată
  pentru Loteria Română (procedura de alegere a setului este necunoscută; sursa publică citată descrie
  selecție aleatoare la altă loterie); este o ipoteză infirmabilă, nu o constatare.
- **De ce perioadele impare 3, 5, 7 (fixate a priori, nu din date):** (i) din 2009 extragerile alternează
  joi/duminică, deci orice perioadă PARĂ ar conține faza paritate ≈ ziua săptămânii, deja testată de
  familia închisă N1/N2 (interacțiune etichetă × joi/duminică, STOP) — perioadele pare sunt EXCLUSE
  pentru a nu relua N1/N2; (ii) 3, 5, 7 sunt prime între ele, deci planul fazelor este încrucișat
  complet (teorema chineză a resturilor: k mod 105 ↔ (k mod 3, k mod 5, k mod 7)) și componentele sunt
  ortogonale în plan echilibrat; (iii) perioadele 3–7 zile de extragere (≈ 1,5–3,5 săptămâni după 2009,
  3–7 săptămâni înainte) sunt departe de ciclul anual (SE649, închis); modelul aditiv NU conține
  interacțiunea pe 105 celule (care ar alia aproximativ un an de 104–105 extrageri), deci nu are
  componentă sezonieră. Rotațiile cu perioadă pară (de ex. 4 seturi) NU sunt testate aici și nu sunt
  declarate infirmate.
- **Indicele k:** indicele pasului (zi de extragere distinctă) în arhiva curățată de `parser.py`, de la 0,
  în ordine cronologică. Extragerile din aceeași zi au același k (aceeași sesiune, același set). Limită
  declarată: k este indicele ARHIVEI, nu numărul oficial al tragerii; zile lipsă din arhivă (mai ales în
  perioada sursei secundare 1993–1997) ar decala faza între segmente și ar dilua un eventual efect.
  Ipoteza testată este exact cea pe indicele arhivei.
- **Informație pre-țintă:** numărările pe nivelurile de fază (`c_{j,K,r}` pentru K ∈ {3,5,7}, r < K),
  numărările totale, numerele încrucișate de extrageri pe perechi de niveluri, toate din pașii `< k*`,
  și fazele țintei `k* mod 3, 5, 7` (indicele zilei-țintă este cunoscut înaintea extragerii). Fără
  ordinea temporală în interiorul unei clase de fază, fără compoziția extragerilor (perechi), ordinea
  bilelor, tipul extragerii, data calendaristică, structura etichetelor sau surse externe.
- **De ce H_CS nu este infirmată deja de eșecul lui B:** B (și orice predictor pe numărările totale)
  estimează numai media pe faze. O rotație cu efecte de medie (aproape) nulă peste seturi lasă
  numărările totale aproape uniforme și este invizibilă pentru B; R (recență exponențială) amestecă
  toate fazele; BO649 caută schimbări de regim, nu periodicitate. Este o clasă de efecte „ascunse”
  compatibilă cu rezultatele negative anterioare pe numărări.
- **De ce decizia diferă de repere:** extragerea din pasul s intră în predicție cu ponderea
  `v_a + v_{3, s mod 3} + v_{5, s mod 5} + v_{7, s mod 7}` (v definit în §2), PERIODICĂ în s (perioadă 105),
  deci NE-monotonă în timp: o extragere din aceeași fază cu ținta, de acum 10 ani, poate cântări mai
  mult decât extragerea de ieri. Nu este o fereastră de recență, nu este un regim BOCPD, nu este o
  partiție calendaristică. Biletul CS poate fi disjunct de biletele B și R (demonstrat analitic în §4 Q6).
- **Infirmare:** eșecul porților §5 pe backtestul unic. Dacă extragerile sunt uniforme și independente
  (sau setul este ales aleator), H_CS este falsă și nu se așteaptă niciun avantaj.
- **Distinctitate (căutare țintită, 26 oct 2026, 10:19–10:26Z, în `next_candidate/predictie_numere/`,
  `next_candidate/quantum_lab_649/` și `next_candidate/loto_romania/`):** termenii
  `ball_set|set de bile|seturi de bile|seturile de bile|ball set|rotați|rotati|rotation|modulo|mod K|
  ciclu de|machine_id|mașin|aparat|drum|within_day|draws_on_date|special|clasă latentă|latent class|
  mixtur|amestec de|pauz|repaus|idle|periodic|periodogram|fourier|spectral|ciclic|cyclic|mod 3|mod 5|
  mod 7` apar numai ca: surse despre procedura altor loterii (selecție aleatoare a urnei și setului) și
  despre cântărirea bilelor la Loteria Română (inventar de mecanism, fără predictor); câmpurile nule
  `ball_set_id`/`machine_id` ale arhivei; scenarii SINTETICE de comutare periodică a unei bile „calde”
  în blocuri (h3_robustete `switch_periodic`, h4_dinamic `periodic`/`rapid`) folosite ca generatoare de
  test pentru predictori de recență, nu ca predictor pe faza indicelui; fixture-le cu „rotații ciclice”
  ale RB (rang binar) și contextele ciclice c0..6 din testele QL7 (context = suprapunerea c = 0..6, nu
  faza indicelui); „amestecuri” de experți/componente (runda D, robustețe M1), nu clase latente de seturi;
  fazele intervalelor de reapariție din sincronizare_intervale/CR (vârsta proprie a etichetei, nu faza
  indicelui global); `DC` = diferențe circulare mod 49 între etichete. Cea mai apropiată familie ca
  șablon de estimare este SE649 (Bayes liniar ierarhic, efect principal + interacțiune cu o covariabilă);
  CS folosește o covariabilă DIFERITĂ (faza indicelui zilei, nu data calendaristică), un mecanism
  diferit (rotația operațională a seturilor, nu mediul ambiental), un plan diferit (trei factori
  încrucișați, sistem Henderson 16×16, fără formă închisă generală) și nu reutilizează rezultatele SE649.
  Familiile temporale (BO, R, SR, G, MI, EX, EC, AO, OR, CR, AC, S, TI, TP, OC, N1, N2) folosesc
  recența, intervalele, excursiile, ordinea contextelor sau faza săptămânală; niciuna nu folosește faza
  indicelui global modulo o perioadă de rotație. CS nu folosește compoziția, perechile sau structura
  etichetelor și este echivariant la TOATE permutările etichetelor (S49).

## 1. Date (identice cu QL649 §1)

`parser.py` din QL649 (doar ingestie: curățare, ordonare, pași-zi; nu este model). SHA-256 al sursei
și al `parser.py` se înregistrează în `START.json`. Ținte = toate extragerile din pașii `k ≥ 100`.
Extragerile din aceeași zi primesc aceeași predicție (același k, aceleași faze).

## 2. Modelul CS (hiperparametri fixați a priori; totul exact în Q)

Notații: `p0 = 6/49`, `1` vectorul de unu (49), `P = I − 11ᵀ/49`, `σ0² = p0(1−p0)·49/48 = 43/392`
(covarianța exactă a indicatorilor unei extrageri uniforme 6-din-49 este `σ0² P`). Cele 16 niveluri
ℓ sunt: `a` (efectul principal) și `(K, r)` pentru K ∈ {3, 5, 7}, r = 0..K−1. Pentru o extragere i din
pasul s, vectorul de incidență `z_i ∈ {0,1}^16` are 1 pe `a` și pe `(K, s mod K)` pentru fiecare K.
Pentru ținta k*: `z*` analog, cu fazele `k* mod K`.

- **Specificare de ordinul doi:** `E[a] = E[b^K(r)] = 0`; `Var(a) = τa² P`, `Var(b^K(r)) = τ² P`,
  necorelate între ele, între faze și între perioade; pentru extragerea i,
  `E[y_i | θ] = θ(s_i)`, `Var(y_i | θ) ≈ σ0² P`, independente între extrageri. (Covarianța la p0 este o
  aproximare fixată a priori a lui `E[Var(y|θ)]`, ca în SE649.)
- **Hiperparametri:** `τa = p0/20` (efect principal relativ 5%), `τ = p0/4` (efect relativ 25% pe
  fiecare rotație, cea mai mică scară la care poarta 1 devine accesibilă în principiu pentru o singură
  rotație, §2.1); exact `τa² = 9/240100`, `τ² = 9/9604`, `σ0²/τa² = 52675/18`, `σ0²/τ² = 2107/18`. Fără grilă.
- **Așteptarea ajustată (Bayes liniar) prin ecuațiile Henderson:** toate covarianțele sunt de forma
  (matrice scalară) ⊗ P, iar `1ᵀ(y_i − p0·1) = 0` exact; deci, cu `Z` matricea N×16 a incidențelor,
  `G = diag(τa², τ², …, τ²)` (16×16):
  `M = ZᵀZ + σ0² G⁻¹` (16×16, pozitiv definită pentru orice istorie, inclusiv niveluri fără extrageri),
  `v = M⁻¹ z*`, `D_{ℓ,j} = Σ_{i în nivelul ℓ} (y_{ij} − p0) = c_{ℓ,j} − p0·n_ℓ`,
  **`p̂_j = p0 + Σ_ℓ v_ℓ D_{ℓ,j}`**.
  (Derivare: forma primală `p̂ − p0·1 = z*ᵀ G Zᵀ (Z G Zᵀ + σ0² I_N)⁻¹ (Y − p0)` și identitatea
  `G Zᵀ (Z G Zᵀ + σ0² I)⁻¹ = (ZᵀZ + σ0² G⁻¹)⁻¹ Zᵀ`.) `ZᵀZ` conține numerele de extrageri pe niveluri și pe
  perechi de niveluri; `n_a = N`.
- **Derivarea C (plan echilibrat, formă închisă):** dacă istoria are `n = 105·m` pași consecutivi cu
  indicii 0..n−1 și câte o extragere pe pas, atunci fiecare fază a lui K are n/K extrageri distribuite
  egal pe fazele celorlalte perioade, componentele (media generală; contrastele fiecărei perioade) sunt
  ortogonale, iar
  `p̂ = p0·1 + λ0 (x̄ − p0·1) + Σ_K λ_K (x̄_{K, k* mod K} − x̄)`, cu `x̄ = c/n`, `x̄_{K,r} = c_{K,r}/(n/K)`,
  `λ_K = τ²/(τ² + K σ0²/n)`, `λ0 = S/(S + σ0²/n)`, `S = τa² + τ²(1/3 + 1/5 + 1/7) = τa² + (71/105) τ²`.
  (Semnalul contrastului K este `b^K(r) − b̄^K`, cu covarianța `τ²(I − J/K)`, zgomotul are covarianța
  `(Kσ0²/n)(I − J/K)`, proporționale; mediile altor perioade se anulează prin echilibru; covarianțele
  încrucișate ale zgomotului dintre componente sunt zero.) La `n = 105`: `λ3 = 90/391 ≈ 0.230179`,
  `λ5 = 54/355 ≈ 0.152113`, `λ7 = 270/2377 ≈ 0.113589`, `S = 282/420175`, `λ0 = 6768/17303 ≈ 0.391146`.
- **Proprietăți exacte:** `Σ_j p̂_j = 6` (deoarece `Σ_j D_{ℓ,j} = 0`); `p̂` depinde numai de
  `(ZᵀZ, D)` și de fazele țintei (invariant la permutarea extragerilor între pași cu aceeași clasă
  `k mod 105`); echivariant la orice permutare a etichetelor. `p̂ ∈ (0,1)` NU este demonstrat în general
  (ponderile v pot avea semne mixte în plan neechilibrat): numărul de pași cu `p̂` în afara lui (0,1) se
  raportează; legea marginală de mai jos rămâne în (0,1) prin construcție.
- **Predicția:** `q_j(k) = p̂_j`, exact în Q. Conversia în `float64` numai pentru lege și scor.
- **Legea marginală CS:** aceeași regulă ca pentru QL, B, R, BO, GL, SE, cu `π = p̂/6`:
  `q_law = 6/49 + λ(6π − 6/49)`, `λ = min(0.5, λ_max)`, `λ_max` menține `q_law ∈ [1e-4, 1−1e-4]`.
- **Biletul CS:** top-6 după `p̂` comparat EXACT în Q; la egalitate exactă se alege numărul mai mic.

### 2.1 Mărimea efectului și puterea, justificate a priori (calcul de mână, fără date)

- Oracolul care cunoaște `p(k*)` și joacă top-6 are excesul așteptat `≈ p0 · 9.657 · σ_rel ≈ 1.18 σ_rel`
  (statistici de ordine Blom). Poarta 1 (exces ≥ 0.20) cere `σ_rel ≥ 0.17` chiar pentru oracol.
- Câștigul estimatorului ≈ `1.18 σ_t ρ`, cu ρ corelația dintre estimare și adevăr (selecție gaussiană
  top-6); în plan aproape echilibrat, contracția contrastului K la n extrageri este `λ_K(n)`, a mediei
  `λ0(n)`; media pe walk-forward (n = 100..2595).
  - Adevărul = priorul (toate trei rotațiile la 25% + efect principal 5%, σ_rel total ≈ 0.436):
    exces așteptat ≈ 0.23 / 0.40 / 0.44 / 0.47 la n = 100 / 650 / 1300 / 2595, medie ≈ **0.42**.
  - O SINGURĂ rotație adevărată (K0 = 3, 5 sau 7) cu efect relativ 25%, modelul de mai sus (celelalte
    două componente adaugă numai zgomot contractat): medie ≈ **0.21 / 0.20 / 0.18**; la 35%:
    ≈ 0.34 / 0.32 / 0.30; la 15%: ≈ 0.09 / 0.09 / 0.08; la τ = p0/8 cu adevărul = priorul: ≈ 0.17.
- Deci poarta 1 este accesibilă dacă o rotație are efect relativ ≥ ~25–30%; sub ~15% este inaccesibilă
  prin construcție. Lecția SE649: estimarea de mână a fost optimistă cu ~15% (0.19 față de 0.162
  sintetic); aceleași aproximări (gaussianitate, plan echilibrat, fără tăiere) se aplică aici, iar
  dezalinierea fazelor din §0 ar reduce suplimentar puterea. Nu există nicio dovadă fizică pentru
  efecte de 25%; probabilitatea a priori a unui verdict negativ este mare (în special dacă extragerile
  sunt corecte sau setul este ales aleator). Puterea sintetică descriptivă (§6) cuantifică aceste estimări.

## 3. Comparatori, scoruri, jumătăți (identici cu QL649 §5, BO649 §3, GL649 §3, SE649 §3)

U (`q = 6/49`). B: `π_B ∝ c_j+1` (toată istoria). R: `π_R ∝ ew_j+0.5`, cu `ew_j = Σ 2^{−(k−1−s)/26}`
peste extragerile din pașii `s<k`. Biletele B/R sunt top-6; la egalitate se alege numărul mai mic.
Legile B/R folosesc aceeași regulă λ. Pe fiecare țintă: hits = `|bilet ∩ extragere|`;
log = `Σ_j y_j log q_j + (1−y_j) log(1−q_j)`; Brier = `Σ_j (q_j − y_j)²`; Exces = `hits/ținte − 36/49`.
Jumătățile sunt cronologice: prima are `floor(n/2)` ținte. Control de consecvență (condiție de
validitate a rulării, nu poartă): pe arhivă, `hitsB` și `hitsR` reimplementate trebuie să fie egale cu
cele publicate de BO649, GL649 și SE649 (`1847`, `1821`, 2495 de ținte); altfel scorul nu se publică
drept rezultat și defectul se tratează prin amendament.

## 4. Calificare (înainte de istoria reală; numai date construite sau sintetice)

Experimentul pe arhivă rulează NUMAI dacă toate Q1–Q6 sunt PASS.

**Construcția „set constant pe fază” (folosită în Q5/Q6).** Istoria are `n = 105` pași, indicii
k = 0..104, câte o extragere pe pas; pentru o perioadă aleasă K și mulțimi de câte 6 etichete
`A_0, …, A_{K−1}`, extragerea pasului k este `A_{k mod K}`. Lemă: pentru orice altă perioadă K' din
{3,5,7}, pașii fiecărei faze a lui K sunt distribuiți egal (105/(K K') pe fiecare fază a lui K'), deci
numărul de apariții al oricărei etichete în fiecare fază a lui K' este constant și contrastele K' sunt
EXACT zero. Cu Derivarea C: `p̂_j = p0 + λ0 (x̄_j − p0) + λ_K (x̄_{K, k* mod K, j} − x̄_j)`.
Funcția de predicție acceptă orice indice-țintă `k* ≥ 105` cu aceeași istorie (folosește numai fazele lui k*).

- **Q1 exactitate în Q** (40 de instanțe, seed `[649, 11, 1]`): offset de start `k0` uniform în 0..104,
  număr de pași n uniform în 1..40 (instanțele 0–5 forțează n ≤ 6, deci niveluri fără extrageri), fiecare
  pas are 2 extrageri cu probabilitatea 0.15, altfel 1; extrageri uniforme 6-din-49; ținta `k* = k0 + n`:
  1. Henderson 16×16 (eliminare exactă) = forma primală N×N `z*ᵀ G Zᵀ (Z G Zᵀ + σ0² I)⁻¹ (Y − p0)`
     rezolvată exact, egalitate EXACTĂ în Q a celor 49 de valori `p̂`;
  2. `Σ p̂ = 6` exact;
  3. echivarianța exactă la 3 permutări aleatoare fixe ale etichetelor (seed `[649, 11, 11]`);
  4. plus 4 cazuri echilibrate: 2 istorii (n = 105 și n = 210, offset 0, o extragere pe pas, extrageri
     uniforme, seed `[649, 11, 2]`) × 2 ținte (k* = n și k* = n+1): Henderson = forma închisă a
     Derivării C, EXACT, pentru toate cele 49 de valori.
- **Q2 identități pe un univers nul sintetic complet** (structura reală a pașilor — numai numărul de
  extrageri pe zi, fără numere și fără date calendaristice; extrageri uniforme 6-din-49, seed
  `[649, 11, 999]`), walk-forward complet exact: la fiecare pas-țintă `Σ p̂ = 6` exact și
  `0 < q_law < 1`; la pașii din 97 în 97, starea incrementală (`ZᵀZ`, `D`) este identică cu cea
  recalculată de la zero, iar `p̂` prin eliminare Bareiss = `p̂` prin eliminare Gauss–Jordan cu fracții
  (a doua implementare), exact. Se raportează numărul de pași cu `p̂` în afara lui (0,1).
- **Q3 cauzalitate:** la pașii din 97 în 97, predicțiile din istoria trunchiată la `<k` (recalculate din
  lista trunchiată) sunt IDENTICE exact cu cele din rularea completă, inclusiv biletul.
- **Q4 echivarianță și invarianță:** (a) o permutare aleatoare fixă a etichetelor (seed `[649, 11, 4]`)
  dă `p̂(σH) = σ p̂(H)` EXACT la pașii din 97 în 97 ai universului Q2; (b) permutarea aleatoare (seed
  `[649, 11, 44]`) a extragerilor între pașii cu o singură extragere din ACEEAȘI clasă `k mod 105`
  (indicii pașilor rămân ficși) lasă `p̂` la pasul final identic exact și schimbă efectiv istoria.
  (Descriptiv, nu poartă: abaterea maximă a lui `p̂` la pasul final când extragerile se permută între
  clase diferite.)
- **Q5 martor de informație (analitic, Derivarea C):** trei fixture `F5_K`, K ∈ {3, 5, 7}, construcția
  „set constant pe fază” cu `A_0 = {5, 20, 21, 22, 23, 24}`, `A_1 = {9, 20, 21, 22, 23, 24}`,
  `A_r = {30, 31, 32, 33, 34, 35}` pentru r ≥ 2. Cerințe pentru fiecare K:
  (a) `c_5 = c_9 = 105/K` (numărări totale egale), deci legea și scorul B sunt identice pentru 5 și 9
  (exact), iar orice predictor pe numărările totale le dă aceeași valoare;
  (b) ținta k* = 105 (toate fazele 0): `p̂_5 − p̂_9 = λ_K` EXACT în Q (de mână 0.230179 / 0.152113 /
  0.113589), semn anticipat `p̂_5 > p̂_9`;
  (c) `q_law,5 − q_law,9 ≥ 1e-3` (de mână `λ_K/2` ≥ 0.0568, marjă ≥ ×56);
  (d) ținta k* = 106 (faza 1 pentru toate K): `p̂_5 − p̂_9 = −λ_K` EXACT; ținta k* = 107 (faza 2):
  `p̂_5 − p̂_9 = 0` EXACT (informația este faza țintei);
  (e) R ordonează invers: `ew_9 = 2^{1/26} · ew_5 > ew_5` la k* = 105 (eticheta 9 apare cu un pas mai
  târziu în fiecare ciclu), verificat în float64 cu toleranță relativă `1e-12` pentru egalitate și strict
  pentru inegalitate.
- **Q6 martor de decizie (analitic, derivat înainte de sigilare):** fixture `F6`, construcția „set
  constant pe fază” cu K = 3: `A_0 = {44, 45, 46, 47, 48, 49}`, `A_1 = A_2 = {1, 2, 3, 4, 5, 6}`; ținta
  k* = 105 (faza 0). Numărări totale: 1..6 → 70, 44..49 → 35, rest 0; `x̄_{3,0}` = 1 pentru 44..49 și 0
  pentru 1..6. Derivarea C dă exact:
  `p̂_j = p0 + λ0(1/3 − p0) + (2/3)λ3` (≈ 0.358388) pentru j = 44..49;
  `p̂_j = p0 + λ0(2/3 − p0) − (2/3)λ3` (≈ 0.181865) pentru j = 1..6;
  `p̂_j = p0(1 − λ0)` (≈ 0.074554) pentru j = 7..43;
  `p̂_44 − p̂_1 = (4λ3 − λ0)/3 = 1194264/6765473 ≈ 0.176523 > 0` (deoarece `4λ3 = 360/391 > λ0`).
  **Bilet CS anticipat = {44, 45, 46, 47, 48, 49}.** B: numărările 70 > 35 → **bilet B = {1, …, 6}**
  (disjunct de CS). R: vârstele `104 − s` ale etichetei 1 sunt {3i, 3i+1}, ale etichetei 44 sunt {3i+2},
  i = 0..34, deci `ew_1 > 2·ew_44 > ew_44`; etichetele 1..6 au același ew, maxim → **bilet R = {1, …, 6}
  ≠ biletul CS**. Cerință Q6: biletul CS calculat este EXACT {44..49}, biletul B este EXACT {1..6},
  `ew_1 > 2·max_{j∈44..49} ew_j`, biletul R ≠ biletul CS, iar cele trei valori `p̂` de mai sus sunt exacte.
  (Dacă oricare anticipare analitică este infirmată, Q6 eșuează și se publică.)

Rezultat `CS_QUALIFIED` (6/6) sau `CS_NOT_QUALIFIED`. Dacă nu se califică, rezultatul se publică, codul
rămâne condiționat NEVALIDAT și istoria reală nu se atinge. Defectele tehnice ale implementării (nu
ale ipotezei) descoperite în calificare se tratează prin amendament scris și sigilat ÎNAINTE de orice
acces la istoria reală, cu încercarea inițială păstrată.

## 5. Backtest walk-forward unic pe arhivă și porți (toate 6 necesare)

1. `ExcesCS/U ≥ 0.20`;
2. `hitsCS > hitsB` și `hitsCS > hitsR`;
3. `logCS − logU > 0` și `logCS − logB > 0`;
4. `BrierCS < BrierU, BrierB, BrierR`;
5. în ambele jumătăți: exces `> 0` și `hitsCS − hitsB > 0`;
6. în ambele jumătăți: `logCS − logB > 0`.

Verdict `CS_PROMOVAT_EXPLORATORIU` (6/6), altfel `CS_NO_PROMOTION_EXPLORATORY`. Și la 6/6 rămâne
`positive_claims_allowed=false`; ar urma o confirmare prospectivă separată. Rularea are loc O SINGURĂ
dată; `START.json` blochează repetarea. Predicțiile (`p̂` exacte serializate ca fracții, `q_law`,
bilete, fazele țintei, ponderile v exacte) se scriu și se sigilează SHA-256 ÎNAINTE de scor. Rezultatul
se publică indiferent de verdict. Fără tuning după vizualizare.

## 6. Descriptiv (nu intră în porți și nu schimbă verdictul)

Rulările descriptive (nule, putere, sensibilitate) folosesc aceleași ecuații Henderson în `float64`
(`numpy.linalg.solve`), declarat acum; backtestul și calificarea sunt exacte.

- p exact pentru hits sub extrageri uniforme independente (convoluție hipergeometrică);
- numărul de pași-țintă în care biletul CS diferă de B, respectiv de R; hits și log pe faza-țintă a
  fiecărei perioade; numărul de pași cu `p̂` în afara lui (0,1);
- la pasul final: numerele de extrageri pe niveluri, ponderile v, abaterea, minimul și maximul lui
  `p̂/p0 − 1`;
- statisticile G ale tabelelor etichetă × fază pentru K = 3, 5, 7 pe întreaga arhivă
  (`G_K = 2 Σ c_{jKr} ln(c_{jKr}/(6 n_{Kr}/49))`, n în extrageri) și suma lor, cu rangul printre
  universurile nule (controlul premisei, independent de predictor — lecția SE649 (4));
- **32 de universuri nule** sintetice cu aceeași structură de pași, extrageri uniforme 6-din-49, seed
  `[649, 11, u]`, `u = 0..31`: CS, comparatori, porți, statisticile G; distribuția excesului, a lui
  `logCS−B`, a porților trecute și rangul empiric al valorilor reale (lecția: `logModel−B > 0` poate
  apărea sub nul prin contracție);
- **putere sintetică sub H_CS** (strict descriptiv, compară cu §2.1): 16 universuri la scara priorului,
  seed `[649, 11, 1000+u]`: `a ~ N(0, 0.05²)`, `b^K(r) ~ N(0, 0.25²)` independente (49 valori fiecare,
  K ∈ {3,5,7}, r < K); 8 universuri cu o SINGURĂ rotație, seed `[649, 11, 2000+u]`:
  `K0 = [3, 5, 7, 3, 5, 7, 3, 5][u]`, `a ~ N(0, 0.05²)`, `b^{K0}(r) ~ N(0, 0.25²)`, celelalte zero;
  în ambele, `p_j(k) = p0(1 + [P(a + Σ_K b^K(k mod K))]_j)` tăiat la `[0.2 p0, 1.8 p0]`, extrageri prin
  alegere secvențială fără întoarcere cu ponderi `p(k)`; aceleași scoruri și porți;
- **sensibilitate declarată acum:** `(τa, τ) ∈ {(p0/20, p0/8), (p0/20, p0/2), (p0/10, p0/4)}` pe arhivă,
  după backtestul unic, aceleași scoruri. Strict descriptiv; nicio configurație alternativă nu poate
  fi promovată, selectată sau folosită ulterior ca „variantă reparată”; nicio altă mulțime de perioade
  (inclusiv pare, 11, 13 etc.) nu se testează ca salvare.

## 7. Verificare independentă

`verify_cs649.py` NU importă `cs649.py`, `se649.py`, `gl649.py`, `wu649.py`, `bo649.py`, `engine.py`,
`parser.py` sau `validare.py`. Script-ul:
- reparsează JSONL după §1 și verifică SHA-256, numărul de extrageri și de pași; fazele `k mod K`
  recalculate din propriul indice al pașilor;
- recalculează comparatorii B/R (R prin recursie), scorurile, porțile și verdictul; verifică
  `hitsB = 1847`, `hitsR = 1821`, 2495 de ținte;
- recalculează `p̂` la FIECARE pas printr-o metodă DIFERITĂ: forma primală pe CELULE (clasele
  `k mod 105` nevide; `x̄_c` media celulei, `Var(x̄) = Z_c G Z_cᵀ + σ0² diag(1/n_c)`,
  `p̂ − p0 = Cov(θ*, x̄) Var(x̄)⁻¹ (x̄ − p0)`, `numpy.linalg.solve` în `float64`, fără sistemul Henderson),
  cu `max|Δp̂| ≤ 1e-10` față de predicțiile salvate; la pașii din 25 în 25, sistemul Henderson rezolvat
  EXACT în Q printr-o eliminare Gauss–Jordan proprie este egal exact cu fracțiile salvate;
- biletul salvat este top-6 exact după fracțiile salvate (cu regula de egalitate) și un top-6 valid sub
  `p̂` independent (`min p̂_bilet ≥ max p̂_rest − 1e-10`);
- verifică hash-ul predicțiilor; hits exacte, sume de scor cu toleranță `1e-6`.

Status PASS numai dacă toate verificările trec. UNKNOWN nu devine PASS.

## 8. Lecțiile de proces aplicate (din WU649, GL649, SE649)

(1) Martorii Q5/Q6 sunt derivați ANALITIC înainte de sigilare (Derivarea C: formă închisă în plan
echilibrat, bilete determinate exact, margini explicite pentru R). (2) Mărimea efectului necesară
porții 1 este calculată de mână în §2.1 (cu nota de optimism din SE649), iar puterea sintetică este
declarată în §6. (3) `logCS − logB` se raportează mereu împreună cu universurile nule. (4) Statisticile G
etichetă × fază, comparate cu nulul, controlează premisa independent de predictor.
