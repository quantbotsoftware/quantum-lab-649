# Quantum Lab 649 — User Manual (English)

> **Scope notice.** Quantum Lab 649 is a *classical* combinatorial and spectral observatory for historical lottery draws (Romanian Loto 6/49, 5/40 and Joker, plus ten international archives). Every operator in it is ordinary mathematics executed on a GPU or CPU. The application **does not predict winning numbers, does not offer an advantage and guarantees nothing** — the program itself enforces `positive_claims_allowed = false` in every screen and every sealed file. It is published AS-IS under the MIT License, without warranty or technical support. Read [DISCLAIMER.md](DISCLAIMER.md) before use.

This manual describes what you actually receive in the archive, how to install and start it, what every control in the interface does and what to expect when something is missing.

---

## 1. What is in the box

| Item | Description |
|---|---|
| `app.py`, `engine.py`, `parser.py`, `validare.py` | The main Loto 6/49 observatory: data ingestion, the six mathematical operators (O1–O6), validation (Null Multiverse, causal walk-forward backtest) and the Streamlit dashboard. |
| `tu3/` | Multi-game layer (TU3): Loto 5/40 and Joker engines, the game selector, the LIVE/frozen data-source switch and the bundled draw archives. |
| `hs_v4/`, `pl_v3/`, `tu4/`, `xi/`, `kj_v5/` | Optional engines and sealed research protocols (HS-V4 bosonic multiplet + ERA5 meteo, PL-V3 Jastrow, TU4 read-only prospective tribunal, XI strategy screens, KJ-V5 Rust protocol). |
| `bo649/`, `wu649/`, `gl649/`, `se649/`, `cs649/`, `pl649/` | Six *closed* research tracks, each with its sealed pre-registration and final report. |
| `data/extrageri_649.jsonl` | 2,600+ Loto 6/49 draws (JSONL, one draw per line with date, numbers and provenance fields). |
| `tu3/date/extrageri_540.jsonl`, `tu3/date/extrageri_joker.jsonl`, `tu3/date/live/` | Loto 5/40 and Joker archives plus the frozen LIVE snapshot (`CURRENT_LIVE.json` → `versiuni/<sha12>/`). |
| `hs_v4/date_intl/`, `hs_v4/date_meteo/` | Ten international lottery archives (mechanical and electronic RNG) and the 90-day ERA5 Bucharest air-density series. |
| `tests/` | pytest suite (parser, engine, validation, UI AppTest). |
| `setup_venv.sh`, `run_app_tu3.sh`, `run_app.sh`, `porneste_aplicatia.sh` | Installer and launchers (see §3). |
| `desktop/install-desktop-shortcut.sh` | Creates the Linux `quantum-lab-649.desktop` launcher pointing at your extracted folder. |
| `verify_ql649.py` | Independent NumPy fp64 verifier for the walk-forward backtest artefacts. |
| `check-updates.sh` | Manual, zero-telemetry update check against `https://bot-tradingsoftware.com/versions.json`. |
| `PREINREGISTRARE_QL649.md`, `AMENDAMENT_0x.md`, `SIGILIU_*.json`, `RAPORT_QL649.md`, `PLAN_QL649.md` | The sealed protocol, amendments, SHA-256 seals and the published report. |

**Not included on purpose** (generated locally or available on request): `rezultate/` run outputs, `hs_v4/cache/`, `xi/rezultate/`, `kj_v5/rezultate/`, `tu4/rezultate/`. See §10.

---

## 2. Requirements

| Component | Minimum | Recommended |
|---|---|---|
| Operating system | Linux x86-64 (tested on Ubuntu/Pop!_OS 22.04+) | Any recent Linux with Python 3.10+ |
| Python | 3.10 | 3.11 / 3.12 |
| GPU | *Optional.* Without CUDA the engine falls back to CPU automatically (10–30× slower). | NVIDIA GPU with ≥ 6 GB VRAM and a CUDA-enabled PyTorch build |
| RAM | 8 GB | 16 GB |
| Disk | ~6 GB (virtual environment with PyTorch ≈ 4–5 GB + 15 MB data) | — |
| Browser | Any modern browser (the dashboard is served locally on `http://127.0.0.1:8649`) | Chromium / Firefox |

