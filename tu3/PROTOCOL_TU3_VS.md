# PROTOCOL TU3-VS — modulul „Validare + server”: suita pe toate 3 căile (sintetic) + server 127.0.0.1:8649 + matricea de inițializare

Sesiunea 2026-10-26 (start ~18:07Z), continuare din checkpoint-ul 20261026T180415Z, la cererea utilizatorului (Mesajul 34).
Scris și sigilat ÎNAINTE de orice cod al modulului: `tu3/validare_tu3.py`, `tu3/matrice_init.py`,
`tests/test_validare_tu3.py`, `tests/baseline/run_app_v2.sh` și `tu3/rezultate/VS/` NU există la sigilare, iar
`run_app.sh` are încă hash-ul din sigiliu. Subordonat `PROTOCOL_TU3_P1.md` (§1, ultimele două trepte: „validare
(sintetic, γ = 1/2) → server 127.0.0.1:8649”) și `PROTOCOL_TU3_UI.md` (§0: serverul și matricea aparțin acestui modul).

## 0. Încadrare onestă

- Calcul CLASIC (PyTorch, CUDA pe RTX 5060 Laptop; fallback CPU jurnalizat). Modulul doar VERIFICĂ și PORNEȘTE produsul
  existent; nu introduce niciun model, niciun scor pe istoria reală, niciun prag nou pentru produs.
  `positive_claims_allowed=false`. Variantele sunt minime de energie ale modelului, NU predicții; nu se compară cu nicio
  extragere. Orice scor pe istoria reală (5/40, Joker sau 6/49 LIVE) cere protocol separat, sigilat înainte.
- NEMODIFICATE (hash-uri în sigiliu): `engine.py`, `parser.py`, `validare.py`, `app.py`, `porneste_aplicatia.sh`,
  `tu3/parser_multi.py`, `tu3/motor_n.py`, `tu3/motor_joker.py`, `tu3/joker_entanglement.py`, `tu3/ui_tu3.py`,
  `tu3/arhiva_live.py`, `tests/test_app.py`, `tests/test_app_tu3.py`, protocoalele P1/P/E40/EJ/UI și fișierele de putere
  `PUTERE_J.json`, `PUTERE_E40.json`, `PUTERE_EJ.json`. Calea 6/49 rămâne identică (sursa înghețată
  `parser.DEFAULT_SOURCE` + `engine.run_full`). Singurul fișier existent atins: `run_app.sh`, strict ADITIV (§3).
- Neatinse: colectorul/baza, arhiva LIVE și deduplicarea versiunilor (submodul separat, numai la cererea utilizatorului),
  6/49 pe LIVE (numai la cererea utilizatorului, cu amendament), protocolul prospectiv și gardul lui (kernel
  7.0.11→7.2.6, decizia utilizatorului), OGLINDA, DL (numai verificare read-only), modelele închise.
- Verificările de putere γ = 1/2 (J, E40, EJ) au fost rulări UNICE, cu refuz de suprascriere. NU se rerulează; „reverificare”
  înseamnă recitirea fișierelor de putere și recalcularea porților din valorile stocate față de pragurile sigilate (§1 V4).

## 1. Suita de validare (`tu3/validare_tu3.py --suita`) — praguri fixate înainte de rulare

Toți pașii rulează în ordine; niciun pas nu tipărește, nu salvează și nu compară variante (nici reale, nici sintetice);
din pytest se păstrează numai numărătorile.

- **V1 — calea 6/49 (sintetic):** `pytest tests/test_parser.py tests/test_engine.py tests/test_validare.py` →
  PASS dacă `failed = errors = skipped = 0` și `passed = 32` (inventar `--collect-only`: 32 teste; cele 2 `skipif` cer
  numai absența CUDA, iar CUDA e prezent). Notă: `test_parser.py::
  test_real_dataset_invariants` citește sursa înghețată 6/49 numai pentru invarianți de integritate (inventar, nu
  selecție; niciun motor pe date reale).
- **V2 — căile 5/40 și Joker + J/P/arhivă:** `pytest tu3/tests` → PASS dacă `passed = 53`, `failed = errors = skipped = 0`.
  (Include fumurile de produs E11/EJ12 pe LIVE din protocoalele E40/EJ, deja existente; variantele nu sunt tipărite.)
