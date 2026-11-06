# AMENDAMENT 01 la WU649-P1 — toleranța de zgomot în testul Armijo

Scris și sigilat ÎNAINTE de orice cod WU649 și de orice calcul WU649 (real, sintetic sau
construit). Protocolul `PREINREGISTRARE_WU649.md` (sha256 `e46db3cf…f961`) rămâne neschimbat
în rest. Nu modifică ipoteza, priorul, cuadratura, certificatele, martorii, porțile sau
verdictul.

## Defect anticipat (analitic, fără calcul)

`log posterior` real este o sumă de circa 2600 de termeni `log P(S_t) ≈ −16`, fiecare evaluat
printr-un logsumexp pe 129 de noduri, cu eroare de ordinul câtorva ulp (≈1e-14). Zgomotul
sumei este de ordinul `1e-13 … 1e-12`. Lângă optim, creșterea adevărată a unui pas Newton
este `≈ ½ g·δ`; la `‖g‖_∞ ≈ 1e-6` aceasta este `≈ 1e-13`, sub zgomot. Testul Armijo strict
`lp_nou ≥ lp + c·pas·g·δ` poate eșua din cauza zgomotului de rotunjire, iar Newton s-ar bloca
înainte de `‖g‖_∞ ≤ 1e-8`. Defectul este numeric, nu al ipotezei.

## Modificare

1. Diferența `lp_nou − lp` se calculează ca `Σ_t (log P_t(nou) − log P_t(vechi))` minus
   diferența priorului (aceleași evaluări, ordine de însumare fixă).
2. Testul Armijo devine `lp_nou − lp ≥ c·pas·g·δ − τ`, cu **`τ = 1e-10`** (toleranță de
   zgomot fixată acum). În rest: `c = 1e-4`, înjumătățire, cel mult 60.
3. Certificatul de pas rămâne neschimbat și este singurul criteriu de acceptare a lui `θ̂`:
   `‖g‖_∞ ≤ 1e-8` ȘI `−H` pozitiv definită (Cholesky). Pentru determinism bit cu bit (Q3),
   BLAS rulează cu un singur fir în fiecare proces.

Toleranța τ poate accepta doar pași care scad `lp` cu cel mult `1e-10`, adică în interiorul
zgomotului numeric. Nu poate schimba punctul staționar certificat.
