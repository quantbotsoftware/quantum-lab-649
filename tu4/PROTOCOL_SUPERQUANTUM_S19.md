# PROTOCOL TU4-S19 „SUPERQUANTUM” — paritate Rust ↔ Python înghețat, strat Tauri v2, FrFT + filtrul de admisibilitate nativ

Sesiunea S19, decizia utilizatorului = Mesajul 63 (2026-10-27T21:01:40-04:00 = 2026-10-28T01:01:40Z).
Scris și sigilat (`tu4/SIGILIU_TU4_S19.json`) ÎNAINTE de orice modificare de cod în `./rust_core` și
înaintea scriptului de referință Python. `positive_claims_allowed=false`. Calcul clasic pe CPU, IEEE-754 binary64;
„quantum”, „spectral”, „densitate” = vocabular matematic (numere complexe, matrice hermitiene, operator densitate în
sensul algebrei liniare), fără hardware cuantic sau avantaj cuantic revendicat.

## 0. Ce este și ce NU este S19

- **Este:** (a) verificarea încrucișată numerică a nucleului Rust față de codul Python ÎNGHEȚAT (`tu4/ip_core.py`
  `ab3e1de9…`, plus ieșirile deja sigilate ale `tu4/emite.py` din cele 3 emisii pentru 2026-10-29 și ale
  `tu4/s17_admisibil.py`); (b) asamblarea stratului Tauri v2 (`build.rs`, `tauri.conf.json`, comenzi
  `#[tauri::command]` în `src/main.rs`, frontend static ușor); (c) transformata Fourier fracționară discretă
  (Candan–Kutay–Ozaktas) și filtrul de admisibilitate S17 („pur liniar” = progresie aritmetică) implementate nativ în
  modulul spectral, pe bilete reprezentate ca măști de biți `u64`.
- **NU este:** model nou, emisie, decontare, reglaj, modificare a tribunalului, a emițătorului, a emisiilor sau a
  interfeței 8649. Rust NU emite și NU decontează; tribunalul Python rămâne autoritatea. Nicio cifră din S19 nu este o
  predicție. Rularea formulelor H1/H3 înghețate pe arhiva LIVE curentă este numai PARITATE (aceleași formule, aceleași
  numărări ca emisiile deja sigilate), nu selecție și nu un test nou.
- **Înghețat și neatins:** tot ce e listat în §7 (`ip_core.py`, `judecator.py`, `emite.py`, verificatoarele, emisiile,
  `LANT.jsonl`, sigiliile TU4/S16/S17/S18, `s16_martori.py`, `s17_admisibil.py`, `tu3/ui_tu3.py`, `app.py`,
  `genereaza_predare.py`, OGLINDA, DL, systemd, `QL649_*` pe SSD). Serverul 8649 nu se repornește. Timerele rămân.

## 1. Decizii de inginerie (autonome, fixate acum)

