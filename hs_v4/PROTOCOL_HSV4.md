# PROTOCOL PREÎNREGISTRAT — `HS-V4` (Bosonic Hubbard–Stratonovich Deconvolution, Exogenous Aero-Physical Coupling, Spectral Bitwise/Modular RNG Detector & Bayesian Abstention Portfolio)

- **Versiune:** `HSV4-P1` (scris și sigilat SHA-256 cu permisiuni `0444` în `hs_v4/SIGILIU_PROTOCOL_HSV4.json` ÎNAINTE de orice fișier de cod `hs_v4/*.py` și ÎNAINTE de orice descărcare ori citire de arhive).
- **Încadrare epistemică:** Calcul clasic exact în `float64` pe GPU (CUDA / PyTorch) și CPU; transformarea bosonică Hubbard–Stratonovich, deconvoluția tensorială Jennrich, termodinamica aerului umed, analiza spectrală bitwise/modulară și portofoliul Bayesian cu martingală de test sunt **strict matematice și fizico-statistice**, fără hardware cuantic, fără afirmații comerciale/contabile și fără promisiuni de câștig. `positive_claims_allowed = false`.
- **Izolare strictă:** Nu se ating `app.py`, `engine.py`, `parser.py`, `tu3/*`, `tu4/*`, `pl_v3/*`, pistele închise `*649/` și nu se citesc niciodată fișierele oarbe `0400` din `xi/date_p2/*/rezerva.json`.

---

## 1. Constante Fixate A Priori (Zero Tuning Post-Hoc)

- **Rang subspațiu bosonic latent (`O1`):** $R = 3$; orizont EMA momente de ordin $1, 2, 3$: $\tau_{\text{bos}} = 160.0$ pași ($\rho_{\text{bos}} = \exp(-1/160)$); orizonturi câmp local intrinsec: $\tau_{\text{int}} = (16.0, 64.0, 256.0)$ cu ponderi $(0.50, 0.30, 0.20)$; cuplaj bipartit secundar (ex. Joker $45 \times 20$): $\tau_J = 128.0$, $\kappa_J = 0.50$.
- **Cuplaj aero-fizic exogen (`O2`):** coordonate București $44.43^\circ\text{N}, 26.10^\circ\text{E}$ la ora extragerii `18:00 Europe/Bucharest`; regularizare ridge online $\lambda_{\text{aero}} = 24.0$, factor de uitare cauzal $\rho_{\text{aero}} = \exp(-1/256)$, prag de winsorizare standardizare cauzală $z_{\max} = 4.0$ (după minimum $s_{\text{warm}} = 5$ pași).
- **Detector spectral bitwise / congruență modulară RNG (`O4`):** regularizare ridge online $\lambda_{\text{rng}} = 16.0$, factor de uitare cauzal $\rho_{\text{rng}} = \exp(-1/192)$; lățimi de biți pentru bias de respingere incompletă $b \in \{6, 7, 8\}$ ($2^b \bmod N$); module prime $p \in \{3, 5, 7\}$.
- **Portofoliu Bayesian cu abținere (`O3`):** $M = 8$ experți, unde $m = 0$ este exact legea uniformă $(\eta_0, \gamma_0) = (0, 0)$ cu masă a priori $w_0^{(0)} = 0.50$; repulsie multiplet ortogonal Coulomb–Jastrow $\gamma_{\text{Jastrow}} = 0.50$ pe bazinul top-$2048$; ordin cvadratură Gauss–Hermite $M_{\text{GH}} = 16$ noduri/axă ($16^3 = 4096$ noduri în $\mathbb{R}^3$).

---

## 2. Definirea Exactă a Operatoarelor `O1`–`O4`

