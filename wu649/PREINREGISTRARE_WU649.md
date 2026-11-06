# PREINREGISTRARE WU649 — „Urna ponderată” (cursa exponențială Luce, ordine nevăzută marginalizată)

Versiune protocol: `WU649-P1`. Scris și sigilat (SHA-256 în `SIGILIU_PROTOCOL_WU649.json`)
ÎNAINTE de scrierea oricărui cod WU649 și înainte de orice calcul WU649 (pe date reale,
sintetice sau construite). Ipoteză NOUĂ și DISTINCTĂ în pista QL649. Nu salvează, nu repară
și nu re-parametrizează QL649 (închis `QL_NO_PROMOTION_EXPLORATORY`, 0/6), BO649 (închis
`BO_NO_PROMOTION_EXPLORATORY`, 0/6) sau DL-649 (înghețat, revizia `20261025T165403Z`, neatins).
Modelele închise nu se importă și nu se rulează. OGLINDA nu este atinsă.

Calcul clasic: NumPy `float64` pe CPU (procese paralele pe pași independenți) pentru rulări,
aritmetică rațională exactă (`fractions.Fraction`, în Q) pentru certificate. Fără hardware
cuantic, fără avantaj cuantic, fără noutate mondială revendicată. „Cursa” și „ceasurile
Poisson” sunt construcții probabilistice clasice. `positive_claims_allowed=false`. Arhiva este
deja explorată în proiect: valoare confirmatoare 0, nu set nevăzut.

Precedente atribuite: R. D. Luce, *Individual Choice Behavior* (1959) — axioma alegerii;
R. L. Plackett, „The analysis of permutations” (1975); K. T. Wallenius (1963), distribuția
hipergeometrică necentrală a extragerii ponderate fără întoarcere; J. I. Yellott, „The
relationship between Luce's choice axiom, Thurstone's theory of comparative judgment, and the
double exponential distribution” (1977) — reprezentarea prin curse; D. R. Hunter, „MM
algorithms for generalized Bradley–Terry models” (Ann. Statist., 2004); F. Caron, A. Doucet,
„Efficient Bayesian inference for generalized Bradley–Terry models” (JCGS, 2012); cuadratura
tanh-sinh: H. Takahasi, M. Mori (1974). Formula prin includere–excludere pentru mulțimea
primilor κ sosiți într-o cursă exponențială este clasică; aici este doar re-derivată și
certificată. Contribuția proprie este numai aplicarea pe 6/49 cu protocolul, martorii și
porțile de mai jos.

## 0. Ipoteza, informația pre-țintă, motivul unei decizii diferite, distinctitate

- **Ipoteză H_WU:** fiecare bilă j are o propensiune fizică constantă `w_j > 0` (masă,
  diametru, suprafață). Mașina extrage κ bile secvențial, fără întoarcere: la fiecare etapă,
  o bilă rămasă este aleasă cu probabilitate proporțională cu `w` (axioma Luce). Echivalent
  (Yellott): fiecare bilă are un ceas exponențial independent `T_j ~ Exp(w_j)`, iar extragerea
  este mulțimea primelor κ sosiri. Ordinea fizică NU este observată; verosimilitatea unei
  mulțimi se obține marginalizând exact peste ordine.
- **Informație pre-țintă:** numai mulțimile extrase în pașii `< k` (zile calendaristice, ca în
  QL649 §1–2). Fără calendar, tip de extragere, ordinea bilelor sau surse externe.
- **De ce decizia diferă de repere:** B (frecvențe `c+1`) folosește aproximarea produs-
  Bernoulli/multinomială, în care numărările sunt statistici suficiente. Sub H_WU numărările
  NU sunt suficiente: verosimilitatea exactă fără întoarcere depinde și de compoziția fiecărei
  extrageri. O bilă care „câștigă” (intră în mulțime) în fața unor bile puternice, rămase
  afară, primește mai multă greutate decât una care câștigă doar în fața unor bile slabe; o
  bilă care „pierde” în fața unor bile slabe primește mai puțină (analogul „tăriei
  calendarului” din Bradley–Terry). La numărări egale, WU poate ordona diferit, deci biletul
  diferă de B. Față de R (fereastră exponențială) și BO (regimuri), WU este schimbabil:
  aceeași istorie în altă ordine temporală dă EXACT aceeași predicție (cu toleranță numerică).
  Folosește compoziția, nu ordinea. Legea WU este probabilitatea exactă de includere sub
  extragerea ponderată fără întoarcere (neliniară în w), nu `π ∝ c+1`.
