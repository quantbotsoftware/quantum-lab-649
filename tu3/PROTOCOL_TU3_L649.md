# PROTOCOL TU3-L649 — 6/49 pe arhiva LIVE în aplicație + înlocuirea sigilată (sesiunea S3 din plan)

Scris și sigilat 2026-10-27 (~13:50Z), ÎNAINTE de orice cod al submodulului (`code_files_present: []` în
`tu3/SIGILIU_TU3_L649.json`). Subordonat planului `tu3/PLAN_SESIUNI_TU3_20261027.md` (sha `c7b4bfd3…7ead7f`, neschimbat)
și deciziilor `tu3/DECIZII_PLAN_TU3_20261027.json` (sha `b6a5ba05…53ccad`, neschimbat; D2 = bloc ADITIV în `app.py`,
LIVE implicit + comutator „înghețat (sigilat)”). Nu e un protocol științific: fără scor, fără verdict, fără ținte, fără
evaluare prospectivă. Variantele produsului rămân minime de energie ale modelului, NU predicții. Calcul clasic (GPU/CPU).
`positive_claims_allowed=false`.

## 1. Inventar read-only (înainte de protocol) și decizia utilizatorului

- `app.py` (sha `051dd839…eb7c93`) și `tu3/ui_tu3.py` (sha `9fe6c4d3…23c19f`) sunt ÎNGHEȚATE în trei sigilii publicate,
  care nu se rescriu: `tu3/SIGILIU_TU3_VS.json` (21 fișiere), `tu3/SIGILIU_TU3_DD.json` (30), `tu3/SIGILIU_TU3_LN.json`
  (55). `tu3/SIGILIU_TU3_UI.json` are `app.py` cu sha-ul vechi `db650372…`, iar `tests/test_app_tu3.py::U8` îl sare și cere
  numai inserții față de `tests/baseline/app_v2_649.py`.
- Cititorii acestor hash-uri: `tu3/matrice_init.py::integrity()` (rulat la FIECARE pornire din pictogramă; linia
  „Integritate” ajunge în jurnalul lansatorului și în notificare), `tu3/validare_tu3.py::integrity_check()`,
  `tests/test_validare_tu3.py::test_T4_frozen_hashes`, `tests/test_dedup_live.py::test_T11_frozen_and_stdlib_only`,
  `tests/test_lansator_tu3.py::test_T1_static_protected_and_desktop`. `tests/test_app_tu3.py::U1` compară calea 6/49
  implicită cu copia de referință (cu LIVE implicit ar pica). Cititorii sunt la rândul lor înghețați în DD/LN (cascadă).
  `tu3/rezultate/DD/rulare_reala_dd.py` citește sigiliul DD numai ca martor istoric (nu se rulează din nou).
- Consecință: orice octet schimbat în `app.py` sau `ui_tu3.py` dă DRIFT în matrice („ATENȚIE” permanent) și 3 teste
  roșii; nicio cale nu ocolește asta fără fișiere în plus (`run_app*.sh` și lansatoarele sunt NEMODIFICABILE prin cererea
  utilizatorului; o pagină `pages/` nu poate face LIVE implicit în vederea principală).
- Utilizatorul a ales (Mesajul 44, 2026-10-27T13:39Z), dintre patru variante, **varianta 1 — înlocuire sigilată, cu toți
  cititorii aliniați**: helper NOU `tu3/inlocuiri_tu3.py` (numai stdlib) + înregistrări 0444
  `tu3/inlocuiri/INLOCUIRE_L649_<UTC>Z.json` scrise DUPĂ teste (hash vechi → nou), cu lista fișierelor înlocuibile fixată
  ÎNAINTE de cod în `tu3/SIGILIU_TU3_L649.json`; `matrice_init.py` și `validare_tu3.py` primesc un apel spre helper în
  funcția de integritate; testele T4/T11/T1/U1 sunt amendate. Mecanismul se refolosește în S4–S6.

## 2. Domeniu (închis)

