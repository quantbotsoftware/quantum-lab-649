# PROTOCOL TU4-S20 — compilare nativă (target-cpu=native), ținta 2026-11-01 în filtrul S17 + fereastra Tauri, măsurarea RSS a Webview-ului

Sesiunea S20. Cererea inițială = Mesajul 64 (2026-10-27T22:06:15-04:00 = 2026-10-28T02:06:15Z). Agentul NU a
executat-o ca atare (vezi §0). Decizia utilizatorului = Mesajul 65 (2026-10-27T22:19:05-04:00 = 2026-10-28T02:19:05Z),
care aprobă exact variantele (a), (b) și (c) propuse de agent și cere ca H1/H3 și sigiliul S19 să rămână intacte.
Acest protocol este scris și sigilat (`tu4/SIGILIU_TU4_S20.json`) ÎNAINTE de orice modificare a codului din
`./rust_core`. `positive_claims_allowed=false`. Calculul rămâne clasic, pe CPU, IEEE-754 binary64.
Numele fișierului („QUANTUM”) vine din cererea utilizatorului. Nu înseamnă hardware cuantic, avantaj cuantic sau fizică
aplicată extragerilor.

## 0. Ce este și ce NU este S20

- **Este:**
  - (a) compilarea întregului workspace cu `-C target-cpu=native` (`rust_core/.cargo/config.toml`) și manifestul nou al
    binarului;
  - (b) amendamentul S20-T01 (§3): filtrul de admisibilitate S17 nativ și fereastra Tauri nu mai sunt fixate pe ținta
    2026-10-29. Ținta se rezolvă din `tu4/tribunal/LANT.jsonl`, cu certificarea SHA-256 a fiecărei emisii, iar ținta
    următoare programată (2026-11-01) apare explicit;
  - (c) măsurarea exactă, prin procfs, a memoriei rezidente (RSS) a proceselor Webview (WebKitGTK) ale ferestrei Tauri,
    cu verdict PASS/FAIL/UNKNOWN față de limita de 30 MB din Mesajul 64.
- **NU este:** model nou, emisie, decontare, reglaj, selecție de bilete, modificare a tribunalului Python, a emițătorului,
  a emisiilor, a interfeței 8649 sau a pistei DL. Rust NU emite și NU decontează. Nicio cifră din S20 nu este o
  predicție.
- **Respins din Mesajul 64 (motivat, fără cod):**
  - holonomii Ashtekar–Barbero / rețele de spin pentru Navier–Stokes;
  - polinoame Jones pentru cuplajul Joker;
  - operatori de vârf chirali care „anulează anomalii Green–Schwarz în L2-ul GPU”;
  - coomologie Floer 4D pe octeți mapați cu `memmap2`;
  - „densități Wheeler–DeWitt” pentru bilete;
  - `panic!` la |Δ| > 1e-15.

  Niciunul nu are o definiție matematică aplicabilă acestor date. O implementare ar purta doar numele, fără conținutul,
  ceea ce AGENTS.md interzice („Quantum” se declară exact). Toleranța 1e-15 este sub erorile de rotunjire deja măsurate
  (S19: max |Δ| = 2,27e-13), deci ar produce panică pe date reale. Marginea informațională W4 (S16) rămâne valabilă.
- **Înghețat și neatins:** tot ce e listat în §7 („frozen_hashes” din sigiliu), inclusiv `rust_core/src/models/h1_mass.rs`,
  `h3_aero.rs`, `parser.rs`, `rustfmt.toml` (0444, aceleași sha ca în S19), plus toate modulele S19 nemenționate la
  „modificate”. Sigiliul S19 nu se atinge. Serverul 8649 nu se repornește. Timerele rămân.

## 1. Decizii de inginerie (autonome, fixate acum)