### 2.1. `O1` — Deconvoluția Bosonică Hubbard–Stratonovich a Valizelor Latente
Pentru un joc cu urnă principală $N$, mărime extragere $r$ și mărime variantă $k$ (în RO: `649` cu $N=49, r=6, k=6 \Rightarrow 13\,983\,816$ stări; `540` cu $N=40, r=6, k=5 \Rightarrow 658\,008$ stări; `joker` cu $N=45, r=5, k=5$ și urnă secundară $M_J=20, r_J=1 \Rightarrow 24\,435\,180$ stări; dacă $\binom{N}{k} > 5 \times 10^7$, ex. `Pick 10` $10/80$, evaluarea $Z_{\text{HS}}$ și a marginalelor se face exact prin transformarea Hubbard–Stratonovich Gauss–Hermite + $e_k$):
1. Fie $\bar{x}_t \in [0, 1]^N$ media indicatorilor extragerilor din pasul calendaristic $t$ ($\sum_i \bar{x}_{t,i} = r$, invariantă la ordinea din zilele cu extragere dublă din `step_offsets`). Se mențin cauzal momentele exponențiale $M_1^{(s)} \in \mathbb{R}^N$, $M_2^{(s)} \in \mathbb{R}^{N \times N}$ și tensorul simetric de ordin 3 al tripletelor distincte din aceeași extragere $M_{3,\text{dist}}^{(s)} \in \mathbb{R}^{N \times N \times N}$ ($M_{3,\text{dist},ijk} = 0$ dacă $i=j$, $j=k$ sau $i=k$).
2. Cu proiectorul de sumă nulă $P_\perp = I_N - \frac{1}{N}\mathbf{1}_N\mathbf{1}_N^T$ și varianța hipergeometrică nulă pe mod $\sigma_0^2 = \frac{r(N-r)}{N(N-1)}$, matricea cauzală de co-apariții de-biasată hipergeometric și adimensională este:
   $$C^{(s)} = P_\perp \left(\frac{M_2^{(s)} - M_1^{(s)} M_1^{(s)T}}{\sigma_0^2} - P_\perp\right) P_\perp.$$
3. Se extrag cele mai mari $R=3$ valori proprii $(\lambda_1, \lambda_2, \lambda_3)$ și vectorii proprii ortonormați $U_R = [u_1, u_2, u_3] \in \mathbb{R}^{N \times 3}$ ai lui $C^{(s)}$, cu partea pozitivă atenuată lin la eșantioane mici $\tilde{\lambda}_r^+ = \frac{n_{\text{eff}}^{(s)}}{n_{\text{eff}}^{(s)} + 32.0} \max(\lambda_r, 0)$.
4. **Deconvoluția spectrală Jennrich $O(R)$-echivariantă:** Tensorul de ordin 3 de-biasat hipergeometric $T_{ijk}^{(s)} = \big(M_{3,\text{dist},ijk}^{(s)} - \frac{r(r-1)(r-2)}{N(N-1)(N-2)}\big)\mathbf{1}_{i \neq j \neq k}$ se proiectează în subspațiul $U_R$: $\mathcal{G}_{abc} = \sum_{i,j,k} T_{ijk}^{(s)} U_{ia} U_{jb} U_{kc}$. Vectorul urmă intrinsec $\xi_a = \sum_{b=1}^R \mathcal{G}_{abb}$ este $O(R)$-covariant (zero numere aleatoare); dacă $\|\xi\|_2 > 10^{-12}$, matricea simetrică Jennrich $S_{\text{Jen}} = \sum_{c=1}^R \frac{\xi_c}{\|\xi\|_2} \mathcal{G}_{:,:,c}$ se diagonalizează ortogonal $S_{\text{Jen}} = Q_{\text{Jen}} \text{diag}(\nu) Q_{\text{Jen}}^T$ ($Q_{\text{Jen}} \in O(R)$), altfel $Q_{\text{Jen}} = I_R$. Direcțiile deconvoluate sunt $W_{\text{Jen}}^{(s)} = U_R Q_{\text{Jen}}$, iar subspațiul bosonic ponderat este:
   $$V_s = [v_s^{(1)}, \dots, v_s^{(R)}] = \sqrt{\frac{N}{k}} \, U_R \, \text{diag}\!\big(\sqrt{\tilde{\lambda}_1^+}, \dots, \sqrt{\tilde{\lambda}_R^+}\big) Q_{\text{Jen}}.$$
   Deoarece $Q_{\text{Jen}} Q_{\text{Jen}}^T = I_R$, forma pătratică $\sum_{r=1}^R (v_s^{(r)T} \mathbf{1}_\sigma)^2 = \mathbf{1}_\sigma^T (V_s V_s^T) \mathbf{1}_\sigma$ este exact invariantă la semnele vectorilor proprii și echivariantă $S_N$ la precizie mașină.
