# PROTOCOL PREÎNREGISTRAT — `KJ-V5` & `Rust Core v2` (Transport Spectral Neechilibru Johnson–Krawtchouk, Afinitate Ciclică Ireversibilă Koopman–Schnakenberg $V_2 \to V_2$ & Aplicația Nativă Tauri v2)

- **Protocol ID:** `KJV5-RCV2-P1`
- **Scris și sigilat SHA-256 (`0444`):** în `kj_v5/SIGILIU_PROTOCOL_KJV5.json` **ÎNAINTE** de existența directorului `./rust_core_v2/` (`code_files_present: []`, `results_present: false`) și **ÎNAINTE** de orice citire ori evaluare pe arhivele de extrageri.
- **Încadrare epistemică obligatorie:** Calcul clasic exact în `IEEE-754 binary64` (`f64` și `Complex64`) pe CPU multi-thread (`24` fire hardware, `AVX2` + `FMA` + `BMI2/POPCNT`). Structurile din schema de asociere Johnson $\mathcal{J}(N, k)$, polinoamele ortogonale hipergeometrice/Krawtchouk, operatorul de transport ireversibil Koopman pe subspațiul armonic $V_2$, curenții antisimetrici Schnakenberg și cvadratura Gauss–Hermite complexă sunt **strict matematice și fizico-statistice**, fără hardware cuantic, fără afirmații comerciale/contabile/bugetare și fără promisiuni de câștig. Variantele multipletului Coulomb–Jastrow $(\alpha, \beta, \gamma)$ și nucleul determinist sunt **minime de energie / stări statistice condiționate de istoric, NU predicții**. `positive_claims_allowed = false`.

---

## 1. Izolare Arhitecturală & Reguli de Integritate Pre-Cod

1. **Nucleul înghețat v1 rămâne 100% neatins (`frozen_hashes`):**
   - Toate cele `27` de fișiere `0444` din `./rust_core/` și binarul `./rust_core/target/release/rust-singularity-core` (`c20fdcd2f7f237578d1f0ea85c05f9bf6b32a888d228e4443b6756dd1d43fd9e`), împreună cu lansatorul `porneste_rust_core.sh` (`4e54add1…`), rămân nemodificate byte-cu-byte, astfel încât `tu4/s27/sonda_s27.py` (`G2`/`G3`) și `tu4/s34/verifica_publicarea_v2.py` (`DL_RC_V2=0`) să rămână permanent `PASS`.
   - Rămân de asemenea 100% neatinse: `app.py`, `engine.py`, `parser.py`, `validare.py`, `tu3/*`, `tu4/*`, `pl_v3/*`, `hs_v4/*`, `*649/*`, `xi/*`, `next_candidate/predictie_numere/*` și `next_candidate/quantum_limit/*`.
   - Fișierele oarbe `0400` din `xi/date_p2/*/rezerva.json` și `xi/date_p2/*/sigilat/*` **NU** sunt atinse sau citite niciodată.
2. **Crate-ul nou versionat și lansatorul autoadaptiv:**
   - Aplicația nativă Tauri v2 + motorul matematic Rust `KJ-V5` se dezvoltă în crate-ul nou `./rust_core_v2/` (`rust-singularity-core-v2` v2.0.0), compilat `--offline --release` cu `-C target-cpu=native`.
   - Artefactele protocolului, calificării sintetice `Q1–Q6`, evaluării walk-forward RO + Internațional/RNG, verificatorului independent Python și manifestul binarului v2 se scriu în `${QL649_ROOT:-.}/kj_v5/`, cu arhivă în oglindă `0444` pe `./ssd_data/RUST_CORE_V2_S01/`.
   - Noul lansator autoadaptiv `${QL649_ROOT:-.}/porneste_rust_core_v2.sh` (`0555`) este legat la pictograma existentă `~/Desktop/quantum-lab-649-rust-core.desktop` (și `~/.local/share/applications/quantum-lab-649-rust-core.desktop`), păstrând o copie byte-identică a fișierului `.desktop` v1 în `kj_v5/backup_desktop_v1/`.

