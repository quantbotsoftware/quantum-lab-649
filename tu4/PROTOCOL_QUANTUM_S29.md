# PROTOCOL TU4-S29 — asigurarea mapării orei de emisie UTC/EST (fereastra de duminică C1/B5)

Cererea = Mesajul 80 (2026-10-28T09:06:40-04:00 = 13:06:40Z). Protocolul și sigiliul (`tu4/SIGILIU_TU4_S29.json`) se scriu
ÎNAINTEA oricărui cod S29 (`tu4/s29/`) și a oricărei verificări S29. Singurul cod scris înainte de sigiliu este scriptul de
sigilare `tu4/rezultate/S29/sigileaza_s29.py` (ca în S27/S28), care nu calculează decât hash-uri.

`positive_claims_allowed=false`. S29 este numai documentare și asigurare a mapării orelor: confirmă cu trei martori
independenți de cod QL649 (zoneinfo Python, `zdump` pe tzdata-ul sistemului, motorul de calendar systemd) că sloturile de
emisie Europe/Bucharest și fereastra verificării finale C1/B5 se mapează corect pe UTC și pe ora laptopului
(America/New_York, EDT→EST), înregistrează formal instrucțiunea pentru duminică și dovedește neintervenția. Nu citește
numerele extragerilor, nu calculează scoruri, nu emite, nu decontează, nu rulează binarul Rust în afara primului pas
neschimbat și nu prezice nimic. Nu există „stări de vacuum” sau alt calcul cuantic: calculul este clasic; prefixul
`LANT_PREFIX_S20` este verificat numai ca integritate (byte-identic), iar verdictele C1/B5/decontare rămân EXCLUSIV ale
primului pas neschimbat.

**Corecții de premisă (declarate, fără a adopta formulările):**
1. „PROTOCOL_QUANTUM_S25.md (sau indexul curent în pipeline)”: `tu4/PROTOCOL_QUANTUM_S25.md` există deja, este sigilat
   (`tu4/SIGILIU_TU4_S25.json`, 0444) și NU se rescrie. Indexul curent este **S29** (S28 închis `S28_PASS`), deci
   documentul este `tu4/PROTOCOL_QUANTUM_S29.md`. Hash-ul sigiliului S29 nu se poate alege dinainte; se publică după scriere.
2. „Fereastra C1/B5 fixată strict 13:36–13:57Z (08:36–08:57 EST)”: este aceeași fereastră recomandată de S28 §2 (corecția
   4). S29 o adoptă ca regulă STRICTĂ pentru duminică 2026-11-01 (§2). Formularea „orice rulare în afara ferestrei va genera
   coliziune cu timerele” nu este literal adevărată pentru orice oră: înainte de 13:36Z rularea cade în fereastra interzisă
   a emisiei 13:20Z (13:05–13:35Z) și emisia poate fi încă în curs; la 13:58Z–14:04Z cade în minutele excluse ale
   actualizării/judecătorului (14:00:30Z) și lângă cutoff-ul 14:00Z; mai târziu nu există coliziune cu un timer în sine.
   S29 nu declară coliziuni inexistente, dar adoptă totuși restricția utilizatorului (mai strictă decât S28): dacă fereastra
   este ratată, verificarea C1/B5 NU se improvizează în altă fereastră; C1/B5 rămân `PENDING`/`UNKNOWN` până la un protocol
   nou care fixează altă fereastră.
3. „Suita completă de verificări de paritate hardware” = primul pas neschimbat (`primul_pas_S26.sh`: paritatea de
   referință 587/587, `cargo test` 61/61, binarul `c20fdcd2…`) urmat de Q7L. Flagurile `avx2`/`fma` sunt informative (G4)
   și nu dovedesc execuția instrucțiunilor. Nu se adaugă nicio afirmație hardware.
4. „Corectitudinea amendamentului AMENDAMENT_S28_A01.md”: se verifică (a) integritatea (sha `bf379c83…` = sigiliul A01
   `b44ffea3…`) și (b) conținutul regulii (9 sloturi, 8 `postponed` sub H_BLOCAT) printr-un martor independent de codul
   S28: motorul de calendar systemd pe expresiile `OnCalendar` ale timerului instalat (P1).
