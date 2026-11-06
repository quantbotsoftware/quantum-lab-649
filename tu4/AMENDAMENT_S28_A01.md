# AMENDAMENT TU4-S28-A01 — numărul sloturilor din P2(4) (eroare de numărare în protocolul sigilat)

Stare: scris și sigilat (`tu4/SIGILIU_AMENDAMENT_S28_A01.json`) după sigiliul S28 (`0b4fd79b…`, 12:52:18Z) și ÎNAINTE de
orice cod de verificare S28 (`tu4/s28/` inexistent) și înainte de orice verificare S28. Incident de pregătire declarat:
`tu4/rezultate/S28/INCIDENT_S28_01.json`. Protocolul `tu4/PROTOCOL_QUANTUM_S28.md` (`d1480622…`, 0444) rămâne NESCHIMBAT.
`positive_claims_allowed=false`.

## 1. Defectul

§3 P2(4) spune: „sloturile 2026-10-29T14:00Z → 2026-11-01T14:00Z sunt exact cele 8 din §2, iar sub H_BLOCAT primele 7 dau
`postponed` și ultimul (13:20Z) emisie”. Tabelul din §2 al aceluiași protocol listează însă vineri 3 sloturi, sâmbătă 3
sloturi și duminică 3 sloturi (06:20Z, 10:20Z, 13:20Z) = **9** sloturi; slotul de joi 13:20Z (15:20 Europe/Bucharest) este
înaintea cutoff-ului de joi 14:00Z și aparține țintei 2026-10-29 (deja emisă). Numărul „8/7” este o greșeală aritmetică
a textului, nu o schimbare de calendar.

## 2. Regula amendată (singura schimbare)

P2(4): sloturile din intervalul (2026-10-29T14:00Z, 2026-11-01T14:00Z) sunt exact cele **9** din §2 (vin 30, sâm 31,
dum 1 nov, fiecare la 06:20Z, 10:20Z, 13:20Z), iar sub H_BLOCAT primele **8** dau `postponed` și ultimul (2026-11-01T13:20Z)
dă emisie. Toate celelalte criterii, praguri, ferestre și verdicte rămân cele sigilate.

## 3. Încadrare

Incidentul `S28_01` este de pregătire (text de protocol), detectat la recitirea protocolului înainte de scrierea
verificatorului. Nu s-a citit nicio dată nouă, nu s-a rulat nicio verificare S28 și nu s-a schimbat niciun prag. Verdictul
S28 se raportează împreună cu acest incident (nu „zero incidente”).
