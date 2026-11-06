# PROTOCOL TU4-S25 — amendamentul preventiv A-S25-01: drift structural `LANT.jsonl` și scutul prefixului

Cererea = Mesajul 76 (2026-10-28T07:22:35-04:00 = 11:22:35Z). Protocolul și sigiliul (`tu4/SIGILIU_TU4_S25.json`) se scriu
ÎNAINTEA oricărui cod S25. Amendamentul e **preventiv**: e sigilat înaintea emisiei de vineri 30 oct (ținta
2026-11-01), deci înaintea evenimentului pe care îl tratează (cum cerea limita anticipată din predarea `111921Z`).

`positive_claims_allowed=false`. S25 este numai infrastructură de verificare a integrității (octeți, hash-uri, lanțuri de
înregistrări). Nu citește extrageri, nu calculează scoruri, nu emite, nu decontează și nu prezice nimic.

**Corecții de premisă (declarate, fără a adopta formulările):**
1. Cererea cere „reconfigurarea” verificatorului Q7 (`tu4/s24/verifica_s24.py q7`) și a testului V0
   (`tu4/rezultate/S23/verifica_s23.py v0`). Ambele sunt probe istorice: `verifica_s23.py` e 0444 și înghețat în sigiliul
   S24, iar `verifica_s24.py` a produs verdictele S24. **Nu se rescriu.** Amendamentul adaugă variante NOI, `V0L` și
   `Q7L`, în `tu4/s25/verifica_s25.py`; cele vechi rămân byte-identice (verificat în A0). După emisia de vineri, vechiul
   Q7 va da exact FAIL-ul formal anticipat în predarea `111921Z` (`v0_27_28_numai_incidente`, din cauza
   `drift_14_goale`); acest FAIL e anticipat, nu e incident și nu se ascunde. Primul pas viitor folosește `Q7L`.
2. Cererea spune că o linie nouă „trebuie considerată validă dacă prefixul istoric rămâne byte-identic”. Prefixul
   identic e **necesar, dar nu suficient**: fără alte condiții, orice octeți adăugați (o scriere coruptă, o linie
   trunchiată, o linie străină) ar trece. Interpretarea fixată: o linie „adăugată de timer” este o linie în formatul
   exact scris de `tu4/emite.py` (`lant_append`): JSON canonic (`sort_keys`, `ensure_ascii=False`), cheile fixe, `i`
   consecutiv, `prev_line_sha256` = sha-ul liniei precedente, `sha256` = sha-ul fișierului de emisie existent. O linie
   care nu are acest format nu e o linie de timer ⇒ FAIL. Condiția e mai strictă decât formularea cererii, nu mai laxă.
3. Eticheta „scut topologic” se folosește numai ca nume. Mecanismul e clasic: comparații de octeți și un lanț de
   hash-uri SHA-256. Nu există nicio proprietate topologică sau cuantică.
4. „Evaluare pe arhivă”: S25 nu evaluează arhiva de extrageri; verifică doar fișiere de registru.

## 0. Inventar read-only (făcut înainte de protocol)

