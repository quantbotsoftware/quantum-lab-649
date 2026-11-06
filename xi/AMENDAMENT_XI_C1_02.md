# AMENDAMENT XI-C1_02 — permutarea anti-mulțime numai în domeniul validat al modelului (înainte de rerulare)

Scris și sigilat după inspecția primului rezultat §5 și ÎNAINTE de orice nouă permutare. Motiv (constatat, publicat):
`PERMUTARE_J140P.json` dă EV 301.27 lei față de 298.66 (identitate) și 271.14 (media permutărilor aleatoare), dar
**toate cele 140 de bilete** din J140 și din J140P sunt marcate de `quantum_limit.ceiling.patterned` (runde de numere
consecutive). Pentru asemenea bilete modelul mulțimii este declarat optimist („outside the model's validated domain”):
jucătorii de modele vizuale sunt o populație pe care modelul nu o vede. Câștigul EV ar exploata deci punctul orb al
modelului. J140P rămâne publicat, cu eticheta **EXCLUS_DOMENIU**, și nu intră în evaluarea §6.

**§5 (completare).** Restricție tare: designul permutat trebuie să aibă **zero** bilete marcate de `patterned`
(aceeași funcție, importată nemodificat). Recoacerea acceptă numai stări fără bilete marcate; pornește de la cea mai
bună permutare aleatoare fără bilete marcate. Comparatorii se raportează și restrânși la permutările aleatoare fără
bilete marcate. Eticheta identică se raportează informativ, cu numărul de bilete marcate. Fișierul rezultat primește
sufixul `Q` (de exemplu J140Q), cu re-verificare exhaustivă §4. Aceeași regulă se aplică designului 6/49.
Restul protocolului rămâne neschimbat.
