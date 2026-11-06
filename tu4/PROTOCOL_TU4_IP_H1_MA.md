# PROTOCOL TU4-IP-H1 „MA” — asimetrie de masă staționară, contracție James–Stein pozitivă

Parte a protocolului `tu4/PROTOCOL_TU4_IP.md` (comun: legea, e-procesul, lumile, porțile Q1–Q6). Sigilat împreună,
cu hash propriu, ÎNAINTE de cod.

## 1. Mecanismul fizic și informația pre-țintă

- **Ipoteză H_MA:** fiecare bilă i are o abatere fizică CONSTANTĂ în timp (masă, diametru, centrul de greutate,
  rugozitate) care îi dă propensiunea w_i în legea Fisher P_w. Abaterea este mică (S10: D ≤ D_max).
- **Informație pre-țintă:** numărările c_i ale tuturor extragerilor anterioare (arhivă + viitor până la t−1), cu
  pondere egală; nimic altceva (fără ordine, calendar, perechi, jocuri diferite).
- **Decizia diferită față de repere:** B (c+1) pariază întreaga abatere observată, oricât de mică (supra-pariu sub
  zgomot); uniformul nu pariază deloc. H_MA pariază o FRACȚIUNE λ = (1 − (n−3)/X²)₊ determinată de cât de mult
  depășește X² zgomotul: pe date compatibile cu uniformul (X² ≈ df) pariul ≈ 0 (e-procesul nu pierde), la abatere
  reală pariul crește spre 1. Biletul top coincide cu ordinea numărărilor (declarat: π este monotonă în w), deci
  decizia diferită este MĂRIMEA pariului — exact ce judecă e-procesul.

## 2. Modelul (exact)

N = T + t − 1, c = numărările; θ̂, X² ca în protocolul comun §3; λ = max(0, 1 − (n−3)/X²); ln ŵ = λ θ̂.
Bila Joker: aceleași formule cu n = 20, k = 1 (λ = max(0, 1 − 17/X²_B)). Precedente: James & Stein (1961),
Efron & Morris (1973, contracția empirică bayesiană); Fisher (1935) / Chen, Dempster & Liu (1994) pentru Poisson
condiționat. Contribuția proprie: numai aplicarea în tribunalul prospectiv.

## 3. Implantul A1 (lumea H1)

v ~ N(0, I_n) proiectat ortogonal pe 1 și normalizat (‖v‖ = 1), nou pentru fiecare lume; ln w = ε v cu ε > 0 rezolvat
prin bisecție (60 de iterații pe [0, ε_sup], ε_sup dublat până D(ε_sup v) > D_țintă) astfel încât D(w) = D_țintă
(abatere relativă ≤ 1e-10). w fix pentru toate cele T + H extrageri. Joker: idem, independent, pentru urna principală
(D 0.0517…) și bilă (D 0.0199…). Direcția este ALEATOARE, nu cea observată în arhivă (niciun contact cu arhiva).

## 4. Fixturile (definite exact acum)

- **F1 (decizie: mărimea pariului vs B), 6/49, N = 2595:** v_i = ((5 i) mod 49) − 24, i = 1..49 (permutare a
  −24..24, Σv = 0). c = Np + γ v, γ ales astfel încât X²(c) = 50 (γ = √(50·N p(1−p)·n / ((n−1)‖v‖²))). q_B = legea
  Fisher cu ln w = θ̂ (λ = 1). PASS dacă D(ŵ_H1) ≤ 0.1·D(ŵ_B) ȘI biletul top H1 = cele 6 etichete cu v maxim.
- **I1 (informație: pariază când abaterea e reală):** aceeași construcție cu X²(c) = 400. PASS dacă λ_H1 ≥ 0.85 și
  D(ŵ_H1) ≥ 0.5·D(ŵ_B).

## 5. Infirmare și limite

H1 este infirmat pentru tribunal dacă oricare poartă Q1–Q6 eșuează pe un joc (atunci nu intră pentru acel joc).
Dacă intră, tribunalul (S13) îl retrage la ln E_T < −10. Calificarea NU arată că abaterea există.
