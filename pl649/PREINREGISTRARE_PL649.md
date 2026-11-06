# PREINREGISTRARE PL649 — „Singularitatea Planck” (rețea de spin + holonomii SU(3) + vid Higgs)

Versiune protocol: `PL649-P1`. Scris și sigilat (SHA-256 în `SIGILIU_PROTOCOL_PL649.json`) ÎNAINTE de
scrierea oricărui cod PL649 și înainte de orice calcul PL649 pe date reale, sintetice sau construite.
Singurele calcule anterioare sunt evaluarea formulelor ÎNCHISE ale martorilor din §5, derivate de mână
(`jurnal/preprotocol/calculator_constante.py`, fără model și fără date; ieșirea în
`jurnal/preprotocol/constante_preprotocol.json`). Răspunde cererii utilizatorului din 26 oct 2026
08:37 (−04:00), „PROTOCOLUL DE MUTAȚIE CORE V2.0”, păstrată exact în `predari/MESAJE_UTILIZATOR_QL649.md`
(Mesajul 24).

## 0. Încadrare onestă și abateri declarate de la formularea literală a cererii

- **Calculul este CLASIC.** O placă NVIDIA RTX 5060 (3.328 nuclee CUDA, 8 GB VRAM) execută aritmetică
  clasică în virgulă mobilă; nu există „ieșire” din calculul clasic pe acest hardware. Termenii LQG,
  spumă de spin, SU(3) Yang–Mills, Higgs, monopol sunt INSPIRAȚIE MATEMATICĂ: folosim exact structurile
  algebrice declarate mai jos (spectrul de arie `√(j(j+1))`, grupul SU(3) cu matricele Gell-Mann, bucle
  Wilson, potențial φ⁴ cu rupere de simetrie, vortexuri XY), fără nicio pretenție fizică. Fără hardware
  cuantic, avantaj cuantic sau noutate mondială. `positive_claims_allowed=false`.
- **Fizică:** nu există niciun mecanism cunoscut prin care geometria la scara Planck (~1.6·10⁻³⁵ m) sau
  câmpurile de culoare să influențeze bile de ordinul centimetrilor într-o urnă; separarea de scară este
  de ~33 de ordine de mărime. Probabilitatea a priori a lui H_PL (§1) este practic zero. Experimentul
  este o transformare matematică a istoricului, testată o singură dată, cu aceleași porți ca toate pistele.
- **`engine.py` și `parser.py` NU se modifică.** `engine.py` (sha256 `1da9be4e…2cb2ae`) este codul sigilat
  al backtestului unic QL649 (în `rezultate/backtest_unic/START.json`); cererea cere și conservarea
  intactă a artefactelor QL649. Noul nucleu se scrie în `pl649/pl_core.py` (motorul v2.0, PyTorch CUDA
  nativ); `parser.py` se folosește read-only pentru ingestie. `app.py` primește ADITIV al 12-lea tab
  („🌌 Orizontul evenimentelor (PL649)”), celelalte 11 rămân neschimbate.
- **Volumul** folosit este un PROXY (§3.2), nu operatorul de volum Ashtekar–Lewandowski/Rovelli–Smolin.
  „Monopolii cromodinamici” sunt vortexuri XY într-un model Kuramoto pe rețeaua de spin (§8), nu monopoli
  QCD. Anealerul Higgs este o dinamică Langevin clasică pe GPU; „starea de vid fundamental” a biletelor
  este certificată EXACT prin enumerarea completă a celor C(49,6) = 13.983.816 bilete pe GPU (§3.5).
- **Cele 3 variante** produse în UI nu sunt „puncte de colaps pentru următoarea extragere” în sens
  predictiv: sunt minimele exacte ale unei energii definite aici. Dacă extragerile sunt uniforme și
  independente, nicio funcție a istoricului nu oferă avantaj.

