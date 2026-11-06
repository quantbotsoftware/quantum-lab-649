# PROTOCOL TU3-SR-R — sesiunea S8: rularea reală UNICĂ 5/40 + Joker, verificarea separată și verdictele în taburile 4–5

Stare: scris și sigilat (`tu3/SIGILIU_TU3_SR_R.json`) ÎNAINTE de orice cod al acestei sesiuni și ÎNAINTE de orice rulare
reală (`code_files_present: []`, `results_present: false`; `tu3/rezultate/SR/540/` și `tu3/rezultate/SR/joker/` absente).
Surse de autoritate: `PROTOCOL_TU3_SR.md` (`7f38a94b…`) §4 și `AMENDAMENT_TU3_SR_01.md` (`3c16f2e0…`), NESCHIMBATE;
`PUTERE_SR.json` (`d6095173…`, `S7_PASS`, ambele jocuri `SR_P_PASS`); cererea S8 din 2026-10-27 (Mesajul 49) și
răspunsul utilizatorului la întrebarea de inventar (2026-10-27 18:35Z): `tests/test_scor_real.py` intră în lista
`replaceable` (W11, numai cele două schimbări de la §4.3). Calcul CLASIC (PyTorch pe GPU-ul RTX 5060 Laptop, NumPy pe CPU).
`positive_claims_allowed=false`.

Acest protocol NU schimbă nimic din scorul real: ținte, metrici, comparatori, praguri, α, semințe, M, verdictele D1/D2/
promovare și sursa (arhiva ÎNGHEȚATĂ) rămân cele din `PROTOCOL_TU3_SR.md` §2 și §4 + A2. El fixează numai: inventarul UI,
verificatorul separat, afișarea în taburile 4–5, înlocuirea sigilată, ordinea și politica de incidente ale S8.

## 1. Inventar read-only (făcut înainte de acest protocol)

### 1.1 Taburile 4–5 în modurile 5/40 și Joker (`tu3/ui_tu3.py` `9920b9dd…`, funcția `render`)
- **Tab 4 „🌌 Multiversul Nul”** (liniile 478–520): `load_json(M.POWER_FILE | MJ.POWER_FILE)` = puterea SINTETICĂ
  E40/EJ (verdict, porțile G1/G2 și GJ1/GJ2, tabelul și graficul ratelor pe seturi); caseta `st.info` de la liniile
  506–507 „SCI (indicele de coerență structurală) pe istoria reală …: NERULAT — `validare.py` este definit pe 6/49 …”;
  frecvențele reale LIVE față de rN/n și, la Joker, frecvențele Joker față de N/20 (descriptiv).
- **Tab 5 „⏳ Mașina Timpului”** (liniile 522–530): caseta `st.info` de la liniile 525–526 „Backtestul cauzal pe istoria
  reală … este NERULAT …” și inventarul setului LIVE (`ds.summary()`, tabel).

### 1.2 Testele care citesc sau constrâng azi aceste taburi
- Niciun test nu citește conținutul taburilor 4–5 în 5/40/Joker (`at.tabs[3]`/`at.tabs[4]` nu apar nicăieri).
- `tests/test_app_tu3.py` (`c9a7f98d…`) U3/U4: 12 taburi, 3 variante, `sum("NEAPLICABIL" in i.value for i in at.info) == 0`
  pe TOATĂ aplicația ⇒ textele noi NU conțin „NEAPLICABIL”.
- „Numai inserții” față de copiile de referință ale `ui_tu3.py`: `test_l649.py` L3 (`ui_tu3_pre_l649.py`),
  `test_porturi_712.py` P9 (`ui_tu3_pre_t7a.py`), `test_porturi_t7b.py` B7 (`ui_tu3_pre_t7b.py`), `test_porturi_t7c.py`
  C7 (`ui_tu3_pre_t7c.py`) ⇒ S8 modifică `ui_tu3.py` NUMAI prin inserții (nicio linie existentă ștearsă sau schimbată).
