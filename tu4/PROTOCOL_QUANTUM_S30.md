# PROTOCOL TU4-S30 — conservare și alinierea fișelor de timp (duminică C1/B5; joi decontare PENDING sub H_BLOCAT)

Cererea = Mesajul 81 (2026-10-28T09:50:35-04:00 = 13:50:35Z). Protocolul și sigiliul (`tu4/SIGILIU_TU4_S30.json`) se scriu
ÎNAINTEA oricărui cod S30 (`tu4/s30/`) și a oricărei verificări S30. Singurul cod scris înainte de sigiliu este scriptul de
sigilare `tu4/rezultate/S30/sigileaza_s30.py` (ca în S27–S29), care nu calculează decât hash-uri.

`positive_claims_allowed=false`. S30 este numai conservare (dovada de neintervenție) și aliniere documentară: re-confirmă,
fără a o rescrie, fișa de duminică `FISA_DUMINICA_S29.json`, o aliniază cu `CALENDAR_S28.json` și cu regula de duminică din
sigiliul S29, și înregistrează formal, într-o fișă nouă, starea așteptată a decontării de joi 2026-10-29 sub H_BLOCAT
(`DECONTARE_PENDING`), acceptată ca atare, fără intervenție activă. Nu citește numerele extragerilor, nu calculează scoruri, nu
emite, nu decontează, nu rulează binarul Rust în afara primului pas neschimbat și nu prezice nimic. Calculul este clasic
(hash-uri, conversii de fus orar, comparații de câmpuri); volumul este mic (metadate), nu „date de volum mare”.

**Corecții de premisă (declarate, fără a adopta formulările):**
1. „PROTOCOL_QUANTUM_S30.md”: corect; indexul curent este S30 (S29 închis `S29_PASS`). Hash-ul sigiliului S30 nu se poate
   alege dinainte; se publică după scriere.
2. „Re-confirmarea înregistrărilor din FISA_DUMINICA_S29.json”: fișa este 0444 și sigilată prin P1 S29 (`2b597a22…`). S30
   NU o rescrie și NU emite o fișă de duminică nouă; re-confirmarea înseamnă (a) integritate (sha, mod, P1 PASS 15/15),
   (b) conținut (fereastra STRICTĂ 13:36:00Z–13:57:59Z = 08:36–08:57 EST, slotul final 13:20Z = 08:20 EST, cele 9 sloturi)
   re-derivat independent cu zoneinfo și `zdump` (martori independenți de timpul curent), (c) aliniere cu `CALENDAR_S28.json`
   și cu `sunday_rule` din sigiliul S29. Martorul systemd cu `NextElapseUSecRealtime` NU se reia (depinde de momentul rulării).
3. „Decontarea de joi (după 16:45Z) va fi marcată ca PENDING”: decontarea este deja `DECONTARE_PENDING` (0/3) și nu este
   „marcată” de nimeni: este starea pasivă a judecătorului înghețat cât timp arhiva LIVE nu conține 2026-10-29. Extragerea
   este la 16:30Z (18:30 EET, 12:30 EDT); fereastra interzisă ±15 min se termină la 16:45Z inclusiv. După 16:45Z, sub H_BLOCAT,
   starea rămâne `DECONTARE_PENDING`; sonda dă `AVERTISMENT_DECONTARE_BLOCATA` de la 18:30Z (≥ 2 h după extragere); după 14
   zile (GRACE) devine `VOID` (CALENDAR_S28). Dacă între timp garda este reparată în sesiunea dedicată și arhiva se
   actualizează, se aplică ramura H_ACTUALIZAT din CALENDAR_S28 — nu de S30.
4. „Amânând intervențiile active până la deblocarea sesiunii dedicate”: S30 nu planifică, nu pornește și nu pregătește
   sesiunea dedicată. Aceasta cere decizia utilizatorului și protocol propriu.
5. Garda externă `loto_romania/cohorta.py:163` (`raise ValueError('Model/environment changed after protocol freeze: ' +
   model)`) rămâne complet NEATINSĂ: nu se modifică, nu se repară, nu se legitimează, nu se investighează cauza. S30 o
   îngheață prin hash (cu unitatea și timerele) ca dovadă de neintervenție.
6. Directoarele `tu4/incidente/S26_*` și `S28_01` rămân NECREATE până la închiderea C1. Orice incident S30 se înregistrează
   în `tu4/rezultate/S30/INCIDENT_S30_NN.json`.

## 0. Inventar read-only (înainte de protocol, baza B0)