Precedente atribuite: C. Rovelli, L. Smolin (1995) și A. Ashtekar, J. Lewandowski (1997) — spectrele
operatorilor de arie/volum în LQG; R. Penrose (1971) — rețele de spin; J. Baez (1998), J. Engle,
E. Livine, R. Pereira, C. Rovelli (2008) — spume de spin; K. Wilson (1974) — bucle Wilson și teoria gauge
pe rețea; M. Gell-Mann (1962) — baza su(3); C. N. Yang, R. Mills (1954); P. Higgs (1964), J. Goldstone —
ruperea spontană a simetriei; Y. Kuramoto (1975); J. M. Kosterlitz, D. J. Thouless (1973) — vortexuri XY;
S. Kirkpatrick et al. (1983) — anealing simulat; QUBO/Ising (Lucas 2014). Contribuția proprie: numai
maparea pe 6/49 de mai jos, protocolul, martorii analitici și porțile.

## 1. Ipoteza, informația pre-țintă, motivul unei decizii diferite, distinctitate

- **Ipoteză H_PL:** propensiunea unei bile scade cu „curbura gauge” locală a nodului ei într-o rețea de
  spin construită din istoric: legăturile (perechi co-extrase) poartă spini `j = n_ab/2`, iar fiecare
  co-extragere aplică legăturii un „transport paralel” SU(3) ne-abelian orientat după vechimea ultimei
  apariții; nodurile cu holonomii aproape triviale (curbură mică) sunt favorizate. Premisa nu are nicio
  justificare fizică (§0); este o ipoteză infirmabilă.
- **Informație pre-țintă:** extragerile din pașii `< k*`, în ordinea lor: numărările pe perechi
  (spinii), ORDINEA co-extragerilor fiecărei perechi (indicele generatorului) și orientarea fiecărei
  co-extrageri după vechimea ultimei apariții a celor două bile (pași strict anteriori). Fără date
  calendaristice, fără structura etichetelor, fără ordinea fizică a bilelor, fără surse externe.
- **De ce nu e infirmată de eșecul lui B și al familiilor de perechi:** predictorul este o funcție a
  buclelor Wilson ne-abeliene, care depind de ORDINEA și ORIENTAREA co-extragerilor; două istorii cu
  EXACT aceeași multi-mulțime de extrageri (deci aceleași numărări, aceleași numărări pe perechi,
  aceleași arii, volume și orice descriptor de compoziție) pot da legi diferite (martorul analitic Q5:
  o istorie dă lege uniformă exactă, cealaltă nu). Este invariant la transformări gauge locale SU(3).
- **De ce decizia diferă de repere:** biletul este starea de energie minimă EXACTĂ a unui QUBO cu termen
  de nod (curbura) și termen de pereche (curbura pe muchie), nu top-6 după numărări (B) sau recență (R);
  martorul Q6 dă bilete diferite de B și disjuncte de R.
- **Infirmare:** eșecul porților §6 la backtestul unic.
- **Distinctitate (căutare țintită, 26 oct 2026, 12:45Z, `grep -rIil` în `next_candidate/` pe
  `*.py|*.md|*.json`, fără `.venv`):** termenii `gell-mann|su(3)|su3|wilson|holonom|gauge|spin network|
  spinfoam|spin foam|loop quantum|yang-mills|higgs|plaquet|vortic|vortex|lattice gauge|area operator`
  apar numai ca: „fără gauge” într-o probă exactă (incertitudine uniformă), variabila `su3` (tuplu) în
  CF/technical.py, intervale Wilson (statistică) în `loto_romania/` și FEASIBILITY. Nicio familie nu
  folosește conexiuni SU(3), holonomii sau bucle Wilson. Cele mai apropiate familii închise: DL
  (proiecții Lüders secvențiale ne-comutative pe segment; aici: transport unitar SU(3) pe MUCHII și bucle
  pe triunghiuri, nu proiecții de stare pe noduri), RH (stare unitară Householder–Coxeter pe noduri), CF
  (curbură Foster–Kirchhoff, comutativă, pe 1-schelet), LS (descriptori simpliciali comutativi pe fețe),
  PG (Plücker), QL649 (Kuramoto/QUBO/MCMC; aici Kuramoto este numai descriptiv §8, iar QUBO-ul este
  minimizat EXACT, nu prin MCMC). PL nu reutilizează rezultatele niciunei familii.

