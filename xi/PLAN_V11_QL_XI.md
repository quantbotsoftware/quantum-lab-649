# Plan v11 — QL-Ξ „Câștig constant, pierdere minimă”: obiectivul tău, tratat cu matematică exactă

> [!IMPORTANT]
> Nimic nu rulează până nu aprobi. `positive_claims_allowed=false`. INCIDENT_XI_00 rămâne declarat.
> **Obiectivul tău:** „categorii mai mici, dar constante, încât să nu fim pe minus”. v11 este construit în jurul acestui obiectiv. Cercetarea cuantică din v9/v10 rămâne, dar ca suport, nu ca promisiune.

---

## 1. Contractul adevărului (cifre din baza proiectului, nu estimări)

Plățile reale din arhivă, mediana ultimelor 52 de extrageri: 6/49 IV = **50 lei** (fix), 6/49 III ≈ 497 lei, 5/40 III ≈ 675 lei, Joker VIII ≈ 30 lei, VII ≈ 43 lei, VI ≈ 62 lei.

| Joc (preț) | Valoarea așteptată din categoriile mici | Biletul mediu | **Cel mai bun bilet** (Quantum Limit, interval 5–95%) |
|---|---|---|---|
| 6/49 (8 lei) | IV 0.88 + III 0.48 = **1.36 lei (17%)** | 3.61 lei (45%) | **5.93 lei (74%)**, 5.06–7.12 |
| 5/40 (5 lei) | III **0.52 lei (10%)** | — | **2.79 lei (56%)**, 1.98–4.30 |
| Joker (7 lei) | VIII 0.56 + VII 0.17 + VI 0.37 ≈ **1.1 lei (16%)** | — | **3.95 lei (56%)**, 2.80–5.37 |

**Concluzia, spusă direct.** Categoriile mici returnează doar 10–17% din miză. Orice sistem care urmărește *numai* câștiguri mici constante pierde, garantat matematic, 83–90% din bani pe termen lung. Nici cel mai bun bilet calculat nu trecea de prețul biletului, nici la capătul de sus al intervalului (7.12 < 8 lei). Prin urmare **„constant și fără minus” nu se poate garanta**. Ce se poate face este să ne apropiem cât mai mult de el, iar asta este ce construiește v11.

---

## 2. Cele cinci componente

### C1. Designuri de acoperire anti-mulțime: câștig **garantat** la ultima categorie, cu valoare maximă
- **Garanția:** un set de bilete care, *orice numere ar ieși*, conține cel puțin un bilet câștigător la ultima categorie.
  - **Joker VIII: 180 de bilete, optim exact.** Pentru fiecare dintre cele 20 de valori Joker sunt necesare și suficiente 9 bilete care acoperă toate cele 45 de numere. Se demonstrează scurt, iar verificarea se face exhaustiv pe calculator.
  - **6/49, 3 numere: cel mai bun design cunoscut are 163 de bilete.** Minimul este o problemă deschisă în matematică (între 87 și 163).
  - **5/40, categoria III:** designul se calculează.
- **Ideea originală: permutarea anti-mulțime.** Garanția unui design **rămâne valabilă la orice permutare a numerelor** 1..n. Dintre cele 49! re-etichetări posibile o alegem pe cea care **maximizează câștigul așteptat** după modelul mulțimii din Quantum Limit, adică pe cea cu cele mai puțin jucate combinații. Căutarea este de tip QAP prin recoacere pe GPU; fiecare evaluare este o sumă de căutări în tabelul exact al celor 14M valori EV. Rezultatul are **aceeași garanție, cu valoare așteptată mai mare**.
- **Atacul pe record (cercetare):** căutare masiv paralelă pe GPU pentru un design 6/49 cu mai puțin de 163 de bilete, verificată exhaustiv pe toate cele 13 983 816 extrageri. Nu promit reușita; recordul a fost atacat intens.
- **Costul, spus cinstit:**

| Joc | Bilete | Cost | Câștig garantat |
|---|---|---|---|
| 6/49 | 163 | 1 304 lei/extragere | cel puțin 50 lei |
| Joker | 180 | 1 260 lei | cel puțin ~30 lei |

  Valoarea așteptată rămâne negativă. Garanția face câștigul **constant**, dar nu **profitabil**.

### C2. Detectorul ferestrelor EV+ („joacă numai când merită”)
- **Regula:** joci numai când **marginea inferioară** (cuantila 5%) a valorii așteptate a biletului optim depășește prețul. Asta se poate întâmpla doar la reporturi mari de jackpot, când sunt și vânzări suficiente.
- **Backtest economic unic, preregistrat:** pentru fiecare extragere istorică din 2010 încoace se calculează EV-ul **numai cu informația disponibilă înainte** de extragere (report anunțat, vânzări prognozate). Întrebarea: *de câte ori a apărut o fereastră EV+ și ce ar fi adus jocul doar atunci?* Poate apărea **de zero ori**, iar rezultatul se publică oricum.
- **Limita:** chiar și în fereastră, câștigul așteptat vine aproape tot din jackpot (probabilitate 1/14M), nu din categoriile mici. Variația este uriașă, deci profitul nu e constant.

