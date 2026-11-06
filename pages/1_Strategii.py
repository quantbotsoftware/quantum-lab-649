"""Ecranul „Strategii” (protocol xi/PROTOCOL_XI_H.md §3–§4). Pagină Streamlit separată (MPA, directorul pages/).

Citește NUMAI xi/rezultate/H/STRATEGII_DATE.json, verifică sha-ul față de SIGILIU_DATE_H.json și afișează
rezultatele publicate P1/P2/C1/C3. Nu calculează nimic în afară de formatare, nu afișează bilete sau numere.
Nu importă torch, motorul, quantum_limit sau alt modul al proiectului. positive_claims_allowed=false.
"""
import sys

sys.dont_write_bytecode = True

import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402

import streamlit as st  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "xi/rezultate/H/STRATEGII_DATE.json"
SEAL = ROOT / "xi/rezultate/H/SIGILIU_DATE_H.json"
JOC_RO = {"649": "Loto 6/49", "540": "Loto 5/40", "joker": "Joker"}
JOC_STR = {"HU_otos": "Ungaria Ötöslottó 5/90", "FR_loto": "Franța Loto 5/49 + 1/10",
           "US_powerball": "SUA Powerball 5/69 + 1/26", "HU_hatos": "Ungaria Hatoslottó 6/45",
           "DE_6aus49_sambata": "Germania Lotto 6aus49 (sâmbătă)", "US_megamillions": "SUA Mega Millions"}
STRAT = {"D_joker": "design Joker la fiecare extragere", "D_649": "design 6/49 la fiecare extragere",
         "D_ambele": "ambele designuri"}
MODELE = ["STAT", "DRIFT", "GAP", "FERMI", "COMB"]
ORDINE = ["649", "540", "joker", "HU_otos", "FR_loto", "US_powerball", "HU_hatos", "D_joker", "D_649", "D_ambele"]


def ordonat(d: dict) -> list:
    """Cheile în ordinea de afișare (JSON-ul este scris cu chei sortate alfabetic)."""
    return sorted(d, key=lambda k: (ORDINE.index(k) if k in ORDINE else len(ORDINE), k))


def pct(x: float, nd: int = 1) -> str:
    return f"{100 * x:.{nd}f}%"


