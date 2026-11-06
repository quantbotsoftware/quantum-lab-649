# PROTOCOL TU4-IP — sesiunea S11 „IP”: 3 ipoteze fizice, calificare EXCLUSIV pe date sintetice

Stare: scris și sigilat (`tu4/SIGILIU_TU4_IP.json`, împreună cu cele 3 protocoale de ipoteză) ÎNAINTE de orice cod
S11 al ipotezelor și ÎNAINTE de orice calcul al lor. Plan: `tu4/PLAN_SESIUNI_TU4_v2_20261027.md` (`32533d53…`) §2 S11.
Amendament precedent: `tu4/AMENDAMENT_TU4_FR_01.md` (sigiliu `45bbcd04…`, 21:11:31Z), reclasificare publicată
`tu4/rezultate/FR/RECLASIFICARE_FR01.json` (`fe5c8a8d…`): C1 6/49 153, 5/40 206, Joker 136, B1 357 extrageri ⇒
`FR_FEZABIL`; C2 ×3 `FR_LENT`; B2 `FR_NEFEZABIL`. Autoritate: Mesajele 52–54. `positive_claims_allowed=false`.
Documente: acest fișier (partea comună) + `PROTOCOL_TU4_IP_H1_MA.md`, `PROTOCOL_TU4_IP_H2_UZ.md`,
`PROTOCOL_TU4_IP_H3_AD.md` (fiecare ipoteză are protocolul ei, cu hash separat în sigiliu).

## 0. Mesajul 54, cum se aplică (decizii ale agentului, delegate)

- **Amendamentul ÎNTÂI:** făcut (vezi antet). Verdictul S10 sigilat rămâne oficial; reclasificarea stă ALĂTURI.
- **3 ipoteze EXCLUSIV fizice:** H1 „MA” asimetrie de masă staționară; H2 „UZ” micro-uzură (derivă lentă continuă);
  H3 „AD” dinamica aerului (amestec incomplet ⇒ memorie netedă a geometriei de încărcare). Toate trei sunt în familia
  marginală (C1/B1), singura `FR_FEZABIL` după amendament. Familiile seriale (`FR_LENT`) nu se folosesc: ar fi
  memorie între extrageri, deja închisă de numeroase piste (vezi §1).
- **`torch.compile(mode="max-autotune-no-break")`:** acest mod NU există în PyTorch 2.11 instalat (lista oficială
  `torch._inductor.list_mode_options()`: `default`, `lite`, `reduce-overhead`, `max-autotune-no-cudagraphs`,
  `max-autotune`). Se folosește cel mai apropiat mod valid: `mode="max-autotune-no-cudagraphs", fullgraph=True`
  (fără întreruperi de graf permise), pe nucleul factorului e (§3). Dacă compilarea eșuează, rularea continuă eager,
  iar eșecul se publică (`compile_status`); rezultatele nu depind de compilare (testul T6 compară compilat ≡ eager).
- **`torch.complex64`, LQG (rețele de spin), CFT/WZW:** NU se folosesc. Legile urnei sunt probabilități reale; o
  reprezentare complexă nu adaugă informație, iar formalismul LQG/WZW a fost testat și închis (PL649 0/6, p 0.948;
  protocol FR §0). Se lucrează în `float64` (S10 a prins un defect float32; log E cere sume precise).
- **`torch.channels_last`:** este un format de memorie definit numai pentru tensori 4D NCHW (imagini); tensorii de
  aici sunt 1D–3D, deci formatul nu este aplicabil (PyTorch l-ar refuza). Declarat, nu simulat.
- **Zero popularitate:** niciun cod, nicio intrare despre biletele altor jucători. Singura intrare a modelelor sunt
  extragerile (aici: SINTETICE).
- **SSD + `numpy.memmap`:** SSD-ul extern (`/dev/sda1`, ext4, eticheta `LOTO_SSD`, 1.8 TB) nu era montat; montat de
  agent cu `udisksctl mount -b /dev/sda1 --no-user-interaction` la 21:08Z în `./ssd_data`. Datele
  sintetice se scriu în `./ssd_data/QL649_S11/` ca `numpy.memmap`, de un fir de scriere asincron în timp ce
  GPU generează bucata următoare. „Intensitate γ = 1” = toate celulele la volumul complet (§4), fără eșantionare redusă.
