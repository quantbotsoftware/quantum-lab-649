# PROTOCOL TU3-FIN — sesiunea S9 „FIN”: regresia completă, `RAPORT_TU3.md`, checkpoint final TU3 și planul TU4

Stare: scris și sigilat (`tu3/SIGILIU_TU3_FIN.json`) ÎNAINTE de orice alt fișier nou al sesiunii S9 și ÎNAINTE de
regresia completă. Singurele lucruri făcute înainte: citirea părții operative a `HANDOFF_QL649_20261027T194756Z.md`
(1–117), verificarea hash-urilor din `VERIFICARE_PREDARE_20261027T194756Z.json` (HANDOFF `7ed91a0d…`, PROMPT
`a4e66338…`, canonic `74641a9d…` — toate egale) și „Primul pas exact” read-only, cu ieșirea în
`/tmp/ql649_s9/primul_pas.log` (în afara depozitului): ciclurile LIVE `PUBLICAT` + dedup `erori 0`, dedup `OK`
(26 versiuni), `ss` = numai `127.0.0.1:8649` (streamlit pid 110053), toate hash-urile așteptate, `inlocuiri --verifica`
`ok: true`, `--stare` `S7_PASS` (real_started true/true), ambele `--verifica-doar --fara-d2` `VERIFICARE_SR_PASS`,
**32 passed**, **38 passed, 3 skipped**, **71 passed**, matricea „TOATE 3 MODURILE READY”, OK pe 21 (3 înlocuite,
5 înregistrări); DL `verifica_publicarea.py` exit 0 (`FAIL_HISTORICAL_DRIFT` + 6 moștenite). Citiri read-only de inventar: planul TU3, sigiliile, rezultatele `tu3/rezultate/*`, secțiunile
„Declarat/Abateri/Incident” din predările istorice TU3, `pl649/RAPORT_PL649.md` (1–30), `README.md` (titluri).

Autoritate: cererea din 2026-10-27T20:07Z („STRATEGIC DIRECTIVE OMEGA-vMAX … S9 (FIN)”, Mesajul 51), care deleagă
100% deciziile agentului („nu mă întreba nimic”), cere corectarea/înlocuirea propriului text cu idei originale, un plan
pe sesiuni cu prompt pentru fiecare chat nou și verificare continuă; `AGENTS.md`; planul TU3 (`c7b4bfd3…`) §4 S9.
`positive_claims_allowed=false`. Fără subagenți, git numai `./dev-git` fără add/commit.

## 1. Corecturile cererii (decizii ale agentului, motivate)

C1 — **Formalismul LQG / Wheeler–DeWitt / Kac–Moody / Green–Schwarz / Jones / Majorana NU se implementează.**
  (a) Sub ipoteza de lucru a proiectului (extrageri independente, uniforme), legea extragerii următoare condiționată de
  orice istoric este uniformă; orice funcție a istoricului — inclusiv o „rețea de spin” — are informație predictivă
  zero (inegalitatea procesării datelor). Nicio reformulare a aceleiași arhive nu schimbă acest fapt.
  (b) Clasa a fost deja testată preînregistrat pe acest depozit: PL649 „Singularitatea Planck” (rețea de spin +
  holonomii SU(3) + vid Higgs) = `PL_QUALIFIED 6/6` la calificare, dar backtestul unic `PL_NO_PROMOTION_EXPLORATORY 0/6`,
  p exact 0.948; QL649 0/6; S8 (MPS „Quantum Shadow”) `SR_FARA_DETECTIE` pe 5/40 și Joker. S7 a declarat deja că
  „Wheeler–DeWitt nu se aplică”. Repetarea ar fi o familie redenumită (interzisă de `AGENTS.md`).
  (c) Neconformități matematice ale textului: ecuația ĤΨ = 0 cere hamiltonianul de constrângere al gravitației, care nu
  există pentru o urnă — proiecția pe nucleul unui operator ales arbitrar este o alegere de model, nu „zero aproximări”;
  Joker = 5/45 × 1/20 este un produs de legi INDEPENDENTE (cuplaj zero), deci nu are „anomalie” de anulat (mecanismul
  Green–Schwarz privește anomalii gauge/gravitaționale ale corzilor în 10 dimensiuni); la nivelul critic k = −h∨
  construcția Sugawara este singulară (tensorul energie-impuls nu există), deci „CFT la nivel afin critic exact” nu e un
  CFT unitar; polinomul Jones este un invariant de noduri/legături (pe 3-varietăți generale: invarianții
  Witten–Reshetikhin–Turaev), nu al unei extrageri; braiding-ul anyonilor Ising (Majorana) nu este nici măcar universal
  pentru calcul cuantic și nu produce predicții.