def lei(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ") + " lei"


def table(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


st.set_page_config(page_title="QL649 · Strategii", page_icon="📊", layout="wide")
st.title("Strategii — ce spun datele")

try:
    raw = DATA.read_bytes()
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    ok = hashlib.sha256(raw).hexdigest() == seal["date_sha256"]
except (OSError, ValueError, KeyError) as exc:  # fișier lipsă sau corupt
    ok, raw, seal = False, b"", {"eroare": str(exc)}
if not ok:
    st.error("Datele ecranului nu corespund sigiliului (xi/rezultate/H/SIGILIU_DATE_H.json). Nu se afișează nimic.")
    st.stop()

D = json.loads(raw.decode("utf-8"))
st.warning(D["text_fix"])
st.caption(f"date `{seal['date_sha256'][:16]}…` · protocol XI-H `{D['protocol_sha256'][:12]}…` · construit {D['utc']} "
           "· calcul clasic · surse: rapoartele P1, P2, C1, C3 din xi/rezultate/")

# 1 ---------------------------------------------------------------------------------------------------------------
P1 = D["P1"]
st.header("1. Jocurile românești — banca de modele (P1)")
st.markdown(
    "Cinci modele statistice (STAT, DRIFT, GAP, FERMI, COMB) au fost rulate „ca în ajun” pe toată arhiva. "
    "Valoarea E arată de câte ori a crescut capitalul unui pariu echitabil contra uniformului: E < 1 înseamnă că "
    f"modelul a fost mai slab decât alegerea la întâmplare. Corecție Holm, α = {P1['alpha']}, {P1['holm_M']} teste.")
rows = []
for g in ordonat(P1["jocuri"]):
    G = P1["jocuri"][g]
    rows.append([JOC_RO[g], str(G["T"]), f"{G['prima']} … {G['ultima']}"]
                + [f"{G['E'][x]:.3f}" for x in MODELE]
                + ["da" if any(G["respins"].values()) else "nu",
                   "abatere detectabilă" if any(G["respins"].values()) else "nicio abatere detectabilă de la uniform"])
st.markdown(table(["Joc", "Extrageri", "Perioada"] + [f"E {x}" for x in MODELE] + ["Respins", "Concluzie"], rows))
st.markdown(f"Verdict: **{P1['verdict']}** · verificare independentă: **{P1['verificare']}**")

# 2 ---------------------------------------------------------------------------------------------------------------
P2 = D["P2"]
st.header("2. Arhive străine oficiale (P2)")
st.markdown("Aceleași modele, înghețate, pe arhive oficiale străine (partea de dezvoltare, 80%). Ultimele 20% din "
            "fiecare arhivă au rămas sigilate (secțiunea 4).")
rows = []
for g in P2["jocuri_valide"]:
    G = P2["jocuri"][g]
    rows.append([JOC_STR.get(g, g), str(G["T_dev"]), f"{G['prima']} … {G['ultima']}"]
                + [f"{G['E'][x]:.3f}" for x in MODELE])
rows.append(["**global (produs pe jocurile valide)**", "", ""] + [f"{P2['global_valid'][x]:.3f}" for x in MODELE])
st.markdown(table(["Joc", "Extrageri (dezvoltare)", "Perioada"] + [f"E {x}" for x in MODELE], rows))
st.markdown("Excluse: " + "; ".join(f"{JOC_STR.get(g, g)} — {P2['excluse'][g]}" for g in ordonat(P2["excluse"])) + ".")
st.markdown(f"Verdict: **{P2['verdict']}** · verificare independentă: **{P2['verificare']}** · rezultatul brut "
            f"`{P2['verdict_dezvoltare_brut']}` a fost anulat de AMENDAMENT_XI_P2_02 (Hatoslottó: defect de citire, "
            "nu semnal).")

# 3 ---------------------------------------------------------------------------------------------------------------
R = D["rezolutie"]
st.header("3. Rezoluția — ce abateri ar fi fost văzute")
st.markdown("Pe istorii sintetice de aceeași lungime, cu bile favorizate/defavorizate cu ±δ, procentul istoriilor în "
            "care modelul STAT ar fi dat alarma (E ≥ 1500):")
rp1 = R["P1"]
rows = [[f"România ({JOC_RO[rp1['joc_lungime']]}, n = {rp1['n']})"]
        + [pct(rp1["frac_E_ge_1500"].get(d, float("nan")), 0) if d in rp1["frac_E_ge_1500"] else "—"
           for d in ("0.03", "0.05", "0.1", "0.15", "0.2")]]
for g in [x for x in P2["jocuri_valide"] if x in R["P2"]]:
    v = R["P2"][g]
    rows.append([f"{JOC_STR.get(g, g)} (n = {v['n']})"]
                + [pct(v["frac_E_ge_1500"][d], 0) if d in v["frac_E_ge_1500"] else "—"
                   for d in ("0.03", "0.05", "0.1", "0.15", "0.2")])
st.markdown(table(["Arhivă", "±3%", "±5%", "±10%", "±15%", "±20%"], rows))
st.markdown(f"Abaterea minimă văzută cu putere ≥ 80% pe arhiva RO: ±{pct(rp1['delta_min_putere_0_8'], 0)}. Se exclud "
            "abateri ale bilelor de ordinul 10–20%; abaterile de câteva procente rămân nedetectabile pe arhive de "
            "această lungime.")

# 4 ---------------------------------------------------------------------------------------------------------------
st.header("4. Rezervele oarbe")
rows = []
for g in ordonat(D["rezerve"]):
    v = D["rezerve"][g]
    rows.append([JOC_STR.get(g, g), str(v["R"]), f"{v['prima']} … {v['ultima']}", f"`{v['sha256_publicat'][:12]}…`",
                 v["mod"], "SIGILATĂ, NECITITĂ" + ("" if v["valid_P2"] else " (joc exclus la dezvoltare)")])
st.markdown(table(["Joc", "Extrageri", "Perioada", "sha256 publicat", "Mod", "Stare"], rows))
st.markdown(f"{P2['rezerva_stare']}. Se pot folosi o singură dată, numai pentru o ipoteză distinctă, cu protocol nou "
            "sigilat înainte.")

# 5 ---------------------------------------------------------------------------------------------------------------
C1 = D["C1"]
st.header("5. C1 — designuri garantate")
st.markdown(f"Simulare pe {C1['M']:,} de ani posibili cu plățile reale din fereastra {C1['fereastra'][0]} … "
            f"{C1['fereastra'][1]} ({C1['T']} extrageri pe 10 ani).".replace(",", " "))
rows = []
for g in ordonat(C1["designuri"]):
    d = C1["designuri"][g]
    rows.append([JOC_RO.get(g, g), d["nume"], str(d["nr_bilete"]), lei(d["cost_extragere"]),
                 str(d["extrageri_fara_premiu"]), lei(d["premiu_minim"]), lei(d["premiu_q05"]), lei(d["premiu_q50"]),
                 lei(d["premiu_q95"])])
st.markdown(table(["Joc", "Design", "Bilete", "Cost/extragere", "Extrageri fără premiu", "Premiu minim",
                   "Premiu 5%", "Premiu median", "Premiu 95%"], rows))
rows = []
for s in ordonat(C1["strategii"]):
    d = C1["strategii"][s]
    o = d["orizonturi"]
    rows.append([STRAT.get(s, s), lei(d["miza_extragere"])]
                + [pct(o[h]["fractie_returnata"]) for h in ("1", "5", "10")]
                + [pct(o[h]["P_net_ge_0"], 2) for h in ("1", "5", "10")])
st.markdown(table(["Strategie", "Miză/extragere", "Returnat 1 an", "Returnat 5 ani", "Returnat 10 ani",
                   "P(pe plus) 1 an", "P(pe plus) 5 ani", "P(pe plus) 10 ani"], rows))
st.markdown("Garanția combinatorie dă un premiu la fiecare extragere, dar returnează ~36–37% din miză: "
            "regularitate, nu profit.")

# 6 ---------------------------------------------------------------------------------------------------------------
C3 = D["C3"]
st.header("6. C3 — portofoliul sub buget")
st.markdown("μ = 0: valoare așteptată maximă (modelul mulțimii al produsului); μ = 1000: compromis spre regularitate "
            "(probabilitatea exactă de a câștiga ceva, P_any). ρ = valoarea așteptată / miză.")
rows = []
for r in C3["randuri"]:
    rows.append([JOC_RO[r["joc"]], f"{r['buget']} lei", f"{r['mu']:g}", str(r["K"]), lei(r["ev"]), f"{r['rho']:.2f}",
                 pct(r["p_any"]), f"{r['rho_aleator']:.2f}", pct(r["p_any_aleator"])])
st.markdown(table(["Joc", "Buget", "μ", "Bilete", "EV", "ρ", "P_any", "ρ bilete aleatoare", "P_any aleatoare"], rows))
st.markdown(f"Pe toate cele {C3['n_instante']} de portofolii: ρ între {C3['rho_min']:.2f} și {C3['rho_max']:.2f}; "
            f"portofolii cu ρ ≥ 1: {C3['n_rho_ge_1']}. Poarta optimului exact G4: {C3['G4']}. ρ < 1 peste tot: "
            "niciun portofoliu nu recuperează miza.")

# 7 ---------------------------------------------------------------------------------------------------------------
st.header("7. Ce înseamnă")
st.markdown(
    "- Pe 6 urne independente (3 românești, 3 străine valide), niciun model din bancă nu bate uniformul: fiecare E "
    "este sub 1. Este exact ce se așteaptă de la extrageri corecte.\n"
    "- Nu există niciun predictor confirmat; nimic de pe acest ecran nu este o predicție.\n"
    "- Designurile C1 cumpără regularitate (un premiu la fiecare extragere) cu aproximativ 63% din miză pierdută în "
    "medie; portofoliile C3 au ρ < 1.\n"
    "- Limite: arhivele au fost explorate; rezervele oarbe rămân pentru o ipoteză distinctă viitoare; un rezultat "
    "negativ nu demonstrează imposibilitatea oricărei metode. Nu se afirmă avantaj, profit sau noutate.\n"
    "- Rapoarte: xi/rezultate/P1/RAPORT_P1.md, xi/rezultate/P2/RAPORT_P2.md, xi/rezultate/C1/RAPORT_C1.md, "
    "xi/rezultate/C3/RAPORT_C3.md, xi/rezultate/H/RAPORT_H.md.")
