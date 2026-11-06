# PROTOCOL TU4-S27 — coloana de asigurare pentru citirea evenimentelor externe (decontarea de joi, emisia 2026-11-01)

Cererea = Mesajul 78 (2026-10-28T08:27:21-04:00 = 12:27:21Z). Protocolul și sigiliul (`tu4/SIGILIU_TU4_S27.json`) se scriu
ÎNAINTEA oricărui cod S27 (`tu4/s27/`) și a oricărei verificări S27.

`positive_claims_allowed=false`. S27 e numai infrastructură de observare: o sondă strict read-only care spune în ce fază
se află lanțul extern (arhiva LIVE → judecătorul → decontarea 2026-10-29 → emisia 2026-11-01) și dacă gărzile care
protejează C1 (S25) și B5 (S20) sunt intacte. Sonda nu citește numerele extragerilor, nu calculează scoruri, nu emite, nu
decontează, nu rulează binarul Rust și nu prezice nimic. Nu înlocuiește instrumentele existente: verdictele C1, B5 și
decontarea rămân EXCLUSIV ale primului pas neschimbat (`primul_pas_S26.sh` → Q7L, `b5_s24.sh`, `raport_decontare_s24.py`).

**Corecții de premisă (declarate, fără a adopta formulările):**
1. Instrumentele read-only pentru decontare (`tu4/s24/raport_decontare_s24.py`) și pentru B5 (`tu4/s24/b5_s24.sh`) există
   deja din S24 și rulează în primul pas. S27 nu le dublează și nu le schimbă; adaugă o sondă de fază cu ZERO scrieri, care
   poate fi rulată oricând (în afara ferestrelor) fără a produce fișiere și fără a consuma o rulare de criteriu.
2. „Decontarea de joi 16:30 UTC”: 16:30Z este ora extragerii (`draw_utc` 2026-10-29T16:30:00Z, 18:30 Europe/Bucharest).
   Decontarea o face judecătorul sigilat TU4-JU, la prima rulare de după extragere în care extragerea este în arhiva LIVE
   (`judecator.py` `decide`: altfel `pending` „extragerea nu este încă în arhiva LIVE”; după 14 zile `VOID`).
3. **Risc extern constatat în inventar (nu se repară în S27):** `loto-actualizare.service` eșuează la fiecare rulare din
   2026-10-25T19:00Z (74/74 în jurnal, 0 reușite) cu „Actualizarea a eșuat; snapshotul anterior rămâne activ.
   Model/environment changed after protocol freeze: gpu-v1”. Arhiva LIVE (`tu3/date/live/CURRENT_LIVE.json`) se republică,
   dar rămâne la `last_date` 2026-10-25 pentru toate cele 3 jocuri. Consecințe, derivate din codul sigilat:
   - dacă eșecul persistă, extragerea din 29 oct nu ajunge în arhivă ⇒ decontarea rămâne `DECONTARE_PENDING`;
   - `emite.py`: cu arhiva incompletă (`last_date` < `previous_draw_date` 2026-10-29) emisia pentru 2026-11-01 e
     `postponed` până la fereastra finală (2026-11-01 15:00 Europe/Bucharest), deci ar veni duminică la slotul 15:20
     (13:20Z), nu vineri. C1 și B5 se mută corespunzător.
   Garda `gpu-v1` aparține produsului principal (în afara QL649) și e moștenită („neatins”); repararea sau legitimarea ei
   cere decizia utilizatorului și un protocol separat. S27 doar o face vizibilă.
4. Directoarele `tu4/incidente/S26_*` rămân NECREATE (Q7L S25 înghețat ar da FAIL pe C1). Același motiv se aplică
   oricărui incident S27: se înregistrează în `tu4/rezultate/S27/INCIDENT_S27_NN.json`, iar directorul
   `tu4/incidente/S27_NN/` se creează numai după închiderea C1, împreună cu `S26_*`.
5. „AVX2/FMA static active”: se verifică numai flagurile CPU (`avx2`, `fma` pe toate CPU-urile logice) și
   `target-cpu=native` în `rust_core/.cargo/config.toml`. Nu se afirmă execuția vreunei instrucțiuni și nici câștig de viteză.