| ID | Cerere | Decizie | Motiv |
|---|---|---|---|
| Q1 | Modificarea `Cargo.toml` (0444) | Amendament prin acest protocol: `chmod u+w` documentat, apoi 0444 la loc. Blocul de producție S18 rămâne VERBATIM; se ADAUGĂ la final numai `[build-dependencies] tauri-build = "2"` și `[features] default = ["custom-protocol"]`, `custom-protocol = ["tauri/custom-protocol"]`. Nicio altă dependență | `tauri-build` e cerut explicit; `custom-protocol` face ca binarul release să servească frontendul încorporat (fără server de dezvoltare) |
| Q2 | Parsarea exactă a referinței | Referința Python scrie fiecare `float` și ca `float.hex()`; Rust îl decodează EXACT cu un parser hexazecimal propriu (fără funcția `float_roundtrip`, deci fără modificarea liniei `serde_json`) | Comparația bit-cu-bit e posibilă; valorile zecimale din emisii (parsate cu serde_json implicit) intră numai sub toleranța 1e-12 |
| Q3 | `src/main.rs` cu `#[tauri::command]` | `main.rs` păstrează CLI-ul S18 (`inventory`, `--version`) și adaugă `parity`, `enumerate`, `gui` (implicit fără argumente = GUI). Comenzile Tauri sunt învelișuri subțiri peste funcții de bibliotecă testate (`src/bridge.rs`) | Primul pas din predări rulează `inventory`; logica trebuie testabilă fără fereastră |
| Q4 | Frontend „lightweight” | HTML/CSS/JS static în `rust_core/ui/` (fără Node, fără bundler), `withGlobalTauri: true`, CSP restrictiv, `bundle.active=false`; pictogramă PNG RGBA generată determinist în `rust_core/icons/` | Zero dependențe noi; Tauri v2 încorporează `ui/` la compilare |
| Q5 | „Densitățile π” | (i) π_i = probabilitatea de includere a etichetei i sub legea Fisher (Poisson condiționat) a modelului, aceeași recursie ca `emite.inclusion`; (ii) matricea de includere de ordinul 2 Π_ij = w_i w_j e_{k−2}(w_{−i,−j}) / e_k(w), Π_ii = π_i; (iii) operatorul densitate ρ = Π / k (hermitian în `Complex64`, urma 1, semidefinit pozitiv, fiind E[XXᵀ]/k pentru vectorul indicator X) | ρ este un operator densitate exact (nu o metaforă): urma 1 și PSD sunt verificate numeric, nu presupuse |
| Q6 | FrFT „direct în modulul spectral” | Fișier nou `src/models/spectral/frft.rs` (submodul declarat în `spectral.rs`). Construcția S16 (Candan–Kutay–Ozaktas 2000): S[j,j] = 2cos(2πj/n) − 4, S[j,j±1 mod n] = 1; descompunerea pară/impară P; vectori proprii prin algoritmul Jacobi ciclic propriu (fără crate de algebră liniară), sortați descrescător după valoarea proprie, intercalați pe ordinele Hermite 0,1,…,n−2, n−1+[n par]; F_a = V diag(e^{−iπ a r/2}) Vᵀ | Reproduce definiția S16 publicată; precedent atribuit (Namias 1980; Ozaktas–Zalevsky–Kutay 2001; Candan–Kutay–Ozaktas 2000) |
| Q7 | „Variantele pur liniare filtrate nativ la nivel de memorie” | Fișier nou `src/models/spectral/admissible.rs`: biletul = mască `u64` (bitul i−1 ⇔ eticheta i); tabela precalculată, sortată, a tuturor măștilor pur liniare pentru (n, b) (căutare binară); căutarea best-first exactă S17 (heap) cu cheia (s exact descrescător, tuplu crescător); s exact prin expansiuni Shewchuk fără suprapunere (TwoSum exact), comparate prin semnul expansiunii diferenței; enumerarea completă prin „Gosper's hack” pe toate nucleele (`std::thread::scope`) | Definiția S17 neschimbată (progresie aritmetică, b ≥ 3, bila Joker exclusă; `NU_PARIAZA` dacă max\|ln w\| = 0); exactitatea ordinii nu depinde de rotunjire |
| Q8 | Legătura FrFT ↔ filtru | Filtrul NU folosește FrFT pentru a selecta bilete (S16: selecția de coeficienți FrFT = ipoteză nouă, necalificată). Martorul W3-S19 verifică faptul că biletul admisibil și ln ŵ sunt invariante la dus-întorsul F_a⁻¹F_a | Transformare unitară ⇒ nicio informație nouă (predicție declarată acum, ca în S16) |
| Q9 | GPU (RTX 5060) | Niciun cod GPU în S19. Volumul maxim real este enumerarea C(49,6) = 13 983 816 de măști (sume de 6 termeni) — fezabilă pe CPU multi-fir; criteriul GPU rămâne cel din `ACCELERARE_GPU.md` (exactitate + câștig ≥ 3× pe un calcul care îl cere). Un nucleu GPU = protocol separat cu măsurarea erorii FP64/FP32 | Fără promisiuni de precizie; FP64 pe GPU-urile de consum are debit redus |
| Q10 | Compilare | `cargo fmt --check`, `cargo check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`, `cargo build --release` (opt-level 3, LTO, codegen-units 1, panic abort — profilul S18 neschimbat), `--offline` dacă registrul local ajunge, altfel rezolvare din crates.io declarată | Reproductibil; jurnale în `tu4/rezultate/S19/` |
| Q11 | Persistență SSD | Copii 0444 ale binarului release, ale referinței și ale rapoartelor de paritate în `./ssd_data/RUST_CORE_S19/` (sha identice) | Cerința de stocare externă |

