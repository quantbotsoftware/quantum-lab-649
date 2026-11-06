# AMENDAMENT S34_01 — corecții de specificație DL v2, înainte de prima rulare oficială

Scris și sigilat ÎNAINTE de orice rulare oficială a `verifica_publicarea_v2.py` (rezultate S34 inexistente).
Testul pe uscat, fără scriere de rezultate, a arătat două presupuneri greșite din §2 al protocolului S34, ambele
despre FORMATUL produsului, nu despre datele de extrageri:

1. **D3**: `seal_sha256` din `registru.json` NU este sha256 al fișierului de sigiliu. Este câmpul `sha256` din
   interiorul sigiliului, adică hash-ul canonic al înregistrării fără câmpul `sha256` (`quantum_limit/prospectiv.py`
   L38/L166). Regula corectată: pentru fiecare intrare nouă, fișierul de sigiliu există, câmpul lui `sha256` ==
   `seal_sha256`, iar recalcularea canonică (`prospectiv._digest`,
   importată nemodificat) dă aceeași valoare.
2. **D4**: raportul Joker conține o linie derivată cumulativă „Numărul Joker (k extrageri obligatorii): …”,
   recalculată la fiecare punctare, la fel ca titlul. Regula corectată: liniile care încep cu „Numărul Joker (”
   sunt tratate ca titlul (se exclud din subsecvență), dar trebuie să existe și în nou, cu k care nu scade.

Restul protocolului S34 rămâne neschimbat. Nu se schimbă pragurile, fișierele verificate sau Q4 v2.
