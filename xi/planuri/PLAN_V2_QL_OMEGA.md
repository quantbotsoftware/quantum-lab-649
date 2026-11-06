# Plan v2 — QL-Ω „Observatorul limitei”: de la 40 de negative la o limită certificată, date cu adevărat nevăzute și un colaps cuantic justificat

> [!IMPORTANT]
> Nimic nu a fost rulat sau modificat; am făcut doar citiri. Planul așteaptă aprobarea ta. `positive_claims_allowed=false` se aplică peste tot.

## 0. De ce v1 merita nota 3 (autocritică pe baza verificărilor de azi)

| Defect v1 | Ce am verificat |
|---|---|
| A prezentat enumerarea celor 14M bilete drept nouă | `quantum_limit/ceiling.py` face deja EV exact pe toate biletele |
| Ising pe perechi ≈ familii închise | pair_collisions, transfer_perechi, MI și PG sunt închise |
| Wheeler–DeWitt și QAOA ca decor | PL649 „Planck/LQG/Higgs” 0/6 și QL649 „Amplituhedron/Kuramoto” 0/6 arată că metafora nu produce semnal |
| Proiectori Lagrange de grad 6 | instabili numeric (≈ 258⁶ ≈ 3·10¹⁴) |
| **Problema reală, neatinsă:** arhiva RO este deja explorată și nu există date nevăzute | toate cele 40 de verdicte sunt explorative, cu valoare confirmatoare 0 |

**Teza v2.** Un nou model-metaforă nu mai aduce nimic. Mai departe se poate merge numai schimbând *jocul epistemic*:
- **Λ** transformă cele 40 de negative într-o **limită certificată**: un număr cu sens.
- **Γ** aduce **date cu adevărat nevăzute**, pentru singurele ipoteze fizice care se pot transfera.
- **V** dă „colapsului funcției de undă” o justificare **de teoria jocurilor**.
- **Q** construiește un **laborator cuantic simulat**, cu adevăr cunoscut ca referință.

---

## 1. Cei cinci piloni

### Λ — Certificatul Limitei Cuantice (original, determinist, fără ipoteze de uniformitate)
O mixtură universală m peste o clasă bogată C de predictori are un regret explicit R_n față de cel mai bun predictor din clasă. Clasa C cuprinde marginale variabile în timp, Markov de ordin d pe etichete, structuri pe glife, anotimpuri și perechi, combinate prin CTW și Fixed-Share. Din definiția regretului:

$$\forall q\in C:\quad \sum_{t\le n}\log\frac{q(x_t)}{u(x_t)}\;\le\;\log\frac{m(x_{1..n})}{u(x_{1..n})}+R_n$$

- **Ce obținem:** pe arhiva reală, *niciun* predictor din C, nici măcar ales retrospectiv, nu ar fi câștigat mai mult de δ_Λ = (ℓ + R_n)/n nați pe extragere.
- **De ce contează:** este o **inegalitate deterministă**. Nu are p-valori și nu presupune nimic despre urnă.
- **Cifra în lei:** prin `ceiling.py`, δ_Λ se convertește într-un plafon al câștigului de EV pe care l-ar putea aduce *orice* predicție din C.
- **Rezultatul:** „Quantum Limit”-ul produsului devine o limită dublă, a mulțimii și a predictibilității, publicată pentru 6/49, 5/40 și Joker.

Atribuire: Shtarkov; Krichevsky–Trofimov; Willems–Shtarkov–Tjalkens (CTW, 1995); Herbster–Warmuth (Fixed-Share, 1998). Contribuția proprie este aplicarea pe spațiul combinatorial al extragerilor și dubla conversie, nați → lei.

### Ω — E-proces universal prospectiv (geamănul lui Λ)
Aceeași mixtură m emite înainte de fiecare cutoff. Raportul

$$E_t=\prod\frac{m(x_t\mid x_{<t})}{u(x_t)}$$

este martingală de test sub H0 și detectează *orice* structură din C, fără să alegem în avans familia. Produsul pe cele 3 jocuri este calculat fără dublă numărare. Fluxul are un judecător separat, iar judecătorul TU4 rămâne înghețat.

### Γ — Replicare pe date nevăzute (singura ieșire din „arhivă explorată”)
- **Ipotezele vizate:** numai cele **fizice și transferabile**. GL649 (masa glifelor, 2/6, cel mai aproape de semnal) și SE649 (anotimp/temperatură).
- **Înghețarea:** predictorul lor sigilat, *cu coeficienții estimați pe RO*, se îngheață înainte de descărcare.
- **Datele:** arhive publice 1..49 nevăzute în proiect. Estimativ: Germania 6aus49 (din 1955), Polonia Lotto (din 1957), Canada 6/49 (din 1982). Inventarul exact și proveniența (URL, dată, sha) se stabilesc în S4.
- **Testul:** o singură statistică fixată în avans (corelația dintre vectorul de efect RO și abaterile străine), cu α = 0.01 în pool și un singur test.
- **Control original prin inversarea emisferei:** dacă efectul SE este termic, el **trebuie să-și schimbe semnul** pe arhivele din emisfera sudică (Australia, Africa de Sud). Este un martor natural de falsificare.
- **Puterea:** circa 15–20k extrageri, ceea ce permite detectarea unor efecte de ordinul 10⁻⁴ nați. Un rezultat nul pe acest volum este o cunoaștere solidă, publicabilă.

