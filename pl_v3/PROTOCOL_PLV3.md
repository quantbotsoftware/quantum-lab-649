# PROTOCOL PREÎNREGISTRAT — `PL-V3` (Dynamic SU(3) Yang-Mills Flow, Hodge Curl & Fermionic Determinantal Engine)

- **Versiune:** `PLV3-P1` (scris și sigilat SHA-256 în `SIGILIU_PROTOCOL_PLV3.json` ÎNAINTE de orice cod `pl_v3/*.py` și de orice evaluare pe arhivă).
- **Încadrare:** Calcul clasic pe GPU (CUDA / PyTorch) și CPU; structurile $\text{SU}(3)$, Yang–Mills, Bochner, Hodge–de Rham, sticlă de spin ultrametrică și procese determinantale sunt **strict matematice**, fără hardware cuantic, fără avantaj cuantic și fără promisiuni de câștig. `positive_claims_allowed = false`. Zero metrici comerciale/contabile.
- **Surse (read-only):** `tu3/parser_multi.py` (`build_game_dataset(mode, "live")`) peste `tu3/date/live/CURRENT_LIVE.json`:
  - `"649"`: $N=49, r=6, k=6$ ($\binom{49}{6} = 13.983.816$ stări);
  - `"540"`: $N=40, r=6$ bile extrase, $k=5$ pe variantă ($\binom{40}{5} = 658.008$ stări);
  - `"joker"`: $N=45, r=5, k=5$ cuplat cu urna secundară $M=20, r_J=1$ ($\binom{45}{5} \times 20 = 24.435.180$ stări).
  - Grupare strictă pe pași calendaristici `step_offsets` (extragerile din aceeași zi primesc aceeași distribuție pre-zi).

## 1. Constante Fixate A Priori (Fără Tuning)

- Orizonturi exponențiale noduri: $\tau_{\text{horiz}} = (16.0, 64.0, 256.0)$; co-apariții $\tau_{\text{co}} = 48.0$; transfer Ruelle $\tau_R = 96.0$ pe lag-uri $L \in (1, 2, 3, 5)$ cu ponderi $(0.45, 0.25, 0.18, 0.12)$.
- Impuls neabelian $\text{SU}(3)$: $\varepsilon_0 = \frac{\pi}{8\sqrt{r}}$; rată de curgere Yang–Mills adaptivă $\gamma_s = 0.02 + 0.10 \cdot \min(1, \sqrt{\text{JSD}(\rho_{16}, \rho_{256}) / \ln 2})$.
- Timp termic Bochner $\tau_B = 0.35$; scară kernel determinantal $\beta_K = 0.75$; temperatură bipartită Joker $\beta_J = 0.85$; cuplaj fază Cartan–Ruelle $\lambda_{\text{CS}} = 0.25$; repulsie multiplet Coulomb–Jastrow $\gamma_{\text{Jastrow}} = 0.50$.

## 2. Arhitectura Celor 5 Operatori

1. **O1 — Curgere Yang–Mills Lüscher–Morningstar–Peardon & Integrator Palindromic Strang pe $\text{SU}(3)$:**
   - La pasul $s$, legăturile $U_{ij}(s) \in \text{SU}(3)$ evoluează gauge-covariant prin suma de capse triunghiulare $\Sigma_{ij} = \frac{1}{N-2}\sum_{k \neq i,j} U_{ik} U_{kj}$, forța $\mathfrak{su}(3)$ fără urmă $F_{ij}^{\text{YM}} = \text{proj}_{\mathfrak{su}(3)}\!\big(\frac{i}{2}(\Omega_{ij}^\dagger - \Omega_{ij})\big)$ cu $\Omega_{ij} = \Sigma_{ij} U_{ij}^\dagger$ și pasul $U_{ij}^{\text{flow}} = \exp(i \gamma_s F_{ij}^{\text{YM}}) U_{ij}$.
   - Perechile co-extrase la pasul $s$ primesc impulsul $\Delta U_{ij}(s) = \exp(i \varepsilon_0 \sigma_{ij}(s) \Lambda_{a+1})$ în canalul $a = n_{ij}(s^-) \bmod 8$, cu orientarea intrinsecă $\sigma_{ij}(s) = \text{sign}(g_j(s^-) - g_i(s^-))$ (tie-break $\text{sign}(c_j(s^-) - c_i(s^-))$, altfel $0$), aplicat palindromic: $U_{ij}(s+1) = \Delta U_{ij}(s)^{1/2} U_{ij}^{\text{flow}} \Delta U_{ij}(s)^{1/2}$.
2. **O2 — Descompunerea Coomologică Exactă Helmholtz–Hodge pe $\mathcal{K}_N$:**
   - Produse scalare adimensionale $W_0, W_1, W_2$, codiferențiale $\delta_1 = W_0^{-1} B_1 W_1$, $\delta_2 = W_1^{-1} B_2 W_2$.
   - Din curentul antisimetric de tranziție Ruelle $J \in C^1(\mathcal{K}_N)$, rezolvă $(B_1 W_1 B_1^T)\phi = B_1 W_1 J$ ($\sum \phi_i = 0$), extrage $J_{\text{exact}} = B_1^T \phi$, $J_{\text{curl}} = J - J_{\text{exact}} \in \ker(\delta_1)$ și vorticitatea de 3 corpuri $\Omega_{\text{curl}} = B_2^T J_{\text{curl}} \in C^2(\mathcal{K}_N)$.
