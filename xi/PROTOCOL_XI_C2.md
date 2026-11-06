# PROTOCOL XI-C2 — backtestul unic al ferestrelor EV+ și reconcilierea ρ_C4 ↔ Quantum Limit (planul V11, faza D)

Scris și sigilat ÎNAINTE de orice cod C2 și de orice calcul pe extragerile țintă. Autoritate: Mesajele 107/110 și cererea
din 2026-10-30 (faza D). `positive_claims_allowed=false`. C2 NU este un predictor de numere: biletele se aleg după
valoarea așteptată (împărțirea premiilor), iar șansa de câștig a oricărui bilet rămâne cea uniformă. Calcul clasic
(CPU + GPU prin `quantum_limit`, neschimbat). Inventarul făcut înainte de protocol (număr de extrageri, reporturi maxime,
sha bazei, valorile sigilate ale produsului) nu este experiment de selecție.

## 1. Întrebările

**C2a (backtest).** Pentru fiecare extragere regulată istorică d (6/49, 5/40, Joker, din 2010-05-02), folosind NUMAI
informația disponibilă înainte de d, ar fi semnalat regula V11 „joacă numai când marginea inferioară (cuantila 5%) a
valorii așteptate a biletului optim depășește prețul” o fereastră EV+? De câte ori, când și ce ar fi adus jocul doar
atunci (valoare așteptată ex-ante și rezultat realizat)? Răspunsul „de zero ori” este un rezultat valid și se publică.

**C2b (reconciliere).** De ce randamentul biletului uniform din C4 (ρ_C4 = 37.5% la 6/49, fereastra de 312 date) diferă
de „biletul mediu 3.61 lei (45%)” al Quantum Limit (sigiliul `prospectiv/649/2026-10-22/sigiliu_20261019T002028Z.json`,
3.607076187360041 lei)? Descompunere cantitativă pe efecte (stare/moment, model ex-ante vs plăți realizate, pe categorii).

## 2. Date (fixate)

- Baza: `${LOTO_RO_ROOT:-.}/loto_romania/data/snapshots/c6bfd021af15d9d6ece6b20d106550e4c8474049e38e9caa3bd1c99d19766adb/loto_romania.sqlite`,
  sha256 `9942abfc25282a715cba70e4f6d17a885a467eaf5fe0440838dc28114003c078` (aceeași ca C4 și ca sigiliile din 29 oct.).
  Calea se fixează explicit (nu `CURRENT.json`, care se poate schimba prin colectorul utilizatorului). Codul verifică sha-ul
  la pornire și refuză altă bază.
- Ținte: extragerile `regular` cu dată ≥ 2010-05-02, în ordinea `load_draws` (dată, cheie).
- Intrări ex-ante pentru ținta d de la poziția i: `draws[:i]` (toate tipurile, ca produsul), adică strict înainte de d.
- Prețuri curente pentru toată istoria (6/49 8 lei, 5/40 5 lei, Joker 7 lei), ca produsul și C4. Limită declarată: dacă
  prețurile istorice au fost altele, raportul EV/preț din anii vechi este deplasat; de aceea se publică și distribuția
  completă a raportului EV_max/preț (nu doar pragul).

## 3. Starea ex-ante și modelul mulțimii (fidele produsului)

- Funcțiile produsului, neschimbate: `ceiling.market_state(game, draws[:i], model)`, `ceiling.ev_all_tickets`,
  `ceiling.patterned`, `crowd.fit`, `joker.estimate_pi`, `data.observed_counts`, `data.time_weights`.
- Modelul 6/49 se reestimează în blocuri de 13 ținte 6/49 consecutive (≈ 6,5 săptămâni). Pentru blocul b, cu data de
  start t_b (data primei ținte a blocului), modelul se estimează exact ca `models.crowd_model('649')`, dar numai pe
  extragerile 6/49 observate cu dată < t_b (`observed_counts(..., end=t_b)`), cu ponderi de timp relative la cea mai
  nouă dată din acel set, ridge 1.0. Aproximarea față de produs (care reestimează la fiecare rulare) este declarată.
