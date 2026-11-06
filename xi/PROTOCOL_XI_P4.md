# PROTOCOL XI-P4 — „Amestecare insuficientă”: interacțiuni de perechi vecine și pe blocuri de încărcare (planul V12, faza P4)

Scris și sigilat (`xi/SIGILIU_XI_P4.json`, permisiuni `0444`) **ÎNAINTE** de orice cod P4 (`xi/p4/`), de orice calcul sintetic sau real P4 și fără niciun acces la `xi/date_p2/*/rezerva.json` ori `xi/date_p2/*/sigilat/`.
Autoritate: Mesajele 107 (autonomie 100%), 108 (predare la fiecare închidere), 117–122, 130–136 („să facem imposibilul posibil”), planul `xi/PLAN_V12_PREDICTIE.md` (`a675289e736f6754e3ca14593e89f4c58be3297f0a3f27b05af927124d302bd1`) și amendamentul `xi/AMENDAMENT_V12_01.md` (`7db003c5b920bddd3fd9d8e86d405ba80deb60519f4f8190545ee3f2bf13e9fe` — confirmarea pe arhive, fără poartă prospectivă obligatorie).
`positive_claims_allowed=false`. Calcul clasic exact în virgulă mobilă dublă (`float64`) și întregi exacți (`int` / `Fraction`) pe CPU (`/usr/bin/python3 -B`, `PYTHONDONTWRITEBYTECODE=1`, `OPENBLAS_NUM_THREADS=1`, NumPy `multiprocessing` pe 24 de fire). Nimic din `quantum_limit` sau din modelele închise nu este importat ori rulat.

---

## 1. Ipoteza fizică, informația pre-țintă și distinctitatea completă

### 1.1. Ipoteza fizică („amestecare insuficientă”)
Înaintea fiecărei extrageri dintr-o urnă $k$-din-$n$, bilele $1, \dots, n$ sunt depozitate și eliberate în cameră dintr-un rastel ordonat: fie dintr-un tub/lanț secvențial $1 \dots n$, fie din tuburi verticale paralele / coloane de câte $b$ bile. Dacă timpul de amestecare sau turbulența mecanică/pneumatică nu șterge complet vecinătatea inițială de încărcare (chiar dacă rotația globală a tamburului uniformizează probabilitatea marginală individuală $\pi_i \approx k/n$ a fiecărei bile!), atunci perechile de numere **vecine numeric** ($1 \le |i - j| \le r$) sau aflate în **același bloc/tub de încărcare** tind să iasă **împreună** în aceeași extragere $S_t$ mai des decât sub uniform ($\beta > 0$, atracție de vecinătate/bloc), ori mai rar ($\beta < 0$, respingere/stratificare mecanică la evacuare).

### 1.2. Informația pre-țintă și motivul unei decizii diferite peste repere și banca P1/P2
- **Informația pre-țintă la pasul $t$:** exclusiv extragerile anterioare $S_1, \dots, S_{t-1}$ ale aceluiași subjoc („ca în ajun”), rezumate prin sumele statisticilor suficiente intra-extragere $\sum_{s=1}^{t-1} A_c(S_s)$, plus geometria fixată a etichetelor $\{1, \dots, n\}$.
- **De ce banca P1/P2 și reperele erau oarbe la acest semnal:**
  1. `STAT`, `DRIFT`, `GAP` (precum și reperele clasice `B`, `I` și modelele `TU4 H1/H2/H3`) modelează exclusiv ponderi individuale 1-corp $w_i$ în legea Poisson condiționată $P_w(S) \propto \prod_{i \in S} w_i$. Sub orice astfel de lege 1-corp, când marginalele individuale sunt uniforme ($w_i = 1$), distribuția colapsează identic la uniform, iar condiționat de marginale asocierea perechilor este întotdeauna slab negativă ($P_w(i, j) \le P_w(i)P_w(j)$).
  2. `FERMI` (procesul punctual determinantal $k$-DPP din P1/P2) construiește nucleul $K_{ij} = \sqrt{\max(\hat{\pi}_i \hat{\pi}_j - \hat{\pi}_{ij}, 0)}$. Prin structura determinantului $P(i, j) = K_{ii}K_{jj} - K_{ij}^2 \le P(i)P(j)$, un $k$-DPP poate reprezenta **numai respingere**, tăind identic la zero orice exces pozitiv de coapariție ($\hat{\pi}_{ij} > \hat{\pi}_i \hat{\pi}_j \implies K_{ij} = 0$); în plus, `FERMI` estimează $\binom{n}{2}$ perechi nestructurate puternic contractate spre uniform.
  3. P4 modelează direct **legea comună de mulțime Gibbs / Ising–Potts cu 2 corpuri** $P_\beta(S) = \exp(\beta A(S)) / Z_{n,k}(\beta)$ peste toate cele $\binom{n}{k}$ bilete posibile, cu $\beta$ de **ambele semne** ($\beta > 0$ atracție și $\beta < 0$ respingere) și cu **normalizare exactă** (fără enumerarea celor $\binom{n}{k}$ mulțimi).

