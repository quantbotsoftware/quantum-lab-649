# PREINREGISTRARE GL649 — „Masa glifelor” (Bayes liniar exact pe structura cifrelor tipărite)

Versiune protocol: `GL649-P1`. Scris și sigilat (SHA-256 în `SIGILIU_PROTOCOL_GL649.json`)
ÎNAINTE de scrierea oricărui cod GL649 și înainte de orice calcul GL649 (pe date reale,
sintetice sau construite). Ipoteză NOUĂ și DISTINCTĂ în pista QL649. Nu salvează, nu repară
și nu re-parametrizează QL649 (închis `QL_NO_PROMOTION_EXPLORATORY`, 0/6), BO649 (închis
`BO_NO_PROMOTION_EXPLORATORY`, 0/6), WU649 (închis `WU_NOT_QUALIFIED`, 5/6, cod NEVALIDAT,
neexecutat aici) sau DL-649 (înghețat, revizia `20261025T165403Z`, neatins). Modelele închise
nu se importă și nu se rulează. OGLINDA nu este atinsă.

Calcul clasic, EXACT în Q (`fractions.Fraction`) pentru predictor și certificate; `float64`
numai pentru scoruri (log, Brier) și pentru verificarea independentă. Fără hardware cuantic,
fără avantaj cuantic, fără noutate mondială revendicată. `positive_claims_allowed=false`.
Arhiva este deja explorată în proiect: valoare confirmatoare 0, nu set nevăzut.

Precedente atribuite: J. A. Hartigan, „Linear Bayesian methods” (JRSS B, 1969); M. Goldstein,
D. Wooff, *Bayes Linear Statistics* (Wiley, 2007) — așteptarea ajustată; C. R. Henderson
(1950, 1975) și G. K. Robinson, „That BLUP is a good thing” (Stat. Sci., 1991) — efecte
aleatorii încrucișate; M. A. Woodbury (1950) — identitatea de inversare; S. E. Fienberg,
„Randomization and social affairs: the 1970 draft lottery” (Science, 1971) — precedent real de
abatere a unei loterii legată de structura etichetelor (ordinea de încărcare), nu de glife.
Ideea populară că „bilele cu mai multă cerneală sunt mai grele” este folclor; nu este a noastră.
Contribuția proprie este numai formularea pe 6/49 (incidența glifelor, covarianța exactă a
eșantionării fără întoarcere, sectorul antisimetric analitic), protocolul, martorii și porțile.

## 0. Ipoteza, informația pre-țintă, motivul unei decizii diferite, distinctitate

- **Ipoteză H_GL:** propensiunea bilei j se abate de la `p0 = 6/49` printr-o sumă de contribuții
  ale glifelor (cifrelor zecimale) tipărite pe bilă — cerneală, vopsea, decal sau gravură —
  plus un rest propriu bilei. Semnul fiecărei contribuții este necunoscut (modelul este
  agnostic: cerneala adaugă masă, gravura scoate). Premisa fizică NU este verificată pentru
  bilele Loteriei Române; este o ipoteză infirmabilă, nu o constatare.
- **Structura a priori (nu din date):** `G` (49×10), `G[j,d]` = numărul de apariții ale cifrei
  `d` în scrierea zecimală a lui j fără zero în față (1..9: o glifă; 10..49: două glife;
  `G[11,1] = G[22,2] = G[33,3] = G[44,4] = 2`; cifra 0 apare numai în 10, 20, 30, 40).
- **Informație pre-țintă:** numai numărările `c_j` și numărul `n` de extrageri din pașii `< k`
  (zile calendaristice, ca în QL649 §1–2), plus `G` (fixă, cunoscută dinainte). Fără calendar,
  tip de extragere, ordine temporală, compoziția extragerilor, ordinea bilelor sau surse externe.
