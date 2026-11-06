# AMENDAMENT S35_02 — restaurarea a doi octeți-cache `.pyc` suprascriși de sesiunea precedentă (înainte de C1)

Scris și sigilat după constatarea INCIDENT_S35_02 (primul pas al sesiunii, 2026-10-30T12:49:48Z) și ÎNAINTE de orice
calcul de reconstrucție, restaurare sau cod nou. Criteriile Q7S v2, fereastra, garda, lansatorul `c1_duminica.sh` și
toți verificatorii rămân NESCHIMBAȚI. `positive_claims_allowed=false`. Calcul clasic.

## 1. Constatarea

- Primul pas exact: toate cele 11 hash-uri corespund, sonda `FAZA_4_EMISIE_COMPLETA RC=0`, dar **`DL_RC_V2=1`**
  (18/19; `tu4/rezultate/S34/DL_V2_VERIFICARE_20261030T124948Z.json`). Verificarea care pică: `D2_original_nemodificat_pe_vedere`,
  `AssertionError('Immutable: next_candidate/quantum_limit/__pycache__/ceiling.cpython-312.pyc')`.
- Scanare read-only a manifestului DL (`documentatie/continuitate_20261025T165403Z/manifest.json`): `installed_files`
  72/72 egale; `immutable_checks` 8 diferite din 5 003 = cele 6 registre vii LIVE6 (așteptate) + **2 fișiere cache**:
  `next_candidate/quantum_limit/__pycache__/ceiling.cpython-312.pyc` (manifest `aadb0d82…`, viu `4dc02b64…`) și
  `next_candidate/quantum_limit/__pycache__/combinatorics.cpython-312.pyc` (manifest `090f6d5e…`, viu `574aff94…`).
- Ambele au mtime 2026-10-29T23:18:55Z, adică imediat după repetiția 2 PASS (23:11:37Z), în timpul rulării
  `xi/c1/permutare.py` din sesiunea precedentă (același agent; `permutare_J140.out` 23:18:39Z). `permutare.py` importă
  `quantum_limit.ceiling` și `quantum_limit.combinatorics` și a fost rulat **fără `-B`**: Python a găsit `.pyc`-urile
  vechi nevalide (antet mtime/mărime diferit de sursa actuală, deci cache vechi, ignorat oricum la import) și le-a
  rescris. Sursele `.py` sunt neschimbate (în manifest). Predarea precedentă nu a rulat DL v2 după căutări.
- Efect: duminică, C1 ar pica de două ori: DL_V2 (D2) și semnul DL original pe rădăcina vie (prima aserțiune ar
  indica un fișier din afara LIVE6). Fără remediere, C1 = FAIL din cauza agentului, nu a sistemului.

## 2. Remedierea (singura permisă)

Octeții originali nu există nicăieri (căutare pe `$HOME` și `./external_media`; `*.pyc` sunt în `.gitignore`).
Un `.pyc` este însă determinist: antet (magic 3.12, flags 0, mtime sursă, mărime sursă) + `marshal` al codului compilat
din sursă cu numele de fișier absolut. Candidate de sursă veche: copia
`$HOME/Desktop/QUANTUM_LIMIT_TEST/quantum-limit-20261019T015222Z/quantum_limit/{ceiling,combinatorics}.py`.

1. **Martor pozitiv obligatoriu (înainte de orice reconstrucție):** metoda (aceeași cu importul Python 3.12.3:
   `compile(src, cale_absolută, 'exec', dont_inherit=True, optimize=-1)` + `_code_to_timestamp_pyc`) aplicată sursei
   ACTUALE cu mtime/mărimea din antetul `.pyc`-ului viu trebuie să reproducă exact sha-ul viu (`4dc02b64…`, `574aff94…`).
   Dacă nu, metoda este invalidă și nu se scrie nimic.
2. **Reconstrucția:** pentru fiecare sursă candidată, mărimea = lungimea sursei; mtime se caută exhaustiv în
   [2026-10-01T00:00Z, 2026-10-25T16:54Z] (înainte de revizia DL). Acceptare NUMAI la egalitate sha256 exactă cu
   manifestul (`aadb0d827a8d0299fd3c9776bc28686ccf2f06b7f55ab8eb796c6e869afacfa3`, respectiv
   `090f6d5e409adc260d20c6de2c7122f1a8b3387064b61cc14c95b07d4c31d700`). Egalitatea sha256 certifică octeții sigilați de DL;
   nu este o falsificare, ci restaurarea exactă a conținutului deja sigilat.
3. Octeții vii actuali se păstrează înainte în `tu4/rezultate/S35/incident_02/` (copie byte-identică). Restaurarea
   scrie numai cele două fișiere, numai dacă ambele sha-uri corespund; mtime-ul fișierului nu contează pentru DL.
   Dacă una nu se reconstruiește, nu se scrie nimic și C1 rămâne expus (raportat; orice altă cale cere amendament nou).
4. Verificare după: primul pas (DL v2 trebuie 19/19) și scanarea manifestului (exact cele 6 LIVE6 diferite). Nu se
   consumă nicio repetiție a lansatorului (cele două permise sunt consumate).

## 3. Prevenție (obligatorie până la finalizarea V11)

Orice proces al agentului care importă `quantum_limit` (sau orice modul din arborele sigilat) rulează cu `-B` și
`PYTHONDONTWRITEBYTECODE=1`. Înainte și după fiecare rulare de acest fel, scanarea manifestului DL trebuie să dea exact
LIVE6. Predarea rulează DL v2 ca ultim pas înainte de generator. Incidentul se publică; nu se ascunde.
