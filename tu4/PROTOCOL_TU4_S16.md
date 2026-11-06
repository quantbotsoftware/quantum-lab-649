# PROTOCOL TU4-S16 — cererea „expansiunea preciziei modelelor fizice H1/H3” (Mesajul 59): decizia înaintea codului și martorii matematici

Scris și sigilat (`tu4/SIGILIU_TU4_S16.json`) ÎNAINTE de orice cod sau calcul al sesiunii S16. Calcul clasic
(float64 / complex128, CPU și GPU). Fără arhiva reală, fără popularitate, fără subagenți. `positive_claims_allowed=false`.

## 0. Context și autoritate

- Ceasul sistemului: 2026-10-27 ≈ 23:50Z. Mesajul spune „28 octombrie 2026”; ca în S15, autoritatea este ceasul.
- Primul pas exact al predării 20261027T234222Z a fost rulat (23:46Z) și a trecut integral: hash-urile perechii și ale
  arhivelor = `VERIFICARE_PREDARE_20261027T234222Z.json`; 7 × `drift []`; `LANT` 3 linii (emisiile din 2026-10-29:
  `e2fe385e…` 649, `a15dc8fd…` 540, `092e3f5c…` joker); `DECONTARI.jsonl` absent ⇒ 0 decontări; ultima rulare a
  judecătorului 23:30:37Z `nothing_to_settle` rc 0; `SCORURI_JU.mmap` (SSD) = 512 octeți = numai antetul, 0 rânduri;
  incidente numai `EM_01`, `FR_01`; `VERIFICARE_EM_PASS` 42/42; `VERIFICARE_JU_PASS` 13/13; 55 passed; 38 passed + 3
  skipped; `"ok": true`; `UI_PASS` 15/15; DL exit 0. Jurnal: `tu4/rezultate/S16/primul_pas_S16_20261027T234606Z.log`.
- Starea modelelor (emisia din 29, `tu4/rezultate/EM/RAPORT_EM.md`): estimarea proprie a abaterii este cel mult
  D = 1.62e-3 nats/extragere (H3_649: `D_nats` = 0.001619927375358543). Aceasta este o ESTIMARE contractată a
  modelului, nu o abatere măsurată. Frontiera S10 (`tu4/rezultate/FR/RAPORT_FR.md`): toate familiile `FR_NEFEZABIL`.

## 1. Ce cere Mesajul 59 și decizia (fixată acum, înainte de cod)

### C1. Modificarea pe loc a `tu4/ip_core.py` (H1 „MA”, H3 „AD”) — REFUZATĂ

1. `tu4/ip_core.py` (`ab3e1de9…`) este înghețat prin sha în `SIGILIU_TU4_EM.json`, `SIGILIU_TU4_JU.json` și
   `SIGILIU_TU4_UI.json`. Cele 3 emisii din 2026-10-29 au fost calculate cu el, iar sha-urile lor sunt înghețate în
   sigiliul JU (I3).
2. Protocolul JU (§1, §4): confirmarea se face NUMAI cu modelul înghețat; verificatorul JU (V1) compară hash-urile
   înghețate; dacă lanțul nu se verifică, judecătorul refuză ORICE decontare. O modificare a `ip_core.py` ar produce
   `drift` în 3 sigilii și ar bloca prima decontare (joi 29 oct), adică exact tribunalul pe care Mesajul 59 cere să-l
   păstreze („judecătorul din S13 și interfețele S14 rămân intacte”, „Protecția hash-urilor”).
3. Științific: schimbarea modelului după emisie și înaintea decontării înseamnă că fluxul nu mai măsoară ipoteza
   înghețată. Orice „precizie nouă” este o ipoteză NOUĂ, care ar cere protocol propriu, calificare Q1–Q6 (S11),
   emițător și fluxuri noi în judecător — incompatibil cu „judecătorul intact”. S16 nu face asta.

### C2. „Navier–Stokes simplificat pentru curentul de aer din urnă” — NECALIFICAT a priori, fără cod

Criteriul (AGENTS.md): informație pre-țintă DISTINCTĂ și motivul unei decizii diferite față de repere.
- Informația disponibilă este aceeași ca la H3: numărările c_i și ordinea etichetelor. Nu există măsurători ale
  urnei: geometrie, viteză/număr Reynolds, tipul mașinii, ordinea reală de încărcare (premisa H3 este deja declarată
  neverificată). O soluție Navier–Stokes ar transforma condiții la limită NECUNOSCUTE într-o funcție ln w_i(θ) pe cele
  n etichete; θ nu este identificabil din numărări.
- Orice astfel de familie este fie inclusă (aproximativ) într-un subspațiu neted de etichete — adică H3 cu alt K, o
  reglare a lui K după emisii, interzisă — fie mai bogată, apropiindu-se de H1 cu cost de învățare mai mare.
