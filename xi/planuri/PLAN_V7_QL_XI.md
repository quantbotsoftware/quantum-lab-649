# Plan v7 — QL-Ξ „Bariera Ehrenfest”: v6 plus upgrade-urile care trec barierele cuantice

> [!IMPORTANT]
> Nimic nu rulează până nu aprobi. `positive_claims_allowed=false`. v7 păstrează integral v6 (testul orb, preregistrarea, TOST, red team, KPI-uri, guvernatorul de resurse, porțile G0–G6). INCIDENT_XI_00 rămâne declarat.
> **Diagnosticul la 7.1:** în v6, stratul cuantic era *opțional* și *decorativ*. În v7 el devine **pilon central, calculat și validat**, legat direct de obiectivul principal.

---

## Q1. De la „Heisenberg” la **bariera Ehrenfest**, cu fizică stabilită

Pentru un sistem haotic, timpul după care un pachet de undă cu incertitudine minimă se întinde până la scară macroscopică este **timpul Ehrenfest**:

$$t_E=\frac{1}{\lambda}\ln\frac{I}{\hbar}$$

Aici λ este exponentul Lyapunov, iar I acțiunea caracteristică. Referințe: Berman–Zaslavsky (1978); Zurek & Paz, *PRL* (1994); Zurek, despre Hyperion (1998).

**Estimarea preliminară pentru urnă** (de calculat riguros, nu de pretins):
- I ≈ m·v·L ≈ 0.003 kg · 1 m/s · 0.25 m ≈ 7.5·10⁻⁴ J·s, deci ln(I/ħ) ≈ **71**.
- Dacă λ ∈ [10, 100] s⁻¹, atunci **t_E ≈ 0.7–7 s**, față de un amestec de 20–60 s.
- Chiar și cu un λ pesimist de 5 s⁻¹, t_E ≈ 14 s, tot sub durata amestecului. Concluzia este robustă, pentru că depinde de ħ numai logaritmic.

**Decoerența** (Joos–Zeh): τ_D = (Λ Δx²)⁻¹, unde Λ este constanta de împrăștiere a aerului pe o sferă de 4 cm. Rezultă τ_D ≪ 10⁻³⁰ s pentru orice Δx macroscopic, deci bilele se comportă clasic, ca stări pointer.

**Concluzia certificabilă:** distribuția rezultatelor *moștenește* incertitudinea cuantică, amplificată de haos și făcută clasică de decoerență. „Quantum Limit” capătă astfel un sens fizic precis: **nicio informație despre trecut nu poate trece de t_E**.

## Q2. Bariera calculată, nu citată: **simulare cuantică pe GPU**

Aceasta este piesa care folosește placa video la maximum *pentru fizică cuantică reală*.

- **Metoda:** ecuația Schrödinger într-un biliard haotic 2D (stadion sau Sinai, cu λ clasic măsurat pe același biliard), rezolvată prin **metoda split-operator cu FFT pe GPU**. Grila ajunge la **8192² complex64 (512 MB)**.
- **Scanarea constantei efective:** ħ_eff = 10⁻² → 2·10⁻⁴. Pentru fiecare valoare măsor t_E ca momentul în care pachetul se desprinde de traiectoria clasică (lățimea Husimi și divergența față de densitatea Liouville).
- **Validarea legii de scalare:** panta lui t_E față de ln(1/ħ_eff) trebuie să fie **1/λ_clasic**, cu toleranța fixată în protocol. Abia după aceea legea se extrapolează la ħ_eff-ul real al bilei (≈ 10⁻³¹).
- **Decoerența simulată:** termen Lindblad de localizare în poziție, prin despicare stocastică. Arăt că probabilitățile de ieșire ale stării decoerate coincid cu cele clasice (amprenta clasicizării).
- **Costul:** circa 10⁴–10⁵ FFT-uri de 8192² pentru fiecare valoare ħ_eff, adică ore de GPU la încărcare de circa 95%. Guvernatorul cedează placa în ferestrele produsului existent.
- **Verificarea:** pe grile mici, norma și energia trebuie conservate (≤ 10⁻⁸ în fp64), iar rezultatele trebuie reproduse independent prin diagonalizare exactă.

## Q3. **Tetrada limitelor**: patru plafoane, într-un singur ecran

| Limita | Ce spune | Sursa |
|---|---|---|
| **Ehrenfest** (fizică) | după t_E, trecutul nu mai determină extragerea | Q1–Q2 |
| **Cramér–Rao** (metrologie) | cât de precis *ar putea* arhiva să măsoare masa unei bile; σ_m ≥ 1/√(N·F), cu F din geamăn | informația Fisher a răspunsului R |
| **Λ** (informație) | cât ar fi câștigat retrospectiv orice predictor din clasa G | marginea de regret |
| **Plafonul EV** (economie) | cât valorează cel mai bun bilet, ținând cont de mulțime | `ceiling.py` |

