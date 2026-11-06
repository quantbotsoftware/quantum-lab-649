# PROTOCOL TU4-S23 — canalele de telemetrie pe SSD, verificate prin pictograma „Quantum Lab 649 · Rust Core”

Cererea = Mesajul 69 (2026-10-28T05:41:28-04:00 = 2026-10-28T09:41:28Z). Utilizatorul l-a numit „Mesajul 68”, dar
numărul 68 este deja ocupat în `predari/MESAJE_UTILIZATOR_QL649.md` de cererea pictogramei (L1). Mesajul curent se
adaugă ca **Mesajul 69**, fără renumerotarea celor existente.

Protocolul și sigiliul (`tu4/SIGILIU_TU4_S23.json`) se scriu ÎNAINTEA oricărei operații care nu e read-only și înaintea
verificatorului `tu4/rezultate/S23/verifica_s23.py`. `positive_claims_allowed=false`. Calculul este clasic (CPU, procfs).
Nimic din S23 nu calculează, emite, decontează sau prezice extrageri.

## 0. Inventar read-only (făcut înainte de protocol)

1. **Predarea:** `HANDOFF_QL649_20261028T034709Z.md` (`9219c55d…`) și `PROMPT_…034709Z.txt` (`b8c1c812…`) au exact
   sha-urile din `VERIFICARE_PREDARE_20261028T034709Z.json`. Canonicul (`74641a9d…`) și suplimentul (`3e28bd63…`)
   coincid. Perechea precedentă `…033626Z` e în `predari/istoric/` cu sha-urile declarate.
2. **L1:** `porneste_rust_core.sh` `4e54add1…`, `PROTOCOL_LANSATOR_L1.md` `ad6efbab…`, `SIGILIU_TU4_L1.json`
   `bdae1df5…`, `RAPORT_L1.md` `84c582dc…` (L1_PASS). Pictograma `~/Desktop/quantum-lab-649-rust-core.desktop` există,
   cu `Exec=…/porneste_rust_core.sh`. Cele 27 de surse `rust_core` sunt 0444, inclusiv `src/models/h1_mass.rs` și
   `src/models/h3_aero.rs`.
3. **Mediu:** la începutul sesiunii (09:42Z) SSD-ul `LOTO_SSD` (`/dev/sda1`) era **nemontat**. A fost montat cu comanda
   documentată în predare (`udisksctl mount -b /dev/sda1 --no-user-interaction`). Fără SSD, telemetria ferestrei ar fi
   pornit `INDISPONIBIL` (comportament S21 Q8). După predare, utilizatorul a pornit fereastra din pictogramă de 3 ori
   (sesiunile `20261028T034818Z_pid283414`, `…035531Z_pid284448`, `…035908Z_pid284727`, ultimele două închise normal,
   cu `rezumat.json`, `n_webview = 2`). Acestea sunt observații; nu sunt acțiuni ale agentului.
4. **Ce există deja (S21 + S22), fără nicio modificare necesară:**
   - `src/telemetry.rs` (S21) scrie, pe un fir dedicat, câte o linie JSONL per eșantion, imediat, în
     `./telemetry/<UTC>_pid<PID>/telemetrie_NNN.jsonl` (append text, fără mmap). Intervalul
     ferestrei normale este 1000 ms (100 ms în `--smoke`). Eșantionul acoperă `{pid} ∪ descendenți`, adică și
     `WebKitWebProcess` și `WebKitNetworkProcess`: `webview_rss`/`webview_hwm` = Σ pe procesele WebKit, `n_webview` =
     numărul lor. Valorile per proces (pid, nume, VmRSS, VmHWM, Pss) apar în tabelul instantaneu al filei „Memorie”
     (`cmd_memorie`), nu în JSONL.
   - Fila „Memorie” (S22) apelează asincron `await invoke("cmd_telemetrie")`, la cel puțin 1000 ms, numai cât fila e
     activă și vizibilă. Desenează câmpurile `*_ultim` și `*_varf` ale agregatului. Câmpurile `*_ultim` sunt actualizate
     DUPĂ scrierea liniei pe SSD (`absorb` după `write_line`), deci reprezintă ultimul eșantion scris.
   - **Consecință:** comportamentul cerut la punctul 2 al cererii există deja. S23 este o sesiune de **verificare pe
     fereastra reală**, fără modificarea surselor. Schimbarea unor surse sigilate fără o nevoie funcțională ar invalida
     manifestul S22 și nu ar aduce nimic nou. Nu se face `chmod u+w` pe nimic.
