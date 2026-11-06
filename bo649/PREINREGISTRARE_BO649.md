# PREINREGISTRARE BO649 — „Rupturi de regim” (detecție bayesiană online a schimbărilor)

Versiune protocol: `BO649-P1`. Scris și sigilat (SHA-256 în `SIGILIU_PROTOCOL_BO649.json`)
ÎNAINTE de scrierea oricărui cod BO649 și înainte de orice calcul BO649 pe
`extrageri_649.jsonl`. Ipoteză NOUĂ și DISTINCTĂ în pista QL649; nu este o salvare,
o reparare sau o re-parametrizare a QL649 (închis `QL_NO_PROMOTION_EXPLORATORY`, 0/6)
și nici a DL-649 (înghețat, revizia `20261025T165403Z`, neatins). Modelele închise nu
se importă și nu se rulează. OGLINDA nu este atinsă.

Calcul clasic exact: NumPy `float64` pe CPU pentru rulări, aritmetică rațională exactă
(`fractions.Fraction`, în Q) pentru certificate. Fără hardware cuantic, fără avantaj
cuantic, fără noutate mondială revendicată. `positive_claims_allowed=false`. Arhiva
este deja explorată în proiect: valoare confirmatoare 0, nu set nevăzut.

Precedente atribuite: R. P. Adams, D. J. C. MacKay, „Bayesian Online Changepoint
Detection” (2007); P. Fearnhead, Z. Liu, „On-line inference for multiple changepoint
problems” (JRSS-B, 2007); conjugarea Beta–Bernoulli este clasică. Contribuția proprie
este doar aplicarea pe loteria 6/49 cu protocolul, martorii și porțile de mai jos.

## 0. Ipoteza, informația pre-țintă și motivul unei decizii diferite

- **Ipoteză H_BO:** ratele de apariție ale numerelor sunt constante pe bucăți, cu rupturi
  la momente necunoscute (de exemplu schimbări de echipament sau de seturi de bile).
  Dacă H_BO e adevărată, cea mai bună predicție pentru pasul următor folosește doar
  regimul curent, a cărui lungime se deduce bayesian din date.
- **Informație pre-țintă:** numai extragerile din pașii `< k` (zile calendaristice, ca în
  QL649 §1–2), ordonate cronologic. Nu se folosesc perechi, ordinea bilelor, calendarul,
  tipul extragerii sau surse externe.
- **De ce decizia diferă de repere:** B folosește toată istoria cu pondere egală. R
  folosește o fereastră exponențială fixă (timp de înjumătățire 26 de pași). BO
  folosește o mixtură posterioară peste lungimile regimului curent, deci o fereastră
  adaptivă și dependentă de date. Dacă nu există rupturi, BO se apropie de B (cu
  netezire). Dacă există o ruptură clară, BO uită trecutul dinaintea rupturii, iar
  B nu. Aceeași multi-mulțime de extrageri în altă ordine temporală schimbă BO, dar
  nu schimbă B (martorul I).
- **Infirmare:** eșecul porților §5 pe backtestul unic. Dacă extragerile sunt uniforme și
  independente, H_BO este falsă și nu se așteaptă niciun avantaj.

## 1. Date (identice cu QL649 §1)

`parser.py` din QL649 (doar ingestie: curățare, ordonare, pași-zi; nu este model).
SHA-256 al sursei și al `parser.py` se înregistrează în `START.json`. Ținte = toate
extragerile din pașii `k ≥ 100` (încălzire 100 de pași). Extragerile din aceeași zi
primesc aceeași predicție.

## 2. Modelul BO (hiperparametri fixați a priori)

Generic pe `N` numere și `κ` bile pe extragere (real: `N=49`, `κ=6`), `y_d ∈ {0,1}^N`.

- **Regim:** rate independente `p_j`, prior `Beta(a0, b0)`, `a0 = m0·κ/N`,
  `b0 = m0·(N−κ)/N`, cu **`m0 = 12`** (prior echivalent cu 12 extrageri). În regim,
  extragerile sunt i.i.d. produs-Bernoulli(p). Constrângerea `Σ y = κ` este ignorată;
  aceasta este o specificare greșită declarată, coerentă cu scorul log produs-Bernoulli din §5.
