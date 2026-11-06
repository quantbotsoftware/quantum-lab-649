# Quantum Lab 649 — Manual de utilizare (Română)

> **Notă privind domeniul.** Quantum Lab 649 este un observator combinatoric și spectral *clasic* pentru extragerile istorice de loterie (Loto 6/49, 5/40 și Joker din România, plus zece arhive internaționale). Fiecare operator din el este matematică obișnuită, executată pe GPU sau CPU. Aplicația **nu prezice numere câștigătoare, nu oferă niciun avantaj și nu garantează nimic** — programul însuși impune `positive_claims_allowed = false` pe fiecare ecran și în fiecare fișier sigilat. Este publicată AS-IS sub licența MIT, fără garanție și fără suport tehnic. Citește [DISCLAIMER.md](DISCLAIMER.md) înainte de utilizare.

Acest manual descrie exact ce primești în arhivă, cum o instalezi și o pornești, ce face fiecare control din interfață și la ce să te aștepți când ceva lipsește.

---

## 1. Ce conține arhiva

| Element | Descriere |
|---|---|
| `app.py`, `engine.py`, `parser.py`, `validare.py` | Observatorul principal Loto 6/49: ingestia datelor, cei șase operatori matematici (O1–O6), validarea (Multiversul Nul, backtest walk-forward cauzal) și dashboard-ul Streamlit. |
| `tu3/` | Stratul multi-joc (TU3): motoarele Loto 5/40 și Joker, selectorul de joc, comutatorul sursă LIVE/înghețat și arhivele de extrageri incluse. |
| `hs_v4/`, `pl_v3/`, `tu4/`, `xi/`, `kj_v5/` | Motoare opționale și protocoale de cercetare sigilate (HS-V4 multiplet bosonic + meteo ERA5, PL-V3 Jastrow, tribunalul prospectiv TU4 numai-citire, ecranele de strategii XI, protocolul Rust KJ-V5). |
| `bo649/`, `wu649/`, `gl649/`, `se649/`, `cs649/`, `pl649/` | Șase piste de cercetare *închise*, fiecare cu preînregistrarea sigilată și raportul final. |
| `data/extrageri_649.jsonl` | Peste 2.600 de extrageri Loto 6/49 (JSONL, o extragere pe linie, cu dată, numere și câmpuri de proveniență). |
| `tu3/date/extrageri_540.jsonl`, `tu3/date/extrageri_joker.jsonl`, `tu3/date/live/` | Arhivele Loto 5/40 și Joker plus instantaneul LIVE înghețat (`CURRENT_LIVE.json` → `versiuni/<sha12>/`). |
| `hs_v4/date_intl/`, `hs_v4/date_meteo/` | Zece arhive internaționale (mecanice și RNG electronice) și seria ERA5 de 90 de zile a densității aerului la București. |
| `tests/` | Suita pytest (parser, motor, validare, UI AppTest). |
| `setup_venv.sh`, `run_app_tu3.sh`, `run_app.sh`, `porneste_aplicatia.sh` | Instalatorul și lansatoarele (vezi §3). |
| `desktop/install-desktop-shortcut.sh` | Creează pictograma Linux `quantum-lab-649.desktop` care indică spre folderul tău dezarhivat. |
| `verify_ql649.py` | Verificatorul independent NumPy fp64 pentru artefactele backtest-ului walk-forward. |
| `check-updates.sh` | Verificare manuală de actualizări, fără telemetrie, față de `https://bot-tradingsoftware.com/versions.json`. |
| `PREINREGISTRARE_QL649.md`, `AMENDAMENT_0x.md`, `SIGILIU_*.json`, `RAPORT_QL649.md`, `PLAN_QL649.md` | Protocolul sigilat, amendamentele, sigiliile SHA-256 și raportul publicat. |

**Neincluse intenționat** (se generează local sau se pot cere): rezultatele de rulare `rezultate/`, `hs_v4/cache/`, `xi/rezultate/`, `kj_v5/rezultate/`, `tu4/rezultate/`. Vezi §10.

