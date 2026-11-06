# AMENDAMENT TU3-02 (înainte de orice cod al modulului J)

Scris 2026-10-26 ~15:50Z, după TU3-01 (15:44:25Z) și ÎNAINTE de orice cod/calcul.
Motiv (derivare de mână): RK4 explicit este stabil numai pentru `dt·λ ≲ 2.78`. Pe grila fixată κ̃ ≤ 100, cu
date concentrate (|Δ_j| / mean|Δ| până la n = 45) sau pe fixtura W9 cu ω, |Δ| de ordin 1, `κ|Δ_j|` poate depăși
50, deci dt = 0.05 ar produce divergență numerică, nu dinamică.
Clarificare de implementare (modelul, grila de ieșire t = 0, 0.05, …, 20, κ̃, K_m, pragurile NU se schimbă):
fiecare pas de ieșire dt = 0.05 se integrează cu `s = max(1, ⌈dt·L / 0.5⌉)` sub-pași RK4 egali, unde
`L = max_j(κ|Δ_j|) + K_m + max_j|ω_j|` (margine Lipschitz, calculată pe tot lotul). `s` se raportează în ieșire.
Fracția blocată folosește viteza `|dθ/dt|` evaluată exact la starea finală (t = 20).
