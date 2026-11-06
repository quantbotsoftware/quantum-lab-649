# AMENDAMENT XI-C1_01 — martorii verificatorului, cu valori exacte calculate analitic (înainte de rerulare)

Scris și sigilat după INCIDENT_XI_C1_01 și ÎNAINTE de orice verificare de design. Motiv: martorul „J180 minus un
bilet ⇒ > 0 necâștigătoare” era greșit ales (J180 este redundant; vezi incidentul). Restul protocolului rămâne neschimbat.

**§4, martorii (înlocuire).** `verifica_design.py --martori` trece numai dacă fiecare număr de extrageri
necâștigătoare este EGAL cu valoarea exactă de mai jos, calculată pe hârtie înainte de rulare:

| Martor | Construcție | Necâștigătoare așteptate | Argument |
|---|---|---|---|
| M1 | J140 fără biletul (B_3, Joker 1) | **1 500** | Joker 1, D ⊆ B_1∪B_2∪B_3, cel mult 2 pe bloc: 3·C(5,2)²·5 |
| M2 | J180 fără toate cele 9 bilete cu Joker 1 | **1 149 750** | Joker 1, cel mult 2 nimeriri pe fiecare bloc: [x⁵](1+5x+10x²)⁹ |
| M3 | 6/49, un singur bilet {1,…,6} | **13 723 192** | C(49,6) − Σ_{h≥3} C(6,h)·C(43,6−h) |
| M4 | J180 fără biletul (B_1, Joker 1) | **0** (martor pozitiv) | redundanța J180 (incidentul XI_C1_01) |
| M5 | J140 fără biletul (B_3, Joker 1) și fără (B_4, Joker 1) | **calculat independent** prin enumerare combinatorică directă pe blocuri (cod separat în același fișier, fără măști), trebuie egal cu verificatorul | dublă implementare |

G2 rămâne: 0 extrageri necâștigătoare pe tot spațiul, cu martorii M1–M5 PASS în aceeași versiune a verificatorului.
