# PROTOCOL TU4-S17 — cererea „realinierea modelului și impactul real” (Mesajul 61): decizia înaintea codului, filtrul de admisibilitate pentru AFIȘARE și martorii lui

Scris și sigilat (`tu4/SIGILIU_TU4_S17.json`) ÎNAINTE de orice cod sau calcul al sesiunii S17. Calcul clasic
(float64 și aritmetică rațională exactă `fractions.Fraction`, CPU și GPU). Fără arhiva reală (se citesc numai cele 3
emisii sigilate din 2026-10-29, read-only), fără subagenți. `positive_claims_allowed=false`.

## 0. Context și autoritate

- Ceasul sistemului: 2026-10-28 ≈ 00:16Z (local 27 oct 20:16 EDT). Mesajul spune „28 Octombrie 2026”: concordă cu UTC.
- Primul pas exact al predării 20261028T000251Z a fost rulat (00:12Z) și a trecut integral: `Linger=yes`; 8649 numai
  127.0.0.1 (streamlit); ambele timere; hash-urile așteptate (`ed395ae6…`, `ae7b1145…`, `2a0100e3…`, `298d3ec6…`,
  `5d2b45cf…`, `118ad7b7…`, `f9b70967…`, `58bd3e44…`, `825dd62c…`, `ab3e1de9…`, `8117e8a3…`, `a15dc8fd…`,
  `e2fe385e…`, `092e3f5c…`); 8 × `drift []`; `LANT` 3 linii; 0 decontări; ultima rulare a judecătorului 00:00:44Z
  `nothing_to_settle` rc 0; `SCORURI_JU.mmap` 512 B; incidente numai `EM_01`, `FR_01`; health `ok`;
  `VERIFICARE_EM_PASS` 42/42; `VERIFICARE_JU_PASS` 13/13; 66 passed; 38 passed + 3 skipped; `"ok": true`;
  `UI_PASS` 15/15; DL exit 0. Jurnal: `tu4/rezultate/S17/primul_pas_S17_20261028T001221Z.log` (`659ac00a…`).
- Faptele din emisiile sigilate (citite din câmpurile `models`, fără recalcul):
  - 649: H1 λ = 0.18170, X² = 56.214 (df 48), biletul top `4 5 6 12 25 36`; H3 λ = 0.83412, biletul top
    `1 2 3 4 5 6` (baza cosinus netedă K = 4 ⇒ tendință monotonă pe etichete; NU este artefact de egalitate).
  - 540: H1 și H3 λ = 0 ⇒ modelele NU pariază (q = uniform); `1 2 3 4 5` este numai regula de egalitate.
  - Joker: H1 `3 5 6 18 45` (bila: λ = 0, nu pariază); H3 `1 2 3 4 5`, bila 20.
- Judecătorul (`tu4/judecator.py`, `8117e8a3…`) decontează fiecare flux prin factorul e al LEGII întregi q pe toate
  biletele, ln e = Σ_{i∈S} ln w_i − ln e_k(w) + ln C(n,k) evaluat pe extragerea reală S — NU prin potrivirile
  biletului top. Biletul top este o ilustrare a legii, nu obiectul testului. Judecătorul verifică sha-ul
  `ip_core.py` (`IP_CORE_SHA`, verificarea A4_cod).

## 1. Ce cere Mesajul 61 și decizia (fixată acum, înainte de cod)

### C1. „Modificări radicale în `ip_core.py` înainte de extragerea de joi” — REFUZATE (ca în S16 C1)

`ip_core.py` (`ab3e1de9…`) este înghețat prin sha în sigiliile EM, JU, UI și S16; judecătorul îl verifică la fiecare
decontare (A4_cod). Orice modificare înaintea joi 29 oct ar face ca cele 3 emisii deja sigilate să nu mai poată fi
decontate — adică ar distruge exact prima măsurare reală a testului. Un model schimbat după emisie este o ipoteză
nouă. `ip_core.py`, `judecator.py`, `emite.py`, emisiile, LANT, systemd și UI rămân NEATINSE în S17.

