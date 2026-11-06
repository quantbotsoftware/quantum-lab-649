# PROTOCOL XI-P2 — arhive străine oficiale, test orb (planul V12, faza P2)

Scris și sigilat (`xi/SIGILIU_XI_P2.json`) ÎNAINTE de orice acces de rețea la siturile candidaților, de orice
descărcare de date, de orice cod P2 și de orice calcul P2. Autoritate: Mesajele 107/108, 117–122 (în special 121:
„putem folosi toate arhivele straine de care ai nevoie”) și cererea din 2026-10-31 seara (Mesajul 124 al
suplimentului). Plan: `xi/PLAN_V12_PREDICTIE.md` (`a675289e…`, §2–§3). `positive_claims_allowed=false`. Calcul clasic
float64 pe CPU (`/usr/bin/python3 -B`, `PYTHONDONTWRITEBYTECODE=1`, NumPy 2.5.3, `multiprocessing` pe 24 de fire);
GPU nefolosit. Nimic din `quantum_limit` nu este importat.

## 0. Sigilare în două trepte (de ce și cum)

- **Treapta A (acest fișier):** criteriile, procedura de inventar, regula de separare a părții rezervate, analiza,
  pragurile, calificarea, verificarea și interpretările. Se sigilează înaintea oricărui acces de rețea la candidați.
- **Treapta B (`xi/PROTOCOL_XI_P2_ANEXA_SURSE.md` + `xi/p2/SURSE_P2.json`, sigiliu
  `xi/SIGILIU_XI_P2_SURSE.json`):** lista finală a jocurilor incluse/excluse, URL-urile exacte, formatul k din n pe
  subjocuri, data de început a perioadei cu format stabil, regulile de citire a fișierului. Se scrie numai din
  inventarul de la §2 și se sigilează ÎNAINTE de orice cod P2 și de orice descărcare de fișier de date.
  Treapta B nu poate schimba nimic din treapta A (analiză, praguri, separare, interpretări).

## 1. Întrebările

- **P2a (primară, partea de dezvoltare).** Pentru fiecare joc inclus g și fiecare predictor
  X ∈ {STAT, DRIFT, GAP, FERMI, COMB} din banca înghețată P1, respinge e-valoarea E^dev_{g,X} ipoteza „extragerile
  jocului g sunt uniforme și independente”? Plus **testul global** pe predictor: E^dev_{★,X} = ∏_g E^dev_{g,X}
  (jocuri diferite = operatori, aparate și urne diferite, independente fizic; produsul de e-valori independente este
  e-valoare sub ipoteza nulă globală „toate jocurile sunt uniforme”). Familia Holm: toate cele 5·G teste pe jocuri +
  5 teste globale (acestea numai dacă G ≥ 2), α = 0.01. Supraviețuitori = testele respinse.
- **P2b (confirmare oarbă, o singură rulare).** Pentru fiecare supraviețuitor: e-valoarea pe partea rezervată
  E^rez = ∏_{t ∈ rezervă} P_X(S_t | toate extragerile anterioare, inclusiv dezvoltarea) / P_U(S_t) (un produs de
  rapoarte condiționate care începe la un moment fixat este e-valoare; ponderile mixturii continuă din dezvoltare).
  Pentru un supraviețuitor global: E^rez_{★,X} = ∏_g E^rez_{g,X}. Holm la α = 0.01 pe numărul de supraviețuitori.
- **P2c (descriptivă).** Rezoluția per joc (curba de putere STAT la lungimea părții de dezvoltare), nimeririle
  biletului de vârf pe dezvoltare față de hipergeometric, log E pe jumătățile părții de dezvoltare, ponderile finale.
  Nu schimbă verdictul.

## 2. Inventarul (după sigilarea treptei A, înainte de treapta B)

- Candidații, în ordinea priorității din plan (§3): Ungaria Ötöslottó 5/90 și Hatoslottó 6/45 (Szerencsejáték Zrt.),
  Franța Loto (FDJ), Polonia Lotto (Totalizator Sportowy), Germania Lotto 6aus49, SUA Powerball și Mega Millions
  (portalul de date deschise al statului New York, data.ny.gov), Marea Britanie Lotto și Thunderball (Camelot/Allwyn,
  The National Lottery), Italia SuperEnalotto, Spania La Primitiva și Bonoloto (SELAE), Canada Lotto 6/49. Nu se
  adaugă alte jocuri; un candidat nu se înlocuiește cu altul.
