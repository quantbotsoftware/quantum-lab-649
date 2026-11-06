# PROTOCOL TU4-IP-H3 „AD” — dinamica aerului: amestec incomplet ⇒ înclinare netedă pe poziția de încărcare

Parte a protocolului `tu4/PROTOCOL_TU4_IP.md` (comun: legea, e-procesul, lumile, porțile Q1–Q6). Sigilat împreună,
cu hash propriu, ÎNAINTE de cod.

## 1. Mecanismul fizic și informația pre-țintă

- **Ipoteză H_AD:** bilele sunt încărcate în cameră în ordinea etichetelor (rastel/tub 1..n). Curentul de aer
  (turbulență, timp de amestec finit, stratificare verticală, efectul pereților) nu șterge complet geometria
  inițială, iar bilele de același tip de material/lot au aceeași reacție aerodinamică. Rezultatul este o propensiune
  care variază NETED cu poziția de încărcare, adică cu eticheta: ln w_i = Σ_{m=1..K} a_m b_m(i), cu modurile cosinus
  discrete b_m(i) = √(2/n)·cos(π m (i − ½)/n), m = 1..K, K = 4 fixat acum (ortonormale, ortogonale pe 1). Premisa
  fizică (încărcare ordonată, amestec incomplet) NU este verificată pentru urnele Loteriei Române: ipoteză infirmabilă.
- **Informație pre-țintă:** numărările c_i (pondere egală) și ordinea fixă a etichetelor (cunoscută dinainte). Fără
  cifre/glife (GL649), fără legea sumei (SC), fără tranziții (MC), fără perechi (D).
- **Decizia diferită față de repere:** B/H1 tratează etichetele ca interschimbabile (biletul = cele mai mari
  numărări, oriunde ar fi). H_AD împrumută forță între etichete vecine și ignoră vârfurile izolate: biletul său este un
  bloc contiguu de etichete (fixtura F3), iar costul de învățare are K = 4 grade de libertate în loc de n − 1.

## 2. Modelul (exact)

N = T + t − 1; z_i = √((n−1)/n)·(c_i − Np)/√(N p(1−p)); X²_s = Σ_m (b_m·z)² (≈ χ²_K sub nul); θ̂ ca în comun §3;
θ̂_s = Σ_m b_m (b_m·θ̂); λ_s = max(0, 1 − (K−2)/X²_s); ln ŵ = λ_s θ̂_s. Bila Joker: aceleași formule cu n = 20, k = 1,
K = 4 (încărcarea bilelor Joker 1..20). Precedente: Ahmed, Natarajan & Rao (1974) transformata cosinus discretă;
Grenander (1981) / Wahba (1990) estimare netedă prin proiecție pe sită; James–Stein în subspațiul de dimensiune K.

## 3. Implantul A3 (lumea H3)

a ~ N(0, I_K) normalizat; ln w = ε Σ_m a_m b_m, ε > 0 prin bisecție (60 iterații) cu D(w) = D_țintă (abatere relativă
≤ 1e-10); w fix pe toate cele T + H extrageri. Joker: idem, independent, urna principală (n 45) și bila (n 20).

## 4. Fixturile (definite exact acum)

6/49, N = 2595. g_i = √n · b_1(i) = √2·cos(π(i − ½)/49); vârfurile V = {15, 20, 25, 30, 35, 40}: h_i = 3.0 pentru
i ∈ V, h_i = −18/43 altfel (Σh = 0); u = g + h; c = Np + A·u·√(N p(1−p)·n/(n−1)), A ales astfel încât X²(c) = 400.
Parametrii fixturii au fost aleși prin aritmetică de mână pe formule ÎNAINTE de sigiliu (design, fără date, fără cod).
- **F3 (decizie):** PASS dacă biletul H1 = V exact, λ_s > 0, biletul H3 este un bloc de 6 etichete CONSECUTIVE și
  biletul H3 ∩ V = ∅.
- **I3 (informație: aceleași numărări ca multi-mulțime, altă așezare):** c (din F3 cu h ≡ 0, adică numai g scalat la
  X² = 100) și c' = aceeași listă de valori așezată după permutarea σ(i) = ((5 i) mod 49) + 1 (c'_{σ(i)} = c_i). X² și
  multi-mulțimea numărărilor sunt identice. PASS dacă D(ŵ_H1(c)) = D(ŵ_H1(c')) (|Δ| ≤ 1e-12) ȘI
  D(ŵ_H3(c)) ≥ 10·D(ŵ_H3(c')).

## 5. Infirmare și limite

Ca în H1/H2 (Q1–Q6; retragere la ln E_T < −10). Implantul la D_max al familiei marginale complete este o margine
GENEROASĂ pentru H3: o abatere netedă de această mărime ar fi fost vizibilă puternic în arhivă (X² concentrat pe 4
grade de libertate); frontiera specifică familiei netede nu se calculează aici (ar fi o statistică nouă pe arhivă).
Puterea la D_max este deci un plafon, declarat.