5. **Ponderea bosonică Hubbard–Stratonovich ($\gamma \ge 0$):**
   $$W_{\text{HS}}(\sigma \mid \eta, \gamma) = \exp\!\left(\eta\, h_s^T \mathbf{1}_\sigma + \frac{\gamma}{2} \sum_{r=1}^R \big(v_s^{(r)T} \mathbf{1}_\sigma\big)^2\right).$$
   Pentru jocuri bipartite $N \times M_J$ (ex. `joker` $45 \times 20$), cu matricea de-biasată de co-apariții încrucișate $J_s \in \mathbb{R}^{N \times M_J}$ și modurile cuplate $u_{s,b}^{(r)} = \kappa_J (J_s^T v_s^{(r)})_b$:
   $$W_{\text{HS}}(\sigma, b \mid \eta, \gamma) = \exp\!\left(\eta\big(h_s^T \mathbf{1}_\sigma + h_{J,s,b} + J_{s,:,b}^T \mathbf{1}_\sigma\big) + \frac{\gamma}{2}\sum_{r=1}^R \big(v_s^{(r)T}\mathbf{1}_\sigma + u_{s,b}^{(r)}\big)^2\right).$$
   Prin identitatea integrală exactă Hubbard–Stratonovich în $\mathbb{R}^R$, funcția de partiție $Z_{\text{HS}}(\eta, \gamma) = \sum_\sigma W_{\text{HS}}(\sigma \mid \eta, \gamma)$ este egală analitic cu integrala Gauss–Hermite a polinoamelor simetrice elementare $e_k$:
   $$Z_{\text{HS}}(\eta, \gamma) = \frac{1}{\pi^{R/2}} \int_{\mathbb{R}^R} e^{-\|x\|_2^2} \, e_k\!\Big(\exp\!\big(\eta h_s + \sqrt{2\gamma}\, V_s x\big)\Big) d^R x.$$
6. **Multipletul ortogonal Jastrow $(\alpha, \beta, \gamma)$:** Din bazinul celor mai probabile $2048$ stări, se selectează determinist $(\sigma_\alpha, \sigma_\beta, \sigma_\gamma)$ maximizând $\sum_{u \in \{\alpha,\beta,\gamma\}} \ln P(\sigma_u) + \gamma_{\text{Jastrow}} \ln \det G$, unde $G_{uv} = |\sigma_u \cap \sigma_v| / k$ (cu fibră secundară distinctă la jocuri bipartite).

### 2.2. `O2` — Cuplaj Aero-Fizic Exogen București
1. Din seria orară ERA5 (`archive-api.open-meteo.com`, București `44.43°N, 26.10°E`, `18:00 Europe/Bucharest`) se extrag temperatura $T_C$ [$^\circ\text{C}$], presiunea la sol $P_{\text{hPa}}$ [$\text{hPa}$] și umiditatea relativă $\text{RH}$ [$\%$]. Cu presiunea de saturație Tetens–Magnus $p_{\text{sat}}(T_C) = 610.94 \exp\!\big(\frac{17.625\,T_C}{T_C + 243.04}\big)$ [$\text{Pa}$], presiunea parțială a vaporilor $p_v = \frac{\text{RH}}{100} p_{\text{sat}}(T_C)$, $R_d = 287.058\text{ J/(kg}\cdot\text{K)}$ și $R_v = 461.495\text{ J/(kg}\cdot\text{K)}$, densitatea aerului umed este:
   $$\rho_{\text{air}}(T_C, P_{\text{hPa}}, \text{RH}) = \frac{100 P_{\text{hPa}} - p_v}{R_d (T_C + 273.15)} + \frac{p_v}{R_v (T_C + 273.15)} \;\; [\text{kg/m}^3].$$
   Pentru orice dată unde reanaliza ERA5 prezintă latență la capăt de arhivă ori indisponibilitate, se aplică exclusiv un fallback determinist strict cauzal (climatologie armonică/persistență calculată strict din zilele $< d$), marcat explicit în `PROVENIENTA_METEO.json`.
