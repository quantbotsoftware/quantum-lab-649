# PROTOCOL TU4-S33 — revenirea la kernelul 7.0.11, criteriul de paritate completă Q7S și starea incidentului S31_01

Cererea = Mesajul 85 (2026-10-29T21:13:27+02:00 = 19:13:27Z). `positive_claims_allowed=false`. Calcul clasic. Fără
afirmații predictive. Numai verificări de metadate și de integritate; LANT rămâne prefixul `LANT_PREFIX_S20` (3 linii).

Acest protocol este scris DUPĂ primul pas exact din predarea `185444Z` (sha-uri + sonda S27, read-only, §1) și ÎNAINTE de
orice altă scriere în workspace pentru S33. Sigiliul `tu4/SIGILIU_TU4_S33.json` (scris de `tu4/rezultate/S33/sigileaza_s33.py`)
fixează sha-ul acestui document și hash-urile înghețate. Codul S33 (`tu4/s33/verifica_s33.py`) se scrie DUPĂ sigiliu.

## 0. Corecții de premisă (ce NU adoptă S33 din formularea cererii)

1. **„Curățarea stării FAIL din `INCIDENT_S31_01.json`”**: nu se face. Rezultatele publicate, inclusiv cele negative, nu se
   rescriu (AGENTS.md). `INCIDENT_S31_01.json` (`6e98ed5b…`), `Q7L_VERIFICARE_20261029T184906Z.json` (`1cb9a923…`) și
   `V0L_VERIFICARE_20261029T184906Z.json` (`4af346d9…`) rămân byte-identice; S31 rămâne `S31_FAIL` formal. S33 poate cel mult
   adăuga un fișier NOU `REZOLUTIE_S31_01_<UTC>.json` care declară incidentul **rezolvat prospectiv** (cauza de mediu înlăturată,
   criteriul de paritate înlocuit pentru rulările viitoare). Asta nu este o anulare și nu micșorează numărul de incidente.
2. **„Paritatea tinde spre 587/587 sub kernelul restabilit”**: kernelul NU intră în numărul de verificări de paritate.
   `INCIDENT_S31_01` a stabilit că `n_checks` din `parity.rs` depinde de date (referința S19 se regenerează din arhiva LIVE
   curentă). Kernelul a blocat numai garda produsului (`cohorta.py:163`), deci intrarea datelor în LIVE. Arhiva LIVE are acum
   versiunea `976072ca8299` (649/540/Joker până la 2026-10-29), diferită de ambele versiuni din S31. Numărul de verificări se
   **măsoară**; 587 nu este o țintă și nu se ajustează nimic pentru a-l obține. Pragul 587 din Q7L/V0L nu se schimbă.
3. **„Lasă judecătorul automat să proceseze decontarea”**: s-a întâmplat deja, fără intervenția agentului: la 19:11:52Z
   `loto-actualizare` a publicat LIVE `976072ca8299` (`Result=success`), iar judecătorul înghețat a decontat la 19:11:53Z
   (`action=decided rc=0 pending=[]`; sonda T2 `DECONTARE_COMPLETA 3/3`: 649, 540, Joker `DECONTAT`). S33 doar verifică
   read-only. Agentul nu pornește timere, joburi sau procese de fundal; timerele existente ale utilizatorului rămân așa cum sunt.
4. **„08:36–08:57 EST”**: fereastra obligatorie rămâne cea UTC, `2026-11-01T13:36:00Z–13:57:59Z` (FISA_DUMINICA_S29, strict).
   Observat acum: fusul sistemului este `Europe/Bucharest` (`/etc/localtime` modificat 2026-10-29 ~14:42Z), deci ceasul local
   al laptopului va afișa 15:36–15:57 EET, nu 08:36–08:57 EST. Etichetele EST din fișă rămân corecte pentru America/New_York,
   dar nu mai descriu ceasul laptopului. Fișa nu se rescrie.
5. Fără modificări în surse Rust (27/27 rămân 0444), `loto_romania/`, tribunal, verificatoarele vechi sau fișe. Git: numai
   `./dev-git status`.

## 1. Observații înainte de protocol (read-only)