5. Garda externă `loto_romania/cohorta.py:163` (`raise ValueError('Model/environment changed after protocol freeze: ' +
   model)`) rămâne complet NEATINSĂ: nu se modifică, nu se repară, nu se legitimează, nu se investighează cauza. S29 o
   îngheață prin hash (împreună cu unitatea și timerele) ca dovadă de neintervenție, până la sesiunea dedicată separată.
6. Directoarele `tu4/incidente/S26_*` și `S28_01` rămân NECREATE până la închiderea C1. Orice incident S29 se înregistrează
   în `tu4/rezultate/S29/INCIDENT_S29_NN.json`.

## 0. Inventar read-only (înainte de protocol, baza B0)

| Element | Valoare constatată |
|---|---|
| Predarea `125934Z` | HANDOFF `bee62a75…`, PROMPT `9321493e…` = `VERIFICARE_PREDARE_20261028T125934Z.json`; canon `74641a9d…`, supliment `fb54159a…` |
| Fereastra la sosirea cererii | 13:06Z–13:35Z interzis (emisia 15:20 Europe/Bucharest = 13:20Z); primul pas amânat la 13:36:56Z |
| Sonda S27 (13:36:56Z) | `SONDA_RC=0`, `FAZA_0_ASTEAPTA_DECONTAREA`; G1 9 incidente, G2 27/27 0444+sha, G3 `c20fdcd2…`, T1 LANT 3 linii, T2 `DECONTARE_PENDING` 0/3, T4 `last_date` 2026-10-25 ×3, `loto-actualizare` `Result=exit-code`; `AVERTISMENT_EMISIE_AMANATA` |
| Primul pas (B0) | `tu4/rezultate/S25/primul_pas_S26_20261028T133656Z.log` (`566bccb7…`): 14 × `drift []`, `LANT_PREFIX_S20 OK linii 3`, 61/61, `c20fdcd2…`, 587/587, `PARITY_RC=0`, `DL_RC=0`, Q0 12/12, Q1 10/10, Q4 `UNKNOWN`, `DECONTARE_PENDING`, `B5_PENDING` + `B2_RC=0`, `SCUT_LANT OK linii 3 []`, A0 PASS |
| V0L / Q7L | `V0L_VERIFICARE_20261028T133940Z.json` (`7b6ac8b2…`) 28/29, singurul FAIL `incidente`; `Q7L_VERIFICARE_20261028T133940Z.json` (`548274d1…`) PASS 11/11 |
| Sigilii | S27 `ce2a9f18…`, S28 `0b4fd79b…`, A01 `b44ffea3…` (amendament `bf379c83…`) |
| Garda externă | `loto_romania/cohorta.py` linia 163 (citire read-only); hash-urile gărzii/unității/timerelor = cele din sigiliul S28 (13/13) |
| Fusuri | `timedatectl`: America/New_York; `zdump`: NY trece EDT→EST la 2026-11-01T06:00:00Z; `systemd-analyze calendar '*-*-* 15:20:00 Europe/Bucharest'` de la 2026-10-31T14:00Z ⇒ „Sun 2026-11-01 08:20:00 EST” = 13:20:00 UTC |

## 1. Ferestre interzise (neschimbate față de S27/S28)

Nicio rulare S29 (verificare, sondă, primul pas) în ±15 min (inclusiv) față de emisiile 08:20/12:20/15:20
Europe/Bucharest sau de extragerea 2026-10-29T16:30Z. Verificatorul S29 refuză pornirea și în minutele [:58, :04) și
[:28, :34). Fereastra se calculează cu funcția înghețată `sonda_s27.window` (import fără modificare). În fereastră: rc 3,
`UNKNOWN_FEREASTRA`, fără scrieri.

## 2. Instrucțiunea pentru duminică 2026-11-01 (înregistrată formal; fixată)

- Laptopul (America/New_York) trece automat din EDT (UTC−4) în EST (UTC−5) la 2026-11-01T06:00Z (02:00 EDT → 01:00 EST).
  Timerele QL649 folosesc explicit Europe/Bucharest (EET = UTC+2 din 2026-10-25T01:00Z) și nu se schimbă. **Se citește
  numai ora UTC.**
