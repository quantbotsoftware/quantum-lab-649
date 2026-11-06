# PROTOCOL TU4-S24 — pornirea automată (systemd, utilizator) a Streamlit 8649 și structura decontării/B5

Cererea = Mesajul 75 (2026-10-28T07:03:31-04:00 = 11:03:31Z). Utilizatorul l-a numit „Mesajul 69”; numărul 69 (ca
și 70–74) e ocupat, deci primește numărul liber următor, 75, fără renumerotare. Protocolul și sigiliul
(`tu4/SIGILIU_TU4_S24.json`) se scriu ÎNAINTEA oricărui cod S24 și a oricărei modificări de sistem.

`positive_claims_allowed=false`. S24 este numai infrastructură (pornirea unui server local) și pregătirea unor rapoarte
read-only. Nu calculează, nu emite și nu prezice nimic.

**Corecții de premisă (declarate, fără a adopta formulările):**
1. Cererea descrie operațiile drept „procesări de stări energetice stabile reflectate din arhivă”. Ca în S23, eticheta
   NU se adoptă: modelele H1/H3 sunt calcule clasice pe arhivă, iar emisiile/decontările sunt înregistrări de test
   științific. Nu există „stări energetice” fizice și niciun avantaj informațional.
2. Cererea cere ca serverul grafic „să citească datele din LOTO_SSD mapat prin fstab”. Inventarul read-only (§0) arată
   că aplicația Streamlit (`app.py`, `engine.py`, `parser.py`, `tu3/`) NU citește nimic de pe SSD; consumatorii SSD sunt
   tribunalul (`emite.py`, `judecator.py`), telemetria ferestrei Rust (`telemetry.rs`) și arhivele `RUST_CORE_S*`.
   S24 NU modifică aplicația ca să citească de pe SSD (ar fi o schimbare de cod fără motiv științific). Ce se
   implementează: serviciul AȘTEAPTĂ montarea fstab (SM1) înainte de pornire și jurnalizează starea SSD-ului, astfel
   încât, după boot, 8649 pornește într-un mediu în care SSD-ul e deja montat.

## 0. Inventar read-only (făcut înainte de protocol)

| Element | Valoare constatată |
|---|---|
| Primul pas S24 (baza B0) | `tu4/rezultate/S24/primul_pas_S24_20261028T110352Z.log`; `primul_pas_S24.sh` `fe7d2be3…`; DRIFT_S23 3/3; 14 × `drift []`; EM 42/42, JU 13/13, 130 passed, 38 + 3s, UI 15/15, `EXIT_PY=0`; `SURSE_RUST_OK 27`, 61/61, `c20fdcd2…`, 7289/0, **587/587**, 4/4, B2 PASS, M2 15/15, G0 17/17, `DL_RC=0`; `verifica_s23.py v0` = 27/28, singurul FAIL `incidente` (cunoscut: `S23_02`, `S23_03`) — `V0_VERIFICARE_20261028T110644Z.json` `3f509248…` |
| Incidente existente | `EM_01 FR_01 S19_01 S20_01 S23_01 S23_02 S23_03 SM1_01` (niciun director nou) |
| 8649 | pornit manual de agent după boot-ul 06:52:08 EDT: pid 5842, în `run-rc8fe300….scope` (`app.slice`), ascultă numai `127.0.0.1:8649`; lansatorul `jurnal/lansator_tu3_20261028T105431Z.log`: „health ok”, „TOATE 3 MODURILE READY” |
| SSD | `/dev/sda1` → `./ssd_data` (montat de systemd la boot, SM1); `/etc/fstab` `e503cbc0…` |
| systemd utilizator | 255; `Linger=yes`; nu există nicio unitate pentru 8649; unitățile pistei sunt fișiere obișnuite (nu legături) în `~/.config/systemd/user/` |
| Lansatorul `porneste_aplicatia_tu3.sh` | oprește instanța veche, verifică sintaxa, pornește detașat (`setsid ./run_app_tu3.sh`), așteaptă health ≤ 120 s, apoi `xdg-open` (browser) și iese cu 0; cod 1 la eroare. Înghețat (sigiliul SM1) — NU se modifică |
| Tribunal | `LANT.jsonl` 3 linii (emisiile 2026-10-29: 649 `e2fe385e`, 540 `a15dc8fd`, joker `092e3f5c`; extragerea `2026-10-29T16:30:00Z`, cutoff 14:00Z); `DECONTARI.jsonl` absent; ultima rulare a judecătorului `nothing_to_settle` |
| Surse Rust înghețate | 27/27 în manifestul S22, 0444, inclusiv `src/models/h1_mass.rs` și `src/models/h3_aero.rs` |