## 2. Date (identice cu QL649 §1)

`parser.py` din QL649, read-only (curățare, ordonare, pași-zi). SHA-256 al sursei și al `parser.py` în
`START.json`. Ținte = toate extragerile din pașii `k ≥ 100`; extragerile din aceeași zi primesc aceeași
predicție.

## 3. Modelul PL (constante fixate a priori; fără grilă)

Constante: `ε = π/32`, `β = 1/2`, `η = 1/8`, `ρ = 1/2` (numai produs), `τ_E = 1e-9`, `τ_sd = 1e-12`.

### 3.1 Conexiunea SU(3) (legăturile)
- Matricele Gell-Mann standard `λ1..λ8` (λ8 = diag(1,1,−2)/√3). Pentru fiecare pereche neordonată
  {a,b} se stochează `U_ab = U_{a→b} ∈ SU(3)` pentru a < b, cu `U_{b→a} = U_ab†`; inițial `I`.
- Vechimea: `g_x(s)` = cel mai mare indice de pas `s' < s` în care x a apărut (−∞ dacă niciunul).
- Extragerile se procesează în ordinea arhivei. Pentru extragerea din pasul s și fiecare pereche {a,b}
  a ei, fie `m` numărul de co-extrageri anterioare ale perechii și `E = exp(i ε λ_{1+(m mod 8)})`:
  dacă `g_a(s) < g_b(s)` (a mai vechi): `U_{a→b} ← E·U_{a→b}`; dacă `g_b(s) < g_a(s)`: `U_{b→a} ← E·U_{b→a}`
  (adică `U_ab ← U_ab·E†`); la egalitate (inclusiv ambele −∞): fără impuls. Apoi `m ← m+1` (și la egalitate).
- Implementare: `torch.linalg.matrix_exp` în motor; verificatorul folosește forma închisă
  (`e^{iελ} = I + i sin ε λ + (cos ε − 1) λ²` pentru λ1..λ7, diagonală pentru λ8).

### 3.2 Rețeaua de spin, aria și volumul-proxy
- `n_ab` = numărul de extrageri anterioare care conțin ambele bile; spin `j_ab = n_ab/2`; aria legăturii
  (unități `8πγℓ_P² = 1`) `a_ab = √(j_ab(j_ab+1))`. Aria nodului `A_a = Σ_b a_ab`; spectrul de arie =
  multi-mulțimea valorilor `a_ab`.
- `S` (49×49, real) cu `S_ab = √a_ab`, `S_aa = 0`; volumul-proxy `V_a = Σ_{b<c} √(a_ab a_ac a_bc) = (S³)_aa/2`
  (dimensional arie^{3/2}); NU este operatorul de volum LQG.

### 3.3 Buclele Wilson și curbura (invariante gauge)
- `M` (147×147 complex) cu blocurile `M_ab = √a_ab · U_{a→b}`, `M_aa = 0`. Pentru triunghiul (a,b,c):
  `W_abc = U_{a→b} U_{b→c} U_{c→a}`, pondere `w_abc = √(a_ab a_bc a_ca)`.
- Curbura pe muchie: `ε_ab = 1 − Re tr(M_ab (M²)_ba) / (3 √a_ab (S²)_ab)` dacă numitorul > 0, altfel 0
  (= media ponderată a lui `1 − Re tr W_abc/3` peste triunghiurile muchiei).
- Curbura nodului: `κ_a = 1 − Σ_b Re tr(M_ab (M²)_ba) / (3 (S³)_aa)` dacă `(S³)_aa > 0`, altfel 0
  (= media ponderată a lui `1 − Re tr W_abc/3` peste triunghiurile nodului). O singură înmulțire `M·M`
  pe GPU dă toate buclele Wilson ale celor 18.424 de triunghiuri.
- Toate mărimile sunt invariante la `U_ab → g_a U_ab g_b†` (g_a ∈ SU(3) arbitrare) și la orientare.

### 3.4 Legea PL
- `z = (κ − mean κ)/sd κ` (sd populațional peste 49; dacă `sd ≤ τ_sd`, z = 0);
  `π_a = exp(−β z_a) / Σ_b exp(−β z_b)` (curbură mică ⇒ propensiune mare).