- **Linger:** `Linger=yes` (verificat la primul pas). **Gardul:** decizia S10 rămâne (gardul produsului vechi conține
  `popularitate-v1`, deci rămâne neatins; emisia automată se aplică tribunalului TU4 în S12).
- **GPU:** RTX 5060 Laptop (sm_120), PyTorch 2.11+cu128, Triton 3.6. Calcul CLASIC în virgulă mobilă; fără hardware
  cuantic, avantaj cuantic sau noutate mondială. Fără subagenți. Git numai `./dev-git`, fără add/commit.
- **Arhiva reală NU se citește în S11** (nici extragerile, nici numărările). Singurele valori preluate din S10 sunt
  T și D_max publicate în `FR_REZULTATE.json`. Niciun model nu este ales după arhivă.

## 1. Verificarea familiilor închise (AGENTS.md + pistele QL649/TU3)

| Familie închisă | Ce folosea | Relația cu H1/H2/H3 |
|---|---|---|
| WU649 (Luce, propensiune constantă, MAP N(0,0.2²); `WU_NOT_QUALIFIED`, nerulat) și comparatorul B (c+1) | marginal staționar | H1 are ACEEAȘI sursă de informație (marginal staționar). Diferă legea (Fisher/Poisson condiționat), estimatorul (contracție James–Stein pozitivă, adaptivă) și judecata (prospectivă). Biletul top al lui H1 = ordinea numărărilor (ca B); diferența este MĂRIMEA pariului (§H1). Nu reutilizează cod sau parametri WU. Declarat: H1 nu este sursă nouă de informație. |
| BO649 (rupturi discrete) și comparatorul R (fereastră exp., înjumătățire 26, fără contracție) | recență | H2: derivă CONTINUĂ, fără regimuri/rupturi; înjumătățire 312 fixată din prior fizic; contracție JS. Suprapunere declarată: informația de recență. |
| GL649 (glifele cifrelor) | structura etichetelor prin cifre | H3 folosește ordinea etichetelor (poziția de încărcare), nu cifrele. |
| SC (legea sumei), MC (compoziția 1..24, tranziții) | aritmetica etichetelor | H3 este o înclinare marginală netedă în etichetă; o înclinare liniară mută media sumei (suprapunere parțială declarată cu SC/MC); H3 nu modelează legea sumei, nici tranziții. |
| D (dependențe în aceeași extragere), XJ (inter-joc) | perechi / cuplaj între jocuri | Niciuna: toate legile sunt de formă produs Fisher; jocurile sunt separate; la Joker, urna principală și bila sunt independente. |
| SE, N1 (calendar), CS (seturi multiple), memoria serială (M1/C2, TI, TP, DC, OC, N2, EX, energia, AT, CR…) | calendar, rotații, tranziții, vârste, excursii | Niciuna nu este folosită; H2 folosește ordinea numai prin discount exponențial neted al numărărilor marginale. |
| PL649 (LQG/SU(3)), DL și pistele R/A/B/C/D | transformări matematice | Nu se importă, nu se rulează. |

Fără redenumiri, fără HMM/restart/solver/adaptor/generator. H1 este declarat explicit drept SUPRAPUS informațional cu
WU/B (planul §2 S11 îl cere: „abatere fizică staționară cu contracție bayesiană optimă … nu frecvența brută B”).

## 2. Legea urnei și jocurile (comune)

- Jocuri: 6/49 (n 49, k 6, bilet b 6, T 2595); 5/40 (n 40, k 6 extrase, bilet b 5, T 2490); Joker (urna principală
  n 45, k 5, b 5, T 2202; bila q 20). T = lungimile arhivelor din S10 (warm start SINTETIC de aceeași lungime).
- Legea fizică: Fisher necentrală / Poisson condiționat P_w(S) = Π_{i∈S} w_i / e_k(w); bila: w_j / Σ w. Informația
  D(w) = Σ_i π_i ln w_i − ln e_k(w) + ln C(n, k), π_i = w_i e_{k−1}(w_{−i}) / e_k(w) (exact, ca în S10).
- Ținte D (din `FR_REZULTATE.json`): 6/49 0.04642096912015248; 5/40 0.035248076774104575; Joker principal
  0.0517260340859611; bila 0.019984140068430675.
- Eșantionare EXACTĂ din P_w: parcurgere secvențială i = 1..n cu tabelele sufix E[i, r] = e_r(w_i..w_n),
  P(i inclus | r locuri) = w_i E[i+1, r−1] / E[i, r] (aceeași construcție ca `frontiera.sample_cp`, reimplementată).

