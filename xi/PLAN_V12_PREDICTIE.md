# PLAN V12 — „Predicție verificabilă” (QL649 / QL-Ξ, după faza E a planului V11)

Scris și sigilat ÎNAINTE de orice cod, descărcare sau calcul V12 (împreună cu `xi/PROTOCOL_XI_P1.md`).
Autoritate: Mesajele 107 (autonomie 100%), 108 (predare la fiecare închidere), 117–122 („vrem predictie”,
„a se calcula pe arhiva din spate”, „putem folosi toate arhivele straine de care ai nevoie”, „c3 conteaza?”).
`positive_claims_allowed=false`. Calcul clasic (CPU, opțional GPU). Componenta „cuantică” a băncii este un model
fermionic de tip Born (proces punctual determinantal, amplitudini = determinanți Slater) calculat EXACT pe hardware
clasic; nu se revendică avantaj cuantic, hardware cuantic sau noutate mondială.

## 0. De ce un plan nou și ce promite (sincer)

Obiectivul declarat de utilizator este predicția numerelor. Dacă extragerile sunt corecte (urnă uniformă,
independentă), NICIO metodă nu poate prezice: orice predictor are, pe termen lung, exact media uniformului.
Singurul lucru pe care îl poate face cinstit un software este să **verifice** dacă o extragere reală se abate de la
uniform într-un mod exploatabil și să publice rezultatul, oricare ar fi. V12 face exact asta, cu o metodă care nu
poate fi „păcălită” de noroc:

- **Scorul.** Fiecare predictor dă, înaintea fiecărei extrageri, o distribuție COMPLETĂ de probabilitate peste toate
  biletele posibile (normalizare exactă). După extragere se calculează raportul de verosimilitate față de uniform.
  Produsul acestor rapoarte, E, este un **e-proces**: dacă urna e corectă, P(E ≥ x vreodată) ≤ 1/x (inegalitatea lui
  Ville), fără aproximări asimptotice, fără simulări, oricât de lungă ar fi arhiva. E = 1 000 înseamnă „mai mult
  decât ar da norocul o dată la 1 000”. E < 1 înseamnă că predictorul a fost mai slab decât ghicitul la întâmplare.
- **Pierdere minimă și la predicție.** Fiecare predictor este o medie bayesiană care include uniformul cu pondere 1/2;
  de aceea E ≥ 1/2 garantat (pierderea maximă în scor este ln 2, oricât de greșită ar fi ipoteza).
- **Rezultatul cel mai probabil, fixat de acum:** „niciun predictor nu bate uniformul”. Se publică oricum, împreună cu
  rezoluția: cât de mare ar fi trebuit să fie o abatere ca s-o vedem (curbele de putere).

## 1. Banca de predictoare (ipoteze distincte, fixate înainte)

| Cod | Ipoteza fizică testată | Model (detalii exacte în PROTOCOL_XI_P1 §3) |
|---|---|---|
| U | urna e corectă (reper) | uniform pe toate biletele |
| STAT | bile/urnă cu abatere constantă în timp | medie bayesiană Dirichlet (4 tării de contracție) + U |
| DRIFT | abatere care se schimbă (seturi de bile/aparat schimbate) | frecvențe cu uitare exponențială (3 timpi de înjumătățire × 2 contracții) + U |
| GAP | memorie mecanică: „restanța” sau „repetarea” | pondere exponențială în timpul de la ultima apariție (4 semne/tării) + U |
| FERMI | structură de perechi respingătoare (bile care „nu ies împreună”) | k-DPP: mașină Born fermionică cu marginalele de perechi potrivite, normalizare exactă prin polinoame simetrice elementare (3 contracții) + U |
| COMB | oricare dintre cele de mai sus | medie bayesiană peste toate cele 17 componente + U |

Nu intră în bancă: modelele închise ale proiectului (QL649, BO649, WU649, GL649, familiile DL/PG/CF/RH/LS/FS/AT/EC/
RA/SR/RB/… din `next_candidate/predictie_numere/`) — nu se rerulează pe aceeași arhivă (AGENTS.md). Ψ-PRED din v10:
numai P-F (k-DPP) intră, ca FERMI; P-B/P-I/P-R rămân în afara V12 (cost mare, normalizare prin enumerare).

## 2. Fazele