Fișiere NOI (numai acestea):
1. `tu3/inlocuiri_tu3.py` — helperul de înlocuire sigilată (§4), numai biblioteca standard.
2. `tests/test_l649.py` — testele noi (§6).
3. `tests/baseline/app_tu3_pre_l649.py` și `tests/baseline/ui_tu3_pre_l649.py` — copii byte-identice (0444) ale
   `app.py` și `tu3/ui_tu3.py` de DINAINTE (sha egal cu valorile `replaceable` din sigiliu), pentru verificarea
   „numai inserții”.
4. `tu3/inlocuiri/INLOCUIRE_L649_<UTC>Z.json` (0444) — înregistrarea de înlocuire (§4.3), scrisă după testele de cod.
5. `tu3/rezultate/L649/acceptare_l649.py` (scriptul de acceptare) și `tu3/rezultate/L649/ACCEPTARE_L649_<UTC>Z.json`
   (0444) + acest protocol și sigiliul lui.

Fișiere MODIFICATE (numai acestea = cheile `replaceable` din sigiliu, cu sha-ul de dinainte):
- `app.py` — NUMAI inserții (§3.1); față de `tests/baseline/app_v2_649.py` și față de copia de dinainte.
- `tu3/ui_tu3.py` — NUMAI inserții (§3.2) față de copia de dinainte.
- `tu3/matrice_init.py` — `integrity()` folosește helperul; linia „Integritate” arată și înlocuirile (§5.1).
- `tu3/validare_tu3.py` — `integrity_check()` folosește helperul (§5.2); restul neschimbat.
- `tests/test_app_tu3.py` (U1 → U1′, §5.3), `tests/test_validare_tu3.py` (T4, §5.4), `tests/test_dedup_live.py` (T11,
  §5.4), `tests/test_lansator_tu3.py` (T1, §5.4).

Fișiere PROTEJATE, byte-identice (hash-urile în `frozen_hashes` / `frozen_external` din sigiliu, verificate la final):
`engine.py`, `parser.py`, `validare.py`, `verify_ql649.py`, `run_app.sh`, `run_app_tu3.sh`, `porneste_aplicatia.sh`,
`porneste_aplicatia_tu3.sh`, `tu3/parser_multi.py`, `tu3/motor_n.py`, `tu3/motor_joker.py`, `tu3/joker_entanglement.py`,
`tu3/arhiva_live.py`, `tu3/dedup_live.py`, `pl649/ui_pl649.py`, toate celelalte teste (inclusiv `tests/test_app.py`,
`tu3/tests/*`), copiile `tests/baseline/*` existente, toate protocoalele, amendamentele, sigiliile și rezultatele
anterioare, planul, deciziile, `predari/genereaza_predare.py`, drop-in-urile `tu3-*.conf`, cele 3 `.desktop`, fișierul
înghețat `predictie_numere/probe_date/extrageri_649.jsonl` (sha `193eaf7a…`). Gardul prognozei automate: neatins.
Pista DL: numai read-only. OGLINDA: neatinsă.

## 3. Specificația L649

### 3.1 `app.py` — patru inserții (niciun rând existent șters sau schimbat)

- A (după blocul TU3 care se termină cu `st.stop()`): bloc comentat „TU3-L649”:
  `L649_SRC = ui_tu3.l649_source_selector()`; la schimbarea sursei față de rularea precedentă (`l649_prev_src`) se
  apelează `ui_tu3.l649_release(vechi, nou, get_dataset)`; `L649_INFO = ui_tu3.l649_info(L649_SRC)`. Dacă
  `L649_SRC == "live"`, se redefinesc, în același modul, `get_dataset()` (întoarce `.base` = `parser.Dataset` al setului
  LIVE din `parser_multi.build_game_dataset("649", "live")`, adică adaptorul `adapt_649` → `parser.build_dataset`,
  ambele nemodificate) și `run_engine(cfg_json)` (→ `ui_tu3.l649_run_engine(cfg_json, cheie_LIVE)`, același
  `engine.run_full` și aceeași conversie tensor → NumPy ca `run_engine` original). Dacă `L649_SRC == "frozen"`, nu se
  redefinește nimic: rulează EXACT funcțiile originale (`build_dataset(DEFAULT_SOURCE)`), adică copia de referință.
- B (după cardurile antetului, înainte de bannerul de onestitate): `ui_tu3.l649_render_source(L649_SRC, L649_INFO)` —
  o singură linie `st.caption` care începe cu „🛰 Sursa 6/49:” + eventual `st.warning` cu diferențele martorului.