- „Ecuații de ordin superior” nu schimbă marginea informațională (martorul W4): niciun model nu poate crește panta
  așteptată a lui ln E peste abaterea REALĂ.
Concluzie: nicio informație distinctă, nicio decizie distinctă ⇒ necalificat, fără cod, fără calcul.

### C3. Transformata Fourier fracționară (FrFT) — martori matematici (§2), concluzia fixată pe rezultat

FrFT discretă de ordin a este o transformare UNITARĂ. Predicția declarată acum: (i) energia (deci X²) este
invariantă; (ii) H1 și H3 calculate după dus-întorsul F_a⁻¹F_a sunt identice; (iii) a selecta coeficienți în domeniul
FrFT = a alege un alt subspațiu liniar de etichete = o ipoteză nouă (ca C1.3), nu o rezoluție mai fină.

### C4. „Micro-abateri < 0.0016 nats” și „creșterea pantei ln E_t” — marginea W4

Pentru orice predictor q (orice transformare a trecutului) și legea reală P a unei extrageri:
E_P[ln q(X)/u(X)] = D(P‖U) − KL(P‖q) ≤ D(P‖U), iar sub urna uniformă (P = U): E_U[ln q/u] = −KL(U‖q) ≤ 0.
Panta așteptată nu poate fi ridicată de nicio transformare peste abaterea reală; supra-pariul (q mai „ascuțit” decât
P) o scade. La D = 1.62e-3, chiar un oracol care știe P exact are nevoie, în medie, de ln(600)/D ≈ 3 950 de
extrageri până la pragul de explorare (≈ 38 de ani la 6/49, ~104 extrageri/an).

### C5. GPU / `torch.compile`

`torch.compile(mode="max-autotune-no-cudagraphs", fullgraph=True)` rulează deja pe generare (`emite.py`,
`judecator.py`). În S16 nucleul compilat se folosește NUMAI unde există volum real: enumerarea exactă W4 a celor
C(49,6) = 13 983 816 bilete, float64 pe RTX 5060, cu verificare încrucișată NumPy float64 pe CPU. Transformatele FrFT
(matrici ≤ 49×49) se calculează în NumPy complex128 pe CPU: GPU nu aduce nimic la această mărime (declarat).
Fără praguri termice proprii; protecțiile hardware/OS rămân; temperatura GPU se înregistrează informativ.
„Saturarea PCIe” nu este un obiectiv științific și nu se urmărește.

### C6. Lanțul emisiilor

`tu4/emite.py` NU se modifică; timerul `ql649-tu4-emitere.timer` continuă emisiile cu modelele înghețate (următoarea
emisie nouă vineri 30 oct, ținta 2026-11-01); `tu4/verifica_em_v01.py` rămâne verificatorul. Nicio emisie manuală.

## 2. Martorii (fixturi sintetice; nicio extragere reală, nicio emisie citită în afara constantei D din §0)

Fixturi: n = 49, k = 6, p = k/n, N = 2595. v_i = ((5 i) mod 49) − 24 (i = 1..49, Σv = 0, ca F1 din H1).
g_i = cos(2π (i − ½)/49) (Σg = 0, profil neted). Pentru un profil u și o țintă X²: c = Np + γ u cu
γ = √(X²·N p(1−p)·n / ((n−1)‖u‖²)). Fixturile: c^F1 (u = v, X² = 50), c^I1 (u = v, X² = 400), c^G (u = g, X² = 100).

FrFT discretă: Candan–Kutay–Ozaktas (2000), IEEE Trans. Signal Process. 48(5): matricea S cu S[j,j] = 2cos(2πj/n) − 4,
S[j, j±1 mod n] = 1; vectorii proprii obținuți separat pe subspațiile pare și impare (descompunerea P), sortați
descrescător după valoarea proprie și intercalați pe ordinele Hermite r = 0, 1, …, n−2, n−1+[n par];
F_a = V diag(exp(−iπ a r/2)) Vᵀ. DFT unitară de referință: W[m,j] = exp(−2πi m j/n)/√n, indici 0..n−1.
Precedente: Namias (1980), Ozaktas–Zalevsky–Kutay (2001), Candan–Kutay–Ozaktas (2000). Contribuția proprie: numai
martorul aplicat aici.

- **W0 (construcție):** pentru n ∈ {20, 40, 45, 49}: max|F_0 − I| ≤ 1e-10; max|F_1 − W| ≤ 1e-8;
  max|F_a F_b − F_{a+b}| ≤ 1e-8 pentru (a, b) ∈ {(0.3, 0.4), (0.5, 0.5), (0.25, 1.5)}.
- **W1 (unitaritate):** pentru aceleași n și a ∈ A = {0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 1.9}: max|F_aᴴF_a − I| ≤ 1e-10.
- **W2 (invarianța X²):** pentru c ∈ {c^F1, c^I1, c^G} și a ∈ A, cu z = √((n−1)/n)(c − Np)/√(Np(1−p)):
  |‖F_a z‖² − ‖z‖²| ≤ 1e-9·‖z‖².
