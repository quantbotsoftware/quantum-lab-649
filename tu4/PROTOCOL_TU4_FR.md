# PROTOCOL TU4-FR — sesiunea S10 „FR”: frontiera matematică a abaterii fizice a urnei (6/49, 5/40, Joker)

Stare: scris și sigilat (`tu4/SIGILIU_TU4_FR.json`) ÎNAINTE de orice cod al sesiunii și ÎNAINTE de orice calcul pe
arhivele reale. Plan: `tu4/PLAN_SESIUNI_TU4_v2_20261027.md` (`32533d53…`) §2 S10. Autoritate: Mesajul 52 (numai
predicție) și Mesajul 53 (2026-10-27T20:42Z: „PREDICȚIE PURĂ bazată pe abaterile fizice ale urnei”, D1 ridicat
explicit, linger, eliminarea filtrului de popularitate, „rulează S10 direct”). `positive_claims_allowed=false`.
Primul pas al sesiunii (read-only, `/tmp/ql649_s10/primul_pas.log`), înainte de acest protocol: toate hash-urile,
`drift [] closed []`, `ok: true`, `S7_PASS`, `VERIFICARE_SR_PASS` ×2, 32 / 38+3s / 71 passed, matricea READY, DL exit 0.

## 0. Deciziile operative din Mesajul 53 (decizii ale agentului, delegate)

- **Linger:** `loginctl show-user tony -p Linger` = `Linger=yes` la 20:43Z — deja activ; nicio comandă necesară.
  Temporizatoarele utilizatorului (`loto-actualizare.timer` etc.) rulează și fără sesiune deschisă.
- **Gardul D1 (cerere explicită primită):** gardul blochează din 24 oct prognozele produsului vechi
  (`loto_romania/cohorta.py:163`, cohorta activă `221a3a10…`), al cărei protocol înghețat conține DOUĂ modele:
  `gpu-v1` și **`popularitate-v1`** (modelul „ce joacă mai puțini clienți”). Re-înghețarea ar reporni automat exact
  filtrul de popularitate pe care punctul 3 îl interzice; scoaterea lui din produsul vechi cere rescrierea registrului
  prospectiv (validarea cere `set(models) == MODELS`) și atinge descărcătorul oficial care alimentează arhivele LIVE ale
  tuturor jocurilor. Decizie: autorizarea emisiei automate din timer se aplică **tribunalului TU4** (emițătorul S12 +
  timer/drop-in propriu, sigilat), care NU conține și NU va conține cod de popularitate. Produsul vechi rămâne blocat ⇒
  `popularitate-v1` NU emite nimic (efectul cerut la punctul 3), fără risc pentru arhiva LIVE. Codul vechi nu se șterge
  (registrul istoric îl referă); se declară.
- **„64 de universuri paralele / LQG / operatori WZW securizați”:** în cod, „universurile paralele” sunt istoriile
  SIMULATE UNIFORME ale testului SCI (prin construcție fără abatere); nu există operatori WZW sau LQG securizați.
  O abatere fizică a urnei este o proprietate statistică a frecvențelor; se măsoară exact mai jos. Formalismul LQG/WZW
  nu adaugă informație (PL649: 0/6, p 0.948) și nu se folosește.

## 1. Întrebarea

Pentru fiecare urnă — 6/49 (6 din 49), 5/40 (6 extrase din 40, bilet de 5), Joker principal (5 din 45) și bila Joker
(1 din 20) — cât de mare poate fi o abatere fizică ÎNCĂ NEDETECTATĂ în arhivă, cât ar valora ea în potriviri și câte
extrageri VIITOARE ar fi necesare ca un e-proces s-o demonstreze? Inventar statistic, nu selecție de modele.

## 2. Date (numai citire, surse înghețate)