C2 — **Hardware.** `torch.compile(mode="max-autotune-no-break")` nu există (moduri valide: `default`,
  `reduce-overhead`, `max-autotune`, `max-autotune-no-cudagraphs`); FMA complex „la nivel de registru” nu se forțează din
  Python; `numpy.memmap` pe SSD nu este „zero-copy CUDA” (trece prin page-cache și RAM-ul gazdei; GPUDirect Storage =
  cuFile/kvikio, neconfigurat); arhivele (≈ 2.6 mii extrageri × 3 jocuri, sub 1 MB) nu pot produce OOM — vârful VRAM S8
  a fost 2.35 GB din 8 GB. S9 nu rulează nicio sarcină GPU, deci nu există țintă termică de aplicat.
C3 — **Contradicție internă** („rescrie modulele backend” vs „engine.py, motor_n.py, motor_joker.py, parser*.py,
  validare.py, app.py, scor_real.py, verifica_sr.py înghețate”; planul S9 = „documente; fără cod nou”). Decizie: NU se
  creează `core/quantum_engine.py` / `MaxSingularityUnifiedEngine`: ar duplica motoarele sigilate fără conținut
  științific nou și ar încălca înghețarea.
C4 — **Portul 8649.** 5/40 și Joker sunt DEJA expuse în UI (modulul UI din 26 oct, porturile S4–S6, verdictele S8).
  Repornirea finală (permisă) este o dovadă de funcționare, nu o „activare”.
C5 — **Telemetria din cerere.** `PL_QUALIFIED 6/6` și „0/6” sunt confirmate de `pl649/RAPORT_PL649.md` (7–8).
  „Indice −0.32σ, p = 0.580, VRAM 11 MiB / 654 MiB” nu apar în artefactele inventariate, iar imaginea nu este
  disponibilă agentului ⇒ **NEVERIFICAT**; nu se folosesc nicăieri.
C6 — **`inlocuiri_tu3/v1/INLOCUIRE_FINAL_vMAX_20261027T211500Z.json`.** `inlocuiri_tu3/v1` este numele mecanismului,
  nu un director (înregistrările stau în `tu3/inlocuiri/`); 21:15:00Z ar fi o marcă din viitor (antedatare); o
  înregistrare de înlocuire fără fișier înlocuit ar falsifica lanțul. S9 NU modifică niciun fișier înghețat ⇒
  **nicio înregistrare de înlocuire**. `README.md` rămâne byte-identic (înghețat în `SIGILIU_TU3_SR`/`SR_R`; schimbarea
  ar cere modificarea W11 și o înlocuire); ghidul actualizat al produsului intră în `RAPORT_TU3.md` §„Ghid”. Abatere
  declarată față de planul TU3 („README actualizat”).
C7 — Antetul `predari/genereaza_predare.py` („nu pune întrebări”) rămâne neatins: Mesajul 51 îl confirmă.

## 2. Regresia completă (decizia S9: toate suitele, nimic sărit pentru „greutate”)

Toate cu `.venv/bin/python -B -m pytest -q -p no:cacheprovider`, din `next_candidate/quantum_lab_649`, ieșirea
capturată în `tu3/rezultate/FIN/` (0444 după scriere).
- R1 = primul pas (deja rulat, §0): 32 / 38+3s / 71 / matrice READY. Se REPETĂ în regresie (aceleași comenzi).
- R2 = `tests/test_engine.py tests/test_parser.py tests/test_validare.py` (6/49 de bază; la VS: 32 passed).
- R3 = `tu3/tests/` (la DD: 53 passed + ulterioare).
- R4 = pistele închise `bo649 cs649 gl649 pl649 se649 wu649` (`*/tests/`), NUMAI read-only: manifest sha256 al celor
  6 directoare înainte și după; orice diferență ⇒ R4 FAIL (se declară, nu se repară).
- R5 = `tu3/verifica_sr.py --joc 540 --verifica-doar` și `--joc joker --verifica-doar` (CU D2/V7, ≈ 40 s pe joc).
- R6 = `tu3/inlocuiri_tu3.py --verifica` (`ok: true`), `tu3/matrice_init.py --out-dir /tmp/ql649_matrice_fin`
  (READY), `tu3/scor_real.py --stare` (`S7_PASS`), DL `verifica_publicarea.py` (exit 0).
