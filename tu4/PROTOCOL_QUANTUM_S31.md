# PROTOCOL TU4-S31 — detecția post-extragere de joi (2026-10-29) și alinierea decontării; re-confirmarea fișei de duminică

Cererea = Mesajul 82 (2026-10-29T19:14:01+02:00 = 17:14:01Z = 13:14:01 EDT). Protocolul și sigiliul
(`tu4/SIGILIU_TU4_S31.json`) se scriu ÎNAINTEA oricărui cod S31 (`tu4/s31/`) și a oricărei verificări S31. Singurul cod scris
înainte de sigiliu este scriptul de sigilare `tu4/rezultate/S31/sigileaza_s31.py` (ca în S27–S30), care nu calculează decât
hash-uri.

`positive_claims_allowed=false`. S31 este numai observație și conservare: confirmă, după extragerea de joi, starea decontării
2026-10-29 așa cum o raportează sonda înghețată S27 (zero scrieri), re-confirmă fără rescriere fișa de duminică
`FISA_DUMINICA_S29.json` și dovedește neintervenția. Nu citește numerele extragerilor, nu calculează scoruri, nu emite, nu
decontează, nu rulează judecătorul/emițătorul/actualizarea, nu rulează binarul Rust în afara primului pas neschimbat și nu
prezice nimic. Calcul clasic pe metadate (hash-uri, conversii de fus orar, comparații de câmpuri).

**Corecții de premisă (declarate, fără a adopta formulările):**
1. Handoff-ul `HANDOFF_QL649_20261028T140923Z.md` se află în `predari/`, nu direct în rădăcina `quantum_lab_649/`. Hash-urile
   (HANDOFF `40f1acdf…`, PROMPT `38d431c6…`) coincid cu `predari/VERIFICARE_PREDARE_20261028T140923Z.json`.
2. „Suntem după 16:45 UTC”: corect (cererea la 17:14:01Z). „`AVERTISMENT_DECONTARE_BLOCATA` generată automat după 18:30Z”:
   la momentul cererii și al primului pas (17:14:44Z) era ÎNAINTE de 18:30Z, deci avertismentul nu putea apărea încă; sonda B0
   a dat corect `FAZA_0_ASTEAPTA_DECONTAREA` fără el (condiția din cod: `now ≥ extragere + 2 h`, `n_dec < 3`, arhiva LIVE <
   2026-10-29). Confirmarea avertismentului se face în M2, la ≥ 18:34:00Z (după minutele excluse [:28, :34)).
3. „Din cauza blocării arhivei LIVE … de către garda `gpu-v1`”: inventarul read-only (jurnalul `loto-actualizare`, fără
   investigarea cauzei) arată că mesajul gărzii (`Model/environment changed after protocol freeze: gpu-v1`) apare ultima dată
   la 2026-10-29T13:30:28Z; de la rularea de 14:00Z, `loto-actualizare` se termină cu `Result=success` (14:05:01Z „Așteptăm
   publicarea oficială completă”; apoi „Colectare verificată; datele și variantele sunt neschimbate”). Cele 13 hash-uri externe
   (inclusiv `loto_romania/cohorta.py`, unitatea, drop-in-urile, timerele) sunt IDENTICE cu sigiliul S30, iar linia 163 conține
   exact textul gărzii: nu a existat intervenție pe fișiere; cauza dispariției mesajului NU se investighează (rămâne pentru
   sesiunea dedicată). Consecință: arhiva LIVE la 2026-10-25 nu mai este demonstrabil cauzată de gardă; este compatibilă și cu
   faptul că extragerea din 29 oct nu a intrat încă în colectarea oficială. Textul avertismentului din sonda înghețată („vezi
   garda gpu-v1”) este un literal înghețat; atribuirea cauzei NU este revalidată de S31. De aceea S31 preînregistrează AMBELE
   ramuri ale `CALENDAR_S28.json`: H_BLOCAT (arhiva < 2026-10-29) și H_ACTUALIZAT (arhiva conține 2026-10-29 ⇒ judecătorul
   înghețat poate deconta automat la :00:30/:30:30, fără nicio intervenție a agentului).