### 1.3. Auditul complet al distinctității față de toate modelele închise ale proiectului
Verificarea prin inspecție directă a protocoalelor și surselor din `next_candidate/predictie_numere/` și `next_candidate/quantum_lab_649/` confirmă că nicio pistă anterioară nu a testat legea $P_\beta(S) \propto \exp(\beta A(S))$ a vecinătății numerice sau a blocurilor de încărcare pe arhivele reale:
- **Termenul „adiacență” în `predictie_numere/`** (`OC`, `TP`, `EX`, `EC`, `CR`, `MC`, `LS`, `DL`): desemnează exclusiv adiacența calendaristică joi–duminică (3 sau 4 zile) între extrageri succesive în timp, nu vecinătatea numerică $|i - j| \le r$ în aceeași extragere.
- **`DC-649` (`deplasari_circulare_20261023`):** leagă tranzițiile temporale $(a \in S_{t-1} \to b \in S_t)$ după diferența $(b - a) \bmod 49$ între două extrageri consecutive, nu coapariția simultană $\{i, j\} \subset S_t$.
- **`SC-649` (`suma_colectiva_20261024`):** modelează suma $\sum_{i \in S} i$, care este invariantă la regruparea internă la sumă fixată (de pildă $\{1, 2, 6\}$ are suma $9$ și o pereche consecutivă, pe când $\{1, 3, 5\}$ are aceeași sumă $9$ și zero perechi consecutive).
- **`MC-649` (`memorie_compozitie_20261023`):** modelează tranziții temporale ale compoziției unui grup fix între $S_{t-1}$ și $S_t$ cu ieșire 1-corp Fisher, nu energia internă de pereche $\binom{|S \cap B|}{2}$.
- **`Runda D` (`runda_d`):** studiu metodologic exclusiv pe date sintetice (`STOP_D_SYNTHETIC`, zero scoruri pe arhive reale), pe $\binom{n}{2}$ perechi individuale izolate $1 + \theta f_{ij}(S)$ fără geometrie de vecinătate numerică sau de blocuri de încărcare.
- **Familiile de graf/istorie pe segment (`DL`, `PG`, `CF`, `RH`, `LS`, `FS`, `AT`, `EC`, `RA`, `SR`, `RB`, `OR`, `AO`, `AC`, `S`, `G`, `MI`, `XJ`, `TI`, `N1`, `N2`)** și pistele **`QL649`, `BO649`, `WU649`, `GL649` (masa cifrelor tipărite), `SE649` (anotimpuri), `CS649` (caruselul seturilor), `PL649`, `TU4 H1/H2/H3`:** toate produc scoruri marginale 1-corp pe bile (eventual netezite cosinus pe etichetă în `H3`), niciodată o distribuție comună Gibbs cu potențial de pereche în aceeași extragere.

---

## 2. Specificația matematică exactă a modelelor și normalizarea fără enumerare

Pentru un subjoc $(n, k)$, etichetele $\{1, \dots, n\}$ se reprezintă intern 0-bazat prin $\{0, \dots, n - 1\}$ ($i_0 = \text{etichetă} - 1$), iar o extragere este o submulțime $S \subset \{0, \dots, n - 1\}$ cu $|S| = k$.
Pentru orice subjoc cu $k = 1$ (bila Joker $(20, 1)$, numéro chance $(10, 1)$, Powerball $(26, 1)$), orice statistică de perechi $A(S) \equiv 0$, deci $P_\beta(\{i\}) = 1/n = P_U(\{i\})$ exact (contribuție $\log E_{\text{bilă}} = 0$).

### 2.1. Familia `VEC` — vecinătate numerică pe lanțul $0 \dots n-1$
Pentru raza $r \in \{1, 2\}$, definim numărul perechilor apropiate din extragerea $S$:
$$A_{\text{vec}, r}(S) = \left|\left\{\{i, j\} \subset S : 1 \le |i - j| \le r\right\}\right|$$
și grila simetrică de 10 valori cu ambele semne:
$$\mathcal{B}_{\text{vec}} = (-1.20,\ -0.60,\ -0.30,\ -0.15,\ -0.07,\ +0.07,\ +0.15,\ +0.30,\ +0.60,\ +1.20)$$
(în total $2 \times 10 = 20$ de componente $(r, \beta)$ pentru $k \ge 2$). Legea componentei $(r, \beta)$ peste toate cele $\binom{n}{k}$ submulțimi este:
$$P^{\text{vec}}_{r, \beta}(S) = \frac{\exp\left(\beta A_{\text{vec}, r}(S)\right)}{Z^{\text{vec}}_{n, k, r}(\beta)}, \qquad Z^{\text{vec}}_{n, k, r}(\beta) = \sum_{|S|=k} \exp\left(\beta A_{\text{vec}, r}(S)\right).$$

