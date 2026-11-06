# PREINREGISTRARE SE649 — „Anotimpurile bilelor” (Bayes liniar ierarhic exact, etichetă × anotimp)

Versiune protocol: `SE649-P1`. Scris și sigilat (SHA-256 în `SIGILIU_PROTOCOL_SE649.json`)
ÎNAINTE de scrierea oricărui cod SE649 și înainte de orice calcul SE649 (pe date reale,
sintetice sau construite). Ipoteză NOUĂ și DISTINCTĂ în pista QL649. Nu salvează, nu repară
și nu re-parametrizează QL649 (închis `QL_NO_PROMOTION_EXPLORATORY`, 0/6), BO649 (închis 0/6),
WU649 (`WU_NOT_QUALIFIED`, cod NEVALIDAT, neexecutat aici), GL649 (închis
`GL_NO_PROMOTION_EXPLORATORY`, 2/6; nicio structură de cifre/etichete nu este folosită aici) sau
DL-649 (înghețat, revizia `20261025T165403Z`, neatins). Modelele închise nu se importă și nu se
rulează. OGLINDA nu este atinsă.

Calcul clasic, EXACT în Q (`fractions.Fraction`) pentru predictor și certificate; `float64`
numai pentru scoruri (log, Brier) și pentru verificarea independentă. Fără hardware cuantic,
fără avantaj cuantic, fără noutate mondială revendicată. `positive_claims_allowed=false`.
Arhiva este deja explorată în proiect: valoare confirmatoare 0, nu set nevăzut.

Precedente atribuite: J. A. Hartigan (1969) și M. Goldstein, D. Wooff, *Bayes Linear
Statistics* (2007) — așteptarea ajustată; C. R. Henderson (1975), G. K. Robinson (1991) —
efecte aleatorii ierarhice (principal + interacțiune); J. Sherman, W. J. Morrison (1950) —
inversarea de rang unu; dependența de temperatură a coeficientului de restituire al
elastomerilor este fizică clasică (de ex. mingile de squash), nu o constatare a noastră despre
bilele Loteriei Române. Contribuția proprie este numai formularea pe 6/49 (efect principal +
interacțiune cu anotimpul, ponderi în formă închisă), protocolul, martorii și porțile.

## 0. Ipoteza, informația pre-țintă, motivul unei decizii diferite, distinctitate

- **Ipoteză H_SE:** propensiunea bilei j depinde de anotimpul meteorologic al extragerii:
  `p_j(φ) = p0 + a_j + b_j(φ)`, cu `a` efectul principal (pe tot anul) și `b(φ)` interacțiunea
  bilă × anotimp. Mecanism ipotetic: condițiile ambientale (temperatură, umiditate) variază cu
  anotimpul, iar bilele individuale (loturi de material, vopsea, uzură diferite) răspund diferit
  (restituție, aderență, încărcare electrostatică). Premisa fizică NU este verificată pentru
  Loteria Română (nu știm dacă studioul este climatizat sau dacă seturile de bile se schimbă);
  este o ipoteză infirmabilă, nu o constatare.
- **Anotimpuri fixate a priori (nu din date):** după luna din `draw_date`: `φ = 0` iarnă (dec,
  ian, feb), `φ = 1` primăvară (mar–mai), `φ = 2` vară (iun–aug), `φ = 3` toamnă (sep–nov).
- **Informație pre-țintă:** numărările pe anotimpuri `c_{j,φ}` și numerele de extrageri `n_φ`
  din pașii `< k` (zile calendaristice, ca în QL649 §1–2) și anotimpul DATEI țintei (data
  extragerii este cunoscută dinainte, din calendarul tragerilor). Fără ordinea temporală în
  interiorul anotimpurilor, compoziția extragerilor, ordinea bilelor, tip de extragere, ziua
  săptămânii, structura etichetelor sau surse externe.