| Element | Valoare constatată |
|---|---|
| Predarea `134819Z` | HANDOFF `778d74fb…`, PROMPT `467d9209…` = `predari/VERIFICARE_PREDARE_20261028T134819Z.json`; canon `74641a9d…`, supliment `6e8b52da…` |
| Fereastra la sosirea cererii | 13:50:35Z: liberă (emisia 13:20Z ±15 min s-a încheiat la 13:35Z; următoarea emisie joi 06:20Z) |
| Sonda S27 (13:50:57Z) | `SONDA_RC=0`, `FAZA_0_ASTEAPTA_DECONTAREA`; G1 9 incidente, G2 27/27 0444+sha, G3 `c20fdcd2…`, T1 LANT 3 linii, T2 `DECONTARE_PENDING` 0/3, T4 `last_date` 2026-10-25 ×3, `loto-actualizare` `Result=exit-code`; `AVERTISMENT_EMISIE_AMANATA` |
| Primul pas (B0) | `tu4/rezultate/S25/primul_pas_S26_20261028T135057Z.log` (`558bfada…`): sha-urile celor 9 fișiere = handoff, 14 × `drift []`, `LANT_PREFIX_S20 OK linii 3`, 61/61, `c20fdcd2…`, 587/587, `PARITY_RC=0`, `DL_RC=0`, Q0/Q1 PASS, Q4 `UNKNOWN`, `DECONTARE_PENDING` (`DECONTARE_20261029_20261028T135343Z.json`, `99a289d5…`), `B5_PENDING` + `B2_RC=0`, `SCUT_LANT OK linii 3 []`, A0 PASS |
| V0L / Q7L | `V0L_VERIFICARE_20261028T135344Z.json` (`bbc1a248…`) 28/29, singurul FAIL `incidente`; `Q7L_VERIFICARE_20261028T135344Z.json` (`229c6b5b…`) PASS 11/11 |
| Sigilii | S27 `ce2a9f18…`, S28 `0b4fd79b…`, A01 `b44ffea3…`, S29 `911af09c…` (144 înghețate, 13 externe) |
| Fișe | `FISA_DUMINICA_S29.json` `2b597a22…` (0444); `CALENDAR_S28.json` (înghețat în S29); `RAPORT_S29.md` `22c34678…` |
| Garda externă / LIVE | linia 163 citită read-only; arhiva LIVE `last_date` 2026-10-25 ×3; `LANT.jsonl` 3 linii, 913 B, `51aa92ce…` |

## 1. Ferestre interzise (neschimbate față de S27–S29)

Nicio rulare S30 (verificare, sondă, primul pas) în ±15 min (inclusiv) față de emisiile 08:20/12:20/15:20
Europe/Bucharest sau de extragerea 2026-10-29T16:30Z. Verificatorul S30 refuză pornirea și în minutele [:58, :04) și
[:28, :34). Fereastra se calculează cu funcția înghețată `sonda_s27.window` (import fără modificare). În fereastră: rc 3,
`UNKNOWN_FEREASTRA`, fără scrieri.

## 2. Fișele de timp (aliniere; nicio fișă existentă nu se rescrie)

- **Duminică 2026-11-01 (neschimbată, S29 §2):** verificarea C1/B5 STRICT 13:36:00Z–13:57:59Z (08:36–08:57 EST), ordinea
  `date -u` ⇒ sonda (`FAZA_4`) ⇒ primul pas neschimbat + `verifica_s25.py q7l`. Ratare sau `late` ⇒ C1/B5 `PENDING`/`UNKNOWN`;
  altă fereastră numai cu protocol nou.
- **Joi 2026-10-29 (nou, fișă S30):** extragerea 16:30Z (18:30 EET, 12:30 EDT); interzis 16:15:00Z–16:45:00Z. După 16:45Z,
  sub H_BLOCAT (arhiva LIVE `last_date` < 2026-10-29), decontarea 2026-10-29 rămâne `DECONTARE_PENDING`, acceptată; de la
  18:30Z sonda afișează `AVERTISMENT_DECONTARE_BLOCATA`; `VOID` după 14 zile (GRACE). Fără intervenție activă: nu se repară
  garda, nu se forțează actualizarea, nu se decontează manual, nu se editează LANT/tribunalul. Sonda se poate rula oricând în
  afara ferestrelor (zero scrieri); primul pas numai în afara ferestrelor.
- Fișierele noi: `tu4/rezultate/S30/FISA_JOI_S30.json` și `tu4/rezultate/S30/ALINIERE_FISE_S30.json` (0444), scrise de K1/K2.