### C2. „Izolarea H1 (asimetrie reală, impact cinetic)” — REFUZATĂ pentru testul în curs; corecție factuală

1. Ce este H1 (`logw_h1`): ln w_i = λ·θ_i, cu θ_i abaterea standardizată a frecvenței numărului i în istoric și
   λ = max(0, 1 − (n−3)/X²) (contracție James–Stein). H1 este un model STATIONAR de frecvențe marginale. Nu conține
   mase, forțe, viteze sau coliziuni; biletul `4 5 6 12 25 36` = cele 6 numere cu frecvența istorică (contractată)
   cea mai mare. A-l numi „distribuție reală de impact cinetic” nu are suport în date.
2. Starea dovezilor: toate fluxurile sunt `EXPLORARE`, ln E = 0, zero decontări. X² = 56.2 la df 48 nu este, în
   sine, dovadă de asimetrie; valoarea p (aproximare χ²) se raportează în §2 fără prag și fără interpretare
   pozitivă. Marginea S16/W4 rămâne: niciun model nu poate depăși abaterea reală.
3. Eliminarea fluxurilor H3 din tribunal după emisie ar schimba M = 6 și pragul 600 ale unui test deja pornit și
   ar cere modificarea `judecator.py` (înghețat). Nu se face. Calculul H1 durează ≈ 1 s pe emisie: „concentrarea
   greutății de calcul” nu are obiect. O eventuală reducere PROSPECTIVĂ a tribunalului (numai H1) ar fi un protocol
   NOU, cu decizia explicită a utilizatorului, aplicabil numai emisiilor viitoare; S17 nu o începe.

### C3. „H4 — forța de impact a bilelor la coliziune” — NECALIFICAT a priori, fără cod

Criteriul (AGENTS.md): informație pre-țintă DISTINCTĂ și motivul unei decizii diferite față de repere.
- Arhiva conține numai mulțimi NEORDONATE de numere (plus bila Joker). Nu există măsurători de forță, masă,
  viteză, geometrie a urnei sau ordinea fizică de extragere (ordinea fizică verificată este absentă — vezi N3).
- Orice „H4” calculat din aceste date se reduce la o lege q pe bilete estimată din aceleași numărări — adică o
  familie din clasa H1/H3, cu parametri neidentificabili; nu aduce informație distinctă. Marginea W4 (S16) se aplică
  oricărei astfel de legi.
- Un flux nou în judecător ar cere protocol propriu, calificare Q1–Q6 și modificarea judecătorului înghețat.
Concluzie: necalificat, fără cod, fără calcul.

### C4. Filtrul de admisibilitate — ACCEPTAT ca strat de AFIȘARE separat (nu în judecător, nu în `ip_core.py`)

Ce se acceptă: utilizatorul nu vrea să vadă bilete „pur liniare” ca variante de joc. Aceasta este o preferință de
afișare legitimă. Ce se refuză: VOID-ul în judecător pe baza biletului afișat (judecătorul notează legea întreagă,
nu biletul; a anula un flux din cauza ilustrării lui ar arunca date după emisie și ar cere modificarea judecătorului
înghețat). „Recalcularea stărilor până la un vector neliniar” nu are sens pentru un model determinist (aceeași
intrare ⇒ aceeași ieșire); echivalentul corect, exact, este al doilea, al treilea… bilet ca densitate sub ACEEAȘI lege.

Declarat acum, fără excepție: filtrul NU schimbă nicio probabilitate. Sub urna uniformă, orice bilet are exact
aceeași șansă (6/49: 1/13 983 816); sub legea modelului, biletul admisibil are densitatea ≤ celei a biletului top.
Singurul efect practic real cunoscut al evitării biletelor „liniare” privește ÎMPĂRȚIREA unui câștig cu alți
jucători care aleg aceleași combinații populare, nu șansa de câștig; S17 nu măsoară acest efect și nu îl afirmă
cantitativ.

