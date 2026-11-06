# PROTOCOL TU4-L1 — lansatorul autoadaptiv (pictograma de pornire) al ferestrei Tauri „Quantum Lab 649 · Rust Core”

Cererea = Mesajul 68 (2026-10-27T23:41:05-04:00 = 2026-10-28T03:41:05Z): „avem vreo interfață UI? Dacă da, creează o
iconiță de pornire care să se autoadapteze încât să pornească întotdeauna versiunea nouă”. Protocolul și sigiliul
(`tu4/SIGILIU_TU4_L1.json`) se scriu ÎNAINTEA lansatorului. `positive_claims_allowed=false`. Lansatorul doar pornește o
interfață existentă; nu calculează, nu emite, nu decontează și nu prezice nimic.

## 0. Inventar read-only (făcut înainte de protocol)

Proiectul are trei interfețe grafice:

| Interfață | Ce este | Lansator existent |
|---|---|---|
| Quantum Lab 649 (Streamlit, `app.py` + `tu3/ui_tu3.py`, 127.0.0.1:8649) | laboratorul în browser | DA: `~/Desktop/quantum-lab-649.desktop` + meniu → `porneste_aplicatia_tu3.sh`, deja autoadaptiv (oprește serverul vechi, șterge bytecode-ul, verifică sintaxa, amprentă de versiune, repornește). Repornirea serverului la 23:24 EDT a fost un clic pe această pictogramă |
| Quantum Limit (`python3 -m quantum_limit fereastra`) | produsul (valoarea biletului) | DA: `quantum-limit-limita.desktop` (rulează mereu codul curent din sursă) |
| Quantum Lab 649 · Rust Core (Tauri, `rust_core/target/release/rust-singularity-core gui`) | fereastra nativă S18–S22 (densități, FrFT, admisibilitate, paritate, inventar, memorie) | **NU există** |

Observație: `~/Desktop/Quantum_Lab_Unified.desktop` (creat 2026-10-27 19:54, nu de această pistă) doar deschide
`http://127.0.0.1:8649` în browser; nu pornește serverul. Nu se modifică și nu se șterge (fișier al utilizatorului).

**Decizie:** lansatorul nou se face pentru fereastra Tauri, singura interfață fără pictogramă. Cele două lansatoare
existente rămân neschimbate.

## 1. Ce înseamnă „se autoadaptează” (definiție fixată)

La fiecare clic, lansatorul:

1. **Compilează incremental** sursele curente: `cargo build --offline --release -q` în `rust_core/`. Cargo decide singur:
   dacă nimic nu s-a schimbat, operația durează sub o secundă; dacă o sesiune viitoare a modificat `src/` sau `ui/`,
   binarul se recompilează înainte de pornire. Nu e nevoie de editarea lansatorului la sesiunile viitoare.
2. **Alternativă sigură:** dacă compilarea eșuează (de exemplu surse în lucru), pornește cel mai nou binar arhivat
   pe SSD (`./ssd_data/RUST_CORE_S<NN>/bin/`, NN maxim), copiat cu `install -m 0555` în
   `~/.cache/ql649_rust_core/`. Notificarea spune explicit acest lucru. Dacă nici acesta nu există: eroare, fără pornire.
3. **Stabilește versiunea și starea verificării:** SHA-256 al binarului ales e comparat cu `release_binary.sha256` din
   TOATE manifestele `tu4/rezultate/S*/MANIFEST_RUST_CORE_*.json` (descoperite automat, deci și cele viitoare):
   - egal cu cel mai nou manifest ⇒ „verificată (manifest TU4-Sxx)”;
   - egal cu un manifest mai vechi ⇒ „verificată, dar mai veche (TU4-Sxx)”;
   - fără potrivire ⇒ „NEVERIFICATĂ (cod modificat după ultima sesiune sigilată)”. Pornirea NU se blochează; doar se
     anunță.
4. **O singură instanță, mereu versiunea nouă:** dacă rulează deja o fereastră (`rust-singularity-core gui`, fără
   `--smoke`) cu ACELAȘI binar (SHA-ul lui `/proc/<pid>/exe`), nu se deschide a doua; notificare „deja deschisă”. Dacă
   rulează o versiune diferită (inclusiv binar înlocuit), fereastra veche primește TERM (KILL după 5 s), apoi pornește
   cea nouă.