- Legea marginală (aceeași regulă ca la QL/B/R/BO/GL/SE/CS): `q_law = 6/49 + λ(6π − 6/49)`,
  `λ = min(0.5, λ_max)`, `λ_max` menține `q_law ∈ [1e-4, 1−1e-4]`.

### 3.5 Biletul: vidul Higgs certificat exact (QUBO)
- `ζ_ab = (ε_ab − mean ε)/sd ε` peste toate cele 1176 de muchii (sd ≤ τ_sd ⇒ ζ = 0).
- Energia biletului s (|s| = 6): `E(s) = Σ_{a∈s} β z_a + η Σ_{a<b∈s} ζ_ab` (fp64).
- **Biletul PL** = primul bilet în ordine lexicografică dintre cele cu `E ≤ E_min + τ_E`, prin enumerarea
  COMPLETĂ a celor 13.983.816 bilete pe GPU (fp64).
- **Produs (UI, nu intră în porți):** varianta 1 = biletul PL; varianta k = 2, 3 minimizează
  `E(s) + ρ Σ_{v<k} |s ∩ v|` peste biletele diferite de variantele anterioare (aceeași regulă de egalitate).
- **Anealerul Higgs** (§8) caută aceleași minime prin rupere de simetrie pe 50.000 de replici;
  rezultatul lui se compară cu enumerarea exactă (certificat), nu o înlocuiește.

### 3.6 Estimări de mână (fără date)
- Sub nul (extrageri uniforme), legea PL are abatere relativă `0.5·β·z_j`; costul așteptat al
  scorului log față de U ≈ `−0.855 β²` pe țintă ≈ −0.214 ⇒ **≈ −530 pe 2495 de ținte**. Poarta 3 este
  deci aproape imposibilă sub nul; un `logPL−U` de acest ordin NU este o surpriză și nu se repară.
- Într-o lume H_PL auto-consistentă cu propensiunea `∝ exp(−γ z)`: oracolul are excesul ≈ `1.18·γ`
  (Blom): γ = 1/2 ⇒ ≈ 0.5–0.6 (poarta 1 accesibilă); γ = 1/8 ⇒ ≈ 0.12–0.15 (inaccesibilă). Lecția
  CS649/SE649: estimările de mână au fost optimiste cu ~15%.

## 4. Comparatori, scoruri, jumătăți (identici cu QL649 §5 … CS649 §3)

U (`q = 6/49`). B: `π_B ∝ c_j+1`. R: `π_R ∝ ew_j+0.5`, `ew_j = Σ 2^{−(k−1−s)/26}`. Bilete B/R top-6, la
egalitate numărul mai mic. hits, log, Brier, Exces = hits/ținte − 36/49, jumătăți cronologice (prima
`floor(n/2)`). Control de consecvență (condiție de validitate, nu poartă): `hitsB = 1847`,
`hitsR = 1821`, 2495 de ținte; altfel nu se publică drept rezultat și defectul se tratează prin amendament.

## 5. Calificare (numai date construite sau sintetice; arhiva reală neatinsă)

Experimentul pe arhivă rulează NUMAI dacă Q1–Q6 sunt toate PASS.

- **Q1 exactitatea implementării** (40 de instanțe, seed `[649, 12, 1]`; n pași uniform 1..40, fiecare
  pas cu 2 extrageri cu prob. 0.15, altfel 1; extrageri uniforme): (i) κ și ε prin `M²` pe GPU = calculul
  explicit triunghi cu triunghi pe CPU (NumPy, exponențiale în formă închisă), `|Δ| ≤ 1e-12`;
  (ii) `max‖U†U − I‖ ≤ 1e-12`, `max|det U − 1| ≤ 1e-12`; (iii) invarianța gauge: g_a ∈ SU(3) aleatoare
  (seed `[649, 12, 11]`) lasă κ, ε, π neschimbate (`≤ 1e-10`); (iv) la 3 instanțe, biletul QUBO prin
  enumerare pe GPU = biletul prin enumerare pe CPU, energiile minime egale în `1e-9`.