5. **Primul pas, rulat înainte de finalizarea acestui protocol** (`tu4/rezultate/S23/primul_pas_S23_20261028T094216Z.log`):
   totul conform predării (14 × `drift []`, `LANT_PREFIX_S20 OK`, EM 42/42, JU 13/13, 130 passed, 38 + 3s, `"ok": true`,
   `SURSE_RUST_OK 27`, 61/61, `c20fdcd2…`, 587/587, 6 + 4/4, B2, M2 15/15, G0 17/17, `DL_RC=0`), CU O EXCEPȚIE:
   **UI 14/15, `FAIL S8_http_health` (connection refused), `EXIT_PY=1`**; `ss` nu arată nimic pe 8649. Cauza, verificată:
   laptopul a repornit la 2026-10-28 05:39:30 EDT (09:39:30Z; `uptime -s`, `last -x reboot`), cu 2 minute înaintea
   cererii. Repornirea a oprit Streamlit 8649 (nu e serviciu systemd) și a demontat SSD-ul. Timerele (Linger) au
   repornit singure. Abaterea se înregistrează ca **incident de mediu `tu4/incidente/S23_01/`**, cu logul păstrat
   neschimbat. Remediul este exclusiv procedura documentată în predare:
   `systemd-run --user --scope --collect -q ./porneste_aplicatia_tu3.sh`. Nu se schimbă cod, praguri sau așteptări.
   Rezultatul acesta a fost văzut ÎNAINTE de sigilare; de aceea V0 cere o a doua rulare completă, după remediu (§3).
   (Notă: predarea rezerva numele `S23_01` pentru un eventual FAIL B5 după emisia de vineri; un astfel de incident va
   primi următorul număr liber.)
6. **Corecție de premisă (etichetă neadoptată):** densitățile din fila „Densități” sunt matrice ρ (urmă 1, pozitiv
   semidefinite) obținute clasic, prin softmax, din log-ponderile modelelor de frecvență H1/H3 (contracție James–Stein)
   pe arhiva de extrageri. `tu4/tribunal/LANT.jsonl` este lanțul emisiilor; e folosit numai de fila „Filtru
   admisibilitate”, pentru certificarea sha-urilor, și nu alimentează densitățile. Nici densitățile, nici LANT nu sunt
   soluții sau „puncte de echilibru energetic” ale ecuației Wheeler–DeWitt. Eticheta NU se adoptă și nu apare în UI
   (la fel ca „stări de energie stabilă” în S22). Densitățile nu au caracter predictiv.

## 1. Definiții fixate

- **Eșantion valid:** o linie a sesiunii pe SSD care se parsează ca obiect JSON, are `pid` = pid-ul ferestrei,
  `seq` = numărul ei de ordine (de la 1, consecutiv), `citiri_esuate = 0`, `n_procese ≥ 1` și `n_webview ≥ 1`.
- **Ultimul eșantion valid citit de UI:** agregatul primit de frontend prin `cmd_telemetrie` are câmpurile
  `utc_ultim`, `rss_total_ultim`, `hwm_total_ultim`, `webview_rss_ultim`, `webview_hwm_ultim`, `n_webview_ultim`,
  `n_procese_ultim`, `citiri_esuate_ultim` EGALE cu câmpurile corespunzătoare ale liniei de pe SSD cu
  `seq = esantioane`, iar acea linie este un eșantion valid.