- **De ce decizia diferă de repere:** B (`π ∝ c+1`) ordonează numai după `c`; U nu ordonează;
  orice predictor care depinde numai de numărări, simetric în etichete, dă aceeași valoare
  etichetelor cu numărări egale.
  GL împrumută putere între etichetele care împart glife: la numărări egale sau apropiate,
  eticheta ale cărei „surori de glifă” au fost frecvente urcă, iar cea ale cărei surori au fost
  rare coboară. Biletul GL poate diferi de B (demonstrat analitic în §4 Q6). Față de R (fereastră
  exponențială) și BO (regimuri), GL este invariant la ordinea temporală. Față de WU, GL nu
  folosește compoziția extragerilor și NU este echivariant la permutarea etichetelor (este
  echivariant numai la automorfismele structurii de glife, §4 Q4).
- **Infirmare:** eșecul porților §5 pe backtestul unic. Dacă extragerile sunt uniforme și
  independente, H_GL este falsă și nu se așteaptă niciun avantaj.
- **Distinctitate (căutare țintită, 25 oct 2026, 21:51Z, în `next_candidate/predictie_numere/`,
  `next_candidate/loto_romania/` și `next_candidate/quantum_lab_649/`):** termenii
  `cifr[aeă]|digit|glif|glyph|cerneal|vopse|tipărit|decad|bayes linear|bayes liniar|BLUP|
  Woodbury|Henderson|efecte aleatorii|random effect|ultima cifr|zeci|unități|geometria numerelor|
  numărul tipărit` apar numai ca: precizie numerică („Decimal cu 40/60 cifre”), formatare,
  sume monetare, accesări de surse; EX declară explicit că NU folosește „geometria numerelor
  tipărite”; scutul anti-mulțime QL649 penalizează euristic „≥4 cu aceeași ultimă cifră” pentru
  popularitate, nu pentru predicție. Familii cu structură pe etichete: Runda B (submulțime
  NECUNOSCUTĂ cu prior schimbabil pe etichete — fără structură fixă), SC (suma etichetelor unei
  extrageri), DC (diferențe circulare mod 49 între extrageri), H1 (atribute fizice MĂSURATE +
  ordine verificată, `DATE_INSUFICIENTE`, nerulat). Niciuna nu folosește incidența glifelor
  zecimale ca structură de covarianță a propensiunilor marginale. Familiile pe perechi/grafuri/
  simpliciale (DL, PG, CF, LS, FS, AT, RA, RH, D, QL649) și compoziționale (WU, MC, M1, PM) sunt
  echivariante la etichete; familiile temporale (BO, SR, G, MI, EX, EC, AO, OR, CR, AC, S, TI, TP,
  OC, N1, N2) folosesc ordinea. GL nu folosește ordinea, compoziția sau perechile.

## 1. Date (identice cu QL649 §1)

`parser.py` din QL649 (doar ingestie: curățare, ordonare, pași-zi; nu este model). SHA-256 al
sursei și al `parser.py` se înregistrează în `START.json`. Ținte = toate extragerile din pașii
`k ≥ 100`. Extragerile din aceeași zi primesc aceeași predicție.

## 2. Modelul GL (hiperparametri fixați a priori; totul exact în Q)

Notații: `p0 = 6/49`, `1` vectorul de unu (49), `J = 1 1ᵀ`, `P = I − J/49`, `x = c/n`,
`v = x − p0·1` (`1ᵀv = 0` exact, deoarece `Σ c = 6n`).

- **Specificare de ordinul doi (Bayes liniar):** `E[p] = p0·1`, `Var(p) = P K P`, cu
  `K = s_g² G Gᵀ + s_e² I`. Proiecția P impune `Σ_j p_j = 6` (exact 6 bile pe extragere).
- **Hiperparametri:** `s_g = p0/10` (abaterea relativă 10% pe glifă), `s_e = p0/20` (rest 5%);
  exact: `s_g² = 9/60025`, `s_e² = 9/240100`. Justificare a priori: H_GL afirmă că glifele sunt
  mecanismul principal; restul permite alte efecte proprii bilei. O etichetă cu două glife are
  abaterea relativă a priori ≈ 15%; poarta 1 (exces 0.20) cere ≈ 27% relativ pe bilet, adică
  ≈ 1.8σ pentru extremele a 49 de etichete — plauzibil sub H_GL, fără să fie impus. Fără grilă.