- Slotul final de emisie: 2026-11-01 15:20 Europe/Bucharest = **13:20Z = 08:20 EST**; interzis 13:05Z–13:35Z.
- **Fereastra verificării critice C1/B5: STRICT 2026-11-01 13:36Z–13:57Z (08:36–08:57 EST)**, capete incluse, minut UTC.
  Ordinea: `date -u` (precondiție: 13:36:00Z ≤ acum ≤ 13:57:59Z), apoi sonda `tu4/s27/sonda_s27.py` (așteptat `FAZA_4`,
  sub H_BLOCAT dacă emisia s-a terminat înainte de cutoff), apoi primul pas neschimbat + `verifica_s25.py q7l`.
- În afara ferestrei nu se rulează verificarea C1/B5 duminică. Dacă fereastra este ratată sau emisia dă `late`, C1/B5
  rămân `PENDING`/`UNKNOWN` (fără PASS) și o nouă încercare cere protocol nou (corecția 2).
- Fișa formală: `tu4/rezultate/S29/FISA_DUMINICA_S29.json` (0444), scrisă de P1.

## 3. Criterii (praguri fixate înainte)

Verificatorul `tu4/s29/verifica_s29.py` (0444) are subcomenzile `p0`, `p1`, `p2`; fiecare rulează O SINGURĂ DATĂ (refuză
dacă există deja `tu4/rezultate/S29/<P>_VERIFICARE_*.json`), scrie JSON-ul în `tu4/rezultate/S29/` (0444) și returnează
rc 0 = PASS, 1 = FAIL, 3 = UNKNOWN (fereastră).

**P0 — starea înainte (toate):** (1) hash-urile perechii `125934Z` = fișierul de verificare (la rădăcina `predari/`), cu
`canon_once`/`supl_once`; (2) B0: log `566bccb7…`, Q7L `548274d1…` PASS 11/11, V0L `7b6ac8b2…` 28/29 numai `incidente`;
(3) sha sigiliilor S27 = `ce2a9f18…`, S28 = `0b4fd79b…`, A01 = `b44ffea3…`, iar sha `AMENDAMENT_S28_A01.md` = valoarea din
sigiliul A01; (4) toate `frozen_hashes` din sigiliul S29 = valorile curente; (5) incidentele = cele 9, fără `S26_*`/`S28_*`/
`S29_*`; (6) 27/27 surse Rust 0444 cu sha = manifestul S22; (7) `verifica_s29.py` are modul 0444.

**P1 — maparea UTC/EST cu trei martori (toate):**
(1) `timedatectl show -p Timezone --value` = `America/New_York`;
(2) zoneinfo: NY are offset −4 h la 2026-11-01T05:59:59Z și −5 h la 06:00:00Z; Europe/Bucharest are offset +2 h la fiecare
oră din intervalul 2026-10-26T00:00Z – 2026-11-02T00:00Z;
(3) `zdump -v -c 2026,2027 America/New_York` (rc 0) conține exact liniile tranziției
`Sun Nov  1 05:59:59 2026 UT = Sun Nov  1 01:59:59 2026 EDT isdst=1 gmtoff=-14400` și
`Sun Nov  1 06:00:00 2026 UT = Sun Nov  1 01:00:00 2026 EST isdst=0 gmtoff=-18000`; `zdump -v -c 2026,2027 Europe/Bucharest`
(rc 0) are ca ultimă linie datată exact `Sun Oct 25 01:00:00 2026 UT = Sun Oct 25 03:00:00 2026 EET isdst=0 gmtoff=7200`
(nicio tranziție ulterioară în 2026);
(4) systemd: pentru fiecare dintre cele 3 linii `OnCalendar=` ale timerului instalat (= `tu4/systemd/ql649-tu4-emitere.timer`
prin sha), `systemd-analyze calendar --iterations=4 --base-time='2026-10-29 14:00:00 UTC'` (rc 0); reuniunea momentelor
`(in UTC)` din intervalul deschis (2026-10-29T14:00Z, 2026-11-01T14:00Z) = exact cele **9** sloturi (vin 30, sâm 31,
dum 1 nov × 06:20Z, 10:20Z, 13:20Z) — confirmarea independentă a regulii A01 —, iar linia de oră locală
(`Next elapse:` sau `Iteration #k:`) care precedă `(in UTC): Sun 2026-11-01 13:20:00 UTC` este `Sun 2026-11-01 08:20:00 EST`,
iar cea pentru 06:20Z din 1 nov este `Sun 2026-11-01 01:20:00 EST`;
(5) sub H_BLOCAT (arhiva LIVE cu `last_date` 2026-10-25), replica independentă a regulii `emite.py`
(`postponed` cât timp arhiva e incompletă și slotul < fereastra finală 13:00Z; emisie dacă slotul < cutoff 14:00Z) dă pe
cele 9 sloturi systemd exact 8 × `postponed` + 1 × emisie (13:20Z);
(6) `systemctl --user show ql649-tu4-emitere.timer -p NextElapseUSecRealtime --value` = `Thu 2026-10-29 02:20:00 EDT`
(= 06:20Z, primul slot după acum; valabil cât timp P1 rulează înainte de 2026-10-29T06:20Z);
(7) fereastra de duminică: `sonda_s27.window` dă interzis la 13:20Z și 13:35Z și liber la fiecare minut 13:36Z…13:57Z (22
minute), iar regula minutelor exclude 13:58Z; fiecare minut 13:36Z…13:57Z se afișează în NY ca `2026-11-01 08:MM EST`
(MM = 36…57);
(8) se scrie `tu4/rezultate/S29/FISA_DUMINICA_S29.json` (0444) cu §2, martorii și comenzile exacte.