| Fază | Conținut | Poartă / rezultat |
|---|---|---|
| **P0** | acest plan + `PROTOCOL_XI_P1.md`, sigilate înainte de cod | sigiliu `xi/SIGILIU_XI_P1.json` |
| **P1** | backtest „ca în ajun” pe arhiva RO (6/49, 5/40, Joker), după calificarea tehnică Q1–Q4 pe date sintetice | E per predictor, Holm la α = 0.01 pe 15 teste; candidați numai (arhiva este EXPLORATĂ) |
| **P2** | arhive străine oficiale: protocol `PROTOCOL_XI_P2.md` sigilat ÎNAINTE de orice descărcare; listă fixată, proveniență (URL, dată UTC, sha256); ultimele 20% din fiecare arhivă, în ordine cronologică, separate la descărcare și NECITITE până la confirmare (test orb) | banca înghețată (cod sha) rulată pe partea de dezvoltare; supraviețuitorii (aceleași praguri) testați o singură dată pe partea rezervată |
| **P3** | confirmare prospectivă numai pentru supraviețuitorii P1/P2: emisii sigilate înainte de cutoff (registru separat), decontare după extragere | prag fixat: E ≥ 1/α_P3 cu α_P3 = 0.001/(nr. supraviețuitori), minim 104 extrageri; altfel PENDING/negativ |
| **Integrare** | un predictor confirmat în P3 intră în C3 ca probabilități modificate în locul uniformului (motorul C3 există) | numai după P3 |
| F, H | registrul pe hârtie (F) și ecranul „Strategii” (H) din V11 | după P1/P2 |

Oprite în V12: atacul pe recordul 163, atlasul Ψ ca scop în sine (cost mare, nerelevante pentru predicție).

## 3. P2 — reguli fixate de acum (detaliile în PROTOCOL_XI_P2, înainte de descărcare)

- **Criterii de includere:** sursă oficială a operatorului sau a unei autorități publice (nu agregatoare), joc de tip
  k din n cu format stabil pe perioada folosită, ≥ 1 000 de extrageri, fișier descărcabil fără cont/plată.
- **Candidați, în ordinea priorității (lista finală, cu URL-urile verificate, se fixează în XI-P2):** Ungaria
  Ötöslottó 5/90 și Hatoslottó 6/45 (Szerencsejáték Zrt.), Franța Loto (FDJ), Polonia Lotto (Totalizator Sportowy),
  Germania Lotto 6aus49, SUA Powerball/Mega Millions (portalul de date deschise al statului New York), Marea Britanie
  Lotto/Thunderball, Italia SuperEnalotto, Spania La Primitiva/Bonoloto, Canada Lotto 6/49. Un candidat fără sursă
  oficială descărcabilă este exclus și consemnat, nu înlocuit cu un agregator.
- **Partea rezervată:** ultimele 20% (rotunjit în jos) din extragerile fiecărui joc, după dată; scrisă într-un fișier
  separat la descărcare, cu sha256, permisiuni 0400; codul de analiză refuză să o citească fără sigiliul de confirmare.
- **Onestitate:** aceste arhive au fost studiate de alții; „orb” înseamnă numai că NOI nu le-am văzut.

## 4. Ce înseamnă rezultatele pentru utilizator

- Dacă nu există supraviețuitori: software-ul arată, pentru fiecare joc, „nicio abatere detectabilă; o abatere a
  bilelor de peste X% ar fi fost văzută” — o informație reală, verificabilă, care lipsește pe piață; motorul C3
  rămâne instrumentul de împărțire a bugetului (regularitate cumpărată, nu profit).
- Dacă există un supraviețuitor confirmat prospectiv: intră în C3; chiar și atunci câștigul așteptat rămâne de
  măsurat (o abatere detectabilă statistic poate fi prea mică pentru profit după reținerea operatorului).

## 5. Reguli permanente

Protocol sigilat înainte de cod/calcule pentru fiecare fază; o singură rulare pe date reale per fază; rezultatele,
inclusiv negative, se publică și nu se rescriu; incidentele se consemnează; fără tuning după rezultat; fără subagenți,
timere sau joburi autonome; git numai `./dev-git status`; orice import `quantum_limit` numai cu `-B` și
`PYTHONDONTWRITEBYTECODE=1`. Predare la fiecare închidere (Mesajul 108) cu `predari/genereaza_predare_v2.py`.
