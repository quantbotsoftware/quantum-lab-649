"""QL649 TU4-S27 (tu4/PROTOCOL_QUANTUM_S27.md §2): sonda de fază, STRICT read-only, ZERO scrieri.

Spune în ce fază e lanțul extern (arhiva LIVE → judecătorul → decontarea țintei → emisia țintei următoare) și dacă gărzile
care protejează C1 (S25) și B5 (S20) sunt intacte. Scrie numai pe stdout. Nu creează/modifică/șterge fișiere, nu ia lock
exclusiv (numai flock PARTAJAT, prin raport_decontare_s24.shared_lock), nu rulează binarul Rust, nu pornește/oprește
unități systemd (cel mult `systemctl --user show`). Nu citește numerele extragerilor. Verdictele C1/B5/decontare rămân
EXCLUSIV ale primului pas neschimbat (primul_pas_S26.sh → Q7L, b5_s24.sh, raport_decontare_s24.py).

Rulare: /usr/bin/python3 -B tu4/s27/sonda_s27.py [--trib D] [--incidente D] [--live D] [--judecator F] [--acum ISO]
        [--tinta-decontare 2026-10-29] [--tinta-emisie 2026-11-01] [--fara-systemd]
rc: 0 = fază normală, 1 = ANOMALIE, 3 = UNKNOWN_FEREASTRA. positive_claims_allowed=false.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True        # niciun __pycache__ la importurile de mai jos

import argparse  # noqa: E402
import datetime as dt  # noqa: E402
import fcntl  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

QL = Path("${QL649_ROOT:-.}")
ROOT = Path("${LOTO_RO_ROOT:-.}")
TZ = ZoneInfo("Europe/Bucharest")
GAMES = ("649", "540", "joker")
EMISSION_SLOTS = ((8, 20), (12, 20), (15, 20))
DRAW_LOCAL = (18, 30)
FINAL_SLOT_LOCAL = (15, 20)
MARGIN = dt.timedelta(minutes=15)
BIN = ROOT / "rust_core/target/release/rust-singularity-core"
BIN_SHA = "c20fdcd2f7f237578d1f0ea85c05f9bf6b32a888d228e4443b6756dd1d43fd9e"
CFG = ROOT / "rust_core/.cargo/config.toml"
MAN22 = QL / "tu4/rezultate/S22/MANIFEST_RUST_CORE_20261028T032900Z.json"
SEAL27 = QL / "tu4/SIGILIU_TU4_S27.json"

sys.path.insert(0, str(QL / "tu4/s25"))
sys.path.insert(0, str(QL / "tu4/s24"))
import raport_decontare_s24 as RD  # noqa: E402  (cod S24 înghețat prin hash; numai funcții de citire)
import verifica_s25 as V25  # noqa: E402  (cod S25 înghețat prin hash; numai scut_lant)

NEXT = {
    "FAZA_0_ASTEAPTA_DECONTAREA": "nimic de rulat; după extragere și după ce arhiva LIVE conține ținta decontării, "
                                  "judecătorul decontează la :00/:30; rulați din nou sonda (în afara ferestrelor)",
    "FAZA_1_DECONTARE_PARTIALA": "decontare în curs; reveniți cu sonda după următoarea rulare a judecătorului",
    "FAZA_2_DECONTARE_COMPLETA": "rulați primul pas NESCHIMBAT (primul_pas_S26.sh + verifica_s25.py q7l) în afara "
                                 "ferestrelor ⇒ DECONTARE_COMPLETA 3/3; apoi raportul de decontare; emisia țintei "
                                 "următoare vine la un slot 08:20/12:20/15:20 Europe/Bucharest",
    "FAZA_3_EMISIE_PARTIALA": "emisie parțială; așteptați slotul următor și rulați din nou sonda",
    "FAZA_4_EMISIE_COMPLETA": "rulați primul pas NESCHIMBAT în afara ferestrelor ⇒ C1 (Q7L 11/11, S16–S19 drift numai "
                              "LANT) și B5_RC=0; apoi RAPORT_S25_INCHIDERE.md; abia apoi tu4/incidente/S26_* (și S27_*)",
    "ANOMALIE": "citiți abaterile de mai sus; nu rulați altceva; înregistrați incidentul în tu4/rezultate/ (directorul "
                "tu4/incidente/ amânat până la închiderea C1)",
}


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def at_local(d: dt.date, hm: tuple[int, int]) -> dt.datetime:
    return dt.datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=TZ).astimezone(dt.timezone.utc)


def window(now: dt.datetime, draw_utc: dt.datetime) -> str | None:
    """Fereastra interzisă §1 care conține `now` (inclusiv capetele) sau None."""
    d0 = now.astimezone(TZ).date()
    for k in (-1, 0, 1):
        for hm in EMISSION_SLOTS:
            t = at_local(d0 + dt.timedelta(days=k), hm)
            if abs(now - t) <= MARGIN:
                return f"emisie {t.strftime('%Y-%m-%dT%H:%MZ')}"
    if abs(now - draw_utc) <= MARGIN:
        return f"extragere {draw_utc.strftime('%Y-%m-%dT%H:%MZ')}"
    return None


def path_of(rel: str) -> Path:
    return Path(rel) if rel.startswith("/") else (ROOT / rel if rel.startswith("rust_core/") else QL / rel)


def last_json_line(p: Path) -> dict | None:
    if not p.is_file():
        return None
    ls = [x for x in p.read_bytes().splitlines() if x.strip()]
    try:
        return json.loads(ls[-1]) if ls else None
    except Exception:  # noqa: BLE001
        return {"eroare": "ultima linie nu e JSON"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trib", type=Path, default=QL / "tu4/tribunal")
    ap.add_argument("--incidente", type=Path, default=QL / "tu4/incidente")
    ap.add_argument("--live", type=Path, default=QL / "tu3/date/live")
    ap.add_argument("--judecator", type=Path, default=QL / "tu4/judecator.py")
    ap.add_argument("--acum", default=None, help="ISO UTC (numai pentru fixture)")
    ap.add_argument("--tinta-decontare", default="2026-10-29")
    ap.add_argument("--tinta-emisie", default="2026-11-01")
    ap.add_argument("--fara-systemd", action="store_true")
    a = ap.parse_args(argv)

    now = (dt.datetime.fromisoformat(a.acum.replace("Z", "+00:00")) if a.acum
           else dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    td_dec = dt.date.fromisoformat(a.tinta_decontare)
    td_em = dt.date.fromisoformat(a.tinta_emisie)
    draw = at_local(td_dec, DRAW_LOCAL)
    print(f"SONDA_S27 acum={now.strftime('%Y-%m-%dT%H:%M:%SZ')} tinta_decontare={td_dec} extragere={draw:%Y-%m-%dT%H:%MZ} "
          f"tinta_emisie={td_em}")

    # W — fereastra (înaintea oricărei citiri a tribunalului)
    w = window(now, draw)
    if w:
        print(f"W FEREASTRA_INTERZISA {w} (±15 min); tribunalul NU a fost citit")
        print("URMATORUL_PAS=reveniți după fereastră")
        print("SONDA_S27_FAZA=UNKNOWN_FEREASTRA RC=3 positive_claims_allowed=false")
        return 3
    print("W liberă")

    anomalies: list[str] = []
    seal = json.loads(SEAL27.read_text(encoding="utf-8"))

    # G1 — incidentele
    found = sorted(d.name for d in a.incidente.iterdir() if d.is_dir()) if a.incidente.is_dir() else []
    want = seal["incidents_before"]
    extra, missing = sorted(set(found) - set(want)), sorted(set(want) - set(found))
    ok = not extra and not missing
    print(f"G1 incidente {'OK' if ok else 'FAIL'} n={len(found)} in_plus={extra} lipsa={missing} "
          f"S26_absente={not any(x.startswith('S26_') for x in found)}")
    if not ok:
        anomalies.append("G1 incidente")

    # G2 — sursele Rust
    man = json.loads(MAN22.read_text(encoding="utf-8"))["sources"]
    bad = [f for f, d in man.items()
           if path_of(f).stat().st_mode & 0o777 != 0o444 or sha_file(path_of(f)) != d["sha256"]]
    print(f"G2 surse_rust {'OK' if len(man) == 27 and not bad else 'FAIL'} {len(man) - len(bad)}/{len(man)} 0444+sha {bad}")
    if len(man) != 27 or bad:
        anomalies.append("G2 surse Rust")

    # G3 — binarul
    bs = sha_file(BIN) if BIN.is_file() else None
    print(f"G3 binar {'OK' if bs == BIN_SHA else 'FAIL'} {bs}")
    if bs != BIN_SHA:
        anomalies.append("G3 binar")

    # G4 — gazda (informativ, static)
    flags = [ln.split(":", 1)[1].split() for ln in Path("/proc/cpuinfo").read_text().splitlines() if ln.startswith("flags")]
    n_avx2, n_fma = sum("avx2" in f for f in flags), sum("fma" in f for f in flags)
    native = "target-cpu=native" in CFG.read_text(encoding="utf-8") if CFG.is_file() else False
    print(f"G4 gazda_static cpu={os.cpu_count()} avx2={n_avx2} fma={n_fma} target-cpu=native:{native} "
          "(informativ; nu dovedește execuția instrucțiunilor)")

    # T1–T5 sub lockul PARTAJAT
    lock = RD.shared_lock(a.trib) if a.trib.is_dir() else None
    try:
        before, nfiles = RD.tree_hash(a.trib)
        scut = V25.scut_lant(a.trib)
        lant = [json.loads(x) for x in (a.trib / "LANT.jsonl").read_bytes().splitlines()] \
            if (a.trib / "LANT.jsonl").is_file() else []
        dec = RD.analyze(a.trib, td_dec.isoformat(), RD.ju_seal_sha(a.judecator))
        em_games = sorted({o.get("game") for o in lant if o.get("target_date") == td_em.isoformat()
                           and isinstance(o.get("file"), str) and (a.trib / o["file"]).is_file()})
        ju_last = last_json_line(a.trib / "JUDECATOR_RULARI.jsonl")
        em_last = last_json_line(a.trib / "RULARI.jsonl")
        after, _ = RD.tree_hash(a.trib)
    finally:
        if lock:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()

    p20 = V25.LS["LANT_PREFIX_S20"]["lines"]
    print(f"T1 scut_lant {'OK' if not scut else 'FAIL'} linii={len(lant)} prefix_S20={p20} "
          f"noi={[(o.get('game'), o.get('target_date')) for o in lant[p20:]]} abateri={scut}")
    if scut:
        anomalies.append("T1 scut LANT")
    n_dec = dec["n_decontate"]
    print(f"T2 decontare {dec['verdict']} {n_dec}/3 linii_DECONTARI={dec['n_linii_DECONTARI']} lipsa={dec['lipsa']} "
          f"statusuri={ {g: x['status'] for g, x in dec['jocuri'].items()} }")
    if dec["verdict"] == "DECONTARE_FAIL":
        anomalies.append("T2 decontare FAIL: " + ", ".join(c["check"] for c in dec["checks"] if not c["pass"]))
    n_em = len(em_games)
    print(f"T3 emisie {td_em} {n_em}/3 jocuri={em_games}")

    # T4 — sursa externă (informativ)
    cur = None
    if (a.live / "CURRENT_LIVE.json").is_file():
        try:
            cur = json.loads((a.live / "CURRENT_LIVE.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cur = None
    last = {g: ((cur or {}).get("games", {}).get(g) or {}).get("last_date") for g in GAMES}
    min_last = min((v for v in last.values() if v), default=None)
    print(f"T4 arhiva_LIVE updated_utc={(cur or {}).get('updated_utc')} last_date={last}")
    if ju_last is not None:
        print(f"T4 judecator ultima={ju_last.get('utc')} action={ju_last.get('action')} rc={ju_last.get('rc')} "
              f"pending={[(x.get('game'), x.get('target_date'), x.get('reason')) for x in ju_last.get('pending') or []]}")
    else:
        print("T4 judecator ultima=None")
    if em_last is not None:
        print(f"T4 emitator ultima={em_last.get('utc')} {em_last.get('game')} {em_last.get('target_date')} "
              f"action={em_last.get('action')} reason={em_last.get('reason')}")
    else:
        print("T4 emitator ultima=None")
    if not a.fara_systemd:
        r = subprocess.run(["systemctl", "--user", "show", "-p", "Result", "-p", "ExecMainExitTimestamp",
                            "loto-actualizare.service"], capture_output=True, text=True)
        print("T4 loto-actualizare " + " ".join(r.stdout.split()))

    # T5 — arborele tribunalului
    same = before == after
    print(f"T5 tribunal_neatins {'OK' if same else 'FAIL'} fisiere={nfiles} arbore={before[:12]}…")
    if not same:
        anomalies.append("T5 tribunal modificat în timpul citirii")

    # Faza
    if anomalies:
        faza, rc = "ANOMALIE", 1
    elif n_em == 3:
        faza, rc = "FAZA_4_EMISIE_COMPLETA", 0
    elif n_em:
        faza, rc = "FAZA_3_EMISIE_PARTIALA", 0
    elif n_dec == 3:
        faza, rc = "FAZA_2_DECONTARE_COMPLETA", 0
    elif n_dec:
        faza, rc = "FAZA_1_DECONTARE_PARTIALA", 0
    else:
        faza, rc = "FAZA_0_ASTEAPTA_DECONTAREA", 0
    for x in anomalies:
        print(f"ABATERE {x}")

    # Avertismente (informative)
    if min_last is not None and now >= draw + dt.timedelta(hours=2) and n_dec < 3 and min_last < td_dec.isoformat():
        print(f"AVERTISMENT_DECONTARE_BLOCATA arhiva LIVE se oprește la {min_last} < {td_dec}, la ≥ 2 h după extragere; "
              "judecătorul nu poate deconta până nu intră extragerea (vezi garda gpu-v1 din loto-actualizare)")
    if min_last is not None and n_em < 3 and min_last < td_dec.isoformat():
        fin = at_local(td_em, FINAL_SLOT_LOCAL)
        print(f"AVERTISMENT_EMISIE_AMANATA arhiva LIVE la {min_last} < {td_dec}: dacă rămâne așa, emite.py amână emisia "
              f"{td_em} până la fereastra finală (slotul {fin:%Y-%m-%dT%H:%MZ}), nu vineri")

    print(f"URMATORUL_PAS={NEXT[faza]}")
    print(f"SONDA_S27_FAZA={faza} RC={rc} positive_claims_allowed=false")
    return rc


if __name__ == "__main__":
    sys.exit(main())