- **Infirmare:** eșecul porților §5 pe backtestul unic. Dacă extragerile sunt uniforme și
  independente, H_WU cu w neconstant este falsă și nu se așteaptă niciun avantaj.
- **Distinctitate (căutare țintită, 25 oct 2026, în `next_candidate/`):** termenii
  `plackett|wallenius|luce|bradley|noncentral|necentral` apar numai în:
  (a) `cercetare_originala_20261020/IDEI_SI_FEZABILITATE.md` H1 — Plackett–Luce cu atribute
  fizice MĂSURATE și ordine verificată, stare `DATE_INSUFICIENTE`, niciodată rulat; WU nu
  folosește atribute externe și nici ordine, ci propensiuni latente deduse doar din mulțimi;
  (b) R1/M1/PM — Fisher necentral ca model de putere pentru un grup fix, mecanism de memorie
  față de mulțimea precedentă (greutate 2 în generator sintetic) sau prior mixt pe suprapuneri;
  nu estimează 49 de propensiuni cu verosimilitatea exactă fără întoarcere;
  (c) N3 — cere ordine fizică verificată (absentă). Familiile pe perechi/grafuri/simpliciale
  (DL, PG, CF, LS, FS, AT, RA, D, QL649) au parametri sau descriptori de ordinul doi; WU are
  numai 49 de parametri de ordinul întâi. Familiile temporale (BO, SR, G, MI, EX, AO, OR,
  CR, AC, S, TI, TP, OC, N1, N2) folosesc ordinea sau calendarul; WU este invariant la ordine.

## 1. Date (identice cu QL649 §1)

`parser.py` din QL649 (doar ingestie: curățare, ordonare, pași-zi; nu este model). SHA-256 al
sursei și al `parser.py` se înregistrează în `START.json`. Ținte = toate extragerile din
pașii `k ≥ 100`. Extragerile din aceeași zi primesc aceeași predicție.

## 2. Modelul WU (hiperparametri fixați a priori)

Generic pe `N` bile și `κ` bile pe extragere (real: `N=49`, `κ=6`); `θ_j = log w_j`.

- **Verosimilitatea unei mulțimi S** (`|S| = κ`, `S^c` = restul, `W_c = Σ_{l∈S^c} w_l`):
  `P(S | w) = P(max_{i∈S} T_i < min_{l∈S^c} T_l)`. Forme egale:
  1. suma pe cele κ! ordini: `Σ_σ Π_{m=1..κ} w_{σ_m} / (W − Σ_{l<m} w_{σ_l})`, `W = Σ_j w_j`;
  2. includere–excludere (exactă în Q): `Σ_{A⊆S} (−1)^{|A|} W_c / (W_c + w_A)`;
  3. integrala pe `u = e^{−x} ∈ (0,1)`: `∫_0^1 W_c u^{W_c−1} Π_{i∈S} (1 − u^{w_i}) du`;
  3'. aceeași integrală după substituția `s = u^{W_c}`: `∫_0^1 Π_{i∈S} (1 − s^{w_i/W_c}) ds`.
  Rularea `float64` folosește forma 3' (integrand în [0,1], pozitiv, fără anulări și fără
  singularitate nemărginită la capăt), în domeniu log.
- **Probabilitatea de includere** pentru extragerea următoare:
  `π_j(w) = ∫_0^1 w_j u^{w_j−1} · P(N_{−j}(u) ≤ κ−1) du`, unde `N_{−j}(u)` este numărul
  celorlalte bile sosite, binomial-Poisson cu `p_l = 1 − u^{w_l}`. Rularea folosește
  substituția `v = u^{w_j}`: `π_j = ∫_0^1 P(N_{−j} ≤ κ−1) dv`, cu `p_l = 1 − v^{w_l/w_j}`
  (integrand în [0,1]; programare dinamică trunchiată la κ). Identitate: `Σ_j π_j = κ`.