6/49 `next_candidate/predictie_numere/probe_date/extrageri_649.jsonl` (`193eaf7a…`, 2595), 5/40
`tu3/date/extrageri_540.jsonl` (`e1591b87…`, 2490), Joker `tu3/date/extrageri_joker.jsonl` (`45713aa2…`, 2202). Câmpuri:
`numbers_sorted` (6/49) / `numbers` (5/40, Joker), `joker`. Validare: k numere distincte în 1..n, bila în 1..20; orice
abatere ⇒ eroare (nu reparare). Ordinea: (`draw_date`, `within_day_sequence` dacă există, `draw_key`). Analiza
principală = toate extragerile; sensibilitate DESCRIPTIVĂ = numai `regular`. Câmpurile fizice `machine_id`,
`ball_set_id`, `ball_measurements` sunt nule ⇒ nu se poate condiționa pe mașină/set (declarat).

## 3. Modelul abaterii fizice (exact)

**Marginal (C1):** urnă cu ponderi fizice w_i > 0: P_w(S) = Π_{i∈S} w_i / e_k(w) (Poisson condiționat; e_k = polinomul
simetric elementar, calculat exact prin recurență). Statistica suficientă = numărările c_i; probabilitățile de includere
π_i = w_i e_{k−1}(w_{−i}) / e_k(w); informația pe extragere D(w) = KL(P_w ‖ U) = Σ π_i ln w_i − ln e_k(w) + ln C(n,k).
Bila Joker: multinomial pe 20, D = KL(f ‖ u). **Serial (C2):** suprapunerea o_t = |S_t ∩ S_{t−1}|; modelul înclinat pe
clasele de suprapunere are D = KL(p ‖ h), h = legea hipergeometrică exactă; bila: P(repetare) vs 1/20. **Perechi (C3):**
co-apariții a_ij în aceeași extragere vs T·k(k−1)/(n(n−1)) — test descriptiv (1 176 / 780 / 990 de parametri nu pot fi
mărginiți util de ~2 500 de extrageri). **Deriva (C4):** omogenitatea marginalelor pe K = 4 blocuri consecutive egale.

## 4. Statistici, valori p, frontieră

- C1: X²_M = (n−1)/n · Σ (c_i − Tk/n)² / (T·(k/n)(1−k/n)) (df n−1); bila: Pearson (df 19). C2: Pearson pe clasele
  de suprapunere, cu categoriile de coadă comasate de sus până la așteptare ≥ 5 (df = clase − 1); bila: df 1.
  C3: X²_P = Σ_{i<j} (a_ij − E)²/E. C4: X²_D = Σ_b X²_M(bloc b) − X²_M(total) (df (K−1)(n−1)); bila analog.
