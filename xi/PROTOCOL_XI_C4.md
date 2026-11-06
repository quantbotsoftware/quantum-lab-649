# PROTOCOL XI-C4 — simulatorul probabilității de profit (planul V11, faza B)

Scris și sigilat ÎNAINTE de codul C4. Autoritate: cererea din 2026-10-30 00:24 EET (execuția V11, autonomie
deplină). `positive_claims_allowed=false`. C4 NU este un model predictiv: biletele sunt uniforme, iar
probabilitățile sunt exacte. Plățile istorice se folosesc numai ca distribuție economică. Calcul clasic pe GPU.

## 1. Întrebarea

Pentru strategii simple, cu prețurile curente (6/49 8 lei, 5/40 5 lei, Joker 7 lei): care este **probabilitatea
de a fi pe plus** (câștig brut cumulat ≥ miza cumulată) după 1, 5 și 10 ani (104 date de extragere/an), și care
este distribuția pierderii?

## 2. Date

Instantaneul curent al bazei (`quantum_limit.data.default_database()`, read-only, sha256 înregistrat). Extragerile
regulate de la 2010-05-02. **Fereastra principală: ultimele 312 date comune celor 3 jocuri (≈ 3 ani).** Fereastra
de sensibilitate: toate datele de la 2010-05-02, descriptiv.

## 3. Probabilitățile exacte pe bilet (fracții în Q, verificate exhaustiv)

- 6/49: I/II/III/IV = 6/5/4/3 nimeriri, hipergeometric (6 din 49, bilet de 6).
- 5/40 (bilet de 5, extragere de 6 în ordine): I = biletul este exact primele 5 bile, P = 1/C(40,5);
  II = 5 nimeriri altfel, P = C(35,1)/C(40,6) − 1/C(40,5); III = exact 4 nimeriri, P = C(5,4)·C(35,2)/C(40,6).
- Joker: h_m = C(5,m)·C(40,5−m)/C(45,5); categoria cu Joker potrivit primește factorul 1/20, cea fără 19/20:
  I(5,J), II(5), III(4,J), IV(4), V(3,J), VI(3), VII(2,J), VIII(1,J).

Verificare: pentru 5/40 se enumeră exhaustiv pe GPU toate cele 3 838 380 de extrageri ordonate-relevante față de
un bilet fix; pentru 6/49 și Joker se verifică Σ categorii + P(fără premiu) = 1 exact în Q și se compară cu
enumerarea exhaustivă a numărului de nimeriri (13 983 816 și 1 221 759 de stări).

## 4. Plata biletului nostru într-o extragere istorică d, la categoria c

- `paid` cu w câștigători: plata = payout_per_win · w/(w+1) (același fond împărțit la w+1). La categoria fixă
  6/49 IV: payout_per_win exact.
- `rollover` (w = 0): plata = `carryover` (am fi câștigătorul unic al fondului reportat).
- `paid_non_cash`, `not_applicable`, `paid_amount_unavailable` sau valoare lipsă: plata = 0 (conservator),
  cu numărare raportată.
- Sume **brute, fără impozit**: rezultatul supraestimează câștigul net.

## 5. Strategii (fixate acum)

- **U_g**: 1 bilet pe dată la jocul g ∈ {649, 540, joker}; **U_3**: câte 1 bilet la fiecare joc.
- **B_x_opt**: buget x ∈ {40, 100, 500} lei/dată, investit integral în jocul cu randamentul analitic maxim
  ρ_g = E[plată]/preț din fereastra principală (⌊x/preț⌋ bilete distincte).
- **B_x_egal**: buget x împărțit egal pe cele 3 jocuri (⌊x/3/preț_g⌋ bilete la fiecare).

Biletele distincte din aceeași dată sunt tratate ca independente la nimeriri. Aproximarea este declarată:
corelația dintre ≤ 100 de bilete distincte din 14M este neglijabilă, iar o verificare exactă pe cazul de 2 bilete
se raportează.

## 6. Monte Carlo

Pentru fiecare sezon simulat și fiecare dată: se trage uniform un indice de dată istorică din fereastră, același
pentru cele 3 jocuri, ca să păstreze corelația reporturilor din aceeași zi. Pentru fiecare joc: numărul de bilete
pe categorie ~ Multinomial(n_bilete, p), eșantionat prin binomiale condiționate pe GPU. Plata vine din §4.
M = 10⁶ sezoane per strategie și orizont, seed 20261030, PyTorch CUDA, fp64 pentru sume.

## 7. Ieșiri

Per strategie și orizont: P(net ≥ 0), mediana și cuantilele 1/5/25/75/95/99% ale netului, miza totală,
randamentul mediu, P(cel puțin un premiu ≥ 1 000 lei), plus randamentul analitic ρ_g pe ambele ferestre. Fișierele
`xi/rezultate/C4/C4_REZULTATE.json` (0444) și `xi/rezultate/C4/RAPORT_C4.md`.

## 8. Porți de corectitudine (înainte de publicarea cifrelor)

- **V1**: media simulată a netului per dată se încadrează în ±4 SE față de valoarea analitică
  Σ_c p_c·E[plată_c] − preț, pentru fiecare strategie.
- **V2**: probabilitățile exacte trec verificările din §3.
- **V3**: P(cel puțin un premiu într-o dată, 1 bilet) simulată se încadrează în ±4 SE față de valoarea exactă.

Dacă o poartă pică, cifrele nu se publică drept rezultat. Se declară incident și se corectează tehnic,
fără ajustări după rezultat. O singură rulare de producție.