- **Rupturi:** numai la începutul unui pas, cu hazard constant **`h = 1/250`**, independent,
  pentru pașii `s ≥ 1`. Pasul 0 începe un regim. Justificare a priori: 2527 de pași în
  33 de ani (inventar, nu selecție), deci un prior de aproximativ 10 regimuri.
- **Lungimea regimului** `r_s` = numărul de pași compleți anteriori din regimul curent.
  Statisticile pentru `r` la pasul `s` sunt `n^(r)` (numărul de extrageri din pașii
  `s−r..s−1`) și `c_j^(r)` (frecvențele lor).
- **Prior predictiv pentru pasul s** (din date `< s`):
  `P(r_s=0) = h` (s ≥ 1), `P(r_s=r+1) = (1−h)·P(r_{s−1}=r | date ≤ s−1)`; `r_0 = 0`.
- **Predicția:** `q_j(s) = Σ_r P(r_s=r | date<s) · (a0 + c_j^(r)) / (m0 + n^(r))`.
  Identitate: `Σ_j q_j = κ` exact.
- **Evidența pasului s pentru r:** produs secvențial peste extragerile pasului
  (fiecare actualizează statisticile pentru următoarea), cu predictivul Beta–Bernoulli
  `Π_j ((a0+c_j)/(m0+n))^{y_j} · ((b0+n−c_j)/(m0+n))^{1−y_j}`.
- **Posterior:** `P(r_s=r | date ≤ s) ∝ P(r_s=r | date<s) · evidența_s(r)`.
- Recursie exactă, fără trunchiere sau tăiere a lungimilor (cost O(K²·N)).
- **Legea marginală BO:** aceeași regulă ca pentru QL, B și R, cu
  `π = q/κ`: `q_law = 6/49 + λ(6π − 6/49)`, unde `λ = min(0.5, λ_max)` și `q_law ∈ [1e-4, 1−1e-4]`.
- **Biletul BO:** top-6 după `q`. La egalitate se alege numărul mai mic, prin sortare
  stabilă. Biletul top-6 maximizează exact numărul așteptat de potriviri sub `q`.

## 3. Comparatori, scoruri, jumătăți (identici cu QL649 §5)

U (`q = 6/49`). B: `π_B ∝ c_j+1`, adică toată istoria. R: `π_R ∝ ew_j+0.5`, cu
`ew_j = Σ 2^{−(k−1−s)/26}` peste extragerile din pașii `s<k`. Biletele B/R sunt top-6;
la egalitate se alege numărul mai mic. Legile B/R folosesc aceeași regulă λ.
Pe fiecare țintă se calculează:
- hits = `|bilet ∩ extragere|`;
- log = `Σ_j y_j log q_j + (1−y_j) log(1−q_j)`;
- Brier = `Σ_j (q_j − y_j)²`;
- Exces = `hits/ținte − 36/49`.

Jumătățile sunt definite cronologic: prima jumătate are `floor(n/2)` ținte.

## 4. Calificare (înainte de istoria reală; numai date construite sau sintetice)

Experimentul pe arhivă rulează NUMAI dacă toate verificările sunt PASS:

- **Q1 exactitate în Q:** pe cel puțin 40 de instanțe mici, cu seed fix
  (`N ∈ {3,4,5}`, `κ ∈ {1,2}`, `T ∈ {6,…,9}` pași cu 1–2 extrageri, `h` și `m0`
  raționale variate), recursia BO în `Fraction` este EGALĂ exact cu suma brută peste
  toate cele `2^{T−1}` segmentări. Se compară:
  - predicția `q(s)` la fiecare pas;
  - evidența totală.

  Implementarea `float64` coincide cu `Fraction` cu `max|Δq| < 1e-12`.
- **Q2 identități:** `Σ_j q_j = κ` (eroare `< 1e-9`) și `0 < q < 1` la fiecare pas,
  pe un univers nul sintetic complet. Structura pașilor este aceeași; datele sunt
  uniforme, cu seed `[649, 2, 999]`.