- **Q2 identități pe un univers nul sintetic complet** (structura reală a pașilor, numai numărul de
  extrageri pe zi; extrageri uniforme, seed `[649, 12, 999]`), walk-forward complet: la fiecare pas-țintă
  `|Σπ − 1| ≤ 1e-12`, `0 < q_law < 1`, κ finit; eroarea de unitaritate `≤ 1e-10`; la pașii din 97 în 97,
  starea incrementală (numărări, vechimi, m — egalitate exactă; legături `≤ 1e-12`) = starea recalculată
  de la zero.
- **Q3 cauzalitate:** la pașii din 97 în 97, predicțiile din istoria trunchiată (π `≤ 1e-12`, bilet
  identic) = cele din rularea completă.
- **Q4 echivarianță:** permutare fixă a etichetelor (seed `[649, 12, 4]`): `π(σH) = σπ(H)` (`≤ 1e-10`) la
  pașii din 97 în 97 ai universului Q2; biletul permutat identic la toți pașii verificați cu decalajul
  energetic `E₂ − E₁ > 1e-6` (al doilea minim distinct), iar acești pași sunt ≥ 90% din cei verificați.
- **Q5 martor de informație (analitic):** `D1 = {1..6}` (pas 0), `D2 = {7..12}` (pas 1),
  `D3 = {1, 7, 13, 14, 15, 16}` (pas 2); `H+ = (D1, D2, D3)`, `H− = (D1, D3, D2)`, ținta k* = 3.
  Derivare: în H+ singurele impulsuri sunt cele din D3 (λ1, m = 0): `U_{1→7}`, `U_{x→1}`, `U_{x→7}` (x = 13..16)
  egale cu `e^{iελ1}`; buclele (1,7,x) dau `W = e^{iελ1}`, `1 − Re tr W/3 = c = (2/3)(1 − cos ε)`, toate
  celelalte bucle sunt `I`; toate muchiile au j = 1/2 (ponderi egale). Deci `κ_1 = κ_7 = c/5` (4 din 20
  triunghiuri), `κ_13..16 = c/10` (1 din 10), restul de 43 = 0. În H− conexiunea este plată (toate buclele
  `I`): κ ≡ 0 ⇒ π uniformă EXACT (prin regula `τ_sd`). Cerințe:
  (a) H+ și H− au aceleași numărări, aceleași `n_ab`, aceleași `A_a`, `V_a` și aceeași lege și același bilet B;
  (b) H−: `max|π − 1/49| ≤ 1e-12`;
  (c) H+: `κ_1 = κ_7 = c/5 = 6.420364437070761e-04`, `κ_13..16 = c/10 = 3.210182218535380e-04` (relativ
      `1e-9`), restul `|κ| ≤ 1e-14`;
  (d) H+: `π_1 = 2.636081961502316e-03`, `π_13 = 7.687388882360370e-03`, `π_2 = 2.241809954761753e-02`
      (relativ `1e-9`), iar `q_law,2 − q_law,1 = 0.0593460527583457 ≥ 1e-3`;
  (e) martor ne-abelian, fixture `N`: `X1 = {1..6}`, `X2 = {2, 7..11}`, `X3 = {1, 2, 12..15}`,
      `X4 = {2, 16..20}`, `X5 = {1, 2, 21..24}` (pașii 0..4), ținta 5. Muchia {1,2}: X1 egalitate (m→1),
      X3 impuls λ2, X5 impuls λ3, ambele cu 1 mai vechi ⇒ `U_{1→2} = e^{iελ3} e^{iελ2}`,
      `Re tr = 1 + 2cos²ε`, `1 − Re tr/3 = (2/3) sin²ε` (cazul abelian cu același generator: `(4/3) sin²ε`,
      dublu). Nodul 3: 10 triunghiuri, unul curbat (3,1,2) cu `w12 = ((√15/2)(3/4))^{1/2}`, nouă cu
      `w0 = (3/4)^{3/4}`: `κ_3 = w12 (2/3) sin²ε / (w12 + 9 w0) = 9.125536822542061e-04` (relativ `1e-9`),
      iar valoarea abeliană `1.825107364508412e-03` este EXCLUSĂ (diferență relativă ≥ 0.4).
