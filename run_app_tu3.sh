#!/usr/bin/env bash
# QL649 / TU3 — lansator cu matricea de inițializare (PROTOCOL_TU3_VS §3, mutat aici prin AMENDAMENT_TU3_VS_01).
# run_app.sh rămâne byte-identic (martorul U8 al TU3-UI); acest lansator tipărește matricea, apoi îl execută.
set -euo pipefail
cd "$(dirname "$0")"
PY_BIN="${PYTHON_BIN:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || command -v python3 || true )}"
ST_BIN="${STREAMLIT_BIN:-$( [ -x .venv/bin/streamlit ] && echo .venv/bin/streamlit || command -v streamlit || true )}"
if [ -z "$PY_BIN" ] || [ -z "$ST_BIN" ]; then
    echo "[QL649] ERROR: python3 and/or streamlit not found. Run ./setup_venv.sh first (creates .venv with all dependencies), or set PYTHON_BIN / STREAMLIT_BIN." >&2
    exit 1
fi
PORT="${QL649_PORT:-8649}"
mkdir -p jurnal
# TU3-VS §3 (a): sintaxa modulelor TU3 (5/40, Joker, UI, matrice, validare)
"$PY_BIN" -m py_compile tu3/ui_tu3.py tu3/parser_multi.py tu3/motor_n.py tu3/motor_joker.py tu3/joker_entanglement.py tu3/matrice_init.py tu3/validare_tu3.py
# TU3-VS §3 (b): matricea de inițializare (fără motoare rulate, fără variante), în fișier separat de jurnalul serverului
MATRIX="jurnal/matrice_$(date -u +%Y%m%dT%H%M%SZ).txt"
if ! "$PY_BIN" -B tu3/matrice_init.py --address "${QL649_ADDRESS:-127.0.0.1}" --port "${PORT}" 2>&1 | tee "${MATRIX}"; then
    echo "[QL649] ATENȚIE: matricea de inițializare nu este complet READY/OK (vezi ${MATRIX}); serverul pornește oricum."
fi
exec ./run_app.sh