- `test_porturi_712.py` P8: cuvintele interzise („promovat”, „hits”, …) se caută NUMAI în taburile 7–12 ⇒ nu privesc S8.
- `tests/test_scor_real.py` (`bc45e402…`) W11: (i) toate `frozen_hashes` din `SIGILIU_TU3_SR.json` byte-identice — printre
  ele `tu3/ui_tu3.py` și `tests/test_app_tu3.py`; (ii) linia 450: nicio `tu3/inlocuiri/INLOCUIRE_SR_*.json`. Ambele ar
  pica la afișarea verdictului ⇒ decizia utilizatorului: `tests/test_scor_real.py` intră în `replaceable` (§4.3).
- `inlocuiri_tu3.verify_all` și `matrice_init` rezolvă lanțurile prin toate înregistrările valide (fără filtru pe sigiliu):
  lanțul `ui_tu3.py` … → `9920b9dd…` (T7C) → sha-ul nou (SR) rămâne rezolvabil; testele C8/B8/P10/L10 cer `chain[0]` =
  înregistrarea proprie și `rep["ok"]` ⇒ neafectate de o înregistrare nouă `INLOCUIRE_SR_*`.

### 1.3 Calea reală din `tu3/scor_real.py` (`969b6239…`, NESCHIMBAT în S8)
- `real_gate` (S8, START absent, `SR_P_PASS`), `check_seals`, plafonul VRAM `set_per_process_memory_fraction(6.2e9/total)`,
  `PM.build_game_dataset(game, "frozen")` + aserțiunea sha înghețat, START.json (0444), `wf_predict` cu semințele
  `step_seed` (`M.score_steps`, sub-loturi 16; O6 loturi 64; garda termică A2), `PREDICTII.npz` + `PREDICTII_SIGILIU.json`
  (0444) ÎNAINTE de scor, scorul din fișierul scris, D1, D2 (nul MPS M = 8192, semințele 5401101 / 4521101, structura reală
  de pași), promovarea, `REZULTATE.json` (0444).
- Declarat (constatat la inventar, NU se repară — codul a rulat neschimbat în S7 și nu se atinge între S7 și S8): garda
  termică se oprește după mersul înainte; faza D2 (≈ 40 s în S7) rulează fără pauze termice. De aceea S8 adaugă un
  monitor EXTERN, numai de citire (§5.3). Calea `seeds = None` (`M.score_steps`) nu are martor în `test_scor_real.py`
  (W8 folosește semințe explicite) ⇒ testul T3 (§3.4) o execută cap-coadă pe o arhivă SINTETICĂ înainte de rularea reală.

## 2. Rularea reală UNICĂ (neschimbată: `PROTOCOL_TU3_SR.md` §4 + A2)

2.1 Comenzile, în această ordine, fiecare O SINGURĂ DATĂ, pornite ca sarcină de fundal a uneltei (fără `&`), cu `python -u`:
    `.venv/bin/python -u -B tu3/scor_real.py --real 540 --sesiune S8 2>&1 | tee tu3/rezultate/SR/real_540_<UTC>Z.log`,
    apoi, după terminarea primei, același lucru cu `--real joker` (`real_joker_<UTC>Z.log`). Jurnalele devin 0444.
2.2 Fără tuning, fără repetare: nicio schimbare de cod, config, sămânță sau parametru după START.json; a doua invocare
    este refuzată de `real_gate`. Verdictele se publică INDIFERENT de rezultat.
2.3 Resurse: plafonul VRAM 6.2·10⁹ B (în cod); garda termică A2 în mersul înainte (în cod); T_max din gardă + T_max al
    monitorului extern se DECLARĂ; `temperature_target_met` (T_max < 71 °C) se raportează, nu invalidează matematica.

## 3. Verificatorul SEPARAT `tu3/verifica_sr.py`

3.1 **Independență.** Importuri ⊆ biblioteca standard ∪ {numpy}. NU importă `scor_real`, `torch`, `motor_n`, `motor_joker`,
    `engine`, `parser`, `parser_multi`, `validare` sau vreo pistă închisă. Re-implementează din specificația `PROTOCOL_TU3_SR`
    §2: citirea arhivei înghețate (JSONL, validarea/deduplicarea/ordonarea (dată, cheie) și pașii pe dată ca
    `parser_multi`), legea marginală, scorurile, comparatorii, porțile, legea nulă exactă, D1, promovarea, statisticile SCI.