## 2. Referința Python (`tu4/s19_paritate_ref.py`, fișier NOU, read-only față de tot restul)

- Verifică întâi sha-urile: `ip_core.py` = `ab3e1de9…`, `s16_martori.py` = `298d3ec6…`, emisiile = `LANT.jsonl`,
  `BILETE_ADMISIBILE_20261028T001924Z.json` = `6e9afe94…`. Importă `ip_core` și `s16_martori` numai după verificare.
  Calcul pe CPU, `torch.float64` (fără compilare). Nu importă `emite.py` (efecte la import); recursia de includere π
  este copiată literal din `emite.inclusion` și folosește `ip_core.esp` înghețat.
- **Fixturi sintetice (extrageri explicite, scrise în referință; Rust le citește, nu le regenerează):**
  - FX1: n=49, k=6, 2595 de extrageri, `random.Random(20261028).sample`; FX2: n=40, k=6, 2490, sămânța 20261029;
  - FX3: n=45, k=5, 2202, sămânța 20261030, plus bila n=20, k=1, 2202 (aceeași sursă);
  - FX4: n=49, k=6, 3000 de extrageri cu ponderi w_i = 1 + 0.35·cos(2π(i−½)/49) (eșantionare fără întoarcere
    ponderată, sămânța 20261031) — λ > 0 așteptat pentru H1/H3 (nu e condiție de trecere);
  - FX5: n=5, k=2, extragerile {1,2},{1,3},{1,4},{2,3} (forma închisă din S18); FX6: n=6, k=3, toate cele 20 de
    combinații (λ = 0); FX7: n=20, k=1, panta netedă din S18 (eticheta l repetată 60 − 2l ori).
- **Arhiva reală (paritate):** cele 3 fișiere ale versiunii indicate de `tu3/date/live/CURRENT_LIVE.json` în momentul
  rulării (sha verificat cu manifestul), citite read-only; numărările se construiesc ca în `emite.load_live`.
- **Mărimi de referință** pentru fiecare caz: N, c (n), P (n×n, P_ii = c_i), θ̂ și X² (`theta_x2`), H1 (`logw_h1`:
  ln ŵ, λ), H3 (`logw_h3` cu `dct_basis`: ln ŵ, λ), baza `dct_basis` (n×4), D = `info_D`(ln ŵ) pentru H1 și H3, π
  (recursia `emite.inclusion`), Π (formula Q5 calculată cu `ip_core.esp` pe w fără i, j), R = (P/N − (c/N)(c/N)ᵀ) /
  (p(1−p)), spectrul unitar Z = `numpy.fft.fft`(z)/√n, iar pentru k = 1 și q = softmax(ln ŵ). FrFT: matricele
  `s16_martori.frft_matrix(n, a)` pentru n ∈ {20, 40, 45, 49}, a ∈ {0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 1.9}.
- Ieșire: `tu4/rezultate/S19/REFERINTA_PARITATE_<UTC>.json` (0444), cu fiecare float în zecimal și în hex.

## 3. Modulele Rust noi (în `rust_core/src/`)

- `models/fisher.rs`: polinoamele simetrice elementare (aceeași ordine ca `ip_core.esp`), π, D (ca `info_D`), Π, ρ,
  puritatea Tr ρ², valoarea proprie minimă a lui ρ (Jacobi), q pentru k = 1.
- `models/spectral/frft.rs`, `models/spectral/admissible.rs` (Q6, Q7); `models/spectral.rs` primește numai declarațiile
  de submodul și reexporturile (nicio formulă S18 schimbată).
