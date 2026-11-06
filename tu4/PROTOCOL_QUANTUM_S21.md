# PROTOCOL TU4-S21 — monitorizarea asincronă continuă a memoriei totale (RSS-vârf), cu tampon de telemetrie pe SSD-ul extern

Sesiunea S21. Cererea = Mesajul 66 (2026-10-27T22:52:39-04:00 = 2026-10-28T02:52:39Z). Protocolul e scris și sigilat
(`tu4/SIGILIU_TU4_S21.json`) ÎNAINTE de orice modificare a codului din `./rust_core`.
`positive_claims_allowed=false`. Calculul rămâne clasic, pe CPU. Cuvântul „QUANTUM” din numele fișierului vine din cererea
utilizatorului. Nu înseamnă hardware cuantic, avantaj cuantic și nicio proprietate a extragerilor.

## 0. Ce este și ce NU este S21

- **Pornire verificată (S0, deja făcut):**
  - primul pas al predării 20261028T024640Z a ieșit integral PASS: `tu4/rezultate/S21/primul_pas_S21_20261028T025303Z.log`
    (`346384c7…`). Rezultate: 12 × `drift []`, `LANT_PREFIX_S20 OK` (3 linii), EM 42/42, JU 13/13, 130 passed, 38 + 3s,
    UI 15/15, `SURSE_RUST_OK 26`, 54/54 teste Rust, binarul `f2d9d65e…`, paritatea 587/587, admisibilitatea implicită
    2026-10-29 6/6 + 4/4, B2 PASS, `DL_RC=0`;
  - inventarul read-only: `tu4/rezultate/S21/INVENTAR_S21_20261028T025603Z.json` (`51842304…`) și suplimentul
    `INVENTAR_S21_SUPLIMENT_20261028T025618Z.json` (`2b411a16…`). Primul fișier a citit cheile fluxurilor la nivelul greșit
    și a scris `null`; e păstrat neschimbat. Inventarul nu e experiment.
  - Starea constatată: ținta implicită e 2026-10-29 (COMPLETA, 3/3 certificate), iar ținta programată e 2026-11-01
    (`EMISIE_ABSENTA` pe toate cele 6 fluxuri). Fereastra Tauri: `main`, 1280 × 860, CSP strict, `bundle.active=false`, cu
    selector de țintă în `app.js` și fără țintă fixă. Timerul de emisie e zilnic (08:20/12:20/15:20 Europe/Bucharest),
    no-op cât timp ținta e deja emisă.
- **Este:** un modul nou `rust_core/src/telemetry.rs`. Un fir de execuție separat eșantionează periodic memoria întregului
  arbore de procese al ferestrei (procesul principal + toți descendenții, inclusiv WebKitWebProcess/NetworkProcess). Fiecare
  eșantion se scrie imediat, ca o linie JSONL, pe SSD-ul extern, în `./telemetry/`. În memorie
  rămân doar agregatele de dimensiune fixă: numărul eșantioanelor, vârfurile și ultimul eșantion. Interfața primește
  numai aceste agregate, niciodată seria. Există și o subcomandă CLI `monitor` pentru măsurători fără fereastră.
- **NU este:** reducerea memoriei WebKitGTK, model nou, emisie, decontare, reglaj, selecție de bilete, modificare a
  tribunalului Python, a emițătorului, a emisiilor, a timerelor, a interfeței 8649 sau a pistei DL. Rust NU emite și NU
  decontează. Emisia pentru 2026-11-01 o face numai `emite.py`, prin timer, sub eticheta standard.
- **Corecții de premisă (declarate exact):**
  1. Cererea spune că reducerea sub 30 MB „s-a dovedit fizic imposibilă”. Nu s-a dovedit. S20 a MĂSURAT
     (Σ VmHWM WebKit = 265 523 200 B, verdict FAIL) și n-a încercat nicio reducere. Afirmația corectă: o reducere nu a fost
     încercată, iar limita de 30 MB e foarte probabil inaccesibilă cu WebKitGTK. Numai WebKitWebProcess avea 214 MB RSS,
     în mare parte biblioteci partajate. S21 nu încearcă reducerea și nu declară imposibilitatea. Verdictul S20 al memoriei
     (FAIL) rămâne neschimbat.
  2. Tamponul pe SSD **nu micșorează** memoria WebKitWebProcess. Telemetria nu a fost niciodată păstrată în procesul
     Webview: S20 afișa un singur raport, fără istoric. Mecanismul garantează altceva, verificabil: monitorizarea continuă
     nu adaugă memorie care crește în timp, nici în procesul principal (agregate O(1), seria merge direct pe disc), nici în
     Webview (primește doar agregatele, fără serii). Paginile scrise ajung în page cache-ul nucleului, care nu se
     contabilizează în RSS-ul proceselor.