## 1. Partea A — pornirea automată a 8649 (variante)

| | A1. Unitate systemd de utilizator, `WantedBy=default.target`, care rulează EXACT comanda cerută — **ALEASĂ** | A2. Autostart XDG (`~/.config/autostart/*.desktop`) | A3. Fără schimbare (pornire manuală) |
|---|---|---|---|
| Pornește după boot fără login | DA (Linger=yes ⇒ managerul de utilizator pornește la boot) | NU (numai după login grafic) | NU |
| Root | nu | nu | nu |
| Izolare | serverul rulează în propriul `run-*.scope` (cgroup separat), creat de `systemd-run --scope` | procesul sesiunii grafice | scope manual |
| Reversibil | `revino_s24.sh` (disable + ștergere + daemon-reload) | ștergerea fișierului | — |

**Decizie:** A1. A2 nu acoperă boot-ul fără login. A3 rămâne procedura de rezervă, documentată.

### 1.1 Specificația fixată a unității

Fișierul canonic în pistă: `tu4/systemd/ql649-tu3-8649.service`; copia instalată, byte-identică:
`~/.config/systemd/user/ql649-tu3-8649.service`; activare cu `systemctl --user enable` (legătura în
`default.target.wants/`). Conținutul (exact; numai comentariile pot fi adăugate deasupra secțiunilor):

```
[Unit]
Description=QL649 TU3 - Streamlit 127.0.0.1:8649 pornit automat (S24; scope izolat prin systemd-run)
Documentation=file://${QL649_ROOT:-.}/tu4/PROTOCOL_QUANTUM_S24.md
StartLimitIntervalSec=15min
StartLimitBurst=3

[Service]
Type=oneshot
WorkingDirectory=${QL649_ROOT:-.}
UnsetEnvironment=DISPLAY WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
Environment=BROWSER=/usr/bin/true
ExecStartPre=/usr/bin/bash ${QL649_ROOT:-.}/tu4/s24/asteapta_ssd.sh 90
ExecStart=/usr/bin/systemd-run --user --scope --collect -q ./porneste_aplicatia_tu3.sh
TimeoutStartSec=6min
Restart=on-failure
RestartSec=30
NoNewPrivileges=yes

[Install]
WantedBy=default.target
```

Motivarea fiecărei opțiuni (fixată):
- `ExecStart` = comanda din cerere, octet cu octet, cu calea absolută a lui `systemd-run`. Serverul ajunge într-un
  `run-*.scope` separat ⇒ terminarea serviciului `oneshot` nu îl oprește, iar oprirea scope-ului nu atinge serviciul.
- `ExecStartPre` = `tu4/s24/asteapta_ssd.sh 90`: așteaptă cel mult 90 s ca `./ssd_data` să fie punct de
  montare (montarea fstab SM1 apare la ~4 s după boot). Scrie în jurnal `SSD_MONTAT <sursă>` sau, la expirare,
  `SSD_ABSENT`, și iese **cu 0 în ambele cazuri** (decizie fixată: aplicația nu citește SSD-ul, deci absența lui nu
  blochează dashboard-ul; starea rămâne vizibilă în jurnal). Scriptul primește opțional al doilea argument = calea
  punctului de montare (numai pentru testul Q3).
