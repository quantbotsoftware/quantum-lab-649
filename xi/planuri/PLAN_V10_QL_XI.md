# Plan v10 — QL-Ξ „Predictorii cuantici”: atlasul v9 plus calculul cuantic *pentru predicție*

> [!IMPORTANT]
> Nimic nu rulează până nu aprobi. `positive_claims_allowed=false`. INCIDENT_XI_00 rămâne declarat.
> **Diagnosticul la 8.5:** v9 folosea fizica cuantică să explice *de ce* previzibilitatea moare. Lipsea partea pe care o cereți explicit: **modele cuantic-computaționale care chiar prezic**, cu verosimilitate exactă, evaluate riguros. v10 adaugă pilonul **Ψ-PRED** și păstrează integral atlasul Ψ1–Ψ5 și infrastructura v8.

---

## Observația care deschide totul

> **O extragere 6/49 este exact o ieșire *fără coliziuni* a unui sampler cuantic cu 6 particule în 49 de moduri.**

Fiecare număr extras este un mod ocupat de o particulă. Probabilitatea Born a unei 6-mulțimi S depinde de **statistica particulelor**:

| Statistică | P(S) ∝ | Echivalent clasic sau computațional | Cost exact pe GPU |
|---|---|---|---|
| **Fermioni** | \|det U_{S,T}\|² | **proces punctual determinantal** (k-DPP); circuite Givens libere | det 6×6, trivial |
| **Bosoni** | \|perm U_{S,T}\|² | **boson sampling**, candidatul la avantaj cuantic (Aaronson–Arkhipov, 2011) | Ryser: 2⁶ × 6 operații pe subset |
| **Distinguibile** | perm(\|U_{S,T}\|²) | particule clasice independente | Ryser real |
| **Parțial distinguibile** | interpolare cu un parametru x ∈ [0,1] | Tichy; Shchesnovich | sumă pe permutări, k = 6 |

Spațiul tuturor biletelor are 13 983 816 elemente. Placa video poate deci calcula **exact normalizarea** fiecărui model, adică exact ce un sampler fizic nu poate face. Verosimilitatea este exactă, nu estimată.

---

## Ψ-PRED: cinci familii de predictori cuantici

### P-F: Mașina Born fermionică (k-DPP)
- **Modelul:** P(S) ∝ det(L_S), unde L = V Vᴴ este învățat. Este echivalent exact cu un circuit de rotații Givens peste 6 fermioni (Kulesza–Taskar, 2012; Gillenwater).
- **Ce surprinde:** **repulsia** între numere (anti-bunching).
- **Uniformul este imbricat:** L = I dă exact distribuția uniformă. Testul raportului de verosimilitate este deci proper.

### P-B: Mașina Born bosonică (boson sampling, sectorul fără coliziuni)
- **Modelul:** P(S) ∝ \|perm(U_{S,T})\|², unde U este un interferometru 49×49 parametrizat unitar (Cayley sau exponențială anti-hermitiană).
- **Calculul:** normalizarea exactă pe cele 14M subseturi, cu Ryser pe GPU (circa 5·10⁹ operații complexe, ordinul secundelor).
- **Ce surprinde:** **atracția** (bunching) între numere.

### P-D: Indicele statisticii
- **Modelul:** familia continuă fermioni ↔ distinguibile ↔ bosoni, cu indistinguibilitatea parțială x.
- **Întrebarea fizică:** *Se comportă numerele loteriei „fermionic” (se resping), „bosonic” (se atrag) sau „clasic” (independent)?*
- **Predicția sub urnă corectă:** indicele estimat nu se distinge de modelul uniform. Intervalul de încredere se publică.

### P-I: Fermioni interacționanți în subspațiul Dicke (dincolo de simularea clasică eficientă generală)
- **Modelul:** circuite variaționale care **conservă greutatea Hamming**: porți XY (Givens) plus porți ZZ de interacțiune.
  - Fără ZZ, circuitul se reduce la P-F, clasic simulabil.
  - Cu ZZ, nu mai există simulare clasică eficientă în general. Aici însă se simulează **exact**, în subspațiul de 14M amplitudini (224 MB complex128).
- **Antrenarea:** gradient adjoint, cu o singură evoluție înainte și una înapoi pe pas.
- **Ce surprinde:** corelații de ordin superior, dincolo de perechi și de determinanți.

### P-R: Rezervor cuantic temporal
- **Modelul:** un lanț de 20 de qubiți (vector de stare de 2²⁰ amplitudini) **condus de istoria extragerilor**, cu o citire liniară care prezice marginalele extragerii următoare.
- **Ce surprinde:** memoria temporală într-un sistem cuantic dinamic.
- **Limita din AGENTS.md:** HQMM, extensia cuantică a HMM, **este exclus explicit**. HMM este închis prin regula proiectului, iar o variantă „cuantică” ar însemna o familie redenumită.

---

## Evaluarea: aceeași rigoare ca restul planului