| ID | Cerere | Decizie | Motiv |
|---|---|---|---|
| R1 | FMA/AVX2 nativ | Fișier NOU `rust_core/.cargo/config.toml` cu `[build] rustflags = ["-C", "target-cpu=native"]`. Nimic altceva nu se schimbă în profilul de compilare: `Cargo.toml` rămâne byte-identic (opt-level 3, `lto = true`, codegen-units 1, panic abort sunt deja acolo din S18) | Cerința (a). Pe i7-14650HX, `native` activează AVX2, FMA, BMI2 etc. (fără AVX-512) |
| R1-decl | Ce face și ce NU face R1 | Rust/LLVM NU contractă `a*b + c` în FMA fără `mul_add` explicit, deci semantica IEEE este păstrată. Codul nu folosește `mul_add`, așa că rezultatele numerice trebuie să rămână bit-identice. Vectorizarea poate folosi registrele AVX2 acolo unde nu schimbă rezultatul. Funcțiile libm din glibc aleg oricum variantele FMA la rulare, independent de acest flag. Câștigul de viteză NU este promis; se raportează o singură măsurare fără prag. Binarul devine neportabil pe procesoare fără aceste extensii | Declarare exactă, fără promisiuni |
| R2 | Manifestul nou | `tu4/rezultate/S20/MANIFEST_RUST_CORE_<UTC>.json`: sha-urile tuturor surselor (inclusiv `.cargo/config.toml` și fișierele noi), sha/mărimea binarului release, toolchain-ul, rustflags, lista „frozen_rust_unchanged”, „modified_vs_S19”, „new_in_S20”, „unauthorized_changes” | Primul pas S21 verifică sursele față de acest manifest |
| R3 | SHA-256 în Rust | Fișier NOU `rust_core/src/integrity.rs`: SHA-256 conform FIPS 180-4, implementat propriu (zero dependențe noi, `Cargo.toml`/`Cargo.lock` neschimbate), plus certificarea emisiilor față de `LANT.jsonl` | Certificarea emisiei înaintea afișării; vectorii NIST ca martori |
| R4 | Ținta | Amendamentul S20-T01 (§3) | Cerința (b) |
| R5 | Măsurarea memoriei | Fișier NOU `rust_core/src/resources.rs` (numai `std`, Linux procfs), cu definițiile din §4 | Cerința (c) |
| R6 | Comenzi Tauri noi | `cmd_tinte` (lista țintelor certificate + ținta programată) și `cmd_memorie` (raportul §4 pentru procesul curent). `cmd_admisibilitate` primește ținta (implicit = ultima țintă COMPLETĂ). Celelalte comenzi rămân neschimbate | Comenzi subțiri peste funcții de bibliotecă testate |
| R7 | CLI | Subcomenzi noi: `admissibility [--root D] [--target T] [--enumerate]` (raport JSON; cu `--enumerate`, fiecare flux activ este verificat prin enumerare completă: același top, același bilet admisibil, același rang; exit 0 numai dacă totul e consistent) și `memory [--pid P]` (raportul §4). `inventory`, `parity`, `gui` rămân neschimbate | Verificarea țintei 2026-11-01 după emisia de vineri, fără fereastră |
| R8 | Frontend | `ui/`: selector de țintă în fila „Filtru admisibilitate” și filă nouă „Memorie”. În modul `--smoke` se apelează în plus `cmd_tinte`, `cmd_admisibilitate` pentru fiecare țintă listată și `cmd_memorie` | Transparență; testul de fum acoperă comenzile noi |
| R9 | GPU | Niciun cod GPU în S20 (motivul S19 Q9 rămâne valabil) | Niciun calcul nu trece criteriul `ACCELERARE_GPU.md` |
| R10 | Persistență SSD | Copii 0444 ale binarului, manifestului, rapoartelor și sursei (`tar`) în `./ssd_data/RUST_CORE_S20/` | Ca în S19 Q11 |

## 2. Aritmetica și reproductibilitatea (martorii pentru R1)

- **A1:** `rustc --print cfg -C target-cpu=native` conține `target_feature="fma"` și `target_feature="avx2"`, iar
  jurnalul `cargo build --release -v` arată `-C target-cpu=native` la compilarea crate-ului `rust_singularity_core`.
- **A2 (invarianță numerică):** binarul S19 (copia de pe SSD, `f63ea21a…`) și binarul S20 rulează `parity` pe ACEEAȘI
  referință (`tu4/rezultate/S19/REFERINTA_PARITATE_20261028T022132Z.json`, produsă de primul pas al acestei sesiuni). Cele
  două rapoarte JSON trebuie să fie identice după eliminarea câmpurilor de timp: cheile `run_utc` și orice cheie care
  conține `seconds`, `elapsed`, `micros` sau `_ms`. În plus, 587/587 PASS.
