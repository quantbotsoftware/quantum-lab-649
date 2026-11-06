#!/usr/bin/env bash
# Quantum Lab 649 — lansatorul pictogramei cu MATRICEA DE INIȚIALIZARE TU3 (AMENDAMENT_TU3_LN_01, sesiunea S2).
#
# Variantă nouă a lui porneste_aplicatia.sh (care rămâne byte-identic, înghețat în sigiliile TU3-VS/TU3-DD).
# Pașii 1–3 sunt aceiași; diferențele (§3 din amendament):
#   L2. pornește ./run_app_tu3.sh (matricea în jurnal/matrice_<UTC>Z.txt, apoi `exec ./run_app.sh`), pgid în
#       jurnal/app.pgid (același fișier ca lansatorul vechi ⇒ fiecare îl poate opri pe celălalt);
#   L3. jurnalul lansatorului: jurnal/lansator_tu3_<UTC>Z.log;
#   L4. după health ok copiază liniile „Integritate” și „Verdict matrice” ale ACESTEI porniri în jurnal și în
#       notificare; verdictul NU blochează pornirea (cod 0 la health ok, oricare ar fi verdictul);
#   L5. our_pids recunoaște și `bash ./run_app_tu3.sh` (faza dinaintea lui exec); oprirea omoară și grupul de
#       procese al fiecărui proces recunoscut care e lider de grup (fără orfani: python matrice_init.py, tee),
#       chiar și când jurnal/app.pgid lipsește.
# Variantele produsului = minime de energie, NU predicții. Calcul clasic. positive_claims_allowed=false.
#
# Utilizare:  ./porneste_aplicatia_tu3.sh          (repornește cu matricea + deschide browserul)
#             ./porneste_aplicatia_tu3.sh --stop   (oprește serverul)
set -uo pipefail

DIR="$(dirname "$(readlink -f "$0")")"
cd "$DIR" || exit 1
PORT="${QL649_PORT:-8649}"
URL="http://localhost:${PORT}"
ICON="$DIR/assets/quantum_lab_649.svg"
mkdir -p jurnal
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="jurnal/lansator_tu3_${STAMP}.log"
exec >>"$LOG" 2>&1
echo "[lansator] $(date -Is) dir=$DIR port=$PORT (TU3: run_app_tu3.sh, matricea de inițializare)"

notify() { notify-send -a "Quantum Lab 649" -i "$ICON" "$1" "${2:-}" 2>/dev/null || true; }

our_pids() {   # NUMAI serverul streamlit, run_app.sh și run_app_tu3.sh pornite din ACEST director (potrivire pe argv)
    local p argv a2
    for p in $(pgrep -f "streamlit|run_app(_tu3)?\.sh" 2>/dev/null); do
        [ "$p" = "$$" ] && continue
        [ "$(readlink -f "/proc/$p/cwd" 2>/dev/null)" = "$DIR" ] || continue
        argv="$(tr '\0' '\n' < "/proc/$p/cmdline" 2>/dev/null)"
        if grep -qx '.venv/bin/streamlit\|.*/\.venv/bin/streamlit' <<<"$(sed -n '1,2p' <<<"$argv")" \
           && grep -qx 'run' <<<"$argv" && grep -qx 'app.py' <<<"$argv"; then
            echo "$p"
        elif [ "$(sed -n '1p' <<<"$argv")" != "" ] && grep -qE '^(/usr/bin/|/bin/)?(env )?bash$' <<<"$(sed -n '1p' <<<"$argv")"; then
            # după `exec ./run_app.sh` din run_app_tu3.sh, argv[1] poate fi calea absolută $DIR/run_app.sh
            a2="$(sed -n '2p' <<<"$argv")"
            if grep -qE '^(\./)?run_app(_tu3)?\.sh$|/quantum_lab_649/run_app(_tu3)?\.sh$' <<<"$a2" \
               || [ "$a2" = "$DIR/run_app.sh" ] || [ "$a2" = "$DIR/run_app_tu3.sh" ]; then
                echo "$p"
            fi
        fi
    done
}

kill_groups() {   # $1 = semnal; grupul fiecărui proces recunoscut care este LIDERUL grupului (pgid = pid recunoscut)
    local sig="$1" own p g
    own="$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')"
    shift
    for p in "$@"; do
        g="$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')"
        [ -n "$g" ] && [ "$g" -gt 1 ] && [ "$g" != "$own" ] && [ "$g" = "$p" ] || continue
        echo "[lansator] $sig grup -$g"
        kill "-$sig" -- "-$g" 2>/dev/null || true
    done
}

stop_server() {
    local pids
    if [ -f jurnal/app.pgid ]; then
        kill -TERM -- "-$(cat jurnal/app.pgid)" 2>/dev/null || true
        rm -f jurnal/app.pgid
    fi
    pids="$(our_pids)"
    if [ -n "$pids" ]; then
        kill_groups TERM $pids
        kill -TERM $pids 2>/dev/null
    fi
    for _ in $(seq 1 20); do
        [ -z "$(our_pids)" ] && break
        sleep 0.5
    done
    pids="$(our_pids)"
    if [ -n "$pids" ]; then
        echo "[lansator] KILL $pids"
        kill_groups KILL $pids
        kill -KILL $pids 2>/dev/null
        sleep 1
    fi
    echo "[lansator] instanțe vechi oprite"
}