4. „Confirmă că starea rămâne `DECONTARE_PENDING`”: S31 o confirmă numai dacă se observă (ramura H_BLOCAT). Dacă arhiva
   avansează între timp (H_ACTUALIZAT), S31 raportează că premisa NU s-a confirmat, fără a forța sau a împiedica decontarea.
   „Nicio scriere sau decontare activă”: S31 nu rulează `judecator.py`, `emite.py` sau `loto`, nu editează tribunalul/LANT și
   nu atinge timerele. Primul pas neschimbat scrie, ca de obicei, numai rapoarte de verificare (`tu4/rezultate/S24/
   DECONTARE_20261029_<UTC>.json/.md`, Q0/Q1/Q4, `tu4/rezultate/S25/*`) — rapoarte, nu decontări în tribunal.
5. „După trecerea automată la EST”: trecerea laptopului (America/New_York) EDT→EST are loc duminică 2026-11-01T06:00Z; joi
   laptopul este încă pe EDT. Fișa de duminică NU se rescrie; re-confirmarea este integritate + conținut + martori.
6. Garda externă `loto_romania/cohorta.py:163` rămâne complet NEATINSĂ (citire + hash). Directoarele `tu4/incidente/S26_*` și
   `S28_01` rămân NECREATE până la închiderea C1. Orice incident S31 se înregistrează în `tu4/rezultate/S31/INCIDENT_S31_NN.json`.

## 0. Inventar read-only (înainte de protocol, baza B0)

| Element | Valoare constatată |
|---|---|
| Predarea `140923Z` | HANDOFF `40f1acdf…`, PROMPT `38d431c6…` = `predari/VERIFICARE_PREDARE_20261028T140923Z.json`; canon `74641a9d…`, supliment `485b6d28…` |
| Fereastra la sosirea cererii | 17:14:01Z: liberă (extragerea 16:30Z ±15 min s-a încheiat la 16:45Z; următoarea emisie vineri 06:20Z) |
| Sonda S27 (17:14:44Z) | `SONDA_RC=0`, `FAZA_0_ASTEAPTA_DECONTAREA`; G1 9 incidente, G2 27/27 0444+sha, G3 `c20fdcd2…`, T1 LANT 3 linii, T2 `DECONTARE_PENDING` 0/3, T4 `last_date` 2026-10-25 ×3 (`updated_utc` 14:05:01Z), judecătorul 17:00:33Z `nothing_to_settle`, `loto-actualizare` `Result=success`; `AVERTISMENT_EMISIE_AMANATA`; fără `AVERTISMENT_DECONTARE_BLOCATA` (înainte de 18:30Z) |
| Primul pas (B0) | `tu4/rezultate/S25/primul_pas_S26_20261029T171444Z.log` (`9c4ff9e8…`): sha-urile celor 11 fișiere = handoff, 14 × `drift []`, `LANT_PREFIX_S20 OK linii 3`, 61/61, `c20fdcd2…`, 587/587, `PARITY_RC=0`, `DL_RC=0`, Q0/Q1 PASS, Q4 `UNKNOWN` (fără repornire), `DECONTARE_PENDING` (`DECONTARE_20261029_20261029T171753Z.json`, `21afe07a…`), `B5_PENDING` + `B2_RC=0`, `SCUT_LANT OK linii 3 []`, A0 PASS |
| V0L / Q7L | `V0L_VERIFICARE_20261029T171753Z.json` (`fa8dbf08…`) 28/29, singurul FAIL `incidente`; `Q7L_VERIFICARE_20261029T171753Z.json` (`952eafed…`) PASS 11/11 |
| Sigilii | S27 `ce2a9f18…`, S28 `0b4fd79b…`, A01 `b44ffea3…`, S29 `911af09c…`, S30 `4cbdb516…` (161 înghețate, 13 externe) |
| Fișe | `FISA_DUMINICA_S29.json` `2b597a22…` (0444); `FISA_JOI_S30.json` `0deeb89e…`; `ALINIERE_FISE_S30.json` `65ef123c…`; `CALENDAR_S28.json` `22e10ea6…` |
| Externe / LIVE | 13/13 hash-uri externe = S30; linia 163 = textul gărzii; arhiva LIVE `last_date` 2026-10-25 ×3; `LANT.jsonl` 3 linii, `51aa92ce…`; jurnal: garda ultima dată 13:30:28Z, `success` de la 14:05:01Z (vezi corecția 3) |