**Definiția (fixată):** biletul T (b numere distincte, sortate t_1 < … < t_b, b ≥ 3) este **pur liniar** ⇔ este o
progresie aritmetică: t_{j+1} − t_j = d pentru toți j, cu același d ≥ 1 (de ex. `1 2 3 4 5 6`, `5 10 15 20 25 30`).
Bila Joker nu intră în definiție.

**Densitatea biletului sub legea emisă:** q(T) ∝ Π_{i∈T} w_i (legea Fisher / Poisson condiționat a `ip_core.py`, pe
b = `ticket_size` numere). Scorul s(T) = Σ_{i∈T} ln w_i, calculat EXACT ca sumă de `Fraction(float)`. Ordinea totală:
s descrescător, apoi tuplul sortat lexicografic crescător (aceeași regulă de egalitate ca `ip_core.ticket`, care
alege etichetele mai mici). ln(q/u)(T) = s(T) − ln e_b(w) + ln C(n, b) (raportat).

**Biletul admisibil** al unui flux = primul bilet în ordinea totală care NU este pur liniar. Stări:
- `ADMISIBIL_IDENTIC`: biletul top emis nu este pur liniar ⇒ biletul admisibil = biletul top (filtrul nu schimbă nimic).
- `ADMISIBIL_INLOCUIT`: biletul top este pur liniar ⇒ se afișează biletul admisibil, cu rangul lui și raportul
  q(admisibil)/q(top).
- `NU_PARIAZA`: λ = 0 (max|ln w| = 0) ⇒ toate biletele au aceeași densitate; NU se afișează niciun bilet (orice
  bilet ar fi un artefact al regulii de egalitate, liniar sau nu). Analog pentru bila Joker cu λ = 0.

**Algoritmul principal:** căutare best-first exactă (heap) pornind de la biletul top, cu vecinii prin o singură
schimbare (un număr din bilet ↔ unul din afară), cheia (−s exact, tuplul). Corectitudine: pentru orice T ≠ top există
a ∈ T∖top, c ∈ top∖T cu c înaintea lui a în ordinea etichetelor (ln w_c > ln w_a sau egal și c < a); T − a + c este
strict înaintea lui T în ordinea totală (suma exactă strict mai mare sau egală și tuplul strict mai mic). Deci
fiecare bilet are un predecesor-vecin și heap-ul enumeră exact în ordinea totală.

**Verificarea independentă (GPU):** enumerarea COMPLETĂ a tuturor b-submulțimilor (6/49: 13 983 816; Joker 5/45:
1 221 759; 5/40: 658 008), scorurile float64 pe RTX 5060 (`torch`, cuda) și pe CPU (NumPy), apoi re-ordonare exactă
(`Fraction`) a ferestrei de candidați cu s_float ≥ s_max_neliniar − 1e-9.

## 2. Martorii și verdictele (fixate acum)

- **A0 (integritate):** sha `ip_core.py` = `ab3e1de9…`; sha-urile celor 3 emisii = cele din `LANT.jsonl`
  (`e2fe385e…`, `a15dc8fd…`, `092e3f5c…`); emisiile sunt 0444 și nemodificate după rulare.
- **A1 (numărarea progresiilor):** pentru (n, b) ∈ {(49, 6), (40, 5), (45, 5)}, numărul biletelor pur liniare din
  enumerarea completă = forma închisă Σ_{d≥1} max(0, n − (b−1)d); numărul total = C(n, b).
- **A2 (corectitudinea algoritmului):** în teste, pentru toate (n, b) cu 6 ≤ n ≤ 12, 3 ≤ b ≤ 5 și 3 vectori ln w
  (aleatoriu cu sămânța fixă 2026102817, cu valori repetate, constant), ordinea heap = sortarea forței brute pe
  primele 40 de bilete (sau toate, dacă sunt mai puține), iar biletul admisibil coincide.
