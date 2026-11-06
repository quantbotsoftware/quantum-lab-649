# AMENDAMENT XI-C1_03 — algoritm nou pentru designul 6/49: construcție greedy pe GPU + reducere țintită (înainte de cod)

Scris și sigilat ÎNAINTE de codul nou `xi/c1/cautare649.py` (nu există la sigilare) și înainte de orice calcul 6/49 din
această sesiune. Autoritate: Mesajul 107, cererea din 2026-10-30 (faza C, rest). Restul `PROTOCOL_XI_C1.md` (§2 condiția
de câștig, §4 verificarea exhaustivă G2 cu `verifica_design.py` NEMODIFICAT, §5 + AMENDAMENT_XI_C1_02 permutarea fără
bilete marcate, §6 evaluarea unică) rămâne neschimbat. `positive_claims_allowed=false`. Calcul clasic (GPU + CPU).

## 1. Motiv (constatat și publicat în `RAPORT_C1_INTERMEDIAR.md` §3)

Căutarea locală v4 pornită din 200 de bilete aleatoare a stagnat la circa 24 000 de extrageri neacoperite (46 min,
~7 iterații/s): un minim local adânc, din care recoacerea nu iese. Problema este punctul de pornire și viteza contorului
(contor int8 pe 14 milioane de extrageri, împachetat/despachetat la fiecare mutare), nu condiția de câștig.

## 2. Algoritmul (fix înainte de rulare)

Reprezentare: aceeași ca în `cautare.py` (universul C(49,6) = 13 983 816 pe biți, indicatorii I[x], acoperirea A3 prin
numărare bit-sliced), importată din `cautare.py` fără modificare. **Nou:** contorul exact c[D] (numărul de bilete cu
≥ 3 nimeriri pe D) este ținut în **8 planuri de biți** (c ≤ 255 > N), cu incrementare/decrementare bit-sliced exactă;
Z0 = (c = 0), Z1 = (c = 1) se obțin direct din planuri, fără despachetare.

**Etapa G (construcție greedy, ≤ 15 min GPU).** Seed 20261030. Cât timp există extrageri neacoperite: R = 8 porniri
(4 extrageri neacoperite alese aleator, luate ca bilete, + 4 bilete aleatoare); fiecare pornire urcă local (cel mult
15 pași) spre vecinul cu un număr schimbat care maximizează câștigul exact `|A3(t) ∩ Z0|` (toți cei 6·43 = 258 de vecini
evaluați exact); se adaugă biletul final cu cel mai mare câștig. Designul rezultat (zero neacoperite) se scrie `SG<N>`.

**Etapa R (reducere, restul bugetului, ≤ 110 min GPU).** Cât timp f = 0: se scrie `SR<N>` (la primul pas, același cu
`SG<N>`, nu se dublează), se elimină biletul cu cea mai mică acoperire unică `|A3(t) ∩ Z1|`. Apoi recoacere până la
f = 0: cu probabilitatea 0.7 mutare țintită (o extragere neacoperită aleatoare; un bilet cu ≥ 2 numere în ea; numai
vecinii care o acoperă), altfel un bilet aleator cu toți vecinii; alegere baie termică softmax(−Δ/T) cu opțiunea „rămâi”;
T0 = 2, răcire ×0.9995, minim 0.05, reîncălzire după 4 000 de pași fără record (ca v4). Oprirea unui nivel N: buget
total epuizat. Fără alte reglaje în timpul rulării; dacă rularea se oprește cu eroare tehnică, se publică și se poate
relua o dată, cu aceiași parametri, din ultimul design `SR`/`SG` scris (incident `XI_C1_NN`).

**Controale de exactitate (obligatorii, în cod):** (a) la fiecare mutare `f_nou = f + Δ` (aserțiune); (b) la fiecare
2 000 de mutări și la fiecare design scris, contorul pe planuri este recalculat de la zero și trebuie să fie identic;
(c) un martor la pornire: un singur bilet {1..6} dă f = 13 723 192 (= M3 din AMENDAMENT_XI_C1_01).

## 3. După căutare

1. Cel mai mic design 6/49 scris trece verificarea exhaustivă §4 (`verifica_design.py`, CPU, independent). Numai
   designurile cu G2 PASS intră în rezultate. Referința publicată 163 rămâne **nereprodusă** dacă nu este atinsă;
   nu se promite atingerea ei. Optimalitatea nu se afirmă.
2. Permutarea Q (§5 + AMENDAMENT_XI_C1_02: zero bilete marcate `patterned`) pe cel mai mic design verificat, apoi
   re-verificare §4 a designului `…Q`.
3. Evaluarea §6: întâi test pe uscat al `c1_evaluare.py` pe o copie în scratch (M mic, ieșire în scratch; nu contează
   ca producție), apoi producția unică cu `--joker JS135Q.json [--649 <…Q.json>]`.

## 4. Igienă (din INCIDENT_S35_02)

Toate rulările care importă `quantum_limit` (permutarea, evaluarea) se fac cu `-B` și `PYTHONDONTWRITEBYTECODE=1`;
înainte și după, scanarea manifestului DL trebuie să dea exact cele 6 registre LIVE6. GPU cedat la ±15 min de emisiile
06:20/10:20/13:20Z și în fereastra C1 de duminică.