- Acțiuni permise: căutări web pentru pagina oficială; GET pe pagini HTML ale operatorului/autorității printr-un
  script care înregistrează numai starea HTTP, tipul conținutului și legăturile (href) spre fișiere de date
  (.csv/.zip/.xls/.xlsx/.txt/.json, API-uri de export), fără afișarea textului paginii; HEAD pe URL-urile de fișiere
  de date (stare, tip, mărime, Last-Modified, ETag). Interzis: GET pe un fișier de date; deschiderea paginilor de
  rezultate care afișează numere. Orice expunere accidentală la numere extrase (de exemplu, un fragment de căutare)
  se consemnează în inventar cu sursa; numerele respective nu se notează.
- Ieșire: `xi/p2/INVENTAR_P2.json` (UTC, URL, stare, antete, legături găsite, decizia și motivul).
- **Criterii de includere (plan §3):** sursă oficială a operatorului sau a unei autorități publice (nu agregatoare,
  nu oglinzi neoficiale); fișier descărcabil direct, fără cont, plată sau cheie API; joc de tip k din n (eventual cu o
  bilă suplimentară dintr-o urnă separată, ca la Joker); perioadă cu format stabil cu cel puțin 1 000 de extrageri
  (numărate după descărcare; sub prag ⇒ exclus, consemnat). Pagini HTML de rezultate pe ani/extrageri („scraping”)
  NU sunt fișier descărcabil ⇒ candidatul este exclus și consemnat.