## 3. Criterii (praguri fixate înainte)

Verificatorul `tu4/s30/verifica_s30.py` (0444) are subcomenzile `k0`, `k1`, `k2`, `k3`; fiecare rulează O SINGURĂ DATĂ
(refuză dacă există deja `tu4/rezultate/S30/<K>_VERIFICARE_*.json`), scrie JSON-ul în `tu4/rezultate/S30/` (0444) și
returnează rc 0 = PASS, 1 = FAIL, 3 = UNKNOWN (fereastră).

**K0 — starea înainte (toate):** (1) hash-urile perechii `134819Z` = fișierul de verificare (la rădăcina `predari/`), cu
`canon_once`/`supl_once`; (2) B0: log `558bfada…`, Q7L `229c6b5b…` PASS 11/11, V0L `bbc1a248…` 28/29 numai `incidente`,
decontarea B0 `99a289d5…` cu `DECONTARE_PENDING`; (3) sha sigiliilor S27 = `ce2a9f18…`, S28 = `0b4fd79b…`, A01 = `b44ffea3…`,
S29 = `911af09c…`, iar sha `AMENDAMENT_S28_A01.md` = valoarea din sigiliul A01; (4) toate `frozen_hashes` din sigiliul S30
= valorile curente; (5) incidentele = cele 9, fără `S26_*`/`S28_*`/`S29_*`/`S30_*`; (6) 27/27 surse Rust 0444 cu sha =
manifestul S22; (7) sha sigiliului S30 = valoarea din verificator și `verifica_s30.py` are modul 0444.

**K1 — re-confirmarea și alinierea fișei de duminică (toate; independent de momentul rulării):**
(1) `FISA_DUMINICA_S29.json`: sha = `2b597a22…` = `fisa_sha256` din `P1_VERIFICARE_20261028T134355Z.json` (PASS 15/15),
mod 0444;
(2) câmpurile fișei: `verificare_C1_B5.utc` = [`2026-11-01T13:36:00Z`, `2026-11-01T13:57:59Z`], `laptop` = [`08:36 EST`,
`08:57 EST`], `strict` = true, `ratare`/`late` = textele PENDING/UNKNOWN; `slot_final_emisie` = 13:20Z / `15:20 EET` /
`08:20 EST`, interzis [13:05Z, 13:35Z]; `tranzitie_laptop.utc` = `2026-11-01T06:00:00Z`; `positive_claims_allowed` = false;
(3) zoneinfo: capetele 13:36:00Z și 13:57:59Z se afișează în America/New_York ca `08:36:00 EST` și `08:57:59 EST`, fiecare
minut 13:36Z…13:57Z (22) ca `2026-11-01 08:MM EST`; 13:20Z ca `08:20 EST` și `15:20 EET`;
(4) cele 9 rânduri `sloturi_H_BLOCAT`: `laptop_zoneinfo` și `bucuresti` = re-derivarea zoneinfo a `slot_utc`; `laptop_systemd`
are aceeași dată/oră/abreviere ca `laptop_zoneinfo`; o replică nouă a regulii `emite.py` (postponed cât timp arhiva e
incompletă și slotul < fereastra finală 13:00Z; emisie dacă < cutoff 14:00Z; `last_date` 2026-10-25) dă 8 × `postponed` + 1 ×
`emisie` = coloana `H_BLOCAT` a fișei;
(5) `zdump -v -c 2026,2027 America/New_York` (rc 0) conține exact liniile tranziției 05:59:59 UT EDT / 06:00:00 UT EST (ca
S29 P1(3)), iar ultima linie datată pentru Europe/Bucharest este tranziția din 2026-10-25T01:00Z în EET;
(6) fereastra: `sonda_s27.window` interzis la 13:20Z și 13:35Z, liber la fiecare minut 13:36Z…13:57Z, regula minutelor
exclude 13:58Z;
(7) alinierea: `CALENDAR_S28.json` (sha = valoarea înghețată în S29) are aceleași 9 `slot_utc` și aceeași coloană `H_BLOCAT`
ca fișa, iar `verificare_finala_C1_B5.utc` = [13:36:00Z, 13:57:00Z] (minut-început al ultimului minut, compatibil cu
13:57:59Z); `sunday_rule` din sigiliul S29 are aceleași capete UTC/EST și `strict` = true;
(8) se scrie `tu4/rezultate/S30/ALINIERE_FISE_S30.json` (0444) cu tabelul alinierii.

