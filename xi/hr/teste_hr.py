"""Calificarea paginii „Registrul pe hârtie” (protocol xi/PROTOCOL_XI_HR.md §4). Numai directoare temporare.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B xi/hr/teste_hr.py

Scrie jurnalul în xi/rezultate/HR/teste/TESTE_HR_<UTC>.log. positive_claims_allowed=false.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import datetime as dt  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

QL = Path(__file__).resolve().parents[2]
PAGE = QL / "pages/2_Registru.py"
PROTO = QL / "xi/PROTOCOL_XI_HR.md"
PF = "ba74568f40fa62303bef59bbd7c23d46b527ec53e00297c59f71670a0b7d3220"
HEADERS = ["1. Țintele înregistrate", "2. Rezultatul pe strategie", "3. Pe familii", "4. Ce înseamnă"]
FORBIDDEN_MODS = ("quantum_limit", "torch", "engine", "app", "ui_tu3")


def cj(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def seal_lines(objs: list) -> list[str]:
    out, prev = [], "0" * 64
    for i, o in enumerate(objs):
        o = dict(o, seq=i, prev_sha256=prev)
        o["sha256"] = hashlib.sha256(cj(o).encode("utf-8")).hexdigest()
        prev = o["sha256"]
        out.append(cj(o))
    return out


def reg_obj(date, joc, strat, nb, miza, utc="2026-12-01T10:00:00Z"):
    return {"tip": "INREGISTRARE", "tinta": {"data": date, "joc": joc}, "strategie": strat, "sursa": {"x": 1},
            "bilete": [[11, 12, 13, 14, 15, 16]], "nr_bilete": nb, "pret_bilet": 8, "miza": miza,
            "utc_inregistrare": utc, "cutoff_utc": f"{date}T14:00:00Z", "protocol_sha256": PF, "cod_sha256": "c" * 64,
            "positive_claims_allowed": False}


def build(root: Path, with_dec=True, bad_reg=False, bad_ref=False) -> None:
    (root / "pages").mkdir(parents=True)
    (root / "xi/rezultate/F").mkdir(parents=True)
    shutil.copy(PAGE, root / "pages/2_Registru.py")
    shutil.copy(PROTO, root / "xi/PROTOCOL_XI_HR.md")
    regs = seal_lines([reg_obj("2026-12-03", "649", "C1_SG324Q", 324, 2592),
                       reg_obj("2026-12-03", "649", "RND_649_B40", 5, 40),
                       reg_obj("2026-12-06", "joker", "C1_JS135Q", 135, 945, "2026-12-02T09:30:00Z")])
    txt = "\n".join(regs) + "\n"
    if bad_reg:
        i = txt.index('"miza":40')
        txt = txt[:i] + '"miza":41' + txt[i + 9:]
    (root / "xi/rezultate/F/LANT_STRATEGII.jsonl").write_text(txt, encoding="utf-8")
    if with_dec:
        r = [json.loads(x) for x in regs]
        decs = seal_lines([
            {"tip": "DECONTARE", "status": "DECONTAT", "ref_seq": 0,
             "ref_sha256": ("f" * 64 if bad_ref else r[0]["sha256"]), "strategie": "C1_SG324Q",
             "tinta": r[0]["tinta"], "rezultat": {"plata": 1020.5, "net": 1020.5 - 2592, "miza": 2592,
                                                  "numere_extrase": [21, 22, 23, 24, 25, 26]}},
            {"tip": "DECONTARE", "status": "VOID", "ref_seq": 1, "ref_sha256": r[1]["sha256"],
             "strategie": "RND_649_B40", "tinta": r[1]["tinta"], "rezultat": {"motiv": "test"}}])
        (root / "xi/rezultate/F/DECONTARI_STRATEGII.jsonl").write_text("\n".join(decs) + "\n", encoding="utf-8")


def apptest(scenario: str, root: str) -> dict:
    from streamlit.testing.v1 import AppTest
    if scenario == "mpa":
        at = AppTest.from_file(str(Path(root) / "main.py"), default_timeout=120)
        at.run()
        at.switch_page("pages/2_Registru.py")
        at.run()
    else:
        at = AppTest.from_file(str(Path(root) / "pages/2_Registru.py"), default_timeout=120)
        at.run()
    texts = {"title": [x.value for x in at.title], "header": [x.value for x in at.header],
             "markdown": [x.value for x in at.markdown], "caption": [x.value for x in at.caption],
             "warning": [x.value for x in at.warning], "error": [x.value for x in at.error],
             "info": [x.value for x in at.info]}
    mods = sorted(m for m in sys.modules if m.split(".")[0] in FORBIDDEN_MODS)
    return {"exception": [str(x.value) for x in at.exception], "texts": texts, "modules_interzise": mods}


def run(scenario: str, root: Path) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-B", str(Path(__file__)), "--apptest", scenario, str(root)],
                       capture_output=True, text=True, env=env, timeout=600)
    line = [x for x in r.stdout.splitlines() if x.startswith("APPTEST_JSON ")]
    if r.returncode != 0 or not line:
        return {"exception": [f"rc={r.returncode}", r.stderr[-1500:]], "texts": {}, "modules_interzise": []}
    return json.loads(line[-1][len("APPTEST_JSON "):])


def number_lists(text: str) -> list:
    return re.findall(r"\b\d{1,2}(?:[ ,]+\d{1,2}){4,}\b", text)


def main() -> int:
    res = []

    def ck(i, ok, det=None):
        res.append((i, bool(ok), det))

    with tempfile.TemporaryDirectory(prefix="ql649_hr_t1_") as d:
        build(Path(d))
        a = run("pagina", Path(d))
    T = a["texts"]
    md = "\n".join(T.get("markdown", []))
    want = ["| 2026-12-03 | Loto 6/49 | 2 | 329 | 2 632.00 lei | 2026-12-03T14:00:00Z | 2026-12-01T10:00:00Z | 1 | 0 | "
            "VOID: 1 | 1 020.50 lei | -1 571.50 lei |",
            "| 2026-12-06 | Joker | 1 | 135 | 945.00 lei | 2026-12-06T14:00:00Z | 2026-12-02T09:30:00Z | 0 | "
            "ÎN AȘTEPTARE: 1 | 0 | — | — |",
            "| C1_SG324Q | C1 | Loto 6/49 | 1 | 2 592.00 lei | 1 020.50 lei | -1 571.50 lei | 39.4% |",
            "| C1 — designuri garantate | 1 | 2 592.00 lei | 1 020.50 lei | -1 571.50 lei | 39.4% |",
            "| C3 — portofolii sub buget | 0 | — | — | — | — |",
            "| RND — control aleator | 0 | — | — | — | — |"]
    miss = [w for w in want if w not in md]
    ck("T1_fara_exceptie", not a["exception"], a["exception"])
    ck("T1_titluri", T.get("header") == HEADERS, T.get("header"))
    ck("T1_valori_exacte", not miss, miss)
    ck("T1_RND_void_nu_in_sume", "RND_649_B40 |" not in md)
    ck("T1_fara_bilete_si_numere", not number_lists("\n".join(x for v in T.values() for x in v))
       and "11, 12" not in md and "21, 22" not in md)

    with tempfile.TemporaryDirectory(prefix="ql649_hr_t2_") as d:
        build(Path(d), with_dec=False)
        b = run("pagina", Path(d))
    T = b["texts"]
    md = "\n".join(T.get("markdown", []))
    ck("T2_fara_decontari", not b["exception"] and T.get("header") == HEADERS and len(T.get("info", [])) == 1
       and "2026-12-03" in T["info"][0] and "ÎN AȘTEPTARE: 2" in md and "ÎN AȘTEPTARE: 1" in md,
       {"exc": b["exception"], "info": T.get("info")})

    for name, kw in (("T3_registru_alterat", {"bad_reg": True}), ("T4_referinta_gresita", {"bad_ref": True})):
        with tempfile.TemporaryDirectory(prefix="ql649_hr_t34_") as d:
            build(Path(d), **kw)
            c = run("pagina", Path(d))
        T = c["texts"]
        ck(name, not c["exception"] and len(T.get("error", [])) == 1 and not T.get("header")
           and not any("|" in x for x in T.get("markdown", [])), {k: len(v) for k, v in T.items()})

    src = PAGE.read_text(encoding="utf-8")
    ck("T5_static", '["bilete"]' not in src and "import torch" not in src and "quantum_limit" not in src
       and "engine" not in src and "ui_tu3" not in src)
    ck("T5_module_neincarcate", not a["modules_interzise"] and not b["modules_interzise"],
       a["modules_interzise"] + b["modules_interzise"])

    with tempfile.TemporaryDirectory(prefix="ql649_hr_t6_") as d:
        build(Path(d))
        (Path(d) / "main.py").write_text("import streamlit as st\nst.write('principal')\n", encoding="utf-8")
        e = run("mpa", Path(d))
    ck("T6_mpa", not e["exception"] and e["texts"].get("title") == ["Registrul pe hârtie — strategiile pe extrageri "
                                                                    "viitoare"], e["exception"])

    utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [("PASS " if ok else "FAIL ") + i + ("" if ok else f"  {json.dumps(det, ensure_ascii=False)[:800]}")
             for i, ok, det in res]
    n = sum(ok for _, ok, _ in res)
    lines.append(f"TESTE_HR {'PASS' if n == len(res) else 'FAIL'} {n}/{len(res)} utc={utc} "
                 f"pagina={hashlib.sha256(PAGE.read_bytes()).hexdigest()}")
    out = QL / f"xi/rezultate/HR/teste/TESTE_HR_{utc}.log"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"JURNAL {out}")
    return 0 if n == len(res) else 1


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--apptest":
        print("APPTEST_JSON " + json.dumps(apptest(sys.argv[2], sys.argv[3]), ensure_ascii=False))
        sys.exit(0)
    sys.exit(main())