- Data de început a formatului stabil se fixează în treapta B din documentația publică (operator; altfel o sursă
  enciclopedică citată), nu din date. O bilă suplimentară extrasă din aceeași urnă după cele k (de exemplu „bonus”)
  NU se modelează (se ignoră); o bilă dintr-o urnă separată (Powerball, Mega Ball, numéro chance) se modelează ca
  subjoc separat (n', 1), ca bila Joker.

## 3. Descărcarea, proveniența și separarea (după sigilarea codului, §6)

- `xi/p2/descarca.py` (cod sigilat): pentru fiecare joc inclus descarcă o singură dată fiecare URL din treapta B
  (cel mult 3 încercări la erori de rețea, toate înregistrate); scrie octeții bruți în `xi/date_p2/<joc>/sigilat/`
  cu `PROVENIENTA.json`: URL cerut, URL final, stare, antetele HTTP (Date, Last-Modified, ETag, Content-Length,
  Content-Type), UTC, sha256 și mărimea.
- Citirea conform regulilor din treapta B; validare: exact k numere distincte în 1..n pe fiecare subjoc, dată/ordine
  citibilă, rânduri anterioare datei de început excluse după dată (nu după conținut). Orice rând invalid în perioada
  stabilă ⇒ jocul este exclus (incident), fără reparare improvizată. Duplicatele exacte ale aceleiași extrageri
  (aceeași cheie și aceleași numere) se păstrează o dată și se numără.
- Ordinea: cronologică după data extragerii (și cheia oficială a extragerii la egalitate). T = numărul de extrageri
  din perioada stabilă; **R = ⌊0.2·T⌋ ultimele extrageri sunt partea rezervată**; primele T − R sunt dezvoltarea.
- Scrie `xi/date_p2/<joc>/dev.json` (0444) și `xi/date_p2/<joc>/rezerva.json` (0400; sha256 în
  `xi/date_p2/<joc>/REZERVA_SHA256.txt`); fișierele brute din `sigilat/` devin 0400 (conțin și rezerva). Pe ecran și
  în jurnal apar numai: T, R, datele primei/ultimei extrageri ale fiecărei părți, numerele de rânduri excluse/duplicate,
  sha-urile. **Niciun număr extras nu se afișează.**
- Dacă citirea eșuează (format diferit de cel declarat), descărcătorul afișează numai linia de antet a fișierului și
  „forma” rândului problematic (cifrele înlocuite cu 9), nu valorile; incidentul se consemnează, iar regula de citire
  se poate corecta printr-un amendament sigilat care NU schimbă jocul, URL-ul, data de început, analiza sau pragurile.
- Codul de analiză refuză orice cale din `sigilat/` sau `rezerva.json` până la existența
  `xi/p2/SIGILIU_CONFIRMARE_P2.json` (§7), cu sha-ul rezultatelor de dezvoltare și lista supraviețuitorilor.

## 4. Banca înghețată (aceleași componente și ponderi, aceleași formule pentru alte (n, k))

- Modulul nou `xi/p2/p2.py` importă funcțiile din `xi/p1/banca.py` după verificarea sha-ului `d7d1cbb4…` (fișier
  neschimbat, import fără bytecode): `components`, `priors`, `run_components`, `mixture_seq`, `logE_closed`, `ticket`,
  `hyper_pmf`, `conv_power`, `binom_sf`, `holm`, `lse`, `gen_history`. Familiile calificate sunt cele din
  `xi/p1/SIGILIU_COD_P1.json` (STAT, DRIFT, GAP, FERMI; COMB calificat); nicio recalificare a familiilor, niciun
  parametru nou, nicio componentă nouă.
- Fiecare subjoc (n, k) primește mixturile P1 (ρ_U = 1/2; pentru k = 1, FERMI folosește U, iar COMB împarte 1/2 între
  STAT, DRIFT, GAP). Un joc cu mai multe subjocuri: log E = suma pe subjocuri (ca la Joker).
- Predicția pentru extragerea t folosește numai extragerile 1..t−1 ale aceluiași joc („ca în ajun”). Jocurile nu se
  amestecă între ele.

## 5. Calificarea tehnică (date sintetice; înainte de orice descărcare de date)

Seminții fixe NumPy PCG64: 20261101 + deplasare declarată în cod. Pentru fiecare (n, k) distinct din treapta B:

- **Q1 exactitate:** (a) suma P(S) pe toate cele C(n, k) mulțimi = 1 ± 10⁻⁹ pentru o componentă CB cu ponderi
  aleatoare și pentru o componentă FERMI construită dintr-o istorie sintetică (enumerare completă pentru
  C(n, k) ≤ 5·10⁷; peste ⇒ marginalele CB și FERMI față de verificatorul independent ≤ 10⁻¹⁰ și suma marginalelor = k
  ± 10⁻⁹); (b) limita uniformă: fiecare componentă la t = 1 dă 1/C(n, k) (relativ ≤ 10⁻¹²); (c) log E ≥ −ln 2 − 10⁻¹²
  pe fiecare subjoc pe toate istoriile Q3.
- **Q2 predictibilitate:** pe o istorie sintetică per joc, la t₀ = ⌊T_dev/2⌋, înlocuirea extragerilor ≥ t₀ lasă
  bit-identice log-probabilitățile și biletele pentru t ≤ t₀.
- **Q3 nul:** 100 de istorii uniforme per joc, cu lungimea dezvoltării din treapta B (estimarea ei; dacă T real
  diferă, Q3 nu se repetă — e-valorile sunt valide la orice lungime): pentru fiecare predictor fracția cu E ≥ 20
  ≤ 0.10; la fel pentru testul global (istoria r a fiecărui joc formează replica r). Depășire ⇒ defect de cod.
- **Q4 cititorul:** fișiere sintetice scrise după formatul declarat în treapta B (inclusiv rânduri anterioare datei de
  început, un duplicat și ordinea inversă) ⇒ cititorul produce exact extragerile generate, aceeași separare 80/20 și
  refuză un fișier cu un rând invalid.
- **Q5 garda rezervei:** fără `SIGILIU_CONFIRMARE_P2.json`, orice comandă de analiză care ar atinge rezerva se
  oprește (testat pe un director sintetic).
- **Descriptiv (rezoluția P2c):** per joc, 20 de istorii STAT cu cote 1+δ / 1/(1+δ) pe jumătățile numerelor, δ ∈ {0.05,
  0.10, 0.20}, lungimea dezvoltării: fracția cu E ≥ 1500 și mediana log E.
- Un eșec Q1–Q5 este defect tehnic: se corectează codul, se consemnează incidentul (fișierele încercării păstrate),
  se reiau testele. După PASS codul se sigilează (`xi/p2/SIGILIU_COD_P2.json`, fișiere 0444) ÎNAINTE de descărcare.

## 6. Ordinea execuției

1. Sigiliul treptei A. 2. Inventarul (§2). 3. Treapta B + sigiliul ei. 4. Codul: `descarca.py`, `p2.py`,
`verifica_p2.py`. 5. Calificarea Q1–Q5 + descriptivele. 6. Sigiliul codului. 7. Descărcarea + separarea (o dată).
8. Producția pe dezvoltare (o singură rulare; `p2.py dezvoltare` refuză repetarea). 9. Verificarea independentă.
10. `SIGILIU_CONFIRMARE_P2.json` (supraviețuitorii, sha-urile dezvoltării și verificării). 11. Numai dacă există
supraviețuitori: `p2.py confirmare` — o singură rulare pe rezervă, numai pentru ei; verificare independentă.
12. `RAPORT_P2.md` din artefacte.

## 7. Producția și verificarea

- `p2.py dezvoltare`: verifică sha-urile (treptele A/B, cod, `banca.py`, `dev.json`), calculează și scrie în
  `xi/rezultate/P2/`: `p2_dev_pas.jsonl` (per joc și t: log-probabilitățile componentelor și predictorilor, biletele,
  nimeririle), `P2_DEV_REZULTATE.json`, `RAPORT_P2_DEV_CIFRE.md`, toate 0444. Pragul Bonferroni al celui mai mic p:
  E ≥ M/α.
- `verifica_p2.py` (fără niciun import din `banca.py` sau `p2.py`; folosește algoritmii independenți din
  `xi/p1/verifica_p1.py`, sha `d39f914f…`, plus cod propriu pentru citirea `dev.json`, mixturi, produsul global și
  Holm): toleranțe 10⁻⁸ pe log-probabilitățile pe pas și 10⁻⁶ pe log E agregat. Scrie `VERIFICARE_P2_DEV.json`.
- `SIGILIU_CONFIRMARE_P2.json` se scrie numai după `VERIFICARE_P2_DEV.json` PASS; supraviețuitorii provin din
  `P2_DEV_REZULTATE.json`, fără alegere manuală.
- `p2.py confirmare` (numai dacă lista nu e goală): citește rezerva (sha verificat), continuă secvența pe jocurile
  supraviețuitorilor și scrie `P2_REZ_REZULTATE.json` + `RAPORT_P2_REZ_CIFRE.md` (0444); refuză repetarea.
  Verificare independentă `VERIFICARE_P2_REZ.json`.

## 8. Interpretări fixate

- Nicio respingere pe dezvoltare ⇒ **`P2_NICIUN_SUPRAVIETUITOR`**: „pe arhivele străine incluse, niciun predictor din
  bancă nu bate uniformul”; se raportează rezoluția. Rezerva rămâne SIGILATĂ și NECITITĂ: poate servi ca test orb
  pentru o ipoteză distinctă viitoare, numai cu protocol nou sigilat înainte.
- Respingeri pe dezvoltare și respingere Holm pe rezervă ⇒ **`P2_CONFIRMAT_ORB`** (lista): candidați pentru P3
  (confirmare prospectivă, prag din plan). Respingeri pe dezvoltare fără respingere pe rezervă ⇒
  **`P2_NECONFIRMAT`** (supraviețuitorii cad).
- Nimic din P2 nu autorizează afirmații de avantaj, câștig sau profit; `positive_claims_allowed=false`. Un rezultat
  negativ nu demonstrează imposibilitatea tuturor metodelor; este însă o măsurătoare cu rezoluție publicată.
- **Onestitate despre „orb”:** aceste arhive au fost studiate de alții; „orb” înseamnă numai că acest proiect nu a
  citit rezerva. Agentul, fiind un model de limbaj, poate avea în datele de antrenament extrageri istorice ale acestor
  loterii celebre; banca este însă înghețată în cod sigilat înainte de descărcare, deci o asemenea cunoaștere nu poate
  influența predicțiile sau pragurile.

## 9. Distinctivitate și precedente

Aceeași bancă P1 (precedentele atribuite acolo: Poisson condiționat, Dirichlet–multinomial, uitarea exponențială,
procese punctuale determinantale, evaluarea prequențială, Ville, e-valori). Nou în P2: aplicarea înghețată pe urne
străine cu altă geometrie (n, k), testul global prin produsul e-valorilor independente (Vovk & Wang 2021, combinarea
e-valorilor) și partea rezervată oarbă separată la descărcare. Nu se rerulează modelele închise ale proiectului.
Fără subagenți, timere sau joburi autonome; git numai `./dev-git status`.
