# AMENDAMENT TU3-01 (înainte de orice cod al modulului J)

Scris 2026-10-26 ~15:45Z, după sigilarea TU3-P1 (15:43:01Z, `694d3545…6b04`) și ÎNAINTE de orice cod/calcul.
Motiv (derivare de mână, nu rezultat): în ecuația Adler `dθ/dt = ω + κa sin(ϑ − θ)` un nod blocat relaxează cu
rata `λ = √(κ²a² − ω²) ≤ κa`. La κ̃ mic (de ex. 0.1) pe date de mărimea arhivei, κa ~ 1e-2, deci la orizontul
t = 400·0.05 = 20 avem λt ~ 0.2: nodul este analitic blocat, dar viteza finală poate depăși 1e-3. Un nod neblocat
are viteza minimă `|ω| − κa`, care poate fi < 1e-3 lângă frontieră. Criteriul numeric din §2.7 nu poate deci egala
numărătoarea analitică pe aceste noduri, indiferent de corectitudinea integratorului.

Clarificări (nu schimbă definițiile, pragurile de putere sau verdictul):
1. W9 compară clasificarea nod cu nod numai pe nodurile NE-frontieră, unde frontieră = oricare dintre:
   (a) `| |ω|/(κa) − 1 | < 0.02` (ca în P1); (b) blocat analitic cu `λ·t_final < 20`; (c) neblocat analitic cu
   `|ω| − κa < 1e-2`. Numărul nodurilor excluse se raportează. Convergența la `ϑ + arcsin(ω/(κa))` (1e-4) se verifică
   pe nodurile blocate ne-frontieră.
2. Ieșirea produsului raportează ALĂTURI de `L(κ)` numeric și fracția analitică Adler
   `L_A(κ) = #{j : |ω_j| ≤ κ|Δ_j|}/n` (exactă numai pentru K_m = 0; descriptivă pentru K_m = 2).
3. Martorul W9 se rulează pe un univers sintetic nul (sămânța 649010, T = 2201) peste toată grila κ̃, plus o
   fixtură deterministă cu ω și |Δ| de ordin 1.
