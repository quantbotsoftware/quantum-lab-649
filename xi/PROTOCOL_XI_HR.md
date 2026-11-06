# PROTOCOL XI-HR — ecranul „Registrul pe hârtie” (planul V11, faza H, versiunea 2 a ecranelor; legat de faza F)

Scris și sigilat (`xi/SIGILIU_XI_HR.json`) ÎNAINTE de orice cod HR, de orice pagină nouă și de orice rulare HR.
Autoritate: Mesajele 107/108 (autonomie, aplicație funcțională, predare la fiecare sesiune), cererea din 2026-10-31
(Mesajul 126 al suplimentului: H2, decontarea F, înregistrarea 2026-11-05) și `predari/OPERATIV.md` (checkpoint
20261031T210720Z, „Neînceput” punctul 3: „H v2 … secțiunea «Registrul pe hârtie» pe ecran (miză, plăți, net cumulat pe
strategie, din `DECONTARI_STRATEGII.jsonl`), fără bilete”). Planuri: `xi/PLAN_V11_QL_XI.md` (`2fb304f4…`, §5 fazele F/H),
`xi/PROTOCOL_XI_F.md` (`ba74568f…`), `xi/PROTOCOL_XI_H.md` (`2c8da0a6…`). `positive_claims_allowed=false`. Calcul
clasic, CPU, Python standard + Streamlit (fără NumPy, fără GPU, fără `quantum_limit`, fără `torch`).

## 0. Ce este și ce nu este

- **Este:** o pagină de citire care arată, din registrul F sigilat, ce s-a înregistrat pe hârtie pentru fiecare
  extragere viitoare (strategii, bilete numărate, miză, cutoff) și, după decontare, plățile și netul pe țintă, pe
  strategie și pe familie (C1 / C3 / RND), cu fracția returnată.
- **Nu este:** o predicție, o recomandare de numere sau de bilete, o promisiune de câștig. Pagina NU afișează niciun
  bilet, nicio listă de numere și nici numerele extrase (sunt publice în altă parte; aici nu adaugă nimic). Toate
  strategiile au ρ < 1 (C1, C3): pierderea pe hârtie este rezultatul așteptat; câteva extrageri sunt zgomot.

## 1. Fișiere

- Pagina: `pages/2_Registru.py` (MPA Streamlit, lângă `pages/1_Strategii.py`). `app.py` (`7c5da1e6…`),
  `pages/1_Strategii.py`, `tu3/ui_tu3.py`, motorul și codul F (`xi/f/*`, sigiliul `6e687c30…`) NU se modifică.
- Calificare: `xi/hr/teste_hr.py` (numai directoare temporare). Verificator independent: `xi/hr/verifica_hr.py` (nu
  importă pagina; recalculează agregatele din registru cu cod propriu și compară cu textul randat prin AppTest).
- Sigiliul codului: `xi/hr/SIGILIU_COD_HR.json` (după calificare, înaintea verificării pe registrul real).
  Rezultate: `xi/rezultate/HR/` (jurnalul testelor, `VERIFICARE_HR_<UTC>.json`, `RAPORT_HR.md`).
- Surse citite de pagină (numai citire, fără sha fix — sunt append-only și cresc): `xi/rezultate/F/LANT_STRATEGII.jsonl`
  (obligatoriu) și `xi/rezultate/F/DECONTARI_STRATEGII.jsonl` (opțional; lipsa = nicio decontare încă).

## 2. Integritatea (pagina refuză afișarea la orice abatere)

Pentru fiecare fișier: fiecare linie `o` trebuie să fie JSON canonic (`sort_keys`, separatori `(",", ":")`,
`ensure_ascii=False`) identic octet cu octet cu linia, `o.seq == i`, `o.prev_sha256 ==` sha-ul liniei precedente
(64 de zerouri la prima), `o.sha256 == sha256(canonic(o fără sha256))`. Registrul: `tip == "INREGISTRARE"` și
`protocol_sha256 == ba74568f40fa62303bef59bbd7c23d46b527ec53e00297c59f71670a0b7d3220` pe fiecare linie; decontările:
`tip == "DECONTARE"`, `status ∈ {DECONTAT, VOID}`, `ref_seq` existent în registru cu `ref_sha256` egal cu sha-ul
liniei lui, cel mult o decontare per `ref_seq`. Orice abatere ⇒ un singur `st.error`, nicio secțiune, `st.stop()`.

## 3. Aritmetica (fixată aici, fără alți parametri)

