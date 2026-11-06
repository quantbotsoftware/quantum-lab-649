# PROTOCOL PLV3-UI — Integrarea Motorului PL-V3 în UI-ul Quantum Lab 649

- **Protocol ID**: `PLV3-UI`
- **Părinte algebric / predictiv**: `PLV3-P1` (`pl_v3/PROTOCOL_PLV3.md`, sigilat în `pl_v3/SIGILIU_PROTOCOL_PLV3.json`)
- **Mecanism de înlocuire**: `inlocuiri_tu3/v1` (`tu3/inlocuiri_tu3.py`)
- **Statut științific afișat permanent**: `PLV3_NO_PROMOTION_EXPLORATORY · 0 / 6 porți · calcul clasic · variantele sunt moduri determinantale/Jastrow, NU predicții cu avantaj demonstrat · positive_claims_allowed=false`
- **positive_claims_allowed**: `false`

---

## 1. Scop și Reguli de Integritate

Acest protocol preînregistrează, **înainte de scrierea oricărui fișier de cod UI nou** (`code_files_present: []`, `results_present: false`), montarea aditivă a modulului `pl_v3/ui_pl_v3.py` în interfața principală lansată de pe Desktop (`./porneste_aplicatia_tu3.sh` → `tu3/matrice_init.py` → `app.py` + `tu3/ui_tu3.py`), pe toate cele 3 universuri din bara laterală (`649`, `540`, `joker`).

1. **Fișiere protejate / neatinse**: `app.py`, `engine.py`, `parser.py`, `tu3/parser_multi.py`, `tu3/motor_n.py`, `tu3/motor_joker.py`, `tu3/matrice_init.py`, `tu3/inlocuiri_tu3.py`, `pl_v3/core.py`, `pl_v3/verify_q.py`, `pl_v3/walkforward.py` și toate sigiliile anterioare rămân nemodificate byte-cu-byte.
2. **Fișiere înlocuibile sigilat (`replaceable`)**:
   - `tu3/ui_tu3.py` — modificat exclusiv prin **inserții pure** (`equal` + `insert` față de copiile de referință), cu blocul de delegare `# PLV3-UI` plasat **înaintea** secțiunii `# TU4-UI (S14;` astfel încât testele `U1–U11`, `L3`, `P9`, `B7`, `C7` și `UT1–UT7` să rămână intacte;
   - `tests/test_scor_real.py` — o singură linie aditivă în `test_W11_seal_frozen_imports` care include înregistrarea sigilată a `pl_v3/SIGILIU_PLV3_UI.json` în lanțul `inlocuiri_tu3/v1`.
3. **Fișiere noi planificate**:
   - `pl_v3/ui_pl_v3.py` — randarea UI principală a multipletului `(α, β, γ)` și a telemetriei predictive/fizice `PL-V3`;
   - `tests/test_ui_plv3.py` — suita `AppTest` end-to-end pe `649`, `540`, `joker`;
   - `tu3/inlocuiri/INLOCUIRE_PLV3_UI_<UTC>Z.json` — înregistrarea `0444` scrisă de `tu3/inlocuiri_tu3.py --inregistreaza`.

---

## 2. Puncte Exacte de Inserție (`P1`–`P4`)

- **P1 (`tu3/ui_tu3.py`, în `sidebar_selector()`)**:
  Inserarea comutatorului `plv3_on = plv3_sidebar_switch()` (`key="plv3_active"`):
  - Activ implicit (`True`) la lansarea normală de pe Desktop;
  - Inactiv implicit (`False`) când `QL649_CONFIG == "fast"`, `QL649_UI_PROTOCOL == "1"` sau sub `pytest` (`"pytest" in sys.modules` / `PYTEST_CURRENT_TEST` în `os.environ`, cu posibilitate de suprascriere explicită în `tests/test_ui_plv3.py`), păstrând neschimbate toate testele UI existente (`U1–U9`, `test_app.py`, `tu4/tests/test_ui.py`).
- **P2 (`tu3/ui_tu3.py`, în `sidebar_selector()`, după garda `if tu4_on:` și înainte de `return mode`)**:
  Dacă `plv3_on` este activ:
  - La schimbarea modului (`st.session_state.get("tu3_prev_mode") not in (None, mode)`), execută eliberarea cache-urilor și a memoriei GPU (`release_mode` / `gc.collect()` + `torch.cuda.empty_cache()`) și actualizează `st.session_state["tu3_prev_mode"] = mode`;
  - Randează pagina principală prin `plv3_render_main(mode)` și oprește execuția ulterioară cu `st.stop()`.
- **P3 (`tu3/ui_tu3.py`, înainte de `# TU4-UI (S14;`)**:
  Funcțiile compacte de delegare `# PLV3-UI` (`plv3_default_on`, `plv3_sidebar_switch`, `plv3_on_mode_and_render`).