- **Înghețat și neatins:** tot ce e listat în §7 („frozen_hashes”), inclusiv `h1_mass.rs`, `h3_aero.rs`, `parser.rs`
  (0444, sha neschimbate), `resources.rs`, `integrity.rs`, `bridge.rs`, `Cargo.toml`, `Cargo.lock` și
  `.cargo/config.toml`. Sigiliile S16–S20 nu se ating. Serverul 8649 nu se repornește. Timerele rămân.

## 1. Decizii de inginerie (autonome, fixate acum)

| ID | Decizie | Motiv |
|---|---|---|
| Q1 | Fișier NOU `rust_core/src/telemetry.rs`, numai `std` + `serde`/`serde_json` (deja dependențe). Refolosește `resources::{read_proc, descendants, is_webview, verdict}` și `integrity::sha256`. `Cargo.toml`/`Cargo.lock` neschimbate | Zero dependențe noi; aceeași sursă procfs ca S20 §4 |
| Q2 | Asincron = un fir dedicat (`std::thread`, numele `ql649-telemetrie`). Firul UI/IPC nu așteaptă niciodată eșantionarea. `cmd_telemetrie` citește doar agregatul, sub un lacăt scurt | Independent de runtime-ul Tauri/tokio |
| Q3 | Rădăcina implicită este `./telemetry`, iar punctul de montare cerut este `./ssd_data`. Verificarea montării: `st_dev(montare) ≠ st_dev(părinte)`, iar rădăcina trebuie să fie sub punctul de montare. Dacă verificarea eșuează sau scrierea nu e posibilă, starea e `INDISPONIBIL`, cu motiv: niciun fir pornit și **nicio alternativă** (nici alt disc, nici acumulare în RAM) | Fără o cădere tăcută pe discul intern |
| Q4 | Fiecare pornire are directorul ei: `<rădăcină>/<UTC>_pid<P>/`. Segmentele se numesc `telemetrie_000.jsonl`, `_001`, …, iar la oprire se scrie `rezumat.json` | Sesiuni separate, auditabile |
| Q5 | Limite: segmentul are cel mult 16 MiB (16 777 216 B), iar sesiunea cel mult 1 GiB (1 073 741 824 B). O linie nu se împarte niciodată între segmente. Când următoarea linie ar depăși plafonul sesiunii, starea devine `PLAFON_ATINS` și scrierea se oprește. **Nimic nu se șterge automat** | Disc mărginit, fără pierderi ascunse |
| Q6 | Intervalul implicit este 1000 ms în fereastra normală și 100 ms în modul `--smoke`. Domeniul permis e 1…60 000 ms; altfel eroare de configurare. Așteptarea se face în pași ≤ 50 ms, cu verificarea cererii de oprire | Oprire promptă |
| Q7 | Scrierea: un tampon `String` refolosit, apoi `write_all` pe un fișier deschis în mod append, câte o linie per eșantion (fără `BufWriter` care să acumuleze). La oprire: `sync_all` și `rezumat.json` (agregat + segmente cu octeți, linii și SHA-256 citit o singură dată după închidere). O eroare de scriere duce la starea `EROARE_SCRIERE` și la oprire | Persistență imediată, integritate verificabilă |
| Q8 | Tauri: telemetria pornește în `gui()` cu pid-ul propriu. Comanda nouă `cmd_telemetrie` întoarce agregatul fără niciun tablou. La `RunEvent::Exit` (prin `Builder::build(..).run(callback)`): oprire + rezumat. În `--smoke`, `cmd_smoke_done` oprește telemetria înainte de scrierea `GUI_SMOKE_<UTC>.json`, care primește cheia `telemetrie` | Închidere curată, fără pierderea rezumatului |
| Q9 | CLI: `monitor [--pid P] [--interval-ms N] --samples K [--root DIR] [--fara-verificare-montare]`. Implicit `P` = procesul propriu; K între 1 și 10 000 000. Rezumatul JSON merge pe stdout. Exit 0 ⇔ starea finală `COMPLET` (K eșantioane scrise) și rezumatul scris; 1 altfel; 2 la utilizare greșită. `--fara-verificare-montare` există numai pentru rădăcini de test | Măsurători reproductibile fără fereastră |
| Q10 | UI: fila „Memorie” primește blocul „Telemetrie continuă (SSD)”, cu agregatele și calea sesiunii, plus butonul de reîmprospătare existent. JavaScript nu păstrează serii | Webview-ul nu acumulează date |
| Q11 | Copii 0444 în `./ssd_data/RUST_CORE_S21/`: binarul, manifestul, protocolul, sigiliul, raportul și `sursa/rust_core_S21.tar`. Tamponul `QL649_S21_TELEMETRIE/` rămâne inscriptibil (date volatile). Fișierele folosite ca dovezi sunt fixate prin SHA-256 în rezultatele S21 | Ca R10 din S20 |
| Q12 | Niciun cod GPU. Niciun reglaj WebKit (variabile de mediu, flag-uri, procese) | Nu e scopul S21 |