- **W3 (H1/H3 neschimbate de dus-întorsul FrFT):** c′ = Np + Re(F_a⁻¹ F_a (c − Np)); cu funcțiile ÎNGHEȚATE
  `logw_h1`, `logw_h3`, `dct_basis` din `tu4/ip_core.py` (importat numai după verificarea sha `ab3e1de9…`):
  max|ln ŵ(c′) − ln ŵ(c)| ≤ 1e-9, |λ(c′) − λ(c)| ≤ 1e-10 și biletul top (cele 6 etichete cu ln ŵ maxim, departajare
  după etichetă) identic, pentru H1 și H3, toate c și a ∈ A.
- **W4 (marginea informațională, enumerare exactă):** v̂ = v/‖v‖; ln w_P = ε v̂ cu ε > 0 prin bisecție (80 de iterații)
  astfel încât `info_D`(ε v̂) = D⋆ = 0.001619927375358543 (abatere relativă ≤ 1e-10). q_s: ln w = s·ε v̂,
  s ∈ S = {0, 0.5, 1, 2, 4, 8}. Pe toate cele 13 983 816 submulțimi de 6 din 49 se calculează
  G_P(s) = Σ_S P(S) ln(q_s(S)/u(S)) și G_U(s) = Σ_S u(S) ln(q_s(S)/u(S)) (u = 1/C(49,6)), pe GPU prin nucleul compilat
  și pe CPU prin NumPy. Independent, forma închisă prin polinoamele simetrice elementare (`esp`, `info_D`):
  G_P(s) = s·Σ_i π_i ln w_P,i − ln e_6(w_s) + ln C(49,6), G_U(s) = −ln e_6(w_s) + ln C(49,6) (Σ ln w = 0).
  - W4a: |GPU − CPU| ≤ 1e-10 și |enumerare − formă închisă| ≤ 1e-9 pentru fiecare s; |Σ_S P(S) − 1| ≤ 1e-12.
  - W4b: |G_P(1) − D⋆| ≤ 1e-9; G_P(s) ≤ D⋆ + 1e-12 pentru toate s; maximul pe grilă este la s = 1.
  - W4c: G_U(s) ≤ 1e-12 pentru toate s; G_U strict descrescătoare pe s > 0 din grilă.
  - Se raportează (fără prag): t⋆ = ln(600)/D⋆, anii la 104 extrageri/an, G_P(2), G_P(4), G_P(8), G_U(s),
    statutul compilării și temperatura GPU înainte/după.

## 3. Verdicte fixate acum

- Toate W0–W4 PASS ⇒ `S16_NECALIFICAT_INVARIANTA`: FrFT și Navier–Stokes nu se califică drept extinderi ale H1/H3;
  `ip_core.py`, judecătorul, emițătorul, emisiile, LANT și UI rămân neschimbate.
- Orice W FAIL sau UNKNOWN ⇒ incident tehnic `tu4/incidente/S16_01/` (fișierele încercării păstrate), fără schimbarea
  pragurilor; o reparație este permisă numai pentru conformitatea implementării cu definiția publicată de mai sus, cu
  amendament scris înainte. UNKNOWN nu devine PASS. Decizia C1 nu depinde de W (rămâne REFUZATĂ în orice caz).
- În niciun caz: afirmații pozitive, modificarea fișierelor înghețate, fluxuri noi, emisii manuale, reglaje.

## 4. Fișiere, rulare, regresie

- Fișiere NOI numai: `tu4/s16_martori.py`, `tu4/tests/test_s16.py`, `tu4/rezultate/S16/*` (0444 după scriere).
  Sigiliul `tu4/SIGILIU_TU4_S16.json` înregistrează sha-ul acestui protocol și hash-urile fișierelor înghețate, cu
  `code_files_present: []` la sigilare.
- O singură rulare reală a martorilor (determinist, fără semințe) ⇒ `tu4/rezultate/S16/MARTORI_S16_<UTC>.json`.
  Testele `test_s16.py` verifică pe dimensiuni mici (fără enumerarea completă) aceleași identități.
- Regresia după cod: `tu4/tests/` (55 + noile teste), primul pas TU3 (38 passed + 3 skipped), suitele istorice
  (linia de bază 188 passed, rulată înaintea codului în `tu4/rezultate/S16/baseline_istoric_*.log`); apoi
  `verifica_em_v01.py`, `verifica_ju.py`, `inlocuiri_tu3.py --verifica`, `verifica_ui_s14.py` și cele 7 sigilii.
- Raport: `tu4/rezultate/S16/RAPORT_S16.md`; apoi `predari/OPERATIV.md`, Mesajul 59 în supliment,
  `predari/genereaza_predare.py`.