- R7 = integritatea: toate cheile `frozen_hashes` din acest sigiliu (calculate la sigilare: cele 283 din
  `SIGILIU_TU3_SR_R` + `replaceable` S8 la sha-urile curente + fișierele noi S8 existente) byte-identice la final.
Criteriu: fiecare suită 0 eșecuri (skip-urile se raportează; numărul de teste se raportează, nu se impune) și R4–R7
PASS ⇒ **`FIN_PASS`**; altfel **`FIN_FAIL`**, publicat ca atare, fără reparare în S9 (se declară; o remediere ar cere
o sesiune proprie). Scriptul de colectare `tu3/rezultate/FIN/regresie_fin.py` (numai stdlib; rulează comenzile de mai
sus, numără `passed/failed/skipped/error`, scrie `REGRESIE_FIN_<UTC>Z.json` 0444) — instrument de rezultat ca
`rezultate/L649/acceptare_l649.py`, nu cod de produs.

## 3. Fișiere permise în S9 (lista închisă)

Noi: `tu3/PROTOCOL_TU3_FIN.md`, `tu3/SIGILIU_TU3_FIN.json` (ambele 0444), `tu3/rezultate/FIN/regresie_fin.py`,
`tu3/rezultate/FIN/REGRESIE_FIN_<UTC>Z.json` + jurnalele `*.log` ale suitelor (0444), `tu3/RAPORT_TU3.md` (0444),
`tu4/PLAN_SESIUNI_TU4_20261027.md` (0444; document de planificare, NU protocol, NU cod). Actualizate:
`predari/OPERATIV.md`, `predari/MESAJE_UTILIZATOR_QL649.md` (numai adăugare la final: Mesajul 51 integral); perechea
nouă `predari/HANDOFF/PROMPT/VERIFICARE_*` prin `predari/genereaza_predare.py` (neschimbat), cu arhivarea celei vechi.
Efecte laterale cunoscute (permise, declarate): `jurnal/MATRICE_INIT_*`, `jurnal/lansator_tu3_<UTC>Z.log`,
`jurnal/matrice_<UTC>Z.txt`, `jurnal/app_*.log`, `jurnal/app.pgid`, `tu3/__pycache__`, `tu3/date/derivat/*.jsonl`,
`tu3/date/live/*` (timerul). Orice alt fișier nou/schimbat ⇒ declarat ca incident.

## 4. `RAPORT_TU3.md` — conținut obligatoriu

Sinteza S0 (modulele P1/J/P/E40/EJ/UI/VS/DD din 26 oct) și S1–S8; tabelul verdictelor cu sursele (fișier + sha);
porturile 7–12 DESCRIPTIVE (identitate pe 6/49); scorul real S8 cu cifrele publicate și verdictele D1/D2/promovare;
TOATE incidentele/abaterile declarate (VS-01, primele rulări dinaintea înregistrărilor, repornirile ratate, termic
72 °C în S7, probele de inginerie S7 etc.); regresia S9; ghidul de utilizare (pictogramă, moduri, surse LIVE/înghețat,
ce NU afirmă aplicația); limitele (arhivă explorată, calcul clasic, „cuantic” = inspirație matematică, fără avantaj
demonstrat, fără atestare externă, linger dezactivat, gardul D1 neatins).

## 5. Planul TU4 (cerința „idei originale + plan pe sesiuni + prompt pe sesiune”)

Document separat, scris DUPĂ regresie: un program nou, onest matematic, în care „cuanticul” este folosit acolo unde
este matematic exact și util (statistici fermionice/determinantale, scheme de asociere, martingale de testare), fără
pretenții predictive. Fiecare sesiune TU4 va avea protocol propriu sigilat înainte de cod. Planul nu aprobă niciun cod
în S9.

## 6. Final

`FIN_PASS` ⇒ repornirea serverului 8649 cu `systemd-run --user --scope --collect -q gtk-launch quantum-lab-649` + bucla
care așteaptă `[lansator] health ok` (sau `EROARE`) în jurnalul NOU, apoi `OPERATIV.md`, supliment, `genereaza_predare.py`.
Fără rulări reale, fără tuning, fără modificarea vreunui verdict publicat.
