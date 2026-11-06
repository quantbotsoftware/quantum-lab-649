"""Generează RAPORT_WU649.md direct din artefactele sigilate (fără editare manuală a cifrelor)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE / "rezultate"


def j(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    seal, aseal = j(HERE / "SIGILIU_PROTOCOL_WU649.json"), j(HERE / "SIGILIU_AMENDAMENT_01.json")
    qual, ver = j(R / "CALIFICARE.json"), j(R / "VERIFICARE_NECALIFICARE.json")
    L = []
    a = L.append
    a("# RAPORT WU649 — „Urna ponderată” (cursa exponențială Luce, ordinea nevăzută marginalizată)\n")
    a(f"Protocol `WU649-P1` sigilat (sha256 `{seal['sha256']}`, {seal['sealed_at_utc']}) înainte de orice cod și "
      f"calcul WU649. Amendamentul 01 (toleranța de zgomot Armijo, τ = 1e-10) a fost sigilat tot înainte de cod "
      f"(sha256 `{aseal['sha256']}`, {aseal['sealed_at_utc']}). Ipoteza este nouă și distinctă în pista QL649. Nu este "
      "o salvare a QL649 (0/6), a BO649 (0/6) sau a DL-649 (înghețat, neatins). Modelele închise nu au fost importate "
      "sau rulate. OGLINDA nu a fost atinsă. Precedente: Luce (1959), Plackett (1975), Wallenius (1963), Yellott "
      "(1977), Hunter (2004), Caron & Doucet (2012), Takahasi & Mori (1974). Calculul este clasic, NumPy fp64 pe CPU, "
      "cu certificate în Q (`Fraction`). Nu se revendică hardware cuantic, avantaj cuantic sau noutate mondială. "
      "`positive_claims_allowed=false`.\n")
    a("## Ipoteza\n")
    a("Fiecare bilă are o propensiune constantă `w_j`. Extragerea este mulțimea primelor 6 sosiri dintr-o cursă de "
      "ceasuri exponențiale independente (echivalent: extragere Luce secvențială fără întoarcere). Ordinea nu este "
      "observată și se marginalizează exact. Sub această ipoteză numărările nu sunt statistici suficiente, deci "
      "compoziția extragerilor poate schimba ordinea propensiunilor față de B. Estimatorul este MAP, cu prior "
      "`N(0, 0.2²)` pe `log w`; legea este probabilitatea exactă de includere.\n")
    a("## Calificare (înainte de istoria reală)\n")
    a(f"Status **{qual['status']}** ({qual['passed']}/6), cod sha256 `{qual['code_sha256'][:16]}…` (arhivat "
      f"byte-identic în `rezultate/cod_calificare/wu649.py`), {qual['utc']}, {qual['seconds']:.0f} s. Numerele "
      "extrase din arhivă NU au fost folosite. Q2 a citit doar structura pașilor (numărul de extrageri pe zi), "
      "conform §4.\n")
    a("| Verificare | Rezultat | Detalii |")
    a("|---|---|---|")
    for c in qual["checks"]:
        a(f"| {c['id']} {c['name']} | {'PASS' if c['pass'] else 'FAIL'} | "
          f"`{json.dumps(c['detail'], ensure_ascii=False)[:300]}` |")
    a("")
    q5 = qual["checks"][4]["detail"]
    q6 = qual["checks"][5]["detail"]
    a("### Ce a eșuat și de ce (descriptiv, fără reparare)\n")
    a(f"- Martorul de informație Q5 a trecut. La numărări identice, WU distinge compoziția: "
      f"`max|Δq| = {q5['max_abs_dq_WU']:.6f}`. Este invariant la ordinea temporală "
      f"(`{q5['order_invariance_max_dq']:.1e}`).")
    a(f"- Martorul de decizie Q6 a eșuat. Anticiparea scrisă în protocol (`q_7 > q_6`) a fost greșită: "
      f"`q_6 = {q5['q6_q7_Hplus'][0]:.6f}`, `q_7 = {q5['q6_q7_Hplus'][1]:.6f}`. Biletul WU "
      f"`{q6['ticket_WU']}` coincide cu B `{q6['ticket_B']}` și cu R `{q6['ticket_R']}`.")
    a("- Interpretare propusă post-hoc, necertificată și netestată separat: într-o cursă pe mulțimi, `P(S)` "
      "este dominată de membrul cel mai lent al lui S. O bilă extrasă împreună cu bile slabe ar primi puțină "
      "informație despre propria pondere, pentru că blocajul este la colegii slabi. Una extrasă împreună cu bile "
      "tari ar primi mai multă. Ar fi un semn opus intuiției Bradley–Terry pe perechi („tăria calendarului”). "
      f"Efectul observat este de ordinul doi și mic: Δθ ≈ "
      f"{q5['theta6_theta7_Hplus'][0] - q5['theta6_theta7_Hplus'][1]:.4f}. În fixture-ul fixat, el a întărit "
      "alegerea lui B în loc să o schimbe.")
    a("- Conform §4, rezultatul se publică. Codul rămâne condiționat NEVALIDAT, iar istoria reală NU se atinge. "
      "Nu se face fixture „oglindit”, nu se schimbă anticiparea și nu se re-rulează. Eșecul este al martorului "
      "de decizie preînregistrat, nu un defect tehnic.\n")
    a("## Verificare independentă a necalificării\n")
    if ver:
        a(f"`verify_necalificare_wu649.py` (fără importuri din model și fără arhiva reală): **{ver['status']}** "
          f"{ver['n_checks'] - ver['n_fail']}/{ver['n_checks']}. Verificarea reconstruiește fixture-ul din textul "
          "protocolului, folosește o altă cuadratură (Gauss–Legendre, forma 3) și un Newton propriu, apoi "
          "reconfirmă: Q5 trece, Q6 eșuează și verdictul este `WU_NOT_QUALIFIED`. Verifică și identitatea exactă "
          "a cursei în Q, ordinea sigiliilor, arhivarea byte-identică a codului și absența artefactelor de "
          "backtest.\n")
        a("| Verificare | Rezultat | Valoare |")
        a("|---|---|---|")
        for c in ver["checks"]:
            a(f"| {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | `{str(c['value'])[:120]}` |")
        a("")
    a("## Consecințe\n")
    a("- **Niciun backtest WU649 pe arhivă**: zero ținte, zero predicții reale, zero porți evaluate.")
    a("- `wu649.py --real` și `--null` refuză (calificare absentă). `verify_wu649.py` (§7) rămâne cod "
      "condiționat nerulat.")
    a("- Rezultatul nu infirmă modelele Luce/Wallenius în general și nu spune nimic despre arhivă. Arată doar "
      "că familia WU-P1 nu a demonstrat, pe martorul preînregistrat, o decizie diferită de B și R.")
    a("- Orice idee nouă cere un protocol nou, sigilat înainte de cod. Nu este o variantă „reparată” a WU649.\n")
    a("## Fișiere\n")
    files = ["PREINREGISTRARE_WU649.md", "SIGILIU_PROTOCOL_WU649.json", "AMENDAMENT_01.md",
             "SIGILIU_AMENDAMENT_01.json", "wu649.py", "verify_wu649.py", "verify_necalificare_wu649.py",
             "raport_wu649.py", "tests/test_wu649.py", "rezultate/CALIFICARE.json",
             "rezultate/VERIFICARE_NECALIFICARE.json", "rezultate/cod_calificare/wu649.py", "jurnal/calificare.log"]
    man = {"generated_from_artifacts": True, "files": {}}
    for f in files:
        p = HERE / f
        if p.exists():
            man["files"][f] = {"sha256": sha(p), "bytes": p.stat().st_size}
            a(f"- `{f}` — sha256 `{man['files'][f]['sha256'][:16]}…`")
    (HERE / "RAPORT_WU649.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    man["files"]["RAPORT_WU649.md"] = {"sha256": sha(HERE / "RAPORT_WU649.md"),
                                       "bytes": (HERE / "RAPORT_WU649.md").stat().st_size}
    man.update({"status": qual["status"], "passed": qual["passed"], "positive_claims_allowed": False})
    (HERE / "MANIFEST_WU649.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print("RAPORT_WU649.md + MANIFEST_WU649.json generate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
