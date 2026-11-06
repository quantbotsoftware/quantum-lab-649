# AMENDAMENT XI-P2-02 — Hatoslottó: defect de citire descoperit după producția de dezvoltare; anularea supraviețuitorilor

Scris ÎNAINTE de `SIGILIU_CONFIRMARE_P2.json` și înaintea oricărei citiri a rezervei. Rezultatele de dezvoltare
(`P2_DEV_REZULTATE.json` `36c46661…`, `p2_dev_pas.jsonl` `84100584…`, `RAPORT_P2_DEV_CIFRE.md` `2d50724b…`) rămân
publicate NESCHIMBATE. Incident: `xi/incidente/P2_02/`.

## 1. Constatarea

Producția unică pe dezvoltare (20:36:47Z) a dat 8 respingeri Holm: HU_hatos × {STAT, DRIFT, GAP, COMB} și
GLOBAL × {STAT, DRIFT, GAP, COMB}, cu E de ordinul 10¹⁰–10⁵⁰. O abatere atât de mare, concentrată într-un singur joc și
care se inversează în a doua jumătate (STAT: log E +145 pe prima jumătate, −76 pe a doua), este semnătura unei schimbări
de format, nu a unei urne. Diagnosticul de format (`xi/p2/diagnostic_campuri.py` ⇒
`DIAGNOSTIC_CAMPURI_HU.json`; numai numărul de câmpuri și tipul lor — întreg/text/gol — fără nicio valoare):

- `hatos.csv`: **794 de rânduri (1988 – mijlocul lui 2007) au 21 de câmpuri, cu 7 întregi la sfârșit** (6 numere +
  pótszám, numărul suplimentar al vechii categorii 5+1); 1 066 de rânduri (din 2007) au 20 de câmpuri, cu 6 întregi.
  Regula din B/amendamentul 01 („ultimele 6 câmpuri”) citește deci greșit toate rândurile vechi: un număr principal
  lipsește și pótszám-ul intră în mulțime. Toate cele 794 de rânduri sunt în partea de dezvoltare; rezerva
  (2020-11-15 … 2026-10-29) are numai rânduri cu 20 de câmpuri.
- `otos.csv`: toate cele 3 634 de rânduri au 16 câmpuri (5 numere la sfârșit) — citire corectă.
- Descompunerea log E pe perioade (din `p2_dev_pas.jsonl`, deja publicat; `LOGE_PE_PERIOADE_HU_hatos.txt`): perioada
  citită greșit (790 de extrageri cu cheie < 2007-07) STAT +155.4, DRIFT +127.9, GAP +34.4, COMB +154.0; perioada citită
  corect (698): STAT −85.5, DRIFT −10.7, GAP −10.9, FERMI 0.0, COMB −38.2. **Tot „câștigul” provine din artefact;
  pe datele citite corect fiecare predictor pierde.**
- Testele GLOBAL respinse sunt dominate de factorul HU_hatos: fără el, log E global = STAT −2.43, DRIFT −2.96,
  GAP −3.45, FERMI −1.56, COMB −2.82 (toate < 0).

## 2. Decizia (conservatoare; nicio salvare)

- **HU_hatos este EXCLUS din P2** pentru defect de citire: anexa B permite cel mult un amendament de citire per joc,
  iar el a fost folosit (XI-P2-01); nu se face o a doua corecție și **nu se rerulează** dezvoltarea.
- **Toți cei 8 supraviețuitori sunt anulați** (4 direct, 4 globali prin factorul invalid). Lista
  `supravietuitori` din `SIGILIU_CONFIRMARE_P2.json` este goală, iar rezerva tuturor jocurilor rămâne SIGILATĂ și
  NECITITĂ. Rularea pe rezervă nu se face: ar consuma testul orb pe un artefact cunoscut.
- Verdictul P2: **`P2_NICIUN_SUPRAVIETUITOR_VALID`** — pe jocurile citite corect (HU_otos, FR_loto, US_powerball) și pe
  produsul lor, niciun predictor nu bate uniformul (toate cele 15 E pe jocuri ≤ 0.84; global ≤ 0.21).
- Direcția deciziei: anularea poate numai să elimine un rezultat pozitiv, nu să creeze unul; nu există parametri sau
  praguri schimbate. Rezerva HU_hatos (372 de extrageri cu format corect) rămâne disponibilă, sigilată, pentru un
  protocol nou distinct (de exemplu Hatoslottó numai din 2007, citire pe 20 de câmpuri), care trebuie scris înainte.

## 3. Lecție de proces (pentru protocoalele viitoare)

Calificarea Q4 a verificat cititorul pe formatul *declarat*; nu putea vedea o schimbare de format în interiorul
fișierului real. De acum: **diagnosticul numărului de câmpuri pe an (fără valori) se face înaintea separării**, iar
un joc cu mai multe forme de rând fără regulă pentru fiecare formă este oprit înainte de analiză.
