# PROTOCOL TU4-S22 — randarea grafică, în direct, a vârfurilor de telemetrie în fila „Memorie” a ferestrei Tauri și eticheta standard a emisiilor

Sesiunea S22. Cererea = Mesajul 67 (2026-10-27T23:17:10-04:00 = 2026-10-28T03:17:10Z). Protocolul e scris și sigilat
(`tu4/SIGILIU_TU4_S22.json`) ÎNAINTE de orice modificare a fișierelor din `./rust_core`.
`positive_claims_allowed=false`. Calculul rămâne clasic, pe CPU. Cuvântul „QUANTUM” din numele fișierului vine din cererea
utilizatorului. Nu înseamnă hardware cuantic, avantaj cuantic și nicio proprietate a extragerilor.

## 0. Ce este și ce NU este S22

- **Pornire verificată (S0, deja făcut):**
  - primul pas al predării 20261028T031336Z (`primul_pas_S22.sh`, `0c755bd7…`) a ieșit integral PASS:
    `tu4/rezultate/S22/primul_pas_S22_20261028T031728Z.log`. Rezultate: 13 × `drift []` (inclusiv cele 80 de hash-uri
    S21), `LANT_PREFIX_S20 OK` (3 linii), EM 42/42, JU 13/13, 130 passed, 38 + 3s, UI 15/15, `EXIT_PY=0`,
    `SURSE_RUST_OK 27`, 61/61 teste Rust, binarul `f25aad0c…`, paritatea 587/587 (`PARITY_RC=0`), admisibilitatea
    implicită 2026-10-29 6/6 + 4/4, B2 PASS (2026-11-01 = 6 × `EMISIE_ABSENTA`), M2 15/15, `DL_RC=0`. În
    `tu4/incidente/` sunt numai `EM_01`, `FR_01`, `S19_01`, `S20_01`.
  - inventarul read-only: `tu4/rezultate/S22/INVENTAR_S22_20261028T032050Z.json` (`427baaef…`), scris de
    `tu4/rezultate/S22/inventar_s22.py`. Inventarul nu e experiment.
- **Starea constatată (din inventar):**
  - Comenzile Tauri înregistrate în `main.rs` (10) și cele invocate în `app.js` (10) coincid exact; `cmd_telemetrie`
    există din S21 și întoarce numai agregatul (fără tablouri).
  - Fila „Memorie” (`tab-mem`) EXISTĂ din S21 (Q10), cu blocul „Telemetrie continuă (SSD)” ca tabel text (`t-kv`). Nu are
    nicio reprezentare grafică (niciun `<canvas>`) și se reîmprospătează numai la pornire și la butonul „Remăsoară”.
  - `telemetry.rs` scrie seria ca **JSONL text**, linie cu linie (`write_all` în mod append), în segmente
    `telemetrie_NNN.jsonl` + `rezumat.json`, sub `./telemetry/`. Nu folosește `mmap`;
    `memmap2` e folosit numai de `parser.rs`, read-only, pentru arhivele LIVE. Agregatul nu are `rss_principal_ultim`.
    Volumul actual al tamponului: 6 sesiuni, 837 028 B (≈ 260 B pe eșantion, ≈ 0,9 MB/oră la 1000 ms).
  - Eticheta standard a emisiilor este `LABEL` din `tu4/emite.py`: „test științific în curs; nu este sfat de joc”.
    Toate cele 3 emisii certificate prin LANT (2026-10-29) o poartă exact. Pentru 2026-11-01 nu există încă emisii.
- **Este:** o modificare NUMAI de frontend (`rust_core/ui/app.js`, `rust_core/ui/index.html`):
  1. în fila „Memorie”, un card nou cu un `<canvas>` de dimensiune fixă care desenează vârfurile din agregatul
     `cmd_telemetrie` (Σ VmRSS arbore: ultim + vârf; Σ VmRSS WebKit*: ultim + vârf + linia de referință 30 MB; VmRSS
     proces principal: vârf);
  2. reîmprospătarea în direct a acestui card și a tabelului `t-kv`, cât timp fila „Memorie” e activă și documentul e
     vizibil, fără nicio serie păstrată în Webview;
  3. în fila „Filtru admisibilitate”, afișarea explicită a etichetei standard și a faptului că starea fiecărui flux
     (inclusiv pentru ținta programată 2026-11-01) este starea curentă a emisiei din LANT.