---

## 2. Audit de Distinctitate Științifică al Pistei `KJ-V5`

`KJ-V5` testează o ipoteză fizico-algebrică netestată în niciuna dintre pistele închise (`predictie_numere/*`, `*649/`, `TU3 H1/H3`, `XI P1/P2/P4`, `PL-V3`, `HS-V4`): **histereza de neechilibru pe învelișurile Krawtchouk ale schemei de asociere Johnson $\mathcal{J}(N, k)$ și transportul ireversibil Koopman $V_2 \to V_2$ între perechi pure fără urmă marginală**.

| Familie precedentă | Observabilă / Mecanism | De ce este oarbă pe martorii `KJ-V5` (`Q2` și `Q3`) |
|---|---|---|
| `B`, `R`, `H1`, `H3`, `XI-P1/P2` (`STAT/DRIFT/GAP`) | Marginale de 1 corp și timpi de așteptare pe bile individuale | Pe martorii `Q2` și `Q3`, toate frecvențele 1-corp și tranzițiile 1-corp sunt exact plate ($r/N$). |
| `XI-P1/P2` (`FERMI`), `PG`, `CF`, `RH`, `LS`, `FS`, `XI-P4` | Interacții 2-corp / 3-corp statice în aceeași extragere ori vecinătate de etichetă | Invariante la inversarea săgeții timpului ($\mathcal{H}_+ \leftrightarrow \mathcal{H}_-$ au exact aceeași multi-mulțime de extrageri și matrice statică 2-corp izotropă). |
| `DL-649` (Lüders–Kraus Zeno), `AT`, `TP`, `MI`, `OC` | Populație diagonală proiectivă 1-corp sau transfer Markov 1-corp $i \to j$ | Pe ciclul chiral de cuplaje perfecte $K_4$ (`Q2`), matricea de tranziție 1-corp $P(a \in D_{t-1} \to b \in D_t)$ este identică și uniformă pe $\mathcal{H}_+$ și $\mathcal{H}_-$. |
| `PL-V3` ($\text{SU}(3)$ Yang–Mills + Hodge Curl + $k$-DPP) | Curent 1-corp Ruelle $J_{ij} \in C^1(\mathcal{K}_N)$ proiectat pe 2-fețe + $\det K$ repulsiv | Curentul 1-corp Ruelle $J_{ij}$ se anulează identic pe `Q2` ($J_{ij} \equiv 0$), iar `PL-V3` nu are nici potențial pe învelișuri Krawtchouk $m=2,3$, nici operator $V_2 \to V_2$. |
| `HS-V4` (`O1` Bosonic-Jennrich + `O2` ERA5 + `O4` Bitwise RNG) | Momente simetrice intra-extragere $(M_1, M_2, M_3)$, regresie meteo și dicționar 1-corp bitwise/modular | `O1` măsoară co-apariții intra-extragere invariante la permutarea ordinii temporale pe multi-mulțime egală; nu vede nici ciclul ireversibil $V_2 \to V_2$ (`Q2`), nici retenția pătratică de înveliș Krawtchouk $m=2$ la medie hipergeometrică fixă (`Q3`). |

---

## 3. Definirea Matematică Exactă a Operatorilor `K1`–`K4` (Constante Fixate A Priori, Zero Tuning)