- **Q6 martor de decizie (analitic):** în H+, nodurile de curbură minimă sunt cele 43 cu κ = 0, iar
  muchiile cu ε ≠ 0 sunt numai 1–7, 1–x, 7–x (x = 13..16); deci orice 6 noduri cu κ = 0 fără astfel de
  muchii ating `E_min` și **biletul PL anticipat = {2, 3, 4, 5, 6, 8}** (primul lexicografic). B:
  numărările 2 pentru 1 și 7, 1 pentru restul celor din extrageri ⇒ **bilet B = {1, 2, 3, 4, 5, 7}**.
  R la k* = 3: `ew_7 = 1 + 2^{−1/26} > ew_1 = 1 + 2^{−2/26} > ew_13..16 = 1 > ew_restul` ⇒
  **bilet R = {1, 7, 13, 14, 15, 16}** (disjunct de PL). În H−: biletul PL anticipat = {1, …, 6}.
  Cerință: toate cele patru bilete calculate sunt EXACT cele anticipate, iar inegalitățile ew sunt
  verificate (strict, float64).

Rezultat `PL_QUALIFIED` (6/6) sau `PL_NOT_QUALIFIED` (publicat; istoria reală neatinsă; cod NEVALIDAT).
Defectele tehnice ale implementării descoperite în calificare se tratează prin amendament scris și
sigilat ÎNAINTE de orice acces la istoria reală, cu încercarea inițială păstrată.

## 6. Backtest walk-forward unic pe arhivă și porți (toate 6 necesare)

1. `ExcesPL/U ≥ 0.20`; 2. `hitsPL > hitsB` și `hitsPL > hitsR`; 3. `logPL − logU > 0` și `logPL − logB > 0`;
4. `BrierPL < BrierU, BrierB, BrierR`; 5. în ambele jumătăți: exces `> 0` și `hitsPL − hitsB > 0`;
6. în ambele jumătăți: `logPL − logB > 0`.

Verdict `PL_PROMOVAT_EXPLORATORIU` (6/6), altfel `PL_NO_PROMOTION_EXPLORATORY`. Și la 6/6 rămâne
`positive_claims_allowed=false`. O SINGURĂ rulare; `START.json` blochează repetarea. Predicțiile (π, κ,
q_law, bilete, `E_min`, al doilea minim distinct) se scriu și se sigilează SHA-256 ÎNAINTE de scor.
Rezultatul se publică indiferent de verdict. Fără tuning după vizualizare.

## 7. Descriptiv (nu intră în porți, nu schimbă verdictul)

- p exact pentru hits sub nul (convoluție hipergeometrică); numărul de pași cu bilet PL ≠ B, ≠ R și
  ≠ top-6 după π (efectul termenului de pereche); distribuția potrivirilor.
- **Universuri nule masive pe GPU** (aceeași structură de pași, extrageri uniforme): 1024 universuri,
  seed `[649, 12, u]`, `u = 0..1023`, statisticile LEGII (log, Brier, porțile 3, 4, 6) și hits ale
  top-6 după π (fără QUBO), în loturi pe GPU (complex128); plus 32 universuri `u = 0..31` cu biletul QUBO
  exact și toate cele 6 porți. Ranguri empirice ale valorilor reale.
- **Putere sub H_PL auto-consistentă:** 8 universuri cu γ = 1/2 (seed `[649, 12, 1000+u]`) și 8 cu
  γ = 1/8 (seed `[649, 12, 2000+u]`): la fiecare pas, extragerile prin alegere secvențială fără întoarcere
  cu ponderi `exp(−γ z_j)` din starea PL a istoricului sintetic de până atunci; aceleași scoruri și porți.
- Anealerul Higgs (§8) la pașii-țintă din 97 în 97 ai backtestului real: rata în care cel mai bun bilet
  găsit = biletul exact; certificat de produs, nu poartă.
- La pasul final: spectrul de arie, `A`, `V`, κ, ε, numărul de triunghiuri, eroarea de unitaritate,
  monopolii XY (§8), deviația ariei Planck (§9).