## 1. Ferestre interzise (neschimbate față de S27–S30)

Nicio rulare S31 (verificare, sondă, primul pas) în ±15 min (inclusiv) față de emisiile 08:20/12:20/15:20
Europe/Bucharest sau de extragerea 2026-10-29T16:30Z. Verificatorul S31 refuză pornirea și în minutele [:58, :04) și
[:28, :34). Fereastra se calculează cu funcția înghețată `sonda_s27.window` (import fără modificare). În fereastră: rc 3,
`UNKNOWN_FEREASTRA`, fără scrieri.

## 2. Ramurile decontării de joi (preînregistrate)

Starea arhivei se citește în M2 din `tu3/date/live/CURRENT_LIVE.json` (înainte și după sondă; dacă diferă: `UNKNOWN_TRANZITIE`,
rc 3, se scrie raportul M2 cu verdict `UNKNOWN`, iar M2 se poate relua O SINGURĂ dată după următoarea rulare :00/:30).

- **H_BLOCAT** (min `last_date` < 2026-10-29): așteptat `SONDA_RC=0`, `FAZA_0_ASTEAPTA_DECONTAREA`, linia
  `AVERTISMENT_DECONTARE_BLOCATA` prezentă (M2 rulează la ≥ 18:34Z), T2 `DECONTARE_PENDING 0/3`, T3 `0/3`, T1 `linii=3`, T5 OK,
  ultima rulare a judecătorului `nothing_to_settle`. Rezultat: `CONFIRMAT_PENDING_CU_AVERTISMENT` (premisa cererii confirmată).
- **H_ACTUALIZAT** (min `last_date` ≥ 2026-10-29): așteptat `SONDA_RC=0`, faza ∈ {`FAZA_0` (judecătorul nu a rulat încă după
  actualizare), `FAZA_1`, `FAZA_2`}, FĂRĂ `AVERTISMENT_DECONTARE_BLOCATA`; decontarea se face numai de judecătorul înghețat,
  automat. Rezultat: `NECONFIRMAT_H_ACTUALIZAT` (premisa „rămâne PENDING” nu se confirmă; NU este FAIL S31 și NU este PASS al
  premisei).
- Orice `ANOMALIE`/`ABATERE`, `SONDA_RC≠0`, o fază incompatibilă cu ramura sau o scriere a sondei = FAIL.

## 3. Criterii (praguri fixate înainte)

Verificatorul `tu4/s31/verifica_s31.py` (0444) are subcomenzile `m0`, `m1`, `m2`, `m3`; fiecare rulează O SINGURĂ DATĂ
(refuză dacă există deja `tu4/rezultate/S31/<M>_VERIFICARE_*.json` cu verdict PASS/FAIL; excepția `UNKNOWN_TRANZITIE` de la §2),
scrie JSON-ul în `tu4/rezultate/S31/` (0444) și returnează rc 0 = PASS, 1 = FAIL, 3 = UNKNOWN.