- C (în dicționarul `payload` al sigiliului de timp, după `"source_sha256"`): `**ui_tu3.l649_seal_fields(L649_SRC,
  L649_INFO),` — câmpurile sursei active intră în conținutul sigilat.
- Nicio altă inserție. Calea 5/40 / Joker rămâne neatinsă (blocul A e după `st.stop()` al acelor moduri).

### 3.2 `tu3/ui_tu3.py` — inserții

- În `release_mode`, ramura `old == "649"`: o linie nouă care golește și cache-ul setului LIVE 6/49 (schimbarea modului
  eliberează și setul LIVE, nu doar pe cel înghețat).
- Secțiune nouă, la final, „TU3-L649”:
  - `L649_SOURCES = {"live": "LIVE — arhiva actualizată automat", "frozen": "înghețat (sigilat)"}`;
  - `l649_source_selector()` — `st.radio` în bara laterală (cheie `l649_src`), implicit `live`; alegerea se păstrează
    în `st.session_state["l649_src_saved"]` (revenirea din alt mod nu o resetează);
  - `l649_live_key()` = sha256 al JSONL-ului LIVE 6/49 rezolvat (`live_key("649")`, lanțul pointer → manifest → JSONL);
  - `l649_live_dataset(src_key)` — `st.cache_resource(max_entries=1)`, `build_game_dataset("649", "live")`;
  - `l649_run_engine(cfg_json, src_key)` — `st.cache_resource(max_entries=4)`, `engine.run_full(base, cfg,
    base.device)`, conversie identică cu `app._np`;
  - `l649_martor(src_key)` — `st.cache_data`; construiește PE CPU setul înghețat și pe cel LIVE și întoarce
    `parser_multi.compare_frozen_live` + sha-urile, `version_dir`, numărul de extrageri și ultima dată ale fiecăruia;
  - `l649_info(src)` — cheia LIVE + martorul; dacă LIVE e indisponibil (orice excepție, inclusiv `IntegrityError`):
    în modul `live` → `st.error` explicit („alege «înghețat (sigilat)»”) + `st.stop()`, fără comutare tăcută; în modul
    `frozen` → aplicația merge, iar linia sursei spune „LIVE indisponibil: <motiv>”;
  - `l649_release(old, new, get_dataset_649)` — golește cache-ul setului sursei părăsite (`live` → `l649_live_dataset`;
    `frozen` → `get_dataset` original), apoi `gc.collect()` + `torch.cuda.empty_cache()`; jurnal în
    `st.session_state["l649_release_log"]` (from/to/VRAM înainte/după/UTC);
  - `l649_render_source(src, info)` și `l649_seal_fields(src, info)` (câmpuri: `l649_source_kind`,
    `l649_source_file_sha256` (JSONL LIVE sau fișierul înghețat), `l649_live_version_dir` (sau null),
    `l649_adapted_sha256` (sau null), `l649_protocol_sha256`).

### 3.3 Comportament (martori S1–S9)

- S1. Implicit (sesiune nouă) sursa 6/49 = LIVE; comutatorul are exact două opțiuni.
- S2. „înghețat (sigilat)” ⇒ vederea principală 6/49 identică cu copia de referință (U1′, §5.3), mai puțin linia
  „🛰 Sursa 6/49:” și eventualul avertisment al martorului.
- S3. Martor: cheile comune LIVE vs înghețat — numărul cheilor comune, al diferențelor pe chei comune (dată/numere), al
  cheilor numai în LIVE și numai în înghețat, și „LIVE ⊇ înghețat: DA/NU”. Diferențele se AFIȘEAZĂ (primele 20 de chei,
  `st.warning`), NU se repară și NU schimbă datele. Valorile afișate = `compare_frozen_live` pe aceleași fișiere.
- S4. Sursa activă și sha-ul ei sunt vizibile în vederea principală (linia „🛰 Sursa 6/49:”), în bara laterală
  (comutatorul) și în sigiliul de timp (câmpurile `l649_*` din §3.2, incluse în `sha256` canonic).