- `models/parity.rs`: încărcarea referinței (hex exact), recalculul Rust și comparațiile; raport JSON.
- `bridge.rs`: funcțiile apelate de comenzile Tauri (inventarul LIVE, densitățile pe arhiva curentă, FrFT pe z,
  starea filtrului pe emisiile sigilate citite read-only, ultimul raport de paritate). Fără scrieri pe disc.
- `main.rs`: CLI (`inventory`, `parity`, `enumerate`, `gui [--smoke <fișier>]`) + `#[tauri::command]`.
- `h1_mass.rs`, `h3_aero.rs`, `parser.rs` NU se modifică (verificat prin sha în sigiliu).

## 4. Criterii de acceptanță (fixate acum; toleranțe absolute)

- **B0 integritate:** sha-urile din §2 și cele 10 sigilii existente `drift []` înainte și după S19.
- **B1 compilare:** fmt 0, check 0, clippy `--all-targets -D warnings` 0, toate testele trec (cele 25 din S18 + cele
  noi), release 0. Testele noi minime: hex exact; Shewchuk (anulare catastrofală, egalități exacte); ESP vs forța
  brută (n ≤ 10); π și Π vs enumerarea completă (n ≤ 10, |Δ| ≤ 1e-12); identitățile Σπ = k, diag Π = π,
  Σ_{j≠i} Π_ij = (k−1)π_i, urma ρ = 1, ρ PSD; urna uniformă ⇒ Π_ij = k(k−1)/(n(n−1)); Jacobi (A V = V Λ); FrFT W0/W1;
  A1 (numărul de progresii = Σ_{d≥1} max(0, n − (b−1)d), prin enumerare completă) și A2 (heap = sortarea forței brute,
  6 ≤ n ≤ 12, 3 ≤ b ≤ 5, 3 vectori: aleator cu sămânță fixă, cu valori repetate, constant); comenzile punții.
- **B2 matricele de frecvențe (exact, Δ = 0):** N, c și P identice Rust ↔ Python pentru FX1–FX7 și cele 3 jocuri
  reale (+ bila Joker); dacă versiunea LIVE are aceleași înregistrări și aceeași ultimă cheie ca emisiile, c (și
  numărările bilei) identice și cu `warm_start` din emisii.
- **B3 H1/H3 (|Δ| ≤ 1e-12):** θ̂, X², λ, ln ŵ (H1); λ, ln ŵ (H3); baza cosinus (n×4) — pentru toate cazurile; X²_s (H3)
  față de câmpul `X2` al emisiei H3; ln ŵ și λ față de câmpurile emisiilor (H1, H3, inclusiv bila Joker).
- **B4 densități (|Δ| ≤ 1e-12):** π, D, Π (și q pentru k = 1) față de referință; π, D, q față de emisii; urma ρ − 1 și
  min eig ρ ≥ −1e-12 pe toate cazurile.
- **B5 Complex64:** R față de referință ≤ 1e-12 și reziduul hermitic exact 0; spectrul Z față de NumPy ≤ 1e-12.
- **B6 FrFT:** W0: max|F_0 − I| ≤ 1e-12, max|F_1 − DFT| ≤ 1e-10, max|F_aF_b − F_{a+b}| ≤ 1e-12 pentru (0.3,0.4),
  (0.5,0.5), (0.25,1.5); W1: max|F_aᴴF_a − I| ≤ 1e-12; W2: |‖F_a z‖² − ‖z‖²| ≤ 1e-12·‖z‖²; W3-S19: după
  c′ = Np + Re(F_a⁻¹F_a(c − Np)), max|Δ ln ŵ| ≤ 1e-12 (H1, H3) și biletul admisibil neschimbat, pe cazurile reale
  active; încrucișat: max|F_a^Rust − F_a^NumPy| ≤ 1e-10 (solvere proprii diferite: Jacobi vs LAPACK).