## 3. Predicția și e-procesul (comune celor 3 modele)

- Un model emite, ÎNAINTE de extragerea t, ponderi ŵ_t calculate NUMAI din extragerile < t: ln ŵ_t = λ_t · θ_t
  (λ_t ∈ [0, 1] factorul de contracție, θ_t direcția estimată, specifice ipotezei). Legea emisă q_t = P_{ŵ_t} este
  VALIDĂ (normalizată exact prin e_k) pentru orice ŵ_t > 0. Biletul top = cele b etichete cu ŵ maxim (egalitate ⇒
  eticheta mai mică); bila top = argmax ŵ^B.
- Factorul e: ln e_t = Σ_{i∈S_t} ln ŵ_{t,i} − ln e_k(ŵ_t) + ln C(n, k); la Joker se adaugă ln ŵ^B_{t,J} − ln Σ ŵ^B_t
  + ln 20. ln E_t = Σ_{s≤t} ln e_s. Sub urna perfectă E_t este martingală nenegativă (Ville): P(sup E_t ≥ 900) ≤ 1/900.
- Statistici comune: p = k/n; pentru numărările c (din N extrageri) θ̂_i = (n−1)/n · (c_i/N − p)/(p(1−p)) (estimarea
  locală a ln w: dπ/dε = p(1−p)·n/(n−1)·v pentru ln w = εv, Σv = 0) și X² = (n−1)/n · Σ (c_i − Np)² / (N p(1−p))
  (statistica S10, df n−1). Pentru bilă (k = 1) aceleași formule cu n = 20.
- Orizont prospectiv H = 520 extrageri (5 ani, marginea `FR_FEZABIL`). Prag ln 900 (M_max = 9 = 3 ipoteze × 3 jocuri;
  pragul tribunalului 100·M cu M ≤ 9 este cel mult acesta). Succes = max_{t≤H} ln E_t ≥ ln 900.

## 4. Lumile sintetice (calificare EXCLUSIV pe sintetic)

Pentru fiecare joc: celula nulă U (urnă perfectă) și celulele alternative A1, A2, A3 (abaterea implantată de tipul
H1, H2, H3, la D țintă, §2), fiecare cu R = 1000 lumi independente. O lume = T extrageri de „arhivă” sintetică +
H = 520 extrageri viitoare. În FIECARE lume rulează toate cele 3 modele (matrice încrucișată). La Joker, urna
principală și bila primesc implanturi de același tip, independente, cu țintele lor. Semințe (generator CUDA Philox):
2026102711 + 100·g + c, g = 0 (6/49), 1 (5/40), 2 (Joker); c = 0 (U), 1 (A1), 2 (A2), 3 (A3). Implanturile exacte
sunt definite în protocoalele ipotezelor. Indicatoarele (uint8, R × (T+H) × n) și ln w implantate (float64) se scriu
pe SSD (memmap) și se păstrează pentru verificator, cu sha256 în manifest.

## 5. Porțile de calificare (praguri fixate acum), pentru fiecare pereche (ipoteză H_k, joc)

- **Q1 putere:** succesele modelului k în A_k; limita inferioară Clopper–Pearson unilaterală 95% ≥ 0.80.
- **Q2 fals-pozitive:** succesele modelului k în U; limita superioară Clopper–Pearson unilaterală 95% ≤ α = 0.01.
- **Q3 martor de informație:** (a) în A_k, media ln E_H a modelului k este STRICT mai mare decât a fiecăruia dintre
  celelalte două modele și > 0; (b) fixtura de informație I_k din protocolul ipotezei trece.
- **Q4 martor de decizie:** fixtura F_k din protocolul ipotezei trece.
- **Q5 exactitate (comună):** T1 Σ_S q(S) = 1 prin enumerare completă (n 12, k 4) pentru fiecare model pe 5 stări
  aleatoare, |Δ| ≤ 1e-12, și ln e_k prin recurență = enumerare; T2 eșantionatorul: n 8, k 3, w fixat, 200 000 extrageri
  vs probabilitățile exacte: χ² cu p > 0.001; T3 D(w) exact = enumerare (|Δ| ≤ 1e-12); T4 predictibilitate: schimbarea
  extragerii t nu schimbă q_t (|Δ| = 0) și schimbă q_{t+1}; T5 bila: aceleași pentru k = 1.
