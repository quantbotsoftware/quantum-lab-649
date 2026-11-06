# AMENDAMENT 02 la PREINREGISTRARE_QL649.md (protocol QL649-P1)

Scris: 2026-10-25, ÎNAINTE de backtestul unic pe istoria reală (`rezultate/backtest_unic`
nu există); niciun scor de performanță pe istoria reală nu a fost văzut.

## Constatare (pe universul nul sintetic u000, prin verificatorul independent)

Protocolul cere (§6, §7) exact 3 variante UNICE, dar energia O6
`… + 1.0·Σ_{w<v}|S ∩ S_w|` permite ca, la π_QL foarte concentrat, o variantă ulterioară
să fie identică cu una anterioară (penalizare +6 mai mică decât costul alternativei).
Pe u000: 2 pași din 2427 cu variante duplicate (verificatorul a raportat FAIL
`variants_unique_per_step`). MCMC-ul a găsit corect minimul energiei definite; definiția era incompletă.

## Modificare

- O6: pentru varianta v, orice combinație identică cu o variantă anterioară w < v primește
  penalizare tare `+1e6` (interdicție). Restul energiei rămâne neschimbat.
- Nu se schimbă varianta 1 (biletul QL folosit în porțile 1, 2, 5), nici π_QL (log/Brier,
  porțile 3, 4, 6). Afectată poate fi doar statistica descriptivă „reuniunea celor 3 variante”.
- Universul u000 rulat cu codul pre-A02 se păstrează integral ca
  `rezultate/multivers_pipeline_preA02/u000` (cronometrare și dovada defectului).
  Cele 4 universuri nule descriptive (Amendament 01) se rulează cu codul final.