### C3. Optimizatorul de portofoliu sub buget (recoacere cuantică simulată pe GPU)
- **Intrarea:** bugetul tău pe extragere (de exemplu 40, 100 sau 500 lei).
- **Ieșirea:** setul de bilete care **maximizează valoarea așteptată totală** și, după alegerea ta, minimizează suprapunerile (riscul de a-ți împărți singur premiul) sau maximizează probabilitatea de câștig la ultima categorie.
- **Metoda:** problemă QUBO cu restricții de cardinalitate, rezolvată prin recoacere cuantică simulată pe integrala de drum (Santoro et al., 2002) și prin tempering paralel pe GPU. Optimul exact se verifică pe instanțe mici.

### C4. Simulatorul probabilității de profit (răspunsul direct la „să nu fim pe minus”)
- **Metoda:** Monte Carlo pe GPU cu **milioane de „ani” simulați** pentru fiecare strategie: bilet optim fix, strategie mixtă, design de acoperire, numai ferestre EV+, buget X.
- **Ieșirile:**
  - **probabilitatea de a fi pe plus după 1, 5 și 10 ani**;
  - pierderea mediană;
  - riscul de ruină pentru un buget dat;
  - fracția Kelly, care arată cât de mic trebuie să fie pariul chiar și în ferestrele EV+.
- **O estimare brută, de confirmat de simulator:** cu biletul optim la fiecare extragere 6/49 timp de un an (104 × 8 = 832 lei), probabilitatea de a încheia anul pe plus este de ordinul **8–10%**, mai ales prin șansa de a prinde o categorie III. Pierderea așteptată este de circa 216 lei.

### C5. Registrul de joc pe hârtie (paper trading), sigilat
- **Ce se înregistrează:** înainte de fiecare cutoff, fiecare strategie își sigilează biletele în `LANT_STRATEGII.jsonl` (SHA-256, 0444).
- **Decontarea:** după extragere, se decontează la plățile reale. Rezultă un **profit și o pierdere reale, verificabile**, fără bani reali.
- **Rostul:** în câteva luni vezi *pe date viitoare* ce face fiecare strategie, nu ce promite. Infrastructura TU4 (emisie, judecător, lanț) există deja și se poate reutiliza pentru un flux separat.

---

## 3. Ce rămâne din planurile anterioare (ca suport)

- **Testul orb pe arhive străine:** singura cale prin care ar putea apărea un avantaj real, deci predicții credibile. Dacă se găsește un bias și se confirmă prospectiv, intră imediat în C3 ca probabilități modificate.
- **Atlasul cuantic Ψ1–Ψ5 și predictorii cuantici Ψ-PRED:** cercetare care explică limitele și testează onest modelele cuantice. Ψ-PRED intră în C5 ca strategie urmărită pe hârtie.
- **Infrastructura:** guvernatorul de resurse, registrul aprobărilor, verificatorul Rust, Lean, kitul de replicare.

## 4. Resursele (folosire maximă)

| Componentă | GPU | CPU (24 de fire) | SSD |
|---|---|---|---|
| C1 permutare + atac record | 30–60 GPU-h (căutare paralelă și verificare exhaustivă: 14M extrageri × 163 de bilete, ~2·10⁹ comparații pe verificare, secunde pe GPU) | verificare independentă în Rust | designuri, jurnale de căutare |
| C2 backtest EV | 5–10 GPU-h (EV exact pe circa 1 700 de extrageri × 14M bilete) | modelul mulțimii | tabele EV, ~100 GB |
| C3 portofoliu QUBO | 5–15 GPU-h | — | mic |
| C4 Monte Carlo | 10–20 GPU-h (10⁸ ani-strategie) | statistici | ~20 GB |
| C5 registru | minim | sigilare | mic |
| **v11 nucleu** | **≈ 50–105 GPU-h** | | **≈ 150 GB** |

Guvernatorul cedează placa video la ±15 minute de emisiile și decontările produsului existent.

## 5. Fazele și porțile

| Fază | Conținut | Poartă |
|---|---|---|
| A | S33_01 opțiunea A, Q4 v2, INCIDENT_XI_00, protocolul-mamă v11 | G0 |
| B | C4: simulatorul de profit, ca să vezi **imediat** cifrele pe strategii | G1: probabilitățile, verificate exact pe cazuri mici |
| C | C1: designurile garantate (Joker 180 verificat, 6/49 163 reprodus, 5/40 calculat) și permutarea anti-mulțime | G2: garanție verificată exhaustiv 100% |
| D | C2: backtestul ferestrelor EV+ | G3: rezultatul publicat, oricare ar fi |
| E | C3: optimizatorul de portofoliu în produs | G4: optim exact pe instanțe mici |
| F | C5: registrul pe hârtie live, cu decontare automată prin judecătorul separat | G5: primele decontări verificate |
| G | atacul pe recordul 163; testul orb; atlasul și Ψ-PRED (suport) | per program |
| H | ecranul „Strategii” în Observatorul Tauri: profit/pierdere live, probabilitatea de profit, garanții | G6: paritate Rust |

## 6. Deciziile tale

1. **INCIDENT_XI_00:** arhivare (recomandat) sau ștergere?
2. **S33_01:** opțiunea A?
3. **Bugetul de referință pe extragere** pentru C3/C4 (de exemplu 40, 100 sau 500 lei), sau mai multe variante simulate?
4. **Registrul pe hârtie (C5):** pornește cu toate strategiile (recomandat)?
5. **Ordinea:** simulatorul de profit primul (recomandat), ca să vezi cifrele reale înainte de orice altceva?
6. **Arhivele străine, SSD-ul 1.5 TB, QPU, Lean:** rămân ca în v10 (decizii separate, ulterioare)?
