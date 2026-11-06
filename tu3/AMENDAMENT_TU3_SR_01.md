# AMENDAMENT TU3-SR-01 — precizări înainte de cod (S7)

Stare: scris și sigilat (`tu3/SIGILIU_AMENDAMENT_TU3_SR_01.json`) DUPĂ sigiliul protocolului `PROTOCOL_TU3_SR.md`
(`7f38a94b…`, sigilat 2026-10-27T15:48:58Z) și ÎNAINTE de orice cod și de orice calcul (`code_files_present: []`,
`results_present: false`). Nu schimbă nicio țintă, metrică, comparator, prag, α, B, G, sămânță sau criteriu P1–P5.
Motiv: două neconcordanțe interne ale protocolului, observate la proiectarea codului (fără date, fără rulări).

## A1. Starea MPS și „entanglement-ul dintre urne” (§0 și §3.5)

§0 descrie entropia „stării √P(S, a)”, iar §3.1/§3.5 descriu un MPS cu un SIT de mod b. Cele două coincid sub nul, dar
nu sub semnal: √(Σ_b p_b P_b(S) P_b(a)) nu are rang Schmidt ≤ 2 în general și nu este un MPS cu legătura (b, c).
Precizare (definiția folosită în cod):
- Starea MPS este PURIFICAREA modelului cu variabilă latentă: |Ψ⟩ = Σ_b √p_b |b⟩ ⊗ |ψ_b⟩_principal ⊗ |χ_b⟩_Joker, cu
  ‖ψ_b‖ = ‖χ_b‖ = 1 (amplitudinile modului se normalizează cu Z_b din mediile MPS). Situl de mod este FIZIC (se
  eșantionează primul); Born pe toate siturile dă (b, S, a) cu probabilitatea p_b P_b(S) P_b(a), iar marginala în (S, a)
  este exact legea amestecului (§3.3). Sub nul (un singur mod) |Ψ⟩ = |D^n_r⟩ ⊗ |uniform⟩ = √P(S, a) (produs).
- „Entanglement-ul dintre urne” = entropia von Neumann la tăietura (mod + urna principală | urna Joker) a stării pure
  |Ψ⟩, adică S(Σ_b p_b |χ_b⟩⟨χ_b|). Nul: EXACT 0 (rang 1). Semnal: 0 < S ≤ ln 2. Marginea min-cut: ln χ_eff al legăturii
  dinaintea sitului Joker (χ_eff = numărul de moduri cu pondere nenulă după eliminarea blocurilor nule). Martorul W5 rămâne
  neschimbat. Este o mărime a purificării (descriptivă), nu o corelație fizică între bile.

## A2. Granularitatea loturilor față de plafonul termic (§3.7 și §4.2)

§3.7 cere loturi ≤ 16 pași de motor între verificările termice, iar §4.2 fixează `score_steps(…, chunk = 64)`. În plus,
O6 (`variants_steps`, 3 × 10 000 de iterații Metropolis) are un cost fix per apel (lansări de kernel) și nu poate fi
întrerupt în interiorul unui apel. Precizare, aplicată identic în S7 (puterea) și în S8 (rularea reală):
- O1–O5: `motor_n.score_steps` (S8, semințele `step_seed`) / `motor_n.score_states` (S7, semințele §5.2) pe sub-loturi
  de ≤ 16 stări consecutive; verificare termică înainte de fiecare sub-lot.
- O6: `motor_n.variants_steps` pe loturi de ≤ 64 de stări consecutive (aceleași semințe); ÎNAINTE de fiecare lot O6, dacă
  T ≥ 66 °C, pauză până la T ≤ 62 °C (lotul nu poate fi întrerupt); regula generală (T ≥ 69 °C ⇒ pauză până la 64 °C) se
  aplică înaintea oricărui lot.
- RNG-ul motorului este pe contor ⇒ aceleași fluxuri aleatoare indiferent de lot; diferențe în virgulă mobilă datorate
  mărimii lotului (kernel-uri GPU) sunt posibile și se declară; nu sunt alegeri dependente de date.
- Mărimea lotului NU se modifică după vizualizarea vreunui rezultat.

## A3. Nimic altceva nu se schimbă

Ținte, metrici, comparatori, praguri, ferestre, B, G, semințe, criteriile P1–P5, verdictele D1/D2/promovare, ordinea §7 și
declarațiile §9 rămân cele din protocolul sigilat. `positive_claims_allowed=false`.
