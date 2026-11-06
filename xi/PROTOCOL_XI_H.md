# PROTOCOL XI-H — ecranul „Strategii” (planul V11, faza H, cu rezultatele V12 P1 + P2)

Scris și sigilat (`xi/SIGILIU_XI_H.json`) ÎNAINTE de orice cod H, de orice fișier de date H și de orice modificare a
aplicației. Autoritate: Mesajele 107/108 (autonomie, aplicație funcțională, predare la fiecare sesiune), 117–122
(obiectivul predicției, tratat cinstit prin V12) și cererea din 2026-10-31 (Mesajul 125 al suplimentului: „faza H
(ecranul «Strategii» cu verdictele P1+P2, rezoluția și C1/C3, fără «predicții»)”). Planuri: `xi/PLAN_V11_QL_XI.md`
(`2fb304f4…`, §5 faza H), `xi/PLAN_V12_PREDICTIE.md` (`a675289e…`, F/H după P1/P2). `positive_claims_allowed=false`.
Calcul clasic. Faza H NU calculează nicio statistică nouă: afișează rezultate deja publicate și verificate.

## 0. Ce este și ce nu este

- **Este:** un ecran de citire care arată, cu proveniență sha256, (1) verdictul băncii de predictoare pe jocurile RO
  (P1) și pe arhivele străine (P2), (2) rezoluția (ce abateri ar fi fost văzute), (3) starea rezervelor oarbe,
  (4) designurile garantate C1 (cost, premiu minim, fracția returnată, probabilitatea de a fi pe plus), (5) frontiera
  portofoliului C3 sub buget (valoare ↔ regularitate, ρ).
- **Nu este:** o predicție, o recomandare de numere sau de bilete, o promisiune de câștig. Ecranul nu afișează NICIUN
  bilet și nicio listă de numere (nici biletele „următoare” din P1, nici biletele C3, nici designurile C1).
- Aritmetica derivată permisă (fixată aici, fără alți parametri): produsul e-valorilor pe jocurile valide P2
  (E_★,X = ∏_g E_g,X, deja definit în XI-P2 §1), ρ = EV / (K · preț) cu prețurile C3 {6/49: 8, 5/40: 5, Joker: 7} lei,
  ρ pentru biletele aleatoare = ev_mean / (K · preț), fracția returnată C1 = `return_mean` (din sursă), min/max ρ.

## 1. Inventarul și alegerea aplicației (făcut înainte de acest protocol, numai citire)

- Observatorul Tauri din V11 §5 nu există în depozit (există numai nucleul Rust `rust_core`, fără interfață).
  „Fereastra Quantum Limit” este un produs separat (`next_candidate/quantum_limit/`), cu `prospectiv.py` înghețat și cu
  `.pyc`-uri restaurate care strică DL v2 la orice import fără `-B`; orice modificare acolo ar risca DL v2 și C1.
- Aleasă: **aplicația Streamlit QL649 (serviciul utilizatorului `ql649-tu3-8649.service`, port 8649)**, ca pagină
  separată în mecanismul multi-pagină Streamlit („MPA v1”: directorul `pages/` lângă `app.py`):
  `pages/1_Strategii.py`. `app.py`, `tu3/ui_tu3.py`, motorul și testele existente NU se modifică (sha `app.py`
  `7c5da1e6…` verificat la final). Pagina nu importă `torch`, `engine`, `quantum_limit` sau alt modul al proiectului;
  citește numai `xi/rezultate/H/STRATEGII_DATE.json`.
- Streamlit 1.66.1 decide folosirea directorului `pages/` o singură dată, la pornirea serverului
  (`PagesManager.uses_pages_directory`). Prin urmare serverul care rulează acum NU se schimbă; pagina devine vizibilă
  la următoarea pornire a serviciului. **Agentul NU repornește serviciul 8649 înainte de încheierea C1
  (2026-11-01 13:46Z)**; activarea (H2) se face într-o sesiune ulterioară C1, prin repornirea oficială
  (`systemctl --user restart ql649-tu3-8649.service`, lansatorul `porneste_aplicatia_tu3.sh`), cu verificarea
  `/_stcore/health` și a jurnalului lansatorului („TOATE 3 MODURILE READY”).

## 2. Sursele (sha256 fixate; constructorul refuză orice diferență)