- **NU este:** modificare Rust (niciun `.rs`, `Cargo.*`, `tauri.conf.json`, `capabilities/` nu se atinge), schimbarea
  formatului de stocare a telemetriei, reducerea memoriei WebKitGTK, model nou, emisie, decontare, reglaj, selecție de
  bilete, modificarea tribunalului Python, a emițătorului, a emisiilor, a timerelor, a interfeței Streamlit 8649
  (`tu3/ui_tu3.py`) sau a pistei DL. Rust NU emite și NU decontează.
- **Corecții de premisă (declarate exact):**
  1. Cererea numește „interfața Tauri (ui_tu3.py / rust_core)”. `tu3/ui_tu3.py` este interfața **Streamlit** de pe
     127.0.0.1:8649 (Python); nu conține nicio comandă Tauri (`refera_comenzi_tauri: false`). Fereastra Tauri este
     `rust_core/ui/` + `rust_core/src/main.rs`. `ui_tu3.py` NU se modifică.
  2. Cererea vorbește de „noua filă Memorie”. Fila există din S21, iar `cmd_telemetrie` îi trimite deja agregatul, ca text.
     S22 adaugă randarea grafică și reîmprospătarea în direct; nu creează o filă nouă.
  3. Cererea spune că datele brute „vor continua să fie stocate prin fișiere binare cu mapare directă (mmap)”. Nu sunt
     binare și nu sunt mapate: sunt JSONL text scris prin `write_all` (S21 Q7). S22 **păstrează neschimbat** mecanismul
     S21 (același SSD, aceeași rădăcină, același format); acesta este sensul exact al lui „continuă să fie stocate”.
     Trecerea la fișiere mapate NU se face în S22, din trei motive verificabile: (a) paginile murdare ale unui fișier
     mapat se contabilizează în RSS-ul procesului care scrie (RssFile), deci ar crește tocmai memoria pe care S21 M3 a
     demonstrat-o mărginită (+4 096 B la 3000 de eșantioane) cu scrierea append; (b) ar invalida martorii M1–M3 ai S21
     și ar cere protocol propriu; (c) volumul real e mic (≈ 0,9 MB/oră). De asemenea, seria nu e „generată de procesele
     WebKitGTK”: e produsă de firul `ql649-telemetrie` din procesul principal, care citește `/proc` pentru tot arborele.
  4. Comanda `cmd_telemetrie` e cerere/răspuns (IPC Tauri), nu un canal de „trimitere”. „Direct în ecranul grafic” se
     realizează prin interogare periodică din frontend (o singură cerere în zbor), fără canal nou de evenimente în Rust.
  5. „Etichetă standard de stări de energie stabilă”: sintagma nu există în proiect și ar atribui fluxurilor sau
     extragerilor o proprietate fizică pe care nu o au. NU se adoptă ca etichetă. Se afișează eticheta standard reală
     (`LABEL` din `emite.py`), verbatim, plus starea emisiei din LANT (`CERTIFICATA` / `EMISIE_ABSENTA`).
- **Înghețat și neatins:** tot ce e listat în §7 (`frozen_hashes`), inclusiv TOATE sursele `rust_core` în afara celor
  două fișiere permise (deci și `h1_mass.rs`, `h3_aero.rs` 0444, `telemetry.rs`, `main.rs`, `lib.rs`, `style.css`).
  Sigiliile S16–S21 nu se ating. Serverul 8649 nu se repornește. Timerele rămân.

## 1. Decizii de inginerie (autonome, fixate acum)