- **V3 — UI pe toate 3 modurile:** `pytest tests/test_app.py tests/test_app_tu3.py` → PASS dacă `passed = 11`,
  `skipped = 3` (testele de protocol cer `QL649_UI_PROTOCOL=1`), `failed = errors = 0`.
- **V4 — reverificarea puterii γ = 1/2 (fără rerulare):** pentru J (`rezultate/J/PUTERE_J.json`), E40 și EJ:
  verdictul este `J_PASS` / `E40_PASS` / `EJ_PASS`; `protocol_sha256` = sha-ul actual al protocolului (P1 / E40 / EJ);
  fiecare intrare din `code_sha256` = sha-ul actual al fișierului; martorii (`witnesses_*`) au `pass = true`;
  `real_archive_read = false`; porțile recalculate din valorile stocate față de pragurile sigilate:
  J — puterea ≥ 0.90 și FPR ≤ 0.02 pentru FIECARE dintre I, S_E, Φ; E40 — G1 ≥ 0.90, G2 ≤ 0.02;
  EJ — G1 ≥ 0.90, G2 ≤ 0.02, GJ1 ≥ 0.50, GJ2 ≤ 0.20; iar indicatorii `*_pass` stocați coincid cu recalcularea.
  Modul fișierului (0444 la E40/EJ; J are 0664 istoric) se raportează descriptiv; nu se modifică nimic.
- **V5 — produsul cap-coadă pe date SINTETICE, câte unul pe cale (config FAST = cele 5 suprascrieri ale UI:
  `mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60, gamma_grid=12`):** seturi uniforme noi, 200 de rânduri,
  zile duble ocazionale, semințe fixe 649 → 64905, 540 → 54005, Joker → 45205, scrise într-un director temporar.
  6/49: `validare.synthetic_dataset` + `engine.run_full`; 5/40: `parser_multi.build_game_dataset("540", <cale>)` +
  `motor_n.run_full(ds, SHAPE_540, FAST)`; Joker: `build_game_dataset("joker", <cale>)` + `motor_joker.engine_joker(ds, FAST)`
  (poarta de putere a produsului se aplică numai datelor reale). PASS pe cale dacă: exact 3 variante unice, regula
  activă (6 distincte 1..49 / 5 distincte 1..40 / 5 distincte 1..45 + Joker 1..20), sortate, energii finite,
  `is_protocol = false`, `positive_claims_allowed = false`, `device = cuda` când CUDA e disponibil.
- **V6 — integritate:** hash-urile tuturor fișierelor NEMODIFICATE (§0) = cele din sigiliu; `run_app.sh` = copia de
  referință + numai inserții (§3); `bash -n run_app.sh` OK.

Verdict suită: `VS_SUITE_PASS` numai dacă V1–V6 trec; altfel `VS_SUITE_FAIL`, publicat ca atare, fără retuning.
Raport: `tu3/rezultate/VS/VALIDARE_TU3_<UTC>Z.json` (0444, refuz de suprascriere) cu pașii, numărătorile, timpii,
hash-urile și dispozitivul; fără variante.

## 2. Matricea de inițializare (`tu3/matrice_init.py`)

Tipărită la pornirea serverului (și la cerere). NU rulează niciun motor (`engine.run_full`, `motor_n.run_full*`,
`motor_joker.engine_joker` / `run_full_joker`) și NU conține variante. Conținut:
- Sistem: UTC, Python, torch, CUDA (dispozitiv, capabilitate, VRAM totală/liberă), Streamlit, adresa/portul de pornire,
  `positive_claims_allowed=false`.
- Câte un rând pe mod (🌌 6/49, 🌀 5/40, 🃏 Joker): regula (extragere / bilet), sursa (6/49: înghețată, sha verificat
  = `FROZEN_649_SHA256`; 5/40, Joker: LIVE prin lanțul pointer → manifest → JSONL), sha (12), extrageri, pași,
  prima/ultima dată, excluse, dispozitivul tensorilor, produsul, protocolul (sha verificat față de sigiliul lui),
  `config_digest` de protocol, verdictul de putere și potrivirea hash-urilor de cod din fișierul de putere (6/49:
  protocolul QL649 propriu, fără poartă de putere TU3), starea `READY` / `ERROR (<motiv>)`.
