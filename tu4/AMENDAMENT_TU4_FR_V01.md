# AMENDAMENT TU4-FR-V01 — defect în verificatorul separat (comasarea claselor de suprapunere), înainte de remediere

Scris și sigilat (`tu4/SIGILIU_AMENDAMENT_TU4_FR_V01.json`) ÎNAINTE de orice modificare a `tu4/verifica_fr.py`.

**Fapte.** Prima rulare completă a verificatorului (20:54:33Z) = **`VERIFICARE_FR_FAIL`**, 47/64: eșuează exclusiv
verificările legate de C2 (grupurile de suprapunere, numărările lor, X²_C2, D_max C2, N C2, p_MC C2 la 6/49 și 5/40).
Cauza, demonstrată: în `groups_for`, instrucțiunea `g[-2] = g[-2] + g.pop()` evaluează ținta `g[-2]` DUPĂ `pop()`,
deci scrie grupul comasat peste penultimul element greșit (ex. 6/49: grupuri corupte, D_max C2 = 0.0). Regula din
protocol §4 („categoriile de coadă comasate de sus până la așteptare ≥ 5”) este implementată corect în
`tu4/frontiera.py` (6/49 `[[0],[1],[2],[3,4,5,6]]`, 5/40 `[[0],[1],[2],[3],[4,5,6]]`, Joker `[[0],[1],[2],[3,4,5]]`).
Toate celelalte 47 de verificări (C1, C3, C4, bilă, quantile, D_max C1 prin Newton, exces, N, p_MC) au trecut.

**Păstrare (nerescrisă).** `tu4/incidente/FR_01/`: `VERIFICARE_FR_FAIL_01.json` (`95d5dade…`), jurnalul rulării
(`13b22088…`), copia verificatorului defect `verifica_fr_defect.py` (`e6fac48d…`), `INCIDENT_TEHNIC_FR_01.json`.

**Remediere permisă (una singură).** În `tu4/verifica_fr.py` se schimbă NUMAI `groups_for`: `last = g.pop();
g[-1] = g[-1] + last` (semantica regulii din protocol). Nimic altceva: aceleași toleranțe, aceleași semințe, același
R = 2000. `FR_REZULTATE.json` (`04f1e730…`), `tu4/frontiera.py`, martorii și protocolul rămân NESCHIMBATE; rularea
reală NU se repetă. O singură rulare suplimentară a verificatorului; verdictul ei se publică oricare ar fi.
