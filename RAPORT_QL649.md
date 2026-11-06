# RAPORT QL649 — „Quantum Lab 649” (pistă nouă, separată de DL-649)

Protocol `QL649-P1` sigilat (sha256 `66597963ed14a3ae0ceda113635056f5a263be8d66b65ed40bab2cc24ccce430`, 2026-10-25T17:40:06.366431+00:00), amendamente [AMENDAMENT_01.md](AMENDAMENT_01.md) (4 universuri nule descriptive în loc de 64, cost de calcul) și [AMENDAMENT_02.md](AMENDAMENT_02.md) (interdicție tare pentru variante identice), ambele sigilate înainte de backtest. Pista DL-649 (revizia 20261025T165403Z) rămâne înghețată și neatinsă.

Calcul clasic (PyTorch pe GPU NVIDIA RTX 5060 Laptop). Inspirația cuantică (non-hermitic/EP, Amplituhedron, Poincaré, Kuramoto, Born–Boltzmann, MCMC) este strict matematică: fără hardware cuantic, fără avantaj cuantic, fără noutate mondială revendicată. Arhivă deja explorată: valoare confirmatoare 0, nu set nevăzut. `positive_claims_allowed=false`.

## Backtest walk-forward cauzal unic (Mașina Timpului)

Sursa sha256 `193eaf7a6f4f9948a43e53e053ee8c03b0cd591bed0279d15d312a2857fa707c`, 2595 extrageri, 2527 pași (zile), încălzire 100 pași, 2427 pași prezisi, **2495 ținte**. Predicții scrise și sigilate înainte de scor (`PREDICTII.npz` sha256 `e1c9f6689d6569ab2d3d64e5bb3f4986a017806904b4aacac70b7cca90610c26`). Config digest `d7b87bb1226e06376c356bdae351575890b84e249eee3d90489bdf20700a11d8`, protocol=True.

| Parte | Ținte | hitsQL | hitsB | hitsR | ExcesQL/U | logQL−U | logQL−B | BrierQL | BrierU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Total | 2495 | 1833 | 1847 | 1821 | -0.000024539 | -5713.914942 | -5699.696918 | 14415.805750 | 13136.938776 |
| Prima jumătate | 1247 | 927 | 902 | 919 | 0.008690244 | -2248.447131 | -2236.020645 | 7230.768664 | 6565.836735 |
| A doua jumătate | 1248 | 906 | 945 | 902 | -0.008732339 | -3465.467811 | -3463.676273 | 7185.037085 | 6571.102041 |

| Poartă | Cerință | Rezultat | Valoare |
|---|---|---|---|
| 1 | ExcesQL/U >= 0.20 | FAIL | `-2.4538873665713723e-05` |
| 2 | hitsQL > hitsB și hitsQL > hitsR | FAIL | `[1833, 1847, 1821]` |
| 3 | logQL−logU > 0 și logQL−logB > 0 | FAIL | `[-5713.914941675743, -5699.696918236921]` |
| 4 | BrierQL < BrierU, BrierB, BrierR | FAIL | `[14415.805749647832, 13136.9387755102, 13139.967405084508, 13171.643465301917]` |
| 5 | ambele jumătăți: exces > 0 și hitsQL−hitsB > 0 | FAIL | `[[0.008690244341521658, 25], [-0.00873233908948201, -39]]` |
| 6 | ambele jumătăți: logQL−logB > 0 | FAIL | `[-2236.020645360528, -3463.6762728763897]` |

**Verdict: `QL_NO_PROMOTION_EXPLORATORY` (0/6 porți).** Descriptiv: p exact (hitsQL ≥ observat | extrageri uniforme independente) = 0.504857; potriviri varianta 1 (0..6) = [1101, 1007, 336, 50, 1, 0, 0] vs așteptat [1087.7, 1030.5, 330.3, 44.0, 2.4, 0.0, 0.0]; reuniunea celor 3 variante: 4003 hits vs 5499.2 așteptat uniform; bilete QL diferite de B la 2494 pași-țintă; EP convergent la 94.7% din pași; γ_q = 0 (punctul hermitic pe grilă) la 75.2% din pași.

Notă corectă pentru reuniune: variantele se suprapun (în medie 13.05 numere distincte din 18), deci așteptarea uniformă condiționată de mărimea reală a reuniunii este 3994.4 hits (observat 4003); cifra 5499.2 din protocol presupune 18 numere distincte și nu este comparabilă direct.

Timp: backtest 1547 s (state 2s, O1_nonhermitian_EP 497s, O2_amplituhedron 0s, O3_poincare 10s, O4_kuramoto 3s, O5_born_boltzmann 17s, O6_mcmc_qubo 1015s), SCI 1 s, vârf VRAM 2059 MiB.

Verificare independentă (NumPy fp64, fără import din engine/parser/validare): **PASS** (60/60).

## Indicele de Coerență Structurală (Multiversul Nul)

M = 8192 istorii uniforme (aceeași structură de zile). SCI = **-0.3247σ**, p empiric = **0.5796**.

| Statistică | Real | Medie nul | Abatere nul | z |
|---|---:|---:|---:|---:|
| chi_freq | 49.8656 | 43.1177 | 8.8999 | +0.7582 |
| chi_pair | 1167.1286 | 1161.2229 | 59.7252 | +0.0989 |
| chi_gap | 1002.5488 | 1023.0202 | 47.5623 | -0.4304 |
| overlap | 0.7187 | 0.7349 | 0.0150 | -1.0761 |

Interpretare `chi_gap`: suma pe cele 49 de numere a χ² histogramelor de goluri (binuri 1..20, 21+) față de media universurilor nule (lectura „per număr” din §4).

## Pipeline complet pe universuri nule (descriptiv)

- u000: exces +0.005186, hits QL/B/R 1846/1845/1849, logQL−B -3260.679, porți 0/6
- u001: exces +0.004384, hits QL/B/R 1844/1848/1830, logQL−B -5175.286, porți 0/6
- u002: exces -0.001628, hits QL/B/R 1829/1818/1779, logQL−B -4276.185, porți 1/6
- u003: exces -0.005235, hits QL/B/R 1820/1818/1863, logQL−B -3822.324, porți 0/6
- u004: exces +0.001178, hits QL/B/R 1836/1865/1853, logQL−B -3496.046, porți 0/6
- u005: exces +0.011198, hits QL/B/R 1861/1819/1823, logQL−B -4306.691, porți 2/6
- u006: exces -0.002429, hits QL/B/R 1827/1824/1773, logQL−B -3641.035, porți 1/6
- Comparație descriptivă (M = 7, nu poartă): excesul real -0.000025 se află în intervalul nul [-0.005235, +0.011198]; logQL−U real -5713.9 față de intervalul nul [-5192.2, -3274.7]. Supra-concentrarea legii marginale QL costă mii de nați și sub nul. Verificare independentă pe universuri: 7/7 PASS.
- pre-A02 u000 (păstrat, dovada defectului de unicitate): exces +0.005186, porți 0/6.

## Limite

Rezultatul nu demonstrează avantaj predictiv real și nu infirmă universal alte idei. Dacă extragerile sunt uniforme și independente, istoricul nu oferă avantaj. Variantele din UI sunt minimele energiei modelului, etichetate „exploratoriu, fără avantaj demonstrat”. Nicio evaluare prospectivă, emisie live sau promisiune de câștig.