Pentru un univers cu urnă principală $N \ge 4$, mărime extragere $r$, mărime variantă $k \le r$ și urnă secundară opțională $M_B$ ($r_B = 1$), extragerile din aceeași dată calendaristică $d_s$ sunt grupate în pasul $s \in \{0, \dots, S-1\}$ și ordonate canonic lexicografic după tuplul sortat al bilelor (invarianță `0.0` la ordinea intra-zi).
Fie $\bar{x}_s = \frac{1}{m_s}\sum_{d \in \text{pas } s} \mathbf{1}_{D_d} \in [0,1]^N$, $\tilde{x}_s = \bar{x}_s - \frac{r}{N}\mathbf{1}_N$, și matricea medie de perechi $\bar{P}_s = \frac{1}{m_s}\sum_{d \in \text{pas } s} P_{D_d}$ cu $(P_D)_{ij} = \mathbf{1}_{\{i,j\}\subset D}$ ($i \neq j$), $(P_D)_{ii}=0$.

Proiectorul ortogonal exact pe reprezentarea ireductibilă armonică $V_2$ ($S^{(N-2,2)}$, diagonală nulă și sume pe linii identic nule $\sum_{j=1}^N Q_{ij} = 0$, deci ortogonală atât pe $V_0$ cât și pe toate funcțiile marginale 1-corp din $V_1$) este:
$$(\Pi_{V_2}(P))_{ij} = P_{ij} - \frac{s_i + s_j}{N - 2} + \frac{S_{\text{tot}}}{(N - 1)(N - 2)} \;\; (i \neq j), \qquad (\Pi_{V_2}(P))_{ii} = 0, \qquad s_i = \sum_{j \neq i} P_{ij}, \;\; S_{\text{tot}} = \sum_{i=1}^N s_i.$$
Notăm $\Phi_s = \Pi_{V_2}(\bar{P}_s)$.