## 0. Inventar read-only (înainte de protocol, baza B0)

| Element | Valoare constatată |
|---|---|
| Predarea `120625Z` | HANDOFF `5ea8f349…`, PROMPT `4527fa40…` = `VERIFICARE_PREDARE_20261028T120625Z.json` |
| Primul pas (B0) | `tu4/rezultate/S25/primul_pas_S26_20261028T122747Z.log` (`7404c1a8…`): 14 × `drift []`, `LANT_PREFIX_S20 OK linii 3`, EM 42/42, JU 13/13, 130 passed, 38 + 3s, UI 15/15, `SURSE_RUST_OK 27`, 61/61, `c20fdcd2…`, 587/587, `PARITY_RC=0`, `DL_RC=0`, Q0/Q1 PASS, Q4 `UNKNOWN`, `DECONTARE_PENDING`, `B5_PENDING` + `B2_RC=0`, `SCUT_LANT OK linii 3 []`, A0 PASS |
| V0L / Q7L | `V0L_VERIFICARE_20261028T123028Z.json` (`78e1303e…`) 28/29, singurul FAIL `incidente`; `Q7L_VERIFICARE_20261028T123028Z.json` (`4f50f63e…`) PASS 11/11 |
| Incidente | `EM_01 FR_01 S19_01 S20_01 S23_01 S23_02 S23_03 S24_01 SM1_01` (9); `S26_*` absente |
| Tribunal | `LANT.jsonl` 3 linii (0444); `DECONTARI.jsonl` absent; `emisii/*/2026-11-01.json` absente; `.lock` 0664; judecătorul rulează la ~:00:30 și ~:30:30 (`nothing_to_settle`, pending „înainte de ora extragerii”) |
| Arhiva LIVE | `CURRENT_LIVE.json` republicat la 30 min; `last_date` 2026-10-25 (649, 540, joker) |
| `loto-actualizare` | `Result=exit-code` la fiecare rulare din 2026-10-25T19:00Z (garda `gpu-v1`) |
| Cod sigilat citit | `emite.py`: `DRAW_T` 18:30, `CUTOFF_T` 16:00, `FINAL_T` 15:00 (Europe/Bucharest), `WEEKDAYS` (joi, duminică); `judecator.py` `decide` |
| Gazda | 24 CPU logice, `avx2` 24/24, `fma` 24/24; `.cargo/config.toml` cu `target-cpu=native` |
| Python | `/usr/bin/python3` 3.12.3, `zoneinfo` Europe/Bucharest disponibil |
| Moduri | `verifica_s25.py`, `raport_decontare_s24.py`, `verifica_s24.py` 0644 (S24/S25, înghețate prin hash, nu prin mod); `verifica_s23.py`, `verifica_s20.py`, `judecator.py` 0444 |

## 1. Ferestre interzise (fixate)

Nicio rulare S27 (sondă reală, verificare, primul pas) în ±15 min (inclusiv) față de emisiile 08:20/12:20/15:20
Europe/Bucharest (orice zi) sau de extragerea 2026-10-29T16:30Z. Sonda refuză citirea tribunalului într-o fereastră
(`SONDA_S27_FAZA=UNKNOWN_FEREASTRA`, rc 3). Suplimentar, verificatorul P2 refuză pornirea în minutele [:58, :04) și
[:28, :34) (rulările judecătorului/actualizării), ca hash-urile externe înainte/după să nu fie confundate cu o scriere.

## 2. Sonda `tu4/s27/sonda_s27.py` (specificație fixată)