macOS and Windows are not tested. The code is pure Python and should run anywhere PyTorch and Streamlit run, but the launch scripts are Bash and the desktop shortcut is Linux-only.

---

## 3. Installation

### 3.1 Download and verify

1. Download `quantum-lab-649-opensource.zip` from [bot-tradingsoftware.com/#downloads](https://bot-tradingsoftware.com/#downloads) or from the GitHub Release of [quantbotsoftware/quantum-lab-649](https://github.com/quantbotsoftware/quantum-lab-649).
2. Verify the archive (same folder as the downloaded `SHA256SUMS.txt`):
   ```bash
   sha256sum -c SHA256SUMS.txt --ignore-missing
   ```
3. Extract it anywhere **without spaces in the path**, e.g. `~/apps/quantum-lab-649/`.

### 3.2 Create the Python environment

```bash
cd ~/apps/quantum-lab-649
./setup_venv.sh
```

The script creates `.venv/` and installs `requirements.txt` (NumPy, SciPy, pandas, **PyTorch**, Streamlit, Plotly, Altair, NetworkX, SymPy, mpmath, pytest). On most Linux machines `pip` selects a CUDA-enabled PyTorch wheel automatically. If you have an NVIDIA GPU but the app later reports `dispozitiv: CPU (fallback)`, install the wheel that matches your driver explicitly, for example:

```bash
.venv/bin/pip install --index-url https://download.pytorch.org/whl/cu124 torch
```

(see [pytorch.org/get-started](https://pytorch.org/get-started/locally/) for the right index URL).

### 3.3 Start the dashboard

```bash
./run_app_tu3.sh
# then open http://127.0.0.1:8649 in your browser
```

What the launcher does, in order: compiles all `.py` files for syntax (`py_compile`), prints the TU3 initialisation matrix (`jurnal/matrice_*.txt`), prints whether CUDA was detected, then starts Streamlit in headless mode on port **8649** and logs to `jurnal/app_<timestamp>.log`.

Alternative launchers:

| Command | Use it when |
|---|---|
| `./run_app_tu3.sh` | Normal start (recommended). |
| `./run_app.sh` | Same server without the TU3 initialisation matrix. |
| `./porneste_aplicatia.sh` | Desktop-icon behaviour: stops any old server from this folder, clears `__pycache__`, starts `run_app.sh`, waits for `/_stcore/health`, opens the browser. `--stop` shuts the server down. |
| `./desktop/install-desktop-shortcut.sh` | Installs `quantum-lab-649.desktop` in `~/.local/share/applications/` and on your Desktop. |

To stop a server started from a terminal press `Ctrl+C`; for the desktop launcher use `./porneste_aplicatia.sh --stop`.

### 3.4 Useful environment variables

| Variable | Default | Effect |
|---|---|---|
| `QL649_PORT` | `8649` | TCP port of the dashboard. |
| `QL649_ADDRESS` | `127.0.0.1` | Bind address. Keep it local; the app has no authentication. |
| `QL649_CONFIG=fast` | unset | Fast test configuration (fewer replicas, PL-V3/HS-V4 toggles default to OFF). Use it on CPU-only machines to explore the UI quickly. |
| `QL649_SEAL_DIR` | `rezultate/sigilii` | Where sealed variant files are written. |
| `QL649_DATA_649` | `data/extrageri_649.jsonl` | Alternative 6/49 JSONL archive (frozen source). |
| `QL649_HSV4_CACHE_DIR` | `hs_v4/cache` | HS-V4 checkpoint cache (created on first run). |
| `PYTHON_BIN`, `STREAMLIT_BIN` | `.venv/bin/…` | Use a different interpreter / Streamlit binary. |
| `QL649_UI_PROTOCOL=1` | unset | Protocol-exact UI mode used by the tests. |

---

## 4. First launch — what you will see

The first load shows the spinner *„Inițializare câmp cuantic pe GPU… (prima rulare ≈ 30–40 s)”*: the engine ingests the archive, builds the day-step tensors and runs the full operator chain once (50,000 Boltzmann replicas, 10,000 MCMC steps). Results are cached in the server process, so switching tabs afterwards is instant. On CPU the first run can take several minutes.

The header shows four cards and the compliance line:

- **extrageri analizate** — number of draws used after validation and de-duplication.
- **pași (zile)** — number of time steps (two draws on the same day form a single step; no invented order).
- **ultima extragere** — date of the most recent draw in the active source.
- **indice coerență structurală (SCI)** — the structural-coherence index in σ units with its empirical p-value against the Null Multiverse (8,192 synthetic histories). Values near 0σ mean the archive is indistinguishable from pure chance — which is the expected, honest result.
- **dispozitiv** — `cuda` (GPU name) or `CPU (fallback)`.
- A grey line with `positive_claims_allowed=false`, the protocol SHA-256 prefix and the configuration digest. If it says **MOD FAST (test)** you started with `QL649_CONFIG=fast`.

The interface language is Romanian (the research protocols were written and sealed in Romanian); this manual translates every label you will meet.

---

## 5. The sidebar

| Control | Meaning |
|---|---|
| **🛰 UNIVERS ACTIV → Mod de joc** | Switches the whole dashboard between **Loto 6/49**, **Loto 5/40** and **Joker (5/45 + 1/20)**. Each mode has its own engine, archive, seals and the same 12-tab layout. |
| **Sursa datelor 6/49** (6/49 only) | `LIVE — arhiva actualizată automat` uses the versioned snapshot in `tu3/date/live/` (pointer → manifest → SHA-verified JSONL). `înghețat (sigilat)` uses the frozen protocol file `data/extrageri_649.jsonl`. The choice is remembered when you change mode. The archive you downloaded contains a frozen LIVE snapshot; it is **not** refreshed over the internet (see §9). |
| **🔮 Predicție prospectivă (TU4)** | Read-only tribunal screen that lists sealed prospective emissions and their settlements from `tu4/tribunal/`. It runs no engine. |
| **⚛ Motor PL-V3 (Jastrow · 0/6)** | Enables the PL-V3 determinantal/Jastrow engine on all three games. Label `0 / 6 porți` = it passed none of the six promotion gates, as published. |
| **⚛ Motor HS-V4 (Bosonic HS · Aero-Meteo ERA5 · RNG O4 · Portofoliu O3)** | Enables the HS-V4 engine and the *International & Electronic Draws* tab (§7). On a normal desktop start both PL-V3 and HS-V4 are ON; under `QL649_CONFIG=fast` they are OFF. |
| **Pages: Strategii, Registru** | Streamlit multipage entries (top of the sidebar). They only display sealed XI results from `xi/rezultate/`; because run outputs are not shipped they show an integrity error — this is expected (§10). |

---

## 6. The twelve tabs (Loto 6/49 — identical layout for 5/40 and Joker)

1. **⚛ Colapsul funcției de undă** — TOP-10 Born amplitudes `P = |Ψ|²` after the non-Hermitian walk, coloured by phase, next to the complex phase plane of all 49 numbers. The bar heights are *model* amplitudes, not probabilities of being drawn.
2. **🌀 Singularitate hiperbolică & Amplituhedron** — the exceptional point γ_EP of the walk, the coalescent eigenvalue λ_EP, the real quasi-EP and the hyperbolic anchors; below, the Poincaré-disk embedding of the co-occurrence graph and the 3-D "amplituhedron" volume plot (Plotly, rotate with the mouse).
3. **♾ Convergența terminală — Limita Cuantică** — the three terminal configurations produced by O5 (Boltzmann filter over 50,000 replicas) and O6 (parallel-tempering MCMC + QUBO). Cards show distinct numbers covered (x/18), the deterministic core (numbers present in ≥ 50 % of replicas), replica/step counts and GPU time. These are **energy minima of the model**, documented as such.
4. **🌌 Multiversul Nul** — 8,192 synthetic null histories generated with the same pipeline; the SCI distribution, where the real archive falls, and the empirical p-value. This tab is the honesty check of every other tab.
5. **⏳ Mașina Timpului** — the single, causal walk-forward backtest: at step *t* the engine sees only draws `< t`. Cards: verdict, gates passed (x/6), number of targets, QL-vs-uniform excess per target, independent verification status (`PASS` when `verify_ql649.py` has been run on a local `rezultate/backtest_unic/`). The published result is 0/6 gates.
6. **🧪 Ablație & Sigiliu temporal** — a form with five checkboxes (`O1 walk non-hermitic`, `O2 Amplituhedron`, `O3 Poincaré`, `O4 Kuramoto + interferență`, `Scutul Anti-Mulțime`) and the button **⚡ Recalculează pe GPU**: untick an operator to see how the terminal configurations change without it. The button **🔏 Sigilează variantele curente** writes a JSON file to `rezultate/sigilii/<mode>/` containing the current variants, configuration digest, source SHA and a SHA-256 over the payload — a timestamped proof of what the model said *before* a future draw. Sealing is local; nothing is uploaded.
7. **📉 Rupturi de regim (BO649)** — closed track: Bayesian online change-point detection (Beta–Bernoulli, h = 1/250). Shows the sealed protocol, verdict cards and the report link.
8. **🎱 Urna ponderată (WU649)** — closed track: weighted-urn model with exact rational certificates (fp64 CPU). Status `NERULAT` (not run) is normal until results exist locally.
9. **🔢 Masa glifelor (GL649)** — closed track: linear-Bayes glyph-mass model (Goldstein–Wooff), exact in ℚ.
10. **🍂 Anotimpurile bilelor (SE649)** — closed track: seasonal model with analytic Q5/Q6 witnesses.
11. **🎠 Caruselul seturilor (CS649)** — closed track: Henderson 16×16 linear-Bayes set carousel.
12. **🌌 Orizontul evenimentelor (PL649)** — closed track: PL649 determinantal model (rendered by `ui_pl649`).

Tabs 7–12 are documentation tabs: they display the pre-registered protocol, the qualification/backtest cards and link to `*/RAPORT_*.md`. Their metric cards read `—` or `NERULAT` until you generate the corresponding `rezultate/` locally with the track's own scripts.

---

## 7. HS-V4 engine (sidebar toggle ON)

When HS-V4 is active for the selected game, the main area is replaced by the HS-V4 observatory:

- **Configurație canal HS-V4 (RO)** (sidebar): `Full_HSV4` (O1 + O2 + O4), `O1_O2`, `O1_O4` or `O1` only — the ablation configuration.
- A synchronisation caption: `CACHE HIT` or `AVANS CAUZAL +n PAȘI` (how many new steps were processed causally), the source key, the checkpoint SHA, `Q1–Q6: 6/6 PASS` (algebraic pre-archive qualification) and the walk-forward gate verdict (published: 0/6 — no promotion), plus residual VRAM.
- **🎯 1-CLICK: Vezi Câte & Unde Ar Fi Fost Potriviri** — opens a historical "how many and where" inspector for all three Romanian games (and the international feeds). It counts, *after the fact*, how often the model's terminal configurations would have matched ≥ k numbers. It is a descriptive audit, not a forecast; press the same button (now labelled ✖) to close it.
- Four sub-tabs:
  1. **⚛ Stări Statistice (α, β, γ) · Spectru & Meteo ERA5** — Hubbard–Stratonovich eigenvalues (raw / attenuated / Jennrich), the 90-day ERA5 air-density series for Bucharest and the exact marginal inclusion probabilities π_i versus the uniform k/N line.
  2. **📉 Calificare Q1–Q6 · Porți G1–G6 & Ablație RO** — the six algebraic qualification checks, the six walk-forward promotion gates and the ablation table (O1/O2/O4 channels, Brier and LogScore columns).
  3. **📊 Martingala E_s · Mase Bayesiene & Categorii RO** — the martingale trajectory E_s, Bayesian posterior masses w₀/w₀₁/w₀₂/w₀₄ collapsing onto the uniform channel, and hypergeometric expected-vs-observed hit categories (3+ … 6/6).
  4. **🌍 Internațional & Extrageri Electronice Online** — selector *Selectează loteria externă*: FR Loto, HU Hatoslottó / Ötöslottó / Skandináv (manual vs machine 7/35), US Powerball, and electronic RNG draws (EuroDreams, NY Take 5 / Cash4Life / Pick 10). Mechanical and RNG feeds are compared with the same pipeline; the paired HU 7/35 experiment and the ERA5 negative control on pure-RNG draws are the controls.

The first HS-V4 run per game builds `hs_v4/cache/` (a few hundred MB, GPU ≈ 1–3 min, CPU considerably longer); later starts are cache hits.

---

## 8. PL-V3 and TU4

- **PL-V3** (toggle) renders the Jastrow/determinantal engine with the same honesty banner (`PLV3_NO_PROMOTION_EXPLORATORY · 0 / 6 porți`). Its variants are determinantal modes of the model.
- **TU4 — 🔮 Predicție prospectivă** is read-only. It lists sealed emissions from `tu4/tribunal/emisii/` and settlements from `tu4/tribunal/decontari/` with their SHA-256 chain. It never computes anything and shows what is available in the archive (the emissions and settlements folders are shipped; the `LANT.jsonl` chain file is not, so the chain card reports it as missing).

---

## 9. Data: what is bundled and how to update it

- All archives are plain **JSONL** files — one draw per line, e.g. `{"draw_date": "2000-09-14", "game": "joker", "numbers": [4, 27, 30, 32, 39], "joker": 7, …}` — validated at load time (6/49: six distinct numbers in 1..49; 5/40: six drawn in 1..40 with five on the ticket; Joker: five distinct in 1..45 plus one in 1..20). Duplicates are removed and draws are ordered chronologically.
- The **LIVE** source is a *frozen snapshot* in this archive. The original project refreshes it from an external collector that downloads official results from loto.ro every 30 minutes; that collector is a separate system and is **not** part of this release. The app never downloads anything by itself.
- To analyse newer draws, append lines in the same format to a copy of the JSONL file and point `QL649_DATA_649` at it (frozen source), or create a new version folder under `tu3/date/live/versiuni/` with a matching `MANIFEST_LIVE.json` and update `CURRENT_LIVE.json` (LIVE source). The parser refuses any version whose SHA-256 does not match its manifest.
- Provenance files (`tu3/date/MANIFEST_DATE.json`, `tu3/date/VERIFICARE_WEB_20261026.json`, `hs_v4/date_intl/PROVENIENTA_INTL.json`) record where each archive came from and its hash.

---

## 10. Files that are generated locally or available on request

| Path | Status | How to obtain |
|---|---|---|
| `rezultate/backtest_unic/` | generated | Run the walk-forward backtest once (tab 5 computes it on first use for the active source); then `python verify_ql649.py` produces the independent `PASS`. |
| `rezultate/sigilii/` | generated | Press **🔏 Sigilează variantele curente**. |
| `hs_v4/cache/` | generated | Created automatically by the HS-V4 engine. |
| `xi/rezultate/`, `kj_v5/rezultate/`, `tu4/rezultate/`, `bo649/…/rezultate/` etc. | research outputs, not shipped | Regenerable with each track's scripts, or request the archived copies: open a *documentation request* on [GitHub Issues](https://github.com/quantbotsoftware/quantum-lab-649/issues/new?template=documentation_request.md) or e-mail [contact@bot-tradingsoftware.com](mailto:contact@bot-tradingsoftware.com). Shared strictly AS-IS, when available. |
| Extended protocols/reports (`PLAN_QL649.md`, `PREINREGISTRARE_QL649.md`, `RAPORT_QL649.md`, TU3/TU4/XI protocols) | included | Read them from the archive root and sub-folders. |

---

## 11. Tests and verification

```bash
.venv/bin/python -m pytest -q -p no:cacheprovider tests/
```

Covers the parser (validation, de-duplication, day steps), the engine (exact 2×2 exceptional point, MCMC vs exact Boltzmann and vs exhaustive enumeration of all 13,983,816 combinations, causality, CPU/GPU parity), validation and the Streamlit AppTest UI. GPU tests are skipped automatically without CUDA. Expect 10–20 minutes on a GPU machine.

Protocol integrity: every `SIGILIU_*.json` contains the SHA-256 of the document it seals; recompute with `sha256sum <file>` and compare.

Update check (manual, no telemetry):

```bash
./check-updates.sh
```

---

## 12. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ERROR: python3 and/or streamlit not found` | Run `./setup_venv.sh` first, or set `PYTHON_BIN` / `STREAMLIT_BIN`. |
| Port 8649 already in use | Another instance is running: `./porneste_aplicatia.sh --stop`, or start with `QL649_PORT=8650 ./run_app_tu3.sh`. |
| Header shows `CPU (fallback)` although you have an NVIDIA GPU | PyTorch was installed without CUDA, or the driver is older than the wheel's CUDA version. Reinstall the matching wheel (§3.2) and check `nvidia-smi`. |
| `🛰 Sursa 6/49: LIVE indisponibilă (...)` | The LIVE snapshot could not be verified (modified or moved files). Select *înghețat (sigilat)* in the sidebar, or restore `tu3/date/live/`. The app never switches sources silently. |
| Pages **Strategii** / **Registru** show an integrity error | They require `xi/rezultate/H` and `xi/rezultate/F`, which are research outputs not included in the archive (§10). |
| Closed-track tabs show `—` / `NERULAT` | Normal: their result files are generated by the track scripts, not shipped. |
| First load takes many minutes | CPU fallback. Use `QL649_CONFIG=fast ./run_app_tu3.sh` to explore the interface with a reduced configuration. |
| Blank or frozen page after editing code | Streamlit caches modules in the server process. Restart with `./porneste_aplicatia.sh` (clears `__pycache__` and restarts). |
| Logs | `jurnal/app_*.log`, `jurnal/matrice_*.txt`, `jurnal/lansator_*.log`. |

---

## 13. Legal and scope reminder

- MIT License — you may use, modify and redistribute the code, keeping the copyright and license notice.
- `positive_claims_allowed = false` is not a slogan: the UI, the seals and the reports are built so that **no screen presents a combination as more likely to be drawn**. Lottery draws are independent random events; every ticket has the same probability.
- Nothing here is gambling, financial or legal advice. Play responsibly or, better, treat this as what it is — a mathematics and GPU-engineering sandbox.
- No technical support is provided. For *existing* documents only: [GitHub documentation request](https://github.com/quantbotsoftware/quantum-lab-649/issues/new?template=documentation_request.md) · [contact@bot-tradingsoftware.com](mailto:contact@bot-tradingsoftware.com).
- Permanent archive and citation: CERN Zenodo DOI [10.5281/zenodo.23992530](https://doi.org/10.5281/zenodo.23992530).