| UTC | Observație |
|---|---|
| 19:08:31Z | boot curent; `uname -r` = `7.0.11-76070011-generic`; `/proc/cmdline` cu `initrd.img-previous` |
| 19:08:36–41Z | `ql649-tu3-8649.service`: `SSD_MONTAT /dev/sda1 … după 0s`, `Finished`; Streamlit ascultă `127.0.0.1:8649` |
| 19:11:52Z | `loto-actualizare` success; LIVE `versiuni/976072ca8299` (649: 2598, 540: 2491, Joker: 2203 până la 2026-10-29) |
| 19:11:53Z | judecătorul: `decided`, `rc=0`, `pending=[]` |
| 19:13:52Z | primul pas exact `185444Z`: 6 sha-uri = predarea (inclusiv `cohorta.py` `8a70951b…`); sonda `SONDA_RC=0`, `FAZA_2_DECONTARE_COMPLETA`, G1 9 incidente, G2 27/27 0444+sha, G3 binar `c20fdcd2…`, T5 tribunal neatins |
| 19:16Z | jurnalul `loto-actualizare` din boot-ul curent: 0 mesaje `Model/environment changed` |

Predarea: sha HANDOFF `2a2da6cb…`, PROMPT `2cd16c42…` (= `VERIFICARE_PREDARE_20261029T185444Z.json`); perechea precedentă
arhivată `80c5025b…` / `21a62bd1…` / `6f121d29…` = valorile din același fișier.

## 2. Ce se rulează în S33 (o singură dată fiecare, în ordine)

Precondiții: în afara minutelor [:58, :04) și [:28, :34) și la ±15 min față de emisii (08:20/12:20/15:20 Europe/Bucharest).

1. `bash tu4/rezultate/S25/primul_pas_S26.sh > tu4/rezultate/S25/primul_pas_S26_<UTC>.log 2>&1`, NESCHIMBAT (scrierile lui
   uzuale: Q0/Q1/Q4, DECONTARE_20261029, A0, referința S19).
2. `verifica_s25.py q7l <log>` NESCHIMBAT, o dată (ca în FISA_DUMINICA_S29). Declarat ÎNAINTE de rulare: dacă `n_pass ≠ 587`,
   Q7L/V0L dau FAIL formal pe `paritate_587` (V0L: `paritate`, plus `incidente`, moștenit). Acesta este FAIL-ul anticipat de
   S32 §4, **nu un incident nou**. Orice alt FAIL Q7L/V0L este incident `S33_NN`.
3. `tu4/s33/verifica_s33.py q7s <log>` (criteriul Q7S, §3), o dată.
4. Dacă Q7S = PASS: `verifica_s33.py rezolutie <Q7S_VERIFICARE.json>` scrie `REZOLUTIE_S31_01_<UTC>.json` (§4). Dacă Q7S = FAIL:
   nicio rezoluție; incidentul S33 se declară cu cauza constatată.

`verifica_s26.py`…`verifica_s31.py` nu se rulează. `cohorta.py` rămâne neatins.

## 3. Criteriul Q7S (fixat acum; PASS ⇔ toate verificările trec)

Q7S este Q7L cu o singură substituție: `paritate_587` (număr fix) devine `paritate_completa` (criteriul propus în S32 §4),
plus verificări de mediu, de reproducere și de integritate. Pragul 587 nu se coboară retroactiv pentru rulările din S31.

**K — mediu**
- K1 `uname -r` = `7.0.11-76070011-generic`.
- K2 identitatea curentă `gpu-v1` = identitatea înghețată în cohorta activă (`tu4/rezultate/S32/diag_gpu_v1.py`, read-only,
  ultima linie `equal`).
- K3 `loto-actualizare.service`: `Result=success` și 0 mesaje `Model/environment changed` în jurnalul boot-ului curent.

**L — logul primului pas** (aceleași expresii ca Q7L unde există)
- L1 V0L (`verifica_s25.v0l_checks`, fără fișier): 29 de verificări; singurele permise să cadă sunt `incidente` și `paritate`;
  incidentele găsite ⊆ `incidents_before` din SIGILIU_TU4_S25.
- L2 `tu4/incidente/` = exact cele 9 incidente din SIGILIU_TU4_S25.
- L3 `paritate_completa_log`: `"verdict_B2_B7": "PASS"`, `n_pass == n_checks` (citite din log), `PARITY_RC=0`.
- L4 `test result: ok. 61 passed`; L5 Q0 PASS; L6 Q1 PASS; L7 `S24_SERVICIU Result=success`.
- L8 `"verdict": "DECONTARE_COMPLETA"` (raportul read-only 2026-10-29; mai strict decât Q7L, care acceptă și PENDING/PARTIALA;
  ales după ce sonda a arătat 3/3 și declarat aici ca atare).