| Element | Valoare constatată |
|---|---|
| Predarea `111921Z` | HANDOFF `e1fe5052…`, PROMPT `7028aaec…`, canonic `74641a9d…`, supliment `52fe372a…` = `VERIFICARE_PREDARE_20261028T111921Z.json` |
| Primul pas (baza B0 S25) | `tu4/rezultate/S24/primul_pas_S25_20261028T112305Z.log` (`e3cc175b…`); `primul_pas_S25.sh` `1e7f883c…`; DRIFT_S23 PASS; 14 × `drift []`; `LANT_PREFIX_S20 OK linii 3`; EM 42/42, JU 13/13, 130 passed, 38 + 3s, UI 15/15, `EXIT_PY=0`; `SURSE_RUST_OK 27`, 61/61, `c20fdcd2…`, **587/587**, B2 PASS, M2, G0, `DL_RC=0`; Q0/Q1 PASS; Q4 `UNKNOWN`; `DECONTARE_PENDING`; `B5_PENDING` + `B2_RC=0` |
| Q7 / V0 | `Q7_VERIFICARE_20261028T112553Z.json` (`8b37b677…`) PASS 10/10; `V0_VERIFICARE_20261028T112553Z.json` 27/28, singurul FAIL `incidente` |
| Incidente | `EM_01 FR_01 S19_01 S20_01 S23_01 S23_02 S23_03 S24_01 SM1_01` |
| `LANT.jsonl` | 3 linii, 913 octeți, sha `51aa92ce…`, 0444; cheile `emitted_utc file game i prev_line_sha256 sha256 target_date`; prima linie `prev_line_sha256` = `82459f48…` (= `SEAL_SHA` din `emite.py`); fiecare linie = `json.dumps(sort_keys=True, ensure_ascii=False)` |
| Amprenta `LANT_PREFIX_S20` | `SIGILIU_TU4_S20.json` → `append_only_prefix` → `lines 3`, `bytes 913`, `sha256 51aa92ce…` |
| Sigiliile cu `LANT.jsonl` înghețat integral | S16, S17, S18, S19 (`frozen_hashes`, toate `51aa92ce…` = primele 3 linii). S20–S24 îl tratează deja ca append-only (prefix) |
| Mecanismul adăugării | `emite.py: append_line`: `chmod 0644`, `O_APPEND`, o linie + `\n`, `fsync`, `chmod 0444` |
| Surse Rust | 27/27 în manifestul S22, 0444, inclusiv `h1_mass.rs` și `h3_aero.rs` |

## 1. Problema (fixată)

Suita moștenită (`primul_pas_S23.sh`) tipărește 14 linii `<sigiliu> drift [...]`. După emisia de vineri, `LANT.jsonl`
crește la 3 + k linii; sigiliile S16–S19, care îl îngheață integral, vor arăta `drift ['tu4/tribunal/LANT.jsonl']`.
`verifica_s23.py v0` cere 14 × `drift []` ⇒ 26/28 ⇒ vechiul Q7 FAIL formal, deși nimic nu e greșit. Amendamentul
înlocuiește, NUMAI în verificatorul nou, condiția „drift gol” cu o condiție structurală verificabilă.

## 2. Scutul `LANT` (funcția `scut_lant`, fixată)

Pe octeții curenți ai `tu4/tribunal/LANT.jsonl` (sau ai unui tribunal sintetic în A1), PASS dacă TOATE:

- **S1 (`LANT_PREFIX_S20`):** primele 3 linii (cu `\n`) au sha `51aa92ce…` și 913 octeți (amprenta din sigiliul S20).
- **S2 (S16–S19):** pentru fiecare dintre S16–S19, valoarea `frozen_hashes['tu4/tribunal/LANT.jsonl']` = sha-ul unui
  prefix aliniat la linii al fișierului curent, anume primele 3 linii (fixat în sigiliu).
- **S3 (prefixul S25):** primii N₂₅ octeți = instantaneul de la sigilarea S25 (octeți + sha în sigiliu).
- **S4 (forma):** fișierul se termină cu `\n`; nicio linie goală; fiecare linie e UTF-8 și un obiect JSON.
- **S5 (formatul timerului, pentru FIECARE linie, inclusiv prefixul):** cheile = exact
  `{emitted_utc, file, game, i, prev_line_sha256, sha256, target_date}`; linia = `json.dumps(obj, ensure_ascii=False,
  sort_keys=True)` octet cu octet; `i` = indexul liniei; `prev_line_sha256` = `82459f48…` pentru linia 0, altfel sha-ul
  octeților liniei precedente (fără `\n`); `game ∈ {649, 540, joker}`; `target_date` = `AAAA-LL-ZZ`;
  `file` = `emisii/<game>/<target_date>.json`; fișierul există în tribunal și are sha-ul `sha256`; `emitted_utc` =
  `AAAA-LL-ZZTHH:MM:SS(.ffffff)Z` și nedescrescător pe linii; perechea (`game`, `target_date`) e unică.
- **S6:** modul fișierului = 0444 (în afara ferestrei de adăugare).

Orice abatere ⇒ FAIL cu motivul (linia, condiția). Scutul NU scrie nimic.

## 3. Criteriul nou de drift (în `V0L`)