2. Vectorul exogen $f_s^{\text{raw}} = (\rho_{\text{air}}(d_s), \text{RH}(d_s), \Delta P_{24\text{h}}(d_s)) \in \mathbb{R}^3$ este standardizat strict cauzal cu algoritmul Welford doar pe pașii $0 \dots s-1$, obținând $z_s^{\text{met}} \in [-4, 4]^3$ ($z_s^{\text{met}} = \mathbf{0}$ pentru $s < 5$).
3. Regresia ridge online cauzală menține $G_{\text{aero}}^{(s)} = \sum_{t=0}^{s-1} \rho_{\text{aero}}^{s-1-t} z_t^{\text{met}} (z_t^{\text{met}})^T \in \mathbb{R}^{3 \times 3}$ și $B_{\text{aero}}^{(s)} = \sum_{t=0}^{s-1} \rho_{\text{aero}}^{s-1-t} z_t^{\text{met}} (\bar{x}_t - \frac{r}{N}\mathbf{1}_N)^T \in \mathbb{R}^{3 \times N}$, proiectând câmpul zero-sum $S_N$-echivariant $\tilde{h}_s^{\text{aero}} = B_{\text{aero}}^{(s)T} (\lambda_{\text{aero}} I_3 + G_{\text{aero}}^{(s)})^{-1} z_s^{\text{met}}$, scalat RMS lin la $h_s^{\text{aero}}$. Canalul este activ pe suflante mecanice și servește drept control negativ pe fluxurile pur electronice RNG.

### 2.3. `O4` — Canal Spectral Bitwise / Congruență Modulară pentru Extrageri Electronice Online (RNG)
1. Pentru indicele zero-based $u = i - 1 \in \{0, \dots, N-1\}$ ($B_{\text{bits}} = \lceil \log_2 N \rceil$ biți), la pasul $s$ se construiește dicționarul cauzal $\Psi_s \in \mathbb{R}^{N \times d_{\text{rng}}}$ ale cărui coloane sunt exact centrate pe urnă ($\sum_{u=0}^{N-1} \Psi_{s,u,m} = 0$, deci medie exact nulă sub orice CSPRNG/lege uniformă pentru orice $N$):
   - profilurile teoretice de modulo la respingere incompletă $\mathbf{1}_{u < (2^b \bmod N)}$ pentru $b \in \{6, 7, 8\}$;
   - indicatorii reziduurilor prime $u \bmod p$ și tranzițiile de stare din pasul $s-1 \to s$ pe clasele $u \bmod p$ pentru $p \in \{3, 5, 7\}$;
   - biții binari $(2\,\text{bit}_\ell(u) - 1)$ și tranzițiile bitwise XOR față de pasul $s-1$: $(2\,\text{bit}_\ell(u) - 1)\cdot \bar{b}_{s-1,\ell}$ pentru $\ell \in \{0, \dots, B_{\text{bits}}-1\}$;
   - paritatea Hamming statică $(-1)^{\text{popcount}(u)}$ și tranziția de paritate Hamming față de pasul $s-1$.
2. Regresia ridge online cauzală $A_{\text{rng}}^{(s)} = \lambda_{\text{rng}} I + \sum_{t=0}^{s-1} \rho_{\text{rng}}^{s-1-t} \Psi_t^T \Psi_t$, $b_{\text{rng}}^{(s)} = \sum_{t=0}^{s-1} \rho_{\text{rng}}^{s-1-t} \Psi_t^T (\bar{x}_t - \frac{r}{N}\mathbf{1}_N)$ produce câmpul spectral electronic $\tilde{h}_s^{\text{rng}} = \Psi_s (A_{\text{rng}}^{(s)})^{-1} b_{\text{rng}}^{(s)}$, scalat RMS lin la $h_s^{\text{rng}}$.