| ID | Decizie | Motiv |
|---|---|---|
| U1 | Se modifică NUMAI `rust_core/ui/app.js` și `rust_core/ui/index.html` (`chmod u+w` documentat, apoi 0444 la loc). Niciun fișier nou în `rust_core` | Suprafață minimă; Rust, testele și paritatea rămân neschimbate ca sursă |
| U2 | Card nou în `tab-mem`: „Vârfuri telemetrie — afișare grafică (în direct)”, cu `<canvas id="c-tel" width="1180" height="230">` și o legendă `t-graf-nota`. Desenul folosește numai ultimul răspuns `cmd_telemetrie`: 3 rânduri orizontale — (1) Σ VmRSS arbore: bară „ultim” + marcaj „vârf”; (2) Σ VmRSS WebKit*: bară „ultim” + marcaj „vârf” + linie punctată la 30 000 000 B; (3) VmRSS proces principal: bară „vârf”. Scala comună = 1,1 × max(valorile afișate, 30 000 000). Valorile lipsă (`null`) se desenează ca „—”, fără bară | Agregatul S21 are exact aceste câmpuri; fără câmpuri inventate |
| U3 | Reîmprospătarea în direct: un singur lanț `setTimeout` cu perioada P = max(1000, `interval_ms`) ms. Următorul pas se programează numai după rezolvarea cererii precedente (fără suprapuneri). Lanțul pornește la activarea filei „Memorie” și se oprește la schimbarea filei, la `visibilityState ≠ visible` sau când `stare ≠ ACTIV` (după o ultimă desenare) | IPC mărginit; Webview-ul nu lucrează când fila nu se vede |
| U4 | Fără serii în Webview: starea JS a telemetriei are dimensiune fixă (`{timer, ticks, ultim}`), iar `ultim` se înlocuiește la fiecare pas. Codul S22 e delimitat de `// S22-BEGIN` / `// S22-END` și nu conține `.push(`, `.concat(`, `.unshift(`, `.splice(`, `Array(`, `localStorage`, `sessionStorage`, `indexedDB` | Verificabil static (G0) |
| U5 | Eticheta: constanta `ETICHETA_STANDARD` din `app.js` = exact `LABEL` din `emite.py`; afișată în `<p class="legend" id="a-eticheta">` din fila „Filtru admisibilitate”, cu textul: eticheta standard + „starea fiecărui flux este starea curentă a emisiei în LANT (CERTIFICATA / EMISIE_ABSENTA); nu este predicție și nu oferă avantaj de selecție”. Pentru ținta afișată se adaugă numărul de fluxuri certificate / total, din răspunsul `cmd_admisibilitate` existent | Reflectare strictă a stării, fără vocabular nou |
| U6 | Modul `--smoke`: după verificările S21, frontendul activează fila „Memorie” (clic pe buton), așteaptă cel puțin 3 pași în direct (≤ 15 s), oprește lanțul înainte de `cmd_smoke_done` și raportează `grafic` = {`ok`, `ticks`, `esantioane_inceput`, `esantioane_sfarsit`, `randuri_desenate` (3 booleeni: pixeli ne-fundal în banda fiecărui rând, prin `getImageData`), `perioada_ms`} și `eticheta` = {`ok`, `text`} (textul DOM conține exact `ETICHETA_STANDARD`). `toate_ok` include `grafic` și `eticheta` | Martor automat pe fereastra reală |
| U7 | Stilul folosește numai clasele existente din `style.css` (înghețat) și culorile de desen deja folosite în `app.js`; CSP neschimbat (`script-src 'self'`, `style-src 'self'`: nimic inline în HTML) | Fără slăbirea CSP |
| U8 | Copii 0444 în `./ssd_data/RUST_CORE_S22/`: binarul, manifestul, protocolul, sigiliul, raportul, rezultatele și `sursa/rust_core_S22.tar`. Tamponul `QL649_S21_TELEMETRIE/` rămâne cel din S21 (inscriptibil); sesiunile-dovadă se fixează prin SHA-256 | Ca Q11 din S21 |
| U9 | Niciun cod GPU, niciun reglaj WebKit (variabile de mediu, flag-uri, procese) | Nu e scopul S22 |

## 2. Ce garantează schimbarea (și ce nu)

- Garantează: vârfurile din agregatul `cmd_telemetrie` apar grafic în fila „Memorie” și se actualizează în direct; Webview-ul
  nu păstrează serii (G0 static + M5 pe răspuns); seria brută rămâne pe SSD, în formatul S21, verificabilă independent
  (M4); eticheta standard afișată e exact cea din `emite.py` și din emisiile certificate (G0).
- NU garantează și NU promite nicio scădere a RSS-ului WebKit; verdictul Webview 30 MB rămâne FAIL (numai informativ).
  Desenul pe canvas poate adăuga câțiva MB de memorie grafică în WebKitWebProcess; se raportează informativ (Σ VmHWM
  WebKit S22 vs S21), fără prag și fără afirmații.

## 3. Criterii de acceptanță (fixate acum)