- **De ce H_SE nu este infirmată deja de eșecul lui B:** B (și orice predictor pe numărările
  totale) estimează numai efectul principal `a`. O interacțiune cu medie anuală zero (bila j
  favorizată iarna, defavorizată vara) lasă numărările totale aproape uniforme și este
  invizibilă pentru B, R și BO; ea poate fi mare chiar dacă B nu câștigă nimic. Este clasa de
  efecte „ascunse” compatibilă cu rezultatele negative anterioare pe numărări.
- **De ce decizia diferă de repere:** B ordonează după numărările totale; R după recența
  exponențială; U nu ordonează. SE ordonează în principal după frecvențele din ANOTIMPUL
  ȚINTEI, adunate peste toți anii: o extragere de acum 20 de ani din același anotimp cântărește
  mai mult decât una de acum două luni din alt anotimp (ponderare NE-monotonă în timp, deci nu
  este o fereastră de recență, nu este un regim BOCPD și nu are schimbări de regim). Biletul SE
  poate fi disjunct de biletul B (demonstrat analitic în §4 Q6).
- **Infirmare:** eșecul porților §5 pe backtestul unic. Dacă extragerile sunt uniforme și
  independente, H_SE este falsă și nu se așteaptă niciun avantaj.
- **Distinctitate (căutare țintită, 25 oct 2026, 22:39–22:43Z, în `next_candidate/
  predictie_numere/`, `next_candidate/quantum_lab_649/` și `next_candidate/loto_romania/`):**
  termenii `sezon|anotimp|seasonal|season|ziua anului|day of year|doy|von mises|periodicitate
  anual|ciclu anual|annual|umiditat|humidity|temperatur|trimestr|quarter|iarn|primăvar|toamn|
  vară|month of|restituti|elasticitat|cauciuc|rubber|idle|repaus` apar numai ca: ora de iarnă a
  fusului (cutoff OGLINDA), rapoarte anuale ale altor loterii în căutări de surse, temperatura
  GPU/laptop (resurse), un diagnostic N2 care împarte rândurile în patru SFERTURI CRONOLOGICE
  (`quarter_1..4`, nu anotimpuri). Cea mai apropiată familie ca șablon este N1/N2 (interacțiune
  etichetă × fază calendaristică joi/duminică, STOP); SE folosește o covariabilă diferită și
  ortogonală (ziua săptămânii este echilibrată în interiorul anotimpurilor), un mecanism diferit
  (mediu ambiental, nu procedură/set pe zi) și un estimator diferit (Bayes liniar ierarhic cu
  efect principal și interacțiune, nu raportul cD/cJ); nu reutilizează codul, datele filtrate sau
  rezultatele N1/N2. Familiile temporale (BO, R, SR, G, MI, EX, EC, AO, OR, CR, AC, S, TI, TP,
  OC, N1, N2) folosesc ordinea/recența sau faza săptămânală; XJ folosește alt joc; GL/SC/DC/
  Runda B folosesc structura etichetelor; familiile pe perechi/grafuri/simpliciale (DL, PG, CF,
  LS, FS, AT, RA, RH, D, QL649) și compoziționale (WU, MC, M1, PM) folosesc compoziția. SE nu
  folosește ordinea în interiorul anotimpului, compoziția, perechile sau structura etichetelor
  și este echivariant la TOATE permutările etichetelor (S49).

## 1. Date (identice cu QL649 §1)

`parser.py` din QL649 (doar ingestie: curățare, ordonare, pași-zi; nu este model). SHA-256 al
sursei și al `parser.py` se înregistrează în `START.json`. Ținte = toate extragerile din pașii
`k ≥ 100`. Extragerile din aceeași zi primesc aceeași predicție (aceeași dată, același
anotimp).

## 2. Modelul SE (hiperparametri fixați a priori; totul exact în Q)

Notații: `p0 = 6/49`, `1` vectorul de unu (49), `P = I − 11ᵀ/49`, `σ0² = p0(1−p0)·49/48 =
43/392` (covarianța exactă a indicatorilor unei extrageri uniforme 6-din-49 este `σ0² P`).
Pentru anotimpul φ cu `n_φ > 0`: `x_φ = c_φ / n_φ`, `d_φ = x_φ − p0·1` (`1ᵀd_φ = 0` exact,
deoarece `Σ_j c_{j,φ} = 6 n_φ`), `ν_φ = σ0² / n_φ`. `O` = mulțimea anotimpurilor cu `n_φ > 0`.