- **A3 (reproductibilitate):** după `cargo clean --release -p rust-singularity-core` și o nouă compilare release, sha-ul
  binarului este identic.
- **A4 (numai raportat):** numărul instrucțiunilor FMA (`vfmadd*`, `vfmsub*`, `vfnmadd*`, `vfnmsub*`) din `objdump -d`
  pentru ambele binare, mărimile lor și câte o măsurare de timp `parity` pentru fiecare (o rulare, nu benchmark).

## 3. AMENDAMENTUL S20-T01 — ținta filtrului S17 și a ferestrei Tauri

Amendează deciziile S19 Q3/Q7 (ținta fixă `DEFAULT_TARGET = "2026-10-29"` din `src/bridge.rs` și `tinta: "2026-10-29"`
din `ui/app.js`). `tu4/s17_admisibil.py` (sigilat în S17/S19, `TARGET` = 2026-10-29) NU se modifică. Pentru ținte noi,
echivalența dintre filtrul nativ și S17 se sprijină pe B7 din S19 (reproducere exactă a celor 6 fluxuri), iar fiecare
flux activ este verificat prin enumerare completă (R7).

- **T1 (validarea țintei):** formatul trebuie să fie exact `AAAA-LL-ZZ` (10 caractere ASCII, cifre și cratime), cu o dată
  calendaristică validă (an bisect gregorian). Ziua săptămânii trebuie să fie joi sau duminică, regula `WEEKDAYS = (3, 6)`
  din `tu4/emite.py`, calculată prin aritmetică civilă exactă, fără fus orar. Altfel: eroare. Ținta nu poate conține
  separatori de cale.
- **T2 (lista țintelor, `tinte`):** din `LANT.jsonl` se grupează liniile pe `target_date`. O țintă este COMPLETA dacă
  cele 3 jocuri (649, 540, joker) au câte o linie, iar fișierul fiecăruia există și are sha-ul din linie. Altfel e
  PARTIALA (cu motivul). Ținta programată = prima dată strict după ultima țintă din LANT care este joi sau duminică
  (din 2026-10-29 rezultă 2026-11-01). Starea ei: EMISIE_ABSENTA dacă nu are linii în LANT. Ținta implicită = ultima
  țintă COMPLETA. Fără nicio țintă COMPLETA: eroare.
- **T3 (certificarea emisiei):** pentru fiecare joc al țintei se citesc o singură dată octeții fișierului
  `tu4/tribunal/emisii/<joc>/<țintă>.json`. Se calculează SHA-256 (R3). Trebuie să existe în LANT o linie cu același
  `game`, `target_date` și `sha256`, iar câmpurile `game` și `target_date` din emisie (dacă există) trebuie să coincidă.
  Calculul filtrului se face pe ACEIAȘI octeți. Orice nepotrivire: eroare, fără afișare. Dacă fișierul lipsește și
  jocul nu are linie în LANT pentru țintă, ambele fluxuri (H1, H3) ale jocului au starea `EMISIE_ABSENTA`, fără
  calcul. Dacă fișierul lipsește, dar jocul are linie în LANT: eroare (lanț inconsistent).
- **T4:** nicio scriere pe disc, nicio emisie, nicio intrare în judecător. Nota de afișare S17 rămâne: „strat de
  AFIȘARE … sub urna uniformă toate biletele au aceeași șansă; nu este sfat de joc”.

## 4. Măsurarea memoriei Webview (definiții fixate ÎNAINTE de orice măsurare)

- **Sursa:** `/proc/<pid>/status` (`Name`, `PPid`, `VmRSS`, `VmHWM`, în kB = 1024 B) pentru procesul principal și pentru
  toți descendenții lui (arborele construit din `PPid`, prin parcurgerea `/proc`). Opțional `Pss` din
  `/proc/<pid>/smaps_rollup`, raportat fără prag (poate lipsi).
- **Procese Webview:** descendenții al căror `Name` începe cu `WebKit` (WebKitWebProcess, WebKitNetworkProcess,
  WebKitGPUProcess; `comm` trunchiat la 15 caractere).