3. **O3 — Propagatorul Termic Bochner & Kernelul Determinantal Gauge-Invariant $K \in \mathbb{C}^{N \times N}$:**
   - Laplacianul Magnetic Bochner $(\Delta_A \psi)_i = \sum_j w_{1,ij}(\psi_i - U_{ij}\psi_j)$, nucleul termic $\mathcal{G}(\tau_B) = \exp(-\tau_B \Delta_A) \in \mathbb{C}^{3N \times 3N}$.
   - Suprapunerea gauge-invariantă $T_{ij} = \frac{1}{3}\text{Tr}_{\mathbb{C}^3}(\mathcal{G}_{ij}(\tau_B) U_{ij}^\dagger)$, matricea hermitiană $M_{ij} = \sqrt{\rho_i^{\text{emp}} \rho_j^{\text{emp}}} T_{ij} + \phi_i \delta_{ij}$ (scalată cu norma spectrală $\|M\|_2$) și kernelul pozitiv-definit $K = \exp(\beta_K M / \max(\|M\|_2, 10^{-8}))$.
4. **O4 — Ultrametrica de Sticlă de Spin (`int64`) & Operatorul Bipartit $\mathcal{H}_{45} \otimes \mathcal{H}_{20}$ la Joker:**
   - Dendrogramă single-linkage pe disimilaritatea $D_{ij} = 1 - |T_{ij}| / \sqrt{T_{ii} T_{jj}}$ cu lungimi exacte de ramură $\Delta h(u) = h(\text{parent}(u)) - h(u) \ge 0$ codificate în mască `int64` ($N-1 \le 48$ biți) + 3 tabele LUT pe 16 biți pentru tăietura Steiner $S_{\text{SG}}(\sigma)$ (scalată cu $h_{\text{root}}$).
   - La Joker: Hamiltonian cuplat $\hat{H}_{45 \otimes 20}$ ($900 \times 900$), stare Gibbs $\hat{\rho}_{45 \otimes 20}$, entropie Von Neumann $S_{\text{vN}}(\hat{\rho}_{20})$ și cuplaj de fază Cartan orientat intrinsec $\tilde{\Theta}_f = \text{sign}(\Omega_{\text{curl}}(f)) \Theta_f$ cu faza proprie Ruelle $\vartheta_b$ a urnei $1/20$.
5. **O5 — Cholesky Despachetat $k \times k$, `Online Log-Sum-Exp` & Multipletul Jastrow $(\alpha, \beta, \gamma)$:**
   - Log-ponderea canonică $\ln \mathcal{W}(\sigma) = \ln \det(K_{\sigma,\sigma}) - \frac{1}{\sqrt{\binom{k}{3}}}\sum_{f \subset \sigma} |\Omega_{\text{curl}}(f)| - \frac{1}{k} S_{\text{SG}}(\sigma)$ (plus termenul bipartit Joker).
   - Normalizare exactă $\ln Z = \ln \sum_\sigma \mathcal{W}(\sigma)$ și marginale $\pi_i = \sum_{\sigma \ni i} P(\sigma)$ în `float64` prin Online Log-Sum-Exp; multiplet $(\sigma_\alpha, \sigma_\beta, \sigma_\gamma)$ ales din top 2048 prin maximizarea $\sum_{u} \ln P(\sigma_u) + \gamma_{\text{Jastrow}} \ln \det G$.

## 3. Porți de Calificare Tehnică (`Q1–Q6`) și Walk-Forward pe Arhivă (`G1–G6`)

- **Calificare (`6/6` obligatoriu pe martori sintetici/algebrici înainte de backtest):**
  - `Q1` Identitatea Cauchy–Binet pe toate cele $13.983.816$ stări ($N=49, k=6$): $|Z_{\text{GPU}} - e_6(\lambda(K))| / e_6(\lambda(K)) < 10^{-11}$.
  - `Q2` Ortogonalitatea Pitagora–Hodge: $|\langle J_{\text{exact}}, J_{\text{curl}}\rangle_{W_1}| / \|J\|_{W_1}^2 < 10^{-13}$ și $\|\delta_1 J_{\text{curl}}\|_\infty < 10^{-13}$.
  - `Q3` Invarianța gauge locală $\text{SU}(3)$ ($U' = \Omega U \Omega^\dagger$) și independența de fazele `eigh`: $\max|\Delta K| < 10^{-12}$, $\max|\Delta \pi| < 10^{-12}$.
  - `Q4` Echivarianța exactă la permutarea bilelor $S_N$ (și $S_{45} \times S_{20}$ la Joker): $\max|\pi(\sigma H) - \sigma \pi(H)| < 10^{-11}$.
  - `Q5` Cauzalitate strictă pe `step_offsets` și identitate rulare incrementală vs. completă: $\max|\Delta U| < 10^{-12}$, $\max|\Delta K| < 10^{-12}$.
  - `Q6` Multiplet Jastrow ortogonal ($\det G > 0$) distinct de reperele marginale `B` și recență `R`.
- **Walk-Forward pe Arhiva LIVE (`s = 100 .. S-1`, raportat onest `X / 6`):**
  - `G1`: Exces potriviri $\sigma_\alpha$ peste media hipergeometrică uniformă $\ge +0.20$;
  - `G2`: $\text{Hits}(\text{PL-V3}) > \max(\text{Hits}(B), \text{Hits}(R))$;
  - `G3`: $\text{LogScore}(\text{PL-V3}) > \max(\text{LogScore}(U), \text{LogScore}(B), \text{LogScore}(R))$;
  - `G4`: $\text{Brier}(\text{PL-V3}) < \min(\text{Brier}(U), \text{Brier}(B), \text{Brier}(R))$;
  - `G5`: $\text{LogScore}(\text{PL-V3}) > \text{LogScore}(B)$ în ambele jumătăți ale arhivei și pe ultimii 100 pași;
  - `G6`: Martingala defensivă Ville $E_S = \prod_{s=100}^{S-1} \big(0.5 + 0.5 \cdot \frac{P_s(D_s)}{U(D_s)}\big) > 1.0$.