- **Covarianța de eșantionare (exactă pentru 6-din-49 la p0):** pentru indicatorii unei extrageri
  uniforme, `Cov(y) = p0(1−p0)·(49/48)·P`; deci `Var(x | p) ≈ ν P`, `ν = σ0²/n`,
  `σ0² = p0(1−p0)·49/48 = 43/392`. (Covarianța la p0 este o aproximare fixată a priori a lui
  `E[Var(x|p)]`.)
- **Așteptarea ajustată:** `p̂ = p0·1 + PKP (PKP + νP)⁺ v`. Pe `1⊥`, `PKP + νP = a·I + s_g² H Hᵀ`,
  cu `a = s_e² + ν`, `H = P G` (coloane centrate). Prin Woodbury:
  `M = (a/s_g²)·I_10 + HᵀH`, `y = M⁻¹ Hᵀ v` (`Hᵀv = Gᵀv`), `z = (v − H y)/a`, **`p̂ = x − ν z`**.
  (Derivare: `(aI + s_g² HHᵀ) z = v` și `PKP z = (aI + s_g² HHᵀ − νI) z = v − νz`.) Rezultă
  `1ᵀz = 0` și `Σ_j p̂_j = 6` EXACT.
- **Efectele de glifă ajustate (descriptiv):** `γ̂ = s_g² Hᵀ z` (= `Cov(γ,x) Var(x)⁺ v`).
- **Predicția:** `q_j(k) = p̂_j`, exact în Q. Conversia în `float64` numai pentru lege și scor.
- **Legea marginală GL:** aceeași regulă ca pentru QL, B, R, BO, cu `π = q/6`:
  `q_law = 6/49 + λ(6π − 6/49)`, `λ = min(0.5, λ_max)`, `λ_max` menține `q_law ∈ [1e-4, 1−1e-4]`.
- **Biletul GL:** top-6 după `p̂` comparat EXACT în Q; la egalitate exactă se alege numărul mai
  mic.

## 3. Comparatori, scoruri, jumătăți (identici cu QL649 §5 și BO649 §3)

U (`q = 6/49`). B: `π_B ∝ c_j+1` (toată istoria). R: `π_R ∝ ew_j+0.5`, cu
`ew_j = Σ 2^{−(k−1−s)/26}` peste extragerile din pașii `s<k`. Biletele B/R sunt top-6; la
egalitate se alege numărul mai mic. Legile B/R folosesc aceeași regulă λ. Pe fiecare țintă:
hits = `|bilet ∩ extragere|`; log = `Σ_j y_j log q_j + (1−y_j) log(1−q_j)`;
Brier = `Σ_j (q_j − y_j)²`; Exces = `hits/ținte − 36/49`. Jumătățile sunt cronologice: prima
are `floor(n/2)` ținte. Control de consecvență (nu poartă predictivă, dar condiție de validitate
a rulării): pe arhivă, totalurile reimplementate `hitsB` și `hitsR` trebuie să fie egale cu cele
publicate de BO649 (`1847`, `1821`, 2495 de ținte); altfel scorul nu se publică drept rezultat
și defectul se tratează prin amendament.

## 4. Calificare (înainte de istoria reală; numai date construite sau sintetice)

Experimentul pe arhivă rulează NUMAI dacă toate Q1–Q6 sunt PASS.

**Construcția rotativă (folosită în Q5/Q6).** Pentru numărări `c` cu `Σ c = 6n` și `c_j ≤ n`:
`L` = concatenarea, pentru j = 1..49, a lui j repetat de `c_j` ori (lungime 6n); extragerea i
(i = 0..n−1) este `{L[i + r·n] : r = 0..5}`, o extragere pe pas. Lemă: aparițiile lui j ocupă
în L un interval contiguu de lungime `c_j ≤ n`, deci pozițiile `i + r·n` (r diferiți) nu pot
cădea ambele în el; fiecare extragere are 6 etichete distincte, iar numărările sunt exact c.