### V — Colapsul justificat: strategia mixtă Born peste biletele aproape optime
- **Observația originală:** într-o loterie pari-mutuel, un „bilet optim” *publicat determinist* se autoanulează. Dacă mulți jucători folosesc același software, ajung să împartă premiul.
- **Răspunsul corect** este o **strategie mixtă** peste mulțimea biletelor ε-aproape optime după EV-ul din `ceiling.py`: eșantionare Born cu amplitudini √EV normalizate.
- **„Colapsul”** devine astfel o operație cu rost economic, nu un decor.
- **Sămânța:** commit-reveal SHA-256(sha protocol ‖ sha arhivă ‖ țintă), sigilată înainte de cutoff.
- **Rezultatul pe ecran:** cele **3 variante (6 / 5 / 5+1)**, etichetate onest: *variante de valoare anti-mulțime; probabilitatea de câștig este exact cea uniformă*.

Atribuire: Clotfelter & Cook (1993); Henze & Riedwyl (1998); Ziemba et al.

### Q — Laboratorul cuantic simulat `dicke649`, cu adevăr cunoscut
- **Simulatorul:** vector de stare exact în subspațiul Dicke pe RTX 5060 (6/49: 14M amplitudini, 224 MB).
- **Mixerul XY** este adiacența grafului Johnson J(n,k). Îl aplic **stabil** prin matricele proprii Eberlein / dual-Hahn ale schemei Johnson, nu prin proiectori Lagrange.
- **Algoritmi:** QAOA-XY, Grover-Dicke, spectroscopia gap-ului adiabatic (Lanczos).
- **Problema-test:** **peisajul EV real** din `ceiling.py`, al cărui optim exact se cunoaște, deci simularea are un benchmark verificabil pe date reale.
- **Validare și export:** validare față de Qiskit Aer pentru n ≤ 14. Export OpenQASM 3 pentru prepararea stărilor Dicke (Bärtschi–Eidenbenz, 2019), pregătit pentru un QPU real doar dacă decizi tu vreodată (cont, cost).
- **Onestitate:** calculul este clasic și nu există avantaj cuantic.

---

## 2. Sesiunile, cu criterii de acceptare și de oprire

| S | Livrabil | Acceptare (PASS) | Oprire / negativ publicat |
|---|---|---|---|
| **S0** | Deblocare legitimă: `verifica_publicarea_v2.py` (registrele prospective verificate ca prefix append-only) și Q4 v2, fiecare cu protocol și sigiliu înainte de cod | DL_RC_v2 = 0 și Q4 v2 PASS; vechile FAIL rămân în arhivă | orice probă veche modificată ⇒ STOP |
| **S1** | Protocol Λ/Ω: clasa C, derivarea lui R_n, fixture-uri | R_n verificat exact în Q (`Fraction`) pe n ≤ 10; inegalitatea testată pe 10⁴ secvențe sintetice | o inegalitate încălcată ⇒ derivare respinsă |
| **S2** | Calcul Λ pe 6/49, 5/40, Joker (GPU) și pornirea Ω | δ_Λ, plafonul în lei și reproducerea independentă CPU/Rust | — (orice δ se publică) |
| **S3** | V: sampler Born peste EV, commit-reveal, prima emisie a celor 3 variante | sigilată înainte de cutoff; verificator separat PASS | cutoff ratat ⇒ ținta următoare, fără retro-emisie |
| **S4** | Γ: inventar și achiziție de arhive străine cu proveniență (inventariere, nu experiment) | sha, URL și dată per fișier; dubla sursă acolo unde există | fără surse verificabile ⇒ Γ NOT_FEASIBLE |
| **S5** | Γ: testul confirmator unic | protocolul sigilat înainte de S4 | rezultatul se publică oricum |
| **S6–S7** | `dicke649`: mixer Eberlein, QAOA-XY, Grover, gap, export QASM 3 | eroare < 10⁻¹⁰ față de Aer (n ≤ 14); optimul EV regăsit exact | instabilitate numerică ⇒ fără afișare |
| **S8–S9** | Tauri „Observator” v2, crate nou; cel vechi (0444, `c20fdcd2…`) rămâne neatins | Rust recalculează independent energiile/EV, Λ și sigiliile; filele Streamlit 4/5 primesc verdicte reale prin TU3-SR-R | divergență de paritate ⇒ nu se publică |
| **S10** | Raport final, OPERATIV.md, HANDOFF/PROMPT | verificări PASS; perechea cu anexa canonică inclusă o singură dată | — |

Pe parcurs: duminică 1 noiembrie emisia automată TU4 merge singură, iar C1 este la 13:36–13:57Z. Fluxurile noi nu se grăbesc pentru această dată.

## 3. Ce vei vedea pe ecran la final

1. **Contorul Limitei:** δ_Λ în nați și lei pentru fiecare joc, alături de plafonul mulțimii.
2. **Cele 3 variante (6 / 5 / 5+1):** strategia mixtă Born, cu commit-reveal SHA-256 și verificare locală.
3. **Traiectoria Ω:** ln E pentru fiecare joc, cu pragurile.
4. **Harta Γ:** efectul pe fiecare țară, inclusiv inversarea emisferei.
5. **Laboratorul Q:** probabilitatea stării fundamentale în funcție de adâncime, gap-ul și starea „colapsată”.

## 4. Deciziile tale

1. **S33_01:** opțiunea A (recomandată)?
2. **Γ:** aprobi descărcarea de **arhive publice** străine? Nu presupune bani sau conturi; proveniența se hash-uiește.
3. Aprobi fluxurile prospective separate **Ω și V**, cu judecători proprii?
4. Ordinea: S0 → Λ → V → Γ → Q → UI (recomandată), sau Q mai devreme, ca demonstrație?
5. QPU real: îl păstrăm doar ca export pregătit (recomandat) sau vrei să pregătesc și accesul (cont/cost, decizia ta)?