- Valori p prin Monte Carlo sub urna perfectă: R = 10 000 istorii uniforme cu același T, semințe 2026102701 (6/49),
  2026102702 (5/40), 2026102703 (Joker); p = (1 + #{X²_sim ≥ X²_obs})/(R + 1). Se raportează și p χ².
- **Frontiera (C1, C2, bila C1/C2):** f = vectorul observat (frecvențe de includere ĉ/T sau legea suprapunerilor),
  u = valoarea nulă, q = χ²_{df; 0.95}. Punctul extrem al regiunii de încredere 95% în direcția abaterii observate:
  f* = u + (f − u)·(1 + √(q / X²_obs)). Pentru C1 se rezolvă EXACT w* cu π(w*) = f* (iterația w_i ← w_i f_i/π_i(w),
  toleranță 1e-13) și se calculează D_max = D(w*) exact; pentru C2/bilă D_max = KL(f* ‖ ·) exact. Se raportează și
  aproximarea locală ½(√X²_obs + √q)²/T și D̂ = D la f (plug-in, deplasat în sus).
- Valoarea în potriviri (C1): biletul oracolului = cele b numere cu π* maxim (b = 6, 5, 5); exces = Σ_top π* − b·k/n
  (și în %); bila: max f*_j − 1/20.
- Extrageri viitoare: N_oracol = ⌈ln(1/α)/D_max⌉ cu α = 0.01, și ⌈ln(100·M)/D_max⌉ cu M = 3 modele; N_învățăcel =
  cel mai mic N cu N·D_max − (df/2)·ln N ≥ ln(100·M) (costul de învățare al unui amestec bayesian, aproximare
  declarată). Ani = N / 104 (două extrageri pe săptămână, declarat).

## 5. Verdicte (praguri fixate acum)

- Pe componentă: `FR_ABATERE_DESCRIPTIVA` dacă p_MC ≤ 0.01/15 (Bonferroni pe 15 teste: 4 + 4 + 4 principal Joker +
  3 bilă), altfel `FR_COMPATIBIL_UNIFORM`. Arhiva e explorată ⇒ orice abatere rămâne DESCRIPTIVĂ, nu predicție.
- Pe familie (C1, C2 per urnă): fezabilitate prospectivă după N_învățăcel(D_max): `FR_FEZABIL` ≤ 520 extrageri
  (5 ani), `FR_LENT` ≤ 2 080 (20 ani), altfel `FR_NEFEZABIL`.
- **Martorul de decizie:** S11 alege ipoteze NUMAI din familiile `FR_FEZABIL`/`FR_LENT`, cu abaterea implantată la
  D_max pentru calibrarea puterii; familiile `FR_NEFEZABIL` sunt excluse (decizie diferită de „testează tot”). Dacă
  toate sunt nefezabile, S11 o spune și propune numai ipoteze cu sursă de informație NOUĂ.

## 6. Martori ÎNAINTE de arhivele reale (toți PASS, altfel `FR_NECALIFICAT`, fără rulare reală)

W1 exactitatea Poisson condiționat: e_k, π, D, eșantionarea exactă vs enumerare completă pe n = 10, k = 3 (5 seturi
w aleatoare): |Δ| ≤ 1e-12; Σπ = k. W2 calibrarea nulă: 400 istorii uniforme (forma 6/49): rata X²_M > q_{0.95} în
[0.02, 0.08]; idem C2. W3 abatere implantată C1 (eșantionare EXACTĂ din P_w): 100 istorii pentru fiecare
D_true ∈ {1e-3, 3e-3}, forma 6/49: acoperire P(D_true ≤ D_max) ≥ 0.90; rezolvarea π → w reproduce w (rel. ≤ 1e-8).
W4 abatere serială implantată (lanț cu suprapuneri din p ≠ h, marginal uniform): 100 istorii, acoperire ≥ 0.90.
W5 determinism: aceeași sămânță ⇒ aceleași numere (două rulări mici identice).

## 7. Verificator SEPARAT `tu4/verifica_fr.py`

Numai biblioteca standard + NumPy (fără SciPy, fără importul `tu4/frontiera.py`). Re-implementează citirea arhivelor,
numărările, X² (C1, C2, C4, bilă), quantilele χ² (gamma regularizată proprie + bisecție), rezolvarea w* (recurență în
spațiul log, algoritm diferit), D_max, excesul, N-urile și verdictele: abatere ≤ 1e-9 relativ. MC independent
(R = 2 000, semințe +500): concordanță |p_v − p| ≤ 4√(p̄(1−p̄)/2000) + 3/2000 pentru toate componentele.
`VERIFICARE_FR_PASS` numai dacă tot trece.

## 8. Fișiere (lista închisă)

Noi: `tu4/PROTOCOL_TU4_FR.md`, `tu4/SIGILIU_TU4_FR.json` (0444); `tu4/frontiera.py`, `tu4/verifica_fr.py`,
`tu4/tests/test_frontiera.py`; `tu4/rezultate/FR/MARTORI_FR.json`, `FR_REZULTATE.json`, `VERIFICARE_FR.json`,
`RAPORT_FR.md`, jurnalele `*.log` (toate rezultatele 0444). Actualizate: `predari/OPERATIV.md`,
`predari/MESAJE_UTILIZATOR_QL649.md` (Mesajul 53 adăugat), perechea de predare prin `genereaza_predare.py`.
Nimic din TU3, pistele închise, produsul vechi sau timerul nu se modifică. Calcul pe CPU (NumPy/SciPy).

## 9. Ce NU face S10

Nu emite predicții, nu alege bilete, nu antrenează modele, nu atinge gardul produsului vechi. Frontiera spune cât de
mare poate fi abaterea și cât ar dura demonstrarea ei; NU spune că abaterea există.
