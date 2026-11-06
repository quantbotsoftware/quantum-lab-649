# Raport Științific — Motorul Nativ Rust `KJ-V5` (`rust_core_v2` v2.0.0)

- **Protocol preînregistrat:** `KJV5-RCV2-P1` (`PROTOCOL_KJV5_RUST_V2.md`, SHA-256 `1ba5e6ce38e87eeba2542edb85df9f511fbfb3a5e32d9d0efbfc66aa94749201`)
- **Calificare sintetică pre-arhivă:** `KJV5_QUALIFIED` (`6 / 6 PASS`, `archive_files_read = 0`, `technical_incidents = 1`, `CALIFICARE_Q_KJV5.json`, SHA-256 `39d62345af25a225be9e0cb5b8231f70091fcb9eb640ea04c26afbc68fdad710`)
- **Sigiliu cod înainte de arhivă:** `SIGILIU_COD_KJV5.json` (`39` fișiere sursă/UI/config + binar `--release` LTO `6b53c467…`, SHA-256 `c47b2edb6b47d11310770f545f4c9b89d1d0d691c30ff10f6488cebb6e6e8105`)
- **Verificare independentă Python/NumPy:** `PASS` (`5 / 5`, eroare maximă de pas `8.327e-15 < 1e-11`, aliniere comparatoare `B/R/U` față de `HS-V4` pe `13` fluxuri cu diferență `0.00e+00`, `VERIFICARE_KJV5.json`, SHA-256 `ed1a6fd243e9bc1c7a43f1f35220fc338630a0108245c7c4d97915b73cbd3e34`)
- **Verdict științific RO LIVE (`Full_KJV5`):** **`KJV5_NO_PROMOTION_EXPLORATORY`** (`6/49`: **`0 / 6`**, `5/40`: **`2 / 6`** [`G4`, `G5`], `Joker`: **`0 / 6`**)
- **Încadrare epistemică obligatorie:** **`positive_claims_allowed = false`**. Toate variantele $(\sigma_\alpha, \sigma_\beta, \sigma_\gamma)$ și nucleele deterministe raportate mai jos reprezintă **minime de energie / stări statistice condiționate de istoric** ale portofoliului cauzal Bayesian, **nu** predicții cu avantaj demonstrat și fără nicio promisiune financiară sau comercială. Întregul calcul este strict clasic (`IEEE-754 binary64` + cuadratură Gauss–Hermite 2D în `Complex64` și programare dinamică pe partiții pe 24 fire CPU).

---

## 1. Sinteză arhitecturală și guvernanță pre-arhivă

Motorul nativ Rust `KJ-V5` (`./rust_core_v2/src/kjv5/`) testează o ipoteză fizico-algebrică distinctă de motoarele anterioare (`DL-649`, `PG`, `CF`, `RH`, `PL-V3`, `TU3/TU4`, `HS-V4`): descompunerea dinamicii secvențiale de neechilibru pe **schema de asociere Johnson** $J(N, k)$ și subspațiul ireductibil al perechilor $V_2$:

1. **`K1` — Histerezisul învelișurilor Johnson–Krawtchouk:** proiecția intersecțiilor cauzale $u_s = |\sigma_s \cap D_{s-1}|$ pe baza ortonormală discretă Krawtchouk $\{\widetilde{K}_m(u)\}_{m=1,2,3}$ ponderată de legea hipergeometrică nulă $p_0(u)$, cu memorie exponențială ($\tau_{\text{sh}} = 128$, regularizare $N_0 = 24$, saturare $A_{\text{sh}} = 0.55$).
2. **`K2` — Transportul ireversibil Koopman pe $V_2 \to V_2$:** proiecția matricei de tranziție cauzale $T_{s-1 \to s}$ pe complementul ortogonal al marginalei $V_0 \oplus V_1$ (atât partea antisimetrică de curent $A = \frac{1}{2}(T - T^\top)$ ridicată prin pătratul antisimetric, cât și partea simetrică reziduală perpendiculară pe învelișul de ordin 1 $\Phi^{(1)}$), cu extracție spectrală Jacobi 2×2 pe modurile extremale $(\lambda_+, u_+)$ și $(\lambda_-, u_-)$ sub prag de gol spectral $\varepsilon_{\text{gap}} = 10^{-8}$.
3. **`K3` — Curentul antisimetric Schnakenberg pe $V_1$ + urna secundară:** fluxul ciclic net pe 3 decalaje cauzale $(0.55, 0.30, 0.15)$ în spațiul bilelor individuale + potențialul de repetiție/memorie pe urna secundară ($1/20$ la Joker, $1/10$ la FR Loto, $1/26$ la Powerball, $1/5$ la EuroDreams, $1/4$ la Cash4Life).
4. **`K4` — Funcția de partiție exactă 2D Gauss–Hermite (`14 × 14` noduri) + Split-DP pe $D_{s-1} \sqcup D_{s-1}^c$ și portofoliul martingal Bayesian cu ancoră uniformă $w_0^{(0)} = 0.50$:** garantează analitic și numeric $E_s \ge 0.50$ la fiecare pas $s$, indiferent de secvența de extrageri, eliminând supra-ajustarea exponențială.