Rulare: `/usr/bin/python3 -B tu4/s27/sonda_s27.py [--trib D] [--incidente D] [--live D] [--judecator F] [--acum ISO]
[--tinta-decontare 2026-10-29] [--tinta-emisie 2026-11-01] [--fara-systemd]`. Implicit: căile reale. Scrie NUMAI pe
stdout. Nu creează, nu modifică și nu șterge fișiere; nu ia lock exclusiv (numai `flock` PARTAJAT pe `.lock`, deschis
read-only, prin `raport_decontare_s24.shared_lock`); nu rulează binarul Rust și nu pornește/oprește unități systemd
(cel mult `systemctl --user show`, read-only). Reutilizează, prin import (fără modificare), `verifica_s25.scut_lant` și
`raport_decontare_s24.analyze/tree_hash/ju_seal_sha`.

Pași, în ordine:
- **W** fereastra §1 (după `--acum` sau ceasul real). În fereastră: rc 3, fără a citi tribunalul.
- **G1** incidentele = exact cele 9 din `incidents_before` (S26); orice director în plus (inclusiv `S26_*`/`S27_*`) ⇒ ANOMALIE.
- **G2** 27/27 surse Rust 0444 cu sha = manifestul S22; **G3** binarul `c20fdcd2…`; **G4** `avx2`/`fma` pe toate CPU-urile
  logice și `target-cpu=native` (descriptiv-static). G2–G4 se raportează; G2/G3 FAIL ⇒ ANOMALIE. G4 e informativ.
- **T1** scutul LANT (`scut_lant` = []); liniile LANT după prefixul S20 (joc, țintă). Scut FAIL ⇒ ANOMALIE.
- **T2** decontarea țintei (`analyze`): verdict și n/3. `DECONTARE_FAIL` ⇒ ANOMALIE.
- **T3** emisia țintei 2026-11-01: numărul de jocuri cu linie LANT și fișier `emisii/<joc>/<țintă>.json`.
- **T4** sursa externă (informativ): `CURRENT_LIVE.json` `updated_utc` și `last_date` pe joc (fără `last_key` și fără
  numere); ultima rulare a judecătorului (`utc`, `action`, motivele `pending`); ultima acțiune a emițătorului; `Result`-ul
  `loto-actualizare.service` (omis cu `--fara-systemd`).
- **T5** arborele tribunalului: hash înainte = după, sub lockul partajat; diferit ⇒ ANOMALIE.

Faza (prima regulă aplicabilă): `ANOMALIE` (rc 1) dacă G1, G2, G3, T1, T2 sau T5 cad; altfel `FAZA_4_EMISIE_COMPLETA`
(3/3), `FAZA_3_EMISIE_PARTIALA` (1–2), `FAZA_2_DECONTARE_COMPLETA` (3/3 decontate, fără emisie), `FAZA_1_DECONTARE_PARTIALA`
(1–2), `FAZA_0_ASTEAPTA_DECONTAREA` (0) — toate rc 0. Avertismente (informative, nu schimbă rc):
- `AVERTISMENT_DECONTARE_BLOCATA` dacă acum ≥ extragerea țintei + 2 h, decontarea nu e completă și min(`last_date`) < ținta;
- `AVERTISMENT_EMISIE_AMANATA` dacă emisia țintei lipsește și min(`last_date`) < ținta decontării: emisia e așteptată la
  fereastra finală (ținta emisiei, 15:20 Europe/Bucharest), nu vineri.
Ultima linie: `SONDA_S27_FAZA=<faza> RC=<rc> positive_claims_allowed=false`, plus `URMATORUL_PAS=` (text fix pe fază).

## 3. Criterii (praguri fixate înainte)

**P0 — starea înainte (toate):** (1) hash-urile predării `120625Z` = fișierul de verificare; (2) B0: log `7404c1a8…`,
Q7L `4f50f63e…` PASS 11/11, V0L `78e1303e…` 28/29 numai `incidente`; (3) toate `frozen_hashes` din sigiliul S27 =
valorile curente; (4) incidentele = cele 9, fără `S26_*`/`S27_*`; (5) 27/27 surse Rust 0444 cu sha = manifestul S22;
(6) sha-ul sigiliului S27 = cel înregistrat în verificator; (7) `tu4/s27/sonda_s27.py` are modul 0444.