- **A3 (date reale, fluxuri active):** pentru fiecare flux cu λ > 0 (649 H1, 649 H3, Joker H1, Joker H3):
  biletul admisibil din heap = cel din enumerarea GPU re-ordonată exact; |s_GPU − s_CPU| ≤ 1e-12 pe toate biletele;
  biletul admisibil nu este pur liniar; s(admisibil) ≤ s(top); dacă top nu este liniar ⇒ admisibil = top.
  Biletul top din heap = `top_ticket` emis (verificare a reproducerii).
- **A4 (fluxuri inactive):** pentru fiecare bloc cu λ = 0 (540 H1, 540 H3, bila Joker H1): max|ln w| = 0 exact ⇒
  `NU_PARIAZA`, niciun bilet/bilă afișat(ă).
- **Raportate fără prag:** rangul biletului admisibil (1 = top), ln(q/u) pentru top și admisibil, raportul
  q(admisibil)/q(top), probabilitatea sub uniform (identică pentru toate biletele), numărul de noduri heap, valoarea
  p χ²(X², df) pentru H1 649/Joker (informativ; NU dovadă), timpul GPU și temperatura GPU înainte/după.

Verdicte:
- Toate A0–A4 PASS ⇒ `S17_FILTRU_AFISARE_PASS`; C1/C2 REFUZATE, C3 NECALIFICAT; fișierul derivat
  `tu4/rezultate/S17/BILETE_ADMISIBILE_<UTC>.json` este biletul de afișare recomandat de sesiune.
- Orice FAIL sau UNKNOWN ⇒ incident tehnic `tu4/incidente/S17_01/` (fișierele încercării păstrate), fără schimbarea
  definiției sau pragurilor; reparație numai pentru conformitatea cu definiția de mai sus, cu amendament scris
  înainte. UNKNOWN nu devine PASS. Deciziile C1–C3 nu depind de martori.
- În niciun caz: afirmații pozitive, modificarea fișierelor înghețate, fluxuri noi, VOID-uri noi, emisii manuale.

## 3. Interfața și serverul 8649

`tu3/ui_tu3.py` este înghețat (S14 UI, S16) și verificat de `verifica_ui_s14.py` printr-o SINGURĂ înregistrare de
înlocuire (S3); o editare în S17 ar produce `UI_FAIL` permanent fără un protocol UI nou. De aceea S17 NU modifică
UI-ul; biletele admisibile se livrează în fișierul derivat și în raport. Integrarea lor în pagina TU4 este o
sesiune UI separată (protocol + sigiliu + înregistrare de înlocuire + verificator nou), propusă pentru S18.
Repornirea 8649 cerută se face după regresie, prin procedura documentată (sarcină de fundal
`systemd-run --user --scope --collect -q gtk-launch quantum-lab-649`, apoi `[lansator] health ok` în jurnalul NOU);
nu schimbă codul servit.

## 4. Fișiere, rulare, regresie

- Fișiere NOI numai: `tu4/s17_admisibil.py`, `tu4/tests/test_s17.py`, `tu4/rezultate/S17/*` (0444 după scriere).
  Sigiliul înregistrează sha-ul acestui protocol și hash-urile fișierelor înghețate, cu `code_files_present: []`.
- O singură rulare reală (deterministă) ⇒ `tu4/rezultate/S17/BILETE_ADMISIBILE_<UTC>.json` + jurnal.
- Regresia după cod: `tu4/tests/` (66 + noile teste), primul pas TU3 (38 + 3 skipped), suitele istorice (linia de
  bază rulată înaintea codului: `tu4/rezultate/S17/baseline_istoric_*.log`), `verifica_em_v01.py`, `verifica_ju.py`,
  `inlocuiri_tu3.py --verifica`, `verifica_ui_s14.py` (după repornire), cele 8 sigilii + sigiliul S17.
- Raport: `tu4/rezultate/S17/RAPORT_S17.md`; apoi `predari/OPERATIV.md`, Mesajul 61 în supliment,
  `predari/genereaza_predare.py`.