matrix_report() {   # fișierul de matrice al ACESTEI porniri (nume ≥ matrice_<STAMP>) + liniile de verdict
    local f best=""
    for f in jurnal/matrice_*Z.txt; do
        [ -f "$f" ] || continue
        [[ "$f" < "jurnal/matrice_${STAMP}" ]] && continue
        [[ -z "$best" || "$f" > "$best" ]] && best="$f"
    done
    MATRIX_FILE="$best"
    MATRIX_INTEG=""
    MATRIX_VERDICT=""
    if [ -n "$best" ]; then
        MATRIX_INTEG="$(grep -m1 'Integritate (sigiliu TU3-VS' "$best" | sed 's/^ *//')"
        MATRIX_VERDICT="$(grep -m1 'Verdict matrice:' "$best" | sed 's/^ *//')"
        echo "[lansator] matrice: fișier $best"
        echo "[lansator] matrice: ${MATRIX_INTEG:-linia de integritate lipsește}"
        echo "[lansator] matrice: ${MATRIX_VERDICT:-linia de verdict lipsește}"
    else
        echo "[lansator] matrice: ABSENTĂ (niciun jurnal/matrice_*Z.txt al acestei porniri)"
    fi
}

if [ "${1:-}" = "--stop" ]; then
    stop_server
    notify "Quantum Lab 649 oprit" "Serverul de pe portul ${PORT} a fost oprit."
    exit 0
fi

# 1. oprește instanța veche (garantează încărcarea codului nou)
stop_server
if ss -ltn "sport = :${PORT}" 2>/dev/null | grep -q LISTEN; then
    echo "[lansator] EROARE: portul ${PORT} este ocupat de alt proces"
    ss -ltnp "sport = :${PORT}"
    notify "Quantum Lab 649 — eroare" "Portul ${PORT} este ocupat de alt proces (vezi ${DIR}/${LOG})."
    exit 1
fi

# 2. fără bytecode vechi
find "$DIR" -path "$DIR/.venv" -prune -o -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
export PYTHONDONTWRITEBYTECODE=1

# 3. sintaxa tuturor modulelor aplicației + amprenta versiunii (fără a scrie .pyc)
PY_BIN="${PYTHON_BIN:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || command -v python3 || true )}"
if [ -z "$PY_BIN" ]; then
    notify "Quantum Lab 649 — eroare" "python3 lipsește: rulează ./setup_venv.sh (creează .venv cu toate dependențele)."
    exit 1
fi
CHECK="$("$PY_BIN" - "$DIR" <<'PY'
import hashlib, pathlib, sys, datetime
root = pathlib.Path(sys.argv[1])
skip = {".venv", "jurnal", "__pycache__", "incidente", "istoric"}
files = sorted(p for p in root.rglob("*.py") if not (set(p.relative_to(root).parts) & skip))
bad, h = [], hashlib.sha256()
for p in files:
    src = p.read_bytes()
    h.update(str(p.relative_to(root)).encode() + b"\0" + src)
    try:
        compile(src, str(p), "exec")
    except SyntaxError as e:
        bad.append(f"{p.relative_to(root)}:{e.lineno}: {e.msg}")
newest = max(files, key=lambda p: p.stat().st_mtime)
ts = datetime.datetime.fromtimestamp(newest.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
print(f"VERSION={h.hexdigest()[:12]}")
print(f"NEWEST={newest.relative_to(root)} ({ts})")
print(f"NFILES={len(files)}")
for b in bad:
    print(f"BAD={b}")
PY
)"
echo "$CHECK"
VERSION="$(sed -n 's/^VERSION=//p' <<<"$CHECK")"
NEWEST="$(sed -n 's/^NEWEST=//p' <<<"$CHECK")"
if grep -q '^BAD=' <<<"$CHECK"; then
    notify "Quantum Lab 649 — eroare de sintaxă" "$(grep '^BAD=' <<<"$CHECK" | head -3 | sed 's/^BAD=//')"
    exit 1
fi

# 4. pornire detașată, CU matricea de inițializare (run_app_tu3.sh → exec ./run_app.sh)
setsid ./run_app_tu3.sh >/dev/null 2>&1 < /dev/null &
SPID=$!
sleep 0.5
ps -o pgid= -p "$SPID" | tr -d ' ' > jurnal/app.pgid
echo "[lansator] pornit run_app_tu3.sh pid=$SPID pgid=$(cat jurnal/app.pgid) versiune=$VERSION"
notify "Quantum Lab 649 pornește…" "Versiunea ${VERSION} · matricea de inițializare TU3 · ultima modificare: ${NEWEST}"

for _ in $(seq 1 240); do
    if [ "$(curl -s --max-time 2 "${URL}/_stcore/health")" = "ok" ]; then
        echo "[lansator] health ok"
        matrix_report
        if [ -z "$MATRIX_FILE" ]; then
            notify "Quantum Lab 649 pornit — matrice absentă" "Versiunea ${VERSION} · vezi ${DIR}/${LOG}"
        elif grep -q 'TOATE 3 MODURILE READY' <<<"$MATRIX_VERDICT"; then
            notify "Quantum Lab 649 pornit — TOATE 3 MODURILE READY" \
                "${MATRIX_INTEG} · versiunea ${VERSION} · ${DIR}/${MATRIX_FILE}"
        else
            notify "Quantum Lab 649 pornit — ATENȚIE: matricea nu e complet READY" \
                "${MATRIX_VERDICT:-verdict lipsă} · ${MATRIX_INTEG} · ${DIR}/${MATRIX_FILE}"
        fi
        xdg-open "${URL}/?v=${VERSION}" >/dev/null 2>&1 &
        exit 0
    fi
    if ! kill -0 "$SPID" 2>/dev/null; then
        break
    fi
    sleep 0.5
done
echo "[lansator] EROARE: serverul nu a răspuns"
matrix_report
LAST="$(ls -t jurnal/app_*.log 2>/dev/null | head -1)"
[ -n "$LAST" ] && tail -20 "$LAST"
notify "Quantum Lab 649 — eroare la pornire" "Vezi ${DIR}/${LOG}"
exit 1