- **Specificare de ordinul doi:** `E[a] = E[b(φ)] = 0`; `Var(a) = τa² P`, `Var(b(φ)) = τb² P`,
  necorelate între ele și între anotimpuri; `Var(d_φ | p) ≈ ν_φ P`, independente între anotimpuri
  (extrageri diferite). (Covarianța la p0 este o aproximare fixată a priori a lui `E[Var(x|p)]`.)
- **Hiperparametri:** `τa = p0/20` (efect principal relativ 5%: echilibrul anual al bilelor este
  ținta obișnuită a testelor de conformitate), `τb = p0/5` (interacțiune relativă 20%); exact
  `τa² = 9/240100`, `τb² = 36/60025`. Fără grilă. Justificarea mărimii (lecția GL649) este în §2.1.
- **Așteptarea ajustată pentru ținta din anotimpul φ*:** cu `θ = a + b(φ*)`, toate covarianțele
  sunt de forma (matrice m×m) ⊗ P, deci `p̂ − p0·1 = Σ_{φ∈O} w_φ d_φ`, unde `w = Σ_d⁻¹ s`,
  `Σ_d = τa² 11ᵀ + diag(D_φ)`, `D_φ = τb² + ν_φ`, `s_φ = τa² + τb² [φ = φ*]`.
  **Formă închisă (Sherman–Morrison):** `S = Σ_{φ∈O} 1/D_φ`, `κ = τa²/(1 + τa² S)`;
  dacă `φ* ∈ O`: `w_φ = κ (ν_{φ*}/D_{φ*}) / D_φ + [φ = φ*] τb²/D_{φ*}`;
  dacă `φ* ∉ O`: `w_φ = κ / D_φ`.
  (Derivare: `Σ_d⁻¹ 1 = D⁻¹1/(1+τa²S)`, `Σ_d⁻¹ e* = e*/D* − τa² D⁻¹1/(D*(1+τa²S))`.)
- **Proprietăți exacte (demonstrate):** `Σ_j p̂_j = 6`; `Σ_φ w_φ < 1` (deoarece `κS < 1` și
  `(ν* + τb²)/D* = 1`), deci `p̂_j = p0(1 − Σw) + Σ w_φ x_{j,φ} ∈ (0, 1)` strict; `p̂` depinde
  numai de `(c_φ, n_φ)_φ` și de φ* (invariant la ordinea în interiorul anotimpurilor);
  echivariant la orice permutare a etichetelor.
- **Predicția:** `q_j(k) = p̂_j`, exact în Q. Conversia în `float64` numai pentru lege și scor.
- **Legea marginală SE:** aceeași regulă ca pentru QL, B, R, BO, GL, cu `π = p̂/6`:
  `q_law = 6/49 + λ(6π − 6/49)`, `λ = min(0.5, λ_max)`, `λ_max` menține `q_law ∈ [1e-4, 1−1e-4]`.
- **Biletul SE:** top-6 după `p̂` comparat EXACT în Q; la egalitate exactă se alege numărul
  mai mic.

### 2.1 Mărimea efectului și puterea, justificate a priori (calcul de mână, fără date)

- Oracolul care cunoaște `p(φ*)` și joacă top-6 are excesul așteptat
  `p0 · σ_rel · E[Σ top-6 din 49 normale standard] ≈ 0.1224 · 9.66 · σ_rel ≈ 1.18 σ_rel`
  (statistici de ordine prin formula Blom: 2.236, 1.838, 1.613, 1.449, 1.317, 1.204). Poarta 1
  (exces ≥ 0.20) cere `σ_rel ≥ 0.17` chiar pentru oracol.
