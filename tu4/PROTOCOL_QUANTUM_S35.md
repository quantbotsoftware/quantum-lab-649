# PROTOCOL QUANTUM S35 — Q7S v2 pentru C1 de duminică 2026-11-01 (DL v2 și Q4 v2 în locul criteriilor înghețate)

Scris și sigilat ÎNAINTE de codul S35 (`tu4/s35/` nu există la sigilare). Autoritate: Mesajul 107 (autonomie 100%,
fără întrebări) și cererea din 2026-10-30 00:48 EET („Prioritatea 1 … protocolul S35 + Q7S v2 pentru C1”).
Plan: `xi/PLAN_V11_QL_XI.md` (`2fb304f4…`). `positive_claims_allowed=false`. Calcul clasic. Fără subagenți, timere
sau joburi autonome; git numai `./dev-git status`.

## 1. Problema

C1 (S33 §5) = `verifica_s33.py q7s` PASS pe logul primului pas din fereastra strictă 2026-11-01 13:36:00Z–13:57:59Z.
Verificatorul S33 este înghețat și pică, previzibil, pe patru verificări, din două cauze deja declarate:

- **S33_01** (DL original pe rădăcina vie: `DL_RC=1`, permanent) ⇒ L1 (V0L `dl`) și L11;
- **S33_02** (Q4 S24: câmpul `USER_INVOCATION_ID` necitit) ⇒ L1 (V0L `fara_fail`), L10 și L13.

Înlocuitorii legitimi există și au trecut în S34: DL v2 (`tu4/s34/verifica_publicarea_v2.py`, `7893db93…`) și Q4 v2
(`tu4/s34/verifica_q4_v2.py`, `c958bad7…`).

## 2. Decizia (a agentului, delegată)

Un verificator NOU `tu4/s35/verifica_q7s_v2.py`. Nu modifică nimic înghețat: `verifica_s33.py`, `verifica_s25.py`,
`verifica_s24.py`, `primul_pas_S26.sh`, FISA_DUMINICA_S29, DL original, manifestul DL, DL v2 și Q4 v2 rămân neatinse.

**Metoda: reutilizare, nu copiere.** Q7S v2 importă `verifica_s33` și execută funcția înghețată `q7s(log)`
NEMODIFICATĂ, cu două substituții de mediu (precedent: `verifica_s25.v0l_checks` față de `verifica_s23.v0`):
(a) clasa `Report` este înlocuită de o captură care întoarce verificările fără să scrie fișiere; (b) `OUT` indică spre
`tu4/rezultate/S35/` (doar fișierul de paritate completă P4 ajunge acolo). Ieșirea standard a funcției înghețate este
capturată și păstrată informativ. Verdictul înghețat se publică informativ (`Q7S_inghetat_informativ`).

## 3. Criteriile Q7S v2 (exacte)

Din cele 23 de verificări înghețate, **19 se păstrează identic** (K1–K3, L2–L9, L12, P1–P4, I1–I3). Exact patru se
înlocuiesc (L1, L10, L11, L13). Expresii folosite:

- `Q4_CUNOSCUT` = regex `^FAIL Q4 (prima_invocatie_ssd_montat|prima_invocatie_finished)( |$)` (semnătura S33_02);
- `LIVE6` = cele 6 fișiere `next_candidate/quantum_limit/prospectiv/{649,540,joker}/{registru.json,REZULTATE_PROSPECTIVE.md}`;
- `SEMN_DL` = în log apare exact o linie `DL_RC=<k>`; fie `k = 0`, fie `k = 1` și linia imediat anterioară este
  `AssertionError: Immutable: <f>` cu `f ∈ LIVE6` (semnătura S33_01).

