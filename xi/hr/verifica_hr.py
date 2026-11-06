"""Verificatorul independent al paginii „Registrul pe hârtie” (protocol xi/PROTOCOL_XI_HR.md §5) ⇒ poarta HR.

Nu importă pagina. Recalculează din registrul F real (cod propriu) toate rândurile tabelelor și verifică prezența lor
în textul randat de AppTest pe pagina reală; verifică integritatea fișierelor înghețate și lipsa __pycache__.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B xi/hr/verifica_hr.py

Se poate relua după fiecare decontare F (scrie un fișier nou cu marcaj). positive_claims_allowed=false.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import datetime as dt  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
from collections import defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402

QL = Path(__file__).resolve().parents[2]
PAGE = QL / "pages/2_Registru.py"
PROTO = QL / "xi/PROTOCOL_XI_HR.md"
SIG_PROTO = QL / "xi/SIGILIU_XI_HR.json"
SIG_COD = QL / "xi/hr/SIGILIU_COD_HR.json"
F = QL / "xi/rezultate/F"
FIXE = {"app.py": "7c5da1e6075cf2ac797fd43e6040c1567392444b295502a1468e9e164c021a47",
        "pages/1_Strategii.py": "9d297ae93280406553110e792f72dd63a1de9ef03214f47a63c8a18ff59ff6eb",
        "xi/rezultate/H/STRATEGII_DATE.json": "be021d2b"}
NUME = {"649": "Loto 6/49", "540": "Loto 5/40", "joker": "Joker"}
FAM = {"C1": "C1 — designuri garantate", "C3": "C3 — portofolii sub buget", "RND": "RND — control aleator"}
HEADERS = ["1. Țintele înregistrate", "2. Rezultatul pe strategie", "3. Pe familii", "4. Ce înseamnă"]


def h(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def lant(p: Path) -> tuple[list, list]:
    if not p.exists():
        return [], []
    rows, errs, prev = [], [], "0" * 64
    for i, raw in enumerate(p.read_bytes().split(b"\n")[:-1]):
        o = json.loads(raw)
        core = dict(o)
        s = core.pop("sha256", None)
        canon = json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if o.get("seq") != i or o.get("prev_sha256") != prev or raw != canon or s != hashlib.sha256(
                json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest():
            errs.append(i)
        prev = s
        rows.append(o)
    return rows, errs


def bani(v: float) -> str:
    semn = "-" if v < 0 else ""
    intreg, zec = f"{abs(v):.2f}".split(".")
    grupe = []
    while len(intreg) > 3:
        grupe.insert(0, intreg[-3:])
        intreg = intreg[:-3]
    grupe.insert(0, intreg)
    return f"{semn}{' '.join(grupe)}.{zec} lei"


def frac(p: float, m: float) -> str:
    return "—" if m == 0 else f"{100 * p / m:.1f}%"


def asteptate(reg: list, dec: list) -> list[str]:
    st = {d["ref_seq"]: d for d in dec}
    out = []
    pe_data = defaultdict(list)
    for r in reg:
        pe_data[r["tinta"]["data"]].append(r)
    for data in sorted(pe_data):
        rr = pe_data[data]
        dd = [r for r in rr if st.get(r["seq"], {}).get("status") == "DECONTAT"]
        vv = [r for r in rr if st.get(r["seq"], {}).get("status") == "VOID"]
        n_a = len(rr) - len(dd) - len(vv)
        jocuri = ", ".join(NUME[g] for g in NUME if g in {r["tinta"]["joc"] for r in rr})
        p = sum(st[r["seq"]]["rezultat"]["plata"] for r in dd)
        n = sum(st[r["seq"]]["rezultat"]["net"] for r in dd)
        cel = [data, jocuri, str(len(rr)), str(sum(r["nr_bilete"] for r in rr)), bani(sum(r["miza"] for r in rr)),
               rr[0]["cutoff_utc"], max(r["utc_inregistrare"] for r in rr), str(len(dd)),
               (f"ÎN AȘTEPTARE: {n_a}" if n_a else "0"), (f"VOID: {len(vv)}" if vv else "0"),
               (bani(p) if dd else "—"), (bani(n) if dd else "—")]
        out.append("| " + " | ".join(cel) + " |")
    pe_s = {}
    for r in reg:
        d = st.get(r["seq"])
        if d and d["status"] == "DECONTAT":
            a = pe_s.setdefault(r["strategie"], [r["tinta"]["joc"], 0, 0.0, 0.0, 0.0])
            a[1] += 1
            a[2] += r["miza"]
            a[3] += d["rezultat"]["plata"]
            a[4] += d["rezultat"]["net"]
    for s, (g, k, m, p, n) in pe_s.items():
        out.append("| " + " | ".join([s, s.split("_")[0], NUME[g], str(k), bani(m), bani(p), bani(n), frac(p, m)]) + " |")
    for f, et in FAM.items():
        sel = [v for s, v in pe_s.items() if s.split("_")[0] == f]
        m, p, n = (sum(v[i] for v in sel) for i in (2, 3, 4))
        out.append("| " + " | ".join([et, str(sum(v[1] for v in sel)), bani(m) if sel else "—", bani(p) if sel else "—",
                                      bani(n) if sel else "—", frac(p, m)]) + " |")
    return out


def apptest(root: str) -> dict:
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(Path(root) / "pages/2_Registru.py"), default_timeout=120)
    at.run()
    t = {k: [x.value for x in getattr(at, k)] for k in ("title", "header", "markdown", "caption", "warning", "error",
                                                         "info")}
    mods = sorted(m for m in sys.modules if m.split(".")[0] in ("quantum_limit", "torch", "engine", "app", "ui_tu3"))
    return {"exception": [str(x.value) for x in at.exception], "texts": t, "modules_interzise": mods}


def main() -> int:
    checks = []

    def ck(i, ok, det=None):
        checks.append({"id": i, "ok": bool(ok), "det": det})

    pyc0 = sorted(str(p) for b in (QL / "xi", QL / "pages") for p in b.rglob("__pycache__"))
    sp = json.loads(SIG_PROTO.read_text(encoding="utf-8"))
    ck("V1_protocol_sigilat", h(PROTO) == sp["protocol_sha256"] and PROTO.stat().st_mode & 0o777 == 0o444)
    sc = json.loads(SIG_COD.read_text(encoding="utf-8")) if SIG_COD.exists() else {"cod": {}}
    dif = {k: h(QL / k) for k, v in sc["cod"].items() if h(QL / k) != v}
    ck("V1_cod_sigilat", sc["cod"] and not dif and "pages/2_Registru.py" in sc["cod"], dif)
    f_before = {p.name: h(p) for p in sorted(F.glob("*.jsonl"))}
    reg, e1 = lant(F / "LANT_STRATEGII.jsonl")
    dec, e2 = lant(F / "DECONTARI_STRATEGII.jsonl")
    ck("V2_lanturi_valide", reg and not e1 and not e2, {"reg": e1[:5], "dec": e2[:5]})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-B", str(Path(__file__)), "--apptest", str(QL)], capture_output=True,
                       text=True, env=env, timeout=600)
    line = [x for x in r.stdout.splitlines() if x.startswith("APPTEST_JSON ")]
    real = json.loads(line[-1][13:]) if r.returncode == 0 and line else {"exception": [r.stderr[-1500:]],
                                                                          "texts": {}, "modules_interzise": []}
    T = real["texts"]
    md = "\n".join(T.get("markdown", []))
    ck("V2_fara_exceptie", not real["exception"] and not T.get("error"), real["exception"] or T.get("error"))
    ck("V2_titluri", T.get("header") == HEADERS, T.get("header"))
    exp = asteptate(reg, dec)
    lips = [x for x in exp if x not in md]
    ck("V2_recalcul_independent", not lips, lips[:10])
    ck("V2_info_fara_decontari", bool(T.get("info")) == (not any(d["status"] == "DECONTAT" for d in dec)),
       T.get("info"))
    tot = "\n".join(x for v in T.values() for x in v)
    ck("V3_fara_liste_numere", not re.findall(r"\b\d{1,2}(?:[ ,]+\d{1,2}){4,}\b", tot))
    ck("V4_module_interzise", not real["modules_interzise"], real["modules_interzise"])
    cod_f = json.loads((QL / "xi/f/SIGILIU_COD_F.json").read_text(encoding="utf-8"))["cod"]
    bad = {k: h(QL / k)[:12] for k, v in FIXE.items() if not h(QL / k).startswith(v)}
    bad.update({k: h(QL / k)[:12] for k, v in cod_f.items() if h(QL / k) != v})
    ck("V5_inghetate_neschimbate", not bad, bad)
    f_after = {p.name: h(p) for p in sorted(F.glob("*.jsonl"))}
    ck("V6_F_neschimbat_de_randare", f_before == f_after)
    pyc1 = sorted(str(p) for b in (QL / "xi", QL / "pages") for p in b.rglob("__pycache__"))
    ck("V7_fara_pycache", pyc0 == pyc1 == [], pyc1)

    n = sum(c["ok"] for c in checks)
    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rep = {"utc": utc, "poarta": "HR", "VERDICT": "PASS" if n == len(checks) else "FAIL", "n_pass": n,
           "n_checks": len(checks), "verifier_sha256": h(Path(__file__)), "pagina_sha256": h(PAGE),
           "registru": {"linii": len(reg), "cap": reg[-1]["sha256"] if reg else None},
           "decontari": {"linii": len(dec), "cap": dec[-1]["sha256"] if dec else None},
           "randuri_asteptate": exp, "checks": checks, "positive_claims_allowed": False}
    out = QL / f"xi/rezultate/HR/VERIFICARE_HR_{utc}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["id"] + ("" if c["ok"] else f"  {json.dumps(c['det'], ensure_ascii=False)[:600]}"))
    print(f"VERIFICARE_HR {rep['VERDICT']} {n}/{len(checks)} {out} {h(out)}")
    return 0 if rep["VERDICT"] == "PASS" else 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--apptest":
        print("APPTEST_JSON " + json.dumps(apptest(sys.argv[2]), ensure_ascii=False))
        sys.exit(0)
    sys.exit(main())
