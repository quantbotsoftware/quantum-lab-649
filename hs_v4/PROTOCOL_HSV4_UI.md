# PROTOCOL HSV4-UI — Integrarea Motorului HS-V4 și a Tab-ului Internațional & Extrageri Electronice Online în UI-ul Quantum Lab 649

- **Protocol ID**: `HSV4-UI`
- **Părinte algebric / fizico-statistic**: `HSV4-P1` (`hs_v4/PROTOCOL_HSV4.md`, sigilat `0444` în `hs_v4/SIGILIU_PROTOCOL_HSV4.json`)
- **Mecanism de înlocuire**: `inlocuiri_tu3/v1` (`tu3/inlocuiri_tu3.py`)
- **Statut științific afișat permanent**: `HSV4_NO_PROMOTION_EXPLORATORY · Calificare Q1–Q6: 6/6 PASS · calcul clasic float64 · variantele multipletului Coulomb–Jastrow (α, β, γ) și nucleul determinist sunt minime de energie / stări statistice condiționate de istoric, NU predicții și fără promisiuni de câștig · positive_claims_allowed=false`
- **positive_claims_allowed**: `false`

---

## 1. Scop și Reguli de Integritate Pre-Cod

Acest protocol preînregistrează, **înainte de scrierea oricărui fișier de cod UI nou** (`code_files_present: []`, `results_present: false`), montarea aditivă a modulului `hs_v4/ui_hs_v4.py` în interfața Quantum Lab 649 pe portul `8649` (`./porneste_aplicatia_tu3.sh` → `tu3/matrice_init.py` → `app.py` + `tu3/ui_tu3.py`), acoperind cele 3 universuri RO (`649`, `540`, `joker`) și tab-ul dedicat **`🌍 Internațional & Extrageri Electronice Online`**.

1. **Fișiere protejate / neatinse (`frozen_hashes`)**: `app.py`, `engine.py`, `parser.py`, `validare.py`, `tu3/parser_multi.py`, `tu3/motor_n.py`, `tu3/motor_joker.py`, `tu3/matrice_init.py`, `tu3/inlocuiri_tu3.py`, `tu4/*`, `pl_v3/*`, pistele închise `*649/`, `hs_v4/PROTOCOL_HSV4.md`, `hs_v4/SIGILIU_PROTOCOL_HSV4.json`, `hs_v4/date_meteo/*`, `hs_v4/core.py`, `hs_v4/meteo_ro.py`, `hs_v4/verify_q.py`, `hs_v4/walkforward.py`, `hs_v4/international.py`, `hs_v4/rezultate/*` și `hs_v4/date_intl/PROVENIENTA_INTL.json` rămân nemodificate byte-cu-byte. Fișierele oarbe `0400` din `xi/date_p2/*/rezerva.json` nu sunt atinse sau citite niciodată.
2. **Fișiere înlocuibile sigilat (`replaceable`)**:
   - `tu3/ui_tu3.py` — extins exclusiv prin **inserții pure** (`equal` + `insert` față de copiile de referință), cu blocul de delegare `# HSV4-UI` plasat **înaintea** secțiunii `# TU4-UI (S14;` astfel încât testele existente (`U1–U11`, `L3`, `P9`, `B7`, `C7`, `UT1–UT7` și `test_ui_plv3.py`) să rămână intacte;
   - `tests/test_scor_real.py` — o singură linie aditivă în `test_W11_seal_frozen_imports` care adaugă înregistrarea sigilată a `hs_v4/SIGILIU_HSV4_UI.json` în lanțul `inlocuiri_tu3/v1`.
3. **Fișiere noi planificate**:
   - `hs_v4/ui_hs_v4.py` — randarea UI pentru `HS-V4` pe modurile RO (`649`, `540`, `joker`) și tab-ul `🌍 Internațional & Extrageri Electronice Online`;
   - `tests/test_ui_hsv4.py` — suita completă de teste `AppTest` + integritate `0444` + coexistență `TU3`/`TU4`/`PL-V3` + VRAM;
   - `tu3/inlocuiri/INLOCUIRE_HSV4_UI_<UTC>Z.json` — înregistrarea `0444` emisă de `tu3/inlocuiri_tu3.py --inregistreaza`.

---

## 2. Puncte Exacte de Inserție (`P1`–`P4`)

- **P1 (`tu3/ui_tu3.py`, în `sidebar_selector()`)**:
  Inserarea comutatorului `hsv4_on = hsv4_sidebar_switch()` (`key="hsv4_active"`):
  - Activ implicit (`True`) la lansarea normală de pe Desktop pe portul `8649`;
  - Inactiv automat (`False`) când `QL649_CONFIG == "fast"`, `QL649_UI_PROTOCOL == "1"`, `QL649_PLV3_DESKTOP_SIM == "1"` sau sub `pytest` (`"pytest" in sys.modules` / `PYTEST_CURRENT_TEST` în `os.environ`), dacă nu este activat explicit prin variabila dedicată `QL649_HSV4_ACTIVE == "1"` (sau `QL649_HSV4_DESKTOP_SIM == "1"`), garantând zero interferențe cu `PL-V3`, `TU4` și modurile clasice `TU3`.
- **P2 (`tu3/ui_tu3.py`, în `sidebar_selector()`, după garda `if tu4_on:` și înainte de `if plv3_on:`)**:
  Dacă `hsv4_on` este activ:
  - La schimbarea modului (`st.session_state.get("tu3_prev_mode") not in (None, mode)`), eliberează cache-urile UI și memoria GPU (`clear_ui_caches()` + `release_mode` / `gc.collect()` + `torch.cuda.empty_cache()`) și actualizează `st.session_state["tu3_prev_mode"] = mode`;
  - Randează interfața prin `render_hs_v4(mode)` și oprește execuția ulterioară cu `st.stop()`.
