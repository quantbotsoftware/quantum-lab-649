# PROTOCOL TU4-S28 — alinierea protocolului la amânarea timing-ului Joker/5-40 (garda externă `gpu-v1`)

Cererea = Mesajul 79 (2026-10-28T08:44:43-04:00 = 12:44:43Z). Protocolul și sigiliul (`tu4/SIGILIU_TU4_S28.json`) se scriu
ÎNAINTEA oricărui cod S28 (`tu4/s28/`) și a oricărei verificări S28. Singurul cod scris înainte de sigiliu este scriptul
de sigilare `tu4/rezultate/S28/sigileaza_s28.py` (ca în S27), care nu calculează nimic altceva decât hash-uri.

`positive_claims_allowed=false`. S28 este numai documentare și aliniere a ferestrelor de procesare: înregistrează formal
avertismentul extern `gpu-v1`, fixează calendarul condiționat al decontării 2026-10-29 și al emisiei 2026-11-01 și
dovedește neintervenția. Nu citește numerele extragerilor, nu calculează scoruri, nu emite, nu decontează, nu rulează
binarul Rust în afara primului pas neschimbat și nu prezice nimic. Nu există „stări de vacuum” sau alt calcul cuantic:
calculul este clasic, iar verdictele C1/B5/decontare rămân EXCLUSIV ale primului pas neschimbat.

**Corecții de premisă (declarate, fără a adopta formulările):**
1. „Noul sigiliu aferent (`ce2a9f18…`)”: `ce2a9f18…` este sha256 al sigiliului **S27** (`tu4/SIGILIU_TU4_S27.json`,
   verificat la 12:45:09Z). Hash-ul unui sigiliu nou nu se poate alege dinainte (este sha256 al conținutului). S28
   verifică `ce2a9f18…` ca precondiție și îl îngheață; sigiliul S28 primește propriul hash, publicat după scriere.
2. „Suita completă de verificări de paritate hardware” = primul pas neschimbat (`primul_pas_S26.sh`: paritatea de referință
   587/587, `cargo test` 61/61, binarul `c20fdcd2…`) urmat de Q7L. Nu se adaugă nicio afirmație hardware; flagurile
   `avx2`/`fma` rămân informative (G4 din S27) și nu dovedesc execuția instrucțiunilor.
3. „Starea de decontare de joi și C1/B5 rămân PENDING”: acum (înainte de extragere) decontarea este `DECONTARE_PENDING`
   prin construcție. După extragere rămâne `PENDING` numai DACĂ arhiva LIVE nu conține 2026-10-29. S28 nu decide viitorul;
   fixează planul condiționat (ipotezele H_BLOCAT / H_ACTUALIZAT, §2) și nu transformă `PENDING`/`UNKNOWN` în PASS.
4. „Verificarea finală de duminică la 13:20 UTC”: 13:20Z este chiar slotul final de emisie (15:20 Europe/Bucharest,
   EET = UTC+2), deci se află în fereastra interzisă ±15 min (inclusiv). Verificarea finală (sonda + primul pas) se poate
   rula numai DUPĂ 13:35Z; cu regula minutelor judecătorului ([:28, :34), [:58, :04)) fereastra recomandată este
   **duminică 2026-11-01 13:36Z–13:57Z** (sau oricând mai târziu, în afara ferestrelor).
5. **Ora laptopului:** fusul sistemului este America/New_York. Duminică 2026-11-01 la 06:00Z ora locală trece din EDT
   (UTC−4) în EST (UTC−5). Deci 13:20Z = 08:20 EST, iar 13:36Z = 08:36 EST (nu 09:20/09:36 cum ar fi azi). Timerele
   QL649 folosesc explicit Europe/Bucharest și nu sunt afectate; numai citirea orei locale de către om este afectată.
6. **Garda externă `gpu-v1` NU se modifică, nu se repară și nu se legitimează în S28** (cererea explicită + regulile de
   neintervenție). Localizare constatată read-only: `loto_romania/cohorta.py` linia 163, `context()` ridică
   `ValueError('Model/environment changed after protocol freeze: ' + model)` când `prognoze.model_identity(model)` diferă
   de identitatea înghețată în cohortă; serviciul `loto-actualizare` rulează `${LOTO_RO_ROOT:-.}/loto sync --automat`.
   Cauza diferenței de identitate NU se investighează aici. Remedierea cere o sesiune dedicată separată, cu protocol
   propriu și decizia utilizatorului. S28 îngheață prin hash fișierele gărzii și ale unității, ca dovadă de neintervenție.