- 5/40: transferul produsului (β restrâns la 1..40, θ_c, θ_L) din modelul 6/49 al blocului cu cel mai mare t_b ≤ data(d).
- Joker: decizia publicată a produsului (`validare_joker.json`: numere „B” = transfer de la 6/49, Joker „pi”): numere din
  modelul 6/49 al blocului cu t_b ≤ data(d); π = `estimate_pi` pe extragerile Joker observate din `draws[:i]`.
- Rodaj: o țintă se evaluează numai dacă modelul ei are ≥ 52 de extrageri 6/49 observate și jocul are ≥ 52 de extrageri
  observate în `draws[:i]`; altfel se numără ca „neevaluată (rodaj)”. Orice excepție a produsului se numără, nu se ascunde.
- Data țintă a produsului (`next_draw`) poate diferi de data(d) când intervin extrageri speciale; se păstrează logica
  produsului („ce ar fi arătat Quantum Limit în ajun”) și se raportează numărul nepotrivirilor.

## 4. Ieșiri pe țintă (etapa 1, toate țintele evaluate)

EV_max = valoarea așteptată a biletului-limită (cel mai bun bilet fără tipar, `limit` al produsului) și biletul însuși;
EV_max_nerestricționat; EV_avg (biletul mediu) și componentele medii pe categorii; componentele biletului-limită;
fondurile, reportul, vânzările prognozate și σ² al modelului de vânzări; valoarea realizată (§6).

## 5. Regula ferestrei (etapa 2)

- **Semnalare:** EV_max(d) > preț.
- **Fereastră EV+:** pentru țintele semnalate, B = 40 de replici bootstrap (ca `incertitudine.py`): replica r a blocului b
  reestimează modelul 6/49 pe o reeșantionare cu întoarcere a extragerilor 6/49 observate cu dată < t_b (ponderile
  reindexate ca în `_resample_fit`), seed `20261030 + 1000·b + r`, replica fiind comună tuturor țintelor blocului;
  la Joker π se reestimează pe o reeșantionare a extragerilor Joker din `draws[:i]`; vânzările se înmulțesc cu
  exp(σ·z − σ²/2), z ~ N(0,1) cu seed `20261030 + 7919·i + r + 100000·cod_joc` (cod 649=1, 540=2, joker=3). Se recalculează
  EV-ul exact al tuturor biletelor și se reține EV-ul **biletului-limită punctual** în fiecare replică.
  q5 = `np.percentile(valori, 5)` (interpolare liniară, ca produsul). **Fereastră dacă q5 > preț** (strict, „depășește”).
- Limită declarată: o țintă cu EV_max ≤ preț nu intră în etapa 2 (q5 ≈ sub mediană). B = 40 < 200 al produsului (cost);
  cuantila are deci eroare Monte Carlo mai mare, declarată.

## 6. Plata realizată (regulile C4 §4, identice)

Pentru categoria c a țintei d: `paid` → payout · w/(w+1) (categoriile fixe, 6/49 IV: payout); `rollover` → carryover;
altfel 0 (numărat). Sume brute, fără impozit. Categoriile biletului: 6/49 după nimeriri (6/5/4/3 → I/II/III/IV);
5/40: I dacă biletul = primele 5 bile din `order`, II dacă biletul ⊂ cele 6 bile altfel, III dacă exact 4 nimeriri;
Joker: (5,J) I, (5) II, (4,J) III, (4) IV, (3,J) V, (3) VI, (2,J) VII, (1,J) VIII.
Valoarea realizată a biletului uniform: R_u(d) = Σ_c P_c · v_c(d) (P_c exacte, ca în C4).

## 7. Ieșiri economice (C2a)

Pe joc: ținte evaluate/neevaluate; semnalate; ferestre (date, EV_max, q5, bilet); distribuția EV_max/preț (max, top 10,
cuantile 50/90/99%). Strategia „fereastră” (1 bilet-limită la fiecare fereastră): miză, Σ EV ex-ante, plată realizată,
premii prinse, Σ R_u(d) la acele date. Strategia „biletul-limită la fiecare țintă”: miză, Σ EV_max/miză, plată realizată/
miză, comparată cu Σ R_u/miză. Pentru ferestre: fracția Kelly aproximativă f* ≈ E[R]/E[R²], R = X/preț − 1, cu
E[X²] ≈ Σ_c comp_c²/P_c (aproximare de ordinul 2 cu cota deterministă, declarată) și bancul minim = preț/f*.