- `UnsetEnvironment` + `BROWSER=/usr/bin/true`: pornirea automată NU deschide browserul (la boot nu există sesiune
  grafică; după login, serviciul nu trebuie să deschidă file nedorite). Pictograma/pornirea manuală rămân neschimbate.
  Notificările (`notify-send … || true`) eșuează silențios dacă nu există sesiune.
- `Restart=on-failure`, `RestartSec=30`, limita 3 porniri / 15 min: o eroare tranzitorie la boot e reîncercată, fără
  buclă infinită.
- `NoNewPrivileges=yes`: procesele nu pot câștiga privilegii (setuid). Rețea: lansatorul impune `127.0.0.1`
  (`.streamlit/config.toml`, `run_app.sh`), verificat în Q2.
- Fără `After=default.target` (ar crea un ciclu) și fără dependențe de unități de sistem (managerul de utilizator nu le
  poate referi); așteptarea SSD-ului e făcută de `ExecStartPre`.

Limite declarate: serviciul pornește o singură dată pe boot (al managerului de utilizator). Dacă serverul moare
ulterior, NU e repornit automat (supravegherea continuă ar cere un alt tip de serviciu, în afara cererii). Pornirea din
pictogramă după login repornește serverul (comportamentul lansatorului), ceea ce e acceptat.

## 2. Partea B — structura decontării fără reglaje (joi 29 oct) și B5 (ținta 2026-11-01)

Decontarea o face EXCLUSIV judecătorul (`ql649-tu4-judecator`, cod sigilat TU4-JU). S24 NU îl rulează, NU îl modifică și
NU scrie în `tu4/tribunal/`. Se adaugă doar instrumente read-only:

- `tu4/s24/raport_decontare_s24.py [--tinta 2026-10-29] [--trib <dir>] [--out <dir>]`:
  1. calculează hash-ul arborelui `tu4/tribunal/` înainte și după; orice diferență ⇒ FAIL (`tribunal_neatins`);
  2. verifică lanțul `DECONTARI.jsonl`: `i` consecutiv de la 0, `prev_line_sha256` = sha liniei precedente (prima linie:
     `JU_SEAL_SHA`, citit textual din `tu4/judecator.py`), `sha256` = sha fișierului `decontari/<joc>/<data>.json`;
  3. pentru ținta cerută și fiecare joc (649, 540, joker) copiază VERBATIM din documentul judecătorului: `status`,
     `reason`, `decided_utc`, `draw`, pentru H1/H3 `ln_e` și `counted`, `streams_before`/`streams_after`, `thresholds`,
     emisia (`sha256`, `lant_i`). **Nu recalculează și nu ajustează nimic**; pragurile se compară cu constantele
     sigilate (`ln 600`, `ln 20`, `-10`, `M=6`) — o nepotrivire e FAIL;
  4. verifică că sha-ul emisiei decontate apare în `LANT.jsonl`;
  5. scrie `tu4/rezultate/S24/DECONTARE_<data>_<UTC>.json` și `.md`, cu verdictul:
     `DECONTARE_COMPLETA` (3/3 jocuri decontate, lanț OK), `DECONTARE_PARTIALA` (1–2), `DECONTARE_PENDING` (0; de
     exemplu înaintea extragerii), `DECONTARE_FAIL` (lanț rupt, sha nepotrivit, tribunal modificat, praguri diferite).
     PENDING nu devine PASS.
- `tu4/s24/b5_s24.sh`: dacă există `tu4/tribunal/emisii/649/2026-11-01.json`, rulează
  `rust-singularity-core admissibility --target 2026-11-01 --enumerate`, salvează ieșirea în
  `tu4/rezultate/S24/ADMISIBILITATE_20261101_<UTC>.json` și rulează `verifica_s20.py b5` (așteptat PASS, 6/6); altfel
  scrie `B5_PENDING` și rulează varianta B2 (fără enumerare), ca suita moștenită. Nu scrie în tribunal.