### Transparența incidentului tehnic pre-arhivă (`technical_incidents = 1`)
Înainte de atingerea oricărui fișier `.jsonl` istoric (`archive_files_read = 0`), prima rulare a calificării sintetice `Q1–Q6` (`incidente/01/CALIFICARE_Q_KJV5_INCIDENT_01.json`, `5 / 6` teste trecute) a evidențiat în fixture-ul sintetic `Q3` (ciclul determinist 3-fazic de blocuri disjuncte) o degenerare exactă de multiplicitate $2$ a valorii proprii maximale pe $V_2$, ceea ce activa garda de gol spectral pe modurile pure `Anti`/`Dir`. Amendamentul tehnic pre-arhivă (`INCIDENT_TEHNIC_01.json` + `AMENDAMENT_TEHNIC_01.md`, ambele sigilate `0444`) a documentat rezolvarea fără modificarea arhitecturii sau a pragurilor `G1–G6`, după care suita sintetică a obținut **`6 / 6 PASS`** (`CALIFICARE_Q_KJV5.json`), iar toate sursele au fost sigilate `0444` în `SIGILIU_COD_KJV5.json` înainte de rularea `kjv5-walkforward`.

---

## 2. Rezultate Walk-Forward Cauzale pe Loteriile din România (`Full_KJV5`, `WARMUP = 100`)

Evaluarea cauzală strictă actualizează starea $(K1, K2, K3)$ și masele Bayesiene $(w_0, \dots, w_7)$ exclusiv după scorarea pasului curent $s \in \{100, \dots, S-1\}$. Zilele cu extrageri duble sunt tratate canonic ca un singur pas temporal cauzal.

### 2.1. Tabel sintetic al porților `G1–G6` pe RO LIVE (`Full_KJV5`)

| Joc RO | Pași evaluați (extrageri țintă) | Potriviri `KJ-V5` vs `B` / `R` | Exces mediu vs `U` (`G1 >= +0.20`) | `LogScore(KJ-V5)` vs `U` / `B` | `Brier(KJ-V5)` vs `U` / `B` | $E_S$ final ($\min_s E_s$) | $w_0$ final | Porți trecute | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Loto 6/49** (`6/49`) | `2,431` (`2,499`) | `1,847` vs `1,851` / `1,822` | `+0.004402` | `-41,117.3625` (`-0.2879` vs `U`, `+51.8712` vs `B`) | `13,158.0082` vs `13,158.0000` / `13,169.1202` | `0.728208` (`0.652697`) | `0.686617` | **`0 / 6`** | `NO_PROMOTION` |
| **Loto 5/40** (`6/40`, bilet `5`) | `2,329` (`2,392`) | `1,830` vs `1,762` / `1,837` | `+0.015050` | `-36,264.2147` (`-0.1529` vs `U`, `+43.1230` vs `B`) | **`12,199.1856` < `12,199.2000` (`U`)** | `0.833960` (`0.826696`) | `0.599549` | **`2 / 6` (`G4`, `G5`)** | `NO_PROMOTION` |
| **Joker** (`5/45 + 1/20`) | `2,041` (`2,104`) | `1,296` vs `1,305` / `1,301` | `+0.010414` | `-35,792.6338` (`-0.3653` vs `U`, `+91.4312` vs `B`) | `11,349.9498` vs `11,349.9111` / `11,364.2380` | `0.702473` (`0.691714`) | `0.711771` | **`0 / 6`** | `NO_PROMOTION` |

### 2.2. Stabilitatea pe ferestre temporale (`Jumătatea 1`, `Jumătatea 2`, `Ultimii 100 pași`)