---

## 2. Cerințe

| Componentă | Minim | Recomandat |
|---|---|---|
| Sistem de operare | Linux x86-64 (testat pe Ubuntu/Pop!_OS 22.04+) | Orice Linux recent cu Python 3.10+ |
| Python | 3.10 | 3.11 / 3.12 |
| GPU | *Opțional.* Fără CUDA motorul trece automat pe CPU (de 10–30× mai lent). | GPU NVIDIA cu ≥ 6 GB VRAM și PyTorch compilat cu CUDA |
| RAM | 8 GB | 16 GB |
| Disc | ~6 GB (mediul virtual cu PyTorch ≈ 4–5 GB + 15 MB date) | — |
| Browser | Orice browser modern (dashboard-ul este servit local pe `http://127.0.0.1:8649`) | Chromium / Firefox |

macOS și Windows nu sunt testate. Codul este Python pur și ar trebui să ruleze oriunde rulează PyTorch și Streamlit, dar scripturile de pornire sunt Bash, iar pictograma de desktop este doar pentru Linux.

---

## 3. Instalare

### 3.1 Descărcare și verificare

1. Descarcă `quantum-lab-649-opensource.zip` de pe [bot-tradingsoftware.com/#downloads](https://bot-tradingsoftware.com/#downloads) sau din GitHub Release [quantbotsoftware/quantum-lab-649](https://github.com/quantbotsoftware/quantum-lab-649).
2. Verifică arhiva (în același folder cu `SHA256SUMS.txt` descărcat):
   ```bash
   sha256sum -c SHA256SUMS.txt --ignore-missing
   ```
3. Dezarhiveaz-o oriunde, **într-o cale fără spații**, de ex. `~/apps/quantum-lab-649/`.

### 3.2 Crearea mediului Python

```bash
cd ~/apps/quantum-lab-649
./setup_venv.sh
```

Scriptul creează `.venv/` și instalează `requirements.txt` (NumPy, SciPy, pandas, **PyTorch**, Streamlit, Plotly, Altair, NetworkX, SymPy, mpmath, pytest). Pe majoritatea sistemelor Linux `pip` alege automat o versiune PyTorch cu CUDA. Dacă ai GPU NVIDIA, dar aplicația raportează ulterior `dispozitiv: CPU (fallback)`, instalează explicit varianta potrivită driverului tău, de exemplu:

```bash
.venv/bin/pip install --index-url https://download.pytorch.org/whl/cu124 torch
```

(vezi [pytorch.org/get-started](https://pytorch.org/get-started/locally/) pentru URL-ul corect).

### 3.3 Pornirea dashboard-ului

```bash
./run_app_tu3.sh
# apoi deschide http://127.0.0.1:8649 în browser
```

Ce face lansatorul, în ordine: compilează toate fișierele `.py` pentru verificarea sintaxei (`py_compile`), tipărește matricea de inițializare TU3 (`jurnal/matrice_*.txt`), afișează dacă a fost detectat CUDA, apoi pornește Streamlit în mod headless pe portul **8649** și scrie jurnalul în `jurnal/app_<timestamp>.log`.

Lansatoare alternative:

| Comandă | Când o folosești |
|---|---|
| `./run_app_tu3.sh` | Pornire normală (recomandat). |
| `./run_app.sh` | Același server, fără matricea de inițializare TU3. |
| `./porneste_aplicatia.sh` | Comportamentul pictogramei: oprește orice server vechi din acest folder, șterge `__pycache__`, pornește `run_app.sh`, așteaptă `/_stcore/health`, deschide browserul. `--stop` oprește serverul. |
| `./desktop/install-desktop-shortcut.sh` | Instalează `quantum-lab-649.desktop` în `~/.local/share/applications/` și pe Desktop. |

Pentru a opri un server pornit din terminal apasă `Ctrl+C`; pentru lansatorul de desktop folosește `./porneste_aplicatia.sh --stop`.

### 3.4 Variabile de mediu utile

| Variabilă | Implicit | Efect |
|---|---|---|
| `QL649_PORT` | `8649` | Portul TCP al dashboard-ului. |
| `QL649_ADDRESS` | `127.0.0.1` | Adresa pe care ascultă. Păstreaz-o locală; aplicația nu are autentificare. |
| `QL649_CONFIG=fast` | nesetat | Configurație rapidă de test (mai puține replici, comutatoarele PL-V3/HS-V4 implicit OFF). Util pe mașini fără GPU pentru a explora rapid interfața. |
| `QL649_SEAL_DIR` | `rezultate/sigilii` | Unde se scriu fișierele de variante sigilate. |
| `QL649_DATA_649` | `data/extrageri_649.jsonl` | Arhivă JSONL 6/49 alternativă (sursa înghețată). |
| `QL649_HSV4_CACHE_DIR` | `hs_v4/cache` | Cache-ul de checkpoint-uri HS-V4 (creat la prima rulare). |
| `PYTHON_BIN`, `STREAMLIT_BIN` | `.venv/bin/…` | Folosește alt interpretor / alt binar Streamlit. |
| `QL649_UI_PROTOCOL=1` | nesetat | Modul UI exact-protocol, folosit de teste. |

---

## 4. Prima pornire — ce vei vedea

Prima încărcare afișează spinner-ul „Inițializare câmp cuantic pe GPU… (prima rulare ≈ 30–40 s)”: motorul ingerează arhiva, construiește tensorii pe pași-zi și rulează o dată întregul lanț de operatori (50.000 de replici Boltzmann, 10.000 de pași MCMC). Rezultatele rămân în cache în procesul serverului, așa că schimbarea tab-urilor este apoi instantanee. Pe CPU prima rulare poate dura câteva minute.

Antetul afișează patru carduri și linia de conformitate:

- **extrageri analizate** — numărul de extrageri folosite după validare și deduplicare.
- **pași (zile)** — numărul de pași de timp (două extrageri în aceeași zi formează un singur pas; fără ordine inventată).
- **ultima extragere** — data celei mai recente extrageri din sursa activă.
- **indice coerență structurală (SCI)** — indicele de coerență structurală în unități σ, cu p-valoarea empirică față de Multiversul Nul (8.192 de istorii sintetice). Valori apropiate de 0σ înseamnă că arhiva nu se distinge de hazardul pur — rezultatul așteptat și onest.
- **dispozitiv** — `cuda` (numele GPU-ului) sau `CPU (fallback)`.
- O linie gri cu `positive_claims_allowed=false`, prefixul SHA-256 al protocolului și amprenta configurației. Dacă apare **MOD FAST (test)**, ai pornit cu `QL649_CONFIG=fast`.

---

## 5. Bara laterală

| Control | Semnificație |
|---|---|
| **🛰 UNIVERS ACTIV → Mod de joc** | Comută întregul dashboard între **Loto 6/49**, **Loto 5/40** și **Joker (5/45 + 1/20)**. Fiecare mod are motorul, arhiva și sigiliile proprii și același aranjament cu 12 tab-uri. |
| **Sursa datelor 6/49** (doar la 6/49) | `LIVE — arhiva actualizată automat` folosește instantaneul versionat din `tu3/date/live/` (pointer → manifest → JSONL verificat SHA). `înghețat (sigilat)` folosește fișierul de protocol `data/extrageri_649.jsonl`. Alegerea se păstrează când schimbi modul. Arhiva descărcată conține un instantaneu LIVE înghețat; el **nu** se actualizează de pe internet (vezi §9). |
| **🔮 Predicție prospectivă (TU4)** | Ecran-tribunal numai-citire care listează emisiile prospective sigilate și decontările lor din `tu4/tribunal/`. Nu rulează niciun motor. |
| **⚛ Motor PL-V3 (Jastrow · 0/6)** | Activează motorul determinantal/Jastrow PL-V3 pe toate cele trei jocuri. Eticheta `0 / 6 porți` = nu a trecut niciuna dintre cele șase porți de promovare, așa cum s-a publicat. |
| **⚛ Motor HS-V4 (Bosonic HS · Aero-Meteo ERA5 · RNG O4 · Portofoliu O3)** | Activează motorul HS-V4 și tab-ul *Internațional & Extrageri Electronice Online* (§7). La o pornire normală de desktop PL-V3 și HS-V4 sunt ON; sub `QL649_CONFIG=fast` sunt OFF. |
| **Pagini: Strategii, Registru** | Intrări multipagină Streamlit (partea de sus a barei laterale). Afișează doar rezultate XI sigilate din `xi/rezultate/`; deoarece rezultatele de rulare nu sunt livrate, afișează o eroare de integritate — este comportamentul așteptat (§10). |

---

## 6. Cele douăsprezece tab-uri (Loto 6/49 — aranjament identic la 5/40 și Joker)

1. **⚛ Colapsul funcției de undă** — TOP-10 amplitudini Born `P = |Ψ|²` după mersul non-hermitic, colorate după fază, alături de planul complex al fazelor pentru toate cele 49 de numere. Înălțimile barelor sunt amplitudini ale *modelului*, nu probabilități de a fi extrase.
2. **🌀 Singularitate hiperbolică & Amplituhedron** — punctul excepțional γ_EP al mersului, valoarea proprie coalescentă λ_EP, quasi-EP-ul real și ancorele hiperbolice; dedesubt, scufundarea pe discul Poincaré a grafului de co-apariție și graficul 3-D al volumului „amplituhedron” (Plotly, rotește cu mouse-ul).
3. **♾ Convergența terminală — Limita Cuantică** — cele trei configurații terminale produse de O5 (filtru Boltzmann pe 50.000 de replici) și O6 (MCMC parallel-tempering + QUBO). Cardurile arată numerele distincte acoperite (x/18), nucleul determinist (numere prezente în ≥ 50 % dintre replici), numărul de replici/pași și timpul GPU. Acestea sunt **minime de energie ale modelului**, documentate ca atare.
4. **🌌 Multiversul Nul** — 8.192 de istorii nule sintetice generate cu același pipeline; distribuția SCI, unde se plasează arhiva reală și p-valoarea empirică. Acest tab este verificarea de onestitate a tuturor celorlalte.
5. **⏳ Mașina Timpului** — backtest-ul walk-forward cauzal unic: la pasul *t* motorul vede numai extragerile `< t`. Carduri: verdict, porți trecute (x/6), numărul de ținte, excesul QL față de uniform pe țintă, starea verificării independente (`PASS` după ce `verify_ql649.py` a fost rulat pe un `rezultate/backtest_unic/` local). Rezultatul publicat este 0/6 porți.
6. **🧪 Ablație & Sigiliu temporal** — un formular cu cinci bife (`O1 walk non-hermitic`, `O2 Amplituhedron`, `O3 Poincaré`, `O4 Kuramoto + interferență`, `Scutul Anti-Mulțime`) și butonul **⚡ Recalculează pe GPU**: debifează un operator ca să vezi cum se schimbă configurațiile terminale fără el. Butonul **🔏 Sigilează variantele curente** scrie un fișier JSON în `rezultate/sigilii/<mod>/` cu variantele curente, amprenta configurației, SHA-ul sursei și un SHA-256 peste conținut — o dovadă datată a ceea ce a spus modelul *înainte* de o extragere viitoare. Sigilarea este locală; nu se încarcă nimic nicăieri.
7. **📉 Rupturi de regim (BO649)** — pistă închisă: detecție bayesiană online a punctelor de schimbare (Beta–Bernoulli, h = 1/250). Afișează protocolul sigilat, cardurile de verdict și linkul spre raport.
8. **🎱 Urna ponderată (WU649)** — pistă închisă: model de urnă ponderată cu certificate raționale exacte (fp64 pe CPU). Starea `NERULAT` este normală până când există rezultate locale.
9. **🔢 Masa glifelor (GL649)** — pistă închisă: model Bayes liniar al masei glifelor (Goldstein–Wooff), exact în ℚ.
10. **🍂 Anotimpurile bilelor (SE649)** — pistă închisă: model sezonier cu martori Q5/Q6 analitici.
11. **🎠 Caruselul seturilor (CS649)** — pistă închisă: carusel de seturi Bayes liniar prin ecuațiile Henderson 16×16.
12. **🌌 Orizontul evenimentelor (PL649)** — pistă închisă: model determinantal PL649 (randat de `ui_pl649`).

Tab-urile 7–12 sunt tab-uri de documentare: afișează protocolul preînregistrat, cardurile de calificare/backtest și trimit la `*/RAPORT_*.md`. Cardurile lor metrice arată `—` sau `NERULAT` până când generezi local directoarele `rezultate/` corespunzătoare cu scripturile pistei respective.

---

## 7. Motorul HS-V4 (comutator ON în bara laterală)

Când HS-V4 este activ pentru jocul selectat, zona principală este înlocuită de observatorul HS-V4:

- **Configurație canal HS-V4 (RO)** (bara laterală): `Full_HSV4` (O1 + O2 + O4), `O1_O2`, `O1_O4` sau doar `O1` — configurația de ablație.
- O linie de sincronizare: `CACHE HIT` sau `AVANS CAUZAL +n PAȘI` (câți pași noi au fost procesați cauzal), cheia sursei, SHA-ul checkpoint-ului, `Q1–Q6: 6/6 PASS` (calificarea algebrică pre-arhivă) și verdictul porților walk-forward (publicat: 0/6 — fără promovare), plus VRAM-ul rezidual.
- **🎯 1-CLICK: Vezi Câte & Unde Ar Fi Fost Potriviri** — deschide un inspector istoric „câte și unde” pentru toate cele trei jocuri românești (și fluxurile internaționale). Numără, *după fapt*, cât de des configurațiile terminale ale modelului ar fi potrivit ≥ k numere. Este un audit descriptiv, nu o prognoză; apasă același buton (acum etichetat ✖) pentru a-l închide.
- Patru sub-tab-uri:
  1. **⚛ Stări Statistice (α, β, γ) · Spectru & Meteo ERA5** — valorile proprii Hubbard–Stratonovich (brute / atenuate / Jennrich), seria ERA5 de 90 de zile a densității aerului la București și probabilitățile marginale exacte de incluziune π_i față de linia uniformă k/N.
  2. **📉 Calificare Q1–Q6 · Porți G1–G6 & Ablație RO** — cele șase verificări algebrice de calificare, cele șase porți de promovare walk-forward și tabelul de ablație (canale O1/O2/O4, coloane Brier și LogScore).
  3. **📊 Martingala E_s · Mase Bayesiene & Categorii RO** — traiectoria martingală E_s, masele posterioare bayesiene w₀/w₀₁/w₀₂/w₀₄ care colapsează pe canalul uniform și categoriile hipergeometrice așteptat-vs-observat (3+ … 6/6).
  4. **🌍 Internațional & Extrageri Electronice Online** — selectorul *Selectează loteria externă*: FR Loto, HU Hatoslottó / Ötöslottó / Skandináv (manual vs mașină 7/35), US Powerball și extrageri RNG electronice (EuroDreams, NY Take 5 / Cash4Life / Pick 10). Fluxurile mecanice și RNG sunt comparate cu același pipeline; experimentul pereche HU 7/35 și controlul negativ ERA5 pe extrageri pur-RNG sunt controalele.

Prima rulare HS-V4 pe joc construiește `hs_v4/cache/` (câteva sute de MB, GPU ≈ 1–3 min, CPU considerabil mai mult); pornirile următoare sunt cache hit.

---

## 8. PL-V3 și TU4

- **PL-V3** (comutator) randează motorul Jastrow/determinantal cu același banner de onestitate (`PLV3_NO_PROMOTION_EXPLORATORY · 0 / 6 porți`). Variantele lui sunt moduri determinantale ale modelului.
- **TU4 — 🔮 Predicție prospectivă** este numai-citire. Listează emisiile sigilate din `tu4/tribunal/emisii/` și decontările din `tu4/tribunal/decontari/`, cu lanțul lor SHA-256. Nu calculează niciodată nimic și afișează ce este disponibil în arhivă (folderele de emisii și decontări sunt livrate; fișierul de lanț `LANT.jsonl` nu este, deci cardul lanțului îl raportează ca lipsă).

---

## 9. Date: ce este inclus și cum se actualizează

- Toate arhivele sunt fișiere **JSONL** simple — o extragere pe linie, de ex. `{"draw_date": "2000-09-14", "game": "joker", "numbers": [4, 27, 30, 32, 39], "joker": 7, …}` — validate la încărcare (6/49: șase numere distincte în 1..49; 5/40: șase extrase în 1..40, cu cinci pe bilet; Joker: cinci distincte în 1..45 plus unul în 1..20). Duplicatele sunt eliminate, iar extragerile sunt ordonate cronologic.
- Sursa **LIVE** este un *instantaneu înghețat* în această arhivă. Proiectul original o reîmprospătează dintr-un colector extern care descarcă rezultatele oficiale de pe loto.ro la fiecare 30 de minute; acel colector este un sistem separat și **nu** face parte din această versiune. Aplicația nu descarcă nimic de una singură.
- Pentru a analiza extrageri mai noi, adaugă linii în același format într-o copie a fișierului JSONL și indică `QL649_DATA_649` spre ea (sursa înghețată), sau creează un nou folder de versiune sub `tu3/date/live/versiuni/` cu un `MANIFEST_LIVE.json` corespunzător și actualizează `CURRENT_LIVE.json` (sursa LIVE). Parserul refuză orice versiune al cărei SHA-256 nu corespunde manifestului.
- Fișierele de proveniență (`tu3/date/MANIFEST_DATE.json`, `tu3/date/VERIFICARE_WEB_20261026.json`, `hs_v4/date_intl/PROVENIENTA_INTL.json`) consemnează de unde provine fiecare arhivă și hash-ul ei.

---

## 10. Fișiere generate local sau disponibile la cerere

| Cale | Stare | Cum se obține |
|---|---|---|
| `rezultate/backtest_unic/` | generat | Rulează backtest-ul walk-forward o dată (tab-ul 5 îl calculează la prima utilizare pentru sursa activă); apoi `python verify_ql649.py` produce `PASS`-ul independent. |
| `rezultate/sigilii/` | generat | Apasă **🔏 Sigilează variantele curente**. |
| `hs_v4/cache/` | generat | Creat automat de motorul HS-V4. |
| `xi/rezultate/`, `kj_v5/rezultate/`, `tu4/rezultate/`, `bo649/…/rezultate/` etc. | rezultate de cercetare, nelivrate | Se pot regenera cu scripturile fiecărei piste sau se pot cere copiile arhivate: deschide o *cerere de documentație* pe [GitHub Issues](https://github.com/quantbotsoftware/quantum-lab-649/issues/new?template=documentation_request.md) sau scrie la [contact@bot-tradingsoftware.com](mailto:contact@bot-tradingsoftware.com). Se oferă strict AS-IS, dacă există. |
| Protocoale/rapoarte extinse (`PLAN_QL649.md`, `PREINREGISTRARE_QL649.md`, `RAPORT_QL649.md`, protocoalele TU3/TU4/XI) | incluse | Se citesc din rădăcina arhivei și din subfoldere. |

---

## 11. Teste și verificare

```bash
.venv/bin/python -m pytest -q -p no:cacheprovider tests/
```

Acoperă parserul (validare, deduplicare, pași-zi), motorul (punct excepțional exact 2×2, MCMC vs Boltzmann exact și vs enumerarea exhaustivă a tuturor celor 13.983.816 combinații, cauzalitate, paritate CPU/GPU), validarea și interfața Streamlit AppTest. Testele GPU sunt sărite automat fără CUDA. Durată estimată: 10–20 de minute pe o mașină cu GPU.

Integritatea protocolului: fiecare `SIGILIU_*.json` conține SHA-256-ul documentului pe care îl sigilează; recalculează cu `sha256sum <fișier>` și compară.

Verificarea actualizărilor (manuală, fără telemetrie):

```bash
./check-updates.sh
```

---

## 12. Depanare

| Simptom | Cauză / rezolvare |
|---|---|
| `ERROR: python3 and/or streamlit not found` | Rulează mai întâi `./setup_venv.sh` sau setează `PYTHON_BIN` / `STREAMLIT_BIN`. |
| Portul 8649 este deja ocupat | Rulează altă instanță: `./porneste_aplicatia.sh --stop` sau pornește cu `QL649_PORT=8650 ./run_app_tu3.sh`. |
| Antetul arată `CPU (fallback)` deși ai GPU NVIDIA | PyTorch a fost instalat fără CUDA sau driverul este mai vechi decât versiunea CUDA a pachetului. Reinstalează pachetul potrivit (§3.2) și verifică `nvidia-smi`. |
| `🛰 Sursa 6/49: LIVE indisponibilă (...)` | Instantaneul LIVE nu a putut fi verificat (fișiere modificate sau mutate). Alege *înghețat (sigilat)* din bara laterală sau restaurează `tu3/date/live/`. Aplicația nu comută niciodată tăcut între surse. |
| Paginile **Strategii** / **Registru** afișează eroare de integritate | Au nevoie de `xi/rezultate/H` și `xi/rezultate/F`, rezultate de cercetare neincluse în arhivă (§10). |
| Tab-urile pistelor închise arată `—` / `NERULAT` | Normal: fișierele lor de rezultate sunt generate de scripturile pistei, nu livrate. |
| Prima încărcare durează multe minute | Fallback pe CPU. Folosește `QL649_CONFIG=fast ./run_app_tu3.sh` ca să explorezi interfața cu o configurație redusă. |
| Pagină goală sau înghețată după modificarea codului | Streamlit păstrează modulele în cache în procesul serverului. Repornește cu `./porneste_aplicatia.sh` (șterge `__pycache__` și repornește). |
| Jurnale | `jurnal/app_*.log`, `jurnal/matrice_*.txt`, `jurnal/lansator_*.log`. |

---

## 13. Memento legal și de domeniu

- Licența MIT — poți folosi, modifica și redistribui codul, păstrând notița de copyright și licența.
- `positive_claims_allowed = false` nu este un slogan: interfața, sigiliile și rapoartele sunt construite astfel încât **niciun ecran să nu prezinte o combinație ca fiind mai probabil extrasă**. Extragerile de loterie sunt evenimente aleatoare independente; fiecare bilet are aceeași probabilitate.
- Nimic de aici nu este sfat de joc, financiar sau juridic. Joacă responsabil sau, mai bine, tratează aceasta drept ceea ce este — un teren de joacă pentru matematică și inginerie GPU.
- Nu se oferă suport tehnic. Doar pentru documente *existente*: [cerere de documentație pe GitHub](https://github.com/quantbotsoftware/quantum-lab-649/issues/new?template=documentation_request.md) · [contact@bot-tradingsoftware.com](mailto:contact@bot-tradingsoftware.com).
- Arhivă permanentă și citare: CERN Zenodo DOI [10.5281/zenodo.23992530](https://doi.org/10.5281/zenodo.23992530).
