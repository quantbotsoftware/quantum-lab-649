"""Verificatorul independent al fazei H (protocol xi/PROTOCOL_XI_H.md §5, V1–V8).

NU importă constructorul (xi/h/construieste_strategii.py) și nici pagina. Sha-urile surselor sunt citite din tabelul
§2 al protocolului sigilat; fiecare valoare din STRATEGII_DATE.json este recalculată din surse cu cod scris separat.
Randarea se verifică prin streamlit.testing.v1.AppTest, fiecare scenariu în subproces propriu (fără server, fără port).

Rulare: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B xi/h/verifica_h.py
Scrie xi/rezultate/H/VERIFICARE_H_<UTC>.json. positive_claims_allowed=false.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

QL = Path(__file__).resolve().parents[2]
PROTO = QL / "xi/PROTOCOL_XI_H.md"
SIG_PROTO = QL / "xi/SIGILIU_XI_H.json"
DATA = QL / "xi/rezultate/H/STRATEGII_DATE.json"
SEAL = QL / "xi/rezultate/H/SIGILIU_DATE_H.json"
PAGE = QL / "pages/1_Strategii.py"
APP_SHA = "7c5da1e6075cf2ac797fd43e6040c1567392444b295502a1468e9e164c021a47"
TEXT_FIX = ("Acest ecran nu face și nu afișează predicții de numere. Dacă extragerile sunt corecte, nicio metodă nu "
            "crește șansa unui bilet. positive_claims_allowed=false.")
WHITELIST = ["Acest ecran nu face și nu afișează predicții de numere.",
             "Nu există niciun predictor confirmat; nimic de pe acest ecran nu este o predicție."]
FORBIDDEN = ["recomand", "garantat profit", "câștig sigur", "castig sigur"]
HEADERS = ["1. Jocurile românești — banca de modele (P1)", "2. Arhive străine oficiale (P2)",
           "3. Rezoluția — ce abateri ar fi fost văzute", "4. Rezervele oarbe", "5. C1 — designuri garantate",
           "6. C3 — portofoliul sub buget", "7. Ce înseamnă"]
MODELS = ("STAT", "DRIFT", "GAP", "FERMI", "COMB")


def h(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def proto_sources() -> dict[str, str]:
    txt = PROTO.read_text(encoding="utf-8")
    sec = txt.split("## 2.", 1)[1].split("## 3.", 1)[0]
    return dict(re.findall(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|$", sec, re.M))


def jl(rel: str):
    p = QL / rel
    if rel.endswith(".jsonl"):
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return json.loads(p.read_text(encoding="utf-8"))


def expected() -> dict:
    """Recalcul independent al tuturor valorilor din §3 (fără metadate)."""
    p1, v1 = jl("xi/rezultate/P1/P1_REZULTATE.json"), jl("xi/rezultate/P1/VERIFICARE_P1.json")
    q1 = jl("xi/rezultate/P1/calificare/CALIFICARE_P1_20261031T192422Z.json")
    p2, v2 = jl("xi/rezultate/P2/P2_DEV_REZULTATE.json"), jl("xi/rezultate/P2/VERIFICARE_P2_DEV.json")
    s2 = jl("xi/p2/SIGILIU_CONFIRMARE_P2.json")
    q2 = jl("xi/rezultate/P2/calificare/CALIFICARE_P2_20261031T202258Z.json")
    c1, c3 = jl("xi/rezultate/C1/C1_EVALUARE.json"), jl("xi/rezultate/C3/C3_REZULTATE.json")
    cm = jl("xi/rezultate/C3/comparatori.jsonl")
    e: dict = {}
    n_ok = lambda v: f"{v['VERDICT']} {v['n_checks'] - v['n_fail']}/{v['n_checks']}"  # noqa: E731
    e["P1"] = {"verdict": p1["verdict"], "alpha": p1["alpha"], "holm_M": p1["holm"]["M"], "verificare": n_ok(v1),
               "jocuri": {g: {"T": p1["games"][g]["T"], "prima": p1["games"][g]["first"],
                              "ultima": p1["games"][g]["last"],
                              "E": {m: math.exp(p1["games"][g]["pred"][m]["logE"]) for m in MODELS},
                              "respins": {m: p1["holm"]["respinse"][g + ":" + m] for m in MODELS}}
                          for g in ("649", "540", "joker")}}
    val = s2["jocuri_valide"]
    e["P2"] = {"verdict": s2["verdict_P2"], "verdict_dezvoltare_brut": p2["verdict_dezvoltare"], "verificare": n_ok(v2),
               "jocuri_valide": val, "excluse": s2["jocuri_excluse"], "rezerva_stare": s2["rezerva"],
               "jocuri": {g: {"T_dev": p2["games"][g]["T_dev"], "T_total": p2["games"][g]["T_total"],
                              "R": p2["games"][g]["R"], "prima": p2["games"][g]["prima"],
                              "ultima": p2["games"][g]["ultima"],
                              "E": {m: math.exp(p2["games"][g]["pred"][m]["logE"]) for m in MODELS}} for g in val},
               "global_valid": {m: math.prod(math.exp(p2["games"][g]["pred"][m]["logE"]) for g in val)
                                for m in MODELS}}
    ps = q1["Q4"]["power_STAT"]
    e["rezolutie"] = {"P1": {"joc_lungime": "649", "n": ps["0.1"]["n"],
                             "frac_E_ge_1500": {d: ps[d]["frac_STAT_E_ge_1500"] for d in ("0.03", "0.05", "0.1", "0.15")},
                             "delta_min_putere_0_8": q1["Q4"]["rezolutie_delta_min_putere_0_8"]},
                      "P2": {g: {"n": q2["rezolutie"][g]["0.1"]["n"],
                                 "frac_E_ge_1500": {d: q2["rezolutie"][g][d]["frac_STAT_E_ge_1500"]
                                                    for d in ("0.05", "0.1", "0.2")}} for g in val}}
    rz = {}
    for g in ("HU_otos", "FR_loto", "US_powerball", "HU_hatos"):
        sp = jl(f"xi/date_p2/{g}/SEPARARE.json")
        st = (QL / f"xi/date_p2/{g}/rezerva.json").stat()
        rz[g] = {"R": sp["R"], "prima": sp["rez_prima_data"], "ultima": sp["rez_ultima_data"],
                 "sha256_publicat": sp["rezerva_sha256"], "mod": format(st.st_mode & 0o777, "o"),
                 "marime_octeti": st.st_size, "valid_P2": g in val}
    e["rezerve"] = rz
    e["C1"] = {"M": c1["meta"]["M"], "T": c1["meta"]["T"], "fereastra": c1["meta"]["window"], "porti": c1["GATES_PASS"],
               "designuri": {g: {"nume": d["name"], "nr_bilete": d["n_tickets"], "cost_extragere": d["cost_per_date"],
                                 "extrageri_fara_premiu": d["E1_dates_without_prize"],
                                 "premiu_minim": d["min_prize_per_date"],
                                 "premiu_q05": d["prize_per_date_quantiles_1_5_50_95_99"][1],
                                 "premiu_q50": d["prize_per_date_quantiles_1_5_50_95_99"][2],
                                 "premiu_q95": d["prize_per_date_quantiles_1_5_50_95_99"][3]}
                             for g, d in c1["designs"].items()},
               "strategii": {s: {"jocuri": d["games"], "miza_extragere": d["stake_per_date"],
                                 "orizonturi": {k: {"P_net_ge_0": d["horizons"][k]["P_net_ge_0"],
                                                    "fractie_returnata": d["horizons"][k]["return_mean"]}
                                                for k in ("1", "5", "10")}}
                             for s, d in c1["strategies"].items()}}
    price = {"649": 8.0, "540": 5.0, "joker": 7.0}
    rows = []
    for g in ("649", "540", "joker"):
        for b in (40, 100, 500):
            cr = next(r for r in cm if r["game"] == g and r["variant"] == "P" and r["B"] == b)
            for mu in (0.0, 1000.0):
                (i,) = [x for x in c3["instances"] if (x["game"], x["variant"], x["B"], x["mu"]) == (g, "P", b, mu)]
                c = i["K"] * price[g]
                rows.append({"joc": g, "buget": b, "mu": mu, "K": i["K"], "ev": i["ev"], "rho": i["ev"] / c,
                             "p_any": i["p_any"], "rho_aleator": cr["C_RND"]["ev_mean"] / c,
                             "p_any_aleator": cr["C_RND"]["p_any_mean"]})
    rh = [x["rho"] for x in c3["instances"]]
    e["C3"] = {"varianta": "P", "randuri": rows, "n_instante": c3["n_instances"], "rho_min": min(rh),
               "rho_max": max(rh), "n_rho_ge_1": len(c3["rho_ge_1"]),
               "G4": f"{c3['G4']['ensemble_hits']}/{c3['G4']['n']}", "G4_PASS": c3["G4"]["G4_PASS"]}
    return e


def compare(a, b, path="") -> list[str]:
    err = []
    if isinstance(b, dict):
        if not isinstance(a, dict) or set(a) != set(b):
            return [f"{path}: chei {sorted(a) if isinstance(a, dict) else type(a)} != {sorted(b)}"]
        for k in b:
            err += compare(a[k], b[k], f"{path}/{k}")
    elif isinstance(b, list):
        if not isinstance(a, list) or len(a) != len(b):
            return [f"{path}: listă diferită"]
        for i, (x, y) in enumerate(zip(a, b)):
            err += compare(x, y, f"{path}[{i}]")
    elif isinstance(b, bool) or isinstance(a, bool):
        if a is not b:
            err.append(f"{path}: {a!r} != {b!r}")
    elif isinstance(b, float) or isinstance(a, float):
        if not (isinstance(a, (int, float)) and abs(a - b) <= 1e-12 * max(1.0, abs(b))):
            err.append(f"{path}: {a!r} != {b!r}")
    elif a != b or type(a) is not type(b):
        err.append(f"{path}: {a!r} != {b!r}")
    return err


def walk_forbidden(o, path="") -> list[str]:
    bad = []
    if isinstance(o, dict):
        for k, v in o.items():
            if re.match(r"^(tickets|bilet|numere)", str(k)):
                bad.append(f"{path}/{k}")
            bad += walk_forbidden(v, f"{path}/{k}")
    elif isinstance(o, list):
        if sum(1 for x in o if isinstance(x, int) and not isinstance(x, bool)) >= 5:
            bad.append(f"{path}: listă de întregi")
        for i, x in enumerate(o):
            bad += walk_forbidden(x, f"{path}[{i}]")
    return bad


# --------------------------------------------------------------------------------------------- scenarii AppTest
def apptest(scenario: str, root: str) -> dict:
    from streamlit.testing.v1 import AppTest
    if scenario == "mpa":
        at = AppTest.from_file(str(Path(root) / "main.py"), default_timeout=120)
        at.run()
        at.switch_page("pages/1_Strategii.py")
        at.run()
    else:
        at = AppTest.from_file(str(Path(root) / "pages/1_Strategii.py"), default_timeout=120)
        at.run()
    texts = {"title": [x.value for x in at.title], "header": [x.value for x in at.header],
             "markdown": [x.value for x in at.markdown], "caption": [x.value for x in at.caption],
             "warning": [x.value for x in at.warning], "error": [x.value for x in at.error]}
    mods = sorted(m for m in sys.modules if m.split(".")[0] in ("quantum_limit", "torch", "engine", "app", "ui_tu3"))
    return {"exception": [str(x.value) for x in at.exception], "texts": texts, "modules_interzise": mods}


def run_scenario(scenario: str, root: Path) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-B", str(Path(__file__)), "--apptest", scenario, str(root)],
                       capture_output=True, text=True, env=env, timeout=600)
    line = [x for x in r.stdout.splitlines() if x.startswith("APPTEST_JSON ")]
    if r.returncode != 0 or not line:
        return {"exception": [f"rc={r.returncode}", r.stderr[-1500:]], "texts": {}, "modules_interzise": []}
    return json.loads(line[-1][len("APPTEST_JSON "):])


def pycache_dirs() -> list[str]:
    return sorted(str(p.relative_to(QL)) for base in (QL / "xi", QL / "pages") if base.exists()
                  for p in base.rglob("__pycache__"))


def main() -> int:
    checks: list[dict] = []

    def ck(name: str, ok: bool, det=None):
        checks.append({"id": name, "ok": bool(ok), "det": det})

    pc_before = pycache_dirs()
    # V1
    src = proto_sources()
    sig = json.loads(SIG_PROTO.read_text(encoding="utf-8"))
    ck("V1_protocol_sigilat", h(PROTO) == sig["protocol_sha256"] and PROTO.stat().st_mode & 0o777 == 0o444, h(PROTO))
    ck("V1_surse_14", len(src) == 14, len(src))
    diff = {k: h(QL / k) for k, v in src.items() if h(QL / k) != v}
    ck("V1_sha_surse", not diff, diff)
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    ck("V1_sha_date_eq_sigiliu", h(DATA) == seal["date_sha256"], h(DATA))
    ck("V1_moduri_0444", all(p.stat().st_mode & 0o777 == 0o444 for p in (DATA, SEAL)))
    data = json.loads(DATA.read_text(encoding="utf-8"))
    # V2
    meta = {"schema", "protocol_sha256", "surse", "text_fix", "positive_claims_allowed", "utc", "constructor_sha256"}
    ck("V2_metadate", data.get("surse") == src and data.get("protocol_sha256") == h(PROTO)
       and data.get("text_fix") == TEXT_FIX and data.get("positive_claims_allowed") is False
       and data.get("constructor_sha256") == seal["constructor_sha256"] == h(QL / "xi/h/construieste_strategii.py"))
    errs = compare({k: v for k, v in data.items() if k not in meta}, expected())
    ck("V2_paritate_independenta", not errs, errs[:20])
    # V3
    bad = walk_forbidden(data)
    ck("V3_fara_bilete", not bad, bad[:20])
    # V4 + V5 + V8 (pagina reală)
    real = run_scenario("pagina", QL)
    ck("V4_fara_exceptie", not real["exception"], real["exception"])
    T = real["texts"]
    ck("V4_titlu", T.get("title") == ["Strategii — ce spun datele"], T.get("title"))
    ck("V4_sectiuni", T.get("header") == HEADERS, T.get("header"))
    md = "\n".join(T.get("markdown", []))
    miss = []
    for g, G in data["P1"]["jocuri"].items():
        miss += [f"P1:{g}:{m}" for m in MODELS if f"| {G['E'][m]:.3f} " not in md]
    for g, G in data["P2"]["jocuri"].items():
        miss += [f"P2:{g}:{m}" for m in MODELS if f"| {G['E'][m]:.3f} " not in md]
    miss += [f"P2:global:{m}" for m in MODELS if f"| {data['P2']['global_valid'][m]:.3f} " not in md]
    ck("V4_e_valori_afisate", not miss, miss)
    ck("V4_verdicte", "P1_NICIUN_CANDIDAT" in md and "P2_NICIUN_SUPRAVIETUITOR_VALID" in md)
    alltxt = "\n".join(x for v in T.values() for x in v)
    stripped = alltxt
    for w in WHITELIST:
        stripped = stripped.replace(w, "")
    low = stripped.lower()
    ck("V5_fara_predictii", "predic" not in low, [m.start() for m in re.finditer("predic", low)][:10])
    ck("V5_lista_alba_prezenta", all(w in alltxt for w in WHITELIST))
    ck("V5_cuvinte_interzise", not any(f in alltxt.lower() for f in FORBIDDEN))
    lists = re.findall(r"\b\d{1,2}(?:[ ,]+\d{1,2}){4,}\b", md)
    ck("V5_fara_liste_numere", not lists, lists[:5])
    ck("V8_module_interzise", not real["modules_interzise"], real["modules_interzise"])
    # V6 integritate
    with tempfile.TemporaryDirectory(prefix="ql649_h_v6_") as d:
        r = Path(d)
        (r / "pages").mkdir()
        (r / "xi/rezultate/H").mkdir(parents=True)
        shutil.copy(PAGE, r / "pages/1_Strategii.py")
        b = bytearray(DATA.read_bytes())
        b[len(b) // 2] = ord("0") if b[len(b) // 2] != ord("0") else ord("1")
        (r / "xi/rezultate/H/STRATEGII_DATE.json").write_bytes(bytes(b))
        shutil.copy(SEAL, r / "xi/rezultate/H/SIGILIU_DATE_H.json")
        alt = run_scenario("pagina", r)
    ck("V6_integritate", not alt["exception"] and len(alt["texts"].get("error", [])) == 1
       and not alt["texts"].get("header") and not any("|" in x for x in alt["texts"].get("markdown", [])),
       {k: len(v) for k, v in alt["texts"].items()})
    # V7 MPA
    with tempfile.TemporaryDirectory(prefix="ql649_h_v7_") as d:
        r = Path(d)
        (r / "pages").mkdir()
        (r / "xi/rezultate/H").mkdir(parents=True)
        (r / "main.py").write_text("import streamlit as st\nst.write('principal')\n", encoding="utf-8")
        shutil.copy(PAGE, r / "pages/1_Strategii.py")
        shutil.copy(DATA, r / "xi/rezultate/H/STRATEGII_DATE.json")
        shutil.copy(SEAL, r / "xi/rezultate/H/SIGILIU_DATE_H.json")
        mpa = run_scenario("mpa", r)
    ck("V7_mpa_descopera_pagina", not mpa["exception"] and mpa["texts"].get("title") == ["Strategii — ce spun datele"]
       and mpa["texts"].get("header") == HEADERS, {"exc": mpa["exception"], "title": mpa["texts"].get("title")})
    # V8
    ck("V8_app_py_neschimbat", h(QL / "app.py") == APP_SHA, h(QL / "app.py"))
    pc_after = pycache_dirs()
    ck("V8_fara_pycache_nou", pc_after == pc_before == [], {"inainte": pc_before, "dupa": pc_after})

    n_pass = sum(c["ok"] for c in checks)
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rep = {"utc": utc, "verifier_sha256": h(Path(__file__)), "date_sha256": h(DATA), "n_checks": len(checks),
           "n_pass": n_pass, "VERDICT": "PASS" if n_pass == len(checks) else "FAIL", "poarta": "H1",
           "checks": checks, "positive_claims_allowed": False}
    out = QL / f"xi/rezultate/H/VERIFICARE_H_{utc}.json"
    out.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["id"] + ("" if c["ok"] else f"  {json.dumps(c['det'], ensure_ascii=False)[:600]}"))
    print(f"VERIFICARE_H {rep['VERDICT']} {n_pass}/{len(checks)} {out} {h(out)}")
    return 0 if rep["VERDICT"] == "PASS" else 1


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--apptest":
        res = apptest(sys.argv[2], sys.argv[3])
        print("APPTEST_JSON " + json.dumps(res, ensure_ascii=False))
        sys.exit(0)
    sys.exit(main())