- **Limită declarată:** dacă ultimul eșantion are `citiri_esuate > 0` (de exemplu un proces WebKit care tocmai se
  închide), UI-ul îl afișează totuși, cu verdictul Webview `UNKNOWN`. S23 nu schimbă acest comportament.

## 2. Fișiere

- NOI: `tu4/PROTOCOL_QUANTUM_S23.md`, `tu4/SIGILIU_TU4_S23.json`, `tu4/rezultate/S23/*` (inclusiv `sigileaza_s23.py`,
  `verifica_s23.py`, `primul_pas_S24.sh`, `RAPORT_S23.md`), sesiunile noi din `./telemetry/`,
  `jurnal/lansator_rust_*.log`, eventual `tu4/incidente/S23_NN/`; în predare: `predari/OPERATIV.md`, Mesajul 69 în
  `predari/MESAJE_UTILIZATOR_QL649.md`, perechea nouă (prin `genereaza_predare.py`).
- ÎNGHEȚATE (în sigiliu): tot ce a înghețat S22, protocolul/sigiliul/rezultatele S22 și L1, cele 27 de surse `rust_core`
  (manifestul S22, inclusiv `app.js`, `index.html`, `telemetry.rs`, `h1_mass.rs`, `h3_aero.rs`), `porneste_rust_core.sh`,
  cele două fișiere `.desktop` ale pictogramei și `genereaza_predare.py`.
- Mutabile prin proiectare (nu se îngheață): `tu4/tribunal/LANT.jsonl` (numai append; prefixul S20 se verifică),
  `DECONTARI.jsonl`, `JUDECATOR_RULARI.jsonl`.

## 3. Criterii (fixate înainte de rulare)

| Id | Criteriu | PASS dacă |
|---|---|---|
| V0 | Integritatea la pornire | V0a: logul `primul_pas_S23_20261028T094216Z.log` rămâne înregistrat ca atare (1 FAIL de mediu, §0.5, incident `S23_01`). V0: după repornirea 8649 prin procedura documentată, o a doua rulare completă `primul_pas_S23_*.log` are: `Linger=yes`, 127.0.0.1:8649 în `ss`, health `ok`, 14 × `drift []`, `LANT_PREFIX_S20 OK`, `VERIFICARE_EM_PASS`, JU 13/13, `130 passed`, `38 passed, 3 skipped`, UI 15/15, `EXIT_PY=0`, `SURSE_RUST_OK 27`, `61 passed`, binarul `c20fdcd2…`, paritatea `PASS`, admisibilitate 6 + 4/4, B2 (sau B5) PASS, M2 15/15, G0 17/17, `DL_RC=0`; incidente numai `EM_01 FR_01 S19_01 S20_01`; cele 27 de surse 0444 |
| V1 | Pornirea prin pictogramă | `gio launch ~/Desktop/quantum-lab-649-rust-core.desktop` (echivalentul clicului; rulează `Exec` din fișier) produce un jurnal `lansator_rust_*.log` nou cu `cargo build --release: exit 0`, `versiune=c20fdcd2`, `verificare=verificată (manifest TU4-S22)`, `sursa=compilat din sursele curente` și `pornită: pid P` (sau `deja deschisă (pid P)`); `/proc/P/exe` are sha-ul `c20fdcd2…`; exact 1 fereastră `gui`. În plus, `porneste_rust_core.sh --verifica` raportează același verdict |
| V2 | Telemetria ferestrei pe SSD | există `./telemetry/<UTC>_pidP/`, iar `findmnt` arată `./ssd_data` pe `/dev/sda1`. La două citiri distanțate cu 60 s, numărul de linii crește cu cel puțin 50. Toate liniile sunt obiecte JSON cu `pid = P` și `seq` = 1…N consecutiv. Ultima linie este un eșantion valid cu `n_webview ≥ 2` și `webview_rss > 0`. La momentul citirii, procfs arată printre descendenții lui P cel puțin un proces `WebKitWebProces` și cel puțin unul `WebKitNetworkPr` (nume `comm`, trunchiate la 15 caractere) |
| V3 | Fila „Memorie” citește asincron ultimul eșantion valid | pe fereastra reală `DISPLAY=:1 … gui --smoke <fișier>` (aceeași cale ca G1 din S22): `toate_ok = true`; `grafic.ok = true` (≥ 3 pași în direct, perioada 1000 ms, 3 rânduri desenate); agregatul primit de frontend (`raport_frontend.telemetrie.raspuns`) respectă definiția „ultimul eșantion valid citit de UI” (§1) față de JSONL-ul sesiunii smoke de pe SSD; agregatul final (cheia `telemetrie`) are `esantioane` = numărul de linii, iar câmpurile `*_ultim` ale lui corespund ultimei linii, care e validă. Static: G0 17/17 (`verifica_s22.py g0`) |
| V4 | Etichetă și axiomă | 0 apariții (fără diferență între majuscule și minuscule) ale șirurilor `wheeler`, `dewitt`, `echilibru energetic`, `energie stabil` în `rust_core/src` și `rust_core/ui`; `info.positive_claims_allowed = false` în raportul smoke |
| V5 | Stabilitate sub sarcina curentă (numai informativ) | se raportează, pe sesiunea V2, primul/ultimul/maximul pentru `rss_total` și `webview_rss` și diferența ultim − prim. Fără prag și fără verdict. Verdictul Webview 30 MB rămâne informativ (FAIL cunoscut din S20–S22) |
| V6 | Închiderea | după rapoarte: sigiliul S23 fără drift; `primul_pas_S24.sh` (nou) rulat integral, cu aceleași așteptări ca V0, plus `drift []` pentru S23 |