3.2 **Verificări pe joc** (toate trebuie să treacă pentru `VERIFICARE_SR_PASS`; altfel `VERIFICARE_SR_FAIL`):
    - **V1 integritatea**: START/PREDICTII.npz/PREDICTII_SIGILIU/REZULTATE prezente și 0444; sha(PREDICTII.npz) =
      `PREDICTII_SIGILIU.sha256` = `REZULTATE.predictions_sha256`; `PREDICTII_SIGILIU.written_at_utc` ≤
      `REZULTATE.finished_at_utc`; `START.started_at_utc` > `sealed_utc` al acestui sigiliu; sha-urile protocolului,
      sigiliului și amendamentului SR din START = fișierele curente; `START.positive_claims_allowed` = false.
    - **V2 arhiva**: sha(JSONL înghețat) = `START.source_sha256` = sha-ul sigilat (5/40 `e1591b87…`, Joker `45713aa2…`);
      reconstrucția independentă dă `n_draws`/`n_steps` din START (2490/2427; 2202/2139); `config_digest` începe cu
      `b364fc0cfb6c` (5/40) / `61c9445bce19` (Joker) (§1.1 din `PROTOCOL_TU3_SR`).
    - **V3 predicțiile**: `ks` = 100..S−1; variantele [S, 3, k] întregi distincți în 1..n; π_QL ≥ 0 cu Σ = 1 (±1e-6);
      Joker: `jokers` în 1..20, π_J ≥ 0 cu Σ = 1 (±1e-6).
    - **V4 comparatorii recalculați din arhivă**: π_B ∝ c + 1 (pașii < k), π_R ∝ ew + 0.5 (ew după §2.5, timp de
      înjumătățire 26); Joker: aceleași pe bilă. Abatere față de PREDICTII.npz ≤ 1e-12 (absolut).
    - **V5 scorul recalculat** pe componente: ținte, hits QL/B/R, log/Brier QL/B/R/U, jumătăți, exces, cele 6 porți cu τ,
      distribuția potrivirilor, reuniunea celor 3 variante, biletele schimbate față de B, p exact (convoluția hipergeometrică
      float64). Egalitate: întregi exact; reali ≤ 1e-9 relativ (sau ≤ 1e-9 absolut lângă 0); `per_target` identic.
    - **V6 verdictele**: D1 (5/40 p ≤ 0.01; Joker min(p) ≤ 0.005) și promovarea (6/6 porți pe toate componentele)
      recalculate = cele din REZULTATE.
    - **V7 D2 recalculat INDEPENDENT**: statisticile reale (χ²_frecv, χ²_perechi, goluri, suprapunere; Joker + bilă + χ²_cross)
      recalculate în NumPy pe structura reală de pași; referința nulă proprie M = 8192 cu legea nulă EXACTĂ (submulțimi
      uniforme de r numere; bila uniformă și independentă — aceeași lege ca nulul MPS, martorul W2), generator NumPy PCG64,
      semințele 5408101 (5/40) / 4528101 (Joker). Criterii (fixate acum): pentru fiecare statistică
      |z_np − z_SR| ≤ 0.10 + 0.03·|z_SR|; |SCI_np − SCI_SR| ≤ 0.10 + 0.03·|SCI_SR|; |p_np − p_SR| ≤
      4·√(p̄(1 − p̄)/M) + 3/M (p̄ = media celor două); verdictul D2 coincide SAU p_SR se află în banda α ± (aceeași
      toleranță) — caz raportat `D2_IN_BANDA_MC` (nu FAIL). `M_null` = 8192 și sămânța = 5401101 / 4521101 în REZULTATE.
      Verdictul D2 oficial rămâne cel din `scor_real.py` (protocolul); verificatorul confirmă sau infirmă coerența.
    - **V8 resursele (declarativ, nu intră în verdict)**: `peak_reserved_bytes` < 6.2·10⁹, T_max (gardă), pauzele,
      `temperature_target_met`; T_max din monitorul extern dacă jurnalul e dat cu `--termic`.
