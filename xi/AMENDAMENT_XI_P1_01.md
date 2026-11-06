# AMENDAMENT XI-P1-01 — construcția FERMI (eroare de derivare găsită înainte de cod)

Scris și sigilat ÎNAINTE de orice cod P1 și de orice citire a extragerilor reale. Protocolul `xi/PROTOCOL_XI_P1.md`
(`731b6839…`, sigilat 2026-10-31T19:18:07Z) rămâne neschimbat ca fișier; acest amendament înlocuiește numai punctele
de mai jos. Incident: `xi/incidente/P1_01/INCIDENT_P1_01.json`.

## 1. Defectul

În §3, FERMI(m) potrivea marginalele de perechi prin formula DPP (cu mărime aleatoare) K_ij = sqrt(π̂_iπ̂_j − π̂_ij).
La T' = 0 (π̂ = valorile uniforme) rezultă K = (p − c₀)I + c₀J cu c₀ = sqrt(p² − q); pentru 6/49 c₀ = 0.0473 și
spectrul lui K este [0.0751, 2.3935]: valoarea proprie 2.39 > 1 este tăiată la 1 − 10⁻⁹, deci ℓ ≈ 10⁹ și det(L_S) pierde
~7 cifre semnificative în float64 (Q1c, toleranța 10⁻¹², ar fi picat; verificatorul independent la fel). Cauza: o
mulțime uniformă de mărime fixă k NU este un DPP cu acele marginale; potrivirea momentelor prin formula DPP nu se
aplică unui k-DPP. Verificarea a fost numai analitică (formula la T' = 0, fără date). Nicio linie de cod P1 nu exista.

## 2. Înlocuirea (FERMI(m), m ∈ {200, 800, 3200}, k ≥ 2; bila Joker rămâne pe U)

- π̂_i = (c_i + m·p)/(T' + m); π̂_ij = (C_ij + m·q)/(T' + m), q = k(k−1)/(n(n−1)) (neschimbate).
- Exces de perechi (log-raport față de independența cu perechi uniforme):
  φ_ij = ln(π̂_ij/q) − ln(π̂_i/p) − ln(π̂_j/p), i ≠ j; φ = 0 exact la uniform.
- A_ij = sqrt(max(−φ_ij, 0)) pentru i ≠ j, A_ii = 0; M = I + A = U·diag(μ)·Uᵀ; μ⁺ = max(μ, 10⁻⁶); L = U·diag(μ⁺)·Uᵀ.
- k-DPP: P(S) = det(L_S)/e_k(μ⁺); marginala π_i = Σ_j U_ij²·μ⁺_j·e_{k−1}(μ⁺_{−j})/e_k(μ⁺).
- Justificare: pentru o pereche, det(I + A_{ij}) = 1 − A_ij² = 1 + φ_ij (φ ≥ −1), deci la ordinul doi potențialul de
  pereche al k-DPP-ului este exact excesul estimat (stare fermionică de tip Slater; numai respingerea, φ > 0 → 0).
  Limita uniformă: φ = 0 ⇒ A = 0 ⇒ L = I ⇒ P uniform. Singularele rămân uniforme în FERMI (abaterile individuale sunt
  ale lui STAT).

## 3. Consecințe pentru calificare (Q1f, Q4)

- Σ_FERMI (Q4) rămâne k-DPP-ul cu L = I + s·B pe blocuri de 7, cu aceeași regulă pentru s (KL ≥ 0.05 nați/extragere).
  Eșantionarea lui exactă se face prin ocupările blocurilor: vectorul (m_1..m_7), Σm_b = 6, se trage din legea exactă
  ∝ ∏_b C(7, m_b)(1 + s·m_b), apoi m_b numere uniform în blocul b (lege identică cu k-DPP-ul).
- Q1f testează acest eșantionator (în locul celui spectral Kulesza–Taskar, care nu mai e folosit): n = 14, k = 4,
  blocuri de 7, s = 2, 200 000 de eșantioane, χ² față de probabilitățile det(L_S)/Σdet, p > 0.001. Testul CB rămâne.
- Q1b se aplică noii construcții: n = 12, k = 4 cu A aleator (|φ| ≤ 1): Σ det(L_S) = e_k(μ⁺) relativ ≤ 10⁻¹⁰, marginale
  ≤ 10⁻¹⁰; n = 40, k = 6: suma pe toate mulțimile = 1 ± 10⁻⁸.
- Restul protocolului (date, celelalte modele, mixturi, scoruri, porți, producție, verificare, interpretări) neschimbat.
