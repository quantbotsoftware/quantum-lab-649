# PROTOCOL TU4-S18 „RUST INCEPTION” — nucleul nativ `rust_core` (RUST-SINGULARITY v1.0, schelet de inginerie)

Sesiunea S18, decizia utilizatorului = Mesajul 62 (2026-10-27T20:38:53-04:00 = 2026-10-28T00:38:53Z).
Scris și sigilat (`tu4/SIGILIU_TU4_S18.json`) ÎNAINTE de orice fișier de cod din `./rust_core`.
`positive_claims_allowed=false`. Calcul clasic pe CPU; „quantum”/„spectral” = vocabular matematic (numere complexe,
spectre de matrice hermitiene), fără hardware cuantic sau avantaj cuantic revendicat.

## 0. Ce este și ce NU este S18

- **Este:** un port de INFRASTRUCTURĂ (decizie fixată de utilizator, nu se rediscută): crate Rust nou, parser nativ al
  arhivelor `.jsonl` (6/49, 5/40, Joker) și scheletul matematic al modelelor H1 „MA” și H3 „AD” cu tipuri
  `num_complex::Complex64`.
- **NU este:** model predictiv nou, emisie, decontare, modificare a tribunalului sau a interfeței 8649. Nicio cifră
  din S18 nu este o predicție, un bilet sau un scor. Niciun calcul de model pe arhiva reală în S18 (numai inventarul
  parserului, care este inventariere de date, nu experiment de selecție).
- **Înghețat și neatins:** tot `next_candidate/quantum_lab_649/` în afară de fișierele NOI S18 listate în §6
  (`ip_core.py`, `judecator.py`, `emite.py`, verificatoarele, emisiile din 2026-10-29, `LANT.jsonl`, sigiliile
  TU4/S16/S17, `tu3/ui_tu3.py`, `app.py`, `genereaza_predare.py`, OGLINDA, DL, systemd, SSD-urile existente
  `QL649_*`). Serverul 8649 NU se repornește (nu e necesar). Timerele rămân cum sunt.

## 1. Decizii de inginerie (autonome, fixate acum)

| ID | Cerere | Decizie | Motiv |
|---|---|---|---|
| R1 | Cargo Workspace în `rust_core/` | `rust_core/Cargo.toml` = manifestul de producție cerut, VERBATIM (pachet `rust-singularity-core` 1.0.0, ed. 2021, cele 6 dependențe, profilul release), plus tabela `[workspace]` (rădăcină de workspace cu un membru, pachetul însuși) și țintele `[lib]`/`[[bin]]` | Cerința „workspace” și manifestul `[package]` dat sunt compatibile numai așa; nicio dependență adăugată |
| R2 | `tauri = "2.0"` | Păstrat ca dependență (compilat și verificat), FĂRĂ fereastră/aplicație în S18 | O aplicație Tauri cere `tauri-build`, `tauri.conf.json` și un frontend — neincluse în lista strictă de dependențe; GUI = sesiune viitoare cu protocol propriu |
| R3 | `tokio::fs` + `memmap2` | Deschidere și metadate asincron prin `tokio::fs`; maparea `memmap2::Mmap` (read-only) și scanarea la nivel de octet într-un `spawn_blocking` | `mmap` este sincron prin natura lui; blocarea runtime-ului async este evitată corect astfel |
| R4 | „direct de pe SSD-ul de 1.8 TB” | Parserul acceptă ORICE cale. Arhivele LIVE actuale stau pe NVMe intern (`/`); pentru demonstrație se copiază cele 3 fișiere ale versiunii LIVE curente într-un director NOU `./ssd_data/RUST_CORE_S18/date/` (hash verificat byte-identic) și se parsează de acolo și din original | SSD-ul este `/dev/sda1` (USB), nu NVMe; nu se mută și nu se modifică nimic existent |
| R5 | `struct Extraction` „imună la memory-leak” | `Extraction` = valoare `Copy` de dimensiune fixă (`[u8; 6]` + lungime + bila Joker opțională + dată + joc), fără heap; mapa se eliberează la ieșirea din funcție (RAII). Deserializarea bilelor se face cu un vizitor serde fără alocare | Proprietatea Rust garantează eliberarea; NU afirmăm „zero memorie” în sens absolut |
| R6 | Complex64 „eliminarea erorilor de rotunjire pe Tensor Blackwell” | Complex64 = pereche IEEE-754 binary64. Erorile de rotunjire sunt MĂRGINITE și MĂSURATE (reziduul hermitic, ortonormalitatea bazei, Parseval), NU eliminate; sumele folosesc compensarea Neumaier. Numărările de bază sunt întregi exacte (`u64`). Niciun cod GPU/Tensor în S18 | Onestitate numerică: GPU-urile consumer Blackwell au FP64 redus; nu promitem ce nu e demonstrat |
| R7 | „Schițarea logicii spectrale urne” | `h1_mass.rs` și `h3_aero.rs` = portul STRUCTURAL al formulelor deja sigilate (PROTOCOL_TU4_IP_H1_MA / H3_AD, `ip_core.logw_h1` / `logw_h3`, la t = momentul curent, N2 = N), plus matricea de corelație pe perechi (hermitiană, Complex64) și spectrul DFT pe etichete. Testate NUMAI pe fixturi sintetice | Paritatea numerică cu `ip_core.py` și orice rulare pe arhiva reală = protocol separat (S19+), deoarece ar fi o nouă rulare a unui model |
| R8 | `cargo check` / `cargo build` | Se rulează `cargo check`, `cargo test`, `cargo build --release`; jurnalele în `tu4/rezultate/S18/` | Verificare reproductibilă |

## 2. Specificația parserului (`rust_core/src/parser.rs`)