**M0 — starea înainte (toate):** (1) hash-urile perechii `140923Z` = fișierul de verificare (la rădăcina `predari/`), cu
`canon_once`/`supl_once`; (2) B0 S31: log `9c4ff9e8…`, Q7L `952eafed…` PASS 11/11, V0L `fa8dbf08…` 28/29 numai `incidente`,
decontarea B0 `21afe07a…` cu `DECONTARE_PENDING`, `n_decontate` 0; (3) sha sigiliilor S27 = `ce2a9f18…`, S28 = `0b4fd79b…`,
A01 = `b44ffea3…`, S29 = `911af09c…`, S30 = `4cbdb516…`, iar sha `AMENDAMENT_S28_A01.md` = valoarea din sigiliul A01;
(4) toate `frozen_hashes` din sigiliul S31 = valorile curente; (5) incidentele = cele 9, fără `S26_*`/`S28_*`/`S29_*`/`S30_*`/
`S31_*`; (6) 27/27 surse Rust 0444 cu sha = manifestul S22; (7) sha sigiliului S31 = valoarea din verificator și
`verifica_s31.py` are modul 0444.

**M1 — re-confirmarea fișei de duminică (toate; independent de momentul rulării, cu excepția (7)):**
(1) `FISA_DUMINICA_S29.json`: sha = `2b597a22…` = `fisa_sha256` din P1 S29 (PASS 15/15), mod 0444; K1 S30 (`1a18f05a…`) PASS
8/8 și `ALINIERE_FISE_S30.json` (`65ef123c…`) cu `fisa_S29_rescrisa` = false;
(2) câmpurile: `verificare_C1_B5.utc` = [`2026-11-01T13:36:00Z`, `2026-11-01T13:57:59Z`], `laptop` = [`08:36 EST`,
`08:57 EST`], `strict` = true; `slot_final_emisie` 13:20Z / `15:20 EET` / `08:20 EST`, interzis [13:05Z, 13:35Z];
`tranzitie_laptop.utc` = `2026-11-01T06:00:00Z`; `positive_claims_allowed` = false;
(3) zoneinfo: 13:36:00Z și 13:57:59Z în America/New_York = `08:36:00 EST` și `08:57:59 EST`; fiecare minut 13:36Z…13:57Z (22)
= `2026-11-01 08:MM EST`; 13:20Z = `08:20 EST` = `15:20 EET`;
(4) `zdump -v -c 2026,2027 America/New_York` (rc 0) conține tranziția 05:59:59 UT EDT / 06:00:00 UT EST din 1 nov; ultima linie
datată Europe/Bucharest = tranziția 2026-10-25T01:00Z în EET;
(5) fereastra: `sonda_s27.window` interzis la 13:20Z și 13:35Z, liber la fiecare minut 13:36Z…13:57Z, regula minutelor
exclude 13:58Z;
(6) robustețea față de ramuri: fereastra C1/B5 începe după ambele momente posibile ale emisiei 2026-11-01 — vineri
2026-10-30T06:20Z (prima fereastră de emisie dacă arhiva se completează, H_ACTUALIZAT) și duminică 13:20Z (slotul final,
H_BLOCAT) — și după sfârșitul ferestrei interzise a slotului final (13:35Z); deci fișa rămâne valabilă în ambele ramuri;
(7) acum (momentul M1, joi) laptopul e încă pe EDT (offset America/New_York = −4 h): trecerea la EST nu a avut loc încă și
este programată la 2026-11-01T06:00Z.

**M2 — detecția post-extragere de joi (toate; numai la ≥ 2026-10-29T18:30:00Z, altfel rc 3 `UNKNOWN_PREMATUR` fără scrieri):**
(1) arborele (căi, mărimi, sha) al `tu4/tribunal/`, `tu4/rezultate/S24/` și `tu3/date/live/CURRENT_LIVE.json` este identic
înainte și după rularea sondei (sonda nu scrie nimic);
(2) sonda înghețată `tu4/s27/sonda_s27.py` (sha = S30) rulată ca subproces `/usr/bin/python3 -B` dă rc 0, fără `ABATERE`/
`ANOMALIE`; ieșirea se salvează integral în `tu4/rezultate/S31/SONDA_M2_<UTC>.txt` (0444);
(3) ramura (§2) se determină din `CURRENT_LIVE.json`, citit identic înainte și după;
(4) faza și prezența/absența `AVERTISMENT_DECONTARE_BLOCATA` sunt cele ale ramurii (§2);
(5) H_BLOCAT: T2 `DECONTARE_PENDING 0/3`, T3 `0/3`, T1 `linii=3`, T5 OK și ultima rulare a judecătorului `nothing_to_settle`;
H_ACTUALIZAT: T5 OK și T3 `0/3` (emisia nu are loc joi seara);
(6) ultimul `tu4/rezultate/S24/DECONTARE_20261029_*.json` este cel din B0 (`21afe07a…`, `DECONTARE_PENDING`): S31 nu a produs
alte rapoarte de decontare între B0 și M2;
(7) informativ (fără prag): `systemctl --user show loto-actualizare.service -p Result` și dacă ultimele 40 de linii de jurnal
ale unității conțin textul gărzii `gpu-v1` (observație de stare, nu investigarea cauzei).