Produsul „Quantum Limit” devine astfel ceea ce îi promite numele: **o limită certificată pe patru axe**.

## Q4. Controlul pozitiv cuantic, cu bias exact

Pe urna cuantică simulată în subspațiul Dicke (14M amplitudini, mixer Eberlein stabil), rotațiile controlate injectează **un bias cunoscut exact**. Extragerile rezultate trec prin același lanț ca datele reale și trebuie detectate la puterea declarată. Este un martor pozitiv **cu adevăr analitic**, mai curat decât cel din DEM.

## Q5. Colapsul certificat (opțional)

Sămânța strategiei mixte Born pentru cele 3 variante poate veni din:
- **aleatoriu cuantic certificat**: protocolul Liu et al., *Nature* (2025), pe un QPU, numai cu contul și decizia ta;
- implicit, din entropia hardware locală (`getrandom`) cu commit-reveal.

În ambele cazuri, „colapsul” este verificabil.

## Q6. Clasa cuantică în Popper

În clasa G intră mașini Born MPS cu dimensiuni de legătură variate. Diagnosticul **spectrului de încurcare** față de spectrul hipergeometric exact al lui |D⁴⁹₆⟩ apare ca grafic în Observator.

---

## U13. Sursele străine, verificate preliminar (căutare web, fără descărcare)

| Țară | Joc | Din | Surse găsite | Dublă sursă |
|---|---|---|---|---|
| Germania | 6aus49 | 1955 | portalurile oficiale regionale (WestLotto, SachsenLotto, Lotto Thüringen) și arhive GitHub | **da** (oficial + comunitar) |
| Polonia | Lotto (Duży Lotek) | 1957 | lotto.pl (oficial), mbnet, multipasko, Kaggle | probabil |
| Canada | Lotto 6/49 | 1982 | de verificat în S7 | — |

Volumul estimat: **≈ 15–17k extrageri străine**, ceea ce confirmă MDE ≈ 0.85–1%. Proveniența finală (URL, dată, sha, comparația între surse) se stabilește în S7, sub testul orb.

## U14. Poarta valorii informației (G3, cu formulă)

Dacă amplitudinea prezisă |b| < MDE/3, testul confirmator este declarat **nedecisiv în avans**. Rămân atunci numai TOST și Cramér–Rao, iar testul nu se mai prezintă ca experiment decisiv. Așa nu se consumă un test unic pe o ipoteză care nu poate fi detectată.

## U15. Pre-mortem (scris acum)

*„Peste 3 luni proiectul a eșuat. De ce?”*

| Cauza imaginată | Prevenirea |
|---|---|
| Simularea cuantică nu reproduce panta 1/λ | toleranță fixată; dacă eșuează, se publică eșecul; Q1 rămâne citat, nu certificat |
| Geamănul DEM nu se poate calibra | etichetă „familie parametrică”; laboratorul U7 opțional |
| Arhivele străine sunt incomplete sau au formate schimbate | inventar în S7; NOT_FEASIBLE declarat |
| Interferență cu produsul existent | guvernatorul cedează la ferestre |
| Pornire fără aprobare (s-a întâmplat la 22:50) | aprobare explicită la fiecare poartă, consemnată în jurnal |

---

## Drumul critic actualizat

| Fază | Adăugat față de v6 | Cost suplimentar |
|---|---|---|
| B | Q1–Q2: bariera Ehrenfest, simulare split-operator și decoerență | +2 sesiuni, +20–30 GPU-ore |
| D | Q3: tetrada; Q6: MPS în G | +1 sesiune |
| E | Q4: control pozitiv Dicke; Q5 opțional | inclus în S12 |

Total: circa **19 sesiuni, ~95 de ore de lucru și 80–115 GPU-ore**.

## Deciziile tale

1. **INCIDENT_XI_00:** arhivare (recomandat) sau ștergere?
2. **S33_01:** opțiunea A?
3. **Arhive străine cu analiză oarbă**, inclusiv fraza secretă păstrată de tine: aprobi?
4. **SSD:** aprobi până la 1.5 TB?
5. **Laboratorul fizic (U7):** da sau varianta fără cost?
6. **QPU** (aleatoriu certificat Q5, urna cuantică reală) și OpenTimestamps: acum, mai târziu sau niciodată?
7. **Aprobare pe etape:** aprobi doar faza A acum (recomandat)?