- **Loto 6/49 (`1995-10-01 .. 2026-11-01`):**
  - *Jumătatea 1 (`1,215` pași / `1,225` extrageri):* `hits = 905` (`B = 887`, `R = 903`, exces `+0.004082`), `ΔLogScore vs B = +41.9826`, `ΔLogScore vs U = -0.4029`.
  - *Jumătatea 2 (`1,216` pași / `1,274` extrageri):* `hits = 942` (`B = 964`, `R = 919`, exces `+0.004710`), `ΔLogScore vs B = +9.8886`, **`ΔLogScore vs U = +0.1150`**, **`Brier = 6,707.9705 < Brier(U) = 6,708.0000`**.
  - *Ultimii 100 pași (`104` extrageri):* `hits = 70` (`B = 82`, `R = 68`), `ΔLogScore vs U = +0.0304`, `Brier = 547.5839 < Brier(U) = 547.5918`, dar `ΔLogScore vs B = -0.4921` (motiv pentru care `G5` este `FAIL`).
- **Loto 5/40 (`1996-11-10 .. 2026-11-01`):**
  - *Jumătatea 1 (`1,164` pași / `1,174` extrageri):* `hits = 935` (`B = 861`, `R = 876`, exces **`+0.046422`**), **`ΔLogScore vs U = +0.3763`**, **`Brier = 5,987.2733 < Brier(U) = 5,987.4000`**.
  - *Jumătatea 2 (`1,165` pași / `1,218` extrageri):* `hits = 895` (`B = 901`, `R = 961`), `ΔLogScore vs B = +5.2982`.
  - *Ultimii 100 pași (`104` extrageri):* `hits = 87` (`B = 57`, `R = 76`, exces **`+0.086538`**), `ΔLogScore vs B = +0.4680`, **`Brier = 530.3998 < Brier(U) = 530.4000`** (`G4` și `G5` ambele **`PASS`**).
- **Joker (`2000-10-08 .. 2026-11-01`):**
  - *Jumătatea 1 (`1,020` pași):* `hits = 609` (`B = 641`, `R = 627`), `ΔLogScore vs B = +70.1634`.
  - *Jumătatea 2 (`1,021` pași):* `hits = 687` > `R = 674` > `B = 664` (exces **`+0.037703`**), `ΔLogScore vs B = +21.2678`.
  - *Ultimii 100 pași (`104` extrageri):* `hits = 62` (`B = 72`, `R = 72`), `ΔLogScore vs B = -0.0558`.

### 2.3. Distribuția pe categorii de potriviri (`Full_KJV5` vs `B`, `R` și așteptarea hipergeometrică `U`)

- **Loto 6/49 (`2,499` extrageri țintă):** `exact 3/6 = 43` (`B = 45`, `R = 46`, `U = 44.11`), `exact 4/6 = 2` (`B = 2`, `R = 0`, `U = 2.42`), `5/6 = 0` (`U = 0.05`), `6/6 = 0`.
- **Loto 5/40 (`2,392` extrageri țintă, 5 bile alese din 6 extrase):** `exact 3/5 = 40` (`B = 40`, `R = 44`, `U = 40.79`), `exact 4/5 = 1` (`B = 2`, `R = 1`, `U = 1.85`), `5/5 = 0` (`U = 0.02`).
- **Joker (`2,104` extrageri țintă, 5/45 principal):** `exact 3/5 = 11` (`B = 12`, `R = 12`, `U = 13.43`), **`exact 4/5 = 1`** (`B = 0`, `R = 0`, `U = 0.34`), `5/5 = 0`.

### 2.4. Stări statistice post-arhivă certificate global pe 24 fire CPU (după `2026-11-01`)

Enumerarea paralelă completă (`exact_global_certified = true`) peste toate cele `13,983,816` (`6/49`), `658,008` (`5/40`) și `24,435,180` (`Joker`) stări comune produce următorul multiplet Coulomb–Jastrow $(\alpha, \beta, \gamma)$ (minime istorice condiționate de energie, **nu** predicții):