- **Cuadratura:** tanh-sinh pe (0,1): `t_k = k·h`, `h = 1/16`, `|k| ≤ 64` (129 de noduri),
  nod `x_k = 1/(1+e^{−π sinh t_k})`, `log x_k` și `1−x_k` calculate direct (stabil), pondere
  `h·π·cosh(t_k)·x_k(1−x_k)`. `1 − x^a` se calculează ca `−expm1(a·log x)`.
  Certificat de precizie: comparația cu `h = 1/32`, `|k| ≤ 128` (§4).
- **Derivate:** `log P(S)` depinde numai de `d_i = θ_i − log W_c` (i ∈ S); gradientul și
  hessiana în θ se obțin analitic din momentele integrandului 3' și regula lanțului prin
  `log W_c = logsumexp(θ_{S^c})`.
- **Prior:** `θ_j ~ N(0, σ²)` independente, **`σ = 0.2`**. Justificare a priori: un efect
  suficient pentru poarta 1 (exces 0.20 pe bilet) cere `|θ| ≈ 0.3` pe numerele favorizate,
  adică circa 1.5σ — plauzibil sub H_WU, fără să fie impus. Priorul izotrop fixează și
  invarianța de scară a modelului Luce: la staționaritate, `Σ_j θ̂_j = 0`.
- **Estimare la pasul k:** MAP `θ̂(k)` = argmax al `Σ_{extrageri în pașii <k} log P(S|e^θ)
  − |θ|²/(2σ²)`. Newton pornit ÎNTOTDEAUNA din `θ = 0` (fără pornire caldă, deci fiecare pas
  depinde numai de prefixul său, iar pașii se pot calcula în paralel cu rezultate identice
  bit cu bit). Gradientul și hessiana sunt analitice prin aceeași cuadratură. Dacă `−H` nu
  este pozitiv definită (Cholesky eșuează), se folosește `−H + μI`, cu `μ` dublat pornind de
  la `1e-6·max|H|`. Pasul are backtracking Armijo (`c = 1e-4`, înjumătățire, cel mult 60).
  Oprire la `‖g‖_∞ ≤ 1e-8`, cel mult 200 de iterații.
  **Certificat de pas:** `‖g‖_∞ ≤ 1e-8` ȘI `−H` pozitiv definită (Cholesky) la `θ̂`. Este un
  certificat de optim LOCAL strict; concavitatea globală nu este presupusă.
- **Predicția:** `q_j(k) = π_j(e^{θ̂(k)})`.
- **Legea marginală WU:** aceeași regulă ca pentru QL, B, R, BO, cu `π = q/κ`:
  `q_law = 6/49 + λ(6π − 6/49)`, `λ = min(0.5, λ_max)`, `q_law ∈ [1e-4, 1−1e-4]`.
- **Biletul WU:** top-6 după `q` (echivalent după `θ̂`, deoarece `π_j` crește strict în
  `w_j`); la egalitate se alege numărul mai mic (sortare stabilă).

## 3. Comparatori, scoruri, jumătăți (identici cu QL649 §5 și BO649 §3)

U (`q = 6/49`). B: `π_B ∝ c_j+1` (toată istoria). R: `π_R ∝ ew_j+0.5`, cu
`ew_j = Σ 2^{−(k−1−s)/26}` peste extragerile din pașii `s<k`. Biletele B/R sunt top-6; la
egalitate se alege numărul mai mic. Legile B/R folosesc aceeași regulă λ. Pe fiecare țintă:
hits = `|bilet ∩ extragere|`; log = `Σ_j y_j log q_j + (1−y_j) log(1−q_j)`;
Brier = `Σ_j (q_j − y_j)²`; Exces = `hits/ținte − 36/49`. Jumătățile sunt cronologice: prima
are `floor(n/2)` ținte.

## 4. Calificare (înainte de istoria reală; numai date construite sau sintetice)

Experimentul pe arhivă rulează NUMAI dacă toate verificările sunt PASS:

