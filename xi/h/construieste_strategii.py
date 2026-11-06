"""Constructorul datelor ecranului „Strategii” (protocol xi/PROTOCOL_XI_H.md §2–§4).

Citește NUMAI sursele cu sha256 fixat în protocol (rezultate P1/P2/C1/C3 deja publicate și verificate), extrage
câmpurile din §3 (fără bilete, fără liste de numere), calculează aritmetica permisă din §0 și scrie
xi/rezultate/H/STRATEGII_DATE.json + SIGILIU_DATE_H.json (0444). Rezervele oarbe: numai os.stat, niciodată citite.

Rulare: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B xi/h/construieste_strategii.py [--forteaza]
positive_claims_allowed=false. Calcul clasic. Nu este o predicție.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path

QL = Path(__file__).resolve().parents[2]
OUT = QL / "xi/rezultate/H"
DATA = OUT / "STRATEGII_DATE.json"
SEAL = OUT / "SIGILIU_DATE_H.json"
PROTO = QL / "xi/PROTOCOL_XI_H.md"
PROTO_SHA = "2c8da0a659c9f05c899ff445cb471f96f6c8ed2b8091a92ef02746d0234b06e9"

SURSE = {
    "xi/rezultate/P1/P1_REZULTATE.json": "ea62e6eda55e49859bc2c2d692e2c223717eee9d330d5b20ef8b0451b69898fa",
    "xi/rezultate/P1/VERIFICARE_P1.json": "2298bc090f72170424611b28e9e43efeab1ab4aa3b29014d5446e0771455da1b",
    "xi/rezultate/P1/calificare/CALIFICARE_P1_20261031T192422Z.json":
        "a93293a359d18c7175c5b4980288a0b13d0837fdabf55d8856f6e5a3005e2931",
    "xi/rezultate/P2/P2_DEV_REZULTATE.json": "36c46661076978759587733f3ea7e33f9fba0e6524b4d29c65f1b5fc1df3e866",
    "xi/rezultate/P2/VERIFICARE_P2_DEV.json": "639dcb71db3ac5d3bf5feb8812bcd74f84642dde460f55eef3645ff6012bf12e",
    "xi/p2/SIGILIU_CONFIRMARE_P2.json": "82f860828200f77a562d7c4a49a9ef8f011ac29e8338a4b6b9de712c6255a4c4",
    "xi/rezultate/P2/calificare/CALIFICARE_P2_20261031T202258Z.json":
        "6ab2f3a39b2b4dbb309760578a07ee5469eb5bd9cd375378cf5420c46996d058",
    "xi/date_p2/HU_otos/SEPARARE.json": "72637fe56186f9942b61aab52cb244f9976e0139206002916610043bd4b5d5df",
    "xi/date_p2/FR_loto/SEPARARE.json": "7ec33bc440d2c2503896cc5a54c3d4498b0940eca94be5b46c8803702e09944e",
    "xi/date_p2/US_powerball/SEPARARE.json": "901cd54c470ab343999ef45f5153aa0c4a1f5fe106ff192542e589ba84de3248",
    "xi/date_p2/HU_hatos/SEPARARE.json": "7ee3918d216ec4b5d941842a9dc8421171670d1d4d50dc00dd653eb2b637a097",
    "xi/rezultate/C1/C1_EVALUARE.json": "5eb6440188d16788e7e7410c44a21512f5830f324324822672eabc5d6803b2e8",
    "xi/rezultate/C3/C3_REZULTATE.json": "01331654bb23b56295e5c23c2b0cf8a72f2ec84f755df2fcefbfcede23c9f9ca",
    "xi/rezultate/C3/comparatori.jsonl": "04c877159694cd9f1d99b903d08465c895d311bb1f90c027dbee81a2c776f652",
}
PRED = ["STAT", "DRIFT", "GAP", "FERMI", "COMB"]
JOCURI_RO = ["649", "540", "joker"]
REZERVE = ["HU_otos", "FR_loto", "US_powerball", "HU_hatos"]
PRET = {"649": 8.0, "540": 5.0, "joker": 7.0}
P1_DELTA = ["0.03", "0.05", "0.1", "0.15"]
P2_DELTA = ["0.05", "0.1", "0.2"]
C3_BUGETE = [40, 100, 500]
C3_MU = [0.0, 1000.0]


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load(rel: str):
    b = (QL / rel).read_bytes()
    h = sha_bytes(b)
    if h != SURSE[rel]:
        raise SystemExit(f"REFUZ: sha diferit pentru {rel}: {h} != {SURSE[rel]}")
    if rel.endswith(".jsonl"):
        return [json.loads(x) for x in b.decode("utf-8").splitlines() if x.strip()]
    return json.loads(b.decode("utf-8"))


def build() -> dict:
    if sha_bytes(PROTO.read_bytes()) != PROTO_SHA:
        raise SystemExit("REFUZ: protocolul XI-H diferă de sigiliu")
    p1 = load("xi/rezultate/P1/P1_REZULTATE.json")
    v1 = load("xi/rezultate/P1/VERIFICARE_P1.json")
    q1 = load("xi/rezultate/P1/calificare/CALIFICARE_P1_20261031T192422Z.json")
    p2 = load("xi/rezultate/P2/P2_DEV_REZULTATE.json")
    v2 = load("xi/rezultate/P2/VERIFICARE_P2_DEV.json")
    s2 = load("xi/p2/SIGILIU_CONFIRMARE_P2.json")
    q2 = load("xi/rezultate/P2/calificare/CALIFICARE_P2_20261031T202258Z.json")
    sep = {g: load(f"xi/date_p2/{g}/SEPARARE.json") for g in REZERVE}
    c1 = load("xi/rezultate/C1/C1_EVALUARE.json")
    c3 = load("xi/rezultate/C3/C3_REZULTATE.json")
    cmp3 = load("xi/rezultate/C3/comparatori.jsonl")

    out: dict = {"schema": "XI-H/1", "protocol_sha256": PROTO_SHA, "surse": dict(SURSE),
                 "text_fix": "Acest ecran nu face și nu afișează predicții de numere. Dacă extragerile sunt corecte, "
                             "nicio metodă nu crește șansa unui bilet. positive_claims_allowed=false.",
                 "positive_claims_allowed": False}

    # P1
    P1 = {"verdict": p1["verdict"], "alpha": p1["alpha"], "holm_M": p1["holm"]["M"],
          "verificare": f"{v1['VERDICT']} {v1['n_checks'] - v1['n_fail']}/{v1['n_checks']}", "jocuri": {}}
    for g in JOCURI_RO:
        G = p1["games"][g]
        P1["jocuri"][g] = {"T": G["T"], "prima": G["first"], "ultima": G["last"],
                           "E": {x: math.exp(G["pred"][x]["logE"]) for x in PRED},
                           "respins": {x: bool(p1["holm"]["respinse"][f"{g}:{x}"]) for x in PRED}}
    out["P1"] = P1

    # P2
    valide = list(s2["jocuri_valide"])
    P2 = {"verdict": s2["verdict_P2"], "verdict_dezvoltare_brut": p2["verdict_dezvoltare"],
          "verificare": f"{v2['VERDICT']} {v2['n_checks'] - v2['n_fail']}/{v2['n_checks']}",
          "jocuri_valide": valide, "excluse": dict(s2["jocuri_excluse"]), "rezerva_stare": s2["rezerva"],
          "jocuri": {}, "global_valid": {}}
    for g in valide:
        G = p2["games"][g]
        P2["jocuri"][g] = {"T_dev": G["T_dev"], "T_total": G["T_total"], "R": G["R"], "prima": G["prima"],
                           "ultima": G["ultima"], "E": {x: math.exp(G["pred"][x]["logE"]) for x in PRED}}
    for x in PRED:
        P2["global_valid"][x] = math.exp(sum(p2["games"][g]["pred"][x]["logE"] for g in valide))
    out["P2"] = P2

    # Rezoluția
    pw = q1["Q4"]["power_STAT"]
    out["rezolutie"] = {
        "P1": {"joc_lungime": "649", "n": pw["0.1"]["n"],
               "frac_E_ge_1500": {d: pw[d]["frac_STAT_E_ge_1500"] for d in P1_DELTA},
               "delta_min_putere_0_8": q1["Q4"]["rezolutie_delta_min_putere_0_8"]},
        "P2": {g: {"n": q2["rezolutie"][g]["0.1"]["n"],
                   "frac_E_ge_1500": {d: q2["rezolutie"][g][d]["frac_STAT_E_ge_1500"] for d in P2_DELTA}}
               for g in valide},
    }

    # Rezervele oarbe: numai stat + sha publicat
    rez = {}
    for g in REZERVE:
        st = os.stat(QL / f"xi/date_p2/{g}/rezerva.json")
        rez[g] = {"R": sep[g]["R"], "prima": sep[g]["rez_prima_data"], "ultima": sep[g]["rez_ultima_data"],
                  "sha256_publicat": sep[g]["rezerva_sha256"], "mod": oct(stat.S_IMODE(st.st_mode))[2:],
                  "marime_octeti": st.st_size, "valid_P2": g in valide}
    out["rezerve"] = rez

    # C1
    des = {}
    for g, d in c1["designs"].items():
        q = d["prize_per_date_quantiles_1_5_50_95_99"]
        des[g] = {"nume": d["name"], "nr_bilete": d["n_tickets"], "cost_extragere": d["cost_per_date"],
                  "extrageri_fara_premiu": d["E1_dates_without_prize"], "premiu_minim": d["min_prize_per_date"],
                  "premiu_q05": q[1], "premiu_q50": q[2], "premiu_q95": q[3]}
    strat = {}
    for s, d in c1["strategies"].items():
        strat[s] = {"jocuri": list(d["games"]), "miza_extragere": d["stake_per_date"],
                    "orizonturi": {h: {"P_net_ge_0": d["horizons"][h]["P_net_ge_0"],
                                       "fractie_returnata": d["horizons"][h]["return_mean"]}
                                   for h in ("1", "5", "10")}}
    out["C1"] = {"M": c1["meta"]["M"], "T": c1["meta"]["T"], "fereastra": list(c1["meta"]["window"]),
                 "porti": bool(c1["GATES_PASS"]), "designuri": des, "strategii": strat}

    # C3
    rnd = {(r["game"], r["B"]): r for r in cmp3 if r["variant"] == "P"}
    rows = []
    for g in JOCURI_RO:
        for B in C3_BUGETE:
            for mu in C3_MU:
                hit = [i for i in c3["instances"] if i["game"] == g and i["variant"] == "P" and i["B"] == B
                       and i["mu"] == mu]
                if len(hit) != 1:
                    raise SystemExit(f"REFUZ: instanța C3 {g}/{B}/{mu} nu este unică ({len(hit)})")
                i = hit[0]
                r = rnd[(g, B)]
                cost = i["K"] * PRET[g]
                rows.append({"joc": g, "buget": B, "mu": mu, "K": i["K"], "ev": i["ev"],
                             "rho": i["ev"] / cost, "p_any": i["p_any"],
                             "rho_aleator": r["C_RND"]["ev_mean"] / cost, "p_any_aleator": r["C_RND"]["p_any_mean"]})
    rhos = [i["rho"] for i in c3["instances"]]
    out["C3"] = {"varianta": "P", "randuri": rows, "n_instante": c3["n_instances"], "rho_min": min(rhos),
                 "rho_max": max(rhos), "n_rho_ge_1": len(c3["rho_ge_1"]),
                 "G4": f"{c3['G4']['ensemble_hits']}/{c3['G4']['n']}", "G4_PASS": bool(c3["G4"]["G4_PASS"])}
    return out


def main(argv: list[str]) -> int:
    force = "--forteaza" in argv
    if (DATA.exists() or SEAL.exists()) and not force:
        print("REFUZ: datele H există deja (folosește --forteaza numai cu incident consemnat)")
        return 2
    data = build()
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["utc"] = utc
    data["constructor_sha256"] = sha_bytes(Path(__file__).read_bytes())
    OUT.mkdir(parents=True, exist_ok=True)
    for p in (DATA, SEAL):
        if p.exists():
            os.chmod(p, 0o644)
    body = (json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    DATA.write_bytes(body)
    seal = {"date": "xi/rezultate/H/STRATEGII_DATE.json", "date_sha256": sha_bytes(body), "utc": utc,
            "constructor_sha256": data["constructor_sha256"], "protocol_sha256": PROTO_SHA, "surse": dict(SURSE),
            "positive_claims_allowed": False}
    SEAL.write_text(json.dumps(seal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(DATA, 0o444)
    os.chmod(SEAL, 0o444)
    print(f"STRATEGII_DATE {seal['date_sha256']} utc={utc}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