3.3 **Ieșiri.** `tu3/rezultate/SR/<joc>/VERIFICARE_SR.json` (0444; refuză suprascrierea) cu verdictul, verificările,
    sha-urile REZULTATE/PREDICTII/verificatorului și numerele D2 independente. `--verifica-doar` = aceleași calcule, fără
    scriere (pentru verificările read-only ulterioare); `--fara-d2` sare peste V7 numai în modul read-only. `--pre-rulare`
    scrie O DATĂ `tu3/rezultate/SR/PRE_RULARE_S8.json` (0444; sha-urile codului S8, ale înregistrării de înlocuire și ale
    sigiliilor; refuză dacă există vreun START.json) — dovada că tot codul S8 a fost înghețat ÎNAINTE de rulare.
3.4 **Teste noi** `tests/test_verifica_sr.py`: T1 importurile (§3.1); T2 identitatea verificator ↔ `scor_real` pe un set
    SINTETIC cu pași dubli (predicții din `SR.wf_predict` cu config FAST, numai în test; scorul, D1, promovarea exact; D2
    în toleranțele V7 cu M redus); T3 calea reală cap-coadă pe o arhivă SINTETICĂ scrisă în director temporar (`run_real`
    cu `build_game_dataset` redirecționat spre fișierul sintetic, config FAST, director de ieșire temporar, PUTERE temporar
    cu `SR_P_PASS`) pentru 5/40 și Joker, urmată de verificator ⇒ PASS și de refuzul unei a doua rulări; T4 falsificări
    (hits modificat, sha PREDICTII schimbat) ⇒ FAIL; T5 (după rulare) fișierele reale `VERIFICARE_SR.json` 0444 și coerente
    cu REZULTATE (skip dacă lipsesc). T2–T4 NU citesc arhivele reale (garda `forbid_real_archive` activă în T2/T3, în afara
    fișierului sintetic dat explicit).

## 4. Afișarea în taburile 4–5 și înlocuirea sigilată (`inlocuiri_tu3/v1`)

4.1 **`tu3/ui_tu3.py` — NUMAI inserții.** Casetele „NERULAT” (liniile 506–507 și 525–526) rămân în cod, dar se scriu
    într-un `st.empty()` deschis înaintea lor (inserție) și închis după ele (inserție). Când există rezultate reale, caseta
    se ÎNLOCUIEȘTE pe loc cu blocul de verdict (tab 4: D2; tab 5: D1 + promovare). Fără START.json pentru jocul respectiv,
    caseta „NERULAT” rămâne neschimbată. Stările afișate:
    - START prezent, REZULTATE absent ⇒ `st.error` „rulare pornită fără rezultate (incident)”;
    - REZULTATE prezent, verificarea absentă sau cu sha diferit ⇒ verdictele + `st.warning` „verificare separată absentă/
      nepotrivită”;
    - `VERIFICARE_SR_FAIL` ⇒ verdictele + `st.error` cu verificările picate;
    - `VERIFICARE_SR_PASS` (sha REZULTATE și PREDICTII potrivite) ⇒ verdictele + linia „verificat separat”.
    Tab 4 (D2): verdictul, SCI, p empiric, M, K, tabelul z pe statistici, D2 independent (verificator). Tab 5 (D1 +
    promovare): verdictul D1, p exacte și α, verdictul de promovare, tabelul pe componente (ținte, hits QL/B/R, E_U·T, exces,
    log QL−U/QL−B, Brier, porți trecute), porțile 1–6 pe componente, un grafic descriptiv pe componentă (hits cumulate QL/B/R
    minus E_U·t), resursele (T_max, VRAM). Fiecare bloc spune explicit: arhivă deja explorată, o detecție NU este avantaj
    predictiv, confirmarea ar cere date prospective separate, `positive_claims_allowed=false`. Directorul rezultatelor se
    poate redirecționa NUMAI în teste cu variabila `QL649_SR_DIR`.