| Joc RO | Varianta $\sigma_\alpha$ (minim global $E_\alpha$) | Varianta $\sigma_\beta$ | Varianta $\sigma_\gamma$ | Nucleu comun ($\ge 2$ variante) | $\det G_3$ | Gol $\Delta \ln P$ |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **Loto 6/49** | `[11, 16, 22, 35, 37, 44]` ($E_\alpha = 16.433490$, lift `+0.019921`) | `[6, 11, 20, 22, 35, 44]` ($E_\beta = 16.434828$) | `[11, 31, 35, 36, 37, 44]` ($E_\gamma = 16.435225$) | `[11, 22, 35, 37, 44]` | `0.305556` | `0.000305` |
| **Loto 5/40** | `[6, 10, 15, 19, 20]` ($E_\alpha = 13.375037$, lift `+0.021935`) | `[6, 7, 15, 28, 33]` ($E_\beta = 13.378225$) | `[6, 7, 19, 27, 29]` ($E_\gamma = 13.378427$) | `[6, 7, 15, 19]` | `0.648000` | `0.000686` |
| **Joker** | `[20, 28, 32, 38, 40] + J5` ($E_\alpha = 16.981105$, lift `+0.030430`) | `[4, 9, 17, 22, 43] + J5` ($E_\beta = 17.001190$) | `[4, 19, 36, 43, 44] + J5` ($E_\gamma = 17.003634$) | `[4, 43]` (`+ J5`) | `0.722222` | `0.015834` |

---

## 3. Studiul de ablație pe 4 configurații (`ABLATIE_RO_KJV5.json`)

| Joc RO | Configurație | Porți | Potriviri (`B` / `R`) | Exces vs `U` | `ΔLogScore vs U` | `ΔBrier vs U` | $E_S$ final ($\min_s E_s$) | $w_0$ final |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **6/49** | `K1` pur (Krawtchouk) | `1 / 6` (`G2`) | **`1,881`** (`1,851` / `1,822`) | `+0.018007` | `-0.5232` | `+0.0286` | `0.589275` (`0.523720`) | `0.848703` |
| **6/49** | `K2` pur (Koopman $V_2$) | `0 / 6` | `1,824` (`1,851` / `1,822`) | `-0.004802` | `-0.1145` | `+0.0002` | `0.889468` (`0.855411`) | `0.562134` |
| **6/49** | `K1_K2` | `0 / 6` | `1,825` (`1,851` / `1,822`) | `-0.004402` | `-0.3151` | `+0.0101` | `0.726420` (`0.684639`) | `0.688307` |
| **6/49** | `Full_KJV5` | `0 / 6` | `1,847` (`1,851` / `1,822`) | `+0.004402` | `-0.2879` | `+0.0082` | `0.728208` (`0.652697`) | `0.686617` |
| **5/40** | `K1` pur (Krawtchouk) | `1 / 6` (`G5`) | `1,828` (`1,762` / `1,837`) | `+0.014214` | `-0.5877` | `+0.0492` | `0.555744` (`0.555122`) | `0.899694` |
| **5/40** | **`K2` pur (Koopman $V_2$)** | **`5 / 6`** (`G2–G6`) | **`1,873`** (`1,762` / `1,837`) | `+0.033027` | **`+0.1117`** | **`-0.0139`** | **`1.096729`** (`0.952458`) | `0.455901` |
| **5/40** | `K1_K2` | `2 / 6` | `1,851` (`1,762` / `1,837`) | `+0.023829` | `-0.2068` | `+0.0146` | `0.803049` (`0.797917`) | `0.622627` |
| **5/40** | `Full_KJV5` | `2 / 6` (`G4,G5`) | `1,830` (`1,762` / `1,837`) | `+0.015050` | `-0.1529` | **`-0.0144`** | `0.833960` (`0.826696`) | `0.599549` |
| **Joker** | `K1` pur (Krawtchouk) | `1 / 6` (`G2`) | **`1,313`** (`1,305` / `1,301`) | `+0.018494` | `-0.6518` | `+0.0468` | `0.525307` (`0.513170`) | `0.951825` |
| **Joker** | **`K2` pur (Koopman $V_2$)** | **`3 / 6`** (`G3,G4,G6`) | `1,267` (`1,305` / `1,301`) | `-0.003369` | **`+0.0099`** | **`-0.0118`** | **`1.024651`** (`0.963054`) | `0.487971` |
| **Joker** | `K1_K2` | `0 / 6` | `1,272` (`1,305` / `1,301`) | `-0.000993` | `-0.3023` | `+0.0144` | `0.748831` (`0.729779`) | `0.667707` |
| **Joker** | `Full_KJV5` | `0 / 6` | `1,296` (`1,305` / `1,301`) | `+0.010414` | `-0.3653` | `+0.0387` | `0.702473` (`0.691714`) | `0.711771` |