**Normalizare exactă, marginale exacte și eșantionare exactă (programare dinamică înainte–înapoi pe lanț):**
Reprezentând $S$ prin vectorul de ocupare $x_0, \dots, x_{n-1} \in \{0, 1\}$ cu $\sum_{i=0}^{n-1} x_i = k$, alegerea lui $x_i$ depinde numai de ultimele $r$ poziții, codificate în starea $s \in \{0, \dots, 2^r - 1\}$ ($s = x_{i-1}$ pentru $r = 1$; $s = 2 x_{i-2} + x_{i-1}$ pentru $r = 2$, inițial $s = 0$ înainte de $i = 0$). La alegerea $x_i = 1$, creșterea energiei este $\Delta A_r(s, 1) = \text{popcount}(s)$, tranziția de memorie este $s'_1 = ((s \ll 1) \mid 1) \ \& \ (2^r - 1)$, iar la $x_i = 0$ avem $\Delta A_r(s, 0) = 0$ și $s'_0 = (s \ll 1) \ \& \ (2^r - 1)$.
- Tabelul înainte $F[i, m, s]$ ($i = 0 \dots n$, $m = 0 \dots k$, $s = 0 \dots 2^r - 1$): $F[0, 0, 0] = 1$, iar:
  $$F[i+1, m, s'_0] \mathrel{+}= F[i, m, s], \qquad F[i+1, m+1, s'_1] \mathrel{+}= F[i, m, s] \cdot e^{\beta \Delta A_r(s, 1)}.$$
  Atunci $Z^{\text{vec}}_{n, k, r}(\beta) = \sum_{s=0}^{2^r - 1} F[n, k, s]$ (exact, în $O(n k 2^r)$ operații).
- Pentru $r = 1$, numărul submulțimilor cu exact $a$ perechi consecutive ($0 \le a \le k - 1$) are și forma închisă Vandermonde:
  $$N_{\text{vec}, 1}(n, k, a) = \binom{k - 1}{a} \binom{n - k + 1}{k - a}, \qquad Z^{\text{vec}}_{n, k, 1}(\beta) = \sum_{a=0}^{k-1} \binom{k - 1}{a} \binom{n - k + 1}{k - a} e^{\beta a}.$$
- Tabelul înapoi $B[i, rem, s]$ ($B[n, 0, s] = 1$ pentru orice $s$):
  $$B[i, rem, s] = B[i+1, rem, s'_0] + \mathbf{1}[rem \ge 1] \cdot e^{\beta \Delta A_r(s, 1)} B[i+1, rem - 1, s'_1].$$