**P2 — neintervenție după (toate):** (1) `frozen_hashes` S29 neschimbate; (2) hash-urile externe (garda, unitatea,
timerele) = cele din sigiliul S29 (= cele din sigiliul S28); (3) linia 163 a `loto_romania/cohorta.py` conține exact
`raise ValueError('Model/environment changed after protocol freeze: ' + model)` (citire, fără scriere); (4) 27/27 surse 0444
cu sha; (5) incidentele = cele 9; (6) `LANT.jsonl` = instantaneul din sigiliu; (7) `tu4/s29/` conține numai
`verifica_s29.py`, 0444; (8) `loto-actualizare.timer` și `ql649-tu4-emitere.timer` `active`.

**Q7L final:** după P2, primul pas `primul_pas_S26.sh` neschimbat, în afara ferestrelor ⇒ Q7L PASS 11/11, V0L 28/29 numai
`incidente`, 587/587, 61/61, `DL_RC=0`, `DECONTARE_PENDING`, `B5_PENDING` + `B2_RC=0`.

## 4. Verdict

- `S29_PASS` = P0 ∧ P1 ∧ P2 ∧ Q7L final.
- `S29_FAIL` = oricare FAIL; se înregistrează `tu4/rezultate/S29/INCIDENT_S29_NN.json`, fără reglaje și fără repetare cu
  alte praguri.
- `UNKNOWN` (fereastră, SSD nemontat) nu devine PASS.
- `S29_PASS` NU înseamnă că decontarea sau emisia vor avea loc la timp și NU repară garda `gpu-v1`.
- Limita martorilor (declarată): zoneinfo, `zdump` și systemd pot citi aceeași bază tzdata a sistemului; sunt independenți
  de codul QL649, nu de tzdata.

Raport: `tu4/rezultate/S29/RAPORT_S29.md`. Fișiere noi permise: `tu4/PROTOCOL_QUANTUM_S29.md`, `tu4/SIGILIU_TU4_S29.json`,
`tu4/rezultate/S29/*`, `tu4/s29/verifica_s29.py`, logul primului pas în `tu4/rezultate/S25/` (scrierile uzuale ale primului
pas), `predari/OPERATIV.md`, Mesajul 80 în `predari/MESAJE_UTILIZATOR_QL649.md` și perechea de predare emisă de
`predari/genereaza_predare.py`. Fără `sudo`, fără `chmod u+w` pe fișiere înghețate, fără scrieri în
tribunal/systemd/surse Rust/produsul principal (`loto_romania/`, `loto`), fără `tu4/incidente/S26_*`/`S28_*`/`S29_*`.
Git: numai `./dev-git status`.
