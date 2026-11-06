# PROTOCOL TU4-IP-H2 „UZ” — micro-uzură: derivă lentă continuă a propensiunilor (discount exponențial + contracție)

Parte a protocolului `tu4/PROTOCOL_TU4_IP.md` (comun: legea, e-procesul, lumile, porțile Q1–Q6). Sigilat împreună,
cu hash propriu, ÎNAINTE de cod.

## 1. Mecanismul fizic și informația pre-țintă

- **Ipoteză H_UZ:** bilele se uzează micro-mecanic (abraziune, ciobiri, pierdere de masă/vopsea, încărcare a
  suprafeței) continuu și neuniform; propensiunea ln w_{t,i} urmează o derivă LENTĂ, continuă (fără rupturi,
  fără regimuri discrete — acelea sunt BO649, închis). Prior fizic fixat ACUM: timp caracteristic de uzură cu
  înjumătățirea memoriei h = 312 extrageri (≈ 3 ani la 104 extrageri/an); nu se reglează.
- **Informație pre-țintă:** numărările marginale ponderate cu vechimea, c̃_i = Σ_s ρ^{vârsta_s}·1[i ∈ S_s],
  ρ = 2^{−1/312} (vârsta ultimei extrageri = 0). Fără tranziții, fără vârsta proprie a etichetelor, fără calendar.
- **Decizia diferită față de repere:** B și H1 cântăresc egal tot trecutul; R (BO649) folosea o fereastră scurtă
  (înjumătățire 26) fără contracție. H_UZ urmărește starea CURENTĂ a urnei cu o memorie fizică lungă și pariază o
  fracțiune adaptivă; când uzura a inversat recent direcția, biletul H2 diferă de cel al lui H1/B (fixtura F2).

## 2. Modelul (exact)

Înaintea extragerii viitoare t (arhiva sintetică are T extrageri): vârstele a = 0..T+t−2; Ñ = Σ_a ρ^a,
N₂ = Σ_a ρ^{2a}; c̃ ca mai sus; θ̂_i = (n−1)/n · (c̃_i/Ñ − p)/(p(1−p)); X̃² = (n−1)/n · Σ (c̃_i − Ñp)² / (N₂ p(1−p))
(varianța corectă a sumelor ponderate sub nul); λ = max(0, 1 − (n−3)/X̃²); ln ŵ = λ θ̂. Bila Joker: idem cu n = 20,
k = 1, același ρ. Precedente: Brown (1959) / Holt (1957) netezirea exponențială; Harrison & Stevens (1976), West &
Harrison (1997) modelul de nivel local / factorul de discount; James–Stein pentru contracție.

## 3. Implantul A2 (lumea H2)

Proces Ornstein–Uhlenbeck discret pe ln w, centrat: x_0 ~ N(0, I_n) proiectat pe 1⊥; x_{t+1} = φ x_t + √(1−φ²)·η_t,
η_t ~ N(0, I_n) proiectat pe 1⊥, φ = 2^{−1/312} (aceeași scală de timp ca priorul — declarat: calificare sub
propria alternativă). ln w_t = ε x_t, cu ε > 0 pe lume rezolvat prin bisecție (60 de iterații) astfel încât media lui
D(ε x_t) pe grila t ∈ {0, 5, 10, …} < T + H să fie D_țintă (abatere relativă ≤ 1e-10). Joker: idem, independent,
pentru urna principală și bilă, cu țintele lor.

## 4. Fixturile (definite exact acum; numărări „așteptate”, fracționare, distribuite uniform în bloc)

v ca în H1-F1, v̂ = v/‖v‖; 6/49, N = 2595 = 2295 (bloc vechi) + 300 (bloc recent);
a = √(300·p(1−p)·n / ((n−1)·2295)) (blocul vechi singur ar avea X² = 300). Pe extragere: abaterea indicatoarelor =
+a·v̂ în blocul vechi și −4a·v̂ în blocul recent.
- **F2 (decizie):** istoria A = bloc vechi (vârste 300..2594) apoi bloc recent (vârste 0..299). PASS dacă λ_H1 > 0,
  λ_H2 > 0, biletul H1 = cele 6 etichete cu v maxim și biletul H2 = cele 6 etichete cu −v maxim.
- **I2 (informație: aceleași numărări, altă ordine):** istoria A' = blocul cu −4a·v̂ primul (vârste 2295..2594),
  apoi blocul cu +a·v̂ (vârste 0..2294). Numărările totale sunt identice cu A. PASS dacă ln ŵ_H1(A) = ln ŵ_H1(A')
  (|Δ| ≤ 1e-12) ȘI biletul H2(A) ≠ biletul H2(A').

## 5. Infirmare și limite

Ca în H1 (porțile Q1–Q6; retragere în tribunal la ln E_T < −10). Dacă urna ar fi staționară, H2 pierde față de H1
din cauza memoriei mai scurte; acest cost este parte a ipotezei și apare în matricea încrucișată.