- **S0:** ca în §0 (deja PASS). La final: 13 × `drift []` pentru sigiliile existente, plus `drift []` pentru S22;
  `LANT_PREFIX_S20 OK`; `h1_mass.rs`, `h3_aero.rs` cu sha-urile înghețate și mod 0444.
- **S1:** `cargo fmt --check`, `cargo check`, `cargo clippy --all-targets -- -D warnings`, `cargo test` (61 de teste,
  niciunul eliminat sau adăugat), `cargo build --release`, totul cu exit 0 și `--offline`. Toate sursele `.rs`,
  `Cargo.toml`, `Cargo.lock`, `.cargo/config.toml`, `tauri.conf.json`, `capabilities/` sunt byte-identice (manifestul
  S22: `unauthorized_changes: []`, `modified_vs_S21` = exact cele 2 fișiere UI).
- **A1:** `rustc --print cfg -C target-cpu=native` conține `fma` și `avx2`; jurnalul `cargo build --release -v` arată
  `-C target-cpu=native` pentru `rust_singularity_core`.
- **A2:** binarul S21 (copia SSD `f25aad0c…`, rulată prin `install -m 0555` într-un director temporar) și binarul S22
  rulează `parity` pe ACEEAȘI referință (cea mai recentă `REFERINTA_PARITATE_*.json`). Rapoartele sunt identice după
  eliminarea cheilor de timp (amendamentul S20-A01; `verifica_s21.py a2`), plus 587/587.
- **A3:** după `cargo clean --release -p rust-singularity-core` și o compilare nouă, sha-ul binarului S22 e identic.
- **B1:** `admissibility --enumerate` (implicit 2026-10-29): exit 0, 6 certificate, 4/4; rapoartele binarelor S21 și S22
  identice fără câmpurile de timp (`verifica_s21.py b1`).
- **B2:** cât timp emisia din 30 oct nu există, `admissibility --target 2026-11-01` dă 6 × `EMISIE_ABSENTA`
  (`verifica_s20.py b2` PASS). Dacă emisia apare în timpul sesiunii, se aplică B5 din S20 (raportat exact).
- **G0 (static, `tu4/rezultate/S22/verifica_s22.py g0`, Python standard, fără cod Rust):**
  - (a) față de sigiliul S22, numai `app.js` și `index.html` diferă; toate celelalte fișiere `rust_core` (fără `target/`,
    `gen/`) au sha-urile din `frozen_hashes`; ambele fișiere UI sunt 0444 la final;
  - (b) `app.js` conține exact un bloc `// S22-BEGIN` … `// S22-END`, fără `.push(`, `.concat(`, `.unshift(`, `.splice(`,
    `Array(`, `localStorage`, `sessionStorage`, `indexedDB`; `loadTelemetry` nu conține `.push(`;
  - (c) `ETICHETA_STANDARD` din `app.js` == `LABEL` din `emite.py` == `label` din fiecare emisie certificată prin LANT;
  - (d) `index.html` conține `id="c-tel"` în `tab-mem` și `id="a-eticheta"` în `tab-adm`, fără `style=` și fără
    `<script>` inline (numai `src="app.js"`);
  - (e) mulțimea comenzilor invocate în `app.js` == mulțimea comenzilor înregistrate în `main.rs` (10);
  - (f) blocul S22 din `app.js` nu conține „energ” (vocabularul „energie” existent aparține FrFT: energia semnalului,
    Parseval, S19), iar „predic” apare în blocul S22 numai în negația fixată „nu este predicție”.
- **G1 (fereastra reală, `verifica_s22.py g1 <GUI_SMOKE.json>`):** `gui --smoke <fișier>` (DISPLAY-ul sesiunii grafice) dă
  exit 0, `toate_ok: true`; `grafic.ok`, `grafic.ticks ≥ 3`, `grafic.esantioane_sfarsit > grafic.esantioane_inceput`,
  `randuri_desenate` = [true, true, true], `grafic.perioada_ms` = 1000; `eticheta.ok` și `eticheta.text` conține
  `ETICHETA_STANDARD`; răspunsul `cmd_telemetrie` fără tablouri.
- **M4/M5 (regresie S21, `verifica_s21.py m4` și `m5` pe același GUI_SMOKE):** PASS. Verdictul memoriei Webview și
  Σ VmHWM se raportează din nou, **numai informativ**.