**Interpretare fizică onestă a ablației:**
1. Canalul `K1` pur (histerezisul învelișurilor Krawtchouk) crește numărul de potriviri discrete pe `6/49` (`1,881 > B = 1,851`) și `Joker` (`1,313 > B = 1,305`), dar penalizează sever log-verosimilitatea pe întreaga distribuție, împingând masa posterioară nulă $w_0$ la `0.85–0.95`.
2. Canalul **`K2` pur (Koopman $V_2 \to V_2$)** este singura componentă cu câștig martingal pozitiv ($E_S = 1.0967 > 1.0$ pe `5/40` cu `5/6` porți și $E_S = 1.0247 > 1.0$ pe `Joker` cu `3/6` porți), dar mărimea efectului (`+0.1117` nats peste `2,329` pași, exces potriviri `+0.0330` sub pragul `+0.20`) este microscopică și insuficientă pentru orice avantaj practic.
3. Conform protocolului `KJV5-RCV2-P1`, **nu se efectuează nicio re-selecție post-hoc** a configurației `K2`; verdictul oficial rămâne cel al configurației complete preînregistrate `Full_KJV5` (`0/6`, `2/6`, `0/6`).

---

## 4. Evaluarea pe cele `10` loterii internaționale mecanice și electronice RNG (`INTERNATIONAL_RNG_KJV5.json`)

| Familie | Flux (`N`, `r`, `k`, bonus) | Pași eval. | Porți `KJ-V5` | Potriviri `KJ-V5` (`B` / `R`) | Exces vs `U` | `ΔLogScore vs U` | `ΔBrier vs U` | $E_S$ final ($\min_s E_s$) | $w_0$ final | Comparație `HS-V4` ($E_S$ / porți) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Mecanic extern** | `fr_loto` (`5/49 + 1/10`) | `2,728` | **`3 / 6`** (`G3,G4,G6`) | `1,651` (`1,734` / `1,712`) | `-0.004999` | **`+0.2795`** | **`-0.001056`** | **`1.322481`** (`0.739566`) | `0.378077` | `1.1583` (`3 / 6`) |
| **Mecanic extern** | `hu_hatoslotto` (`6/45`) | `1,760` | `1 / 6` (`G5`) | `1,402` (`1,357` / `1,454`) | `-0.003409` | `-0.2045` | `+0.048576` | `0.815094` (`0.793719`) | `0.613426` | `0.7816` (`1 / 6`) |
| **Mecanic extern** | `hu_otoslotto` (`5/90`) | `3,530` | `0 / 6` | `983` (`1,000` / `978`) | `+0.000299` | `-0.2594` | `+0.014197` | `0.772950` (`0.720667`) | `0.646873` | `0.8190` (`0 / 6`) |
| **Mecanic extern** | `hu_skandinav_mech` (`Kézi 7/35`) | `1,312` | `1 / 6` (`G5`) | `1,827` (`1,798` / `1,863`) | `-0.007470` | `-0.3710` | `+0.060464` | `0.690036` (`0.675593`) | `0.724600` | `0.7538` (`1 / 6`) |
| **Mecanic extern** | `us_powerball` (`5/69 + 1/26`) | `1,327` | `1 / 6` (`G5`) | `490` (`563` / `555`) | `-0.031526` | `-0.1266` | `+0.003842` | `0.881097` (`0.807251`) | `0.567474` | `0.7524` (`0 / 6`) |
| **RNG electronic** | `fdj_eurodreams` (`6/40 + 1/5`) | `212` | `3 / 6` (`G3,G5,G6`) | `222` (`245` / `236`) | `-0.052830` | `+0.0286` | `+0.005247` | `1.028963` (`0.832596`) | `0.485926` | `0.9082` (`1 / 6`) |
| **RNG electronic** | `hu_skandinav_rng` (`Gépi 7/35`) | `1,312` | `2 / 6` (`G2,G5`) | `1,890` (`1,806` / `1,791`) | `+0.040549` | `-0.0344` | `+0.069775` | `0.966228` (`0.798827`) | `0.517476` | `0.7796` (`1 / 6`) |
| **RNG electronic** | `ny_cash4life` (`5/60 + 1/4`) | `2,849` | `1 / 6` (`G5`) | `1,821` (`1,905` / `1,862`) | `-0.027495` | `-0.4267` | `+0.117952` | `0.652662` (`0.646338`) | `0.766093` | `0.7530` (`1 / 6`) |
| **RNG electronic** | `ny_pick10` (`10/80` din `20/80`) | `14,392` | `0 / 6` | `35,854` (`36,002` / `36,041`) | `-0.008755` | `-0.5219` | `+0.054302` | `0.593366` (`0.593366`) | `0.842650` | `0.7034` (`0 / 6`) |
| **RNG electronic** | `ny_take5` (`5/39`) | `10,682` | `1 / 6` (`G5`) | `8,003` (`8,077` / `7,964`) | `-0.005867` | `-0.5428` | `+0.038258` | `0.585841` (`0.575363`) | `0.853473` | `0.7131` (`1 / 6`) |