- **Q6 determinism (comun):** T6 nucleul compilat ≡ eager (|Δ ln e| ≤ 1e-9); T7 două generări ale unei celule mici
  cu aceeași sămânță sunt byte-identice, iar două rulări ale modelelor dau aceleași ln E.
- Model CALIFICAT pentru jocul respectiv ⇔ Q1–Q6 toate PASS. Numai modelele calificate intră în tribunal (S12).
  Fără calificare ⇒ nu intră; nu se reglează nimic după rezultat (fără alt H, alt prag, alt ρ, alt K, alt R).

## 6. Ordinea de execuție

1. Teste unitare `tu4/tests/test_ip.py` (T1–T7 în formă rapidă) — orice defect se repară ÎNAINTE de martori și se
   declară. 2. `MARTORI_IP.json`: Q5, Q6, fixturile F1–F3 și I1–I3 (fără lumi mari). Dacă Q5 sau Q6 eșuează ⇒
   `IP_NECALIFICAT_TEHNIC`, fără rularea mare. 3. Rularea UNICĂ de calificare (`CALIFICARE_IP.json` + per-lume
   `PER_LUME_IP.npz`). 4. Verificator SEPARAT. 5. Raport.

## 7. Verificator SEPARAT `tu4/verifica_ip.py`

Numai biblioteca standard + NumPy (fără torch, SciPy sau import din codul S11). Recitește memmap-urile de pe SSD:
V1 fiecare extragere are exact k unități (toate celulele, toate lumile); V2 D implantat recalculat (A1, A3 toate
lumile; A2 media pe grila de timp pentru 50 de lumi) cu abatere relativă ≤ 1e-8; V3 recalculează independent (alt
algoritm: actualizare incrementală pas cu pas, recursia discountului ρ·c̃ + x) ln E_H și max ln E pentru primele 40
de lumi din fiecare celulă × 3 modele, |Δ| ≤ 1e-7; V4 recalculează din per-lume puterile, fals-pozitivele, limitele
Clopper–Pearson (bisecție pe CDF binomială exactă) și porțile Q1–Q3a; V5 fixturile F1–F3, I1–I3 reimplementate;
V6 reclasificarea FR-01 prin bisecție; V7 sha256 ale protocoalelor/sigiliului/codului/manifestului SSD neschimbate.
`VERIFICARE_IP_PASS` numai dacă toate trec. Un defect al verificatorului ⇒ amendament sigilat înainte de remediere.

## 8. Fișiere (lista închisă)

Noi: `tu4/PROTOCOL_TU4_IP.md`, `tu4/PROTOCOL_TU4_IP_H1_MA.md`, `tu4/PROTOCOL_TU4_IP_H2_UZ.md`,
`tu4/PROTOCOL_TU4_IP_H3_AD.md`, `tu4/SIGILIU_TU4_IP.json`; cod `tu4/ip_core.py` (legi, eșantionare, modele, nucleul
compilat), `tu4/ip_run.py` (martori, generare memmap, calificare), `tu4/tests/test_ip.py`, `tu4/verifica_ip.py`;
rezultate `tu4/rezultate/IP/` (`MARTORI_IP.json`, `CALIFICARE_IP.json`, `PER_LUME_IP.npz`, `MANIFEST_SSD_IP.json`,
`VERIFICARE_IP.json`, `RAPORT_IP.md`, jurnalele; toate 0444). Pe SSD: `./ssd_data/QL649_S11/`.
Actualizate: `predari/OPERATIV.md`, `predari/MESAJE_UTILIZATOR_QL649.md` (Mesajul 54), perechea de predare.
Nimic din TU3, S10 (în afară de reclasificarea ALĂTURI), pistele închise, produsul vechi, gardul sau timerul.

## 9. Ce NU face S11

Nu citește arhiva reală, nu emite predicții, nu alege bilete reale, nu afirmă că vreo abatere există. Calificarea
arată numai că, DACĂ urna ar avea abaterea de tipul H_k la marginea încă permisă de date (D_max, margine superioară
optimistă), modelul k ar demonstra-o prospectiv în ≤ 520 extrageri cu probabilitate ≥ 0.8, fără a depăși α sub urna
perfectă. Estimarea centrală S10 (RAPORT_FR §4.2) rămâne: probabil nu există nimic de găsit.
