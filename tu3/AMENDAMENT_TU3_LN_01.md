# AMENDAMENT TU3-LN-01 — matricea de inițializare în lansatorul pictogramei (sesiunea S2 din plan)

Scris și sigilat 2026-10-27 (~12:55Z), ÎNAINTE de orice cod al submodulului (`code_files_present: []` în
`tu3/SIGILIU_TU3_LN.json`). Subordonat planului `tu3/PLAN_SESIUNI_TU3_20261027.md` (sha `c7b4bfd3…7ead7f`, neschimbat)
și deciziilor `tu3/DECIZII_PLAN_TU3_20261027.json` (sha `b6a5ba05…53ccad`, neschimbat). Nu e un protocol științific:
nu rulează motoare, nu produce variante, nu atinge datele. `positive_claims_allowed=false`.

## 1. Conflict găsit înainte de cod (inventar read-only) și decizia utilizatorului

- Planul (S2) cerea modificarea `porneste_aplicatia.sh`. Inventarul read-only din această sesiune arată că
  `porneste_aplicatia.sh` (sha `d8df19ce…c193e0`) e ÎNGHEȚAT în două sigilii publicate, care nu se rescriu:
  `tu3/SIGILIU_TU3_VS.json` și `tu3/SIGILIU_TU3_DD.json`. Ele sunt citite de `tu3/matrice_init.py::integrity()`,
  `tu3/validare_tu3.py::integrity_check()`, `tests/test_validare_tu3.py` (testul matricii, T4) și
  `tests/test_dedup_live.py::test_T11_frozen_and_stdlib_only`. Orice modificare a lui ar produce DRIFT: verdictul
  matricii ar deveni permanent „ATENȚIE”, iar suitele existente ar avea teste roșii. E o scăpare a planului meu (S1),
  nu un defect al produsului sau al datelor. Nu s-a scris cod înainte de această constatare.
- Utilizatorul a ales (Mesajul 41, 2026-10-27T12:49Z), dintre trei variante, varianta 1: **`porneste_aplicatia.sh`
  rămâne NEMODIFICAT**. Se scrie un lansator NOU, `porneste_aplicatia_tu3.sh`, plus un test nou. Linia `Exec=` din cele
  3 fișiere `.desktop` identice trece pe lansatorul nou.

## 2. Domeniu (închis)

Fișiere NOI (numai acestea):
1. `porneste_aplicatia_tu3.sh` (rădăcina aplicației, executabil).
2. `tests/test_lansator_tu3.py` (testul nou).
3. `tu3/rezultate/LN/ACCEPTARE_LN_<UTC>Z.json` (raportul de acceptare, 0444) + acest amendament și sigiliul lui.

Fișiere MODIFICATE (numai acestea, numai liniile `Exec=`, două pe fișier; restul octeților identici):
- `assets/quantum-lab-649.desktop`, `~/.local/share/applications/quantum-lab-649.desktop`,
  `~/Desktop/quantum-lab-649.desktop` (azi identice, sha înainte în sigiliu):
  `Exec=…/porneste_aplicatia.sh` → `Exec=…/porneste_aplicatia_tu3.sh`, iar acțiunea Stop
  `Exec=…/porneste_aplicatia.sh --stop` → `Exec=…/porneste_aplicatia_tu3.sh --stop`. Permisiunile rămân; dacă
  atributul `metadata::trusted` al copiei de pe Desktop (azi `true`) se pierde la editare, se restabilește la `true`
  (starea dinainte, declarat în raport).

Fișiere PROTEJATE, byte-identice (hash-urile în sigiliu, verificate la final): `porneste_aplicatia.sh`, `run_app.sh`,
`run_app_tu3.sh`, `app.py`, `engine.py`, `parser.py`, `validare.py`, `verify_ql649.py`, `tu3/parser_multi.py`,
`tu3/motor_n.py`, `tu3/motor_joker.py`, `tu3/joker_entanglement.py`, `tu3/ui_tu3.py`, `tu3/arhiva_live.py`,
`tu3/dedup_live.py`, `tu3/matrice_init.py`, `tu3/validare_tu3.py`, toate testele existente, toate protocoalele,
amendamentele și sigiliile anterioare, planul, deciziile, drop-in-urile `tu3-*.conf`, `predari/genereaza_predare.py`.
Gardul prognozei automate: neatins (decizia utilizatorului).

## 3. Specificația lansatorului nou `porneste_aplicatia_tu3.sh`

- L1. Pașii 1–3 ai `porneste_aplicatia.sh`, cu același comportament: oprește instanța veche din ACEST director, șterge
  `__pycache__` (fără `.venv`), `PYTHONDONTWRITEBYTECODE=1`, verifică sintaxa tuturor `.py` + amprenta versiunii. Portul
  ocupat de alt proces ⇒ eroare + notificare, ca acum.
- L2. Pornire detașată: `setsid ./run_app_tu3.sh` (în locul `./run_app.sh`); pgid în `jurnal/app.pgid` (același fișier
  ca lansatorul vechi ⇒ fiecare îl poate opri pe celălalt). `run_app_tu3.sh` scrie matricea în
  `jurnal/matrice_<UTC>Z.txt`, apoi face `exec ./run_app.sh` (ambele neschimbate).