### Testul natural împerecheat `HU Skandináv Lottó` (`1,312` zile identice `2001-09-12 .. 2026-10-28`)
- `same_dates_verified = true` pe toate cele `1,312` zile evaluate.
- **Tragerea 1 Mecanică (`Kézi 7/35`):** `1 / 6` porți (`G5`), $E_S = 0.690036$ ($\min_s E_s = 0.675593$), `hits = 1,827` (`exces = -0.007470`), $w_0 = 0.724600$.
- **Tragerea 2 Electronică RNG (`Gépi 7/35`):** `2 / 6` porți (`G2`, `G5`), $E_S = 0.966228 < 1.0$ ($\min_s E_s = 0.798827$), `hits = 1,890` (`exces = +0.040549`), `LogScore = -20,626.3420 < LogScore(U) = -20,626.3077`, $w_0 = 0.517476$.
- Nici tragerea mecanică, nici tragerea electronică RNG nu susțin o creștere martingală reală ($E_S < 1$ pe ambele fluxuri), iar pe seriile electronice lungi (`NY Pick 10` cu `14,392` pași și `NY Take 5` cu `10,682` pași) portofoliul Bayesian concentrează automat `84%–85%` din masă pe expertul nul uniform $w_0$, protejând capitalul martingal la $E_S \approx 0.59 \ge 0.50$.
- Pe `FR Loto` (`FDJ 5/49 + 1/10`, `2,728` pași), atât `HS-V4` ($E_S = 1.1583$, `3/6`) cât și `KJ-V5` ($E_S = 1.3225$, `3/6`) detectează aceeași ușoară neuniformitate marginală/pereche în urna secundară și perechi (`ΔLogScore vs U = +0.2795`), însă fără exces de potriviri (`-0.0050` față de `U`) și mult sub pragurile de promovare `6/6`.

---

## 5. Certificarea independentă Python/NumPy (`VERIFICARE_KJV5.json`)

Scriptul independent `kj_v5/verifica_kjv5.py` (sigilat `0444`, fără niciun import din codul de producție) a certificat **`5 / 5 PASS`**:
- **`V1_SEALS_0444_AND_CODE_SHA256` (`PASS`):** toate cele `9` artefacte de protocol/calificare/sigiliu/rezultate sunt `0444` și toate cele `39` fișiere din `rust_core_v2/` au SHA-256 identic cu `SIGILIU_COD_KJV5.json` și `CALIFICARE_Q_KJV5.json`.
- **`V2_PREARCHIVE_QUALIFICATION_6_OF_6` (`PASS`):** `KJV5_QUALIFIED`, `6/6`, `archive_files_read = 0`, `technical_incidents = 1`.
- **`V3_INDEPENDENT_PYTHON_NUMPY_K1_K4_PARITY` (`PASS`):** recalcularea independentă în Python/NumPy (`np.linalg.eigh` + `complex128` 2D Gauss–Hermite + polinoame simetrice elementare) pe `649`, `540` și `joker` reproduce rapoartele de verosimilitate Rust `step_lrs` la precizie de mașină: **`max_abs_err = 8.327e-15`** (`< 1e-11`).
- **`V4_COMPARATOR_B_R_U_EXACT_ALIGNMENT_WITH_HSV4` (`PASS`):** comparatoarele `B`, `R` și `U` din motorul nativ Rust `KJ-V5` coincid exact cu cele din `HS-V4` pe toate cele **`13` fluxuri** (`3` RO + `10` INTL/RNG), cu **`max_diff_rotunjire = 0.00e+00`**.
- **`V5_MARTINGALE_E_GE_050_ALL_22_RUNS_AND_SKANDINAV` (`PASS`):** peste toate cele `22` rulări walk-forward (`12` ablații RO + `10` INTL/RNG), $\min E_s = 0.51316958 \ge 0.50$, sincronizarea pe `1,312` zile a perechii `HU Skandináv` este intactă și `positive_claims_allowed == false` peste tot.