## 2. Definițiile eșantionului (fixate ÎNAINTE de orice măsurare)

Pentru pid-ul monitorizat P, la fiecare eșantion: S = {P} ∪ descendenți(P), din aceeași trecere prin `/proc` (S20 §4).

- `seq`: 1, 2, … (contiguu); `utc`: ISO-8601 Z; `t_ms`: milisecunde monotone de la pornire.
- `n_procese`: câte procese din S au fost citite complet (VmRSS și VmHWM prezente). `citiri_esuate`: câte sunt listate,
  dar dispărute, ilizibile sau fără VmRSS/VmHWM.
- `rss_total` = Σ VmRSS și `hwm_total` = Σ VmHWM, peste procesele citite complet din S. `pss_total` = Σ Pss dacă e
  disponibil pentru toate, altfel `null`.
- `rss_principal`, `hwm_principal` pentru P (`null` dacă P nu se poate citi).
- `webview_rss`, `webview_hwm`, `n_webview`: aceleași sume restrânse la procesele `WebKit*`.
- **Agregatul sesiunii („RSS-vârf”):** `esantioane`; `rss_total_varf` = max `rss_total` (cu `seq_varf` și `utc_varf`);
  `webview_rss_varf` = max `webview_rss`; `rss_principal_varf` = max `rss_principal`; `hwm_total_ultim` și
  `webview_hwm_ultim` din ultimul eșantion; `verdict_webview_30MB_ultim` = verdictul S20 §4 aplicat proceselor WebKit din
  ultimul eșantion (numai raportat); `octeti_scrisi`; `segmente`; `stare`; `motiv`; `director`.
- **Semantică declarată:**
  - `rss_total_varf` e un vârf EȘANTIONAT: vârfurile mai scurte decât intervalul pot scăpa.
  - Σ VmHWM e marginea complementară (vârful fiecărui proces viu, însumat; nu e o măsurare simultană).
  - VmRSS numără paginile partajate de mai multe ori.
  - Stările: `ACTIV`, `COMPLET`, `OPRIT` (oprire cerută), `PLAFON_ATINS`, `EROARE_SCRIERE`, `INDISPONIBIL`.

## 3. Ce garantează mecanismul (și ce nu)

- Garantează că memoria monitorului nu crește cu numărul eșantioanelor (martorul M3), că seria e pe SSD, verificabilă
  independent (M2, M4), că Webview-ul primește numai agregate (M5) și că o lipsă a SSD-ului e semnalată, nu ocolită (M1d).
- NU garantează și NU promite nicio scădere a RSS-ului WebKit. Limita de 30 MB rămâne FAIL până la o eventuală încercare
  separată, cu protocol propriu.

## 4. Criterii de acceptanță (fixate acum)