- L3. Jurnalul lansatorului: `jurnal/lansator_tu3_<UTC>Z.log`.
- L4. După `health ok`, lansatorul identifică fișierul de matrice al ACESTEI porniri (`jurnal/matrice_*Z.txt` mai nou
  decât jurnalul lansatorului) și copiază în jurnalul lui liniile „Integritate …” și „Verdict matrice …” (prefix
  `[lansator] matrice:`). Notificarea finală are titlul „Quantum Lab 649 pornit — TOATE 3 MODURILE READY” dacă linia de
  verdict conține exact acest text, altfel „Quantum Lab 649 pornit — ATENȚIE: matricea nu e complet READY” (sau
  „… — matrice absentă”, dacă fișierul lipsește), cu fișierul de matrice și versiunea în corp. Verdictul NU blochează:
  serverul pornește, browserul se deschide, codul de ieșire e 0 la `health ok`, oricare ar fi verdictul.
- L5. `our_pids` recunoaște, în plus față de cel vechi, `bash ./run_app_tu3.sh` cu `cwd` = directorul aplicației
  (faza dinaintea lui `exec`). `stop_server`: (i) grupul din `jurnal/app.pgid`, ca acum; (ii) NOU: pentru fiecare
  proces recunoscut, întregul lui grup de procese (dacă pgid ≠ grupul lansatorului și > 1), ca să nu rămână orfani
  (`python … tu3/matrice_init.py`, `tee`) nici când `app.pgid` lipsește; (iii) TERM, apoi KILL, ca acum.
- L6. `--stop`: aceeași semantică (oprește tot, notificare „oprit”).
- L7. Fără comutatoare ascunse prin variabile de mediu, în afară de cele existente (`QL649_PORT`, `QL649_ADDRESS`
  transmis mai departe neschimbat).

## 4. Testul nou `tests/test_lansator_tu3.py` (automat, fără a atinge serverul utilizatorului)

Rulează pe o COPIE IZOLATĂ: un director temporar cu legături simbolice spre intrările aplicației (fără `jurnal/`, care e
nou și gol) și cu lansatorul COPIAT ca fișier real (altfel `readlink -f` ar duce în directorul real). Port liber ales
dinamic, nu 8649. `notify-send` și `xdg-open` sunt înlocuite, numai în `PATH`-ul testului, de stub-uri care își scriu
argumentele într-un fișier (fără ferestre, fără browser). Teste:
- T1 static: `bash -n`; lansatorul conține `setsid ./run_app_tu3.sh` și recunoaște `run_app_tu3.sh`; hash-urile
  protejate din sigiliu = cele curente; cele 3 `.desktop` au exact două linii `Exec=` spre lansatorul nou și restul
  octeților = cei de dinainte (comparat cu sha-ul din sigiliu după substituția inversă).
- T2 pornire + oprire: cod 0, `health ok`, fișier de matrice nou, liniile de verdict copiate în jurnalul lansatorului,
  notificarea conține verdictul matricii, `xdg-open` chemat cu URL-ul portului; `--stop` ⇒ 0 procese cu `cwd` = copia,
  portul liber.
- T3 oprire în faza de matrice (înainte de `exec`, când rulează `bash ./run_app_tu3.sh`), o dată cu `app.pgid` și o dată
  fără `app.pgid` (ramura nouă L5-ii): 0 procese rămase cu `cwd` = copia, portul liber.
- T4 serverul utilizatorului: dacă înainte exista un ascultător pe 8649, după test există același pid.

Abatere declarată: `run_app_tu3.sh` (neschimbat) apelează `tu3/matrice_init.py` fără `--out-dir`; implicitul este
`<director real>/jurnal`, deci și copia izolată scrie `MATRICE_INIT_<UTC>Z.json` în `jurnal/` real (numai jurnal,
fără efect asupra produsului).

## 5. Criterii de acceptare (fixate acum; raport în `tu3/rezultate/LN/ACCEPTARE_LN_<UTC>Z.json`, 0444)

- C1. `bash -n porneste_aplicatia_tu3.sh` OK; `tests/test_lansator_tu3.py` integral verde (0 failed, 0 skipped);
  suitele existente `tests/test_validare_tu3.py tests/test_app.py tests/test_app_tu3.py tests/test_dedup_live.py`
  exact **33 passed, 3 skipped**.
- C2. Acceptarea reală, o singură dată, pe 8649, cu acordul utilizatorului (Mesajul 40): serverul utilizatorului se
  oprește prin lansatorul nou; pornirea din PICTOGRAMĂ e emulată cu `gtk-launch quantum-lab-649` (aceeași intrare
  `.desktop`); se cer: `jurnal/matrice_<UTC>Z.txt` nou, cu „TOATE 3 MODURILE READY” și integritate OK; liniile copiate în
  `jurnal/lansator_tu3_<UTC>Z.log`; `health ok`; ascultă numai `127.0.0.1:8649`. Apoi `porneste_aplicatia_tu3.sh --stop`
  ⇒ 0 procese din director, port liber. La final serverul se repornește tot din pictogramă (`gtk-launch`) și rămâne
  pornit pentru utilizator.
- C3. La final: hash-urile protejate identice cu sigiliul; matricea (`tu3/matrice_init.py --out-dir /tmp/…`) „TOATE 3
  MODURILE READY”, integritate OK; `tu3/dedup_live.py --verifica` OK.
- Verdict: `LN_PASS` numai dacă C1–C3 trec integral; altfel `LN_FAIL`, publicat ca atare. O singură remediere permisă,
  numai printr-un amendament nou sigilat înainte de modificare (ca la TU3-VS-01), fără schimbarea criteriilor.

## 6. Ce NU face acest amendament

Nu schimbă produsul, motoarele, datele, protocoalele, pragurile sau verdictele anterioare; nu atinge gardul prognozei
și nici linger-ul (deciziile utilizatorului). `porneste_aplicatia.sh` rămâne funcțional (pornește fără matrice).
Calcul clasic. Variantele produsului = minime de energie, NU predicții. `positive_claims_allowed=false`.