Condiția veche `drift_14_goale` se înlocuiește cu `drift_14_numai_lant_append`, PASS dacă TOATE:
1. logul are exact 14 linii ` drift [`, în ordinea celor 14 sigilii din suita moștenită
   (FR, IP, EM, EM_COD, JU, JU_COD, UI, S16, S17, S18, S19, S20, S21, S22);
2. pentru FR…UI și S20–S22: `drift []`;
3. pentru S16–S19: toate patru identice și fiecare ∈ {`drift []`, `drift ['tu4/tribunal/LANT.jsonl']`};
4. coerența cu logul: dacă S16–S19 arată `drift []`, logul are `LANT_PREFIX_S20 OK linii 3`; dacă arată LANT, logul
   are `LANT_PREFIX_S20 OK linii M` cu M > 3.

Se adaugă verificarea nouă `lant_scut`: `scut_lant` PASS pe tribunalul curent ȘI liniile `LANT <joc> <dată> <sha8>` din
log coincid cu primele M linii ale fișierului curent (M ≤ numărul curent de linii; un timer poate adăuga între log și
verificare). Toate celelalte 27 de verificări ale V0 se păstrează identic (inclusiv `incidente`, cu lista așteptată
moștenită din sigiliul S23, deci FAIL cunoscut). Total V0L: **29 de verificări; așteptat 28/29, singurul FAIL
`incidente`**.

## 4. Criterii (fixate înainte de cod)

| Id | Criteriu | PASS dacă |
|---|---|---|
| A0 | Integritate | sigiliul S25 are sha-ul fixat în cod și e 0444; protocolul are sha-ul din sigiliu și e 0444; fișierele înghețate (§5) fără drift; cele 27 de surse Rust 0444 și sha-urile `h1_mass.rs`, `h3_aero.rs` = manifestul S22; prefixele append-only (`RULARI.jsonl`, `JUDECATOR_RULARI.jsonl`, și `DECONTARI.jsonl` dacă există) intacte; `scut_lant` PASS pe tribunalul real; `verifica_s23.py` și `verifica_s24.py` byte-identice cu sigiliul |
| A1 | Fixture-uri sintetice (director temporar; hash-ul arborelui `tu4/tribunal/` identic înainte/după) | toate cazurile din §4.1 dau rezultatul fixat |
| V0L | V0 amendat, pe logul primului pas | 28/29, singurul FAIL `incidente` |
| Q7L | Q7 amendat | ca Q7 (paritate 587, rust 61, Q0 PASS, Q1 PASS, serviciul `Result=success`, raport de decontare, `B5_RC=0` sau `B2_RC=0`, fără `FAIL Q`), cu V0L 28/29 numai `incidente` (mulțimea găsită ⊆ incidentele permise) în locul V0, incidentele găsite = cele 9 din §0 ∪ incidentele `S25_*` declarate, plus `verifica_s23.py`/`verifica_s24.py` neschimbate. 11 verificări |
| C1 | Confirmarea reală după emisia de vineri | primul pas S26 după emisia 2026-11-01: S16–S19 arată `drift ['tu4/tribunal/LANT.jsonl']`, restul `[]`, `LANT_PREFIX_S20 OK linii 3+k`, Q7L PASS. Până atunci `UNKNOWN` |

### 4.1 Cazurile A1 (rezultat fixat)

| Caz | Construcție (în director temporar) | Așteptat |
|---|---|---|
| F01 | logul B0 real + tribunalul real | V0L 28/29, numai `incidente` |
| F02 | LANT real + 3 linii sintetice valide (emisii sintetice 2099-01-01 cu sha corect, lanț corect); log cu S16–S19 = LANT, `linii 6` și liniile LANT | scut PASS, drift PASS |
| F03 | un octet schimbat în prefix (linia 0) | scut FAIL |
| F04 | fișier trunchiat la 2 linii | scut FAIL |
| F05 | linie nouă cu `prev_line_sha256` greșit | scut FAIL |
| F06 | linie nouă cu `sha256` diferit de fișierul emisiei | scut FAIL |
| F07 | linie nouă cu o cheie în plus | scut FAIL |
| F08 | linie nouă fără `\n` final | scut FAIL |
| F09 | linie nouă cu (`game`, `target_date`) duplicat | scut FAIL |
| F10 | linie nouă cu serializare necanonică (spații diferite) | scut FAIL |
| F11 | log: S17 arată și alt fișier în drift | drift FAIL |
| F12 | log: S20 arată LANT în drift | drift FAIL |
| F13 | log: S16–S19 arată LANT, dar `linii 3` | drift FAIL |
| F14 | log: numai S16 arată LANT | drift FAIL |
| F15 | log: 13 linii drift | drift FAIL |

