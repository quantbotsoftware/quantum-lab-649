"""Ecranul „Registrul pe hârtie” (protocol xi/PROTOCOL_XI_HR.md). Pagină Streamlit separată (MPA, directorul pages/).

Citește NUMAI registrul F (xi/rezultate/F/LANT_STRATEGII.jsonl) și decontările lui (DECONTARI_STRATEGII.jsonl, dacă
există), verifică lanțurile de hash-uri și afișează miza, plățile și netul pe țintă, pe strategie și pe familie.
Nu afișează bilete, liste de numere sau numerele extrase. Nu importă niciun modul al proiectului (nici motorul GPU,
nici produsul separat) — numai biblioteca standard și Streamlit. positive_claims_allowed=false. Calcul clasic.
"""
import sys

sys.dont_write_bytecode = True

import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402

import streamlit as st  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
F_DIR = ROOT / "xi/rezultate/F"
REG = F_DIR / "LANT_STRATEGII.jsonl"
DEC = F_DIR / "DECONTARI_STRATEGII.jsonl"
PROTO_HR = ROOT / "xi/PROTOCOL_XI_HR.md"
PROTO_F_SHA = "ba74568f40fa62303bef59bbd7c23d46b527ec53e00297c59f71670a0b7d3220"
ZERO = "0" * 64
JOC_RO = {"649": "Loto 6/49", "540": "Loto 5/40", "joker": "Joker"}
FAMILII = ["C1", "C3", "RND"]
FAM_RO = {"C1": "C1 — designuri garantate", "C3": "C3 — portofolii sub buget", "RND": "RND — control aleator"}
HEADERS = ["1. Țintele înregistrate", "2. Rezultatul pe strategie", "3. Pe familii", "4. Ce înseamnă"]
TEXT_FIX = ("Joc pe hârtie, fără bani: strategiile se înregistrează înaintea extragerii și se decontează la plățile "
            "oficiale publicate. Nu este o prognoză de numere și nici un sfat de joc; pierderea medie este rezultatul "
            "așteptat (ρ < 1), iar câteva extrageri sunt zgomot.")


class Abatere(Exception):
    pass


def canonic(o: dict) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def citeste_lant(p: Path, obligatoriu: bool) -> list:
    if not p.exists():
        if obligatoriu:
            raise Abatere(f"{p.name} lipsește")
        return []
    rows, prev = [], ZERO
    for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines()):
        try:
            o = json.loads(ln)
        except ValueError:
            raise Abatere(f"{p.name}: linia {i} nu este JSON") from None
        core = {k: v for k, v in o.items() if k != "sha256"}
        if ln != canonic(o) or o.get("seq") != i or o.get("prev_sha256") != prev or o.get("sha256") != sha(
                canonic(core).encode("utf-8")):
            raise Abatere(f"{p.name}: lanț invalid la linia {i}")
        prev = o["sha256"]
        rows.append(o)
    return rows


def incarca() -> tuple:
    reg = citeste_lant(REG, True)
    if not reg:
        raise Abatere("registrul este gol")
    for r in reg:
        if r.get("tip") != "INREGISTRARE" or r.get("protocol_sha256") != PROTO_F_SHA:
            raise Abatere(f"registru: linia {r.get('seq')} nu este o înregistrare XI-F")
    dec = citeste_lant(DEC, False)
    by_seq = {r["seq"]: r for r in reg}
    vazute = set()
    for d in dec:
        ref = d.get("ref_seq")
        if (d.get("tip") != "DECONTARE" or d.get("status") not in ("DECONTAT", "VOID") or ref not in by_seq
                or by_seq[ref]["sha256"] != d.get("ref_sha256") or ref in vazute):
            raise Abatere(f"decontări: linia {d.get('seq')} nu corespunde registrului")
        vazute.add(ref)
    return reg, dec