- **Q1 exactitate în Q** (cel puțin 40 de instanțe, seed `[649, 8, 1]`, `N ∈ {4,5,6}`,
  `κ ∈ {2,3}`, `κ < N`, ponderi raționale `w_i = a_i/b_i`, `a_i ∈ {1..9}`, `b_i ∈ {1..4}`):
  1. pentru fiecare κ-submulțime S: forma 1 (suma pe ordini) = forma 2 (includere–excludere),
     EXACT în Q; `Σ_S P(S) = 1` exact;
  2. cuadratura `float64` a formei 3' vs valoarea exactă: eroare relativă `≤ 1e-12`;
  3. `π_j` exact (sumă în Q peste mulțimile care conțin j) vs cuadratură: `≤ 1e-12` absolut;
     `Σ_j π_j = κ` exact în Q;
  4. gradientul și hessiana lui `log P(S)` în θ: cuadratură vs derivatele exacte raționale
     ale formei 2: eroare `≤ 1e-10` (relativă la `max(1, |valoare|)`);
  5. MAP multi-start: pe fiecare instanță, o istorie de `T ∈ {8..20}` extrageri eșantionate
     secvențial după Luce cu ponderile instanței (seed fix); MAP din 8 porniri (`θ=0` și 7
     porniri `N(0,1)`): toate cu certificat de pas și `max|Δθ̂| ≤ 1e-8` între porniri.
- **Q2 identități pe un univers nul sintetic complet** (structura reală a pașilor, extrageri
  uniforme 6-din-49, seed `[649, 8, 999]`), rulare walk-forward completă: la fiecare pas
  `|Σ_j q_j − κ| ≤ 1e-10`, `0 < q < 1`, certificat de pas valid și `|Σ_j θ̂_j| ≤ 1e-7`; la
  pașii din 97 în 97, cuadratura cu `h = 1/32` dă `max|Δq| ≤ 1e-11`.
- **Q3 cauzalitate:** pentru pașii k din 97 în 97, predicțiile calculate din istoria
  trunchiată la `<k` sunt IDENTICE bit cu bit cu cele din rularea completă.
- **Q4 echivarianță:** o permutare fixă σ a etichetelor (seed `[649, 8, 4]`) permută `q` cu
  toleranță `1e-9`, la pașii din 97 în 97 ai universului Q2.
- **Q5 martor de informație** (fixture construit determinist, o extragere pe pas, `N=49`):
  `rest = (8, 9, …, 49)` (42 de numere); pentru `i = 0..399`, ciclul i are, în ordine:
  `β_i = {7} ∪ {rest[(5i+m) mod 42] : m=0..4}`, `γ_i = {rest[(6i+m+21) mod 42] : m=0..5}`,
  `α = {1,2,3,4,5,6}`. Istoria H+ are 1200 de pași. H− = H+ cu etichetele 6 și 7
  interschimbate în fiecare extragere. Numărările pe etichete sunt identice (6 și 7 apar
  fiecare de 400 de ori), deci legea și biletul B trebuie să fie identice exact; cerința:
  `max_j |q_WU(H+) − q_WU(H−)| ≥ 1e-3` pentru predicția pasului 1200. Suplimentar
  (invarianță la ordine): H+ într-o ordine temporală permutată fix (seed `[649, 8, 5]`) dă
  `q_WU` identic cu toleranță `1e-9`.
- **Q6 martor de decizie:** pe H+ (predicția pasului 1200), biletul WU diferă, ca mulțime,
  atât de biletul B, cât și de biletul R. (Anticipare scrisă înainte de calcul: bila 7
  câștigă în fața bilelor grele 1–6 rămase afară și pierde în fața celor ușoare, deci
  `q_7 > q_6`; B are egalitate 1–7 și alege `{1..6}`; R favorizează α, care încheie fiecare
  ciclu, deci tot `{1..6}`. Dacă anticiparea este greșită, Q6 eșuează și se publică.)

Rezultat `WU_QUALIFIED` (6/6) sau `WU_NOT_QUALIFIED`. Dacă nu se califică, rezultatul se
publică, codul rămâne condiționat NEVALIDAT și istoria reală nu se atinge. Defectele tehnice
ale implementării (nu ale ipotezei) descoperite în calificare se tratează prin amendament
scris și sigilat ÎNAINTE de orice acces la istoria reală, cu încercarea inițială păstrată.

