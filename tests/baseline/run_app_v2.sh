#!/usr/bin/env bash
# QL649 — pornește dashboard-ul Streamlit și jurnalizează starea de boot.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${QL649_PORT:-8649}"
mkdir -p jurnal
LOG="jurnal/app_$(date -u +%Y%m%dT%H%M%SZ).log"
echo "[QL649] verificare sintaxă (parser.py engine.py validare.py app.py verify_ql649.py)…"
.venv/bin/python -m py_compile parser.py engine.py validare.py app.py verify_ql649.py
.venv/bin/python - <<'PY'
import torch
ok = torch.cuda.is_available()
print("[QL649] CUDA:", ok, torch.cuda.get_device_name(0) if ok else "fallback CPU")
PY
echo "[QL649] pornire pe http://localhost:${PORT}  (jurnal: ${LOG})"
.venv/bin/streamlit run app.py --server.address "${QL649_ADDRESS:-127.0.0.1}" --server.port "${PORT}" --server.headless true --browser.gatherUsageStats false 2>&1 | tee "${LOG}"