## 3. Fișiere

- NOI (agentul, după sigiliu): `tu4/s24/asteapta_ssd.sh`, `tu4/s24/verifica_s24.py`, `tu4/s24/raport_decontare_s24.py`,
  `tu4/s24/b5_s24.sh`, `tu4/s24/revino_s24.sh`, `tu4/systemd/ql649-tu3-8649.service`, copia instalată
  `~/.config/systemd/user/ql649-tu3-8649.service` și legătura `default.target.wants/ql649-tu3-8649.service`,
  `tu4/rezultate/S24/*` (inclusiv `primul_pas_S25.sh`, rapoarte, verificări), `jurnal/*` (lansator), eventual
  `tu4/incidente/S24_NN/`, fixture-uri sintetice numai în director temporar.
- ÎNGHEȚATE (în sigiliu): cele 27 de surse `rust_core` (manifestul S22; inclusiv `h1_mass.rs`, `h3_aero.rs`, 0444),
  protocoalele/sigiliile S23 și SM1, `porneste_aplicatia_tu3.sh`, `porneste_aplicatia.sh`, `run_app_tu3.sh`,
  `run_app.sh`, `porneste_rust_core.sh`, `app.py`, `.streamlit/config.toml`, `tu4/judecator.py`, `tu4/emite.py`,
  `tu4/porneste_emitere.sh`, `tu4/porneste_judecator.sh`, unitățile systemd de utilizator existente ale pistei
  (inclusiv drop-in-urile `loto-actualizare.service.d`), `predari/genereaza_predare.py`,
  `tu4/rezultate/S23/primul_pas_S24.sh`, `tu4/rezultate/S23/verifica_s23.py`, `tu4/rezultate/S20/verifica_s20.py`,
  `/etc/fstab` (`e503cbc0…`). Fișierele tribunalului `LANT.jsonl`, `RULARI.jsonl`, `JUDECATOR_RULARI.jsonl` sunt
  append-only: se fixează prefixul (octeți + sha).
- Niciun `chmod u+w` pe surse Rust. Niciun `sudo`.

## 4. Procedura (ordinea fixată)

1. Sigiliul (`tu4/rezultate/S24/sigileaza_s24.py`), care refuză dacă `tu4/s24/` sau unitatea există deja.
2. Codul S24 (§3), apoi Q0 și Q1 (fără activare).
3. Activarea: copierea unității, `systemctl --user daemon-reload`, `enable`, apoi `systemctl --user restart
   ql649-tu3-8649.service` (oprește pid 5842 prin lansator și pornește prin serviciu). Q2, Q3.
4. Q5, Q6 (read-only).
5. Închiderea: `primul_pas_S25.sh` (= `primul_pas_S24.sh` neschimbat + verificările S24) și Q7.
6. Raportul `tu4/rezultate/S24/RAPORT_S24.md`; Q4 rămâne `UNKNOWN` până la o repornire a laptopului, făcută de
   utilizator la momentul ales de el (agentul NU repornește laptopul).

Momente interzise pentru pasul 3 și pentru repornire: emisiile programate 08:20, 12:20, 15:20 Europe/Bucharest și
decontarea de după extragerea de joi (16:30Z), ±15 minute.

## 5. Criterii (fixate înainte de cod)