**Derivarea A (sectorul antisimetric, analitic).** Pentru cifre distincte `d, d' ∈ {5..9}`,
fie `S_{dd'}` = vectorii `u = Σ_{t=0..4} u_t (e_{10t+d} − e_{10t+d'})` (pentru t = 0 etichetele
sunt d și d'). Glifele zecilor se anulează în fiecare pereche, deci `Gᵀu = (Σ_t u_t)(f_d − f_d')`
și `G(f_d − f_d') = Σ_t (e_{10t+d} − e_{10t+d'})`. Rezultă că S este invariant: în coordonatele
t, `PKP|_S = s_e² I_5 + s_g² J_5` și `νP|_S = ν I_5`. Deci pentru `v ∈ S`:
`p̂ − p0·1 = A u`, cu `A u = λ0 (u − ū·1) + λ1 ū·1` (în coordonate t), `ū = (Σ_t u_t)/5`,
`λ0 = s_e²/(s_e² + ν)`, `λ1 = (s_e² + 5 s_g²)/(s_e² + 5 s_g² + ν)`, `λ1 > λ0` strict, iar
`p̂_j = p0` EXACT pentru toate etichetele din afara celor 10 implicate.
Valori de mână pentru `n = 196`: `ν = 43/76832 ≈ 5.5966e-4`, `λ0 ≈ 0.06277`, `λ1 ≈ 0.58446`.

- **Q1 exactitate în Q** (40 de instanțe, seed `[649, 9, 1]`, n uniform în 49..400, numărări din
  n extrageri uniforme 6-din-49):
  1. Woodbury = rezolvarea directă exactă a sistemului 49×49 `(PKP + νP + J) w = v`,
     `p̂_dir = p0·1 + PKP w`: egalitate EXACTĂ în Q;
  2. `Σ p̂ = 6` și `1ᵀz = 0` exact; identitatea Bayes liniară
     `PKP − A_n(PKP + νP) = 0` exact pe 1⊥ (verificată pe vectorii `P e_j`, j = 1..49, la 5
     instanțe), unde `A_n v := p̂ − p0·1`;
  3. echivarianța exactă la 3 permutări ale cifrelor {5..9} (ciclul (5 6 7 8 9), transpoziția
     (5 9), produsul lor), induse pe etichete (cifra unităților permutată, zecile neschimbate);
  4. formula închisă din Derivarea A, exact în Q, pentru 20 de cazuri aleatoare (perechi d,d'
     aleatoare din {5..9}, abateri întregi `a_t`, `|a_t| ≤ 5`, `n = 49·m`, `m` aleator în 1..8,
     `b = 6m`), realizate ca numărări `c_{10t+d} = b + a_t`, `c_{10t+d'} = b − a_t`, restul `b`
     (deci `u = a/n`, `0 ≤ c_j ≤ n`).
- **Q2 identități pe un univers nul sintetic complet** (structura reală a pașilor, numai
  dimensiunile pe zi, extrageri uniforme 6-din-49, seed `[649, 9, 999]`), walk-forward complet:
  la fiecare pas-țintă `Σ p̂ = 6` și `1ᵀz = 0` exact, `0 < q_law < 1`; la pașii din 97 în 97,
  rezolvarea directă 49×49 exactă = Woodbury.
- **Q3 cauzalitate:** la pașii din 97 în 97, predicțiile din istoria trunchiată la `<k` sunt
  IDENTICE (exact în Q) cu cele din rularea completă.
- **Q4 echivarianță la automorfisme:** permutarea etichetelor indusă de ciclul cifrelor
  (5 6 7 8 9) dă `p̂(σH) = σ p̂(H)` EXACT la pașii din 97 în 97 ai universului Q2.
  (Descriptiv, nu poartă: abaterea de la echivarianță la transpoziția etichetelor (17 19), care
  nu este automorfism.)
- **Q5 martor de informație (analitic, Derivarea A cu d=7, d'=8):** fixture F5 prin construcția
  rotativă cu `n = 196`, `c_7 = 36`, `c_8 = 12`, toate celelalte `c_j = 24`. Cerințe:
  (a) `c_17 = c_19`, deci legea și scorul B sunt identice pentru 17 și 19 (exact), iar orice
  predictor pe numărări echivariant la etichete le dă aceeași valoare (transpoziția (17 19)
  fixează vectorul de numărări);
  (b) `p̂_17 − p̂_19 = Δ(λ1 − λ0)/(5n)` EXACT în Q, cu `Δ = 12`, `n = 196`, `p̂_19 = p0` exact;
  semn anticipat analitic: `p̂_17 > p̂_19` (eticheta 17 împarte glifa 7 cu eticheta 7, frecventă);
  (c) `q_law,17 − q_law,19 ≥ 1e-3` (de mână: `≈ 0.5·12·0.52169/980 ≈ 3.19e-3`, marjă ×3);
  (d) invarianța la ordinea temporală: F5 în ordine permutată fix (seed `[649, 9, 5]`) dă `p̂`
  identic exact.
- **Q6 martor de decizie (analitic, derivat înainte de sigilare):** fixture F6 prin construcția
  rotativă cu `n = 196`, `b = 24`: `c_7 = 23`, `c_8 = 25`, `c_{10t+7} = 25`, `c_{10t+8} = 23`
  pentru t = 1..4, toate celelalte 39 de etichete `c_j = 24`. Atunci `v ∈ S_78`,
  `u = (−1, 1, 1, 1, 1)/196`, `ū = 3/980`, iar:
  `[Au]_0 = (−1.6 λ0 + 0.6 λ1)/196 > 0` ⇔ `3λ1 > 8λ0` (de mână: `1.753 > 0.502`, marjă ×3.5);
  `[Au]_t = (0.4 λ0 + 0.6 λ1)/196 > 0` pentru t ≥ 1. Deci GL: etichetele 7, 17, 27, 37, 47 peste
  p0, etichetele 8, 18, 28, 38, 48 sub p0, celelalte 39 exact p0 (cea mai mică: 1).
  **Bilet GL anticipat = {1, 7, 17, 27, 37, 47}.** B (numărări 25 pentru {8, 17, 27, 37, 47}, 24
  pentru 39 de etichete, 23 pentru {7, 18, 28, 38, 48}): **bilet B = {1, 8, 17, 27, 37, 47}**.
  R: în construcția rotativă, eticheta 1 ocupă extragerile 0..23, deci
  `ew_1 ≤ 2^{−172/26}/(1 − 2^{−1/26}) ≈ 0.39 < 1`, iar cele 6 etichete distincte ale ultimei
  extrageri au fiecare `ew ≥ 1`; deci **1 ∉ bilet R**, iar biletul R ≠ biletul GL.
  Cerință Q6: biletul GL calculat este EXACT {1, 7, 17, 27, 37, 47}, biletul B este EXACT
  {1, 8, 17, 27, 37, 47}, 1 ∉ biletul R. (Dacă oricare anticipare analitică este infirmată, Q6
  eșuează și se publică.)

Rezultat `GL_QUALIFIED` (6/6) sau `GL_NOT_QUALIFIED`. Dacă nu se califică, rezultatul se
publică, codul rămâne condiționat NEVALIDAT și istoria reală nu se atinge. Defectele tehnice
ale implementării (nu ale ipotezei) descoperite în calificare se tratează prin amendament
scris și sigilat ÎNAINTE de orice acces la istoria reală, cu încercarea inițială păstrată.

## 5. Backtest walk-forward unic pe arhivă și porți (toate 6 necesare)

1. `ExcesGL/U ≥ 0.20`;
2. `hitsGL > hitsB` și `hitsGL > hitsR`;
3. `logGL − logU > 0` și `logGL − logB > 0`;
4. `BrierGL < BrierU, BrierB, BrierR`;
5. în ambele jumătăți: exces `> 0` și `hitsGL − hitsB > 0`;
6. în ambele jumătăți: `logGL − logB > 0`.

Verdict `GL_PROMOVAT_EXPLORATORIU` (6/6), altfel `GL_NO_PROMOTION_EXPLORATORY`. Și la 6/6
rămâne `positive_claims_allowed=false`; ar urma o confirmare prospectivă separată. Rularea
are loc O SINGURĂ dată; `START.json` blochează repetarea. Predicțiile (`p̂` exacte serializate ca
fracții, `q_law`, bilete) se scriu și se sigilează SHA-256 ÎNAINTE de scor. Rezultatul se
publică indiferent de verdict. Fără tuning după vizualizare.

## 6. Descriptiv (nu intră în porți și nu schimbă verdictul)

- p exact pentru hits sub extrageri uniforme independente (convoluție hipergeometrică);
- numărul de pași-țintă în care biletul GL diferă de B, respectiv de R;
- la pasul final: `γ̂` (10 efecte de glifă ajustate, relativ la p0), abaterea, minimul și
  maximul lui `p̂/p0 − 1`, corelația Spearman între `p̂` și numărări;
- **32 de universuri nule** sintetice cu aceeași structură de pași, extrageri uniforme 6-din-49,
  seed `[649, 9, u]`, `u = 0..31`: GL, comparatori, porți; distribuția excesului, a lui
  `logGL−B`, a porților trecute și rangul empiric al valorilor reale;
- **putere sintetică sub H_GL:** 16 universuri cu aceeași structură de pași; efecte relative
  `γ_d ~ N(0, 0.1²)`, rest `ε_j ~ N(0, 0.05²)`, `p_j = p0(1 + [P(Gγ + ε)]_j)` (cu `p_j` tăiat la
  `[0.2 p0, 1.8 p0]`), extrageri prin alegere secvențială fără întoarcere cu ponderi `p_j`,
  seed `[649, 9, 1000+u]`; aceleași scoruri și porți (strict descriptiv: arată cât de des GL ar
  putea bate B chiar dacă H_GL ar fi adevărată la scara priorului);
- **sensibilitate declarată acum:** `(s_g, s_e) ∈ {(p0/20, p0/20), (p0/5, p0/20), (p0/10, p0/5)}`
  pe arhivă, aceleași scoruri. Strict descriptiv; nicio configurație alternativă nu poate fi
  promovată, selectată sau folosită ulterior ca „variantă reparată”.

## 7. Verificare independentă

`verify_gl649.py` NU importă `gl649.py`, `wu649.py`, `bo649.py`, `engine.py`, `parser.py` sau
`validare.py`. Script-ul:
- reparsează JSONL după §1 și verifică SHA-256, numărul de extrageri și pașii;
- recalculează comparatorii B/R, scorurile, porțile și verdictul; verifică `hitsB = 1847`,
  `hitsR = 1821` (consecvență cu BO649);
- recalculează `p̂` la FIECARE pas printr-o metodă DIFERITĂ: rezolvarea directă `float64` a
  sistemului 49×49 `(PKP + νP + s_e² J) w = v` (fără Woodbury; `s_e² J` doar pentru
  condiționare, pentru `v ⊥ 1` dă același `w = z`), `p̂ = x − ν w`, cu `max|Δp̂| ≤ 1e-12` față
  de predicțiile salvate; la pașii din 25 în 25, rezolvarea directă EXACTĂ în Q a aceluiași
  sistem (eliminare Gauss–Jordan proprie) este egală exact cu fracțiile salvate;
- biletul salvat este top-6 exact după fracțiile salvate (cu regula de egalitate) și este un
  top-6 valid sub `p̂` independent (`min p̂_bilet ≥ max p̂_rest − 1e-12`);
- verifică hash-ul predicțiilor; hits exacte, sume de scor cu toleranță `1e-6`.

Status PASS numai dacă toate verificările trec. UNKNOWN nu devine PASS.

## 8. Lecția de proces aplicată (din WU649)

Martorul de decizie Q6 și martorul de informație Q5 sunt derivați ANALITIC înainte de sigilare
(Derivarea A: sector invariant, valori proprii în formă închisă, ticket determinat exact, fără
efecte de ordinul doi cu semn ghicit). Valorile numerice de mână servesc numai la marje; Q5/Q6
le recalculează exact în Q.
