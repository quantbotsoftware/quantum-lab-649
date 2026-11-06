# AMENDAMENT S35_01 — restaurarea fișierului înghețat `predari/genereaza_predare.py` și a doua repetiție

Scris și sigilat după INCIDENT_S35_01 și ÎNAINTE de orice restaurare sau rulare nouă. Criteriile Q7S v2 (§3), fereastra,
garda și lansatorul rămân NESCHIMBATE; nu se modifică niciun verificator.

## 1. Constatarea (din repetiția oficială, 23:03:59Z)

`predari/genereaza_predare.py` este înghețat (sha `8273c198…`) în sigiliile FR, L1, S17–S31, SM1, UI și în listele
`frozen_hashes` verificate de Q0 (S24) și A0 (S25). Sesiunea precedentă (același agent) l-a modificat la 22:39Z
(„v2”: partea operativă inclusă și în PROMPT), fără protocol, după S33. Efect: Q0 și A0 dau FAIL `inghetate_fara_drift`,
iar suita moștenită arată `drift ['predari/genereaza_predare.py']` ⇒ duminică C1 ar fi picat pe L5, L10, L12 și pe V0L.
Repetiția și-a făcut exact treaba: a detectat deriva înainte de duminică.

## 2. Remedierea (singura permisă)

1. Octeții v2 actuali (sha `7297ffd1…`) se copiază byte-identic în `tu4/rezultate/S35/incident_01/genereaza_predare_v2.py`
   și în fișierul NOU `predari/genereaza_predare_v2.py` (neînghețat), care devine instrumentul de predare (Regula 108).
2. `predari/genereaza_predare.py` se restaurează la octeții înghețați v1, sha **`8273c198a24dc31e5cea098914aa2b12103970da53fb54ccdefff4a9a3f8a4f8`**.
   Reconstrucția este deterministă: v2 cu `PROMPT_HEAD` luat din `predari/istoric/PROMPT_QL649_20261029T192312Z.txt`
   (generat de v1; antetul până la anexa A, cu UTC-ul înlocuit de `{utc}`) și linia de scriere a PROMPT-ului fără
   partea operativă. Restaurarea se face NUMAI dacă sha-ul rezultat este exact `8273c198…`; altfel nu se scrie nimic.
3. Incidentul se păstrează în `tu4/rezultate/S35/` (NU în `tu4/incidente/`, unde L2 cere exact 9 directoare).

## 3. A doua repetiție (exact una)

După restaurare: exact o rulare nouă `c1_duminica.sh --repetitie`, în aceleași condiții (§5 din protocol). Prima
repetiție rămâne publicată așa cum a ieșit (inclusiv FAIL-ul). Dacă a doua pică din alte motive, se raportează; orice
altă corectură cere un amendament nou înainte de duminică.