- Cu estimare din `n` extrageri ale anotimpului: zgomotul relativ are varianța
  `σ0²/(n p0²) = 7.316/n`; fiabilitatea `r = σ_rel²/(σ_rel² + 7.316/n)`, câștigul ≈
  `1.18 σ_rel √r`. Pentru `σ_rel = √(0.05² + 0.2²) ≈ 0.206` (scara priorului): `√r ≈ 0.61 / 0.81
  / 0.89` la `n = 100 / 325 / 650`; media pe walk-forward ≈ 0.78, deci excesul așteptat **sub
  H_SE la scara priorului ≈ 0.19 — la limita porții 1**. La `τb = p0/10` câștigul așteptat
  ≈ 0.09, poarta 1 inaccesibilă.
- Deci `τb = p0/5` este cea mai mică scară la care poarta 1 este accesibilă în principiu;
  sub ea ipoteza nu poate trece prin construcție. Nu există nicio dovadă fizică pentru efecte de
  20%; probabilitatea a priori a unui verdict negativ este mare (în special dacă extragerile sunt
  corecte). Puterea sintetică descriptivă (§6) cuantifică aceste estimări de mână.

## 3. Comparatori, scoruri, jumătăți (identici cu QL649 §5, BO649 §3, GL649 §3)

U (`q = 6/49`). B: `π_B ∝ c_j+1` (toată istoria). R: `π_R ∝ ew_j+0.5`, cu
`ew_j = Σ 2^{−(k−1−s)/26}` peste extragerile din pașii `s<k`. Biletele B/R sunt top-6; la
egalitate se alege numărul mai mic. Legile B/R folosesc aceeași regulă λ. Pe fiecare țintă:
hits = `|bilet ∩ extragere|`; log = `Σ_j y_j log q_j + (1−y_j) log(1−q_j)`;
Brier = `Σ_j (q_j − y_j)²`; Exces = `hits/ținte − 36/49`. Jumătățile sunt cronologice: prima
are `floor(n/2)` ținte. Control de consecvență (condiție de validitate a rulării, nu poartă):
pe arhivă, `hitsB` și `hitsR` reimplementate trebuie să fie egale cu cele publicate de BO649 și
GL649 (`1847`, `1821`, 2495 de ținte); altfel scorul nu se publică drept rezultat și defectul se
tratează prin amendament.

## 4. Calificare (înainte de istoria reală; numai date construite sau sintetice)

Experimentul pe arhivă rulează NUMAI dacă toate Q1–Q6 sunt PASS.

**Construcția rotativă pe blocuri sezoniere (folosită în Q5/Q6).** Pentru un bloc cu numărări
`c` (`Σ c = 6n`, `c_j ≤ n`): `L` = concatenarea, pentru j = 1..49, a lui j repetat de `c_j`
ori; extragerea i (i = 0..n−1) a blocului este `{L[i + r·n] : r = 0..5}`. Lemă: aparițiile lui j
ocupă în L un interval contiguu de lungime `c_j ≤ n`, deci fiecare extragere are 6 etichete
distincte, iar numărările blocului sunt exact c. Fiecare extragere primește o dată distinctă
(un pas pe zi), zilnic, în ordine, de la începutul blocului. Blocuri cu `n = 49` extrageri:
iarnă 2000-12-01..2001-01-18, primăvară 2001-03-01..2001-04-18, vară 2001-06-01..2001-07-19,
toamnă 2001-09-01..2001-10-19. Ținta de iarnă: 2002-01-15; ținta de vară: 2002-07-15.
Cu `n = 49`: `ν = 43/19208 ≈ 2.23865e-3`, `D = τb² + ν ≈ 2.83840e-3`, `τb²/D ≈ 0.211299`.

**Derivarea B (antisimetrie iarnă–vară, analitic).** Dacă toate blocurile observate au același
`n` (deci același D) și `d_φ = 0` pentru anotimpurile din afara {iarnă, vară}, iar
`d_vară = −d_iarnă = −u`, atunci pentru ținta de iarnă `p̂ − p0·1 = (w_iarnă − w_vară) u`
`= (τb²/D) u` (termenii κ se anulează, D egale), iar pentru ținta de vară `p̂ − p0·1 = −(τb²/D) u`.
Etichetele cu `u_j = 0` au `p̂_j = p0` EXACT.

