# AMENDAMENT XI-C3-01 — corecție tehnică a înregistrării producției (INCIDENT_C3_01)

Scris 2026-10-31T16:55:17Z, după G4 (PASS 36/36) și după oprirea producției la prima instanță, ÎNAINTE de orice rezultat de producție
înregistrat. Protocolul `xi/PROTOCOL_XI_C3.md` (`7cfa9680…`) rămâne neschimbat.

**Incidentul.** Codul sigilat `479b2b41…` (2026-10-31T14:37Z) a pornit producția la 15:17Z: comparatorii 6/49 · P ·
40 lei au fost scriși în `comparatori.jsonl`, apoi prima instanță (6/49 · P · 40 lei · μ = 0) a fost rezolvată, dar
construirea înregistrării a ridicat `TypeError: dict() got multiple values for keyword argument 'K'` (cheile `K` și
`mu` existau și în rezultatul `solve`). Nicio instanță nu a fost înregistrată; nicio cifră a instanței nu a fost
afișată sau citită. Raportul automat a rulat pe zero instanțe (fișiere goale). Totul este păstrat în
`xi/incidente/C3_01/` (codul v1, sigiliul v1, jurnalul, raportul gol, `comparatori.jsonl` de la incident).

**Corecția (numai tehnică).** În `cmd_productie`, înregistrarea se construiește fără cheile duplicate și se completează
cu `rec.update(r)`. Diferența față de v1 este exclusiv aceasta (3 linii); metoda, obiectivul, pool-ul, parametrii
(`PARAMS`), seed-urile, instanțele și pragurile sunt identice. Reluarea instanței 6/49 · P · 40 · μ = 0 cu același seed
este deterministă (aceeași calculație), nu o selecție. Linia de comparatori deja scrisă rămâne (produsă de cod identic
pe această porțiune) și producția continuă reluabil de la ea. G4 (`G4.jsonl`, `G4_REZUMAT.json`) rămâne valabil: G4
nu folosește funcția corectată.

Cod nou: `xi/c3/portofoliu.py` `a1a8b799b96206d17bc6a0a70025d856dbfa91d51ae9a8130e7f3834bdc966db` (sigiliul
`xi/c3/SIGILIU_COD_C3.json` actualizat; v1 păstrat). `positive_claims_allowed=false`.