4.2 **`tests/test_app_tu3.py` — numai inserții**: U10 (5/40 și Joker, rezultate de test în `QL649_SR_DIR` temporar):
    tab 4 conține verdictul D2 și NU caseta „SCI … NERULAT”; tab 5 conține D1 + promovarea și NU „Backtestul cauzal …
    NERULAT”; „positive_claims_allowed=false”; fără REZULTATE ⇒ casetele „NERULAT” rămân; sha nepotrivit ⇒ avertisment;
    `NEAPLICABIL` = 0. U11 (după rulare; skip fără REZULTATE reale): textele taburilor 4–5 conțin exact verdictele din
    `tu3/rezultate/SR/<joc>/REZULTATE.json` și starea verificării.
4.3 **`tests/test_scor_real.py` — exact două schimbări în W11** (decizia utilizatorului): (a) fișierele din
    `SIGILIU_TU3_SR.json` `frozen_hashes` trebuie să fie byte-identice, cu excepția celor din `replaceable` al ACESTUI
    sigiliu, care pot diferi numai printr-un lanț `inlocuiri_tu3` rezolvat (`inlocuit`) format exclusiv din înregistrări al
    căror sigiliu este `tu3/SIGILIU_TU3_SR_R.json`; (b) „nicio `INLOCUIRE_SR_*`” devine „orice `INLOCUIRE_SR_*` este validă,
    trimite la `tu3/SIGILIU_TU3_SR_R.json` și are `written_utc` ulterior sigilării lui”. W1–W10, W12 și restul W11 neschimbate.
4.4 **`replaceable`** (sha-urile de dinainte): `tu3/ui_tu3.py` `9920b9dd…`, `tests/test_app_tu3.py` `c9a7f98d…`,
    `tests/test_scor_real.py` `bc45e402…`. Înregistrarea `tu3/inlocuiri/INLOCUIRE_SR_<UTC>Z.json` se scrie cu
    `inlocuiri_tu3.py --inregistreaza tu3/SIGILIU_TU3_SR_R.json SR` DUPĂ ce testele de cod trec și ÎNAINTE de rularea
    reală (prefixul `INLOCUIRE_T7C_` aparține S6; C8 citește ultima `INLOCUIRE_T7C_*`).

## 5. Ordinea S8

1. Acest protocol + sigiliul (`code_files_present: []`).
2. Codul: `tu3/verifica_sr.py`, `tests/test_verifica_sr.py`, inserțiile în `tu3/ui_tu3.py` și `tests/test_app_tu3.py`,
   cele două schimbări W11 în `tests/test_scor_real.py`.
3. Testele de cod: `test_verifica_sr.py` (T1–T4; T5 skip), `test_app_tu3.py`, `test_porturi_712/t7b/t7c.py`,
   `test_l649.py` (numai inserții); apoi înregistrarea `INLOCUIRE_SR_<UTC>Z.json`; apoi `test_scor_real.py` (24 passed).
4. `verifica_sr.py --pre-rulare` ⇒ `PRE_RULARE_S8.json` (0444).
5. Monitorul termic extern (§5.3) pornit; rularea reală 540, apoi Joker (§2.1); monitorul oprit; jurnalele 0444.
6. `verifica_sr.py --joc 540 --termic …` și `--joc joker …` ⇒ `VERIFICARE_SR.json` (0444).
7. Suitele: `test_scor_real.py`, `test_verifica_sr.py` (cu T5), suita de 33(+) și cea de 71(+), `inlocuiri_tu3 --verifica`,
   matricea; DL read-only.
8. Publicarea: `tu3/rezultate/SR/RAPORT_SR_S8.md` (0444) cu verdictele D1/D2/promovare, verificarea, resursele și
   declarațiile, INDIFERENT de rezultat.
9. Repornirea serverului 8649 (systemd-run --scope + bucla „[lansator] health ok” în jurnalul NOU); predarea.

5.3 **Monitorul termic extern** (numai citire, descriptiv): `nvidia-smi --query-gpu=timestamp,temperature.gpu,
    memory.used,power.draw --format=csv -l 1` ⇒ `tu3/rezultate/SR/termic_s8_<UTC>Z.csv` (0444 la final), pornit înaintea
    rulării 540 și oprit după Joker. Nu influențează calculul; acoperă și faza D2.