- Marginala exactă a fiecărui număr $i \in \{0, \dots, n - 1\}$:
  $$\pi_i = \frac{1}{Z^{\text{vec}}_{n, k, r}(\beta)} \sum_{m=0}^{k-1} \sum_{s=0}^{2^r - 1} F[i, m, s] \cdot e^{\beta \Delta A_r(s, 1)} \cdot B[i+1, k - 1 - m, s'_1].$$
- Eșantionarea exactă fără enumerare: pornind din $(i = 0, rem = k, s = 0)$, se alege $x_i = 1$ cu probabilitatea condiționată exactă $e^{\beta \Delta A_r(s, 1)} B[i+1, rem - 1, s'_1] / B[i, rem, s]$.

### 2.2. Familia `BLOC` — tuburi contigue și coloane de încărcare în rastel
Definim șase partiții deterministe $\Pi_{\text{tip}, b}$ ale mulțimii $\{0, \dots, n - 1\}$, pentru $\text{tip} \in \{\text{CONT}, \text{MOD}\}$ și mărimea/perioada $b \in \{5, 7, 10\}$:
- **`CONT`, $b$** (tuburi contigue de câte $b$ bile): blocurile $B_q = \{i \in \{0, \dots, n - 1\} : \lfloor i / b \rfloor = q\}$, $q = 0, \dots, \lceil n / b \rceil - 1$.
- **`MOD`, $b$** (coloane verticale în rastel cu $b$ coloane): blocurile $B_r = \{i \in \{0, \dots, n - 1\} : i \bmod b = r\}$, $r = 0, \dots, b - 1$.

Pentru o partiție $\Pi = \{B_1, \dots, B_M\}$ cu mărimi $s_q = |B_q|$, statistica perechilor extrase din **același bloc** este:
$$A_\Pi(S) = \sum_{q=1}^M \binom{|S \cap B_q|}{2}$$
cu grila simetrică de 8 valori:
$$\mathcal{B}_{\text{bloc}} = (-0.80,\ -0.40,\ -0.20,\ -0.08,\ +0.08,\ +0.20,\ +0.40,\ +0.80)$$
(în total $6 \times 8 = 48$ de componente $(\text{tip}, b, \beta)$ pentru $k \ge 2$). Legea componentei este:
$$P^{\text{bloc}}_{\Pi, \beta}(S) = \frac{\exp\left(\beta A_\Pi(S)\right)}{Z^{\text{bloc}}_{\Pi, k}(\beta)}.$$

**Normalizare exactă, marginale exacte și eșantionare exactă (convoluție de polinoame pe blocuri):**
Fie polinomul blocului $q$: $P_q(x) = \sum_{u=0}^{\min(s_q, k)} \binom{s_q}{u} e^{\beta \binom{u}{2}} x^u$ (trunchiat la gradul $k$).
- Constanta de normalizare este coeficientul exact al lui $x^k$ în produsul celor $M$ polinoame:
  $$Z^{\text{bloc}}_{\Pi, k}(\beta) = [x^k] \prod_{q=1}^M P_q(x),$$
  calculat prin tabelul prefix $D[q, m]$ ($q = 0 \dots M$, $m = 0 \dots k$) și tabelul sufix $R_{\text{suf}}[q, rem]$.
- Fie $E^{(-q)}[r] = \sum_{m=0}^r D[q-1, m] R_{\text{suf}}[q, r - m]$ coeficientul lui $x^r$ în $\prod_{q' \ne q} P_{q'}(x)$. Pentru orice $i \in B_q$, marginala exactă este:
  $$\pi_i = \frac{1}{Z^{\text{bloc}}_{\Pi, k}(\beta)} \sum_{u=1}^{\min(s_q, k)} \binom{s_q - 1}{u - 1} e^{\beta \binom{u}{2}} E^{(-q)}[k - u].$$
- Eșantionarea exactă fără enumerare: se extrag secvențial ocupările $u_q \in \{0, \dots, \min(s_q, rem)\}$ cu probabilitatea $\binom{s_q}{u_q} e^{\beta \binom{u_q}{2}} R_{\text{suf}}[q, rem - u_q] / R_{\text{suf}}[q-1, rem]$, apoi în fiecare bloc $B_q$ se aleg uniform fără înlocuire $u_q$ elemente.

### 2.3. Predictorii bayesiani (`VEC`, `BLOC`, `COMB`), e-procesul și biletele
Lista completă a celor $1 + 20 + 48 = 69$ de componente (pentru $k \ge 2$) are pe poziția $0$ legea uniformă $U$ ($P_U(S) = 1 / \binom{n}{k}$). Fiecare predictor $X \in \{\text{VEC}, \text{BLOC}, \text{COMB}\}$ atribuie $\rho_U = 1/2$ și împarte restul de $1/2$ egal între familiile sale calificate și apoi egal între componentele fiecărei familii:
- **`VEC`**: $\rho_U = 1/2$, iar cele $20$ de componente `VEC` primesc fiecare $1/40$.
- **`BLOC`**: $\rho_U = 1/2$, iar cele $48$ de componente `BLOC` primesc fiecare $1/96$.
- **`COMB`**: $\rho_U = 1/2$, `VEC` primește $1/4$ ($20 \times 1/80$), `BLOC` primește $1/4$ ($48 \times 1/192$); dacă o familie ar pica Q4, cealaltă primește $1/2$ (iar pentru $k = 1$, $\rho_U = 1$).

La pasul $t = 1, \dots, T$, folosind exclusiv $S_1, \dots, S_{t-1}$:
$$\log w_t(j) = \log \rho_j + \sum_{s=1}^{t-1} \log P_j(S_s), \qquad \log P_X(S_t \mid H_{t-1}) = \operatorname{LSE}_j\bigl(\log w_t(j) + \log P_j(S_t)\bigr) - \operatorname{LSE}_j\bigl(\log w_t(j)\bigr).$$
Log-e-valoarea acumulată pe subjoc este $\log E_X = \sum_{t=1}^T \bigl[\log P_X(S_t \mid H_{t-1}) + \log \binom{n}{k}\bigr]$, care satisface identitatea exactă de telescopare $E_X = \sum_j \rho_j \prod_{t=1}^T [P_j(S_t) / P_U(S_t)] \ge \rho_U = 1/2$ ($\log E_X \ge -\ln 2$). Pentru jocurile cu două subjocuri (`RO_joker`, `FR_loto`, `US_powerball`), $\log E_{g, X} = \log E^{\text{princ}}_{g, X} + \log E^{\text{bilă}}_{g, X}$ (cu $\log E^{\text{bilă}}_{g, X} = 0$, deci $E_{g, X} \ge 1/2$ pe jocul întreg!).
Biletul descriptiv de vârf la pasul $t$ este `ticket(marg_t)` — cele $k$ numere cu cea mai mare marginală mixtă $\pi_{X, t}(i) = \sum_j W_t(j) \pi^{(j)}_i$ (`np.round(marg, 12)`, egalități rupte prin indicele mai mic, identic cu P1/P2). Se raportează de asemenea ponderea posterioară finală pe $U$, pe atracție ($\beta > 0$) și pe respingere ($\beta < 0$).

---

## 3. Martorii analitici de informație și de decizie (derivați înainte de cod)

### 3.1. Martorul `VEC` pe $(n = 6, k = 3)$ ($\binom{6}{3} = 20$ mulțimi pe $\{1, 2, 3, 4, 5, 6\}$)
Pentru $r = 1$ și $u = e^\beta > 0$, formula Vandermonde dă $N_{\text{vec}, 1}(6, 3, 0) = 4$ (`{1,3,5},{1,3,6},{1,4,6},{2,4,6}`), $N_{\text{vec}, 1}(6, 3, 1) = 12$ și $N_{\text{vec}, 1}(6, 3, 2) = 4$ (`{1,2,3},{2,3,4},{3,4,5},{4,5,6}`), deci:
$$Z^{\text{vec}}_{6, 3, 1}(\beta) = 4(1 + 3u + u^2).$$
Numărând aparițiile fiecărei etichete pe straturile $a \in \{0, 1, 2\}$, marginalele exacte sunt:
$$\pi_1(\beta) = \pi_6(\beta) = \frac{3 + 6u + u^2}{4(1 + 3u + u^2)}, \quad \pi_2(\beta) = \pi_5(\beta) = \frac{1 + 7u + 2u^2}{4(1 + 3u + u^2)}, \quad \pi_3(\beta) = \pi_4(\beta) = \frac{2 + 5u + 3u^2}{4(1 + 3u + u^2)}.$$
Diferențele numărătorilor se factorizează exact:
- $\operatorname{num}(\pi_3) - \operatorname{num}(\pi_1) = (2u + 1)(u - 1)$,
- $\operatorname{num}(\pi_2) - \operatorname{num}(\pi_1) = (u + 2)(u - 1)$,
- $\operatorname{num}(\pi_3) - \operatorname{num}(\pi_2) = (u - 1)^2 > 0$ pentru orice $\beta \ne 0$.
Prin urmare:
- pentru orice $\beta > 0$ ($u > 1$): $\pi_3 = \pi_4 > \pi_2 = \pi_5 > \pi_1 = \pi_6 \implies$ biletul de vârf este **`[2, 3, 4]`**;
- pentru orice $\beta < 0$ ($0 < u < 1$): $\pi_1 = \pi_6 > \pi_3 = \pi_4 > \pi_2 = \pi_5 \implies$ biletul de vârf este **`[1, 3, 6]`**.
La fel, pentru $r = 2$: $Z^{\text{vec}}_{6, 3, 2}(\beta) = 4(2u + 2u^2 + u^3)$, cu $\pi_1 = \pi_6 = \frac{6u + 3u^2 + u^3}{Z}$, $\pi_2 = \pi_5 = \frac{4u + 4u^2 + 2u^3}{Z}$, $\pi_3 = \pi_4 = \frac{2u + 5u^2 + 3u^3}{Z}$, dând din nou $\pi_3 = \pi_4 > \pi_2 = \pi_5 > \pi_1 = \pi_6$ pentru orice $u > 1$.

**Istoriile martor de lungime $T_w = 8$:**
- $H_+ = 4 \times (\{1, 2, 3\},\ \{4, 5, 6\})$ (toate cele 8 extrageri au $A_{\text{vec}, 1} = 2$ și $A_{\text{vec}, 2} = 3$);
- $H_- = 4 \times (\{1, 3, 5\},\ \{2, 4, 6\})$ (toate cele 8 extrageri au $A_{\text{vec}, 1} = 0$).
Proprietăți verificate în Q1d:
1. **Informație peste `STAT` și `FERMI`:** $H_+$ și $H_-$ au exact aceleași frecvențe individuale $c(H_+) = c(H_-) = (4, 4, 4, 4, 4, 4)$ și grafuri de coapariții izomorfe $K_3 \sqcup K_3$ (tranzitive pe vârfuri), astfel încât atât `STAT`, cât și `FERMI` și `U` dau marginale identice $[1/2]^6$ și biletul **`[1, 2, 3]`** pe ambele istorii.
2. **Separare predictivă și de decizie sub `VEC`:** după $H_+$, posteriorul `VEC` se concentrează pe $\beta > 0$, dând $P_{\text{VEC}}(\{1, 2, 3\} \mid H_+) > 1/20 > P_{\text{VEC}}(\{1, 3, 5\} \mid H_+)$ și biletul **`[2, 3, 4]`**; după $H_-$, componentele $(r = 1, \beta < 0)$ domină posteriorul `VEC`, dând $P_{\text{VEC}}(\{1, 3, 5\} \mid H_-) > 1/20 > P_{\text{VEC}}(\{1, 2, 3\} \mid H_-)$ și biletul **`[1, 3, 6]`** (ambele diferite de `[1, 2, 3]` și opuse între ele).

### 3.2. Martorul `BLOC` pe $(n = 7, k = 3)$, partiția `CONT`, $b = 5$
Blocurile sunt $B_1 = \{1, 2, 3, 4, 5\}$ ($s_1 = 5$) și $B_2 = \{6, 7\}$ ($s_2 = 2$). Cu $w = e^\beta > 0$:
$$Z^{\text{bloc}}(w) = 25w + 10w^3 = 5w(5 + 2w^2), \qquad \pi_{B_1}(w) = \frac{9 + 6w^2}{5(5 + 2w^2)}, \qquad \pi_{B_2}(w) = \frac{15}{5(5 + 2w^2)},$$
de unde $\pi_{B_1}(w) - \pi_{B_2}(w) = \frac{6(w^2 - 1)}{5(5 + 2w^2)}$: pentru $\beta > 0$ biletul este **`[1, 2, 3]`**, iar pentru $\beta < 0$ biletul este **`[1, 6, 7]`**.

---

## 4. Arhivele, familiile Holm și regula de confirmare pe arhive (`AMENDAMENT_V12_01`)

### 4.1. Dezvoltare pe arhiva RO (explorată, fără rezervă oarbă)
- Baza SQLite înghețată din P1/C2/C3/C4: `${LOTO_RO_ROOT:-.}/loto_romania/data/snapshots/c6bfd021af15d9d6ece6b20d106550e4c8474049e38e9caa3bd1c99d19766adb/loto_romania.sqlite`, `sha256 = 9942abfc25282a715cba70e4f6d17a885a467eaf5fe0440838dc28114003c078`, citită identic cu XI-P1 §2 (`regular` și `special`):
  * `RO_649`: $(49, 6)$, $T = 2384$;
  * `RO_540`: $(40, 6)$, $T = 2341$;
  * `RO_joker`: principal $(45, 5)$ + bilă $(20, 1)$, $T = 2203$.
- Familia Holm RO: $3 \times |\mathcal{P}|$ teste ($9$ teste dacă ambele familii `VEC` și `BLOC` trec Q4), $\alpha = 0.01$, $p = \min(1, 1/E)$ (cel mai mic $p$ cere $E \ge 900$). Fiind o arhivă deja explorată și fără rezervă oarbă, o respingere pe RO primește eticheta `P4_CANDIDAT_RO` (nu `CONFIRMAT_PE_ARHIVA`).

### 4.2. Dezvoltare pe arhivele străine (`xi/date_p2/*/dev.json`) și testul global
Se evaluează cele **4 arhive străine valide** care au perechea `(dev.json, rezerva.json)` în `xi/date_p2/`:
1. **`HU_otos`** (Ungaria Ötöslottó, $(90, 5)$): `dev.json` (`sha256 = b6024d3ad27d4dc6b09b411b5da680d3a4e16a8fa453222618fa40d30a7de557`, $T_{\text{dev}} = 2908$), `rezerva.json` (`1acd697ea3354034595abf40bb59650087f3a3aad29231ad5b00b1a4661b3213`, $R = 726$).
2. **`FR_loto`** (Franța Loto, $(49, 5) + (10, 1)$): `dev.json` (`sha256 = eec4e4d3751804a029f89e92ee108047776c724dc5b9592ba0f0d9eefeb9e636`, $T_{\text{dev}} = 1980$), `rezerva.json` (`b8aa19bc5026bafcc8085edb2e90daa95ec31b84d2ac62e26923d6a90298fedd`, $R = 494$).
3. **`US_powerball`** (SUA Powerball, $(69, 5) + (26, 1)$): `dev.json` (`sha256 = cd5aa83ad627c296117bfaf5df0451b10343983abc1e154b38a5351b85985e40`, $T_{\text{dev}} = 1141$), `rezerva.json` (`afc3387713acb021b99cab2d4ea7f847e168c2f57207cfec03a286d8fc1bee0f`, $R = 285$).
4. **`HU_hatos`** (Ungaria Hatoslottó, $(45, 6)$, **perioada curată fără pótszám `data >= "2007-07-29"`**, conform `AMENDAMENT_XI_P2_02` §1–2 și `DIAGNOSTIC_CAMPURI_HU.json`: primele 794 de rânduri din `dev.json` aveau 21 de câmpuri cu pótszám și sunt excluse după dată, rămânând exact sufixul `extrageri[794:]` cu 20 de câmpuri): `dev.json` (`sha256 = 951d6eaf19fd434dbbc8d9af95dec2b2340e3e648fae061c289138e95dbfd784`, $T_{\text{dev}} = 694$ extrageri cu `data >= "2007-07-29"`), `rezerva.json` (`9a67d775d0c6f46d6d9e903907aed4004adae0776d3b4cc8337e820411e204d3`, $R = 372$, integral cu 20 de câmpuri).
*(Notă: `DE_6aus49_sambata` și `US_megamillions` au `EXCLUS.json` din P2, fără `dev.json` și fără `rezerva.json`; nu se ating fișierele lor `sigilat/`.)*

- **Familia Holm pe dezvoltarea străină (poarta către rezerva oarbă, identică structural cu XI-P2 §1):**
  pentru cei $|\mathcal{P}|$ predictori calificați, cele $4 \cdot |\mathcal{P}|$ teste pe jocuri străine + $|\mathcal{P}|$ teste globale $E^{\text{dev}}_{\star, X} = \prod_{g \in \{\text{HU\_otos, FR\_loto, US\_powerball, HU\_hatos}\}} E^{\text{dev}}_{g, X}$ = **$5 \cdot |\mathcal{P}| = 15$ teste** la $\alpha = 0.01$ (pragul celui mai mic $p$: $E \ge 1500$). Lista `supravietuitori_dev_strain` conține testele respinse de Holm în această familie.

### 4.3. O singură rulare pe `rezerva.json` (numai dacă există supraviețuitori)
- Dacă `supravietuitori_dev_strain` este **goală**: verdict **`P4_NICIUN_SUPRAVIETUITOR`**; rezervele `rezerva.json` (0400) rămân **SIGILATE și NECITITE**.
- **Numai dacă `supravietuitori_dev_strain` este nevidă**, și numai după ce verificatorul independent `verifica_p4.py dev` returnează `PASS`: se scrie `xi/p4/SIGILIU_CONFIRMARE_P4.json` (cu sha-urile `P4_DEV_REZULTATE.json`, `VERIFICARE_P4_DEV.json` și lista supraviețuitorilor) și se execută **o singură dată** `p4.py confirmare` pe `rezerva.json` (ponderile posterioare continuă neîntrerupt din dezvoltare pe rezervă: $E^{\text{rez}}_{g, X} = \prod_{t \in \text{rez}} P_X(S_t \mid H_{t-1}) / P_U(S_t)$, respectiv produsul pe cele 4 jocuri pentru `GLOBAL`), cu corecția Holm la $\alpha = 0.01$ pe numărul de supraviețuitori, urmată de `verifica_p4.py rez`.

---

## 5. Calificarea tehnică (date sintetice; înainte de orice citire a datelor reale)

Seminții fixe NumPy PCG64: `SEED = 202611014` + deplasări deterministe în cod. Niciun fișier de date reale (`loto_romania.sqlite`, `dev.json`, `rezerva.json`) nu este deschis în subcomanda `teste`.

- **Q1 — Exactitate matematică și martori analitici:**
  - **(a)** Pe $(10, 3)$ și $(12, 4)$, toate cele 68 de componente non-uniforme (`VEC` + `BLOC`): $|\sum_{|S|=k} P_j(S) - 1| \le 10^{-12}$, eroarea maximă pe $P_j(S)$ și pe $\pi_i$ față de enumerarea directă $\le 10^{-12}$, $|\sum_i \pi_i - k| \le 10^{-12}$. Pe toate subjocurile reale cu $k \ge 2$ — $(49, 6), (40, 6), (45, 5), (49, 5), (69, 5), (90, 5)$: $|\sum_i \pi_i - k| \le 10^{-11}$, acord cu formula Vandermonde la $r = 1$ ($\le 10^{-12}$), și enumerare completă pe $(49, 6)$ ($13\,983\,816$ mulțimi) pentru `VEC(r=2, β=0.60)` și `BLOC(CONT, b=7, β=0.40)` cu suma probabilităților $= 1 \pm 10^{-9}$.
  - **(b)** Pe subjocurile cu $k = 1$ ($(20, 1), (10, 1), (26, 1)$): $|\log P_X(\{i\}) + \ln n| \le 10^{-12}$; telescoparea BMA pe o istorie sintetică $|\log E_{\text{secv}} - \log E_{\text{închis}}| \le 10^{-9}$; $\log E \ge -\ln 2 - 10^{-12}$ pe fiecare subjoc în toate replicile Q3/Q4.
  - **(c)** Eșantionatoarele exacte pe $(8, 3)$ ($200\,000$ de extrageri fiecare pentru `VEC(r=2, β=+0.60)`, `VEC(r=1, β=-0.60)` și `BLOC(CONT, b=3, β=+0.80)`): test $\chi^2$ pe cele $\binom{8}{3} = 56$ de mulțimi față de distribuția exactă, $p > 0.001$ pe fiecare.
  - **(d)** Verificarea exactă a martorilor analitici din §3.1 (`VEC` pe $(6, 3)$: formulele raționale închise la $\le 10^{-13}$, `STAT`/`FERMI`/`U` dau $[1/2]^6$ și `[1, 2, 3]` pe $H_+$ și $H_-$, iar `VEC` separă probabilitățile și dă biletele `[2, 3, 4]` vs `[1, 3, 6]`) și §3.2 (`BLOC` pe $(7, 3, b=5)$: biletele `[1, 2, 3]` vs `[1, 6, 7]`).
- **Q2 — Predictibilitate („ca în ajun”):** pe o istorie sintetică $(49, 6)$ de lungime $T = 2000$, la $t_0 \in \{400, 1000, 1600\}$, înlocuirea extragerilor $\ge t_0$ lasă bit-identice log-probabilitățile și biletele pentru $t \le t_0$.
- **Q3 — Controlul sub nul (Ville):** câte $100$ de istorii uniforme pentru fiecare dintre cele 7 jocuri (`RO_649`, `RO_540`, `RO_joker`, `HU_otos`, `FR_loto`, `US_powerball`, `HU_hatos` la lungimile de dezvoltare din §4) și produsul `GLOBAL` străin: fracția cu $E \ge 20$ este $\le 0.10$ peste tot.
- **Q4 — Puterea pe semnal injectat de amestecare insuficientă** ($(49, 6)$, $T = 2384$, câte $20$ de istorii pe scenariu):
  - $\Sigma_{\text{VEC}+}$: `VEC(r=1)` cu $\beta = +0.35$ (atracție între numere consecutive);
  - $\Sigma_{\text{VEC}-}$: `VEC(r=1)` cu $\beta = -0.45$ (respingere între numere consecutive);
  - $\Sigma_{\text{BLOC}+}$: `BLOC(CONT, b=7)` cu $\beta = +0.25$ (atracție în același tub de 7 bile — marginale individuale exact uniforme $\pi_i \equiv 6/49$!);
  - $\Sigma_{\text{BLOC}-}$: `BLOC(MOD, b=10)` cu $\beta = -0.30$ (respingere pe aceeași coloană zecimală).
  **Poarta Q4:** `VEC` atinge $E \ge 1500$ în $\ge 16/20$ istorii sub $\Sigma_{\text{VEC}+}$ și $\Sigma_{\text{VEC}-}$; `BLOC` atinge $E \ge 1500$ în $\ge 16/20$ istorii sub $\Sigma_{\text{BLOC}+}$ și $\Sigma_{\text{BLOC}-}$; `COMB` atinge $E \ge 1500$ în $\ge 16/20$ istorii pe toate cele 4 scenarii. (Dacă o familie pică, este marcată `NOT_QUALIFIED` și exclusă ca în XI-P1 §5, fără reglaj de salvare.)
  **Descriptiv (curba de rezoluție P4c):** pe $(49, 6)$, $T = 2384$, câte 20 de istorii pentru `VEC(r=1)` și `BLOC(CONT, b=7)` la $\beta \in \{+0.05, +0.10, +0.15, +0.20, +0.30, -0.10, -0.20, -0.30\}$: fracția cu $E \ge 1500$, mediana $\log E$ și raportul $\mathbb{E}_\beta[A] / \mathbb{E}_U[A]$.
- **Q5 — Garda rezervei:** fără `SIGILIU_CONFIRMARE_P4.json` valid și cu supraviețuitori nevid, funcția de citire refuză cu `PermissionError` orice cale conținând `rezerva` sau `sigilat` (testat pe un director temporar sintetic).

După `PASS` pe Q1–Q5, codul (`xi/p4/p4.py` și `xi/p4/verifica_p4.py`) se sigilează în `xi/p4/SIGILIU_COD_P4.json` (fișiere `0444`) **înainte** de rularea pe dezvoltare.

---

## 6. Ordinea execuției și verificarea independentă

1. Sigilarea acestui protocol (`xi/SIGILIU_XI_P4.json`, `0444`).
2. Scrierea `xi/p4/p4.py` și `xi/p4/verifica_p4.py` (verificatorul nu importă nimic din `p4.py` sau `banca.py`; calculează constantele de normalizare și marginalele `VEC` prin spațieri interne exacte în $\mathbb{Z}$, iar pentru `BLOC` prin histograme 2D întregi de ocupare–perechi în $\mathbb{Z}$, verificând toate log-probabilitățile la $\le 10^{-8}$ pe pas și $\le 10^{-6}$ pe $\log E$ agregat, biletele cu toleranța de graniță $10^{-9}$, nimeririle, p-valorile hipergeometrice exacte, jumătățile, produsul global și Holm).
3. Calificarea `p4.py teste` $\implies$ `xi/rezultate/P4/calificare/CALIFICARE_P4_<UTC>.json` (`PASS`).
4. Sigilarea codului `xi/p4/SIGILIU_COD_P4.json` (`0444`).
5. Dezvoltarea unică `p4.py dezvoltare` (pe RO + cele 4 arhive străine `dev.json`; refuză repetarea) $\implies$ `xi/rezultate/P4/p4_dev_pas.jsonl`, `P4_DEV_REZULTATE.json`, `RAPORT_P4_DEV_CIFRE.md` (`0444`).
6. Verificarea independentă `verifica_p4.py dev` $\implies$ `VERIFICARE_P4_DEV.json` (`PASS`).
7. Dacă există supraviețuitori străini: `SIGILIU_CONFIRMARE_P4.json` $\to$ o singură rulare `p4.py confirmare` pe `rezerva.json` $\to$ `verifica_p4.py rez`; altfel rezervele rămân sigilate și necitite (`SIGILIU_CONFIRMARE_P4.json` cu listă goală, iar `p4.py confirmare` refuză citirea rezervei).
8. Raportul final `xi/rezultate/P4/RAPORT_P4.md` (`0444`).

---

## 7. Interpretări fixate

- Nicio respingere pe dezvoltarea străină (și nicio respingere pe RO) $\implies$ **`P4_NICIUN_SUPRAVIETUITOR`**: *„nici pe arhiva României, nici pe cele 4 arhive străine oficiale, modelele de amestecare insuficientă (vecinătate numerică și blocuri/coloane de încărcare, atracție sau respingere) nu bat uniformul”*, cu rezoluția publicată; rezervele oarbe `rezerva.json` rămân sigilate și necitite.
- Respingere pe dezvoltarea străină și respingere Holm pe `rezerva.json` $\implies$ **`CONFIRMAT_PE_ARHIVA`** (conform `AMENDAMENT_V12_01`): intră în C3 și pe ecran cu eticheta exactă *„confirmat pe arhivă (test orb), neconfirmat prospectiv”*, cu raportarea câștigului așteptat calculat și `positive_claims_allowed=false` (fără promisiune de profit).
- Respingere pe dezvoltarea străină fără respingere pe `rezerva.json` $\implies$ **`P4_NECONFIRMAT_PE_REZERVA`** (supraviețuitorul cade la testul orb).
- Respingere numai pe RO fără supraviețuitor străin $\implies$ **`P4_CANDIDAT_RO_NECONFIRMAT_ORB`** (arhiva RO nu are rezervă oarbă; rezervele străine nu se deschid).

Precedente atribuite: modelele Gibbs / Ising pe rețea finită cu număr fix de particule (gaz pe rețea în ansamblul canonic), distribuțiile exponențiale pe partiții de mulțimi, evaluarea prequențială și mixturile bayesiene (Dawid 1984), inegalitatea lui Ville (1939) și combinarea e-valorilor prin produs (Vovk & Wang 2021). Fără noutate matematică mondială sau avantaj cuantic revendicate.