- **S0:** ca în §0 (deja PASS). La final: 12 × `drift []` pentru sigiliile existente, plus `drift []` pentru S21;
  `LANT_PREFIX_S20 OK`; `h1_mass.rs`, `h3_aero.rs` și `parser.rs` cu sha-urile S19/S20 și mod 0444.
- **S1:** `cargo fmt --check`, `cargo check`, `cargo clippy --all-targets -- -D warnings`, `cargo test` (toate cele 54 de
  teste existente + cele noi, niciunul eliminat), `cargo build --release`, totul cu exit 0 și `--offline`. `Cargo.toml`,
  `Cargo.lock` și `.cargo/config.toml` sunt byte-identice.
- **A1:** `rustc --print cfg -C target-cpu=native` conține `fma` și `avx2`. Jurnalul `cargo build --release -v` arată
  `-C target-cpu=native` pentru `rust_singularity_core`.
- **A2:** binarul S20 (copia SSD `f2d9d65e…`, rulată prin `install -m 0555` într-un director temporar) și binarul S21
  rulează `parity` pe ACEEAȘI referință (cea mai recentă `REFERINTA_PARITATE_*.json`). Rapoartele trebuie să fie identice
  după eliminarea cheilor `run_utc` și a oricărei chei care conține `seconds`, `elapsed`, `micros`, `_ms` sau `secunde`
  (amendamentul S20-A01). În plus, 587/587.
- **A3:** după `cargo clean --release -p rust-singularity-core` și o compilare nouă, sha-ul binarului e identic.
- **B1:** `admissibility --enumerate` (implicit 2026-10-29) dă exit 0, 6 certificate, 4/4. Rapoartele binarelor S20 și
  S21 sunt identice fără `run_utc`.
- **B2:** cât timp emisia din 30 oct nu există, `admissibility --target 2026-11-01` dă 6 × `EMISIE_ABSENTA`
  (`verifica_s20.py b2` PASS). Dacă emisia apare în timpul sesiunii, se aplică B5 din S20 (raportat exact).
- **M1 (teste unitare noi în `telemetry.rs`):**
  - (a) un arbore procfs sintetic dă sume exacte pentru toate câmpurile §2;
  - (b) N eșantioane sintetice dau N linii JSONL valide, `seq` contiguu, iar max-urile recalculate din fișier sunt egale cu
    agregatul;
  - (c) rotația la plafonul segmentului (cu limite mici de test) nu împarte nicio linie, iar plafonul sesiunii dă
    `PLAFON_ATINS` fără ștergeri;
  - (d) o rădăcină care nu e punct de montare dă `INDISPONIBIL`, niciun fișier creat și niciun fir pornit;
  - (e) oprirea cerută cu interval 60 000 ms se încheie în ≤ 2 s, iar SHA-256 din `rezumat.json` e egal cu recalcularea;
  - (f) cu un copil real (`/bin/sleep`) al procesului de test, `n_procese` ≥ 2;
  - (g) intervalele 0 și 60 001 sunt refuzate.
- **M2 (CLI real pe SSD):** `monitor --interval-ms 100 --samples 50` (pid propriu, rădăcina implicită) dă exit 0.
  Verificatorul independent `tu4/rezultate/S21/verifica_s21.py m2` (Python, fără cod Rust) confirmă:
  - directorul e sub `./telemetry/`;
  - Σ linii = 50 și `seq` = 1…50;
  - SHA-256 și octeții segmentelor sunt egali cu `rezumat.json`;
  - `rss_total_varf`, `seq_varf`, `webview_rss_varf` și `rss_principal_varf` sunt egale cu recalcularea;
  - `stare` = `COMPLET`.
- **M3 (memoria monitorului e mărginită):** `monitor --interval-ms 1 --samples 3000`, pid propriu, pe SSD. Criteriul,
  calculat din fișier de `verifica_s21.py m3`:
  max(`rss_principal`, seq 2001…3000) − max(`rss_principal`, seq 501…1000) ≤ 1 048 576 B. Plus verificările M2 pentru
  3000 de linii.