- **Q1 exactitate în Q** (40 de instanțe, seed `[649, 10, 1]`): anotimp țintă φ* aleator; pentru
  fiecare anotimp `n_φ` uniform în 0..120 (instanțele 0–4 forțează `n_{φ*} = 0`; instanțele
  5–9 forțează exact un alt anotimp cu `n_φ = 0`; cel puțin un anotimp are `n_φ > 0`), numărări
  din `n_φ` extrageri uniforme 6-din-49:
  1. forma închisă = rezolvarea directă exactă a sistemului `|O|×|O|` `Σ_d w = s` (eliminare
     exactă), egalitate EXACTĂ în Q;
  2. `Σ p̂ = 6` exact, `Σ w < 1` exact, `0 < p̂_j < 1` pentru toți j;
  3. ortogonalitatea Bayes liniară pe vectori expliciți (instanțele 10–14): pentru fiecare
     coloană `(ψ, l)` a matricei `Var(d)` explicite de dimensiune `49|O|` (bloc φ:
     `[τa² + [φ=ψ] D_ψ] P e_l`), operatorul `d ↦ Σ_φ w_φ d_φ` aplicat dă EXACT coloana
     `[τa² + τb² [ψ=φ*]] P e_l` a lui `Cov(θ, d)`;
  4. echivarianța exactă la 3 permutări aleatoare fixe ale etichetelor (seed `[649, 10, 11]`).
- **Q2 identități pe un univers nul sintetic complet** (structura reală a pașilor ȘI datele lor
  calendaristice — numai dimensiunile pe zi și anotimpurile, fără numere; extrageri uniforme
  6-din-49, seed `[649, 10, 999]`), walk-forward complet: la fiecare pas-țintă `Σ p̂ = 6` exact și
  `0 < p̂ < 1`, `0 < q_law < 1`; la pașii din 97 în 97, forma închisă = rezolvarea directă exactă.
- **Q3 cauzalitate:** la pașii din 97 în 97, predicțiile din istoria trunchiată la `<k`
  (recalculate din lista trunchiată) sunt IDENTICE exact cu cele din rularea completă.
- **Q4 echivarianță și invarianță:** (a) o permutare aleatoare fixă a etichetelor (seed
  `[649, 10, 4]`) dă `p̂(σH) = σ p̂(H)` EXACT la pașii din 97 în 97 ai universului Q2;
  (b) permutarea aleatoare (seed `[649, 10, 44]`) a extragerilor între pașii cu o singură
  extragere din ACELAȘI anotimp (datele pașilor rămân fixe) lasă `p̂` la pasul final identic
  exact (invarianța la ordinea din interiorul anotimpului). (Descriptiv, nu poartă: abaterea
  maximă a lui `p̂` la pasul final când extragerile se permută între anotimpuri diferite.)
- **Q5 martor de informație (analitic, Derivarea B):** fixture F5 cu patru blocuri de câte 49
  extrageri: în toate blocurile `c_j = 6`, cu excepția: iarnă `c_5 = 9`, `c_9 = 3`; vară
  `c_5 = 3`, `c_9 = 9`. Cerințe:
  (a) numărările totale ale lui 5 și 9 sunt egale (24 = 24) și toate cele 49 sunt egale, deci
  legea și scorul B sunt identice pentru 5 și 9 (exact), iar orice predictor pe numărările
  totale le dă aceeași valoare;
  (b) ținta de iarnă: `p̂_5 − p̂_9 = 6 τb² / (49 D)` EXACT în Q (de mână ≈ 0.025873), cu
  `p̂_5 − p0 = p0 − p̂_9` și `p̂_j = p0` exact pentru j ∉ {5, 9}; semn anticipat `p̂_5 > p̂_9`;
  (c) `q_law,5 − q_law,9 ≥ 1e-3` (de mână ≈ 0.012937, marjă ×12);
  (d) ținta de vară (aceeași istorie): `p̂_5 − p̂_9 = −6 τb²/(49 D)` EXACT (informația este
  anotimpul țintei);
  (e) permutarea aleatoare (seed `[649, 10, 5]`) a extragerilor în interiorul fiecărui bloc
  (datele rămân fixe) dă `p̂` identic exact.