### 2.4. `O3` — Portofoliu Universal Bayesian cu Masă Punctuală de Abținere ($w_0 = 0.50$)
Grila fixată de $M = 8$ experți $(m = 0 \dots 7)$ cu ponderi a priori $w^{(0)}$ ($\sum_{m=0}^7 w_m^{(0)} = 1$):
- `m=0` (`Abținere / Uniform`): $h=0, \eta=0.00, \gamma=0.00$, prior **$w_0^{(0)} = 0.50$**;
- `m=1` (`O1 Bosonic Mild`): $h=0, \eta=0.00, \gamma=0.35$, prior $0.10$;
- `m=2` (`O1 Bosonic Strong`): $h=0, \eta=0.00, \gamma=0.75$, prior $0.08$;
- `m=3` (`O1 Intrinsec+Bosonic`): $h=h_s^{\text{int}}, \eta=0.35, \gamma=0.40$, prior $0.08$;
- `m=4` (`O2 Aero-Fizic Pur`): $h=h_s^{\text{aero}}, \eta=0.45, \gamma=0.00$, prior $0.06$;
- `m=5` (`O1+O2 Mecanic Cuplat`): $h=\frac{h_s^{\text{int}} + h_s^{\text{aero}}}{\sqrt{2}}, \eta=0.40, \gamma=0.45$, prior $0.06$;
- `m=6` (`O4 Electronic RNG Mild`): $h=h_s^{\text{rng}}, \eta=0.45, \gamma=0.00$, prior $0.06$;
- `m=7` (`O4 Electronic RNG Strong`): $h=h_s^{\text{rng}}, \eta=0.95, \gamma=0.00$, prior $0.06$.

Dacă un subcanal este dezactivat în ablație sau în nucleul mecanic pur (`enable_o4=False`), masa $w_0^{(0)} = 0.50$ rămâne neschimbată, iar restul de $0.50$ se redistribuie proporțional între experții activi. Cu raportul exact de verosimilitate pe pas $L_m^{(s)}(D_s) = \prod_{D \in \text{pas } s} \frac{\binom{N}{k}}{\binom{r}{k}} \sum_{\sigma \subset D, |\sigma|=k} P_m^{(s)}(\sigma)$ (unde $L_0^{(s)} \equiv 1$ și $\mathbb{E}_{\text{unif}}[L_m^{(s)} \mid \mathcal{F}_{s-1}] = 1$), averea fiecărui expert evoluează exact prin $W_m^{(s+1)} = W_m^{(s)} L_m^{(s)}$. Deoarece $E_S = \prod_{s} \sum_{m=0}^{M-1} w_m^{(s)} L_m^{(s)} = \sum_{m=0}^{M-1} W_m^{(S)} \ge W_0^{(S)} = 0.50$, **pragul $E_s \ge 0.50$ este garantat algebric pe orice traiectorie**, iar sub un QRNG/CSPRNG curat $w_0^{(s)} \to 1$.

---

## 3. Porți Sintetice (`Q1–Q6`), Walk-Forward RO (`G1–G6`) & Pachet Internațional / RNG Electronic