- L9 `B5_RC=0` sau `B2_RC=0`; L10 nicio linie `FAIL Q…`/`FAIL A…`; L11 `DL_RC=0`; L12 A0 PASS și `SCUT_LANT OK linii N []`.
- L13 Q4 (S24) cu verdict `PASS` în log (nu `UNKNOWN`, nu `FAIL`).

**P — reproducerea parității**
- P1 binarul `rust_core/target/release/rust-singularity-core` are sha `c20fdcd2…`.
- P2 cele 27 de surse din MANIFEST_RUST_CORE_20261028T032900Z au modul 0444 și sha-ul din manifest.
- P3 referința folosită de log (cea mai nouă `REFERINTA_PARITATE_*.json`, creată după începutul logului) are `version_dir`
  egal cu versiunea LIVE curentă (arhiva nu s-a schimbat între referință și verificare).
- P4 o rulare nouă `parity --ref <P3>` (ieșirea completă salvată în `tu4/rezultate/S33/PARITATE_COMPLETA_<UTC>.json`):
  `verdict_B2_B7 == PASS`, `n_pass == n_checks`, `n_checks` egal cu cel din log, toate grupele PASS, suma grupelor = `n_checks`.
- P5 (informativ, fără prag): `n_checks` față de 587 și față de 552, cu defalcarea pe grupe.

**I — integritate**
- I1 SIGILIU_TU4_S33 și acest protocol: sha din sigiliu, mod 0444.
- I2 `INCIDENT_S31_01.json`, Q7L/V0L `184906Z` și `NOTA_COMPLETARE_S31.md` byte-identice cu sigiliul.
- I3 neschimbate: `verifica_s25.py`, `primul_pas_S26.sh`, SIGILIU_TU4_S25, FISA_DUMINICA_S29, `cohorta.py`, PROTOCOL_QUANTUM_S32.

Ieșire: `tu4/rezultate/S33/Q7S_VERIFICARE_<UTC>.json` (toate verificările cu detalii), `Q7S_RC` = 0 numai la PASS.

## 4. Rezoluția S31_01 (numai după Q7S PASS)

`REZOLUTIE_S31_01_<UTC>.json` conține: `stare = REZOLVAT_PROSPECTIV`; `incident_neschimbat = true` (sha `6e98ed5b…`);
`S31_verdict = S31_FAIL` (neschimbat); cauza de mediu (kernelul 7.2.6) înlăturată prin opțiunea A din S32 §3 (aleasă de
utilizator); criteriul `paritate_587` înlocuit prospectiv de Q7S `paritate_completa`; trimiteri la Q7S, la paritatea completă
și la Q7L/V0L S33. Numărul de incidente al proiectului nu scade (NU zero incidente).

## 5. Duminică 2026-11-01 (C1/B5), aliniere fără rescrierea fișei

Fereastra strictă rămâne `13:36:00Z–13:57:59Z` (pe ceasul actual al laptopului: 15:36–15:57 EET). Pașii FISA_DUMINICA_S29 se
execută neschimbați (sonda; primul pas + `verifica_s25.py q7l`). Q7L va da FAIL formal anticipat pe `paritate_587` dacă
`n_pass ≠ 587` (nu este incident). Pasul nou, în aceeași fereastră și pe același log:
`/usr/bin/python3 -B tu4/s33/verifica_s33.py q7s "$L"`. Pentru duminică, **C1 = Q7S PASS**; B5 rămâne cel din log
(`B5_RC=0` după emisia 13:20Z). Dacă emisia dă `late` sau fereastra e ratată, C1/B5 rămân PENDING/UNKNOWN. Altă fereastră
numai cu protocol nou. Monitorizarea este pasivă: agentul nu creează timere.

## 6. Verdict S33

`S33_PASS` ⇔ Q7S PASS și niciun FAIL Q7L/V0L în afara celui anticipat la §2.2. Altfel `S33_FAIL` cu incident `S33_NN`.
Calcul clasic. Fără sudo, fără `chmod u+w` pe fișiere înghețate. `positive_claims_allowed=false`.