7. Directoarele `tu4/incidente/S26_*` rămân NECREATE (Q7L S25 înghețat ar da FAIL pe C1). Orice incident S28 se
   înregistrează în `tu4/rezultate/S28/INCIDENT_S28_NN.json`; `tu4/incidente/S28_NN/` se creează numai după închiderea C1.

## 0. Inventar read-only (înainte de protocol, baza B0)

| Element | Valoare constatată |
|---|---|
| Predarea `124151Z` | HANDOFF `493be481…`, PROMPT `da712aa1…` = `VERIFICARE_PREDARE_20261028T124151Z.json`; canon `74641a9d…`, supliment `8a9ba722…` |
| Sonda S27 (12:45:09Z) | `SONDA_RC=0`, `FAZA_0_ASTEAPTA_DECONTAREA`; G1 9 incidente, G2 27/27 0444+sha, G3 `c20fdcd2…`, T1 LANT 3 linii, T2 `DECONTARE_PENDING` 0/3, T3 0/3, T4 `last_date` 2026-10-25 ×3, `loto-actualizare` `Result=exit-code`, T5 OK; `AVERTISMENT_EMISIE_AMANATA` |
| Primul pas (B0) | `tu4/rezultate/S25/primul_pas_S26_20261028T124509Z.log` (`2a6aca6c…`): 14 × `drift []`, `LANT_PREFIX_S20 OK linii 3`, 61/61, `c20fdcd2…`, 587/587, `PARITY_RC=0`, `DL_RC=0`, Q0/Q1 PASS, Q4 `UNKNOWN`, `DECONTARE_PENDING`, `B5_PENDING` + `B2_RC=0`, `SCUT_LANT OK linii 3 []`, A0 PASS |
| V0L / Q7L | `V0L_VERIFICARE_20261028T124747Z.json` (`83f079cf…`) 28/29, singurul FAIL `incidente`; `Q7L_VERIFICARE_20261028T124747Z.json` (`2431cdb9…`) PASS 11/11 |
| Sigiliul S27 | `ce2a9f18…` (0444), 104 fișiere înghețate; perechea `120625Z` mutată byte-identic în `predari/istoric/` |
| `loto-actualizare` | 74 rulări eșuate cu `gpu-v1` în jurnal din 2026-10-25 (ultima 12:30:28Z); arhiva LIVE republicată la 12:30:29Z cu `last_date` 2026-10-25 ×3 |
| Cod sigilat citit | `emite.py`: `DRAW_T, CUTOFF_T, FINAL_T = 18:30, 16:00, 15:00` (Europe/Bucharest), `WEEKDAYS = (3, 6)`, `postponed` cât timp arhiva e incompletă și `now < final_window`; `late` dacă emisia se termină după cutoff; `judecator.py` `GRACE = 14 zile` ⇒ `VOID` |
| Timere | `ql649-tu4-emitere.timer` (`b3f0f9bf…`, identic cu `tu4/systemd/`): 08:20/12:20/15:20 Europe/Bucharest; `loto-actualizare.timer` la :00/:30 |

## 1. Ferestre interzise (fixate, neschimbate față de S27)

Nicio rulare S28 (verificare, sondă, primul pas) în ±15 min (inclusiv) față de emisiile 08:20/12:20/15:20
Europe/Bucharest (orice zi) sau de extragerea 2026-10-29T16:30Z. Verificatorul S28 refuză pornirea și în minutele
[:58, :04) și [:28, :34) (rulările actualizării/judecătorului). Fereastra este calculată cu funcția înghețată
`sonda_s27.window` (import fără modificare). În fereastră: rc 3, `UNKNOWN_FEREASTRA`, fără citiri ale tribunalului.

## 2. Calendarul condiționat (fixat; P2 îl recalculează independent)

