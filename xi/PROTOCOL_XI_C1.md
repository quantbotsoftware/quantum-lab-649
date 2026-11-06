# PROTOCOL XI-C1 — designuri cu câștig garantat, permutarea anti-mulțime și evaluarea în simulator (V11, faza C)

Scris și sigilat ÎNAINTE de codul C1 (`xi/c1/` nu există la sigilare). Autoritate: Mesajul 107 (autonomie 100%) și
cererea din 2026-10-30 00:48 EET. Plan: `xi/PLAN_V11_QL_XI.md` (`2fb304f4…`), componenta C1, poarta G2.
`positive_claims_allowed=false`. Calcul clasic (CPU + GPU). Un design garantează un câștig la categoria cea mai mică;
**nu** crește șansa vreunui bilet și **nu** face jocul profitabil. Fără subagenți, timere sau joburi autonome.

## 1. Întrebările

1. Care este cel mai mic număr de bilete, construit și verificat exhaustiv de noi, care garantează cel puțin un premiu
   la fiecare extragere posibilă: (a) Joker, (b) 6/49 (cel puțin 3 nimeriri, categoria IV)?
2. Cât valorează designul după permutarea anti-mulțime (aceeași garanție, EV mai mare după modelul Quantum Limit)?
3. Ce înseamnă economic designul jucat la fiecare dată (simulatorul C4, plăți reale, partajare exactă)?
4. 5/40, categoria III: cât costă minimum, după o limită demonstrabilă?

## 2. Condițiile exacte de câștig

- **Joker** (5 din 45 + Joker 1 din 20). Biletul (s, j) câștigă la extragerea (D, J) dacă `|s∩D| ≥ 1` și `j = J`
  (categoriile VIII, VII, V, III, I) sau dacă `|s∩D| ≥ 3` (VI, IV, II fără Joker; cu Joker V, III, I).
  Spațiul: C(45,5)·20 = **24 435 180** de extrageri.
- **6/49**: biletul s câștigă cel puțin categoria IV dacă `|s∩D| ≥ 3`. Spațiul: C(49,6) = **13 983 816**.
- **5/40** (bilet de 5, extragere de 6): categoria III sau mai bine ⇔ `|s∩D| ≥ 4`. Spațiul: C(40,6) = 3 838 380.

## 3. Designurile

**J180 (referința planului):** blocurile `B_i = {5i−4,…,5i}`, i = 1..9; biletele (B_i, j) pentru toți i, j.
Garanție: pentru Joker-ul extras J, cele 9 bilete cu Joker J partiționează 1..45, deci unul are ≥ 1 nimerire.

**J140 (construcție proprie, observată la redactarea acestui protocol):** afirmația planului „180 optim exact” nu este
demonstrată. Pentru fiecare J, se exclude perechea de blocuri `P_J` = a J-a pereche {a<b} din ordinea lexicografică
a celor 36 de perechi din 1..9; biletele cu Joker J sunt cele 7 blocuri rămase. Argumentul: o extragere (D, J) fără
nimerire pe biletele cu Joker J are D ⊆ B_a ∪ B_b, deci |D∩B_a| ≥ 3 sau |D∩B_b| ≥ 3; blocul respectiv apare ca bilet
la un alt Joker (fiecare bloc este exclus la cel mult 8 din 20 de Jokeri), deci câștigă VI sau mai bine. 20·7 = 140.
Este raționament standard de lotto-design; nu revendicăm noutate mondială.

**JS / SS (căutare):** căutare locală pe GPU (recoacere simulată pe mutări „înlocuiește un bilet”) care minimizează
numărul de extrageri necâștigătoare, cu actualizare incrementală exactă a contorului de acoperire pe toate extragerile.
Pornire: Joker din J140 minus un bilet; 6/49 din bilete aleatoare (seed 20261030) la N = 200, apoi N scade cu 1 după
fiecare design găsit cu zero extrageri necâștigătoare. Buget în faza C: **≤ 60 min GPU Joker, ≤ 180 min GPU 6/49**
(restul în faza G). Explorare, nu producție: se publică jurnalele și designurile, dar intră în rezultate numai designurile
care trec verificarea §4. Referința 6/49 cunoscută: **163** de bilete (nereprodusă aici dacă nu este găsită); minimul
este deschis. Nu se promite atingerea sau depășirea ei.