**P1 — fixture sintetice (toate), în directoare temporare din afara pistei; sonda rulată ca subproces:**
F1 copie a tribunalului real (LANT 0444 + emisii) ⇒ `FAZA_0`, rc 0; F2 `--acum 2026-10-29T16:40:00Z` ⇒ rc 3
`UNKNOWN_FEREASTRA`, `--acum 2026-11-01T13:25:00Z` ⇒ rc 3, `--acum 2026-10-29T16:50:00Z` ⇒ rc 0; F3 incidente + `S26_01` ⇒
`ANOMALIE` rc 1; F4 un octet schimbat în prefixul LANT ⇒ `ANOMALIE` rc 1; F5 decontare sintetică validă (lanț din
`JU_SEAL_SHA`, sha-urile emisiilor reale) pentru 1 joc ⇒ `FAZA_1`, pentru 3 ⇒ `FAZA_2`, cu sha alterat ⇒ `ANOMALIE`;
F6 1 respectiv 3 linii LANT sintetice valide pentru ținta 2099-01-01 (`--tinta-emisie 2099-01-01`) ⇒ `FAZA_3` respectiv
`FAZA_4`; F7 arhivă LIVE sintetică: `last_date` 2026-10-25 și `--acum 2026-10-29T19:00:00Z` ⇒ `AVERTISMENT_DECONTARE_BLOCATA`
și `AVERTISMENT_EMISIE_AMANATA` prezente; `last_date` 2026-10-29 ⇒ ambele absente; F8 în fiecare fixture arborele
fixture-ului e identic înainte/după rulare. Toate fixture-urile folosesc `--fara-systemd`.

**P2 — rularea reală (o singură dată, toate):** (1) rc 0; (2) faza = cea calculată independent de verificator din
fișiere (linii `DECONTARI.jsonl` pentru 2026-10-29, fișiere `emisii/*/2026-11-01.json`); (3) arborele tribunalului
neschimbat (intern în sondă și extern în verificator); (4) instantaneu (cale, mărime, mtime_ns, sha) al `tu4/` fără
`tu4/tribunal/`, al `predari/` și al `rust_core/src/` identic înainte/după; (5) stdout conține
`positive_claims_allowed=false` și liniile G1–G4, T1–T5.

**P3 — neintervenție după (toate):** (1) `frozen_hashes` S27 neschimbate; (2) incidentele = cele 9; (3) 27/27 surse 0444;
(4) `ql649-tu4-emitere.timer` și `loto-actualizare.timer` `active`; (5) `tu4/s27/` conține numai `sonda_s27.py` și
`verifica_s27.py`, ambele 0444.

**Q7L final:** după P3, primul pas `primul_pas_S26.sh` neschimbat, în afara ferestrelor ⇒ Q7L PASS 11/11, V0L 28/29
numai `incidente`, `DECONTARE_PENDING`, `B5_PENDING` + `B2_RC=0`.

## 4. Verdict

- `S27_PASS` = P0 ∧ P1 ∧ P2 ∧ P3 ∧ Q7L final.
- `S27_FAIL` = oricare FAIL; se înregistrează `tu4/rezultate/S27/INCIDENT_S27_NN.json` (directorul de incident amânat,
  corecția 4), fără reglaje și fără repetare cu alte praguri.
- `UNKNOWN` (fereastră interzisă, SSD nemontat) nu devine PASS.
- `S27_PASS` NU înseamnă că decontarea sau emisia vor avea loc la timp: riscul `gpu-v1` (corecția 3) rămâne deschis.

Raport: `tu4/rezultate/S27/RAPORT_S27.md`. Fișiere noi permise: `tu4/PROTOCOL_QUANTUM_S27.md`, `tu4/SIGILIU_TU4_S27.json`,
`tu4/rezultate/S27/*`, `tu4/s27/sonda_s27.py`, `tu4/s27/verifica_s27.py`, logul primului pas în `tu4/rezultate/S25/`
(scrierile uzuale ale primului pas). Fără `sudo`, fără `chmod u+w` pe fișiere înghețate, fără scrieri în
tribunal/systemd/surse/produsul principal, fără `tu4/incidente/S26_*`/`S27_*`. Git: numai `./dev-git status`.