**M3 — neintervenție după (toate):** (1) `frozen_hashes` S31 neschimbate; (2) cele 13 hash-uri externe = cele din sigiliul S31
(= S30); (3) linia 163 a `loto_romania/cohorta.py` = textul gărzii (citire); (4) 27/27 surse 0444 cu sha; (5) incidentele =
cele 9; (6) `LANT.jsonl` = instantaneul din sigiliu (emisia nu are loc joi); (7) `tu4/s31/` conține numai `verifica_s31.py`,
0444; (8) `loto-actualizare.timer` și `ql649-tu4-emitere.timer` `active`; (9) `FISA_DUMINICA_S29.json` tot `2b597a22…`, 0444,
și `FISA_JOI_S30.json` tot `0deeb89e…`.

**Q7L final:** după M3, primul pas `primul_pas_S26.sh` neschimbat, în afara ferestrelor ⇒ Q7L PASS 11/11, V0L 28/29 numai
`incidente`, 587/587, 61/61, `DL_RC=0`; decontarea `DECONTARE_PENDING` (H_BLOCAT) sau starea judecătorului (H_ACTUALIZAT),
`B5_PENDING` + `B2_RC=0`.

## 4. Verdict

- `S31_PASS` = M0 ∧ M1 ∧ M2 ∧ M3 ∧ Q7L final; raportul precizează rezultatul M2: `CONFIRMAT_PENDING_CU_AVERTISMENT` sau
  `NECONFIRMAT_H_ACTUALIZAT`.
- `S31_FAIL` = oricare FAIL; se înregistrează `tu4/rezultate/S31/INCIDENT_S31_NN.json`, fără reglaje și fără repetare cu alte
  praguri.
- `UNKNOWN` (fereastră, prematur, tranziție, SSD nemontat) nu devine PASS.
- `S31_PASS` NU înseamnă că decontarea sau emisia vor avea loc la timp, NU repară și NU explică garda `gpu-v1` și NU închide C1.
- Limitele martorilor (declarate): zoneinfo și `zdump` pot citi aceeași bază tzdata; sunt independenți de codul QL649, nu de
  tzdata. Observația din jurnal (corecția 3) este o constatare de stare, nu o diagnoză.

Raport: `tu4/rezultate/S31/RAPORT_S31.md`. Fișiere noi permise: `tu4/PROTOCOL_QUANTUM_S31.md`, `tu4/SIGILIU_TU4_S31.json`,
`tu4/rezultate/S31/*`, `tu4/s31/verifica_s31.py`, logul primului pas în `tu4/rezultate/S25/` (și scrierile uzuale ale primului
pas), `predari/OPERATIV.md`, Mesajul 82 în `predari/MESAJE_UTILIZATOR_QL649.md` și perechea de predare emisă de
`predari/genereaza_predare.py`. Fără `sudo`, fără `chmod u+w` pe fișiere înghețate, fără scrieri în
tribunal/systemd/surse Rust/produsul principal (`loto_romania/`, `loto`), fără `tu4/incidente/S26_*`/`S28_*`/`S29_*`/`S30_*`/
`S31_*`. Git: numai `./dev-git status`.