- Arhiva LIVE: `updated_utc`, `version_dir`, manifest (12), mărimea `versiuni/` (descriptiv).
- Integritate: hash-urile fișierelor NEMODIFICATE față de sigiliul TU3-VS (`OK` / `DRIFT`).
Ieșiri: tabel pe stdout + `jurnal/MATRICE_INIT_<UTC>Z.json`. Cod de ieșire 0 dacă toate 3 modurile sunt `READY` și
integritatea este `OK`, altfel 1 (serverul pornește oricum; UI-ul își afișează propriile erori — §3).

## 3. `run_app.sh` — modificare strict ADITIVĂ

Copie byte-identică a versiunii actuale în `tests/baseline/run_app_v2.sh` (sha în sigiliu). Inserții (liniile existente
rămân byte-identice și în aceeași ordine): (a) după `py_compile`-ul existent, un al doilea `py_compile` pe modulele TU3
(`tu3/ui_tu3.py`, `tu3/parser_multi.py`, `tu3/motor_n.py`, `tu3/motor_joker.py`, `tu3/joker_entanglement.py`,
`tu3/matrice_init.py`, `tu3/validare_tu3.py`); (b) după verificarea CUDA, rularea matricei cu ieșirea în
`jurnal/app_<UTC>Z.matrice.txt` (fișier separat, pentru că linia existentă `tee "${LOG}"` trunchiază jurnalul serverului);
cod ≠ 0 ⇒ mesaj `[QL649] ATENȚIE …` și pornire în continuare. Adresa implicită rămâne 127.0.0.1, portul 8649.

## 4. Serverul (`tu3/validare_tu3.py --server`, după `./run_app.sh`)

PASS dacă: `GET http://127.0.0.1:8649/_stcore/health` = `ok`; `GET /` = 200; `ss -ltn` arată ascultare pe
`127.0.0.1:8649` și pe nicio adresă publică/wildcard (`0.0.0.0`, `[::]`, `*`); ultimul `jurnal/app_*.matrice.txt` există,
are 3 moduri `READY` și integritate `OK`, iar JSON-ul matricei nu conține chei `variants`; jurnalul serverului nu conține
`Traceback`. Raport `tu3/rezultate/VS/SERVER_TU3_<UTC>Z.json` (0444). Verdict modul: `VS_PASS` numai dacă suita și
serverul trec. Serverul rămâne pornit pentru utilizator în sesiunea agentului (procesul se oprește la închiderea
sesiunii; oprire explicită: `./porneste_aplicatia.sh --stop` sau Ctrl+C); nu se instalează serviciu systemd.

## 5. Teste (`tests/test_validare_tu3.py`) — toate trebuie să treacă

T1 matricea nu apelează niciun motor (funcțiile motor înlocuite cu unele care ridică excepție), are 3 moduri `READY` și
nicio cheie `variants`; T2 reverificarea V4 detectează falsificarea (verdict, hash de cod, sha de protocol, valoare de
poartă, `real_archive_read`) pe copii temporare (martori negativi); T3 `run_app.sh` = copia + numai inserții, `bash -n`
OK; T4 hash-urile NEMODIFICATE; T5 V5 trece pe toate 3 căile sintetice; T6 parserul numărătorilor pytest pe exemple fixe.
Plus: `py_compile` pe fișierele noi/atinse; `tu3/tests` 53/53 și UI 11 passed + 3 skipped (prin V2/V3).

## 6. Artefacte

`tu3/PROTOCOL_TU3_VS.md` + `tu3/SIGILIU_TU3_VS.json` (înainte de cod), `tests/baseline/run_app_v2.sh`,
`tu3/matrice_init.py`, `tu3/validare_tu3.py`, `run_app.sh` (inserții), `tests/test_validare_tu3.py`,
`tu3/rezultate/VS/VALIDARE_TU3_*.json`, `tu3/rezultate/VS/SERVER_TU3_*.json`; apoi `predari/OPERATIV.md`, Mesajul 34 în
supliment, `predari/genereaza_predare.py` (pereche nouă, același UTC).
