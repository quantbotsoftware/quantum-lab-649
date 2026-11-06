#!/usr/bin/env bash
# Quantum Lab 649 — lansatorul pictogramei (desktop / App Library).
#
# Garantează că pornește MEREU varianta curentă a aplicației, inclusiv după modificări viitoare:
#   1. oprește orice instanță veche a serverului Streamlit din acest director (modulele Python importate și
#      cache-urile st.cache_* trăiesc în procesul serverului, deci o instanță veche ar servi cod vechi);
#   2. șterge bytecode-ul vechi (__pycache__) și pornește cu PYTHONDONTWRITEBYTECODE=1;
#   3. verifică sintaxa TUTUROR fișierelor .py ale aplicației (nu o listă fixă, ca să includă și module viitoare);
#   4. pornește ./run_app.sh detașat, așteaptă /_stcore/health și deschide browserul;
#   5. jurnalizează amprenta versiunii (sha256 peste toate .py) și ultimul fișier modificat.
# Pictograma apelează acest fișier din repo (nu o copie), deci orice modificare viitoare a lui sau a aplicației
# este preluată automat.
#
# Utilizare:  ./porneste_aplicatia.sh          (repornește + deschide browserul)
#             ./porneste_aplicatia.sh --stop   (oprește serverul)
set -uo pipefail

DIR="$(dirname "$(readlink -f "$0")")"
cd "$DIR" || exit 1
PORT="${QL649_PORT:-8649}"
URL="http://localhost:${PORT}"
ICON="$DIR/assets/quantum_lab_649.svg"
mkdir -p jurnal
LOG="jurnal/lansator_$(date -u +%Y%m%dT%H%M%SZ).log"
exec >>"$LOG" 2>&1
echo "[lansator] $(date -Is) dir=$DIR port=$PORT"

notify() { notify-send -a "Quantum Lab 649" -i "$ICON" "$1" "${2:-}" 2>/dev/null || true; }

our_pids() {   # NUMAI serverul streamlit și run_app.sh pornite din ACEST director (potrivire exactă pe argv)
    local p argv
    for p in $(pgrep -f "streamlit|run_app\.sh" 2>/dev/null); do
        [ "$p" = "$$" ] && continue
        [ "$(readlink -f "/proc/$p/cwd" 2>/dev/null)" = "$DIR" ] || continue
        argv="$(tr '\0' '\n' < "/proc/$p/cmdline" 2>/dev/null)"
        if grep -qx '.venv/bin/streamlit\|.*/\.venv/bin/streamlit' <<<"$(sed -n '1,2p' <<<"$argv")" \
           && grep -qx 'run' <<<"$argv" && grep -qx 'app.py' <<<"$argv"; then
            echo "$p"
        elif [ "$(sed -n '1p' <<<"$argv")" != "" ] && grep -qE '^(/usr/bin/|/bin/)?(env )?bash$' <<<"$(sed -n '1p' <<<"$argv")" \
           && grep -qE '^(\./)?run_app\.sh$|/quantum_lab_649/run_app\.sh$' <<<"$(sed -n '2p' <<<"$argv")"; then
            echo "$p"
        fi
    done
}

stop_server() {
    local pids
    if [ -f jurnal/app.pgid ]; then
        kill -TERM -- "-$(cat jurnal/app.pgid)" 2>/dev/null || true
        rm -f jurnal/app.pgid
    fi
    pids="$(our_pids)"
    [ -n "$pids" ] && kill -TERM $pids 2>/dev/null
    for _ in $(seq 1 20); do
        [ -z "$(our_pids)" ] && break
        sleep 0.5
    done
    pids="$(our_pids)"
    [ -n "$pids" ] && { echo "[lansator] KILL $pids"; kill -KILL $pids 2>/dev/null; sleep 1; }
    echo "[lansator] instanțe vechi oprite"
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
CHECK="$(.venv/bin/python - "$DIR" <<'PY'
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

# 4. pornire detașată
setsid ./run_app.sh >/dev/null 2>&1 < /dev/null &
SPID=$!
sleep 0.5
ps -o pgid= -p "$SPID" | tr -d ' ' > jurnal/app.pgid
echo "[lansator] pornit pid=$SPID pgid=$(cat jurnal/app.pgid) versiune=$VERSION"
notify "Quantum Lab 649 pornește…" "Versiunea ${VERSION} · ultima modificare: ${NEWEST}"

for _ in $(seq 1 240); do
    if [ "$(curl -s --max-time 2 "${URL}/_stcore/health")" = "ok" ]; then
        echo "[lansator] health ok"
        xdg-open "${URL}/?v=${VERSION}" >/dev/null 2>&1 &
        exit 0
    fi
    if ! kill -0 "$SPID" 2>/dev/null; then
        break
    fi
    sleep 0.5
done
echo "[lansator] EROARE: serverul nu a răspuns"
LAST="$(ls -t jurnal/app_*.log 2>/dev/null | head -1)"
[ -n "$LAST" ] && tail -20 "$LAST"
notify "Quantum Lab 649 — eroare la pornire" "Vezi ${DIR}/${LOG}"
exit 1