- S5. Schimbarea sursei eliberează cache-ul setului părăsit + `empty_cache` (jurnalizat); schimbarea modului din 6/49
  eliberează ambele seturi 6/49.
- S6. Arhiva LIVE se actualizează la 30 min: cheia cache-ului = sha-ul JSONL-ului LIVE ⇒ o versiune nouă intră la
  următoarea rulare a paginii; versiunea veche iese din cache (`max_entries=1` la set).
- S7. `validare.py`, protocoalele sigilate, backtestul unic, SCI și artefactele pistelor închise rămân pe sursa
  înghețată: taburile 4–5 și 7–12 afișează aceleași rezultate sigilate în ambele surse (linia sursei o spune explicit).
- S8. Calea 5/40 / Joker neschimbată (U2–U7 neschimbate și verzi).
- S9. Niciun fișier nou în `predictie_numere/`; singurul efect lateral al căii LIVE: `adapt_649` scrie (0444) fișierul
  derivat `tu3/date/derivat/649_<sha12>.jsonl` pentru fiecare versiune LIVE nouă (comportament existent al P).

## 4. Mecanismul de înlocuire sigilată `inlocuiri_tu3/v1`

### 4.1 Sigiliul protocolului (scris ÎNAINTE de cod)
`tu3/SIGILIU_<...>.json` cu: `sha256` = sha protocolului, `file`, `sealed_utc` (`YYYY-MM-DDTHH:MM:SSZ`),
`code_files_present: []`, `results_present: false`, `replacement_mechanism: "inlocuiri_tu3/v1"`,
`replaceable: {cale relativă: sha înainte}` (lista ÎNCHISĂ a fișierelor care pot fi înlocuite), `frozen_hashes`,
`frozen_external`, `positive_claims_allowed: false`; fișierul 0444.

### 4.2 Înregistrarea de înlocuire (scrisă DUPĂ teste)
`tu3/inlocuiri/INLOCUIRE_<ETICHETĂ>_<UTC>Z.json`, 0444, creată exclusiv (`open(…, "x")`), cu: `record`,
`mechanism: "inlocuiri_tu3/v1"`, `seal` (cale relativă), `seal_sha256`, `protocol`, `protocol_sha256`, `written_utc`,
`replacements: {cale: {"from": sha, "to": sha}}`, `positive_claims_allowed: false`.

### 4.3 Reguli de validitate (toate obligatorii)
- R1 JSON obiect cu toate câmpurile de mai sus; `positive_claims_allowed is False`; `mechanism` corect.
- R2 înregistrarea nu are niciun bit de scriere (`mode & 0o222 == 0`).
- R3 sigiliul există, sha-ul lui = `seal_sha256`, nu are bit de scriere.
- R4 `seal.sha256` = sha(protocol) = `protocol_sha256`; `seal.file` = numele protocolului.
- R5 `seal.code_files_present == []`, `seal.results_present is False`, `seal.replacement_mechanism ==
  "inlocuiri_tu3/v1"`.
- R6 `written_utc` > `seal.sealed_utc` (înregistrarea e ulterioară sigilării).
- R7 fiecare cale din `replacements` ∈ `seal.replaceable`; `from`/`to` = 64 hex, `from ≠ to`.
- R8 `from` = `seal.replaceable[cale]` SAU = `to` al unei înregistrări valide anterioare (ordinea numelor) a ACELUIAȘI
  sigiliu, pentru aceeași cale (corectură după înregistrare = lanț, declarată ca incident).
Înregistrările invalide sunt ignorate (raportate în `invalid_records`), nu repară nimic.

### 4.4 Rezolvarea
Pentru fiecare `(cale, sha_sigilat)` din `frozen_hashes` al unui sigiliu vechi: fișier absent ⇒ DRIFT; sha curent =
sha_sigilat ⇒ identic; altfel se urmează lanțul `sha_sigilat → to → to …` prin înregistrări valide (fără cicluri);
dacă se ajunge la sha-ul curent ⇒ „înlocuit sigilat” (cu numele înregistrărilor), altfel DRIFT. API:
`resolve(frozen_hashes, root) -> {"drift": [...], "replaced": [...], "identical": int, "records": [...],
"invalid_records": [...]}`. CLI: `--verifica` (rezolvă VS/DD/LN/L649), `--simuleaza SIGILIU ETICHETĂ`,
`--inregistreaza SIGILIU ETICHETĂ`. Scrierea refuză (cod 1): orice DRIFT în `frozen_hashes` / `frozen_external` ale
sigiliului nou, nicio schimbare, o cale schimbată din afara `replaceable`, un fișier `new_files_planned` de tip
copie de referință cu sha greșit.

