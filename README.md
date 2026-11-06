# Quantum Lab 649 — Classical Combinatorial & Spectral Observatory (Python + PyTorch + Streamlit)

![License: MIT](https://img.shields.io/badge/license-MIT-10b981) ![Claims: None](https://img.shields.io/badge/positive__claims__allowed-false-ef4444) [![Donations: Good Samaritans](https://img.shields.io/badge/donations-good%20samaritans-ec4899)](https://ko-fi.com/quantbotsoftware)

> ⚠️ **STRICTLY AS-IS · CLASSICAL COMPUTATION ONLY · DOES NOT PREDICT WINNING NUMBERS (`positive_claims_allowed = false`):**
> All operators in this repository (non-Hermitian walks, Poincaré disk embeddings, Kuramoto oscillators, Boltzmann/QUBO energy minima, Johnson scheme / Krawtchouk spectral projections, and 8,192-history Null Multiverse validation) are **100% classical mathematical/combinatorial explorations**. Lottery draws are independent random physical events where every combination has identical probability. **No warranty, no technical support, and zero financial/prize claims.** See [DISCLAIMER.md](DISCLAIMER.md).

## Quick Start (English)

```bash
./setup_venv.sh
./run_app_tu3.sh
# Open http://127.0.0.1:8649
```

To install the Linux desktop launcher (`quantum-lab-649.desktop`):
```bash
./desktop/install-desktop-shortcut.sh
```

## 🖼️ UI Reference Screenshots (Running Observatory Confirmation)

> *Illustrative engineering confirmation only (`positive_claims_allowed = false`) — showing the running Streamlit + PyTorch GPU mathematical observatory; does NOT predict lottery numbers.*

- 🌐 **Full Interactive UI Gallery:** [https://bot-tradingsoftware.com/#screenshots](https://bot-tradingsoftware.com/#screenshots)

![Quantum Lab 649 Wavefunction & Born Amplitudes](https://bot-tradingsoftware.com/img/screenshots/quantum-lab-649-1-wavefunction.png)

![Quantum Lab 649 Poincare Disc & 3D Amplituhedron](https://bot-tradingsoftware.com/img/screenshots/quantum-lab-649-2-poincare-amplituhedron.png)

![Quantum Lab 649 Terminal Equilibrium Configurations](https://bot-tradingsoftware.com/img/screenshots/quantum-lab-649-3-quantum-limit.png)

## ❤️ Voluntary Donations ("Good Samaritans")
100% free & open-source under MIT. If the mathematical/PyTorch/Streamlit modules help your own research or personal projects:
- 🌐 **Hub & Donations:** [https://bot-tradingsoftware.com/#donate](https://bot-tradingsoftware.com/#donate)

---

# QL649 — „Quantum Lab 649”

Laborator exploratoriu pentru Loto 6/49 RO: motor clasic accelerat pe GPU (PyTorch/CUDA, RTX 5060 Laptop)
cu operatori de inspirație cuantică și un dashboard Streamlit în stil cyberpunk. Pista e separată de DL-649,
care rămâne înghețată.

> Calcul **clasic**. Inspirația cuantică este strict matematică. Variantele sunt minimele energiei modelului,
> nu combinații cu șanse mai mari. `positive_claims_allowed=false`. Fără promisiuni de câștig.

## Pornire

```bash
./setup_venv.sh && ./run_app_tu3.sh
# apoi deschide http://localhost:8649
```

## Module

| Fișier | Rol |
|---|---|
| `parser.py` | ingestie JSONL în RAM, validare, deduplicare, ordonare cronologică, pași pe zile, tensori `cuda` (fallback CPU numai la eroare de driver) |
| `engine.py` | O1 walk non-hermitic + puncte excepționale · O2 volume „Amplituhedron” · O3 disc Poincaré + ancore · O4 Kuramoto cu salturi de interferență · O5 colaps Born + filtru Boltzmann pe 50 000 de replici · O6 MCMC paralel tempering (10 000 de pași) + QUBO pentru 3 variante |
| `validare.py` | Multiversul Nul (8192 de istorii) + SCI, backtest walk-forward cauzal unic, porți, pipeline pe universuri nule |
| `verify_ql649.py` | verificator independent NumPy fp64 (fără import din motor) |
| `app.py` | dashboard: Colaps · Singularitate hiperbolică & Amplituhedron · Limita Cuantică (3 variante) · Multiversul Nul · Mașina Timpului · Ablație & Sigiliu temporal |
| `raport.py` | generează `RAPORT_QL649.md` din artefactele sigilate |

## Rigoare

- Protocol [PREINREGISTRARE_QL649.md](PREINREGISTRARE_QL649.md), sigilat înainte de cod/calcule ([SIGILIU_PROTOCOL.json](SIGILIU_PROTOCOL.json)), plus [AMENDAMENT_01.md](AMENDAMENT_01.md) și [AMENDAMENT_02.md](AMENDAMENT_02.md).
- Teste: `.venv/bin/python -m pytest -q -p no:cacheprovider tests/` (parser, motor: EP exact 2×2, MCMC vs Boltzmann exact și vs enumerarea exhaustivă a celor 13 983 816 combinații, cauzalitate, paritate CPU/GPU; validare; AppTest UI). Testul UI pe configurația protocolului se rulează cu `QL649_UI_PROTOCOL=1`.
- Rezultate: [RAPORT_QL649.md](RAPORT_QL649.md), `rezultate/backtest_unic/` (o singură rulare, cu manifest și verificare independentă).

## Pictograma de pornire (lansator)

- Pictograma „Quantum Lab 649” (desktop + App Library) rulează `porneste_aplicatia.sh` DIN REPO (nu o copie), deci
  preia automat orice modificare viitoare a aplicației sau a lansatorului.
- La fiecare clic: oprește instanța veche a serverului (cod/cache vechi în memorie), șterge `__pycache__`, verifică
  sintaxa TUTUROR fișierelor `.py` (inclusiv module noi), pornește `./run_app.sh`, așteaptă `/_stcore/health`, deschide
  http://localhost:8649 și notifică amprenta versiunii (sha256 peste toate `.py`) + ultimul fișier modificat.
- Clic dreapta → „Oprește serverul Quantum Lab 649” (`porneste_aplicatia.sh --stop`). Jurnal: `jurnal/lansator_*.log`.
- Fișierele sursă ale pictogramei: `assets/quantum_lab_649.svg`, `assets/quantum-lab-649.desktop` (instalat în
  `~/.local/share/applications/` și `~/Desktop/`; dacă se mută repo-ul, se actualizează căile din `.desktop`).

