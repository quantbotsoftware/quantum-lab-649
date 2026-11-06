"""Teste TU3-LN (AMENDAMENT_TU3_LN_01 §4): lansatorul pictogramei cu matricea de inițializare, `porneste_aplicatia_tu3.sh`.

Testele de proces rulează pe o COPIE IZOLATĂ a directorului aplicației (legături simbolice + lansatorul copiat ca fișier
real), pe un port liber ales dinamic (nu 8649), cu `notify-send`/`xdg-open` înlocuite în PATH de stub-uri care își
scriu argumentele într-un fișier. Funcția de oprire a lansatorului recunoaște procesele după director (`cwd`), deci
serverul utilizatorului din directorul real NU este atins (T4 verifică explicit).
Variantele produsului = minime de energie, NU predicții. positive_claims_allowed=false.
"""
import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "porneste_aplicatia_tu3.sh"
OLD = ROOT / "porneste_aplicatia.sh"
SEAL = json.loads((ROOT / "tu3" / "SIGILIU_TU3_LN.json").read_text())
DESKTOPS = [ROOT / "assets" / "quantum-lab-649.desktop",
            Path.home() / ".local" / "share" / "applications" / "quantum-lab-649.desktop",
            Path.home() / "Desktop" / "quantum-lab-649.desktop"]
NEW_EXEC = [f"Exec={LAUNCHER}", f"Exec={LAUNCHER} --stop"]
READY = "TOATE 3 MODURILE READY"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _listener_pid(port: int):
    out = subprocess.run(["ss", "-ltnpH", f"sport = :{port}"], capture_output=True, text=True).stdout
    for tok in out.split("pid=")[1:]:
        return int(tok.split(",")[0])
    return None


USER_PID_BEFORE = _listener_pid(8649)   # T4: serverul utilizatorului (dacă există) înaintea testelor


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _procs_in(d: Path) -> dict:
    """pid → argv pentru toate procesele cu cwd = d (directorul copiei izolate)."""
    found, target = {}, str(d.resolve())
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            if os.readlink(p / "cwd") == target:
                found[int(p.name)] = (p / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
    return found


def _wait(pred, timeout: float, step: float = 0.1) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(step)
    return pred()


@pytest.fixture()
def iso(tmp_path):
    """Copie izolată: legături simbolice spre intrările aplicației, jurnal/ nou, lansatorul copiat ca fișier real."""
    app = tmp_path / "ql649_copie"
    app.mkdir()
    for e in ROOT.iterdir():
        if e.name in {"jurnal", "__pycache__", LAUNCHER.name}:
            continue
        (app / e.name).symlink_to(e)
    shutil.copy2(LAUNCHER, app / LAUNCHER.name)
    (app / "jurnal").mkdir()
    stub = tmp_path / "stub_bin"
    stub.mkdir()
    calls = tmp_path / "apeluri.txt"
    for name in ("notify-send", "xdg-open"):
        f = stub / name
        f.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "{calls}"\n')
        f.chmod(0o755)
    port = _free_port()
    env = dict(os.environ, PATH=f"{stub}:{os.environ['PATH']}", QL649_PORT=str(port))
    env.pop("QL649_ADDRESS", None)
    yield {"app": app, "port": port, "env": env, "calls": calls, "sh": app / LAUNCHER.name}
    # curățenie defensivă: nu lăsa nimic pornit din copie, oricare ar fi rezultatul testului
    subprocess.run(["bash", str(app / LAUNCHER.name), "--stop"], env=env, timeout=60)
    for pid in _procs_in(app):
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def _stop_and_assert_clean(iso):
    r = subprocess.run(["bash", str(iso["sh"]), "--stop"], env=iso["env"], timeout=60)
    assert r.returncode == 0
    assert _wait(lambda: not _procs_in(iso["app"]), 10), _procs_in(iso["app"])
    assert _wait(lambda: not _port_open(iso["port"]), 10)


# ---------------- T1: static + fișiere protejate + .desktop ----------------
def test_T1_static_protected_and_desktop():
    assert subprocess.run(["bash", "-n", str(LAUNCHER)]).returncode == 0
    assert os.access(LAUNCHER, os.X_OK)
    src = LAUNCHER.read_text()
    assert "setsid ./run_app_tu3.sh" in src and "setsid ./run_app.sh" not in src
    assert "run_app(_tu3)?" in src and "jurnal/app.pgid" in src and "lansator_tu3_" in src
    # amendamentul sigilat înaintea codului
    assert _sha((ROOT / "tu3" / "AMENDAMENT_TU3_LN_01.md").read_bytes()) == SEAL["sha256"]
    assert SEAL["code_files_present"] == [] and SEAL["results_present"] is False
    assert SEAL["positive_claims_allowed"] is False
    # fișierele protejate byte-identice (inclusiv lansatorul vechi d8df19ce…)
    import sys   # TU3-L649 §5.4: fișier înghețat = identic SAU înlocuit sigilat (inlocuiri_tu3/v1)
    if str(ROOT / "tu3") not in sys.path:
        sys.path.insert(0, str(ROOT / "tu3"))
    import inlocuiri_tu3 as INL
    res = INL.resolve(SEAL["frozen_hashes"], ROOT)
    assert res["drift"] == [], res["drift"]
    for path, h in SEAL["frozen_external"].items():
        assert _sha(Path(path).read_bytes()) == h, path
    assert SEAL["frozen_hashes"]["porneste_aplicatia.sh"].startswith("d8df19ce")
    assert SEAL["frozen_hashes"]["run_app_tu3.sh"].startswith("e5f6c2c7")
    assert SEAL["frozen_hashes"]["run_app.sh"].startswith("a8f38cea")
    # .desktop: exact două linii Exec= spre lansatorul nou; restul octeților = cei de dinainte
    before = list(SEAL["desktop_before"].values())
    assert len(set(before)) == 1
    for d in DESKTOPS:
        txt = d.read_text()
        execs = [ln for ln in txt.splitlines() if ln.startswith("Exec=")]
        assert execs == NEW_EXEC, (d, execs)
        assert _sha(txt.replace(LAUNCHER.name, OLD.name).encode()) == before[0], d


# ---------------- T2: pornire cu matrice + oprire completă ----------------
def test_T2_start_matrix_verdict_and_stop(iso):
    app, port = iso["app"], iso["port"]
    r = subprocess.run(["bash", str(iso["sh"])], env=iso["env"], timeout=300)
    logs = sorted((app / "jurnal").glob("lansator_tu3_*Z.log"))
    log = logs[-1].read_text() if logs else ""
    assert r.returncode == 0, log
    assert "[lansator] health ok" in log
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=5) as h:
        assert h.read().decode() == "ok"
    mats = sorted((app / "jurnal").glob("matrice_*Z.txt"))
    assert len(mats) == 1
    mtxt = mats[0].read_text()
    assert f"Verdict matrice: {READY}" in mtxt and "Integritate (sigiliu TU3-VS" in mtxt and ": OK pe" in mtxt
    assert f"[lansator] matrice: fișier jurnal/{mats[0].name}" in log
    assert f"[lansator] matrice: Verdict matrice: {READY}" in log
    assert "[lansator] matrice: Integritate (sigiliu TU3-VS" in log
    assert _wait(lambda: "xdg-open" in iso["calls"].read_text(), 10)
    calls = iso["calls"].read_text()
    assert f"Quantum Lab 649 pornit — {READY}" in calls
    assert f"xdg-open http://localhost:{port}/?v=" in calls
    # după exec, procesul lider este `bash …/run_app.sh` (fostul `bash ./run_app_tu3.sh`, același pid = pgid);
    # argv[1] poate fi relativ sau calea absolută din directorul copiei
    pgid = int((app / "jurnal" / "app.pgid").read_text())
    procs = _procs_in(app)
    assert procs.get(pgid, [b""])[:2] in ([b"bash", b"./run_app.sh"], [b"bash", str(app / "run_app.sh").encode()]), procs
    # ramura nouă din our_pids recunoaște liderul și după exec, chiar fără app.pgid
    (app / "jurnal" / "app.pgid").unlink()
    assert any(b".venv/bin/streamlit" in a for argv in procs.values() for a in argv[:2])
    _stop_and_assert_clean(iso)
    assert any(f"[lansator] TERM grup -{pgid}" in p.read_text() for p in (app / "jurnal").glob("lansator_tu3_*Z.log"))
    assert "oprit" in iso["calls"].read_text()