## 8. Reconcilierea (C2b), 6/49 principal, 5/40 și Joker descriptiv

W312 = ultimele 312 date comune ale C4 (aceeași construcție ca `c4_simulator.load_payouts`). Se raportează:
ρ_snap = 3.607076187360041/8; ρ_QL(2026-10-22) din backtest; ρ_QL,W = media EV_avg(d)/preț pe W312;
ρ_C4 = media R_u(d)/preț pe W312; diferențele: Δ_cadență = ρ_snap − ρ_QL(2026-10-22), Δ_moment = ρ_QL(2026-10-22) − ρ_QL,W,
Δ_model = ρ_QL,W − ρ_C4, cu Δ_model descompus pe categorii (media componentei ex-ante − media P_c·v_c(d)); pentru
categoria I se dă și P_I·A_I ex-ante (fără împărțire). Descompunerea este exactă aritmetic (suma Δ = ρ_snap − ρ_C4).

## 9. Porți de corectitudine (înainte de publicarea cifrelor)

- **K1** (replicarea C4): ρ_C4 recalculat pe W312 egal cu `C4_REZULTATE.json` (`rho_window`) la |Δ| ≤ 1e-12 pentru toate
  cele 3 jocuri.
- **K2** (fidelitate față de produs): starea finală (toate extragerile până la 2026-10-29, model reestimat pe tot) reproduce
  sigiliile `prospectiv/*/2026-11-01/sigiliu_20261029T2140*Z.json`: EV_avg și EV-ul limitei cu eroare relativă ≤ 1e-9 și
  același bilet-limită, la toate cele 3 jocuri. Rulat ÎNAINTE de producție (nu folosește ținte istorice).
- **K3** (fără privire în viitor): pentru fiecare țintă, data maximă a intrărilor stării < data(d) sau poziție < i, iar
  datele modelului < t_b ≤ data(d); zero încălcări (verificate în cod la fiecare țintă).
- **K4** (plata realizată): teste sintetice ale regulilor §6 (toate categoriile, regula „primele 5”, Joker potrivit/nu),
  rulate ÎNAINTE de producție.
- **K5** (bootstrap): replica-identitate (fără reeșantionare, fără zgomot) reproduce EV-ul punctual al limitei la ≤ 1e-9,
  verificată o dată pe fiecare bloc cu ținte semnalate.

Dacă K1–K5 pică, cifrele economice nu se publică drept rezultat; se declară incident și se corectează tehnic, fără
ajustări după rezultat.

## 10. Rulare

- Cod: `xi/c2/backtest_c2.py` (etapele 1, 2 și raportul) — scris după sigilarea acestui protocol. Python `/usr/bin/python3 -B`
  cu `PYTHONDONTWRITEBYTECODE=1` (igienă INCIDENT_S35_02); DL v2 se reverifică la sfârșit.
- **O singură producție.** Ieșirile pe țintă se scriu incremental (JSONL), astfel încât o întrerupere tehnică se reia de la
  ultima țintă terminată (fiecare țintă se calculează o singură dată, determinist; reluarea nu este o rerulare).
  Procesele 6/49 și Joker folosesc GPU, 5/40 procesorul (decizia G2 a produsului). Procesele cedează placa video/procesorul
  (pauză internă, fără timere de sistem) în ±15 min de 06:20, 10:20, 13:20 și 21:40 UTC (emisii/prospectivul produsului).
- Ieșiri: `xi/rezultate/C2/` — `etapa1_<joc>.jsonl`, `etapa2_<joc>.jsonl`, `C2_REZULTATE.json`, `RAPORT_C2.md` (0444 la final).

## 11. Interpretări fixate acum

- 0 ferestre la un joc ⇒ „regula C2 nu ar fi jucat niciodată la acest joc în istorie (în ipotezele produsului)”.
- ≥ 1 fereastră ⇒ se raportează valoarea ex-ante și rezultatul realizat; rezultatul realizat al câtorva bilete este zgomot
  (șansa la orice premiu ≈ 1/54 la 6/49) și NU dovedește profit sau pierdere; nicio afirmație pozitivă.
- Reconcilierea se raportează ca descompunere; nu se „alege” o valoare corectă după rezultat. Ambele cifre rămân definite
  (moment fix vs medie pe fereastră; model ex-ante vs plăți realizate).