- **P3 (`tu3/ui_tu3.py`, înainte de `# TU4-UI (S14;`)**:
  Funcțiile compacte de delegare `# HSV4-UI` (`hsv4_default_on`, `hsv4_sidebar_switch`, `hsv4_on_mode_and_render`).
- **P4 (`tests/test_scor_real.py`, în `test_W11_seal_frozen_imports`)**:
  Adăugarea liniei `valid_r += [r for r in INL.load_records(ROOT)[0] if r["seal"] == "hs_v4/SIGILIU_HSV4_UI.json"]`.

---

## 3. Specificația Funcțională și Epistemică (`hs_v4/ui_hs_v4.py`)

Zero elemente comerciale, contabile, financiare, cheltuieli sau bugete. `positive_claims_allowed = false`.

1. **Încărcare Instantanee Verificată SHA-256 & Decontare Cauzală Automată (`RO: 649, 540, joker`)**:
   - Interoghează `hs_v4.walkforward.get_or_advance_live(mode, config_key=...)` peste `hs_v4/cache/`, verificând obligatoriu SHA-256 al checkpoint-ului `.pt` și sincronizându-se cauzal automat la apariția unor extrageri noi în `CURRENT_LIVE.json`, cu eliberare completă VRAM.
2. **Stări Statistice `(α, β, γ)` · Nucleu Determinist · Spectru Bosonic/Jennrich · Meteo ERA5 București**:
   - Cele 3 carduri `.ql-variant` (`α`, `β`, `γ`) + nucleul determinist + $\det G_3$, încadrate explicit și permanent ca **minime de energie / stări statistice condiționate de istoric, NU predicții** și fără promisiuni de câștig;
   - Spectrul bosonic `O1` ($\lambda_1, \lambda_2, \lambda_3$ brute și atenuate) + valorile proprii tensoriale Jennrich ($\nu_1, \nu_2, \nu_3$);
   - Vectorul exogen meteo ERA5 București `18:00 Europe/Bucharest` (`ρ_air`, `RH`, `ΔP_24h` + standardizarea cauzală Welford $z^{\text{met}}_s$).
3. **Calificare `Q1–Q6` · Porți Walk-Forward `G1–G6` · Ablație · Martingală $E_s$ · Mase Bayesiene & Categorii**:
   - Rezumatul calificării `Q1–Q6` (`6/6 PASS`, `HSV4_QUALIFIED`) și al porților `G1–G6` (`X / 6`, `HSV4_NO_PROMOTION_EXPLORATORY`);
   - Studiul complet de ablație (`O1`, `O1+O2`, `O1+O4`, `Full HS-V4`) din `hs_v4/rezultate/ABLATIE_RO.json` și curbele `.npz`;
   - Traiectoria martingală $E_s$ (evidențiind pragul garantat algebric $E_s \ge 0.50$), evoluția maselor Bayesiene $(w_0, w_{\text{O1}}, w_{\text{O2}}, w_{\text{O4}})$ și distribuția pe categorii câștigătoare (`3+`, `4+`, `5+`, `6/6`, `+Joker`) față de `U`, `B`, `R`.
4. **Tab-ul Dedicat `🌍 Internațional & Extrageri Electronice Online`**:
   - Alimentat din `hs_v4/rezultate/INTERNATIONAL_RNG_EVAL.json`, `hs_v4/date_intl/PROVENIENTA_INTL.json` și curbele `hs_v4/rezultate/intl_*_walkforward.npz`:
     * **Loterii mecanice externe**: `FR Loto` ($5/49 + 1/10$), `HU Hatoslottó` ($6/45$), `HU Ötöslottó` ($5/90$), `US Powerball` ($5/69 + 1/26$);
     * **Extrageri electronice online RNG**: `FDJ EuroDreams` ($6/40 + 1/5$), `NY Take 5` ($5/39$), `NY Cash4Life` ($5/60 + 1/4$), `NY Pick 10` ($10/80$ din $20/80$);
     * **Comparația directă pereche pe aceeași urnă `7/35`** (`HU Skandináv Lottó`: Tragerea 1 Mecanică `kézi` vs. Tragerea 2 Electronică RNG `gépi` pe cele `1312` zile sincronizate);
     * **Martorul de control negativ `O2`** pe fluxurile pur electronice RNG (contracția $w_{\text{O2}}$ sub prior și garanția $E_s \ge 0.50$).

---

## 4. Verificare End-to-End

1. Sigilare pre-cod `0444` pentru `hs_v4/PROTOCOL_HSV4_UI.md` și `hs_v4/SIGILIU_HSV4_UI.json` înaintea creării `hs_v4/ui_hs_v4.py` și `tests/test_ui_hsv4.py`.
2. Înregistrare sigilată `tu3/inlocuiri_tu3.py --simuleaza` / `--inregistreaza hs_v4/SIGILIU_HSV4_UI.json HSV4_UI`.
3. Suită `tests/test_ui_hsv4.py` și rulare integrală `pytest` (100% PASS pe toate testele vechi și noi).
4. Verificare live HTTP `200 OK` + `/_stcore/health` pe `http://127.0.0.1:8649`, curățare `__pycache__`, `inlocuiri_tu3.py --verifica` (`"ok": true`) și `tu3/matrice_init.py` (`TOATE 3 MODURILE READY`, `Integritate: OK`).