- **B7 filtrul de admisibilitate:** A1 prin enumerarea Gosper completă pentru (49,6), (40,5), (45,5) = forma închisă
  (216, 180, 231 bilete liniare; total C(n,b)); A3: pe ln ŵ din cele 3 emisii sigilate, heap-ul Rust reproduce EXACT
  fișierul S17 pentru toate cele 6 fluxuri: `stare`, `top_ticket_emis`, `top_emis_liniar`, `bilet_afisare`, `rang`,
  `noduri_heap`, `bila_stare`, `bila_afisare`, iar |ln(q/u)| top/admisibil față de S17 ≤ 1e-12; enumerarea completă
  multi-fir dă același top, același bilet admisibil și același rang.
- **B8 Tauri:** `build.rs` + `tauri.conf.json` acceptate de `tauri-build` la compilare; binarul release pornește
  fereastra cu `gui --smoke <fișier>`: frontendul apelează fiecare comandă prin IPC și scrie raportul de fum;
  B8 PASS ⇔ toate comenzile au răspuns fără eroare. Dacă fereastra nu poate porni în mediu ⇒ B8 = UNKNOWN (nu PASS),
  raportat ca atare.
- **B9 zero drift și regresie:** după S19, rerularea primului pas (EM 42/42, JU 13/13, 130 passed, 38 + 3s, UI 15/15,
  `"ok": true`, 10 × `drift []`), emisiile și `ip_core.py` cu sha neschimbate; DL exit 0.
- **Verdict:** `S19_SUPERQUANTUM_PASS` ⇔ B0–B9 PASS. Altfel `S19_SUPERQUANTUM_PARTIAL` (cu lista exactă) sau
  `S19_SUPERQUANTUM_FAIL`; orice FAIL/UNKNOWN ⇒ incident `tu4/incidente/S19_NN/` cu fișierele încercării păstrate, fără
  schimbarea toleranțelor; reparația e permisă numai pentru conformitatea cu definițiile de mai sus, cu amendament
  scris înainte. Iterațiile de compilare (erori de tip/stil) sunt inginerie normală, raportate în `RAPORT_S19.md`.

## 5. Ce se raportează fără prag

Abaterile maxime |Δ| pe fiecare mărime și numărul de potriviri bit-cu-bit; timpii (o singură rulare, nu benchmark,
fără comparație cu Python); mărimea binarului release; dimensiunile matricelor; puritatea ρ și min eig ρ.

## 6. Interpretare fixată acum

PASS înseamnă: Rust reproduce aritmetica nucleului Python înghețat în limita 1e-12 și reproduce exact filtrul S17.
NU înseamnă nicio putere predictivă; marginea informațională W4 (S16) rămâne valabilă pentru orice transformare,
inclusiv FrFT. ρ descrie legea MODELULUI (sub urna reală uniformă, toate biletele au aceeași șansă).

## 7. Fișiere

- NOI permise: `tu4/PROTOCOL_SUPERQUANTUM_S19.md`, `tu4/SIGILIU_TU4_S19.json`, `tu4/s19_paritate_ref.py`,
  `tu4/rezultate/S19/*`, `tu4/incidente/S19_*/` (numai la nevoie), în `rust_core/`: `build.rs`, `tauri.conf.json`,
  `capabilities/default.json`, `icons/*`, `ui/*`, `src/bridge.rs`, `src/models/fisher.rs`, `src/models/parity.rs`,
  `src/models/spectral/frft.rs`, `src/models/spectral/admissible.rs`, `gen/` (generat de tauri-build, ignorat);
  `./ssd_data/RUST_CORE_S19/**`.
- MODIFICATE permis (sha-urile vechi în sigiliu): `rust_core/Cargo.toml` (numai adaosul Q1), `rust_core/Cargo.lock`,
  `rust_core/.gitignore` (adaugă `/gen`), `rust_core/src/lib.rs`, `rust_core/src/main.rs`,
  `rust_core/src/models/mod.rs`, `rust_core/src/models/spectral.rs` (numai declarații + reexporturi).
- Predarea: `predari/OPERATIV.md`, Mesajul 63 în `predari/MESAJE_UTILIZATOR_QL649.md`, perechea nouă prin
  `predari/genereaza_predare.py` (neschimbat).