- **Q6 martor de decizie (analitic, derivat înainte de sigilare):** fixture F6 cu DOUĂ blocuri
  (iarnă, apoi vară) de câte 49 de extrageri, ținta de iarnă 2002-01-15 (`k = 98`):
  iarnă: `c_j = 0` pentru j = 1..6, `c_j = 6` pentru j = 7..43, `c_j = 12` pentru j = 44..49;
  vară: `c_j = 12` pentru j = 1..6, `6` pentru 7..43, `0` pentru 44..49 (sume 294 = 6·49).
  Atunci numărările totale sunt toate 12; `u_j = d_iarnă,j = (c_j − 6)/49` este `+6/49` pentru
  j = 44..49, `−6/49` pentru j = 1..6 și 0 în rest, iar Derivarea B dă exact
  `p̂_j = p0 + 6 τb²/(49 D)` (≈ p0 + 0.025873) pentru j = 44..49, `p̂_j = p0 − 6 τb²/(49 D)`
  pentru j = 1..6 și `p̂_j = p0` pentru j = 7..43.
  **Bilet SE anticipat = {44, 45, 46, 47, 48, 49}.** B (toate numărările 12, egalitate → numerele
  mai mici): **bilet B = {1, 2, 3, 4, 5, 6}** (disjunct de SE).
  R: eticheta 1 ocupă în blocul de vară extragerile 0..11 (vârste `k−1−s` = 37..48), deci
  `ew_1 ≥ 12 · 2^{−48/26} ≈ 3.338`; etichetele 44..49 apar numai iarna (vârste ≥ 49), deci
  `ew_j ≤ 12 · 2^{−49/26} ≈ 3.250 < ew_1`. Eticheta 1 este mai sus decât toate 44..49 în R, deci
  **biletul R ≠ biletul SE**.
  Cerință Q6: biletul SE calculat este EXACT {44..49}, biletul B este EXACT {1..6},
  `ew_1 > max_{j∈44..49} ew_j`, biletul R ≠ biletul SE, iar cele trei valori `p̂` de mai sus sunt
  exacte. (Dacă oricare anticipare analitică este infirmată, Q6 eșuează și se publică.)

Rezultat `SE_QUALIFIED` (6/6) sau `SE_NOT_QUALIFIED`. Dacă nu se califică, rezultatul se
publică, codul rămâne condiționat NEVALIDAT și istoria reală nu se atinge. Defectele tehnice
ale implementării (nu ale ipotezei) descoperite în calificare se tratează prin amendament
scris și sigilat ÎNAINTE de orice acces la istoria reală, cu încercarea inițială păstrată.

## 5. Backtest walk-forward unic pe arhivă și porți (toate 6 necesare)

1. `ExcesSE/U ≥ 0.20`;
2. `hitsSE > hitsB` și `hitsSE > hitsR`;
3. `logSE − logU > 0` și `logSE − logB > 0`;
4. `BrierSE < BrierU, BrierB, BrierR`;
5. în ambele jumătăți: exces `> 0` și `hitsSE − hitsB > 0`;
6. în ambele jumătăți: `logSE − logB > 0`.

Verdict `SE_PROMOVAT_EXPLORATORIU` (6/6), altfel `SE_NO_PROMOTION_EXPLORATORY`. Și la 6/6
rămâne `positive_claims_allowed=false`; ar urma o confirmare prospectivă separată. Rularea
are loc O SINGURĂ dată; `START.json` blochează repetarea. Predicțiile (`p̂` exacte serializate ca
fracții, `q_law`, bilete, anotimpul țintei, ponderile `w`) se scriu și se sigilează SHA-256
ÎNAINTE de scor. Rezultatul se publică indiferent de verdict. Fără tuning după vizualizare.

## 6. Descriptiv (nu intră în porți și nu schimbă verdictul)