## 8. Anealerul Higgs și monopolii XY (motor, descriptiv și produs)

- **Anealer:** R = 50.000 replici × 49 câmpuri reale φ pe GPU (fp32), ocupare `n = (1 + tanh φ)/2`,
  `H(φ) = Σ_a [μ²(t) φ_a²/2 + φ_a⁴/4] + Σ_a β z_a n_a + η Σ_{a<b} ζ_ab n_a n_b + 2 (Σ_a n_a − 6)²`;
  Langevin `φ ← φ − dt ∇H + √(2 dt T(t)) ξ`, 1500 de pași, `dt = 0.02`, `μ²` liniar de la +1 la −1 (vidul
  simetric φ = 0 devine instabil la mijloc: rupere spontană de simetrie Z2 pe fiecare nod),
  `T(t) = 0.5 (1 − t/1500)²`, `φ0 ~ N(0, 0.1²)`, generator CUDA cu seed 649. La final: top-6 după φ în
  fiecare replică, coborâre deterministă prin schimburi 1↔1 până la minim local (≤ 50 iterații),
  stări distincte ordonate după E. Telemetrie: parametrul de ordine `⟨|φ|⟩`, momentul ruperii, fracția
  replicilor în minimul exact.
- **Monopoli XY („cromodinamici” doar ca nume):** 4096 replici Kuramoto pe GPU, `ω_a = z_a`, cuplaj
  `K_ab = a_ab / mean(a pe muchiile cu spin)`, zgomot termic `T_K = 0.05`, `dt = 0.05`, 2000 de pași
  Euler–Maruyama, θ0 uniform (seed `[649, 12, 77]`); vorticitatea triunghiului (toate muchiile cu spin)
  `q = round((wrap(θ_b−θ_a) + wrap(θ_c−θ_b) + wrap(θ_a−θ_c))/2π)`; „monopol persistent” = triunghi cu
  același q ≠ 0 în ≥ 90% din replici. Strict descriptiv.

## 9. Produsul UI (tabul 12, read-only față de cercetare)

Rețeaua de spin 3D rotativă (Plotly/WebGL; poziții din vectorii proprii 2..4 ai Laplacianului normalizat
ponderat cu `a_ab`, calculați cu `torch.linalg.eigh` pe GPU; cadre pentru ultimele extrageri = tranziții
„spinfoam”, scalate cu volumul-proxy total; dimensiunea nodului = A, culoarea = κ); telemetrie: deviația
ariei Planck `PAD = (Σ a_ab − media nulă)/media nulă` (media din 4096 istorii uniforme de aceeași lungime,
pe GPU), rata erorii de holonomie (fracția legăturilor cu `‖U†U − I‖ > 1e-12` și maximul), VRAM
(`torch.cuda.memory_allocated/reserved/max`), timpii; „Singularitatea”: EXACT 3 variante unice (§3.5),
cu certificatul enumerării complete și avertismentul `positive_claims_allowed=false`. Fallback CPU
jurnalizat dacă CUDA lipsește.

## 10. Verificare independentă

`verify_pl649.py` NU importă `pl_core.py`, `pl649.py`, alte modele, `engine.py`, `parser.py` sau
`validare.py`. Reparsează JSONL după §2 (SHA-256, extrageri, pași); reconstruiește legăturile cu
exponențialele în formă închisă (NumPy, CPU), calculează κ și ε triunghi cu triunghi (nu prin `M²`) la
FIECARE pas, `max|Δπ| ≤ 1e-9` față de predicțiile salvate; reface QUBO prin enumerare completă pe CPU
(multiproces) la fiecare pas: energia biletului salvat `≤ E_min + 1e-8` și biletul = primul lexicografic
în toleranța τ_E (pașii cu ambiguitate de toleranță se raportează); recalculează B/R, scorurile, porțile,
verdictul, `hitsB = 1847`, `hitsR = 1821`; verifică hash-ul predicțiilor și ordinea sigiliu < calificare <
START. PASS numai dacă toate verificările trec. UNKNOWN nu devine PASS.