- Intrare: fișier `.jsonl`, câte un obiect JSON pe linie. Două scheme acceptate:
  (A) `tu3`/LIVE: `game` ∈ {`"649"`,`"540"`,`"joker"`}, `draw_date`, `numbers`, `joker`, `draw_kind`, `draw_key`;
  (B) `probe_date` 6/49: fără `game`, cu `numbers_sorted`, `draw_date`, `draw_key` cu prefixul `649:`.
- Jocul: `game`, altfel prefixul `draw_key` până la `:`, altfel indiciul apelantului; altfel linia e respinsă.
- Validare: 6/49 → 6 numere distincte în 1..49, fără bilă; 5/40 → 6 numere distincte în 1..40, fără bilă;
  Joker → 5 numere distincte în 1..45 și bila Joker în 1..20. Data `AAAA-LL-ZZ` validă (lună 1..12, zi 1..31).
  Numerele se sortează crescător. Liniile goale (inclusiv `\r\n` final) se ignoră; orice altă linie invalidă se
  RESPINGE cu numărul liniei și motivul (nu se repară, nu se ghicește).
- Ieșire: `ParsedArchive { path, bytes, lines, records: Vec<Extraction>, rejects: Vec<Reject> }` + rezumat
  (număr pe joc, prima/ultima dată, ultima cheie, ordinea datelor nedescrescătoare: da/nu).
- Binarul `rust-singularity-core inventory <căi…>` încarcă fișierele concurent (`tokio::task::JoinSet`) și scrie un
  rezumat JSON. Fără scrieri în afara stdout.

## 3. Specificația modelelor (schelet, fără emisie)

Notații din protocolul sigilat TU4-IP: n etichete, k bile/extragere, p = k/n, c_i numărări, N extrageri.
- **H1 „MA”:** θ̂_i = (n−1)/n · (c_i/N − p)/(p(1−p)); X² = (n−1)/n · Σ(c_i − Np)²/(N p(1−p)); λ = max(0, 1 − (n−3)/X²)
  (X² = 0 ⇒ λ = 0); ln ŵ = λ θ̂.
- **H3 „AD”:** b_m(i) = √(2/n) cos(π m (i − ½)/n), m = 1..K, K = 4; z_i = √((n−1)/n)(c_i − Np)/√(N p(1−p));
  X²_s = Σ_m (b_m·z)²; θ̂_s = Σ_m b_m (b_m·θ̂); λ_s = max(0, 1 − (K−2)/X²_s); ln ŵ = λ_s θ̂_s.
- **Corelația pe perechi (Complex64, hermitiană):** R_ij = (P_ij/N − (c_i/N)(c_j/N)) / (p(1−p)), cu P_ii = c_i,
  P_ij = numărul extragerilor care conțin i și j. Diagnostic: max|R − R†|, urma, forma pătratică pe modurile H3.
- **Spectrul DFT pe etichete:** Z_m = n^{-1/2} Σ_i z_i e^{−2π i m (i−1)/n}; verificare Parseval Σ|Z_m|² = Σ z_i².

## 4. Criterii de acceptanță (fixate acum)

- A1 `cargo check` exit 0 (cu `tauri` 2.x rezolvat din crates.io).
- A2 `cargo test` exit 0, toate testele trec; minim: 2 scheme, cele 3 jocuri, respingeri (duplicat, interval, lungime,
  dată, joc necunoscut, JSON corupt), fișier gol, CRLF; H1 uniform ⇒ λ = 0 și ln ŵ = 0; H1 pe fixtură față de forma
  închisă (|Δ| ≤ 1e-12); baza H3 ortonormală și ortogonală pe 1 (|Δ| ≤ 1e-12); R hermitiană exact (reziduu 0) și
  urma = Σ var normalizat; Parseval (|Δ| ≤ 1e-9 relativ).
- A3 `cargo build --release` exit 0.
- A4 inventarul pe cele 3 fișiere LIVE ale versiunii curente `versiuni/c692296dd1f6`: 0 respingeri și numărări egale
  cu `CURRENT_LIVE.json` (649 = 2597, 540 = 2490, Joker = 2202), ultimele chei identice; idem pe copiile din SSD.
- A5 zero drift: cele 9 sigilii (FR, IP, EM, EM_COD, JU, JU_COD, UI, S16, S17) `drift []` după S18; emisiile din
  2026-10-29 și `ip_core.py` cu hash-urile neschimbate.
- Verdict: `S18_RUST_INCEPTION_PASS` dacă A1–A5 trec; altfel `S18_RUST_INCEPTION_FAIL` cu motivul, publicat fără
  rescriere. Orice eroare de compilare corectată înainte de verdict se raportează în `RAPORT_S18.md` (iterația de
  compilare este inginerie normală, nu schimbă §2–§4).

## 5. Ce urmează (nu în S18)

S19+: protocol de paritate numerică Rust ↔ `ip_core.py` (pe fixturi, apoi pe arhivă), protocol GUI Tauri
(fereastră, `tauri.conf.json`, frontend), eventual nucleu GPU — fiecare cu protocol + sigiliu înaintea codului.
Tribunalul Python și decontarea de joi 2026-10-29 rămân autoritatea; Rust NU emite și NU decontează.

## 6. Fișiere NOI permise în S18

`tu4/PROTOCOL_RUST_INCEPTION.md`, `tu4/SIGILIU_TU4_S18.json`, `tu4/rezultate/S18/*`, `./rust_core/**`
(cu `target/` ignorat), `./ssd_data/RUST_CORE_S18/**`, plus actualizările de predare
(`predari/OPERATIV.md`, Mesajul 62 în `predari/MESAJE_UTILIZATOR_QL649.md`, perechea nouă prin
`predari/genereaza_predare.py`).