1. **Preregistrare per familie înainte de cod:** praguri, comparatori (B, I, U), aceleași 6 porți ca până acum, martor de informație și martor de decizie.
2. **Walk-forward unic pe arhiva RO**, explorativ: fiecare familie se învață numai pe extragerile < t și se evaluează prin log-verosimilitatea comună exactă față de uniform.
3. **Scorul prospectiv XEB.** Benchmark-ul de entropie încrucișată liniară este instrumentul de verificare a supremației cuantice (Google, 2019), aplicat aici predictorilor:

$$F_{XEB}=\binom{n}{k}\,\mathbb{E}[P_{\text{model}}(S)]-1$$

   Sub o urnă uniformă, F_XEB are **media exact 0 pentru orice model fixat**, deci este un scor nedistorsionat. Pe fiecare extragere nouă se calculează și log-raportul, ca e-valoare.
4. **Integrarea în Popper.** Cele 5 familii, cu variantele lor sigilate Merkle, intră în fluxul e-LOND prospectiv, cu FDR ≤ 5%.
5. **Verificarea independentă în Rust:** det, perm (Ryser) și normalizările se recalculează pe CPU. Pe n ≤ 12 se face și verificarea exactă în Q (`Fraction`).

## Cele 3 variante (6 / 5 / 5+1), generate cuantic și etichetate onest

- **Generarea:** eșantionare Born din modelul cuantic cu cel mai bun scor XEB prospectiv. Pentru 5/40 și Joker se folosesc analogii n = 40 și n = 45, iar bila Joker vine dintr-un model cu un singur mod. Sămânța folosește commit-reveal SHA-256, sigilat înainte de cutoff.
- **Eticheta afișată lângă variante:** „*eșantion Born din modelul fermionic/bosonic/interacționant; avantaj predictiv nedemonstrat; e-valoare curentă = …; șansa reală de câștig = uniformă*”.
- **Dacă niciun model nu trece porțile:** variantele vin din strategia mixtă anti-mulțime, iar modelul cuantic se afișează alături, ca explorativ.

## Hardware cuantic real (opțional; decizia ta)

Interferometrul învățat în P-B se poate rula pe un **sampler fotonic real**, cu un cont cloud deschis de tine. Instanța ar fi la scară redusă: hardware-ul actual are circa 6 fotoni în 12–20 de moduri. Comparația dintre eșantioanele fizice și distribuția exactă de pe GPU, prin aceleași teste XEB, devine un **experiment de verificare a unui dispozitiv cuantic** pe un model antrenat pe date reale.

---

## Bugetul Ψ-PRED

| Familie | GPU | CPU | SSD |
|---|---|---|---|
| P-F (DPP) | 2–4 GPU-h | verificarea det fp64 | mic |
| P-B (permanenți) | 12–20 GPU-h (Ryser pe 14M × iterații × walk-forward cu warm-start) | Ryser în Rust | ~20 GB |
| P-D (indice) | 4–8 GPU-h | — | mic |
| P-I (Dicke interacționant) | 20–35 GPU-h (re-antrenare la fiecare 50 de extrageri, gradient adjoint) | verificare n ≤ 12 | ~50 GB checkpoint-uri |
| P-R (rezervor) | 3–6 GPU-h | — | mic |
| **Total Ψ-PRED** | **≈ 40–75 GPU-h** | | **≈ 80 GB** |

**Totalul proiectului:** atlasul (60–95) + Ψ-PRED (40–75) + infrastructura v8 ≈ **190–290 GPU-ore**, în circa **31 de sesiuni**. Guvernatorul ține GPU-ul în jur de 95%, CPU-ul pe 24 de fire în paralel, iar pe SSD se folosesc 1.0–1.5 TB.

## Fazele actualizate

| Fază | Conținut | Poartă |
|---|---|---|
| A | deblocare, protocolul-mamă, audit bibliografic (inclusiv DPP și boson sampling aplicate pe loterii), sondă de fezabilitate | G0, G1 |
| B | motorul cuantic GPU: split-operator, Lanczos, Chebyshev, Ryser, det, circuite Dicke cu gradient adjoint | G2: verificări exacte |
| C | atlasul Ψ1–Ψ5 | per program |
| **D** | **Ψ-PRED: P-F, P-B, P-D, P-I, P-R, cu preregistrare și walk-forward unic per familie** | **per familie** |
| E | geamănul DEM, ierarhia zgomotelor, amestecul Johnson | G3 |
| F | testul orb confirmator, red team | G4 |
| G | Popper cu familiile cuantice prospective, Lean, cele 3 variante Born | G5 |
| H | Observatorul (Atlas + Predictori), preprint, kit de replicare | G6 |

## Deciziile tale

1. **INCIDENT_XI_00:** arhivare (recomandat) sau ștergere?
2. **S33_01:** opțiunea A?
3. **Arhive străine cu analiză oarbă**, inclusiv fraza secretă păstrată de tine: aprobi?
4. **SSD:** aprobi până la 1.5 TB?
5. **Laboratorul fizic:** da sau varianta fără cost?
6. **Hardware cuantic** (sampler fotonic pentru P-B, QPU pentru Ψ4), OpenTimestamps, Lean 4: da, nu sau mai târziu, pentru fiecare?
7. **Aprobare pe etape:** aprobi doar faza A acum (recomandat)?