| Sursă | sha256 |
|---|---|
| `xi/rezultate/P1/P1_REZULTATE.json` | `ea62e6eda55e49859bc2c2d692e2c223717eee9d330d5b20ef8b0451b69898fa` |
| `xi/rezultate/P1/VERIFICARE_P1.json` | `2298bc090f72170424611b28e9e43efeab1ab4aa3b29014d5446e0771455da1b` |
| `xi/rezultate/P1/calificare/CALIFICARE_P1_20261031T192422Z.json` | `a93293a359d18c7175c5b4980288a0b13d0837fdabf55d8856f6e5a3005e2931` |
| `xi/rezultate/P2/P2_DEV_REZULTATE.json` | `36c46661076978759587733f3ea7e33f9fba0e6524b4d29c65f1b5fc1df3e866` |
| `xi/rezultate/P2/VERIFICARE_P2_DEV.json` | `639dcb71db3ac5d3bf5feb8812bcd74f84642dde460f55eef3645ff6012bf12e` |
| `xi/p2/SIGILIU_CONFIRMARE_P2.json` | `82f860828200f77a562d7c4a49a9ef8f011ac29e8338a4b6b9de712c6255a4c4` |
| `xi/rezultate/P2/calificare/CALIFICARE_P2_20261031T202258Z.json` | `6ab2f3a39b2b4dbb309760578a07ee5469eb5bd9cd375378cf5420c46996d058` |
| `xi/date_p2/HU_otos/SEPARARE.json` | `72637fe56186f9942b61aab52cb244f9976e0139206002916610043bd4b5d5df` |
| `xi/date_p2/FR_loto/SEPARARE.json` | `7ec33bc440d2c2503896cc5a54c3d4498b0940eca94be5b46c8803702e09944e` |
| `xi/date_p2/US_powerball/SEPARARE.json` | `901cd54c470ab343999ef45f5153aa0c4a1f5fe106ff192542e589ba84de3248` |
| `xi/date_p2/HU_hatos/SEPARARE.json` | `7ee3918d216ec4b5d941842a9dc8421171670d1d4d50dc00dd653eb2b637a097` |
| `xi/rezultate/C1/C1_EVALUARE.json` | `5eb6440188d16788e7e7410c44a21512f5830f324324822672eabc5d6803b2e8` |
| `xi/rezultate/C3/C3_REZULTATE.json` | `01331654bb23b56295e5c23c2b0cf8a72f2ec84f755df2fcefbfcede23c9f9ca` |
| `xi/rezultate/C3/comparatori.jsonl` | `04c877159694cd9f1d99b903d08465c895d311bb1f90c027dbee81a2c776f652` |

- **Rezervele oarbe** `xi/date_p2/*/rezerva.json` și directoarele `sigilat/` NU se deschid și NU se hash-uiesc (hash =
  citire de octeți). Pentru ele se folosește numai `os.stat` (mod 0400, mărime) și sha-ul deja publicat în
  `SEPARARE.json` (`rezerva_sha256`).
- Câmpurile `tickets`, `bilet_urmatoarea_extragere` și orice listă de numere din surse NU se copiază în datele H.

## 3. Conținutul ecranului (secțiuni fixe, în această ordine)

- **S0 Antet:** titlul „Strategii — ce spun datele”, amprenta `STRATEGII_DATE.json` (sha) și a protocolului, textul
  fix: „Acest ecran nu face și nu afișează predicții de numere. Dacă extragerile sunt corecte, nicio metodă nu crește
  șansa unui bilet. positive_claims_allowed=false.”
- **S1 Jocurile RO (P1):** pentru 6/49, 5/40, Joker: T, prima/ultima dată, E pentru STAT/DRIFT/GAP/FERMI/COMB (3
  zecimale), respins Holm (da/nu), verdictul `P1_NICIUN_CANDIDAT`, verificarea `PASS n/n`; mesajul per joc „nicio
  abatere detectabilă de la uniform”.
- **S2 Arhive străine (P2):** jocurile valide din `SIGILIU_CONFIRMARE_P2.json` (`jocuri_valide`): T_dev, perioada, E
  pe predictori; rândul „global (produs pe jocurile valide)” recalculat; jocurile excluse cu motivul; verdictul
  `verdict_P2`, verificarea `PASS n/n`, mențiunea că producția brută (`verdict_dezvoltare`) a fost anulată de
  `AMENDAMENT_XI_P2_02` (Hatoslottó, defect de citire).
- **S3 Rezoluția:** P1 (lungimea 6/49): fracția istoriilor sintetice cu E ≥ 1500 la δ ∈ {3, 5, 10, 15}% (STAT) și δ
  minim cu putere ≥ 0.8; P2: aceeași fracție la δ ∈ {5, 10, 20}% pentru jocurile valide (STAT). Textul: „se exclud
  abateri ale bilelor de ordinul 10–20%; abaterile de câteva procente rămân nedetectabile pe arhive de această lungime”.
- **S4 Rezervele oarbe:** pentru HU_otos, FR_loto, US_powerball, HU_hatos: R, perioada rezervei (din SEPARARE), sha
  publicat (12 caractere), mod 0400 (stat), starea „SIGILATĂ, NECITITĂ”.
- **S5 C1 — designuri garantate:** pentru fiecare design din `C1_EVALUARE.json`: nume, număr de bilete, cost pe
  extragere, extrageri fără premiu (E1), premiul minim pe extragere, cuantilele 5/50/95% ale premiului; pentru
  strategiile D_joker / D_649 / D_ambele: miza pe extragere, fracția returnată și P(net ≥ 0) la 1, 5, 10 ani. Textul:
  „garanția combinatorie dă un premiu la fiecare extragere, dar returnează ~36–37% din miză: regularitate, nu profit”.