| Id | Criteriu | PASS dacă |
|---|---|---|
| Q0 | Integritate | protocolul și sigiliul au sha-urile din sigiliu; toate fișierele înghețate au sha-ul din sigiliu; cele 27 de surse Rust au modul 0444; prefixele append-only sunt intacte; `/etc/fstab` = `e503cbc0…` |
| Q1 | Unitatea | fișierul canonic = copia instalată (octet cu octet) = textul din §1.1 (fără comentarii); `systemd-analyze --user verify` fără erori; `is-enabled` = `enabled`; `Linger=yes` |
| Q2 | Pornirea prin systemd (fără repornire) | după `restart`: `Result=success`; health `ok` în ≤ 150 s; procesul care ascultă pe 8649 e în `run-*.scope` (NU în cgroup-ul serviciului) și ascultă numai pe `127.0.0.1`; jurnalul lansatorului acestei porniri conține „health ok” și „TOATE 3 MODURILE READY”; vechiul pid 5842 nu mai există |
| Q3 | Așteptarea SSD-ului | `asteapta_ssd.sh 5` (cale implicită) → cod 0 și `SSD_MONTAT /dev/sda1`; `asteapta_ssd.sh 2 <director-nemontat>` → cod 0, `SSD_ABSENT`, durată ≥ 2 s; jurnalul serviciului (pornirea Q2) conține `SSD_MONTAT` |
| Q4 | După repornirea laptopului (fără intervenția agentului) | `journalctl --user -b -u ql649-tu3-8649.service` arată pornirea reușită în boot-ul curent, cu `SSD_MONTAT`; ascultătorul 8649 e în `run-*.scope`, pornit după boot; health `ok`. Până la repornire: `UNKNOWN` |
| Q5 | Decontarea (structură, read-only) | rularea pe tribunalul real: `tribunal_neatins`; verdict corect pentru starea curentă (`DECONTARE_PENDING` înaintea decontărilor); pe fixture sintetic temporar: 3/3 ⇒ `DECONTARE_COMPLETA`, un sha alterat ⇒ `DECONTARE_FAIL`, un prag modificat ⇒ `DECONTARE_FAIL` |
| Q6 | B5 (structură) | `b5_s24.sh` produce exact ramura corectă pentru starea curentă (fără emisia 2026-11-01: `B5_PENDING` + B2 PASS; cu emisia: B5 PASS 6/6); tribunalul neatins |
| Q7 | Închidere | `primul_pas_S25.sh`: aceleași rezultate ca baza B0 (inclusiv 587/587, 61/61, EM 42/42, JU 13/13, UI 15/15, M2 15/15, G0 17/17, `DL_RC=0`) și `verifica_s23.py v0` 27/28 cu singurul FAIL `incidente`; incidentele găsite = cele 8 din §0 ∪ incidentele `S24_*` declarate în raport (orice alt director = FAIL) |

Verdicte:
- `S24_PASS`: Q0–Q7 PASS.
- `S24_PARTIAL`: Q0–Q3 și Q5–Q7 PASS, Q4 `UNKNOWN` (repornirea nu a fost încă făcută).
- `S24_FAIL`: oricare criteriu FAIL. Pentru Q1–Q4: imediat `revino_s24.sh` (dezactivare + ștergere + daemon-reload) și
  pornirea manuală documentată; pentru orice FAIL: incident `tu4/incidente/S24_NN/`, fără reglaje.

**Regula de închidere (lecția `S23_02`):** incidentele apărute în sesiune se declară în raport cu sha-ul lor și intră
în mulțimea așteptată a lui Q7; nu se rescrie nimic sigilat. UNKNOWN nu devine PASS.

## 6. Riscuri și revenire

- Pornirea serviciului oprește instanța curentă (comportamentul lansatorului): întrerupere de câteva secunde a 8649.
- Dacă serviciul pică repetat: `systemctl --user status ql649-tu3-8649.service`, apoi revenirea
  `bash tu4/s24/revino_s24.sh` și pornirea manuală (`systemd-run --user --scope --collect -q ./porneste_aplicatia_tu3.sh`).
- Serviciul nu primește privilegii și nu expune portul în afara `127.0.0.1`.

## 7. Interpretare

PASS înseamnă: după boot, managerul systemd al utilizatorului pornește 8649 singur, izolat într-un scope propriu, după ce
SSD-ul montat prin fstab e disponibil, iar instrumentele de decontare/B5 sunt pregătite read-only. Nu înseamnă nimic
despre rezultatul vreunei extrageri și nu are legătură cu vreo putere predictivă.