- **Limita:** L = 30 MB = **30 000 000 B** (SI, varianta mai strictă decât 30 MiB).
- **Verdictul memoriei Webview:**
  - UNKNOWN dacă procfs nu este disponibil, dacă nu există niciun descendent WebKit sau dacă `VmHWM`/`VmRSS` nu se
    poate citi pentru vreunul dintre ei;
  - altfel PASS ⇔ Σ VmHWM(WebKit) ≤ L (vârful fiecărui proces, însumat; implică Σ VmRSS ≤ L);
  - altfel FAIL.

  Se raportează și Σ VmRSS, Σ Pss, RSS/HWM ale procesului principal și lista per proces.
- **Momentul măsurării în testul de fum:** în `cmd_smoke_done`, de partea Rust (nu din JavaScript), după ce frontendul a
  apelat toate comenzile și a desenat toate filele. Raportul intră în `GUI_SMOKE_<UTC>.json` la cheia
  `memorie_webview`.
- **Interpretare fixată acum:** VmRSS include paginile partajate (biblioteci WebKitGTK/GTK mapate). S20 MĂSOARĂ, nu
  optimizează: nu se fac reglaje ca să treacă limita. Un FAIL este un rezultat publicat, nu un defect de implementare. O
  eventuală reducere a memoriei = protocol separat.

## 5. Criterii de acceptanță (fixate acum)

- **S0 integritate:** primul pas al predării 013816Z rulat înaintea protocolului, integral PASS (jurnalul
  `tu4/rezultate/S20/primul_pas_S20_20261028T022038Z.log`). La final: 11 × `drift []` pentru sigiliile existente plus
  `drift []` pentru S20; `h1_mass.rs`, `h3_aero.rs`, `parser.rs`, `rustfmt.toml` cu sha-urile din S19 și mod 0444.
- **S1 compilare:** `cargo fmt --check`, `cargo check`, `cargo clippy --all-targets -- -D warnings`, `cargo test` (cele 41
  de teste S19 + cele noi), `cargo build --release` → 0, `--offline`, cu `.cargo/config.toml` activ. `Cargo.toml` și
  `Cargo.lock` byte-identice cu S19.
- **A1–A3** ca în §2 (A4 numai raportat).
- **B1 (ținta 2026-10-29):** `admissibility --target 2026-10-29` dă 6 fluxuri certificate (T3) cu `stare`,
  `top_ticket`, `bilet_afisare`, `rang`, `noduri_heap` identice cu `tu4/rezultate/S17/BILETE_ADMISIBILE_20261028T001924Z.json`
  (`top_ticket_emis`, `bilet_afisare`, `rang`, `noduri_heap`, `stare`) și |Δ ln(q/u)| ≤ 1e-12. Cu `--enumerate`:
  exit 0.
- **B2 (ținta 2026-11-01, acum):** `tinte` listează 2026-10-29 = COMPLETA (implicită) și 2026-11-01 = programată,
  EMISIE_ABSENTA. `admissibility --target 2026-11-01` dă 6 fluxuri `EMISIE_ABSENTA`, fără eroare.
- **B3 (refuzuri):** formate invalide (`2026-11-1`, `../x/2026`, `2026-02-30`, șir gol), zi greșită (`2026-10-30`),
  emisie cu sha absent din LANT, nepotrivire game/target, fișier lipsă pentru o linie LANT existentă → eroare. Testele
  folosesc rădăcini sintetice temporare.
- **B4 (SHA-256):** vectorii FIPS 180-2/NIST: `""`, `"abc"`, mesajul de 448 de biți
  `"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"`, 1 000 000 × `'a'`, plus egalitatea cu sha-urile din LANT
  pentru cele 3 emisii reale.
- **B5 (AMÂNAT, acum UNKNOWN, nu PASS):** după emisia de vineri 30 oct, `admissibility --target 2026-11-01 --enumerate`
  → exit 0, 6 fluxuri certificate. Se rulează în prima sesiune de după emisie.
- **C1 (implementarea măsurării):** teste unitare pe texte `status` sintetice (parsare, kB → B, câmpuri lipsă →
  UNKNOWN); granița verdictului (Σ HWM = L → PASS, L + 1 → FAIL, fără WebKit → UNKNOWN); arborele de procese găsește un
  copil real lansat de test (`/bin/sleep`); `memory` pe procesul curent: RSS > 0 și HWM ≥ RSS.
- **C2 (măsurarea reală):** testul de fum produce `memorie_webview` cu verdict PASS sau FAIL (nu UNKNOWN), cu cel puțin
  un proces WebKitWebProcess găsit. **Verdictul memoriei (PASS/FAIL) se raportează separat și NU schimbă verdictul S20.**
  Un UNKNOWN face C2 = UNKNOWN.