- **Q3 cauzalitate:** predicțiile pentru pașii `k` (eșantion fix: din 97 în 97) calculate
  din istoria trunchiată la `<k` sunt identice cu cele din rularea completă.
- **Q4 echivarianță:** o permutare fixă σ a etichetelor permută `q` exact, cu
  toleranță `1e-12`.
- **Q5 martor de informație:** două istorii construite, H+ și H−, cu aceeași
  multi-mulțime de extrageri, în ordine temporală diferită. Legea și biletul B sunt
  identice exact, dar `max_j |q_BO(H+) − q_BO(H−)| ≥ 1e-3`.
- **Q6 martor de decizie:** un fixture construit determinist, cu un regim vechi lung,
  un regim intermediar și o fluctuație recentă scurtă. Biletul BO diferă, ca mulțime,
  atât de biletul B, cât și de biletul R.

Rezultat `BO_QUALIFIED` (6/6) sau `BO_NOT_QUALIFIED`. Dacă nu se califică, rezultatul
se publică, codul rămâne condiționat NEVALIDAT și istoria reală nu se atinge.

## 5. Backtest walk-forward unic pe arhivă și porți (toate 6 necesare)

1. `ExcesBO/U ≥ 0.20`;
2. `hitsBO > hitsB` și `hitsBO > hitsR`;
3. `logBO − logU > 0` și `logBO − logB > 0`;
4. `BrierBO < BrierU, BrierB, BrierR`;
5. în ambele jumătăți: exces `> 0` și `hitsBO − hitsB > 0`;
6. în ambele jumătăți: `logBO − logB > 0`.

Verdictul este `BO_PROMOVAT_EXPLORATORIU` (6/6), altfel `BO_NO_PROMOTION_EXPLORATORY`.
Și la 6/6 rămâne `positive_claims_allowed=false`; ar urma o confirmare prospectivă
separată. Rularea este O SINGURĂ dată. `START.json` blochează repetarea. Predicțiile
(`q`, bilete, posterior pe lungimi) se scriu și se sigilează SHA-256 înainte de scor.
Rezultatul se publică indiferent de verdict. Nu se face tuning după vizualizare. Orice
defect tehnic se tratează prin amendament scris, iar încercarea inițială se păstrează.

## 6. Descriptiv (nu intră în porți și nu schimbă verdictul)

- p exact pentru hits sub extrageri uniforme independente, folosind convoluția
  hipergeometrică;
- numărul de pași-țintă în care biletul BO diferă de B sau de R;
- traiectoria lungimii așteptate a regimului `E[r]` și numărul de pași cu
  `P(r ≤ 100) > 0.5`;
- **64 de universuri nule** sintetice, cu aceeași structură de pași, extrageri
  uniforme 6-din-49 fără întoarcere și seed `[649, 2, u]` pentru `u = 0..63`. Pe
  fiecare se rulează BO, comparatorii și porțile. Se raportează distribuția
  excesului, `logBO−B`, porțile trecute și rangul empiric al valorilor reale;
- **sensibilitate declarată acum:** `h ∈ {1/100, 1/250, 1/1000}` × `m0 ∈ {6, 12, 48}`
  pe arhivă, cu aceleași scoruri. Raportarea este strict descriptivă; nicio
  configurație alternativă nu poate fi promovată, selectată sau folosită ulterior ca
  „variantă reparată”.

## 7. Verificare independentă

`verify_bo649.py` NU importă `bo649.py`, `engine.py`, `parser.py` sau `validare.py`.
Script-ul:
- reparsează JSONL după §1 și verifică SHA-256, numărul de extrageri și pașii;
- recalculează BO cu o formulare diferită (log-domeniu, sume de prefix);
- recalculează comparatorii, scorurile, porțile și verdictul;
- verifică hash-ul predicțiilor, cu toleranțe: `q` sub `1e-9`, bilete și hits exacte,
  sume sub `1e-6`.

Statusul este PASS doar dacă toate verificările trec. UNKNOWN nu devine PASS.