# ---------------- T3: oprire în faza de matrice (înainte de exec), cu și fără app.pgid ----------------
@pytest.mark.parametrize("with_pgid", [True, False], ids=["cu_app_pgid", "fara_app_pgid"])
def test_T3_stop_during_matrix_phase_no_orphans(iso, with_pgid):
    app = iso["app"]
    launcher = subprocess.Popen(["bash", str(iso["sh"])], env=iso["env"])
    try:
        def in_matrix_phase():
            ps = _procs_in(app).values()
            return (any(argv[:2] == [b"bash", b"./run_app_tu3.sh"] for argv in ps)
                    and any(b"tu3/matrice_init.py" in argv for argv in ps))
        assert _wait(in_matrix_phase, 60, 0.05), _procs_in(app)
        pgid_file = app / "jurnal" / "app.pgid"
        assert _wait(pgid_file.exists, 5)
        if not with_pgid:
            pgid_file.unlink()
        r = subprocess.run(["bash", str(iso["sh"]), "--stop"], env=iso["env"], timeout=60)
        assert r.returncode == 0
        assert launcher.wait(timeout=60) == 1          # lansatorul vede serverul oprit ⇒ eroare de pornire, cod 1
    finally:
        if launcher.poll() is None:
            launcher.kill()
    assert _wait(lambda: not _procs_in(app), 10), _procs_in(app)
    assert not _port_open(iso["port"])
    stop_logs = sorted((app / "jurnal").glob("lansator_tu3_*Z.log"))
    if not with_pgid:
        assert any("[lansator] TERM grup -" in p.read_text() for p in stop_logs)


# ---------------- T4: serverul utilizatorului (8649) neatins ----------------
def test_T4_user_server_untouched():
    # același ascultător pe 8649 ca înaintea testelor (sau niciunul, dacă nu exista) — copia nu atinge directorul real
    assert _listener_pid(8649) == USER_PID_BEFORE