### 4.5 Limite declarate
Sigilii locale, fără atestare externă (ca toate sigiliile proiectului). Mecanismul nu face un fișier „neschimbat”:
matricea și testele spun explicit câte și care fișiere sunt înlocuite sigilat și prin ce înregistrare. O nouă înlocuire
(de ex. `ui_tu3.py` în S4) cere un protocol NOU sigilat înainte de cod, cu propria listă `replaceable`.

## 5. Cititorii aliniați

- 5.1 `matrice_init.integrity()`: `drift` = `resolve(VS.frozen_hashes, QL)["drift"]`; câmpuri noi `replaced`,
  `records`; `status` OK ⇔ `drift == []`. Linia „Integritate (sigiliu TU3-VS …): OK pe 21 fișiere” păstrează prefixul
  și „: OK pe” și adaugă „(N înlocuite sigilat: … · INLOCUIRE_…)” când N > 0. Restul matricii neschimbat.
- 5.2 `validare_tu3.integrity_check()`: `drift` prin `resolve`; câmp nou `replaced`; celelalte verificări neschimbate.
- 5.3 U1′ (`test_app_tu3.py`): copia de referință vs aplicația cu „înghețat (sigilat)” selectat ⇒ instantaneele vederii
  principale identice după eliminarea EXACT a liniilor `caption` care încep cu „🛰 Sursa 6/49:” (cel mult una); restul
  testului ca înainte. U2–U9 neschimbate.
- 5.4 T4 / T11 / T1: bucla „fișierele înghețate byte-identice” devine „fiecare fișier înghețat e identic SAU înlocuit
  sigilat prin `inlocuiri_tu3`”; restul aserțiunilor neschimbat; T4 cere în plus ca setul înlocuit ⊆
  `SIGILIU_TU3_L649.replaceable`.

## 6. Testele noi `tests/test_l649.py` (AppTest în mod FAST unde e nevoie; NU tipăresc și NU compară variantele)

- L1 sigiliul L649: sha protocol; `code_files_present == []`; `results_present is False`; mecanism v1; 0444;
  `positive_claims_allowed is False`; `replaceable` = exact cele 8 fișiere din §2.
- L2 `frozen_hashes` + `frozen_external` ale sigiliului L649 byte-identice.
- L3 copiile `tests/baseline/*_pre_l649.py` au sha = `replaceable`; `app.py` = numai inserții față de copie și față de
  `app_v2_649.py`; `ui_tu3.py` = numai inserții față de copie.
- L4 helperul pe directoare temporare: identic; înlocuit valid; DRIFT fără înregistrare; înregistrare cu bit de scriere,
  sigiliu modificat, cale în afara `replaceable`, `from` greșit, `written_utc` anterior sigilării ⇒ ignorată ⇒ DRIFT;
  lanț în două trepte; ciclu fără buclă infinită; numai biblioteca standard (AST).
- L5 implicit LIVE: `session_state["l649_src"] == "live"`; linia sursei conține sha-ul JSONL LIVE (= `PM.resolve_live`)
  și ultima dată LIVE; fără excepții; 12 taburi; 3 variante 6 din 1..49 distincte.
- L6 martorul: valorile din linia sursei = `compare_frozen_live`; o comparație sintetică cu diferențe produce
  avertismentul cu cheile (funcția de randare, fără a atinge datele).
- L7 LIVE → înghețat → LIVE: jurnalul `l649_release_log` = [(live, frozen), (frozen, live)]; în înghețat linia sursei
  conține `193eaf7a6f4f`; VRAM după revenire ≤ VRAM inițial + 8 MiB.