| Cod | Verificare | PASS dacă |
|---|---|---|
| L1v2 | V0L numai incidente/paritate/dl/Q4 | `v0l_checks(log)` are 29 de verificări; numele celor picate ⊆ {incidente, paritate, dl, fara_fail}; incidentele găsite ⊆ `SIGILIU_TU4_S25.incidents_before`; dacă pică `dl`, atunci `SEMN_DL`; dacă pică `fara_fail`, toate liniile `FAIL ` din log respectă `Q4_CUNOSCUT` |
| L10v2 | fără FAIL Q/A în afara S33_02 | nicio linie care începe cu `FAIL Q`/`FAIL A`, exceptând cele care respectă `Q4_CUNOSCUT` |
| L11v2a | semnătura DL din log | `SEMN_DL` |
| L11v2b | DL v2 PASS în aceeași rulare | sha DL v2 == `7893db93…` înainte de rulare; rc 0; JSON nou cu `criteriu DL_V2`, `verdict PASS`, `n_pass == n_checks == 19`, `script_sha256 == 7893db93…`, `run_utc ≥` începutul rulării Q7S v2 |
| L13v2a | semnătura Q4 din log | Q4 din log există; verdict PASS, sau FAIL cu cel puțin o linie `FAIL Q4` și toate liniile `FAIL Q4` respectă `Q4_CUNOSCUT` |
| L13v2b | Q4 v2 PASS în aceeași rulare | sha Q4 v2 == `c958bad7…`; rc 0; JSON nou cu `criteriu Q4V2`, `verdict PASS` (UNKNOWN NU este PASS), `n_pass == n_checks == 6`, `script_sha256 == c958bad7…`, `run_utc ≥` începutul rulării |
| I4 | sigiliul și protocolul S35 | sha sigiliu == valoarea fixată în cod după sigilare; ambele 0444; sha protocol == cel din sigiliu |
| I5 | înghețatele S35 neschimbate | toate `frozen_hashes` din `SIGILIU_TU4_S35.json` sunt identice |
| W1 | (numai `--mod c1`) start în fereastră | ora UTC de început ∈ [2026-11-01T13:36:00Z, 13:57:59Z] și `log_utc` (din numele logului) în aceeași fereastră |
| W2 | (numai `--mod c1`) sfârșit în fereastră | ora UTC de sfârșit ≤ 2026-11-01T13:57:59Z |

**Verdict**: `PASS` ⇔ toate verificările numărate trec (mod c1: 19 + 6 + I4 + I5 + W1 + W2 = 29; mod repetiție: 27).
Mod c1 în afara ferestrei la start: refuz (exit 3), fără fișier, C1 rămâne `PENDING`.
`C1`: `PASS` ⇔ mod c1 și verdict PASS; `UNKNOWN` dacă pică numai W1/W2; altfel `FAIL` (incident `S35_NN`).
B5 rămâne cel din log (`B5_RC=0` după emisia 13:20Z); dacă emisia dă `late`, C1/B5 rămân PENDING/UNKNOWN.

Ieșire: `tu4/rezultate/S35/Q7S2_VERIFICARE_<UTC>.json` (mod c1) sau `Q7S2_REPETITIE_<UTC>.json`, 0444, cu toate
verificările, detaliile, căile și sha-urile rezultatelor DL v2/Q4 v2 (acestea se scriu, ca prin design, în
`tu4/rezultate/S34/`), verdictul înghețat informativ și `positive_claims_allowed=false`. `Q7S2_RC=0` numai la PASS.

## 4. Lansatorul de duminică `tu4/s35/c1_duminica.sh`

Execută, în ordine, pașii FISA_DUMINICA_S29 NESCHIMBAȚI (sonda; primul pas S26 în log; `verifica_s25.py q7l`), apoi
pasul nou `verifica_q7s_v2.py --mod c1 "$L"`. Garda de start: refuză în afara [13:36:00Z, 13:46:00Z] (marjă pentru
durata măsurată la repetiție). Nu creează timere; trebuie pornit manual (utilizatorul sau agentul într-o sesiune
deschisă). Comanda exactă se trece în predare. `verifica_s33.py q7s` nu se mai rulează separat (funcția lui rulează
captată în Q7S v2).

## 5. Repetiția generală (o singură dată, înainte de duminică)

Exact o rulare `c1_duminica.sh --repetitie` (fără gardă de fereastră, etichetă REPETITIE, NU C1), în afara minutelor
[:28,:34), [:58,:04) și a ferestrelor ±15 min ale emisiilor 06:20/10:20/13:20Z. Scopul: dovada că lanțul funcționează
pe un log proaspăt și măsurarea duratei. Rezultatul se publică așa cum iese în `tu4/rezultate/S35/RAPORT_S35.md`.
Q7L/V0L ale repetiției dau FAIL formal anticipat (nu incident). Dacă repetiția pică dintr-un defect de cod S35, se
declară incidentul `S35_NN`, iar orice corectură cere amendament sigilat înainte de duminică; pragurile §3 nu se
schimbă. Dacă pică din cauza mediului, se raportează, fără reglaje.

## 6. Ce NU face S35

Nu rescrie incidente, rezultate, fișe sau verificatoare vechi. Nu execută rezoluția S31_01 (rămâne pentru un protocol
ulterior). Nu atinge `quantum_limit/`, tribunalul, timerele utilizatorului sau garda `loto_romania/cohorta.py:163`.
Fără sudo, fără `chmod u+w` pe fișiere înghețate.