Ipoteze: **H_BLOCAT** = garda `gpu-v1` persistă, arhiva LIVE rămâne cu `last_date` < 2026-10-29; **H_ACTUALIZAT** = arhiva
LIVE conține 2026-10-29 de la momentul X.

| Eveniment | UTC | Ora laptopului | H_BLOCAT | H_ACTUALIZAT |
|---|---|---|---|---|
| Extragerea 649/540/Joker | 2026-10-29 16:30Z (interzis 16:15–16:45Z) | 12:30 EDT | — | — |
| Decontarea 2026-10-29 | prima rulare a judecătorului după X | — | `DECONTARE_PENDING`; `AVERTISMENT_DECONTARE_BLOCATA` de la 18:30Z; `VOID` după 14 zile | `DECONTARE_COMPLETA` 3/3 (verificat cu primul pas) |
| Sloturile vin 30 / sâm 31 | 06:20Z, 10:20Z, 13:20Z | 02:20/06:20/09:20 EDT | `postponed` | emisie la primul slot ≥ X |
| Slotul dum 1 nov 08:20 / 12:20 | 06:20Z, 10:20Z | 01:20 EST*, 05:20 EST | `postponed` (< `final_window` 13:00Z) | emisie la primul slot ≥ X |
| Slotul final dum 1 nov 15:20 | 13:20Z (interzis 13:05–13:35Z) | 08:20 EST | emisie cu `warm_start_complete=false` (dacă se termină înainte de cutoff 14:00Z; altfel `late`) | deja emisă |
| **Verificarea finală C1/B5** | **dum 13:36Z–13:57Z** | 08:36–08:57 EST | sonda ⇒ `FAZA_4` ⇒ primul pas neschimbat ⇒ Q7L | sonda ⇒ `FAZA_4` imediat după emisie, în afara ferestrelor |

\* 06:20Z din 1 nov este după trecerea la EST (06:00Z), deci 01:20 EST.

Riscuri declarate (nu se reglează): sub H_BLOCAT, dacă emisia de la 13:20Z nu se termină înainte de 14:00Z, `emite.py`
dă `late` și ținta 2026-11-01 nu se emite ⇒ C1/B5 rămân `PENDING`/`UNKNOWN` (fără PASS). Decontarea nu se mai poate
face după 14 zile (`VOID`).

## 3. Criterii (praguri fixate înainte)

Verificatorul `tu4/s28/verifica_s28.py` (0444) are subcomenzile `p0`, `p1`, `p2`, `p3`; fiecare rulează O SINGURĂ DATĂ
(refuză dacă există deja `tu4/rezultate/S28/<P>_VERIFICARE_*.json`), scrie JSON-ul în `tu4/rezultate/S28/` (0444) și
returnează rc 0 = PASS, 1 = FAIL, 3 = UNKNOWN (fereastră).

**P0 — starea înainte (toate):** (1) hash-urile perechii `124151Z` = fișierul de verificare (la rădăcina `predari/`);
(2) B0: log `2a6aca6c…`, Q7L `2431cdb9…` PASS 11/11, V0L `83f079cf…` 28/29 numai `incidente`; (3) sha-ul sigiliului S27 =
`ce2a9f18…`; (4) toate `frozen_hashes` din sigiliul S28 = valorile curente; (5) incidentele = cele 9, fără
`S26_*`/`S28_*`; (6) 27/27 surse Rust 0444 cu sha = manifestul S22; (7) `verifica_s28.py` are modul 0444.

**P1 — înregistrarea formală a avertismentului extern (toate):** (1) `journalctl --user -u loto-actualizare.service
--since 2026-10-25T19:00:00Z` citit cu rc 0; (2) numărate: pornirile (`Starting`), eșecurile (`Failed with result`),
mesajele `gpu-v1`, reușitele (`Finished`), cu prima/ultima apariție `gpu-v1`; consistență `n_gpu ≤ n_esec ≤ n_porniri`
și `n_porniri ≥ 1`; (3) `CURRENT_LIVE.json`: `updated_utc` și `last_date` pe joc (fără numere); (4) `systemctl --user
show loto-actualizare.service -p Result,ExecMainExitTimestamp`; (5) se scriu `tu4/rezultate/S28/AVERTISMENT_EXTERN_S28.json`
și extrasul filtrat `tu4/rezultate/S28/JURNAL_GPU_V1_S28.txt` (numai liniile systemd ale unității și liniile cu
`gpu-v1`), ambele 0444. Starea (`GARDA_ACTIVA` dacă ultima rulare a eșuat cu `gpu-v1`, altfel `GARDA_NEOBSERVATA`) și
consecința (`DECONTARE_PENDING_CONDITIONAT`) sunt descriptive, nu praguri.