### 3.1. `K1` — Potențialul Învelișurilor Hipergeometrice / Krawtchouk pe $\mathcal{J}(N, k)$
- Sub legea uniformă, suprapunerea $u = |\sigma \cap D|$ dintre o mulțime fixată $|D|=r$ și $\sigma \sim \text{Unif}\binom{[N]}{k}$ urmează legea hipergeometrică exactă $p_0(u; N, r, k) = \binom{r}{u}\binom{N-r}{k-u} / \binom{N}{k}$ pe $\{u_{\min}, \dots, u_{\max}\}$, $u_{\min} = \max(0, k+r-N)$, $u_{\max} = \min(k, r)$.
- Prin ortogonalizare Gram–Schmidt a monomiilor $(1, u, u^2, u^3)$ în raport cu ponderea $p_0(u)$ (cu coeficient dominant al lui $u^m$ strict pozitiv, păstrând ordinele $m \in \{1, 2, 3\}$ cu normă reziduală $> 10^{-12}$), se construiesc bazele ortonormate exacte $\psi_m^{\text{draw}}(u)$ pentru $(N, r, r)$ și $\psi_m^{\text{tkt}}(u)$ pentru $(N, r, k)$ ($\mathbb{E}_{p_0}[\psi_m] = 0$, $\mathbb{E}_{p_0}[\psi_m \psi_{m'}] = \delta_{mm'}$).
- Cu orizontul $\tau_{\text{sh}} = 128.0$ ($\rho_{\text{sh}} = \exp(-1/128)$) și regularizarea $n_0^{\text{sh}} = 24.0$, la pasul $s \ge 2$:
  $$S_{\text{sh},m}^{(s)} = \sum_{t=1}^{s-1} \rho_{\text{sh}}^{s-1-t} \bar{\psi}_m^{(t)}, \qquad N_{\text{sh}}^{(s)} = \sum_{t=1}^{s-1} \rho_{\text{sh}}^{s-1-t}, \qquad c_m^{(s)} = 0.55\,\tanh\!\left(\frac{S_{\text{sh},m}^{(s)}}{N_{\text{sh}}^{(s)} + 24.0}\right),$$
  unde $\bar{\psi}_m^{(t)}$ este media perechilor $(D' \in \text{pas } t-1, D \in \text{pas } t)$ a lui $\psi_m^{\text{draw}}(|D \cap D'|)$. Potențialul de înveliș pe bilet este $\theta_u^{(s)} = \sum_{m=1}^{m_{\max}} c_m^{(s)} \psi_m^{\text{tkt}}(u)$ ($\theta_u^{(s)} = 0$ pentru $s < 2$).

### 3.2. `K2` — Transportul Ireversibil Koopman $V_2 \to V_2$ & Afinitatea Ciclică Antisimetrică
- Cu orizontul $\tau_{K2} = 160.0$ ($\rho_{K2} = \exp(-1/160)$) și regularizarea $\lambda_{K2} = 16.0$, la pasul $s \ge 2$, folosind identitatea exactă a produsului Frobenius $\langle \Phi_{t-1}, \Phi_{s-1}\rangle_F = \langle \bar{P}_{t-1}, \Phi_{s-1}\rangle_F$:
  $$\kappa_t^{\text{fwd}} = \langle \bar{P}_{t-1}, \Phi_{s-1}\rangle_F, \qquad \kappa_t^{\text{rev}} = \langle \bar{P}_t, \Phi_{s-1}\rangle_F, \qquad Z_{2,\text{eff}}^{(s)} = \lambda_{K2} + \sum_{t=1}^{s-1} \rho_{K2}^{s-1-t} \|\Phi_{t-1}\|_F^2,$$
  $$\widehat{Q}_{\text{dir}}^{(s)} = \Pi_{V_2}\!\left(\frac{1}{Z_{2,\text{eff}}^{(s)}} \sum_{t=1}^{s-1} \rho_{K2}^{s-1-t} \kappa_t^{\text{fwd}} \bar{P}_t\right), \qquad \widehat{Q}_{\text{anti}}^{(s)} = \Pi_{\perp \Phi_{s-1}}\!\left(\Pi_{V_2}\!\left(\frac{1}{Z_{2,\text{eff}}^{(s)}} \sum_{t=1}^{s-1} \rho_{K2}^{s-1-t} \frac{\kappa_t^{\text{fwd}} \bar{P}_t - \kappa_t^{\text{rev}} \bar{P}_{t-1}}{2}\right)\right),$$
  unde $\Pi_{\perp \Phi}(Q) = Q - \frac{\langle Q, \Phi\rangle_F}{\max(\|\Phi\|_F^2, 10^{-15})}\Phi$ impune identitatea exactă de algebră Lie antisimetrică $\langle \widehat{Q}_{\text{anti}}^{(s)}, \Phi_{s-1}\rangle_F \equiv 0$.
- Pentru $Q \in \{\widehat{Q}_{\text{anti}}^{(s)}, \widehat{Q}_{\text{dir}}^{(s)}\}$, scalarea netedă $O(N)$-invariantă este $\widetilde{Q} = \frac{2.5\,\tanh(4.0\|Q\|_F)}{\max(\|Q\|_F, 10^{-12})} Q$ ($0$ dacă $\|Q\|_F < 10^{-12}$), din care se extrag prin diagonalizare simetrică Jacobi în `f64` valoarea proprie maximal pozitivă $(\lambda_+, u_+)$ ($\lambda_+ = \max(\lambda_{\max}(\widetilde{Q}), 0)$) și valoarea proprie minimal negativă $(\lambda_-, u_-)$ ($\lambda_- = \min(\lambda_{\min}(\widetilde{Q}), 0)$), păstrând simetria exactă la inversarea semnului $\widetilde{Q} \mapsto -\widetilde{Q}$.

### 3.3. `K3` — Curentul Ireversibil Antisimetric Schnakenberg în $V_1$ & Cuplajul Bipartit Bonus/Joker
- Pe lag-urile $\ell \in \{1, 2, 3\}$ cu ponderi $(0.55, 0.30, 0.15)$, orizont $\tau_{K3} = 128.0$ ($\rho_{K3} = \exp(-1/128)$) și $\lambda_{K3} = 16.0$:
  $$C_{\to}^{(s)} = \frac{1}{\lambda_{K3} + \sum_{t=1}^{s-1} \rho_{K3}^{s-1-t}} \sum_{\ell=1}^3 w_\ell \sum_{t=\ell}^{s-1} \rho_{K3}^{s-1-t} \tilde{x}_{t-\ell} \tilde{x}_t^T, \qquad J_1^{(s)} = \frac{1}{2}\Big(C_{\to}^{(s)} - (C_{\to}^{(s)})^T\Big).$$
- Câmpul antisimetric centrat $\tilde{h}_s = (J_1^{(s)})^T \tilde{x}_{s-1} - \frac{1}{N}\mathbf{1}_N \mathbf{1}_N^T (J_1^{(s)})^T \tilde{x}_{s-1}$ se normează lin la $h_s^{\text{anti}} = \frac{\tilde{h}_s}{\max(\|\tilde{h}_s\|_2/\sqrt{N}, 10^{-12})}\tanh(\|\tilde{h}_s\|_2)$. Pentru jocurile cu urnă secundară $M_B \ge 2$, același operator antisimetric Schnakenberg + cuplajul direcționat $\tilde{x}_{s-1} \to \tilde{y}_s$ definește câmpul secundar $h_{B,s}^{\text{anti}} \in \mathbb{R}^{M_B}$ ($\sum_b h_{B,s,b}^{\text{anti}} = 0$).

### 3.4. `K4` — Funcția de Partiție Exactă (`Complex64` Gauss–Hermite 2D + Split-DP) & Portofoliul Bayesian ($w_0 = 0.50$)
- Pentru un expert $m$ cu parametri $(\eta_m, \gamma_{\text{sh},m}, \gamma_{2,m})$ și moduri $(\lambda_+, u_+), (\lambda_-, u_-)$, ponderea condiționată de o extragere $D \in \text{pas }(s-1)$ este:
  $$W_m(\sigma \mid D) = \exp\!\left(\gamma_{\text{sh},m} \theta_{|\sigma \cap D|}^{(s)} + \eta_m (h_s^{\text{anti}})^T \mathbf{1}_\sigma + \frac{\gamma_{2,m}}{2}\Big[\lambda_+ (u_+^T \mathbf{1}_\sigma)^2 + \lambda_- (u_-^T \mathbf{1}_\sigma)^2\Big]\right).$$
- Deoarece $\lambda_+ \ge 0$ și $\lambda_- \le 0$, transformarea integrală Gauss–Hermite în `Complex64` cu $M_{\text{GH}} = 14$ noduri pe axă ($14 \times 14 = 196$ noduri când ambele moduri sunt nenule; $14$ noduri când unul singur este nenul; $1$ nod când $\gamma_{2,m} = 0$) cu $\alpha_+ = \sqrt{2\gamma_{2,m}\lambda_+} \in \mathbb{R}$ și $i\alpha_- = i\sqrt{2\gamma_{2,m}|\lambda_-|} \in i\mathbb{R}$, combinată cu partiționarea $[N] = D \sqcup ([N]\setminus D)$ și polinoamele simetrice elementare prefix-sufix $e_u(z_D)\,e_{k-u}(z_{D^c})$, evaluează **exact în $O(N k)$** atât funcția de partiție $Z_m(D)$, cât și toate cele $N$ marginale $\pi_{m,i}(D)$ și suma restricționată $\sum_{\sigma \subset D_{\text{target}}, |\sigma|=k} W_m(\sigma \mid D)$ (inclusiv pentru `Pick 10` $10/80$ cu $\binom{80}{10} \approx 1.65 \times 10^{12}$ stări!).
- Grila fixată de $M = 8$ experți cu masă punctuală de abținere $w_0^{(0)} = 0.50$:
  - `m=0` (`Abținere / Uniform`): $\gamma_{\text{sh}}=0, \gamma_2=0, \eta=0$, prior **$w_0^{(0)} = 0.50$**;
  - `m=1` (`K1 Shell Mild`): $\gamma_{\text{sh}}=0.50, \gamma_2=0, \eta=0$, prior $0.08$;
  - `m=2` (`K1 Shell Strong`): $\gamma_{\text{sh}}=1.00, \gamma_2=0, \eta=0$, prior $0.07$;
  - `m=3` (`K2 Koopman V2 Antisimetric`): $\gamma_{\text{sh}}=0, \gamma_2=0.70$ pe $\widehat{Q}_{\text{anti}}^{(s)}$, $\eta=0$, prior $0.09$;
  - `m=4` (`K2 Koopman V2 Direcționat`): $\gamma_{\text{sh}}=0, \gamma_2=0.65$ pe $\widehat{Q}_{\text{dir}}^{(s)}$, $\eta=0$, prior $0.08$;
  - `m=5` (`K3 Schnakenberg V1`): $\gamma_{\text{sh}}=0, \gamma_2=0, \eta=0.50$ (+ secundar $\eta_B=0.50$), prior $0.06$;
  - `m=6` (`K1+K2 Cuplat Mild`): $\gamma_{\text{sh}}=0.55, \gamma_2=0.55$ pe $\frac{1}{2}(\widehat{Q}_{\text{anti}}^{(s)}+\widehat{Q}_{\text{dir}}^{(s)})$, $\eta=0$, prior $0.06$;
  - `m=7` (`Full KJ-V5 Strong`): $\gamma_{\text{sh}}=0.75, \gamma_2=0.75$ pe $\frac{1}{2}(\widehat{Q}_{\text{anti}}^{(s)}+\widehat{Q}_{\text{dir}}^{(s)})$, $\eta=0.45$ (+ $\eta_B=0.45$), prior $0.06$.
- La ablație (dezactivarea unuia sau mai multor canale `K1`, `K2`, `K3`), masa $w_0^{(0)} = 0.50$ rămâne fixă, iar $0.50$ se redistribuie proporțional între experții activi. Prin $W_m^{(s+1)} = W_m^{(s)} L_m^{(s)}$, **inegalitatea $E_s = \sum_{m=0}^{7} W_m^{(s)} \ge W_0^{(s)} = 0.50$ este garantată algebric pe orice traiectorie**. Multipletul $(\sigma_\alpha, \sigma_\beta, \sigma_\gamma)$ maximizează $\sum_{u \in \{\alpha,\beta,\gamma\}} \ln P_{\text{port}}(\sigma_u) + 0.50 \ln \det G$.

---

## 4. Porți de Calificare Pre-Arhivă (`Q1–Q6`, `6/6 PASS` Obligatoriu) & Porți Walk-Forward (`G1–G6`)

### 4.1. Calificare Sintetică și Algebrică Nativă în Rust (`Q1–Q6`, Zero Citiri de Arhive Reale)
1. **`Q1` (Exactitate Algebrică `Complex64` Gauss–Hermite 2D + Split-DP vs Enumerare Brută Completă):** pe toate cele $13\,983\,816$ stări din `649` ($49,6,6$), $658\,008$ stări din `540` ($40,6,5$) și $24\,435\,180$ stări din `joker` ($45,5,5 \times 20$) cu `K1 + K2 (ambele semne!) + K3` active simultan: $|Z_{\text{enum}} - Z_{\text{GH}}| / Z_{\text{enum}} < 10^{-12}$ și $\max_i |\pi_{\text{enum},i} - \pi_{\text{GH},i}| < 10^{-12}$, plus identitatea sumei restricționate pe `Pick 10` ($r=20, k=10$, $184\,756$ submulțimi) $< 10^{-12}$.
2. **`Q2` (Martor Chiral de Informație și Decizie la Inversarea Timpului — Ciclul de Cuplaje $K_4$, $\mathcal{H}_+$ vs $\mathcal{H}_-$):** pe $N=12, r=4, k=4$, două istorii chirale $\mathcal{H}_+$ ($M_1 \to M_2 \to M_3 \to M_1$) și $\mathcal{H}_-$ ($M_1 \to M_3 \to M_2 \to M_1$) cu exact aceeași multi-mulțime de extrageri, frecvențe 1-corp plate, matrice statică de perechi 2-corp izotropă, matrice Markov 1-corp plată și distribuție de suprapunere lag-1 identică produc $\widehat{Q}_{\text{anti}}(\mathcal{H}_+) = -\widehat{Q}_{\text{anti}}(\mathcal{H}_-)$ ($\|\widehat{Q}_{\text{anti}}(\mathcal{H}_+) + \widehat{Q}_{\text{anti}}(\mathcal{H}_-)\|_F < 10^{-13}$), bilete fundamentale distincte $\sigma_\alpha(\mathcal{H}_+) \neq \sigma_\alpha(\mathcal{H}_-)$ (și distincte de `B` și `R`) și $E_S > 1000$ pe fluxul chiral, față de $E_S \le 1.0$ pentru reperele simetrice/marginale.
3. **`Q3` (Martor de Înveliș Krawtchouk Pătratic Pur $m=2$):** pe o istorie sintetică cu frecvențe 1-corp și 2-corp uniforme și suprapunere medie $\mathbb{E}[|D_t \cap D_{t-1}|] = r^2/N$ egală cu media hipergeometrică ($m=1$ nul), dar varianță anomală de înveliș $m=2$, `KJ-V5` atinge $w_{K1} > 0.80$ și $E_S > 100$.
4. **`Q4` (Echivarianță Exactă la Permutări $S_{49}$, $S_{40}$ și $S_{45} \times S_{20}$):** $\max|\Delta \pi| < 10^{-12}$, $|\Delta \ln Z| < 10^{-12}$, $\max|\Delta w_m| < 10^{-12}$ și bilet fundamental $\sigma_\alpha(\pi \mathcal{H}) = \pi(\sigma_\alpha(\mathcal{H}))$.
5. **`Q5` (Cauzalitate Strictă, Invarianță `0.0` la Ordinea Intra-Zi `step_offsets` & `Incremental == Full`):** zero scurgere din pașii viitori $> s$, diferență $< 10^{-14}$ la inversarea extragerilor din zile cu extragere dublă și diferență $< 10^{-12}$ între execuția incrementală pas-cu-pas și execuția batch.
6. **`Q6` (Siguranță sub CSPRNG Uniform & Multiplet Ortogonal):** pe istorie sintetică pur uniformă, $E_s \ge 0.50$ pe toți pașii, $w_0^{(S)} > w_0^{(0)} = 0.50$, $\det G_3 > 0$ și $\sigma_\alpha \notin \{B, R\}$.

### 4.2. Porți Walk-Forward LIVE RO & Internațional/RNG (`G1–G6`, `s = 100 .. S-1`, Raportate Onest `X / 6`)
Evaluate pe `RO` (`649`, `540`, `joker`, cu ablație `K1`, `K2`, `K1_K2`, `Full_KJV5` și enumerare globală paralelă exactă pe 24 fire CPU pentru multipletul post-arhivă) și pe cele `10` fluxuri internaționale mecanice & electronice RNG (`fr_loto`, `hu_hatoslotto`, `hu_otoslotto`, `us_powerball`, `hu_skandinav_mech`, `hu_skandinav_rng`, `fdj_eurodreams`, `ny_take5`, `ny_cash4life`, `ny_pick10`):
- **`G1`:** Exces mediu de potriviri $\sigma_\alpha$ peste media hipergeometrică uniformă $\ge +0.20$;
- **`G2`:** $\text{Hits}(\text{KJ-V5}) > \max(\text{Hits}(B), \text{Hits}(R))$;
- **`G3`:** $\text{LogScore}(\text{KJ-V5}) > \max(\text{LogScore}(U), \text{LogScore}(B), \text{LogScore}(R))$;
- **`G4`:** $\text{Brier}(\text{KJ-V5}) < \min(\text{Brier}(U), \text{Brier}(B), \text{Brier}(R))$;
- **`G5`:** $\text{LogScore}(\text{KJ-V5}) > \text{LogScore}(B)$ în ambele jumătăți ale arhivei și pe ultimii $100$ pași;
- **`G6`:** Valoarea martingală a portofoliului Bayesian $E_S > 1.0$ (cu garanția structurală $E_s \ge 0.50$).

---

## 5. Arhitectura Ferestrei Native Tauri v2 (`rust_core_v2`) & Pictograma `quantum-lab-649-rust-core.desktop`

Fereastra nativă `Quantum Lab 649 · Rust Core v2` (`1360×880`, CSP strict `script-src 'self'; style-src 'self'`, zero bundler extern, `positive_claims_allowed = false` vizibil permanent în antet) expune 9 file native prin IPC Tauri v2:
1. **`⚡ KJ-V5 · Rust Nativ`** — Starea cauzală post-arhivă și multipletul exact $(\alpha, \beta, \gamma)$ + nucleul determinist pe `649`, `540`, `joker` (calculate pe 24 fire CPU), spectrul învelișurilor Krawtchouk $\psi_{1..3}$ & valorile proprii Koopman $V_2$ $(\lambda_+, \lambda_-)$, porțile `Q1–Q6` și `G1–G6`, studiul de ablație (`K1`, `K2`, `K1_K2`, `Full_KJV5`), curbele $E_s$ și $(w_0, w_{K1}, w_{K2}, w_{K3})$, categoriile câștigătoare și evaluarea pe cele `10` loterii internaționale mecanice & electronice RNG.
2. **`⚛ HS-V4 · RO Live & ERA5`** — Cititor nativ Rust verificat SHA-256 peste rapoartele JSON și curbele binare `.npz` din `hs_v4/rezultate/` + sincronizare cauzală cu `CURRENT_LIVE.json`, multipletul $(\alpha, \beta, \gamma)$, spectrul bosonic/Jennrich, meteo ERA5 București `18:00` (`ρ_air`, `RH`, `ΔP_24h`), ablația `O1 / O1+O2 / O1+O4 / Full_HSV4`, categoriile câștigătoare și panoul **1-Click `Câte & Unde`** (în România și pe loteriile externe compatibile).
3. **`🌍 Internațional & RNG Electronic`** — Comparație nativă completă (`HS-V4` și `KJ-V5`) pe cele `4` loterii mecanice externe, cele `4` loterii electronice online RNG, perechea sincronizată `7/35` `HU Skandináv Lottó` (`kézi` mecanic vs `gépi` electronic pe `1312` zile) și martorul de control negativ `O2` pe fluxurile pur electronice.
4. **`Densități π · ρ`** (`S18–S19`: probabilități de includere $\pi_i$, operator densitate $\rho = \Pi/k$, spectru DFT pe etichete).
5. **`FrFT`** (`S19`: transformata Fourier fracționară Candan–Kutay–Ozaktas $|F_a z|$, reziduu unitar și Parseval).
6. **`Filtru admisibilitate`** (`S17/S20/S22`: măști `u64`, ordine exactă Shewchuk, certificare SHA-256 prin `LANT.jsonl`, eticheta standard).
7. **`Paritate Rust ↔ Python`** (`S19`: verificare încrucișată cu `ip_core.py` la $|\Delta| \le 10^{-12}$ + verificarea independentă `KJ-V5`).
8. **`Inventar LIVE`** (`S18`: `tokio::fs` + `memmap2` peste `CURRENT_LIVE.json`).
9. **`Memorie`** (`S20–S22`: `procfs` `VmRSS`/`VmHWM`/`Pss` + telemetrie continuă pe `./telemetry/`, grafic în direct fără serii păstrate în Webview).
