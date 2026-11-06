#!/usr/bin/env python3
"""Generează xi/rezultate/C4/RAPORT_C4.md din C4_REZULTATE.json (fără calcule noi)."""
import hashlib
import json
from pathlib import Path

D = Path(__file__).resolve().parent / "rezultate" / "C4"
R = json.loads((D / "C4_REZULTATE.json").read_text())
sha = hashlib.sha256((D / "C4_REZULTATE.json").read_bytes()).hexdigest()
m = R["meta"]
L = [f"# RAPORT C4 — probabilitatea de profit (planul V11, faza B)", "",
     f"Protocol `PROTOCOL_XI_C4.md` (`{m['protocol_sha256'][:12]}…`) + `AMENDAMENT_XI_C4_01.md` "
     f"(`{m['amendament_sha256'][:12]}…`), ambele sigilate înainte de cod. Script `{m['script_sha256'][:12]}…`. "
     f"Rezultate `C4_REZULTATE.json` sha256 `{sha}`. Bază `{m['database_sha256'][:12]}…`; fereastra principală "
     f"{m['window'][0]} … {m['window'][1]} (312 date comune). M = {m['M']:,} sezoane, {m['seconds']} s pe {m['gpu']}.",
     "", f"**Porți de corectitudine: {'PASS' if R['GATES_PASS'] else 'FAIL'}** "
     f"(V1 media față de analitic, V2 probabilități exacte prin enumerare exhaustivă, V3 prima dată).", "",
     "Sume **brute, fără impozit**; biletele sunt uniforme (niciun model de predicție). "
     "`positive_claims_allowed=false`.", "", "## Randamentul unui bilet (valoare așteptată / preț)", "",
     "| Joc | Fereastra 3 ani | De la 2010 | Șansa la orice premiu |", "|---|---:|---:|---:|"]
for g in ("649", "540", "joker"):
    L.append(f"| {g} | {R['rho_window'][g]:.1%} | {R['rho_since_2010'][g]:.1%} | 1 din "
             f"{R['V2_probabilitati'][g]['one_in']:.1f} |")
L += ["", "## Probabilitatea de a fi pe plus (net ≥ 0)", "",
      "| Strategie | Miză/dată | 1 an | 5 ani | 10 ani | Net median 1 an | Randament mediu 10 ani |",
      "|---|---:|---:|---:|---:|---:|---:|"]
for name, s in R["strategies"].items():
    h = s["horizons"]
    L.append(f"| {name} | {s['stake_per_date']:.0f} lei | {h['1']['P_net_ge_0']:.2%} | {h['5']['P_net_ge_0']:.2%} | "
             f"{h['10']['P_net_ge_0']:.2%} | {h['1']['net_quantiles_1_5_25_50_75_95_99'][3]:,.0f} lei | "
             f"{h['10']['return_mean']:.1%} |")
L += ["", "## Porți", "", "| Strategie | net/dată analitic | simulat | SE | V1 |", "|---|---:|---:|---:|---|"]
for name, s in R["strategies"].items():
    v = s["V1"]
    L.append(f"| {name} | {v['analytic_net_per_date']:.3f} | {v['sim_net_per_date']:.3f} | {v['se']:.3f} | "
             f"{'PASS' if v['pass'] else 'FAIL'} |")
L += ["", "| Joc | P(premiu, 1 bilet) exact | simulat | V3 |", "|---|---:|---:|---|"]
for g, v in R["V3_prima_data"].items():
    L.append(f"| {g} | {v['exact']:.5f} | {v['sim']:.5f} | {'PASS' if v['pass'] else 'FAIL'} |")
L += ["", "## Interpretare (scrisă după rezultat; cifrele de mai sus nu se schimbă)", "",
      "Notă de corectitudine: generatorul conținea un text de interpretare scris înainte de rulare "
      "(„probabilitatea scade cu orizontul pentru toate strategiile”), infirmat de date; a fost înlocuit înainte de "
      "publicare, fără a modifica vreun număr.", "",
      "1. **Randamentul mediu este 34–38% din miză** în fereastra de 3 ani (20–28% de la 2010): în medie se pierd "
      "62–66% din bani, la orice buget și orice orizont.",
      "2. **Probabilitatea de a fi pe plus este mică (0.3–5%) și NU scade monoton cu orizontul**: profitul vine "
      "aproape exclusiv din premii rare și mari (categoria I sau II), a căror șansă cumulată crește cu timpul, "
      "în timp ce pierderea de bază crește liniar. Rezultatul este un joc al cozii, nu un venit constant.",
      "3. **Bugetele mai mari nu îmbunătățesc randamentul**; doar scalează pierderea (mediana la 1 an: de la "
      "−520 lei pentru 5 lei/dată la −43 800 lei pentru ~500 lei/dată).",
      "4. Obiectivul „câștiguri mici constante fără minus” este infirmat cantitativ pentru strategiile simple; "
      "fazele următoare (designuri garantate C1, ferestre EV+ C2, portofoliu anti-mulțime C3) se evaluează în "
      "același simulator, cu aceleași porți."]
(D / "RAPORT_C4.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