## 5. Fișiere

- NOI (agentul, după sigiliu): `tu4/s25/verifica_s25.py`; `tu4/rezultate/S25/*` (inclusiv `primul_pas_S26.sh`,
  `RAPORT_S25.md`, verificările `A0/A1/V0L/Q7L_VERIFICARE_<UTC>.json`); eventual `tu4/incidente/S25_NN/`.
  `tu4/rezultate/S25/sigileaza_s25.py` e unealta de sigilare (scrisă după protocol, înaintea sigiliului; refuză dacă
  `tu4/s25/` există).
- ÎNGHEȚATE (în sigiliu, prin sha): cele 27 de surse `rust_core` (0444); protocolul și sigiliul S24 și toate cele 14
  sigilii ale suitei moștenite + S23; `verifica_s23.py`, `verifica_s24.py`, `raport_decontare_s24.py`, `b5_s24.sh`,
  `asteapta_ssd.sh`, `revino_s24.sh`; `primul_pas_S23.sh`, `primul_pas_S24.sh`, `primul_pas_S25.sh`; `verifica_s20.py`;
  `tu4/emite.py`, `tu4/judecator.py`, `porneste_*`, `run_app*.sh`, `app.py`; `predari/genereaza_predare.py`; unitățile
  systemd de utilizator ale pistei; `/etc/fstab`.
- APPEND-ONLY: `LANT.jsonl` (prin `scut_lant`), `RULARI.jsonl`, `JUDECATOR_RULARI.jsonl`, `DECONTARI.jsonl` (dacă
  există la sigilare; altfel numai lanțul, verificat de `raport_decontare_s24.py`).
- Niciun `chmod u+w` pe surse Rust, niciun `sudo`, nicio scriere în `tu4/tribunal/`, nicio modificare de systemd.

## 6. Procedura (ordinea fixată)

1. Sigiliul (`sigileaza_s25.py`).
2. Codul `tu4/s25/verifica_s25.py`, apoi A0 și A1.
3. `primul_pas_S26.sh` (= `primul_pas_S25.sh` NESCHIMBAT + hash-urile S25 + A0), rulat într-un log nou; apoi V0L prin
   Q7L. Compilarea nativă și testele Rust sunt cele din suita moștenită (`cargo test`, `cargo build --release`).
4. `RAPORT_S25.md`. Verdict:
   - `S25_PARTIAL`: A0, A1, V0L, Q7L PASS, C1 `UNKNOWN` (emisia nu a avut loc);
   - `S25_PASS`: și C1 PASS, scris într-un raport de închidere nou, fără rescrierea `RAPORT_S25.md`;
   - `S25_FAIL`: orice FAIL ⇒ incident `tu4/incidente/S25_NN/`, fără reglaje.

**Ferestre:** verificările care citesc `LANT.jsonl` nu se rulează în ±15 min față de emisiile 08:20/12:20/15:20
Europe/Bucharest (fișierul e 0644 și poate avea o linie incompletă câteva milisecunde). Un rezultat produs în fereastră
e invalid, se păstrează și se declară; rularea se repetă după fereastră.

**Regula de închidere (lecția `S23_02`):** incidentele apărute se declară cu sha și intră în mulțimea așteptată a
Q7L; nimic sigilat nu se rescrie. UNKNOWN nu devine PASS.

## 7. Interpretare

PASS înseamnă: un verificator nou deosebește o creștere legitimă a registrului de emisii (format exact al timerului,
prefix istoric byte-identic, lanț de hash-uri, sha-uri de emisie corecte) de orice altă modificare. Nu înseamnă nimic
despre conținutul emisiilor, despre vreo extragere sau despre vreo putere predictivă.