Verdicte: `S23_PASS` = V0–V4 și V6 PASS. Orice FAIL ⇒ `S23_FAIL` + incident `tu4/incidente/S23_NN/`, fără reglaje și
fără modificarea criteriilor. UNKNOWN nu devine PASS.

## 4. Ordinea operațiilor

1. V0a (primul pas S23, rulat înaintea acestui protocol: read-only, cu excepția scrierilor uzuale declarate în predare).
2. Protocolul, apoi sigiliul (`sigileaza_s23.py`, rulat o singură dată), apoi incidentul `S23_01` și `verifica_s23.py`.
3. Repornirea 8649 (procedura documentată), apoi V0 (a doua rulare a primului pas).
4. V3 (smoke), apoi V1 și V2 pe fereastra pornită din pictogramă, V4, V5.
5. Raportul `RAPORT_S23.md`, arhiva SSD `./ssd_data/RUST_CORE_S23/` (protocol, sigiliu, rezultate; binarul
   este identic cu cel din `RUST_CORE_S22`), V6.
6. Predarea: `OPERATIV.md`, Mesajul 69, `genereaza_predare.py`.

**Fereastra pornită din pictogramă rămâne deschisă** la sfârșitul sesiunii, pentru monitorizarea cerută. Ea scrie pe SSD
un eșantion pe secundă (≈ 280 B/linie, ≈ 1 MB/oră; plafon 1 GiB pe sesiune; segmente de 16 MiB). Închiderea completă
(cu `rezumat.json`) se face din butonul ferestrei. `--stop` din meniul pictogramei nu scrie `rezumat.json` (limita L1).

## 5. Interpretare

PASS înseamnă: pictograma pornește versiunea verificată a ferestrei, telemetria ei scrie continuu pe SSD eșantioane care
includ procesele WebKitWebProcess și WebKitNetworkProcess, iar fila „Memorie” afișează exact ultimul eșantion valid scris
pe SSD. Nu înseamnă reducerea memoriei Webview și nu înseamnă nicio putere predictivă.
