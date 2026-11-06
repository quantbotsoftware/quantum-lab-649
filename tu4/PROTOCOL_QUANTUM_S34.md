# PROTOCOL QUANTUM S34 — faza A a planului V11 QL-Ξ: S33_01 opțiunea A (DL v2) și Q4 v2 (S33_02)

Scris și sigilat ÎNAINTE de codul S34. Autoritate: cererea utilizatorului din 2026-10-30 00:24 EET („trecem la
executarea planului V11 QI XI”, autonomie deplină, fără întrebări). Planul: artefactul `PLAN_V11_QL_XI.md`
(copiat în `xi/PLAN_V11_QL_XI.md`). `positive_claims_allowed=false`. Calcul clasic. Fără subagenți, timere sau
joburi autonome; git numai `./dev-git status`.

## 1. Decizii luate de agent (delegate explicit)

- **S33_01 → opțiunea A**: un verificator NOU `tu4/s34/verifica_publicarea_v2.py`. Verificatorul DL original,
  manifestul DL și fișierele produsului rămân NEATINSE.
- **S33_02 → Q4 v2**: un verificator NOU `tu4/s34/verifica_q4_v2.py`. `tu4/s24/verifica_s24.py` rămâne neatins;
  Q4 S24 rămâne FAIL formal în arhivă.
- **INCIDENT_XI_00** este deja arhivat byte-identic în `xi/incidente/00/` (procedural, fără măsurători).

## 2. DL v2 — semantica exactă

Fișierele vii L (6): `next_candidate/quantum_limit/prospectiv/{649,540,joker}/{registru.json,REZULTATE_PROSPECTIVE.md}`.
Preimaginile P(L): copiile din `next_candidate/predictie_numere/vechime_conditionata_20261023/external_state_at_entry/…`
(același sufix de cale).

DL v2 = PASS dacă și numai dacă toate cele de mai jos sunt adevărate:

1. **D1 preimagini**: pentru fiecare L, sha256(P(L)) == `immutable_checks[L]` din manifestul DL
   (`documentatie/continuitate_20261025T165403Z/manifest.json`) și == `immutable_checks[P(L)]`.
2. **D2 verificatorul original, nemodificat**: `verify(V, V)` din `verifica_publicarea.py` (importat, nu copiat)
   întoarce `status == "PASS"`, unde V este o vedere temporară cu legături simbolice spre rădăcina reală, în care
   NUMAI cele 6 fișiere L sunt înlocuite de P(L). Orice alt fișier rămâne verificat strict.
3. **D3 append-only `registru.json`** (pentru fiecare joc): `schema`, `protocol`, `game` identice; lista veche
   `entries` este prefix (după poziție și `target_draw`) al listei noi; pentru fiecare intrare veche, orice cheie cu
   valoare ne-nulă în vechi are valoare identică în nou (cheile nule/absente pot fi completate la punctare);
   fiecare intrare NOUĂ are fișierul de sigiliu `prospectiv/<joc>/<target_draw>/<seal>` existent, cu sha256 ==
   `seal_sha256`. `summary` este derivat și se poate recalcula.
4. **D4 append-only `REZULTATE_PROSPECTIVE.md`**: liniile vechi, cu excepția titlului (linia 1) și a liniei cu
   numărul de extrageri punctate (linia 3), apar în fișierul nou ca subsecvență în aceeași ordine; numărul k din
   titlul „(k/52” nu scade.

Rezultat: `tu4/rezultate/S34/DL_V2_VERIFICARE_<UTC>.json` (0444), plus informativ rezultatul verificatorului
original pe rădăcina vie (FAIL așteptat, cauza S33_01). DL_RC_v2 = 0 numai la PASS.

## 3. Q4 v2 — semantica exactă

Identic cu Q4 din `tu4/s24/verifica_s24.py` (aceleași 6 verificări, aceleași funcții importate: unitatea din
`SIGILIU_TU4_S24.json`, `health`, `listeners`, `boot_epoch`, `proc_start_epoch`), cu o SINGURĂ diferență:
identificatorul invocației se ia din `INVOCATION_ID`, `_SYSTEMD_INVOCATION_ID` **sau `USER_INVOCATION_ID`**
(serviciu `--user`), iar evenimentul „Finished” se potrivește pe oricare dintre cele trei câmpuri. Jurnalul
invocației se citește cu `_SYSTEMD_INVOCATION_ID=<id>`. UNKNOWN dacă boot-ul este anterior sigiliului S24.
Rezultat: `tu4/rezultate/S34/Q4V2_VERIFICARE_<UTC>.json` (0444).

## 4. Reguli

Fiecare verificator rulează o dată în S34; rezultatul se publică așa cum iese; fără reglaje după rezultat.
Erorile tehnice se declară ca incidente `S34_xx`. Adaptarea C1 (un Q7S v2 care citește DL v2 și Q4 v2 în locul
DL_RC/Q4 înghețate) este pasul următor și cere protocolul ei; verifica_s33.py rămâne înghețat.