**P2 — calendarul (toate):** (1) `emite.py` conține exact liniile constantelor (`DRAW_T, CUTOFF_T, FINAL_T = dt.time(18, 30),
dt.time(16, 0), dt.time(15, 0)`, `WEEKDAYS = (3, 6)`) și `judecator.py` linia `GRACE = dt.timedelta(days=14)`; (2) timerul
instalat = `tu4/systemd/ql649-tu4-emitere.timer` (sha) și conține cele 3 `OnCalendar` Europe/Bucharest; (3) o replică
independentă a `schedule()` dă, la 2026-10-29T14:05Z, ținta 2026-11-01, precedenta 2026-10-29, cutoff 14:00Z, fereastra
finală 13:00Z, extragerea 16:30Z; (4) sloturile 2026-10-29T14:00Z → 2026-11-01T14:00Z sunt exact cele 8 din §2, iar sub
H_BLOCAT primele 7 dau `postponed` și ultimul (13:20Z) emisie; (5) `sonda_s27.window`: 13:20Z și 13:35Z interzise,
13:36Z și 13:57Z libere, 16:15Z/16:45Z (joi) interzise, 16:46Z liber; (6) conversiile America/New_York din §2 (inclusiv
trecerea EDT→EST la 2026-11-01T06:00Z); (7) se scrie `tu4/rezultate/S28/CALENDAR_S28.json` (0444).

**P3 — neintervenție după (toate):** (1) `frozen_hashes` S28 neschimbate; (2) hash-urile externe (garda, unitatea, timerele)
= cele din sigiliu; (3) 27/27 surse 0444 cu sha; (4) incidentele = cele 9; (5) `LANT.jsonl` = instantaneul din sigiliu
(nicio emisie nouă nu e așteptată înainte de joi 14:00Z); (6) `tu4/s28/` conține numai `verifica_s28.py`, 0444;
(7) `loto-actualizare.timer` și `ql649-tu4-emitere.timer` `active`.

**Q7L final:** după P3, primul pas `primul_pas_S26.sh` neschimbat, în afara ferestrelor ⇒ Q7L PASS 11/11, V0L 28/29 numai
`incidente`, 587/587, 61/61, `DL_RC=0`, `DECONTARE_PENDING`, `B5_PENDING` + `B2_RC=0`.

## 4. Verdict

- `S28_PASS` = P0 ∧ P1 ∧ P2 ∧ P3 ∧ Q7L final.
- `S28_FAIL` = oricare FAIL; se înregistrează `tu4/rezultate/S28/INCIDENT_S28_NN.json`, fără reglaje și fără repetare cu
  alte praguri.
- `UNKNOWN` (fereastră, SSD nemontat) nu devine PASS.
- `S28_PASS` NU înseamnă că decontarea sau emisia vor avea loc la timp și NU repară garda: riscul `gpu-v1` rămâne deschis
  până la o sesiune dedicată separată.

Raport: `tu4/rezultate/S28/RAPORT_S28.md`. Fișiere noi permise: `tu4/PROTOCOL_QUANTUM_S28.md`, `tu4/SIGILIU_TU4_S28.json`,
`tu4/rezultate/S28/*`, `tu4/s28/verifica_s28.py`, logul primului pas în `tu4/rezultate/S25/` (scrierile uzuale ale
primului pas), `predari/OPERATIV.md`, Mesajul 79 în `predari/MESAJE_UTILIZATOR_QL649.md` și perechea de predare emisă de
`predari/genereaza_predare.py`. Fără `sudo`, fără `chmod u+w` pe fișiere înghețate, fără scrieri în
tribunal/systemd/surse Rust/produsul principal (`loto_romania/`, `loto`), fără `tu4/incidente/S26_*`/`S28_*`.
Git: numai `./dev-git status`.