5. **Pornește** fereastra detașat (`setsid … gui`), cu `QL649_ROOT` = directorul pistei, și confirmă după 3 s că
   procesul trăiește. Jurnal: `jurnal/lansator_rust_<UTC>.log`. Notificare cu versiunea (8 hex), starea verificării și
   sursa binarului.

Moduri: fără argumente = pornire; `--verifica` = pașii 1–4 fără pornire și fără oprirea altor instanțe (raport pe
stdout); `--stop` = închide ferestrele Tauri pornite (TERM, apoi KILL). Variabile numai pentru teste:
`QL649_RUST_CORE_DIR` (alt director de surse) și `QL649_SSD_BIN_ROOT` (altă rădăcină de arhivă).

Limită declarată: `--stop`/TERM oprește procesul fără evenimentul `RunEvent::Exit`, deci fără `rezumat.json` pentru acea
sesiune de telemetrie (segmentele JSONL rămân pe SSD). Închiderea normală, din butonul ferestrei, rămâne cea completă.

## 2. Fișiere

- NOI: `tu4/PROTOCOL_LANSATOR_L1.md`, `tu4/SIGILIU_TU4_L1.json`, `tu4/rezultate/L1/*`,
  `porneste_rust_core.sh` (în directorul pistei), `~/.local/share/applications/quantum-lab-649-rust-core.desktop`,
  `~/Desktop/quantum-lab-649-rust-core.desktop`, cache-ul `~/.cache/ql649_rust_core/` (numai la alternativă), jurnalele.
- ÎNGHEȚATE (în sigiliu): toate sursele `rust_core` din manifestul S22, sigiliile S16–S22, `porneste_aplicatia_tu3.sh`,
  `run_app.sh`, `run_app_tu3.sh`, cele două lansatoare `.desktop` existente ale pistei și ale produsului,
  `genereaza_predare.py`.
- NIMIC în `rust_core/` nu se modifică sau adaugă (pictograma folosită: `rust_core/icons/icon.png`, existentă).

## 3. Criterii de acceptanță

- **L0:** la final, toate hash-urile înghețate sunt neschimbate (drift gol) și toate cele 27 de surse `rust_core` sunt
  0444; `verifica_s22.py g0` PASS.
- **L1 (actual):** `porneste_rust_core.sh --verifica` pe sursele reale: compilare exit 0, binarul `c20fdcd2…`, starea
  „verificată (manifest TU4-S22)”.
- **L2 (pornire reală):** clic simulat (rularea scriptului cu `DISPLAY` al sesiunii): o fereastră nouă trăiește după
  3 s, cu `/proc/<pid>/exe` = binarul local; o nouă sesiune de telemetrie apare pe SSD.
- **L3 (o singură instanță):** a doua rulare, cât fereastra e deschisă: niciun proces nou, jurnal „deja deschisă”.
- **L4 (oprire):** `--stop`: nicio fereastră `gui` rămasă după ≤ 6 s.
- **L5 (autoadaptare):** pe o COPIE a `rust_core` (sursele + `target/release`, copiate pe SSD în
  `./ssd_data/QL649_L1_PROBA/`),
  modificarea textului `<title>` din `ui/index.html`: `--verifica` cu `QL649_RUST_CORE_DIR=<copie>` recompilează,
  raportează un SHA diferit de `c20fdcd2…` și starea „NEVERIFICATĂ”. Sursele reale rămân neatinse.
- **L6 (alternativă):** `QL649_RUST_CORE_DIR=<director inexistent>` + `--verifica`: compilarea eșuează, se alege
  binarul arhivat `RUST_CORE_S22` (`c20fdcd2…`), starea „verificată (manifest TU4-S22)”, sursa „arhivă SSD”.
- **L7:** fișierele `.desktop` trec `desktop-file-validate` (dacă există) și au `Exec` = calea absolută a scriptului.
- **Verdict:** `L1_PASS` ⇔ L0–L7 PASS (L7 cu validatorul marcat UNKNOWN dacă lipsește, fără a bloca). Orice FAIL ⇒
  incident `tu4/incidente/L1_NN/`, fără schimbarea criteriilor.

## 4. Interpretare

PASS înseamnă: o pictogramă pornește mereu cea mai nouă versiune compilabilă a ferestrei Tauri, spune dacă e cea
verificată de ultima sesiune sigilată și nu lasă două ferestre deschise. Nu înseamnă nicio putere predictivă.