**5/40:** numai limita inferioară demonstrabilă (fiecare bilet acoperă C(5,4)·C(35,2) + C(35,1) = 3 010 extrageri,
deci N ≥ ⌈3 838 380 / 3 010⌉ = 1 276 bilete = 6 380 lei/extragere) și concluzia economică; construcția trece în faza G.

**Limita inferioară Joker și 6/49:** se raportează numai ce este demonstrat riguros (cu argumentul scris); altfel
„deschis”. Optimalitatea nu se afirmă fără demonstrație.

## 4. Verificarea exhaustivă (poarta G2)

Verificator SEPARAT `xi/c1/verifica_design.py` (CPU, numpy, cod independent de căutare): enumeră toate extragerile
(§2), calculează exact numărul de nimeriri pe măști de biți și raportează: numărul de extrageri necâștigătoare (trebuie
0), distribuția celei mai bune categorii pe extragere, numărul de bilete distincte și formatul (numere 1..n distincte,
Joker 1..20). **G2 PASS ⇔ 0 extrageri necâștigătoare** pe tot spațiul. Martori negativi obligatorii: J180 minus un
bilet și J140 minus un bilet trebuie să dea > 0 extrageri necâștigătoare (altfel verificatorul este invalid).
Pentru fiecare design publicat: fișier JSON (0444) cu biletele și sha256, plus raportul verificatorului.

## 5. Permutarea anti-mulțime

Garanția este invariantă la orice permutare a numerelor 1..n (și, la Joker, la orice permutare a valorilor Joker).
Tabelul EV: `quantum_limit.ceiling.ev_all_tickets(model, state)` pe baza curentă (`crowd_model`, `market_state`,
read-only, sha256 înregistrat). Obiectivul: `Σ_t EV(π(t))` (EV individual al biletelor; partajarea între propriile
bilete este ignorată aici și tratată exact în §6). Metoda: recoacere pe transpoziții de numere; la Joker, pentru π fix,
permutarea Jokerilor este optimă exact prin problema de asignare 20×20. Comparatori: eticheta identică și 1 000 de
permutări aleatoare (seed 20261030; media, cuantilele 5/50/95%). Ieșire: câștigul EV în lei/extragere și în % din cost.
Designul permutat se re-verifică exhaustiv (§4). EV este cel al modelului mulțimii, nu un avantaj demonstrat.

## 6. Evaluarea în simulator (o singură rulare de producție)

Script nou `xi/c1/c1_evaluare.py`, reutilizând din `xi/c4_simulator.py` (importat, nemodificat) probabilitățile
exacte și metoda pe măști (AMENDAMENT_XI_C4_01). Fereastra principală: aceleași ultime 312 date comune; extragere
uniformă reală la fiecare dată; plăți brute din istoric cu **partajare exactă**: dacă k bilete ale noastre câștigă
categoria c, unde existau w câștigători, plata noastră totală este `k·ppw·w/(w+k)` (fond partajat); la `rollover`
(w = 0), totalul nostru este `carryover` (indiferent de k); 6/49 IV fix: `k·ppw`; alte stări: 0 (conservator).
Strategii: **D_joker** (cel mai mic design Joker verificat, permutat), **D_649** (cel mai mic design 6/49 verificat,
permutat, dacă există), **D_ambele**. M = 10⁶ sezoane × 1 040 de date, seed 20261030, orizonturi 1/5/10 ani.
Ieșiri: costul pe dată, P(net ≥ 0), mediana și cuantilele netului, randamentul mediu, plata minimă observată pe dată.
Porți: **E1** în nicio dată simulată nu lipsește premiul (consecința G2); **E2** numărul mediu de bilete câștigătoare pe
categorie și dată, simulat, în ±4 SE față de valoarea exactă N·p_c; **E3** probabilitățile exacte trec verificarea V2
din C4. Dacă o poartă pică, cifrele nu se publică drept rezultat (incident XI_C1_NN, corectură tehnică fără reglaje).
Fișiere: `xi/rezultate/C1/C1_EVALUARE.json` (0444), `RAPORT_C1.md`.

## 7. Reguli

Rezultatele, inclusiv negative, se publică și nu se rescriu. Erorile tehnice → incidente `XI_C1_NN`. Resursele
GPU/CPU se folosesc la maxim, dar se cedează la ±15 min de emisiile 06:20/10:20/13:20Z și în fereastra C1 de duminică.
Garanția nu schimbă semnul valorii așteptate; nicio afirmație de profit.