- **D1 (regresie):** la final, `tu4/rezultate/S22/primul_pas_S23.sh` (manifestul S22, 14 sigilii) dă integral PASS: EM
  42/42, JU 13/13, 130 passed, 38 + 3s, UI 15/15, `"ok": true`, `SURSE_RUST_OK 27`, 61/61, 587/587, admisibilitate,
  B2 (sau B5), M2, G0, `DL_RC=0`.
- **Verdict:** `S22_PASS` ⇔ S0, S1, A1–A3, B1, B2, G0, G1, M4, M5, D1 PASS. Altfel `S22_PARTIAL` (cu lista exactă) sau
  `S22_FAIL`. Orice FAIL/UNKNOWN ⇒ incident `tu4/incidente/S22_NN/`, cu fișierele încercării păstrate și fără schimbarea
  pragurilor. Reparația e permisă numai pentru conformitatea cu definițiile de mai sus, cu amendament scris înainte.
  Iterațiile de compilare/sintaxă sunt inginerie normală și se raportează în `RAPORT_S22.md`.

## 4. Interpretare fixată acum

PASS înseamnă: fereastra Tauri afișează grafic și în direct vârfurile telemetriei de memorie, fără serii în Webview, cu
seria brută păstrată pe SSD în formatul S21, iar fila de admisibilitate afișează eticheta standard și starea curentă a
emisiilor din LANT. NU înseamnă că Webview-ul folosește mai puțină memorie, că limita de 30 MB e atinsă sau vreo putere
predictivă. Sub urna uniformă reală, toate biletele au aceeași șansă.

## 5. Ținta 2026-11-01

Nicio schimbare de fond: emisia o face `emite.py` prin timer, după decontarea extragerii din 29 oct, sub eticheta standard.
Fereastra afișează doar starea curentă (astăzi 6 × `EMISIE_ABSENTA`). B5 (S20) se rulează în prima sesiune de după emisie.

## 6. Ordinea operațiilor

1. Sigiliul S22 (`code_files_present` = modificările UI încă neîncepute: sha-urile pre = cele din manifestul S21).
2. `chmod u+w` pe cele 2 fișiere (jurnal), editare, `chmod 0444` (jurnal).
3. S1, A1, A3, G0, G1 + M4/M5, A2/B1/B2, manifest, copii SSD, raport, `primul_pas_S23.sh`, D1.
4. Predarea: `predari/OPERATIV.md`, Mesajul 67 integral în `predari/MESAJE_UTILIZATOR_QL649.md`, perechea nouă prin
   `predari/genereaza_predare.py` (neschimbat).

## 7. Fișiere

- NOI permise: `tu4/PROTOCOL_QUANTUM_S22.md`, `tu4/SIGILIU_TU4_S22.json`, `tu4/rezultate/S22/*`,
  `tu4/incidente/S22_*/` (numai la nevoie), `./ssd_data/RUST_CORE_S22/**` (0444), sesiuni noi în
  `./telemetry/**` (tamponul S21, prin fereastră/`monitor`).
- MODIFICATE permis (sha-urile vechi în sigiliu, `chmod u+w` documentat, apoi 0444 la loc): `rust_core/ui/app.js`,
  `rust_core/ui/index.html`.
- ÎNGHEȚATE (în sigiliu):
  - lista S21 `frozen_hashes` (80);
  - artefactele S21: protocolul, sigiliul, raportul, manifestul, `verifica_s21.py`, `manifest_s21.py`,
    `sigileaza_s21.py`, `primul_pas_S22.sh`, jurnalele și rezultatele JSON S21, `SESIUNI_TELEMETRIE_DOVADA.txt`;
  - jurnalul primului pas S22, inventarul S22 și `inventar_s22.py`;
  - TOATE celelalte surse `rust_core` (din manifestul S21) în afara celor 2 fișiere UI: `src/main.rs`, `src/lib.rs`,
    `src/telemetry.rs` + cele deja înghețate.
  - LANT rămâne în `append_only_prefix` (aceleași 3 linii ca în S20/S21); `DECONTARI.jsonl`, `JUDECATOR_RULARI.jsonl`
    și emisiile viitoare NU se îngheață (se schimbă prin tribunal).
- Predarea: `predari/OPERATIV.md`, `predari/MESAJE_UTILIZATOR_QL649.md` (Mesajul 67 adăugat), perechea nouă.