- Familia unei strategii = prefixul identificatorului până la primul `_` (`C1`, `C3`, `RND`).
- Starea unei înregistrări: `DECONTAT` / `VOID` după decontarea ei; altfel `ÎN AȘTEPTARE`.
- Agregatele monetare folosesc NUMAI înregistrările `DECONTAT`: miză Σ `miza` (din registru), plăți Σ
  `rezultat.plata`, net Σ `rezultat.net`, fracția returnată = plăți / miză (afișată „—” la miză 0). `VOID` se numără,
  dar nu intră în sume. Formatul: lei cu 2 zecimale (separator de mii spațiu), fracția în procente cu 1 zecimală.
- Secțiunile (titluri fixe): „1. Țintele înregistrate” (pe dată: jocuri, strategii, bilete, miză totală, cutoff,
  momentul înregistrării, decontate / în așteptare / VOID, plăți și net pe decontate); „2. Rezultatul pe strategie”
  (pe strategie cu cel puțin o decontare `DECONTAT`: familie, joc, ținte decontate, miză, plăți, net, fracție; dacă nu
  există: un `st.info` care spune că prima decontare vine după extragerea țintei celei mai vechi și publicarea
  plăților); „3. Pe familii” (C1, C3, RND: strategii·ținte decontate, miză, plăți, net, fracție); „4. Ce înseamnă”
  (text fix: ρ < 1, zgomot pe puține extrageri, rolul controlului aleator, fără bilete/sfaturi).
- Un avertisment fix în capul paginii și o legendă cu capetele celor două lanțuri (primele 16 caractere ale sha),
  numărul de linii și sha-ul acestui protocol.

## 4. Calificarea (`teste_hr.py`, înainte de sigiliul codului; numai directoare temporare)

- **T1** registru sintetic (3 înregistrări pe 2 date, lanț valid) + decontări (una `DECONTAT`, una `VOID`): pagina
  randează fără excepție, cu cele 4 titluri, iar textul conține exact valorile calculate de mână în test (miză, plăți,
  net, fracție pe țintă, pe strategie, pe familie) și stările „ÎN AȘTEPTARE”/„VOID”.
- **T2** fără `DECONTARI_STRATEGII.jsonl`: fără excepție, secțiunea 2 arată `st.info`, toate țintele „în așteptare”.
- **T3** un octet alterat în registru ⇒ exact un `st.error`, niciun titlu de secțiune, nicio tabelă.
- **T4** o decontare cu `ref_sha256` greșit (lanț de decontări altfel valid) ⇒ exact un `st.error`, nicio secțiune.
- **T5** static + execuție: sursa paginii nu conține `["bilete"]`, `import torch`, `quantum_limit`, `engine`,
  `ui_tu3`; după randare, niciunul dintre aceste module nu este încărcat; textul randat nu conține liste de ≥ 5 numere.
- **T6** MPA: un `main.py` minimal + `pages/2_Registru.py` într-un director temporar; `switch_page` deschide pagina.

## 5. Verificarea pe registrul real (`verifica_hr.py`) ⇒ poarta HR

V1 protocol sigilat (0444) și codul sigilat (sha egal cu `SIGILIU_COD_HR.json`); V2 recalcul independent al tuturor
agregatelor (§3) din fișierele reale și prezența fiecărei valori formatate în textul randat (AppTest pe pagina reală);
V3 fără liste de numere și fără bilete în text; V4 fără module interzise încărcate; V5 `app.py`, `pages/1_Strategii.py`,
`xi/rezultate/H/STRATEGII_DATE.json`, codul F neschimbate (sha); V6 fișierele F neschimbate de randare (sha înainte =
după); V7 fără `__pycache__` în `xi/` sau `pages/`. **HR = PASS** dacă trec toate. Verificarea se reia după fiecare
decontare F (aceeași comandă; scrie un fișier nou cu marcaj), fără a modifica pagina.

## 6. Activarea

Streamlit citește `pages/` numai la pornire: pagina apare la repornirea H2 (după C1, după 14:05Z, 2026-11-01), odată
cu „Strategii”. Agentul NU repornește serviciul 8649 în această sesiune. La H2 se verifică ambele pagini în bara
laterală (`/Strategii` și `/Registru`); rezultatul intră în `xi/rezultate/H/H2_ACTIVARE.md`.

## 7. Ordinea și incidentele

1. Acest protocol + sigiliu. 2. Pagina + teste + verificator; calificare PASS; `SIGILIU_COD_HR.json`. 3. `verifica_hr.py`
pe registrul real ⇒ HR; `RAPORT_HR.md`. Orice defect după sigilare ⇒ incident + amendament sigilat înainte de corecție.
Nu se afirmă avantaj, profit sau noutate.