- **S6 C3 — portofoliul sub buget:** varianta P, pentru fiecare joc × buget {40, 100, 500} × μ ∈ {0, 1000}: K, EV, ρ,
  P_any; comparatorul „bilete aleatoare” (ρ_rnd, P_any_rnd medie); min/max ρ pe toate cele 81 de instanțe, numărul
  instanțelor cu ρ ≥ 1, poarta G4 (n/n). Textul: „ρ < 1 peste tot: niciun portofoliu nu recuperează miza”.
- **S7 Ce înseamnă (text fix):** rezumatul de mai sus, sursele (căile rapoartelor), limitele (arhive explorate,
  rezervă sigilată pentru o ipoteză distinctă viitoare, rezultat negativ ≠ imposibilitate universală).

## 4. Arhitectura

1. `xi/h/construieste_strategii.py` (constructor): verifică sha-urile §2, extrage numai câmpurile §3, calculează
   aritmetica §0, scrie `xi/rezultate/H/STRATEGII_DATE.json` (0444) și `xi/rezultate/H/SIGILIU_DATE_H.json` (sha-ul
   datelor, sha-ul constructorului, sha-urile surselor; 0444). Refuză să suprascrie un fișier existent fără `--forteaza`
   (folosit numai dacă un incident consemnat o cere).
2. `pages/1_Strategii.py` (pagina): citește JSON-ul, recalculează sha-ul și îl compară cu `SIGILIU_DATE_H.json`; la
   nepotrivire afișează numai o eroare (fără tabele). Nu face alte calcule decât formatarea. `sys.dont_write_bytecode`.
3. `xi/h/verifica_h.py` (verificator independent; NU importă constructorul sau pagina).
4. Toate rulările: `/usr/bin/python3 -B` sau `.venv/bin/python -B` cu `PYTHONDONTWRITEBYTECODE=1`; niciun
   `__pycache__` nou în `xi/` sau `pages/`.

## 5. Verificarea (poarta G6 a fazei H; înlocuiește „paritatea Rust” a V11, care viza Observatorul Tauri inexistent)

`verifica_h.py` scrie `xi/rezultate/H/VERIFICARE_H_<UTC>.json` cu verificările:

- V1 sha-urile §2 egale; sha-ul datelor egal cu sigiliul datelor; modurile 0444.
- V2 **paritate independentă:** fiecare valoare numerică din `STRATEGII_DATE.json` recalculată din surse (cod scris
  separat): egalitate exactă pentru întregi/șiruri, |Δ| ≤ 1e-12 · max(1, |x|) pentru reale; nicio valoare în plus sau
  lipsă față de lista §3.
- V3 **fără bilete:** nicio cheie `tickets`/`bilet*`/`numere` în date; nicio listă de ≥ 5 întregi în datele H.
- V4 **randare (AppTest Streamlit, fără server, fără port):** pagina rulează fără excepție; titlurile S0–S7 prezente;
  pentru fiecare joc și predictor, E formatat cu 3 zecimale apare în tabelele randate; verdictele `P1_NICIUN_CANDIDAT`
  și `P2_NICIUN_SUPRAVIETUITOR_VALID` apar.
- V5 **fără „predicții”:** în tot textul randat (markdown, tabele, titluri), rădăcina „predic” apare NUMAI în frazele
  fixe de negație din §3 S0 / S7 (listă albă exactă în verificator); cuvintele „recomand”, „garantat profit”,
  „câștig sigur” nu apar.
- V6 **integritate:** cu date alterate (copie temporară cu un octet schimbat), pagina afișează eroarea și niciun tabel.
- V7 **MPA:** într-un director temporar cu un script principal minimal și o copie a paginii în `pages/`, AppTest
  descoperă pagina „Strategii” și o randează (mecanismul care va fi folosit la repornire).
- V8 **neatins:** sha-ul `app.py` = `7c5da1e6…`; niciun `__pycache__` nou în `xi/` sau `pages/`; nimic din
  `quantum_limit` importat (verificat prin `sys.modules` în procesul AppTest).

Poarta **H1 = PASS** dacă V1–V8 trec toate. **H2** (activarea la repornire, după C1) se evaluează separat: health ok în
150 s, jurnalul lansatorului cu „TOATE 3 MODURILE READY”, `DL_RC_V2=0` după repornire.

## 6. Ordinea

1. Acest protocol + sigiliul (înainte de orice cod H).
2. Constructorul, pagina, verificatorul (cod), apoi sigiliul codului `xi/h/SIGILIU_COD_H.json`.
3. O singură construire a datelor; verificarea; raportul `xi/rezultate/H/RAPORT_H.md`.
4. Orice defect găsit după sigilarea codului ⇒ incident + amendament sigilat înainte de corecție; datele se reconstruiesc
   numai cu `--forteaza`, iar fișierele vechi se păstrează în `xi/incidente/H_NN/`.

## 7. Interpretare (fixată)

Ecranul face vizibil, în aplicația zilnică, adevărul cuantificat: pe 6 urne independente niciun predictor al băncii nu
bate uniformul; designurile garantate cumpără regularitate cu ~63% din miză; portofoliile sub buget au ρ < 1. Nu
demonstrează imposibilitatea universală a oricărei metode. Nu se afirmă avantaj, profit sau noutate mondială.
