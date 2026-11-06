# AMENDAMENT XI-P2-01 — reguli de citire (Ungaria, Germania), după descărcare, fără valori văzute

Scris și sigilat ÎNAINTE de separarea jocurilor HU_otos, HU_hatos, DE_6aus49_sambata și înaintea oricărei analize.
Protocolul A (`01ff6235…`) §3 și anexa B permit corectarea regulii de citire printr-un amendament sigilat, cel mult unul
per joc, fără schimbarea jocului, a URL-urilor, a perioadei, a filtrului de zi, a subjocurilor, a analizei sau a
pragurilor. Incident: `xi/incidente/P2_01/INCIDENT_P2_01.json`.

## 1. Ce s-a văzut (numai forme: cifrele → 9; niciun număr extras)

Din `STRUCTURA` a descărcării (20:33:04Z) și din `structura_xlsx.py` (forme ale primelor 6 / ultimelor 2 rânduri):

- **HU_otos, HU_hatos:** fișierele încep cu marcajul BOM UTF-8 (`ï»¿` în decodarea latin-1) și conțin text UTF-8
  („Csütörtök”). Cu `encoding = latin-1` declarat, primul câmp al primului rând (extragerea cea mai nouă) ar fi
  `\ufeff…`/`ï»¿2026`, iar regula `antet = auto` l-ar fi tratat drept antet ⇒ **o extragere ar fi fost pierdută în
  tăcere**. Nu este o eroare semnalată de cititor, deci regula trebuia corectată înainte de separare.
- **HU_hatos:** are o coloană în plus, ziua săptămânii (`Csütörtök`/`Vasárnap`/`Szombat`), pe poziția 2; data este
  pe poziția 3 (regula declarată: 2 ⇒ eroare de dată). Numerele rămân ultimele 6 câmpuri.
- **DE_6aus49_sambata:** arhiva conține un singur `LOTTO6aus49_2021.xlsx` cu 67 de foi (una pe an), rânduri de titlu
  și antet pe 4 linii, note de subsol; două aranjamente: (a) `VA | dată | 6 numere | Zusatzzahl | …` (anii vechi),
  (b) `KW | dată | MI/SA | 6 numere | …` (după unificarea miercuri/sâmbătă). Data este o serie Excel (5 cifre).
- **FR_loto, US_powerball, US_megamillions:** conforme regulilor declarate; separate la 20:33:26Z cu cititorul v1
  (Mega Millions exclus: T = 776 < 1 000).

## 2. Regulile noi (`xi/p2/AMENDAMENTE_CITIRE_P2.json`)

- HU_otos: `encoding = utf-8` (BOM eliminat); restul neschimbat.
- HU_hatos: `encoding = utf-8`, `camp_data = 3`; restul neschimbat.
- DE_6aus49_sambata: toate foile; rândurile de date sunt cele cu data (serie Excel de 5 cifre sau dată text
  `zz.ll.aaaa`) pe poziția 1 (`filtru_rand`; celelalte rânduri — titluri, antete, note — se sar și se numără); data
  pe poziția 1; numerele: pozițiile 3–8 dacă poziția 2 este `MI`/`SA`, altfel 2–7. Filtrul de zi din B rămâne:
  **numai sâmbăta** (consecință consemnată: eventualele extrageri timpurii din altă zi a săptămânii sunt excluse de
  regula fixată în B, nu de acest amendament). Zusatzzahl/Superzahl ignorate (B).

## 3. Cod (cititorul) și calificare

`citire.py` a primit numai opțiuni declarative noi (`filtru_rand`, `camp_data_poz`, `camp_cheie_poz`, regula
`variante`) și numărarea extragerilor pe an; versiunea v1 și sigiliul v1 al codului sunt păstrate în
`xi/incidente/P2_01/`. `p2.py`, `descarca.py`, `verifica_p2.py` neschimbate (Q1–Q3 din `CALIFICARE_P2_20261031T202258Z`
rămân valabile: nu depind de cititor). Q4 nou (`q4_amendament.py` ⇒ `Q4_AMENDAMENT_P2_01_20261031T203555Z.json`, PASS):
fișiere sintetice HU cu BOM, Hatoslottó cu coloana zilei și două extrageri pe săptămână, DE cu foi pe ani, ambele
aranjamente, titluri, note, miercuri/duminică excluse, serii Excel și date text — toate reproduse exact; în plus
re-citirea brută a FR/US cu cititorul nou dă exact aceleași extrageri și același sha al rezervei (echivalență).
Codul se resigilează (`SIGILIU_COD_P2.json` v2, cu trimitere la v1) înaintea separării HU/DE.