- **P4 (`tests/test_scor_real.py`, în `test_W11_seal_frozen_imports`)**:
  Adăugarea liniei `valid_r += [r for r in INL.load_records(ROOT)[0] if r["seal"] == "pl_v3/SIGILIU_PLV3_UI.json"]`.

---

## 3. Specificația Vizuală și Funcțională (`pl_v3/ui_pl_v3.py`)

Modulul reutilizează stilul neon cyberpunk din `app.py` și `tu3/ui_tu3.py` (`.ql-title`, `.ql-sub`, `.ql-warn`, `.ql-variant`, `.ql-variant.v2`, `.ql-variant.v3`, `.ql-ball`, `.ql-plus`, `.ql-ball.jk`, `.ql-card`, `PLOT_LAYOUT`):

1. **Etichetă permanentă de onestitate**:
   `PLV3_NO_PROMOTION_EXPLORATORY · 0 / 6 porți · calcul clasic · variantele sunt moduri determinantale/Jastrow, NU predicții cu avantaj demonstrat · positive_claims_allowed=false`.
2. **Sincronizare automată LIVE**:
   Interoghează `parser_multi.live_key(mode)` și `pl_v3.walkforward.get_or_advance_live(mode)` (`< 0.01 s` pe cache-hit din `pl_v3/cache/state_{mode}_{src_key[:12]}.pt`, `< 0.35 s` la avansarea incrementală `CURRENT_LIVE.json`, cu `gc.collect()` + `torch.cuda.empty_cache()`).
3. **Cele 3 Carduri Principale cu Bile**:
   - `VARIANTA 1 · STARE FUNDAMENTALĂ α` (cyan `.ql-variant.v1`)
   - `VARIANTA 2 · EXCITATĂ ORTOGONALĂ β` (magenta `.ql-variant.v2`)
   - `VARIANTA 3 · EXCITATĂ ORTOGONALĂ γ` (lime `.ql-variant.v3`)
   - Pentru `joker`: 5 bile principale `1..45` + `<span class="ql-plus">+</span><span class="ql-ball jk">b</span>` (`1..20`).
   - Fiecare card afișează `ln W(σ)`, probabilitatea exactă `P(σ)` pe întreg spațiul finit și ortogonalitatea Coulomb–Jastrow `det G` (`det G₁`, `det G₂`, `det G₃`).
4. **Carduri KPI sub variante (`.ql-card`)**:
   - `NUMERE DISTINCTE ACOPERITE`
   - `NUCLEU DETERMINIST`
   - `EROARE CAUCHY-BINET`
   - `GAP FUNDAMENTAL ΔlnW`
   - `TIMP MOTOR GPU`
   - `VRAM` (cu telemetria eliberării la comutarea modului).
5. **Telemetrie Strict Predictivă & Fizică**:
   - `CALIFICARE Q1–Q6` (`6/6 PASS` din `pl_v3/rezultate/CALIFICARE_Q.json`);
   - `WALK-FORWARD ARHIVĂ LIVE (G1–G6: 0/6)` (tabelul porților G1–G6, ferestrele `total`, `half1`, `half2`, `last100` și defalcarea `5/45 + 1/20` pe `joker` din `pl_v3/rezultate/{mode}_walkforward.json`);
   - Curba Plotly `log10(E_s)` a E-procesului defensiv Ville pe toată arhiva la zi (`{mode}_walkforward.npz` extinsă cauzal cu eventualele extrageri noi din `settlement_history`);
   - Fracția de vorticitate coomologică `‖J_curl‖²/‖J‖²` (împreună cu eroarea de ortogonalitate Hodge și holonomia Wilson `SU(3)`);
   - Diagrama Argand a spectrului operatorului de transfer Ruelle `λ(L̃_Ruelle)` în planul complex;
   - Entropia de încurcare Von Neumann `S_vN` + distribuția exactă a celor 20 bile Joker (`P_J(b)` vs reperul uniform `1/20` și bilele `(α, β, γ)`);
   - Istoricul decontărilor automate live (`settlement_history` / `settled_new_draws`);
   - Graficul orizontal `PROFIL GPU PE OPERATOR (secunde)`.

---

## 4. Verificare End-to-End

1. Sigilare pre-cod `0444` pentru `pl_v3/PROTOCOL_PLV3_UI.md` și `pl_v3/SIGILIU_PLV3_UI.json`.
2. Suită `tests/test_ui_plv3.py` (`AppTest` cu `PL-V3` activ pe `649`, `540`, `joker`, verificare carduri, KPI, telemetrie, eliberare VRAM la schimbarea modului și latență `get_or_advance_live`).
3. Înregistrare sigilată `.venv/bin/python -B tu3/inlocuiri_tu3.py --inregistreaza pl_v3/SIGILIU_PLV3_UI.json PLV3_UI` și validare `--verifica`.
4. Verificare `.venv/bin/python -B tu3/matrice_init.py` (`TOATE 3 MODURILE READY` și `Integritate: OK`), rulare `pytest` completă pe suitele UI/integritate și pornire curată `./porneste_aplicatia_tu3.sh` pe portul `8649`.