- L8 sigiliul de timp în LIVE și în înghețat: `l649_source_kind`, sha-ul sursei, `version_dir`; `sha256` canonic.
- L9 schimbarea modului 6/49 (LIVE) → 5/40 golește și setul LIVE (cache gol după comutare).
- L10 `--verifica` al helperului: VS/DD/LN/L649 fără DRIFT; înlocuirile ⊆ `replaceable`.

## 7. Ordinea lucrului

O1 acest protocol + sigiliul (0444) → O2 copiile de referință (0444) → O3 cod (`inlocuiri_tu3.py`, `ui_tu3.py`,
`app.py`, `matrice_init.py`, `validare_tu3.py`) + testele (noi/amendate) → O4 `py_compile`, testele care nu depind de
înregistrare (`test_l649.py` fără L10, `test_app.py`, `test_app_tu3.py`) → O5 `--simuleaza`, apoi `--inregistreaza
tu3/SIGILIU_TU3_L649.json L649` → O6 toate suitele → O7 C2 (server real din pictogramă) → O8 acceptare (0444).
Orice eșec după O5 care cere cod nou ⇒ înregistrare înlănțuită (R8) + incident declarat în acceptare; sigiliile și
înregistrările scrise nu se rescriu și nu se șterg.

## 8. Criterii de acceptare (raport `tu3/rezultate/L649/ACCEPTARE_L649_<UTC>Z.json`, 0444) — verdict `L649_PASS`

- C1 `tests/test_l649.py` integral verde (0 failed; skipped numai dacă CUDA lipsește, declarat);
  `tests/test_validare_tu3.py tests/test_app.py tests/test_app_tu3.py tests/test_dedup_live.py` exact
  **33 passed, 3 skipped**; `tests/test_lansator_tu3.py` **5 passed**.
- C2 server real: serverul utilizatorului oprit, repornit cu `gtk-launch quantum-lab-649` ⇒ matricea „TOATE 3 MODURILE
  READY”, „Integritate …: OK pe 21 fișiere (… înlocuite sigilat …)”, health ok, numai 127.0.0.1; o rulare AppTest în
  configurația de PROTOCOL pe LIVE fără excepții (sursa = LIVE, sha afișat = sha-ul LIVE curent); la final serverul
  repornit din pictogramă.
- C3 0 DRIFT pe `frozen_hashes`/`frozen_external` L649; `inlocuiri_tu3 --verifica` OK; `dedup_live --verifica` OK;
  DL `verifica_publicarea.py` exit 0 (read-only).
- C4 fișierele modificate = exact cele cu înlocuire în înregistrare (⊆ `replaceable`); fișiere noi = numai cele din §2
  (plus jurnale și fișierele derivate S9).
Altfel verdict `L649_FAIL`, publicat cu motivele, fără rescrierea sigiliilor.

## 9. Abateri și limite declarate dinainte

- Tabul 4 (Multiversul Nul) în LIVE: histogramele și SCI provin din `SCI.json` sigilat (înghețat, 2595 extrageri), dar
  linia „6N/49” folosește N al sursei active (`R["n_draws_used"]`, rând existent, neschimbabil prin regula inserțiilor);
  diferența (de ordinul a câteva extrageri din ~2600) e declarată în linia sursei.
- În LIVE, `R["source_sha256"]` (subsolul paginii și câmpul existent al sigiliului) e sha-ul fișierului ADAPTAT
  (`parser.Dataset` construit din `adapt_649`); sha-ul JSONL-ului LIVE apare separat (`l649_source_file_sha256`).
- Variantele cu configurația QL649-P1 pe date LIVE NU sunt rezultatul protocolului științific QL649-P1 (închis pe sursa
  înghețată); sunt minimele de energie ale aceluiași model pe date mai noi. Linia sursei o spune.
- Sigiliul de timp al modului înghețat primește și el câmpurile `l649_*` (format nou, aditiv).
- Prima încărcare în LIVE rulează motorul complet (~30–40 s pe GPU la configurația de protocol), ca înainte pe sursa
  înghețată; a doua sursă se calculează la prima selectare.

## 10. În afara domeniului

Gardul prognozei automate (decizia utilizatorului), linger, retenția `versiuni/`, porturile taburilor 7–12 (S4–S6),
scorul real 5/40 / Joker (S7–S8), pista DL (înghețată, read-only), OGLINDA.