## 6. Politica de incidente (fixată acum)

- Defect de inginerie în codul S8 (verificator/UI/teste) găsit ÎNAINTE de `PRE_RULARE_S8.json`: se repară, se declară;
  protocolul nu se schimbă.
- Prăbușire a rulării reale DUPĂ START.json și ÎNAINTE de REZULTATE.json: directorul încercării se păstrează intact
  (mutat byte-identic în `tu3/rezultate/SR/incidente/<joc>_01/`), se scrie un amendament, iar o reluare cere DECIZIA
  UTILIZATORULUI (agentul se oprește și întreabă). Nicio reluare după ce un scor a devenit vizibil.
- `VERIFICARE_SR_FAIL`: se publică așa cum iese (UI cu eroare), verdictele din REZULTATE NU se modifică, cauza se
  investighează și se declară; nicio rulare nouă.
- Orice fișier nou sau schimbat după sigiliu în afara listei §7 se declară în predare.

## 7. Fișiere

- NOI: `tu3/PROTOCOL_TU3_SR_R.md`, `tu3/SIGILIU_TU3_SR_R.json`, `tu3/verifica_sr.py`, `tests/test_verifica_sr.py`,
  `tu3/inlocuiri/INLOCUIRE_SR_<UTC>Z.json`, `tu3/rezultate/SR/PRE_RULARE_S8.json`, `tu3/rezultate/SR/<joc>/{START.json,
  PREDICTII.npz, PREDICTII_SIGILIU.json, REZULTATE.json, VERIFICARE_SR.json}` (joc ∈ {540, joker}),
  `tu3/rezultate/SR/real_<joc>_<UTC>Z.log`, `tu3/rezultate/SR/termic_s8_<UTC>Z.csv`, `tu3/rezultate/SR/RAPORT_SR_S8.md`.
- ÎNLOCUITE sigilat (§4.4): `tu3/ui_tu3.py`, `tests/test_app_tu3.py`, `tests/test_scor_real.py`.
- NEMODIFICATE: `engine.py`, `parser.py`, `tu3/parser_multi.py`, `tu3/motor_n.py`, `tu3/motor_joker.py`,
  `tu3/joker_entanglement.py`, `validare.py`, `app.py`, `tu3/scor_real.py`, `tu3/porturi_712.py`, `tu3/inlocuiri_tu3.py`,
  `tu3/matrice_init.py`, `tu3/validare_tu3.py`, celelalte teste, pistele închise, protocoalele/sigiliile/amendamentele
  anterioare, `PUTERE_SR.json`, arhivele înghețate, drop-in-urile, gardul prognozei automate.
- Efecte laterale așteptate (declarate): `jurnal/*`, `tu3/__pycache__`, `tu3/date/derivat/*` (rescrise de suite/aplicație).

## 8. Acceptare S8

S8 complet = §5 parcurs; pentru fiecare joc cu `SR_P_PASS` (ambele): REZULTATE.json scris, `VERIFICARE_SR.json` scris,
verdictele publicate în `RAPORT_SR_S8.md` și afișate în taburile 4–5; toate suitele verzi; `inlocuiri_tu3 --verifica` ok;
0 drift în afara §7. Verdictele (detecție sau nu, promovare sau nu) se publică așa cum ies.

## 9. Declarații

Arhivele 5/40 și Joker sunt deja explorate (produs, porturile 7–12, graficele de frecvență, inventare); nu există set
„nevăzut”. D1 și D2 sunt teste exploratorii; o detecție NU este avantaj predictiv și nu poate fi folosită pentru bilete; o
confirmare ar cere date prospective separate și un protocol nou. Dacă extragerile sunt uniforme și independente, istoricul
nu oferă avantaj predictiv. Inspirația cuantică (MPS, entanglement, „Ryu–Takayanagi” în sensul §0 al `PROTOCOL_TU3_SR`) este
strict matematică; nicio ecuație Wheeler–DeWitt. Sigilii locale, fără atestare externă. `positive_claims_allowed=false`.
