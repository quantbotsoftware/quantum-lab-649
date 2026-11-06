"""Testele de calificare ale fazei H (înainte de sigilarea codului și de construirea unică a datelor).

T1 build() (fără scriere) = recalculul independent din verifica_h.expected() (paritate);
T2 constructorul refuză o sursă cu sha diferit; T3 fără bilete/liste de numere; T4 pagina randează datele temporare
(AppTest în subproces, director temporar) cu toate secțiunile și fără „predic” în afara listei albe.
Rulare: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B xi/h/teste_h.py   (nu scrie în xi/rezultate/H)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    C, V = load("construieste_strategii"), load("verifica_h")
    res = {}
    d = C.build()
    meta = {"schema", "protocol_sha256", "surse", "text_fix", "positive_claims_allowed"}
    errs = V.compare({k: v for k, v in d.items() if k not in meta}, V.expected())
    res["T1_paritate"] = (not errs, errs[:10])
    k0 = next(iter(C.SURSE))
    good = C.SURSE[k0]
    C.SURSE[k0] = "0" * 64
    try:
        C.build()
        res["T2_refuz_sha"] = (False, "nu a refuzat")
    except SystemExit as e:
        res["T2_refuz_sha"] = ("REFUZ" in str(e), str(e)[:120])
    C.SURSE[k0] = good
    bad = V.walk_forbidden(d)
    res["T3_fara_bilete"] = (not bad, bad[:10])
    with tempfile.TemporaryDirectory(prefix="ql649_h_t4_") as t:
        r = Path(t)
        (r / "pages").mkdir()
        (r / "xi/rezultate/H").mkdir(parents=True)
        (r / "pages/1_Strategii.py").write_bytes((HERE.parents[1] / "pages/1_Strategii.py").read_bytes())
        d["utc"], d["constructor_sha256"] = "TEST", "TEST"
        body = (json.dumps(d, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode()
        (r / "xi/rezultate/H/STRATEGII_DATE.json").write_bytes(body)
        (r / "xi/rezultate/H/SIGILIU_DATE_H.json").write_text(
            json.dumps({"date_sha256": hashlib.sha256(body).hexdigest()}), encoding="utf-8")
        out = V.run_scenario("pagina", r)
    T = out["texts"]
    alltxt = "\n".join(x for v in T.values() for x in v)
    for w in V.WHITELIST:
        alltxt = alltxt.replace(w, "")
    res["T4_randare"] = (not out["exception"] and T.get("header") == V.HEADERS and "predic" not in alltxt.lower()
                         and not out["modules_interzise"],
                         {"exc": out["exception"][:2], "headers": T.get("header"), "mods": out["modules_interzise"]})
    ok = all(v[0] for v in res.values())
    for k, v in res.items():
        print(("PASS " if v[0] else "FAIL ") + k + ("" if v[0] else f"  {v[1]}"))
    print("TESTE_H", "PASS" if ok else "FAIL", f"{sum(v[0] for v in res.values())}/{len(res)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