- p exact pentru hits sub extrageri uniforme independente (convoluție hipergeometrică);
- numărul de pași-țintă în care biletul SE diferă de B, respectiv de R; hits/log pe anotimpuri;
- la pasul final: `n_φ`, ponderile `w_φ` pentru fiecare anotimp țintă, abaterea, minimul și
  maximul lui `p̂/p0 − 1`;
- statistica G a tabelului etichetă × anotimp pe întreaga arhivă
  (`G = 2 Σ c_{jφ} ln(c_{jφ}/(6 n_φ/49))`) și rangul ei printre universurile nule (măsoară dacă
  există heterogenitate sezonieră, independent de predictor);
- **32 de universuri nule** sintetice cu aceeași structură de pași și aceleași date, extrageri
  uniforme 6-din-49, seed `[649, 10, u]`, `u = 0..31`: SE, comparatori, porți, statistica G;
  distribuția excesului, a lui `logSE−B`, a porților trecute și rangul empiric al valorilor reale
  (lecția GL649: `logModel−B > 0` poate apărea sub nul prin contracție);
- **putere sintetică sub H_SE:** 16 universuri la scara priorului, seed `[649, 10, 1000+u]`:
  `a ~ N(0, 0.05²)`, `b(φ) ~ N(0, 0.2²)` independente (49 valori fiecare, φ = 0..3),
  `p_j(φ) = p0(1 + [P(a + b(φ))]_j)` tăiat la `[0.2 p0, 1.8 p0]`, extrageri prin alegere
  secvențială fără întoarcere cu ponderi `p(φ)` ale anotimpului datei; plus 8 universuri la
  jumătatea scării interacțiunii (`b ~ N(0, 0.1²)`), seed `[649, 10, 2000+u]`; aceleași scoruri
  și porți (strict descriptiv: compară cu estimarea de mână din §2.1);
- **sensibilitate declarată acum:** `(τa, τb) ∈ {(p0/20, p0/10), (p0/20, p0/4), (p0/10, p0/5)}`
  pe arhivă, după backtestul unic, aceleași scoruri. Strict descriptiv; nicio configurație
  alternativă nu poate fi promovată, selectată sau folosită ulterior ca „variantă reparată”.

## 7. Verificare independentă

`verify_se649.py` NU importă `se649.py`, `gl649.py`, `wu649.py`, `bo649.py`, `engine.py`,
`parser.py` sau `validare.py`. Script-ul:
- reparsează JSONL după §1 și verifică SHA-256, numărul de extrageri, pașii și anotimpurile
  (luna prin `datetime.date`, nu prin felierea șirului);
- recalculează comparatorii B/R (R prin recursie), scorurile, porțile și verdictul; verifică
  `hitsB = 1847`, `hitsR = 1821`, 2495 de ținte;
- recalculează `p̂` la FIECARE pas printr-o metodă DIFERITĂ: rezolvarea directă `float64` a
  sistemului `|O|×|O|` (`numpy.linalg.solve`, fără formula Sherman–Morrison), cu
  `max|Δp̂| ≤ 1e-12` față de predicțiile salvate; la pașii din 25 în 25, rezolvarea directă
  EXACTĂ în Q (eliminare Gauss–Jordan proprie) este egală exact cu fracțiile salvate;
- biletul salvat este top-6 exact după fracțiile salvate (cu regula de egalitate) și un top-6
  valid sub `p̂` independent (`min p̂_bilet ≥ max p̂_rest − 1e-12`);
- verifică hash-ul predicțiilor; hits exacte, sume de scor cu toleranță `1e-6`.

Status PASS numai dacă toate verificările trec. UNKNOWN nu devine PASS.

## 8. Lecțiile de proces aplicate (din WU649 și GL649)

(1) Martorii Q5/Q6 sunt derivați ANALITIC înainte de sigilare (Derivarea B: formă închisă,
bilete determinate exact, margini explicite pentru R). (2) Mărimea efectului necesară porții 1
este calculată de mână în §2.1, iar puterea sintetică este declarată în §6. (3) `logSE − logB`
se raportează mereu împreună cu universurile nule.