## 5. Backtest walk-forward unic pe arhivă și porți (toate 6 necesare)

1. `ExcesWU/U ≥ 0.20`;
2. `hitsWU > hitsB` și `hitsWU > hitsR`;
3. `logWU − logU > 0` și `logWU − logB > 0`;
4. `BrierWU < BrierU, BrierB, BrierR`;
5. în ambele jumătăți: exces `> 0` și `hitsWU − hitsB > 0`;
6. în ambele jumătăți: `logWU − logB > 0`.

Verdict `WU_PROMOVAT_EXPLORATORIU` (6/6), altfel `WU_NO_PROMOTION_EXPLORATORY`. Și la 6/6
rămâne `positive_claims_allowed=false`; ar urma o confirmare prospectivă separată. Rularea
are loc O SINGURĂ dată; `START.json` blochează repetarea. Predicțiile (`θ̂`, `q`, bilete,
certificatele de pas) se scriu și se sigilează SHA-256 ÎNAINTE de scor. Dacă vreun pas real
nu are certificat valid, scorul NU se calculează: defectul se tratează prin amendament
scris, iar încercarea inițială se păstrează. Rezultatul se publică indiferent de verdict.
Fără tuning după vizualizare.

## 6. Descriptiv (nu intră în porți și nu schimbă verdictul)

- p exact pentru hits sub extrageri uniforme independente (convoluție hipergeometrică);
- numărul de pași-țintă în care biletul WU diferă de B, respectiv de R;
- la pasul final: abaterea standard, minimul și maximul lui `θ̂`, corelația Spearman între
  `θ̂` și numărări, și `log P(date|θ̂) − log P(date|θ=0)` (în eșantion, descriptiv);
- verificarea cuadraturii `h = 1/32` la pașii reali din 97 în 97;
- **32 de universuri nule** sintetice cu aceeași structură de pași, extrageri uniforme
  6-din-49 fără întoarcere, seed `[649, 8, u]`, `u = 0..31`: WU, comparatori, porți;
  distribuția excesului, a lui `logWU−B`, a porților trecute și rangul empiric al valorilor
  reale;
- **sensibilitate declarată acum:** `σ ∈ {0.05, 0.2, 0.8}` pe arhivă, aceleași scoruri.
  Strict descriptiv; nicio configurație alternativă nu poate fi promovată, selectată sau
  folosită ulterior ca „variantă reparată”.

## 7. Verificare independentă

`verify_wu649.py` NU importă `wu649.py`, `bo649.py`, `engine.py`, `parser.py` sau
`validare.py`. Script-ul:
- reparsează JSONL după §1 și verifică SHA-256, numărul de extrageri și pașii;
- recalculează comparatorii B/R, scorurile, porțile și verdictul;
- folosește o cuadratură DIFERITĂ (Gauss–Legendre cu 200 de noduri pe `u ∈ (0,1)`, spațiu
  de probabilitate) și o implementare proprie a gradientului;
- la FIECARE pas: `‖g(θ̂_model)‖_∞ ≤ 1e-6` în formularea independentă și `−H` pozitiv
  definită; `q` recalculat din `θ̂_model` cu `max|Δq| ≤ 1e-9`; biletul modelului este un top-6
  valid sub `q` independent (`min q_bilet ≥ max q_rest − 1e-9`) și coincide cu regula top-6
  aplicată pe `q` salvat;
- la pașii din 25 în 25: re-optimizare completă independentă din `θ=0`, `max|Δθ̂| ≤ 1e-7`;
- identitatea cursei pe date reale: la 200 de extrageri reale eșantionate fix, la `θ̂` final,
  forma 1 (720 de ordini, `float64`) vs cuadratura independentă: eroare relativă `≤ 1e-10`;
- verifică hash-ul predicțiilor; hits exacte, sume de scor cu toleranță `1e-6`.

Status PASS numai dacă toate verificările trec. UNKNOWN nu devine PASS.