### 3.1. Calificare Tehnică & Algebrică în Sesiunea 1 (`Q1–Q6`, `6/6 PASS` obligatoriu fără citirea arhivei reale RO)
- **`Q1` (Exactitate Algebrică Hubbard–Stratonovich):** $|Z_{\text{GPU}} - Z_{\text{GH}}| / Z_{\text{GH}} < 10^{-12}$ între suma brută pe GPU și cvadratura Gauss–Hermite + $e_k$ în `float64`, plus $|\sum P(\sigma) - 1| < 10^{-12}$ pe toate stările din `649` ($13\,983\,816$), `540` ($658\,008$) și `joker` ($24\,435\,180$).
- **`Q2` (Exactitate Deconvoluție `O1` + Canal Electronic `O4`):** recuperarea direcțiilor latente cu cosinus $> 0.90$ prin deconvoluția Jennrich pe un amestec de valize cu marginale 1-corp plate $\approx r/N$, respectiv detectarea unui bias sintetic de modulo $2^b \bmod N$ în extrageri electronice ($w_{\text{O4}} > 0.80$, $E_S > 100$).
- **`Q3` (Echivarianță Exactă `O1–O2`):** echivarianță sub permutări $S_{49}$, $S_{40}$ și $S_{45} \times S_{20}$ pentru nucleul mecanic `O1–O2` ($\max|\Delta \pi| < 10^{-12}$, $|\Delta \ln Z| < 10^{-12}$, $\max|\Delta w_m| < 10^{-12}$ și bilet fundamental $\sigma_\alpha$ echivariant).
- **`Q4` (Cauzalitate Strictă):** invarianță la ordinea extragerilor din aceeași zi (`step_offsets` cu zile duble), zero scurgere din viitor în standardizarea meteo și în regresia online, și identitate `incremental == full` $< 10^{-12}$.
- **`Q5` (Martor de Separare Fizică — $Z=2$ Valize Alese cu Moneda $1/2$):** pe o istorie sintetică cu două valize opuse ($+\delta / -\delta$), reperele `B`, `R` și un model $k$-DPP respingător obțin $E_S \le 1$ (marginale 1-corp oarbe), în timp ce `HS-V4` obține $E_S > 1000$ ($\log_{10} E_S > 3$).
- **`Q6` (Martor de Siguranță sub Nul / CSPRNG + Multiplet Distinct):** pe univers sintetic pur uniform (CSPRNG curat), $E_s \ge 0.50$ pe toată traiectoria, creșterea masei de abținere $w_0^{(S)} > w_0^{(0)} = 0.50$, $\det G > 0$ pentru multipletul $(\alpha, \beta, \gamma)$ și $\sigma_\alpha$ distinct de `B` și `R`.

### 3.2. Porți Walk-Forward LIVE RO în Sesiunea 2 (`G1–G6`, `s = 100 .. S-1`, cu ablație pe canale)
Raportate onest `X / 6` pe `649`, `540` și `joker` (cu ablație `O1`, `O1+O2`, `O1+O4`, `Full HS-V4`):
- **`G1`:** Exces mediu de potriviri $\sigma_\alpha$ peste media hipergeometrică uniformă $\ge +0.20$;
- **`G2`:** $\text{Hits}(\text{HS-V4}) > \max(\text{Hits}(B), \text{Hits}(R))$;
- **`G3`:** $\text{LogScore}(\text{HS-V4}) > \max(\text{LogScore}(U), \text{LogScore}(B), \text{LogScore}(R))$;
- **`G4`:** $\text{Brier}(\text{HS-V4}) < \min(\text{Brier}(U), \text{Brier}(B), \text{Brier}(R))$;
- **`G5`:** $\text{LogScore}(\text{HS-V4}) > \text{LogScore}(B)$ în ambele jumătăți ale arhivei și pe ultimii $100$ pași;
- **`G6`:** Valoarea martingală a portofoliului Bayesian $E_S > 1.0$ (cu garanția structurală $E_S \ge 0.50$).

### 3.3. Pachetul Internațional & Extrageri Electronice Online (Sesiunea 2 `hs_v4/international.py` + Sesiunea 3 UI Tab Port `8649`)
Verificare walk-forward strict cauzală pe categorii oficiale câștigătoare (`3+`, `4+`, `5+`, `6/6`, `+Bonus`), curba $E_s$ și distribuția maselor Bayesiene $(w_0, w_{\text{O1}}, w_{\text{O2}}, w_{\text{O4}})$ pe două clase de arhive oficiale (fără atingerea `xi/date_p2/*/rezerva.json`):
1. **Loterii mecanice externe:** `FR Loto` ($5/49 + 1/10$), `HU Hatoslottó` ($6/45$), `HU Ötöslottó` ($5/90$), `US Powerball` ($5/69 + 1/26$).
2. **Extrageri electronice online oficiale (RNG / e-Draw):** `FDJ EuroDreams` ($6/40 + 1/5$ electronic), `HU Skandináv Lottó` ($7/35$ — comparație directă tragerea electronică RNG vs. tragerea mecanică pe aceeași urnă), `US NY Open Data` (`Take 5` $5/39$, `Cash4Life` $5/60 + 1/4$, `Pick 10` $10/80$ electronic online), cu `O2` rulat și ca martor de control negativ pe fluxurile pur electronice.