**K2 — fișa de joi (decontare PENDING sub H_BLOCAT; toate):**
(1) `tu3/date/live/CURRENT_LIVE.json`: `last_date` = 2026-10-25 pentru 649, 540, joker (H_BLOCAT în vigoare; citire);
(2) zoneinfo: 2026-10-29T16:30Z = `18:30 EET` = `12:30 EDT`; `sonda_s27.window` interzis la 16:15:00Z, 16:30:00Z, 16:45:00Z și
liber la 16:46:00Z și la 18:35:00Z (după extragere; în afara regulii minutelor);
(3) decontarea curentă: ultimul `tu4/rezultate/S24/DECONTARE_20261029_*.json` (= cel din B0) are `verdict` =
`DECONTARE_PENDING`, `n_decontate` = 0; `CALENDAR_S28.json` `decontare_2026_10_29.H_BLOCAT` conține `DECONTARE_PENDING`,
`2026-10-29T18:30:00Z` și `VOID`;
(4) sursa înghețată `tu4/s27/sonda_s27.py` (sha = valoarea din S29) conține literal `AVERTISMENT_DECONTARE_BLOCATA` și
`FAZA_0_ASTEAPTA_DECONTAREA`; `tu4/judecator.py` (sha = S29) neschimbat;
(5) replica regulii: cu `last_date` = 2026-10-25 < 2026-10-29, pentru fiecare moment t ∈ {16:46Z, 17:00Z, 18:00Z, 18:30Z,
19:00Z} din 29 oct, starea așteptată = `DECONTARE_PENDING`, iar avertismentul = (t ≥ 18:30Z);
(6) se scrie `tu4/rezultate/S30/FISA_JOI_S30.json` (0444) cu §2 (joi), starea acceptată, lista intervențiilor interzise și
comenzile sondei.

**K3 — neintervenție după (toate):** (1) `frozen_hashes` S30 neschimbate; (2) hash-urile externe (garda, unitatea,
timerele) = cele din sigiliul S30 (= cele din sigiliul S29); (3) linia 163 a `loto_romania/cohorta.py` conține exact textul
gărzii (citire); (4) 27/27 surse 0444 cu sha; (5) incidentele = cele 9; (6) `LANT.jsonl` = instantaneul din sigiliu;
(7) `tu4/s30/` conține numai `verifica_s30.py`, 0444; (8) `loto-actualizare.timer` și `ql649-tu4-emitere.timer` `active`;
(9) `FISA_DUMINICA_S29.json` tot `2b597a22…`, 0444.

**Q7L final:** după K3, primul pas `primul_pas_S26.sh` neschimbat, în afara ferestrelor ⇒ Q7L PASS 11/11, V0L 28/29 numai
`incidente`, 587/587, 61/61, `DL_RC=0`, `DECONTARE_PENDING`, `B5_PENDING` + `B2_RC=0`.

## 4. Verdict

- `S30_PASS` = K0 ∧ K1 ∧ K2 ∧ K3 ∧ Q7L final.
- `S30_FAIL` = oricare FAIL; se înregistrează `tu4/rezultate/S30/INCIDENT_S30_NN.json`, fără reglaje și fără repetare cu
  alte praguri.
- `UNKNOWN` (fereastră, SSD nemontat) nu devine PASS.
- `S30_PASS` NU înseamnă că decontarea sau emisia vor avea loc la timp, NU repară garda `gpu-v1` și NU închide C1.
- Limita martorilor (declarată): zoneinfo și `zdump` pot citi aceeași bază tzdata a sistemului; sunt independenți de codul
  QL649, nu de tzdata.

Raport: `tu4/rezultate/S30/RAPORT_S30.md`. Fișiere noi permise: `tu4/PROTOCOL_QUANTUM_S30.md`, `tu4/SIGILIU_TU4_S30.json`,
`tu4/rezultate/S30/*`, `tu4/s30/verifica_s30.py`, logul primului pas în `tu4/rezultate/S25/` (scrierile uzuale ale primului
pas), `predari/OPERATIV.md`, Mesajul 81 în `predari/MESAJE_UTILIZATOR_QL649.md` și perechea de predare emisă de
`predari/genereaza_predare.py`. Fără `sudo`, fără `chmod u+w` pe fișiere înghețate, fără scrieri în
tribunal/systemd/surse Rust/produsul principal (`loto_romania/`, `loto`), fără `tu4/incidente/S26_*`/`S28_*`/`S29_*`/`S30_*`.
Git: numai `./dev-git status`.
