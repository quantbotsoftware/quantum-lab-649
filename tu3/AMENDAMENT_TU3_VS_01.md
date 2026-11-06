# AMENDAMENT TU3-VS-01 — incident tehnic: conflict între TU3-VS §3 și martorul U8 al TU3-UI

Scris și sigilat 2026-10-26 (~18:21Z), DUPĂ prima rulare a suitei și ÎNAINTE de orice modificare de cod care o urmează.
Subordonat `PROTOCOL_TU3_VS.md` (sha `7f448d21…e7a1`, neschimbat).

## 1. Ce s-a întâmplat (publicat, nerescris)

- Rularea unică `tu3/validare_tu3.py --suita` din 18:16–18:19Z a dat **`VS_SUITE_FAIL`**:
  `tu3/rezultate/VS/VALIDARE_TU3_20261026T181924Z.json` (sha `4bb85cf0…`, 0444, PĂSTRAT). V1 32/32, V2 53/53, V4 J/E40/EJ
  PASS, V5 649/540/Joker PASS, V6 PASS; **V3: 1 failed, 10 passed, 3 skipped** (așteptat 11 passed, 3 skipped).
- Cauza (diagnostic, fără schimbarea vreunui prag): testul înghețat `tests/test_app_tu3.py::
  test_u8_unchanged_files_and_additive_app` (martorul U8 al TU3-UI) cere ca `run_app.sh` să aibă hash-ul din
  `SIGILIU_TU3_UI.json` (`a8f38cea…`). TU3-VS §3 a autorizat o modificare aditivă a `run_app.sh` (noul sha
  `1236442e…`), dar §0 a înghețat totodată `tests/test_app_tu3.py` și §1 V3 a cerut 11 passed — cerințe incompatibile
  în propriul meu protocol. Eroare de proiectare a protocolului, nu defect al produsului sau al datelor.
- Copia `run_app.sh` modificată se păstrează byte-identic în `tu3/incidente/VS_01/run_app.sh` (cu hash în
  `INCIDENT_TEHNIC_VS_01.json`).

## 2. Remediere (fără tuning)

- `run_app.sh` revine BYTE-IDENTIC la copia de referință `tests/baseline/run_app_v2.sh` (sha `a8f38cea…`), deci
  martorul U8 al TU3-UI și `porneste_aplicatia.sh` (înghețat) rămân neatinse.
- Inserțiile (a) și (b) din TU3-VS §3 se mută, cu același conținut, într-un lansator NOU `run_app_tu3.sh` (rădăcina
  aplicației): `py_compile` pe modulele TU3, matricea de inițializare cu ieșirea în `jurnal/matrice_<UTC>Z.txt`
  (cod ≠ 0 ⇒ `[QL649] ATENȚIE …`, pornire în continuare), apoi `exec ./run_app.sh` (serverul neschimbat:
  127.0.0.1:8649). Lansarea din pictogramă (`porneste_aplicatia.sh` → `run_app.sh`) NU tipărește matricea (abatere
  declarată; matricea se poate tipări oricând cu `tu3/matrice_init.py`).
- Modificări de cod consecutive (numai integrare, aceleași praguri): V6 cere `run_app.sh` = sha `a8f38cea…` (în locul
  „copia + numai inserții”), `bash -n` pe `run_app.sh` și `run_app_tu3.sh`, iar `run_app_tu3.sh` conține inserțiile
  (a)/(b) și `exec ./run_app.sh`; §4 caută ultimul `jurnal/matrice_*Z.txt`; T3 se adaptează identic.
- Pragurile V1–V6 și §4 rămân EXACT cele sigilate (V3: 11 passed, 3 skipped). Suita se rulează O DATĂ, încă o dată,
  după remediere, cu raport nou (`VALIDARE_TU3_<UTC>Z.json`); ambele rapoarte rămân publicate. Verdictul modulului se
  ia din a doua rulare numai dacă trece integral; dacă nu, modulul rămâne `VS_FAIL`, fără alte reîncercări.

## 3. Bilanț incidente TU3-VS

`technical_incidents = 1` (acesta). Fără impact asupra datelor, protocoalelor anterioare, motoarelor sau puterii.
`positive_claims_allowed=false`.