- **D1 (Tauri):** binarul release pornește fereastra cu `gui --smoke <fișier>`. Toate comenzile (vechi + `cmd_tinte`,
  `cmd_admisibilitate` pentru fiecare țintă listată, `cmd_memorie`) răspund fără eroare, `toate_ok: true`, exit 0. Dacă
  fereastra nu poate porni: UNKNOWN.
- **D2 (regresie):** după S20, rerularea primului pas (EM 42/42, JU 13/13, 130 passed, 38 + 3s, UI 15/15, `"ok": true`),
  paritatea 587/587 cu binarul S20, DL exit 0, emisiile și `ip_core.py` neschimbate.
- **Verdict:** `S20_PASS` ⇔ S0, S1, A1–A3, B1–B4, C1, C2, D1, D2 PASS (B5 rămâne amânat și declarat). Altfel
  `S20_PARTIAL` (cu lista exactă) sau `S20_FAIL`. Orice FAIL/UNKNOWN al acestor criterii ⇒ incident
  `tu4/incidente/S20_NN/`, cu fișierele încercării păstrate și fără schimbarea pragurilor. Reparația e permisă numai
  pentru conformitatea cu definițiile de mai sus, cu amendament scris înainte. Iterațiile de compilare (erori de
  tip/stil) sunt inginerie normală și se raportează în `RAPORT_S20.md`.

## 6. Interpretare fixată acum

PASS înseamnă: binarul nativ calculează aceleași numere ca binarul S19, filtrul S17 se poate afișa certificat pentru
orice țintă din LANT, iar memoria Webview este măsurată exact și raportată. NU înseamnă nicio putere predictivă. Sub
urna reală uniformă, toate biletele au aceeași șansă. Un verdict FAIL al memoriei înseamnă doar că fereastra WebKitGTK
depășește 30 MB.

## 7. Fișiere

- NOI permise: `tu4/PROTOCOL_QUANTUM_S20.md`, `tu4/SIGILIU_TU4_S20.json`, `tu4/rezultate/S20/*`,
  `tu4/incidente/S20_*/` (numai la nevoie), `rust_core/.cargo/config.toml`, `rust_core/src/integrity.rs`,
  `rust_core/src/resources.rs`, `./ssd_data/RUST_CORE_S20/**`.
- MODIFICATE permis (sha-urile vechi în sigiliu, `chmod u+w` documentat, apoi 0444 la loc): `rust_core/src/main.rs`,
  `rust_core/src/lib.rs` (declarațiile modulelor noi), `rust_core/src/bridge.rs`, `rust_core/ui/index.html`,
  `rust_core/ui/app.js`, `rust_core/ui/style.css`.
- ÎNGHEȚATE (în sigiliu): lista S19 `frozen_hashes` fără `tu4/tribunal/LANT.jsonl`. LANT este un lanț append-only:
  emisia de vineri adaugă linii. Sigiliul S20 îngheață prefixul lui (cele 3 linii existente, sha pe octeți) în câmpul
  separat `append_only_prefix`. Mai sunt înghețate artefactele S19 (protocol, sigiliu, referința Python, raport,
  manifest, paritatea finală, incidentul S19_01) și sursele Rust nemodificabile: `Cargo.toml`, `Cargo.lock`,
  `.gitignore`, `build.rs`, `tauri.conf.json`, `capabilities/default.json`, `icons/icon.png`, `rustfmt.toml`,
  `src/parser.rs`, `src/models/{mod,fisher,h1_mass,h3_aero,parity,spectral}.rs`,
  `src/models/spectral/{frft,admissible}.rs`.
- Notă: sigiliile S16–S19 conțin `LANT.jsonl` în `frozen_hashes`. După emisia de vineri, verificarea lor de drift va
  raporta `tu4/tribunal/LANT.jsonl`, comportament de proiectare al lanțului append-only, nu o modificare neautorizată.
  Se raportează exact, cu verificarea prefixului S20.
- Predarea: `predari/OPERATIV.md`, Mesajele 64 și 65 integral în `predari/MESAJE_UTILIZATOR_QL649.md`, perechea nouă
  prin `predari/genereaza_predare.py` (neschimbat).