def lei(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ") + " lei"


def pct(num: float, den: float) -> str:
    return f"{100 * num / den:.1f}%" if den else "—"


def table(head: list, rows: list) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


st.set_page_config(page_title="QL649 · Registrul pe hârtie", page_icon="🧾", layout="wide")
st.title("Registrul pe hârtie — strategiile pe extrageri viitoare")

try:
    REGISTRU, DECONTARI = incarca()
except (Abatere, OSError) as exc:
    st.error(f"Registrul F nu trece verificarea de integritate ({exc}). Nu se afișează nimic.")
    st.stop()

st.warning(TEXT_FIX)
proto_hr = sha(PROTO_HR.read_bytes())[:12] if PROTO_HR.exists() else "lipsă"
cap_d = f"`{DECONTARI[-1]['sha256'][:16]}…` ({len(DECONTARI)} linii)" if DECONTARI else "— (nicio decontare)"
st.caption(f"registru `{REGISTRU[-1]['sha256'][:16]}…` ({len(REGISTRU)} linii) · decontări {cap_d} · protocol XI-HR "
           f"`{proto_hr}…` · protocol XI-F `{PROTO_F_SHA[:12]}…` · calcul clasic, numai citire")

stare = {d["ref_seq"]: d for d in DECONTARI}

# 1 ---------------------------------------------------------------------------------------------------------------
st.header(HEADERS[0])
rows = []
for data in sorted({r["tinta"]["data"] for r in REGISTRU}):
    rr = [r for r in REGISTRU if r["tinta"]["data"] == data]
    dec = [r for r in rr if r["seq"] in stare and stare[r["seq"]]["status"] == "DECONTAT"]
    void = [r for r in rr if r["seq"] in stare and stare[r["seq"]]["status"] == "VOID"]
    asteapta = len(rr) - len(dec) - len(void)
    jocuri = ", ".join(JOC_RO[g] for g in ("649", "540", "joker") if any(r["tinta"]["joc"] == g for r in rr))
    plati = sum(stare[r["seq"]]["rezultat"]["plata"] for r in dec)
    net = sum(stare[r["seq"]]["rezultat"]["net"] for r in dec)
    rows.append([data, jocuri, str(len(rr)), str(sum(r["nr_bilete"] for r in rr)), lei(sum(r["miza"] for r in rr)),
                 rr[0]["cutoff_utc"], max(r["utc_inregistrare"] for r in rr), str(len(dec)),
                 f"ÎN AȘTEPTARE: {asteapta}" if asteapta else "0", f"VOID: {len(void)}" if void else "0",
                 lei(plati) if dec else "—", lei(net) if dec else "—"])
st.markdown(table(["Data", "Jocuri", "Strategii", "Bilete", "Miză", "Cutoff (UTC)", "Înregistrat (UTC)", "Decontate",
                   "În așteptare", "VOID", "Plăți (decontate)", "Net (decontate)"], rows))

# 2 ---------------------------------------------------------------------------------------------------------------
st.header(HEADERS[1])
agg: dict = {}
for r in REGISTRU:
    d = stare.get(r["seq"])
    if d is None or d["status"] != "DECONTAT":
        continue
    a = agg.setdefault(r["strategie"], {"joc": r["tinta"]["joc"], "n": 0, "miza": 0.0, "plata": 0.0, "net": 0.0})
    a["n"] += 1
    a["miza"] += r["miza"]
    a["plata"] += d["rezultat"]["plata"]
    a["net"] += d["rezultat"]["net"]
if not agg:
    prima = min(r["tinta"]["data"] for r in REGISTRU)
    st.info(f"Nicio decontare încă. Prima vine după extragerea din {prima} (18:30, ora României) și publicarea "
            "plăților oficiale.")
else:
    rows = []
    for s in sorted(agg, key=lambda k: (FAMILII.index(k.split("_")[0]) if k.split("_")[0] in FAMILII else 9, k)):
        a = agg[s]
        rows.append([s, s.split("_")[0], JOC_RO[a["joc"]], str(a["n"]), lei(a["miza"]), lei(a["plata"]), lei(a["net"]),
                     pct(a["plata"], a["miza"])])
    st.markdown(table(["Strategie", "Familie", "Joc", "Ținte decontate", "Miză", "Plăți", "Net", "Fracție returnată"],
                      rows))

# 3 ---------------------------------------------------------------------------------------------------------------
st.header(HEADERS[2])
rows = []
for f in FAMILII:
    sel = [a for s, a in agg.items() if s.split("_")[0] == f]
    m, p, n = sum(a["miza"] for a in sel), sum(a["plata"] for a in sel), sum(a["net"] for a in sel)
    rows.append([FAM_RO[f], str(sum(a["n"] for a in sel)), lei(m) if sel else "—", lei(p) if sel else "—",
                 lei(n) if sel else "—", pct(p, m)])
st.markdown(table(["Familie", "Strategii·ținte decontate", "Miză", "Plăți", "Net", "Fracție returnată"], rows))

# 4 ---------------------------------------------------------------------------------------------------------------
st.header(HEADERS[3])
st.markdown(
    "- Toate strategiile au valoarea așteptată sub miză (ρ < 1, din C1 și C3): pierderea pe hârtie este rezultatul "
    "așteptat. Designurile C1 câștigă ceva la fiecare extragere, dar returnează în medie ~36–37% din miză.\n"
    "- Pe câteva extrageri, diferențele dintre strategii sunt zgomot. Controlul aleator (RND) are același număr de "
    "bilete ca portofoliile C3 tocmai pentru comparație.\n"
    "- Biletele există numai în registrul sigilat (pentru decontare); nu se afișează și nu sunt recomandări.\n"
    "- Nu se afirmă avantaj, profit sau noutate. Rapoarte: xi/rezultate/F/RAPORT_F.md, xi/rezultate/HR/RAPORT_HR.md.")