- **M4 (fereastra reală):** `gui --smoke <fișier>` (DISPLAY-ul sesiunii grafice, ca în S20 D1) dă exit 0 și
  `toate_ok: true`, cu toate comenzile vechi + `cmd_telemetrie`. Documentul are `telemetrie.stare` ∈ {`OPRIT`, `COMPLET`},
  `esantioane` ≥ 5 și `n_webview` ≥ 1 în ultimul eșantion. `verifica_s21.py m4` confirmă pe directorul SSD aceleași
  egalități ca la M2 (fără numărul fix de linii; Σ linii = `esantioane`). Verdictul S20 al memoriei (30 MB) și Σ VmHWM se
  raportează din nou, **numai informativ** (așteptat: FAIL). Comparația cu S20 e informativă, fără afirmații.
- **M5 (fără serii în Webview):** răspunsul `cmd_telemetrie` din raportul frontendului nu conține niciun tablou JSON, la
  nicio adâncime (`verifica_s21.py m5`). `app.js` nu are acumulatori pentru telemetrie (inspecție declarată în raport).
- **D1 (regresie):** la final, `tu4/rezultate/S21/primul_pas_S22.sh` (manifestul S21) dă integral PASS: EM 42/42,
  JU 13/13, 130 passed, 38 + 3s, UI 15/15, `"ok": true`, `SURSE_RUST_OK <N>`, toate testele Rust, 587/587, admisibilitate,
  B2, `DL_RC=0`.
- **Verdict:** `S21_PASS` ⇔ S0, S1, A1–A3, B1, B2, M1–M5, D1 PASS. Altfel `S21_PARTIAL` (cu lista exactă) sau
  `S21_FAIL`. Orice FAIL/UNKNOWN ⇒ incident `tu4/incidente/S21_NN/`, cu fișierele încercării păstrate și fără schimbarea
  pragurilor. Reparația e permisă numai pentru conformitatea cu definițiile de mai sus, cu amendament scris înainte.
  Iterațiile de compilare (erori de tip/stil) sunt inginerie normală și se raportează în `RAPORT_S21.md`.

## 5. Interpretare fixată acum

PASS înseamnă: fereastra și CLI-ul pot monitoriza continuu memoria totală a arborelui de procese, cu seria pe SSD-ul
extern, verificabilă independent, iar monitorizarea nu adaugă memorie care crește în timp. NU înseamnă că Webview-ul
folosește mai puțină memorie, că limita de 30 MB e atinsă sau vreo putere predictivă. Sub urna uniformă reală, toate
biletele au aceeași șansă.

## 6. Ținta 2026-11-01

Nicio schimbare: emisia o face `emite.py` prin timer, după decontarea extragerii din 29 oct, sub eticheta standard. B5
(S20) se rulează în prima sesiune de după emisie. Rust doar afișează certificat ce există în LANT.

## 7. Fișiere

- NOI permise: `tu4/PROTOCOL_QUANTUM_S21.md`, `tu4/SIGILIU_TU4_S21.json`, `tu4/rezultate/S21/*`,
  `tu4/incidente/S21_*/` (numai la nevoie), `rust_core/src/telemetry.rs`, `./telemetry/**`
  (tampon inscriptibil), `./ssd_data/RUST_CORE_S21/**` (0444).
- MODIFICATE permis (sha-urile vechi în sigiliu, `chmod u+w` documentat, apoi 0444 la loc): `rust_core/src/main.rs`,
  `rust_core/src/lib.rs`, `rust_core/ui/app.js`, `rust_core/ui/index.html`.
- ÎNGHEȚATE (în sigiliu):
  - lista S20 `frozen_hashes`;
  - artefactele S20: protocolul, sigiliul, raportul, manifestul, incidentul + amendamentul, `verifica_s20.py`,
    `primul_pas_S21.sh`;
  - jurnalul primului pas S21 și inventarele S21;
  - sursele Rust nemodificabile: `.cargo/config.toml`, `src/bridge.rs`, `src/integrity.rs`, `src/resources.rs`,
    `ui/style.css` + toate cele înghețate deja în S20.
  - LANT rămâne în `append_only_prefix` (aceleași 3 linii ca în S20).
- Predarea: `predari/OPERATIV.md`, Mesajul 66 integral în `predari/MESAJE_UTILIZATOR_QL649.md`, perechea nouă prin
  `predari/genereaza_predare.py` (neschimbat).
